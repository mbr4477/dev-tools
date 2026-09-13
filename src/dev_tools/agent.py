import asyncio
import json
import os
import sys

from rich.console import Console
from rich.markdown import Markdown

from dev_tools.backends import AgentBackend
from dev_tools.backends.openai import OpenAIBackend
from dev_tools.file_async import read_file_async
from dev_tools.tools import Tool


class Agent:
    """A class encapsulating a multi-turn agent with tool calling."""

    def __init__(
        self,
        backend: AgentBackend,
        instructions: str | None = None,
        tools: list[Tool] | None = None,
        max_iters: int | None = None,
    ):
        """
        Args:
            backend: The agent backend.
            instructions: The system prompt.
            tools: The tools the agent can call.
            max_iters: The max number of agent API calls.
        """
        self._backend = backend
        self._instructions = instructions
        self._tool_dict = {x.schema()["name"]: x for x in tools} if tools else {}
        self._max_iters = max_iters

    async def run(self, prompt: str, json_schema: dict[str, object] | None = None):
        """Run the agent.

        Args:
            prompt: The initial prompt.
            json_schema: An optional schema for structured output
        """
        session = self._backend.create_session(self._instructions)
        session.add_user_content(prompt)

        # Run the agentic loop
        working = True
        iters = 0
        is_piped = not sys.stdout.isatty()
        console = Console(stderr=True, force_terminal=not is_piped)
        with console.status("[bold yellow]Working...[/]"):
            while working:
                try:
                    response = await self._backend.create_response(session, json_schema)
                except Exception:
                    console.log(response.session)
                    raise

                session = response.session
                if response.output:
                    console.log(Markdown(response.output))

                if response.structured_output:
                    console.log(response.structured_output)
                    print(json.dumps(response.structured_output, indent=2), flush=True)

                # Assume we are done
                working = False

                # Check for max iters
                iters += 1
                if self._max_iters is not None and iters >= self._max_iters:
                    break

                # Look for function tool calls to execute
                for tool_call in response.tool_calls:
                    if tool_call.name in self._tool_dict:
                        # Collect the arguments
                        console.log(
                            f"  [dim white]{tool_call.name}({json.dumps(tool_call.args)})[/]"
                        )
                        try:
                            # Call the tool
                            result = await self._tool_dict[tool_call.name].execute(
                                **tool_call.args
                            )
                            session.add_tool_output(tool_call.call_id, result)
                        except Exception as e:  # noqa: BLE001
                            console.log(f"[bold red]{e}[/]")
                            session.add_tool_output(tool_call.call_id, str(e))
                    else:
                        console.log(f"[bold red]No tool named '{tool_call.name}'[/]")
                        session.add_tool_output(
                            tool_call.call_id, f"No tool named '{tool_call.name}'"
                        )

                    # If a tool call was at least attempted, we are still working
                    working = True


async def async_main():
    import argparse

    from dev_tools.tools import (
        ListFiles,
        MakeDirs,
        ReadFile,
        ReadWritePolicy,
        RemovePath,
        SearchFiles,
        ToolDef,
        UserTool,
        WriteFile,
    )

    if os.path.exists(".agent-tools.json"):
        content = json.loads(await read_file_async(".agent-tools.json"))
        tool_defs = [ToolDef.from_dict(x) for x in content]
        user_tools = {x.schema.name: UserTool(x) for x in tool_defs}
    else:
        user_tools = {}

    parser = argparse.ArgumentParser()
    write_group = parser.add_mutually_exclusive_group(required=False)
    write_group.add_argument("--write", action="store_true", help="enable write mode")
    write_group.add_argument(
        "--allow-write",
        action="append",
        type=str,
        help="whitelist a path as writable in the default read-only mode",
    )
    parser.add_argument(
        "--read-only",
        type=str,
        action="append",
        help="mark a relative path as read-only",
        dest="read_only",
    )
    allow_group = parser.add_mutually_exclusive_group(required=False)
    allow_group.add_argument(
        "--allow",
        type=str,
        action="append",
        choices=list(user_tools.keys()),
        help="allow use of a user-defined tool",
    )
    allow_group.add_argument(
        "--allow-all", "-A", action="store_true", help="allow all user tools"
    )

    ins_group = parser.add_mutually_exclusive_group(required=False)
    ins_group.add_argument("--instructions", "-I", type=str, help="agent instructions")
    ins_group.add_argument(
        "--instructions-file",
        type=str,
        help="path to file containing agent instructions",
    )

    prompt_group = parser.add_mutually_exclusive_group(required=False)
    prompt_group.add_argument("--prompt", "-p", type=str, help="prompt")
    prompt_group.add_argument(
        "--prompt-file", type=str, help="path to file containing prompt"
    )

    parser.add_argument(
        "--model", "-m", type=str, help="model identifier", required=True
    )

    parser.add_argument(
        "--json-schema",
        type=str,
        help="json schema for model output. Objects must have `additionalProperties: false` and all properties listed in `required`.",
    )

    args = parser.parse_args()

    # Create policy
    policy = ReadWritePolicy(args.write, args.allow_write, args.read_only)

    # Configure allowed tools
    if not args.allow_all:
        user_tools = (
            {k: v for k, v in user_tools.items() if k in args.allow}
            if args.allow
            else {}
        )
    system_tools = {
        x.schema()["name"]: x for x in (ListFiles(), SearchFiles(), ReadFile(policy))
    }

    if policy.has_writable_paths():
        write_tools = [
            WriteFile(policy),
            MakeDirs(policy),
            RemovePath(policy),
        ]
        system_tools.update({x.schema()["name"]: x for x in write_tools})

    tools = {**system_tools, **user_tools}

    instructions = None
    if args.instructions_file:
        instructions = await read_file_async(args.instructions_file)
    elif args.instructions:
        instructions = str(args.instructions)

    prompt = ""
    if args.prompt:
        prompt = args.prompt
    elif args.prompt_file:
        prompt = await read_file_async(args.prompt_file)

    # If text is piped in, append it to the prompt
    if not sys.stdin.isatty():
        prompt += f"\n\n{sys.stdin.read()}"

    prompt = prompt.strip()

    assert prompt, "No prompt provided"

    backend = OpenAIBackend(args.model, list(tools.values()))

    await Agent(
        backend,
        instructions,
        list(tools.values()),
    ).run(prompt, json.loads(args.json_schema) if args.json_schema else None)


def main():
    asyncio.run(async_main())
