"""Demonstrate the auto-fix loop primitive: a broken macro must fail with a
captured, structured error (no hang, no crash) so Claude can fix and re-run."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sw_mcp import server  # noqa: E402
from sw_mcp.util import new_work_path  # noqa: E402

LOG = str(new_work_path(".log")).replace("\\", "/")
BROKEN = f"""Option Explicit
Dim swApp As SldWorks.SldWorks
Dim swModel As SldWorks.ModelDoc2
Sub main()
    On Error GoTo Fail
    Dim f As Integer
    Set swApp = Application.SldWorks
    Set swModel = swApp.NewDocument(swApp.GetUserPreferenceStringValue(8), 0, 0, 0)
    f = FreeFile
    Open "{LOG}" For Append As #f
    Print #f, "OK|init|part created"
    Close #f
    ' BUG: method that does not exist -> runtime error
    swModel.ThisMethodDoesNotExist 123
    Exit Sub
Fail:
    f = FreeFile
    Open "{LOG}" For Append As #f
    Print #f, "ERROR|runtime|VBA error " & Err.Number & ": " & Err.Description
    Close #f
End Sub
"""


def main():
    # Inject our log path by also passing it through executor's reader: the
    # macro writes to LOG; run_and_verify reads whatever the macro wrote.
    import json

    from sw_mcp import executor
    from sw_mcp.com_worker import call

    res = call(lambda app: executor.run_inline_and_verify(app, BROKEN, log_path=LOG))
    print("success:", res["success"], "| ran:", res["ran"])
    print("log:")
    for s in res["log"]:
        print("  ", s["status"], s["step"], "-", s["message"])
    print("\nverdict keys:", sorted(res.keys()))


if __name__ == "__main__":
    main()
