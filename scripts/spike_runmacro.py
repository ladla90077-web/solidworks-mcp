"""Spike 2: determine what RunMacro2 accepts for inline execution.

Tests whether a *text* macro file (.swb / .swp / .bas) can be run, and how
RunMacro2 reports errors. SolidWorks must already be running.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pythoncom  # noqa: E402
from sw_mcp.sw_connection import SWConnection  # noqa: E402
from sw_mcp.util import WORK_DIR  # noqa: E402

MARKER = (WORK_DIR / "spike_marker.txt").as_posix()
MACRO_TEXT = f"""Option Explicit
Dim swApp As Object
Sub main()
    Set swApp = Application.SldWorks
    Dim f As Integer
    f = FreeFile
    Open "{MARKER}" For Output As #f
    Print #f, "spike-ok " & swApp.RevisionNumber
    Close #f
End Sub
"""


def try_run(app, path: Path):
    print(f"\n--- RunMacro2 on {path.name} ---", flush=True)
    forms = {
        "4-arg (omit ByRef Error)": lambda: app.RunMacro2(str(path), "Module1", "main", 1),
        "5-arg Missing": lambda: app.RunMacro2(str(path), "Module1", "main", 1, pythoncom.Missing),
        "RunMacro (legacy)": lambda: app.RunMacro(str(path), "Module1", "main"),
    }
    for label, fn in forms.items():
        try:
            res = fn()
            print(f"  [{label}] result: {res!r}", flush=True)
        except pythoncom.com_error as e:
            print(f"  [{label}] com_error: {e.args[:3]}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  [{label}] {type(e).__name__}: {e}", flush=True)


def main():
    conn = SWConnection.get()
    app = conn.ensure(launch=False)
    print("INFO:", conn.info(), flush=True)

    marker = WORK_DIR / "spike_marker.txt"
    for ext in (".swb", ".swp", ".bas"):
        if marker.exists():
            marker.unlink()
        p = WORK_DIR / f"spike_text{ext}"
        p.write_text(MACRO_TEXT, encoding="utf-8")
        try_run(app, p)
        print(f"  marker written: {marker.exists()}"
              + (f"  -> {marker.read_text().strip()!r}" if marker.exists() else ""),
              flush=True)


if __name__ == "__main__":
    main()
