---
slug: mark-all-the-shit-down-mvp
created: 2026-05-24
status: in-progress
phases:
  - id: Ф1
    scope: "Fork base: copy original skill, apply rename diffs, baseline tests green"
    status: in-progress
  - id: Ф2
    scope: "Bundle tessdata (rus+eng+osd fast) and verify tesseract uses it"
    status: pending
  - id: Ф3
    scope: "Implement ocr.py module with full unit-test coverage"
    status: pending
  - id: Ф4
    scope: "Wire OCR into convert.py + update SKILL.md, installers, CI, integration tests"
    status: pending
---

# mark-all-the-shit-down Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use dev-orchestrator to implement this plan phase-by-phase. Steps inside each phase use checkbox (`- [ ]`) syntax for tracking.

---

## Goal

Fork `mark-the-shit-down` v0.2.0 into a new skill `mark-all-the-shit-down` v0.1.0 (the fork resets to fresh numbering) that keeps the entire CLI contract intact while adding OCR support. Scanned PDFs (previously hard-erroring with `scanned-pdf`) and image files (`.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`, `.webp`) become first-class inputs.

OCR runs locally in the Claude Cowork sandbox via the preinstalled `tesseract` binary plus bundled `tessdata/` (rus, eng, osd — fast variants, ~18-19 MB total) shipped inside the skill itself. No root, no apt, no internet. `.webp` uses a runtime Pillow fallback (PNG materialization) so it works without a custom Leptonica build.

## Acceptance criteria

1. `python convert.py "<scanned.pdf>"` produces a `.md` next to the source with `## Page N` per page, OCR comments `<!-- ocr page=N conf=<int> words=<int> -->`, and cache-marker `backend: tesseract-ocr`. Exit 0.
2. `python convert.py "<image.png|jpg|jpeg|tif|tiff|bmp|webp>"` produces a `.md` with `<!-- ocr conf=<int> words=<int> -->` (no `page=N`, no `## Page N` heading), cache-marker `backend: tesseract-ocr`. Exit 0.
3. Cache-marker first line matches regex `^<!-- mark-all-the-shit-down v0\.1\.0 \|` for any OCR-produced `.md`. `marker_line()` no longer contains the literal `mark-the-stuff-down`.
4. `grep -nE '\bmark-the-(stuff|shit)-down\b' convert.py` returns empty; `grep -n '0\.2\.0' convert.py` returns empty (the upstream version literal).
5. Median page/image confidence < 60 emits exactly one `WARN ocr-low-confidence: ...` line to stderr and still exits 0.
6. Missing Pillow on a `.webp` input produces `ERROR install-failed: webp requires Pillow ...` on stderr, exit 1. Missing/broken `tesseract` produces `ERROR ocr-failed: ...`, exit 1.
7. CI `verify-bundle` job passes on a freshly built bundle containing `convert.py`, `ocr.py`, `SKILL.md`, `README.md`, `LICENSE`, and `tessdata/{rus,eng,osd}.traineddata`. All pre-existing tests still pass.

## Non-goals / deferred

- OCR languages beyond `rus+eng`.
- Table / formula / handwriting recognition; complex layout reconstruction.
- Alternative OCR engines (PaddleOCR, cloud APIs).
- Changing text-PDF backends.
- Parallelizing per-page OCR.
- Image preprocessing (deskew, denoise, binarization).
- Raising the 50 MB input limit.
- `.webp` support in environments without Pillow (clean error only).
- Renaming `MTSD_*` env vars / temp prefixes in installers.

## Files

**Ф1 — Fork base:**
- Create (copy from original): `convert.py`, `SKILL.md`, `README.md`, `LICENSE`, `install.sh`, `install.ps1`, `requirements-dev.txt`, `.github/workflows/ci.yml`, all of `tests/**` including `conftest.py`, `corpus/`, `generate_corpus.py`.
- Modify (rename diffs only): `convert.py` (~30 lines as listed in spec table).
- Create new test: `tests/test_marker_prefix.py` — asserts `marker_line()` contains new name only.
- Create new test: `tests/test_grep_no_old_name.py` — asserts forbidden substrings absent from `convert.py`.

**Ф2 — tessdata bundle:**
- Create (binary, committed): `tessdata/rus.traineddata`, `tessdata/eng.traineddata`, `tessdata/osd.traineddata`.
- Modify: `.gitignore` (ensure `tessdata/` is NOT ignored).

**Ф3 — ocr.py module:**
- Create: `ocr.py` — `OcrError`, `_parse_tsv_page()`, `_materialize_for_tesseract()`, `convert_image()`, `convert_pdf_scanned()`. ~200 lines, no dependency on `convert.py`.
- Create: `tests/test_ocr.py` — unit + integration tests (integration marked `@pytest.mark.ocr`).
- Modify: `tests/conftest.py` — register `ocr` marker.

**Ф4 — Wire-in + packaging:**
- Modify: `convert.py` — extend `SUPPORTED_EXTS`, add image branch in `dispatch()`, replace `scanned-pdf` raise in `_do_pdf()` with `convert_pdf_scanned()` call (both with local `OcrError` → `ConversionError` translation).
- Modify: `SKILL.md` (description, paths, error rules).
- Modify: `README.md` (mention OCR + tessdata bundle).
- Modify: `install.sh` (rename, add `ocr.py` + `tessdata/` copy + post-check).
- Modify: `install.ps1` (same).
- Modify: `.github/workflows/ci.yml` (rename, install tesseract on Linux, add `verify-bundle` job).
- Create: `tests/test_scanned_pdf_no_longer_errors.py`.

## Contracts

### ocr.py — public interface

```python
from pathlib import Path

TESSDATA_DIR = Path(__file__).parent / "tessdata"

class OcrError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message

def convert_pdf_scanned(src: Path, total_pages: int) -> tuple[str, str]:
    """Return (markdown_body, "tesseract-ocr"). total_pages comes from caller's _pdf_probe()."""

def convert_image(src: Path) -> tuple[str, str]:
    """Return (markdown_body, "tesseract-ocr"). .webp routed through Pillow."""

def _materialize_for_tesseract(src: Path, tmpdir: Path) -> Path:
    """For .webp: PIL → tmpdir/<stem>.png; otherwise return src as-is.
    Raises OcrError('install-failed', ...) when Pillow missing on .webp."""

def _parse_tsv_page(tsv_text: str) -> tuple[str, float, int]:
    """Group words by (block_num, par_num, line_num); drop conf < 30.
    Returns (page_text, median_conf, word_count) — median over post-filter words.
    Empty input or fully filtered → ('', 0.0, 0)."""
```

### convert.py — dispatch site contracts

```python
# in _do_pdf(), scanned branch (replaces: raise ConversionError("scanned-pdf", ...)):
from ocr import convert_pdf_scanned, OcrError
try:
    body, backend = convert_pdf_scanned(src, info.total_pages)
except OcrError as e:
    raise ConversionError(e.kind, e.message) from e

# in dispatch(), new image branch (before unsupported-format raise):
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
if ext in IMAGE_EXTS:
    from ocr import convert_image, OcrError
    try:
        body, backend = convert_image(src)
    except OcrError as e:
        raise ConversionError(e.kind, e.message) from e
    return body, backend
```

### Output format

PDF OCR page block:

```
## Page N
<!-- ocr page=N conf=87 words=412 -->
<text>
```

Image OCR (no page heading):

```
<!-- ocr conf=91 words=234 -->
<text>
```

Low-confidence warnings to stderr (one per page/image, conversion continues):

```
WARN ocr-low-confidence: page N conf=55
WARN ocr-low-confidence: conf=45
```

Cache marker (first line of every `.md`):

```
<!-- mark-all-the-shit-down v0.1.0 | source: X | source_id: Y | src_mtime: Z | mtime: W | backend: tesseract-ocr -->
```

### Tesseract invocation

```
tesseract <input> stdout --tessdata-dir <skill-root>/tessdata -l rus+eng --psm 1 tsv
```

For PDFs: `pdftoppm -f N -l N -r 300 -gray <pdf> <tmpdir>/page` once per page, then locate the single `page-*.pgm` in `tmpdir`, OCR it, delete it.

## Test strategy

**Ф1 — Baseline + rename:**
- All ported tests from the original (unit + integration + corpus) must pass unchanged.
- New unit: `test_marker_prefix` — calls `marker_line(...)` and asserts substring `mark-all-the-shit-down` is in the result and `mark-the-stuff-down` is not.
- New unit: `test_grep_no_old_name` — reads `convert.py` as text, asserts forbidden patterns absent.

**Ф2 — tessdata:**
- Manual verification step: invoke `tesseract --tessdata-dir tessdata --list-langs` and confirm `rus`, `eng`, `osd` listed.

