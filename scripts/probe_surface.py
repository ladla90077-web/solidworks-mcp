"""Late-binding probe: which object+method actually creates a planar/extruded
surface and thickens it? Late binding avoids compile errors so we see runtime
reality (438 = method missing on that object)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sw_mcp import macro_runner  # noqa: E402
from sw_mcp.com_worker import call  # noqa: E402
from sw_mcp.util import new_work_path  # noqa: E402

LOG = str(new_work_path(".log")).replace("\\", "/")
CODE = f"""Option Explicit
Dim app As Object, model As Object, sk As Object, fm As Object
Dim gf As Integer
Sub LG(ByVal s As String)
    Print #gf, s
End Sub
Sub TryExtrude(ByVal label As String, ByVal obj As Object)
    On Error Resume Next
    Dim r As Object
    Set r = obj.FeatureExtruRefSurface2(True, False, False, 0, 0, 0.04, 0, False, False, False, False, 0, 0, False, False, False, False, False, False, False)
    LG label & " v2: err=" & Err.Number & " ok=" & (Not r Is Nothing)
    Err.Clear
    Set r = obj.FeatureExtruRefSurface3(True, False, 0, 0, 0, 0, 0.04, 0, False, False, False, False, 0, 0, False, False, False, False, False, False, False, False)
    LG label & " v3: err=" & Err.Number & " ok=" & (Not r Is Nothing)
    On Error GoTo 0
End Sub
Sub main()
    Set app = Application.SldWorks
    Set model = app.NewDocument(app.GetUserPreferenceStringValue(8), 0, 0, 0)
    Set fm = model.FeatureManager
    Set sk = model.SketchManager
    gf = FreeFile
    Open "{LOG}" For Output As #gf
    ' open-line sketch on front plane for extrude test
    model.Extension.SelectByID2 "Front Plane", "PLANE", 0, 0, 0, False, 0, Nothing, 0
    sk.InsertSketch True
    sk.CreateLine -0.05, 0, 0, 0.05, 0, 0
    sk.InsertSketch True
    ' select the sketch
    Dim feat As Object
    Set feat = model.FirstFeature
    Dim last As String
    Do While Not feat Is Nothing
        If feat.GetTypeName2 = "ProfileFeature" Then last = feat.Name
        Set feat = feat.GetNextFeature
    Loop
    model.Extension.SelectByID2 last, "SKETCH", 0, 0, 0, False, 0, Nothing, 0
    TryExtrude "model", model
    ' re-select and try via featuremanager
    model.Extension.SelectByID2 last, "SKETCH", 0, 0, 0, False, 0, Nothing, 0
    TryExtrude "featMgr", fm
    ' planar surface existence
    On Error Resume Next
    Dim p As Object
    model.Extension.SelectByID2 last, "SKETCH", 0, 0, 0, False, 0, Nothing, 0
    Set p = model.InsertPlanarRefSurface()
    LG "model.InsertPlanarRefSurface: err=" & Err.Number & " ok=" & (Not p Is Nothing)
    Err.Clear
    Set p = fm.InsertPlanarRefSurface()
    LG "fm.InsertPlanarRefSurface: err=" & Err.Number & " ok=" & (Not p Is Nothing)
    On Error GoTo 0
    Close #gf
End Sub
"""

call(lambda a: macro_runner.run_inline_vba(a, CODE, keep_file=False))
print(Path(LOG).read_text(encoding="utf-8", errors="replace"))
