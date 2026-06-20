"""Convenience VBA generators.

Each builder emits a complete macro in the user's verified early-bound style
(ported from the solidworks-vba skill's core-patterns.md): Option Explicit,
module-level early-bound handles, dimensions as Const in metres, one Sub per
feature guarded by `buildFailed`, the SelectStdPlane / SelectLatestSketch
helpers, and SWMCP_Log calls (silent log) in place of blocking MsgBox.

The generated text is run via macro_runner.run_inline_vba; the server reads the
log file to report per-step status.
"""
from __future__ import annotations

from .util import VBA_DIR, mm

MODULE_DIMS = """Dim swApp As SldWorks.SldWorks
Dim swModel As SldWorks.ModelDoc2
Dim swModelExt As SldWorks.ModelDocExtension
Dim swSketchMgr As SldWorks.SketchManager
Dim swFeatMgr As SldWorks.FeatureManager
Dim swFeat As SldWorks.Feature
Dim boolstatus As Boolean
Dim buildFailed As Boolean"""

_INIT = """Sub main()
    On Error GoTo SWMCP_Fail
    buildFailed = False
    Set swApp = Application.SldWorks
    swApp.Visible = True
    Dim partTemplate As String
    partTemplate = swApp.GetUserPreferenceStringValue(swUserPreferenceStringValue_e.swDefaultTemplatePart)
    If partTemplate = "" Then
        SWMCP_Log "init", "ERROR", "No default part template set"
        Exit Sub
    End If
    Set swModel = swApp.NewDocument(partTemplate, 0, 0, 0)
    If swModel Is Nothing Then
        SWMCP_Log "init", "ERROR", "Could not create new part"
        Exit Sub
    End If
    Set swModelExt = swModel.Extension
    Set swSketchMgr = swModel.SketchManager
    Set swFeatMgr = swModel.FeatureManager
    SWMCP_Log "init", "OK", "Part created"
"""

_FOOTER = """    swModel.ClearSelection2 True
    swModel.ForceRebuild3 False
    swModel.ShowNamedView2 "*Isometric", -1
    swModel.ViewZoomtofit2
    SWMCP_Log "done", "OK", "Macro completed"
    Exit Sub
SWMCP_Fail:
    SWMCP_Log "runtime", "ERROR", "VBA error " & Err.Number & ": " & Err.Description
End Sub
"""


def _helpers() -> str:
    return (VBA_DIR / "helpers.vba").read_text(encoding="utf-8")


def _vba_path(p: str) -> str:
    """Forward-slash path is accepted by VBA Open and avoids backslash escaping."""
    return p.replace("\\", "/")


def assemble_part_macro(log_path: str, consts: list[str], calls: list[str],
                        subs: list[str]) -> str:
    """Compose a full part macro: header + main(init+calls+footer) + subs + helpers."""
    const_block = "\n".join(consts)
    call_block = "".join(
        f"    Call {c}\n    If buildFailed Then Exit Sub\n" for c in calls
    )
    header = (
        "Option Explicit\n\n"
        f"{MODULE_DIMS}\n\n"
        f'Const SWMCP_LOG_PATH As String = "{_vba_path(log_path)}"\n'
        f"{const_block}\n\n"
    )
    body = _INIT + call_block + _FOOTER
    return header + body + "\n" + "\n".join(subs) + "\n\n" + _helpers()


# --- Feature builders ------------------------------------------------------
def build_extrusion(length_mm: float, width_mm: float, height_mm: float,
                    plane: int, log_path: str) -> str:
    """Center-rectangle base + FeatureExtrusion3 (verified core-patterns recipe)."""
    consts = [
        f"Const PART_LENGTH As Double = {mm(length_mm)}   ' {length_mm} mm",
        f"Const PART_WIDTH As Double = {mm(width_mm)}    ' {width_mm} mm",
        f"Const PART_HEIGHT As Double = {mm(height_mm)}   ' {height_mm} mm",
    ]
    sub = f"""Sub CreateBase()
    Dim okSel As Boolean
    swModel.ClearSelection2 True
    okSel = SelectStdPlane({plane}, False, 0)   ' 1=Front 2=Top 3=Right
    If okSel = False Then   ' NOT "If Not okSel" - see helpers.vba bitwise note
        SWMCP_Log "base", "ERROR", "Could not select plane {plane}"
        buildFailed = True: Exit Sub
    End If
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    ' CreateCenterRectangle returns a Variant ARRAY of segments - capture as
    ' Variant (Set on a non-object raises 424 in an on-the-fly .swb).
    Dim vSegs As Variant
    vSegs = swSketchMgr.CreateCenterRectangle(0, 0, 0, PART_LENGTH / 2#, PART_WIDTH / 2#, 0)
    If IsArray(vSegs) = False Then
        SWMCP_Log "base", "ERROR", "Rectangle creation failed"
        swSketchMgr.AddToDB = False
        swSketchMgr.InsertSketch True
        buildFailed = True: Exit Sub
    End If
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If SelectLatestSketch() = False Then
        SWMCP_Log "base", "ERROR", "Could not reselect sketch"
        buildFailed = True: Exit Sub
    End If
    Set swFeat = swFeatMgr.FeatureExtrusion3(True, False, False, _
        swEndConditions_e.swEndCondBlind, swEndConditions_e.swEndCondBlind, _
        PART_HEIGHT, 0#, False, False, False, False, 0#, 0#, _
        False, False, False, False, True, True, True, _
        swStartConditions_e.swStartSketchPlane, 0#, False)
    If swFeat Is Nothing Then
        SWMCP_Log "base", "ERROR", "Base extrusion failed"
        buildFailed = True: Exit Sub
    End If
    SWMCP_Log "base", "OK", "Base extrude created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts, ["CreateBase"], [sub])


# --- Shared base block (X=len, Z=wid, Y=hgt; top face at y=BLK_HGT) --------
def _base_consts(length_mm: float, width_mm: float, height_mm: float) -> list[str]:
    return [
        f"Const BLK_LEN As Double = {mm(length_mm)}   ' X {length_mm} mm",
        f"Const BLK_WID As Double = {mm(width_mm)}   ' Z {width_mm} mm",
        f"Const BLK_HGT As Double = {mm(height_mm)}   ' Y {height_mm} mm",
    ]

_BASE_BLOCK_SUB = """Sub CreateBaseBlock()
    Dim okSel As Boolean
    Dim vSegs As Variant
    swModel.ClearSelection2 True
    okSel = SelectStdPlane(2, False, 0)   ' Top (XZ)
    If okSel = False Then
        SWMCP_Log "base", "ERROR", "Could not select Top plane"
        buildFailed = True: Exit Sub
    End If
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    ' CreateCornerRectangle returns a Variant array - capture, don't Set.
    vSegs = swSketchMgr.CreateCornerRectangle(-BLK_LEN / 2, -BLK_WID / 2, 0, BLK_LEN / 2, BLK_WID / 2, 0)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If IsArray(vSegs) = False Then
        SWMCP_Log "base", "ERROR", "Base rectangle failed"
        buildFailed = True: Exit Sub
    End If
    If SelectLatestSketch() = False Then
        SWMCP_Log "base", "ERROR", "Could not reselect base sketch"
        buildFailed = True: Exit Sub
    End If
    Set swFeat = swFeatMgr.FeatureExtrusion3(True, False, False, _
        swEndCondBlind, swEndCondBlind, BLK_HGT, 0, False, False, False, False, _
        0, 0, False, False, False, False, True, True, True, 0, 0, False)
    If swFeat Is Nothing Then
        SWMCP_Log "base", "ERROR", "Base block extrusion failed"
        buildFailed = True: Exit Sub
    End If
    swFeat.Name = "Base_Block"
    SWMCP_Log "base", "OK", "Base block created"
    swModel.ClearSelection2 True
End Sub"""


def build_fillet(length_mm: float, width_mm: float, height_mm: float,
                 radius_mm: float, log_path: str) -> str:
    """Base block + edge fillet on the 4 vertical edges (FeatureFillet3)."""
    consts = _base_consts(length_mm, width_mm, height_mm) + [
        f"Const FILLET_RAD As Double = {mm(radius_mm)}   ' {radius_mm} mm",
    ]
    sub = """Sub CreateFilletFeature()
    swModel.ClearSelection2 True
    Dim midY As Double: midY = BLK_HGT / 2
    Dim b As Boolean
    b = SelectEdgeAt(BLK_LEN / 2, midY, BLK_WID / 2, False, 1)
    b = SelectEdgeAt(-BLK_LEN / 2, midY, BLK_WID / 2, True, 1)
    b = SelectEdgeAt(BLK_LEN / 2, midY, -BLK_WID / 2, True, 1)
    b = SelectEdgeAt(-BLK_LEN / 2, midY, -BLK_WID / 2, True, 1)
    Dim radiiArray0 As Variant:      Dim radiis0 As Double
    Dim dist2Array0 As Variant:      Dim dists20 As Double
    Dim conicRhosArray0 As Variant:  Dim coniRhos0 As Double
    Dim setBackArray0 As Variant:    Dim setBacks0 As Double
    Dim pointArray0 As Variant:      Dim points0 As Double
    Dim pointDist2Array0 As Variant: Dim pointsDist20 As Double
    Dim pointRhoArray0 As Variant:   Dim pointsRhos0 As Double
    radiiArray0 = radiis0: dist2Array0 = dists20: conicRhosArray0 = coniRhos0
    setBackArray0 = setBacks0: pointArray0 = points0
    pointDist2Array0 = pointsDist20: pointRhoArray0 = pointsRhos0
    Set swFeat = swFeatMgr.FeatureFillet3(195, FILLET_RAD, FILLET_RAD, 0, 0, 0, 0, _
        (radiiArray0), (dist2Array0), (conicRhosArray0), (setBackArray0), _
        (pointArray0), (pointDist2Array0), (pointRhoArray0))
    If swFeat Is Nothing Then
        SWMCP_Log "fillet", "ERROR", "Fillet failed - verify edge selection"
        buildFailed = True: Exit Sub
    End If
    swFeat.Name = "Fillet1"
    SWMCP_Log "fillet", "OK", "Fillet created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts,
                               ["CreateBaseBlock", "CreateFilletFeature"],
                               [_BASE_BLOCK_SUB, sub])


