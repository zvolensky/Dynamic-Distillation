"""
test_column_spec_builder_v1.py

Dynamic Distillation - ColumnSpec Builder Tests

PURPOSE
-------
Validate that Excel case inputs are transformed into a consistent
`ColumnSpec`, including dimensions, initialization arrays, and optional
geometry/simulation metadata.

SCOPE
-----
- smoke validation against template workbook
- expected defaults and optional geometry normalization checks

KEY DEPENDENCIES
----------------
- excel_case_loader_v1
- column_spec_builder_v1
"""


from dynamic_distillation.excel_case_loader_v1 import CaseData, load_case_from_excel
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
import numpy as np
import pandas as pd


def test_build_column_spec_from_template():
    case = load_case_from_excel("distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx")
    spec = build_column_spec_from_case(case)

    assert spec.n_stages == 20
    assert spec.n_components == 3
    assert spec.y0.shape == (20, 3)
    assert spec.x0.shape == (20, 3)

    # Module 8B: tau loaded (or defaults)
    assert hasattr(spec, "tau_eq_sec")
    assert spec.tau_eq_sec > 0.0
    assert float(spec.tau_eq_sec) == 4.0

    # Geometry expansion (optional in the template)
    if spec.geometry is not None:
        assert spec.geometry.vapor_volume_ft3_per_stage.shape == (20,)
        # Stage 1 (condenser) is not in the geometry table; we back-fill from stage 2.
        assert spec.geometry.vapor_volume_ft3_per_stage[0] == spec.geometry.vapor_volume_ft3_per_stage[1]
        # Percent-style void fraction in later section should have been normalized to 0.75
        assert abs(float(spec.geometry.gas_void_frac_per_stage[15]) - 0.75) < 1e-12


def test_build_column_spec_carries_restart_energy_and_controller_state():
    case = CaseData(
        excel_path="<unit-test>",
        components=["A", "B"],
        component_ids_dwsim=["A", "B"],
        specs={
            "Number of Stages": 2,
            "Number of Components": 2,
            "Simulation Length (min)": 1.0,
            "Timestep (sec)": 1.0,
            "Log Frequency (timesteps)": 1,
        },
        initial_conditions=pd.DataFrame(
            {
                "Stage": [1.0, 2.0],
                "Temperature (F)": [100.0, 120.0],
                "Pressure (psia)": [200.0, 210.0],
                "Vapor Flow (lbmol/h)": [10.0, 11.0],
                "Liquid Flow (lbmol/h)": [20.0, 21.0],
                "Liquid Holdup (lbmol)": [5.0, 6.0],
                "Vapor Composition Component 1": [0.6, 0.5],
                "Vapor Composition Component 2": [0.4, 0.5],
                "Liquid Composition Component 1": [0.3, 0.4],
                "Liquid Composition Component 2": [0.7, 0.6],
            }
        ),
        boundary_state={},
        energy_state={
            "tray_EL_BTU": [101.0, 102.0],
            "tray_EV_BTU": [201.0, 202.0],
        },
        controller_state={
            "top_level_integ": 1.5,
            "top_pressure_integ": -2.5,
        },
        memory_state={
            "P_tray_prev_psia": [200.0, 210.0],
            "T_tray_prev_F": [100.0, 120.0],
        },
        streams={},
    )

    spec = build_column_spec_from_case(case)
    assert np.allclose(spec.tray_EL0_BTU, np.array([101.0, 102.0], dtype=float))
    assert np.allclose(spec.tray_EV0_BTU, np.array([201.0, 202.0], dtype=float))
    assert spec.controller_state["top_level_integ"] == 1.5
    assert spec.controller_state["top_pressure_integ"] == -2.5
    assert np.allclose(spec.memory_state["P_tray_prev_psia"], np.array([200.0, 210.0], dtype=float))
    assert np.allclose(spec.memory_state["T_tray_prev_F"], np.array([100.0, 120.0], dtype=float))
