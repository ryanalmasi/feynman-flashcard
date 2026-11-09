# Phase 2a Foundations: Design

> **Status:** Approved by the owner 2026-11-09 (builder-checked; owner answered its questions 2026-11-09)
> **Decided in:** orchestrator session 3. Decisions: ADRs 0012–0018 (Phase 2), building on 0001–0011 (Phase 1).
> **Next:** it becomes `docs/implementation-plan-phase-2a.md` (tasks in the Phase 1 plan format) plus an implementer kickoff prompt. The orchestrator reviews the resulting draft PR; the owner merges.

## 1. Intent and why

Phase 2 builds the MVP loop: *upload a PDF → editable Knowledge Map → generated flashcards → teach it to a "curious novice" AI tutor → score + feedback* (ADR 0012). It is split into three branches. **2a lays the non-AI foundations every later step stands on:** real accounts, a user's own study sets and flashcards, and PDF upload processed by a durable background worker into stored page text. No LLM is involved, so 2a can be built and tested before the provider decision (2b).

What makes 2a matter: it fixes, for good, the prototype's worst failures (cross-user access, cards addressed by list position, auth holes), and it puts in place the security posture the owner asked for (least privilege, no secrets in code, minimal personal data). Everything in 2b/2c will be "one more owned resource plus one more job kind" on top of it.

## 2. Goals

1. **Accounts (M1):** register (13+ neutral age screen), log in, log out, delete account; server-side sessions in Postgres; CSRF; rate limiting; breached-password check (ADRs 0005, 0013, 0017).
2. **Study sets + flashcards (M2):** CRUD for sets and manual cards; a flip/next/previous/shuffle review screen; cards addressed by id; every resource scoped to its owner (ADR 0018).
3. **PDF upload + job queue (M3):** upload a PDF (creates a set), store it via `FileStore`, process it in a separate worker using an own `jobs` table, store per-page text, show processing status in the UI (ADRs 0015, 0016, 0018).
4. **Styled web app:** Tailwind + shadcn/ui with centralised theme tokens (ADR 0014); auth-guarded routes.
5. **Phase 1 leftovers** fixed: CORS headers on 500 responses; `X-CSRF-Token` in CORS `allow_headers`; `dev-env.sh` warning; small test hardening (§7.9).

**Exit criteria (2a):** in a browser, a new user can register, log in, create a set, add/edit/delete cards, review them, upload a text-based PDF and watch it reach "Ready", delete the set, and delete their account. Every owned-resource endpoint has a cross-user test returning 404. `make check` and CI are green on the pushed branch. The owner's manual browser check passes.

## 3. Non-goals (later sub-phases or Phase 3+; do not build)

- Anything using an LLM or embeddings: Knowledge Map, generated flashcards, tutor, scoring, feedback, usage logging (2b/2c).
- Email sending, email verification, password reset, password change, OAuth/Google, MFA/passkeys.
- OCR or vision for scanned PDFs; more than one PDF per set; S3 or any object store; deployment.
- Spaced repetition or recall grading; card reordering; Markdown/rich text in cards.
- Landing page, branding, dark mode.
- Browser end-to-end test tooling (e.g. Playwright): not approved; the owner's manual check covers the end-to-end flow.

## 4. Anti-goals (failure even if it works)

- A password, birth month/year, session token, or CSRF token written to logs, error messages, or the DB in plain form (except the CSRF token, stored as designed in §7.2).
- Any endpoint that returns, changes, or reveals another user's resource (must be **404**, indistinguishable from "doesn't exist").
- PDF parsing in the API process; any filesystem path built from user input; the user's filename used as the stored name.
- Exception text, SQL, file paths, or connection details in an HTTP response.
- Raw palette colours or hex values in screens (ADR 0014); a UI library other than those approved.
- Tests that call the real HIBP service or depend on network access.
- A new dependency not approved here or in an ADR; `create_all()`; SQLite; secrets committed.

## 5. Constraints

