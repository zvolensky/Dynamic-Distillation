from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def _sanitize_filename(value: str) -> str:
    keep = []
    for ch in value:
        if ch.isalnum() or ch in ("-", "_"):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep)


def _ensure_output_dir(path: Path | None, summary_csv: Path) -> Path:
    if path is not None:
        path.mkdir(parents=True, exist_ok=True)
        return path
    out = summary_csv.parent / "analysis_charts"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _plot_summary_overview(summary: pd.DataFrame, output_dir: Path) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)

    axes[0].plot(summary["time_s"], summary["P_top_psia"], label="P_top")
    axes[0].plot(summary["time_s"], summary["P_top_psia_spec"], "--", label="P_top SP")
    axes[0].set_ylabel("Top P (psia)")
    axes[0].legend(loc="best")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(summary["time_s"], summary["xD_comp_pv"], label="xD(C4)")
    axes[1].plot(summary["time_s"], summary["xD_comp_sp"], "--", label="xD SP")
    axes[1].set_ylabel("xD(C4)")
    axes[1].legend(loc="best")
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(summary["time_s"], summary["dM_total_dt_lbmolph"], label="dM/dt")
    axes[2].plot(summary["time_s"], summary["net_F_minus_D_minus_B_lbmolph"], "--", label="F-D-B")
    axes[2].set_ylabel("lbmol/h")
    axes[2].legend(loc="best")
    axes[2].grid(True, alpha=0.3)

    axes[3].plot(summary["time_s"], summary["steady_state_score"], label="SS score")
    axes[3].set_ylabel("Score")
    axes[3].set_xlabel("Time (s)")
    axes[3].legend(loc="best")
    axes[3].grid(True, alpha=0.3)

    fig.suptitle("Run Overview")
    fig.tight_layout()
    fig.savefig(output_dir / "01_run_overview.png", dpi=160)
    plt.close(fig)


def _plot_controller_pack(summary: pd.DataFrame, output_dir: Path) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)

    axes[0].plot(summary["time_s"], summary["Q_cond_cmd_BTUph"] / 1.0e6, label="Qcond cmd")
    axes[0].plot(summary["time_s"], summary["Q_cond_used_BTUph"] / 1.0e6, "--", label="Qcond used")
    axes[0].set_ylabel("MMBtu/h")
    axes[0].legend(loc="best")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(summary["time_s"], summary["P_top_ctrl_p_term"] / 1.0e6, label="Pressure P")
    axes[1].plot(summary["time_s"], summary["P_top_ctrl_i_term"] / 1.0e6, label="Pressure I")
    axes[1].set_ylabel("MMBtu/h")
    axes[1].legend(loc="best")
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(summary["time_s"], summary["Top_level_ctrl_u_unclamped_lbmolph"], label="D cmd")
    axes[2].plot(summary["time_s"], summary["Bottom_level_ctrl_u_unclamped_lbmolph"], label="B cmd")
    axes[2].set_ylabel("lbmol/h")
    axes[2].legend(loc="best")
    axes[2].grid(True, alpha=0.3)

    axes[3].plot(summary["time_s"], summary["Reflux_cmd_lbmolph"], label="Reflux cmd")
    if "Boilup_cmd_lbmolph" in summary.columns:
        axes[3].plot(summary["time_s"], summary["Boilup_cmd_lbmolph"], label="Boilup cmd")
    axes[3].set_ylabel("lbmol/h")
    axes[3].set_xlabel("Time (s)")
    axes[3].legend(loc="best")
    axes[3].grid(True, alpha=0.3)

    fig.suptitle("Controller Outputs and Internal Terms")
    fig.tight_layout()
    fig.savefig(output_dir / "02_controller_pack.png", dpi=160)
    plt.close(fig)


