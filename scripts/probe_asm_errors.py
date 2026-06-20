"""Probe the ACTIVE assembly: walk top features + one level of sub-features
(mates live as sub-features of the MateGroup), logging GetErrorCode2."""
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
Dim gf As Integer
Sub main()
    Dim feat As SldWorks.Feature, subf As SldWorks.Feature
    Set swApp = Application.SldWorks
    Set swModel = swApp.ActiveDoc
    gf = FreeFile
    Open "{LOG}" For Output As #gf
    If swModel Is Nothing Then Print #gf, "no active doc": Close #gf: Exit Sub
    Print #gf, "active: " & swModel.GetTitle & " type=" & swModel.GetType
    Dim isWarn As Boolean, ec As Long
    Set feat = swModel.FirstFeature
    Do While Not feat Is Nothing
        ec = feat.GetErrorCode2(isWarn)
        If ec <> 0 Or InStr(1, feat.GetTypeName2, "Mate", vbTextCompare) > 0 Then
            Print #gf, "TOP " & feat.Name & " | " & feat.GetTypeName2 & " | err=" & ec & " warn=" & isWarn
        End If
        Set subf = feat.GetFirstSubFeature
        Do While Not subf Is Nothing
            ec = subf.GetErrorCode2(isWarn)
            Print #gf, "  SUB " & subf.Name & " | " & subf.GetTypeName2 & " | err=" & ec & " warn=" & isWarn
            Set subf = subf.GetNextSubFeature
        Loop
        Set feat = feat.GetNextFeature
    Loop
    Close #gf
End Sub
"""

call(lambda app: macro_runner.run_inline_vba(app, CODE, keep_file=False))
print(Path(LOG).read_text(encoding="utf-8", errors="replace"))
