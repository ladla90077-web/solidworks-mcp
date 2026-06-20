"""Shared utilities: unit conversion, paths, SolidWorks error-code tables, log protocol."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

# --- Paths -----------------------------------------------------------------
PKG_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = PKG_DIR / "resources"
VBA_DIR = PKG_DIR / "vba"
CACHE_DIR = RESOURCES_DIR / "cache" / "docs"

# Working area for generated macros, logs, screenshots. Kept out of the repo.
WORK_DIR = Path(tempfile.gettempdir()) / "sw_mcp"
WORK_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# --- Units (the SolidWorks API is meters + radians internally) -------------
def mm(value_mm: float) -> float:
    """Millimetres -> metres (API unit)."""
    return value_mm / 1000.0


def to_mm(value_m: float) -> float:
    """Metres (API unit) -> millimetres."""
    return value_m * 1000.0


# --- swFileSaveError_e (RunMacro2 / SaveAs return codes) -------------------
# Bit-flag style values returned by Extension.SaveAs and related calls.
SAVE_ERROR_CODES = {
    1: "swGenericSaveError",
    2: "swReadOnlySaveError",
    4: "swFileNameEmpty",
    8: "swFileNameContainsAtSign",
    16: "swFileLockError",
    32: "swFileSaveFormatNotAvailable",
    128: "swFileSaveAsBadEAfterRebuild",
    256: "swFileSaveAsInvalidFileExtension",
    1024: "swFileSaveAsNameExceedsMaxPathLength",
    2048: "swFileSaveAsNotSupported",
    8192: "swFileSaveRequiresSavingReferences",
}

# swFeatureError_e / GetErrorCode2 common values (subset; extended at runtime).
FEATURE_ERROR_CODES = {
    0: "swFeatureErrorNone (no error)",
    1: "swFeatureErrorGeneral",
    2: "swSketchErrorGeneral",
    8: "swFeatureErrorRebuild",
}


def decode_save_error(code: int) -> list[str]:
    """Decode a SaveAs/RunMacro bit-flag error code into readable names."""
    if not code:
        return []
    out = [name for bit, name in SAVE_ERROR_CODES.items() if code & bit]
    return out or [f"unknown error code {code}"]


def new_work_path(suffix: str) -> Path:
    """Return a unique path inside the working dir (not created)."""
    import uuid

    return WORK_DIR / f"swmcp_{uuid.uuid4().hex[:8]}{suffix}"
