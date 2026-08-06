"""Structural registry for the Core V3 provider-governed architecture.

This module declares equation ownership and thermodynamic-provider authority.
It deliberately contains no property calls, residual evaluation, root solve,
or dependency on a Core V2 residual implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping, Sequence

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank


ARCHITECTURE_NAME = (
    "Core V3 - Provider-Governed Energy-Owned Equilibrium Architecture"
)
ARCHITECTURE_VERSION = "core-v3-provider-governed-v1"

VOLUME_IDS = (
    "reflux_drum",
    "rectifying_tray",
    "feed_tray",
    "stripping_tray",
    "combined_reboiler_sump",
)
EQUILIBRIUM_VOLUME_IDS = VOLUME_IDS[1:]
HYDRAULIC_VOLUME_IDS = VOLUME_IDS[1:4]
TERMINAL_VOLUME_IDS = (VOLUME_IDS[0], VOLUME_IDS[-1])

LIQUID_LINKS = (
    ("reflux_drum", "rectifying_tray", "R"),
    ("rectifying_tray", "feed_tray", "L[rectifying_tray]"),
    ("feed_tray", "stripping_tray", "L[feed_tray]"),
    ("stripping_tray", "combined_reboiler_sump", "L[stripping_tray]"),
)
VAPOR_LINKS = (
    (
        "combined_reboiler_sump",
        "stripping_tray",
        "V[combined_reboiler_sump->stripping_tray]",
    ),
    (
        "stripping_tray",
        "feed_tray",
        "V[stripping_tray->feed_tray]",
    ),
    (
        "feed_tray",
        "rectifying_tray",
        "V[feed_tray->rectifying_tray]",
    ),
    (
        "rectifying_tray",
        "reflux_drum",
        "V[rectifying_tray->reflux_drum]",
    ),
)

NO_FALLBACK = "fail explicitly; do not substitute another provider interface"


@dataclass(frozen=True)
class Unknown:
    name: str
    block: str
    physical_owner: str


@dataclass(frozen=True)
class Residual:
    name: str
    block: str
    physical_owner: str
    dependencies: tuple[str, ...]
    property_quantities: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderAuthority:
    quantity: str
    provider_path: str
    role: str
    expected_basis: str
    permitted_residual_blocks: tuple[str, ...]
    fallback_policy: str


@dataclass(frozen=True)
class ProspectiveAcceptanceRule:
    name: str
    quantity: str
    comparison: str
    limit: float | bool
    role: str


@dataclass(frozen=True)
class BalanceContribution:
    family: str
    stream: str
    component: str | None
    coefficient: int


@dataclass(frozen=True)
class ProviderGovernedRegistry:
    architecture_name: str
    architecture_version: str
    provider_identity: str
    interface_provider_identities: tuple[tuple[str, str], ...]
    component_names: tuple[str, ...]
    unknowns: tuple[Unknown, ...]
    residuals: tuple[Residual, ...]
    external_parameters: tuple[str, ...]
    provider_authorities: tuple[ProviderAuthority, ...]
    acceptance_rules: tuple[ProspectiveAcceptanceRule, ...]
    contributions: tuple[BalanceContribution, ...]
    interface_fallback_permitted: bool
    historical_acceptance_imported: bool
    live_property_evaluation_attempted: bool
    nonlinear_solve_attempted: bool
    dynamic_integration_attempted: bool


@dataclass(frozen=True)
class RegistryAudit:
    unknown_count: int
    residual_count: int
    expected_count: int
    structural_rank: int
    structural_nullity: int
    zero_unknown_columns: tuple[str, ...]
    zero_residual_rows: tuple[str, ...]
    unregistered_dependencies: tuple[str, ...]
    unregistered_property_quantities: tuple[str, ...]
    imported_profile_dependencies: tuple[str, ...]
    governing_tp_flash_uses: tuple[str, ...]
    production_independent_pr_uses: tuple[str, ...]
    mixed_basis_dependencies: tuple[str, ...]
    unauthorized_property_uses: tuple[str, ...]
    duplicate_authority_quantities: tuple[str, ...]
    authority_fallbacks: tuple[str, ...]
    fixed_condenser_duty_parameter_present: bool
    condenser_duty_unknown_count: int
    vapor_unknown_count: int
    francis_liquid_unknown_count: int
    full_fugacity_row_count: int
    condenser_bubble_row_count: int
    component_conservation_passed: bool
    energy_conservation_passed: bool
    prospective_acceptance_contract_passed: bool
    historical_acceptance_imported: bool
    core_v2_residual_owner_imported: bool
    live_property_evaluation_attempted: bool
    nonlinear_solve_attempted: bool
    dynamic_integration_attempted: bool
    pass_gate: bool


def _validated_components(component_names: Sequence[str]) -> tuple[str, ...]:
    components = tuple(str(value).strip() for value in component_names)
    if len(components) < 2:
        raise ValueError("Core V3 requires at least two components")
    if any(not value for value in components):
        raise ValueError("component names must be nonempty")
    if len(set(components)) != len(components):
        raise ValueError("component names must be unique")
    return components


def _coordinates(
    components: tuple[str, ...],
    phase: str,
    volume: str,
) -> tuple[str, ...]:
    return tuple(
        f"{phase}[{volume},{component}]" for component in components[:-1]
    )


def _phase_state_dependencies(
    components: tuple[str, ...],
    phase: str,
    volume: str,
) -> tuple[str, ...]:
    coordinate = "x" if phase == "liquid" else "y"
    return (
        f"T[{volume}]",
        f"P[{volume}]",
        *_coordinates(components, coordinate, volume),
    )


def _validated_provider_identity(provider_identity: str) -> str:
    identity = str(provider_identity).strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", identity):
        raise ValueError("provider_identity must be a simple lowercase identifier")
    return identity


def _provider_authorities(
    provider_identity: str,
    interface_provider_identities: Mapping[str, str] | None = None,
) -> tuple[ProviderAuthority, ...]:
    identity = _validated_provider_identity(provider_identity)
    identities = {
        str(interface): _validated_provider_identity(value)
        for interface, value in dict(interface_provider_identities or {}).items()
    }

    def path(interface: str) -> str:
        return f"{identities.get(interface, identity)}.{interface}"

    return (
        ProviderAuthority(
            "stage_fugacity_equilibrium",
            path("direct_imposed_phase_fugacity"),
            "governing_equation",
            "declared liquid x and vapor y at stage T/P",
            ("full_phase_equilibrium",),
            NO_FALLBACK,
        ),
        ProviderAuthority(
            "condenser_bubble_equilibrium",
            path("direct_imposed_phase_fugacity"),
            "governing_equation",
            "drum liquid x and incipient vapor y at drum T/P",
            ("condenser_bubble_fugacity",),
            NO_FALLBACK,
        ),
        ProviderAuthority(
            "phase_enthalpy",
            path("declared_phase_enthalpy"),
            "governing_balance",
            "declared phase composition, T, and P",
            ("energy_balance",),
            NO_FALLBACK,
        ),
        ProviderAuthority(
            "liquid_density",
            path("declared_liquid_density"),
            "hydraulic_geometry",
            "declared liquid x at stage T/P",
            ("francis_hydraulics",),
            NO_FALLBACK,
        ),
        ProviderAuthority(
            "bubble_temperature_and_incipient_vapor",
            path("direct_imposed_phase_fugacity"),
            "governing_state",
            "fixed pressure and declared liquid x",
            ("condenser_bubble_fugacity",),
            NO_FALLBACK,
        ),
        ProviderAuthority(
            "stable_phase",
            path("tp_flash"),
            "diagnostic_gate",
            "overall composition z at declared T/P",
            (),
            NO_FALLBACK,
        ),
        ProviderAuthority(
            "vapor_fraction",
            path("tp_flash"),
            "diagnostic_gate",
            "overall composition z",
            (),
            NO_FALLBACK,
        ),
        ProviderAuthority(
            "flash_x_y_K",
            path("tp_flash"),
            "flash_basis_diagnostic",
            "K_flash = y_flash/x_flash",
            (),
            NO_FALLBACK,
        ),
        ProviderAuthority(
            "lever_rule_closure",
            path("tp_flash"),
            "diagnostic_gate",
            "z = (1-beta)*x_flash + beta*y_flash",
            (),
            NO_FALLBACK,
        ),
        ProviderAuthority(
            "independent_pr_bubble",
            "independent.parameter_aligned_peng_robinson",
            "validation_only",
            "same P, x, constants, omega, and kij",
            (),
            "validation failure stops authorization",
        ),
    )


def _acceptance_rules() -> tuple[ProspectiveAcceptanceRule, ...]:
    return (
        ProspectiveAcceptanceRule(
            "governing_stage_fugacity",
            "stage_fugacity_equilibrium",
            "max_abs_less_than",
            1.0e-10,
            "future_governing_acceptance",
        ),
        ProspectiveAcceptanceRule(
            "governing_condenser_fugacity",
            "condenser_bubble_equilibrium",
            "max_abs_less_than",
            1.0e-10,
            "future_governing_acceptance",
        ),
        ProspectiveAcceptanceRule(
            "independent_pr_bubble_temperature",
            "independent_pr_bubble",
            "temperature_abs_F_less_than",
            1.0e-3,
            "future_validation",
        ),
        ProspectiveAcceptanceRule(
            "independent_pr_incipient_vapor",
            "independent_pr_bubble",
            "composition_max_abs_less_than",
            1.0e-6,
            "future_validation",
        ),
        ProspectiveAcceptanceRule(
            "tp_flash_stable_vapor",
            "stable_phase",
            "equals",
            False,
            "future_diagnostic_gate",
        ),
        ProspectiveAcceptanceRule(
            "tp_flash_bubble_region",
            "vapor_fraction",
            "less_than_or_equal",
            1.0e-3,
            "future_diagnostic_gate",
        ),
        ProspectiveAcceptanceRule(
            "tp_flash_Kx_internal_closure",
            "flash_x_y_K",
            "max_abs_less_than",
            1.0e-12,
            "future_diagnostic_gate",
        ),
        ProspectiveAcceptanceRule(
            "tp_flash_lever_rule",
            "lever_rule_closure",
            "max_abs_less_than",
            1.0e-12,
            "future_diagnostic_gate",
        ),
    )


def build_provider_governed_registry(
    component_names: Sequence[str],
    *,
    provider_identity: str = "dwsim",
    interface_provider_identities: Mapping[str, str] | None = None,
) -> ProviderGovernedRegistry:
    """Build the provider-tagged five-volume steady structural ledger."""
    components = _validated_components(component_names)
    identity = _validated_provider_identity(provider_identity)
    interface_identities = tuple(
        sorted(
            (
                str(interface),
                _validated_provider_identity(value),
            )
            for interface, value in dict(
                interface_provider_identities or {}
            ).items()
        )
    )
    unknowns: list[Unknown] = []
    residuals: list[Residual] = []
    contributions: list[BalanceContribution] = []

    for volume in VOLUME_IDS:
        unknowns.append(Unknown(f"NL[{volume}]", "liquid_amount", volume))
        unknowns.extend(
            Unknown(name, "liquid_composition", volume)
            for name in _coordinates(components, "x", volume)
        )
        unknowns.append(Unknown(f"T[{volume}]", "temperature", volume))
    for volume in EQUILIBRIUM_VOLUME_IDS:
        unknowns.extend(
            Unknown(name, "vapor_composition", volume)
            for name in _coordinates(components, "y", volume)
        )
    for volume in HYDRAULIC_VOLUME_IDS:
        unknowns.append(
            Unknown(f"L[{volume}]", "francis_liquid_flow", "francis_hydraulics")
        )
    for _source, _destination, symbol in VAPOR_LINKS:
        unknowns.append(
            Unknown(symbol, "energy_owned_vapor_flow", "energy_balances")
        )
    unknowns.extend(
        (
            Unknown("D", "terminal_product_flow", "reflux_drum"),
            Unknown("B", "terminal_product_flow", "combined_reboiler_sump"),
        )
    )
    unknowns.extend(
        Unknown(
            name,
            "condenser_incipient_vapor",
            "total_condenser_reflux_drum_boundary",
        )
        for name in _coordinates(components, "y_bubble", "reflux_drum")
    )
    unknowns.append(
        Unknown(
            "Q_C",
            "solved_condenser_duty",
            "total_condenser_reflux_drum_boundary",
        )
    )

    for volume in EQUILIBRIUM_VOLUME_IDS:
        dependencies = (
            f"T[{volume}]",
            f"P[{volume}]",
            *_coordinates(components, "x", volume),
            *_coordinates(components, "y", volume),
        )
        residuals.extend(
            Residual(
                f"phase_fugacity[{volume},{component}]",
                "full_phase_equilibrium",
                volume,
                dependencies,
                ("stage_fugacity_equilibrium",),
            )
            for component in components
        )

    internal_links = tuple(
        (source, destination, symbol, "liquid")
        for source, destination, symbol in LIQUID_LINKS
    ) + tuple(
        (source, destination, symbol, "vapor")
        for source, destination, symbol in VAPOR_LINKS
    )
    for volume in VOLUME_IDS:
        for component in components:
            dependencies: list[str] = []
            for source, destination, symbol, phase in internal_links:
                if volume not in {source, destination}:
                    continue
                dependencies.append(symbol)
                coordinate = "x" if phase == "liquid" else "y"
                dependencies.extend(_coordinates(components, coordinate, source))
                contributions.append(
                    BalanceContribution(
                        "component",
                        symbol,
                        component,
                        -1 if volume == source else 1,
                    )
                )
            if volume == "feed_tray":
                dependencies.append(f"F_component[{component}]")
            if volume == "reflux_drum":
                dependencies.extend(
                    ("D", *_coordinates(components, "x", volume))
                )
            if volume == "combined_reboiler_sump":
                dependencies.extend(
                    ("B", *_coordinates(components, "x", volume))
                )
            residuals.append(
                Residual(
                    f"component_balance[{volume},{component}]",
                    "component_balance",
                    volume,
                    tuple(dict.fromkeys(dependencies)),
                )
            )

        energy_dependencies: list[str] = []
        for source, destination, symbol, phase in internal_links:
            if volume not in {source, destination}:
                continue
            energy_dependencies.append(symbol)
            energy_dependencies.extend(
                _phase_state_dependencies(components, phase, source)
            )
            contributions.append(
                BalanceContribution(
                    "energy",
                    symbol,
                    None,
                    -1 if volume == source else 1,
                )
            )
        if volume == "feed_tray":
            energy_dependencies.append("H_feed")
        if volume == "reflux_drum":
            energy_dependencies.extend(
                (
                    "D",
                    "Q_C",
                    *_phase_state_dependencies(components, "liquid", volume),
                )
            )
        if volume == "combined_reboiler_sump":
            energy_dependencies.extend(
                (
                    "B",
                    "Q_R",
                    *_phase_state_dependencies(components, "liquid", volume),
                )
            )
        residuals.append(
            Residual(
                f"energy_balance[{volume}]",
                "energy_balance",
                volume,
                tuple(dict.fromkeys(energy_dependencies)),
                ("phase_enthalpy",),
            )
        )

    for volume in HYDRAULIC_VOLUME_IDS:
        residuals.append(
            Residual(
                f"francis_hydraulics[{volume}]",
                "francis_hydraulics",
                volume,
                (
                    f"L[{volume}]",
                    f"NL[{volume}]",
                    f"T[{volume}]",
                    f"P[{volume}]",
                    *_coordinates(components, "x", volume),
                    f"francis_geometry[{volume}]",
                ),
                ("liquid_density",),
            )
        )
    for volume in TERMINAL_VOLUME_IDS:
        residuals.append(
            Residual(
                f"terminal_amount[{volume}]",
                "terminal_amount_specification",
                volume,
                (f"NL[{volume}]", f"NL_target[{volume}]"),
            )
        )

    bubble_dependencies = (
        "T[reflux_drum]",
        "P[reflux_drum]",
        *_coordinates(components, "x", "reflux_drum"),
        *_coordinates(components, "y_bubble", "reflux_drum"),
    )
    residuals.extend(
        Residual(
            f"condenser_bubble_fugacity[{component}]",
            "condenser_bubble_fugacity",
            "total_condenser_reflux_drum_boundary",
            bubble_dependencies,
            (
                "condenser_bubble_equilibrium",
                "bubble_temperature_and_incipient_vapor",
            ),
        )
        for component in components
    )

    external_parameters = (
        *(f"P[{volume}]" for volume in VOLUME_IDS),
        "R",
        *(f"F_component[{component}]" for component in components),
        "H_feed",
        "Q_R",
        *(f"francis_geometry[{volume}]" for volume in HYDRAULIC_VOLUME_IDS),
        *(f"NL_target[{volume}]" for volume in TERMINAL_VOLUME_IDS),
    )
    return ProviderGovernedRegistry(
        architecture_name=ARCHITECTURE_NAME,
        architecture_version=ARCHITECTURE_VERSION,
        provider_identity=identity,
        interface_provider_identities=interface_identities,
        component_names=components,
        unknowns=tuple(unknowns),
        residuals=tuple(residuals),
        external_parameters=tuple(external_parameters),
        provider_authorities=_provider_authorities(
            identity, dict(interface_identities)
        ),
        acceptance_rules=_acceptance_rules(),
        contributions=tuple(contributions),
        interface_fallback_permitted=False,
        historical_acceptance_imported=False,
        live_property_evaluation_attempted=False,
        nonlinear_solve_attempted=False,
        dynamic_integration_attempted=False,
    )


def _pattern(registry: ProviderGovernedRegistry) -> csr_matrix:
    unknown_index = {
        entry.name: index for index, entry in enumerate(registry.unknowns)
    }
    rows: list[int] = []
    columns: list[int] = []
    for row, residual in enumerate(registry.residuals):
        for dependency in residual.dependencies:
            if dependency in unknown_index:
                rows.append(row)
                columns.append(unknown_index[dependency])
    return csr_matrix(
        (
            np.ones(len(rows), dtype=np.int8),
            (rows, columns),
        ),
        shape=(len(registry.residuals), len(registry.unknowns)),
    )


def _conservation_passes(
    contributions: Iterable[BalanceContribution],
    *,
    family: str,
    streams: Iterable[str],
    components: Iterable[str | None],
) -> bool:
    records = tuple(contributions)
    for stream in streams:
        for component in components:
            coefficients = tuple(
                record.coefficient
                for record in records
                if record.family == family
                and record.stream == stream
                and record.component == component
            )
            if len(coefficients) != 2 or sum(coefficients) != 0:
                return False
    return True


def _contains_prohibited_mixed_basis(text: str) -> bool:
    normalized = (
        text.lower()
        .replace(" ", "")
        .replace("-", "_")
        .replace("overall_composition", "z")
    )
    return (
        "k_flash*z" in normalized
        or "normalize(k_flash*z)" in normalized
        or "kflash*z" in normalized
        or "flash_k_overall_z" in normalized
    )


def _acceptance_contract_passes(
    registry: ProviderGovernedRegistry,
    authorities: dict[str, ProviderAuthority],
) -> bool:
    expected_rules = {
        ("stage_fugacity_equilibrium", "max_abs_less_than", 1.0e-10),
        ("condenser_bubble_equilibrium", "max_abs_less_than", 1.0e-10),
        (
            "independent_pr_bubble",
            "temperature_abs_F_less_than",
            1.0e-3,
        ),
        (
            "independent_pr_bubble",
            "composition_max_abs_less_than",
            1.0e-6,
        ),
        ("stable_phase", "equals", False),
        ("vapor_fraction", "less_than_or_equal", 1.0e-3),
        ("flash_x_y_K", "max_abs_less_than", 1.0e-12),
        ("lever_rule_closure", "max_abs_less_than", 1.0e-12),
    }
    actual = {
        (rule.quantity, rule.comparison, rule.limit)
        for rule in registry.acceptance_rules
    }
    no_cross_interface_equality = all(
        "direct" not in rule.name.lower() or "flash" not in rule.name.lower()
        for rule in registry.acceptance_rules
    )
    return bool(
        expected_rules <= actual
        and no_cross_interface_equality
        and authorities["independent_pr_bubble"].role == "validation_only"
        and authorities["flash_x_y_K"].expected_basis
        == "K_flash = y_flash/x_flash"
    )


def audit_provider_governed_registry(
    registry: ProviderGovernedRegistry,
) -> RegistryAudit:
    """Audit the frozen DD-091 structural and provider-ownership contract."""
    pattern = _pattern(registry)
    unknown_names = tuple(entry.name for entry in registry.unknowns)
    residual_names = tuple(entry.name for entry in registry.residuals)
    row_nonzero = np.asarray(pattern.getnnz(axis=1)).reshape((-1,))
    column_nonzero = np.asarray(pattern.getnnz(axis=0)).reshape((-1,))
    rank = int(structural_rank(pattern))
    expected = 10 * len(registry.component_names) + 10

    known_dependencies = set(unknown_names) | set(registry.external_parameters)
    dependencies = tuple(
        dependency
        for residual in registry.residuals
        for dependency in residual.dependencies
    )
    unregistered_dependencies = tuple(
        sorted(set(dependencies) - known_dependencies)
    )
    imported_profiles = tuple(
        sorted(
            {
                dependency
                for dependency in dependencies
                if "profile" in dependency.lower()
                or "chemsep" in dependency.lower()
                or "previous_step" in dependency.lower()
            }
        )
    )

    authority_names = tuple(
        authority.quantity for authority in registry.provider_authorities
    )
    duplicate_authorities = tuple(
        sorted(
            {
                name
                for name in authority_names
                if authority_names.count(name) > 1
            }
        )
    )
    authority_by_name = {
        authority.quantity: authority
        for authority in registry.provider_authorities
    }
    property_uses = tuple(
        (residual, quantity)
        for residual in registry.residuals
        for quantity in residual.property_quantities
    )
    unregistered_properties = tuple(
        sorted(
            {
                quantity
                for _residual, quantity in property_uses
                if quantity not in authority_by_name
            }
        )
    )
    unauthorized_uses = tuple(
        sorted(
            f"{residual.name}:{quantity}"
            for residual, quantity in property_uses
            if quantity in authority_by_name
            and residual.block
            not in authority_by_name[quantity].permitted_residual_blocks
        )
    )
    governing_tp_flash = tuple(
        sorted(
            f"{residual.name}:{quantity}"
            for residual, quantity in property_uses
            if quantity in authority_by_name
            and "tp_flash" in authority_by_name[quantity].provider_path
        )
    )
    production_independent_pr = tuple(
        sorted(
            f"{residual.name}:{quantity}"
            for residual, quantity in property_uses
            if quantity in authority_by_name
            and authority_by_name[quantity].provider_path.startswith(
                "independent."
            )
        )
    )
    mixed_basis = tuple(
        sorted(
            {
                token
                for token in (
                    *dependencies,
                    *(
                        quantity
                        for residual in registry.residuals
                        for quantity in residual.property_quantities
                    ),
                    *(rule.name for rule in registry.acceptance_rules),
                )
                if _contains_prohibited_mixed_basis(token)
            }
        )
    )
    authority_fallbacks = tuple(
        authority.quantity
        for authority in registry.provider_authorities
        if not authority.fallback_policy.strip()
        or (
            authority.role != "validation_only"
            and authority.fallback_policy != NO_FALLBACK
        )
    )

    internal_symbols = tuple(
        symbol for _, _, symbol in (*LIQUID_LINKS, *VAPOR_LINKS)
    )
    component_conservation = _conservation_passes(
        registry.contributions,
        family="component",
        streams=internal_symbols,
        components=registry.component_names,
    )
    energy_conservation = _conservation_passes(
        registry.contributions,
        family="energy",
        streams=internal_symbols,
        components=(None,),
    )

    full_fugacity_count = sum(
        residual.block == "full_phase_equilibrium"
        for residual in registry.residuals
    )
    bubble_count = sum(
        residual.block == "condenser_bubble_fugacity"
        for residual in registry.residuals
    )
    vapor_count = sum(
        unknown.block == "energy_owned_vapor_flow"
        and unknown.physical_owner == "energy_balances"
        for unknown in registry.unknowns
    )
    liquid_count = sum(
        unknown.block == "francis_liquid_flow"
        and unknown.physical_owner == "francis_hydraulics"
        for unknown in registry.unknowns
    )
    q_c_count = sum(
        unknown.name == "Q_C"
        and unknown.block == "solved_condenser_duty"
        for unknown in registry.unknowns
    )
    core_v2_imported = any(
        "core_v2" in value.lower()
        for value in (
            registry.architecture_name,
            registry.architecture_version,
            *(residual.physical_owner for residual in registry.residuals),
        )
    )
    acceptance_passed = (
        not unregistered_properties
        and not duplicate_authorities
        and _acceptance_contract_passes(registry, authority_by_name)
    )

    pass_gate = bool(
        len(unknown_names) == len(residual_names) == expected
        and rank == expected
        and not np.any(row_nonzero == 0)
        and not np.any(column_nonzero == 0)
        and not unregistered_dependencies
        and not imported_profiles
        and not unregistered_properties
        and not unauthorized_uses
        and not governing_tp_flash
        and not production_independent_pr
        and not mixed_basis
        and not duplicate_authorities
        and not authority_fallbacks
        and "Q_C" not in registry.external_parameters
        and q_c_count == 1
        and vapor_count == len(VAPOR_LINKS)
        and liquid_count == len(HYDRAULIC_VOLUME_IDS)
        and full_fugacity_count
        == len(EQUILIBRIUM_VOLUME_IDS) * len(registry.component_names)
        and bubble_count == len(registry.component_names)
        and component_conservation
        and energy_conservation
        and acceptance_passed
        and not registry.interface_fallback_permitted
        and not registry.historical_acceptance_imported
        and not core_v2_imported
        and not registry.live_property_evaluation_attempted
        and not registry.nonlinear_solve_attempted
        and not registry.dynamic_integration_attempted
    )
    return RegistryAudit(
        unknown_count=len(unknown_names),
        residual_count=len(residual_names),
        expected_count=expected,
        structural_rank=rank,
        structural_nullity=max(len(unknown_names) - rank, 0),
        zero_unknown_columns=tuple(
            unknown_names[index]
            for index in np.flatnonzero(column_nonzero == 0)
        ),
        zero_residual_rows=tuple(
            residual_names[index] for index in np.flatnonzero(row_nonzero == 0)
        ),
        unregistered_dependencies=unregistered_dependencies,
        unregistered_property_quantities=unregistered_properties,
        imported_profile_dependencies=imported_profiles,
        governing_tp_flash_uses=governing_tp_flash,
        production_independent_pr_uses=production_independent_pr,
        mixed_basis_dependencies=mixed_basis,
        unauthorized_property_uses=unauthorized_uses,
        duplicate_authority_quantities=duplicate_authorities,
        authority_fallbacks=authority_fallbacks,
        fixed_condenser_duty_parameter_present=bool(
            "Q_C" in registry.external_parameters
        ),
        condenser_duty_unknown_count=q_c_count,
        vapor_unknown_count=vapor_count,
        francis_liquid_unknown_count=liquid_count,
        full_fugacity_row_count=full_fugacity_count,
        condenser_bubble_row_count=bubble_count,
        component_conservation_passed=component_conservation,
        energy_conservation_passed=energy_conservation,
        prospective_acceptance_contract_passed=acceptance_passed,
        historical_acceptance_imported=registry.historical_acceptance_imported,
        core_v2_residual_owner_imported=core_v2_imported,
        live_property_evaluation_attempted=(
            registry.live_property_evaluation_attempted
        ),
        nonlinear_solve_attempted=registry.nonlinear_solve_attempted,
        dynamic_integration_attempted=registry.dynamic_integration_attempted,
        pass_gate=pass_gate,
    )


__all__ = [
    "ARCHITECTURE_NAME",
    "ARCHITECTURE_VERSION",
    "EQUILIBRIUM_VOLUME_IDS",
    "HYDRAULIC_VOLUME_IDS",
    "LIQUID_LINKS",
    "NO_FALLBACK",
    "TERMINAL_VOLUME_IDS",
    "VAPOR_LINKS",
    "VOLUME_IDS",
    "BalanceContribution",
    "ProviderAuthority",
    "ProviderGovernedRegistry",
    "ProspectiveAcceptanceRule",
    "RegistryAudit",
    "Residual",
    "Unknown",
    "audit_provider_governed_registry",
    "build_provider_governed_registry",
]