- Everything from Phase 1 still holds (`CLAUDE.md` Conventions, `docs/implementation-plan.md` Global Constraints): API connects only as `feynman_app`, Alembic only as `feynman_migrator`; dev URLs use `localhost`; one error shape; TDD; real Postgres in tests.
- **Git (ADR 0011, ADR 0012):** branch **`phase-2a-foundations`** from `main`; one commit per plan task as `ryanalmasii`; pushed; draft PR; owner merges.
- **Approved new dependencies for 2a:** API runtime `argon2-cffi`, `pypdfium2`, `python-multipart` (FastAPI form/file uploads), `httpx` (moved from dev to runtime, for the HIBP call), `email-validator` (Pydantic `EmailStr`). Web: `tailwindcss`, `@tailwindcss/vite`, `tw-animate-css`, the Radix primitives pulled in by shadcn components (individual `@radix-ui/*` packages or the `radix-ui` umbrella package, whichever the shadcn CLI installs), `sonner` (toasts), `lucide-react`, `class-variance-authority`, `clsx`, `tailwind-merge`, `shadcn` CLI (dev-time). **Not approved:** `next-themes` (strip it from the generated `sonner` wrapper; light mode only), `react-hook-form`, `zod` (use plain controlled forms). Anything else → stop and ask.

## 6. Approaches considered (full reasoning in the ADRs)

| Decision | Chosen | Rejected and why |
|---|---|---|
| Scope/split (0012) | §0 scope as written; 2a/2b/2c branches | One big PR (unreviewable); trimming generated cards (cheap once maps exist) |
| Age (0013) | 13+ neutral screen, store only `age_verified_at` | 16+ (excludes 13–15), 18+ (excludes school students), parental consent (too heavy) |
| UI (0014) | Tailwind + shadcn/ui, central tokens | Mantine (hard to rebrand); CSS Modules + Base UI (slow) |
| Jobs (0015) | Own `jobs` table + worker | procrastinate (second DB driver + own schema); pgqueuer (young, heavy deps) |
| Files (0016) | Local disk behind `FileStore`; 20 MB / 200 pages / text-only | S3-compatible in Compose (infra, licensing check); bytea (bloat) |
| Auth details (0017) | 12-char min, HIBP fail-open, Postgres rate limits, session CSRF token + Origin, hashed session tokens | 15-char (owner preferred 12); bundled password list (weaker); in-memory limiter (lost on restart) |
| Content/PDF (0018) | One PDF per set; pypdfium2 in worker only | Multi-PDF sets (map merging); pypdf (weaker text); pdfplumber (slow); PyMuPDF (AGPL) |

## 7. The design as decided

### 7.1 Additions to the tree
```
api/src/feynman_api/
  auth/            passwords.py (argon2, normalisation, HIBP client), sessions.py, csrf.py,
                   rate_limit.py, dependencies.py (current_user, require_csrf)
  routes/          auth.py, study_sets.py, flashcards.py, documents.py   (+ health.py)
  models/          auth_session.py, rate_limit.py, study_set.py, flashcard.py, document.py, job.py
  storage.py       FileStore protocol + LocalFileStore
  jobs/            queue.py (enqueue, claim, complete, fail), worker.py (`python -m feynman_api.worker`),
                   handlers/extract_pdf.py
api/alembic/versions/   0002_auth_sessions_rate_limits.py, 0003_study_content.py, 0004_jobs.py (split at the builder's discretion)
api/tests/fixtures/     small committed PDFs (text, image-only, >200 pages) + README saying how they were made
web/src/
  index.css        Tailwind import + @theme tokens (the only place colours/radius/fonts are defined)
  components/ui/   shadcn components;  components/  AppShell, RequireAuth, …
  auth/            AuthProvider (session + csrf token), useAuth
  pages/           LoginPage, RegisterPage, SetsPage, SetDetailPage, ReviewPage, AccountPage,
                   StatusPage (moved to /status), NotFoundPage
Makefile           + `worker`
```
Exact file splits are the builder's (§8); the module boundaries above are not.

### 7.2 Data model (new and changed tables)
All ids `uuid` (default `uuid4`), timestamps `timestamptz` with `now()` defaults, FKs `ON DELETE CASCADE` toward the owning user, length limits enforced **both** in Pydantic and as DB `CHECK` constraints.