def _plot_inventory_pack(summary: pd.DataFrame, output_dir: Path) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)

    axes[0].plot(summary["time_s"], summary["M_total_lbmol"], label="M total")
    axes[0].set_ylabel("lbmol")
    axes[0].legend(loc="best")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(summary["time_s"], summary["Top_level_ctrl_pv"], label="Top PV")
    axes[1].plot(summary["time_s"], summary["Top_level_ctrl_sp"], "--", label="Top SP")
    axes[1].set_ylabel("Top level PV")
    axes[1].legend(loc="best")
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(summary["time_s"], summary["Bottom_level_ctrl_pv"], label="Bottom PV")
    axes[2].plot(summary["time_s"], summary["Bottom_level_ctrl_sp"], "--", label="Bottom SP")
    axes[2].set_ylabel("Bottom level PV")
    axes[2].legend(loc="best")
    axes[2].grid(True, alpha=0.3)

    axes[3].plot(summary["time_s"], summary["F_lbmolph"], label="Feed")
    axes[3].plot(summary["time_s"], summary["D_lbmolph"], label="D")
    axes[3].plot(summary["time_s"], summary["B_lbmolph"], label="B")
    axes[3].plot(summary["time_s"], summary["D_lbmolph"] + summary["B_lbmolph"], "--", label="D+B")
    axes[3].set_ylabel("lbmol/h")
    axes[3].set_xlabel("Time (s)")
    axes[3].legend(loc="best")
    axes[3].grid(True, alpha=0.3)

    fig.suptitle("Inventory and Boundary Flows")
    fig.tight_layout()
    fig.savefig(output_dir / "03_inventory_and_boundary_flows.png", dpi=160)
    plt.close(fig)


def _plot_distillate_drum_pack(summary: pd.DataFrame, output_dir: Path) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)

    axes[0].plot(summary["time_s"], summary["P_top_drum_psia"], label="Top drum P")
    axes[0].plot(summary["time_s"], summary["P_top_psia"], "--", label="Top column P")
    axes[0].plot(summary["time_s"], summary["P_top_psia_spec"], ":", label="Top P SP")
    axes[0].set_ylabel("psia")
    axes[0].legend(loc="best")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(summary["time_s"], summary["Distillate_L_lbmol"], label="Drum liquid holdup")
    axes[1].plot(summary["time_s"], summary["MV_top_drum_lbmol"], label="Drum vapor holdup")
    axes[1].set_ylabel("lbmol")
    axes[1].legend(loc="best")
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(summary["time_s"], summary["Top_level_ctrl_pv"], label="Top level PV")
    axes[2].plot(summary["time_s"], summary["Top_level_ctrl_sp"], "--", label="Top level SP")
    axes[2].plot(summary["time_s"], summary["Top_level_ctrl_p_term"], label="Top LC P")
    axes[2].plot(summary["time_s"], summary["Top_level_ctrl_i_term"], label="Top LC I")
    axes[2].set_ylabel("PV / lbmol/h")
    axes[2].legend(loc="best")
    axes[2].grid(True, alpha=0.3)

    axes[3].plot(summary["time_s"], summary["D_lbmolph"], label="Distillate flow D")
    axes[3].plot(summary["time_s"], summary["Top_level_ctrl_u_unclamped_lbmolph"], "--", label="Top LC cmd")
    axes[3].plot(summary["time_s"], summary["V_condensed_in_lbmolph"], label="Condensed in")
    axes[3].set_ylabel("lbmol/h")
    axes[3].set_xlabel("Time (s)")
    axes[3].legend(loc="best")
    axes[3].grid(True, alpha=0.3)

    fig.suptitle("Distillate Drum and Top Controller")
    fig.tight_layout()
    fig.savefig(output_dir / "12_distillate_drum_and_top_controller.png", dpi=160)
    plt.close(fig)


