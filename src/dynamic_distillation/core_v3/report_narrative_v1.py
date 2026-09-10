"""Deterministic, evidence-bound prose for Core V3 report introductions."""

from __future__ import annotations

from typing import Any, Mapping


NARRATIVE_SCHEMA_VERSION = "core-v3-report-narrative-v1"


def _observed_metric(report: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
    for item in report.get("initial_final_delta", []):
        if item.get("variable") == name and item.get("initial", {}).get("data_state") == "observed":
            return item
    return None


def _number(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "not reported"


def build_report_narrative_v1(report: Mapping[str, Any], *, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Create fixed-language paragraphs from observed/derived report facts only."""

    metadata = metadata or {}
    facts: list[str] = []
    name = str(metadata.get("run_name") or report.get("run_id") or "this run")
    duration = report.get("provenance", {}).get("completed_duration_sec")
    checkpoint = report.get("provenance", {}).get("source_checkpoint")
    continuation = f" It continued from checkpoint `{checkpoint}`." if checkpoint else ""
    paragraphs = [
        f"Run `{name}` completed {str(report.get('overall_status', 'NOT EVALUATED')).lower()} after {_number(duration, 2)} s of simulated time.{continuation}"
    ]
    facts.extend(["overall_status", "provenance.completed_duration_sec"])
    feed = _observed_metric(report, "Feed flow")
    top_pressure = _observed_metric(report, "Top pressure")
    bottom_pressure = _observed_metric(report, "Bottom pressure")
    if feed:
        text = f"Feed flow changed from {_number(feed['initial']['value'], 2)} to {_number(feed['final']['value'], 2)} {feed['units']}"
        if top_pressure and bottom_pressure:
            text += f"; top pressure changed from {_number(top_pressure['initial']['value'], 3)} to {_number(top_pressure['final']['value'], 3)} psia and bottom pressure from {_number(bottom_pressure['initial']['value'], 3)} to {_number(bottom_pressure['final']['value'], 3)} psia"
        paragraphs.append(text + ".")
        facts.extend(["initial_final_delta.Feed flow", "initial_final_delta.Top pressure", "initial_final_delta.Bottom pressure"])
    constraints = report.get("constraints", [])
    passed = [str(row.get("check")) for row in constraints if row.get("status") == "PASS"]
    unevaluated = [str(row.get("check")) for row in constraints if row.get("status") == "NOT EVALUATED"]
    if passed:
        paragraphs.append("Observed operating-limit checks passed for " + ", ".join(passed) + ".")
        facts.append("constraints")
    if unevaluated:
        paragraphs.append("The following checks were not evaluated because their required evidence was unavailable: " + ", ".join(unevaluated) + ".")
        facts.append("constraints.not_evaluated")
    balances = report.get("balances", {}).get("summaries", [])
    if balances:
        items = [f"{row.get('quantity')} max residual {_number(row.get('maximum_absolute_residual'), 3)} {row.get('units')}" for row in balances]
        paragraphs.append("Balance evidence reports " + "; ".join(items) + ".")
        facts.append("balances.summaries")
    controllers = report.get("controllers", [])
    if controllers:
        items = [f"{row.get('controller')} final error {_number(row.get('final_error'), 5)}" for row in controllers]
        paragraphs.append("Controller tracking finished with " + "; ".join(items) + ".")
        facts.append("controllers")
    health = report.get("numerical_health", {})
    if health:
        rejected = health.get("rejected_steps")
        rejected_text = str(rejected) if rejected not in (None, "not_available") else "not reported"
        paragraphs.append(
            f"Numerical evidence records {health.get('accepted_steps', 'not reported')} accepted steps, {rejected_text} rejected steps, "
            f"maximum scaled residual {_number(health.get('maximum_residual_infinity_norm'), 3)}, and termination `{health.get('termination_reason', 'not reported')}`."
        )
        facts.append("numerical_health")
    limitations = []
    if any(row.get("saturation_data_state") != "observed" for row in controllers):
        limitations.append("controller saturation")
    if any(row.get("settling_data_state") != "observed" for row in controllers):
        limitations.append("controller settling time")
    if limitations:
        paragraphs.append("Unavailable controller evidence: " + " and ".join(limitations) + "; no conclusion is drawn for those measures.")
        facts.append("controllers.data_state")
    return {"narrative_schema_version": NARRATIVE_SCHEMA_VERSION, "data_state": "derived", "paragraphs": paragraphs, "facts_used": facts}


__all__ = ["NARRATIVE_SCHEMA_VERSION", "build_report_narrative_v1"]
