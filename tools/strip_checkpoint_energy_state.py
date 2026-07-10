#!/usr/bin/env python
"""
Strip tray energy-state blocks from a native checkpoint.

This creates a layout-compatible checkpoint for runs that use tray temperature
states without B1 tray energy inventory states. It preserves all non-energy
packed state blocks and leaves checkpoint diagnostic/memory arrays in place.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path
import sys
from typing import Any, Dict

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _PROJECT_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from dynamic_distillation.dynamic_run_scaffold_v1 import read_native_checkpoint  # noqa: E402
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


def _layout_from_doc(doc: Dict[str, Any]) -> StateVectorLayout:
    return StateVectorLayout(
        n_stages=int(doc["n_stages"]),
        n_components=int(doc["n_components"]),
        include_top=bool(doc.get("include_top", True)),
        include_bottom=bool(doc.get("include_bottom", True)),
        include_vapor=bool(doc.get("include_vapor", True)),
        include_temperature=bool(doc.get("include_temperature", False)),
        include_energy=bool(doc.get("include_energy", False)),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Create a no-energy-state native checkpoint from an energy checkpoint.")
    ap.add_argument("--checkpoint", required=True, help="Input native .npz checkpoint.")
    ap.add_argument("--output", required=True, help="Output native .npz checkpoint.")
    args = ap.parse_args()

    checkpoint_path = _resolve_path(args.checkpoint)
    output_path = _resolve_path(args.output)
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Native checkpoint file not found: {checkpoint_path}")

    checkpoint = read_native_checkpoint(checkpoint_path)
    metadata = dict(checkpoint.get("metadata") or {})
    arrays = dict(checkpoint.get("arrays") or {})
    layout_doc = metadata.get("layout") if isinstance(metadata.get("layout"), dict) else {}
    source_layout = _layout_from_doc(layout_doc)
    if not bool(source_layout.include_energy):
        raise ValueError("Input checkpoint layout does not include energy states.")
    target_layout = StateVectorLayout(
        n_stages=int(source_layout.n_stages),
        n_components=int(source_layout.n_components),
        include_top=bool(source_layout.include_top),
        include_bottom=bool(source_layout.include_bottom),
        include_vapor=bool(source_layout.include_vapor),
        include_temperature=bool(source_layout.include_temperature),
        include_energy=False,
    )

    y_source = np.asarray(arrays["final_state"], dtype=float).reshape((-1,))
    u_source = source_layout.unpack(y_source)
    y_target = np.zeros(target_layout.n_states(), dtype=float)
    src_sl = source_layout.slices()
    tgt_sl = target_layout.slices()
    copied_blocks = []
    for block, tgt_slice in tgt_sl.items():
        if block not in src_sl:
            raise ValueError(f"Source checkpoint missing block required by target layout: {block}")
        y_target[tgt_slice] = y_source[src_sl[block]]
        copied_blocks.append(block)

    arrays["final_state"] = y_target.copy()
    metadata["layout"] = {
        "n_stages": int(target_layout.n_stages),
        "n_components": int(target_layout.n_components),
        "include_top": bool(target_layout.include_top),
        "include_bottom": bool(target_layout.include_bottom),
        "include_vapor": bool(target_layout.include_vapor),
        "include_temperature": bool(target_layout.include_temperature),
        "include_energy": False,
    }
    metadata["energy_state_strip"] = {
        "schema": "dynamic_distillation.energy_state_strip.v1",
        "source_checkpoint": str(checkpoint_path),
        "created_at": _timestamp_tag(),
        "removed_blocks": ["tray_EL_BTU", "tray_EV_BTU"],
        "copied_blocks": copied_blocks,
        "source_state_length": int(y_source.size),
        "target_state_length": int(y_target.size),
        "source_total_liquid_lbmol": float(np.sum(u_source.get("tray_L", 0.0))),
        "source_total_vapor_lbmol": float(np.sum(u_source.get("tray_V", 0.0))),
    }
    metadata["array_keys"] = sorted(arrays.keys())
    arrays["metadata_json"] = np.asarray(json.dumps(metadata, indent=2, sort_keys=True, default=_json_default))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_path, **arrays)

    print("Stripped checkpoint energy states")
    print(f"Input: {checkpoint_path}")
    print(f"Output: {output_path}")
    print(f"State length: {y_source.size} -> {y_target.size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