def _plot_bottoms_pack(summary: pd.DataFrame, output_dir: Path) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)

    axes[0].plot(summary["time_s"], summary["Bottoms_L_lbmol"], label="Sump liquid holdup")
    axes[0].plot(summary["time_s"], summary["Bottom_level_ctrl_pv"], "--", label="Bottom PV")
    axes[0].plot(summary["time_s"], summary["Bottom_level_ctrl_sp"], ":", label="Bottom SP")
    axes[0].set_ylabel("lbmol")
    axes[0].legend(loc="best")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(summary["time_s"], summary["Bottom_level_ctrl_p_term"], label="Bottom LC P")
    axes[1].plot(summary["time_s"], summary["Bottom_level_ctrl_i_term"], label="Bottom LC I")
    axes[1].plot(summary["time_s"], summary["Bottom_level_ctrl_u_unclamped_lbmolph"], "--", label="Bottom LC cmd")
    axes[1].set_ylabel("lbmol/h")
    axes[1].legend(loc="best")
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(summary["time_s"], summary["B_lbmolph"], label="Bottoms flow B")
    axes[2].plot(summary["time_s"], summary["Q_reb_used_BTUph"] / 1.0e6, label="Qreb used (MMBtu/h)")
    axes[2].plot(summary["time_s"], summary["Boilup_cmd_lbmolph"], label="Boilup cmd")
    axes[2].set_ylabel("Mixed units")
    axes[2].legend(loc="best")
    axes[2].grid(True, alpha=0.3)

    axes[3].plot(summary["time_s"], summary["T_sump_F"], label="Sump T")
    axes[3].plot(summary["time_s"], summary["Bottoms_x_n_Propane"], label="xB(C3)")
    axes[3].set_ylabel("F / mole frac")
    axes[3].set_xlabel("Time (s)")
    axes[3].legend(loc="best")
    axes[3].grid(True, alpha=0.3)

    fig.suptitle("Bottoms Side and Bottom Controller")
    fig.tight_layout()
    fig.savefig(output_dir / "13_bottoms_and_bottom_controller.png", dpi=160)
    plt.close(fig)


def _plot_stage_set(
    profile: pd.DataFrame,
    output_dir: Path,
    stages: list[int],
    value_col: str,
    title: str,
    ylabel: str,
    filename: str,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    for stage in stages:
        subset = profile[profile["stage"] == stage]
        if subset.empty:
            continue
        ax.plot(subset["time_s"], subset[value_col], label=f"Stage {stage}")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Time (s)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", ncol=3)
    fig.tight_layout()
    fig.savefig(output_dir / filename, dpi=160)
    plt.close(fig)


def _plot_stage_heatmap(
    profile: pd.DataFrame,
    output_dir: Path,
    value_col: str,
    title: str,
    filename: str,
    cmap: str = "viridis",
) -> None:
    pivot = profile.pivot(index="stage", columns="time_s", values=value_col).sort_index()
    fig, ax = plt.subplots(figsize=(13, 6))
    im = ax.imshow(pivot.values, aspect="auto", origin="lower", cmap=cmap)
    ax.set_title(title)
    ax.set_ylabel("Stage")
    ax.set_xlabel("Time index")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([str(int(v)) for v in pivot.index])
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label(value_col)
    fig.tight_layout()
    fig.savefig(output_dir / filename, dpi=160)
    plt.close(fig)


def _focus_filename(prefix_num: int, stem: str, t_min: float, t_max: float) -> str:
    return f"{prefix_num:02d}_{stem}_{int(t_min)}_{int(t_max)}s.png"


def _plot_phase_relax_focus(
    profile: pd.DataFrame,
    output_dir: Path,
    stages: list[int],
    t_min: float,
    t_max: float,
    *,
    prefix_num: int = 14,
) -> None:
    window = profile[(profile["time_s"] >= t_min) & (profile["time_s"] <= t_max)].copy()
    if window.empty:
        return
    window["bubble_minus_state_F"] = window["T_bubble_target_F_tray"] - window["T_F"]
    window["vapor_flow_gap_lbmolph"] = window["vflow_energy_calc_lbmolph"] - window["vflow_energy_used_lbmolph"]

    fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)
    specs = [
        ("dMLdt_phase_relax_lbmolps", "Phase Relaxation (lbmol/s)"),
        ("stage_energy_balance_resid_BTUps", "Energy Residual (BTU/s)"),
        ("vapor_flow_gap_lbmolph", "Vapor Calc - Used (lbmol/h)"),
        ("bubble_minus_state_F", "T_bubble - T_state (F)"),
    ]

    for ax, (col, ylabel) in zip(axes, specs):
        for stage in stages:
            subset = window[window["stage"] == stage]
            if subset.empty:
                continue
            ax.plot(subset["time_s"], subset[col], label=f"Stage {stage}")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best", ncol=3)

    axes[-1].set_xlabel("Time (s)")
    fig.suptitle(f"Phase-Relaxation Focus ({int(t_min)}-{int(t_max)} s)")
    fig.tight_layout()
    fig.savefig(output_dir / _focus_filename(prefix_num, "phase_relax_focus", t_min, t_max), dpi=160)
    plt.close(fig)


