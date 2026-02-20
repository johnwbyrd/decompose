# Comprehension Patterns — Worked Examples

Five detailed examples showing the full assessment → comprehend → aggregate workflow
using the persistent REPL and subagents.

## Pattern 1: Large Log File (500K lines)

**Scenario:** User asks "What errors occurred in the last 24 hours and what caused them?"

**Assessment:**
```bash
python3 scripts/chunk_text.py info server.log
# → char_count: 45000000, line_count: 520000, suggested_chunks: 450
```

45M characters — far too large for a single pass.

**Strategy:** Timestamps provide natural boundaries. Chunk by time window,
fan out in parallel, aggregate error summaries via the REPL.

**Execution:**

1. Generate a session-unique address, start the REPL, and examine log structure:
   ```bash
   REPL_ADDR=$(python3 scripts/repl_server.py --make-addr)
   python3 scripts/repl_server.py "$REPL_ADDR" &

   python3 scripts/repl_client.py REPL_ADDR '
   with open("server.log") as f:
       first_lines = [next(f) for _ in range(5)]
       print("First lines:", first_lines)
   '
   ```

2. Chunk into manageable pieces (~100K chars each):
   ```bash
   python3 scripts/chunk_text.py chunk server.log --size 100000
   ```

3. Fan out parallel Task calls (one per chunk). Each subagent stores
   findings in the REPL:
   ```
   Task(prompt="Use REPL at REPL_ADDR. Identify all errors, warnings, and
   exceptions in this log segment. Store results in errors['chunk_N'] as a list
   of dicts with keys: timestamp, error_type, cause. Chunk: <chunk>")
   ```
   Issue multiple Task calls in a single message for parallelism.

4. Aggregate from the REPL:
   ```bash
   python3 scripts/repl_client.py REPL_ADDR '
   all_errors = []
   for chunk_id, chunk_errors in errors.items():
       all_errors.extend(chunk_errors)
   by_type = {}
   for e in all_errors:
       by_type.setdefault(e["error_type"], []).append(e)
   for t, errs in sorted(by_type.items(), key=lambda x: -len(x[1])):
       print(f"{t}: {len(errs)} occurrences")
   '
   ```

**Key insight:** Log files have temporal structure. Exploit it for chunking
rather than using arbitrary character boundaries. The REPL accumulates
findings across all chunks so aggregation is a simple Python operation.

---

## Pattern 2: Multi-File Codebase Review (~30 files)

**Scenario:** User asks "Review this codebase for architectural issues and
potential bugs."

**Assessment:**
```bash
python3 scripts/repl_client.py REPL_ADDR '
import glob, os
source_files = glob.glob("src/**/*.py", recursive=True)
file_sizes = {f: os.path.getsize(f) for f in source_files}
total = sum(file_sizes.values())
print(f"{len(source_files)} files, {total} bytes ({total/1024:.0f} KB)")
'
```

400KB total, multi-file. No single file exceeds 100KB.

**Strategy:** One subagent per module, parallel fan-out. All results stored
in the REPL for cross-module aggregation.

**Execution:**

1. Group files by directory in the REPL:
   ```bash
   python3 scripts/repl_client.py REPL_ADDR '
   from collections import defaultdict
   groups = defaultdict(list)
   for f in source_files:
       module = "/".join(f.split("/")[:2])
       groups[module].append(f)
   for module, files in groups.items():
       size = sum(file_sizes[f] for f in files)
       print(f"{module}: {len(files)} files, {size/1024:.0f} KB")
   '
   ```

2. Fan out parallel Task calls, one per module group:
   ```
   Task(prompt="Use REPL at REPL_ADDR. Read and review these source files
   for architectural issues, potential bugs, and code quality concerns.
   Store findings in reviews['module_name'] as a list of dicts with keys:
   file, line, severity, description. Files: <list of files in group>")
   ```

