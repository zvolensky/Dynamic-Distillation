"""
thermo_backend_factory_v1.py

Dynamic Distillation - Thermo Backend Factory

PURPOSE
-------
Centralize thermo backend construction so the runner can move toward a more
explicit backend-adapter architecture without changing runtime behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np

from dynamic_distillation.thermo_backend_protocol_v1 import (
    ThermoBackendCapabilities,
    get_thermo_backend_capabilities,
)
from dynamic_distillation.thermo_stub_provider_v1 import StubThermoProvider


_DWSIM_MODE_ALIASES = (
    "dwsim",
    "dwsim-unifac",
    "dwsim-nrtl",
    "dwsim-uniquac",
    "dwsim-raoult",
    "dwsim-srk",
)


@dataclass(frozen=True)
class ThermoBackendBuildResult:
    provider: Any
    thermo_mode: str
    dwsim_property_package: Optional[str]
    capabilities: ThermoBackendCapabilities


def supported_thermo_modes_text() -> str:
    return (
        "'stub', 'relative-volatility', 'clapeyron', 'dwsim', 'dwsim-unifac', 'dwsim-nrtl', "
        "'dwsim-uniquac', 'dwsim-raoult', 'dwsim-srk', 'table', or 'table-pool'"
    )


def _clapeyron_dwsim_pr_userlocations(col: Any) -> dict[str, Any]:
    from dynamic_distillation import pr_flash_backend_v1 as dwsim_backend
    import pyclapeyron

    dwsim_backend.set_component_ids(list(col.components_dwsim))
    dwsim_backend.set_component_names(list(col.components_excel))
    dwsim_backend.set_property_package("pr")
    dwsim_backend._init_dwsim()

    def _const(component_id: str, prop_name: str) -> float:
        return float(dwsim_backend._dtlc.GetCompoundConstProp(str(component_id), str(prop_name)))

    component_ids = [str(v) for v in col.components_dwsim]
    tc = [_const(cid, "criticalTemperature") for cid in component_ids]
    pc = [_const(cid, "criticalPressure") for cid in component_ids]
    mw = [_const(cid, "molecularWeight") for cid in component_ids]
    omega = [_const(cid, "acentricFactor") for cid in component_ids]

    n = len(component_ids)
    kij = np.zeros((n, n), dtype=float)
    try:
        ip = dwsim_backend._prop_package.m_pr.InteractionParameters
        for i, c1 in enumerate(component_ids):
            for j, c2 in enumerate(component_ids):
                if i == j:
                    continue
                for a, b in ((c1, c2), (c2, c1)):
                    try:
                        kij[i, j] = float(ip[a][b].kij)
                        break
                    except Exception:
                        continue
    except Exception:
        pass

    def _julia_vector(values: list[float]) -> str:
        return "[" + ", ".join(f"{float(v):.17g}" for v in values) + "]"

    def _julia_matrix(values: np.ndarray) -> str:
        return "[" + "; ".join(" ".join(f"{float(v):.17g}" for v in row) for row in values) + "]"

    expr = (
        f"(;Tc={_julia_vector(tc)}, Pc={_julia_vector(pc)}, Mw={_julia_vector(mw)}, "
        f"acentricfactor={_julia_vector(omega)}, k={_julia_matrix(kij)})"
    )
    return {"userlocations": pyclapeyron.jl.seval(expr)}


def resolve_dwsim_property_package(thermo_mode: str, configured_package: Optional[str]) -> Optional[str]:
    mode = str(thermo_mode or "").strip().lower()
    if mode not in _DWSIM_MODE_ALIASES:
        return None
    pkg = str(configured_package or "pr").strip().lower()
    if mode.startswith("dwsim-"):
        pkg = str(mode.split("-", 1)[1]).strip().lower()
    return pkg


def _set_debug_trace_hook_if_available(provider: Any, emit_progress: Callable[[str], None]) -> None:
    if hasattr(provider, "debug_trace_hook"):
        try:
            setattr(provider, "debug_trace_hook", emit_progress)
        except Exception:
            pass


def _attach_optional_tabular_helpers(
    *,
    provider: Any,
    cfg: Any,
    col: Any,
    emit_progress: Callable[[str], None],
) -> None:
    if getattr(cfg, "thermo_top_saturation_table_path", None):
        try:
            from dynamic_distillation.top_end_saturation_table_v1 import TopEndSaturationTableV1

            top_sat = TopEndSaturationTableV1.from_json(str(cfg.thermo_top_saturation_table_path))
            if hasattr(provider, "attach_top_saturation_table"):
                provider.attach_top_saturation_table(top_sat)
                emit_progress(f"[Init] Attached top-end saturation table: {cfg.thermo_top_saturation_table_path}")
        except Exception as exc:
            emit_progress(f"[Warn] Failed to attach top-end saturation table: {exc}")
    if getattr(cfg, "thermo_upper_section_table_path", None):
        try:
            from dynamic_distillation.thermo_surrogate_v1 import TabularThermoProviderV1

            upper_prov = TabularThermoProviderV1.from_json(
                str(cfg.thermo_upper_section_table_path),
                expected_component_names_excel=col.components_excel,
                expected_component_ids_dwsim=col.components_dwsim,
                n_anchor_blend=int(cfg.thermo_table_n_anchor_blend),
                anchor_blend_power=float(cfg.thermo_table_anchor_blend_power),
            )
            if hasattr(provider, "attach_upper_section_flash_provider"):
                stage_count = max(int(getattr(cfg, "thermo_upper_section_stage_count", 5) or 5), 1)
                provider.attach_upper_section_flash_provider(
                    upper_prov,
                    max_stage_index0=int(stage_count - 1),
                )
                emit_progress(
                    f"[Init] Attached upper-section flash table: "
                    f"{cfg.thermo_upper_section_table_path} (stages 1-{stage_count})"
                )
        except Exception as exc:
            emit_progress(f"[Warn] Failed to attach upper-section flash table: {exc}")


def build_primary_thermo_backend(
    *,
    cfg: Any,
    col: Any,
    emit_progress: Callable[[str], None],
) -> ThermoBackendBuildResult:
    thermo_mode = str(getattr(cfg, "thermo_mode", "") or "").strip().lower()
    dwsim_pkg = resolve_dwsim_property_package(
        thermo_mode,
        getattr(cfg, "dwsim_property_package", "pr"),
    )

    if thermo_mode in _DWSIM_MODE_ALIASES:
        from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1

        emit_progress(f"[Init] Building thermo provider  mode={thermo_mode}  package={dwsim_pkg}")
        provider = ThermoProviderV1(
            component_names_excel=col.components_excel,
            component_ids_dwsim=col.components_dwsim,
            silence_backend_console=True,
            property_package=dwsim_pkg,
        )
    elif thermo_mode == "clapeyron":
        from dynamic_distillation.thermo_clapeyron_provider_v1 import ThermoClapeyronProviderV1

        clapeyron_model = str(getattr(cfg, "clapeyron_model", "PR") or "PR").strip()
        clapeyron_ideal_model = getattr(cfg, "clapeyron_ideal_model", None)
        parameter_source = str(getattr(cfg, "clapeyron_pr_parameter_source", "default") or "default").strip().lower()
        model_kwargs = {}
        if parameter_source in {"dwsim", "dwsim-pr"}:
            if clapeyron_model.upper() != "PR":
                raise ValueError("--clapeyron-pr-parameter-source dwsim is only valid with --clapeyron-model PR")
            emit_progress("[Init] Aligning Clapeyron PR parameters to DWSIM PR constants/kij")
            model_kwargs = _clapeyron_dwsim_pr_userlocations(col)
        elif parameter_source not in {"default", "clapeyron"}:
            raise ValueError("clapeyron_pr_parameter_source must be 'default' or 'dwsim'")
        emit_progress(
            f"[Init] Building thermo provider  mode=clapeyron  model={clapeyron_model}"
        )
        provider = ThermoClapeyronProviderV1(
            component_names_excel=col.components_excel,
            component_ids_dwsim=col.components_dwsim,
            model_name=clapeyron_model,
            ideal_model_name=clapeyron_ideal_model,
            model_kwargs=model_kwargs,
        )
    elif thermo_mode == "table":
        emit_progress("[Init] Building thermo provider  mode=table")
        if not getattr(cfg, "thermo_table_path", None):
            raise ValueError("thermo_mode='table' requires RunnerConfig.thermo_table_path")
        from dynamic_distillation.thermo_surrogate_v1 import TabularThermoProviderV1

        provider = TabularThermoProviderV1.from_json(
            str(cfg.thermo_table_path),
            expected_component_names_excel=col.components_excel,
            expected_component_ids_dwsim=col.components_dwsim,
            n_anchor_blend=int(cfg.thermo_table_n_anchor_blend),
            anchor_blend_power=float(cfg.thermo_table_anchor_blend_power),
        )
        _attach_optional_tabular_helpers(provider=provider, cfg=cfg, col=col, emit_progress=emit_progress)
    elif thermo_mode == "table-pool":
        emit_progress("[Init] Building thermo provider  mode=table-pool")
        if not getattr(cfg, "thermo_table_path", None):
            raise ValueError("thermo_mode='table-pool' requires RunnerConfig.thermo_table_path")
        from dynamic_distillation.thermo_table_pool_v1 import ParallelTabularThermoProviderV1

        provider = ParallelTabularThermoProviderV1(
            table_path=str(cfg.thermo_table_path),
            expected_component_names_excel=col.components_excel,
            expected_component_ids_dwsim=col.components_dwsim,
            n_anchor_blend=int(cfg.thermo_table_n_anchor_blend),
            anchor_blend_power=float(cfg.thermo_table_anchor_blend_power),
            max_workers=cfg.thermo_pool_workers,
            chunk_size=int(cfg.thermo_pool_chunk_size),
            task_timeout_sec=cfg.thermo_pool_task_timeout_sec,
        )
    elif thermo_mode == "stub":
        emit_progress("[Init] Building thermo provider  mode=stub")
        n_components = int(col.n_components)
        if n_components == 1:
            k_vals = np.array([1.0], dtype=float)
        else:
            k_vals = 2.0 ** (1.0 - np.arange(n_components, dtype=float) / float(n_components - 1))
        provider = StubThermoProvider(K=k_vals, Z=1.0)
    elif thermo_mode in {"relative-volatility", "simple-rv", "constant-alpha"}:
        from dynamic_distillation.thermo_relative_volatility_provider_v1 import RelativeVolatilityThermoProviderV1

        specs_raw = getattr(col, "specs_raw", {}) or {}
        alpha = specs_raw.get("Relative Volatility", None)
        if alpha is None:
            alpha = specs_raw.get("Relative Volatility Alpha", None)
        if alpha is None:
            alpha = specs_raw.get("Constant Relative Volatility", None)
        alpha = 1.6 if alpha is None else float(alpha)
        emit_progress(f"[Init] Building thermo provider  mode=relative-volatility  alpha={alpha:g}")
        provider = RelativeVolatilityThermoProviderV1(
            component_names_excel=col.components_excel,
            component_ids_dwsim=col.components_dwsim,
            alpha_light=float(alpha),
        )
    else:
        raise ValueError(f"Unsupported thermo_mode: {thermo_mode!r} (use {supported_thermo_modes_text()})")

    _set_debug_trace_hook_if_available(provider, emit_progress)
    emit_progress(f"[Init] Thermo provider ready  mode={thermo_mode}")
    return ThermoBackendBuildResult(
        provider=provider,
        thermo_mode=thermo_mode,
        dwsim_property_package=dwsim_pkg,
        capabilities=get_thermo_backend_capabilities(provider),
    )


def build_equilibrium_relaxation_pr_provider(
    *,
    enabled: bool,
    col: Any,
    primary_thermo_mode: str,
    primary_dwsim_property_package: Optional[str],
    emit_progress: Callable[[str], None],
) -> Any:
    if not bool(enabled):
        return None
    if str(primary_thermo_mode or "").startswith("dwsim"):
        primary_pkg = str(primary_dwsim_property_package or "pr").strip().lower()
        if primary_pkg == "pr":
            emit_progress(
                "[Init] Equilibrium-relaxation live PR requested, but primary thermo is already DWSIM PR; "
                "skipping separate override provider"
            )
            return None
        emit_progress("[Init] Building selective equilibrium-relaxation PR provider")
    from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1

    return ThermoProviderV1(
        component_names_excel=col.components_excel,
        component_ids_dwsim=col.components_dwsim,
        silence_backend_console=True,
        property_package="pr",
    )
