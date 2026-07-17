from dataclasses import replace
from types import SimpleNamespace

import numpy as np

from dynamic_distillation.frozen_checkpoint_closure_v1 import (
    TerminalConservedNode,
    checkpoint_phase_state_to_conserved_totals,
    classify_frozen_closure,
    combine_terminal_nodes,
    summarize_terminal_inventory_mapping,
)
from dynamic_distillation.uv_flash_stage_v1 import BTU_PER_PSI_FT3


def test_checkpoint_phase_state_to_conserved_totals_sums_phases_and_converts_h_to_u():
    unpacked = {
        "tray_L": np.asarray([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]),
        "tray_V": np.asarray([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]),
        "tray_EL_BTU": np.asarray([100.0, 200.0, 300.0]),
        "tray_EV_BTU": np.asarray([10.0, 20.0, 30.0]),
    }
    totals, internal = checkpoint_phase_state_to_conserved_totals(
        unpacked=unpacked,
        active_stage0=[1],
        pressure_psia=[10.0, 20.0, 30.0],
        fixed_total_volume_ft3=[5.0],
    )
    assert np.allclose(totals, [[3.3, 4.4]])
    assert np.allclose(internal, [220.0 - 20.0 * 5.0 * BTU_PER_PSI_FT3])


def test_classification_separates_local_failure_from_global_failure():
    bridge = SimpleNamespace(terminal_mapping_complete=False)
    local_bad = SimpleNamespace(
        converged=False,
        component_relative_max=0.0,
        energy_relative_max=0.0,
        volume_relative_max=0.0,
        equilibrium_beta_max=0.0,
        negative_phase_count=0,
        projection_count=0,
    )
    assert (
        classify_frozen_closure(bridge=bridge, local=local_bad, hydraulic=None)
        == "local_uv_failed"
    )

    local_good = SimpleNamespace(
        converged=True,
        component_relative_max=1.0e-10,
        energy_relative_max=1.0e-10,
        volume_relative_max=1.0e-10,
        equilibrium_beta_max=1.0e-10,
        negative_phase_count=0,
        projection_count=0,
    )
    hydraulic_bad = SimpleNamespace(strict_gate_pass=False)
    assert (
        classify_frozen_closure(
            bridge=bridge,
            local=local_good,
            hydraulic=hydraulic_bad,
        )
        == "local_uv_passed_global_hydraulics_failed_or_unverified"
    )


def _terminal_node(node_id, source_block, components, energy, volume=10.0):
    components = np.asarray(components, dtype=float)
    return TerminalConservedNode(
        node_id=node_id,
        topology_role=node_id,
        source_blocks=(source_block,),
        conserved=True,
        total_component_inventory_lbmol=components,
        total_internal_energy_BTU=float(energy),
        fixed_total_volume_ft3=float(volume),
        liquid_inventory_lbmol=components,
        vapor_inventory_lbmol=np.zeros_like(components),
        temperature_guess_F=100.0,
        pressure_guess_psia=200.0,
    )


def test_terminal_inventory_mapping_accounts_for_all_four_terminal_blocks():
    nodes = (
        _terminal_node("condenser_stage", "tray_stage_1", [1.0, 2.0], 10.0),
        _terminal_node("reflux_drum", "top_boundary", [3.0, 4.0], 20.0),
        _terminal_node("reboiler_stage", "tray_stage_N", [5.0, 6.0], 30.0),
        _terminal_node("bottoms_sump", "bottom_boundary", [7.0, 8.0], 40.0),
    )
    summary = summarize_terminal_inventory_mapping(
        interior_components_lbmol=np.asarray([[10.0, 20.0], [30.0, 40.0]]),
        interior_internal_energy_BTU=np.asarray([100.0, 200.0]),
        checkpoint_total_components_lbmol=np.asarray([56.0, 80.0]),
        checkpoint_total_internal_energy_BTU=400.0,
        nodes=nodes,
    )
    assert summary.accounting_complete is True
    assert summary.algebraic_coupling_complete is False
    assert summary.component_balance_abs_max_lbmol == 0.0
    assert summary.energy_balance_abs_BTU == 0.0


