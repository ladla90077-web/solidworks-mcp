import pytest

from sw_mcp import diagnostics, docs_pipeline, executor, feature_tools, macro_runner
from sw_mcp.performance import fast_mode


@pytest.fixture(autouse=True)
def _close_docs():
    yield


class Flags:
    EnableGraphicsUpdate = True
    EnableFeatureTree = True
    DisplayWhenAdded = True


class Doc:
    def __init__(self):
        self.ActiveView = Flags()
        self.FeatureManager = Flags()
        self.SketchManager = Flags()


class App:
    def __init__(self):
        self.CommandInProgress = False
        self.ActiveDoc = Doc()


def test_fast_mode_restores_every_flag():
    app = App()
    with fast_mode(app):
        assert app.CommandInProgress is True
        assert app.ActiveDoc.ActiveView.EnableGraphicsUpdate is False
        assert app.ActiveDoc.FeatureManager.EnableFeatureTree is False
        assert app.ActiveDoc.SketchManager.DisplayWhenAdded is False
    assert app.CommandInProgress is False
    assert app.ActiveDoc.ActiveView.EnableGraphicsUpdate is True
    assert app.ActiveDoc.FeatureManager.EnableFeatureTree is True
    assert app.ActiveDoc.SketchManager.DisplayWhenAdded is True


def test_executor_rebuilds_and_scans_only_once(tmp_path, monkeypatch):
    app = App()
    calls = {"rebuild": 0, "scan": 0}
    monkeypatch.setattr(macro_runner, "run_inline_vba", lambda *a, **k: {"ran": True, "macro_path": "x"})

    def rebuild(*_a, **kwargs):
        calls["rebuild"] += 1
        assert kwargs["inspect"] is False
        return {"rebuilt": True}

    def scan(_model):
        calls["scan"] += 1
        return {"feature_count": 1, "errors": [], "errored_features": [],
                "warnings": [], "suppressed_features": [], "has_errors": False}

    monkeypatch.setattr(diagnostics, "rebuild", rebuild)
    monkeypatch.setattr(diagnostics, "get_build_errors", scan)
    verdict = executor.run_inline_and_verify(app, "code", str(tmp_path / "run.log"))
    assert verdict["success"] is True
    assert calls == {"rebuild": 1, "scan": 1}


def test_generated_macros_include_reversible_fast_mode(tmp_path):
    code = feature_tools.build_extrusion(10, 10, 10, 2, str(tmp_path / "x.log"))
    assert "SWMCP_FastMode True" in code
    assert "SWMCP_FastMode False" in code
    assert "If buildFailed Then GoTo SWMCP_Cleanup" in code


def test_docs_use_local_and_cosmon_before_web(monkeypatch):
    from sw_mcp import cosmon_resources, local_docs

    monkeypatch.setattr(cosmon_resources, "search", lambda *a, **k: {"hits": [{"path": "cosmon.json"}]})
    monkeypatch.setattr(local_docs, "local_method", lambda *a, **k: {"syntax": "FeatureExtrusion3(...)"})
    monkeypatch.setattr(docs_pipeline, "fetch", lambda *_a, **_k: pytest.fail("web fallback used"))
    result = docs_pipeline.lookup_method("FeatureManager", "FeatureExtrusion3")
    assert result["syntax"] == "FeatureExtrusion3(...)"
    assert result["cosmon_references"][0]["path"] == "cosmon.json"
