"""Surface modeling + sheet metal generators must build clean (no errors)."""
import pytest

from sw_mcp import executor, feature_tools
from sw_mcp.com_worker import call
from sw_mcp.util import new_work_path


def _run(builder, *args):
    lp = str(new_work_path(".log"))
    code = builder(*args, log_path=lp)
    return call(lambda app: executor.run_inline_and_verify(app, code, log_path=lp))


@pytest.mark.parametrize("builder,args", [
    (feature_tools.build_surface_extrude, (100, 40)),
    (feature_tools.build_surface_planar, (80, 50)),
    (feature_tools.build_surface_revolve, (25, 60)),
    (feature_tools.build_surface_thicken, (100, 40, 3)),
])
def test_surface(builder, args):
    v = _run(builder, *args)
    assert v["ran"] and v["success"], v.get("log")
    assert not v["has_errors"]


@pytest.mark.parametrize("builder,args", [
    (feature_tools.build_sheet_base_flange, (120, 80, 2, 1)),
    (feature_tools.build_sheet_lbracket, (60, 40, 80, 2, 2)),
])
def test_sheet_metal(builder, args):
    v = _run(builder, *args)
    assert v["ran"] and v["success"], v.get("log")
    assert not v["has_errors"]
