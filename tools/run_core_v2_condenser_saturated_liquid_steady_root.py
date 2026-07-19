#!/usr/bin/env python
"""Prepare or execute the frozen DD-088 three-start steady-root campaign."""

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
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from audit_core_v2_energy_owned_vapor_numerical import _build_problem
from dynamic_distillation.core_v2.condenser_saturated_liquid_numerical_gate_v1 import (
    CondenserNumericalReference,
    coordinate_layout,
    residual_rows,
)
from dynamic_distillation.core_v2.condenser_saturated_liquid_steady_solve_v1 import (
    CondenserSteadySolveSettings,
    execute_start,
    pairwise_root_agreement,
    prepare_campaign,
)
from dynamic_distillation.core_v2.energy_owned_vapor_numerical_gate_v1 import (
    EnergyOwnedReference,
    residual_rows as base_residual_rows,
)
from dynamic_distillation.core_v2.energy_owned_vapor_registry_v1 import (
    HYDRAULIC_VOLUME_IDS,
    VOLUME_IDS,
)
from dynamic_distillation.core_v2.energy_owned_vapor_steady_solve_v1 import (
    CampaignDefinition,
)


SCHEMA_ID = "dd088-core-v2-condenser-saturated-liquid-steady-root-contract-v1"
RESULT_SCHEMA_ID = "dd088-core-v2-condenser-saturated-liquid-steady-root-result-v1"
DD087_CONTRACT = ROOT / (
    "logs/dd087_condenser_saturated_liquid_numerical_contract_20260718.json"
)


def _float_list(values: Any) -> list[float]:
    return [
        float(value)
        for value in np.asarray(values, dtype=float).reshape((-1,))
    ]


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


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


def _load_dd087_contract() -> dict[str, Any]:
    contract = json.loads(DD087_CONTRACT.read_text(encoding="utf-8"))
    if (
        contract.get("schema_id")
        != "dd087-core-v2-condenser-saturated-liquid-numerical-contract-v1"
    ):
        raise RuntimeError("DD-088 requires the committed DD-087 contract")
    return contract


def _reference_from_dd087(
    base_reference: EnergyOwnedReference,
    contract: Mapping[str, Any],
) -> CondenserNumericalReference:
    temperature = np.asarray(base_reference.temperature_F, dtype=float).copy()
    temperature[0] = float(
        contract["canonical_bubble_seed"]["temperature_F"]
    )
    base = EnergyOwnedReference(
        liquid_moles_lbmol=np.asarray(
            base_reference.liquid_moles_lbmol,
            dtype=float,
        ).copy(),
        liquid_mole_fraction=np.asarray(
            base_reference.liquid_mole_fraction,
            dtype=float,
        ).copy(),
        temperature_F=temperature,
        vapor_mole_fraction=np.asarray(
            base_reference.vapor_mole_fraction,
            dtype=float,
        ).copy(),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            base_reference.hydraulic_liquid_flow_lbmolph,
            dtype=float,
        ).copy(),
        vapor_flow_lbmolph=np.asarray(
            base_reference.vapor_flow_lbmolph,
            dtype=float,
        ).copy(),
        distillate_lbmolph=float(base_reference.distillate_lbmolph),
        bottoms_lbmolph=float(base_reference.bottoms_lbmolph),
    )
    energy = contract["condenser_energy_seed"]
    return CondenserNumericalReference(
        base=base,
        bubble_vapor_mole_fraction=np.asarray(
            contract["canonical_bubble_seed"]["vapor_mole_fraction"],
            dtype=float,
        ),
        condenser_duty_reference_BTUph=float(
            energy["condenser_duty_reference_BTUph"]
        ),
        condenser_duty_scale_BTUph=float(
            energy["condenser_duty_scale_BTUph"]
        ),
    )


def _settings_payload(settings: CondenserSteadySolveSettings) -> dict[str, Any]:
    values = asdict(settings)
    values["endpoint_jacobian_steps"] = list(
        settings.endpoint_jacobian_steps
    )
    return values


