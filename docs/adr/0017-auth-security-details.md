# 0017. Auth security details (implements ADR 0005 for Phase 2a)

- **Status:** Accepted (owner, 2026-11-09)

## Context
ADR 0005 fixed the shape: own server-side sessions in Postgres, email + password in the MVP, CSRF on state-changing requests, argon2id. This ADR fixes the details for Phase 2a's auth milestone (M1). Versions checked 2026-11-09.

## Options and decision
1. **Minimum password length.** NIST SP 800-63B rev. 4 (2025) recommends ≥ 15 characters when the password is the only factor. Options: 15 / 12 / 8. **Decision: 12 characters minimum** (owner's choice; a deliberate compromise below NIST's single-factor guidance, to revisit when MFA or passkeys arrive). Maximum **at least 64** (accept up to 128). **No composition rules** (no forced symbols/digits). Unicode allowed (NFKC-normalised before hashing).
2. **Breached-password check at sign-up:** Have I Been Pwned Pwned Passwords **range API** (k-anonymity: only the first 5 hex chars of the SHA-1 hash leave the server; `Add-Padding: true`). **Fails open** on timeout (2 s) or error, logging a warning. Tests use a fake; CI never calls the real service. Chosen over a bundled common-password list (offline but far weaker).
3. **Rate limiting:** a small Postgres-backed limiter (no Redis; survives restarts). Applies to login and registration, keyed **per IP and per normalised email**. Starting values (tunable settings): 5 failed logins per email per 15 min; 20 login attempts per IP per 15 min; 5 registrations per IP per hour. Over the limit → **429** with `Retry-After`, in the standard error shape. Login failures always return the generic "Invalid email or password". Known, accepted trade-off: registration reveals "an account with this email already exists" (no email sending in the MVP to avoid it); rate limiting bounds the enumeration.
4. **CSRF:** a per-session random token, stored with the session and returned to the SPA (e.g. via `GET /auth/session`); the SPA sends it as `X-CSRF-Token` on every non-GET/HEAD/OPTIONS request; the server compares in constant time. In addition, unsafe requests must carry an `Origin` header in `CORS_ORIGINS`. `X-CSRF-Token` is added to CORS `allow_headers`.
5. **Sessions:** cookie value = 256-bit random token (`secrets.token_urlsafe(32)`); the DB stores only its **SHA-256 hash**. Cookie `HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure` in every environment except local dev (a setting). **7-day idle timeout, 30-day absolute lifetime.** A new token on every login (no fixation); logout deletes the session row; account deletion (ADR 0013) requires the current password and deletes all sessions.
6. **Hashing:** `argon2-cffi` (MIT) with its RFC 9106-based default parameters; rehash on login if parameters change. Password reset and email verification remain deferred (ADR 0005).

## Consequences
New API dependency: `argon2-cffi`. The HIBP call adds one outbound HTTPS request at sign-up (via `httpx`, promoted from a dev to a runtime dependency). Rate-limit and session tables are added by Alembic migrations in Phase 2a. The 12-character minimum is recorded as below NIST's single-factor recommendation.
