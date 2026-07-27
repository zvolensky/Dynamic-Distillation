import copy
import json
from pathlib import Path

from dynamic_distillation.core_v3.dd116_gate_adjudication_v1 import (
    adjudicate_dd116_representation_gate,
)


ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    return json.loads((ROOT / "logs" / name).read_text(encoding="utf-8"))


def _evidence():
    return (
        _load("dd116_core_v3_initializer_handoff_term_audit_contract_20260727.json"),
        _load("dd116_core_v3_initializer_handoff_term_audit_20260727.json"),
        _load("dd115_core_v3_initializer_first_step_refinement_contract_20260727.json"),
        _load("dd115_core_v3_initializer_first_step_refinement_20260727.json"),
    )


def test_dd117_real_evidence_passes_representation_adjudication():
    audit = adjudicate_dd116_representation_gate(*_evidence())

    assert audit.source_failed_gates == ("physical_reproduction",)
    assert not audit.unexpected_source_failures
    assert audit.replacement_gates["physical_reproduction"]
    assert audit.replacement_gates["nominal_effective_rate_representation_proven"]
    assert audit.pass_gate


def test_dd117_rejects_changed_physical_reproduction():
    contract, result, dd115_contract, dd115_result = _evidence()
    changed = copy.deepcopy(result)
    changed["snapshots"]["half_step"]["metrics"]["temperature_reproduction_F"] = 1.0

    audit = adjudicate_dd116_representation_gate(
        contract, changed, dd115_contract, dd115_result
    )

    assert not audit.replacement_gates["physical_reproduction"]
    assert not audit.pass_gate


def test_dd117_rejects_changed_effective_rate():
    contract, result, dd115_contract, dd115_result = _evidence()
    changed = copy.deepcopy(dd115_result)
    changed["outcomes"]["half1"]["component_rate_lbmolph"][0][0] += 1.0

    audit = adjudicate_dd116_representation_gate(
        contract, result, dd115_contract, changed
    )

    assert not audit.replacement_gates["nominal_effective_rate_representation_proven"]
    assert not audit.pass_gate


def test_dd117_cannot_override_unrelated_failure():
    contract, result, dd115_contract, dd115_result = _evidence()
    changed = copy.deepcopy(result)
    changed["gates"]["energy_reconciliation"] = False

    audit = adjudicate_dd116_representation_gate(
        contract, changed, dd115_contract, dd115_result
    )

    assert audit.unexpected_source_failures == ("energy_reconciliation",)
    assert not audit.pass_gate
