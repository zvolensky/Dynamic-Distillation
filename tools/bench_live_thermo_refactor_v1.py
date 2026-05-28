"""
bench_live_thermo_refactor_v1.py

Simple benchmark harness for the compute-efficiency refactor branch.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List


def _default_manifest_path() -> Path:
    return Path(__file__).resolve().parents[1] / "docs" / "thermo_refactor_benchmark_manifest_2026-04-05.json"


def _load_manifest(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _select_case(manifest: Dict[str, Any], case_id: str) -> Dict[str, Any]:
    for case in manifest.get("benchmarks", []):
        if str(case.get("id")) == str(case_id):
            return case
    raise KeyError(f"Unknown benchmark case: {case_id}")


def _print_case(case: Dict[str, Any]) -> None:
    baseline = case.get("baseline", {})
    print(f"id: {case['id']}")
    print(f"description: {case.get('description', '')}")
    print(f"command_source: {case.get('command_source', '')}")
    if case.get("comparison_target"):
        print(f"comparison_target: {case.get('comparison_target')}")
    requirements = case.get("requirements", {})
    if requirements:
        print(f"requirements: {json.dumps(requirements, sort_keys=True)}")
    print(f"baseline_run_id: {baseline.get('run_id', '')}")
    if "elapsed_wall_sec" in baseline:
        print(f"baseline_elapsed_wall_sec: {baseline['elapsed_wall_sec']}")
    if "final_time_s" in baseline:
        print(f"baseline_final_time_s: {baseline['final_time_s']}")


def _print_command(case: Dict[str, Any]) -> None:
    argv = [sys.executable, *list(case.get("argv", []))]
    print(subprocess.list2cmdline(argv))


def _print_baseline(case: Dict[str, Any], repo_root: Path) -> None:
    baseline = dict(case.get("baseline", {}) or {})
    if not baseline:
        print("[info] no saved baseline metadata for this case yet")
        return
    print(json.dumps(baseline, indent=2))
    meta_path_txt = baseline.get("run_metadata_json")
    if not meta_path_txt:
        return
    meta_path = repo_root / str(meta_path_txt)
    if not meta_path.exists():
        print(f"[warn] baseline metadata not found: {meta_path}")
        return
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    elapsed = payload.get("elapsed_wall_sec")
    final_time = payload.get("final_time_s")
    counters = payload.get("thermo_call_counters", {})
    print("")
    print("baseline_metadata_summary:")
    print(f"  elapsed_wall_sec: {elapsed}")
    print(f"  final_time_s: {final_time}")
    if counters:
        print("  thermo_categories:")
        for key in sorted(counters):
            print(f"    - {key}")


def main(argv: List[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(_default_manifest_path()))
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--case", default=None)
    parser.add_argument("--print-command", action="store_true")
    parser.add_argument("--print-baseline", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)

    manifest = _load_manifest(Path(args.manifest))
    cases = list(manifest.get("benchmarks", []))

    if args.list:
        for case in cases:
            _print_case(case)
            print("")
        return 0

    if not args.case:
        parser.error("--case is required unless --list is used")

    case = _select_case(manifest, args.case)

    if args.print_command:
        _print_command(case)

    if args.print_baseline:
        _print_baseline(case, repo_root)

    if args.run:
        cmd = [sys.executable, *list(case.get("argv", []))]
        print(f"[run] {subprocess.list2cmdline(cmd)}")
        completed = subprocess.run(cmd, cwd=str(repo_root), check=False)
        return int(completed.returncode)

    if (not args.print_command) and (not args.print_baseline) and (not args.run):
        _print_case(case)
        print("")
        _print_command(case)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