_SEED_HOLE_SUB = """Sub CreateSeedHole()
    Dim s As SldWorks.SketchSegment, b As Boolean
    swModel.ClearSelection2 True
    b = SelectFaceAt(SEED_X, BLK_HGT, SEED_Z, False, 0)   ' top face at seed point
    If b = False Then
        SWMCP_Log "seed", "ERROR", "Could not select top face": buildFailed = True: Exit Sub
    End If
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    Set s = swSketchMgr.CreateCircle(SEED_X, SEED_Z, 0, SEED_X + SEED_R, SEED_Z, 0)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If s Is Nothing Then
        SWMCP_Log "seed", "ERROR", "seed circle failed": buildFailed = True: Exit Sub
    End If
    If SelectLatestSketch() = False Then buildFailed = True: Exit Sub
    Set swFeat = swFeatMgr.FeatureCut4(True, False, False, _
        swEndCondThroughAll, swEndCondBlind, 0.01, 0#, False, False, False, False, _
        0#, 0#, False, False, False, False, False, True, True, True, True, False, _
        0#, 0#, False, False)
    If swFeat Is Nothing Then
        SWMCP_Log "seed", "ERROR", "seed cut failed": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "Seed"
    SWMCP_Log "seed", "OK", "seed hole created"
    swModel.ClearSelection2 True
End Sub"""


def build_pattern_linear(length_mm: float, width_mm: float, height_mm: float,
                         pitch_mm: float, count: int, log_path: str) -> str:
    """Block + a seed hole, linearly patterned along X (swFmLPattern)."""
    consts = _base_consts(length_mm, width_mm, height_mm) + [
        f"Const SEED_X As Double = {mm(-length_mm / 2 + 12)}",
        "Const SEED_Z As Double = 0",
        "Const SEED_R As Double = 0.004",
        f"Const PAT_PITCH As Double = {mm(pitch_mm)}   ' {pitch_mm} mm",
        f"Const PAT_COUNT As Long = {int(count)}",
    ]
    pat = """Sub CreateLinearPat()
    Dim patData As Object, seed As SldWorks.Feature, b As Boolean
    swModel.ClearSelection2 True
    Set seed = FindFeatureByName("Seed")
    If seed Is Nothing Then
        SWMCP_Log "pattern", "ERROR", "Seed missing": buildFailed = True: Exit Sub
    End If
    b = seed.Select2(False, 4)
    b = SelectStdPlane(3, True, 1)   ' Right plane normal = X direction, mark 1
    Set patData = swFeatMgr.CreateDefinition(swFmLPattern)
    patData.BodyPattern = False
    patData.D1EndCondition = 0
    patData.D1ReverseDirection = False
    patData.D1Spacing = PAT_PITCH
    patData.D1TotalInstances = PAT_COUNT
    patData.GeometryPattern = False
    patData.VarySketch = False
    Set swFeat = swFeatMgr.CreateFeature(patData)
    If swFeat Is Nothing Then
        ' Fallback: reverse the direction (the plane normal may point -X).
        swModel.ClearSelection2 True
        b = seed.Select2(False, 4): b = SelectStdPlane(3, True, 1)
        Set patData = swFeatMgr.CreateDefinition(swFmLPattern)
        patData.BodyPattern = False: patData.D1EndCondition = 0
        patData.D1ReverseDirection = True: patData.D1Spacing = PAT_PITCH
        patData.D1TotalInstances = PAT_COUNT
        patData.GeometryPattern = False: patData.VarySketch = False
        Set swFeat = swFeatMgr.CreateFeature(patData)
    End If
    If swFeat Is Nothing Then
        SWMCP_Log "pattern", "ERROR", "Linear pattern failed": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "LinearPattern1"
    SWMCP_Log "pattern", "OK", "Linear pattern created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts,
                               ["CreateBaseBlock", "CreateSeedHole", "CreateLinearPat"],
                               [_BASE_BLOCK_SUB, _SEED_HOLE_SUB, pat])


def build_pattern_mirror(length_mm: float, width_mm: float, height_mm: float,
                         log_path: str) -> str:
    """Block + a seed hole, mirrored about the Right plane (InsertMirrorFeature)."""
    consts = _base_consts(length_mm, width_mm, height_mm) + [
        f"Const SEED_X As Double = {mm(-length_mm / 4)}",
        "Const SEED_Z As Double = 0",
        "Const SEED_R As Double = 0.005",
    ]
    pat = """Sub CreateMirrorPat()
    Dim seed As SldWorks.Feature, b As Boolean
    swModel.ClearSelection2 True
    Set seed = FindFeatureByName("Seed")
    If seed Is Nothing Then
        SWMCP_Log "pattern", "ERROR", "Seed missing": buildFailed = True: Exit Sub
    End If
    b = SelectStdPlane(3, False, 2)   ' Right plane = mirror plane, mark 2
    b = seed.Select2(True, 1)
    Set swFeat = swFeatMgr.InsertMirrorFeature(False, False, False, False)
    If swFeat Is Nothing Then
        SWMCP_Log "pattern", "ERROR", "Mirror failed": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "Mirror1"
    SWMCP_Log "pattern", "OK", "Mirror created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts,
                               ["CreateBaseBlock", "CreateSeedHole", "CreateMirrorPat"],
                               [_BASE_BLOCK_SUB, _SEED_HOLE_SUB, pat])


def build_pattern_circular(diameter_mm: float, height_mm: float,
                           bolt_circle_mm: float, count: int, log_path: str) -> str:
    """Disc + central boss + a seed hole on a bolt circle, circular-patterned
    around the boss axis (swFmCirPattern)."""
    consts = [
        f"Const D_DIA As Double = {mm(diameter_mm)}   ' disc dia {diameter_mm} mm",
        f"Const D_HGT As Double = {mm(height_mm)}   ' {height_mm} mm",
        f"Const BOSS_R As Double = {mm(diameter_mm * 0.12)}",
        f"Const PCD_R As Double = {mm(bolt_circle_mm / 2)}",
        "Const HOLE_R As Double = 0.004",
        f"Const HOLE_COUNT As Long = {int(count)}",
    ]
    disc = """Sub CreateDisc()
    Dim s As SldWorks.SketchSegment
    swModel.ClearSelection2 True
    If SelectStdPlane(2, False, 0) = False Then buildFailed = True: Exit Sub
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    Set s = swSketchMgr.CreateCircleByRadius(0, 0, 0, D_DIA / 2)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If SelectLatestSketch() = False Then buildFailed = True: Exit Sub
    Set swFeat = swFeatMgr.FeatureExtrusion3(True, False, False, _
        swEndCondBlind, swEndCondBlind, D_HGT, 0, False, False, False, False, _
        0, 0, False, False, False, False, True, True, True, 0, 0, False)
    If swFeat Is Nothing Then
        SWMCP_Log "disc", "ERROR", "disc extrude": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "Disc"
    ' Central boss (provides the cylindrical axis for the circular pattern).
    swModel.ClearSelection2 True
    Dim b As Boolean: b = SelectFaceAt(0, D_HGT, 0, False, 0)
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    Set s = swSketchMgr.CreateCircleByRadius(0, 0, 0, BOSS_R)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If SelectLatestSketch() = False Then buildFailed = True: Exit Sub
    Set swFeat = swFeatMgr.FeatureExtrusion3(True, False, False, _
        swEndCondBlind, swEndCondBlind, D_HGT, 0, False, False, False, False, _
        0, 0, False, False, False, False, True, True, True, 0, 0, False)
    If swFeat Is Nothing Then
        SWMCP_Log "disc", "ERROR", "boss extrude": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "Boss"
    SWMCP_Log "disc", "OK", "disc + boss created"
    swModel.ClearSelection2 True
End Sub"""
    seed = """Sub CreateSeedHoleC()
    Dim s As SldWorks.SketchSegment, b As Boolean
    swModel.ClearSelection2 True
    b = SelectFaceAt(0, D_HGT, PCD_R, False, 0)   ' top face at the bolt-circle point
    If b = False Then
        SWMCP_Log "seed", "ERROR", "top face for seed": buildFailed = True: Exit Sub
    End If
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    Set s = swSketchMgr.CreateCircle(0, PCD_R, 0, HOLE_R, PCD_R, 0)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If SelectLatestSketch() = False Then buildFailed = True: Exit Sub
    Set swFeat = swFeatMgr.FeatureCut4(True, False, False, _
        swEndCondThroughAll, swEndCondBlind, 0.01, 0#, False, False, False, False, _
        0#, 0#, False, False, False, False, False, True, True, True, True, False, _
        0#, 0#, False, False)
    If swFeat Is Nothing Then
        SWMCP_Log "seed", "ERROR", "seed cut": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "Seed"
    SWMCP_Log "seed", "OK", "seed hole created"
    swModel.ClearSelection2 True
End Sub"""
    pat = """Sub CreateCircularPat()
    Const PI As Double = 3.14159265358979
    Dim patData As Object, seed As SldWorks.Feature, axisFace As SldWorks.Face2
    Dim ent As SldWorks.Entity, selData As SldWorks.SelectData, b As Boolean
    swModel.ClearSelection2 True
    Set seed = FindFeatureByName("Seed")
    Set axisFace = FindCylindricalFace(BOSS_R)
    If seed Is Nothing Or axisFace Is Nothing Then
        SWMCP_Log "pattern", "ERROR", "seed or axis face missing": buildFailed = True: Exit Sub
    End If
    b = seed.Select2(False, 4)
    Set selData = swModel.SelectionManager.CreateSelectData
    selData.Mark = 1
    Set ent = axisFace
    b = ent.Select4(True, selData)
    Set patData = swFeatMgr.CreateDefinition(swFmCirPattern)
    patData.BodyPattern = False
    patData.EqualSpacing = True
    patData.Spacing = 2# * PI
    patData.TotalInstances = HOLE_COUNT
    patData.GeometryPattern = False
    patData.VarySketch = False
    Set swFeat = swFeatMgr.CreateFeature(patData)
    If swFeat Is Nothing Then
        SWMCP_Log "pattern", "ERROR", "Circular pattern failed": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "CircularPattern1"
    SWMCP_Log "pattern", "OK", "Circular pattern created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts,
                               ["CreateDisc", "CreateSeedHoleC", "CreateCircularPat"],
                               [disc, seed, pat])


def build_hole_wizard(length_mm: float, width_mm: float, height_mm: float,
                      size: str, clear_dia_mm: float, cbore_dia_mm: float,
                      cbore_depth_mm: float, log_path: str) -> str:
    """Block + a Hole Wizard counterbore (metric socket-head cap screw) drilled
    through the top face at the center (HoleWizard5)."""
    consts = _base_consts(length_mm, width_mm, height_mm) + [
        f'Const HW_SIZE As String = "{size}"',
        f"Const HW_CLEAR As Double = {mm(clear_dia_mm)}   ' {clear_dia_mm} mm",
        f"Const HW_CBORE_DIA As Double = {mm(cbore_dia_mm)}   ' {cbore_dia_mm} mm",
        f"Const HW_CBORE_DEPTH As Double = {mm(cbore_depth_mm)}   ' {cbore_depth_mm} mm",
    ]
    sub = """Sub CreateHoleWizard()
    swModel.ClearSelection2 True
    Dim b As Boolean
    b = SelectFaceAt(0, BLK_HGT, 0, False, 0)   ' top face, center
    If b = False Then
        SWMCP_Log "hole", "ERROR", "Could not select top face": buildFailed = True: Exit Sub
    End If
    Set swFeat = swFeatMgr.HoleWizard5(swWzdCounterBore, _
        swStandardAnsiMetric, _
        swStandardAnsiMetricSocketHeadCapScrew, _
        HW_SIZE, swEndCondThroughAll, _
        HW_CLEAR, BLK_HGT, 0#, _
        HW_CBORE_DIA, HW_CBORE_DEPTH, 0#, 0#, _
        0#, 0#, 0#, 0#, 0#, 0#, _
        0#, 0#, _
        "", False, True, True, True, True, False)
    If swFeat Is Nothing Then
        SWMCP_Log "hole", "ERROR", "Hole Wizard failed": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "HoleWizard1"
    SWMCP_Log "hole", "OK", "Hole Wizard counterbore created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts,
                               ["CreateBaseBlock", "CreateHoleWizard"],
                               [_BASE_BLOCK_SUB, sub])


