#!/usr/bin/env python
"""Prepare or execute the frozen DD-105 pressure-enabled first-step audit."""

from __future__ import annotations

import argparse
from dataclasses import asdict
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
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    inventory_from_state,
)
from dynamic_distillation.core_v3.implicit_step_v1 import (
    ImplicitStepSettings,
    component_rate_scales,
    governing_storage_vector,
    zero_rate_evaluation,
)
from dynamic_distillation.core_v3.pressure_implicit_dae_contract_v1 import (
    audit_pressure_implicit_dae_contract,
    build_pressure_implicit_dae_contract,
)
from dynamic_distillation.core_v3.pressure_implicit_step_v1 import (
    audit_pressure_step_jacobian,
    evaluate_pressure_backward_euler_residual,
    solve_pressure_backward_euler_step,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureLinkGeometry,
    PressureNumericalSpec,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit


SCHEMA = "dd105-core-v3-pressure-implicit-first-step-contract-v1"
RESULT_SCHEMA = "dd105-core-v3-pressure-implicit-first-step-result-v1"
CONTRACT = Path("logs/dd105_core_v3_pressure_implicit_first_step_contract_20260726.json")
RESULT = Path("logs/dd105_core_v3_pressure_implicit_first_step_20260726.json")
CONTRACT_DOC = Path("docs/dd_105_core_v3_pressure_implicit_first_step_contract_20260726.md")
RESULT_DOC = Path("docs/dd_105_core_v3_pressure_implicit_first_step_20260726.md")
DD103_CONTRACT = Path("logs/dd103_core_v3_pressure_layer_steady_root_contract_20260726.json")
DD103_RESULT = Path("logs/dd103_core_v3_pressure_layer_steady_root_20260726.json")
DD104 = Path("logs/dd104_core_v3_pressure_implicit_dae_20260726.json")
STEPS = (1.0, 0.5)
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/pressure_implicit_dae_contract_v1.py",
    "src/dynamic_distillation/core_v3/pressure_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/pressure_layer_numerical_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "tools/run_core_v3_pressure_implicit_first_step.py",
    "tests/test_core_v3_pressure_implicit_step_v1.py",
)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _vector(value: Any) -> list[float]:
    return [float(item) for item in np.asarray(value, dtype=float).reshape((-1,))]


def _rows(value: Any) -> list[list[float]]:
    return [_vector(row) for row in np.asarray(value, dtype=float)]


def _spectrum_change(a: np.ndarray, b: np.ndarray) -> float:
    denominator = np.maximum.reduce((np.abs(a), np.abs(b), np.full_like(a, 1e-15)))
    return float(np.max(np.abs(a - b) / denominator))


