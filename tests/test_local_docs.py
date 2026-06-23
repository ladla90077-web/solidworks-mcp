"""Local CHM docs layer.

Pure-function tests (parsing, syntax selection, PS quoting) run anywhere.
The integration tests that actually read the extracted CHMs are skipped when
SolidWorks isn't installed on the machine.
"""
import pytest

from sw_mcp import local_docs as ld

_HAVE_DOCS = ld.available()
needs_docs = pytest.mark.skipif(not _HAVE_DOCS,
                                reason="SolidWorks API CHMs not installed")


# --- Pure functions --------------------------------------------------------
def test_ps_quote_escapes_single_quotes():
    assert ld._ps_quote(r"C:\a b\c") == r"'C:\a b\c'"
    assert ld._ps_quote("it's") == "'it''s'"


def test_clean_strips_bom_and_nbsp():
    assert ld._clean("﻿hello\xa0world") == "hello world"


def test_best_syntax_prefers_real_vba_over_net():
    s = {"syntax": "retval = obj.Foo(a, b)", "syntax_net": "Function Foo(...)"}
    assert ld._best_syntax(s) == "retval = obj.Foo(a, b)"


def test_best_syntax_falls_back_to_net_when_vba_is_crossref():
    s = {"syntax": "See FeatureManager::FeatureExtrusion3 .",
         "syntax_net": "Function FeatureExtrusion3(ByVal Sd As Boolean)"}
    assert ld._best_syntax(s).startswith("Function FeatureExtrusion3")


def test_parse_topic_splits_sections():
    html = """<html><head><title>Foo Method (IBar)</title></head><body>
    <h1>Visual Basic for Applications (VBA) Syntax</h1>
    <p>retval = obj.Foo(a)</p>
    <h4>Parameters</h4><p>a description here</p>
    <h1>Return Value</h1><p>True if ok</p>
    <h1>Remarks</h1><p>call inside a sketch</p>
    <h1>Example</h1><p>Dim x</p>
    </body></html>"""
    parsed = ld._parse_topic(html)
    assert parsed["title"] == "Foo Method (IBar)"
    s = parsed["sections"]
    assert "obj.Foo(a)" in s["syntax"]
    assert "description here" in s["parameters"]
    assert "True if ok" in s["return_value"]
    assert "inside a sketch" in s["remarks"]
    assert "Dim x" in s["example"]


# --- Integration (needs the installed CHMs) --------------------------------
@needs_docs
def test_extraction_builds_key_index():
    st = ld.ensure_extracted()
    assert st["ready"] is True
    assert st["topics"] > 1000  # the API CHM alone has thousands of topics


@needs_docs
def test_lookup_method_returns_signature_and_remarks():
    m = ld.local_method("FeatureManager", "FeatureExtrusion3")
    assert m is not None
    assert "FeatureExtrusion3" in (m["title"] or "")
    assert m["syntax"] and "FeatureExtrusion3" in m["syntax"]
    assert m["parameters"] and "Sd" in m["parameters"]
    assert m["source"] == "local-chm"


@needs_docs
def test_lookup_method_interface_agnostic_fallback():
    # ModelDoc2 has no FeatureExtrusion3; we should still resolve it and say so.
    m = ld.local_method("ModelDoc2", "FeatureExtrusion3")
    assert m is not None
    assert m.get("note") and "FeatureManager" in m["note"]


@needs_docs
def test_lookup_enum_returns_members():
    e = ld.local_enum("swEndConditions_e")
    assert e is not None
    assert "swEndCond" in (e["members"] or "")


@needs_docs
def test_search_finds_topics():
    res = ld.search("circular pattern feature", limit=5)
    assert res["available"] is True
    assert res["hits"]
    assert any("CircularPattern" in h["title"] for h in res["hits"])


@needs_docs
def test_missing_method_returns_none():
    assert ld.local_method("FeatureManager", "NoSuchMethodXyz123") is None
