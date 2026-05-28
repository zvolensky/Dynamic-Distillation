from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_bench_module():
    repo_root = Path(__file__).resolve().parents[1]
    mod_path = repo_root / "tools" / "bench_live_thermo_refactor_v1.py"
    spec = importlib.util.spec_from_file_location("bench_live_thermo_refactor_v1", mod_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_manifest_contains_clapeyron_benchmark_candidates():
    bench = _load_bench_module()
    manifest = bench._load_manifest(bench._default_manifest_path())
    case_ids = {str(case.get("id")) for case in manifest.get("benchmarks", [])}

    assert "depropanizer_hydraulic_short_clapeyron_pr" in case_ids
    assert "depropanizer_hydraulic_5min_clapeyron_pr" in case_ids
    assert "depropanizer_hydraulic_60s_clapeyron_pr_te5_noguard" in case_ids
    assert "depropanizer_hydraulic_5min_clapeyron_pr_te5_noguard" in case_ids
    assert "depropanizer_hydraulic_short_clapeyron_pr_prewarm" in case_ids
    assert "water_methanol_hydraulic_short_clapeyron_pr" in case_ids


def test_clapeyron_benchmark_case_uses_expected_runtime_flags():
    bench = _load_bench_module()
    manifest = bench._load_manifest(bench._default_manifest_path())
    case = bench._select_case(manifest, "depropanizer_hydraulic_short_clapeyron_pr")

    argv = list(case.get("argv", []))
    assert "--thermo" in argv
    assert argv[argv.index("--thermo") + 1] == "clapeyron"
    assert "--clapeyron-model" in argv
    assert argv[argv.index("--clapeyron-model") + 1] == "PR"
    assert case.get("comparison_target") == "depropanizer_hydraulic_5min_probe"
    assert case.get("requirements", {}).get("optional_python_package") == "pyclapeyron"


def test_clapeyron_prewarm_benchmark_case_enables_startup_prewarm():
    bench = _load_bench_module()
    manifest = bench._load_manifest(bench._default_manifest_path())
    case = bench._select_case(manifest, "depropanizer_hydraulic_short_clapeyron_pr_prewarm")

    argv = list(case.get("argv", []))
    assert "--thermo" in argv
    assert argv[argv.index("--thermo") + 1] == "clapeyron"
    assert "--enable-primary-thermo-startup-prewarm" in argv
    assert case.get("comparison_target") == "depropanizer_hydraulic_short_clapeyron_pr"


def test_clapeyron_cadence_benchmark_case_disables_guardrails_for_frozen_thermo_probe():
    bench = _load_bench_module()
    manifest = bench._load_manifest(bench._default_manifest_path())
    case = bench._select_case(manifest, "depropanizer_hydraulic_5min_clapeyron_pr_te5_noguard")

    argv = list(case.get("argv", []))
    assert "--thermo" in argv
    assert argv[argv.index("--thermo") + 1] == "clapeyron"
    assert "--thermo-every" in argv
    assert argv[argv.index("--thermo-every") + 1] == "5"
    assert "--disable-thermo-cadence-guardrails" in argv
    assert case.get("comparison_target") == "depropanizer_hydraulic_5min_clapeyron_pr"