def _plot_phase_driver_focus(
    profile: pd.DataFrame,
    output_dir: Path,
    stages: list[int],
    t_min: float,
    t_max: float,
    *,
    prefix_num: int = 15,
) -> None:
    required = {
        "eq_target_vapor_total_lbmol_tray",
        "eq_target_vapor_delta_lbmol_tray",
        "eq_target_vapor_fraction_tray",
        "eq_current_vapor_fraction_tray",
        "eq_phase_change_lbmolps_tray",
    }
    if not required.issubset(set(profile.columns)):
        return
    window = profile[(profile["time_s"] >= t_min) & (profile["time_s"] <= t_max)].copy()
    if window.empty:
        return

    fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)
    specs = [
        ("eq_target_vapor_total_lbmol_tray", "Target vapor holdup (lbmol)"),
        ("eq_target_vapor_delta_lbmol_tray", "Target - current vapor holdup (lbmol)"),
        ("eq_phase_change_lbmolps_tray", "Eq phase change (lbmol/s)"),
        ("eq_target_vapor_fraction_tray", "Target vapor fraction"),
    ]

    for ax, (col, ylabel) in zip(axes, specs):
        for stage in stages:
            subset = window[window["stage"] == stage]
            if subset.empty:
                continue
            ax.plot(subset["time_s"], subset[col], label=f"Stage {stage} {col}")
            if col == "eq_target_vapor_fraction_tray":
                ax.plot(
                    subset["time_s"],
                    subset["eq_current_vapor_fraction_tray"],
                    "--",
                    label=f"Stage {stage} current vapor frac",
                )
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best", ncol=2, fontsize=8)

    axes[-1].set_xlabel("Time (s)")
    fig.suptitle(f"Phase-Relaxation Driver Focus ({int(t_min)}-{int(t_max)} s)")
    fig.tight_layout()
    fig.savefig(output_dir / _focus_filename(prefix_num, "phase_driver_focus", t_min, t_max), dpi=160)
    plt.close(fig)


def _plot_flash_sensitivity_focus(
    profile: pd.DataFrame,
    output_dir: Path,
    stages: list[int],
    t_min: float,
    t_max: float,
    *,
    prefix_num: int = 16,
) -> None:
    required = {
        "beta_eq_tray",
        "eq_flash_mv_total_lbmol_tray",
        "K_thermo_n_Propane",
        "K_thermo_n_Butane",
    }
    if not required.issubset(set(profile.columns)):
        return
    window = profile[(profile["time_s"] >= t_min) & (profile["time_s"] <= t_max)].copy()
    if window.empty:
        return

    fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)
    specs = [
        ("K_thermo_n_Propane", "K(C3)"),
        ("K_thermo_n_Butane", "K(C4)"),
        ("beta_eq_tray", "beta_eq"),
        ("eq_flash_mv_total_lbmol_tray", "Flash MV total (lbmol)"),
    ]

    for ax, (col, ylabel) in zip(axes, specs):
        for stage in stages:
            subset = window[window["stage"] == stage]
            if subset.empty:
                continue
            ax.plot(subset["time_s"], subset[col], label=f"Stage {stage}")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best", ncol=3)

    axes[-1].set_xlabel("Time (s)")
    fig.suptitle(f"Flash Sensitivity Focus ({int(t_min)}-{int(t_max)} s)")
    fig.tight_layout()
    fig.savefig(output_dir / _focus_filename(prefix_num, "flash_sensitivity_focus", t_min, t_max), dpi=160)
    plt.close(fig)


