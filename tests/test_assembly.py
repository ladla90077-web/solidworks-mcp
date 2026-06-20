"""Assembly must build with both components fully mated and NO over-defined
mates, and the verdict must reflect that (regression for the false-positive
and false-negative mate bugs). Screenshot must be a real PNG."""
from sw_mcp import executor, feature_tools, model_ops
from sw_mcp.com_worker import call
from sw_mcp.util import new_work_path


def test_assembly_mates_clean(sw):
    pp = str(new_work_path(".sldprt"))
    ap = str(new_work_path(".sldasm"))
    lp = str(new_work_path(".log"))
    code = feature_tools.build_assembly(pp, ap, 0, lp)
    v = call(lambda app: executor.run_inline_and_verify(app, code, log_path=lp))
    assert v["ran"] is True
    assert v["success"] is True, v["log"]      # no false negative
    assert v["has_errors"] is False            # no over-defined mate slipped through
    mates_ok = [s for s in v["log"] if s["step"] == "mate" and s["status"] == "OK"]
    assert len(mates_ok) == 3, v["log"]


def test_screenshot_is_real_png(sw):
    # Build something first so there is an active document to capture.
    lp = str(new_work_path(".log"))
    code = feature_tools.build_extrusion(60, 40, 12, 2, lp)
    call(lambda app: executor.run_inline_and_verify(app, code, log_path=lp))
    out = str(new_work_path(".png"))
    shot = call(lambda app: model_ops.capture_screenshot(app, path=out))
    assert shot["ok"] is True
    with open(shot["path"], "rb") as f:
        assert f.read(8) == b"\x89PNG\r\n\x1a\n", "expected real PNG bytes"
