# 0013. Age policy: 13+ with a neutral age screen; no birth date stored

- **Status:** Accepted (owner, 2026-11-09)

## Context
The prototype stored date of birth. ADR 0005 left DOB out of the schema until this decision (planning doc §5 #7). Likely users include high-school and university students. Legal background (not legal advice; to be re-checked before any public launch): in the US, COPPA requires verifiable parental consent for users under 13; in the EU, GDPR Art. 8 sets the age of digital consent at 13–16 depending on the member state. Phase 2 runs locally only, so this mainly fixes the sign-up flow and schema.

## Options
1. **13+ with a neutral age screen.** Sign-up asks for birth month and year without revealing the cutoff (the FTC-recommended pattern; an "I am 13+" checkbox invites false answers). Under 13 is refused. Only an `age_verified_at` timestamp is stored.
2. 16+ with the same screen: clears every EU consent age, excludes 13–15-year-olds.
3. 18+ only: simplest legally, excludes most school students.
4. All ages with verifiable parental consent: too heavy for an MVP.

## Decision
Option 1.
- Sign-up collects birth month and year in a neutral way. If the user is under 13, registration is refused with a polite, non-specific message, and the form does not reveal the cutoff.
- **The birth month/year is never stored or logged.** `users` gains `age_verified_at timestamptz` (set at successful registration).
- **Account deletion** ("delete my account" removes everything the user owns, via the existing cascades) is in the MVP (Phase 2a), as a default the owner did not object to.
- Provider data-retention/training settings are decided with the LLM provider (Phase 2b).

## Consequences
Minimal personal data. EU users aged 13–15 and the exact wording of the terms and privacy policy are launch-time questions (Phase 3+ / deployment), recorded as open. Refusal is not cookie-locked in the MVP; a determined under-13 user can retry with a false date, which a self-declared age screen cannot prevent anyway.
