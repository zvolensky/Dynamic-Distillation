#!/usr/bin/env python
"""Create or continue a reusable Core V3 C3/C4 dynamic checkpoint."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from dataclasses import replace
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from typing import Any, Mapping

import numpy as np
from scipy.optimize import least_squares


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_vapor_holdup_dynamic_pressure_residual as dd273  # noqa: E402
import run_core_v3_vapor_holdup_dynamic_pressure_thirty_second_trajectory as dd274  # noqa: E402
import run_core_v3_vapor_holdup_small_moving_step as dd249  # noqa: E402
import run_core_v3_vapor_holdup_terminal_control_short_trajectory as dd267  # noqa: E402

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case  # noqa: E402
from dynamic_distillation.core_v3.vapor_holdup_dynamic_pressure_contract_v1 import (  # noqa: E402
    audit_vapor_holdup_dynamic_pressure_contract,
    build_vapor_holdup_dynamic_pressure_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (  # noqa: E402
    VaporHoldupImplicitReference,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_contract_v1 import (  # noqa: E402
    terminal_level_fractions,
)
from dynamic_distillation.core_v3.vapor_holdup_regulatory_control_contract_v1 import (  # noqa: E402
    VaporHoldupRegulatoryControlContract,
    VaporHoldupRegulatoryControllerSpecification,
    audit_vapor_holdup_regulatory_control_contract,
    build_vapor_holdup_regulatory_control_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_regulatory_control_implicit_residual_v1 import (  # noqa: E402
    evaluate_vapor_holdup_regulatory_control_implicit_residual,
    regulatory_control_bounds,
    regulatory_control_initial_coordinates,
    regulatory_control_pattern,
)
from dynamic_distillation.core_v3.persistent_parallel_colored_jacobian_v1 import (  # noqa: E402
    PersistentParallelColoredJacobian,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit  # noqa: E402
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel  # noqa: E402


SCHEMA = "dynamic_distillation.core_v3_checkpoint.v1"
MODEL_ID = "core-v3-c3c4-vapor-holdup-dynamic-pressure"
DEFAULT_TIMESTEP_SEC = 0.25
VALIDATED_TIMESTEPS_SEC = (0.25, 0.5)
DEFAULT_DD274_CHECKPOINT = Path(
    "logs/core_v3_checkpoints/dd274_endpoint_core_v3_checkpoint.npz"
)
SS_REL_RATE_TOL_PER_SEC = 3.0e-3
SS_TEMP_RATE_TOL_F_PER_SEC = 0.15
SS_KPI_SLOPE_TOL_PER_SEC = 1.0e-4
SS_MV_RATE_TOL_LBMOLPH_PER_SEC = 20.0
SS_GLOBAL_RATE_TOL_FRAC_FEED = 0.01
SS_RATE_DENOM_FLOOR_LBMOL = 1.0
SS_WINDOW_SEC = 30.0
SS_MIN_TIME_SEC = 60.0
FEED_TEMPERATURE_DISTURBANCE_MAX_NFEV_PER_ROOT = 160
_PARALLEL_WORKER_CONTEXT: dict[str, Any] | None = None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(type(value).__name__)


def _validated_timestep_sec(value: float) -> float:
    timestep = float(value)
    for validated in VALIDATED_TIMESTEPS_SEC:
        if abs(timestep - validated) <= 1.0e-12:
            return float(validated)
    choices = ", ".join(f"{item:g}" for item in VALIDATED_TIMESTEPS_SEC)
    raise ValueError(f"Core V3 timestep must be one of the validated values: {choices} s")


def _resolve_timestep_sec(
    requested: float | None,
    checkpoint_metadata: Mapping[str, Any],
) -> float:
    if requested is not None:
        return _validated_timestep_sec(requested)
    inherited = checkpoint_metadata.get("dt_sec", DEFAULT_TIMESTEP_SEC)
    return _validated_timestep_sec(float(inherited))


def _context(
    *,
    drum_level_kc: float | None = None,
    drum_level_ti_sec: float | None = None,
    regulatory_options: Mapping[str, Any] | None = None,
    feed_temperature_step_F: float = 0.0,
) -> dict[str, Any]:
    original = dd267._context()
    feed_step = float(feed_temperature_step_F)
    if not np.isfinite(feed_step):
        raise ValueError("Feed-temperature step must be finite")
    feed_disturbance: dict[str, Any] = {
        "active": False,
        "temperature_step_F": 0.0,
        "baseline_enthalpy_BTUph": float(
            original["balance_inputs"].feed_enthalpy_BTUph
        ),
        "disturbed_enthalpy_BTUph": float(
            original["balance_inputs"].feed_enthalpy_BTUph
        ),
    }
    if abs(feed_step) > 1.0e-15:
        source_mapping = dict(original["source"]["source_mapping"])
        feed_component = np.asarray(
            original["balance_inputs"].feed_component_lbmolph, dtype=float
        )
        feed_total = float(np.sum(feed_component))
        feed_composition = feed_component / feed_total
        baseline_temperature = float(source_mapping["feed_temperature_F"])
        disturbed_temperature = baseline_temperature + feed_step
        feed_pressure = float(source_mapping["feed_pressure_psia"])
        preparation_audit = ProviderCallAudit(provider_identity="dwsim")
        baseline_h = preparation_audit.phase_enthalpy(
            original["provider"], phase="liquid",
            temperature_F=baseline_temperature, pressure_psia=feed_pressure,
            composition=feed_composition, caller="core_v3_feed_disturbance",
            state_id="baseline_feed_enthalpy", evaluation_kind="preparation",
        )
        disturbed_h = preparation_audit.phase_enthalpy(
            original["provider"], phase="liquid",
            temperature_F=disturbed_temperature, pressure_psia=feed_pressure,
            composition=feed_composition, caller="core_v3_feed_disturbance",
            state_id="disturbed_feed_enthalpy", evaluation_kind="preparation",
        )
        baseline_enthalpy = feed_total * baseline_h
        disturbed_enthalpy = feed_total * disturbed_h
        existing_enthalpy = float(original["balance_inputs"].feed_enthalpy_BTUph)
        parity_error = abs(baseline_enthalpy - existing_enthalpy) / max(
            abs(existing_enthalpy), 1.0
        )
        if parity_error > 1.0e-10:
            raise RuntimeError(
                "Governed baseline feed enthalpy does not reproduce the Core V3 boundary"
            )
        original = {
            **original,
            "balance_inputs": replace(
                original["balance_inputs"],
                feed_enthalpy_BTUph=float(disturbed_enthalpy),
            ),
        }
        feed_disturbance = {
            "active": True,
            "temperature_step_F": feed_step,
            "baseline_temperature_F": baseline_temperature,
            "disturbed_temperature_F": disturbed_temperature,
            "pressure_psia": feed_pressure,
            "component_lbmolph": feed_component.tolist(),
            "composition": feed_composition.tolist(),
            "total_lbmolph": feed_total,
            "baseline_molar_enthalpy_BTU_lbmol": baseline_h,
            "disturbed_molar_enthalpy_BTU_lbmol": disturbed_h,
            "molar_enthalpy_delta_BTU_lbmol": disturbed_h - baseline_h,
            "baseline_enthalpy_BTUph": baseline_enthalpy,
            "disturbed_enthalpy_BTUph": disturbed_enthalpy,
            "enthalpy_delta_BTUph": disturbed_enthalpy - baseline_enthalpy,
            "baseline_boundary_parity_relative_error": parity_error,
            "provider": "dwsim_pr_liquid_phase_enthalpy",
        }
    contract = build_vapor_holdup_dynamic_pressure_contract(original["contract"])
    workbook_controllers = contract.controllers
    if drum_level_kc is not None or drum_level_ti_sec is not None:
        controllers = replace(
            contract.controllers,
            drum_kc=(
                float(drum_level_kc)
                if drum_level_kc is not None
                else contract.controllers.drum_kc
            ),
            drum_ti_sec=(
                float(drum_level_ti_sec)
                if drum_level_ti_sec is not None
                else contract.controllers.drum_ti_sec
            ),
        )
        if controllers.drum_kc <= 0.0 or controllers.drum_ti_sec <= 0.0:
            raise ValueError("Drum level-controller Kc and Ti must be positive")
        contract = replace(contract, controllers=controllers)
    regulatory_active = regulatory_options is not None
    if regulatory_active:
        options = dict(regulatory_options or {})
        duty_reference = float(options["condenser_duty_reference_BTUph"])
        reflux_reference = float(
            options.get("reflux_reference_lbmolph")
            or original["balance_inputs"].reflux_lbmolph
        )
        pressure_kc = options.get("pressure_kc_per_psia")
        if pressure_kc is None:
            pressure_kc = 300_000.0 / abs(duty_reference)
        composition_kc = options.get("composition_kc_per_molfrac")
        if composition_kc is None:
            composition_kc = 5_000.0 / reflux_reference
        regulatory = VaporHoldupRegulatoryControllerSpecification(
            pressure_setpoint_psia=float(options["pressure_setpoint_psia"]),
            pressure_kc_per_psia=float(pressure_kc),
            pressure_ti_sec=float(options.get("pressure_ti_sec", 180.0)),
            condenser_duty_reference_BTUph=duty_reference,
            condenser_duty_ratio_bounds=tuple(
                options.get("condenser_duty_ratio_bounds", (0.5, 1.5))
            ),
            composition_component=str(
                options.get("composition_component", "n-Butane")
            ),
            composition_setpoint_molfrac=float(
                options["composition_setpoint_molfrac"]
            ),
            composition_kc_per_molfrac=float(composition_kc),
            composition_ti_sec=float(options.get("composition_ti_sec", 600.0)),
            reflux_reference_lbmolph=reflux_reference,
            reflux_ratio_bounds=tuple(options.get("reflux_ratio_bounds", (0.5, 1.5))),
        )
        contract = build_vapor_holdup_regulatory_control_contract(contract, regulatory)
        audit = audit_vapor_holdup_regulatory_control_contract(contract)
    else:
        audit = audit_vapor_holdup_dynamic_pressure_contract(contract)
    if not audit.pass_gate:
        raise RuntimeError("Core V3 controlled structure failed its startup audit")
    return {
        **original,
        "contract": contract,
        "workbook_controllers": workbook_controllers,
        "regulatory_control_active": regulatory_active,
        "feed_temperature_disturbance": feed_disturbance,
    }


def _reference_arrays(reference: VaporHoldupImplicitReference) -> dict[str, np.ndarray]:
    return {
        "liquid_component_inventory_lbmol": reference.liquid_component_inventory_lbmol,
        "vapor_component_inventory_lbmol": reference.vapor_component_inventory_lbmol,
        "phase_transfer_lbmolph": reference.phase_transfer_lbmolph,
        "phase_transfer_scale_lbmolph": reference.phase_transfer_scale_lbmolph,
        "temperature_F": reference.temperature_F,
        "pressure_psia": reference.pressure_psia,
        "hydraulic_liquid_flow_lbmolph": reference.hydraulic_liquid_flow_lbmolph,
        "vapor_flow_lbmolph": reference.vapor_flow_lbmolph,
        "total_stored_energy_BTU": reference.total_stored_energy_BTU,
    }


def _reference_payload(reference: VaporHoldupImplicitReference) -> dict[str, Any]:
    return {
        **{
            name: np.asarray(value, dtype=float).tolist()
            for name, value in _reference_arrays(reference).items()
        },
        "condenser_duty_BTUph": float(reference.condenser_duty_BTUph),
    }


def _reference_from_payload(payload: Mapping[str, Any]) -> VaporHoldupImplicitReference:
    return VaporHoldupImplicitReference(
        liquid_component_inventory_lbmol=np.asarray(
            payload["liquid_component_inventory_lbmol"], dtype=float
        ),
        vapor_component_inventory_lbmol=np.asarray(
            payload["vapor_component_inventory_lbmol"], dtype=float
        ),
        phase_transfer_lbmolph=np.asarray(payload["phase_transfer_lbmolph"], dtype=float),
        phase_transfer_scale_lbmolph=np.asarray(
            payload["phase_transfer_scale_lbmolph"], dtype=float
        ),
        temperature_F=np.asarray(payload["temperature_F"], dtype=float),
        pressure_psia=np.asarray(payload["pressure_psia"], dtype=float),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            payload["hydraulic_liquid_flow_lbmolph"], dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(payload["vapor_flow_lbmolph"], dtype=float),
        condenser_duty_BTUph=float(payload["condenser_duty_BTUph"]),
        total_stored_energy_BTU=np.asarray(
            payload["total_stored_energy_BTU"], dtype=float
        ),
    )


def _parallel_worker_initialize(
    drum_level_kc: float | None = None,
    drum_level_ti_sec: float | None = None,
    regulatory_options: Mapping[str, Any] | None = None,
    feed_temperature_step_F: float = 0.0,
) -> None:
    global _PARALLEL_WORKER_CONTEXT
    context = _context(
        drum_level_kc=drum_level_kc,
        drum_level_ti_sec=drum_level_ti_sec,
        regulatory_options=regulatory_options,
        feed_temperature_step_F=feed_temperature_step_F,
    )
    provider = context["provider"]
    setter = getattr(provider, "set_exact_state_memoization", None)
    if callable(setter):
        setter(True, clear=True)
    _PARALLEL_WORKER_CONTEXT = {
        "context": context,
        "root_epoch": None,
        "reference": None,
        "memory": None,
        "timestep_sec": None,
        "specified_duty": None,
    }


def _parallel_worker_evaluate(work: Mapping[str, Any]) -> dict[str, Any]:
    if _PARALLEL_WORKER_CONTEXT is None:
        raise RuntimeError("Core V3 parallel worker is unavailable")
    worker = _PARALLEL_WORKER_CONTEXT
    epoch = str(work["root_epoch"])
    rebuilt = worker["root_epoch"] != epoch
    if rebuilt:
        worker["reference"] = _reference_from_payload(work["reference"])
        worker["memory"] = np.asarray(work["memory"], dtype=float)
        worker["timestep_sec"] = float(work["timestep_sec"])
        worker["specified_duty"] = float(work["specified_duty"])
        worker["root_epoch"] = epoch
        provider = worker["context"]["provider"]
        setter = getattr(provider, "set_exact_state_memoization", None)
        if callable(setter):
            setter(True, clear=True)
        worker["context"]["audit"] = ProviderCallAudit(
            provider_identity="dwsim",
            interface_provider_identities={"declared_liquid_density": "aligned_pr"},
        )
    task = work["task"]
    context = worker["context"]
    audit = context["audit"]
    before = audit.record_count
    if context.get("regulatory_control_active"):
        evaluation = evaluate_vapor_holdup_regulatory_control_implicit_residual(
            context["contract"], context["geometry"], worker["reference"],
            context["balance_inputs"], context["spec"].hydraulic_geometry,
            replace(context["numerical"], timestep_sec=worker["timestep_sec"]),
            context["provider"], context["audit"],
            np.asarray(task.coordinates, dtype=float),
            controller_memory_previous=worker["memory"],
            state_id=task.state_id, evaluation_kind="jacobian",
        )
    else:
        evaluation = dd274._evaluate(
            context, worker["reference"], worker["memory"],
            np.asarray(task.coordinates, dtype=float), worker["timestep_sec"],
            worker["specified_duty"], task.state_id,
        )
    provider_report = audit.report()
    return {
        "order": int(task.order),
        "residual": evaluation.scaled.tolist(),
        "process_id": int(os.getpid()),
        "method": str(work["method"]),
        "root_epoch": epoch,
        "basis_rebuilt": rebuilt,
        "logical_provider_calls": int(audit.record_count - before),
        "provider_pass": bool(provider_report["pass"]),
        "fallback_attempted": bool(provider_report["fallback_attempted"]),
    }


def _write_checkpoint(
    path: Path,
    *,
    workbook: Path,
    context: Mapping[str, Any],
    reference: VaporHoldupImplicitReference,
    controller_memory: np.ndarray,
    previous_coordinates: np.ndarray,
    controller_rate_per_sec: np.ndarray,
    product_log_ratio: np.ndarray,
    reflux_log_ratio: float = 0.0,
    jacobian_refresh_interval: int = 0,
    max_nfev_per_root: int = 40,
    composition_error_limit_molfrac: float | None = None,
    final_time_s: float,
    timestep_sec: float,
    source: str,
) -> Path:
    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    topology = context["contract"].base.topology.column
    regulatory = (
        context["contract"].regulatory
        if isinstance(context["contract"], VaporHoldupRegulatoryControlContract)
        else None
    )
    metadata = {
        "schema": SCHEMA,
        "model_id": MODEL_ID,
        "source": source,
        "workbook_path": str(workbook.resolve()),
        "workbook_sha256": _sha256(workbook.resolve()),
        "final_time_s": float(final_time_s),
        "dt_sec": _validated_timestep_sec(timestep_sec),
        "n_stages": len(topology.volume_ids),
        "n_components": len(context["contract"].base.component_names),
        "component_names": list(context["contract"].base.component_names),
        "volume_ids": list(topology.volume_ids),
        "specified_condenser_duty_BTUph": float(reference.condenser_duty_BTUph),
        "pressure_controller_active": regulatory is not None,
        "distillate_composition_controller_active": regulatory is not None,
        "terminal_level_controllers_active": True,
        "drum_level_kc": float(context["contract"].controllers.drum_kc),
        "drum_level_ti_sec": float(context["contract"].controllers.drum_ti_sec),
        "sump_level_kc": float(context["contract"].controllers.sump_kc),
        "sump_level_ti_sec": float(context["contract"].controllers.sump_ti_sec),
        "feed_temperature_step_F": float(
            context.get("feed_temperature_disturbance", {}).get(
                "temperature_step_F", 0.0
            )
        ),
        "feed_temperature_disturbance": dict(
            context.get("feed_temperature_disturbance", {})
        ),
        "jacobian_refresh_interval": int(jacobian_refresh_interval),
        "max_nfev_per_root": int(max_nfev_per_root),
        "composition_error_limit_molfrac": (
            None
            if composition_error_limit_molfrac is None
            else float(composition_error_limit_molfrac)
        ),
    }
    if regulatory is not None:
        metadata.update(
            {
                "pressure_setpoint_psia": regulatory.pressure_setpoint_psia,
                "pressure_kc_per_psia": regulatory.pressure_kc_per_psia,
                "pressure_ti_sec": regulatory.pressure_ti_sec,
                "condenser_duty_reference_BTUph": regulatory.condenser_duty_reference_BTUph,
                "condenser_duty_ratio_bounds": regulatory.condenser_duty_ratio_bounds,
                "composition_component": regulatory.composition_component,
                "composition_setpoint_molfrac": regulatory.composition_setpoint_molfrac,
                "composition_kc_per_molfrac": regulatory.composition_kc_per_molfrac,
                "composition_ti_sec": regulatory.composition_ti_sec,
                "reflux_reference_lbmolph": regulatory.reflux_reference_lbmolph,
                "reflux_ratio_bounds": regulatory.reflux_ratio_bounds,
            }
        )
    arrays = {
        **_reference_arrays(reference),
        "controller_memory": np.asarray(controller_memory, dtype=float),
        "previous_coordinates": np.asarray(previous_coordinates, dtype=float),
        "controller_rate_per_sec": np.asarray(controller_rate_per_sec, dtype=float),
        "product_log_ratio": np.asarray(product_log_ratio, dtype=float),
        "reflux_log_ratio": np.asarray(float(reflux_log_ratio)),
        "metadata_json": np.asarray(json.dumps(metadata, sort_keys=True, default=_json_default)),
    }
    temporary = destination.parent / f".core_v3_checkpoint_{os.getpid()}.tmp.npz"
    np.savez_compressed(temporary, **arrays)
    temporary.replace(destination)
    return destination


def _load_checkpoint(
    path: Path,
    *,
    workbook: Path,
    context: Mapping[str, Any],
) -> tuple[dict[str, Any], VaporHoldupImplicitReference, np.ndarray, np.ndarray, Any]:
    resolved = path.expanduser().resolve()
    with np.load(resolved, allow_pickle=False) as data:
        metadata = json.loads(str(data["metadata_json"].item()))
        arrays = {name: np.asarray(data[name], dtype=float).copy() for name in data.files if name != "metadata_json"}
    if metadata.get("schema") != SCHEMA or metadata.get("model_id") != MODEL_ID:
        raise ValueError("Checkpoint is not a reusable Core V3 dynamic-pressure checkpoint")
    if metadata.get("workbook_sha256") != _sha256(workbook.resolve()):
        raise ValueError("Checkpoint workbook does not match the selected Excel case")
    expected_components = list(context["contract"].base.component_names)
    if list(metadata.get("component_names") or []) != expected_components:
        raise ValueError("Checkpoint component order does not match Core V3")
    reference = VaporHoldupImplicitReference(
        liquid_component_inventory_lbmol=arrays["liquid_component_inventory_lbmol"],
        vapor_component_inventory_lbmol=arrays["vapor_component_inventory_lbmol"],
        phase_transfer_lbmolph=arrays["phase_transfer_lbmolph"],
        phase_transfer_scale_lbmolph=arrays["phase_transfer_scale_lbmolph"],
        temperature_F=arrays["temperature_F"],
        pressure_psia=arrays["pressure_psia"],
        hydraulic_liquid_flow_lbmolph=arrays["hydraulic_liquid_flow_lbmolph"],
        vapor_flow_lbmolph=arrays["vapor_flow_lbmolph"],
        condenser_duty_BTUph=float(metadata["specified_condenser_duty_BTUph"]),
        total_stored_energy_BTU=arrays["total_stored_energy_BTU"],
    )
    prior = SimpleNamespace(
        controller_rate_per_sec=arrays["controller_rate_per_sec"],
        product_log_ratio=arrays["product_log_ratio"],
        reflux_log_ratio=float(arrays.get("reflux_log_ratio", np.asarray(0.0))),
    )
    return metadata, reference, arrays["controller_memory"], arrays["previous_coordinates"], prior


def _peek_checkpoint_metadata(path: Path) -> dict[str, Any]:
    with np.load(path.expanduser().resolve(), allow_pickle=False) as data:
        return json.loads(str(data["metadata_json"].item()))


def _regulatory_options_from_checkpoint(
    path: Path,
    metadata: Mapping[str, Any],
    *,
    pressure_setpoint_psia: float | None = None,
    pressure_kc_BTUph_per_psia: float | None = None,
    pressure_ti_sec: float | None = None,
    composition_component: str | None = None,
    composition_setpoint_molfrac: float | None = None,
    composition_kc_lbmolph_per_molfrac: float | None = None,
    composition_ti_sec: float | None = None,
) -> dict[str, Any]:
    with np.load(path.expanduser().resolve(), allow_pickle=False) as data:
        pressure_now = float(np.asarray(data["pressure_psia"], dtype=float)[0])
        liquid_now = np.asarray(data["liquid_component_inventory_lbmol"], dtype=float)[0]
    names = list(metadata["component_names"])
    component = str(
        composition_component or metadata.get("composition_component") or "n-Butane"
    )
    if component not in names:
        raise ValueError(f"Composition-control component is not in Core V3: {component}")
    composition_now = float(liquid_now[names.index(component)] / np.sum(liquid_now))
    duty_reference = float(
        metadata.get("condenser_duty_reference_BTUph")
        or metadata["specified_condenser_duty_BTUph"]
    )
    reflux_reference = metadata.get("reflux_reference_lbmolph")
    pressure_kc = metadata.get("pressure_kc_per_psia")
    if pressure_kc_BTUph_per_psia is not None:
        pressure_kc = float(pressure_kc_BTUph_per_psia) / abs(duty_reference)
    composition_kc = metadata.get("composition_kc_per_molfrac")
    if composition_kc_lbmolph_per_molfrac is not None:
        if reflux_reference is None:
            reflux_reference = 5952.48
        composition_kc = (
            float(composition_kc_lbmolph_per_molfrac) / float(reflux_reference)
        )
    return {
        "pressure_setpoint_psia": float(
            pressure_setpoint_psia
            if pressure_setpoint_psia is not None
            else metadata.get("pressure_setpoint_psia", pressure_now)
        ),
        "pressure_kc_per_psia": pressure_kc,
        "pressure_ti_sec": float(
            pressure_ti_sec
            if pressure_ti_sec is not None
            else metadata.get("pressure_ti_sec", 180.0)
        ),
        "condenser_duty_reference_BTUph": duty_reference,
        "condenser_duty_ratio_bounds": tuple(
            metadata.get("condenser_duty_ratio_bounds", (0.5, 1.5))
        ),
        "composition_component": component,
        "composition_setpoint_molfrac": float(
            composition_setpoint_molfrac
            if composition_setpoint_molfrac is not None
            else metadata.get("composition_setpoint_molfrac", composition_now)
        ),
        "composition_kc_per_molfrac": composition_kc,
        "composition_ti_sec": float(
            composition_ti_sec
            if composition_ti_sec is not None
            else metadata.get("composition_ti_sec", 600.0)
        ),
        "reflux_reference_lbmolph": reflux_reference,
        "reflux_ratio_bounds": tuple(metadata.get("reflux_ratio_bounds", (0.5, 1.5))),
    }


def _bumpless_controller_memory(
    *,
    product_log_ratio: np.ndarray,
    level_fraction: np.ndarray,
    controllers: Any,
) -> np.ndarray:
    gains = np.asarray((controllers.drum_kc, controllers.sump_kc), dtype=float)
    setpoints = np.asarray(
        (
            controllers.drum_level_setpoint_fraction,
            controllers.sump_level_setpoint_fraction,
        ),
        dtype=float,
    )
    logs = np.asarray(product_log_ratio, dtype=float).reshape((2,))
    levels = np.asarray(level_fraction, dtype=float).reshape((2,))
    return logs - gains * (levels - setpoints)


def _bumpless_regulatory_state(
    *,
    controller_memory: np.ndarray,
    controller_rates_per_sec: np.ndarray,
    pressure_error_psia: float,
    condenser_duty_log_ratio: float,
    pressure_kc_per_psia: float,
    pressure_ti_sec: float,
    composition_error_molfrac: float,
    reflux_log_ratio: float,
    composition_kc_per_molfrac: float,
    composition_ti_sec: float,
) -> tuple[np.ndarray, np.ndarray]:
    memory = np.asarray(controller_memory, dtype=float).reshape((4,)).copy()
    rates = np.asarray(controller_rates_per_sec, dtype=float).reshape((4,)).copy()
    memory[2] = (
        float(condenser_duty_log_ratio)
        - float(pressure_kc_per_psia) * float(pressure_error_psia)
    )
    memory[3] = (
        float(reflux_log_ratio)
        - float(composition_kc_per_molfrac) * float(composition_error_molfrac)
    )
    rates[2] = (
        float(pressure_kc_per_psia)
        * float(pressure_error_psia)
        / float(pressure_ti_sec)
    )
    rates[3] = (
        float(composition_kc_per_molfrac)
        * float(composition_error_molfrac)
        / float(composition_ti_sec)
    )
    if np.any(~np.isfinite(memory)) or np.any(~np.isfinite(rates)):
        raise ValueError("bumpless regulatory state is not finite")
    return memory, rates


def _reference_level_fractions(
    context: Mapping[str, Any],
    reference: VaporHoldupImplicitReference,
) -> np.ndarray:
    liquid = np.asarray(reference.liquid_component_inventory_lbmol, dtype=float)
    composition = liquid / np.sum(liquid, axis=1, keepdims=True)
    density = np.asarray(
        [
            context["provider"].liquid_density_lbmol_ft3(
                float(reference.temperature_F[index]),
                float(reference.pressure_psia[index]),
                composition[index].tolist(),
            )
            for index in range(liquid.shape[0])
        ],
        dtype=float,
    )
    if np.any(~np.isfinite(density)) or np.any(density <= 0.0):
        raise RuntimeError("Cannot reconstruct terminal levels for bumpless controller retuning")
    return terminal_level_fractions(liquid, density, context["contract"].geometry)


def export_dd274_checkpoint(workbook: Path, output: Path) -> Path:
    workbook = workbook.expanduser().resolve()
    result = json.loads((ROOT / dd274.RESULT).read_text(encoding="utf-8"))
    if not result.get("pass_gate"):
        raise RuntimeError("The accepted DD-274 result is unavailable")
    original = dd267._context()
    replay = dd273._replay(original)
    contract = build_vapor_holdup_dynamic_pressure_contract(original["contract"])
    context = {**original, "contract": contract}
    with np.load(ROOT / dd274.EVIDENCE, allow_pickle=False) as evidence:
        coordinates = np.asarray(evidence["nominal_coordinates"], dtype=float)
        memories = np.asarray(evidence["nominal_controller_memory"], dtype=float)
    reference = replay["reference"]
    memory = replay["memory"]
    final = None
    for index, point in enumerate(coordinates):
        final = dd274._evaluate(
            context,
            reference,
            memory,
            point,
            0.25,
            float(result["specified_condenser_duty_BTUph"]),
            f"core_v3_checkpoint:dd274_replay_{index + 1}",
            "residual",
        )
        if np.max(np.abs(final.controller_memory_endpoint - memories[index])) > 1.0e-10:
            raise RuntimeError("DD-274 controller memory replay failed")
        reference = dd249._next_reference(reference, final.base)
        memory = final.controller_memory_endpoint.copy()
    if final is None:
        raise RuntimeError("DD-274 evidence contains no endpoints")
    saved = result["nominal_endpoints"][-1]
    parity = max(
        abs(final.distillate_lbmolph - float(saved["distillate_lbmolph"])),
        abs(final.bottoms_lbmolph - float(saved["bottoms_lbmolph"])),
        float(np.max(np.abs(final.level_fraction - np.asarray(saved["level_fraction"], dtype=float)))),
    )
    if parity > 1.0e-8:
        raise RuntimeError(f"DD-274 checkpoint replay parity failed: {parity}")
    return _write_checkpoint(
        output,
        workbook=workbook,
        context=context,
        reference=reference,
        controller_memory=memory,
        previous_coordinates=coordinates[-1],
        controller_rate_per_sec=final.controller_rate_per_sec,
        product_log_ratio=final.product_log_ratio,
        final_time_s=60.0,
        timestep_sec=DEFAULT_TIMESTEP_SEC,
        source="accepted DD-274 endpoint (DD-271 30 s handoff plus DD-274 30 s continuation)",
    )


def _summary_row(
    context: Mapping[str, Any],
    evaluation: Any,
    *,
    time_s: float,
    wall_elapsed_s: float,
    report: Mapping[str, Any],
    steady: Mapping[str, Any],
) -> dict[str, Any]:
    endpoint = evaluation.base.endpoint
    liquid = endpoint.liquid_component_inventory_lbmol
    top_x = liquid[0] / np.sum(liquid[0])
    bottom_x = liquid[-1] / np.sum(liquid[-1])
    components = list(context["contract"].base.component_names)
    row: dict[str, Any] = {
        "time_s": float(time_s),
        "wall_elapsed_s": float(wall_elapsed_s),
        "steady_state_score": float(steady["steady_state_score"]),
        "steady_state_flag": float(steady["steady_state_flag"]),
        "ss_max_rel_state_rate_per_s": float(steady["ss_max_rel_state_rate_per_s"]),
        "ss_max_temp_rate_F_per_s": float(steady["ss_max_temp_rate_F_per_s"]),
        "ss_max_kpi_slope_per_s": float(steady["ss_max_kpi_slope_per_s"]),
        "ss_max_mv_rate_per_s": float(steady["ss_max_mv_rate_per_s"]),
        "ss_global_inventory_rate_frac_feed": float(steady["ss_global_inventory_rate_frac_feed"]),
        "Q_cond_used_BTUph": float(endpoint.condenser_duty_BTUph),
        "Q_reb_used_BTUph": float(context["balance_inputs"].reboiler_duty_BTUph),
        "Reflux_cmd_lbmolph": float(
            getattr(evaluation, "reflux_lbmolph", context["spec"].reflux_lbmolph)
        ),
        "Boilup_lbmolph": float(endpoint.vapor_flow_lbmolph[-1]),
        "D_lbmolph": float(evaluation.distillate_lbmolph),
        "B_lbmolph": float(evaluation.bottoms_lbmolph),
        "Top_level_ctrl_pv": float(evaluation.level_fraction[0]),
        "Bottom_level_fraction": float(evaluation.level_fraction[1]),
        "P_top_drum_psia": float(endpoint.pressure_psia[0]),
        "T_Distillate_F": float(endpoint.temperature_F[0]),
        "T_sump_F": float(endpoint.temperature_F[-1]),
        "scaled_residual_inf_norm": float(report["scaled_residual_inf_norm"]),
        "jacobian_condition": float(report["jacobian_condition"]),
        "root_wall_s": float(report.get("root_wall_s", np.nan)),
        "root_objective_calls": float(report.get("function_calls_observed", np.nan)),
        "root_nfev": float(report.get("nfev", np.nan)),
        "root_njev": float(report.get("njev", np.nan)),
        "root_jacobian_builds": float(report.get("jacobian_build_count", np.nan)),
        "root_color_count": float(report.get("color_count", np.nan)),
        "root_memo_hits": float(report.get("memo_hits_delta", np.nan)),
        "root_memo_misses": float(report.get("memo_misses_delta", np.nan)),
        "root_memo_hit_fraction": float(report.get("memo_hit_fraction", np.nan)),
    }
    feed_disturbance = dict(context.get("feed_temperature_disturbance", {}))
    row.update(
        {
            "Feed_temperature_step_F": float(
                feed_disturbance.get("temperature_step_F", 0.0)
            ),
            "Feed_temperature_F": float(
                feed_disturbance.get("disturbed_temperature_F", np.nan)
            ),
                "Feed_enthalpy_BTUph": float(
                    getattr(context["balance_inputs"], "feed_enthalpy_BTUph", np.nan)
                ),
            "Feed_enthalpy_delta_BTUph": float(
                feed_disturbance.get("enthalpy_delta_BTUph", 0.0)
            ),
        }
    )
    if hasattr(evaluation, "pressure_error_psia"):
        row.update(
            {
                "Pressure_ctrl_SP_psia": float(
                    context["contract"].regulatory.pressure_setpoint_psia
                ),
                "Pressure_ctrl_error_psia": float(evaluation.pressure_error_psia),
                "Composition_ctrl_component": context["contract"].regulatory.composition_component,
                "Composition_ctrl_SP_molfrac": float(
                    context["contract"].regulatory.composition_setpoint_molfrac
                ),
                "Composition_ctrl_PV_molfrac": float(evaluation.composition_molfrac),
                "Composition_ctrl_error_molfrac": float(
                    evaluation.composition_error_molfrac
                ),
            }
        )
    for index, component in enumerate(components):
        row[f"Distillate_x_{component}"] = float(top_x[index])
        row[f"Bottoms_x_{component}"] = float(bottom_x[index])
    return row


def _memo_snapshot(provider: Any) -> dict[str, int]:
    getter = getattr(provider, "get_exact_state_memoization_stats", None)
    if not callable(getter):
        return {"hits": 0, "misses": 0, "entries": 0}
    stats = getter()
    families = dict(stats.get("families", {}) or {})
    return {
        "hits": int(stats.get("hits", 0) or 0),
        "misses": int(stats.get("misses", 0) or 0),
        "entries": int(
            sum(int(dict(item).get("entries", 0) or 0) for item in families.values())
        ),
    }


def _memo_delta(before: Mapping[str, int], after: Mapping[str, int]) -> dict[str, float]:
    hits = max(int(after.get("hits", 0)) - int(before.get("hits", 0)), 0)
    misses = max(int(after.get("misses", 0)) - int(before.get("misses", 0)), 0)
    requests = hits + misses
    return {
        "memo_hits_delta": hits,
        "memo_misses_delta": misses,
        "memo_hit_fraction": float(hits / requests) if requests else 0.0,
    }


def _composition_quality_pass(
    error_molfrac: float,
    limit_molfrac: float | None,
) -> bool:
    if limit_molfrac is None:
        return True
    limit = float(limit_molfrac)
    if not np.isfinite(limit) or limit <= 0.0:
        raise ValueError("composition error limit must be positive when declared")
    return abs(float(error_molfrac)) < limit


def _linear_slope(times: list[float], values: list[float]) -> float:
    x = np.asarray(times, dtype=float)
    y = np.asarray(values, dtype=float)
    finite = np.isfinite(x) & np.isfinite(y)
    if np.count_nonzero(finite) < 2:
        return 0.0
    x = x[finite]
    y = y[finite]
    centered = x - float(np.mean(x))
    denominator = float(np.dot(centered, centered))
    if denominator <= 0.0:
        return 0.0
    return float(np.dot(centered, y - float(np.mean(y))) / denominator)


def _steady_state_metrics(
    context: Mapping[str, Any],
    previous: VaporHoldupImplicitReference,
    evaluation: Any,
    *,
    interval_sec: float,
    time_s: float,
    history: list[dict[str, Any]],
) -> dict[str, float]:
    endpoint = evaluation.base.endpoint
    dt = float(interval_sec)
    if not np.isfinite(dt) or dt <= 0.0:
        raise ValueError("steady-state scoring interval must be positive")

    relative_rates = []
    for before, after in (
        (previous.liquid_component_inventory_lbmol, endpoint.liquid_component_inventory_lbmol),
        (previous.vapor_component_inventory_lbmol, endpoint.vapor_component_inventory_lbmol),
    ):
        rate_per_sec = (np.asarray(after) - np.asarray(before)) / dt
        relative_rates.append(
            np.abs(rate_per_sec)
            / (np.abs(np.asarray(after)) + SS_RATE_DENOM_FLOOR_LBMOL)
        )
    max_relative_rate = float(max(np.max(block) for block in relative_rates))
    max_temperature_rate = float(
        np.max(
            np.abs(
                (endpoint.temperature_F - previous.temperature_F) / dt
            )
        )
    )
    total_before = float(
        np.sum(previous.liquid_component_inventory_lbmol)
        + np.sum(previous.vapor_component_inventory_lbmol)
    )
    total_after = float(
        np.sum(endpoint.liquid_component_inventory_lbmol)
        + np.sum(endpoint.vapor_component_inventory_lbmol)
    )
    feed_rate = float(np.sum(context["spec"].feed_component_lbmolph))
    global_rate_fraction = abs((total_after - total_before) * 3600.0 / dt) / max(feed_rate, 1.0e-300)

    liquid = endpoint.liquid_component_inventory_lbmol
    top_x = liquid[0] / np.sum(liquid[0])
    bottom_x = liquid[-1] / np.sum(liquid[-1])
    history.append(
        {
            "time_s": float(time_s),
            "top_x": np.asarray(top_x, dtype=float).copy(),
            "bottom_x": np.asarray(bottom_x, dtype=float).copy(),
            "distillate_lbmolph": float(evaluation.distillate_lbmolph),
            "bottoms_lbmolph": float(evaluation.bottoms_lbmolph),
        }
    )
    history[:] = [
        item for item in history
        if float(time_s) - float(item["time_s"]) <= SS_WINDOW_SEC + 1.0e-12
    ]
    times = [float(item["time_s"]) for item in history]
    composition_slopes = []
    component_count = len(context["contract"].base.component_names)
    for component in range(component_count):
        composition_slopes.append(
            abs(_linear_slope(times, [float(item["top_x"][component]) for item in history]))
        )
        composition_slopes.append(
            abs(_linear_slope(times, [float(item["bottom_x"][component]) for item in history]))
        )
    max_kpi_slope = float(max(composition_slopes, default=0.0))
    max_mv_rate = float(
        max(
            abs(_linear_slope(times, [float(item["distillate_lbmolph"]) for item in history])),
            abs(_linear_slope(times, [float(item["bottoms_lbmolph"]) for item in history])),
        )
    )
    score = float(
        max(
            max_relative_rate / SS_REL_RATE_TOL_PER_SEC,
            max_temperature_rate / SS_TEMP_RATE_TOL_F_PER_SEC,
            max_kpi_slope / SS_KPI_SLOPE_TOL_PER_SEC,
            max_mv_rate / SS_MV_RATE_TOL_LBMOLPH_PER_SEC,
            global_rate_fraction / SS_GLOBAL_RATE_TOL_FRAC_FEED,
        )
    )
    return {
        "steady_state_score": score,
        "steady_state_flag": 1.0 if float(time_s) >= SS_MIN_TIME_SEC and score <= 1.0 else 0.0,
        "ss_max_rel_state_rate_per_s": max_relative_rate,
        "ss_max_temp_rate_F_per_s": max_temperature_rate,
        "ss_max_kpi_slope_per_s": max_kpi_slope,
        "ss_max_mv_rate_per_s": max_mv_rate,
        "ss_global_inventory_rate_frac_feed": global_rate_fraction,
    }


def _profile_rows(context: Mapping[str, Any], evaluation: Any, *, time_s: float) -> list[dict[str, Any]]:
    rows = dd267._profile(context, evaluation)
    components = list(context["contract"].base.component_names)
    output = []
    for stage, item in enumerate(rows, start=1):
        volume = str(item["volume"])
        row: dict[str, Any] = {
            "time_s": float(time_s),
            "stage": stage,
            "volume": volume,
            "node_type": (
                "reflux_drum"
                if stage == 1
                else ("reboiler_sump" if stage == len(rows) else "tray")
            ),
            "T_F": item["temperature_F"],
            "P_psia_hyd": item["pressure_psia"],
            "ML_lbmol": item["liquid_inventory_lbmol"],
            "MV_lbmol": item["vapor_inventory_lbmol"],
            "L_out_used_lbmolph": item["liquid_flow_lbmolph"],
            "V_out_lbmolph": item["vapor_flow_lbmolph"],
        }
        for index, component in enumerate(components):
            row[f"x_{component}"] = item["liquid_mole_fraction"][index]
            row[f"y_{component}"] = item["vapor_mole_fraction"][index]
        output.append(row)
    return output


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _requested_total_steps(control_path: Path, current: int) -> int:
    if not control_path.exists():
        return int(current)
    try:
        payload = json.loads(control_path.read_text(encoding="utf-8"))
        requested = int(payload.get("requested_total_steps", current))
    except Exception:
        return int(current)
    return max(int(current), requested)


def backfill_run_logs(*, workbook: Path, checkpoint: Path, logs_dir: Path) -> Path:
    workbook = workbook.expanduser().resolve()
    logs_dir = logs_dir.expanduser().resolve()
    summary_matches = sorted(logs_dir.glob("column_summary_*.csv"))
    profile_matches = sorted(logs_dir.glob("column_profile_*.csv"))
    if not summary_matches or not profile_matches:
        raise ValueError("Core V3 run directory is missing summary or profile CSV data")
    summary_path = summary_matches[-1]
    profile_path = profile_matches[-1]
    with summary_path.open("r", newline="", encoding="utf-8") as stream:
        summary_rows = list(csv.DictReader(stream))
    with profile_path.open("r", newline="", encoding="utf-8") as stream:
        profile_rows = list(csv.DictReader(stream))
    if not summary_rows or not profile_rows:
        raise ValueError("Core V3 run CSV data is empty")

    context = _context()
    _metadata, reference, _memory, _coordinates, prior = _load_checkpoint(
        checkpoint, workbook=workbook, context=context
    )
    initial_liquid = reference.liquid_component_inventory_lbmol
    initial_products = np.asarray(
        (
            float(context["balance_inputs"].distillate_lbmolph) * np.exp(prior.product_log_ratio[0]),
            float(context["balance_inputs"].bottoms_lbmolph) * np.exp(prior.product_log_ratio[1]),
        ),
        dtype=float,
    )
    history: list[dict[str, Any]] = [
        {
            "time_s": 0.0,
            "top_x": initial_liquid[0] / np.sum(initial_liquid[0]),
            "bottom_x": initial_liquid[-1] / np.sum(initial_liquid[-1]),
            "distillate_lbmolph": float(initial_products[0]),
            "bottoms_lbmolph": float(initial_products[1]),
        }
    ]
    profiles_by_time: dict[float, list[dict[str, str]]] = {}
    for row in profile_rows:
        profiles_by_time.setdefault(float(row["time_s"]), []).append(row)
    previous: Any = reference
    previous_time = 0.0
    components = list(context["contract"].base.component_names)
    for summary in summary_rows:
        time_s = float(summary["time_s"])
        stage_rows = sorted(profiles_by_time[time_s], key=lambda item: int(item["stage"]))
        liquid_total = np.asarray([float(item["ML_lbmol"]) for item in stage_rows])
        vapor_total = np.asarray([float(item["MV_lbmol"]) for item in stage_rows])
        liquid_x = np.asarray(
            [[float(item[f"x_{component}"]) for component in components] for item in stage_rows]
        )
        vapor_y = np.asarray(
            [[float(item[f"y_{component}"]) for component in components] for item in stage_rows]
        )
        vapor_flow = np.asarray(
            [float(item["V_out_lbmolph"]) if item["V_out_lbmolph"] else np.nan for item in stage_rows]
        )
        endpoint = SimpleNamespace(
            liquid_component_inventory_lbmol=liquid_total[:, None] * liquid_x,
            vapor_component_inventory_lbmol=vapor_total[:, None] * vapor_y,
            temperature_F=np.asarray([float(item["T_F"]) for item in stage_rows]),
            vapor_flow_lbmolph=vapor_flow,
        )
        evaluation = SimpleNamespace(
            base=SimpleNamespace(endpoint=endpoint),
            distillate_lbmolph=float(summary["D_lbmolph"]),
            bottoms_lbmolph=float(summary["B_lbmolph"]),
        )
        steady = _steady_state_metrics(
            context,
            previous,
            evaluation,
            interval_sec=time_s - previous_time,
            time_s=time_s,
            history=history,
        )
        summary.update({key: str(value) for key, value in steady.items()})
        summary["Reflux_cmd_lbmolph"] = str(float(context["spec"].reflux_lbmolph))
        finite_vapor = vapor_flow[np.isfinite(vapor_flow)]
        summary["Boilup_lbmolph"] = str(float(finite_vapor[-1])) if finite_vapor.size else "nan"
        previous = endpoint
        previous_time = time_s
    _write_csv(summary_path, summary_rows)
    final_time = float(summary_rows[-1]["time_s"])
    run_id = summary_path.stem.removeprefix("column_summary_")
    metadata_path = logs_dir / f"run_metadata_{run_id}.json"
    if not metadata_path.exists():
        metadata_path.write_text(
            json.dumps(
                {
                    "schema": "dynamic_distillation.core_v3_run_metadata.v1",
                    "status": "failed",
                    "run_id": run_id,
                    "failure_reason": (
                        "Trajectory completed, but the original runner failed while writing an "
                        "overlong checkpoint filename; reporting was backfilled afterward."
                    ),
                    "excel_path": str(workbook),
                    "started_from_checkpoint": str(checkpoint),
                    "duration_sec": final_time,
                    "dt_sec": _resolve_timestep_sec(None, _metadata),
                    "n_steps": int(
                        round(final_time / _resolve_timestep_sec(None, _metadata))
                    ),
                    "final_time_s": final_time,
                    "summary_csv": str(summary_path),
                    "profile_csv": str(profile_path),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return summary_path


def _solve_endpoint_parallel(
    context: Mapping[str, Any],
    payload: Mapping[str, Any],
    reference: Any,
    memory: np.ndarray,
    previous_coordinates: np.ndarray,
    previous_evaluation: Any,
    timestep_sec: float,
    specified_duty: float,
    root_name: str,
    jacobians: PersistentParallelColoredJacobian,
    jacobian_refresh_interval: int = 0,
    composition_error_limit_molfrac: float | None = None,
):
    regulatory_active = bool(context.get("regulatory_control_active"))
    if regulatory_active:
        lower, upper = regulatory_control_bounds(context["contract"], reference)
        point = regulatory_control_initial_coordinates(
            context["contract"],
            controller_rates_per_sec=previous_evaluation.controller_rate_per_sec,
            timestep_sec=timestep_sec,
            previous_coordinates=previous_coordinates,
            product_log_ratios_previous=previous_evaluation.product_log_ratio,
            reflux_log_ratio_previous=previous_evaluation.reflux_log_ratio,
        )
    else:
        lower, upper = dd267.dd265._bounds(context["contract"])
        point = dd274.controlled_implicit_initial_coordinates(
            context["contract"],
            controller_rates_per_sec=previous_evaluation.controller_rate_per_sec,
            timestep_sec=timestep_sec,
            previous_coordinates=previous_coordinates,
            product_log_ratios_previous=previous_evaluation.product_log_ratio,
        )
    cached_matrix: np.ndarray | None = None
    calls = 0
    jacobian_calls = 0
    evidence_start = len(jacobians.evidence)

    def objective(candidate: np.ndarray, state_id: str = "residual") -> np.ndarray:
        nonlocal calls
        calls += 1
        if regulatory_active:
            return evaluate_vapor_holdup_regulatory_control_implicit_residual(
                context["contract"], context["geometry"], reference,
                context["balance_inputs"], context["spec"].hydraulic_geometry,
                replace(context["numerical"], timestep_sec=timestep_sec),
                context["provider"], context["audit"], candidate,
                controller_memory_previous=memory,
                state_id=f"{root_name}:{state_id}:{calls}",
                evaluation_kind="jacobian",
            ).scaled
        return dd274._evaluate(
            context, reference, memory, candidate, timestep_sec, specified_duty,
            f"{root_name}:{state_id}:{calls}",
        ).scaled

    def jacobian(candidate: np.ndarray) -> np.ndarray:
        nonlocal cached_matrix, jacobian_calls
        refresh = bool(
            cached_matrix is None
            or (
                int(jacobian_refresh_interval) > 0
                and jacobian_calls > 0
                and jacobian_calls % int(jacobian_refresh_interval) == 0
            )
        )
        jacobian_calls += 1
        if refresh:
            cached_matrix = jacobians.build(
                candidate,
                f"{root_name}:jacobian:{jacobian_calls}",
                method="backward_euler",
                root_epoch=root_name,
                work_basis={
                    "reference": _reference_payload(reference),
                    "memory": np.asarray(memory, dtype=float).tolist(),
                    "timestep_sec": float(timestep_sec),
                    "specified_duty": float(specified_duty),
                },
            )
        return cached_matrix

    solution = least_squares(
        objective,
        point,
        jac=jacobian,
        bounds=(lower, upper),
        method="trf",
        x_scale=float(payload["solver"]["x_scale"]),
        ftol=float(payload["solver"]["ftol"]),
        xtol=float(payload["solver"]["xtol"]),
        gtol=float(payload["solver"]["gtol"]),
        max_nfev=int(payload["solver"]["max_nfev_per_root"]),
        verbose=0,
    )
    if regulatory_active:
        final = evaluate_vapor_holdup_regulatory_control_implicit_residual(
            context["contract"], context["geometry"], reference,
            context["balance_inputs"], context["spec"].hydraulic_geometry,
            replace(context["numerical"], timestep_sec=timestep_sec),
            context["provider"], context["audit"], solution.x,
            controller_memory_previous=memory,
            state_id=f"{root_name}:accepted", evaluation_kind="residual",
        )
    else:
        final = dd274._evaluate(
            context, reference, memory, solution.x, timestep_sec, specified_duty,
            f"{root_name}:accepted", "residual",
        )
    if cached_matrix is None:
        raise RuntimeError("Core V3 parallel root did not build its required Jacobian")
    rank, condition, _ = dd249._rank_condition(cached_matrix)
    memory_error = float(
        np.max(
            np.abs(
                final.controller_memory_endpoint
                - memory
                - timestep_sec * final.controller_rate_per_sec
            )
        )
    )
    endpoint = final.base.endpoint
    topology = context["contract"].base.topology.column
    top = topology.top_volume
    top_tray = next(
        source for source, destination, _name in topology.vapor_links if destination == top
    )
    top_index = topology.volume_ids.index(top)
    tray_index = topology.volume_ids.index(top_tray)
    root_evidence = jacobians.evidence[evidence_start:]
    if not root_evidence:
        raise RuntimeError("Core V3 parallel root produced no Jacobian evidence")
    evidence = root_evidence[-1]
    task_count = int(sum(item.task_count for item in root_evidence))
    worker_ids = sorted(
        {worker for item in root_evidence for worker in item.worker_ids}
    )
    duty_error = (
        np.nan
        if regulatory_active
        else abs(endpoint.condenser_duty_BTUph / specified_duty - 1.0)
    )
    controller_rows = [
        index for index, row in enumerate(context["contract"].rows)
        if "controller" in row.block
    ]
    if regulatory_active:
        regulatory_spec = context["contract"].regulatory
        condenser_duty_ratio = abs(float(endpoint.condenser_duty_BTUph)) / abs(
            float(regulatory_spec.condenser_duty_reference_BTUph)
        )
        reflux_ratio = float(final.reflux_lbmolph) / float(
            regulatory_spec.reflux_reference_lbmolph
        )
        pressure_quality_pass = abs(float(final.pressure_error_psia)) < 0.5
        composition_quality_pass = _composition_quality_pass(
            float(final.composition_error_molfrac),
            composition_error_limit_molfrac,
        )
        level_quality_pass = bool(
            np.all(np.asarray(final.level_fraction) > 0.45)
            and np.all(np.asarray(final.level_fraction) < 0.55)
        )
        mv_quality_pass = bool(
            regulatory_spec.condenser_duty_ratio_bounds[0] < condenser_duty_ratio
            < regulatory_spec.condenser_duty_ratio_bounds[1]
            and regulatory_spec.reflux_ratio_bounds[0] < reflux_ratio
            < regulatory_spec.reflux_ratio_bounds[1]
        )
    else:
        condenser_duty_ratio = np.nan
        reflux_ratio = np.nan
        pressure_quality_pass = True
        composition_quality_pass = True
        level_quality_pass = True
        mv_quality_pass = True
    variable_names = tuple(final.variable_names)
    bound_tolerance = 1.0e-8
    active_lower = [
        variable_names[index]
        for index in np.flatnonzero(solution.x - lower <= bound_tolerance)
    ]
    active_upper = [
        variable_names[index]
        for index in np.flatnonzero(upper - solution.x <= bound_tolerance)
    ]
    residual_order = np.argsort(np.abs(final.scaled))[::-1]
    dominant_residuals = [
        {
            "row": final.row_names[index],
            "scaled_residual": float(final.scaled[index]),
        }
        for index in residual_order[:10]
    ]
    bound_slack_order = np.argsort(
        np.minimum(solution.x - lower, upper - solution.x)
    )
    nearest_bounds = [
        {
            "variable": variable_names[index],
            "side": (
                "lower"
                if solution.x[index] - lower[index]
                <= upper[index] - solution.x[index]
                else "upper"
            ),
            "slack": float(
                min(
                    solution.x[index] - lower[index],
                    upper[index] - solution.x[index],
                )
            ),
            "value": float(solution.x[index]),
            "lower": float(lower[index]),
            "upper": float(upper[index]),
        }
        for index in bound_slack_order[:10]
    ]
    report = {
        "scipy_success": bool(solution.success),
        "scipy_status": int(solution.status),
        "scipy_message": str(solution.message),
        "scipy_optimality": float(solution.optimality),
        "scipy_cost": float(solution.cost),
        "nfev": int(solution.nfev),
        "njev": int(solution.njev or 0),
        "function_calls_observed": int(calls + task_count),
        "main_process_function_calls": int(calls),
        "parallel_jacobian_evaluations": task_count,
        "jacobian_build_count": len(root_evidence),
        "jacobian_refresh_interval": int(jacobian_refresh_interval),
        "active_lower_bounds": active_lower,
        "active_upper_bounds": active_upper,
        "nearest_bounds": nearest_bounds,
        "dominant_residuals": dominant_residuals,
        "color_count": int(evidence.color_count),
        "scaled_residual_inf_norm": float(np.max(np.abs(final.scaled))),
        "controller_residual_inf_norm": float(
            np.max(np.abs(final.scaled[controller_rows]))
        ),
        "jacobian_rank": int(rank),
        "jacobian_condition": float(condition),
        "physical_pass": bool(dd267._physical(final)),
        "controller_memory_recurrence_error": memory_error,
        "fixed_duty_relative_error": duty_error,
        "condenser_duty_BTUph": float(endpoint.condenser_duty_BTUph),
        "reflux_drum_pressure_psia": float(endpoint.pressure_psia[top_index]),
        "top_tray_pressure_psia": float(endpoint.pressure_psia[tray_index]),
        "bottom_pressure_psia": float(endpoint.pressure_psia[-1]),
        "top_tray_minus_drum_pressure_psia": float(
            endpoint.pressure_psia[tray_index] - endpoint.pressure_psia[top_index]
        ),
        "level_fraction": final.level_fraction.tolist(),
        "controller_memory_endpoint": final.controller_memory_endpoint.tolist(),
        "controller_rate_per_sec": final.controller_rate_per_sec.tolist(),
        "product_log_ratio": final.product_log_ratio.tolist(),
        "distillate_lbmolph": final.distillate_lbmolph,
        "bottoms_lbmolph": final.bottoms_lbmolph,
        "reflux_lbmolph": float(
            getattr(final, "reflux_lbmolph", context["spec"].reflux_lbmolph)
        ),
        "pressure_error_psia": float(getattr(final, "pressure_error_psia", np.nan)),
        "composition_error_molfrac": float(
            getattr(final, "composition_error_molfrac", np.nan)
        ),
        "condenser_duty_ratio": float(condenser_duty_ratio),
        "reflux_ratio": float(reflux_ratio),
        "pressure_quality_pass": bool(pressure_quality_pass),
        "composition_quality_pass": bool(composition_quality_pass),
        "composition_error_limit_molfrac": (
            None
            if composition_error_limit_molfrac is None
            else float(composition_error_limit_molfrac)
        ),
        "level_quality_pass": bool(level_quality_pass),
        "mv_quality_pass": bool(mv_quality_pass),
        "disturbance_quality_pass": bool(
            pressure_quality_pass
            and composition_quality_pass
            and level_quality_pass
            and mv_quality_pass
        ),
        "parallel_worker_ids": worker_ids,
    }
    return solution.x.copy(), final, report, cached_matrix


def run(
    *,
    workbook: Path,
    checkpoint: Path,
    duration_sec: float,
    timestep_sec: float | None,
    log_every: int,
    logs_dir: Path,
    run_name: str,
    run_description: str = "",
    parallel_workers: int = 1,
    drum_level_kc: float | None = None,
    drum_level_ti_sec: float | None = None,
    enable_regulatory_control: bool | None = None,
    pressure_setpoint_psia: float | None = None,
    pressure_kc_BTUph_per_psia: float | None = None,
    pressure_ti_sec: float | None = None,
    composition_component: str | None = None,
    composition_setpoint_molfrac: float | None = None,
    composition_kc_lbmolph_per_molfrac: float | None = None,
    composition_ti_sec: float | None = None,
    feed_temperature_step_F: float | None = None,
    jacobian_refresh_interval: int | None = None,
    composition_error_limit_molfrac: float | None = None,
) -> dict[str, Any]:
    if int(parallel_workers) < 1:
        raise ValueError("parallel_workers must be positive")
    saved_metadata = _peek_checkpoint_metadata(checkpoint)
    inherited_composition_limit = saved_metadata.get(
        "composition_error_limit_molfrac"
    )
    effective_composition_limit = (
        inherited_composition_limit
        if composition_error_limit_molfrac is None
        else composition_error_limit_molfrac
    )
    if effective_composition_limit is not None:
        effective_composition_limit = float(effective_composition_limit)
        _composition_quality_pass(0.0, effective_composition_limit)
    inherited_feed_step = float(saved_metadata.get("feed_temperature_step_F", 0.0))
    effective_feed_step = (
        inherited_feed_step
        if feed_temperature_step_F is None
        else float(feed_temperature_step_F)
    )
    if (
        abs(inherited_feed_step) > 1.0e-15
        and abs(effective_feed_step - inherited_feed_step) > 1.0e-12
    ):
        raise ValueError(
            "A disturbed checkpoint must inherit its saved feed-temperature step unchanged"
        )
    inherited_refresh_interval = int(
        saved_metadata.get("jacobian_refresh_interval", 0)
    )
    effective_refresh_interval = (
        inherited_refresh_interval
        if jacobian_refresh_interval is None and inherited_refresh_interval > 0
        else (
            5
            if jacobian_refresh_interval is None and abs(effective_feed_step) > 1.0e-15
            else int(jacobian_refresh_interval or 0)
        )
    )
    if effective_refresh_interval < 0:
        raise ValueError("Jacobian refresh interval cannot be negative")
    if (
        inherited_refresh_interval > 0
        and effective_refresh_interval != inherited_refresh_interval
    ):
        raise ValueError(
            "A continuation must inherit its saved Jacobian refresh interval unchanged"
        )
    inherited_regulatory = bool(saved_metadata.get("pressure_controller_active", False))
    regulatory_active = (
        inherited_regulatory
        if enable_regulatory_control is None
        else bool(enable_regulatory_control)
    )
    if inherited_regulatory and not regulatory_active:
        raise ValueError(
            "An active regulatory-control checkpoint must continue with its controller memories; "
            "controller deactivation is not a bumpless supported transition."
        )
    regulatory_options = None
    regulatory_override_requested = bool(
        inherited_regulatory
        and any(
            value is not None
            for value in (
                pressure_setpoint_psia,
                pressure_kc_BTUph_per_psia,
                pressure_ti_sec,
                composition_component,
                composition_setpoint_molfrac,
                composition_kc_lbmolph_per_molfrac,
                composition_ti_sec,
            )
        )
    )
    if regulatory_active:
        regulatory_options = _regulatory_options_from_checkpoint(
            checkpoint,
            saved_metadata,
            pressure_setpoint_psia=pressure_setpoint_psia,
            pressure_kc_BTUph_per_psia=pressure_kc_BTUph_per_psia,
            pressure_ti_sec=pressure_ti_sec,
            composition_component=composition_component,
            composition_setpoint_molfrac=composition_setpoint_molfrac,
            composition_kc_lbmolph_per_molfrac=composition_kc_lbmolph_per_molfrac,
            composition_ti_sec=composition_ti_sec,
        )
    if regulatory_active and int(parallel_workers) == 1:
        raise ValueError("Regulatory-control qualification currently requires parallel_workers > 1")
    timestep_sec = _resolve_timestep_sec(timestep_sec, saved_metadata)
    steps_float = float(duration_sec) / float(timestep_sec)
    steps = int(round(steps_float))
    if steps < 1 or abs(steps - steps_float) > 1.0e-9:
        raise ValueError(
            f"Duration must be a positive whole number of {timestep_sec:g} s timesteps"
        )
    workbook = workbook.expanduser().resolve()
    build_column_spec_from_case(load_case_from_excel(str(workbook)))
    effective_drum_kc = (
        float(drum_level_kc)
        if drum_level_kc is not None
        else saved_metadata.get("drum_level_kc")
    )
    effective_drum_ti_sec = (
        float(drum_level_ti_sec)
        if drum_level_ti_sec is not None
        else saved_metadata.get("drum_level_ti_sec")
    )
    context = _context(
        drum_level_kc=effective_drum_kc,
        drum_level_ti_sec=effective_drum_ti_sec,
        regulatory_options=regulatory_options,
        feed_temperature_step_F=effective_feed_step,
    )
    metadata, reference, memory, coordinates, prior = _load_checkpoint(
        checkpoint, workbook=workbook, context=context
    )
    if regulatory_active and not inherited_regulatory:
        memory = np.concatenate((np.asarray(memory, dtype=float), np.zeros(2)))
        spec = context["contract"].regulatory
        top_liquid = np.asarray(reference.liquid_component_inventory_lbmol[0], dtype=float)
        top_x = top_liquid / np.sum(top_liquid)
        component_index = context["contract"].base.component_names.index(
            spec.composition_component
        )
        pressure_error = float(reference.pressure_psia[0]) - spec.pressure_setpoint_psia
        composition_error = float(top_x[component_index]) - spec.composition_setpoint_molfrac
        memory[2] = -spec.pressure_kc_per_psia * pressure_error
        memory[3] = -spec.composition_kc_per_molfrac * composition_error
        prior = SimpleNamespace(
            controller_rate_per_sec=np.concatenate(
                (np.asarray(prior.controller_rate_per_sec, dtype=float), np.zeros(2))
            ),
            product_log_ratio=np.asarray(prior.product_log_ratio, dtype=float),
            reflux_log_ratio=0.0,
        )
    elif regulatory_override_requested:
        spec = context["contract"].regulatory
        top_liquid = np.asarray(reference.liquid_component_inventory_lbmol[0], dtype=float)
        top_x = top_liquid / np.sum(top_liquid)
        component_index = context["contract"].base.component_names.index(
            spec.composition_component
        )
        pressure_error = float(reference.pressure_psia[0]) - spec.pressure_setpoint_psia
        composition_error = float(top_x[component_index]) - spec.composition_setpoint_molfrac
        duty_log_ratio = float(
            np.log(
                float(reference.condenser_duty_BTUph)
                / float(spec.condenser_duty_reference_BTUph)
            )
        )
        memory, regulatory_rates = _bumpless_regulatory_state(
            controller_memory=np.asarray(memory, dtype=float),
            controller_rates_per_sec=np.asarray(prior.controller_rate_per_sec, dtype=float),
            pressure_error_psia=pressure_error,
            condenser_duty_log_ratio=duty_log_ratio,
            pressure_kc_per_psia=spec.pressure_kc_per_psia,
            pressure_ti_sec=spec.pressure_ti_sec,
            composition_error_molfrac=composition_error,
            reflux_log_ratio=float(prior.reflux_log_ratio),
            composition_kc_per_molfrac=spec.composition_kc_per_molfrac,
            composition_ti_sec=spec.composition_ti_sec,
        )
        prior = SimpleNamespace(
            controller_rate_per_sec=regulatory_rates,
            product_log_ratio=np.asarray(prior.product_log_ratio, dtype=float),
            reflux_log_ratio=float(prior.reflux_log_ratio),
        )
    source_controllers = context["workbook_controllers"]
    source_drum_kc = float(metadata.get("drum_level_kc", source_controllers.drum_kc))
    source_drum_ti_sec = float(
        metadata.get("drum_level_ti_sec", source_controllers.drum_ti_sec)
    )
    tuning_changed = bool(
        abs(float(context["contract"].controllers.drum_kc) - source_drum_kc) > 1.0e-15
        or abs(float(context["contract"].controllers.drum_ti_sec) - source_drum_ti_sec)
        > 1.0e-15
    )
    initial_level_fraction: np.ndarray | None = None
    if tuning_changed:
        initial_level_fraction = _reference_level_fractions(context, reference)
        level_memory = _bumpless_controller_memory(
            product_log_ratio=prior.product_log_ratio,
            level_fraction=initial_level_fraction,
            controllers=context["contract"].controllers,
        )
        memory = np.asarray(memory, dtype=float).copy()
        memory[:2] = level_memory
    solver_payload = json.loads((ROOT / dd274.CONTRACT).read_text(encoding="utf-8"))
    if abs(effective_feed_step) > 1.0e-15:
        solver_payload["solver"]["max_nfev_per_root"] = max(
            int(solver_payload["solver"]["max_nfev_per_root"]),
            FEED_TEMPERATURE_DISTURBANCE_MAX_NFEV_PER_ROOT,
        )
    effective_max_nfev = int(solver_payload["solver"]["max_nfev_per_root"])
    specified_duty = float(metadata["specified_condenser_duty_BTUph"])
    logs_dir = logs_dir.expanduser().resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%d_%H%M%S")
    summary_path = logs_dir / f"column_summary_{run_id}.csv"
    profile_path = logs_dir / f"column_profile_{run_id}.csv"
    metadata_path = logs_dir / f"run_metadata_{run_id}.json"
    output_checkpoint = logs_dir / f"core_v3_checkpoint_{run_id}.npz"
    recovery_checkpoint = logs_dir / f"core_v3_recovery_checkpoint_{run_id}.npz"
    summary_rows: list[dict[str, Any]] = []
    profile_rows: list[dict[str, Any]] = []
    initial_liquid = reference.liquid_component_inventory_lbmol
    initial_products = np.asarray(
        (
            float(context["balance_inputs"].distillate_lbmolph) * np.exp(prior.product_log_ratio[0]),
            float(context["balance_inputs"].bottoms_lbmolph) * np.exp(prior.product_log_ratio[1]),
        ),
        dtype=float,
    )
    steady_history: list[dict[str, Any]] = [
        {
            "time_s": 0.0,
            "top_x": initial_liquid[0] / np.sum(initial_liquid[0]),
            "bottom_x": initial_liquid[-1] / np.sum(initial_liquid[-1]),
            "distillate_lbmolph": float(initial_products[0]),
            "bottoms_lbmolph": float(initial_products[1]),
        }
    ]
    steady_reference = reference
    steady_reference_time = 0.0
    started = time.perf_counter()
    final = None
    reports = []
    provider = context.get("provider")
    target_steps = steps
    control_path = logs_dir / "runtime_control.json"
    parallel_executor: ProcessPoolExecutor | None = None
    parallel_jacobians: PersistentParallelColoredJacobian | None = None
    if int(parallel_workers) > 1:
        parallel_executor = ProcessPoolExecutor(
            max_workers=int(parallel_workers),
            mp_context=mp.get_context("spawn"),
            initializer=_parallel_worker_initialize,
            initargs=(
                effective_drum_kc,
                effective_drum_ti_sec,
                regulatory_options,
                effective_feed_step,
            ),
        )
        parallel_jacobians = PersistentParallelColoredJacobian(
            parallel_executor,
            _parallel_worker_evaluate,
            pattern=(
                regulatory_control_pattern(context["contract"])
                if regulatory_active
                else dd274.vapor_holdup_terminal_control_pattern(context["contract"])
            ),
            step=float(solver_payload["solver"]["difference_step"]),
            worker_count=int(parallel_workers),
            require_all_workers=False,
        )
    index = 0
    while index < target_steps:
        target_steps = _requested_total_steps(control_path, target_steps)
        index += 1
        memo_before = _memo_snapshot(provider)
        root_started = time.perf_counter()
        try:
            if parallel_jacobians is None:
                coordinates, final, report, _matrix = dd274._solve_endpoint(
                    context,
                    solver_payload,
                    reference,
                    memory,
                    coordinates,
                    prior,
                    timestep_sec,
                    specified_duty,
                    f"core_v3_dynamic:{run_id}:{index}",
                )
            else:
                coordinates, final, report, _matrix = _solve_endpoint_parallel(
                    context,
                    solver_payload,
                    reference,
                    memory,
                    coordinates,
                    prior,
                    timestep_sec,
                    specified_duty,
                    f"core_v3_dynamic:{run_id}:{index}",
                    parallel_jacobians,
                    effective_refresh_interval,
                    effective_composition_limit,
                )
        except BaseException:
            if parallel_executor is not None:
                parallel_executor.shutdown(wait=True, cancel_futures=True)
            raise
        report = dict(report)
        report["root_wall_s"] = time.perf_counter() - root_started
        report.update(_memo_delta(memo_before, _memo_snapshot(provider)))
        if (
            not report["scipy_success"]
            or report["scaled_residual_inf_norm"] >= 1.0e-8
            or report["jacobian_rank"] != len(context["contract"].rows)
            or report["jacobian_condition"] >= 1.0e8
            or not report["physical_pass"]
            or (
                abs(effective_feed_step) > 1.0e-15
                and not report.get("disturbance_quality_pass", False)
            )
        ):
            if parallel_executor is not None:
                parallel_executor.shutdown(wait=True, cancel_futures=True)
            raise RuntimeError(f"Core V3 endpoint {index} failed its acceptance gate: {report}")
        next_reference = dd249._next_reference(reference, final.base)
        memory = final.controller_memory_endpoint.copy()
        prior = final
        reports.append(report)
        segment_time = index * timestep_sec
        if index == 1 or index % max(int(log_every), 1) == 0 or index == target_steps:
            wall = time.perf_counter() - started
            steady = _steady_state_metrics(
                context,
                steady_reference,
                final,
                interval_sec=segment_time - steady_reference_time,
                time_s=segment_time,
                history=steady_history,
            )
            summary_rows.append(
                _summary_row(
                    context,
                    final,
                    time_s=segment_time,
                    wall_elapsed_s=wall,
                    report=report,
                    steady=steady,
                )
            )
            profile_rows.extend(_profile_rows(context, final, time_s=segment_time))
            _write_csv(summary_path, summary_rows)
            _write_csv(profile_path, profile_rows)
            _write_checkpoint(
                recovery_checkpoint,
                workbook=workbook,
                context=context,
                reference=next_reference,
                controller_memory=memory,
                previous_coordinates=coordinates,
                controller_rate_per_sec=final.controller_rate_per_sec,
                product_log_ratio=final.product_log_ratio,
                reflux_log_ratio=float(getattr(final, "reflux_log_ratio", 0.0)),
                jacobian_refresh_interval=effective_refresh_interval,
                max_nfev_per_root=effective_max_nfev,
                composition_error_limit_molfrac=effective_composition_limit,
                final_time_s=float(metadata["final_time_s"]) + segment_time,
                timestep_sec=timestep_sec,
                source=f"in-progress continuation of {checkpoint.resolve()}",
            )
            steady_reference = next_reference
            steady_reference_time = segment_time
        reference = next_reference
        if index % max(int(log_every), 1) == 0 or index == target_steps:
            print(
                f"[Progress] Core V3 step {index}/{target_steps} t={segment_time:.2f} s "
                f"Pdrum={report['reflux_drum_pressure_psia']:.6f} psia "
                f"SS={summary_rows[-1]['steady_state_score']:.6g}",
                flush=True,
            )
        target_steps = _requested_total_steps(control_path, target_steps)
    if parallel_executor is not None:
        parallel_executor.shutdown(wait=True)
    if final is None:
        raise RuntimeError("Core V3 continuation produced no endpoint")
    actual_duration_sec = float(target_steps) * float(timestep_sec)
    final_time = float(metadata["final_time_s"]) + actual_duration_sec
    _write_checkpoint(
        output_checkpoint,
        workbook=workbook,
        context=context,
        reference=reference,
        controller_memory=memory,
        previous_coordinates=coordinates,
        controller_rate_per_sec=final.controller_rate_per_sec,
        product_log_ratio=final.product_log_ratio,
        reflux_log_ratio=float(getattr(final, "reflux_log_ratio", 0.0)),
        jacobian_refresh_interval=effective_refresh_interval,
        max_nfev_per_root=effective_max_nfev,
        composition_error_limit_molfrac=effective_composition_limit,
        final_time_s=final_time,
        timestep_sec=timestep_sec,
        source=f"continuation of {checkpoint.resolve()}",
    )
    wall = time.perf_counter() - started
    root_walls = np.asarray([float(item["root_wall_s"]) for item in reports], dtype=float)
    memo_hits = int(sum(int(item["memo_hits_delta"]) for item in reports))
    memo_misses = int(sum(int(item["memo_misses_delta"]) for item in reports))
    memo_requests = memo_hits + memo_misses
    provider_counter_getter = getattr(provider, "get_call_counters", None)
    provider_call_counters = provider_counter_getter() if callable(provider_counter_getter) else {}
    run_metadata = {
        "schema": "dynamic_distillation.core_v3_run_metadata.v1",
        "status": "completed",
        "run_id": run_id,
        "run_name": run_name,
        "run_description": str(run_description or ""),
        "controller_tuning": {
            "drum_kc": float(context["contract"].controllers.drum_kc),
            "drum_ti_sec": float(context["contract"].controllers.drum_ti_sec),
            "sump_kc": float(context["contract"].controllers.sump_kc),
            "sump_ti_sec": float(context["contract"].controllers.sump_ti_sec),
            "source_drum_kc": source_drum_kc,
            "source_drum_ti_sec": source_drum_ti_sec,
            "bumpless_memory_adjustment": tuning_changed,
            "bumpless_level_fraction": (
                initial_level_fraction.tolist()
                if initial_level_fraction is not None
                else None
            ),
            "regulatory_control_active": regulatory_active,
            "regulatory_activation_bumpless": bool(
                regulatory_active and not inherited_regulatory
            ),
            "regulatory_retuning_bumpless": regulatory_override_requested,
            "pressure": (
                {
                    "setpoint_psia": context["contract"].regulatory.pressure_setpoint_psia,
                    "kc_per_psia": context["contract"].regulatory.pressure_kc_per_psia,
                    "ti_sec": context["contract"].regulatory.pressure_ti_sec,
                    "mv": "condenser_duty_BTUph",
                }
                if regulatory_active else None
            ),
            "distillate_composition": (
                {
                    "component": context["contract"].regulatory.composition_component,
                    "setpoint_molfrac": context["contract"].regulatory.composition_setpoint_molfrac,
                    "kc_per_molfrac": context["contract"].regulatory.composition_kc_per_molfrac,
                    "ti_sec": context["contract"].regulatory.composition_ti_sec,
                    "mv": "reflux_lbmolph",
                }
                if regulatory_active else None
            ),
        },
        "feed_temperature_disturbance": dict(
            context.get("feed_temperature_disturbance", {})
        ),
        "jacobian_refresh_interval": effective_refresh_interval,
        "max_nfev_per_root": effective_max_nfev,
        "composition_error_limit_molfrac": effective_composition_limit,
        "started_from_checkpoint": str(checkpoint.resolve()),
        "excel_path": str(workbook),
        "source_final_time_s": float(metadata["final_time_s"]),
        "duration_sec": actual_duration_sec,
        "final_time_s": final_time,
        "dt_sec": float(timestep_sec),
        "n_steps": target_steps,
        "wall_elapsed_s": wall,
        "started_at_local": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - wall)),
        "ended_at_local": time.strftime("%Y-%m-%d %H:%M:%S"),
        "simulation_wall_ratio": actual_duration_sec / max(wall, 1.0e-300),
        "native_checkpoint": str(output_checkpoint),
        "recovery_checkpoint": str(recovery_checkpoint),
        "summary_csv": str(summary_path),
        "profile_csv": str(profile_path),
        "performance": {
            "jacobian_execution": "persistent_parallel" if parallel_workers > 1 else "serial",
            "parallel_workers": int(parallel_workers),
            "endpoint_wall_total_s": float(np.sum(root_walls)),
            "endpoint_wall_mean_s": float(np.mean(root_walls)),
            "endpoint_wall_median_s": float(np.median(root_walls)),
            "endpoint_wall_p95_s": float(np.percentile(root_walls, 95.0)),
            "endpoint_wall_max_s": float(np.max(root_walls)),
            "objective_calls_total": int(
                sum(int(item["function_calls_observed"]) for item in reports)
            ),
            "jacobian_builds_total": int(
                sum(int(item["jacobian_build_count"]) for item in reports)
            ),
            "memo_hits_total": memo_hits,
            "memo_misses_total": memo_misses,
            "memo_hit_fraction": float(memo_hits / memo_requests) if memo_requests else 0.0,
            "memoization_final": (
                provider.get_exact_state_memoization_stats()
                if callable(getattr(provider, "get_exact_state_memoization_stats", None))
                else {}
            ),
            "provider_call_counters": provider_call_counters,
        },
        "final_endpoint": reports[-1],
        "final_steady_state": {
            key: summary_rows[-1][key]
            for key in (
                "steady_state_score",
                "steady_state_flag",
                "ss_max_rel_state_rate_per_s",
                "ss_max_temp_rate_F_per_s",
                "ss_max_kpi_slope_per_s",
                "ss_max_mv_rate_per_s",
                "ss_global_inventory_rate_frac_feed",
            )
        },
    }
    metadata_path.write_text(json.dumps(run_metadata, indent=2, default=_json_default) + "\n", encoding="utf-8")
    print(json.dumps(run_metadata, indent=2, default=_json_default), flush=True)
    return run_metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excel", type=Path, required=True)
    parser.add_argument("--export-dd274-checkpoint", type=Path)
    parser.add_argument("--init-from-checkpoint", type=Path)
    parser.add_argument("--backfill-logs", type=Path)
    parser.add_argument("--duration-sec", type=float, default=30.0)
    parser.add_argument(
        "--dt",
        type=float,
        default=None,
        help=(
            "Validated Core V3 timestep (0.25 or 0.5 s). "
            "If omitted, inherit the checkpoint value; older Core V3 checkpoints "
            "default to 0.25 s."
        ),
    )
    parser.add_argument("--log-every", type=int, default=4)
    parser.add_argument("--logs-dir", type=Path, default=Path("logs/core_v3_ui_runs"))
    parser.add_argument("--run-name", default="core_v3_restart")
    parser.add_argument("--run-description", default="")
    parser.add_argument(
        "--drum-level-kc",
        type=float,
        help="Override the Core V3 drum-level PI proportional gain with a bumpless memory conversion.",
    )
    parser.add_argument(
        "--drum-level-ti-sec",
        type=float,
        help="Override the Core V3 drum-level PI integral time in seconds with a bumpless memory conversion.",
    )
    parser.add_argument(
        "--parallel-workers",
        type=int,
        default=8,
        help="Persistent Jacobian worker processes; use 1 for the serial path.",
    )
    parser.add_argument(
        "--regulatory-control",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Enable/inherit pressure-to-condenser-duty and distillate-composition-to-reflux PI control. "
            "New activation defaults both setpoints to the checkpoint endpoint for a bumpless hold."
        ),
    )
    parser.add_argument("--pressure-sp-psia", type=float)
    parser.add_argument("--pressure-kc-btuph-per-psia", type=float)
    parser.add_argument("--pressure-ti-sec", type=float)
    parser.add_argument("--composition-component", default=None)
    parser.add_argument("--composition-sp-molfrac", type=float)
    parser.add_argument("--composition-kc-lbmolph-per-molfrac", type=float)
    parser.add_argument("--composition-ti-sec", type=float)
    parser.add_argument(
        "--composition-error-limit-molfrac",
        type=float,
        default=None,
        help=(
            "Optional declared product-quality error limit. If omitted, "
            "composition remains a logged diagnostic and does not stop a run."
        ),
    )
    parser.add_argument(
        "--feed-temperature-step-F",
        type=float,
        default=None,
        help=(
            "Liquid-feed temperature step in degrees F. The runner recomputes "
            "feed enthalpy with governed DWSIM PR at unchanged feed pressure, "
            "composition, and flow. Disturbed checkpoints inherit this value."
        ),
    )
    parser.add_argument(
        "--jacobian-refresh-interval",
        type=int,
        default=None,
        help=(
            "Refresh the colored Jacobian after this many Jacobian callbacks. "
            "Feed-temperature disturbances default to 5; ordinary continuations "
            "retain the one-Jacobian method."
        ),
    )
    args = parser.parse_args()
    if args.export_dd274_checkpoint:
        destination = export_dd274_checkpoint(args.excel, args.export_dd274_checkpoint)
        print(destination)
        return 0
    if args.backfill_logs:
        if args.init_from_checkpoint is None:
            parser.error("--init-from-checkpoint is required with --backfill-logs")
        destination = backfill_run_logs(
            workbook=args.excel,
            checkpoint=args.init_from_checkpoint,
            logs_dir=args.backfill_logs,
        )
        print(destination)
        return 0
    if args.init_from_checkpoint is None:
        parser.error("--init-from-checkpoint is required for Core V3 continuation")
    run(
        workbook=args.excel,
        checkpoint=args.init_from_checkpoint,
        duration_sec=args.duration_sec,
        timestep_sec=args.dt,
        log_every=args.log_every,
        logs_dir=args.logs_dir,
        run_name=args.run_name,
        run_description=args.run_description,
        parallel_workers=args.parallel_workers,
        drum_level_kc=args.drum_level_kc,
        drum_level_ti_sec=args.drum_level_ti_sec,
        enable_regulatory_control=args.regulatory_control,
        pressure_setpoint_psia=args.pressure_sp_psia,
        pressure_kc_BTUph_per_psia=args.pressure_kc_btuph_per_psia,
        pressure_ti_sec=args.pressure_ti_sec,
        composition_component=args.composition_component,
        composition_setpoint_molfrac=args.composition_sp_molfrac,
        composition_kc_lbmolph_per_molfrac=args.composition_kc_lbmolph_per_molfrac,
        composition_ti_sec=args.composition_ti_sec,
        feed_temperature_step_F=args.feed_temperature_step_F,
        jacobian_refresh_interval=args.jacobian_refresh_interval,
        composition_error_limit_molfrac=args.composition_error_limit_molfrac,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
