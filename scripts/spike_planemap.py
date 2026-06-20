"""Determine the local->model coordinate mapping for the Right (YZ) plane."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sw_mcp import macro_runner  # noqa: E402
from sw_mcp.com_worker import call  # noqa: E402
from sw_mcp.util import new_work_path  # noqa: E402

LOG = str(new_work_path(".log")).replace("\\", "/")
CODE = f"""Option Explicit
Dim swApp As SldWorks.SldWorks
Dim swModel As SldWorks.ModelDoc2
Dim swSketchMgr As SldWorks.SketchManager
Function SelStd(ByVal i As Long) As Boolean
    Dim ft As SldWorks.Feature, n As Long
    Set ft = swModel.FirstFeature
    Do While Not ft Is Nothing
        If ft.GetTypeName2 = "RefPlane" Then
            n = n + 1
            If n = i Then SelStd = ft.Select2(False, 0): Exit Function
        End If
        Set ft = ft.GetNextFeature
    Loop
End Function
Sub main()
    Dim seg As SldWorks.SketchSegment, f As Integer, pts As Variant, k As Long
    Set swApp = Application.SldWorks
    Set swModel = swApp.NewDocument(swApp.GetUserPreferenceStringValue(8), 0, 0, 0)
    Set swSketchMgr = swModel.SketchManager
    Dim b As Boolean: b = SelStd(3)
    swSketchMgr.InsertSketch True
    Set seg = swSketchMgr.CreateLine(0.01, 0.02, 0, 0.03, 0.04, 0)
    f = FreeFile
    Open "{LOG}" For Output As #f
    If seg Is Nothing Then
        Print #f, "seg is nothing"
    Else
        pts = seg.GetSketchPoints2
        For k = 0 To UBound(pts)
            Print #f, "local-in (0.01,0.02)/(0.03,0.04) -> model pt" & k & "=(" & _
                Round(pts(k).X, 4) & "," & Round(pts(k).Y, 4) & "," & Round(pts(k).Z, 4) & ")"
        Next k
    End If
    Close #f
    swSketchMgr.InsertSketch True
End Sub
"""

call(lambda app: macro_runner.run_inline_vba(app, CODE, keep_file=False))
print(Path(LOG).read_text(encoding="utf-8", errors="replace"))
