---
description: Quick recipe for a simple multi-view drawing — auto-scaled orthographic views, centered layout, hidden construction sketches, optional view rotation — in one execute_csharp_code call. The 'just drop 3 views' workflow.
---

# Quick Multi-View Drawing (Views Only)

> Drop standard orthographic views onto a sheet with proper scale, spacing, and clean geometry — front + projected right + projected top, auto-scaled and centered. Use when the user asks for "just views" (no dims, no GD&T, no title-block fill), for a quick visualization/review drawing, or as a starting point before annotating later. Target: under 90 seconds, ONE `execute_csharp_code` call. To add dimensions afterward, see `dimensioning-simple.md` (+ `dimensioning-systems.md` to pick a system, `manual-dimensioning.md` to dimension from scratch).

---

## Recipe (happy path)

Everything below goes in a single `execute_csharp_code`. No Phase-1 extraction needed.

1. **Get references + guard** — grab `ActiveDoc`; if it's already a drawing, close it back to the part → [How to: set up references and guards](#how-to-set-up-references-and-guards).
2. **Read the bounding box** — `PartDoc.GetPartBox(true)` for X/Y/Z extents → [How to: set up references and guards](#how-to-set-up-references-and-guards).
3. **Hide construction sketches in the part FIRST** — traverse features, `Feature.Select2` + `BlankSketch()` → [How to: hide construction geometry before the drawing](#how-to-hide-construction-geometry-before-the-drawing).
4. **Create the drawing + set up the sheet** — `NewDocument`, enable auto-scale, `SetupSheet6` → [How to: create the drawing and sheet](#how-to-create-the-drawing-and-sheet).
5. **Set units** — `SetUserPreferenceInteger(swUnitsLinear, …)` from the part's units → [How to: create the drawing and sheet](#how-to-create-the-drawing-and-sheet).
6. **Drop the standard views in one call — the robust default.** `Create3rdAngleViews2(modelPath)` (or `Create1stAngleViews2(modelPath)` for first-angle) places the full standard set — front + top + right, plus isometric — in a single call, each properly projected and linked at SolidWorks' default standard-3-view scale. Prefer this whenever the user just wants the standard three views → [How to: place and project views](#how-to-place-and-project-views).
7. **Only for non-standard view sets or per-view placement control** — place the front yourself with `CreateDrawViewFromModelView3(modelPath, "*Front", x, y, z)` (one view from a named orientation), then project each secondary view from it with `CreateUnfoldedViewAt3(x, y, z, false)` (front selected first) so they stay linked; never create right/top as standalone views. Keep SolidWorks' default scale unless the user specified one → [How to: place and project views](#how-to-place-and-project-views).
   - **Name every view** with `View.SetName2(...)` (`Front`, `Top`, `Right`, `Isometric`, `Section A-A`, …) right after creating it — for the one-call method, traverse and rename. Later steps address views by name → [How to: place and project views](#how-to-place-and-project-views).
8. **Read actual outlines, compute centered positions, reposition** — `View.GetOutline()` → set `View.Position` → [How to: center the layout from real outlines](#how-to-center-the-layout-from-real-outlines).
9. **(Optional) add center marks** — `ActivateView` each view, then `AutoInsertCenterMarks2(…)` for its holes/fillets/slots → [How to: add center marks](#how-to-add-center-marks).
10. **(Optional) rotate a view — only if the user explicitly asks.** Don't rotate by default; the standard front/top/right layout is correct as-projected. If you do rotate, remember it re-maps the projections (rotating the front 90° lands the right view where the top belongs) → [How to: rotate a placed view](#how-to-rotate-a-placed-view).
11. **Reset sketch visibility + rebuild** — `View.ResetSketchVisibility()` per view, `ForceRebuild3`, `ViewZoomtofit2` → [How to: center the layout from real outlines](#how-to-center-the-layout-from-real-outlines).

---

## API quick reference

**Paper size** — `SetupSheet6` paper-size argument:

| Request | Enum | Value | Format File |
|---------|------|-------|-------------|
| A4 landscape | `swDwgPaperA4size` | 6 | `a4 - iso.slddrt` |
| A4 portrait | `swDwgPaperA4sizeVertical` | 7 | `a4 - iso.slddrt` |
| A3 landscape | `swDwgPaperA3size` | 8 | `a3 - iso.slddrt` |
| A (letter) | `swDwgPaperAsize` | 0 | `a - landscape.slddrt` |
| B (tabloid) | `swDwgPaperBsize` | 2 | `b - landscape.slddrt` |

To **resize an existing sheet** later (re-run `SetupSheet6` with a new size + matching format file, reload, re-fit views), see `change-paper-size.md`.

**`swLengthUnit_e`** — read from `ModelDoc2.LengthUnit`; imperial when value is `3` (`swFEET`) or `4` (`swFEETINCHES`). Set on the drawing via `SetUserPreferenceInteger(swUnitsLinear, 0, …)`:

| Constant | Use |
|---|---|
| `swMM` | metric drawing units |
| `swINCHES` | imperial drawing units |

**`Feature.GetTypeName2()` → hide method** — what to call after selecting the feature:

| Sketch Type | TypeName | Hide Method |
|-------------|----------|-------------|
| 2D profile sketch | `ProfileFeature` | `feat.Select2(false, 0)` then `BlankSketch()` |
| 3D sketch (helix, guide) | `3DProfileFeature` | `feat.Select2(false, 0)` then `BlankSketch()` |
| Reference curve | `ReferenceCurve` | `feat.Select2(false, 0)` then `BlankRefGeom()` |
| Reference plane | `RefPlane` | `feat.Select2(false, 0)` then `BlankRefGeom()` |

**Key signatures:**

- `PartDoc.GetPartBox(bUseRefPlane)` → `double[6]` = `[xMin, yMin, zMin, xMax, yMax, zMax]` in meters.
- `DrawingDoc.SetupSheet6(name, paperSize, templateIn, scale1, scale2, firstAngle, templateName, width, height, propViewName, displayThirdAngle, custPropView, ...)` → `bool`. Pass `!thirdAngle` to the `firstAngle` slot (first-angle is the inverse of third-angle).
- `DrawingDoc.CreateDrawViewFromModelView3(ModelName, ViewName, LocX, LocY, LocZ)` → `View`. Creates **one** view from a named model orientation, e.g. `"*Front"`, `"*Top"`, `"*Right"`, `"*Isometric"`.
- `DrawingDoc.CreateUnfoldedViewAt3(X, Y, Z, NotAligned)` → `View`. Projects a new view from the currently selected parent view; call after `SelectByID2(parent.Name, "DRAWINGVIEW", …)`. Pass `NotAligned = false` to keep the projected view aligned to its parent.
- `DrawingDoc.Create3rdAngleViews2(ModelName)` / `DrawingDoc.Create1stAngleViews2(ModelName)` → `bool`. **One-call shortcut** that drops the three standard orthographic views (front + top + right, plus isometric) laid out for third- / first-angle projection, at SolidWorks' default standard-3-view scale. (The non-`2` `Create3rdAngleViews` / `Create1stAngleViews` are obsolete — use the `2` versions.)
- `View.SetName2(Name)` — renames the view; `View.GetName2()` / `View.Name` read it back. Name every view (`Front`, `Top`, `Right`, `Isometric`, `Section A-A`, …) right after creating it — later steps address views by name.
- `View.GetOutline()` → `double[4]` = `[xMin, yMin, xMax, yMax]` in sheet meters.
- `View.Position` — `double[3]` `{x, y, 0}` in sheet meters; the view's center point.
- `View.ResetSketchVisibility()` — re-applies part sketch visibility to the view.
- `ISheet.GetProperties2()` → `double[]`; index `5` = sheet width (m), index `6` = sheet height (m).
- `View.Angle` —  **Dont use this unless explicitly asked to rotate the views** **USE THIS ONLY IF REQUIRED BECAUSE IF YOU ROTATE TOP projected view will turn into right view and so on** -  **get/set** the view's rotation in **absolute radians** (`Math.PI / 2` = 90°; ignore the API doc's "degrees" note — it's wrong). Idempotent: set the final target angle once, not an increment. **Primary rotation method.**
- `swApp.SetUserPreferenceToggle(swAutomaticScaling3ViewDrawings, true)` — let SolidWorks auto-pick view scale.
- `swApp.GetUserPreferenceStringValue(swFileLocationsSheetFormat)` — folder holding the `.slddrt` format files.
- `View.AutoInsertCenterMarks2(InsertType, InsertOption, LinearSlotCenter, ArcSlotCenter, UseDocumentDefaults, Size, Gap, ExtendedLines, CenterLineFont, Angle)` → `bool`. Auto-inserts center marks on a view's features; **`ActivateView` the view first** (SW 2016+). `InsertType` = `swAutoInsertCenterMarkTypes_e` bitmask (`Hole`=1, `Fillets`=2, `Slots`=4). `InsertOption` = `swCenterMarkConnectionLine_e` bitmask (`ShowNoConnectLines`=0, `Linear`=1, `Circular`=2, `Radial`=4, `Base`=8). `UseDocumentDefaults=true` ignores `Size`/`Gap`/`ExtendedLines`/`CenterLineFont`. `Angle` in radians (+CCW).
- `DrawingDoc.InsertCenterMark3(Style, Propagate, Slot)` → `CenterMark`. One mark on the currently selected circular edge/arc. `Style` = `swCenterMarkStyle_e` (`NonAnnotation`=1, `Single`=2, `LinearGroup`=3, `CircularGroup`=4); `Propagate` applies to like features; `Slot` for slot marks. (`AddCenterMark`, `InsertCenterMark`/`2`, `AutoInsertCenterMarks` are obsolete.)
- `View.GetCenterMarkCount2(out int Size)` → `int`. Count of center-mark features in the view (use to verify after inserting).

**Layout constants** (defaults used in the recipe, meters):

| Constant | Value | Meaning |
|---|---|---|
| `titleBlockH` | `0.060` | 60 mm reserved at sheet bottom for title block |
| `border` | `0.012` | 12 mm sheet border |
| `gap` | `0.020` | ~20 mm between adjacent view edges |

---

## How to: set up references and guards

Grab the active document. If it's already a drawing (a stale one from a previous run), close it and fall back to the part so the rest of the recipe runs against part geometry.

```csharp
ModelDoc2 swPartModel = (ModelDoc2)swApp.ActiveDoc;
string modelPath = swPartModel.GetPathName();
if (swPartModel.GetType() == (int)swDocumentTypes_e.swDocDRAWING)
{
    swApp.CloseDoc(swPartModel.GetTitle());
    swPartModel = (ModelDoc2)swApp.ActiveDoc;
    modelPath = swPartModel.GetPathName();
}
bool isImperial = (swPartModel.LengthUnit == 3 || swPartModel.LengthUnit == 4);
```

Read the bounding box up front — the extents inform sheet/scale judgement even though auto-scale does the final sizing.

```csharp
PartDoc swPart = (PartDoc)swPartModel;
double[] bbox = (double[])swPart.GetPartBox(true);
double partW = bbox[3] - bbox[0]; // X extent in meters
double partH = bbox[4] - bbox[1]; // Y extent in meters
double partD = bbox[5] - bbox[2]; // Z extent in meters
```

---

## How to: hide construction geometry before the drawing

Hide loft/sweep/guide-curve sketches in the **part** before creating the drawing. (Left visible, `ProfileFeature` / `3DProfileFeature` sketches show in drawing views as dangling construction geometry — and you cannot hide them from the drawing context once the views exist.)

Traverse the feature tree and use `Feature.Select2(false, 0)` + `BlankSketch()` directly. (Use the traversal rather than `SelectByID2`: absorbed sketches — children of a loft/sweep — cannot be selected by name with type strings like `3DPROFILEFEAT` or `REFERENCECURVES`; that path silently fails. The direct `Feature.Select2` from the loop works reliably.)

```csharp
Feature feat = (Feature)swPartModel.FirstFeature();
while (feat != null)
{
    string typeName = feat.GetTypeName2();
    if (typeName == "ProfileFeature" || typeName == "3DProfileFeature")
    {
        feat.Select2(false, 0);
        swPartModel.BlankSketch();
        swPartModel.ClearSelection2(true);
    }
    feat = (Feature)feat.GetNextFeature();
}
swPartModel.ForceRebuild3(true);
```

For reference curves and planes, the same traversal applies — call `BlankRefGeom()` instead of `BlankSketch()` (see the [hide-method table](#api-quick-reference)).

**If you only notice the stray geometry after the drawing exists**, hide it retroactively:

1. `swApp.ActivateDoc3(partPath, false, 0, 0)`
2. Hide sketches there using the traversal loop above.
3. `swApp.ActivateDoc3(drawTitle, false, 0, 0)`
4. `ResetSketchVisibility()` on each view.
5. `ForceRebuild3(true)`

---

## How to: create the drawing and sheet

Create the drawing from the default template, **enable auto-scale**, then lay out the sheet. Let SolidWorks pick the best scale rather than forcing one.

```csharp
string template = swApp.GetDocumentTemplate(
    (int)swDocumentTypes_e.swDocDRAWING, "", 0, 0, 0);
ModelDoc2 swDrawModel = (ModelDoc2)swApp.NewDocument(template, 0, 0, 0);
DrawingDoc swDraw = (DrawingDoc)swDrawModel;
ModelDocExtension swExt = swDrawModel.Extension;

string formatPath = swApp.GetUserPreferenceStringValue(
    (int)swUserPreferenceStringValue_e.swFileLocationsSheetFormat);

// ENABLE auto-scale -- let SolidWorks pick the best scale
swApp.SetUserPreferenceToggle(
    (int)swUserPreferenceToggle_e.swAutomaticScaling3ViewDrawings, true);
```

Pick the paper size and format file from the [paper size table](#api-quick-reference), then call `SetupSheet6`. The `1, 1` scale is a placeholder — auto-scale overrides it per view.

```csharp
int paperSize = 7; // A4 portrait -- change per user request
string formatFile = "a4 - iso.slddrt";
bool thirdAngle = true;

bool ok = swDraw.SetupSheet6(
    "Sheet1", paperSize,
    (int)swDwgTemplates_e.swDwgTemplateCustom,
    1, 1,           // Scale 1:1 placeholder -- auto-scale overrides per view
    !thirdAngle,    // FirstAngle (inverted)
    formatPath + "\\" + formatFile,
    0, 0, "", false,
    0, 0, 0, 0, 0, 0);

swDrawModel.ForceRebuild3(true);
ISheet sheet = (ISheet)swDraw.GetCurrentSheet();
sheet.ReloadTemplate(true);
```

Set drawing units from the part's units (computed in [step 1](#how-to-set-up-references-and-guards)).

```csharp
if (isImperial)
    swDrawModel.Extension.SetUserPreferenceInteger(
        (int)swUserPreferenceIntegerValue_e.swUnitsLinear, 0, (int)swLengthUnit_e.swINCHES);
else
    swDrawModel.Extension.SetUserPreferenceInteger(
        (int)swUserPreferenceIntegerValue_e.swUnitsLinear, 0, (int)swLengthUnit_e.swMM);
```

---

## How to: place and project views

**Prefer linked views — unlinked views are usually not standard.** A linked (projected) view inherits its parent's scale, holds the orthographic alignment, and updates with the model; an unlinked/standalone view drifts out of alignment, can carry a mismatched scale, and breaks the projection relationship a reader expects. Both methods below produce linked views: the one-call `Create3rdAngleViews2`/`Create1stAngleViews2` links the whole standard set automatically, and the manual path links each secondary view by projecting it from the front with `CreateUnfoldedViewAt3`. Only create an unlinked view when the user explicitly asks for one.

**For a standard three-view drawing, prefer the single one-call method.** `Create3rdAngleViews2(modelPath)` (or `Create1stAngleViews2(modelPath)` for first-angle) drops the full standard set — front + top + right, plus isometric — in one call, each properly projected and linked to the front at SolidWorks' default standard-3-view scale. It's the robust default: less code, and none of the manual projection or alignment to get wrong.

```csharp
bool made = swDraw.Create3rdAngleViews2(modelPath); // or Create1stAngleViews2 for first-angle
swDrawModel.ForceRebuild3(true);
```

The standard layout SolidWorks applies is usually fine. If you do need to re-center it, traverse the sheet's views (`GetFirstView` returns the sheet — skip it) and read/set outlines per the [centering step](#how-to-center-the-layout-from-real-outlines). The one-call views come in with default names (`Drawing View1`, …); **traverse them and `SetName2` each to a meaningful name** (`Front`, `Top`, `Right`, `Isometric`) so later steps can address them — see [name your views](#how-to-place-and-project-views).

---

**For non-standard view sets or when you need per-view placement control, build the views yourself** — linked, projected views are still the standard. Place only the primary (front) view from a named model orientation; project every other view from it with `CreateUnfoldedViewAt3` (parent selected, `NotAligned = false`). Projected views stay *linked* to their parent: they inherit its scale, hold the orthographic alignment, and update together when the model or layout changes. Don't build the right/top as independent `CreateDrawViewFromModelView3` views — standalone views drift out of alignment, can carry a mismatched scale, and break the projection relationship a reader relies on.

Place the front view at a rough position — you reposition precisely in the next step once real outlines exist. **Let auto-scale pick the scale**: leave `UseSheetScale` at `0` and don't override `ScaleDecimal`. (Setting `UseSheetScale = 1` or forcing the sheet scale shrinks the views.)

```csharp
double[] sheetProps = (double[])sheet.GetProperties2();
double shW = sheetProps[5]; // width in meters
double shH = sheetProps[6]; // height in meters

// Place front view roughly -- will reposition after reading actual outlines
double frontX = shW * 0.35;
double frontY = shH * 0.35;

View frontView = (View)swDraw.CreateDrawViewFromModelView3(
    modelPath, "*Front", frontX, frontY, 0);
frontView.SetName2("Front"); // name every view — see "name your views" below
```

Project the secondary views from the front. Select the front view by name first, then `CreateUnfoldedViewAt3`. **Name each view as you create it** so later steps (selection, dimensioning) can address it by a meaningful name.

```csharp
View rightView = null, topView = null;
if (frontView != null)
{
    swExt.SelectByID2(frontView.Name, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
    rightView = (View)swDraw.CreateUnfoldedViewAt3(
        frontX + 0.10, frontY, 0, false);
    if (rightView != null) rightView.SetName2("Right");

    swDrawModel.ClearSelection2(true);
    swExt.SelectByID2(frontView.Name, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
    topView = (View)swDraw.CreateUnfoldedViewAt3(
        frontX, frontY + 0.10, 0, false);
    if (topView != null) topView.SetName2("Top");
}
```

**Name every view appropriately.** Whichever path you used, give each view a meaningful name with `IView.SetName2(...)` — `Front`, `Top`, `Right`, `Isometric` for the standard set, and a descriptive name for any extra view (e.g. `Section A-A`, `Detail B`). Don't leave the default `Drawing View1` / `Drawing View2` labels: every later step (selecting a view, projecting from it, dimensioning, skipping the title-block view) addresses views by name, and meaningful names make that reliable and the tree readable.

---

## How to: center the layout from real outlines

This is the critical step. Auto-scale sets the view size — read it with `GetOutline()`, then compute centered positions from those real footprints. (Hardcoding positions, or pre-computing scale before placing views, fights auto-scale; place first, measure, then position.)

```csharp
swDrawModel.ForceRebuild3(true);

double[] fOut = (double[])frontView.GetOutline(); // [xMin, yMin, xMax, yMax]
double fW = fOut[2] - fOut[0];
double fH = fOut[3] - fOut[1];

double[] rOut = (double[])rightView.GetOutline();
double rW = rOut[2] - rOut[0];

double[] tOut = (double[])topView.GetOutline();
double tH = tOut[3] - tOut[1];

// Layout constants
double titleBlockH = 0.060; // 60mm for title block
double border = 0.012;
double gap = 0.020;         // ~20mm between view edges

// Usable area
double usableMinX = border;
double usableMaxX = shW - border;
double usableMinY = border + titleBlockH;
double usableMaxY = shH - border;

// Total footprint
double totalW = fW + gap + rW;
double totalH = fH + gap + tH;

// Center in usable area
double cx = (usableMinX + usableMaxX) / 2.0;
double cy = (usableMinY + usableMaxY) / 2.0;

double newFrontX = cx - totalW / 2.0 + fW / 2.0;
double newFrontY = cy - totalH / 2.0 + fH / 2.0;
double newRightX = newFrontX + fW / 2.0 + gap + rW / 2.0;
double newRightY = newFrontY;
double newTopX = newFrontX;
double newTopY = newFrontY + fH / 2.0 + gap + tH / 2.0;

frontView.Position = new double[] { newFrontX, newFrontY, 0 };
rightView.Position = new double[] { newRightX, newRightY, 0 };
topView.Position = new double[] { newTopX, newTopY, 0 };
```

**Centering strategy:** compute the total footprint of all views + gaps, then center that rectangle in the usable area (sheet minus border minus title block). To fix a layout that doesn't fit, reposition the views or pick a larger sheet — keep the scale auto-picked rather than shrinking it.

Finally, reset sketch visibility on each view (so part-level hides take effect) and rebuild/zoom-to-fit.

```csharp
View vv = (View)swDraw.GetFirstView();
vv = (View)vv.GetNextView();
while (vv != null)
{
    vv.ResetSketchVisibility();
    vv = (View)vv.GetNextView();
}
swDrawModel.ForceRebuild3(true);
swDrawModel.ViewZoomtofit2();
```

### Layout reference (from a real user drawing)

A4 portrait drawing of a 70×100×70 mm lofted hex part:

- **Views at 1:1** (auto-scale picked 1:1), `UseSheetScale = 0`.
- **Front:** center (74, 118) mm, bbox 64×58 mm.
- **Right:** center (158, 118) mm — 20 mm gap from front edge.
- **Top:** center (74, 232) mm — 52 mm gap from front edge (more vertical breathing room).
- **Title block clearance:** front bottom edge at Y = 89 mm, well above the 60 mm title-block zone.
- Views fill the sheet well — no cramming, no wasted space.

### Layout rules of thumb

| Sheet | Orientation | Title Block Reserve (from bottom) | Border |
|-------|------------|-----------------------------------|--------|
| A4 | Portrait | 60 mm | 12 mm |
| A4 | Landscape | 55 mm | 12 mm |
| A3 | Landscape | 60 mm | 12 mm |
| A2+ | Landscape | 70 mm | 12 mm |

**View gaps:** ~20 mm between adjacent view edges. Matches professional drawings and leaves room for future dimensions.

---

## How to: add center marks

Center marks mark hole / arc / slot centers. Add them per view — **`ActivateView` the target view first**; the call inserts into the *active* view, not the one whose entities you selected (SW 2016+).

Bulk — auto-insert on every hole in a view:

```csharp
swDraw.ActivateView(view.Name);   // REQUIRED: target view must be active first

bool ok = view.AutoInsertCenterMarks2(
    (int)swAutoInsertCenterMarkTypes_e.swAutoInsertCenterMarkType_Hole, // InsertType bitmask: Hole=1 | Fillets=2 | Slots=4
    (int)swCenterMarkConnectionLine_e.swCenterMark_ShowNoConnectLines,  // InsertOption bitmask: None=0 | Linear=1 | Circular=2 | Radial=4 | Base=8
    false,   // LinearSlotCenter — true = slot centers, false = slot ends
    false,   // ArcSlotCenter    — true = arc centers,  false = arc ends
    true,    // UseDocumentDefaults — true => Size/Gap/ExtendedLines/CenterLineFont/Angle below are ignored
    0.0,     // Size  (only when UseDocumentDefaults = false)
    0.0,     // Gap   (only when UseDocumentDefaults = false)
    false,   // ExtendedLines
    false,   // CenterLineFont
    0.0);    // Angle (radians, +CCW)
```

Mark every feature type at once by OR-ing the bitmask: `swAutoInsertCenterMarkType_Hole | swAutoInsertCenterMarkType_Fillets | swAutoInsertCenterMarkType_Slots` (`1|2|4` = `7`).

Single — one mark on a selected circular edge/arc:

```csharp
swModel.ClearSelection2(true);
view.SelectEntity(circularEdge, false);   // or SelectByID2(…, "EDGE", …)
CenterMark cm = (CenterMark)swDraw.InsertCenterMark3(
    (int)swCenterMarkStyle_e.swCenterMark_Single, // NonAnnotation=1, Single=2, LinearGroup=3, CircularGroup=4
    false,   // Propagate — true applies to like features
    false);  // Slot — true for slot center marks
```

Verify: `int n = view.GetCenterMarkCount2(out int size);`.

**Don't sketch center marks by hand.** Use `AutoInsertCenterMarks2` / `InsertCenterMark3` — never draw them as manual sketch lines. If it doesnt work leave it.

## Gotchas & fixes

- **For the standard three views, prefer the one call.** `Create3rdAngleViews2(modelPath)` / `Create1stAngleViews2(modelPath)` drops the whole standard set in a single call, properly projected and linked — fewer moving parts than placing and projecting by hand. Only drop to the manual path (`CreateDrawViewFromModelView3("*Front", …)` + `CreateUnfoldedViewAt3`) for non-standard view sets or when you need per-view placement control.
- **Name every view with `SetName2` — don't ship `Drawing View1` labels.** Give each view a meaningful name (`Front`, `Top`, `Right`, `Isometric`, `Section A-A`, …) right after creating it; for the one-call method, traverse the views and rename. Every later step selects views by name, so meaningful names keep selection/projection/dimensioning reliable and the tree readable.
- **When you do build views by hand, project linked from the front — never standalone.** Place only the front from a named orientation; create right/top with `CreateUnfoldedViewAt3` (`NotAligned = false`) so they stay linked to the parent — shared scale, locked alignment, and they update together. Independent `CreateDrawViewFromModelView3` views for right/top drift, mismatch scales, and break the projection a reader expects. Linked, projected views are the drawing standard.
- **Prefer SolidWorks' default (auto) scale unless the user specified one.** Leave `UseSheetScale = 0` and don't override `ScaleDecimal`; forcing the sheet scale shrinks the views (setting `UseSheetScale = 1` is the classic cause of tiny views). Set an explicit scale only when the user asked for one.
- **Place views, read `GetOutline()`, then position.** Don't pre-compute scale before placing views or hardcode view positions — auto-scale decides the size, so measure the real outline first and center from that.
- **Hide construction sketches in the part before creating the drawing.** You can't hide them from the drawing context once views exist; left visible they appear as dangling construction geometry. If you forgot, hide retroactively via `ActivateDoc3` → traversal → `ResetSketchVisibility` (see [How to: hide construction geometry](#how-to-hide-construction-geometry-before-the-drawing)).
- **Select absorbed sketches via `Feature.Select2()` from the traversal loop.** `SelectByID2` with type strings like `3DPROFILEFEAT` / `REFERENCECURVES` silently fails on loft/sweep child sketches.
- **Do the whole 3-view job in one `execute_csharp_code` call.** Splitting a simple views-only drawing across multiple calls adds round-trips for no benefit.
- **To fix a cramped layout, reposition views or pick a larger sheet** — don't change the scale to "fix" it, or you lose the auto-picked sizing.
- **`ActivateView` before `AutoInsertCenterMarks2`** — it inserts into the *active* view, not the one whose entities you selected; skip the activation and it targets the wrong view. For one mark on one feature, select the circular edge and use `InsertCenterMark3` instead. See [How to: add center marks](#how-to-add-center-marks).
- **Don't rotate views unless the user asks.** The standard front/right/top layout is correct as-projected; an unrequested rotation breaks it. And a rotation carries the projections with it — turn the front 90° and the right view ends up showing what the top view did.
- **Rotate via `IView.Angle` (radians), not and select the view first do this only if required because this requires recalibrating view projection strategy right view will become top after rotating pi/2.
- **Verify a rotation took before screenshotting.** Read `GetOutline()` after rotating and assert the footprint flipped (`w` ↔ `h`) — this catches the silent no-op cheaply.
- **Run `ResetSketchVisibility()` on each view after hiding sketches in the part** — otherwise the part-level hide doesn't propagate to the existing drawing views.
- **Don't trust the feature-tree view *type* label under first-angle.** With `firstAngle = true`, `CreateDrawViewFromModelView3(..., "*Front", ...)` may register the view as **Auxiliary** in the tree (cosmetic only — it's still your front view), and projected children of a model containing a `RevCut` can be classified **Section**. The labels don't mean what they say here; key off the view's name/role you assigned, not the tree's type string.
