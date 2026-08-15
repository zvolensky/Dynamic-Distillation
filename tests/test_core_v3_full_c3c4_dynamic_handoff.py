from tools.audit_core_v3_full_c3c4_dynamic_handoff import build_report


def test_dd232_maps_the_accepted_root_into_every_dynamic_layer():
    report = build_report()

    assert report["dimensions"] == {
        "stationary_coordinates": 160,
        "component_inventory_states": 60,
        "dynamic_algebraic_coordinates": 98,
        "open_loop_dynamic_solve": 158,
        "controller_memory_states": 2,
        "controlled_dynamic_solve": 162,
        "bdf2_component_history_values": 120,
        "bdf2_energy_history_values": 40,
        "bdf2_controller_history_values": 4,
        "bdf2_total_history_values": 164,
    }
    assert all(report["gates"].values())
    assert report["pass_gate"]


def test_dd232_repeats_inventory_history_and_starts_controllers_bumpless():
    report = build_report()
    history = report["bdf2_history"]
    inventory = [value for row in report["component_inventory_lbmol"] for value in row]

    assert history["component_values_lbmol"][:60] == inventory
    assert history["component_values_lbmol"][60:] == inventory
    assert history["controller_values"] == [0.0, 0.0, 0.0, 0.0]
    assert report["controller_memory"] == [0.0, 0.0]
    assert report["controlled_root_solve_coordinates"][:62] == [0.0] * 62
    assert report["controlled_root_solve_coordinates"][-2:] == [0.0, 0.0]


def test_dd232_is_property_free_and_authorizes_only_a_live_audit():
    report = build_report()

    assert not any(report["scope"].values())
    assert report["decision"] == "authorize_one_separately_frozen_live_zero_motion_audit"
    assert "aligned_pr" in report["provider_routing"]["declared_liquid_density"]
