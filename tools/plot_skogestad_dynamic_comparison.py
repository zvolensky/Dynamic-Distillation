from __future__ import annotations

import argparse
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd

try:
    import matplotlib.pyplot as plt
except ModuleNotFoundError:  # pragma: no cover - exercised in lean environments.
    plt = None


def _endpoint_frame(df: pd.DataFrame, model_stage: int) -> pd.DataFrame:
    out = df.loc[df["model_stage_top_based"].astype(int) == int(model_stage)].copy()
    if out.empty:
        raise ValueError(f"No rows found for model stage {model_stage}.")
    return out.sort_values("time_min")


def _plot_pair(
    ax,
    time_min,
    model,
    reference,
    *,
    ylabel: str,
    title: str,
    err_ax=None,
) -> None:
    ax.plot(time_min, model, color="#005f73", linewidth=2.0, label="Model")
    ax.plot(time_min, reference, color="#ca6702", linewidth=1.8, linestyle="--", label="Skogestad colamod.m")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.28, linewidth=0.8)
    ax.legend(loc="best", frameon=False)
    if err_ax is not None:
        err_ax.plot(time_min, model - reference, color="#9b2226", linewidth=1.4)
        err_ax.axhline(0.0, color="#333333", linewidth=0.8)
        err_ax.set_ylabel("Model - ref")
        err_ax.set_xlabel("Time (min)")
        err_ax.grid(True, alpha=0.28, linewidth=0.8)


def _svg_points(xs, ys, *, x_min, x_max, y_min, y_max, left, top, width, height) -> str:
    def sx(x):
        denom = (x_max - x_min) or 1.0
        return left + (float(x) - x_min) / denom * width

    def sy(y):
        denom = (y_max - y_min) or 1.0
        return top + height - (float(y) - y_min) / denom * height

    return " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in zip(xs, ys))


def _svg_axis(
    *,
    title: str,
    ylabel: str,
    xlabel: str,
    series: list[tuple[str, list[float], list[float], str, str]],
    out_path: Path,
    width: int = 980,
    height: int = 620,
) -> Path:
    left, top, plot_w, plot_h = 82, 78, width - 132, height - 150
    all_x = [x for _label, xs, _ys, _color, _dash in series for x in xs]
    all_y = [y for _label, _xs, ys, _color, _dash in series for y in ys]
    x_min, x_max = min(all_x), max(all_x)
    y_min, y_max = min(all_y), max(all_y)
    pad_y = 0.05 * ((y_max - y_min) or 1.0)
    y_min -= pad_y
    y_max += pad_y

    def sx(x):
        return left + (float(x) - x_min) / ((x_max - x_min) or 1.0) * plot_w

    def sy(y):
        return top + plot_h - (float(y) - y_min) / ((y_max - y_min) or 1.0) * plot_h

    grid = []
    for i in range(6):
        x = left + i * plot_w / 5.0
        val = x_min + i * (x_max - x_min) / 5.0
        grid.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#dddddd"/>')
        grid.append(f'<text x="{x:.2f}" y="{top + plot_h + 28}" text-anchor="middle" font-size="13">{val:.0f}</text>')
    for i in range(6):
        y = top + i * plot_h / 5.0
        val = y_max - i * (y_max - y_min) / 5.0
        grid.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="#dddddd"/>')
        grid.append(f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" font-size="13">{val:.5g}</text>')

    lines = []
    legend = []
    for idx, (label, xs, ys, color, dash) in enumerate(series):
        pts = _svg_points(xs, ys, x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max, left=left, top=top, width=plot_w, height=plot_h)
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        lines.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.4"{dash_attr}/>')
        ly = top + 18 + idx * 24
        lx = left + plot_w - 225
        legend.append(f'<line x1="{lx}" y1="{ly}" x2="{lx + 34}" y2="{ly}" stroke="{color}" stroke-width="2.4"{dash_attr}/>')
        legend.append(f'<text x="{lx + 44}" y="{ly + 5}" font-size="14">{escape(label)}</text>')

    body = "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#ffffff"/>',
            f'<text x="{width / 2:.1f}" y="34" text-anchor="middle" font-size="22" font-family="Arial, sans-serif">{escape(title)}</text>',
            *grid,
            f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#333333"/>',
            *lines,
            *legend,
            f'<text x="{width / 2:.1f}" y="{height - 28}" text-anchor="middle" font-size="15">{escape(xlabel)}</text>',
            f'<text x="24" y="{top + plot_h / 2:.1f}" text-anchor="middle" font-size="15" transform="rotate(-90 24 {top + plot_h / 2:.1f})">{escape(ylabel)}</text>',
            "</svg>",
        ]
    )
    out_path.write_text(body, encoding="utf-8")
    return out_path


