from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import audit_core_v3_aligned_pr_density_parity as dd229


class _Provider:
    def phase_fugacity_coefficients(self, *args, **kwargs):
        return "fugacity"

    def phase_enthalpy_BTU_lbmol(self, *args, **kwargs):
        return 12.0

    def liquid_density_lbmol_ft3(self, *args, **kwargs):
        return 1.0


class _Density:
    def liquid_density_lbmol_ft3(self, *args, **kwargs):
        return 2.0


def test_dd229_provider_routes_only_density():
    provider = dd229.DensityRoutedProvider(_Provider(), _Density())

    assert provider.phase_fugacity_coefficients() == "fugacity"
    assert provider.phase_enthalpy_BTU_lbmol() == 12.0
    assert provider.liquid_density_lbmol_ft3(100.0, 200.0, [0.5, 0.5]) == 2.0


def test_dd229_contract_freezes_explicit_property_routing_without_live_work(tmp_path):
    contract = dd229.prepare(tmp_path / "dd229_contract.json")

    assert contract["provider_routing"]["direct_imposed_phase_fugacity"] == "dwsim"
    assert contract["provider_routing"]["declared_phase_enthalpy"] == "dwsim"
    assert contract["provider_routing"]["declared_liquid_density"] == "aligned_pr_smallest_positive_root"
    assert contract["provider_calls_during_preparation"] == 0
    assert not contract["nonlinear_solve_attempted"]
    assert not contract["state_changed"]
    assert not contract["timestep_attempted"]
