import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CONVERT = REPO / "convert.py"
CORPUS = REPO / "tests" / "corpus"


@pytest.fixture
def run_convert():
    def _run(path, env=None, extra_args=()):
        full_env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        if env:
            full_env.update(env)
        return subprocess.run(
            [sys.executable, str(CONVERT), str(path), *extra_args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=full_env,
            timeout=60,
        )

    return _run


@pytest.fixture
def tmp_copy(tmp_path):
    def _copy(src):
        dst = tmp_path / Path(src).name
        shutil.copy2(src, dst)
        return dst

    return _copy


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "ocr: integration tests that require the tesseract binary on PATH",
    )
    config.addinivalue_line(
        "markers",
        "online: requires network and/or uv (skipped automatically when "
        "MTSD_FORCE_PREINSTALLED=1 is set on the runner shell)",
    )


def pytest_collection_modifyitems(config, items):
    if os.environ.get("MTSD_FORCE_PREINSTALLED") == "1":
        skip = pytest.mark.skip(reason="MTSD_FORCE_PREINSTALLED=1 (offline runner)")
        for it in items:
            if "online" in it.keywords:
                it.add_marker(skip)
