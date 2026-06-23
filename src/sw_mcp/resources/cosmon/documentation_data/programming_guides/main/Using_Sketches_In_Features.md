---
description: Interaction between features and sketches (active sketch vs selection marks). Correct EditSketch patterns.
---

# SOLIDWORKS API: Sketch Selection and Feature Creation

There are essentially two ways in which any feature fetches information regarding a sketch:

1. It just uses the latest active sketch.
2. It uses a selection with a specific mark to select a specific sketch.

---

## Case 1: Active Sketch

Feature methods operate on whichever sketch is currently in edit mode (active).

### Subcase 1a: Creating a New Sketch

When you create sketch geometry, that sketch automatically becomes active.

**FeatureExtrusion3** - Creates an extruded boss/base from the active sketch.
**FeatureCut4** - Creates a cut extrusion from the active sketch.
**FeatureRevolve2** - Creates a revolved feature from the active sketch.
**FeatureSweep2** - Creates a swept feature from the active sketch.
**FeatureLoft2** - Creates a lofted feature from the active sketch.

```csharp
// Select plane (only establishes where to create sketch)
swModelDocExt.SelectByID2("Front Plane", "PLANE", 0, 0, 0, false, 0, null, 0);

// Create geometry (sketch becomes active automatically)
swSketchManager.CreateCircle(0, 0, 0, 0.03, 0, 0);

// Feature uses the active sketch (feature creation automatically exits sketch mode)
swFeature = swFeatureManager.FeatureCut4(...);

// ALWAYS check and conditionally exit sketch mode at the end
// InsertSketch is a toggle - it exits sketch mode when a sketch is active
if (swSketchManager.ActiveSketch != null)
{
    swSketchManager.InsertSketch(true);
}
```

### Subcase 1b: Editing an Existing Sketch

To make an existing sketch active, you must call EditSketch().

**EditSketch** - Puts a selected sketch into edit mode, making it the active sketch.

```csharp
// Select existing sketch
swModelDocExt.SelectByID2("Sketch1", "SKETCH", 0, 0, 0, false, 0, null, 0);

// Make it active (REQUIRED)
swModel.EditSketch();

// Feature uses the now-active sketch (feature creation automatically exits sketch mode)
swFeature = swFeatureManager.FeatureCut4(...);

// ALWAYS check and conditionally exit sketch mode at the end
// InsertSketch is a toggle - it exits sketch mode when a sketch is active
if (swSketchManager.ActiveSketch != null)
{
    swSketchManager.InsertSketch(true);
}
```

---

## Case 2: Selection with Marks

Some feature methods can use SelectByID2 with specific marks to identify sketch inputs.

**FeatureExtrusion3** - Documented to support selection marks for sketch, direction, and end conditions.

### Selection Marks (from FeatureExtrusion3 documentation)

| Mark | Purpose |
|------|---------|
| 0 | 2D sketch, 3D sketch |
| 4 | Sketch contours/segments |
| 16 | Direction reference (3D sketch) |
| 32 | Start condition reference |
| 1 | End condition reference |
| 8 | Bodies to affect |

```csharp
// 3D sketch example using selection marks
swModelDocExt.SelectByID2("3DSketch1", "SKETCH", 0, 0, 0, false, 0, null, 0);
swModelDocExt.SelectByID2("Edge1", "EDGE", 0, 0, 0, true, 16, null, 0); // Mark 16 = direction
swModelDocExt.SelectByID2("Face1", "FACE", 0, 0, 0, true, 1, null, 0);  // Mark 1 = end condition

swFeature = swFeatureManager.FeatureExtrusion3(...);
```

### Feature Definition Approach

**CreateDefinition** - Creates a feature data object that captures selections when CreateFeature is called.
**CreateFeature** - Creates the feature using the configured feature data object.

