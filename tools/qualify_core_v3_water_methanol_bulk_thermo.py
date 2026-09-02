#!/usr/bin/env python
"""Compare bulk thermo providers against the fixed ChemSep water-methanol state."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_provider_governed_numerical as dd092  # noqa: E402
from audit_core_v3_water_methanol_starting_state import (  # noqa: E402
    DEFAULT_WORKBOOK,
    _source_mapping,
)
from dynamic_distillation.column_spec_builder_v1 import (  # noqa: E402
    build_column_spec_from_case,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (  # noqa: E402
    BubbleSolveSettings,
    solve_local_bubble,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel  # noqa: E402
from dynamic_distillation.thermo_clapeyron_provider_v1 import (  # noqa: E402
    ThermoClapeyronProviderV1,
)


DEFAULT_JSON = Path("logs/core_v3_water_methanol_bulk_thermo_qualification_20260901.json")
DEFAULT_DOC = Path("docs/core_v3_water_methanol_bulk_thermo_qualification_20260901.md")
DEFAULT_CHEMSEP_EXPORT = Path("water-methanol-ChemSep.xls")
DWSIM_PACKAGES = ("unifac", "nrtl", "modfac")
CLAPEYRON_MODELS = ("UNIFAC", "NRTL", "VTPR")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _short_error(error: Exception) -> str:
    text = str(error).strip().splitlines()
    return f"{type(error).__name__}: {text[0] if text else 'unknown error'}"


def _chemsep_method(export_path: Path) -> dict[str, Any]:
    data = export_path.read_bytes()
    strings: list[tuple[int, str]] = []
    for pattern, encoding in (
        (rb"[\x20-\x7e]{4,}", "ascii"),
        (rb"(?:[\x20-\x7e]\x00){4,}", "utf-16le"),
    ):
        for match in re.finditer(pattern, data):
            strings.append((match.start(), match.group().decode(encoding)))
    ordered = [text.strip() for _offset, text in sorted(strings) if text.strip()]

    def first(prefix: str) -> str:
        return next(text for text in ordered if text.startswith(prefix))

    return {
        "export": str(export_path),
        "export_sha256": hashlib.sha256(data).hexdigest(),
        "k_value_model": first("DECHEMA K model"),
        "activity_coefficient_model": first("UNIFAC Activity coefficient"),
        "vapor_pressure_model": first("Antoine Vapour pressure"),
        "enthalpy_model": first("Excess Enthalpy"),
        "unifac_main_group_bip_record": first("2 289.6 -181"),
    }


def _evaluate_provider(
    *,
    identity: str,
    provider: Any,
    source: dict[str, Any],
) -> dict[str, Any]:
    started = time.perf_counter()
    x = np.asarray(source["liquid_mole_fraction"], dtype=float)
    tail_y = np.asarray(source["vapor_mole_fraction"], dtype=float)
    temperature = np.asarray(source["temperature_F"], dtype=float)
    pressure = np.asarray(source["pressure_psia"], dtype=float)
    residual = []
    for stage_index in range(1, len(x) - 1):
        y = tail_y[stage_index - 1]
        phi_liquid = provider.phase_fugacity_coefficients(
            "liquid", temperature[stage_index], pressure[stage_index], x[stage_index]
        )
        phi_vapor = provider.phase_fugacity_coefficients(
            "vapor", temperature[stage_index], pressure[stage_index], y
        )
        residual.append(np.log(y * phi_vapor / (x[stage_index] * phi_liquid)))
    residual_array = np.asarray(residual, dtype=float)

    feed_component = np.asarray(source["feed_component_lbmolph"], dtype=float)
    feed_total = float(np.sum(feed_component))
    h_feed = provider.phase_enthalpy_BTU_lbmol(
        "liquid",
        float(source["feed_temperature_F"]),
        float(source["feed_pressure_psia"]),
        feed_component / feed_total,
    )
    h_top = provider.phase_enthalpy_BTU_lbmol(
        "liquid", temperature[0], pressure[0], x[0]
    )
    h_bottom = provider.phase_enthalpy_BTU_lbmol(
        "liquid", temperature[-1], pressure[-1], x[-1]
    )
    external_energy = (
        feed_total * h_feed
        + float(source["condenser_duty_BTUph"])
        + float(source["reboiler_duty_BTUph"])
        - float(source["distillate_reference_lbmolph"]) * h_top
        - float(source["bottoms_reference_lbmolph"]) * h_bottom
    )

    audit = ProviderCallAudit(provider_identity=identity)
    bubbles = []
    for label, index, guess in (
        ("top", 0, tail_y[0]),
        ("bottom", len(x) - 1, tail_y[-2]),
    ):
        bubble = solve_local_bubble(
            provider,
            audit,
            pressure_psia=float(pressure[index]),
            liquid_x=x[index],
            temperature_guess_F=float(temperature[index]),
            vapor_guess=guess,
            state_id=f"bulk_thermo:{identity}:{label}",
            evaluation_kind="preparation",
            settings=BubbleSolveSettings(),
        )
        if not bubble.success:
            raise RuntimeError(f"{label} bubble reconstruction failed")
        bubbles.append(
            {
                "terminal": label,
                "workbook_temperature_F": float(temperature[index]),
                "bubble_temperature_F": float(bubble.temperature_F),
                "temperature_difference_F": float(
                    bubble.temperature_F - temperature[index]
                ),
                "vapor_mole_fraction": [
                    float(value) for value in bubble.vapor_mole_fraction
                ],
                "residual_inf_norm": float(bubble.residual_inf_norm),
            }
        )
    return {
        "identity": identity,
        "available": True,
        "core_bulk_interface_compatible": True,
        "interior_log_fugacity_residual": residual_array.tolist(),
        "maximum_interior_abs_log_fugacity_residual": float(
            np.max(np.abs(residual_array))
        ),
        "rms_interior_log_fugacity_residual": float(
            np.sqrt(np.mean(residual_array**2))
        ),
        "fixed_state_external_energy_rate_BTUph": float(external_energy),
        "fixed_state_required_condenser_duty_BTUph": float(
            source["condenser_duty_BTUph"] - external_energy
        ),
        "terminal_bubbles": bubbles,
        "wall_clock_sec": float(time.perf_counter() - started),
    }


def build_report(workbook: Path = DEFAULT_WORKBOOK) -> dict[str, Any]:
    workbook_path = _rooted(workbook).resolve()
    case = load_case_from_excel(str(workbook_path))
    column = build_column_spec_from_case(case)
    source = _source_mapping(column)
    chemsep_export = _rooted(DEFAULT_CHEMSEP_EXPORT).resolve()
    factories: list[tuple[str, Callable[[], Any]]] = []
    for package in DWSIM_PACKAGES:
        factories.append(
            (f"dwsim_{package}", lambda package=package: dd092._provider(column, package))
        )
    for model in CLAPEYRON_MODELS:
        factories.append(
            (
                f"clapeyron_{model.lower()}",
                lambda model=model: ThermoClapeyronProviderV1(
                    column.components_excel,
                    column.components_dwsim,
                    model_name=model,
                ),
            )
        )

    candidates = []
    for identity, factory in factories:
        started = time.perf_counter()
        try:
            provider = factory()
            if hasattr(provider, "validate_backend_available"):
                provider.validate_backend_available()
            candidates.append(
                _evaluate_provider(identity=identity, provider=provider, source=source)
            )
        except Exception as error:
            candidates.append(
                {
                    "identity": identity,
                    "available": False,
                    "core_bulk_interface_compatible": False,
                    "error": _short_error(error),
                    "wall_clock_sec": float(time.perf_counter() - started),
                }
            )

    compatible = [item for item in candidates if item["core_bulk_interface_compatible"]]
    ranked = sorted(
        compatible,
        key=lambda item: (
            item["maximum_interior_abs_log_fugacity_residual"],
            abs(item["fixed_state_external_energy_rate_BTUph"]),
        ),
    )
    selected = ranked[0]["identity"] if ranked else None
    return {
        "schema_id": "core-v3-water-methanol-bulk-thermo-qualification-v1",
        "workbook": str(workbook_path),
        "workbook_sha256": hashlib.sha256(workbook_path.read_bytes()).hexdigest(),
        "components": list(column.components_excel),
        "chemsep_method": _chemsep_method(chemsep_export),
        "selection_rule": (
            "minimum maximum interior log-fugacity residual; external energy residual "
            "is the tie-breaker"
        ),
        "candidates": candidates,
        "ranking": [item["identity"] for item in ranked],
        "selected_for_prescribed_pressure_gate": selected,
        "clapeyron_scope": (
            "VTPR is evaluated as a full bulk provider. Clapeyron UNIFAC/NRTL are "
            "rejected if the imposed-phase fugacity interface is unavailable; no fallback is used."
        ),
        "pass_gate": bool(selected is not None),
        "decision": (
            "run_prescribed_pressure_stationary_parity"
            if selected is not None
            else "stop_no_compatible_bulk_provider"
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    method = report["chemsep_method"]
    lines = [
        "# Core V3 water-methanol bulk-thermo qualification",
        "",
        f"- Selected for prescribed-pressure gate: `{report['selected_for_prescribed_pressure_gate']}`",
        f"- Decision: `{report['decision']}`",
        "- No fallback property route was allowed.",
        f"- ChemSep method: `{method['k_value_model']}` / `{method['activity_coefficient_model']}` / `{method['vapor_pressure_model']}` / `{method['enthalpy_model']}`",
        f"- ChemSep UNIFAC interaction record: `{method['unifac_main_group_bip_record']}`",
        "",
        "| Provider | Compatible | Max VLE log error | RMS VLE log error | Energy residual (BTU/h) | Top dT (F) | Bottom dT (F) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["candidates"]:
        if not item["core_bulk_interface_compatible"]:
            lines.append(
                f"| {item['identity']} | No | -- | -- | -- | -- | -- |"
            )
            continue
        bubbles = {row["terminal"]: row for row in item["terminal_bubbles"]}
        lines.append(
            f"| {item['identity']} | Yes | "
            f"{item['maximum_interior_abs_log_fugacity_residual']:.6f} | "
            f"{item['rms_interior_log_fugacity_residual']:.6f} | "
            f"{item['fixed_state_external_energy_rate_BTUph']:.3f} | "
            f"{bubbles['top']['temperature_difference_F']:+.6f} | "
            f"{bubbles['bottom']['temperature_difference_F']:+.6f} |"
        )
    lines.extend(("", "## Unavailable interfaces", ""))
    unavailable = [
        item for item in report["candidates"] if not item["core_bulk_interface_compatible"]
    ]
    if unavailable:
        for item in unavailable:
            lines.append(f"- `{item['identity']}`: {item['error']}")
    else:
        lines.append("- None.")
    lines.extend(
        (
            "",
            "## Meaning",
            "",
            "This is a fixed-state comparison, not a fitted model. The selected provider "
            "is simply the available Core-compatible provider that most closely reproduces "
            "the ChemSep interior equilibrium rows. Density-only VTPR remains a separate "
            "choice and does not alter this bulk-provider ranking.",
            "",
        )
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    args = parser.parse_args()
    report = build_report(args.workbook)
    json_path = _rooted(args.json)
    doc_path = _rooted(args.doc)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    doc_path.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "selected": report["selected_for_prescribed_pressure_gate"],
                "ranking": report["ranking"],
                "decision": report["decision"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
