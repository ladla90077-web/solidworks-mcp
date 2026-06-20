def test_connects_and_reports_sw2022(sw):
    assert sw["connected"] is True
    assert sw["revision"], "expected a revision string"
    assert sw["year"] == 2022, f"expected SolidWorks 2022, got {sw['year']}"
