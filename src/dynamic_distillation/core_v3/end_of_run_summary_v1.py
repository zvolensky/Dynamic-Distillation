"""Generic end-of-run operating summary for Core V3 dynamic trajectories."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .vapor_holdup_terminal_control_contract_v1 import (
    VaporHoldupTerminalGeometry,
    terminal_level_fractions,
)


SS_REL_RATE_TOL_PER_SEC = 3.0e-3
SS_TEMP_RATE_TOL_F_PER_SEC = 0.15
SS_KPI_SLOPE_TOL_PER_SEC = 1.0e-4
SS_MV_RATE_TOL_LBMOLPH_PER_SEC = 20.0
SS_GLOBAL_RATE_TOL_FRAC_FEED = 0.01
SS_RATE_DENOM_FLOOR_LBMOL = 1.0
SS_WINDOW_SEC = 30.0
SS_MIN_TIME_SEC = 60.0


def _array(values: Any, *, name: str, ndim: int) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.ndim != ndim or np.any(~np.isfinite(result)):
        raise ValueError(f"{name} must be a finite {ndim}-D array")
    return result


def _linear_slope(times: np.ndarray, values: np.ndarray) -> float:
    if times.size < 2 or float(np.ptp(times)) <= 0.0:
        return 0.0
    centered = times - float(np.mean(times))
    denominator = float(np.dot(centered, centered))
    if denominator <= 0.0:
        return 0.0
    return float(np.dot(centered, values - float(np.mean(values))) / denominator)


def _composition(inventory: np.ndarray) -> np.ndarray:
    totals = np.sum(inventory, axis=-1, keepdims=True)
    if np.any(inventory <= 0.0) or np.any(totals <= 0.0):
        raise ValueError("phase inventories must be strictly positive")
    return inventory / totals


def build_end_of_run_summary(
    *,
    component_names: Sequence[str],
    volume_ids: Sequence[str],
    node_types: Sequence[str],
    time_sec: Sequence[float],
    liquid_component_inventory_lbmol: Any,
    vapor_component_inventory_lbmol: Any,
    temperature_F: Any,
    pressure_psia: Any,
    hydraulic_liquid_flow_lbmolph: Any,
    hydraulic_volume_ids: Sequence[str],
    vapor_flow_lbmolph: Any,
    vapor_links: Sequence[tuple[str, str, str]],
    condenser_duty_BTUph: Sequence[float],
    reboiler_duty_BTUph: float,
    reflux_lbmolph: float,
    distillate_lbmolph: float,
    bottoms_lbmolph: float,
    feed_component_lbmolph: Sequence[float],
    final_liquid_density_lbmol_ft3: Sequence[float],
    final_liquid_enthalpy_BTU_lbmol: Sequence[float],
    final_vapor_enthalpy_BTU_lbmol: Sequence[float],
    terminal_geometry: VaporHoldupTerminalGeometry,
    distillate_flow_history_lbmolph: Sequence[float] | None = None,
    bottoms_flow_history_lbmolph: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Build duties, products, levels, steady score, and final profiles."""
    components = tuple(str(name) for name in component_names)
    volumes = tuple(str(name) for name in volume_ids)
    kinds = tuple(str(name) for name in node_types)
    times = _array(time_sec, name="time_sec", ndim=1)
    liquid = _array(
        liquid_component_inventory_lbmol,
        name="liquid_component_inventory_lbmol",
        ndim=3,
    )
    vapor = _array(
        vapor_component_inventory_lbmol,
        name="vapor_component_inventory_lbmol",
        ndim=3,
    )
    temperature = _array(temperature_F, name="temperature_F", ndim=2)
    pressure = _array(pressure_psia, name="pressure_psia", ndim=2)
    liquid_flow = _array(
        hydraulic_liquid_flow_lbmolph,
        name="hydraulic_liquid_flow_lbmolph",
        ndim=2,
    )
    vapor_flow = _array(vapor_flow_lbmolph, name="vapor_flow_lbmolph", ndim=2)
    condenser = _array(
        condenser_duty_BTUph, name="condenser_duty_BTUph", ndim=1
    )
    density = _array(
        final_liquid_density_lbmol_ft3,
        name="final_liquid_density_lbmol_ft3",
        ndim=1,
    )
    liquid_enthalpy = _array(
        final_liquid_enthalpy_BTU_lbmol,
        name="final_liquid_enthalpy_BTU_lbmol",
        ndim=1,
    )
    vapor_enthalpy = _array(
        final_vapor_enthalpy_BTU_lbmol,
        name="final_vapor_enthalpy_BTU_lbmol",
        ndim=1,
    )
    feed = _array(feed_component_lbmolph, name="feed_component_lbmolph", ndim=1)
    volume_count = len(volumes)
    component_count = len(components)
    if len(kinds) != volume_count:
        raise ValueError("node_types must align with volume_ids")
    expected_history = (times.size, volume_count, component_count)
    if liquid.shape != expected_history or vapor.shape != expected_history:
        raise ValueError("inventory histories do not align with time/volume/component ledgers")
    if temperature.shape != (times.size, volume_count) or pressure.shape != (
        times.size,
        volume_count,
    ):
        raise ValueError("temperature/pressure histories do not align with the volume ledger")
    if condenser.shape != (times.size,):
        raise ValueError("condenser duty history does not align with time")
    if density.shape != (volume_count,) or liquid_enthalpy.shape != (
        volume_count,
    ) or vapor_enthalpy.shape != (volume_count,):
        raise ValueError("final property arrays do not align with the volume ledger")
    if feed.shape != (component_count,) or np.any(feed < 0.0):
        raise ValueError("feed component ledger is invalid")
    if times.size < 2 or np.any(np.diff(times) <= 0.0):
        raise ValueError("end-of-run summary requires increasing trajectory times")

    distillate_history = (
        np.full(times.shape, float(distillate_lbmolph), dtype=float)
        if distillate_flow_history_lbmolph is None
        else _array(
            distillate_flow_history_lbmolph,
            name="distillate_flow_history_lbmolph",
            ndim=1,
        )
    )
    bottoms_history = (
        np.full(times.shape, float(bottoms_lbmolph), dtype=float)
        if bottoms_flow_history_lbmolph is None
        else _array(
            bottoms_flow_history_lbmolph,
            name="bottoms_flow_history_lbmolph",
            ndim=1,
        )
    )
    if distillate_history.shape != times.shape or bottoms_history.shape != times.shape:
        raise ValueError("product flow histories do not align with time")
    if np.any(distillate_history <= 0.0) or np.any(bottoms_history <= 0.0):
        raise ValueError("product flow histories must be positive")

    final_liquid = liquid[-1]
    final_vapor = vapor[-1]
    liquid_x = _composition(final_liquid)
    vapor_y = _composition(final_vapor)
    levels = terminal_level_fractions(final_liquid, density, terminal_geometry)
    top_index = 0
    bottom_index = volume_count - 1
    products = {
        "distillate": {
            "phase": "liquid",
            "flow_lbmolph": float(distillate_history[-1]),
            "temperature_F": float(temperature[-1, top_index]),
            "pressure_psia": float(pressure[-1, top_index]),
            "mole_fraction": {
                name: float(liquid_x[top_index, index])
                for index, name in enumerate(components)
            },
            "molar_enthalpy_BTU_lbmol": float(liquid_enthalpy[top_index]),
            "molar_density_lbmol_ft3": float(density[top_index]),
        },
        "bottoms": {
            "phase": "liquid",
            "flow_lbmolph": float(bottoms_history[-1]),
            "temperature_F": float(temperature[-1, bottom_index]),
            "pressure_psia": float(pressure[-1, bottom_index]),
            "mole_fraction": {
                name: float(liquid_x[bottom_index, index])
                for index, name in enumerate(components)
            },
            "molar_enthalpy_BTU_lbmol": float(liquid_enthalpy[bottom_index]),
            "molar_density_lbmol_ft3": float(density[bottom_index]),
        },
    }

    final_dt = float(times[-1] - times[-2])
    relative_rates = []
    for history in (liquid, vapor):
        rate_per_sec = (history[-1] - history[-2]) / final_dt
        relative_rates.append(
            np.abs(rate_per_sec)
            / (np.abs(history[-1]) + SS_RATE_DENOM_FLOOR_LBMOL)
        )
    max_relative_rate = float(max(np.max(block) for block in relative_rates))
    max_temperature_rate = float(
        np.max(np.abs((temperature[-1] - temperature[-2]) / final_dt))
    )
    total_before = float(np.sum(liquid[-2]) + np.sum(vapor[-2]))
    total_after = float(np.sum(liquid[-1]) + np.sum(vapor[-1]))
    feed_rate = float(np.sum(feed))
    global_rate_fraction = abs(
        (total_after - total_before) * 3600.0 / final_dt
    ) / max(feed_rate, 1.0e-300)
    window_start = float(times[-1] - SS_WINDOW_SEC)
    mask = times >= window_start - 1.0e-12
    window_times = times[mask]
    history_x = _composition(liquid[mask])
    kpi_slopes = []
    for component_index in range(component_count):
        kpi_slopes.append(
            abs(
                _linear_slope(
                    window_times, history_x[:, top_index, component_index]
                )
            )
        )
        kpi_slopes.append(
            abs(
                _linear_slope(
                    window_times, history_x[:, bottom_index, component_index]
                )
            )
        )
    max_kpi_slope = float(max(kpi_slopes, default=0.0))
    max_mv_rate = float(
        max(
            abs(distillate_history[-1] - distillate_history[-2]),
            abs(bottoms_history[-1] - bottoms_history[-2]),
        )
        / final_dt
    )
    score_terms = {
        "relative_state_rate": max_relative_rate / SS_REL_RATE_TOL_PER_SEC,
        "temperature_rate": max_temperature_rate / SS_TEMP_RATE_TOL_F_PER_SEC,
        "product_composition_slope": max_kpi_slope / SS_KPI_SLOPE_TOL_PER_SEC,
        "product_flow_rate": max_mv_rate / SS_MV_RATE_TOL_LBMOLPH_PER_SEC,
        "global_inventory_rate": global_rate_fraction / SS_GLOBAL_RATE_TOL_FRAC_FEED,
    }
    steady_score = float(max(score_terms.values()))

    liquid_flow_map = {
        str(volume): float(liquid_flow[-1, index])
        for index, volume in enumerate(hydraulic_volume_ids)
    }
    liquid_flow_map[volumes[0]] = float(reflux_lbmolph)
    liquid_flow_map[volumes[-1]] = float(bottoms_history[-1])
    vapor_flow_map = {
        str(source): float(vapor_flow[-1, index])
        for index, (source, _destination, _symbol) in enumerate(vapor_links)
    }
    profiles = []
    for index, (volume, node_type) in enumerate(zip(volumes, kinds, strict=True)):
        profiles.append(
            {
                "stage": index + 1,
                "volume": volume,
                "node_type": node_type,
                "temperature_F": float(temperature[-1, index]),
                "pressure_psia": float(pressure[-1, index]),
                "liquid_inventory_lbmol": float(np.sum(final_liquid[index])),
                "vapor_inventory_lbmol": float(np.sum(final_vapor[index])),
                "liquid_flow_out_lbmolph": liquid_flow_map.get(volume),
                "vapor_flow_out_lbmolph": vapor_flow_map.get(volume),
                "liquid_mole_fraction": {
                    name: float(liquid_x[index, component_index])
                    for component_index, name in enumerate(components)
                },
                "vapor_mole_fraction": {
                    name: float(vapor_y[index, component_index])
                    for component_index, name in enumerate(components)
                },
                "liquid_enthalpy_BTU_lbmol": float(liquid_enthalpy[index]),
                "vapor_enthalpy_BTU_lbmol": float(vapor_enthalpy[index]),
            }
        )
    return {
        "schema_id": "core-v3-end-of-run-summary-v1",
        "time_sec": float(times[-1]),
        "duties": {
            "condenser_BTUph": float(condenser[-1]),
            "reboiler_BTUph": float(reboiler_duty_BTUph),
        },
        "products": products,
        "terminal_levels": {
            "distillate_drum_fraction": float(levels[0]),
            "bottom_drum_fraction": float(levels[1]),
        },
        "steady_state": {
            "score": steady_score,
            "steady": bool(times[-1] >= SS_MIN_TIME_SEC and steady_score <= 1.0),
            "criterion": "score <= 1.0 after at least 60 seconds",
            "terms": {name: float(value) for name, value in score_terms.items()},
            "raw": {
                "maximum_relative_state_rate_per_s": max_relative_rate,
                "maximum_temperature_rate_F_per_s": max_temperature_rate,
                "maximum_product_composition_slope_per_s": max_kpi_slope,
                "maximum_product_flow_rate_lbmolph_per_s": max_mv_rate,
                "global_inventory_rate_fraction_feed": global_rate_fraction,
            },
        },
        "profiles": profiles,
    }


