---
description: "Best practices for creating cut-extrude features via the SolidWorks COM API, covering end condition selection, cut direction, deletion cascades, and common patterns for through-holes vs pocket cuts."
keywords:
  - extrude cut
  - FeatureCut4
  - end condition
  - through all
  - blind cut
  - swEndConditions_e
  - cut direction
  - sketch normal
  - deletion cascade
---

# Creating Extrude Cut Features

## 1. Choose the Correct End Condition

The most common mistake is using Through All (`swEndCondThroughAll = 1`) when a Blind cut (`swEndCondBlind = 0`) is needed.

**Through All cuts through ALL solid bodies in the cut direction** — not just the face you sketched on. This means:
- A hole sketched on a top surface will cut through that surface AND any geometry below
- A cutout sketched on a base will cut upward through walls and features above
- A pocket on one face will exit through the opposite face and keep cutting

### Rule of Thumb
- **Blind** (`T1=0`) with specific depth `D1`: When you want to cut through a known thickness only
- **Through All** (`T1=1`): ONLY for holes that must penetrate the entire part in one direction
- **Through All Both** (`Sd=false`, `T1=T2=1`): ONLY for holes that must go through everything in both directions
- **Through Next** (`T1=2`): Cut through just the next wall/surface encountered

**Default safe choice: Blind with known depth.** Only escalate to Through All when certain the cut should penetrate everything.

---

## 2. API Reference: FeatureCut4

```csharp
Feature FeatureCut4(
    bool Sd,           // true=single-ended, false=double-ended
    bool Flip,         // true to remove material outside profile
    bool Dir,          // true to reverse default cut direction
    int T1,            // End condition direction 1 (swEndConditions_e)
    int T2,            // End condition direction 2 (swEndConditions_e)
    double D1,         // Depth direction 1 (meters, for Blind)
    double D2,         // Depth direction 2 (meters, for Blind)
    bool Dchk1, bool Dchk2,     // Draft enable
    bool Ddir1, bool Ddir2,     // Draft direction
    double Dang1, double Dang2, // Draft angles
    bool OffsetReverse1, bool OffsetReverse2,
    bool TranslateSurface1, bool TranslateSurface2,
    bool NormalCut,              // Sheet metal only (false for parts)
    bool UseFeatScope,           // Body scope control
    bool UseAutoSelect,          // Auto-select bodies
    bool AssemblyFeatureScope,   // Assembly only
    bool AutoSelectComponents,   // Assembly only
    bool PropagateFeatureToParts,// Assembly only
    int T0,                      // Start condition (swStartConditions_e)
    double StartOffset,          // Offset distance if T0=swStartOffset
    bool FlipStartOffset,        // Flip offset direction
    bool OptimizeGeometry        // Sheet metal only
)
```

**Uses the ACTIVE SKETCH.** The sketch must be in edit mode when this is called.

---

## 3. End Condition Enum Values (swEndConditions_e)

| Value | Name | Description |
|-------|------|-------------|
| 0 | `swEndCondBlind` | Fixed depth (specify D1/D2 in meters) |
| 1 | `swEndCondThroughAll` | Through entire part in one direction |
| 2 | `swEndCondThroughNext` | Through next surface only |
| 3 | `swEndCondUpToVertex` | Up to a selected vertex |
| 4 | `swEndCondUpToSurface` | Up to a selected surface |
| 5 | `swEndCondOffsetFromSurface` | Offset from a selected surface |
| 6 | `swEndCondMidPlane` | Symmetric about the sketch plane |
| 7 | `swEndCondUpToBody` | Up to a selected body |
| 9 | `swEndCondThroughAllBoth` | Through all in both directions |

**REMINDER**: Always verify enum values via documentation lookup before using. Never trust memorized values.

---

## 4. Common Patterns

### Pattern A — Through Hole (must penetrate entire part)
```csharp
FeatureCut4(
    false, false, false,    // Sd=false (double-ended)
    1, 1,                   // T1=T2=swEndCondThroughAll
    0, 0,                   // D1,D2 ignored
    false, false, false, false, 0, 0,
    false, false, false, false,
    false, false, true,
    false, false, false,
    0, 0, false, false);
```

### Pattern B — Pocket/Slot (cut through known thickness only)
```csharp
FeatureCut4(
    true, false, false,     // Sd=true (single-ended)
    0, 0,                   // T1=swEndCondBlind
    0.010, 0,               // D1=10mm depth
    false, false, false, false, 0, 0,
    false, false, false, false,
    false, false, true,
    false, false, false,
    0, 0, false, false);
```

### Pattern C — Through Next (cut through just the next wall/surface)
```csharp
FeatureCut4(
    true, false, false,
    2, 0,                   // T1=swEndCondThroughNext
    0, 0,                   // D1 ignored
    ...);
```

---

## 5. Sketch Plane and Cut Direction

The **default cut direction is OPPOSITE the sketch normal** (i.e., into the material):
- Sketch on top face (normal = +Y): cut goes in **-Y** direction (downward)
- Sketch on bottom face (normal = -Y): cut goes in **+Y** direction (upward)
- Setting `Dir=true` reverses the default direction

**IMPORTANT**: If you sketch on the bottom face and use Through All, the cut goes UPWARD through the base, then continues through walls and anything above.

### For Predictable Results
1. Sketch on the face **closest to the material you want to remove**
2. Use **Blind** with the exact depth of the feature you want to cut through
3. Only use Through All when you genuinely want to cut through everything

---

## 6. Deletion Cascade Warning

When deleting a sketch that was originally used by a feature (even if the feature was already deleted), SolidWorks may cascade-delete dependent features built on faces in the same region.

### Safe Deletion Approach
1. Delete features **BEFORE** their sketches — not the other way around
2. Before deleting a dangling sketch, check if any features reference affected faces
3. If a cascade occurs, recreate the affected features

### Avoiding Dangling Sketches
When a `FeatureCut4` or `FeatureExtrusion3` call fails and you need to retry:
```csharp
// Always exit sketch mode first
if (swSketchMgr.ActiveSketch != null)
    swSketchMgr.InsertSketch(true);
// Then delete the failed sketch immediately before creating a new one
```

---

## 7. Verification Checklist

After creating any cut-extrude feature:
- [ ] Check return value is not null
- [ ] Visually verify the cut depth
- [ ] Confirm the cut did NOT penetrate features it shouldn't have
- [ ] Check for dangling sketches in the feature tree if you had to retry

**Key question after every cut**: "Did this cut go deeper than intended?"

### Common Symptoms of Wrong End Condition
| Symptom | Likely Cause |
|---------|-------------|
| Other features above/below are cut through | Through All when Blind was needed |
| Hole doesn't fully penetrate the part | Blind when Through All was needed |
| Cut goes away from material (no visible change) | Wrong direction (`Dir` parameter) |

---

## 8. Decision Matrix

| Scenario | End Condition | Sd | Depth |
|----------|--------------|-----|-------|
| Bolt hole through entire part | Through All Both | false | N/A |
| Pocket in one face only | Blind | true | exact thickness |
| Hole through one wall only | Through Next | true | N/A |
| Counterbore (specific depth) | Blind | true | bore depth |
| Slot through a plate | Blind | true | plate thickness |
| Window through a wall | Blind | true | wall thickness |

Generated At: 2026-04-13T07:33:57.169396