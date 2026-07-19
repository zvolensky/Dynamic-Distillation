#!/usr/bin/env python
"""Prepare or execute the frozen DD-087 live 40 x 40 numerical audit."""

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
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from audit_core_v2_energy_owned_vapor_numerical import _build_problem
from dynamic_distillation.core_v2.condenser_saturated_liquid_numerical_gate_v1 import (
    BubbleSeedSettings,
    CondenserNumericalReference,
    audit_numerical_jacobian,
    coordinate_layout,
    decode_coordinates,
    evaluate_residual,
    phase_stability_diagnostics,
    residual_rows,
    solve_local_bubble_seed,
    structural_pattern,
)
from dynamic_distillation.core_v2.condenser_saturated_liquid_registry_v1 import (
    audit_condenser_saturated_liquid_registry,
    build_condenser_saturated_liquid_registry,
)
from dynamic_distillation.core_v2.energy_owned_vapor_numerical_gate_v1 import (
    EnergyOwnedReference,
    audit_points,
    residual_rows as base_residual_rows,
)
from dynamic_distillation.core_v2.energy_owned_vapor_registry_v1 import (
    HYDRAULIC_VOLUME_IDS,
    VOLUME_IDS,
)
from dynamic_distillation.core_v2.one_volume_property_gate_v1 import (
    normalize_composition,
)


SCHEMA_ID = "dd087-core-v2-condenser-saturated-liquid-numerical-contract-v1"
RESULT_SCHEMA_ID = "dd087-core-v2-condenser-saturated-liquid-numerical-result-v1"
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
JACOBIAN_COUPLING_TOLERANCE = 1.0e-7
JACOBIAN_CONDITION_HARD_STOP = 1.0e8
COMPONENT_CONSERVATION_TOLERANCE = 1.0e-12
ENERGY_CONSERVATION_TOLERANCE = 1.0e-10
BUBBLE_RESIDUAL_TOLERANCE = 1.0e-10
BUBBLE_SUM_TOLERANCE = 1.0e-4
BUBBLE_VAPOR_FRACTION_TOLERANCE = 1.0e-3
BUBBLE_COMPOSITION_TOLERANCE = 1.0e-5
BUBBLE_PERTURBATION = np.asarray([0.0015, -0.001], dtype=float)
CONDENSER_DUTY_PERTURBATION = 0.001


def _float_list(values: Any) -> list[float]:
    return [
        float(value)
        for value in np.asarray(values, dtype=float).reshape((-1,))
    ]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _reference_with_bubble_temperature(
    reference: EnergyOwnedReference,
    temperature_F: float,
) -> EnergyOwnedReference:
    temperatures = np.asarray(reference.temperature_F, dtype=float).copy()
    temperatures[0] = float(temperature_F)
    return EnergyOwnedReference(
        liquid_moles_lbmol=np.asarray(
            reference.liquid_moles_lbmol,
            dtype=float,
        ).copy(),
        liquid_mole_fraction=np.asarray(
            reference.liquid_mole_fraction,
            dtype=float,
        ).copy(),
        temperature_F=temperatures,
        vapor_mole_fraction=np.asarray(
            reference.vapor_mole_fraction,
            dtype=float,
        ).copy(),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            reference.hydraulic_liquid_flow_lbmolph,
            dtype=float,
        ).copy(),
        vapor_flow_lbmolph=np.asarray(
            reference.vapor_flow_lbmolph,
            dtype=float,
        ).copy(),
        distillate_lbmolph=float(reference.distillate_lbmolph),
        bottoms_lbmolph=float(reference.bottoms_lbmolph),
    )


def _bubble_initial_vapor_guess(provider, spec, reference) -> np.ndarray:
    flash = provider.flash_TP_full(
        float(reference.temperature_F[0]),
        float(spec.pressure_psia[0]),
        normalize_composition(reference.liquid_mole_fraction[0]).tolist(),
    )
    K = np.asarray(flash.K, dtype=float).reshape((-1,))
    if np.any(~np.isfinite(K)) or np.any(K <= 0.0):
        raise RuntimeError("DD-087 TP seed returned invalid K estimates")
    return normalize_composition(
        K * normalize_composition(reference.liquid_mole_fraction[0])
    )


