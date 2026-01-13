"""test_dynamic_run_scaffold_v1.py

Created: 2026-01-11  (America/New_York)
Updated: 2026-01-13 12:29 (America/New_York)

Unit test for the smoke-test runner.

This test intentionally avoids writing log files and avoids DWSIM by using
the built-in stub thermo provider.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from dynamic_distillation.dynamic_run_scaffold_v1 import RunnerConfig, run_smoke_simulation
from dynamic_distillation.column_rhs_v1 import column_rhs


def test_smoke_runner_builds_and_rhs_runs(tmp_path: Path):
    # Use the project template if present; otherwise skip.
    excel = Path("distillation_column_template.xlsx")
    if not excel.exists():
        # In CI or partial checkouts, the template may not exist.
        return

    cfg = RunnerConfig(
        excel_path=str(excel),
        n_steps=2,
        dt_sec=0.1,
        log_every_n_steps=1,
        include_temperature=True,
        include_energy=False,
        enable_equilibrium_relaxation=True,
        thermo_mode="stub",
        logs_dir=str(tmp_path),
        write_logs=False,
    )

    out = run_smoke_simulation(cfg)

    assert out["profile_csv"] is None
    assert out["summary_csv"] is None

    layout = out["layout"]
    col = out["column"]
    inputs = out["inputs"]
    y_final = np.asarray(out["final_state"], dtype=float)

    assert y_final.size == layout.n_states()
    assert abs(out["final_time_s"] - cfg.n_steps * cfg.dt_sec) < 1e-12

    # One RHS call should produce equilibrium diagnostics when enabled
    _dydt, diag = column_rhs(out["final_time_s"], y_final, col, layout, inputs=inputs)
    assert "y_eq_tray" in diag


def test_runner_initializes_vapor_holdup_to_match_spec_pressure(tmp_path: Path):
    """At t=0, MV should be initialized so PV diagnostic pressure ~ P_spec.

    We skip condenser (stage index 0) because MV is intentionally zero there.
    """

    excel = Path("distillation_column_template.xlsx")
    if not excel.exists():
        return

    cfg = RunnerConfig(
        excel_path=str(excel),
        n_steps=0,  # only run initialization + one RHS evaluation
        dt_sec=0.1,
        log_every_n_steps=1,
        include_temperature=True,
        include_energy=False,
        enable_equilibrium_relaxation=True,
        thermo_mode="stub",
        logs_dir=str(tmp_path),
        write_logs=False,
    )

    out = run_smoke_simulation(cfg)

    col = out["column"]
    layout = out["layout"]
    inputs = out["inputs"]
    y0 = np.asarray(out["final_state"], dtype=float)

    # If the case lacks an operating pressure profile, nothing to check.
    if not hasattr(col, "P_psia"):
        return

    P_spec = np.asarray(col.P_psia, dtype=float).reshape((col.n_stages,))
    if not np.all(np.isfinite(P_spec[1:])):
        # If spec pressure is missing on trays, skip.
        return

    # Re-evaluate RHS at t=0 with thermo diagnostics to get P_psia_diag.
    _dydt, diag = column_rhs(0.0, y0, col, layout, inputs=inputs)
    assert "P_psia_diag" in diag

    P_diag = np.asarray(diag["P_psia_diag"], dtype=float).reshape((col.n_stages,))

    # Condenser stage has MV=0 by design.
    u = layout.unpack(y0)
    assert float(u["MV_tot_tray"][0]) < 1e-12

    # On trays, PV diagnostic pressure should match spec within a small tolerance.
    # The stub provider uses Z=1.0; initialization uses the same R and temperature basis.
    max_abs = float(np.max(np.abs(P_diag[1:] - P_spec[1:])))
    assert max_abs < 1e-2