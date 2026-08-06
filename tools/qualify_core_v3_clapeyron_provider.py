#!/usr/bin/env python
"""Qualify Clapeyron as an optional Core V3 property authority."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    audit_provider_governed_registry,
    build_provider_governed_registry,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_backend_factory_v1 import (
    _clapeyron_dwsim_pr_userlocations,
)
from dynamic_distillation.thermo_clapeyron_provider_v1 import (
    ThermoClapeyronProviderV1,
)
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


SOURCE = ROOT / "logs/dd160_core_v3_memoized_captured_multiminute_trajectory_contract_20260806.json"
RESULT = ROOT / "logs/dd161_core_v3_clapeyron_provider_qualification_20260806.json"


def _max_abs(left: Any, right: Any) -> float:
    return float(
        np.max(
            np.abs(
                np.asarray(left, dtype=float).reshape((-1,))
                - np.asarray(right, dtype=float).reshape((-1,))
            )
        )
    )


def _property_packet(provider: Any, states: list[dict[str, Any]], offset_F: float) -> None:
    for state in states:
        temperature = float(state["temperature_F"]) + float(offset_F)
        pressure = float(state["pressure_psia"])
        provider.phase_enthalpy_BTU_lbmol(
            "liquid", temperature, pressure, state["liquid_x"]
        )
        provider.liquid_density_lbmol_ft3(
            temperature, pressure, state["liquid_x"]
        )
    for state in states[:4]:
        temperature = float(state["temperature_F"]) + float(offset_F)
        pressure = float(state["pressure_psia"])
        provider.phase_fugacity_coefficients(
            "liquid", temperature, pressure, state["liquid_x"]
        )
        provider.phase_fugacity_coefficients(
            "vapor", temperature, pressure, state["vapor_y"]
        )
        provider.phase_enthalpy_BTU_lbmol(
            "vapor", temperature, pressure, state["vapor_y"]
        )
        provider.vapor_z_factor_F_psia(
            temperature, pressure, state["vapor_y"]
        )
    drum = states[0]
    temperature = float(drum["temperature_F"]) + float(offset_F)
    provider.phase_fugacity_coefficients(
        "liquid", temperature, float(drum["pressure_psia"]), drum["liquid_x"]
    )
    provider.phase_fugacity_coefficients(
        "vapor", temperature, float(drum["pressure_psia"]), drum["bubble_y"]
    )


def _benchmark_packets(provider: Any, states: list[dict[str, Any]], count: int) -> float:
    _property_packet(provider, states, 0.0)
    started = time.perf_counter()
    for index in range(count):
        _property_packet(provider, states, 1.0e-4 * float(index + 1))
    return float(time.perf_counter() - started)


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    mapping = source["source_mapping"]
    root = source["accepted_root_state"]
    case = load_case_from_excel(source["workbook"])
    column = build_column_spec_from_case(case)

    dwsim = ThermoProviderV1(
        column.components_excel,
        column.components_dwsim,
        silence_backend_console=True,
        property_package="pr",
    )
    alignment_started = time.perf_counter()
    model_kwargs = _clapeyron_dwsim_pr_userlocations(column)
    alignment_seconds = float(time.perf_counter() - alignment_started)
    build_started = time.perf_counter()
    clapeyron = ThermoClapeyronProviderV1(
        column.components_excel,
        column.components_dwsim,
        model_name="PR",
        model_kwargs=model_kwargs,
    )
    clapeyron.validate_backend_available()
    model_build_seconds = float(time.perf_counter() - build_started)

    states: list[dict[str, Any]] = []
    for index, role in enumerate(mapping["roles"]):
        states.append(
            {
                "role": role,
                "temperature_F": float(root["temperature_F"][index]),
                "pressure_psia": float(mapping["pressure_psia"][index]),
                "liquid_x": list(root["liquid_mole_fraction"][index]),
                "vapor_y": (
                    list(root["vapor_mole_fraction"][index])
                    if index < 4
                    else list(root["vapor_mole_fraction"][-1])
                ),
                "bubble_y": list(root["bubble_vapor_mole_fraction"]),
            }
        )

    comparisons: list[dict[str, Any]] = []
    for state in states:
        temperature = state["temperature_F"]
        pressure = state["pressure_psia"]
        liquid = state["liquid_x"]
        vapor = state["vapor_y"]
        d_phi_l = dwsim.phase_fugacity_coefficients(
            "liquid", temperature, pressure, liquid
        )
        c_phi_l = clapeyron.phase_fugacity_coefficients(
            "liquid", temperature, pressure, liquid
        )
        d_phi_v = dwsim.phase_fugacity_coefficients(
            "vapor", temperature, pressure, vapor
        )
        c_phi_v = clapeyron.phase_fugacity_coefficients(
            "vapor", temperature, pressure, vapor
        )
        d_hl = dwsim.phase_enthalpy_BTU_lbmol(
            "liquid", temperature, pressure, liquid
        )
        c_hl = clapeyron.phase_enthalpy_BTU_lbmol(
            "liquid", temperature, pressure, liquid
        )
        d_hv = dwsim.phase_enthalpy_BTU_lbmol(
            "vapor", temperature, pressure, vapor
        )
        c_hv = clapeyron.phase_enthalpy_BTU_lbmol(
            "vapor", temperature, pressure, vapor
        )
        d_rho = float(
            dwsim.liquid_density_lbmol_ft3(temperature, pressure, liquid)
        )
        c_rho = float(
            clapeyron.liquid_density_lbmol_ft3(temperature, pressure, liquid)
        )
        d_z = float(dwsim.vapor_z_factor_F_psia(temperature, pressure, vapor))
        c_z = float(clapeyron.vapor_z_factor_F_psia(temperature, pressure, vapor))
        comparisons.append(
            {
                "role": state["role"],
                "temperature_F": temperature,
                "pressure_psia": pressure,
                "max_abs_fugacity_liquid_delta": _max_abs(d_phi_l, c_phi_l),
                "max_abs_fugacity_vapor_delta": _max_abs(d_phi_v, c_phi_v),
                "liquid_enthalpy_delta_BTU_lbmol": float(c_hl - d_hl),
                "vapor_enthalpy_delta_BTU_lbmol": float(c_hv - d_hv),
                "latent_enthalpy_delta_BTU_lbmol": float(
                    (c_hv - c_hl) - (d_hv - d_hl)
                ),
                "liquid_density_relative_delta": float((c_rho - d_rho) / d_rho),
                "vapor_z_relative_delta": float((c_z - d_z) / d_z),
            }
        )

    mw_dwsim = np.asarray(dwsim.component_mw_lbm_per_lbmol(), dtype=float)
    mw_clapeyron = np.asarray(
        clapeyron.component_mw_lbm_per_lbmol(), dtype=float
    )
    feed = states[2]
    phi_reference = clapeyron.phase_fugacity_coefficients(
        "liquid",
        feed["temperature_F"],
        feed["pressure_psia"],
        feed["liquid_x"],
    )
    repeat_delta = 0.0
    for _ in range(100):
        repeat_delta = max(
            repeat_delta,
            _max_abs(
                phi_reference,
                clapeyron.phase_fugacity_coefficients(
                    "liquid",
                    feed["temperature_F"],
                    feed["pressure_psia"],
                    feed["liquid_x"],
                ),
            ),
        )

    packet_count = 50
    dwsim_packet_seconds = _benchmark_packets(dwsim, states, packet_count)
    clapeyron_packet_seconds = _benchmark_packets(clapeyron, states, packet_count)
    registry = build_provider_governed_registry(
        mapping["component_names"], provider_identity="clapeyron"
    )
    registry_audit = audit_provider_governed_registry(registry)

    worst_phi_l = max(row["max_abs_fugacity_liquid_delta"] for row in comparisons)
    worst_phi_v = max(row["max_abs_fugacity_vapor_delta"] for row in comparisons)
    worst_density = max(
        abs(row["liquid_density_relative_delta"]) for row in comparisons
    )
    worst_latent = max(
        abs(row["latent_enthalpy_delta_BTU_lbmol"]) for row in comparisons
    )
    speedup = dwsim_packet_seconds / clapeyron_packet_seconds
    gates = {
        "provider_contract_complete": all(
            callable(getattr(clapeyron, name, None))
            for name in (
                "phase_fugacity_coefficients",
                "phase_enthalpy_BTU_lbmol",
                "liquid_density_lbmol_ft3",
                "vapor_z_factor_F_psia",
                "component_mw_lbm_per_lbmol",
            )
        ),
        "clapeyron_registry_pass": bool(registry_audit.pass_gate),
        "molecular_weight_match": _max_abs(mw_dwsim, mw_clapeyron) < 1.0e-10,
        "forced_fugacity_match": worst_phi_l < 1.0e-3 and worst_phi_v < 1.0e-3,
        "repeatability": repeat_delta == 0.0,
        "meaningful_warm_packet_speedup": speedup >= 2.0,
        "liquid_density_drop_in_match": worst_density < 1.0e-2,
        "caloric_drop_in_match": worst_latent < 5.0,
        "no_solve_or_dynamics": True,
    }
    full_drop_in = bool(all(gates.values()))
    fugacity_candidate = bool(
        all(
            gates[name]
            for name in (
                "provider_contract_complete",
                "clapeyron_registry_pass",
                "molecular_weight_match",
                "forced_fugacity_match",
                "repeatability",
                "meaningful_warm_packet_speedup",
                "no_solve_or_dynamics",
            )
        )
    )
    result = {
        "schema_id": "dd161-core-v3-clapeyron-provider-qualification-v1",
        "classification": (
            "clapeyron_full_provider_qualified"
            if full_drop_in
            else (
                "clapeyron_fugacity_authority_qualified_only"
                if fugacity_candidate
                else "clapeyron_provider_not_qualified"
            )
        ),
        "decision": (
            "authorize_full_provider_equivalence_contract"
            if full_drop_in
            else (
                "authorize_fugacity_acceleration_design_only"
                if fugacity_candidate
                else "retain_dwsim_and_stop_clapeyron_integration"
            )
        ),
        "source_contract": str(SOURCE.relative_to(ROOT)),
        "components": list(mapping["component_names"]),
        "parameter_alignment": "DWSIM PR Tc/Pc/Mw/acentric-factor/kij",
        "startup_seconds": {
            "dwsim_parameter_alignment": alignment_seconds,
            "clapeyron_model_build": model_build_seconds,
        },
        "molecular_weights": {
            "dwsim_lbm_lbmol": mw_dwsim.tolist(),
            "clapeyron_lbm_lbmol": mw_clapeyron.tolist(),
            "max_abs_delta": _max_abs(mw_dwsim, mw_clapeyron),
        },
        "fixed_state_comparisons": comparisons,
        "worst": {
            "fugacity_liquid_max_abs_delta": worst_phi_l,
            "fugacity_vapor_max_abs_delta": worst_phi_v,
            "liquid_density_max_abs_relative_delta": worst_density,
            "latent_enthalpy_max_abs_delta_BTU_lbmol": worst_latent,
            "repeat_max_abs_delta": repeat_delta,
        },
        "warm_property_packet_benchmark": {
            "packet_count": packet_count,
            "calls_per_packet": 28,
            "dwsim_seconds": dwsim_packet_seconds,
            "clapeyron_seconds": clapeyron_packet_seconds,
            "speedup": speedup,
            "neighboring_temperature_offset_F": 1.0e-4,
        },
        "gates": gates,
        "full_drop_in_authorized": full_drop_in,
        "fugacity_acceleration_design_authorized": fugacity_candidate,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
    }
    RESULT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if fugacity_candidate else 1


if __name__ == "__main__":
    raise SystemExit(main())
