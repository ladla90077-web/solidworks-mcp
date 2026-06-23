---
description: "Guide for defeaturing complex CAD assemblies for thermal FEA, covering component suppression, fillet removal, and thermal equivalent block creation with lessons learned from practical application."
keywords:
  - defeaturing
  - thermal FEA
  - simplification
  - fillet removal
  - thermal equivalent
  - bounding box
  - suppression
  - DeleteFace
  - imported STEP
  - mesh reduction
---

# Defeaturing Complex Assemblies for Thermal FEA

## Overview

This guide covers three defeaturing techniques for preparing complex assemblies (especially imported STEP files) for thermal and thermal-structural finite element analysis:

1. **Suppressing thermally insignificant components** (biggest impact)
2. **Removing small fillets** from housing/shell parts
3. **Creating thermal equivalent blocks** to replace suppressed high-detail components

---

## Principle 1: Categorize Before You Cut

Before suppressing anything, inventory every component with body count, face count, and edge count. Then classify each by thermal role:

| Thermal Role | Action | Examples |
|---|---|---|
| Heat sources | Replace with simplified block | IC packages, processors |
| Primary conduction paths | **Keep** | PCB boards, thermal pads |
| Convection surfaces | **Keep**, simplify fillets | Enclosure shells |
| Thermal interface materials | **Keep** — these are critical | Thermal gels, thermal greases |
| Metal conduction elements | Keep | Copper foils, heat spreaders, shields |
| Cosmetic/assembly detail | **Suppress** | Snap clips, RFID tags, logos |
| Complex multi-body parts | **Replace** with simplified block | SMD component arrays, pin-detail connectors |
| Gaskets and foams | Usually suppress | Adhesive layers, sealing foams |

**Lesson learned**: Thermal gels and interface materials are easy to overlook but are critical for accurate thermal simulation. Always verify they are retained.

---

## Principle 2: Suppress in Priority Order by Complexity Impact

Suppression is the highest-ROI defeaturing step. Prioritize by body/face count:

1. **Multi-body parts** (hundreds of bodies in one component) — single biggest win
2. **High-face-count connectors** with pin-level detail
3. **Small thermal-mass items** (EMI absorbers, adhesive films)
4. **Non-thermal components** (RFID tags, labels, cosmetic gaskets)

### Code Pattern
```csharp
Component2.SetSuppression2((int)swComponentSuppressionState_e.swComponentSuppressed);
```

### Key Notes
- Works reliably on deeply nested sub-assembly components
- Suppressed components return null from `GetModelDoc2()` — account for this in inventory code
- Some components may already be suppressed in the imported STEP

---

## Principle 3: Fillet Removal — Open Part Directly, Not In Assembly

`InsertDeleteFace` is a **part-level operation only**. You must activate the part document directly.

### Identifying Fillet Faces
Fillets on imported bodies appear as cylindrical (and sometimes toroidal) surface faces. Classify faces by surface type:

```csharp
Surface surf = (Surface)face.GetSurface();
if (surf.IsCylinder()) {
    double radius = ((double[])surf.CylinderParams)[6]; // meters
    if (radius < threshold) { /* select for deletion */ }
}
```

**API Gotcha**: `IsBSplineSurface()` does NOT exist on the Surface interface. After checking `IsPlane()`, `IsCylinder()`, `IsTorus()`, `IsSphere()`, `IsCone()`, anything remaining is a B-spline surface — use process of elimination.

### Removing Fillets
```csharp
// Must work on part document, not assembly
ModelDoc2 partDoc = (ModelDoc2)swApp.ActivateDoc2(partPath, true, ref errors);
// ... select small cylindrical faces ...
((ModelDocExtension)partDoc.Extension).InsertDeleteFace(2); // swFaceDelete_Fill = 2
```

### Enum Reference
| swFaceDeleteOption_e | Value | Use |
|---|---|---|
| swFaceDelete_Default | 0 | Delete only |
| swFaceDelete_Patch | 1 | Patch with surface |
| swFaceDelete_Fill | 2 | **Best for fillets** — fills gap |
| swFaceDelete_FillWithTangent | 3 | Fill maintaining tangency |

### Lessons Learned
- **Threshold of ~2mm radius** captures most cosmetic edge breaks without removing structural rounds
- **Impact may be modest**: Removing hundreds of tiny (0.1–0.2mm) fillet faces may only reduce face count by ~5-10%. The visual/mesh impact is less dramatic than suppressing whole components
- **The real complexity on housings is internal features** (bosses, clips, ribs, snap-fits) — fillets are secondary
- Consider also targeting toroidal faces: `surf.IsTorus()` with minor radius from `surf.TorusParams[7]`

