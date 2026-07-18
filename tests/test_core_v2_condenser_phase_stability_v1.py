from __future__ import annotations

import numpy as np
import pytest

from dynamic_distillation.core_v2.condenser_phase_stability_v1 import (
    audit_fixed_duty_condenser_outlet,
    rachford_rice_vapor_fraction,
)
from dynamic_distillation.core_v2.condenser_saturated_liquid_registry_v1 import (
    audit_condenser_saturated_liquid_registry,
    build_condenser_saturated_liquid_registry,
)


class _Provider:
    def __init__(self, K):
        self.K = np.asarray(K, dtype=float)

    def flash_TP_full(self, T_F, P_psia, z):
        class _Result:
            pass

        result = _Result()
        result.K = self.K
        return result

    def phase_enthalpy_BTU_lbmol(self, phase, T_F, P_psia, comp):
        return 1000.0 if str(phase).lower() == "vapor" else 500.0


def test_dd086_rachford_rice_classifies_single_phase_limits():
    z = [0.5, 0.5]

    assert rachford_rice_vapor_fraction([0.5, 0.8], z) == 0.0
    assert rachford_rice_vapor_fraction([1.2, 2.0], z) == 1.0
    assert 0.0 < rachford_rice_vapor_fraction([2.0, 0.5], z) < 1.0


def test_dd086_fixed_duty_audit_does_not_equate_enthalpy_with_liquid_stability():
    audit = audit_fixed_duty_condenser_outlet(
        _Provider([1.2, 2.0]),
        inlet_temperature_F=160.0,
        inlet_pressure_psia=220.0,
        inlet_vapor_composition=[0.5, 0.5],
        outlet_temperature_F=165.0,
        outlet_pressure_psia=218.0,
        outlet_overall_composition=[0.5, 0.5],
        overhead_vapor_flow_lbmolph=100.0,
        condenser_duty_BTUph=-50000.0,
    )

    assert audit.enthalpy_error_BTU_lbmol == pytest.approx(0.0)
    assert audit.phase_classification == "vapor"
    assert not audit.stable_single_liquid


def test_dd086_solved_duty_registry_is_square_full_rank_and_conservative():
    registry = build_condenser_saturated_liquid_registry(
        ("Propane", "n-Butane", "n-Pentane")
    )
    audit = audit_condenser_saturated_liquid_registry(registry)

    assert audit.unknown_count == 40
    assert audit.residual_count == 40
    assert audit.structural_rank == 40
    assert audit.structural_nullity == 0
    assert audit.condenser_duty_unknown_count == 1
    assert audit.condenser_incipient_vapor_coordinate_count == 2
    assert audit.condenser_bubble_equation_count == 3
    assert not audit.fixed_condenser_duty_parameter_present
    assert audit.base_component_conservation_passed
    assert audit.base_energy_conservation_passed
    assert audit.pass_gate


def test_dd086_registry_has_one_condenser_duty_owner_and_no_profile():
    registry = build_condenser_saturated_liquid_registry(("A", "B", "C"))
    duty = [entry for entry in registry.unknowns if entry.name == "Q_C"]
    drum_energy = [
        entry
        for entry in registry.residuals
        if entry.name == "energy_balance[reflux_drum]"
    ]

    assert len(duty) == 1
    assert duty[0].block == "solved_condenser_duty"
    assert len(drum_energy) == 1
    assert "Q_C" in drum_energy[0].dependencies
    assert "Q_C" not in registry.external_parameters
    assert not any(
        "profile" in dependency.lower() or "chemsep" in dependency.lower()
        for residual in registry.residuals
        for dependency in residual.dependencies
    )
