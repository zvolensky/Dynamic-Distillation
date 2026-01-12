from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case


def test_build_column_spec_from_template():
    case = load_case_from_excel("distillation_column_template.xlsx")
    spec = build_column_spec_from_case(case)

    assert spec.n_stages == 20
    assert spec.n_components == 3
    assert spec.y0.shape == (20, 3)
    assert spec.x0.shape == (20, 3)

    # Module 8B: tau loaded (or defaults)
    assert hasattr(spec, "tau_eq_sec")
    assert spec.tau_eq_sec > 0.0
    assert float(spec.tau_eq_sec) == 10.0
