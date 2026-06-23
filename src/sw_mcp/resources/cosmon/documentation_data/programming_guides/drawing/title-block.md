---
description: Read a title block's fields and fill them by the right mechanism — property-linked notes ($PRP/$PRPSHEET), free-text notes, or the Title Block Fields feature. Covers the Read/Fill two-pass flow, ReloadTemplate stale-note cleanup, the "X in a box" link-error marker, and text-overflow shrink-to-fit.
---

# Guide: Title Block

> Read a title block's fields, classify each by its fill mechanism, and fill each through the right path. Most fields in a modern sheet format fill by writing **custom properties** and letting linked notes auto-resolve — not by editing notes. Run after `quick_multi_view_drawing.md` or `create-assembly-drawing.md`.

---

## Recipe (happy path)

Two passes — Read at the end of Call 1, Fill in a separate Call 2 (the long template-edit session can't coexist with view/dimension/BOM work).

1. **Only if you swapped sheet formats** (a second `SetupSheet6`): call `ReloadTemplate(false)` once, before reading, to purge stale notes → [How to: clean up stale notes](#how-to-clean-up-stale-notes-after-a-format-swap).
2. **Read pass (end of Call 1):** `EditTemplate()` → dump every note classified `$PRP` / `$PRPSHEET` / free-text / `[tbf]` → `EditSheet()` → [How to: read & classify](#how-to-read--classify-every-note-read-pass).
3. **Fill — properties:** write custom properties for every `$PRP`/`$PRPSHEET` note (covers ~80% of fields) → [How to: fill](#how-to-fill-the-title-block-fill-pass--call-2).
4. **Fill — free text:** overwrite literal placeholders with the shrink-to-fit loop.
5. **Fill — TBF:** iterate `sheet.TitleBlock.GetNotes()` if the schema showed `[tbf]` entries.
6. **Rebuild + verify:** `ForceRebuild3(true)`, then re-read the notes to confirm every linked reference resolved.

---

## API quick reference

### The three fill mechanisms

| # | Mechanism | How the agent fills it | When it's used |
|---|---|---|---|
| 1 | **Property-linked note** (`$PRP:"X"` / `$PRPSHEET:"X"`) — the note contains a reference like `$PRPSHEET:"Description"` | Write the referenced **custom property** on the drawing (`$PRP`) or on the referenced model (`$PRPSHEET`); let the note resolve on rebuild. | ~80% of fields in a well-designed modern sheet format |
| 2 | **Free-text note** — the note contains a literal placeholder like `"TITLE"`, `"DWG. NO."`, or is blank | `EditTemplate()` → match the note → `SetText(newValue)` → `EditSheet()` | Legacy templates, hand-authored sheet formats, or fields the author left un-linked |
| 3 | **Title Block Fields feature** (`ISheet.TitleBlock`, SW 2015+) — sheet format has a dedicated titleblock region with named fields | Access `sheet.TitleBlock` and iterate its notes. No `EditTemplate()` required. | Newer sheet formats authored with "Define Title Block Fields" |

`$PRPSHEET` pulls from the **model shown in the view specified under Sheet Properties** (default: first view on the sheet). `$PRP` pulls from the drawing document itself.

### Standard property-name map (cheat sheet)

Property names mainstream SolidWorks sheet formats (ANSI and ISO) link to by default. Write these as custom properties and the linked notes resolve. If your format uses different names, the Read pass surfaces them.

| Title block field | Property name | Set on | Linked via |
|---|---|---|---|
| TITLE / description | `Description` | **Model** (part/assembly) | `$PRPSHEET:"Description"` |
| DWG. NO. / part number | `PartNo` *or* `Number` | **Model** | `$PRPSHEET:"PartNo"` |
| DWG. NO. (as filename) | `SW-File Name` | system (auto) | built-in |
| MATERIAL | `Material` | **Model** | `$PRPSHEET:"Material"` (often resolves from `SW-Material`) |
| WEIGHT / MASS | `Weight` | **Model** | `$PRPSHEET:"Weight"` (often `SW-Mass`) |
| FINISH | `Finish` | **Model** | `$PRPSHEET:"Finish"` |
| TREATMENT | `Treatment` | **Model** | `$PRPSHEET:"Treatment"` |
| REV / REVISION | `Revision` | **Model** or **Drawing** | `$PRPSHEET` or `$PRP` |
| SCALE | `SW-Sheet Scale` | system (auto) | built-in |
| SHEET (x of n) | `SW-Current Sheet` / `SW-Total Sheets` | system (auto) | built-in |
| COMPANY | `CompanyName` | **Drawing** | `$PRP:"CompanyName"` |
| DRAWN BY | `DrawnBy` | **Drawing** | `$PRP:"DrawnBy"` |
| DATE DRAWN | `DrawnDate` | **Drawing** | `$PRP:"DrawnDate"` |
| CHECKED BY | `CheckedBy` | **Drawing** | `$PRP:"CheckedBy"` |
| DATE CHECKED | `CheckedDate` | **Drawing** | `$PRP:"CheckedDate"` |
| ENG. APPROVAL | `EngineeringApproval` | **Drawing** | `$PRP:"EngineeringApproval"` |
| ENG. APP. DATE | `EngAppDate` | **Drawing** | `$PRP:"EngAppDate"` |
| MFG. APPROVAL | `ManufacturingApproval` | **Drawing** | `$PRP:"ManufacturingApproval"` |
| MFG. APP. DATE | `MfgAppDate` | **Drawing** | `$PRP:"MfgAppDate"` |
| CONTRACT | `ContractNumber` | **Drawing** | `$PRP:"ContractNumber"` |

### Core calls

| Call | Signature / values | Notes |
|---|---|---|
| `ISheet.ReloadTemplate(KeepNoteChanges)` | returns rc: `0` Success, `1` UnknownError, `2` FileNotFound, `3` CustomSheet, `4` ViewOnly | `false` = discard note edits, reload from `.slddrt` (cleanup); `true` = keep edits, refresh the rest |
| `CustomPropertyManager.Add3(name, type, value, option)` | `type`: `30` Text, `5` Double, `3` Integer, `11` YesNo, `64` Date. `option`: `0` skip-if-exists, `1` DeleteAndAdd, `2` replace-if-type-matches | `cpm[""]` is the **file-level** manager — what `$PRP`/`$PRPSHEET` read by default |
| `INote.GetExtent()` | 6 doubles, sheet-space meters: `[xMin, yMin, zMin, xMax, yMax, zMax]` | current text's bounding box, not the slot background |
| `IAnnotation.GetTextFormat(0)` / `SetTextFormat(0, UseDoc, tf)` | `UseDoc=false` keeps the local format | `INote.SetTextFormat` is obsolete — go through the annotation |
| `IDrawingDoc.EditTemplate()` / `EditSheet()` | — | always pair them; `EditSheet()` is mandatory before any other drawing edit, even on error paths |
| `ISheet.TitleBlock` | `null` on legacy formats (expected) | non-null only for "Define Title Block Fields" formats |

---

## How it works: route each field to its mechanism

A title block has the three mechanisms above, and the agent must route each field to the right one or most fields stay blank. The dominant path on modern formats is **write a custom property and let the linked note resolve** — not note editing. The Read pass tells you which mechanism each field uses; the Fill pass applies them.

A `$PRP:` or `$PRPSHEET:` note that *looks* blank on screen is not empty — it's an unresolved property reference. Fill it by writing the property; that keeps the link live. (Overwriting it with `SetText` is the one move to avoid — see [Gotchas](#gotchas--fixes).)

---

## How to: read & classify every note (Read pass)

Append to the end of Call 1, after views/dimensions/BOM are placed. Covers the sheet-format notes path **and** the Title Block Fields path so Fill knows which mechanism each sheet uses.

```csharp
// --- Title block: read pass (end of Call 1) ---
// Log every note with: text, box extent, and CLASSIFICATION (prp / prpsheet / freetext)
// plus the property name extracted from any $PRP:"X" / $PRPSHEET:"X" reference.

var schema = new List<string>();

// (a) Sheet-format notes — the main mechanism on most drawings
swDraw.EditTemplate();
View sheetView = (View)swDraw.GetFirstView();
object[] notesArr = (object[])sheetView.GetNotes();
if (notesArr != null)
{
    foreach (object obj in notesArr)
    {
        Note note = (Note)obj;
        string text = note.GetText() ?? "";
        double[] ext = (double[])note.GetExtent();
        double w = ext[3] - ext[0], h = ext[4] - ext[1];

        string kind = "freetext";
        string propName = null;
        // Extract $PRP:"Name" or $PRPSHEET:"Name" — accept single or double quotes
        var m = System.Text.RegularExpressions.Regex.Match(
            text, "\\$(PRPSHEET|PRP|PRPMODEL|PRPVIEW):\"?([^\"\\s}]+)\"?");
        if (m.Success) { kind = m.Groups[1].Value.ToLower(); propName = m.Groups[2].Value; }

        schema.Add($"  [{kind,-8}] prop={propName ?? "-"}  text=\"{text}\"  box={w*1000:F1}×{h*1000:F1}mm");
    }
}
swDraw.EditSheet(); // CRITICAL: exit template mode before anything else

// (b) Title Block Fields feature (SW 2015+) — usually null on legacy formats
Sheet swSheet = (Sheet)swDraw.GetCurrentSheet();
TitleBlock tbf = (TitleBlock)swSheet.TitleBlock;
if (tbf != null)
{
    object[] tbfNotes = (object[])tbf.GetNotes();
    if (tbfNotes != null)
    {
        schema.Add("  --- Title Block Fields feature (ISheet.TitleBlock) ---");
        foreach (object obj in tbfNotes)
        {
            Note note = (Note)obj;
            schema.Add($"  [tbf     ] text=\"{note.GetText()}\"");
        }
    }
}

System.Diagnostics.Debug.WriteLine("TITLE BLOCK SCHEMA:\n" + string.Join("\n", schema));
```

Interpret the schema:

- `[prpsheet] prop=Description` → Fill writes `Description` on the **model**.
- `[prp     ] prop=DrawnBy`     → Fill writes `DrawnBy` on the **drawing**.
- `[freetext]` with text `"TITLE"` or similar → Fill enters template mode and overwrites the note.
- `[tbf     ]` → Fill iterates `sheet.TitleBlock.GetNotes()` (no `EditTemplate`).

Mostly `freetext` placeholders with no `$PRP`/`$PRPSHEET` → legacy template, fill entirely via note overwrites. Mostly `prpsheet`/`prp` → custom properties are the primary path.

**Labels-only schema (common on ISO stock templates).** When the `freetext` entries are all **labels** like `"TITLE"`, `"MATERIAL"`, `"WEIGHT"`, `"DWG. NO."` with **no adjacent empty value notes**, the template has invisible value slots rendered from custom properties via `$PRPSHEET`. Handle it as property-linked:

- **Route values through custom properties (Step 1) and skip the free-text fill.** There are no value notes to overwrite — matching `"TITLE"` against an update map would overwrite the **label** itself. The schema shows `text="TITLE"` because that's the label text, not because a value note is waiting.
- **Write** `Description`, `Material`, `Weight`, `PartNo`, `Revision`, `Finish` on the part model; ISO templates link these via `$PRPSHEET` even when the Read pass doesn't surface the link (it lives inside the sheet-format definition). Save the model, rebuild, and the values render.
- **Detection heuristic:** if every `freetext` entry is a short all-caps label (`^[A-Z][A-Z. ]*:?$`) and none look like placeholder values (lowercase, long, or blank), treat the template as property-linked and route 100% through Step 1.

---

## How to: fill the title block (Fill pass — Call 2)

Up to three sub-steps, driven by what the schema found, then rebuild + verify.

### Step 1 — Write custom properties (covers `$PRP` and `$PRPSHEET` notes)

The step most agents skip. Without it every `$PRPSHEET:"Description"` stays blank no matter how many notes you overwrite.

```csharp
ModelDoc2 swDrawModel = (ModelDoc2)swApp.ActiveDoc;
DrawingDoc swDraw = (DrawingDoc)swDrawModel;

// Resolve the referenced model (the part/assembly shown on the sheet).
// $PRPSHEET pulls from this model, not the drawing.
ModelDoc2 swPartModel = null;
View firstView = (View)swDraw.GetFirstView();         // sheet background
View realView   = (View)firstView.GetNextView();      // first actual drawing view
if (realView != null) swPartModel = (ModelDoc2)realView.ReferencedDocument;

const int TEXT            = 30; // swCustomInfoType_e.swCustomInfoText
const int DELETE_AND_ADD  = 1;  // swCustomPropertyAddOption_e.swCustomPropertyDeleteAndAdd

// --- Model-level properties ($PRPSHEET sources from here) ---
if (swPartModel != null)
{
    CustomPropertyManager cpmModel = swPartModel.Extension.CustomPropertyManager[""]; // "" = file-level (not a specific config)
    cpmModel.Add3("Description", TEXT, "BRACKET, MOUNTING",        DELETE_AND_ADD);
    cpmModel.Add3("PartNo",      TEXT, "P-00123",                   DELETE_AND_ADD);
    cpmModel.Add3("Material",    TEXT, "6061-T6",                   DELETE_AND_ADD);
    cpmModel.Add3("Finish",      TEXT, "Anodize, Clear Type II",    DELETE_AND_ADD);
    cpmModel.Add3("Weight",      TEXT, "0.45 kg",                   DELETE_AND_ADD);
    cpmModel.Add3("Revision",    TEXT, "A",                         DELETE_AND_ADD);
    swPartModel.Save3(1, 0, 0); // persist so future opens keep the values
}

// --- Drawing-level properties ($PRP sources from here) ---
CustomPropertyManager cpmDrw = swDrawModel.Extension.CustomPropertyManager[""];
cpmDrw.Add3("CompanyName", TEXT, "Cosmon",     DELETE_AND_ADD);
cpmDrw.Add3("DrawnBy",     TEXT, "PS",          DELETE_AND_ADD);
cpmDrw.Add3("DrawnDate",   TEXT, "2026-04-17",  DELETE_AND_ADD);
cpmDrw.Add3("CheckedBy",   TEXT, "",            DELETE_AND_ADD);
cpmDrw.Add3("Revision",    TEXT, "A",           DELETE_AND_ADD); // drawing-level rev if your format uses $PRP
```

- `Add3(name, type, value, option)` with `option=1` (`swCustomPropertyDeleteAndAdd`) both creates and updates — what you almost always want. `option=0` silently skips existing properties; `option=2` replaces value only if the type matches.
- **Type `30` = Text.** Title-block values are almost always text even when they look numeric (weight with units, revision letter).
- `CustomPropertyManager[""]` (empty string) is the **file-level** manager — what `$PRP`/`$PRPSHEET` read by default. `CustomPropertyManager[configName]` is config-specific and read only when the view's config matches.
- After writing model properties, **`Save3` the model** or the values won't persist beyond this session. The drawing reads them live from the model.

### Step 2 — Overwrite free-text notes (covers `[freetext]` entries)

For notes the Read pass classified as free-text — `"TITLE"`, `"DWG NO."`, blank placeholders, anything without a `$PRP`/`$PRPSHEET` reference — use the shrink-to-fit loop:

```csharp
// Built from the Read pass — one entry per FREE-TEXT placeholder
var fieldUpdates = new Dictionary<string, string>
{
    ["TITLE"]     = "BRACKET, MOUNTING",
    ["DWG NO"]    = "P-00123",
    ["UNITS"]     = "MM",
    ["TOLERANCE"] = "±0.1",
    // Add only placeholders that appeared as [freetext] in the schema
};

swDraw.EditTemplate();
sheetView = (View)swDraw.GetFirstView();
notesArr = (object[])sheetView.GetNotes();
if (notesArr != null)
{
    foreach (object obj in notesArr)
    {
        Note note = (Note)obj;
        string text = note.GetText();
        if (text.Contains("$PRP:") || text.Contains("$PRPSHEET:")
            || text.Contains("$PRPMODEL:") || text.Contains("$PRPVIEW:"))
            continue; // property-linked — already handled in Step 1

        string newText = null;
        foreach (var kv in fieldUpdates)
            if (text.Contains(kv.Key)) { newText = kv.Value; break; }
        if (newText == null) continue;

        // --- Inline shrink-to-fit ---
        double[] ext = (double[])note.GetExtent();
        double boxWidth = ext[3] - ext[0];
        Annotation ann = (Annotation)note.GetAnnotation();
        TextFormat tf = (TextFormat)ann.GetTextFormat(0);
        int currentPts = tf.CharHeightInPts > 0 ? tf.CharHeightInPts : 10;

        double widthFor(int pts, int chars) => chars * 0.5 * pts * 0.000353;
        int fitPts = currentPts;
        while (fitPts > 7 && widthFor(fitPts, newText.Length) > boxWidth * 0.9)
            fitPts--;

        if (fitPts != currentPts)
        {
            tf.CharHeightInPts = fitPts;
            ann.SetTextFormat(0, false, tf);
        }
        note.SetText(newText);
    }
}
swDraw.EditSheet(); // CRITICAL: always exit template mode
```

Match free-text by the placeholder label, and skip any note carrying a `$PRP`/`$PRPSHEET`/`$PRPMODEL`/`$PRPVIEW` reference (Step 1 owns those). For deeper overflow control (wrap vs shrink, long descriptions) see [How to: prevent text overflow](#how-to-prevent-title-block-text-overflow).

### Step 3 — Title Block Fields feature (only if the schema showed `[tbf]` entries)

```csharp
Sheet swSheet = (Sheet)swDraw.GetCurrentSheet();
TitleBlock tbf = (TitleBlock)swSheet.TitleBlock;
if (tbf != null)
{
    object[] tbfNotes = (object[])tbf.GetNotes();
    if (tbfNotes != null)
    {
        foreach (object obj in tbfNotes)
        {
            Note note = (Note)obj;
            string text = note.GetText();
            // Match by label and overwrite — no EditTemplate/EditSheet needed.
            // Title Block Fields are always editable.
            if (text.Contains("TITLE"))    note.SetText("BRACKET, MOUNTING");
            else if (text.Contains("DWG")) note.SetText("P-00123");
        }
    }
}
```

`ISheet.TitleBlock` is usually `null` on legacy sheet formats — that's expected, just skip this step.

### Step 4 — Rebuild

```csharp
swDrawModel.ForceRebuild3(true); // re-resolves every $PRP / $PRPSHEET linked note
```

### Step 5 — Verify (mandatory on property-linked templates)

On a labels-only / property-linked template, rebuild is when the fields become visible. **Always run a verification dump afterwards** — a misspelled property name, a property set on the wrong doc (drawing vs model), or a `ReferencedDocument` that pointed somewhere unexpected renders the field blank, and the only way to catch it is to re-read the notes and check their resolved text.

```csharp
// --- Verification pass: confirm linked notes resolved ---
swDraw.EditTemplate();
View sv = (View)swDraw.GetFirstView();
object[] notes = (object[])sv.GetNotes();
var unresolved = new List<string>();
if (notes != null)
{
    foreach (object obj in notes)
    {
        Note n = (Note)obj;
        string raw = n.GetText() ?? "";
        // DisplayText returns the resolved, rendered text (what the user sees on the sheet)
        // instead of the raw $PRP:"X" reference. Available on IAnnotation.
        Annotation ann = (Annotation)n.GetAnnotation();
        string shown = ann.GetTextAtIndex(0); // or note.GetText() on non-linked notes

        if (raw.Contains("$PRP") || raw.Contains("$PRPSHEET"))
        {
            // Still showing the raw $PRP reference → the link didn't resolve
            if (shown == null || shown.Contains("$PRP"))
                unresolved.Add($"  UNRESOLVED: raw=\"{raw}\"  shown=\"{shown}\"");
            else
                unresolved.Add($"  ok:         prop-linked → \"{shown}\"");
        }
    }
}
swDraw.EditSheet();
System.Diagnostics.Debug.WriteLine("VERIFY:\n" + string.Join("\n", unresolved));
```

If any entry is `UNRESOLVED`, the most likely causes in order:

1. **Property written on the wrong document.** `$PRPSHEET:"Description"` reads from the model; write `Description` on the model, not the drawing. Re-check Step 1.
2. **Property name misspelled or wrong case.** `PartNo` ≠ `Part No` ≠ `partno`. Confirm the exact name on the model (`cpmModel.GetNames()`) matches the `$PRPSHEET:"..."` reference.
3. **Referenced-document pointer missed the model.** If `firstView.GetNextView()` returned a sheet-format artifact instead of a real view, `ReferencedDocument` is null/wrong — skip the sheet background explicitly and verify `swPartModel.GetPathName()` matches the intended part.
4. **Wrong `CustomPropertyManager` scope.** Sheet-format `$PRPSHEET` without a config qualifier reads file-level (`cpm[""]`) — write there, not `cpm["Default"]`.
5. **Model wasn't saved.** `Save3` on the model persists the properties in the `.sldprt` header; without it some hosts won't rebuild the drawing against the new values.

This 100 ms read is the cheapest insurance against "everything looks correct in the code but the title block is blank on the rendered sheet."

---

## How to: clean up stale notes after a format swap

If the sheet format was ever swapped — manually or via a second `SetupSheet6` — the title block can keep **leftover notes from the old format** sitting on top of (or beside) the new ones. Symptoms: duplicated title fields, ghost text, placeholders from the previous format that never appear in the new schema. The Read pass surfaces these (unexpected notes) before Fill touches them.

Fix with `ISheet::ReloadTemplate(KeepNoteChanges)`:

```csharp
Sheet swSheet = (Sheet)swDraw.GetCurrentSheet();
int rc = swSheet.ReloadTemplate(false); // false = DISCARD all note modifications, reload cleanly from the .slddrt file
// rc: 0 = Success (swReloadTemplate_Success), 1 = UnknownError, 2 = FileNotFound, 3 = CustomSheet, 4 = ViewOnly
```

- **`KeepNoteChanges = false`** for cleanup — discards user edits and restores the notes exactly as the `.slddrt` defines them. Run it **before** the Read pass so the schema reflects only the current format's fields.
- **`KeepNoteChanges = true`** preserves your edits but still reloads everything else (borders, logos, geometry) — use only when you've *intentionally* modified notes and just want to refresh the rest.
- Run `ReloadTemplate` only when you actually suspect a stale format (opening an existing drawing, or after a `SetupSheet6` swap). On a freshly created drawing it's wasted work.

Sequence so the reload doesn't wipe values you've written: do all `SetupSheet6` calls first, then `ReloadTemplate(false)` once, then Read + Fill. `ReloadTemplate` discards already-filled free-text values, so filling before the reload loses them.

```
SetupSheet6(...)            // if switching format
ReloadTemplate(false)       // discard stale notes
<Read pass>                 // dump fresh schema, classified
<Fill pass, Call 2>         // write properties + overwrite free-text notes
```

`ReloadTemplate` operates on the current sheet — for multi-sheet drawings with different formats, iterate sheet names and call it per sheet.

**Initial load of a custom `.slddrt` is a different case.** When `SetupSheet6` is the first touch of the format (fresh drawing, no prior fills), `ReloadTemplate(false)` has been observed to leave the sheet empty — the geometry never loads. For the initial-load path use `ReloadTemplate(true)` and verify by counting notes (no real sheet format has 0). The `false` guidance here is for the cleanup-after-swap case, where you *want* to discard already-filled values. See `quick_multi_view_drawing.md` → "Step 4: Create Drawing + Sheet Setup" for the initial-load recipe.

---

## How to: fix the "X in a box" link-error marker

**Symptom:** after deleting a title block note (or after a property a note depended on disappears / gets renamed / never existed), a small red-ish cross or crossed-box appears where the note was. It usually doesn't render in PDF exports but is visible on-screen and can leak into prints depending on display settings.

**What it is:** SolidWorks' **annotation link error indicator**. Two distinct causes produce the same marker; the fix differs.

### Cause 1 — Broken property link (by far the most common)

The note contains `$PRP:"X"` or `$PRPSHEET:"X"` but property `X` doesn't exist on the target doc (drawing for `$PRP`, referenced model for `$PRPSHEET`). Typical triggers: a property-linked note overwritten with `SetText` then re-applied; a name mismatch (`PartNo` vs `Part No` vs `partno`); the referenced model changed; a property deleted after the format was authored.

**Proper fix — create the missing property** (the real problem is the missing property, not the indicator):

```csharp
// For each broken $PRPSHEET reference surfaced by the Read pass, create the property
// on the referenced model.
CustomPropertyManager cpmModel = swPartModel.Extension.CustomPropertyManager[""];
cpmModel.Add3("MissingProp", 30 /*Text*/, "",  1 /*DeleteAndAdd*/);
// Blank value is fine if you don't have one yet — the indicator clears as soon as
// the property exists, even empty. Fill the real value in the normal fill pass.

// Drawing-level ($PRP) equivalents go on the drawing doc:
CustomPropertyManager cpmDrw = swDrawModel.Extension.CustomPropertyManager[""];
cpmDrw.Add3("MissingDrwProp", 30, "", 1);

swDrawModel.ForceRebuild3(true); // indicator clears on rebuild
```

**Alternative fix — delete the orphaned note** (when the property isn't coming back):

```csharp
swDraw.EditTemplate();
View sheetView = (View)swDraw.GetFirstView();
object[] notesArr = (object[])sheetView.GetNotes();
if (notesArr != null)
{
    foreach (object obj in notesArr)
    {
        Note n = (Note)obj;
        string text = n.GetText() ?? "";
        if (text.Contains("$PRP:\"MissingProp\"") || text.Contains("$PRPSHEET:\"MissingProp\""))
        {
            Annotation ann = (Annotation)n.GetAnnotation();
            ann.Select3(false, null);
            swDrawModel.Extension.DeleteSelection2(0);
        }
    }
}
swDraw.EditSheet();
```

### Cause 2 — Dangling annotation (the referenced geometry is gone)

Less common in title blocks, common in views: a dimension or note referenced a feature/edge since deleted or no longer visible. `IAnnotation::IsDangling()` returns `true` on these.

```csharp
// Walk every view (including the sheet background where title-block notes live)
// and delete dangling annotations.
View view = (View)swDraw.GetFirstView();
while (view != null)
{
    object[] notes = (object[])view.GetNotes();
    if (notes != null)
    {
        foreach (object obj in notes)
        {
            Note n = (Note)obj;
            Annotation ann = (Annotation)n.GetAnnotation();
            if (ann.IsDangling())
            {
                swDrawModel.ClearSelection2(true);
                ann.Select3(false, null);
                swDrawModel.Extension.DeleteSelection2(0);
            }
        }
    }

    // Also sweep display dimensions
    DisplayDimension dd = (DisplayDimension)view.GetFirstDisplayDimension5();
    while (dd != null)
    {
        Annotation ann = (Annotation)dd.GetAnnotation();
        DisplayDimension next = (DisplayDimension)dd.GetNext5(); // capture BEFORE delete
        if (ann.IsDangling())
        {
            swDrawModel.ClearSelection2(true);
            ann.Select3(false, null);
            swDrawModel.Extension.DeleteSelection2(0);
        }
        dd = next;
    }

    view = (View)view.GetNextView();
}
swDrawModel.ClearSelection2(true);
swDrawModel.ForceRebuild3(true);
```

### Decision flow

1. Run the Read pass. For every note whose raw text contains `$PRP:` or `$PRPSHEET:`, check whether the referenced property exists on the target doc (`cpm.Get5(name, useCached, out val, out typ, out resolvedValue, out ...)` — non-zero on miss).
2. Missing property → **create it** (Cause 1, fix A). If you truly don't want the field → **delete the note** (fix B).
3. For every annotation in every view, check `IsDangling()` → delete if true (Cause 2).
4. **Keep the link-error display on.** It exists to flag blank fields whose property is missing. As a last resort for a clean screenshot you can hide the marker, but re-enable it before delivery — silencing it turns a visible bug into an invisible one:

```csharp
// Display-only — hides the X marker, does not fix what's broken. Re-enable before delivery.
swApp.SetUserPreferenceToggle(
    (int)swUserPreferenceToggle_e.swViewShowAnnotationLinkErrors, false);
```

---

## How to: prevent title-block text overflow

The inline loop in Step 2 covers the common case. Use these steps when you need to tune the behavior — wrap instead of shrink, or handle unusually long descriptions. (For property-linked notes, shrink-to-fit must be configured at the note level in the `.slddrt`; the API writes the raw value and SolidWorks renders it at the format's native size — if a linked note overflows, shorten the value or edit the template.)

### Step A — Measure the box from the template

Read the existing note's extent before writing — the author sized the box for the placeholder, and that extent is your room.

```csharp
// note.GetExtent() returns 6 doubles in sheet space (meters):
// [xMin, yMin, zMin, xMax, yMax, zMax]
double[] ext = (double[])note.GetExtent();
double boxWidth  = ext[3] - ext[0];   // meters
double boxHeight = ext[4] - ext[1];   // meters
```

`GetExtent()` gives the current text's bounding box, not the slot's background rectangle. Read it **before** overwriting the placeholder. If the placeholder was short (e.g. `"TITLE"`), use a conservative multiplier — the real field is typically 4–8× the placeholder width.

### Step B — Estimate whether new text fits

A character at font height `h` points is roughly `0.5 × h` points wide in the default SolidWorks font (Century Gothic / Arial). Convert to meters: `1 pt ≈ 0.000353 m`.

```csharp
// Rough width estimate in meters for `text` at `pts` points
double EstimateWidth(string text, int pts) =>
    text.Length * pts * 0.5 * 0.000353;
```

If `EstimateWidth(newText, currentPts) > boxWidth × 0.9`, it will overflow (0.9 leaves border margin).

### Step C — Shrink the font via `IAnnotation::SetTextFormat`

`INote::SetTextFormat` is **obsolete**. Cast the note's annotation and use `IAnnotation::SetTextFormat` with a fresh `ITextFormat`:

```csharp
Annotation ann = (Annotation)note.GetAnnotation();
TextFormat tf = (TextFormat)ann.GetTextFormat(0);

// Pick a size that fits. Never go below 7 pt — smaller becomes unreadable
// on printed A-size sheets.
int newPts = Math.Max(7, (int)Math.Floor(
    boxWidth * 0.9 / (newText.Length * 0.5 * 0.000353)));
newPts = Math.Min(newPts, 12); // don't scale UP past a reasonable ceiling

tf.CharHeightInPts = newPts;
ann.SetTextFormat(0, false /* UseDoc */, tf); // false = local format, not doc default
note.SetText(newText);
```

`UseDoc = false` is required, or the note reverts to the document default and the size change is discarded. Set text **after** the format so rich-text embedding doesn't clobber it.

### Step D — Prefer wrapping or abbreviation over tiny fonts

Shrinking below ~7 pt is a code smell. Instead:

- **Multi-word descriptions** — insert `\n` to wrap onto 2 lines, doubling effective width at the cost of height. Only if `boxHeight` accommodates `2 × (pts × 0.000353 × 1.2)` (1.2 = default line spacing).
- **Long part numbers** — truncate to the schema's visible length; callers needing the full ID read the custom property, not the title block text.
- **Material specs** — use the short form (`"6061-T6"`, not `"Aluminum 6061-T6 per AMS-QQ-A-250/11"`). The long form belongs in a separate "NOTES" note.

### Step E — Verify after the fact

After `SetText` + `SetTextFormat`, re-read `GetExtent()` and confirm the new box is inside the original. If not, drop one more point and retry. End with `swModel.GraphicsRedraw2()` or `ForceRebuild3(true)` so the extent reflects the new format.

```csharp
double[] after = (double[])note.GetExtent();
if ((after[3] - after[0]) > boxWidth)
{
    tf.CharHeightInPts = Math.Max(7, newPts - 1);
    ann.SetTextFormat(0, false, tf);
}
```

### Quick reference — fits-per-point at common box widths

| Box width | 12 pt | 10 pt | 8 pt | 7 pt |
|---|---|---|---|---|
| 20 mm (≈0.020 m) | 9 ch | 11 ch | 14 ch | 16 ch |
| 30 mm | 14 ch | 17 ch | 21 ch | 24 ch |
| 40 mm | 19 ch | 22 ch | 28 ch | 32 ch |
| 60 mm | 28 ch | 34 ch | 42 ch | 48 ch |

Counts are approximate — narrow letters (`i`, `l`, `1`) fit more, wide letters (`M`, `W`, `#`) fit fewer. Treat as an upper bound.

---

## Completeness gate — run before declaring the title block done

Walk the schema row-by-row and confirm each is handled:

| Schema entry | Required action | Check |
|---|---|---|
| `[prpsheet] prop=X` | `cpmModel.Add3("X", 30, "...", 1)` on the **model** | Did you call it? |
| `[prp     ] prop=X` | `cpmDrw.Add3("X", 30, "...", 1)` on the **drawing** | Did you call it? |
| `[freetext]` with a **value-slot** placeholder (blank or lowercase template text) | `EditTemplate()` → `SetText()` → `EditSheet()` | Did the loop match it? |
| `[freetext]` that is only a **label** (`"TITLE"`, `"MATERIAL"`, …) on a labels-only template | Route the value to a custom property in Step 1; leave the label alone | Did you skip it correctly? |
| `[tbf     ]` | `sheet.TitleBlock.GetNotes()` iterated and updated | Did you reach Step 3? |
| Verification pass (Step 5) | Re-read notes; confirm every `$PRP`/`$PRPSHEET` note resolved to non-`$PRP` text | Did you see the rendered value? |

Any un-actioned row means the title block is incomplete. Two common failure modes: covering `[freetext]` labels while skipping `[prpsheet]` rows (labels show, values blank), and running Fill before `ReloadTemplate(false)` after a second `SetupSheet6` (the reload discards your values).

---

## Gotchas & fixes

- **Fill `$PRP`/`$PRPSHEET` notes by writing the property, not `SetText`.** Overwriting a linked note severs the link permanently — the field never auto-updates again. Write the property and let the note resolve on rebuild.
- **Write `$PRPSHEET` properties on the model in the first view.** `$PRPSHEET` resolves against the model shown in the first view on the sheet; a property on the drawing doc (or on a component instead of the top-level part) leaves the note blank. Read `ReferencedDocument` of the first non-background view and write there.
- **Match property names exactly — case-sensitive.** `PartNo` ≠ `partno` ≠ `Part No`. Use what the Read pass logged as `prop=`.
- **Use the file-level property manager.** `CustomPropertyManager[""]` is file-level and is what `$PRPSHEET` reads by default; per-config (`["Default"]`) is read only when the view's active config matches.
- **Save the model after writing its properties.** `swPartModel.Save3(1, 0, 0)` — without it the values vanish at session end.
- **Always pair `EditTemplate()` with `EditSheet()`**, including on error paths and in the Read pass. Leaving the drawing in template mode breaks every subsequent drawing edit.
- **Keep the Read pass short** — enter template, dump notes, exit. View/dimension APIs misbehave while template mode is active, so don't interleave them.
- **On labels-only templates, treat the label as a label.** A note reading `"TITLE"` on a property-linked ISO format is the label, not a value field — route the value through a custom property (Step 1) instead of overwriting.
- **Use `IAnnotation::SetTextFormat`, not `INote::SetTextFormat`** (obsolete), and pass `UseDoc = false` or the note reverts to doc defaults. Set text **after** format — rich-text strings can override formatting applied first.
- **After a sheet-format swap, call `ReloadTemplate(false)` right after the second `SetupSheet6`**, before the Read pass — `SetupSheet6` alone doesn't purge old-format notes. Sequence `SetupSheet6` → `ReloadTemplate(false)` → Read → Fill so the reload doesn't wipe values.
- **`ISheet.TitleBlock` is usually `null`** on legacy formats — expected, just skip Step 3. Only the "Define Title Block Fields" workflow creates an `ITitleBlock`.
- **Rebuild after setting properties.** `ForceRebuild3(true)` resolves the linked notes; without it the fields stay blank.
- **For the "X in a box" marker**, create the missing custom property (or delete the orphan note), then `ForceRebuild3`; use `IAnnotation::IsDangling()` for the dangling-reference case. Don't ship with `swViewShowAnnotationLinkErrors` toggled off as the "fix" — that only hides it. See [How to: fix the "X in a box" marker](#how-to-fix-the-x-in-a-box-link-error-marker).
- **The `SetupSheet6` FirstAngle flag governs view placement only — it does not draw the projection symbol.** Draw the symbol as geometry or insert it as a block separately; a drawing with first/third-angle placement but a missing or mismatched symbol is ambiguous to machinists.
