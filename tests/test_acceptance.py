"""End-to-end acceptance covering §6 contract for each corpus file.

Two scenarios:
  * online   -- full backend chain available (uv + network or prewarmed uv tool).
               XLS/RTF/EPUB MUST convert successfully via markitdown[<fmt>].
               Uses `<name>.json` expected file.
  * offline  -- MTSD_FORCE_PREINSTALLED=1, no uv, no network.
               XLS/RTF/EPUB are expected to fail with install-failed.
               Uses `<name>.preinstalled.json` if it exists, else `<name>.json`.

The two scenarios run as separate parametrized cases so a failure in one does
not mask the other.
"""
import json
import re
import shutil
from pathlib import Path

import pytest

CORPUS = Path(__file__).resolve().parent / "corpus"
EXPECTED = CORPUS / "expected"


def _online_cases():
    # All non-".preinstalled" expected files are the online scenario.
    for j in sorted(EXPECTED.glob("*.json")):
        if j.stem.endswith(".preinstalled"):
            continue
        spec = json.loads(j.read_text(encoding="utf-8"))
        marks = [pytest.mark.ocr] if spec.get("requires_ocr") else []
        yield pytest.param(j.stem, id=f"online::{j.stem}", marks=marks)


def _offline_cases():
    # For each fixture: if a "<name>.preinstalled.json" exists, use that;
    # otherwise the offline expectation equals the online one (same behavior).
    for j in sorted(EXPECTED.glob("*.json")):
        if j.stem.endswith(".preinstalled"):
            continue
        name = j.stem
        pre = EXPECTED / f"{name}.preinstalled.json"
        spec_name = pre.stem if pre.is_file() else name
        spec = json.loads((EXPECTED / f"{spec_name}.json").read_text(encoding="utf-8"))
        marks = [pytest.mark.ocr] if spec.get("requires_ocr") else []
        yield pytest.param(name, spec_name, id=f"offline::{name}", marks=marks)


def _skip_if_missing_ocr(spec: dict):
    if spec.get("requires_ocr") and not (
        shutil.which("tesseract") and shutil.which("pdftoppm")
    ):
        pytest.skip("requires tesseract+pdftoppm")


def _assert_against_spec(spec: dict, r, md_path: Path):
    assert r.returncode == spec["exit_code"], (
        f"exit {r.returncode} != {spec['exit_code']}; stderr={r.stderr}"
    )
    if spec.get("error_type"):
        assert f"ERROR {spec['error_type']}" in r.stderr
        assert r.stdout == ""
        return
    assert md_path.is_file()
    text = md_path.read_text(encoding="utf-8")
    if spec.get("backend"):
        first_line = text.splitlines()[0]
        assert f"backend: {spec['backend']}" in first_line
    assert len(text) >= spec.get("min_markdown_length", 0)
    for sub in spec.get("required_substrings", []):
        assert sub in text, f"missing required substring: {sub!r}"
    for sub in spec.get("forbidden_substrings", []):
        assert sub not in text, f"forbidden substring present: {sub!r}"


def _assert_stdout_contract(r, md_path: Path):
    out_lines = r.stdout.splitlines()
    assert len(out_lines) == 1
    line = out_lines[0]
    path_text, size_text = line.rsplit(" (", 1)
    assert path_text == str(md_path)
    assert Path(path_text).suffix == ".md"
    assert re.fullmatch(r"\d+(?:\.\d+)? (KB|MB)\)", size_text)
    byte_count = md_path.stat().st_size
    assert byte_count > 0
    expected_size = (
        f"{byte_count / 1000:.1f} KB"
        if byte_count < 10 * 1000 * 1000
        else f"{byte_count / 1_000_000:.1f} MB"
    )
    assert line == f"{md_path} ({expected_size})"


@pytest.mark.online
@pytest.mark.parametrize("name", list(_online_cases()))
def test_acceptance_online(name, run_convert, tmp_copy):
    """Online: full backend chain. XLS/RTF/EPUB must convert successfully."""
    spec = json.loads((EXPECTED / f"{name}.json").read_text(encoding="utf-8"))
    _skip_if_missing_ocr(spec)
    src = tmp_copy(CORPUS / name)
    # No MTSD_FORCE_PREINSTALLED -- exercise uvx / pip / direct in order.
    r = run_convert(src)
    md = src.with_suffix(".md")
    _assert_against_spec(spec, r, md)
    if not spec.get("error_type"):
        _assert_stdout_contract(r, md)


@pytest.mark.parametrize("name,spec_name", list(_offline_cases()))
def test_acceptance_offline(name, spec_name, run_convert, tmp_copy):
    """Offline / preinstalled-only: XLS/RTF/EPUB -> install-failed."""
    spec = json.loads((EXPECTED / f"{spec_name}.json").read_text(encoding="utf-8"))
    _skip_if_missing_ocr(spec)
    src = tmp_copy(CORPUS / name)
    r = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    md = src.with_suffix(".md")
    _assert_against_spec(spec, r, md)
    if not spec.get("error_type"):
        _assert_stdout_contract(r, md)
