from pathlib import Path

import numpy as np
import pytest

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.reduced_column_feasibility_v1 import (
    FixedSolverSettings,
    build_reduced_feasibility_case,
    reduce_column_to_five_volumes,
    run_reduced_feasibility_study,
)
from dynamic_distillation.direct_steady_state_residual_v1 import (
    build_chemsep_guess,
    evaluate_direct_steady_state_residual,
)
from dynamic_distillation.thermo_relative_volatility_provider_v1 import (
    RelativeVolatilityThermoProviderV1,
)


ROOT = Path(__file__).resolve().parents[1]
CASE = (
    ROOT
    / "distillation_column_template_20stage_chemsep_warmer_feed_seed_preserved_mv18_20260524.xlsx"
)


@pytest.fixture(scope="module")
def source_column():
    return build_column_spec_from_case(load_case_from_excel(CASE))


@pytest.fixture(scope="module")
def reduced_case(source_column):
    provider = RelativeVolatilityThermoProviderV1(
        component_names_excel=source_column.components_excel,
        component_ids_dwsim=source_column.components_dwsim,
        alpha_light=1.6,
    )
    return build_reduced_feasibility_case(
        column=source_column,
        provider=provider,
    )


def test_reduction_selects_five_ordered_physical_roles(source_column):
    reduced, mapping = reduce_column_to_five_volumes(source_column)

    assert reduced.n_stages == 5
    assert tuple(reduced.stage_1based) == (1, 2, 3, 4, 5)
    assert mapping.role_by_reduced_stage == (
        "reflux_drum",
        "rectifying_tray",
        "feed_tray",
        "stripping_tray",
        "combined_reboiler_sump",
    )
    assert tuple(sorted(mapping.source_stage_1based)) == (
        mapping.source_stage_1based
    )
    assert reduced.streams["Feed"].stage_1based == (
        reduced.n_stages + 1
    ) // 2
    assert reduced.streams["Distillate"].stage_1based == reduced.stage_1based[0]
    assert reduced.streams["Bottom"].stage_1based == reduced.stage_1based[-1]

    source_indices = np.asarray(mapping.source_stage_1based) - 1
    assert np.array_equal(reduced.T_f, source_column.T_f[source_indices])
    assert np.array_equal(reduced.P_psia, source_column.P_psia[source_indices])
    assert np.array_equal(
        reduced.geometry.vapor_volume_ft3_per_stage,
        source_column.geometry.vapor_volume_ft3_per_stage[source_indices],
    )


def test_reduced_registry_is_square_and_structurally_full_rank(reduced_case):
    structure = reduced_case.structure

    assert structure.unknown_count == 71
    assert structure.residual_count == 71
    assert structure.structural_rank == 71
    assert structure.structural_nullity == 0
    assert structure.unmatched_unknowns == ()
    assert structure.unmatched_residuals == ()
    assert structure.pass_gate


def test_reduced_guess_uses_the_unmodified_direct_residual(reduced_case):
    guess = build_chemsep_guess(reduced_case.problem)
    evaluation = evaluate_direct_steady_state_residual(
        reduced_case.problem, guess
    )

    assert evaluation.raw.shape == (71,)
    assert np.all(np.isfinite(evaluation.raw))
    assert evaluation.conservation.component_pass
    assert evaluation.conservation.energy_pass
    assert evaluation.conservation.internal_energy_pairing_pass
    assert evaluation.safeguards_used == ()


def test_rank_deficient_surrogate_stops_before_solver_attempts(reduced_case):
    study = run_reduced_feasibility_study(
        reduced_case,
        settings=FixedSolverSettings(),
    )

    assert not study.numerical_gate_pass
    assert study.attempts == ()
    assert not study.accepted
    assert (
        study.classification
        == "reduced_feasibility_structural_or_numerical_gate_failed"
    )
    assert "do not start" in study.decision.lower()
