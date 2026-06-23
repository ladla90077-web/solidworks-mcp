"""COM connection to SolidWorks 2022.

Uses late binding (win32com Dispatch) so the server does not depend on a
generated type-library cache being present on the machine. Enum values are
passed as raw integers throughout the codebase for the same reason.
"""
from __future__ import annotations

import threading
import time
import re
from typing import Any, Optional

import pythoncom
import win32com.client
import win32com.client.dynamic

PROGID = "SldWorks.Application"
PROGID_VERSIONED = "SldWorks.Application.30"  # 2022 == major 30


def _as_dynamic_dispatch(raw: Any) -> Any:
    """Wrap ROT/GetActiveObject results as IDispatch before late binding.

    Some SOLIDWORKS installations return a bare PyIUnknown from the ROT.
    dynamic.Dispatch expects IDispatch and otherwise tries GetTypeInfo directly
    on PyIUnknown, which raises AttributeError.
    """
    candidate = getattr(raw, "_oleobj_", raw)
    if not hasattr(candidate, "GetTypeInfo"):
        candidate = candidate.QueryInterface(pythoncom.IID_IDispatch)
    return win32com.client.dynamic.Dispatch(candidate)


def _rev(app) -> Optional[str]:
    """RevisionNumber is exposed as a property under dynamic dispatch (no parens)."""
    try:
        val = app.RevisionNumber
        return val() if callable(val) else val  # tolerate both bindings
    except pythoncom.com_error:
        return None


class SolidWorksError(RuntimeError):
    pass


