from __future__ import annotations

import numpy as np

from dynamic_distillation.thermo_relative_volatility_provider_v1 import RelativeVolatilityThermoProviderV1


def test_relative_volatility_provider_flash_uses_constant_alpha_and_enthalpy():
    provider = RelativeVolatilityThermoProviderV1(["N-butane", "n-Pentane"], alpha_light=1.6)

    fres = provider.flash_TP_full(200.0, 14.7, [0.5, 0.5])

    assert np.allclose(fres.x, [0.5, 0.5])
    assert np.allclose(fres.K, [1.6 / 1.3, 1.0 / 1.3])
    assert np.allclose(fres.y, [1.6 / 2.6, 1.0 / 2.6])
    assert fres.HL_BTU_lbmol > 0.0
    assert fres.HV_BTU_lbmol > fres.HL_BTU_lbmol
    assert fres.cpL_BTU_lbmolF is not None and fres.cpL_BTU_lbmolF > 0.0
    assert fres.cpV_BTU_lbmolF is not None and fres.cpV_BTU_lbmolF > 0.0


def test_relative_volatility_provider_exposes_energy_helpers():
    provider = RelativeVolatilityThermoProviderV1(["A", "B"], alpha_light=2.0)

    cpL, cpV = provider.cp_liq_vap_btu_per_lbmolF(190.0, 20.0, [0.25, 0.75])
    tbub = provider.bubble_point_temperature_F_psia(20.0, [0.25, 0.75])
    hL = provider.phase_enthalpy_BTU_lbmol("liquid", 190.0, 20.0, [0.25, 0.75])
    hV = provider.phase_enthalpy_BTU_lbmol("vapor", 190.0, 20.0, [0.25, 0.75])

    assert cpL > cpV > 0.0
    assert 180.0 < tbub < 230.0
    assert hV > hL
    assert provider.liquid_density_lbmol_ft3(190.0, 20.0, [0.25, 0.75]) == 1.0
    assert provider.component_mw_lbm_per_lbmol().shape == (2,)
