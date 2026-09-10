"""Deterministic baseline/candidate comparison for Core V3 report summaries."""

from __future__ import annotations

from typing import Any, Mapping


COMPARISON_SCHEMA_VERSION = "core-v3-report-comparison-v1"


def _numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metrics(report: Mapping[str, Any]) -> dict[str, float]:
    values: dict[str, float] = {}
    for item in report.get("initial_final_delta", ()):
        final = item.get("final", {})
        if final.get("data_state") == "observed":
            value = _numeric(final.get("value"))
            if value is not None:
                values[str(item.get("variable"))] = value
    steady = _numeric(dict(report.get("steady_state", {})).get("score"))
    if steady is not None:
        values["steady_state_score"] = steady
    return values


def compare_report_summaries(
    baseline: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare persisted v2 summaries without interpreting missing evidence."""
    base_metrics = _metrics(baseline)
    candidate_metrics = _metrics(candidate)
    kpis = []
    for name in sorted(set(base_metrics) | set(candidate_metrics)):
        left, right = base_metrics.get(name), candidate_metrics.get(name)
        kpis.append({"metric": name, "baseline": left, "candidate": right, "delta": None if left is None or right is None else right - left, "data_state": "observed" if left is not None and right is not None else "not_available"})
    base_constraints = {str(item.get("check")): item.get("status") for item in baseline.get("constraints", ())}
    candidate_constraints = {str(item.get("check")): item.get("status") for item in candidate.get("constraints", ())}
    changes = [{"check": name, "baseline": base_constraints.get(name, "NOT AVAILABLE"), "candidate": candidate_constraints.get(name, "NOT AVAILABLE"), "changed": base_constraints.get(name) != candidate_constraints.get(name)} for name in sorted(set(base_constraints) | set(candidate_constraints))]
    return {"comparison_schema_version": COMPARISON_SCHEMA_VERSION, "baseline_run_id": baseline.get("run_id"), "candidate_run_id": candidate.get("run_id"), "baseline_status": baseline.get("overall_status"), "candidate_status": candidate.get("overall_status"), "kpi_deltas": kpis, "constraint_changes": changes, "profile_difference": {"status": "NOT EVALUATED", "detail": "Profile comparison requires aligned persisted profiles."}, "balance_change": {"baseline": baseline.get("balances", {}).get("maximum_absolute_residual"), "candidate": candidate.get("balances", {}).get("maximum_absolute_residual")}, "numerical_health_change": {"baseline": baseline.get("numerical_health", {}).get("performance", {}), "candidate": candidate.get("numerical_health", {}).get("performance", {})}}


__all__ = ["COMPARISON_SCHEMA_VERSION", "compare_report_summaries"]
