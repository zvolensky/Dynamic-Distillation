import csv

from tools.rank_dynamic_one_step_initialization_candidates import rank_candidates


def _write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _make_run(root, name, *, score, rel, vapor_rhs):
    run = root / name
    run.mkdir()
    _write_csv(
        run / "column_summary_test.csv",
        [
            {
                "time_s": "0.2",
                "steady_state_score": str(score),
                "ss_max_rel_state_rate_per_s": str(rel),
                "ss_max_temp_rate_F_per_s": "0.0",
            }
        ],
    )
    _write_csv(
        run / "column_profile_test.csv",
        [
            {
                "time_s": "0.0",
                "node_type": "stage",
                "stage": "1",
                "MV_lbmol": "1",
                "y_A": "0.5",
                "y_target_A": "0.5",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "0",
                "tray_V_equilibrium_transfer_lbmolps_A": "0",
                "tray_V_final_rhs_lbmolps_A": "0",
            },
            {
                "time_s": "0.0",
                "node_type": "stage",
                "stage": "2",
                "MV_lbmol": "10",
                "y_A": "0.4",
                "y_target_A": "0.35",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "1.0",
                "tray_V_equilibrium_transfer_lbmolps_A": "-1.0",
                "tray_V_final_rhs_lbmolps_A": str(vapor_rhs),
            },
            {
                "time_s": "0.0",
                "node_type": "stage",
                "stage": "3",
                "MV_lbmol": "1",
                "y_A": "0.5",
                "y_target_A": "0.5",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "0",
                "tray_V_equilibrium_transfer_lbmolps_A": "0",
                "tray_V_final_rhs_lbmolps_A": "0",
            },
            {
                "time_s": "0.2",
                "node_type": "stage",
                "stage": "1",
                "MV_lbmol": "1",
                "y_A": "0.5",
                "y_target_A": "0.5",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "0",
                "tray_V_equilibrium_transfer_lbmolps_A": "0",
                "tray_V_final_rhs_lbmolps_A": "0",
            },
            {
                "time_s": "0.2",
                "node_type": "stage",
                "stage": "2",
                "MV_lbmol": "10",
                "y_A": "0.4",
                "y_target_A": "0.35",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "1.0",
                "tray_V_equilibrium_transfer_lbmolps_A": "-1.0",
                "tray_V_final_rhs_lbmolps_A": str(vapor_rhs),
            },
            {
                "time_s": "0.2",
                "node_type": "stage",
                "stage": "3",
                "MV_lbmol": "1",
                "y_A": "0.5",
                "y_target_A": "0.5",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "0",
                "tray_V_equilibrium_transfer_lbmolps_A": "0",
                "tray_V_final_rhs_lbmolps_A": "0",
            },
        ],
    )
    return run


def test_rank_dynamic_one_step_initialization_candidates_orders_by_objective(tmp_path):
    base = _make_run(tmp_path, "baseline", score=3.0, rel=0.03, vapor_rhs=0.3)
    better = _make_run(tmp_path, "better", score=1.0, rel=0.01, vapor_rhs=0.1)
    worse = _make_run(tmp_path, "worse", score=5.0, rel=0.05, vapor_rhs=0.5)

    report = rank_candidates([base, worse, better], baseline_dir=base)

    assert report["best"]["label"] == "better"
    assert report["best_beats_baseline"] is True
    assert report["objective_improvement_vs_baseline"] > 0.0
    assert [r["label"] for r in report["candidates"]] == ["better", "baseline", "worse"]


def test_rank_dynamic_one_step_initialization_candidates_keeps_unscorable_rows(tmp_path):
    good = _make_run(tmp_path, "good", score=1.0, rel=0.01, vapor_rhs=0.1)
    bad = tmp_path / "bad"
    bad.mkdir()
    _write_csv(
        bad / "column_summary_test.csv",
        [{"time_s": "0.2", "steady_state_score": "1", "ss_max_rel_state_rate_per_s": "0.01", "ss_max_temp_rate_F_per_s": "0"}],
    )
    _write_csv(
        bad / "column_profile_test.csv",
        [{"time_s": "0.2", "node_type": "stage", "stage": "1", "MV_lbmol": "1", "y_A": "1"}],
    )

    report = rank_candidates([bad, good])

    assert report["best"]["label"] == "good"
    assert report["n_scorable"] == 1
    assert report["n_unscorable"] == 1
    bad_row = next(r for r in report["candidates"] if r["label"] == "bad")
    assert bad_row["scorable"] is False
    assert bad_row["error"]
