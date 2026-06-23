---
description: "Guide for creating circular arrays of holes (bolt-hole patterns) via the SolidWorks COM API, covering PCD calculations, sketch plane selection pitfalls, single-sketch vs circular-pattern approaches, and cut-extrude best practices."
keywords:
  - circular pattern
  - bolt hole
  - PCD
  - pitch circle diameter
  - FeatureCut4
  - through all both
  - sketch plane
  - face selection
  - hole array
  - FeatureCircularPattern4
---

# Creating Circular Arrays of Holes

## 1. Reading Hole Pattern Dimensions

Key dimensions to extract:
- **PCD (Pitch Circle Diameter)**: The diameter of the circle on which hole centers are placed
- **Hole diameter**: Often given as a tolerance range — use the mean for modeling
- **Number of holes**: Confirm angular spacing = 360° / N
- **Starting angle**: Usually 0° unless the drawing specifies otherwise
- **Hole type**: Through-all, blind, counterbored, countersunk

### Calculations
```csharp
double pcdR = pcdDiameter / 2.0;   // PCD radius
double holeR = holeDiameter / 2.0;  // Hole radius
// Convert to meters if needed:
double inToM = 0.0254;
```

---

## 2. Choosing the Sketch Plane — CRITICAL

This is where most failures occur. The sketch **MUST** be on a plane perpendicular to the hole axes.

### Approach A — Standard Plane (RECOMMENDED)
- For holes along the Y-axis (vertical part), use the **Top Plane**
- On Top Plane: sketch X = model X, sketch Y = model Z
- Use **Through All Both Directions** to cut through regardless of sketch offset from the part

**This approach avoids face selection issues entirely.**

### Approach B — Select the Actual Face
- Use `SelectByID2` with type `"FACE"` at a point ON the face
- The point must be in **model coordinates**
- **PITFALL**: Face selection often fails silently. If it fails, the sketch lands on a default plane, creating holes in the wrong orientation
- **ALWAYS** check the boolean return value

**Recommendation**: Use Approach A for maximum reliability.

---

## 3. Sketching All Holes in One Sketch

The simplest approach: draw all N circles in a single sketch, then do one Cut-Extrude. This creates **exactly one feature** in the tree.

```csharp
// Select Top Plane
swExt.SelectByID2("Top Plane", "PLANE", 0, 0, 0, false, 0, null, 0);
swSketchMgr.InsertSketch(true);

// Draw N circles at equal angular intervals
for (int i = 0; i < numHoles; i++)
{
    double angle = i * (360.0 / numHoles) * Math.PI / 180.0;
    double cx = pcdR * Math.Cos(angle);
    double cy = pcdR * Math.Sin(angle);
    swSketchMgr.CreateCircle(cx, cy, 0, cx + holeR, cy, 0);
}
```

**Note**: On Top Plane, sketch `(cx, cy)` maps to model `(cx, 0, -cy)` or `(cx, 0, cy)`. For a symmetric circular pattern centered on origin, the sign convention doesn't matter — the pattern is identical either way.

---

## 4. Cut-Extrude Through All Both Directions

Use `FeatureCut4` with Through All in both directions for guaranteed penetration:

```csharp
Feature cutFeat = (Feature)swFeatMgr.FeatureCut4(
    false,          // Sd = false → double-ended (BOTH directions)
    false,          // Flip
    false,          // Dir
    1, 1,           // T1=T2 = swEndCondThroughAll
    0, 0,           // D1, D2 (ignored for through-all)
    false, false, false, false, 0, 0,   // draft params
    false, false, false, false,          // offset/translate
    false,          // NormalCut (false for non-sheet-metal)
    false,          // UseFeatScope
    true,           // UseAutoSelect
    false, false, false,                 // assembly params
    0,              // T0 = swStartSketchPlane
    0,              // StartOffset
    false,          // FlipStartOffset
    false           // OptimizeGeometry
);
```

**Key**: `Sd = false` makes it double-ended. `T1 = T2 = 1` ensures complete penetration.

---

## 5. Alternative: Single Hole + Circular Pattern

For parametric patterns (easy to change count later):
1. Sketch ONE hole on the PCD at angle 0
2. Cut-Extrude through all
3. Use `FeatureCircularPattern4` to pattern it N times around the axis

This creates 2 features (Cut + Pattern) but is more parametric.

**Note**: The circular pattern approach requires selecting:
- The cut feature to pattern (Mark 4)
- The axis of revolution (Mark 1) — typically a temporary axis through the center

For simple bolt-hole patterns, the **all-in-one-sketch approach** is simpler and creates fewer features.

---

## 6. Verification

After creating the holes:
- [ ] Visually count the holes — confirm N holes present
- [ ] Check the feature tree for the Cut-Extrude feature
- [ ] Optionally enumerate circular edges to confirm positions:
  - Each through-hole creates 2 circular edges (top and bottom)
  - Expected: N × 2 new circular edges with radius = holeR
  - Centers should all be at distance pcdR from the origin

### Common Failures

| Symptom | Cause |
|---------|-------|
| Fewer holes than expected | Sketch on wrong plane — some holes miss the part |
| Holes in wrong direction | Face selection failed silently, sketch defaulted to wrong plane |
| Holes too close/far from center | Wrong PCD radius (check diameter vs radius) |

---

## 7. Quick Reference: Key Enum Values

Always verify via documentation lookup, but for quick reference:

**swEndConditions_e:**
| Value | Name |
|-------|------|
| 0 | `swEndCondBlind` |
| 1 | `swEndCondThroughAll` |
| 6 | `swEndCondThroughAllBoth` |

**swStartConditions_e:**
| Value | Name |
|-------|------|
| 0 | `swStartSketchPlane` |
| 1 | `swStartOffset` |
| 2 | `swStartSurface` |

**REMINDER**: Never trust memorized enum values in production code. Always verify via documentation.

Generated At: 2026-04-13T07:35:20.738265