import os
from typing import List

from smolagents import tool


def _abs_norm(p: str) -> str:
    return os.path.realpath(os.path.abspath(p))

def _is_within(base: str, target: str) -> bool:
    base_abs = _abs_norm(base)
    tgt_abs = _abs_norm(target)
    return os.path.commonpath([base_abs]) == os.path.commonpath([base_abs, tgt_abs])

def _ensure_parent_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

def create_scoped_filesystem_tools(*, codebase_root: str, workspace_root: str):
    """
    Creates a set of filesystem tools scoped to the given codebase and workspace roots.
    
    Args:
        codebase_root (str): The root directory of the codebase.
        workspace_root (str): The root directory of the workspace
        
    Returns:
        List[Tool]: A list of tool instances.
    
    """
    codebase_root = _abs_norm(codebase_root)
    workspace_root = _abs_norm(workspace_root)

    @tool
    def get_codebase_tree() -> str:
        """
        Returns a tree representation of the codebase.

        Returns:
            str: A string representing the directory tree of the codebase.
        """
        lines = []
        for root, _dirs, files in os.walk(codebase_root):
            rel = os.path.relpath(root, codebase_root)
            indent = "" if rel == "." else "  " * len(rel.split(os.sep))
            lines.append(f"{indent}{'.' if rel == '.' else rel}/")
            for f in files:
                lines.append(f"{indent}  {f}")
        return "\n".join(lines)

    @tool
    def list_codebase_directory(dir_path: str) -> List[str]:
        """
        Lists the contents of a directory within the codebase.
        Args:
            dir_path (str): Relative path to the directory within the codebase.

        Raises:
            ValueError: if path traversal is detected.
            FileNotFoundError: if directory is not found.

        Returns:
            List[str]: A list of filenames and directory names in the specified directory.
        """
        
        target = _abs_norm(os.path.join(codebase_root, dir_path))
        if not _is_within(codebase_root, target):
            raise ValueError("Path traversal detected for codebase read.")
        if not os.path.isdir(target):
            raise FileNotFoundError(f"Directory not found: {dir_path}")
        return sorted(os.listdir(target))

    @tool
    def read_codebase_file(file_path: str) -> str:
        """
        Reads a file within the codebase.
        
        Args:
            file_path (str): Relative path to the file within the codebase.
        Raises:
            ValueError: if path traversal is detected.
            FileNotFoundError: if file is not found.
        Returns:
            str: The contents of the specified file.
        """
        target = _abs_norm(os.path.join(codebase_root, file_path))
        if not _is_within(codebase_root, target):
            raise ValueError("Path traversal detected for codebase read.")
        if not os.path.isfile(target):
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(target, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    @tool
    def write_workspace_file(file_path: str, content: str) -> str:
        """
        Writes a file to the workspace.
        
        Args:
            file_path (str): Relative path to the file within the workspace.
            content (str): The content to write to the file.
            
        Raises:
            ValueError: if path traversal is detected.
            
        Returns:
            str: A message indicating the path of the written file.
        """
        target = _abs_norm(os.path.join(workspace_root, file_path))
        if not _is_within(workspace_root, target):
            raise ValueError("Path traversal detected for workspace write.")
        _ensure_parent_dir(target)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {os.path.relpath(target, workspace_root)}"
    
    @tool
    def grep_codebase(pattern: str, max_results: int = 20) -> str:
        """
        Search for a text pattern in text-like files under the codebase.

        Args:
            pattern (str): Substring or simple regex pattern to search for.
            max_results (int): Max number of matching lines to return.

        Returns:
            str: A human-readable list of matches in the form:
                 path:line_no: line text
        """
        import re

        try:
            regex = re.compile(pattern)
        except re.error:
            # fallback: literal substring search
            regex = None

        # Hangi uzantılarda arayalım?
        allowed_exts = {
            ".py", ".md", ".rst", ".txt",
            ".toml", ".cfg", ".ini",
            ".yml", ".yaml", ".json",
        }

        matches = []
        for root, _dirs, files in os.walk(codebase_root):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in allowed_exts:
                    continue

                fpath = os.path.join(root, fname)
                if not _is_within(codebase_root, fpath):
                    continue

                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for lineno, line in enumerate(f, start=1):
                            text = line.rstrip("\n")
                            ok = False
                            if regex is not None:
                                if regex.search(text):
                                    ok = True
                            else:
                                if pattern in text:
                                    ok = True
                            if ok:
                                rel = os.path.relpath(fpath, codebase_root).replace("\\", "/")
                                matches.append(f"{rel}:{lineno}: {text}")
                                if len(matches) >= max_results:
                                    break
                except Exception:
                    continue
                if len(matches) >= max_results:
                    break
            if len(matches) >= max_results:
                break

        if not matches:
            return f"No matches for pattern {pattern!r}."

        return "Matches:\n" + "\n".join(matches)

    return [get_codebase_tree, list_codebase_directory, read_codebase_file, write_workspace_file, grep_codebase]

