"""Keyed in-memory indexes over the bundled Cosmon documentation databases.

The Cosmon payload under resources/cosmon/documentation_data is *structured*:
12k+ API members with curated one-line descriptions and signatures, 961
enriched enums, 496 interface summaries with **accessor chains** (how each
interface is obtained - e.g. IWizardHoleFeatureData2 via
IFeature::GetDefinition), 2.3k deprecated->replacement edges, see-also
networks and feature creation recipes.

Before this module, that knowledge was only reachable through
cosmon_resources.search - a byte-scan over every file including four ~30 MB
function_summaries variants (~124 MB of I/O per uncached query). Here each
database is parsed once, lazily, into plain dicts; every lookup after that is
a hash access. The bulky per-entry `stripped_doc` markdown is dropped at load
so the resident index stays small.
"""
from __future__ import annotations

import json
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .util import RESOURCES_DIR

_FUNC_DB = RESOURCES_DIR / "cosmon" / "documentation_data" / "function_documentation_db"
_FEAT_DB = RESOURCES_DIR / "cosmon" / "documentation_data" / "feature_documentation_db"

_lock = threading.Lock()
_db: Optional[dict] = None


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _members_table(stripped_doc: str) -> Optional[str]:
    """Pull the '# Members' markdown table out of an enriched enum doc."""
    m = re.search(r"#\s*Members\s*\n(.*?)(?:\n#|\Z)", stripped_doc or "", re.S)
    if not m:
        return None
    rows = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("|") and not re.match(r"^\|[-| ]+\|$", line):
            rows.append(line.strip("|").replace("**", "").replace("|", " = ", 1)
                        .replace("|", " | "))
    rows = [r.strip() for r in rows if r.strip() and not r.lower().startswith("member =")]
    return "\n".join(rows) or None


def _build() -> dict:
    members: dict[str, dict] = {}       # "iinterface::member" (lower) -> record
    by_member: dict[str, list[str]] = {}  # member name (lower) -> [ids]
    for entry in _load_json(_FUNC_DB / "function_summaries.json") or []:
        rec = {
            "id": entry.get("id"),
            "interface": entry.get("interface_name"),
            "member": entry.get("member_name"),
            "member_type": entry.get("member_type"),
            "description": entry.get("description"),
            "return_type": entry.get("return_type"),
            "signature": entry.get("csharp_signature"),
        }
        key = (entry.get("id") or "").lower()
        if not key:
            continue
        members[key] = rec
        by_member.setdefault((entry.get("member_name") or "").lower(), []).append(key)

    enums: dict[str, dict] = {}
    for entry in _load_json(_FUNC_DB / "enriched_enum_summaries.json") or []:
        name = (entry.get("id") or "").lower()
        if name:
            enums[name] = {"enum": entry.get("id"),
                           "description": entry.get("description"),
                           "members": _members_table(entry.get("stripped_doc"))}

    interfaces: dict[str, dict] = {}
    for entry in _load_json(_FUNC_DB / "interface_summaries.json") or []:
        name = (entry.get("interface_name") or "").lower()
        if name:
            interfaces[name] = {
                "interface": entry.get("interface_name"),
                "description": entry.get("short_description"),
                "accessors": entry.get("accessors") or [],
            }

    deprecated: dict[str, list[str]] = {}   # full id (lower) -> replacements
    deprecated_names: dict[str, set] = {}   # member name (lower) -> replacements
    for edge in _load_json(_FUNC_DB / "deprecation_edges_cleaned.json") or []:
        old, new = edge.get("deprecated_id"), edge.get("replacement_id")
        if not old or not new:
            continue
        deprecated.setdefault(old.lower(), []).append(new)
        old_name = old.split("::")[-1].lower()
        deprecated_names.setdefault(old_name, set()).add(new.split("::")[-1])

    related: dict[str, list[str]] = {}
    for net in _load_json(_FUNC_DB / "see_also_networks.json") or []:
        ids = net.get("member_function_ids") or []
        for mid in ids:
            related.setdefault(mid.lower(),
                               [i for i in ids if i != mid][:12])

    recipes = []
    for entry in _load_json(_FEAT_DB / "creation_methods.json") or []:
        recipes.append({
            "id": entry.get("id"),
            "identifier": entry.get("identifier"),
            "feature_data_interface": entry.get("feature_data_interface_name"),
            "mode": entry.get("creation_or_modification"),
            "description": (entry.get("description") or "")[:400],
        })

    return {"members": members, "by_member": by_member, "enums": enums,
            "interfaces": interfaces, "deprecated": deprecated,
            "deprecated_names": deprecated_names, "related": related,
            "recipes": recipes}


