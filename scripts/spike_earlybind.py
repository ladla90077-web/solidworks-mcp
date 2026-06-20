"""Spike 3: does an on-the-fly .swb macro resolve early-bound SolidWorks types
and enum NAMES (which require type-library references)? Decides generator style.

Builds a real base extrude. SolidWorks must be running.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sw_mcp.com_worker import call  # noqa: E402
from sw_mcp.macro_runner import run_inline_vba  # noqa: E402
from sw_mcp.util import WORK_DIR  # noqa: E402

MARKER = (WORK_DIR / "spike_eb.txt").as_posix()

# Early-bound types + enum NAMES (needs SldWorks + swconst references).
EARLY = f"""Option Explicit
Dim swApp As SldWorks.SldWorks
Dim swModel As SldWorks.ModelDoc2
Dim swFeatMgr As SldWorks.FeatureManager
Dim swSketchMgr As SldWorks.SketchManager
Sub main()
    Dim tmpl As String
    Dim f As Integer
    Set swApp = Application.SldWorks
    tmpl = swApp.GetUserPreferenceStringValue(swUserPreferenceStringValue_e.swDefaultTemplatePart)
    Set swModel = swApp.NewDocument(tmpl, 0, 0, 0)
    Set swSketchMgr = swModel.SketchManager
    Set swFeatMgr = swModel.FeatureManager
    swModel.SketchManager.InsertSketch True
    swSketchMgr.CreateCenterRectangle 0, 0, 0, 0.05, 0.035, 0
    swModel.SketchManager.InsertSketch True
    swModel.ClearSelection2 True
    f = FreeFile
    Open "{MARKER}" For Output As #f
    Print #f, "early-bound-ok"
    Close #f
End Sub
"""


def _go(app):
    return run_inline_vba(app, EARLY, keep_file=True)


def main():
    marker = WORK_DIR / "spike_eb.txt"
    if marker.exists():
        marker.unlink()
    res = call(_go)
    print("run result:", res, flush=True)
    print("marker written:", marker.exists(),
          ("-> " + marker.read_text().strip()) if marker.exists() else "", flush=True)


if __name__ == "__main__":
    main()
