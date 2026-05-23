---
name: mark-the-stuff-down
description: |
  Конвертирует офисные документы (.docx, .pdf, .xlsx, .xls, .pptx, .rtf, .html, .epub)
  в Markdown для последующего чтения по фрагментам. Invoke when the user provides or references
  a binary office document and you need to extract its textual content. Saves output as a .md
  file next to the source; returns Markdown file paths on stdout. Token-efficient: do not paste the
  full document into context — read the .md file with offset/limit or grep instead.
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
---

# mark-the-stuff-down

## When to invoke

When the user attaches or references a binary office document and you need its textual content.

## How to invoke

```sh
python /path/to/mark-the-stuff-down/convert.py "<absolute-path-to-document>"
```

For multiple documents, pass all paths in one invocation; the converter runs them in parallel by default:

```sh
python /path/to/mark-the-stuff-down/convert.py --jobs 4 "<doc-1>" "<doc-2>" "<doc-3>"
```

The script prints one stdout line per successfully converted file: `<abs-path-to-markdown> (<size>)`. Read those files with `Read` using `offset` and `limit`, or `grep` them. **Do not paste full documents into context.**

## Errors

The script writes `ERROR <type>: <reason>` to stderr and exits 1 on expected errors. Surface the message to the user.

**STOP rules — do not improvise around an error:**

- `ERROR scanned-pdf` — PDF has no text layer. **Do NOT** run OCR yourself, install tesseract/pytesseract, download language data, or dispatch vision subagents to read the pages. This is out of scope for this skill. Report the error to the user and wait for an explicit instruction (e.g. they may provide an OCR'd copy, request a vision pass with their consent, or skip the file).
- `ERROR unsupported: .doc legacy format` — ask the user to resave the file as `.docx`.
- `ERROR too-large` — report the file size; do not attempt to split, compress, or partially read the file without the user's say-so.
- `ERROR protected` — the file is password-protected. Do not attempt to guess or strip the password. Ask the user for an unprotected copy.
- `ERROR install-failed` — a required backend is not installed and the sandbox cannot fetch it. Report the missing backend; do not attempt manual installs from arbitrary sources.

Surfacing an error is the terminal step for this skill. Resuming the original task with a different approach requires the user's explicit go-ahead.

## Re-runs

Re-invoking on the same unchanged file is cheap: the script detects an existing up-to-date Markdown via an `<!-- mark-the-stuff-down vX.Y -->` marker on the first line and returns the cached path.