def _condenser_reference(
    provider,
    spec,
    base_reference,
    bubble_temperature_F: float,
    bubble_y: np.ndarray,
) -> tuple[CondenserNumericalReference, dict[str, float]]:
    reference = _reference_with_bubble_temperature(
        base_reference,
        bubble_temperature_F,
    )
    drum_x = normalize_composition(reference.liquid_mole_fraction[0])
    h_liquid = float(
        provider.phase_enthalpy_BTU_lbmol(
            "liquid",
            float(reference.temperature_F[0]),
            float(spec.pressure_psia[0]),
            drum_x.tolist(),
        )
    )
    top_y = normalize_composition(reference.vapor_mole_fraction[0])
    h_vapor_top = float(
        provider.phase_enthalpy_BTU_lbmol(
            "vapor",
            float(reference.temperature_F[1]),
            float(spec.pressure_psia[1]),
            top_y.tolist(),
        )
    )
    top_vapor = float(reference.vapor_flow_lbmolph[-1])
    outlet_liquid = float(spec.reflux_lbmolph + reference.distillate_lbmolph)
    condenser_duty = outlet_liquid * h_liquid - top_vapor * h_vapor_top
    condenser_scale = max(
        abs(float(condenser_duty)),
        abs(float(spec.reboiler_duty_BTUph)),
        abs(float(spec.feed_enthalpy_BTUph)),
    )
    if (
        not np.isfinite(condenser_duty)
        or condenser_duty >= 0.0
        or not np.isfinite(condenser_scale)
        or condenser_scale <= 0.0
    ):
        raise RuntimeError("DD-087 canonical condenser duty is not negative")
    result = CondenserNumericalReference(
        base=reference,
        bubble_vapor_mole_fraction=normalize_composition(bubble_y),
        condenser_duty_reference_BTUph=float(condenser_duty),
        condenser_duty_scale_BTUph=float(condenser_scale),
    )
    return result, {
        "drum_liquid_enthalpy_BTU_lbmol": h_liquid,
        "top_vapor_enthalpy_BTU_lbmol": h_vapor_top,
        "top_vapor_flow_lbmolph": top_vapor,
        "outlet_liquid_flow_lbmolph": outlet_liquid,
        "condenser_duty_reference_BTUph": float(condenser_duty),
        "condenser_duty_scale_BTUph": float(condenser_scale),
    }


def _fixed_scales() -> np.ndarray:
    prior = json.loads(
        (ROOT / "logs/dd085_energy_owned_steady_root_contract_20260718.json")
        .read_text(encoding="utf-8")
    )
    base = np.asarray(prior["campaign"]["fixed_residual_scales"], dtype=float)
    if base.shape != (37,) or np.any(base <= 0.0):
        raise RuntimeError("DD-087 could not recover the frozen DD-084 scales")
    return np.concatenate((base, np.ones(3, dtype=float)))


def _phase_payload(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "K": _float_list(values["K"]),
        "bubble_sum_xK_minus_one": float(
            values["bubble_sum_xK_minus_one"]
        ),
        "vapor_fraction": float(values["vapor_fraction"]),
        "Kx_normalized": _float_list(values["Kx_normalized"]),
        "bubble_y_minus_Kx_max_abs": float(
            values["bubble_y_minus_Kx_max_abs"]
        ),
    }


def _phase_pass(values: Mapping[str, Any]) -> bool:
    return bool(
        abs(float(values["bubble_sum_xK_minus_one"]))
        <= BUBBLE_SUM_TOLERANCE
        and float(values["vapor_fraction"])
        <= BUBBLE_VAPOR_FRACTION_TOLERANCE
        and float(values["bubble_y_minus_Kx_max_abs"])
        <= BUBBLE_COMPOSITION_TOLERANCE
    )


