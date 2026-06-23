---
name: DOCX
description: >-
  Use whenever a .docx file is involved — as input, output, or both: creating
  Word documents, reports, memos, letters, or templates; reading, parsing, or
  extracting text from a .docx; editing or updating existing documents; working
  with headings, tables of contents, page numbers, tables, images, headers, or
  footers. Trigger whenever the user mentions "Word doc," "document," "report,"
  "memo," "letter," or a .docx filename, regardless of what they do with the
  content afterward.
---

# Working with Word documents (.docx)

You build and edit documents **by writing Python code**, not by filling in a
fixed schema. The `docgen` tool's `run_python` runs your code in the app's
bundled interpreter, which has these libraries pre-installed:

- **`docx` (python-docx)** — create/edit documents, load templates, add
  headings, paragraphs, runs, tables, images, page breaks, headers/footers.
- **`fitz` (PyMuPDF)** and **`PIL` (Pillow)** — rasterize PDFs to images, image ops.
- **`pptx`, `openpyxl`** — PowerPoint / Excel, if the task drifts there.

`run_python` is real execution with full filesystem access. `print(...)` is
captured and returned to you. Iterate: **write code → render → inspect → fix → re-render.**

## Reading / analyzing a document

To extract text, use the `files` read tool on the `.docx`, or write a quick script:

```python
from docx import Document
doc = Document("/path/to/report.docx")
for para in doc.paragraphs:
    if para.text.strip():
        print(f"[{para.style.name}] {para.text}")
for ti, table in enumerate(doc.tables, 1):
    print(f"## Table {ti}")
    for row in table.rows:
        print(" | ".join(cell.text for cell in row.cells))
```

## Creating / editing

Start from the user's template when they have one (`Document("template.docx")`)
— it preserves their styles, fonts, and branding. Otherwise `Document()` gives a
blank US-Letter-ish A4 doc; set page size and margins explicitly on the section:

```python
from docx import Document
from docx.shared import Inches, Pt, RGBColor

doc = Document()
section = doc.sections[0]
section.page_width = Inches(8.5)      # US Letter
section.page_height = Inches(11)
section.top_margin = section.bottom_margin = Inches(1)
section.left_margin = section.right_margin = Inches(1)

doc.add_heading("Quarterly Report", level=1)
doc.add_paragraph("Summary of the quarter.")
doc.add_paragraph("First point", style="List Bullet")   # built-in list styles —
doc.add_paragraph("Second point", style="List Bullet")  # never type "• " yourself
doc.save("/abs/path/report.docx")
```

Add content with python-docx (`add_heading`, `add_paragraph` / `add_run`,
`add_picture`, `add_table`, `add_page_break`). **Save to a real path, and pass
that path to `run_python`'s `output_files` argument** — the saved document then
comes back as a downloadable tile the user can open directly, so you don't have
to make them hunt for the path. Still mention where it landed.

A few python-docx specifics worth knowing:

- **Lists**: use the built-in `"List Bullet"` / `"List Number"` paragraph styles.
  Never insert `•` or `•` manually.
- **Tables**: `table = doc.add_table(rows=…, cols=…); table.style = "Table Grid"`
  for visible borders; set `table.autofit = False` and width per column for
  predictable layout. Write cells via `table.cell(r, c).text = …`.
- **Page breaks**: `doc.add_page_break()`.
- **Headers / footers**: `section.header` / `section.footer`; page numbers need a
  `PAGE` field, which python-docx doesn't expose directly — add it via the
  paragraph's XML run if the user asks for numbered pages.
- **Table of contents**: python-docx can't build a *live* TOC field. If the user
  needs an auto-updating TOC, build the headings with `add_heading(level=…)` and
  insert a TOC field via XML, or tell the user to press F9 in Word to populate it.

## Visual QA (required)

Your first render usually has real issues — overflow tables, awkward page
breaks, misaligned images. Render and **look** before declaring done:

```python
import os, subprocess, tempfile, fitz
soffice = os.environ.get("COSMON_SOFFICE_BIN") or "soffice"
out = tempfile.mkdtemp()
subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", out, "report.docx"], check=True)
pdf = os.path.join(out, "report.pdf")
doc = fitz.open(pdf)
paths = []
for i, page in enumerate(doc):
    p = os.path.join(out, f"page-{i+1}.png")
    page.get_pixmap(dpi=150).save(p)
    paths.append(p)
print("\n".join(paths))
```

Then open those PNG paths with the `files` read tool to **see** the pages.
Check for table/text overflow past the margins, orphaned headings at page
bottoms, broken image placement, and leftover placeholder text (`xxx`, `lorem`,
`[insert…]`). Fix the offending content, re-render, re-inspect. Stop after one
fix-and-verify cycle unless a new visible defect appears.

## Design (don't make boring documents)

- **Use styles, not manual formatting** — `add_heading(level=…)` and named
  paragraph styles keep the document consistent and make a TOC possible.
- **Readable defaults** — body 11–12pt, generous line spacing, ≥1" margins.
- **Tables earn their keep** — borders on (`"Table Grid"`), header row bold,
  consistent cell padding. Don't use empty tables as horizontal rules.
- **One accent color** — apply via `RGBColor` to headings or table header
  shading; don't rainbow the document.
- **Letterhead / report polish** — title block, date, section headings, page
  numbers in the footer. Match the user's template when they have one.

## Common mistakes

- Typing bullet characters instead of using `"List Bullet"` style.
- Tables without `table.style` — they render borderless and read as plain text.
- Manual page-number text instead of a real `PAGE` field (won't update).
- Forgetting to set page size — python-docx defaults to A4, not US Letter.
- Leftover template placeholder text — read the extracted text and fix before finishing.
- Saving the document but not passing its path to `output_files`, so the user
  has no tile to click.
