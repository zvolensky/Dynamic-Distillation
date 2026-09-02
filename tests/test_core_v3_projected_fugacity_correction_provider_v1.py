from __future__ import annotations

from contextlib import contextmanager

import numpy as np
import pytest

from dynamic_distillation.core_v3.projected_fugacity_correction_provider_v1 import (
    ProjectedFugacityCorrectionProviderV1,
)


class _BaseProvider:
    component_names_excel = ["A", "B"]
    component_ids_dwsim = ["a", "b"]

    def __init__(self) -> None:
        self.memoization = None

    def phase_fugacity_coefficients(self, phase, temperature, pressure, composition):
        return np.asarray((2.0, 3.0), dtype=float)

    def phase_enthalpy_BTU_lbmol(self, phase, temperature, pressure, composition):
        return 123.0

    @contextmanager
    def thermo_call_category(self, category):
        yield

    def set_exact_state_memoization(self, enabled, *, clear=True):
        self.memoization = (enabled, clear)


def test_projected_correction_changes_only_configured_phase() -> None:
    base = _BaseProvider()
    provider = ProjectedFugacityCorrectionProviderV1(
        base_provider=base,
        projection=(1.0, 0.0),
        projection_limits=(0.0, 1.0),
        liquid_log_coefficients=((np.log(2.0), 0.0), (0.0, np.log(3.0))),
    )

    liquid = provider.phase_fugacity_coefficients("liquid", 100.0, 14.7, (1.0, 0.0))
    vapor = provider.phase_fugacity_coefficients("vapor", 100.0, 14.7, (1.0, 0.0))

    assert liquid == pytest.approx((4.0, 9.0))
    assert vapor == pytest.approx((2.0, 3.0))
    assert provider.phase_enthalpy_BTU_lbmol("liquid", 100.0, 14.7, (0.5, 0.5)) == 123.0


def test_projected_correction_validates_dimensions_and_forwards_memoization() -> None:
    base = _BaseProvider()
    with pytest.raises(ValueError, match="rows"):
        ProjectedFugacityCorrectionProviderV1(
            base_provider=base,
            projection=(1.0, 0.0),
            projection_limits=(0.0, 1.0),
            liquid_log_coefficients=((0.0,),),
        )

    provider = ProjectedFugacityCorrectionProviderV1(
        base_provider=base,
        projection=(1.0, 0.0),
        projection_limits=(0.0, 1.0),
        liquid_log_coefficients=((0.0,), (0.0,)),
    )
    provider.set_exact_state_memoization(True, clear=False)
    assert base.memoization == (True, False)
