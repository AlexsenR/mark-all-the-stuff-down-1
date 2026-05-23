import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import convert as cv  # noqa: E402


def _install_fake_striprtf(monkeypatch):
    package = types.ModuleType("striprtf")
    module = types.ModuleType("striprtf.striprtf")

    def rtf_to_text(raw):
        assert raw.startswith("{\\rtf")
        return "Постановление № 1234-р\nот 25 мая 2026 года"

    module.rtf_to_text = rtf_to_text
    monkeypatch.setitem(sys.modules, "striprtf", package)
    monkeypatch.setitem(sys.modules, "striprtf.striprtf", module)


def test_convert_rtf_direct_uses_striprtf(monkeypatch, tmp_path):
    _install_fake_striprtf(monkeypatch)
    src = tmp_path / "Постановление № 1234-р.rtf"
    src.write_text(r"{\rtf1\ansi test}", encoding="utf-8")

    body = cv._convert_rtf_direct(src)

    assert "Постановление № 1234-р" in body
    assert body.endswith("\n")


def test_rtf_markitdown_only_prefers_striprtf(monkeypatch, tmp_path):
    _install_fake_striprtf(monkeypatch)
    monkeypatch.delenv("MTSD_FORCE_PREINSTALLED", raising=False)
    monkeypatch.setattr(cv, "_ensure_pip_installed", lambda packages: False)
    src = tmp_path / "Постановление № 1234-р.rtf"
    src.write_text(r"{\rtf1\ansi test}", encoding="utf-8")

    body, backend = cv._do_markitdown_only(src, use_uv=False, fmt="rtf")

    assert backend == "striprtf"
    assert "Постановление № 1234-р" in body
