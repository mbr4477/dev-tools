import argparse
import asyncio
import shutil
import subprocess
import tempfile
import os
from pathlib import Path

from halo import Halo
from openai import AsyncOpenAI


client = AsyncOpenAI()

async def get_suggested_fix(path: str, clang_tidy_out: str) -> str:
    with Halo(text="Getting agent suggestion", spinner="dots") as spinner:
        with open(path, "r") as code_file:
            code_content = code_file.read()

        prompt = ">>>>> INPUT FILE\n"
        prompt += code_content
        prompt += "\n<<<<<\n"
        prompt += ">>>>> STATIC ANALYSIS FINDINGS\n"
        prompt += clang_tidy_out
        prompt += "\n<<<<<"
        prompt += "Make the minimal changes to resolve all the errors consistent with modern C++ best practices. "
        prompt += "Maintain consistency with formatting and patterns in the file. "
        prompt += "Output only the corrected file."
        response = await client.responses.create(
            model="gpt-5.6-luna",
            input=prompt,
        )
        spinner.succeed()
        return response.output_text


async def get_findings(path: str) -> str | None:
    with Halo(text="Analyzing code", spinner="dots") as spinner:
        cmd = ["clang-tidy"]
        cmd.append(path)
        proc = subprocess.Popen(cmd, text=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
        out = ""
        while (c := proc.stdout.read(1)) != "":
            out += c
        proc.wait()

        if proc.returncode == 0:
            spinner.succeed("No findings")
            return None

        spinner.fail("Found errors")
        return out 


async def async_main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=str, help="path to file to check")
    parser.add_argument("--loop", type=int, help="max loop count")
    args = parser.parse_args()

    path = args.path
    findings = await get_findings(path)

    max_attempts = args.loop if args.loop is not None else 1
    attempts = 0
    fix_path = os.path.join(os.path.dirname(path), f".{os.path.basename(path)}")
    shutil.copy(path, fix_path)
    while findings is not None and attempts < max_attempts:
        fix = await get_suggested_fix(fix_path, findings)

        with open(fix_path, "w") as fix_file:
            fix_file.write(fix)

        findings = await get_findings(fix_path)
        attempts += 1

    subprocess.run(["diff", "-u", "--color", path, fix_path])

    if findings is not None:
        print(findings)


def main():
    asyncio.run(async_main())
