"""
test_thermo_table_pool_v1.py

Dynamic Distillation - Parallel Tabular Provider Tests

PURPOSE
-------
Validate that `ParallelTabularThermoProviderV1` batch flash results match
single-provider reference results for deterministic table fixtures.

SCOPE
-----
- process-pool batch execution result consistency
- close/lifecycle behavior in test context

KEY DEPENDENCIES
----------------
- thermo_table_pool_v1 and thermo_surrogate_v1
- numpy/json fixtures
"""


from __future__ import annotations

import json

import numpy as np

from dynamic_distillation.thermo_surrogate_v1 import TabularThermoProviderV1
from dynamic_distillation.thermo_table_pool_v1 import ParallelTabularThermoProviderV1


def _build_table_doc() -> dict:
    T = [100.0, 200.0]
    P = [100.0, 200.0]

    def build_anchor(offset_k: float, offset_h: float, z_ref):
        K = np.zeros((2, 2, 2), dtype=float)
        HL = np.zeros((2, 2), dtype=float)
        HV = np.zeros((2, 2), dtype=float)
        Z = np.zeros((2, 2), dtype=float)

        for i, Tf in enumerate(T):
            t = (Tf - 100.0) / 100.0
            for j, Pp in enumerate(P):
                p = (Pp - 100.0) / 100.0
                K[i, j, 0] = 2.0 + t + 2.0 * p + offset_k
                K[i, j, 1] = 0.5 + 0.5 * t + p + 0.5 * offset_k
                HL[i, j] = 1000.0 + 10.0 * Tf + 2.0 * Pp + offset_h
                HV[i, j] = 2000.0 + 20.0 * Tf + 3.0 * Pp + offset_h
                Z[i, j] = 1.0 + 0.1 * t + 0.05 * p

        return {
            "z_ref": z_ref,
            "K": K.tolist(),
            "HL_BTU_lbmol": HL.tolist(),
            "HV_BTU_lbmol": HV.tolist(),
            "Z": Z.tolist(),
        }

    a1 = build_anchor(offset_k=0.0, offset_h=0.0, z_ref=[0.9, 0.1])
    a2 = build_anchor(offset_k=1.0, offset_h=500.0, z_ref=[0.1, 0.9])

    return {
        "format_version": 1,
        "components_excel": ["A", "B"],
        "components_dwsim": ["A", "B"],
        "T_grid_F": T,
        "P_grid_psia": P,
        "anchors": [
            {"name": "a1", **a1},
            {"name": "a2", **a2},
        ],
    }


def test_parallel_tabular_provider_batch_matches_scalar_reference(tmp_path):
    p = tmp_path / "table.json"
    with p.open("w", encoding="utf-8") as f:
        json.dump(_build_table_doc(), f, indent=2, ensure_ascii=True)

    ref = TabularThermoProviderV1.from_json(
        str(p),
        expected_component_names_excel=["A", "B"],
        expected_component_ids_dwsim=["A", "B"],
        n_anchor_blend=2,
    )
    pool = ParallelTabularThermoProviderV1(
        table_path=str(p),
        expected_component_names_excel=["A", "B"],
        expected_component_ids_dwsim=["A", "B"],
        n_anchor_blend=2,
        max_workers=2,
        chunk_size=2,
    )
    try:
        T = [120.0, 150.0, 190.0, 175.0]
        P = [110.0, 150.0, 180.0, 130.0]
        Z = [
            [0.90, 0.10],
            [0.50, 0.50],
            [0.20, 0.80],
            [0.65, 0.35],
        ]

        got = pool.flash_TP_full_batch(T, P, Z)
        exp = [ref.flash_TP_full(t, p_, z) for t, p_, z in zip(T, P, Z)]

        assert len(got) == len(exp)
        for g, e in zip(got, exp):
            assert np.allclose(g.K, e.K, atol=1e-12)
            assert abs(float(g.HL_BTU_lbmol) - float(e.HL_BTU_lbmol)) < 1e-12
            assert abs(float(g.HV_BTU_lbmol) - float(e.HV_BTU_lbmol)) < 1e-12
            if e.Z is None:
                assert g.Z is None
            else:
                assert g.Z is not None
                assert abs(float(g.Z) - float(e.Z)) < 1e-12
    finally:
        pool.close()
