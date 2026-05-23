import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import convert as cv  # noqa: E402


def _read_last_log_line(monkeypatch, tmp_path):
    # cv._log_path() reads from _cache_root(); we redirect cache root to tmp_path
    if sys.platform == "win32":
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        log_path = tmp_path / "mtsd" / "log.jsonl"
    else:
        monkeypatch.setenv("HOME", str(tmp_path))
        log_path = tmp_path / ".cache" / "mtsd" / "log.jsonl"
    return log_path


def test_log_event_silent_when_unset(capsys, tmp_path, monkeypatch):
    log_path = _read_last_log_line(monkeypatch, tmp_path)
    src = tmp_path / "Договор.pdf"
    src.write_bytes(b"x")
    monkeypatch.delenv("MTSD_LOG", raising=False)
    cv.log_event(src, backend="x", duration_ms=1, size_kb=1, exit_code=0)
    captured = capsys.readouterr()
    assert captured.err == ""
    assert not log_path.exists()


def test_log_event_default_hides_path(capsys, tmp_path, monkeypatch):
    log_path = _read_last_log_line(monkeypatch, tmp_path)
    src = tmp_path / "Договор.pdf"
    src.write_bytes(b"x")
    monkeypatch.setenv("MTSD_LOG", "1")
    monkeypatch.delenv("MTSD_LOG_VERBOSE", raising=False)
    cv.log_event(src, backend="pdfplumber", duration_ms=42, size_kb=10, exit_code=0)
    # nothing on stderr
    assert capsys.readouterr().err == ""
    # JSONL line appended to log file
    assert log_path.is_file()
    line = log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    rec = json.loads(line)
    assert "path" not in rec
    assert rec["path_hash"] and len(rec["path_hash"]) == 16
    assert rec["backend"] == "pdfplumber"
    assert rec["exit"] == 0


def test_log_event_verbose_includes_path(capsys, tmp_path, monkeypatch):
    log_path = _read_last_log_line(monkeypatch, tmp_path)
    src = tmp_path / "Договор.pdf"
    src.write_bytes(b"x")
    monkeypatch.setenv("MTSD_LOG", "1")
    monkeypatch.setenv("MTSD_LOG_VERBOSE", "1")
    cv.log_event(src, backend="b", duration_ms=1, size_kb=1, exit_code=0)
    assert capsys.readouterr().err == ""
    line = log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    rec = json.loads(line)
    assert rec["path"].endswith("Договор.pdf")
    assert "path_hash" in rec


def test_log_event_appends_jsonl(tmp_path, monkeypatch):
    log_path = _read_last_log_line(monkeypatch, tmp_path)
    src = tmp_path / "a.pdf"
    src.write_bytes(b"x")
    monkeypatch.setenv("MTSD_LOG", "1")
    cv.log_event(src, backend="b1", duration_ms=1, size_kb=1, exit_code=0)
    cv.log_event(src, backend="b2", duration_ms=2, size_kb=1, exit_code=0)
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["backend"] == "b1"
    assert json.loads(lines[1])["backend"] == "b2"
