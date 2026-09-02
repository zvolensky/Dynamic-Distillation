from __future__ import annotations

import numpy as np

from dynamic_distillation.core_v3.end_of_run_summary_v1 import (
    build_end_of_run_summary,
    format_end_of_run_summary,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_contract_v1 import (
    terminal_geometry_from_specs,
)


def test_end_of_run_summary_is_component_and_topology_ledger_driven():
    volumes = ("top", "tray_a", "feed", "tray_b", "bottom")
    components = ("A", "B")
    time = np.asarray([0.0, 60.0])
    liquid = np.full((2, 5, 2), 10.0)
    vapor = np.full((2, 5, 2), 0.5)
    temperature = np.tile(np.linspace(100.0, 140.0, 5), (2, 1))
    pressure = np.tile(np.linspace(15.0, 20.0, 5), (2, 1))
    liquid_flow = np.full((2, 3), 100.0)
    vapor_flow = np.full((2, 4), 120.0)
    geometry = terminal_geometry_from_specs(
        {
            "Top Drum Diameter (ft)": 4.0,
            "Top Drum Length (ft)": 10.0,
            "Bottom Sump Diameter (ft)": 4.0,
            "Bottom Sump Height (ft)": 10.0,
        }
    )

    summary = build_end_of_run_summary(
        component_names=components,
        volume_ids=volumes,
        node_types=("reflux_drum", "tray", "feed_tray", "tray", "reboiler_sump"),
        time_sec=time,
        liquid_component_inventory_lbmol=liquid,
        vapor_component_inventory_lbmol=vapor,
        temperature_F=temperature,
        pressure_psia=pressure,
        hydraulic_liquid_flow_lbmolph=liquid_flow,
        hydraulic_volume_ids=volumes[1:-1],
        vapor_flow_lbmolph=vapor_flow,
        vapor_links=(
            ("bottom", "tray_b", "v4"),
            ("tray_b", "feed", "v3"),
            ("feed", "tray_a", "v2"),
            ("tray_a", "top", "v1"),
        ),
        condenser_duty_BTUph=np.asarray([-1000.0, -1000.0]),
        reboiler_duty_BTUph=1100.0,
        reflux_lbmolph=80.0,
        distillate_lbmolph=40.0,
        bottoms_lbmolph=60.0,
        feed_component_lbmolph=(50.0, 50.0),
        final_liquid_density_lbmol_ft3=np.ones(5),
        final_liquid_enthalpy_BTU_lbmol=np.linspace(-100.0, -80.0, 5),
        final_vapor_enthalpy_BTU_lbmol=np.linspace(10.0, 30.0, 5),
        terminal_geometry=geometry,
    )

    assert summary["duties"] == {
        "condenser_BTUph": -1000.0,
        "reboiler_BTUph": 1100.0,
    }
    assert summary["products"]["distillate"]["mole_fraction"] == {
        "A": 0.5,
        "B": 0.5,
    }
    assert summary["steady_state"]["score"] == 0.0
    assert summary["steady_state"]["steady"]
    assert len(summary["profiles"]) == 5
    assert summary["profiles"][0]["liquid_flow_out_lbmolph"] == 80.0
    assert summary["profiles"][-1]["liquid_flow_out_lbmolph"] == 60.0
    rendered = format_end_of_run_summary(summary)
    assert "FINAL TRAY PROFILES" in rendered
    assert rendered.splitlines()[-1].startswith("5 | bottom | reboiler_sump")
