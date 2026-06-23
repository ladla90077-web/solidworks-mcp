---
description: Pick a dimensioning system (ordinate / baseline / chain / polar / tabular / GD&T) for a part and drive its SolidWorks API; includes the Phase-1 system-selection decision and the per-feature completeness table.
---

# Guide: Dimensioning Systems

> Pick the right dimensioning system for a part (ordinate / baseline / chain / polar / tabular / GD&T) and apply it programmatically. Companion to `dimensioning-simple.md` (bulk per-dimension recipe — linear, Ø, angular; callout text, AutoArrange) and `manual-dimensioning.md` (dimensioning from visible entities, across-flats pockets); section-view dimensioning rules live in `section-views.md` → "Dimensioning a section view".

---

## Recipe (happy path)

1. **Phase 1 — pick the system** from the part type → [Choosing a system](#choosing-a-system-phase-1-decision).
2. **Phase 1 — build the completeness table**, one row per feature → [Completeness table](#completeness-table-phase-1-output).
3. **Phase 2 — drive the chosen system's API** → the matching `How to:` section below.
4. **Immediately after each `Add…Dimension2`**, replay the row's QUALIFIER + QUANTITY text → see `dimensioning-simple.md` → "How to: callout text (QUALIFIER / QUANTITY)".
5. **Arrange once at the end** → `AlignDimensions(AutoArrange)` per view; see `dimensioning-simple.md` → "How to: arrange dimensions (AutoArrange)".

---

## Choosing a system (Phase 1 decision)

The Part extractor emits a recommended `dimensioningSystem` string. Confirm or override it in the Phase 1 plan **before** filling the completeness table — the choice determines the *outer loop* of your Phase 2 code.

| System | When to use | Phase 2 API |
|---|---|---|
| **ordinate** | Flat/prismatic CNC part with many holes from a single origin; matches CNC G-code and CMM inspection | `IModelDocExtension.AddOrdinateDimension(swAddOrdinateDims_e.swHorizontalOrdinate/swVerticalOrdinate, x, y, z)` — see [How to: ordinate](#how-to-ordinate-dimensions) |
| **baseline** | Precision mill/turn work — every dim from one datum edge/face to avoid stack-up | Repeated `AddHorizontalDimension2` / `AddVerticalDimension2` each anchored to the **same** datum entity |
| **chain** | Non-critical geometry (weldments, sheet-metal fab) where stack-up doesn't matter; always leave one dim open + give an overall | `IModelDocExtension.InsertChainDimensions(entityArray)` or repeated `AddDimension2` |
| **polar** | Bolt circles, flanges, lathe cross-holes — radius + angle about a center | `AddRadialDimension2` for BCD + `AddDimension2`/`Create_Angular_Dimension` for index angles |
| **tabular** | ≥12 holes, mixed hole sizes, or part families — labels (A/B/C) on the view, X/Y/Ø in a table | `IDrawingDoc.InsertHoleTable2` (hole-table feature) or a general `TableAnnotation` with X/Y/Ø columns |
| **gdt** | Mating/functional features, cast/molded/forged parts, regulated industries | `IModelDocExtension.InsertGtol` (feature control frame) + `AddSymmetricDimension` for basic dims; datum tags via `InsertDatumTag` |

Apply these on top of **any** system:

| Overlay | Apply to | API |
|---|---|---|
| **chamfer** | Every chamfered edge | `IDrawingDoc.AddChamferDim(x, y, z)` — returns `DisplayDimension` with C×angle / dist×dist |
| **hole callout** | Every Hole Wizard feature | `IDrawingDoc.AddHoleCallout2(x, y, z)` after selecting a hole edge — compound Ø+depth+thread in one annotation |

### Default selection logic (matches the extractor)

- **Turned/revolved part** → `baseline` from end face, ODs/IDs off centerline.
- **Cast / shelled / swept form** → `gdt` with datum targets.
- **Flat plate + ≥12 holes** → `tabular`.
- **Flat plate + 6–11 holes, homogeneous** → `ordinate`.
- **Prismatic CNC with mixed features** → `baseline`.
- **Simple sheet-metal fab with few holes** → `chain`.
- **Everything else** → `baseline` (safe default for milled prismatic).

### Override rules (Phase 1 judgement)

- Customer spec or drawing standard mandates GD&T → `gdt` regardless of heuristic.
- Mixed hole sizes on a flat plate → prefer `tabular` over `ordinate` even below 12 (table column disambiguates sizes better than Ø on each arrow).
- Bolt-circle or rotary-indexed features on an otherwise-prismatic part → apply `polar` **for that subset only**; keep the rest on the part-level system.

**Keep one system per view.** Mix systems only with a documented override reason — consistency reads better than theoretical optimality. (Chamfer and hole-callout overlays are the only routine exception.)

---

## Completeness table (Phase 1 output)

Before Phase 2, convert the extracted feature list into an **explicit dimension table** — one row per feature. A blank row means the plan is incomplete; fill it before writing any drawing code. Missing rows are the #1 cause of drawings that ship without hole-location dims, THRU callouts, or depth qualifiers.

For **every** feature the extractor found (holes, cuts, bosses, revolves, fillets, chamfers, sheet-metal bends, patterns), fill in:

| Column | What goes here |
|---|---|
| SIZE | Diameter, length, width, height, radius, angle — the dim that defines the feature's own geometry |
| LOCATION | Distance from 2 datums (edges/centerlines) for every feature whose position isn't implied by symmetry, an edge, or an axis. Note "symmetric about ⌀" / "on centerline" when a dim is replaced by a symmetry note |
| QUALIFIER | THRU / depth / TYP / counterbore / countersink / chamfer size×angle — anything a machinist needs beyond raw size |
| QUANTITY | `4X`, `2X` for patterned features; blank if unique |

**Feature-type minimums** (sanity check — fewer dims than this for a given feature means something is missing):

- **Hole (simple, `round-hole` from classifier)** — Ø + location (2 dims OR symmetry note) + THRU or depth
- **Hole (counterbore/countersink)** — thru Ø + CB/CSK Ø + CB depth or CSK angle + location
- **Polygonal pocket (`polygon-Nsides-regular`)** — **A/F (across-flats) distance**, NOT a diameter. Plus orientation angle (if not aligned to a datum) + location + depth/THRU. Standard callout: `"4X 10 A/F THRU"`. Recipe: see `manual-dimensioning.md` → "How to: polygonal pockets (across-flats)".
- **Slot (`slot`)** — length + width + location of center + depth (or THRU)
- **Rectangular pocket (`rectangle`/`square`)** — W × H + location + depth (or THRU)
- **Boss/extrude** — W × H + location + height
- **Revolve** — profile dims (every OD/ID + length segment) + overall length
- **Fillet** — R + which edges (TYP if pattern)
- **Chamfer** — size × angle (or `1 × 45°`) + which edges
- **Pattern** — base-feature dims + pitch + count (e.g. `4X Ø6 THRU EQ SP`)

**Trust the classifier tag, not the feature name.** `"Hole pattern"` in the feature tree is a user-assigned name — it can wrap hex pockets, square cutouts, or anything else. The `[tag]` from `ClassifyCutProfile` (`round-hole`, `polygon-6sides-regular`, `slot`, `rectangle`, `freeform(...)`) tells you the actual profile topology and therefore which dimensioning API to plan for.

**Pick datums before filling LOCATION cells.** Choose 2 datums (usually two orthogonal edges or centerlines of the primary view). Every location dim references those same 2 datums. Chain feature-to-feature only when the relationship genuinely matters (e.g. a bolt-hole pattern on a bolt circle, where BCD is the intent).

**Skip dims already implied** by the overall bounding box or a symmetry note. A hole dead-center on a rectangular plate needs only `Ø` + `THRU` + a `⌀` symmetry note — not two location dims.

**Tie every cell to Phase 2.** Each non-empty QUALIFIER or QUANTITY cell corresponds to a `DisplayDimension::SetText(...)` call. A `6X Ø6 THRU` row becomes `dim.SetText(3, "6X")` + `dim.SetText(2, " THRU")` — see `dimensioning-simple.md` → "How to: callout text (QUALIFIER / QUANTITY)".

End Phase 1 with "proceed?" only after the table is complete and every row is filled. The temptation to skip this on a part that "looks simple" is exactly when hole-location dims go missing.

---

## API quick reference

**`swAddOrdinateDims_e`** (pass as `(int)`):

| Value | Constant | Meaning |
|---|---|---|
| 1 | `swOrdinate` | direction auto-picked from first two selected points — prefer explicit |
| 2 | `swVerticalOrdinate` | measures Y distance, labels stack vertically |
| 3 | `swHorizontalOrdinate` | measures X distance, labels stack along a row |
| 4 | `swAngularOrdinate` | polar-ordinate for rotary parts |

**`swCreateOrdDimError_e`** — return code of `AddOrdinateDimension` (an `int`, **not** a `DisplayDimension`):

| Code | Constant | Meaning / likely cause |
|---|---|---|
| 0 | `Success` | OK |
| -1 | `Undefined` | unknown state — re-check the view is active |
| 1 | `GenFailure` | generic failure — base entity not selected first |
| 2 | `GenNoInternalDims` | no internal dims — feature imported without dims |
| 3 | `GenBadSel` | bad selection — face/body picked instead of edge/vertex |
| 4 | `GenNeedModelLoaded` | referenced model unloaded |
| 5 | `GenSamePartOnly` | cross-part selection — one part per group |
| 6 | `GenExtraSelection` | too many entities — clear before each append |
| 7 | `OrdFailure` | generic ordinate failure — coordinates landed off-entity |
| 8 | `OrdDupInGroup` | feature already in the group |
| 9 | `OrdBadDir` | bad direction — `swOrdinate` with coplanar points |

> A `0` return does **not** guarantee the dim attached — the bare-selection-append path returns `0` but silently no-ops (see [How to: ordinate](#how-to-ordinate-dimensions)). Always verify by counting `GetFirstDisplayDimension5`/`GetNext5` after the loop.

**Selection signatures:**

`SelectByID2(Name, Type, X, Y, Z, Append, Mark, Callout, SelectOption)`
- `Name` — persistent id (e.g. `"Edge<1>@Drawing View1"`); `""` locates by XYZ.
- `Type` — `"VERTEX"`, `"EDGE"`, `"SKETCHPOINT"`, `"DIMENSION"`, etc.
- `X, Y, Z` — **sheet-space** meters (drawings use `Z ≈ -500` as a sentinel in the 2007+ C# examples).
- `Append` — `false` clears prior selection; `true` adds to it.
- `Mark, Callout, SelectOption` — pass `0, null, 0` unless you specifically need them.

`View.SelectEntity(entity, Append)` — `entity` is an `IEdge`/`IVertex`/`ISketchPoint` pointer you already hold (skips the XYZ lookup); `Append` as above.

`IAnnotation.Select3(Append, Mark)` — `Append` `false` to replace / `true` to add; `Mark` usually `null`.

---

## How to: ordinate dimensions

Ordinate is the most leveraged system for CNC-friendly drawings and the one most often done wrong programmatically. The API is stateful — get the sequence right or every dim after the first fails silently.

### Start with `AddOrdinateDimension`, not `InsertModelDimensions`

When the plan says ordinate, go **straight** to `AddOrdinateDimension`. Reaching for `InsertModelDimensions` (or any generic "insert dims" helper) first and then deleting-and-replacing costs you:

- stranded callouts (hole diameters, chamfer dims) that looked like part of the linear dims SW just inserted,
- ~30 s per view on two round-trips that land on the same state as skipping the first call,
- orphan dims bound to the sheet view that never show up in `view.GetFirstDisplayDimension5` — only a full-drawing audit finds them.

Same rule for `tabular`, `polar`, and `gdt` — jump straight to their sections. `InsertModelDimensions` is the right first step only for `baseline` and `chain`.

### Base the 0 datum on a virtual sharp

The 0 datum of any ordinate group must be a **virtual sharp** (theoretical corner) — the pickable point SolidWorks auto-generates where two edges would meet if the fillet weren't there. A plate with radiused corners, a turned shoulder with a fillet, an inside pocket with rounded corners: the "natural" vertex sits on the radius, not at the theoretical corner a machinist or CMM operator zeroes to. Base off the radius endpoint and every downstream dim is offset by the fillet R — silently. The drawing looks fine until parts come back out-of-tolerance.

To base correctly:

1. Walk `view.GetVisibleEntities2(null, swViewEntityType_SketchPoint)` for the view.
2. Keep only `ISketchPoint.Type == swSketchPointType_VirtualSharp` (value = `4`).
3. If no virtual sharps are visible, **insert them first** — select the two adjacent edges and use `ISketchManager.AddToDB` / the "Point at Virtual Intersection" path (or set the view's `DisplaySharps = true`).
4. Pick the virtual sharp as the base entity (`SelectByID2(..., "SKETCHPOINT", ...)` / `SelectEntity`), then seed the group with `AddOrdinateDimension`.

```csharp
// Find the virtual sharp at the lower-left corner of the view
object[] sps = (object[])view.GetVisibleEntities2(null, (int)swViewEntityType_e.swViewEntityType_SketchPoint);
ISketchPoint baseSharp = null;
double minX = double.MaxValue, minY = double.MaxValue;
foreach (object o in sps ?? Array.Empty<object>())
{
    SketchPoint sp = (SketchPoint)o;
    if (sp.Type != (int)swSketchPointType_e.swSketchPointType_VirtualSharp) continue;  // MANDATORY filter
    if (sp.X <= minX + 1e-6 && sp.Y <= minY + 1e-6) { baseSharp = sp; minX = sp.X; minY = sp.Y; }
}
if (baseSharp == null)
    throw new InvalidOperationException("No virtual sharp on this view — insert virtual sharps before ordinate dimensioning");

view.SelectEntity((Entity)baseSharp, false);  // Append=false — this is the 0 datum
```

When the view lacks a virtual sharp at the datum you want, add one — a `VERTEX` on a filleted corner sits on the radius, not the theoretical corner.

### Append with `EditOrdinate` (the bare-select pattern no-ops)

SolidWorks' own `Create_Ordinate_Dimensions_Example_CSharp.md` shows a "keep selecting after the first `AddOrdinateDimension` and dims auto-append" pattern. From COM that pattern **silently no-ops** — `AddOrdinateDimension` returns `Success`, no error is raised, but only the first dim attaches. Append each subsequent feature with `EditOrdinate` instead:

```
1. ActivateView("<ViewName>")                              ── must be the right view
2. ClearSelection2(true)                                   ── always start clean
3. SelectEntity(BASE entity,   Append=false)               ── becomes the 0 datum
4. SelectEntity(firstFeature,  Append=true)
5. AddOrdinateDimension(type, labelX, labelY, 0)           ── creates group + first dim
── returns an int error code, not the DisplayDimension — recover the handle (see below) ──
6. For each remaining feature:
     ClearSelection2(true)
     existingGroupMember.Select3(false, null)              ── re-selects a dim in the group
     view.SelectEntity(nextFeature, Append=true)
     swModel.EditOrdinate()                                 ── appends nextFeature
7. (No SetPickMode needed — EditOrdinate closes cleanly each call)
```

### Recover the base dimension handle

`AddOrdinateDimension` returns an `int` (a `swCreateOrdDimError_e` code), not the `DisplayDimension` it created. To append more features you need a handle to any group member — walk `GetFirstDisplayDimension5` and match by expected label position.

```csharp
DisplayDimension FindOrdinateMember(View v, double expectedLabelX, double tol)
{
    DisplayDimension dd = (DisplayDimension)v.GetFirstDisplayDimension5();
    while (dd != null)
    {
        Annotation a = (Annotation)dd.GetAnnotation();
        double[] p = (double[])a.GetPosition();
        if (Math.Abs(p[0] - expectedLabelX) < tol) return dd;
        dd = (DisplayDimension)dd.GetNext5();
    }
    return null;
}
```

### Full working loop

```csharp
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

DrawingDoc swDraw = (DrawingDoc)swModel;
ModelDocExtension swExt = swModel.Extension;
View v = (View)swDraw.ActivateView("Drawing View1");
swModel.ClearSelection2(true);

// 1. Base datum — MUST be a virtual sharp (see above). Never a fillet endpoint or radiused vertex.
swExt.SelectByID2("", "SKETCHPOINT", baseSharpX, baseSharpY, baseSharpZ, false, 0, null, 0);

// 2. First hole edge — append to seed the group
swExt.SelectByID2("", "EDGE", holes[0].X, holes[0].Y, holes[0].Z, true, 0, null, 0);

// 3. Create group + first dim (returns ERROR CODE, not a handle)
int err = swExt.AddOrdinateDimension(
    (int)swAddOrdinateDims_e.swHorizontalOrdinate,
    labelStartX, labelRowY, 0);
if (err != 0) throw new InvalidOperationException($"Ordinate seed failed: {(swCreateOrdDimError_e)err}");

// 4. Recover a handle to any group member (needed for EditOrdinate appends)
DisplayDimension anchor = FindOrdinateMember(v, labelStartX, 0.001);
if (anchor == null) throw new InvalidOperationException("Couldn't locate seeded ordinate dim");
Annotation anchorAnn = (Annotation)anchor.GetAnnotation();

// 5. Append remaining features via EditOrdinate
for (int i = 1; i < holes.Count; i++)
{
    swModel.ClearSelection2(true);
    anchorAnn.Select3(false, null);                                       // mark the group
    v.SelectEntity(holeEdges[i], true);                                   // Append=true
    swModel.EditOrdinate();                                               // actually appends
}
```

### `AddOrdinateDimension` argument reference

`AddOrdinateDimension(DimType, LocX, LocY, LocZ)`:
- `DimType` — `swAddOrdinateDims_e` (see [API quick reference](#api-quick-reference)). Pass as `(int)`.
- `LocX`, `LocY` — label position in sheet meters. For `swHorizontalOrdinate`, `LocX` drives the first label and subsequent labels extend along X at the same `LocY`; for `swVerticalOrdinate` it's the reverse — `LocY` fixes the row and labels walk along Y.
- `LocZ` — always `0.0` for 2D drawings.
- returns `int` (`swCreateOrdDimError_e`), **not** a `DisplayDimension` pointer.

### Horizontal and vertical are separate groups

Horizontal and vertical ordinates are **separate groups**, each with its own base. For an XY plate, run TWO full sequences: one `swHorizontalOrdinate` for X positions, one `swVerticalOrdinate` for Y. They share no state.

### Editing an existing group

- **Add more features** → `IModelDoc2.EditOrdinate` (select the group's base dim, then the new feature entity — this is the append mechanism in the loop above).
- **Fix a broken base reference** → `IModelDoc2.ReattachOrdinate`.
- **Clean up spacing** → `IDrawingDoc.AlignOrdinate` (redistributes labels evenly along the row).

### Ordinate best practices

- **Match circles vs arcs when finding feature entities.** `view.GetVisibleEntities2` returns both. Full circles (through-holes) have `IEdge.GetStartVertex() == null`; arcs (fillets, partial cuts) have real vertices. Filter `sv == null` for holes, `sv != null` for fillet radii — matching on radius alone conflates a Ø10 hole with an R5 fillet.
- **Place labels OUTSIDE the view bounds** with ~15 mm clearance. Extension lines may cross geometry; label text must not.
- **Let labels auto-jog** — set `DisplayDimension.AutoJogOrdinate = true` so extension lines jog when labels would collide.
- **Share one row Y (horizontal) / column X (vertical)** across a group; don't let labels drift.
- **Keep the "0" label on the base** — SolidWorks auto-labels it; it's the visual anchor.
- **One group per datum axis per view** — never split a horizontal group across two base entities.
- **Use meters** in every coordinate argument (`SelectByID2`/`SelectEntity` and the `AddOrdinateDimension` label positions).
- **`ActivateView` first** — ordinate dims attach to the active view, not the view whose entity you selected.
- **Verify the group size after the loop** — count `GetFirstDisplayDimension5`/`GetNext5` in the view; a count ≠ expected means the append path didn't attach (usually a stale `anchorAnn.Select3` after a rebuild).

---

## How to: baseline dimensions

No dedicated API — baseline is a **pattern**, not a method. Create N individual dims, all anchored to the same datum entity.

```csharp
swDraw.ActivateView("Drawing View1");
swModel.ClearSelection2(true);

// For each feature, make a dim from (datumEdge, featureEdge)
foreach (var feat in features)
{
    swModel.ClearSelection2(true);
    swExt.SelectByID2("", "EDGE", datumEdge.X, datumEdge.Y, datumEdge.Z, false, 0, null, 0);
    swExt.SelectByID2("", "EDGE", feat.X, feat.Y, feat.Z, true, 0, null, 0);

    // Choose Horizontal or Vertical based on measurement axis
    DisplayDimension dim = (DisplayDimension)swModel.AddHorizontalDimension2(
        labelX_stacked_per_feature, labelY, 0);
}
```

- Stack labels on ~8 mm increments moving away from the part (`AlignDimensions(AutoArrange)` handles this automatically — call it once at the end; see `dimensioning-simple.md` → "How to: arrange dimensions (AutoArrange)" for the real signature).
- Anchor every dim to the **same geometric entity**, not two edges that merely happen to be collinear — otherwise a future datum shift decouples them.
- Keep it baseline: every dim from the datum. The moment you dim A→B then B→C you've made a chain, not a baseline.

---

## How to: chain dimensions

```csharp
object[] entities = new object[] { edge0, edge1, edge2, edge3 };
object dimArray = swExt.InsertChainDimensions(entities);
// Returns an array of IDisplayDimension
```

Or the manual pattern: N pairwise `AddDimension2`/`AddHorizontalDimension2` calls, each from the previous entity to the next.

- Add an overall dim on top, and leave **one** chain dim out (covered by the overall) — that keeps the chain from over-constraining on inspection.
- Reserve chain for non-critical geometry. On CNC parts, prefer baseline or ordinate.

---

## How to: polar dimensions

No single polar-dim API. Assemble from:
- **`AddRadialDimension2(x, y, z)`** on the bolt-circle diameter (the BCD itself).
- **Angular dims** between each feature and a reference axis — see `Create_Angular_Dimension_Example_CSharp.md`.
- **`AddAngularRunningDim`** (`IModelDocExtension`) for ordinate-style angular layout.

- Call out BCD as `"N×Ø<hole dia> EQ SP ON Ø<BCD> B.C."` using `SetText(3, "NX ")` + suffix for `EQ SP ON …`.
- For unevenly indexed holes, use `swAngularOrdinate` ordinate from a reference axis.

---

## How to: tabular dimensions

```csharp
// IDrawingDoc.InsertHoleTable2 — creates a hole-table annotation
HoleTable ht = (HoleTable)swDraw.InsertHoleTable2(
    useDocumentSettings: true,
    anchorType: 0,        // 0 = top-left
    x: tableX, y: tableY,
    datumX: 0, datumY: 0, // drawing origin for X/Y columns
    tagStyle: "A1",
    sortOrder: 0);
```

- The datum passed to `InsertHoleTable2` must match the ordinate/baseline datum you'd otherwise pick — CMM programs read off the table.
- For mixed hole sizes, the table's Ø column does the disambiguation; skip per-hole Ø callouts on the view.
- Labels (A1, A2, B1, …) auto-generate — leave them alone, or the table sort breaks.

---

## How to: GD&T (feature control frames)

```csharp
// IModelDocExtension.InsertGtol — opens the feature control frame
Gtol gt = (Gtol)swExt.InsertGtol();
// Configure via IGtol.SetFrameValues2 — see Insert_GTol_Example_CSharp.md
```

- **Insert datum tags first** (`InsertDatumTag`), then the FCFs that reference them — an `InsertGtol` on a feature referencing datum `A` produces a broken frame if `A` doesn't exist yet.
- Create basic dimensions (theoretical exact) via `AddSymmetricDimension` + the `[`/`]` PREFIX/SUFFIX or the document's basic-dim style.
- Stack FCFs in order: position > orientation > form. Keep them un-intermixed.
- Apply material conditions (MMC Ⓜ, LMC Ⓛ) only where bonus tolerance is actually usable — MMC on a press-fit is a bug.

See `Insert_GTol_Example_CSharp.md` and `Create_Gtol_Composite_Frame_Example_CSharp.md` for complete frame-construction code.

---

## Gotchas & fixes

- **Keep one system per view.** Mixing systems confuses the reader; chamfer and hole-callout overlays are the only routine exception.
- **Append ordinates with `EditOrdinate`.** The bare-select-append pattern returns `Success (0)` but attaches only the first dim. Verify by counting dims after the loop.
- **Base ordinates on a virtual sharp**, never a rounded/radiused edge — `swSketchPointType_VirtualSharp = 4` from `GetVisibleEntities2`. A fillet-endpoint base offsets every downstream dim by the fillet R, silently. If no sharp exists, insert one before dimensioning.
- **Tell circles from arcs** when picking feature entities — both come from `GetVisibleEntities2`. Filter `GetStartVertex() == null` for full circles (holes) vs real vertices for fillet arcs.
- **`ActivateView` first.** `AddOrdinateDimension` / `AddChamferDim` / `AddHoleCallout2` attach to the *active* view, not the view whose entity you selected.
- **Pin the datum entity once for baseline.** Reusing a different datum edge each time produces chain, not baseline.
- **Match the tabular datum** passed to `InsertHoleTable2` to the drawing's ordinate/baseline datum — a mismatch makes the CMM program wrong.
- **Insert datum tags before GD&T.** `InsertGtol` referencing datum `A` produces a broken frame if `A` wasn't inserted yet.