def generate_chart_pack(summary_csv: Path, profile_csv: Path, output_dir: Path | None = None) -> Path:
    summary = pd.read_csv(summary_csv)
    profile = pd.read_csv(profile_csv)
    out = _ensure_output_dir(output_dir, summary_csv)

    tracked_stages = [2, 7, 12, 16, 20]
    available_stages = sorted(set(profile["stage"].astype(int).tolist()))
    stages = [stage for stage in tracked_stages if stage in available_stages]
    if not stages:
        stages = available_stages[: min(5, len(available_stages))]

    _plot_summary_overview(summary, out)
    _plot_controller_pack(summary, out)
    _plot_inventory_pack(summary, out)
    _plot_distillate_drum_pack(summary, out)
    _plot_bottoms_pack(summary, out)
    _plot_stage_set(profile, out, stages, "T_F", "Selected Stage Temperatures", "F", "04_stage_temperatures.png")
    _plot_stage_set(profile, out, stages, "ML_lbmol", "Selected Stage Liquid Holdup", "lbmol", "05_stage_liquid_holdup.png")
    _plot_stage_set(
        profile,
        out,
        stages,
        "dMLdt_phase_relax_lbmolps",
        "Selected Stage Phase-Relaxation Rate",
        "lbmol/s",
        "06_stage_phase_relax.png",
    )
    _plot_stage_set(
        profile,
        out,
        stages,
        "stage_energy_balance_resid_BTUps",
        "Selected Stage Energy Residual",
        "BTU/s",
        "07_stage_energy_residual.png",
    )

    profile = profile.copy()
    profile["vapor_flow_gap_lbmolph"] = profile["vflow_energy_calc_lbmolph"] - profile["vflow_energy_used_lbmolph"]
    _plot_stage_set(
        profile,
        out,
        stages,
        "vapor_flow_gap_lbmolph",
        "Selected Stage Vapor Flow Calc - Used",
        "lbmol/h",
        "08_stage_vapor_gap.png",
    )

    _plot_stage_heatmap(profile, out, "T_F", "Stage Temperature Heatmap", "09_stage_temperature_heatmap.png", cmap="plasma")
    _plot_stage_heatmap(
        profile,
        out,
        "stage_energy_balance_resid_BTUps",
        "Stage Energy Residual Heatmap",
        "10_stage_energy_residual_heatmap.png",
        cmap="coolwarm",
    )
    _plot_stage_heatmap(
        profile,
        out,
        "dMLdt_phase_relax_lbmolps",
        "Stage Phase-Relaxation Heatmap",
        "11_stage_phase_relax_heatmap.png",
        cmap="coolwarm",
    )
    _plot_phase_relax_focus(profile, out, [9, 10, 11], 300.0, 450.0, prefix_num=14)
    _plot_phase_driver_focus(profile, out, [9, 10, 11], 300.0, 450.0, prefix_num=15)
    _plot_flash_sensitivity_focus(profile, out, [9, 10, 11], 300.0, 450.0, prefix_num=16)
    _plot_phase_relax_focus(profile, out, [2, 10, 12, 16], 510.0, 600.0, prefix_num=17)
    _plot_phase_driver_focus(profile, out, [2, 10, 12, 16], 510.0, 600.0, prefix_num=18)
    _plot_flash_sensitivity_focus(profile, out, [2, 10, 12, 16], 510.0, 600.0, prefix_num=19)

    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a compact chart pack for a dynamic distillation run.")
    parser.add_argument("--summary-csv", type=Path, required=True)
    parser.add_argument("--profile-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    out = generate_chart_pack(args.summary_csv, args.profile_csv, args.output_dir)
    print(out)


if __name__ == "__main__":
    main()
