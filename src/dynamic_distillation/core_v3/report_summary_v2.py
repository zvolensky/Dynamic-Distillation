"""Versioned, evidence-aware presentation summary for Core V3 reports.

This module deliberately does not alter simulation results.  It translates the
existing end-point summary and optional saved trajectory into a stable report
contract, preserving absence as data rather than inventing measurements.
"""

from __future__ import annotations

from pathlib import Path
import hashlib
import json
from typing import Any, Mapping, Sequence

import numpy as np


REPORT_SCHEMA_VERSION = "core-v3-report-v2"
MISSING = "not_available"
BALANCE_FINAL_WINDOW_SEC = 60.0


def _state(value: Any, *, available: bool = True) -> dict[str, Any]:
    return {"value": value if available else None, "data_state": "observed" if available else MISSING}


def _series(trajectory: Mapping[str, Any] | None, key: str) -> np.ndarray | None:
    if trajectory is None or key not in trajectory:
        return None
    values = np.asarray(trajectory[key], dtype=float)
    return values if values.size and np.all(np.isfinite(values)) else None


def _metric(name: str, values: np.ndarray | None, units: str) -> dict[str, Any]:
    if values is None or values.ndim != 1:
        return {"variable": name, "initial": _state(None, available=False), "final": _state(None, available=False), "change": _state(None, available=False), "minimum": _state(None, available=False), "maximum": _state(None, available=False), "units": units}
    return {"variable": name, "initial": _state(float(values[0])), "final": _state(float(values[-1])), "change": _state(float(values[-1] - values[0]),), "minimum": _state(float(np.min(values))), "maximum": _state(float(np.max(values))), "units": units}


def _artifact_index(metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    names = {"endpoint_json": "json_path", "checkpoint": "native_checkpoint", "summary_csv": "summary_csv", "profile_csv": "profile_csv", "trajectory": "trajectory_path", "report_trajectory": "report_trajectory_jsonl", "events": "report_events_jsonl", "balance_ledger": "report_balance_ledger_jsonl", "console_log": "console_log", "report_metadata": "report_metadata", "word_report": "word_report", "report_summary": "report_summary"}
    values = dict(metadata)
    if not values.get("console_log") and values.get("summary_csv"):
        candidate = Path(str(values["summary_csv"])).parent / "console_stdout.txt"
        if candidate.exists():
            values["console_log"] = str(candidate)
    rows = []
    for label, key in names.items():
        path = values.get(key)
        if path:
            candidate = Path(str(path))
            if candidate.exists() and candidate.is_file():
                hasher = hashlib.sha256()
                with candidate.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        hasher.update(block)
                digest = hasher.hexdigest()
                rows.append({"artifact": label, "path": str(path), "size_bytes": candidate.stat().st_size, "sha256": digest, "status": "available"})
            else:
                rows.append({"artifact": label, "path": str(path), "size_bytes": None, "sha256": None, "status": "referenced_not_found"})
    return rows


def _jsonl(path_value: Any) -> list[dict[str, Any]]:
    if not path_value:
        return []
    try:
        with Path(str(path_value)).open(encoding="utf-8") as stream:
            return [dict(json.loads(line)) for line in stream if line.strip()]
    except (OSError, ValueError, TypeError):
        return []


def _accepted_series(rows: Sequence[Mapping[str, Any]], key: str) -> np.ndarray | None:
    try:
        values = np.asarray([float(row[key]) for row in rows], dtype=float)
    except (KeyError, TypeError, ValueError):
        return None
    return values if values.size and np.all(np.isfinite(values)) else None


def _controller_tuning(name: str, metadata: Mapping[str, Any]) -> dict[str, Any] | None:
    """Attach only recorded tuning; never infer limits or controller policy."""

    direct = dict(metadata.get("controllers", {}))
    if name == "distillate_drum_level" and isinstance(direct.get("drum"), Mapping):
        return dict(direct["drum"])
    if name == "bottoms_sump_level" and isinstance(direct.get("bottom"), Mapping):
        return dict(direct["bottom"])
    tuning = dict(metadata.get("controller_tuning", {}))
    if name == "drum_level":
        return {key: tuning[key] for key in ("drum_kc", "drum_ti_sec") if key in tuning}
    if name == "sump_level":
        return {key: tuning[key] for key in ("sump_kc", "sump_ti_sec") if key in tuning}
    if name in {"pressure", "distillate_composition"} and isinstance(tuning.get(name), Mapping):
        return dict(tuning[name])
    return None


def _controller_descriptor(name: str, item: Mapping[str, Any]) -> tuple[str, str]:
    """Return a human-readable controlled variable and PV unit without guessing."""

    descriptors = {
        "drum_level": ("distillate drum liquid level", "fraction"),
        "sump_level": ("bottoms sump liquid level", "fraction"),
        "pressure": ("top pressure", "psia"),
        "distillate_composition": ("distillate composition", "mole fraction"),
    }
    return descriptors.get(name, (str(item.get("controlled_variable", name)).replace("_", " "), str(item.get("pv_units", "Not reported"))))


def _output_unit(output_key: str | None) -> str:
    if output_key == "output_lbmolph":
        return "lbmol/h"
    if output_key == "output_BTUph":
        return "BTU/h"
    return "Not reported"


def _controller_bounds(name: str, metadata: Mapping[str, Any]) -> tuple[float, float] | None:
    """Read explicitly persisted output bounds; never infer them from observations."""

    source = metadata.get("controller_output_bounds", {})
    if not isinstance(source, Mapping):
        return None
    bounds = source.get(name)
    if not isinstance(bounds, Mapping):
        return None
    try:
        lower, upper = float(bounds["lower"]), float(bounds["upper"])
    except (KeyError, TypeError, ValueError):
        return None
    return (lower, upper) if np.isfinite(lower) and np.isfinite(upper) and lower <= upper else None


def _settling_tolerance(name: str, metadata: Mapping[str, Any]) -> float | None:
    """Use an explicitly persisted absolute-error criterion when provided."""

    source = metadata.get("controller_settling_tolerance", {})
    value = source.get(name) if isinstance(source, Mapping) else None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) and result >= 0.0 else None