def _contract_markdown(contract: Mapping[str, Any]) -> str:
    bubble = contract["canonical_bubble_seed"]
    duty = contract["condenser_energy_seed"]
    return "\n".join(
        (
            "# DD-087 Frozen Numerical-Audit Contract",
            "",
            f"- Schema: `{contract['schema_id']}`",
            f"- Payload SHA-256: `{contract['contract_payload_sha256']}`",
            f"- Preparation base commit: `{contract['preparation_base_commit']}`",
            f"- Workbook SHA-256: `{contract['workbook_sha256']}`",
            f"- Property package: `{contract['property_package']}`",
            "- Direct provider bubble API: `False`",
            "- Bubble seed method: local frozen `3 x 3` fugacity solve",
            "- Full residual evaluated during preparation: `False`",
            "- Full nonlinear root solve attempted: `False`",
            "- Dynamic integration attempted: `False`",
            "",
            "## Canonical Boundary",
            "",
            f"- Bubble temperature: `{bubble['temperature_F']:.12g} F`",
            f"- Bubble residual inf norm: `{bubble['residual_inf_norm']:.6e}`",
            f"- Incipient vapor: `{bubble['vapor_mole_fraction']}`",
            f"- Reference condenser duty: "
            f"`{duty['condenser_duty_reference_BTUph']:.12g} BTU/h`",
            f"- Signed affine duty scale: "
            f"`{duty['condenser_duty_scale_BTUph']:.12g} BTU/h`",
            "",
            "## Frozen Audit",
            "",
            "Exactly two committed 40-coordinate states are evaluated. Each uses "
            "uncolored central differences at `1e-5` and `5e-6`. The exact "
            "vectors, scales, row names, tolerances, and local bubble settings "
            "are stored in the adjacent JSON contract.",
            "",
            "Execution is authorized only after this contract and its "
            "implementation are committed. No root solve or integration is "
            "authorized.",
            "",
        )
    )


def prepare(
    workbook: Path,
    property_package: str,
    contract_path: Path,
) -> dict[str, Any]:
    provider, spec, base_reference, source, operating = _build_problem(
        workbook,
        property_package,
    )
    settings = BubbleSeedSettings()
    provider.reset_call_counters()
    vapor_guess = _bubble_initial_vapor_guess(
        provider,
        spec,
        base_reference,
    )
    bubble = solve_local_bubble_seed(
        provider,
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=base_reference.liquid_mole_fraction[0],
        temperature_guess_F=float(base_reference.temperature_F[0]),
        vapor_guess=vapor_guess,
        settings=settings,
    )
    if not bubble.success or bubble.residual_inf_norm > BUBBLE_RESIDUAL_TOLERANCE:
        raise RuntimeError("DD-087 local bubble seed failed its frozen gate")
    phase = phase_stability_diagnostics(
        provider,
        temperature_F=bubble.temperature_F,
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=base_reference.liquid_mole_fraction[0],
        bubble_y=bubble.vapor_mole_fraction,
    )
    if not _phase_pass(phase):
        raise RuntimeError("DD-087 canonical bubble seed failed phase diagnostics")
    reference, energy = _condenser_reference(
        provider,
        spec,
        base_reference,
        bubble.temperature_F,
        bubble.vapor_mole_fraction,
    )
    layout = coordinate_layout(spec)
    canonical = np.zeros(len(layout.names), dtype=float)
    perturbed = np.concatenate(
        (
            audit_points(spec)["deterministic_combined_perturbation"],
            BUBBLE_PERTURBATION,
            np.asarray([CONDENSER_DUTY_PERTURBATION]),
        )
    )
    if perturbed.shape != canonical.shape:
        raise RuntimeError("DD-087 perturbation is not a 40-coordinate vector")
    for point in (canonical, perturbed):
        base_state, condenser = decode_coordinates(spec, reference, point)
        if (
            condenser.condenser_duty_BTUph >= 0.0
            or np.any(base_state.liquid_moles_lbmol <= 0.0)
            or np.any(base_state.hydraulic_liquid_flow_lbmolph <= 0.0)
            or np.any(base_state.vapor_flow_lbmolph <= 0.0)
        ):
            raise RuntimeError("DD-087 frozen state is not physically bounded")
    rows = residual_rows(spec, base_residual_rows(spec))
    scales = _fixed_scales()
    registry = audit_condenser_saturated_liquid_registry(
        build_condenser_saturated_liquid_registry(spec.component_names)
    )
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "workbook": str(workbook.resolve()),
        "workbook_sha256": _sha256_file(workbook),
        "property_package": property_package,
        "component_names": list(spec.component_names),
        "coordinate_names": list(layout.names),
        "residual_names": [row.name for row in rows],
        "residual_blocks": {
            "full_phase_equilibrium": 12,
            "component_balance": 15,
            "energy_balance": 5,
            "francis_hydraulics": 3,
            "terminal_level_specification": 2,
            "condenser_saturated_liquid": 3,
        },
        "source_mapping": source,
        "operating_parameters": operating,
        "direct_provider_fixed_P_x_bubble_api": False,
        "bubble_seed_settings": asdict(settings),
        "canonical_bubble_seed": {
            "temperature_F": float(bubble.temperature_F),
            "vapor_mole_fraction": _float_list(bubble.vapor_mole_fraction),
            "scaled_coordinates": _float_list(bubble.scaled_coordinates),
            "residual": _float_list(bubble.residual),
            "residual_inf_norm": float(bubble.residual_inf_norm),
            "success": bool(bubble.success),
            "status": int(bubble.status),
            "message": bubble.message,
            "nfev": int(bubble.nfev),
            "njev": bubble.njev,
        },
        "canonical_phase_diagnostic": _phase_payload(phase),
        "phase_api_consistency_note": (
            "The exact forced-phase fugacity seed and the DWSIM TP-flash "
            "endpoint have a measured numerical consistency floor. The direct "
            "bubble equations retain a 1e-10 gate; the independent TP check "
            "uses frozen near-boundary tolerances and still rejects stable vapor."
        ),
        "condenser_energy_seed": energy,
        "fixed_residual_scales": _float_list(scales),
        "states": {
            "canonical_saturated_liquid_seed": _float_list(canonical),
            "deterministic_combined_perturbation": _float_list(perturbed),
        },
        "jacobian_steps": list(JACOBIAN_STEPS),
        "tolerances": {
            "jacobian_coupling": JACOBIAN_COUPLING_TOLERANCE,
            "jacobian_condition_hard_stop": JACOBIAN_CONDITION_HARD_STOP,
            "component_conservation_relative": COMPONENT_CONSERVATION_TOLERANCE,
            "energy_conservation_relative": ENERGY_CONSERVATION_TOLERANCE,
            "bubble_seed_residual_inf": BUBBLE_RESIDUAL_TOLERANCE,
            "bubble_sum_xK_minus_one_abs": BUBBLE_SUM_TOLERANCE,
            "bubble_vapor_fraction": BUBBLE_VAPOR_FRACTION_TOLERANCE,
            "bubble_composition_max_abs": BUBBLE_COMPOSITION_TOLERANCE,
        },
        "structural_registry_passed": bool(registry.pass_gate),
        "preparation_property_call_counters": provider.get_call_counters(),
        "full_residual_evaluation_attempted": False,
        "full_nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
    }
    payload["contract_payload_sha256"] = _payload_hash(payload)
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    contract_path.with_suffix(".md").write_text(
        _contract_markdown(payload),
        encoding="utf-8",
    )
    return payload


