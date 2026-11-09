from argon2 import PasswordHasher

from feynman_api.auth.passwords import (
    hash_password,
    needs_rehash,
    normalize_password,
    verify_dummy,
    verify_password,
)

PHRASE = "correct horse battery"


async def test_hash_and_verify() -> None:
    h = await hash_password(PHRASE)
    assert h.startswith("$argon2id$")
    assert await verify_password(h, PHRASE)
    assert not await verify_password(h, "wrong")


async def test_nfkc_normalisation() -> None:
    h = await hash_password(normalize_password("ﬁ" * 12))
    assert await verify_password(h, normalize_password("fi" * 12))


def test_needs_rehash_detects_old_params() -> None:
    old = PasswordHasher(time_cost=1).hash(PHRASE)
    assert needs_rehash(old)
    assert not needs_rehash(PasswordHasher().hash(PHRASE))


async def test_verify_invalid_hash_returns_false() -> None:
    assert not await verify_password("not-a-hash", PHRASE)
    assert not await verify_password("", PHRASE)


async def test_verify_dummy_runs() -> None:
    await verify_dummy(PHRASE)