def build_chamfer(length_mm: float, width_mm: float, height_mm: float,
                  distance_mm: float, log_path: str) -> str:
    """Base block + 45 degree chamfer on the 4 vertical edges (InsertFeatureChamfer)."""
    consts = _base_consts(length_mm, width_mm, height_mm) + [
        f"Const CHAM_DIST As Double = {mm(distance_mm)}   ' {distance_mm} mm",
    ]
    sub = """Sub CreateChamferFeature()
    swModel.ClearSelection2 True
    Dim midY As Double: midY = BLK_HGT / 2
    Dim b As Boolean
    b = SelectEdgeAt(BLK_LEN / 2, midY, BLK_WID / 2, False, 1)
    b = SelectEdgeAt(-BLK_LEN / 2, midY, BLK_WID / 2, True, 1)
    b = SelectEdgeAt(BLK_LEN / 2, midY, -BLK_WID / 2, True, 1)
    b = SelectEdgeAt(-BLK_LEN / 2, midY, -BLK_WID / 2, True, 1)
    ' Angle-distance chamfer: Width=CHAM_DIST, Angle=45 deg (radians).
    Set swFeat = swFeatMgr.InsertFeatureChamfer(4, swChamferType_e.swChamferAngleDistance, _
        CHAM_DIST, 0.78539816, 0, 0, 0, 0)
    If swFeat Is Nothing Then
        SWMCP_Log "chamfer", "ERROR", "Chamfer failed - verify edge selection"
        buildFailed = True: Exit Sub
    End If
    swFeat.Name = "Chamfer1"
    SWMCP_Log "chamfer", "OK", "Chamfer created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts,
                               ["CreateBaseBlock", "CreateChamferFeature"],
                               [_BASE_BLOCK_SUB, sub])


def build_shell(length_mm: float, width_mm: float, height_mm: float,
                thickness_mm: float, log_path: str) -> str:
    """Base block + shell, removing the top face (InsertFeatureShell)."""
    consts = _base_consts(length_mm, width_mm, height_mm) + [
        f"Const SHELL_THK As Double = {mm(thickness_mm)}   ' {thickness_mm} mm",
    ]
    sub = """Sub CreateShellFeature()
    swModel.ClearSelection2 True
    Dim b As Boolean
    b = SelectFaceAt(0, BLK_HGT, 0, False, 1)   ' remove the top face
    If b = False Then
        SWMCP_Log "shell", "ERROR", "Could not select top face"
        buildFailed = True: Exit Sub
    End If
    swModel.InsertFeatureShell SHELL_THK, False
    Dim f As SldWorks.Feature
    Set f = FindLastFeatureByType("Shell")
    If f Is Nothing Then
        SWMCP_Log "shell", "ERROR", "Shell feature not created"
        buildFailed = True: Exit Sub
    End If
    f.Name = "Shell1"
    SWMCP_Log "shell", "OK", "Shell created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts,
                               ["CreateBaseBlock", "CreateShellFeature"],
                               [_BASE_BLOCK_SUB, sub])


def build_draft(length_mm: float, width_mm: float, height_mm: float,
                angle_deg: float, log_path: str) -> str:
    """Base block + draft on the 4 side faces (neutral plane = bottom face)."""
    consts = _base_consts(length_mm, width_mm, height_mm) + [
        f"Const DRAFT_ANG_DEG As Double = {angle_deg}   ' degrees",
    ]
    sub = """Sub CreateDraftFeature()
    swModel.ClearSelection2 True
    Dim b As Boolean
    Dim midY As Double: midY = BLK_HGT / 2
    b = SelectFaceAt(0, 0, 0, False, 1)            ' neutral plane = bottom face
    b = SelectFaceAt(BLK_LEN / 2, midY, 0, True, 2)
    b = SelectFaceAt(-BLK_LEN / 2, midY, 0, True, 2)
    b = SelectFaceAt(0, midY, BLK_WID / 2, True, 2)
    b = SelectFaceAt(0, midY, -BLK_WID / 2, True, 2)
    Dim ang As Double: ang = DRAFT_ANG_DEG * 0.01745329252
    Set swFeat = swFeatMgr.InsertMultiFaceDraft(ang, False, False, 0, False, False)
    If swFeat Is Nothing Then
        SWMCP_Log "draft", "ERROR", "Draft failed - verify face selection"
        buildFailed = True: Exit Sub
    End If
    swFeat.Name = "Draft1"
    SWMCP_Log "draft", "OK", "Draft created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts,
                               ["CreateBaseBlock", "CreateDraftFeature"],
                               [_BASE_BLOCK_SUB, sub])


def build_rib(length_mm: float, depth_mm: float, height_mm: float,
              thickness_mm: float, log_path: str) -> str:
    """L-bracket (plate + perpendicular wall) + a gusset rib bridging the inner
    corner. A rib needs walls to bridge - it cannot form above a flat block.

    length=X span, depth=plate reach in +Z, height=wall reach in +Y,
    thickness=plate/wall/rib thickness."""
    consts = [
        f"Const LB_LEN As Double = {mm(length_mm)}   ' X {length_mm} mm",
        f"Const LB_DEPTH As Double = {mm(depth_mm)}   ' Z plate {depth_mm} mm",
        f"Const LB_HEIGHT As Double = {mm(height_mm)}   ' Y wall {height_mm} mm",
        f"Const LB_THK As Double = {mm(thickness_mm)}   ' {thickness_mm} mm",
    ]
    bracket = """Sub CreateLBracket()
    Dim vSegs As Variant
    ' --- Plate on Top plane: X[-L/2,L/2], Z[0,DEPTH], extruded up THK ---
    swModel.ClearSelection2 True
    If SelectStdPlane(2, False, 0) = False Then
        SWMCP_Log "bracket", "ERROR", "Top plane": buildFailed = True: Exit Sub
    End If
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    vSegs = swSketchMgr.CreateCornerRectangle(-LB_LEN / 2, 0, 0, LB_LEN / 2, LB_DEPTH, 0)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If IsArray(vSegs) = False Then
        SWMCP_Log "bracket", "ERROR", "plate rect": buildFailed = True: Exit Sub
    End If
    If SelectLatestSketch() = False Then buildFailed = True: Exit Sub
    Set swFeat = swFeatMgr.FeatureExtrusion3(True, False, False, _
        swEndCondBlind, swEndCondBlind, LB_THK, 0, False, False, False, False, _
        0, 0, False, False, False, False, True, True, True, 0, 0, False)
    If swFeat Is Nothing Then
        SWMCP_Log "bracket", "ERROR", "plate extrude": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "Plate"
    ' --- Wall on Front plane: X[-L/2,L/2], Y[0,HEIGHT], extruded +Z by THK ---
    swModel.ClearSelection2 True
    If SelectStdPlane(1, False, 0) = False Then
        SWMCP_Log "bracket", "ERROR", "Front plane": buildFailed = True: Exit Sub
    End If
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    vSegs = swSketchMgr.CreateCornerRectangle(-LB_LEN / 2, 0, 0, LB_LEN / 2, LB_HEIGHT, 0)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If IsArray(vSegs) = False Then
        SWMCP_Log "bracket", "ERROR", "wall rect": buildFailed = True: Exit Sub
    End If
    If SelectLatestSketch() = False Then buildFailed = True: Exit Sub
    Set swFeat = swFeatMgr.FeatureExtrusion3(True, False, False, _
        swEndCondBlind, swEndCondBlind, LB_THK, 0, False, False, False, False, _
        0, 0, False, False, False, False, True, True, True, 0, 0, False)
    If swFeat Is Nothing Then
        SWMCP_Log "bracket", "ERROR", "wall extrude": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "Wall"
    SWMCP_Log "bracket", "OK", "L-bracket created"
    swModel.ClearSelection2 True