def _load_contract(path: Path) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    claimed = str(contract.pop("contract_payload_sha256", ""))
    actual = _payload_hash(contract)
    contract["contract_payload_sha256"] = claimed
    if contract.get("schema_id") != SCHEMA_ID:
        raise RuntimeError("DD-087 contract schema does not match")
    if claimed != actual:
        raise RuntimeError("DD-087 contract payload checksum does not match")
    return contract


def _verify_contract_is_committed(path: Path) -> str:
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    _git("ls-files", "--error-unmatch", relative)
    committed = _git("show", f"HEAD:{relative}")
    current = path.read_text(encoding="utf-8")
    if committed.replace("\r\n", "\n") != current.replace("\r\n", "\n"):
        raise RuntimeError("DD-087 contract differs from committed HEAD")
    relevant = (
        "src/dynamic_distillation/core_v2/"
        "condenser_saturated_liquid_numerical_gate_v1.py",
        "tools/audit_core_v2_condenser_saturated_liquid_numerical.py",
        "tests/test_core_v2_condenser_saturated_liquid_numerical_gate_v1.py",
        "docs/dd_087_condenser_saturated_liquid_numerical_audit_contract_20260718.md",
        relative,
        Path(relative).with_suffix(".md").as_posix(),
    )
    if _git("status", "--short", "--", *relevant):
        raise RuntimeError("DD-087 contract implementation has tracked changes")
    return _git("rev-parse", "HEAD")


def _reference_from_contract(provider, spec, base_reference, contract):
    seed = contract["canonical_bubble_seed"]
    reference, energy = _condenser_reference(
        provider,
        spec,
        base_reference,
        float(seed["temperature_F"]),
        np.asarray(seed["vapor_mole_fraction"], dtype=float),
    )
    declared = contract["condenser_energy_seed"]
    for key in (
        "condenser_duty_reference_BTUph",
        "condenser_duty_scale_BTUph",
    ):
        if not np.isclose(
            float(energy[key]),
            float(declared[key]),
            rtol=1.0e-12,
            atol=1.0e-6,
        ):
            raise RuntimeError(f"DD-087 live {key} differs from contract")
    return reference


