import numpy as np
import pytest

from dynamic_distillation.core_v3.provider_call_audit_v1 import (
    ProviderCallAudit,
)


class _Provider:
    def phase_fugacity_coefficients(self, phase, temperature_F, pressure_psia, composition):
        return np.ones(len(composition), dtype=float)

    def phase_enthalpy_BTU_lbmol(self, phase, temperature_F, pressure_psia, composition):
        return float(temperature_F)

    def liquid_density_lbmol_ft3(self, temperature_F, pressure_psia, composition):
        return 2.0

    def vapor_z_factor_F_psia(self, temperature_F, pressure_psia, composition):
        return 0.8

    def component_mw_lbm_per_lbmol(self):
        return np.asarray([44.0, 58.0, 72.0])

    def flash_TP_full_F_psia(self, temperature_F, pressure_psia, composition):
        z = np.asarray(composition, dtype=float)
        return z, z, np.ones_like(z), 0.0, 0.0


def test_dd092_provider_audit_records_all_required_provenance_fields():
    audit = ProviderCallAudit()
    provider = _Provider()

    audit.phase_enthalpy(
        provider,
        phase="liquid",
        temperature_F=120.0,
        pressure_psia=200.0,
        composition=[0.7, 0.2, 0.1],
        caller="energy_balance[feed_tray]",
        state_id="canonical",
        evaluation_kind="residual",
    )
    report = audit.report()

    assert report["pass"]
    assert report["total_calls"] == 1
    assert report["grouped_records"][0] == {
        "quantity": "phase_enthalpy",
        "provider_interface": "dwsim.declared_phase_enthalpy",
        "caller": "energy_balance[feed_tray]",
        "state_id": "canonical",
        "evaluation_kind": "residual",
        "count": 1,
    }


def test_dd092_tp_flash_is_rejected_in_residual_or_jacobian_evaluation():
    audit = ProviderCallAudit()
    provider = _Provider()

    for kind in ("residual", "jacobian"):
        with pytest.raises(RuntimeError, match="diagnostic-only"):
            audit.tp_flash(
                provider,
                temperature_F=120.0,
                pressure_psia=200.0,
                overall_composition=[0.7, 0.2, 0.1],
                caller="bad_governing_row",
                state_id="canonical",
                evaluation_kind=kind,
            )

    assert audit.records == ()


def test_dd092_independent_pr_is_rejected_outside_validation():
    audit = ProviderCallAudit()
    provider = _Provider()

    with pytest.raises(RuntimeError, match="validation-only"):
        audit.independent_phase_fugacity(
            provider,
            phase="liquid",
            temperature_F=120.0,
            pressure_psia=200.0,
            composition=[0.7, 0.2, 0.1],
            caller="bad_production_row",
            state_id="canonical",
            evaluation_kind="residual",
        )

    assert audit.records == ()


def test_dd092_diagnostic_flash_is_recorded_without_cross_interface_gate():
    audit = ProviderCallAudit()
    provider = _Provider()

    x, y, K = audit.tp_flash(
        provider,
        temperature_F=120.0,
        pressure_psia=200.0,
        overall_composition=[0.7, 0.2, 0.1],
        caller="condenser_phase_diagnostic",
        state_id="canonical",
        evaluation_kind="diagnostic",
    )

    assert np.allclose(x, [0.7, 0.2, 0.1])
    assert np.allclose(y, x)
    assert np.allclose(K, 1.0)
    assert audit.report()["pass"]


def test_dd102_direct_vapor_z_is_governing_and_audited():
    audit = ProviderCallAudit()
    value = audit.vapor_compressibility_factor(
        _Provider(),
        temperature_F=180.0,
        pressure_psia=225.0,
        composition=[0.6, 0.3, 0.1],
        caller="vapor_pressure_drop[feed->rectifying]",
        state_id="pressure_probe",
        evaluation_kind="jacobian",
    )

    assert value == 0.8
    assert audit.report()["pass"]
    assert audit.records[0].provider_interface == (
        "dwsim.declared_vapor_compressibility_factor"
    )


def test_dd102_component_molecular_weights_are_preparation_only():
    audit = ProviderCallAudit()
    values = audit.component_molecular_weights(
        _Provider(),
        caller="pressure_layer_fixed_parameters",
        state_id="dd102",
        evaluation_kind="preparation",
    )

    assert np.allclose(values, [44.0, 58.0, 72.0])
    with pytest.raises(RuntimeError, match="preparation-only"):
        audit.component_molecular_weights(
            _Provider(),
            caller="bad_governing_row",
            state_id="dd102",
            evaluation_kind="residual",
        )