def test_terminal_inventory_mapping_rejects_missing_boundary_source():
    nodes = (
        _terminal_node("condenser_stage", "tray_stage_1", [1.0, 2.0], 10.0),
        _terminal_node("reflux_drum", "top_boundary", [3.0, 4.0], 20.0),
        _terminal_node("reboiler_stage", "tray_stage_N", [5.0, 6.0], 30.0),
    )
    summary = summarize_terminal_inventory_mapping(
        interior_components_lbmol=np.asarray([[10.0, 20.0], [30.0, 40.0]]),
        interior_internal_energy_BTU=np.asarray([100.0, 200.0]),
        checkpoint_total_components_lbmol=np.asarray([49.0, 72.0]),
        checkpoint_total_internal_energy_BTU=360.0,
        nodes=nodes,
    )
    assert summary.accounting_complete is False
    assert "bottom_boundary" not in summary.mapped_source_blocks


def test_terminal_inventory_mapping_accepts_empty_eliminated_algebraic_node():
    empty_condenser = TerminalConservedNode(
        node_id="condenser_stage",
        topology_role="eliminated_algebraic_total_condenser_stage",
        source_blocks=("tray_stage_1",),
        conserved=False,
        total_component_inventory_lbmol=np.asarray([0.0, 0.0]),
        total_internal_energy_BTU=0.0,
        fixed_total_volume_ft3=0.0,
        liquid_inventory_lbmol=np.asarray([0.0, 0.0]),
        vapor_inventory_lbmol=np.asarray([0.0, 0.0]),
        temperature_guess_F=100.0,
        pressure_guess_psia=200.0,
    )
    nodes = (
        empty_condenser,
        _terminal_node("reflux_drum", "top_boundary", [3.0, 4.0], 20.0),
        _terminal_node("reboiler_stage", "tray_stage_N", [5.0, 6.0], 30.0),
        _terminal_node("bottoms_sump", "bottom_boundary", [7.0, 8.0], 40.0),
    )
    summary = summarize_terminal_inventory_mapping(
        interior_components_lbmol=np.asarray([[10.0, 20.0]]),
        interior_internal_energy_BTU=np.asarray([100.0]),
        checkpoint_total_components_lbmol=np.asarray([25.0, 38.0]),
        checkpoint_total_internal_energy_BTU=190.0,
        nodes=nodes,
    )
    assert summary.accounting_complete is True


def test_combine_terminal_nodes_preserves_conserved_totals_and_weighted_guesses():
    first = _terminal_node(
        "reboiler_stage",
        "tray_stage_N",
        [1.0, 2.0],
        30.0,
        volume=5.0,
    )
    second = _terminal_node(
        "bottoms_sump",
        "bottom_boundary",
        [3.0, 4.0],
        40.0,
        volume=15.0,
    )
    second = replace(
        second,
        temperature_guess_F=200.0,
        pressure_guess_psia=300.0,
    )
    combined = combine_terminal_nodes(
        assembly_id="bottom_terminal",
        topology_role="partial_reboiler_and_bottoms_sump",
        nodes=(first, second),
    )
    assert np.allclose(combined.total_component_inventory_lbmol, [4.0, 6.0])
    assert combined.total_internal_energy_BTU == 70.0
    assert combined.fixed_total_volume_ft3 == 20.0
    assert combined.temperature_guess_F == 170.0
    assert combined.pressure_guess_psia == 270.0
    assert set(combined.source_blocks) == {"tray_stage_N", "bottom_boundary"}


def test_classification_separates_terminal_mapping_from_terminal_coupling():
    local_good = SimpleNamespace(
        converged=True,
        component_relative_max=1.0e-10,
        energy_relative_max=1.0e-10,
        volume_relative_max=1.0e-10,
        equilibrium_beta_max=1.0e-10,
        negative_phase_count=0,
        projection_count=0,
    )
    hydraulic_good = SimpleNamespace(strict_gate_pass=True)
    bridge_unmapped = SimpleNamespace(
        terminal_mapping_complete=False,
        terminal_coupling_complete=False,
    )
    assert (
        classify_frozen_closure(
            bridge=bridge_unmapped,
            local=local_good,
            hydraulic=hydraulic_good,
        )
        == "global_hydraulics_passed_terminal_mapping_incomplete"
    )

    bridge_uncoupled = SimpleNamespace(
        terminal_mapping_complete=True,
        terminal_coupling_complete=False,
    )
    assert (
        classify_frozen_closure(
            bridge=bridge_uncoupled,
            local=local_good,
            hydraulic=hydraulic_good,
        )
        == "terminal_inventory_mapped_algebraic_coupling_incomplete"
    )