def _time_at_bound(times: np.ndarray, values: np.ndarray, bound: float) -> float:
    if times.size < 2:
        return 0.0
    at_bound = np.isclose(values, bound, rtol=1.0e-9, atol=1.0e-12)
    return float(np.sum(np.diff(times)[at_bound[:-1] & at_bound[1:]]))


def _settling_time(times: np.ndarray, error: np.ndarray, tolerance: float) -> float | None:
    """First accepted endpoint after which error remains within the recorded criterion."""

    within = np.abs(error) <= tolerance
    for index in range(times.size):
        if bool(np.all(within[index:])):
            return float(times[index])
    return None


def _controller_kpis(
    rows: list[dict[str, Any]], *, metadata: Mapping[str, Any]
) -> list[dict[str, Any]]:
    grouped: dict[str, list[tuple[float, Mapping[str, Any]]]] = {}
    for row in rows:
        for name, item in dict(row.get("controllers", {})).items():
            grouped.setdefault(name, []).append((float(row["time_sec"]), dict(item)))
    result = []
    for name, items in sorted(grouped.items()):
        times = np.asarray([item[0] for item in items], dtype=float)
        error = np.asarray([float(item[1]["pv"]) - float(item[1]["sp"]) for item in items], dtype=float)
        output_keys = [
            next((key for key in item if key.startswith("output_")), None)
            for _time, item in items
        ]
        output_key = output_keys[0] if output_keys and all(key == output_keys[0] for key in output_keys) else None
        try:
            outputs = np.asarray(
                [float(item[output_key]) for _time, item in items] if output_key else [], dtype=float
            )
        except (KeyError, TypeError, ValueError):
            outputs = np.asarray([])
        output_available = outputs.size == times.size and np.all(np.isfinite(outputs))
        integral = (
            float(getattr(np, "trapezoid", np.trapz)(np.abs(error), times))
            if times.size > 1 else None
        )
        output_slew = np.abs(np.diff(outputs) / np.diff(times)) if output_available and times.size > 1 and np.all(np.diff(times) > 0.0) else np.asarray([])
        tuning = _controller_tuning(name, metadata)
        controlled_variable, pv_units = _controller_descriptor(name, items[-1][1])
        bounds = _controller_bounds(name, metadata)
        tolerance = _settling_tolerance(name, metadata)
        result.append({
            "controller": name,
            "controlled_variable": controlled_variable,
            "pv_units": pv_units,
            "final_pv": float(items[-1][1]["pv"]), "setpoint": float(items[-1][1]["sp"]),
            "final_error": float(error[-1]), "maximum_absolute_error": float(np.max(np.abs(error))),
            "mean_absolute_error": float(np.mean(np.abs(error))), "integral_absolute_error": integral,
            "overshoot": float(np.max(error)), "undershoot": float(np.min(error)),
            "output_units": _output_unit(output_key),
            "output_minimum": float(np.min(outputs)) if output_available else None,
            "output_maximum": float(np.max(outputs)) if output_available else None,
            "maximum_output_slew_per_sec": float(np.max(output_slew)) if output_slew.size else None,
            "output_data_state": "observed" if output_available else "not_available",
            "output_lower_bound": bounds[0] if bounds else None,
            "output_upper_bound": bounds[1] if bounds else None,
            "lower_saturation_time_sec": _time_at_bound(times, outputs, bounds[0]) if output_available and bounds else None,
            "upper_saturation_time_sec": _time_at_bound(times, outputs, bounds[1]) if output_available and bounds else None,
            "saturation_data_state": "observed" if output_available and bounds else "not_evaluated",
            "settling_criterion_absolute_error": tolerance,
            "settling_time_sec": _settling_time(times, error, tolerance) if tolerance is not None else None,
            "settling_data_state": "observed" if tolerance is not None else "not_evaluated",
            "history_start_time_sec": float(times[0]), "history_end_time_sec": float(times[-1]),
            "history_record_count": int(times.size),
            "tuning": tuning, "tuning_data_state": "observed" if tuning else "not_available",
            "data_state": "observed", "completeness": "accepted-step history",
        })
    return result


