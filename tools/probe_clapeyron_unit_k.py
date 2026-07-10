#!/usr/bin/env python
"""
Probe Clapeyron TP flash behavior at logged runtime stage/time points.

The dynamic thermo refresh uses overall tray composition, not liquid x alone.
This tool reconstructs x, y, and z = (ML*x + MV*y)/(ML+MV) from a profile CSV
and compares fresh Clapeyron scalar and batch flash calls at quarantine-heavy
points.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_clapeyron_provider_v1 import ThermoClapeyronProviderV1
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _resolve(path: str | Path) -> Path:
    p = Path(str(path))
    if p.is_absolute():
        return p.resolve()
    return (PROJECT_ROOT / p).resolve()


def _finite_float(value: Any, default: float = math.nan) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def _read_csv(path: str | Path) -> List[Dict[str, str]]:
    with _resolve(path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _component_suffix(name: str) -> str:
    return str(name).strip().replace("-", "_").replace(" ", "_")


def _normalize(vals: Sequence[float]) -> np.ndarray:
    arr = np.asarray(vals, dtype=float).reshape((-1,))
    arr = np.where(np.isfinite(arr), arr, 0.0)
    arr = np.maximum(arr, 0.0)
    s = float(np.sum(arr))
    if s <= 0.0:
        return np.full(arr.size, 1.0 / max(arr.size, 1), dtype=float)
    return arr / s


def _is_unit_k(K: Sequence[float], *, atol: float = 1.0e-9) -> bool:
    arr = np.asarray(K, dtype=float).reshape((-1,))
    finite = arr[np.isfinite(arr)]
    return bool(finite.size and float(np.max(np.abs(finite - 1.0))) <= float(atol))


def _row_z(row: Dict[str, str], suffixes: Sequence[str]) -> np.ndarray:
    x = _normalize([_finite_float(row.get(f"x_{s}"), 0.0) for s in suffixes])
    y = _normalize([_finite_float(row.get(f"y_{s}"), 0.0) for s in suffixes])
    ML = max(_finite_float(row.get("ML_lbmol"), 0.0), 0.0)
    MV = max(_finite_float(row.get("MV_lbmol"), 0.0), 0.0)
    if ML + MV <= 0.0:
        return x
    return _normalize(ML * x + MV * y)


def _row_composition(row: Dict[str, str], suffixes: Sequence[str], basis: str) -> np.ndarray:
    basis_l = str(basis).strip().lower()
    if basis_l == "x":
        return _normalize([_finite_float(row.get(f"x_{s}"), 0.0) for s in suffixes])
    if basis_l == "y":
        return _normalize([_finite_float(row.get(f"y_{s}"), 0.0) for s in suffixes])
    if basis_l == "z":
        return _row_z(row, suffixes)
    raise ValueError(f"Unsupported composition basis {basis!r}; use x, y, z, or all.")


def _select_rows(
    rows: Iterable[Dict[str, str]],
    *,
    stages: Optional[set[int]],
    times: Optional[set[float]],
    max_points: int,
    prefer_quarantined: bool,
) -> List[Dict[str, str]]:
    candidates: List[Dict[str, str]] = []
    for row in rows:
        if str(row.get("node_type", "")).lower() != "stage":
            continue
        stage = int(round(_finite_float(row.get("stage"), math.nan)))
        time_s = _finite_float(row.get("time_s"), math.nan)
        if stages is not None and stage not in stages:
            continue
        if times is not None and not any(abs(time_s - t) <= 1.0e-6 for t in times):
            continue
        candidates.append(row)

    if prefer_quarantined:
        candidates.sort(
            key=lambda r: (
                _finite_float(r.get("thermo_degenerate_two_phase_unit_K_quarantined"), 0.0),
                _finite_float(r.get("time_s"), 0.0),
            ),
            reverse=True,
        )
    else:
        candidates.sort(key=lambda r: (_finite_float(r.get("time_s"), 0.0), _finite_float(r.get("stage"), 0.0)))
    return candidates[: max(int(max_points), 0)]


def _parse_csv_ints(raw: Optional[str]) -> Optional[set[int]]:
    if raw is None or not str(raw).strip():
        return None
    return {int(float(part.strip())) for part in str(raw).split(",") if part.strip()}


def _parse_csv_floats(raw: Optional[str]) -> Optional[set[float]]:
    if raw is None or not str(raw).strip():
        return None
    return {float(part.strip()) for part in str(raw).split(",") if part.strip()}


def _flash_object(provider: ThermoClapeyronProviderV1, T_F: float, P_psia: float, z: np.ndarray) -> Dict[str, Any]:
    fres = provider.flash_TP_full(float(T_F), float(P_psia), z.tolist())
    return {
        "K": np.asarray(fres.K, dtype=float).reshape((-1,)),
        "HL": float(fres.HL_BTU_lbmol),
        "HV": float(fres.HV_BTU_lbmol),
        "Z": math.nan if fres.Z is None else float(fres.Z),
        "phase_count": math.nan if fres.phase_count is None else float(fres.phase_count),
    }


def _flash_tuple(provider: ThermoClapeyronProviderV1, T_F: float, P_psia: float, z: np.ndarray) -> Dict[str, Any]:
    out = provider.flash_TP_full_F_psia(float(T_F), float(P_psia), z.tolist())
    return {
        "K": np.asarray(out[2], dtype=float).reshape((-1,)),
        "HL": float(out[3]),
        "HV": float(out[4]),
        "Z": math.nan if len(out) < 6 or out[5] is None else float(out[5]),
        "phase_count": math.nan,
    }


def _flash_batch(provider: ThermoClapeyronProviderV1, points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not points:
        return []
    out = provider.flash_TP_full_batch(
        [p["T_F"] for p in points],
        [p["P_psia"] for p in points],
        [p["z"] for p in points],
    )
    records: List[Dict[str, Any]] = []
    for item in out:
        records.append(
            {
                "K": np.asarray(item[2], dtype=float).reshape((-1,)),
                "HL": float(item[3]),
                "HV": float(item[4]),
                "Z": math.nan if len(item) < 6 or item[5] is None else float(item[5]),
                "phase_count": math.nan if len(item) < 9 or item[8] is None else float(item[8]),
            }
        )
    return records


def _flash_dwsim(provider: ThermoProviderV1, T_F: float, P_psia: float, z: np.ndarray) -> Dict[str, Any]:
    out = provider.flash_TP_full_F_psia(float(T_F), float(P_psia), z.tolist())
    return {
        "K": np.asarray(out[2], dtype=float).reshape((-1,)),
        "HL": float(out[3]),
        "HV": float(out[4]),
        "Z": math.nan if len(out) < 6 or out[5] is None else float(out[5]),
        "phase_count": math.nan,
    }


def probe_points(
    *,
    excel_path: Path,
    profile_rows: List[Dict[str, str]],
    stages: Optional[set[int]],
    times: Optional[set[float]],
    max_points: int,
    model_name: str,
    composition_basis: str,
    compare_dwsim_pr: bool,
    prefer_quarantined: bool = True,
) -> Dict[str, Any]:
    case = load_case_from_excel(str(excel_path))
    col = build_column_spec_from_case(case)
    suffixes = [_component_suffix(name) for name in col.components_excel]
    selected = _select_rows(
        profile_rows,
        stages=stages,
        times=times,
        max_points=max_points,
        prefer_quarantined=prefer_quarantined,
    )

    scalar_object_provider = ThermoClapeyronProviderV1(
        component_names_excel=col.components_excel,
        component_ids_dwsim=col.components_dwsim,
        model_name=model_name,
    )
    scalar_tuple_provider = ThermoClapeyronProviderV1(
        component_names_excel=col.components_excel,
        component_ids_dwsim=col.components_dwsim,
        model_name=model_name,
    )
    batch_provider = ThermoClapeyronProviderV1(
        component_names_excel=col.components_excel,
        component_ids_dwsim=col.components_dwsim,
        model_name=model_name,
    )
    dwsim_provider = (
        ThermoProviderV1(
            component_names_excel=col.components_excel,
            component_ids_dwsim=col.components_dwsim,
            silence_backend_console=True,
            property_package="pr",
        )
        if compare_dwsim_pr
        else None
    )

    bases = ["x", "y", "z"] if str(composition_basis).strip().lower() == "all" else [composition_basis]

    points: List[Dict[str, Any]] = []
    for row in selected:
        for basis in bases:
            comp = _row_composition(row, suffixes, basis)
            points.append(
                {
                    "time_s": _finite_float(row.get("time_s")),
                    "stage": int(round(_finite_float(row.get("stage")))),
                    "composition_basis": str(basis).strip().lower(),
                    "T_F": _finite_float(row.get("T_F")),
                    "P_psia": _finite_float(row.get("P_psia_hyd")),
                    "z": comp.tolist(),
                    "logged_quarantined": _finite_float(row.get("thermo_degenerate_two_phase_unit_K_quarantined"), 0.0),
                    "logged_phase_count": _finite_float(row.get("thermo_flash_phase_count")),
                    "logged_unit_K_flag": _finite_float(row.get("thermo_unit_K_flag"), 0.0),
                    "logged_K": [_finite_float(row.get(f"K_thermo_{s}")) for s in suffixes],
                    "logged_x": [_finite_float(row.get(f"x_{s}")) for s in suffixes],
                    "logged_y": [_finite_float(row.get(f"y_{s}")) for s in suffixes],
                }
            )

    batch_results = _flash_batch(batch_provider, points)
    records: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for idx, point in enumerate(points):
        base = {k: v for k, v in point.items() if k not in {"z", "logged_K", "logged_x", "logged_y"}}
        try:
            scalar_obj = _flash_object(scalar_object_provider, point["T_F"], point["P_psia"], np.asarray(point["z"]))
            scalar_tuple = _flash_tuple(scalar_tuple_provider, point["T_F"], point["P_psia"], np.asarray(point["z"]))
            batch = batch_results[idx]
            record = dict(base)
            for comp_i, suffix in enumerate(suffixes):
                record[f"z_{suffix}"] = float(point["z"][comp_i])
                record[f"logged_K_{suffix}"] = float(point["logged_K"][comp_i])
                record[f"scalar_object_K_{suffix}"] = float(scalar_obj["K"][comp_i])
                record[f"scalar_tuple_K_{suffix}"] = float(scalar_tuple["K"][comp_i])
                record[f"batch_K_{suffix}"] = float(batch["K"][comp_i])
            for prefix, res in (
                ("scalar_object", scalar_obj),
                ("scalar_tuple", scalar_tuple),
                ("batch", batch),
            ):
                record[f"{prefix}_unit_K"] = 1.0 if _is_unit_k(res["K"]) else 0.0
                record[f"{prefix}_phase_count"] = float(res["phase_count"])
                record[f"{prefix}_HL"] = float(res["HL"])
                record[f"{prefix}_HV"] = float(res["HV"])
                record[f"{prefix}_Z"] = float(res["Z"])
                record[f"{prefix}_max_abs_K_minus_1"] = float(np.max(np.abs(np.asarray(res["K"]) - 1.0)))
            record["max_abs_batch_minus_scalar_object_K"] = float(
                np.max(np.abs(np.asarray(batch["K"]) - np.asarray(scalar_obj["K"])))
            )
            if dwsim_provider is not None:
                dwsim = _flash_dwsim(dwsim_provider, point["T_F"], point["P_psia"], np.asarray(point["z"]))
                for comp_i, suffix in enumerate(suffixes):
                    record[f"dwsim_K_{suffix}"] = float(dwsim["K"][comp_i])
                    record[f"dwsim_minus_scalar_object_K_{suffix}"] = float(
                        dwsim["K"][comp_i] - scalar_obj["K"][comp_i]
                    )
                record["dwsim_unit_K"] = 1.0 if _is_unit_k(dwsim["K"]) else 0.0
                record["dwsim_HL"] = float(dwsim["HL"])
                record["dwsim_HV"] = float(dwsim["HV"])
                record["dwsim_Z"] = float(dwsim["Z"])
                record["max_abs_dwsim_minus_scalar_object_K"] = float(
                    np.max(np.abs(np.asarray(dwsim["K"]) - np.asarray(scalar_obj["K"])))
                )
            records.append(record)
        except Exception as exc:
            errors.append({**base, "error": str(exc)})

    return {
        "excel_path": str(excel_path),
        "model_name": model_name,
        "composition_basis": composition_basis,
        "components": list(col.components_excel),
        "records": records,
        "errors": errors,
        "summary": {
            "points": len(points),
            "records": len(records),
            "errors": len(errors),
            "scalar_object_unit_K_count": sum(1 for r in records if r.get("scalar_object_unit_K") == 1.0),
            "scalar_tuple_unit_K_count": sum(1 for r in records if r.get("scalar_tuple_unit_K") == 1.0),
            "batch_unit_K_count": sum(1 for r in records if r.get("batch_unit_K") == 1.0),
            "dwsim_unit_K_count": sum(1 for r in records if r.get("dwsim_unit_K") == 1.0)
            if compare_dwsim_pr
            else None,
            "logged_quarantined_count": sum(1 for r in records if _finite_float(r.get("logged_quarantined"), 0.0) > 0.5),
            "basis_counts": {
                basis: {
                    "records": sum(1 for r in records if r.get("composition_basis") == basis),
                    "scalar_object_unit_K_count": sum(
                        1
                        for r in records
                        if r.get("composition_basis") == basis and r.get("scalar_object_unit_K") == 1.0
                    ),
                    "batch_unit_K_count": sum(
                        1 for r in records if r.get("composition_basis") == basis and r.get("batch_unit_K") == 1.0
                    ),
                }
                for basis in sorted({str(r.get("composition_basis")) for r in records})
            },
            "max_abs_batch_minus_scalar_object_K": max(
                [float(r["max_abs_batch_minus_scalar_object_K"]) for r in records],
                default=math.nan,
            ),
            "max_abs_dwsim_minus_scalar_object_K": max(
                [float(r["max_abs_dwsim_minus_scalar_object_K"]) for r in records if "max_abs_dwsim_minus_scalar_object_K" in r],
                default=math.nan,
            ),
        },
    }


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    fields: List[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, report: Dict[str, Any], *, profile_path: Path) -> None:
    s = report["summary"]
    lines = [
        "# Clapeyron Unit-K Probe",
        "",
        f"Profile: `{profile_path}`",
        f"Excel: `{report['excel_path']}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in s.items():
        lines.append(f"| `{key}` | {value} |")
    lines.extend(
        [
            "",
            "## Points",
            "",
            "| time_s | stage | basis | quarantined | logged phase | scalar phase | scalar unit-K | batch unit-K | dwsim unit-K | max |batch-scalar K| | max |dwsim-scalar K| |",
            "|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for r in report["records"]:
        fmt = dict(r)
        fmt["dwsim_unit_K"] = _finite_float(r.get("dwsim_unit_K"), math.nan)
        fmt["max_abs_dwsim_minus_scalar_object_K"] = _finite_float(
            r.get("max_abs_dwsim_minus_scalar_object_K"), math.nan
        )
        lines.append(
            "| {time_s:.6g} | {stage} | {composition_basis} | {logged_quarantined:.0f} | {logged_phase_count:.6g} | "
            "{scalar_object_phase_count:.6g} | {scalar_object_unit_K:.0f} | {batch_unit_K:.0f} | "
            "{dwsim_unit_K:.0f} | {max_abs_batch_minus_scalar_object_K:.6g} | "
            "{max_abs_dwsim_minus_scalar_object_K:.6g} |".format(**fmt)
        )
    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        for err in report["errors"]:
            lines.append(f"- stage {err.get('stage')} t={err.get('time_s')}: {err.get('error')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Probe Clapeyron unit-K behavior at logged profile points.")
    ap.add_argument("--excel", required=True)
    ap.add_argument("--profile-csv", required=True)
    ap.add_argument("--stages", default=None, help="Comma-separated 1-based stages.")
    ap.add_argument("--times", default=None, help="Comma-separated times in seconds.")
    ap.add_argument("--max-points", type=int, default=20)
    ap.add_argument("--model", default="PR")
    ap.add_argument("--composition-basis", default="z", choices=["x", "y", "z", "all"])
    ap.add_argument("--compare-dwsim-pr", action="store_true")
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--output-csv", default=None)
    ap.add_argument("--output-md", default=None)
    args = ap.parse_args(argv)

    excel_path = _resolve(args.excel)
    profile_path = _resolve(args.profile_csv)
    report = probe_points(
        excel_path=excel_path,
        profile_rows=_read_csv(profile_path),
        stages=_parse_csv_ints(args.stages),
        times=_parse_csv_floats(args.times),
        max_points=int(args.max_points),
        model_name=str(args.model),
        composition_basis=str(args.composition_basis),
        compare_dwsim_pr=bool(args.compare_dwsim_pr),
    )
    if args.output_json:
        _resolve(args.output_json).write_text(json.dumps(report, indent=2, allow_nan=True) + "\n", encoding="utf-8")
    else:
        print(json.dumps(report["summary"], indent=2, allow_nan=True))
    if args.output_csv:
        write_csv(_resolve(args.output_csv), report["records"])
    if args.output_md:
        write_markdown(_resolve(args.output_md), report, profile_path=profile_path)

    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
