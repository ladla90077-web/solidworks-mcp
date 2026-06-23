---
description: Pull the feature tree of a specific assembly component (subpart) on demand, for parts beyond the auto-expansion cap.
---

# SolidWorks API: Assembly Subpart Extraction

Model state already expands assembly subpart feature trees automatically, up to a
fixed cap of 10 unique parts per call. Components beyond the cap still render their
name and location, only the feature details are withheld — the stub looks like
`↳ bracket.SLDPRT — C:\parts\bracket.SLDPRT [feature tree truncated; probe this with guide if required]`.
You only need the specific parts the task requires, not all of them.

## Preferred: the `subcomponent` option on get model state

Call `get_complete_model_state` with `subcomponent` set to the component instance
name shown on its `[Reference]` node (e.g. `b plate_pcs2b-1`). It returns that
component's referenced part/sub-assembly feature tree directly — no C# needed. A
sub-assembly target descends into its own children under the same caps. Per-feature
error info is not included for these subcomponent trees.

Drop to the `execute_csharp_code` recipe below only when you need something the tree
walk does not give you (custom properties, geometry, mates, etc.); the stub's path
tells you exactly which document to target.

## The bridge: feature node -> component -> referenced document

An assembly component is a top-level feature node whose `GetTypeName2()` is
`"Reference"`. To reach its part feature tree, cross the document boundary:

```csharp
// feat is a top-level Feature in the assembly
IComponent2 comp = feat.GetSpecificFeature2() as IComponent2;   // feature -> component
ModelDoc2 partDoc = comp.GetModelDoc2() as ModelDoc2;            // referenced part/sub-assembly
```

`GetModelDoc2()` returns null for suppressed, lightweight, or unloaded components.
Do not force-resolve them (that mutates the user's document) unless the user asks.

## Walk a named component's feature tree

```csharp
var result = new Dictionary<string, object>();
AssemblyDoc asm = (AssemblyDoc)swApp.ActiveDoc;

string target = "b plate_pcs2b-1";   // the component instance name from the model state
object[] comps = (object[])asm.GetComponents(true);   // top-level components

foreach (object o in comps)
{
    IComponent2 comp = o as IComponent2;
    if (comp == null || comp.Name2 != target) continue;

    ModelDoc2 partDoc = comp.GetModelDoc2() as ModelDoc2;
    if (partDoc == null) { result["error"] = "component not resolved"; break; }

    var feats = new List<string>();
    Feature f = (Feature)partDoc.FirstFeature();
    while (f != null) { feats.Add(f.Name + " [" + f.GetTypeName2() + "]"); f = (Feature)f.GetNextFeature(); }

    result["part"] = partDoc.GetTitle();
    result["config"] = comp.ReferencedConfiguration;
    result["features"] = feats;
    break;
}
return result;
```

## Notes

- The component instance name (`Name2`) matches the name shown on the `[Reference]`
  node in model state, e.g. `b plate_pcs2b-1`.
- A part instanced many times shares one part document, so its tree is identical
  across instances; expand it once.
- For a sub-assembly component, `GetModelDoc2()` returns another assembly; recurse
  with `comp.GetChildren()` to reach its components.
