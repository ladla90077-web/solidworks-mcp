---
description: Surface finish symbol guide for the drafting agent — symbol type selection (swSFSymType_e), attach-to-dimension, silhouette-edge (ISO-preferred on-surface), and select-edge InsertSurfaceFinishSymbol3 workflows, text slots, lay direction, general (sheet-level) finish notes, repositioning, verification via the annotation walk, and silent-failure modes.
---

# Guide: Surface Finish Symbols

How to place and edit surface finish (roughness) symbols on a drawing through the API. One method does the insertion — `IModelDocExtension.InsertSurfaceFinishSymbol3` — and it attaches to **the last selection**, so the work is in selecting the right edge first.

Companion to `dimensioning.md` (layer/styling, AutoArrange) and `gdt-guide.md` (datum faces frequently also carry a finish symbol).

> **Golden rule: verify every selection's bool return before inserting.** A surface-finish symbol attaches to the *last selection*; if that selection silently failed, you get a floating symbol at the origin, not an error. Prefer the silhouette-edge attach ([§2c](#2c-attach-to-a-silhouette-edge--the-iso-correct-on-the-surface-placement)) or dimension attach ([§2b](#2b-attach-to-a-dimension--the-robust-default-for-turnedcylindrical-features)) over coordinate edge-picking; either way, `swNO_LEADER` always requires an explicit `SetPosition2` afterward. Note that `swNO_LEADER` ignoring LocX/Y and needing an explicit `SetPosition2` applies to **every** attachment kind — dimension ([§2b](#2b-attach-to-a-dimension--the-robust-default-for-turnedcylindrical-features)) and silhouette edge ([§2c](#2c-attach-to-a-silhouette-edge--the-iso-correct-on-the-surface-placement)) included, not just unattached symbols.

---

## 1. Choose the symbol type (`swSFSymType_e`)

| Requirement | Type | Value |
|---|---|---|
| Finish specified, any process allowed | `swSFBasic` | 0 |
| Material removal required (machined face) | `swSFMachining_Req` | 9 |
| Material removal prohibited (as-cast/forged/rolled) | `swSFDont_Machine` | 2 |
| JIS drawings only | `swSFJIS_Basic` 8, `swSFJIS_Machining_Req` 1, `swSFJIS_No_Machining` 7, `swSFJIS_Surface_Texture_1..4` 3–6 | — |

Selection logic: bearing/seal/gasket faces and anything with an FCF datum → `swSFMachining_Req` with an Ra value. Cosmetic or non-functional machined faces → `swSFBasic`. Cast surfaces left raw → `swSFDont_Machine`, no Ra. The rendered style (ISO vs ANSI) follows the document's drafting standard, not the enum.

---

## 2. Insert: select the edge, then call

