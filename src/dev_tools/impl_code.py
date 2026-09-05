import asyncio
import argparse
import json
import os

from halo import Halo
from openai import AsyncOpenAI

from dev_tools.tools import ListFiles, SearchFiles, ReadFile
from dev_tools.agent import Agent

# Create files
# Edit files
# Setup commands
# Build command
# Execute/test command


async def async_main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", type=str, help="initial prompt")
    args = parser.parse_args()

    agent = Agent(tools=[ListFiles(), SearchFiles(), ReadFile()])
    await agent.run(args.prompt)


def main():
    asyncio.run(async_main())
