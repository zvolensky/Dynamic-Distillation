from __future__ import annotations

from types import SimpleNamespace

import pytest

from dynamic_distillation.thermo_backend_factory_v1 import (
    build_equilibrium_relaxation_pr_provider,
    build_primary_thermo_backend,
)


def _fake_col(*, n_components: int = 2):
    return SimpleNamespace(
        components_excel=["A", "B"][:n_components],
        components_dwsim=["A", "B"][:n_components],
        n_components=n_components,
    )


def test_build_primary_stub_backend_exposes_expected_methods():
    cfg = SimpleNamespace(thermo_mode="stub", dwsim_property_package="pr")
    build = build_primary_thermo_backend(cfg=cfg, col=_fake_col(), emit_progress=lambda _msg: None)

    assert build.thermo_mode == "stub"
    assert build.dwsim_property_package is None
    assert callable(getattr(build.provider, "flash_TP_full_F_psia", None))
    assert callable(getattr(build.provider, "cp_liq_vap_btu_per_lbmolF", None))
    assert build.capabilities.supports_direct_cp is True
    assert build.capabilities.supports_density is True


def test_build_primary_relative_volatility_backend_exposes_energy_methods():
    cfg = SimpleNamespace(thermo_mode="relative-volatility", dwsim_property_package="pr")
    col = _fake_col()
    col.specs_raw = {"Relative Volatility": 1.7}
    build = build_primary_thermo_backend(cfg=cfg, col=col, emit_progress=lambda _msg: None)

    assert build.thermo_mode == "relative-volatility"
    assert build.dwsim_property_package is None
    assert callable(getattr(build.provider, "flash_TP_full_F_psia", None))
    assert build.capabilities.supports_batch_tp_flash is True
    assert build.capabilities.supports_phase_enthalpy is True
    assert build.capabilities.supports_bubble_point is True
    assert build.provider.relative_volatility.tolist() == [1.7, 1.0]


def test_build_primary_dwsim_backend_resolves_package_alias(monkeypatch):
    import dynamic_distillation.thermo_provider_v1 as thermo_provider_v1

    calls = []

    class _FakeProvider:
        def __init__(self, *args, **kwargs):
            calls.append(dict(kwargs))

    monkeypatch.setattr(thermo_provider_v1, "ThermoProviderV1", _FakeProvider)

    cfg = SimpleNamespace(thermo_mode="dwsim-unifac", dwsim_property_package="pr")
    build = build_primary_thermo_backend(cfg=cfg, col=_fake_col(), emit_progress=lambda _msg: None)

    assert build.thermo_mode == "dwsim-unifac"
    assert build.dwsim_property_package == "unifac"
    assert calls[0]["property_package"] == "unifac"


def test_build_primary_clapeyron_backend_uses_configured_model(monkeypatch):
    import dynamic_distillation.thermo_clapeyron_provider_v1 as thermo_clapeyron_provider_v1

    calls = []

    class _FakeProvider:
        def __init__(self, *args, **kwargs):
            calls.append(dict(kwargs))

    monkeypatch.setattr(thermo_clapeyron_provider_v1, "ThermoClapeyronProviderV1", _FakeProvider)

    cfg = SimpleNamespace(
        thermo_mode="clapeyron",
        dwsim_property_package="pr",
        clapeyron_model="PCSAFT",
        clapeyron_ideal_model="WalkerIdeal",
    )
    build = build_primary_thermo_backend(cfg=cfg, col=_fake_col(), emit_progress=lambda _msg: None)

    assert build.thermo_mode == "clapeyron"
    assert build.dwsim_property_package is None
    assert calls[0]["model_name"] == "PCSAFT"
    assert calls[0]["ideal_model_name"] == "WalkerIdeal"
    assert calls[0]["model_kwargs"] == {}


def test_build_primary_clapeyron_backend_can_use_dwsim_pr_parameters(monkeypatch):
    import dynamic_distillation.thermo_backend_factory_v1 as factory
    import dynamic_distillation.thermo_clapeyron_provider_v1 as thermo_clapeyron_provider_v1

    calls = []

    class _FakeProvider:
        def __init__(self, *args, **kwargs):
            calls.append(dict(kwargs))

    monkeypatch.setattr(thermo_clapeyron_provider_v1, "ThermoClapeyronProviderV1", _FakeProvider)
    monkeypatch.setattr(factory, "_clapeyron_dwsim_pr_userlocations", lambda _col: {"userlocations": "sentinel"})

    cfg = SimpleNamespace(
        thermo_mode="clapeyron",
        dwsim_property_package="pr",
        clapeyron_model="PR",
        clapeyron_ideal_model=None,
        clapeyron_pr_parameter_source="dwsim",
    )
    build = build_primary_thermo_backend(cfg=cfg, col=_fake_col(), emit_progress=lambda _msg: None)

    assert build.thermo_mode == "clapeyron"
    assert calls[0]["model_name"] == "PR"
    assert calls[0]["model_kwargs"] == {"userlocations": "sentinel"}


