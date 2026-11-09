import asyncio
import os
import threading
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from asgi_lifespan import LifespanManager

from feynman_api.config import Settings
from feynman_api.main import create_app
from feynman_api.storage import InvalidStorageKey, LocalFileStore, new_storage_key


async def _chunks(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        yield part


async def test_put_open_delete_roundtrip(tmp_path: Path) -> None:
    store = LocalFileStore(tmp_path)
    key = new_storage_key()
    written = await store.put(key, _chunks(b"ab", b"cde", b"f"))
    assert written == 6
    with store.open(key) as fh:
        assert fh.read() == b"abcdef"
    await store.delete(key)
    with pytest.raises(FileNotFoundError):
        store.open(key)


async def test_delete_missing_is_noop(tmp_path: Path) -> None:
    await LocalFileStore(tmp_path).delete(new_storage_key())


@pytest.mark.parametrize(
    "key",
    [
        "../x",
        "a/b",
        "ABC",
        "",
        "0" * 31,
        "0" * 33,
        "../../etc/passwd",
        "0" * 32 + "\n",
        "\u0660" * 32,
    ],
)
async def test_rejects_non_uuid_hex_keys(tmp_path: Path, key: str) -> None:
    root = tmp_path / "root"
    root.mkdir()
    store = LocalFileStore(root)
    with pytest.raises(InvalidStorageKey):
        await store.put(key, _chunks(b"x"))
    with pytest.raises(InvalidStorageKey):
        store.open(key)
    with pytest.raises(InvalidStorageKey):
        await store.delete(key)
    assert os.listdir(root) == []
    assert os.listdir(tmp_path) == ["root"]


async def test_failed_put_leaves_no_file(tmp_path: Path) -> None:
    async def boom() -> AsyncIterator[bytes]:
        yield b"partial"
        raise RuntimeError("boom")

    store = LocalFileStore(tmp_path)
    with pytest.raises(RuntimeError, match="boom"):
        await store.put(new_storage_key(), boom())
    assert os.listdir(tmp_path) == []


async def test_app_creates_upload_dir(tmp_path: Path, test_settings: Settings) -> None:
    target = tmp_path / "u" / "nested"
    settings = test_settings.model_copy(update={"upload_dir": target})
    app = create_app(settings)
    async with LifespanManager(app):
        assert target.is_dir()
        assert isinstance(app.state.file_store, LocalFileStore)


async def test_cancelled_put_leaves_no_file(tmp_path: Path) -> None:
    started = asyncio.Event()

    async def stall() -> AsyncIterator[bytes]:
        yield b"partial"
        started.set()
        await asyncio.Event().wait()

    store = LocalFileStore(tmp_path)
    task = asyncio.create_task(store.put(new_storage_key(), stall()))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert os.listdir(tmp_path) == []


async def test_put_replace_oserror_leaves_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(self: Path, target: Path) -> Path:
        raise OSError("disk says no")

    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(OSError, match="disk says no"):
        await LocalFileStore(tmp_path).put(new_storage_key(), _chunks(b"x"))
    assert os.listdir(tmp_path) == []


async def test_cancel_during_replace_leaves_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered = threading.Event()
    release = threading.Event()
    real_replace = Path.replace

    def slow(self: Path, target: Path) -> Path:
        result = real_replace(self, target)
        entered.set()
        release.wait(5)
        return result

    monkeypatch.setattr(Path, "replace", slow)
    task = asyncio.create_task(LocalFileStore(tmp_path).put(new_storage_key(), _chunks(b"x")))
    assert await asyncio.to_thread(entered.wait, 5)
    task.cancel()
    asyncio.get_running_loop().call_later(0.1, release.set)
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0.3)  # let the worker thread finish its rename, if any
    assert os.listdir(tmp_path) == []
