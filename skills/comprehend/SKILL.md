---
name: comprehend
description: A methodology for working effectively in unfamiliar codebases. Use this skill whenever you need to fix a bug, add a feature, refactor, or make any non-trivial change in code you haven't seen before. It prevents the most common failure mode — diving into edits before understanding the code — by enforcing a measure-first workflow with persistent state and parallel readers.
license: AGPL-3.0
metadata:
  version: "0.6.0"
---

# Comprehend

You are working in an unfamiliar codebase. Before you touch anything,
understand what you're dealing with.

Break the problem into pieces. Use a persistent REPL to store everything
you learn. Fan out subagents to do the reading. Keep your own context window
small and available for the actual work — edits, debugging, reasoning.

That is the entire method. What follows is how to do it.

## When to Use This

Use this workflow whenever you are making changes in code you don't already
understand. This includes:

- Fixing a bug in a repository you haven't seen before
- Adding a feature that touches multiple files or modules
- Refactoring code whose structure you need to map out first
- Any task where you'd otherwise spend your first several turns just reading

The default instinct is to start reading files immediately and jump to a fix.
That works for trivial changes. For anything else, it leads to patches that
miss edge cases, break related code, or over-engineer because you didn't
see the simpler path. Measure first.

**Skip this workflow only when** the change is truly trivial — a one-line
typo fix, a config value change, something where understanding the
surrounding code is unnecessary.

## Prerequisites

This skill requires **python** and **nohup**. Before doing anything else,
verify they are available:

```bash
python --version && nohup --version > /dev/null 2>&1 && echo "ok"
```

If this does not print `ok`, **stop here**. Tell the user which command
is missing. On Windows, both are available in Git Bash. On macOS and
Linux, both are standard.

## Script Paths

This skill bundles scripts in its `scripts/` directory. Before using them,
resolve the absolute path based on where you loaded this SKILL.md from.
For example, if you loaded this file from
`/home/user/project/skills/comprehend/SKILL.md`, then the scripts
are at `/home/user/project/skills/comprehend/scripts/`.

Throughout this document, `SCRIPTS` refers to that resolved path. In all
bash commands, substitute the actual absolute path.

## The REPL

Every session starts by generating a unique address and launching the server:

```bash
# Generate a session-unique address (prevents collisions between
# simultaneous sessions on the same machine)
REPL_ADDR=$(python SCRIPTS/repl_server.py --make-addr)
nohup python SCRIPTS/repl_server.py "$REPL_ADDR" > /dev/null 2>&1 &
```

The server must outlive the shell that starts it. Use `nohup` and shell
backgrounding (`&`) as shown above. Do **not** use the Bash tool's
`run_in_background` parameter — it may kill the server when the task
"completes." On Windows, the server automatically uses TCP on localhost
instead of Unix sockets. No code changes needed — the interface is
identical.

Throughout this document, `REPL_ADDR` refers to the session-unique
address returned by `--make-addr`. In all bash commands, substitute the
actual path. **Each session must use its own address.**

This launches a persistent Python REPL. Variables, imports, and definitions
survive across calls — not just during comprehension, but for the entire
session. The REPL is your memory: use it instead of reading files into
your context window.

**This is the key tradeoff.** The upfront cost is a few extra turns to
launch the server and measure the codebase. The payoff: you build a
queryable knowledge base that persists for the entire session. When you
need to check something later — while debugging, while writing tests,
while responding to follow-up questions — you query the REPL instead of
re-reading source files. Every lookup costs one small Bash call instead
of consuming context window.

**Always use a heredoc to send code to the REPL.** Never pass code as a
positional command-line argument — it will break on quotes, braces, or
multi-line input. The only exceptions are `--vars`, `--shutdown`, and
`--file`.

```bash
# Run code (state persists between calls)
python SCRIPTS/repl_client.py REPL_ADDR <<'PYEOF'
greeting_message = "hello"
PYEOF

python SCRIPTS/repl_client.py REPL_ADDR <<'PYEOF'
print(greeting_message)
PYEOF

# See all stored variables
python SCRIPTS/repl_client.py REPL_ADDR --vars
```

The quoted delimiter (`<<'PYEOF'`) passes all characters through to
Python unchanged — single quotes, double quotes, backslashes, parentheses,
braces, everything.

**Large results:** Heredocs can break on very large blocks of code
(100+ lines). When storing large data in `_comprehend_results`, use the
Write tool to write the Python code to a temporary file, then use
`--file`:

```bash
# First: use the Write tool to create /tmp/comprehend_data.py
# with the Python code (assignments, dict literals, etc.)
# Then:
python SCRIPTS/repl_client.py REPL_ADDR --file /tmp/comprehend_data.py
```

This bypasses shell quoting entirely. The Write tool writes the file
directly, and `--file` reads it directly. Use this for any REPL code
that is too large for a heredoc.

**Windows paths in heredocs:** Always use forward slashes in Python code
inside heredocs (`"C:/Users/..."` not `"C:\\Users\\..."`). Python accepts
forward slashes on all platforms. This avoids backslash-as-line-continuation
confusion.

