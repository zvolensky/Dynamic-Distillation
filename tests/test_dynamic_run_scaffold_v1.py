"""
test_dynamic_run_scaffold_v1.py

Dynamic Distillation - Runner/CLI Unit Tests

PURPOSE
-------
Validate core runner scaffolding behavior in `dynamic_run_scaffold_v1`
without requiring full external thermo backends.

SCOPE
-----
- RunnerConfig behaviors and startup-state helpers
- controller helper utilities and guardrail logic
- summary/log-field population and selective runtime branches

KEY DEPENDENCIES
----------------
- dynamic_run_scaffold_v1 runner helpers
- column_rhs_v1 integration points
- numpy/pytest fixtures
"""


from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dynamic_distillation.dynamic_run_scaffold_v1 import (
    PIController,
    _apply_slew_limit,
    RunnerConfig,
    _clear_initial_tray_vapor_holdup,
    _component_index_by_name,
    _clip_temperature_states_to_provider_bounds,
    _initialize_thermo_consistent_state,
    _initialize_vapor_holdup_from_spec_pressure,
    _initialize_top_drum_dynamic_steady,
    _pi_update,
    _pressure_resid_gain_scale,
    _resolve_startup_hydraulic_sequence_step,
    build_inputs_for_runner,
    run_smoke_simulation,
)
from dynamic_distillation.column_rhs_v1 import ColumnInputs, column_rhs
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


def test_initialize_vapor_holdup_rescales_ev_when_energy_states_enabled():
    class TinyCol:
        n_stages = 2
        n_components = 2
        M_L_lbmol = np.array([5.0, 5.0], dtype=float)
        M_V_lbmol = np.array([0.0, 0.0], dtype=float)
        x0 = np.array([[0.8, 0.2], [0.3, 0.7]], dtype=float)
        y0 = np.array([[0.9, 0.1], [0.4, 0.6]], dtype=float)
        T_f = np.array([100.0, 120.0], dtype=float)
        P_psia = np.array([200.0, 210.0], dtype=float)
        streams = {}

    col = TinyCol()
    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
        include_energy=True,
    )
    y0 = layout.pack_y0(col)
    y0 = _clear_initial_tray_vapor_holdup(y0, layout)

    u0 = layout.unpack(y0)
    hV_prev = np.asarray(u0["tray_EV_BTU"], dtype=float) / np.maximum(
        np.asarray(u0["MV_tot_tray"], dtype=float),
        float(layout.epsilon_lbmol),
    )

    y1 = _initialize_vapor_holdup_from_spec_pressure(
        col=col,
        layout=layout,
        y=y0,
        inputs=ColumnInputs(Zfac_prev=np.ones(col.n_stages, dtype=float)),
        include_temperature=False,
    )
    u1 = layout.unpack(y1)
    mv1 = np.asarray(u1["MV_tot_tray"], dtype=float)
    ev1 = np.asarray(u1["tray_EV_BTU"], dtype=float)
    hV_new = ev1 / np.maximum(mv1, float(layout.epsilon_lbmol))

    assert float(mv1[1]) > 0.0
    assert abs(float(hV_new[1]) - float(hV_prev[1])) < 1e-9
    assert abs(float(ev1[0])) < 1e-12


