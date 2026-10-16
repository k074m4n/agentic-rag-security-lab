import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CODEBASE = REPO_ROOT / "data" / "sample_codebase"


@pytest.fixture(autouse=True)
def no_throttle(monkeypatch):
    """The global RPM limiter sleeps between calls; tests never hit a real LLM."""
    from agents import common

    monkeypatch.setattr(common.rate_limiter, "interval", 0.0)


@pytest.fixture
def codebase(tmp_path) -> Path:
    """A private copy of the sample codebase, so tests can't mutate the tracked one."""
    dst = tmp_path / "codebase"
    shutil.copytree(SAMPLE_CODEBASE, dst, ignore=shutil.ignore_patterns("__pycache__"))
    return dst


@pytest.fixture
def workspace(tmp_path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws
