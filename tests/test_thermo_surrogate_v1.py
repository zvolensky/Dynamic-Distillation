"""
test_thermo_surrogate_v1.py

Dynamic Distillation - Tabular Surrogate Tests

PURPOSE
-------
Validate interpolation/blending behavior of `TabularThermoProviderV1` from
synthetic table documents.

SCOPE
-----
- anchor blending and bilinear interpolation consistency
- flash/property output shape and numeric expectations

KEY DEPENDENCIES
----------------
- thermo_surrogate_v1
- numpy/pytest/json fixtures
"""


from __future__ import annotations

import json

import numpy as np
import pytest

from dynamic_distillation.thermo_surrogate_v1 import TabularThermoProviderV1


def _build_table_doc() -> dict:
    T = [100.0, 200.0]
    P = [100.0, 200.0]

    def build_anchor(offset_k: float, offset_h: float, z_ref):
        K = np.zeros((2, 2, 2), dtype=float)
        HL = np.zeros((2, 2), dtype=float)
        HV = np.zeros((2, 2), dtype=float)
        Z = np.zeros((2, 2), dtype=float)
        rho = np.zeros((2, 2), dtype=float)

        for i, Tf in enumerate(T):
            t = (Tf - 100.0) / 100.0
            for j, Pp in enumerate(P):
                p = (Pp - 100.0) / 100.0
                K[i, j, 0] = 2.0 + t + 2.0 * p + offset_k
                K[i, j, 1] = 0.5 + 0.5 * t + p + 0.5 * offset_k
                HL[i, j] = 1000.0 + 10.0 * Tf + 2.0 * Pp + offset_h
                HV[i, j] = 2000.0 + 20.0 * Tf + 3.0 * Pp + offset_h
                Z[i, j] = 1.0 + 0.1 * t + 0.05 * p
                rho[i, j] = 40.0 - 0.01 * Tf + 0.02 * Pp

        return {
            "z_ref": z_ref,
            "K": K.tolist(),
            "HL_BTU_lbmol": HL.tolist(),
            "HV_BTU_lbmol": HV.tolist(),
            "Z": Z.tolist(),
            "rhoL_lbmol_ft3": rho.tolist(),
        }

    a1 = build_anchor(offset_k=0.0, offset_h=0.0, z_ref=[0.9, 0.1])
    a2 = build_anchor(offset_k=1.0, offset_h=500.0, z_ref=[0.1, 0.9])

    return {
        "format_version": 1,
        "components_excel": ["A", "B"],
        "components_dwsim": ["A", "B"],
        "mw_lbm_per_lbmol": [10.0, 20.0],
        "T_grid_F": T,
        "P_grid_psia": P,
        "anchors": [
            {"name": "a1", **a1},
            {"name": "a2", **a2},
        ],
    }


def test_tabular_provider_interpolates_and_matches_expected_values(tmp_path):
    p = tmp_path / "table.json"
    with p.open("w", encoding="utf-8") as f:
        json.dump(_build_table_doc(), f, indent=2, ensure_ascii=True)

    prov = TabularThermoProviderV1.from_json(
        str(p),
        expected_component_names_excel=["A", "B"],
        expected_component_ids_dwsim=["A", "B"],
        cp_dt_F=1.0,
        n_anchor_blend=1,
    )

    res = prov.flash_TP_full(150.0, 150.0, [0.85, 0.15])

    # With n_anchor_blend=1 this should use anchor 1 only.
    # Midpoint interpolation with anchor-1 formulas:
    # K1=2 + 0.5 + 1 = 3.5
    # K2=0.5 + 0.25 + 0.5 = 1.25
    assert np.allclose(res.K, np.array([3.5, 1.25]), atol=1e-12)

    # HL=1000 + 10*T + 2*P; HV=2000 + 20*T + 3*P
    assert abs(res.HL_BTU_lbmol - 2800.0) < 1e-12
    assert abs(res.HV_BTU_lbmol - 5450.0) < 1e-12
    assert abs(float(res.Z) - 1.075) < 1e-12

    # Compositions are normalized and physically bounded.
    assert abs(float(np.sum(res.x)) - 1.0) < 1e-12
    assert abs(float(np.sum(res.y)) - 1.0) < 1e-12
    assert np.all(res.x >= 0.0)
    assert np.all(res.y >= 0.0)

    cpL, cpV = prov.cp_liq_vap_btu_per_lbmolF(150.0, 150.0, [0.85, 0.15])
    assert abs(float(cpL) - 10.0) < 1e-12
    assert abs(float(cpV) - 20.0) < 1e-12

    rho = prov.liquid_density_lbmol_ft3(150.0, 150.0, [0.85, 0.15])
    assert abs(float(rho) - 41.5) < 1e-12

    mw = prov.component_mw_lbm_per_lbmol()
    assert mw is not None
    assert np.allclose(mw, np.array([10.0, 20.0]))


