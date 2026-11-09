# 0016. File storage: local disk behind a `FileStore` interface; upload limits

- **Status:** Accepted (owner, 2026-11-09)

## Context
Phase 2a adds PDF upload (ADR 0012). Phase 2 runs locally only; deployment storage is a Phase 3+ concern. The original PDF is needed to re-run extraction and to cite sources.

## Options
1. **Local disk behind a small `FileStore` interface**, with an S3-compatible adapter added at deployment.
2. An S3-compatible server in Docker Compose now: real S3 API from day one, but more infrastructure, and self-hosted S3 projects' licensing/distribution has shifted recently (would need its own check).
3. PDF bytes in Postgres: simple and backed up with the data, but bloats the DB and would move later anyway.

## Decision
Option 1.
- `FileStore` protocol (`put`, `open`/`get`, `delete`) with a `LocalFileStore` implementation rooted at a configured directory (setting e.g. `UPLOAD_DIR`, default a gitignored `var/uploads/`). Stored under a random UUID key, **never the user's filename** (the original name is kept only as display metadata, sanitised). Paths are never built from user input.
- **Limits:** PDF only, verified by content (`%PDF-` magic bytes and a successful parse), not just the extension or `Content-Type`; **max 20 MB** (enforced by a body-size cap in front of the upload endpoint plus byte counting while saving; see the Phase 2a design §7.3); **max 200 pages**. **Text-based PDFs only:** if extraction yields no meaningful text, the job fails with a clear user message ("This PDF looks scanned; it can't be read yet"). OCR/vision is Phase 3+.
- **Retention:** the file is kept until the user deletes the study set or their account (ADR 0013), then removed from disk as well as the DB.

## Consequences
No new infrastructure. The S3 adapter and its access policy are deployment work. Disk files are outside DB transactions, so deletes must remove the file after the DB commit and tolerate an already-missing file.
