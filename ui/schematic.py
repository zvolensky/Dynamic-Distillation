from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import math


def _fmt(value: Any, *, nd: int = 2, suffix: str = "") -> str:
    try:
        v = float(value)
    except Exception:
        return "n/a"
    if v != v:
        return "n/a"
    return f"{v:.{nd}f}{suffix}"


def _pick_live_or_seed(live: Any, seed: Any) -> Any:
    try:
        v = float(live)
        if v == v:
            return v
    except Exception:
        pass
    return seed


def _extract_live_component_values(summary_row: Dict[str, Any], prefix: str, component_names: List[Any]) -> List[Any]:
    return [summary_row.get(f"{prefix}_{name}") for name in component_names]


def _horizontal_cylinder_height_fraction_from_volume_fraction(v_over_v: Any) -> float | None:
    try:
        vf = float(v_over_v)
    except Exception:
        return None
    if not math.isfinite(vf):
        return None
    if vf <= 0.0:
        return 0.0
    if vf >= 1.0:
        return 1.0
    if abs(vf - 0.5) <= 1e-14:
        return 0.5

    def _vol_frac_from_hf(hf: float) -> float:
        if hf <= 0.0:
            return 0.0
        if hf >= 1.0:
            return 1.0
        r = 0.5
        h = hf
        term = max(2.0 * r * h - h * h, 0.0)
        area = (r * r) * math.acos((r - h) / r) - (r - h) * math.sqrt(term)
        return float(max(0.0, min(1.0, area / (math.pi * r * r))))

    lo = 0.0
    hi = 1.0
    for _ in range(48):
        mid = 0.5 * (lo + hi)
        if _vol_frac_from_hf(mid) < vf:
            lo = mid
        else:
            hi = mid
    return float(0.5 * (lo + hi))


def _fmt_level(summary_row: Dict[str, Any], overview: Dict[str, Any], *, top: bool) -> str:
    if top:
        pv_mode = str(overview.get("top_level_pv_mode") or "").strip().lower()
        pv_live = summary_row.get("Top_level_ctrl_pv")
        v_liq = summary_row.get("V_top_drum_liquid_ft3")
        total_v = overview.get("top_total_volume_ft3")
        if pv_mode == "true-level":
            try:
                if total_v is not None and float(total_v) > 0.0 and v_liq is not None:
                    frac = float(v_liq) / float(total_v)
                    hf = _horizontal_cylinder_height_fraction_from_volume_fraction(frac)
                    if hf is not None:
                        return _fmt(100.0 * hf, suffix="%")
            except Exception:
                pass
            try:
                pv = float(pv_live)
                if math.isfinite(pv) and 0.0 <= pv <= 1.0:
                    return _fmt(100.0 * pv, suffix="%")
            except Exception:
                pass
            seed = overview.get("initial_top_level_frac")
            try:
                sf = float(seed)
                if math.isfinite(sf):
                    return _fmt(100.0 * sf, suffix="%")
            except Exception:
                pass
            return "n/a"
        return _fmt(_pick_live_or_seed(summary_row.get("Distillate_L_lbmol"), pv_live), nd=1, suffix=" lbmol")

    pv_mode = str(overview.get("bottom_level_pv_mode") or "").strip().lower()
    pv_live = summary_row.get("Bottom_level_ctrl_pv")
    if pv_mode == "true-level":
        try:
            pv = float(pv_live)
            if math.isfinite(pv) and 0.0 <= pv <= 1.0:
                return _fmt(100.0 * pv, suffix="%")
        except Exception:
            pass
        seed = overview.get("initial_bottom_level_frac")
        try:
            sf = float(seed)
            if math.isfinite(sf):
                return _fmt(100.0 * sf, suffix="%")
        except Exception:
            pass
        return "n/a"
    return _fmt(_pick_live_or_seed(summary_row.get("Bottoms_L_lbmol"), pv_live), nd=1, suffix=" lbmol")