3. Aggregate from the REPL:
   ```bash
   python3 scripts/repl_client.py REPL_ADDR '
   all_findings = []
   for module, findings in reviews.items():
       all_findings.extend(findings)
   for severity in ["critical", "important", "minor"]:
       items = [f for f in all_findings if f["severity"] == severity]
       print(f"\n{severity.upper()} ({len(items)}):")
       for item in items:
           print(f"  {item[\"file\"]}:{item[\"line\"]} — {item[\"description\"]}")
   '
   ```

**Key insight:** For multi-file analysis, group by module rather than
processing each file individually. This preserves intra-module context.
The REPL lets you aggregate findings programmatically across all modules.

---

## Pattern 3: Long Document Q&A (200-page PDF or text)

**Scenario:** User asks "Does this contract contain any clauses that limit
liability to less than the purchase price?"

**Assessment:**
```bash
python3 scripts/chunk_text.py info contract.txt
# → char_count: 850000, suggested_chunks: 9, has_structure: true
```

850K chars with structure (sections/headings). The question is specific —
most sections are irrelevant.

**Strategy:** Two-phase approach. Phase 1: identify relevant sections
(fast, parallel). Phase 2: deep analysis of only the relevant ones.
All results flow through the REPL.

**Execution:**

1. Detect section boundaries:
   ```bash
   python3 scripts/chunk_text.py boundaries contract.txt
   ```

2. Chunk by sections. Fan out Phase 1 — lightweight relevance check:
   ```
   Task(subagent_type="Explore",
        prompt="Does this section contain any mention of liability,
   indemnification, limitation of damages, or caps on liability?
   Answer YES or NO with a one-sentence explanation: <section>")
   ```
   Issue all in parallel.

3. Collect Phase 1 results. Store relevance flags in the REPL:
   ```bash
   python3 scripts/repl_client.py REPL_ADDR '
   relevant_sections = [s for s, flag in section_flags.items() if flag == "YES"]
   print(f"{len(relevant_sections)} of {len(section_flags)} sections are relevant")
   '
   ```

4. Phase 2 — deep analysis of relevant sections only:
   ```
   Task(subagent_type="general-purpose",
        prompt="Use REPL at REPL_ADDR. Analyze this contract section
   for clauses that limit liability to less than the purchase price. Store
   findings in liability_analysis['section_N'] with keys: clause_text,
   implication. Section: <relevant_section>")
   ```

5. Synthesize from the REPL into a final answer.

**Key insight:** Two-phase comprehension avoids wasting deep analysis on
irrelevant content. The fast relevance filter (Phase 1) uses lightweight
subagents; only flagged sections get expensive deep analysis (Phase 2).

---

## Pattern 4: Comparing Two Large Datasets

**Scenario:** User provides two CSV exports (before and after a migration)
and asks "What data was lost or changed in the migration?"

**Assessment:**
```bash
python3 scripts/repl_client.py REPL_ADDR '
import os
before_size = os.path.getsize("before.csv")
after_size = os.path.getsize("after.csv")
print(f"before.csv: {before_size/1024/1024:.1f} MB")
print(f"after.csv: {after_size/1024/1024:.1f} MB")
'
```

Two parallel contexts, each ~2MB. Too large to diff in memory directly.

**Strategy:** Chunk both files by row ranges, pair corresponding chunks,
compare pairwise, aggregate differences in the REPL.

**Execution:**

1. Examine structure in the REPL:
   ```bash
   python3 scripts/repl_client.py REPL_ADDR '
   with open("before.csv") as f:
       header = f.readline().strip()
       row_count_before = sum(1 for _ in f)
   with open("after.csv") as f:
       f.readline()
       row_count_after = sum(1 for _ in f)
   print(f"Header: {header}")
   print(f"Rows: before={row_count_before}, after={row_count_after}")
   '
   ```

2. Chunk both files into matching row ranges:
   ```bash
   python3 scripts/chunk_text.py chunk before.csv --size 100000
   python3 scripts/chunk_text.py chunk after.csv --size 100000
   ```

