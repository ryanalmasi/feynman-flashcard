import asyncio
import unicodedata

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

PASSWORD_MIN = 12
PASSWORD_MAX = 128

_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing-equalisation")


def normalize_password(raw: str) -> str:
    return unicodedata.normalize("NFKC", raw)


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hasher.hash, normalize_password(password))


def _verify(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, normalize_password(password))
    except (VerificationError, InvalidHashError):
        return False


async def verify_password(stored_hash: str, password: str) -> bool:
    return await asyncio.to_thread(_verify, stored_hash, password)


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


async def verify_dummy(password: str) -> None:
    """Burn the same time as a real verify, so unknown emails aren't detectable by timing."""
    await verify_password(_DUMMY_HASH, password)
