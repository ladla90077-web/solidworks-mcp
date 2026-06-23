---
name: PDF
description: >-
  Use whenever a .pdf file is involved — as input, output, or both: reading or
  extracting text and tables from a PDF; merging, splitting, or reordering
  pages; rotating, cropping, or deleting pages; adding watermarks or stamps;
  extracting images; creating a new PDF from scratch; or OCR'ing a scanned PDF
  to make it searchable. Trigger whenever the user mentions a .pdf filename or
  asks to produce one, regardless of what they do with the content afterward.
  Note that .docx / .pptx / .xlsx files are usually best turned into a PDF by
  exporting through LibreOffice (`COSMON_SOFFICE_BIN`) — see those skills.
---

# Working with PDFs (.pdf)

You read and build PDFs **by writing Python code**, not by filling in a fixed
schema. The `docgen` tool's `run_python` runs your code in the app's bundled
interpreter, which has these libraries pre-installed:

- **`fitz` (PyMuPDF)** — the one tool for almost everything: extract text and
  tables, merge/split/reorder/rotate/delete pages, watermark, extract images,
  create new PDFs, render pages to PNG, and OCR scanned pages.
- **`PIL` (Pillow)** — image ops (resize, convert, compose) for images you pull
  out of or drop into a PDF.
- **`pptx`, `docx`, `openpyxl`, `pandas`** — if the source or target drifts to
  Office formats. To turn one of those into a PDF, export via LibreOffice (see
  the "Office → PDF" note below).

`run_python` is real execution with full filesystem access. `print(...)` is
captured and returned to you. Iterate: **write code → run → inspect → fix.**

There is **no pypdf / reportlab / pdfplumber** in the bundle — don't import
them. PyMuPDF covers all of those use cases; use `fitz`.

## Reading / extracting text

To dump text, use the `files` read tool on the `.pdf`, or write a script:

```python
import fitz
doc = fitz.open("/path/to/document.pdf")
for i, page in enumerate(doc, 1):
    print(f"## Page {i}")
    print(page.get_text())
```

`page.get_text("text")` gives plain reading order; `"words"` / `"dict"` /
`"blocks"` give positions when you need layout. For a scanned (image-only) PDF
`get_text()` returns empty — see **OCR** below.

## Extracting tables

```python
import fitz
doc = fitz.open("/path/to/document.pdf")
for i, page in enumerate(doc, 1):
    for t, table in enumerate(page.find_tables().tables, 1):
        print(f"## Page {i} table {t}")
        for row in table.extract():
            print(row)
        # table.to_pandas() gives a DataFrame if you want to write .csv/.xlsx
```

## Merge / split / reorder / delete pages

```python
import fitz

# Merge several PDFs into one
out = fitz.open()
for path in ["a.pdf", "b.pdf", "c.pdf"]:
    with fitz.open(path) as src:
        out.insert_pdf(src)
out.save("/abs/path/merged.pdf")

# Split: one file per page
src = fitz.open("input.pdf")
for i in range(src.page_count):
    one = fitz.open()
    one.insert_pdf(src, from_page=i, to_page=i)
    one.save(f"/abs/path/page_{i+1}.pdf")

# Reorder / subset: select() takes the new page order (0-based)
src.select([2, 0, 1])          # keep+reorder these pages
src.delete_page(0)             # or delete_pages(from_page=, to_page=)
src.save("/abs/path/reordered.pdf")
```

## Rotate pages

```python
import fitz
doc = fitz.open("input.pdf")
doc[0].set_rotation(90)        # 90 / 180 / 270, clockwise
doc.save("/abs/path/rotated.pdf")
```

## Watermark / stamp

Overlay text or an image on every page. For text, `insert_htmlbox` gives you
styling; for a logo or an existing watermark PDF, stamp it with `show_pdf_page`
(vector, stays sharp) or `insert_image`.

```python
import fitz
doc = fitz.open("document.pdf")
for page in doc:
    # insert_htmlbox's `rotate=` only accepts 0/90/180/270; for a diagonal
    # watermark rotate with CSS `transform` instead.
    page.insert_htmlbox(
        page.rect,
        "<div style='font-size:60px;color:rgba(150,150,150,0.4);"
        "text-align:center;transform:rotate(-45deg)'>DRAFT</div>",
    )
doc.save("/abs/path/watermarked.pdf")
```

