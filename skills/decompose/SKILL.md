---
name: decompose
description: This skill should be used when the user asks to "analyze a large file", "process multiple files", "decompose this problem", "chunk and analyze", "fan out analysis", "recursive analysis", "analyze this codebase", or when the task involves processing context that exceeds what can be reasoned about in a single pass. Also activate when encountering any input larger than ~50KB that requires detailed analysis, or when the user mentions "context decomposition" or "recursive decomposition".
license: AGPL-3.0
metadata:
  version: "0.3.0"
---

# Context Decomposition

Systematic context-first decomposition for large or complex analysis tasks.

The core principle: **assess context properties first, then write a programmatic
decomposition strategy based on what the assessment reveals.** Do not attempt to
process large contexts in a single pass. Do not decompose ad hoc. Measure first,
then choose the right strategy.

## The Persistent REPL: Your Primary Tool

**The persistent REPL is the central mechanism for all decomposition work.**
Do not treat it as optional. Start it first, use it for everything, and keep
it running throughout the session.

The Bash tool is stateless — each invocation starts a fresh shell. The REPL
solves this: variables, imports, and function definitions persist across calls.
This makes it the right tool for:

- **Querying the codebase** — Write short Python programs that grep, find,
  parse, and extract information. This is preferred over using Read, Grep, or
  Glob tools directly, because results stay in REPL variables for later use.
- **Storing discovered context** — Every fact you learn goes into a variable.
  File listings, function signatures, dependency graphs, summaries — all
  stored in the REPL namespace where they accumulate instead of evaporating.
- **Communicating between subagents and parent** — Subagents write results
  into the REPL. The parent reads them out. No context window wasted on
  passing large strings back and forth.
- **Aggregating results** — Fan out subagents, each stores its findings in
  the REPL, then synthesize from the accumulated state.

**When in doubt: use the REPL.**

### Starting the Server

Start the REPL as your **first action** in any decomposition workflow:

```bash
python3 scripts/repl_server.py /tmp/repl.sock &
```

This starts a background Python REPL listening on a Unix domain socket. The
namespace persists across all calls for the lifetime of the session.

### Executing Code

```bash
# Inline code
python3 scripts/repl_client.py /tmp/repl.sock 'x = 42'
python3 scripts/repl_client.py /tmp/repl.sock 'print(x + 1)'

# Pipe code from stdin
echo 'import math; print(math.sqrt(x))' | python3 scripts/repl_client.py /tmp/repl.sock

# Inspect current variables
python3 scripts/repl_client.py /tmp/repl.sock --vars

# Shut down the server (only at end of session)
python3 scripts/repl_client.py /tmp/repl.sock --shutdown
```

### REPL-First Patterns

Instead of using file-reading and search tools, write short programs in the
REPL. The results stay available for the rest of the session.

**Finding files** (instead of Glob):

```bash
python3 scripts/repl_client.py /tmp/repl.sock '
import glob
source_files = glob.glob("/path/to/project/**/*.py", recursive=True)
print(f"Found {len(source_files)} files")
for f in source_files[:10]: print(f)
'
```

**Searching content** (instead of Grep):

```bash
python3 scripts/repl_client.py /tmp/repl.sock '
import re
matches = {}
for f in source_files:
    with open(f) as fh:
        for i, line in enumerate(fh, 1):
            if re.search(r"def process_", line):
                matches.setdefault(f, []).append((i, line.strip()))
print(f"Found matches in {len(matches)} files")
for f, hits in matches.items():
    print(f"\n{f}:")
    for lineno, text in hits: print(f"  {lineno}: {text}")
'
```

**Reading and storing file contents** (instead of Read):

```bash
python3 scripts/repl_client.py /tmp/repl.sock '
file_contents = {}
for f in source_files:
    with open(f) as fh:
        file_contents[f] = fh.read()
total_bytes = sum(len(v) for v in file_contents.values())
print(f"Loaded {len(file_contents)} files, {total_bytes} bytes total")
'
```

**Building and querying a knowledge store**:

```bash
python3 scripts/repl_client.py /tmp/repl.sock '
# Subagent 1 stored its findings:
analysis = {
    "core_modules": ["auth.py", "api.py", "models.py"],
    "entry_points": {"api.py": ["handle_request", "validate_token"]},
    "dependencies": {"auth.py": ["models.py"], "api.py": ["auth.py", "models.py"]},
}
print("Analysis stored for later queries")
'
```

The key insight: every subagent and every step of the workflow should read
from and write to the REPL. Information compounds instead of being lost.

### Variable Naming Convention

When fanning out to subagents, you must establish a naming contract so the
parent context knows exactly which REPL variables to read back:

1. **Before fan-out**, initialize the collection variable in the REPL:
   ```bash
   python3 scripts/repl_client.py /tmp/repl.sock 'results = {}'
   ```

2. **In each subagent prompt**, specify the exact variable and key to write:
   ```
   Task(prompt="...Store your findings in results['handlers'] as a dict...")
   ```

3. **After fan-out**, the parent reads back by name:
   ```bash
   python3 scripts/repl_client.py /tmp/repl.sock '
   for key, value in results.items():
       print(f"\n=== {key} ===")
       print(value)
   '
   ```

