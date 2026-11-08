# CLAUDE.md

Guidance for Claude Code sessions in this repository. It describes what the repo **currently is**, not what it is meant to become. The product vision is covered separately below so the two don't get mixed up.

> **Status:** Early prototype, dormant since Jan 2025. The code was written by hand with ChatGPT pasting, with no agentic tooling. There are no tests, no CI, no migrations, and no Docker. Several features shown in the UI are placeholders. Expect bugs (listed in [Known Issues](#known-issues--gaps)).

---

## Product vision (intended, mostly NOT implemented)

A study tool built around the **Feynman technique**: after studying, the student "teaches" the topic to someone else to find gaps in their understanding.

1. **Feynman tutor agent (the core product):** the student explains a topic to an AI agent, either by typing or in **voice mode**. The agent acts as the learner and asks follow-up questions.
2. **Scoring:** at the end of the session, the student's explanation is scored by semantic/topical similarity to the source material.
3. **Feedback:** the agent reviews the conversation and reports what was missing, wrong, or unclear, and what to work on.
4. **Auto-generated flashcards (supplementary):** agents parse an uploaded lesson PDF or a discussion topic and generate a full set of flashcards for review.

**What exists today toward that vision:** manual flashcard CRUD, plus a single-card "Feynman" textbox. That textbox scores one typed explanation against the card's stored definition using cosine similarity of sentence embeddings, and returns a canned feedback string. There is no conversation, no agent, no LLM, no voice, no PDF ingestion, and no flashcard generation.

---

## Tech stack (as written)

| Layer | Tech |
|---|---|
| Frontend | React 18 (Create React App / `react-scripts` 5), React Router v6, axios, react-modal, react-select, FontAwesome |
| Backend | Flask, Flask-SQLAlchemy, Flask-Session (Redis), Flask-CORS, bcrypt, python-dotenv |
| Database | MySQL via PyMySQL; database name is hard-coded as `Illumina` |
| Sessions | Server-side sessions in Redis (cookie-based, `withCredentials`) |
| "AI" | `sentence-transformers` model `bert-base-nli-mean-tokens` (deprecated) + scikit-learn `cosine_similarity` |

---

## Repository map

```
feynman-flashcard/
├── CLAUDE.md                     ← this file
├── docs/planning-handoff.md      Design + research doc: roadmap (§0), scoring design, providers, costs, pricing, open decisions
├── memory.md                     Running project context + completed work. Read right after this file; update FIRST on every handoff
├── handoff-prompts/              Numbered prompts for starting the next agent session (orchestrator-handoff-N.md). Latest: #1. Written LAST in a handoff
├── .claude/                      Project Claude Code config: settings.json (handoff hooks), hooks/handoff-check.py, skills/handoff/SKILL.md
├── README.md                     Setup instructions (partly inaccurate, see Running Locally)
├── LICENSE                       MIT
├── requirements.txt              Python deps (at REPO ROOT, not backend/). Unused: pandas, numpy (imported but unused), flask-bcrypt (code uses `bcrypt` directly)
├── .DS_Store                     macOS junk, committed by mistake
│
├── backend/
│   ├── .DS_Store                 macOS junk
│   └── feynman_card/             Flat module dir, NOT a Python package (no __init__.py); imports are `from models import ...`
│       ├── routes.py             ★ Flask app entry point. Creates `app`, configures Session/CORS/DB, runs `db.create_all()`, defines all HTTP routes. `python routes.py` starts the debug server on :5000
│       ├── methods.py            Business logic: register/login, create set, add card, list cards, `evaluate_user_response()`. Loads the SentenceTransformer model at import time (slow, happens on first request because routes import methods lazily inside handlers)
│       ├── models.py             SQLAlchemy models: Users, FlashcardSets, Flashcards (32-char hex UUID PKs)
│       ├── config.py             `AppConfig`, reads .env: SECRET_KEY, DB_USRNAME (sic), DB_PASSWORD, DB_HOST, REDIS_URL
│       ├── flask_session/        5 stale filesystem session files, committed by mistake (from an earlier filesystem session backend)
│       └── __pycache__/          Compiled .pyc, committed by mistake
│
└── frontend/                     Create React App project
    ├── package.json / package-lock.json
    ├── .gitignore                Standard CRA ignore (the only .gitignore in the repo)
    ├── README.md                 Stock CRA readme
    ├── public/                   Stock CRA index.html (title still "React App"), manifest, favicon, logos
    └── src/
        ├── index.js              createRoot → <App/>
        ├── App.js                Router: "/" → HomePage, "/sets" → FlashcardSets, "/sets/:setName" → Flashcard. Sets axios.defaults.withCredentials
        ├── assets/images/        feynman.png, flashcard_graphic.png, learning.png (used by HomePage); background-auth*.png (used by AuthPage.css)
        └── components/
            ├── HomePage.js       Marketing landing page: header nav, hero, feature carousel (DOM-manipulating infinite scroll), "What is the Feynman Technique" sections with a mouse-hover spotlight effect, footer. Hosts the sign-in/sign-up overlay via activePage/activeTab state
            ├── AuthPage.js       Modal shell (overlay, close button, left title panel, right children panel)
            ├── SignIn.js         Login form → POST /login → navigate("/sets"). Google/Facebook/Apple buttons are non-functional
            ├── SignUp.js         Register form (email, username, password, birthday via 3 react-selects) → POST /register. Google/Facebook buttons non-functional; ToS checkbox not enforced
            ├── FlashcardSets.js  Lists the user's sets (GET /api/sets), creates a set (POST /api/sets), selects a set (POST /api/sets/select) then navigates to /sets/:setName. Unstyled
            ├── Flashcard.js      Card grid for the selected set: click to flip, "+" modal to add a card, "Feynman" button opens a textarea → POST /evaluate → shows raw score + feedback
            └── style/
                ├── HomePage.css  (~540 lines)
                ├── AuthPage.css  (~460 lines)
                └── Flashcard.css (~150 lines)
```

---

## Data model (`backend/feynman_card/models.py`)

```
Users (users)
  id            String(32) PK  (uuid4 hex)
  email         String(345) unique, not null
  username      String(255) unique, not null
  password      Text            bcrypt hash
  dob           Date, not null
  date_created  DateTime
      │ 1
      │ N
FlashcardSets (flashcard_sets)
  id            String(32) PK
  user_id       FK → users.id
  set_name      String(255)    (unique per user, enforced in code only)
  date_created  DateTime
      │ 1
      │ N
Flashcards (flashcards)
  id            String(32) PK
  set_id        FK → flashcard_sets.id
  concept       String(255)    (unique per set, enforced in code only)
  definition    Text
  date_created  DateTime
```

No SQLAlchemy `relationship()`s, no cascades, no DB-level unique constraints beyond email/username. Tables are created with `db.create_all()` at import time. There are no migrations.

---

## HTTP API (`backend/feynman_card/routes.py`)

All responses are JSON. Auth is a server-side session cookie. The "current set" is also stored in the session (`session['selected_set']`), which is unusual and causes several bugs.

| Method | Path | Auth | Body | Behavior |
|---|---|---|---|---|
| GET | `/@me` | session | none | Returns `session['user']` or 401. **Not called by the frontend.** |
| POST | `/register` | none | `email, username, password, birthday (YYYY-MM-DD)` | Hashes the password with bcrypt and inserts a user. Returns `{success, message}` (HTTP 200 even on failure) |
| POST | `/login` | none | `email, password` | Verifies bcrypt and stores `user.to_dict()` in the session |
| POST | `/logout` | none | none | `session.clear()`. **Not called by the frontend.** |
| GET | `/api/sets` | session | none | Lists the user's sets (no card counts or cards included) |
| POST | `/api/sets` | session | `set_name` | Creates a set |
| POST | `/api/sets/select` | session | `set_id` | Stores the set in `session['selected_set']`. **Does not check ownership.** |
| GET | `/api/sets/<set_name>` | session | none | Returns cards of `session['selected_set']`. **`set_name` is ignored.** Returns `[{index, concept, definition}]` with 0-based index in DB order |
| POST | `/api/sets/<set_name>/add` | session | `concept, definition` | Adds a card to `session['selected_set']`. **`set_name` is ignored.** |
| POST | `/evaluate` | selected set in session (does **not** check user) | `index, response, setName` | Loads cards for the selected set, picks `flashcards[index]`, and computes cosine similarity between embeddings of the response and the definition. Feedback is `"Good explanation!"` if > 0.8, else `"Try to add more details."` |

Frontend calls use the hard-coded base URL `http://127.0.0.1:5000`. CORS allows `localhost:3000` and `127.0.0.1:3000`.

---

## User flow (as implemented)

1. `/` HomePage → "Sign up for free" opens the SignUp overlay → register → switches to the SignIn tab → login → navigates to `/sets`.
2. `/sets` → list or create sets → clicking a set calls `/api/sets/select`, then navigates to `/sets/<name>`.
3. `/sets/<name>` → flip cards, add cards with the "+" modal, click "Feynman" on a card → type an explanation → submit → see the raw float score and the canned feedback.

There is no logout button, no route guard (the "Get Started" link goes straight to `/sets`, and unauthenticated users see an axios 401 error), no nav bar outside the homepage, and no 404 page. `/contact`, `/terms`, `/privacy`, and `/forgot-password` are linked but have no routes.

---

## Running locally (what actually works)

The README's backend steps are partly wrong. The steps below reflect the code.

**Prerequisites:** Python 3.10+ (pycache shows 3.10/3.13), Node + npm, a running **MySQL** server with a database named `Illumina` already created, and a running **Redis** server.

**`.env`** (not committed; place it where you run the backend, i.e. `backend/feynman_card/`):
```
SECRET_KEY=...
DB_USRNAME=...        # note the misspelling, it's what config.py reads
DB_PASSWORD=...
DB_HOST=localhost
REDIS_URL=redis://localhost:6379
```

**Backend:**
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt          # from repo root
cd backend/feynman_card
python routes.py                          # http://127.0.0.1:5000 (debug)
# or: FLASK_APP=routes flask run
```
`flask run` from `backend/` (as the README says) will not find the app: there is no `app.py`/`wsgi.py`, and imports are flat. The first request that touches `methods.py` downloads and loads the BERT model, which is slow.

**Frontend:**
```bash
cd frontend
npm install
npm start                                 # http://localhost:3000
```

**Tests / lint:** None exist. `npm test` runs CRA's jest, but there are no test files. There are no Python tests.

---

## Known issues & gaps

Collected while mapping the code. Useful input for the upcoming planning session.

### Backend
- **Redis config key is wrong:** `config.py` sets `SESSION_URL`, but Flask-Session reads `SESSION_REDIS`. `REDIS_URL` is effectively ignored, and Flask-Session falls back to its default (localhost:6379).
- **Fragile card indexing:** `/evaluate` and `GET /api/sets/<name>` identify cards by their position in an unordered `query.all()`, not by ID. The order can change between calls.
- **Authorization holes:** `/api/sets/select` doesn't check that the set belongs to the user, and `/evaluate` doesn't check login at all.
- **Crash:** in `get_flashcard_set`, `flashcard_set.get('id')` runs before the `None` check, so it returns a 500 if no set is selected.
- **URL `set_name` params are ignored.** State lives in the session instead, so deep links and refreshes on `/sets/<name>` break after the session changes. Set names aren't URL-encoded either.
- Failure responses often return HTTP 200 with `success: false` (register, create set, add card).
- `SQLALCHEMY_ECHO=True`, many `print()` debug statements, and the session is printed to stdout.
- No input validation (e.g. email format, password strength), no rate limiting, and no CSRF protection.
- The model loads at module import, and `bert-base-nli-mean-tokens` is deprecated. Raw cosine similarity is a weak scoring signal (short or paraphrased answers score oddly).
- No `relationship()`/cascades, so deleting a user or set would leave orphans. There are no delete/update endpoints at all.

### Frontend
- **Double AuthPage overlay:** HomePage wraps SignIn/SignUp in `<AuthPage>`, and SignIn/SignUp each render their own `<AuthPage>` too, so the overlay and modal are nested twice.
- Social login buttons sit inside `<form>` without `type="button"`, so clicking them **submits the form**. The tab-switch buttons do the same.
- `FlashcardSets.addSet` appends the new set without its `id`, so clicking a newly created set sends `set_id: undefined` until the page is refreshed. The card count always shows 0 because the API doesn't return cards.
- `Flashcard.addFlashcard` assigns `index: length + 1`, which doesn't match the backend's 0-based index, so evaluating a newly added card targets the wrong card.
- The Feynman `response` textarea isn't cleared between cards. `setConcept`/`setDefinition` from `selectFlashcard` pre-fill the "Add" modal by accident.
- Hard-coded API base URL, no shared axios instance, no env config. Lots of `console.log`.
- Uses `class=` instead of `className=` in a few JSX spots (React warnings).
- No auth state or context, route guards, logout, or loading states. `index.html` title is "React App".

### Repo hygiene
- Committed by mistake: `.DS_Store` files, `__pycache__/`, `flask_session/`. There is no root `.gitignore`.
- `requirements.txt` sits at the root while the README says to install from `backend/`. Dependencies are unpinned.
- Git history is six "Initial Commit"-style commits from 2025-01-04.

---

## Conventions observed

- Backend: plain functions in `methods.py` return `{"success": bool, "message": str, ...}` dicts. Routes are thin wrappers that import methods lazily inside each handler.
- IDs: `uuid4().hex` strings (32 chars) generated in Python.
- Frontend: function components with hooks, one CSS file per major component under `components/style/`, and direct axios calls inside components.

## Notes for future sessions

- A **planning session** is expected next to scope a first iteration toward the vision above (the Feynman tutor agent, text and voice, scoring, feedback, and PDF-to-flashcards). Treat the current code as a rough prototype.
- **Start with [`docs/planning-handoff.md`](docs/planning-handoff.md).** It holds the detailed multi-stage scoring design, the provider, voice, embedding, and Postgres research with pricing, per-session cost estimates, and the list of open decisions for the owner.

### Phase order (decided)
1. **Refactor and restructure the architecture.** 2. **Build an MVP of the backend and app.** 3. **Then improvements.** The scope and exit criteria for each phase are in `docs/planning-handoff.md` §0. Don't start Phase 3 features (voice, billing, calibration, and so on) before the MVP exists.

### Handoffs and memory.md (owner's rule)
`memory.md` (repo root) is the project's running record of context and completed work. It is **versioned with the repo** and is separate from Claude Code's private auto-memory. Every new session reads it right after this file.

**Every time the owner asks for a handoff, do these steps in this order. The handoff prompt is always the LAST step.**
1. **Update `memory.md` first:** bump the dates and handoff number, add a Session log entry (what was completed, what the owner decided, what is still open), refresh the repo state (git status, files added or changed, anything uncommitted) and the next steps and caveats. Be factual about anything incomplete or failed.
2. **Update the other docs that are now stale:** `docs/planning-handoff.md` §1/§5, the ADRs and `docs/implementation-plan.md` if they exist, and this file if the structure, commands, or rules changed.
3. **Write the handoff prompt last:** a new file `handoff-prompts/orchestrator-handoff-N.md`, where N is the highest existing number + 1. Never overwrite earlier handoffs. It is a self-contained prompt for the next agent session and should include:
   - which files to read first, in order (`CLAUDE.md`, `memory.md`, then the planning doc, ADRs, the implementation plan, and so on)
   - what has been decided and built since the previous handoff, and what is still open
   - where things stand against the phase plan, and exactly what the next session should do
   - the owner's rules (explain decisions first, the owner has final say, commit only when asked)
4. Tell the owner the path of the new file, and stop. Don't start new work after the handoff is written.

**This is automated.** The project skill `/handoff` (`.claude/skills/handoff/SKILL.md`) holds this procedure and also matches automatically when the owner says it's time to hand off or start a new agent session. A hook (`.claude/hooks/handoff-check.py`, registered in `.claude/settings.json` on `UserPromptSubmit` and `PostToolUse`) injects reminders:
- at about **250k tokens (~25% of a 1M context window)**: a heads-up. Offer the handoff to the owner, and don't start it unless they agree.
- at about **300k tokens (~30%)**: run the `handoff` skill at the next natural stopping point (not mid-edit), then tell the owner to start a new session.
- whenever the owner's prompt mentions a handoff or a new agent session: if they're asking for one, run the skill.

If you see a `[handoff-hook]` note in your context, follow it as described here. Token counts are an estimate taken from the last assistant turn's usage record. The thresholds can be changed with the `HANDOFF_WARN_TOKENS` and `HANDOFF_URGENT_TOKENS` environment variables.

### Decision process (owner's rule)
**Every design decision must be explained before implementation, and the owner has the final say.** For each choice (stack, provider, schema, auth, hosting), present the options, the trade-offs, and a recommendation with reasoning. Then wait for approval before writing code that depends on it. Don't make silent architectural choices.

### Direction agreed so far (not yet implemented)
- **Stack:** a full stack change is allowed. Pick whatever fits the design best (streaming chat, voice, document ingestion), but justify it first.
- **Database:** leaning towards **PostgreSQL**. The goal is the most secure, minimal setup: a least-privilege app role, no superuser in the app, TLS, secrets in env vars rather than code, and only the extensions that are actually needed (e.g. evaluate `pgvector` only if embeddings are stored). Whether Redis is still needed is an open question.
- **Scoring is multi-stage:**
  1. **Baseline score:** a cheap, deterministic, objective measure of how closely the explanation matches the source material (e.g. embedding similarity or key-concept coverage).
  2. **AI-graded score(s):** an LLM judges the explanation against the source on things like accuracy, completeness, clarity, and misconceptions.
  3. **Final result:** combine both, so the AI's subjective judgement is anchored to the objective baseline. Then generate actionable feedback from the conversation.
  - The full proposal is in `docs/planning-handoff.md` §2: a Knowledge Map, claim extraction, a baseline, an evidence-quoted rubric judge, asymmetric-band reconciliation, and calibration. It is a proposal awaiting owner approval.
- **"Illumina"** was just the name of the old MySQL database. It is not a product, dependency, or external system and can be dropped.

### Research status
The first round of research on the LLM provider, voice, embeddings, and Postgres hosting is done (2026-11-08); see `docs/planning-handoff.md` §3–4. A draft pricing model (free trial, Plus and Pro tiers, margins) is in §4b. **The owner has not decided on any of it yet.** The handoff doc recommends choosing the LLM through a gold-set bake-off rather than on price, because cheap-tier models cost about $0.01–0.02 per session.