def _comp_lines(label: str, values: List[Any], component_names: List[Any]) -> str:
    if not values or not component_names:
        return f"<div class='pfd-kv'><span>{label}</span><span>n/a</span></div>"
    rows: List[str] = [f"<div class='pfd-kv pfd-kv-head'><span>{label}</span><span></span></div>"]
    for name, val in zip(component_names, values):
        rows.append(f"<div class='pfd-kv'><span>{name}</span><span>{_fmt(val, nd=4)}</span></div>")
    return "".join(rows)


def _mini_card(title: str, lines_html: str, *, klass: str = "") -> str:
    extra = f" {klass}" if klass else ""
    return (
        f"<div class='pfd-card{extra}'>"
        f"<div class='pfd-card-title'>{title}</div>"
        f"{lines_html}"
        f"</div>"
    )


def _kv(label: str, value: str) -> str:
    return f"<div class='pfd-kv'><span>{label}</span><span>{value}</span></div>"


def _stage_row(stage_rows: List[Dict[str, Any]], stage_no: int) -> Dict[str, Any]:
    for row in stage_rows:
        try:
            if str(row.get("node_type")) == "stage" and int(float(row.get("stage"))) == stage_no:
                return row
        except Exception:
            continue
    return {}


def _feed_arrow_y(n_stages: int, feed_stage: Optional[int]) -> int:
    if not n_stages or not feed_stage:
        return 270
    feed_idx = max(1, min(int(feed_stage), int(n_stages)))
    top_y = 150
    bottom_y = 510
    frac = (feed_idx - 1) / max(n_stages - 1, 1)
    return int(round(top_y + frac * (bottom_y - top_y)))