def _dominant_rows(evaluation, count: int = 10) -> list[dict[str, Any]]:
    order = np.argsort(np.abs(evaluation.scaled))[::-1][:count]
    return [
        {
            "name": evaluation.rows[index].name,
            "block": evaluation.rows[index].block,
            "raw": float(evaluation.raw[index]),
            "scaled": float(evaluation.scaled[index]),
        }
        for index in order
    ]


def _jacobian_payload(audit) -> dict[str, Any]:
    return {
        "step": float(audit.step),
        "rank": int(audit.rank),
        "condition": float(audit.condition),
        "singular_values": _float_list(audit.singular_values),
        "zero_rows": list(audit.zero_rows),
        "zero_columns": list(audit.zero_columns),
        "unexpected_couplings": list(audit.unexpected_couplings),
        "bubble_rank": int(audit.bubble_rank),
        "bubble_singular_values": _float_list(audit.bubble_singular_values),
        "bubble_zero_rows": list(audit.bubble_zero_rows),
        "bubble_zero_columns": list(audit.bubble_zero_columns),
    }


def _state_report(spec, evaluation, jacobians) -> dict[str, Any]:
    state = evaluation.base.state
    properties = evaluation.base.properties
    heights = [
        float(properties.liquid_height_ft[VOLUME_IDS.index(volume)])
        for volume in HYDRAULIC_VOLUME_IDS
    ]
    spacings = [
        float(geometry.tray_spacing_ft) for geometry in spec.hydraulic_geometry
    ]
    jacobian_pass = all(
        audit.rank == 40
        and audit.condition < JACOBIAN_CONDITION_HARD_STOP
        and audit.bubble_rank == 3
        and not audit.zero_rows
        and not audit.zero_columns
        and not audit.unexpected_couplings
        and not audit.bubble_zero_rows
        and not audit.bubble_zero_columns
        for audit in jacobians
    )
    physical_pass = bool(
        np.all(np.isfinite(evaluation.raw))
        and np.all(np.isfinite(properties.liquid_enthalpy_BTU_lbmol))
        and np.all(np.isfinite(properties.vapor_enthalpy_BTU_lbmol[1:]))
        and np.all(np.isfinite(properties.liquid_density_lbmol_ft3))
        and np.all(properties.liquid_density_lbmol_ft3 > 0.0)
        and np.all(state.liquid_moles_lbmol > 0.0)
        and np.all(state.temperature_F > 0.0)
        and np.all(state.liquid_mole_fraction > 0.0)
        and np.all(state.vapor_mole_fraction > 0.0)
        and np.all(evaluation.condenser.bubble_vapor_mole_fraction > 0.0)
        and np.allclose(np.sum(state.liquid_mole_fraction, axis=1), 1.0)
        and np.allclose(np.sum(state.vapor_mole_fraction, axis=1), 1.0)
        and np.isclose(
            np.sum(evaluation.condenser.bubble_vapor_mole_fraction),
            1.0,
        )
        and np.all(state.hydraulic_liquid_flow_lbmolph > 0.0)
        and np.all(state.vapor_flow_lbmolph > 0.0)
        and state.distillate_lbmolph > 0.0
        and state.bottoms_lbmolph > 0.0
        and evaluation.condenser.condenser_duty_BTUph < 0.0
        and all(height < spacing for height, spacing in zip(heights, spacings))
    )
    conservation_pass = bool(
        evaluation.base.component_telescoping_relative_error
        < COMPONENT_CONSERVATION_TOLERANCE
        and evaluation.base.energy_telescoping_relative_error
        < ENERGY_CONSERVATION_TOLERANCE
    )
    passed = bool(
        jacobian_pass
        and physical_pass
        and conservation_pass
        and not evaluation.base.clipping_or_projection_used
        and not evaluation.base.property_fallback_used
    )
    return {
        "pass_gate": passed,
        "scaled_residual_inf_norm": float(np.max(np.abs(evaluation.scaled))),
        "raw_residual_inf_norm": float(np.max(np.abs(evaluation.raw))),
        "dominant_residuals": _dominant_rows(evaluation),
        "component_telescoping_error_lbmolph": _float_list(
            evaluation.base.component_telescoping_error_lbmolph
        ),
        "component_telescoping_relative_error": float(
            evaluation.base.component_telescoping_relative_error
        ),
        "energy_telescoping_error_BTUph": float(
            evaluation.base.energy_telescoping_error_BTUph
        ),
        "energy_telescoping_relative_error": float(
            evaluation.base.energy_telescoping_relative_error
        ),
        "condenser_duty_BTUph": float(
            evaluation.condenser.condenser_duty_BTUph
        ),
        "bubble_vapor_mole_fraction": _float_list(
            evaluation.condenser.bubble_vapor_mole_fraction
        ),
        "liquid_height_ft": heights,
        "tray_spacing_ft": spacings,
        "physical_pass": physical_pass,
        "conservation_pass": conservation_pass,
        "jacobian_pass": jacobian_pass,
        "clipping_or_projection_used": bool(
            evaluation.base.clipping_or_projection_used
        ),
        "property_fallback_used": bool(evaluation.base.property_fallback_used),
        "jacobians": [_jacobian_payload(audit) for audit in jacobians],
    }


