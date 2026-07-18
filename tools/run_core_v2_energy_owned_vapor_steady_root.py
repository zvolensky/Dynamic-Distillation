#!/usr/bin/env python
"""Prepare or execute the frozen DD-085 three-start steady-root campaign."""

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
from dynamic_distillation.core_v2.energy_owned_vapor_numerical_gate_v1 import (
    coordinate_layout,
    evaluate_residual,
)
from dynamic_distillation.core_v2.energy_owned_vapor_registry_v1 import (
    HYDRAULIC_VOLUME_IDS,
    VOLUME_IDS,
)
from dynamic_distillation.core_v2.energy_owned_vapor_steady_solve_v1 import (
    CampaignDefinition,
    SteadySolveSettings,
    execute_start,
    pairwise_root_agreement,
    prepare_campaign,
)


SCHEMA_ID = "dd085-core-v2-energy-owned-vapor-steady-root-contract-v1"
RESULT_SCHEMA_ID = "dd085-core-v2-energy-owned-vapor-steady-root-result-v1"


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


def _settings_payload(settings: SteadySolveSettings) -> dict[str, Any]:
    values = asdict(settings)
    values["endpoint_jacobian_steps"] = list(settings.endpoint_jacobian_steps)
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
    starts = contract["campaign"]["starts"]
    lines = [
        "# DD-085 Frozen Numeric Campaign Contract",
        "",
        f"- Schema: `{contract['schema_id']}`",
        f"- Contract payload SHA-256: `{contract['contract_payload_sha256']}`",
        f"- Preparation base commit: `{contract['preparation_base_commit']}`",
        f"- Workbook: `{contract['workbook']}`",
        f"- Workbook SHA-256: `{contract['workbook_sha256']}`",
        f"- Property package: `{contract['property_package']}`",
        f"- Coordinates/residuals: `{len(contract['coordinate_names'])}` / "
        f"`{len(contract['residual_names'])}`",
        "- Nonlinear solve attempted during preparation: `False`",
        "",
        "## Frozen Solver",
        "",
        "```json",
        json.dumps(contract["settings"], indent=2),
        "```",
        "",
        "## Frozen Bounds",
        "",
        "The exact 37-element lower and upper transformed-coordinate vectors are "
        "stored in the adjacent JSON contract.",
        "",
        "## Frozen Starts",
        "",
    ]
    for name, point in starts.items():
        lines.append(
            f"- `{name}`: {len(point)} coordinates, "
            f"`||q||inf={np.max(np.abs(point)):.9e}`"
        )
    lines.extend(
        (
            "",
            "## Authorization",
            "",
            "After this artifact and implementation are committed, exactly one "
            "execution of the three-start campaign is authorized. The execution "
            "must consume this JSON contract without modifying it.",
            "",
        )
    )
    return "\n".join(lines)


def prepare(
    workbook: Path,
    property_package: str,
    contract_path: Path,
) -> dict[str, Any]:
    provider, spec, reference, source, operating = _build_problem(
        workbook,
        property_package,
    )
    settings = SteadySolveSettings()
    provider.reset_call_counters()
    definition = prepare_campaign(spec, reference, provider, settings)
    canonical = evaluate_residual(
        spec,
        reference,
        provider,
        definition.starts["canonical_role_mapped_seed"],
        fixed_scales=definition.fixed_residual_scales,
    )
    layout = coordinate_layout(spec)
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "workbook": str(workbook.resolve()),
        "workbook_sha256": _sha256_file(workbook),
        "property_package": property_package,
        "component_names": list(spec.component_names),
        "coordinate_names": list(layout.names),
        "residual_names": [row.name for row in canonical.rows],
        "source_mapping": source,
        "operating_parameters": operating,
        "settings": _settings_payload(settings),
        "campaign": _definition_payload(definition),
        "preparation_property_call_counters": provider.get_call_counters(),
        "nonlinear_solve_attempted": False,
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
    claimed_hash = str(contract.pop("contract_payload_sha256", ""))
    actual_hash = _payload_hash(contract)
    contract["contract_payload_sha256"] = claimed_hash
    if contract.get("schema_id") != SCHEMA_ID:
        raise RuntimeError("DD-085 contract schema does not match")
    if claimed_hash != actual_hash:
        raise RuntimeError("DD-085 contract payload checksum does not match")
    return contract


