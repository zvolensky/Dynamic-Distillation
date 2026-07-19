"""Provider-call provenance and runtime ownership enforcement for Core V3."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

import numpy as np


GOVERNING_EVALUATION_KINDS = frozenset({"residual", "jacobian"})


@dataclass(frozen=True)
class ProviderCallRecord:
    quantity: str
    provider_interface: str
    caller: str
    state_id: str
    evaluation_kind: str


class ProviderCallAudit:
    """Record and enforce provider ownership without fallback."""

    def __init__(self) -> None:
        self._records: list[ProviderCallRecord] = []
        self.fallback_attempted = False

    @property
    def records(self) -> tuple[ProviderCallRecord, ...]:
        return tuple(self._records)

    def _record(
        self,
        *,
        quantity: str,
        provider_interface: str,
        caller: str,
        state_id: str,
        evaluation_kind: str,
    ) -> None:
        self._records.append(
            ProviderCallRecord(
                quantity=str(quantity),
                provider_interface=str(provider_interface),
                caller=str(caller),
                state_id=str(state_id),
                evaluation_kind=str(evaluation_kind),
            )
        )

    def direct_phase_fugacity(
        self,
        provider: Any,
        *,
        phase: str,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
        quantity: str,
        caller: str,
        state_id: str,
        evaluation_kind: str,
    ) -> np.ndarray:
        if quantity not in {
            "stage_fugacity_equilibrium",
            "condenser_bubble_equilibrium",
            "bubble_temperature_and_incipient_vapor",
        }:
            raise RuntimeError(f"unauthorized direct-fugacity quantity {quantity!r}")
        self._record(
            quantity=quantity,
            provider_interface="dwsim.direct_imposed_phase_fugacity",
            caller=caller,
            state_id=state_id,
            evaluation_kind=evaluation_kind,
        )
        values = provider.phase_fugacity_coefficients(
            str(phase),
            float(temperature_F),
            float(pressure_psia),
            list(composition),
        )
        result = np.asarray(values, dtype=float).reshape((-1,))
        if np.any(~np.isfinite(result)) or np.any(result <= 0.0):
            raise RuntimeError("DWSIM direct fugacity returned non-physical values")
        return result

    def phase_enthalpy(
        self,
        provider: Any,
        *,
        phase: str,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
        caller: str,
        state_id: str,
        evaluation_kind: str,
    ) -> float:
        self._record(
            quantity="phase_enthalpy",
            provider_interface="dwsim.declared_phase_enthalpy",
            caller=caller,
            state_id=state_id,
            evaluation_kind=evaluation_kind,
        )
        result = float(
            provider.phase_enthalpy_BTU_lbmol(
                str(phase),
                float(temperature_F),
                float(pressure_psia),
                list(composition),
            )
        )
        if not np.isfinite(result):
            raise RuntimeError("DWSIM phase enthalpy is non-finite")
        return result

    def liquid_density(
        self,
        provider: Any,
        *,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
        caller: str,
        state_id: str,
        evaluation_kind: str,
    ) -> float:
        self._record(
            quantity="liquid_density",
            provider_interface="dwsim.declared_liquid_density",
            caller=caller,
            state_id=state_id,
            evaluation_kind=evaluation_kind,
        )
        result = provider.liquid_density_lbmol_ft3(
            float(temperature_F),
            float(pressure_psia),
            list(composition),
        )
        if result is None or not np.isfinite(float(result)) or float(result) <= 0.0:
            raise RuntimeError("DWSIM liquid density is unavailable or non-physical")
        return float(result)

    def tp_flash(
        self,
        provider: Any,
        *,
        temperature_F: float,
        pressure_psia: float,
        overall_composition: Sequence[float],
        caller: str,
        state_id: str,
        evaluation_kind: str,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if evaluation_kind != "diagnostic":
            raise RuntimeError(
                "TP flash is diagnostic-only and cannot run during "
                f"{evaluation_kind!r}"
            )
        self._record(
            quantity="flash_x_y_K",
            provider_interface="dwsim.tp_flash",
            caller=caller,
            state_id=state_id,
            evaluation_kind=evaluation_kind,
        )
        raw = provider.flash_TP_full_F_psia(
            float(temperature_F),
            float(pressure_psia),
            list(overall_composition),
        )
        if not isinstance(raw, (tuple, list)) or len(raw) not in {5, 6}:
            raise RuntimeError("DWSIM TP flash returned an unexpected payload")
        x = np.asarray(raw[0], dtype=float).reshape((-1,))
        y = np.asarray(raw[1], dtype=float).reshape((-1,))
        K = np.asarray(raw[2], dtype=float).reshape((-1,))
        if (
            x.shape != y.shape
            or x.shape != K.shape
            or np.any(~np.isfinite(x))
            or np.any(~np.isfinite(y))
            or np.any(~np.isfinite(K))
            or np.any(K <= 0.0)
        ):
            raise RuntimeError("DWSIM TP flash returned invalid phase data")
        return x, y, K

    def independent_phase_fugacity(
        self,
        provider: Any,
        *,
        phase: str,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
        caller: str,
        state_id: str,
        evaluation_kind: str,
    ) -> np.ndarray:
        if evaluation_kind != "validation":
            raise RuntimeError(
                "independent PR is validation-only and cannot run during "
                f"{evaluation_kind!r}"
            )
        self._record(
            quantity="independent_pr_bubble",
            provider_interface="independent.parameter_aligned_peng_robinson",
            caller=caller,
            state_id=state_id,
            evaluation_kind=evaluation_kind,
        )
        result = np.asarray(
            provider.phase_fugacity_coefficients(
                str(phase),
                float(temperature_F),
                float(pressure_psia),
                list(composition),
            ),
            dtype=float,
        ).reshape((-1,))
        if np.any(~np.isfinite(result)) or np.any(result <= 0.0):
            raise RuntimeError("independent PR returned non-physical fugacities")
        return result

    def grouped_records(self) -> list[dict[str, Any]]:
        counts: dict[tuple[str, str, str, str, str], int] = {}
        for record in self._records:
            key = (
                record.quantity,
                record.provider_interface,
                record.caller,
                record.state_id,
                record.evaluation_kind,
            )
            counts[key] = counts.get(key, 0) + 1
        return [
            {
                **asdict(
                    ProviderCallRecord(
                        quantity=key[0],
                        provider_interface=key[1],
                        caller=key[2],
                        state_id=key[3],
                        evaluation_kind=key[4],
                    )
                ),
                "count": count,
            }
            for key, count in sorted(counts.items())
        ]

    def violations(self) -> tuple[str, ...]:
        violations: list[str] = []
        for index, record in enumerate(self._records):
            prefix = f"call[{index}] {record.caller}"
            if (
                record.provider_interface == "dwsim.tp_flash"
                and record.evaluation_kind != "diagnostic"
            ):
                violations.append(f"{prefix}: TP flash outside diagnostics")
            if (
                record.provider_interface.startswith("independent.")
                and record.evaluation_kind != "validation"
            ):
                violations.append(f"{prefix}: independent PR outside validation")
            if record.evaluation_kind in GOVERNING_EVALUATION_KINDS:
                permitted = {
                    "dwsim.direct_imposed_phase_fugacity",
                    "dwsim.declared_phase_enthalpy",
                    "dwsim.declared_liquid_density",
                }
                if record.provider_interface not in permitted:
                    violations.append(
                        f"{prefix}: unauthorized governing provider "
                        f"{record.provider_interface}"
                    )
        if self.fallback_attempted:
            violations.append("provider fallback was attempted")
        return tuple(violations)

    def report(self) -> dict[str, Any]:
        violations = self.violations()
        return {
            "total_calls": len(self._records),
            "grouped_records": self.grouped_records(),
            "violations": list(violations),
            "fallback_attempted": bool(self.fallback_attempted),
            "pass": not violations,
        }


__all__ = [
    "GOVERNING_EVALUATION_KINDS",
    "ProviderCallAudit",
    "ProviderCallRecord",
]
