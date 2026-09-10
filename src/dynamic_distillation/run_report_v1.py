"""Generate a human-readable Word report from completed run artifacts."""

from __future__ import annotations

import json
import math
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from dynamic_distillation.core_v3.report_summary_v2 import build_report_summary_v2
from dynamic_distillation.core_v3.report_narrative_v1 import build_report_narrative_v1


NAVY = "18324A"
TEAL = "247B7B"
GOLD = "C9942E"
PALE_BLUE = "E8F0F5"
PALE_TEAL = "E7F2F1"
PALE_GOLD = "F8F0DF"
LIGHT_GRAY = "F3F5F7"
MID_GRAY = "66727D"
WHITE = "FFFFFF"
INK = "1C252C"


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _number(row: Mapping[str, Any], key: str) -> float:
    value = row.get(key, np.nan)
    return float(value) if _finite(value) else float("nan")


def _fmt(value: Any, digits: int = 2, suffix: str = "") -> str:
    if not _finite(value):
        return "Not reported"
    return f"{float(value):,.{digits}f}{suffix}"


def _first_and_last(summary: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    if summary.empty:
        raise ValueError("Summary CSV contains no rows")
    ordered = summary.sort_values("time_s", kind="stable") if "time_s" in summary else summary
    return ordered.iloc[0], ordered.iloc[-1]


def _component_names(columns: Iterable[str], prefix: str) -> list[str]:
    return [str(c)[len(prefix) :] for c in columns if str(c).startswith(prefix)]


def _pretty_component(name: str) -> str:
    return name.replace("_", "-").replace("n-", "n-")


def _set_cell_fill(cell: Any, color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), color)


def _set_cell_margins(cell: Any, top: int = 80, start: int = 110, bottom: int = 80, end: int = 110) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def _set_repeat_table_header(row: Any) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def _set_table_widths(table: Any, widths: Sequence[float]) -> None:
    table.autofit = False
    table.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for row in table.rows:
        for cell, width in zip(row.cells, widths):
            cell.width = Inches(width)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            _set_cell_margins(cell)


def _set_run(run: Any, *, size: float = 9.5, color: str = INK, bold: bool = False, italic: bool = False) -> None:
    run.font.name = "Aptos"
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Aptos")
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Aptos")
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    run.bold = bold
    run.italic = italic


def _style_document(doc: Document) -> None:
    section = doc.sections[0]
    section.top_margin = Inches(0.72)
    section.bottom_margin = Inches(0.68)
    section.left_margin = Inches(0.78)
    section.right_margin = Inches(0.78)
    section.header_distance = Inches(0.32)
    section.footer_distance = Inches(0.34)

    normal = doc.styles["Normal"]
    normal.font.name = "Aptos"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Aptos")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Aptos")
    normal.font.size = Pt(9.5)
    normal.font.color.rgb = RGBColor.from_string(INK)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.08

    for style_name, size, color, before, after in (
        ("Title", 26, NAVY, 0, 5),
        ("Heading 1", 16, NAVY, 14, 7),
        ("Heading 2", 12.5, TEAL, 10, 5),
        ("Heading 3", 10.5, NAVY, 7, 4),
    ):
        style = doc.styles[style_name]
        style.font.name = "Aptos Display" if style_name != "Normal" else "Aptos"
        style.font.size = Pt(size)
        style.font.bold = style_name != "Title"
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True


def _add_page_number(paragraph: Any) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run("Page ")
    _set_run(run, size=8, color=MID_GRAY)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    paragraph._p.append(fld)


def _add_header_footer(doc: Document, case_name: str) -> None:
    for index, section in enumerate(doc.sections):
        if index > 0:
            section.header.is_linked_to_previous = False
            section.footer.is_linked_to_previous = False
        header = section.header.paragraphs[0]
        header.text = "DYNAMIC DISTILLATION  /  RUN REPORT"
        _set_run(header.runs[0], size=8, color=TEAL, bold=True)
        footer = section.footer.paragraphs[0]
        footer.clear()
        left = footer.add_run(case_name[:70])
        _set_run(left, size=8, color=MID_GRAY)
        footer.add_run("\t")
        _add_page_number(footer)


def _add_table(
    doc: Document,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    widths: Sequence[float],
    *,
    header_fill: str = NAVY,
    font_size: float = 8.5,
) -> Any:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    _set_table_widths(table, widths)
    header = table.rows[0]
    _set_repeat_table_header(header)
    for cell, text in zip(header.cells, headers):
        _set_cell_fill(cell, header_fill)
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        run = p.add_run(str(text))
        _set_run(run, size=font_size, color=WHITE, bold=True)
    for row_index, values in enumerate(rows):
        cells = table.add_row().cells
        if row_index % 2:
            for cell in cells:
                _set_cell_fill(cell, LIGHT_GRAY)
        for cell, value in zip(cells, values):
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            run = p.add_run(str(value))
            _set_run(run, size=font_size)
    return table


def _add_metric_strip(doc: Document, metrics: Sequence[tuple[str, str, str]]) -> None:
    table = doc.add_table(rows=1, cols=len(metrics))
    table.style = "Table Grid"
    widths = [6.94 / len(metrics)] * len(metrics)
    _set_table_widths(table, widths)
    for cell, (label, value, fill) in zip(table.rows[0].cells, metrics):
        _set_cell_fill(cell, fill)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        r1 = p.add_run(label.upper() + "\n")
        _set_run(r1, size=7.5, color=MID_GRAY, bold=True)
        r2 = p.add_run(value)
        _set_run(r2, size=13, color=NAVY, bold=True)


def _controller_display(value: Any, *, digits: int = 5) -> str:
    return _fmt(value, digits) if value is not None else "Not reported"


def _evidence_display(value: Any, *, digits: int = 5) -> str:
    if value is None:
        return "Not reported"
    if isinstance(value, float):
        return _fmt(value, digits)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _balance_display(value: Any, *, digits: int = 5) -> str:
    """Keep small but nonzero residuals visible instead of rounding them to zero."""

    if value is None:
        return "Not reported"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number != 0.0 and abs(number) < 10.0 ** (-digits + 1):
        return f"{number:.3e}"
    return _fmt(number, digits)


def _add_constraint_table(doc: Document, constraints: Sequence[Mapping[str, Any]]) -> None:
    rows = [
        [
            item.get("check", "Not reported"), item.get("variable", "Not reported"),
            _evidence_display(item.get("limit")), _evidence_display(item.get("observed")),
            _controller_display(item.get("time_sec"), digits=3), item.get("location", "Not reported"),
            item.get("status", "NOT EVALUATED"), item.get("evidence", "Not reported"),
        ]
        for item in constraints
    ] or [["Constraints", "Not reported", "", "", "Not reported", "Not reported", "NOT EVALUATED", "Not reported"]]
    _add_table(
        doc, ("Check", "Variable", "Limit", "Observed", "Time (s)", "Location", "Status", "Evidence"),
        rows, (0.82, 0.92, 0.55, 0.83, 0.52, 0.7, 0.55, 1.05), font_size=5.8,
    )


def _add_event_table(doc: Document, events: Sequence[Mapping[str, Any]]) -> None:
    rows = [
        [
            _controller_display(item.get("time_sec"), digits=3), item.get("event_type", "Not reported"),
            item.get("variable", "Not reported"), _evidence_display(item.get("before")),
            _evidence_display(item.get("after")), item.get("message", "Not reported"),
            item.get("severity", "Not reported"), item.get("source_component", "Not reported"),
            item.get("related_gate", "Not reported"),
        ]
        for item in events
    ]
    _add_table(
        doc, ("Time (s)", "Event", "Variable", "Before", "After", "Consequence", "Severity", "Source", "Related gate"),
        rows, (0.5, 0.8, 0.8, 0.72, 0.72, 1.43, 0.55, 0.62, 0.75), font_size=5.7,
    )


def _add_balance_summary_table(doc: Document, balances: Mapping[str, Any]) -> None:
    """Render rate-residual aggregates separately from endpoint ledger rows."""

    summaries = balances.get("summaries", [])
    if not summaries:
        return
    doc.add_paragraph("Balance Summary", style="Heading 2")
    rows = []
    for item in summaries:
        tolerance = []
        if item.get("tolerance_absolute") is not None:
            tolerance.append(f"abs <= {_fmt(item['tolerance_absolute'], 5)}")
        if item.get("tolerance_normalized") is not None:
            tolerance.append(f"norm <= {_fmt(item['tolerance_normalized'], 5)}")
        tolerance_text = "; ".join(tolerance) if tolerance else "Not configured"
        rows.append([
            item.get("quantity", "Not reported"), item.get("units", "Not reported"),
            _balance_display(item.get("maximum_absolute_residual")),
            _balance_display(item.get("maximum_normalized_residual")),
            _balance_display(item.get("integrated_absolute_residual")),
            _balance_display(item.get("final_window_maximum_absolute_residual")),
            _controller_display(item.get("worst_time_sec"), digits=3),
            item.get("worst_location", "Not reported"),
            f"{item.get('status', 'NOT EVALUATED')}; {tolerance_text}",
        ])
    _add_table(
        doc,
        ("Quantity", "Units", "Max |residual|", "Max normalized", "Integrated |residual|", "Final-window max", "Worst time (s)", "Location", "Tolerance / status"),
        rows,
        (0.65, 0.5, 0.66, 0.66, 0.84, 0.73, 0.65, 0.62, 1.37),
        font_size=5.7,
    )


