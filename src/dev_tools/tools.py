from __future__ import annotations

import asyncio
import dataclasses
import os
import shlex
import shutil
from typing import Any

import jsonschema

from dev_tools.file_async import read_file_async, write_file_async


class InvalidReadWritePolicy(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)


def normalize_relative_path(rel_path: str) -> str:
    abs_path = os.path.abspath(rel_path)
    return os.path.relpath(abs_path, os.getcwd())


class ReadWritePolicy:
    def __init__(
        self,
        write_mode: bool,
        allow_write: list[str] | None = None,
        read_only: list[str] | None = None,
    ):
        self._write_mode = write_mode
        self._allow_write = allow_write
        self._read_only = read_only

        if write_mode and allow_write:
            raise InvalidReadWritePolicy(
                "allow_write list disallowed when write_mode=True"
            )

    def _is_whitelisted(self, rel_path: str) -> bool:
        return self._allow_write is not None and any(
            rel_path.startswith(x) for x in self._allow_write
        )

    def _is_blacklisted(self, rel_path: str) -> bool:
        return self._read_only is not None and any(
            rel_path.startswith(x) for x in self._read_only
        )

    def is_readable(self, rel_path: str) -> bool:
        # Disallow everything outside the working directory
        path = os.path.abspath(rel_path)
        return path.startswith(os.getcwd())

    def is_writable(self, rel_path: str) -> bool:
        # To be writable, we at a minimum need to be readable
        if not self.is_readable(rel_path):
            return False

        return (self._write_mode and not self._is_blacklisted(rel_path)) or (
            not self._write_mode and self._is_whitelisted(rel_path)
        )

    def has_writable_paths(self) -> bool:
        return self._write_mode or self._allow_write is not None


@dataclasses.dataclass
class ToolSchema:
    name: str
    description: str
    param_schema: dict[str, object]

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ToolSchema:
        return ToolSchema(data["name"], data["description"], data["parameters"])


class Tool:
    def schema(self) -> ToolSchema:
        raise NotImplementedError()

    async def execute(self, **kwargs) -> str:
        raise NotImplementedError()


@dataclasses.dataclass
class UserToolDef:
    schema: ToolSchema
    program: str
    args: list[str] | None = None
    shell: bool = False

    @staticmethod
    def from_dict(data: dict[str, Any]) -> UserToolDef:
        return UserToolDef(
            ToolSchema.from_dict(data["schema"]),
            data["program"],
            data.get("args", None),
            data.get("shell", False),
        )


