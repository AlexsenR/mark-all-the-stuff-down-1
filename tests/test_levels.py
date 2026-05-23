import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import convert as cv  # noqa: E402


def test_have_uv_respects_no_uv_flag(monkeypatch):
    monkeypatch.delenv("MTSD_FORCE_PREINSTALLED", raising=False)
    monkeypatch.setattr(cv.shutil, "which", lambda _: "/usr/local/bin/uv")
    assert cv._have_uv(no_uv=False) is True
    assert cv._have_uv(no_uv=True) is False


def test_have_uv_false_when_missing(monkeypatch):
    monkeypatch.delenv("MTSD_FORCE_PREINSTALLED", raising=False)
    monkeypatch.setattr(cv.shutil, "which", lambda _: None)
    assert cv._have_uv(no_uv=False) is False


def test_force_preinstalled_disables_uv_and_network(monkeypatch):
    monkeypatch.setenv("MTSD_FORCE_PREINSTALLED", "1")
    monkeypatch.setattr(cv.shutil, "which", lambda _: "/usr/local/bin/uv")
    assert cv._have_uv(no_uv=False) is False
    assert cv._have_network() is False


def test_run_child_passes_utf8_env(monkeypatch):
    captured = {}

    def fake_run(cmd, **kw):
        captured["env"] = kw["env"]
        captured["cmd"] = cmd

        class R:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return R()

    monkeypatch.setattr(cv.subprocess, "run", fake_run)
    cv._run_child(["echo", "hi"], timeout=5)
    env = captured["env"]
    assert env["LC_ALL"] == "en_US.UTF-8"
    assert env["LANG"] == "en_US.UTF-8"
    assert env["PYTHONIOENCODING"] == "utf-8"
