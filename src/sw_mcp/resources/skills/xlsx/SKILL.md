---
name: XLSX
description: >-
  Use whenever a spreadsheet file is the primary input or output: creating,
  reading, editing, or fixing .xlsx / .xlsm / .csv / .tsv files — adding columns,
  computing formulas, formatting, charting, cleaning messy tabular data — or
  building a new spreadsheet or financial model from scratch. Trigger whenever
  the user references a spreadsheet by name or path (even casually, like "the
  xlsx in my downloads") and wants something done to it or produced from it. Do
  NOT trigger when the primary deliverable is a Word doc, slide deck, or a
  standalone script — only when the deliverable is a spreadsheet file.
---

# Working with spreadsheets (.xlsx / .csv)

You build and edit spreadsheets **by writing Python code**, not by filling in a
fixed schema. The `docgen` tool's `run_python` runs your code in the app's
bundled interpreter. For spreadsheets the available library is:

- **`openpyxl`** — create/edit `.xlsx` / `.xlsm`, read and write cells, formulas,
  number formats, fonts, fills, column widths, charts, multiple sheets.
- **`pandas`** — fast reading/analysis, bulk operations, and `.csv` / `.tsv`
  ↔ `.xlsx` conversion (`read_excel`, `read_csv`, `to_excel`).

Reach for **pandas** to load, clean, reshape, and analyze tabular data, and for
**openpyxl** when you need formulas, cell formatting, or to preserve an existing
workbook's structure. `csv` / `json` from the standard library also work for
plain delimited text.

`run_python` is real execution with full filesystem access. `print(...)` is
captured and returned to you.

## Reading / analyzing a spreadsheet

To dump contents, use the `files` read tool on the `.xlsx`, or write a script.
**Use `data_only=True` to read the last-calculated values** of formula cells —
but never *save* a workbook opened that way, or the formulas are replaced by
values and lost.

```python
from openpyxl import load_workbook
wb = load_workbook("/path/to/model.xlsx", data_only=True)
for ws in wb.worksheets:
    print(f"## Sheet: {ws.title}")
    for row in ws.iter_rows(values_only=True):
        if any(c is not None for c in row):
            print("\t".join("" if c is None else str(c) for c in row))
```

## Creating / editing

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

wb = Workbook()
ws = wb.active
ws.title = "Summary"
ws.append(["Quarter", "Revenue", "COGS", "Gross profit"])
ws.append(["Q1", 1200, 700, "=B2-C2"])
ws.append(["Q2", 1500, 820, "=B3-C3"])
ws["A1"].font = Font(bold=True)
ws.column_dimensions["A"].width = 14
wb.save("/abs/path/model.xlsx")
```

**Save to a real path, and pass that path to `run_python`'s `output_files`
argument** — the saved workbook then comes back as a downloadable tile the user
can open directly, so you don't have to make them hunt for the path. Still
mention where it landed.

To edit an existing file, `load_workbook(path)` (without `data_only`) preserves
formulas and formatting; modify cells, then `wb.save(...)`.

## Use formulas, not hardcoded values (critical)

Always write Excel **formulas** so the sheet recalculates when inputs change —
never compute a number in Python and paste the result.

```python
ws["B10"] = "=SUM(B2:B9)"          # not  ws["B10"] = 5000
ws["C5"]  = "=(C4-C2)/C2"          # not  a Python-computed growth rate
ws["D20"] = "=AVERAGE(D2:D19)"     # not  sum(values)/len(values)
```

Put assumptions (growth rates, margins, multiples) in their own cells and
reference them: `=B5*(1+$B$6)`, not `=B5*1.05`. This applies to every
total, ratio, and difference.

## Aim for zero formula errors

The deliverable should have **zero** formula errors (`#REF!`, `#DIV/0!`,
`#VALUE!`, `#N/A`, `#NAME?`). openpyxl writes formulas as strings *without*
cached results — Excel recalculates them when the user opens the file, so the
errors only appear there. You can't fully verify them offline; the reliable
defense is to **author defensively**:

- Guard every denominator (`=IF(B2=0, "", A2/B2)`) — `#DIV/0!` is the most common.
- Re-check references after inserting/deleting rows or columns (`#REF!`).
- Use `Sheet1!A1` form for cross-sheet links; match types in math (`#VALUE!`).
- Spell function names correctly (`#NAME?`).

**Best-effort machine check (only if LibreOffice is present).** When
`COSMON_SOFFICE_BIN` is set you *may* recalc and scan, but treat the result with
care — headless convert does not always force a recalculation, and if it
doesn't, `data_only` reads come back `None` (openpyxl stored no cached values),
so the scan finds nothing and looks clean when it never actually checked. Only
trust a "none" result if formula cells came back **populated**:

```python
import os, subprocess, tempfile
from openpyxl import load_workbook
soffice = os.environ.get("COSMON_SOFFICE_BIN")
if soffice:
    out = tempfile.mkdtemp()
    subprocess.run([soffice, "--headless", "--calc", "--convert-to", "xlsx",
                    "--outdir", out, "/abs/path/model.xlsx"], check=True)
    calc = load_workbook(os.path.join(out, "model.xlsx"), data_only=True)
    cells = [c for ws in calc.worksheets for row in ws.iter_rows() for c in row]
    recalced = any(c.value is not None for c in cells)
    errors = [(c.coordinate, c.value) for c in cells
              if isinstance(c.value, str) and c.value.startswith("#")]
    # No recalc → the scan proves nothing; fall back to the manual audit above.
    print("recalc ran:", recalced, "| errors:", errors or "none")
```

If `soffice` is unavailable or didn't recalc, audit denominators and references
by hand — don't claim the model is error-free on the strength of a scan that
didn't run.

## Formatting & financial conventions

Match an existing template's conventions exactly when editing one — they always
override the defaults below.

- **Font**: a consistent professional font (Arial / Times New Roman) unless told otherwise.
- **Number formats** (set `cell.number_format`):
  - Currency: `"#,##0"`, and put units in the header (`"Revenue ($mm)"`).
  - Zeros shown as `-`: `"#,##0;(#,##0);-"`. Negatives in parentheses, not `-123`.
  - Percentages: `"0.0%"`. Valuation multiples: `"0.0x"`.
  - Years are text (`"2024"`), never `"2,024"`.
- **Financial-model color coding** (font color) when building a model from scratch:
  - Blue `0000FF` — hardcoded inputs / scenario drivers.
  - Black `000000` — all formulas and calculations.
  - Green `008000` — links to other sheets in the same workbook.
  - Red `FF0000` — links to external files.
  - Yellow fill `FFFF00` — key assumptions needing attention.
- **Document hardcodes** with a cell comment giving the source
  (`"Source: Company 10-K, FY2024, p.45"`).

## Common mistakes

- Reaching for pandas to *write a model* — pandas dumps static values with no
  formulas or formatting. Use openpyxl when the deliverable needs either.
- Hardcoding a Python-computed number instead of writing an Excel formula.
- Saving a workbook that was opened with `data_only=True` — destroys formulas.
- Trusting a clean offline scan as proof — a headless recalc that didn't run
  reports zero errors falsely; author defensively and audit by hand.
- Saving the file but not passing its path to `output_files`, so the user has
  no tile to click.
