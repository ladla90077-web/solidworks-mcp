---
description: Dimension a detail view — run IMA4 with DuplicateDimensions on, then dedup across the detail and its parent (delete one copy of each shared dim, from whichever view reads worse) and drop off-view dims. If the detail is still under-dimensioned, dimension by hand — see manual-dimensioning.md.
---

# Dimensioning a Detail View

> Import model dims with duplicates on, then dedup across the detail and its parent and drop anything off the detail's crop. It's a dedup, not a move — both views already hold their own copy, so *moving* one would stack a duplicate. If the detail ends up under-dimensioned, dimension by hand via `manual-dimensioning.md`.

## Recipe

1. **Insert** — `InsertModelAnnotations4` on the detail and its parent with `DuplicateDimensions = true`, so a shared dim lands on both.
2. **Dedup + clean** — for each dim on both views (same `FullName`), delete one copy (parent or detail, whichever reads worse — feature close-ups belong on the detail, overall/locating dims on the parent); also delete any detail dim whose geometry falls off the detail outline. **"Move a dim to the detail" = delete-from-parent-then-import, not import-then-delete** — see [Gotcha: a model dimension lives on exactly ONE view](#gotcha-a-model-dimension-lives-on-exactly-one-view--duplicate-wont-clone-an-already-placed-dim). Get the order backwards and the dim is lost.
3. **Fall back** — if the detail is still under-dimensioned (no model dims to import, or everything was off-view), dimension from scratch — see `manual-dimensioning.md`.

## How to

```csharp
// 1. Insert with duplicates on (run on the detail and on the parent).
swExt.SelectByID2(view.GetName2(), "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
swDraw.InsertModelAnnotations4(
    0, 32768 | 524288,   // entire model; marked | not-marked for drawing
    false,               // AllViews
    true,                // DuplicateDimensions = TRUE — allow cross-view copies
    false, false, false, false);

// 2. Dedup + drop off-view. This keeps the PARENT's copy and deletes the detail's;
//    flip it (collect detail names, walk the parent) to keep the detail's instead.
var parentNames = new HashSet<string>();
for (var pd = (DisplayDimension)parentView.GetFirstDisplayDimension5(); pd != null; pd = (DisplayDimension)pd.GetNext5())
    try { parentNames.Add(((Dimension)pd.GetDimension()).FullName); } catch { }

double[] box = (double[])detailView.GetOutline();   // [xMin, yMin, xMax, yMax] sheet meters
double pad = 0.005;
MathTransform m2v = detailView.ModelToViewTransform;
MathUtility mu = (MathUtility)swApp.GetMathUtility();

var dd = (DisplayDimension)detailView.GetFirstDisplayDimension5();
while (dd != null)
{
    var next = (DisplayDimension)dd.GetNext5();        // capture BEFORE deleting
    var d = (Dimension)dd.GetDimension();
    bool drop = false;

    try { if (parentNames.Contains(d.FullName)) drop = true; } catch { }   // cross-view duplicate

    if (!drop)   // off-view: a reference point projects outside the detail outline
    {
        bool got = false;
        try {
            foreach (object rp in (object[])d.ReferencePoints ?? Array.Empty<object>()) {
                if (rp == null) continue;
                got = true;
                double[] s = (double[])((MathPoint)((MathPoint)mu.CreatePoint(
                    (double[])((MathPoint)rp).ArrayData)).MultiplyTransform(m2v)).ArrayData;
                if (s[0] < box[0]-pad || s[0] > box[2]+pad || s[1] < box[1]-pad || s[1] > box[3]+pad) { drop = true; break; }
            }
        } catch { got = false; }   // ReferencePoints throws on some radial/Ø, chamfer, thread dims
        if (!got) {                // fallback: test the label position instead
            double[] p = (double[])((Annotation)dd.GetAnnotation()).GetPosition();
            drop = p[0] < box[0]-0.03 || p[0] > box[2]+0.03 || p[1] < box[1]-0.03 || p[1] > box[3]+0.03;
        }
    }

    if (drop) {
        swModel.ClearSelection2(true);
        ((Annotation)dd.GetAnnotation()).Select3(false, null);
        swModel.Extension.DeleteSelection2((int)swDeleteSelectionOptions_e.swDelete_Absorbed);
    }
    dd = next;
}
swModel.EditRebuild3();
// Then auto-arrange — see dimensioning-simple.md → "How to: arrange dimensions (AutoArrange)".
```

## Gotcha: a model dimension lives on exactly ONE view — "duplicate" won't clone an already-placed dim

`DuplicateDimensions = true` on `InsertModelAnnotations4` only duplicates **unconsumed** model dims. A model dimension is owned by a single drawing view: once the Front view has projected a given model dim (say `D2@Sketch2`), that dim is consumed. Re-running the import on the detail view returns nothing for it — the detail gets no copy even though the dim plainly exists in the model.

### The symptom

- Imported into Detail Z with `DuplicateDimensions = true` → nothing kept in the detail, nothing deleted from it. The detail got no dims.
- The dedup step then deleted the width copy from Front.
- Net: the dim was deleted from Front and never appeared in the detail — lost entirely.

### The rule

To **move** a model dim from view A to view B, **free it first**: delete it from A, *then* import into B. You cannot "copy then delete the original" — there is no copy. Reverse the order from what feels natural.

### Correct sequence (move a groove-width dim Front → Detail Z)

1. **Delete the dim from the parent view** — find the `DisplayDimension` by `FullName` (form `"<dimName>@<sketch>@<model>"`, e.g. `"D2@Sketch2@<model>"`) on Front, select it, `EditDelete`. The model dim is now **unconsumed**.
2. `EditRebuild3`.
3. **Import into the detail view** — select Detail Z, `InsertModelAnnotations4(...)`. Only unconsumed dims land here, so just that one dim appears (everything else is still owned by Front) — no flood to clean up.
4. Re-find it on the detail, apply the fit suffix, recolor, reposition.

### When NOT to use this

- If the dim isn't yet placed on **any** view (fresh import), `DuplicateDimensions` behaves normally — no need to pre-delete.
- A Ø-to-axis dim cannot be freed into a detail that excludes the axis (the attachment geometry isn't in the detail). Those stay on the parent — e.g. a groove's Ø stays on Front; only the axis-independent width moves to the detail. (That rule is the first bullet in [Gotchas](#gotchas) below; the freeing-order rule here is the new part.)

### Recovery if you already lost the dim

If the diff shows the dim removed from the parent but the detail kept nothing — it's **freed, not gone**. Run step 3 (import into the detail); the now-unconsumed model dim drops straight in. Only fall back to manual `AddDimension2` off `GetVisibleEntities2` (`manual-dimensioning.md`) if re-import still yields nothing.

## Gotchas

- **A radius/Ø-to-axis dim can't live in a detail that excludes the axis.** It attaches to the visible feature on one side and the axis (r = 0) on the other — far off the crop. It's complete, not broken; the off-view test catches it and deletes it from the detail (correct). Put that Ø on a view showing the full diameter + axis (the parent); in the detail, dimension only axis-independent quantities — width and depth.
- **Reference points throw on radial/Ø, chamfer, and thread dims** (`COMException` or zeroed), which would hide an off-view dim — the snippet falls back to the label position for those.
- **Hand-dimensioning needs `swViewEntityType_e` `1`/`2`/`3`/`4`** (not the `swSelectType_e` `12`/`11`/`4`/`2`) for `GetVisibleEntities2`; a wrong value returns 0 entities with no error. Full recipe in `manual-dimensioning.md`.