**CRITICAL: AFTER STARTING THE REPL SERVER, YOU MUST NOT USE ANY OTHER TOOLS FOR FILE OPERATIONS.**

The following actions are **FORBIDDEN** once the REPL is running:
- Using `cat`, `head`, `tail`, `grep`, `find`, `wc`, `ls` or any shell command to read files
- Using Read_file tool to read source files directly into your context
- Using Glob tool to enumerate files
- Using Grep tool to search file contents
- Any operation that brings file content into your context window

If you catch yourself about to use a shell command or file tool to access file content, **STOP**. Use the REPL client instead.

**Use the REPL for everything!** Finding files, searching content, reading
source, storing results — all of it. Every fact you discover goes into a
variable where it accumulates instead of evaporating.

```bash
python SCRIPTS/repl_client.py REPL_ADDR <<'PYEOF'
import glob, os, re

# Find files (instead of Glob tool)
project_source_files = glob.glob("/path/to/project/**/*.py", recursive=True)
project_source_files = [f for f in project_source_files if "/.git/" not in f.replace("\\", "/")]

# Measure them (instead of wc)
file_size_by_path = {f: os.path.getsize(f) for f in project_source_files}
total_source_bytes = sum(file_size_by_path.values())

# Search content (instead of Grep tool)
function_definition_matches = {}
for filepath in project_source_files:
    with open(filepath) as fh:
        for line_number, line_text in enumerate(fh, 1):
            if re.search(r"def process_", line_text):
                function_definition_matches.setdefault(filepath, []).append(
                    (line_number, line_text.strip()))

# Everything persists: project_source_files, file_size_by_path,
# total_source_bytes, function_definition_matches
print(f"{len(project_source_files)} files, {total_source_bytes/1024:.0f} KB, "
      f"{len(function_definition_matches)} files with matches")
PYEOF
```

## The Results Dict

All subagent findings go into one well-known dict: **`_comprehend_results`**.

The REPL server initializes this dict automatically on startup. Do not
re-initialize it — that would wipe results from other subagents. Just
write to it:

```bash
python SCRIPTS/repl_client.py REPL_ADDR <<'PYEOF'
_comprehend_results["auth_module_analysis"] = {"functions": [...], "issues": [...]}
PYEOF
```

**The parent assigns every subagent a unique key** before launching it.
Subagents must never choose their own keys — the parent is the only one
that sees all keys in use and can guarantee uniqueness. A subagent writes
only to its assigned key; it never reads or writes other subagents' keys.

Keys should be descriptive: `'auth_module_function_signatures'`, not
`'chunk1'`. For deeper nesting, use sub-keys within the assigned key:

```bash
python SCRIPTS/repl_client.py REPL_ADDR <<'PYEOF'
_comprehend_results["auth_module"] = {
    "function_signatures": [...],
    "import_map": {...},
    "issues": [...]
}
PYEOF
```

The parent reads from `_comprehend_results[key]`. The underscore prefix
and specific name avoid collisions with user or project variables.

## The Workflow

### 1. Measure

Before reading any files, measure everything relevant to your task. Use the
REPL (as above) or the bundled script:

```bash
python SCRIPTS/chunk_text.py info <file>
```

Measure broadly — source, tests, docs, config. The most common failure
is measuring only the core source, classifying it as small, then also
reading tests and docs and blowing past the limit.

### 2. Choose a strategy

| Total Size | Strategy |
|:-----------|:---------|
| < 50KB | Read directly into REPL variables. No subagents needed. |
| 50KB–200KB | Fan out subagents — one per file or file group, parallel. |
| 200KB–1MB | Chunk + fan out + aggregate in REPL. |
| > 1MB | Two-level: chunk, fan out, aggregate chunks, synthesize. |

### 3. Plan

Based on what you measured, decide what to read and in what order. For a
bug fix, focus on the files in the stack trace plus their immediate
dependencies. For a feature, map the module boundaries first. State your
plan before reading anything.

### 4. Execute

Fan out subagents. Each writes to `_comprehend_results[key]`. You read the
results back. Details are in the Fan-Out Patterns section below.

### 5. Iterate

If the aggregated answer has gaps, target those specific areas for deeper
analysis. The REPL still holds everything from the first pass.

### 6. Make Your Changes

Now that you understand the code, make your edits. The REPL remains
available — query `_comprehend_results` whenever you need to check
something instead of re-reading source files. This keeps your context
window small and available for reasoning about the actual changes.

```bash
python SCRIPTS/repl_client.py REPL_ADDR <<'PYEOF'
# Check a detail without re-reading source
print(_comprehend_results["core_library"]["function_signatures"])
PYEOF
```

### 7. Shut down the REPL

When your task is complete, shut down the REPL:

```bash
python SCRIPTS/repl_client.py REPL_ADDR --shutdown
```

The `nohup` server runs until explicitly stopped. Shut it down when
done to avoid leaving an orphan process.

### The 50KB Rule

