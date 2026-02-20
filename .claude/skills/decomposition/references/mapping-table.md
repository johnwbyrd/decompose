# RLM Primitive → Claude Code Tool Mapping

Complete mapping from the RLM framework's primitives to Claude Code's native tools.

## Core Primitives

| RLM Primitive | Claude Code Equivalent | Notes |
|:---|:---|:---|
| `context` variable | Files on disk via `Read` tool | RLM loads context into a Python variable. In Claude Code, context lives in files. Use `Read` to examine, `Bash` with `wc` to measure. |
| `len(context)` | `wc -c <file>` or `scripts/chunk_text.py info` | Always measure before choosing a strategy. |
| `context[:10000]` | `Read <file> --offset 1 --limit N` | Read a slice of the file. Use line offsets to grab specific sections. |
| `llm_query(prompt)` | `Task` tool (lightweight subagent) | Use `subagent_type="Explore"` or `model="haiku"` for fast one-shot work. No iteration, no tool access needed. |
| `rlm_query(prompt)` | `Task` tool (general-purpose subagent) | Use `subagent_type="general-purpose"` when the sub-problem needs its own multi-step reasoning, file access, or code execution. |
| `llm_query_batched(prompts)` | Multiple `Task` calls in a single message | Issue N independent Task calls simultaneously. Claude Code runs them in parallel. |
| `rlm_query_batched(prompts)` | Multiple `Task` calls (general-purpose) in a single message | Same as above but each subagent gets full tool access for deeper reasoning. |
| `print()` for debugging | Direct text output to user | Claude Code's responses are visible to the user. No special mechanism needed. |
| `SHOW_VARS()` | N/A | No REPL namespace in Claude Code. State lives in files or in the conversation context. |
| `FINAL_VAR(answer)` / `FINAL(answer)` | Final response to user | Simply present the synthesized answer. No special directive needed. |
| Python computation in REPL | `Bash` tool running Python | `python3 -c "import math; print(math.sin(1.5))"` or run a script. |
| `import` in REPL | `Bash` tool with pip/python | Claude Code can install and use any Python package via Bash. |

## Decomposition Patterns

| RLM Pattern | Claude Code Pattern |
|:---|:---|
| `for chunk in chunks: answer = llm_query(...)` | Sequential Task calls, one per chunk. Use when order matters or each chunk depends on prior results. |
| `answers = llm_query_batched(prompts)` | Multiple Task calls in one message. Use when chunks are independent. |
| `if "X" in result: rlm_query(...)` | Inspect subagent result, then conditionally launch another Task. Branching on results is natural in Claude Code's agentic loop. |
| Nested `rlm_query` inside `rlm_query` | Task subagent that itself launches Task calls. Supported natively — subagents can spawn their own subagents. |
| `context` as `List[str]` (chunked input) | Multiple files, or a single file chunked via `scripts/chunk_text.py`. Read each chunk separately. |

## Edge Cases and Fallbacks

| Situation | Approach |
|:---|:---|
| Task tool not available | Fall back to sequential processing: read chunks one at a time with `Read`, analyze each in the main conversation context, aggregate manually. |
| Subagent output too large | Have the subagent summarize its findings rather than returning raw data. Instruct it in the prompt: "Return a concise summary, not the raw content." |
| Binary files | Use `Bash` with `file <path>` to detect type. For binary formats (PDF, images), use appropriate tools (`python3` with libraries, or dedicated MCP tools) rather than chunking. |
| Context is a URL or API | Fetch with `WebFetch` or `Bash` with `curl`, save to a temp file, then apply the standard assessment and chunking workflow. |
| Very large number of files (100+) | Group files by directory or type first. Fan out one subagent per group, not per file. Two-level decomposition. |
