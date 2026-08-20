#!/usr/bin/env python
"""Compact DD-245 provider evidence without model or solver calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from run_core_v3_vapor_holdup_stationary_root import (  # noqa: E402
    DEFAULT_JSON,
    compact_provider_report,
)


def compact(path: Path) -> tuple[int, int]:
    before = path.stat().st_size
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not payload.get("pass_gate"):
        raise RuntimeError("DD-245 compaction requires the accepted result")
    payload["provider"] = compact_provider_report(payload["provider"])
    payload["reporting_compaction"] = {
        "per-state_grouped_records_removed": True,
        "route_level_counts_preserved": True,
        "scientific_values_changed": False,
        "model_calls": 0,
        "solver_calls": 0,
        "timestep_calls": 0,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return before, path.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    args = parser.parse_args()
    before, after = compact(ROOT / args.json)
    print(
        json.dumps(
            {
                "bytes_before": before,
                "bytes_after": after,
                "reduction_ratio": after / before,
                "model_or_solver_calls": 0,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
