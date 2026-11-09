import asyncio
import re
import uuid
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import BinaryIO, Protocol

from fastapi import Request

_KEY_RE = re.compile(r"[0-9a-f]{32}")


async def _uninterruptible[**P, T](func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """Run func in a thread; on cancellation wait for it to finish before re-raising.

    Guarantees no worker thread is still touching the file when put's cleanup runs.
    """
    task = asyncio.ensure_future(asyncio.to_thread(func, *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await asyncio.wait([task])
        raise


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
        """Write chunks to key, overwriting any existing file; cancellation-safe."""
        final = self._path(key)
        part = self._path(key, ".part")
        total = 0
        fh: BinaryIO | None = None
        renamed = False

        def open_part() -> None:
            nonlocal fh
            fh = part.open("wb")

        def write_part(chunk: bytes) -> None:
            if fh is not None:
                fh.write(chunk)

        def close_part() -> None:
            nonlocal fh
            if fh is not None:
                fh.close()
                fh = None

        def rename() -> None:
            nonlocal renamed
            part.replace(final)
            renamed = True

        def cleanup() -> None:
            try:
                close_part()
            finally:
                part.unlink(missing_ok=True)
                if renamed:
                    final.unlink(missing_ok=True)

        try:
            await _uninterruptible(open_part)
            async for chunk in chunks:
                await _uninterruptible(write_part, chunk)
                total += len(chunk)
            await _uninterruptible(close_part)
            await _uninterruptible(rename)
        except BaseException:
            await _uninterruptible(cleanup)
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