def _plot_svg_fallback(top: pd.DataFrame, bottom: pd.DataFrame, out_dir: Path) -> list[Path]:
    paths: list[Path] = []
    paths.append(
        _svg_axis(
            title="Skogestad Column A +1% Feed Step: Top / Distillate Composition",
            ylabel="Light component mole fraction",
            xlabel="Time (min)",
            series=[
                ("Model yD/top", top["time_min"].tolist(), top["x_model"].tolist(), "#005f73", ""),
                ("Skogestad colamod.m", top["time_min"].tolist(), top["x_ref"].tolist(), "#ca6702", "7 5"),
            ],
            out_path=out_dir / "skogestad_feed_step_top_composition_comparison.svg",
        )
    )
    paths.append(
        _svg_axis(
            title="Skogestad Column A +1% Feed Step: Bottom Composition",
            ylabel="Light component mole fraction",
            xlabel="Time (min)",
            series=[
                ("Model xB/bottom", bottom["time_min"].tolist(), bottom["x_model"].tolist(), "#005f73", ""),
                ("Skogestad colamod.m", bottom["time_min"].tolist(), bottom["x_ref"].tolist(), "#ca6702", "7 5"),
            ],
            out_path=out_dir / "skogestad_feed_step_bottom_composition_comparison.svg",
        )
    )
    paths.append(
        _svg_axis(
            title="Skogestad Column A +1% Feed Step: Reboiler Holdup",
            ylabel="Reboiler holdup",
            xlabel="Time (min)",
            series=[
                ("Model MB", bottom["time_min"].tolist(), bottom["m_model"].tolist(), "#005f73", ""),
                ("Skogestad colamod.m", bottom["time_min"].tolist(), bottom["m_ref"].tolist(), "#ca6702", "7 5"),
            ],
            out_path=out_dir / "skogestad_feed_step_reboiler_holdup_comparison.svg",
        )
    )
    paths.append(
        _svg_axis(
            title="Skogestad Column A +1% Feed Step: Endpoint Composition Overlay",
            ylabel="Light component mole fraction",
            xlabel="Time (min)",
            series=[
                ("Model yD/top", top["time_min"].tolist(), top["x_model"].tolist(), "#005f73", ""),
                ("Reference yD/top", top["time_min"].tolist(), top["x_ref"].tolist(), "#005f73", "7 5"),
                ("Model xB/bottom", bottom["time_min"].tolist(), bottom["x_model"].tolist(), "#ca6702", ""),
                ("Reference xB/bottom", bottom["time_min"].tolist(), bottom["x_ref"].tolist(), "#ca6702", "7 5"),
            ],
            out_path=out_dir / "skogestad_feed_step_endpoint_overlay.svg",
        )
    )
    return paths


def plot_comparison(comparison_csv: Path, out_dir: Path) -> list[Path]:
    df = pd.read_csv(comparison_csv)
    required = {
        "time_min",
        "model_stage_top_based",
        "x_model",
        "x_ref",
        "m_model",
        "m_ref",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{comparison_csv} is missing required columns: {sorted(missing)}")

    out_dir.mkdir(parents=True, exist_ok=True)
    top = _endpoint_frame(df, 1)
    bottom = _endpoint_frame(df, 41)

    if plt is None:
        return _plot_svg_fallback(top, bottom, out_dir)

    paths: list[Path] = []

    fig, axes = plt.subplots(
        2,
        2,
        figsize=(11.0, 7.2),
        sharex="col",
        gridspec_kw={"height_ratios": [3.0, 1.0]},
        constrained_layout=True,
    )
    _plot_pair(
        axes[0, 0],
        top["time_min"],
        top["x_model"],
        top["x_ref"],
        ylabel="Light component mole fraction",
        title="Top / Distillate Composition",
        err_ax=axes[1, 0],
    )
    _plot_pair(
        axes[0, 1],
        bottom["time_min"],
        bottom["x_model"],
        bottom["x_ref"],
        ylabel="Light component mole fraction",
        title="Bottom Composition",
        err_ax=axes[1, 1],
    )
    fig.suptitle("Skogestad Column A +1% Feed Step: Composition Response", fontsize=14)
    comp_path = out_dir / "skogestad_feed_step_composition_comparison.png"
    fig.savefig(comp_path, dpi=180)
    plt.close(fig)
    paths.append(comp_path)

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(9.5, 6.5),
        sharex=True,
        gridspec_kw={"height_ratios": [3.0, 1.0]},
        constrained_layout=True,
    )
    _plot_pair(
        axes[0],
        bottom["time_min"],
        bottom["m_model"],
        bottom["m_ref"],
        ylabel="Reboiler holdup",
        title="Reboiler Holdup Response",
        err_ax=axes[1],
    )
    fig.suptitle("Skogestad Column A +1% Feed Step: Reboiler Holdup", fontsize=14)
    holdup_path = out_dir / "skogestad_feed_step_reboiler_holdup_comparison.png"
    fig.savefig(holdup_path, dpi=180)
    plt.close(fig)
    paths.append(holdup_path)

    fig, ax = plt.subplots(figsize=(9.5, 5.8), constrained_layout=True)
    ax.plot(top["time_min"], top["x_model"], color="#005f73", linewidth=2.0, label="Model yD/top")
    ax.plot(top["time_min"], top["x_ref"], color="#005f73", linewidth=1.8, linestyle="--", label="Reference yD/top")
    ax.plot(bottom["time_min"], bottom["x_model"], color="#ca6702", linewidth=2.0, label="Model xB/bottom")
    ax.plot(bottom["time_min"], bottom["x_ref"], color="#ca6702", linewidth=1.8, linestyle="--", label="Reference xB/bottom")
    ax.set_title("Endpoint Composition Responses")
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Light component mole fraction")
    ax.grid(True, alpha=0.28, linewidth=0.8)
    ax.legend(loc="best", frameon=False)
    overlay_path = out_dir / "skogestad_feed_step_endpoint_overlay.png"
    fig.savefig(overlay_path, dpi=180)
    plt.close(fig)
    paths.append(overlay_path)

    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot model-vs-reference Skogestad dynamic comparison traces.")
    parser.add_argument(
        "comparison_csv",
        type=Path,
        help="CSV from tools/compare_skogestad_dynamic_response.py.",
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    out_dir = args.out_dir or args.comparison_csv.parent
    for path in plot_comparison(args.comparison_csv, out_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