def test_build_primary_clapeyron_backend_reports_batch_capability(monkeypatch):
    import dynamic_distillation.thermo_clapeyron_provider_v1 as thermo_clapeyron_provider_v1

    class _FakeProvider:
        component_names_excel = ["A", "B"]

        def __init__(self, *args, **kwargs):
            _ = (args, kwargs)

        def flash_TP_full_F_psia(self, T_F, P_psia, z):
            _ = (T_F, P_psia, z)
            return ([0.5, 0.5], [0.5, 0.5], [1.0, 1.0], -10.0, 10.0, 1.0)

        def flash_TP_full_batch(self, T_rows, P_rows, z_rows):
            _ = (T_rows, P_rows, z_rows)
            return []

        def cp_liq_vap_btu_per_lbmolF(self, T_F, P_psia, z):
            _ = (T_F, P_psia, z)
            return (1.0, 2.0)

        def liquid_density_lbmol_ft3(self, T_F, P_psia, x):
            _ = (T_F, P_psia, x)
            return 1.0

        def bubble_point_temperature_F_psia(self, P_psia, x):
            _ = (P_psia, x)
            return 100.0

    monkeypatch.setattr(thermo_clapeyron_provider_v1, "ThermoClapeyronProviderV1", _FakeProvider)

    cfg = SimpleNamespace(
        thermo_mode="clapeyron",
        dwsim_property_package="pr",
        clapeyron_model="PR",
        clapeyron_ideal_model=None,
    )
    build = build_primary_thermo_backend(cfg=cfg, col=_fake_col(), emit_progress=lambda _msg: None)

    assert build.capabilities.supports_batch_tp_flash is True
    assert build.capabilities.supports_direct_cp is True
    assert build.capabilities.supports_density is True
    assert build.capabilities.supports_bubble_point is True


def test_build_primary_clapeyron_backend_fails_fast_when_package_missing(monkeypatch):
    import dynamic_distillation.thermo_clapeyron_provider_v1 as thermo_clapeyron_provider_v1

    def fake_import_module(name):
        if name == "pyclapeyron":
            raise ImportError("missing pyclapeyron")
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr(thermo_clapeyron_provider_v1.importlib, "import_module", fake_import_module)

    cfg = SimpleNamespace(
        thermo_mode="clapeyron",
        dwsim_property_package="pr",
        clapeyron_model="PR",
        clapeyron_ideal_model=None,
    )
    with pytest.raises(RuntimeError, match="pyclapeyron"):
        build_primary_thermo_backend(cfg=cfg, col=_fake_col(), emit_progress=lambda _msg: None)


def test_build_equilibrium_relaxation_pr_provider_skips_redundant_pr(monkeypatch):
    import dynamic_distillation.thermo_provider_v1 as thermo_provider_v1

    calls = []

    class _FakeProvider:
        def __init__(self, *args, **kwargs):
            calls.append(dict(kwargs))

    monkeypatch.setattr(thermo_provider_v1, "ThermoProviderV1", _FakeProvider)

    provider = build_equilibrium_relaxation_pr_provider(
        enabled=True,
        col=_fake_col(),
        primary_thermo_mode="dwsim",
        primary_dwsim_property_package="pr",
        emit_progress=lambda _msg: None,
    )

    assert provider is None
    assert calls == []


def test_build_equilibrium_relaxation_pr_provider_builds_for_non_pr(monkeypatch):
    import dynamic_distillation.thermo_provider_v1 as thermo_provider_v1

    calls = []

    class _FakeProvider:
        def __init__(self, *args, **kwargs):
            calls.append(dict(kwargs))

    monkeypatch.setattr(thermo_provider_v1, "ThermoProviderV1", _FakeProvider)

    provider = build_equilibrium_relaxation_pr_provider(
        enabled=True,
        col=_fake_col(),
        primary_thermo_mode="dwsim",
        primary_dwsim_property_package="unifac",
        emit_progress=lambda _msg: None,
    )

    assert provider is not None
    assert calls[0]["property_package"] == "pr"


def test_build_primary_table_requires_table_path():
    cfg = SimpleNamespace(
        thermo_mode="table",
        thermo_table_path=None,
        thermo_table_n_anchor_blend=3,
        thermo_table_anchor_blend_power=2.0,
        thermo_top_saturation_table_path=None,
        thermo_upper_section_table_path=None,
        thermo_upper_section_stage_count=5,
    )

    with pytest.raises(ValueError, match="thermo_mode='table' requires RunnerConfig.thermo_table_path"):
        build_primary_thermo_backend(cfg=cfg, col=_fake_col(), emit_progress=lambda _msg: None)