Use descriptive key names (`results['auth_module']`, `results['chunk_003']`)
so the parent can selectively read specific results. Always `print()` what
you need — the REPL client returns stdout to the agent's context.

## Context Assessment Protocol

**MANDATORY GATE: You MUST complete the assessment and announce your strategy
to the user BEFORE reading any source files.** Do not read files first and
rationalize a strategy afterward. The assessment controls what you do next.

### Step 1: Start the REPL and measure EVERYTHING

Start the REPL, then use it to identify and measure all files relevant to
the analysis:

```bash
python3 scripts/repl_server.py /tmp/repl.sock &

python3 scripts/repl_client.py /tmp/repl.sock '
import glob, os

# Discover project structure — adapt extensions to the actual project
all_files = []
for ext in ["*.py", "*.toml", "*.md", "*.yml", "*.yaml"]:
    all_files.extend(glob.glob("/path/to/project/**/" + ext, recursive=True))

# Filter out build artifacts
all_files = [f for f in all_files if "/build/" not in f and "/.git/" not in f]

# Measure
file_sizes = {f: os.path.getsize(f) for f in all_files}
total = sum(file_sizes.values())
print(f"Files: {len(all_files)}, Total: {total} bytes ({total/1024:.1f} KB)")
for f, s in sorted(file_sizes.items(), key=lambda x: -x[1])[:15]:
    print(f"  {s:>8} {f}")
'
```

For individual large files, also use the bundled chunking script:

```bash
python3 scripts/chunk_text.py info <file>
```

### Step 2: Choose a strategy from the decision table

| Context Size | Context Type | Strategy |
|:-------------|:-------------|:---------|
| < 50KB | Any | Direct processing. Read into REPL variables. |
| 50KB-200KB | Single file | Chunk into sections, process sequentially or in parallel via subagents. |
| 50KB-200KB | Multi-file | One subagent per file or file group, parallel. All results stored in REPL. |
| 200KB-1MB | Any | Chunk + fan out parallel subagent calls + aggregate via REPL. |
| > 1MB | Any | Two-level: chunk, fan out, aggregate chunk answers in REPL, then synthesize. |

### Step 3: Announce your strategy to the user

**Before reading any files,** output a message to the user stating:

1. Total size measured (bytes or KB)
2. Number of files
3. Strategy chosen from the table
4. How you will partition the work (which subagents, what each covers)

Example:

> Assessment: 47 files, ~145KB total. Strategy: multi-file 50KB-200KB —
> fanning out 4 parallel subagents: (1) core library headers, (2) test
> harness + adapters, (3) test cases, (4) docs + build config. All results
> stored in REPL for aggregation.

Only after announcing the strategy may you proceed to execute it.

### Hard limit: 50KB in main context

**NEVER read more than 50KB of source content directly into the main context.**
If the assessment shows >50KB total, you MUST use subagents for the excess.
Subagents digest files and store results in the REPL; the main context stays
lean for follow-up work.

If you find yourself making a third or fourth round of parallel Read calls,
STOP. You are almost certainly over budget. Switch to subagents that use the
REPL.

### Cumulative tracking

Track cumulative bytes read into the main context. If you notice cumulative
reads approaching 50KB (roughly 15-20 files of typical source code, or
~1500 lines of dense code), do not read further — delegate remaining files
to subagents that store their findings in the REPL.

## Anti-Pattern: The "It'll Probably Fit" Trap

This is the single most common failure mode. It looks like this:

1. You measure the core source at ~30KB. Under threshold — direct processing!
2. You read the source files. Simple, fast, no subagent latency.
3. But the analysis also needs tests... and config... and docs...
4. Each round of reads is "just a few more files."
5. You've now read 120KB into context. The analysis is done, but the context
   window is exhausted. The user asks a follow-up question and you hit
   compression, losing nuance from the very files you just read.

**The cost of subagents is latency. The cost of context exhaustion is the
entire rest of the session.** When in doubt, use subagents writing to the
REPL. You are optimizing for session durability, not single-response speed.

## Three Decomposition Primitives

### 1. Direct Query

For simple, one-shot tasks: extracting a fact from a chunk, summarizing a
section, classifying content. The subagent's return value is used directly —
no REPL needed for simple cases.

```
Task(subagent_type="Explore", prompt="Summarize the key functions in this file: <chunk>")
```

Fast, lightweight, no iteration. Use the return value in the parent context.

### 2. Recursive Query

For sub-problems requiring multi-step reasoning, code execution, or their own
iterative problem-solving. The subagent uses the shared REPL to store results
that outlive the subagent itself.

**Parent initializes**, then launches the subagent:
```bash
python3 scripts/repl_client.py /tmp/repl.sock 'auth_analysis = {}'
```
```
Task(subagent_type="general-purpose",
     prompt="Use the REPL at /tmp/repl.sock. Read and analyze these modules.
     Store your findings in auth_analysis['functions'] (list of signatures),
     auth_analysis['dependencies'] (dict of imports), and
     auth_analysis['issues'] (list of concerns).
     Files: <file list>")
```

