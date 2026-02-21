"""
test_compound_registry_v1.py

Dynamic Distillation - Compound Registry Tests

PURPOSE
-------
Confirm alias-to-canonical mapping behavior and error reporting for unknown
compound names in `compound_registry_v1`.

SCOPE
-----
- known alias canonicalization
- clean failure path for unmapped compounds

KEY DEPENDENCIES
----------------
- pytest
- dynamic_distillation.compound_registry_v1
"""


import pytest

from dynamic_distillation.compound_registry_v1 import canonicalize_to_dwsim_id


def test_alias_npropane_maps_to_propane():
    assert canonicalize_to_dwsim_id("n-Propane") == "Propane"


def test_unknown_compound_raises_clean_error():
    with pytest.raises(ValueError) as excinfo:
        canonicalize_to_dwsim_id("DefinitelyNotARealCompound123")
    msg = str(excinfo.value)
    assert "does not match the DWSIM compound database" in msg