def format_end_of_run_summary(summary: Mapping[str, Any]) -> str:
    """Format the operating summary with profiles as the final section."""
    duties = summary["duties"]
    products = summary["products"]
    levels = summary["terminal_levels"]
    steady = summary["steady_state"]
    lines = [
        "END-OF-RUN OPERATING SUMMARY",
        f"Time: {float(summary['time_sec']):.3f} s",
        f"Qc: {float(duties['condenser_BTUph']):.6f} BTU/h",
        f"Qr: {float(duties['reboiler_BTUph']):.6f} BTU/h",
    ]
    for key, label in (("distillate", "Distillate"), ("bottoms", "Bottoms")):
        stream = products[key]
        composition = ", ".join(
            f"x({name})={float(value):.8f}"
            for name, value in stream["mole_fraction"].items()
        )
        lines.append(
            f"{label}: F={float(stream['flow_lbmolph']):.6f} lbmol/h, "
            f"T={float(stream['temperature_F']):.6f} F, "
            f"P={float(stream['pressure_psia']):.6f} psia, "
            f"h={float(stream['molar_enthalpy_BTU_lbmol']):.6f} BTU/lbmol, "
            f"{composition}"
        )
    lines.extend(
        (
            f"Distillate drum level: {100.0 * float(levels['distillate_drum_fraction']):.6f}%",
            f"Bottom drum level: {100.0 * float(levels['bottom_drum_fraction']):.6f}%",
            f"Steady-state score: {float(steady['score']):.8g} "
            f"({'steady' if steady['steady'] else 'not steady'}; criterion <= 1.0)",
            "",
            "FINAL TRAY PROFILES",
        )
    )
    components = tuple(products["distillate"]["mole_fraction"].keys())
    composition_headers = [
        *(f"x_{name}" for name in components),
        *(f"y_{name}" for name in components),
    ]
    headers = [
        "Stage",
        "Volume",
        "Type",
        "T_F",
        "P_psia",
        "ML_lbmol",
        "MV_lbmol",
        "Lout_lbmolph",
        "Vout_lbmolph",
        *composition_headers,
    ]
    lines.append(" | ".join(headers))
    for row in summary["profiles"]:
        values = [
            str(int(row["stage"])),
            str(row["volume"]),
            str(row["node_type"]),
            f"{float(row['temperature_F']):.6f}",
            f"{float(row['pressure_psia']):.6f}",
            f"{float(row['liquid_inventory_lbmol']):.6f}",
            f"{float(row['vapor_inventory_lbmol']):.6f}",
            (
                "-"
                if row["liquid_flow_out_lbmolph"] is None
                else f"{float(row['liquid_flow_out_lbmolph']):.6f}"
            ),
            (
                "-"
                if row["vapor_flow_out_lbmolph"] is None
                else f"{float(row['vapor_flow_out_lbmolph']):.6f}"
            ),
            *(
                f"{float(row['liquid_mole_fraction'][name]):.8f}"
                for name in components
            ),
            *(
                f"{float(row['vapor_mole_fraction'][name]):.8f}"
                for name in components
            ),
        ]
        lines.append(" | ".join(values))
    return "\n".join(lines)


__all__ = [
    "build_end_of_run_summary",
    "format_end_of_run_summary",
]
