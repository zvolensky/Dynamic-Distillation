import copy
import json
from pathlib import Path

import numpy as np

from dynamic_distillation.core_v3.dd109_gate_adjudication_v1 import (
    adjudicate_dd109_physical_gates,
)


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "logs/dd109_core_v3_conserved_nu_pressure_numerical_20260726.json"
CONTRACT = ROOT / "logs/dd109_core_v3_conserved_nu_pressure_numerical_contract_20260726.json"


def _evidence():
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    return result, contract["pressure_link_geometry"]


def test_dd110_real_dd109_evidence_passes_applicability_adjudication():
    result, geometry = _evidence()
    audit = adjudicate_dd109_physical_gates(result, geometry)

    assert audit.source_failed_gates == (
        "finite_physical_state",
        "positive_pressure_and_geometry_terms",
    )
    assert not audit.unexpected_source_failures
    assert audit.applicable_volume_indices == (1, 2, 3)
    assert audit.terminal_sentinel_indices == (0, 4)
    assert audit.replacement_gates["terminal_height_sentinels"]
    assert audit.pass_gate


def test_dd110_rejects_nonfinite_applicable_tray_height():
    result, geometry = _evidence()
    changed = copy.deepcopy(result)
    changed["states"][0]["liquid_height_ft"][2] = np.nan

    audit = adjudicate_dd109_physical_gates(changed, geometry)

    assert not audit.replacement_gates["finite_physical_state"]
    assert not audit.replacement_gates["positive_pressure_and_geometry_terms"]
    assert not audit.pass_gate


def test_dd110_requires_terminal_height_sentinels():
    result, geometry = _evidence()
    changed = copy.deepcopy(result)
    changed["states"][0]["liquid_height_ft"][0] = 1.0

    audit = adjudicate_dd109_physical_gates(changed, geometry)

    assert not audit.replacement_gates["terminal_height_sentinels"]
    assert not audit.pass_gate


def test_dd110_rejects_liquid_head_on_dry_only_link():
    result, geometry = _evidence()
    changed = copy.deepcopy(result)
    dry_link = next(
        index for index, item in enumerate(geometry) if not item["include_liquid_head"]
    )
    changed["states"][0]["liquid_head_drop_psia"][dry_link] = 0.01

    audit = adjudicate_dd109_physical_gates(changed, geometry)

    assert not audit.replacement_gates["positive_pressure_and_geometry_terms"]
    assert not audit.pass_gate


def test_dd110_cannot_override_an_unrelated_failed_gate():
    result, geometry = _evidence()
    changed = copy.deepcopy(result)
    changed["gates"]["rank"] = False

    audit = adjudicate_dd109_physical_gates(changed, geometry)

    assert audit.unexpected_source_failures == ("rank",)
    assert not audit.pass_gate
