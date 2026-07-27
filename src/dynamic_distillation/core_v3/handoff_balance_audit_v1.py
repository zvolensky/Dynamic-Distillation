"""Term-level material and energy ledger for Core V3 handoff audits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    EQUILIBRIUM_VOLUME_IDS,
    VOLUME_IDS,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    LiveProperties,
    OperatingSpec,
    PhysicalState,
)


@dataclass(frozen=True)
class BalanceTermLedger:
    component_terms_lbmolph: Mapping[str, Mapping[str, np.ndarray]]
    energy_terms_BTUph: Mapping[str, Mapping[str, float]]

    @property
    def component_net_lbmolph(self) -> np.ndarray:
        return np.asarray(
            [
                np.sum(
                    np.asarray(list(self.component_terms_lbmolph[volume].values())),
                    axis=0,
                )
                for volume in VOLUME_IDS
            ],
            dtype=float,
        )

    @property
    def energy_net_BTUph(self) -> np.ndarray:
        return np.asarray(
            [sum(self.energy_terms_BTUph[volume].values()) for volume in VOLUME_IDS],
            dtype=float,
        )


def _vapor_composition(state: PhysicalState, volume: str) -> np.ndarray:
    return np.asarray(
        state.vapor_mole_fraction[EQUILIBRIUM_VOLUME_IDS.index(volume)],
        dtype=float,
    )


def build_balance_term_ledger(
    spec: OperatingSpec,
    state: PhysicalState,
    properties: LiveProperties,
) -> BalanceTermLedger:
    component_count = len(spec.component_names)
    x = np.asarray(state.liquid_mole_fraction, dtype=float)
    h_l = np.asarray(properties.liquid_enthalpy_BTU_lbmol, dtype=float)
    h_v = np.asarray(properties.vapor_enthalpy_BTU_lbmol, dtype=float)
    liquid = np.asarray(state.hydraulic_liquid_flow_lbmolph, dtype=float)
    vapor = np.asarray(state.vapor_flow_lbmolph, dtype=float)
    feed = np.asarray(spec.feed_component_lbmolph, dtype=float)
    if (
        x.shape != (len(VOLUME_IDS), component_count)
        or h_l.shape != (len(VOLUME_IDS),)
        or h_v.shape != (len(VOLUME_IDS),)
        or liquid.shape != (3,)
        or vapor.shape != (4,)
        or feed.shape != (component_count,)
    ):
        raise ValueError("Core V3 balance-term input shape is invalid")

    drum, rectifying, feed_volume, stripping, bottom = VOLUME_IDS
    y_rect = _vapor_composition(state, rectifying)
    y_feed = _vapor_composition(state, feed_volume)
    y_strip = _vapor_composition(state, stripping)
    y_bottom = _vapor_composition(state, bottom)
    l_rect, l_feed, l_strip = liquid
    v_bottom_strip, v_strip_feed, v_feed_rect, v_rect_drum = vapor
    reflux = float(spec.reflux_lbmolph)
    distillate = float(state.distillate_lbmolph)
    bottoms = float(state.bottoms_lbmolph)

    component = {
        drum: {
            "vapor_in_from_rectifying": v_rect_drum * y_rect,
            "liquid_out_reflux": -reflux * x[0],
            "liquid_out_distillate": -distillate * x[0],
        },
        rectifying: {
            "liquid_in_reflux": reflux * x[0],
            "vapor_in_from_feed": v_feed_rect * y_feed,
            "liquid_out_to_feed": -l_rect * x[1],
            "vapor_out_to_drum": -v_rect_drum * y_rect,
        },
        feed_volume: {
            "liquid_in_from_rectifying": l_rect * x[1],
            "vapor_in_from_stripping": v_strip_feed * y_strip,
            "feed_in": feed.copy(),
            "liquid_out_to_stripping": -l_feed * x[2],
            "vapor_out_to_rectifying": -v_feed_rect * y_feed,
        },
        stripping: {
            "liquid_in_from_feed": l_feed * x[2],
            "vapor_in_from_bottom": v_bottom_strip * y_bottom,
            "liquid_out_to_bottom": -l_strip * x[3],
            "vapor_out_to_feed": -v_strip_feed * y_strip,
        },
        bottom: {
            "liquid_in_from_stripping": l_strip * x[3],
            "liquid_out_bottoms": -bottoms * x[4],
            "vapor_out_to_stripping": -v_bottom_strip * y_bottom,
        },
    }
    energy = {
        drum: {
            "vapor_in_from_rectifying": v_rect_drum * h_v[1],
            "condenser_duty": float(state.condenser_duty_BTUph),
            "liquid_out_reflux": -reflux * h_l[0],
            "liquid_out_distillate": -distillate * h_l[0],
        },
        rectifying: {
            "liquid_in_reflux": reflux * h_l[0],
            "vapor_in_from_feed": v_feed_rect * h_v[2],
            "liquid_out_to_feed": -l_rect * h_l[1],
            "vapor_out_to_drum": -v_rect_drum * h_v[1],
        },
        feed_volume: {
            "liquid_in_from_rectifying": l_rect * h_l[1],
            "vapor_in_from_stripping": v_strip_feed * h_v[3],
            "feed_in": float(spec.feed_enthalpy_BTUph),
            "liquid_out_to_stripping": -l_feed * h_l[2],
            "vapor_out_to_rectifying": -v_feed_rect * h_v[2],
        },
        stripping: {
            "liquid_in_from_feed": l_feed * h_l[2],
            "vapor_in_from_bottom": v_bottom_strip * h_v[4],
            "liquid_out_to_bottom": -l_strip * h_l[3],
            "vapor_out_to_feed": -v_strip_feed * h_v[3],
        },
        bottom: {
            "liquid_in_from_stripping": l_strip * h_l[3],
            "reboiler_duty": float(spec.reboiler_duty_BTUph),
            "liquid_out_bottoms": -bottoms * h_l[4],
            "vapor_out_to_stripping": -v_bottom_strip * h_v[4],
        },
    }
    return BalanceTermLedger(
        component_terms_lbmolph=component,
        energy_terms_BTUph=energy,
    )


def ranked_component_term_changes(
    first: BalanceTermLedger,
    second: BalanceTermLedger,
    *,
    volume: str,
    component_index: int,
) -> tuple[tuple[str, float], ...]:
    first_terms = first.component_terms_lbmolph[volume]
    second_terms = second.component_terms_lbmolph[volume]
    if first_terms.keys() != second_terms.keys():
        raise ValueError("component balance ownership changed between snapshots")
    return tuple(
        sorted(
            (
                (name, float(np.asarray(second_terms[name])[component_index] - np.asarray(first_terms[name])[component_index]))
                for name in first_terms
            ),
            key=lambda item: abs(item[1]),
            reverse=True,
        )
    )


def ranked_energy_term_changes(
    first: BalanceTermLedger,
    second: BalanceTermLedger,
    *,
    volume: str,
) -> tuple[tuple[str, float], ...]:
    first_terms = first.energy_terms_BTUph[volume]
    second_terms = second.energy_terms_BTUph[volume]
    if first_terms.keys() != second_terms.keys():
        raise ValueError("energy balance ownership changed between snapshots")
    return tuple(
        sorted(
            (
                (name, float(second_terms[name] - first_terms[name]))
                for name in first_terms
            ),
            key=lambda item: abs(item[1]),
            reverse=True,
        )
    )


__all__ = [
    "BalanceTermLedger",
    "build_balance_term_ledger",
    "ranked_component_term_changes",
    "ranked_energy_term_changes",
]
