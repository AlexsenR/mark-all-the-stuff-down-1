"""Ensure the converter never emits LLM-generated text for images."""
from pathlib import Path
import re

LLM_SIGNATURE_PATTERNS = [
    r"\bthis image (shows|depicts)\b",
    r"\bthe image (shows|depicts|appears)\b",
    r"\ba photo of\b",
    r"\bна изображении\b",
    r"\bphoto shows\b",
]

CORPUS = Path(__file__).resolve().parent / "corpus"


def test_pptx_with_images_contains_no_llm_caption(run_convert, tmp_copy):
    # IMPORTANT: do NOT pass MTSD_FORCE_PREINSTALLED here. The whole point of
    # this smoke test is to exercise the real markitdown/uvx code path (where
    # any --llm flag would surface) and verify no LLM-generated captions leak
    # into the markdown. The CI no-llm-smoke job runs this under `unshare -rn`
    # so no network is available, but uv and the prewarmed markitdown tool
    # venv are still reachable.
    src = tmp_copy(CORPUS / "Презентация с картинками.pptx")
    r = run_convert(src)
    assert r.returncode == 0, r.stderr
    text = src.with_suffix(".md").read_text(encoding="utf-8").lower()
    for pat in LLM_SIGNATURE_PATTERNS:
        assert not re.search(pat, text), f"matched LLM signature pattern: {pat}"


def test_markitdown_snippet_does_not_pass_llm_args():
    import convert as cv

    assert "llm_client" not in cv.MIT_SNIPPET
    assert "llm_model" not in cv.MIT_SNIPPET
    assert "--llm" not in cv.MIT_SNIPPET


def test_uvx_markitdown_command_does_not_pass_llm_args(monkeypatch, tmp_path):
    import convert as cv

    captured = {}

    def fake_run_child(cmd, **kwargs):
        captured["cmd"] = cmd

        class R:
            returncode = 0
            stdout = "# ok\n"
            stderr = ""

        return R()

    monkeypatch.setenv("MTSD_FORCE_PREINSTALLED", "1")
    monkeypatch.setattr(cv, "_run_child", fake_run_child)

    src = tmp_path / "slides.pptx"
    src.write_bytes(b"pptx")
    body = cv._convert_via_markitdown_uvx(src, "pptx")

    assert body == "# ok\n"
    cmd = captured["cmd"]
    forbidden = {"--llm-client", "--llm-model", "--llm"}
    assert not any(arg in forbidden or arg.startswith("--llm-") for arg in cmd)
    assert not any("llm_client" in arg or "llm_model" in arg for arg in cmd)
