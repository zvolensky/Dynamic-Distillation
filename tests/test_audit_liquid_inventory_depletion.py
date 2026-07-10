from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "audit_liquid_inventory_depletion.py"
_SPEC = spec_from_file_location("audit_liquid_inventory_depletion", _TOOL_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def test_audit_flags_low_inventory_and_large_update_fraction():
    rows = [
        {
            "time_s": "0",
            "stage": "2",
            "node_type": "stage",
            "ML_lbmol": "2.0",
            "dMLdt_total_lbmolps": "-0.2",
            "x_A": "0.5",
            "x_B": "0.5",
        },
        {
            "time_s": "1",
            "stage": "2",
            "node_type": "stage",
            "ML_lbmol": "0.8",
            "dMLdt_total_lbmolps": "-0.2",
            "x_A": "0.9",
            "x_B": "0.1",
        },
        {
            "time_s": "0",
            "stage": "3",
            "node_type": "stage",
            "ML_lbmol": "20.0",
            "dMLdt_total_lbmolps": "0.01",
            "x_A": "0.4",
            "x_B": "0.6",
        },
        {
            "time_s": "1",
            "stage": "3",
            "node_type": "stage",
            "ML_lbmol": "20.01",
            "dMLdt_total_lbmolps": "0.01",
            "x_A": "0.41",
            "x_B": "0.59",
        },
    ]

    report = _MOD.audit_profile(
        rows,
        min_liquid_lbmol=1.0,
        update_fraction_limit=0.05,
        include_terminal_stages=True,
    )

    assert report["passed"] is False
    assert report["risk_count"] == 1
    risky = [r for r in report["stage_records"] if r["stage_1based"] == 2][0]
    assert risky["below_min_liquid"] is True
    assert risky["update_fraction_exceeds_limit"] is True
    assert risky["worst_composition_step_component"] == "A"


def test_audit_passes_for_well_buffered_inventory():
    rows = [
        {
            "time_s": "0",
            "stage": "2",
            "node_type": "stage",
            "ML_lbmol": "20",
            "dMLdt_total_lbmolps": "-0.01",
            "x_A": "0.5",
        },
        {
            "time_s": "1",
            "stage": "2",
            "node_type": "stage",
            "ML_lbmol": "19.99",
            "dMLdt_total_lbmolps": "-0.01",
            "x_A": "0.501",
        },
    ]

    report = _MOD.audit_profile(
        rows,
        min_liquid_lbmol=1.0,
        update_fraction_limit=0.05,
        include_terminal_stages=True,
    )

    assert report["passed"] is True
    assert report["risk_count"] == 0