class UserTool(Tool):
    def __init__(self, tool_def: UserToolDef):
        super().__init__()
        self._tool_def = tool_def

    def schema(self) -> ToolSchema:
        return self._tool_def.schema

    async def execute(self, **kwargs) -> str:
        # Validate parameters
        try:
            jsonschema.validate(
                instance=kwargs, schema=self._tool_def.schema.param_schema
            )
        except jsonschema.ValidationError as err:
            return f"Error: {err.message}"
        except jsonschema.SchemaError as err:
            return f"Error: {err.message}"

        cmd = [self._tool_def.program]

        # Safely substitute into args
        if self._tool_def.args is not None:
            if self._tool_def.shell:
                cmd += [
                    shlex.quote(x.format(**kwargs, cwd=os.getcwd()))
                    for x in self._tool_def.args
                ]
            else:
                cmd += [
                    x.format(**kwargs, cwd=os.getcwd()) for x in self._tool_def.args
                ]

        if self._tool_def.shell:
            proc = await asyncio.create_subprocess_shell(
                " ".join(cmd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

        else:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

        stdout, _ = await proc.communicate()

        if stdout:
            return stdout.decode()
        return "Error: no output"


class ListFiles(Tool):
    def schema(self) -> ToolSchema:
        return ToolSchema(
            "list_files",
            "List relative paths for files in the current working directory",
            {
                "type": "object",
                "properties": {
                    "filter_regex": {
                        "type": "string",
                        "description": "Optional regex filter for relative paths. Must match the full relative path.",
                    }
                },
            },
        )

    async def execute(self, filter_regex: str | None = None) -> str:
        proc = await asyncio.create_subprocess_exec(
            "find",
            ".",
            "-regex",
            filter_regex or ".*",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if stdout:
            lines = stdout.decode().split("\n")
            lines = [x[2:] for x in lines]
            return "\n".join(lines)
        if stderr:
            return stderr.decode()
        return ""


class SearchFiles(Tool):
    def schema(self) -> ToolSchema:
        return ToolSchema(
            "search_files",
            "Get the relative path for files matching the filter regex and containing the search regex",
            {
                "type": "object",
                "properties": {
                    "filter_regex": {
                        "type": "string",
                        "description": "Regex filter for file relative path",
                    },
                    "search_regex": {"type": "string", "description": "Search regex"},
                },
                "required": ["search_regex"],
            },
        )

    async def execute(self, search_regex: str, filter_regex: str | None = None) -> str:
        proc = await asyncio.create_subprocess_exec(
            "find",
            "*",
            "-regex",
            filter_regex or ".*",
            "-exec",
            "grep",
            "-qE",
            search_regex,
            "{}",
            ";",
            "-exec",
            "echo",
            "{}",
            ";",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if stdout:
            return stdout.decode()
        if stderr:
            return stderr.decode()

        return "Error: no output"


class ReadFile(Tool):
    def __init__(self, policy: ReadWritePolicy):
        super().__init__()
        self._policy = policy

    def schema(self) -> ToolSchema:
        return ToolSchema(
            "read_file",
            "Read the content of a file in the current working directory",
            {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "Relative path to the file",
                    },
                },
                "required": ["relative_path"],
            },
        )

    async def execute(self, relative_path: str) -> str:
        if not self._policy.is_readable(relative_path):
            return f"Error: {relative_path} is not readable under the ReadWritePolicy"

        path = os.path.abspath(relative_path)
        return await read_file_async(path)


class WriteFile(Tool):
    def __init__(self, write_policy: ReadWritePolicy):
        super().__init__()
        self._policy = write_policy

    def schema(self) -> ToolSchema:
        return ToolSchema(
            "write_file",
            "Create or replace file in the current working directory.",
            {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "Relative path to the file",
                    },
                    "text": {
                        "type": "string",
                        "description": "The content to write to the file",
                    },
                },
                "required": ["relative_path", "text"],
            },
        )

    async def execute(self, relative_path: str, text: str) -> str:
        normalized = normalize_relative_path(relative_path)
        if not self._policy.is_writable(normalized):
            return f"Error: {normalized} is not writable under the ReadWritePolicy"

        path = os.path.abspath(normalized)
        await write_file_async(path, text)
        return "ok"


class MakeDirs(Tool):
    def __init__(self, write_policy: ReadWritePolicy):
        super().__init__()
        self._policy = write_policy

    def schema(self) -> ToolSchema:
        return ToolSchema(
            "make_dirs",
            "Create a directory, including intermediate directories.",
            {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "Directory path to create",
                    },
                },
                "required": ["relative_path"],
            },
        )

    async def execute(self, relative_path: str) -> str:
        normalized = normalize_relative_path(relative_path)
        if not self._policy.is_writable(normalized):
            return f"Error: {normalized} is not writable under the ReadWritePolicy"

        path = os.path.abspath(normalized)
        os.makedirs(path, exist_ok=True)

        return "ok"


class RemovePath(Tool):
    def __init__(self, write_policy: ReadWritePolicy):
        super().__init__()
        self._policy = write_policy

    def schema(self) -> ToolSchema:
        return ToolSchema(
            "remove_path",
            "Remove a file or directory.",
            {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "Path to remove",
                    },
                },
                "required": ["relative_path"],
            },
        )

    async def execute(self, relative_path: str) -> str:
        normalized = normalize_relative_path(relative_path)
        if not self._policy.is_writable(normalized):
            return f"Error: {normalized} is not writable under the ReadWritePolicy"

        path = os.path.abspath(normalized)
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(relative_path)

        return "ok"
