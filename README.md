# Dev Tools

Because I couldn't think of a better name.

## Features

- **Run auto mode with confidence**
  - Built-in filesystem tools can't run arbitrary code and executables
  - Filesystem tools default to read-only in the working directory with an optional whitelist of writable paths
  - Enabling write mode allows all writes and deletes in the working directory with an optional blacklist of read-only paths
  - *No Bash tool. Define custom tools when you need more than basic filesystem operations.*
- **Maximum flexibility**
  - Define custom tools in an `.agent-tools.json` file (always read-only) in the working directory
  - Custom tools can call any program with (shell-escaped) args populated from agent inputs
  - Need an extra layer of security? Define your custom tool as a bubblewrap `bwrap` call or define tools to provision and execute within a container.
- **Multiple backends**&mdash;Use the same frontend for OpenAI and Anthropic endpoints
- **Structured output**&mdash;Define a structured output format using JSON Schema


## Installation

> Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager

```shell
uv tool install --editable .
```

## Usage

See the full set of CLI options with `run_agent -h`.

### Read-Only Mode

The agent defaults to read-only mode.
The current directory is readable and no filesystem write tools are provided to the model.

```shell
run_agent \
  --model openai/gpt-5.6-luna \
  --instructions "You are a coding agent." \
  --prompt "Explain this codebase in 3-5 bullets"
```

When in read-only mode, whitelist paths or files with one or more `--allow-write` arguments to allow restricted writes.

```shell
run_agent \
  --model openai/gpt-5.6-luna \
  --instructions "You are a coding agent." \
  --prompt "Generate installation instructions in docs/INSTALL.md" \
  --allow-write docs
```

> [!note]
> Writes outside the working directory cannot be whitelisted and are *always* blocked.

### Write Mode

Add the `--write` option to invert the filesystem policy&mdash;the entire working directory becomes writable, and specific paths and files can be blocked with one or more `--read-only` arguments.

```shell
run_agent \
  --model openai/gpt-5.6-luna \
  --instructions "You are a coding agent." \
  --prompt "Generate installation instructions in docs/INSTALL.md" \
  --write \
  --read-only src
```

> [!note]
> `.agent-tools.json` in the working directory is always read-only
> to prevent the agent from creating tools as a backdoor to disallowed actions in future turns.

### Piped Prompts

Use the `--stdin` option to append `stdin` to any other supplied prompt:

```shell
clang-tidy -p build src/main.cpp | run_agent \
  --model openai/gpt-5.6-luna \
  --instructions "You are a coding agent." \
  --prompt "Fix these clang-tidy findings: " \
  --allow-write src
```

### Structured Output

Use a [JSON Schema](https://json-schema.org/docs) to request structured output:

```shell
clang-tidy -p build src/main.cpp | run_agent \
  --model anthropic/claude-haiku-4-5-20251001 \
  --instructions "You are a coding agent." \
  --prompt "Fix these clang-tidy findings. Report the number of successful fixes. List findings you couldn't or didn't attempt to fix and why." \
  --allow-write src \
  --json-schema '{"type":"object","properties":{"fixCount":{"type":"number"},"skipped":{"type":"array","items":{"type":"object","properties":{"finding":{"type":"string"},"reason":{"type":"string"}},"additionalProperties":false,"required":["finding","reason"]}}},"additionalProperties":false,"required":["fixCount","skipped"]}'\
```

## Custom Agent Tools

Define custom agent tools in `.agent-tools.json` in the working directory:

```json
[
  {
    "program": "cmake",
    "args": [
      "-S",
      ".",
      "--preset={preset}"
    ],
    "schema": {
      "name": "cmake_configure_preset",
      "description": "Configure the CMake project for a preset.",
      "parameters": {
        "type": "object",
        "properties": {
          "preset": {
            "type": "string",
            "description": "The CMake preset to configure."
          }
        },
        "additionalProperties": false,
        "required": ["preset"]
      }
    }
  }
]
```

Tools default to disabled. Enable individual tools with `--allow`. Enable all tools with `--allow-all`.

## Backends

Select OpenAI or Anthropic endpoints by changing the model string prefix: `<backend>/<model identifier>`.

### OpenAI

Enable the OpenAI backend with a model string like `openai/<model identifier>`. Set `OPENAI_API_KEY` with your API key and use `OPENAI_BASE_URL` to specify a custom endpoint.

### Anthropic

Enable the Anthropic backend with a model string like `anthropic/<model identifier>`. Set `ANTHROPIC_API_KEY` with your API key and use `ANTHROPIC_BASE_URL` to specify a custom endpoint.

## Roadmap

- [ ] Persistent session history for recovery
- [ ] Built-in Git tools governed by the read/write policy 
- [ ] More variable expansions in tool definition `args`
