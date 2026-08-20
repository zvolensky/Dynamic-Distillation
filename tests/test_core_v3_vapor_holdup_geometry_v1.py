from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    build_column_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_geometry_v1 import (
    audit_vapor_geometry,
    build_column_vapor_geometry,
    evaluate_free_vapor_volume,
    gross_capacity_mapping,
    horizontal_drum_capacity_ft3,
    vertical_cylinder_capacity_ft3,
)


def _source():
    topology = build_column_topology()
    geometry = SimpleNamespace(
        area_ft2_per_stage=np.asarray((20.0, 20.0, 25.0, 25.0, 30.0)),
        tray_spacing_ft_per_stage=np.asarray((2.0, 2.0, 2.5, 2.5, 3.0)),
        vapor_volume_ft3_per_stage=np.asarray((30.0, 30.0, 45.0, 45.0, 60.0)),
    )
    column = SimpleNamespace(n_stages=5, geometry=geometry)
    specs = {
        "Top Drum Diameter (ft)": 4.0,
        "Top Drum Length (ft)": 12.0,
        "Bottom Sump Diameter (ft)": 5.0,
        "Bottom Sump Height (ft)": 8.0,
    }
    return column, specs, topology


def test_geometry_maps_every_volume_and_preserves_topology_order():
    column, specs, topology = _source()
    geometry = build_column_vapor_geometry(column, specs, topology)
    audit = audit_vapor_geometry(geometry, topology)

    assert tuple(record.volume_id for record in geometry) == topology.volume_ids
    assert tuple(record.source_stage_1based for record in geometry) == (1, 2, 3, 4, 5)
    assert audit.tray_volume_count == 3
    assert audit.terminal_volume_count == 2
    assert audit.pass_gate


def test_terminal_and_tray_capacities_use_declared_geometry():
    column, specs, topology = _source()
    geometry = build_column_vapor_geometry(column, specs, topology)
    capacities = gross_capacity_mapping(geometry)

    assert capacities[topology.top_volume] == pytest.approx(
        horizontal_drum_capacity_ft3(4.0, 12.0)
    )
    assert capacities[topology.volume_ids[1]] == pytest.approx(20.0 * 2.0)
    assert capacities[topology.volume_ids[2]] == pytest.approx(25.0 * 2.5)
    assert capacities[topology.bottom_volume] == pytest.approx(
        vertical_cylinder_capacity_ft3(5.0, 8.0) + 60.0
    )
    assert geometry[-1].fixed_vapor_extension_ft3 == 60.0


def test_free_vapor_volume_subtracts_live_liquid_volume():
    column, specs, topology = _source()
    geometry = build_column_vapor_geometry(column, specs, topology)
    inventory = np.full((5, 3), 1.0)
    density = np.full(5, 0.5)
    evaluation = evaluate_free_vapor_volume(geometry, inventory, density)

    assert np.allclose(evaluation.liquid_volume_ft3, 6.0)
    assert np.allclose(
        evaluation.free_vapor_volume_ft3,
        evaluation.gross_capacity_ft3 - 6.0,
    )


def test_free_vapor_volume_rejects_overfill():
    column, specs, topology = _source()
    geometry = build_column_vapor_geometry(column, specs, topology)
    inventory = np.full((5, 3), 1.0)
    inventory[1] = 100.0

    with pytest.raises(ValueError, match="overfills vapor control volume"):
        evaluate_free_vapor_volume(
            geometry,
            inventory,
            np.full(5, 0.5),
        )


def test_geometry_audit_rejects_missing_liquid_displacement():
    column, specs, topology = _source()
    geometry = build_column_vapor_geometry(column, specs, topology)
    bad = (
        geometry[0],
        replace(geometry[1], liquid_displacement_active=False),
        *geometry[2:],
    )
    audit = audit_vapor_geometry(bad, topology)

    assert audit.liquid_displacement_missing == (topology.volume_ids[1],)
    assert not audit.pass_gate
