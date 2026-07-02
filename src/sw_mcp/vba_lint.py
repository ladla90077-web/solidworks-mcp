"""Static VBA validation against the real SolidWorks API surface.

Most auto-fix-loop iterations are spent discovering that a generated macro
calls a method that does not exist, misspells an enum member, or trips one of
the known VBA/COM pitfalls. Every one of those failures costs a full COM
round trip (run + ForceRebuild, up to a minute) *plus* a model round trip to
regenerate. This module catches them in milliseconds instead:

  * called method names are checked against the CHM filename key index
    (every documented interface member, ~tens of thousands of names);
  * `sw*` constant tokens are checked against the swconst enum/member set;
  * the seed pitfall rules from `knowledge.py` (bitwise `If Not` on API
    booleans, `Set` on Create*Rectangle, MsgBox deadlocks, hardcoded
    template paths, name-based plane selection) are checked as patterns.

`validate()` never needs SolidWorks running - only the extracted CHM docs.
When those are absent the API checks are skipped and only the pattern checks
run, so the result is always usable.
"""
from __future__ import annotations

import difflib
import re

from . import local_docs

# VBA keywords/builtins that legitimately appear as `x.Name(` or bare calls.
_VBA_BUILTINS = {
    "abs", "array", "asc", "atn", "cbool", "cbyte", "ccur", "cdate", "cdbl",
    "chr", "cint", "clng", "cos", "csng", "cstr", "cvar", "dateadd",
    "datediff", "datepart", "dateserial", "datevalue", "day", "dir", "environ",
    "eof", "err", "exp", "fileattr", "filedatetime", "filelen", "fix",
    "format", "freefile", "getattr", "hex", "hour", "iif", "input", "instr",
    "instrrev", "int", "isarray", "isdate", "isempty", "isnull", "isnumeric",
    "isobject", "join", "lbound", "lcase", "left", "len", "log", "ltrim",
    "mid", "minute", "month", "msgbox", "now", "oct", "print", "raise",
    "replace", "rgb", "right", "rnd", "round", "rtrim", "second", "sgn",
    "sin", "space", "split", "sqr", "str", "strcomp", "string", "tan", "time",
    "timer", "timeserial", "timevalue", "trim", "typename", "ubound", "ucase",
    "val", "vartype", "weekday", "write", "year", "add", "item", "count",
    "remove", "clear", "open", "close", "readline", "writeline",
    # Scripting.FileSystemObject members used by logging helpers.
    "opentextfile", "createtextfile", "fileexists", "folderexists",
    "deletefile", "createobject", "getobject",
}

_METHOD_CALL_RE = re.compile(r"\.\s*([A-Za-z_]\w*)\s*\(")
# VBA also calls methods paren-less in statement position:
#   swModel.FeatureManager.FeatureExtrusion3 True, False, ...
# The last dotted segment is the method; assignments (obj.Prop = x) and
# further member access (obj.A.B) are excluded by the trailing check.
_STMT_CALL_RE = re.compile(
    r"^\s*(?:Call\s+)?[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+", re.IGNORECASE)
_SW_TOKEN_RE = re.compile(r"\bsw[A-Z]\w*\b")
_DECL_RE = re.compile(r"^\s*(?:Public\s+|Private\s+)?(?:Sub|Function)\s+(\w+)",
                      re.IGNORECASE | re.MULTILINE)
# Lines/positions that *declare* identifiers. Anything declared locally must
# never be checked against the API surface - hungarian names like swApp or
# swSketchMgr would otherwise false-positive as unknown enum tokens.
_DIM_LINE_RE = re.compile(
    r"^\s*(?:Dim|Static|Public|Private|Global|Const|ReDim)\b([^\n']*)",
    re.IGNORECASE | re.MULTILINE)
_PARAMS_RE = re.compile(
    r"^\s*(?:Public\s+|Private\s+)?(?:Sub|Function)\s+\w+\s*\(([^)\n]*)\)",
    re.IGNORECASE | re.MULTILINE)
_ASSIGNED_RE = re.compile(r"\b(?:Set|For)\s+([A-Za-z_]\w*)", re.IGNORECASE)
_IDENT_RE = re.compile(r"\b[A-Za-z_]\w*\b")


def _declared_names(code: str) -> set:
    """Every identifier the macro itself declares (procs, Dim/Const lines,
    parameters, Set/For targets), lowercased. Over-inclusive on purpose: an
    extra skipped name just means one fewer check."""
    names = {n.lower() for n in _DECL_RE.findall(code)}
    for chunk in (_DIM_LINE_RE.findall(code) + _PARAMS_RE.findall(code)):
        names.update(t.lower() for t in _IDENT_RE.findall(chunk))
    names.update(n.lower() for n in _ASSIGNED_RE.findall(code))
    return names

