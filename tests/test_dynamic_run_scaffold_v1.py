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

from dynamic_distillation.dynamic_run_scaffold_v1 import (
    RunnerConfig,
    _clip_temperature_states_to_provider_bounds,
    run_smoke_simulation,
)
from dynamic_distillation.column_rhs_v1 import column_rhs
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout


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


def test_level_control_writes_dynamic_draws_to_summary_log(tmp_path: Path):
    excel = Path("distillation_column_template.xlsx")
    if not excel.exists():
        return

    cfg = RunnerConfig(
        excel_path=str(excel),
        n_steps=0,
        dt_sec=0.1,
        log_every_n_steps=1,
        include_temperature=True,
        include_energy=False,
        enable_equilibrium_relaxation=True,
        thermo_mode="stub",
        logs_dir=str(tmp_path),
        write_logs=True,
        enable_level_control=True,
        top_level_sp_lbmol=300.0,
        bottom_level_sp_lbmol=700.0,
    )

    out = run_smoke_simulation(cfg)
    summary_csv = Path(str(out["summary_csv"]))
    assert summary_csv.exists()

    import csv

    with summary_csv.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows, "summary log is empty"

    r0 = rows[0]
    d = float(r0["D_lbmolph"])
    b = float(r0["B_lbmolph"])
    assert np.isfinite(d) and np.isfinite(b)
    # With setpoints far below initial inventories, both product draws should increase.
    assert d > 2380.99
    assert b > 4761.98


def test_clip_temperature_states_to_provider_bounds():
    layout = StateVectorLayout(
        n_stages=3,
        n_components=2,
        include_top=True,
        include_bottom=True,
        include_vapor=True,
        include_temperature=True,
    )

    class TinyCol:
        n_stages = 3
        n_components = 2
        T_f = np.array([100.0, 110.0, 120.0], dtype=float)
        P_psia = np.array([200.0, 205.0, 210.0], dtype=float)
        V_lbmolph = np.array([10.0, 10.0, 10.0], dtype=float)
        L_lbmolph = np.array([10.0, 10.0, 10.0], dtype=float)
        M_L_lbmol = np.array([5.0, 5.0, 5.0], dtype=float)
        M_V_lbmol = np.array([1.0, 1.0, 1.0], dtype=float)
        x0 = np.array([[0.5, 0.5], [0.5, 0.5], [0.5, 0.5]], dtype=float)
        y0 = np.array([[0.5, 0.5], [0.5, 0.5], [0.5, 0.5]], dtype=float)

    y = layout.pack_y0(TinyCol())
    sl = layout.slices()
    y[sl["tray_T_f"]] = np.array([70.0, 115.0, 170.0], dtype=float)
    y[sl["bottom_T_f"]] = np.array([180.0], dtype=float)

    class Provider:
        T_grid_F = np.array([95.0, 130.0, 150.0], dtype=float)

    y2 = _clip_temperature_states_to_provider_bounds(y, layout, Provider())
    assert np.allclose(y2[sl["tray_T_f"]], np.array([95.0, 115.0, 150.0], dtype=float))
    assert np.allclose(y2[sl["bottom_T_f"]], np.array([150.0], dtype=float))
