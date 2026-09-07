import asyncio
import dataclasses
import json
import os
import shlex
from typing import Any, Self

import jsonschema


@dataclasses.dataclass
class ToolSchema:
    type_: str
    name: str
    description: str
    parameters: Any

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Self:
        return ToolSchema(
            data["type"], data["name"], data["description"], data["parameters"]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type_,
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclasses.dataclass
class ToolDef:
    schema: ToolSchema
    program: str
    args: list[str] | None = None
    shell: bool = False

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Self:
        return ToolDef(
            ToolSchema.from_dict(data["schema"]),
            data["program"],
            data.get("args", None),
            data.get("shell", False),
        )


class Tool:
    def schema(self) -> dict[str, Any]:
        raise NotImplementedError()

    async def execute(self, **kwargs) -> str:
        raise NotImplementedError()


class UserTool(Tool):
    def __init__(self, tool_def: ToolDef):
        super().__init__()
        self._tool_def = tool_def

    def schema(self) -> dict[str, Any]:
        return self._tool_def.schema.to_dict()

    async def execute(self, **kwargs) -> str:
        # Validate parameters
        try:
            jsonschema.validate(instance=kwargs, schema=self.schema()["parameters"])
        except jsonschema.exceptions.ValidationError as err:
            return f"Error: {err.message}"
        except jsonschema.exceptions.SchemaError as err:
            return "Error: tool parameter schema is malformed"

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
    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": "list_files",
            "description": "List relative paths for files in the current working directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter_regex": {
                        "type": "string",
                        "description": "Optional regex filter for relative paths. Must match entire relative path.",
                    }
                },
            },
        }

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
    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": "search_files",
            "description": "Get the relative path for files matching the filter regex and containing the search regex",
            "parameters": {
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
        }

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
    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": "read_file",
            "description": "Read the content of a file in the current working directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "Relative path to the file",
                    },
                },
                "required": ["relative_path"],
            },
        }

    async def execute(self, relative_path: str) -> str:
        path = os.path.abspath(relative_path)
        if not path.startswith(os.getcwd()):
            return (
                f"Error: {relative_path} resolves outside the current working directory"
            )

        with open(path, "r") as file:
            content = file.read()

        return content


class WriteFile(Tool):
    def __init__(self, read_only_prefixes: list[str] | None = None):
        super().__init__()
        self._ro_prefixes = read_only_prefixes or []

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": "write_file",
            "description": f"Create or replace file in the current working directory. Disallowed paths: {','.join(self._ro_prefixes)}",
            "parameters": {
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
        }

    async def execute(self, relative_path: str, text: str) -> str:
        path = os.path.abspath(relative_path)
        if not path.startswith(os.getcwd()):
            return (
                f"Error: {relative_path} resolves outside the current working directory"
            )

        for prefix in self._ro_prefixes:
            if relative_path.startswith(prefix):
                return f"Error: {relative_path} is disallowed because {prefix} is read-only"

        with open(path, "w") as file:
            file.write(text)

        return "Success"
