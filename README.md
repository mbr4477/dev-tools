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

When in read-only mode, specify paths or files can be whitelisted with one or more `--allow-write` arguments to allow restricted writes.

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

Add the `--write` to invert the filesystem policy&mdash;the entire working directory becomes writable, and specific paths and files can be blocked with one or more `--read-only` arguments.

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

```
clang-tidy -p build src/main.cpp | run_agent \
  --model openai/gpt-5.6-luna \
  --instructions "You are a coding agent." \
  --prompt "Fix these clang-tidy findings: " \
  --allow-write src
```

### Structured Output

- TODO

## Custom Agent Tools

- TODO

## Backends

Use OpenAI and Anthropic model endpoints to the `--model` argument using `<backend>/<model identifier>`.

### OpenAI

Enable the OpenAI backend with a model string like `openai/<model identifier>`. Set `OPENAI_API_KEY` with your API key and use `OPENAI_BASE_URL` to configure a custom endpoint.

### Anthropic

Enable the Anthropic backend with a model string like `anthropic/<model identifier>`. Set `ANTHROPIC_API_KEY` with your API key and use `ANTHROPIC_BASE_URL` to configure a custom endpoint.

## Roadmap

- [ ] Persistent session history for recovery
- [ ] Built-in Git tools governed by the read/write policy 
- [ ] More variable expansions in tool definition `args`
