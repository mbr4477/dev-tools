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

```shell
uv tool install --editable .
```

## Usage

- TODO

## Backends

### OpenAI

- TODO

### Anthropic

- TODO

## Roadmap

- [ ] Persistent session history for recovery
- [ ] Built-in Git tools governed by the read/write policy 
- [ ] More variable expansions in tool definition `args`