End Sub"""
    rib = """Sub CreateRibFeature()
    swModel.ClearSelection2 True
    Dim s1 As SldWorks.SketchSegment
    ' Gusset = closed triangle in the Right (YZ) plane bridging the inner corner
    ' (y=THK,z=THK) up the wall (z=THK) and along the plate (y=THK), extruded
    ' thin in X. This is the reliable equivalent of a rib feature - the API
    ' InsertRib silently no-ops on programmatic sketches (see learned rule).
    If SelectStdPlane(3, False, 0) = False Then   ' Right (YZ)
        SWMCP_Log "rib", "ERROR", "Right plane": buildFailed = True: Exit Sub
    End If
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    ' Right-plane sketch local coords (u,v) map to model (Z = -u, Y = v).
    Set s1 = swSketchMgr.CreateLine(-LB_THK, LB_THK, 0, -LB_THK, 0.6 * LB_HEIGHT, 0)
    Set s1 = swSketchMgr.CreateLine(-LB_THK, 0.6 * LB_HEIGHT, 0, -0.6 * LB_DEPTH, LB_THK, 0)
    Set s1 = swSketchMgr.CreateLine(-0.6 * LB_DEPTH, LB_THK, 0, -LB_THK, LB_THK, 0)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If s1 Is Nothing Then
        SWMCP_Log "rib", "ERROR", "rib triangle": buildFailed = True: Exit Sub
    End If
    If SelectLatestSketch() = False Then buildFailed = True: Exit Sub
    ' Thin gusset: extrude both directions about the Right plane by LB_THK total.
    Set swFeat = swFeatMgr.FeatureExtrusion3(False, False, False, _
        swEndCondBlind, swEndCondBlind, LB_THK / 2, LB_THK / 2, False, False, False, False, _
        0, 0, False, False, False, False, True, True, True, 0, 0, False)
    If swFeat Is Nothing Then
        SWMCP_Log "rib", "ERROR", "Rib gusset extrude failed"
        buildFailed = True: Exit Sub
    End If
    swFeat.Name = "Rib1"
    SWMCP_Log "rib", "OK", "Rib (gusset) created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts,
                               ["CreateLBracket", "CreateRibFeature"],
                               [bracket, rib])


def build_thread(diameter_mm: float, height_mm: float, log_path: str) -> str:
    """A cylinder + a real (cut-sweep) Thread feature on its cylindrical face
    (CreateDefinition(swFmSweepThread)). Mirrors the verified official recipe:
    find the cylindrical face, take its two circular edges, thread between them."""
    consts = [
        f"Const TH_RADIUS As Double = {mm(diameter_mm / 2.0)}   ' dia {diameter_mm} mm",
        f"Const TH_HEIGHT As Double = {mm(height_mm)}   ' {height_mm} mm",
    ]
    cyl = """Sub CreateThreadCylinder()
    Dim swCircle As SldWorks.SketchSegment
    swModel.ClearSelection2 True
    If SelectStdPlane(2, False, 0) = False Then
        SWMCP_Log "thread", "ERROR", "Top plane": buildFailed = True: Exit Sub
    End If
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    Set swCircle = swSketchMgr.CreateCircleByRadius(0, 0, 0, TH_RADIUS)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If swCircle Is Nothing Then
        SWMCP_Log "thread", "ERROR", "cylinder circle": buildFailed = True: Exit Sub
    End If
    If SelectLatestSketch() = False Then buildFailed = True: Exit Sub
    Set swFeat = swFeatMgr.FeatureExtrusion3(True, False, False, _
        swEndCondBlind, swEndCondBlind, TH_HEIGHT, 0, False, False, False, False, _
        0, 0, False, False, False, False, True, True, True, 0, 0, False)
    If swFeat Is Nothing Then
        SWMCP_Log "thread", "ERROR", "cylinder extrude": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "Cylinder"
    SWMCP_Log "thread", "OK", "cylinder created"
    swModel.ClearSelection2 True
End Sub"""
    thr = """Sub CreateThreadFeature()
    Dim cylFeat As SldWorks.Feature, fAry As Variant, eachF As Variant
    Dim fc As SldWorks.Face2, srf As SldWorks.Surface, eds As Variant
    Dim e0 As SldWorks.Edge, e1 As SldWorks.Edge
    Dim selMgr As SldWorks.SelectionMgr, startE As SldWorks.Edge, endE As SldWorks.Edge
    Dim tData As Object, found As Boolean
    Set cylFeat = FindFeatureByName("Cylinder")
    If cylFeat Is Nothing Then
        SWMCP_Log "thread", "ERROR", "Cylinder feature missing": buildFailed = True: Exit Sub
    End If
    fAry = cylFeat.GetFaces
    For Each eachF In fAry
        Set fc = eachF
        Set srf = fc.GetSurface
        If srf.IsCylinder() Then
            eds = fc.GetEdges
            If Not IsEmpty(eds) Then
                If UBound(eds) >= 1 Then
                    Set e0 = eds(0): Set e1 = eds(1): found = True: Exit For
                End If
            End If
        End If
    Next
    If found = False Then
        SWMCP_Log "thread", "ERROR", "no cylindrical face/edges": buildFailed = True: Exit Sub
    End If
    Set selMgr = swModel.SelectionManager
    swModel.ClearSelection2 True
    Dim b As Boolean
    b = e0.Select4(False, Nothing)
    Set startE = selMgr.GetSelectedObject6(1, -1)
    swModel.ClearSelection2 True
    b = e1.Select4(False, Nothing)
    Set endE = selMgr.GetSelectedObject6(1, -1)
    swModel.ClearSelection2 True
    Set tData = swFeatMgr.CreateDefinition(swFeatureNameID_e.swFmSweepThread)
    If tData Is Nothing Then
        SWMCP_Log "thread", "ERROR", "thread definition failed": buildFailed = True: Exit Sub
    End If
    tData.InitializeThreadData
    tData.ThreadMethod = swThreadMethod_Cut
    tData.EndCondition = swThreadEndCondition_UpToSelection
    tData.Edge = startE
    tData.SetEndConditionReference endE
    Set swFeat = swFeatMgr.CreateFeature(tData)
    If swFeat Is Nothing Then
        SWMCP_Log "thread", "ERROR", "Thread feature failed (try swapping edges)": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "Thread1"
    SWMCP_Log "thread", "OK", "Thread feature created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts,
                               ["CreateThreadCylinder", "CreateThreadFeature"],
                               [cyl, thr])


def build_spring(coil_dia_mm: float, wire_dia_mm: float, pitch_mm: float,
                 revolutions: float, log_path: str) -> str:
    """Helix (InsertHelix) swept with a circular wire profile = a coil spring.
    Covers both the helix curve and the sweep-along-path."""
    consts = [
        f"Const SP_DIA As Double = {mm(coil_dia_mm)}   ' coil dia {coil_dia_mm} mm",
        f"Const SP_WIRE As Double = {mm(wire_dia_mm)}   ' wire dia {wire_dia_mm} mm",
        f"Const SP_PITCH As Double = {mm(pitch_mm)}   ' pitch {pitch_mm} mm",
        f"Const SP_REVS As Double = {revolutions}   ' revolutions",
    ]
    sub = """Sub CreateSpring()
    Dim swSweep As Object, sp As SldWorks.SketchSegment, b As Boolean
    Dim helixName As String, profileName As String
    ' Helix base circle on the Top plane (CreateCircle auto-opens the sketch;
    ' InsertHelix consumes it as the path).
    swModel.ClearSelection2 True
    If SelectStdPlane(2, False, 0) = False Then
        SWMCP_Log "spring", "ERROR", "Top plane": buildFailed = True: Exit Sub
    End If
    swModel.ClearSelection2 True
    Set sp = swSketchMgr.CreateCircle(0, 0, 0, SP_DIA / 2, 0, 0)
    ' InsertHelix is a Sub: Reversed, Clockwise, Tapered, Outward, DefinedBy,
    ' Height, Pitch, Revolutions, TaperAngle, StartAngle.
    swModel.InsertHelix False, True, False, False, _
        swHelixDefinedBy_e.swHelixDefinedByPitchAndRevolution, 0, SP_PITCH, SP_REVS, 0, 0
    swModel.ClearSelection2 True
    ' Wire profile circle on the Right plane at the helix start.
    If SelectStdPlane(3, False, 0) = False Then
        SWMCP_Log "spring", "ERROR", "Right plane": buildFailed = True: Exit Sub
    End If
    swModel.ClearSelection2 True
    Set sp = swSketchMgr.CreateCircle(SP_DIA / 2, 0, 0, SP_DIA / 2 + SP_WIRE / 2, 0, 0)
    swSketchMgr.InsertSketch True
    swModel.ClearSelection2 True
    helixName = FindFeatureNameByType("Helix")
    profileName = FindLastSketchName()
    If Len(helixName) = 0 Then
        SWMCP_Log "spring", "ERROR", "helix not found": buildFailed = True: Exit Sub
    End If
    ' Sweep: profile Mark=1, helix path (REFERENCECURVES) Mark=4.
    b = swModelExt.SelectByID2(profileName, "SKETCH", 0, 0, 0, True, 1, Nothing, 0)
    b = swModelExt.SelectByID2(helixName, "REFERENCECURVES", 0, 0, 0, True, 4, Nothing, 0)
    Set swSweep = swFeatMgr.CreateDefinition(swFeatureNameID_e.swFmSweep)
    Set swFeat = swFeatMgr.CreateFeature(swSweep)
    If swFeat Is Nothing Then
        SWMCP_Log "spring", "ERROR", "Sweep (spring) failed": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "Spring"
    SWMCP_Log "spring", "OK", "Spring (helix + sweep) created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts, ["CreateSpring"], [sub])


