"""Bridge to the SOLIDWORKS engineering resources bundled with Cosmon/Nexus.

The complete documentation payload is bundled with this package. The Cosmon
installation remains a fallback/diagnostic source and can be relocated with
``COSMON_RESOURCES_DIR``.
"""
from __future__ import annotations

import os
import re
import copy
from functools import lru_cache
from pathlib import Path

from .util import RESOURCES_DIR

DEFAULT_COSMON_RESOURCES = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Cosmon" / "resources"
BUNDLED_ROOT = RESOURCES_DIR / "cosmon"
TEXT_EXTENSIONS = {".md", ".json", ".txt", ".cs", ".j2", ".rsp", ".xml", ".toml", ".py"}


def cosmon_resources_dir() -> Path:
    return Path(os.environ.get("COSMON_RESOURCES_DIR", DEFAULT_COSMON_RESOURCES)).expanduser()


def external_solidworks_root() -> Path:
    return cosmon_resources_dir() / "extras" / "solidworks"


def _collection_paths(collection: str) -> list[tuple[str, Path]]:
    aliases = {
        "all": "",
        "guides": "documentation_data/programming_guides",
        "quickrefs": "documentation_data/quickrefs",
        "feature_docs": "documentation_data/feature_documentation_db",
        "function_docs": "documentation_data/function_documentation_db",
        "service": "persistent_service",
        "code_execution": "code_execution",
    }
    if collection not in aliases:
        raise ValueError(f"unknown collection '{collection}'; choose from {', '.join(aliases)}")
    relative = aliases[collection]
    roots: list[tuple[str, Path]] = []
    bundled = BUNDLED_ROOT / relative
    external = external_solidworks_root() / relative
    if bundled.exists():
        roots.append(("bundled", bundled))
    if external.exists():
        roots.append(("cosmon-install", external))
    return roots


def _files(collection: str = "all"):
    seen: set[str] = set()
    for source, root in _collection_paths(collection):
        candidates = [root] if root.is_file() else root.rglob("*")
        for path in candidates:
            if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            logical_root = external_solidworks_root() if source == "cosmon-install" else BUNDLED_ROOT
            logical = str(path.relative_to(logical_root)).replace("\\", "/")
            if logical in seen:
                continue
            seen.add(logical)
            yield source, logical, path


def status() -> dict:
    external = external_solidworks_root()
    resources = cosmon_resources_dir()
    collections = {}
    for name in ("guides", "quickrefs", "feature_docs", "function_docs", "service", "code_execution"):
        entries = list(_files(name))
        collections[name] = {"files": len(entries), "bytes": sum(path.stat().st_size for _, _, path in entries)}
    bundled_docs = BUNDLED_ROOT / "documentation_data"
    bundled_doc_files = list(bundled_docs.rglob("*")) if bundled_docs.is_dir() else []
    bundled_doc_files = [path for path in bundled_doc_files if path.is_file()]
    external_docs = external / "documentation_data"
    external_doc_files = list(external_docs.rglob("*")) if external_docs.is_dir() else []
    external_doc_files = [path for path in external_doc_files if path.is_file()]
    bundled_bytes = sum(path.stat().st_size for path in bundled_doc_files)
    external_bytes = sum(path.stat().st_size for path in external_doc_files)
    return {
        "available": external.is_dir() or BUNDLED_ROOT.is_dir(),
        "cosmon_resources_dir": str(resources),
        "external_solidworks_available": external.is_dir(),
        "bundled_portable_resources": BUNDLED_ROOT.is_dir(),
        "bundled_documentation": {
            "files": len(bundled_doc_files),
            "bytes": bundled_bytes,
            "source_files": len(external_doc_files),
            "source_bytes": external_bytes,
            "complete_copy": bool(bundled_doc_files)
            and (not external_doc_files or (len(bundled_doc_files) == len(external_doc_files)
                                             and bundled_bytes == external_bytes)),
        },
        "collections": collections,
    }


def list_resources(collection: str = "all", limit: int = 500) -> dict:
    entries = [
        {"path": logical, "bytes": path.stat().st_size, "source": source}
        for source, logical, path in _files(collection)
    ]
    entries.sort(key=lambda item: item["path"].casefold())
    return {"collection": collection, "count": len(entries), "resources": entries[:max(1, min(limit, 5000))]}


def _excerpt(data: bytes, position: int, width: int = 900) -> str:
    start = max(0, position - width // 3)
    end = min(len(data), start + width)
    text = data[start:end].decode("utf-8", errors="replace")
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=128)
def _search_cached(query: str, collection: str, limit: int, resource_key: str) -> dict:
    """Search every portable guide and large Cosmon SOLIDWORKS JSON database."""
    terms = [term.casefold() for term in re.findall(r"[A-Za-z0-9_.-]+", query) if len(term) > 1]
    if not terms:
        return {"query": query, "collection": collection, "hits": []}
    encoded = [term.encode("utf-8") for term in terms]
    phrase = query.casefold().encode("utf-8")
    hits = []
    for source, logical, path in _files(collection):
        try:
            # The multi-MB function_summaries variants are served by the keyed
            # cosmon_db indexes; byte-scanning them here cost ~124 MB of I/O
            # per uncached query for hits the index finds instantly.
            if path.stat().st_size > 2_000_000:
                continue
            raw = path.read_bytes()
        except OSError:
            continue
        lower = raw.lower()
        positions = [lower.find(term) for term in encoded]
        matched = sum(pos >= 0 for pos in positions)
        if not matched:
            continue
        phrase_pos = lower.find(phrase)
        position = phrase_pos if phrase_pos >= 0 else next(pos for pos in positions if pos >= 0)
        score = matched * 10 + (15 if phrase_pos >= 0 else 0) + (5 if any(t in logical.casefold() for t in terms) else 0)
        hits.append({"path": logical, "source": source, "score": score, "excerpt": _excerpt(raw, position)})
    hits.sort(key=lambda item: (-item["score"], item["path"].casefold()))
    return {"query": query, "collection": collection, "hits": hits[:max(1, min(limit, 50))]}


def search(query: str, collection: str = "all", limit: int = 8) -> dict:
    """Cached full-text search; repeated generation queries return immediately."""
    key = str(cosmon_resources_dir().resolve())
    return copy.deepcopy(_search_cached(query, collection, int(limit), key))


def get_resource(relative_path: str, max_chars: int = 30000) -> dict:
    """Read a resource by the logical path returned from search/list tools."""
    relative = relative_path.replace("\\", "/").lstrip("/")
    if ".." in Path(relative).parts:
        raise ValueError("resource path cannot contain '..'")
    for source, root in (("bundled", BUNDLED_ROOT), ("cosmon-install", external_solidworks_root())):
        candidate = (root / relative).resolve()
        resolved_root = root.resolve()
        if resolved_root not in candidate.parents or not candidate.is_file():
            continue
        text = candidate.read_text(encoding="utf-8", errors="replace")
        cap = max(1000, min(max_chars, 200000))
        return {"path": relative, "source": source, "text": text[:cap], "truncated": len(text) > cap, "total_chars": len(text)}
    raise FileNotFoundError(f"resource '{relative}' not found")
