from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import audit_core_v3_aligned_pr_liquid_density as dd228
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    IndependentPengRobinsonProvider,
    PengRobinsonParameters,
)


def _provider():
    return IndependentPengRobinsonProvider(
        PengRobinsonParameters(
            critical_temperature_K=np.asarray([369.83, 425.12, 469.7]),
            critical_pressure_Pa=np.asarray([4.248e6, 3.796e6, 3.37e6]),
            acentric_factor=np.asarray([0.152, 0.2, 0.251]),
            binary_interaction=np.zeros((3, 3)),
        )
    )


def test_aligned_pr_liquid_density_uses_smallest_physical_root():
    provider = _provider()
    roots = provider.phase_compressibility_roots(133.7, 218.44, [0.70, 0.28, 0.02])
    density = provider.liquid_density_lbmol_ft3(133.7, 218.44, [0.70, 0.28, 0.02])

    assert np.all(np.diff(roots) > 0.0)
    assert density > 0.0


def test_dd228_candidate_is_property_free_and_smooth_at_saved_states():
    report = dd228.run()

    assert report["pass_gate"]
    assert report["classification"] == "aligned_pr_liquid_density_feasible"
    assert report["dwsim_provider_calls"] == 0
    assert report["solver_calls"] == 0
    assert all(item["smooth"] for item in report["endpoints"].values())
