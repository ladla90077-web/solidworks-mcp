---
description: Place dimensions from scratch off a view's visible geometry when there's no model dim to project — pull visible entities, classify edges by curve type, dimension by class, take overall dims from extreme vertices, and the polygonal across-flats (A/F) recipe.
---

# Guide: Manual Dimensioning (from visible geometry)

> Place a dimension **from scratch** off a view's visible geometry — for the case where there's no model dim to project and `InsertModelDimensions` / `InsertModelAnnotations4` leave a feature undimensioned. Pull the view's visible entities, classify each edge by curve type, dimension by class, take overall dims from the extreme vertices, and handle polygonal across-flats. Companion to `dimensioning-simple.md` (bulk per-dimension recipe, QUALIFIER/QUANTITY callout text, chamfer/hole callouts, broken leaders, AutoArrange) and `dimensioning-systems.md` (ordinate / baseline / chain / polar / tabular / GD&T systems).

This guide owns exactly one job: building a drawing-side dimension by selecting visible edges / vertices / faces and calling an `Add…Dimension2`. It does **not** cover which dimensioning system to choose (`dimensioning-systems.md`), the QUALIFIER/QUANTITY `SetText` cheat-sheet, chamfer/hole-callout overlays, broken leaders, or AutoArrange (all in `dimensioning-simple.md`).

---

## When to use this

Reach for from-scratch dimensioning when:

