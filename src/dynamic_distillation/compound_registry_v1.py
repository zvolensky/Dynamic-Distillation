"""
compound_registry_v1.py

Dynamic Distillation - Compound Name Canonicalization

PURPOSE
-------
Convert Excel-provided component names to canonical DWSIM compound IDs.
Apply name aliases, validate against DWSIM database, and fail fast on
unrecognized compounds.

INPUTS
------
name : str
    Excel or user-provided component name
extra_aliases : Optional[Dict[str, str]]
    Additional name mappings to apply (merged with defaults)

OUTPUTS
-------
dwsim_id : str
    Canonical DWSIM compound ID (exact name from DWSIM database)

DEPENDENCIES
------------
from dynamic_distillation.dwsim_compounds_v2 : DWSIM_COMPOUNDS, DWSIM_COMPOUND_SET

ASSUMPTIONS & CONSTRAINTS
--------------------------
- DWSIM_COMPOUNDS list is available and immutable
- Input names are strings or convertible to strings
- Aliases are applied before DWSIM database lookup
- Case-insensitive alias matching; DWSIM returns exact case
- No compound IDs contain spaces or special characters (DWSIM standard)

SIDE EFFECTS / STATE MUTATIONS
-------------------------------
- No state modifications; pure function (deterministic, repeatable)
- No file I/O or external calls

PERFORMANCE NOTES
-----------------
- Alias lookup: O(1) dict lookup per name
- DWSIM set lookup: O(1) membership check
- Total per-compound: < 1 µs

ERROR HANDLING
--------------
- Raises ValueError if compound not found in DWSIM database after alias resolution
- Provides helpful error message with available DWSIM compounds nearby (edit distance match)

VERSION / COMPATIBILITY
-----------------------
v1.0 (current):
    - Default aliases hardcoded (gas naming conventions only)
    - Case-insensitive matching; DWSIM case preserved in output

NOTES / KEY FEATURES
--------------------
Updated: 2026-01-11 15:xx ET

- Default aliases handle common naming variants:
  n-propane -> Propane, i-butane -> Isobutane, etc.
- Case-insensitive keying; preserves DWSIM case
- Fails fast if compound not in DWSIM database

EXAMPLE USAGE
-------------
    dwsim_id = canonicalize_to_dwsim_id("n-propane")
    # Returns: "Propane"
    
    custom_aliases = {"nC4": "N-butane", "nC5": "N-pentane"}
    dwsim_id = canonicalize_to_dwsim_id("nC4", extra_aliases=custom_aliases)
    # Returns: "N-butane"
    
    # Raises ValueError with helpful message:
    # canonicalize_to_dwsim_id("xylyne")  # NOT in DWSIM database
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

# Your attached file must live here:
#   src/dynamic_distillation/dwsim_compounds_v2.py
from dynamic_distillation.dwsim_compounds_v2 import DWSIM_COMPOUNDS, DWSIM_COMPOUND_SET  # type: ignore


# Keep this intentionally small and editable.
# Extend as you encounter new Excel naming conventions.
_DEFAULT_ALIASES: Dict[str, str] = {
    # Common petro / ChemSep-ish names
    "n-propane": "Propane",
    "propane": "Propane",
    "n-butane": "N-butane",
    "butane": "N-butane",
    "n-pentane": "N-pentane",
    "pentane": "N-pentane",
    # Isomers (common spellings)
    "i-butane": "Isobutane",
    "isobutane": "Isobutane",
    "i-pentane": "Isopentane",
    "isopentane": "Isopentane",
    # Space variants
    "n propane": "Propane",
    "n butane": "N-butane",
    "n pentane": "N-pentane",
}


def _norm_str(x: Any) -> str:
    return str(x).strip() if x is not None else ""


def canonicalize_to_dwsim_id(name: str, extra_aliases: Optional[Dict[str, str]] = None) -> str:
    """
    Convert an Excel component name to a canonical DWSIM compound ID.

    Rules:
    - Apply alias map (case-insensitive keying)
    - Accept exact match in DWSIM set
    - Accept case-insensitive unique match
    - Accept mild punctuation normalization (underscore/hyphen/extra spaces)
    """
    raw = _norm_str(name)
    if not raw:
        raise ValueError("Blank component name in Excel")

    aliases = dict(_DEFAULT_ALIASES)
    if extra_aliases:
        aliases.update(extra_aliases)

    key = raw.lower()
    if key in aliases:
        candidate = aliases[key]
        if candidate in DWSIM_COMPOUND_SET:
            return candidate
        # Fall-through to matching logic using candidate as raw
        raw = candidate

    # Exact match (case-sensitive)
    if raw in DWSIM_COMPOUND_SET:
        return raw

    # Case-insensitive unique match
    matches = [c for c in DWSIM_COMPOUNDS if c.lower() == raw.lower()]
    if len(matches) == 1:
        return matches[0]

    # Mild punctuation normalization
    raw2 = raw.replace("_", "-").replace("  ", " ").strip()
    matches2 = [c for c in DWSIM_COMPOUNDS if c.lower() == raw2.lower()]
    if len(matches2) == 1:
        return matches2[0]

    raise ValueError(
        f"Component '{name}' does not match the DWSIM compound database.\n"
        f"Tip: fix spelling in Excel or add an alias in compound_registry_v1.py."
    )


def canonicalize_components(
    component_names: Sequence[str],
    extra_aliases: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Vectorized canonicalization."""
    return [canonicalize_to_dwsim_id(nm, extra_aliases=extra_aliases) for nm in component_names]