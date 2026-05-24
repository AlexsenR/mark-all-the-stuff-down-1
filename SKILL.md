---
name: mark-all-the-stuff-down
description: |
  Конвертирует офисные документы (.docx, .pdf, .xlsx, .xls, .pptx, .rtf, .html, .epub)
  и изображения (.png, .jpg, .jpeg, .tiff, .tif, .bmp, .webp) в Markdown для
  последующего чтения по фрагментам. Scanned PDFs and images are OCR'd locally
  with tesseract using bundled rus+eng tessdata. Invoke when the user provides
  or references a binary office document or image and you need to extract its
  textual content. Saves output as a .md file next to the source; returns
  Markdown file paths on stdout. Token-efficient: do not paste the full document
  into context — read the .md file with offset/limit or grep instead.
  Note: legacy .doc (Word 97-2003) is not supported — ask user to resave as .docx.
paths:
  - "*.docx"
  - "*.pdf"
  - "*.xlsx"
  - "*.xls"
  - "*.pptx"
  - "*.rtf"
  - "*.html"
  - "*.epub"
  - "*.png"
  - "*.jpg"
  - "*.jpeg"
  - "*.tiff"
  - "*.tif"
  - "*.bmp"
  - "*.webp"
---

# mark-all-the-stuff-down

## When to invoke

When the user attaches or references a binary office document or image and you need its textual content.

## How to invoke

```sh
python /path/to/mark-all-the-stuff-down/convert.py "<absolute-path-to-document>"
```

For multiple documents, pass all paths in one invocation; the converter runs them in parallel by default:

```sh
python /path/to/mark-all-the-stuff-down/convert.py --jobs 4 "<doc-1>" "<doc-2>" "<doc-3>"
```

The script prints one stdout line per successfully converted file: `<abs-path-to-markdown> (<size>)`. Read those files with `Read` using `offset` and `limit`, or `grep` them. **Do not paste full documents into context.**

## OCR

Scanned PDFs and image files are converted with local tesseract OCR using bundled `rus+eng` tessdata. Image OCR supports `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`, and `.webp`; `.webp` requires Pillow to be available at runtime.

## Errors

The script writes `ERROR <type>: <reason>` to stderr and exits 1 on expected errors. Warnings are non-fatal and should be surfaced to the user.

**STOP rules — do not improvise around an error:**

- `WARN ocr-low-confidence` — OCR median confidence is below 60%. The conversion completed; surface the warning and inspect the Markdown before relying on it.
- `ERROR ocr-failed` — tesseract failed, `pdftoppm` is missing for scanned PDFs, or bundled tessdata is absent. Report the failure; do not download language data or switch to an external OCR/vision pipeline without the user's explicit go-ahead.
- `ERROR install-failed` — for `.webp`, Pillow is not available in this environment. Report the missing runtime dependency; do not attempt manual installs from arbitrary sources.
- `ERROR unsupported: .doc legacy format` — ask the user to resave the file as `.docx`.
- `ERROR too-large` — report the file size; do not attempt to split, compress, or partially read the file without the user's say-so.
- `ERROR protected` — the file is password-protected. Do not attempt to guess or strip the password. Ask the user for an unprotected copy.

Surfacing an error is the terminal step for this skill. Resuming the original task with a different approach requires the user's explicit go-ahead.

## Re-runs

Re-invoking on the same unchanged file is cheap: the script detects an existing up-to-date Markdown via an `<!-- mark-all-the-stuff-down vX.Y -->` marker on the first line and returns the cached path.
