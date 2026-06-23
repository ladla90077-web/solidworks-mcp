---
description: Documentation for NexusSWHelpers, a set of helper functions made available to Nexus, that Nexus is obligated to use when necessary.
---

# Nexus SolidWorks Helpers

The `NexusSWHelpers` static class is **automatically available** in the `execute_csharp_code` environment. You do not need to load or inject it.

## SelectByID2Reliable

A view-independent, verification-based replacement for `SelectByID2`. **It was designed to match the signature of `SelectByID2` as closely as possible and can be used as a drop-in replacement.** The only difference is that it is a static method requiring explicit `swModelExt` and `swApp` arguments.

You must use this instead of `SelectByID2` for all coordinate-based selections of **Faces**, **Edges**, and **Vertices**.

**Syntax:**
```csharp
bool success = NexusSWHelpers.SelectByID2Reliable(
    swModelExt,              // IModelDocExtension
    swApp,                   // ISldWorks
    "",                      // Name (usually empty for coordinate selection)
    "FACE",                  // Type ("FACE", "EDGE", "VERTEX")
    x, y, z,                 // Coordinates (Meters, Model Space)
    false,                   // Append (true/false)
    0,                       // Mark
    null,                    // Callout
    0                        // SelectOption
);
```

**Why use it?**
Standard `SelectByID2` with coordinates relies on view-dependent ray tracing. It often fails or selects the wrong entity if the view is rotated or the point is occluded. `SelectByID2Reliable` casts rays from random directions and **verifies** the selected entity matches the target coordinates within 1 micrometer.

**Full Signature:**
```csharp
public static bool SelectByID2Reliable(
    IModelDocExtension swModelExt, ISldWorks swApp,
    string Name, string Type,
    double X, double Y, double Z,
    bool Append, int Mark, Callout Callout, int SelectOption,
    int maxAttempts = 10,              // Optional: default 10
    double tolerance = 1e-6,           // Optional: default 1 micrometer
    double minOffsetDistance = 0.001,  // Optional: default 1mm
    double maxOffsetDistance = 0.005,  // Optional: default 5mm
    double rayRadius = 1e-6            // Optional: default 1 micrometer
)
```

**Critical Requirements:**
1.  **Coordinates**: Must be in **Meters** and **Model Space**. If you have Sketch Space coordinates, use `ModelToSketchTransform.Inverse()` to convert them.
2.  **Type**: Must be `"FACE"`, `"EDGE"`, or `"VERTEX"`. Other types are delegated to the standard `SelectByID2`.

## GetClosestPointOnEntity

Calculates the closest point on an entity (Face, Edge, Vertex) to a target point. Used internally by `SelectByID2Reliable` but available for custom verification logic.

**Syntax:**
```csharp
// Returns MathPoint or null if entity type not supported
MathPoint pt = NexusSWHelpers.GetClosestPointOnEntity(
    selectedObj,    // Object (IFace2, IEdge, or IVertex)
    targetX, targetY, targetZ, // Target coordinates (Meters)
    mathUtil        // MathUtility instance
);
```

