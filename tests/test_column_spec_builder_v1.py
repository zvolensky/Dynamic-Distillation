from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case


def test_build_column_spec_from_template():
    case = load_case_from_excel("distillation_column_template.xlsx")
    spec = build_column_spec_from_case(case)

    assert spec.n_stages == 20
    assert spec.n_components == 3

    assert spec.y0.shape == (20, 3)
    assert spec.x0.shape == (20, 3)

    # Stage is strictly 1..N
    assert spec.stage_1based[0] == 1
    assert spec.stage_1based[-1] == 20

    # Settings
    assert spec.sim.dt_sec > 0.0
    assert spec.sim.t_final_sec > 0.0
    assert spec.sim.log_every_n_steps >= 1

    # Duties present in template
    assert spec.duties.q_cond_btu_per_h is not None
    assert spec.duties.q_reb_btu_per_h is not None
