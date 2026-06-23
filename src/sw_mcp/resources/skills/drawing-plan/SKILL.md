---
name: Drawing Plan
description: Decide HOW to draw a part before drawing it — manufacturing method, primary view, view set, dimensioning scheme, sheet/scale, GD&T — and propose a short plan with a rationale per choice for approval. Use to plan a drawing before execution.
---

# Plan Drawing

Decide *how* to draw the part before drawing it. The output is a short plan the user approves or adjusts — not a finished drawing. Plan well and execution is mechanical; plan badly and you redo views and dimensions.

The standards in brackets are the authority; when nothing says which applies, default to the company standard, then ASME for inch / ISO for metric.

## How to plan

1. Understand the part: model type, bounding box, features, units, symmetry, internal geometry, key dimensions.
2. Take screenshots of the part from multiple angles to understand the part
3. Decide the manufacturing method first — it drives features, symmetry, and datums.
4. Work through each decision below.
5. Propose the plan with a one-line *because* for every choice, so the user can accept or override on judgment. Keep it short enough to approve at a glance.
6. **Stop and confirm before executing.** Planning is the place to disagree; once drawing starts, changes are expensive.

## The plan

**Manufacturing method** *(decide first)*
- How the part is made: turned, milled, cast, sheet metal, etc. — read it from the feature signature (a revolve + chamfer reads as turned).
- This sets the datum scheme: a turned part is datumed on its first turned feature; a milled part on its functional faces.

**Primary view** *(ASME Y14.3 / ISO 128-3)*
- Pick the most informative profile from the bounding box — don't assume the front view. Profiles: front = X×Y, right = Z×Y, top = X×Z; choose the one that shows the most features.
- Turned → revolve axis horizontal. Sheet metal → largest flat face. General → largest, most detailed profile.

**Views** — scale the set to the part's complexity:
- **Simple part** — the minimum set that fully describes it; give each view a purpose (section to expose a pocket, top for the hole pattern, isometric for context only).
- **More complex part** — add a section where internal detail matters, a detail view for features too small to dimension, an auxiliary view for inclined faces.
- **Complex or long part** — use broken, detail, and section views so every feature can be dimensioned without overcrowding the sheet (a broken view shortens a long uniform part so it fits at a usable scale).

**Dimensioning scheme** *(ASME Y14.5 / ISO 129-1)*
- **Chain** — feature-to-feature; avoid where cumulative location matters.
- **Baseline** — all from one reference edge; no build-up.
- **Ordinate** — +X/+Y from one origin; best for many-hole plates.
- **Polar** — radius and angle; for radial patterns and bolt circles.

**Dimension table** — one row per feature: size / location / qualifier (THRU, TYP, ⌀…) / quantity. No blank cells, and every feature appears — this is the completeness check before any drawing happens.

**GD&T** *(ASME Y14.5 / ISO 1101, ISO 5459)*
- Required for mating/functional features; skip for cosmetic ones.
- Datums follow how the part mounts or functions, in A→B→C order.

**Sheet & scale** *(ISO 5457 / ASME Y14.1; scales ISO 5455)*
- Size to the part footprint — default A3, landscape. Reserve space for the title block (bottom-right) and border before placing views.
- Units from the model: imperial → inch, metric → mm.
- Clean ratio scale (1:1, 1:2, 1:5, 1:10, 2:1...); full size when it fits; leave white space.

**Title block** *(ISO 7200)*
- Plan the values: material, finish, mass, tolerances, notes, projection method.

## Company standards

House rules that go beyond or override the general standards above (e.g. a required template, datum-labelling scheme, default sheet/scale, standard notes). These win on any conflict.

_None defined yet — add house rules here as they're established._

## Failure modes to avoid

- **Skipping the manufacturing method.** Datums and symmetry come out wrong if you draw before deciding how it's made.
- **Defaulting to the front view.** Pick the view that shows the most, from the bounding box.
- **Over-viewing.** More views than needed clutter the sheet and invite redundant dimensions.
- **Planning silently, then executing.** Always propose and confirm first.
- **Cramming.** A plan with no white space is a plan to redo the layout.

## Adapt to context

- **Simple part** — a few lines: method, primary view, sheet/scale, then go.
- **Complex part or assembly** — full plan; for assemblies add BOM and balloon strategy.
- **User gave a layout** — treat it as input, not truth; propose the right views and flag where you'd differ, with the reason.
