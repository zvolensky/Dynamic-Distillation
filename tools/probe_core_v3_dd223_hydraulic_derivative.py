#!/usr/bin/env python
"""Prepare or execute DD-227's frozen direct hydraulic-derivative probe."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_full_c3c4_steady_root as dd223

from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    coordinate_layout,
    evaluate_residual,
    residual_rows,
)


SCHEMA = "dd227-core-v3-dd223-hydraulic-derivative-contract-v1"
RESULT_SCHEMA = "dd227-core-v3-dd223-hydraulic-derivative-result-v1"
SOURCE_REPLAY = Path("logs/dd225_core_v3_dd223_endpoint_replay_20260815.json")
SOURCE_LOCALIZATION = Path(
    "logs/dd226_core_v3_dd223_conditioning_localization_20260815.json"
)
SOURCE_ROOT_CONTRACT = dd223.CONTRACT
CONTRACT = Path("logs/dd227_core_v3_dd223_hydraulic_derivative_contract_20260815.json")
RESULT = Path("logs/dd227_core_v3_dd223_hydraulic_derivative_20260815")
STEPS = (2.0e-5, 1.0e-5, 5.0e-6, 2.5e-6)
DIRECT_COLORED_RELATIVE_LIMIT = 1.0e-8
REPEAT_ABSOLUTE_LIMIT = 1.0e-12
CALL_LIMIT = 20000
WALL_LIMIT_SEC = 120.0
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_registry_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "tools/audit_core_v3_provider_governed_numerical.py",
    "tools/audit_core_v3_full_c3c4_live_readiness.py",
    "tools/run_core_v3_full_c3c4_steady_root.py",
    "tools/probe_core_v3_dd223_hydraulic_derivative.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _target_from_localization(localization: Mapping[str, Any]) -> tuple[str, str]:
    pairs = {
        (
            endpoint["finite_difference_step_comparison"]["maximum_difference_residual"],
            endpoint["finite_difference_step_comparison"]["maximum_difference_coordinate"],
        )
        for endpoint in localization["endpoints"].values()
    }
    if len(pairs) != 1:
        raise RuntimeError("DD-227 requires one common DD-226 target")
    residual, coordinate = pairs.pop()
    if not residual.startswith("francis_hydraulics[") or not coordinate.startswith("T["):
        raise RuntimeError("DD-227 target is not a local temperature/hydraulics pair")
    residual_owner = re.search(r"\[([^\]]+)\]", residual)
    coordinate_owner = re.search(r"\[([^\]]+)\]", coordinate)
    if residual_owner is None or coordinate_owner is None or residual_owner.group(1) != coordinate_owner.group(1):
        raise RuntimeError("DD-227 residual and coordinate owners differ")
    return residual, coordinate


def prepare(contract_path: Path) -> dict[str, Any]:
    replay = _load(SOURCE_REPLAY)
    localization = _load(SOURCE_LOCALIZATION)
    root_contract = _load(SOURCE_ROOT_CONTRACT)
    if not replay.get("pass_gate") or not localization.get("pass_gate"):
        raise RuntimeError("DD-227 requires passing DD-225 and DD-226 evidence")
    target_residual, target_coordinate = _target_from_localization(localization)
    residual_index = replay["residual_names"].index(target_residual)
    coordinate_index = replay["coordinate_names"].index(target_coordinate)
    saved_colored = {
        name: {
            str(item["step"]): float(item["matrix"][residual_index][coordinate_index])
            for item in endpoint["jacobians"]
        }
        for name, endpoint in replay["endpoints"].items()
    }
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "source_replay": str(SOURCE_REPLAY).replace("\\", "/"),
        "source_replay_sha256": _sha(ROOT / SOURCE_REPLAY),
        "source_localization": str(SOURCE_LOCALIZATION).replace("\\", "/"),
        "source_localization_sha256": _sha(ROOT / SOURCE_LOCALIZATION),
        "source_root_contract": str(SOURCE_ROOT_CONTRACT).replace("\\", "/"),
        "source_root_contract_sha256": _sha(ROOT / SOURCE_ROOT_CONTRACT),
        "source_model_contract": root_contract["source_contract"],
        "source_model_contract_sha256": _sha(ROOT / root_contract["source_contract"]),
        "workbook": root_contract["workbook"],
        "workbook_sha256": root_contract["workbook_sha256"],
        "target_residual": target_residual,
        "target_residual_index": residual_index,
        "target_coordinate": target_coordinate,
        "target_coordinate_index": coordinate_index,
        "target_owner": re.search(r"\[([^\]]+)\]", target_coordinate).group(1),
        "endpoints": {
            name: endpoint["coordinates"] for name, endpoint in replay["endpoints"].items()
        },
        "fixed_residual_scales": root_contract["fixed_residual_scales"],
        "steps": list(STEPS),
        "saved_colored_target_derivatives": saved_colored,
        "limits": {
            "direct_colored_relative": DIRECT_COLORED_RELATIVE_LIMIT,
            "repeat_absolute": REPEAT_ABSOLUTE_LIMIT,
            "logical_provider_calls": CALL_LIMIT,
            "wall_clock_sec": WALL_LIMIT_SEC,
        },
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "provider_calls_during_preparation": 0,
        "nonlinear_solve_attempted": False,
        "state_changed": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "hard_stops": [
            "a source, workbook, implementation, endpoint, target, or ledger changes",
            "direct and saved colored target derivatives disagree at a common step",
            "an exact endpoint repeat changes beyond the frozen limit",
            "provider ownership fails or a call or wall limit is exceeded",
            "any solve, state adjustment, retry, timestep, or integration occurs",
        ],
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    if destination.exists():
        raise RuntimeError("DD-227 contract already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    destination.with_suffix(".md").write_text(
        "\n".join(
            (
                "# DD-227 Frozen Direct Hydraulic-Derivative Contract",
                "",
                f"- Target residual: `{target_residual}`",
                f"- Target coordinate: `{target_coordinate}`",
                f"- Steps: `{STEPS}`",
                "- Nonlinear solve or state change: `False`",
                "- Timestep or integration: `False`",
                "",
                "One direct-column execution is authorized after commit.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def _load_committed(path: Path) -> tuple[dict[str, Any], str]:
    destination = ROOT / path
    relative = destination.resolve().relative_to(ROOT.resolve()).as_posix()
    _git("ls-files", "--error-unmatch", relative)
    committed = _git("show", f"HEAD:{relative}")
    if committed.replace("\r\n", "\n").strip() != destination.read_text(
        encoding="utf-8"
    ).replace("\r\n", "\n").strip():
        raise RuntimeError("DD-227 contract differs from committed content")
    payload = json.loads(destination.read_text(encoding="utf-8"))
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if payload.get("schema_id") != SCHEMA or claimed != actual:
        raise RuntimeError("DD-227 contract schema or checksum failed")
    for implementation, digest in payload["implementation_sha256"].items():
        if _sha(ROOT / implementation) != digest:
            raise RuntimeError(f"DD-227 implementation changed: {implementation}")
    for key in ("source_replay", "source_localization", "source_root_contract", "source_model_contract"):
        if _sha(ROOT / payload[key]) != payload[f"{key}_sha256"]:
            raise RuntimeError(f"DD-227 {key} changed")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-227 workbook changed")
    return payload, _git("rev-parse", "HEAD")


def _snapshot(evaluation: Any, volume_index: int, residual_index: int) -> dict[str, Any]:
    return {
        "temperature_F": float(evaluation.state.temperature_F[volume_index]),
        "liquid_moles_lbmol": float(evaluation.state.liquid_moles_lbmol[volume_index]),
        "liquid_mole_fraction": evaluation.state.liquid_mole_fraction[volume_index].tolist(),
        "liquid_density_lbmol_ft3": float(
            evaluation.properties.liquid_density_lbmol_ft3[volume_index]
        ),
        "liquid_height_ft": float(evaluation.properties.liquid_height_ft[volume_index]),
        "over_weir_head_ft": float(
            evaluation.properties.over_weir_head_ft[volume_index]
        ),
        "francis_flow_lbmolph": float(
            evaluation.properties.francis_flow_lbmolph[volume_index]
        ),
        "raw_target_residual": float(evaluation.raw[residual_index]),
        "scaled_target_residual": float(evaluation.scaled[residual_index]),
    }


def execute(contract_path: Path, out_prefix: Path) -> dict[str, Any]:
    contract, commit = _load_committed(contract_path)
    model_contract = _load(Path(contract["source_model_contract"]))
    _workbook, provider, spec, reference = dd223._source_model(model_contract)
    layout = coordinate_layout(spec)
    rows = residual_rows(spec)
    coordinate_index = int(contract["target_coordinate_index"])
    residual_index = int(contract["target_residual_index"])
    if layout.names[coordinate_index] != contract["target_coordinate"]:
        raise RuntimeError("DD-227 target coordinate changed")
    if rows[residual_index].name != contract["target_residual"]:
        raise RuntimeError("DD-227 target residual changed")
    volume_index = spec.topology.volume_ids.index(contract["target_owner"])
    scales = np.asarray(contract["fixed_residual_scales"], dtype=float)
    started = time.perf_counter()
    endpoint_reports: dict[str, Any] = {}
    total_calls = 0
    pass_gate = True
    for name, values in contract["endpoints"].items():
        point = np.asarray(values, dtype=float)
        provider.set_exact_state_memoization(True, clear=True)
        audit = ProviderCallAudit()
        baseline = evaluate_residual(
            spec,
            reference,
            provider,
            audit,
            point,
            fixed_scales=scales,
            state_id=f"dd227_{name}_baseline",
            evaluation_kind="residual",
        )
        steps = []
        for step in contract["steps"]:
            delta = np.zeros_like(point)
            delta[coordinate_index] = float(step)
            plus = evaluate_residual(
                spec,
                reference,
                provider,
                audit,
                point + delta,
                fixed_scales=scales,
                state_id=f"dd227_{name}_{float(step):g}_plus",
                evaluation_kind="jacobian",
            )
            minus = evaluate_residual(
                spec,
                reference,
                provider,
                audit,
                point - delta,
                fixed_scales=scales,
                state_id=f"dd227_{name}_{float(step):g}_minus",
                evaluation_kind="jacobian",
            )
            column = (plus.scaled - minus.scaled) / (2.0 * float(step))
            target_derivative = float(column[residual_index])
            saved = contract["saved_colored_target_derivatives"][name].get(str(step))
            relative = None if saved is None else abs(target_derivative - saved) / max(abs(target_derivative), 1.0e-15)
            steps.append(
                {
                    "step": float(step),
                    "direct_scaled_target_derivative": target_derivative,
                    "saved_colored_scaled_target_derivative": saved,
                    "direct_colored_relative_difference": relative,
                    "plus": _snapshot(plus, volume_index, residual_index),
                    "minus": _snapshot(minus, volume_index, residual_index),
                }
            )
        provider.set_exact_state_memoization(False, clear=True)
        repeat_audit = ProviderCallAudit()
        repeated = evaluate_residual(
            spec,
            reference,
            provider,
            repeat_audit,
            point,
            fixed_scales=scales,
            state_id=f"dd227_{name}_repeat",
            evaluation_kind="residual",
        )
        repeat_difference = float(np.max(np.abs(repeated.scaled - baseline.scaled)))
        provenance = audit.report()
        repeat_provenance = repeat_audit.report()
        total_calls += int(provenance["total_calls"]) + int(repeat_provenance["total_calls"])
        common_differences = [
            item["direct_colored_relative_difference"]
            for item in steps
            if item["direct_colored_relative_difference"] is not None
        ]
        endpoint_pass = bool(
            max(common_differences) < contract["limits"]["direct_colored_relative"]
            and repeat_difference < contract["limits"]["repeat_absolute"]
            and provenance["pass"]
            and repeat_provenance["pass"]
        )
        pass_gate = pass_gate and endpoint_pass
        derivatives = np.asarray(
            [item["direct_scaled_target_derivative"] for item in steps], dtype=float
        )
        endpoint_reports[name] = {
            "baseline": _snapshot(baseline, volume_index, residual_index),
            "steps": steps,
            "successive_derivative_ratios": (derivatives[1:] / derivatives[:-1]).tolist(),
            "baseline_repeat_scaled_residual_max_abs_difference": repeat_difference,
            "provider_provenance": provenance,
            "repeat_provider_provenance": repeat_provenance,
            "pass": endpoint_pass,
        }
    elapsed = time.perf_counter() - started
    pass_gate = bool(
        pass_gate
        and total_calls < contract["limits"]["logical_provider_calls"]
        and elapsed < contract["limits"]["wall_clock_sec"]
    )
    direct_matches_colored = bool(
        all(
            item["direct_colored_relative_difference"] is None
            or item["direct_colored_relative_difference"] < contract["limits"]["direct_colored_relative"]
            for endpoint in endpoint_reports.values()
            for item in endpoint["steps"]
        )
    )
    derivative_step_stable = bool(
        all(
            max(abs(ratio - 1.0) for ratio in endpoint["successive_derivative_ratios"])
            < 0.1
            for endpoint in endpoint_reports.values()
        )
    )
    if direct_matches_colored and not derivative_step_stable:
        diagnosis = "underlying_property_or_hydraulic_derivative_is_discontinuous"
        decision = "inspect_the_saved_density_and_weir_path_before_scaling_or_root_solving"
    elif not direct_matches_colored:
        diagnosis = "colored_jacobian_grouping_is_incorrect"
        decision = "correct_the_structural_pattern_before_scaling_or_root_solving"
    else:
        diagnosis = "target_derivative_is_stable_and_requires_broader_review"
        decision = "review_other_saved_matrix_differences_before_scaling_or_root_solving"
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": "direct_hydraulic_derivative_probe_passed" if pass_gate else "direct_hydraulic_derivative_probe_failed",
        "diagnosis": diagnosis,
        "decision": decision,
        "contract_commit": commit,
        "contract_payload_sha256": contract["contract_payload_sha256"],
        "target_residual": contract["target_residual"],
        "target_coordinate": contract["target_coordinate"],
        "direct_matches_colored": direct_matches_colored,
        "derivative_step_stable": derivative_step_stable,
        "endpoints": endpoint_reports,
        "logical_provider_calls": total_calls,
        "wall_clock_sec": elapsed,
        "nonlinear_solve_attempted": False,
        "state_changed": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "pass_gate": pass_gate,
        "executed_once": True,
    }
    destination = ROOT / out_prefix
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    destination.with_suffix(".md").write_text(
        "\n".join(
            (
                "# DD-227 Direct Hydraulic-Derivative Probe",
                "",
                f"- Classification: `{report['classification']}`",
                f"- Diagnosis: `{diagnosis}`",
                f"- Direct matches colored: `{direct_matches_colored}`",
                f"- Derivative step stable: `{derivative_step_stable}`",
                f"- Logical provider calls: `{total_calls}`",
                f"- Wall clock: `{elapsed:.3f} s`",
                "- Solve, state change, or integration: `False`",
                "",
            )
        ),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--out-prefix", type=Path, default=RESULT)
    args = parser.parse_args()
    output = prepare(args.contract) if args.prepare_only else execute(args.contract, args.out_prefix)
    print(json.dumps(output, indent=2))
    return 0 if args.prepare_only or output["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