def _definition_payload(definition: CampaignDefinition) -> dict[str, Any]:
    return {
        "lower_bounds": _float_list(definition.lower_bounds),
        "upper_bounds": _float_list(definition.upper_bounds),
        "starts": {
            name: _float_list(point)
            for name, point in definition.starts.items()
        },
        "fixed_residual_scales": _float_list(
            definition.fixed_residual_scales
        ),
        "physical_comparison_scales": _float_list(
            definition.physical_comparison_scales
        ),
    }


def _contract_markdown(contract: Mapping[str, Any]) -> str:
    smooth = contract["independent_start_metadata"]
    lines = [
        "# DD-088 Frozen Steady-Root Contract",
        "",
        f"- Schema: `{contract['schema_id']}`",
        f"- Payload SHA-256: `{contract['contract_payload_sha256']}`",
        f"- Preparation base commit: `{contract['preparation_base_commit']}`",
        f"- DD-087 contract SHA-256: `{contract['dd087_contract_sha256']}`",
        f"- Workbook SHA-256: `{contract['workbook_sha256']}`",
        f"- Coordinates/residuals: `{len(contract['coordinate_names'])}` / "
        f"`{len(contract['residual_names'])}`",
        "- Full-system solve attempted during preparation: `False`",
        "- Dynamic integration attempted: `False`",
        "",
        "## Frozen Starts",
        "",
    ]
    for name, point in contract["campaign"]["starts"].items():
        lines.append(
            f"- `{name}`: `{len(point)}` coordinates, "
            f"`||q||inf={np.max(np.abs(point)):.6e}`"
        )
    lines.extend(
        (
            "",
            "## Independent Start",
            "",
            f"- Drum composition: `{smooth['drum_liquid_mole_fraction']}`",
            f"- Bubble temperature: `{smooth['bubble_temperature_F']:.12g} F`",
            f"- Bubble residual: `{smooth['bubble_residual_inf_norm']:.6e}`",
            f"- Condenser duty: "
            f"`{smooth['condenser_duty_BTUph']:.12g} BTU/h`",
            "",
            "## Authorization",
            "",
            "After this contract and implementation are committed and pushed, "
            "exactly one three-start execution is authorized. No alternate "
            "solver, continuation, restart, retuning, or dynamic integration "
            "is permitted.",
            "",
        )
    )
    return "\n".join(lines)


def prepare(
    workbook: Path,
    property_package: str,
    contract_path: Path,
) -> dict[str, Any]:
    dd087 = _load_dd087_contract()
    provider, spec, base_reference, source, operating = _build_problem(
        workbook,
        property_package,
    )
    reference = _reference_from_dd087(base_reference, dd087)
    settings = CondenserSteadySolveSettings()
    provider.reset_call_counters()
    definition, independent = prepare_campaign(
        spec,
        reference,
        provider,
        settings,
        canonical=dd087["states"]["canonical_saturated_liquid_seed"],
        perturbation=dd087["states"][
            "deterministic_combined_perturbation"
        ],
        fixed_residual_scales=dd087["fixed_residual_scales"],
    )
    phase = independent["phase_diagnostic"]
    if (
        abs(float(phase["bubble_sum_xK_minus_one"]))
        > settings.bubble_sum_tolerance
        or float(phase["vapor_fraction"])
        > settings.bubble_vapor_fraction_tolerance
        or float(phase["bubble_y_minus_Kx_max_abs"])
        > settings.bubble_composition_tolerance
    ):
        raise RuntimeError("DD-088 independent start failed the phase gate")
    layout = coordinate_layout(spec)
    rows = residual_rows(spec, base_residual_rows(spec))
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "workbook": str(workbook.resolve()),
        "workbook_sha256": _sha256_file(workbook),
        "property_package": property_package,
        "dd087_contract_path": str(DD087_CONTRACT.relative_to(ROOT)),
        "dd087_contract_sha256": _sha256_file(DD087_CONTRACT),
        "component_names": list(spec.component_names),
        "coordinate_names": list(layout.names),
        "residual_names": [row.name for row in rows],
        "source_mapping": source,
        "operating_parameters": operating,
        "settings": _settings_payload(settings),
        "campaign": _definition_payload(definition),
        "independent_start_metadata": _jsonable(independent),
        "preparation_property_call_counters": provider.get_call_counters(),
        "full_system_residual_evaluation_attempted": False,
        "full_system_solve_attempted": False,
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
        raise RuntimeError("DD-088 contract schema does not match")
    if claimed != actual:
        raise RuntimeError("DD-088 contract payload checksum does not match")
    return contract


