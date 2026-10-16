import os
import re
import json
import math
import time
from typing import List, Dict, Any

from dotenv import load_dotenv
from smolagents import tool

from agents.common import rate_limiter

load_dotenv()

# Roots
CODEBASE_PATH = os.getenv("CODEBASE_PATH", "data/sample_codebase")
AGENT_WORKSPACE = os.getenv("AGENT_WORKSPACE_PATH", "data/agent_workspace")
RAG_INDEX_DIR = os.getenv("RAG_INDEX_DIR", "data/rag_index")
RAG_INDEX_FILE = os.path.join(RAG_INDEX_DIR, "kb_rag_index.json")

EMBED_DIM = int(os.getenv("RAG_EMBED_DIM", "256"))
MAX_CHUNK_CHARS = int(os.getenv("RAG_MAX_CHUNK_CHARS", "1200"))

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def _read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def _simple_tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())

def _embed_text(text: str, dim: int = EMBED_DIM) -> List[float]:
    """
    A very simple embedding function that creates a normalized bag-of-words
    vector based on hashed tokens.
    
    Args: 
        text (str): Text to embed.
        dim (int): Dimension of the embedding vector.
    Returns:
        List[float]: Normalized embedding vector of size `dim`.

    """
    vec = [0.0] * dim
    for tok in _simple_tokenize(text):
        idx = hash(tok) % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]

def _split_markdown_into_chunks(text: str) -> List[str]:
    """
    Split markdown text into chunks of up to MAX_CHUNK_CHARS characters,
    trying to split at paragraph boundaries.

    Args:
        text (str): The markdown text to split.
    Returns:
        List[str]: A list of text chunks.

    """
    paragraphs = text.split("\n\n")
    chunks: List[str] = []
    current: List[str] = []

    def flush_current():
        if current:
            chunk = "\n\n".join(current).strip()
            if chunk:
                chunks.append(chunk)

    current_len = 0
    for para in paragraphs:
        para = para.rstrip()
        if not para:
            # Empty paragraph
            if current_len + 2 <= MAX_CHUNK_CHARS:
                current.append("")
                current_len += 2
            else:
                flush_current()
                current = []
                current_len = 0
            continue

        if current_len + len(para) + 2 > MAX_CHUNK_CHARS:
            flush_current()
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para) + 2

    flush_current()
    return chunks

def _collect_kb_documents() -> List[Dict[str, Any]]:
    """
    Collect KB documents from AGENT_WORKSPACE for RAG indexing.

    Returns:
        List[Dict[str, Any]]: A list of document dicts with keys:
            - id: Unique document ID
            - source_file: Source file name
            - kind: 'kb'

    """
    docs: List[Dict[str, Any]] = []
    kb_files = ["KB_INDEX.md"]
    for fname in kb_files:
        fpath = os.path.join(AGENT_WORKSPACE, fname)
        if not os.path.exists(fpath):
            continue
        try:
            text = _read_file(fpath)
        except FileNotFoundError:
            continue
        chunks = _split_markdown_into_chunks(text)
        rel_path = os.path.relpath(fpath, os.getcwd()).replace("\\", "/")
        for idx, chunk in enumerate(chunks):
            docs.append(
                {
                    "id": f"{fname}#chunk-{idx}",
                    "source_file": fname,
                    "kind": "kb",
                    "path": rel_path,
                    "chunk_index": idx,
                    "text": chunk,
                }
            )
    return docs

def _collect_code_documents() -> List[Dict[str, Any]]:
    """
    Collect code documents from CODEBASE_PATH for RAG indexing.

    Returns:
        List[Dict[str, Any]]: A list of document dicts with keys:
            - id: Unique document ID
            - source_file: Source file name
            - kind: 'code'
    """
    docs: List[Dict[str, Any]] = []

    # Basit bir uzantı filtresi – gerekirse genişletebilirsin.
    allowed_exts = {
        ".py",
        ".md",
        ".rst",
        ".txt",
        ".toml",
        ".cfg",
        ".ini",
        ".yml",
        ".yaml",
        ".json",
    }

    for root, _dirs, files in os.walk(CODEBASE_PATH):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in allowed_exts:
                continue

            fpath = os.path.join(root, fname)
            try:
                text = _read_file(fpath)
            except Exception:
                # İkincil önemde: okunamayan / binary dosyaları sessizce atla
                continue

            chunks = _split_markdown_into_chunks(text)
            rel_path = os.path.relpath(fpath, os.getcwd()).replace("\\", "/")
            for idx, chunk in enumerate(chunks):
                docs.append(
                    {
                        "id": f"code:{rel_path}#chunk-{idx}",
                        "source_file": fname,
                        "kind": "code",
                        "path": rel_path,
                        "chunk_index": idx,
                        "text": chunk,
                    }
                )
    return docs


