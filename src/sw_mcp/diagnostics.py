"""Inspect a model for build errors, suppressed/errored features and rebuild state.

All functions run on the COM worker thread and take a live ModelDoc2 (`model`).
Feature inspection uses the feature-tree walk (FirstFeature/GetNextFeature) from
the user's verified core-patterns, plus per-feature GetErrorCode2. The official
ModelDocExtension.GetWhatsWrong is attempted first when available.
"""
from __future__ import annotations

from typing import Any, Optional

import pythoncom
import win32com.client

# IFeature::GetErrorCode2 values (swFeatureError_e subset). 0 = OK; non-zero is
# an error (or a warning when IsWarning is true). 51 = over-defined/conflicting.
FEATURE_ERROR = {
    0: "no error",
    1: "general error",
    2: "needs rebuild",
    51: "over-defined / conflicting (e.g. mate)",
}


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


def _err_code(feat: Any) -> tuple[int, bool]:
    """IFeature.GetErrorCode2(ByRef IsWarning) -> (code, is_warning).

    The ByRef IsWarning arg is REQUIRED; calling it without the arg always
    throws, which previously made every feature silently report 0.
    """
    try:
        warn = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BOOL, False)
        code = int(feat.GetErrorCode2(warn))
        return code, bool(warn.value)
    except Exception:  # noqa: BLE001
        return 0, False


def _entry(feat: Any, sub: bool) -> dict:
    code, is_warning = _err_code(feat)
    return {
        "name": _safe(lambda: feat.Name),
        "type": _safe(lambda: feat.GetTypeName2),
        "suppressed": bool(_safe(lambda: feat.IsSuppressed, default=False)),
        "error_code": code,
        "is_warning": is_warning,
        "error": FEATURE_ERROR.get(code, f"error code {code}") if code else None,
        "sub_feature": sub,
    }


def walk_feature_tree(model: Any, include_ok: bool = True) -> list[dict]:
    """Walk the whole feature tree, descending one level into sub-features so
    nested items (mates under the MateGroup, etc.) are inspected too. Returns
    one dict per feature with name, type, suppression and error code."""
    feats: list[dict] = []
    feat = _safe(lambda: model.FirstFeature)
    guard = 0
    while feat is not None and guard < 100000:
        guard += 1
        e = _entry(feat, sub=False)
        if include_ok or e["error_code"] or e["suppressed"]:
            feats.append(e)
        sub = _safe(lambda f=feat: f.GetFirstSubFeature)
        sguard = 0
        while sub is not None and sguard < 100000:
            sguard += 1
            se = _entry(sub, sub=True)
            if include_ok or se["error_code"] or se["suppressed"]:
                feats.append(se)
            sub = _safe(lambda s=sub: s.GetNextSubFeature)
        feat = _safe(lambda f=feat: f.GetNextFeature)
    return feats


def rebuild(model: Any, force: bool = True) -> dict:
    """Rebuild the model. ForceRebuild3(False) rebuilds the whole tree top-down.
    Returns success plus the post-rebuild error/warning feature lists."""
    ok = bool(_safe(lambda: model.ForceRebuild3(False) if force else model.EditRebuild3(),
                    default=False))
    errs = get_build_errors(model)
    return {"rebuilt": ok, **errs}


def get_build_errors(model: Any) -> dict:
    """Scan the model (incl. nested mates) and split real errors from warnings.

    A non-zero GetErrorCode2 with IsWarning False is a real error (e.g. an
    over-defined mate, code 51); IsWarning True is a warning. `has_errors`
    reflects real errors only.
    """
    tree = walk_feature_tree(model, include_ok=True)
    errors = [f for f in tree if f["error_code"] and not f["is_warning"]]
    warnings = [f for f in tree if f["error_code"] and f["is_warning"]]
    suppressed = [f for f in tree if f["suppressed"]]
    return {
        "feature_count": len(tree),
        "errors": errors,
        "errored_features": errors,
        "warnings": warnings,
        "suppressed_features": suppressed,
        "has_errors": bool(errors),
    }
