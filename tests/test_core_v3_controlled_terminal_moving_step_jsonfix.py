import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_controlled_terminal_moving_step_jsonfix as dd130


def test_dd130_numpy_boolean_result_is_json_serializable():
    result = {
        "gates": {
            "controller_direction": np.bool_(True),
            "nested": [np.bool_(False), {"pass": np.bool_(True)}],
        }
    }

    native = dd130.native_json_booleans(result)

    assert type(native["gates"]["controller_direction"]) is bool
    assert type(native["gates"]["nested"][0]) is bool
    assert type(native["gates"]["nested"][1]["pass"]) is bool
    json.dumps(native)


def test_dd130_json_proxy_serializes_complete_gate_fixture():
    fixture = {
        "classification": "fixture",
        "movement_signal": {"direction": np.bool_(True)},
        "gates": {
            "solver_success": True,
            "controller_direction": np.bool_(True),
            "physical": np.bool_(True),
        },
        "pass": np.bool_(True),
    }

    encoded = dd130._BooleanSafeJSON.dumps(fixture, indent=2)
    decoded = json.loads(encoded)

    assert decoded["gates"]["controller_direction"] is True
    assert decoded["pass"] is True


def test_dd130_scientific_projection_excludes_only_governance_fields():
    payload = {
        "schema_id": "successor",
        "sources": {"a": "b"},
        "solver": {"method": "trf"},
        "moved_level_setpoints": {"drum_fraction": 0.5},
        "residual_limit": 1.0e-8,
        "contract_payload_sha256": "hash",
    }

    projection = dd130.scientific_contract_projection(payload)

    assert projection == {
        "solver": {"method": "trf"},
        "moved_level_setpoints": {"drum_fraction": 0.5},
        "residual_limit": 1.0e-8,
    }