def _balance_tolerance(metadata: Mapping[str, Any]) -> dict[str, float | None]:
    """Read a declared report tolerance without creating an acceptance gate."""

    raw = metadata.get("report_balance_tolerance", metadata.get("balance_tolerance"))
    if not isinstance(raw, Mapping):
        return {"absolute": None, "normalized": None}
    values: dict[str, float | None] = {}
    for name in ("absolute", "normalized"):
        try:
            value = float(raw.get(name))
        except (TypeError, ValueError):
            value = float("nan")
        values[name] = value if np.isfinite(value) and value >= 0.0 else None
    return values


def _balance_series_summary(
    label: str, units: str, rows: Sequence[Mapping[str, Any]], *, tolerance: Mapping[str, float | None]
) -> dict[str, Any]:
    """Summarize signed rate residuals on their persisted accepted-step times."""

    by_time: dict[float, list[Mapping[str, Any]]] = {}
    for row in rows:
        by_time.setdefault(float(row["time_sec"]), []).append(row)
    times = np.asarray(sorted(by_time), dtype=float)
    residual = np.asarray([sum(float(item["residual"]) for item in by_time[time]) for time in times], dtype=float)
    normalized = np.asarray([
        max(abs(float(item["normalized_residual"])) for item in by_time[time]) for time in times
    ], dtype=float)
    worst_index = int(np.argmax(np.abs(residual)))
    worst_rows = by_time[float(times[worst_index])]
    worst_row = max(worst_rows, key=lambda item: abs(float(item["residual"])))
    window_start = max(float(times[0]), float(times[-1]) - BALANCE_FINAL_WINDOW_SEC)
    final_mask = times >= window_start
    absolute_tolerance = tolerance.get("absolute")
    normalized_tolerance = tolerance.get("normalized")
    checks = []
    if absolute_tolerance is not None:
        checks.append(float(np.max(np.abs(residual))) <= absolute_tolerance)
    if normalized_tolerance is not None:
        checks.append(float(np.max(normalized)) <= normalized_tolerance)
    return {
        "quantity": label, "units": units,
        "maximum_absolute_residual": float(np.max(np.abs(residual))),
        "maximum_normalized_residual": float(np.max(normalized)),
        "integrated_absolute_residual": float(getattr(np, "trapezoid", np.trapz)(np.abs(residual), times)) if times.size > 1 else 0.0,
        "integrated_residual_units": units.replace("/h", "") if units.endswith("/h") else f"{units} s",
        "final_window_start_sec": window_start, "final_window_end_sec": float(times[-1]),
        "final_window_maximum_absolute_residual": float(np.max(np.abs(residual[final_mask]))),
        "worst_time_sec": float(times[worst_index]), "worst_location": worst_row.get("volume", "Not reported"),
        "tolerance_absolute": absolute_tolerance, "tolerance_normalized": normalized_tolerance,
        "status": "PASS" if checks and all(checks) else ("FAIL" if checks else "NOT EVALUATED"),
        "data_state": "derived",
    }


