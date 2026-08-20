"""Two-phase conservation balances for the vapor-holdup successor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from dynamic_distillation.core_v3.provider_governed_registry_v1 import ColumnTopology


@dataclass(frozen=True)
class VaporHoldupBalanceInputs:
    topology: ColumnTopology
    feed_component_lbmolph: np.ndarray
    feed_enthalpy_BTUph: float
    reflux_lbmolph: float
    distillate_lbmolph: float
    bottoms_lbmolph: float
    condenser_duty_BTUph: float
    reboiler_duty_BTUph: float


@dataclass(frozen=True)
class TwoPhaseTransportEvaluation:
    volume_ids: tuple[str, ...]
    liquid_transport_lbmolph: np.ndarray
    vapor_transport_lbmolph: np.ndarray
    liquid_energy_transport_BTUph: np.ndarray
    vapor_energy_transport_BTUph: np.ndarray
    external_component_rate_lbmolph: np.ndarray
    external_energy_rate_BTUph: float


@dataclass(frozen=True)
class TwoPhaseBalanceEvaluation:
    liquid_component_residual_lbmolph: np.ndarray
    vapor_component_residual_lbmolph: np.ndarray
    total_component_residual_lbmolph: np.ndarray
    energy_residual_BTUph: np.ndarray
    phase_transfer_cancellation_lbmolph: np.ndarray
    global_component_telescoping_error_lbmolph: np.ndarray
    global_energy_telescoping_error_BTUph: float


def _matrix(values: Sequence[Sequence[float]], *, name: str, shape: tuple[int, int]) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != shape or np.any(~np.isfinite(result)):
        raise ValueError(f"{name} must be finite with shape {shape}")
    return result


def _vector(values: Sequence[float], *, name: str, length: int) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != (length,) or np.any(~np.isfinite(result)):
        raise ValueError(f"{name} must be finite with length {length}")
    return result


def evaluate_two_phase_transport(
    inputs: VaporHoldupBalanceInputs,
    liquid_mole_fraction: Sequence[Sequence[float]],
    vapor_mole_fraction: Sequence[Sequence[float]],
    hydraulic_liquid_flow_lbmolph: Sequence[float],
    vapor_flow_lbmolph: Sequence[float],
    liquid_enthalpy_BTU_lbmol: Sequence[float],
    vapor_enthalpy_BTU_lbmol: Sequence[float],
) -> TwoPhaseTransportEvaluation:
    topology = inputs.topology
    volumes = tuple(topology.volume_ids)
    volume_count = len(volumes)
    component_count = np.asarray(inputs.feed_component_lbmolph).size
    x = _matrix(
        liquid_mole_fraction,
        name="liquid mole fraction",
        shape=(volume_count, component_count),
    )
    y = _matrix(
        vapor_mole_fraction,
        name="vapor mole fraction",
        shape=(volume_count, component_count),
    )
    if np.any(x <= 0.0) or np.any(y <= 0.0):
        raise ValueError("phase compositions must be strictly positive")
    if not np.allclose(np.sum(x, axis=1), 1.0, rtol=0.0, atol=1.0e-10):
        raise ValueError("liquid compositions must sum to one")
    if not np.allclose(np.sum(y, axis=1), 1.0, rtol=0.0, atol=1.0e-10):
        raise ValueError("vapor compositions must sum to one")
    liquid_flow = _vector(
        hydraulic_liquid_flow_lbmolph,
        name="hydraulic liquid flow",
        length=len(topology.hydraulic_volume_ids),
    )
    vapor_flow = _vector(
        vapor_flow_lbmolph,
        name="vapor flow",
        length=len(topology.vapor_links),
    )
    h_liquid = _vector(
        liquid_enthalpy_BTU_lbmol,
        name="liquid enthalpy",
        length=volume_count,
    )
    h_vapor = _vector(
        vapor_enthalpy_BTU_lbmol,
        name="vapor enthalpy",
        length=volume_count,
    )
    feed = _vector(
        inputs.feed_component_lbmolph,
        name="feed component flow",
        length=component_count,
    )
    scalar_values = np.asarray(
        [
            inputs.feed_enthalpy_BTUph,
            inputs.reflux_lbmolph,
            inputs.distillate_lbmolph,
            inputs.bottoms_lbmolph,
            inputs.condenser_duty_BTUph,
            inputs.reboiler_duty_BTUph,
        ],
        dtype=float,
    )
    if np.any(~np.isfinite(scalar_values)):
        raise ValueError("balance inputs must be finite")
    if np.any(scalar_values[1:4] < 0.0):
        raise ValueError("reflux and product flows must be nonnegative")
    if np.any(liquid_flow < 0.0) or np.any(vapor_flow < 0.0):
        raise ValueError("interstage flows must be nonnegative")

    volume_index = {volume: index for index, volume in enumerate(volumes)}
    hydraulic_index = {
        volume: index
        for index, volume in enumerate(topology.hydraulic_volume_ids)
    }
    liquid_transport = np.zeros((volume_count, component_count), dtype=float)
    vapor_transport = np.zeros_like(liquid_transport)
    liquid_energy = np.zeros(volume_count, dtype=float)
    vapor_energy = np.zeros(volume_count, dtype=float)
    for source, destination, symbol in topology.liquid_links:
        source_index = volume_index[source]
        flow = (
            float(inputs.reflux_lbmolph)
            if symbol == "R"
            else float(liquid_flow[hydraulic_index[source]])
        )
        component_rate = flow * x[source_index]
        enthalpy_rate = flow * h_liquid[source_index]
        liquid_transport[source_index] -= component_rate
        liquid_transport[volume_index[destination]] += component_rate
        liquid_energy[source_index] -= enthalpy_rate
        liquid_energy[volume_index[destination]] += enthalpy_rate
    for link_index, (source, destination, _symbol) in enumerate(topology.vapor_links):
        source_index = volume_index[source]
        component_rate = float(vapor_flow[link_index]) * y[source_index]
        enthalpy_rate = float(vapor_flow[link_index]) * h_vapor[source_index]
        vapor_transport[source_index] -= component_rate
        vapor_transport[volume_index[destination]] += component_rate
        vapor_energy[source_index] -= enthalpy_rate
        vapor_energy[volume_index[destination]] += enthalpy_rate

    feed_index = volume_index[topology.feed_volume]
    top_index = volume_index[topology.top_volume]
    bottom_index = volume_index[topology.bottom_volume]
    liquid_transport[feed_index] += feed
    liquid_transport[top_index] -= float(inputs.distillate_lbmolph) * x[top_index]
    liquid_transport[bottom_index] -= float(inputs.bottoms_lbmolph) * x[bottom_index]
    liquid_energy[feed_index] += float(inputs.feed_enthalpy_BTUph)
    liquid_energy[top_index] += (
        float(inputs.condenser_duty_BTUph)
        - float(inputs.distillate_lbmolph) * h_liquid[top_index]
    )
    liquid_energy[bottom_index] += (
        float(inputs.reboiler_duty_BTUph)
        - float(inputs.bottoms_lbmolph) * h_liquid[bottom_index]
    )
    external_component = (
        feed
        - float(inputs.distillate_lbmolph) * x[top_index]
        - float(inputs.bottoms_lbmolph) * x[bottom_index]
    )
    external_energy = (
        float(inputs.feed_enthalpy_BTUph)
        + float(inputs.condenser_duty_BTUph)
        + float(inputs.reboiler_duty_BTUph)
        - float(inputs.distillate_lbmolph) * h_liquid[top_index]
        - float(inputs.bottoms_lbmolph) * h_liquid[bottom_index]
    )
    return TwoPhaseTransportEvaluation(
        volume_ids=volumes,
        liquid_transport_lbmolph=liquid_transport,
        vapor_transport_lbmolph=vapor_transport,
        liquid_energy_transport_BTUph=liquid_energy,
        vapor_energy_transport_BTUph=vapor_energy,
        external_component_rate_lbmolph=external_component,
        external_energy_rate_BTUph=external_energy,
    )


def evaluate_two_phase_balances(
    transport: TwoPhaseTransportEvaluation,
    liquid_component_rate_lbmolph: Sequence[Sequence[float]],
    vapor_component_rate_lbmolph: Sequence[Sequence[float]],
    phase_transfer_vapor_to_liquid_lbmolph: Sequence[Sequence[float]],
    total_stored_energy_rate_BTUph: Sequence[float],
) -> TwoPhaseBalanceEvaluation:
    shape = transport.liquid_transport_lbmolph.shape
    liquid_rate = _matrix(
        liquid_component_rate_lbmolph,
        name="liquid component rate",
        shape=shape,
    )
    vapor_rate = _matrix(
        vapor_component_rate_lbmolph,
        name="vapor component rate",
        shape=shape,
    )
    transfer = _matrix(
        phase_transfer_vapor_to_liquid_lbmolph,
        name="phase transfer",
        shape=shape,
    )
    energy_rate = _vector(
        total_stored_energy_rate_BTUph,
        name="total stored energy rate",
        length=shape[0],
    )
    liquid_residual = liquid_rate - (
        transport.liquid_transport_lbmolph + transfer
    )
    vapor_residual = vapor_rate - (
        transport.vapor_transport_lbmolph - transfer
    )
    total_residual = liquid_residual + vapor_residual
    energy_transport = (
        transport.liquid_energy_transport_BTUph
        + transport.vapor_energy_transport_BTUph
    )
    energy_residual = energy_rate - energy_transport
    transfer_cancellation = transfer - transfer
    component_telescoping = (
        np.sum(
            transport.liquid_transport_lbmolph
            + transport.vapor_transport_lbmolph,
            axis=0,
        )
        - transport.external_component_rate_lbmolph
    )
    energy_telescoping = float(
        np.sum(energy_transport) - transport.external_energy_rate_BTUph
    )
    return TwoPhaseBalanceEvaluation(
        liquid_component_residual_lbmolph=liquid_residual,
        vapor_component_residual_lbmolph=vapor_residual,
        total_component_residual_lbmolph=total_residual,
        energy_residual_BTUph=energy_residual,
        phase_transfer_cancellation_lbmolph=transfer_cancellation,
        global_component_telescoping_error_lbmolph=component_telescoping,
        global_energy_telescoping_error_BTUph=energy_telescoping,
    )


def stationary_phase_transfer_from_vapor_transport(
    transport: TwoPhaseTransportEvaluation,
) -> np.ndarray:
    """Return positive vapor-to-liquid transfer needed for zero vapor rates."""
    return np.asarray(transport.vapor_transport_lbmolph, dtype=float).copy()


__all__ = [
    "TwoPhaseBalanceEvaluation",
    "TwoPhaseTransportEvaluation",
    "VaporHoldupBalanceInputs",
    "evaluate_two_phase_balances",
    "evaluate_two_phase_transport",
    "stationary_phase_transfer_from_vapor_transport",
]
