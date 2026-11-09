# 0018. Study content model (one PDF per set) and PDF text extraction library

- **Status:** Accepted (owner, 2026-11-09)

## Context
Phase 2a builds study sets, manual flashcards (M2), and PDF upload (M3). Planning doc §2.11 sketches the later tables. Libraries and licences checked 2026-11-09.

## Options
**PDFs per study set:** (1) one PDF per set; (2) several per set (closer to a course, but 2b would have to merge Knowledge Map concepts across documents).

**PDF text library:** pypdfium2 5.15 (PDFium, BSD-3/Apache-2.0); pypdf 7.0 (pure Python, BSD-3, weaker on complex layouts); pdfplumber 0.11 / pdfminer.six (MIT, layout-aware, slow); PyMuPDF (AGPL-3.0 or commercial: **excluded**, it would oblige publishing the hosted service's source).

## Decision
- **One PDF per study set in the MVP.** Uploading a PDF creates a study set from it (title defaulting to the sanitised file name). A set may also be created empty for manual cards; a set holds **at most one** document. The `documents` table carries `study_set_id` so several per set remain possible later without reshaping.
- **Study set:** `title` (1–120 chars), optional `description` (≤ 1000).
- **Flashcard:** `front` (1–500 chars), `back` (1–2000 chars), plain text with line breaks preserved (no Markdown/HTML rendering); `origin` `manual|generated` (only `manual` is produced in 2a); ordered by `created_at`; no manual reordering. `concept_id` is added in Phase 2b when concepts exist.
- **Review UI:** flip, next/previous, shuffle. No recall grading or scheduling (spaced repetition is out of MVP, ADR 0012).
- **Naming (orchestrator's call):** login sessions are `auth_sessions`; Feynman tutor conversations (2c) will be `study_sessions`, not `sessions` as §2.11 sketched.
- **PDF library: pypdfium2.** Parsing untrusted PDFs happens **only in the worker** (ADR 0015), never in the API process. The API checks size (≤ 20 MB, streaming) and the `%PDF-` signature; the worker enforces the 200-page limit and the "no readable text" failure (ADR 0016).

## Consequences
New API dependency: `pypdfium2` (binary wheels; worker-only use). Multi-document sets would be a later ADR plus a Knowledge Map merge design.
