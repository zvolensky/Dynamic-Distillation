import math

import pytest

from tools.add_terminal_vessel_geometry import (
    size_horizontal_hemispherical_drum,
    size_vertical_cylindrical_sump,
)


def test_horizontal_drum_includes_two_hemispherical_heads() -> None:
    result = size_horizontal_hemispherical_drum(
        liquid_flow_lbmolph=600.0,
        liquid_density_lbmol_ft3=2.0,
        residence_time_min=10.0,
        normal_liquid_fraction=0.5,
        tangent_length_to_diameter=3.0,
    )

    assert result.normal_holdup_lbmol == pytest.approx(100.0)
    assert result.normal_liquid_volume_ft3 == pytest.approx(50.0)
    assert result.total_volume_ft3 == pytest.approx(100.0)
    expected_volume = (
        math.pi * result.diameter_ft**2 * result.tangent_length_ft / 4.0
        + math.pi * result.diameter_ft**3 / 6.0
    )
    assert expected_volume == pytest.approx(result.total_volume_ft3)
    assert result.tangent_length_ft == pytest.approx(3.0 * result.diameter_ft)
    assert result.overall_length_ft == pytest.approx(result.tangent_length_ft + result.diameter_ft)


def test_vertical_sump_uses_fixed_diameter_and_normal_level() -> None:
    result = size_vertical_cylindrical_sump(
        liquid_flow_lbmolph=600.0,
        liquid_density_lbmol_ft3=2.0,
        residence_time_min=10.0,
        normal_liquid_fraction=0.5,
        diameter_ft=10.0,
    )

    assert result.normal_holdup_lbmol == pytest.approx(100.0)
    assert result.normal_liquid_volume_ft3 == pytest.approx(50.0)
    assert result.total_volume_ft3 == pytest.approx(100.0)
    assert result.total_height_ft == pytest.approx(100.0 / (math.pi * 10.0**2 / 4.0))
    assert result.required_height_ft == pytest.approx(result.total_height_ft)
    assert result.normal_liquid_height_ft == pytest.approx(0.5 * result.total_height_ft)
    assert result.usable_residence_time_min == pytest.approx(10.0)


def test_vertical_sump_sizes_working_inventory_and_applies_minimum_height() -> None:
    result = size_vertical_cylindrical_sump(
        liquid_flow_lbmolph=600.0,
        liquid_density_lbmol_ft3=2.0,
        residence_time_min=10.0,
        normal_liquid_fraction=0.5,
        low_liquid_fraction=0.25,
        diameter_ft=10.0,
        minimum_height_ft=3.0,
    )

    assert result.required_height_ft == pytest.approx(200.0 / (math.pi * 10.0**2 / 4.0))
    assert result.total_height_ft == pytest.approx(3.0)
    assert result.normal_liquid_height_ft == pytest.approx(1.5)
    assert result.low_liquid_height_ft == pytest.approx(0.75)
    assert result.usable_residence_time_min > 10.0


@pytest.mark.parametrize("fraction", [0.0, 1.0, -0.1, 1.1])
def test_invalid_normal_level_is_rejected(fraction: float) -> None:
    with pytest.raises(ValueError, match="between zero and one"):
        size_vertical_cylindrical_sump(
            liquid_flow_lbmolph=600.0,
            liquid_density_lbmol_ft3=2.0,
            residence_time_min=10.0,
            normal_liquid_fraction=fraction,
            diameter_ft=10.0,
        )
