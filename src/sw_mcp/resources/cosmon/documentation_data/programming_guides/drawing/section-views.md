---
description: Create, link, position, and clean up section views in a SolidWorks drawing. Covers full / half / offset / aligned / slice / removed sections, all three partial flavours (depth-limited derived, broken-out short-line derived, in-place broken-out with free-form jagged boundary), transverse cuts through off-axis features, section-line placement, overlap avoidance, parent-view linkage, dimensioning inside a section, and teardown.
---

# Section Views

> Draw a cutting line in the parent view's sketch, call `CreateSectionViewAt5`, tune the resulting `IDrSection`, keep it linked to its parent, place it without overlap, and delete view + line cleanly on rollback. Use whenever a drawing needs to reveal internal geometry a plain projection hides.

Companion to `quick_multi_view_drawing.md` (sets up the views this guide cuts sections into). Dimensioning *inside* a section view is covered below under [How to: dimension a section view](#how-to-dimension-a-section-view). For drafting theory behind section types, see Open Oregon *Blueprint Reading*, [Unit 7 — Sectional Views](https://openoregon.pressbooks.pub/blueprint/chapter/unit-7-sectional-views/) — this guide is the API translation of those conventions.

## Recipe (happy path)

1. **Pick the parent view** that best reveals the internal structure (skip the sheet background — `GetFirstView()` returns it, so `GetNextView()` once). → [How to: create a full section](#how-to-create-a-full-section)
2. **Route the cutting line through the internal features**, in the parent view's sketch via `ModelToSketchTransform`, extending ≥10% past the silhouette on both ends. → [How to: create a full section](#how-to-create-a-full-section)
3. **Select the line, then `IDrawingDoc::CreateSectionViewAt5`** — it consumes the live selection. Null-check the result. → [How to: create a full section](#how-to-create-a-full-section)
4. **Configure `View::GetSection()` → `IDrSection`** with defensive resets, then `EditRebuild3()`. → [How to: configure the section (IDrSection)](#how-to-configure-the-section-idrsection)
5. **Verify the cut revealed interior geometry** with the edge-count heuristic before shipping. → [How to: verify and diagnose a flat section](#how-to-verify-and-diagnose-a-flat-section)
6. **Place without overlap** using the create-rough → measure → reposition pattern. → [How to: place a section without overlap](#how-to-place-a-section-without-overlap)
7. **On rollback, delete both the derived view and the cutting line** in the parent's sketch. → [How to: delete a section view](#how-to-delete-a-section-view)

Variants build on this happy path: [half/offset/aligned](#how-to-create-a-half-offset-or-aligned-section), [partial flavours A/B/C](#how-to-create-a-partial-section-flavours-abc), [transverse](#how-to-create-a-transverse-section-through-off-axis-features), [slice](#how-to-create-a-slice-section-cut-plane-only), [removed/cropped](#how-to-create-a-removed-or-cropped-corner-section).

## API quick reference

### `IDrawingDoc::CreateSectionViewAt5`

```csharp
View sectionView = (View)swDraw.CreateSectionViewAt5(
    sectionX,             // X: sheet coords (meters), CENTER of new section view
    sectionY,             // Y: sheet coords (meters)
    0,                    // Z: always 0
    "A",                  // SectionLabel: single letter ("A", "B", ...); "A" → "SECTION A-A"
    0,                    // Options: bitmask — see swCreateSectionViewAtOptions_e
    null,                 // ExcludedComponents: assembly only; null for parts
    0                     // SectionDepth: 0 = cut fully through; >0 = partial, meters
);
```

Returns `IView`. Runs silently — no user prompt. **Consumes the currently-selected section line(s) in the parent view's sketch**, so `line.Select4(false, null)` must be the last call before it. Returns `null` if the selection is missing, the line is degenerate, or the position is off-sheet.

| Param | Units / type | Notes |
|---|---|---|
| `X, Y, Z` | meters, sheet space | Center of the new section view. `Z` is always 0. |
| `SectionLabel` | string | Single letter on both cutting line and derived view. Use sequential letters across a drawing. Duplicate labels silently clobber previous sections — use `IDrSection::SetLabel2` to get a duplicate warning. |
| `Options` | `int` bitmask | Combination of `swCreateSectionViewAtOptions_e` members (table below). |
| `ExcludedComponents` | `object[]` or `null` | Array of `IComponent2` for assembly drawings. `null` for parts. |
| `SectionDepth` | meters | `0` = full depth. `>0` = partial section cutting only this far past the line. |

### `swCreateSectionViewAtOptions_e` bitmask

| Value | Member | Effect |
|---|---|---|
| `0x01` (1)  | `swCreateSectionView_NotAligned`        | Don't snap to parent alignment. Required for a freely-movable section (a **removed section**). |
| `0x02` (2)  | `swCreateSectionView_OffsetSection`     | Aligned / offset / half section — two or more connected sketch segments. |
| `0x04` (4)  | `swCreateSectionView_ChangeDirection`   | Flip the cut-direction arrows and the resulting view. |
| `0x08` (8)  | `swCreateSectionView_ScaleWithModel`    | Scale the section view (and hatch) with model changes. |
| `0x10` (16) | `swCreateSectionView_Partial`           | **Broken-out / partial** section — doesn't cut through the whole body. |
| `0x20` (32) | `swCreateSectionView_DisplaySurfaceCut` | **Slice section** — show only the cut surfaces, not the geometry behind them. |
| `0x40` (64) | `swCreateSectionView_ExcludeFasteners`  | Assembly only — don't section fasteners. |
| `0x80` (128)| `swCreateSectionView_CutSurfaceBodies`  | For surface bodies, show only the intersection curve where the plane cuts. |

Combine with `|`:
```csharp
int opts = (int)(swCreateSectionViewAtOptions_e.swCreateSectionView_Partial
               | swCreateSectionViewAtOptions_e.swCreateSectionView_NotAligned); // 17
```

### Key `IDrSection` members

`View::GetSection()` returns the `IDrSection` that owns the cutting line. Most per-section settings live here, not on `IView`.

| Member | Type | Use |
|---|---|---|
| `SetAutoHatch(bool)` / `GetAutoHatch()` | method | Toggle cross-hatch on the cut faces. Turn on for readability. |
| `SetLabel2(string, bool warnDup)` | method | Change the section letter after creation; `warnDup = true` raises a duplicate-name warning. |
| `SectionDepth` | `double` (m) | Read/override the partial-section depth set in `CreateSectionViewAt5`. |
| `SetPartialSection(bool)` / `GetPartialSection()` | method | Toggle partial-section mode post-hoc. |
| `SetReversedCutDirection(bool)` / `GetReversedCutDirection()` | method | Flip the look-direction (equivalent to `ChangeDirection`). |
| `SetDisplayOnlySurfaceCut(bool)` / `GetDisplayOnlySurfaceCut()` | method | `false` = show ALL geometry behind the cut; `true` = only the cut silhouette (slice section). |
| `DisplaySurfaceBodies` | `bool` | Show surface bodies inside the section. |
| `CutSurfaceBodies` | `bool` | Hide cut surface bodies (show only cut geometry on solids). |
| `ExcludeSliceSectionBodies` | `bool` | Slice section: suppress bodies the plane doesn't touch (assembly-only). |
| `ExcludeFasteners` | `bool` | Assembly only: skip fasteners in the cut. |
| `ScaleHatchPattern`, `RandomizeScale` | `bool` | Hatch display controls. |
| `CuttingLineShoulders` | `bool` | Hide/show the shoulder ticks at the ends of the cutting line. |
| `Layer` | `string` | Move the section line onto a named drawing layer. |
| `SetExcludedComponents(object[])` / `EnumExcludedComponents2()` | method | Assembly-only exclusion list. |
| `GetLineInfo()` / `GetArrowInfo()` / `GetTextInfo()` | methods | Read cutting-line geometry (vertices), arrow positions, label position — useful for repositioning. |
| `GetView()` | method | Returns the **parent** view (where the line lives). Pair with `GetSectionView()` for the resulting section view. |

### Alignment constants (`swAlignView_e`) — argument to `IView::AlignWithView`

| Value | Constant | Effect |
|---|---|---|
| `0` | `swNoViewAlignment` | **UNLINK** — removes alignment. Use for removed sections. |
| `1` | `swDefaultViewAlignment` | Reset to SolidWorks' default for this view type. |
| `2` | `swAlignViewHorizontalCenter` | Align on horizontal centerline (typical for a horizontal cut). |
| `3` | `swAlignViewVerticalCenter`   | Align on vertical centerline (typical for a vertical cut). |

### `IBrokenOutSectionFeatureData` (in-place broken-out — Flavour C)

`IView::GetBreakOutSections()` returns the array of `BrokenOutSection`-type `IFeature`s on a view; `IView::GetBreakOutSectionCount()` gives the count. Each feature's `GetDefinition()` returns an `IBrokenOutSectionFeatureData`:

| Member | Type | Use |
|---|---|---|
| `Depth` | `double` (m) | Cut depth into the view. |
| `DepthReference` | `Entity` | Cut down to a referenced edge instead of a numeric depth; `null` when using `Depth`. |
| `EditSketch` | `bool` | Expose the boundary segments for reading/editing. |
| `SketchSegment` | `object[]` | The closed boundary loop. |
| `GetSketchSegmentCount()` | method | Count of boundary segments. |
| `AccessSelections(model, mark)` / `ReleaseSelectionAccess()` | method | Lock/unlock the definition for editing. |

Pair with `IFeature::ModifyDefinition(def, model, mark)` to commit edits. The in-place command itself is reached via `swDrawModel.Extension.RunCommand((int)swCommands_e.swCommands_BrokenOutSection, "")` (see [Flavour C](#how-to-create-a-partial-section-flavours-abc)).

### Section types → which call / option bit creates them

| Unit 7 type | What it shows | API recipe |
|---|---|---|
| **Full section** | Cut plane passes straight through the whole object | `CreateSectionViewAt5` with a single straight line, `Options = 0` → [Full section](#how-to-create-a-full-section) |
| **Half section** | Cut plane removes one quarter; symmetric parts only | L-shaped line ending at the axis of symmetry + `OffsetSection` (2) → [Half/offset/aligned](#how-to-create-a-half-offset-or-aligned-section) |
| **Offset section** | Cutting plane jogs through features not in a single plane | Two or more connected sketch segments + `swCreateSectionView_OffsetSection` (2) → [Half/offset/aligned](#how-to-create-a-half-offset-or-aligned-section) |
| **Aligned section** | Rotates a feature (spoke, arm) into the cut plane | Offset section; don't pass `NotAligned` (1) → [Half/offset/aligned](#how-to-create-a-half-offset-or-aligned-section) |
| **Partial section view** (derived, depth-limited) | New derived view, cut to a limited depth | `swCreateSectionView_Partial` (16) + `SectionDepth > 0` — Flavour A → [Partial](#how-to-create-a-partial-section-flavours-abc) |
| **Broken-out section view** (derived, short cut line) | New derived view, short cut line over the feature only | `Partial (16) \| NotAligned (1)` + short line + `SectionDepth > 0` — Flavour B → [Partial](#how-to-create-a-partial-section-flavours-abc) |
| **In-place broken-out section** (modifies parent, no new view) | Parent view modified with a free-form jagged boundary cut into it | `IBrokenOutSectionFeatureData` on the parent + closed spline boundary — Flavour C → [Partial](#how-to-create-a-partial-section-flavours-abc) |
| **Transverse section** | Cut perpendicular to the long axis to reveal radial features | Vertical line at the feature's projected X + `NotAligned` (1) → [Transverse](#how-to-create-a-transverse-section-through-off-axis-features) |
| **Slice section** | Show only the cut surface | `swCreateSectionView_DisplaySurfaceCut` (32) → [Slice](#how-to-create-a-slice-section-cut-plane-only) |
| **Removed section** | Same cut, drawn off to the side at a different scale | Standard section, then `RemoveAlignment()` / unlink + set scale → [Removed/cropped](#how-to-create-a-removed-or-cropped-corner-section) |
| **Revolved section** | Cross-section drawn in-place on the parent view | Out of scope for `CreateSectionViewAt5` — draw sketch geometry on the parent view directly |

### Coordinate reference

| Context | Coordinate system | Units |
|---|---|---|
| `view.GetOutline()` | Sheet | Meters |
| `view.Position` | Sheet | Meters |
| `CreateSectionViewAt5(X, Y, Z, …)` | Sheet | Meters |
| Section-line vertices (inputs to `CreateLine`) | View sketch (apply `ModelToSketchTransform`) | Meters |
| `IDrSection.SectionDepth` | Model space, perpendicular to cut | Meters |
| `IDrSection.GetLineInfo()` | View sketch | Meters |

Transform chain (both transforms mandatory — see [Gotchas & fixes](#gotchas--fixes)):

```
Model space (meters, feature in 3D part coordinates)
   ↓  ModelToViewTransform        (parent view's projection of model onto its sheet area)
Sheet space (meters, where the feature shows up on the drawing)
   ↓  ModelToSketchTransform      (parent view's sketch — the coord system CreateLine uses)
View-sketch space (meters, hand to skMgr.CreateLine)
```

`ModelToViewTransform` tells you WHERE to cut (the sheet position where the feature projects). `ModelToSketchTransform` converts that into the coordinate system `CreateLine` expects.

## How to: create a full section

### Step 1 — Route and draw the cutting line through the internal features

Place the line so it actually crosses interior geometry — the #1 reason a fresh section "looks just like a side view and shows no internal profile" is that the cutting line doesn't cross any internal feature in 3D. A horizontal line through the parent's centroid only reveals geometry that happens to lie on that line; offset holes, off-center bores, or one-sided pockets get missed and the section legitimately looks like a plain projection. Fix this at line-placement time:

1. **Locate internal features in model coords** — from the Phase 1 extractor you already have `circularFeatures[]` (hole/bore centers), `pockets[]`, `bossCenters[]`, etc. in model space.
2. **Project each to parent-view sheet coords** — `view.ModelToViewTransform` takes model → view-sketch coords; compose with the view's position on the sheet. (Or use `ISketchPoint.Type == swSketchPointType_CenterMark` on the view's visible entities — already in sketch space.)
3. **Route through the subset that reveals the most** — for a single full section, cross the *Y of the feature centers*, not the view's geometric Y-center. For features at different Y's, switch to an offset section (`swCreateSectionView_OffsetSection = 2`) threading through each feature.
4. **Extend ≥10% past the body edges on BOTH ends** so the total line length is ≥120% of the body width along the cut axis. Endpoints inside or exactly on the body edge produce a degenerate cut: `CreateSectionViewAt5` may return a valid `View`, but the section is silently truncated, downgraded to partial, or rendered as a plain projection — no warning, no `null`, no exception. Overshoot by 20% when unsure; there is no penalty for an over-long section line, only for one too short.

```csharp
// CORRECT — endpoints 10% past the outline on BOTH sides, routed through hole-center Y
double[] holeYsInSheet = GetHoleYCoordsInParentSheetSpace(parentView);  // Phase 1 + transform
double routeY = holeYsInSheet.Average();                                  // or median for robustness
double[] startPt = { outline[0] - halfW * 0.10, routeY, 0 };             // 10% past left edge
double[] endPt   = { outline[2] + halfW * 0.10, routeY, 0 };             // 10% past right edge

// WRONG — line stops at body edges (degenerate) or inside the body (truncated):
// { outline[0], routeY, 0 } … { outline[2], routeY, 0 }
// { centerX - halfW * 0.5, routeY, 0 } … { centerX + halfW * 0.5, routeY, 0 }
```

For tall narrow parts or wide flat ones, scale the overrun to the cut-axis dimension: vertical cut → overrun in Y by `halfH * 0.10+`; horizontal cut → overrun in X by `halfW * 0.10+`. If your Phase 1 extractor doesn't emit per-feature Y-in-view coordinates, add one before writing section-view code — guessing at line placement produces empty sections.

The section line lives in the **view sketch** of the parent view, not on the sheet. Transform sheet coords through `ModelToSketchTransform` before handing them to `CreateLine`:

```csharp
// Pick the parent view — typically the one that best reveals internal structure.
// GetFirstView() returns the sheet background; call GetNextView() once for a real view.
View parentView = frontView;

double[] outline = (double[])parentView.GetOutline();   // [xMin, yMin, xMax, yMax] sheet meters
double centerX = (outline[0] + outline[2]) / 2;
double centerY = (outline[1] + outline[3]) / 2;
double halfW   = (outline[2] - outline[0]) / 2;
double halfH   = (outline[3] - outline[1]) / 2;

// SHEET → VIEW SKETCH transform (COM casts are mandatory)
Sketch viewSketch          = (Sketch)parentView.GetSketch();
MathTransform sketchXform  = viewSketch.ModelToSketchTransform;
MathUtility mathUtils      = (MathUtility)swApp.GetMathUtility();

MathPoint mStart = (MathPoint)((MathPoint)mathUtils.CreatePoint(startPt)).MultiplyTransform(sketchXform);
MathPoint mEnd   = (MathPoint)((MathPoint)mathUtils.CreatePoint(endPt  )).MultiplyTransform(sketchXform);
double[] tS = (double[])mStart.ArrayData;
double[] tE = (double[])mEnd.ArrayData;

// Activate the PARENT view before drawing — CreateLine writes to the active view's sketch.
swDraw.ActivateView(parentView.GetName2());
swDrawModel.ClearSelection2(true);
SketchManager skMgr = swDrawModel.SketchManager;
skMgr.AddToDB = true;
SketchSegment sectionLine = (SketchSegment)skMgr.CreateLine(tS[0], tS[1], tS[2], tE[0], tE[1], tE[2]);
skMgr.AddToDB = false;

// Must be selected when CreateSectionViewAt5 fires — it consumes the selection.
sectionLine.Select4(false, null);
```

**Orientation determines placement.** A horizontal cut line (↔) drops the section below the parent (`p1 = { centerX - halfW*0.8, centerY, 0 }`, `p2 = { centerX + halfW*0.8, centerY, 0 }`). A vertical cut line (↕) places the section left/right (`p1 = { centerX, centerY - halfH*0.8, 0 }`, `p2 = { centerX, centerY + halfH*0.8, 0 }`). The `0.8` coverage spans most of the view; raise toward 1.0+ to overrun the edges per the rule above.

#### Routing concave / multi-body parts through the body, not empty space

`view.GetOutline()` is a bounding rectangle, not a silhouette. For L-brackets, U-channels, T-shapes, rings, and multi-body parts with gaps, a line at outline-`centerY` can fall entirely in empty space — `CreateSectionViewAt5` returns `null` (sometimes preceded by a modal "section line does not intersect model" dialog that hangs the macro). Route through the **median Y of body edges** instead: by definition half the edges are above and half below, so the median always sits inside material.

```csharp
// Walk visible edges, project to view-sketch space, take median along the route axis.
MathTransform m2v = parentView.ModelToViewTransform;
var ys = new List<double>();
foreach (int t in new[] { (int)swViewEntityType_e.swViewEntityType_Edge,
                          (int)swViewEntityType_e.swViewEntityType_SilhouetteEdge })
{
    object[] ents = (object[])parentView.GetVisibleEntities2(null, t) ?? new object[0];
    foreach (Edge e in ents.OfType<Edge>())
    {
        Vertex sv = e.GetStartVertex() as Vertex, ev = e.GetEndVertex() as Vertex;
        if (sv == null || ev == null) continue;          // skip closed curves
        double[] sp = (double[])sv.GetPoint(), ep = (double[])ev.GetPoint();
        double[] mid = { (sp[0]+ep[0])/2, (sp[1]+ep[1])/2, (sp[2]+ep[2])/2 };
        ys.Add(((double[])((MathPoint)((MathPoint)mathUtils.CreatePoint(mid))
                              .MultiplyTransform(m2v)).ArrayData)[1]);
    }
}
ys.Sort();
double routeY = ys[ys.Count / 2];      // in view-sketch space — use DIRECTLY in CreateLine, no further transform
```

Then build line endpoints in sketch space directly (skip the sheet→sketch transform): `skMgr.CreateLine(skLeftX, routeY, 0, skRightX, routeY, 0)`. For vertical cuts, take the median along X and span Y.

### Step 2 — Create the section view and null-check it

```csharp
View sectionView = (View)swDraw.CreateSectionViewAt5(
    sectionX, sectionY, 0, "A", 0, null, 0);   // see API quick reference for params
if (sectionView == null)
{
    // Section line didn't cut the body — delete the orphan line, then fail loud or retry.
    swDraw.ActivateView(parentView.GetName2());
    sectionLine.Select4(false, null);
    swDrawModel.EditDelete();        // remove orphan line — otherwise it stays on the sheet
    throw new InvalidOperationException(
        "Section line didn't cut the body. Re-route through the median of GetVisibleEntities2 edges, " +
        "or switch to an offset section (Options |= 2) with jog segments.");
}
```

Always null-check: every downstream `sectionView.GetSection()` / `sectionView.GetOutline()` throws `NullReferenceException` on a swallowed `null`. Pick `sectionX`/`sectionY` per [How to: place a section without overlap](#how-to-place-a-section-without-overlap) — the naive `centerX, outline[1] - 0.08` only works when the section view is smaller than the gap.

### Step 3 — Configure the section

Continue to [How to: configure the section (IDrSection)](#how-to-configure-the-section-idrsection), then verify with [How to: verify and diagnose a flat section](#how-to-verify-and-diagnose-a-flat-section).

## How to: configure the section (IDrSection)

Apply the defensive-reset block so behavior is deterministic across runs, then rebuild. The SolidWorks "Create_Section_View_and_Get_Some_Data" example does all of these even when `Options = 0` was passed — template state, user preferences, or a prior section in the same session can leave sticky bits, so passing `Options = 0` does not guarantee `DisplayOnlySurfaceCut` / `PartialSection` / `ReversedCutDirection` are off on the result.

```csharp
DrSection sec = (DrSection)sectionView.GetSection();
sec.SetAutoHatch(true);                  // auto cross-hatch the cut faces
sec.ScaleHatchPattern = true;            // scale hatch with section view

// ─── Defensive resets — force full section, interior revealed ───
sec.SetDisplayOnlySurfaceCut(false);     // false = show ALL geometry behind cut; true = only cut silhouette
sec.SetPartialSection(false);            // full-depth cut, not stopped at SectionDepth
sec.SetReversedCutDirection(false);      // default arrow direction (flip manually only if needed)
sec.DisplaySurfaceBodies = true;         // surface bodies visible (no effect on solid-only parts)
sec.CutSurfaceBodies = false;            // show, don't hide, cut surface bodies
sec.ExcludeSliceSectionBodies = false;   // include bodies the plane doesn't directly touch

// sec.CuttingLineShoulders = false;     // hide the right-angle ticks at the line ends
// sec.ExcludeFasteners   = true;        // assembly only

swDrawModel.EditRebuild3();              // required after any IDrSection change — flags don't repaint until rebuild
```

Skip a reset only when you deliberately want that mode — e.g. for a slice section, set `SetDisplayOnlySurfaceCut(true)` after the reset block (see [Slice section](#how-to-create-a-slice-section-cut-plane-only)).

## How to: verify and diagnose a flat section

### Step 1 — Verify the cut revealed more geometry than the parent

Don't trust the bitmask; check the result. A valid section through holes or pockets produces **strictly more** visible edges than the parent — the interior profile adds edges. Equal-or-fewer is a red flag.

```csharp
int CountEdges(View v) {
    object[] edges = (object[])v.GetVisibleEntities2(
        null, (int)swViewEntityType_e.swViewEntityType_Edge);
    return edges?.Length ?? 0;
}

int parentEdges  = CountEdges(parentView);
int sectionEdges = CountEdges(sectionView);
if (sectionEdges <= parentEdges) {
    // Section failed to expose internal profile — run the diagnostic table below.
    // Don't ship — a section with ≤ parent-view edge count is almost always wrong.
}
```

### Step 2 — Split the failure mode

- **`CreateSectionViewAt5` returned `null`** (maybe with a modal "section line does not intersect model" dialog) → the line missed the body. This is a *hard* failure caught at creation: re-route through the median of visible body-edge midpoints and retry once (see [How to: create a full section](#how-to-create-a-full-section) → "Routing concave / multi-body parts").
- **A valid `View` returned but it visually looks like a plain projection** — no holes, bores, or pockets in the cut face → *soft* failure. Work the table below in order; most cases are #1 or #2.

| # | Cause | Check | Fix |
|---|---|---|---|
| 1 | **Cutting line doesn't pass through any internal feature in 3D** | Overlay the line on the parent's hidden-line output; does it cross any hidden circle/oval? | Re-route through feature centers ([Step 1](#how-to-create-a-full-section)). For features at different Y/X, use an offset section with jog segments. |
| 2 | **`swCreateSectionView_DisplaySurfaceCut` (32) is set** — only the cut silhouette shows | `sec.GetDisplayOnlySurfaceCut()` returns `true` | `sec.SetDisplayOnlySurfaceCut(false); swDrawModel.EditRebuild3();` Add to the defensive-reset block so it doesn't recur. |
| 3 | **Partial section with insufficient `SectionDepth`** — cut stops before the features | `sec.GetPartialSection()` returns `true` and `sec.SectionDepth < distance_to_feature` | `sec.SetPartialSection(false);` (full cut), or increase `SectionDepth` past the feature. |
| 4 | **Line drawn in wrong coordinate space** (sheet coords without `ModelToSketchTransform`) | Read the sketch line's endpoints — far outside the body means the transform was skipped | Redraw with the transform applied (see [Gotchas & fixes](#gotchas--fixes)). |
| 5 | **Line drawn in wrong view's sketch** (forgot `ActivateView` on the parent) | `IDrSection::GetView()` returns a view other than the intended parent | Delete and recreate with `swDraw.ActivateView(parentView.GetName2())` immediately before `CreateLine`. |
| 6 | **Cut direction flipped** — showing the "outside" half rather than the half with features | `sec.GetReversedCutDirection()` returns `true` (or features sit on the arrow-source side) | `sec.SetReversedCutDirection(false);` for default, or `true` to flip. Either half should reveal the cut interior — but if features are all on one side, only one direction exposes them. |
| 7 | **Surface body / shell with `CutSurfaceBodies = true`** — hides cut surface bodies | `sec.CutSurfaceBodies` returns `true` on a surface-heavy part | `sec.CutSurfaceBodies = false;` |

## How to: create a half, offset, or aligned section

These share one API path: connected sketch segments + `swCreateSectionView_OffsetSection` (2). Draw the multi-segment line (Step 1 below), select all segments, then run [Steps 2–3 of the full section](#how-to-create-a-full-section) passing `Options = 2`.

**Half section** (symmetric parts) — draw an **L-shape** (two segments at 90°): one from the axis of symmetry outward, a second perpendicular segment defining the removed quarter. Pass `OffsetSection` (2) so SolidWorks honors the corner.

```csharp
// Axis at centerX (vertical symmetry). Cut the right half.
double[] a = { centerX,                centerY + halfH * 0.8, 0 };  // top of axis
double[] b = { centerX,                centerY,               0 };  // corner at center
double[] c = { centerX + halfW * 0.8,  centerY,               0 };  // exit right
// Draw two connected segments a→b and b→c, select both, pass Options = 2.
```

**Offset section** — two or more connected jog segments threading through features not in a single plane. Same API; `Options |= swCreateSectionView_OffsetSection` (2).

**Aligned section** — rotates a feature (spoke, arm) into the cut plane. Build it as an offset section and leave `NotAligned` (1) off.

## How to: create a partial section (Flavours A/B/C)

A partial section cuts only the portion needed to reveal an internal feature, leaving the rest intact. Pick by question: **do you want a separate section view (A/B), or to modify the parent view itself (C)?**

| Flavour | What you draw | What you get | When to use |
|---|---|---|---|
| **A. Partial-depth section view** (derived, full-width cut line, depth limited) | Full straight section line across parent + `Options \|= Partial (16)` + `SectionDepth > 0` | New derived view (B, C, …) showing the cut to a limited depth | Single internal feature mid-part; you want a separate "B-B" callout but not a full cut. |
| **B. Broken-out section view** (derived, **short cut line**, depth limited) | Short section line over the feature region + `Options \|= Partial (16) \| NotAligned (1)` + `SectionDepth > 0` | New derived view at a custom location with a section-letter callout | Localized feature in an externally-detailed part; the parent shows the full part with a small `B-B` callout, separate view shows the cut. |
| **C. In-place broken-out section** (no new view — modify parent) | Closed spline boundary on the parent + `IBrokenOutSectionFeatureData.Depth` | Parent view modified: material inside the spline cut away to `Depth`, exposing the feature in-place | The ASME/ISO jagged free-form boundary convention. Most compact — saves a whole view. Single localized internal (one cavity, one bore). |

Decision flow:

```
Want internal feature visible?
├─ Single localized feature, parent view otherwise clean?
│  → Flavour C (in-place, jagged boundary)
├─ Multiple internal features, or you want a separate scaled callout?
│  → Flavour A (derived view, full-width cut line, depth limited)
└─ One internal feature but you want it shown as a separate view rather than in-place?
   → Flavour B (derived view, short cut line, depth limited)
```

The Phase 1 view-plan should pick A/B/C explicitly per feature — not "section view, partial" without further qualification.

### Flavour A — Partial-depth section view (derived, full-width line)

Apply the partial flag in **three places** — Options bit, post-hoc setter, and verification read — so it sticks reliably. The Options bit can be overridden by template defaults; the setter can be ignored if the view isn't fully rebuilt; the verification catches both.

```csharp
// 1. Options bit at creation. SectionDepth > 0 is mandatory — depth=0 with Partial set
//    silently falls through to a full section regardless of the bit.
int opts = (int)swCreateSectionViewAtOptions_e.swCreateSectionView_Partial;  // 16
double depth = 0.015;  // 15 mm past the section line (model space, meters)
View sectionView = (View)swDraw.CreateSectionViewAt5(x, y, 0, "B", opts, null, depth);
if (sectionView == null) throw new InvalidOperationException("Section creation failed");

// 2. Post-hoc setters on IDrSection. Defensive: template state, prior section views in the
//    same session, or user-pref defaults can flip the bit back off even when Options had it.
DrSection sec = (DrSection)sectionView.GetSection();
sec.SetPartialSection(true);
sec.SectionDepth = depth;       // re-assert; SectionDepth alone with Partial=false does nothing
sec.SetAutoHatch(true);
swDrawModel.EditRebuild3();      // mandatory — flags don't apply until rebuild

// 3. Verify. SetPartialSection has no return value, so read it back via GetPartialSection.
//    If false, reapply and rebuild a second time; if still false after the retry, the geometry
//    doesn't support a partial cut at this depth (too small or line outside body) — bump depth
//    or recheck the line.
if (!sec.GetPartialSection())
{
    sec.SetPartialSection(true);
    sec.SectionDepth = depth;
    swDrawModel.EditRebuild3();
    if (!sec.GetPartialSection())
        throw new InvalidOperationException(
            $"Partial section flag refused to stick on '{sectionView.GetName2()}'. " +
            $"Increase SectionDepth past the far wall of the feature, or verify the " +
            $"section line crosses the body. Current depth={depth}m.");
}
if (Math.Abs(sec.SectionDepth - depth) > 1e-6)
    sec.SectionDepth = depth;     // depth got clamped or reset; force it back
```

The three-step pattern is non-optional: skipping the verification step is what users describe as "the agent forgot to select partial" — the call returned successfully, the view rendered, but the flag was never applied so the section came out as an indistinguishable full cut.

`SectionDepth` is measured **perpendicular to the section line, in model space (meters)**. Choose it to land just past the far wall of the bore / hole / pocket:

| Feature | Suggested `SectionDepth` |
|---|---|
| Through-hole in a thick plate (Ø ≤ plate thickness) | `hole_center_offset + hole_diameter × 0.6` |
| Blind hole / pocket (depth `d`) | `feature_top_to_line_distance + d + 0.002` (2 mm overrun for clarity) |
| Counterbore / counterdrill stack | Reach past the deepest level of the stack + 1–2 mm |
| Generic "go deep enough to see it" | `model_thickness × 0.55` (just past half) |

### Flavour B — Broken-out section view (derived, short cut line)

A broken-out section over a local feature only. The section line covers just the feature region (≈40% of view width), with arrowheads pointing inward. Add `NotAligned` (1) to the options so the new view isn't constrained to the parent's axis — a short line would otherwise place oddly. The callout on the parent spans only the short region; the rest is undisturbed.

```csharp
// Section line covers only ~40% of view width, centered on the feature.
double[] outline = (double[])parentView.GetOutline();
double cx = (outline[0] + outline[2]) / 2.0;
double cy = (outline[1] + outline[3]) / 2.0;
double halfW = (outline[2] - outline[0]) / 2.0;

double[] p1 = { cx - halfW * 0.4, cy, 0 };   // sheet coords
double[] p2 = { cx + halfW * 0.4, cy, 0 };

// Transform sheet → parent view's sketch space (same pattern as the full-section recipe).
Sketch vSketch = (Sketch)parentView.GetSketch();
MathTransform xf = vSketch.ModelToSketchTransform;
MathUtility mu = (MathUtility)swApp.GetMathUtility();
double[] t1 = (double[])((MathPoint)((MathPoint)mu.CreatePoint(p1)).MultiplyTransform(xf)).ArrayData;
double[] t2 = (double[])((MathPoint)((MathPoint)mu.CreatePoint(p2)).MultiplyTransform(xf)).ArrayData;

swDraw.ActivateView(parentView.GetName2());
swDrawModel.ClearSelection2(true);
SketchManager sk = swDrawModel.SketchManager;
sk.AddToDB = true;
SketchSegment line = (SketchSegment)sk.CreateLine(t1[0], t1[1], 0, t2[0], t2[1], 0);
sk.AddToDB = false;
line.Select4(false, null);

// Options: Partial (16) | NotAligned (1) = 17.
int opts = (int)(swCreateSectionViewAtOptions_e.swCreateSectionView_Partial
                | swCreateSectionViewAtOptions_e.swCreateSectionView_NotAligned);
double depth = 0.015;
View sv = (View)swDraw.CreateSectionViewAt5(sectionX, sectionY, 0, "B", opts, null, depth);
if (sv == null) throw new InvalidOperationException("Broken-out section creation failed");

// Defensive set + verify pattern (same three-place pattern as Flavour A).
DrSection sec = (DrSection)sv.GetSection();
sec.SetPartialSection(true);
sec.SectionDepth = depth;
sec.SetAutoHatch(true);
swDrawModel.EditRebuild3();

if (!sec.GetPartialSection())
{
    sec.SetPartialSection(true);
    sec.SectionDepth = depth;
    swDrawModel.EditRebuild3();
    if (!sec.GetPartialSection())
        throw new InvalidOperationException(
            "Partial flag refused to stick on the broken-out section. " +
            "Bump SectionDepth or check that the short cut line actually crosses the body.");
}
```

### Flavour C — In-place broken-out section (modify parent, no new view)

The ASME/ISO convention most readers expect from "broken-out section": a **free-form jagged boundary** (closed spline) on the parent view, everything inside cut away to a set depth — exposing the feature **in-place**, with no separate view. Most compact way to show a localized internal feature. Uses a different API path — `IBrokenOutSectionFeatureData`, not `CreateSectionViewAt5` — because nothing new is created; the parent view gets a broken-out-section *feature* added.

Pattern: activate the parent → draw a closed spline (or any closed loop) encircling the area to cut → select it → invoke the broken-out command → set depth via `IBrokenOutSectionFeatureData.Depth`. Convention is a free-form spline following the contours irregularly for the characteristic jagged "torn" boundary.

```csharp
// 1. Activate parent view and prepare sketch space.
swDraw.ActivateView(parentView.GetName2());
swDrawModel.ClearSelection2(true);

Sketch vSketch = (Sketch)parentView.GetSketch();
MathTransform xf = vSketch.ModelToSketchTransform;
MathUtility mu = (MathUtility)swApp.GetMathUtility();
SketchManager sk = swDrawModel.SketchManager;

// 2. Draw a closed spline boundary around the internal feature (sheet → sketch coords).
//    For a jagged "torn" look, scatter ~8–12 control points loosely around the feature.
double[] outline = (double[])parentView.GetOutline();
double cx = (outline[0] + outline[2]) / 2.0;
double cy = (outline[1] + outline[3]) / 2.0;
double r  = 0.020;   // 20 mm radius of the broken-out region on the sheet

int n = 10;
double[] pts = new double[n * 3];
var rng = new Random(0);
for (int i = 0; i < n; i++)
{
    double theta = 2 * Math.PI * i / n;
    double rr = r * (0.85 + 0.3 * rng.NextDouble());     // 15% jitter for the jagged look
    double sx = cx + rr * Math.Cos(theta);
    double sy = cy + rr * Math.Sin(theta);
    double[] sht = { sx, sy, 0 };
    double[] skt = (double[])((MathPoint)((MathPoint)mu.CreatePoint(sht)).MultiplyTransform(xf)).ArrayData;
    pts[i * 3]     = skt[0];
    pts[i * 3 + 1] = skt[1];
    pts[i * 3 + 2] = 0;
}

sk.AddToDB = true;
// Closed spline: pass IsClosed = true so SW connects the last point back to the first.
object spline = sk.CreateSpline2(pts, true);
sk.AddToDB = false;

// 3. Select the closed spline.
((SketchSegment)spline).Select4(false, null);

// 4. Insert the broken-out section. The exact creation method varies by SW version; the
//    UI command "Insert → Drawing View → Broken-out Section" maps to an InsertBrokenOutSection
//    call (some versions expose swDraw.InsertBrokenSection). The RunCommand path always works:
swDrawModel.Extension.RunCommand(
    (int)swCommands_e.swCommands_BrokenOutSection, "");
// SW picks the active sketch as the boundary; depth defaults to half-thickness.

// 5. Set depth programmatically by walking the parent view's broken-out section features.
object[] bsList = (object[])parentView.GetBreakOutSections();
if (bsList != null && bsList.Length > 0)
{
    Feature lastBS = (Feature)bsList[bsList.Length - 1];   // the one we just inserted
    BrokenOutSectionFeatureData bsd =
        (BrokenOutSectionFeatureData)lastBS.GetDefinition();
    bsd.AccessSelections(swDrawModel, null);
    bsd.Depth = 0.015;                  // 15 mm cut depth
    // bsd.DepthReference = (Entity)someEdge;   // alternative: cut down to a referenced edge
    lastBS.ModifyDefinition(bsd, swDrawModel, null);
}
swDrawModel.EditRebuild3();
```

Read or edit existing broken-out sections by enumerating them on the view:

```csharp
object[] bsList = (object[])view.GetBreakOutSections();
int n = view.GetBreakOutSectionCount();
foreach (object o in bsList ?? Array.Empty<object>())
{
    Feature bsFeat = (Feature)o;
    BrokenOutSectionFeatureData bsd = (BrokenOutSectionFeatureData)bsFeat.GetDefinition();
    bsd.AccessSelections(swDrawModel, null);

    double depth = bsd.Depth;                          // meters
    Entity depthRef = (Entity)bsd.DepthReference;      // null if using numeric Depth
    bsd.EditSketch = true;                              // expose boundary segments
    object[] segs = (object[])bsd.SketchSegment;       // the closed loop
    int segCount = bsd.GetSketchSegmentCount();

    // Modify (e.g. increase depth by 5 mm):
    bsd.Depth = depth + 0.005;
    bsFeat.ModifyDefinition(bsd, swDrawModel, null);
    bsd.ReleaseSelectionAccess();
}
```

**Why C wins for localized features** — compared to a derived section (A/B):

| | In-place broken-out (C) | Derived partial section (A / B) |
|---|---|---|
| Adds a new view to the sheet | No — parent shows the cut directly | Yes — extra view, callout, sheet space |
| Reader has to cross-reference | No — feature exposed where it is on the part | Yes — section-letter "B-B" callout + look at separate view |
| Best for | Single localized internal feature, externally-detailed part, A4/A3 sheet | Multiple internal features in different locations; larger sheet with space |
| Drafting convention | Free-form jagged boundary | Straight section line + arrowheads + letter |

For "I have ONE internal feature and an otherwise-fine external view, should I add a section view?" the answer is usually no — use Flavour C.

To dimension a broken-out section (Flavour C), target the **parent** view (there is no new view): use the parent's `SelectEntity` to grab the newly-exposed internal edges.

## How to: create a transverse section through off-axis features

A **transverse** section is a cut **perpendicular to the part's long axis** that reveals radial features the standard longitudinal cut can't see. A longitudinal cut (horizontal line through the revolve axis) only intersects geometry on the centerline — radial ports, cross-holes, keyways, and flats sit above or below the axis, so a centered horizontal cut passes through solid material and shows nothing.

Use it for: port bores drilled radially into a turned cylinder; cross-holes, keyways, or flats whose centerlines are perpendicular to the long axis; any internal feature visible in the front silhouette but invisible in a longitudinal section. If Phase 1 emitted a feature with `axis ⊥ revolve_axis`, the section for it is transverse.

| | Longitudinal (A-A) | Transverse (B-B) |
|---|---|---|
| Cut-line orientation | Horizontal (along axis) | Vertical (perpendicular to axis) |
| What it reveals | Bore IDs, wall thickness, axial steps | Port bores, cross-holes, keyway profiles |
| Alignment | Aligned below parent (`Options = 0`) | `NotAligned` (1) — free placement |
| Line routing | Through revolve-axis centerline (or median Y of visible edges) | Through feature's axial position via `ModelToViewTransform` |
| Coordinate source | `centerY` of parent view | Project model-space `featureX` → sheet X |

### Step 1 — Locate the feature in model space

Query the feature's cylindrical faces to recover the axial position (X along the part axis) and the radial axis direction:

```csharp
Feature feat = /* port / cross-hole / keyway feature */;
double featureX_m = 0;
foreach (object fo in (object[])feat.GetFaces())
{
    Face2 fc = (Face2)fo;
    Surface surf = (Surface)fc.GetSurface();
    if (!surf.IsCylinder()) continue;
    double[] cp = (double[])surf.CylinderParams;
    // cp = [cx, cy, cz, ax, ay, az, radius] in meters
    // (cx, cy, cz) = point on cylinder axis;  (ax, ay, az) = axis direction unit vector
    featureX_m = cp[0];          // for a part with revolve axis along X
    break;
}
```

For a part whose revolve axis is along X, a radial port's cylinder axis points along Y (or Z), and `cx` gives the feature's axial position. Substitute the correct index if the revolve axis is Y or Z. When the feature has multiple cylindrical faces, iterate all and pick the one whose axis is ⊥ to the revolve axis — longitudinal cylinders are the part body, not the port.

### Step 2 — Project the feature position into the parent view

```csharp
View parentView = frontView;
MathTransform m2v = parentView.ModelToViewTransform;
MathUtility mu = (MathUtility)swApp.GetMathUtility();

double[] featureModel = { featureX_m, 0, 0 };                       // on the revolve centerline
MathPoint ptView = (MathPoint)((MathPoint)mu.CreatePoint(featureModel))
    .MultiplyTransform(m2v);
double[] ptInView = (double[])ptView.ArrayData;
double lineX_sheet = ptInView[0];                                    // where the feature projects in sheet X
```

### Step 3 — Draw a vertical section line at that X

Span the full height of the parent view AND overrun the silhouette top and bottom (endpoints inside the body produce a degenerate cut — see the line-routing rule in [How to: create a full section](#how-to-create-a-full-section)).

```csharp
Sketch viewSketch = (Sketch)parentView.GetSketch();
MathTransform sketchXform = viewSketch.ModelToSketchTransform;

double[] fOut = (double[])parentView.GetOutline();
double centerY = (fOut[1] + fOut[3]) / 2.0;
double halfH   = (fOut[3] - fOut[1]) / 2.0;

// Vertical line at the feature's projected X, overrunning the parent height by 10%.
double[] topPt = { lineX_sheet, centerY + halfH * 1.10, 0 };
double[] botPt = { lineX_sheet, centerY - halfH * 1.10, 0 };

MathPoint topSk = (MathPoint)((MathPoint)mu.CreatePoint(topPt)).MultiplyTransform(sketchXform);
MathPoint botSk = (MathPoint)((MathPoint)mu.CreatePoint(botPt)).MultiplyTransform(sketchXform);
double[] tTop = (double[])topSk.ArrayData;
double[] tBot = (double[])botSk.ArrayData;

swDraw.ActivateView(parentView.GetName2());
swDrawModel.ClearSelection2(true);
SketchManager skMgr = swDrawModel.SketchManager;
skMgr.AddToDB = true;
SketchSegment secLine = (SketchSegment)skMgr.CreateLine(
    tTop[0], tTop[1], 0, tBot[0], tBot[1], 0);
skMgr.AddToDB = false;
secLine.Select4(false, null);
```

### Step 4 — Create with `NotAligned`

Pass `swCreateSectionView_NotAligned` (1) so the transverse view can be placed freely — a transverse cut is perpendicular to the parent's axis, so default alignment would constrain placement to an axis the section doesn't actually share with the parent.

```csharp
int opts = (int)swCreateSectionViewAtOptions_e.swCreateSectionView_NotAligned;  // 1
View secView = (View)swDraw.CreateSectionViewAt5(
    placementX, placementY, 0,
    "B",                  // section label
    opts,
    null,                 // no excluded components
    0);                   // full depth (0 = through)

if (secView == null) {
    // Standard null-return cleanup — delete the orphan line, retry, or fail loud.
    swDraw.ActivateView(parentView.GetName2());
    secLine.Select4(false, null);
    swDrawModel.EditDelete();
    throw new InvalidOperationException(
        "Transverse section creation failed. Verify lineX_sheet falls inside the parent's silhouette " +
        "and the line overruns the top/bottom edges.");
}

secView.UseSheetScale = 1;
DrSection sec = (DrSection)secView.GetSection();
sec.SetAutoHatch(true);
sec.SetDisplayOnlySurfaceCut(false);
swDrawModel.EditRebuild3();
```

### Step 5 — Verify the cut reveals the feature

A transverse cut that hits the port bore produces strictly more visible edges than a plain projection at the same X (the [edge-count heuristic](#how-to-verify-and-diagnose-a-flat-section)).

```csharp
int parentEdges  = ((object[])parentView.GetVisibleEntities2(
    null, (int)swViewEntityType_e.swViewEntityType_Edge))?.Length ?? 0;
int sectionEdges = ((object[])secView.GetVisibleEntities2(
    null, (int)swViewEntityType_e.swViewEntityType_Edge))?.Length ?? 0;
if (sectionEdges <= parentEdges) {
    // Cut didn't reveal the radial feature. Check that lineX_sheet matches the
    // feature's projected X (not the part's center), and that the cylinder axis you
    // queried is actually perpendicular to the revolve axis.
}
```

Then position to avoid overlap (`secView.Position = new double[] { newX, newY };`) and check against other views' `GetOutline()` pairwise. For **multiple radial features at different axial positions**, use one transverse section per feature each at its own `featureX`, or an offset section with vertical jog segments threading through each feature's X.

## How to: create a slice section (cut plane only)

Shows **only the surfaces intersected by the cutting plane**; material behind the cut is hidden. Two cases where this is the correct default, not an advanced option:

- **Hollow / shelled parts** — reveals a wall profile without the full body cross-section filling the view.
- **Dense repeating surface geometry** — knurling, thread cuts, diamond/checker/textured patterns. A full section renders every knurl diamond or thread turn as internal geometry and becomes illegible. Escalation ladder when even a slice is too busy:
  1. Slice section (`swCreateSectionView_DisplaySurfaceCut = 32`) — hides everything behind the cut plane.
  2. `swHIDDEN` / `swHIDDEN_GREYED` display mode on the section view — suppresses internal clutter further.
  3. Replace the geometry with a note (`"KNURL PER MIL-K-303"`, `"M10x1.5 THREAD"`) and don't dimension the texture in the section at all.

```csharp
int opts = (int)swCreateSectionViewAtOptions_e.swCreateSectionView_DisplaySurfaceCut;  // 32
View sliceView = (View)swDraw.CreateSectionViewAt5(x, y, 0, "C", opts, null, 0);

DrSection sec = (DrSection)sliceView.GetSection();
// sec.ExcludeSliceSectionBodies = true;  // drop bodies the plane doesn't intersect (assembly)
```

Two related controls, often confused:
- `swCreateSectionView_DisplaySurfaceCut` / `IDrSection.DisplaySurfaceBodies` — visibility of surface bodies in the view.
- `IDrSection.ExcludeSliceSectionBodies` — suppresses entire bodies the plane never touches (assembly-only).

For a parts drawing with a single solid body, `DisplaySurfaceCut` is the one you want.

## How to: create a removed or cropped-corner section

**Removed section** — the same cut pulled out and placed wherever fits best, often at a different scale. Create a standard section, then unlink alignment and rescale. Get free two-axis placement by one of:

1. **Create unaligned from the start** — pass `swCreateSectionView_NotAligned = 1` to `CreateSectionViewAt5`. Born as a removed section with no alignment; `Position` on both axes works immediately.
2. **Break alignment after creation** — `sectionView.AlignWithView(0, parentView)` (`swNoViewAlignment = 0`) unlinks. Re-link later with `AlignWithView(2, parentView)` (`swAlignViewHorizontalCenter`) or `AlignWithView(3, parentView)` (`swAlignViewVerticalCenter`) per cut orientation.
3. **Place right at creation** — the `(X, Y)` passed to `CreateSectionViewAt5` is honored on both axes even for linked views. If you know the target before the call, place it directly and skip any post-create `Position` set.

Set the scale on the removed view via `IView.ScaleDecimal2` (or `ScaleRatio`).

**Cropped-corner section** (sales-aid "just show the edge detail"): create a full section first, then crop the view (sketch a closed profile + `IView.SetCrop`), unlink its alignment (`IView.AlignWithView(0, parentView)`), and rescale via `IView.ScaleDecimal2`. Outside the scope of a standard part drawing but a common deliverable.

## How to: link a section view to its parent

Keep section views linked. An unlinked section is a floating picture: if the parent moves it doesn't follow, scale changes drift alignment, and downstream consumers (auto-arrange, BOM export, PDF layout solvers) can't reason about parent-child relationships.

**The link exists by default.** `CreateSectionViewAt5` — called **without** `swCreateSectionView_NotAligned` (1) — returns a view already aligned to its parent, with two relationships maintained automatically:
- **Alignment** — the section snaps to the parent's horizontal or vertical axis; moving the parent drags the section.
- **Cutting-line ownership** — the line stays in the parent's sketch, but `IDrSection::GetView()` returns the parent and `IDrSection::GetSectionView()` returns the derived view. That two-way pointer is what makes "linked" mean something.

Pass `NotAligned` (1) **only** when you deliberately want a removed section. For every other case, leave it off — it unlinks the section, which then won't follow parent moves and can't be re-aligned by auto-layout.

```csharp
// Confirm the link
View linkedParent = (View)((DrSection)sectionView.GetSection()).GetView();
bool isLinked = linkedParent != null && linkedParent.GetName2() == parentView.GetName2();

// If it was created unlinked and you want to re-link:
sectionView.AlignWithView(2, parentView);  // 2 = swAlignViewHorizontalCenter
// or  3 = swAlignViewVerticalCenter (depends on cut orientation)
```

### Placement follows cut-line orientation

By default (`NotAligned` not passed), alignment locks one axis:

- **Vertical cut line** (↕) → section can be placed **LEFT or RIGHT** of the parent. `Y` is locked to the parent's Y; only `X` is free.
- **Horizontal cut line** (↔) → section can be placed **ABOVE or BELOW** the parent. `X` is locked to the parent's X; only `Y` is free.

This comes from `IView::Position`: *"If it is aligned with another view, it will only be allowed to move along the alignment vector."* Writes to the locked axis are **silently ignored** — no exception, no warning, no `false` return. Setting `Position = { x, y }` on a linked vertical-cut section applies only `x`; `y` is discarded.

So: for a **vertical** cut, change only X; for a **horizontal** cut, change only Y. When you genuinely need free two-axis placement, use one of the three approaches in [removed sections](#how-to-create-a-removed-or-cropped-corner-section) — don't write both axes hoping one takes effect (e.g. a vertical-cut section set to the same X as its parent lands beside it on the free X axis, not below).

## How to: place a section without overlap

`CreateSectionViewAt5(X, Y, …)` places the *center* of the section at `(X, Y)`. You can't know the section's extent until after the call returns (SolidWorks decides the scale), so use a two-step pattern: create at a rough position, read the new view's outline, then `Position`-nudge the gap to what you want. Passing `centerX, outline[1] - 0.08` (80 mm below parent's bottom, gap-to-center) overlaps the parent if the section is itself ≥160 mm tall.

```csharp
// Step A — rough placement (leave enough slack that the create succeeds)
double roughY = outline[1] - 0.15;               // 150 mm below parent bottom (generous)
View sectionView = (View)swDraw.CreateSectionViewAt5(
    centerX, roughY, 0, "A", 0, null, 0);
if (sectionView == null) throw new InvalidOperationException("Section creation failed");

// Step B — measure the section view and reposition so the gap is exactly what we want
double gap = 0.04;                                // 40 mm gap between parent and section
double[] secOutline = (double[])sectionView.GetOutline();
double secHalfH = (secOutline[3] - secOutline[1]) / 2;
double targetY  = outline[1] - gap - secHalfH;   // parent bottom - gap - half of section height
// Preserve horizontal alignment with the parent (linked views snap, but Position still works on X)
double[] newPos = { centerX, targetY };
sectionView.Position = newPos;

swDrawModel.EditRebuild3();
```

For a **vertical cut** (section placed right of parent), mirror on X:

```csharp
double[] secOutlineR = (double[])sectionView.GetOutline();
double secHalfW = (secOutlineR[2] - secOutlineR[0]) / 2;
double targetX  = outline[2] + gap + secHalfW;   // parent right + gap + half of section width
double[] newPos = { targetX, centerY };
sectionView.Position = newPos;
```

Rule of thumb: **gap ≈ 30–60 mm** on an A-size sheet, **60–100 mm** on larger sheets. Smaller than 25 mm and dimensions from the two views start colliding.

Keep the repositioned view in bounds — if `targetY` falls below the sheet's drawable area, `Position` silently clamps or leaves the view put. Check against the sheet:

```csharp
Sheet sheet = (Sheet)swDraw.GetCurrentSheet();
double[] sheetProps = (double[])sheet.GetProperties2();  // [paperSize, templateIn, scale1, scale2, W, H]
double sheetW = sheetProps[5], sheetH = sheetProps[6];
if (targetY - secHalfH < 0.02) {
    // Not enough room below — shrink scale or place the section to the side instead.
}
```

## How to: dimension a section view

Section views override the generic dimensioning patterns in `dimensioning-simple.md`. Read this before writing any `Add*Dimension2` call that targets a section.

### Use `AddHorizontalDimension2` / `AddVerticalDimension2`, not `AddDimension2`

Generic `AddDimension2` / `AddDimension` frequently returns `null` in section views *even with a valid selection* — SolidWorks can't resolve the direction from selections that include silhouettes, projected arcs, or rotated geometry. The explicit-direction variants pin the axis and succeed on the same selections.

```csharp
targetView.SelectEntity(edgeA, false);
targetView.SelectEntity(edgeB, true);
// Reliable — direction is pinned:
DisplayDimension h = (DisplayDimension)swDrawModel.AddHorizontalDimension2(textX, textY, 0);
DisplayDimension v = (DisplayDimension)swDrawModel.AddVerticalDimension2(textX, textY, 0);
// Often returns null in section views — reserve AddDimension2 for simple orthographic views:
DisplayDimension g = (DisplayDimension)swDrawModel.AddDimension2(textX, textY, 0);
```

Text position `(X, Y, Z)` is a **hint** — SolidWorks often repositions text during creation, and a downstream `AlignDimensions(AutoArrange)` moves it again (see the "How to: arrange dimensions (AutoArrange)" section in `dimensioning-simple.md`). A reasonable point above/below/beside the view is enough.

### Select by entity, never by coordinate

```csharp
// In section views, select via the view, not by sheet coordinate:
targetView.SelectEntity(edge, append);     // the reliable path
// swExt.SelectByID2("", "EDGE", x, y, 0, …) fails in section views
```

`SelectByID2` assumes a linear sheet→view coordinate mapping. A section view is rotated, clipped, and (for partial/slice sections) masked — the mapping is neither linear nor injective, so computed sheet coordinates do not land on the edge and every attempt returns `false`. No amount of coordinate tweaking fixes it. `SelectByID2` by coordinate is fine in simple orthographic views (front/top/right where the edge is clearly in the view interior); forbidden in section views.

Also: edges near the section boundary (where the cut intersects the body) are nearly impossible to hit with a pick point regardless; and circles in the model become **arcs** in section views, so their projected centers don't match `curve.CircleParams`.

### Section-view geometry rules

Internalise these before writing dimensioning code for a section:

1. **The outer diameter is NOT a circle in a section view.** In a half- or full-section of a turned part, the OD projects as two **parallel horizontal lines** at `y = +R` and `y = −R` (model space). To dimension the OD: find two parallel lines of matching length and opposite Y, select both, and call `AddVerticalDimension2`. Full circular edges only appear for features fully inside the cut plane (bore IDs, counterbores, bolt-hole patterns on the section face).
2. **Two-circle selection can produce an angle dimension.** Selecting two circular edges and calling `AddDimension2` sometimes yields an angle (90°, 270°) instead of a linear center-to-center distance. Force the direction with `AddHorizontalDimension2` / `AddVerticalDimension2`, or select the two straight edges the circles share.
3. **Circle centers shift.** A model full circle may appear as an arc — its `CircleParams` center is still the model-space center, but the projected on-sheet center may not equal the arc's on-sheet midpoint. Don't use `CircleParams` to compute a sheet coordinate for any pick-based call.
4. **`view.GetOutline()` returns sheet space, `CircleParams` / `GetPoint` return model space.** Don't mix them; convert with `view.ModelToViewTransform` if comparison is needed.
5. **Two parallel lines can produce an angle dimension too.** Selecting two horizontal silhouette lines (top and bottom OD) and calling `AddDimension2` may yield `180°` instead of a linear OD. Fix, in order of preference:
   - `AddVerticalDimension2` for horizontal parallel lines (dim extends vertically between them) or `AddHorizontalDimension2` for vertical parallel lines.
   - Select one horizontal + one perpendicular vertical edge, then `AddDimension2`.
   - `AddDimension` with an explicit `swSmartDimensionDirection_*`.
6. **Silhouette edges are a separate entity class.** For turned / axisymmetric parts, `GetVisibleEntities2` with just `swViewEntityType_Edge` misses the OD lines. Also enumerate `swViewEntityType_SilhouetteEdge` and treat them the same as regular edges when identifying geometry.

### Moving a dim between section-view and circle-view — delete and re-create

Moving a **linear Ø-between-silhouettes dim** from a section view to a view where the feature is a full circle (or vice versa) produces a floating callout — the target view has no matching geometry pair to reattach to. SolidWorks keeps the dim but strands it on the sheet. For circular features that need to move between section-view and circle-view:
- Delete the original dim.
- In the target view select the correct geometry (full circle → `AddDiameterDimension2`; silhouette pair in a section → `AddVerticalDimension2` on a horizontal cylinder, `AddHorizontalDimension2` on a vertical one).
- Replay the PREFIX / SUFFIX / ABOVE / BELOW qualifier text via `DisplayDimension.SetText(...)` so `THRU`, `6X`, depth symbols, etc. come back — the SetText slot reference is in `dimensioning-simple.md`.

Use delete-and-recreate, not `DragModelDimension` — `DragModelDimension` preserves dim type, not geometry association.

## How to: delete a section view

Section views have two pieces of state: the derived `IView` on the sheet, and the cutting line in the **parent view's sketch**. Delete both — deleting only the view leaves the cutting line orphaned on the parent (a stray labelled arrow with no section to point to).

```csharp
// Inputs: View sectionView, View parentView
if (sectionView != null)
{
    // 1. Capture the section line BEFORE deleting the view — GetSection() goes null after.
    DrSection sec = (DrSection)sectionView.GetSection();
    string sectionViewName = sectionView.GetName2();

    // 2. If the view was unlinked (removed section), restore alignment first so any
    //    dependents re-snap; otherwise skip.
    // sectionView.AlignWithView(1, parentView);  // 1 = swDefaultViewAlignment

    // 3. Delete the derived view. Select-then-Delete via the model is the reliable path.
    swDrawModel.Extension.SelectByID2(
        sectionViewName, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
    swDrawModel.EditDelete();

    // 4. Delete the cutting line in the parent's sketch. Activate parent, select the
    //    sketch segment, delete. IDrSection.GetLineInfo() gave us the vertices earlier
    //    if we need to target a specific line when multiple sections share a parent.
    swDraw.ActivateView(parentView.GetName2());
    Sketch parentSketch = (Sketch)parentView.GetSketch();
    object[] segs = (object[])parentSketch.GetSketchSegments();
    if (segs != null)
    {
        // Simple case (one section on this view): deleting all segments in the view sketch is
        // fine — nothing else lives in a drawing view's sketch by default. If multiple sections
        // share the parent, use GetLineInfo() to match by endpoints.
        swDrawModel.ClearSelection2(true);
        foreach (object o in segs)
        {
            SketchSegment s = (SketchSegment)o;
            s.Select4(true, null);  // append to selection
        }
        swDrawModel.EditDelete();
    }

    swDrawModel.EditRebuild3();
}
```

When you delete the parent view instead, the section and its line go with it automatically — no manual cleanup needed in that order.

## Gotchas & fixes

- **To get a real interior reveal, route the line through the feature centers and overrun the silhouette ≥10% on both ends.** A line through the view centroid or stopping at the body edge produces a degenerate cut that silently looks like a plain projection — no warning, no `null`, no exception.
- **To section concave / multi-body parts, route through the median Y of visible body edges, not `GetOutline()`'s center.** `GetOutline()` is a bounding rectangle; for L/U/T/ring/multi-body parts its center can sit in empty space, so `CreateSectionViewAt5` returns `null` (sometimes with a modal "section line does not intersect model" dialog that hangs the macro). On `null` return, delete the orphan line and retry once before raising — don't swallow the `null`, or every downstream `GetSection()` / `GetOutline()` throws `NullReferenceException`.
- **To draw the line where you intend, apply `ModelToSketchTransform` and `ActivateView` the parent first.** Raw sheet coords to `CreateLine` land at a rotated/scaled offset (line diagonal or offscreen); `CreateLine` writes to the *active* view's sketch, so without `ActivateView(parentView...)` the line goes into the wrong sketch and the create sees an empty selection and returns `null`. Section-line coords are view-sketch space; section-view `Position` is sheet space — run each input through the right transform.
- **To project a feature to the right cut location, apply BOTH transforms.** `ModelToViewTransform` tells you WHERE to cut; `ModelToSketchTransform` converts that into the coordinate system `CreateLine` expects. Skip the first and the line lands at view center; skip the second and it lands diagonally or offscreen.
- **To use the real first drawing view, call `GetNextView()` once.** `GetFirstView()` returns the sheet background; its `GetOutline()` returns sheet bounds, which rarely match a real view, so a line placed off it ends up centered on the sheet.
- **To let `CreateSectionViewAt5` see the line, make `line.Select4(false, null)` the last call before it** — no intervening `ClearSelection2`, no other selections. The call consumes the current selection.
- **To make `IDrSection` changes take effect, call `EditRebuild3()` after them.** `SetAutoHatch`, `SetPartialSection`, `SectionDepth`, `SetReversedCutDirection` — none repaint until rebuild.
- **To get a partial flag that sticks, apply it in three places** — `Options` bit at creation, post-hoc `sec.SetPartialSection(true)` + `sec.SectionDepth = depth`, then `EditRebuild3` and **verify with `sec.GetPartialSection()`**. `SetPartialSection` returns `void` so you can't tell if it applied, and template state / prior sections / user prefs can reset it. If verify returns `false`, reapply once and rebuild again; if still false, the geometry doesn't support partial at this depth — increase `SectionDepth` or check the line crosses the body. This is the fix for "agent forgot to select partial."
- **To make `Partial` actually limit depth, set `SectionDepth > 0`.** `SectionDepth = 0` with `Partial` falls through to a full cut. The post-hoc setter needs `SectionDepth` re-asserted too — `SetPartialSection(true)` without setting depth leaves whatever stale value was last there. After `EditRebuild3`, read `sec.SectionDepth` back and re-set if SW clamped or reset it.
- **To keep a partial cut hatched, call `SetAutoHatch(true)` after creation** (on the `IDrSection` for A/B, rebuild the parent for C) — some SW versions leave it unhatched.
- **To make an in-place broken-out (C) actually cut, pass a closed boundary that reaches the feature.** Pass `IsClosed = true` to `CreateSpline2` and verify `bsd.GetSketchSegmentCount() > 0` — an unclosed spline silently no-ops (feature created, cuts nothing). If you see no internal geometry, bump `Depth` or set `DepthReference` to an edge inside the feature. Pad the boundary ~15–25% beyond the feature's extent so it doesn't clip the feature edge ambiguously.
- **To place a broken-out derived view (B) sensibly, combine `Partial (16) | NotAligned (1)`.** Without `NotAligned`, the derived view tries to align to the parent's axis and lands oddly.
- **To keep a section following its parent, leave `NotAligned` (1) off** unless you want a removed section. `NotAligned` unlinks the section; unlinked sections don't follow parent moves and can't be re-aligned by auto-layout.
- **To avoid silently clobbering a label, use sequential letters** — `CreateSectionViewAt5("A", …)` twice overwrites the first "A" without warning. Use `IDrSection::SetLabel2(label, true)` to get the duplicate-name prompt.
- **To place a section without overlap, use create-rough → measure → reposition** with `sectionView.GetOutline()` so the *edge* of the section clears the parent, not its center. Gap-to-center placement overlaps.
- **To move both axes of a linked section, unlink it first (or pass `NotAligned` at creation, or place at creation).** A linked section silently ignores writes to its locked axis — for a vertical cut only X applies, for a horizontal cut only Y.
- **To read `IDrSection` data on a view you're deleting, read it before `EditDelete()`.** `GetSection()` returns `null` after delete — capture label, line info, and depth first.
- **To delete the section line, `ActivateView` the parent first.** `EditDelete` operates on the active view's sketch — if the sheet is active, the delete no-ops silently. For multiple sections on one parent, use `IDrSection::GetLineInfo()` to match the right line by endpoints rather than clearing the sketch. Rebuild after deletion (`EditRebuild3()`) or a phantom label can linger in the sheet's cached draw list.
- **To avoid `InvalidCastException`, keep the COM casts.** `GetSketch()`, `CreateLine()`, `GetSection()`, `GetOutline()`, `GetSketchSegments()` all return `object`; omitting `(Sketch)`, `(SketchSegment)`, `(DrSection)`, `(double[])`, `(object[])` causes a cast error or late-binding failure at runtime.
- **To dimension inside a section, follow the section-view rules** ([How to: dimension a section view](#how-to-dimension-a-section-view)): silhouette pairs, select by entity not `SelectByID2`, `AddHorizontal/VerticalDimension2` over `AddDimension2`.