def _add_controller_performance_tables(doc: Document, controllers: Sequence[Mapping[str, Any]]) -> None:
    """Render all available controller KPIs without presenting absent policy as data."""

    if not controllers:
        doc.add_paragraph("Controller performance: not available in this artifact version.")
        return
    doc.add_paragraph("Tracking Performance", style="Heading 2")
    tracking_rows = [
        [
            item.get("controller", "Not reported"), item.get("controlled_variable", "Not reported"),
            _controller_display(item.get("final_pv")), _controller_display(item.get("setpoint")),
            _controller_display(item.get("final_error")), _controller_display(item.get("maximum_absolute_error")),
            _controller_display(item.get("mean_absolute_error")), _controller_display(item.get("integral_absolute_error")),
            _controller_display(item.get("overshoot")), _controller_display(item.get("undershoot")),
        ]
        for item in controllers
    ]
    _add_table(
        doc,
        ("Controller", "Controlled variable", "Final PV", "SP", "Final error", "Max |error|", "Mean |error|", "IAE", "Overshoot", "Undershoot"),
        tracking_rows,
        (0.73, 1.16, 0.53, 0.46, 0.61, 0.66, 0.68, 0.52, 0.59, 0.67),
        font_size=5.8,
    )
    doc.add_paragraph("Output and Settling", style="Heading 2")
    output_rows = [
        [
            item.get("controller", "Not reported"), item.get("output_units", "Not reported"),
            _controller_display(item.get("output_minimum")), _controller_display(item.get("output_maximum")),
            _controller_display(item.get("maximum_output_slew_per_sec")),
            _controller_display(item.get("lower_saturation_time_sec"), digits=3),
            _controller_display(item.get("upper_saturation_time_sec"), digits=3),
            _controller_display(item.get("settling_time_sec"), digits=3),
            _controller_display(item.get("settling_criterion_absolute_error")),
            f"output: {item.get('output_data_state', 'not_available')}; saturation: {item.get('saturation_data_state', 'not_evaluated')}; settling: {item.get('settling_data_state', 'not_evaluated')}",
        ]
        for item in controllers
    ]
    _add_table(
        doc,
        ("Controller", "Output units", "Min", "Max", "Max slew /s", "At low bound (s)", "At high bound (s)", "Settling time (s)", "Settling |error|", "Data state"),
        output_rows,
        (0.7, 0.55, 0.48, 0.48, 0.62, 0.72, 0.72, 0.66, 0.64, 1.19),
        font_size=5.7,
    )
    doc.add_paragraph("Controller Evidence and Tuning", style="Heading 2")
    evidence_rows = [
        [
            item.get("controller", "Not reported"),
            f"{item.get('history_record_count', 'Not reported')} accepted endpoints; "
            f"{_controller_display(item.get('history_start_time_sec'), digits=3)} to "
            f"{_controller_display(item.get('history_end_time_sec'), digits=3)} s",
            json.dumps(item.get("tuning"), sort_keys=True) if item.get("tuning") else "Not reported",
            item.get("completeness", "not_available"),
        ]
        for item in controllers
    ]
    _add_table(
        doc, ("Controller", "History", "Tuning", "Completeness"), evidence_rows,
        (0.95, 1.75, 2.2, 1.5), font_size=6.5,
    )


def _plot_series(
    summary: pd.DataFrame,
    output: Path,
    panels: Sequence[tuple[str, Sequence[tuple[str, str, float]]]],
    *,
    cumulative_offset_s: float,
    event_times_s: Sequence[float] = (),
    qualification_time_s: float | None = None,
) -> bool:
    if "time_s" not in summary or summary.empty:
        return False
    t_min = (pd.to_numeric(summary["time_s"], errors="coerce") + cumulative_offset_s) / 60.0
    fig, axes = plt.subplots(len(panels), 1, figsize=(9.0, 2.35 * len(panels)), sharex=True)
    if len(panels) == 1:
        axes = [axes]
    palette = ["#247B7B", "#C9942E", "#345B7E", "#A64B3C", "#6C7A3D", "#7D5A8C"]
    plotted = False
    axis_units = {
        "Feed and product flows": "lbmol/h",
        "Column traffic": "lbmol/h",
        "Top pressure": "psia",
        "Heat duties": "MMBtu/h",
        "Level-controller outputs": "lbmol/h",
        "Column pressure (psia)": "psia",
        "Product temperature (deg F)": "deg F",
        "Total inventory (lbmol)": "lbmol",
        "Distillate composition (mole fraction)": "mole fraction",
        "Bottoms composition (mole fraction)": "mole fraction",
        "Product flows (lbmol/h)": "lbmol/h",
        "Pressure (psia)": "psia",
        "Temperature (deg F)": "deg F",
        "Duties (MMBtu/h)": "MMBtu/h",
        "Stored inventories (lbmol)": "lbmol",
    }
    for ax, (title, series) in zip(axes, panels):
        for index, (column, label, scale) in enumerate(series):
            if column not in summary:
                continue
            values = pd.to_numeric(summary[column], errors="coerce") * scale
            if not values.notna().any():
                continue
            ax.plot(t_min, values, label=label, color=palette[index % len(palette)], linewidth=1.8)
            plotted = True
        for event_time in event_times_s:
            ax.axvline((float(event_time) + cumulative_offset_s) / 60.0, color="#66727D", linewidth=0.8, linestyle=":", alpha=0.75)
        if qualification_time_s is not None:
            ax.axvline((float(qualification_time_s) + cumulative_offset_s) / 60.0, color="#247B7B", linewidth=1.0, linestyle="--", alpha=0.85)
        ax.set_title(title, loc="left", fontsize=10, fontweight="bold", color="#18324A")
        ax.set_ylabel(axis_units.get(title, "%" if "levels (%)" in title else "value"), fontsize=8.5)
        ax.grid(True, alpha=0.22, linewidth=0.7)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=8)
        if ax.lines:
            ax.legend(loc="best", frameon=False, fontsize=8, ncol=min(3, len(ax.lines)))
    axes[-1].set_xlabel("Cumulative simulation time (min)", fontsize=8.5)
    fig.tight_layout(pad=1.1)
    if plotted:
        fig.savefig(output, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return plotted


def _plot_steady_state_score(
    summary: pd.DataFrame,
    output: Path,
    *,
    cumulative_offset_s: float,
    event_times_s: Sequence[float] = (),
    qualification_time_s: float | None = None,
) -> bool:
    """Plot accepted score history and its dimensionless acceptance threshold."""

    if "time_s" not in summary or "steady_state_score" not in summary or summary.empty:
        return False
    time_min = (pd.to_numeric(summary["time_s"], errors="coerce") + cumulative_offset_s) / 60.0
    score = pd.to_numeric(summary["steady_state_score"], errors="coerce")
    valid = time_min.notna() & score.notna()
    if not valid.any():
        return False
    fig, ax = plt.subplots(figsize=(9.0, 2.55))
    ax.plot(time_min[valid], score[valid], color="#247B7B", linewidth=1.8, label="Steady-state score")
    ax.axhline(1.0, color="#A64B3C", linewidth=1.0, linestyle="--", label="Acceptance limit")
    for event_time in event_times_s:
        ax.axvline((float(event_time) + cumulative_offset_s) / 60.0, color="#66727D", linewidth=0.8, linestyle=":", alpha=0.75)
    if qualification_time_s is not None:
        ax.axvline((float(qualification_time_s) + cumulative_offset_s) / 60.0, color="#247B7B", linewidth=1.0, linestyle="--", alpha=0.85, label="Qualification")
    ax.set_title("Steady-state score", loc="left", fontsize=10, fontweight="bold", color="#18324A")
    ax.set_xlabel("Cumulative simulation time (min)", fontsize=8.5)
    ax.set_ylabel("Score (ratio to limit)", fontsize=8.5)
    ax.grid(True, alpha=0.22, linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8)
    ax.legend(loc="best", frameon=False, fontsize=8)
    fig.tight_layout(pad=1.1)
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True


def _plot_balance_and_constraint_trends(
    trajectory: pd.DataFrame,
    balance_rows: Sequence[Mapping[str, Any]],
    output: Path,
    *,
    cumulative_offset_s: float,
    event_times_s: Sequence[float] = (),
    qualification_time_s: float | None = None,
) -> bool:
    """Plot only persisted residual evidence and the explicit solver margin."""

    panels: list[tuple[str, np.ndarray, np.ndarray, str, str]] = []
    if balance_rows:
        ledger = pd.DataFrame(balance_rows)
        if {"time_sec", "quantity", "residual"}.issubset(ledger.columns):
            ledger["time_sec"] = pd.to_numeric(ledger["time_sec"], errors="coerce")
            ledger["residual"] = pd.to_numeric(ledger["residual"], errors="coerce")
            material = ledger[ledger["quantity"].astype(str) != "energy"].dropna(subset=["time_sec", "residual"])
            energy = ledger[ledger["quantity"].astype(str) == "energy"].dropna(subset=["time_sec", "residual"])
            if not material.empty:
                grouped = material.assign(absolute_residual=material["residual"].abs()).groupby("time_sec")["absolute_residual"].sum()
                panels.append(("Total material residual", grouped.index.to_numpy(), grouped.to_numpy(), "lbmol/h", "Material residual"))
            if not energy.empty:
                grouped = energy.assign(absolute_residual=energy["residual"].abs()).groupby("time_sec")["absolute_residual"].max()
                panels.append(("Maximum per-volume energy residual", grouped.index.to_numpy(), grouped.to_numpy(), "BTU/h", "Energy residual"))
    if {"time_sec", "solver_residual_inf_norm"}.issubset(trajectory.columns):
        time = pd.to_numeric(trajectory["time_sec"], errors="coerce")
        residual = pd.to_numeric(trajectory["solver_residual_inf_norm"], errors="coerce")
        valid = time.notna() & residual.notna()
        if valid.any():
            panels.append(("Solver residual constraint margin", time[valid].to_numpy(), 1.0e-8 - residual[valid].to_numpy(), "margin to 1e-8", "Residual margin"))
    if not panels:
        return False
    fig, axes = plt.subplots(len(panels), 1, figsize=(9.0, 2.2 * len(panels)), sharex=True)
    if len(panels) == 1:
        axes = [axes]
    for ax, (title, time, values, units, label) in zip(axes, panels):
        ax.plot((time + cumulative_offset_s) / 60.0, values, color="#7D5A8C", linewidth=1.7, label=label)
        if title == "Solver residual constraint margin":
            ax.axhline(0.0, color="#A64B3C", linewidth=1.0, linestyle="--", label="Acceptance boundary")
        for event_time in event_times_s:
            ax.axvline((float(event_time) + cumulative_offset_s) / 60.0, color="#66727D", linewidth=0.8, linestyle=":", alpha=0.75)
        if qualification_time_s is not None:
            ax.axvline((float(qualification_time_s) + cumulative_offset_s) / 60.0, color="#247B7B", linewidth=1.0, linestyle="--", alpha=0.85)
        ax.set_title(title, loc="left", fontsize=10, fontweight="bold", color="#18324A")
        ax.set_ylabel(units, fontsize=8.5)
        ax.grid(True, alpha=0.22, linewidth=0.7)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=8)
        ax.legend(loc="best", frameon=False, fontsize=8)
    axes[-1].set_xlabel("Cumulative simulation time (min)", fontsize=8.5)
    fig.tight_layout(pad=1.1)
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True


