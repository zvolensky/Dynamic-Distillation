#!/usr/bin/env python
"""Prepare or execute DD-229's aligned-PR density residual/Jacobian parity audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

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


SCHEMA = "dd229-core-v3-aligned-pr-density-parity-contract-v1"
RESULT_SCHEMA = "dd229-core-v3-aligned-pr-density-parity-result-v1"
SOURCE_FEASIBILITY = Path("logs/dd228_core_v3_aligned_pr_liquid_density_20260815.json")
SOURCE_REPLAY = Path("logs/dd225_core_v3_dd223_endpoint_replay_20260815.json")
SOURCE_ROOT_CONTRACT = dd223.CONTRACT
CONTRACT = Path("logs/dd229_core_v3_aligned_pr_density_parity_contract_20260815.json")
RESULT = Path("logs/dd229_core_v3_aligned_pr_density_parity_20260815")
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
CONDITION_LIMIT = 1.0e8
SPECTRUM_CHANGE_LIMIT = 0.05
MATRIX_CHANGE_LIMIT = 0.05
CALL_LIMIT = 20000
WALL_LIMIT_SEC = 180.0
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_registry_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "tools/audit_core_v3_provider_governed_numerical.py",
    "tools/audit_core_v3_full_c3c4_live_readiness.py",
    "tools/run_core_v3_full_c3c4_steady_root.py",
    "tools/audit_core_v3_aligned_pr_density_parity.py",
)


class DensityRoutedProvider:
    """Use DWSIM for bulk thermo except aligned PR for liquid density."""

    provider_identity = "dwsim-aligned-pr-density"

    def __init__(self, dwsim_provider: Any, density_provider: Any) -> None:
        self.dwsim_provider = dwsim_provider
        self.density_provider = density_provider

    def phase_fugacity_coefficients(self, *args: Any, **kwargs: Any) -> Any:
        return self.dwsim_provider.phase_fugacity_coefficients(*args, **kwargs)

    def phase_enthalpy_BTU_lbmol(self, *args: Any, **kwargs: Any) -> Any:
        return self.dwsim_provider.phase_enthalpy_BTU_lbmol(*args, **kwargs)

    def liquid_density_lbmol_ft3(
        self,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
    ) -> float:
        return float(
            self.density_provider.liquid_density_lbmol_ft3(
                temperature_F, pressure_psia, composition
            )
        )

    def set_exact_state_memoization(self, enabled: bool, *, clear: bool = True) -> None:
        self.dwsim_provider.set_exact_state_memoization(enabled, clear=clear)

    def get_exact_state_memoization_stats(self) -> dict[str, Any]:
        return self.dwsim_provider.get_exact_state_memoization_stats()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.dwsim_provider, name)


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
    feasibility = _load(SOURCE_FEASIBILITY)
    replay = _load(SOURCE_REPLAY)
    root_contract = _load(SOURCE_ROOT_CONTRACT)
    model_contract = _load(Path(root_contract["source_contract"]))
    if not feasibility.get("pass_gate") or not replay.get("pass_gate"):
        raise RuntimeError("DD-229 requires passing DD-225 and DD-228 evidence")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "source_feasibility": str(SOURCE_FEASIBILITY).replace("\\", "/"),
        "source_feasibility_sha256": _sha(ROOT / SOURCE_FEASIBILITY),
        "source_replay": str(SOURCE_REPLAY).replace("\\", "/"),
        "source_replay_sha256": _sha(ROOT / SOURCE_REPLAY),
        "source_root_contract": str(SOURCE_ROOT_CONTRACT).replace("\\", "/"),
        "source_root_contract_sha256": _sha(ROOT / SOURCE_ROOT_CONTRACT),
        "source_model_contract": root_contract["source_contract"],
        "source_model_contract_sha256": _sha(ROOT / root_contract["source_contract"]),
        "workbook": root_contract["workbook"],
        "workbook_sha256": root_contract["workbook_sha256"],
        "dimension": len(replay["coordinate_names"]),
        "coordinate_names": replay["coordinate_names"],
        "residual_names": replay["residual_names"],
        "residual_blocks": replay["residual_blocks"],
        "fixed_residual_scales": root_contract["fixed_residual_scales"],
        "endpoints": {
            name: endpoint["coordinates"] for name, endpoint in replay["endpoints"].items()
        },
        "original_endpoint_residual_norms": {
            name: endpoint["scaled_residual_inf_norm"]
            for name, endpoint in replay["endpoints"].items()
        },
        "provider_routing": {
            "direct_imposed_phase_fugacity": "dwsim",
            "declared_phase_enthalpy": "dwsim",
            "declared_liquid_density": "aligned_pr_smallest_positive_root",
        },
        "jacobian": {
            "mode": "colored_central_difference",
            "steps": list(JACOBIAN_STEPS),
            "coupling_tolerance": float(
                root_contract["settings"]["jacobian_coupling_tolerance"]
            ),
            "color_groups": root_contract["jacobian"]["color_groups"],
        },
        "limits": {
            "condition": CONDITION_LIMIT,
            "spectrum_relative_change": SPECTRUM_CHANGE_LIMIT,
            "matrix_relative_frobenius_change": MATRIX_CHANGE_LIMIT,
            "logical_provider_calls": CALL_LIMIT,
            "wall_clock_sec": WALL_LIMIT_SEC,
        },
        "evidence_format": "compressed_npz_matrices_plus_json_summary",
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "provider_calls_during_preparation": 0,
        "nonlinear_solve_attempted": False,
        "state_changed": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "hard_stops": [
            "a source, workbook, implementation, endpoint, ledger, or coloring changes",
            "a matrix loses rank, exceeds the condition limit, or changes excessively with step",
            "physicality, conservation, provider ownership, call, or wall gate fails",
            "any solve, state change, retry, timestep, or integration occurs",
        ],
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    if destination.exists():
        raise RuntimeError("DD-229 contract already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    destination.with_suffix(".md").write_text(
        "\n".join(
            (
                "# DD-229 Frozen Aligned-PR Density Parity Contract",
                "",
                "- DWSIM owns fugacity and enthalpy.",
                "- Parameter-aligned PR owns liquid density.",
                f"- Endpoints: `{', '.join(payload['endpoints'])}`",
                f"- Jacobian steps: `{JACOBIAN_STEPS}`",
                "- Nonlinear solve, state change, or integration: `False`",
                "",
                "One residual/Jacobian execution is authorized after commit.",
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
    if committed.replace("\r\n", "\n").strip() != destination.read_text(encoding="utf-8").replace("\r\n", "\n").strip():
        raise RuntimeError("DD-229 contract differs from committed content")
    payload = json.loads(destination.read_text(encoding="utf-8"))
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if payload.get("schema_id") != SCHEMA or claimed != actual:
        raise RuntimeError("DD-229 contract schema or checksum failed")
    for implementation, digest in payload["implementation_sha256"].items():
        if _sha(ROOT / implementation) != digest:
            raise RuntimeError(f"DD-229 implementation changed: {implementation}")
    for key in ("source_feasibility", "source_replay", "source_root_contract", "source_model_contract"):
        if _sha(ROOT / payload[key]) != payload[f"{key}_sha256"]:
            raise RuntimeError(f"DD-229 {key} changed")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-229 workbook changed")
    return payload, _git("rev-parse", "HEAD")


def execute(contract_path: Path, out_prefix: Path) -> dict[str, Any]:
    contract, commit = _load_committed(contract_path)
    model_contract = _load(Path(contract["source_model_contract"]))
    _workbook, dwsim, spec, reference = dd223._source_model(model_contract)
    aligned = dd092._independent_provider(model_contract)
    provider = DensityRoutedProvider(dwsim, aligned)
    layout = coordinate_layout(spec)
    rows = residual_rows(spec)
    groups = greedy_column_groups(structural_pattern(spec))
    if list(layout.names) != contract["coordinate_names"]:
        raise RuntimeError("DD-229 coordinate ledger changed")
    if [row.name for row in rows] != contract["residual_names"]:
        raise RuntimeError("DD-229 residual ledger changed")
    if [list(group) for group in groups] != contract["jacobian"]["color_groups"]:
        raise RuntimeError("DD-229 coloring changed")
    scales = np.asarray(contract["fixed_residual_scales"], dtype=float)
    started = time.perf_counter()
    endpoint_reports: dict[str, Any] = {}
    arrays: dict[str, np.ndarray] = {}
    total_calls = 0
    pass_gate = True
    for name, values in contract["endpoints"].items():
        point = np.asarray(values, dtype=float)
        provider.set_exact_state_memoization(True, clear=True)
        audit = ProviderCallAudit(
            provider_identity="dwsim",
            interface_provider_identities={"declared_liquid_density": "aligned_pr"},
        )
        evaluation = evaluate_residual(
            spec,
            reference,
            provider,
            audit,
            point,
            fixed_scales=scales,
            state_id=f"dd229_{name}_endpoint",
            evaluation_kind="residual",
        )
        jacobians = []
        for step in contract["jacobian"]["steps"]:
            item, item_groups = audit_colored_numerical_jacobian(
                spec,
                reference,
                provider,
                audit,
                point,
                fixed_scales=scales,
                state_id=f"dd229_{name}_{float(step):g}",
                step=float(step),
                coupling_tolerance=float(contract["jacobian"]["coupling_tolerance"]),
            )
            if [list(group) for group in item_groups] != contract["jacobian"]["color_groups"]:
                raise RuntimeError("DD-229 runtime coloring changed")
            jacobians.append(item)
        memo = provider.get_exact_state_memoization_stats()
        provider.set_exact_state_memoization(False, clear=True)
        provenance = audit.report()
        total_calls += int(provenance["total_calls"])
        spectrum_change = float(
            np.max(
                np.abs(jacobians[0].singular_values - jacobians[1].singular_values)
                / np.maximum(np.abs(jacobians[0].singular_values), 1.0e-15)
            )
        )
        matrix_change = float(
            np.linalg.norm(jacobians[1].matrix - jacobians[0].matrix)
            / max(np.linalg.norm(jacobians[0].matrix), 1.0e-30)
        )
        physical = bool(
            np.all(evaluation.state.liquid_moles_lbmol > 0.0)
            and np.all(evaluation.state.hydraulic_liquid_flow_lbmolph > 0.0)
            and np.all(evaluation.state.vapor_flow_lbmolph > 0.0)
            and np.all(evaluation.properties.liquid_density_lbmol_ft3 > 0.0)
            and np.all(np.diff(evaluation.state.temperature_F) > 0.0)
            and evaluation.state.condenser_duty_BTUph < 0.0
        )
        endpoint_pass = bool(
            all(item.rank == contract["dimension"] for item in jacobians)
            and all(item.condition < contract["limits"]["condition"] for item in jacobians)
            and spectrum_change < contract["limits"]["spectrum_relative_change"]
            and matrix_change < contract["limits"]["matrix_relative_frobenius_change"]
            and evaluation.component_telescoping_relative_error < 1.0e-12
            and evaluation.energy_telescoping_relative_error < 1.0e-10
            and physical
            and provenance["pass"]
            and not evaluation.clipping_or_projection_used
            and not evaluation.property_fallback_used
        )
        pass_gate = pass_gate and endpoint_pass
        key = name.replace("-", "_")
        arrays[f"{key}_scaled_residual"] = evaluation.scaled
        for index, item in enumerate(jacobians):
            arrays[f"{key}_jacobian_{index}"] = item.matrix
        endpoint_reports[name] = {
            "original_scaled_residual_inf_norm": float(
                contract["original_endpoint_residual_norms"][name]
            ),
            "routed_scaled_residual_inf_norm": float(np.max(np.abs(evaluation.scaled))),
            "routed_liquid_density_lbmol_ft3": evaluation.properties.liquid_density_lbmol_ft3.tolist(),
            "jacobians": [
                {
                    "step": float(item.step),
                    "rank": int(item.rank),
                    "condition": float(item.condition),
                    "singular_values": item.singular_values.tolist(),
                }
                for item in jacobians
            ],
            "spectrum_relative_change": spectrum_change,
            "matrix_relative_frobenius_change": matrix_change,
            "component_telescoping_relative_error": float(evaluation.component_telescoping_relative_error),
            "energy_telescoping_relative_error": float(evaluation.energy_telescoping_relative_error),
            "physical": physical,
            "provider_provenance": provenance,
            "exact_state_memoization": memo,
            "pass": endpoint_pass,
        }
    elapsed = time.perf_counter() - started
    pass_gate = bool(
        pass_gate
        and total_calls < contract["limits"]["logical_provider_calls"]
        and elapsed < contract["limits"]["wall_clock_sec"]
    )
    destination = ROOT / out_prefix
    destination.parent.mkdir(parents=True, exist_ok=True)
    evidence_path = destination.with_suffix(".npz")
    np.savez_compressed(evidence_path, **arrays)
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": "aligned_pr_density_parity_passed" if pass_gate else "aligned_pr_density_parity_failed",
        "decision": (
            "authorize_fixed_coordinate_scaling_design_with_aligned_pr_density"
            if pass_gate else "stop_aligned_pr_governing_density_path"
        ),
        "contract_commit": commit,
        "contract_payload_sha256": contract["contract_payload_sha256"],
        "provider_routing": contract["provider_routing"],
        "endpoints": endpoint_reports,
        "matrix_evidence": str(evidence_path.relative_to(ROOT)).replace("\\", "/"),
        "matrix_evidence_sha256": _sha(evidence_path),
        "logical_provider_calls": total_calls,
        "wall_clock_sec": elapsed,
        "nonlinear_solve_attempted": False,
        "state_changed": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "pass_gate": pass_gate,
        "executed_once": True,
    }
    destination.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    destination.with_suffix(".md").write_text(
        "\n".join(
            (
                "# DD-229 Aligned-PR Density Parity Audit",
                "",
                f"- Classification: `{report['classification']}`",
                f"- Decision: `{report['decision']}`",
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
