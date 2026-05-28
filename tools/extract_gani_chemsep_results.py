#!/usr/bin/env python
"""Extract key ChemSep results from the Gani debutanizer seed case."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEP_PATH = Path(r"C:\Users\Thoma\AppData\Local\ChemSepL8v42\Gani_1986_Debutanizer_PR_RB_seed.sep")
OUT_DIR = ROOT / "logs" / "gani_1986_chemsep_rb_seed_results"

COMPONENTS = [
    "1,3-butadiene",
    "Isobutene",
    "N-pentane",
    "1-pentene",
    "1-hexene",
    "Benzene",
]

KMOLS_TO_KMOLH = 3600.0
MW_TO_GCALH = 3600.0 / 4184.0


def find_line(lines: list[str], marker: str) -> int:
    for idx, line in enumerate(lines):
        if line.strip() == marker:
            return idx
    raise ValueError(f"Could not find {marker}")


def parse_profiles(lines: list[str]) -> list[dict[str, float]]:
    start = find_line(lines, "[Profiles]")
    rows: list[dict[str, float]] = []
    for line in lines[start + 1 :]:
        if line.startswith("["):
            break
        parts = line.split()
        if len(parts) != 6 or not parts[0].isdigit():
            continue
        rows.append(
            {
                "stage": int(parts[0]),
                "temperature_K": float(parts[1]),
                "pressure_Pa": float(parts[2]),
                "vapor_flow_kmol_s": float(parts[3]),
                "liquid_flow_kmol_s": float(parts[4]),
                "duty_W": float(parts[5]),
                "vapor_flow_kmol_h": float(parts[3]) * KMOLS_TO_KMOLH,
                "liquid_flow_kmol_h": float(parts[4]) * KMOLS_TO_KMOLH,
            }
        )
    return rows


def parse_stage_compositions(lines: list[str], marker: str) -> list[dict[str, float]]:
    start = find_line(lines, marker)
    data: dict[int, dict[str, float]] = {stage: {"stage": stage} for stage in range(1, 29)}
    header_re = re.compile(r"stages:\s+(\d+)\s+to\s+(\d+)")

    idx = start + 1
    while idx < len(lines):
        line = lines[idx]
        if line.startswith("[") and idx > start + 1:
            break
        match = header_re.search(line)
        if not match:
            idx += 1
            continue
        first = int(match.group(1))
        last = int(match.group(2))
        stages = list(range(first, last + 1))
        idx += 2
        for _ in COMPONENTS:
            parts = lines[idx].split()
            comp_num = int(parts[0])
            values = [float(v) for v in parts[1:]]
            for stage, value in zip(stages, values):
                data[stage][COMPONENTS[comp_num - 1]] = value
            idx += 1
    return [data[stage] for stage in sorted(data)]


def parse_scalar_section(lines: list[str], marker: str) -> dict[str, float]:
    start = find_line(lines, marker)
    out: dict[str, float] = {}
    mole_fraction_count = 0
    for line in lines[start + 1 :]:
        if line.startswith("["):
            break
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(maxsplit=1)
        try:
            value = float(parts[0])
        except ValueError:
            continue
        label = parts[1] if len(parts) > 1 else "value"
        if "Mole fraction of component" in label:
            mole_fraction_count += 1
            if mole_fraction_count <= len(COMPONENTS):
                out[f"x_{COMPONENTS[mole_fraction_count - 1]}"] = value
            continue
        if label in out:
            continue
        out[label] = value
    return out


def write_csv(path: Path, rows: list[dict[str, float]]) -> None:
    if not rows:
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    text = SEP_PATH.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    profiles = parse_profiles(lines)
    vapor_y = parse_stage_compositions(lines, "[Vapour phase compositions]")
    liquid_x = parse_stage_compositions(lines, "[Liquid phase compositions]")
    top = parse_scalar_section(lines, "[Top product]")
    bottom = parse_scalar_section(lines, "[Bottom product]")
    qcond = parse_scalar_section(lines, "[Condenser Heat Duty]")
    qreb = parse_scalar_section(lines, "[Reboiler Heat Duty]")

    write_csv(OUT_DIR / "profiles.csv", profiles)
    write_csv(OUT_DIR / "vapor_y.csv", vapor_y)
    write_csv(OUT_DIR / "liquid_x.csv", liquid_x)

    source_reboiler_mw = 3.207733333
    summary = {
        "sep_path": str(SEP_PATH),
        "converged": "  1 Converged" in text,
        "iterations": 3,
        "top_flow_kmol_s": top["Flow rate"],
        "top_flow_kmol_h": top["Flow rate"] * KMOLS_TO_KMOLH,
        "bottom_flow_kmol_s": bottom["Flow rate"],
        "bottom_flow_kmol_h": bottom["Flow rate"] * KMOLS_TO_KMOLH,
        "condenser_duty_MW": qcond["Duty"] / 1.0e6,
        "reboiler_duty_MW": qreb["Duty"] / 1.0e6,
        "reboiler_duty_Gcal_h": qreb["Duty"] / 1.0e6 * MW_TO_GCALH,
        "source_reboiler_duty_MW": source_reboiler_mw,
        "reboiler_duty_vs_source_pct": (qreb["Duty"] / 1.0e6 / source_reboiler_mw - 1.0) * 100.0,
        "top_temperature_K": top["Temperature [K]"],
        "bottom_temperature_K": bottom["Temperature [K]"],
        "top_composition": {k.removeprefix("x_"): v for k, v in top.items() if k.startswith("x_")},
        "bottom_composition": {k.removeprefix("x_"): v for k, v in bottom.items() if k.startswith("x_")},
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md = [
        "# Gani 1986 ChemSep RB Seed Results",
        "",
        f"Source file: `{SEP_PATH}`",
        "",
        f"- Converged: {summary['converged']} in {summary['iterations']} iterations",
        f"- Distillate: {summary['top_flow_kmol_h']:.2f} kmol/h",
        f"- Bottoms: {summary['bottom_flow_kmol_h']:.2f} kmol/h",
        f"- Condenser duty: {summary['condenser_duty_MW']:.6g} MW",
        f"- Reboiler duty: {summary['reboiler_duty_MW']:.6g} MW ({summary['reboiler_duty_Gcal_h']:.6g} Gcal/h)",
        f"- Source reboiler duty: {summary['source_reboiler_duty_MW']:.6g} MW",
        f"- Reboiler duty difference vs source: {summary['reboiler_duty_vs_source_pct']:.2f}%",
        f"- Top temperature: {summary['top_temperature_K']:.2f} K",
        f"- Bottom temperature: {summary['bottom_temperature_K']:.2f} K",
        "",
        "Generated CSV files: `profiles.csv`, `liquid_x.csv`, `vapor_y.csv`.",
        "",
    ]
    (OUT_DIR / "summary.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {OUT_DIR}")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
