import csv
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from dynamic_distillation.uv_flash_sandbox_v1 import (
    _LiquidFlowClosure,
    _LiquidNodeReference,
    _LiquidNodeState,
    _StageBoundaryState,
    _VaporFlowClosure,
    UvMini8PrototypeSpec,
    _compute_huang_htc_liquid_flow_closure,
    _compute_vapor_flow_closure,
    _compute_rhs,
    _pack_state,
    _unpack_state,
    compare_uv_run_to_reference,
)
from dynamic_distillation.uv_flash_stage_v1 import UvFlashStageGuess, UvFlashStageResult


def _write_csv(path: Path, rows):
    fieldnames = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_compare_uv_run_to_reference_skips_placeholder_stage_holdup():
    tmp_path = Path("sandbox/mini8/runs/test_compare_uv")
    tmp_path.mkdir(parents=True, exist_ok=True)
    uv_profile = tmp_path / "uv_profile.csv"
    ref_profile = tmp_path / "ref_profile.csv"

    _write_csv(
        uv_profile,
        [
            {
                "time_s": 0.0,
                "stage": 2,
                "node_type": "stage",
                "T_F": 100.0,
                "m_total_lbmol": 50.0,
                "x_npropane": 0.80,
                "y_npropane": 0.90,
            },
            {
                "time_s": 0.0,
                "stage": 0,
                "node_type": "distillate_drum",
                "m_total_lbmol": 10.0,
                "x_npropane": 0.95,
            },
        ],
    )
    _write_csv(
        ref_profile,
        [
            {
                "time_s": 0.0,
                "stage": 2,
                "node_type": "stage",
                "T_F": 102.0,
                "M_total_lbmol": 0.0,
                "x_n_Propane": 0.78,
                "y_n_Propane": 0.88,
            },
            {
                "time_s": 0.0,
                "stage": 0,
                "node_type": "distillate_drum",
                "Distillate_L_lbmol": 9.5,
                "Distillate_x_n_Propane": 0.96,
            },
        ],
    )

    out = compare_uv_run_to_reference(
        uv_profile_csv=str(uv_profile),
        reference_profile_csv=str(ref_profile),
        out_dir=str(tmp_path),
        run_id="unit",
    )

    with Path(out["metrics_csv"]).open("r", newline="", encoding="utf-8") as f:
        metrics = list(csv.DictReader(f))

    metric_keys = {(row["stage"], row["node_type"], row["variable"]) for row in metrics}
    assert ("2", "stage", "T_F") in metric_keys
    assert ("2", "stage", "x_npropane") in metric_keys
    assert ("2", "stage", "y_npropane") in metric_keys
    assert ("0", "distillate_drum", "m_total_lbmol") in metric_keys
    assert ("0", "distillate_drum", "x_npropane") in metric_keys
    assert ("2", "stage", "m_total_lbmol") not in metric_keys


