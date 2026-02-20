---
name: decomposition
description: This skill should be used when the user asks to "analyze a large file", "process multiple files", "decompose this problem", "chunk and analyze", "fan out analysis", "recursive analysis", "analyze this codebase", or when the task involves processing context that exceeds what can be reasoned about in a single pass. Also activate when encountering any input larger than ~50KB that requires detailed analysis, or when the user mentions "context decomposition" or "recursive decomposition".
version: 0.1.1
---

# Context Decomposition

Systematic context-first decomposition for large or complex analysis tasks.

The core principle: **assess context properties first, then write a programmatic
decomposition strategy based on what the assessment reveals.** Do not attempt to
process large contexts in a single pass. Do not decompose ad hoc. Measure first,
then choose the right strategy.

## Context Assessment Protocol

Before decomposing any large input, run an assessment. Use the bundled script
or standard tools:

```bash
python3 scripts/chunk_text.py info <file>
```

This returns size, line count, character count, estimated tokens, and suggested
chunk count. For multiple files, run `wc -c` or `ls -la` across the set.

Based on the assessment, choose a strategy:

| Context Size | Context Type | Strategy |
|:-------------|:-------------|:---------|
| < 50KB | Any | Direct processing. No decomposition needed. |
| 50KB-200KB | Single file | Chunk into sections, process sequentially or in parallel. |
| 50KB-200KB | Multi-file | One subagent per file, parallel. |
| 200KB-1MB | Any | Chunk + fan out parallel subagent calls + aggregate. |
| > 1MB | Any | Two-level: chunk, fan out, aggregate chunk answers, then synthesize. |

Do not skip the assessment. The strategy depends on what the measurement reveals.

## Three Decomposition Primitives

### 1. Direct Query

For simple, one-shot tasks: extracting a fact from a chunk, summarizing a section,
classifying content. Use a Task tool call with a focused prompt and constrained scope.

```
Task(subagent_type="Explore", prompt="Summarize the key functions in this file: <chunk>")
```

Fast, lightweight, no iteration.

### 2. Recursive Query

For sub-problems requiring multi-step reasoning, code execution, or their own
iterative problem-solving. Use a Task tool call where the subagent may itself
need to read files, run code, or further decompose.

```
Task(subagent_type="general-purpose", prompt="Trace the data flow from input to output across these modules: <context>")
```

The subagent gets its own tools and can iterate — including spawning its own subagents.

### 3. Batched Parallel Query

For independent sub-tasks that can run concurrently. Issue multiple Task tool
calls in a single response message. Claude Code processes them in parallel.

```
# In a single message, issue all of these simultaneously:
Task(prompt="Analyze chunk 1: <chunk1>")
Task(prompt="Analyze chunk 2: <chunk2>")
Task(prompt="Analyze chunk 3: <chunk3>")
```

Use this for fan-out over chunks or files.

## The Decomposition Workflow

Follow these steps in order:

1. **Assess** — Measure context size, type, and structure using `scripts/chunk_text.py info`
   or standard tools (`wc`, `ls`, `Read` with line limits).

2. **Plan** — Consult the decision table above. Choose a decomposition strategy.
   State the strategy explicitly before proceeding.

3. **Chunk** (if needed) — Use `scripts/chunk_text.py chunk <file> --size <chars>`
   for text files. For structured files (code, markdown), prefer natural boundaries:
   functions, classes, sections, chapters. Use `scripts/chunk_text.py boundaries <file>`
   to detect these.

4. **Fan Out** — Issue parallel Task calls, one per chunk, with a consistent prompt
   template plus chunk-specific context. Keep prompts identical except for the data.

5. **Collect** — Gather all subagent responses. Each returns a focused answer about
   its chunk.

6. **Aggregate** — Synthesize chunk-level answers into a coherent final answer.
   For large result sets, this step may itself require a Task call to summarize.

7. **Iterate** — If the aggregated answer reveals gaps or contradictions, target
   those specific chunks for deeper analysis. Do not re-process everything.

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

- **Small contexts (< 50KB)** — Direct processing is faster and preserves coherence.
  Decomposition adds latency and loses cross-section context for no benefit.

- **Tasks requiring global understanding** — "What is the overall theme?" or
  "What is the architectural philosophy?" Chunk-level answers lose the forest
  for the trees. Instead: summarize the full context first (possibly in chunks),
  then analyze the summary as a whole.

- **Time-sensitive requests** — When the user needs a quick answer, sequential
  processing of a manageable context beats the overhead of decomposition.

## Persistent REPL

Claude Code's Bash tool is stateless — each invocation starts a fresh shell. For
decomposition workflows that need to accumulate state across steps (variables,
imported modules, intermediate results), use the persistent REPL server.

### Starting the Server

```bash
python3 scripts/repl_server.py /tmp/repl.sock &
```

This starts a background Python REPL that listens on a Unix domain socket. The
REPL namespace persists across calls — variables, imports, and function definitions
all survive between invocations.

### Executing Code

```bash
# Inline code
python3 scripts/repl_client.py /tmp/repl.sock 'x = 42'
python3 scripts/repl_client.py /tmp/repl.sock 'print(x + 1)'

# Pipe code from stdin
echo 'import math; print(math.sqrt(x))' | python3 scripts/repl_client.py /tmp/repl.sock

# Inspect current variables
python3 scripts/repl_client.py /tmp/repl.sock --vars

# Shut down the server
python3 scripts/repl_client.py /tmp/repl.sock --shutdown
```

### Use Cases

- **Accumulating results**: Fan out subagents, store each result in a dict, then
  aggregate in a final step — all in the same namespace.
- **Iterative computation**: Build up a data structure across multiple Bash calls
  without serialization overhead.
- **Stateful analysis**: Import a library once, load data once, run multiple
  analyses against it.

## Additional Resources

### Reference Files

- **`references/decomposition-patterns.md`** — Five detailed worked examples:
  large log analysis, multi-file codebase review, long document Q&A, dataset
  comparison, and multi-step codebase reasoning.

- **`references/mapping-table.md`** — Decomposition primitive to Claude Code tool
  mapping with edge cases and fallback patterns.

- **`references/rlm-system-prompt.md`** — Annotated reference for the theoretical
  foundation of context-first decomposition.
