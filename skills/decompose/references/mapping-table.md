# RLM Primitive → Agent Tool Mapping

Complete mapping from the RLM framework's primitives to agent tools, with the
persistent REPL as the primary mechanism.

## Core Primitives

| RLM Primitive | Agent Equivalent | Notes |
|:---|:---|:---|
| `context` variable | REPL variables | Load file contents into REPL variables where they persist and can be queried programmatically. Preferred over reading files into the agent's context window. |
| `len(context)` | `scripts/chunk_text.py info` or REPL `os.path.getsize()` | Always measure before choosing a strategy. Store measurements in REPL variables. |
| `context[:10000]` | REPL string slicing | `content = open(f).read(); chunk = content[:10000]` — slice in the REPL, not via tool arguments. |
| `llm_query(prompt)` | `Task` tool (lightweight subagent) | Use `subagent_type="Explore"` or `model="haiku"` for fast one-shot work. No iteration, no tool access needed. |
| `rlm_query(prompt)` | `Task` tool (general-purpose subagent) | Use `subagent_type="general-purpose"` when the sub-problem needs its own multi-step reasoning, file access, or REPL interaction. |
| `llm_query_batched(prompts)` | Multiple `Task` calls in a single message | Issue N independent Task calls simultaneously. They run in parallel. |
| `rlm_query_batched(prompts)` | Multiple `Task` calls (general-purpose) in a single message | Same as above but each subagent gets full tool access for deeper reasoning. |
| `print()` for debugging | Direct text output to user | Agent responses are visible to the user. No special mechanism needed. |
| `SHOW_VARS()` | `python3 scripts/repl_client.py /tmp/repl.sock --vars` | The persistent REPL provides a true equivalent. Inspect all accumulated state at any time. |
| `FINAL_VAR(answer)` / `FINAL(answer)` | Final response to user | Present the synthesized answer directly. Read final results from the REPL if needed. |
| Python computation in REPL | Persistent REPL | `python3 scripts/repl_client.py /tmp/repl.sock 'import math; print(math.sin(1.5))'` — state persists across calls. |
| `import` in REPL | Persistent REPL | Import once, use everywhere. The REPL namespace persists for the session. |

## Decomposition Patterns

| RLM Pattern | Agent Pattern |
|:---|:---|
| `for chunk in chunks: answer = llm_query(...)` | Sequential Task calls, one per chunk. Each stores results in the REPL. Use when order matters or each chunk depends on prior results. |
| `answers = llm_query_batched(prompts)` | Multiple Task calls in one message. Each writes to a named REPL variable. Use when chunks are independent. |
| `if "X" in result: rlm_query(...)` | Inspect subagent result (or REPL variable), then conditionally launch another Task. Branching on results is natural in the agentic loop. |
| Nested `rlm_query` inside `rlm_query` | Task subagent that itself launches Task calls. Supported natively — subagents can spawn their own subagents, all sharing the same REPL. |
| `context` as `List[str]` (chunked input) | Multiple files loaded into REPL variables, or a single file chunked via `scripts/chunk_text.py` and stored in a REPL list. |

## Edge Cases and Fallbacks

| Situation | Approach |
|:---|:---|
| Task tool not available | Fall back to sequential processing in the REPL: load chunks one at a time, analyze each with inline Python, aggregate results in REPL variables. |
| Subagent output too large | Have the subagent store results in the REPL instead of returning them. The parent reads from the REPL — no context window wasted on large return values. |
| Binary files | Use the REPL: `import subprocess; result = subprocess.run(["file", path], capture_output=True)`. For binary formats (PDF, images), use appropriate Python libraries in the REPL. |
| Context is a URL or API | Fetch in the REPL: `import urllib.request; data = urllib.request.urlopen(url).read()`. Save to a REPL variable, then apply the standard assessment and chunking workflow. |
| Very large number of files (100+) | Group files by directory or type in the REPL first. Fan out one subagent per group, not per file. Two-level decomposition with REPL as the aggregation layer. |
