"""A generated extrude must build clean: ran, no log errors, no feature errors."""
from sw_mcp import executor, feature_tools
from sw_mcp.com_worker import call
from sw_mcp.util import new_work_path


def test_extrusion_builds_clean(sw):
    log_path = str(new_work_path(".log"))
    code = feature_tools.build_extrusion(80, 50, 12, plane=2, log_path=log_path)
    verdict = call(lambda app: executor.run_inline_and_verify(app, code, log_path=log_path))
    assert verdict["ran"] is True
    assert verdict["success"] is True, verdict["log"]
    assert verdict["has_errors"] is False
    assert verdict["feature_count"] >= 18  # default tree + sketch + extrude


def test_cylinder_builds_clean(sw):
    log_path = str(new_work_path(".log"))
    code = feature_tools.build_cylinder(40, 25, plane=2, log_path=log_path)
    verdict = call(lambda app: executor.run_inline_and_verify(app, code, log_path=log_path))
    assert verdict["success"] is True, verdict["log"]
