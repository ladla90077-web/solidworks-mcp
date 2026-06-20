"""Pytest fixtures. Integration tests need a reachable SolidWorks 2022;
they skip cleanly if it cannot be connected."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(scope="session")
def sw():
    """Yield a connected SolidWorks app (launching if needed) or skip."""
    from sw_mcp.com_worker import call
    from sw_mcp.sw_connection import SWConnection

    try:
        info = call(lambda app: SWConnection.get().info(), timeout=180)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"SolidWorks not available: {exc}")
    if not info.get("connected"):
        pytest.skip("SolidWorks did not connect")
    return info


@pytest.fixture(autouse=True)
def _close_docs(sw):
    """Close all documents after each test so accumulated open docs don't degrade
    SolidWorks (stale state caused intermittent selection/build failures)."""
    yield
    from sw_mcp.com_worker import call
    try:
        call(lambda app: app.CloseAllDocuments(True), timeout=60)
    except Exception:  # noqa: BLE001
        pass
