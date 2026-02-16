#!/usr/bin/env python
"""
Regenerate docs/experiment_ledger.csv and docs/experiment_ledger.md.

Usage:
  python tools/update_experiment_ledger.py
"""

from pathlib import Path

from dynamic_distillation.experiment_ledger_v1 import rebuild_experiment_ledger


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    csv_path, md_path, n_rows = rebuild_experiment_ledger(project_root=project_root)
    print(f"Wrote: {csv_path}")
    print(f"Wrote: {md_path}")
    print(f"Rows: {n_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

