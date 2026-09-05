import asyncio
import os
from typing import Any


class Tool:
    def schema(self) -> dict[str, Any]:
        raise NotImplementedError()

    async def execute(self, **args) -> str:
        raise NotImplementedError()


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
