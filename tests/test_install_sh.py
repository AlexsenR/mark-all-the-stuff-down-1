import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
INSTALL = REPO / "install.sh"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell only")
def test_install_sh_exists_executable_and_posix_syntax():
    assert INSTALL.is_file()
    assert os.access(INSTALL, os.X_OK)
    r = subprocess.run(["sh", "-n", str(INSTALL)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell only")
def test_install_sh_dry_run_creates_skill_link(tmp_path, monkeypatch):
    target_dir = tmp_path / "fakeclaude" / "skills"
    target_dir.mkdir(parents=True)
    stale_dest = tmp_path / ".local" / "share" / "mark-the-stuff-down"
    (stale_dest / "tests").mkdir(parents=True)
    (stale_dest / ".git").mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MTSD_SKILL_TARGET", str(target_dir))
    monkeypatch.setenv("MTSD_DRY_RUN", "1")
    monkeypatch.setenv("MTSD_SOURCE", str(REPO))

    r = subprocess.run(["sh", str(INSTALL), "--no-uv"], capture_output=True, text=True)

    assert r.returncode == 0, r.stderr
    link = target_dir / "mark-the-stuff-down"
    assert link.exists()
    assert link.is_symlink()
    assert (link / "convert.py").is_file()
    assert (link / "SKILL.md").is_file()
    assert (link / "README.md").is_file()
    assert (link / "LICENSE").is_file()
    assert not (link / "tests").exists()
    assert not (link / ".git").exists()
    assert not (link / "requirements-dev.txt").exists()
    assert "Smoke test OK" not in r.stdout


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell only")
def test_install_sh_help_documents_supported_flags():
    r = subprocess.run(["sh", str(INSTALL), "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "--no-uv" in r.stdout
    assert "--only=claude|codex|pi" in r.stdout


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell only")
def test_install_sh_contains_prewarm_and_smoke_test():
    text = INSTALL.read_text(encoding="utf-8")
    assert "convert.py\" --version" in text
    assert "smoke.docx" in text
    assert "markitdown[docx,xlsx,pdf,pptx,xls,rtf,html,epub]" in text
    assert "pymupdf4llm" in text


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell only")
def test_install_sh_checks_python_version():
    text = INSTALL.read_text(encoding="utf-8")
    assert "sys.version_info >= (3, 10)" in text
    assert "Python 3.10+ is required" in text


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell only")
def test_install_sh_installs_runtime_files_only():
    text = INSTALL.read_text(encoding="utf-8")
    assert "RUNTIME_FILES=" in text
    assert "install_runtime_from_source" in text
    assert 'cp -R "$SOURCE_DIR"/.' not in text
