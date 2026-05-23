from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

CI = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"


def _workflow():
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


def _on(data):
    return data.get("on", data.get(True, {}))


def test_ci_yml_exists():
    assert CI.is_file()


def test_ci_yml_has_windows_and_python_matrix():
    data = _workflow()
    matrix = data["jobs"]["test"]["strategy"]["matrix"]
    assert "windows-latest" in matrix["os"]
    assert {"3.10", "3.11", "3.12"} <= set(map(str, matrix["python-version"]))


def test_ci_yml_has_preinstalled_fallback_job():
    data = _workflow()
    job = data["jobs"]["preinstalled-fallback"]
    assert job["env"]["MTSD_FORCE_PREINSTALLED"] == "1"
    assert 'pytest -q -m "not online"' in CI.read_text(encoding="utf-8")


def test_ci_yml_has_no_llm_smoke_job():
    data = _workflow()
    assert "no-llm-smoke" in data["jobs"]
    assert "tests/test_no_llm.py" in CI.read_text(encoding="utf-8")


def test_ci_yml_release_skill_job_on_tags():
    data = _workflow()
    assert "release-skill" in data["jobs"]
    push = _on(data)["push"]
    assert push["tags"] == ["v*"]
    flat = CI.read_text(encoding="utf-8")
    assert "softprops/action-gh-release" in flat
    assert "mark-all-the-shit-down-*.skill" in flat
    assert "mark-all-the-shit-down-*.zip" in flat
    for name in ("convert.py", "ocr.py", "SKILL.md", "LICENSE", "README.md"):
        assert name in flat
    assert "tessdata" in flat
    assert "verify-bundle" in data["jobs"]
