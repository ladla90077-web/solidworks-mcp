"""SolidWorks 2022 API documentation pipeline.

help.solidworks.com/2022 is JavaScript-rendered: a plain HTTP GET returns a
"Loading..." shell. We render the page with headless Chromium (Playwright),
then scrape the Syntax / Parameters / Remarks / Example sections with
BeautifulSoup. Results are cached to disk so repeat lookups are instant and
work offline after the first fetch.

This feeds verified API signatures straight into the auto-fix loop, replacing
the manual "Claude in Chrome" step the solidworks-vba skill describes.

The web render is now the *fallback*, not the default: lookups first try the
installed CHM docs via `local_docs` (offline, instant, token-trimmed) and only
hit Chromium when a topic is genuinely absent locally. Pass prefer="web" to
force a fresh online render.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Optional

from bs4 import BeautifulSoup

from .util import CACHE_DIR

BASE = "https://help.solidworks.com/2022/english/api"
SLDWORKS_NS = "SolidWorks.Interop.sldworks"
SWCONST_NS = "SolidWorks.Interop.swconst"

_SECTION_HEADERS = ["Syntax", "Parameters", "Return Value", "Remarks",
                    "Example", "See Also", "Accessors"]

# Token diet: remarks/example sections in the help topics routinely run to
# thousands of tokens, and in an agent loop every past tool result is re-read
# on every subsequent model call. Compact results are the default; callers
# pass full=True for the rare topic where the prose matters.
REMARKS_CAP = 1200
EXAMPLE_CAP = 1500


def _cap(text, cap: int):
    """Trim `text` to ~cap chars at a line boundary. Returns (text, truncated)."""
    if not text or len(text) <= cap:
        return text, False
    cut = text.rfind("\n", 0, cap)
    if cut < cap // 2:
        cut = cap
    return text[:cut].rstrip() + " [...]", True


def _compact_method(out: dict, full: bool) -> dict:
    if full:
        return out
    any_trimmed = False
    for field, cap in (("remarks", REMARKS_CAP), ("example", EXAMPLE_CAP)):
        trimmed, truncated = _cap(out.get(field), cap)
        out[field] = trimmed
        any_trimmed = any_trimmed or truncated
    if any_trimmed:
        out["truncated"] = True
        out["note_truncated"] = ("Long sections trimmed to save tokens; pass "
                                 "full=True for the complete text.")
    return out


# --- URL builders ----------------------------------------------------------
def method_url(interface: str, method: str) -> str:
    iface = interface if interface.startswith("I") else f"I{interface}"
    return (f"{BASE}/sldworksapi/{SLDWORKS_NS}~{SLDWORKS_NS}."
            f"{iface}~{method}.html")


def enum_url(enum_name: str) -> str:
    if not enum_name.endswith("_e"):
        enum_name = f"{enum_name}_e"
    return f"{BASE}/swconst/{SWCONST_NS}~{SWCONST_NS}.{enum_name}.html"


def search_url(query: str) -> str:
    # The API help list / search index page (JS-rendered).
    return f"{BASE}/help_list.htm?id=2&search={query}"


# --- Caching ---------------------------------------------------------------
def _cache_path(url: str):
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"{h}.json"


def _cache_get(url: str) -> Optional[dict]:
    p = _cache_path(url)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _cache_put(url: str, data: dict) -> None:
    try:
        _cache_path(url).write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


# --- Rendering -------------------------------------------------------------
def render_html(url: str, timeout_ms: int = 45000, settle_ms: int = 4000) -> str:
    """Render `url` with headless Chromium and return the final HTML.

    The help site holds network connections open, so 'networkidle' never
    fires; we wait for DOM content then give JS a fixed beat to populate the
    content host. The real documentation usually renders inside an iframe, so
    we return the largest frame's HTML.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(settle_ms)
            html = page.content()
            for frame in page.frames:
                try:
                    fhtml = frame.content()
                    if len(fhtml) > len(html):
                        html = fhtml
                except Exception:  # noqa: BLE001
                    pass
            return html
        finally:
            browser.close()


# --- Scraping --------------------------------------------------------------
def _clean(text: str) -> str:
    text = text.replace("\xa0", " ")  # non-breaking spaces from the help pages
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def _scrape_sections(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = _clean(soup.title.get_text()) if soup.title else None
    full = _clean(soup.get_text("\n"))

    # Split the flat text by known section headers (the rendered help pages use
    # these as headings). Best-effort; raw text is always returned as fallback.
    sections: dict[str, str] = {}
    pattern = re.compile(
        r"^\s*(" + "|".join(re.escape(h) for h in _SECTION_HEADERS) + r")\s*$",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(full))
    for i, m in enumerate(matches):
        name = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full)
        sections[name.lower().replace(" ", "_")] = _clean(full[start:end])

    return {"title": title, "sections": sections, "text": full}


