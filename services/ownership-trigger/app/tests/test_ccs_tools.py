import re
from ..ccs_tools import ccs_get_meter_reads, _mask_nmi


def test_mask_nmi_basic():
    assert _mask_nmi("70011233").endswith("1233")
    assert set(_mask_nmi("70011233")[:-4]) == {"*"}


def test_get_meter_reads_schema():
    out = ccs_get_meter_reads(nmi="70011233", from_date=None, to_date=None, user="tester", purpose_of_use="care-coordination")
    assert isinstance(out, dict)
    assert "reads" in out and isinstance(out["reads"], list)
    assert len(out["reads"]) >= 1
    r0 = out["reads"][0]
    assert set(["read_type", "date", "value"]).issubset(r0.keys())
    assert r0["read_type"] in ("ACTUAL", "ESTIMATE")
    # ISO date format (YYYY-MM-DD)
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", r0["date"]) is not None
    assert isinstance(r0["value"], (int, float))


def test_get_meter_reads_date_range_validation():
    # from_date > to_date should raise
    try:
        ccs_get_meter_reads(nmi="70011233", from_date="2025-12-02", to_date="2025-12-01", user="tester", purpose_of_use="care-coordination")
        assert False, "Expected ValueError for invalid date range"
    except ValueError:
        pass


def test_sacsf_controls_logging_and_purpose(capsys):
    # Ensure we log masked NMI and purpose-of-use per SACSF AC-3/LG-1
    ccs_get_meter_reads(nmi="70011233", from_date=None, to_date=None, user="auditor", purpose_of_use="care-coordination")
    captured = capsys.readouterr().out
    assert "SACSF" in captured
    assert "ccs.get_meter_reads.access" in captured
    assert "nmi_masked" in captured and "70011233" not in captured
    assert captured.count("*") >= 1
    assert "care-coordination" in captured