def _verify_contract_is_committed(path: Path) -> str:
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    _git("ls-files", "--error-unmatch", relative)
    committed = _git("show", f"HEAD:{relative}")
    current = path.read_text(encoding="utf-8")
    if committed.replace("\r\n", "\n") != current.replace("\r\n", "\n"):
        raise RuntimeError("DD-088 contract differs from committed HEAD")
    relevant = (
        "src/dynamic_distillation/core_v2/"
        "condenser_saturated_liquid_steady_solve_v1.py",
        "tools/run_core_v2_condenser_saturated_liquid_steady_root.py",
        "tests/test_core_v2_condenser_saturated_liquid_steady_solve_v1.py",
        "docs/dd_088_condenser_saturated_liquid_steady_root_contract_20260719.md",
        relative,
        Path(relative).with_suffix(".md").as_posix(),
    )
    if _git("status", "--short", "--", *relevant):
        raise RuntimeError("DD-088 contract implementation has tracked changes")
    return _git("rev-parse", "HEAD")


def _definition_from_contract(contract: Mapping[str, Any]) -> CampaignDefinition:
    campaign = contract["campaign"]
    return CampaignDefinition(
        lower_bounds=np.asarray(campaign["lower_bounds"], dtype=float),
        upper_bounds=np.asarray(campaign["upper_bounds"], dtype=float),
        starts={
            name: np.asarray(point, dtype=float)
            for name, point in campaign["starts"].items()
        },
        fixed_residual_scales=np.asarray(
            campaign["fixed_residual_scales"],
            dtype=float,
        ),
        physical_comparison_scales=np.asarray(
            campaign["physical_comparison_scales"],
            dtype=float,
        ),
    )


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


def _json_start_result(
    result: Mapping[str, Any],
    counters: Mapping[str, Any],
) -> dict[str, Any]:
    evaluation = result["endpoint_evaluation"]
    state = evaluation.base.state
    properties = evaluation.base.properties
    condenser = evaluation.condenser
    return {
        "name": result["name"],
        "success_flag": result["success_flag"],
        "status": result["status"],
        "termination_reason": result["termination_reason"],
        "nfev": result["nfev"],
        "njev": result["njev"],
        "wall_clock_sec": result["wall_clock_sec"],
        "property_call_counters": counters,
        "initial_coordinates": _float_list(result["initial_coordinates"]),
        "final_coordinates": _float_list(result["final_coordinates"]),
        "initial_residual_inf_norm": result["initial_residual_inf_norm"],
        "final_residual_inf_norm": result["final_residual_inf_norm"],
        "initial_block_norms": result["initial_block_norms"],
        "final_block_norms": result["final_block_norms"],
        "movement_by_coordinate_family": result[
            "movement_by_coordinate_family"
        ],
        "minimum_transformed_bound_distance": result[
            "minimum_transformed_bound_distance"
        ],
        "active_bound_indices": [
            int(value) for value in result["active_bound_indices"]
        ],
        "liquid_moles_lbmol": _float_list(state.liquid_moles_lbmol),
        "liquid_mole_fraction": [
            _float_list(row) for row in state.liquid_mole_fraction
        ],
        "temperature_F": _float_list(state.temperature_F),
        "vapor_mole_fraction": [
            _float_list(row) for row in state.vapor_mole_fraction
        ],
        "bubble_vapor_mole_fraction": _float_list(
            condenser.bubble_vapor_mole_fraction
        ),
        "condenser_duty_BTUph": float(condenser.condenser_duty_BTUph),
        "liquid_flow_lbmolph": _float_list(
            state.hydraulic_liquid_flow_lbmolph
        ),
        "francis_flow_lbmolph": _float_list(
            [
                properties.francis_flow_lbmolph[VOLUME_IDS.index(volume)]
                for volume in HYDRAULIC_VOLUME_IDS
            ]
        ),
        "vapor_flow_lbmolph": _float_list(state.vapor_flow_lbmolph),
        "distillate_lbmolph": float(state.distillate_lbmolph),
        "bottoms_lbmolph": float(state.bottoms_lbmolph),
        "liquid_heights_ft": _float_list(result["liquid_heights_ft"]),
        "tray_spacings_ft": _float_list(result["tray_spacings_ft"]),
        "residence_times_sec": _float_list(result["residence_times_sec"]),
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
        "phase_diagnostic": _phase_payload(result["phase_diagnostic"]),
        "jacobians": [
            {
                "step": float(audit.step),
                "rank": int(audit.rank),
                "condition": float(audit.condition),
                "singular_values": _float_list(audit.singular_values),
                "zero_rows": list(audit.zero_rows),
                "zero_columns": list(audit.zero_columns),
                "unexpected_couplings": list(audit.unexpected_couplings),
                "bubble_rank": int(audit.bubble_rank),
                "bubble_singular_values": _float_list(
                    audit.bubble_singular_values
                ),
                "bubble_zero_rows": list(audit.bubble_zero_rows),
                "bubble_zero_columns": list(audit.bubble_zero_columns),
            }
            for audit in result["endpoint_jacobians"]
        ],
        "residual_pass": result["residual_pass"],
        "jacobian_pass": result["jacobian_pass"],
        "conservation_pass": result["conservation_pass"],
        "phase_pass": result["phase_pass"],
        "physical_pass": result["physical_pass"],
        "no_active_bound": result["no_active_bound"],
        "start_pass": result["start_pass"],
    }


