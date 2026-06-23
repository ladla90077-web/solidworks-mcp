---
description: How to draw long parts (shafts, tubes, lead screws, bottles, fittings — anything with aspect ratio ≥ ~3:1) using a broken parent view + detail bubbles per cluster + section for internals. Covers trigger thresholds, the view-strategy decision flow, break-position selection, ordering with detail views, dimension distribution, and the Phase 1 plan contract.
---

# Guide: Drawing Long Parts

> A "long part" has a dominant axis ≥ ~3× the cross-section (shafts, lead screws, cylinder bodies, pipe fittings, gland nuts, bottles, valve bodies with a through-bore). It almost always needs a broken parent view — without one the parent crowds the sheet or shrinks small features to illegibility. Read this BEFORE finalising the view list whenever aspect ratio ≥ 3:1.

## Recipe (happy path)

1. **Check the trigger** — `aspectRatio = max(L,W,H) / min(W,H) ≥ 3.0`, or a clear dominant axis with end clusters and a uniform middle → [Trigger](#how-to-decide-whether-to-break).
2. **Place primary view unbroken** — `CreateDrawViewFromModelView3(model, "*Front", x, y, 0)` → [Build views](#how-to-build-the-canonical-long-part-layout).
3. **Place longitudinal section A-A unbroken** — `CreateSectionViewAt5(x, y, 0, "A", 0, null, 0)` on the revolve axis.
4. **Create every detail view against the UNBROKEN parent + section** — `CreateDetailViewAt4(...)`, one bubble per cluster → [Detail bubbles](#how-to-pick-cluster-detail-bubbles).
5. **Apply the break to the front** — `frontView.InsertBreak3(...)` then `BreakView` → [Break placement](#how-to-place-the-break).
6. **Apply the matching break to the section** — read `frontView.GetBreakLines()[0].GetPosition(0/1)` and replicate.
7. **(Optional) transverse section E-E** — `CreateSectionViewAt5` perpendicular to the axis; independent of the break.
8. **Place the iso** — `CreateDrawViewFromModelView3` with `"*Isometric"`, no dims.
9. **Dimension detail-first, then section, then front, then transverse** — `InsertModelDimensions` per view → [Dimension distribution](#how-to-distribute-dimensions-across-views).
10. **Auto-arrange, dedup, style** — see `dimensioning-simple.md` → "How to: arrange dimensions (AutoArrange)".

## API quick reference

| Step | Call | Notes |
|---|---|---|
| 1 — Place primary | `swDraw.CreateDrawViewFromModelView3(model, "*Front", x, y, 0)` | Unbroken |
| 2 — Place section | `swDraw.CreateSectionViewAt5(x, y, 0, "A", 0, null, 0)` | Full, unbroken; cut line on revolve axis |
| 3 — Place each detail | `swDraw.CreateDetailViewAt4(x, y, 0, swDetViewSTANDARD, 1, 1, "B", swDetCirclePROFILE, true, false, false, 5)` | Rectangle boundary; against unbroken parent |
| 4 — Break front | `frontView.InsertBreak3(2, breakX1, breakX2, swBreakLine_Curve, 1, false)` then `BreakView` | Vertical break for a horizontal-axis part. `swBreakLine_Curve` (3) is the wavy / S-curve default — reads cleanly on both prismatic and revolved parts |
| 5 — Break section to match | Read `frontView.GetBreakLines()[0].GetPosition(0/1)` → apply identical values to section | Don't recompute |
| 6 — Transverse section (optional) | `CreateSectionViewAt5` with cut perpendicular to axis | Independent of the break |
| 7 — In-place broken-out (optional) | `BrokenOutSectionFeatureData` on the front (no new view) | See `section-views.md` Flavour C — for single internals when a full section is overkill |
| 8 — Iso | `CreateDrawViewFromModelView3` with `"*Isometric"`, no dims | Top-right corner |
| 9 — Dimension | `InsertModelDimensions` per view in detail-first order | See `dimensioning-simple.md` → "Order rationale" |

**Break-line style** — the `swBreakLineStyle_e` value passed to `InsertBreak3`: `swBreakLine_Curve` = 3 (wavy / S-curve, the recommended default for both prismatic and revolved parts). Break orientation: pass `2` (vertical break) for a horizontal-axis part so the gap is cut across the long axis.

**Detail boundary** — `swDetViewStyle_e` value passed to `CreateDetailViewAt4`: `swDetCirclePROFILE` selects a sketched-profile (rectangle/polygon) boundary instead of a circle. On a longitudinal section of a turned part the cluster is axially-long-and-radially-short, so a rectangle captures the band without dragging unrelated geometry in.

### Decision table — when to break

| L / (max cross-section) | What to do |
|---|---|
| < 3 | Standard 3-view layout. Skip this guide. |
| 3 – 4 | Broken view **only if** any end feature renders < 2 mm on paper at the no-break scale. Otherwise standard. |
| 4 – 8 | Break. Pick a uniform mid-section, shorten to ~3:1 visual L/D. |
| > 8 | Break, hard. Pick a uniform mid-section, target ~2:1 visual L/D. May need TWO breaks for very long parts (rare). |

### View classes — order of creation

| Order | View | Carries | Required? |
|---|---|---|---|
| 1 | **Front view (broken)** | OD silhouettes, overall length, axial step lengths between visible shoulders, thread callouts, chamfer dims on visible edges, detail-circle callouts | Always |
| 2 | **Longitudinal section A-A** | IDs, counterbore Ø, internal step lengths, internal radii, GD&T position/runout | If ANY internal feature exists |
| 3 | **Detail B / D / F / …** | One bubble per feature **cluster**, not per feature. Dims that don't fit at parent scale | One per cluster |
| 4 | **Transverse section E-E** | Cross-hole angles, keyway orientation, non-circular OD profiles | If off-axis features exist |
| 5 | **Iso pictorial** | Decorative only, no dims | Optional |

### Dimension distribution table

| Dim | Lives on | Why |
|---|---|---|
| Overall length | Front (broken) — **once** | SW adjusts the value for the break gap automatically. Never put it on the section too. |
| Axial step length (OD shoulders) | Front | Shoulders project as clean silhouettes here. |
| Axial step length (ID / bore steps) | Longitudinal section | Hidden everywhere except the section. |
| Every OD diameter | Pick **one** carrier view (front or section). Stick to it. | Both views show ODs as silhouette pairs. |
| Every ID diameter | Longitudinal section | Use line pairs at `z = ±R` + `AddVerticalDimension2` + `SetText(PREFIX, "<MOD-DIAM>")`. |
| Groove / O-ring / undercut dims | Detail view (cluster bubble) | High scale; multiple dims per feature fit cleanly. |
| Cross-hole Ø | Transverse section | Full-circle face-on. |
| Cross-hole index angle | Transverse section | Angular references belong on the face-on view. |
| Cross-hole axial position | Front view | Axial = length, not angle. |
| Chamfers | Front for OD, section for ID | `AddChamferDim`. |
| Threads | Text callout on front | `AddNote` with the standard spec — don't dimension thread geometry. |

## How to: decide whether to break

Apply this guide when **either**:

- `aspectRatio = max(L, W, H) / min(W, H) ≥ 3.0` — covers turned parts and rectangular bars.
- A clear dominant axis with feature clusters at the ends and a uniform middle, regardless of strict ratio.

The aspect-ratio threshold is intentionally low: at 3:1 you're already losing legibility on A3; at 5:1 you're cluttering; above 8:1 the choice is binary (break, or split across sheets). Use the [decision table](#decision-table--when-to-break) to pick the response.

The threshold for "break needed" drops as the smallest dimensioned feature shrinks. A Ø1.5 mm O-ring groove on a 4:1 part reads at well under 1 mm on the unbroken parent — so break to free up scale headroom for the detail view.

This guide exists because Phase 1 reliably forgets broken views on long parts: the trigger gets skipped under the default "front + top + right + iso" reflex. To avoid that, run the trigger check before finalising the view list whenever aspect ratio ≥ 3:1.

## How to: build the canonical long-part layout

Apply this layout as a default; deviate only with a written reason. (Don't reinvent the layout — deviating without a reason almost always produces duplicate dims or a crowded sheet.)

```
┌───────────────────────────────────────────────────────────────┐
│                                                               │
│  Front view (axis horizontal, BROKEN at uniform middle)       │
│  ────────────────[≈≈]────────────────                          │
│  OD silhouettes, overall length, axial step lengths, chamfers │
│                                                               │
│  Section A-A  (cut on the axis, full)                         │
│  ────────────────[≈≈]────────────────                          │
│  IDs, counterbores, internal step lengths, bore Ø dims        │
│                                                               │
│  DETAIL B (left cluster, 2:1–4:1)   DETAIL D (right cluster)  │
│  [bubble]                            [bubble]                  │
│                                                               │
│  Optional: TRANSVERSE SECTION E-E for cross-holes / keyways   │
│  Optional: small unscaled iso, top-right corner               │
└───────────────────────────────────────────────────────────────┘
```

Create the [five view classes](#view-classes--order-of-creation) in order. The order matters and is mandatory.

```csharp
// 1. Primary view, unbroken
View front = (View)swDraw.CreateDrawViewFromModelView3(model, "*Front", x, y, 0);

// 2. Longitudinal section A-A, unbroken, cut on the revolve axis
View sectionAA = (View)swDraw.CreateSectionViewAt5(secX, secY, 0, "A", 0, null, 0);
```

For the API mechanics of breaking views, see `broken-views-guide.md`. For section-view flavours (longitudinal vs transverse, full vs partial), see `section-views.md`.

## How to: order the build (details before the break)

Build in this exact order. The first three steps are the load-bearing ones — getting them right is what keeps detail boundaries stable and dims on the correct view.

```
1. Place primary view (unbroken)
2. Place longitudinal section A-A (unbroken)
3. Create EVERY detail view against the UNBROKEN parent + section
4. Apply break to the front view (InsertBreak3 + BreakView)
5. Apply matching break to the section (read parent's GetBreakLines → GetPosition; replicate)
6. (Optional) Create transverse section E-E (rotated cut — not affected by break)
7. (Optional) Create broken-out sections on the parent for single-internal-feature locations
   that don't justify a separate section view (see section-views.md → Flavour C)
8. Place iso view (no dims)
9. Dimension — detail views FIRST, then section, then front, then transverse (DuplicateDims=true ordering)
10. Auto-arrange, dedup, style
```

- **Create details against the UNBROKEN parent.** Detail boundaries lock to model geometry, not sketch space, so they survive the subsequent break cleanly. (Apply the break before creating details and the gap collapses sketch space — rectangle (`swDetCirclePROFILE`) boundaries especially get unstable coordinates inside it. See `detail-views.md` → "Authoring order with broken parents".)
- **Match the section break to the parent break.** Read the parent's break-line positions via `IView::GetBreakLines()[i].GetPosition(0/1)` and replicate them; recomputing from percentages drifts and produces visible misalignment. (See `broken-views-guide.md` → "Matching Break Positions from a Parent View".)
- **Dimension detail-first.** Long parts always carry small features (O-rings, snap-ring grooves, undercuts) that must land on the detail at 4:1, not the parent at 1:5. With `DuplicateDims = true` it's first-come-first-served, so the detail must claim them before the parent grabs them and leaves the detail empty.

## How to: place the break

Put the break in a **uniform region** — no features inside the gap. Two rules:

1. **Use the largest contiguous featureless gap along the long axis.** Walk the dim plan; record each feature's axial position; find the biggest gap between adjacent positions; place the break in the middle of that gap.
2. **Don't break across a shoulder, fillet, or chamfer.** Even when the gap technically spans it, the break visually swallows whatever's underneath — fine for a uniform OD, wrong for anything with character.

```csharp
// Pseudo-code for the break-position pick (called from Phase 1's layout pass).
var featureAxial = dimPlan
    .Where(r => r.kind != "overall-bbox")
    .Select(r => r.axialPosition)
    .OrderBy(x => x)
    .ToList();

double bestGap = 0, breakCenter = 0;
for (int i = 0; i + 1 < featureAxial.Count; i++)
{
    double gap = featureAxial[i + 1] - featureAxial[i];
    if (gap > bestGap)
    {
        bestGap = gap;
        breakCenter = (featureAxial[i] + featureAxial[i + 1]) / 2.0;
    }
}
// Break width: typically 8–15 mm of paper space.
// Convert breakCenter from model meters → sheet meters at the planned scale.
```

Then apply the break and replicate it onto the section:

```csharp
// 4. Break the front. Pass 2 (vertical break) for a horizontal-axis part; swBreakLine_Curve = 3.
front.InsertBreak3(2, breakX1, breakX2, (int)swBreakLineStyle_e.swBreakLine_Curve, 1, false);
swDraw.BreakView();

// 5. Read the parent's break-line positions and apply the identical values to the section — don't recompute.
object[] breakLines = (object[])front.GetBreakLines();
IBreakLine bl = (IBreakLine)breakLines[0];
double p0 = bl.GetPosition(0);
double p1 = bl.GetPosition(1);
sectionAA.InsertBreak3(2, p0, p1, (int)swBreakLineStyle_e.swBreakLine_Curve, 1, false);
swDraw.BreakView();
```

If the biggest gap is < 10 mm of model space there's no good break point — the part is feature-dense; split it across sheets instead of breaking.

## How to: distribute dimensions across views

Long parts always have more dims than fit cleanly on one view. Follow the [dimension distribution table](#dimension-distribution-table) — it's the canonical pattern, and deviating from it almost always creates duplicates.

Pick **one carrier view per dim category and stick to it**: the most common long-part mistake is putting the overall length AND every step length on BOTH the front and the section. Each category has a single home in the table.

For ID diameters specifically, dimension on the longitudinal section using a line pair at `z = ±R`, `AddVerticalDimension2`, then `SetText(PREFIX, "<MOD-DIAM>")` to render the Ø symbol. (The QUALIFIER/QUANTITY `SetText` cheat-sheet lives in `dimensioning-simple.md` → "How to: callout text".)

## How to: pick cluster detail bubbles

A cluster earns its own detail view when **all** of:

- **≥ 3 features within ~20 mm axial.** O-ring + back-up ring + thread relief at one shoulder is the textbook case.
- **Combined feature span ≤ ~10 mm of paper at parent scale.** A 30 mm-of-paper span isn't a cluster — it's a region, and its dims fit in-line.
- **≥ 4 dims required for the cluster.** Sum each feature's SIZE + LOCATION + QUALIFIER. Below 4 dims, put them on the parent.

Apply this per end of the part. Long parts typically end up with one detail per end — `DETAIL B` for the left cluster, `DETAIL D` for the right. Make **one bubble per cluster** and dimension everything inside it; don't make four bubbles for four grooves at the same end.

Use a **rectangle (`swDetCirclePROFILE`)** boundary on a longitudinal section of a turned part: the cluster is axially-long-and-radially-short, so the rectangle captures the band without pulling unrelated geometry in. (A circle boundary inscribes a much wider region than needed.)

See `detail-views.md` → "Recipe B — Rectangular (profile) detail view" and its symmetry shortcut ("bound y from a small positive value up to +sketchHalfY — capture the upper wall only") for cluster boundaries on revolved-part sections.

## How to: write the Phase 1 plan

When the extractor reports `isLongPart: true`, the Phase 1 plan's "Views" item must include, at minimum:

```
Views:
- *Front (BROKEN at axial X = ___, gap width ___ mm) — primary, shows overall length, OD silhouettes, chamfers; detail-circle callouts for B/D
- Section A-A (cut on *Front through revolve axis, FULL, BROKEN to match parent at same X) — exposes IDs, counterbore depths, internal step lengths
- Detail B — from Section A-A at left cluster (x = ___, y = 0), rectangle boundary spanning [xMin, yMin, xMax, yMax] in sketch space, scale ___ — magnifies [list features]
- Detail D — from Section A-A at right cluster (x = ___, y = 0), rectangle boundary spanning [xMin, yMin, xMax, yMax], scale ___ — magnifies [list features]
- (optional) Section E-E (transverse cut at x = ___, NotAligned) — exposes cross-hole angles, keyway orientation
- ISO — small shaded, top-right, no dims
```

Put the break parameters in the plan **explicitly** (axial X and gap width), not "we'll figure it out". A long-part plan without break coordinates is incomplete.

## Gotchas & fixes

- **To keep detail boundaries stable: create every detail against the UNBROKEN parent + section.** Boundaries lock to model geometry, so they survive the later break. (Breaking first collapses sketch space inside the gap and rectangle (`swDetCirclePROFILE`) boundaries get unstable coordinates.) See `detail-views.md` → "Authoring order with broken parents".
- **To avoid visible break misalignment: copy the parent's break-line positions onto the section.** Read `frontView.GetBreakLines()[0].GetPosition(0/1)` and apply identical values. (Recomputing from percentages drifts.) See `broken-views-guide.md` → "Matching Break Positions from a Parent View".
- **To get small features onto the detail at 4:1: dimension detail-first, then section, then front, then transverse.** With `DuplicateDims = true` it's first-come-first-served. (Dimension the parent first and it grabs the O-ring/snap-ring/undercut dims, leaving the detail empty.)
- **To keep dims off the wrong view: pick one carrier view per dim category.** Use the distribution table. (Putting overall length and every step length on both the front and the section is the #1 source of duplicate dims.)
- **To get a legible overall length: place it on the broken front once.** SW adjusts the value for the break gap automatically. (Also placing it on the section double-dimensions the length.)
- **To break cleanly: place the gap in the largest featureless region, never across a shoulder/fillet/chamfer.** (A break swallows whatever's under the gap; over a featured region it hides geometry.)
- **When the biggest gap is < 10 mm of model space: split across sheets instead of breaking.** The part is feature-dense and has no good break point. A 200 mm worm shaft with a continuous thread is the classic case — break it anywhere and you obscure geometry. Use a larger paper size (A2 → A1) or two sheets.
- **For one bubble per cluster, not per feature.** Four grooves at one shoulder = one `DETAIL B`, dimensioned inside. (Four bubbles for four grooves clutters the sheet and duplicates leaders.)
- **For axially-long clusters on a turned section: use a rectangle (`swDetCirclePROFILE`) boundary.** It captures the band tightly. (A circle inscribes a much wider region than needed and drags in unrelated geometry.)
- **Limit to two breaks.** Two is the legibility limit; three or more reads like a comic strip. If you'd need more, use a larger sheet or an unbroken view at a tighter scale.
- **Skip the break when its benefit is marginal.** L/D ≈ 3.2 with no small features: use a generous scale instead.
- **Ask before breaking for first-article / tooling-shop audiences.** Some shops reject broken views on principle when the inspector wants to physically lay the drawing alongside the part. Use an unbroken view at a tighter scale for those.

## Companion guides

- `broken-views-guide.md` — full API reference for `InsertBreak3` + `BreakView`, break-line styles, position calculation.
- `detail-views.md` — `CreateDetailViewAt4` signature, circle vs rectangle boundaries, offset-correction pattern, cleanup.
- `detail-view-dimensioning.md` — dimensioning inside a detail bubble.
- `section-views.md` — `CreateSectionViewAt5` signature, longitudinal vs transverse, partial / broken-out flavours (A/B/C).
- `dimensioning-simple.md` → "Order rationale" — `InsertModelDimensions` per-view loop in detail-first order; "Algorithm" — construction-dim cleanup; "How to: arrange dimensions (AutoArrange)" — `AlignDimensions(AutoArrange)` final pass.
- `dimensioning-simple.md` → "How to: callout text" — the QUALIFIER/QUANTITY `SetText` cheat-sheet for groove/ID/thread callouts.
