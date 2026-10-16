import os

import pytest

from toolkits.scoped_filesystem_toolkit import create_scoped_filesystem_tools


@pytest.fixture
def tools(codebase, workspace):
    built = create_scoped_filesystem_tools(codebase_root=str(codebase), workspace_root=str(workspace))
    return {t.name: t for t in built}


def test_exposes_expected_tools(tools):
    assert set(tools) == {
        "get_codebase_tree",
        "list_codebase_directory",
        "read_codebase_file",
        "write_workspace_file",
        "grep_codebase",
    }


def test_reads_file_inside_codebase(tools):
    assert "def validate_title" in tools["read_codebase_file"]("app/utils.py")


@pytest.mark.parametrize("path", ["../outside.txt", "app/../../outside.txt", "/etc/passwd"])
def test_read_rejects_paths_outside_codebase(tools, codebase, path):
    (codebase.parent / "outside.txt").write_text("secret")
    with pytest.raises(ValueError, match="Path traversal"):
        tools["read_codebase_file"](path)


def test_read_rejects_symlink_escape(tools, codebase):
    (codebase.parent / "outside.txt").write_text("secret")
    os.symlink(codebase.parent / "outside.txt", codebase / "link.txt")
    with pytest.raises(ValueError, match="Path traversal"):
        tools["read_codebase_file"]("link.txt")


def test_write_stays_inside_workspace(tools, workspace):
    tools["write_workspace_file"]("notes/a.md", "# hi")
    assert (workspace / "notes" / "a.md").read_text() == "# hi"
    with pytest.raises(ValueError, match="Path traversal"):
        tools["write_workspace_file"]("../escape.md", "x")


def test_grep_finds_symbol(tools):
    out = tools["grep_codebase"]("def get_db")
    assert "app/db.py:" in out


def test_tree_lists_files(tools):
    tree = tools["get_codebase_tree"]()
    assert "routes.py" in tree and "DEPLOYMENT.md" in tree
