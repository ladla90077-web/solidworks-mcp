"""Self-improving knowledge base.

Every time a macro fails and the fix is found, a *rule* is recorded here. On the
next failure the server matches the new error against stored rules and returns
the known fix as `suggested_fixes`, so the same problem is never solved twice.

Storage: resources/knowledge/rules.json (the source of truth) and a regenerated
human-readable resources/knowledge/LESSONS.md (the living documentation). Both
grow over time as the auto-fix loop learns.
"""
from __future__ import annotations

import datetime
import json
import re
import threading
from typing import Optional

from .util import RESOURCES_DIR

KNOWLEDGE_DIR = RESOURCES_DIR / "knowledge"
RULES_FILE = KNOWLEDGE_DIR / "rules.json"
LESSONS_FILE = KNOWLEDGE_DIR / "LESSONS.md"

_lock = threading.Lock()


# Rules discovered while building/validating the server - the base knowledge.
_SEED_RULES = [
    {
        "title": "API booleans return +1 in .swb - never use bitwise 'If Not'",
        "applies_to": ["vba", "inline", "selection"],
        "error_signature": "could not select|selectstdplane|if not",
        "symptom": "A selection/boolean helper clearly returns True, yet the "
                   "'If Not x' guard takes the failure branch.",
        "cause": "In an on-the-fly .swb macro, SolidWorks API VARIANT_BOOL "
                 "returns arrive as +1 (not VBA's True == -1). VBA 'Not' is "
                 "bitwise, so 'Not 1' = -2 (truthy) and the guard misfires.",
        "fix": "Test API booleans with 'If x = False Then' (never 'If Not x'). "
               "Object checks ('Is Nothing') are unaffected.",
        "example_bad": "If Not okSel Then ... End If",
        "example_good": "If okSel = False Then ... End If",
    },
    {
        "title": "Create*Rectangle returns a Variant array - do not use Set",
        "applies_to": ["vba", "inline", "sketch"],
        "error_signature": "object required|424|createcenterrectangle|createcornerrectangle",
        "symptom": "Run-time error 424 'Object required' on "
                   "Set seg = swSketchMgr.Create...Rectangle(...).",
        "cause": "CreateCenterRectangle/CreateCornerRectangle return a Variant "
                 "ARRAY of sketch segments, not a single object; Set on a "
                 "non-object raises 424.",
        "fix": "Capture as Variant and check IsArray: "
               "Dim v As Variant: v = swSketchMgr.CreateCenterRectangle(...): "
               "If IsArray(v) = False Then ... . (CreateCircleByRadius returns a "
               "single SketchSegment, so Set is fine there.)",
        "example_bad": "Set swSeg = swSketchMgr.CreateCenterRectangle(0,0,0,a,b,0)",
        "example_good": "Dim v As Variant\nv = swSketchMgr.CreateCenterRectangle(0,0,0,a,b,0)\nIf IsArray(v) = False Then buildFailed = True",
    },
    {
        "title": "MsgBox blocks automation - use the silent log instead",
        "applies_to": ["vba", "inline", "automation"],
        "error_signature": "timed out|modal|msgbox",
        "symptom": "A macro call hangs / times out.",
        "cause": "A modal MsgBox (or SendMsgToUser) blocks RunMacro2 until "
                 "dismissed, deadlocking the COM thread.",
        "fix": "In automated macros replace MsgBox with SWMCP_Log "
               "step/status/message lines; the server reads the log for "
               "per-step status. A dialog watchdog also auto-dismisses strays.",
        "example_bad": 'MsgBox "Base failed", vbCritical',
        "example_good": 'SWMCP_Log "base", "ERROR", "Base extrusion failed"',
    },
    {
        "title": "Never hardcode template paths; abort if none configured",
        "applies_to": ["vba", "document"],
        "error_signature": "no default part template|newdocument returned nothing|could not create",
        "symptom": "NewDocument returns Nothing / part is not created.",
        "cause": "No default template is configured, or a hardcoded template "
                 "path does not exist on this machine.",
        "fix": "Get the template via GetUserPreferenceStringValue("
               "swDefaultTemplatePart=8) and abort cleanly (SWMCP_Log ERROR) "
               "if it is empty.",
        "example_bad": 'Set m = swApp.NewDocument("C:\\templates\\part.prtdot",0,0,0)',
        "example_good": 'tpl = swApp.GetUserPreferenceStringValue(8)\nIf tpl = "" Then SWMCP_Log "init","ERROR","no template": Exit Sub',
    },
    {
        "title": "Select reference planes by tree position, not by name",
        "applies_to": ["vba", "selection", "plane"],
        "error_signature": "select plane|top plane|front plane|right plane|selectbyid2.*plane",
        "symptom": "SelectByID2(\"Top Plane\",\"PLANE\",...) returns False even "
                   "though the name matches on screen.",
        "cause": "Name-based plane selection is unreliable across templates / "
                 "languages.",
        "fix": "Use the SelectStdPlane helper (walks the tree, selects the "
               "Nth RefPlane feature directly): 1=Front, 2=Top, 3=Right.",
        "example_bad": 'swModelExt.SelectByID2 "Top Plane","PLANE",0,0,0,False,0,Nothing,0',
        "example_good": "okSel = SelectStdPlane(2, False, 0)  ' Top",
    },
]