def _plot_final_profiles(profile: pd.DataFrame, output: Path) -> bool:
    if profile.empty or "time_s" not in profile or "stage" not in profile:
        return False
    t = pd.to_numeric(profile["time_s"], errors="coerce").max()
    final = profile[np.isclose(pd.to_numeric(profile["time_s"], errors="coerce"), t)]
    if "node_type" in final:
        # Current Core V3 trajectory artifacts identify physical column stages
        # as ``tray``; early artifacts used ``stage``.  Both are reportable.
        final = final[final["node_type"].astype(str).isin(("stage", "tray"))]
    final = final.sort_values("stage")
    if final.empty:
        return False
    stage = pd.to_numeric(final["stage"], errors="coerce")
    fig, axes = plt.subplots(2, 2, figsize=(9.4, 6.1))
    ax = axes[0, 0]
    ax.plot(stage, pd.to_numeric(final.get("T_F"), errors="coerce"), color="#A64B3C", marker="o", ms=3)
    ax.set_title("Temperature", loc="left", fontweight="bold", color="#18324A")
    ax.set_ylabel("deg F")
    ax = axes[0, 1]
    ax.plot(stage, pd.to_numeric(final.get("P_psia_hyd"), errors="coerce"), color="#345B7E", marker="o", ms=3)
    ax.set_title("Pressure", loc="left", fontweight="bold", color="#18324A")
    ax.set_ylabel("psia")
    ax = axes[1, 0]
    ax.plot(stage, pd.to_numeric(final.get("L_out_used_lbmolph"), errors="coerce"), label="Liquid", color="#247B7B")
    ax.plot(stage, pd.to_numeric(final.get("V_out_lbmolph"), errors="coerce"), label="Vapor", color="#C9942E")
    ax.set_title("Internal traffic", loc="left", fontweight="bold", color="#18324A")
    ax.set_ylabel("lbmol/h")
    ax.legend(frameon=False, fontsize=8)
    ax = axes[1, 1]
    composition_columns = [c for c in final.columns if str(c).startswith("x_") and not str(c).startswith("x_eq_")]
    colors = ["#247B7B", "#C9942E", "#7D5A8C", "#A64B3C"]
    for index, column in enumerate(composition_columns[:4]):
        ax.plot(stage, pd.to_numeric(final[column], errors="coerce"), label=_pretty_component(column[2:]), color=colors[index])
    ax.set_title("Liquid composition", loc="left", fontweight="bold", color="#18324A")
    ax.set_ylabel("mole fraction")
    if ax.lines:
        ax.legend(frameon=False, fontsize=8)
    for ax in axes.flat:
        ax.set_xlabel("Stage")
        ax.grid(True, alpha=0.22, linewidth=0.7)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=8)
    fig.tight_layout(pad=1.2)
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True


def _plot_core_v3_profiles(rows: Sequence[Mapping[str, Any]], output: Path) -> bool:
    """Render distinct thermal/hydraulic, liquid-x, and vapor-y profile views."""
    if not rows:
        return False
    stage = np.arange(1, len(rows) + 1)
    components = tuple(rows[0].get("liquid_mole_fraction", {}).keys())
    fig, axes = plt.subplots(1, 3, figsize=(10.0, 3.4))
    axes[0].plot(stage, [float(row["temperature_F"]) for row in rows], label="Temperature (F)", color="#A64B3C")
    pressure_axis = axes[0].twinx()
    pressure_axis.plot(stage, [float(row["pressure_psia"]) for row in rows], label="Pressure (psia)", color="#345B7E")
    axes[0].set_title("Thermal and hydraulic profile", loc="left", fontweight="bold", color="#18324A")
    axes[0].set_ylabel("Temperature (F)")
    pressure_axis.set_ylabel("Pressure (psia)")
    colors = ["#247B7B", "#C9942E", "#7D5A8C", "#A64B3C"]
    for index, component in enumerate(components):
        axes[1].plot(stage, [float(row["liquid_mole_fraction"][component]) for row in rows], label=_pretty_component(component), color=colors[index % len(colors)])
        axes[2].plot(stage, [float(row["vapor_mole_fraction"][component]) for row in rows], label=_pretty_component(component), color=colors[index % len(colors)])
    axes[1].set_title("Liquid composition profile", loc="left", fontweight="bold", color="#18324A")
    axes[2].set_title("Vapor composition profile", loc="left", fontweight="bold", color="#18324A")
    for axis in axes:
        axis.set_xlabel("Stage / volume order")
        axis.set_ylabel("Mole fraction" if axis is not axes[0] else "")
        axis.grid(True, alpha=0.22, linewidth=0.7)
        axis.spines[["top", "right"]].set_visible(False)
        if axis.lines:
            axis.legend(frameon=False, fontsize=7)
    fig.tight_layout(pad=1.0)
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True


def _final_profile_assessment(profile: pd.DataFrame) -> dict[str, Any]:
    """Extract reportable profile facts without treating terminal nodes as trays."""

    if profile.empty or "time_s" not in profile:
        return {"available": False}
    final_time = pd.to_numeric(profile["time_s"], errors="coerce").max()
    final = profile[np.isclose(pd.to_numeric(profile["time_s"], errors="coerce"), final_time)].copy()
    if final.empty:
        return {"available": False}
    tray = final[final.get("node_type", pd.Series("", index=final.index)).astype(str).isin(("stage", "tray"))].copy()
    terminals = final[~final.index.isin(tray.index)]
    volume_names = final.get("volume", final.get("stage", pd.Series("Not reported", index=final.index))).astype(str)
    tray_volume_names = tray.get("volume", tray.get("stage", pd.Series("Not reported", index=tray.index))).astype(str)
    assessment: dict[str, Any] = {
        "available": True,
        "final_time_s": float(final_time),
        "feed_stage": None,
        "terminal_volumes": list(volume_names.loc[terminals.index]),
        "non_stage_nodes": list(volume_names.loc[terminals.index]),
        "flow_reversals": [],
        "composition_extrema": {},
    }
    feed = final[volume_names.eq("feed_tray")]
    if not feed.empty and "stage" in feed:
        assessment["feed_stage"] = int(float(feed.iloc[0]["stage"]))
    if not tray.empty:
        for key, label in (("T_F", "temperature_range_F"), ("P_psia_hyd", "pressure_range_psia")):
            values = pd.to_numeric(tray.get(key, pd.Series(np.nan, index=tray.index)), errors="coerce")
            if values.notna().any():
                assessment[label] = (float(values.min()), float(values.max()))
        pressure = pd.to_numeric(tray.get("P_psia_hyd", pd.Series(np.nan, index=tray.index)), errors="coerce")
        if pressure.notna().any():
            assessment["top_to_bottom_pressure_drop_psia"] = float(pressure.iloc[-1] - pressure.iloc[0])
        for key in ("L_out_used_lbmolph", "V_out_lbmolph"):
            values = pd.to_numeric(tray.get(key, pd.Series(np.nan, index=tray.index)), errors="coerce")
            assessment["flow_reversals"].extend(
                f"{key}:{volume}" for volume in tray_volume_names.loc[values < 0.0]
            )
        for column in tray.columns:
            if not str(column).startswith(("x_", "y_")):
                continue
            values = pd.to_numeric(tray[column], errors="coerce")
            if values.notna().any():
                assessment["composition_extrema"][str(column)] = (float(values.min()), float(values.max()))
    return assessment


def _add_profile_assessment_tables(doc: Document, assessment: Mapping[str, Any]) -> None:
    """Present final-profile facts in scan-friendly tables, not a dense sentence."""

    if not assessment.get("available"):
        return
    temperature = assessment.get("temperature_range_F")
    pressure_drop = assessment.get("top_to_bottom_pressure_drop_psia")
    summary_rows = [
        ["Feed stage", assessment.get("feed_stage") if assessment.get("feed_stage") is not None else "Not reported"],
        ["Terminal volumes", ", ".join(assessment.get("terminal_volumes", ())) or "None"],
        ["Tray pressure drop", _fmt(pressure_drop, 3, " psia")],
        ["Tray temperature range", f"{_fmt(temperature[0], 2)} to {_fmt(temperature[1], 2)} deg F" if temperature else "Not reported"],
        ["Flow reversals", ", ".join(assessment.get("flow_reversals", ())) or "None observed"],
    ]
    doc.add_paragraph("Profile Summary", style="Heading 2")
    _add_table(doc, ("Attribute", "Observed final-profile value"), summary_rows, (1.65, 5.19), header_fill=TEAL, font_size=8.0)
    extrema = assessment.get("composition_extrema", {})
    if not extrema:
        return
    components = sorted({key[2:] for key in extrema if key.startswith(("x_", "y_"))})
    rows = []
    for component in components:
        liquid = extrema.get(f"x_{component}")
        vapor = extrema.get(f"y_{component}")
        rows.append([
            _pretty_component(component),
            _fmt(liquid[0], 4) if liquid else "Not reported",
            _fmt(liquid[1], 4) if liquid else "Not reported",
            _fmt(vapor[0], 4) if vapor else "Not reported",
            _fmt(vapor[1], 4) if vapor else "Not reported",
        ])
    doc.add_paragraph("Composition Extrema", style="Heading 2")
    _add_table(doc, ("Component", "Liquid min", "Liquid max", "Vapor min", "Vapor max"), rows, (1.4, 1.2, 1.2, 1.2, 1.2), header_fill=TEAL, font_size=7.8)


def _add_artifact_index(doc: Document, report: Mapping[str, Any]) -> None:
    """Show provenance identifiers in a compact, audit-friendly final index."""

    report_schema = str(report.get("report_schema_version", "Not reported"))
    rows = []
    for item in report.get("artifacts", []):
        digest = item.get("sha256")
        fingerprint = f"sha256:{str(digest)[:12]}" if digest else "Not reported"
        schema = report_schema if item.get("artifact") == "report_summary" else "Not reported"
        rows.append([
            item.get("artifact", "Not reported"), str(item.get("path", "Not reported")), schema,
            fingerprint, str(item.get("size_bytes")) if item.get("size_bytes") is not None else "Not reported",
            item.get("status", "Not reported"),
        ])
    _add_table(
        doc,
        ("Artifact", "Path", "Schema/version", "Hash", "Size (bytes)", "Status"),
        rows or [["Artifacts", "Not reported", "Not reported", "Not reported", "Not reported", "not_available"]],
        (0.75, 2.35, 0.9, 0.9, 0.62, 0.58),
        font_size=5.7,
    )


