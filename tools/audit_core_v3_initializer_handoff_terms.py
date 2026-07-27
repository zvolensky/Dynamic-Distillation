#!/usr/bin/env python
"""Prepare or execute the frozen DD-116 initializer handoff term audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_pressure_layer_numerical as dd102
from dynamic_distillation.core_v3.conserved_nu_pressure_dae_contract_v1 import (
    audit_conserved_nu_pressure_dae_contract,
    build_conserved_nu_pressure_dae_contract,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_numerical_v1 import (
    evaluate_conserved_nu_pressure_residual,
)
from dynamic_distillation.core_v3.handoff_balance_audit_v1 import (
    BalanceTermLedger,
    build_balance_term_ledger,
    ranked_component_term_changes,
    ranked_energy_term_changes,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureLinkGeometry,
    PressureNumericalSpec,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    VAPOR_LINKS,
    VOLUME_IDS,
)


SCHEMA = "dd116-core-v3-initializer-handoff-term-audit-contract-v1"
RESULT_SCHEMA = "dd116-core-v3-initializer-handoff-term-audit-result-v1"
DD112_CONTRACT = Path("logs/dd112_core_v3_conserved_nu_pressure_initializer_contract_20260726.json")
DD112_RESULT = Path("logs/dd112_core_v3_conserved_nu_pressure_initializer_20260726.json")
DD114_RESULT = Path("logs/dd114_core_v3_initializer_zero_time_audit_20260727.json")
DD115_CONTRACT = Path("logs/dd115_core_v3_initializer_first_step_refinement_contract_20260727.json")
DD115_RESULT = Path("logs/dd115_core_v3_initializer_first_step_refinement_20260727.json")
CONTRACT = Path("logs/dd116_core_v3_initializer_handoff_term_audit_contract_20260727.json")
RESULT = Path("logs/dd116_core_v3_initializer_handoff_term_audit_20260727.json")
CONTRACT_DOC = Path("docs/dd_116_core_v3_initializer_handoff_term_audit_contract_20260727.md")
RESULT_DOC = Path("docs/dd_116_core_v3_initializer_handoff_term_audit_20260727.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/handoff_balance_audit_v1.py",
    "src/dynamic_distillation/core_v3/conserved_nu_pressure_numerical_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "tests/test_core_v3_handoff_balance_audit_v1.py",
    "tools/audit_core_v3_initializer_handoff_terms.py",
    "tools/audit_core_v3_pressure_layer_numerical.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape((-1,))]


def _snapshot_payloads(dd114: Mapping[str, Any], dd115_contract: Mapping[str, Any], dd115: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "zero_time": {
            "inventory_lbmol": dd115_contract["previous_inventory_lbmol"],
            "lower_internal_energy_BTU": dd115_contract["previous_lower_internal_energy_BTU"],
            "coordinates": dd115_contract["initial_coordinates"],
            "component_rate_lbmolph": dd115_contract["initial_component_rate_lbmolph"],
            "internal_energy_rate_BTUph": dd115_contract["initial_internal_energy_rate_BTUph"],
            "physical_reference": dd114["fresh_endpoint"],
            "time_sec": 0.0,
        },
        "half_step": {
            "inventory_lbmol": dd115["outcomes"]["half1"]["inventory_lbmol"],
            "lower_internal_energy_BTU": dd115["outcomes"]["half1"]["lower_internal_energy_BTU"],
            "coordinates": dd115["outcomes"]["half1"]["final_coordinates"],
            "component_rate_lbmolph": dd115["outcomes"]["half1"]["component_rate_lbmolph"],
            "internal_energy_rate_BTUph": dd115["outcomes"]["half1"]["internal_energy_rate_BTUph"],
            "physical_reference": dd115["outcomes"]["half1"],
            "time_sec": 0.5,
        },
        "refined_one_second": {
            "inventory_lbmol": dd115["outcomes"]["half2"]["inventory_lbmol"],
            "lower_internal_energy_BTU": dd115["outcomes"]["half2"]["lower_internal_energy_BTU"],
            "coordinates": dd115["outcomes"]["half2"]["final_coordinates"],
            "component_rate_lbmolph": dd115["outcomes"]["half2"]["component_rate_lbmolph"],
            "internal_energy_rate_BTUph": dd115["outcomes"]["half2"]["internal_energy_rate_BTUph"],
            "physical_reference": dd115["outcomes"]["half2"],
            "time_sec": 1.0,
        },
    }


def prepare() -> dict[str, Any]:
    dd112_contract = _load(DD112_CONTRACT)
    dd112_result = _load(DD112_RESULT)
    dd114 = _load(DD114_RESULT)
    dd115_contract = _load(DD115_CONTRACT)
    dd115 = _load(DD115_RESULT)
    if not dd114["pass"] or dd114["decision"] != "authorize_frozen_first_step_refinement_contract":
        raise RuntimeError("DD-116 requires the accepted DD-114 endpoint")
    if dd115["pass"] or dd115["decision"] != "stop_initializer_dynamic_handoff":
        raise RuntimeError("DD-116 requires the immutable failed DD-115 handoff")
    snapshots = _snapshot_payloads(dd114, dd115_contract, dd115)
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (
                DD112_CONTRACT,
                DD112_RESULT,
                DD114_RESULT,
                DD115_CONTRACT,
                DD115_RESULT,
            )
        },
        "source_contract_commits": {
            "dd112": dd112_result["contract_commit"],
            "dd114": dd114["contract_commit"],
            "dd115": dd115["contract_commit"],
        },
        "snapshot_sha256": {
            name: _hash(snapshot) for name, snapshot in snapshots.items()
        },
        "snapshot_order": list(snapshots),
        "material_rate_scale_lbmolph": float(dd115_contract["component_rate_scale_lbmolph"]),
        "energy_rate_scale_BTUph": float(max(dd112_contract["energy_rate_scales_BTUph"])),
        "component_rate_reconciliation_limit": 1.0e-10,
        "energy_rate_reconciliation_limit": 1.0e-10,
        "physical_reproduction_limit": 1.0e-8,
        "pressure_reproduction_limit_psia": 1.0e-7,
        "temperature_reproduction_limit_F": 1.0e-6,
        "ownership_change_limit": 0,
        "provider_call_limit": 5000,
        "wall_clock_limit_sec": 30.0,
        "permitted_live_residual_evaluations": 3,
        "initializer_objective_blocks": {
            "conserved_state": [0, 19],
            "conserved_rate": [19, 38],
            "algebraic": [38, 65],
        },
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "any DD-112, DD-114, or DD-115 evidence hash changes",
            "any frozen snapshot or DD-116 implementation hash changes",
            "more or fewer than three saved-state residual/property evaluations are attempted",
            "a nonlinear solve, Jacobian, timestep, controller, trajectory, or initializer is attempted",
            "a reported component or energy rate cannot be reconciled from its signed physical terms",
            "a saved physical state cannot be reproduced",
            "balance ownership changes between snapshots",
            "provider ownership, call count, or wall-clock limits fail",
        ],
        "authorization_on_pass": "structural_slow_start_feasibility_audit_only",
        "live_property_evaluation_attempted": False,
        "residual_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "jacobian_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "audit_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-116 Frozen Core V3 Initializer Handoff Term Audit Contract",
                "",
                f"- Base commit: `{payload['preparation_base_commit']}`",
                f"- Contract payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Frozen snapshots: `t=0`, refined `t=0.5 s`, refined `t=1.0 s`",
                "- Permitted live work: exactly three residual/property evaluations",
                "- Prohibited: solve, Jacobian, timestep, controller, trajectory, or initializer",
                "",
                "The audit independently expands every component and energy balance into signed physical terms, reconciles those sums against the immutable DD-114/DD-115 rates, and ranks the contributors to the largest rate changes. It may distinguish an explained non-steady transient from an ownership or equation discontinuity. Passing authorizes only a property-free structural study of whether a zero-rate or slow-start state is feasible under the retained physical constraints.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def _verify(payload: Mapping[str, Any]) -> None:
    copy = dict(payload)
    expected = copy.pop("contract_payload_sha256")
    if _hash(copy) != expected:
        raise RuntimeError("DD-116 contract checksum mismatch")
    for path, digest in payload["sources"].items():
        if _sha(ROOT / path) != digest:
            raise RuntimeError(f"DD-116 source changed: {path}")
    for path, digest in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != digest:
            raise RuntimeError(f"DD-116 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-116 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def _ledger_record(ledger: BalanceTermLedger) -> dict[str, Any]:
    return {
        "component_terms_lbmolph": {
            volume: {name: _vector(value) for name, value in terms.items()}
            for volume, terms in ledger.component_terms_lbmolph.items()
        },
        "energy_terms_BTUph": {
            volume: {name: float(value) for name, value in terms.items()}
            for volume, terms in ledger.energy_terms_BTUph.items()
        },
        "component_net_lbmolph": np.asarray(ledger.component_net_lbmolph).tolist(),
        "energy_net_BTUph": _vector(ledger.energy_net_BTUph),
    }


def _objective_breakdown(contract: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, float]:
    canonical_name = "dd094_storage_and_pressure_profile"
    canonical = next(item for item in result["starts"] if item["name"] == canonical_name)
    point = np.asarray(canonical["final_coordinates"], dtype=float)
    center = np.asarray(contract["objective_center"], dtype=float)
    weights = np.asarray(contract["objective_weights"], dtype=float)
    delta = point - center
    blocks = {
        "conserved_state": slice(0, 19),
        "conserved_rate": slice(19, 38),
        "algebraic": slice(38, 65),
    }
    values = {
        name: float(0.5 * np.dot(weights[selection] * delta[selection], delta[selection]))
        for name, selection in blocks.items()
    }
    values["total"] = float(sum(values.values()))
    values["maximum_normalized_rate_coordinate"] = float(np.max(np.abs(point[19:38])))
    return values


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    dd112_contract = _load(DD112_CONTRACT)
    dd112_result = _load(DD112_RESULT)
    dd114 = _load(DD114_RESULT)
    dd115_contract = _load(DD115_CONTRACT)
    dd115 = _load(DD115_RESULT)
    snapshots = _snapshot_payloads(dd114, dd115_contract, dd115)
    for name, snapshot in snapshots.items():
        if _hash(snapshot) != payload["snapshot_sha256"][name]:
            raise RuntimeError(f"DD-116 snapshot changed: {name}")

    spec = dd102._spec(
        dd112_contract["source_mapping"],
        float(dd112_contract["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd102._reference(dd112_contract["reference"])
    template = dd102._state(dd112_contract["accepted_root_state"])
    contract = build_conserved_nu_pressure_dae_contract(spec.component_names)
    if not audit_conserved_nu_pressure_dae_contract(contract).pass_gate:
        raise RuntimeError("DD-116 structural prerequisite changed")
    provider = dd102._provider(
        Path(dd112_contract["workbook"]), dd112_contract["property_package"]
    )
    call_audit = ProviderCallAudit()
    molecular_weight = call_audit.component_molecular_weights(
        provider,
        caller="dd116_molecular_weight",
        state_id="dd116:preparation",
        evaluation_kind="preparation",
    )
    pressure_numerical = PressureNumericalSpec(
        reference_pressure_psia=np.asarray(dd112_contract["pressure_reference_psia"]),
        pressure_coordinate_scale_psia=float(dd112_contract["pressure_coordinate_scale_psia"]),
        pressure_residual_scale_psia=float(dd112_contract["pressure_residual_scale_psia"]),
        dry_tray_pressure_drop_coefficient=float(dd112_contract["dry_tray_pressure_drop_coefficient"]),
        component_mw_lbm_per_lbmol=molecular_weight,
        link_geometry=tuple(
            PressureLinkGeometry(**item) for item in dd112_contract["pressure_link_geometry"]
        ),
        enforce_pressure_order=False,
    )
    started = time.perf_counter()
    ledgers: dict[str, BalanceTermLedger] = {}
    records: dict[str, Any] = {}
    component_scale = float(payload["material_rate_scale_lbmolph"])
    energy_scale = float(payload["energy_rate_scale_BTUph"])
    for name in payload["snapshot_order"]:
        snapshot = snapshots[name]
        evaluation = evaluate_conserved_nu_pressure_residual(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            inventory_lbmol=snapshot["inventory_lbmol"],
            lower_internal_energy_BTU=snapshot["lower_internal_energy_BTU"],
            top_storage_gradient_BTU_lbmol=np.zeros(len(spec.component_names)),
            energy_rate_scales_BTUph=dd112_contract["energy_rate_scales_BTUph"],
            solve_coordinates=snapshot["coordinates"],
            fixed_steady_scales=dd112_contract["fixed_steady_residual_scales"],
            storage_scales_BTU=dd112_contract["storage_scales_BTU"],
            numerical=pressure_numerical,
            state_id=f"dd116:{name}",
            evaluation_kind="residual",
        )
        base = evaluation.pressure_evaluation.base_evaluation
        steady = base.steady_evaluation
        state = base.physical_state
        ledger = build_balance_term_ledger(spec, state, steady.properties)
        ledgers[name] = ledger
        expected_component = np.asarray(snapshot["component_rate_lbmolph"], dtype=float)
        expected_energy = np.asarray(snapshot["internal_energy_rate_BTUph"], dtype=float)
        physical_reference = snapshot["physical_reference"]
        metrics = {
            "component_rate_reconciliation": float(np.max(np.abs(ledger.component_net_lbmolph - expected_component)) / component_scale),
            "energy_rate_reconciliation": float(np.max(np.abs(ledger.energy_net_BTUph - expected_energy)) / energy_scale),
            "component_coordinate_reproduction": float(np.max(np.abs(evaluation.component_rate_lbmolph - expected_component)) / component_scale),
            "pressure_reproduction_psia": float(np.max(np.abs(evaluation.pressure_evaluation.pressure_psia - np.asarray(physical_reference["pressure_psia"])))),
            "temperature_reproduction_F": float(np.max(np.abs(np.asarray(state.temperature_F) - np.asarray(physical_reference["temperature_F"])))),
            "liquid_flow_reproduction": float(np.max(np.abs(np.asarray(state.hydraulic_liquid_flow_lbmolph) - np.asarray(physical_reference["liquid_flow_lbmolph"]))) / component_scale),
            "vapor_flow_reproduction": float(np.max(np.abs(np.asarray(state.vapor_flow_lbmolph) - np.asarray(physical_reference["vapor_flow_lbmolph"]))) / component_scale),
            "distillate_reproduction": abs(float(state.distillate_lbmolph) - float(physical_reference["distillate_lbmolph"])) / component_scale,
            "bottoms_reproduction": abs(float(state.bottoms_lbmolph) - float(physical_reference["bottoms_lbmolph"])) / component_scale,
            "condenser_duty_reproduction": abs(float(state.condenser_duty_BTUph) - float(physical_reference["condenser_duty_BTUph"])) / energy_scale,
        }
        records[name] = {
            "time_sec": float(snapshot["time_sec"]),
            "metrics": metrics,
            "pressure_psia": _vector(evaluation.pressure_evaluation.pressure_psia),
            "temperature_F": _vector(state.temperature_F),
            "liquid_flow_lbmolph": _vector(state.hydraulic_liquid_flow_lbmolph),
            "vapor_flow_lbmolph": _vector(state.vapor_flow_lbmolph),
            "liquid_enthalpy_BTU_lbmol": _vector(steady.properties.liquid_enthalpy_BTU_lbmol),
            "vapor_enthalpy_BTU_lbmol": _vector(steady.properties.vapor_enthalpy_BTU_lbmol),
            "ledger": _ledger_record(ledger),
        }

    zero = ledgers["zero_time"]
    half = ledgers["half_step"]
    zero_component = zero.component_net_lbmolph
    half_component = half.component_net_lbmolph
    component_delta = half_component - zero_component
    worst_component_flat = int(np.argmax(np.abs(component_delta)))
    worst_volume_index, worst_component_index = np.unravel_index(
        worst_component_flat, component_delta.shape
    )
    energy_delta = half.energy_net_BTUph - zero.energy_net_BTUph
    worst_energy_index = int(np.argmax(np.abs(energy_delta)))
    component_terms = ranked_component_term_changes(
        zero,
        half,
        volume=VOLUME_IDS[worst_volume_index],
        component_index=worst_component_index,
    )
    energy_terms = ranked_energy_term_changes(
        zero,
        half,
        volume=VOLUME_IDS[worst_energy_index],
    )
    zero_vapor = np.asarray(records["zero_time"]["vapor_flow_lbmolph"])
    half_vapor = np.asarray(records["half_step"]["vapor_flow_lbmolph"])
    link_index = int(np.argmax(np.abs(half_vapor - zero_vapor)))
    ownership_signatures = {
        name: {
            "component": {
                volume: list(ledger.component_terms_lbmolph[volume]) for volume in VOLUME_IDS
            },
            "energy": {
                volume: list(ledger.energy_terms_BTUph[volume]) for volume in VOLUME_IDS
            },
        }
        for name, ledger in ledgers.items()
    }
    ownership_changes = sum(
        ownership_signatures[name] != ownership_signatures["zero_time"]
        for name in payload["snapshot_order"][1:]
    )
    elapsed = time.perf_counter() - started
    provenance = call_audit.report()
    all_metrics = [record["metrics"] for record in records.values()]
    gates = {
        "component_reconciliation": all(item["component_rate_reconciliation"] < payload["component_rate_reconciliation_limit"] for item in all_metrics),
        "energy_reconciliation": all(item["energy_rate_reconciliation"] < payload["energy_rate_reconciliation_limit"] for item in all_metrics),
        "physical_reproduction": all(
            max(
                item["component_coordinate_reproduction"],
                item["liquid_flow_reproduction"],
                item["vapor_flow_reproduction"],
                item["distillate_reproduction"],
                item["bottoms_reproduction"],
                item["condenser_duty_reproduction"],
            ) < payload["physical_reproduction_limit"]
            and item["pressure_reproduction_psia"] < payload["pressure_reproduction_limit_psia"]
            and item["temperature_reproduction_F"] < payload["temperature_reproduction_limit_F"]
            for item in all_metrics
        ),
        "ownership_unchanged": ownership_changes <= payload["ownership_change_limit"],
        "provider": bool(provenance["pass"]),
        "calls": provenance["total_calls"] < payload["provider_call_limit"],
        "wall": elapsed < payload["wall_clock_limit_sec"],
        "exactly_three_evaluations": len(records) == payload["permitted_live_residual_evaluations"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "balance_explained_nonsteady_transient"
            if passed
            else "handoff_discontinuity_not_resolved"
        ),
        "decision": (
            "authorize_structural_slow_start_feasibility_audit"
            if passed
            else "stop_core_v3_initializer_work"
        ),
        "snapshots": records,
        "largest_initial_component_rate_change": {
            "volume": VOLUME_IDS[worst_volume_index],
            "component": spec.component_names[worst_component_index],
            "change_lbmolph": float(component_delta[worst_volume_index, worst_component_index]),
            "term_changes_lbmolph": [
                {"term": name, "change": value} for name, value in component_terms
            ],
            "term_sum_lbmolph": float(sum(value for _name, value in component_terms)),
        },
        "largest_initial_energy_rate_change": {
            "volume": VOLUME_IDS[worst_energy_index],
            "change_BTUph": float(energy_delta[worst_energy_index]),
            "term_changes_BTUph": [
                {"term": name, "change": value} for name, value in energy_terms
            ],
            "term_sum_BTUph": float(sum(value for _name, value in energy_terms)),
        },
        "largest_initial_vapor_link_change": {
            "link": VAPOR_LINKS[link_index][2],
            "change_lbmolph": float(half_vapor[link_index] - zero_vapor[link_index]),
        },
        "initializer_objective_breakdown": _objective_breakdown(dd112_contract, dd112_result),
        "ownership_signatures": ownership_signatures,
        "ownership_changes": int(ownership_changes),
        "provider_provenance": provenance,
        "wall_clock_sec": float(elapsed),
        "gates": gates,
        "pass": bool(passed),
        "live_residual_evaluations": len(records),
        "nonlinear_solve_attempted": False,
        "jacobian_attempted": False,
        "timestep_attempted": False,
        "controller_attempted": False,
        "dynamic_integration_attempted": False,
        "audit_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-116 Core V3 Initializer Handoff Term Audit Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Wall clock: `{elapsed:.3f} s`",
                f"- Provider calls: `{provenance['total_calls']}`",
                f"- Largest component-rate change: `{result['largest_initial_component_rate_change']['volume']}` / `{result['largest_initial_component_rate_change']['component']}` = `{result['largest_initial_component_rate_change']['change_lbmolph']:.6f} lbmol/h`",
                f"- Largest energy-rate change: `{result['largest_initial_energy_rate_change']['volume']}` = `{result['largest_initial_energy_rate_change']['change_BTUph']:.6f} BTU/h`",
                f"- Largest vapor-link change: `{result['largest_initial_vapor_link_change']['link']}` = `{result['largest_initial_vapor_link_change']['change_lbmolph']:.6f} lbmol/h`",
                "- Solve, Jacobian, timestep, controller, or trajectory: `False`",
                "",
            )
        ),
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    arguments = parser.parse_args()
    output = prepare() if arguments.prepare else execute()
    print(json.dumps(output, indent=2))