> Fallback path — prefer the on-surface silhouette attach in [§2c](#2c-attach-to-a-silhouette-edge--the-iso-correct-on-the-surface-placement) (ISO-correct placement), or the dimension attach in [§2b](#2b-attach-to-a-dimension--the-robust-default-for-turnedcylindrical-features) when the feature is already dimensioned; use the coordinate edge pick only when neither applies or the surface region is too crowded (then with a leader).

```csharp
// 1. Select the target edge IN THE VIEW (same entity source as dimensioning):
//    walk view.GetVisibleEntities2(null, swViewEntityType_Edge) to find the edge,
//    then entity.Select4(false, null).  SelectByID2("", "EDGE", x, y, z, ...) also works.

// 2. Insert — attaches to the last selection
SFSymbol sfs = (SFSymbol)model.Extension.InsertSurfaceFinishSymbol3(
    (int)swSFSymType_e.swSFMachining_Req,      // SymType
    (int)swLeaderStyle_e.swNO_LEADER,          // LeaderType: NO_LEADER=0 STRAIGHT=1 BENT=2
    0, 0, 0,                                   // LocX/Y/Z — ONLY used when LeaderType != swNO_LEADER
    (int)swSFLaySym_e.swSFNone,                // lay direction (§3)
    (int)swArrowStyle_e.swCLOSED_ARROWHEAD,    // leader arrow (ignored with no leader)
    "",                                        // MachAllowance  (material removal allowance)
    "",                                        // OtherVals      (other roughness values)
    "",                                        // ProdMethod     (e.g. "GRIND")
    "",                                        // SampleLen      (sampling length)
    "3.2",                                     // MaxRoughness   ← the principal Ra value
    "",                                        // MinRoughness
    "");                                       // RoughnessSpacing
model.ClearSelection2(true);
model.GraphicsRedraw2();
```

- With `swNO_LEADER` the symbol sits directly on the selected edge; `LocX/Y/Z` are ignored.
- With `swSTRAIGHT`/`swBENT` the symbol body goes at `LocX/Y` (meters, sheet space) with a leader back to the selected edge — use this when the edge region is crowded with dims.
- Null return = insertion failed; the selection was empty or invalid. Re-select and retry once.
- ⚠ **`SelectByID2("", "EDGE", x, y, z, …)` returns `false` when the sheet point misses the thin contour line** (common — the hit tolerance is tiny). **Always check the bool return:**

  ```csharp
  bool ok = ext.SelectByID2("", "EDGE", x, y, z, false, 0, null, 0);
  if (!ok) { /* fall back to §2c silhouette or §2b dimension attach, or use a leader */ }
  ```

  Inserting after a failed select produces an **unattached** symbol at the sheet origin — the "stray in the corner."

## 2b. Attach to a dimension — the robust default for turned/cylindrical features

On shafts and bores the feature you want to flag is already dimensioned (Ø40 h7, Ø50 js6, …). Attach the finish symbol to that **dimension** rather than hunting for the contour edge — selecting an annotation never misses, a sheet-coordinate edge pick often does (no hit-tolerance lottery). `InsertSurfaceFinishSymbol3` attaches to the last selection, dimension or edge alike.

```csharp
// 1. Find the dimension and select its ANNOTATION (not an edge):
//    walk GetFirstDisplayDimension5 / GetNext5, match by FullName
//    (form "<dimName>@<sketch>@<doc>" — match the dimName of the target feature).
DisplayDimension dd = (DisplayDimension)view.GetFirstDisplayDimension5();
while (dd != null && ((Dimension)dd.GetDimension()).FullName != targetFullName)
    dd = (DisplayDimension)dd.GetNext5();
Annotation an = (Annotation)dd.GetAnnotation();
an.Select3(false, null);                         // selects the dim itself — never misses

// 2. Insert with that selection live — the SF symbol binds to the dimension:
SFSymbol sf = (SFSymbol)model.Extension.InsertSurfaceFinishSymbol3(
    (int)swSFSymType_e.swSFMachining_Req, (int)swLeaderStyle_e.swNO_LEADER,
    0, 0, 0, (int)swSFLaySym_e.swSFNone, (int)swArrowStyle_e.swNO_ARROWHEAD,
    "", "", "", "", "1.6", "", "");

// 3. MANDATORY reposition — NO_LEADER ignores LocX/Y, so the symbol renders at the
//    origin until you move it. Anchor off the dimension's own text position:
double[] dp = (double[])an.GetPosition();        // dim text anchor, sheet meters
((Annotation)sf.GetAnnotation()).SetPosition2(dp[0], dp[1] + 0.012, 0);   // 12 mm above the dim text
```

Never trust the insert to place it — with `swNO_LEADER` the explicit `SetPosition2` off the host dim's `GetPosition()` is part of the recipe, not an optional cleanup.

## 2c. Attach to a silhouette edge — the ISO-correct "on the surface" placement

On a turned part the cylindrical face you want to flag shows in the side
view as a **silhouette edge** — the straight outline of the cylinder. These are NOT
returned by `GetVisibleEntities2(..., swViewEntityType_Edge)`; that call yields only
the **real** model edges, which on a shaft are just the circular diameter-transition
edges. The surface outlines come from a separate entity type:

```csharp
object[] sils = (object[])view.GetVisibleEntities2(null,
    (int)swViewEntityType_e.swViewEntityType_SilhouetteEdge);  // = 4
```

### Gotchas (all learned the hard way)

- **The returned objects are `ISilhouetteEdge`, not `IEntity`/`IEdge`.** Casting to
  `Entity` throws `E_NOINTERFACE`. Cast to `SilhouetteEdge`.
- **The silhouette `Curve` is an *unbounded* line.** `GetEndParams` returns a huge
  param range, so `Evaluate2(start,0)` gives points at ±10000 m — useless for extents.
  - For the **real y-extent and radius**, use `((Face2)se.GetFace()).GetBox()`
    → `{xmin,ymin,zmin,xmax,ymax,zmax}`. The face box y-range tells you *which*
    cylinder (seat vs. thread vs. chamfer), and max|z| gives the radius.
  - The point's **z-coordinate** (`Evaluate2(startParam,0)[2]`) is the signed radius
    offset: `+r` = top outline, `−r` = bottom outline. Use it to pick the top edge.
- **`GetStartPoint()`/`GetEndPoint()` return `MathPoint` and can throw
  `RPC_E_SERVERFAULT`** in some contexts — prefer `GetFace().GetBox()` for geometry.

### Identify the target, then attach

Walk the silhouettes, match each face box's y-range and radius against the target
cylinder, and pick the `+r` entry (top outline) for that face. Then:

```csharp
SelectionMgr sm = (SelectionMgr)model.SelectionManager;
SilhouetteEdge se = (SilhouetteEdge)sils[idx];
SelectData sd = (SelectData)sm.CreateSelectData();
bool ok = se.Select2(false, sd);                 // selects the outline in the view

SFSymbol sf = (SFSymbol)model.Extension.InsertSurfaceFinishSymbol3(
    (int)swSFSymType_e.swSFMachining_Req, (int)swLeaderStyle_e.swNO_LEADER,
    0,0,0, (int)swSFLaySym_e.swSFNone, (int)swArrowStyle_e.swNO_ARROWHEAD,
    "","","","","0.8","","");

// NO_LEADER still ignores LocX/Y — position it onto the outline yourself.
// View transform (front view of a Y-axis part):
//   sheetX = viewOrigin.X + scale*(modelY - modelMidY)
//   surface sheetY = viewOrigin.Y(axis) + scale*r
double[] vo = (double[])view.Position;
double sx = vo[0] + scale*(midY - modelMidY);
double sy = vo[1] + scale*r + 0.001;             // 1 mm clear of the line
((Annotation)sf.GetAnnotation()).SetPosition2(sx, sy, 0);
model.ClearSelection2(true);
```

This is the **preferred ISO placement** — the symbol sits on the surface outline
itself, no leader, cleaner than leadering to a transition circle (§2). Use the §2
leader-to-circular-edge approach only when the surface region is too crowded.

> ⚠ **`IsAttached()` lies for silhouette- and dimension-attached symbols** — it
> returns `False` even when the symbol is correctly bound and renders on the surface.
> `IsAttached()` returns `True` *only* for a leader/no-leader attachment to a **real**
> `IEdge`. Don't gate success on it for §2b/§2c — verify by screenshot.

## 3. Lay direction (`swSFLaySym_e`) — only when the process demands it

None=0, Circular=1, Cross=2 (X), MultiDir=3 (M), Parallel=4 (=), Perp=5 (⊥), Radial=6 (R), Particulate=7 (P). Default `swSFNone`; specify only for sealing/bearing/sliding surfaces where lay matters (e.g. Perp on a dynamic seal bore).

---

## 4. Edit an existing symbol

Text slots use `swSurfaceFinishSymbolText_e`: MaterialRemovalAllowance=1, ProductionMethod=2, SamplingLength=3, OtherRoughnessValue=4, **MaximumRoughness=5**, MinimumRoughness=6, RoughnessSpacing=7, RoughnessValue1..3=8–10 (ISO-2002-style symbols).

```csharp
sfs.SetText((int)swSurfaceFinishSymbolText_e.swSFSymbolMaximumRoughness, "1.6");
sfs.SetSymbol((int)swSFSymType_e.swSFMachining_Req);   // use SetSymbol — SetSymbolType is obsolete and may no-op
sfs.SetDirectionOfLay((int)swSFLaySym_e.swSFPerp);

// Reposition / style via the underlying annotation (meters, sheet space)
Annotation ann = (Annotation)sfs.GetAnnotation();
ann.SetPosition2(x, y, 0);
ann.Layer = "DIMS";              // match dim styling layer (see dimensioning.md)
```

`sfs.GetText(which)` / `GetTextCount` read back. `sfs.IsAttached` only reports real-`IEdge` attachments — it reads `False` for dimension- and silhouette-attached symbols even when correctly bound (§2c).

---

## 5. General finish note (sheet-level "all surfaces" symbol)

Convention: one symbol next to the title block — "all surfaces Ra X unless noted" — plus per-face symbols only for tighter faces.

```csharp
model.ClearSelection2(true);                        // NO selection → unattached symbol
SFSymbol gen = (SFSymbol)model.Extension.InsertSurfaceFinishSymbol3(
    (int)swSFSymType_e.swSFBasic, (int)swLeaderStyle_e.swNO_LEADER,
    0, 0, 0, (int)swSFLaySym_e.swSFNone, (int)swArrowStyle_e.swNO_ARROWHEAD,
    "", "", "", "", "6.3", "", "");
// Placement of an unattached symbol is unreliable — ALWAYS position explicitly:
((Annotation)gen.GetAnnotation()).SetPosition2(titleBlockX - 0.015, titleBlockY + 0.010, 0);
```

Every per-face symbol must then be **tighter** (lower Ra) than the general note, or it's redundant — remove it.

---

## 6. Verify, don't trust

Walk the view's annotations; surface finish symbols are annotation type `swSFSymbol` = 7 (`swAnnotationType_e`):

```csharp
Annotation a = (Annotation)view.GetFirstAnnotation3();
while (a != null)
{
    if (a.GetType() == (int)swAnnotationType_e.swSFSymbol)
    {
        SFSymbol s = (SFSymbol)a.GetSpecificAnnotation();
        // s.GetText(5) == expected Ra; a.GetPosition() inside sheet bounds
    }
    a = (Annotation)a.GetNext3();
}
```

Check: expected count, Ra text in slot 5, position on-sheet. `IsAttached` is only meaningful for real-edge attachments (§2) — it reads `False` for dimension- and silhouette-attached symbols even when correctly bound (§2c), so don't use it as a success gate for those.

---

## 7. Silent-failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Returns null | Nothing (or wrong entity) selected | Select edge via `GetVisibleEntities2` + `Select4`, retry once |
| Symbol at sheet origin / odd corner | `swNO_LEADER` with no selection — LocX/Y ignored | `SetPosition2` explicitly after insert (§5) |
| Symbol at sheet origin; `SelectByID2` returned false | Edge pick missed the contour line | Check the `SelectByID2` bool; fall back to §2c silhouette or §2b dimension attach |
| Several Ra-text strays accumulate at origin | Each failed-select insert leaves one unattached symbol | Audit via the §6 walk: delete any `swSFSymbol` sitting at/near the origin — gate on **position**, not `IsAttached` (§2b/§2c symbols also read `false`); keep the intentional general note, §5 |
| Symbol ignores LocX/Y entirely | LocX/Y only apply when `LeaderType != swNO_LEADER` | Use STRAIGHT/BENT leader, or reposition via annotation |
| Ra value missing | Value passed to wrong text param (e.g. OtherVals) | Principal Ra = MaxRoughness param / `SetText(5, …)` |
| Symbol placed at 10× scale off-sheet | Coords passed in mm | Meters, sheet space — `0.010` = 10 mm |
| Symbol overlaps dimensions | Inserted after dims with no re-arrange | Run AutoArrange after inserting (mandatory, see `dimensioning.md`) |
| JIS glyphs on an ISO/ANSI drawing | Used types 1/3–8 | ISO/ANSI use 0 / 9 / 2 only |
| Surface outline not in `GetVisibleEntities2(Edge)` | Outlines are silhouette edges, not real edges | Use `swViewEntityType_SilhouetteEdge` (=4); cast results to `SilhouetteEdge` (§2c) |
| `IsAttached()==False` but symbol renders on the dim/surface | `IsAttached` only tracks real-edge attachment | Expected for §2b/§2c — verify by screenshot, not this flag |
