#!/usr/bin/env python3
"""Handoff reminder hook for Claude Code.

Runs on UserPromptSubmit and PostToolUse. Reads the hook JSON from stdin and
injects `additionalContext` telling the model to run the `handoff` skill when:

  1. Estimated context size crosses WARN (default 250k tokens, ~25% of a 1M window)
     -> heads-up: offer a handoff.
  2. It crosses URGENT (default 300k tokens, ~30%)
     -> run the handoff skill at the next natural stopping point.
  3. (UserPromptSubmit only) the user's prompt mentions a handoff / a new agent session.

Each token level fires once per session, and re-arms if context shrinks later
(e.g. after /compact). Context size is estimated from the most recent assistant
`usage` record in the transcript: input + cache read + cache creation tokens.

This hook never blocks: any error exits 0 with no output.

Env overrides: HANDOFF_WARN_TOKENS, HANDOFF_URGENT_TOKENS, HANDOFF_CONTEXT_WINDOW.
"""
import json
import os
import re
import sys
from pathlib import Path

WARN = int(os.environ.get("HANDOFF_WARN_TOKENS", "250000"))
URGENT = int(os.environ.get("HANDOFF_URGENT_TOKENS", "300000"))
WINDOW = int(os.environ.get("HANDOFF_CONTEXT_WINDOW", "1000000"))
TAIL_BYTES = 4_000_000  # only read the end of the transcript

KEYWORD = re.compile(
    r"hand[\s-]?off"
    r"|(?:start|open|begin|move to|switch to|hand (?:this )?over to)\s+(?:a\s+)?(?:new|fresh)\s+(?:agent\s+)?session",
    re.IGNORECASE,
)


def context_tokens(transcript_path):
    """Return the token count of the latest main-thread assistant turn, or None."""
    try:
        path = Path(transcript_path)
        size = path.stat().st_size
        with path.open("rb") as f:
            f.seek(max(0, size - TAIL_BYTES))
            data = f.read()
    except Exception:
        return None
    for line in reversed(data.splitlines()):
        try:
            obj = json.loads(line)
        except Exception:
            continue  # partial first line or non-JSON
        if not isinstance(obj, dict) or obj.get("isSidechain"):
            continue  # skip subagent turns: they have their own context
        message = obj.get("message")
        usage = message.get("usage") if isinstance(message, dict) else None
        if not isinstance(usage, dict):
            continue
        total = sum(
            int(usage.get(k) or 0)
            for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
        )
        if total > 0:
            return total
    return None


def state_file(session_id):
    base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session_id or "") or "unknown"
    return base / "feynman-handoff-hook" / f"{safe}.json"


def load_level(path):
    try:
        return int(json.loads(path.read_text()).get("level", 0))
    except Exception:
        return 0


def save_level(path, level):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"level": level}))
    except Exception:
        pass


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    event = payload.get("hook_event_name") or "UserPromptSubmit"
    notes = []  # context for the model
    banners = []  # short notices for the user

    tokens = context_tokens(payload.get("transcript_path", ""))
    if tokens is not None:
        sf = state_file(payload.get("session_id", ""))
        fired = load_level(sf)
        if tokens < WARN * 0.8:
            level = 0
        elif tokens >= URGENT:
            level = 2
        elif tokens >= WARN:
            level = 1
        else:
            level = fired
        pct = round(100 * tokens / WINDOW)
        if level > fired:
            if level == 1:
                notes.append(
                    f"[handoff-hook] Context is at about {tokens:,} tokens (~{pct}% of the window). "
                    "Per CLAUDE.md, briefly tell the owner the session is approaching the handoff point "
                    "and offer to run the `handoff` skill (update memory.md, then docs, then write "
                    "handoff-prompts/orchestrator-handoff-N.md LAST). Finish the current step first. "
                    "Do not start the handoff unless the owner agrees."
                )
                banners.append(f"Context ~{tokens:,} tokens (~{pct}%): handoff heads-up sent to Claude.")
            else:
                notes.append(
                    f"[handoff-hook] Context is at about {tokens:,} tokens (~{pct}% of the window), past the "
                    "handoff threshold. At the next natural stopping point (not mid-edit), invoke the "
                    "`handoff` skill: update memory.md FIRST, then any stale docs, then write the next "
                    "handoff-prompts/orchestrator-handoff-N.md LAST. Then tell the owner to start a new "
                    "session with that file, and stop doing other work."
                )
                banners.append(f"Context ~{tokens:,} tokens (~{pct}%): Claude was told to run the handoff.")
        save_level(sf, level)

    if event == "UserPromptSubmit":
        prompt = payload.get("prompt") or ""
        if KEYWORD.search(prompt):
            notes.append(
                "[handoff-hook] The owner's message mentions a handoff or a new agent session. If they are "
                "asking you to hand off, invoke the `handoff` skill now: update memory.md first, then docs, "
                "and write handoff-prompts/orchestrator-handoff-N.md last. If they are only discussing "
                "handoffs, ignore this note."
            )

    if not notes:
        return
    out = {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": "\n".join(notes),
        }
    }
    if banners:
        out["systemMessage"] = " ".join(banners)
    print(json.dumps(out))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