def test_compute_huang_htc_liquid_flow_closure_uses_holdup_over_tau():
    spec = UvMini8PrototypeSpec(
        excel_path="dummy.xlsx",
        component_names=["n-Propane"],
        n_total_stages=4,
        active_stage0=np.asarray([1, 2], dtype=int),
        active_stage1=np.asarray([2, 3], dtype=int),
        fixed_total_volume_ft3=np.asarray([1.0, 1.0], dtype=float),
        initial_total_component_holdup_lbmol=np.asarray([[10.0], [20.0]], dtype=float),
        initial_total_internal_energy_BTU=np.asarray([0.0, 0.0], dtype=float),
        initial_guesses=[
            UvFlashStageGuess(T_F=100.0, P_psia=120.0, beta_vapor=0.5),
            UvFlashStageGuess(T_F=110.0, P_psia=130.0, beta_vapor=0.5),
        ],
        top_stage_boundary=_StageBoundaryState(
            T_F=90.0,
            P_psia=115.0,
            x_liq=np.asarray([1.0], dtype=float),
            hL_BTU_lbmol=10.0,
            y_vap=np.asarray([1.0], dtype=float),
            hV_BTU_lbmol=11.0,
        ),
        bottom_stage_boundary=_StageBoundaryState(
            T_F=120.0,
            P_psia=140.0,
            x_liq=np.asarray([1.0], dtype=float),
            hL_BTU_lbmol=20.0,
            y_vap=np.asarray([1.0], dtype=float),
            hV_BTU_lbmol=21.0,
        ),
        top_node_reference=_LiquidNodeReference(
            stage_label=0,
            node_type="distillate_drum",
            T_F=90.0,
            P_psia=115.0,
            initial_component_holdup_lbmol=np.asarray([5.0], dtype=float),
            initial_hL_BTU_lbmol=10.0,
        ),
        bottom_node_reference=_LiquidNodeReference(
            stage_label=5,
            node_type="bottoms_sump",
            T_F=120.0,
            P_psia=140.0,
            initial_component_holdup_lbmol=np.asarray([7.0], dtype=float),
            initial_hL_BTU_lbmol=20.0,
        ),
        feed_term=None,
        L_lbmolps=np.asarray([1.0, 2.0, 3.0, 0.25], dtype=float),
        V_lbmolps=np.asarray([0.0, 7.0, 8.0, 0.4], dtype=float),
        distillate_total_lbmolps=0.5,
        bottoms_total_lbmolps=0.25,
        dry_tray_K=1.0,
        conductance_nominal_hi_ratio=1.25,
        huang_liquid_htc_sec=5.0,
        geometry=SimpleNamespace(active_area_ft2_per_stage=np.ones(4), area_ft2_per_stage=np.ones(4)),
        component_mw_lbm_per_lbmol=None,
        condenser_is_total=True,
        reboiler_is_partial=True,
    )
    y = _pack_state(
        np.asarray([[10.0], [20.0]], dtype=float),
        np.asarray([0.0, 0.0], dtype=float),
        np.asarray([5.0], dtype=float),
        np.asarray([7.0], dtype=float),
        50.0,
        140.0,
    )
    stage_results = [
        UvFlashStageResult(
            T_F=100.0,
            P_psia=120.0,
            beta_vapor=0.5,
            x=np.asarray([1.0], dtype=float),
            y=np.asarray([1.0], dtype=float),
            K=np.asarray([1.0], dtype=float),
            HL_BTU_lbmol=1.0,
            HV_BTU_lbmol=2.0,
            uL_BTU_lbmol=0.0,
            uV_BTU_lbmol=0.0,
            vL_ft3_lbmol=1.0,
            vV_ft3_lbmol=1.0,
            Z_vapor=1.0,
            residual_u_BTU_lbmol=0.0,
            residual_v_ft3_lbmol=0.0,
            residual_beta=0.0,
            converged=True,
            iterations=1,
        ),
        UvFlashStageResult(
            T_F=110.0,
            P_psia=130.0,
            beta_vapor=0.25,
            x=np.asarray([1.0], dtype=float),
            y=np.asarray([1.0], dtype=float),
            K=np.asarray([1.0], dtype=float),
            HL_BTU_lbmol=3.0,
            HV_BTU_lbmol=4.0,
            uL_BTU_lbmol=0.0,
            uV_BTU_lbmol=0.0,
            vL_ft3_lbmol=2.0,
            vV_ft3_lbmol=1.0,
            Z_vapor=1.0,
            residual_u_BTU_lbmol=0.0,
            residual_v_ft3_lbmol=0.0,
            residual_beta=0.0,
            converged=True,
            iterations=1,
        ),
    ]
    out = _compute_huang_htc_liquid_flow_closure(
        spec=spec,
        y=y,
        stage_results=stage_results,
        l_prev_lbmolps=np.asarray([1.0, 2.0, 3.0, 0.25], dtype=float),
    )
    # Internal stage 2 raw flow: liquid holdup = (1-beta)*10 = 5 lbmol, tau = 5 s -> 1 lbmol/s.
    assert np.isclose(out.raw_lbmolph[1], 3600.0)
    # Internal stage 3 raw flow: liquid holdup = (1-beta)*20 = 15 lbmol, tau = 5 s -> 3 lbmol/s.
    assert np.isclose(out.raw_lbmolph[2], 10800.0)


