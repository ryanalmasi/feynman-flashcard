import asyncio
import re
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import BinaryIO, Protocol

from fastapi import Request

_KEY_RE = re.compile(r"[0-9a-f]{32}")


class InvalidStorageKey(ValueError):
    pass


def new_storage_key() -> str:
    return uuid.uuid4().hex


class FileStore(Protocol):
    async def put(self, key: str, chunks: AsyncIterator[bytes]) -> int:
        """Store the chunks under key; return bytes written. Removes partial data on failure."""
        ...

    def open(self, key: str) -> BinaryIO:
        """Open for reading (sync, for the worker). Raises FileNotFoundError."""
        ...

    async def delete(self, key: str) -> None:
        """Delete the file; a missing file is not an error."""
        ...


class LocalFileStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, key: str, suffix: str = "") -> Path:
        # Validate before any path is built.
        if not _KEY_RE.fullmatch(key):
            raise InvalidStorageKey("invalid storage key")
        return self._root / f"{key}{suffix}"

    async def put(self, key: str, chunks: AsyncIterator[bytes]) -> int:
        final = self._path(key)
        part = self._path(key, ".part")
        total = 0
        fh = await asyncio.to_thread(part.open, "wb")
        try:
            try:
                async for chunk in chunks:
                    await asyncio.to_thread(fh.write, chunk)
                    total += len(chunk)
            finally:
                await asyncio.to_thread(fh.close)
            await asyncio.to_thread(part.replace, final)
        except BaseException:
            await asyncio.to_thread(part.unlink, missing_ok=True)
            raise
        return total

    def open(self, key: str) -> BinaryIO:
        return self._path(key).open("rb")

    async def delete(self, key: str) -> None:
        path = self._path(key)
        await asyncio.to_thread(path.unlink, missing_ok=True)


def get_file_store(request: Request) -> FileStore:
    store: FileStore = request.app.state.file_store
    return store
