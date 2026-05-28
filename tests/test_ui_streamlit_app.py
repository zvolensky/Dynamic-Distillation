from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


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
