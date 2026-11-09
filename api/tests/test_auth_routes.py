import re
import unicodedata
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from argon2 import PasswordHasher
from asgi_lifespan import LifespanManager
from conftest import ORIGIN, FrozenClock, auth_headers, register
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.auth.passwords import needs_rehash
from feynman_api.auth.sessions import SESSION_COOKIE
from feynman_api.config import Settings
from feynman_api.main import create_app
from feynman_api.storage import LocalFileStore

pytestmark = pytest.mark.usefixtures("clean_db")

PW = "a-long-passphrase"


async def _login(
    client: httpx.AsyncClient, email: str = "a@example.com", password: str = PW
) -> httpx.Response:
    return await client.post(
        "/auth/login", json={"email": email, "password": password}, headers=ORIGIN
    )


async def test_register_success(api_client: httpx.AsyncClient, db: AsyncSession) -> None:
    r = await register(api_client, email="  A@Example.com ")
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == "a@example.com"
    assert body["csrf_token"]
    assert (await db.execute(text("select age_verified_at from users"))).scalar_one() is not None
    cols = (
        await db.execute(
            text("select column_name from information_schema.columns where table_name='users'")
        )
    ).scalars()
    assert not [c for c in cols if "birth" in c]


async def test_register_sets_session_cookie_flags(api_client: httpx.AsyncClient) -> None:
    r = await register(api_client)
    header = next(
        v for k, v in r.headers.multi_items() if k == "set-cookie" and SESSION_COOKIE in v
    )
    assert "HttpOnly" in header
    assert "SameSite=lax" in header
    assert "Path=/" in header
    assert "Max-Age=2592000" in header
    assert "Secure" not in header


async def test_secure_flag_follows_setting(
    migrated_db: None, test_settings: Settings, file_store: LocalFileStore
) -> None:
    app = create_app(
        test_settings.model_copy(update={"session_cookie_secure": True}), file_store=file_store
    )
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await register(client)
    assert r.status_code == 201
    assert "Secure" in r.headers["set-cookie"]


async def test_register_duplicate_email_409(api_client: httpx.AsyncClient) -> None:
    assert (await register(api_client)).status_code == 201
    r = await register(api_client, email="A@Example.com")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize("pw", ["x" * 11, "x" * 129])
async def test_register_password_length_422(api_client: httpx.AsyncClient, pw: str) -> None:
    r = await register(api_client, password=pw)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert pw not in r.text


async def test_register_password_nfkc_roundtrip(api_client: httpx.AsyncClient) -> None:
    pw = "ｐａｓｓｗｏｒｄ１２３４５６"  # noqa: RUF001  full-width forms
    assert unicodedata.normalize("NFKC", pw) != pw
    assert (await register(api_client, password=pw)).status_code == 201
    assert (await _login(api_client, password=pw)).status_code == 200
    assert (await _login(api_client, password=unicodedata.normalize("NFKC", pw))).status_code == 200


async def test_register_breached_422(api_client: httpx.AsyncClient, db: AsyncSession) -> None:
    r = await register(api_client, password="breached-password-123")  # noqa: S106
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "password_breached"
    assert (await db.execute(text("select count(*) from users"))).scalar_one() == 0


async def test_register_birth_year_out_of_range(
    api_client: httpx.AsyncClient, clock: FrozenClock
) -> None:
    for year in (clock().year + 1, clock().year - 121):
        r = await register(api_client, birth_year=year)
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "validation_error"


async def test_register_under_13_refused_neutrally(
    api_client: httpx.AsyncClient, clock: FrozenClock, db: AsyncSession
) -> None:
    now = clock()
    r = await register(api_client, birth_month=now.month, birth_year=now.year - 12)
    assert r.status_code == 403
    err = r.json()["error"]
    assert err["code"] == "registration_not_allowed"
    assert not re.search(r"\d", err["message"])
    assert "age" not in err["message"].lower()
    assert (await db.execute(text("select count(*) from users"))).scalar_one() == 0


async def test_register_13th_birthday_month_allowed(
    api_client: httpx.AsyncClient, clock: FrozenClock
) -> None:
    now = clock()
    r = await register(api_client, birth_month=now.month, birth_year=now.year - 13)
    assert r.status_code == 201


async def test_register_requires_origin(api_client: httpx.AsyncClient) -> None:
    body = {"email": "a@example.com", "password": PW, "birth_month": 1, "birth_year": 2000}
    r = await api_client.post("/auth/register", json=body)
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed"
    r = await api_client.post(
        "/auth/register", json=body, headers={"Origin": "http://evil.example"}
    )
    assert r.status_code == 403


async def test_register_rate_limited_per_ip(api_client: httpx.AsyncClient) -> None:
    for i in range(5):
        r = await register(api_client, email=f"u{i}@example.com")
        assert r.status_code == 201
    r = await register(api_client, email="u6@example.com")
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
    assert r.headers["retry-after"].isdigit()


