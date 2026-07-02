"""Local SolidWorks 2022 API docs - read straight from the installed CHM files.

The web pipeline (docs_pipeline) renders help.solidworks.com with headless
Chromium: every lookup spins up a browser, waits seconds for JS, and returns a
large page blob. That is slow and burns tokens on the auto-fix loop.

The same documentation already ships *on disk* as compiled HTML Help (.chm) at
`C:\\Program Files\\SOLIDWORKS Corp\\SOLIDWORKS\\api`. This module decompiles
those CHMs once with the built-in Windows `hh.exe -decompile`, then serves
lookups from the extracted HTML - offline, in milliseconds, and trimmed to just
the sections that matter (Syntax / Parameters / Return Value / Remarks /
Example).

Key insight: the CHM topic filenames are byte-for-byte the same identifiers the
web pipeline builds its URLs from, e.g.

    SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager~FeatureExtrusion3.html
    SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swEndConditions_e.html

so a method/enum lookup resolves to an exact file with no search at all. A
SQLite FTS5 index (built lazily) backs free-text search and interface-agnostic
fallback.

This is the *first-priority* docs source; docs_pipeline only falls back to the
web when a topic is genuinely absent locally.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from .util import RESOURCES_DIR

# --- Configuration ---------------------------------------------------------
SLDWORKS_NS = "SolidWorks.Interop.sldworks"
SWCONST_NS = "SolidWorks.Interop.swconst"

# Where SolidWorks installs the API CHMs. Overridable for other install paths.
_DEFAULT_API_DIRS = [
    r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\api",
    r"C:\Program Files (x86)\SOLIDWORKS Corp\SOLIDWORKS\api",
]

# The CHMs worth indexing for VBA macro generation. The two big ones
# (sldworksapi = every interface/method, swconst = every enum) cover ~all of
# what the auto-fix loop needs; the prog guide adds task-level how-tos.
_CORE_CHMS = ["sldworksapi.chm", "swconst.chm", "sldworksapiprogguide.chm",
              "swmotionstudyapi.chm", "swdocmgrapi.chm"]

EXTRACT_DIR = RESOURCES_DIR / "cache" / "chm"
KEYS_FILE = EXTRACT_DIR / "keys.json"
INDEX_DB = EXTRACT_DIR / "index.sqlite"
READY_MARKER = EXTRACT_DIR / ".extracted"
MEMBERS_FILE = EXTRACT_DIR / "enum_members.json"

_HH = Path(os.environ.get("WINDIR", r"C:\Windows")) / "hh.exe"

_lock = threading.Lock()
_keys: Optional[dict] = None  # lower filename stem -> relative path under EXTRACT_DIR


# --- Discovery -------------------------------------------------------------
def api_dir() -> Optional[Path]:
    """Resolve the installed SolidWorks API doc folder, or None if absent."""
    env = os.environ.get("SW_API_DOCS_DIR")
    candidates = ([env] if env else []) + _DEFAULT_API_DIRS
    for c in candidates:
        if c and Path(c).is_dir():
            return Path(c)
    return None


def _chm_list() -> list[str]:
    env = os.environ.get("SW_API_DOCS_CHMS")
    if env:
        return [c.strip() for c in env.split(",") if c.strip()]
    return list(_CORE_CHMS)


def available() -> bool:
    """True if we can serve local docs (CHMs found and hh.exe present)."""
    return api_dir() is not None and _HH.exists()


# --- Decompilation ---------------------------------------------------------
def _ps_quote(s: str) -> str:
    """Quote a string as a PowerShell single-quoted literal."""
    return "'" + str(s).replace("'", "''") + "'"


def _hh_decompile(chm: Path, dest: Path, wait_s: int = 120) -> bool:
    """Decompile one CHM into `dest` with the Windows HTML Help compiler.

    `hh.exe -decompile` is doubly finicky:
      1. It only actually runs when launched the way PowerShell's Start-Process
         spawns it - a plain CreateProcess/subprocess (any creationflags) and
         even ShellExecuteEx return success but write nothing.
      2. It mis-parses a destination path containing spaces, even quoted.
    So we bridge through `Start-Process ... -Wait` (fixes #1) into the 8.3 short
    path of the destination (fixes #2).
    """
    dest.mkdir(parents=True, exist_ok=True)
    short_dest = str(dest)
    try:
        import win32api
        short_dest = win32api.GetShortPathName(str(dest))
    except Exception:  # noqa: BLE001 - fall back to the raw path
        pass
    ps = (f"Start-Process -FilePath {_ps_quote(_HH)} -ArgumentList "
          f"'-decompile',{_ps_quote(short_dest)},{_ps_quote(chm)} -Wait")
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            timeout=wait_s, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        pass
    # Be robust if Start-Process returns before the last files are flushed.
    deadline = time.time() + 10
    last = -1
    while time.time() < deadline:
        n = sum(1 for _ in dest.glob("*.htm*"))
        if n and n == last:
            break
        last = n
        time.sleep(0.5)
    return any(dest.glob("*.htm*"))


# --- Extraction + key index ------------------------------------------------
def ensure_extracted(force: bool = False) -> dict:
    """Decompile the core CHMs (once) and build the filename key index.

    Cheap on repeat calls: returns immediately once the ready marker exists.
    The full-text index is built lazily on first search, not here.
    """
    global _keys
    with _lock:
        if not force and READY_MARKER.exists() and KEYS_FILE.exists():
            if _keys is None:
                _keys = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
            return {"ready": True, "topics": len(_keys), "cached": True}

        src = api_dir()
        if src is None or not _HH.exists():
            return {"ready": False,
                    "error": "SolidWorks API CHMs or hh.exe not found",
                    "api_dir": str(src) if src else None}

        EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
        extracted: list[str] = []
        for name in _chm_list():
            chm = src / name
            if not chm.exists():
                continue
            dest = EXTRACT_DIR / chm.stem
            if force or not any(dest.glob("*.htm*")):
                if _hh_decompile(chm, dest):
                    extracted.append(name)
            else:
                extracted.append(name)

        keys = _build_keys()
        _keys = keys
        KEYS_FILE.write_text(json.dumps(keys), encoding="utf-8")
        # New extraction invalidates any stale full-text index.
        if force and INDEX_DB.exists():
            try:
                INDEX_DB.unlink()
            except OSError:
                pass
        READY_MARKER.write_text(str(int(time.time())), encoding="utf-8")
        return {"ready": True, "topics": len(keys), "extracted": extracted,
                "cached": False}


def _build_keys() -> dict:
    """Map every extracted topic's lowercased filename stem to its rel path.

    Filenames-only (no parsing) so this stays fast over ~17k topics.
    """
    keys: dict[str, str] = {}
    for f in EXTRACT_DIR.rglob("*.htm*"):
        keys[f.stem.lower()] = str(f.relative_to(EXTRACT_DIR))
    return keys


def _load_keys() -> dict:
    global _keys
    if _keys is None:
        ensure_extracted()
    return _keys or {}


def _resolve(stem: str) -> Optional[Path]:
    rel = _load_keys().get(stem.lower())
    return EXTRACT_DIR / rel if rel else None


# --- Topic parsing ---------------------------------------------------------
def _clean(text: str) -> str:
    text = text.replace("\xa0", " ").replace("﻿", "")  # nbsp + BOM
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def _best_syntax(sections: dict) -> Optional[str]:
    """Pick the most useful call signature.

    The interface topic's VBA syntax block is often just a cross-reference
    ("See FeatureManager::FeatureExtrusion3"); in that case the .NET "Visual
    Basic (Declaration)" block carries the real, fully-typed signature - which
    is what the model needs to call the method correctly.
    """
    vba = (sections.get("syntax") or "").strip()
    net = (sections.get("syntax_net") or "").strip()
    if vba and not re.match(r"^See\s+[\w.]+::", vba):
        return vba
    return net or vba or None


# CHM topics split content under these headings. The VBA syntax block is the
# one we want for macro generation; the others mirror the web layout.
_HEADER_MAP = [
    ("Visual Basic for Applications (VBA) Syntax", "syntax"),
    ("VBA Syntax", "syntax"),
    ("VB.NET Syntax", "syntax_net"),
    (".NET Syntax", "syntax_net"),
    ("Syntax", "syntax"),
    ("Parameters", "parameters"),
    ("Return Value", "return_value"),
    ("Remarks", "remarks"),
    ("Example", "example"),
    ("See Also", "see_also"),
    ("Availability", "availability"),
]


def _parse_topic(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = _clean(soup.title.get_text()) if soup.title else None
    full = _clean(soup.get_text("\n"))

    # Build an alternation of every known heading, longest first so
    # "...(VBA) Syntax" wins over bare "Syntax".
    headers = sorted({h for h, _ in _HEADER_MAP}, key=len, reverse=True)
    pattern = re.compile(
        r"^\s*(" + "|".join(re.escape(h) for h in headers) + r")\s*$",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(full))
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        label = m.group(1)
        key = next((k for h, k in _HEADER_MAP if h == label), None)
        if not key:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full)
        body = _clean(full[start:end])
        # Keep the first occurrence (web pages repeat headings in nav/footers).
        sections.setdefault(key, body)
    return {"title": title, "sections": sections, "text": full}


# --- Public lookups (shape matches docs_pipeline) --------------------------
def local_method(interface: str, method: str) -> Optional[dict]:
    """Resolve a method topic from the local CHMs, or None if not present.

    Tries the exact `<iface>~<method>` file first; if that interface doesn't
    carry the method, falls back to any interface that does and reports them.
    """
    if not available():
        return None
    iface = interface if interface.startswith("I") else f"I{interface}"
    stem = f"{SLDWORKS_NS}~{SLDWORKS_NS}.{iface}~{method}"
    path = _resolve(stem)

    alternatives: list[str] = []
    if path is None:
        # Interface-agnostic fallback: find any interface exposing this method.
        suffix = f"~{method}.html".lower()
        hits = [v for k, v in _load_keys().items() if (k + ".html").endswith(suffix)]
        if not hits:
            return None
        path = EXTRACT_DIR / hits[0]
        alternatives = [Path(h).stem for h in hits]

    parsed = _parse_topic(path.read_text(encoding="utf-8", errors="replace"))
    s = parsed["sections"]
    out = {
        "interface": interface,
        "method": method,
        "url": path.as_uri(),
        "local_path": str(path),
        "title": parsed.get("title"),
        "syntax": _best_syntax(s),
        "parameters": s.get("parameters"),
        "return_value": s.get("return_value"),
        "remarks": s.get("remarks"),
        "example": s.get("example"),
        "source": "local-chm",
        "cached": True,
        "unrendered": False,
    }
    if alternatives:
        out["note"] = (f"'{iface}' has no {method}; resolved from another "
                       f"interface. Interfaces with this method: "
                       + ", ".join(sorted(set(alternatives))[:12]))
    return out


def _enum_member_table(html: str) -> Optional[str]:
    """Extract the enum's member table as compact 'name = value | note' lines.

    Enum topics list members in an HTML table; the raw page text repeats them
    inside a wall of navigation/remarks prose. The table alone is what a
    macro generator needs, at a fraction of the tokens.
    """
    soup = BeautifulSoup(html, "html.parser")
    lines: list[str] = []
    for row in soup.find_all("tr"):
        cells = [_clean(c.get_text(" ")) for c in row.find_all(["td", "th"])]
        if not cells or not re.match(r"^sw\w+$", cells[0]):
            continue
        rest = " | ".join(c for c in cells[1:] if c)[:120]
        lines.append(f"{cells[0]}" + (f" = {rest}" if rest else ""))
    return "\n".join(lines) if lines else None


def local_enum(enum_name: str) -> Optional[dict]:
    """Resolve an enum topic (and its members) from the local CHMs."""
    if not available():
        return None
    name = enum_name if enum_name.endswith("_e") else f"{enum_name}_e"
    stem = f"{SWCONST_NS}~{SWCONST_NS}.{name}"
    path = _resolve(stem)
    if path is None:
        return None
    html = path.read_text(encoding="utf-8", errors="replace")
    members = _enum_member_table(html)
    if members is None:
        parsed = _parse_topic(html)
        members = parsed["sections"].get("remarks") or parsed.get("text")
        title = parsed.get("title")
    else:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        title = _clean(m.group(1)) if m else name
    return {
        "enum": name,
        "url": path.as_uri(),
        "local_path": str(path),
        "title": title,
        "members": members,
        "source": "local-chm",
        "cached": True,
        "unrendered": False,
    }


def get_topic(stem_or_path: str) -> Optional[dict]:
    """Read+parse a topic by its filename stem (escape hatch for `docs_get`)."""
    if not available():
        return None
    p = Path(stem_or_path)
    path = p if p.is_absolute() and p.exists() else _resolve(p.stem)
    if path is None or not path.exists():
        return None
    parsed = _parse_topic(path.read_text(encoding="utf-8", errors="replace"))
    return {"url": path.as_uri(), "local_path": str(path),
            "title": parsed.get("title"), "sections": parsed["sections"],
            "text": parsed["text"], "source": "local-chm", "cached": True}


# --- API-surface name indexes (for the static VBA linter) ------------------
# Built from the filename key index alone (no HTML parsing), so they are
# millisecond-cheap after the one-time CHM extraction.
_api_names: Optional[dict] = None  # {"methods": {lower: [Iface,...]}, "enums": {lower: Name}}
_member_set: Optional[set] = None  # lowercased swconst member/type tokens


def api_name_index() -> dict:
    """Map every documented member name to the interfaces exposing it, plus
    every swconst enum type name. Derived purely from topic filenames."""
    global _api_names
    if _api_names is not None:
        return _api_names
    methods: dict[str, list[str]] = {}
    enums: dict[str, str] = {}
    sld_ns = SLDWORKS_NS.lower() + "."
    const_ns = SWCONST_NS.lower() + "."
    for stem in _load_keys():
        parts = stem.split("~")
        if len(parts) == 3 and parts[1].startswith(sld_ns):
            iface = parts[1][len(sld_ns):]
            methods.setdefault(parts[2], []).append(iface)
        elif len(parts) == 2 and parts[1].startswith(const_ns):
            name = parts[1][len(const_ns):]
            if name.endswith("_e"):
                enums[name] = name
    _api_names = {"methods": methods, "enums": enums}
    return _api_names


def enum_member_set() -> set:
    """Set of every lowercased `sw*` token appearing in the swconst topics -
    i.e. every enum member and type name. Built once (a few seconds over the
    extracted pages), then persisted next to the FTS index."""
    global _member_set
    if _member_set is not None:
        return _member_set
    with _lock:
        if _member_set is not None:
            return _member_set
        if MEMBERS_FILE.exists():
            try:
                data = json.loads(MEMBERS_FILE.read_text(encoding="utf-8"))
                _member_set = set(data.get("members", []))
                return _member_set
            except (json.JSONDecodeError, OSError):
                pass
        token_re = re.compile(r"\bsw[A-Z]\w*\b")
        members: set[str] = set()
        const_prefix = f"{SWCONST_NS}~".lower()
        for stem, rel in _load_keys().items():
            if not stem.startswith(const_prefix):
                continue
            try:
                html = (EXTRACT_DIR / rel).read_text(encoding="utf-8",
                                                     errors="replace")
            except OSError:
                continue
            members.update(t.lower() for t in token_re.findall(html))
        _member_set = members
        try:
            MEMBERS_FILE.write_text(
                json.dumps({"members": sorted(members),
                            "built": int(time.time())}),
                encoding="utf-8")
        except OSError:
            pass
        return _member_set


# --- Full-text search (lazy FTS5 index) ------------------------------------
def _build_fts() -> None:
    """Parse every extracted topic into a SQLite FTS5 index (one-time)."""
    keys = _load_keys()
    # Regex tag-strip (not BeautifulSoup) - ~10x faster over ~18k files, which
    # keeps the one-time index build to seconds rather than minutes.
    title_re = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
    strip_re = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.I | re.S)
    tag_re = re.compile(r"<[^>]+>")
    ws_re = re.compile(r"\s+")

    con = sqlite3.connect(INDEX_DB)
    try:
        con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS topics "
                    "USING fts5(stem UNINDEXED, path UNINDEXED, title, body)")
        con.execute("DELETE FROM topics")
        rows = []
        for stem, rel in keys.items():
            f = EXTRACT_DIR / rel
            try:
                html = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            tm = title_re.search(html)
            title = ws_re.sub(" ", tm.group(1)).strip() if tm else stem
            text = tag_re.sub(" ", strip_re.sub(" ", html))
            body = ws_re.sub(" ", text.replace("&nbsp;", " "))[:8000]
            rows.append((stem, rel, title, body))
            if len(rows) >= 1000:
                con.executemany("INSERT INTO topics VALUES (?,?,?,?)", rows)
                rows = []
        if rows:
            con.executemany("INSERT INTO topics VALUES (?,?,?,?)", rows)
        con.commit()
    finally:
        con.close()


def _fts_ready() -> bool:
    if not INDEX_DB.exists():
        return False
    try:
        con = sqlite3.connect(INDEX_DB)
        n = con.execute("SELECT count(*) FROM topics").fetchone()[0]
        con.close()
        return n > 0
    except sqlite3.Error:
        return False


def search(query: str, limit: int = 8) -> dict:
    """Full-text search across the local docs. Builds the index on first use.

    Returns lightweight hits (stem, title, snippet) so the model can pick the
    right method/enum without rendering anything or guessing in a fix loop.
    """
    if not available():
        return {"available": False, "hits": []}
    ensure_extracted()
    with _lock:
        if not _fts_ready():
            _build_fts()
    # Sanitize into a safe FTS MATCH expression (token prefix search).
    terms = re.findall(r"[A-Za-z0-9_]+", query)
    if not terms:
        return {"available": True, "hits": [], "query": query}
    match = " ".join(f'"{t}"*' for t in terms)
    con = sqlite3.connect(INDEX_DB)
    try:
        try:
            cur = con.execute(
                "SELECT stem, title, snippet(topics, 3, '[', ']', ' … ', 12) "
                "FROM topics WHERE topics MATCH ? ORDER BY rank LIMIT ?",
                (match, limit))
            rows = cur.fetchall()
        except sqlite3.Error:
            rows = []
    finally:
        con.close()
    return {"available": True, "query": query,
            "hits": [{"stem": s, "title": t, "snippet": sn} for s, t, sn in rows]}