def _get() -> dict:
    global _db
    if _db is None:
        with _lock:
            if _db is None:
                _db = _build()
    return _db


def available() -> bool:
    return (_FUNC_DB / "function_summaries.json").exists()


# --- Lookups (all O(1) after the lazy one-time load) ------------------------
def member_info(interface: str, member: str) -> Optional[dict]:
    """Compact record for one API member, with deprecation and accessor info."""
    db = _get()
    iface = interface if interface.lower().startswith("i") else f"I{interface}"
    rec = db["members"].get(f"{iface}::{member}".lower())
    if rec is None:
        hits = db["by_member"].get(member.lower()) or []
        if not hits:
            return None
        rec = dict(db["members"][hits[0]])
        if len(hits) > 1:
            rec["also_on"] = sorted({db["members"][h]["interface"] for h in hits})[:10]
    else:
        rec = dict(rec)
    dep = db["deprecated"].get((rec.get("id") or "").lower())
    if dep:
        rec["deprecated"] = True
        rec["replacements"] = sorted(set(dep))
    acc = db["interfaces"].get((rec.get("interface") or "").lower())
    if acc and acc.get("accessors"):
        rec["interface_accessors"] = acc["accessors"][:8]
    rel = db["related"].get((rec.get("id") or "").lower())
    if rel:
        rec["related"] = rel
    return rec


def enum_info(name: str) -> Optional[dict]:
    if not name.endswith("_e"):
        name = f"{name}_e"
    return _get()["enums"].get(name.lower())


def interface_info(name: str) -> Optional[dict]:
    iface = name if name.lower().startswith("i") else f"I{name}"
    info = _get()["interfaces"].get(iface.lower())
    if info is None:
        return None
    out = dict(info)
    prefix = f"{iface}::".lower()
    names = [r["member"] for k, r in _get()["members"].items()
             if k.startswith(prefix)]
    out["member_count"] = len(names)
    out["members"] = sorted(names)[:60]
    return out


def deprecation_for(member_name: str) -> Optional[list]:
    """Replacement member names when `member_name` is deprecated everywhere it
    appears (unambiguous rename like AddComponent4 -> AddComponent5)."""
    reps = _get()["deprecated_names"].get(member_name.lower())
    return sorted(reps) if reps else None


def feature_recipes(query: str = "") -> list[dict]:
    recipes = _get()["recipes"]
    if not query:
        return recipes
    terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2]
    scored = []
    for r in recipes:
        hay = f"{r['identifier']} {r['feature_data_interface']} {r['description']}".lower()
        score = sum(1 for t in terms if t in hay)
        if score:
            scored.append((score, r))
    scored.sort(key=lambda p: -p[0])
    return [r for _, r in scored[:6]]


def search_members(query: str, limit: int = 10) -> list[dict]:
    """Substring-scored search over the 12k member ids + descriptions.
    In-memory and cached - replaces byte-scanning the 30 MB summary files."""
    return [dict(hit) for hit in _search_members_cached(query, int(limit))]


@lru_cache(maxsize=256)
def _search_members_cached(query: str, limit: int) -> tuple:
    db = _get()
    terms = [t for t in re.findall(r"[a-z0-9_]+", query.lower()) if len(t) > 2]
    if not terms:
        return []
    hits = []
    for key, rec in db["members"].items():
        id_score = sum(2 for t in terms if t in key)
        desc_score = sum(1 for t in terms if t in (rec.get("description") or "").lower())
        if id_score + desc_score:
            hits.append((id_score * 2 + desc_score, key, rec))
    hits.sort(key=lambda h: (-h[0], h[1]))
    return tuple({"id": r["id"],
                  "description": (r.get("description") or "")[:160],
                  "signature": r.get("signature")}
                 for _, _, r in hits[:limit])
