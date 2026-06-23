---
description: Create broken (shortened) views in SolidWorks drawings to remove featureless middle sections of long parts. Covers InsertBreak3/BreakView, view-relative break-position math, break-line styles, multi-view alignment, matching breaks to a parent view, removing breaks, and the break-vs-detail authoring order.
---

# Broken Views in SolidWorks Drawings

> Shorten long parts (shafts, tubes, beams, rods) by removing a featureless middle section, leaving double break lines per ASME Y14.3. Use when a part's aspect ratio exceeds ~3:1 and the middle is uniform, so the ends fit at a readable scale.

## Recipe (happy path)

1. Create the drawing and place all views at the desired scale, still unbroken.
2. If the drawing also has detail views, create them FIRST against the unbroken parent — see [How to: order break vs detail views](#how-to-order-break-vs-detail-views).
3. Read `View.GetOutline()` + `View.Position` and compute break positions in VIEW-RELATIVE coordinates → [How to: apply a break to one view](#how-to-apply-a-break-to-one-view).
4. `View.InsertBreak3(orientation, pos1, pos2, style, intensity, breakSketchBlocks)` on the view.
5. Select the view (`SelectByID2 … "DRAWINGVIEW"`) → `DrawingDoc.BreakView()` to apply it.
6. Repeat for every long-axis view, reusing the same percentages → [How to: break multiple aligned views](#how-to-break-multiple-aligned-views).
7. `ModelDoc2.ForceRebuild3(true)`, re-read outlines, and re-center (broken views are shorter) → [How to: re-center after breaking](#how-to-re-center-after-breaking).

## API quick reference

**`View.InsertBreak3(Orientation, Position1, Position2, BreakLineStyle, ShapeIntensity, BreakSketchBlocks)`** — inserts the break lines; returns an `IBreakLine` (or `null` on failure). Positions are view-relative, in meters.

| Arg | Type | Meaning |
|---|---|---|
| `Orientation` | int (`swBreakLineOrientation_e`) | break-line direction (see enum below) |
| `Position1` | double | first break line, view-relative coordinate in meters |
| `Position2` | double | second break line, view-relative coordinate in meters |
| `BreakLineStyle` | int (`swBreakLineStyle_e`) | line style (see enum below) |
| `ShapeIntensity` | int | 1–5; only meaningful for the Jagged style |
| `BreakSketchBlocks` | bool | whether to break sketch blocks too |

**`swBreakLineOrientation_e`** — choose by the part's long axis:

| Value | Constant | Use for | Position1/2 are |
|---|---|---|---|
| 1 | `swBreakLineHorizontal` | long axis VERTICAL (tall part) → horizontal break lines | **Y** values relative to view origin |
| 2 | `swBreakLineVertical` | long axis HORIZONTAL (typical turned part in Front view) → vertical break lines | **X** values relative to view origin |

**`swBreakLineStyle_e`**:

| Value | Constant | Style |
|---|---|---|
| 1 | `swBreakLine_Straight` | simple straight cut |
| 2 | `swBreakLine_ZigZag` | large zigzag |
| 3 | `swBreakLine_Curve` | S-curve / wave — **project default** |
| 4 | `swBreakLine_SmallZigZag` | double zigzag |
| 5 | `swBreakLine_Jagged` | jagged / rough cut (use `ShapeIntensity` 1–5) |

Default to `swBreakLine_Curve (3)` for all view types — it reads cleanly on both prismatic and revolved parts and matches the house style. Use another style only with a written reason (shop preference, or a project standard explicitly mandating e.g. SmallZigZag).

**Other break APIs:**

| Member | Signature | Notes |
|---|---|---|
| `DrawingDoc.BreakView()` | `BreakView()` | applies the break; the target view must be selected first |
| `DrawingDoc.UnBreakView()` | `UnBreakView()` | removes the break but keeps the break-line features |
| `View.IsBroken()` | `bool IsBroken()` | a **method**, not a property |
| `View.GetBreakLineCount2(out int)` | `int GetBreakLineCount2(out int arraySize)` | needs the `out` parameter for the array size |
| `View.GetBreakLines()` | `object[] GetBreakLines()` | returns the `IBreakLine` objects |
| `View.BreakLineGap` | `double` (property) | controls the zigzag/gap width |
| `IBreakLine.GetPosition(i)` | `double GetPosition(int i)` | view-relative position of line `i` (`0` or `1`) |
| `IBreakLine.Style` | int (property) | `swBreakLineStyle_e` |
| `IBreakLine.Orientation` | int (property) | `swBreakLineOrientation_e` |

**View geometry helpers used for positioning:**

- `double[] View.GetOutline()` → `[xMin, yMin, xMax, yMax]` in **sheet** coordinates.
- `double[] View.Position` → the view origin in sheet coordinates, which is the **center of the view's bounding box** on the sheet (not the model-origin projection).

## How to: apply a break to one view

Break positions are relative to the VIEW ORIGIN (center of the bounding box), not the model origin. Compute them from the outline and `Position`, then insert and apply.

1. Read the outline and view origin, and derive view-relative span. These will be roughly symmetric, e.g. `-138 mm` and `+138 mm`.

```csharp
double[] fOut = (double[])view.GetOutline();  // [xMin, yMin, xMax, yMax] in sheet coords
double[] fPos = (double[])view.Position;       // view origin (bounding-box center) in sheet coords

// View-relative coordinates (vertical break → X):
double viewRelLeft  = fOut[0] - fPos[0];  // negative (left of center)
double viewRelRight = fOut[2] - fPos[0];  // positive (right of center)
```

2. Pick break positions. For a part with features on both ends, keep ~35% on each side; shift the percentages toward whichever end the features actually cluster on.

```csharp
double viewWidth = viewRelRight - viewRelLeft;
double breakPos1 = viewRelLeft + viewWidth * 0.35;  // negative value
double breakPos2 = viewRelLeft + viewWidth * 0.65;  // positive value
```

3. Activate and select the view, then insert the break lines.

```csharp
swDraw.ActivateView(frontView.Name);
swExt.SelectByID2(frontView.Name, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);

object breakLineObj = frontView.InsertBreak3(
    2,           // swBreakLineVertical (horizontal long axis)
    breakPos1,   // first break line (view-relative, meters)
    breakPos2,   // second break line (view-relative, meters)
    3,           // swBreakLine_Curve — wavy default
    1,           // ShapeIntensity (1-5, only for Jagged style)
    false        // BreakSketchBlocks
);
```

4. Apply the break: clear, re-select the view, `BreakView()`, then clear and deactivate.

```csharp
swDrawModel.ClearSelection2(true);
swExt.SelectByID2(frontView.Name, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
swDraw.BreakView();
swDrawModel.ClearSelection2(true);
swDraw.ActivateView("");
```

For a horizontal break (`orientation == 1`, tall part), use the Y components of the outline instead — `viewRelLeft = fOut[1] - fPos[1]` and `viewRelRight = fOut[3] - fPos[1]` — and `Position1/Position2` are Y values.

### Full template (config + break + rebuild)

```csharp
var result = new Dictionary<string, object>();

ModelDoc2 swDrawModel = (ModelDoc2)swApp.ActiveDoc;
DrawingDoc swDraw = (DrawingDoc)swDrawModel;
ModelDocExtension swExt = swDrawModel.Extension;

// Get views (adjust traversal for your view order)
View sheetView = (View)swDraw.GetFirstView();   // sheet view
View frontView = (View)sheetView.GetNextView();  // first placed view
View rightView = (View)frontView.GetNextView();   // projected right
View topView   = (View)rightView.GetNextView();   // projected top

// === CONFIGURATION ===
int breakOrientation = 2;  // swBreakLineVertical (for horizontal long axis)
int breakStyle = 3;        // swBreakLine_Curve — wavy default
double keepLeftPct  = 0.35;  // keep 35% of left end
double keepRightPct = 0.35;  // keep 35% of right end
// Adjust these percentages based on feature locations

// === APPLY BREAK TO A VIEW ===
// Step 1: Calculate view-relative break positions
double[] outline = (double[])frontView.GetOutline();
double[] pos = (double[])frontView.Position;

double viewRelLeft, viewRelRight;
if (breakOrientation == 2) // vertical break
{
    viewRelLeft  = outline[0] - pos[0];  // X coords
    viewRelRight = outline[2] - pos[0];
}
else // horizontal break
{
    viewRelLeft  = outline[1] - pos[1];  // Y coords
    viewRelRight = outline[3] - pos[1];
}

double viewSpan = viewRelRight - viewRelLeft;
double breakPos1 = viewRelLeft + viewSpan * keepLeftPct;
double breakPos2 = viewRelLeft + viewSpan * (1.0 - keepRightPct);

// Step 2: Activate view and insert break lines
swDraw.ActivateView(frontView.Name);
swExt.SelectByID2(frontView.Name, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);

object breakLineObj = frontView.InsertBreak3(
    breakOrientation,  // swBreakLineVertical or swBreakLineHorizontal
    breakPos1,         // position of first break line (view-relative, meters)
    breakPos2,         // position of second break line (view-relative, meters)
    breakStyle,        // swBreakLineStyle_e value
    1,                 // ShapeIntensity (1-5, only for Jagged style)
    false              // BreakSketchBlocks
);

// Step 3: Apply the break
swDrawModel.ClearSelection2(true);
swExt.SelectByID2(frontView.Name, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
swDraw.BreakView();
swDrawModel.ClearSelection2(true);

// Step 4: Deactivate view
swDraw.ActivateView("");

// === REPEAT FOR OTHER VIEWS (e.g., Top View) ===
// Use the SAME percentage-based calculation for each view
// to keep break lines visually aligned across views

// === REBUILD AND RE-CENTER ===
swDrawModel.ForceRebuild3(true);

// Read new outlines (views are now shorter)
double[] fOut = (double[])frontView.GetOutline();
double fW = fOut[2] - fOut[0];
double fH = fOut[3] - fOut[1];
// ... read other view outlines ...

// Re-center views in usable area (same logic as initial placement)
// ... centering code ...

swDrawModel.ForceRebuild3(true);
swDrawModel.ViewZoomtofit2();
```

## How to: break multiple aligned views

When front and top (or front and side) both need breaks at the same location, break every view that shares the long axis at the same percentages so the break lines line up visually.

1. Use the **same percentage** for all views on the same long axis.
2. Compute positions independently per view — outlines may differ slightly.
3. Break one view at a time: insert → select → `BreakView` → clear → next view.
4. Re-center all views together only after every break is applied.

```csharp
// Process each view that needs a break
View[] viewsToBreak = { frontView, topView };
foreach (View v in viewsToBreak)
{
    double[] ol = (double[])v.GetOutline();
    double[] vp = (double[])v.Position;
    double relL = ol[0] - vp[0];
    double relR = ol[2] - vp[0];
    double span = relR - relL;
    double bp1 = relL + span * keepLeftPct;
    double bp2 = relL + span * (1.0 - keepRightPct);

    swDraw.ActivateView(v.Name);
    swExt.SelectByID2(v.Name, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
    v.InsertBreak3(breakOrientation, bp1, bp2, breakStyle, 1, false);

    swDrawModel.ClearSelection2(true);
    swExt.SelectByID2(v.Name, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
    swDraw.BreakView();
    swDrawModel.ClearSelection2(true);
}
swDraw.ActivateView("");
```

**Consistency rule — break EVERY view that needs it.** If you break one view of a long part, break every other view that shares the same long axis at the same percentages (or the matching absolute positions — see [How to: match break positions from a parent view](#how-to-match-break-positions-from-a-parent-view)). A broken front view pairs with a broken section, top, and right of the same long axis; the ISO view and any view on a perpendicular axis stay unbroken. Apply it all-or-nothing: either every long-axis view is broken or none are. (Mixing a broken front with an unbroken section/top/right makes the reader read two contradictory lengths for the same feature, breaks parallel projection lines, and breaks the dim plan.)

## How to: match break positions from a parent view

When a section view's breaks must line up exactly with its parent (front) view, read the parent's actual break-line positions and replicate them rather than recomputing from percentages. This works because section views inherit the parent's view origin and outline span, so `GetPosition(0/1)` returns view-relative coordinates that map 1:1 onto the section.

```csharp
// Pull the parent's break-line positions (view-relative, meters)
object[] parentBLs = (object[])frontView.GetBreakLines();
IBreakLine pbl = (IBreakLine)parentBLs[0];
double bp1 = pbl.GetPosition(0);
double bp2 = pbl.GetPosition(1);
int orientation = pbl.Orientation;   // re-use the parent's orientation
int style = pbl.Style;

// Apply the same view-relative positions to the section view
swDraw.ActivateView(sectionView.Name);
swExt.SelectByID2(sectionView.Name, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
sectionView.InsertBreak3(orientation, bp1, bp2, style, 1, false);

swDrawModel.ClearSelection2(true);
swExt.SelectByID2(sectionView.Name, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
swDraw.BreakView();
```

Replicate-from-parent for any view that has a parent break to copy; compute-from-percentage only for views with no parent break to read. (Recomputing both from percentages lets floating-point drift across the two outlines produce ~0.1–0.5 mm visual misalignment.)

## How to: order break vs detail views

If the drawing has both detail views AND a broken parent view, create the detail views FIRST against the unbroken parent, then apply `InsertBreak3` / `BreakView`. Detail boundaries lock to **model geometry**, not sketch space, so once a detail view exists it survives the subsequent break cleanly — the source view gets shorter while the detail keeps the right feature cluster.

Authoring order for a turned-part drawing with break + details:

```
1. Place orthographic views (front, top, right)
2. Insert section view (still unbroken)
3. Create ALL detail views off the unbroken section / front
4. Apply InsertBreak3 + BreakView to the section and any other long views
5. Re-center views (broken views are shorter)
6. Dimension (details first — see dimensioning-simple.md "Order rationale")
```

Dimension before or after the break is fine for the view that's broken — only the detail geometry must be authored before breaking. (The break collapses the parent's sketch space, so sheet coordinates inside the break gap no longer map intuitively to model geometry; drawing a detail-circle boundary after the break — especially a rectangular `swDetCirclePROFILE` — gives confusing coordinates and frequently fails silently.)

## How to: re-center after breaking

Broken views are shorter, so always re-center after applying breaks — and consider that you may now fit a **larger scale** since the views are shorter.

```csharp
swDrawModel.ForceRebuild3(true);

// Read new outlines (views are now shorter)
double[] fOut = (double[])frontView.GetOutline();
double fW = fOut[2] - fOut[0];
double fH = fOut[3] - fOut[1];
// ... read other view outlines, then re-center in the usable area ...

swDrawModel.ForceRebuild3(true);
swDrawModel.ViewZoomtofit2();
```

- Keep the same break percentages across aligned views for visual consistency.
- The break gap (zigzag width) is controlled by `View.BreakLineGap`; adjust it if breaking pushes the end view too far from the front view.

## How to: check break state

```csharp
// IView.IsBroken() — note: it's a METHOD, not a property
bool isBroken = view.IsBroken();

// Get break line count (has out parameter for array size)
int arraySize;
int breakCount = view.GetBreakLineCount2(out arraySize);

// Get break line objects
object[] breakLines = (object[])view.GetBreakLines();
IBreakLine bl = (IBreakLine)breakLines[0];
double pos0 = bl.GetPosition(0);  // first line position
double pos1 = bl.GetPosition(1);  // second line position
int style = bl.Style;
int orientation = bl.Orientation;
```

## How to: remove or modify a break

`UnBreakView()` removes the break while keeping the break-line features; to fully clean up, traverse the feature tree and delete the `"BreakLine"` features.

```csharp
// Unbreak a view
swExt.SelectByID2(view.Name, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
swDraw.UnBreakView();  // removes break but keeps break lines

// Delete break line features (to fully clean up)
// Traverse feature tree and delete BreakLine features
Feature feat = (Feature)swDrawModel.FirstFeature();
while (feat != null)
{
    Feature sub = (Feature)feat.GetFirstSubFeature();
    while (sub != null)
    {
        Feature subsub = (Feature)sub.GetFirstSubFeature();
        while (subsub != null)
        {
            if (subsub.GetTypeName2() == "BreakLine")
            {
                subsub.Select2(false, 0);
                swDrawModel.EditDelete();
                swDrawModel.ClearSelection2(true);
            }
            subsub = (Feature)subsub.GetNextSubFeature();
        }
        sub = (Feature)sub.GetNextSubFeature();
    }
    feat = (Feature)feat.GetNextFeature();
}
```

## Decision: when to break

| Condition | Action |
|---|---|
| Part fits well at 1:2 or larger without breaking | Don't break |
| Part needs 1:4+ to fit, featureless middle > 40% of length | Break |
| Features distributed evenly along length | Don't break — use full view |
| Part has 2–3 feature clusters with gaps | Consider multiple breaks |
| Section view needed through middle | Don't break that view (break the others) |

## Gotchas & fixes

- **To position break lines correctly: compute from the view outline relative to `View.Position` (the bounding-box center).** (Model-origin-relative coordinates, or assuming `Position` is the model-origin projection, land the break lines in the wrong place.)
- **To check whether a view is broken: call `IView.IsBroken()` — it's a method, not a property.** (Reading it as a property doesn't compile/bind.)
- **To get the break-line count: pass the `out int` argument, `GetBreakLineCount2(out size)`.** (Calling it with no args fails — it needs the out parameter for the array size.)
- **To set break positions: pass them straight into `InsertBreak3()`, which sets them at creation time.** (Calling `SetPosition()` afterward, or the older `InsertBreakVertical()` then `SetPosition`, is the fragile path.)
- **To actually shorten the view: after `InsertBreak3`, do `ClearSelection → Select the view → BreakView()`.** (Inserting the break lines alone leaves the view unbroken until `BreakView()` runs.)
- **To break a view: `SelectByID2(viewName, "DRAWINGVIEW", ...)` it first, and `ActivateView()` the target view before inserting.** (`BreakView()` with nothing selected, or inserting into a view that isn't active, no-ops.)
- **To keep breaks valid across scale changes: compute positions from the live view outlines.** (Hardcoded positions go wrong because the outline changes with scale.)
- **To keep aligned views consistent: break every long-axis view at the same percentages, all-or-nothing.** (A partly-broken set reads as two different lengths for one feature.)
- **To author detail geometry on a broken view: create the detail FIRST, then break.** (After the break, sketch-space coordinates inside the gap no longer map to model geometry and detail-boundary draws fail silently.)
- **To re-center after breaking: re-read outlines and reposition — broken views are shorter.** (Skipping the re-center leaves views off-center in the now-larger usable area.)
