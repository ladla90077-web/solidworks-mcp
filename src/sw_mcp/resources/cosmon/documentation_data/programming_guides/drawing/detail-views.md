---
description: Create a detail view from an existing drawing view via the SolidWorks API. Covers circular and rectangular (profile) boundaries, the sketch-vs-sheet coordinate split, safe placement, cleanup of both view and boundary, and where/when to place a detail.
---

# Guide: Create a Detail View From Another View

> One `IDrawingDoc::CreateDetailViewAt4` call spawns a detail view from a closed boundary sketched in a source view; use it to magnify a small or crowded feature. The same call handles circular and rectangular (profile) boundaries — only the boundary you sketch and the `Showtype` enum change.

## Recipe (happy path)

1. Pick the **source view** to detail off, and call `ActivateView("<source>")` so the boundary lands in its sketch — see [How to: circular](#how-to-circular-detail-view) / [rectangular](#how-to-rectangular-profile-detail-view).
2. Sketch a closed boundary in the source view's **sketch space** (`CreateCircle` for circular, `CreateCenterRectangle` / `CreateCornerRectangle` / 4×`CreateLine` for profile) — coordinates in [sketch space, not sheet space](#api-quick-reference). Don't guess the center — [locate the feature from the view's polylines](#how-to-locate-the-feature-automatically-do-this-before-sketching-the-boundary) first.
3. Clear, then explicitly re-select the boundary: one segment for a circle, **all** segments for a profile loop.
4. Call `IDrawingDoc::CreateDetailViewAt4(X, Y, Z, …)` at a rough on-sheet position with the right `Showtype`.
5. Set scale (`view.ScaleDecimal`), `EditRebuild3`, then [offset-correct the placement](#how-to-place-the-detail-create--scale--measure--offset--verify--clamp) and verify on-sheet.
6. To delete later, [remove both the view and its boundary](#how-to-clean-up-view--boundary) in order.

If the parent view will be broken (`InsertBreak3` + `BreakView`), **create every detail first, then break** — see [Gotchas & fixes](#gotchas--fixes).

## API quick reference

### `CreateDetailViewAt4` — signature

```vb
swDrawing.CreateDetailViewAt4( _
    X, Y, Z,             ' meters, sheet space — center of the new detail view
    Style,               ' swDetViewStyle_e: 0=STANDARD, 1=BROKEN, 2=LEADER, 3=NOLEADER, 4=CONNECTED
    Scale1, Scale2,      ' numerator/denominator; pass 1,1 and override later via view.ScaleDecimal
    LabelIn,             ' single letter, e.g. "A" — appears as "DETAIL A"
    Showtype,            ' swDetCircleShowType_e: 0=PROFILE (rectangle/closed loop), 1=CIRCLE, 2=DONTSHOW
    FullOutline,         ' True = bubble border around detail view
    JaggedOutline,       ' True = torn-paper edge (mutually exclusive with FullOutline)
    NoOutline,           ' True overrides the two above
    ShapeIntensity)      ' 1..5, only used if JaggedOutline=True
```

Returns the new `IView`, or `Nothing` if creation failed (no/incomplete selection, open boundary, off-sheet position). Available on `IDrawingDoc` since SOLIDWORKS 2017. Older overloads (`CreateDetailView` … `CreateDetailViewAt3`) exist for earlier versions.

### `swDetViewStyle_e`

| Value | Constant |
|---|---|
| 0 | `swDetViewSTANDARD` |
| 1 | `swDetViewBROKEN` |
| 2 | `swDetViewLEADER` |
| 3 | `swDetViewNOLEADER` |
| 4 | `swDetViewCONNECTED` |

### `swDetCircleShowType_e` (`Showtype` arg)

| Value | Constant | Boundary |
|---|---|---|
| 0 | `swDetCirclePROFILE` | rectangle / any closed loop |
| 1 | `swDetCircleCIRCLE` | circle |
| 2 | `swDetCircleDONTSHOW` | hide the source boundary |

### Rectangle-sketch methods

Pick by which corner data you already have. All three write into the active view's sketch (so `ActivateView` first), return a `Variant` array of the created `SketchSegment` objects, and leave the segments selected immediately after creation. Coordinates are meters in the active sketch's local frame; SolidWorks ignores any document-display unit setting.

| Method | Signature | Use when |
|---|---|---|
| `CreateCenterRectangle(cx, cy, cz, x1, y1, z1)` | center + one corner | You computed a feature-cluster centroid and a half-extent |
| `CreateCornerRectangle(x1, y1, z1, x2, y2, z2)` | upper-left corner + lower-right corner | You have the bounding-box corners of the feature cluster |
| `CreateLine` × 4 | Four explicit segments | You need a non-axis-aligned rectangle, or any non-rectangular closed loop |

`CreateCircle(cx, cy, cz, px, py, pz)` — center triplet + any point on the circle. `CreateCircleByRadius(cx, cy, cz, r)` is the equivalent when you have a radius rather than a perimeter point.

### Coordinate reference

| Used for | Coordinate system | Units |
|---|---|---|
| `CreateDetailViewAt4(X, Y, Z, …)` | Sheet | Meters |
| `view.Position`, `view.GetOutline` | Sheet | Meters |
| `CreateCircle` / `CreateLine` / `CreateCenterRectangle` inputs (after `ActivateView`) | Active view's sketch | Meters |
| `IDetailCircle.SetParameters(x, y, r)` | Source view's sketch | Meters |
| `view.ScaleDecimal` | Ratio | — |

Sheet-coord ↔ sketch-coord conversions go through `sketch.ModelToSketchTransform` and `MathUtility.CreatePoint(...).MultiplyTransform(xform)` — needed only when you computed the boundary center in sheet space and must draw it in sketch space.

### Sheet width/height — pull from the sheet, don't hardcode

```csharp
Sheet sheet = (Sheet)swDraw.GetCurrentSheet();
double[] props = (double[])sheet.GetProperties2();
double sheetW = props[5];   // index 5 = sheet width  (meters)
double sheetH = props[6];   // index 6 = sheet height (meters)
```

The clamp math in placement depends on accurate `sheetW`/`sheetH`. Pulling them from the sheet survives a template switch; hardcoded A1/A3 dimensions (e.g. A1 = 0.841 × 0.594) silently break when someone changes the template.

### Post-creation handles

| Call | Returns |
|---|---|
| `swDetail.ScaleDecimal = 4#` | sets magnification (4:1, 2:1, …) — prefer integer ratios off the parent scale |
| `swModel.EditRebuild3` | forces the sheet to repaint with the new scale |
| `swDetail.GetDetail` | the `IDetailCircle` (boundary on the source view) for `SetLabel`, `SetParameters`, `PinPosition`, `ScaleHatchPattern`, `Layer` |
| `swDetail.GetOutline` | measured outline on the sheet, for collision checks and post-placement |
| `sourceView.GetDetailCircles` | every `IDetailCircle` on a source view (each has its own `GetDetailView`) |

### `EditDelete` selection types (cleanup)

`EditDelete` removes whatever is selected on the **active** document/view. There is no `DeleteDetailView` API. Match by name, not coordinates (coordinates are ignored for these types):

| Selection type string | Selects | Use when |
|---|---|---|
| `"DRAWINGVIEW"` | The derived detail view | Deleting the view |
| `"DETAILCIRCLE"` | The boundary on the source view | Deleting the boundary on the source |

Both work with `SelectByID2(name, type, 0, 0, 0, false, 0, Nothing, 0)`.

## Sketch space vs sheet space — get this right before sketching the boundary

The recipes below mix two coordinate systems, and confusing them is the #1 reason a boundary lands "nowhere near the feature."

| Call | Coordinate space | Why |
|---|---|---|
| `SketchManager.CreateCircle` / `CreateCornerRectangle` / `CreateCenterRectangle` (after `ActivateView` on the source) | **The view's sketch space.** Origin = view center. Axes match the view orientation. Scale is *part scale*, not sheet scale. | Sketches in a drawing view belong to the view's sketch, not the sheet's sketch. |
| `IDrawingDoc::CreateDetailViewAt4(X, Y, Z, …)` | **Sheet space**, meters. Origin = sheet bottom-left. | This positions the *new detail view* on the sheet, not the boundary inside the source. |

Pass sheet meters into `CreateCircle` and the boundary lands far off the feature (typically off the view entirely) — `CreateDetailViewAt4` then returns `Nothing` or makes a detail of empty space.

### The transform

```
sketch_coord = (sheet_coord − view_position) × scale_factor
scale_factor = 1 / view.ScaleDecimal       // 1:2 view → 0.5 → scale_factor = 2
```

Example — view at sheet position `(0.300, 0.281)`, scale 1:2:

| Sheet point | Sketch point |
|---|---|
| `(0.300, 0.281)` | `(0, 0)` — view center |
| `(0.576, 0.343)` | `(0.547, 0.123)` — top-right corner of the view |

### Verify with `ModelToSketchTransform`

For a known sheet point you can transform into sketch coords directly:

```csharp
Sketch viewSketch = (Sketch)view.GetSketch();
MathTransform xf = viewSketch.ModelToSketchTransform;
MathPoint sheetPt = (MathPoint)mathUtils.CreatePoint(new double[] { x, y, 0 });
MathPoint sketchPt = (MathPoint)sheetPt.MultiplyTransform(xf);
double[] sketchXYZ = (double[])sketchPt.ArrayData;
```

### Easier — work directly in sketch space

Skip the transform. Read the view's outline (sheet meters), convert half-extents to sketch space, and place the boundary inside those bounds:

```csharp
double[] outline = (double[])view.GetOutline();   // sheet meters: [xMin, yMin, xMax, yMax]
double halfWsheet = (outline[2] - outline[0]) / 2.0;
double halfHsheet = (outline[3] - outline[1]) / 2.0;

double scaleFactor = 1.0 / view.ScaleDecimal;     // e.g. 1:2 view → 2
double sketchHalfX = halfWsheet * scaleFactor;
double sketchHalfY = halfHsheet * scaleFactor;
// Sketch coords range: X ∈ [-sketchHalfX, +sketchHalfX], Y ∈ [-sketchHalfY, +sketchHalfY]
// (0, 0) in sketch space = view center on the sheet.
```

### Turned-part shortcut — anchor `y` to a wall, not to the void

A longitudinal section of a turned part (axis horizontal) is mirror-symmetric about the axis (`y = 0` in sketch space). Anchor `y_sk` (the boundary center in sketch space) to a *wall radius* — not to the midpoint of the section's y range, and not to `sketchHalfY` minus an arbitrary margin. Two distinct things go wrong otherwise:

1. **A boundary that spans both walls roughly doubles in size and duplicates information.** Capture the upper wall only; the reader infers the lower wall by symmetry.
2. **A boundary centered between ID and OD lands in the solid-hatch void.** In a longitudinal section the material between the bore (ID) and outer surface (OD) is filled with solid section hatching — no detailable edges live there. The `CreateDetailViewAt4` call succeeds and the derived view renders, but the contents come out as empty cross-hatching.

Read the wall radii from the part's bounding box (`sizeY / 2` for an axis-horizontal turned part) or from the feature's parent face, then place `y_sk` per the table:

| Feature lives on… | Set `y_sk` ≈ | Boundary radius |
|---|---|---|
| Bore / ID wall (O-ring groove, ID chamfer, thread relief) | `+r_ID` (bore radius in model meters) | sized to clear the feature + its dim halo |
| OD wall (port boss, surface groove, OD chamfer) | `+r_OD` (outer radius in model meters) | sized to clear the feature + its dim halo, typically a touch larger than for ID work |
| Centerline feature (axial hole on axis) | `0` | sized to clear the bore diameter |

`sketchHalfY` is the section's full vertical extent, which includes the void between the two walls — the wall radii are the only `y` values where features actually exist; the rest of the y range is hatch.

### Sanity checks after creation

- `detail.GetOutline()` returns negative coords → the detail view landed off-sheet. Reposition.
- `detail.GetSheetName()` reports no sheet, or the boundary on the source view is visibly far from the target feature → sheet coords were passed into `CreateCircle` by mistake. Delete the boundary sketch + the detail (see [Cleanup](#how-to-clean-up-view--boundary)), retry with sketch coords.
- Boundary visibly off the feature (but in the right coordinate space) → you guessed sketch coords instead of reading them. Use `GetPolylines7` to locate the feature — see [How to: locate the feature automatically](#how-to-locate-the-feature-automatically-do-this-before-sketching-the-boundary).

## How to: circular detail view

`swDetCircleCIRCLE = 1`. The circle you sketch defines the boundary on the source view; SolidWorks crops the detail to whatever falls inside. For a circle detail, `view.Position` equals the rendered outline center, so no offset correction is needed for placement.

```vb
Option Explicit

Sub MakeCircularDetail()
    Dim swApp As SldWorks.SldWorks
    Dim swModel As SldWorks.ModelDoc2
    Dim swDrawing As SldWorks.DrawingDoc
    Dim swSketchMgr As SldWorks.SketchManager
    Dim swCircle As SldWorks.SketchSegment
    Dim swDetail As SldWorks.View

    Set swApp = Application.SldWorks
    Set swModel = swApp.ActiveDoc
    Set swDrawing = swModel
    Set swSketchMgr = swModel.SketchManager

    ' 1. Activate the SOURCE view — the boundary must land in its sketch.
    swDrawing.ActivateView "Drawing View1"
    swModel.ClearSelection2 True

    ' 2. Sketch a circle in the source view's sketch.
    '    CreateCircle(centerX, centerY, centerZ, perimX, perimY, perimZ) — second triplet is any point on the circle.
    '    All coords in meters, in the active view's sketch space.
    Set swCircle = swSketchMgr.CreateCircle( _
        0.05, 0.03, 0, _
        0.058, 0.03, 0)

    ' 3. The just-created segment is already selected. If anything intervened, re-select:
    '    swCircle.Select4 False, Nothing

    ' 4. Spawn the detail view at a sheet position. ShowType = swDetCircleCIRCLE (1).
    Set swDetail = swDrawing.CreateDetailViewAt4( _
        0.22, 0.10, 0, _
        swDetViewSTANDARD, 1, 1, "A", _
        swDetCircleCIRCLE, _
        True, False, False, 5)

    If swDetail Is Nothing Then
        MsgBox "Detail view creation failed (check selection / source view)."
        Exit Sub
    End If

    ' 5. Set the real scale and rebuild.
    swDetail.ScaleDecimal = 4#
    swModel.EditRebuild3
End Sub
```

## How to: rectangular (profile) detail view

`swDetCirclePROFILE = 0`. For non-circular features — stepped bores, groove clusters, slots — a rectangle wastes less paper than a circle that has to inscribe the same content. The boundary is *any* closed sketch profile; rectangle is the common case. Polygon, freeform spline, and mixed line/arc loops are all accepted — the only requirements are **closed** and **fully selected**.

Select **every** segment of the closed loop before the call (selecting only one of four sides returns `Nothing`). Unlike a circle, `view.Position` for a profile detail is the profile's sketch anchor with a constant per-detail offset, not the outline center — so use the [Safe placement recipe](#how-to-place-the-detail-create--scale--measure--offset--verify--clamp) rather than a raw `Position` assignment.

```vb
Option Explicit

Sub MakeRectangularDetail()
    Dim swApp As SldWorks.SldWorks
    Dim swModel As SldWorks.ModelDoc2
    Dim swDrawing As SldWorks.DrawingDoc
    Dim swSketchMgr As SldWorks.SketchManager
    Dim vSegs As Variant
    Dim swDetail As SldWorks.View
    Dim i As Long

    Set swApp = Application.SldWorks
    Set swModel = swApp.ActiveDoc
    Set swDrawing = swModel
    Set swSketchMgr = swModel.SketchManager

    ' 1. Activate the source view.
    swDrawing.ActivateView "Drawing View1"
    swModel.ClearSelection2 True

    ' 2. Sketch a closed rectangle in the source view's sketch.
    '    CreateCenterRectangle returns a Variant array of the 4 SketchSegments + center point.
    '    (Center X, Y, Z, Corner X, Y, Z) — all meters, sketch space.
    vSegs = swSketchMgr.CreateCenterRectangle( _
        0.05, 0.03, 0, _
        0.065, 0.04, 0)

    ' 3. Select ALL segments of the closed loop. Partial selection → CreateDetailViewAt4 returns Nothing.
    swModel.ClearSelection2 True
    For i = LBound(vSegs) To UBound(vSegs)
        If TypeOf vSegs(i) Is SldWorks.SketchSegment Then
            vSegs(i).Select4 True, Nothing   ' append=True so each adds to the selection
        End If
    Next i

    ' 4. Spawn the detail view. ShowType = swDetCirclePROFILE (0).
    Set swDetail = swDrawing.CreateDetailViewAt4( _
        0.22, 0.10, 0, _
        swDetViewSTANDARD, 1, 1, "B", _
        swDetCirclePROFILE, _
        True, False, False, 5)

    If swDetail Is Nothing Then
        MsgBox "Detail view creation failed (verify all 4 segments were selected)."
        Exit Sub
    End If

    ' 5. Scale, then offset-correct position (see Safe placement).
    swDetail.ScaleDecimal = 4#
    swModel.EditRebuild3
End Sub
```

`CreateCornerRectangle` variant of step 2:

```vb
Dim vSegs As Variant
vSegs = swSketchMgr.CreateCornerRectangle( _
    0.035, 0.020, 0, _      ' upper-left  (X1, Y1, Z1)
    0.065, 0.040, 0)        ' lower-right (X2, Y2, Z2)
```

Closed loops drawn line-by-line work the same way: `CreateLine` four times, then select all four segments before the call. The selection-and-call pattern (step 3 onward) is identical for all rectangle-sketch methods — pick whichever requires less coordinate math at the call site.

### Same call, both shapes — what differs

| Step | Circular | Rectangular (profile) |
|---|---|---|
| Boundary sketch | `CreateCircle` (or `CreateCircleByRadius`) | `CreateCenterRectangle` (or 4 × `CreateLine`) |
| Selection before call | One segment (auto-selected on create) | All N segments of the closed loop |
| `Showtype` arg | `swDetCircleCIRCLE` (`1`) | `swDetCirclePROFILE` (`0`) |
| `view.Position` placement | Equals outline center — place directly | Offset from outline center — measure-then-correct |
| Best for | Isolated circular features (O-rings, single radii) | Stepped bores, groove clusters, slots, anything non-circular |

Everything else — style, scale, label, outline flags, cleanup — is identical.

## How to: locate the feature automatically (do this BEFORE sketching the boundary)

The #1 time sink isn't the math — it's guessing where the feature sits in the source view's sketch space and iterating via screenshots. Don't guess. Read the view's actual geometry and compute the boundary center from it. One extra read collapses 4–5 screenshot rounds into a single shot.

### `IView::GetPolylines7` — the feature locator

```csharp
object obj;
// Return = polyline COUNT, but it arrives boxed — Convert.ToInt32, don't cast straight to int.
int nPolylines = Convert.ToInt32(sourceView.GetPolylines7(
    (int)swCrossHatchFilter_e.swDontApplyCrossHatch, out obj));
double[] data = (double[])obj;   // ← the geometry lives in the OUT param, not the return
```

**Parsing pitfall — the return value is the polyline *count*, not the data.** The return is just how many polylines were emitted; the geometry is the `out` parameter, and it is **one flat `double[]`** (typically a few hundred to a few thousand doubles, depending on part complexity). Two casts bite here:

- **The count comes back boxed**, not as a plain `int`. A direct `int n = view.GetPolylines7(...)` / `(int)` unbox throws `InvalidCastException` — wrap it in `Convert.ToInt32(...)`, or just ignore the count entirely and drive the walk off `data.Length`.
- **The `out` data is `double[]`, not `object[]`.** Casting the `out` object to `object[]` *appears* to succeed but yields an array of all-`null` elements — always cast it to `double[]` and walk it as one flat buffer.

Each record is laid out as:

```
[ Type, GeomDataSize, GeomData[...], LineColor, LineStyle, LineFont,
  LineWeight, LayerID, LayerOverride, NumPolyPoints, x,y,z × NumPolyPoints ]
```

Walk it record-by-record, advancing the cursor by `GeomDataSize` and `NumPolyPoints` per record, and collect every `(x, y)`. Mis-parsing this layout is the common failure here.

**Coordinates are view-centered model meters — independent of the view's display scale.** `(x, y)` are model meters measured from the view center (`(0, 0)` = view center) — exactly the sketch space `CreateCircle` / `CreateCenterRectangle` expect. They are **not** multiplied by the view's display scale: on a 1:2 view the points come back at real model size, not halved. Pass them straight through — no `×scale`, no transform.

### Turn points into a boundary center

`GetPolylines7` hands you **every visible edge in the whole view**, not just your feature — so filtering is mandatory, not optional. Don't eyeball the blob; narrow it programmatically:

1. **Filter to the feature's neighborhood.** You usually already know the feature's approximate axial position from the model (e.g. a groove at some axial `x`, on the wall at `y ≈ +r`). Keep only points within a window around it — or find the tight cluster of short segments that a groove / undercut / thread produces.
2. **Cluster the surviving points.** For a groove/undercut, the two wall edges show up as two tight x-clusters; the floor is a y-cluster at the groove-bottom radius. The midpoint of the wall clusters = boundary center x; the floor radius = boundary center y.
3. **Sanity-check the subset before sketching.** Confirm a derived quantity against the model's nominal — e.g. the wall-cluster spacing should equal the known feature width. If it doesn't, you grabbed the wrong edges; re-filter rather than proceeding.
4. **Size the boundary to the cluster span + a halo** (~1× feature size) so witness lines aren't cropped.

```csharp
// Example: groove located from polyline points already filtered to its region.
double cx = (xWallLeft + xWallRight) / 2.0;   // groove center, sketch meters
double cy = yFloor;                            // groove floor radius (wall the feature lives on)
double r  = (Math.Abs(xWallRight - xWallLeft) / 2.0) + halo;   // halo ≈ feature size
var circle = swSketchMgr.CreateCircleByRadius(cx, cy, 0, r);
```

### Cross-check against the model

You almost always have the feature's nominal location from the part (sketch dim, feature position, bounding box). Use it two ways:

- As the **filter window** in step 1 (so you cluster the right edges, not a neighboring step).
- As a **sanity check**: computed `cx`/`cy` should match the model's nominal within a fraction of a mm. If it doesn't, you filtered the wrong region — don't proceed to `CreateDetailViewAt4`.

For an axis-horizontal turned part, `cy` is the wall radius (`sizeY / 2` from the bounding box, or the feature's parent-face radius) — combine this with the [Turned-part shortcut](#turned-part-shortcut--anchor-y-to-a-wall-not-to-the-void) table above.

### Why this is one-shot

| Without locator | With locator |
|---|---|
| Guess sketch x/y → create → screenshot → boundary's off the feature → nudge → repeat | Read polylines → cluster → compute center → create once, on-target |
| Boundary radius guessed → crops witness lines or grabs neighbor | Radius derived from measured cluster span + halo |

## How to: place the detail (create → scale → measure → offset → verify → clamp)

A single-pass `CreateDetailViewAt4(targetX, targetY, ...)` rarely lands the outline where you want it: (1) for profile details, `view.Position` is the sketch anchor, not the outline center; (2) until `EditRebuild3` runs after the scale is applied, `GetOutline` has nothing meaningful to report. Run this fixed six-step sequence — same code for circle and profile details, only the `Showtype` arg differs.

```csharp
// 1. Create at a ROUGH on-sheet position (doesn't matter where, just on-sheet).
//    The offset-correction below relocates the view; the rough spot just has to
//    be inside the sheet so the detail doesn't get rejected at creation time.
View detail = (View)swDraw.CreateDetailViewAt4(
    sheetW * 0.5, sheetH * 0.3, 0,
    (int)swDetViewStyle_e.swDetViewSTANDARD,
    1, 1, "B",
    1,                                        // 1 = swDetCircleCIRCLE, 0 = swDetCirclePROFILE
    true, false, false, 5);

if (detail == null) throw new InvalidOperationException("Detail creation failed");

// 2. Set scale and rebuild BEFORE reading outline.
//    GetOutline reflects the post-scale rendering — reading it before EditRebuild3
//    returns the pre-scale outline and the offset math below silently produces
//    a wrong result.
detail.ScaleDecimal = targetScale;
swDrawModel.EditRebuild3();

// 3. Measure the offset between Position (anchor) and outline center.
double[] pos = (double[])detail.Position;
double[] ol  = (double[])detail.GetOutline();
double offX = pos[0] - (ol[0] + ol[2]) / 2.0;
double offY = pos[1] - (ol[1] + ol[3]) / 2.0;
double detW = ol[2] - ol[0];
double detH = ol[3] - ol[1];

// 4. Compute the target — where you actually want the outline center.
//    Account for the detail's own size so it doesn't overlap neighbors.
double targetCX = 0.60;
double targetCY = 0.15;

// 5. Apply the offset-corrected position.
detail.Position = new double[] { targetCX + offX, targetCY + offY };
swDrawModel.EditRebuild3();

// 6. VERIFY on-sheet — non-negotiable. ScaleDecimal can push the outline off
//    the sheet even when `(targetCX, targetCY)` looked safe before scaling.
double[] finalOL = (double[])detail.GetOutline();
const double margin = 0.005;   // 5 mm sheet-edge margin
bool onSheet = finalOL[0] >= margin && finalOL[1] >= margin
            && finalOL[2] <= sheetW - margin && finalOL[3] <= sheetH - margin;

if (!onSheet)
{
    // Clamp the *outline center* to keep the outline fully on-sheet.
    // We clamp targetCX/Y between [detW/2 + neighborGap, sheetW - detW/2 - neighborGap].
    const double neighborGap = 0.01;   // 10 mm clear of sheet edge after detail size
    double clampX = Math.Max(detW / 2.0 + neighborGap, Math.Min(targetCX, sheetW - detW / 2.0 - neighborGap));
    double clampY = Math.Max(detH / 2.0 + neighborGap, Math.Min(targetCY, sheetH - detH / 2.0 - neighborGap));
    detail.Position = new double[] { clampX + offX, clampY + offY };
    swDrawModel.EditRebuild3();
}
```

### Why each step is non-optional

| Step | If you skip it | Symptom |
|---|---|---|
| 1. Rough on-sheet creation | Pass `targetCX, targetCY` directly | Profile detail's anchor ≠ center → outline lands somewhere unexpected; circle detail lands at the right spot only by coincidence |
| 2. Scale + rebuild before measuring | `GetOutline` returns pre-scale outline | Offset math is computed against the wrong outline; final position is off by a factor of `scale - 1` of the detail's half-extent |
| 3. Measure `pos - outline_center` | Assume `Position == outline_center` | Wrong by the per-detail anchor offset for profile details; right by accident for circle details |
| 4. Account for `detW × detH` when picking target | Pick `targetCX/Y` ignoring detail size | Detail collides with the source view or runs off the sheet edge |
| 5. Apply `targetCX + offX, targetCY + offY` | Apply `targetCX, targetCY` directly | Outline lands at `targetCX - offX, targetCY - offY` — visibly shifted |
| 6. Verify + clamp | Trust step 5 | At higher scales (≥ 4:1) the post-scale outline can run past the sheet edge despite a "safe-looking" target — the drawing renders with the detail half off-sheet |

For circle details, the offset measured in step 3 is `(0, 0)` — `Position == outline_center` — so steps 3–5 collapse to a no-op offset. Run the full recipe anyway; it costs nothing and keeps the placement code uniform regardless of `Showtype`.

## How to: dimension the new detail view

Use `IDrawingDoc.AutoDimension` (SW 2005 FCS+) for detail views — it is scoped to the view's actual rendered entity list (boundary-cropped), so it cannot project dims whose attachment lies outside the detail boundary. `InsertModelDimensions` walks the **model**'s annotations, not the view's *visible* geometry, so on a detail view it can project dims with leaders going nowhere visible.

```csharp
swModel.ClearSelection2(true);
swExt.SelectByID2(detailView.GetName2(), "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);

int status = swDraw.AutoDimension(
    (int)swAutodimEntities_e.swAutodimEntitiesAll,                            // every supported entity IN this view
    (int)swAutodimScheme_e.swAutodimSchemeBaseline,
    (int)swAutodimHorizontalPlacement_e.swAutodimHorizontalPlacementAbove,
    (int)swAutodimScheme_e.swAutodimSchemeBaseline,
    (int)swAutodimVerticalPlacement_e.swAutodimVerticalPlacementRight);
```

One call. Entities outside the detail boundary aren't in the view's entity list, so AutoDimension can't touch them. Supported entities (per `swAutodimEntities_e` remarks): lines, points, vertices, faces, sketch entities, center lines, center marks; circles/arcs auto-receive Ø/R dims.

**Default workflow:** `InsertModelDimensions` for parent / section / standard views (detail-first order, per `dimensioning-simple.md` → "Order rationale") + **AutoDimension for detail views**. Apply only one per view — running both on the same view produces duplicates. Full per-flavour comparison + caveats + qualifier-replay strategy in `detail-view-dimensioning.md`.

For per-entity qualifier control AutoDimension can't produce, select entities via `IView::SelectEntity` (not by sheet coordinates) and use the standard `Add*Dimension2` calls — see `detail-view-dimensioning.md`. `GetVisibleEntities2` on a detail view returns edges in **model space** (the model's internal units, usually centimeters even when the document's display unit is inches/mm); the unit mismatch and the detail's scale factor compound, so reach for `AutoDimension` first and only walk `GetVisibleEntities2` manually when you need that per-entity control.

## How to: clean up (view + boundary)

A detail view has **two pieces of state** on the drawing:

1. **The derived `IView`** — the rendered detail box on the sheet (with its label, scale, outline).
2. **The `IDetailCircle` / profile boundary** in the *source* view's sketch — the original closed loop you drew.

Delete **both** explicitly in this order, capturing the boundary handle *before* the view is destroyed. Deleting only the view via `EditDelete` can leave an **orphan boundary** on the source view (a labelled circle/rectangle pointing at nothing); whether it does varies by SW version and how the view was selected.

```
1. Capture IDetailCircle handle      ← from detailView.GetDetail(); becomes invalid after step 4
2. Capture the bare circle name      ← dc.GetName()  (e.g. "Detail Circle1"); NOT "name@view"
3. Capture detailView name + source-view name
4. Delete the derived detail view    ← SelectByID2(name, "DRAWINGVIEW") + EditDelete
5. Activate the SOURCE view          ← mandatory; EditDelete operates on the active view's sketch
6. Delete the boundary               ← SelectByID2(dcName, "DETAILCIRCLE") + EditDelete
7. EditRebuild3
```

Three details make this work (verified in-session):

- Capture `detailView.GetDetail()` **before** step 4 — it returns `null` after the detail view is deleted.
- Pass the bare `dc.GetName()` value (e.g. `"Detail Circle1"`) to `SelectByID2`. The `"name@view"` suffix form is silently rejected and fails to select.
- `EditDelete` operates on selections within the **active view's** sketch. `ActivateView(sourceViewName)` first — if the sheet is still active in step 6, the call silently no-ops.

`SelectByID2(dcName, "DETAILCIRCLE", …)` with the bare name is the only deletion path observed to clean up both the boundary and its feature-tree node. (`dc.Select(true, null)` on an `IDetailCircle` returns `false` and selects nothing; `dc.GetProfileItems()` + `Select4` + `EditDelete` deletes the underlying sketch segments but leaves the `DetailCircle` node intact in the tree.)

### Full C# cleanup example

Verified end-to-end against SolidWorks API. Drop-in ready for `solidworks_execute_csharp_code_drawing`.

```csharp
// Capture handles BEFORE deleting anything.
DetailCircle dc = (DetailCircle)detailView.GetDetail();   // becomes invalid after view delete
string dcName = dc.GetName();                              // e.g. "Detail Circle1" — bare name, NOT "name@view"
string dvName = detailView.Name;
string sourceViewName = sourceView.GetName2();

// 1. Delete the derived detail view.
swDrawModel.ClearSelection2(true);
swExt.SelectByID2(dvName, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
swDrawModel.EditDelete();

// 2. Activate the SOURCE view (mandatory — EditDelete operates on the active view's sketch).
swDraw.ActivateView(sourceViewName);
swDrawModel.ClearSelection2(true);

// 3. Delete the boundary — bare dcName from GetName(), not "name@view".
bool sel = swExt.SelectByID2(dcName, "DETAILCIRCLE", 0, 0, 0, false, 0, null, 0);
if (sel) swDrawModel.EditDelete();

swDrawModel.EditRebuild3();

// 4. Verify the boundary is gone — surfaces orphaned-tree-node bugs early.
object[] remaining = (object[])sourceView.GetDetailCircles();
if (remaining != null && remaining.Length > 0)
    throw new InvalidOperationException(
        $"DetailCircle still present after delete — check dcName matches GetName() output (got '{dcName}')");
```

Helper to look up a view by name when you don't already hold the `IView`:

```csharp
View FindViewByName(DrawingDoc swDrawing, string viewName)
{
    View v = (View)swDrawing.GetFirstView();   // returns the sheet, not a real view
    v = (View)v.GetNextView();                 // first real view
    while (v != null)
    {
        if (v.GetName2() == viewName) return v;
        v = (View)v.GetNextView();
    }
    return null;
}
```

### Multiple detail circles on one source view

If the source view has several detail boundaries (e.g. details A, B, C all carved out of one section), enumerate via `IView.GetDetailCircles`, match by label, then delete via `SelectByID2` using the bare circle name. Target one at a time — a blanket `EditSketch` + clear on the source's sketch destroys boundaries for **all** details on that source.

```csharp
swDraw.ActivateView(sourceView.GetName2());  // mandatory before EditDelete
swDrawModel.ClearSelection2(true);

object[] circles = (object[])sourceView.GetDetailCircles();
foreach (DetailCircle dc in circles)
{
    if (dc.GetLabel() == "B")
    {
        string dcName = dc.GetName();          // bare name, not "name@view"
        if (swExt.SelectByID2(dcName, "DETAILCIRCLE", 0, 0, 0, false, 0, null, 0))
            swDrawModel.EditDelete();
        break;
    }
}

swDrawModel.EditRebuild3();
```

### Keep the boundary, drop only the view

To delete the **derived view** but keep the boundary visible on the source view (for a sales-aid drawing, or to re-create the detail at a different scale later), stop after deleting the view and skip the boundary deletion (steps 5–6). The boundary remains as a labelled circle/rectangle on the source — the programmatic equivalent of Hawk Ridge's "remove a section/detail view without deleting the defining sketch" UI workflow.

Deleting the **source view** auto-deletes its detail views and their boundaries — no manual cleanup needed in that order, but you also lose every detail on that source, intended or not.

## Best practices — where and when to create a detail view

The API will create a detail anywhere you ask; these conventions keep the result readable rather than zoomed-in clutter.

### When a detail view is justified

Create one when at least one of these holds:

- The smallest dimensioned feature renders **smaller than ~3 mm on paper** at the parent view's scale (text and arrowheads stop being legible below that).
- Dimensions, GD&T frames, or leaders are **overlapping** in the parent view and can't be resolved by repositioning alone.
- A **tight tolerance** or surface-finish callout needs to attach to geometry that's visually crowded.
- A feature cluster (stepped bore, O-ring groove, undercut) needs its own dimensioning frame separate from the parent.

If none apply, skip the detail view — every extra view costs sheet real estate and adds a label the reader has to chase. For internal features (hidden bores, cavities), reach for a **section view** first; a detail view zooms the outside silhouette and won't reveal internal geometry on its own.

### Where to draw the boundary on the source view

- **Center the boundary on the feature**, then enlarge it by roughly **1× the feature's size in context** so dimension witness lines and leaders aren't cropped. A boundary that hugs the geometry edge crops them.
- For a **circular feature**, draw the boundary circle ~1.5× the feature's bounding diameter — generous enough that the feature has breathing room for dimensions.
- For a **rectangular cluster** (multiple holes, a slot row, a groove pattern), use one rectangle enclosing all of them plus a margin — not one detail per feature.
- **Keep the boundary clear of part edges** unless you intend to show the edge — a boundary that clips a fillet mid-arc produces an ambiguous edge in the detail.
- **Keep boundaries from overlapping** on the source view — two detail circles that overlap produce two details the reader must mentally untangle; combine them or pick one.

### What scale to pick

- Use **integer multiples of the parent scale**: 2×, 4×, 5×, 10×. Non-integer ratios (3.5×, 7×) force the reader to do mental math when comparing features across views.
- Pick the **lowest** scale at which the smallest dimensioned feature reads at ~3 mm on paper. Over-zooming wastes the sheet and exaggerates surface roughness artifacts.
- **Keep to at most two detail scales per drawing.** Three magnifications (2:1, 4:1, 8:1) on one sheet is hard to follow; consolidate or accept a slightly larger detail.

### Where to place the detail on the sheet

- Place each detail **in reading order from its source** — typically to the right of, or below, the source view (Western reading order is left-to-right, top-to-bottom; the detail should follow the parent, not lead it).
- Reserve a **dimension halo** around the detail — roughly the detail's own outline size, on the side where you'll place dimensions and the `DETAIL X SCALE Y:Z` label.
- **Place the detail on the same side as its boundary** so the leader from the source view's detail circle to the detail view runs short — putting the detail on the opposite side forces a long leader that snakes across other geometry.
- Use `GetOutline` after creation to **check collisions** with neighboring views and the title block before committing the position. For profile details, remember `Position` ≠ outline center — apply the offset correction from [Safe placement](#how-to-place-the-detail-create--scale--measure--offset--verify--clamp).

### One detail per concern

If a single feature needs two scales (overview at 2:1, micro-callout at 8:1), that's two details — but the **second detail's boundary should sit on the first detail**, not on the original parent. Chained details (detail-of-detail) are valid and read naturally; redundant parallel details of the same feature do not.

## Gotchas & fixes

- **Prefer rectangular (profile) detail views, sketch the boundary carefully on the source view, and predict the rendered size before you create.** A rectangle hugs the feature and wastes less paper than a circle inscribing the same content. Sketch the boundary deliberately in the source view's sketch space — not a rough guess — placed squarely over the exact feature(s) you intend the detail to show, so the rendered view captures that geometry and nothing extraneous. Then compute how big the detail will render *before* the call: `rendered_size_on_sheet ≈ boundary_size_in_sketch_meters × view.ScaleDecimal`. Check that against the free sheet space (and its dimension halo) so you don't create a detail that overruns the sheet or collides with neighbors.
- **Create details before breaking the parent.** If the parent (section/front) view will be broken via `InsertBreak3` + `BreakView`, create every detail view first, then break. (Authoring a detail against an already-broken view collapses the source-view sketch space inside the break gap; `swDetCirclePROFILE` rectangle boundaries especially get unstable coordinates and frequently return `Nothing`.) Detail boundaries lock to **model geometry**, not sketch/sheet space, so once a detail exists it survives the subsequent break cleanly — see `broken-views-guide.md` → "Workflow Order — Break LAST When Combined with Detail Views."
- **`GetPolylines7` returns one flat `double[]`, not nested arrays.** Walk it record-by-record, advancing the cursor by `GeomDataSize` and `NumPolyPoints` per record — anything else mis-parses the layout (see [How to: locate the feature automatically](#how-to-locate-the-feature-automatically-do-this-before-sketching-the-boundary)).
- **Activate the source view before sketching the boundary.** `SketchManager.CreateCircle` / `CreateLine` writes to the *active* view's sketch — activate the source view first, or the boundary lands in the wrong sketch and `CreateDetailViewAt4` sees no valid selection → returns `Nothing`.
- **Select every segment of a profile boundary.** Append each segment of the closed loop to the selection; one missed side returns `Nothing`. (A circle is one auto-selected segment.)
- **Close the loop.** A rectangle missing one side, or two unconnected arcs, is treated as not-a-boundary. Use a genuinely closed profile.
- **Get the real source view, not the sheet.** `GetFirstView()` returns the sheet background, not the first real view. Call `GetNextView()` once to reach the actual view.
- **Pass an on-sheet position to `CreateDetailViewAt4`.** `(X, Y, Z)` must land inside the sheet bounds in meters — pass a rough but on-sheet value and reposition afterward. Verify the view's `Position` (its anchor point in sheet meters) against the sheet's width/height, both before and after any `Position` reassignment:

  ```csharp
  double[] pos = (double[])view.Position;   // anchor in sheet meters
  Sheet sheet = (Sheet)swDraw.GetCurrentSheet();
  double[] props = (double[])sheet.GetProperties2();
  double sheetW = props[5];                 // sheet width  (meters)
  double sheetH = props[6];                 // sheet height (meters)

  bool onSheet = pos[0] > 0 && pos[0] < sheetW
              && pos[1] > 0 && pos[1] < sheetH;
  ```

  For profile (rectangular) details, `Position` is the anchor, not the outline center — apply the offset-correction from [Safe placement](#how-to-place-the-detail-create--scale--measure--offset--verify--clamp) before deciding the view is "where you wanted it."
- **Re-select the boundary explicitly before creating the detail.** Don't rely on auto-selection persisting from `CreateCircle` to `CreateDetailViewAt4` — when `AddToDB = true` was recently toggled, or an intervening operation touched the selection, the just-created segment may not be selected:

  ```csharp
  swModel.ClearSelection2(true);
  circle.Select4(false, null);   // or, for a profile, append every segment with Select4(true, ...)
  swDraw.CreateDetailViewAt4(...);
  ```

- **Anchor the boundary to a wall radius on section-view voids.** On a section of a hollow/turned part, the area between walls is solid hatch — no edges, no features; the call succeeds and the view renders, but the contents are blank cross-hatching. Anchor `y_sk` to a wall radius (see [Turned-part shortcut](#turned-part-shortcut--anchor-y-to-a-wall-not-to-the-void)), never to a midpoint between ID and OD.
- **Check `GetOutline` sign after creation.** A negative `GetOutline` corner means the view is partly off-sheet — the preview can still look fine but it misbehaves downstream. Reposition.
- **Capture the boundary handle before deleting the view.** `GetDetail()` returns `Nothing` after `EditDelete` on the detail view — capture it first (see [Cleanup](#how-to-clean-up-view--boundary)).
- **`EditRebuild3` after delete.** Skipping it can leave a phantom label cached in the sheet header until the next interaction.
- **Read `GetOutline` only after scale + `EditRebuild3`.** Before the rebuild, `GetOutline` returns the pre-scale outline and the placement offset math silently produces a wrong result.
