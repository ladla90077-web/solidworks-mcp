---
description: Creating holes and slots using HoleWizard5 and AdvancedHole2 — parameters, enums, and working C# examples
keywords: [hole, hole wizard, HoleWizard5, AdvancedHole2, counterbore, countersink, tap, slot, drill, FeatureManager]
---

# Creating Holes in SolidWorks via the API

## Overview

There are two main methods for creating holes:

| Method | Use case |
|--------|----------|
| `FeatureManager.HoleWizard5` | Standard holes and slots (counterbore, countersink, straight, tap, pipe tap, slots) |
| `FeatureManager.AdvancedHole2` | Complex multi-element holes with stacked sections from both sides |

Both require a **face selection** before calling. All length parameters are in **meters**, all angles in **radians**.

---

## ⚠️ Known API Bug: `swWzdHole` + `swEndCondThroughAll`

**`swEndCondThroughAll` (1) silently returns `null` when used with `swWzdHole` (simple hole type = 2).**

This affects **only** simple/regular holes (`swWzdHole`). Countersinks, counterbores, and taps work correctly with `swEndCondThroughAll`.

**Workarounds for simple through-all holes:**

| Workaround | How |
|------------|-----|
| Use `swEndCondThroughAllBoth` (9) | Drop-in replacement — produces identical through-all geometry |
| Use `swEndCondBlind` (0) | Set depth larger than part thickness (e.g., `0.1m` for a `10mm` part) |

```csharp
// ❌ BROKEN — returns null for simple holes
swFeatMgr.HoleWizard5(
    (int)swWzdGeneralHoleTypes_e.swWzdHole, ...,
    (int)swEndConditions_e.swEndCondThroughAll, ...);  // NULL!

// ✅ WORKAROUND — use ThroughAllBoth instead
swFeatMgr.HoleWizard5(
    (int)swWzdGeneralHoleTypes_e.swWzdHole, ...,
    (int)swEndConditions_e.swEndCondThroughAllBoth, ...);  // Works!
```

`swEndCondThroughNext` (2) is also broken for `swWzdHole`. Other end conditions (`swEndCondBlind`, `swEndCondMidPlane`, `swEndCondThroughAllBoth`) work correctly.

---

## HoleWizard5

The primary method for creating standard holes and slots.

### Signature

```csharp
Feature HoleWizard5(
    int GenericHoleType,        // swWzdGeneralHoleTypes_e
    int StandardIndex,          // swWzdHoleStandards_e
    int FastenerTypeIndex,      // swWzdHoleStandardFastenerTypes_e
    string SSize,               // Size string, e.g. "M6", "#8", "1/16"
    short EndType,              // swEndConditions_e
    double Diameter,            // meters (0 if SSize determines it)
    double Depth,               // meters (ignored for through-all)
    double Length,              // meters — only used for slot types; use -1 for holes
    double Value1,              // \
    double Value2,              //  |
    double Value3,              //  |
    double Value4,              //  | Hole-type-specific params
    double Value5,              //  | (see tables below)
    double Value6,              //  |
    double Value7,              //  |
    double Value8,              //  |
    double Value9,              //  |
    double Value10,             //  |
    double Value11,             //  |
    double Value12,             // /
    string ThreadClass,         // "1B"/"2B"/"3B" for ANSI Inch taps; "" otherwise
    bool RevDir,                // Reverse direction
    bool FeatureScope,          // true = affect selected bodies only
    bool AutoSelect,            // true = auto-select intersecting bodies
    bool AssemblyFeatureScope,
    bool AutoSelectComponents,
    bool PropagateFeatureToParts
)
```

### Face Selection for Hole Placement

Use `SelectByID2("", "FACE", x, y, z, ...)` to select the face. The coordinates determine hole placement on the face.

**Multiple holes:** Call `HoleWizard5` in a loop — one face selection + one `HoleWizard5` call per hole location:

