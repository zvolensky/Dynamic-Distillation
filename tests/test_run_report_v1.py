from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from docx import Document

from dynamic_distillation.run_report_v1 import _first_and_last, generate_run_report


def _summary_rows() -> list[dict[str, float]]:
    common = {
        "F_lbmolph": 100.0,
        "P_bot_psia": 225.0,
        "T_Distillate_F": 110.0,
        "T_sump_F": 220.0,
        "Q_reb_used_BTUph": 5.0e6,
        "total_reflux_used_lbmolph": 75.0,
        "V_condensed_in_lbmolph": 90.0,
        "boilup_realized_lbmolph": 95.0,
        "Top_level_ctrl_sp": 0.5,
        "Bottom_level_ctrl_sp": 0.5,
        "Distillate_x_A": 0.9,
        "Distillate_x_B": 0.1,
        "Bottoms_x_A": 0.2,
        "Bottoms_x_B": 0.8,
    }
    return [
        common | {
            "time_s": 0.0,
            "D_lbmolph": 40.0,
            "B_lbmolph": 60.0,
            "P_top_psia": 224.0,
            "P_top_ctrl_pv_psia": 224.0,
            "P_top_psia_spec": 220.0,
            "Q_cond_used_BTUph": -4.0e6,
            "Top_level_ctrl_pv": 0.48,
            "Bottom_level_ctrl_pv": 0.45,
            "steady_state_score": 2.0,
            "steady_state_flag": 0.0,
        },
        common | {
            "time_s": 60.0,
            "D_lbmolph": 42.0,
            "B_lbmolph": 58.0,
            "P_top_psia": 220.2,
            "P_top_ctrl_pv_psia": 220.2,
            "P_top_psia_spec": 220.0,
            "Q_cond_used_BTUph": -4.4e6,
            "Top_level_ctrl_pv": 0.50,
            "Bottom_level_ctrl_pv": 0.49,
            "steady_state_score": 0.5,
            "steady_state_flag": 1.0,
        },
    ]


def _profile_rows() -> list[dict[str, float | str]]:
    rows = []
    for t in (0.0, 60.0):
        for stage in (1, 2, 3):
            rows.append(
                {
                    "time_s": t,
                    "stage": stage,
                    "node_type": "stage",
                    "T_F": 100.0 + 10.0 * stage,
                    "P_psia_hyd": 220.0 + stage,
                    "L_out_used_lbmolph": 70.0 + stage,
                    "V_out_lbmolph": 80.0 + stage,
                    "x_A": 0.9 - 0.2 * (stage - 1),
                    "x_B": 0.1 + 0.2 * (stage - 1),
                    "y_A": 0.95 - 0.2 * (stage - 1),
                    "y_B": 0.05 + 0.2 * (stage - 1),
                }
            )
    return rows


def test_first_and_last_orders_by_simulation_time() -> None:
    frame = pd.DataFrame([{"time_s": 10.0, "value": 2}, {"time_s": 0.0, "value": 1}])
    start, end = _first_and_last(frame)
    assert start["value"] == 1
    assert end["value"] == 2


def test_generate_run_report_creates_readable_docx(tmp_path: Path) -> None:
    summary = tmp_path / "column_summary_test.csv"
    profile = tmp_path / "column_profile_test.csv"
    metadata = tmp_path / "run_metadata_test.json"
    pd.DataFrame(_summary_rows()).to_csv(summary, index=False)
    pd.DataFrame(_profile_rows()).to_csv(profile, index=False)
    metadata.write_text(
        json.dumps(
            {
                "run_id": "test",
                "run_name": "C3/C4 report smoke test",
                "run_description": "Automated report validation",
                "status": "completed",
                "started_at_local": "2026-07-10 10:00:00",
                "ended_at_local": "2026-07-10 10:01:00",
                "elapsed_wall_sec": 30.0,
                "final_time_s": 60.0,
                "excel_path": str(tmp_path / "case.xlsx"),
                "summary_csv": str(summary),
                "profile_csv": str(profile),
                "native_checkpoint_init": {
                    "loaded": True,
                    "path": str(tmp_path / "seed.npz"),
                    "source_final_time_s": 900.0,
                },
            }
        ),
        encoding="utf-8",
    )

    report = Path(
        generate_run_report(
            metadata,
            simulation_parameters={"runtime_mode": "hydraulic", "thermo_mode": "dwsim", "n_steps": 300},
            launch_command="python -m dynamic_distillation.dynamic_run_scaffold_v1 --n-steps 300",
        )
    )

    assert report.exists()
    assert report.stat().st_size > 20_000
    doc = Document(report)
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    assert "C3/C4 report smoke test" in text
    assert "Operating Snapshot" in text
    assert "Final Tray Profiles" in text
    assert "Exact Launch Command" in text
    assert len(doc.inline_shapes) >= 2