- A feature came in without model dims (imported body, surface, or a cut whose driving dims aren't marked for drawing), so there's nothing to project.
- You need a specific drawing-side dim the model doesn't carry — an overall length, a hole-to-edge distance, an across-flats on a polygonal pocket.
- The bulk insert (`dimensioning-simple.md` → "How to: order and insert dims per view") left a per-view shortfall and you're patching it by hand.

After placing any from-scratch dim, replay its QUALIFIER + QUANTITY text (`dimensioning-simple.md` → callout-text cheat-sheet) and arrange the view once with `AlignDimensions(AutoArrange)` (`dimensioning-simple.md` → "How to: arrange dimensions (AutoArrange)"). Drawing-side dims land where you place them and stack unless arranged.

---

## API quick reference

**Pulling visible geometry to dimension** (when you hold no persistent id and want to pick entities by position):

- `IView.GetVisibleComponents()` → `object[]` of `Component2` drawn in the view; pass each (or `null` for all) to the next call.
- `IView.GetVisibleEntities2(component, entityType)` → `object[]` of visible entities. `entityType` = `swViewEntityType_e`: `1`=Edges, `2`=Vertices, `3`=Faces, `4`=Silhouette edges. **Pass these values, NOT the `swSelectType_e` values (`12`/`11`/`4`/`2`)** — a wrong value returns 0 entities with no error (the #1 reason a manual pass finds nothing, especially on detail / section-derived views). Section-derived detail views carry real `IEdge`/`IVertex`/`IFace2` geometry, so dimensioning works on them exactly as on a standard view.
- `IView.ModelToViewTransform` → `MathTransform`; `modelPt.MultiplyTransform(it)` maps a model point to view/sheet meters (to compare positions / pick extremes).

**Dimension-creation calls** (label coords `x, y, z` in **sheet meters**, `z = 0` for 2D):

| Call | Selection needed | Produces |
|---|---|---|
| `IModelDoc2.AddHorizontalDimension2(x, y, z)` | two line edges | horizontal (axial) linear dim |
| `IModelDoc2.AddVerticalDimension2(x, y, z)` | two line edges | vertical (radial) linear dim |
| `IModelDoc2.AddDiameterDimension2(x, y, z)` | one circular edge | Ø dim |
| `IModelDoc2.AddRadialDimension2(x, y, z)` | one arc/fillet edge | radius dim |
| `IModelDoc2.AddDimension2(x, y, z)` | one or two edges | smart dim (auto-detect) |
| `IDrawingDoc.AddChamferDim(x, y, z)` | angled edge + adjacent straight edge | chamfer dim |

**Selection signatures** (only what these calls need):

`View.SelectEntity(entity, Append)` — `entity` is an `IEdge`/`IVertex`/`ISketchPoint` pointer you already hold (skips the XYZ lookup); `Append` `false` clears prior selection, `true` adds to it.

`IModelDocExtension.SelectByID2(Name, Type, X, Y, Z, Append, Mark, Callout, SelectOption)` — when you only have a position: `Name=""` locates by XYZ; `Type` = `"VERTEX"`, `"EDGE"`, etc.; `X, Y, Z` in **sheet-space** meters; `Append` as above; pass `Mark, Callout, SelectOption` = `0, null, 0`.

---

## How to: add a dim from visible entities (edges / vertices / faces)

When there's no model dim to project — or you need a specific drawing-side dim (an overall length, a hole-to-edge distance) — pull the view's **visible** geometry, pick the entities you want, select them, and call an `Add…Dimension2`. `view.GetVisibleEntities2(component, entityType)` returns the entities actually drawn in the view; `view.ModelToViewTransform` maps a model point into view/sheet coordinates so you can compare positions and choose the right entity (leftmost, topmost, etc.). **Always auto-arrange afterward** — drawing-side dims land where you place them and stack unless `AlignDimensions(AutoArrange)` tidies them (see `dimensioning-simple.md` → "How to: arrange dimensions (AutoArrange)").

```csharp
// Entities in the view, by component. entityType = swViewEntityType_e:
//   1 = Edges, 2 = Vertices, 3 = Faces, 4 = Silhouette edges
object[] comps = (object[])view.GetVisibleComponents();
foreach (Component2 comp in comps)
{
    object[] edges      = (object[])view.GetVisibleEntities2(comp, 1);
    object[] vertices   = (object[])view.GetVisibleEntities2(comp, 2);
    object[] faces      = (object[])view.GetVisibleEntities2(comp, 3);
    object[] silhouettes = (object[])view.GetVisibleEntities2(comp, 4);
}

// Map a model point into view/sheet coords (to compare/choose entities)
MathTransform viewXform = view.ModelToViewTransform;
MathUtility mathUtil = (MathUtility)swApp.GetMathUtility();
double[] ptModel = /* point from an entity, e.g. vertex.GetPoint() */;
MathPoint viewPt = (MathPoint)((MathPoint)mathUtil.CreatePoint(ptModel)).MultiplyTransform(viewXform);
double[] pt = (double[])viewPt.ArrayData;   // [x, y, z] in sheet meters

// Select the two entities and dimension between them
swModel.ClearSelection2(true);
view.SelectEntity((Entity)edge1, false);    // first selection
view.SelectEntity((Entity)edge2, true);     // append
swModel.AddHorizontalDimension2(x, y, 0);   // or AddVerticalDimension2
```

### Classify edges before dimensioning

`GetVisibleEntities2(comp, 1)` returns every edge mixed together — classify each by its curve type and whether it has start/end vertices to pick the right `Add…Dimension2` call. This also distinguishes a full circle (hole) from an arc (fillet): full circles have no vertices, arcs do.

```csharp
foreach (var edgeObj in edges)
{
    var edge = (Edge)edgeObj;
    var curve = (Curve)edge.GetCurve();
    var sv = (Vertex)edge.GetStartVertex();
    var ev = (Vertex)edge.GetEndVertex();

    if (curve.IsLine() && sv != null && ev != null)
    {
        // Straight edge — groove wall, bore surface, step, chamfer
        var sp = (double[])sv.GetPoint();  // meters
        var ep = (double[])ev.GetPoint();  // meters
    }
    else if (curve.IsCircle() && sv != null)
    {
        // Arc — fillet, partial groove
        var cp = (double[])curve.CircleParams;  // [cx, cy, cz, ax, ay, az, radius]
    }
    else if (curve.IsCircle() && sv == null && ev == null)
    {
        // Full circle — through-hole, port
    }
    else if (!curve.IsLine() && !curve.IsCircle() && sv == null && ev == null)
    {
        // Closed spline — O-ring groove, gasket channel
    }
}
```

Then dimension by class:

- **Two line edges → linear.** `AddHorizontalDimension2` (axial) or `AddVerticalDimension2` (radial). A single edge passed to `AddDimension2` returns `null` — select two.
- **One circular edge → Ø.** `AddDiameterDimension2`, on a **real circular edge, not a silhouette** — silhouettes are projected lines, not circles, so they produce no Ø dim.
- **One arc/fillet → radius.** `AddRadialDimension2`.
- **Angled edge + adjacent straight edge → chamfer.** `AddChamferDim` (the second selection is the reference edge).

### Overall dimensions from the extreme vertices

A common case: an overall length and height on the front view. Walk the view's visible vertices, transform each to sheet coords, keep the extreme one in each direction, then dimension across the pairs. Offset the label outside the view outline.

```csharp
View sheetView = (View)swDraw.GetFirstView();
View frontView = (View)sheetView.GetNextView();

double[] outline = (double[])frontView.GetOutline();   // [xMin, yMin, xMax, yMax] sheet m
double xMin = outline[0], yMin = outline[1], xMax = outline[2], yMax = outline[3];
double viewCenterX = (xMin + xMax) / 2.0, viewCenterY = (yMin + yMax) / 2.0;
double offset = 0.015;                                  // 15 mm clear of the view

MathTransform viewXform = frontView.ModelToViewTransform;
MathUtility mathUtil = (MathUtility)swApp.GetMathUtility();

object[] visibleVertices = (object[])frontView.GetVisibleEntities2(
    null, (int)swViewEntityType_e.swViewEntityType_Vertex);
if (visibleVertices == null) return;

Vertex leftV = null, rightV = null, topV = null, bottomV = null;
double minX = double.MaxValue, maxX = double.MinValue;
double minY = double.MaxValue, maxY = double.MinValue;
foreach (object obj in visibleVertices)
{
    Vertex v = (Vertex)obj;
    double[] viewPt = (double[])((MathPoint)((MathPoint)mathUtil.CreatePoint(
        (double[])v.GetPoint())).MultiplyTransform(viewXform)).ArrayData;
    if (viewPt[0] < minX) { minX = viewPt[0]; leftV = v; }
    if (viewPt[0] > maxX) { maxX = viewPt[0]; rightV = v; }
    if (viewPt[1] < minY) { minY = viewPt[1]; bottomV = v; }
    if (viewPt[1] > maxY) { maxY = viewPt[1]; topV = v; }
}

// Overall length — horizontal dim above the view
if (leftV != null && rightV != null)
{
    swModel.ClearSelection2(true);
    frontView.SelectEntity((Entity)leftV, false);
    frontView.SelectEntity((Entity)rightV, true);
    swModel.AddHorizontalDimension2(viewCenterX, yMax + offset, 0);
}

// Overall height — vertical dim left of the view
if (topV != null && bottomV != null)
{
    swModel.ClearSelection2(true);
    frontView.SelectEntity((Entity)topV, false);
    frontView.SelectEntity((Entity)bottomV, true);
    swModel.AddVerticalDimension2(xMin - offset, viewCenterY, 0);
}

swModel.ClearSelection2(true);
swModel.ForceRebuild3(true);
// Then AlignDimensions(AutoArrange) on the view — see dimensioning-simple.md → "How to: arrange dimensions (AutoArrange)".
```

---

## How to: polygonal pockets (across-flats)

A polygonal pocket — a cut whose sketch profile is a regular N-sided polygon — is **not** a round hole. `AddHoleCallout2` and `AddDiameterDimension2` return `null` on its edges (none are circular). The correct dimension is the **across-flats (A/F)** distance: the perpendicular distance between any two antiparallel edges.

**Recognize it from the extractor:** the cut's sketch has N straight segments (N ≥ 3), all within ~1% of each other in length, with opposing pairs antiparallel. Three sides → triangular; four equal → square; five → pentagonal; six → hex; eight → octagonal. When Phase 1 classifies a "hole" as polygonal, plan the dim as A/F, not Ø.

**Dimensioning recipe (view-agnostic):**

```csharp
// 1. Enumerate straight edges in the view
object[] edges = (object[])targetView.GetVisibleEntities2(null, (int)swViewEntityType_e.swViewEntityType_Edge);

// 2. Find antiparallel edge pairs that belong to the pocket.
//    Two edges are antiparallel when their direction vectors dot to ≈ -1
//    (or +1 if you don't care about orientation). Limit to edges of roughly
//    equal length and within the pocket's bounding area so you don't match
//    part silhouettes.
Edge edgeA = null, edgeB = null;
var straight = new List<(Edge e, double[] dir, double len, double[] mid)>();
foreach (object obj in edges)
{
    Edge e = (Edge)obj;
    Curve c = (Curve)e.GetCurve();
    if (!c.IsLine()) continue;
    Vertex sv = (Vertex)e.GetStartVertex();
    Vertex ev = (Vertex)e.GetEndVertex();
    double[] sp = (double[])sv.GetPoint();
    double[] ep = (double[])ev.GetPoint();
    double dx = ep[0]-sp[0], dy = ep[1]-sp[1], dz = ep[2]-sp[2];
    double len = Math.Sqrt(dx*dx + dy*dy + dz*dz);
    if (len < 1e-6) continue;
    straight.Add((e, new[]{ dx/len, dy/len, dz/len }, len,
                  new[]{ (sp[0]+ep[0])/2, (sp[1]+ep[1])/2, (sp[2]+ep[2])/2 }));
}

// Pair-wise: same length (within 1%), antiparallel (dot ≈ -1),
// midpoints separated by the expected A/F distance.
double targetAF = 0.010; // from Phase 1 — the measured across-flats distance in meters
for (int i = 0; i < straight.Count && edgeA == null; i++)
for (int j = i+1; j < straight.Count; j++)
{
    var a = straight[i]; var b = straight[j];
    if (Math.Abs(a.len - b.len) / Math.Max(a.len, b.len) > 0.01) continue;
    double dot = a.dir[0]*b.dir[0] + a.dir[1]*b.dir[1] + a.dir[2]*b.dir[2];
    if (dot > -0.99) continue;
    double dx = a.mid[0]-b.mid[0], dy = a.mid[1]-b.mid[1], dz = a.mid[2]-b.mid[2];
    double mid = Math.Sqrt(dx*dx + dy*dy + dz*dz);
    if (Math.Abs(mid - targetAF) > targetAF * 0.05) continue;
    edgeA = a.e; edgeB = b.e; break;
}

// 3. Select the pair and dimension. AddDimension2 resolves to the perpendicular
//    distance between antiparallel lines, which IS the A/F value.
if (edgeA != null && edgeB != null)
{
    swDrawModel.ClearSelection2(true);
    targetView.SelectEntity(edgeA, false);
    targetView.SelectEntity(edgeB, true);
    DisplayDimension afDim = (DisplayDimension)swDrawModel.AddDimension2(textX, textY, 0);

    // 4. Apply QUALIFIER / QUANTITY per the callout-text rules. Use the triplet, not part 0.
    //    Examples: "4X 10 A/F THRU"   "10 A/F ▼ 5"  — see dimensioning-simple.md → callout-text cheat-sheet.
    afDim.SetText(3, "4X");              // ABOVE — quantity (only if patterned)
    afDim.SetText(2, " A/F THRU");       // SUFFIX — standard callout
    // For blind pocket: afDim.SetText(2, " A/F"); afDim.SetText(4, "▼ 5");
}
```

- **`AddDimension2` is the reliable call.** `AddHorizontalDimension2` / `AddVerticalDimension2` only work when one edge pair aligns with the view's H/V axes (a "pointy-up" hex has horizontal top/bottom edges; "flat-up" has vertical left/right edges). Generic `AddDimension2` on the selected pair returns the perpendicular distance regardless of orientation.
- **The Phase-1 sketch-segment count is the gatekeeper.** When the extractor reports "Cut, 6 equal straight sides," dimension A/F and skip `AddDiameterDimension2` entirely.
- **Across-corners vs across-flats.** A/F is the standard machining callout for polygonal sockets (hex keys, wrench flats). If the customer wants across-corners, switch the suffix to `" A/C"` and measure vertex-to-opposite-vertex. Default to A/F.

---

## Gotchas & fixes

- **Two edges for a linear dim — a single edge returns `null`.** `AddDimension2` / `AddHorizontalDimension2` / `AddVerticalDimension2` need two line edges selected; pass only one and you get `null` back. Select both walls before the call.
- **`AddDiameterDimension2` needs a real circular edge, not a silhouette.** Silhouette edges (`entityType = 4`) are projected lines, not circles — they produce no Ø dim. Use a true circular edge (`curve.IsCircle() && sv == null`) for a through-hole, and skip silhouettes when hunting for the dimensionable circle.
- **Tell circles from arcs.** Both come from `GetVisibleEntities2(comp, 1)`. Full circles (through-holes) have `GetStartVertex() == null`; arcs (fillets, partial cuts) have real vertices. Filter on the vertex, not on radius — radius alone conflates a Ø10 hole with an R5 fillet.
- **Dimension polygonal pockets A/F, not Ø.** A regular N-sided pocket has no circular edge — `AddHoleCallout2` and `AddDiameterDimension2` return `null`. Use `AddDimension2` across an antiparallel edge pair (see "How to: polygonal pockets").
- **Map model points through `ModelToViewTransform` before comparing positions.** Raw `vertex.GetPoint()` is in model meters; pick "leftmost"/"topmost" only after `MultiplyTransform(view.ModelToViewTransform)` puts every candidate in the same sheet frame.
- **Auto-arrange after placing from-scratch dims.** They land where you put the label and stack until `AlignDimensions(AutoArrange)` reflows the view (see `dimensioning-simple.md`).
