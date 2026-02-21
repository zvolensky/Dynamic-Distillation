"""
excel_case_validator_v1.py

Dynamic Distillation - Preflight Case Validation

PURPOSE
-------
Run pre-integration validation checks on loaded case/spec content and produce
structured blocking/non-blocking diagnostics for CLI and API workflows.

INPUTS
------
validate_loaded_case(case, col):
- CaseData from loader
- ColumnSpec from builder

OUTPUTS
-------
ExcelValidationReport:
- errors (blocking)
- warnings (non-blocking)
- ok flag

print_validation_report(report): formatted console summary helper.

KEY DEPENDENCIES
----------------
- excel_case_loader_v1 / column_spec_builder_v1 data contracts

ASSUMPTIONS & CONSTRAINTS
-------------------------
- Validation checks focus on actionable startup correctness, not optimization.
- Warnings preserve run permissiveness while highlighting likely issues.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from dynamic_distillation.excel_case_loader_v1 import CaseData
from dynamic_distillation.column_spec_builder_v1 import ColumnSpec


@dataclass(frozen=True)
class ExcelValidationReport:
    errors: List[str]
    warnings: List[str]

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def _to_int(x: Any) -> Optional[int]:
    try:
        return int(float(x))
    except Exception:
        return None


def _to_float(x: Any) -> Optional[float]:
    try:
        v = float(x)
        if not np.isfinite(v):
            return None
        return v
    except Exception:
        return None


def _norm_key(s: str) -> str:
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def _get_stream_scalar(stream_obj: Any, keys: List[str]) -> Any:
    if stream_obj is None:
        return None
    if isinstance(stream_obj, dict):
        for k in keys:
            if k in stream_obj:
                return stream_obj[k]
    for k in keys:
        if hasattr(stream_obj, k):
            return getattr(stream_obj, k)
    return None


def _get_stream_comp_dict(stream_obj: Any) -> Optional[Dict[str, Any]]:
    if stream_obj is None:
        return None
    if isinstance(stream_obj, dict):
        v = stream_obj.get("Component Mole Flows (lbmol/h)")
        if isinstance(v, dict):
            return v
        v = stream_obj.get("component_molar_flows_lbmolph")
        if isinstance(v, dict):
            return v
    if hasattr(stream_obj, "component_molar_flows_lbmolph"):
        v = getattr(stream_obj, "component_molar_flows_lbmolph")
        if isinstance(v, dict):
            return v
    return None


def validate_loaded_case(case: CaseData, col: ColumnSpec) -> ExcelValidationReport:
    errors: List[str] = []
    warnings: List[str] = []

    specs = getattr(case, "specs", {}) or {}
    ic = getattr(case, "initial_conditions", None)
    streams = getattr(case, "streams", {}) or {}

    n_stages = int(getattr(col, "n_stages", 0))
    n_components = int(getattr(col, "n_components", 0))

    # Specifications consistency checks.
    req_specs = (
        "Number of Stages",
        "Number of Components",
        "Timestep (sec)",
        "Simulation Length (min)",
        "Log Frequency (timesteps)",
    )
    for k in req_specs:
        if k not in specs:
            errors.append(f"Missing required specification: '{k}'.")
    n_stages_spec = _to_int(specs.get("Number of Stages"))
    n_components_spec = _to_int(specs.get("Number of Components"))
    if n_stages_spec is not None and n_stages_spec != n_stages:
        errors.append(f"Stage count mismatch: specs={n_stages_spec}, built={n_stages}.")
    if n_components_spec is not None and n_components_spec != n_components:
        errors.append(f"Component count mismatch: specs={n_components_spec}, built={n_components}.")

    dt = _to_float(specs.get("Timestep (sec)"))
    if dt is None or dt <= 0.0:
        errors.append("Timestep (sec) must be a finite value > 0.")

    tlen = _to_float(specs.get("Simulation Length (min)"))
    if tlen is None or tlen <= 0.0:
        errors.append("Simulation Length (min) must be a finite value > 0.")

    log_every = _to_int(specs.get("Log Frequency (timesteps)"))
    if log_every is None or log_every <= 0:
        errors.append("Log Frequency (timesteps) must be an integer > 0.")

    # Initial Conditions checks.
    if not isinstance(ic, pd.DataFrame):
        errors.append("Initial Conditions was not loaded as a DataFrame.")
    else:
        if len(ic) != n_stages:
            errors.append(f"Initial Conditions row count is {len(ic)}; expected {n_stages}.")

        required_ic_cols = (
            "Stage",
            "Temperature (F)",
            "Pressure (psia)",
            "Vapor Flow (lbmol/h)",
            "Liquid Flow (lbmol/h)",
        )
        for c in required_ic_cols:
            if c not in ic.columns:
                errors.append(f"Initial Conditions missing required column '{c}'.")

        if "Stage" in ic.columns:
            stage_vals = pd.to_numeric(ic["Stage"], errors="coerce").to_numpy(dtype=float)
            if np.any(~np.isfinite(stage_vals)):
                errors.append("Initial Conditions 'Stage' contains non-numeric values.")
            else:
                stage_int = stage_vals.astype(int)
                expected = np.arange(1, n_stages + 1, dtype=int)
                if len(stage_int) == n_stages and not np.array_equal(stage_int, expected):
                    errors.append("Initial Conditions 'Stage' must be exactly 1..N in ascending order.")

        for c in ("Temperature (F)", "Pressure (psia)", "Vapor Flow (lbmol/h)", "Liquid Flow (lbmol/h)"):
            if c not in ic.columns:
                continue
            vals = pd.to_numeric(ic[c], errors="coerce").to_numpy(dtype=float)
            if np.any(~np.isfinite(vals)):
                errors.append(f"Initial Conditions '{c}' contains non-numeric/NaN values.")
                continue
            if c == "Pressure (psia)" and np.any(vals <= 0.0):
                errors.append("Initial Conditions has non-positive pressures.")
            if c in ("Vapor Flow (lbmol/h)", "Liquid Flow (lbmol/h)") and np.any(vals < 0.0):
                warnings.append(f"Initial Conditions has negative values in '{c}'.")

        for c in ("Liquid Holdup (lbmol)", "Vapor Holdup (lbmol)"):
            if c not in ic.columns:
                continue
            vals = pd.to_numeric(ic[c], errors="coerce").to_numpy(dtype=float)
            good = vals[np.isfinite(vals)]
            if good.size > 0 and np.any(good < 0.0):
                warnings.append(f"Initial Conditions has negative values in optional column '{c}'.")

        liq_cols = [f"Liquid Composition Component {i}" for i in range(1, n_components + 1)]
        vap_cols = [f"Vapor Composition Component {i}" for i in range(1, n_components + 1)]
        for cols, label in ((liq_cols, "liquid"), (vap_cols, "vapor")):
            missing = [c for c in cols if c not in ic.columns]
            if missing:
                errors.append(f"Initial Conditions missing {label} composition columns: {missing}.")
                continue
            mat = ic[cols].to_numpy(dtype=float)
            if np.any(~np.isfinite(mat)):
                errors.append(f"Initial Conditions {label} composition contains NaN/non-numeric values.")
                continue
            s = np.sum(mat, axis=1)
            off = np.abs(s - 1.0)
            if np.any(off > 1e-3):
                max_off = float(np.max(off))
                warnings.append(
                    f"Initial Conditions {label} composition row sums deviate from 1.0 (max abs dev={max_off:.3e})."
                )

    # Streams checks (optional but useful).
    if not isinstance(streams, dict) or len(streams) == 0:
        warnings.append("No streams were parsed; boundary and composition fallbacks will be used where needed.")
    else:
        for nm, sobj in streams.items():
            stage = _to_int(
                _get_stream_scalar(
                    sobj,
                    ["Stage", "stage_1based", "stage", "Stage (1-based)"],
                )
            )
            if stage is not None and (stage < 1 or stage > n_stages):
                warnings.append(f"Stream '{nm}' stage {stage} is outside valid range 1..{n_stages}.")

            total = _to_float(
                _get_stream_scalar(
                    sobj,
                    ["Total Molar Flow (lbmol/h)", "total_molar_flow_lbmolph", "flow_lbmolph"],
                )
            )
            if total is not None and total < 0.0:
                warnings.append(f"Stream '{nm}' has negative total molar flow ({total:g} lbmol/h).")

            comp = _get_stream_comp_dict(sobj)
            if isinstance(comp, dict) and len(comp) > 0 and total is not None and total > 0.0:
                csum = 0.0
                for v in comp.values():
                    fv = _to_float(v)
                    if fv is not None:
                        csum += fv
                rel = abs(csum - total) / max(abs(total), 1e-12)
                if rel > 0.05:
                    warnings.append(
                        f"Stream '{nm}' component-flow sum ({csum:g}) differs from total flow ({total:g}) by {rel*100:.1f}%."
                    )

    # Model-setting visibility warnings.
    specs_raw = getattr(col, "specs_raw", {}) or {}
    norm_map = {_norm_key(k): v for k, v in specs_raw.items()}
    norm_keys = set(norm_map.keys())

    pressure_raw = str(norm_map.get("pressuremodel", "")).strip().lower()
    pressure_default = "hydraulic" if getattr(col, "geometry", None) is not None else "spec"
    pressure_effective = pressure_raw if pressure_raw in ("spec", "hydraulic") else pressure_default

    vapor_raw = str(norm_map.get("vaporflowmodel", "")).strip().lower()
    vapor_default = "energy" if pressure_effective == "hydraulic" else "profile"
    vapor_effective = vapor_raw if vapor_raw in ("profile", "energy") else vapor_default

    if "pressuremodel" not in norm_keys:
        warnings.append(
            f"Pressure Model not specified; runner default is '{pressure_effective}'."
        )
    if "vaporflowmodel" not in norm_keys:
        warnings.append(
            f"Vapor Flow Model not specified; runner default is '{vapor_effective}'."
        )

    return ExcelValidationReport(errors=errors, warnings=warnings)


def print_validation_report(report: ExcelValidationReport) -> None:
    status = "PASS" if report.ok else "FAIL"
    print(f"[Validation] {status}  errors={len(report.errors)}  warnings={len(report.warnings)}")
    for msg in report.errors:
        print(f"[Validation][Error] {msg}")
    for msg in report.warnings:
        print(f"[Validation][Warn] {msg}")
