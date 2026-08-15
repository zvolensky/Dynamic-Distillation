from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "adjudicate_core_v3_bdf2_300s_controlled_response_jsonfix.py"


def _module():
    spec = importlib.util.spec_from_file_location("dd220_tool", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_json_native_recursively_converts_numpy_scalars():
    converted = _module()._json_native(
        {
            "flag": np.bool_(True),
            "integer": np.int64(3),
            "floating": np.float64(1.5),
            "nested": (np.bool_(False),),
        }
    )

    assert converted == {
        "flag": True,
        "integer": 3,
        "floating": 1.5,
        "nested": [False],
    }
    json.dumps(converted)
