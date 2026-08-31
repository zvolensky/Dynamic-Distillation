#!/usr/bin/env python
"""Plot final profiles for the completed Core V3 +5 F disturbance run."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
PROFILE = (
    ROOT
    / "logs/core_v3_kc3m_compkc30k_feedT_plus5F_complete600s_20260830"
    / "column_profile_20260830_204510.csv"
)
OUTPUT = (
    ROOT
    / "logs/core_v3_kc3m_compkc30k_feedT_plus5F_complete600s_20260830"
    / "final_stage_profiles.png"
)


def _number(row: dict[str, str], key: str) -> float:
    value = row[key]
    return float(value) if value else float("nan")


def main() -> int:
    with PROFILE.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    final_time = max(float(row["time_s"]) for row in rows)
    rows = [row for row in rows if float(row["time_s"]) == final_time]

    stage = [_number(row, "stage") for row in rows]
    colors = {
        "n-Propane": "#2563eb",
        "n-Butane": "#ea580c",
        "n-Pentane": "#16a34a",
    }

    fig, axes = plt.subplots(2, 2, figsize=(14, 9), dpi=160)

    temperature_axis = axes[0, 0]
    pressure_axis = temperature_axis.twinx()
    temperature_axis.plot(stage, [_number(r, "T_F") for r in rows], "o-", color="#dc2626", label="Temperature")
    pressure_axis.plot(stage, [_number(r, "P_psia_hyd") for r in rows], "s-", color="#475569", label="Pressure")
    temperature_axis.set_title("Temperature and Pressure")
    temperature_axis.set_ylabel("Temperature (°F)", color="#dc2626")
    pressure_axis.set_ylabel("Pressure (psia)", color="#475569")

    flow_axis = axes[0, 1]
    flow_axis.plot(stage, [_number(r, "L_out_used_lbmolph") for r in rows], "o-", label="Liquid out")
    flow_axis.plot(stage, [_number(r, "V_out_lbmolph") for r in rows], "s-", label="Vapor out")
    flow_axis.axvline(12, color="#64748b", linestyle=":", linewidth=1.3, label="Feed stage")
    flow_axis.set_title("Internal Molar Flow")
    flow_axis.set_ylabel("Flow (lbmol/h)")
    flow_axis.legend()

    liquid_axis = axes[1, 0]
    vapor_axis = axes[1, 1]
    for component, color in colors.items():
        liquid_axis.plot(stage, [_number(r, f"x_{component}") for r in rows], "o-", color=color, label=component)
        vapor_axis.plot(stage, [_number(r, f"y_{component}") for r in rows], "o-", color=color, label=component)
    liquid_axis.set_title("Liquid Composition")
    vapor_axis.set_title("Vapor Composition")
    liquid_axis.set_ylabel("Liquid mole fraction, x")
    vapor_axis.set_ylabel("Vapor mole fraction, y")
    liquid_axis.legend()
    vapor_axis.legend()

    for axis in axes.flat:
        axis.set_xlabel("Stage / volume (1 = reflux drum, 20 = reboiler sump)")
        axis.set_xticks(range(1, 21))
        axis.grid(True, color="#cbd5e1", linewidth=0.7, alpha=0.7)

    fig.suptitle("Core V3 Final Profiles — 600 s after +5 °F Feed Step", fontsize=16)
    fig.tight_layout()
    fig.savefig(OUTPUT, bbox_inches="tight")
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
