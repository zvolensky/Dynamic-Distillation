#!/usr/bin/env python
"""Plot the retained Core V3 distillate n-butane tuning comparison."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
SETPOINT = 0.11987175180429868
FORMER_DIAGNOSTIC_OFFSET = 0.002

CASES = (
    {
        "label": "Composition Kc = 5,000 lbmol/h per mole fraction",
        "preflight": ROOT
        / "logs/core_v3_pressure_kc3m_feedT_plus5F_preflight_20260830/column_summary_20260830_192306.csv",
        "continuation": ROOT
        / "logs/core_v3_pressure_kc3m_feedT_plus5F_600s_20260830/column_summary_20260830_192407.csv",
        "final_time_s": 355.0,
        "final_error": 0.002001574239445955,
        "color": "#2563eb",
    },
    {
        "label": "Composition Kc = 30,000 lbmol/h per mole fraction",
        "preflight": ROOT
        / "logs/core_v3_kc3m_compkc30k_feedT_plus5F_preflight_20260830/column_summary_20260830_195142.csv",
        "continuation": ROOT
        / "logs/core_v3_kc3m_compkc30k_feedT_plus5F_600s_20260830/column_summary_20260830_195242.csv",
        "continuation_tail": ROOT
        / "logs/core_v3_kc3m_compkc30k_feedT_plus5F_complete600s_20260830/column_summary_20260830_204510.csv",
        "tail_offset_s": 360.5,
        "final_time_s": 600.0,
        "final_error": 0.003784724999292541,
        "color": "#ea580c",
    },
)


def _first_row(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as stream:
        return next(csv.DictReader(stream))


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _series(case: dict[str, object]) -> tuple[list[float], list[float]]:
    preflight = _first_row(Path(case["preflight"]))
    times = [0.5]
    values = [float(preflight["Composition_ctrl_PV_molfrac"])]
    for row in _rows(Path(case["continuation"])):
        # The continuation clock restarts after the accepted 0.5 s preflight.
        times.append(0.5 + float(row["time_s"]))
        values.append(float(row["Composition_ctrl_PV_molfrac"]))
    if "continuation_tail" in case:
        for row in _rows(Path(case["continuation_tail"])):
            times.append(float(case["tail_offset_s"]) + float(row["time_s"]))
            values.append(float(row["Composition_ctrl_PV_molfrac"]))
    times.append(float(case["final_time_s"]))
    values.append(SETPOINT + float(case["final_error"]))
    ordered = sorted(zip(times, values), key=lambda item: item[0])
    return [item[0] for item in ordered], [100.0 * item[1] for item in ordered]


def main() -> int:
    output_dir = ROOT / "logs/core_v3_composition_tuning_comparison_20260830"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "distillate_xc4_comparison.png"

    fig, axis = plt.subplots(figsize=(11.5, 6.5), dpi=160)
    for case in CASES:
        times, values = _series(case)
        axis.plot(
            times,
            values,
            color=str(case["color"]),
            linewidth=2.4,
            marker="o",
            markersize=4.5,
            label=str(case["label"]),
        )
        axis.scatter(
            [times[-1]],
            [values[-1]],
            color=str(case["color"]),
            edgecolor="white",
            linewidth=1.2,
            s=70,
            zorder=5,
        )

    setpoint_percent = 100.0 * SETPOINT
    former_upper_percent = 100.0 * (SETPOINT + FORMER_DIAGNOSTIC_OFFSET)
    axis.axhline(
        setpoint_percent,
        color="#475569",
        linestyle="--",
        linewidth=1.5,
        label=f"Controller setpoint ({setpoint_percent:.4f} mol%)",
    )
    axis.axhline(
        former_upper_percent,
        color="#dc2626",
        linestyle=":",
        linewidth=1.8,
        label=(
            "Former +0.002 diagnostic threshold "
            f"({former_upper_percent:.4f} mol%; not a product specification)"
        ),
    )

    axis.set_title(
        "Distillate n-Butane Response to a +5 °F Feed-Temperature Step",
        fontsize=15,
        pad=14,
    )
    axis.set_xlabel("Time after disturbance (s)", fontsize=11)
    axis.set_ylabel("Distillate n-butane, x-C4 (mol%)", fontsize=11)
    axis.set_xlim(0.0, 620.0)
    axis.grid(True, color="#cbd5e1", linewidth=0.7, alpha=0.75)
    axis.legend(loc="upper left", frameon=True, framealpha=0.96, fontsize=9)
    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
