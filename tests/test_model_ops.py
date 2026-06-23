"""save_model / export must pass a real null IDispatch VARIANT for the SaveAs
ImportExportData arg. Python `None` marshals as VT_EMPTY/VT_NULL and SolidWorks
rejects it with COM "Type mismatch" (0x80020005) — regression guard."""
import pythoncom

from sw_mcp import model_ops
from sw_mcp.com_worker import call
from sw_mcp.util import new_work_path


def test_null_dispatch_is_vt_dispatch_null():
    """The ExportData placeholder must be a VT_DISPATCH null, not None."""
    v = model_ops._null_dispatch()
    assert v.varianttype == pythoncom.VT_DISPATCH
    assert v.value is None


def test_save_as_sldprt(sw):
    """Saving a freshly created part to a .SLDPRT path must succeed (was the
    Type-mismatch failure at the Extension.SaveAs ExportData argument)."""
    out = str(new_work_path(".SLDPRT"))

    def _build_and_save(app):
        model_ops.new_document(app, "part")
        return model_ops.save_model(app, out)

    saved = call(_build_and_save)
    assert saved["ok"] is True, saved
    assert saved["save_errors"] == [], saved
    import os

    assert os.path.exists(out), out
