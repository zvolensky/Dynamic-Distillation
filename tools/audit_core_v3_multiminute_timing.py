#!/usr/bin/env python
"""Prepare or execute DD-152 zero-call DD-151 timing diagnosis."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


SCHEMA = "dd152-core-v3-multiminute-timing-audit-contract-v1"
RESULT_SCHEMA = "dd152-core-v3-multiminute-timing-audit-result-v1"
DD150_RESULT = Path(
    "logs/dd150_core_v3_parallel_captured_longer_trajectory_20260805.json"
)
DD151_CONTRACT = Path(
    "logs/dd151_core_v3_parallel_captured_multiminute_trajectory_contract_20260805.json"
)
DD151_RESULT = Path(
    "logs/dd151_core_v3_parallel_captured_multiminute_trajectory_20260805.json"
)
PROVIDER_SOURCE = Path("src/dynamic_distillation/thermo_provider_v1.py")
PARALLEL_SOURCE = Path("tools/run_core_v3_parallel_captured_short_trajectory.py")
CONTRACT = Path("logs/dd152_core_v3_multiminute_timing_audit_contract_20260806.json")
RESULT = Path("logs/dd152_core_v3_multiminute_timing_audit_20260806.json")
CONTRACT_DOC = Path(
    "docs/dd_152_core_v3_multiminute_timing_audit_contract_20260806.md"
)
RESULT_DOC = Path("docs/dd_152_core_v3_multiminute_timing_audit_20260806.md")
IMPLEMENTATION = (
    "tests/test_core_v3_multiminute_timing_audit.py",
    "tools/audit_core_v3_multiminute_timing.py",
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


def _summary(values: Sequence[float]) -> dict[str, float | int]:
    data = np.asarray(values, dtype=float)
    if data.size == 0 or np.any(~np.isfinite(data)):
        raise ValueError("timing series must contain finite values")
    return {
        "count": int(data.size),
        "sum_sec": float(np.sum(data)),
        "mean_sec": float(np.mean(data)),
        "median_sec": float(np.median(data)),
        "p95_sec": float(np.percentile(data, 95.0)),
        "max_sec": float(np.max(data)),
    }


def _window_summaries(
    values: Sequence[float], roots_per_window: int
) -> list[dict[str, float | int]]:
    if roots_per_window <= 0 or len(values) % roots_per_window != 0:
        raise ValueError("timing series must divide into complete windows")
    return [
        {
            "window": int(start // roots_per_window + 1),
            "root_start": int(start + 1),
            "root_end": int(start + roots_per_window),
            **_summary(values[start : start + roots_per_window]),
        }
        for start in range(0, len(values), roots_per_window)
    ]


def _trend(values: Sequence[float]) -> dict[str, float]:
    data = np.asarray(values, dtype=float)
    index = np.arange(data.size, dtype=float)
    slope, intercept = np.polyfit(index, data, 1)
    correlation = float(np.corrcoef(index, data)[0, 1])
    return {
        "slope_sec_per_root": float(slope),
        "intercept_sec": float(intercept),
        "pearson_root_order": correlation,
    }


def _path_records(result: Mapping[str, Any], path: str) -> list[Mapping[str, Any]]:
    token = f":{path}:"
    return [
        item
        for item in result["parallel_jacobian_evidence"]
        if token in str(item["state_id"])
    ]


def _path_audit(
    result: Mapping[str, Any], path: str, roots_per_window: int
) -> dict[str, Any]:
    records = _path_records(result, path)
    walls = [float(item["wall_clock_sec"]) for item in records]
    windows = _window_summaries(walls, roots_per_window)
    trajectory = result["trajectories"][path]
    iterations = [int(item["iterations"]) for item in trajectory]
    residual_evaluations = [int(item["residual_evaluations"]) for item in trajectory]
    return {
        "jacobian": _summary(walls),
        "windows": windows,
        "trend": _trend(walls),
        "first_to_last_window_mean_ratio": float(
            windows[-1]["mean_sec"] / windows[0]["mean_sec"]
        ),
        "solver_iterations": _summary(iterations),
        "residual_evaluations": _summary(residual_evaluations),
    }


def _decomposition(result: Mapping[str, Any]) -> dict[str, float]:
    jacobian = sum(
        float(item["wall_clock_sec"])
        for item in result["parallel_jacobian_evidence"]
    )
    trajectory = float(result["trajectory_wall_clock_sec"])
    total = float(result["total_wall_clock_sec"])
    roots = len(result["parallel_jacobian_evidence"])
    non_jacobian = trajectory - jacobian
    outside = total - trajectory
    return {
        "roots": float(roots),
        "jacobian_sec": float(jacobian),
        "trajectory_non_jacobian_sec": float(non_jacobian),
        "outside_trajectory_sec": float(outside),
        "total_sec": float(total),
        "jacobian_sec_per_root": float(jacobian / roots),
        "trajectory_non_jacobian_sec_per_root": float(non_jacobian / roots),
    }


def prepare() -> dict[str, Any]:
    dd150 = _load(DD150_RESULT)
    dd151_contract = _load(DD151_CONTRACT)
    dd151 = _load(DD151_RESULT)
    if (
        not dd150["pass"]
        or dd151["pass"]
        or dd151["classification"]
        != "parallel_captured_five_minute_trajectory_failed"
    ):
        raise RuntimeError("DD-152 requires immutable DD-150 pass and DD-151 wall failure")
    payload = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (
                DD150_RESULT,
                DD151_CONTRACT,
                DD151_RESULT,
                PROVIDER_SOURCE,
                PARALLEL_SOURCE,
            )
        },
        "audit": {
            "model_or_provider_calls_allowed": 0,
            "expected_dd150_roots": 180,
            "expected_dd151_roots": 900,
            "coarse_roots_per_60s_window": 60,
            "refined_roots_per_60s_window": 120,
            "expected_dd151_tasks": 37800,
            "expected_dd151_worker_calls": 1058400,
            "attribution_majority_fraction": 0.60,
            "history_ratio_threshold": 1.25,
            "history_correlation_threshold": 0.50,
            "provider_cache_limit": 2000,
            "provider_cache_eviction": "clear entire cache after insertion beyond limit",
            "analysis_wall_limit_sec": 120.0,
        },
        "implementation_sha256": {
            path: _sha(ROOT / path) for path in IMPLEMENTATION
        },
        "hard_stops": [
            "a DD-150/DD-151 result, provider source, parallel source, or DD-152 implementation hash changes",
            "any DWSIM, provider, residual, Jacobian, solver, correction, state advance, timestep, or trajectory call occurs",
            "saved root, task, worker-call, prefix-equivalence, or scientific-gate integrity does not reproduce",
            "timing decomposition does not telescope to saved total wall time",
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
                "# DD-152 Frozen Zero-Call Multiminute Timing Audit Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Sources: immutable DD-150/DD-151 results and current frozen provider/parallel sources",
                "- Work: static timing decomposition only",
                "- Windows: 60 simulated seconds per coarse/refined segment",
                "- Attribution: Jacobian, trajectory non-Jacobian, and outside-trajectory wall",
                "- History test: first/last window ratio `>1.25` and root-order correlation `>0.50`",
                "- Provider fact: exact-state density/Cp caches cap at 2,000 entries and clear wholesale",
                "- DWSIM/provider/model/solver/state calls: prohibited",
                "- Audit wall limit: `<120 s`",
                "",
                "The audit may diagnose and recommend a bounded efficiency correction. It cannot authorize another trajectory.",
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
        raise RuntimeError("DD-152 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-152 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-152 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-152 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    import time

    started = time.perf_counter()
    payload = _load(CONTRACT)
    _verify(payload)
    audit = payload["audit"]
    dd150 = _load(DD150_RESULT)
    dd151 = _load(DD151_RESULT)
    paths = {
        "dd150": {
            "coarse": _path_audit(dd150, "coarse", 60),
            "refined": _path_audit(dd150, "refined", 120),
        },
        "dd151": {
            "coarse": _path_audit(dd151, "coarse", 60),
            "refined": _path_audit(dd151, "refined", 120),
        },
    }
    decomposition = {
        "dd150": _decomposition(dd150),
        "dd151": _decomposition(dd151),
    }
    scale = audit["expected_dd151_roots"] / audit["expected_dd150_roots"]
    excess = {
        "total_sec": decomposition["dd151"]["total_sec"]
        - scale * decomposition["dd150"]["total_sec"],
        "jacobian_sec": decomposition["dd151"]["jacobian_sec"]
        - scale * decomposition["dd150"]["jacobian_sec"],
        "trajectory_non_jacobian_sec": decomposition["dd151"][
            "trajectory_non_jacobian_sec"
        ]
        - scale * decomposition["dd150"]["trajectory_non_jacobian_sec"],
        "outside_trajectory_sec": decomposition["dd151"]["outside_trajectory_sec"]
        - scale * decomposition["dd150"]["outside_trajectory_sec"],
    }
    excess["telescoping_error_sec"] = float(
        excess["total_sec"]
        - excess["jacobian_sec"]
        - excess["trajectory_non_jacobian_sec"]
        - excess["outside_trajectory_sec"]
    )
    positive_total = sum(max(excess[key], 0.0) for key in (
        "jacobian_sec",
        "trajectory_non_jacobian_sec",
        "outside_trajectory_sec",
    ))
    excess["positive_attribution_fraction"] = {
        key: float(max(excess[key], 0.0) / positive_total)
        for key in (
            "jacobian_sec",
            "trajectory_non_jacobian_sec",
            "outside_trajectory_sec",
        )
    }
    fractions = excess["positive_attribution_fraction"]
    if fractions["jacobian_sec"] >= audit["attribution_majority_fraction"]:
        attribution = "jacobian_dominated"
    elif fractions["trajectory_non_jacobian_sec"] >= audit["attribution_majority_fraction"]:
        attribution = "main_process_non_jacobian_dominated"
    else:
        attribution = "mixed_timing_growth"

    history_paths = {}
    for path in ("coarse", "refined"):
        item = paths["dd151"][path]
        history_paths[path] = bool(
            item["first_to_last_window_mean_ratio"]
            > audit["history_ratio_threshold"]
            and item["trend"]["pearson_root_order"]
            > audit["history_correlation_threshold"]
        )
    history_dependent = any(history_paths.values())
    cache_inference = (
        "timing_is_history_dependent_and_consistent_with_persistent_provider_or_backend_state; wholesale_cache_clears_are_a_specific_candidate, not proven causality"
        if history_dependent
        else "saved_timing_does_not_support_monotonic_persistent-state_slowdown"
    )
    elapsed = time.perf_counter() - started
    gates = {
        "source_result_integrity": bool(
            dd150["pass"]
            and not dd151["pass"]
            and all(
                value
                for key, value in dd151["source_dd134_gates"].items()
                if key != "wall"
            )
        ),
        "root_counts": len(dd150["parallel_jacobian_evidence"])
        == audit["expected_dd150_roots"]
        and len(dd151["parallel_jacobian_evidence"])
        == audit["expected_dd151_roots"],
        "work_counts": dd151["parallel_provider_calls"]
        == audit["expected_dd151_worker_calls"]
        and sum(
            int(item["task_count"])
            for item in dd151["parallel_jacobian_evidence"]
        )
        == audit["expected_dd151_tasks"],
        "prefix_and_science": max(dd151["capture_differences"].values()) == 0.0
        and max(dd151["trajectory_differences"].values()) == 0.0,
        "decomposition_telescopes": abs(excess["telescoping_error_sec"]) < 1.0e-9,
        "zero_model_calls": True,
        "wall": elapsed < audit["analysis_wall_limit_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": attribution if passed else "timing_audit_invalid",
        "decision": (
            "authorize_separately_frozen_persistent_pool_state_efficiency_probe"
            if passed and history_dependent
            else "retain_current_parallel_path_without_live_extension"
        ),
        "paths": paths,
        "decomposition": decomposition,
        "five_x_dd150_excess": excess,
        "history_dependent_paths": history_paths,
        "history_dependent": bool(history_dependent),
        "cache_backend_inference": cache_inference,
        "provider_cache_facts": {
            "density_limit": audit["provider_cache_limit"],
            "heat_capacity_limit": audit["provider_cache_limit"],
            "eviction": audit["provider_cache_eviction"],
        },
        "recommended_probe": {
            "scope": "saved-state Jacobian timing only; no nonlinear solve or state acceptance",
            "comparison": "one persistent pool versus precommitted periodic fresh-pool boundaries",
            "science_gate": "all matrices bit-for-bit equal to saved DD-151 matrices or reconstructed hashes",
            "purpose": "separate worker lifetime/backend state from physical-state cost before any trajectory rerun",
        },
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
                "# DD-152 Zero-Call Multiminute Timing Audit Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- DD-150/DD-151 decomposition: `{decomposition}`",
                f"- Excess versus five times DD-150: `{excess}`",
                f"- History-dependent paths: `{history_paths}`",
                f"- Provider/cache inference: `{cache_inference}`",
                f"- Analysis wall: `{elapsed:.3f} s`",
                f"- Model/provider calls: `0`",
                f"- Gates: `{gates}`",
                "",
                "The audit attributes the measured wall overrun without rerunning thermodynamics or dynamics. Cache/backend state is treated as a bounded hypothesis, not a proven cause.",
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
                    "analysis_wall_sec",
                    "pass",
                }
            },
            indent=2,
        )
    )
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
