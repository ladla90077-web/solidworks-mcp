"""Static VBA linter + token-diet layers.

Pitfall/parsing tests are pure and run anywhere. The API-surface tests need
the extracted CHM docs and skip cleanly without them (same convention as
test_local_docs).
"""
import pytest

from sw_mcp import docs_pipeline as dp
from sw_mcp import executor
from sw_mcp import local_docs as ld
from sw_mcp import vba_lint

needs_docs = pytest.mark.skipif(not ld.available(),
                                reason="SolidWorks API CHMs not installed")


# --- Pure: noise stripping & declared names ---------------------------------
def test_strip_noise_blanks_comments_and_strings():
    code = 'x = "MsgBox inside string"  \' MsgBox inside comment'
    stripped = vba_lint._strip_noise(code)
    assert "MsgBox" not in stripped
    assert stripped.count('"') == 2  # literal delimiters survive


def test_declared_names_cover_dims_params_and_set_targets():
    code = (
        "Sub main(swIn As Object)\n"
        "Dim swApp As Object, swModel As Object\n"
        "Const swMyFlag = 1\n"
        "Set swSketchMgr = swModel.SketchManager\n"
        "End Sub\n"
    )
    names = vba_lint._declared_names(code)
    for n in ("main", "swin", "swapp", "swmodel", "swmyflag", "swsketchmgr"):
        assert n in names


# --- Pure: pitfall patterns --------------------------------------------------
def test_pitfalls_flag_the_seeded_failure_modes():
    code = (
        "Sub main()\n"
        "Dim okSel\n"
        "If Not okSel Then okSel = 1\n"
        'MsgBox "done"\n'
        'Set seg = swSketchMgr.CreateCenterRectangle(0, 0, 0, 1, 1, 0)\n'
        'Set m = swApp.NewDocument("C:\\t\\part.prtdot", 0, 0, 0)\n'
        "End Sub\n"
    )
    res = vba_lint.validate(code)
    assert res["ok"] is False
    messages = " ".join(f["message"] for f in res["errors"] + res["warnings"])
    assert "If x = False" in messages          # bitwise If Not
    assert "MsgBox" in messages                # modal dialog deadlock
    assert "Variant ARRAY" in messages         # Set on Create*Rectangle
    assert "template" in messages.lower()      # hardcoded template path
    assert any("Option Explicit" in w["message"] for w in res["warnings"])


def test_pitfalls_allow_safe_constructs():
    code = (
        "Option Explicit\n"
        "Sub main()\n"
        "Dim v As Variant, obj As Object\n"
        "If Not obj Is Nothing Then obj.Quit\n"
        "If Not IsArray(v) Then v = 0\n"
        "End Sub\n"
    )
    res = vba_lint.validate(code)
    assert not [f for f in res["errors"] if f["kind"] == "pitfall"]


# --- API surface (needs extracted CHMs) --------------------------------------
@needs_docs
def test_valid_macro_passes_api_checks():
    code = (
        "Option Explicit\n"
        "Sub main()\n"
        "Dim swApp As Object, swModel As Object, swFeat As Object\n"
        "Dim d As Long\n"
        "d = swDocPART\n"
        "Set swFeat = swModel.FeatureManager.FeatureExtrusion3(True, False, "
        "False, swEndCondBlind, swEndCondBlind, 0.01, 0.01, False, False, "
        "False, False, 0, 0, False, False, False, False, True, True, True, "
        "swStartSketchPlane, 0, False)\n"
        "End Sub\n"
    )
    res = vba_lint.validate(code)
    assert res["docs_available"] is True
    assert res["errors"] == []
    assert res["checked"]["methods"] >= 1
    assert res["checked"]["enum_tokens"] >= 1


@needs_docs
def test_unknown_method_and_enum_are_caught_with_suggestions():
    code = (
        "Option Explicit\n"
        "Sub main()\n"
        "Dim swModel As Object, x As Long\n"
        "swModel.FeatureManager.FeatureExtrusion99 True\n"
        "Call swModel.FeatureManager.FeatureExtruzion3(True)\n"
        "x = swEndCondBlindd\n"
        "End Sub\n"
    )
    res = vba_lint.validate(code)
    kinds = {f["kind"] for f in res["errors"]}
    assert "unknown_method" in kinds
    assert "unknown_enum" in kinds
    method_err = next(f for f in res["errors"] if f["kind"] == "unknown_method")
    assert any("featureextrusion3" in s for s in method_err["suggestions"])


@needs_docs
def test_parenless_statement_call_is_checked():
    code = (
        "Option Explicit\n"
        "Sub main()\n"
        "Dim swModel As Object\n"
        "swModel.FeatureManager.FeatureExtruzion3 True, False\n"
        "swModel.Visible = True\n"          # property set: not a call
        "End Sub\n"
    )
    res = vba_lint.validate(code)
    names = {f.get("name") for f in res["errors"]}
    assert "FeatureExtruzion3" in names
    assert "Visible" not in names


@needs_docs
def test_enum_member_set_and_name_index():
    idx = ld.api_name_index()
    assert "featureextrusion3" in idx["methods"]
    assert "swendconditions_e" in idx["enums"]
    members = ld.enum_member_set()
    assert "swendcondblind" in members


# --- Token diet: docs payload trimming ---------------------------------------
def test_cap_trims_at_line_boundary():
    text = "\n".join(f"line {i}" for i in range(400))
    trimmed, truncated = dp._cap(text, 200)
    assert truncated is True
    assert trimmed.endswith("[...]")
    assert len(trimmed) < 240


def test_compact_method_respects_full_flag():
    out = {"remarks": "x" * 5000, "example": "y" * 5000}
    full = dp._compact_method(dict(out), full=True)
    assert full["remarks"] == out["remarks"]
    compact = dp._compact_method(dict(out), full=False)
    assert compact["truncated"] is True
    assert len(compact["remarks"]) <= dp.REMARKS_CAP + 20


def test_enum_member_table_extracts_compact_lines():
    html = ("<html><body><table>"
            "<tr><td>swEndCondBlind</td><td>0</td><td>Blind</td></tr>"
            "<tr><td>swEndCondThroughAll</td><td>1</td><td>Through all</td></tr>"
            "<tr><td>not_a_member</td><td>9</td></tr>"
            "</table></body></html>")
    table = ld._enum_member_table(html)
    assert "swEndCondBlind = 0 | Blind" in table
    assert "swEndCondThroughAll" in table
    assert "not_a_member" not in table


@needs_docs
def test_local_miss_never_renders_the_web():
    res = dp.lookup_method("FeatureManager", "NoSuchMethodXyz123")
    # A miss resolves instantly to bundled Cosmon references or an explicit
    # not-found hint - the web path (which has no 'source' key) only runs
    # when the caller passes prefer='web'.
    assert res.get("source") in ("bundled-cosmon", "none")


# --- Verdict log trimming -----------------------------------------------------
def _steps(n, status="OK"):
    return [{"status": status, "step": f"s{i}", "message": f"m{i}"}
            for i in range(n)]


def test_trim_log_keeps_tail_and_all_errors():
    steps = _steps(40)
    err = {"status": "ERROR", "step": "boom", "message": "failed"}
    steps.insert(5, err)
    trimmed = executor._trim_log(steps, [err], success=False)
    assert err in trimmed
    assert trimmed[-1] == steps[-1]
    assert len(trimmed) <= executor._LOG_TAIL + 1


def test_trim_log_success_keeps_only_tail():
    steps = _steps(40)
    assert len(executor._trim_log(steps, [], success=True)) == 3
