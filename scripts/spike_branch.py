"""Minimal reproduction: does 'If Not okSel' really take the error branch
when okSel logs as True? Explicit Else logging settles it."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sw_mcp.com_worker import call  # noqa: E402
from sw_mcp.macro_runner import run_inline_vba  # noqa: E402
from sw_mcp.util import new_work_path  # noqa: E402

LOG = str(new_work_path(".log")).replace("\\", "/")
CODE = f"""Option Explicit
Dim swApp As SldWorks.SldWorks
Dim swModel As SldWorks.ModelDoc2
Sub main()
    Dim tmpl As String, okSel As Boolean
    Set swApp = Application.SldWorks
    tmpl = swApp.GetUserPreferenceStringValue(swUserPreferenceStringValue_e.swDefaultTemplatePart)
    Set swModel = swApp.NewDocument(tmpl, 0, 0, 0)
    swModel.ClearSelection2 True
    okSel = SelectStdPlane(2, False, 0)
    Lg "okSel=" & okSel & " ; CLng(okSel)=" & CLng(okSel) & " ; CLng(Not okSel)=" & CLng(Not okSel)
    If okSel = False Then
        Lg "ERROR BRANCH"
    Else
        Lg "OK BRANCH"
    End If
End Sub

Function SelectStdPlane(ByVal planeIndex As Long, ByVal appendSel As Boolean, ByVal markValue As Long) As Boolean
    Dim feat As SldWorks.Feature
    Dim nFound As Long
    Set feat = swModel.FirstFeature
    Do While Not feat Is Nothing
        If feat.GetTypeName2 = "RefPlane" Then
            nFound = nFound + 1
            If nFound = planeIndex Then
                SelectStdPlane = CBool(feat.Select2(appendSel, markValue))
                Lg "inside: set return = " & SelectStdPlane & " CLng=" & CLng(SelectStdPlane)
                Exit Function
            End If
        End If
        Set feat = feat.GetNextFeature
    Loop
    SelectStdPlane = False
End Function

Sub Lg(ByVal s As String)
    Dim f As Integer
    f = FreeFile
    Open "{LOG}" For Append As #f
    Print #f, s
    Close #f
End Sub
"""


def main():
    p = Path(LOG)
    if p.exists():
        p.unlink()
    call(lambda app: run_inline_vba(app, CODE, keep_file=False))
    print(p.read_text(encoding="utf-8", errors="replace"))


if __name__ == "__main__":
    main()
