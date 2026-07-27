from dynamic_distillation.core_v3.zero_rate_feasibility_v1 import (
    audit_zero_rate_feasibility,
)


def test_dd118_three_component_case_identifies_six_surplus_targets():
    audit = audit_zero_rate_feasibility(("A", "B", "C"))

    assert audit.zero_rate_dae_shape == (46, 46)
    assert audit.zero_rate_dae_structural_rank == 46
    assert audit.all_target_shape == (52, 46)
    assert audit.all_target_equation_surplus == 6
    assert audit.augmented_shape == (71, 65)
    assert audit.augmented_structural_rank == 65
    assert audit.augmented_equation_surplus == 6
    assert len(audit.unmatched_all_target_rows) == 6
    assert audit.released_global_target_count == 4
    assert audit.terminal_scale_freedom_count == 2
    assert audit.pass_gate


def test_dd118_two_component_case_remains_generic():
    audit = audit_zero_rate_feasibility(("A", "B"))

    assert audit.zero_rate_dae_shape == (36, 36)
    assert audit.zero_rate_dae_structural_rank == 36
    assert audit.all_target_shape == (41, 36)
    assert audit.all_target_equation_surplus == 5
    assert audit.released_global_target_count == 3
    assert audit.terminal_scale_freedom_count == 2
    assert audit.pass_gate


def test_dd118_recommended_structure_retains_only_terminal_targets():
    audit = audit_zero_rate_feasibility(("A", "B", "C"))

    assert audit.recommended_shape == (48, 46)
    assert audit.recommended_structural_rank == 46
    assert audit.recommended_equation_surplus == 2
    assert audit.terminal_target_rows == (
        "terminal_total_inventory[reflux_drum]",
        "terminal_total_inventory[combined_reboiler_sump]",
    )
    assert audit.global_target_rows == (
        "global_component_inventory[A]",
        "global_component_inventory[B]",
        "global_component_inventory[C]",
        "global_stored_energy",
    )
