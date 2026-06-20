"""A broken macro must fail with a captured, structured error - no hang/crash."""
from sw_mcp import executor
from sw_mcp.com_worker import call
from sw_mcp.util import new_work_path

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
    swModel.ThisMethodDoesNotExist 123
    Exit Sub
Fail:
    f = FreeFile
    Open "{LOG}" For Append As #f
    Print #f, "ERROR|runtime|VBA error " & Err.Number & ": " & Err.Description
    Close #f
End Sub
"""


def test_broken_macro_is_captured(sw):
    verdict = call(lambda app: executor.run_inline_and_verify(app, BROKEN, log_path=LOG))
    assert verdict["success"] is False
    assert verdict["log_errors"], "expected a captured runtime error"
    assert any("438" in s["message"] for s in verdict["log_errors"])
