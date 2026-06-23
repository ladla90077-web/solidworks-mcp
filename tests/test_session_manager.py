import pytest

from sw_mcp import sw_connection
from sw_mcp.sw_connection import SWConnection, SolidWorksError


@pytest.fixture(autouse=True)
def _close_docs():
    yield


class FakeApp:
    def __init__(self, pid, title=None):
        self.GetProcessID = pid
        self.RevisionNumber = "30.5.1"
        self.Visible = True
        self.ActiveDoc = None
        self.title = title


def test_bare_iunknown_is_promoted_to_idispatch(monkeypatch):
    dispatch = object()
    class BareUnknown:
        def QueryInterface(self, iid):
            assert iid == sw_connection.pythoncom.IID_IDispatch
            return dispatch
    monkeypatch.setattr(sw_connection.win32com.client.dynamic, "Dispatch", lambda value: value)
    assert sw_connection._as_dynamic_dispatch(BareUnknown()) is dispatch


def test_no_session_returns_start_action(monkeypatch):
    conn = SWConnection()
    monkeypatch.setattr(conn, "_enumerate_apps", lambda: [])
    status = conn.session_status()
    assert status["ready"] is False
    assert status["action"] == "start_solidworks"


def test_single_session_is_selected_automatically(monkeypatch):
    conn = SWConnection()
    app = FakeApp(101)
    monkeypatch.setattr(conn, "_enumerate_apps", lambda: [(101, "SolidWorks_PID_101", app)])
    status = conn.session_status()
    assert status["ready"] is True
    assert status["process_id"] == 101
    assert conn.ensure() is app


def test_multiple_sessions_require_explicit_selection(monkeypatch):
    conn = SWConnection()
    first, second = FakeApp(101), FakeApp(202)
    sessions = [(101, "SolidWorks_PID_101", first), (202, "SolidWorks_PID_202", second)]
    monkeypatch.setattr(conn, "_enumerate_apps", lambda: sessions)
    status = conn.session_status()
    assert status["action"] == "select_session"
    with pytest.raises(SolidWorksError, match="Multiple"):
        conn.ensure()
    selected = conn.select_session(202)
    assert selected["process_id"] == 202
    assert conn.ensure() is second