def _looks_unrendered(text: str) -> bool:
    snippet = (text or "")[:400].lower()
    return ("loading" in snippet and len(text) < 600) or len(text) < 80


# --- Public lookups --------------------------------------------------------
def fetch(url: str, refresh: bool = False) -> dict:
    if not refresh:
        cached = _cache_get(url)
        if cached:
            cached["cached"] = True
            return cached
    html = render_html(url)
    data = _scrape_sections(html)
    data["url"] = url
    data["unrendered"] = _looks_unrendered(data.get("text", ""))
    data["cached"] = False
    if not data["unrendered"]:
        _cache_put(url, data)
    return data


def _cosmon_enrich(out: dict, interface: str, method: str) -> dict:
    """Bolt the curated Cosmon knowledge onto a lookup result: one-line
    description, deprecation warning + replacement, and the accessor chain
    showing how the owning interface is obtained. A few hundred bytes that
    encode exactly the linkage knowledge macro generation needs."""
    try:
        from . import cosmon_db
        info = cosmon_db.member_info(interface, method)
    except Exception:  # noqa: BLE001
        info = None
    if not info:
        return out
    if info.get("description") and not out.get("description"):
        out["description"] = info["description"]
    if info.get("deprecated"):
        out["deprecated"] = True
        out["replacements"] = info.get("replacements")
    if info.get("interface_accessors"):
        out["interface_accessors"] = info["interface_accessors"]
    return out


def lookup_method(interface: str, method: str, refresh: bool = False,
                  prefer: str = "local", full: bool = False) -> dict:
    if prefer != "web" and not refresh:
        try:
            from . import local_docs
            loc = local_docs.local_method(interface, method)
            if loc and loc.get("syntax"):
                return _cosmon_enrich(_compact_method(loc, full),
                                      interface, method)
        except Exception:  # noqa: BLE001 - never let local issues block lookup
            pass
        try:
            from . import cosmon_db
            info = cosmon_db.member_info(interface, method)
        except Exception:  # noqa: BLE001
            info = None
        if info:
            info.update({"source": "bundled-cosmon-db", "cached": True,
                         "unrendered": False,
                         "note": ("Local CHM topic was unavailable; this is "
                                  "the curated Cosmon record (C# signature - "
                                  "adapt to VBA).")})
            return info
        # Fast, explicit miss. The old behaviour silently launched a headless
        # Chromium render (up to ~50s) in the middle of the fix loop.
        return {
            "interface": interface, "method": method, "found": False,
            "source": "none",
            "hint": ("No local topic for this interface/method. Check the "
                     "spelling with docs_search, or pass prefer='web' to "
                     "render help.solidworks.com (slow, ~10-50s)."),
        }
    url = method_url(interface, method)
    data = fetch(url, refresh=refresh)
    s = data.get("sections", {})
    return _compact_method({
        "interface": interface,
        "method": method,
        "url": url,
        "title": data.get("title"),
        "syntax": s.get("syntax"),
        "parameters": s.get("parameters"),
        "return_value": s.get("return_value"),
        "remarks": s.get("remarks"),
        "example": s.get("example"),
        "cached": data.get("cached"),
        "unrendered": data.get("unrendered"),
    }, full)


def lookup_enum(enum_name: str, refresh: bool = False,
                prefer: str = "local") -> dict:
    if prefer != "web" and not refresh:
        try:
            from . import local_docs
            loc = local_docs.local_enum(enum_name)
            if loc and loc.get("members"):
                return loc
        except Exception:  # noqa: BLE001
            pass
        try:
            from . import cosmon_db
            info = cosmon_db.enum_info(enum_name)
        except Exception:  # noqa: BLE001
            info = None
        if info and info.get("members"):
            return {**info, "source": "bundled-cosmon-db", "cached": True,
                    "unrendered": False}
        return {
            "enum": enum_name, "found": False, "source": "none",
            "hint": ("No local topic for this enum. Check the name with "
                     "docs_search, or pass prefer='web' to render "
                     "help.solidworks.com (slow, ~10-50s)."),
        }
    url = enum_url(enum_name)
    data = fetch(url, refresh=refresh)
    return {
        "enum": enum_name,
        "url": url,
        "title": data.get("title"),
        "members": data.get("sections", {}).get("members")
        or data.get("text"),
        "cached": data.get("cached"),
        "unrendered": data.get("unrendered"),
    }


def get_page(url: str, refresh: bool = False) -> dict:
    return fetch(url, refresh=refresh)
