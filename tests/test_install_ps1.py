import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INSTALL_PS1 = REPO / "install.ps1"


def test_install_ps1_exists():
    assert INSTALL_PS1.is_file()


def test_install_ps1_configures_utf8_and_no_uv():
    text = INSTALL_PS1.read_text(encoding="utf-8")
    assert "65001" in text
    assert "UTF8Encoding" in text
    assert "[switch]$NoUv" in text
    assert "--no-uv" in text


def test_install_ps1_links_skill_with_junction():
    text = INSTALL_PS1.read_text(encoding="utf-8")
    assert "New-Item" in text
    assert "Junction" in text
    assert "mark-all-the-stuff-down" in text
    assert "mark-all-the-shit-down" in text


def test_install_ps1_contains_prewarm_and_smoke_test():
    text = INSTALL_PS1.read_text(encoding="utf-8")
    assert "convert.py" in text
    assert "--version" in text
    assert "smoke.docx" in text
    assert "markitdown[docx,xlsx,pdf,pptx,xls,rtf,html,epub]" in text
    assert "pymupdf4llm" in text


def test_install_ps1_checks_native_command_exit_codes():
    text = INSTALL_PS1.read_text(encoding="utf-8")
    assert "function Assert-ExitCode" in text
    for action in (
        "python version check",
        "git clone",
        "uv tool install",
        "python -m pip install",
        "python convert.py --version",
        "python smoke conversion",
    ):
        assert f'Assert-ExitCode "{action}"' in text


def test_install_ps1_checks_python_version():
    text = INSTALL_PS1.read_text(encoding="utf-8")
    assert "sys.version_info >= (3, 10)" in text
    assert "Python 3.10+ is required" in text


def test_install_ps1_installs_runtime_files_only():
    text = INSTALL_PS1.read_text(encoding="utf-8")
    assert "$RuntimeFiles" in text
    assert "Install-RuntimeFromSource" in text
    for name in ("convert.py", "ocr.py", "SKILL.md", "README.md", "LICENSE"):
        assert f'"{name}"' in text
    assert "tessdata\\rus.traineddata" in text
    assert "tessdata\\eng.traineddata" in text
    assert "tessdata\\osd.traineddata" in text
    assert 'Copy-Item -Recurse -Force (Join-Path $SourceOverride "*") $Dest' not in text


def test_install_ps1_syntax_when_powershell_available():
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        return
    command = (
        "$tokens=$null;$errors=$null;"
        f"[System.Management.Automation.Language.Parser]::ParseFile('{INSTALL_PS1}',"
        "[ref]$tokens,[ref]$errors) | Out-Null;"
        "if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Error $_ }; exit 1 }"
    )
    r = subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr + r.stdout