**Ф3 — ocr.py units:**
- `test_tsv_parsing` — feed a hand-crafted TSV header + word rows, assert grouping into lines/paragraphs and `conf < 30` filtering.
- `test_confidence_aggregation` — median computed after filtering; empty post-filter ⇒ `(0.0, 0)`.
- `test_materialize_passthrough` — non-`.webp` paths returned unchanged.
- `test_webp_pillow_fallback` — when Pillow is importable, `.webp` becomes a `.png` in `tmpdir`; when import is patched out, raises `OcrError("install-failed", ...)`.
- `test_convert_image_smoke` (`@pytest.mark.ocr`) — generate a PNG with `reportlab` containing the string `HELLO OCR`, run `convert_image`, assert returned markdown contains `HELLO` (case-insensitive) and backend `tesseract-ocr`. Skips if `tesseract` not on PATH.

What NOT to test:
- Exact OCR word-for-word accuracy on arbitrary scans (tesseract behaviour, not our code).
- pdftoppm output format details beyond "exactly one `page-*.pgm` produced".

**Ф4 — Integration + packaging:**
- `test_scanned_pdf_no_longer_errors` — synthesize an image-only PDF (reportlab drawing the same rasterized text), run `convert.py`, assert exit 0 and output `.md` contains `## Page 1`.
- Re-run full suite including original tests; nothing regresses.
- CI `verify-bundle` step — staging-dir mock-build + asserts every listed file present.

## Risks / unknowns / assumptions

- **Assumption:** `tesseract` binary is reachable as `tesseract` on PATH in target sandbox. If absent → `OcrError("ocr-failed", ...)`. Test environments must install it (CI Linux step).
- **Assumption:** `pdftoppm` from poppler-utils is on PATH (preinstalled in Cowork, available via apt in CI).
- **Assumption:** Pillow is importable in target Cowork env. If not, `.webp` errors cleanly — `.png/.jpg/.tiff/.bmp` keep working.
- **Risk:** `pdftoppm`'s numeric padding for output filenames is width-of-`total_pages` decimal digits; we sidestep guessing by globbing `page-*.pgm` and asserting exactly one match.
- **Risk:** binary `tessdata` files inflate the repo (~18-19 MB). Acceptable per spec; ensure they are committed (not `.gitignore`d) and present in the release bundle.
- **Risk:** `convert.py` is run as `__main__`; importing `convert.ConversionError` from `ocr.py` would create class-identity issues. Mitigated by `OcrError` + translation at dispatch sites.
- **Unknown:** corpus-generation tests may take long on CI. Inherited from original — no change here.

---

## Ф1: Fork base — copy original files + apply all rename diffs

**Files in this phase:**
- Create: `/Users/strigov/Documents/Claude/projects-сode/mark-all-the-shit-down/{convert.py,SKILL.md,README.md,LICENSE,install.sh,install.ps1,requirements-dev.txt}`
- Create: `.github/workflows/ci.yml`
- Create: entire `tests/` tree from upstream
- Modify: `convert.py` (rename diffs)
- Create: `tests/test_marker_prefix.py`, `tests/test_grep_no_old_name.py`

- [ ] **Step 1: Copy upstream skill files into new repo**

```bash
SRC=/Users/strigov/Documents/Claude/projects-сode/mark-the-shit-down
DST=/Users/strigov/Documents/Claude/projects-сode/mark-all-the-shit-down
cd "$DST"
cp "$SRC/convert.py" "$SRC/SKILL.md" "$SRC/README.md" "$SRC/LICENSE" \
   "$SRC/install.sh" "$SRC/install.ps1" "$SRC/requirements-dev.txt" .
mkdir -p .github/workflows
cp "$SRC/.github/workflows/ci.yml" .github/workflows/ci.yml
cp -R "$SRC/tests" tests
# strip caches
rm -rf tests/__pycache__ tests/.pytest_cache
ls -la
```

Expected: top-level lists `convert.py`, `ocr.py` (not yet), `tests/`, etc.

- [ ] **Step 1a: Rename ONLY the tests whose assertions cover convert.py behavior (updated in this phase)**

Several upstream tests embed the old skill name as assertion literals. We must split
them into two groups based on WHICH file the assertion targets:

**Group A — rename now (Ф1).** These tests assert content of `convert.py`'s output,
which IS rewritten in Steps 7-13 of this phase:
- `tests/test_output_path.py` — asserts marker startswith `<!-- mark-the-stuff-down v...`
- `tests/test_docx.py` — asserts marker startswith `<!-- mark-the-stuff-down v...`

**Group B — defer to Ф4.** These tests assert content of `SKILL.md`, `ci.yml`,
`install.sh`, `install.ps1` — none of which are modified in Ф1. Renaming their
expectations now would make them fail at Step 15 against still-old source files.
They will be renamed in Ф4 alongside the actual source updates:
- `tests/test_skill_md.py`
- `tests/test_ci_yml.py`
- `tests/test_install_sh.py`
- `tests/test_install_ps1.py`

Run the targeted rename (macOS BSD sed — note the `-i ''` two-arg form):

```bash
cd /Users/strigov/Documents/Claude/projects-сode/mark-all-the-shit-down
# Group A only — tests for convert.py behavior, which is renamed in this phase
grep -rl 'mark-the-stuff-down' tests/test_output_path.py tests/test_docx.py \
  | xargs sed -i '' 's/mark-the-stuff-down/mark-all-the-shit-down/g'
# Group B remains untouched here — those test files still assert the old strings,
# matching the still-old SKILL.md / ci.yml / install.sh / install.ps1.
```

Version literal `0.2.0` (the upstream `__version__`) does NOT currently appear inside
any upstream test file (`grep -rn '0\.2\.0' tests/` returns empty against the upstream
tree); the tests read `__version__` dynamically from `convert.py` via f-strings. So no
version-string rewrite inside tests is needed.

Key assertions after rename (illustrative):

```python
# tests/test_output_path.py (line ~25) and tests/test_docx.py (line ~56):
assert first.startswith(f"<!-- mark-all-the-shit-down v{cv.__version__}")
```

These edits intentionally happen on the copied tests (which now live in our repo and are
ours to maintain) BEFORE the convert.py rename diffs — so that after Steps 7-13 land,
those two test files match the new reality and `pytest -x -q` is green for them.
Group B is handled symmetrically in Ф4 once their source files are updated.

- [ ] **Step 2: Run upstream test suite (post selective test-rename, pre convert.py-rename) to establish a known baseline**

Run:

```bash
cd /Users/strigov/Documents/Claude/projects-сode/mark-all-the-shit-down
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -x -q
```

Expected: tests fail ONLY because `convert.py` still says `mark-the-stuff-down` —
specifically `test_output_path.py` and `test_docx.py` (whose expectations were
just updated in Step 1a to expect the new name) will mismatch the unrenamed
`convert.py`. Group B tests (`test_skill_md`, `test_ci_yml`, `test_install_sh`,
`test_install_ps1`) MUST still pass at this point because their expectations
were intentionally NOT renamed yet and the corresponding source files are
likewise still upstream-verbatim. Triage any OTHER failure before continuing.

The plan therefore relies on Steps 7-13 (rename diffs to `convert.py`) to bring
Group A back to green. Group B stays green throughout Ф1 (no Ф1 source change
touches the files they assert) and is migrated atomically in Ф4. Final
verification of Ф1's invariant happens in Step 15.

- [ ] **Step 3: Write `tests/test_marker_prefix.py` (failing first)**

```python
# tests/test_marker_prefix.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import convert  # noqa: E402


def test_marker_prefix_uses_new_name(tmp_path):
    # marker_line(src: Path, backend: str) — src must exist (it calls src.stat()).
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"fake")
    line = convert.marker_line(f, "text")
    assert line.startswith("<!-- mark-all-the-shit-down v0.1.0")
    assert "mark-the-stuff-down" not in line
    assert f"v{convert.__version__}" in line


def test_version_is_0_1_0():
    assert convert.__version__ == "0.1.0"
```

Note: upstream `marker_line()` signature is `marker_line(src: Path, backend: str) -> str`. The function calls `src.stat()`, so the input file must exist on disk — use `tmp_path` to materialize one. The first assertion (`startswith`) verifies both the new skill name and the new version in a single check.

- [ ] **Step 4: Run new test to confirm it FAILS**

```bash
pytest tests/test_marker_prefix.py -v
```

Expected: FAIL — assertion mismatch on `"mark-all-the-shit-down" in line` (upstream still says `mark-the-stuff-down`) and/or `__version__ == "0.1.0"`.

- [ ] **Step 5: Write `tests/test_grep_no_old_name.py` (failing first)**