def build_sweep(length_mm: float, width_mm: float, height_mm: float,
                groove_dia_mm: float, log_path: str) -> str:
    """Base block + a swept cut: a straight path along the top face with a
    circular profile (CreateDefinition(swFmSweepCut), CircularProfile=True)."""
    consts = _base_consts(length_mm, width_mm, height_mm) + [
        f"Const SWEEP_DIA As Double = {mm(groove_dia_mm)}   ' groove dia {groove_dia_mm} mm",
    ]
    sub = """Sub CreateSweepFeature()
    Dim s As SldWorks.SketchSegment
    Dim swSweep As Object
    ' Path on the Front plane along +X, sitting on the top face (y=BLK_HGT).
    swModel.ClearSelection2 True
    If SelectStdPlane(1, False, 0) = False Then
        SWMCP_Log "sweep", "ERROR", "Front plane": buildFailed = True: Exit Sub
    End If
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    Set s = swSketchMgr.CreateLine(-BLK_LEN / 2 + 0.01, BLK_HGT, 0, BLK_LEN / 2 - 0.01, BLK_HGT, 0)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If s Is Nothing Then
        SWMCP_Log "sweep", "ERROR", "path line failed": buildFailed = True: Exit Sub
    End If
    RenameFeature FindLastSketchName(), "SweepPath"
    swModel.ClearSelection2 True
    ' Select path with Mark=4, build a circular-profile swept cut.
    Dim b As Boolean
    b = swModelExt.SelectByID2("SweepPath", "SKETCH", 0, 0, 0, False, 4, Nothing, 0)
    Set swSweep = swFeatMgr.CreateDefinition(swFeatureNameID_e.swFmSweepCut)
    If swSweep Is Nothing Then
        SWMCP_Log "sweep", "ERROR", "could not create sweep definition": buildFailed = True: Exit Sub
    End If
    swSweep.TangentPropagation = False
    swSweep.AlignWithEndFaces = True
    swSweep.TwistControlType = 0
    swSweep.MaintainTangency = False
    swSweep.AdvancedSmoothing = False
    swSweep.PathAlignmentType = 0
    swSweep.FeatureScope = True
    swSweep.AutoSelect = True
    swSweep.CircularProfile = True
    swSweep.CircularProfileDiameter = SWEEP_DIA
    Set swFeat = swFeatMgr.CreateFeature(swSweep)
    If swFeat Is Nothing Then
        SWMCP_Log "sweep", "ERROR", "Swept cut failed": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "SweptCut1"
    SWMCP_Log "sweep", "OK", "Swept cut created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts,
                               ["CreateBaseBlock", "CreateSweepFeature"],
                               [_BASE_BLOCK_SUB, sub])


def build_loft(length_mm: float, width_mm: float, height_mm: float,
               depth_mm: float, log_path: str) -> str:
    """Base block + a lofted cut: a rectangle profile on the top face blended
    down to a circle profile `depth` below it (two ref planes + InsertCutBlend)."""
    top_w = length_mm * 0.45
    top_h = width_mm * 0.45
    bot_r = min(length_mm, width_mm) * 0.12
    consts = _base_consts(length_mm, width_mm, height_mm) + [
        f"Const LOFT_W As Double = {mm(top_w)}",
        f"Const LOFT_H As Double = {mm(top_h)}",
        f"Const LOFT_R As Double = {mm(bot_r)}",
        f"Const LOFT_DEPTH As Double = {mm(depth_mm)}   ' {depth_mm} mm",
    ]
    sub = """Sub CreateLoftFeature()
    Dim swRP As Object, s As SldWorks.SketchSegment, b As Boolean
    Const C As Long = swRefPlaneReferenceConstraints_e.swRefPlaneReferenceConstraint_Distance
    ' Top ref plane at the top face.
    swModel.ClearSelection2 True
    If SelectStdPlane(2, False, 0) = False Then
        SWMCP_Log "loft", "ERROR", "Top plane": buildFailed = True: Exit Sub
    End If
    Set swRP = swFeatMgr.InsertRefPlane(C, BLK_HGT, 0, 0, 0, 0)
    If swRP Is Nothing Then
        SWMCP_Log "loft", "ERROR", "top ref plane": buildFailed = True: Exit Sub
    End If
    RenameFeature FindLastRefPlaneName(), "LoftTopPlane"
    swModel.ClearSelection2 True
    b = swModelExt.SelectByID2("LoftTopPlane", "PLANE", 0, 0, 0, False, 0, Nothing, 0)
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    swSketchMgr.CreateCornerRectangle -LOFT_W / 2, -LOFT_H / 2, 0, LOFT_W / 2, LOFT_H / 2, 0
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    RenameFeature FindLastSketchName(), "LoftTop"
    swModel.ClearSelection2 True
    ' Bottom ref plane depth below the top face + circle profile.
    If SelectStdPlane(2, False, 0) = False Then buildFailed = True: Exit Sub
    Set swRP = swFeatMgr.InsertRefPlane(C, BLK_HGT - LOFT_DEPTH, 0, 0, 0, 0)
    If swRP Is Nothing Then
        SWMCP_Log "loft", "ERROR", "bottom ref plane": buildFailed = True: Exit Sub
    End If
    RenameFeature FindLastRefPlaneName(), "LoftBotPlane"
    swModel.ClearSelection2 True
    b = swModelExt.SelectByID2("LoftBotPlane", "PLANE", 0, 0, 0, False, 0, Nothing, 0)
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    Set s = swSketchMgr.CreateCircleByRadius(0, 0, 0, LOFT_R)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    RenameFeature FindLastSketchName(), "LoftBot"
    swModel.ClearSelection2 True
    ' Select both profiles (mark 1) top -> bottom and cut-loft between them.
    b = swModelExt.SelectByID2("LoftTop", "SKETCH", 0, 0, 0, True, 1, Nothing, 0)
    b = swModelExt.SelectByID2("LoftBot", "SKETCH", 0, 0, 0, True, 1, Nothing, 0)
    Set swFeat = swFeatMgr.InsertCutBlend(False, True, True, 0.01, 0, 0, False, 0, 0, 0, True, True)
    If swFeat Is Nothing Then
        SWMCP_Log "loft", "ERROR", "Lofted cut failed": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "LoftedCut1"
    SWMCP_Log "loft", "OK", "Lofted cut created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts,
                               ["CreateBaseBlock", "CreateLoftFeature"],
                               [_BASE_BLOCK_SUB, sub])


