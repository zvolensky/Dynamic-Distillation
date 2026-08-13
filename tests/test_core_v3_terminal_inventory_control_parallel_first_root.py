from copy import deepcopy
import json
from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_seven_volume_terminal_inventory_control_parallel_first_root as dd191  # noqa: E402


def _source():
    return json.loads((ROOT / dd191.DD190_RESULT).read_text(encoding="utf-8"))


def test_dd191_accepts_preserved_dd190_stop_pattern():
    dd191._validate_source(_source())


def test_dd191_rejects_an_additional_dd190_campaign_failure():
    source = deepcopy(_source())
    source["campaign_gates"]["provider"] = False
    with pytest.raises(RuntimeError, match="failure pattern"):
        dd191._validate_source(source)


def test_dd191_controlled_outcome_comparison_includes_controller_state():
    evaluation = type("Evaluation", (), {})()
    evaluation.endpoint_inventory_lbmol = np.ones((2, 2))
    evaluation.component_rate_lbmolph = np.zeros((2, 2))
    evaluation.algebraic_coordinates = np.zeros(2)
    evaluation.endpoint_controller_memory = np.zeros(2)
    evaluation.level_fraction = np.asarray((0.4, 0.5))
    evaluation.product_log_ratio = np.zeros(2)
    evaluation.distillate_lbmolph = 10.0
    evaluation.bottoms_lbmolph = 20.0
    evaluation.endpoint_internal_energy_BTU = np.ones(2)
    outcome = type("Outcome", (), {})()
    outcome.evaluation = evaluation
    outcome.success = True
    outcome.status = 1
    outcome.message = "ok"
    outcome.nfev = 2
    outcome.njev = 2
    outcome.cost = 0.0
    outcome.optimality = 0.0
    outcome.initial_coordinates = np.zeros(2)
    outcome.final_coordinates = np.zeros(2)
    outcome.final_residual = np.zeros(2)
    outcome.final_jacobian = np.eye(2)

    with pytest.raises(TypeError, match="controlled evaluations"):
        dd191._outcome_comparison(outcome, outcome)
