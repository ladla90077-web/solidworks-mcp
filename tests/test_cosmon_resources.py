import json

import pytest

from sw_mcp import cosmon_resources


@pytest.fixture(autouse=True)
def _close_docs():
    """Override the integration-test cleanup fixture for pure resource tests."""
    yield


def _fake_cosmon(tmp_path, monkeypatch):
    root = tmp_path / "Cosmon" / "resources"
    sw = root / "extras" / "solidworks"
    guides = sw / "documentation_data" / "programming_guides" / "main"
    functions = sw / "documentation_data" / "function_documentation_db"
    guides.mkdir(parents=True)
    functions.mkdir(parents=True)
    (guides / "selection.md").write_text("Use selection marks before creating a loft.", encoding="utf-8")
    (functions / "functions.json").write_text(json.dumps({"FixtureOnlyFeature999": "Creates a test fixture"}), encoding="utf-8")
    monkeypatch.setenv("COSMON_RESOURCES_DIR", str(root))


def test_status_and_full_resource_search(tmp_path, monkeypatch):
    _fake_cosmon(tmp_path, monkeypatch)
    result = cosmon_resources.search("FixtureOnlyFeature999", "function_docs")
    assert result["hits"]
    assert result["hits"][0]["source"] == "cosmon-install"
    assert cosmon_resources.status()["external_solidworks_available"] is True


def test_get_resource_and_containment(tmp_path, monkeypatch):
    _fake_cosmon(tmp_path, monkeypatch)
    result = cosmon_resources.get_resource("documentation_data/programming_guides/main/selection.md")
    assert "selection marks" in result["text"]
    with pytest.raises(ValueError):
        cosmon_resources.get_resource("../secrets.txt")
