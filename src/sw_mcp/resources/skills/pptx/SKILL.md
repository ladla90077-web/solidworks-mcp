---
name: PPTX
description: >-
  Use whenever a .pptx file is involved — as input, output, or both: creating
  slide decks, pitch decks, or presentations; reading, parsing, or extracting
  text from a .pptx; editing or updating existing presentations; combining or
  splitting decks; working with templates, layouts, speaker notes, or tables.
  Trigger whenever the user mentions "deck," "slides," "presentation," or a
  .pptx filename, regardless of what they do with the content afterward.
---

# Working with PowerPoint (.pptx)

You build and edit presentations **by writing Python code**, not by filling in
a fixed schema. The `docgen` tool's `run_python` runs your code in the app's
bundled interpreter, which has these libraries pre-installed:

- **`pptx` (python-pptx)** — create/edit decks, load templates, add slides,
  text, images, tables, shapes.
- **`fitz` (PyMuPDF)** and **`PIL` (Pillow)** — rasterize PDFs to images, image ops.
- **`docx`, `openpyxl`** — Word / Excel, if the task drifts there.

`run_python` is real execution with full filesystem access. `print(...)` is
captured and returned to you. Iterate: **write code → render → inspect → fix → re-render.**

## Reading / analyzing a deck

To extract text, use the `files` read tool on the `.pptx` (it returns
per-slide text), or write a quick script:

```python
from pptx import Presentation
prs = Presentation("/path/to/deck.pptx")
for i, slide in enumerate(prs.slides, 1):
    print(f"## Slide {i}")
    for shape in slide.shapes:
        if shape.has_text_frame:
            print(shape.text_frame.text)
```

## Creating / editing

Start from the user's template when they have one (`Presentation("template.pptx")`)
— it preserves their masters, fonts, and branding. Otherwise `Presentation()`
gives a blank 4:3 deck; set 16:9 with `prs.slide_width = Inches(13.333);
prs.slide_height = Inches(7.5)`. Add content with python-pptx
(`add_slide`, `add_textbox`, `add_picture`, `add_table`, `add_shape`). Save to a
real path, and pass that path to `run_python`'s `output_files` argument — the
saved deck then comes back as a downloadable tile the user can open directly, so
you don't have to make them hunt for the path. Still mention where it landed.

## Visual QA (required)

Your first render usually has real issues — overflow, overlap, misalignment.
Render and **look** before declaring done:

```python
import os, subprocess, tempfile, fitz
soffice = os.environ.get("COSMON_SOFFICE_BIN") or "soffice"
out = tempfile.mkdtemp()
subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", out, "deck.pptx"], check=True)
pdf = os.path.join(out, "deck.pdf")
doc = fitz.open(pdf)
paths = []
for i, page in enumerate(doc):
    p = os.path.join(out, f"slide-{i+1}.png")
    page.get_pixmap(dpi=150).save(p)
    paths.append(p)
print("\n".join(paths))
```

Then open those PNG paths with the `files` read tool to **see** the slides.
Check text bounds first (overflow is the most common, always-visible defect),
then overlaps, contrast, alignment, and leftover placeholder text
(`xxx`, `lorem`, `[insert…]`). Fix the offending slide, re-render, re-inspect.
Stop after one fix-and-verify cycle unless a new visible defect appears — don't
chase sub-pixel nudges.

## Design (don't make boring slides)

- **Pick a content-informed palette** — one dominant color (60–70%), 1–2
  supporting tones, one sharp accent. Don't default to blue.
- **Every slide needs a visual element** — image, chart, icon, or shape.
  Avoid plain title + bullets.
- **Vary layouts** — two-column, icon+text rows, 2×2 grids, half-bleed image,
  big stat callouts. Don't repeat one layout.
- **Type contrast** — titles 36–44pt bold, body 14–16pt. Left-align body;
  center only titles. Pick a header/body font pairing with personality.
- **Spacing** — ≥0.5" margins, consistent 0.3–0.5" gaps, breathing room.
- **Avoid AI-slop tells** — no accent lines under titles, no decorative
  full-width colored bars/ribbons, no cream/beige default backgrounds (use
  white or the brand palette), never ship text that overflows its shape.

## Common mistakes

- Centering body text; skimping on title size contrast.
- Styling one slide and leaving the rest plain — commit fully or keep it simple.
- Forgetting text-box padding when aligning shapes to text edges (`margin=0`).
- Low-contrast text/icons (light on light, dark on dark).
- Leftover template placeholder text — grep the extracted text and fix before finishing.