class SWConnection:
    """Process-wide handle to the SolidWorks application object.

    COM is apartment-threaded; every thread that touches the object must have
    called CoInitialize. We keep one app object and (re)initialise COM lazily
    per call via `ensure()`.
    """

    _instance: Optional["SWConnection"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._app: Any = None
        self._selected_pid: Optional[int] = None
        self._selected_moniker: Optional[str] = None

    @classmethod
    def get(cls) -> "SWConnection":
        with cls._lock:
            if cls._instance is None:
                cls._instance = SWConnection()
            return cls._instance

    # -- internal ----------------------------------------------------------
    @staticmethod
    def _co_init() -> None:
        try:
            pythoncom.CoInitialize()
        except pythoncom.com_error:
            pass  # already initialised on this thread

    def _enumerate_apps(self) -> list[tuple[int, str, Any]]:
        """Return every SOLIDWORKS instance registered in the Windows ROT."""
        found: dict[int, tuple[int, str, Any]] = {}
        try:
            rot = pythoncom.GetRunningObjectTable()
            enum = rot.EnumRunning()
            bind = pythoncom.CreateBindCtx(0)
            while True:
                monikers = enum.Next(1)
                if not monikers:
                    break
                moniker = monikers[0]
                try:
                    name = str(moniker.GetDisplayName(bind, None))
                except pythoncom.com_error:
                    continue
                match = re.search(r"(?:SolidWorks|SldWorks)_PID_(\d+)", name, re.I)
                if not match:
                    continue
                try:
                    app = _as_dynamic_dispatch(rot.GetObject(moniker))
                    pid = int(match.group(1))
                    actual = _safe(lambda: int(_value(app.GetProcessID)))
                    if actual:
                        pid = actual
                    found[pid] = (pid, name, app)
                except (pythoncom.com_error, AttributeError, ValueError, TypeError):
                    continue
        except pythoncom.com_error:
            pass

        # Older installations may expose only the generic active-object entry.
        if not found:
            app = self._attach_running()
            if app is not None:
                pid = _safe(lambda: int(_value(app.GetProcessID)))
                if pid:
                    found[pid] = (pid, f"SolidWorks_PID_{pid}", app)
        return sorted(found.values(), key=lambda item: item[0])

    def _attach_running(self) -> Any:
        """Attach to an already-running SolidWorks, or None if not running.

        Force dynamic dispatch so member binding (property vs. method) is
        deterministic regardless of any cached makepy wrappers on the machine.
        """
        for progid in (PROGID_VERSIONED, PROGID):
            try:
                raw = win32com.client.GetActiveObject(progid)
                return _as_dynamic_dispatch(raw)
            except (pythoncom.com_error, AttributeError):
                continue
        return None

    def _launch(self) -> Any:
        """Launch SolidWorks (or attach if Dispatch finds a running one)."""
        for progid in (PROGID_VERSIONED, PROGID):
            try:
                return win32com.client.dynamic.Dispatch(progid)
            except pythoncom.com_error:
                continue
        raise SolidWorksError(
            "Could not create SldWorks.Application. Is SolidWorks 2022 installed?"
        )

    # -- public ------------------------------------------------------------
    def ensure(self, launch: bool = False, visible: bool = True, timeout: float = 120.0) -> Any:
        """Return a live SldWorks app object, launching it if needed.

        `launch=False` only attaches to a running instance (never starts one).
        """
        self._co_init()
        if self._app is not None:
            if _rev(self._app) is not None:  # liveness probe
                return self._app
            self._app = None  # stale handle; reconnect below

        sessions = self._enumerate_apps()
        app = None
        moniker = None
        if self._selected_pid is not None:
            selected = next((item for item in sessions if item[0] == self._selected_pid), None)
            if selected:
                _, moniker, app = selected
            elif not launch:
                self._selected_pid = None
                self._selected_moniker = None
                raise SolidWorksError(
                    "The selected SOLIDWORKS session is no longer running. "
                    "Call sw_list_sessions, then sw_select_session."
                )
        elif len(sessions) == 1:
            self._selected_pid, moniker, app = sessions[0]
        elif len(sessions) > 1:
            pids = ", ".join(str(item[0]) for item in sessions)
            raise SolidWorksError(
                f"Multiple SOLIDWORKS sessions are running ({pids}). "
                "Call sw_select_session(process_id) before modeling."
            )
        if app is None and launch:
            app = self._launch()
        if app is None:
            raise SolidWorksError(
                "No active SOLIDWORKS session was found. Start SOLIDWORKS, then "
                "call sw_list_sessions and sw_select_session before modeling."
            )

        # Wait until the app is responsive (it may still be starting up).
        deadline = time.time() + timeout
        while _rev(app) is None:
            if time.time() > deadline:
                raise SolidWorksError("SolidWorks did not become responsive in time.")
            time.sleep(1.0)

        if visible:
            try:
                app.Visible = True
            except pythoncom.com_error:
                pass
        self._app = app
        self._selected_moniker = moniker or (
            f"SolidWorks_PID_{self._selected_pid}" if self._selected_pid else None
        )
        return app

    def list_sessions(self) -> list[dict]:
        """List running SOLIDWORKS processes without launching a new one."""
        self._co_init()
        sessions = []
        for pid, moniker, app in self._enumerate_apps():
            active = _safe(lambda: app.ActiveDoc)
            sessions.append({
                "process_id": pid,
                "moniker": moniker,
                "revision": _rev(app),
                "year": _rev_to_year(_rev(app)),
                "visible": _safe(lambda a=app: bool(a.Visible)),
                "active_document": _safe(lambda d=active: _value(d.GetPathName)) if active else None,
                "active_document_title": _safe(lambda d=active: _value(d.GetTitle)) if active else None,
                "selected": pid == self._selected_pid,
            })
        return sessions

    def select_session(self, process_id: int) -> dict:
        """Bind this MCP process to one exact SOLIDWORKS ROT session."""
        self._co_init()
        selected = next((item for item in self._enumerate_apps() if item[0] == int(process_id)), None)
        if selected is None:
            available = [item[0] for item in self._enumerate_apps()]
            raise SolidWorksError(
                f"SOLIDWORKS session {process_id} was not found. Available sessions: {available}"
            )
        self._selected_pid, self._selected_moniker, self._app = selected
        return self.info()

    def clear_selection(self) -> dict:
        previous = self._selected_pid
        self._app = None
        self._selected_pid = None
        self._selected_moniker = None
        return {"disconnected": True, "previous_process_id": previous}

    def session_status(self, auto_select_single: bool = True) -> dict:
        """Return an actionable session-first status without starting SOLIDWORKS."""
        sessions = self.list_sessions()
        if not sessions:
            self._app = None
            self._selected_pid = None
            return {
                "connected": False, "ready": False, "sessions": [],
                "action": "start_solidworks",
                "message": "Start SOLIDWORKS, then call sw_list_sessions.",
            }
        selected = next((item for item in sessions if item["selected"]), None)
        if selected is None and len(sessions) == 1 and auto_select_single:
            selected = self.select_session(sessions[0]["process_id"])
            sessions = self.list_sessions()
        if selected is None:
            return {
                "connected": False, "ready": False, "sessions": sessions,
                "action": "select_session",
                "message": "Choose a process_id with sw_select_session before modeling.",
            }
        info = self.info()
        return {**info, "ready": True, "action": None, "sessions": sessions}

    def info(self) -> dict:
        """Version / state summary used by the sw_status tool."""
        app = self.ensure(launch=False)
        rev = _rev(app)  # e.g. "30.1.0.82" for SW2022
        active = self.active_doc(required=False)
        return {
            "connected": True,
            "revision": rev,
            "year": _rev_to_year(rev),
            "visible": _safe(lambda: bool(app.Visible)),
            "process_id": _safe(lambda: int(_value(app.GetProcessID))),
            "moniker": self._selected_moniker,
            "active_document": _safe(lambda: _value(active.GetPathName)) if active else None,
        }

    def active_doc(self, required: bool = True) -> Any:
        app = self.ensure()
        doc = app.ActiveDoc
        if doc is None and required:
            raise SolidWorksError("No active document is open in SolidWorks.")
        return doc


def _rev_to_year(rev: Optional[str]) -> Optional[int]:
    """Map a major revision number to the marketing year (30 -> 2022)."""
    if not rev:
        return None
    try:
        major = int(str(rev).split(".")[0])
    except (ValueError, IndexError):
        return None
    return 1992 + major  # 30 -> 2022


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None


def _value(value):
    """Tolerate COM members exposed as either properties or zero-arg methods."""
    return value() if callable(value) else value