```csharp
// Make selections
swModelDocExt.SelectByID2("Sketch1", "SKETCH", 0, 0, 0, false, 4, null, 0);

// Create and configure feature data
swExtrudeData = swFeatureManager.CreateDefinition(swFmExtrusion);
swExtrudeData.SetEndCondition(...);

// Create feature (captures current selections)
swFeature = swFeatureManager.CreateFeature(swExtrudeData);
```

---

## Important Notes

**Method-specific behavior**: Different feature methods handle sketches differently. There is NO universal default:
- **Active sketch examples**: FeatureCut4, FeatureCut3, FeatureRevolve2, FeatureSweep2, FeatureLoft2 use Case 1 (active sketch)
- **Selection marks examples**: FeatureExtrusion3 documents support for selection marks (Case 2)
- You must determine which approach each specific method requires - they are not interchangeable.

**Selection vs Active**: Selecting a sketch with SelectByID2 does NOT make it active. You must call EditSketch() to activate it.

**Critical: Sketch must be active when feature is created**: For features that use the active sketch approach, the sketch MUST be active (in edit mode) at the moment the feature creation method is called. The feature creation method itself automatically exits sketch mode, so you do NOT need to call InsertSketch() before creating the feature. If you exit sketch mode before calling the feature method, the feature will not use that sketch.

**REQUIRED: Check and conditionally exit sketch mode**: After any code that manipulates or activates sketches, you MUST check if sketch edit mode is still active using `SketchManager.ActiveSketch` and conditionally exit if needed. This is critical defensive programming because:
- Feature creation may fail silently or unexpectedly, leaving you in sketch edit mode
- Other operations may fail if SOLIDWORKS is left in sketch edit mode
- The state transition is complex and error-prone

**Pattern to follow**: Always end sketch manipulation code with:
```csharp
if (swSketchManager.ActiveSketch != null)
{
    swSketchManager.InsertSketch(true);  // Toggle: exits sketch edit mode if active
}
```
This pattern ensures that `InsertSketch()` is only called when a sketch is active (to exit), not when no sketch is active (which would create a new sketch).

**InsertSketch is a toggle**: `InsertSketch(bool)` is a toggle function that can both enter and exit sketch edit mode:
- If no sketch is active: `InsertSketch(true)` creates a new sketch and enters edit mode (if a plane/face is selected)
- If a sketch is active: `InsertSketch(true)` exits sketch edit mode
- The function's behavior depends on the current state - it toggles between sketch edit mode and normal mode

**ActiveSketch property**: Use `SketchManager.ActiveSketch` to check if you're currently in sketch edit mode. This property returns the active sketch object if a sketch is in edit mode, or `null` if no sketch is active. This is the reliable way to detect sketch edit state. Always check `ActiveSketch` before calling `InsertSketch()` to ensure you're exiting (not entering) sketch mode.

**ClearSelection2**: Clearing selections does not clear the active sketch - the active sketch remains active.

---

## Quick Decision Guide

- **Creating new sketch** → Create geometry (sketch becomes active), call feature method (exits sketch automatically), **ALWAYS check `ActiveSketch` and conditionally exit**
- **Using existing sketch with active approach** → SelectByID2, EditSketch() (makes sketch active), call feature method (exits sketch automatically), **ALWAYS check `ActiveSketch` and conditionally exit**
- **Using existing sketch with selection marks** → SelectByID2 with appropriate marks, call feature method
- **Complex features** → Use CreateDefinition/CreateFeature with appropriate selections
- **Unsure which approach?** → Check method documentation or use inspection tools to explore

**Critical Requirements**:
1. When using the active sketch approach, the feature creation method MUST be called while the sketch is still active. The feature creation automatically exits sketch mode, so do NOT call InsertSketch() before feature creation.
2. **ALWAYS** end any code that manipulates or activates sketches with a conditional check: `if (swSketchManager.ActiveSketch != null) { swSketchManager.InsertSketch(true); }` to ensure you're not left in sketch edit mode.
