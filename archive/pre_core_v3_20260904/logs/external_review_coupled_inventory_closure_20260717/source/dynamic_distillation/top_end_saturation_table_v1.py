"""
top_end_saturation_table_v1.py

Local PR-backed top-end saturation table for condenser/drum closure.

Purpose
-------
Provide direct bubble-point temperature/pressure interpolation in the narrow
top-end operating envelope where the broad flash table has shown material bias.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


def _normalize_comp(z: Sequence[float], n_expected: Optional[int] = None) -> np.ndarray:
    a = np.asarray(z, dtype=float).reshape((-1,))
    if n_expected is not None and a.size != int(n_expected):
        raise ValueError(f"Expected composition length {int(n_expected)}, got {a.size}")
    s = float(np.sum(a))
    if (not np.isfinite(s)) or s <= 0.0:
        raise ValueError("Composition sum must be > 0")
    return a / s


def _validate_str_list(name: str, values: Sequence[str]) -> List[str]:
    out = [str(v).strip() for v in values]
    if not out or any((not v) for v in out):
        raise ValueError(f"{name} must be a non-empty list of non-empty strings")
    return out


def _parse_comp_csv(text: str, n_expected: Optional[int] = None) -> np.ndarray:
    parts = [str(x).strip() for x in str(text).split(",")]
    vals = [float(x) for x in parts if x]
    return _normalize_comp(vals, n_expected)


def _thermo_id_from_name(name: str) -> str:
    key = str(name).strip().lower().replace("_", "-")
    mapping = {
        "propane": "propane",
        "n-propane": "propane",
        "butane": "n-butane",
        "n-butane": "n-butane",
        "pentane": "n-pentane",
        "n-pentane": "n-pentane",
    }
    if key in mapping:
        return mapping[key]
    raise ValueError(f"Unsupported component for local PR saturation table: {name!r}")


def _interp_1d(grid: np.ndarray, values: np.ndarray, point: float) -> float:
    g = np.asarray(grid, dtype=float).reshape((-1,))
    v = np.asarray(values, dtype=float).reshape((-1,))
    if g.size != v.size or g.size < 2:
        raise ValueError("1D interpolation requires matching grid/value lengths >= 2")
    p = float(np.clip(float(point), float(g[0]), float(g[-1])))
    return float(np.interp(p, g, v))


def _rachford_rice_beta(K: np.ndarray, z: np.ndarray, tol: float = 1e-10, max_iter: int = 80) -> float:
    K = np.asarray(K, dtype=float).reshape((-1,))
    z = np.asarray(z, dtype=float).reshape((-1,))
    z = z / max(float(np.sum(z)), 1e-300)
    K = np.where(~np.isfinite(K) | (K <= 1e-12), 1e-12, K)

    def f(beta: float) -> float:
        denom = 1.0 + beta * (K - 1.0)
        denom = np.where(np.abs(denom) < 1e-12, np.sign(denom) * 1e-12 + (denom == 0.0) * 1e-12, denom)
        return float(np.sum(z * (K - 1.0) / denom))

    f0 = f(0.0)
    f1 = f(1.0)
    if f0 < 0.0 and f1 < 0.0:
        return 0.0
    if f0 > 0.0 and f1 > 0.0:
        return 1.0

    lo = 0.0
    hi = 1.0
    flo = f0
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        fmid = f(mid)
        if abs(fmid) <= tol:
            return float(mid)
        if fmid * flo > 0.0:
            lo = mid
            flo = fmid
        else:
            hi = mid
    return float(0.5 * (lo + hi))


def _sum_kx(provider: ThermoProviderV1, T_F: float, P_psia: float, x: np.ndarray) -> float:
    res = provider.flash_TP_full(float(T_F), float(P_psia), x.tolist())
    K = np.asarray(res.K, dtype=float).reshape((-1,))
    return float(np.sum(K * x))


def _bubble_point_pressure_psia(
    *,
    provider: ThermoProviderV1,
    T_F: float,
    x: np.ndarray,
    P_guess_psia: float,
    P_min_psia: float,
    P_max_psia: float,
    max_iter: int = 50,
) -> float:
    x = _normalize_comp(x)
    P_min = max(float(P_min_psia), 1.0)
    P_max = max(float(P_max_psia), P_min + 1.0)
    Ps = np.linspace(P_min, P_max, 25)
    vals = [(_sum_kx(provider, float(T_F), float(P), x) - 1.0) for P in Ps]

    bracket = None
    best_dist = float("inf")
    for i in range(len(Ps) - 1):
        f0 = float(vals[i])
        f1 = float(vals[i + 1])
        if f0 == 0.0:
            return float(Ps[i])
        if f0 * f1 < 0.0:
            mid = 0.5 * (float(Ps[i]) + float(Ps[i + 1]))
            dist = abs(mid - float(P_guess_psia))
            if dist < best_dist:
                best_dist = dist
                bracket = (float(Ps[i]), float(Ps[i + 1]), f0, f1)

    if bracket is None:
        P_best = float(Ps[int(np.argmin(np.abs(np.asarray(vals, dtype=float))))])
        return float(P_best)

    lo, hi, flo, _fhi = bracket
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        fmid = _sum_kx(provider, float(T_F), float(mid), x) - 1.0
        if abs(fmid) <= 1.0e-8:
            return float(mid)
        if fmid * flo > 0.0:
            lo = mid
            flo = fmid
        else:
            hi = mid
    return float(0.5 * (lo + hi))


def _bubble_point_temperature_F(
    *,
    provider: ThermoProviderV1,
    P_psia: float,
    x: np.ndarray,
    T_guess_F: float,
    T_min_F: float,
    T_max_F: float,
    beta_target: float = 1.0e-6,
    max_iter: int = 50,
) -> float:
    x = _normalize_comp(x)
    T_min = float(T_min_F)
    T_max = max(float(T_max_F), T_min + 1.0)
    Ts = np.linspace(T_min, T_max, 25)
    vals = []
    for T in Ts:
        res = provider.flash_TP_full(float(T), float(P_psia), x.tolist())
        beta = _rachford_rice_beta(np.asarray(res.K, dtype=float), x)
        vals.append(float(beta - beta_target))

    bracket = None
    best_dist = float("inf")
    for i in range(len(Ts) - 1):
        f0 = float(vals[i])
        f1 = float(vals[i + 1])
        if f0 == 0.0:
            return float(Ts[i])
        if f0 * f1 < 0.0:
            mid = 0.5 * (float(Ts[i]) + float(Ts[i + 1]))
            dist = abs(mid - float(T_guess_F))
            if dist < best_dist:
                best_dist = dist
                bracket = (float(Ts[i]), float(Ts[i + 1]), f0, f1)

    if bracket is None:
        T_best = float(Ts[int(np.argmin(np.abs(np.asarray(vals, dtype=float))))])
        return float(T_best)

    lo, hi, flo, _fhi = bracket
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        res = provider.flash_TP_full(float(mid), float(P_psia), x.tolist())
        beta = _rachford_rice_beta(np.asarray(res.K, dtype=float), x)
        fmid = float(beta - beta_target)
        if abs(fmid) <= 1.0e-8:
            return float(mid)
        if fmid * flo > 0.0:
            lo = mid
            flo = fmid
        else:
            hi = mid
    return float(0.5 * (lo + hi))


@dataclass(frozen=True)
class _TopSatAnchor:
    name: str
    z_ref: np.ndarray
    P_bubble_psia: np.ndarray
    T_bubble_F: np.ndarray


class TopEndSaturationTableV1:
    def __init__(
        self,
        *,
        component_names_excel: Sequence[str],
        component_ids_dwsim: Sequence[str],
        T_grid_F: Sequence[float],
        P_grid_psia: Sequence[float],
        anchors: Sequence[_TopSatAnchor],
        n_anchor_blend: int = 3,
        anchor_blend_power: float = 2.0,
        anchor_distance_eps: float = 1.0e-12,
    ) -> None:
        self.component_names_excel = _validate_str_list("component_names_excel", component_names_excel)
        self.component_ids_dwsim = _validate_str_list("component_ids_dwsim", component_ids_dwsim)
        if len(self.component_names_excel) != len(self.component_ids_dwsim):
            raise ValueError("component_names_excel and component_ids_dwsim must have equal length")
        self.n_components = len(self.component_ids_dwsim)
        self.T_grid_F = np.asarray(T_grid_F, dtype=float).reshape((-1,))
        self.P_grid_psia = np.asarray(P_grid_psia, dtype=float).reshape((-1,))
        self.n_anchor_blend = max(int(n_anchor_blend), 1)
        self.anchor_blend_power = float(anchor_blend_power)
        self.anchor_distance_eps = float(anchor_distance_eps)
        self.anchors: List[_TopSatAnchor] = []
        for a in anchors:
            self.anchors.append(
                _TopSatAnchor(
                    name=str(a.name),
                    z_ref=_normalize_comp(a.z_ref, self.n_components),
                    P_bubble_psia=np.asarray(a.P_bubble_psia, dtype=float).reshape((self.T_grid_F.size,)),
                    T_bubble_F=np.asarray(a.T_bubble_F, dtype=float).reshape((self.P_grid_psia.size,)),
                )
            )
        if not self.anchors:
            raise ValueError("At least one saturation anchor is required")

    @classmethod
    def from_json(cls, path: str | Path) -> "TopEndSaturationTableV1":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        anchors_raw = data.get("anchors", [])
        anchors = [
            _TopSatAnchor(
                name=str(raw.get("name", f"anchor_{i+1}")),
                z_ref=np.asarray(raw["z_ref"], dtype=float),
                P_bubble_psia=np.asarray(raw["P_bubble_psia"], dtype=float),
                T_bubble_F=np.asarray(raw["T_bubble_F"], dtype=float),
            )
            for i, raw in enumerate(anchors_raw)
        ]
        return cls(
            component_names_excel=data["components_excel"],
            component_ids_dwsim=data["components_dwsim"],
            T_grid_F=data["T_grid_F"],
            P_grid_psia=data["P_grid_psia"],
            anchors=anchors,
            n_anchor_blend=int(data.get("n_anchor_blend", 3)),
            anchor_blend_power=float(data.get("anchor_blend_power", 2.0)),
            anchor_distance_eps=float(data.get("anchor_distance_eps", 1.0e-12)),
        )

    def _anchor_blend(self, z: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        z = _normalize_comp(z, self.n_components)
        nA = len(self.anchors)
        if nA == 1 or self.n_anchor_blend <= 1:
            return np.array([0], dtype=int), np.array([1.0], dtype=float)
        dists = np.asarray([float(np.linalg.norm(a.z_ref - z, ord=1)) for a in self.anchors], dtype=float)
        i_near = int(np.argmin(dists))
        if dists[i_near] <= self.anchor_distance_eps:
            return np.array([i_near], dtype=int), np.array([1.0], dtype=float)
        k = min(self.n_anchor_blend, nA)
        idx = np.argsort(dists)[:k].astype(int)
        d = np.clip(dists[idx], self.anchor_distance_eps, None)
        w = d ** (-self.anchor_blend_power)
        s = float(np.sum(w))
        if (not np.isfinite(s)) or s <= 0.0:
            return np.array([i_near], dtype=int), np.array([1.0], dtype=float)
        return idx, (w / s)

    def bubble_pressure_psia(self, T_F: float, x: Sequence[float]) -> float:
        z = _normalize_comp(x, self.n_components)
        idx, w = self._anchor_blend(z)
        vals = []
        for j, ia in enumerate(idx.tolist()):
            vals.append(float(w[j]) * _interp_1d(self.T_grid_F, self.anchors[int(ia)].P_bubble_psia, float(T_F)))
        return float(np.sum(np.asarray(vals, dtype=float)))

    def bubble_temperature_F(self, P_psia: float, x: Sequence[float]) -> float:
        z = _normalize_comp(x, self.n_components)
        idx, w = self._anchor_blend(z)
        vals = []
        for j, ia in enumerate(idx.tolist()):
            vals.append(float(w[j]) * _interp_1d(self.P_grid_psia, self.anchors[int(ia)].T_bubble_F, float(P_psia)))
        return float(np.sum(np.asarray(vals, dtype=float)))


def build_top_end_saturation_table_from_case(
    *,
    excel_path: str,
    out_path: str,
    top_stage_count: int = 5,
    T_margin_F: float = 10.0,
    P_margin_psia: float = 20.0,
    n_T: int = 21,
    n_P: int = 21,
    extra_anchor_compositions: Optional[Sequence[Sequence[float]]] = None,
    silence_backend_console: bool = True,
) -> Path:
    case = load_case_from_excel(excel_path)
    col = build_column_spec_from_case(case)

    n_top = max(1, min(int(top_stage_count), int(col.n_stages)))
    T_ref = np.asarray(col.T_f[:n_top], dtype=float).reshape((n_top,))
    P_ref = np.asarray(col.P_psia[:n_top], dtype=float).reshape((n_top,))
    x0 = np.asarray(col.x0[:n_top, :], dtype=float).reshape((n_top, col.n_components))

    T_min = float(np.nanmin(T_ref) - abs(float(T_margin_F)))
    T_max = float(np.nanmax(T_ref) + abs(float(T_margin_F)))
    P_min = max(float(np.nanmin(P_ref) - abs(float(P_margin_psia))), 1.0)
    P_max = float(np.nanmax(P_ref) + abs(float(P_margin_psia)))
    if T_max <= T_min:
        T_max = T_min + 1.0
    if P_max <= P_min:
        P_max = P_min + 1.0

    T_grid = np.linspace(T_min, T_max, max(int(n_T), 2))
    P_grid = np.linspace(P_min, P_max, max(int(n_P), 2))

    from thermo import CEOSGas, CEOSLiquid, ChemicalConstantsPackage, FlashVL, PRMIX  # type: ignore
    from thermo.interaction_parameters import IPDB  # type: ignore

    thermo_ids = [_thermo_id_from_name(v) for v in list(col.components_excel)]
    constants, props = ChemicalConstantsPackage.from_IDs(thermo_ids)
    kijs = IPDB.get_ip_asymmetric_matrix("ChemSep PR", constants.CASs, "kij")
    eos_kwargs = dict(Tcs=constants.Tcs, Pcs=constants.Pcs, omegas=constants.omegas, kijs=kijs)
    liquid = CEOSLiquid(PRMIX, HeatCapacityGases=props.HeatCapacityGases, eos_kwargs=eos_kwargs)
    gas = CEOSGas(PRMIX, HeatCapacityGases=props.HeatCapacityGases, eos_kwargs=eos_kwargs)
    flasher = FlashVL(constants, props, liquid=liquid, gas=gas)

    anchor_candidates: List[Tuple[str, np.ndarray]] = []
    for i in range(n_top):
        anchor_candidates.append((f"top_stage_{i + 1}", _normalize_comp(x0[i, :], col.n_components)))
    if extra_anchor_compositions is not None:
        for i, z_ref in enumerate(extra_anchor_compositions, start=1):
            anchor_candidates.append((f"extra_{i}", _normalize_comp(z_ref, col.n_components)))

    anchors_unique: List[Tuple[str, np.ndarray]] = []
    seen: set[Tuple[float, ...]] = set()
    for name, z_ref in anchor_candidates:
        key = tuple(np.round(_normalize_comp(z_ref, col.n_components), 8).tolist())
        if key in seen:
            continue
        seen.add(key)
        anchors_unique.append((name, _normalize_comp(z_ref, col.n_components)))

    anchors_out: List[Dict[str, Any]] = []
    for name, z_ref in anchors_unique:
        p_bub = np.full(T_grid.shape, np.nan, dtype=float)
        t_bub = np.full(P_grid.shape, np.nan, dtype=float)
        for i, T_F in enumerate(T_grid):
            try:
                T_K = (float(T_F) - 32.0) * 5.0 / 9.0 + 273.15
                res = flasher.flash(T=float(T_K), VF=0.0, zs=z_ref.tolist())
                p_bub[i] = float(res.P) / 6894.757293168
            except Exception:
                p_bub[i] = np.nan
        for i, P_psia in enumerate(P_grid):
            try:
                P_pa = float(P_psia) * 6894.757293168
                res = flasher.flash(P=float(P_pa), VF=0.0, zs=z_ref.tolist())
                t_bub[i] = (float(res.T) - 273.15) * 9.0 / 5.0 + 32.0
            except Exception:
                t_bub[i] = np.nan
        anchors_out.append(
            {
                "name": str(name),
                "z_ref": z_ref.tolist(),
                "P_bubble_psia": p_bub.tolist(),
                "T_bubble_F": t_bub.tolist(),
            }
        )

    out_doc: Dict[str, Any] = {
        "format_version": 1,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": "Local PR-backed top-end saturation table",
        "excel_path": str(excel_path),
        "components_excel": list(col.components_excel),
        "components_dwsim": list(col.components_dwsim),
        "n_components": int(col.n_components),
        "top_stage_count": int(n_top),
        "T_grid_F": T_grid.tolist(),
        "P_grid_psia": P_grid.tolist(),
        "n_anchor_blend": 3,
        "anchor_blend_power": 2.0,
        "anchor_distance_eps": 1.0e-12,
        "anchors": anchors_out,
    }

    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(out_doc, indent=2, ensure_ascii=True), encoding="utf-8")
    return out_p


def _cli() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Build local PR-backed top-end saturation table.")
    p.add_argument("--excel", dest="excel_path", required=True)
    p.add_argument("--out", dest="out_path", required=True)
    p.add_argument("--top-stage-count", dest="top_stage_count", type=int, default=5)
    p.add_argument("--t-margin", dest="T_margin_F", type=float, default=10.0)
    p.add_argument("--p-margin", dest="P_margin_psia", type=float, default=20.0)
    p.add_argument("--n-t", dest="n_T", type=int, default=21)
    p.add_argument("--n-p", dest="n_P", type=int, default=21)
    p.add_argument(
        "--extra-anchor-z",
        dest="extra_anchor_z",
        action="append",
        default=None,
        help="Optional extra composition anchor as comma-separated mole fractions. Repeatable.",
    )
    p.add_argument("--verbose-backend", dest="silence_backend_console", action="store_false")
    args = p.parse_args()

    extra_anchor_compositions = None
    if args.extra_anchor_z:
        extra_anchor_compositions = [_parse_comp_csv(str(s), None) for s in list(args.extra_anchor_z)]

    out = build_top_end_saturation_table_from_case(
        excel_path=str(args.excel_path),
        out_path=str(args.out_path),
        top_stage_count=int(args.top_stage_count),
        T_margin_F=float(args.T_margin_F),
        P_margin_psia=float(args.P_margin_psia),
        n_T=int(args.n_T),
        n_P=int(args.n_P),
        extra_anchor_compositions=extra_anchor_compositions,
        silence_backend_console=bool(args.silence_backend_console),
    )
    print(f"Wrote top-end saturation table: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
