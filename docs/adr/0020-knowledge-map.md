# 0020. Knowledge Map: schema, editing, chunked extraction job, limits and a minimal cost guard

- **Status:** Accepted (owner, 2026-11-10)

## Context
Phase 2b, milestone M4 (ADR 0012). A Knowledge Map is the list of concepts extracted from a study set's PDF. The idea is in planning doc §2.2, with the tables sketched in §2.11. It feeds generated flashcards (2b, ADR 0021) and scoring (2c), which uses the explanations, key terms and misconceptions. The LLM and models come from ADR 0019 (Sonnet 5.5 for extraction). The source text is the `document_pages` rows written by `extract_pdf` (ADR 0015/0018).

## Options (each was presented to the owner with a recommendation)
1. **Trigger:** automatic after extraction (**chosen**) / the student clicks "Build".
2. **Prerequisites** (concept-to-concept links): none in the MVP (**chosen**) / included.
3. **Editing:** add/edit/delete / add/edit/delete **plus reordering (chosen; the owner's choice over the recommendation)**.
4. **Versioning:** one live map edited in place, with 2c snapshotting at session start (**chosen**) / immutable versions / no rebuild.
5. **Long PDFs:** one call plus a text cap / **chunk + merge (chosen; the owner's choice over the recommendation)**.
6. **Merge:** **the LLM groups duplicates and code merges the fields (chosen)** / the LLM rewrites the final list.
7. **Safety cap on extracted text:** **2,000,000 characters (chosen)** / page limit only.
8. **Retries mid-run:** re-run everything / **resume from saved chunk results (chosen; the owner's choice over the recommendation)**.
9. **Cost guard:** **5 map builds and 20 card generations per user per 24 h (chosen)** / looser / none.
10. **Usage record and kill switch:** **both (chosen)** / usage only / neither.

## Decision
**Schema**
- `knowledge_maps`:
  - `id`, `study_set_id` (FK CASCADE, **unique**: one map per set), `document_id` (FK CASCADE)
  - `status` `processing|ready|failed`, `error_message`
  - `model_id`
  - `revision` (an integer, bumped on every student edit, reorder or rebuild)
  - timestamps
- `concepts`:
  - `id`, `knowledge_map_id` (FK CASCADE)
  - `position` (an integer, unique within a map)
  - `title` (1–120 characters)
  - `explanation` (1–2000 characters, grounded in the source)
  - `importance` `core|supporting|detail`
  - `key_terms` JSONB `[{term, synonyms[]}]` (at most 10)
  - `misconceptions` JSONB `[text]` (at most 5)
  - `source_pages` `int[]` (checked against the document's page count)
  - timestamps
  - The 2b design states the exact per-item lengths.
- `knowledge_map_chunks` (used for resuming):
  - `knowledge_map_id` (FK CASCADE), `chunk_index` (together the primary key)
  - `page_start`, `page_end`
  - `status` `pending|done`
  - `result` JSONB (that chunk's validated concepts), `usage` JSONB
- No `prerequisites` column in the MVP.

**Building the map**
- **Automatic:** when `extract_pdf` succeeds, it creates the map (`processing`) and enqueues a `build_knowledge_map` job in the same transaction.
- **Chunks:** consecutive pages, split on page boundaries, about 30k tokens per chunk (the 2b design sets the exact character budget). Each page in a chunk carries a page marker, so concepts cite real page numbers.
  - A document that fits in one chunk gets one extraction call and no merge.
  - Several chunks are extracted in parallel (a small bounded number) with Sonnet 5.5.
  - Each chunk's validated result is saved in `knowledge_map_chunks` before the next stage. A retried job skips chunks already `done`.
- **Merge** (only with two or more chunks):
  - One Sonnet call receives a compact list (concept id, title, a one-line summary) and returns duplicate groups.
  - Code merges each group deterministically:
    - the explanation comes from the kept concept
    - key terms and misconceptions are unioned, de-duplicated and capped
    - `source_pages` are unioned
    - importance takes the highest value
  - Concepts are ordered by first appearance.
- **Rebuild:** the student confirms; it counts against the limit. It deletes the chunks and concepts and runs the job again. Generated cards are kept, and their `concept_id` becomes NULL (ADR 0021).
- **Failures:**
  - temporary provider errors (429, 5xx, network) retry through the queue's backoff
  - a refusal, output truncated at `max_tokens`, or output that fails validation fails permanently, with a fixed user-facing message
  - a failed map can be retried by the student (this counts as a rebuild)
- **Untrusted input:** PDF text goes in delimited blocks, with an instruction to treat it only as source material. The model gets no tools, the output is held to the schema, and everything is rendered as plain text.
- **Long-running work:** an LLM job must not hold a database transaction or row lock while it waits on the provider, and its lease must cover its calls. The 2b design specifies the mechanism.

**Editing (owner-scoped)**
- Add a concept (appended at the end), edit any field, delete, and **reorder** (one request with the full ordered list of concept IDs).
- Each change bumps `revision`.
- The UI labels the map "AI-generated from <file>" (AI disclosure, ADR 0019).

**Versioning:** one live map per set, with stable concept IDs. **2c snapshots** the content of the concepts a session covers into that session, so scores are always tied to the text they were scored against. There are no version tables in 2b.

**Limits and cost guard**
- `extract_pdf` fails a document whose extracted text exceeds **2,000,000 characters**, with a clear message. This closes 2a owner item 3 for text size.
- **Per-user limits** use the existing Postgres rate limiter:
  - **5 map builds per 24 h** (automatic builds, rebuilds and retries)
  - **20 card generation runs per 24 h**
  - The API answers `429 rate_limited`. An automatic build over the limit fails the map with a "daily limit reached" message the student can act on later.
- **Usage:** every LLM job stores the summed `Usage` (model, input, output and cached tokens, per call and in total) in `jobs.result`. Full usage logging remains 2c (M9).
- **`LLM_ENABLED`** setting (kill switch). When it is false, LLM jobs fail cleanly with a fixed message, so dev setups without an API key keep working.

## Consequences
- Three new tables and two new job kinds (`build_knowledge_map` here; `generate_flashcards` in ADR 0021).
- Chunking and resuming add code, but a retry never pays twice for finished chunks.
- The worst-case cost per map is bounded by the 200-page limit, the text cap and the per-user limit (roughly $1–1.50 for a maximal document at Sonnet 5.5 prices).
- Prerequisites, immutable versions and multi-document maps are later ADRs.
