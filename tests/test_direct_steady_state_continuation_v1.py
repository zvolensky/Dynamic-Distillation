from pathlib import Path

import numpy as np
import pytest

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.direct_steady_state_continuation_v1 import (
    AdaptiveLambdaController,
    SmoothPhysicalCoordinates,
    build_continuation_stages,
    evaluate_stage_homotopy,
    finite_difference_stage_jacobian,
    stage_structural_pattern,
)
from dynamic_distillation.direct_steady_state_registry_v1 import (
    build_direct_steady_state_registry,
    combine_reboiler_and_sump_registry,
)
from dynamic_distillation.direct_steady_state_residual_v1 import (
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
def continuation_problem():
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


def _coordinates(problem):
    guess = build_chemsep_guess(problem)
    evaluation = evaluate_direct_steady_state_residual(problem, guess)
    return (
        guess,
        evaluation,
        SmoothPhysicalCoordinates(problem, guess, evaluation.variable_scales),
    )


def test_dd073_stage_counts_are_the_five_square_systems(continuation_problem):
    stages = build_continuation_stages(continuation_problem)

    assert [stage.size for stage in stages] == [160, 240, 258, 277, 281]
    assert all(
        len(stage.unknown_indices) == len(stage.residual_indices)
        for stage in stages
    )
    assert all(
        len(stage.new_unknown_indices) == len(stage.new_residual_indices)
        for stage in stages
    )


def test_dd073_stage_one_anchor_orientation_matches_closure_variable_type(
    continuation_problem,
):
    stage = build_continuation_stages(continuation_problem)[0]
    registry = continuation_problem.registry
    signs = dict(stage.anchor_sign_by_residual)

    for residual_index, unknown_index in stage.anchor_unknown_by_residual:
        residual = registry.residuals[residual_index]
        unknown = registry.unknowns[unknown_index]
        if residual.block in {"local_energy_closure", "local_volume_closure"}:
            assert signs[residual_index] == -1.0
        elif residual.block == "local_component_closure":
            expected = 1.0 if unknown.name.startswith("x[") else -1.0
            assert signs[residual_index] == expected
        else:
            assert signs[residual_index] == 1.0


def test_dd073_transform_round_trip_and_physical_domains(continuation_problem):
    guess, _, coordinates = _coordinates(continuation_problem)
    stage = build_continuation_stages(continuation_problem)[-1]
    encoded = coordinates.encode(guess, stage.unknown_indices)
    decoded = coordinates.decode(encoded, stage.unknown_indices)

    assert np.allclose(decoded, guess, rtol=1.0e-13, atol=1.0e-13)
    assert not coordinates.saturated(encoded, stage.unknown_indices)
    for node in (
        "reflux_drum",
        *(f"tray_{stage_id}" for stage_id in range(2, 20)),
        "partial_reboiler",
    ):
        for phase in ("x", "y"):
            independent = np.asarray(
                [
                    decoded[
                        next(
                            index
                            for index, entry in enumerate(
                                continuation_problem.registry.unknowns
                            )
                            if entry.name == f"{phase}[{node},{component}]"
                        )
                    ]
                    for component in continuation_problem.registry.component_names[:-1]
                ]
            )
            full = np.append(independent, 1.0 - np.sum(independent))
            assert np.all(full > 0.0)
            assert np.sum(full) == pytest.approx(1.0)

    for index, entry in enumerate(continuation_problem.registry.unknowns):
        if not entry.name.startswith(("T[", "U[", "x[", "y[")):
            assert decoded[index] > 0.0


def test_dd073_homotopy_endpoint_identities(continuation_problem):
    guess, evaluation, coordinates = _coordinates(continuation_problem)
    stage = build_continuation_stages(continuation_problem)[0]
    encoded = coordinates.encode(guess, stage.unknown_indices)

    at_zero = evaluate_stage_homotopy(
        continuation_problem,
        stage,
        coordinates,
        encoded,
        0.0,
        evaluation.residual_scales,
    )
    at_one = evaluate_stage_homotopy(
        continuation_problem,
        stage,
        coordinates,
        encoded,
        1.0,
        evaluation.residual_scales,
    )

    assert np.array_equal(at_zero.vector, np.zeros(stage.size))
    assert np.array_equal(
        at_one.vector,
        evaluation.raw[list(stage.residual_indices)]
        / evaluation.residual_scales[list(stage.residual_indices)],
    )
    assert at_one.physical.conservation.component_pass
    assert at_one.physical.conservation.energy_pass


def test_dd073_final_lambda_physical_residual_is_dd072_residual(
    continuation_problem,
):
    guess, evaluation, coordinates = _coordinates(continuation_problem)
    stage = build_continuation_stages(continuation_problem)[-1]
    encoded = coordinates.encode(guess, stage.unknown_indices)

    endpoint = evaluate_stage_homotopy(
        continuation_problem,
        stage,
        coordinates,
        encoded,
        1.0,
        evaluation.residual_scales,
    )

    assert np.array_equal(endpoint.physical.raw, evaluation.raw)
    assert np.array_equal(
        endpoint.vector, evaluation.raw / evaluation.residual_scales
    )


def test_dd073_colored_and_uncolored_transformed_jacobians_match(
    continuation_problem,
):
    guess, evaluation, coordinates = _coordinates(continuation_problem)
    stage = build_continuation_stages(continuation_problem)[0]
    encoded = coordinates.encode(guess, stage.unknown_indices)
    pattern = stage_structural_pattern(continuation_problem, stage)

    def residual(value):
        return evaluate_stage_homotopy(
            continuation_problem,
            stage,
            coordinates,
            value,
            0.35,
            evaluation.residual_scales,
        ).vector

    colored = finite_difference_stage_jacobian(
        residual, encoded, pattern, mode="colored"
    ).toarray()
    uncolored = finite_difference_stage_jacobian(
        residual, encoded, pattern, mode="uncolored"
    ).toarray()

    assert np.allclose(colored, uncolored, rtol=0.0, atol=0.0)


def test_dd073_adaptive_controller_growth_reduction_and_stop():
    controller = AdaptiveLambdaController()
    assert controller.target(0.0) == pytest.approx(0.10)

    controller.accept(nfev=4)
    assert controller.delta == pytest.approx(0.15)
    assert controller.reject()
    assert controller.delta == pytest.approx(0.075)

    while controller.reject():
        pass
    assert controller.delta == controller.minimum_delta
    assert controller.consecutive_reductions <= (
        controller.maximum_consecutive_reductions
    )
