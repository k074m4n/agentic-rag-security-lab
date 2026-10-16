import pytest

from toolkits import kb_search_toolkit


@pytest.fixture
def kb(monkeypatch, workspace):
    monkeypatch.setenv("AGENT_WORKSPACE_PATH", str(workspace))
    (workspace / "KB_INDEX.md").write_text(
        "# Knowledge Base Index\n\n## OVERVIEW.md\nTasky is a todo API.\n\n"
        "## API_REFERENCE.md\nPOST /api/v1/todos requires a bearer token.\n"
    )
    return workspace


def test_search_uses_configured_workspace(kb):
    results = kb_search_toolkit.search_kb("bearer token", top_k=3)
    assert results and results[0]["section"] == "API_REFERENCE.md"


def test_read_kb_file_rejects_unknown_names(kb):
    with pytest.raises(ValueError):
        kb_search_toolkit.read_kb_file("../../.env")


def test_read_kb_file_reads_index(kb):
    assert "Tasky" in kb_search_toolkit.read_kb_file("KB_INDEX.md")