---

## Principle 4: Thermal Equivalent Blocks — Bounding Box Pitfalls

### The Workflow
1. Capture bounding boxes of components to be replaced (before or by temporarily unsuppressing)
2. Create simple extruded rectangle parts matching the bounding box
3. Insert into assembly and position with explicit transforms

### CRITICAL: Bounding Box Inflation from Sibling Components

**The Error**: When a sub-assembly contains mixed components (e.g., a PCBA sub-assembly containing both an SMD array AND connectors), the bounding box of the SMD part may extend into the connector region because some SMD components physically sit near the connectors.

**The Consequence**: A thermal block sized to this inflated bounding box will overlap with an adjacent thermal block (e.g., the connector replacement block), creating intersecting geometry.

**The Fix**:
- After computing bounding boxes for ALL replacement blocks, **cross-check for overlaps**
- Trim any overlapping block to stop at the boundary of its neighbor
- Use the **actual PCB board extent** as a more reliable spatial reference than the component envelope of mounted parts
- When in doubt, make the block slightly smaller — the user can adjust

### CRITICAL: AddComponent5 Positioning Is Unreliable

**The Error**: Passing coordinates to `AssemblyDoc.AddComponent5(path, ..., tx, ty, tz)` does NOT guarantee the component will be placed at those coordinates. SolidWorks may auto-position it elsewhere.

**The Fix**: ALWAYS set `Component2.Transform2` explicitly after insertion:

```csharp
Component2 comp = (Component2)swAsm.AddComponent5(path, 0, "", false, "", 0, 0, 0);
// Don't trust the position above — set it explicitly:
double[] xformData = new double[] {
    1, 0, 0,  0, 1, 0,  0, 0, 1,  // identity rotation
    tx, ty, tz,                      // desired translation (meters)
    1,  0, 0, 0                      // scale + unused
};
comp.Transform2 = (MathTransform)mathUtil.CreateTransform(xformData);
```

### Sketch Strategy for Blocks
Draw the rectangle sketch at the **correct XY position in part space** (matching the target assembly-space XY center). Then only a Z-translation is needed when positioning in the assembly. This reduces the degrees of freedom for positioning errors.

### User Adjustment Is Expected
Even with correct bounding box data, thermal blocks typically need manual fine-tuning for:
- Ensuring thermal contact with adjacent surfaces (gels, PCB, housing walls)
- Avoiding interference with internal housing features
- Adjusting based on domain knowledge of actual heat source locations within the component envelope

**Always present the blocks as a starting point and invite the user to verify/adjust positioning.**

---

## Principle 5: Verification After Defeaturing

### Automated Checks
1. Count total faces/edges across all active components — confirm meaningful reduction
2. Verify no thermal blocks overlap (compare bounding box extents)
3. Confirm all thermal interface materials still active
4. Rebuild assembly without errors

### Visual Checks
- Thermal blocks visible and contained within housing cavity
- Blocks don't protrude unexpectedly through housing walls
- No large gaps where thermal contact is expected
- HDMI/connector blocks properly extend outside housing where applicable

### Typical Results to Expect
| Technique | Face Reduction | Effort |
|---|---|---|
| Suppress multi-body components | **60-80%** | Low |
| Suppress detailed connectors | 10-20% | Low |
| Remove small fillets (<2mm) | 5-10% | Medium |
| Total with thermal blocks added | Net 70-90% reduction | Medium |

---

## API Quick Reference

| Function | Purpose |
|---|---|
| `Component2.SetSuppression2()` | Suppress/unsuppress |
| `Component2.GetBox(false, false)` | Bounding box in assembly space (meters) |
| `Component2.Transform2` | Get/set position transform |
| `Surface.IsCylinder()` | Identify fillet faces |
| `Surface.CylinderParams[6]` | Cylinder radius (meters) |
| `Surface.IsTorus()` / `TorusParams[7]` | Toroidal fillet faces / minor radius |
| `IModelDocExtension.InsertDeleteFace(2)` | Remove faces with fill |
| `AssemblyDoc.AddComponent5()` | Insert part into assembly |
| `MathUtility.CreateTransform()` | Create positioning transform |
| `swApp.ActivateDoc2()` | Switch between open documents |
| `PartDoc.GetBodies2(swSolidBody, true)` | Get solid bodies from part |
| `Body2.GetFaces()` | Get all faces on a body |

Generated At: 2026-04-13T07:27:15.465437