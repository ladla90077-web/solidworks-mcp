---
description: "Guide for programmatically creating chamfer features via the SolidWorks COM API, documenting the critical pitfall of the legacy InsertFeatureChamfer method and the reliable modern CreateDefinition/CreateFeature workflow."
keywords:
  - chamfer
  - InsertFeatureChamfer
  - CreateDefinition
  - CreateFeature
  - swFmFillet
  - SimpleFilletFeatureData2
  - ConicTypeForCrossSectionProfile
  - swFeatureFilletConicRhoZeroChamfer
  - edge selection
  - asymmetric chamfer
---

# Chamfer Creation

## 1. CRITICAL: Do NOT Use InsertFeatureChamfer

**Problem**: `IFeatureManager::InsertFeatureChamfer` creates a chamfer feature that appears in the feature tree with correct parameters and edge selections, but does **NOT visually apply the geometry** to the model.

The feature shows no error (error code = 0), edges are correctly stored, and calling `EditRebuild3()`, `ForceRebuild3(true)`, or programmatically resubmitting via `ModifyDefinition` does NOT fix it. The only way to make it work is to manually open the feature in the UI and click OK — which is unacceptable for programmatic workflows.

**Root Cause**: `InsertFeatureChamfer` is a legacy method. The fillet/chamfer documentation explicitly states it is obsolete.

**Solution**: Always use the modern `CreateDefinition` / `CreateFeature` workflow with `ISimpleFilletFeatureData2`.

---

## 2. The Correct Approach: CreateDefinition + CreateFeature

Chamfers are created through the **fillet infrastructure** in SolidWorks. You use `swFmFillet` (not `swFmChamfer`) with `CreateDefinition`. The chamfer behavior is specified by setting the cross-section profile type.

### Steps
1. Create a feature data object: `CreateDefinition(swFmFillet)`
2. Initialize for chamfer type: `Initialize(swConstRadiusFillet)`
3. Set cross-section to chamfer: `ConicTypeForCrossSectionProfile = swFeatureFilletConicRhoZeroChamfer`
4. Create the feature: `CreateFeature(filletData)`

---

## 3. Enum Values Reference

### swFeatureNameID_e
- `swFmFillet` — Used for `CreateDefinition` (for BOTH fillets and chamfers)

### swSimpleFilletType_e
| Value | Name | Use |
|-------|------|-----|
| 0 | `swConstRadiusFillet` | Constant radius fillets and edge chamfers |
| 2 | `swFaceFillet` | Face fillets and face-face chamfers |
| 3 | `swFullRoundFillet` | Full round fillets |

### swFeatureFilletProfileType_e
| Value | Name | Use |
|-------|------|-----|
| 0 | `swFeatureFilletCircular` | Circular fillet (default) |
| 1 | `swFeatureFilletConicRho` | Conic rho fillet |
| 2 | `swFeatureFilletConicRadius` | Conic radius fillet |
| 3 | `swFeatureFilletConicRhoZeroChamfer` | **CHAMFER cross section** |

### Selection Marks
| Mark | Use |
|------|-----|
| 1 | Edges, faces, features, or loops (constant radius type) |
| 2 | Face Set 1 (face-face chamfer) |
| 4 | Face Set 2 (face-face chamfer) |

---

## 4. Equal Distance Edge Chamfer

```csharp
// Select edges with Mark = 1
swModel.ClearSelection2(true);
NexusSWHelpers.SelectByID2Reliable(swExt, swApp,
    "", "EDGE", mx1, my1, mz1, true, 1, null, 0);
NexusSWHelpers.SelectByID2Reliable(swExt, swApp,
    "", "EDGE", mx2, my2, mz2, true, 1, null, 0);

// Create chamfer using modern approach
SimpleFilletFeatureData2 filletData = (SimpleFilletFeatureData2)
    swFeatMgr.CreateDefinition((int)swFeatureNameID_e.swFmFillet);

filletData.Initialize((int)swSimpleFilletType_e.swConstRadiusFillet);

filletData.ConicTypeForCrossSectionProfile =
    (int)swFeatureFilletProfileType_e.swFeatureFilletConicRhoZeroChamfer;

filletData.DefaultRadius = 0.002; // 2mm chamfer distance

Feature chamferFeat = (Feature)swFeatMgr.CreateFeature(filletData);
```

---

## 5. Asymmetric (Distance-Distance) Chamfer

```csharp
SimpleFilletFeatureData2 filletData = (SimpleFilletFeatureData2)
    swFeatMgr.CreateDefinition((int)swFeatureNameID_e.swFmFillet);

filletData.Initialize((int)swSimpleFilletType_e.swConstRadiusFillet);

filletData.ConicTypeForCrossSectionProfile =
    (int)swFeatureFilletProfileType_e.swFeatureFilletConicRhoZeroChamfer;

// Enable asymmetric mode
filletData.AsymmetricFillet = true;
filletData.DefaultRadius = 0.002;    // Distance 1 = 2mm
filletData.DefaultDistance = 0.003;  // Distance 2 = 3mm

Feature chamferFeat = (Feature)swFeatMgr.CreateFeature(filletData);
```

---

## 6. Face-Face Chamfer (Offset Face Chamfer)

```csharp
// Select Face Set 1 with Mark = 2
NexusSWHelpers.SelectByID2Reliable(swExt, swApp,
    "", "FACE", fx1, fy1, fz1, false, 2, null, 0);
// Select Face Set 2 with Mark = 4
NexusSWHelpers.SelectByID2Reliable(swExt, swApp,
    "", "FACE", fx2, fy2, fz2, true, 4, null, 0);

SimpleFilletFeatureData2 filletData = (SimpleFilletFeatureData2)
    swFeatMgr.CreateDefinition((int)swFeatureNameID_e.swFmFillet);

filletData.Initialize((int)swSimpleFilletType_e.swFaceFillet);

filletData.ConicTypeForCrossSectionProfile =
    (int)swFeatureFilletProfileType_e.swFeatureFilletConicRhoZeroChamfer;

filletData.DefaultRadius = 0.002;

Feature chamferFeat = (Feature)swFeatMgr.CreateFeature(filletData);
```

---

## 7. Edge Selection Best Practices

1. Use `NexusSWHelpers.SelectByID2Reliable` for coordinate-based edge selection — it is view-independent and verifies the selection
2. Always use **Mark = 1** for edge selections in constant radius chamfers
3. Set **Append = true** for all selections after the first one
4. To programmatically find edges, iterate through `Body2.GetEdges()` and filter by:
   - Curve type (`IsLine` for straight edges)
   - Vertex positions (`GetStartVertex`/`GetEndVertex` → `GetPoint`)
   - Geometric criteria (vertical, horizontal, at specific coordinates)
5. Calculate edge **midpoints** for reliable selection coordinates:
```csharp
double mx = (p1[0] + p2[0]) / 2.0;
double my = (p1[1] + p2[1]) / 2.0;
double mz = (p1[2] + p2[2]) / 2.0;
```

---

## 8. Summary: Legacy vs Modern

| | Legacy (DO NOT USE) | Modern (ALWAYS USE) |
|---|---|---|
| Method | `InsertFeatureChamfer(...)` | `CreateDefinition` → `CreateFeature` |
| Geometry applied? | **No** — ghost feature | **Yes** — reliable |
| Rebuilding fixes it? | No | N/A (works first time) |
| Supports all types? | Limited | Equal distance, asymmetric, face-face |

Generated At: 2026-04-13T07:36:02.627624