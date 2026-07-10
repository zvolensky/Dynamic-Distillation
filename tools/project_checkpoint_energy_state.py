#!/usr/bin/env python
"""
Project a native checkpoint energy state onto its restored thermo enthalpy basis.

The tool keeps material, temperature, boundary, controller, and runtime memory
unchanged. It only rewrites tray_EL_BTU and tray_EV_BTU in the packed final_state
using:

    EL = ML * HL
    EV = MV * HV

where ML/MV come from the packed material state and HL/HV come from native
checkpoint memory restored by load_native_checkpoint_initial_state.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _PROJECT_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case  # noqa: E402
from dynamic_distillation.dynamic_run_scaffold_v1 import (  # noqa: E402
    load_native_checkpoint_initial_state,
    read_native_checkpoint,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel  # noqa: E402
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout  # noqa: E402


def _resolve_path(raw: str | Path) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (_PROJECT_ROOT / p).resolve()


def _timestamp_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _json_default(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _energy_projection(
    *,
    y: np.ndarray,
    layout: StateVectorLayout,
    memory: Dict[str, Any],
) -> tuple[np.ndarray, Dict[str, Any]]:
    sl = layout.slices()
    if "tray_EL_BTU" not in sl or "tray_EV_BTU" not in sl:
        raise ValueError("Current layout must include tray_EL_BTU and tray_EV_BTU.")
    if "last_HL" not in memory or "last_HV" not in memory:
        raise ValueError("Checkpoint memory must include last_HL and last_HV.")

    n_stages = int(layout.n_stages)
    tray_L = np.asarray(y[sl["tray_L"]], dtype=float).reshape((n_stages, int(layout.n_components)))
    tray_V = np.asarray(y[sl["tray_V"]], dtype=float).reshape((n_stages, int(layout.n_components)))
    ml = np.sum(tray_L, axis=1)
    mv = np.sum(tray_V, axis=1)
    hl = np.asarray(memory["last_HL"], dtype=float).reshape((n_stages,))
    hv = np.asarray(memory["last_HV"], dtype=float).reshape((n_stages,))

    y_new = np.asarray(y, dtype=float).reshape((-1,)).copy()
    old_el = np.asarray(y_new[sl["tray_EL_BTU"]], dtype=float).reshape((n_stages,)).copy()
    old_ev = np.asarray(y_new[sl["tray_EV_BTU"]], dtype=float).reshape((n_stages,)).copy()
    new_el = ml * hl
    new_ev = mv * hv
    y_new[sl["tray_EL_BTU"]] = new_el.reshape((-1,))
    y_new[sl["tray_EV_BTU"]] = new_ev.reshape((-1,))

    info = {
        "max_abs_delta_EL_BTU": float(np.max(np.abs(new_el - old_el))) if n_stages else 0.0,
        "max_abs_delta_EV_BTU": float(np.max(np.abs(new_ev - old_ev))) if n_stages else 0.0,
        "rms_delta_EL_BTU": float(np.sqrt(np.mean(np.square(new_el - old_el)))) if n_stages else 0.0,
        "rms_delta_EV_BTU": float(np.sqrt(np.mean(np.square(new_ev - old_ev)))) if n_stages else 0.0,
        "projected_blocks": ["tray_EL_BTU", "tray_EV_BTU"],
    }
    return y_new, info


def main() -> int:
    ap = argparse.ArgumentParser(description="Project native checkpoint tray energy states onto checkpoint HL/HV.")
    ap.add_argument("--excel", required=True, help="Excel workbook defining the case/layout.")
    ap.add_argument("--checkpoint", required=True, help="Input native .npz checkpoint.")
    ap.add_argument("--output", required=True, help="Output native .npz checkpoint.")
    ap.add_argument("--include-temperature", dest="include_temperature", action="store_true")
    ap.add_argument("--no-temperature", dest="include_temperature", action="store_false")
    ap.set_defaults(include_temperature=True)
    args = ap.parse_args()

    excel_path = _resolve_path(args.excel)
    checkpoint_path = _resolve_path(args.checkpoint)
    output_path = _resolve_path(args.output)
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel case file not found: {excel_path}")
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Native checkpoint file not found: {checkpoint_path}")

    case = load_case_from_excel(str(excel_path))
    col = build_column_spec_from_case(case)
    layout = StateVectorLayout(
        n_stages=int(col.n_stages),
        n_components=int(col.n_components),
        include_top=True,
        include_bottom=True,
        include_vapor=True,
        include_temperature=bool(args.include_temperature),
        include_energy=True,
    )
    y, info, memory = load_native_checkpoint_initial_state(path=checkpoint_path, layout=layout, col=col)
    y_projected, projection_info = _energy_projection(y=y, layout=layout, memory=memory)

    checkpoint = read_native_checkpoint(checkpoint_path)
    metadata = dict(checkpoint.get("metadata") or {})
    arrays = dict(checkpoint.get("arrays") or {})
    arrays["final_state"] = y_projected.copy()
    metadata["energy_state_projection"] = {
        "schema": "dynamic_distillation.energy_state_projection.v1",
        "source_checkpoint": str(checkpoint_path),
        "created_at": _timestamp_tag(),
        "checkpoint_source_run_id": info.get("source_run_id", ""),
        **projection_info,
    }
    metadata["array_keys"] = sorted(arrays.keys())
    arrays["metadata_json"] = np.asarray(json.dumps(metadata, indent=2, sort_keys=True, default=_json_default))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_path, **arrays)

    print("Projected checkpoint energy state")
    print(f"Input: {checkpoint_path}")
    print(f"Output: {output_path}")
    print(f"Max |delta EL|: {projection_info['max_abs_delta_EL_BTU']:.8g} BTU")
    print(f"Max |delta EV|: {projection_info['max_abs_delta_EV_BTU']:.8g} BTU")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
