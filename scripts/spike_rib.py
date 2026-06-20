"""Find an InsertRib parameter combo that actually forms a rib on a block."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sw_mcp import diagnostics, macro_runner  # noqa: E402
from sw_mcp.com_worker import call  # noqa: E402
from sw_mcp.feature_tools import _BASE_BLOCK_SUB, _base_consts, assemble_part_macro  # noqa: E402
from sw_mcp.util import new_work_path  # noqa: E402


def rib_sub(rev_mat: str, norm_to_sketch: str, two_sided: str):
    return f"""Sub CreateRibFeature()
    swModel.ClearSelection2 True
    Dim okSel As Boolean
    Dim swLineSeg As SldWorks.SketchSegment
    okSel = SelectStdPlane(1, False, 0)
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    Dim yRib As Double: yRib = BLK_HGT + 0.005
    Set swLineSeg = swSketchMgr.CreateLine(-BLK_LEN / 2 + 0.01, yRib, 0, BLK_LEN / 2 - 0.01, yRib, 0)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If SelectLatestSketch() = False Then buildFailed = True: Exit Sub
    swFeatMgr.InsertRib {two_sided}, False, RIB_THK, 0, {rev_mat}, False, False, 0, {norm_to_sketch}, False
    Dim f As SldWorks.Feature
    Set f = FindLastFeatureByType("Rib")
    If f Is Nothing Then
        SWMCP_Log "rib", "ERROR", "no rib (revMat={rev_mat} norm={norm_to_sketch} 2s={two_sided})"
    Else
        SWMCP_Log "rib", "OK", "RIB OK (revMat={rev_mat} norm={norm_to_sketch} 2s={two_sided}) type=" & f.GetTypeName2
    End If
End Sub"""


def test(rev_mat, norm, two_sided):
    consts = _base_consts(120, 80, 40) + ["Const RIB_THK As Double = 0.005"]
    lp = str(new_work_path(".log"))
    code = assemble_part_macro(lp, consts, ["CreateBaseBlock", "CreateRibFeature"],
                               [_BASE_BLOCK_SUB, rib_sub(rev_mat, norm, two_sided)])

    def go(app):
        macro_runner.run_inline_vba(app, code, keep_file=False)
        from sw_mcp.executor import read_log
        return read_log(lp)

    for s in call(go):
        if s["step"] == "rib":
            print(" ", s["status"], "-", s["message"])


for rev in ("False", "True"):
    for norm in ("False", "True"):
        test(rev, norm, "True")
