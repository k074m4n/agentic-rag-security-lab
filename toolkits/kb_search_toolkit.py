# toolkits/kb_search_toolkit.py
import os
import re
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from smolagents import tool

load_dotenv()

# Files produced by the KB build pipeline (merge_kb_outputs_to_index / build_kb_short_from_index)
KB_FILES = ["KB_INDEX.md", "KB_SHORT.md"]


def _kb_root() -> str:
    # Read at call time so AGENT_WORKSPACE_PATH from .env (or tests) is honoured
    return os.path.abspath(os.getenv("AGENT_WORKSPACE_PATH", "data/agent_workspace"))

def _read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def _tokenize(t: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9_]+", t.lower())

def _score(query: str, text: str) -> float:
    # çok basit BM25-vari: tf * idf taklidi
    q = _tokenize(query)
    if not q:
        return 0.0
    toks = _tokenize(text)
    if not toks:
        return 0.0
    tf = {w: 0 for w in q}
    for w in toks:
        if w in tf:
            tf[w] += 1
    # idf ~ 1 / freq
    score = 0.0
    for w in q:
        score += tf[w] / (1.0 + toks.count(w))
    return score

def _split_by_sections(md: str) -> List[Tuple[str,str]]:
    # ### veya ## başlıklarına göre kaba böl
    parts = re.split(r"(?m)^#{1,6}\s+", md)
    heads = re.findall(r"(?m)^#{1,6}\s+(.+)$", md)
    out=[]
    if not heads:
        return [("Document", md)]
    # parts[0] doküman başındaki giriş olabilir
    if parts[0].strip():
        out.append(("Intro", parts[0]))
    for h, body in zip(heads, parts[1:], strict=False):
        out.append((h.strip(), body))
    return out

@tool
def search_kb(query: str, top_k: int = 5) -> List[Dict]:
    """
    Search the local KB (markdown files) and return the most relevant sections.
    Returns a list of dicts: {file, section, snippet}
    
    Args:
        query (str): The search query.
        top_k (int): The number of top results to return.

    Returns:
        List[Dict]: A list of dictionaries, each containing 'file', 'section', 'score', and 'snippet'.
        The list is sorted by 'score' in descending order.
    
    """
    results=[]
    for fname in KB_FILES:
        fpath = os.path.join(_kb_root(), fname)
        if not os.path.exists(fpath): 
            continue
        md = _read_file(fpath)
        for (section, body) in _split_by_sections(md):
            sc = _score(query, body + " " + section)
            if sc > 0:
                snippet = body.strip()
                # kırp
                snippet = re.sub(r"\s+", " ", snippet)
                if len(snippet) > 700:
                    snippet = snippet[:700] + "..."
                results.append({
                    "file": fname,
                    "section": section,
                    "score": round(sc, 4),
                    "snippet": snippet
                })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]

@tool
def read_kb_file(file_name: str) -> str:
    """
    Read a KB file verbatim (KB_INDEX.md or KB_SHORT.md).
    
    Args:
        file_name (str): The name of the KB file to read.

    Returns:
        str: The contents of the KB file.
    
    """
    if file_name not in KB_FILES:
        raise ValueError(f"Unsupported KB file: {file_name}")
    fpath = os.path.join(_kb_root(), file_name)
    if not os.path.exists(fpath):
        raise FileNotFoundError(f"{file_name} not found in KB root.")
    return _read_file(fpath)