```csharp
for (int i = 0; i < holeCount; i++) {
    swModel.ClearSelection2(true);
    swExt.SelectByID2("", "FACE", holeX[i], faceY, holeZ[i], false, 0, null, 0);
    Feature hole = (Feature)swFeatMgr.HoleWizard5(...);
}
```

> **Note:** Selecting the same face at multiple coordinates before a single `HoleWizard5` call does **not** produce multiple holes — the face selections are deduplicated.

### Hole Type Enum (`swWzdGeneralHoleTypes_e`)

| Value | Name | Description |
|-------|------|-------------|
| 0 | `swWzdCounterBore` | Counterbore hole |
| 1 | `swWzdCounterSink` | Countersink hole |
| 2 | `swWzdHole` | Straight hole |
| 3 | `swWzdPipeTap` | Tapered pipe tap |
| 4 | `swWzdTap` | Straight tap |
| 5 | `swWzdLegacy` | Legacy (deprecated) |
| 6 | `swWzdCounterBoreSlot` | Counterbore slot |
| 7 | `swWzdCounterSinkSlot` | Countersink slot |
| 8 | `swWzdHoleSlot` | Straight slot |

### Standard Enum (`swWzdHoleStandards_e`)

| Value | Name |
|-------|------|
| 0 | `swStandardAnsiInch` |
| 1 | `swStandardAnsiMetric` |
| 4 | `swStandardDIN` |
| 8 | `swStandardISO` |
| 9 | `swStandardJIS` |
| 13 | `swStandardGB` |

Other values: BSI (2), DME (3), Hasco Metric (5), Helicoil Inch (6), Helicoil Metric (7), PCS (10), Progressive (11), Superior (12), KS (14), IS (15), AS (16), PEM Inch (17), PEM Metric (18).

### End Condition Enum (`swEndConditions_e`)

| Value | Name | Notes |
|-------|------|-------|
| 0 | `swEndCondBlind` | Specify depth |
| 1 | `swEndCondThroughAll` | ⚠️ Broken for `swWzdHole` — use 9 instead |
| 2 | `swEndCondThroughNext` | ⚠️ Broken for `swWzdHole` |
| 6 | `swEndCondMidPlane` | Mid plane |
| 9 | `swEndCondThroughAllBoth` | Through all, both directions — **use this for simple through-all holes** |
| 10 | `swEndCondUpToSelection` | Up to selected surface/vertex |

### Fastener Type Must Match Standard and Hole Type

The `FastenerTypeIndex` must be valid for both the `StandardIndex` and the `GenericHoleType`. Mismatches cause silent failure (returns null). Common valid combinations:

| Hole Type | Standard | Fastener Type | Value |
|-----------|----------|---------------|-------|
| `swWzdHole` | ANSI Metric (1) | DrillSizes | 39 |
| `swWzdHole` | ANSI Metric (1) | ScrewClearances | 40 |
| `swWzdHole` | ISO (8) | ISODrillSizes | 143 |
| `swWzdHole` | ISO (8) | ISOScrewClearances | 144 |
| `swWzdCounterSink` | ANSI Metric (1) | FlatHead82 | 36 |
| `swWzdCounterBore` | ANSI Metric (1) | SocketHeadCapScrew | 33 |
| `swWzdCounterBore` | ISO (8) | ISOHexCapScrew | 136 |

---

## Value1–Value12 by Hole Type

Set unused values to **-1** (SolidWorks ignores them).

### Regular Holes and Straight Slots (`swWzdHole`, `swWzdHoleSlot`)

| Param | Meaning |
|-------|---------|
| Value1 | Screw fit (`swWzdHoleScrewClearanceTypes_e`: 0=Close, 1=Normal, 2=Loose) |
| Value2 | Drill angle (radians); **must be -1 for ThroughAll/ThroughNext**; default 118° = 2.0595 rad |
| Value3 | Near countersink diameter |
| Value4 | Near countersink angle (radians) |
| Value5 | Far countersink diameter |
| Value6 | Far countersink angle (radians) |
| Value7 | Offset (only for `swEndCondOffsetFromSurface`) |
| Value8–12 | -1 (unused) |

