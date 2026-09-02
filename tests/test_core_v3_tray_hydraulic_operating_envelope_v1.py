from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from dynamic_distillation.core_v3.tray_hydraulic_operating_envelope_v1 import (
    TrayHydraulicOperatingEnvelopeSpec,
    evaluate_tray_hydraulic_operating_envelope,
)


def _fixture(*, vapor_flow_lbmolph: float = 8000.0):
    topology = SimpleNamespace(
        volume_ids=("reflux_drum", "tray_1", "reboiler_sump"),
        hydraulic_volume_ids=("tray_1",),
        vapor_links=(
            ("tray_1", "reflux_drum", "V_top"),
            ("reboiler_sump", "tray_1", "V_boilup"),
        ),
    )
    endpoint = SimpleNamespace(
        liquid_component_inventory_lbmol=np.asarray(
            ((80.0, 20.0), (20.0, 30.0), (10.0, 90.0))
        ),
        vapor_component_inventory_lbmol=np.asarray(
            ((90.0, 10.0), (50.0, 50.0), (20.0, 80.0))
        ),
        pressure_psia=np.asarray((220.0, 220.1, 220.2)),
        temperature_F=np.asarray((120.0, 170.0, 220.0)),
        vapor_flow_lbmolph=np.asarray((vapor_flow_lbmolph, 8100.0)),
        hydraulic_liquid_flow_lbmolph=np.asarray((6000.0,)),
    )
    properties = SimpleNamespace(
        liquid_density_lbmol_ft3=np.asarray((0.55, 0.50, 0.45)),
        vapor_compressibility_factor=np.asarray((0.80, 0.85, 0.90)),
    )
    pressure_drop = SimpleNamespace(
        liquid_head_drop_psia=np.asarray((0.05, 0.0)),
        dry_tray_drop_psia=np.asarray((0.02, 0.02)),
        over_weir_head_ft=np.asarray((0.10, 0.10)),
    )
    hydraulic_geometry = (
        SimpleNamespace(tray_spacing_ft=1.5),
    )
    pressure_link_geometry = (
        SimpleNamespace(
            include_liquid_head=True,
            active_area_ft2=100.0,
            tray_area_ft2=110.0,
            weir_height_in=2.0,
        ),
        SimpleNamespace(
            include_liquid_head=False,
            active_area_ft2=100.0,
            tray_area_ft2=110.0,
            weir_height_in=2.0,
        ),
    )
    return {
        "topology": topology,
        "endpoint": endpoint,
        "properties": properties,
        "pressure_drop": pressure_drop,
        "hydraulic_geometry": hydraulic_geometry,
        "pressure_link_geometry": pressure_link_geometry,
        "component_mw_lbm_per_lbmol": np.asarray((44.0, 58.0)),
    }


def test_missing_capacity_factor_is_explicitly_not_evaluated() -> None:
    result = evaluate_tray_hydraulic_operating_envelope(
        **_fixture(),
        spec=TrayHydraulicOperatingEnvelopeSpec(),
    )

    assert len(result.stages) == 1
    assert not result.fully_evaluable
    assert result.overall_classification == "not_evaluated"
    assert np.isnan(result.maximum_flooding_fraction)
    assert result.maximum_critical_effective_capacity_factor_ft_s > 0.0
    assert result.critical_effective_capacity_factor_limiting_stage == 2
    assert result.maximum_backup_fraction > 0.0
    assert result.stages[0].limitation == "no declared tray flooding capacity factor"
    assert result.stages[0].weeping_classification == "not_evaluated"


def test_declared_capacity_factor_produces_reproducible_stage_metrics() -> None:
    result = evaluate_tray_hydraulic_operating_envelope(
        **_fixture(),
        spec=TrayHydraulicOperatingEnvelopeSpec(capacity_factor_ft_s=0.35),
    )
    tray = result.stages[0]

    assert result.fully_evaluable
    assert tray.stage == 2
    assert tray.volume == "tray_1"
    assert tray.vapor_superficial_velocity_ft_s > 0.0
    assert tray.vapor_f_factor > 0.0
    assert tray.liquid_to_vapor_mass_flow_parameter > 0.0
    assert tray.predicted_flooding_velocity_ft_s > 0.0
    assert tray.flooding_fraction == pytest.approx(
        tray.vapor_superficial_velocity_ft_s / tray.predicted_flooding_velocity_ft_s
    )
    assert tray.flooding_fraction == pytest.approx(
        tray.critical_effective_capacity_factor_ft_s
        / (result.capacity_factor_ft_s * result.system_factor)
    )
    assert tray.total_tray_pressure_drop_psia == pytest.approx(0.07)
    assert tray.backup_head_ft > tray.clear_liquid_height_ft


def test_flooding_fraction_increases_monotonically_with_vapor_flow() -> None:
    spec = TrayHydraulicOperatingEnvelopeSpec(capacity_factor_ft_s=0.35)
    low = evaluate_tray_hydraulic_operating_envelope(
        **_fixture(vapor_flow_lbmolph=6000.0), spec=spec
    )
    high = evaluate_tray_hydraulic_operating_envelope(
        **_fixture(vapor_flow_lbmolph=9000.0), spec=spec
    )

    assert high.maximum_flooding_fraction > low.maximum_flooding_fraction
    assert (
        high.maximum_critical_effective_capacity_factor_ft_s
        > low.maximum_critical_effective_capacity_factor_ft_s
    )
    assert high.stages[0].vapor_superficial_velocity_ft_s == pytest.approx(
        1.5 * low.stages[0].vapor_superficial_velocity_ft_s
    )


def test_alert_and_hard_stop_thresholds_are_declared_semantics() -> None:
    nominal = evaluate_tray_hydraulic_operating_envelope(
        **_fixture(),
        spec=TrayHydraulicOperatingEnvelopeSpec(
            capacity_factor_ft_s=0.35,
            advisory_fraction=0.01,
            high_loading_fraction=0.02,
            predicted_flooding_fraction=0.03,
            hard_stop_fraction=0.025,
        ),
    )

    assert nominal.overall_classification == "predicted_flooding"
    assert nominal.predicted_flooding
    assert nominal.hard_stop_reached


def test_invalid_or_unordered_alert_fractions_are_rejected() -> None:
    with pytest.raises(ValueError, match="positive and ordered"):
        evaluate_tray_hydraulic_operating_envelope(
            **_fixture(),
            spec=TrayHydraulicOperatingEnvelopeSpec(
                capacity_factor_ft_s=0.35,
                advisory_fraction=0.85,
                high_loading_fraction=0.70,
            ),
        )
