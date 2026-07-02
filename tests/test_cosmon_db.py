"""Keyed Cosmon documentation indexes (bundled JSON databases, no SolidWorks
or CHM requirement)."""
import pytest

from sw_mcp import cosmon_db, vba_lint

needs_db = pytest.mark.skipif(not cosmon_db.available(),
                              reason="bundled Cosmon databases missing")


@needs_db
def test_member_info_resolves_exact_and_by_name():
    rec = cosmon_db.member_info("FeatureManager", "FeatureExtrusion3")
    assert rec and rec["interface"] == "IFeatureManager"
    assert rec["description"]
    assert rec["signature"]
    # Name-only resolution reports the owning interface(s).
    rec2 = cosmon_db.member_info("", "FeatureExtrusion3")
    assert rec2 and rec2["member"] == "FeatureExtrusion3"


@needs_db
def test_interface_info_exposes_accessor_chain():
    info = cosmon_db.interface_info("WizardHoleFeatureData2")
    assert info is not None
    assert any("GetDefinition" in a for a in info["accessors"])
    assert info["member_count"] > 0


@needs_db
def test_deprecated_member_gets_replacement():
    reps = cosmon_db.deprecation_for("AddComponent4")
    assert reps and any("AddComponent5" in r for r in reps)
    rec = cosmon_db.member_info("AssemblyDoc", "AddComponent4")
    assert rec.get("deprecated") is True
    assert rec.get("replacements")


@needs_db
def test_enum_info_has_compact_member_table():
    info = cosmon_db.enum_info("swEndConditions_e")
    assert info is not None
    assert "swEndCondBlind" in (info["members"] or "")
    # Compact: the member table, not the whole stripped_doc page.
    assert len(info["members"]) < 6000


@needs_db
def test_search_members_is_instant_and_relevant():
    hits = cosmon_db.search_members("hole wizard depth")
    assert hits
    assert any("Hole" in h["id"] for h in hits)


@needs_db
def test_feature_recipes_match_query():
    recipes = cosmon_db.feature_recipes("hole wizard")
    assert recipes
    assert any("HoleWizard" in (r["description"] or "") or
               "WizardHole" in (r["feature_data_interface"] or "")
               for r in recipes)


@needs_db
def test_lint_warns_on_deprecated_call():
    code = (
        "Option Explicit\n"
        "Sub main()\n"
        "Dim swAsm As Object, c As Object\n"
        'Set c = swAsm.AddComponent4("C:\\p.sldprt", "", 0, 0, 0)\n'
        "End Sub\n"
    )
    res = vba_lint.validate(code)
    dep = [w for w in res["warnings"] if w["kind"] == "deprecated"]
    assert dep and "AddComponent5" in dep[0]["message"]
