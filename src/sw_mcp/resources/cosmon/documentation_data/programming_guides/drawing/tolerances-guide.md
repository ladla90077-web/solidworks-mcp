---
description: Dimension tolerance guide for the drafting agent — tolerance type selection (swTolType_e), the IDimension.Tolerance → Type → SetValues2 workflow, hole/shaft fit callouts, tolerance precision, units and sign conventions, verification, and silent-failure modes.
---

# Guide: Applying Dimension Tolerances

How to put ±, limit, fit, and basic tolerances on existing dimensions through the API. Tolerances attach to the **model dimension** (`IDimension`), not the drawing's display dimension — set once, it shows everywhere that dimension appears.

Companion to `dimensioning.md` (placement/styling) and `gdt-guide.md` (geometric tolerances / FCFs — a different system; do not use this guide for position, flatness, runout, etc.).

---

## 1. Choose the tolerance type (`swTolType_e`)

| Situation | Type | Value | Displays as |
|---|---|---|---|
| Untoleranced (title block general tol applies) | `swTolNONE` | 0 | `25` |
| Equal bilateral | `swTolSYMMETRIC` | 4 | `25 ±0.1` |
| Unequal bilateral | `swTolBILAT` | 2 | `25 +0.05/-0.02` |
| Upper/lower absolute limits | `swTolLIMIT` | 3 | `25.05 / 24.98` stacked |
| One-sided floor / ceiling | `swTolMIN` 5 / `swTolMAX` 6 | 5/6 | `25 MIN` / `25 MAX` |
| ISO hole/shaft fit (fit letters only) | `swTolFIT` | 7 | `25 H7/g6` |
| Fit + resolved values | `swTolFITWITHTOL` | 8 | `25 H7 +0.021/0` |
| Resolved fit values only | `swTolFITTOLONLY` | 9 | `25 +0.021/0` |
| Theoretically exact dim for an FCF (GD&T) | `swTolBASIC` | 1 | boxed `25` |
| Title-block / general tolerance note | `swTolBLOCK` 10, `swTolGeneral` 11 | 10/11 | per doc general-tol class |

Selection logic: mating features that have an FCF in `gdt-guide.md` get `swTolBASIC` locating dims. Fits on bores/shafts use the fit types (§4). Everything functional but not GD&T-controlled gets SYMMETRIC/BILAT/LIMIT. Leave reference and stock dims at `swTolNONE` so the title block governs.

---

## 2. Core workflow

```csharp
// 1. Find the display dimension in the view (walk pattern, same as FCF reuse)
DisplayDimension dispDim = (DisplayDimension)view.GetFirstDisplayDimension5();
while (dispDim != null)
{
    Dimension dim = (Dimension)dispDim.GetDimension2(0);
    if (dim.FullName.StartsWith("D3@Boss-Extrude1")) break;   // match your target
    dispDim = (DisplayDimension)dispDim.GetNext5();
}

// 2. Set type FIRST, then values (SetValues2 FAILS while Type == swTolNONE)
Dimension swDim = (Dimension)dispDim.GetDimension2(0);
DimensionTolerance tol = swDim.Tolerance;
tol.Type = (int)swTolType_e.swTolBILAT;

// 3. Values: METERS, min is NEGATIVE for the "minus" side
bool ok = tol.SetValues2(-0.00002, 0.00005,            // -0.02 mm / +0.05 mm
    (int)swSetValueInConfiguration_e.swSetValue_InThisConfiguration, "");

// 4. Tolerance text precision (decimal places) on the DISPLAY dim
dispDim.SetPrecision3(2, -1, 3, -1);   // primary, dual, primaryTol, dualTol

// 5. Rebuild + re-arrange (tolerance text widens the dim — see dimensioning.md)
model.EditRebuild3();
drawing.Extension.AlignDimensions((int)swAlignDimensionType_e.swAlignDimensionType_AutoArrange, 0.006);
```

For `swTolSYMMETRIC` pass `SetValues2(-v, +v, ...)`; SW renders the single ± value. For `swTolMIN`/`swTolMAX` only one bound is rendered but set both anyway. For `swTolBASIC` no values are needed — setting the type boxes the dimension.

`swSetValueInConfiguration_e`: UseCurrentSetting=0, InThisConfiguration=1, InAllConfigurations=2, InSpecificConfigurations=3 (pass config names array as the last arg only for 3).

---

## 3. Units and sign conventions (most common silent failure)

- **Linear values are meters.** `+0.05 mm` = `0.00005`. Passing `0.05` produces a ±50 mm tolerance that "succeeds".
- **Angular values are radians.** `±0.5°` = `0.00873`.
- **MinValue carries its own sign.** The minus side of a bilateral is a *negative* number. `SetValues2(0.02e-3, 0.05e-3, ...)` is a +0.02/+0.05 shifted band, not +0.05/−0.02.
- `GetToleranceValues` / `tol.GetMinValue()` / `tol.GetMaxValue()` return the same convention: index 0 / Min = signed lower delta, index 1 / Max = signed upper delta. (LIMIT type also stores deltas, not absolute limits.)

---

## 4. Fit tolerances (bores and shafts)

```csharp
tol.Type = (int)swTolType_e.swTolFIT;                  // or FITWITHTOL (8) / FITTOLONLY (9)
tol.SetFitValues("H7", "g6");                          // hole fit, shaft fit — either may be ""
tol.FitType = (int)swFitType_e.swFitCLEARANCE;         // USER=0 CLEARANCE=1 TRANSITIONAL=2 PRESS=3
tol.FitDisplayStyle = (int)swFitTolDisplay_e.swFitTolDisplay_Stacked;  // StackedWithLine=1 Stacked=2 Linear=3
```

For a hole dim pass only the hole fit (`"H7", ""`); for a shaft dim only the shaft fit (`"", "g6"`). SW computes the resolved deviations for types 8/9 from the fit designation and the nominal — do not also call `SetValues2`.

---

## 5. Verify, don't trust

```csharp
bool typeOk  = swDim.GetToleranceType() == expectedType;
double[] v   = (double[])swDim.GetToleranceValues();   // [min, max], meters
bool valsOk  = Math.Abs(v[0] - expMin) < 1e-9 && Math.Abs(v[1] - expMax) < 1e-9;
```

Read back after `EditRebuild3()`. If `SetValues2` returned false, the usual causes in order: type still `swTolNONE`, dimension is read-only/driven by an equation, or a fit type where values are computed (§4).

---

## 6. Silent-failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `SetValues2` returns false, nothing changes | `Type` still `swTolNONE` | Set `tol.Type` first, then values |
| Tolerance is ±50 mm | Passed mm, not meters | Divide by 1000 |
| Band shifted (+0.02/+0.05) instead of bilateral | MinValue passed positive | Min side must be negative |
| Tolerance shows on model but reads `.00` on drawing | Tol precision defaulted | `dispDim.SetPrecision3(p, -1, tolP, -1)` |
| Dim text now overlaps neighbors | Text widened after tol added | Re-run AutoArrange (mandatory after every tol change) |
| Tolerance vanished in another configuration | Scoped with `InThisConfiguration` | Use `swSetValue_InAllConfigurations` (2) unless configs intentionally differ |
| `IsReference` misuse during cleanup walks | It's a **method**: `dim.IsReference()` | See IDimension API name gotchas in `dimensioning.md` |

Do not apply both an FCF (`gdt-guide.md`) and a tight ± tolerance to the same feature's locating dims — position FCFs require BASIC locating dims.