**Never read more than 50KB of source into your main context window.**
Everything above that limit must go through subagents that write findings
to the REPL. The cost of a subagent is latency. The cost of context
exhaustion is the entire rest of the session.

Watch for the trap: you measure 30KB of core source (under threshold!),
then also read tests, config, and docs — now you're at 120KB and your
context window is shot. Measure the total. All of it.

## Fan-Out Patterns

All patterns follow the same contract:

1. Parent starts the REPL server (once per session). `_comprehend_results`
   is auto-initialized. **Never re-initialize it.**
2. **Parent assigns a unique key** to each subagent in the prompt.
   Subagents never pick their own keys.
3. Subagent writes findings only to its assigned
   `_comprehend_results[key]`. It may create sub-keys within that key
   freely, but must not touch any other top-level key.
4. **Subagent reports back** the key it wrote and a summary of what's in it.
5. Parent reads `_comprehend_results[key]` from the REPL.

Step 4 is critical. The Task tool returns a text message to the parent —
that message is the *only* way the parent learns what the subagent stored.
Every subagent prompt must end with an instruction to report what was written.

### Direct Query

For simple one-shot tasks (summarize, classify, extract a fact). The
subagent's return value is used directly — no REPL variable needed.

```
Task(subagent_type="Explore",
     prompt="Summarize the key functions in this file: <chunk>")
```

### Recursive Query

For sub-problems needing multi-step reasoning or tool access. The subagent
stores results in `_comprehend_results` under a descriptive key.

**Parent launches subagent:**
```
Task(subagent_type="general-purpose",
     prompt="Use the REPL at REPL_ADDR. Read and analyze these modules.
     Store your findings in _comprehend_results['auth_module_analysis'] as a
     dict with keys:
       'function_signatures' — list of all public function signatures
       'import_dependency_map' — dict mapping each file to its imports
       'identified_concerns' — list of architectural or correctness issues

     Files: src/auth.py, src/models.py, src/tokens.py

     When done, reply with: the key you wrote to in _comprehend_results,
     what sub-keys you stored, and a one-line summary of each.")
```

**Parent receives** a message like: "Wrote to
`_comprehend_results['auth_module_analysis']` with keys:
'function_signatures' (12 public functions), 'import_dependency_map' (3 files
mapped), 'identified_concerns' (2 issues: circular import between auth.py and
models.py, unused import in tokens.py)."

**Parent reads back:**
```bash
python SCRIPTS/repl_client.py REPL_ADDR <<'PYEOF'
auth_data = _comprehend_results["auth_module_analysis"]
print("Functions:", auth_data["function_signatures"])
print("Concerns:", auth_data["identified_concerns"])
PYEOF
```

### Batched Parallel Query

For independent chunks that can run concurrently. Issue all Task calls in
a single message.

**Parent launches all subagents at once:**
```
Task(prompt="Use REPL at REPL_ADDR. Analyze this log segment for errors.
     Store in _comprehend_results['log_segment_hours_00_to_06'] as a dict with
     keys 'error_summary' and 'critical_error_list'.
     Segment: <chunk1>

     When done, reply with: the _comprehend_results key you wrote,
     how many errors found, and one sentence summarizing the most severe.")

Task(prompt="Use REPL at REPL_ADDR. Analyze this log segment for errors.
     Store in _comprehend_results['log_segment_hours_06_to_12'] as a dict with
     keys 'error_summary' and 'critical_error_list'.
     Segment: <chunk2>

     When done, reply with: the _comprehend_results key you wrote,
     how many errors found, and one sentence summarizing the most severe.")

Task(prompt="Use REPL at REPL_ADDR. Analyze this log segment for errors.
     Store in _comprehend_results['log_segment_hours_12_to_18'] as a dict with
     keys 'error_summary' and 'critical_error_list'.
     Segment: <chunk3>

     When done, reply with: the _comprehend_results key you wrote,
     how many errors found, and one sentence summarizing the most severe.")
```

**Parent receives** three messages confirming what each wrote.

**Parent reads accumulated results:**
```bash
python SCRIPTS/repl_client.py REPL_ADDR <<'PYEOF'
for segment_key, segment_data in sorted(_comprehend_results.items()):
    if segment_key.startswith("log_segment_"):
        print(f"{segment_key}: {segment_data['error_summary']}")
        for critical_error in segment_data.get('critical_error_list', []):
            print(f"  - {critical_error}")
PYEOF
```

## Chunking

For large single files, use the bundled script to split at natural boundaries:

```bash
python SCRIPTS/chunk_text.py info large_file.txt      # measure
python SCRIPTS/chunk_text.py boundaries source.py      # find split points
python SCRIPTS/chunk_text.py chunk large_file.txt --size 80000 --overlap 200  # split
```

For structured files (code, markdown), prefer splitting at functions, classes,
or section headers rather than arbitrary character boundaries.

## References

- `references/comprehension-patterns.md` — Five worked examples.
- `references/mapping-table.md` — RLM primitive to agent tool mapping.
- `references/rlm-system-prompt.md` — Theoretical foundation.
