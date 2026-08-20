from __future__ import annotations

import numpy as np
import pytest

from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.vapor_holdup_geometry_v1 import (
    VaporControlVolumeGeometry,
)
from dynamic_distillation.core_v3.vapor_holdup_properties_v1 import (
    audit_vapor_holdup_properties,
    evaluate_vapor_holdup_properties,
    evaluate_vapor_holdup_trial_properties,
)


class _Provider:
    def liquid_density_lbmol_ft3(self, temperature_F, pressure_psia, composition):
        return 2.0

    def vapor_z_factor_F_psia(self, temperature_F, pressure_psia, composition):
        return 0.9

    def phase_enthalpy_BTU_lbmol(
        self, phase, temperature_F, pressure_psia, composition
    ):
        return 1000.0 if phase == "liquid" else 9000.0


def _geometry(capacity: float = 100.0):
    return (
        VaporControlVolumeGeometry(
            volume_id="reflux_drum",
            source_stage_1based=1,
            geometry_kind="test",
            gross_capacity_ft3=capacity,
            fixed_vapor_extension_ft3=0.0,
            liquid_displacement_active=True,
            provenance="test",
        ),
        VaporControlVolumeGeometry(
            volume_id="combined_bottom",
            source_stage_1based=2,
            geometry_kind="test",
            gross_capacity_ft3=capacity,
            fixed_vapor_extension_ft3=0.0,
            liquid_displacement_active=True,
            provenance="test",
        ),
    )


def _evaluate(*, capacity: float = 100.0, liquid_x=None, vapor_y=None):
    liquid_x = liquid_x or [[0.7, 0.3], [0.4, 0.6]]
    vapor_y = vapor_y or [[0.8, 0.2], [0.5, 0.5]]
    inventory = np.asarray(liquid_x) * np.asarray([[20.0], [30.0]])
    audit = ProviderCallAudit(
        interface_provider_identities={"declared_liquid_density": "aligned_pr"}
    )
    result = evaluate_vapor_holdup_properties(
        _geometry(capacity),
        inventory,
        liquid_x,
        vapor_y,
        [100.0, 150.0],
        [200.0, 220.0],
        _Provider(),
        audit,
        state_id="unit-test",
    )
    return result, audit


def test_reconstructs_positive_vapor_inventory_and_two_phase_energy():
    result, audit = _evaluate()

    assert np.all(result.vapor_moles_lbmol > 0.0)
    assert np.all(result.vapor_component_inventory_lbmol > 0.0)
    assert np.allclose(
        np.sum(result.vapor_component_inventory_lbmol, axis=1),
        result.vapor_moles_lbmol,
    )
    assert np.allclose(result.eos_volume_residual_ft3, 0.0, atol=1.0e-12)
    assert np.allclose(
        result.total_stored_energy_BTU,
        result.liquid_stored_energy_BTU + result.vapor_stored_energy_BTU,
    )
    assert result.provider_record_end - result.provider_record_start == 8
    assert audit.record_count == 8
    assert sum(record.quantity == "phase_enthalpy" for record in audit.records) == 4
    assert all(
        record.evaluation_kind == "residual" for record in audit.records
    )
    density_records = [
        record for record in audit.records if record.quantity == "liquid_density"
    ]
    assert all(
        record.provider_interface == "aligned_pr.declared_liquid_density"
        for record in density_records
    )
    gate = audit_vapor_holdup_properties(result, audit)
    assert gate.pass_gate
    assert gate.provider_call_count == 8
    assert gate.maximum_relative_eos_residual <= 1.0e-12


def test_free_volume_displaces_resident_vapor():
    large, _ = _evaluate(capacity=100.0)
    small, _ = _evaluate(capacity=50.0)

    assert np.all(small.vapor_moles_lbmol < large.vapor_moles_lbmol)


def test_rejects_inconsistent_liquid_inventory_composition():
    with pytest.raises(ValueError, match="inventory composition disagrees"):
        evaluate_vapor_holdup_properties(
            _geometry(),
            [[18.0, 2.0], [12.0, 18.0]],
            [[0.7, 0.3], [0.4, 0.6]],
            [[0.8, 0.2], [0.5, 0.5]],
            [100.0, 150.0],
            [200.0, 220.0],
            _Provider(),
            ProviderCallAudit(),
            state_id="bad-x",
        )


def test_rejects_non_normalized_vapor_composition():
    with pytest.raises(ValueError, match="rows must sum to one"):
        _evaluate(vapor_y=[[0.8, 0.3], [0.5, 0.5]])


def test_rejects_overfilled_volume():
    with pytest.raises(ValueError, match="overfills vapor control volume"):
        _evaluate(capacity=10.0)


def test_rejects_non_governing_evaluation_kind():
    with pytest.raises(ValueError, match="residual/Jacobian only"):
        evaluate_vapor_holdup_properties(
            _geometry(),
            [[14.0, 6.0], [12.0, 18.0]],
            [[0.7, 0.3], [0.4, 0.6]],
            [[0.8, 0.2], [0.5, 0.5]],
            [100.0, 150.0],
            [200.0, 220.0],
            _Provider(),
            ProviderCallAudit(),
            state_id="diagnostic",
            evaluation_kind="diagnostic",
        )


def test_property_gate_rejects_fallback_marker():
    result, audit = _evaluate()
    audit.fallback_attempted = True

    gate = audit_vapor_holdup_properties(result, audit)

    assert not gate.pass_gate
    assert gate.provider_fallback_attempted


def test_trial_properties_preserve_supplied_vapor_inventory_and_report_eos_error():
    inventory = np.asarray([[14.0, 6.0], [12.0, 18.0]])
    vapor_inventory = np.asarray([[1.6, 0.4], [2.5, 2.5]])
    audit = ProviderCallAudit()

    result = evaluate_vapor_holdup_trial_properties(
        _geometry(),
        inventory,
        vapor_inventory,
        [100.0, 150.0],
        [200.0, 220.0],
        _Provider(),
        audit,
        state_id="trial",
    )

    assert np.array_equal(result.vapor_component_inventory_lbmol, vapor_inventory)
    assert np.allclose(result.vapor_moles_lbmol, [2.0, 5.0])
    assert np.any(np.abs(result.eos_volume_residual_ft3) > 1.0e-6)
    assert np.allclose(
        result.total_stored_energy_BTU,
        result.liquid_stored_energy_BTU + result.vapor_stored_energy_BTU,
    )
