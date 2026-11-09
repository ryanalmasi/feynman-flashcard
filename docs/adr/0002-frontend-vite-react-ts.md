# 0002. Frontend: Vite + React + TypeScript SPA

- **Status:** Accepted (owner, 2026-11-08)

## Context
Create React App (`react-scripts`) is deprecated. Nearly all of the app sits behind a login. The backend is a separate FastAPI service (0001).

## Options
1. **Vite + React + TypeScript single-page app.** The standard React setup, simple, and a natural fit for a separate API.
2. **Next.js.** Server rendering and file routing. Next to FastAPI it is a second server to run and deploy, and the main payoff (SEO for a marketing page) is post-MVP.

## Decision
**Vite + React + TypeScript (strict)** on Node 26 LTS ("Lithium", the active LTS as of 2026-10-28) with npm, pinned via `web/.nvmrc` and `engines`. Client-side routing uses React Router.

## Consequences
- The UI styling approach (e.g. Tailwind vs. CSS modules) and the component library are **Phase 2 decisions**. The Phase 1 skeleton needs neither.
- A marketing page with SEO needs, if wanted later, can be a separate static page.
