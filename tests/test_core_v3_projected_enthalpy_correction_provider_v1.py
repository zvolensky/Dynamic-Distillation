from __future__ import annotations

import numpy as np
import pytest

from dynamic_distillation.core_v3.projected_enthalpy_correction_provider_v1 import (
    ProjectedEnthalpyCorrectionProviderV1,
)


class _BaseProvider:
    component_names_excel = ["A", "B"]
    component_ids_dwsim = ["a", "b"]

    def phase_enthalpy_BTU_lbmol(self, phase, temperature, pressure, composition):
        return 100.0 if phase == "liquid" else 200.0

    def phase_fugacity_coefficients(self, phase, temperature, pressure, composition):
        return np.asarray((2.0, 3.0))


def test_projected_enthalpy_correction_is_phase_specific() -> None:
    provider = ProjectedEnthalpyCorrectionProviderV1(
        base_provider=_BaseProvider(),
        projection=(1.0, 0.0),
        projection_limits=(0.0, 1.0),
        liquid_correction_coefficients_BTU_lbmol=((10.0, 20.0),),
        vapor_correction_coefficients_BTU_lbmol=((-30.0, 40.0),),
    )
    assert provider.phase_enthalpy_BTU_lbmol(
        "liquid", 100.0, 14.7, (1.0, 0.0)
    ) == pytest.approx(130.0)
    assert provider.phase_enthalpy_BTU_lbmol(
        "vapor", 100.0, 14.7, (0.0, 1.0)
    ) == pytest.approx(130.0)
    assert provider.phase_fugacity_coefficients(
        "liquid", 100.0, 14.7, (0.5, 0.5)
    ) == pytest.approx((2.0, 3.0))