def _result_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# DD-087 Saturated-Liquid Condenser Numerical Audit",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Decision: `{report['decision']}`",
        f"- Contract commit: `{report['contract_commit']}`",
        f"- Structural rank: `{report['structural_rank']}/40`",
        f"- Runtime: `{report['wall_clock_sec']:.3f} s`",
        "- Full nonlinear solve attempted: `False`",
        "- Dynamic integration attempted: `False`",
        "",
        "## Numerical States",
        "",
        "| State | Residual inf | Rank h / h/2 | Bubble rank | Worst condition | Pass |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for name, state in report["states"].items():
        jac = state["jacobians"]
        lines.append(
            f"| {name} | {state['scaled_residual_inf_norm']:.6e} | "
            f"{jac[0]['rank']} / {jac[1]['rank']} | "
            f"{jac[0]['bubble_rank']} / {jac[1]['bubble_rank']} | "
            f"{max(jac[0]['condition'], jac[1]['condition']):.6e} | "
            f"{state['pass_gate']} |"
        )
    phase = report["canonical_phase_diagnostic"]
    lines.extend(
        (
            "",
            "## Canonical Phase Gate",
            "",
            f"- `sum(x*K)-1`: `{phase['bubble_sum_xK_minus_one']:.6e}`",
            f"- vapor fraction: `{phase['vapor_fraction']:.6e}`",
            f"- `max|y_bubble-normalize(K*x)|`: "
            f"`{phase['bubble_y_minus_Kx_max_abs']:.6e}`",
            f"- Pass: `{report['canonical_phase_pass']}`",
            "",
            "## Decision",
            "",
            str(report["authorization"]),
            "",
        )
    )
    return "\n".join(lines)


