---
description: Working with user selections via save_last_user_selection tool and selection sets in code
---

# Handling User Selections and Selection Sets

## Key Concept: Selection Sets vs Selection Marks

**Selection sets** store *what* is selected (the entities), but NOT the marks. When you restore a selection set with `Select()`, all items are selected with **no mark (mark = 0)**. If a feature requires specific marks, you must assign them after restoration.

---

## How Do I Reinstate a Selection Set?

To make a selection set the active selection:

```csharp
FeatureManager featMgr = swModel.FeatureManager;
ISelectionSetFolder folder = featMgr.GetSelectionSetFolder() as ISelectionSetFolder;

ISelectionSet selSet = folder.GetSelectionSetByName("Nexus_EdgesForFillet") as ISelectionSet;
if (selSet == null) {
    result["error"] = "Selection set not found";
    return result;
}

swModel.ClearSelection2(true);  // Clear current selection first
selSet.Select();                // Items are now selected (all with mark 0)
```

After `Select()`, the items are the active selection and can be accessed via `ISelectionMgr`.

**Gotcha**: When you call `Select()` on a selection set, sometimes the selection set node itself (`swSelSELECTIONSETNODE`, type_code 259) gets included as the first selected item. This behavior is unreliable - it happens sometimes but not always. **Always filter it out** when iterating:

```csharp
for (int i = 1; i <= count; i++) {
    int typeCode = selMgr.GetSelectedObjectType3(i, -1);
    if (typeCode == (int)swSelectType_e.swSelSELECTIONSETNODE) {
        continue;  // Skip the selection set node itself
    }
    // Process actual selected items...
}
```

**Don't do this** - directly casting the first item without checking type:
```csharp
// WRONG - assumes index 1 is your face, but it might be the selection set node!
// face will return null here if the first item is the selection set node
IFace2 face = (IFace2)selMgr.GetSelectedObject6(1, -1);
```

---

## How Do I Assign Marks to a Restored Selection Set?

After restoring a selection set, use `SetSelectedObjectMark` to assign marks:

```csharp
// First restore the selection set
swModel.ClearSelection2(true);  // Clear current selection first
selSet.Select();

ISelectionMgr selMgr = (ISelectionMgr)swModel.SelectionManager;
int count = selMgr.GetSelectedObjectCount2(-1);

// Assign mark 4 to all items (e.g., for sketch contours)
for (int i = 1; i <= count; i++) {
    int typeCode = selMgr.GetSelectedObjectType3(i, -1);
    if (typeCode == (int)swSelectType_e.swSelSELECTIONSETNODE) {
        continue;  // Skip the selection set node itself
    }
    selMgr.SetSelectedObjectMark(i, 4, (int)swSelectionMarkAction_e.swSelectionMarkSet);
}
```

**Mark action values:**
- `swSelectionMarkSet` (0) - Set the mark to the specified value
- `swSelectionMarkAppend` (1) - Add to existing mark (OR operation)
- `swSelectionMarkSubtract` (2) - Remove from existing mark

---

## How Do I Select Specific Items with Different Marks?

If different items need different marks (e.g., profile vs path for sweep):

```csharp
selSet.Select();

ISelectionMgr selMgr = (ISelectionMgr)swModel.SelectionManager;
int count = selMgr.GetSelectedObjectCount2(-1);

for (int i = 1; i <= count; i++) {
    int typeCode = selMgr.GetSelectedObjectType3(i, -1);
    
    // Skip the selection set node itself
    if (typeCode == (int)swSelectType_e.swSelSELECTIONSETNODE) {
        continue;
    }
    
    // Assign different marks based on type
    if ((swSelectType_e)typeCode == swSelectType_e.swSelSKETCHES) {
        // Mark 1 for profile sketch
        selMgr.SetSelectedObjectMark(i, 1, (int)swSelectionMarkAction_e.swSelectionMarkSet);
    } else if ((swSelectType_e)typeCode == swSelectType_e.swSelEDGES) {
        // Mark 4 for path
        selMgr.SetSelectedObjectMark(i, 4, (int)swSelectionMarkAction_e.swSelectionMarkSet);
    }
}
```

---

## How Do I Work with User Selections?

When the user selects geometry and sends a message, you see two things:
1. The **model state** (feature tree or diff)
2. A **separate "Selected items" section** - listing what the user currently has selected

Example of what you see:
```
## Current SolidWorks Model State
Document: Part1
Features:
    - Boss-Extrude1 [Boss-Extrude]
    ...

Selected items (3):
  [Face] Planar face of Boss-Extrude1 (2500.00mm²)
  [Edge] Circular edge of Fillet1 (15.71mm)
  [Edge] Linear edge of Boss-Extrude1 (50.00mm)
```

Behind the scenes, this selection is also saved to `Nexus_Last_Selection`. **Do NOT access `Nexus_Last_Selection` directly.**

**Workflow:**
1. Call `save_last_user_selection(new_name="EdgesForFillet", reasoning="...")` 
2. This renames it to `Nexus_EdgesForFillet` (persistent, won't be overwritten)
3. Use that named selection set in code (see above)

---

## Common Selection Types Reference

| Type | swSelectType_e | Cast To |
|------|----------------|---------|
| Face | `swSelFACES` | `IFace2` |
| Edge | `swSelEDGES` | `IEdge` |
| Vertex | `swSelVERTICES` | `IVertex` |
| Feature | `swSelBODYFEATURES` | `IFeature` |
| Sketch | `swSelSKETCHES` | `IFeature` |
| Plane | `swSelDATUMPLANES` | `IFeature` |
| Component | `swSelCOMPONENTS` | `IComponent2` |

---

## Reading Items from the Active Selection

```csharp
ISelectionMgr selMgr = (ISelectionMgr)swModel.SelectionManager;
int count = selMgr.GetSelectedObjectCount2(-1);  // -1 = all marks

for (int i = 1; i <= count; i++) {  // 1-based index!
    int typeCode = selMgr.GetSelectedObjectType3(i, -1);
    
    // If reading from a restored selection set, skip the selection set node
    if (typeCode == (int)swSelectType_e.swSelSELECTIONSETNODE) {
        continue;
    }
    
    int mark = selMgr.GetSelectedObjectMark(i);
    object selObj = selMgr.GetSelectedObject6(i, -1);
    
    // Cast based on typeCode (see table above)
}
```
