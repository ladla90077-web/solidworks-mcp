---
description: Guide for creating rectangular extrusions (boxes, plates, cuboids) via the SolidWorks COM API in a single atomic step — sketch creation through extrusion.
keywords: [box, plate, cuboid, rectangular extrusion, FeatureExtrusion3, CreateCenterRectangle, boss extrude, sketch rectangle, blind extrude]
---

# Creating a Box / Plate / Cuboid Extrusion

---

## Key Points

- This is a **single atomic operation** — no need to inspect state, check sketches, or verify planes beforehand on a clean/known model.
- Uses `FeatureExtrusion3` (available since SW 2014+, works on all modern versions).
- All dimensions must be in **meters** (SolidWorks internal unit).
- Default extrusion direction is along the **sketch plane normal** (e.g., Front Plane sketch extrudes along +Z).

## Plane Quick Reference

| Plane | Normal | Rectangle lies in | SelectByID2 name |
|-------|--------|-------------------|------------------|
| Front Plane | +Z | XY | `"Front Plane"` |
| Top Plane | +Y | XZ | `"Top Plane"` |
| Right Plane | +X | YZ | `"Right Plane"` |

## Complete Code Template

```csharp
var result = new Dictionary<string, object>();
ModelDoc2 swModel = (ModelDoc2)swApp.ActiveDoc;
SketchManager skMgr = swModel.SketchManager;
FeatureManager ftMgr = swModel.FeatureManager;

// === PARAMETERS (all in meters) ===
string planeName = "Front Plane";  // or "Top Plane", "Right Plane"
double width  = 0.300;   // X-extent (300mm)
double height = 0.200;   // Y-extent (200mm)
double depth  = 0.030;   // Extrusion depth (30mm)
string featName = "Base_Plate_300x200x30";

// === SELECT PLANE & OPEN SKETCH ===
swModel.Extension.SelectByID2(planeName, "PLANE", 0, 0, 0, false, 0, null, 0);
skMgr.InsertSketch(true);

// === DRAW CENTERED RECTANGLE ===
// CreateCenterRectangle(cx, cy, cz, cornerX, cornerY, cornerZ)
// Coordinates are in sketch-local space (which equals model space for origin planes)
skMgr.CreateCenterRectangle(0, 0, 0, width / 2, height / 2, 0);

// === EXTRUDE (FeatureExtrusion3 — 23 params) ===
// Do NOT close the sketch first: FeatureExtrusion3 consumes the active sketch
// and exits sketch mode itself.
Feature feat = (Feature)ftMgr.FeatureExtrusion3(
    true,       // Sd:  single-ended
    false,      // Flip: don't flip cut side
    false,      // Dir:  don't reverse direction (extrudes along +normal)
    0,          // T1:   swEndCondBlind (0)
    0,          // T2:   (unused for single-ended)
    depth,      // D1:   extrusion depth in meters
    0,          // D2:   (unused)
    false,      // Dchk1:  no draft
    false,      // Dchk2:  no draft
    false,      // Ddir1:  (unused)
    false,      // Ddir2:  (unused)
    0,          // Dang1:  (unused)
    0,          // Dang2:  (unused)
    false,      // OffsetReverse1
    false,      // OffsetReverse2
    false,      // TranslateSurface1
    false,      // TranslateSurface2
    true,       // Merge: merge result in multibody part
    false,      // UseFeatScope
    false,      // UseAutoSelect
    0,          // T0:   swStartSketchPlane (0) — start from sketch plane
    0,          // StartOffset (unused when T0=0)
    false       // FlipStartOffset (unused when T0=0)
);

feat.Name = featName;
result["success"] = true;
return result;
```

## Variations

### Corner-anchored rectangle (not centered)
Replace `CreateCenterRectangle` with `CreateCornerRectangle`:
```csharp
// CreateCornerRectangle(x1, y1, z1, x2, y2, z2)
skMgr.CreateCornerRectangle(0, 0, 0, width, height, 0);
```
This places one corner at origin, opposite corner at (width, height).

### Double-ended extrusion (symmetric about sketch plane)
```csharp
Feature feat = (Feature)ftMgr.FeatureExtrusion3(
    false,      // Sd: double-ended
    false, false,
    0, 0,       // Both ends blind
    depth / 2,  // D1: half-depth each side
    depth / 2,  // D2: half-depth each side
    false, false, false, false, 0, 0,
    false, false, false, false,
    true, false, false,
    0, 0, false
);
```

### Reverse extrusion direction
Set `Dir` (3rd param) to `true` to extrude opposite to the plane normal.

## Common swEndConditions_e Values

| Value | Name | Use |
|-------|------|-----|
| 0 | swEndCondBlind | Fixed depth |
| 1 | swEndCondThroughAll | Through entire part |
| 5 | swEndCondOffsetFromSurface | Offset from a selected surface — see warning |
| 6 | swEndCondMidPlane | Symmetric about sketch plane (use Sd=true, depth=total) |
| 7 | swEndCondUpToBody | Terminate at a selected body — see warning |

For MidPlane, set `Sd=true`, `T1=6`, and `D1=total depth` (SW splits it automatically).

> **MidPlane is `6`, not `5`.** `T1=5` (`swEndCondOffsetFromSurface`) and `T1=7`
> (`swEndCondUpToBody`) both require a pre-selected reference (a surface / a body). A fresh
> part has neither, so either throws `0x80010105 (RPC_E_SERVERFAULT)` on the first feature.
> Always look enum values up — do not trust memorized ones.

## Reminders

- **No need to call `get_model_state` or `inspect_sketch`** for this simple operation — the automatic state diff after execution confirms success.
- **Rename the feature** immediately with a descriptive name including key dimensions.
- **Merge=true** is important when adding to an existing body; for the first feature in a part it doesn't matter but is good practice.

Generated At: 2026-04-27T19:36:57.954101