import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import convert  # noqa: E402


def test_marker_prefix_uses_new_name(tmp_path):
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"fake")
    line = convert.marker_line(f, "text")
    assert line.startswith(f"<!-- mark-all-the-stuff-down v{convert.__version__}")
    assert "shit" not in line
    assert f"v{convert.__version__}" in line


def test_version_is_0_1_1():
    assert convert.__version__ == "0.1.1"