**Parent reads back** after the subagent completes:
```bash
python3 scripts/repl_client.py /tmp/repl.sock '
print("Functions:", auth_analysis.get("functions", []))
print("Issues:", auth_analysis.get("issues", []))
'
```

### 3. Batched Parallel Query

For independent sub-tasks that can run concurrently. Issue multiple Task tool
calls in a single response message. They run in parallel.

**Parent initializes the collection variable first:**
```bash
python3 scripts/repl_client.py /tmp/repl.sock 'results = {}'
```

**Then issues all subagent calls in a single message:**
```
Task(prompt="Use REPL at /tmp/repl.sock. Analyze chunk 1, store findings in results['chunk_1'] as a dict with keys 'summary' and 'issues': <chunk1>")
Task(prompt="Use REPL at /tmp/repl.sock. Analyze chunk 2, store findings in results['chunk_2'] as a dict with keys 'summary' and 'issues': <chunk2>")
Task(prompt="Use REPL at /tmp/repl.sock. Analyze chunk 3, store findings in results['chunk_3'] as a dict with keys 'summary' and 'issues': <chunk3>")
```

**Parent reads accumulated results:**
```bash
python3 scripts/repl_client.py /tmp/repl.sock '
print(f"Collected results from {len(results)} chunks")
all_issues = []
for chunk_id, data in sorted(results.items()):
    print(f"\n{chunk_id}: {data[\"summary\"]}")
    all_issues.extend(data.get("issues", []))
print(f"\nTotal issues found: {len(all_issues)}")
'
```

Each subagent writes to its own key; the parent reads the full dict afterward.

## The Decomposition Workflow

Follow these steps in order:

1. **Start REPL** — `python3 scripts/repl_server.py /tmp/repl.sock &`
   This is always the first step. No exceptions.

2. **Assess** — Use the REPL to measure total context size across ALL files
   you intend to read. Store the file list and sizes in REPL variables.

3. **Announce** — State your strategy to the user: total size, file count,
   strategy from the table, partition plan. **Do not read any files before
   this step.**

4. **Chunk** (if needed) — Use `scripts/chunk_text.py chunk <file> --size <chars>`
   for text files. For structured files (code, markdown), prefer natural boundaries:
   functions, classes, sections, chapters. Use `scripts/chunk_text.py boundaries <file>`
   to detect these.

5. **Fan Out** — Issue parallel Task calls, one per chunk or file group. Each
   subagent uses the shared REPL to store its findings. Keep prompts identical
   except for the data and the variable name to write to.

6. **Collect** — Read accumulated results from the REPL. All subagent findings
   are already there in named variables.

7. **Aggregate** — Synthesize results in the REPL. For large result sets, this
   step may itself require a Task call to summarize.

8. **Iterate** — If the aggregated answer reveals gaps or contradictions, target
   those specific chunks for deeper analysis. The REPL still holds all prior
   findings, so you build on what you have instead of starting over.

For detailed worked examples of this workflow, read `references/decomposition-patterns.md`.

## Chunking Helper Script

The `scripts/chunk_text.py` utility provides deterministic chunking without
reimplementing the logic each time.

**Subcommands:**

- `info <file>` — Print JSON with file size, line count, char count, estimated
  tokens (chars/4), and suggested chunk count for a 100K-char target.

- `chunk <file> --size <chars> --overlap <chars>` — Split file into chunks.
  Default size: 100,000 chars. Default overlap: 500 chars. Breaks at natural
  boundaries (newlines, paragraph breaks) when possible. Outputs JSON array
  to stdout.

- `boundaries <file>` — Detect natural boundaries (markdown headers, Python
  `def`/`class`, blank line sequences). Outputs JSON array of boundary locations.

**Example:**

```bash
python3 scripts/chunk_text.py info large_log.txt
python3 scripts/chunk_text.py chunk large_log.txt --size 80000 --overlap 200
```

## When NOT to Decompose

- **Small contexts (< 50KB total, including ALL files you will read)** —
  Direct processing is faster and preserves coherence. Decomposition adds
  latency and loses cross-section context for no benefit. But be honest about
  the total — if you're reading source AND tests AND docs, sum all of them.
  Even for small contexts, prefer loading content into the REPL so it persists.

- **Tasks requiring global understanding** — "What is the overall theme?" or
  "What is the architectural philosophy?" Chunk-level answers lose the forest
  for the trees. Instead: summarize the full context first (possibly in chunks),
  then analyze the summary as a whole.

- **Time-sensitive requests** — When the user needs a quick answer, sequential
  processing of a manageable context beats the overhead of decomposition.

## Additional Resources

### Reference Files

- **`references/decomposition-patterns.md`** — Five detailed worked examples:
  large log analysis, multi-file codebase review, long document Q&A, dataset
  comparison, and multi-step codebase reasoning.

- **`references/mapping-table.md`** — Decomposition primitive to tool mapping
  with edge cases and fallback patterns.

- **`references/rlm-system-prompt.md`** — Annotated reference for the theoretical
  foundation of context-first decomposition.
