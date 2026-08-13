from types import SimpleNamespace

import numpy as np
import pytest

import dynamic_distillation.core_v3.terminal_inventory_control_bdf2_residual_v1 as residual
from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    build_column_topology,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_kinematics_v1 import (
    build_controlled_bdf2_history,
)
from dynamic_distillation.core_v3.terminal_inventory_control_contract_v1 import (
    TerminalPIParameters,
    TerminalVesselGeometry,
    build_terminal_inventory_control_contract,
)


def _contract():
    topology = build_column_topology(
        rectifying_volume_count=1,
        stripping_volume_count=1,
    )
    base = build_dynamic_dae_contract(
        ("a", "b", "c"),
        topology=topology,
        accepted_root_artifact="accepted.json",
        product_flow_parameters=("D", "B"),
    )
    return build_terminal_inventory_control_contract(
        base,
        geometry=TerminalVesselGeometry(
            12.0, 36.0, "two_hemispherical", 18.0, 12.0
        ),
        controllers=TerminalPIParameters(0.5, 120.0, 8.0, 120.0, (0.25, 2.0)),
    )


def _fixture(monkeypatch):
    contract = _contract()
    volumes = contract.base.topology.volume_ids
    components = contract.base.component_names
    inventory = np.arange(1, len(volumes) * len(components) + 1, dtype=float).reshape(
        len(volumes), len(components)
    )
    energy = np.linspace(-5.0e7, -1.0e7, len(volumes))
    history = build_controlled_bdf2_history(
        step_seconds=0.125,
        current_inventory_lbmol=inventory,
        prior_inventory_lbmol=inventory,
        current_internal_energy_BTU=energy,
        prior_internal_energy_BTU=energy,
        current_controller_memory=(0.0, 0.0),
        prior_controller_memory=(0.0, 0.0),
    )
    point = np.zeros(len(contract.rows))
    base_rate_count = len(contract.base.derivative_variables)
    algebraic_count = len(contract.base.algebraic_variables)
    point[base_rate_count + 2 : base_rate_count + 2 + algebraic_count] = 0.25
    captured = {}
    base_scales = np.ones(len(contract.base.rows))
    base_raw = np.zeros(len(contract.base.rows))

    def fake_control(*args, **kwargs):
        captured.update(kwargs)
        base = SimpleNamespace(
            raw=base_raw.copy(),
            scales=base_scales.copy(),
        )
        return SimpleNamespace(
            raw=np.zeros(len(contract.rows)),
            row_names=tuple(row.name for row in contract.rows),
            variable_names=tuple(f"v{index}" for index in range(len(contract.rows))),
            base=base,
            level_fraction=np.asarray([0.5, 0.5]),
            level_error=np.zeros(2),
            distillate_lbmolph=10.0,
            bottoms_lbmolph=20.0,
        )

    monkeypatch.setattr(residual, "evaluate_terminal_inventory_control_residual", fake_control)
    monkeypatch.setattr(
        residual,
        "governing_storage_vector",
        lambda spec, base, endpoint: energy.copy(),
    )
    spec = SimpleNamespace(topology=contract.base.topology, component_names=components)
    return contract, spec, history, point, captured


def test_dd196_property_free_stationary_residual_is_exact(monkeypatch):
    contract, spec, history, point, captured = _fixture(monkeypatch)
    audit = ProviderCallAudit()
    result = residual.evaluate_terminal_inventory_control_bdf2_residual(
        contract,
        spec,
        SimpleNamespace(),
        SimpleNamespace(),
        object(),
        audit,
        history=history,
        level_setpoints=SimpleNamespace(),
        rate_scales_lbmolph=np.ones_like(history.current_inventory_lbmol),
        solve_coordinates=point,
        step_seconds=0.125,
        fixed_steady_scales=np.ones(len(contract.base.rows)),
        product_reference_lbmolph=(10.0, 20.0),
        state_id="dd196_stationary",
        evaluation_kind="residual",
    )

    assert np.array_equal(result.raw, np.zeros(len(contract.rows)))
    assert np.array_equal(result.scaled, np.zeros(len(contract.rows)))
    assert np.array_equal(
        result.kinematics.endpoint_inventory_lbmol,
        history.current_inventory_lbmol,
    )
    assert np.count_nonzero(result.kinematics.component_rate_lbmolph) == 0
    assert np.count_nonzero(result.kinematics.energy_storage_rate_BTUph) == 0
    assert np.count_nonzero(result.kinematics.controller_rate_per_sec) == 0
    assert np.array_equal(
        captured["inventory_lbmol"], history.current_inventory_lbmol
    )
    assert audit.record_count == 0