# ===========================================================================
# Surface modeling generators (FeatureExtruRefSurface3, InsertPlanarRefSurface,
# InsertRevolvedRefSurface, FeatureBossThicken). Mirrors the pro surface
# workflow: build surfaces, then thicken/knit to a solid.
# ===========================================================================
def build_surface_extrude(length_mm: float, height_mm: float, log_path: str) -> str:
    """An open line sketched on the Top plane extruded into a flat surface
    (FeatureExtruRefSurface3, 22 args)."""
    consts = [
        f"Const SE_LEN As Double = {mm(length_mm)}   ' {length_mm} mm",
        f"Const SE_HGT As Double = {mm(height_mm)}   ' {height_mm} mm",
    ]
    sub = """Sub CreateSurfExtrude()
    Dim s As SldWorks.SketchSegment
    swModel.ClearSelection2 True
    If SelectStdPlane(2, False, 0) = False Then
        SWMCP_Log "surface", "ERROR", "Top plane": buildFailed = True: Exit Sub
    End If
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    Set s = swSketchMgr.CreateLine(-SE_LEN / 2, 0, 0, SE_LEN / 2, 0, 0)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If s Is Nothing Then
        SWMCP_Log "surface", "ERROR", "profile line": buildFailed = True: Exit Sub
    End If
    If SelectLatestSketch() = False Then buildFailed = True: Exit Sub
    ' IModelDoc2.FeatureExtruRefSurface2 is a Sub (17 args) - call as a statement,
    ' then grab the new surface feature from the tree.
    ' Sd, Flip, Dir, T1, T2, D1, D2, Dchk1, Dchk2, Ddir1, Ddir2, Dang1, Dang2,
    ' OffRev1, OffRev2, Trans1, Trans2
    swModel.FeatureExtruRefSurface2 True, False, False, _
        swEndCondBlind, swEndCondBlind, SE_HGT, 0, False, False, False, False, _
        0, 0, False, False, False, False
    Set swFeat = FindLastFeature()
    If swFeat Is Nothing Or swFeat.GetTypeName2 = "ProfileFeature" Then
        SWMCP_Log "surface", "ERROR", "Surface extrude failed": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "SurfExtrude1"
    SWMCP_Log "surface", "OK", "Extruded surface created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts, ["CreateSurfExtrude"], [sub])


def build_surface_planar(length_mm: float, width_mm: float, log_path: str) -> str:
    """A closed rectangle on the Front plane turned into a planar surface
    (InsertPlanarRefSurface)."""
    consts = [
        f"Const SP_L As Double = {mm(length_mm)}   ' {length_mm} mm",
        f"Const SP_W As Double = {mm(width_mm)}   ' {width_mm} mm",
    ]
    sub = """Sub CreateSurfPlanar()
    Dim s As SldWorks.SketchSegment
    swModel.ClearSelection2 True
    If SelectStdPlane(1, False, 0) = False Then
        SWMCP_Log "surface", "ERROR", "Front plane": buildFailed = True: Exit Sub
    End If
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    Set s = swSketchMgr.CreateLine(-SP_L / 2, -SP_W / 2, 0, SP_L / 2, -SP_W / 2, 0)
    Set s = swSketchMgr.CreateLine(SP_L / 2, -SP_W / 2, 0, SP_L / 2, SP_W / 2, 0)
    Set s = swSketchMgr.CreateLine(SP_L / 2, SP_W / 2, 0, -SP_L / 2, SP_W / 2, 0)
    Set s = swSketchMgr.CreateLine(-SP_L / 2, SP_W / 2, 0, -SP_L / 2, -SP_W / 2, 0)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If s Is Nothing Then
        SWMCP_Log "surface", "ERROR", "rectangle": buildFailed = True: Exit Sub
    End If
    If SelectLatestSketch() = False Then buildFailed = True: Exit Sub
    ' InsertPlanarRefSurface returns Boolean (not a Feature) - check it, then grab
    ' the new surface feature from the tree.
    If swModel.InsertPlanarRefSurface() = False Then
        SWMCP_Log "surface", "ERROR", "Planar surface failed": buildFailed = True: Exit Sub
    End If
    Set swFeat = FindLastFeature()
    swFeat.Name = "SurfPlanar1"
    SWMCP_Log "surface", "OK", "Planar surface created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts, ["CreateSurfPlanar"], [sub])


def build_surface_revolve(radius_mm: float, height_mm: float, log_path: str) -> str:
    """An open profile + centerline revolved into a surface (InsertRevolvedRefSurface)."""
    consts = [
        f"Const SR_R As Double = {mm(radius_mm)}   ' {radius_mm} mm",
        f"Const SR_H As Double = {mm(height_mm)}   ' {height_mm} mm",
    ]
    sub = """Sub CreateSurfRevolve()
    Const PI As Double = 3.14159265358979
    Dim s As SldWorks.SketchSegment
    swModel.ClearSelection2 True
    If SelectStdPlane(1, False, 0) = False Then
        SWMCP_Log "surface", "ERROR", "Front plane": buildFailed = True: Exit Sub
    End If
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    ' Open profile offset from the Y axis (a vertical line) + centerline on axis.
    Set s = swSketchMgr.CreateLine(SR_R, 0, 0, SR_R, SR_H, 0)
    Set s = swSketchMgr.CreateCenterLine(0, -0.01, 0, 0, SR_H + 0.01, 0)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If s Is Nothing Then
        SWMCP_Log "surface", "ERROR", "profile": buildFailed = True: Exit Sub
    End If
    If SelectLatestSketch() = False Then buildFailed = True: Exit Sub
    ' Angle, ReverseDir, Angle2, RevType
    Set swFeat = swFeatMgr.InsertRevolvedRefSurface(2# * PI, False, 0, 0)
    If swFeat Is Nothing Then
        SWMCP_Log "surface", "ERROR", "Surface revolve failed": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "SurfRevolve1"
    SWMCP_Log "surface", "OK", "Revolved surface (cylinder) created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts, ["CreateSurfRevolve"], [sub])


def build_surface_thicken(length_mm: float, height_mm: float,
                          thickness_mm: float, log_path: str) -> str:
    """Pro surface->solid pipeline: extrude a surface, then Thicken it into a
    solid (FeatureBossThicken with FillVolume)."""
    consts = [
        f"Const ST_LEN As Double = {mm(length_mm)}",
        f"Const ST_HGT As Double = {mm(height_mm)}",
        f"Const ST_THK As Double = {mm(thickness_mm)}   ' {thickness_mm} mm",
    ]
    surf = """Sub CreateSurfExtrude()
    Dim s As SldWorks.SketchSegment
    swModel.ClearSelection2 True
    If SelectStdPlane(2, False, 0) = False Then
        SWMCP_Log "surface", "ERROR", "Top plane": buildFailed = True: Exit Sub
    End If
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    Set s = swSketchMgr.CreateLine(-ST_LEN / 2, 0, 0, ST_LEN / 2, 0, 0)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If SelectLatestSketch() = False Then buildFailed = True: Exit Sub
    ' FeatureExtruRefSurface2 is a Sub (17 args) - call as a statement.
    swModel.FeatureExtruRefSurface2 True, False, False, _
        swEndCondBlind, swEndCondBlind, ST_HGT, 0, False, False, False, False, _
        0, 0, False, False, False, False
    Set swFeat = FindLastFeature()
    If swFeat Is Nothing Or swFeat.GetTypeName2 = "ProfileFeature" Then
        SWMCP_Log "surface", "ERROR", "surface extrude": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "SurfExtrude1"
    SWMCP_Log "surface", "OK", "surface created"
    swModel.ClearSelection2 True
End Sub"""
    thick = """Sub ThickenToSolid()
    swModel.ClearSelection2 True
    ' Thicken needs the surface BODY's face selected. Find the surface body and
    ' select its first face, then thicken into a solid (FillVolume=True).
    Dim swPart As SldWorks.PartDoc, vB As Variant, swBody As SldWorks.Body2
    Dim swFc As SldWorks.Face2, sd As SldWorks.SelectData
    Set swPart = swModel
    vB = swPart.GetBodies2(swSheetBody, True)   ' surface bodies are sheet bodies
    If IsEmpty(vB) Then
        SWMCP_Log "thicken", "ERROR", "no surface body": buildFailed = True: Exit Sub
    End If
    Set swBody = vB(0)
    Set swFc = swBody.GetFirstFace
    Set sd = swModel.SelectionManager.CreateSelectData
    swFc.Select4 False, sd
    ' FeatureBossThicken is a Sub with 3 args: Thickness, Direction
    ' (swThickenThicknessType_e), FaceIndex. Call as a statement.
    swModel.FeatureBossThicken ST_THK, 0, 0
    Set swFeat = FindLastFeature()
    If swFeat Is Nothing Or swFeat.GetTypeName2 = "ProfileFeature" Then
        SWMCP_Log "thicken", "ERROR", "Thicken failed": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "Thicken1"
    SWMCP_Log "thicken", "OK", "Surface thickened to solid"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts,
                               ["CreateSurfExtrude", "ThickenToSolid"],
                               [surf, thick])


