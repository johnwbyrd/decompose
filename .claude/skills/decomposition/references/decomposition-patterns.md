# Decomposition Patterns — Worked Examples

Five detailed examples showing the full assessment → decompose → aggregate workflow
using Claude Code's native tools.

## Pattern 1: Large Log File (500K lines)

**Scenario:** User asks "What errors occurred in the last 24 hours and what caused them?"

**Assessment:**
```bash
python3 scripts/chunk_text.py info server.log
# → char_count: 45000000, line_count: 520000, suggested_chunks: 450
```

45M characters — far too large for a single pass.

**Strategy:** Timestamps provide natural boundaries. Chunk by time window,
fan out in parallel, aggregate error summaries.

**Execution:**

1. Use Bash to extract the time range and split by hour:
   ```bash
   python3 scripts/chunk_text.py boundaries server.log
   # Look for timestamp patterns to determine time-based chunking
   ```

2. Chunk into manageable pieces (~100K chars each):
   ```bash
   python3 scripts/chunk_text.py chunk server.log --size 100000
   ```

3. Fan out parallel Task calls (one per chunk):
   ```
   Task(prompt="Identify all errors, warnings, and exceptions in this log segment.
   For each, note the timestamp, error type, and likely cause: <chunk>")
   ```
   Issue multiple Task calls in a single message for parallelism.

4. Aggregate: collect all subagent responses, launch one final Task:
   ```
   Task(prompt="Synthesize these per-chunk error reports into a unified summary.
   Group by error type, note frequency, identify root causes: <all_reports>")
   ```

**Key insight:** Log files have temporal structure. Exploit it for chunking
rather than using arbitrary character boundaries.

---

## Pattern 2: Multi-File Codebase Review (~30 files)

**Scenario:** User asks "Review this codebase for architectural issues and
potential bugs."

**Assessment:**
```bash
wc -c src/**/*.py
# → 15 files, ranging from 2KB to 85KB, total ~400KB
```

400KB total, multi-file. No single file exceeds 100KB.

**Strategy:** One subagent per file (or per module), parallel fan-out.
Files are independent at the analysis stage, so parallelize fully.

**Execution:**

1. List and measure all source files:
   ```bash
   find src/ -name "*.py" -exec wc -c {} +
   ```

2. Group small files by directory to avoid excessive subagent count:
   - `src/core/` (5 files, 180KB) → 2 subagents
   - `src/clients/` (7 files, 120KB) → 1 subagent
   - `src/utils/` (3 files, 50KB) → 1 subagent
   - `src/environments/` (5 files, 50KB) → 1 subagent

3. Fan out 5 parallel Task calls:
   ```
   Task(prompt="Review these source files for architectural issues, potential
   bugs, and code quality concerns. Note file:line for each finding.
   Files: <list of files in group>. Read each file and analyze.")
   ```

4. Aggregate findings:
   ```
   Task(prompt="Synthesize these per-module reviews into a prioritized list.
   Group as: Critical (bugs), Important (architecture), Minor (style).
   Reports: <all_reports>")
   ```

**Key insight:** For multi-file analysis, group by module rather than
processing each file individually. This preserves intra-module context.

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

3. Collect Phase 1 results. Only sections marked YES proceed.

4. Phase 2 — deep analysis of relevant sections only:
   ```
   Task(subagent_type="general-purpose",
        prompt="Analyze this contract section for clauses that limit
   liability to less than the purchase price. Quote the exact language
   and explain its implications: <relevant_section>")
   ```

5. Aggregate deep analyses into a final answer.

**Key insight:** Two-phase decomposition avoids wasting deep analysis on
irrelevant content. The fast relevance filter (Phase 1) uses lightweight
subagents; only flagged sections get expensive deep analysis (Phase 2).

---

## Pattern 4: Comparing Two Large Datasets

**Scenario:** User provides two CSV exports (before and after a migration)
and asks "What data was lost or changed in the migration?"

**Assessment:**
```bash
wc -c before.csv after.csv
# → before.csv: 2.1MB, after.csv: 1.9MB
```

Two parallel contexts, each ~2MB. Too large to diff in memory directly.

**Strategy:** Chunk both files by row ranges, pair corresponding chunks,
compare pairwise, aggregate differences.

**Execution:**

1. Examine structure (headers, row count):
   ```bash
   head -1 before.csv
   wc -l before.csv after.csv
   ```

2. Chunk both files into matching row ranges:
   ```bash
   python3 scripts/chunk_text.py chunk before.csv --size 100000
   python3 scripts/chunk_text.py chunk after.csv --size 100000
   ```

3. Pair chunks by position. Fan out parallel comparisons:
   ```
   Task(prompt="Compare these two CSV segments. Identify rows that are
   present in 'before' but missing in 'after', rows that changed, and
   rows that were added. Before: <before_chunk> After: <after_chunk>")
   ```

4. Aggregate all pairwise difference reports:
   ```
   Task(prompt="Synthesize these pairwise comparison reports into a
   unified migration diff. Categorize: lost rows, changed rows, added
   rows. Quantify each category: <all_reports>")
   ```

**Key insight:** For comparison tasks, chunk both inputs in parallel and
pair them. Do not try to hold both datasets in a single context.

---

## Pattern 5: Multi-Step Codebase Reasoning

**Scenario:** User asks "Trace how a user request flows from the HTTP handler
to the database, identifying all validation steps along the way."

**Assessment:**
```bash
find src/ -name "*.py" | wc -l
# → 45 files
wc -c src/**/*.py | tail -1
# → total 620KB
```

620KB across 45 files. The question requires understanding call chains
across files — pure chunking would lose cross-file context.

**Strategy:** Three-phase approach.
Phase 1: Map the architecture (parallel).
Phase 2: Trace specific flows (targeted recursive queries).
Phase 3: Synthesize the trace.

**Execution:**

1. Phase 1 — Architecture mapping. Fan out per module:
   ```
   Task(prompt="Read all files in src/handlers/ and list: every public
   function, what it calls, and what modules it imports. Return as a
   structured list.")

   Task(prompt="Read all files in src/validators/ and list: every
   validation function, what it checks, and what errors it raises.")

   Task(prompt="Read all files in src/database/ and list: every
   database operation, what tables it touches, and what ORM it uses.")
   ```

2. Collect architecture maps. Identify the entry point and the call chain.

3. Phase 2 — Targeted trace. Based on the architecture map, follow the
   specific path:
   ```
   Task(subagent_type="general-purpose",
        prompt="Given this architecture map: <map>
   Trace the flow from the HTTP handler for POST /users through
   all validation steps to the database insert. Read each file
   along the path and document every validation check, transformation,
   and error handling step.")
   ```

4. Phase 3 — Synthesize into a readable flow diagram for the user.

**Key insight:** Cross-file reasoning requires a map-then-trace approach,
not a flat chunking approach. Build the architecture map first (parallel,
per-module), then use it to guide targeted deep dives.
