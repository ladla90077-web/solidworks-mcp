---
description: C# template for creating an assembly drawing — isometric view, BOM table, auto-balloons, optional section view, title block — in one execute_csharp_code call. Assembly drawings use BOM + balloons, not dimensions.
---

# Guide: Create Assembly Drawing

> Build an assembly drawing — isometric view, BOM, auto-balloons, optional section view — in a single `execute_csharp_code` call, then fill the title block in a second call. Assembly drawings document *what parts go where* with a BOM + balloons rather than dimensions.

## Recipe (happy path)

1. **Create the drawing doc** from the drawing template → `swApp.NewDocument(...)` → [How to: create + format the sheet](#how-to-create--format-the-sheet).
2. **Apply the sheet format** with `SetupSheet6(... swDwgTemplateCustom ...)` + `ReloadTemplate(true)`, then verify by counting notes → [How to: create + format the sheet](#how-to-create--format-the-sheet).
3. **Set units + enable auto-scale** to match the assembly's unit system → [How to: set units](#how-to-set-units--auto-scale).
4. **Place the isometric view** (the primary assembly view) with `CreateDrawViewFromModelView3(...)` → [How to: place views](#how-to-place-views--snap-to-a-clean-scale).
5. **Snap the sheet scale** to a clean integer and pin `UseSheetScale` on every view → [How to: place views](#how-to-place-views--snap-to-a-clean-scale).
6. **Insert the BOM table** with `InsertBomTable6(...)` after selecting the view → [How to: insert the BOM](#how-to-insert-the-bom-table).
7. **Insert auto-balloons** with `AutoBalloon5(...)` after `ActivateView` + `SelectByID2` → [How to: insert balloons](#how-to-insert-auto-balloons).
8. *(Optional)* **Add a section view** to expose internal interfaces → [How to: add a section view](#how-to-add-a-section-view-optional).
9. **Rebuild + zoom to fit**, then log the title-block schema for Call 2 → [How to: hand off the title block](#how-to-hand-off-the-title-block-call-2).

---

## API quick reference

**Coordinates & units**

- All positions are in **meters**.
- `view.GetOutline()` → `[xMin, yMin, xMax, yMax]` in **sheet** coords.
- Section line endpoints: **view-sketch** coords (apply `ModelToSketchTransform`).
- `CreateSectionViewAt5` position: **sheet** coords.

**`SetupSheet6(name, paperSize, templateType, scale1, scale2, firstAngle, templateName, ...)`** — key args:
- `paperSize` — `swDwgPaperSizes_e` (e.g. `swDwgPaperA3size`).
- `templateType` — `swDwgTemplates_e`; **must be `swDwgTemplateCustom`** for `templateName` to apply. `swDwgTemplateNone` silently ignores the path.
- `firstAngle` — pass `!thirdAngle` (true = first-angle projection).
- `templateName` — full path to the `.slddrt` sheet format.

**`swDwgPaperSizes_e`** — `swDwgPaperA3size` (one of many; pick per the chosen paper).

**`swDwgTemplates_e`**:

| Constant | Use |
|---|---|
| `swDwgTemplateCustom` | required so `SetupSheet6`/`SetTemplateName` honor the custom `.slddrt` path |
| `swDwgTemplateNone` | no sheet format — silently ignores any path passed |

**`swBomType_e`** (pass as `(int)`):

| Value | Constant | Meaning |
|---|---|---|
| 1 | `swBomType_TopLevelOnly` | top-level components only |
| 2 | `swBomType_PartsOnly` | flattened parts list (default for assembly drawings) |
| 3 | `swBomType_Indented` | indented sub-assembly hierarchy |

**`InsertBomTable6(useAnchor, x, y, anchorType, bomType, configName, tableTemplate, hidden, indentedNumbering, detailedCutList, version, displayDeleted)`** — insert on a selected view; positions in meters.

**`swBOMConfigurationAnchorType_e`** — `swBOMConfigurationAnchor_TopLeft` (and the other three corners).

**`AutoBalloonOptions`** (from `swExt.CreateAutoBalloonOptions()`) — drives `AutoBalloon5(options)`:

| Property | Enum / type | Notes |
|---|---|---|
| `Layout` | `swBalloonLayoutType_e` | e.g. `swDetailingBalloonLayout_Square` |
| `Style` | `swBalloonStyle_e` | e.g. `swBS_Circular` |
| `Size` | `swBalloonFit_e` | e.g. `swBF_3Chars` |
| `UpperTextContent` | `swBalloonTextContent_e` | e.g. `swBalloonTextItemNumber` |
| `ReverseDirection` | bool | balloon walk direction |
| `IgnoreMultiple` | bool | one balloon per component instance |
| `InsertMagneticLine` | bool | aligns balloons on a magnetic line |
| `LeaderAttachmentToFaces` | bool | attach leaders to faces vs edges |
| `ShowQuantity` | bool | append qty to balloon text |
| `ItemNumberStart` / `ItemNumberIncrement` | int | numbering sequence |

**`CreateSectionViewAt5(x, y, z, sectionLabel, ...)`** — position in **sheet** coords; returns the new section `View`. Configure the result via `IDrSection` (e.g. `SetAutoHatch(true)`).

**`AutoInsertCenterMarks2`** — takes **10** parameters; `ActivateView` the target view first.

---

## How to: create + format the sheet

```csharp
// ════════════════════════════════════════════════════════
// INPUTS — set these based on Phase 1 plan
// ════════════════════════════════════════════════════════
ModelDoc2 swAssyModel = (ModelDoc2)swApp.ActiveDoc;
string modelPath = swAssyModel.GetPathName();
string config = swAssyModel.ConfigurationManager.ActiveConfiguration.Name;

int paperSize = (int)swDwgPaperSizes_e.swDwgPaperA3size;
string sheetFormatFile = "a3 - iso.slddrt";
bool thirdAngle = true;

// Isometric is the primary view for assemblies
// Optionally add one orthographic for section/internal structure
double isoX = 0.20, isoY = 0.16;
double orthoX = 0.12, orthoY = 0.16; // if needed

// ════════════════════════════════════════════════════════
// 1. CREATE DRAWING
// ════════════════════════════════════════════════════════
string template = swApp.GetDocumentTemplate((int)swDocumentTypes_e.swDocDRAWING, "", 0, 0, 0);
ModelDoc2 swDrawModel = (ModelDoc2)swApp.NewDocument(template, 0, 0, 0);
DrawingDoc swDraw = (DrawingDoc)swDrawModel;
ModelDocExtension swExt = swDrawModel.Extension;

// ════════════════════════════════════════════════════════
// 2. APPLY SHEET FORMAT
// ════════════════════════════════════════════════════════
string formatPath = swApp.GetUserPreferenceStringValue(
    (int)swUserPreferenceStringValue_e.swFileLocationsSheetFormat);
// Loading a custom .slddrt needs TemplateCustom + ReloadTemplate(TRUE) (see Gotchas).
bool ok = swDraw.SetupSheet6("Sheet1", paperSize,
    (int)swDwgTemplates_e.swDwgTemplateCustom,      // MUST be Custom for SetTemplateName / TemplateName to apply
    1, 1, !thirdAngle,
    formatPath + "\\" + sheetFormatFile,
    0, 0, "", false, 0, 0, 0, 0, 0, 0);
if (!ok) throw new InvalidOperationException("SetupSheet6 returned false");
swDrawModel.ForceRebuild3(true);
ISheet sheet = (ISheet)swDraw.GetCurrentSheet();
sheet.ReloadTemplate(true);                          // MUST be true — false reuses empty cache

// Verify the format actually loaded: no real sheet format has 0 notes.
View sheetView = (View)swDraw.GetFirstView();
int nNotes = 0; Note n = (Note)sheetView.GetFirstNote();
while (n != null) { nNotes++; n = (Note)n.GetNext(); }
if (nNotes == 0) throw new InvalidOperationException("Sheet format loaded 0 notes — silent load failure");
```

Counting notes is the load check — see `quick_multi_view_drawing.md` → Step 4 for the same verify pattern.

---

## How to: set units + auto-scale

Mirror the assembly's unit system onto the drawing, then enable automatic scaling so the first 3-view placement picks a sensible scale.

```csharp
// ════════════════════════════════════════════════════════
// 3. SET UNITS + ENABLE AUTO-SCALE
// ════════════════════════════════════════════════════════
bool isImperial = swAssyModel.LengthUnit == 3;   // swINCHES == 3
if (isImperial)
{
    swDrawModel.Extension.SetUserPreferenceInteger(
        (int)swUserPreferenceIntegerValue_e.swUnitsLinear, 0, (int)swLengthUnit_e.swINCHES);
    swDrawModel.Extension.SetUserPreferenceInteger(
        (int)swUserPreferenceIntegerValue_e.swUnitSystem, 0, (int)swUnitSystem_e.swUnitSystem_IPS);
}
else
{
    swDrawModel.Extension.SetUserPreferenceInteger(
        (int)swUserPreferenceIntegerValue_e.swUnitsLinear, 0, (int)swLengthUnit_e.swMM);
    swDrawModel.Extension.SetUserPreferenceInteger(
        (int)swUserPreferenceIntegerValue_e.swUnitSystem, 0, (int)swUnitSystem_e.swUnitSystem_MMGS);
}
swApp.SetUserPreferenceToggle(
    (int)swUserPreferenceToggle_e.swAutomaticScaling3ViewDrawings, true);
```

---

## How to: place views + snap to a clean scale

The isometric is the primary view for an assembly. Add at most one orthographic if you need it to host a section view.

```csharp
// ════════════════════════════════════════════════════════
// 4. PLACE VIEWS
// ════════════════════════════════════════════════════════

// Isometric — primary view for assemblies
View isoView = (View)swDraw.CreateDrawViewFromModelView3(
    modelPath, "*Isometric", isoX, isoY, 0);

// Optional: one orthographic view for section/internal structure
// View frontView = (View)swDraw.CreateDrawViewFromModelView3(
//     modelPath, "*Front", orthoX, orthoY, 0);

// ════════════════════════════════════════════════════════
// 5. ADJUST SCALE TO CLEAN INTEGER
// ════════════════════════════════════════════════════════
double finalScale = 1.0;
if (isoView != null)
{
    double autoScale = isoView.ScaleDecimal;
    double[] cleanScales = { 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 10.0 };
    double bestScale = cleanScales[0];
    foreach (double cs in cleanScales)
        if (cs <= autoScale) bestScale = cs;
    finalScale = bestScale;

    if (Math.Abs(bestScale - autoScale) > 0.001)
    {
        Sheet sheet = (Sheet)swDraw.GetCurrentSheet();
        double num = bestScale >= 1.0 ? bestScale : 1.0;
        double den = bestScale >= 1.0 ? 1.0 : 1.0 / bestScale;
        sheet.SetScale(num, den, false, false);
        isoView.UseSheetScale = 1;   // pin EVERY view to the sheet scale after changing it
    }
}
```

---

## How to: insert the BOM table

Select the view first, then insert. For assembly drawings, `swBomType_PartsOnly` (flattened parts list) is the usual choice.

```csharp
// ════════════════════════════════════════════════════════
// 6. INSERT BOM TABLE
// ════════════════════════════════════════════════════════
// BOM types: swBomType_TopLevelOnly=1, swBomType_PartsOnly=2, swBomType_Indented=3
if (isoView != null)
{
    swExt.SelectByID2(isoView.Name, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
    object bomObj = isoView.InsertBomTable6(
        false,      // don't use anchor
        0.05, 0.27, // position (meters)
        (int)swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_TopLeft,
        (int)swBomType_e.swBomType_PartsOnly,
        config, "", false, 0, false, false, false);
}
```

---

## How to: insert auto-balloons

`ActivateView` **and** `SelectByID2` the view before `AutoBalloon5` — balloons attach to the active view.

```csharp
// ════════════════════════════════════════════════════════
// 7. INSERT AUTO-BALLOONS
// ════════════════════════════════════════════════════════
if (isoView != null)
{
    swExt.SelectByID2(isoView.Name, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
    swDraw.ActivateView(isoView.Name);

    AutoBalloonOptions balloonOpts = swExt.CreateAutoBalloonOptions();
    balloonOpts.Layout = (int)swBalloonLayoutType_e.swDetailingBalloonLayout_Square;
    balloonOpts.ReverseDirection = false;
    balloonOpts.IgnoreMultiple = true;
    balloonOpts.InsertMagneticLine = true;
    balloonOpts.LeaderAttachmentToFaces = true;
    balloonOpts.Style = (int)swBalloonStyle_e.swBS_Circular;
    balloonOpts.Size = (int)swBalloonFit_e.swBF_3Chars;
    balloonOpts.UpperTextContent = (int)swBalloonTextContent_e.swBalloonTextItemNumber;
    balloonOpts.UpperText = "";
    balloonOpts.ShowQuantity = false;
    balloonOpts.ItemNumberStart = 1;
    balloonOpts.ItemNumberIncrement = 1;

    swDraw.AutoBalloon5(balloonOpts);
}

// ════════════════════════════════════════════════════════
// 8. REBUILD + ZOOM TO FIT
// ════════════════════════════════════════════════════════
swDrawModel.ForceRebuild3(true);
swDrawModel.ViewZoomtofit2();
swDrawModel.ClearSelection2(true);

var result = new Dictionary<string, object>();
result["status"] = "Assembly drawing created";
result["sheetScale"] = finalScale;
result["viewCount"] = swDraw.GetViewCount();
result["isoViewName"] = isoView?.Name;
return result;
```

---

## How to: add a section view (optional)

Use a section view to expose internal interfaces. Add an orthographic parent view first, draw the section line in the **view-sketch** coords, then create the section in **sheet** coords. For the full section-view toolkit (section types, option bitmask, `IDrSection` members, placement math), see `section-views.md`.

```csharp
// Add an orthographic view first, then create section through it
// Section line in VIEW SKETCH coords, CreateSectionViewAt5 in SHEET coords
View parentView = frontView; // the orthographic view
double[] outline = (double[])parentView.GetOutline();
double centerX = (outline[0] + outline[2]) / 2;
double centerY = (outline[1] + outline[3]) / 2;
double halfW = (outline[2] - outline[0]) / 2;

Sketch viewSketch = parentView.GetSketch();
MathTransform sketchXform = viewSketch.ModelToSketchTransform;
MathUtility mathUtils = (MathUtility)swApp.GetMathUtility();

double[] startPt = new double[] { centerX - halfW * 0.8, centerY, 0 };
double[] endPt = new double[] { centerX + halfW * 0.8, centerY, 0 };
MathPoint mStart = (MathPoint)mathUtils.CreatePoint(startPt);
MathPoint mEnd = (MathPoint)mathUtils.CreatePoint(endPt);
mStart = (MathPoint)mStart.MultiplyTransform(sketchXform);
mEnd = (MathPoint)mEnd.MultiplyTransform(sketchXform);
double[] tS = (double[])mStart.ArrayData;
double[] tE = (double[])mEnd.ArrayData;

swDraw.ActivateView(parentView.GetName2());
swDrawModel.ClearSelection2(true);
SketchManager skMgr = swDrawModel.SketchManager;
skMgr.AddToDB = true;
SketchSegment line = skMgr.CreateLine(tS[0], tS[1], tS[2], tE[0], tE[1], tE[2]);
skMgr.AddToDB = false;

line.Select4(false, null);
View sectionView = (View)swDraw.CreateSectionViewAt5(
    centerX, outline[1] - 0.08, 0, "A", 0, null, 0);
if (sectionView != null)
{
    DrSection sec = (DrSection)sectionView.GetSection();
    if (sec != null) sec.SetAutoHatch(true);
}
swDrawModel.EditRebuild3();
```

---

## How to: hand off the title block (Call 2)

The title block is filled in a **separate** `execute_csharp_code` call.

1. **End of Call 1 — read the schema.** Before returning, enter template mode, dump each note's text + extent, then exit. This gives Call 2 the placeholder names and box widths it needs. See `title-block.md` → **Read pass**.
2. **Call 2 — fill the fields.** Use the schema logged at the end of Call 1 to build the field map and write the values. See `title-block.md` → **Fill pass**.

---

## Gotchas & fixes

- **To make a custom sheet format actually load:** pass `swDwgTemplateCustom` to `SetupSheet6` **and** call `sheet.ReloadTemplate(true)`. (`swDwgTemplateNone` silently ignores the path; `ReloadTemplate(false)` reuses an empty cache — both leave you with a blank format.)
- **To confirm the format loaded, count the notes** on the first view — throw if it's 0. (A silent load failure produces a sheet with 0 notes; no real sheet format is empty.)
- **To keep all views at the chosen scale, set `UseSheetScale = 1` on every view** after changing the sheet scale. (Views created before the scale change keep their own scale otherwise, so they render at the wrong size.)
- **To insert a BOM, `SelectByID2` the view first**, then call `InsertBomTable6`. (With nothing selected the table has no host view and the call no-ops.)
- **To insert balloons, `ActivateView` AND `SelectByID2` the view before `AutoBalloon5`.** (Balloons attach to the active view; skipping either leaves them on the wrong view or none at all.)
- **To insert center marks, call `AutoInsertCenterMarks2` with all 10 parameters after `ActivateView`.** (The 5-arg form `(true, true, false, 0, true)` does not exist; calling without an active view targets the wrong view.)
- **Dimension assembly drawings with BOM + balloons, not dimensions.** (Assembly drawings communicate part identity and placement; linear dims belong on the part drawings instead.)
