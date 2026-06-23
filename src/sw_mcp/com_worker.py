"""Single-threaded COM apartment worker.

SolidWorks COM objects are apartment-bound: an interface pointer obtained on
one thread cannot be safely used from another without marshalling. The MCP
server may dispatch tool calls from arbitrary threads, so we funnel *every*
SolidWorks interaction through one dedicated STA thread that owns the
connection for the life of the process.

Usage:
    from .com_worker import call
    info = call(lambda app: conn.info())          # runs on the COM thread
"""
from __future__ import annotations

import queue
import threading
import traceback
from typing import Any, Callable

import pythoncom

from .sw_connection import SWConnection


class _Task:
    __slots__ = ("fn", "needs_app", "result", "error", "done")

    def __init__(self, fn: Callable, needs_app: bool) -> None:
        self.fn = fn
        self.needs_app = needs_app
        self.result: Any = None
        self.error: BaseException | None = None
        self.done = threading.Event()


class ComWorker:
    _instance: "ComWorker | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._q: "queue.Queue[_Task | None]" = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="sw-com", daemon=True)
        self._started = False

    @classmethod
    def get(cls) -> "ComWorker":
        with cls._lock:
            if cls._instance is None:
                cls._instance = ComWorker()
                cls._instance._ensure_started()
            return cls._instance

    def _ensure_started(self) -> None:
        if not self._started:
            self._started = True
            self._thread.start()

    def _run(self) -> None:
        pythoncom.CoInitialize()  # STA apartment for this thread
        try:
            while True:
                task = self._q.get()
                if task is None:
                    break
                try:
                    if task.needs_app:
                        # Session-first contract: never silently launch or bind to
                        # an arbitrary process. A sole session is auto-selected;
                        # multiple sessions require sw_select_session.
                        app = SWConnection.get().ensure(launch=False)
                        task.result = task.fn(app)
                    else:
                        task.result = task.fn()
                except BaseException as exc:  # noqa: BLE001
                    exc._sw_tb = traceback.format_exc()  # type: ignore[attr-defined]
                    task.error = exc
                finally:
                    task.done.set()
        finally:
            pythoncom.CoUninitialize()

    def submit(self, fn: Callable, needs_app: bool, timeout: float | None) -> Any:
        task = _Task(fn, needs_app)
        self._q.put(task)
        if not task.done.wait(timeout):
            raise TimeoutError("SolidWorks COM call timed out (a modal dialog may be open).")
        if task.error is not None:
            raise task.error
        return task.result


def call(fn: Callable[..., Any], *, needs_app: bool = True, timeout: float | None = 300.0) -> Any:
    """Run `fn` on the COM thread. If needs_app, `fn(app)` receives the live
    SolidWorks application; otherwise `fn()` is called with no args.
    """
    return ComWorker.get().submit(fn, needs_app=needs_app, timeout=timeout)
