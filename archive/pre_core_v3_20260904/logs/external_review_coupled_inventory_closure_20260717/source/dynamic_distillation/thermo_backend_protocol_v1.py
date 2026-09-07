"""
thermo_backend_protocol_v1.py

Dynamic Distillation - Thermo Backend Contracts

PURPOSE
-------
Define lightweight backend-facing contracts for thermo adapters so the runner
and RHS can evolve toward explicit capability-driven behavior instead of
implicit duck-typing only.

CURRENT ROLE
------------
This first version is intentionally small. It documents the common thermo
surface already shared by the existing providers and exposes helper functions
for capability discovery. Later refactor phases can build richer request and
packet orchestration on top of this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class ThermoBackendCapabilities:
    supports_batch_tp_flash: bool = False
    supports_direct_cp: bool = False
    supports_phase_enthalpy: bool = False
    supports_bubble_point: bool = False
    supports_density: bool = False
    supports_z_factor: bool = False
    supports_stage_context: bool = False
    supports_session_reuse: bool = False
    supports_call_counters: bool = False
    supports_trace_context: bool = False


@dataclass(frozen=True)
class ThermoFlashRequest:
    stage_index0: Optional[int]
    T_F: float
    P_psia: float
    z_overall: Sequence[float]
    category: str = ""


@dataclass(frozen=True)
class ThermoFlashResult:
    x: Sequence[float]
    y: Sequence[float]
    K: Sequence[float]
    HL_BTU_lbmol: float
    HV_BTU_lbmol: float
    Z: Optional[float] = None
    cpL_BTU_lbmolF: Optional[float] = None
    cpV_BTU_lbmolF: Optional[float] = None
    provider_tag: str = ""


@runtime_checkable
class ThermoBackendAdapter(Protocol):
    component_names_excel: Sequence[str]

    def flash_TP_full_F_psia(self, T_F: float, P_psia: float, z: Sequence[float]): ...


def get_thermo_backend_capabilities(provider: Any) -> ThermoBackendCapabilities:
    if provider is None:
        return ThermoBackendCapabilities()
    return ThermoBackendCapabilities(
        supports_batch_tp_flash=callable(getattr(provider, "flash_TP_full_batch", None)),
        supports_direct_cp=callable(getattr(provider, "cp_liq_vap_btu_per_lbmolF", None)),
        supports_phase_enthalpy=callable(getattr(provider, "phase_enthalpy_BTU_lbmol", None)),
        supports_bubble_point=callable(getattr(provider, "bubble_point_temperature_F_psia", None)),
        supports_density=callable(getattr(provider, "liquid_density_lbmol_ft3", None)),
        supports_z_factor=callable(getattr(provider, "vapor_z_factor_F_psia", None)),
        supports_stage_context=callable(getattr(provider, "flash_TP_full_stage_F_psia", None)),
        supports_session_reuse=bool(
            callable(getattr(provider, "close", None))
            or callable(getattr(provider, "shutdown", None))
            or hasattr(provider, "_pool")
        ),
        supports_call_counters=callable(getattr(provider, "get_call_counters", None)),
        supports_trace_context=callable(getattr(provider, "set_debug_trace_context", None)),
    )
