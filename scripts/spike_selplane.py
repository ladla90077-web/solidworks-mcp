"""Test SelectStdPlane logic in isolation: log nFound and Select2 result."""
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
Dim gf As Integer
Sub main()
    Dim tmpl As String, feat As SldWorks.Feature, n As Long, b As Boolean
    Set swApp = Application.SldWorks
    tmpl = swApp.GetUserPreferenceStringValue(swUserPreferenceStringValue_e.swDefaultTemplatePart)
    Set swModel = swApp.NewDocument(tmpl, 0, 0, 0)
    gf = FreeFile
    Open "{LOG}" For Output As #gf
    Set feat = swModel.FirstFeature
    Do While Not feat Is Nothing
        If feat.GetTypeName2 = "RefPlane" Then
            n = n + 1
            If n = 2 Then
                b = feat.Select2(False, 0)
                Print #gf, "found plane #2 = " & feat.Name & " ; Select2=" & b
                Exit Do
            End If
        End If
        Set feat = feat.GetNextFeature
    Loop
    If n < 2 Then Print #gf, "only found " & n & " RefPlanes"
    Close #gf
End Sub
"""


def main():
    call(lambda app: run_inline_vba(app, CODE, keep_file=False))
    print(Path(LOG).read_text(encoding="utf-8", errors="replace"))


if __name__ == "__main__":
    main()