def _today() -> str:
    return datetime.date.today().isoformat()


def _load() -> dict:
    if RULES_FILE.exists():
        try:
            return json.loads(RULES_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    # First run: seed.
    data = {"next_id": 1, "rules": []}
    for r in _SEED_RULES:
        _append(data, r)
    _persist(data)
    return data


def _append(data: dict, rule: dict) -> dict:
    rid = f"r{data['next_id']:04d}"
    data["next_id"] += 1
    full = {
        "id": rid,
        "title": rule["title"],
        "applies_to": rule.get("applies_to", []),
        "error_signature": rule.get("error_signature", ""),
        "symptom": rule.get("symptom", ""),
        "cause": rule.get("cause", ""),
        "fix": rule.get("fix", ""),
        "example_bad": rule.get("example_bad", ""),
        "example_good": rule.get("example_good", ""),
        "created": rule.get("created", _today()),
        "hits": 0,
    }
    data["rules"].append(full)
    return full


def _persist(data: dict) -> None:
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    RULES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _regenerate_lessons(data)


def _regenerate_lessons(data: dict) -> None:
    lines = [
        "# SolidWorks MCP - Learned Lessons",
        "",
        "Auto-generated from `rules.json`. Each rule was recorded the first time "
        "an error was hit and fixed, so the same mistake is avoided next time. "
        "**Do not edit by hand** - use the `learn_rule` tool.",
        "",
        f"_{len(data['rules'])} rules._",
        "",
    ]
    by_tag: dict[str, list[dict]] = {}
    for r in data["rules"]:
        tag = (r["applies_to"] or ["general"])[0]
        by_tag.setdefault(tag, []).append(r)
    for tag in sorted(by_tag):
        lines.append(f"## {tag}")
        lines.append("")
        for r in by_tag[tag]:
            lines.append(f"### {r['id']} - {r['title']}")
            if r["symptom"]:
                lines.append(f"- **Symptom:** {r['symptom']}")
            if r["cause"]:
                lines.append(f"- **Cause:** {r['cause']}")
            if r["fix"]:
                lines.append(f"- **Fix:** {r['fix']}")
            if r["example_good"]:
                lines.append(f"- **Good:** `{r['example_good'].splitlines()[0]}`")
            lines.append(f"- _hits: {r['hits']} · since {r['created']}_")
            lines.append("")
    LESSONS_FILE.write_text("\n".join(lines), encoding="utf-8")


# --- Public API ------------------------------------------------------------
def add_rule(title: str, symptom: str = "", cause: str = "", fix: str = "",
             error_signature: str = "", applies_to: Optional[list] = None,
             example_bad: str = "", example_good: str = "") -> dict:
    """Record a new lesson. If a rule with the same title exists, update it."""
    with _lock:
        data = _load()
        for r in data["rules"]:
            if r["title"].strip().lower() == title.strip().lower():
                r.update({"symptom": symptom or r["symptom"],
                          "cause": cause or r["cause"],
                          "fix": fix or r["fix"],
                          "error_signature": error_signature or r["error_signature"],
                          "applies_to": applies_to or r["applies_to"],
                          "example_bad": example_bad or r["example_bad"],
                          "example_good": example_good or r["example_good"]})
                _persist(data)
                return r
        rule = _append(data, {
            "title": title, "symptom": symptom, "cause": cause, "fix": fix,
            "error_signature": error_signature, "applies_to": applies_to or [],
            "example_bad": example_bad, "example_good": example_good,
        })
        _persist(data)
        return rule


def match(error_text: str, tags: Optional[list] = None) -> list[dict]:
    """Return rules relevant to an error: signature substring/regex hit, or a
    shared tag. Increments hit counters for matched rules."""
    text = (error_text or "").lower()
    tagset = {t.lower() for t in (tags or [])}
    with _lock:
        data = _load()
        hits: list[dict] = []
        for r in data["rules"]:
            sig = r.get("error_signature", "")
            matched = False
            if sig:
                try:
                    if re.search(sig, text, re.IGNORECASE):
                        matched = True
                except re.error:
                    matched = sig.lower() in text
            if not matched and tagset and tagset.intersection(
                    {a.lower() for a in r.get("applies_to", [])}):
                matched = True
            if matched:
                r["hits"] = r.get("hits", 0) + 1
                hits.append({k: r[k] for k in
                             ("id", "title", "cause", "fix", "example_good")})
        if hits:
            _persist(data)
        return hits


def all_rules() -> list[dict]:
    return _load()["rules"]
