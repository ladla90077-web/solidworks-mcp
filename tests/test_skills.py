import pytest

from sw_mcp import skills


@pytest.fixture(autouse=True)
def _close_docs():
    """Override the integration-test cleanup fixture for pure filesystem tests."""
    yield


def test_all_bundled_skills_parse():
    items = skills.list_skills()
    slugs = {item["slug"] for item in items}
    assert len(items) >= 12
    assert {"drawing-plan", "drawing-review", "setup-full-simulation"} <= slugs
    assert all(item["name"] and not item.get("error") for item in items)


def test_skill_crud_uses_user_override(tmp_path, monkeypatch):
    monkeypatch.setenv("SW_MCP_SKILLS_DIR", str(tmp_path / "skills"))
    made = skills.create_skill("Fixture Checker", "Checks fixtures", "Follow the fixture checklist.")
    assert made["slug"] == "fixture-checker"
    assert made["source"] == "user"
    edited = skills.update_skill("fixture-checker", instructions="Use the revised checklist.")
    assert "revised" in edited["instructions"]
    with pytest.raises(ValueError, match="confirm"):
        skills.delete_skill("fixture-checker")
    assert skills.delete_skill("fixture-checker", confirm=True)["deleted"]


def test_skill_paths_are_contained(tmp_path, monkeypatch):
    monkeypatch.setenv("SW_MCP_SKILLS_DIR", str(tmp_path / "skills"))
    with pytest.raises(ValueError):
        skills.get_skill("../outside")


def test_folded_frontmatter_description():
    meta, body = skills.parse_skill("---\nname: Test\ndescription: >-\n  first line\n  second line\n---\n\nDo it")
    assert meta["description"] == "first line second line"
    assert body == "Do it"
