from pathlib import Path

import numpy as np
import pytest

from dynamic_distillation.column_spec_builder_v1 import (
    build_column_spec_from_case,
)
from dynamic_distillation.direct_steady_state_registry_v1 import (
    build_direct_steady_state_registry,
    combine_reboiler_and_sump_registry,
    structural_pattern,
)
from dynamic_distillation.direct_steady_state_residual_v1 import (
    DirectResidualEvaluationError,
    audit_numerical_jacobian,
    build_bounded_perturbed_guess,
    build_chemsep_guess,
    build_direct_steady_state_problem,
    evaluate_direct_steady_state_residual,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_relative_volatility_provider_v1 import (
    RelativeVolatilityThermoProviderV1,
)


ROOT = Path(__file__).resolve().parents[1]
CASE = (
    ROOT
    / "distillation_column_template_20stage_chemsep_warmer_feed_seed_preserved_mv18_20260524.xlsx"
)


@pytest.fixture(scope="module")
def direct_problem():
    column = build_column_spec_from_case(load_case_from_excel(CASE))
    registry = combine_reboiler_and_sump_registry(
        build_direct_steady_state_registry(
            component_names=column.components_excel,
            active_stage_ids=tuple(range(2, 20)),
        )
    )
    provider = RelativeVolatilityThermoProviderV1(
        component_names_excel=column.components_excel,
        component_ids_dwsim=column.components_dwsim,
        alpha_light=1.6,
    )
    return build_direct_steady_state_problem(
        registry=registry,
        column=column,
        provider=provider,
    )


def test_dd072_populates_every_residual_and_telescopes(direct_problem):
    guess = build_chemsep_guess(direct_problem)
    evaluation = evaluate_direct_steady_state_residual(
        direct_problem, guess
    )

    assert evaluation.raw.shape == (281,)
    assert evaluation.scaled.shape == (281,)
    assert np.all(np.isfinite(evaluation.raw))
    assert len(evaluation.rows) == 281
    assert evaluation.safeguards_used == ()
    assert evaluation.conservation.component_pass is True
    assert evaluation.conservation.energy_pass is True
    assert evaluation.conservation.internal_energy_pairing_pass is True


def test_dd072_bounded_perturbation_stays_evaluable(direct_problem):
    guess = build_chemsep_guess(direct_problem)
    perturbed = build_bounded_perturbed_guess(direct_problem, guess)
    evaluation = evaluate_direct_steady_state_residual(
        direct_problem, perturbed
    )

    assert not np.array_equal(guess, perturbed)
    assert evaluation.conservation.component_pass is True
    assert evaluation.conservation.energy_pass is True


def test_dd072_invalid_reduced_composition_fails_without_projection(
    direct_problem,
):
    guess = build_chemsep_guess(direct_problem)
    names = [
        entry.name for entry in direct_problem.registry.unknowns
    ]
    invalid = guess.copy()
    invalid[names.index("x[tray_2,n-Propane]")] = 0.8
    invalid[names.index("x[tray_2,n-Butane]")] = 0.3

    with pytest.raises(
        DirectResidualEvaluationError,
        match=r"tray_2 liquid: composition is outside the open simplex",
    ):
        evaluate_direct_steady_state_residual(direct_problem, invalid)


def test_dd072_colored_jacobian_matches_uncolored_registered_entries(
    direct_problem,
):
    guess = build_chemsep_guess(direct_problem)
    colored = audit_numerical_jacobian(
        direct_problem, guess, mode="colored"
    )
    uncolored = audit_numerical_jacobian(
        direct_problem, guess, mode="uncolored"
    )
    expected = structural_pattern(direct_problem.registry).toarray().astype(
        bool
    )

    assert colored.matrix.shape == (281, 281)
    assert np.allclose(
        colored.matrix[expected],
        uncolored.matrix[expected],
        rtol=0.0,
        atol=0.0,
    )
    assert uncolored.unexpected_nonzeros == ()
