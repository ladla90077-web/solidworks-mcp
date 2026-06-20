"""COM connection to SolidWorks 2022.

Uses late binding (win32com Dispatch) so the server does not depend on a
generated type-library cache being present on the machine. Enum values are
passed as raw integers throughout the codebase for the same reason.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Optional

import pythoncom
import win32com.client
import win32com.client.dynamic

PROGID = "SldWorks.Application"
PROGID_VERSIONED = "SldWorks.Application.30"  # 2022 == major 30


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

    def _attach_running(self) -> Any:
        """Attach to an already-running SolidWorks, or None if not running.

        Force dynamic dispatch so member binding (property vs. method) is
        deterministic regardless of any cached makepy wrappers on the machine.
        """
        for progid in (PROGID_VERSIONED, PROGID):
            try:
                raw = win32com.client.GetActiveObject(progid)
                return win32com.client.dynamic.Dispatch(raw)
            except pythoncom.com_error:
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
    def ensure(self, launch: bool = True, visible: bool = True, timeout: float = 120.0) -> Any:
        """Return a live SldWorks app object, launching it if needed.

        `launch=False` only attaches to a running instance (never starts one).
        """
        self._co_init()
        if self._app is not None:
            if _rev(self._app) is not None:  # liveness probe
                return self._app
            self._app = None  # stale handle; reconnect below

        app = self._attach_running()
        if app is None and launch:
            app = self._launch()
        if app is None:
            raise SolidWorksError("SolidWorks is not running (launch=False).")

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
        return app

    def info(self) -> dict:
        """Version / state summary used by the sw_status tool."""
        app = self.ensure()
        rev = _rev(app)  # e.g. "30.1.0.82" for SW2022
        active = self.active_doc(required=False)
        return {
            "connected": True,
            "revision": rev,
            "year": _rev_to_year(rev),
            "visible": _safe(lambda: bool(app.Visible)),
            "process_id": _safe(lambda: int(app.GetProcessID)),
            "active_document": _safe(lambda: active.GetPathName) if active else None,
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
