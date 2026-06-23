---
description: "Bulk-dimension a drawing with InsertModelAnnotations4 once per view (detail → section → rest), cleaning and styling inside the same iteration; falls back to InsertModelDimensions, deletes reference/out-of-boundary dims, recolors, and patches shortfalls with Add…Dimension2. Includes a part-agnostic inspect-driven pass: list every dim, delete chosen dims by FullName, and move dims across views. Also covers QUALIFIER/QUANTITY callout text via the PREFIX/ABOVE/SUFFIX SetText triplet, chamfer & hole-callout overlays, and straightening broken leaders on Ø/R dims."
---

# Dimensioning — Simple Recipe

> Project model dims onto every drawing view in one bulk pass — insert, clean (drop reference + out-of-bounds dims), recolor, and patch shortfalls — iterating detail → section → rest. Use this for the per-dimension bulk recipe (linear, Ø, angular). For picking an explicit dimensioning system (ordinate / baseline / chain / polar / tabular / GD&T), see `dimensioning-systems.md`.

## Recipe (happy path)

1. List sheet views with `Sheet.GetViews()`; skip the title-block ISO (`Drawing View7`). Order **detail → section → rest** → [How to: order and insert per view](#how-to-order-and-insert-dims-per-view).
2. **Insert on every view first.** For each view in that order, select it and run `InsertModelAnnotations4(0, 32768|524288, false, true, false, false, false, false)`; if it returns 0, fall back to `swDraw.InsertModelDimensions(0)` and re-count. **Insert only — do not clean, recolor, delete, or patch anything yet** → [How to: order and insert per view](#how-to-order-and-insert-dims-per-view).
3. **Right after IMA4, before anything else: list every dimension in a table for the user.** Walk all views and present each dim as a Markdown table with columns **View | Name (`FullName`) | Type | Prefix | Suffix | Value | Text**, with **Value** and **Text** in drawing units (mm / degrees), not raw SI. This is the **first thing you do after inserting — a required checkpoint on every dimensioning run, not optional** — so the user sees every dim that landed *before* any of it is cleaned or deleted. Use the [list-every-dimension snippet](#2-list-every-dimension-for-analysis).
4. **Then clean & recolor, per view** — delete construction dims (`dim.IsReference() == true`), delete detail-view dims whose `ann.GetPosition()` falls outside `view.GetOutline()` ± 30 mm, recolor survivors `ann.Color = 6316128` (RGB 96,96,96), and count/log `construction / filtered / remaining` → [How to: clean and recolor](#how-to-clean-and-recolor-survivors).
5. `swModel.EditRebuild3()` once.
6. Patch any view short vs. its Phase 1 expected count with `AddDimension2 / AddRadialDimension2 / AddDiameterDimension2 / AddHorizontalDimension2 / AddVerticalDimension2 / AddHoleCallout2` → [How to: recover missing dims](#how-to-recover-missing-dims-after-the-loop).
7. **Always finish by arranging.** Once every view is inserted, cleaned, recolored, and patched, run `AlignDimensions(AutoArrange)` once per view as the final step — never leave raw stacked labels. `AlignDimensions(AutoArrange)` is shorthand — see the [How to: arrange dimensions (AutoArrange)](#how-to-arrange-dimensions-autoarrange) section below for the real `IModelDocExtension.AlignDimensions(AlignType, SpaceValue)` signature, args, and full recipe before calling it.

## Inspect-driven pass: list → prune → move

The **listing (step 2) is always required** — it's the reference table you show the user on every run. The **prune (step 3) and move (step 4)** are situational: use them when you want to curate the dims by hand rather than relying only on the bulk auto-clean above — typically paired with a screenshot. The whole pass is fully part-agnostic: nothing below hard-codes a part, sketch, view, or dim name. You fill the `toDelete` / `moves` lists from what the listing returns, so the same code works on any drawing.

1. **Insert** dims per view with IMA4 (see [order and insert](#how-to-order-and-insert-dims-per-view)).
2. **List all dimensions in a table for the user (always)** — after the IMA4 insert, present every dim as a Markdown table with columns **View | Name | Type | Prefix | Suffix | Value | Text** (add a **Required/Delete** column too when you're using this listing to drive a manual prune, marking each row **Required** to keep or **Delete** for reference / redundant). Show **Value** and **Text** in drawing units (mm / degrees), not raw SI. This table is also what drives the prune in step 3.
3. **Delete the unnecessary ones** — after analysing the listing, put their `FullName`s in `toDelete` and delete in one pass.
4. **Move dims across views if needed** — list the view outlines to choose target coordinates, then drag each misplaced dim into the right view.

Each snippet returns a `result` dictionary so you can inspect the outcome before the next step.

### 2. List every dimension (for analysis)

Walks every view and every display dim, returning one `View | FullName | Type | Prefix | Suffix | Value | Text` row per dim. Read `Type2` and `GetText` (prefix / suffix / whole-callout) from the **`DisplayDimension`**, and `FullName` / `Value` from the **`Dimension`** (`dd.GetDimension2(0)`). `dd.Type2` gives the `swDimensionType_e` enum, mapped to a readable label by a plain lookup. Guard the `Dimension`-layer reads — they throw `COMException` on cosmetic-thread dims, so a throw yields an empty field instead of aborting the pass.

**Keep this part-agnostic — never branch on a specific part's callout text.** The displayed `Text` comes from `GetText(swDimensionTextAll)`: non-empty is the user override (e.g. `"M40x1.5"`, `"1 X 30°"`), empty means native auto text, in which case compose `prefix + value + suffix`. Don't sniff the prefix for characters like `X` / `H` to guess intent — that overfits to one drawing.

```csharp
var result = new Dictionary<string, object>();
DrawingDoc swDraw = (DrawingDoc)swApp.ActiveDoc;

// swDimensionType_e → readable label. Pure lookup — no part-specific assumptions.
Func<int,string> typeName = t => {
    switch(t){
        case 2: return "Linear"; case 3: return "Angular"; case 4: return "Arc Length";
        case 5: return "Radial"; case 6: return "Diameter"; case 10: return "Chamfer";
        case 1: case 7: case 8: return "Ordinate";
        case 11: return "Linear (H)"; case 12: return "Linear (V)";
        default: return "Type" + t;
    }
};

var rows = new List<string>();
foreach (object vobj in (object[])swDraw.GetViews())
    foreach (object vo in (object[])vobj){
        View v = (View)vo;
        object d = v.GetFirstDisplayDimension5();
        while (d != null){
            DisplayDimension dd = (DisplayDimension)d;
            Dimension dim = dd.GetDimension2(0);

            // Model layer — guard: FullName / Value throw on cosmetic-thread dims.
            string name = "";   try { name   = dim != null ? dim.FullName : ""; }            catch { }
            string valTxt = ""; try { valTxt = dim != null ? dim.Value.ToString("0.###") : ""; } catch { }

            // DisplayDimension text — read prefix/suffix for every dim so the listing shows them.
            string pre = ""; try { pre = dd.GetText((int)swDimensionTextParts_e.swDimensionTextPrefix) ?? ""; } catch { }
            string suf = ""; try { suf = dd.GetText((int)swDimensionTextParts_e.swDimensionTextSuffix) ?? ""; } catch { }
            // Displayed callout, part-agnostic: GetText(All) is the override ("" = native auto value).
            string over = ""; try { over = dd.GetText((int)swDimensionTextParts_e.swDimensionTextAll) ?? ""; } catch { }
            string disp = over != "" ? over : (pre + valTxt + suf).Trim();
            if (disp == "") disp = valTxt;

            rows.Add(v.Name + " | " + name + " | " + typeName(dd.Type2) + " | " + pre + " | " + suf + " | " + valTxt + " | " + disp);
            d = dd.GetNext5();
        }
    }

result["dimensions"] = rows;
result["count"] = rows.Count;
return result;
```

`result["dimensions"]` is one `View | FullName | Type | Prefix | Suffix | Value | Text` string per dim (`result["count"]` is the total). `Value` is `dim.Value` and `Text` is the displayed callout, both already in the drawing's units (mm / degrees), not raw SI. Use `FullName` as the stable key for the prune/move steps below.

**Then render it in your reply as a Markdown table — this is the required output, not an optional flourish.** The snippet only *returns* rows; it does not show the user anything. You must take `result["dimensions"]` and post a Markdown table in your message before any cleanup/delete/arrange step. Each pipe-delimited row maps one-to-one to a table row:

```markdown
| View | Name | Type | Prefix | Suffix | Value | Text |
|---|---|---|---|---|---|---|
| Drawing View1 | D1@Sketch1@Part | Diameter |  | THRU | 6 | Ø6 THRU |
| Drawing View1 | D2@Sketch1@Part | Linear (H) |  |  | 40 | 40 |
| … | … | … | … | … | … | … |
```

Running the snippet and moving straight to cleaning — without posting the table — is the failure to avoid: the whole point of the listing is to be *shown* to the user, every run, so they see what landed before anything is changed.

### 3. Delete the unnecessary dims by FullName

After reading the step-2 listing, collect the `FullName`s to drop into `toDelete`, then walk all views and delete the matches. `missed` catches any whose annotation wouldn't select (usually already gone, or renamed by a rebuild) — re-list and retry those. This is the blacklist counterpart to [enforce an allowed-dim whitelist](#how-to-enforce-an-allowed-dim-whitelist-heavy-views); use the whitelist when it's easier to say what to keep.

```csharp
var result = new Dictionary<string, object>();
var swModel = (ModelDoc2)swApp.ActiveDoc;
var swDraw = (DrawingDoc)swModel;

// Fill from the step-2 listing — the FullName of each dim you decided to drop.
var toDelete = new HashSet<string> {
    // "D1@Sketch1@MyPart.Part",
    // "D2@Sketch1@MyPart.Part",
};

var sheet = (Sheet)swDraw.GetCurrentSheet();
object[] allViews = (object[])sheet.GetViews();

swModel.ClearSelection2(true);
var deleted = new List<string>();
var missed = new List<string>();

foreach (object o in allViews)
{
    var v = (View)o;
    var dd = (DisplayDimension)v.GetFirstDisplayDimension5();
    while (dd != null)
    {
        var ddNext = (DisplayDimension)dd.GetNext5(); // grab next before deleting
        Dimension dim = (Dimension)dd.GetDimension2(0);
        string fn = ""; try { fn = dim?.FullName ?? ""; } catch { }
        if (toDelete.Contains(fn))
        {
            Annotation ann = (Annotation)dd.GetAnnotation();
            if (ann.Select3(false, null)) { swModel.EditDelete(); deleted.Add(fn); }
            else missed.Add(fn);
            swModel.ClearSelection2(true);
        }
        dd = ddNext;
    }
}
result["deleted"] = deleted;
result["missed"] = missed;
return result;
```

### 4a. List view positions & outlines

Pick the target `x, y` for a move from these outlines (sheet metres → shown in millimetres). `GetOutline()` is `{xmin, ymin, xmax, ymax}`.

```csharp
var result = new Dictionary<string, object>();
var swModel = (ModelDoc2)swApp.ActiveDoc;
var swDraw = (DrawingDoc)swModel;

var sheet = (Sheet)swDraw.GetCurrentSheet();
object[] allViews = (object[])sheet.GetViews();

var infos = new List<Dictionary<string, object>>();
foreach (object o in allViews)
{
    var v = (View)o;
    double[] pos = (double[])v.Position;      // view origin, sheet metres
    double[] ob = (double[])v.GetOutline();   // {xmin, ymin, xmax, ymax}, sheet metres
    infos.Add(new Dictionary<string, object> {
        { "name", v.GetName2() },
        { "pos_mm", new double[] { pos[0] * 1000, pos[1] * 1000 } },
        { "outline_mm", new double[] { ob[0] * 1000, ob[1] * 1000, ob[2] * 1000, ob[3] * 1000 } },
    });
}
result["views"] = infos;
return result;
```

### 4b. Move dims across views by FullName

Key each dim's `FullName` to its target label position (sheet metres, from the 4a outlines), then walk all views, select each match, and drag it into `targetView`. The walk grabs `GetNext5()` before moving so the iteration survives the edit.

```csharp
var result = new Dictionary<string, object>();
var swModel = (ModelDoc2)swApp.ActiveDoc;
var swDraw = (DrawingDoc)swModel;

string targetView = "Drawing View2"; // where these dims should land
// FullName -> target label position { x, y } in sheet metres (pick from 4a outlines).
var moves = new Dictionary<string, double[]> {
    // { "D3@Sketch1@MyPart.Part", new double[] { 0.390, 0.160 } },
    // { "D4@Sketch1@MyPart.Part", new double[] { 0.390, 0.135 } },
};

var sheet = (Sheet)swDraw.GetCurrentSheet();
object[] allViews = (object[])sheet.GetViews();

var moved = new List<string>();
foreach (object o in allViews)
{
    var v = (View)o;
    var dd = (DisplayDimension)v.GetFirstDisplayDimension5();
    while (dd != null)
    {
        var ddNext = (DisplayDimension)dd.GetNext5();
        Dimension dim = (Dimension)dd.GetDimension2(0);
        string fn = ""; try { fn = dim?.FullName ?? ""; } catch { }
        if (moves.ContainsKey(fn))
        {
            swModel.ClearSelection2(true);
            if (((Annotation)dd.GetAnnotation()).Select3(false, null))
            {
                double[] p = moves[fn];
                swDraw.DragModelDimension(targetView, 2, p[0], p[1], 0); // mode 2 = move
                moved.Add(fn);
            }
            swModel.ClearSelection2(true);
        }
        dd = ddNext;
    }
}
swModel.EditRebuild3();
result["moved"] = moved;
return result;
```

This moves every dim into one `targetView`; **to distribute dims into several different views, run once per target.** If a move doesn't take, do one dim per pass with a rebuild between — see [How to: move a dim to another view](#how-to-move-a-dim-to-another-view).

## API quick reference

**Insert / annotation calls:**

- `IDrawingDoc.InsertModelAnnotations4(0, typeFlags, false, true, false, false, false, false)` — projects model items into the selected view; returns an `object[]` of inserted items (or `null`). `typeFlags = 32768 | 524288` = marked + not-marked for drawing.
  - Annotations-only variant: `InsertModelAnnotations4(0, 0, false, true, false, false, false, false)` — `bInsertAllDims=false`, `bInsertAnnotations=true`.
- `IDrawingDoc.InsertModelDimensions(int Option)` — on `swDraw`; one int arg, returns `void`. Fallback when IMA4 inserts nothing; projects driving dims regardless of the "marked for drawing" flag. Select the view first, then re-count by walking `GetFirstDisplayDimension5` / `GetNext5`.
  - `Option`: `0` = all dims in the selected view · `1` = selected component · `2` = selected feature · `3` = whole assembly.

**Dimension walk / query:**

- `IView.GetFirstDisplayDimension5()` → first `DisplayDimension`; `IDisplayDimension.GetNext5()` → next (walks dims only).
- `dim.IsReference()` — **method**, returns `bool`. Call with parens.
- `dd.IsReferenceDim()` — sister method on `IDisplayDimension`, same result; use when walking display dims.
- `dim.GetType()` — returns `int` per `swDimensionParamType_e`.
- `dim.GetSystemValue3(int whichConfigs, string[] configNames)` — returns `object`, underlying type `double[]` (one entry per config), **not** a scalar.
- `dim.SystemValue` — `double` property, scalar value in the active config.
- `Dimension.FullName` — stable `<DimName>@<Sketch>@<Part>` identifier across views.
- `IView.GetOutline()` → `double[]` `{xmin, ymin, xmax, ymax}` in sheet meters.
- `IAnnotation.GetPosition()` → `double[]` label position in sheet meters.
- `IAnnotation.Color` — `int` RGB; set to `6316128` (RGB 96,96,96) for the project default.

**Selection / edit:**

- `SelectByID2(Name, Type, X, Y, Z, Append, Mark, Callout, SelectOption)` — `Type` here is `"DRAWINGVIEW"`; `Append=false` clears prior selection.
- `IAnnotation.Select3(Append, Mark)` — `Append=false` replaces selection; `Mark` usually `null`.
- `IModelDoc2.EditDelete()`, `IModelDoc2.ClearSelection2(true)`, `IModelDoc2.EditRebuild3()`.

**Patch / recover calls (drawing-side dims):**

| Need | API |
|---|---|
| Linear | `AddDimension2` |
| Radius | `AddRadialDimension2` |
| Diameter | `AddDiameterDimension2` |
| Axis-aligned | `AddHorizontalDimension2`, `AddVerticalDimension2` |
| Hole callout | `AddHoleCallout2` |

These patch a per-view shortfall after the bulk insert. **To manually add dimensions from scratch by selecting visible geometry (edges / vertices / faces) — e.g. when there's no model dim to project — see `manual-dimensioning.md` → "How to: add a dim from visible entities."**

**Callout-text calls (`IDisplayDimension::SetText`):**

**`swDimensionTextParts_e`** — the slots `IDisplayDimension::SetText(part, text)` writes to. Default to the **PREFIX / ABOVE / SUFFIX** triplet (1, 3, 2):

| Part | Enum (int) | What goes here | Example |
|---|---|---|---|
| Prefix | `swDimensionTextPrefix` = 1 | text **before** the number, same line — typically `<MOD-DIAM>` for Ø (auto for diameters) | `"2X "` |
| Suffix | `swDimensionTextSuffix` = 2 | text **after** the number, same line — THRU, TYP, REF, units | `" THRU"` |
| Callout Above | `swDimensionTextCalloutAbove` = 3 | second line above — quantity prefixes like `6X`, notes like `ON BCD Ø50` | `"6X"` |
| Callout Below | `swDimensionTextCalloutBelow` = 4 | second line below — depth, bore specs | `"▼ 10"` |
| All | `swDimensionTextAll` = 0 | write each piece to its own part instead (see [callout text](#how-to-callout-text-qualifier--quantity)) | |

**Text tokens** (usable inside any part string):

| Token | Renders as |
|---|---|
| `<DIM>` | the measured numeric value |
| `<MOD-DIAM>` | Ø (diameter symbol) |
| `<MOD-PM>` | ± |
| `<MOD-DEG>` | ° |
| `▼` / `▼` | depth symbol (ASME) |
| `⌴` / `⌴` | counterbore / spotface symbol |
| `⌵` / `⌵` | countersink symbol |
| `\n` | newline (second line of callout) |

**Move a dim to another view:**

- `IDrawingDoc.DragModelDimension(targetViewName, mode, x, y, z)` — `x, y` in sheet meters, `mode 2` = move. Address dims by `FullName`. One dim per pass, rebuild between moves.

**Color note:** `6316128 = 96 | (96 << 8) | (96 << 16)` (RGB 96,96,96), the project default. Lighter than 128 washes out in PDF.

## How to: order and insert dims per view

Build the view order (detail → section → rest), skip the title-block ISO, then per view select it, call IMA4, and fall back to `InsertModelDimensions` only when IMA4 inserts nothing. **This pass inserts only** — list the dims for the user next, then clean in a second pass.

```csharp
var swModel = (ModelDoc2)swApp.ActiveDoc;
var swDraw = (DrawingDoc)swModel;
var swExt = swModel.Extension;

int typeFlags = 32768 | 524288; // marked + not marked for drawing

var sheet = (Sheet)swDraw.GetCurrentSheet();
object[] allViews = (object[])sheet.GetViews();

var detailViews = new List<View>();
var sectionViews = new List<View>();
var otherViews = new List<View>();

foreach (object vObj in allViews)
{
    var v = (View)vObj;
    string name = v.GetName2();
    if (name == "Drawing View7") continue; // ISO title-block view — skip it
    if (name.Contains("Detail")) detailViews.Add(v);
    else if (name.Contains("Section")) sectionViews.Add(v);
    else otherViews.Add(v);
}

var ordered = new List<View>();
ordered.AddRange(detailViews);
ordered.AddRange(sectionViews);
ordered.AddRange(otherViews);

foreach (var v in ordered)
{
    string vName = v.GetName2();

    // Select the view, then IMA4 (fall back to InsertModelDimensions if it returns 0)
    swModel.ClearSelection2(true);
    swExt.SelectByID2(vName, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
    var ins = swDraw.InsertModelAnnotations4(0, typeFlags, false, true, false, false, false, false);
    int inserted = ins != null ? ((object[])ins).Length : 0;
    if (inserted == 0)
    {
        // IMA4 returns 0 when nothing is "marked for drawing". InsertModelDimensions
        // projects driving dims regardless of that flag — re-select the view first
        // because EditDelete / EditRebuild calls below may clear selection.
        swModel.ClearSelection2(true);
        swExt.SelectByID2(vName, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
        swDraw.InsertModelDimensions(0); // 0 = all dims in the selected view; returns void
        var ddPost = (DisplayDimension)v.GetFirstDisplayDimension5();
        while (ddPost != null) { inserted++; ddPost = (DisplayDimension)ddPost.GetNext5(); }
    }

    // INSERT ONLY — do not clean here. List the dims for the user next (the reference
    // table), THEN clean + recolor in a second pass over these same views.
}
```

Why this order works:

- **Order matters — dimension the views with the fewest features first.** With `DuplicateDims=true` it's first-come-first-served: whichever view is dimensioned first claims each shared feature, and later views get the leftovers suppressed. Going lightest-first lets the sparse views (details, single-feature sections) claim their few features cleanly before the busy parent views sweep up everything else, so nothing important lands on the wrong view or gets crammed. The detail → section → rest order below is the usual realization of this — details and sections are normally the lightest.
- **Detail first** — tightest crop, so its strays sit far outside `GetOutline` and are easy to delete. Running parents first lets `DuplicateDims=true` suppress the detail copies.
- **Section next** — cut-edge dims only exist after the section is built.
- **Parents last** — by now most dims have homes; parents pick up the spine dims (overall L/W/H, primary feature locations).

## How to: clean and recolor survivors

This is a **second pass over the views, run after you've listed the dims for the user** (never before — the listing must show the raw inserted set). Loop the same `ordered` views from the insert step: delete reference dims, drop detail-view strays, recolor what remains, and count.

```csharp
var result = new Dictionary<string, string>();
foreach (var v in ordered) // same detail → section → rest views from the insert pass
{
    string vName = v.GetName2();

    // 2. Delete construction (reference) dims
    int constructionDeleted = 0;
    {
        var dd = (DisplayDimension)v.GetFirstDisplayDimension5();
        while (dd != null)
        {
            var next = (DisplayDimension)dd.GetNext5();
            Dimension dim = (Dimension)dd.GetDimension2(0);
            if (dim != null && dim.IsReference())
            {
                swModel.ClearSelection2(true);
                ((Annotation)dd.GetAnnotation()).Select3(false, null);
                swModel.EditDelete();
                constructionDeleted++;
            }
            dd = next;
        }
    }

    // 3. Detail-only: delete out-of-boundary dims (outside GetOutline ± 30 mm)
    int filtered = 0;
    if (vName.Contains("Detail"))
    {
        double[] outline = (double[])v.GetOutline();
        double margin = 0.030;

        var dd = (DisplayDimension)v.GetFirstDisplayDimension5();
        while (dd != null)
        {
            var next = (DisplayDimension)dd.GetNext5();
            Annotation ann = (Annotation)dd.GetAnnotation();
            double[] pos = (double[])ann.GetPosition();
            if (pos != null)
            {
                bool outside = pos[0] < outline[0] - margin || pos[0] > outline[2] + margin ||
                               pos[1] < outline[1] - margin || pos[1] > outline[3] + margin;
                if (outside)
                {
                    swModel.ClearSelection2(true);
                    ann.Select3(false, null);
                    swModel.EditDelete();
                    filtered++;
                }
            }
            dd = next;
        }
    }

    // 4. Recolor survivors — RGB 96,96,96 = 6316128
    int dimGray = 96 | (96 << 8) | (96 << 16); // 6316128
    {
        var dd = (DisplayDimension)v.GetFirstDisplayDimension5();
        while (dd != null)
        {
            ((Annotation)dd.GetAnnotation()).Color = dimGray;
            dd = (DisplayDimension)dd.GetNext5();
        }
    }

    // 5. Count remaining and log
    int remaining = 0;
    var ddc = (DisplayDimension)v.GetFirstDisplayDimension5();
    while (ddc != null) { remaining++; ddc = (DisplayDimension)ddc.GetNext5(); }

    result[vName] = $"construction={constructionDeleted}, filtered={filtered}, remaining={remaining}";
    swModel.ClearSelection2(true);
}
```

After the loop, rebuild once:

```csharp
swModel.EditRebuild3();
return result;
```

Where to walk other annotation kinds: `GetFirstDisplayDimension5` walks dims only. For notes / GTOL / surface-finish color, walk `GetFirstNote` / `GetFirstGTOL` or `view.GetAnnotations()`.

## How to: drop unnecessary thread / construction angle dims

Insert can drag in dims you don't want — most often **thread-callout angles** and **construction angle dims** (helix lead, thread pitch, draft/guide-curve angles). These come from construction geometry, not the manufactured feature, so they clutter the view without adding manufacturing intent. They aren't always flagged `IsReference()`, so the reference-dim pass in [clean and recolor](#how-to-clean-and-recolor-survivors) misses them — if you spot them after the insert (on screenshot or by walking the dims), delete them. Same mechanism as the reference-dim cleanup: select the annotation, `EditDelete`.

```csharp
var dd = (DisplayDimension)v.GetFirstDisplayDimension5();
while (dd != null)
{
    var next = (DisplayDimension)dd.GetNext5();
    Dimension dim = (Dimension)dd.GetDimension2(0);

    // Dimension.FullName THROWS COMException on cosmetic-thread / annotation-style
    // dims — exactly the kind near these strays. Guard every access; a throw means
    // "no usable name", so treat it as empty and let the match fall through.
    string fn;
    try { fn = dim != null ? (dim.FullName ?? "") : ""; }
    catch { fn = ""; }

    // Match construction angle strays by name (thread/helix/draft sketches carry these).
    bool isStrayAngle =
        fn.Contains("Thread") || fn.Contains("Helix") ||
        fn.Contains("Draft")  || fn.Contains("Cosmetic");
    if (isStrayAngle)
    {
        swModel.ClearSelection2(true);
        ((Annotation)dd.GetAnnotation()).Select3(false, null);
        swModel.EditDelete();
    }
    dd = next;
}
```

Delete only what's genuinely redundant — keep any angle that actually dimensions the part (a real chamfer or taper angle). When in doubt, leave it. For a stricter pass on heavy thread/pattern views, drive deletion from the Phase 1 allowed-dim list instead — see [enforce an allowed-dim whitelist](#how-to-enforce-an-allowed-dim-whitelist-heavy-views).

**`Dimension.FullName` can throw `COMException` on cosmetic-thread / annotation-style dims** — and those are precisely the dims this filter sits next to. Always wrap the access; never branch on a raw `dim.FullName`:

```csharp
string fn;
try { fn = dim.FullName ?? ""; }
catch { fn = ""; }
```

A dim that throws on `FullName` won't match by name (it falls through as `""`). If it's a reference dim, the [clean and recolor](#how-to-clean-and-recolor-survivors) pass already removed it — **`IsReference()` never throws**, so if you only need to delete reference dims, skip the `FullName` branch entirely and key off `IsReference()` alone.

## How to: recover missing dims (after the loop)

When a view falls short of its Phase 1 expected count, patch the shortfall per view with drawing-side dims — pick the call by feature type (see the patch table in [API quick reference](#api-quick-reference)).

If only annotations (threads, GTOL, surface finish) are missing — not dims — re-run IMA4 annotations-only:

```csharp
swDraw.InsertModelAnnotations4(0, 0, false, true, false, false, false, false);
//                                  ^ bInsertAllDims=false, bInsertAnnotations=true
```

## How to: enforce an allowed-dim whitelist (heavy views)

For parts with >3 views or heavy thread/pattern construction-dim load, map each view to the set of allowed dim `FullName`s up front (from Phase 1's `dimPlan`), then enforce once after the loop — deleting anything not on the list.

```csharp
var viewAllowedDims = new Dictionary<string, HashSet<string>> {
    { "Section View A-A", new HashSet<string> { "D4@OD Sketch@…", "D1@ID Sketch@…" } },
    { "Detail View B",    new HashSet<string> { "D1@Sketch22@…" } },
};

foreach (var view in allViews) {
    var dd = (DisplayDimension)view.GetFirstDisplayDimension5();
    while (dd != null) {
        var next = (DisplayDimension)dd.GetNext5();
        var dim = (Dimension)dd.GetDimension2(0);
        if (!viewAllowedDims[view.GetName2()].Contains(dim.FullName)) {
            ((Annotation)dd.GetAnnotation()).Select3(false, null);
            swModel.EditDelete();
        }
        dd = next;
    }
}
```

## How to: move a dim to another view

Address the dim by `FullName`, select its annotation, then drag it into the target view. Do one dim per pass and rebuild between moves.

```csharp
swModel.ClearSelection2(true);
((Annotation)dd.GetAnnotation()).Select3(false, null);
swDraw.DragModelDimension(targetView.Name, 2, x, y, 0); // mode 2 = move; x,y in sheet meters
swModel.EditRebuild3();
```

## How to: fix combined chamfer callouts that hard-code 45°

Combined chamfer callouts (`"1×45°"` style) hard-code the `45°` text. When `AddChamferDim` produces the combined length-×-angle callout, the angle portion is fixed string text — it does **not** read the model angle. A 30° chamfer driven by `D2@FaseX = 30°` still renders as `1×45°` on the drawing, silently misrepresenting the part.

**Detect the case:** the dim's `DisplayDimension.GetText(swDimensionTextMain)` reads `<DIM>x45°` (or `<DIM>X45°`) regardless of the underlying model angle. The literal `45` in the callout is the tell.

**Fix — pick one:**

1. **Preferred for non-45° chamfers:** delete the combined callout and place two regular dims — a length dim (`AddDimension2` / `AddHorizontalDimension2` on the chamfer flat) plus an angle dim (`AddDimension2` on the chamfer edge against its reference face). This always reflects the real model values.
2. **Keep the combined look** but replace the literal text via `DisplayDimension.SetText(swDimensionTextMain, "<DIM>x30°")` (or whichever angle the model actually has). This is a drawing-side text override; it will not auto-update if the model angle later changes — leave a comment.

**Verify after either fix:** re-read `GetText(swDimensionTextMain)` and assert the angle substring matches `dim.SystemValue * 180 / Math.PI` for the angle dim of that chamfer.

## How to: chamfer & hole callouts (always-on overlays)

Both are per-feature annotations that layer on top of whatever dimensioning you're doing — apply them to **every** chamfered edge and **every** Hole Wizard feature. They complement (don't replace) the [combined-chamfer-callout fix above](#how-to-fix-combined-chamfer-callouts-that-hard-code-45): `AddChamferDim` here places the overlay, and that section handles the case where its combined `length×45°` text hard-codes the wrong angle.

### Chamfer

```csharp
swModel.ClearSelection2(true);
swExt.SelectByID2("", "EDGE", chamferEdge.X, chamferEdge.Y, chamferEdge.Z, false, 0, null, 0);
swExt.SelectByID2("", "EDGE", referenceEdge.X, referenceEdge.Y, referenceEdge.Z, true, 0, null, 0);
DisplayDimension cd = (DisplayDimension)swDraw.AddChamferDim(labelX, labelY, 0);
```

The second selection is the reference edge (the one the chamfer's angle is measured from). Text format (`C1×45°` vs `1×45°` vs distance×distance) comes from `Tools → Document Properties → Dimensions → Chamfer` or per-dim via `DisplayDimension.ChamferTextStyle`.

### Hole callout

```csharp
swModel.ClearSelection2(true);
swExt.SelectByID2("", "EDGE", holeEdge.X, holeEdge.Y, holeEdge.Z, false, 0, null, 0);
DisplayDimension hc = (DisplayDimension)swDraw.AddHoleCallout2(labelX, labelY, 0);
// swDispDim.GetText(swDimensionTextCalloutAbove) reads auto-generated text
```

`AddHoleCallout2` works on **Hole Wizard features only**. Plain `Cut` holes return `null` — check `Feature.GetTypeName2() == "HoleWzd"` first; for plain cuts use `AddDiameterDimension2` + manual `SetText` for THRU/depth. (The classifier's `round-hole` tag doesn't distinguish Hole Wizard from plain cuts.)

## How to: callout text (QUALIFIER / QUANTITY)

A raw `Ø6` is wrong when the plan says `6X Ø6 THRU` — the drawing is incomplete and a machinist can't make the part. **The moment you get a non-null `DisplayDimension` back from an `Add…Dimension2` / patch call, apply the qualifier and quantity before moving on** — batch it for later and you will forget.

Write each piece to its own part using the **PREFIX / ABOVE / SUFFIX** triplet (1, 3, 2) — see the [`swDimensionTextParts_e` table](#api-quick-reference). Writing to part 0 (`All`) backfires: a string containing a `<DIM>` token often gets stored whole in the **prefix** slot at runtime — it renders visually, but `GetText(0)` returns empty while `GetText(1)` holds your full string, breaking every search-by-text path. The triplet keeps each piece in the slot you wrote it to.

So when you must read a dimension's text back later (e.g. to find "the THRU hole"), read all four parts and concatenate rather than trusting part 0:

```csharp
string Combined(DisplayDimension d) =>
    (d.GetText(3) ?? "") + " " +
    (d.GetText(1) ?? "") + (d.GetText(2) ?? "") + " " +
    (d.GetText(4) ?? "");
```

**Cheat-sheet — right after `dim = (DisplayDimension)swDrawModel.Add…Dimension2(...)`:**

```csharp
const int PREFIX   = 1;
const int SUFFIX   = 2;
const int ABOVE    = 3;
const int BELOW    = 4;

// Simple hole — "Ø6 THRU"
dim.SetText(SUFFIX, " THRU");

// Patterned holes — "6X Ø6 THRU"
dim.SetText(ABOVE, "6X");
dim.SetText(SUFFIX, " THRU");

// Polygonal pocket across-flats (e.g. hex, pentagon, octagon) — "4X 10 A/F THRU"
// The measured value is the across-flats distance (see manual-dimensioning.md → "How to: polygonal pockets").
dim.SetText(ABOVE,  "4X");
dim.SetText(SUFFIX, " A/F THRU");

// Blind hole with depth — "Ø6 ▼ 10" (▼ = U+25BC, the ASME depth symbol)
dim.SetText(SUFFIX, " ▼ 10");

// Counterbore — "Ø6 THRU" with second line "⌴ Ø10 ▼ 5"
// Use CalloutBelow for the second line instead of a \n in part 0.
dim.SetText(SUFFIX, " THRU");
dim.SetText(BELOW,  "⌴ Ø10 ▼ 5");

// Chamfer — "1 × 45° TYP" (AddChamferDim already produces "1 × 45°")
dim.SetText(SUFFIX, " TYP");

// Fillet applied to many edges — "R3 TYP"
dim.SetText(SUFFIX, " TYP");

// Reference dimension — "(25)" style. Use PREFIX + SUFFIX parens, not part 0.
dim.SetText(PREFIX, "(");
dim.SetText(SUFFIX, ")");
```

(Token reference — `<MOD-DIAM>`, `▼`, `⌴`, `⌵`, etc. — is in the [API quick reference](#api-quick-reference).)

**Hole Wizard shortcut.** If the hole was made with Hole Wizard, use `AddHoleCallout2` instead of `AddDiameterDimension2` + manual `SetText` — it auto-generates the full callout from the hole's definition (`"6X M8x1.25 THRU"` etc.). Fall back to manual `SetText` only when the feature isn't a Hole Wizard hole.

**Gate before `AlignDimensions`.** Walk your dim table: for every row with a non-empty QUALIFIER or QUANTITY, confirm the matching `DisplayDimension` has `SetText` applied. If you can't produce that mapping from memory, you missed one — re-check before arranging.

## How to: straighten broken leaders on Ø / R dimensions

Under ISO drafting, diameter and radius dims default to a jogged ("broken") leader. To run the leader uninterrupted to a horizontal text shoulder:

```csharp
DisplayDimension dim = …;  // from AddDiameterDimension2 or AddRadialDimension2
dim.SetBrokenLeader2(false, (int)swBrokenLeader_e.swBrokenLeaderHorizontalText);
```

`SetBrokenLeader2(false, swBrokenLeaderHorizontalText)` works on both **diameter (`Type2 == 6`)** and **radius (`Type2 == 5`)** dims under the ISO standard. Apply it per-dim right after the `Add*Dimension2` call — same slot in the pipeline as the `SetText` qualifier replay above.

## How to: arrange dimensions (AutoArrange)

The always-last pass. Once every view is inserted, cleaned, recolored, and patched, run `AlignDimensions(AutoArrange)` once per view to reflow the layout — re-route leaders, space stacked labels, pick sides. Every insertion, deletion, reposition, or text edit leaves leaders drifting and labels colliding until you re-arrange, so this runs after all the steps above. Then hand-place only the 1–3 dims AutoArrange didn't nail with `SetPosition2`.

**Scope — automate the arrange, defer the polish.** Run `AlignDimensions(AutoArrange)` per view, then fix only dims that are *genuinely broken* — off-sheet, overlapping geometry or another annotation, or sitting in the title-block zone. Minor cosmetic placement — a label you'd nudge a few millimetres for taste — is left to the user. Don't burn turns chasing a pixel-perfect layout with `SetPosition2`; AutoArrange plus a handful of genuine-fault fixes is "done". Tell the user the dimensions are auto-arranged and invite them to fine-tune positions to preference.

The two APIs are NOT interchangeable:

| API | What it does | When to use |
|---|---|---|
| `IModelDocExtension.AlignDimensions(AutoArrange, spacing)` | Bulk reflow of selected dims — re-routes leaders, spaces stacked dims, picks sides | **Always last**, once per view, after every dim on that view is inserted, cleaned, and patched |
| `IAnnotation.SetPosition2(x, y, z)` | Move one dim's text to an explicit sheet coordinate | **Fine-tuning only**, on the 1–3 dims AutoArrange didn't quite get right |

SolidWorks does not retroactively re-route leaders when you move a dim's text: whatever attachment path existed at the time of `SetPosition2` is what you keep. So AutoArrange does the routing; `SetPosition2` only nudges the residue.

### Parameters

`IModelDocExtension.AlignDimensions(AlignType, SpaceValue)` → `bool` — `true` if any dim moved, `false` if nothing was selected or every dim was already arranged (a useful post-call sanity check). It acts on the **current selection**, so select the view's dims first.

**`AlignType`** (`swAlignDimensionType_e`, pass as `(int)`) — *which* arrangement to run:

| Value | Member | What it does |
|---|---|---|
| `0` | `swAlignDimensionType_AutoArrange` | The finish-pass operation: re-routes leaders, stacks parallel dims at even spacing, and picks which side of the view each lands on. **This is the one you call.** |
| — | `swAlignDimensionType_RightAligntext` | Right-aligns the text of the selected dims — a manual touch-up on a hand-picked selection, not a whole-view reflow. |

Other members align/space a hand-picked selection (collinear, parallel, group edges); they operate on exactly what you select, so they're for manual cleanup, not the bulk pass. **Casing traps:** every member is prefixed `swAlignDimensionType_` (not `swAlignDimension_`), and `RightAligntext` has a lowercase `t` — both wrong forms are silent compile errors.

**`SpaceValue`** (`double`, **meters**) — the gap between adjacent stacked dims. Only the spacing arrangements (AutoArrange) use it. Tune per view — don't reuse one constant across the sheet:

| View kind | SpaceValue |
|---|---|
| Detail | `0.005`–`0.006` (5–6 mm) |
| Standard / front | `0.008` (8 mm — default) |
| Large / dim-dense | `0.010` (10 mm) |

**Examples:**

```csharp
var ext = swModel.Extension;
const int AUTO = (int)swAlignDimensionType_e.swAlignDimensionType_AutoArrange;

ext.AlignDimensions(AUTO, 0.008);          // front/standard view — 8 mm
ext.AlignDimensions(AUTO, 0.005);          // detail view — tighter, 5 mm

bool moved = ext.AlignDimensions(AUTO, 0.010);   // large/crowded view — 10 mm
if (!moved) { /* nothing was selected, or it was already arranged */ }
```

**`IAnnotation.SetPosition2(x, y, z)`** — moves one dim's text to a sheet coordinate measured from the sheet's lower-left corner, in meters; Z is always `0`. It moves text only (leaders are not re-routed), doesn't reflow neighbours, doesn't reposition radial/diameter dim text (leader-attached), and returns `false` silently on unsupported annotation types — always check the return value. Read the dim's `GetPosition()` first to match the sheet frame before writing a new position.

Per view that was dimensioned: activate it, select every dim, AutoArrange with this view's spacing, clear. Rebuild once after all views, then verify each dim landed inside its view outline plus a 30 mm halo and `SetPosition2` only the genuine outliers.

```csharp
foreach (View v in allViewsThatGotDimensioned)
{
    swDraw.ActivateView(v.Name);
    swModel.ClearSelection2(true);

    // Select every dim on this view.
    var dd = (DisplayDimension)v.GetFirstDisplayDimension5();
    bool first = true;
    while (dd != null)
    {
        ((Annotation)dd.GetAnnotation()).Select3(!first, null); // first=false replaces; rest append
        first = false;
        dd = (DisplayDimension)dd.GetNext5();
    }

    if (!first) // had at least one dim
    {
        swModel.Extension.AlignDimensions(
            (int)swAlignDimensionType_e.swAlignDimensionType_AutoArrange,
            spacingMetersForThisView); // 0.005–0.010 typical
    }
    swModel.ClearSelection2(true);
}

swModel.EditRebuild3();
```

Run AutoArrange once per view (a second consecutive call is a no-op for AutoArrange), and arrange one view at a time — running it on the whole sheet mixes dims across views and produces strange stagger patterns. Verify placement afterward against `view.GetOutline()` ± 30 mm; for the few dims outside the halo, `SetPosition2` them individually rather than re-lowering the spacing and re-arranging the whole view (which re-disrupts everything that was already good). Run `EditRebuild3()` after any `SetPosition2` — the position is stored but the sheet doesn't repaint until the next interaction.

## Gotchas & fixes

- **To insert dims when IMA4 returns 0: fall back to `swDraw.InsertModelDimensions(0)`.** It is `IDrawingDoc.InsertModelDimensions(int Option)` — one int (`0` = all dims in the selected view), returns `void`, so re-count by walking `GetFirstDisplayDimension5` / `GetNext5`. IMA4 returns 0 when the model has no items "marked for drawing"; `InsertModelDimensions` projects driving dims regardless. Re-select the view before the fallback — earlier `EditDelete` / `EditRebuild` calls may have cleared selection.
- **To read a single dim value: use the `SystemValue` property, not `GetSystemValue3`.** `GetSystemValue3(...)` returns a `double[]` (one entry per config); `Convert.ToDouble(...)` on it throws `InvalidCastException`. For one value in the active config use `dim.SystemValue`; for all configs, `double[] all = (double[])dim.GetSystemValue3(1, null);` then `all[0]`.
- **To test for a reference dim: call `dim.IsReference()` with parens** (it is a method returning `bool`, not a property). When walking display dims, `dd.IsReferenceDim()` gives the same result.
- **To skip the title block: skip `Drawing View7`** — it is the title-block ISO view, not part geometry.
- **To keep dims legible in PDF: set `Annotation.Color = 6316128`** (RGB 96,96,96), the project default. Lighter than 128 washes out in PDF.
- **To recolor notes / GTOL / surface finish: walk `GetFirstNote` / `GetFirstGTOL` or `view.GetAnnotations()`.** `GetFirstDisplayDimension5` walks dimensions only, so annotation-class items are missed if you rely on it alone.
- **To move dims reliably: do one dim per `DragModelDimension` pass and `EditRebuild3()` between moves.** Address dims by `FullName` so the right one is selected after each rebuild.
- **To remove stray thread / construction angle dims: select the annotation and `EditDelete`.** Thread-callout angles and construction angle dims (helix lead, thread pitch, draft) often aren't flagged `IsReference()`, so the reference-dim pass leaves them behind — delete them explicitly, matching by `FullName` (`Thread` / `Helix` / `Draft` / `Cosmetic`). Keep real chamfer/taper angles. See [How to: drop unnecessary thread / construction angle dims](#how-to-drop-unnecessary-thread--construction-angle-dims).
- **`Dimension.FullName` throws `COMException` on cosmetic-thread / annotation-style dims — wrap every access.** Use `string fn; try { fn = dim.FullName ?? ""; } catch { fn = ""; }`; a raw `dim.FullName.Contains(...)` crashes the whole pass on the first cosmetic-thread dim. If you only need reference dims, skip the `FullName` branch — `IsReference()` doesn't throw.
- **For chamfer callouts: verify the angle substring against the model angle** — combined callouts hard-code `45°` and silently misrepresent non-45° chamfers (see [How to: fix combined chamfer callouts](#how-to-fix-combined-chamfer-callouts-that-hard-code-45)).
- **Always end with `AlignDimensions(AutoArrange)` once per view** — the last action after every view is inserted, cleaned, recolored, and patched. Skipping it ships overlapping, unstacked labels. `AlignDimensions(AutoArrange)` is shorthand — see the [How to: arrange dimensions (AutoArrange)](#how-to-arrange-dimensions-autoarrange) section above for the real signature, args, and recipe before calling it.

## Out of scope here

- **Manually adding dimensions from scratch** by selecting visible geometry (edges / vertices / faces) — e.g. when there's no model dim to project, or for overall dims from extreme vertices — see `manual-dimensioning.md` → "How to: add a dim from visible entities". The polygonal across-flats (A/F) recipe lives there too.
- Ordinate / baseline / chain / polar / tabular / GD&T systems, the Phase-1 system-selection decision, and the completeness table — see `dimensioning-systems.md`.