def _add_numerical_health_tables(doc: Document, health: Mapping[str, Any]) -> None:
    """Group numeric solver evidence and avoid dumping nested dictionaries into cells."""

    primary = (
        ("Integrator", health.get("integrator")),
        ("Termination reason", health.get("termination_reason")),
        ("Accepted / rejected steps", f"{health.get('accepted_steps', 'Not reported')} / {health.get('rejected_steps', 'Not reported')}"),
        ("Configured timestep", _controller_display(health.get("configured_timestep_sec"), digits=3) + " s"),
        ("Actual timestep min / mean / max", " / ".join(_controller_display(health.get(key), digits=3) for key in ("actual_timestep_min_sec", "actual_timestep_mean_sec", "actual_timestep_max_sec")) + " s"),
        ("Maximum scaled residual", _balance_display(health.get("maximum_residual_infinity_norm"))),
        ("Maximum Jacobian condition", _balance_display(health.get("maximum_jacobian_condition"))),
        ("Function evaluations total / max", f"{health.get('nonlinear_function_evaluations_total', 'Not reported')} / {health.get('nonlinear_function_evaluations_maximum', 'Not reported')}"),
        ("Jacobian evaluations", health.get("jacobian_evaluations_total")),
        ("Configured max evaluations per root", health.get("configured_max_function_evaluations_per_root")),
        ("Events / warnings / errors", f"{health.get('event_count', 'Not reported')} / {health.get('warning_count', 'Not reported')} / {health.get('error_count', 'Not reported')}"),
    )
    doc.add_paragraph("Solver and Acceptance", style="Heading 2")
    _add_table(doc, ("Metric", "Observed"), [[label, _evidence_display(value)] for label, value in primary], (2.55, 4.29), font_size=7.5)
    performance = health.get("performance", {})
    if not isinstance(performance, Mapping):
        return
    performance_rows = [
        ("Jacobian execution / workers", f"{performance.get('jacobian_execution', 'Not reported')} / {performance.get('parallel_workers', 'Not reported')}"),
        ("Endpoint wall time total / mean / p95", " / ".join(_controller_display(performance.get(key), digits=3) for key in ("endpoint_wall_total_s", "endpoint_wall_mean_s", "endpoint_wall_p95_s")) + " s"),
        ("Objective calls / Jacobian builds", f"{performance.get('objective_calls_total', 'Not reported')} / {performance.get('jacobian_builds_total', 'Not reported')}"),
        ("Memo hits / misses / hit fraction", f"{performance.get('memo_hits_total', 'Not reported')} / {performance.get('memo_misses_total', 'Not reported')} / {_controller_display(performance.get('memo_hit_fraction'), digits=4)}"),
    ]
    doc.add_paragraph("Runtime and Cache", style="Heading 2")
    _add_table(doc, ("Metric", "Observed"), [[label, value] for label, value in performance_rows], (2.55, 4.29), font_size=7.5)


def _add_run_narrative(doc: Document, report: Mapping[str, Any], metadata: Mapping[str, Any]) -> None:
    narrative = build_report_narrative_v1(report, metadata=metadata)
    doc.add_heading("Run Narrative", level=1)
    for text in narrative["paragraphs"]:
        doc.add_paragraph(text)


def _condition_rows(row: Mapping[str, Any]) -> list[list[str]]:
    top_pv = _number(row, "Top_level_ctrl_pv")
    top_sp = _number(row, "Top_level_ctrl_sp")
    bottom_pv = _number(row, "Bottom_level_ctrl_pv")
    bottom_sp = _number(row, "Bottom_level_ctrl_sp")
    top_is_fraction = _finite(top_pv) and _finite(top_sp) and max(abs(top_pv), abs(top_sp)) <= 1.5
    bottom_is_fraction = _finite(bottom_pv) and _finite(bottom_sp) and max(abs(bottom_pv), abs(bottom_sp)) <= 1.5
    return [
        ["Feed", _fmt(_number(row, "F_lbmolph")), "lbmol/h"],
        ["Feed temperature", _fmt(_number(row, "Feed_temperature_F"), 2), "deg F"],
        ["Feed pressure", _fmt(_number(row, "Feed_pressure_psia"), 3), "psia"],
        ["Distillate", _fmt(_number(row, "D_lbmolph")), "lbmol/h"],
        ["Bottoms", _fmt(_number(row, "B_lbmolph")), "lbmol/h"],
        ["Reflux", _fmt(_number(row, "total_reflux_used_lbmolph")), "lbmol/h"],
        ["Top pressure", _fmt(_number(row, "P_top_psia"), 3), "psia"],
        ["Bottom pressure", _fmt(_number(row, "P_bot_psia"), 3), "psia"],
        ["Distillate temperature", _fmt(_number(row, "T_Distillate_F"), 2), "deg F"],
        ["Bottoms temperature", _fmt(_number(row, "T_sump_F"), 2), "deg F"],
        ["Condenser duty", _fmt(_number(row, "Q_cond_used_BTUph") / 1.0e6, 3), "MMBtu/h"],
        ["Reboiler duty", _fmt(_number(row, "Q_reb_used_BTUph") / 1.0e6, 3), "MMBtu/h"],
        [
            "Distillate drum level" if top_is_fraction else "Distillate drum controller PV",
            _fmt(100.0 * top_pv if top_is_fraction else top_pv, 2),
            "%" if top_is_fraction else "lbmol",
        ],
        [
            "Bottoms sump level" if bottom_is_fraction else "Bottoms sump controller PV",
            _fmt(100.0 * bottom_pv if bottom_is_fraction else bottom_pv, 2),
            "%" if bottom_is_fraction else "lbmol",
        ],
        ["Steady-state score", _fmt(_number(row, "steady_state_score"), 4), "-"],
    ]


def _product_composition_rows(row: Mapping[str, Any]) -> list[list[str]]:
    components = sorted(
        set(_component_names(row.keys(), "Distillate_x_")) | set(_component_names(row.keys(), "Bottoms_x_"))
    )
    return [
        [
            _pretty_component(component),
            _fmt(100.0 * _number(row, f"Distillate_x_{component}"), 3, "%"),
            _fmt(100.0 * _number(row, f"Bottoms_x_{component}"), 3, "%"),
        ]
        for component in components
    ]


def _parameter_rows(metadata: Mapping[str, Any]) -> list[list[str]]:
    params = dict(metadata.get("simulation_parameters") or {})
    preferred = [
        "runtime_mode", "thermo_mode", "dwsim_property_package", "integrator", "n_steps", "dt_sec",
        "log_every_n_steps", "thermo_every_n_steps",
        "include_energy", "enable_equilibrium_relaxation", "equilibrium_relaxation_mode", "equilibrium_tau_sec",
        "flash_feed_at_stage_conditions", "enable_liquid_hydraulic_override", "liquid_hydraulic_model",
        "liquid_hydraulic_override_alpha", "enable_level_control", "top_level_pv_mode", "top_level_kc",
        "top_level_ti_sec", "bottom_level_pv_mode", "bottom_level_kc", "bottom_level_ti_sec",
        "enable_pressure_control", "pressure_control_mv", "top_pressure_sp_psia", "top_pressure_kc",
        "top_pressure_ti_sec", "top_pressure_pv_filter_tau_sec", "top_pressure_mv_slew_limit_per_s",
        "condenser_duty_mode", "condenser_duty_btu_per_h", "condenser_duty_min_btu_per_h",
        "condenser_duty_max_btu_per_h", "reboiler_duty_btu_per_h", "vapor_holdup_relaxation_sec",
        "vapor_flow_relaxation_sec", "vapor_flow_zero_temperature_target", "dynamic_vflow_nominal_hi_ratio",
        "steady_state_window_sec", "steady_state_min_time_sec", "steady_state_rel_state_rate_tol_per_s",
        "steady_state_temp_rate_tol_F_per_s", "steady_state_sp_error_tol", "steady_state_require_sp",
    ]
    if not params:
        params = {key: metadata.get(key) for key in ("runtime_mode", "thermo_mode", "n_steps", "dt_sec", "flash_feed_at_stage_conditions")}
    rows: list[list[str]] = []
    used: set[str] = set()
    for key in preferred:
        if key in params and params[key] is not None:
            rows.append([key.replace("_", " ").title(), str(params[key])])
            used.add(key)
    return rows


def _launch_command_for_report(metadata: Mapping[str, Any]) -> tuple[str | None, str]:
    """Return the persisted CLI, or a visibly reconstructed command for old runs."""

    command = str(metadata.get("launch_command") or "").strip()
    if command:
        return command, "Exact invoked command persisted by the runner."
    required = ("excel_path", "started_from_checkpoint", "duration_sec", "dt_sec", "n_steps", "run_name")
    if not all(metadata.get(key) is not None for key in required):
        return None, "CLI command was not persisted for this artifact."
    quote = lambda value: f'"{value}"' if any(char in str(value) for char in " \t") else str(value)
    command = " ".join((
        "python", "tools/run_core_v3_dynamic.py",
        "--excel", quote(metadata["excel_path"]),
        "--init-from-checkpoint", quote(metadata["started_from_checkpoint"]),
        "--duration-sec", str(metadata["duration_sec"]),
        "--dt", str(metadata["dt_sec"]),
        "--log-every", "4",
        "--logs-dir", quote(Path(str(metadata["summary_csv"])).parent),
        "--run-name", quote(metadata["run_name"]),
    ))
    return command, "Reconstructed from persisted run metadata; the original CLI was not recorded."


