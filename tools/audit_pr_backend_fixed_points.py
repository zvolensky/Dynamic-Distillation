#!/usr/bin/env python
"""
Audit DWSIM PR vs Clapeyron PR at fixed T/P/composition points.

Inputs are existing comparison logs. The script samples final tray profile rows,
calls both live PR backends at the same T, P, and liquid composition, then
reports flash, enthalpy, density, and K-value deltas.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys
from typing import Any, Sequence

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _PROJECT_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_clapeyron_provider_v1 import ThermoClapeyronProviderV1
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


def _resolve_path(raw: str) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (_PROJECT_ROOT / p).resolve()


def _to_float(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    return out if math.isfinite(out) else None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _comp_suffix(name: str) -> str:
    raw = str(name).strip().lower()
    out = "".join(ch if ch.isalnum() else "_" for ch in raw).strip("_")
    return out if out else "comp"


def _normalize(values: Sequence[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape((-1,))
    arr = np.where(np.isfinite(arr), arr, 0.0)
    arr = np.maximum(arr, 0.0)
    total = float(np.sum(arr))
    if total <= 0.0:
        raise ValueError("composition sum must be positive")
    return arr / total


def _find_profile_path(report_dir: Path, backend: str) -> Path:
    report_path = report_dir / "pr_backend_comparison_report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    backend_key = str(backend).strip().lower()
    for result in payload.get("results", []):
        if str(result.get("backend", "")).strip().lower() != backend_key:
            continue
        run_id = str(result.get("run_id") or "")
        logs_dir = Path(str(result.get("logs_dir") or ""))
        if run_id:
            candidate = logs_dir / f"column_profile_{run_id}.csv"
            if candidate.exists():
                return candidate
        matches = sorted(logs_dir.glob("column_profile_*.csv"), key=lambda p: p.stat().st_mtime)
        if matches:
            return matches[-1]
    raise FileNotFoundError(f"Could not find profile CSV for backend {backend!r} in {report_dir}")


def _dwsim_pr_userlocation_kwargs(col: Any) -> dict[str, Any]:
    from dynamic_distillation import pr_flash_backend_v1 as dwsim_backend
    import pyclapeyron

    dwsim_backend.set_component_ids(list(col.components_dwsim))
    dwsim_backend.set_component_names(list(col.components_excel))
    dwsim_backend.set_property_package("pr")
    dwsim_backend._init_dwsim()

    def const(component_id: str, prop: str) -> float:
        return float(dwsim_backend._dtlc.GetCompoundConstProp(str(component_id), str(prop)))

    ids = [str(v) for v in col.components_dwsim]
    Tc = [const(v, "criticalTemperature") for v in ids]
    Pc = [const(v, "criticalPressure") for v in ids]
    Mw = [const(v, "molecularWeight") for v in ids]
    omega = [const(v, "acentricFactor") for v in ids]
    kij = np.zeros((len(ids), len(ids)), dtype=float)
    try:
        ip = dwsim_backend._prop_package.m_pr.InteractionParameters
        for i, c1 in enumerate(ids):
            for j, c2 in enumerate(ids):
                if i == j:
                    continue
                for a, b in ((c1, c2), (c2, c1)):
                    try:
                        kij[i, j] = float(ip[a][b].kij)
                        break
                    except Exception:
                        continue
    except Exception:
        pass

    def vec(values: Sequence[float]) -> str:
        return "[" + ", ".join(f"{float(v):.17g}" for v in values) + "]"

    def mat(values: np.ndarray) -> str:
        return "[" + "; ".join(" ".join(f"{float(v):.17g}" for v in row) for row in values) + "]"

    expr = (
        f"(;Tc={vec(Tc)}, Pc={vec(Pc)}, Mw={vec(Mw)}, "
        f"acentricfactor={vec(omega)}, k={mat(kij)})"
    )
    return {"userlocations": pyclapeyron.jl.seval(expr)}


def _final_stage_rows(profile_path: Path) -> list[dict[str, str]]:
    rows = _read_csv(profile_path)
    final_time = max(v for v in (_to_float(row.get("time_s")) for row in rows) if v is not None)
    out = []
    for row in rows:
        time_s = _to_float(row.get("time_s"))
        if time_s is None or abs(time_s - final_time) > 1.0e-9:
            continue
        if str(row.get("node_type", "")).strip().lower() != "stage":
            continue
        T_F = _to_float(row.get("T_F"))
        if T_F is None:
            continue
        out.append(row)
    return sorted(out, key=lambda r: int(float(r.get("stage", "0"))))


def _sample_rows(rows: list[dict[str, str]], max_points: int) -> list[dict[str, str]]:
    if max_points <= 0 or len(rows) <= max_points:
        return rows
    idx = np.linspace(0, len(rows) - 1, int(max_points))
    chosen = sorted(set(int(round(v)) for v in idx.tolist()))
    return [rows[i] for i in chosen]


def _row_get_case_insensitive(row: dict[str, str], key: str) -> str:
    if key in row:
        return row[key]
    target = str(key).lower()
    for existing, value in row.items():
        if str(existing).lower() == target:
            return value
    raise KeyError(key)


def _flash(provider: Any, T_F: float, P_psia: float, z: np.ndarray) -> dict[str, Any]:
    if hasattr(provider, "flash_TP_full_F_psia_no_cp"):
        out = provider.flash_TP_full_F_psia_no_cp(T_F, P_psia, z.tolist())
    else:
        out = provider.flash_TP_full_F_psia(T_F, P_psia, z.tolist())
    x, y, K, HL, HV, *rest = out
    Z = rest[0] if rest else None
    rhoL = None
    if hasattr(provider, "liquid_density_lbmol_ft3"):
        rhoL = provider.liquid_density_lbmol_ft3(T_F, P_psia, np.asarray(x, dtype=float).tolist())
    cpL = None
    cpV = None
    if hasattr(provider, "cp_liq_vap_btu_per_lbmolF"):
        try:
            cpL, cpV = provider.cp_liq_vap_btu_per_lbmolF(T_F, P_psia, z.tolist())
        except Exception:
            cpL, cpV = None, None
    return {
        "x": np.asarray(x, dtype=float).reshape((-1,)),
        "y": np.asarray(y, dtype=float).reshape((-1,)),
        "K": np.asarray(K, dtype=float).reshape((-1,)),
        "HL": float(HL),
        "HV": float(HV),
        "latent": float(HV) - float(HL),
        "Z": None if Z is None else float(Z),
        "rhoL": None if rhoL is None else float(rhoL),
        "cpL": None if cpL is None else float(cpL),
        "cpV": None if cpV is None else float(cpV),
    }


def _max_abs_delta(a: np.ndarray, b: np.ndarray) -> float:
    aa = np.asarray(a, dtype=float).reshape((-1,))
    bb = np.asarray(b, dtype=float).reshape((-1,))
    mask = np.isfinite(aa) & np.isfinite(bb)
    if not np.any(mask):
        return math.nan
    return float(np.max(np.abs(bb[mask] - aa[mask])))


def _scalar_delta(left: Any, right: Any) -> tuple[Any, Any, Any]:
    lval = _to_float(left)
    rval = _to_float(right)
    if lval is None or rval is None:
        return left, right, ""
    return lval, rval, rval - lval


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit fixed-point PR backend differences.")
    parser.add_argument("report_dir")
    parser.add_argument("--excel", default="distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx")
    parser.add_argument("--profile-backend", default="dwsim-pr")
    parser.add_argument("--max-points", type=int, default=8)
    parser.add_argument("--align-clapeyron-to-dwsim-pr", action="store_true")
    parser.add_argument("--output-csv", default="")
    args = parser.parse_args(argv)

    report_dir = _resolve_path(args.report_dir)
    excel_path = _resolve_path(args.excel)
    profile_path = _find_profile_path(report_dir, str(args.profile_backend))

    case = load_case_from_excel(str(excel_path))
    col = build_column_spec_from_case(case)
    suffixes = [_comp_suffix(name) for name in col.components_excel]
    stage_pressure = {
        int(stage): float(pressure)
        for stage, pressure in zip(
            np.asarray(col.stage_1based, dtype=int).reshape((-1,)).tolist(),
            np.asarray(col.P_psia, dtype=float).reshape((-1,)).tolist(),
        )
    }

    dwsim = ThermoProviderV1(
        component_names_excel=col.components_excel,
        component_ids_dwsim=col.components_dwsim,
        silence_backend_console=True,
        property_package="pr",
    )
    clap_model_kwargs = _dwsim_pr_userlocation_kwargs(col) if bool(args.align_clapeyron_to_dwsim_pr) else {}
    clap = ThermoClapeyronProviderV1(
        component_names_excel=col.components_excel,
        component_ids_dwsim=col.components_dwsim,
        model_name="PR",
        model_kwargs=clap_model_kwargs,
    )

    rows = _sample_rows(_final_stage_rows(profile_path), int(args.max_points))
    out_rows: list[dict[str, Any]] = []
    for row in rows:
        stage = int(float(row["stage"]))
        T_F = float(row["T_F"])
        P_profile = _to_float(row.get("P_psia_hyd"))
        P_psia = float(P_profile if P_profile is not None else stage_pressure[stage])
        z = _normalize([float(_row_get_case_insensitive(row, f"x_{suffix}")) for suffix in suffixes])

        try:
            dres = _flash(dwsim, T_F, P_psia, z)
            cres = _flash(clap, T_F, P_psia, z)
            error = ""
        except Exception as exc:
            dres = {}
            cres = {}
            error = str(exc)

        out: dict[str, Any] = {
            "source_profile": str(args.profile_backend),
            "clapeyron_aligned_to_dwsim_pr": bool(args.align_clapeyron_to_dwsim_pr),
            "stage": stage,
            "T_F": T_F,
            "P_psia": P_psia,
            "error": error,
            "max_abs_dx": _max_abs_delta(dres.get("x", []), cres.get("x", [])) if not error else "",
            "max_abs_dy": _max_abs_delta(dres.get("y", []), cres.get("y", [])) if not error else "",
            "max_abs_dK": _max_abs_delta(dres.get("K", []), cres.get("K", [])) if not error else "",
        }
        for key in ("HL", "HV", "latent", "Z", "rhoL", "cpL", "cpV"):
            lval, rval, delta = _scalar_delta(dres.get(key), cres.get(key))
            out[f"dwsim_{key}"] = lval
            out[f"clapeyron_{key}"] = rval
            out[f"delta_{key}"] = delta
        for i, suffix in enumerate(suffixes):
            out[f"z_{suffix}"] = float(z[i])
            if not error:
                out[f"dwsim_K_{suffix}"] = float(dres["K"][i])
                out[f"clapeyron_K_{suffix}"] = float(cres["K"][i])
                out[f"delta_K_{suffix}"] = float(cres["K"][i] - dres["K"][i])
        out_rows.append(out)

    output_csv = Path(args.output_csv) if args.output_csv else report_dir / "pr_backend_fixed_point_audit.csv"
    fieldnames: list[str] = []
    for row in out_rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"[audit] source profile: {profile_path}")
    print(f"[audit] wrote {output_csv}")
    good = [r for r in out_rows if not r.get("error")]
    if good:
        for metric in ("max_abs_dK", "max_abs_dy", "delta_HL", "delta_HV", "delta_latent", "delta_rhoL", "delta_cpL", "delta_cpV"):
            vals = [_to_float(r.get(metric)) for r in good]
            vals = [v for v in vals if v is not None]
            if vals:
                max_abs = max(vals, key=lambda v: abs(v))
                mean_abs = sum(abs(v) for v in vals) / len(vals)
                print(f"[audit] {metric}: max_abs_signed={max_abs:.8g} mean_abs={mean_abs:.8g}")
    errors = [r for r in out_rows if r.get("error")]
    if errors:
        print(f"[audit] errors: {len(errors)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
