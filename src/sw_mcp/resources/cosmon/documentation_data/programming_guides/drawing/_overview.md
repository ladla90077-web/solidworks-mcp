---
description: START HERE for any drawing task — read this index FIRST, before reading or running any other drawing guide. It maps every SolidWorks drawing guide, grouped into atomic building blocks (single drafting operations) and molecular workflows (multi-step recipes that compose them), so you can pick the smallest correct set of guides for the job.
---

# Guide Index — what each drawing guide is for

> Read this first. It maps every guide so you can pick the smallest set that does the job.
>
> - **Atomic** guides each do *one* cohesive drafting operation — drop one in wherever you need it.
> - **Molecular** guides are end-to-end workflows that chain several atomic operations — start there for a whole-drawing task, then follow their links into the atomic guides for detail.

---

## Molecular workflows (start here for a whole drawing)

| Guide | Composes | What it does |
|---|---|---|
| `quick_multi_view_drawing.md` | drawing + sheet + views | Scaffold a new part drawing: create the doc and sheet, place + project the standard views, auto-scale and center. The usual first step. |
| `long-part-views.md` | views + breaks + dimensioning + details | Strategy for long/slender parts: canonical layout, where to break, how to distribute dims across views, which clusters earn a detail bubble. |
| `create-assembly-drawing.md` | drawing + views + BOM + balloons + section + title block | End-to-end assembly drawing in two calls: views, bill of materials, auto-balloons, optional section, then title-block hand-off. |

## Atomic building blocks (one cohesive operation each)

### Sheet
| Guide | What it does |
|---|---|
| `change-paper-size.md` | Resize an existing sheet — re-run `SetupSheet6` with the new size + matching format file, reload the template, re-fit views. |

### Views
| Guide | What it does |
|---|---|
| `section-views.md` | Cut section views (full / half / offset / aligned / broken-out / removed / slice), configure them, keep them linked to the parent, place without overlap, and dimension inside them. |
| `detail-views.md` | Create magnified detail views (circular or rectangular/profile), place them safely on the sheet, and clean up the view + its boundary sketch. |
| `broken-views-guide.md` | Add or remove view breaks to compress long parts; match break positions across aligned views. |

### Dimensioning
| Guide | What it does |
|---|---|
| `dimensioning-simple.md` | The standard per-dimension recipe — insert, list every dim for the user, clean, recolor, recover, arrange (`AlignDimensions`/AutoArrange), and move linear / Ø / angular dims per view. Also owns the QUALIFIER/QUANTITY callout-text cheat-sheet, chamfer & hole callouts, and broken-leader straightening. The default dimensioning guide. |
| `dimensioning-systems.md` | Pick a dimensioning *system* (ordinate / baseline / chain / polar / tabular / GD&T) and drive its API; includes the Phase-1 system-selection decision and the per-feature completeness table. |
| `manual-dimensioning.md` | Place a dimension from scratch off a view's visible geometry — pull visible entities, classify edges, take overall dims from extreme vertices, and dimension polygonal across-flats (A/F) pockets — when there's no model dim to project. |
| `detail-view-dimensioning.md` | Dimension a detail view — IMA4 (cross-view duplicates OK), then delete the detail's cross-view-duplicate and off-view dims (parent keeps its copy); falls back to `manual-dimensioning.md`. |

### Annotations
| Guide | What it does |
|---|---|
| `gdt-recipe.md` | Apply datum tags and feature control frames (GD&T) — position / orientation / form / runout / profile, composite frames, basic dims. |
| `surface-finish.md` | Place and edit surface-finish symbols, attached to a dimension or an edge. |
| `title-block.md` | Read and fill the title block by the right mechanism — property-linked notes, free-text notes, or the Title Block Fields feature. |

### Tables
| Guide | What it does |
|---|---|
| `tables.md` | Insert and edit drawing tables (BOM / hole / revision / bend / weldment / general) via the shared `ITableAnnotation` API — sizing, row/column ops, anchoring, splitting, formatting. **Prefer the general table** over specialized types; it's more flexible and reliable. |

---

## How to combine them

A typical single-part drawing:

`quick_multi_view_drawing.md` (views) → `section-views.md` / `detail-views.md` / `broken-views-guide.md` as the geometry needs → `dimensioning-simple.md` (+ `dimensioning-systems.md` to pick the system, `manual-dimensioning.md` to dimension from scratch, `detail-view-dimensioning.md` for details) → `gdt-recipe.md` / `surface-finish.md` (annotations) → `tables.md` (BOM / hole / general tables) → `title-block.md` (finish).

For long parts, use `long-part-views.md` in place of plain views. For assemblies, use `create-assembly-drawing.md`.
