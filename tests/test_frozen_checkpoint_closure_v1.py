from types import SimpleNamespace

import numpy as np

from dynamic_distillation.frozen_checkpoint_closure_v1 import (
    checkpoint_phase_state_to_conserved_totals,
    classify_frozen_closure,
)
from dynamic_distillation.uv_flash_stage_v1 import BTU_PER_PSI_FT3


def test_checkpoint_phase_state_to_conserved_totals_sums_phases_and_converts_h_to_u():
    unpacked = {
        "tray_L": np.asarray([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]),
        "tray_V": np.asarray([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]),
        "tray_EL_BTU": np.asarray([100.0, 200.0, 300.0]),
        "tray_EV_BTU": np.asarray([10.0, 20.0, 30.0]),
    }
    totals, internal = checkpoint_phase_state_to_conserved_totals(
        unpacked=unpacked,
        active_stage0=[1],
        pressure_psia=[10.0, 20.0, 30.0],
        fixed_total_volume_ft3=[5.0],
    )
    assert np.allclose(totals, [[3.3, 4.4]])
    assert np.allclose(internal, [220.0 - 20.0 * 5.0 * BTU_PER_PSI_FT3])


def test_classification_separates_local_failure_from_global_failure():
    bridge = SimpleNamespace(terminal_mapping_complete=False)
    local_bad = SimpleNamespace(
        converged=False,
        component_relative_max=0.0,
        energy_relative_max=0.0,
        volume_relative_max=0.0,
        equilibrium_beta_max=0.0,
        negative_phase_count=0,
        projection_count=0,
    )
    assert (
        classify_frozen_closure(bridge=bridge, local=local_bad, hydraulic=None)
        == "local_uv_failed"
    )

    local_good = SimpleNamespace(
        converged=True,
        component_relative_max=1.0e-10,
        energy_relative_max=1.0e-10,
        volume_relative_max=1.0e-10,
        equilibrium_beta_max=1.0e-10,
        negative_phase_count=0,
        projection_count=0,
    )
    hydraulic_bad = SimpleNamespace(strict_gate_pass=False)
    assert (
        classify_frozen_closure(
            bridge=bridge,
            local=local_good,
            hydraulic=hydraulic_bad,
        )
        == "local_uv_passed_global_hydraulics_failed_or_unverified"
    )