def test_level_control_writes_dynamic_draws_to_summary_log(tmp_path: Path):
    excel = Path("distillation_column_template.xlsx")
    if not excel.exists():
        return

    cfg = RunnerConfig(
        excel_path=str(excel),
        n_steps=1,
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
    assert len(rows) >= 2

    r0 = rows[0]
    r1 = rows[1]
    d = float(r0["D_lbmolph"])
    b = float(r0["B_lbmolph"])
    assert np.isfinite(d) and np.isfinite(b)
    assert "Q_reb_used_BTUph" in r0
    assert np.isfinite(float(r0["Q_reb_used_BTUph"]))
    assert "M_total_lbmol" in r0
    assert "dM_total_dt_lbmolph" in r0
    assert "net_F_minus_D_minus_B_lbmolph" in r0
    assert "global_mass_closure_error_lbmolph" in r0
    assert "global_mass_closure_cum_lbmol" in r0
    assert np.isfinite(float(r0["M_total_lbmol"]))
    assert np.isfinite(float(r0["dM_total_dt_lbmolph"]))
    assert np.isfinite(float(r0["net_F_minus_D_minus_B_lbmolph"]))
    assert np.isfinite(float(r0["global_mass_closure_error_lbmolph"]))
    assert np.isfinite(float(r0["global_mass_closure_cum_lbmol"]))
    # Controller output is held at initialization row.
    assert d == pytest.approx(2380.99)
    assert b == pytest.approx(4761.98)
    # With setpoints far below initial inventories, both product draws should increase
    # on the first actionable timestep.
    assert float(r1["D_lbmolph"]) > 2380.99
    assert float(r1["B_lbmolph"]) > 4761.98


def test_summary_row_prefers_logged_pressure_controller_pv():
    import dynamic_distillation.dynamic_run_scaffold_v1 as scaffold

    class TinyCol:
        n_stages = 2
        n_components = 2
        components_excel = ["C3", "C4"]
        T_f = np.array([120.0, 130.0], dtype=float)
        P_psia = np.array([220.0, 230.0], dtype=float)
        M_L_lbmol = np.array([5.0, 6.0], dtype=float)
        M_V_lbmol = np.array([1.0, 1.0], dtype=float)
        x0 = np.array([[0.80, 0.20], [0.30, 0.70]], dtype=float)
        y0 = np.array([[0.75, 0.25], [0.25, 0.75]], dtype=float)
        streams = {}

    col = TinyCol()
    layout = StateVectorLayout(
        n_stages=col.n_stages,
        n_components=col.n_components,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y = layout.pack_y0(col)

    diag = {
        "x_tray": np.asarray(col.x0, dtype=float).copy(),
        "y_tray": np.asarray(col.y0, dtype=float).copy(),
        "P_psia_diag": np.array([222.0, 231.0], dtype=float),
        "P_psia_hyd": np.array([224.0, 232.0], dtype=float),
        "P_top_drum_psia": np.array([226.0], dtype=float),
        "P_top_ctrl_pv_psia": np.array([221.0], dtype=float),
    }

    row = scaffold._summary_row(
        t_s=0.0,
        case=None,
        col=col,
        layout=layout,
        y=y,
        diag=diag,
        include_temperature=False,
        volume_model=scaffold.VolumeModel(default_vapor_volume_ft3=10.0),
        wall_clock_iso="2026-02-17T00:00:00",
        wall_elapsed_s=0.0,
        feed_tag=scaffold.StreamTag(name="Feed", flow_lbmolph=1000.0, stage_1based=2),
        dist_tag=scaffold.StreamTag(name="Distillate", flow_lbmolph=200.0, stage_1based=1),
        bots_tag=scaffold.StreamTag(name="Bottoms", flow_lbmolph=800.0, stage_1based=2),
    )

    assert float(row["P_top_ctrl_pv_psia"]) == pytest.approx(221.0)
    assert float(row["P_top_psia"]) == pytest.approx(221.0)
    assert float(row["P_top_psia"]) != pytest.approx(226.0)


def test_profile_rows_add_unit_rows_and_move_drum_sump_fields():
    import dynamic_distillation.dynamic_run_scaffold_v1 as scaffold

    class TinyCol:
        n_stages = 2
        n_components = 2
        components_excel = ["C3", "C4"]
        T_f = np.array([120.0, 130.0], dtype=float)
        P_psia = np.array([220.0, 230.0], dtype=float)
        M_L_lbmol = np.array([5.0, 6.0], dtype=float)
        M_V_lbmol = np.array([1.0, 1.0], dtype=float)
        x0 = np.array([[0.80, 0.20], [0.30, 0.70]], dtype=float)
        y0 = np.array([[0.75, 0.25], [0.25, 0.75]], dtype=float)
        streams = {}

    col = TinyCol()
    layout = StateVectorLayout(
        n_stages=col.n_stages,
        n_components=col.n_components,
        include_top=True,
        include_bottom=True,
        include_vapor=True,
        include_temperature=True,
    )
    y = layout.pack_y0(col)
    sl = layout.slices()
    y[sl["bottom_T_f"]] = np.array([165.0], dtype=float)

    diag = {
        "x_tray": np.asarray(col.x0, dtype=float).copy(),
        "y_tray": np.asarray(col.y0, dtype=float).copy(),
        "P_psia_hyd": np.array([220.0, 222.0], dtype=float),
        "L_out_hyd_lbmolph": np.array([100.0, 120.0], dtype=float),
        "V_out_lbmolph": np.array([1000.0, 1100.0], dtype=float),
        "Q_cond_cmd_BTUph": np.array([-5.1e7], dtype=float),
        "Q_cond_calc_BTUph": np.array([-5.0e7], dtype=float),
        "Q_cond_used_BTUph": np.array([-5.0e7], dtype=float),
        "P_top_drum_psia": np.array([219.0], dtype=float),
        "V_top_drum_vapor_ft3": np.array([500.0], dtype=float),
        "Q_reb_cmd_BTUph": np.array([8.2e7], dtype=float),
        "Q_reb_used_BTUph": np.array([8.1e7], dtype=float),
        "xD_comp_sp": np.array([0.10], dtype=float),
        "xD_comp_pv": np.array([0.12], dtype=float),
        "Reflux_cmd_lbmolph": np.array([6000.0], dtype=float),
        "xB_comp_sp": np.array([0.30], dtype=float),
        "xB_comp_pv": np.array([0.28], dtype=float),
        "Boilup_cmd_lbmolph": np.array([12000.0], dtype=float),
    }

    rows = scaffold._profile_rows(
        t_s=0.0,
        case=None,
        col=col,
        layout=layout,
        y=y,
        diag=diag,
        include_temperature=True,
        volume_model=scaffold.VolumeModel(default_vapor_volume_ft3=10.0),
        wall_clock_iso="2026-02-18T00:00:00",
        wall_elapsed_s=0.0,
        feed_tag=scaffold.StreamTag(name="Feed", flow_lbmolph=1000.0, stage_1based=2),
        dist_tag=scaffold.StreamTag(name="Distillate", flow_lbmolph=200.0, stage_1based=1),
        bots_tag=scaffold.StreamTag(name="Bottoms", flow_lbmolph=800.0, stage_1based=2),
    )

    assert len(rows) == 4
    assert str(rows[0]["node_type"]) == "distillate_drum"
    assert str(rows[-1]["node_type"]) == "bottoms_sump"
    stage_rows = [r for r in rows if str(r["node_type"]) == "stage"]
    drum_rows = [r for r in rows if str(r["node_type"]) == "distillate_drum"]
    sump_rows = [r for r in rows if str(r["node_type"]) == "bottoms_sump"]
    assert len(stage_rows) == 2
    assert len(drum_rows) == 1
    assert len(sump_rows) == 1

    stage1 = next(r for r in stage_rows if int(r["stage"]) == 1)
    stage2 = next(r for r in stage_rows if int(r["stage"]) == 2)
    drum = drum_rows[0]
    sump = sump_rows[0]

    assert int(drum["stage"]) == 0
    assert int(sump["stage"]) == 3
    assert float(stage1["P_psia_hyd"]) == pytest.approx(220.0)
    assert float(stage2["P_psia_hyd"]) == pytest.approx(222.0)

    assert np.isnan(float(stage1["P_top_drum_psia"]))
    assert float(drum["P_top_drum_psia"]) == pytest.approx(219.0)
    assert np.isnan(float(stage1["Distillate_L_lbmol"]))
    assert np.isfinite(float(drum["Distillate_L_lbmol"]))
    assert np.isnan(float(stage1["Distillate_x_C3"]))
    assert np.isfinite(float(drum["Distillate_x_C3"]))
    assert np.isnan(float(stage1["D_lbmolph"]))
    assert float(drum["D_lbmolph"]) == pytest.approx(200.0)

    assert np.isnan(float(stage2["Q_reb_cmd_BTUph"]))
    assert float(sump["Q_reb_cmd_BTUph"]) == pytest.approx(8.2e7)
    assert np.isnan(float(stage2["Bottoms_L_lbmol"]))
    assert np.isfinite(float(sump["Bottoms_L_lbmol"]))
    assert np.isnan(float(stage2["Bottoms_x_C4"]))
    assert np.isfinite(float(sump["Bottoms_x_C4"]))
    assert np.isnan(float(stage2["B_lbmolph"]))
    assert float(sump["B_lbmolph"]) == pytest.approx(800.0)


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


def test_component_index_by_name_handles_c_number_alias():
    class TinyCol:
        n_components = 3
        components_excel = ["C3H8", "C4H10", "C5H12"]
        components_dwsim = ["Propane", "n-Butane", "n-Pentane"]

    assert _component_index_by_name(TinyCol(), "C4") == 1
    assert _component_index_by_name(TinyCol(), "c4h10") == 1
    assert _component_index_by_name(TinyCol(), "n-Butane") == 1


def test_pi_update_negative_gain_unwinds_low_saturation():
    ctrl = PIController(kc=-1.0, ti_sec=1.0, bias=0.0, out_min=-100.0, out_max=100.0, integ=500.0)

    # sat_lo with reverse-acting gain: negative error should unwind integrator.
    u = _pi_update(ctrl, pv=0.0, sp=10.0, dt_sec=1.0)
    assert u == pytest.approx(-100.0)
    assert ctrl.integ == pytest.approx(490.0)


def test_pi_update_negative_gain_blocks_windup_low_saturation():
    ctrl = PIController(kc=-1.0, ti_sec=1.0, bias=0.0, out_min=-100.0, out_max=100.0, integ=500.0)

    # sat_lo with reverse-acting gain: positive error pushes deeper into saturation.
    u = _pi_update(ctrl, pv=20.0, sp=10.0, dt_sec=1.0)
    assert u == pytest.approx(-100.0)
    assert ctrl.integ == pytest.approx(500.0)


def test_pressure_resid_gain_scale_maps_residual_to_bounded_gain():
    assert _pressure_resid_gain_scale(resid_abs_btups=None, resid_ref_btups=1000.0, min_gain=0.2) == pytest.approx(1.0)
    assert _pressure_resid_gain_scale(resid_abs_btups=0.0, resid_ref_btups=1000.0, min_gain=0.2) == pytest.approx(1.0)

    g_mid = _pressure_resid_gain_scale(resid_abs_btups=1000.0, resid_ref_btups=1000.0, min_gain=0.2)
    assert g_mid == pytest.approx(0.5)

    g_hi = _pressure_resid_gain_scale(resid_abs_btups=1.0e9, resid_ref_btups=1000.0, min_gain=0.2)
    assert g_hi == pytest.approx(0.2)


def test_apply_slew_limit_clamps_step_change():
    u = _apply_slew_limit(cmd=10.0, prev_cmd=0.0, rate_limit_per_s=2.0, dt_sec=1.0)
    assert u == pytest.approx(2.0)

    u2 = _apply_slew_limit(cmd=-10.0, prev_cmd=0.0, rate_limit_per_s=2.0, dt_sec=1.0)
    assert u2 == pytest.approx(-2.0)

    u3 = _apply_slew_limit(cmd=1.0, prev_cmd=0.0, rate_limit_per_s=2.0, dt_sec=1.0)
    assert u3 == pytest.approx(1.0)


def test_startup_hydraulic_sequence_stages_pressure_then_energy_then_liquid_ramp():
    base = ColumnInputs(
        pressure_model="hydraulic",
        vapor_flow_model="energy",
        enable_liquid_hydraulic_override=True,
        liquid_hydraulic_override_alpha=1.0,
    )

    p0, v0, a0, ph0 = _resolve_startup_hydraulic_sequence_step(
        t_s=0.0,
        dt_sec=1.0,
        base_inputs=base,
        enable_sequence=True,
        energy_on_sec=10.0,
        liquid_on_sec=20.0,
        liquid_ramp_sec=40.0,
        liquid_resid_gate_lbmolph=250.0,
        liquid_backoff_sec=None,
        liquid_alpha_state=1.0,
        last_mass_resid_max_lbmolph=None,
    )
    assert p0 == "hydraulic"
    assert v0 == "profile"
    assert a0 == pytest.approx(0.0)
    assert ph0 == "pressure_only"

    p1, v1, a1, ph1 = _resolve_startup_hydraulic_sequence_step(
        t_s=12.0,
        dt_sec=1.0,
        base_inputs=base,
        enable_sequence=True,
        energy_on_sec=10.0,
        liquid_on_sec=20.0,
        liquid_ramp_sec=40.0,
        liquid_resid_gate_lbmolph=250.0,
        liquid_backoff_sec=None,
        liquid_alpha_state=a0,
        last_mass_resid_max_lbmolph=25.0,
    )
    assert p1 == "hydraulic"
    assert v1 == "energy"
    assert a1 == pytest.approx(0.0)
    assert ph1 == "pressure_energy"

    _p2, _v2, a2, ph2 = _resolve_startup_hydraulic_sequence_step(
        t_s=40.0,
        dt_sec=40.0,
        base_inputs=base,
        enable_sequence=True,
        energy_on_sec=10.0,
        liquid_on_sec=20.0,
        liquid_ramp_sec=40.0,
        liquid_resid_gate_lbmolph=250.0,
        liquid_backoff_sec=None,
        liquid_alpha_state=a1,
        last_mass_resid_max_lbmolph=25.0,
    )
    assert a2 == pytest.approx(0.5)
    assert ph2 == "pressure_energy_liquid_ramp"


def test_startup_hydraulic_sequence_backs_off_liquid_alpha_on_high_residual():
    base = ColumnInputs(
        pressure_model="hydraulic",
        vapor_flow_model="energy",
        enable_liquid_hydraulic_override=True,
        liquid_hydraulic_override_alpha=1.0,
    )
    _p, _v, a, _ph = _resolve_startup_hydraulic_sequence_step(
        t_s=90.0,
        dt_sec=10.0,
        base_inputs=base,
        enable_sequence=True,
        energy_on_sec=10.0,
        liquid_on_sec=20.0,
        liquid_ramp_sec=40.0,
        liquid_resid_gate_lbmolph=100.0,
        liquid_backoff_sec=20.0,
        liquid_alpha_state=0.8,
        last_mass_resid_max_lbmolph=250.0,
    )
    assert a == pytest.approx(0.3)


def test_startup_hydraulic_sequence_disabled_uses_base_modes():
    base = ColumnInputs(
        pressure_model="hydraulic",
        vapor_flow_model="energy",
        enable_liquid_hydraulic_override=True,
        liquid_hydraulic_override_alpha=0.75,
    )
    p, v, a, ph = _resolve_startup_hydraulic_sequence_step(
        t_s=0.0,
        dt_sec=1.0,
        base_inputs=base,
        enable_sequence=False,
        energy_on_sec=10.0,
        liquid_on_sec=20.0,
        liquid_ramp_sec=40.0,
        liquid_resid_gate_lbmolph=100.0,
        liquid_backoff_sec=None,
        liquid_alpha_state=0.0,
        last_mass_resid_max_lbmolph=None,
    )
    assert p == "hydraulic"
    assert v == "energy"
    assert a == pytest.approx(0.75)
    assert ph == "base"


def test_top_drum_dynamic_steady_initializer_with_mocked_rhs(monkeypatch):
    class TinyCol:
        n_stages = 2
        n_components = 2
        M_L_lbmol = np.array([10.0, 10.0], dtype=float)
        M_V_lbmol = np.array([1.0, 1.0], dtype=float)
        x0 = np.array([[0.8, 0.2], [0.4, 0.6]], dtype=float)
        y0 = np.array([[0.7, 0.3], [0.5, 0.5]], dtype=float)
        streams = {}

    col = TinyCol()
    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=True,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
        include_energy=False,
    )
    y0 = layout.pack_y0(col)
    sl = layout.slices()
    y0[sl["top_L"]] = np.array([0.8, 0.2], dtype=float) * 1.0
    y0[sl["top_V"]] = np.array([0.6, 0.4], dtype=float) * 9.0

    import dynamic_distillation.dynamic_run_scaffold_v1 as scaffold

    def _fake_rhs(_t, y_vec, _col, _layout, inputs=None):
        u = layout.unpack(np.asarray(y_vec, dtype=float))
        top_L_tot = float(np.sum(np.asarray(u["top_L"], dtype=float)))
        top_V_tot = float(np.sum(np.asarray(u["top_V"], dtype=float)))
        dydt = np.zeros(layout.n_states(), dtype=float)
        # Linear residual model with known root at top_L=5, top_V=3.
        dydt[sl["top_L"]] = np.array([0.7, 0.3], dtype=float) * (top_L_tot - 5.0)
        dydt[sl["top_V"]] = np.array([0.4, 0.6], dtype=float) * (top_V_tot - 3.0)
        return dydt, {}

    monkeypatch.setattr(scaffold, "column_rhs", _fake_rhs)

    y1, info = _initialize_top_drum_dynamic_steady(
        col=col,
        layout=layout,
        y=y0,
        inputs=ColumnInputs(),
        max_iter=6,
        tol_lbmolps=1e-9,
    )

    u1 = layout.unpack(y1)
    top_L_tot = float(np.sum(np.asarray(u1["top_L"], dtype=float)))
    top_V_tot = float(np.sum(np.asarray(u1["top_V"], dtype=float)))
    assert info["attempted"] is True
    assert top_L_tot == pytest.approx(5.0, abs=1e-6)
    assert top_V_tot == pytest.approx(3.0, abs=1e-6)
    assert abs(float(info["d_top_L_final_lbmolps"])) < 1e-7
    assert abs(float(info["d_top_V_final_lbmolps"])) < 1e-7


def test_thermo_startup_conditioner_with_mocked_rhs(monkeypatch):
    class TinyCol:
        n_stages = 3
        n_components = 2
        M_L_lbmol = np.array([5.0, 6.0, 7.0], dtype=float)
        M_V_lbmol = np.array([1.0, 1.5, 2.0], dtype=float)
        x0 = np.array([[0.8, 0.2], [0.5, 0.5], [0.2, 0.8]], dtype=float)
        y0 = np.array([[0.7, 0.3], [0.4, 0.6], [0.1, 0.9]], dtype=float)
        T_f = np.array([100.0, 110.0, 120.0], dtype=float)
        P_psia = np.array([200.0, 205.0, 210.0], dtype=float)
        streams = {}

    col = TinyCol()
    layout = StateVectorLayout(
        n_stages=3,
        n_components=2,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
        include_energy=True,
    )
    y0 = layout.pack_y0(col)
    sl = layout.slices()

    x_eq = np.array([[0.9, 0.1], [0.6, 0.4], [0.3, 0.7]], dtype=float)
    y_eq = np.array([[0.8, 0.2], [0.55, 0.45], [0.25, 0.75]], dtype=float)
    HL = np.array([10.0, 20.0, 30.0], dtype=float)
    HV = np.array([100.0, 200.0, 300.0], dtype=float)

    import dynamic_distillation.dynamic_run_scaffold_v1 as scaffold

    def _fake_rhs(_t, y_vec, _col, _layout, inputs=None):
        u = layout.unpack(np.asarray(y_vec, dtype=float))
        x_now = np.asarray(u["x_tray"], dtype=float).reshape((col.n_stages, col.n_components))
        gap = np.sum(np.abs(x_now - x_eq), axis=1)
        dydt = np.zeros(layout.n_states(), dtype=float)
        diag = {
            "x_eq_tray": x_eq.copy(),
            "y_eq_tray": y_eq.copy(),
            "HL_BTU_lbmol_tray": HL.copy(),
            "HV_BTU_lbmol_tray": HV.copy(),
            "Z_tray": np.ones(col.n_stages, dtype=float),
            "eq_phase_change_lbmolps_tray": gap,
        }
        return dydt, diag

    monkeypatch.setattr(scaffold, "column_rhs", _fake_rhs)
    monkeypatch.setattr(
        scaffold,
        "_initialize_vapor_holdup_from_spec_pressure",
        lambda **kwargs: np.asarray(kwargs["y"], dtype=float).copy(),
    )

    y1, info = _initialize_thermo_consistent_state(
        col=col,
        layout=layout,
        y=y0,
        inputs=ColumnInputs(thermo_provider=object()),
        include_temperature=False,
        max_iter=1,
        relaxation=1.0,
    )

    u1 = layout.unpack(y1)
    x1 = np.asarray(u1["x_tray"], dtype=float).reshape((col.n_stages, col.n_components))
    y1_frac = np.asarray(u1["y_tray"], dtype=float).reshape((col.n_stages, col.n_components))
    assert info["attempted"] is True
    assert int(info["n_iter"]) == 1
    assert np.allclose(x1, x_eq, atol=1e-12)
    # Stage 1 vapor holdup is forced to zero by startup policy.
    assert np.allclose(y1_frac[1:, :], y_eq[1:, :], atol=1e-12)

    ml_tot = np.asarray(u1["ML_tot_tray"], dtype=float).reshape((col.n_stages,))
    mv_tot = np.asarray(u1["MV_tot_tray"], dtype=float).reshape((col.n_stages,))
    tray_EL = np.asarray(y1[sl["tray_EL_BTU"]], dtype=float).reshape((col.n_stages,))
    tray_EV = np.asarray(y1[sl["tray_EV_BTU"]], dtype=float).reshape((col.n_stages,))
    assert np.allclose(tray_EL, ml_tot * HL, atol=1e-12)
    assert np.allclose(tray_EV, mv_tot * HV, atol=1e-12)
    assert abs(float(info["eq_phase_change_final_lbmolps"])) < float(info["eq_phase_change_init_lbmolps"])


def test_distillate_composition_control_logs_command(tmp_path: Path):
    excel = Path("distillation_column_template.xlsx")
    if not excel.exists():
        return
    thermo_table = Path("cache/thermo_table.json")
    if not thermo_table.exists():
        return

    cfg = RunnerConfig(
        excel_path=str(excel),
        n_steps=0,
        dt_sec=0.2,
        log_every_n_steps=1,
        include_temperature=True,
        include_energy=True,
        enable_equilibrium_relaxation=True,
        thermo_mode="table",
        thermo_table_path=str(thermo_table),
        logs_dir=str(tmp_path),
        write_logs=True,
        enable_level_control=True,
        top_level_sp_lbmol=397.0,
        bottom_level_sp_lbmol=794.0,
        enable_distillate_composition_control=True,
        distillate_composition_component="C4",
        distillate_composition_sp_molfrac=0.05,
    )

    out = run_smoke_simulation(cfg)
    summary_csv = Path(str(out["summary_csv"]))
    assert summary_csv.exists()

    import csv

    with summary_csv.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows, "summary log is empty"

    r0 = rows[0]
    assert "xD_comp_sp" in r0
    assert "xD_comp_pv" in r0
    assert "RR_comp_cmd" in r0
    assert np.isfinite(float(r0["xD_comp_sp"]))
    assert np.isfinite(float(r0["RR_comp_cmd"]))


def test_build_inputs_reads_and_overrides_condenser_pressure_drop():
    excel = Path("distillation_column_template.xlsx")
    if not excel.exists():
        return

    from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
    from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case

    case = load_case_from_excel(str(excel))
    col = build_column_spec_from_case(case)

    specs = dict(getattr(col, "specs_raw", {}) or {})
    specs["Condenser Pressure Drop (psi)"] = 2.0
    object.__setattr__(col, "specs_raw", specs)

    cfg = RunnerConfig(excel_path=str(excel), thermo_mode="stub")
    inputs, _ = build_inputs_for_runner(case, col, cfg)
    assert abs(float(inputs.condenser_pressure_drop_psi) - 2.0) < 1e-12

    cfg_override = RunnerConfig(excel_path=str(excel), thermo_mode="stub", condenser_pressure_drop_psi=1.25)
    inputs_override, _ = build_inputs_for_runner(case, col, cfg_override)
    assert abs(float(inputs_override.condenser_pressure_drop_psi) - 1.25) < 1e-12


def test_build_inputs_reads_and_overrides_top_psv_settings():
    excel = Path("distillation_column_template.xlsx")
    if not excel.exists():
        return

    from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
    from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case

    case = load_case_from_excel(str(excel))
    col = build_column_spec_from_case(case)

    specs = dict(getattr(col, "specs_raw", {}) or {})
    specs["Enable Top PSV"] = "Yes"
    specs["Top PSV SP (psia)"] = 245.0
    specs["Top PSV Gain (lbmol/s/psi)"] = 0.05
    specs["Top PSV Max Vent (lbmol/s)"] = 0.60
    object.__setattr__(col, "specs_raw", specs)

    cfg = RunnerConfig(excel_path=str(excel), thermo_mode="stub")
    inputs, _ = build_inputs_for_runner(case, col, cfg)
    assert bool(inputs.enable_top_drum_psv) is True
    assert abs(float(inputs.top_drum_psv_setpoint_psia) - 245.0) < 1e-12
    assert abs(float(inputs.top_drum_psv_gain_lbmolps_per_psi) - 0.05) < 1e-12
    assert abs(float(inputs.top_drum_psv_max_vent_lbmolps) - 0.60) < 1e-12

    cfg_override = RunnerConfig(
        excel_path=str(excel),
        thermo_mode="stub",
        enable_top_psv=True,
        top_psv_setpoint_psia=230.0,
        top_psv_gain_lbmolps_per_psi=0.20,
        top_psv_max_vent_lbmolps=0.90,
    )
    inputs_override, _ = build_inputs_for_runner(case, col, cfg_override)
    assert bool(inputs_override.enable_top_drum_psv) is True
    assert abs(float(inputs_override.top_drum_psv_setpoint_psia) - 230.0) < 1e-12
    assert abs(float(inputs_override.top_drum_psv_gain_lbmolps_per_psi) - 0.20) < 1e-12
    assert abs(float(inputs_override.top_drum_psv_max_vent_lbmolps) - 0.90) < 1e-12


def test_build_inputs_computes_top_drum_vapor_volume_from_geometry():
    excel = Path("distillation_column_template.xlsx")
    if not excel.exists():
        return

    from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
    from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case

    case = load_case_from_excel(str(excel))
    col = build_column_spec_from_case(case)

    specs = dict(getattr(col, "specs_raw", {}) or {})
    specs["Top Drum Vapor Volume (ft3)"] = None
    specs["Top Drum Total Volume (ft3)"] = None
    specs["Top Drum Diameter (ft)"] = 10.0
    specs["Top Drum Length (ft)"] = 40.0
    specs["Top Drum Liquid Fraction (-)"] = 0.60
    object.__setattr__(col, "specs_raw", specs)

    cfg = RunnerConfig(excel_path=str(excel), thermo_mode="stub")
    inputs, _ = build_inputs_for_runner(case, col, cfg)

    total_vol = float(np.pi * 0.25 * 10.0 * 10.0 * 40.0)
    expected_vapor = total_vol * (1.0 - 0.60)
    assert inputs.top_drum_total_volume_ft3 is not None
    assert abs(float(inputs.top_drum_total_volume_ft3) - total_vol) < 1e-9
    assert inputs.top_drum_vapor_volume_ft3 is not None
    assert abs(float(inputs.top_drum_vapor_volume_ft3) - expected_vapor) < 1e-9


def test_build_inputs_infers_top_drum_total_volume_from_holdup_and_vapor_volume():
    excel = Path("distillation_column_template.xlsx")
    if not excel.exists():
        return

    from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
    from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case

    case = load_case_from_excel(str(excel))
    col = build_column_spec_from_case(case)

    specs = dict(getattr(col, "specs_raw", {}) or {})
    specs["Top Drum Total Volume (ft3)"] = None
    specs["Top Drum Liquid Fraction (-)"] = None
    specs["Top Drum Vapor Volume (ft3)"] = 900.0
    specs["Top Accumulator Holdup (lbmol)"] = 397.0
    object.__setattr__(col, "specs_raw", specs)

    cfg = RunnerConfig(excel_path=str(excel), thermo_mode="stub")
    inputs, _ = build_inputs_for_runner(case, col, cfg)

    assert inputs.top_drum_vapor_volume_ft3 is not None
    assert abs(float(inputs.top_drum_vapor_volume_ft3) - 900.0) < 1e-12
    assert inputs.top_drum_total_volume_ft3 is not None
    assert float(inputs.top_drum_total_volume_ft3) > 900.0


def test_build_inputs_applies_hydraulic_energy_stability_defaults():
    excel = Path("distillation_column_template.xlsx")
    if not excel.exists():
        return

    from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
    from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case

    case = load_case_from_excel(str(excel))
    col = build_column_spec_from_case(case)

    specs = dict(getattr(col, "specs_raw", {}) or {})
    specs["Pressure Model"] = "hydraulic"
    specs["Vapor Flow Model"] = "energy"
    specs["Vapor Holdup Relaxation (sec)"] = None
    specs["Reboiler Neighbor Vapor Hi Ratio"] = None
    specs["Reboiler Neighbor Vapor Lo Ratio"] = None
    specs["Thermo Refresh dT (F)"] = 5.0
    specs["Thermo Refresh dP (psia)"] = 2.0
    specs["Thermo Refresh dX"] = 0.05
    object.__setattr__(col, "specs_raw", specs)

    cfg = RunnerConfig(excel_path=str(excel), thermo_mode="stub")
    inputs, _ = build_inputs_for_runner(case, col, cfg)

    assert str(inputs.pressure_model).lower() == "hydraulic"
    assert str(inputs.vapor_flow_model).lower() == "energy"
    assert abs(float(inputs.vapor_holdup_relaxation_sec) - 10.0) < 1e-12
    assert abs(float(inputs.hydraulic_pressure_relaxation_sec) - 10.0) < 1e-12
    assert abs(float(inputs.reboiler_neighbor_vflow_hi_ratio) - 1.20) < 1e-12
    assert abs(float(inputs.reboiler_neighbor_vflow_lo_ratio) - 0.80) < 1e-12
    assert inputs.thermo_refresh_dT_F is None
    assert inputs.thermo_refresh_dP_psia is None
    assert inputs.thermo_refresh_dx is None


def test_build_inputs_hydraulic_energy_stability_defaults_allow_cfg_overrides():
    excel = Path("distillation_column_template.xlsx")
    if not excel.exists():
        return

    from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
    from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case

    case = load_case_from_excel(str(excel))
    col = build_column_spec_from_case(case)

    specs = dict(getattr(col, "specs_raw", {}) or {})
    specs["Pressure Model"] = "hydraulic"
    specs["Vapor Flow Model"] = "energy"
    object.__setattr__(col, "specs_raw", specs)

    cfg = RunnerConfig(
        excel_path=str(excel),
        thermo_mode="stub",
        vapor_holdup_relaxation_sec=6.0,
        hydraulic_pressure_relaxation_sec=3.0,
        reboiler_neighbor_vflow_hi_ratio=1.05,
        reboiler_neighbor_vflow_lo_ratio=0.95,
        thermo_refresh_dT_F=0.2,
        thermo_refresh_dP_psia=0.3,
        thermo_refresh_dx=1.0e-3,
        enforce_top_pressure_ordering=False,
        top_pressure_ordering_margin_psi=0.15,
    )
    inputs, _ = build_inputs_for_runner(case, col, cfg)

    assert abs(float(inputs.vapor_holdup_relaxation_sec) - 6.0) < 1e-12
    assert abs(float(inputs.hydraulic_pressure_relaxation_sec) - 3.0) < 1e-12
    assert abs(float(inputs.reboiler_neighbor_vflow_hi_ratio) - 1.05) < 1e-12
    assert abs(float(inputs.reboiler_neighbor_vflow_lo_ratio) - 0.95) < 1e-12
    assert abs(float(inputs.thermo_refresh_dT_F) - 0.2) < 1e-12
    assert abs(float(inputs.thermo_refresh_dP_psia) - 0.3) < 1e-12
    assert abs(float(inputs.thermo_refresh_dx) - 1.0e-3) < 1e-12
    assert bool(inputs.enforce_top_pressure_ordering) is False
    assert abs(float(inputs.top_pressure_ordering_margin_psi) - 0.15) < 1e-12


def test_bottoms_composition_control_logs_command(tmp_path: Path):
    excel = Path("distillation_column_template.xlsx")
    if not excel.exists():
        return

    cfg = RunnerConfig(
        excel_path=str(excel),
        n_steps=0,
        dt_sec=0.2,
        log_every_n_steps=1,
        include_temperature=True,
        include_energy=False,
        enable_equilibrium_relaxation=True,
        thermo_mode="stub",
        logs_dir=str(tmp_path),
        write_logs=True,
        enable_bottoms_composition_control=True,
        bottoms_composition_component="C5",
        bottoms_composition_sp_molfrac=0.20,
    )

    out = run_smoke_simulation(cfg)
    summary_csv = Path(str(out["summary_csv"]))
    assert summary_csv.exists()

    import csv

    with summary_csv.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows, "summary log is empty"

    r0 = rows[0]
    assert "xB_comp_sp" in r0
    assert "xB_comp_pv" in r0
    assert "Boilup_cmd_lbmolph" in r0
    assert np.isfinite(float(r0["xB_comp_sp"]))
    assert np.isfinite(float(r0["Boilup_cmd_lbmolph"]))
