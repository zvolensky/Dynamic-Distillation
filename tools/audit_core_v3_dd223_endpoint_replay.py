#!/usr/bin/env python
"""Prepare or execute DD-225's frozen read-only DD-223 endpoint replay."""

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

import audit_core_v3_provider_governed_numerical as dd092
import run_core_v3_full_c3c4_steady_root as dd223

from dynamic_distillation.core_v3.colored_jacobian_v1 import greedy_column_groups
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    audit_colored_numerical_jacobian,
    coordinate_layout,
    evaluate_residual,
    residual_rows,
    structural_pattern,
)


SCHEMA = "dd225-core-v3-dd223-endpoint-replay-contract-v1"
RESULT_SCHEMA = "dd225-core-v3-dd223-endpoint-replay-result-v1"
SOURCE_CONTRACT = dd223.CONTRACT
SOURCE_RESULT = dd223.RESULT.with_suffix(".json")
SOURCE_EVIDENCE = Path("logs/dd224_core_v3_dd223_diagnostic_evidence_20260815.json")
CONTRACT = Path("logs/dd225_core_v3_dd223_endpoint_replay_contract_20260815.json")
RESULT = Path("logs/dd225_core_v3_dd223_endpoint_replay_20260815")
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
RESIDUAL_NORM_REPRODUCTION_LIMIT = 1.0e-10
SPECTRUM_REPRODUCTION_RELATIVE_LIMIT = 1.0e-4
CALL_LIMIT = 50000
WALL_LIMIT_SEC = 180.0
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_registry_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "tools/audit_core_v3_provider_governed_numerical.py",
    "tools/audit_core_v3_full_c3c4_live_readiness.py",
    "tools/run_core_v3_full_c3c4_steady_root.py",
    "tools/audit_core_v3_dd223_endpoint_replay.py",
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