async def test_login_success_rotates_session(api_client: httpx.AsyncClient) -> None:
    await register(api_client)
    cookie_a = api_client.cookies[SESSION_COOKIE]
    r = await _login(api_client)
    assert r.status_code == 200
    cookie_b = api_client.cookies[SESSION_COOKIE]
    assert cookie_a != cookie_b
    old = httpx.Cookies()
    old.set(SESSION_COOKIE, cookie_a)
    transport = httpx.ASGITransport(app=api_client._transport.app)  # type: ignore[attr-defined]
    async with httpx.AsyncClient(transport=transport, base_url="http://test", cookies=old) as c:
        assert (await c.get("/auth/session")).status_code == 401
    assert (await api_client.get("/auth/session")).status_code == 200


async def test_login_wrong_password_generic(api_client: httpx.AsyncClient) -> None:
    await register(api_client)
    r = await _login(api_client, password="wrong-password-xx")  # noqa: S106
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


async def test_login_unknown_email_generic(api_client: httpx.AsyncClient) -> None:
    await register(api_client)
    known = await _login(api_client, password="wrong-password-xx")  # noqa: S106
    unknown = await _login(api_client, email="nobody@example.com", password="wrong-password-xx")  # noqa: S106
    assert unknown.status_code == 401
    assert unknown.json() == known.json()


async def test_login_email_lockout_blocks_correct_password(
    api_client: httpx.AsyncClient, clock: FrozenClock
) -> None:
    await register(api_client)
    for _ in range(5):
        assert (await _login(api_client, password="wrong-password-xx")).status_code == 401  # noqa: S106
    r = await _login(api_client)
    assert r.status_code == 429
    assert r.headers["retry-after"].isdigit()
    clock.advance(minutes=15)
    assert (await _login(api_client)).status_code == 200


async def test_login_success_clears_email_failures(api_client: httpx.AsyncClient) -> None:
    await register(api_client)
    bad = "wrong-password-xx"
    for _ in range(4):
        assert (await _login(api_client, password=bad)).status_code == 401
    assert (await _login(api_client)).status_code == 200
    for _ in range(4):
        assert (await _login(api_client, password=bad)).status_code == 401


async def test_login_ip_limit(api_client: httpx.AsyncClient) -> None:
    for i in range(20):
        r = await _login(api_client, email=f"u{i}@example.com")
        assert r.status_code == 401
    assert (await _login(api_client, email="u21@example.com")).status_code == 429


async def test_login_rehashes_outdated_hash(
    api_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    await register(api_client)
    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(PW)
    assert needs_rehash(weak)
    await db.execute(text("update users set password_hash = :h"), {"h": weak})
    await db.commit()
    assert (await _login(api_client)).status_code == 200
    stored = (await db.execute(text("select password_hash from users"))).scalar_one()
    assert stored != weak
    assert not needs_rehash(stored)


async def test_session_endpoint(api_client: httpx.AsyncClient) -> None:
    created = (await register(api_client)).json()
    r = await api_client.get("/auth/session")
    assert r.status_code == 200
    assert r.json() == created


async def test_session_401_without_cookie(api_client: httpx.AsyncClient) -> None:
    r = await api_client.get("/auth/session")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "not_authenticated"


async def test_logout_invalidates_session(api_client: httpx.AsyncClient) -> None:
    await register(api_client)
    token = api_client.cookies[SESSION_COOKIE]
    headers = await auth_headers(api_client)
    r = await api_client.post("/auth/logout", headers=headers)
    assert r.status_code == 204
    api_client.cookies.set(SESSION_COOKIE, token)
    assert (await api_client.get("/auth/session")).status_code == 401


async def test_idle_expiry_via_api(api_client: httpx.AsyncClient, clock: FrozenClock) -> None:
    await register(api_client)
    clock.advance(days=7, seconds=1)
    assert (await api_client.get("/auth/session")).status_code == 401


async def test_delete_account_wrong_password_keeps_session(
    api_client: httpx.AsyncClient,
) -> None:
    await register(api_client)
    headers = await auth_headers(api_client)
    r = await api_client.request(
        "DELETE", "/auth/account", json={"password": "wrong-password-xx"}, headers=headers
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"
    assert (await api_client.get("/auth/session")).status_code == 200


async def test_delete_account_removes_rows_and_files(
    app: FastAPI,
    api_client: httpx.AsyncClient,
    file_store: LocalFileStore,
    db: AsyncSession,
) -> None:
    await register(api_client)
    user_id = (await db.execute(text("select id from users"))).scalar_one()
    key = uuid.uuid4().hex

    async def chunks() -> AsyncIterator[bytes]:
        yield b"%PDF-"

    await file_store.put(key, chunks())
    set_id = uuid.uuid4()
    await db.execute(
        text("insert into study_sets (id, user_id, title) values (:i, :u, 'T')"),
        {"i": set_id, "u": user_id},
    )
    await db.execute(
        text(
            "insert into documents (id, study_set_id, storage_key, original_filename, size_bytes,"
            " status) values (:i, :s, :k, 'a.pdf', 5, 'ready')"
        ),
        {"i": uuid.uuid4(), "s": set_id, "k": key},
    )
    await db.commit()
    headers = await auth_headers(api_client)
    r = await api_client.request("DELETE", "/auth/account", json={"password": PW}, headers=headers)
    assert r.status_code == 204
    for table in ("users", "auth_sessions", "study_sets", "documents"):
        assert (await db.execute(text(f"select count(*) from {table}"))).scalar_one() == 0  # noqa: S608
    with pytest.raises(FileNotFoundError):
        file_store.open(key)
    assert SESSION_COOKIE not in api_client.cookies
