"""Dump feature name|type of a freshly created part to debug plane selection."""
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
    Dim tmpl As String, feat As Object, f As Integer, n As Long
    Set swApp = Application.SldWorks
    tmpl = swApp.GetUserPreferenceStringValue(swUserPreferenceStringValue_e.swDefaultTemplatePart)
    Set swModel = swApp.NewDocument(tmpl, 0, 0, 0)
    f = FreeFile
    Open "{LOG}" For Output As #f
    Print #f, "active=" & swApp.ActiveDoc.GetTitle
    Set feat = swModel.FirstFeature
    Do While Not feat Is Nothing
        n = n + 1
        Print #f, n & "|" & feat.Name & "|" & feat.GetTypeName2
        Set feat = feat.GetNextFeature
        If n > 40 Then Exit Do
    Loop
    Close #f
End Sub
"""


def main():
    call(lambda app: run_inline_vba(app, CODE, keep_file=False))
    print(Path(LOG).read_text(encoding="utf-8", errors="replace"))


if __name__ == "__main__":
    main()
