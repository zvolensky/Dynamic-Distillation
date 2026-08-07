from dataclasses import replace

import pytest

from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    audit_provider_governed_registry,
    build_column_topology,
    build_provider_governed_registry,
)


COMPONENTS = ("Propane", "n-Butane", "n-Pentane")


def test_dd167_seven_volume_registry_is_square_full_rank_and_conservative():
    topology = build_column_topology(
        rectifying_volume_count=2,
        stripping_volume_count=2,
    )
    registry = build_provider_governed_registry(COMPONENTS, topology=topology)
    audit = audit_provider_governed_registry(registry)

    assert len(topology.volume_ids) == 7
    assert topology.feed_volume == "feed_tray"
    assert len(topology.liquid_links) == len(topology.vapor_links) == 6
    assert audit.unknown_count == audit.residual_count == 56
    assert audit.expected_count == audit.structural_rank == 56
    assert audit.structural_nullity == 0
    assert audit.component_conservation_passed
    assert audit.energy_conservation_passed
    assert audit.pass_gate


def test_dd167_scaled_registry_preserves_provider_ownership_and_no_execution():
    topology = build_column_topology(
        rectifying_volume_count=2,
        stripping_volume_count=2,
    )
    registry = build_provider_governed_registry(COMPONENTS, topology=topology)
    audit = audit_provider_governed_registry(registry)

    assert audit.vapor_unknown_count == 6
    assert audit.francis_liquid_unknown_count == 5
    assert audit.full_fugacity_row_count == 18
    assert audit.condenser_bubble_row_count == 3
    assert not audit.governing_tp_flash_uses
    assert not audit.production_independent_pr_uses
    assert not audit.live_property_evaluation_attempted
    assert not audit.nonlinear_solve_attempted
    assert not audit.dynamic_integration_attempted


def test_scaled_registry_count_is_generic_in_volume_and_component_count():
    topology = build_column_topology(
        rectifying_volume_count=3,
        stripping_volume_count=2,
    )
    components = ("light", "middle", "heavy", "trace")
    audit = audit_provider_governed_registry(
        build_provider_governed_registry(components, topology=topology)
    )
    expected = 2 * len(topology.volume_ids) * (len(components) + 1)

    assert audit.unknown_count == audit.residual_count == expected
    assert audit.structural_rank == expected
    assert audit.pass_gate


def test_scaled_registry_rejects_broken_adjacency():
    topology = build_column_topology(
        rectifying_volume_count=2,
        stripping_volume_count=2,
    )
    broken = replace(topology, liquid_links=topology.liquid_links[:-1])

    with pytest.raises(ValueError, match="liquid links"):
        build_provider_governed_registry(COMPONENTS, topology=broken)
