from __future__ import annotations

import argparse
import csv
from pathlib import Path
import ssl
from urllib.error import URLError
from urllib.request import urlopen


SOURCE_URL = "https://skoge.folk.ntnu.no/book/matlab_m/cola/cola.dat"


def _fetch_source_text() -> str:
    try:
        with urlopen(SOURCE_URL, timeout=20) as response:
            return response.read().decode("utf-8", errors="replace")
    except (ssl.SSLError, URLError):
        context = ssl._create_unverified_context()
        with urlopen(SOURCE_URL, timeout=20, context=context) as response:
            return response.read().decode("utf-8", errors="replace")


def _parse_cola_dat(text: str) -> dict[int, dict[str, float]]:
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
    rows: dict[int, dict[str, float]] = {}
    for i in range(0, 5 * 41, 5):
        stage = int(float(tokens[i]))
        rows[stage] = {
            "L": float(tokens[i + 1]),
            "V": float(tokens[i + 2]),
            "x": float(tokens[i + 3]),
            "y": float(tokens[i + 4]),
        }
    return rows


def _float(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    if value is None or str(value).strip() == "":
        return float("nan")
    return float(value)


def _latest_time_stage_rows(profile_csv: Path) -> list[dict[str, str]]:
    with profile_csv.open(newline="") as f:
        rows = list(csv.DictReader(f))
    stage_rows = [row for row in rows if str(row.get("node_type", "")).strip().lower() == "stage"]
    if not stage_rows:
        raise ValueError(f"No stage rows found in {profile_csv}")
    latest = max(_float(row, "time_s") for row in stage_rows)
    return [row for row in stage_rows if abs(_float(row, "time_s") - latest) <= 1.0e-9]


def compare(profile_csv: Path) -> dict[str, float | str]:
    source = _parse_cola_dat(_fetch_source_text())
    rows = _latest_time_stage_rows(profile_csv)
    n = len(rows)
    errors_x: list[float] = []
    errors_y: list[float] = []
    endpoint: dict[str, float] = {}
    for row in rows:
        model_stage = int(float(row["stage"]))
        source_stage = n + 1 - model_stage
        expected = source[source_stage]
        x_model = _float(row, "x_N_butane")
        y_model = _float(row, "y_N_butane")
        if model_stage == 1:
            # The source total-condenser row has Y=0 by convention; compare x only there.
            y_model = expected["y"]
        err_x = x_model - expected["x"]
        err_y = y_model - expected["y"]
        errors_x.append(abs(err_x))
        errors_y.append(abs(err_y))
        if model_stage in {1, n}:
            name = "top" if model_stage == 1 else "bottom"
            endpoint[f"{name}_x_model"] = x_model
            endpoint[f"{name}_x_source"] = expected["x"]
            endpoint[f"{name}_x_error"] = err_x
    return {
        "profile_csv": str(profile_csv),
        "n_stage_rows": float(n),
        "max_abs_x_error": max(errors_x),
        "max_abs_y_error": max(errors_y),
        **endpoint,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile_csv", type=Path)
    parser.add_argument("--tol-x", type=float, default=1.0e-3)
    parser.add_argument("--tol-y", type=float, default=1.0e-3)
    args = parser.parse_args()

    result = compare(args.profile_csv)
    for key, value in result.items():
        if isinstance(value, float):
            print(f"{key}: {value:.12g}")
        else:
            print(f"{key}: {value}")
    ok = (
        float(result["max_abs_x_error"]) <= float(args.tol_x)
        and float(result["max_abs_y_error"]) <= float(args.tol_y)
    )
    print(f"pass: {int(ok)}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