def prepare() -> dict[str, Any]:
    source = _load(DD103_CONTRACT)
    result = _load(DD103_RESULT)
    structural = _load(DD104)
    if result["pass"] or not structural["pass"]:
        raise RuntimeError("DD-105 requires failed DD-103 and passed DD-104")
    settings = ImplicitStepSettings(
        method="trf", ftol=1e-12, xtol=1e-12, gtol=1e-12,
        max_nfev=60, x_scale=1.0, jacobian_step=1e-5, jacobian_mode="colored",
    )
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {str(path).replace("\\", "/"): _sha(ROOT / path) for path in (DD103_CONTRACT, DD103_RESULT, DD104)},
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "previous_state": source["accepted_root_state"],
        "previous_inventory_lbmol": source["dynamic_inventory_lbmol"],
        "previous_algebraic_coordinates": source["starts"][0]["coordinates"][:23],
        "fixed_scales": source["fixed_steady_residual_scales"],
        "pressure_reference_psia": source["pressure_reference_psia"],
        "pressure_coordinate_scale_psia": source["pressure_coordinate_scale_psia"],
        "pressure_residual_scale_psia": source["pressure_residual_scale_psia"],
        "dry_tray_pressure_drop_coefficient": source["dry_tray_pressure_drop_coefficient"],
        "pressure_link_geometry": source["pressure_link_geometry"],
        "initial_coordinates": [0.0] * 15 + result["starts"][0]["final_coordinates"],
        "step_seconds": list(STEPS),
        "solver": asdict(settings),
        "endpoint_jacobian_steps": list(JACOBIAN_STEPS),
        "required_rank": 42,
        "residual_limit": 1e-8,
        "condition_limit": 1e8,
        "spectrum_change_limit": 0.25,
        "coupling_tolerance": 1e-7,
        "inventory_refinement_limit": 5e-3,
        "algebraic_refinement_limit": 5e-3,
        "pressure_refinement_limit_psia": 5e-3,
        "component_conservation_limit": 1e-12,
        "energy_conservation_limit": 1e-10,
        "provider_call_limit": 100000,
        "wall_clock_limit_sec": 180.0,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "either independent first step fails", "endpoint residual exceeds 1e-8",
            "rank, condition, spectrum, physicality, refinement, conservation, or provider gate fails",
            "provider calls exceed 100000 or wall time exceeds 180 seconds",
            "retry, substep, continuation, alternate solver, or trajectory is attempted",
        ],
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text("\n".join((
        "# DD-105 Frozen Pressure-Enabled First-Step Contract", "",
        f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
        "- Independent steps: `1.0 s`, `0.5 s`", "- System: exact-storage `42 x 42` backward Euler",
        "- Jacobian: frozen 20-color central difference", "- Live calls during preparation: `False`", "",
        "The endpoint energy balance uses the exact live `U_next-U_previous`; the fixed-pressure storage gradient is prohibited. Commit before one execution. No retry, trajectory, or controller is authorized.", "",
    )), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any]) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-105 contract hash mismatch")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-105 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-105 workbook changed")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-105 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    spec = dd102._spec(payload["source_mapping"], float(payload["operating_spec"]["feed_enthalpy_BTUph"]))
    reference = dd102._reference(payload["reference"])
    state = dd102._state(payload["previous_state"])
    contract = build_pressure_implicit_dae_contract(spec.component_names)
    if not audit_pressure_implicit_dae_contract(contract).pass_gate:
        raise RuntimeError("DD-105 structural prerequisite changed")
    provider = dd102._provider(Path(payload["workbook"]), payload["property_package"])
    audit = ProviderCallAudit()
    inventory = inventory_from_state(state)
    base_alg = np.asarray(payload["previous_algebraic_coordinates"], dtype=float)
    baseline = zero_rate_evaluation(
        contract.pressure_contract.base_contract, spec, reference, state, provider, audit,
        inventory_lbmol=inventory, algebraic_coordinates=base_alg,
        fixed_steady_scales=payload["fixed_scales"], state_id="dd105:previous", evaluation_kind="residual",
    )
    rate_scales = component_rate_scales(contract.pressure_contract.base_contract, baseline)
    previous_storage = governing_storage_vector(spec, baseline, inventory)
    component_mw = audit.component_molecular_weights(
        provider,
        caller="pressure_implicit_step_molecular_weight",
        state_id="dd105:preparation",
        evaluation_kind="preparation",
    )
    numerical = PressureNumericalSpec(
        reference_pressure_psia=np.asarray(payload["pressure_reference_psia"], dtype=float),
        pressure_coordinate_scale_psia=float(payload["pressure_coordinate_scale_psia"]),
        pressure_residual_scale_psia=float(payload["pressure_residual_scale_psia"]),
        dry_tray_pressure_drop_coefficient=float(payload["dry_tray_pressure_drop_coefficient"]),
        component_mw_lbm_per_lbmol=component_mw,
        link_geometry=tuple(PressureLinkGeometry(**item) for item in payload["pressure_link_geometry"]),
        enforce_pressure_order=False,
    )
    settings = ImplicitStepSettings(**payload["solver"])
    initial = np.asarray(payload["initial_coordinates"], dtype=float)
    started = time.perf_counter()
    records = []
    for dt in payload["step_seconds"]:
        def objective(point: np.ndarray, state_id: str, dt=float(dt)):
            return evaluate_pressure_backward_euler_residual(
                contract, spec, reference, state, provider, audit,
                previous_inventory_lbmol=inventory, previous_internal_energy_BTU=previous_storage,
                rate_scales_lbmolph=rate_scales, solve_coordinates=point, step_seconds=dt,
                fixed_steady_scales=payload["fixed_scales"], numerical=numerical,
                state_id=state_id, evaluation_kind="jacobian" if "jacobian" in state_id else "residual",
            )
        outcome = solve_pressure_backward_euler_step(contract, objective, initial, settings)
        jacobians = [audit_pressure_step_jacobian(
            contract, objective, outcome.final_coordinates, step=step,
            coupling_tolerance=float(payload["coupling_tolerance"]),
        ) for step in payload["endpoint_jacobian_steps"]]
        ev = outcome.evaluation
        records.append({
            "step_seconds": dt, "success": outcome.success, "nfev": outcome.nfev, "njev": outcome.njev,
            "residual": outcome.final_scaled_residual_inf_norm,
            "coordinates": _vector(outcome.final_coordinates),
            "inventory": _rows(ev.endpoint_inventory_lbmol),
            "component_rates": _rows(ev.component_rate_lbmolph),
            "energy_rates": _vector(ev.energy_storage_rate_BTUph),
            "pressure_psia": _vector(ev.pressure_evaluation.pressure_psia),
            "temperature_F": _vector(ev.pressure_evaluation.base_evaluation.physical_state.temperature_F),
            "jacobians": [{"step": j.step, "rank": j.rank, "condition": j.condition, "singular_values": _vector(j.singular_values), "zero_rows": list(j.zero_rows), "zero_columns": list(j.zero_columns), "color_count": j.color_count} for j in jacobians],
            "spectrum_change": _spectrum_change(jacobians[0].singular_values, jacobians[1].singular_values),
            "component_conservation": ev.pressure_evaluation.base_evaluation.steady_evaluation.component_telescoping_relative_error,
            "energy_conservation": ev.pressure_evaluation.base_evaluation.steady_evaluation.energy_telescoping_relative_error,
        })
    elapsed = time.perf_counter() - started
    coarse, fine = records
    inventory_refinement = float(np.max(np.abs(np.asarray(coarse["inventory"]) - np.asarray(fine["inventory"])) / np.maximum(np.abs(np.asarray(fine["inventory"])), 1e-12)))
    algebraic_refinement = float(np.max(np.abs(np.asarray(coarse["coordinates"])[15:] - np.asarray(fine["coordinates"])[15:])))
    pressure_refinement = float(np.max(np.abs(np.asarray(coarse["pressure_psia"]) - np.asarray(fine["pressure_psia"]))))
    provider = audit.report()
    gates = {
        "solve": all(item["success"] and item["residual"] < payload["residual_limit"] for item in records),
        "rank": all(j["rank"] == 42 for item in records for j in item["jacobians"]),
        "condition": all(j["condition"] < payload["condition_limit"] for item in records for j in item["jacobians"]),
        "spectrum": all(item["spectrum_change"] < payload["spectrum_change_limit"] for item in records),
        "structure": all(not j["zero_rows"] and not j["zero_columns"] for item in records for j in item["jacobians"]),
        "pressure": all(np.all(np.diff(item["pressure_psia"]) > 0) for item in records),
        "refinement": inventory_refinement < payload["inventory_refinement_limit"] and algebraic_refinement < payload["algebraic_refinement_limit"] and pressure_refinement < payload["pressure_refinement_limit_psia"],
        "conservation": all(abs(item["component_conservation"]) < payload["component_conservation_limit"] and abs(item["energy_conservation"]) < payload["energy_conservation_limit"] for item in records),
        "provider": provider["pass"], "calls": provider["total_calls"] < payload["provider_call_limit"], "wall": elapsed < payload["wall_clock_limit_sec"],
    }
    passed = all(gates.values())
    result = {"schema_id": RESULT_SCHEMA, "contract_commit": _git("rev-parse", "HEAD"), "classification": "dd105_passed" if passed else "dd105_failed", "decision": "authorize_pressure_implicit_step_contract" if passed else "stop_before_pressure_step", "wall_clock_sec": elapsed, "steps": records, "inventory_refinement": inventory_refinement, "algebraic_refinement": algebraic_refinement, "pressure_refinement_psia": pressure_refinement, "provider_provenance": provider, "gates": gates, "pass": passed, "campaign_executed_once": True, "dynamic_trajectory_attempted": False}
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text("\n".join(("# DD-105 Pressure-Enabled First-Step Result", "", f"- Classification: `{result['classification']}`", f"- Decision: `{result['decision']}`", f"- Wall clock: `{elapsed:.3f} s`", f"- Provider calls: `{provider['total_calls']}`", f"- Inventory refinement: `{inventory_refinement:.6e}`", f"- Algebraic refinement: `{algebraic_refinement:.6e}`", f"- Pressure refinement: `{pressure_refinement:.6e} psi`", "")), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    output = prepare() if args.prepare else execute()
    print(json.dumps(output, indent=2))
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
