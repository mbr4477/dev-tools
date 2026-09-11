import asyncio
import json
import os
import sys

from openai import AsyncOpenAI, Omit
from openai.types.responses import ResponseTextConfigParam
from rich.console import Console
from rich.markdown import Markdown

from dev_tools.file_async import read_file_async
from dev_tools.tools import Tool


class Agent:
    """A class encapsulating a multi-turn agent with tool calling."""

    def __init__(
        self,
        model: str,
        tools: list[Tool],
        instructions: str | None = None,
        json_schema: dict[str, object] | None = None,
        max_iters: int | None = None,
    ):
        """
        Args:
            model: The model identifier.
            tools: A list of permitted tools.
            instructions: The system prompt.
            json_schema: A json schema for the final output.
            max_iters: The max number of agent API calls.
        """
        self._model = model
        self._tools = {x.schema()["name"]: x for x in tools}
        self._instructions = instructions
        self._json_schema = json_schema
        self._max_iters = max_iters

    async def run(self, prompt: str):
        """Run the agent.

        Args:
            prompt: The initial prompt.
        """
        # Create the client, tool schemas, and initial input list
        client = AsyncOpenAI()
        tools = [x.schema() for x in self._tools.values()]
        input_list = [{"role": "user", "content": prompt}]

        text = Omit()
        if self._json_schema is not None:
            text = ResponseTextConfigParam(
                {
                    "format": {
                        "type": "json_schema",
                        "name": self._json_schema.get("name", "output"),
                        "strict": True,
                        "schema": self._json_schema,
                    }
                }
            )

        # Run the agentic loop
        working = True
        iters = 0
        is_piped = not sys.stdout.isatty()
        console = Console(stderr=True, force_terminal=not is_piped)
        with console.status("[bold yellow]Working...[/]"):
            while working:
                response = await client.responses.create(
                    model=self._model,
                    tools=tools,
                    instructions=self._instructions,
                    input=input_list,
                    text=text,
                )
                if response.output_text:
                    if self._json_schema is not None:
                        try:
                            console.log(json.loads(response.output_text))
                        except json.JSONDecodeError as e:
                            console.log(f"[bold red]{e}[/]")
                        print(response.output_text, flush=True)
                    else:
                        console.log(Markdown(response.output_text))

                # Assume we are done
                working = False

                # Check for max iters
                iters += 1
                if self._max_iters is not None and iters >= self._max_iters:
                    break

                # Append to the conversation history
                input_list += response.output

                # Look for function tool calls to execute
                for item in response.output:
                    if item.type == "function_call":
                        if item.name in self._tools:
                            # Collect the arguments
                            args = json.loads(item.arguments)
                            console.log(
                                f"  [dim white]{item.name}({','.join(k + '=' + json.dumps(v) for k, v in args.items())})[/]"
                            )
                            try:
                                # Call the tool
                                result = await self._tools[item.name].execute(**args)
                                input_list.append(
                                    {
                                        "type": "function_call_output",
                                        "call_id": item.call_id,
                                        "output": result,
                                    }
                                )
                            except Exception as e:  # noqa: BLE001
                                console.log(f"[bold red]{e}[/]")
                                input_list.append(
                                    {
                                        "type": "function_call_output",
                                        "call_id": item.call_id,
                                        "output": str(e),
                                    }
                                )
                        else:
                            console.log(f"[bold red]No tool named '{item.name}'[/]")
                            input_list.append(
                                {
                                    "type": "function_call_output",
                                    "call_id": item.call_id,
                                    "output": f"Error: no tool named '{item.name}'",
                                }
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

    await Agent(
        args.model,
        list(tools.values()),
        instructions,
        json.loads(args.json_schema) if args.json_schema else None,
    ).run(prompt)


def main():
    asyncio.run(async_main())
