import os
import subprocess
import sys

import pytest

from tests.conftest import REPO_ROOT
from toolkits import rag_toolkit


@pytest.fixture
def rag_paths(monkeypatch, codebase, workspace, tmp_path):
    index_dir = tmp_path / "rag_index"
    monkeypatch.setattr(rag_toolkit, "CODEBASE_PATH", str(codebase))
    monkeypatch.setattr(rag_toolkit, "AGENT_WORKSPACE", str(workspace))
    monkeypatch.setattr(rag_toolkit, "RAG_INDEX_DIR", str(index_dir))
    monkeypatch.setattr(rag_toolkit, "RAG_INDEX_FILE", str(index_dir / "kb_rag_index.json"))
    (workspace / "KB_INDEX.md").write_text("# Knowledge Base Index\n\nTasky is a todo API.\n")


def _embedding_in_subprocess(seed: str) -> str:
    code = "from toolkits.rag_toolkit import _embed_text; print(_embed_text('sqlite database connection')[:32])"
    env = {**os.environ, "PYTHONHASHSEED": seed}
    return subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, env=env, capture_output=True, text=True, check=True
    ).stdout


def test_embedding_is_stable_across_processes():
    # Regression: builtin hash() is salted per process, so an index built in one
    # run did not match query embeddings computed in the next one.
    assert _embedding_in_subprocess("1") == _embedding_in_subprocess("2")


def test_build_and_search_codebase(rag_paths):
    summary = rag_toolkit.build_rag_index_for_kb(include_codebase=True)
    assert "kb" in summary and "code" in summary

    hits = rag_toolkit.semantic_search_documents("database connection sqlite get_db", top_k=3)
    assert "db.py" in hits or "DEPLOYMENT.md" in hits


def test_kb_only_index_excludes_code(rag_paths):
    summary = rag_toolkit.build_rag_index_for_kb(include_codebase=False)
    assert "0 code" in summary