```python
# tests/test_grep_no_old_name.py
import re
from pathlib import Path

CONVERT = Path(__file__).resolve().parents[1] / "convert.py"


def test_no_old_skill_name_in_convert():
    text = CONVERT.read_text(encoding="utf-8")
    assert "mark-the-stuff-down" not in text
    # Upstream's __version__ was "0.2.0"; the fork resets to "0.1.0".
    assert "0.2.0" not in text


def test_no_old_repo_slug_in_convert():
    text = CONVERT.read_text(encoding="utf-8")
    # \bmark-the-shit-down\b must not appear; mark-all-the-shit-down is OK
    assert re.search(r"(?<!-)\bmark-the-shit-down\b", text) is None


def test_new_marker_prefix_constant():
    text = CONVERT.read_text(encoding="utf-8")
    assert '"<!-- mark-all-the-shit-down v"' in text or \
           "'<!-- mark-all-the-shit-down v'" in text
```

- [ ] **Step 6: Run new test to confirm it FAILS**

```bash
pytest tests/test_grep_no_old_name.py -v
```

Expected: FAIL on both `mark-the-stuff-down not in text` and `0.2.0 not in text`.

- [ ] **Step 7: Apply rename diff #1 — module docstring (line ~2)**

Edit `convert.py` line 2.

Before:
```python
"""mark-the-stuff-down - convert office docs to Markdown."""
```

After:
```python
"""mark-all-the-shit-down - convert office docs to Markdown (with OCR)."""
```

- [ ] **Step 8: Apply rename diff #2 — `__version__` (line ~23)**

Before (current upstream value):
```python
__version__ = "0.2.0"
```

After (fork resets to fresh numbering):
```python
__version__ = "0.1.0"
```

- [ ] **Step 9: Apply rename diff #3 — `MARKER_PREFIX` (line ~23)**

Before:
```python
MARKER_PREFIX = "<!-- mark-the-stuff-down v"
```

After:
```python
MARKER_PREFIX = "<!-- mark-all-the-shit-down v"
```

- [ ] **Step 10: Apply rename diff #4 — `marker_line()` hardcoded literal (line ~147)**

Before (illustrative; the literal `"<!-- mark-the-stuff-down v"` is inlined inside `marker_line()`):
```python
def marker_line(...):
    ...
    return (
        f"<!-- mark-the-stuff-down v{__version__} | source: ..."
    )
```

After: route through the constant so future renames touch only one spot.
```python
def marker_line(...):
    ...
    return (
        f"{MARKER_PREFIX}{__version__} | source: ..."
    )
```

Use Read+Edit on the exact lines from the freshly copied `convert.py` — preserve all surrounding f-string content (the `| source: ... | source_id: ... | src_mtime: ... | mtime: ... | backend: ... -->` tail must remain byte-identical to the upstream).

- [ ] **Step 11: Apply rename diff #5 — CLI `--version` string (line ~1043)**

Before:
```python
parser.add_argument("--version", action="version",
                    version=f"mark-the-stuff-down {__version__}")
```

After:
```python
parser.add_argument("--version", action="version",
                    version=f"mark-all-the-shit-down {__version__}")
```

- [ ] **Step 12: Apply rename diff #6 — internal-error URL (line ~1095)**

Before:
```python
"... github.com/strigov/mark-the-shit-down/issues ..."
```

After:
```python
"... github.com/strigov/mark-all-the-shit-down/issues ..."
```

- [ ] **Step 13: Apply rename diff #7 — extend `SUPPORTED_EXTS`**

Locate the existing `SUPPORTED_EXTS` set/frozenset definition and add the seven image extensions. Keep alphabetical order if upstream uses it.

```python
SUPPORTED_EXTS = frozenset({
    # ... existing entries unchanged ...
    ".bmp",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
})
```

