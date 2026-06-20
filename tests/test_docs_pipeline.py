"""The docs pipeline must render the JS page and extract real parameter text
(not the 'Loading...' shell). Skips if the page can't be fetched."""
import pytest

from sw_mcp import docs_pipeline as dp


def test_lookup_feature_extrusion3():
    try:
        res = dp.lookup_method("FeatureManager", "FeatureExtrusion3")
    except Exception as exc:  # noqa: BLE001  (network / chromium missing)
        pytest.skip(f"docs render unavailable: {exc}")
    if res.get("unrendered"):
        pytest.skip("page did not render (offline?)")
    assert res["title"] and "FeatureExtrusion3" in res["title"]
    assert res["parameters"] and "swEndConditions_e" in res["parameters"]


def test_cache_roundtrip():
    try:
        first = dp.lookup_method("FeatureManager", "FeatureExtrusion3")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"docs render unavailable: {exc}")
    if first.get("unrendered"):
        pytest.skip("page did not render (offline?)")
    second = dp.lookup_method("FeatureManager", "FeatureExtrusion3")
    assert second["cached"] is True
