import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONVERT = REPO / "convert.py"

sys.path.insert(0, str(REPO))
import convert as cv  # noqa: E402


def test_convert_exists():
    assert CONVERT.is_file()


def test_convert_prints_version():
    r = subprocess.run(
        [sys.executable, str(CONVERT), "--version"], capture_output=True, text=True
    )
    assert r.returncode == 0
    assert cv.__version__ in r.stdout


def test_convert_no_args_exits_2_with_usage():
    r = subprocess.run([sys.executable, str(CONVERT)], capture_output=True, text=True)
    assert r.returncode == 2
    assert "usage" in r.stderr.lower() or "ERROR" in r.stderr


def test_convert_too_large_error(tmp_path):
    big = tmp_path / "huge.pdf"
    # 50_000_001 bytes > MAX_BYTES (50_000_000, decimal units)
    big.write_bytes(b"%PDF-1.4\n" + b"x" * (50_000_001 - 9))
    r = subprocess.run([sys.executable, str(CONVERT), str(big)], capture_output=True, text=True)
    assert r.returncode == 1
    assert "ERROR too-large" in r.stderr


def test_convert_batch_runs_in_parallel_and_outputs_input_order(
    tmp_path, monkeypatch, capsys
):
    first = tmp_path / "first.html"
    second = tmp_path / "second.html"
    first.write_text("<h1>first</h1>", encoding="utf-8")
    second.write_text("<h1>second</h1>", encoding="utf-8")

    barrier = threading.Barrier(2)
    active = 0
    max_active = 0
    lock = threading.Lock()

    def fake_dispatch(src, *, no_uv):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        try:
            barrier.wait(timeout=1)
            time.sleep(0.01)
            return f"# {src.stem}\n", "fake"
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(cv, "dispatch", fake_dispatch)

    rc = cv.main(["--jobs", "2", str(first), str(second)])
    captured = capsys.readouterr()

    assert rc == 0
    assert max_active == 2
    assert captured.err == ""
    assert captured.out.splitlines() == [
        cv.success_line(first.with_suffix(".md")),
        cv.success_line(second.with_suffix(".md")),
    ]


def test_convert_batch_serializes_same_stem_output_collision(
    tmp_path, monkeypatch, capsys
):
    pdf = tmp_path / "contract.pdf"
    docx = tmp_path / "contract.docx"
    pdf.write_bytes(b"%PDF-1.4 test")
    docx.write_bytes(b"docx placeholder")

    def fake_dispatch(src, *, no_uv):
        return f"# {src.name}\n", "fake"

    monkeypatch.setattr(cv, "dispatch", fake_dispatch)

    rc = cv.main(["--jobs", "2", str(pdf), str(docx)])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    assert captured.out.splitlines() == [
        cv.success_line(tmp_path / "contract.md"),
        cv.success_line(tmp_path / "contract.mtsd.md"),
    ]
    assert (tmp_path / "contract.md").read_text(encoding="utf-8").splitlines()[0]
    assert (tmp_path / "contract.mtsd.md").read_text(encoding="utf-8").splitlines()[0]
