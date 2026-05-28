#!/usr/bin/env python
"""
Reconcile PR model definitions between DWSIM PR and Clapeyron PR.

This audit focuses on static model inputs: component constants, alpha inputs,
mixing rule, translation model, ideal model, and binary interaction parameters.
It complements fixed-point flash audits by explaining why K-values and enthalpy
packets differ before the dynamic model is involved.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _PROJECT_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_clapeyron_provider_v1 import ThermoClapeyronProviderV1


def _resolve_path(raw: str) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (_PROJECT_ROOT / p).resolve()


def _finite_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    return out if math.isfinite(out) else None


def _as_list(value: Any) -> list[float]:
    return [float(v) for v in list(value)]


def _as_matrix(value: Any) -> list[list[float]]:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 2:
        raise ValueError("expected matrix")
    return [[float(v) for v in row] for row in arr.tolist()]


def _init_dwsim(col: Any):
    from dynamic_distillation import pr_flash_backend_v1 as dwsim_backend

    dwsim_backend.set_component_ids(list(col.components_dwsim))
    dwsim_backend.set_component_names(list(col.components_excel))
    dwsim_backend.set_property_package("pr")
    dwsim_backend._init_dwsim()
    return dwsim_backend


def _dwsim_constant(dwsim_backend: Any, component_id: str, prop: str) -> float | None:
    try:
        return _finite_or_none(dwsim_backend._dtlc.GetCompoundConstProp(str(component_id), str(prop)))
    except Exception:
        return None


def _extract_dwsim_components(dwsim_backend: Any, col: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    prop_map = {
        "molecular_weight": "molecularWeight",
        "Tc_K": "criticalTemperature",
        "Pc_Pa": "criticalPressure",
        "acentric_factor": "acentricFactor",
        "normal_boiling_point_K": "normalBoilingPoint",
    }
    for i, (excel_name, dwsim_id) in enumerate(zip(col.components_excel, col.components_dwsim)):
        row: dict[str, Any] = {
            "component_index": int(i),
            "excel_name": str(excel_name),
            "dwsim_id": str(dwsim_id),
        }
        for out_key, prop in prop_map.items():
            row[f"dwsim_{out_key}"] = _dwsim_constant(dwsim_backend, str(dwsim_id), prop)
        rows.append(row)
    return rows


def _extract_dwsim_kij(dwsim_backend: Any, col: Any) -> list[list[float]]:
    n = len(col.components_dwsim)
    kij = np.zeros((n, n), dtype=float)
    try:
        ip = dwsim_backend._prop_package.m_pr.InteractionParameters
    except Exception:
        return kij.tolist()
    names = [str(v) for v in col.components_dwsim]
    for i, c1 in enumerate(names):
        for j, c2 in enumerate(names):
            if i == j:
                continue
            val = None
            for a, b in ((c1, c2), (c2, c1)):
                try:
                    val = float(ip[a][b].kij)
                    break
                except Exception:
                    continue
            kij[i, j] = 0.0 if val is None else float(val)
    return kij.tolist()


def _extract_clapeyron(col: Any) -> dict[str, Any]:
    provider = ThermoClapeyronProviderV1(
        component_names_excel=col.components_excel,
        component_ids_dwsim=col.components_dwsim,
        model_name="PR",
    )
    model = provider._build_model()
    jl = provider._load_module().jl

    def call(expr: str) -> Any:
        return jl.seval(expr)(model)

    params = {
        "components": [str(v) for v in list(call("m -> m.components"))],
        "Tc_K": _as_list(call("m -> m.params.Tc.values")),
        "Pc_Pa": _as_list(call("m -> m.params.Pc.values")),
        "molecular_weight": _as_list(call("m -> m.params.Mw.values")),
        "acentric_factor": _as_list(call("m -> m.alpha.params.acentricfactor.values")),
        "a_matrix": _as_matrix(call("m -> m.params.a.values")),
        "b_matrix": _as_matrix(call("m -> m.params.b.values")),
        "alpha_type": str(call("m -> string(typeof(m.alpha))")),
        "mixing_rule": str(call("m -> string(typeof(m.mixing))")),
        "translation_type": str(call("m -> string(typeof(m.translation))")),
        "ideal_model_type": str(call("m -> string(typeof(m.idealmodel))")),
    }
    params["inferred_kij_from_a_matrix"] = _infer_kij_from_a_matrix(params["a_matrix"])
    return params


def _infer_kij_from_a_matrix(a_matrix: list[list[float]]) -> list[list[float]]:
    a = np.asarray(a_matrix, dtype=float)
    n = a.shape[0]
    kij = np.zeros((n, n), dtype=float)
    diag = np.diag(a)
    for i in range(n):
        for j in range(n):
            denom = math.sqrt(float(diag[i]) * float(diag[j]))
            if denom > 0.0:
                kij[i, j] = 1.0 - float(a[i, j]) / denom
    return kij.tolist()


def _component_rows(
    dwsim_components: list[dict[str, Any]],
    clapeyron: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fields = [
        "molecular_weight",
        "Tc_K",
        "Pc_Pa",
        "acentric_factor",
    ]
    for i, base in enumerate(dwsim_components):
        row = dict(base)
        row["clapeyron_name"] = clapeyron["components"][i]
        for field in fields:
            dval = _finite_or_none(row.get(f"dwsim_{field}"))
            cval = _finite_or_none(clapeyron[field][i])
            row[f"clapeyron_{field}"] = cval
            if dval is not None and cval is not None:
                row[f"delta_{field}"] = cval - dval
                row[f"rel_delta_{field}"] = (cval - dval) / dval if abs(dval) > 1.0e-12 else ""
            else:
                row[f"delta_{field}"] = ""
                row[f"rel_delta_{field}"] = ""
        return_fields = ["normal_boiling_point_K"]
        for field in return_fields:
            row[f"clapeyron_{field}"] = ""
            row[f"delta_{field}"] = ""
            row[f"rel_delta_{field}"] = ""
        rows.append(row)
    return rows


def _pair_rows(
    col: Any,
    dwsim_kij: list[list[float]],
    clap_kij: list[list[float]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    names = [str(v) for v in col.components_dwsim]
    n = len(names)
    for i in range(n):
        for j in range(i + 1, n):
            dval = float(dwsim_kij[i][j])
            cval = float(clap_kij[i][j])
            rows.append(
                {
                    "component_i": names[i],
                    "component_j": names[j],
                    "dwsim_kij": dval,
                    "clapeyron_inferred_kij": cval,
                    "delta_kij": cval - dval,
                }
            )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile DWSIM PR and Clapeyron PR model definitions.")
    parser.add_argument("--excel", default="distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx")
    parser.add_argument("--output-dir", default="logs/pr_backend_definition_reconciliation")
    args = parser.parse_args(argv)

    excel_path = _resolve_path(args.excel)
    output_dir = _resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    case = load_case_from_excel(str(excel_path))
    col = build_column_spec_from_case(case)

    dwsim_backend = _init_dwsim(col)
    dwsim_components = _extract_dwsim_components(dwsim_backend, col)
    dwsim_kij = _extract_dwsim_kij(dwsim_backend, col)
    clapeyron = _extract_clapeyron(col)

    comp_rows = _component_rows(dwsim_components, clapeyron)
    pair_rows = _pair_rows(col, dwsim_kij, clapeyron["inferred_kij_from_a_matrix"])

    comp_csv = output_dir / "pr_component_constant_reconciliation.csv"
    kij_csv = output_dir / "pr_binary_interaction_reconciliation.csv"
    report_json = output_dir / "pr_definition_reconciliation_report.json"
    _write_csv(comp_csv, comp_rows)
    _write_csv(kij_csv, pair_rows)

    report = {
        "excel": str(excel_path),
        "components_excel": [str(v) for v in col.components_excel],
        "components_dwsim": [str(v) for v in col.components_dwsim],
        "dwsim_property_package": "PengRobinsonPropertyPackage(True)",
        "clapeyron_model": {
            "model": "PR",
            "components": clapeyron["components"],
            "alpha_type": clapeyron["alpha_type"],
            "mixing_rule": clapeyron["mixing_rule"],
            "translation_type": clapeyron["translation_type"],
            "ideal_model_type": clapeyron["ideal_model_type"],
        },
        "component_rows": comp_rows,
        "binary_interaction_rows": pair_rows,
        "dwsim_kij_matrix": dwsim_kij,
        "clapeyron_inferred_kij_matrix": clapeyron["inferred_kij_from_a_matrix"],
        "clapeyron_a_matrix": clapeyron["a_matrix"],
        "clapeyron_b_matrix": clapeyron["b_matrix"],
        "outputs": {
            "component_csv": str(comp_csv),
            "kij_csv": str(kij_csv),
        },
    }
    report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"[reconcile] wrote {report_json}")
    print(f"[reconcile] wrote {comp_csv}")
    print(f"[reconcile] wrote {kij_csv}")
    print(
        "[reconcile] Clapeyron model: "
        f"alpha={clapeyron['alpha_type']} mixing={clapeyron['mixing_rule']} "
        f"translation={clapeyron['translation_type']} ideal={clapeyron['ideal_model_type']}"
    )
    print("[reconcile] Component constant deltas:")
    for row in comp_rows:
        print(
            f"  {row['dwsim_id']}: "
            f"dTc={row['delta_Tc_K']:.6g} K "
            f"dPc={row['delta_Pc_Pa']:.6g} Pa "
            f"domega={row['delta_acentric_factor']:.6g} "
            f"dMW={row['delta_molecular_weight']:.6g}"
        )
    print("[reconcile] Binary interaction deltas:")
    for row in pair_rows:
        print(
            f"  {row['component_i']} / {row['component_j']}: "
            f"DWSIM kij={row['dwsim_kij']:.6g}, "
            f"Clapeyron inferred kij={row['clapeyron_inferred_kij']:.6g}, "
            f"delta={row['delta_kij']:.6g}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