def test_compute_rhs_uses_liquid_flow_closure_instead_of_profile():
    spec = UvMini8PrototypeSpec(
        excel_path="dummy.xlsx",
        component_names=["n-Propane"],
        n_total_stages=4,
        active_stage0=np.asarray([1, 2, 3], dtype=int),
        active_stage1=np.asarray([2, 3, 4], dtype=int),
        fixed_total_volume_ft3=np.asarray([1.0, 1.0, 1.0], dtype=float),
        initial_total_component_holdup_lbmol=np.asarray([[10.0], [20.0], [12.0]], dtype=float),
        initial_total_internal_energy_BTU=np.asarray([0.0, 0.0, 0.0], dtype=float),
        initial_guesses=[
            UvFlashStageGuess(T_F=100.0, P_psia=120.0, beta_vapor=0.5),
            UvFlashStageGuess(T_F=110.0, P_psia=130.0, beta_vapor=0.5),
            UvFlashStageGuess(T_F=120.0, P_psia=140.0, beta_vapor=0.5),
        ],
        top_stage_boundary=_StageBoundaryState(
            T_F=90.0,
            P_psia=115.0,
            x_liq=np.asarray([1.0], dtype=float),
            hL_BTU_lbmol=10.0,
            y_vap=np.asarray([1.0], dtype=float),
            hV_BTU_lbmol=11.0,
        ),
        bottom_stage_boundary=_StageBoundaryState(
            T_F=120.0,
            P_psia=140.0,
            x_liq=np.asarray([1.0], dtype=float),
            hL_BTU_lbmol=20.0,
            y_vap=np.asarray([1.0], dtype=float),
            hV_BTU_lbmol=21.0,
        ),
        top_node_reference=_LiquidNodeReference(
            stage_label=0,
            node_type="distillate_drum",
            T_F=90.0,
            P_psia=115.0,
            initial_component_holdup_lbmol=np.asarray([5.0], dtype=float),
            initial_hL_BTU_lbmol=10.0,
        ),
        bottom_node_reference=_LiquidNodeReference(
            stage_label=5,
            node_type="bottoms_sump",
            T_F=120.0,
            P_psia=140.0,
            initial_component_holdup_lbmol=np.asarray([7.0], dtype=float),
            initial_hL_BTU_lbmol=20.0,
        ),
        feed_term=None,
        L_lbmolps=np.asarray([1.0, 2.0, 3.0, 0.0], dtype=float),
        V_lbmolps=np.asarray([0.0, 7.0, 8.0, 9.0], dtype=float),
        distillate_total_lbmolps=0.5,
        bottoms_total_lbmolps=0.25,
        dry_tray_K=1.0,
        conductance_nominal_hi_ratio=1.25,
        huang_liquid_htc_sec=10.0,
        geometry=SimpleNamespace(),
        component_mw_lbm_per_lbmol=None,
        condenser_is_total=True,
    )
    y = _pack_state(
        np.asarray([[10.0], [20.0], [12.0]], dtype=float),
        np.asarray([0.0, 0.0, 0.0], dtype=float),
        np.asarray([5.0], dtype=float),
        np.asarray([7.0], dtype=float),
        50.0,
        140.0,
    )
    stage_results = [
        UvFlashStageResult(
            T_F=100.0,
            P_psia=120.0,
            beta_vapor=0.5,
            x=np.asarray([1.0], dtype=float),
            y=np.asarray([1.0], dtype=float),
            K=np.asarray([1.0], dtype=float),
            HL_BTU_lbmol=1.0,
            HV_BTU_lbmol=2.0,
            uL_BTU_lbmol=0.0,
            uV_BTU_lbmol=0.0,
            vL_ft3_lbmol=1.0,
            vV_ft3_lbmol=1.0,
            Z_vapor=1.0,
            residual_u_BTU_lbmol=0.0,
            residual_v_ft3_lbmol=0.0,
            residual_beta=0.0,
            converged=True,
            iterations=1,
        ),
        UvFlashStageResult(
            T_F=110.0,
            P_psia=130.0,
            beta_vapor=0.5,
            x=np.asarray([1.0], dtype=float),
            y=np.asarray([1.0], dtype=float),
            K=np.asarray([1.0], dtype=float),
            HL_BTU_lbmol=3.0,
            HV_BTU_lbmol=4.0,
            uL_BTU_lbmol=0.0,
            uV_BTU_lbmol=0.0,
            vL_ft3_lbmol=1.0,
            vV_ft3_lbmol=1.0,
            Z_vapor=1.0,
            residual_u_BTU_lbmol=0.0,
            residual_v_ft3_lbmol=0.0,
            residual_beta=0.0,
            converged=True,
            iterations=1,
        ),
        UvFlashStageResult(
            T_F=120.0,
            P_psia=140.0,
            beta_vapor=0.5,
            x=np.asarray([1.0], dtype=float),
            y=np.asarray([1.0], dtype=float),
            K=np.asarray([1.0], dtype=float),
            HL_BTU_lbmol=5.0,
            HV_BTU_lbmol=6.0,
            uL_BTU_lbmol=0.0,
            uV_BTU_lbmol=0.0,
            vL_ft3_lbmol=1.0,
            vV_ft3_lbmol=1.0,
            Z_vapor=1.0,
            residual_u_BTU_lbmol=0.0,
            residual_v_ft3_lbmol=0.0,
            residual_beta=0.0,
            converged=True,
            iterations=1,
        ),
    ]
    condenser_state = UvFlashStageResult(
        T_F=95.0,
        P_psia=118.0,
        beta_vapor=0.0,
        x=np.asarray([1.0], dtype=float),
        y=np.asarray([1.0], dtype=float),
        K=np.asarray([1.0], dtype=float),
        HL_BTU_lbmol=0.5,
        HV_BTU_lbmol=1.5,
        uL_BTU_lbmol=0.0,
        uV_BTU_lbmol=0.0,
        vL_ft3_lbmol=1.0,
        vV_ft3_lbmol=1.0,
        Z_vapor=1.0,
        residual_u_BTU_lbmol=0.0,
        residual_v_ft3_lbmol=0.0,
        residual_beta=0.0,
        converged=True,
        iterations=1,
    )
    top_node = _LiquidNodeState(
        stage_label=0,
        node_type="distillate_drum",
        T_F=90.0,
        P_psia=115.0,
        total_component_holdup_lbmol=np.asarray([5.0], dtype=float),
        total_moles_lbmol=5.0,
        x_liq=np.asarray([1.0], dtype=float),
        hL_BTU_lbmol=10.0,
    )
    bottom_node = _LiquidNodeState(
        stage_label=5,
        node_type="bottoms_sump",
        T_F=120.0,
        P_psia=140.0,
        total_component_holdup_lbmol=np.asarray([7.0], dtype=float),
        total_moles_lbmol=7.0,
        x_liq=np.asarray([1.0], dtype=float),
        hL_BTU_lbmol=20.0,
    )
    liquid_flow = _LiquidFlowClosure(
        used_lbmolps=np.asarray([2.0, 5.0, 6.0, 4.0], dtype=float),
        raw_lbmolph=np.asarray([7200.0, 18000.0, 21600.0, 14400.0], dtype=float),
        h_ow_ft=np.asarray([0.0, 0.1, 0.2, 0.1], dtype=float),
        clamped_flag=np.asarray([0.0, 0.0, 0.0, 0.0], dtype=float),
    )
    vapor_flow = _VaporFlowClosure(
        used_lbmolps=np.asarray([0.0, 7.0, 8.0, 9.0], dtype=float),
        raw_lbmolps=np.asarray([0.0, 7.0, 8.0, 9.0], dtype=float),
        dp_psia=np.asarray([np.nan, 1.0, 1.0, np.nan], dtype=float),
        h_ow_ft=np.asarray([0.0, 0.1, 0.2, 0.0], dtype=float),
        clamped_flag=np.asarray([np.nan, 0.0, 0.0, np.nan], dtype=float),
    )

    dydt = _compute_rhs(
        spec=spec,
        y=y,
        stage_results=stage_results,
        condenser_state=condenser_state,
        reboiler_state=None,
        top_node=top_node,
        bottom_node=bottom_node,
        liquid_flow=liquid_flow,
        vapor_flow=vapor_flow,
    )
    dn, _dU, dtop, dbottom, dtop_u, dbottom_u = _unpack_state(dydt, n_active=3, n_components=1)

    assert dn.shape == (3, 1)
    assert dn[0, 0] == -3.0
    assert dn[1, 0] == 0.0
    assert dn[2, 0] == -7.0
    assert dtop[0] == 4.5
    assert dbottom[0] == 3.75
    assert dtop_u == -21.5
    assert dbottom_u == 15.0


