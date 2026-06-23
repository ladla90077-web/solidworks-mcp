---
description: Change a drawing's paper size by re-running SetupSheet6 on the existing sheet with the new swDwgPaperSizes_e enum + the matching .slddrt format file, then ReloadTemplate(false) to swap the border/title block and purge stale old-format notes, and re-fit views. Includes the size↔format-file map.
---

# Guide: Change Paper Size

> Resize an existing drawing sheet: re-run `SetupSheet6` with the new paper-size enum and the **matching** format file, reload the template, then re-center and re-scale the views (resizing rescales nothing automatically).

---

## Recipe (happy path)

1. Look up the new size's `swDwgPaperSizes_e` enum and its matching `.slddrt` format file → [Size ↔ format file](#size-enum--format-file-must-match-or-the-border-is-wrong).
2. Re-run `SetupSheet6` on the existing sheet with that size + format file → [How to](#how-to-change-the-paper-size).
3. `ForceRebuild3(true)` → `ReloadTemplate(false)` (refresh border/title block **and purge stale old-format notes**) → `ForceRebuild3(true)`.
4. Re-center views from `GetOutline()` and `ViewZoomtofit2()`, and reset the scale yourself.

---

## API quick reference

### Size enum ↔ format file (must match, or the border is wrong)

| Size | Enum (`swDwgPaperSizes_e`) | Format file |
|---|---|---|
| A4 portrait | `swDwgPaperA4sizeVertical` | `a4 - iso.slddrt` |
| A4 landscape | `swDwgPaperA4size` | `a4 - iso.slddrt` |
| A3 | `swDwgPaperA3size` | `a3 - iso.slddrt` |
| A (letter) | `swDwgPaperAsize` | `a - landscape.slddrt` |
| B (tabloid) | `swDwgPaperBsize` | `b - landscape.slddrt` |

- `IDrawingDoc.SetupSheet6(name, paperSize, template, scale1, scale2, firstAngle, templateName, …)` — re-applies sheet setup to an existing sheet. `firstAngle = !thirdAngle`.
- Sheet-format directory: `swApp.GetUserPreferenceStringValue((int)swUserPreferenceStringValue_e.swFileLocationsSheetFormat)`.
- `ISheet.ReloadTemplate(loadNotes)` — refreshes the border/title block from the `.slddrt`. Pass **`false`** when resizing: `true` keeps the existing sheet's notes, so the old format's annotations linger on the new size; `false` reloads cleanly and purges those stale old-format notes.

---

## How to: change the paper size

Re-run `SetupSheet6` on the existing sheet with the new size enum + matching format file, reload, then re-fit views.

```csharp
var swDraw = (DrawingDoc)swApp.ActiveDoc;
var swModel = (ModelDoc2)swDraw;
string fmtDir = swApp.GetUserPreferenceStringValue(
    (int)swUserPreferenceStringValue_e.swFileLocationsSheetFormat);

swDraw.SetupSheet6(
    "Sheet1",
    (int)swDwgPaperSizes_e.swDwgPaperA3size,   // <-- new size
    (int)swDwgTemplates_e.swDwgTemplateCustom,
    1, 1,            // scale (use your chosen ratio)
    false,           // firstAngle = !thirdAngle
    fmtDir + "\\a3 - iso.slddrt",   // <-- format file MUST match the size
    0, 0, "", false, 0, 0, 0, 0, 0, 0);

swModel.ForceRebuild3(true);
((ISheet)swDraw.GetCurrentSheet()).ReloadTemplate(false);  // refresh border/title block + purge stale old-format notes
swModel.ForceRebuild3(true);
// then re-center views from GetOutline() and ViewZoomtofit2()
```

---

## Gotchas & fixes

- **Always call `ReloadTemplate` after resizing** — otherwise the old border/title block stays on the sheet at the previous size.
- **Pass `false`, not `true`, to `ReloadTemplate` when resizing.** `true` keeps the existing sheet's notes, so old-format annotations carry over and linger at the new size; `false` reloads the format cleanly and purges those stale notes.
- **Resizing rescales nothing automatically** — re-center the views (from `GetOutline()`) and reset the view scale yourself afterward.
- **For a custom size**, pass the width/height (in meters) in the trailing args and use `swDwgPapersUserDefined`.
