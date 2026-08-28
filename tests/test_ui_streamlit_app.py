from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_trend_chart_omits_none_domain_when_altair_scale_built(monkeypatch):
    import ui.streamlit_app as app

    df = pd.DataFrame(
        {
            "time_s": [0.0, 10.0, 20.0],
            "Bottoms_x_n_Butane": [0.1, 0.2, 0.3],
        }
    )

    scale_calls = []
    real_scale = app.alt.Scale
    real_series_min = pd.Series.min
    real_series_max = pd.Series.max

    def fake_scale(*args, **kwargs):
        scale_calls.append(dict(kwargs))
        return real_scale(*args, **kwargs)

    def fake_series_min(self, *args, **kwargs):
        if getattr(self, "name", None) == "value":
            raise RuntimeError("force missing domain")
        return real_series_min(self, *args, **kwargs)

    def fake_series_max(self, *args, **kwargs):
        if getattr(self, "name", None) == "value":
            raise RuntimeError("force missing domain")
        return real_series_max(self, *args, **kwargs)

    captured = {"chart": None, "info": []}

    monkeypatch.setattr(app.alt, "Scale", fake_scale)
    monkeypatch.setattr(pd.Series, "min", fake_series_min)
    monkeypatch.setattr(pd.Series, "max", fake_series_max)
    monkeypatch.setattr(app.st, "altair_chart", lambda chart, use_container_width=True: captured.__setitem__("chart", chart))
    monkeypatch.setattr(app.st, "info", lambda msg: captured["info"].append(msg))

    app._trend_chart(df, ["Bottoms_x_n_Butane"], "Bottoms Composition", y_unit="mole fraction (-)")

    assert captured["chart"] is not None
    assert captured["info"] == []
    assert scale_calls
    assert "domain" not in scale_calls[0]
    assert scale_calls[0]["zero"] is False


def test_composition_change_table_preserves_small_terminal_changes():
    import ui.streamlit_app as app

    df = pd.DataFrame(
        {
            "time_s": [0.0, 60.0],
            "Distillate_x_n-Propane": [0.8795363972, 0.8795642471],
            "Distillate_x_n-Butane": [0.1204217554, 0.1203939259],
        }
    )

    table = app._composition_change_table(
        df,
        ["Distillate_x_n-Propane", "Distillate_x_n-Butane"],
    )

    assert table["Component"].tolist() == ["n-Propane", "n-Butane"]
    assert table.loc[0, "Initial"] == 0.8795363972
    assert table.loc[0, "Current"] == 0.8795642471
    assert table.loc[0, "Change"] == pytest.approx(2.78499e-5)
    assert table.loc[1, "Change"] == pytest.approx(-2.78295e-5)


def test_ui_exposes_fresh_and_restart_initial_state_modes():
    app = AppTest.from_file(str(ROOT / "ui" / "streamlit_app.py"), default_timeout=30).run()

    assert not app.exception
    initial_state = app.radio(key="initialization_mode")
    assert list(initial_state.options) == ["Fresh Start from Excel", "Restart from Stored State"]
    assert initial_state.value == "Fresh Start from Excel"
    assert any(button.label == "Start Fresh Run" for button in app.button)

    initial_state.set_value("Restart from Stored State").run()

    assert not app.exception
    assert any(field.label == "Stored State Path" for field in app.text_input)
    assert any(uploader.label == "Upload Stored State" for uploader in app.get("file_uploader"))
    restart_buttons = [button for button in app.button if button.label == "Start Core V3 Run"]
    assert len(restart_buttons) == 1
    assert restart_buttons[0].disabled is False
    assert app.number_input(key="core_v3_duration_sec").value == 30.0


def test_cli_mode_uses_an_explicit_cli_action_label():
    app = AppTest.from_file(str(ROOT / "ui" / "streamlit_app.py"), default_timeout=30).run()
    app.selectbox(key="launch_mode").set_value("CLI").run()

    assert not app.exception
    cli_buttons = [button for button in app.button if button.label == "Run CLI Command"]
    assert len(cli_buttons) == 1
    assert cli_buttons[0].disabled is True
