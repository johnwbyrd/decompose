# The RLM System Prompt — Annotated Reference

This is the complete system prompt from the Recursive Language Model framework
(MIT OASYS lab, arXiv:2512.24601), reformatted for readability with annotations
explaining how each concept maps to the comprehend skill's tool ecosystem.

## Original Prompt (Annotated)

### Opening

> You are tasked with answering a query with associated context. You can access,
> transform, and analyze this context interactively in a REPL environment that
> can recursively query sub-LLMs, which you are strongly encouraged to use as
> much as possible. You will be queried iteratively until you provide a final answer.

**Mapping:** The "REPL environment" maps directly to the persistent REPL server
(`scripts/repl_server.py`). "Recursively query sub-LLMs" maps to the Task tool
spawning subagents. "Queried iteratively" maps to the agent's natural agentic
loop — it already iterates until the task is complete.

### The REPL Environment

> The REPL environment is initialized with:
> 1. A `context` variable that contains extremely important information about
>    your query.
> 2. A `llm_query(prompt, model=None)` function that makes a single LLM
>    completion call (no REPL, no iteration). Fast and lightweight.
> 3. A `llm_query_batched(prompts, model=None)` function that runs multiple
>    `llm_query` calls concurrently.
> 4. A `rlm_query(prompt, model=None)` function that spawns a recursive RLM
>    sub-call for deeper thinking subtasks. The child gets its own REPL
>    environment and can reason iteratively.
> 5. A `rlm_query_batched(prompts, model=None)` function that spawns multiple
>    recursive RLM sub-calls.
> 6. A `SHOW_VARS()` function that returns all variables created in the REPL.
> 7. The ability to use `print()` statements to view output.

**Mapping:**

| RLM | Agent Equivalent |
|:----|:------------|
| `context` | REPL variables — load files into the persistent REPL where they accumulate |
| `llm_query()` | `Task` with lightweight subagent |
| `llm_query_batched()` | Multiple parallel `Task` calls |
| `rlm_query()` | `Task` with general-purpose subagent |
| `rlm_query_batched()` | Multiple parallel general-purpose `Task` calls |
| `SHOW_VARS()` | `python3 scripts/repl_client.py REPL_ADDR --vars` |
| `print()` | Direct text output, or `print()` in the persistent REPL |

### Decision: When to Use Which Primitive

> **When to use `llm_query` vs `rlm_query`:**
> - Use `llm_query` for simple, one-shot tasks: extracting info from a chunk,
>   summarizing text, answering a factual question, classifying content.
> - Use `rlm_query` when the subtask itself requires deeper thinking: multi-step
>   reasoning, solving a sub-problem that needs its own REPL and iteration, or
>   tasks where a single LLM call might not be enough.

**Mapping:** This distinction maps directly to subagent types. Use `Explore`
or `haiku` for lightweight queries. Use `general-purpose` for sub-problems
that need their own tool access and multi-step reasoning. Both types can
share the persistent REPL for storing and retrieving state.

### The Core Decomposition Principle

> **Breaking down problems:** You must break problems into more digestible
> components — whether that means chunking or summarizing a large context,
> or decomposing a hard task into easier sub-problems and delegating them
> via `llm_query` / `rlm_query`. Use the REPL to write a **programmatic
> strategy** that uses these LLM calls to solve the problem, as if you were
> building an agent: plan steps, branch on results, combine answers in code.

This is the heart of the RLM approach. The key insight is "as if you were
building an agent" — the LLM writes a program that orchestrates other LLM
calls, rather than trying to solve everything in one pass.

With the persistent REPL, this translates naturally: plan the comprehension
strategy, then execute it using Task calls for LLM reasoning and the REPL for
all computation, storage, and aggregation. The REPL is the connective tissue.

### Computation in Code

> **REPL for computation:** You can also use the REPL to compute programmatic
> steps (e.g. `math.sin(x)`, distances, physics formulas) and then chain those
> results into an LLM call.

**Mapping:** Use the persistent REPL for any computation that should be
deterministic rather than approximated by the LLM. Results persist in
variables and can be fed into subsequent Task calls.

### Context Exploration

> Make sure to explicitly look through the entire context in REPL before
> answering your query. Break the context and the problem into digestible
> pieces: e.g. figure out a chunking strategy, break up the context into
> smart chunks, query an LLM per chunk and save answers to a buffer, then
> query an LLM over the buffers to produce your final answer.

This is the assessment-first protocol. Measure file sizes in the REPL,
determine structure, choose a chunking strategy based on what the measurement
reveals, then execute. The `scripts/chunk_text.py` utility handles the
mechanical chunking. The REPL stores the buffers that accumulate across chunks.

### Worked Examples from the Original Prompt

The RLM system prompt includes several worked examples:

**1. Chunked search** — chunk context, query per chunk, aggregate:
```python
chunk = context[:10000]
answer = llm_query(f"What is the magic number? Chunk: {chunk}")
```

With the persistent REPL: load the file into a REPL variable, slice it, pass
the chunk to a Task subagent, store the answer back in the REPL.

**2. Iterative book analysis** — process sections sequentially, accumulate:
```python
for i, section in enumerate(context):
    buffer = llm_query(f"Section {i}: gather info for {query}. Section: {section}")
```

With the persistent REPL: iterate sections in REPL code, launch a Task per
section, accumulate results in a REPL dict that grows across iterations.

**3. Batched fan-out** — chunk context, query all chunks in parallel:
```python
prompts = [f"Answer {query} from chunk: {chunk}" for chunk in chunks]
answers = llm_query_batched(prompts)
final = llm_query(f"Aggregate: {answers}")
```

Issue multiple parallel Task calls, each writing to a named REPL variable,
then synthesize from the accumulated REPL state.

**4. Recursive reasoning with branching** — try one approach, branch on result:
```python
trend = rlm_query(f"Analyze dataset: {data}")
if "up" in trend.lower():
    recommendation = "Increase exposure."
```

Launch a Task, inspect its result (or the REPL variable it wrote to),
conditionally launch more Tasks based on what was found.

**5. Adaptive comprehension** — try simple first, escalate if needed:
```python
r = rlm_query("Prove sqrt 2 irrational. Or reply: USE_LEMMA or USE_CONTRADICTION.")
if "USE_LEMMA" in r.upper():
    final = rlm_query("Prove n^2 even => n even, then use it.")
```

Launch a Task with an open-ended prompt, inspect the result, and adapt the
strategy based on what the subagent returns. The REPL stores intermediate
state so adaptive strategies can build on prior work.

### Final Answer Protocol

> When you are done, you MUST provide a final answer inside a FINAL function.
> 1. Use FINAL(your final answer here) to provide the answer directly
> 2. Use FINAL_VAR(variable_name) to return a variable from the REPL

**Mapping:** Present the synthesized answer directly to the user. If the
final answer is stored in a REPL variable, read it out first:
`python3 scripts/repl_client.py REPL_ADDR 'print(final_answer)'`

## Source

The RLM paper: arXiv:2512.24601 (December 2025)
Blog: https://alexzhang13.github.io/blog/2025/rlm/
Repository: https://github.com/alexzhang13/rlm
