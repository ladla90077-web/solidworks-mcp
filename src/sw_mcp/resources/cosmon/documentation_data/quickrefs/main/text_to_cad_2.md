---
description: "Guide for creating CAD models from natural language descriptions via the SolidWorks COM API, covering feature sequence planning, design intent analysis, face selection pitfalls, coordinate system awareness, and verification workflows."
keywords:
  - text to CAD
  - feature sequence
  - design intent
  - face selection
  - coordinate system
  - ModelToSketchTransform
  - sketch plane
  - verification
  - fully constrained sketch
---

# Creating CAD Models from Natural Language Descriptions

## 1. Planning the Feature Sequence

When a part is described in plain language, the user may or may not provide a feature breakdown or build sequence.

### Key Principles
1. **Analyze the full description** (and any pictures/drawings) and **plan a feature sequence** before writing any code
2. Each feature should be as simple as possible with emphasis on functional parameterization
3. Build with **fully constrained and defined sketches** — do not rely on equations or relations
4. Ask for confirmation at important stages if uncertain
5. Ensure the part is consistent as a solid with **no error-state features** after every step
6. Save after each important step
7. **Every word in the user's description matters** — follow it precisely

### If the User Provides a Sequence
Follow it as-is — they may anticipate dependencies between features that aren't immediately obvious.

---

## 2. Design Intent Analysis

Before building, determine the manufacturing intent:

- **Rotationally symmetric** → likely turned on a lathe → use revolve as the base feature
- **Prismatic with symmetry** → possibly cast or machined → use extrude with mirror/pattern
- **Identify primary datum planes** and build centered/aligned for symmetry where specified

### General Rules
- Do not over-rely on shortcuts or fancy features — keep it simple and parametric
- For holes, always sketch and extrude-cut from the face where the hole enters (simulating drilling)
- Use center rectangles and center-based geometry to maintain symmetry automatically

---

## 3. Feature Building Best Practices

For each feature:
- Create the sketch on the correct plane or face
- **Always verify sketch plane orientation** before drawing geometry
- Use center rectangles and center-based geometry for symmetry
- Keep sketches fully defined with dimensions and constraints
- Check for null return values after feature creation
- Always exit sketch mode after feature creation:

```csharp
if (sketchManager.ActiveSketch != null)
    sketchManager.InsertSketch(true);
```

---

## 4. CRITICAL: Always Verify Face Selection Before Sketching

**Problem**: When selecting a face for a new sketch, the selection can fail silently. If the code proceeds without a valid selection, SolidWorks may default to a standard plane, causing the sketch and feature to be misplaced.

**Root Causes of Silent Failure**:
- Target point lies at the boundary between multiple features
- Target point is on an internal face that is occluded or ambiguous
- The face has been split by overlapping feature footprints

**Solution**:
1. **Always check the boolean return value** of the face selection call
2. If selection returns false, **do not proceed** — choose a different point on the target face that is clearly unambiguous, away from feature boundaries and edges
3. For flat surfaces with features on top, select a point on an exposed area rather than the center where other features may split the face

```csharp
// BAD: Selecting at center where other features may split the face
bool sel = SelectByID2Reliable(ext, app, "", "FACE", 0, 0.01, 0, ...);

// GOOD: Selecting at an exposed area, away from feature footprints
bool sel = SelectByID2Reliable(ext, app, "", "FACE", 0.05, 0.01, 0, ...);

// MANDATORY: Check result before proceeding
if (!sel) {
    // Try alternative point or abort with error
}
```

---

## 5. Coordinate System Awareness

When working with sketches on different planes and faces:

- **Top Plane**: Sketch X = Model X, Sketch Y = Model **-Z** (often counter-intuitive)
- **Never assume coordinate mappings** — always use `ModelToSketchTransform` and its inverse
- When placing geometry at specific distances from edges or corners, **calculate positions in model space first**, then transform to sketch space
- For symmetric parts, use the origin as center of symmetry and calculate offsets from there

```csharp
MathTransform sketchToModel = sketch.ModelToSketchTransform.Inverse();
MathTransform modelToSketch = sketch.ModelToSketchTransform;

// Model space → Sketch space
MathPoint sketchPt = (MathPoint)modelPt.MultiplyTransform(modelToSketch);
```

---

## 6. Verification Workflow

After each major feature or group of features:

1. **Visually inspect** using screenshot analysis
2. Use sketch inspection tools to verify geometry, orientation, and positioning
3. Use feature inspection tools to verify parameters
4. Check the feature tree for error-state features
5. **Save** after each successful feature group

### When a Feature Fails
- First check that the underlying sketch geometry is correct
- Verify the sketch is on the correct plane/face
- Verify selections (edges, faces) are valid
- **Do not jump to a different approach without understanding the root cause**

---

## 7. Summary Checklist

### Before Each Feature
- [ ] Plan the feature and identify the sketch plane/face
- [ ] Verify face/plane selection succeeded (check boolean return)
- [ ] Verify sketch orientation matches expectations
- [ ] Calculate all coordinates in model space, then transform to sketch space

### During Feature Creation
- [ ] Check feature creation return value is not null
- [ ] Exit sketch mode if still active

### After Feature Creation
- [ ] Visually verify the result
- [ ] Save the model

### Key Principles
- Every word in the user's description matters — follow it precisely
- Keep features simple and parametric
- Fully constrain all sketches
- Verify at every step — never assume success

Generated At: 2026-04-13T07:36:53.720380