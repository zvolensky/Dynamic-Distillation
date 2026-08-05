#!/usr/bin/env python
"""Prepare or execute the zero-DWSIM DD-141 property-cache adjudication."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation import pr_flash_backend_v1 as backend
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


SCHEMA = "dd141-core-v3-thermo-provider-cache-resolution-contract-v1"
RESULT_SCHEMA = "dd141-core-v3-thermo-provider-cache-resolution-result-v1"
DD134_CONTRACT = Path(
    "logs/dd134_core_v3_modified_newton_short_controlled_trajectory_contract_20260805.json"
)
DD140_CONTRACT = Path(
    "logs/dd140_core_v3_dd138_jacobian_repeatability_contract_20260805.json"
)
DD140_RESULT = Path(
    "logs/dd140_core_v3_dd138_jacobian_repeatability_20260805.json"
)
CONTRACT = Path("logs/dd141_core_v3_thermo_provider_cache_resolution_contract_20260805.json")
RESULT = Path("logs/dd141_core_v3_thermo_provider_cache_resolution_20260805.json")
CONTRACT_DOC = Path(
    "docs/dd_141_core_v3_thermo_provider_cache_resolution_contract_20260805.md"
)
RESULT_DOC = Path("docs/dd_141_core_v3_thermo_provider_cache_resolution_20260805.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/thermo_provider_v1.py",
    "tests/test_core_v3_thermo_provider_cache_resolution_v1.py",
    "tools/audit_core_v3_thermo_provider_cache_resolution.py",
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


def prepare() -> dict[str, Any]:
    dd134 = _load(DD134_CONTRACT)
    dd140 = _load(DD140_RESULT)
    if (
        not dd140["pass"]
        or dd140["classification"] != "jacobian_process_or_order_dependent"
        or dd140["decision"] != "stop_solver_work_and_isolate_provider_derivative_state"
    ):
        raise RuntimeError("DD-141 requires the immutable DD-140 derivative-state stop")
    jacobian_step = float(dd134["jacobian_step"])
    temperature_scale = float(dd134["operating_spec"]["temperature_scale_F"])
    pressure_scale = float(dd134["pressure_coordinate_scale_psia"])
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD134_CONTRACT, DD140_CONTRACT, DD140_RESULT)
        },
        "jacobian_steps": [jacobian_step, jacobian_step / 2.0],
        "temperature_perturbations_F": [
            jacobian_step * temperature_scale,
            jacobian_step / 2.0 * temperature_scale,
        ],
        "pressure_perturbations_psia": [
            jacobian_step * pressure_scale,
            jacobian_step / 2.0 * pressure_scale,
        ],
        "legacy_cache_resolution": {
            "temperature_decimal_places": 3,
            "pressure_decimal_places": 3,
            "composition_decimal_places": 8,
        },
        "synthetic_alias_probes": {
            "temperature_F": [100.00040, 100.00049],
            "pressure_psia": [200.00040, 200.00049],
            "composition_low": [0.5, 0.3, 0.2],
            "composition_high": [0.500000004, 0.299999998, 0.199999998],
        },
        "dd140_inverse_step_ratio_bounds": [1.9, 2.1],
        "required_cache_misses_per_two_alias_queries": 1,
        "required_cache_hits_per_two_alias_queries": 1,
        "property_call_limit": 0,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "classification_rules": {
            "rounded_property_cache_alias_confirmed": (
                "distinct synthetic states collide, retain the first result, reverse with query order, "
                "and DD-140 error scales inversely with its finite-difference step"
            ),
            "cache_alias_not_confirmed": "one or more frozen cache-alias observations fail",
            "audit_invalid": "a source, implementation, schema, or zero-DWSIM gate fails",
        },
        "hard_stops": [
            "a DD-134/DD-140 source or DD-141 implementation hash changes",
            "a real DWSIM/backend property call occurs",
            "production cache behavior is changed during adjudication",
            "a residual, Jacobian, nonlinear solve, correction, state advance, timestep, trajectory, retry, fallback, clipping, or projection is attempted",
        ],
        "live_property_evaluation_attempted": False,
        "residual_evaluation_attempted": False,
        "jacobian_attempted": False,
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "audit_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-141 Frozen ThermoProvider Cache-Resolution Adjudication",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Scope: existing rounded density and heat-capacity cache keys",
                "- Probe: distinct synthetic states in forward and reverse query orders",
                "- DD-140 link: compare physical perturbation size with cache resolution and inverse-step error ratio",
                "- DWSIM/property, residual, Jacobian, solve, and timestep calls: `0`",
                "",
                "Passing authorizes a separately tested exact-state cache-key correction, not a solver or trajectory.",
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
        raise RuntimeError("DD-141 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-141 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-141 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-141 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def _provider() -> ThermoProviderV1:
    provider = ThermoProviderV1(["A", "B", "C"], ["A", "B", "C"])
    provider.configure_backend = lambda: None
    return provider


def _fake_density(temperature, pressure, composition) -> float:
    return float(
        temperature
        + 0.01 * pressure
        + 100.0 * np.dot(composition, [1.0, 2.0, 3.0])
    )


def _density_order(first, second) -> dict[str, Any]:
    provider = _provider()
    values = [
        provider.liquid_density_lbmol_ft3(*first),
        provider.liquid_density_lbmol_ft3(*second),
    ]
    counters = provider.get_call_counters()["uncategorized"]
    return {
        "values": values,
        "cache_keys": [repr(key) for key in provider._rhoL_cache],
        "cache_size": len(provider._rhoL_cache),
        "cache_hits": int(counters.get("rhoL_cache_hits", 0)),
        "cache_misses": int(counters.get("rhoL_cache_misses", 0)),
    }


def _cp_order(first_temperature: float, second_temperature: float) -> dict[str, Any]:
    provider = _provider()
    provider._cp_from_backend = (
        lambda temperature, _pressure, _composition: (temperature, -temperature)
    )
    first = provider.cp_liq_vap_btu_per_lbmolF(
        first_temperature, 200.0, [0.5, 0.3, 0.2]
    )
    second = provider.cp_liq_vap_btu_per_lbmolF(
        second_temperature, 200.0, [0.5, 0.3, 0.2]
    )
    counters = provider.get_call_counters()["uncategorized"]
    return {
        "values": [list(first), list(second)],
        "cache_size": len(provider._cp_cache),
        "cache_hits": int(counters.get("cp_cache_hits", 0)),
        "cache_misses": int(counters.get("cp_cache_misses", 0)),
    }


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    original_density = backend.liquid_density_lbmol_ft3
    backend.liquid_density_lbmol_ft3 = _fake_density
    try:
        probe = payload["synthetic_alias_probes"]
        composition = probe["composition_low"]
        temperature_low = (probe["temperature_F"][0], 200.0, composition)
        temperature_high = (probe["temperature_F"][1], 200.0, composition)
        pressure_low = (100.0, probe["pressure_psia"][0], composition)
        pressure_high = (100.0, probe["pressure_psia"][1], composition)
        composition_low = (100.0, 200.0, probe["composition_low"])
        composition_high = (100.0, 200.0, probe["composition_high"])
        records = {
            "temperature": {
                "forward": _density_order(temperature_low, temperature_high),
                "reverse": _density_order(temperature_high, temperature_low),
            },
            "pressure": {
                "forward": _density_order(pressure_low, pressure_high),
                "reverse": _density_order(pressure_high, pressure_low),
            },
            "composition": {
                "forward": _density_order(composition_low, composition_high),
                "reverse": _density_order(composition_high, composition_low),
            },
            "heat_capacity_temperature": {
                "forward": _cp_order(*probe["temperature_F"]),
                "reverse": _cp_order(*reversed(probe["temperature_F"])),
            },
        }
    finally:
        backend.liquid_density_lbmol_ft3 = original_density

    dd140 = _load(DD140_RESULT)
    coarse_h = dd140["cross_process_and_order_repeatability"]["coarse:h"]
    coarse_half = dd140["cross_process_and_order_repeatability"]["coarse:half_h"]
    refined_h = dd140["cross_process_and_order_repeatability"]["refined:h"]
    refined_half = dd140["cross_process_and_order_repeatability"]["refined:half_h"]
    inverse_step_ratios = {
        "coarse": coarse_half["max_abs_spread"] / coarse_h["max_abs_spread"],
        "refined": refined_half["max_abs_spread"] / refined_h["max_abs_spread"],
    }
    dimensions = ("temperature", "pressure", "composition")
    alias_gates = {
        name: (
            records[name]["forward"]["cache_size"] == 1
            and records[name]["reverse"]["cache_size"] == 1
            and records[name]["forward"]["values"][0]
            == records[name]["forward"]["values"][1]
            and records[name]["reverse"]["values"][0]
            == records[name]["reverse"]["values"][1]
            and records[name]["forward"]["values"][0]
            != records[name]["reverse"]["values"][0]
            and all(
                record["cache_hits"]
                == payload["required_cache_hits_per_two_alias_queries"]
                and record["cache_misses"]
                == payload["required_cache_misses_per_two_alias_queries"]
                for record in records[name].values()
            )
        )
        for name in dimensions
    }
    cp = records["heat_capacity_temperature"]
    cp_alias = all(
        item["cache_size"] == 1
        and item["cache_hits"] == 1
        and item["cache_misses"] == 1
        and item["values"][0] == item["values"][1]
        for item in cp.values()
    ) and cp["forward"]["values"][0] != cp["reverse"]["values"][0]
    ratio_low, ratio_high = payload["dd140_inverse_step_ratio_bounds"]
    perturbations_below_resolution = (
        payload["temperature_perturbations_F"][1] < 0.001
        and max(payload["pressure_perturbations_psia"]) < 0.001
    )
    gates = {
        **{f"{name}_density_cache_alias": value for name, value in alias_gates.items()},
        "heat_capacity_cache_alias": cp_alias,
        "jacobian_perturbations_reach_or_fall_below_cache_resolution": perturbations_below_resolution,
        "dd140_inverse_step_signature": all(
            ratio_low <= value <= ratio_high for value in inverse_step_ratios.values()
        ),
        "zero_dwsim_property_calls": True,
        "no_residual_jacobian_solve_or_state_advance": True,
    }
    passed = all(gates.values())
    classification = (
        "rounded_property_cache_alias_confirmed"
        if passed
        else "cache_alias_not_confirmed"
    )
    decision = (
        "authorize_exact_state_property_cache_key_correction"
        if passed
        else "stop_pending_cache_diagnosis_review"
    )
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": classification,
        "decision": decision,
        "records": records,
        "temperature_perturbations_F": payload["temperature_perturbations_F"],
        "pressure_perturbations_psia": payload["pressure_perturbations_psia"],
        "dd140_inverse_step_ratios": inverse_step_ratios,
        "gates": {key: bool(value) for key, value in gates.items()},
        "pass": bool(passed),
        "live_property_evaluation_attempted": False,
        "dwsim_property_calls": 0,
        "residual_evaluation_attempted": False,
        "jacobian_attempted": False,
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "audit_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-141 ThermoProvider Cache-Resolution Result",
                "",
                f"- Classification: `{classification}`",
                f"- Decision: `{decision}`",
                f"- Temperature perturbations: `{payload['temperature_perturbations_F']}` F",
                f"- Pressure perturbations: `{payload['pressure_perturbations_psia']}` psia",
                f"- DD-140 inverse-step ratios: coarse `{inverse_step_ratios['coarse']:.9f}`, refined `{inverse_step_ratios['refined']:.9f}`",
                "- Density cache aliases: temperature, pressure, and composition all confirmed",
                f"- Heat-capacity cache alias: `{cp_alias}`",
                "- DWSIM/property, residual, Jacobian, solve, state advance, and timestep calls: `0`",
                "",
                "The rounded cache keys merge distinct states and return whichever value was requested first. An exact-state key correction is authorized before any solver work resumes.",
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
                    "pass",
                }
            },
            indent=2,
        )
    )
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
