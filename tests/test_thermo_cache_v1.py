# test_thermo_cache_v1.py

from dynamic_distillation.thermo_cache_v1 import build_thermo_cache, load_thermo_cache


def test_build_and_load_thermo_cache(tmp_path):
    out_path = tmp_path / "thermo_cache.json"
    build_thermo_cache(
        excel_path="distillation_column_template.xlsx",
        thermo_mode="stub",
        out_path=str(out_path),
    )

    data = load_thermo_cache(str(out_path))
    assert int(data["n_stages"]) > 0
    assert int(data["n_components"]) > 0
    assert data["K_tray"].shape[0] == int(data["n_stages"])
    assert data["HL_BTU_lbmol_tray"].shape[0] == int(data["n_stages"])
    assert data["HV_BTU_lbmol_tray"].shape[0] == int(data["n_stages"])