def generate_run_report(
    metadata_json_path: str | Path,
    *,
    output_path: str | Path | None = None,
    simulation_parameters: Optional[Mapping[str, Any]] = None,
    launch_command: Optional[str] = None,
) -> str:
    """Create a Word report for one completed dynamic run."""
    metadata_path = Path(metadata_json_path).expanduser().resolve()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if simulation_parameters is not None:
        metadata["simulation_parameters"] = dict(simulation_parameters)
    if launch_command:
        metadata["launch_command"] = str(launch_command)
    summary_path = Path(str(metadata["summary_csv"])).expanduser()
    profile_path = Path(str(metadata["profile_csv"])).expanduser()
    if not summary_path.is_absolute():
        summary_path = (metadata_path.parent / summary_path).resolve()
    if not profile_path.is_absolute():
        profile_path = (metadata_path.parent / profile_path).resolve()
    summary = pd.read_csv(summary_path)
    profile = pd.read_csv(profile_path)
    trajectory = pd.DataFrame()
    balance_rows: list[dict[str, Any]] = []
    # Normalize Core V3's current result names to the report's stable semantic
    # names.  Only measured quantities are aliased here: do not invent missing
    # controller pressure/level setpoints merely to draw an extra trend line.
    for report_name, result_name in {
        "total_reflux_used_lbmolph": "Reflux_cmd_lbmolph",
        "boilup_realized_lbmolph": "Boilup_lbmolph",
        "P_top_ctrl_pv_psia": "P_top_drum_psia",
        "Bottom_level_ctrl_pv": "Bottom_level_fraction",
    }.items():
        if report_name not in summary.columns and result_name in summary.columns:
            summary[report_name] = summary[result_name]
    # Core V3's report trajectory contains feed and pressure history that is
    # intentionally absent from the compact legacy summary CSV.  Bring across
    # only actual time-series evidence, aligned by simulation time; no endpoint
    # value is used as a substitute when that history is unavailable.
    trajectory_path = metadata.get("report_trajectory_jsonl")
    if trajectory_path:
        candidate = Path(str(trajectory_path)).expanduser()
        if not candidate.is_absolute():
            candidate = metadata_path.parent / candidate
        try:
            trajectory_records = [json.loads(line) for line in candidate.read_text(encoding="utf-8").splitlines() if line.strip()]
            trajectory = pd.DataFrame(trajectory_records)
        except (OSError, ValueError):
            trajectory = pd.DataFrame()
        if not trajectory.empty and "time_sec" in trajectory:
            if "feed_component_lbmolph" in trajectory:
                trajectory["F_lbmolph"] = trajectory["feed_component_lbmolph"].map(
                    lambda values: float(np.sum(values)) if isinstance(values, list) else np.nan
                )
            for target, source in {
                "F_lbmolph": "F_lbmolph",
                "P_top_psia": "top_pressure_psia",
                "P_bot_psia": "bottom_pressure_psia",
                "Feed_temperature_F": "feed_temperature_F",
                "Feed_pressure_psia": "feed_pressure_psia",
                "Total_liquid_inventory_lbmol": "liquid_inventory_lbmol",
                "Total_vapor_inventory_lbmol": "vapor_inventory_lbmol",
            }.items():
                if (
                    source not in trajectory
                    or (target in summary.columns and pd.to_numeric(summary[target], errors="coerce").notna().any())
                ):
                    continue
                source_time = pd.to_numeric(trajectory["time_sec"], errors="coerce")
                values = pd.to_numeric(trajectory[source], errors="coerce")
                valid = source_time.notna() & values.notna()
                if valid.any():
                    summary[target] = np.interp(
                        pd.to_numeric(summary["time_s"], errors="coerce"),
                        source_time[valid], values[valid], left=np.nan, right=np.nan,
                    )
    balance_path = metadata.get("report_balance_ledger_jsonl")
    if balance_path:
        candidate = Path(str(balance_path)).expanduser()
        if not candidate.is_absolute():
            candidate = metadata_path.parent / candidate
        try:
            balance_rows = [json.loads(line) for line in candidate.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, ValueError):
            balance_rows = []
    feed_conditions = metadata.get("feed_temperature_disturbance", {})
    if isinstance(feed_conditions, Mapping):
        for target, source in {
            "Feed_temperature_F": "disturbed_temperature_F",
            "Feed_pressure_psia": "pressure_psia",
        }.items():
            if (
                source not in feed_conditions
                or (target in summary.columns and pd.to_numeric(summary[target], errors="coerce").notna().any())
            ):
                continue
            value = _number(feed_conditions, source)
            if _finite(value):
                # This is a declared feed configuration, not a missing-history
                # endpoint fallback.  It is constant unless a feed event says otherwise.
                summary[target] = value
    start, end = _first_and_last(summary)

    run_id = str(metadata.get("run_id") or metadata_path.stem.replace("run_metadata_", ""))
    case_name = str(metadata.get("run_name") or Path(str(metadata.get("excel_path", "case"))).stem)
    output = Path(output_path).expanduser().resolve() if output_path else metadata_path.parent / f"run_report_{run_id}.docx"
    continuation = bool((metadata.get("native_checkpoint_init") or {}).get("loaded"))
    source_time = float((metadata.get("native_checkpoint_init") or {}).get("source_final_time_s") or 0.0)
    elapsed = float(metadata.get("elapsed_wall_sec") or _number(end, "wall_elapsed_s"))
    sim_time = float(metadata.get("final_time_s") or _number(end, "time_s"))
    sim_wall = sim_time / elapsed if elapsed > 0.0 else float("nan")

    doc = Document()
    _style_document(doc)
    section = doc.sections[0]
    _add_header_footer(doc, case_name)

    kicker = doc.add_paragraph()
    kicker.paragraph_format.space_after = Pt(5)
    _set_run(kicker.add_run("DYNAMIC DISTILLATION  /  COMPLETED RUN"), size=8.5, color=TEAL, bold=True)
    title = doc.add_paragraph(case_name, style="Title")
    title.paragraph_format.keep_with_next = True
    subtitle = doc.add_paragraph()
    subtitle.paragraph_format.space_after = Pt(12)
    _set_run(subtitle.add_run(str(metadata.get("run_description") or "Simulation operating report")), size=11, color=MID_GRAY)

    end_score = _number(end, "steady_state_score")
    gate = "PASS" if _number(end, "steady_state_flag") >= 0.5 else "NOT PASSED"
    final_t = pd.to_numeric(profile.get("time_s"), errors="coerce").max()
    final_profile_for_status = profile[
        np.isclose(pd.to_numeric(profile.get("time_s"), errors="coerce"), final_t)
    ]
    flash_failure_values = (
        final_profile_for_status["thermo_flash_failed"]
        if "thermo_flash_failed" in final_profile_for_status
        else pd.Series(0.0, index=final_profile_for_status.index)
    )
    flash_failures = int((pd.to_numeric(flash_failure_values, errors="coerce").fillna(0) > 0.5).sum())
    pressure_error = abs(_number(end, "P_top_psia") - _number(end, "P_top_psia_spec"))
    pressure_off_target = _finite(pressure_error) and pressure_error > max(2.0, 0.01 * _number(end, "P_top_psia_spec"))
    top_level_error = abs(_number(end, "Top_level_ctrl_pv") - _number(end, "Top_level_ctrl_sp"))
    bottom_level_error = abs(_number(end, "Bottom_level_ctrl_pv") - _number(end, "Bottom_level_ctrl_sp"))
    inventory_off_target = (
        (_finite(top_level_error) and top_level_error > 0.05)
        or (_finite(bottom_level_error) and bottom_level_error > 0.05)
    )
    run_validity = "REVIEW" if flash_failures or gate != "PASS" or pressure_off_target or inventory_off_target else "USABLE"
    _add_metric_strip(
        doc,
        [
            ("Run validity", run_validity, PALE_TEAL if run_validity == "USABLE" else PALE_GOLD),
            ("Dynamic gate", gate, PALE_TEAL if gate == "PASS" else PALE_GOLD),
            ("Final score", _fmt(end_score, 3), PALE_BLUE),
            ("Sim / wall", _fmt(sim_wall, 3), LIGHT_GRAY),
        ],
    )
    report_summary = None
    report_summary_path = metadata.get("report_summary")
    if report_summary_path:
        candidate = Path(str(report_summary_path)).expanduser()
        if not candidate.is_absolute():
            candidate = metadata_path.parent / candidate
        try:
            report_summary = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            report_summary = None
    if report_summary:
        doc.add_heading("Executive Verdict", level=1)
        _add_table(
            doc, ("Item", "Status"),
            (("Overall status", report_summary.get("overall_status", "NOT AVAILABLE")),
             ("Completion", report_summary.get("completion", {}).get("status", "NOT AVAILABLE")),
             ("Steady state", report_summary.get("steady_state", {}).get("status", "NOT AVAILABLE"))),
            (2.1, 4.84), header_fill=TEAL, font_size=8.2,
        )
        _add_run_narrative(doc, report_summary, metadata)
        reasons = report_summary.get("verdict_reasons", [])
        if reasons:
            doc.add_heading("Ranked Verdict Reasons", level=2)
            _add_table(doc, ("Check", "Severity", "Status", "Explanation"), [[item.get("check_id"), item.get("severity"), item.get("status"), item.get("explanation")] for item in reasons[:3]], (1.2, 0.8, 0.8, 4.14), font_size=7.8)
        doc.add_heading("Operating-Limit Assessment", level=1)
        _add_constraint_table(doc, report_summary.get("constraints", []))
        balances = report_summary.get("balances", {})
        balance_rows = balances.get("ledger_rows", [])
        if balance_rows:
            doc.add_heading("Material and Energy Balances", level=1)
            doc.add_paragraph(str(balances.get("detail", "Balance detail not reported.")))
            _add_balance_summary_table(doc, balances)
            for title, is_energy, separate_terms in (
                ("Material Balance", False, balances.get("material_has_separate_in_out", False)),
                ("Energy Balance", True, balances.get("energy_has_separate_in_out", False)),
            ):
                endpoint_times = sorted({float(row.get("time_sec", 0.0)) for row in balance_rows})
                selected_times = set(endpoint_times[:1] + endpoint_times[-1:])
                rows = [
                    row for row in balance_rows
                    if (str(row.get("quantity")) == "energy") is is_energy
                    and float(row.get("time_sec", 0.0)) in selected_times
                ]
                if not rows:
                    continue
                doc.add_heading(title, level=2)
                headers = (
                    ("Time (s)", "Volume", "Quantity", "In", "Out", "Accumulation", "Residual", "Normalized")
                    if separate_terms else
                    ("Time (s)", "Volume", "Quantity", "Net expected", "Accumulation", "Residual", "Normalized")
                )
                table_rows = []
                for row in rows:
                    base = [_fmt(row.get("time_sec"), 3), str(row.get("volume", "Not reported")), str(row.get("quantity", "Not reported"))]
                    terms = ([_fmt(row.get("in"), 5), _fmt(row.get("out"), 5)] if separate_terms else [_fmt(row.get("net_expected_change", row.get("in")), 5)])
                    table_rows.append([*base, *terms, _fmt(row.get("accumulation"), 5), _fmt(row.get("residual"), 5), _fmt(row.get("normalized_residual"), 5)])
                widths = (0.55, 0.75, 0.8, 0.65, 0.65, 0.85, 0.7, 0.85) if separate_terms else (0.55, 0.85, 0.9, 1.0, 0.95, 0.8, 0.9)
                _add_table(doc, headers, table_rows, widths, font_size=6.2)
        doc.add_heading("Controller Performance", level=1)
        controllers = report_summary.get("controllers", [])
        _add_controller_performance_tables(doc, controllers)
        doc.add_heading("Event and Disturbance Timeline", level=1)
        events = report_summary.get("events", {})
        doc.add_paragraph(str(events.get("detail", "Event timeline: not available in this artifact version.")))
        if events.get("records"):
            _add_event_table(doc, events["records"])
        doc.add_heading("Numerical Health", level=1)
        health = report_summary.get("numerical_health", {})
        _add_numerical_health_tables(doc, health)
    event_times_s = tuple(
        float(item["time_sec"])
        for item in (report_summary or {}).get("events", {}).get("records", ())
        if item.get("time_sec") is not None
    )
    qualification_time_s = next(
        (float(item["time_sec"]) for item in (report_summary or {}).get("events", {}).get("records", ()) if item.get("event_type") == "steady_state_qualification"),
        None,
    )

    assessment_notes = []
    if gate != "PASS":
        assessment_notes.append(f"The dynamic acceptance gate did not pass (final score {_fmt(end_score, 3)}).")
    if flash_failures:
        assessment_notes.append(f"The final tray snapshot reports {flash_failures} failed thermo flashes; interpret operating results as invalid until the thermo path is restored.")
    if pressure_off_target:
        assessment_notes.append(f"Top pressure is {_fmt(pressure_error, 2, ' psi')} from its logged target, so the rate gate does not establish acceptable pressure control.")
    if inventory_off_target:
        assessment_notes.append("At least one geometry-based vessel level remains more than five percentage points from setpoint.")
    if max(abs(_number(end, "Top_level_ctrl_pv")), abs(_number(end, "Top_level_ctrl_sp"))) > 1.5:
        assessment_notes.append("The top level loop reported molar holdup rather than a geometry-based level fraction.")
    if max(abs(_number(end, "Bottom_level_ctrl_pv")), abs(_number(end, "Bottom_level_ctrl_sp"))) > 1.5:
        assessment_notes.append("The bottom level loop reported molar holdup rather than a geometry-based level fraction.")
    if assessment_notes:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(4)
        _set_run(p.add_run("AUTOMATED ASSESSMENT  "), size=8.2, color=GOLD, bold=True)
        _set_run(p.add_run(" ".join(assessment_notes)), size=9.2, color=INK)

    doc.add_heading("Run Identity", level=1)
    init_kind = "Continuation from native checkpoint" if continuation else "Fresh start"
    identity = [
        ["Run ID", run_id],
        ["Started", str(metadata.get("started_at_local", "Not reported"))],
        ["Completed", str(metadata.get("ended_at_local", "Not reported"))],
        ["Run type", init_kind],
        ["Input workbook", str(metadata.get("excel_path", "Not reported"))],
        ["Input checkpoint", str((metadata.get("native_checkpoint_init") or {}).get("path") or "None")],
        ["Summary data", str(summary_path)],
        ["Tray-profile data", str(profile_path)],
    ]
    _add_table(doc, ["Item", "Value"], identity, [1.45, 5.49], header_fill=TEAL, font_size=8.2)

    doc.add_heading("Operating Snapshot", level=1)
    start_conditions = _condition_rows(start)
    end_conditions = _condition_rows(end)
    _add_table(
        doc,
        ["Parameter", "Start", "End", "Units"],
        [
            [
                e[0] if s[1] == "Not reported" else s[0],
                s[1],
                e[1],
                e[2] if s[1] == "Not reported" else s[2],
            ]
            for s, e in zip(start_conditions, end_conditions)
        ],
        [2.65, 1.45, 1.45, 1.25],
        font_size=8.3,
    )

    doc.add_heading("Product Composition", level=2)
    start_comps = _product_composition_rows(start)
    end_comps = _product_composition_rows(end)
    comp_rows = []
    for initial, final in zip(start_comps, end_comps):
        comp_rows.append([initial[0], initial[1], final[1], initial[2], final[2]])
    _add_table(
        doc,
        ["Component", "Distillate start", "Distillate end", "Bottoms start", "Bottoms end"],
        comp_rows,
        [1.55, 1.35, 1.35, 1.35, 1.35],
        header_fill=TEAL,
        font_size=8.2,
    )

    doc.add_page_break()
    doc.add_heading("Dynamic Trends", level=1)
    with tempfile.TemporaryDirectory(prefix="distillation_report_") as temp_dir:
        temp = Path(temp_dir)
        flow_chart = temp / "flows.png"
        control_chart = temp / "controls.png"
        steady_state_chart = temp / "steady_state_score.png"
        composition_chart = temp / "product_composition.png"
        state_chart = temp / "state_trends.png"
        balance_chart = temp / "balance_and_constraints.png"
        profile_chart = temp / "profiles.png"
        top_level_scale = 100.0 if max(
            abs(_number(end, "Top_level_ctrl_pv")), abs(_number(end, "Top_level_ctrl_sp"))
        ) <= 1.5 else 1.0
        bottom_level_scale = 100.0 if max(
            abs(_number(end, "Bottom_level_ctrl_pv")), abs(_number(end, "Bottom_level_ctrl_sp"))
        ) <= 1.5 else 1.0
        level_title = (
            "Vessel levels (%)"
            if top_level_scale == 100.0 and bottom_level_scale == 100.0
            else "Vessel level-controller PVs (mixed units; see operating snapshot)"
        )
        if _plot_series(
            summary,
            flow_chart,
            [
                ("Feed and product flows", (("F_lbmolph", "Feed", 1.0), ("D_lbmolph", "Distillate", 1.0), ("B_lbmolph", "Bottoms", 1.0))),
                ("Column traffic", (("total_reflux_used_lbmolph", "Reflux", 1.0), ("V_condensed_in_lbmolph", "Condensate", 1.0), ("boilup_realized_lbmolph", "Boilup", 1.0))),
            ],
            cumulative_offset_s=source_time,
            event_times_s=event_times_s,
            qualification_time_s=qualification_time_s,
        ):
            doc.add_picture(str(flow_chart), width=Inches(6.75))
        if _plot_series(
            summary,
            control_chart,
            [
                ("Top pressure", (("P_top_ctrl_pv_psia", "PV", 1.0), ("P_top_psia_spec", "Target", 1.0))),
                (level_title, (("Top_level_ctrl_pv", "Drum PV", top_level_scale), ("Top_level_ctrl_sp", "Drum SP", top_level_scale), ("Bottom_level_ctrl_pv", "Sump PV", bottom_level_scale), ("Bottom_level_ctrl_sp", "Sump SP", bottom_level_scale))),
                ("Heat duties", (("Q_cond_used_BTUph", "Condenser", 1.0e-6), ("Q_reb_used_BTUph", "Reboiler", 1.0e-6))),
                ("Level-controller outputs", (("D_lbmolph", "Distillate MV", 1.0), ("B_lbmolph", "Bottoms MV", 1.0))),
            ],
            cumulative_offset_s=source_time,
            event_times_s=event_times_s,
            qualification_time_s=qualification_time_s,
        ):
            doc.add_picture(str(control_chart), width=Inches(6.75))
        if _plot_series(
            summary,
            state_chart,
            [
                ("Column pressure (psia)", (("P_top_psia", "Top", 1.0), ("P_bot_psia", "Bottom", 1.0))),
                ("Product temperature (deg F)", (("T_Distillate_F", "Distillate", 1.0), ("T_sump_F", "Bottoms", 1.0))),
                ("Total inventory (lbmol)", (("Total_liquid_inventory_lbmol", "Liquid", 1.0), ("Total_vapor_inventory_lbmol", "Vapor", 1.0))),
            ],
            cumulative_offset_s=source_time,
            event_times_s=event_times_s,
            qualification_time_s=qualification_time_s,
        ):
            doc.add_picture(str(state_chart), width=Inches(6.75))
        if _plot_steady_state_score(
            summary,
            steady_state_chart,
            cumulative_offset_s=source_time,
            event_times_s=event_times_s,
            qualification_time_s=qualification_time_s,
        ):
            doc.add_picture(str(steady_state_chart), width=Inches(6.75))
        components = sorted(
            set(_component_names(summary.columns, "Distillate_x_"))
            | set(_component_names(summary.columns, "Bottoms_x_"))
        )
        composition_panels = [
            (
                "Distillate composition (mole fraction)",
                tuple((f"Distillate_x_{component}", _pretty_component(component), 1.0) for component in components),
            ),
            (
                "Bottoms composition (mole fraction)",
                tuple((f"Bottoms_x_{component}", _pretty_component(component), 1.0) for component in components),
            ),
        ] if components else []
        if composition_panels and _plot_series(
            summary,
            composition_chart,
            composition_panels,
            cumulative_offset_s=source_time,
            event_times_s=event_times_s,
            qualification_time_s=qualification_time_s,
        ):
            doc.add_picture(str(composition_chart), width=Inches(6.75))
        if _plot_balance_and_constraint_trends(
            trajectory,
            balance_rows,
            balance_chart,
            cumulative_offset_s=source_time,
            event_times_s=event_times_s,
            qualification_time_s=qualification_time_s,
        ):
            doc.add_picture(str(balance_chart), width=Inches(6.75))

        doc.add_heading("Final Tray Profiles", level=1)
        profile_assessment = _final_profile_assessment(profile)
        _add_profile_assessment_tables(doc, profile_assessment)
        if _plot_final_profiles(profile, profile_chart):
            doc.add_picture(str(profile_chart), width=Inches(6.75))

        landscape = doc.add_section()
        landscape.orientation = WD_ORIENT.LANDSCAPE
        landscape.page_width = Inches(11.0)
        landscape.page_height = Inches(8.5)
        landscape.top_margin = Inches(0.55)
        landscape.bottom_margin = Inches(0.55)
        landscape.left_margin = Inches(0.55)
        landscape.right_margin = Inches(0.55)
        _add_header_footer(doc, case_name)
        doc.add_heading("Final Tray Profile Table", level=1)
        final_t = pd.to_numeric(profile["time_s"], errors="coerce").max()
        final_profile = profile[np.isclose(pd.to_numeric(profile["time_s"], errors="coerce"), final_t)]
        if "node_type" in final_profile:
            final_profile = final_profile[
                final_profile["node_type"].astype(str).isin(("stage", "tray"))
            ]
        final_profile = final_profile.sort_values("stage")
        comp_names = [c[2:] for c in final_profile.columns if str(c).startswith("x_") and not str(c).startswith("x_eq_")][:3]
        tray_rows = []
        for _, row in final_profile.iterrows():
            tray_rows.append(
                [
                    str(int(float(row["stage"]))),
                    _fmt(row.get("T_F"), 2),
                    _fmt(row.get("P_psia_hyd"), 3),
                    _fmt(row.get("L_out_used_lbmolph"), 1),
                    _fmt(row.get("V_out_lbmolph"), 1),
                    *[_fmt(row.get(f"x_{name}"), 4) for name in comp_names],
                    *[_fmt(row.get(f"y_{name}"), 4) for name in comp_names],
                ]
            )
        headers = ["Stage", "T (deg F)", "P (psia)", "L (lbmol/h)", "V (lbmol/h)"]
        headers += [f"x {_pretty_component(name)}" for name in comp_names]
        headers += [f"y {_pretty_component(name)}" for name in comp_names]
        widths = [0.55, 0.78, 0.82, 0.95, 0.95] + [0.76] * (2 * len(comp_names))
        _add_table(doc, headers, tray_rows, widths, header_fill=NAVY, font_size=7.2)

    portrait = doc.add_section()
    portrait.orientation = WD_ORIENT.PORTRAIT
    portrait.page_width = Inches(8.5)
    portrait.page_height = Inches(11.0)
    portrait.top_margin = Inches(0.72)
    portrait.bottom_margin = Inches(0.68)
    portrait.left_margin = Inches(0.78)
    portrait.right_margin = Inches(0.78)
    _add_header_footer(doc, case_name)
    doc.add_heading("Simulation Configuration", level=1)
    _add_table(doc, ["Parameter", "Value"], _parameter_rows(metadata), [3.0, 3.94], header_fill=TEAL, font_size=7.8)
    command, command_note = _launch_command_for_report(metadata)
    if command:
        doc.add_heading("CLI Command", level=2)
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(3)
        _set_run(p.add_run(command), size=7.5, color=INK)
        note = doc.add_paragraph(command_note)
        _set_run(note.runs[0], size=7.5, color=MID_GRAY, italic=True)
    if report_summary:
        doc.add_heading("Artifact Index", level=1)
        _add_artifact_index(doc, report_summary)

    doc.core_properties.title = f"Dynamic Distillation Run Report - {case_name}"
    doc.core_properties.subject = f"Run {run_id}"
    doc.core_properties.keywords = "dynamic distillation, run report, process simulation"
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)
    return str(output)