def _dd085_comparison() -> dict[str, Any]:
    path = ROOT / "logs/dd085_energy_owned_steady_root_20260718.json"
    if not path.exists():
        return {"available": False}
    report = json.loads(path.read_text(encoding="utf-8"))
    start = next(iter(report["starts"].values()))
    return {
        "available": True,
        "source": str(path.relative_to(ROOT)),
        "drum_temperature_F": float(start["temperature_F"][0]),
        "rectifying_temperature_F": float(start["temperature_F"][1]),
        "condenser_duty_BTUph": -49640000.0,
        "top_vapor_flow_lbmolph": float(start["vapor_flow_lbmolph"][-1]),
        "distillate_lbmolph": float(start["distillate_lbmolph"]),
        "bottoms_lbmolph": float(start["bottoms_lbmolph"]),
        "phase_classification": "stable_vapor",
    }


def _result_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# DD-088 Saturated-Liquid Steady-Root Result",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Decision: `{report['decision']}`",
        f"- Contract commit: `{report['contract_commit']}`",
        f"- Total wall time: `{report['wall_clock_sec']:.3f} s`",
        "",
        "## Starts",
        "",
        "| Start | Initial inf | Final inf | nfev / njev | Worst condition | "
        "Min bound distance | Qc MMBTU/h | Pass |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, result in report["starts"].items():
        lines.append(
            f"| {name} | {result['initial_residual_inf_norm']:.6e} | "
            f"{result['final_residual_inf_norm']:.6e} | "
            f"{result['nfev']} / {result['njev']} | "
            f"{max(item['condition'] for item in result['jacobians']):.6e} | "
            f"{result['minimum_transformed_bound_distance']:.6e} | "
            f"{result['condenser_duty_BTUph']/1e6:.6f} | "
            f"{result['start_pass']} |"
        )
    lines.extend(("", "## Root Agreement", ""))
    for pair, value in report["pairwise_physical_root_difference"].items():
        lines.append(f"- `{pair}`: `{value:.6e}`")
    lines.extend(("", "## Decision", "", report["authorization"], ""))
    return "\n".join(lines)


