---
name: handoff
description: Hand the project off to a fresh agent session. Use when the owner says it's time to hand off, wants to start a new agent session, or asks for a handoff, or when the handoff hook reports context at about 250k-300k tokens. Updates memory.md first, then writes the next handoff-prompts/orchestrator/orchestrator-handoff-N.md as the final step.
---

# Handoff procedure

Follow these steps **in order**. The handoff prompt is always the **last** thing written.

## 1. Update `memory.md` (first)
Edit `memory.md` at the repo root so it reflects the true current state:
- bump **Last updated** and **Latest handoff written** (the number you are about to write)
- add a new entry to the **Session log**: what was completed this session, decisions the owner made, decisions still open
- refresh **Repository state** (git status, files added or changed, anything uncommitted) and **Open questions and next steps**
- add any caveats the next session must know (assumptions, unverified numbers, things that failed)

Be factual. Report incomplete or failed work as incomplete or failed.

## 2. Bring the other docs up to date
- `docs/planning-handoff.md`: update §1 "Decisions so far" and §5 open decisions if anything was decided.
- `docs/adr/` and `docs/implementation-plan.md`, if they exist: make sure they match what was decided or built.
- `CLAUDE.md`: update it only if the repo structure, commands, or rules changed. Update the "Latest" handoff number in its file map.

## 3. Write the handoff prompt (last)
1. List `handoff-prompts/orchestrator/` and find the highest `orchestrator-handoff-N.md`. The new file is `orchestrator-handoff-(N+1).md`. **Never overwrite an earlier handoff.**
2. Write it as a self-contained prompt for a brand-new session. Include:
   - **Read first, in order:** `CLAUDE.md`, `memory.md`, then the relevant docs (`docs/planning-handoff.md`, `docs/adr/*`, `docs/implementation-plan.md`)
   - what was decided and built since the previous handoff, and what is still open
   - where things stand against the phase plan (`docs/planning-handoff.md` §0)
   - **exactly what the next session should do**, in order
   - the owner's rules: explain every design decision first, the owner has the final say, commit or push only when asked
   - what is out of scope
   - the reminder that the next handoff follows this same procedure
3. Keep it concrete: file paths and next actions, not a retelling of the conversation.

## 4. Finish
Tell the owner, briefly: the path of the new handoff file, what changed in `memory.md`, and anything uncommitted. Say they can start a new session and paste the handoff file as the first prompt. **Do not start new work after the handoff is written.**
