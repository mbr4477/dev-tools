import asyncio
import json
import sys

from openai import AsyncOpenAI
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner

from dev_tools.tools import Tool


class Agent:
    def __init__(
        self,
        model: str,
        instructions: str,
        tools: list[Tool],
        max_iters: int | None = None,
    ):
        self._model = model
        self._instructions = instructions
        self._tools = {x.schema()["name"]: x for x in tools}
        self._max_iters = max_iters

    async def run(self, prompt: str):
        client = AsyncOpenAI()

        tools = [x.schema() for x in self._tools.values()]

        input_list = [{"role": "user", "content": prompt}]

        working = True
        iters = 0
        console = Console()
        while working:
            with Live("", console=console, vertical_overflow="visible") as live:
                live.update(Spinner("dots", text="[yellow]Working...[/yellow]"))
                response = await client.responses.create(
                    model=self._model,
                    tools=tools,
                    instructions=self._instructions,
                    input=input_list,
                )
                if response.output_text:
                    live.update(Markdown(response.output_text))
                else:
                    live.update("")

            # Assume we are done
            working = False

            # Check for max iters
            iters += 1
            if self._max_iters is not None and iters >= self._max_iters:
                break

            input_list += response.output

            for item in response.output:
                if item.type == "function_call":
                    if item.name in self._tools:
                        args = json.loads(item.arguments)
                        print(
                            f"    {item.name}({','.join(k + '=' + v for k, v in args.items())})"
                        )
                        try:
                            result = await self._tools[item.name].execute(**args)
                            input_list.append(
                                {
                                    "type": "function_call_output",
                                    "call_id": item.call_id,
                                    "output": result,
                                }
                            )
                        except Exception as e:
                            print("   ", e)
                            input_list.append(
                                {
                                    "type": "function_call_output",
                                    "call_id": item.call_id,
                                    "output": str(e),
                                }
                            )
                    else:
                        input_list.append(
                            {
                                "type": "function_call_output",
                                "call_id": item.call_id,
                                "output": f"Error: no tool named {item.name}",
                            }
                        )
                    working = True


async def async_main(model: str, instructions: str, tools: list[Tool], prompt: str):
    await Agent(model, instructions, tools).run(prompt)


def main():
    import argparse

    from dev_tools.tools import List, Search, Read

    tools = {x.schema()["name"]: x for x in (List(), Search(), Read())}
    tool_names = list(tools.keys())

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow",
        type=str,
        help=f"comma separate list of allowed tools: {','.join(tool_names)}",
    )

    ins_group = parser.add_mutually_exclusive_group(required=True)
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

    args = parser.parse_args()

    allowed_tool_names = args.allow.split(",") if args.allow else []
    for tool_name in allowed_tool_names:
        if tool_name not in tools:
            print(f"Error: unknown tool '{tool_name}'")
            sys.exit(1)

    instructions = None
    if args.instructions_file:
        with open(args.instructions_file, "r") as ins_file:
            instructions = ins_file.read()
    elif args.instructions:
        instructions = args.instructions

    prompt = None
    if args.prompt:
        prompt = args.prompt
    else:
        prompt = sys.stdin.read()

    asyncio.run(
        async_main(
            args.model, instructions, [tools[x] for x in allowed_tool_names], prompt
        )
    )
