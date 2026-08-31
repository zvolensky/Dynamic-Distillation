from __future__ import annotations

from pathlib import Path
import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_dynamic as runner


def test_core_v3_timestep_policy_defaults_inherits_and_overrides() -> None:
    assert runner._resolve_timestep_sec(None, {}) == pytest.approx(0.25)
    assert runner._resolve_timestep_sec(None, {"dt_sec": 0.5}) == pytest.approx(0.5)
    assert runner._resolve_timestep_sec(0.25, {"dt_sec": 0.5}) == pytest.approx(0.25)


def test_core_v3_timestep_policy_rejects_unvalidated_values() -> None:
    with pytest.raises(ValueError, match="validated values: 0.25, 0.5 s"):
        runner._resolve_timestep_sec(1.0, {"dt_sec": 0.25})

    with pytest.raises(ValueError, match="validated values: 0.25, 0.5 s"):
        runner._resolve_timestep_sec(None, {"dt_sec": 0.75})


def test_core_v3_checkpoint_records_selected_timestep(tmp_path: Path) -> None:
    workbook = tmp_path / "case.xlsx"
    workbook.write_bytes(b"workbook")
    checkpoint = tmp_path / "checkpoint.npz"
    topology = SimpleNamespace(volume_ids=("reflux_drum",))
    controllers = SimpleNamespace(
        drum_kc=4.0,
        drum_ti_sec=120.0,
        sump_kc=8.0,
        sump_ti_sec=120.0,
    )
    context = {
        "contract": SimpleNamespace(
            base=SimpleNamespace(
                topology=SimpleNamespace(column=topology),
                component_names=("A",),
            ),
            controllers=controllers,
        )
    }
    reference = SimpleNamespace(
        liquid_component_inventory_lbmol=np.ones((1, 1)),
        vapor_component_inventory_lbmol=np.ones((1, 1)),
        phase_transfer_lbmolph=np.zeros((1, 1)),
        phase_transfer_scale_lbmolph=np.ones((1, 1)),
        temperature_F=np.asarray([120.0]),
        pressure_psia=np.asarray([220.0]),
        hydraulic_liquid_flow_lbmolph=np.asarray([], dtype=float),
        vapor_flow_lbmolph=np.asarray([], dtype=float),
        total_stored_energy_BTU=np.asarray([1.0]),
        condenser_duty_BTUph=-50.0e6,
    )

    runner._write_checkpoint(
        checkpoint,
        workbook=workbook,
        context=context,
        reference=reference,
        controller_memory=np.zeros(2),
        previous_coordinates=np.zeros(1),
        controller_rate_per_sec=np.zeros(2),
        product_log_ratio=np.zeros(2),
        final_time_s=10.0,
        timestep_sec=0.5,
        source="test",
    )

    with np.load(checkpoint, allow_pickle=False) as saved:
        metadata = json.loads(str(saved["metadata_json"].item()))
    assert metadata["dt_sec"] == pytest.approx(0.5)


def test_core_v3_runtime_extension_only_increases_target(tmp_path: Path) -> None:
    control = tmp_path / "runtime_control.json"
    assert runner._requested_total_steps(control, 120) == 120
    control.write_text('{"requested_total_steps": 200}', encoding="utf-8")
    assert runner._requested_total_steps(control, 120) == 200
    control.write_text('{"requested_total_steps": 80}', encoding="utf-8")
    assert runner._requested_total_steps(control, 120) == 120


def _fixture() -> tuple[dict, SimpleNamespace, SimpleNamespace, list[dict]]:
    liquid = np.asarray([[8.0, 2.0], [3.0, 7.0]])
    vapor = np.asarray([[4.0, 1.0], [2.0, 3.0]])
    temperature = np.asarray([120.0, 210.0])
    previous = SimpleNamespace(
        liquid_component_inventory_lbmol=liquid.copy(),
        vapor_component_inventory_lbmol=vapor.copy(),
        temperature_F=temperature.copy(),
    )
    endpoint = SimpleNamespace(
        liquid_component_inventory_lbmol=liquid.copy(),
        vapor_component_inventory_lbmol=vapor.copy(),
        temperature_F=temperature.copy(),
        pressure_psia=np.asarray([220.0, 221.5]),
        vapor_flow_lbmolph=np.asarray([8000.0, 8100.0]),
        condenser_duty_BTUph=-50.0e6,
    )
    evaluation = SimpleNamespace(
        base=SimpleNamespace(endpoint=endpoint),
        distillate_lbmolph=80.0,
        bottoms_lbmolph=120.0,
        level_fraction=np.asarray([0.5, 0.5]),
    )
    context = {
        "spec": SimpleNamespace(
            feed_component_lbmolph=np.asarray([100.0, 100.0]),
            reflux_lbmolph=5952.48,
        ),
        "balance_inputs": SimpleNamespace(reboiler_duty_BTUph=54.706e6),
        "contract": SimpleNamespace(base=SimpleNamespace(component_names=("A", "B"))),
    }
    history = [
        {
            "time_s": 0.0,
            "top_x": np.asarray([0.8, 0.2]),
            "bottom_x": np.asarray([0.3, 0.7]),
            "distillate_lbmolph": 80.0,
            "bottoms_lbmolph": 120.0,
        }
    ]
    return context, previous, evaluation, history