### Counterbore (`swWzdCounterBore`, `swWzdCounterBoreSlot`)

| Param | Meaning |
|-------|---------|
| Value1 | Counterbore diameter |
| Value2 | Counterbore depth |
| Value3 | Head clearance |
| Value4 | Screw fit (`swWzdHoleScrewClearanceTypes_e`) |
| Value5 | Drill angle (radians) |
| Value6 | Near countersink diameter |
| Value7 | Near countersink angle (radians) |
| Value8 | Underhead countersink diameter |
| Value9 | Underhead countersink angle (radians) |
| Value10 | Far countersink diameter |
| Value11 | Far countersink angle (radians) |
| Value12 | Offset (if `swEndCondOffsetFromSurface`) |

### Countersink (`swWzdCounterSink`, `swWzdCounterSinkSlot`)

| Param | Meaning |
|-------|---------|
| Value1 | Near countersink diameter |
| Value2 | Near countersink angle (radians) |
| Value3 | Head clearance |
| Value4 | Screw fit |
| Value5 | Drill angle (radians) |
| Value6 | Far countersink diameter |
| Value7 | Far countersink angle (radians) |
| Value8 | Offset |
| Value9 | Head clearance type (`swWzdHoleCounterSinkHeadClearanceTypes_e`) |
| Value10–12 | -1 (unused) |

### Tap (`swWzdTap`)

| Param | Meaning |
|-------|---------|
| Value1 | Tap thread depth |
| Value2 | Near countersink diameter |
| Value3 | Near countersink angle (radians) |
| Value4 | Far countersink diameter |
| Value5 | Far countersink angle (radians) |
| Value6 | Drill angle (radians) |
| Value7 | Cosmetic thread type (`swWzdHoleCosmeticThreadTypes_e`) |
| Value8 | Thread end condition (`swWzdHoleThreadEndCondition_e`) |
| Value9 | Helicoil tap type (`swWzdHoleHcoilTapTypes_e`) |
| Value10 | Offset |
| Value11–12 | -1 (unused) |

### Tapered Tap / Pipe Tap (`swWzdPipeTap`)

| Param | Meaning |
|-------|---------|
| Value1 | Tap thread depth |
| Value2 | Near countersink diameter |
| Value3 | Near countersink angle (radians) |
| Value4 | Far countersink diameter |
| Value5 | Far countersink angle (radians) |
| Value6 | Drill angle (radians) |
| Value7 | Cosmetic thread type |
| Value8 | Offset |
| Value9–12 | -1 (unused) |

---

## Example: Simple M5 Through-All Holes on a Bolt Circle

```csharp
// Creates 5 M5 clearance holes in a circular pattern
double cx = -0.0304;  // disk center X (model space)
double cy = 0.01;     // top face Y
double cz = -0.02773; // disk center Z
double boltR = 0.024; // bolt circle radius

for (int i = 0; i < 5; i++) {
    double angle = i * 2.0 * Math.PI / 5.0;
    double hx = cx + boltR * Math.Cos(angle);
    double hz = cz + boltR * Math.Sin(angle);

    swModel.ClearSelection2(true);
    swExt.SelectByID2("", "FACE", hx, cy, hz, false, 0, null, 0);

    Feature hole = (Feature)swFeatMgr.HoleWizard5(
        (int)swWzdGeneralHoleTypes_e.swWzdHole,
        (int)swWzdHoleStandards_e.swStandardISO,
        144,    // swStandardISOScrewClearances
        "M5",
        (short)swEndConditions_e.swEndCondThroughAllBoth,  // NOT ThroughAll!
        0.0053, 0.0, -1,
        1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
        "", false, true, true, false, false, false);
}
```

## Example: Countersink Hole (ANSI Metric M2, Flat Head 82°)

