---
description: Guide for creating rectangular box features (Boss-Extrude) via the SolidWorks COM API, covering plane selection based on extrusion axis, coordinate planning, stacking boxes on existing geometry, and the complete C# workflow.
keywords: [box, rectangular prism, extrude, Boss-Extrude, FeatureExtrusion3, CenterRectangle, sketch plane, coordinate transform, stacking, height axis, blind extrusion]
---

# Creating Extruded Boxes (Rectangular Prisms)

---

## 1. Core Concept

A box is a **sketch rectangle + blind extrusion**. The key decisions are:
1. **Which plane/face** to sketch on (determines extrusion direction)
2. **Which two dimensions** go in the sketch vs. which is the extrusion depth
3. **Where to center** the rectangle

## 2. Plane Selection Based on Height Axis

The extrusion direction is **normal to the sketch plane**. Choose the sketch plane so the extrusion aligns with the desired "height" axis:

| Height Axis | Sketch On     | Sketch Dims | Extrude Depth |
|-------------|---------------|-------------|---------------|
| **Z**       | Front Plane   | X × Y       | Z dimension   |
| **Y**       | Top Plane     | X × Z       | Y dimension   |
| **X**       | Right Plane   | Y × Z       | X dimension   |

**Default SolidWorks planes:**
- **Front Plane** → normal is +Z (XY sketch)
- **Top Plane** → normal is +Y (XZ sketch)
- **Right Plane** → normal is +X (YZ sketch)

## 3. Basic Box on a Reference Plane

```csharp
// === INPUTS ===
string planeName = "Front Plane";  // Choose based on height axis (see table above)
double sketchDim1 = 0.100;         // First sketch dimension (meters) e.g. X
double sketchDim2 = 0.050;         // Second sketch dimension (meters) e.g. Y
double extrudeDepth = 0.010;       // Extrusion depth (meters) e.g. Z

// === SELECT PLANE ===
ModelDoc2 swModel = (ModelDoc2)swApp.ActiveDoc;
swModel.Extension.SelectByID2(planeName, "PLANE", 0, 0, 0, false, 0, null, 0);

// === CREATE SKETCH ===
swModel.SketchManager.InsertSketch(true);
swModel.SketchManager.CreateCenterRectangle(
    0, 0, 0,                           // Center point (sketch coords)
    sketchDim1 / 2.0, sketchDim2 / 2.0, 0  // Corner point (half-widths)
);

// === EXTRUDE ===
// Do NOT close the sketch first: FeatureExtrusion3 consumes the active sketch
// and exits sketch mode itself.
var extFeat = (Feature)swModel.FeatureManager.FeatureExtrusion3(
    true, false, false,   // sd (single direction), flip, dir2
    0, 0,                 // endCond1=Blind(0), endCond2=Blind(0)
    extrudeDepth, 0,      // depth1, depth2
    false, false,         // draftOn1, draftOn2
    false, false,         // draftOutward1, draftOutward2
    0, 0,                 // draftAngle1, draftAngle2
    false, false,         // offsetReverse1, offsetReverse2
    false, false,         // translateSurface1, translateSurface2
    true, false, false,   // merge, useFeatScope, useAutoSelect
    0, 0,                 // startCond1, startCond2
    false                 // flipStartDir
);
```

## 4. Stacking a Box on an Existing Face

When placing a box on top of an existing body:

### Step A: Determine the target face coordinates
The face to sketch on is at the **end of the previous extrusion**. For a box centered at origin with height along Z:
- Top face Z = sum of all previous Z extrusions (e.g., 0.010m for a 10mm box)
- The face center is at `(0, 0, Z_top)` in model space

### Step B: Select the face and sketch on it
```csharp
// Select the top face using a point ON the face
swModel.ClearSelection2(true);
swModel.Extension.SelectByID2("", "FACE", 0, 0, 0.010, false, 0, null, 0);

// Sketch on the selected face
swModel.SketchManager.InsertSketch(true);
```

### Step C: Sketch coordinates on a planar face
When sketching on a **planar face parallel to a reference plane**, the sketch coordinate system typically aligns with the model axes. For a face parallel to Front Plane (XY):
- Sketch X → Model X
- Sketch Y → Model Y
- Origin of sketch → projected model origin onto the face

So a centered rectangle at `(0, 0, 0)` in sketch coords will be centered at the model origin (projected onto the face). This is usually what you want for "centrally located".

```csharp
// Centered 50x20mm rectangle on face
swModel.SketchManager.CreateCenterRectangle(0, 0, 0, 0.025, 0.010, 0);
```

### Step D: Extrude (same as basic box)
The extrusion goes along the face normal (outward from the body), so the new box stacks on top.

## 5. Non-Centered / Offset Boxes

For a box NOT centered at origin, adjust the `CreateCenterRectangle` center point:

```csharp
// Box centered at (30mm, 10mm) in sketch coordinates
double cx = 0.030;  // center X offset
double cy = 0.010;  // center Y offset
swModel.SketchManager.CreateCenterRectangle(
    cx, cy, 0,
    cx + sketchDim1/2.0, cy + sketchDim2/2.0, 0
);
```

Alternatively, use `CreateCornerRectangle` for explicit corner-to-corner placement:
```csharp
swModel.SketchManager.CreateCornerRectangle(x1, y1, 0, x2, y2, 0);
```

## 6. Dimension Mapping Checklist

Given user input like "AxBxC where height is along [axis]":
1. **Identify height axis** → pick sketch plane from table in Section 2
2. **Map A, B, C to sketch dims and depth**:
   - If "100x50x10, height along Z": sketch = 100×50 (X×Y on Front Plane), depth = 10
   - If "100x50x10, height along Y": sketch = 100×10 (X×Z on Top Plane), depth = 50
3. **Convert mm to meters** (API uses meters): divide by 1000
4. **Center vs offset**: default to centered at origin unless specified otherwise

## 7. Common Pitfalls

- **Units**: SolidWorks API uses **meters**. Always convert mm → m by dividing by 1000.
- **Sketch plane confusion**: The extrusion goes along the plane **normal**, not along any sketch axis.
- **Face selection for stacking**: Use `SelectByID2("", "FACE", x, y, z, ...)` with a point that lies ON the target face. A point at the face center is safest.
- **Merge bodies**: Set `merge=true` in FeatureExtrusion3 (parameter 19) to merge the new box with existing solid body. Set `false` for separate bodies.
- **Sketch transform on non-standard faces**: For faces not parallel to reference planes, always check `ModelToSketchTransform` to map model coordinates to sketch coordinates. For standard axis-aligned faces, sketch coords typically align with model coords.
- **Do not close the sketch before extruding**: `FeatureExtrusion3` consumes the active sketch and exits sketch mode itself. Draw the rectangle, then call `FeatureExtrusion3` directly — no second `InsertSketch(true)`, no re-selection.

Generated At: 2026-04-22T23:20:28.186243