@tool
def build_rag_index_for_kb(include_codebase: bool = True) -> str:
    """
    Build RAG index for the KB (and optionally codebase) and store it under RAG_INDEX_FILE.

    Args:
        include_codebase (bool): If True, include codebase files in the RAG index. Default is True: Allowing Code Files in RAG Indexing.
    Returns:
        str: A message indicating the result. The RAG index is stored as a JSON file:
            {
                "dim": EMBED_DIM,
                "documents": [...],
                "embeddings": [[...], ...]
            }
    """
    _ensure_dir(RAG_INDEX_DIR)

    # 1) KB dokümanlarını topla
    docs = _collect_kb_documents()

    # 2) İstenirse codebase dokümanlarını da ekle
    if include_codebase:
        code_docs = _collect_code_documents()
        docs.extend(code_docs)

    if not docs:
        raise FileNotFoundError(
            f"No documents found for RAG index. "
            f"Checked KB under {AGENT_WORKSPACE} and codebase under {CODEBASE_PATH}."
        )

    embeddings: List[List[float]] = []
    for doc in docs:
        emb = _embed_text(doc["text"])
        embeddings.append(emb)

    index = {
        "dim": EMBED_DIM,
        "documents": docs,
        "embeddings": embeddings,
    }

    with open(RAG_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f)

    # Rate limit to avoid overwhelming any system resources
    rate_limiter.wait()
    time.sleep(0.2)

    kb_count = sum(1 for d in docs if d.get("kind") == "kb")
    code_count = sum(1 for d in docs if d.get("kind") == "code")

    rel_index = os.path.relpath(RAG_INDEX_FILE, os.getcwd()).replace("\\", "/")
    return (
        f"Built RAG index with {len(docs)} chunks "
        f"({kb_count} kb, {code_count} code). Index stored at {rel_index}."
    )

def _load_index() -> Dict[str, Any]:
    if not os.path.exists(RAG_INDEX_FILE):
        raise FileNotFoundError(
            f"RAG index file not found at {RAG_INDEX_FILE}. "
            "Run build_rag_index_for_kb first."
        )
    with open(RAG_INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    # Cosine similarity between two vectors
    return sum(a * b for a, b in zip(vec_a, vec_b))

@tool
def semantic_search_documents(query: str, top_k: int = 5) -> str:
    """
    Perform semantic search over the RAG index and return the top_k most relevant chunks.
    
    Args:
        query (str): The search query.
        top_k (int): The number of top results to return.
    Returns:
        str: A formatted string listing the top_k most relevant chunks with their scores and snippets.

    """
    index = _load_index()
    embeddings: List[List[float]] = index.get("embeddings", [])
    docs: List[Dict[str, Any]] = index.get("documents", [])

    if not embeddings or not docs:
        raise RuntimeError("RAG index is empty or malformed.")

    q_emb = _embed_text(query)

    scored: List[Dict[str, Any]] = []
    for emb, doc in zip(embeddings, docs):
        score = _cosine_similarity(q_emb, emb)
        scored.append({"score": score, "doc": doc})

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[: max(1, min(top_k, len(scored)))]

    lines: List[str] = []
    lines.append("Top RAG matches:")
    for i, item in enumerate(top, start=1):
        doc = item["doc"]
        score = item["score"]
        kind = doc.get("kind", "kb")
        source = doc.get("source_file")
        path = doc.get("path")
        snippet = doc["text"].strip().replace("\n", " ")
        if len(snippet) > 400:
            snippet = snippet[:400] + " ..."
        lines.append(
            f"\n[{i}] score={score:.3f} kind={kind} "
            f"source={source} (chunk #{doc['chunk_index']}, path={path}):\n"
            f"{snippet}\n"
        )

    rate_limiter.wait()
    time.sleep(0.1)

    return "\n".join(lines)