3. Pair chunks by position. Fan out parallel comparisons:
   ```
   Task(prompt="Use REPL at REPL_ADDR. Compare these two CSV segments.
   Store results in diffs['chunk_N'] with keys: lost_rows, changed_rows,
   added_rows (each a list). Before: <before_chunk> After: <after_chunk>")
   ```

4. Aggregate from the REPL:
   ```bash
   python3 scripts/repl_client.py REPL_ADDR '
   total_lost = sum(len(d["lost_rows"]) for d in diffs.values())
   total_changed = sum(len(d["changed_rows"]) for d in diffs.values())
   total_added = sum(len(d["added_rows"]) for d in diffs.values())
   print(f"Lost: {total_lost}, Changed: {total_changed}, Added: {total_added}")
   '
   ```

**Key insight:** For comparison tasks, chunk both inputs in parallel and
pair them. The REPL accumulates diffs across all chunks so you get exact
counts without holding both datasets in the agent's context window.

---

## Pattern 5: Multi-Step Codebase Reasoning

**Scenario:** User asks "Trace how a user request flows from the HTTP handler
to the database, identifying all validation steps along the way."

**Assessment:**
```bash
python3 scripts/repl_client.py REPL_ADDR '
import glob, os
py_files = glob.glob("src/**/*.py", recursive=True)
total = sum(os.path.getsize(f) for f in py_files)
print(f"{len(py_files)} files, {total/1024:.0f} KB")
'
```

620KB across 45 files. The question requires understanding call chains
across files — pure chunking would lose cross-file context.

**Strategy:** Three-phase approach.
Phase 1: Map the architecture (parallel), store in REPL.
Phase 2: Trace specific flows (targeted recursive queries).
Phase 3: Synthesize the trace from REPL state.

**Execution:**

1. Phase 1 — Architecture mapping. Fan out per module, all writing to REPL:
   ```
   Task(prompt="Use REPL at REPL_ADDR. Read all files in src/handlers/
   and store in arch['handlers'] a dict mapping each public function to:
   its calls, its imports, and a one-line summary.")

   Task(prompt="Use REPL at REPL_ADDR. Read all files in src/validators/
   and store in arch['validators'] a dict mapping each validation function to:
   what it checks, what errors it raises.")

   Task(prompt="Use REPL at REPL_ADDR. Read all files in src/database/
   and store in arch['database'] a dict mapping each database operation to:
   what tables it touches, what ORM it uses.")
   ```

2. Read the architecture map from the REPL and identify the call chain:
   ```bash
   python3 scripts/repl_client.py REPL_ADDR '
   for layer, funcs in arch.items():
       print(f"\n{layer}:")
       for name, info in funcs.items():
           print(f"  {name}: {info.get(\"summary\", \"\")}")
   '
   ```

3. Phase 2 — Targeted trace using the architecture map:
   ```
   Task(subagent_type="general-purpose",
        prompt="Use REPL at REPL_ADDR. Read arch variable for the
   architecture map. Trace the flow from the HTTP handler for POST /users
   through all validation steps to the database insert. Read each file
   along the path. Store the complete trace in trace_result as a list of
   steps, each with: file, function, action, validation_checks.")
   ```

4. Phase 3 — Read trace from REPL and synthesize for the user:
   ```bash
   python3 scripts/repl_client.py REPL_ADDR '
   for i, step in enumerate(trace_result, 1):
       checks = ", ".join(step.get("validation_checks", []))
       print(f"{i}. {step[\"file\"]}:{step[\"function\"]} — {step[\"action\"]}")
       if checks: print(f"   Validates: {checks}")
   '
   ```

**Key insight:** Cross-file reasoning requires a map-then-trace approach,
not a flat chunking approach. Build the architecture map first (parallel,
per-module), store it in the REPL, then use it to guide targeted deep dives.
The REPL is the connective tissue that lets Phase 2 build on Phase 1's work.
