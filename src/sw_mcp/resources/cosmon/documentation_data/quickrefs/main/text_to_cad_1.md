---
description: "Guide for interpreting engineering drawings and creating stepped/L-shaped revolve profiles via the SolidWorks COM API, covering dimension extraction, profile vertex planning, centerline creation, and sketch plane selection."
keywords:
  - revolve
  - FeatureRevolve2
  - L-shaped profile
  - centerline
  - CreateCenterLine
  - axisymmetric
  - sketch plane
  - engineering drawing
  - cross section
  - unit conversion
---

# Creating Revolve Sketch Profiles from Engineering Drawings

## 1. Reading Dimensions from the Drawing

Before writing any code, extract ALL relevant dimensions and organize them into a table.

### Key Dimensions for a Stepped/Flanged Revolve
- Outer diameter (OD) of each step
- Thickness/height of each step
- Central hole diameter (if applicable)
- Any chamfers, tapers, or transitions between steps

### Tolerance Handling
- For modeling, use the **mean of tolerance limits** (e.g., 0.2750/0.2650 → use 0.2700)
- For critical fits, clarify with the user

### Unit Conversion
The SolidWorks API **always works in meters**. Define a conversion constant at the top of every script:
```csharp
double inToM = 0.0254;  // inches to meters
double mmToM = 0.001;   // millimeters to meters
```

### Cross-Referencing Views
Section views show critical height/depth dimensions. Cross-reference front view diameters with section view heights to build the full profile.

---

## 2. Planning the Revolve Profile

For an axisymmetric part with steps and a central hole, the revolve profile is drawn on one side of the axis of revolution.

### Profile Vertex Planning (axis along Y, radial along X)

For a two-step body with a central hole:
```
P1 (holeR, 0)        — bottom, inner edge
P2 (outerR1, 0)      — bottom, outer edge
P3 (outerR1, height1) — top of first step, outer edge
P4 (outerR2, height1) — step transition
P5 (outerR2, totalH)  — top of second step, outer edge
P6 (holeR, totalH)    — top, inner edge (hole)
Close back to P1
```

### Key Rules
- **ALL profile points must be on the POSITIVE X side** (right of centerline)
- The profile must be a **CLOSED loop** (last line connects back to first point)
- The centerline must be a **separate construction line** along the Y-axis
- Use `CreateCenterLine` (not `CreateLine`) for the revolve axis

---

## 3. Choosing the Sketch Plane

For axisymmetric parts revolved around the Y-axis:
- Use the **Right Plane** (or Front Plane) — these contain the Y-axis
- On the Right Plane: sketch X = radial direction, sketch Y = axial (height) direction

The centerline goes along the Y-axis at X=0. **Extend it slightly beyond the profile** for reliable axis detection:
```csharp
swSketchMgr.CreateCenterLine(0, -0.01, 0, 0, totalH + 0.01, 0);
```

**Do NOT use the Top Plane** for revolve profiles — its normal is along Y, which conflicts with the revolution axis.

---

## 4. Code Pattern

```csharp
// 1. Select plane
swExt.SelectByID2("Right Plane", "PLANE", 0, 0, 0, false, 0, null, 0);
swSketchMgr.InsertSketch(true);

// 2. Draw closed profile (connect vertices sequentially)
swSketchMgr.CreateLine(holeR, 0, 0,      outerR1, 0, 0);       // bottom
swSketchMgr.CreateLine(outerR1, 0, 0,    outerR1, height1, 0); // outer wall step 1
swSketchMgr.CreateLine(outerR1, height1, 0, outerR2, height1, 0); // step transition
swSketchMgr.CreateLine(outerR2, height1, 0, outerR2, totalH, 0);  // outer wall step 2
swSketchMgr.CreateLine(outerR2, totalH, 0,  holeR, totalH, 0);    // top
swSketchMgr.CreateLine(holeR, totalH, 0,    holeR, 0, 0);         // inner wall (hole)

// 3. Centerline for axis
swSketchMgr.CreateCenterLine(0, -0.01, 0, 0, totalH + 0.01, 0);

// 4. Create 360-degree revolve (uses active sketch)
Feature feat = (Feature)swFeatMgr.FeatureRevolve2(
    true, true, false, false, false, false,
    0, 0, 6.28318530718, 0,
    false, false, 0, 0, 0, 0, 0,
    true, false, true);

// 5. Safety: exit sketch if still active
if (swSketchMgr.ActiveSketch != null)
    swSketchMgr.InsertSketch(true);
```

---

## 5. Verification Checklist

After creating the revolve:
- [ ] Feature tree shows the Revolve feature (not just a sketch)
- [ ] Visually confirm proportions match the drawing
- [ ] Central hole goes all the way through (if applicable)
- [ ] Step heights and diameters look correct relative to each other

### Common Failures

| Symptom | Cause |
|---------|-------|
| Revolve returns null | Profile not closed |
| Revolve fails with no axis | Centerline missing or not a construction line |
| Invalid geometry error | Profile crosses the centerline (negative X) |
| Part oriented incorrectly | Sketch on wrong plane |

---

## 6. Handling More Complex Profiles

For parts with counterbores, chamfers, or additional steps, add more vertices to the profile.

### Counterbore (adds step at the hole entrance)
```
P1(holeR, 0) → P2(cboreR, 0) → P3(cboreR, cboreDepth) →
P4(holeR, cboreDepth) → ... continue up the body
```

### Chamfer on an Edge (replace sharp corner with angled line)
Instead of:
```
P5(outerR, totalH) → P6(holeR, totalH)
```
Use:
```
P5(outerR, totalH - chamfer) → P5a(outerR - chamfer, totalH) → P6(holeR, totalH)
```

### Best Practice
Always sketch the full cross-section on paper first, labeling all vertices with their (radial, axial) coordinates, then convert to meters in code.

Generated At: 2026-04-13T07:34:38.301746