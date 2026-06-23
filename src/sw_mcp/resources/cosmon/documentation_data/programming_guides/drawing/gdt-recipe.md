---
description: Part-agnostic GD&T recipe for SolidWorks drawings. Pre-2022 string-based API. UPPERCASE tokens (lowercase silently no-renders). Datum tags → basic dims → FCFs. Cookbook of common FCFs, composite frames, basic-dim setup, and datum-scheme selection by manufacturing type.
---

# Recipe: GD&T on Any SolidWorks Drawing

> Apply datum tags and feature control frames (FCFs) to any SolidWorks drawing using the pre-2022 string-based GTol API. Use when a part needs geometric tolerancing — position, orientation, form, runout, or profile. (For the 2022+ schema, use `IGtolFrame.SetSymbolXml`.)

## Recipe (happy path)

1. Insert views (see `section-views.md`, `detail-views.md`), then dimensions — `InsertModelAnnotations4` or the `AddXxxDimension2` family (see `dimensioning-simple.md` / `manual-dimensioning.md`).
2. Set `tol.Type = 1` (swTolBASIC) on the basic dims that Position / Angularity FCFs reference → [How to: basic dimensions](#how-to-basic-dimensions-required-by-position--angularity-fcfs).
3. Insert one `InsertDatumTag2()` per datum letter (A, B, C) the FCFs reference → [How to: datum tags](#how-to-attach-a-datum-tag-to-an-edge-or-face). Insert datum tags first so FCFs render filled datum cells.
4. For each FCF, walk `view.GetFirstDisplayDimension5()` to find the dim that references the feature, then attach the GTol to that dim with `InsertGtol()` → [How to: FCF on an existing dimension](#how-to-attach-an-fcf-to-an-existing-dimension-default-path). This is the default path.
5. When no dim references the feature anywhere on the sheet, attach the FCF to the edge instead → [How to: FCF on an edge](#how-to-attach-an-fcf-to-an-edge-fallback).
6. Merge composite frames with `SetCompositeFrame2(true, 1)` → [How to: composite FCF](#how-to-build-a-composite-fcf-one-gcs-two-rows).
7. Promote any FCF that doubles as a datum with `gtol.SetDatumIdentifier(...)` → [How to: datum tags](#how-to-attach-a-datum-tag-to-an-edge-or-face).
8. `ForceRebuild3(true)` + `ClearSelection2(true)` at the end.

## API quick reference

Pre-2022 GTol format, string-based API. All `SetFrameSymbols2` / `SetFrameValues2` params are strings (tokens from `gtol.sym`), not enum ints.

### Core calls

| Call | Returns | Notes |
|---|---|---|
| `swDoc.InsertDatumTag2()` | `DatumTag` (`null` if nothing selected) | Select target edge/face first; always null-check. |
| `swDoc.InsertGtol()` | `Gtol` (`null` if nothing selected) | Select a dim's `Annotation` (default) or an edge (fallback) first; always null-check. |
| `gtol.SetFrameSymbols2(row, sym, dia, mc1, ..., "", "", "", "")` | — | `sym` is a GCS token; `dia` bool draws Ø; `mc1` is a modifier token. |
| `gtol.SetFrameValues2(row, tol1, tol2, d1, d2, d3)` | — | Tolerance values are in **display units** (`"0.25"` = 0.25 mm if drawing is mm, 0.25 in if inches). |
| `gtol.SetCompositeFrame2(true, 1)` | — | Merges rows into one tall GCS cell. |
| `gtol.SetPTZHeight2(1, 1, true, "50")` | — | Projected tolerance zone height (e.g. `"50"` mm). |
| `gtol.SetDatumIdentifier("B")` | — | Makes an FCF double as a datum (integrated, no separate tag). |
| `gtol.GetFrameSymbols3(1)` | `string[6]` | Read back FCF symbols. |
| `gtol.GetFrameValues(1)` | `string[5]` | `[Tol1, Tol2, D1, D2, D3]`. |
| `dt.SetLabel("A")` | — | Datum label, ≤ 2 chars. |
| `dt.FilledTriangle` | bool | `true` = ASME filled; `false` = ISO open. |
| `view.GetVisibleEntities2(comp, type)` | `object[]` | `comp` is `null` for parts, `IComponent2` for assemblies. |
| `swDoc.ClearSelection2(true)` | — | Run between every annotation so stale selection isn't reused as the next anchor. |
| `swDoc.ForceRebuild3(true)` | — | Run after every insert so leaders redraw. |

### Geometric Characteristic Symbols (GCS)

Use UPPERCASE tokens — `<IGTOL-POSI>` renders; `<igtol-posi>` stores the property but draws no symbol and raises no error.

| Symbol | Name | Token |
|---|---|---|
| ⊕ | Position | `<IGTOL-POSI>` |
| ⊥ | Perpendicularity | `<IGTOL-PERP>` |
| ∥ | Parallelism | `<IGTOL-PARA>` |
| ∠ | Angularity | `<IGTOL-ANGU>` |
| ▱ | Flatness | `<IGTOL-FLAT>` |
| — | Straightness | `<IGTOL-STR>` |
| ○ | Circularity | `<IGTOL-ROUND>` |
| ⌭ | Cylindricity | `<IGTOL-CYLI>` |
| ⌒ | Profile of Surface | `<IGTOL-SPRO>` |
| ⌢ | Profile of Line | `<IGTOL-LPRO>` |
| ◎ | Concentricity | `<IGTOL-CONC>` |
| ≡ | Symmetry | `<IGTOL-SYMM>` |
| ↗ | Circular Runout | `<IGTOL-CIRC>` |
| ⇉ | Total Runout | `<IGTOL-TOTL>` |

### Material Condition & Diameter Modifiers

| Modifier | Token | Where it goes |
|---|---|---|
| MMC Ⓜ | `<MOD-MMC>` | `TolMC1` arg, or append to datum: `"A<MOD-MMC>"` |
| LMC Ⓛ | `<MOD-LMC>` | same |
| RFS Ⓢ | `<MOD-RFS>` | same (default in ASME Y14.5-2009+; rarely written) |
| Projected Ⓟ | `<MOD-PROJ>` | `TolMC1` arg |
| Diameter Ø | `<MOD-DIAM>` | rarely used as string; prefer `TolDia1=true` arg |
| None | `""` | empty string, not `null` |

### Annotation types (for `view.GetFirstAnnotation3()` walks)

| Type | Object |
|---|---|
| 2 | DatumTag |
| 4 | DisplayDimension |
| 5 | Gtol (FCF) |
| 6 | SectionLine |
| 13 | CenterMark |
| 15 | Note |

### `swTolType_e` (for `tol.Type` / `SetTolerance2`)

`0` NONE, `1` BASIC, `2` BILAT, `3` LIMIT, `4` SYMMETRIC, `5` MIN, `6` MAX, `7` FIT, `10` BLOCK, `11` General.

## How to: attach a datum tag to an edge or face

```csharp
swDraw.ActivateView(viewName);

// Get edges; null for parts, IComponent2 for assemblies
object[] edges = (object[])view.GetVisibleEntities2(
    isAssembly ? (Component2)comp : null,
    (int)swViewEntityType_e.swViewEntityType_Edge);

// Identify target edge by geometry:
//   ((Curve)edge.GetCurve()).IsLine() / .IsCircle()
//   edge.GetStartVertex().GetPoint() / edge.GetEndVertex().GetPoint() → double[3] meters
//   For circles: ((Curve)edge.GetCurve()).CircleParams → double[7] = [cx,cy,cz, ax,ay,az, r]
Entity datumEdge = (Entity)edges[targetIndex];

swDoc.ClearSelection2(true);
view.SelectEntity(datumEdge, false);

DatumTag dt = (DatumTag)swDoc.InsertDatumTag2();
if (dt == null) throw new InvalidOperationException("InsertDatumTag2 returned null");

dt.SetLabel("A");              // ≤ 2 chars
dt.FilledTriangle = true;      // ASME filled; false = ISO open

Annotation ann = (Annotation)dt.GetAnnotation();
ann.SetPosition2(x_m, y_m, 0); // sheet space, meters

swDoc.ForceRebuild3(true);
```

**Datum on a feature that already has a dimension.** Declare the datum on an FCF that targets the same feature with `gtol.SetDatumIdentifier("B")` — a single call that makes the FCF double as the datum, no separate tag. (The API exposes no working path to make an `IDatumTag` a child of an `IDisplayDimension`: selecting the dim's annotation before `InsertDatumTag2`, re-parenting via the annotation, etc. all fail.) If no FCF targets the feature, fall back to a free-standing tag on the edge using the snippet above, accepting the extra leader as the cost.

## How to: attach an FCF to an existing dimension (DEFAULT PATH)

Attaching the FCF to an existing dimension draws no new leader — the frame hangs off the dimension itself. Prefer this path: walk `view.GetFirstDisplayDimension5()` first and attach the GTol to whichever dim already references the feature.

```csharp
// Walk view.GetFirstDisplayDimension5() / GetNext5() to find the dim referencing the feature
DisplayDimension dd = ...;
Annotation dimAnn = (Annotation)dd.GetAnnotation();

swDoc.ClearSelection2(true);
dimAnn.Select3(false, null);

Gtol g = (Gtol)swDoc.InsertGtol();
if (g == null) throw new InvalidOperationException("InsertGtol returned null — dim not selected");

g.SetFrameSymbols2(1, "<IGTOL-POSI>", true, "<MOD-MMC>", false, "", "", "", "");
g.SetFrameValues2 (1, "0.25", "", "A", "B", "");

swDoc.ForceRebuild3(true);
```

If a dim references the feature in **any** view of the sheet, attach there rather than creating a new annotation — redundant leaders for already-dimensioned features are a defect. Use the edge fallback only when no dim references the feature at all.

## How to: build the FCF cookbook callouts

After selecting the anchor and getting a non-null `Gtol g` (from either path above), configure the frame. Common callouts:

```csharp
// Flatness 0.05 (no datum, no Ø)
g.SetFrameSymbols2(1, "<IGTOL-FLAT>", false, "",          false, "", "",  "", "");
g.SetFrameValues2 (1, "0.05", "", "", "", "");

// Perpendicularity Ø0.05 | A
g.SetFrameSymbols2(1, "<IGTOL-PERP>", true,  "",          false, "", "",  "", "");
g.SetFrameValues2 (1, "0.05", "", "A", "", "");

// Position Ø0.25 MMC | A | B | C
g.SetFrameSymbols2(1, "<IGTOL-POSI>", true,  "<MOD-MMC>", false, "", "",  "", "");
g.SetFrameValues2 (1, "0.25", "", "A", "B", "C");

// Position Ø0.25 MMC | A | B(MMC) | C(LMC)
g.SetFrameSymbols2(1, "<IGTOL-POSI>", true,  "<MOD-MMC>", false, "", "",  "", "");
g.SetFrameValues2 (1, "0.25", "", "A", "B<MOD-MMC>", "C<MOD-LMC>");

// Concentricity Ø0.03 | A
g.SetFrameSymbols2(1, "<IGTOL-CONC>", true,  "",          false, "", "",  "", "");
g.SetFrameValues2 (1, "0.03", "", "A", "", "");

// Circular Runout 0.05 | A
g.SetFrameSymbols2(1, "<IGTOL-CIRC>", false, "",          false, "", "",  "", "");
g.SetFrameValues2 (1, "0.05", "", "A", "", "");

// Total Runout 0.05 | A | B
g.SetFrameSymbols2(1, "<IGTOL-TOTL>", false, "",          false, "", "",  "", "");
g.SetFrameValues2 (1, "0.05", "", "A", "B", "");

// Cylindricity 0.02
g.SetFrameSymbols2(1, "<IGTOL-CYLI>", false, "",          false, "", "",  "", "");
g.SetFrameValues2 (1, "0.02", "", "", "", "");

// Profile of Surface 0.4 | A | B
g.SetFrameSymbols2(1, "<IGTOL-SPRO>", false, "",          false, "", "",  "", "");
g.SetFrameValues2 (1, "0.4",  "", "A", "B", "");

// Position with Projected Tolerance Zone Ø0.25 (height set separately)
g.SetFrameSymbols2(1, "<IGTOL-POSI>", true,  "<MOD-PROJ>", false, "", "", "", "");
g.SetFrameValues2 (1, "0.25", "", "A", "B", "C");
g.SetPTZHeight2  (1, 1, true, "50");          // 50 mm projection height
```

## How to: attach an FCF to an edge (FALLBACK)

Reserve edge-attach for the case where no dim references the feature anywhere on the sheet — it creates a new leader, which is a defect when a dim for the feature already exists. Before using this path, confirm all three:

1. Walked `view.GetFirstDisplayDimension5()` in the target view,
2. Walked it in **every other view** that shows the same feature,
3. Found zero dims referencing the feature anywhere on the sheet.

If a feature lacks a dim because dimensioning was skipped, add the dim first and attach via the [default path](#how-to-attach-an-fcf-to-an-existing-dimension-default-path) — that keeps missing dimensioning from being papered over with a free leader.

```csharp
swDoc.ClearSelection2(true);
view.SelectEntity(targetEdge, false);

Gtol g = (Gtol)swDoc.InsertGtol();
if (g == null) throw new InvalidOperationException("InsertGtol returned null");

g.SetFrameSymbols2(1, "<IGTOL-PERP>", false, "", false, "", "", "", "");
g.SetFrameValues2 (1, "0.05", "", "A", "", "");

((Annotation)g.GetAnnotation()).SetPosition2(x_m, y_m, 0);
swDoc.ForceRebuild3(true);
```

## How to: build a composite FCF (one GCS, two rows)

Pattern-locating (upper, looser) + feature-relating (lower, tighter). Same symbol; lower row typically drops datums.

```csharp
// Row 1: pattern-locating
g.SetFrameSymbols2(1, "<IGTOL-POSI>", true, "<MOD-MMC>", false, "", "", "", "");
g.SetFrameValues2 (1, "0.5", "", "A", "B", "C");

// Row 2: feature-relating (fewer datums, tighter tolerance)
g.SetFrameSymbols2(2, "<IGTOL-POSI>", true, "<MOD-MMC>", false, "", "", "", "");
g.SetFrameValues2 (2, "0.1", "", "A", "", "");

// Merge into composite (single tall GCS cell spanning both rows)
g.SetCompositeFrame2(true, 1);
```

Keep Row 2 tolerance ≤ Row 1, or the composite adds no constraint.

## How to: basic dimensions (required by Position / Angularity FCFs)

Set `tol.Type = 1` (swTolBASIC) to box the value, as Position and Angularity FCFs require.

```csharp
Dimension d = (Dimension)displayDim.GetDimension2(0);
DimensionTolerance tol = (DimensionTolerance)d.Tolerance;
tol.Type = 1; // swTolBASIC = 1 → boxed value
```

Use `1` for BASIC, not `6` — `6` is `swTolMAX`, so `SetTolerance2(6, …)` puts a `MAX` prefix on the dim instead of a box. (Full enum in the [API quick reference](#swtoltype_e-for-toltype--settolerance2).)

## How to: walk existing annotations (audit / round-trip)

```csharp
Annotation a = (Annotation)view.GetFirstAnnotation3();
while (a != null)
{
    int type = a.GetType();
    switch (type)
    {
        case 2:  /* DatumTag */         break;
        case 4:  /* DisplayDimension */ break;
        case 5:  /* Gtol */             break;
        case 6:  /* SectionLine */      break;
        case 13: /* CenterMark */       break;
        case 15: /* Note */             break;
    }
    a = (Annotation)a.GetNext3();
}
```

For reading FCF contents:
```csharp
object syms = g.GetFrameSymbols3(1);   // string[6]
object vals = g.GetFrameValues(1);     // string[5]: Tol1, Tol2, D1, D2, D3
```

## How to: pick a datum scheme by manufacturing process

| Part type | Primary (A) | Secondary (B) | Tertiary (C) |
|---|---|---|---|
| Turned | Axis (bore/OD) | Face (shoulder) | — |
| Milled prismatic | Largest flat face | Long edge | Short edge |
| Flange | Mounting face | Center bore axis | Bolt-pattern hole |
| Sheet metal | Flat face | Long bend / edge | Short bend / edge |
| Cast / molded | Machined face | Machined bore | Pin / slot / target |

Reference, not prescriptive — choose datums by functional interface (how the part mates and is inspected), then verify against this table.

## Gotchas & fixes

- **To make symbols draw: use UPPERCASE tokens.** `<IGTOL-POSI>` renders; `<igtol-posi>` stores the property but draws no symbol and raises no error.
- **To fill datum compartments: insert datum tags before FCFs.** Order is datum tags → basic dims → FCFs. An FCF referencing a datum letter that has no `DatumTag` yet renders with empty datum cells.
- **To avoid a null GTol/tag: select first, then null-check.** `InsertGtol()` / `InsertDatumTag2()` return `null` when nothing is selected.
- **To keep leaders anchored: call `ClearSelection2(true)` between every annotation.** Otherwise stale selection becomes the next anchor and leaders drift.
- **To redraw leaders: call `ForceRebuild3(true)` after every insert.** Leaders don't redraw without it.
- **To pass frame args correctly: use string tokens, not enum ints.** All `SetFrameSymbols2` / `SetFrameValues2` params are strings drawn from `gtol.sym`.
- **To get the intended tolerance: remember values are in display units.** `"0.25"` = 0.25 mm if the drawing is mm, 0.25 in if inches.
- **To enumerate the right entities: pass the correct first arg to `GetVisibleEntities2`.** `null` for parts, `IComponent2` for assemblies.
- **To avoid redundant leaders: attach FCFs to existing dimensions, not new leaders.** Walk `GetFirstDisplayDimension5()` across every view before falling back to edge-attach; a redundant leader on an already-dimensioned feature is a defect. (Edge-attach is the fallback only when no dim references the feature anywhere on the sheet.)
- **To declare a datum on a dimensioned feature: use `SetDatumIdentifier` on an FCF, not a datum tag on the dim.** No working API path attaches an `IDatumTag` to an `IDisplayDimension`; the integrated FCF-as-datum is the supported route.
- **To box a basic dim: use `tol.Type = 1` (BASIC), not `6`.** `6` is `swTolMAX` and produces a `MAX` prefix instead of a box.
- **To make a composite frame constrain: keep Row 2 tolerance ≤ Row 1.** A looser lower row adds no constraint.