def execute(contract_path: Path, out_prefix: Path) -> dict[str, Any]:
    contract_commit = _verify_contract_is_committed(contract_path)
    contract = _load_contract(contract_path)
    workbook = Path(contract["workbook"])
    if _sha256_file(workbook) != contract["workbook_sha256"]:
        raise RuntimeError("DD-088 workbook checksum changed")
    if _sha256_file(DD087_CONTRACT) != contract["dd087_contract_sha256"]:
        raise RuntimeError("DD-087 contract changed after DD-088 preparation")
    dd087 = _load_dd087_contract()
    provider, spec, base_reference, _source, _operating = _build_problem(
        workbook,
        str(contract["property_package"]),
    )
    reference = _reference_from_dd087(base_reference, dd087)
    settings = CondenserSteadySolveSettings()
    if _settings_payload(settings) != contract["settings"]:
        raise RuntimeError("DD-088 settings differ from contract")
    layout = coordinate_layout(spec)
    if list(layout.names) != contract["coordinate_names"]:
        raise RuntimeError("DD-088 coordinate identity changed")
    rows = residual_rows(spec, base_residual_rows(spec))
    if [row.name for row in rows] != contract["residual_names"]:
        raise RuntimeError("DD-088 residual identity changed")
    definition = _definition_from_contract(contract)

    started = time.perf_counter()
    raw_results: dict[str, Any] = {}
    serialized: dict[str, Any] = {}
    for name, point in definition.starts.items():
        provider.reset_call_counters()
        raw = execute_start(
            spec,
            reference,
            provider,
            name=name,
            initial=point,
            lower_bounds=definition.lower_bounds,
            upper_bounds=definition.upper_bounds,
            fixed_scales=definition.fixed_residual_scales,
            settings=settings,
        )
        raw_results[name] = raw
        serialized[name] = _json_start_result(
            raw,
            provider.get_call_counters(),
        )
    comparisons = pairwise_root_agreement(
        spec,
        reference,
        {
            name: result["final_coordinates"]
            for name, result in raw_results.items()
        },
        definition.physical_comparison_scales,
    )
    common_root_pass = bool(
        comparisons
        and max(comparisons.values()) < settings.root_agreement_tolerance
    )
    passed = bool(
        all(result["start_pass"] for result in raw_results.values())
        and common_root_pass
    )
    report: dict[str, Any] = {
        "schema_id": RESULT_SCHEMA_ID,
        "classification": (
            "dd088_saturated_liquid_steady_root_passed"
            if passed
            else "dd088_saturated_liquid_steady_root_failed"
        ),
        "decision": (
            "authorize_structural_dynamic_dae_contract"
            if passed
            else "retire_solved_duty_saturated_liquid_five_volume_architecture"
        ),
        "authorization": (
            "DD-088 passes. Drafting a structural dynamic-DAE mass-matrix, "
            "index, and consistent-initialization contract is authorized. "
            "Dynamic integration remains unauthorized."
            if passed
            else "DD-088 met its frozen hard stop. Retire this solved-duty "
            "saturated-liquid five-volume steady architecture; do not tune, "
            "widen bounds, sweep duty, add a partial condenser, or integrate."
        ),
        "contract_path": str(contract_path.resolve()),
        "contract_commit": contract_commit,
        "contract_payload_sha256": contract["contract_payload_sha256"],
        "workbook": str(workbook.resolve()),
        "workbook_sha256": contract["workbook_sha256"],
        "property_package": contract["property_package"],
        "settings": contract["settings"],
        "starts": serialized,
        "pairwise_physical_root_difference": comparisons,
        "root_agreement_tolerance": settings.root_agreement_tolerance,
        "common_physical_root_pass": common_root_pass,
        "dd085_diagnostic_comparison": _dd085_comparison(),
        "nonlinear_campaign_executions": 1,
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
            "logs/dd088_condenser_saturated_liquid_steady_root_contract_20260719.json"
        ),
    )
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path(
            "logs/dd088_condenser_saturated_liquid_steady_root_20260719"
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
            "independent_bubble_temperature_F": output[
                "independent_start_metadata"
            ]["bubble_temperature_F"],
            "full_system_solve_attempted": False,
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
            == "dd088_saturated_liquid_steady_root_passed"
            else 2
        )
    print(json.dumps(summary, indent=2))
    raise SystemExit(exit_code)
