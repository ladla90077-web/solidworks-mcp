"""Spike 2b: RunMacro2 with a proper VARIANT byref to capture the error code,
and observe how a broken (won't-compile) macro is reported.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pythoncom  # noqa: E402
import win32com.client  # noqa: E402
from sw_mcp.sw_connection import SWConnection  # noqa: E402
from sw_mcp.util import WORK_DIR  # noqa: E402

MARKER = (WORK_DIR / "spike_marker2.txt").as_posix()

GOOD = f"""Option Explicit
Sub main()
    Dim f As Integer
    f = FreeFile
    Open "{MARKER}" For Output As #f
    Print #f, "good-ran"
    Close #f
End Sub
"""

# Compile error: references an undeclared var under Option Explicit + bad syntax.
BROKEN = """Option Explicit
Sub main()
    Dim x As Integer
    x = = 5  'syntax error
    y = 10    'undeclared (Option Explicit)
End Sub
"""


def run2(app, path: Path):
    err = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    try:
        ok = app.RunMacro2(str(path), "Module1", "main", 1, err)
        return ("ok", ok, err.value)
    except pythoncom.com_error as e:
        return ("com_error", e.args[:3], err.value)


def main():
    app = SWConnection.get().ensure(launch=False)
    marker = WORK_DIR / "spike_marker2.txt"

    for name, text in (("GOOD", GOOD), ("BROKEN", BROKEN)):
        if marker.exists():
            marker.unlink()
        p = WORK_DIR / f"spike2_{name}.swb"
        p.write_text(text, encoding="utf-8")
        result = run2(app, p)
        print(f"\n[{name}] RunMacro2 -> {result}", flush=True)
        print(f"  marker written: {marker.exists()}", flush=True)


if __name__ == "__main__":
    main()