- `users` + `age_verified_at timestamptz NULL` (set on registration; nullable so the column can be added and future OAuth users get it at their own age screen).
- `auth_sessions(id, user_id → users, token_hash bytea UNIQUE NOT NULL, csrf_token text NOT NULL, created_at, last_seen_at, expires_at)`. `token_hash` = SHA-256 of the cookie token. `csrf_token` is a separate random value, not a credential on its own, returned to the SPA. Idle expiry: `last_seen_at + 7 days`; absolute: `expires_at = created_at + 30 days`. `last_seen_at` updates are throttled (e.g. at most once a minute) to avoid a write per request. Expired rows are deleted lazily (on lookup) and by a cheap cleanup at login.
- `rate_limit_buckets(key text, window_start timestamptz, count int, PRIMARY KEY(key, window_start))`: fixed-window counters, incremented with `INSERT … ON CONFLICT DO UPDATE`. Keys like `login:email:<sha256(normalised email)>` and `login:ip:<ip>` (emails hashed so the table holds no plain addresses). Old windows deleted opportunistically.
- `study_sets(id, user_id → users, title, description NULL, created_at, updated_at)`.
- `flashcards(id, study_set_id → study_sets, front, back, origin text CHECK IN ('manual','generated') DEFAULT 'manual', created_at, updated_at)`. Index on `(study_set_id, created_at)`.
- `documents(id, study_set_id → study_sets UNIQUE, storage_key text UNIQUE, original_filename text, size_bytes int, page_count int NULL, status text CHECK IN ('processing','ready','failed'), error_message text NULL, created_at, updated_at)`. `error_message` holds only fixed, user-facing strings (§7.6).
- `document_pages(document_id → documents, page_number int, text text, PRIMARY KEY(document_id, page_number))`. Page text is kept for 2b's Knowledge Map and source citations.
- `jobs(id, user_id → users, kind text, payload jsonb, status text CHECK IN ('queued','running','succeeded','failed'), attempts int DEFAULT 0, max_attempts int DEFAULT 3, run_after timestamptz DEFAULT now(), locked_until timestamptz NULL, last_error text NULL, result jsonb NULL, created_at, updated_at)`. Index on `(status, run_after)` for claiming.

`feynman_app` gets DML on all of these through the existing default privileges. No new extensions.

### 7.3 API
All under the existing error shape `{"error":{"code","message","details"}}`. Unauthenticated requests to protected endpoints → **401 `not_authenticated`**. Unsafe methods (POST/PUT/PATCH/DELETE) on authenticated endpoints require a valid `X-CSRF-Token` and an allowed `Origin`, else **403 `csrf_failed`**. Other users' resources → **404 `not_found`**.

