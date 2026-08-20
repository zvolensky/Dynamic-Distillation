from __future__ import annotations

import numpy as np
import pytest

from dynamic_distillation.core_v3.vapor_holdup_dynamic_pressure_implicit_residual_v1 import (
    evaluate_vapor_holdup_dynamic_pressure_implicit_residual,
)


@pytest.mark.parametrize("duty", [0.0, 1.0, np.nan])
def test_dynamic_pressure_residual_rejects_invalid_specified_duty(duty):
    with pytest.raises(ValueError, match="condenser duty"):
        evaluate_vapor_holdup_dynamic_pressure_implicit_residual(
            contract=None,
            geometry=(),
            reference=None,
            balance_inputs=None,
            hydraulic_geometry=(),
            numerical=None,
            provider=None,
            call_audit=None,
            coordinates=(),
            controller_memory_previous=(),
            specified_condenser_duty_BTUph=duty,
            state_id="test",
            evaluation_kind="residual",
        )