def build_column_schematic_html(
    *,
    overview: Dict[str, Any],
    summary_row: Dict[str, Any] | None,
    stage_rows: List[Dict[str, Any]],
) -> str:
    summary_row = dict(summary_row or {})
    n_stages = int(overview.get("n_stages") or 0)
    feed_stage = overview.get("feed_stage_1based")
    component_names = list(overview.get("component_names") or [])

    top_stage = _stage_row(stage_rows, 1)
    second_stage = _stage_row(stage_rows, 2)
    bottom_stage = _stage_row(stage_rows, n_stages)

    q_cond = _pick_live_or_seed(summary_row.get("Q_cond_used_BTUph"), overview.get("initial_condenser_duty_btuph"))
    q_reb = _pick_live_or_seed(summary_row.get("Q_reb_used_BTUph"), overview.get("initial_reboiler_duty_btuph"))
    p_top = _pick_live_or_seed(summary_row.get("P_top_drum_psia"), overview.get("initial_top_pressure_psia"))
    p_bot = _pick_live_or_seed(summary_row.get("P_bot_psia"), overview.get("initial_bottom_pressure_psia"))
    t_dist = _pick_live_or_seed(summary_row.get("T_Distillate_F"), overview.get("initial_top_temperature_F"))
    t_sump = _pick_live_or_seed(summary_row.get("T_sump_F"), overview.get("initial_bottom_temperature_F"))
    feed_stream = dict(overview.get("feed_stream", {}) or {})
    feed_flow = _pick_live_or_seed(summary_row.get("F_lbmolph"), feed_stream.get("flow_lbmolph"))
    feed_temp = _pick_live_or_seed(feed_stream.get("temperature_F"), _pick_live_or_seed(_stage_row(stage_rows, int(feed_stage or 1)).get("T_F"), None))
    feed_press = _pick_live_or_seed(feed_stream.get("pressure_psia"), p_bot)
    d_flow = _pick_live_or_seed(
        summary_row.get("D_lbmolph"),
        overview.get("initial_liquid_flow_profile_lbmolph", [None])[0] if overview.get("initial_liquid_flow_profile_lbmolph") else None,
    )
    b_flow = _pick_live_or_seed(
        summary_row.get("B_lbmolph"),
        overview.get("initial_liquid_flow_profile_lbmolph", [None])[-1] if overview.get("initial_liquid_flow_profile_lbmolph") else None,
    )
    reflux_flow = _pick_live_or_seed(summary_row.get("Reflux_cmd_lbmolph"), None)

    live_xd = _extract_live_component_values(summary_row, "Distillate_x", component_names)
    live_xb = _extract_live_component_values(summary_row, "Bottoms_x", component_names)
    top_comp = live_xd if any(v is not None and v == v for v in live_xd) else overview.get("initial_top_liquid_comp", [])
    bottom_comp = live_xb if any(v is not None and v == v for v in live_xb) else overview.get("initial_bottom_liquid_comp", [])

    feed_y = _feed_arrow_y(n_stages, feed_stage)
    tray_lines = []
    if n_stages > 0:
        for idx in range(n_stages):
            y = 150 + idx * (360 / max(n_stages - 1, 1))
            color = "#f59e0b" if feed_stage and idx + 1 == int(feed_stage) else "#aab6cc"
            width = 1.5 if feed_stage and idx + 1 == int(feed_stage) else 1.0
            tray_lines.append(
                f"<line x1='330' y1='{y:.1f}' x2='410' y2='{y:.1f}' stroke='{color}' stroke-width='{width}' opacity='0.9'/>"
            )
    tray_svg = "".join(tray_lines)

    top_block = _mini_card(
        "Condenser / Drum",
        "".join(
            [
                _kv("Duty", f"{_fmt(q_cond, nd=0)} Btu/h"),
                _kv("Pressure", f"{_fmt(p_top)} psia"),
                _kv("Level", _fmt_level(summary_row, overview, top=True)),
                _kv("Drum vapor", f"{_fmt(summary_row.get('MV_top_drum_lbmol'))} lbmol"),
            ]
        ),
        klass="pfd-top-card",
    )
    reflux_block = _mini_card(
        "Reflux",
        "".join(
            [
                _kv("Flow", f"{_fmt(reflux_flow)} lbmol/h"),
                _kv("Top tray T", f"{_fmt(top_stage.get('T_F'))} F"),
                _kv("Tray 2 V", f"{_fmt(second_stage.get('V_out_lbmolph'))} lbmol/h"),
            ]
        ),
        klass="pfd-reflux-card",
    )
    feed_block = _mini_card(
        "Feed",
        "".join(
            [
                _kv("Flow", f"{_fmt(feed_flow)} lbmol/h"),
                _kv("T", f"{_fmt(feed_temp)} F"),
                _kv("P", f"{_fmt(feed_press)} psia"),
            ]
        ),
        klass="pfd-feed-card",
    )
    distillate_block = _mini_card(
        "Distillate",
        "".join(
            [
                _kv("Flow", f"{_fmt(d_flow)} lbmol/h"),
                _kv("T", f"{_fmt(t_dist)} F"),
                _kv("P", f"{_fmt(p_top)} psia"),
                _comp_lines("xD", top_comp, component_names),
            ]
        ),
        klass="pfd-dist-card",
    )
    reboiler_block = _mini_card(
        "Reboiler",
        "".join(
            [
                _kv("Duty", f"{_fmt(q_reb, nd=0)} Btu/h"),
                _kv("Bottom tray T", f"{_fmt(bottom_stage.get('T_F'))} F"),
                _kv("Boilup V", f"{_fmt(bottom_stage.get('V_out_lbmolph'))} lbmol/h"),
            ]
        ),
        klass="pfd-reb-card",
    )
    sump_block = _mini_card(
        "Bottoms Sump",
        "".join(
            [
                _kv("Level", _fmt_level(summary_row, overview, top=False)),
                _kv("T", f"{_fmt(t_sump)} F"),
                _kv("P", f"{_fmt(p_bot)} psia"),
                _kv("Holdup", f"{_fmt(summary_row.get('Bottoms_L_lbmol'))} lbmol"),
            ]
        ),
        klass="pfd-sump-card",
    )
    bottoms_block = _mini_card(
        "Bottoms",
        "".join(
            [
                _kv("Flow", f"{_fmt(b_flow)} lbmol/h"),
                _kv("T", f"{_fmt(t_sump)} F"),
                _kv("P", f"{_fmt(p_bot)} psia"),
                _comp_lines("xB", bottom_comp, component_names),
            ]
        ),
        klass="pfd-bot-card",
    )
    column_block = _mini_card(
        "Column",
        "".join(
            [
                _kv("Stages", f"{n_stages}"),
                _kv("Feed tray", f"{feed_stage if feed_stage is not None else 'n/a'}"),
                _kv("Top tray T", f"{_fmt(top_stage.get('T_F'))} F"),
                _kv("Bottom tray T", f"{_fmt(bottom_stage.get('T_F'))} F"),
            ]
        ),
        klass="pfd-col-card",
    )

    status_note = ""
    if not summary_row:
        status_note = (
            "<div class='pfd-banner'>Workbook loaded. Waiting for first logged simulation data...</div>"
        )

    return f"""
    <style>
    .pfd-wrap {{
      font-family: "Segoe UI", system-ui, sans-serif;
      color: #e5edf7;
    }}
    .pfd-banner {{
      margin-bottom: 12px;
      padding: 10px 12px;
      border-radius: 12px;
      background: rgba(30, 41, 59, 0.88);
      border: 1px solid rgba(148, 163, 184, 0.28);
      color: #d9e7fb;
    }}
    .pfd-shell {{
      position: relative;
      min-height: 900px;
      border-radius: 18px;
      padding: 18px;
      background:
        radial-gradient(circle at top left, rgba(37,99,235,0.16), transparent 30%),
        radial-gradient(circle at bottom right, rgba(14,165,233,0.12), transparent 28%),
        linear-gradient(180deg, #0f172a 0%, #111827 100%);
      border: 1px solid rgba(148, 163, 184, 0.18);
      overflow: hidden;
    }}
    .pfd-svg {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
    }}
    .pfd-card {{
      position: absolute;
      width: 220px;
      padding: 10px 12px;
      border-radius: 14px;
      background: rgba(15, 23, 42, 0.84);
      border: 1px solid rgba(148, 163, 184, 0.24);
      box-shadow: 0 10px 30px rgba(0,0,0,0.28);
      backdrop-filter: blur(6px);
    }}
    .pfd-card-title {{
      font-size: 13px;
      font-weight: 700;
      color: #f8fafc;
      margin-bottom: 8px;
      letter-spacing: 0.01em;
    }}
    .pfd-kv {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      margin: 2px 0;
      font-size: 12px;
      color: #d6e2f1;
    }}
    .pfd-kv span:last-child {{
      text-align: right;
      color: #f8fafc;
      font-variant-numeric: tabular-nums;
    }}
    .pfd-kv-head {{
      margin-top: 6px;
      padding-top: 6px;
      border-top: 1px solid rgba(148, 163, 184, 0.16);
      font-weight: 700;
      color: #93c5fd;
    }}
    .pfd-top-card {{ top: 22px; right: 28px; }}
    .pfd-reflux-card {{ top: 210px; right: 96px; width: 190px; }}
    .pfd-feed-card {{ top: 300px; left: 76px; width: 210px; }}
    .pfd-dist-card {{ top: 420px; right: 28px; }}
    .pfd-reb-card {{ bottom: 220px; left: 28px; }}
    .pfd-sump-card {{ bottom: 34px; left: 518px; width: 220px; }}
    .pfd-bot-card {{ bottom: 22px; right: 28px; }}
    .pfd-col-card {{ top: 22px; left: 28px; width: 190px; }}
    .pfd-eq-label {{
      font-family: "Georgia", "Times New Roman", serif;
      fill: #f8fafc;
      font-size: 18px;
      font-weight: 600;
      letter-spacing: 0.01em;
    }}
    .pfd-stream-label {{
      font-family: "Segoe UI", system-ui, sans-serif;
      fill: #cbd5e1;
      font-size: 14px;
      font-weight: 600;
    }}
    .pfd-stage-label {{
      font-family: "Segoe UI", system-ui, sans-serif;
      fill: #93c5fd;
      font-size: 12px;
      font-weight: 600;
    }}
    </style>
    <div class="pfd-wrap">
      {status_note}
      <div class="pfd-shell">
        <svg class="pfd-svg" viewBox="0 0 980 900" xmlns="http://www.w3.org/2000/svg" aria-label="Distillation process flow schematic">
          <defs>
            <marker id="pfd-arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L0,10 L9,5 z" fill="#8ec5ff"/>
            </marker>
            <linearGradient id="col-grad" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stop-color="#1e293b"/>
              <stop offset="100%" stop-color="#0f172a"/>
            </linearGradient>
          </defs>

          <rect x="330" y="130" width="80" height="400" rx="10" fill="url(#col-grad)" stroke="#dbeafe" stroke-width="2"/>
          {tray_svg}
          <text x="370" y="118" text-anchor="middle" class="pfd-eq-label">Column</text>
          <text x="422" y="146" class="pfd-stage-label">Tray 1</text>
          <text x="422" y="{feed_y + 4}" class="pfd-stage-label">Feed @ {feed_stage if feed_stage is not None else 'n/a'}</text>
          <text x="422" y="532" class="pfd-stage-label">Tray {n_stages}</text>

          <line x1="410" y1="142" x2="410" y2="70" stroke="#8ec5ff" stroke-width="3" marker-end="url(#pfd-arrow)"/>
          <line x1="410" y1="70" x2="628" y2="70" stroke="#8ec5ff" stroke-width="3"/>
          <line x1="628" y1="70" x2="628" y2="118" stroke="#8ec5ff" stroke-width="3" marker-end="url(#pfd-arrow)"/>

          <circle cx="690" cy="118" r="28" fill="#111827" stroke="#dbeafe" stroke-width="2"/>
          <line x1="676" y1="132" x2="704" y2="104" stroke="#f8fafc" stroke-width="2"/>
          <text x="690" y="78" text-anchor="middle" class="pfd-eq-label">Condenser</text>

          <line x1="718" y1="118" x2="820" y2="118" stroke="#8ec5ff" stroke-width="3" marker-end="url(#pfd-arrow)"/>
          <text x="784" y="106" class="pfd-stream-label">Top product</text>

          <line x1="690" y1="146" x2="690" y2="212" stroke="#8ec5ff" stroke-width="3"/>
          <rect x="654" y="212" width="72" height="44" rx="10" fill="#111827" stroke="#dbeafe" stroke-width="2"/>
          <text x="690" y="204" text-anchor="middle" class="pfd-eq-label">Drum</text>

          <line x1="654" y1="182" x2="410" y2="182" stroke="#8ec5ff" stroke-width="3" marker-end="url(#pfd-arrow)"/>
          <text x="516" y="170" class="pfd-stream-label">Reflux</text>

          <line x1="184" y1="{feed_y}" x2="330" y2="{feed_y}" stroke="#8ec5ff" stroke-width="3" marker-end="url(#pfd-arrow)"/>
          <text x="196" y="{feed_y - 10}" class="pfd-stream-label">Feed</text>

          <line x1="370" y1="530" x2="370" y2="612" stroke="#8ec5ff" stroke-width="3"/>
          <line x1="370" y1="612" x2="230" y2="612" stroke="#8ec5ff" stroke-width="3" marker-end="url(#pfd-arrow)"/>
          <text x="206" y="598" class="pfd-stream-label">To reboiler</text>

          <circle cx="180" cy="612" r="28" fill="#111827" stroke="#dbeafe" stroke-width="2"/>
          <line x1="166" y1="626" x2="194" y2="598" stroke="#f8fafc" stroke-width="2"/>
          <text x="180" y="572" text-anchor="middle" class="pfd-eq-label">Reboiler</text>

          <line x1="208" y1="612" x2="330" y2="530" stroke="#8ec5ff" stroke-width="3" marker-end="url(#pfd-arrow)"/>
          <line x1="180" y1="640" x2="180" y2="744" stroke="#8ec5ff" stroke-width="3"/>
          <line x1="180" y1="744" x2="640" y2="744" stroke="#8ec5ff" stroke-width="3"/>
          <rect x="640" y="722" width="84" height="44" rx="10" fill="#111827" stroke="#dbeafe" stroke-width="2"/>
          <text x="682" y="712" text-anchor="middle" class="pfd-eq-label">Sump</text>

          <line x1="724" y1="744" x2="842" y2="744" stroke="#8ec5ff" stroke-width="3" marker-end="url(#pfd-arrow)"/>
          <text x="754" y="730" class="pfd-stream-label">Bottom product</text>
        </svg>

        {column_block}
        {top_block}
        {reflux_block}
        {feed_block}
        {distillate_block}
        {reboiler_block}
        {sump_block}
        {bottoms_block}
      </div>
    </div>
    """
