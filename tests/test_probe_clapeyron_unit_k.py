from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from tools.probe_clapeyron_unit_k import (
    _flash_k_diagnostic,
    _flash_k_diagnostic_batch,
)


class _DiagnosticProvider:
    def flash_TP_K_diagnostic_F_psia(self, T_F, P_psia, z):
        _ = (T_F, P_psia, z)
        return SimpleNamespace(
            K=np.array([1.38, 0.59, 0.25], dtype=float),
            Z=0.84,
            phase_count=1,
            phase_slot_count=2,
            k_source="clapeyron-inactive-flash-estimate",
            k_is_equilibrium=False,
            inactive_phase_used=True,
        )

    def flash_TP_K_diagnostic_batch_F_psia(self, T_rows, P_rows, z_rows):
        return [
            self.flash_TP_K_diagnostic_F_psia(T_F, P_psia, z)
            for T_F, P_psia, z in zip(T_rows, P_rows, z_rows)
        ]


def test_probe_maps_inactive_k_diagnostic_metadata():
    provider = _DiagnosticProvider()
    z = np.array([0.54, 0.42, 0.04], dtype=float)

    scalar = _flash_k_diagnostic(provider, 133.0, 232.0, z)
    batch = _flash_k_diagnostic_batch(
        provider,
        [{"T_F": 133.0, "P_psia": 232.0, "z": z.tolist()}],
    )

    assert np.allclose(scalar["K"], [1.38, 0.59, 0.25])
    assert scalar["phase_count"] == 1.0
    assert scalar["phase_slot_count"] == 2.0
    assert scalar["k_source"] == "clapeyron-inactive-flash-estimate"
    assert scalar["k_is_equilibrium"] == 0.0
    assert scalar["inactive_phase_used"] == 1.0
    assert len(batch) == 1
    assert np.array_equal(batch[0]["K"], scalar["K"])
