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
    return response.output_text


async def get_findings(path: str, args: list[str]) -> str | None:
    cmd = ["clang-tidy", *args]
    cmd.append(path)
    proc = subprocess.Popen(
        cmd, text=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE
    )
    out = ""
    while (c := proc.stdout.read(1)) != "":
        out += c
    proc.wait()

    if proc.returncode == 0:
        return None

    return out


async def async_main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=str, help="path to file to check")
    parser.add_argument("--max-iters", "-N", type=int, help="max loop count")
    parser.add_argument(
        "-i", "--in-place", action="store_true", help="apply final fixes in place"
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="when used with --in-place, apply changes even if errors remain",
    )
    parser.add_argument("passthrough", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    print(args)

    path = args.path
    with Halo(text="Analyzing code", spinner="dots") as spinner:
        findings = await get_findings(path, args.passthrough)
        if findings is None:
            spinner.succeed("No findings")
        else:
            spinner.fail("Found errors")

    max_attempts = args.max_iters if args.max_iters is not None else 1
    attempts = 0
    fix_path = os.path.join(os.path.dirname(path), f".{os.path.basename(path)}")
    shutil.copy(path, fix_path)
    while findings is not None and attempts < max_attempts:
        with Halo(text="Getting agent suggestion", spinner="dots") as spinner:
            fix = await get_suggested_fix(fix_path, findings)
            spinner.succeed()

        with open(fix_path, "w") as fix_file:
            fix_file.write(fix)

        with Halo(text="Analyzing code", spinner="dots") as spinner:
            findings = await get_findings(fix_path, args.passthrough)
            if findings is None:
                spinner.succeed("No findings")
            else:
                spinner.fail("Found errors")
        attempts += 1

    subprocess.run(["diff", "-u", "--color", path, fix_path])

    if findings is not None:
        print(findings)

    if args.in_place and (findings is None or agrs.force):
        shutil.move(fix_path, path)
        print(f"Applied fixes to {path}")


def main():
    asyncio.run(async_main())
