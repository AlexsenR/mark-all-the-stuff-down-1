import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import convert as cv  # noqa: E402

CORPUS = Path(__file__).resolve().parent / "corpus"


def test_second_call_does_not_rewrite_md(run_convert, tmp_copy):
    src = tmp_copy(CORPUS / "simple_letter.docx")
    r1 = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r1.returncode == 0, r1.stderr
    md = src.with_suffix(".md")
    mtime1 = md.stat().st_mtime
    time.sleep(0.05)
    r2 = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r2.returncode == 0, r2.stderr
    assert md.stat().st_mtime == mtime1, "md should not be rewritten"
    assert str(md) in r2.stdout


def test_modified_source_triggers_rewrite(run_convert, tmp_copy):
    src = tmp_copy(CORPUS / "simple_letter.docx")
    r1 = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r1.returncode == 0
    md = src.with_suffix(".md")
    md_mtime_1 = md.stat().st_mtime
    # bump source mtime into the future
    new_t = md_mtime_1 + 10
    os.utime(src, (new_t, new_t))
    r2 = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r2.returncode == 0
    assert md.stat().st_mtime >= new_t


def test_source_mtime_marker_detects_edit_before_future_mtime_passes(
    run_convert, tmp_copy
):
    src = tmp_copy(CORPUS / "simple_letter.docx")
    future_t = time.time() + 3600
    os.utime(src, (future_t, future_t))

    r1 = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r1.returncode == 0, r1.stderr
    md = src.with_suffix(".md")
    assert cv.is_up_to_date(src, md) is True

    current_t = time.time()
    os.utime(src, (current_t, current_t))
    assert md.stat().st_mtime > src.stat().st_mtime
    assert cv.is_up_to_date(src, md) is False
