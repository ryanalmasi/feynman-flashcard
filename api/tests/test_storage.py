import os
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


@pytest.mark.parametrize("key", ["../x", "a/b", "ABC", "", "0" * 31, "0" * 33, "../../etc/passwd"])
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