def execute(contract_path: Path, out_prefix: Path) -> dict[str, Any]:
    contract = _load_contract(contract_path)
    contract_commit = _verify_contract_is_committed(contract_path)
    workbook = Path(contract["workbook"])
    if _sha256_file(workbook) != contract["workbook_sha256"]:
        raise RuntimeError("DD-087 workbook checksum differs from contract")
    provider, spec, base_reference, _source, _operating = _build_problem(
        workbook,
        str(contract["property_package"]),
    )
    layout = coordinate_layout(spec)
    if list(layout.names) != contract["coordinate_names"]:
        raise RuntimeError("DD-087 live coordinate names differ from contract")
    rows = residual_rows(spec, base_residual_rows(spec))
    if [row.name for row in rows] != contract["residual_names"]:
        raise RuntimeError("DD-087 live residual names differ from contract")
    reference = _reference_from_contract(
        provider,
        spec,
        base_reference,
        contract,
    )
    scales = np.asarray(contract["fixed_residual_scales"], dtype=float)
    pattern = structural_pattern(spec)
    structural_rank_value = int(structural_rank(csr_matrix(pattern)))
    registry = audit_condenser_saturated_liquid_registry(
        build_condenser_saturated_liquid_registry(spec.component_names)
    )
    q_column = layout.condenser_duty
    q_rows = np.flatnonzero(pattern[:, q_column]).tolist()
    dependency_pass = bool(
        q_rows == [15]
        and registry.pass_gate
        and not registry.fixed_condenser_duty_parameter_present
    )

    started = time.perf_counter()
    states: dict[str, Any] = {}
    for name, values in contract["states"].items():
        point = np.asarray(values, dtype=float)
        provider.reset_call_counters()
        evaluation = evaluate_residual(
            spec,
            reference,
            provider,
            point,
            fixed_scales=scales,
        )
        jacobians = [
            audit_numerical_jacobian(
                spec,
                reference,
                provider,
                point,
                fixed_scales=scales,
                step=float(step),
                coupling_tolerance=JACOBIAN_COUPLING_TOLERANCE,
            )
            for step in JACOBIAN_STEPS
        ]
        state_report = _state_report(spec, evaluation, jacobians)
        state_report["property_call_counters"] = provider.get_call_counters()
        states[name] = state_report

    seed = contract["canonical_bubble_seed"]
    phase = phase_stability_diagnostics(
        provider,
        temperature_F=float(seed["temperature_F"]),
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=base_reference.liquid_mole_fraction[0],
        bubble_y=seed["vapor_mole_fraction"],
    )
    phase_pass = _phase_pass(phase)
    passed = bool(
        structural_rank_value == 40
        and dependency_pass
        and phase_pass
        and all(state["pass_gate"] for state in states.values())
    )
    report: dict[str, Any] = {
        "schema_id": RESULT_SCHEMA_ID,
        "classification": (
            "dd087_condenser_saturated_liquid_numerical_passed"
            if passed
            else "dd087_condenser_saturated_liquid_numerical_failed"
        ),
        "decision": (
            "authorize_drafting_one_bounded_40x40_root_contract"
            if passed
            else "freeze_core_v2_at_dd085_and_stop_before_root_solve"
        ),
        "authorization": (
            "DD-087 passes. Drafting and precommitting one bounded 40 x 40 "
            "steady-root campaign is authorized. Execution, dynamic integration, "
            "and DAE work remain unauthorized."
            if passed
            else "DD-087 met a frozen hard stop. Do not tune the audit, restore "
            "fixed duty, remove phase stability, or attempt a nonlinear solve."
        ),
        "contract_path": str(contract_path.resolve()),
        "contract_commit": contract_commit,
        "contract_payload_sha256": contract["contract_payload_sha256"],
        "workbook": str(workbook.resolve()),
        "workbook_sha256": contract["workbook_sha256"],
        "property_package": contract["property_package"],
        "unknown_count": len(layout.names),
        "residual_count": len(rows),
        "structural_rank": structural_rank_value,
        "dependency_ownership": {
            "condenser_duty_residual_rows_zero_based": q_rows,
            "condenser_duty_only_in_drum_energy": q_rows == [15],
            "fixed_condenser_duty_parameter_present": bool(
                registry.fixed_condenser_duty_parameter_present
            ),
            "pass": dependency_pass,
        },
        "canonical_phase_diagnostic": _phase_payload(phase),
        "canonical_phase_pass": phase_pass,
        "states": states,
        "full_nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
        "wall_clock_sec": float(time.perf_counter() - started),
    }
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    out_prefix.with_suffix(".md").write_text(
        _result_markdown(report),
        encoding="utf-8",
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--workbook",
        type=Path,
        default=Path("sandbox/mini8/input/distillation_column_template_8stage.xlsx"),
    )
    parser.add_argument("--property-package", default="pr")
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path(
            "logs/dd087_condenser_saturated_liquid_numerical_contract_20260718.json"
        ),
    )
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path(
            "logs/dd087_condenser_saturated_liquid_numerical_20260718"
        ),
    )
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare_only:
        output = prepare(
            args.workbook.resolve(),
            args.property_package,
            args.contract,
        )
        summary = {
            "schema_id": output["schema_id"],
            "contract_payload_sha256": output["contract_payload_sha256"],
            "bubble_temperature_F": output["canonical_bubble_seed"][
                "temperature_F"
            ],
            "condenser_duty_reference_BTUph": output[
                "condenser_energy_seed"
            ]["condenser_duty_reference_BTUph"],
            "full_residual_evaluation_attempted": False,
        }
        exit_code = 0
    else:
        output = execute(args.contract, args.out_prefix)
        summary = {
            "classification": output["classification"],
            "decision": output["decision"],
            "wall_clock_sec": output["wall_clock_sec"],
        }
        exit_code = (
            0
            if output["classification"]
            == "dd087_condenser_saturated_liquid_numerical_passed"
            else 2
        )
    print(json.dumps(summary, indent=2))
    raise SystemExit(exit_code)
