"""Document & utility operations (open/close/save/new/export, mass properties,
bounding box, screenshot). All run on the COM worker thread (receive `app`)."""
from __future__ import annotations

import os
from typing import Any, Optional

import pythoncom
import win32com.client

from .util import decode_save_error, new_work_path

# swDocumentTypes_e
DOC_PART, DOC_ASM, DOC_DRW = 1, 2, 3
# swUserPreferenceStringValue_e default templates
TPL_PART, TPL_ASM, TPL_DRW = 8, 9, 10
_DOC_BY_EXT = {".sldprt": DOC_PART, ".sldasm": DOC_ASM, ".slddrw": DOC_DRW}
_TPL_FOR = {"part": TPL_PART, "assembly": TPL_ASM, "drawing": TPL_DRW}


def _byref_long(v=0):
    return win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, v)


def new_document(app: Any, doc_type: str = "part") -> dict:
    key = doc_type.lower()
    if key not in _TPL_FOR:
        return {"ok": False, "error": f"unknown doc_type '{doc_type}'"}
    tpl = app.GetUserPreferenceStringValue(_TPL_FOR[key])
    if not tpl:
        return {"ok": False, "error": f"no default {key} template configured in SolidWorks"}
    model = app.NewDocument(tpl, 0, 0, 0)
    return {"ok": model is not None, "doc_type": key,
            "title": _safe(lambda: model.GetTitle) if model else None}


def open_model(app: Any, path: str, config: str = "") -> dict:
    ext = os.path.splitext(path)[1].lower()
    dtype = _DOC_BY_EXT.get(ext, DOC_PART)
    errs, warns = _byref_long(), _byref_long()
    # OpenDoc6(FileName, Type, Options, Configuration, Errors, Warnings)
    model = app.OpenDoc6(path, dtype, 0, config, errs, warns)
    return {
        "ok": model is not None,
        "path": path,
        "errors": int(errs.value or 0),
        "warnings": int(warns.value or 0),
        "title": _safe(lambda: model.GetTitle) if model else None,
    }


def save_model(app: Any, path: Optional[str] = None) -> dict:
    model = app.ActiveDoc
    if model is None:
        return {"ok": False, "error": "no active document"}
    errs, warns = _byref_long(), _byref_long()
    if path:
        ok = bool(model.Extension.SaveAs(path, 0, 1, None, errs, warns))
    else:
        ok = bool(model.Save3(1, errs, warns))
    code = int(errs.value or 0)
    return {"ok": ok, "path": path, "save_errors": decode_save_error(code),
            "warnings": int(warns.value or 0)}


def export_file(app: Any, path: str) -> dict:
    """SolidWorks infers the export format from the extension (.step, .iges,
    .stl, .x_t, .pdf, .png, ...)."""
    model = app.ActiveDoc
    if model is None:
        return {"ok": False, "error": "no active document"}
    errs, warns = _byref_long(), _byref_long()
    ok = bool(model.Extension.SaveAs(path, 0, 0, None, errs, warns))
    code = int(errs.value or 0)
    return {"ok": ok, "path": path if ok else None,
            "save_errors": decode_save_error(code)}


def close_model(app: Any, save: bool = False) -> dict:
    model = app.ActiveDoc
    if model is None:
        return {"ok": True, "note": "no active document"}
    title = _safe(lambda: model.GetTitle)
    if save:
        save_model(app)
    app.CloseDoc(title)
    return {"ok": True, "closed": title}


def get_mass_properties(app: Any) -> dict:
    model = app.ActiveDoc
    if model is None:
        return {"ok": False, "error": "no active document"}
    # IModelDoc2.GetMassProperties is exposed as a no-arg property under dynamic
    # dispatch and returns a 12-element array:
    # [comX, comY, comZ, volume, area, mass, Ixx, Iyy, Izz, Ixy, Iyz, Izx]
    arr = _safe(lambda: list(model.GetMassProperties))
    if not arr or len(arr) < 6:
        return {"ok": False, "error": "mass properties unavailable (empty model?)"}
    vol = arr[3]
    mass = arr[5]
    return {
        "ok": True,
        "mass_kg": mass,
        "volume_m3": vol,
        "surface_area_m2": arr[4],
        "density_kg_m3": (mass / vol) if vol else None,
        "center_of_mass_m": arr[0:3],
        "moments_of_inertia": {"Ixx": arr[6], "Iyy": arr[7], "Izz": arr[8]}
        if len(arr) >= 9 else None,
    }


def get_bounding_box(app: Any) -> dict:
    model = app.ActiveDoc
    if model is None:
        return {"ok": False, "error": "no active document"}
    box = _safe(lambda: list(model.GetPartBox(True)))  # part: 6 values, metres
    if not box or len(box) < 6:
        return {"ok": False, "error": "bounding box unavailable (is this a part?)"}
    return {
        "ok": True,
        "min_m": box[0:3],
        "max_m": box[3:6],
        "size_m": [box[3] - box[0], box[4] - box[1], box[5] - box[2]],
    }


def capture_screenshot(app: Any, path: Optional[str] = None,
                       width: int = 1280, height: int = 960) -> dict:
    model = app.ActiveDoc
    if model is None:
        return {"ok": False, "error": "no active document"}
    model.ViewZoomtofit2()
    # SaveBMP always writes BMP format regardless of extension, so save to a
    # .bmp temp then convert to the requested PNG (real PNG bytes).
    bmp = str(new_work_path(".bmp"))
    ok = bool(model.SaveBMP(bmp, width, height))
    if not ok:
        return {"ok": False, "error": "SaveBMP failed"}
    out = path or bmp[:-4] + ".png"
    try:
        from PIL import Image

        Image.open(bmp).save(out)  # convert BMP -> PNG (out ends in .png)
    except Exception:  # noqa: BLE001
        out = bmp  # Pillow missing: return the raw BMP
    return {"ok": True, "path": out}


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default
