# 0014. UI styling: Tailwind CSS + shadcn/ui, theme kept swappable

- **Status:** Accepted (owner, 2026-11-09)

## Context
Phase 1 had no styling (spec §3). The MVP needs real, accessible UI: auth forms with the age screen (ADR 0013), dialogs, a flip-card review, an editable concept list, file upload with job status, a streaming chat, and toasts. The prototype's CSS stays retired (ADR 0010); the landing page is out of the MVP (ADR 0012). The owner compared mockups of the options and asked that the choice stay **flexible for later visual changes**.

## Options (versions checked 2026-11-09)
1. **Tailwind CSS 4.3 + shadcn/ui**: components copied into the repo as our own code, on Radix accessible primitives.
2. Mantine 9: complete component library; fastest to working screens; its look is hard to move far from.
3. CSS Modules + Base UI headless primitives: full control, every visual decision hand-made; slowest.

## Decision
Option 1, with these rules so the look can change later without touching every screen:
- **All design tokens live in one place** (the Tailwind v4 `@theme` / CSS variables in the global stylesheet, e.g. `web/src/index.css`): colours, radius, fonts, spacing scale. Rebranding = editing that file.
- **Components use semantic token classes** (`bg-primary`, `text-muted-foreground`, `border-border`), never raw palette colours (`bg-indigo-600`) or hex values in screens. shadcn's generated components already follow this.
- **Screens are built from the shared components in `web/src/components/ui/`**, not from ad-hoc styled markup, so a component restyle propagates everywhere.
- MVP look: shadcn's neutral default theme + **one accent colour**, **light mode only**. Branding and dark mode are later (Phase 3+).
- Approved new web dependencies: `tailwindcss`, `@tailwindcss/vite`, the Radix primitives that shadcn components pull in, `lucide-react`, `class-variance-authority`, `clsx`, `tailwind-merge`, and the `shadcn` CLI as a dev-time tool. Further shadcn components may be added as needed without a new ADR; any *other* UI library needs owner approval.

## Consequences
The copied components are code we maintain (but also control). Markup carries utility classes. The token rule is reviewable: a raw colour class in a screen is a review finding.