def generate_core_v3_run_report(
    summary: Mapping[str, Any],
    *,
    output_path: str | Path,
    title: str = "Core V3 Dynamic Run",
    metadata: Optional[Mapping[str, Any]] = None,
    trajectory: Optional[Mapping[str, Any]] = None,
) -> str:
    """Create a DOCX report from a structured Core V3 end-of-run summary."""
    output = Path(output_path).expanduser().resolve()
    duties = summary["duties"]
    products = summary["products"]
    levels = summary["terminal_levels"]
    steady = summary["steady_state"]
    metadata_values = metadata or {}
    report = build_report_summary_v2(
        summary, metadata=metadata_values, trajectory=trajectory
    )
    simulated_seconds = float(summary["time_sec"])
    elapsed_seconds = metadata_values.get(
        "wall_clock_sec",
        metadata_values.get("wall_elapsed_s", metadata_values.get("elapsed_wall_sec")),
    )
    ratio = metadata_values.get("clock_time_per_sim_time", metadata_values.get("simulation_wall_ratio"))
    if ratio is None and elapsed_seconds is not None and simulated_seconds > 0.0:
        ratio = float(elapsed_seconds) / simulated_seconds
    doc = Document()
    _style_document(doc)
    _add_header_footer(doc, title)

    kicker = doc.add_paragraph()
    _set_run(kicker.add_run("DYNAMIC DISTILLATION  /  CORE V3 RUN"), size=8.5, color=TEAL, bold=True)
    doc.add_paragraph(title, style="Title")
    if metadata:
        details = []
        for key in (
            "classification",
            "decision",
            "started_at_local",
            "ended_at_local",
            "time_sec",
            "timestep_sec",
        ):
            if key in metadata and metadata[key] is not None:
                details.append(f"{key.replace('_', ' ').title()}: {metadata[key]}")
        details.append(
            "Report generated: "
            + datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
        )
        if details:
            paragraph = doc.add_paragraph(" | ".join(details))
            _set_run(paragraph.runs[0], size=9.5, color=MID_GRAY)

    doc.add_paragraph("Run Identity", style="Heading 1")
    identity = [
        ["Status", str((metadata or {}).get("classification", "completed"))],
        ["Simulation started", str((metadata or {}).get("started_at_local", "Not recorded"))],
        ["Simulation ended", str((metadata or {}).get("ended_at_local", "Not recorded"))],
        [
            "Report generated",
            datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
        ],
        ["Simulated time", _fmt(summary["time_sec"], 3, " s")],
        ["Elapsed clock time", _fmt(elapsed_seconds, 3, " s")],
        ["Clock / simulated time", _fmt(ratio, 6)],
        ["CLI command", str(metadata_values.get("launch_command", "Not recorded"))],
        ["Input workbook", str((metadata or {}).get("workbook", (metadata or {}).get("excel_path", "Not reported")))],
        ["Source checkpoint", str((metadata or {}).get("started_from_checkpoint", "None"))],
    ]
    _add_table(doc, ("Item", "Value"), identity, (1.55, 5.39), header_fill=TEAL, font_size=8.2)

    doc.add_paragraph("Executive Verdict", style="Heading 1")
    verdict_rows = [
        ["Overall status", report["overall_status"]],
        ["Simulation completed", report["completion"]["status"]],
        ["Steady state", report["steady_state"]["status"]],
        ["Evidence completeness", "PARTIAL" if any(item["status"] == "NOT EVALUATED" for item in report["constraints"]) else "COMPLETE"],
    ]
    _add_table(doc, ("Item", "Status"), verdict_rows, (2.2, 4.74), header_fill=TEAL)
    _add_run_narrative(doc, report, metadata or {})
    doc.add_paragraph("Ranked Verdict Reasons", style="Heading 2")
    reason_rows = [[item["check_id"], item["severity"], item["status"], item["explanation"]] for item in report["verdict_reasons"]] or [["None", "", "", "No adverse reason reported."]]
    _add_table(doc, ("Check", "Severity", "Status", "Explanation"), reason_rows, (1.25, 0.8, 0.8, 4.09), font_size=8.0)

    doc.add_paragraph("Initial, Final, and Delta", style="Heading 1")
    metric_rows = []
    for item in report["initial_final_delta"]:
        def display(field: str) -> str:
            value = item[field]
            return _fmt(value["value"], 4) if value["data_state"] == "observed" else "Not reported"
        metric_rows.append([item["variable"], display("initial"), display("final"), display("change"), display("minimum"), display("maximum"), item["units"]])
    _add_table(doc, ("Variable", "Initial", "Final", "Change", "Minimum", "Maximum", "Units"), metric_rows, (1.35, 0.75, 0.75, 0.75, 0.75, 0.75, 0.84), font_size=7.5)

    doc.add_paragraph("Steady-State Assessment", style="Heading 1")
    steady_rows = []
    for name, value in sorted(report["steady_state"].get("terms", {}).items()):
        steady_rows.append([name.replace("_", " "), _fmt(value, 6), "1.0", _fmt(value, 6), "PASS" if value <= 1.0 else "REVIEW"])
    _add_table(doc, ("Term", "Score", "Limit", "Ratio to limit", "Status"), steady_rows, (2.5, 1.0, 0.85, 1.35, 1.24), font_size=8.0)

    doc.add_paragraph("Operating-Limit Assessment", style="Heading 1")
    _add_constraint_table(doc, report["constraints"])
    doc.add_paragraph("Material and Energy Balances", style="Heading 1")
    doc.add_paragraph(report["balances"]["detail"])
    _add_balance_summary_table(doc, report["balances"])
    def add_balance_table(title: str, *, energy: bool, has_separate_terms: bool) -> None:
        rows = []
        for key in ("initial_interval", "final_interval"):
            interval = report["balances"].get(key)
            if interval:
                rows.extend(
                    [
                        interval["label"], _fmt(interval["time_sec"], 3),
                        str(row.get("volume", "Not reported")),
                        str(row.get("component") or row.get("quantity", "Not reported")),
                        *(
                            [_fmt(row.get("in"), 5), _fmt(row.get("out"), 5)]
                            if has_separate_terms else
                            [_fmt(row.get("net_expected_change", row.get("in")), 5)]
                        ),
                        _fmt(row.get("accumulation"), 5), _fmt(row.get("residual"), 5),
                        _fmt(row.get("normalized_residual"), 5),
                    ]
                    for row in interval["rows"] if (row.get("quantity") == "energy") is energy
                )
        if not rows:
            return
        doc.add_paragraph(title, style="Heading 2")
        headers = (
            ("Interval", "Time (s)", "Volume", "Quantity", "In", "Out", "Accumulation", "Residual", "Normalized")
            if has_separate_terms else
            ("Interval", "Time (s)", "Volume", "Quantity", "Net expected", "Accumulation", "Residual", "Normalized")
        )
        widths = (0.8, 0.55, 0.75, 0.75, 0.65, 0.65, 0.85, 0.7, 0.85) if has_separate_terms else (0.85, 0.55, 0.75, 0.75, 0.95, 0.9, 0.8, 0.85)
        _add_table(doc, headers, rows, widths, font_size=6.2)

    add_balance_table("Material Balance", energy=False, has_separate_terms=report["balances"].get("material_has_separate_in_out", False))
    add_balance_table("Energy Balance", energy=True, has_separate_terms=report["balances"].get("energy_has_separate_in_out", False))
    doc.add_paragraph("Controller Performance", style="Heading 1")
    _add_controller_performance_tables(doc, report["controllers"])
    doc.add_paragraph("Event and Disturbance Timeline", style="Heading 1")
    doc.add_paragraph(report["events"]["detail"])
    if report["events"].get("records"):
        _add_event_table(doc, report["events"]["records"])
    doc.add_paragraph("Numerical Health", style="Heading 1")
    numerical_health = report["numerical_health"]
    _add_numerical_health_tables(doc, numerical_health)

    doc.add_paragraph("Operating Summary", style="Heading 1")
    _add_metric_strip(
        doc,
        (
            ("Condenser duty", _fmt(duties["condenser_BTUph"], 1, " BTU/h"), PALE_BLUE),
            ("Reboiler duty", _fmt(duties["reboiler_BTUph"], 1, " BTU/h"), PALE_GOLD),
            ("Steady-state score", _fmt(steady["score"], 4), PALE_TEAL),
        ),
    )
    product_rows = []
    component_count = max(
        (len(products[key].get("mole_fraction", {})) for key in ("distillate", "bottoms")),
        default=0,
    )
    for key, label in (("distillate", "Distillate"), ("bottoms", "Bottoms")):
        stream = products[key]
        composition = ", ".join(
            f"{name}={float(value):.6f}"
            for name, value in stream["mole_fraction"].items()
        )
        product_rows.append(
            [
                label,
                _fmt(stream["flow_lbmolph"], 3, " lbmol/h"),
                _fmt(stream["temperature_F"], 2, " F"),
                _fmt(stream["pressure_psia"], 2, " psia"),
                _fmt(stream.get("molar_enthalpy_BTU_lbmol"), 2, " BTU/lbmol"),
                _fmt(stream.get("molar_density_lbmol_ft3"), 4, " lbmol/ft3"),
                composition if component_count <= 2 else "See product composition table",
            ]
        )
    _add_table(
        doc,
        ("Product", "Flow", "Temperature", "Pressure", "Enthalpy", "Density", "Mole fractions"),
        product_rows,
        (0.65, 0.95, 0.8, 0.75, 1.0, 0.9, 1.89),
        font_size=7.5,
    )
    if component_count > 2:
        doc.add_paragraph("Product Composition", style="Heading 2")
        composition_rows = [
            [label, component, _fmt(value, 6)]
            for key, label in (("distillate", "Distillate"), ("bottoms", "Bottoms"))
            for component, value in products[key]["mole_fraction"].items()
        ]
        _add_table(
            doc,
            ("Product", "Component", "Mole fraction"),
            composition_rows,
            (1.5, 2.5, 2.79),
            font_size=8.0,
        )
    doc.add_paragraph(
        f"Terminal levels: distillate drum {_fmt(100.0 * float(levels['distillate_drum_fraction']), 3, '%')}; "
        f"bottom drum {_fmt(100.0 * float(levels['bottom_drum_fraction']), 3, '%')}. "
        f"Steady state: {'PASS' if steady['steady'] else 'REVIEW'}."
    )

    if trajectory is not None and "time_sec" in trajectory:
        times = np.asarray(trajectory["time_sec"], dtype=float)
        if times.ndim == 1 and times.size > 1:
            trend = pd.DataFrame({"time_s": times})
            for key, column in (("condenser_duty_BTUph", "Qc_BTUph"),):
                if key in trajectory and np.asarray(trajectory[key]).shape == times.shape:
                    trend[column] = np.asarray(trajectory[key], dtype=float)
            for key, column in (("pressure_psia", "P_psia"), ("temperature_F", "T_F")):
                if key in trajectory:
                    values = np.asarray(trajectory[key], dtype=float)
                    if values.ndim == 2 and values.shape[0] == times.size:
                        trend[f"{column}_top"] = values[:, 0]
                        trend[f"{column}_bottom"] = values[:, -1]
            for key, column in (
                ("liquid_component_inventory_lbmol", "liquid_inventory_lbmol"),
                ("vapor_component_inventory_lbmol", "vapor_inventory_lbmol"),
            ):
                if key in trajectory:
                    values = np.asarray(trajectory[key], dtype=float)
                    if values.ndim == 3 and values.shape[0] == times.size:
                        trend[column] = np.sum(values, axis=(1, 2))
            product_history = False
            for key, column in (
                ("distillate_flow_lbmolph", "distillate_lbmolph"),
                ("bottoms_flow_lbmolph", "bottoms_lbmolph"),
            ):
                values = np.asarray(trajectory[key], dtype=float) if key in trajectory else None
                if values is not None and values.shape == times.shape:
                    trend[column] = values
                    product_history = True
            doc.add_page_break()
            doc.add_paragraph("Dynamic Trends", style="Heading 1")
            if not product_history:
                doc.add_paragraph(
                    "Product-flow trend: not available; terminal values were not substituted for a history."
                )
            with tempfile.TemporaryDirectory(prefix="core_v3_report_") as temp_dir:
                chart = Path(temp_dir) / "dynamic_trends.png"
                if _plot_series(
                    trend,
                    chart,
                    [
                        ("Product flows (lbmol/h)", (("distillate_lbmolph", "Distillate", 1.0), ("bottoms_lbmolph", "Bottoms", 1.0))),
                        ("Pressure (psia)", (("P_psia_top", "Top", 1.0), ("P_psia_bottom", "Bottom", 1.0))),
                        ("Temperature (deg F)", (("T_F_top", "Top", 1.0), ("T_F_bottom", "Bottom", 1.0))),
                        ("Duties (MMBtu/h)", (("Qc_BTUph", "Condenser", 1.0e-6),)),
                        ("Stored inventories (lbmol)", (("liquid_inventory_lbmol", "Liquid", 1.0), ("vapor_inventory_lbmol", "Vapor", 1.0))),
                    ],
                    cumulative_offset_s=0.0,
                    event_times_s=tuple(
                        float(item["time_sec"])
                        for item in report["events"].get("records", ())
                        if item.get("time_sec") is not None
                    ),
                    qualification_time_s=next(
                        (float(item["time_sec"]) for item in report["events"].get("records", ()) if item.get("event_type") == "steady_state_qualification"),
                        None,
                    ),
                ):
                    doc.add_picture(str(chart), width=Inches(6.75))

    doc.add_paragraph("Final Volume Profiles", style="Heading 1")
    profile_assessment = report.get("profile_assessment", {})
    if profile_assessment.get("data_state") == "observed":
        doc.add_paragraph(
            "Profile summary: "
            f"feed stage {profile_assessment.get('feed_stage', 'Not reported')}; "
            f"top-to-bottom pressure drop {_fmt(profile_assessment['top_to_bottom_pressure_drop_psia'], 3, ' psia')}; "
            f"temperature range {_fmt(profile_assessment['temperature_minimum_F'], 2, ' F')} to "
            f"{_fmt(profile_assessment['temperature_maximum_F'], 2, ' F')}."
        )
    with tempfile.TemporaryDirectory(prefix="core_v3_profiles_") as temp_dir:
        profile_chart = Path(temp_dir) / "final_profiles.png"
        if _plot_core_v3_profiles(summary["profiles"], profile_chart):
            doc.add_picture(str(profile_chart), width=Inches(6.75))
    components = tuple(products["distillate"]["mole_fraction"].keys())
    profile_rows = []
    for row in summary["profiles"]:
        liquid_x = ", ".join(
            f"{name}={float(row['liquid_mole_fraction'][name]):.5f}" for name in components
        )
        vapor_y = ", ".join(
            f"{name}={float(row['vapor_mole_fraction'][name]):.5f}" for name in components
        )
        profile_rows.append(
            [
                row["volume"],
                row["node_type"],
                _fmt(row["temperature_F"], 2),
                _fmt(row["pressure_psia"], 2),
                _fmt(row["liquid_inventory_lbmol"], 2),
                _fmt(row["vapor_inventory_lbmol"], 2),
                _fmt(row.get("liquid_flow_out_lbmolph"), 2),
                _fmt(row.get("vapor_flow_out_lbmolph"), 2),
                liquid_x,
                vapor_y,
            ]
        )
    for start in range(0, len(profile_rows), 15):
        if start:
            doc.add_paragraph("Final Volume Profiles (continued)", style="Heading 2")
        _add_table(
            doc,
            ("Volume", "Type", "T (F)", "P (psia)", "ML", "MV", "L out", "V out", "Liquid x", "Vapor y"),
            profile_rows[start : start + 15],
            (0.95, 0.65, 0.5, 0.6, 0.55, 0.55, 0.6, 0.6, 1.2, 1.2),
            font_size=7.5,
        )
    config_rows = []
    for key in (
        "classification",
        "decision",
        "timestep_sec",
        "duration_completed_sec",
        "duration_requested_sec",
        "feed_multiplier",
        "provider",
    ):
        if metadata and key in metadata:
            config_rows.append([key.replace("_", " ").title(), str(metadata[key])])
    tuning = (metadata or {}).get("controller_tuning")
    if isinstance(tuning, Mapping):
        for key in ("drum_kc", "drum_ti_sec", "sump_kc", "sump_ti_sec"):
            if key in tuning:
                config_rows.append([key.replace("_", " ").title(), str(tuning[key])])
    if config_rows:
        doc.add_paragraph("Simulation Configuration", style="Heading 1")
        _add_table(doc, ("Parameter", "Value"), config_rows, (2.3, 4.64), header_fill=TEAL, font_size=8.0)
    launch_command = str((metadata or {}).get("launch_command") or "").strip()
    if launch_command:
        doc.add_paragraph("Exact Launch Command", style="Heading 2")
        paragraph = doc.add_paragraph(launch_command)
        _set_run(paragraph.runs[0], size=7.5, color=INK)
    doc.add_paragraph("Artifact Index", style="Heading 1")
    _add_artifact_index(doc, report)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)
    return str(output)


__all__ = ["generate_core_v3_run_report", "generate_run_report"]
