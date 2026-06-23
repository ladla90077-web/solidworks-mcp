"""Orchestration: run a macro (inline or file), collect the silent log, rebuild,
and scan the resulting model for errors -> one structured verdict.

This is the primitive the Claude-driven auto-fix loop calls each iteration.
All functions run on the COM worker thread (receive the live `app`).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from . import diagnostics, knowledge, macro_runner
from .performance import fast_mode
from .util import new_work_path


def read_log(log_path: Optional[str]) -> list[dict]:
    """Parse the SWMCP_Log file: lines are 'STATUS|step|message'."""
    if not log_path:
        return []
    p = Path(log_path)
    if not p.exists():
        return []
    steps: list[dict] = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            steps.append({"status": parts[0], "step": parts[1], "message": parts[2]})
        elif line.strip():
            steps.append({"status": "INFO", "step": "", "message": line})
    return steps


def _verdict(run: dict, log_steps: list[dict], model: Any,
             tags: Optional[list] = None) -> dict:
    log_errors = [s for s in log_steps if s["status"].upper() == "ERROR"]
    diag = diagnostics.get_build_errors(model) if model is not None else {
        "feature_count": 0, "errors": [], "errored_features": [],
        "suppressed_features": [], "has_errors": False,
    }
    success = run["ran"] and not log_errors and not diag["has_errors"]
    verdict = {
        "success": success,
        "ran": run["ran"],
        "run_error": None if run["ran"] else run.get("run_error"),
        "log": log_steps,
        "log_errors": log_errors,
        **diag,
        "macro_path": run.get("macro_path"),
    }
    if not success:
        # Self-improving: surface any previously-learned fix for this failure.
        error_text = " ".join(
            [run.get("run_error") or ""]
            + [s["message"] for s in log_errors]
            + [str(f.get("error") or f.get("name")) for f in diag["errored_features"]]
        )
        suggestions = knowledge.match(error_text, tags=tags)
        if suggestions:
            verdict["suggested_fixes"] = suggestions
            verdict["hint"] = ("Known fixes matched this error (see "
                               "suggested_fixes). Apply and call run_and_verify "
                               "again. If the real fix differs, call learn_rule.")
        else:
            verdict["hint"] = ("No known rule matched. After you fix this, call "
                               "learn_rule so it is auto-suggested next time.")
    return verdict


def run_inline_and_verify(app: Any, code: str, log_path: Optional[str] = None,
                          proc: str = "main", module: str = "Module1",
                          rebuild: bool = True) -> dict:
    if log_path is None:
        log_path = str(new_work_path(".log"))
    # Start fresh so a stale log can't mask a compile failure.
    lp = Path(log_path)
    if lp.exists():
        lp.unlink()
    with fast_mode(app):
        run = macro_runner.run_inline_vba(app, code, proc=proc, module=module,
                                          keep_file=True)
    log_steps = read_log(log_path)
    model = app.ActiveDoc
    if rebuild and model is not None:
        # Rebuild now, inspect once in _verdict (the old path walked the entire
        # feature tree here and then immediately walked it a second time).
        diagnostics.rebuild(model, force=True, inspect=False)
    verdict = _verdict(run, log_steps, model)
    verdict["log_path"] = log_path
    return verdict


def run_file_and_verify(app: Any, path: str, module: str = "", proc: str = "main",
                        rebuild: bool = True) -> dict:
    with fast_mode(app):
        run = macro_runner.run_macro_file(app, path, module=module, proc=proc)
    model = app.ActiveDoc
    if rebuild and model is not None:
        diagnostics.rebuild(model, force=True, inspect=False)
    return _verdict(run, [], model)
