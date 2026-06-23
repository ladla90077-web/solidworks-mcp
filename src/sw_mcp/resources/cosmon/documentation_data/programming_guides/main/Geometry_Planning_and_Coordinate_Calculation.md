---
description: 'CRITICAL: Calculate coordinates for sketches/features. Never guess coordinates.'
---

# SolidWorks API: Coordinate Systems and Transformations

## Fundamental Principles: "Zero Trust" Coordinates

When working with SolidWorks geometry, you are constantly moving between different "worlds" (coordinate systems). **Never assume** coordinates from one world are valid in another.

### The Golden Rule
**Treat Model Space (Global Coordinates) as the universal language.**
- **Sketch A to Sketch B?** Route through Model Space: `Sketch A -> Model -> Sketch B`
- **Sketch to Selection?** Route through Model Space: `Sketch -> Model -> Selection`
- **Math Calculation?** Perform all logic (angles, offsets, midpoints) in Model Space.

### The "Universal Translator" Pattern
Use this pattern whenever you need to move geometry between contexts (e.g., aligning a hole in `Sketch2` with a point in `Sketch1`).

```csharp
// 1. SETUP: Get the Transformations
MathTransform sourceToModel = sourceSketch.ModelToSketchTransform.Inverse();
MathTransform modelToTarget = targetSketch.ModelToSketchTransform;

// 2. SOURCE: Start with Local Point in Sketch A
MathPoint localPointA = (MathPoint)mathUtil.CreatePoint(new double[] { 0.05, 0.05, 0 }); 

// 3. WORLD: Transform to Model Space (The Universal Reference)
MathPoint worldPoint = (MathPoint)localPointA.MultiplyTransform(sourceToModel);
// Perform any geometric logic here (e.g., bisecting angles, finding midpoints)

// 4. TARGET: Transform to Target Sketch Space
MathPoint localPointB = (MathPoint)worldPoint.MultiplyTransform(modelToTarget);
double[] targetCoords = (double[])localPointB.ArrayData;
```

### Critical Warning: The "Standard Plane" Trap
Do not rely on intuition for standard planes. Their local coordinate systems are often rotated or flipped relative to the model. **Always use the transformation matrices.**
*   **Top Plane Sketch:** Sketch Y is often Model -Z.
*   **Points vs. Vectors:** Use `MathPoint` for location (affected by translation) and `MathVector` for direction (affected only by rotation/scale).

---

## Case Study: Calculating Coordinates from Sketch and Feature Data

### Problem Statement
Select the top face of a disc by calculating its coordinates from fundamental sketch and feature parameters.

### Complete Working Code with Explanations
This example demonstrates the "Zero Trust" workflow: Extract (Local) -> Transform (Global) -> Calculate -> Select.

```csharp
var result = new Dictionary<string, object>();

ModelDoc2 swModel = (ModelDoc2)swApp.ActiveDoc;
PartDoc swPart = (PartDoc)swModel;
MathUtility mathUtil = (MathUtility)swApp.GetMathUtility();

// --------------------------------------------------------------------------
// 1. Extract sketch geometry (Local Coordinates)
//    CRITICAL: Coordinates from GetCenterPoint() are relative to the sketch origin,
//    not the model origin.
// --------------------------------------------------------------------------
Feature sketchFeature = (Feature)swPart.FeatureByName("Sketch1");
Sketch sketch = (Sketch)sketchFeature.GetSpecificFeature2();
object[] segments = (object[])sketch.GetSketchSegments();
SketchArc arc = (SketchArc)segments[0]; // Assuming circle

double[] centerCoords = (double[])arc.GetCenterPoint();
double[] normalVec = (double[])arc.GetNormalVector();

// --------------------------------------------------------------------------
// 2. Transform to Model Space (Global Coordinates)
//    Use Inverse() because ModelToSketchTransform goes Model -> Sketch.
//    We need Sketch -> Model.
// --------------------------------------------------------------------------
MathTransform sketchToModel = (MathTransform)sketch.ModelToSketchTransform.Inverse();

// Transform POINT (Location) - Affected by translation
MathPoint mathSketchPoint = (MathPoint)mathUtil.CreatePoint(centerCoords);
MathPoint modelPoint = (MathPoint)mathSketchPoint.MultiplyTransform(sketchToModel);
double[] modelCoords = (double[])modelPoint.ArrayData;

// Transform VECTOR (Direction) - Affected ONLY by rotation/scale
MathVector mathNormal = (MathVector)mathUtil.CreateVector(normalVec);
MathVector modelNormal = (MathVector)mathNormal.MultiplyTransform(sketchToModel);
double[] modelNormalCoords = (double[])modelNormal.ArrayData;

// --------------------------------------------------------------------------
// 3. Get extrusion depth
//    Must use AccessSelections() before reading feature data.
// --------------------------------------------------------------------------
Feature extrudeFeature = (Feature)swPart.FeatureByName("Boss-Extrude1");
ExtrudeFeatureData2 extrudeData = (ExtrudeFeatureData2)extrudeFeature.GetDefinition();
extrudeData.AccessSelections(swModel, null);
double depth = extrudeData.GetDepth(true);
extrudeData.ReleaseSelectionAccess();

// --------------------------------------------------------------------------
// 4. Calculate top face center
//    Now safe to do math because all values are in Model Space.
// --------------------------------------------------------------------------
double topFaceCenterX = modelCoords[0] + modelNormalCoords[0] * depth;
double topFaceCenterY = modelCoords[1] + modelNormalCoords[1] * depth;
double topFaceCenterZ = modelCoords[2] + modelNormalCoords[2] * depth;

// --------------------------------------------------------------------------
// 5. Select the face
//    SelectByID2 uses Model Space coordinates.
// --------------------------------------------------------------------------
ModelDocExtension swModelExt = (ModelDocExtension)swModel.Extension;
swModel.ClearSelection2(true);
bool selected = swModelExt.SelectByID2("", "FACE", 
    topFaceCenterX, topFaceCenterY, topFaceCenterZ, 
    false, 0, null, 0);

result["selected"] = selected;
result["top_face_center"] = new double[] { topFaceCenterX, topFaceCenterY, topFaceCenterZ };
return result;
```

## Required Interfaces
- `IPartDoc`: `FeatureByName()`
- `ISketch`: `GetSketchSegments()`, `ModelToSketchTransform`
- `ISketchArc`: `GetCenterPoint()`, `GetRadius()`, `GetNormalVector()`
- `IExtrudeFeatureData2`: `GetDepth()`, `AccessSelections()`, `ReleaseSelectionAccess()`
- `IMathUtility`: `CreatePoint()`, `CreateVector()`
- `IMathTransform`: `Inverse()`, `MultiplyTransform()`
- `IModelDocExtension`: `SelectByID2()`