def _balance_summary(rows: list[dict[str, Any]], *, metadata: Mapping[str, Any]) -> dict[str, Any]:
    if not rows:
        return {"status": "NOT EVALUATED", "detail": "Balance detail: aggregate maximum only; signed per-volume ledger unavailable.", "data_state": "not_available"}
    residuals = np.asarray([float(row["residual"]) for row in rows], dtype=float)
    normalized = np.asarray([float(row["normalized_residual"]) for row in rows], dtype=float)
    component_rows = [row for row in rows if row.get("quantity") != "energy"]
    energy_rows = [row for row in rows if row.get("quantity") == "energy"]
    per_volume_energy = any(str(row.get("volume", "global")) != "global" for row in energy_rows)
    material_has_separate_terms = bool(component_rows) and all(
        row.get("out") is not None for row in component_rows
    )
    energy_has_separate_terms = bool(energy_rows) and all(
        row.get("out") is not None for row in energy_rows
    )
    detail = (
        "Signed global component and per-volume energy ledgers are available; "
        "no report-level balance tolerance is configured."
        if per_volume_energy
        else "Signed global component and energy ledgers are available; "
        "no report-level balance tolerance is configured."
    )
    if not material_has_separate_terms or not energy_has_separate_terms:
        detail += " This artifact records net expected change rather than a separate In/Out split where shown."
    times = sorted({float(row["time_sec"]) for row in rows})
    tolerance = _balance_tolerance(metadata)
    component_summaries = [
        _balance_series_summary(
            component_name,
            "lbmol/h",
            [row for row in component_rows if str(row.get("quantity")) == component_name],
            tolerance=tolerance,
        )
        for component_name in sorted({str(row.get("quantity")) for row in component_rows})
    ]
    summaries = list(component_summaries)
    if component_rows:
        summaries.insert(0, _balance_series_summary("total material", "lbmol/h", component_rows, tolerance=tolerance))
    if energy_rows:
        summaries.append(_balance_series_summary("energy", "BTU/h", energy_rows, tolerance=tolerance))

    def interval(label: str, time_sec: float) -> dict[str, Any]:
        interval_rows = [row for row in rows if float(row["time_sec"]) == time_sec]
        return {
            "label": label,
            "time_sec": time_sec,
            "data_state": "observed",
            "rows": interval_rows,
            "maximum_absolute_residual": max(abs(float(row["residual"])) for row in interval_rows),
            "maximum_normalized_residual": max(float(row["normalized_residual"]) for row in interval_rows),
        }

    return {"status": "NOT EVALUATED", "detail": detail, "data_state": "derived", "maximum_absolute_residual": float(np.max(np.abs(residuals))), "maximum_normalized_residual": float(np.max(normalized)), "component_ledger_rows": len(component_rows), "energy_ledger_rows": len(energy_rows), "material_has_separate_in_out": material_has_separate_terms, "energy_has_separate_in_out": energy_has_separate_terms, "tolerance": tolerance, "summaries": summaries, "initial_interval": interval("Initial accepted interval", times[0]), "final_interval": interval("Final accepted interval", times[-1]), "ledger_rows": rows}


def _profile_assessment(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"data_state": "not_available"}
    temperature = [float(row["temperature_F"]) for row in rows]
    pressure = [float(row["pressure_psia"]) for row in rows]
    liquid_flows = [row.get("liquid_flow_out_lbmolph") for row in rows]
    vapor_flows = [row.get("vapor_flow_out_lbmolph") for row in rows]
    return {"data_state": "observed", "feed_stage": next((int(row["stage"]) for row in rows if row.get("node_type") == "feed_tray"), None), "top_to_bottom_pressure_drop_psia": float(pressure[-1] - pressure[0]), "temperature_minimum_F": min(temperature), "temperature_maximum_F": max(temperature), "flow_reversals": {"liquid": [row.get("volume") for row, value in zip(rows, liquid_flows, strict=True) if value is not None and float(value) < 0.0], "vapor": [row.get("volume") for row, value in zip(rows, vapor_flows, strict=True) if value is not None and float(value) < 0.0]}, "non_stage_nodes": [row.get("volume") for row in rows if row.get("node_type") != "tray"], "composition_extrema": {"liquid": {component: {"minimum": min(float(row["liquid_mole_fraction"][component]) for row in rows), "maximum": max(float(row["liquid_mole_fraction"][component]) for row in rows)} for component in rows[0].get("liquid_mole_fraction", {})}, "vapor": {component: {"minimum": min(float(row["vapor_mole_fraction"][component]) for row in rows), "maximum": max(float(row["vapor_mole_fraction"][component]) for row in rows)} for component in rows[0].get("vapor_mole_fraction", {})}}}