```csharp
// Precondition: a planar face is selected
Feature swFeat = swFeatMgr.HoleWizard5(
    (int)swWzdGeneralHoleTypes_e.swWzdCounterSink,
    (int)swWzdHoleStandards_e.swStandardAnsiMetric,
    (int)swWzdHoleStandardFastenerTypes_e.swStandardAnsiMetricFlatHead82,
    "M2",
    (int)swEndConditions_e.swEndCondThroughAll,  // Works for countersinks
    0.0102, 0.010312189893273, 0,
    0.0044, 1.57079632679489, 0.000152189893272978, 0,
    -1, -1, -1, -1, 1, -1, -1, -1,
    "", false, true, true, true, true, false);
```

## Example: Counterbore Hole (ISO M6, Hex Cap Screw)

```csharp
// Precondition: a planar face is selected
Feature swFeat = swFeatMgr.HoleWizard5(
    (int)swWzdGeneralHoleTypes_e.swWzdCounterBore,
    (int)swWzdHoleStandards_e.swStandardISO,
    (int)swWzdHoleStandardFastenerTypes_e.swStandardISOHexCapScrew,
    "M6",
    (int)swEndConditions_e.swEndCondBlind,
    0.0066, 0.02, 0,
    0.014547, 0.004, 0.0, 1.0, 2.05948851735331,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    "", false, true, true, true, true, false);
```

---

## AdvancedHole2

For complex holes with stacked elements from both near and far sides.

### Signature

```csharp
Feature AdvancedHole2(
    object AdvancedHoleNearElementArray,  // DispatchWrapper[] of near-side elements
    object AdvancedHoleFarElementArray,   // DispatchWrapper[] of far-side elements
    bool UseBaselineDimensions,
    bool IsCustomCallout,
    bool IsDepthUptoTip,
    out object ResultArray               // per-element result codes
)
```

### Workflow

1. **Select faces** using `SelectByRay` — Mark=256 for near side, Mark=512 for far side.
2. **Create elements** via `ModelDocExtension.CreateAdvancedHoleElementData(type)`.
3. **Configure each element** (Size, Standard, FastenerType, Diameter, BlindDepth, EndCondition, Orientation).
4. **Wrap in DispatchWrapper arrays** and call `AdvancedHole2`.

---

## Important Gotchas

1. **Units**: All lengths in meters, all angles in radians. Common conversions:
   - inches to meters: `value * 25.4 / 1000.0`
   - degrees to radians: `value * Math.PI / 180.0`
   - Default drill angle: 118° = 2.0595 rad

2. **Face selection**: Use `SelectByID2("", "FACE", x, y, z, ...)` before calling `HoleWizard5`. The (x, y, z) coordinates determine hole placement.

3. **Length parameter**: Must be `-1` for non-slot holes. Only used for slot types (6, 7, 8).

4. **Fastener/Standard/Type mismatch**: The `FastenerTypeIndex` must be valid for both the chosen `StandardIndex` and `GenericHoleType`, or the call silently fails (returns null).

5. **`swEndCondThroughAll` bug**: Returns null for `swWzdHole`. Use `swEndCondThroughAllBoth` (9) instead.

6. **Multiple holes**: Loop with one `SelectByID2` + one `HoleWizard5` per hole. Multi-selecting the same face at different coordinates does not create multiple holes.

7. **Set unused Value params to -1**: SolidWorks ignores them safely.

8. **Scope flags for single-body parts**: Use `true, true, false, false, false`.

9. **Macro recorder issues**: The recorder sometimes gets tap hole parameters wrong and uses deprecated end-condition values (3, 4 instead of 10). Always verify recorded values.

10. **AdvancedHole2 is parts-only**: Does not work in assemblies.

11. **DispatchWrapper required**: C# requires wrapping `AdvancedHoleElementData` objects in `DispatchWrapper[]` arrays for COM interop.

12. **Accessing hole data after creation**: Call `Feature.GetDefinition()` to get a `WizardHoleFeatureData2` object. To modify geometry properties, call `AccessSelections()` first (this rolls back the feature), then `ReleaseSelectionAccess()` when done.