## Extract images

```python
import fitz
doc = fitz.open("input.pdf")
for pno in range(doc.page_count):
    for ix, img in enumerate(doc.get_page_images(pno)):
        pix = fitz.Pixmap(doc, img[0])
        if pix.n - pix.alpha >= 4:           # CMYK → RGB before saving
            pix = fitz.Pixmap(fitz.csRGB, pix)
        pix.save(f"/abs/path/p{pno+1}_{ix}.png")
```

## Creating a PDF from scratch

Build pages and lay out content with `insert_htmlbox` (HTML/CSS — the easiest
way to get readable, styled text without manual coordinate math):

```python
import fitz
doc = fitz.open()
page = doc.new_page(width=595, height=842)   # A4 in points (US Letter: 612×792)
page.insert_htmlbox(
    fitz.Rect(72, 72, 523, 770),             # 1" margins
    "<h1 style='font-family:sans-serif'>Quarterly Report</h1>"
    "<p style='font-family:sans-serif;font-size:12px'>Summary of the quarter.</p>",
)
doc.save("/abs/path/report.pdf")
```

For precise single-line placement use `page.insert_text((x, y), "…", fontsize=11)`
(coordinates are points from the **top-left**). Reach for `insert_htmlbox` when
there's flowing text — it wraps and paginates for you.

**Whatever you produce, save to a real path and pass that path to
`run_python`'s `output_files` argument** — the saved PDF then comes back as a
downloadable tile the user can open directly, so you don't have to make them
hunt for the path. Still mention where it landed.

## OCR a scanned PDF (make it searchable)

Image-only PDFs have no extractable text. PyMuPDF OCRs through Tesseract when
it's installed; check first and fall back gracefully.

```python
import fitz
doc = fitz.open("scanned.pdf")
page = doc[0]
tp = page.get_textpage_ocr(dpi=300, full=True)   # needs Tesseract on PATH
print(page.get_text(textpage=tp))
```

To produce a *searchable* PDF (image + invisible text layer), render each page
and rebuild with an OCR layer; if Tesseract isn't available, tell the user it's
required rather than silently returning empty text.

## Office → PDF

A `.docx` / `.pptx` / `.xlsx` is best converted by exporting through the bundled
LibreOffice — it preserves layout far better than re-typesetting:

```python
import os, subprocess, tempfile
soffice = os.environ.get("COSMON_SOFFICE_BIN") or "soffice"
out = tempfile.mkdtemp()
subprocess.run([soffice, "--headless", "--convert-to", "pdf",
                "--outdir", out, "/abs/path/report.docx"], check=True)
# → out/report.pdf
```

## Visual QA (required when you produce or modify a PDF)

Your first output often has real issues — text overflow, clipped images, wrong
rotation, blank pages. Render and **look** before declaring done:

```python
import fitz
doc = fitz.open("/abs/path/output.pdf")
paths = []
for i, page in enumerate(doc, 1):
    p = f"/tmp/pdf-qa-{i}.png"
    page.get_pixmap(dpi=150).save(p)
    paths.append(p)
print("\n".join(paths))
```

Then open those PNG paths with the `files` read tool to **see** the pages.
Check text bounds first (overflow past margins is the most common defect), then
clipped/missing images, page rotation, and leftover placeholder text (`xxx`,
`lorem`, `[insert…]`). Fix the offending page, re-render, re-inspect. Stop after
one fix-and-verify cycle unless a new visible defect appears.

## Common mistakes

- Importing `pypdf` / `reportlab` / `pdfplumber` — not in the bundle. Use `fitz`.
- Re-typesetting a Word/PPTX/Excel file into a PDF by hand instead of exporting
  through LibreOffice — you lose the original layout and branding.
- Assuming `get_text()` works on a scanned PDF — it returns empty; OCR instead.
- Saving over the source path with `doc.save("input.pdf")` while it's open —
  use `doc.saveIncr()` for in-place, or save to a new path.
- Forgetting CMYK→RGB conversion when extracting images (saves come out wrong).
- Saving the PDF but not passing its path to `output_files`, so the user has no
  tile to click.
```