def test_compute_rhs_bottom_node_subtracts_partial_reboiler_boilup():
    spec = UvMini8PrototypeSpec(
        excel_path="dummy.xlsx",
        component_names=["n-Propane"],
        n_total_stages=4,
        active_stage0=np.asarray([1, 2], dtype=int),
        active_stage1=np.asarray([2, 3], dtype=int),
        fixed_total_volume_ft3=np.asarray([1.0, 1.0], dtype=float),
        initial_total_component_holdup_lbmol=np.asarray([[10.0], [20.0]], dtype=float),
        initial_total_internal_energy_BTU=np.asarray([0.0, 0.0], dtype=float),
        initial_guesses=[
            UvFlashStageGuess(T_F=100.0, P_psia=120.0, beta_vapor=0.5),
            UvFlashStageGuess(T_F=110.0, P_psia=130.0, beta_vapor=0.5),
        ],
        top_stage_boundary=_StageBoundaryState(
            T_F=90.0,
            P_psia=115.0,
            x_liq=np.asarray([1.0], dtype=float),
            hL_BTU_lbmol=10.0,
            y_vap=np.asarray([1.0], dtype=float),
            hV_BTU_lbmol=11.0,
        ),
        bottom_stage_boundary=_StageBoundaryState(
            T_F=120.0,
            P_psia=140.0,
            x_liq=np.asarray([1.0], dtype=float),
            hL_BTU_lbmol=20.0,
            y_vap=np.asarray([1.0], dtype=float),
            hV_BTU_lbmol=21.0,
        ),
        top_node_reference=_LiquidNodeReference(
            stage_label=0,
            node_type="distillate_drum",
            T_F=90.0,
            P_psia=115.0,
            initial_component_holdup_lbmol=np.asarray([5.0], dtype=float),
            initial_hL_BTU_lbmol=10.0,
        ),
        bottom_node_reference=_LiquidNodeReference(
            stage_label=5,
            node_type="bottoms_sump",
            T_F=120.0,
            P_psia=140.0,
            initial_component_holdup_lbmol=np.asarray([7.0], dtype=float),
            initial_hL_BTU_lbmol=20.0,
        ),
        feed_term=None,
        L_lbmolps=np.asarray([1.0, 2.0, 3.0, 0.25], dtype=float),
        V_lbmolps=np.asarray([0.0, 7.0, 8.0, 0.4], dtype=float),
        distillate_total_lbmolps=0.5,
        bottoms_total_lbmolps=0.25,
        dry_tray_K=1.0,
        conductance_nominal_hi_ratio=1.25,
        huang_liquid_htc_sec=10.0,
        geometry=SimpleNamespace(),
        component_mw_lbm_per_lbmol=None,
        condenser_is_total=True,
        reboiler_is_partial=True,
    )
    y = _pack_state(
        np.asarray([[10.0], [20.0]], dtype=float),
        np.asarray([0.0, 0.0], dtype=float),
        np.asarray([5.0], dtype=float),
        np.asarray([7.0], dtype=float),
        50.0,
        140.0,
    )
    stage_results = [
        UvFlashStageResult(
            T_F=100.0,
            P_psia=120.0,
            beta_vapor=0.5,
            x=np.asarray([1.0], dtype=float),
            y=np.asarray([1.0], dtype=float),
            K=np.asarray([1.0], dtype=float),
            HL_BTU_lbmol=1.0,
            HV_BTU_lbmol=2.0,
            uL_BTU_lbmol=0.0,
            uV_BTU_lbmol=0.0,
            vL_ft3_lbmol=1.0,
            vV_ft3_lbmol=1.0,
            Z_vapor=1.0,
            residual_u_BTU_lbmol=0.0,
            residual_v_ft3_lbmol=0.0,
            residual_beta=0.0,
            converged=True,
            iterations=1,
        ),
        UvFlashStageResult(
            T_F=110.0,
            P_psia=130.0,
            beta_vapor=0.5,
            x=np.asarray([1.0], dtype=float),
            y=np.asarray([1.0], dtype=float),
            K=np.asarray([1.0], dtype=float),
            HL_BTU_lbmol=3.0,
            HV_BTU_lbmol=4.0,
            uL_BTU_lbmol=0.0,
            uV_BTU_lbmol=0.0,
            vL_ft3_lbmol=1.0,
            vV_ft3_lbmol=1.0,
            Z_vapor=1.0,
            residual_u_BTU_lbmol=0.0,
            residual_v_ft3_lbmol=0.0,
            residual_beta=0.0,
            converged=True,
            iterations=1,
        ),
    ]
    condenser_state = UvFlashStageResult(
        T_F=95.0,
        P_psia=118.0,
        beta_vapor=0.0,
        x=np.asarray([1.0], dtype=float),
        y=np.asarray([1.0], dtype=float),
        K=np.asarray([1.0], dtype=float),
        HL_BTU_lbmol=0.5,
        HV_BTU_lbmol=1.5,
        uL_BTU_lbmol=0.0,
        uV_BTU_lbmol=0.0,
        vL_ft3_lbmol=1.0,
        vV_ft3_lbmol=1.0,
        Z_vapor=1.0,
        residual_u_BTU_lbmol=0.0,
        residual_v_ft3_lbmol=0.0,
        residual_beta=0.0,
        converged=True,
        iterations=1,
    )
    reboiler_state = UvFlashStageResult(
        T_F=130.0,
        P_psia=140.0,
        beta_vapor=0.0,
        x=np.asarray([1.0], dtype=float),
        y=np.asarray([1.0], dtype=float),
        K=np.asarray([1.0], dtype=float),
        HL_BTU_lbmol=5.0,
        HV_BTU_lbmol=6.0,
        uL_BTU_lbmol=0.0,
        uV_BTU_lbmol=0.0,
        vL_ft3_lbmol=1.0,
        vV_ft3_lbmol=1.0,
        Z_vapor=1.0,
        residual_u_BTU_lbmol=0.0,
        residual_v_ft3_lbmol=0.0,
        residual_beta=0.0,
        converged=True,
        iterations=1,
    )
    top_node = _LiquidNodeState(
        stage_label=0,
        node_type="distillate_drum",
        T_F=90.0,
        P_psia=115.0,
        total_component_holdup_lbmol=np.asarray([5.0], dtype=float),
        total_moles_lbmol=5.0,
        x_liq=np.asarray([1.0], dtype=float),
        hL_BTU_lbmol=10.0,
    )
    bottom_node = _LiquidNodeState(
        stage_label=5,
        node_type="bottoms_sump",
        T_F=120.0,
        P_psia=140.0,
        total_component_holdup_lbmol=np.asarray([7.0], dtype=float),
        total_moles_lbmol=7.0,
        x_liq=np.asarray([1.0], dtype=float),
        hL_BTU_lbmol=20.0,
    )
    liquid_flow = _LiquidFlowClosure(
        used_lbmolps=np.asarray([2.0, 5.0, 6.0, 0.25], dtype=float),
        raw_lbmolph=np.asarray([7200.0, 18000.0, 21600.0, 900.0], dtype=float),
        h_ow_ft=np.asarray([0.0, 0.1, 0.2, 0.0], dtype=float),
        clamped_flag=np.asarray([0.0, 0.0, 0.0, 0.0], dtype=float),
    )
    vapor_flow = _VaporFlowClosure(
        used_lbmolps=np.asarray([0.0, 7.0, 8.0, 0.4], dtype=float),
        raw_lbmolps=np.asarray([0.0, 7.0, 8.0, 0.4], dtype=float),
        dp_psia=np.asarray([np.nan, 1.0, 1.0, np.nan], dtype=float),
        h_ow_ft=np.asarray([0.0, 0.1, 0.2, 0.0], dtype=float),
        clamped_flag=np.asarray([np.nan, 0.0, 0.0, np.nan], dtype=float),
    )

    dydt = _compute_rhs(
        spec=spec,
        y=y,
        stage_results=stage_results,
        condenser_state=condenser_state,
        reboiler_state=reboiler_state,
        top_node=top_node,
        bottom_node=bottom_node,
        liquid_flow=liquid_flow,
        vapor_flow=vapor_flow,
    )
    _dn, _dU, _dtop, dbottom, _dtop_u, dbottom_u = _unpack_state(dydt, n_active=2, n_components=1)

    assert dbottom[0] == 5.35
    assert dbottom_u == 10.6


