"""The proactive design-knowledge layer (pure Python - no SolidWorks needed).

Guards that get_design_guidance routes a part description to the right archetype
recipe, returns focused (not exhaustive) principles, surfaces GD&T only for
tolerancing queries, and that the playbook renders.
"""
from sw_mcp import design_library as dl


def test_catalogue_is_well_formed():
    assert len(dl.RECIPES) >= 6
    assert len(dl.PRINCIPLES) >= 20
    for r in dl.RECIPES:
        for key in ("name", "archetype", "keywords", "summary",
                    "feature_sequence", "design_intent", "key_dimensions", "source"):
            assert r[key], f"{r['name']} missing {key}"
        assert len(r["feature_sequence"]) >= 3
    ids = [p["id"] for p in dl.PRINCIPLES]
    assert len(ids) == len(set(ids)), "duplicate principle ids"


def test_empty_query_returns_full_orientation():
    g = dl.get_guidance("")
    assert len(g["principles"]) == len(dl.PRINCIPLES)
    assert len(g["recipes"]) == len(dl.RECIPES)


def test_routes_to_expected_archetype():
    cases = {
        "deep-groove ball bearing": "Deep-groove ball bearing",
        "hollow exhaust manifold": "Exhaust manifold",
        "thin-wall plastic bottle": "Surface-modeled plastic bottle",
        "mounting base plate with bolt circle": "Mounting base plate",
        "revolved machined housing with tapped holes":
            "Revolved machined housing (Exercise-263)",
    }
    for query, expected in cases.items():
        names = [r.get("name") for r in dl.get_guidance(query)["recipes"]]
        assert expected in names, f"{query!r} -> {names}, expected {expected}"


def test_principles_are_focused_not_exhaustive():
    # A specific query must NOT dump the entire principle catalogue; it returns
    # the matched ones plus the four foundational principles only.
    g = dl.get_guidance("plastic bottle thin wall")
    ids = {p["id"] for p in g["principles"]}
    assert {"P01", "P02", "P03", "P09"}.issubset(ids)  # foundational always present
    assert "P14" in ids                                 # surface-first (relevant)
    assert len(ids) < len(dl.PRINCIPLES)                # focused, not everything


def test_gdnt_only_for_tolerancing_queries():
    assert "gdnt" in dl.get_guidance("shaft tolerance datum fit")
    assert "gdnt" not in dl.get_guidance("simple cylinder")


def test_unmatched_query_still_nudges_professional():
    g = dl.get_guidance("design a plain cube")
    # No archetype, but foundational principles + a recipe index are returned.
    ids = {p["id"] for p in g["principles"]}
    assert {"P01", "P02", "P03", "P09"}.issubset(ids)
    assert g["recipes"]  # the fallback note + index


def test_playbook_renders():
    md = dl.render_playbook_md()
    assert "Professional Design Playbook" in md
    for r in dl.RECIPES:
        assert r["name"] in md
    assert "GD&T reference" in md
