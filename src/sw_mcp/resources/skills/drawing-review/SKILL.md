---
name: Drawing Review
description: Judge whether a drawing is shop-ready. Go feature by feature for defects — missing/duplicate/wrong-view dimensions, blank title-block fields, missing views/tolerances, overlaps — and report worst-first. Use to review, check, or QA a drawing.
---

# Review Drawing

Judge whether a drawing is ready for the shop. The bar: could someone build the *right* part from it without asking what you meant? Every place a reader has to guess is a defect. Your job is to find and report defects — not fix them.

The output is a list of findings, each tied to a specific feature or field. The standards in brackets are the authority; when the drawing doesn't say which applies, default to the company standard, then ASME for inch / ISO for metric.

## How to review

1. Scan the whole sheet for layout, crowding, and obvious gaps.
2. Then go feature by feature: for each dimension note its value, what it measures, and which view it's on; confirm every feature is covered; read every title-block field. This catches duplicates and missing callouts the eye glides over.
3. Check what you find against **The checklist** and **Company standards**.
4. Record every finding in one pass. For each, name the feature/field, say what's wrong, and cite the rule.
5. Report findings worst first (wrong-part defects before clarity issues).
6. End with a concise plan to fix them.

## The checklist

**Sheet & title block** *(ASME Y14.1 / ISO 5457, ISO 7200)*
- Every titled field filled: material, finish, mass, units, title, part number, scale, sheet number, revision, dates, default-tolerance block.
- Auto-filled property notes actually resolved — no blank or placeholder text.
- Scale is a clean ratio (1:1, 1:2, 1:5, 1:10, 2:1, 5:1, 10:1); full size when the part fits.

**Views** *(ASME Y14.3 / ISO 128-3)*
- Minimum views that fully describe the part; no redundant views.
- Internal features shown — by a section where the detail matters, otherwise hidden lines shown on a standard view so nothing is left undefined.
- Detail views for features too small to dimension; auxiliary views for inclined faces.
- Correct line types: visible thick, hidden dashed, centerlines thin chain, cutting planes with arrows, sections hatched.
- Projected, section, and auxiliary views tied to their parent (only isometric and removed views stand alone).
- Center marks, centerlines, symmetry axes, and bolt/pitch-circle markings present.

**Dimensions** *(ASME Y14.5 / ISO 129-1)*
- **Fully defined** — every feature sized and located, or derivable; nothing scaled or assumed.
- **Once only** — no feature dimensioned twice, restated across views, or echoed as a reference.
- **True-shape view** — dimension where the feature reads true: diameters/radii/holes on the circular view, depths on the side that shows them; never off a rectangular projection or a hidden line.
- **Real geometry only** — no dimensions to formed edges or tangent intersections.
- **Part, not process** — give a hole's diameter, not "drill," unless the method is required.
- Correct symbols and shorthand: ⌀, R, counterbore, countersink, depth, THRU (not "THRU ALL"), TYP or "n×", SYMM.
- Dimensioning scheme suits the function — see below.

**Tolerances & GD&T** *(ASME Y14.5 / ISO 1101, ISO 8015, ISO 2768)*
- Every dimension toleranced — directly, by note, or by the title-block default (except reference/basic/stock).
- Critical and mating dimensions toleranced to function; not over-tightened.
- Mating chains don't stack up badly (baseline or basic+GD&T avoids build-up that chains cause).
- Geometric tolerances control location/orientation/form; ± controls size only.
- Datums follow how the part mounts or functions, in A→B→C order. Datum letters and basic dimensions boxed; reference dimensions in parentheses.

**Clarity** *(ASME Y14.2, ISO 128-2)*
- Nothing overlaps: dimensions, text, leaders, view outlines, datum blocks, view titles, title block. The only exception is an interior leader that can't route clear.
- Dimension lines don't cross; longer dimensions outside shorter ones; dimensions outside the part outline.

## Company standards

House rules that go beyond or override the general standards above (e.g. a required title-block template, datum-labelling scheme, standard notes, approved materials). These win on any conflict.

_None defined yet — add house rules here as they're established._

## Failure modes to avoid

- **Judging by looks, not the sheet.** Verify actual values and fields feature by feature.
- **Eyeballing for duplicates.** Only the feature-by-feature pass catches a dimension restated on another view.
- **Stopping early.** Find everything in one pass.
- **Vague findings.** Name the feature, the view, and the rule.
- **Drifting into fixing.** Report what's wrong and why; leave the fix to the drawing's owner.

## Adapt to context

- **Quick check** — hit the high-frequency defects (overlaps, duplicates, under-defined features, blank fields) and give pass/fail.
- **Full review** — the whole checklist plus company standards, as a complete findings list. The default.
- **Targeted review** — review the area asked about; note anything glaring elsewhere in passing.