**Auth** (`/auth`)
| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/auth/register` | `email, password, birth_month (1–12), birth_year` | 201 `{user, csrf_token}` + session cookie (registration logs you in) | 422 `validation_error` (bad email, password < 12 or > 128 chars); 422 `password_breached`; 409 `email_taken`; 403 `registration_not_allowed` (under 13; message neutral, no age mentioned); 429 `rate_limited` |
| POST | `/auth/login` | `email, password` | 200 `{user, csrf_token}` + new session cookie | 401 `invalid_credentials` ("Invalid email or password"); 429 `rate_limited` + `Retry-After` |
| POST | `/auth/logout` | none | 204, cookie cleared, session row deleted | 401, 403 |
| GET | `/auth/session` | none | 200 `{user, csrf_token}` | 401 |
| DELETE | `/auth/account` | `password` | 204: deletes the user (cascades), all sessions, and their stored files | 401, 403, 401 `invalid_credentials` on wrong password |

`register`/`login` are exempt from the CSRF token (no session yet) but **do** require an allowed `Origin`. Age is computed from month/year against today (a user born in the current month of the 13th-birthday year counts as 13). Birth month/year are never stored or logged. `user` = `{id, email, created_at}`.

**Study sets and flashcards**
| Method | Path | Notes |
|---|---|---|
| GET | `/study-sets` | Own sets, newest first; each with `card_count` and `document` summary (`status`, `page_count`, `original_filename`) or null |
| POST | `/study-sets` | `{title, description?}` → 201 |
| GET / PATCH / DELETE | `/study-sets/{id}` | DELETE → 204; removes cards, document, pages, and the stored file |
| GET | `/study-sets/{id}/flashcards` | Ordered by `created_at` |
| POST | `/study-sets/{id}/flashcards` | `{front, back}` → 201, `origin='manual'` |
| PATCH / DELETE | `/flashcards/{id}` | Ownership checked through the set |

No pagination in 2a (sets and cards are small); responses are lists.

**Documents**
| Method | Path | Notes |
|---|---|---|
| POST | `/documents` | `multipart/form-data` with `file` (+ optional `title`), via FastAPI `UploadFile`. **Size enforcement (owner decision, option A):** (1) a pure-ASGI body-size-limit middleware on this route rejects a declared `Content-Length` above the cap immediately and aborts any body (chunked or not) once it exceeds the cap (20 MB + a small multipart allowance), before Starlette's temp spool can grow past it; (2) the handler counts bytes while copying to `FileStore` and enforces exactly 20 MB. Over the limit → 413 `file_too_large`; no stored file and no temp file left behind. First bytes not `%PDF-` → 415 `unsupported_file_type`. Creates set + document (`processing`) + `extract_pdf` job in one transaction → **202** `{study_set, document}` |
| GET | `/documents/{id}` | `{id, study_set_id, status, page_count, error_message, original_filename}` (the UI polls this) |

No endpoint returns page text in 2a (2b's concern).

### 7.4 File storage
`FileStore` protocol: `async put(key, stream) -> int` (bytes written), `open(key)`, `async delete(key)` (missing file is not an error). `LocalFileStore(root)` writes to `root/<key>` where `key` is a server-generated UUID hex; it refuses keys that are not plain UUID hex. Root from setting `UPLOAD_DIR` (default `var/uploads` relative to `api/`, gitignored; created on startup). Deletions of sets/accounts commit the DB change first, then delete files; failures to delete are logged, not raised. Tests use a temporary directory.

### 7.5 Job queue and worker
- `enqueue(session, kind, payload, user_id)` inserts a `queued` row in the caller's transaction.
- The worker (`python -m feynman_api.worker`, `make worker`) connects as `feynman_app` with its own engine, loops: claim one due job (`status='queued' AND run_after <= now()` **or** `status='running' AND locked_until < now()`), `FOR UPDATE SKIP LOCKED`, set `running`, `attempts += 1`, `locked_until = now() + lease` (default 5 min); run the handler; on success `succeeded` (+ `result`); on a **transient** error, back to `queued` with `run_after = now() + backoff` (e.g. 10 s × 2^attempts) until `max_attempts`, then `failed`; on a **permanent** error (handler raises a dedicated `PermanentJobError`), `failed` immediately. `last_error` stores a short sanitised message, never a traceback (the traceback goes to the worker log).
- Polls every 1 s when idle (setting). Graceful shutdown on SIGINT/SIGTERM: finish the current job, then exit.
- Handlers are idempotent and registered by `kind`. 2a has one: `extract_pdf`.

### 7.6 PDF processing (`extract_pdf`)
1. Load the document; if it no longer exists (set deleted meanwhile), succeed as a no-op.
2. Open the stored file with pypdfium2. Unparseable → permanent failure, document `failed`, message **"This file couldn't be read as a PDF."**
3. Page count > 200 → permanent failure, **"This PDF has more than 200 pages."**
4. Extract text per page; replace the document's `document_pages`; set `page_count`.
5. If the total non-whitespace text is below a threshold (setting; default 100 characters for the whole document), permanent failure: **"This PDF looks scanned or has no selectable text, so it can't be read yet."**
6. Otherwise document `ready`.
7. *(Orchestrator's call, from the builder check.)* **Any other exception is transient** (retried with backoff). When retries run out (`max_attempts`), the job is `failed` **and the document is set to `failed`** with the generic message **"Something went wrong while processing this PDF. Try uploading it again."** A document never stays `processing` because of a job failure.
Document `status`/`error_message` and the job row are updated in the same transaction as the outcome.

### 7.7 Web
- **Routes:** `/login`, `/register`, `/` (→ `/sets` if signed in, else `/login`), `/sets`, `/sets/:id`, `/sets/:id/review`, `/account`, `/status`, `*` (not found). Everything except `/login`, `/register`, `/status`, and not-found is behind `RequireAuth` (redirect to `/login?next=…`; `next` must be a same-app relative path).
- **AuthProvider:** calls `GET /auth/session` on load; holds `user` and `csrf_token`; a 401 there just means "signed out" (no redirect, so `/register` stays reachable). An openapi-fetch middleware adds `X-CSRF-Token` to unsafe requests. *(Orchestrator's call.)* Only a 401 with code **`not_authenticated`** on other calls clears auth state and sends the user to `/login`; a 401 `invalid_credentials` (wrong password on login or account deletion) is shown as a form error and never logs the user out.
- **Register:** email, password (hint: "At least 12 characters"), birth month + year selects (year list spans the last 100 years, no default that hints at a cutoff, no mention of age limits). Refusal shows the neutral server message.
- **Sets page:** list of sets (title, card count, document status badge); "New set" dialog; "Upload PDF" (client-side check: `.pdf` and ≤ 20 MB, then the server decides).
- **Set detail:** title/description edit; card list with add/edit/delete (dialogs); document status: "Processing…" (polls `GET /documents/{id}` every 2 s, stops on `ready`/`failed`; *orchestrator's call:* after 10 minutes it stops and shows "This is taking longer than expected. Check back later.", which also covers a worker that isn't running), "Ready · N pages", or the failure message; "Review" button (disabled with no cards).
- **Review:** one card at a time, click/space to flip, arrow keys or buttons for next/previous, shuffle toggle, "Card i of n".
- **Account:** email shown; log out; delete account (dialog requiring the password, with a plain warning that everything is deleted).
- **Styling:** shadcn neutral theme, one accent colour, light mode, tokens only in `index.css` (ADR 0014). Toasts for success/failure of actions. Accessible: labelled inputs, focus management in dialogs (shadcn/Radix), keyboard-operable review.

### 7.8 Security details (ADR 0017, restated for the builder)
argon2id via `argon2-cffi` defaults, rehash on login when parameters change; password NFKC-normalised; length 12–128; HIBP range API with `Add-Padding: true`, 2 s timeout, fail-open with a warning log, disabled in tests via a fake. Session cookie name e.g. `feynman_session`, `HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure` controlled by setting `SESSION_COOKIE_SECURE` (default true; `false` in the dev `.env`). Constant-time comparison for CSRF tokens. Rate-limit starting values: 5 failed logins per email / 15 min; 20 login attempts per IP / 15 min; 5 registrations per IP / hour (all settings). Client IP = the socket peer address (no `X-Forwarded-For` trust in 2a; proxies are a deployment concern).
*Rate-limit semantics (orchestrator's call, from the builder check):* the limiter is checked **before** the password is verified. Once an email's failure window is full, **every** login for that email gets 429 until the window ends, including the correct password; otherwise the 429/200 difference would tell an attacker when a guess was right. The cost (anyone who knows an email can lock that account out for up to 15 minutes) is accepted for the MVP and bounded by the per-IP limit. The per-email counter counts **failures only**; a successful login clears it. The per-IP login counter counts **all** attempts; the registration counter counts all registration attempts.

### 7.9 Phase 1 leftovers folded in
- **500s without CORS headers (F7):** unhandled exceptions must produce the standard 500 body **with** CORS headers for allowed origins. Pinned by a test (allowed `Origin` + a raising route → 500 JSON + `access-control-allow-origin`). Mechanism left to the builder (e.g. catching exceptions in a middleware that sits inside `CORSMiddleware`).
- CORS `allow_headers` adds `X-CSRF-Token`.
- `scripts/dev-env.sh` warns when it creates `infra/.env` while `api/.env` already exists (passwords would not match). New settings get `.env.example` entries and `make env` values (dev: `SESSION_COOKIE_SECURE=false`).
- `test_migrations`: `try/finally` to always leave the DB at head; an explicit inspector assertion that `uq_users_email_lower` exists and is unique.
- `logging.basicConfig(..., force=True)` so the configured level always applies.

### 7.10 Testing (minimum)
- **Auth:** register success sets a cookie with the right flags; duplicate email 409; short password 422; breached 422 (fake HIBP); HIBP timeout fails open; under-13 403 with a neutral message and nothing stored; login success/failure; generic failure message; rate limits → 429 + `Retry-After`; logout invalidates the session; idle and absolute expiry (with controllable time); session token stored only hashed; CSRF missing/wrong → 403; bad `Origin` → 403; account deletion requires the password and removes rows **and files**; no password/birth data in captured logs.
- **Ownership:** a parametrized test over **every** owned-resource endpoint: user B gets 404 for user A's set/card/document (read, update, delete).
- **Content:** CRUD happy paths, validation limits (DB `CHECK` and API), card order, delete cascades.
- **Upload/worker:** > 20 MB → 413 and no file left behind; non-PDF → 415; text PDF → `ready` with pages stored; > 200 pages → `failed` with the exact message; image-only → `failed` with the exact message; transient failure retries with backoff then fails; an expired lease is reclaimed; two concurrent claimers never get the same job; set deleted mid-processing → no-op.
- **Web (Vitest):** route guard redirects; CSRF header added on unsafe requests only; 401 → login; register form (password hint, month/year selects, server errors shown); upload client checks; status polling stops on terminal states (fake timers); review flip/next/shuffle and keyboard.
- **Manual (owner):** the exit-criteria flow in the Windows browser.

## 8. Left to the builder
File splits within the modules of §7.1; migration file split; exact backoff numbers, lease length and polling interval within the stated defaults; the rate-limit cleanup strategy; the CORS-on-500 mechanism; how fixture PDFs are produced (committed binaries; any generator must not become a project dependency without approval); shadcn component selection; UI copy not quoted above (keep it short and plain); test-fixture mechanics. Anything that changes structure, dependencies, or security posture goes back to the owner.