def test_dd196_residual_passes_effective_bdf2_rates_not_nominal_coordinates(monkeypatch):
    contract, spec, history, point, captured = _fixture(monkeypatch)
    base_rate_count = len(contract.base.derivative_variables)
    point[:base_rate_count] = 0.2
    scales = np.full_like(history.current_inventory_lbmol, 10.0)
    result = residual.evaluate_terminal_inventory_control_bdf2_residual(
        contract,
        spec,
        SimpleNamespace(),
        SimpleNamespace(),
        object(),
        ProviderCallAudit(),
        history=history,
        level_setpoints=SimpleNamespace(),
        rate_scales_lbmolph=scales,
        solve_coordinates=point,
        step_seconds=0.125,
        fixed_steady_scales=np.ones(len(contract.base.rows)),
        state_id="dd196_effective",
        evaluation_kind="residual",
    )

    effective = captured["solve_coordinates"][:base_rate_count].reshape(scales.shape)
    assert np.allclose(effective, result.kinematics.component_rate_coordinates)
    assert not np.array_equal(effective, point[:base_rate_count].reshape(scales.shape))


def test_dd196_residual_rejects_history_with_wrong_topology(monkeypatch):
    contract, spec, history, point, _captured = _fixture(monkeypatch)
    bad = build_controlled_bdf2_history(
        step_seconds=0.125,
        current_inventory_lbmol=np.ones((4, 3)),
        prior_inventory_lbmol=np.ones((4, 3)),
        current_internal_energy_BTU=np.ones(4),
        prior_internal_energy_BTU=np.ones(4),
        current_controller_memory=(0.0, 0.0),
        prior_controller_memory=(0.0, 0.0),
    )

    with pytest.raises(ValueError, match="topology"):
        residual.evaluate_terminal_inventory_control_bdf2_residual(
            contract,
            spec,
            SimpleNamespace(),
            SimpleNamespace(),
            object(),
            ProviderCallAudit(),
            history=bad,
            level_setpoints=SimpleNamespace(),
            rate_scales_lbmolph=np.ones((5, 3)),
            solve_coordinates=point,
            step_seconds=0.125,
            fixed_steady_scales=np.ones(len(contract.base.rows)),
            state_id="dd196_bad",
            evaluation_kind="residual",
        )


def test_dd198_bdf2_solver_rejects_bad_initial_coordinates(monkeypatch):
    contract, spec, history, point, _captured = _fixture(monkeypatch)

    with pytest.raises(ValueError, match="initial coordinates"):
        residual.solve_terminal_inventory_control_bdf2_step(
            contract,
            spec,
            SimpleNamespace(),
            SimpleNamespace(),
            object(),
            ProviderCallAudit(),
            history=history,
            level_setpoints=SimpleNamespace(),
            rate_scales_lbmolph=np.ones_like(history.current_inventory_lbmol),
            initial_solve_coordinates=point[:-1],
            step_seconds=0.125,
            fixed_steady_scales=np.ones(len(contract.base.rows)),
            settings=SimpleNamespace(
                jacobian_step=1.0e-5,
                method="trf",
                ftol=1.0e-12,
                xtol=1.0e-12,
                gtol=1.0e-12,
                max_nfev=10,
                x_scale=1.0,
            ),
            name="dd198_bad",
        )
