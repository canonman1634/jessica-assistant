"""
Vector-backed semantic + episodic memory.

Two Chroma collections, persisted per-user under memory/{semantic,episodic}/chroma_db/:
  - semantic: durable facts (people, prefs, mappings) — retrieved top-k by relevance
  - episodic: dated events (tool actions, decisions, session digests) — retrieved top-k,
    optionally filtered by date range

Each entry is also written as a human-readable Markdown card under
memory/{semantic,episodic}/cards/{user}/ so memory stays inspectable outside the vector
index (the index itself is a rebuildable cache, not the source of truth).

Chroma's default embedding function downloads a small local ONNX model (all-MiniLM-L6-v2,
~80MB) on first use and runs fully offline after that — no embeddings API key required.
"""
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import chromadb

from config import JESSICA_USER, TZ

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent / "memory"
_TZ = ZoneInfo(TZ)

_clients: dict[str, chromadb.ClientAPI] = {}


def _client(kind: str) -> chromadb.ClientAPI:
    """kind is 'semantic' or 'episodic'."""
    if kind not in _clients:
        path = _ROOT / kind / "chroma_db" / JESSICA_USER
        path.mkdir(parents=True, exist_ok=True)
        _clients[kind] = chromadb.PersistentClient(path=str(path))
    return _clients[kind]


def _collection(kind: str):
    return _client(kind).get_or_create_collection(f"{kind}_{JESSICA_USER}")


def _cards_dir(kind: str) -> Path:
    d = _ROOT / kind / "cards" / JESSICA_USER
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_card(kind: str, card_id: str, text: str, metadata: dict) -> None:
    frontmatter = "\n".join(f"{k}: {v}" for k, v in metadata.items())
    card = f"---\nid: {card_id}\n{frontmatter}\n---\n{text}\n"
    (_cards_dir(kind) / f"{card_id}.md").write_text(card)


def upsert_semantic(card_id: str, text: str, metadata: dict) -> None:
    """Add or replace a durable fact. metadata should include at least 'type' and 'key'."""
    meta = {**metadata, "updated": datetime.now(_TZ).isoformat()}
    _collection("semantic").upsert(ids=[card_id], documents=[text], metadatas=[meta])
    _write_card("semantic", card_id, text, meta)


def delete_semantic(card_id: str) -> None:
    try:
        _collection("semantic").delete(ids=[card_id])
    except Exception:
        pass
    path = _cards_dir("semantic") / f"{card_id}.md"
    if path.exists():
        path.unlink()


def add_episodic(card_id: str, text: str, metadata: dict) -> None:
    """Append a dated event. metadata should include 'date' (ISO) and 'type'."""
    meta = {**metadata}
    meta.setdefault("date", datetime.now(_TZ).isoformat())
    _collection("episodic").upsert(ids=[card_id], documents=[text], metadatas=[meta])
    _write_card("episodic", card_id, text, meta)


def query_semantic(query: str, k: int = 5) -> list[dict]:
    return _query("semantic", query, k)


def query_episodic(query: str, k: int = 5) -> list[dict]:
    return _query("episodic", query, k)


def _query(kind: str, query: str, k: int) -> list[dict]:
    col = _collection(kind)
    if col.count() == 0:
        return []
    k = min(k, col.count())
    try:
        res = col.query(query_texts=[query], n_results=k)
    except Exception:
        logger.exception("Vector query failed for %s", kind)
        return []
    out = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        out.append({"text": doc, "metadata": meta, "distance": dist})
    return out