def prepare(contract_path: Path) -> dict[str, Any]:
    source_contract = _load(SOURCE_CONTRACT)
    source_result = _load(SOURCE_RESULT)
    source_evidence = _load(SOURCE_EVIDENCE)
    if source_result.get("classification") != "full_c3c4_stationary_root_failed":
        raise RuntimeError("DD-225 requires the failed DD-223 result")
    if source_evidence.get("decision") != "authorize_one_frozen_read_only_endpoint_replay_contract":
        raise RuntimeError("DD-225 was not authorized by DD-224")
    source_model_contract = _load(Path(source_contract["source_contract"]))
    preparation_spec = dd223.dd222._spec(
        source_model_contract["source_mapping"],
        float(source_model_contract["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    preparation_rows = residual_rows(preparation_spec)
    endpoints = {
        name: list(start["final_coordinates"])
        for name, start in source_result["starts"].items()
    }
    saved = {
        name: {
            "scaled_residual_inf_norm": float(start["scaled_residual_inf_norm"]),
            "jacobians": [
                {
                    "step": float(item["step"]),
                    "rank": int(item["rank"]),
                    "condition": float(item["condition"]),
                    "singular_values": list(item["singular_values"]),
                }
                for item in start["jacobians"]
            ],
        }
        for name, start in source_result["starts"].items()
    }
    dimension = len(next(iter(endpoints.values())))
    if any(len(point) != dimension for point in endpoints.values()):
        raise RuntimeError("DD-223 endpoint dimensions differ")
    if tuple(source_contract["settings"]["endpoint_jacobian_steps"]) != JACOBIAN_STEPS:
        raise RuntimeError("DD-223 Jacobian steps differ from DD-225")
    color_groups = source_contract["jacobian"]["color_groups"]
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "source_contract": str(SOURCE_CONTRACT).replace("\\", "/"),
        "source_contract_sha256": _sha(ROOT / SOURCE_CONTRACT),
        "source_result": str(SOURCE_RESULT).replace("\\", "/"),
        "source_result_sha256": _sha(ROOT / SOURCE_RESULT),
        "source_evidence": str(SOURCE_EVIDENCE).replace("\\", "/"),
        "source_evidence_sha256": _sha(ROOT / SOURCE_EVIDENCE),
        "source_model_contract": source_contract["source_contract"],
        "source_model_contract_sha256": _sha(ROOT / source_contract["source_contract"]),
        "workbook": source_contract["workbook"],
        "workbook_sha256": source_contract["workbook_sha256"],
        "property_package": source_contract["property_package"],
        "dimension": dimension,
        "coordinate_names": source_model_contract["coordinate_names"],
        "residual_names": source_model_contract["residual_names"],
        "residual_blocks": [row.block for row in preparation_rows],
        "fixed_residual_scales": source_contract["fixed_residual_scales"],
        "endpoints": endpoints,
        "saved_dd223_endpoint_summaries": saved,
        "jacobian": {
            "mode": "colored_central_difference",
            "steps": list(JACOBIAN_STEPS),
            "coupling_tolerance": float(
                source_contract["settings"]["jacobian_coupling_tolerance"]
            ),
            "color_count": len(color_groups),
            "color_groups": color_groups,
        },
        "reproduction_limits": {
            "scaled_residual_inf_norm_absolute": RESIDUAL_NORM_REPRODUCTION_LIMIT,
            "singular_spectrum_relative": SPECTRUM_REPRODUCTION_RELATIVE_LIMIT,
        },
        "limits": {
            "logical_provider_calls": CALL_LIMIT,
            "wall_clock_sec": WALL_LIMIT_SEC,
        },
        "required_saved_evidence": [
            "complete raw and scaled residual vectors with row names and blocks",
            "complete scaled Jacobian matrices at both frozen steps",
            "complete singular vectors and singular values",
            "provider provenance and exact-state memoization statistics",
        ],
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "full_residual_evaluated_during_preparation": False,
        "provider_calls_during_preparation": 0,
        "nonlinear_solve_attempted": False,
        "state_changed": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "hard_stops": [
            "a source hash, implementation hash, endpoint, ledger, or coloring changes",
            "a complete residual vector or Jacobian matrix is not recorded",
            "an endpoint residual norm does not reproduce within the frozen limit",
            "a singular spectrum does not reproduce within the frozen limit",
            "provider ownership fails or a call or wall limit is exceeded",
            "any solve, state adjustment, timestep, retry, or dynamic integration occurs",
        ],
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    if destination.exists():
        raise RuntimeError("DD-225 contract already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    destination.with_suffix(".md").write_text(
        "\n".join(
            (
                "# DD-225 Frozen DD-223 Endpoint Replay Contract",
                "",
                f"- Endpoints: `{', '.join(endpoints)}`",
                f"- Dimension: `{dimension}`",
                f"- Jacobian steps: `{JACOBIAN_STEPS}`",
                f"- Jacobian colors: `{len(color_groups)}`",
                "- Nonlinear solve: `False`",
                "- State change, timestep, or integration: `False`",
                "",
                "One read-only execution is authorized after commit.",
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
        raise RuntimeError("DD-225 contract differs from committed content")
    payload = json.loads(destination.read_text(encoding="utf-8"))
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if payload.get("schema_id") != SCHEMA or claimed != actual:
        raise RuntimeError("DD-225 contract schema or checksum failed")
    for implementation, digest in payload["implementation_sha256"].items():
        if _sha(ROOT / implementation) != digest:
            raise RuntimeError(f"DD-225 implementation changed: {implementation}")
    for key in ("source_contract", "source_result", "source_evidence", "source_model_contract"):
        if _sha(ROOT / payload[key]) != payload[f"{key}_sha256"]:
            raise RuntimeError(f"DD-225 {key} changed")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-225 workbook changed")
    return payload, _git("rev-parse", "HEAD")


def _spectrum_difference(current: np.ndarray, saved: np.ndarray) -> float:
    return float(
        np.max(np.abs(current - saved) / np.maximum(np.abs(saved), 1.0e-15))
    )


def _jacobian_payload(item: Any) -> dict[str, Any]:
    left, singular, right_t = np.linalg.svd(item.matrix, full_matrices=False)
    return {
        "step": float(item.step),
        "matrix": np.asarray(item.matrix, dtype=float).tolist(),
        "rank": int(item.rank),
        "condition": float(item.condition),
        "singular_values": np.asarray(singular, dtype=float).tolist(),
        "left_singular_vectors": np.asarray(left, dtype=float).tolist(),
        "right_singular_vectors_transposed": np.asarray(right_t, dtype=float).tolist(),
        "zero_rows": list(item.zero_rows),
        "zero_columns": list(item.zero_columns),
        "unexpected_couplings": list(item.unexpected_couplings),
        "bubble_matrix": np.asarray(item.bubble_matrix, dtype=float).tolist(),
        "bubble_rank": int(item.bubble_rank),
        "bubble_singular_values": np.asarray(item.bubble_singular_values, dtype=float).tolist(),
    }


def execute(contract_path: Path, out_prefix: Path) -> dict[str, Any]:
    contract, commit = _load_committed(contract_path)
    source_contract = _load(Path(contract["source_contract"]))
    model_contract = _load(Path(source_contract["source_contract"]))
    _workbook, provider, spec, reference = dd223._source_model(model_contract)
    scales = np.asarray(contract["fixed_residual_scales"], dtype=float)
    layout = coordinate_layout(spec)
    rows = residual_rows(spec)
    groups = greedy_column_groups(structural_pattern(spec))
    if list(layout.names) != contract["coordinate_names"]:
        raise RuntimeError("DD-225 coordinate ledger changed")
    if [row.name for row in rows] != contract["residual_names"]:
        raise RuntimeError("DD-225 residual ledger changed")
    if [row.block for row in rows] != contract["residual_blocks"]:
        raise RuntimeError("DD-225 residual block ledger changed")
    if [list(group) for group in groups] != contract["jacobian"]["color_groups"]:
        raise RuntimeError("DD-225 coloring changed")

    started = time.perf_counter()
    endpoint_reports: dict[str, Any] = {}
    total_calls = 0
    all_pass = True
    for name, values in contract["endpoints"].items():
        point = np.asarray(values, dtype=float)
        provider.set_exact_state_memoization(True, clear=True)
        audit = ProviderCallAudit()
        evaluation = evaluate_residual(
            spec,
            reference,
            provider,
            audit,
            point,
            fixed_scales=scales,
            state_id=f"dd225_{name}_endpoint",
            evaluation_kind="residual",
        )
        jacobians = []
        replay_groups = []
        for step in contract["jacobian"]["steps"]:
            item, item_groups = audit_colored_numerical_jacobian(
                spec,
                reference,
                provider,
                audit,
                point,
                fixed_scales=scales,
                state_id=f"dd225_{name}_{float(step):g}",
                step=float(step),
                coupling_tolerance=float(contract["jacobian"]["coupling_tolerance"]),
            )
            jacobians.append(item)
            replay_groups.append(item_groups)
        memo = provider.get_exact_state_memoization_stats()
        provider.set_exact_state_memoization(False, clear=True)
        provenance = audit.report()
        total_calls += int(provenance["total_calls"])

        saved = contract["saved_dd223_endpoint_summaries"][name]
        residual_norm = float(np.max(np.abs(evaluation.scaled)))
        residual_difference = abs(residual_norm - float(saved["scaled_residual_inf_norm"]))
        spectrum_differences = [
            _spectrum_difference(
                item.singular_values,
                np.asarray(saved_item["singular_values"], dtype=float),
            )
            for item, saved_item in zip(jacobians, saved["jacobians"], strict=True)
        ]
        color_groups_match = all(
            [list(group) for group in item_groups]
            == contract["jacobian"]["color_groups"]
            for item_groups in replay_groups
        )
        endpoint_pass = bool(
            residual_difference
            <= contract["reproduction_limits"]["scaled_residual_inf_norm_absolute"]
            and max(spectrum_differences)
            <= contract["reproduction_limits"]["singular_spectrum_relative"]
            and all(item.rank == contract["dimension"] for item in jacobians)
            and color_groups_match
            and provenance["pass"]
            and not evaluation.clipping_or_projection_used
            and not evaluation.property_fallback_used
        )
        all_pass = all_pass and endpoint_pass
        endpoint_reports[name] = {
            "coordinates": point.tolist(),
            "coordinate_sha256": _hash({"coordinates": point.tolist()}),
            "raw_residual": evaluation.raw.tolist(),
            "scaled_residual": evaluation.scaled.tolist(),
            "residual_scales": evaluation.scales.tolist(),
            "scaled_residual_inf_norm": residual_norm,
            "saved_scaled_residual_inf_norm": float(saved["scaled_residual_inf_norm"]),
            "scaled_residual_inf_norm_absolute_difference": residual_difference,
            "component_telescoping_relative_error": float(
                evaluation.component_telescoping_relative_error
            ),
            "energy_telescoping_relative_error": float(
                evaluation.energy_telescoping_relative_error
            ),
            "jacobians": [_jacobian_payload(item) for item in jacobians],
            "singular_spectrum_relative_differences_from_dd223": spectrum_differences,
            "provider_provenance": provenance,
            "exact_state_memoization": memo,
            "pass": endpoint_pass,
        }

    elapsed = time.perf_counter() - started
    complete = bool(
        all(len(item["raw_residual"]) == contract["dimension"] for item in endpoint_reports.values())
        and all(
            np.asarray(jacobian["matrix"]).shape == (contract["dimension"], contract["dimension"])
            for item in endpoint_reports.values()
            for jacobian in item["jacobians"]
        )
    )
    pass_gate = bool(
        all_pass
        and complete
        and total_calls < contract["limits"]["logical_provider_calls"]
        and elapsed < contract["limits"]["wall_clock_sec"]
    )
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "dd223_endpoint_evidence_capture_passed"
            if pass_gate else "dd223_endpoint_evidence_capture_failed"
        ),
        "decision": (
            "authorize_zero_call_dd223_conditioning_localization"
            if pass_gate else "stop_before_conditioning_localization"
        ),
        "contract_commit": commit,
        "contract_payload_sha256": contract["contract_payload_sha256"],
        "coordinate_names": list(layout.names),
        "residual_names": [row.name for row in rows],
        "residual_blocks": [row.block for row in rows],
        "endpoints": endpoint_reports,
        "complete_evidence_saved": complete,
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
    destination.with_suffix(".json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    destination.with_suffix(".md").write_text(
        "\n".join(
            (
                "# DD-225 DD-223 Endpoint Replay",
                "",
                f"- Classification: `{report['classification']}`",
                f"- Decision: `{report['decision']}`",
                f"- Complete evidence saved: `{complete}`",
                f"- Logical provider calls: `{total_calls}`",
                f"- Wall clock: `{elapsed:.3f} s`",
                "- Nonlinear solve, state change, or integration: `False`",
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
