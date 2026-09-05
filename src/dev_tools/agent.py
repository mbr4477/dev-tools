import json

from openai import AsyncOpenAI
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner

from dev_tools.tools import Tool


class Agent:
    def __init__(self, tools: list[Tool], max_iters: int | None = None):
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
                    model="gpt-5.6-luna",
                    tools=tools,
                    input=input_list,
                )
                if response.output_text:
                    live.update(Markdown(response.output_text))
                else:
                    live.update("[bold green]✔ Done[/bold green]")

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
