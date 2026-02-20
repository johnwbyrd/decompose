# decompose

An agent skill for systematic context decomposition. Inspired by the
[RLM framework](https://github.com/alexzhang13/rlm) from MIT OASYS lab
([paper](https://arxiv.org/abs/2512.24601),
[blog](https://alexzhang13.github.io/blog/2025/rlm/)).

## What This Does

Teaches AI coding agents to systematically decompose large contexts and complex
problems instead of attempting to process everything in a single pass. The
skill provides:

- A context assessment protocol (measure before decomposing)
- Three decomposition primitives (direct, recursive, batched parallel)
- A chunking utility for splitting large files
- A persistent REPL server for stateful computation across shell calls
- Worked examples for common scenarios

## Installation

### Via Skills.sh

```bash
npx skills add johnwbyrd/decompose
```

### Local install (single project)

Copy the skill into your project's `.claude/skills/` directory:

```bash
git clone https://github.com/johnwbyrd/decompose.git
mkdir -p .claude/skills
cp -r decompose/skills/decompose .claude/skills/
```

Compatible agents auto-discover skills at `.claude/skills/*/SKILL.md`. Commit
the directory to version control to share it with your team.

### Global install (all projects)

Copy the skill into your personal skills directory so it's available in
every project:

```bash
git clone https://github.com/johnwbyrd/decompose.git
mkdir -p ~/.claude/skills
cp -r decompose/skills/decompose ~/.claude/skills/
```

## Usage

Invoke explicitly with the `/decompose` slash command, or let it activate
automatically when the agent encounters large-context analysis tasks.
Trigger phrases include:

- "Analyze this large file"
- "Process multiple files"
- "Chunk and analyze"
- "Recursive analysis"
- Any task involving input larger than ~50KB

## Bundled Scripts

### chunk_text.py

Deterministic text chunking:

```bash
python3 .claude/skills/decompose/scripts/chunk_text.py info large_file.txt
python3 .claude/skills/decompose/scripts/chunk_text.py chunk large_file.txt --size 80000
python3 .claude/skills/decompose/scripts/chunk_text.py boundaries source.py
```

### repl_server.py / repl_client.py

Persistent Python REPL over Unix domain socket. Variables, imports, and
function definitions survive across shell calls:

```bash
# Start the server
python3 .claude/skills/decompose/scripts/repl_server.py /tmp/repl.sock &

# Execute code (state persists between calls)
python3 .claude/skills/decompose/scripts/repl_client.py /tmp/repl.sock 'x = 42'
python3 .claude/skills/decompose/scripts/repl_client.py /tmp/repl.sock 'print(x + 1)'

# Inspect variables
python3 .claude/skills/decompose/scripts/repl_client.py /tmp/repl.sock --vars

# Shut down
python3 .claude/skills/decompose/scripts/repl_client.py /tmp/repl.sock --shutdown
```

All scripts are pure Python 3, no external dependencies.

## License

[AGPL-3.0](LICENSE)
