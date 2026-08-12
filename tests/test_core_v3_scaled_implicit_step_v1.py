import numpy as np

from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    dynamic_algebraic_coordinates,
    inventory_from_state,
)
from dynamic_distillation.core_v3.implicit_step_v1 import (
    component_rate_scales,
    evaluate_backward_euler_residual,
    governing_storage_vector,
    zero_rate_evaluation,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from test_core_v3_scaled_dynamic_dae_numerical_audit_v1 import _fixture


def test_dd172_scaled_backward_euler_mapping_uses_declared_topology():
    provider, spec, reference, state, contract = _fixture()
    inventory = inventory_from_state(state)
    algebraic = dynamic_algebraic_coordinates(spec, reference, state)
    audit = ProviderCallAudit()
    baseline = zero_rate_evaluation(
        contract,
        spec,
        reference,
        state,
        provider,
        audit,
        inventory_lbmol=inventory,
        algebraic_coordinates=algebraic,
        fixed_steady_scales=np.ones(56),
        state_id="scaled_step_baseline",
        evaluation_kind="residual",
    )
    rate_scales = component_rate_scales(contract, baseline)
    storage = governing_storage_vector(spec, baseline, inventory)
    point = np.concatenate((np.zeros(21), algebraic))
    evaluation = evaluate_backward_euler_residual(
        contract,
        spec,
        reference,
        state,
        provider,
        audit,
        previous_inventory_lbmol=inventory,
        previous_internal_energy_BTU=storage,
        rate_scales_lbmolph=rate_scales,
        solve_coordinates=point,
        step_seconds=1.0,
        fixed_steady_scales=np.ones(56),
        state_id="scaled_step",
        evaluation_kind="residual",
    )

    assert rate_scales.shape == (7, 3)
    assert storage.shape == (7,)
    assert evaluation.raw.shape == evaluation.scaled.shape == (54,)
    assert evaluation.endpoint_inventory_lbmol.shape == (7, 3)
    assert evaluation.energy_storage_rate_BTUph.shape == (7,)
    assert np.array_equal(evaluation.endpoint_inventory_lbmol, inventory)
    assert np.allclose(evaluation.component_rate_lbmolph, 0.0)
    assert np.allclose(evaluation.energy_storage_rate_BTUph, 0.0)
