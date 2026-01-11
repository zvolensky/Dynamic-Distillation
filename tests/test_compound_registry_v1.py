# test_compound_registry_v1.py
# Last updated: 2026-01-11 15:xx ET

import pytest

from dynamic_distillation.compound_registry_v1 import canonicalize_to_dwsim_id


def test_alias_npropane_maps_to_propane():
    assert canonicalize_to_dwsim_id("n-Propane") == "Propane"


def test_unknown_compound_raises_clean_error():
    with pytest.raises(ValueError) as excinfo:
        canonicalize_to_dwsim_id("DefinitelyNotARealCompound123")
    msg = str(excinfo.value)
    assert "does not match the DWSIM compound database" in msg