def test_core_v3_steady_state_score_is_zero_for_an_unchanged_state() -> None:
    context, previous, evaluation, history = _fixture()

    metrics = runner._steady_state_metrics(
        context,
        previous,
        evaluation,
        interval_sec=1.0,
        time_s=60.0,
        history=history,
    )

    assert metrics["steady_state_score"] == pytest.approx(0.0)
    assert metrics["steady_state_flag"] == pytest.approx(1.0)


def test_core_v3_summary_reports_score_and_prescribed_reflux() -> None:
    context, previous, evaluation, history = _fixture()
    steady = runner._steady_state_metrics(
        context,
        previous,
        evaluation,
        interval_sec=1.0,
        time_s=60.0,
        history=history,
    )
    report = {
        "scaled_residual_inf_norm": 1.0e-12,
        "jacobian_condition": 1.0e7,
        "root_wall_s": 1.25,
        "function_calls_observed": 43,
        "nfev": 11,
        "njev": 9,
        "jacobian_build_count": 1,
        "color_count": 16,
        "memo_hits_delta": 800,
        "memo_misses_delta": 400,
        "memo_hit_fraction": 2.0 / 3.0,
    }

    row = runner._summary_row(
        context,
        evaluation,
        time_s=60.0,
        wall_elapsed_s=5.0,
        report=report,
        steady=steady,
    )

    assert row["steady_state_score"] == pytest.approx(0.0)
    assert row["Reflux_cmd_lbmolph"] == pytest.approx(5952.48)
    assert row["Boilup_lbmolph"] == pytest.approx(8100.0)
    assert row["root_wall_s"] == pytest.approx(1.25)
    assert row["root_objective_calls"] == pytest.approx(43.0)
    assert row["root_color_count"] == pytest.approx(16.0)
    assert row["root_memo_hit_fraction"] == pytest.approx(2.0 / 3.0)


def test_core_v3_memo_delta_reports_exact_request_reuse() -> None:
    delta = runner._memo_delta(
        {"hits": 100, "misses": 50, "entries": 40},
        {"hits": 900, "misses": 450, "entries": 80},
    )

    assert delta["memo_hits_delta"] == 800
    assert delta["memo_misses_delta"] == 400
    assert delta["memo_hit_fraction"] == pytest.approx(2.0 / 3.0)


def test_composition_quality_limit_is_opt_in() -> None:
    assert runner._composition_quality_pass(0.25, None)
    assert runner._composition_quality_pass(0.0019, 0.002)
    assert not runner._composition_quality_pass(0.002, 0.002)
    with pytest.raises(ValueError, match="must be positive"):
        runner._composition_quality_pass(0.0, 0.0)


def test_core_v3_controller_retuning_preserves_product_outputs_bumplessly() -> None:
    controllers = SimpleNamespace(
        drum_level_setpoint_fraction=0.5,
        drum_kc=2.0,
        sump_level_setpoint_fraction=0.5,
        sump_kc=8.0,
    )
    product_logs = np.log(np.asarray([3160.0 / 2519.0, 4607.0 / 4623.0]))
    levels = np.asarray([0.5135, 0.5])

    memory = runner._bumpless_controller_memory(
        product_log_ratio=product_logs,
        level_fraction=levels,
        controllers=controllers,
    )
    gains = np.asarray([controllers.drum_kc, controllers.sump_kc])
    setpoints = np.asarray(
        [
            controllers.drum_level_setpoint_fraction,
            controllers.sump_level_setpoint_fraction,
        ]
    )

    reconstructed_logs = memory + gains * (levels - setpoints)
    assert reconstructed_logs == pytest.approx(product_logs, abs=1.0e-15)


def test_core_v3_regulatory_retuning_preserves_duty_and_reflux_bumplessly() -> None:
    pressure_error = -0.0347
    composition_error = 0.000125
    duty_log = np.log(1.0008)
    reflux_log = np.log(1.0002)
    pressure_kc = 3_000_000.0 / 50_894_825.691564746
    composition_kc = 5_000.0 / 5952.48

    memory, rates = runner._bumpless_regulatory_state(
        controller_memory=np.asarray((0.1, -0.1, 9.0, -9.0)),
        controller_rates_per_sec=np.asarray((0.01, -0.01, 8.0, -8.0)),
        pressure_error_psia=pressure_error,
        condenser_duty_log_ratio=duty_log,
        pressure_kc_per_psia=pressure_kc,
        pressure_ti_sec=180.0,
        composition_error_molfrac=composition_error,
        reflux_log_ratio=reflux_log,
        composition_kc_per_molfrac=composition_kc,
        composition_ti_sec=600.0,
    )

    assert memory[:2] == pytest.approx((0.1, -0.1))
    assert memory[2] + pressure_kc * pressure_error == pytest.approx(duty_log)
    assert memory[3] + composition_kc * composition_error == pytest.approx(reflux_log)
    assert rates[:2] == pytest.approx((0.01, -0.01))
    assert 180.0 * rates[2] == pytest.approx(pressure_kc * pressure_error)
    assert 600.0 * rates[3] == pytest.approx(composition_kc * composition_error)
