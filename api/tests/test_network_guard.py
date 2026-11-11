import re
import socket
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

TESTS_DIR = Path(__file__).resolve().parent


def test_network_guard_blocks_external_connect() -> None:
    with pytest.raises(OSError, match="network access blocked"):
        socket.create_connection(("192.0.2.1", 80), timeout=0.1)  # TEST-NET-1, never routable


async def test_network_guard_allows_loopback(db: AsyncSession) -> None:
    assert (await db.execute(text("select 1"))).scalar_one() == 1


def test_allow_network_marker_used_only_by_live_test() -> None:
    found = {
        str(p.relative_to(TESTS_DIR.parent))
        for p in TESTS_DIR.rglob("*.py")
        if p.name not in {"conftest.py", "test_network_guard.py"}
        and re.search(r"allow_network", p.read_text())
    }
    assert found <= {"tests/llm/test_anthropic_live.py"}