def build_report_summary_v2(
    end_summary: Mapping[str, Any], *, metadata: Mapping[str, Any] | None = None,
    trajectory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an additive report contract from current Core V3 artifacts.

    The builder is intentionally tolerant of v1 summaries so archived runs can
    be rendered with their limited evidence called out explicitly.
    """
    metadata = metadata or {}
    accepted_step_rows = _jsonl(metadata.get("report_trajectory_jsonl"))
    event_rows = sorted(_jsonl(metadata.get("report_events_jsonl")), key=lambda item: (float(item.get("time_sec", 0.0)), str(item.get("event_id", ""))))
    balance_rows = _jsonl(metadata.get("report_balance_ledger_jsonl"))
    steady = end_summary["steady_state"]
    completed = bool(metadata.get("completed", metadata.get("pass_gate", True)))
    explicit = str(metadata.get("overall_status", metadata.get("classification", ""))).upper()
    failed_gate = any(not passed for passed in (metadata.get("gates") or {}).values())
    overall = "FAIL" if (not completed or failed_gate) else (explicit if explicit in {"PASS", "REVIEW", "FAIL"} else ("PASS" if steady.get("steady") else "REVIEW"))
    terms = steady.get("terms", {})
    raw = steady.get("raw", {})
    controlling = max(terms, key=lambda key: (float(terms[key]), key)) if terms else None
    reasons = []
    if not completed:
        reasons.append({"check_id": "RUN-COMPLETION", "severity": "error", "status": "FAIL", "observed": "incomplete", "limit": "completed", "units": None, "time_sec": None, "location": "run", "explanation": "Simulation did not complete.", "evidence": "run metadata"})
    if not steady.get("steady", False):
        reasons.append({"check_id": f"SS-{controlling or 'UNAVAILABLE'}", "severity": "warning", "status": "REVIEW", "observed": float(terms[controlling]) if controlling else None, "limit": 1.0, "units": "ratio to limit", "time_sec": end_summary.get("time_sec"), "location": controlling, "explanation": "Steady-state qualification was not met; the listed term controls the score.", "evidence": "end-of-run-summary-v1"})
    endpoint = dict(metadata.get("final_endpoint") or {})
    gate_evidence = {
        "SOLVER-SUCCESS": (endpoint.get("scipy_success"), True, None),
        "RESIDUAL-INFINITY-NORM": (endpoint.get("scaled_residual_inf_norm"), 1.0e-8, "scaled residual"),
        "JACOBIAN-RANK": (endpoint.get("jacobian_rank"), "full contract rank", "Jacobian"),
        "JACOBIAN-CONDITION": (endpoint.get("jacobian_condition"), 1.0e8, "condition number"),
        "PHYSICAL": (endpoint.get("physical_pass"), True, "physical state"),
        "HYDRAULIC-QUALITY": (endpoint.get("hydraulic_envelope_quality_pass"), True, "tray hydraulics"),
    }
    for name, passed in sorted((metadata.get("gates") or {}).items()):
        if not passed:
            observed, limit, location = gate_evidence.get(str(name), (False, True, "gate"))
            reasons.append({"check_id": str(name), "severity": "error", "status": "FAIL", "observed": observed, "limit": limit, "units": None, "time_sec": end_summary.get("time_sec"), "location": location or "gate", "explanation": f"Required gate {name} failed.", "evidence": "final endpoint metadata" if str(name) in gate_evidence else "run metadata"})
    reasons.sort(key=lambda item: ({"error": 0, "warning": 1}.get(item["severity"], 2), item["check_id"]))
    pressure = _series(trajectory, "pressure_psia")
    temperature = _series(trajectory, "temperature_F")
    liquid = _series(trajectory, "liquid_component_inventory_lbmol")
    vapor = _series(trajectory, "vapor_component_inventory_lbmol")
    metrics = [
        _metric("Distillate flow", _series(trajectory, "distillate_flow_lbmolph"), "lbmol/h"),
        _metric("Bottoms flow", _series(trajectory, "bottoms_flow_lbmolph"), "lbmol/h"),
        _metric("Condenser duty", _series(trajectory, "condenser_duty_BTUph"), "BTU/h"),
        _metric("Top pressure", pressure[:, 0] if pressure is not None and pressure.ndim == 2 else None, "psia"),
        _metric("Bottom pressure", pressure[:, -1] if pressure is not None and pressure.ndim == 2 else None, "psia"),
        _metric("Top temperature", temperature[:, 0] if temperature is not None and temperature.ndim == 2 else None, "F"),
        _metric("Bottom temperature", temperature[:, -1] if temperature is not None and temperature.ndim == 2 else None, "F"),
        _metric("Total liquid inventory", np.sum(liquid, axis=(1, 2)) if liquid is not None and liquid.ndim == 3 else None, "lbmol"),
        _metric("Total vapor inventory", np.sum(vapor, axis=(1, 2)) if vapor is not None and vapor.ndim == 3 else None, "lbmol"),
    ]
    if accepted_step_rows:
        metrics.extend([
            _metric("Feed flow", np.asarray([sum(map(float, row["feed_component_lbmolph"])) for row in accepted_step_rows], dtype=float) if all("feed_component_lbmolph" in row for row in accepted_step_rows) else None, "lbmol/h"),
            _metric("Reflux flow", _accepted_series(accepted_step_rows, "reflux_flow_lbmolph"), "lbmol/h"),
            _metric("Top pressure", _accepted_series(accepted_step_rows, "top_pressure_psia"), "psia"),
            _metric("Bottom pressure", _accepted_series(accepted_step_rows, "bottom_pressure_psia"), "psia"),
            _metric("Top temperature", _accepted_series(accepted_step_rows, "top_temperature_F"), "F"),
            _metric("Bottom temperature", _accepted_series(accepted_step_rows, "bottom_temperature_F"), "F"),
            _metric("Distillate drum level", _accepted_series(accepted_step_rows, "drum_level_fraction"), "fraction"),
            _metric("Bottoms sump level", _accepted_series(accepted_step_rows, "sump_level_fraction"), "fraction"),
        ])
        first_feed = accepted_step_rows[0].get("feed_component_lbmolph", ())
        for index in range(len(first_feed)):
            component_values = np.asarray([float(row["feed_component_lbmolph"][index]) for row in accepted_step_rows], dtype=float)
            metrics.append(_metric(f"Feed component {index + 1}", component_values, "lbmol/h"))
    constraints = [
        {"check": "positive inventories", "variable": "liquid/vapor inventory", "limit": "> 0", "observed": float(min(np.min(liquid), np.min(vapor))) if liquid is not None and vapor is not None else None, "time_sec": None, "location": "all volumes", "status": "PASS" if liquid is not None and vapor is not None and min(np.min(liquid), np.min(vapor)) > 0 else "NOT EVALUATED", "evidence": "trajectory" if liquid is not None and vapor is not None else "not available"},
        {"check": "mole fractions", "variable": "phase composition", "limit": "[0, 1]", "observed": "not recomputed", "time_sec": None, "location": "all volumes", "status": "NOT EVALUATED", "evidence": "composition history not supplied to report layer"},
    ]
    complete_endpoint_rows = [
        row for row in accepted_step_rows
        if {"liquid_inventory_lbmol", "vapor_inventory_lbmol", "solver_residual_inf_norm"}.issubset(row)
    ]
    if complete_endpoint_rows:
        inventory_min = min(
            min(float(row["liquid_inventory_lbmol"]), float(row["vapor_inventory_lbmol"]))
            for row in complete_endpoint_rows
        )
        residual_max = max(float(row["solver_residual_inf_norm"]) for row in complete_endpoint_rows)
        constraints.extend([
            {"check": "positive inventories", "variable": "total liquid/vapor inventory", "limit": "> 0", "observed": inventory_min, "time_sec": None, "location": "column", "status": "PASS" if inventory_min > 0 else "FAIL", "evidence": "accepted-step trajectory"},
            {"check": "solver residual", "variable": "scaled residual infinity norm", "limit": "< 1e-8", "observed": residual_max, "time_sec": None, "location": "solver", "status": "PASS" if residual_max < 1.0e-8 else "FAIL", "evidence": "accepted-step trajectory"},
        ])
    composition_rows = [row for row in accepted_step_rows if "distillate_mole_fraction" in row and "bottoms_mole_fraction" in row]
    if composition_rows:
        fractions = [float(value) for row in composition_rows for stream in (row["distillate_mole_fraction"], row["bottoms_mole_fraction"]) for value in stream.values()]
        constraints.append({"check": "product mole fractions", "variable": "distillate/bottoms composition", "limit": "[0, 1]", "observed": {"minimum": min(fractions), "maximum": max(fractions)}, "time_sec": None, "location": "products", "status": "PASS" if min(fractions) >= 0.0 and max(fractions) <= 1.0 else "FAIL", "evidence": "accepted-step trajectory"})
    level_rows = [row for row in accepted_step_rows if "drum_level_fraction" in row and "sump_level_fraction" in row]
    if level_rows:
        level_min = min(min(float(row["drum_level_fraction"]), float(row["sump_level_fraction"])) for row in level_rows)
        level_max = max(max(float(row["drum_level_fraction"]), float(row["sump_level_fraction"])) for row in level_rows)
        constraints.append({"check": "terminal geometry levels", "variable": "drum/sump level fraction", "limit": "[0, 1]", "observed": {"minimum": level_min, "maximum": level_max}, "time_sec": None, "location": "terminals", "status": "PASS" if level_min >= 0.0 and level_max <= 1.0 else "FAIL", "evidence": "accepted-step trajectory"})
    times = np.asarray([float(row["time_sec"]) for row in accepted_step_rows], dtype=float)
    severity = [str(row.get("severity", "")).lower() for row in event_rows]
    health = {"data_state": "observed", "provider_calls": metadata.get("provider_calls"), "performance": metadata.get("performance", {}), "integrator": "implicit nonlinear endpoint solve", "configured_timestep_sec": metadata.get("timestep_sec", metadata.get("dt_sec")), "configured_max_function_evaluations_per_root": metadata.get("max_nfev_per_root"), "accepted_steps": len(accepted_step_rows), "rejected_steps": "not_available", "event_count": len(event_rows), "warning_count": int(sum(value == "warning" for value in severity)), "error_count": int(sum(value in {"error", "critical"} for value in severity)), "termination_reason": metadata.get("termination_reason", metadata.get("status", "not_available"))}
    if times.size > 1:
        steps = np.diff(times)
        health["actual_timestep_min_sec"] = float(np.min(steps))
        health["actual_timestep_max_sec"] = float(np.max(steps))
        health["actual_timestep_mean_sec"] = float(np.mean(steps))
    if complete_endpoint_rows:
        health["maximum_residual_infinity_norm"] = max(float(row["solver_residual_inf_norm"]) for row in complete_endpoint_rows)
        health["maximum_jacobian_condition"] = max(float(row["jacobian_condition"]) for row in complete_endpoint_rows)
    nfev = _accepted_series(accepted_step_rows, "nfev")
    njev = _accepted_series(accepted_step_rows, "njev")
    if nfev is not None:
        health["nonlinear_function_evaluations_total"] = int(np.sum(nfev))
        health["nonlinear_function_evaluations_maximum"] = int(np.max(nfev))
    if njev is not None:
        health["jacobian_evaluations_total"] = int(np.sum(njev))
    retry_values = [bool(row.get("retry_attempted", False)) for row in accepted_step_rows if "retry_attempted" in row]
    if retry_values:
        health["solver_retry_count"] = int(sum(retry_values))
    profiles = end_summary.get("profiles", [])
    return {"report_schema_version": REPORT_SCHEMA_VERSION, "source_summary_schema": end_summary.get("schema_id", "unknown"), "run_id": metadata.get("run_id", metadata.get("case_id", "Not recorded")), "overall_status": overall, "completion": {"status": "PASS" if completed else "FAIL", "data_state": "observed"}, "steady_state": {**steady, "status": "PASS" if steady.get("steady") else "REVIEW", "controlling_term": controlling, "score_limit": 1.0, "minimum_time_sec": 60.0, "data_state": "derived"}, "verdict_reasons": reasons, "initial_final_delta": metrics, "constraints": constraints, "balances": _balance_summary(balance_rows, metadata=metadata), "controllers": _controller_kpis(accepted_step_rows, metadata=metadata), "events": {"status": "AVAILABLE" if event_rows else "NOT AVAILABLE", "detail": "Structured event stream available." if event_rows else "Event timeline: not available in this artifact version.", "data_state": "observed" if event_rows else "not_available", "records": event_rows}, "numerical_health": health, "accepted_step_trajectory": {"record_count": len(accepted_step_rows), "data_state": "observed" if accepted_step_rows else "not_available"}, "profiles": profiles, "profile_assessment": _profile_assessment(profiles), "products": end_summary.get("products", {}), "duties": end_summary.get("duties", {}), "terminal_levels": end_summary.get("terminal_levels", {}), "provenance": {"input_workbook": metadata.get("workbook", metadata.get("excel_path")), "launch_command": metadata.get("launch_command"), "source_checkpoint": metadata.get("started_from_checkpoint"), "timestep_sec": metadata.get("timestep_sec", metadata.get("dt_sec")), "completed_duration_sec": end_summary.get("time_sec")}, "artifacts": _artifact_index(metadata)}


def build_report_summary_from_tabular_v2(
    rows: Sequence[Mapping[str, Any]], *, metadata: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Adapt existing Core V3 summary-CSV rows without changing their schema.

    This is deliberately a lossy adapter: values absent from the older CSV are
    represented as unavailable by :func:`build_report_summary_v2`, never filled
    from a final endpoint.
    """
    if not rows:
        raise ValueError("at least one summary row is required")
    def values(key: str) -> np.ndarray | None:
        try:
            result = np.asarray([float(row[key]) for row in rows], dtype=float)
        except (KeyError, TypeError, ValueError):
            return None
        return result if np.all(np.isfinite(result)) else None

    final = rows[-1]
    steady_terms = {
        "relative_state_rate": final.get("ss_max_rel_state_rate_per_s"),
        "temperature_rate": final.get("ss_max_temp_rate_F_per_s"),
        "product_composition_slope": final.get("ss_max_kpi_slope_per_s"),
        "product_flow_rate": final.get("ss_max_mv_rate_per_s"),
        "global_inventory_rate": final.get("ss_global_inventory_rate_frac_feed"),
    }
    tolerances = {
        "relative_state_rate": 3.0e-3,
        "temperature_rate": 0.15,
        "product_composition_slope": 1.0e-4,
        "product_flow_rate": 20.0,
        "global_inventory_rate": 0.01,
    }
    score = float(final.get("steady_state_score", np.nan))
    end_summary = {
        "schema_id": "core-v3-summary-csv-adapter-v1",
        "time_sec": float(final.get("time_s", 0.0)),
        "duties": {"condenser_BTUph": final.get("Q_cond_used_BTUph"), "reboiler_BTUph": final.get("Q_reb_used_BTUph")},
        "products": {}, "terminal_levels": {}, "profiles": [],
        "steady_state": {
            "score": score, "steady": bool(final.get("steady_state_flag", False)),
            "terms": {key: float(value) / tolerances[key] for key, value in steady_terms.items() if value is not None},
            "raw": {key: value for key, value in steady_terms.items() if value is not None},
        },
    }
    trajectory = {
        "distillate_flow_lbmolph": values("D_lbmolph"),
        "bottoms_flow_lbmolph": values("B_lbmolph"),
        "condenser_duty_BTUph": values("Q_cond_used_BTUph"),
    }
    return build_report_summary_v2(end_summary, metadata=metadata, trajectory=trajectory)


def format_report_summary_v2(report: Mapping[str, Any]) -> str:
    """Deterministic plain-text decision report for logs and test fixtures."""
    lines = ["CORE V3 END-OF-RUN REPORT", f"Overall status: {report['overall_status']}", f"Simulation completed: {report['completion']['status']}", f"Steady state: {report['steady_state']['status']}", "", "RANKED VERDICT REASONS"]
    if report["verdict_reasons"]:
        lines.extend(
            f"{item['check_id']} | {item['severity']} | {item['status']} | {item['explanation']}"
            for item in report["verdict_reasons"]
        )
    else:
        lines.append("None reported")
    lines.extend(["", "INITIAL / FINAL / DELTA"])
    for item in report["initial_final_delta"]:
        final = item["final"]
        lines.append(f"{item['variable']}: {final['value'] if final['data_state'] == 'observed' else 'Not reported'} {item['units']}")
    lines.extend(["", "STEADY-STATE ASSESSMENT"])
    for name, value in sorted(report["steady_state"].get("terms", {}).items()):
        lines.append(f"{name}: {value:.6g} of limit")
    lines.extend(["", "BALANCE SUMMARY", report["balances"]["detail"]])
    for item in report["balances"].get("summaries", []):
        lines.append(
            f"{item['quantity']} ({item['units']}): max abs residual "
            f"{item['maximum_absolute_residual']:.6g}; max normalized "
            f"{item['maximum_normalized_residual']:.6g}; integrated abs residual "
            f"{item['integrated_absolute_residual']:.6g} {item['integrated_residual_units']}; "
            f"final-window max {item['final_window_maximum_absolute_residual']:.6g}; "
            f"worst at {item['worst_time_sec']:.6g} s ({item['worst_location']}); "
            f"{item['status']}"
        )
    for key in ("initial_interval", "final_interval"):
        interval = report["balances"].get(key)
        if interval:
            lines.append(
                f"{interval['label']} at {interval['time_sec']:.6g} s: "
                f"max abs residual {interval['maximum_absolute_residual']:.6g}; "
                f"max normalized residual {interval['maximum_normalized_residual']:.6g}"
            )
    lines.extend(["", "CONTROLLER PERFORMANCE"])
    if report["controllers"]:
        lines.extend(
            f"{item['controller']} ({item['controlled_variable']}): final error {item['final_error']:.6g}; "
            f"max/mean abs error {item['maximum_absolute_error']:.6g}/{item['mean_absolute_error']:.6g}; "
            f"IAE {item['integral_absolute_error'] if item['integral_absolute_error'] is not None else 'Not reported'}; "
            f"overshoot/undershoot {item['overshoot']:.6g}/{item['undershoot']:.6g}; "
            f"output range {item['output_minimum'] if item['output_minimum'] is not None else 'Not reported'} to "
            f"{item['output_maximum'] if item['output_maximum'] is not None else 'Not reported'} {item['output_units']}; "
            f"settling {item['settling_time_sec'] if item['settling_time_sec'] is not None else 'Not evaluated'} s "
            f"({item['settling_data_state']}); saturation {item['saturation_data_state']}"
            for item in report["controllers"]
        )
    else:
        lines.append("Controller performance: not available in this artifact version.")
    lines.extend(["", "NUMERICAL HEALTH"])
    lines.extend(
        f"{key}: {value}"
        for key, value in sorted(report["numerical_health"].items())
        if key not in {"data_state", "performance"} and value is not None
    )
    lines.extend(["", "EVENT TIMELINE", report["events"]["detail"], "", "ARTIFACT INDEX"])
    if report["artifacts"]:
        lines.extend(
            f"{item['artifact']} | {item['path']} | {item['status']}"
            for item in report["artifacts"]
        )
    else:
        lines.append("Not reported")
    return "\n".join(lines)


__all__ = ["REPORT_SCHEMA_VERSION", "build_report_summary_from_tabular_v2", "build_report_summary_v2", "format_report_summary_v2"]