def test_tabular_provider_anchor_blending_interpolates_across_composition(tmp_path):
    p = tmp_path / "table.json"
    with p.open("w", encoding="utf-8") as f:
        json.dump(_build_table_doc(), f, indent=2, ensure_ascii=True)

    prov = TabularThermoProviderV1.from_json(str(p), n_anchor_blend=2)

    # Midpoint composition has equal L1 distance to both anchors => 50/50 blend.
    res = prov.flash_TP_full(150.0, 150.0, [0.5, 0.5])

    # At (150,150):
    # anchor1: K=[3.5, 1.25], HL=2800, HV=5450
    # anchor2: K=[4.5, 1.75], HL=3300, HV=5950
    # K uses ln-space blending => geometric mean for equal weights.
    assert abs(res.HL_BTU_lbmol - 3050.0) < 1e-12
    assert abs(res.HV_BTU_lbmol - 5700.0) < 1e-12
    assert abs(res.K[0] - np.sqrt(3.5 * 4.5)) < 1e-12
    assert abs(res.K[1] - np.sqrt(1.25 * 1.75)) < 1e-12


def test_tabular_provider_component_mismatch_raises(tmp_path):
    p = tmp_path / "table.json"
    with p.open("w", encoding="utf-8") as f:
        json.dump(_build_table_doc(), f, indent=2, ensure_ascii=True)

    with pytest.raises(ValueError, match="components_excel mismatch"):
        TabularThermoProviderV1.from_json(str(p), expected_component_names_excel=["X", "Y"])


def test_tabular_provider_can_blend_more_than_two_anchors(tmp_path):
    doc = _build_table_doc()
    third = {
        "name": "a3",
        "z_ref": [0.5, 0.5],
        "K": (np.asarray(doc["anchors"][0]["K"], dtype=float) + 2.0).tolist(),
        "HL_BTU_lbmol": (np.asarray(doc["anchors"][0]["HL_BTU_lbmol"], dtype=float) + 1000.0).tolist(),
        "HV_BTU_lbmol": (np.asarray(doc["anchors"][0]["HV_BTU_lbmol"], dtype=float) + 1000.0).tolist(),
        "Z": doc["anchors"][0]["Z"],
        "rhoL_lbmol_ft3": doc["anchors"][0]["rhoL_lbmol_ft3"],
    }
    doc["anchors"].append(third)

    p = tmp_path / "table3.json"
    with p.open("w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=True)

    prov = TabularThermoProviderV1.from_json(str(p), n_anchor_blend=3)
    res = prov.flash_TP_full(150.0, 150.0, [0.5, 0.5])

    # The midpoint anchor should pull the blend away from the original 2-anchor midpoint.
    assert res.HL_BTU_lbmol > 3050.0


def test_tabular_provider_can_overlay_upper_section_flash_provider(tmp_path):
    p = tmp_path / "table.json"
    with p.open("w", encoding="utf-8") as f:
        json.dump(_build_table_doc(), f, indent=2, ensure_ascii=True)

    base = TabularThermoProviderV1.from_json(str(p), n_anchor_blend=1)
    upper = TabularThermoProviderV1.from_json(str(p), n_anchor_blend=1)
    base.attach_upper_section_flash_provider(upper, max_stage_index0=4)

    assert base.upper_section_flash_provider is upper
    assert base.upper_section_max_stage_index0 == 4

    res_top = base.flash_TP_full_stage_F_psia(0, 150.0, 150.0, [0.85, 0.15])
    res_bot = base.flash_TP_full_stage_F_psia(10, 150.0, 150.0, [0.85, 0.15])

    assert np.allclose(res_top.K, res_bot.K)
    assert abs(res_top.HL_BTU_lbmol - 2800.0) < 1e-12