def test_vapor_flow_closure_uses_reboiler_duty_for_boilup():
    spec = UvMini8PrototypeSpec(
        excel_path="dummy.xlsx",
        component_names=["n-Propane"],
        n_total_stages=4,
        active_stage0=np.asarray([1, 2], dtype=int),
        active_stage1=np.asarray([2, 3], dtype=int),
        fixed_total_volume_ft3=np.asarray([1.0, 1.0], dtype=float),
        initial_total_component_holdup_lbmol=np.asarray([[10.0], [20.0]], dtype=float),
        initial_total_internal_energy_BTU=np.asarray([0.0, 0.0], dtype=float),
        initial_guesses=[
            UvFlashStageGuess(T_F=100.0, P_psia=120.0, beta_vapor=0.5),
            UvFlashStageGuess(T_F=110.0, P_psia=130.0, beta_vapor=0.5),
        ],
        top_stage_boundary=_StageBoundaryState(
            T_F=90.0,
            P_psia=115.0,
            x_liq=np.asarray([1.0], dtype=float),
            hL_BTU_lbmol=10.0,
            y_vap=np.asarray([1.0], dtype=float),
            hV_BTU_lbmol=11.0,
        ),
        bottom_stage_boundary=_StageBoundaryState(
            T_F=120.0,
            P_psia=140.0,
            x_liq=np.asarray([1.0], dtype=float),
            hL_BTU_lbmol=20.0,
            y_vap=np.asarray([1.0], dtype=float),
            hV_BTU_lbmol=21.0,
        ),
        top_node_reference=_LiquidNodeReference(
            stage_label=0,
            node_type="distillate_drum",
            T_F=90.0,
            P_psia=115.0,
            initial_component_holdup_lbmol=np.asarray([5.0], dtype=float),
            initial_hL_BTU_lbmol=10.0,
        ),
        bottom_node_reference=_LiquidNodeReference(
            stage_label=5,
            node_type="bottoms_sump",
            T_F=120.0,
            P_psia=140.0,
            initial_component_holdup_lbmol=np.asarray([7.0], dtype=float),
            initial_hL_BTU_lbmol=20.0,
        ),
        feed_term=None,
        L_lbmolps=np.asarray([1.0, 2.0, 3.0, 0.25], dtype=float),
        V_lbmolps=np.asarray([0.0, 7.0, 8.0, 0.4], dtype=float),
        distillate_total_lbmolps=0.5,
        bottoms_total_lbmolps=0.25,
        dry_tray_K=1.0,
        conductance_nominal_hi_ratio=1.25,
        huang_liquid_htc_sec=10.0,
        geometry=SimpleNamespace(area_ft2_per_stage=np.ones(4), active_area_ft2_per_stage=np.ones(4)),
        component_mw_lbm_per_lbmol=None,
        q_stage_BTUps=np.asarray([0.0, 0.0, 0.0, 10.0], dtype=float),
        condenser_is_total=True,
        reboiler_is_partial=True,
    )
    y = _pack_state(
        np.asarray([[10.0], [20.0]], dtype=float),
        np.asarray([0.0, 0.0], dtype=float),
        np.asarray([5.0], dtype=float),
        np.asarray([7.0], dtype=float),
        50.0,
        140.0,
    )
    stage_results = [
        UvFlashStageResult(
            T_F=100.0,
            P_psia=120.0,
            beta_vapor=0.5,
            x=np.asarray([1.0], dtype=float),
            y=np.asarray([1.0], dtype=float),
            K=np.asarray([1.0], dtype=float),
            HL_BTU_lbmol=1.0,
            HV_BTU_lbmol=2.0,
            uL_BTU_lbmol=0.0,
            uV_BTU_lbmol=0.0,
            vL_ft3_lbmol=1.0,
            vV_ft3_lbmol=1.0,
            Z_vapor=1.0,
            residual_u_BTU_lbmol=0.0,
            residual_v_ft3_lbmol=0.0,
            residual_beta=0.0,
            converged=True,
            iterations=1,
        ),
        UvFlashStageResult(
            T_F=110.0,
            P_psia=130.0,
            beta_vapor=0.5,
            x=np.asarray([1.0], dtype=float),
            y=np.asarray([1.0], dtype=float),
            K=np.asarray([1.0], dtype=float),
            HL_BTU_lbmol=3.0,
            HV_BTU_lbmol=4.0,
            uL_BTU_lbmol=0.0,
            uV_BTU_lbmol=0.0,
            vL_ft3_lbmol=1.0,
            vV_ft3_lbmol=1.0,
            Z_vapor=1.0,
            residual_u_BTU_lbmol=0.0,
            residual_v_ft3_lbmol=0.0,
            residual_beta=0.0,
            converged=True,
            iterations=1,
        ),
    ]
    condenser_state = UvFlashStageResult(
        T_F=95.0,
        P_psia=118.0,
        beta_vapor=0.0,
        x=np.asarray([1.0], dtype=float),
        y=np.asarray([1.0], dtype=float),
        K=np.asarray([1.0], dtype=float),
        HL_BTU_lbmol=0.5,
        HV_BTU_lbmol=1.5,
        uL_BTU_lbmol=0.0,
        uV_BTU_lbmol=0.0,
        vL_ft3_lbmol=1.0,
        vV_ft3_lbmol=1.0,
        Z_vapor=1.0,
        residual_u_BTU_lbmol=0.0,
        residual_v_ft3_lbmol=0.0,
        residual_beta=0.0,
        converged=True,
        iterations=1,
    )
    reboiler_state = UvFlashStageResult(
        T_F=130.0,
        P_psia=140.0,
        beta_vapor=0.0,
        x=np.asarray([1.0], dtype=float),
        y=np.asarray([1.0], dtype=float),
        K=np.asarray([1.0], dtype=float),
        HL_BTU_lbmol=5.0,
        HV_BTU_lbmol=7.0,
        uL_BTU_lbmol=0.0,
        uV_BTU_lbmol=0.0,
        vL_ft3_lbmol=1.0,
        vV_ft3_lbmol=1.0,
        Z_vapor=1.0,
        residual_u_BTU_lbmol=0.0,
        residual_v_ft3_lbmol=0.0,
        residual_beta=0.0,
        converged=True,
        iterations=1,
    )
    top_node = _LiquidNodeState(
        stage_label=0,
        node_type="distillate_drum",
        T_F=90.0,
        P_psia=115.0,
        total_component_holdup_lbmol=np.asarray([5.0], dtype=float),
        total_moles_lbmol=5.0,
        x_liq=np.asarray([1.0], dtype=float),
        hL_BTU_lbmol=10.0,
    )
    bottom_node = _LiquidNodeState(
        stage_label=5,
        node_type="bottoms_sump",
        T_F=120.0,
        P_psia=140.0,
        total_component_holdup_lbmol=np.asarray([7.0], dtype=float),
        total_moles_lbmol=7.0,
        x_liq=np.asarray([1.0], dtype=float),
        hL_BTU_lbmol=20.0,
    )
    liquid_flow = _LiquidFlowClosure(
        used_lbmolps=np.asarray([2.0, 5.0, 6.0, 0.25], dtype=float),
        raw_lbmolph=np.asarray([7200.0, 18000.0, 21600.0, 900.0], dtype=float),
        h_ow_ft=np.asarray([0.0, 0.1, 0.2, 0.0], dtype=float),
        clamped_flag=np.asarray([0.0, 0.0, 0.0, 0.0], dtype=float),
    )

    vapor_flow = _compute_vapor_flow_closure(
        spec=spec,
        y=y,
        stage_results=stage_results,
        condenser_state=condenser_state,
        reboiler_state=reboiler_state,
        top_node=top_node,
        bottom_node=bottom_node,
        v_prev_lbmolps=None,
        liquid_flow=liquid_flow,
    )

    assert vapor_flow.used_lbmolps[-1] == 5.0
    assert vapor_flow.raw_lbmolps[-1] == 5.0