# ===========================================================================
# Sheet metal generators (InsertSheetMetalBaseFlange2, InsertSheetMetalEdgeFlange2).
# ===========================================================================
def build_sheet_base_flange(length_mm: float, width_mm: float,
                            thickness_mm: float, bend_radius_mm: float,
                            log_path: str) -> str:
    """A closed rectangle turned into a flat sheet-metal plate
    (InsertSheetMetalBaseFlange2, 19 args, returns Feature). This is the base of
    every sheet-metal part; edge flanges/hems are then added to its edges."""
    consts = [
        f"Const SM_LEN As Double = {mm(length_mm)}   ' {length_mm} mm",
        f"Const SM_WID As Double = {mm(width_mm)}   ' {width_mm} mm",
        f"Const SM_THK As Double = {mm(thickness_mm)}   ' {thickness_mm} mm",
        f"Const SM_RAD As Double = {mm(bend_radius_mm)}   ' bend R {bend_radius_mm} mm",
    ]
    sub = """Sub CreateBaseFlange()
    Dim v As Variant
    swModel.ClearSelection2 True
    If SelectStdPlane(2, False, 0) = False Then
        SWMCP_Log "sheetmetal", "ERROR", "Top plane": buildFailed = True: Exit Sub
    End If
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    v = swSketchMgr.CreateCornerRectangle(-SM_LEN / 2, -SM_WID / 2, 0, SM_LEN / 2, SM_WID / 2, 0)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If IsArray(v) = False Then
        SWMCP_Log "sheetmetal", "ERROR", "base rectangle": buildFailed = True: Exit Sub
    End If
    If SelectLatestSketch() = False Then buildFailed = True: Exit Sub
    ' Mirrors the official VBA example exactly (DirToUse=1, UseDefaultRelief=False,
    ' ReliefType=2, non-zero relief, Merge=False, UseFeatScope=True). PCBA is an
    ' uninitialised Object (= Nothing), which the example also uses.
    Dim cba As Object
    Set swFeat = swFeatMgr.InsertSheetMetalBaseFlange2(SM_THK, False, SM_RAD, _
        0.02, 0.01, False, 0, 0, 1, cba, False, 2, 0.0001, 0.0001, 0.5, True, False, True, True)
    If swFeat Is Nothing Then
        SWMCP_Log "sheetmetal", "ERROR", "Base flange failed": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "BaseFlange1"
    SWMCP_Log "sheetmetal", "OK", "Sheet-metal base flange created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts, ["CreateBaseFlange"], [sub])


def build_sheet_lbracket(arm1_mm: float, arm2_mm: float, depth_mm: float,
                         thickness_mm: float, bend_radius_mm: float,
                         log_path: str) -> str:
    """A bent sheet-metal L-bracket from an OPEN L-profile + base flange. An open
    profile makes InsertSheetMetalBaseFlange2 extrude by ExtrudeDist and add a
    bend at the corner (the iconic one-feature bent part)."""
    consts = [
        f"Const SM_A1 As Double = {mm(arm1_mm)}   ' arm1 {arm1_mm} mm",
        f"Const SM_A2 As Double = {mm(arm2_mm)}   ' arm2 {arm2_mm} mm",
        f"Const SM_DEP As Double = {mm(depth_mm)}   ' depth {depth_mm} mm",
        f"Const SM_THK As Double = {mm(thickness_mm)}   ' {thickness_mm} mm",
        f"Const SM_RAD As Double = {mm(bend_radius_mm)}   ' bend R {bend_radius_mm} mm",
    ]
    sub = """Sub CreateLBracket()
    Dim s As SldWorks.SketchSegment, cba As Object
    swModel.ClearSelection2 True
    If SelectStdPlane(1, False, 0) = False Then   ' Front (XY)
        SWMCP_Log "sheetmetal", "ERROR", "Front plane": buildFailed = True: Exit Sub
    End If
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    ' Open L profile: a horizontal arm and a vertical arm sharing the origin.
    Set s = swSketchMgr.CreateLine(0, 0, 0, SM_A1, 0, 0)
    Set s = swSketchMgr.CreateLine(0, 0, 0, 0, SM_A2, 0)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If s Is Nothing Then
        SWMCP_Log "sheetmetal", "ERROR", "L profile": buildFailed = True: Exit Sub
    End If
    If SelectLatestSketch() = False Then buildFailed = True: Exit Sub
    ' Open profile -> ExtrudeDist1 = depth; bend added at the corner.
    Set swFeat = swFeatMgr.InsertSheetMetalBaseFlange2(SM_THK, False, SM_RAD, _
        SM_DEP, 0, False, 0, 0, 1, cba, False, 2, 0.0001, 0.0001, 0.5, True, False, True, True)
    If swFeat Is Nothing Then
        SWMCP_Log "sheetmetal", "ERROR", "L-bracket base flange failed": buildFailed = True: Exit Sub
    End If
    swFeat.Name = "BaseFlange1"
    SWMCP_Log "sheetmetal", "OK", "Sheet-metal L-bracket (bent) created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts, ["CreateLBracket"], [sub])


def build_assembly(part_path: str, asm_path: str, offset_mm: float,
                   log_path: str) -> str:
    """Self-contained assembly demo: build+save a part, create+save an assembly,
    insert two instances, and fully mate both with plane mates (AddComponent5 +
    AddMate5). Mirrors the verified assembly-mates recipe."""
    # SolidWorks document paths must be native Windows (backslash) and must
    # match exactly between SaveAs/OpenDoc6/AddComponent5 - forward slashes make
    # AddComponent5 return Nothing. Escape backslashes for the VBA string literal.
    pp = part_path.replace("/", "\\").replace("\\", "\\\\")
    ap = asm_path.replace("/", "\\").replace("\\", "\\\\")
    header = (
        "Option Explicit\n\n"
        "Dim swApp As SldWorks.SldWorks\n"
        "Dim swModel As SldWorks.ModelDoc2\n"
        "Dim swModelExt As SldWorks.ModelDocExtension\n"
        "Dim swAsm As SldWorks.AssemblyDoc\n"
        "Dim swComp As SldWorks.Component2\n"
        "Dim swMate As SldWorks.Mate2\n"
        "Dim swSketchMgr As SldWorks.SketchManager\n"
        "Dim swFeatMgr As SldWorks.FeatureManager\n"
        "Dim swFeat As SldWorks.Feature\n"
        "Dim boolstatus As Boolean\n"
        "Dim buildFailed As Boolean\n"
        "Dim asmTitle As String\n\n"
        f'Const SWMCP_LOG_PATH As String = "{_vba_path(log_path)}"\n'
        f'Const PART_PATH As String = "{pp}"\n'
        f'Const ASM_PATH As String = "{ap}"\n'
        "Const PART_T As Double = 0.01   ' part thickness 10 mm (stack distance)\n\n"
    )
    body = """Sub main()
    On Error GoTo SWMCP_Fail
    Dim c1 As SldWorks.Component2, c2 As SldWorks.Component2
    buildFailed = False
    Set swApp = Application.SldWorks
    swApp.Visible = True
    Call CreatePart
    If buildFailed Then Exit Sub
    Call CreateAssembly
    If buildFailed Then Exit Sub
    ' First component is auto-FIXED at the origin: do NOT mate it (mating a
    ' fixed component over-defines it -> the classic over-defined mate error).
    Set c1 = AddComponentToAssembly(PART_PATH, 0, 0, 0, "Base")
    ' Second component starts offset, then is fully constrained relative to c1.
    Set c2 = AddComponentToAssembly(PART_PATH, 0, 0.05, 0, "Second")
    If c1 Is Nothing Or c2 Is Nothing Then
        SWMCP_Log "asm", "ERROR", "component insertion failed": Exit Sub
    End If
    ' Stack c2 squarely on top of c1: align Front & Right planes (coincident),
    ' and separate the Top planes by one part thickness (distance). Three mates
    ' fully constrain c2 without over-defining anything.
    AddComponentMate c2, 1, c1, 1, swMateCOINCIDENT, 0, "FrontAlign"
    AddComponentMate c2, 3, c1, 3, swMateCOINCIDENT, 0, "RightAlign"
    AddComponentMate c2, 2, c1, 2, swMateDISTANCE, PART_T, "StackUp"
    swModel.ForceRebuild3 False
    Dim e As Long, w As Long
    boolstatus = swModelExt.SaveAs(ASM_PATH, 0, 1, Nothing, e, w)
    swModel.ShowNamedView2 "*Isometric", -1
    swModel.ViewZoomtofit2
    SWMCP_Log "done", "OK", "Assembly: 2 components, c2 stacked on c1 with 3 mates"
    Exit Sub
SWMCP_Fail:
    SWMCP_Log "runtime", "ERROR", "VBA error " & Err.Number & ": " & Err.Description
End Sub

Sub CreatePart()
    Dim tpl As String, vSegs As Variant, e As Long, w As Long
    tpl = swApp.GetUserPreferenceStringValue(swDefaultTemplatePart)
    If tpl = "" Then
        SWMCP_Log "asm", "ERROR", "no part template": buildFailed = True: Exit Sub
    End If
    Set swModel = swApp.NewDocument(tpl, 0, 0, 0)
    If swModel Is Nothing Then
        SWMCP_Log "asm", "ERROR", "part doc": buildFailed = True: Exit Sub
    End If
    Set swModelExt = swModel.Extension
    Set swSketchMgr = swModel.SketchManager
    Set swFeatMgr = swModel.FeatureManager
    swModel.ClearSelection2 True
    boolstatus = SelectStdPlane(2, False, 0)
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    vSegs = swSketchMgr.CreateCornerRectangle(-0.03, -0.02, 0, 0.03, 0.02, 0)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If SelectLatestSketch() = False Then buildFailed = True: Exit Sub
    Set swFeat = swFeatMgr.FeatureExtrusion3(True, False, False, _
        swEndCondBlind, swEndCondBlind, 0.01, 0, False, False, False, False, _
        0, 0, False, False, False, False, True, True, True, 0, 0, False)
    If swFeat Is Nothing Then
        SWMCP_Log "asm", "ERROR", "part extrude": buildFailed = True: Exit Sub
    End If
    boolstatus = swModelExt.SaveAs(PART_PATH, 0, 1, Nothing, e, w)
    If boolstatus = False Then
        SWMCP_Log "asm", "ERROR", "part save failed": buildFailed = True: Exit Sub
    End If
    SWMCP_Log "asm", "OK", "part created and saved"
    swApp.CloseDoc swModel.GetTitle
End Sub

Sub CreateAssembly()
    Dim tpl As String, e As Long, w As Long
    tpl = swApp.GetUserPreferenceStringValue(swDefaultTemplateAssembly)
    If tpl = "" Then
        SWMCP_Log "asm", "ERROR", "no assembly template": buildFailed = True: Exit Sub
    End If
    Set swModel = swApp.NewDocument(tpl, 0, 0, 0)
    If swModel Is Nothing Then
        SWMCP_Log "asm", "ERROR", "assembly doc": buildFailed = True: Exit Sub
    End If
    Set swModelExt = swModel.Extension
    boolstatus = swModelExt.SaveAs(ASM_PATH, 0, 1, Nothing, e, w)
    Set swAsm = swModel
    asmTitle = StripExt(swModel.GetTitle)
    SWMCP_Log "asm", "OK", "assembly created and saved"
End Sub

Function AddComponentToAssembly(ByVal filePath As String, _
    ByVal xPos As Double, ByVal yPos As Double, ByVal zPos As Double, _
    ByVal compName As String) As SldWorks.Component2
    Dim partDoc As SldWorks.ModelDoc2
    Dim e As Long, w As Long, ae As Long
    Set partDoc = swApp.GetOpenDocumentByName(filePath)
    If partDoc Is Nothing Then
        Set partDoc = swApp.OpenDoc6(filePath, swDocPART, swOpenDocOptions_Silent, "", e, w)
    End If
    If partDoc Is Nothing Then
        SWMCP_Log "asm", "ERROR", "could not open part": Exit Function
    End If
    ' Use the loaded doc's EXACT path so AddComponent5 matches the in-memory doc.
    Dim loadedPath As String
    loadedPath = partDoc.GetPathName
    Set swModel = swApp.ActivateDoc3(asmTitle, False, swDontRebuildActiveDoc, ae)
    If swModel Is Nothing Then
        SWMCP_Log "asm", "ERROR", "could not reactivate assembly ae=" & ae: Exit Function
    End If
    Set swAsm = swModel
    Set swModelExt = swModel.Extension
    Set swComp = swAsm.AddComponent5(loadedPath, _
        swAddComponentConfigOptions_CurrentSelectedConfig, "", False, "", xPos, yPos, zPos)
    If swComp Is Nothing Then
        Set swComp = swAsm.AddComponent4(loadedPath, "", xPos, yPos, zPos)
    End If
    If swComp Is Nothing Then
        SWMCP_Log "asm", "ERROR", "AddComponent failed": Exit Function
    End If
    swComp.Name2 = compName
    Set AddComponentToAssembly = swComp
End Function

Sub AddComponentMate(ByVal compA As SldWorks.Component2, ByVal idxA As Long, _
    ByVal compB As SldWorks.Component2, ByVal idxB As Long, _
    ByVal mateType As Long, ByVal offsetValue As Double, ByVal mateName As String)
    ' Mate compA's Nth plane to compB's Nth plane (both entities mark 1).
    Dim mateError As Long
    swModel.ClearSelection2 True
    If SelectComponentPlane(compA, idxA, False) = False Then
        SWMCP_Log "mate", "ERROR", "planeA " & mateName: Exit Sub
    End If
    If SelectComponentPlane(compB, idxB, True) = False Then
        SWMCP_Log "mate", "ERROR", "planeB " & mateName
        swModel.ClearSelection2 True: Exit Sub
    End If
    If mateType = swMateDISTANCE Then
        Set swMate = swAsm.AddMate5(swMateDISTANCE, swMateAlignALIGNED, (offsetValue < 0#), _
            Abs(offsetValue), Abs(offsetValue), Abs(offsetValue), _
            0#, 0#, 0#, 0#, 0#, False, False, 0, mateError)
    Else
        Set swMate = swAsm.AddMate5(swMateCOINCIDENT, swMateAlignALIGNED, False, _
            0#, 0#, 0#, 0#, 0#, 0#, 0#, 0#, False, False, 0, mateError)
    End If
    ' Authoritative success = a mate object was created. The ByRef ErrorStatus
    ' is unreliable in an inline .swb (returns 1 even on a valid mate), so it is
    ' only logged as info; true validity is confirmed by the post-rebuild
    ' GetErrorCode2 scan in the verdict (catches over-defined/conflicting mates).
    If swMate Is Nothing Then
        SWMCP_Log "mate", "ERROR", mateName & " not created (AddMate5 returned Nothing)"
    Else
        SWMCP_Log "mate", "OK", mateName & " created (status=" & mateError & ")"
    End If
    swModel.ClearSelection2 True
End Sub

Function SelectComponentPlane(ByVal comp As SldWorks.Component2, _
    ByVal planeIdx As Long, ByVal append As Boolean) As Boolean
    ' Select a COMPONENT-INSTANCE plane for mating (mark 1). With two instances
    ' of the same part, the part-feature tree-walk is ambiguous and AddMate5
    ' rejects it (err=1), so we use the component-qualified name string:
    '   "<Plane>@<ComponentName>@<AssemblyTitle>".
    Dim planeName As String, sel As String
    Select Case planeIdx
        Case 1: planeName = "Front Plane"
        Case 2: planeName = "Top Plane"
        Case 3: planeName = "Right Plane"
    End Select
    sel = planeName & "@" & comp.Name2 & "@" & asmTitle
    SelectComponentPlane = swModelExt.SelectByID2(sel, "PLANE", 0, 0, 0, append, 1, Nothing, 0)
    If SelectComponentPlane Then Exit Function
    ' Fallbacks: alternate name formats SolidWorks sometimes uses.
    sel = planeName & "@" & comp.Name2
    SelectComponentPlane = swModelExt.SelectByID2(sel, "PLANE", 0, 0, 0, append, 1, Nothing, 0)
End Function

Function StripExt(ByVal s As String) As String
    Dim p As Long
    p = InStrRev(s, ".")
    If p > 0 Then StripExt = Left(s, p - 1) Else StripExt = s
End Function

"""
    return header + body + _helpers()


