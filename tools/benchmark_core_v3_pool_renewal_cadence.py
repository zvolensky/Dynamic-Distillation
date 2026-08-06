#!/usr/bin/env python
"""Prepare or execute DD-154 zero-call pool-renewal cadence benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


SCHEMA = "dd154-core-v3-pool-renewal-cadence-contract-v1"
RESULT_SCHEMA = "dd154-core-v3-pool-renewal-cadence-result-v1"
DD151_RESULT = Path(
    "logs/dd151_core_v3_parallel_captured_multiminute_trajectory_20260805.json"
)
DD152_RESULT = Path("logs/dd152_core_v3_multiminute_timing_audit_20260806.json")
DD153_RESULT = Path("logs/dd153_core_v3_worker_lifetime_efficiency_probe_20260806.json")
CONTRACT = Path("logs/dd154_core_v3_pool_renewal_cadence_contract_20260806.json")
RESULT = Path("logs/dd154_core_v3_pool_renewal_cadence_20260806.json")
CONTRACT_DOC = Path("docs/dd_154_core_v3_pool_renewal_cadence_contract_20260806.md")
RESULT_DOC = Path("docs/dd_154_core_v3_pool_renewal_cadence_20260806.md")
IMPLEMENTATION = (
    "tests/test_core_v3_pool_renewal_cadence.py",
    "tools/benchmark_core_v3_pool_renewal_cadence.py",
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


def _project(
    cadence: int,
    *,
    coarse_roots: int,
    refined_roots: int,
    fresh_coarse_sec: float,
    fresh_refined_sec: float,
    coarse_slope_sec_per_root: float,
    refined_slope_sec_per_root: float,
    pool_lifecycle_overhead_sec: float,
    fixed_non_jacobian_sec: float,
    calibration_sec: float = 0.0,
) -> dict[str, float | int]:
    total_roots = int(coarse_roots + refined_roots)
    if cadence <= 0 or cadence > total_roots:
        raise ValueError("cadence must be within the complete root sequence")
    jacobian = 0.0
    for global_index in range(total_roots):
        age = global_index % cadence
        if global_index < coarse_roots:
            jacobian += fresh_coarse_sec + coarse_slope_sec_per_root * age
        else:
            jacobian += fresh_refined_sec + refined_slope_sec_per_root * age
    pools = int(math.ceil(total_roots / cadence))
    renewal = pools * pool_lifecycle_overhead_sec
    total = jacobian + renewal + fixed_non_jacobian_sec + calibration_sec
    return {
        "cadence_roots": int(cadence),
        "pool_count": pools,
        "jacobian_sec": float(jacobian),
        "pool_lifecycle_sec": float(renewal),
        "fixed_non_jacobian_sec": float(fixed_non_jacobian_sec),
        "calibration_sec": float(calibration_sec),
        "projected_total_sec": float(total),
    }


def _select(projections: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    if not projections:
        raise ValueError("at least one cadence projection is required")
    return min(projections, key=lambda item: float(item["projected_total_sec"]))


def prepare() -> dict[str, Any]:
    dd151 = _load(DD151_RESULT)
    dd152 = _load(DD152_RESULT)
    dd153 = _load(DD153_RESULT)
    if (
        dd151["pass"]
        or not dd152["pass"]
        or not dd153["pass"]
        or dd153["decision"]
        != "authorize_separately_frozen_pool_renewal_cadence_benchmark"
    ):
        raise RuntimeError("DD-154 requires immutable DD-151/DD-152/DD-153 decisions")
    payload = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD151_RESULT, DD152_RESULT, DD153_RESULT)
        },
        "benchmark": {
            "candidate_cadences_roots": [60, 120, 180, 240, 300, 360, 450, 900],
            "coarse_roots": 300,
            "refined_roots": 600,
            "baseline_cadence_roots": 900,
            "slope_scale_nominal": 1.0,
            "slope_scale_low": 0.75,
            "slope_scale_high": 1.25,
            "minimum_projected_improvement_fraction": 0.20,
            "selected_cadence_minimum_roots": 120,
            "selected_cadence_maximum_roots": 450,
            "analysis_wall_limit_sec": 120.0,
            "model_or_provider_calls_allowed": 0,
        },
        "implementation_sha256": {
            path: _sha(ROOT / path) for path in IMPLEMENTATION
        },
        "hard_stops": [
            "a DD-151/DD-152/DD-153 result or DD-154 implementation hash changes",
            "the frozen candidate set, projection equation, slope uncertainty, or selection rule changes",
            "saved decomposition does not telescope or the cadence-900 model cannot be calibrated exactly to DD-151",
            "any DWSIM, provider, residual, Jacobian, solve, correction, state advance, timestep, or trajectory call occurs",
            "the audit exceeds 120 seconds",
        ],
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-154 Frozen Zero-Call Pool-Renewal Cadence Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Candidates: `60/120/180/240/300/360/450/900` roots",
                "- Inputs: DD-152 coarse/refined aging slopes and DD-153 fresh matrix/pool lifecycle measurements",
                "- Projection: path-specific fresh cost plus slope-by-worker-age, complete pool lifecycle overhead, and fixed DD-151 non-Jacobian wall",
                "- Calibration: cadence `900` must reproduce DD-151 total wall exactly",
                "- Uncertainty: slopes at `0.75x`, `1.0x`, and `1.25x`",
                "- Selection: minimum nominal projected total; cadence must lie in `120..450` and improve at least `20%`",
                "- DWSIM/provider/model/solver/state calls: prohibited",
                "",
                "Passing may authorize only implementation of the selected renewal cadence plus a separately frozen saved-state equivalence proof. No trajectory is authorized.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def _verify(payload: dict[str, Any]) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-154 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-154 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-154 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-154 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    started = time.perf_counter()
    payload = _load(CONTRACT)
    _verify(payload)
    benchmark = payload["benchmark"]
    dd151 = _load(DD151_RESULT)
    dd152 = _load(DD152_RESULT)
    dd153 = _load(DD153_RESULT)

    fresh_by_path = {
        path: float(
            statistics.median(
                item["fresh_median_wall_sec"]
                for item in dd153["checkpoints"]
                if item["path"] == path
            )
        )
        for path in ("coarse", "refined")
    }
    lifecycle = float(
        statistics.mean(
            record["pool_lifetime_sec"] - record["fresh_matrix_wall_sec"]
            for record in dd153["records"]
        )
    )
    slopes = {
        path: float(dd152["paths"]["dd151"][path]["trend"]["slope_sec_per_root"])
        for path in ("coarse", "refined")
    }
    fixed_non_jacobian = float(
        dd152["decomposition"]["dd151"]["trajectory_non_jacobian_sec"]
    )
    common = {
        "coarse_roots": int(benchmark["coarse_roots"]),
        "refined_roots": int(benchmark["refined_roots"]),
        "fresh_coarse_sec": fresh_by_path["coarse"],
        "fresh_refined_sec": fresh_by_path["refined"],
        "pool_lifecycle_overhead_sec": lifecycle,
        "fixed_non_jacobian_sec": fixed_non_jacobian,
    }
    uncalibrated_baseline = _project(
        int(benchmark["baseline_cadence_roots"]),
        coarse_slope_sec_per_root=slopes["coarse"],
        refined_slope_sec_per_root=slopes["refined"],
        **common,
    )
    calibration = float(
        dd151["total_wall_clock_sec"] - uncalibrated_baseline["projected_total_sec"]
    )
    scenarios = {}
    for label, scale_key in (
        ("low", "slope_scale_low"),
        ("nominal", "slope_scale_nominal"),
        ("high", "slope_scale_high"),
    ):
        scale = float(benchmark[scale_key])
        projections = [
            _project(
                int(cadence),
                coarse_slope_sec_per_root=scale * slopes["coarse"],
                refined_slope_sec_per_root=scale * slopes["refined"],
                calibration_sec=calibration,
                **common,
            )
            for cadence in benchmark["candidate_cadences_roots"]
        ]
        scenarios[label] = {
            "slope_scale": scale,
            "projections": projections,
            "selected": dict(_select(projections)),
        }
    selected = scenarios["nominal"]["selected"]
    baseline = next(
        item
        for item in scenarios["nominal"]["projections"]
        if item["cadence_roots"] == benchmark["baseline_cadence_roots"]
    )
    improvement = float(
        (baseline["projected_total_sec"] - selected["projected_total_sec"])
        / baseline["projected_total_sec"]
    )
    elapsed = time.perf_counter() - started
    gates = {
        "source_integrity": bool(
            not dd151["pass"] and dd152["pass"] and dd153["pass"]
        ),
        "baseline_calibration": abs(
            baseline["projected_total_sec"] - dd151["total_wall_clock_sec"]
        )
        < 1.0e-9,
        "interior_selection": benchmark["selected_cadence_minimum_roots"]
        <= selected["cadence_roots"]
        <= benchmark["selected_cadence_maximum_roots"],
        "meaningful_improvement": improvement
        >= benchmark["minimum_projected_improvement_fraction"],
        "uncertainty_bounded": all(
            benchmark["selected_cadence_minimum_roots"]
            <= scenarios[label]["selected"]["cadence_roots"]
            <= benchmark["selected_cadence_maximum_roots"]
            for label in scenarios
        ),
        "zero_model_calls": True,
        "wall": elapsed < benchmark["analysis_wall_limit_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "pool_renewal_cadence_selected" if passed else "cadence_model_invalid"
        ),
        "decision": (
            "authorize_selected_cadence_implementation_and_saved_state_proof"
            if passed
            else "retain_persistent_pool_without_trajectory_extension"
        ),
        "measured_inputs": {
            "fresh_matrix_sec": fresh_by_path,
            "aging_slope_sec_per_root": slopes,
            "pool_lifecycle_overhead_sec": lifecycle,
            "fixed_non_jacobian_sec": fixed_non_jacobian,
            "calibration_sec": calibration,
        },
        "scenarios": scenarios,
        "selected_cadence_roots": int(selected["cadence_roots"]),
        "selected_projected_total_sec": float(selected["projected_total_sec"]),
        "baseline_projected_total_sec": float(baseline["projected_total_sec"]),
        "projected_improvement_fraction": improvement,
        "analysis_wall_sec": float(elapsed),
        "model_or_provider_calls": 0,
        "gates": gates,
        "pass": bool(passed),
        "campaign_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-154 Zero-Call Pool-Renewal Cadence Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Measured inputs: `{result['measured_inputs']}`",
                f"- Selected cadence: `{result['selected_cadence_roots']} roots`",
                f"- Projected total: `{result['selected_projected_total_sec']:.3f} s`",
                f"- Persistent baseline: `{result['baseline_projected_total_sec']:.3f} s`",
                f"- Projected improvement: `{100.0 * improvement:.2f}%`",
                f"- Low/nominal/high selections: `{[scenarios[key]['selected']['cadence_roots'] for key in ('low', 'nominal', 'high')]}`",
                f"- Model/provider calls: `0`",
                f"- Gates: `{gates}`",
                "",
                "The selected cadence is a projection from frozen measurements. Implementation and saved-state equivalence require a separate contract before any trajectory rerun.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    output = prepare() if args.prepare else execute()
    print(
        json.dumps(
            {
                key: output[key]
                for key in output
                if key
                in {
                    "schema_id",
                    "classification",
                    "decision",
                    "contract_payload_sha256",
                    "selected_cadence_roots",
                    "analysis_wall_sec",
                    "pass",
                }
            },
            indent=2,
        )
    )
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
