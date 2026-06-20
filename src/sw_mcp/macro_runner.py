"""Run VBA macros in SolidWorks.

Two execution paths, both via ISldWorks::RunMacro2:
  * run_macro_file  - run an existing macro the user saved (.swp or .swb).
  * run_inline_vba  - write a VBA string to a temp .swb and run it. Verified in
    the spike: SolidWorks compiles and runs plain-text .swb macros on the fly,
    so no .swp authoring / VBIDE / "trust access to VBA project" is required.

All functions here are designed to be invoked on the COM worker thread
(they receive the live `app`). RunMacro2's ByRef error code is captured with a
VARIANT byref (the binding that worked in the spike).
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Optional

import pythoncom
import win32com.client

from .util import new_work_path

# swRunMacroError_e (subset). Note: VBA *compile/runtime* errors are NOT
# reported here - RunMacro2 simply returns False with code 0. They are detected
# via the silent log + feature-tree scan instead.
RUN_MACRO_ERROR = {
    0: "swRunMacroError_None",
    1: "swRunMacroError_DispatchError",
    2: "swRunMacroError_NotExist",
    3: "swRunMacroError_LaunchError",
}


def _run_macro2(app: Any, path: str, module: str, proc: str, unload: bool) -> tuple[bool, int]:
    """Call RunMacro2 with a proper VARIANT byref for the error code."""
    err = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    options = 1 if unload else 0  # 1 = swRunMacroUnloadAfterRun
    ok = bool(app.RunMacro2(path, module, proc, options, err))
    return ok, int(err.value or 0)


def run_macro_file(
    app: Any,
    path: str,
    module: str = "",
    proc: str = "main",
    unload: bool = True,
    watchdog: bool = True,
) -> dict:
    p = Path(path)
    if not p.exists():
        return {"ran": False, "run_error_code": 2,
                "run_error": "file not found", "macro_path": str(p)}
    # SolidWorks infers the module from the file when module == "".
    with _DialogWatchdog(app, enabled=watchdog):
        ok, code = _run_macro2(app, str(p), module, proc, unload)
    return {
        "ran": ok,
        "run_error_code": code,
        "run_error": RUN_MACRO_ERROR.get(code, f"code {code}"),
        "macro_path": str(p),
        "module": module or p.stem,
        "procedure": proc,
    }


def run_inline_vba(
    app: Any,
    code: str,
    proc: str = "main",
    module: str = "Module1",
    keep_file: bool = False,
    watchdog: bool = True,
) -> dict:
    """Write `code` to a temp .swb and run `proc`. Returns the run result plus
    the path to the generated macro (kept if keep_file or if it failed, so the
    user can inspect/repair it)."""
    swb = new_work_path(".swb")
    swb.write_text(code, encoding="utf-8")
    with _DialogWatchdog(app, enabled=watchdog):
        ok, ecode = _run_macro2(app, str(swb), module, proc, unload=True)
    result = {
        "ran": ok,
        "run_error_code": ecode,
        "run_error": RUN_MACRO_ERROR.get(ecode, f"code {ecode}"),
        "macro_path": str(swb),
        "module": module,
        "procedure": proc,
    }
    if ok and not keep_file:
        try:
            swb.unlink()
            result["macro_path"] = None
        except OSError:
            pass
    return result


class _DialogWatchdog:
    """Best-effort auto-dismiss of modal dialogs that would block a macro.

    RunMacro2 blocks the COM thread until any MsgBox / message dialog the macro
    raises is dismissed. This watchdog runs on a *separate* thread, finds modal
    dialogs owned by the SolidWorks process, and closes them so automation never
    deadlocks. It is intentionally conservative: only standard dialog windows
    (class #32770) belonging to the SW process, and only after a short grace
    period so legitimate fast dialogs are left alone.
    """

    def __init__(self, app: Any, enabled: bool = True, grace: float = 1.5) -> None:
        self.enabled = enabled
        self.grace = grace
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._pid: Optional[int] = None
        if enabled:
            try:
                self._pid = int(app.GetProcessID)
            except Exception:  # noqa: BLE001
                self._pid = None

    def __enter__(self) -> "_DialogWatchdog":
        if self.enabled and self._pid:
            self._thread = threading.Thread(target=self._loop, name="sw-dialog-watchdog",
                                            daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        try:
            import win32con
            import win32gui
            import win32process
        except ImportError:
            return
        time.sleep(self.grace)
        while not self._stop.is_set():
            try:
                for hwnd in _find_dialogs(win32gui):
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid == self._pid and win32gui.IsWindowVisible(hwnd):
                        # Close the dialog (equivalent to pressing the default/OK).
                        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:  # noqa: BLE001
                pass
            self._stop.wait(0.4)


def _find_dialogs(win32gui) -> list[int]:
    found: list[int] = []

    def _cb(hwnd, _):
        if win32gui.GetClassName(hwnd) == "#32770":  # standard dialog box class
            found.append(hwnd)
        return True

    win32gui.EnumWindows(_cb, None)
    return found