def _verify_contract_is_committed(path: Path) -> str:
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    _git("ls-files", "--error-unmatch", relative)
    committed = _git("show", f"HEAD:{relative}")
    current = path.read_text(encoding="utf-8")
    if committed.replace("\r\n", "\n") != current.replace("\r\n", "\n"):
        raise RuntimeError("DD-085 contract differs from committed HEAD")
    relevant = (
        "src/dynamic_distillation/core_v2/"
        "energy_owned_vapor_steady_solve_v1.py",
        "tools/run_core_v2_energy_owned_vapor_steady_root.py",
        "docs/dd_085_energy_owned_vapor_steady_root_contract_20260718.md",
        "tests/test_core_v2_energy_owned_vapor_steady_solve_v1.py",
        relative,
    )
    if _git("status", "--short", "--", *relevant):
        raise RuntimeError("DD-085 contract implementation has tracked changes")
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


def _verify_live_problem(
    contract: Mapping[str, Any],
    workbook: Path,
    property_package: str,
    spec: Any,
    reference: Any,
    provider: Any,
    definition: CampaignDefinition,
) -> None:
    if _sha256_file(workbook) != contract["workbook_sha256"]:
        raise RuntimeError("DD-085 workbook checksum changed")
    if property_package != contract["property_package"]:
        raise RuntimeError("DD-085 property package changed")
    if _settings_payload(SteadySolveSettings()) != contract["settings"]:
        raise RuntimeError("DD-085 solver settings changed")
    layout = coordinate_layout(spec)
    if list(layout.names) != contract["coordinate_names"]:
        raise RuntimeError("DD-085 coordinate identity changed")
    canonical = evaluate_residual(
        spec,
        reference,
        provider,
        definition.starts["canonical_role_mapped_seed"],
        fixed_scales=definition.fixed_residual_scales,
    )
    if [row.name for row in canonical.rows] != contract["residual_names"]:
        raise RuntimeError("DD-085 residual identity changed")
    if canonical.raw.size != 37 or len(layout.names) != 37:
        raise RuntimeError("DD-085 system is no longer 37 x 37")


def _json_start_result(result: Mapping[str, Any], counters: Mapping[str, Any]) -> dict:
    evaluation = result["endpoint_evaluation"]
    state = evaluation.state
    properties = evaluation.properties
    jacobians = result["endpoint_jacobians"]
    singular_values = result["endpoint_singular_values"]
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
            evaluation.component_telescoping_error_lbmolph
        ),
        "component_telescoping_relative_error": float(
            evaluation.component_telescoping_relative_error
        ),
        "energy_telescoping_error_BTUph": float(
            evaluation.energy_telescoping_error_BTUph
        ),
        "energy_telescoping_relative_error": float(
            evaluation.energy_telescoping_relative_error
        ),
        "jacobians": [
            {
                "step": float(audit.step),
                "rank": int(audit.rank),
                "condition": float(audit.condition),
                "singular_values": _float_list(values),
                "zero_rows": list(audit.zero_rows),
                "zero_columns": list(audit.zero_columns),
                "unexpected_couplings": list(audit.unexpected_couplings),
            }
            for audit, values in zip(jacobians, singular_values)
        ],
        "residual_pass": result["residual_pass"],
        "jacobian_pass": result["jacobian_pass"],
        "conservation_pass": result["conservation_pass"],
        "physical_pass": result["physical_pass"],
        "no_active_bound": result["no_active_bound"],
        "start_pass": result["start_pass"],
    }


def _dd082_diagnostic() -> dict[str, Any]:
    path = ROOT / "logs/dd082_core_v2_gate_c_steady_solve_20260718.json"
    if not path.exists():
        return {"available": False}
    report = json.loads(path.read_text(encoding="utf-8"))
    diagnostic: dict[str, Any] = {
        "available": True,
        "source": str(path.relative_to(ROOT)),
        "classification": report.get("classification"),
    }
    text = json.dumps(report)
    for key in (
        "reflux_drum_n-pentane",
        "reflux_drum_n_pentane",
        "top_vapor_flow_lbmolph",
    ):
        if key in text:
            diagnostic["note"] = (
                "The DD-082 artifact contains terminal diagnostics; DD-085 "
                "uses it only for post-solve comparison, never as a start."
            )
            break
    return diagnostic


