#!/usr/bin/env python
"""Prepare or execute the standalone DD-089 DWSIM PR interface study."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.core_v2.dwsim_phase_interface_consistency_v1 import (
    IndependentPengRobinsonProvider,
    PengRobinsonParameters,
    evaluate_interface_state,
    solve_bubble_from_fugacity,
)
from dynamic_distillation.core_v2.one_volume_property_gate_v1 import (
    normalize_composition,
    vapor_from_logits,
    vapor_logits,
)
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


SCHEMA_ID = "dd089-dwsim-pr-phase-interface-consistency-contract-v1"
RESULT_SCHEMA_ID = "dd089-dwsim-pr-phase-interface-consistency-result-v1"
DD088_RESULT = ROOT / (
    "logs/dd088_condenser_saturated_liquid_steady_root_20260719.json"
)
DD088_CONTRACT = ROOT / (
    "logs/dd088_condenser_saturated_liquid_steady_root_contract_20260719.json"
)
TEMPERATURE_OFFSETS_F = (-0.1, -0.01, -0.001, 0.001, 0.01, 0.1)
PRESSURE_OFFSETS_PSIA = (-0.1, -0.01, 0.01, 0.1)
COMPOSITION_ALR_OFFSETS = (-1.0e-4, 1.0e-4)
FRESH_PROCESS_COUNT = 3


def _float_list(values: Any) -> list[float]:
    return [
        float(value)
        for value in np.asarray(values, dtype=float).reshape((-1,))
    ]


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _load_hashed_contract(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    claimed = str(payload.pop("contract_payload_sha256", ""))
    actual = _payload_hash(payload)
    payload["contract_payload_sha256"] = claimed
    if payload.get("schema_id") != SCHEMA_ID:
        raise RuntimeError("DD-089 contract schema does not match")
    if claimed != actual:
        raise RuntimeError("DD-089 contract payload checksum does not match")
    return payload


def _dd088_endpoint() -> dict[str, Any]:
    result = json.loads(DD088_RESULT.read_text(encoding="utf-8"))
    contract = json.loads(DD088_CONTRACT.read_text(encoding="utf-8"))
    start = result["starts"]["canonical_saturated_liquid_seed"]
    return {
        "temperature_F": float(start["temperature_F"][0]),
        "pressure_psia": float(contract["source_mapping"]["pressure_psia"][0]),
        "liquid_mole_fraction": _float_list(
            start["liquid_mole_fraction"][0]
        ),
        "bubble_vapor_mole_fraction": _float_list(
            start["bubble_vapor_mole_fraction"]
        ),
        "legacy_composition_metric": float(
            start["phase_diagnostic"]["bubble_y_minus_Kx_max_abs"]
        ),
    }


def _provider_from_contract(contract: Mapping[str, Any]) -> ThermoProviderV1:
    return ThermoProviderV1(
        component_names_excel=contract["component_names_excel"],
        component_ids_dwsim=contract["component_ids_dwsim"],
        property_package=contract["property_package"],
        silence_backend_console=True,
    )


def _extract_pr_parameters(
    provider: ThermoProviderV1,
    component_ids: list[str],
) -> dict[str, Any]:
    from dynamic_distillation import pr_flash_backend_v1 as backend

    provider.configure_backend()
    backend._init_dwsim()

    def constant(component_id: str, name: str) -> float:
        return float(backend._dtlc.GetCompoundConstProp(component_id, name))

    tc = [constant(component, "criticalTemperature") for component in component_ids]
    pc = [constant(component, "criticalPressure") for component in component_ids]
    omega = [constant(component, "acentricFactor") for component in component_ids]
    kij = np.zeros((len(component_ids), len(component_ids)), dtype=float)
    try:
        interactions = backend._prop_package.m_pr.InteractionParameters
        for i, left in enumerate(component_ids):
            for j, right in enumerate(component_ids):
                if i == j:
                    continue
                for first, second in ((left, right), (right, left)):
                    try:
                        kij[i, j] = float(
                            interactions[first][second].kij
                        )
                        break
                    except Exception:
                        continue
    except Exception:
        pass
    return {
        "critical_temperature_K": _float_list(tc),
        "critical_pressure_Pa": _float_list(pc),
        "acentric_factor": _float_list(omega),
        "binary_interaction": [
            _float_list(row) for row in np.asarray(kij, dtype=float)
        ],
        "source": (
            "DWSIM compound constants and PengRobinsonPropertyPackage "
            "interaction parameters; equations evaluated independently"
        ),
    }


def _sample_definitions(endpoint: Mapping[str, Any]) -> list[dict[str, Any]]:
    temperature = float(endpoint["temperature_F"])
    pressure = float(endpoint["pressure_psia"])
    x = normalize_composition(endpoint["liquid_mole_fraction"])
    y = normalize_composition(endpoint["bubble_vapor_mole_fraction"])
    samples: list[dict[str, Any]] = [
        {
            "name": "dd088_exact",
            "mode": "preserved",
            "temperature_F": temperature,
            "pressure_psia": pressure,
            "liquid_mole_fraction": _float_list(x),
            "vapor_guess": _float_list(y),
        },
        {
            "name": "same_state_bubble_resolve",
            "mode": "bubble_solve",
            "temperature_F": temperature,
            "pressure_psia": pressure,
            "liquid_mole_fraction": _float_list(x),
            "vapor_guess": _float_list(y),
        },
    ]
    for offset in TEMPERATURE_OFFSETS_F:
        tag = f"{offset:+.3g}".replace("+", "p").replace("-", "m").replace(".", "p")
        samples.append(
            {
                "name": f"fixed_temperature_{tag}_F",
                "mode": "preserved",
                "temperature_F": temperature + float(offset),
                "pressure_psia": pressure,
                "liquid_mole_fraction": _float_list(x),
                "vapor_guess": _float_list(y),
            }
        )
    for offset in PRESSURE_OFFSETS_PSIA:
        tag = f"{offset:+.3g}".replace("+", "p").replace("-", "m").replace(".", "p")
        samples.append(
            {
                "name": f"bubble_pressure_{tag}_psia",
                "mode": "bubble_solve",
                "temperature_F": temperature,
                "pressure_psia": pressure + float(offset),
                "liquid_mole_fraction": _float_list(x),
                "vapor_guess": _float_list(y),
            }
        )
    base_alr = vapor_logits(x)
    for coordinate in range(base_alr.size):
        for offset in COMPOSITION_ALR_OFFSETS:
            delta = np.zeros_like(base_alr)
            delta[coordinate] = float(offset)
            perturbed = vapor_from_logits(base_alr + delta)
            sign = "p" if offset > 0.0 else "m"
            samples.append(
                {
                    "name": (
                        f"bubble_composition_alr{coordinate}_{sign}1em4"
                    ),
                    "mode": "bubble_solve",
                    "temperature_F": temperature,
                    "pressure_psia": pressure,
                    "liquid_mole_fraction": _float_list(perturbed),
                    "vapor_guess": _float_list(y),
                }
            )
    return samples


def _orders(names: list[str]) -> list[list[str]]:
    interleaved = names[::2] + names[1::2]
    return [names, list(reversed(names)), interleaved]


def _contract_markdown(contract: Mapping[str, Any]) -> str:
    endpoint = contract["dd088_preserved_endpoint"]
    return "\n".join(
        (
            "# DD-089 DWSIM PR Interface-Consistency Contract",
            "",
            f"- Schema: `{contract['schema_id']}`",
            f"- Payload SHA-256: `{contract['contract_payload_sha256']}`",
            f"- Preparation base commit: `{contract['preparation_base_commit']}`",
            f"- DD-088 result SHA-256: `{contract['dd088_result_sha256']}`",
            f"- DD-088 contract SHA-256: `{contract['dd088_contract_sha256']}`",
            f"- Samples per fresh process: `{len(contract['samples'])}`",
            f"- Fresh processes: `{len(contract['execution_orders'])}`",
            "",
            "## Preserved State",
            "",
            f"- Temperature: `{endpoint['temperature_F']:.12g} F`",
            f"- Pressure: `{endpoint['pressure_psia']:.12g} psia`",
            f"- Liquid composition: `{endpoint['liquid_mole_fraction']}`",
            f"- Direct bubble vapor: `{endpoint['bubble_vapor_mole_fraction']}`",
            f"- Frozen DD-088 metric: "
            f"`{endpoint['legacy_composition_metric']:.6e}`",
            "",
            "## Scope",
            "",
            "The execution evaluates imposed-phase fugacity, raw TP-flash "
            "compositions/K-values, lever-rule closure, fresh-process "
            "repeatability, a predefined local T/P/composition neighborhood, "
            "and an independent Peng-Robinson fugacity implementation.",
            "",
            "No column residual, nonlinear column solve, checkpoint repair, "
            "tolerance revision, or dynamic integration is authorized.",
            "",
        )
    )


def prepare(contract_path: Path) -> dict[str, Any]:
    dd088_result = json.loads(DD088_RESULT.read_text(encoding="utf-8"))
    dd088_contract = json.loads(DD088_CONTRACT.read_text(encoding="utf-8"))
    endpoint = _dd088_endpoint()
    component_names = list(dd088_contract["component_names"])
    component_ids = ["Propane", "N-butane", "N-pentane"]
    provider = ThermoProviderV1(
        component_names_excel=component_names,
        component_ids_dwsim=component_ids,
        property_package=str(dd088_result["property_package"]),
        silence_backend_console=True,
    )
    pr_parameters = _extract_pr_parameters(provider, component_ids)
    samples = _sample_definitions(endpoint)
    names = [sample["name"] for sample in samples]
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "dd088_result_path": str(DD088_RESULT.relative_to(ROOT)),
        "dd088_result_sha256": _sha256_file(DD088_RESULT),
        "dd088_contract_path": str(DD088_CONTRACT.relative_to(ROOT)),
        "dd088_contract_sha256": _sha256_file(DD088_CONTRACT),
        "property_package": str(dd088_result["property_package"]),
        "component_names_excel": component_names,
        "component_ids_dwsim": component_ids,
        "dd088_preserved_endpoint": endpoint,
        "independent_pr_parameters": pr_parameters,
        "samples": samples,
        "execution_orders": _orders(names),
        "bubble_solver": {
            "method": "scipy.optimize.least_squares_trf",
            "ftol": 1.0e-12,
            "xtol": 1.0e-12,
            "gtol": 1.0e-12,
            "jacobian": "uncolored_central_difference",
            "jacobian_step": 1.0e-5,
            "max_nfev": 100,
            "temperature_bounds_F": [80.0, 260.0],
        },
        "analysis_rules": {
            "fresh_process_repeatability_reference": 1.0e-10,
            "algebraic_closure_reference": 1.0e-12,
            "legacy_metric_reproduction_reference": 1.0e-10,
            "lever_basis_dominant_fraction": 0.5,
            "rules_are_diagnostic_not_architecture_acceptance": True,
        },
        "column_residual_evaluated_during_preparation": False,
        "column_solve_attempted_during_preparation": False,
        "dynamic_integration_attempted_during_preparation": False,
    }
    payload["contract_payload_sha256"] = _payload_hash(payload)
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    contract_path.with_suffix(".md").write_text(
        _contract_markdown(payload),
        encoding="utf-8",
    )
    return payload


def _pr_provider(contract: Mapping[str, Any]) -> IndependentPengRobinsonProvider:
    raw = contract["independent_pr_parameters"]
    return IndependentPengRobinsonProvider(
        PengRobinsonParameters(
            critical_temperature_K=np.asarray(
                raw["critical_temperature_K"], dtype=float
            ),
            critical_pressure_Pa=np.asarray(
                raw["critical_pressure_Pa"], dtype=float
            ),
            acentric_factor=np.asarray(raw["acentric_factor"], dtype=float),
            binary_interaction=np.asarray(
                raw["binary_interaction"], dtype=float
            ),
        )
    )


def _bubble_payload(result: Any) -> dict[str, Any]:
    return {
        "temperature_F": float(result.temperature_F),
        "vapor_mole_fraction": _float_list(result.vapor_mole_fraction),
        "residual": _float_list(result.residual),
        "residual_inf_norm": float(result.residual_inf_norm),
        "success": bool(result.success),
        "status": int(result.status),
        "message": result.message,
        "nfev": int(result.nfev),
    }


def execute_worker(
    contract_path: Path,
    order_index: int,
    output_path: Path,
) -> dict[str, Any]:
    contract = _load_hashed_contract(contract_path)
    provider = _provider_from_contract(contract)
    independent = _pr_provider(contract)
    samples = {sample["name"]: sample for sample in contract["samples"]}
    order = contract["execution_orders"][int(order_index)]
    results: dict[str, Any] = {}
    started = time.perf_counter()
    for name in order:
        sample = samples[name]
        x = normalize_composition(sample["liquid_mole_fraction"])
        y_guess = normalize_composition(sample["vapor_guess"])
        pressure = float(sample["pressure_psia"])
        temperature = float(sample["temperature_F"])
        if sample["mode"] == "bubble_solve":
            dwsim_bubble = solve_bubble_from_fugacity(
                provider,
                pressure_psia=pressure,
                liquid_x=x,
                temperature_guess_F=temperature,
                vapor_guess=y_guess,
            )
            if not dwsim_bubble.success:
                raise RuntimeError(f"DWSIM bubble solve failed for {name}")
            temperature = float(dwsim_bubble.temperature_F)
            direct_y = dwsim_bubble.vapor_mole_fraction
        else:
            dwsim_bubble = None
            direct_y = y_guess
        snapshot = evaluate_interface_state(
            provider,
            temperature_F=temperature,
            pressure_psia=pressure,
            overall_z=x,
            direct_bubble_y=direct_y,
        )
        independent_bubble = solve_bubble_from_fugacity(
            independent,
            pressure_psia=pressure,
            liquid_x=x,
            temperature_guess_F=temperature,
            vapor_guess=direct_y,
        )
        results[name] = {
            "sample": sample,
            "dwsim_bubble_solve": (
                None if dwsim_bubble is None else _bubble_payload(dwsim_bubble)
            ),
            "interface": _jsonable(snapshot),
            "independent_pr_bubble": _bubble_payload(independent_bubble),
            "independent_pr_minus_dwsim": {
                "temperature_F": float(
                    independent_bubble.temperature_F - temperature
                ),
                "vapor_mole_fraction": _float_list(
                    independent_bubble.vapor_mole_fraction - direct_y
                ),
                "vapor_max_abs": float(
                    np.max(
                        np.abs(
                            independent_bubble.vapor_mole_fraction - direct_y
                        )
                    )
                ),
            },
        }
    report = {
        "worker_index": int(order_index),
        "process_id": int(__import__("os").getpid()),
        "order": order,
        "samples": results,
        "property_call_counters": provider.get_call_counters(),
        "wall_clock_sec": float(time.perf_counter() - started),
    }
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _numeric_vector(sample: Mapping[str, Any]) -> np.ndarray:
    interface = sample["interface"]
    metrics = interface["metrics"]
    independent = sample["independent_pr_bubble"]
    values = [
        float(interface["temperature_F"]),
        float(interface["pressure_psia"]),
        float(interface["rachford_rice_beta"]),
        *[float(value) for value in interface["flash_x"]],
        *[float(value) for value in interface["flash_y"]],
        *[float(value) for value in interface["flash_K"]],
        *[float(value) for value in metrics.values()],
        float(independent["temperature_F"]),
        *[float(value) for value in independent["vapor_mole_fraction"]],
        float(independent["residual_inf_norm"]),
    ]
    bubble = sample["dwsim_bubble_solve"]
    if bubble is not None:
        values.extend(
            [
                float(bubble["temperature_F"]),
                *[float(value) for value in bubble["vapor_mole_fraction"]],
                float(bubble["residual_inf_norm"]),
            ]
        )
    return np.asarray(values, dtype=float)


def _repeatability(workers: list[Mapping[str, Any]]) -> dict[str, Any]:
    names = workers[0]["samples"].keys()
    by_sample: dict[str, float] = {}
    for name in names:
        vectors = np.asarray(
            [_numeric_vector(worker["samples"][name]) for worker in workers],
            dtype=float,
        )
        by_sample[name] = float(np.max(np.ptp(vectors, axis=0)))
    return {
        "by_sample_max_abs": by_sample,
        "overall_max_abs": float(max(by_sample.values())),
    }


def _verify_contract_is_committed(path: Path) -> str:
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    _git("ls-files", "--error-unmatch", relative)
    committed = _git("show", f"HEAD:{relative}")
    current = path.read_text(encoding="utf-8")
    if committed.replace("\r\n", "\n") != current.replace("\r\n", "\n"):
        raise RuntimeError("DD-089 contract differs from committed HEAD")
    relevant = (
        "src/dynamic_distillation/core_v2/"
        "dwsim_phase_interface_consistency_v1.py",
        "tools/audit_core_v2_dwsim_phase_interface_consistency.py",
        "tests/test_core_v2_dwsim_phase_interface_consistency_v1.py",
        "docs/dd_089_dwsim_pr_interface_consistency_contract_20260719.md",
        relative,
        Path(relative).with_suffix(".md").as_posix(),
    )
    if _git("status", "--short", "--", *relevant):
        raise RuntimeError("DD-089 contract implementation has tracked changes")
    return _git("rev-parse", "HEAD")


def _result_markdown(report: Mapping[str, Any]) -> str:
    base = report["base_state_analysis"]
    lines = [
        "# DD-089 DWSIM PR Interface-Consistency Result",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Contract commit: `{report['contract_commit']}`",
        f"- Wall clock: `{report['wall_clock_sec']:.3f} s`",
        f"- Fresh-process maximum spread: "
        f"`{report['repeatability']['overall_max_abs']:.6e}`",
        "",
        "## Preserved DD-088 State",
        "",
        f"- Legacy `y_direct` vs `normalize(K*z)`: "
        f"`{base['legacy_direct_y_minus_Kz_max_abs']:.6e}`",
        f"- Direct bubble `y` vs TP-flash `y`: "
        f"`{base['direct_y_minus_flash_y_max_abs']:.6e}`",
        f"- TP-flash `y` vs `normalize(K*x_flash)`: "
        f"`{base['flash_y_minus_Kx_flash_max_abs']:.6e}`",
        f"- Composition-basis contribution: "
        f"`{base['Kx_flash_minus_Kz_max_abs']:.6e}`",
        f"- Flash `x` vs overall `z`: "
        f"`{base['flash_x_minus_overall_z_max_abs']:.6e}`",
        f"- Rachford-Rice beta: `{base['rachford_rice_beta']:.6e}`",
        f"- Lever-rule closure: "
        f"`{base['lever_rule_closure_max_abs']:.6e}`",
        "",
        "## Independent PR",
        "",
        f"- Bubble temperature difference: "
        f"`{report['independent_pr_base_comparison']['temperature_F']:.6e} F`",
        f"- Vapor-composition maximum difference: "
        f"`{report['independent_pr_base_comparison']['vapor_max_abs']:.6e}`",
        "",
        "## Authorization",
        "",
        report["authorization"],
        "",
    ]
    return "\n".join(lines)


def execute(contract_path: Path, out_prefix: Path) -> dict[str, Any]:
    contract_commit = _verify_contract_is_committed(contract_path)
    contract = _load_hashed_contract(contract_path)
    if _sha256_file(DD088_RESULT) != contract["dd088_result_sha256"]:
        raise RuntimeError("DD-088 result changed after DD-089 preparation")
    if _sha256_file(DD088_CONTRACT) != contract["dd088_contract_sha256"]:
        raise RuntimeError("DD-088 contract changed after DD-089 preparation")
    started = time.perf_counter()
    workers: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="dd089_") as temp:
        temp_path = Path(temp)
        for index in range(len(contract["execution_orders"])):
            worker_out = temp_path / f"worker_{index}.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker-index",
                    str(index),
                    "--contract",
                    str(contract_path.resolve()),
                    "--worker-out",
                    str(worker_out),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    f"DD-089 worker {index} failed: {completed.stderr}"
                )
            workers.append(
                json.loads(worker_out.read_text(encoding="utf-8"))
            )
    repeatability = _repeatability(workers)
    base_sample = workers[0]["samples"]["dd088_exact"]
    base_interface = base_sample["interface"]
    base_metrics = dict(base_interface["metrics"])
    base_metrics["rachford_rice_beta"] = float(
        base_interface["rachford_rice_beta"]
    )
    legacy = float(base_metrics["legacy_direct_y_minus_Kz_max_abs"])
    basis = float(base_metrics["Kx_flash_minus_Kz_max_abs"])
    basis_fraction = float(basis / legacy) if legacy > 0.0 else 0.0
    rules = contract["analysis_rules"]
    repeatable = bool(
        repeatability["overall_max_abs"]
        <= float(rules["fresh_process_repeatability_reference"])
    )
    reproduced = bool(
        abs(
            legacy
            - float(
                contract["dd088_preserved_endpoint"][
                    "legacy_composition_metric"
                ]
            )
        )
        <= float(rules["legacy_metric_reproduction_reference"])
    )
    algebraic = bool(
        float(base_metrics["decomposition_closure_max_abs"])
        <= float(rules["algebraic_closure_reference"])
        and float(base_metrics["flash_y_minus_Kx_flash_max_abs"])
        <= float(rules["algebraic_closure_reference"])
    )
    basis_dominant = bool(
        basis_fraction >= float(rules["lever_basis_dominant_fraction"])
    )
    if repeatable and reproduced and algebraic and basis_dominant:
        classification = (
            "repeatable_overall_vs_flash_liquid_composition_basis_effect"
        )
    elif repeatable and reproduced and algebraic:
        classification = "repeatable_cross_api_offset_not_basis_dominant"
    else:
        classification = "mixed_or_nonrepeatable_provider_behavior"
    report: dict[str, Any] = {
        "schema_id": RESULT_SCHEMA_ID,
        "classification": classification,
        "authorization": (
            "DD-089 is a provider study only. DD-088 remains formally failed "
            "and retired. These findings may inform a prospective property "
            "contract for a materially new architecture; they do not authorize "
            "rerunning DD-088 or integrating dynamics."
        ),
        "contract_commit": contract_commit,
        "contract_payload_sha256": contract["contract_payload_sha256"],
        "dd088_result_sha256": contract["dd088_result_sha256"],
        "dd088_contract_sha256": contract["dd088_contract_sha256"],
        "workers": workers,
        "repeatability": repeatability,
        "base_state_analysis": base_metrics,
        "composition_basis_fraction_of_legacy_metric": basis_fraction,
        "legacy_metric_reproduced": reproduced,
        "algebraic_identity_pass": algebraic,
        "composition_basis_dominant": basis_dominant,
        "independent_pr_base_comparison": base_sample[
            "independent_pr_minus_dwsim"
        ],
        "column_residual_evaluated": False,
        "column_solve_attempted": False,
        "dynamic_integration_attempted": False,
        "wall_clock_sec": float(time.perf_counter() - started),
    }
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    out_prefix.with_suffix(".md").write_text(
        _result_markdown(report),
        encoding="utf-8",
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--worker-index", type=int)
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path(
            "logs/dd089_dwsim_pr_interface_consistency_contract_20260719.json"
        ),
    )
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path("logs/dd089_dwsim_pr_interface_consistency_20260719"),
    )
    parser.add_argument("--worker-out", type=Path)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare_only:
        output = prepare(args.contract)
        summary = {
            "schema_id": output["schema_id"],
            "contract_payload_sha256": output["contract_payload_sha256"],
            "sample_count": len(output["samples"]),
            "fresh_process_count": len(output["execution_orders"]),
        }
    elif args.execute:
        output = execute(args.contract, args.out_prefix)
        summary = {
            "classification": output["classification"],
            "wall_clock_sec": output["wall_clock_sec"],
        }
    else:
        if args.worker_out is None:
            raise SystemExit("--worker-out is required with --worker-index")
        output = execute_worker(
            args.contract,
            args.worker_index,
            args.worker_out,
        )
        summary = {
            "worker_index": output["worker_index"],
            "wall_clock_sec": output["wall_clock_sec"],
        }
    print(json.dumps(summary, indent=2))
