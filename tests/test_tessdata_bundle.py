from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tessdata_bundle_present():
    tdir = ROOT / "tessdata"
    assert tdir.is_dir()
    for lang in ("rus", "eng", "osd"):
        f = tdir / f"{lang}.traineddata"
        assert f.is_file(), f"missing {f}"
        assert f.stat().st_size > 100_000, f"{f} suspiciously small"