def _result_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# DD-085 Energy-Owned Steady-Root Result",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Decision: `{report['decision']}`",
        f"- Contract commit: `{report['contract_commit']}`",
        f"- Contract SHA-256: `{report['contract_payload_sha256']}`",
        f"- Total wall time: `{report['wall_clock_sec']:.3f} s`",
        "",
        "## Starts",
        "",
        "| Start | Initial inf | Final inf | nfev / njev | Worst condition | "
        "Min bound distance | Pass |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for name, result in report["starts"].items():
        worst_condition = max(
            audit["condition"] for audit in result["jacobians"]
        )
        lines.append(
            f"| {name} | {result['initial_residual_inf_norm']:.6e} | "
            f"{result['final_residual_inf_norm']:.6e} | "
            f"{result['nfev']} / {result['njev']} | "
            f"{worst_condition:.6e} | "
            f"{result['minimum_transformed_bound_distance']:.6e} | "
            f"{result['start_pass']} |"
        )
    lines.extend(
        (
            "",
            "## Root Agreement",
            "",
        )
    )
    for pair, value in report["pairwise_physical_root_difference"].items():
        lines.append(f"- `{pair}`: `{value:.6e}`")
    lines.extend(
        (
            "",
            "## Decision",
            "",
            report["authorization"],
            "",
        )
    )
    return "\n".join(lines)


def execute(
    contract_path: Path,
    out_prefix: Path,
) -> dict[str, Any]:
    contract_commit = _verify_contract_is_committed(contract_path)
    contract = _load_contract(contract_path)
    workbook = Path(contract["workbook"])
    property_package = str(contract["property_package"])
    definition = _definition_from_contract(contract)
    settings = SteadySolveSettings()
    provider, spec, reference, _source, _operating = _build_problem(
        workbook,
        property_package,
    )
    _verify_live_problem(
        contract,
        workbook,
        property_package,
        spec,
        reference,
        provider,
        definition,
    )

    started = time.perf_counter()
    raw_results: dict[str, Any] = {}
    serialized_results: dict[str, Any] = {}
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
        serialized_results[name] = _json_start_result(
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
            "dd085_energy_owned_steady_root_passed"
            if passed
            else "dd085_energy_owned_steady_root_failed"
        ),
        "decision": (
            "authorize_dynamic_dae_structural_contract"
            if passed
            else "retire_five_volume_energy_owned_steady_architecture"
        ),
        "authorization": (
            "DD-085 passes. Drafting the structural dynamic DAE contract is "
            "authorized. Dynamic integration remains unauthorized."
            if passed
            else "DD-085 met its frozen hard stop. Retire this five-volume "
            "energy-owned steady architecture; do not tune or continue it."
        ),
        "contract_path": str(contract_path.resolve()),
        "contract_commit": contract_commit,
        "contract_payload_sha256": contract["contract_payload_sha256"],
        "workbook": str(workbook.resolve()),
        "workbook_sha256": contract["workbook_sha256"],
        "property_package": property_package,
        "settings": contract["settings"],
        "starts": serialized_results,
        "pairwise_physical_root_difference": comparisons,
        "root_agreement_tolerance": settings.root_agreement_tolerance,
        "common_physical_root_pass": common_root_pass,
        "dd082_diagnostic_comparison": _dd082_diagnostic(),
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
        default=Path("logs/dd085_energy_owned_steady_root_contract_20260718.json"),
    )
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path("logs/dd085_energy_owned_steady_root_20260718"),
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
            "nonlinear_solve_attempted": output["nonlinear_solve_attempted"],
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
            == "dd085_energy_owned_steady_root_passed"
            else 2
        )
    print(json.dumps(summary, indent=2))
    raise SystemExit(exit_code)
