from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
import ssl
from urllib.error import URLError
from urllib.request import urlopen

import numpy as np
from scipy.integrate import solve_ivp


SOURCE_DATA_URL = "https://skoge.folk.ntnu.no/book/matlab_m/cola/cola.dat"
SOURCE_MODEL_URL = "https://skoge.folk.ntnu.no/book/matlab_m/cola/colamod.m"


@dataclass(frozen=True)
class SourceCase:
    n_stages: int = 41
    feed_stage_bottom_based: int = 21
    alpha: float = 1.5
    taul_min: float = 0.063
    f0_kmol_min: float = 1.0
    qf0: float = 1.0
    l0_kmol_min: float = 2.70629
    v0_kmol_min: float = 3.20629
    lambda_k2: float = 0.0
    reflux_kmol_min: float = 2.70629
    boilup_kmol_min: float = 3.20629
    distillate_kmol_min: float = 0.5
    bottoms_kmol_min: float = 0.5
    feed_kmol_min: float = 1.01
    zf: float = 0.5
    qf: float = 1.0

    @property
    def l0b_kmol_min(self) -> float:
        return self.l0_kmol_min + self.qf0 * self.f0_kmol_min

    @property
    def v0t_kmol_min(self) -> float:
        return self.v0_kmol_min + (1.0 - self.qf0) * self.f0_kmol_min


def _fetch_text(url: str) -> str:
    try:
        with urlopen(url, timeout=20) as response:
            return response.read().decode("utf-8", errors="replace")
    except (ssl.SSLError, URLError):
        context = ssl._create_unverified_context()
        with urlopen(url, timeout=20, context=context) as response:
            return response.read().decode("utf-8", errors="replace")


def _parse_cola_dat(text: str) -> list[dict[str, float]]:
    marker = "STAGE"
    if marker not in text:
        raise ValueError("Could not find Skogestad cola.dat stage profile marker.")
    tail = text.split(marker, 1)[1]
    tokens = tail.replace("d", "e").replace("D", "e").split()
    while tokens:
        try:
            float(tokens[0])
            break
        except ValueError:
            tokens.pop(0)
    if len(tokens) < 5 * 41:
        raise ValueError(f"Expected at least 41 source stage rows, found {len(tokens) // 5}.")
    rows: list[dict[str, float]] = []
    for i in range(0, 5 * 41, 5):
        rows.append(
            {
                "stage": int(float(tokens[i])),
                "L": float(tokens[i + 1]),
                "V": float(tokens[i + 2]),
                "x": float(tokens[i + 3]),
                "y": float(tokens[i + 4]),
            }
        )
    return rows


def _initial_state_from_source(rows: list[dict[str, float]], case: SourceCase) -> np.ndarray:
    by_stage = {int(row["stage"]): row for row in rows}
    x = np.array([by_stage[i]["x"] for i in range(1, case.n_stages + 1)], dtype=float)
    m = np.full(case.n_stages, 0.5, dtype=float)
    return np.r_[x, m]


def colamod_rhs_min(_t_min: float, state: np.ndarray, case: SourceCase) -> np.ndarray:
    nt = case.n_stages
    nf = case.feed_stage_bottom_based
    x = np.asarray(state[:nt], dtype=float)
    m = np.asarray(state[nt : 2 * nt], dtype=float)

    y = np.empty(nt - 1, dtype=float)
    y[:] = case.alpha * x[: nt - 1] / (1.0 + (case.alpha - 1.0) * x[: nt - 1])

    v = np.full(nt - 1, case.boilup_kmol_min, dtype=float)
    v[nf - 1 :] += (1.0 - case.qf) * case.feed_kmol_min

    l = np.zeros(nt + 1, dtype=float)
    m0 = np.full(nt, 0.5, dtype=float)
    # MATLAB source is bottom based and 1-indexed:
    # i=2:NF uses L0b, i=NF+1:NT-1 uses L0, L(NT)=LT.
    for i_matlab in range(2, nf + 1):
        j = i_matlab - 1
        l[j] = case.l0b_kmol_min + (m[j] - m0[j]) / case.taul_min + case.lambda_k2 * (v[j - 1] - case.v0_kmol_min)
    for i_matlab in range(nf + 1, nt):
        j = i_matlab - 1
        l[j] = case.l0_kmol_min + (m[j] - m0[j]) / case.taul_min + case.lambda_k2 * (v[j - 1] - case.v0t_kmol_min)
    l[nt - 1] = case.reflux_kmol_min

    d_m = np.zeros(nt, dtype=float)
    d_mx = np.zeros(nt, dtype=float)

    for i_matlab in range(2, nt):
        j = i_matlab - 1
        d_m[j] = l[j + 1] - l[j] + v[j - 1] - v[j]
        d_mx[j] = l[j + 1] * x[j + 1] - l[j] * x[j] + v[j - 1] * y[j - 1] - v[j] * y[j]

    j = nf - 1
    d_m[j] += case.feed_kmol_min
    d_mx[j] += case.feed_kmol_min * case.zf

    d_m[0] = l[1] - v[0] - case.bottoms_kmol_min
    d_mx[0] = l[1] * x[1] - v[0] * y[0] - case.bottoms_kmol_min * x[0]

    d_m[nt - 1] = v[nt - 2] - case.reflux_kmol_min - case.distillate_kmol_min
    d_mx[nt - 1] = v[nt - 2] * y[nt - 2] - case.reflux_kmol_min * x[nt - 1] - case.distillate_kmol_min * x[nt - 1]

    d_x = (d_mx - x * d_m) / m
    return np.r_[d_x, d_m]


