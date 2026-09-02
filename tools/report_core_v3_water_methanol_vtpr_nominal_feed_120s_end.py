#!/usr/bin/env python
"""Add and display the standard end-of-run summary for the saved 120-second run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import core_v3_water_methanol_vtpr_dynamic_support as support  # noqa: E402


DEFAULT_JSON = Path(
    "logs/core_v3_water_methanol_vtpr_nominal_feed_120s_20260901.json"
)
DEFAULT_MATRIX = Path(
    "logs/core_v3_water_methanol_vtpr_nominal_feed_120s_20260901.npz"
)
DEFAULT_DOC = Path(
    "docs/core_v3_water_methanol_vtpr_nominal_feed_120s_end_summary_20260901.md"
)


def _markdown(summary: dict) -> str:
    duties = summary["duties"]
    products = summary["products"]
    levels = summary["terminal_levels"]
    steady = summary["steady_state"]
    lines = [
        "# Core V3 water-methanol 120-second end summary",
        "",
        f"- Qc: `{duties['condenser_BTUph']:.6f} BTU/h`",
        f"- Qr: `{duties['reboiler_BTUph']:.6f} BTU/h`",
        f"- Distillate flow: `{products['distillate']['flow_lbmolph']:.6f} lbmol/h`",
        f"- Bottoms flow: `{products['bottoms']['flow_lbmolph']:.6f} lbmol/h`",
        f"- Distillate drum level: `{100.0 * levels['distillate_drum_fraction']:.6f}%`",
        f"- Bottom drum level: `{100.0 * levels['bottom_drum_fraction']:.6f}%`",
        f"- Steady-state score: `{steady['score']:.8g}` (`{'steady' if steady['steady'] else 'not steady'}`)",
        "",
        "```text",
        support.format_end_of_run_summary(summary),
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    args = parser.parse_args()
    json_path = support.rooted(args.json)
    matrix_path = support.rooted(args.matrix)
    doc_path = support.rooted(args.doc)
    report = json.loads(json_path.read_text(encoding="utf-8"))
    if not report.get("pass_gate") or report.get("feed_multiplier") != 1.0:
        raise RuntimeError("end summary requires the accepted nominal-feed run")
    case = support.load_post_pulse_case()
    with np.load(matrix_path) as saved:
        evidence = {name: np.asarray(saved[name]) for name in saved.files}
    summary, provider_report, provider_calls = support.build_trajectory_end_summary(
        case,
        evidence,
        state_id="water_methanol:nominal_120s:saved_end_summary",
    )
    if not provider_report["pass"]:
        raise RuntimeError("end summary property evaluation failed its provider audit")
    report["end_of_run"] = summary
    report.setdefault("provider", {})["end_of_run_summary"] = provider_report
    report["provider"]["total_calls"] = int(
        report["provider"].get("total_calls", 0)
    ) + provider_calls
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(_markdown(summary), encoding="utf-8")
    print(support.format_end_of_run_summary(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