(Image dispatch logic itself is added in Ф4; Ф1 only widens the accepted-extension gate so the dispatcher doesn't reject images before we wire OCR.)

- [ ] **Step 14: Re-run rename tests to confirm GREEN**

```bash
pytest tests/test_marker_prefix.py tests/test_grep_no_old_name.py -v
```

Expected: PASS on all four assertions across both files.

- [ ] **Step 15: Run full suite — nothing else regressed**

```bash
pytest -x -q
```

Expected: all tests PASS. If a corpus or installer test references the old name, update its expected string (these are tests under our control inside `tests/`) — but do not introduce new logic. Document any such patch in the commit message.

- [ ] **Step 16: Commit**

```bash
cd /Users/strigov/Documents/Claude/projects-сode/mark-all-the-shit-down
git add convert.py SKILL.md README.md LICENSE install.sh install.ps1 \
        requirements-dev.txt .github/workflows/ci.yml tests
git commit -m "Ф1: fork mark-the-shit-down v0.1.1 as mark-all-the-shit-down v0.1.0

Copy upstream files verbatim, apply 7 rename diffs to convert.py
(docstring, __version__, MARKER_PREFIX, marker_line() literal,
--version CLI string, internal-error URL, SUPPORTED_EXTS extension),
add test_marker_prefix and test_grep_no_old_name to lock invariants."
```

---

## Ф2: Bundle tessdata

> **⚠️ LOCAL SETUP — runs on your development machine, not in Claude Cowork.**
> The tessdata download uses GitHub; once committed to the repo, the skill carries
> the files with it and needs no network access at runtime. Cowork's sandbox has no
> internet access — every command in this phase is executed on the developer's
> workstation during initial fork setup, and the resulting binaries are checked
> into git so the bundled skill is fully self-contained downstream.
>
> Optional but recommended: after the download, verify the files locally with
> `tesseract --tessdata-dir ./tessdata --list-langs` (or set `TESSDATA_PREFIX=./tessdata`)
> before committing, so a corrupted/partial download cannot poison the repo.

**Files in this phase:**
- Create: `tessdata/rus.traineddata`, `tessdata/eng.traineddata`, `tessdata/osd.traineddata`
- Modify: `.gitignore` (if needed) to keep `tessdata/` tracked

- [ ] **Step 1: Download three traineddata files from tessdata_fast (LOCAL DEV machine)**

```bash
cd /Users/strigov/Documents/Claude/projects-сode/mark-all-the-shit-down
mkdir -p tessdata
BASE="https://github.com/tesseract-ocr/tessdata_fast/raw/main"
for L in rus eng osd; do
  curl -fL --retry 3 -o "tessdata/${L}.traineddata" "${BASE}/${L}.traineddata"
done
ls -la tessdata
```

Expected: three files present, sizes roughly `rus ~4 MB`, `eng ~4 MB`, `osd ~10 MB` (total ~18-19 MB). If any download fails, abort.

- [ ] **Step 2: Verify tesseract can use the bundled tessdata**

```bash
tesseract --tessdata-dir ./tessdata --list-langs
```

Expected stdout contains exactly `eng`, `osd`, `rus` (order may vary). If tesseract is not on PATH locally, skip this manual step — CI will exercise it.

- [ ] **Step 3: Ensure `.gitignore` does not exclude tessdata**

Read existing `.gitignore` (if any). If it contains a line that would match `tessdata/` (e.g. `*.traineddata`, `tessdata/`), remove that line. Otherwise leave untouched.

- [ ] **Step 4: Write a tiny sanity test for bundle presence**

Create `tests/test_tessdata_bundle.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tessdata_bundle_present():
    tdir = ROOT / "tessdata"
    assert tdir.is_dir()
    for lang in ("rus", "eng", "osd"):
        f = tdir / f"{lang}.traineddata"
        assert f.is_file(), f"missing {f}"
        assert f.stat().st_size > 100_000, f"{f} suspiciously small"
```

- [ ] **Step 5: Run it**

```bash
pytest tests/test_tessdata_bundle.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tessdata/ tests/test_tessdata_bundle.py
# include .gitignore only if it was edited
git status --short | grep -q '\.gitignore' && git add .gitignore
git commit -m "Ф2: bundle tessdata_fast (rus+eng+osd, ~18 MB) into skill repo

OCR runtime points --tessdata-dir at this folder, making the skill
self-contained and independent of system tessdata layout."
```

---

## Ф3: ocr.py — module + unit tests

**Files in this phase:**
- Create: `ocr.py`
- Create: `tests/test_ocr.py`
- Modify: `tests/conftest.py` (register `ocr` marker)

- [ ] **Step 1: Register `ocr` pytest marker**

Edit `tests/conftest.py` — append (or merge with existing `pytest_configure`):

```python
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "ocr: integration tests that require the tesseract binary on PATH",
    )
```

If `conftest.py` already defines `pytest_configure`, merge the `addinivalue_line` call into the existing function.

- [ ] **Step 2: Write `tests/test_ocr.py` — TSV parsing test (failing first)**

```python
# tests/test_ocr.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest


SAMPLE_TSV = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
    "left\ttop\twidth\theight\tconf\ttext\n"
    # block 1, par 1, line 1: "Hello world" both high-conf
    "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t90\tHello\n"
    "5\t1\t1\t1\t1\t2\t0\t0\t10\t10\t88\tworld\n"
    # block 1, par 1, line 2: "noise" low-conf must be dropped
    "5\t1\t1\t1\t2\t1\t0\t0\t10\t10\t12\tnoise\n"
    # block 2, par 1, line 1: "second paragraph"
    "5\t1\t2\t1\t1\t1\t0\t0\t10\t10\t80\tsecond\n"
    "5\t1\t2\t1\t1\t2\t0\t0\t10\t10\t70\tparagraph\n"
)


def test_tsv_parsing_groups_and_filters():
    from ocr import _parse_tsv_page
    text, conf, words = _parse_tsv_page(SAMPLE_TSV)
    assert "Hello world" in text
    assert "second paragraph" in text
    assert "noise" not in text
    # paragraphs separated by blank line
    assert "world\n\nsecond" in text
    assert words == 4  # noise dropped
    # median of [90, 88, 80, 70] = 84.0
    assert conf == pytest.approx(84.0)


def test_tsv_parsing_empty_after_filter():
    from ocr import _parse_tsv_page
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
        "left\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t5\tjunk\n"
    )
    text, conf, words = _parse_tsv_page(tsv)
    assert text == ""
    assert conf == 0.0
    assert words == 0


def test_tsv_parsing_empty_input():
    from ocr import _parse_tsv_page
    text, conf, words = _parse_tsv_page("")
    assert (text, conf, words) == ("", 0.0, 0)


def test_materialize_passthrough(tmp_path):
    from ocr import _materialize_for_tesseract
    p = tmp_path / "x.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert _materialize_for_tesseract(p, tmp_path) == p


def test_materialize_webp_without_pillow(tmp_path, monkeypatch):
    import builtins
    from ocr import _materialize_for_tesseract, OcrError

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError("PIL not available")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    src = tmp_path / "x.webp"
    src.write_bytes(b"RIFF....WEBP")
    with pytest.raises(OcrError) as ei:
        _materialize_for_tesseract(src, tmp_path)
    assert ei.value.kind == "install-failed"
    assert "Pillow" in ei.value.message


def test_materialize_webp_with_pillow(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    from ocr import _materialize_for_tesseract

    src = tmp_path / "x.webp"
    Image.new("RGB", (8, 8), "white").save(src, format="WEBP")
    out = _materialize_for_tesseract(src, tmp_path)
    assert out.suffix == ".png"
    assert out.exists()


@pytest.mark.ocr
def test_convert_image_smoke(tmp_path):
    import shutil
    if not shutil.which("tesseract"):
        pytest.skip("tesseract not on PATH")
    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (480, 120), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 36)
    except OSError:
        font = ImageFont.load_default()
    d.text((10, 30), "HELLO OCR", fill="black", font=font)
    src = tmp_path / "hello.png"
    img.save(src)

    from ocr import convert_image
    body, backend = convert_image(src)
    assert backend == "tesseract-ocr"
    assert "HELLO" in body.upper()
    assert "<!-- ocr conf=" in body
    assert "## Page" not in body  # single image: no page heading
```

- [ ] **Step 3: Run tests to confirm they FAIL (no `ocr.py` yet)**

```bash
pytest tests/test_ocr.py -v
```

Expected: ImportError / ModuleNotFoundError for `ocr` on every test (collection-time error).

- [ ] **Step 4: Implement `ocr.py`**

Create `/Users/strigov/Documents/Claude/projects-сode/mark-all-the-shit-down/ocr.py`:

```python
"""OCR backend for mark-all-the-shit-down.

Self-contained: depends only on stdlib, the bundled tessdata/, the system
`tesseract` and `pdftoppm` binaries, and (for .webp) a runtime-imported PIL.
Does NOT import from convert.py to keep the module reusable and to avoid
class-identity issues when convert.py runs as __main__.
"""
from __future__ import annotations

import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

TESSDATA_DIR = Path(__file__).parent / "tessdata"
_CONF_FLOOR = 30
_LOW_CONF_THRESHOLD = 60
_TESS_LANGS = "rus+eng"
_PSM = "1"


class OcrError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


def _require_tesseract() -> str:
    exe = shutil.which("tesseract")
    if not exe:
        raise OcrError("ocr-failed", "tesseract binary not found on PATH")
    if not TESSDATA_DIR.is_dir():
        raise OcrError(
            "ocr-failed",
            f"bundled tessdata directory missing: {TESSDATA_DIR}",
        )
    return exe


def _require_pdftoppm() -> str:
    exe = shutil.which("pdftoppm")
    if not exe:
        raise OcrError("ocr-failed", "pdftoppm binary not found on PATH")
    return exe


def _run_tesseract_tsv(exe: str, input_path: Path) -> str:
    try:
        res = subprocess.run(
            [
                exe, str(input_path), "stdout",
                "--tessdata-dir", str(TESSDATA_DIR),
                "-l", _TESS_LANGS,
                "--psm", _PSM,
                "tsv",
            ],
            capture_output=True, text=True, check=False,
        )
    except OSError as e:
        raise OcrError("ocr-failed", f"tesseract invocation failed: {e}") from e
    if res.returncode != 0:
        raise OcrError(
            "ocr-failed",
            f"tesseract exited {res.returncode}: {res.stderr.strip()[:500]}",
        )
    return res.stdout


def _parse_tsv_page(tsv_text: str) -> tuple[str, float, int]:
    """Group words into lines/paragraphs and compute post-filter stats.

    Returns (page_text, median_conf, word_count).
    Words with conf < 30 are dropped. Median is computed over surviving
    words only. Empty input or fully filtered → ('', 0.0, 0).
    """
    if not tsv_text:
        return ("", 0.0, 0)
    lines = tsv_text.splitlines()
    if len(lines) <= 1:
        return ("", 0.0, 0)
    header = lines[0].split("\t")
    try:
        i_block = header.index("block_num")
        i_par = header.index("par_num")
        i_line = header.index("line_num")
        i_conf = header.index("conf")
        i_text = header.index("text")
    except ValueError:
        return ("", 0.0, 0)

    # ordered dict of (block, par) -> list[ list[word] ]
    paragraphs: dict[tuple[int, int], dict[int, list[str]]] = {}
    confs: list[int] = []
    for raw in lines[1:]:
        if not raw.strip():
            continue
        cols = raw.split("\t")
        if len(cols) <= max(i_block, i_par, i_line, i_conf, i_text):
            continue
        try:
            conf = int(float(cols[i_conf]))
        except ValueError:
            continue
        word = cols[i_text]
        if not word or not word.strip():
            continue
        if conf < _CONF_FLOOR:
            continue
        try:
            b = int(cols[i_block]); p = int(cols[i_par]); ln = int(cols[i_line])
        except ValueError:
            continue
        confs.append(conf)
        par = paragraphs.setdefault((b, p), {})
        par.setdefault(ln, []).append(word)

    if not confs:
        return ("", 0.0, 0)

    out_paragraphs: list[str] = []
    for (_b, _p), lines_dict in paragraphs.items():
        rendered_lines = [
            " ".join(words)
            for _ln, words in sorted(lines_dict.items())
            if words
        ]
        if rendered_lines:
            out_paragraphs.append("\n".join(rendered_lines))
    text = "\n\n".join(out_paragraphs)
    median_conf = float(statistics.median(confs))
    return (text, median_conf, len(confs))


def _materialize_for_tesseract(src: Path, tmpdir: Path) -> Path:
    if src.suffix.lower() != ".webp":
        return src
    try:
        from PIL import Image  # runtime import
    except ImportError as e:
        raise OcrError(
            "install-failed",
            "webp requires Pillow; not available in this environment",
        ) from e
    out = tmpdir / (src.stem + ".png")
    with Image.open(src) as im:
        im.convert("RGB").save(out, format="PNG")
    return out


def _warn(msg: str) -> None:
    sys.stderr.write(f"WARN ocr-low-confidence: {msg}\n")


def convert_image(src: Path) -> tuple[str, str]:
    exe = _require_tesseract()
    with tempfile.TemporaryDirectory(prefix="matsd-ocr-") as td:
        tmp = Path(td)
        target = _materialize_for_tesseract(src, tmp)
        tsv = _run_tesseract_tsv(exe, target)
    text, conf, words = _parse_tsv_page(tsv)
    conf_int = int(round(conf))
    if conf < _LOW_CONF_THRESHOLD:
        _warn(f"conf={conf_int}")
    body_lines = [f"<!-- ocr conf={conf_int} words={words} -->"]
    if text:
        body_lines.append(text)
    body = "\n".join(body_lines) + "\n"
    return body, "tesseract-ocr"


def convert_pdf_scanned(src: Path, total_pages: int) -> tuple[str, str]:
    tess = _require_tesseract()
    ppm = _require_pdftoppm()
    if total_pages <= 0:
        raise OcrError("ocr-failed", f"invalid total_pages={total_pages}")
    pages_md: list[str] = []
    with tempfile.TemporaryDirectory(prefix="matsd-pdf-") as td:
        tmp = Path(td)
        for n in range(1, total_pages + 1):
            stem = tmp / "page"
            try:
                res = subprocess.run(
                    [
                        ppm, "-f", str(n), "-l", str(n),
                        "-r", "300", "-gray",
                        str(src), str(stem),
                    ],
                    capture_output=True, text=True, check=False,
                )
            except OSError as e:
                raise OcrError(
                    "ocr-failed", f"pdftoppm failed on page {n}: {e}"
                ) from e
            if res.returncode != 0:
                raise OcrError(
                    "ocr-failed",
                    f"pdftoppm exited {res.returncode} on page {n}: "
                    f"{res.stderr.strip()[:300]}",
                )
            matches = sorted(tmp.glob("page-*.pgm"))
            if len(matches) != 1:
                raise OcrError(
                    "ocr-failed",
                    f"expected 1 page-*.pgm in tmpdir, found {len(matches)}",
                )
            pgm = matches[0]
            try:
                tsv = _run_tesseract_tsv(tess, pgm)
            finally:
                try:
                    pgm.unlink()
                except OSError:
                    pass
            text, conf, words = _parse_tsv_page(tsv)
            conf_int = int(round(conf))
            if conf < _LOW_CONF_THRESHOLD:
                _warn(f"page {n} conf={conf_int}")
            block = [
                f"## Page {n}",
                f"<!-- ocr page={n} conf={conf_int} words={words} -->",
            ]
            if text:
                block.append(text)
            pages_md.append("\n".join(block))
    return ("\n\n".join(pages_md) + "\n", "tesseract-ocr")
```

- [ ] **Step 5: Run unit tests — confirm GREEN (except the @pytest.mark.ocr one)**

```bash
pytest tests/test_ocr.py -v -m "not ocr"
```

Expected: all non-`ocr` tests PASS.

- [ ] **Step 6: Run integration smoke test (skipped if no tesseract)**

```bash
pytest tests/test_ocr.py::test_convert_image_smoke -v
```

Expected: PASS if `tesseract` available locally; SKIPPED otherwise.

- [ ] **Step 7: Commit**

```bash
git add ocr.py tests/test_ocr.py tests/conftest.py
git commit -m "Ф3: add ocr.py with OcrError, TSV parsing, image + PDF pipelines

- _parse_tsv_page groups by (block,par,line), drops conf<30, post-filter median
- _materialize_for_tesseract: runtime Pillow fallback for .webp → PNG
- convert_image: single-pass, emits <!-- ocr conf=N words=M --> + body
- convert_pdf_scanned: per-page pdftoppm -gray @300dpi, one PGM at a time
- WARN ocr-low-confidence emitted (non-fatal) when median <60
- Pillow import is lazy; tessdata path is bundled-only (no system fallback)
- Full unit-test coverage; integration smoke test marked @pytest.mark.ocr"
```

---

## Ф4: Wire OCR into convert.py + SKILL.md + installers + CI

**Files in this phase:**
- Modify: `convert.py` (image dispatch, scanned-PDF dispatch)
- Modify: `SKILL.md`, `README.md`
- Modify: `install.sh`, `install.ps1`
- Modify: `.github/workflows/ci.yml`
- Create: `tests/test_scanned_pdf_no_longer_errors.py`

- [ ] **Step 1: Write failing test — scanned PDF must no longer raise `ConversionError("scanned-pdf", ...)`**

Create `tests/test_scanned_pdf_no_longer_errors.py`:

```python
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _make_scanned_pdf(path: Path) -> None:
    """Build an image-only PDF: rasterized text drawn as an image."""
    PIL = pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1240, 1754), "white")  # ~A4 @150dpi
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 48)
    except OSError:
        font = ImageFont.load_default()
    d.text((100, 200), "HELLO OCR", fill="black", font=font)
    img.save(path, "PDF", resolution=150.0)


@pytest.mark.ocr
def test_scanned_pdf_converts(tmp_path):
    if not shutil.which("tesseract"):
        pytest.skip("tesseract not on PATH")
    if not shutil.which("pdftoppm"):
        pytest.skip("pdftoppm not on PATH")
    src = tmp_path / "scan.pdf"
    _make_scanned_pdf(src)

    res = subprocess.run(
        [sys.executable, str(ROOT / "convert.py"), str(src)],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, f"stderr={res.stderr}"
    out_md = src.with_suffix(".md")
    assert out_md.exists()
    body = out_md.read_text(encoding="utf-8")
    assert body.startswith("<!-- mark-all-the-shit-down v0.1.0 ")
    assert "## Page 1" in body
    assert "backend: tesseract-ocr" in body.splitlines()[0]
```

- [ ] **Step 2: Run it to confirm FAIL**

```bash
pytest tests/test_scanned_pdf_no_longer_errors.py -v
```

Expected: FAIL — convert.py still raises `ERROR scanned-pdf: ...` or skips (depending on env). The assertion `returncode == 0` fails.

- [ ] **Step 3: Patch `convert.py` — scanned-PDF dispatch**

Inside `_do_pdf()`, locate the branch that currently raises `ConversionError("scanned-pdf", ...)`. Replace with:

```python
# scanned PDF — route to OCR
from ocr import convert_pdf_scanned, OcrError
try:
    body, backend = convert_pdf_scanned(src, info.total_pages)
except OcrError as e:
    raise ConversionError(e.kind, e.message) from e
return body, backend
```

Preserve all surrounding control flow (the function's return contract `(body, backend)` matches what callers expect).

- [ ] **Step 4: Patch `convert.py` — image dispatch in `dispatch()`**

Add this branch in `dispatch()` BEFORE the "unsupported format" raise (and after any existing format-specific branches):

```python
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}

# inside dispatch():
if ext in IMAGE_EXTS:
    from ocr import convert_image, OcrError
    try:
        body, backend = convert_image(src)
    except OcrError as e:
        raise ConversionError(e.kind, e.message) from e
    return body, backend
```

`IMAGE_EXTS` may be defined at module-top alongside other constants if that fits the upstream style; if upstream uses a single dispatch table, add a corresponding entry there instead. Either way the import remains LOCAL (inside the branch).

- [ ] **Step 5: Re-run the scanned-PDF test — confirm GREEN**

```bash
pytest tests/test_scanned_pdf_no_longer_errors.py -v
```

Expected: PASS (or SKIP if tesseract/pdftoppm unavailable in local dev env; CI must run on Linux runner where both are installed).

- [ ] **Step 5a: Rename Group B test expectations (deferred from Ф1 Step 1a)**

These four test files assert content of `SKILL.md`, `.github/workflows/ci.yml`,
`install.sh`, `install.ps1` — source files that are still upstream-verbatim at
this point and that Steps 6-10 below are about to rewrite. Rename the test
expectations BEFORE updating the source files so that after Steps 6-10 land,
both sides of each assertion line up.

```bash
cd /Users/strigov/Documents/Claude/projects-сode/mark-all-the-shit-down
grep -rl 'mark-the-stuff-down' \
  tests/test_skill_md.py tests/test_ci_yml.py \
  tests/test_install_sh.py tests/test_install_ps1.py \
  | xargs sed -i '' 's/mark-the-stuff-down/mark-all-the-shit-down/g'
# Confirm zero remaining hits in these four files
! grep -n 'mark-the-stuff-down' tests/test_skill_md.py tests/test_ci_yml.py \
                                tests/test_install_sh.py tests/test_install_ps1.py
```

Key assertions after rename (illustrative):

```python
# tests/test_skill_md.py (line ~16):
assert "name: mark-all-the-shit-down" in fm

# tests/test_ci_yml.py (lines ~49-50):
assert "mark-all-the-shit-down-*.skill" in flat
assert "mark-all-the-shit-down-*.zip" in flat

# tests/test_install_sh.py (lines ~24, ~35):
stale_dest = tmp_path / ".local" / "share" / "mark-all-the-shit-down"
link = target_dir / "mark-all-the-shit-down"

# tests/test_install_ps1.py:
assert "mark-all-the-shit-down" in text
```

Run them and confirm they now FAIL (expected — sources not yet updated; Steps 6-10
will bring them back to green; Step 11 verifies):

```bash
pytest tests/test_skill_md.py tests/test_ci_yml.py \
       tests/test_install_sh.py tests/test_install_ps1.py -v
```

Expected: FAIL — assertion mismatches against still-old `SKILL.md`, `ci.yml`,
`install.sh`, `install.ps1`. After Steps 6-10 land, re-run:

```bash
pytest tests/test_skill_md.py tests/test_ci_yml.py \
       tests/test_install_sh.py tests/test_install_ps1.py -v
```

Expected at that point: PASS on all four.

- [ ] **Step 6: Update `SKILL.md`**

Edit `SKILL.md`. Specific changes:

- Change `name:` to `mark-all-the-shit-down`.
- Update `description:` to mention OCR (`rus+eng`) for scanned PDFs and images.
- Append the image extensions to `paths:` (`*.png`, `*.jpg`, `*.jpeg`, `*.tiff`, `*.tif`, `*.bmp`, `*.webp`).
- Add error rules:
  - `WARN ocr-low-confidence` — median confidence below 60%; non-fatal, surface to user.
  - `ERROR ocr-failed` — tesseract missing/failed or bundled tessdata absent; exit 1.
  - `ERROR install-failed` — only for `.webp` when Pillow is absent; exit 1.
- Remove the `ERROR scanned-pdf` rule.

- [ ] **Step 7: Update `README.md`**

Edit `README.md`. Specific changes:

- Replace skill name everywhere.
- Add a short OCR section listing supported image extensions, the runtime requirements (`tesseract` on PATH, optional Pillow for `.webp`), and note that tessdata is bundled.

- [ ] **Step 8: Update `install.sh`**

```bash
# line ~40
DEST=$HOME/.local/share/mark-all-the-shit-down

# line ~91 — git clone URL
git clone --depth=1 https://github.com/strigov/mark-all-the-shit-down "$TMP_SOURCE"

# line ~129 — symlink target name
target=$d/mark-all-the-shit-down

# line ~189 — final message
echo "mark-all-the-shit-down installed"
```

Add `ocr.py` to `RUNTIME_FILES`. **Critical:** the upstream `RUNTIME_FILES` is a
newline-separated string consumed by `printf '%s\n' "$RUNTIME_FILES" | while IFS= read -r file`.
Collapsing it into a single space-separated line breaks the loop (it would try to find a single
file literally named `"convert.py ocr.py SKILL.md README.md LICENSE"`). Keep the newline format:

Before (upstream, lines 41-44):
```sh
RUNTIME_FILES="convert.py
SKILL.md
README.md
LICENSE"
```

After:
```sh
RUNTIME_FILES="convert.py
ocr.py
SKILL.md
README.md
LICENSE"
```

Then patch `install_runtime_from_source()` to copy `tessdata/` **after** the RUNTIME_FILES loop
(the loop only handles files; `tessdata/` is a directory). Add the post-install check at the
end of the same function so every successful install — whether from `$MTSD_SOURCE` or the
`git clone` path — runs identical verification.

Before (upstream, lines 54-66):
```sh
install_runtime_from_source() {
  src=$1
  rm -rf "$DEST"
  mkdir -p "$DEST"
  printf '%s\n' "$RUNTIME_FILES" | while IFS= read -r file; do
    [ -n "$file" ] || continue
    if [ ! -f "$src/$file" ]; then
      echo "ERROR: missing runtime file: $file" >&2
      exit 1
    fi
    cp "$src/$file" "$DEST/$file"
  done
}
```

After:
```sh
install_runtime_from_source() {
  src=$1
  rm -rf "$DEST"
  mkdir -p "$DEST"
  printf '%s\n' "$RUNTIME_FILES" | while IFS= read -r file; do
    [ -n "$file" ] || continue
    if [ ! -f "$src/$file" ]; then
      echo "ERROR: missing runtime file: $file" >&2
      exit 1
    fi
    cp "$src/$file" "$DEST/$file"
  done
  if [ ! -d "$src/tessdata" ]; then
    echo "ERROR: missing tessdata directory" >&2
    exit 1
  fi
  cp -R "$src/tessdata" "$DEST/tessdata"
  for f in ocr.py tessdata/rus.traineddata tessdata/eng.traineddata tessdata/osd.traineddata; do
    if [ ! -f "$DEST/$f" ]; then
      echo "ERROR: post-install check failed; missing $DEST/$f" >&2
      exit 1
    fi
  done
}
```

- [ ] **Step 9: Update `install.ps1`**

Mirror the unix script. **Critical:** in the upstream `install.ps1`, the function parameter is
`$Source` (PascalCase, declared `param([string]$Source)`) and the module-level array is
`$RuntimeFiles` (PascalCase). Inside `Install-RuntimeFromSource` there is no `$src` variable —
using `$src` would silently expand to empty under StrictMode-off (or throw under StrictMode),
producing paths like `\tessdata`. All edits below use the actual upstream names.

```powershell
# line ~23
$Dest = Join-Path $HOME ".local\share\mark-all-the-shit-down"

# line ~24 — extend $RuntimeFiles (PascalCase, as upstream)
$RuntimeFiles = @("convert.py", "ocr.py", "SKILL.md", "README.md", "LICENSE")

# line ~62 — git clone URL
git clone --depth=1 https://github.com/strigov/mark-all-the-shit-down $tmpSource

# line ~99 — symlink-name
$target = Join-Path $d "mark-all-the-shit-down"

# line ~150 — final message
Write-Host "mark-all-the-shit-down installed"
```

Patch `Install-RuntimeFromSource` (upstream lines 26-43) to copy `tessdata/` and run the
post-install check after the file-copy loop. Use `$Source` (the function's actual parameter
name) and `$Dest` (module-level), built via `Join-Path` for cross-version safety:

```powershell
function Install-RuntimeFromSource {
  param(
    [string]$Source
  )

  if (Test-Path $Dest) {
    Remove-Item -Recurse -Force $Dest
  }
  New-Item -ItemType Directory -Force -Path $Dest | Out-Null

  foreach ($file in $RuntimeFiles) {
    $from = Join-Path $Source $file
    if (-not (Test-Path -Path $from -PathType Leaf)) {
      throw "ERROR: missing runtime file: $file"
    }
    Copy-Item -Force $from (Join-Path $Dest $file)
  }

  $tessdata_src = Join-Path $Source "tessdata"
  $tessdata_dst = Join-Path $Dest "tessdata"
  if (-not (Test-Path $tessdata_src)) {
    Write-Error "ERROR: missing tessdata directory"
    exit 1
  }
  Copy-Item -Recurse $tessdata_src $tessdata_dst

  foreach ($f in @("ocr.py", "tessdata\rus.traineddata", "tessdata\eng.traineddata", "tessdata\osd.traineddata")) {
    if (-not (Test-Path (Join-Path $Dest $f))) {
      Write-Error "post-install check failed; missing $Dest\$f"
      exit 1
    }
  }
}
```

- [ ] **Step 10: Update `.github/workflows/ci.yml`**

Concrete edits below. Note: the existing `release-skill` job packages the released
`.skill`/`.zip` bundle and currently lists ONLY `convert.py SKILL.md LICENSE README.md`
— after the fork it must also ship `ocr.py` AND the bundled `tessdata/` directory,
otherwise downloads of the released skill cannot OCR. The `verify-bundle` job added
here must check the SAME staging directory layout that `release-skill` produces (so
a packaging regression cannot slip past CI).

(a) Global rename — replace every `mark-the-stuff-down` with `mark-all-the-shit-down`
(job/step/artifact names — the upstream file has 4 occurrences in `release-skill`
alone: package dir, `.skill` artifact name, two `.zip`/glob lines, plus `release-skill`'s
own internal `pkg=` path).

(b) On Linux runners only, add a tesseract+poppler install before the test step in the
`test`, `preinstalled-fallback`, and `pip-fallback` jobs:

```yaml
- name: Install tesseract (Linux only)
  if: runner.os == 'Linux'
  run: |
    sudo apt-get update
    sudo apt-get install -y tesseract-ocr tesseract-ocr-rus poppler-utils
```

(c) **Patch the `release-skill` job to include `ocr.py` and `tessdata/`.**

Upstream `release-skill` step (`.github/workflows/ci.yml` lines 149-158) currently reads:

```yaml
      - name: Build release .skill / .zip bundle
        run: |
          mkdir -p dist
          staging=$(mktemp -d)
          pkg="$staging/mark-the-stuff-down"
          mkdir -p "$pkg"
          cp convert.py SKILL.md LICENSE README.md "$pkg/"
          (cd "$staging" && zip -r "mark-the-stuff-down-${TAG_NAME}.skill" mark-the-stuff-down)
          mv "$staging/mark-the-stuff-down-${TAG_NAME}.skill" dist/
          cp "dist/mark-the-stuff-down-${TAG_NAME}.skill" "dist/mark-the-stuff-down-${TAG_NAME}.zip"
```

Replace with (renamed slug + `ocr.py` + recursive `tessdata/` copy + post-stage
verification that fails the job if any required file is missing):

```yaml
      - name: Build release .skill / .zip bundle
        run: |
          set -euo pipefail
          mkdir -p dist
          staging=$(mktemp -d)
          pkg="$staging/mark-all-the-shit-down"
          mkdir -p "$pkg"
          cp convert.py ocr.py SKILL.md LICENSE README.md "$pkg/"
          cp -R tessdata "$pkg/tessdata"
          # Post-stage check — same file list that verify-bundle re-asserts.
          for f in convert.py ocr.py SKILL.md LICENSE README.md \
                   tessdata/rus.traineddata tessdata/eng.traineddata tessdata/osd.traineddata; do
            test -f "$pkg/$f" || { echo "MISSING IN STAGING: $f"; exit 1; }
          done
          (cd "$staging" && zip -r "mark-all-the-shit-down-${TAG_NAME}.skill" mark-all-the-shit-down)
          mv "$staging/mark-all-the-shit-down-${TAG_NAME}.skill" dist/
          cp "dist/mark-all-the-shit-down-${TAG_NAME}.skill" "dist/mark-all-the-shit-down-${TAG_NAME}.zip"
```

Also update the `softprops/action-gh-release` upload globs (upstream lines 163-165):

```yaml
          files: |
            dist/mark-all-the-shit-down-*.skill
            dist/mark-all-the-shit-down-*.zip
```

(d) Add a new `verify-bundle` job. **It must replay the exact same staging logic as
`release-skill` above** (same file list, same `pkg/` layout) so a drift between the
two is impossible — if `release-skill` is later modified, `verify-bundle` must be
updated in lockstep.

```yaml
  verify-bundle:
    name: verify-bundle
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Replay release-skill staging and verify contents
        run: |
          set -euo pipefail
          staging=$(mktemp -d)
          pkg="$staging/mark-all-the-shit-down"
          mkdir -p "$pkg"
          # Mirror the release-skill step exactly:
          cp convert.py ocr.py SKILL.md LICENSE README.md "$pkg/"
          cp -R tessdata "$pkg/tessdata"
          # Same required-files list as release-skill's post-stage check:
          for f in convert.py ocr.py SKILL.md LICENSE README.md \
                   tessdata/rus.traineddata tessdata/eng.traineddata tessdata/osd.traineddata; do
            test -f "$pkg/$f" || { echo "MISSING IN BUNDLE: $f"; exit 1; }
          done
          # Also verify the zip round-trips:
          (cd "$staging" && zip -qr bundle.zip mark-all-the-shit-down)
          unzip -q "$staging/bundle.zip" -d "$staging/unpacked"
          for f in convert.py ocr.py SKILL.md LICENSE README.md \
                   tessdata/rus.traineddata tessdata/eng.traineddata tessdata/osd.traineddata; do
            test -f "$staging/unpacked/mark-all-the-shit-down/$f" \
              || { echo "MISSING AFTER ROUND-TRIP: $f"; exit 1; }
          done
          echo "Bundle OK"
```

This job runs on every push/PR (unlike `release-skill`, which only runs on tags),
giving us continuous protection against omitting `ocr.py` or `tessdata/` from the
release archive.

(e) Update `tests/test_ci_yml.py` to reflect the new release-job contents. The upstream
test (lines 49-52) hard-codes the old artifact names — Step 5a above just migrated
`mark-the-stuff-down-*.skill/.zip` to `mark-all-the-shit-down-*.skill/.zip`,
but we additionally need the test to assert `ocr.py` and `tessdata` are mentioned in the
workflow. Extend it:

```python
# tests/test_ci_yml.py — append inside test_ci_yml_release_skill_job_on_tags:
    for name in ("convert.py", "ocr.py", "SKILL.md", "LICENSE", "README.md"):
        assert name in flat
    assert "tessdata" in flat
    assert "verify-bundle" in data["jobs"]
```

(f) Add a grep invariant step (in the `test` job, before `Run tests`). **Critical:** the upstream
`test` job runs on a matrix that includes Windows runners, where the default shell is PowerShell
(`pwsh`). Bash-syntax (`set -e`, leading `!` to negate exit codes, single-quoted regex) will not
parse under `pwsh`. Pin `shell: bash` so GitHub Actions uses Git Bash on Windows and `/bin/bash`
on Linux/macOS:

```yaml
- name: Grep — old names absent from convert.py
  shell: bash
  run: |
    set -e
    ! grep -n 'mark-the-stuff-down' convert.py
    ! grep -nE '(^|[^-])mark-the-shit-down' convert.py
    ! grep -n '0\.2\.0' convert.py
```

The `Install tesseract (Linux only)` step from (b) above is already gated by
`if: runner.os == 'Linux'` and so never runs on Windows — no `shell:` change needed there.
The `release-skill` patch in (c) and the new `verify-bundle` job in (d) both run on
`ubuntu-latest` only, so their bash bodies (with `set -euo pipefail`, `cp -R`, `mktemp -d`,
etc.) are safe as-is.

- [ ] **Step 10a: Migrate scanned-PDF expectations in `tests/test_pdf.py` and corpus**

The upstream `tests/test_pdf.py` and `tests/corpus/expected/Контракт от 25.05 — окончательная редакция.pdf.json` both still encode the old "scanned-pdf hard error" contract. After Steps 3-4 above, scanned PDFs succeed via OCR (or fail with `ocr-failed`, never `scanned-pdf`). Without this migration, the next step's `pytest -q` is guaranteed to fail on `test_dispatch_pdf_scanned_errors` and on the corpus-driven test that consumes the JSON expectation.

This is purely a test-side migration — no further changes to `convert.py` or `ocr.py`.

**A. Patch `tests/test_pdf.py` — replace `test_dispatch_pdf_scanned_errors`**

Upstream (lines 56-60, copied verbatim into our repo during Ф1):

```python
def test_dispatch_pdf_scanned_errors(run_convert, tmp_copy):
    src = tmp_copy(CORPUS / "Контракт от 25.05 — окончательная редакция.pdf")
    r = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r.returncode == 1
    assert "ERROR scanned-pdf" in r.stderr
```

Replace this single function with TWO functions (one for the OCR-success path, one for the no-tesseract fallback), and add the required `pytest`/`shutil` imports at the top of the file if they are not already present (upstream `tests/test_pdf.py` does not currently `import pytest` or `import shutil`):

```python
# Add to imports at top of tests/test_pdf.py if missing:
import shutil
import pytest


@pytest.mark.ocr
def test_dispatch_pdf_scanned_converts_via_ocr(run_convert, tmp_copy):
    """Scanned PDFs are no longer a hard error — they OCR successfully."""
    if not shutil.which("tesseract"):
        pytest.skip("tesseract not on PATH")
    if not shutil.which("pdftoppm"):
        pytest.skip("pdftoppm not on PATH")
    src = tmp_copy(CORPUS / "Контракт от 25.05 — окончательная редакция.pdf")
    r = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r.returncode == 0, r.stderr
    md = src.with_suffix(".md")
    body = md.read_text(encoding="utf-8")
    # First line is the cache marker; backend must be tesseract-ocr.
    first = body.splitlines()[0]
    assert first.startswith("<!-- mark-all-the-shit-down v0.1.0 ")
    assert "backend: tesseract-ocr" in first
    assert "## Page 1" in body


def test_dispatch_pdf_scanned_without_tesseract_is_ocr_failed(
    run_convert, tmp_copy, monkeypatch, tmp_path
):
    """When tesseract is unavailable, we surface ocr-failed (NOT scanned-pdf)."""
    if shutil.which("tesseract"):
        # Mask tesseract by giving the subprocess a PATH that excludes it.
        # tmp_path serves as an empty PATH directory.
        monkeypatch.setenv("PATH", str(tmp_path))
    src = tmp_copy(CORPUS / "Контракт от 25.05 — окончательная редакция.pdf")
    r = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r.returncode == 1
    assert "ERROR ocr-failed" in r.stderr
    assert "scanned-pdf" not in r.stderr
```

Note on the `monkeypatch.setenv("PATH", ...)` approach: this works only if `run_convert` (defined in upstream `tests/conftest.py`) propagates the parent process's environment into the subprocess it spawns. If `run_convert` instead builds a fresh env dict, change the second test to pass `env={"MTSD_FORCE_PREINSTALLED": "1", "PATH": str(tmp_path)}` explicitly. Inspect `conftest.py::run_convert` once during implementation and pick the form that matches.

**B. Patch `tests/generate_corpus.py` — update `_pdf_scanned()` expected JSON**

Upstream (lines 213-228, copied into our repo during Ф1):

```python
def _pdf_scanned():
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(
        str(ROOT / "Контракт от 25.05 — окончательная редакция.pdf"), pagesize=A4
    )
    c.setFillColorRGB(0.9, 0.9, 0.9)
    c.rect(50, 50, 500, 700, fill=1, stroke=0)
    c.showPage()
    c.save()
    _expected(
        "Контракт от 25.05 — окончательная редакция.pdf",
        exit_code=1,
        error_type="scanned-pdf",
    )
```

Replace the `_expected(...)` call with the OCR-success contract. OCR output on a near-blank gray rectangle is unpredictable (zero or a few low-confidence words), so the expectation must NOT assert on `min_markdown_length` or `required_substrings` — only on exit code and backend. Extend `_expected()` to accept (and emit) a new `backend` key for tests that want to assert it; the JSON keys upstream tests already understand (`exit_code`, `error_type`, `min_markdown_length`, `required_substrings`, `forbidden_substrings`) remain unchanged.

After:

```python
def _pdf_scanned():
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(
        str(ROOT / "Контракт от 25.05 — окончательная редакция.pdf"), pagesize=A4
    )
    c.setFillColorRGB(0.9, 0.9, 0.9)
    c.rect(50, 50, 500, 700, fill=1, stroke=0)
    c.showPage()
    c.save()
    # OCR now converts this successfully on environments with tesseract+pdftoppm.
    # Corpus-runner must guard this case behind @pytest.mark.ocr (see Step 10a/C).
    _expected(
        "Контракт от 25.05 — окончательная редакция.pdf",
        exit_code=0,
        backend="tesseract-ocr",
        requires_ocr=True,
    )
```

And extend `_expected()` (lines 25-35 in upstream) to carry the two new keys forward:

Before:
```python
def _expected(name: str, **kw):
    payload = {
        "exit_code": kw.get("exit_code", 0),
        "error_type": kw.get("error_type"),
        "min_markdown_length": kw.get("min_markdown_length", 0),
        "required_substrings": kw.get("required_substrings", []),
        "forbidden_substrings": kw.get("forbidden_substrings", []),
    }
```

After:
```python
def _expected(name: str, **kw):
    payload = {
        "exit_code": kw.get("exit_code", 0),
        "error_type": kw.get("error_type"),
        "min_markdown_length": kw.get("min_markdown_length", 0),
        "required_substrings": kw.get("required_substrings", []),
        "forbidden_substrings": kw.get("forbidden_substrings", []),
        "backend": kw.get("backend"),
        "requires_ocr": kw.get("requires_ocr", False),
    }
```

Then regenerate the expectation file in-place:

```bash
cd /Users/strigov/Documents/Claude/projects-сode/mark-all-the-shit-down
python tests/generate_corpus.py
```

This rewrites `tests/corpus/expected/Контракт от 25.05 — окончательная редакция.pdf.json` from the old shape:

```json
{
  "exit_code": 1,
  "error_type": "scanned-pdf",
  "min_markdown_length": 0,
  "required_substrings": [],
  "forbidden_substrings": []
}
```

to the new shape:

```json
{
  "exit_code": 0,
  "error_type": null,
  "min_markdown_length": 0,
  "required_substrings": [],
  "forbidden_substrings": [],
  "backend": "tesseract-ocr",
  "requires_ocr": true
}
```

Commit the regenerated JSON alongside the `generate_corpus.py` edit.

**C. Teach the corpus-driven test to honor `requires_ocr`**

Locate the corpus runner test (in upstream this is the file that iterates `tests/corpus/expected/*.json` and runs `convert.py` against each fixture — typically `tests/test_corpus.py` or similar; identify it during Ф1 Step 1 when the tests are first copied). The runner must:

1. Read `requires_ocr` from the expectation JSON (defaulting to `False` for backward compatibility — all other expectation files lack the key and continue to work unchanged).
2. When `requires_ocr` is `True`, skip the case unless `shutil.which("tesseract")` and `shutil.which("pdftoppm")` are both truthy. Use `pytest.skip(...)` from inside the parametrized test body, OR mark the parametrize entry with `pytest.param(..., marks=pytest.mark.ocr)` if the runner uses `pytest.mark.parametrize`.
3. When `backend` is present in the expectation, assert the cache-marker first line of the produced `.md` contains `backend: <value>`.

Minimal sketch (adapt to upstream runner's actual structure):

```python
# inside the per-fixture test body, after loading `expected` from JSON:
import shutil
if expected.get("requires_ocr"):
    if not (shutil.which("tesseract") and shutil.which("pdftoppm")):
        pytest.skip("requires tesseract+pdftoppm")
# ... run convert.py, capture result, read md ...
if expected.get("backend"):
    first_line = md_text.splitlines()[0]
    assert f"backend: {expected['backend']}" in first_line
```

If the runner uses `@pytest.mark.parametrize` over expectation files, also register the `ocr` marker on parametrize entries whose JSON has `requires_ocr: true` (the marker is already registered in `tests/conftest.py` per Ф3 Step 1).

**D. Verify the migration in isolation before the full suite**

```bash
cd /Users/strigov/Documents/Claude/projects-сode/mark-all-the-shit-down
pytest tests/test_pdf.py -v
pytest tests/test_pdf.py::test_dispatch_pdf_scanned_without_tesseract_is_ocr_failed -v
```

Expected: `test_dispatch_pdf_scanned_converts_via_ocr` passes (with tesseract) or skips (without); `test_dispatch_pdf_scanned_without_tesseract_is_ocr_failed` passes unconditionally — it never asserts OCR success, only that the failure mode is `ocr-failed` rather than the gone `scanned-pdf`.

- [ ] **Step 11: Run the full test suite**

```bash
pytest -q
```

Expected: all tests PASS (with `@pytest.mark.ocr` either passing on a machine with tesseract or skipping cleanly).

- [ ] **Step 12: Smoke-run CLI end-to-end on an image**

```bash
cd /Users/strigov/Documents/Claude/projects-сode/mark-all-the-shit-down
python - <<'PY'
from PIL import Image, ImageDraw, ImageFont
img = Image.new("RGB", (480, 120), "white")
d = ImageDraw.Draw(img)
try: font = ImageFont.truetype("DejaVuSans.ttf", 36)
except OSError: font = ImageFont.load_default()
d.text((10, 30), "HELLO OCR", fill="black", font=font)
img.save("/tmp/hello.png")
PY
python convert.py /tmp/hello.png
head -1 /tmp/hello.md
```

Expected: stdout shows `/tmp/hello.md (<size>)`; `head -1` shows the new marker prefix and `backend: tesseract-ocr`.

- [ ] **Step 13: Commit**

```bash
git add convert.py ocr.py SKILL.md README.md install.sh install.ps1 \
        .github/workflows/ci.yml tests/
git commit -m "feat: wire OCR into convert.py, update SKILL.md, installers, CI, and test suite

Ф4: wire OCR into convert.py dispatcher + update packaging & CI

- _do_pdf scanned branch now calls ocr.convert_pdf_scanned via local import
- dispatch() routes image extensions to ocr.convert_image
- Both sites translate OcrError → ConversionError to preserve __main__ class identity
- SKILL.md, README.md updated for new name, OCR rules, image inputs
- install.sh / install.ps1 ship ocr.py + tessdata/ with post-install checks
- CI installs tesseract+poppler on Linux, adds verify-bundle job and grep invariants
- New test_scanned_pdf_no_longer_errors confirms the formerly fatal path now succeeds"
```

---

## Self-review notes (kept inline)

- **Spec coverage:** every spec table row maps to a step — module docstring (Ф1 S7), `__version__` (S8), `MARKER_PREFIX` (S9), `marker_line()` literal (S10), CLI `--version` (S11), internal-error URL (S12), `SUPPORTED_EXTS` (S13), image dispatch (Ф4 S4), scanned-PDF dispatch (Ф4 S3), local-module import strategy (Ф4 S3/S4), installer rename + ocr.py + tessdata + post-check (Ф4 S8/S9), CI rename + tesseract install + verify-bundle + grep (Ф4 S10), grep invariants (Ф1 S5, Ф4 S10), tests enumerated in spec §4 (Ф1 S3/S5, Ф3 S2, Ф4 S1), `WARN ocr-low-confidence` (ocr.py `_warn`), `OcrError`/`install-failed`/`ocr-failed` (ocr.py), tessdata bundling and `--tessdata-dir` (Ф2 + ocr.py `TESSDATA_DIR`), per-page pdftoppm + glob (ocr.py `convert_pdf_scanned`), .webp Pillow fallback (ocr.py `_materialize_for_tesseract`).
- **Placeholders:** none — every step contains exact code, command, or expected output.
- **Type consistency:** `convert_pdf_scanned(Path, int) -> (str, str)` and `convert_image(Path) -> (str, str)` consistent between contract section, ocr.py implementation, and convert.py dispatch sites. `OcrError(kind, message)` consistent at raise sites and translation sites.
- **Acceptance criteria mapping:** AC1 → Ф4 S5 + Ф3; AC2 → Ф4 S12 + Ф3; AC3 → Ф1 S3/S14; AC4 → Ф1 S5/S14 + Ф4 S10; AC5 → ocr.py `_warn`; AC6 → ocr.py `_require_tesseract` + `_materialize_for_tesseract`; AC7 → Ф4 S10 (`verify-bundle`).
- **Frontmatter:** YAML valid; phase IDs Ф1-Ф4 match the four `## Фn:` headings below; first phase `in-progress`, others `pending`.