# Pattern checks distilled from the seed rules in knowledge.py. Each entry:
# (regex, severity, message, scan_raw). String literals/comments are blanked
# before scanning unless scan_raw (the template-path check must see literals).
_PITFALLS = [
    (re.compile(r"\bIf\s+Not\s+(?!\w+\s+Is\s+Nothing)(?!Is[A-Za-z]+\s*\()\w+",
                re.IGNORECASE),
     "error",
     "Bitwise 'If Not x' misfires on API booleans (VARIANT_BOOL returns +1 in "
     ".swb macros). Test with 'If x = False Then' instead; 'Is Nothing' and "
     "IsArray/IsEmpty checks are fine.", False),
    (re.compile(r"\bSet\s+\w+\s*=\s*\w+(?:\.\w+)*\.Create(?:Center|Corner)Rectangle",
                re.IGNORECASE),
     "error",
     "Create*Rectangle returns a Variant ARRAY, not an object - 'Set' raises "
     "run-time error 424. Capture as 'Dim v As Variant: v = ...' and check "
     "IsArray(v).", False),
    (re.compile(r"\bMsgBox\b", re.IGNORECASE),
     "error",
     "MsgBox blocks RunMacro2 and deadlocks automation. Use the SWMCP_Log "
     "silent-log convention instead.", False),
    (re.compile(r'"[^"\n]*\.(?:prtdot|asmdot|drwdot)"', re.IGNORECASE),
     "warning",
     "Hardcoded template path - it will not exist on other machines. Use "
     "GetUserPreferenceStringValue(swDefaultTemplatePart) and abort cleanly "
     "if empty.", True),
    (re.compile(r'SelectByID2\s*\(?\s*"[^"]*Plane"\s*,\s*"PLANE"', re.IGNORECASE),
     "warning",
     "Name-based plane selection breaks across templates/languages. Select "
     "the Nth RefPlane feature from the tree instead (SelectStdPlane helper: "
     "1=Front, 2=Top, 3=Right).", True),
]


def _line_of(code: str, pos: int) -> int:
    return code.count("\n", 0, pos) + 1


def _strip_noise(code: str) -> str:
    """Blank out comments and string literals (preserving newlines) so name
    extraction never fires on prose."""
    out: list[str] = []
    for line in code.split("\n"):
        chars: list[str] = []
        in_str = False
        i = 0
        while i < len(line):
            c = line[i]
            if in_str:
                if c == '"':
                    in_str = False
                chars.append('"' if c == '"' else " ")
            elif c == '"':
                in_str = True
                chars.append('"')
            elif c == "'":
                break  # rest of the line is a comment
            else:
                chars.append(c)
            i += 1
        out.append("".join(chars))
    return "\n".join(out)


def validate(code: str) -> dict:
    """Statically validate a VBA macro. Returns
    {ok, errors[], warnings[], docs_available, checked:{methods,enum_tokens}}.
    Each finding: {kind, line, name?, message, suggestions?}."""
    errors: list[dict] = []
    warnings: list[dict] = []
    stripped = _strip_noise(code)

    # --- Pitfall patterns (always available) --------------------------------
    for pattern, severity, message, scan_raw in _PITFALLS:
        for m in pattern.finditer(code if scan_raw else stripped):
            finding = {"kind": "pitfall", "line": _line_of(code, m.start()),
                       "message": message}
            (errors if severity == "error" else warnings).append(finding)

    if not re.search(r"^\s*Option\s+Explicit", code, re.IGNORECASE | re.MULTILINE):
        warnings.append({"kind": "pitfall", "line": 1,
                         "message": "Missing 'Option Explicit' - typos in "
                                    "variable names will fail silently."})

    # --- API-surface checks (need the extracted CHM docs) -------------------
    docs_ok = local_docs.available()
    checked_methods = checked_tokens = 0
    if docs_ok:
        index = local_docs.api_name_index()
        methods = index["methods"]
        enums = index["enums"]
        members = local_docs.enum_member_set()
        local_names = _declared_names(code)

        seen: set[tuple[str, int]] = set()

        def _check_method(name: str, line: int) -> None:
            nonlocal checked_methods
            low = name.lower()
            if low in _VBA_BUILTINS or low in local_names or (low, line) in seen:
                return
            seen.add((low, line))
            checked_methods += 1
            if low not in methods:
                close = difflib.get_close_matches(low, methods.keys(), n=3,
                                                  cutoff=0.75)
                errors.append({
                    "kind": "unknown_method", "name": name, "line": line,
                    "message": f"'{name}' is not a documented SolidWorks API "
                               "member.",
                    "suggestions": close,
                })

        for m in _METHOD_CALL_RE.finditer(stripped):
            _check_method(m.group(1), _line_of(code, m.start()))

        for lineno, text in enumerate(stripped.split("\n"), start=1):
            m = _STMT_CALL_RE.match(text)
            if not m:
                continue
            rest = text[m.end():].lstrip()
            if rest[:1] in ("=", ".", "("):  # assignment / access / paren call
                continue
            _check_method(m.group(0).rsplit(".", 1)[1], lineno)

        for m in _SW_TOKEN_RE.finditer(stripped):
            token = m.group(0)
            low = token.lower()
            line = _line_of(code, m.start())
            if low in local_names or (low, line) in seen:
                continue
            seen.add((low, line))
            checked_tokens += 1
            if low not in enums and low not in members:
                close = difflib.get_close_matches(low, members, n=3, cutoff=0.8)
                errors.append({
                    "kind": "unknown_enum", "name": token, "line": line,
                    "message": f"'{token}' is not a documented swconst "
                               "enum/member.",
                    "suggestions": close,
                })

    # --- Deprecation (Cosmon edge database; independent of the CHMs) --------
    try:
        from . import cosmon_db
        if cosmon_db.available():
            flagged: set[str] = set()
            for m in _METHOD_CALL_RE.finditer(stripped):
                name = m.group(1)
                low = name.lower()
                if low in flagged or low in _VBA_BUILTINS:
                    continue
                reps = cosmon_db.deprecation_for(name)
                if reps:
                    flagged.add(low)
                    warnings.append({
                        "kind": "deprecated", "name": name,
                        "line": _line_of(code, m.start()),
                        "message": f"'{name}' is deprecated in the SolidWorks "
                                   f"API; use {' or '.join(reps[:3])} instead.",
                        "suggestions": reps[:3],
                    })
    except Exception:  # noqa: BLE001 - enrichment only, never block
        pass

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "docs_available": docs_ok,
        "checked": {"methods": checked_methods, "enum_tokens": checked_tokens},
    }
