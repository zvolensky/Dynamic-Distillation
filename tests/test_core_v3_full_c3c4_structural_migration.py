import pytest

from tools.audit_core_v3_full_c3c4_structural_migration import run


@pytest.fixture(scope="module")
def result():
    return run()


def test_dd221_full_c3c4_mapping_and_structural_layers_pass(result):

    assert result["source"]["stage_count"] == 20
    assert result["source"]["feed_stage_1based"] == 12
    assert result["mapping"]["rectifying_volume_count"] == 10
    assert result["mapping"]["stripping_volume_count"] == 7
    assert result["dimensions"] == {
        "provider_governed_registry": 160,
        "dynamic_dae": 158,
        "terminal_controlled_dae": 162,
        "controlled_bdf2": 162,
        "bdf2_history_values": 164,
    }
    assert all(result["gates"].values())
    assert result["pass_gate"]


def test_dd221_maps_every_source_stage_without_named_interior_equations(result):
    mapping = result["mapping"]["volume_to_source_stage_1based"]

    assert list(mapping.values()) == list(range(1, 21))
    assert mapping["reflux_drum"] == 1
    assert mapping["rectifying_volume_10"] == 11
    assert mapping["feed_tray"] == 12
    assert mapping["stripping_volume_7"] == 19
    assert mapping["combined_reboiler_sump"] == 20
    assert result["gates"]["interior_ownership_is_generic"]


def test_dd221_performs_no_live_or_numerical_work(result):
    assert not any(result["execution_prohibitions"].values())
    assert not result["source"]["seed_is_accepted_root"]