def build_revolve(outer_dia_mm: float, inner_dia_mm: float, height_mm: float,
                  log_path: str) -> str:
    """Revolved tube: a rectangular profile offset from the Y axis on the Front
    plane, revolved 360 deg about a centerline (FeatureRevolve2)."""
    consts = [
        f"Const RO As Double = {mm(outer_dia_mm / 2.0)}   ' outer dia {outer_dia_mm} mm",
        f"Const RI As Double = {mm(inner_dia_mm / 2.0)}   ' inner dia {inner_dia_mm} mm",
        f"Const RH As Double = {mm(height_mm)}   ' height {height_mm} mm",
    ]
    sub = """Sub CreateRevolve()
    Const PI As Double = 3.14159265358979
    Dim s As SldWorks.SketchSegment
    swModel.ClearSelection2 True
    If SelectStdPlane(1, False, 0) = False Then   ' Front (XY)
        SWMCP_Log "revolve", "ERROR", "Front plane": buildFailed = True: Exit Sub
    End If
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    ' Closed rectangular profile offset from the axis: (RI,0)-(RO,0)-(RO,H)-(RI,H)
    Set s = swSketchMgr.CreateLine(RI, 0, 0, RO, 0, 0)
    Set s = swSketchMgr.CreateLine(RO, 0, 0, RO, RH, 0)
    Set s = swSketchMgr.CreateLine(RO, RH, 0, RI, RH, 0)
    Set s = swSketchMgr.CreateLine(RI, RH, 0, RI, 0, 0)
    ' Centerline on the Y axis (drawn last so it is not part of the loop).
    Set s = swSketchMgr.CreateCenterLine(0, -0.01, 0, 0, RH + 0.01, 0)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If s Is Nothing Then
        SWMCP_Log "revolve", "ERROR", "profile/centerline failed": buildFailed = True: Exit Sub
    End If
    If SelectLatestSketch() = False Then buildFailed = True: Exit Sub
    Set swFeat = swFeatMgr.FeatureRevolve2(True, True, False, False, False, False, _
        0, 0, 2# * PI, 0#, False, False, 0#, 0#, 0, 0#, 0#, True, True, True)
    If swFeat Is Nothing Then
        SWMCP_Log "revolve", "ERROR", "Revolve failed - profile must be a closed loop"
        buildFailed = True: Exit Sub
    End If
    swFeat.Name = "Revolve1"
    SWMCP_Log "revolve", "OK", "Revolve created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts, ["CreateRevolve"], [sub])


def build_cylinder(diameter_mm: float, height_mm: float, plane: int,
                   log_path: str) -> str:
    """Circle sketch + FeatureExtrusion3 -> a cylinder."""
    consts = [
        f"Const CYL_RADIUS As Double = {mm(diameter_mm / 2.0)}   ' dia {diameter_mm} mm",
        f"Const CYL_HEIGHT As Double = {mm(height_mm)}   ' {height_mm} mm",
    ]
    sub = f"""Sub CreateBase()
    Dim okSel As Boolean
    Dim swCircle As SldWorks.SketchSegment
    swModel.ClearSelection2 True
    okSel = SelectStdPlane({plane}, False, 0)
    If okSel = False Then
        SWMCP_Log "base", "ERROR", "Could not select plane {plane}"
        buildFailed = True: Exit Sub
    End If
    swSketchMgr.InsertSketch True
    swSketchMgr.AddToDB = True
    ' CreateCircleByRadius returns a single SketchSegment - Set is safe.
    Set swCircle = swSketchMgr.CreateCircleByRadius(0, 0, 0, CYL_RADIUS)
    swSketchMgr.AddToDB = False
    swSketchMgr.InsertSketch True
    If swCircle Is Nothing Then
        SWMCP_Log "base", "ERROR", "Circle creation failed"
        buildFailed = True: Exit Sub
    End If
    If SelectLatestSketch() = False Then
        SWMCP_Log "base", "ERROR", "Could not reselect sketch"
        buildFailed = True: Exit Sub
    End If
    Set swFeat = swFeatMgr.FeatureExtrusion3(True, False, False, _
        swEndConditions_e.swEndCondBlind, swEndConditions_e.swEndCondBlind, _
        CYL_HEIGHT, 0#, False, False, False, False, 0#, 0#, _
        False, False, False, False, True, True, True, _
        swStartConditions_e.swStartSketchPlane, 0#, False)
    If swFeat Is Nothing Then
        SWMCP_Log "base", "ERROR", "Cylinder extrusion failed"
        buildFailed = True: Exit Sub
    End If
    SWMCP_Log "base", "OK", "Cylinder created"
    swModel.ClearSelection2 True
End Sub"""
    return assemble_part_macro(log_path, consts, ["CreateBase"], [sub])