def simulate_reference(times_min: np.ndarray, case: SourceCase) -> np.ndarray:
    rows = _parse_cola_dat(_fetch_text(SOURCE_DATA_URL))
    x0 = _initial_state_from_source(rows, case)
    sol = solve_ivp(
        fun=lambda t, y: colamod_rhs_min(t, y, case),
        t_span=(float(times_min[0]), float(times_min[-1])),
        y0=x0,
        method="BDF",
        t_eval=np.asarray(times_min, dtype=float),
        rtol=1.0e-9,
        atol=1.0e-11,
    )
    if not sol.success:
        raise RuntimeError(f"Reference integration failed: {sol.message}")
    return np.asarray(sol.y.T, dtype=float)


def _float(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    if value is None or str(value).strip() == "":
        return float("nan")
    return float(value)


def _load_model_profile(path: Path) -> dict[float, dict[int, dict[str, float]]]:
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    out: dict[float, dict[int, dict[str, float]]] = {}
    for row in rows:
        if str(row.get("node_type", "")).strip().lower() != "stage":
            continue
        time_min = _float(row, "time_s") / 60.0
        stage = int(float(row["stage"]))
        out.setdefault(time_min, {})[stage] = {
            "x": _float(row, "x_N_butane"),
            "m": _float(row, "ML_lbmol"),
        }
    if not out:
        raise ValueError(f"No stage rows found in {path}")
    return out


def compare(profile_csv: Path, out_csv: Path | None = None) -> dict[str, float | str]:
    model_by_time = _load_model_profile(profile_csv)
    times_min = np.array(sorted(model_by_time), dtype=float)
    ref = simulate_reference(times_min, SourceCase())
    nt = SourceCase().n_stages

    rows: list[dict[str, float]] = []
    max_abs_x = 0.0
    max_abs_m = 0.0
    endpoint_max_abs_x = 0.0
    endpoint_max_abs_m = 0.0
    for ti, time_min in enumerate(times_min):
        for model_stage, model_row in sorted(model_by_time[float(time_min)].items()):
            source_stage = nt + 1 - model_stage
            ref_index = source_stage - 1
            x_ref = float(ref[ti, ref_index])
            m_ref = float(ref[ti, nt + ref_index])
            x_model = float(model_row["x"])
            m_model = float(model_row["m"])
            err_x = x_model - x_ref
            err_m = m_model - m_ref
            max_abs_x = max(max_abs_x, abs(err_x))
            max_abs_m = max(max_abs_m, abs(err_m))
            if model_stage in {1, nt}:
                endpoint_max_abs_x = max(endpoint_max_abs_x, abs(err_x))
                endpoint_max_abs_m = max(endpoint_max_abs_m, abs(err_m))
            rows.append(
                {
                    "time_min": float(time_min),
                    "model_stage_top_based": float(model_stage),
                    "source_stage_bottom_based": float(source_stage),
                    "x_model": x_model,
                    "x_ref": x_ref,
                    "x_error": err_x,
                    "m_model": m_model,
                    "m_ref": m_ref,
                    "m_error": err_m,
                }
            )

    if out_csv is not None:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with out_csv.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    t_final = float(times_min[-1])
    top = model_by_time[t_final][1]
    bottom = model_by_time[t_final][nt]
    ref_top_x = float(ref[-1, nt - 1])
    ref_bottom_x = float(ref[-1, 0])
    ref_bottom_m = float(ref[-1, nt])
    return {
        "profile_csv": str(profile_csv),
        "source_model_url": SOURCE_MODEL_URL,
        "final_time_min": t_final,
        "max_abs_x_error": max_abs_x,
        "max_abs_m_error": max_abs_m,
        "endpoint_max_abs_x_error": endpoint_max_abs_x,
        "endpoint_max_abs_m_error": endpoint_max_abs_m,
        "model_final_yD_top_x": float(top["x"]),
        "ref_final_yD_top_x": ref_top_x,
        "model_final_xB_bottom_x": float(bottom["x"]),
        "ref_final_xB_bottom_x": ref_bottom_x,
        "model_final_MB": float(bottom["m"]),
        "ref_final_MB": ref_bottom_m,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare a model run to a direct Python translation of Skogestad colamod.m.")
    parser.add_argument("profile_csv", type=Path)
    parser.add_argument("--out-csv", type=Path, default=None)
    parser.add_argument("--tol-x", type=float, default=1.0e-3)
    parser.add_argument("--tol-m", type=float, default=1.0e-3)
    args = parser.parse_args()

    result = compare(args.profile_csv, out_csv=args.out_csv)
    for key, value in result.items():
        if isinstance(value, float):
            print(f"{key}: {value:.12g}")
        else:
            print(f"{key}: {value}")
    ok = (
        float(result["endpoint_max_abs_x_error"]) <= float(args.tol_x)
        and float(result["endpoint_max_abs_m_error"]) <= float(args.tol_m)
    )
    print(f"pass: {int(ok)}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
