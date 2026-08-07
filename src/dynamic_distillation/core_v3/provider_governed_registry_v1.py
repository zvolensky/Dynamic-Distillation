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

@dataclass(frozen=True)
class ColumnTopology:
    volume_ids: tuple[str, ...]
    equilibrium_volume_ids: tuple[str, ...]
    hydraulic_volume_ids: tuple[str, ...]
    terminal_volume_ids: tuple[str, str]
    liquid_links: tuple[tuple[str, str, str], ...]
    vapor_links: tuple[tuple[str, str, str], ...]
    top_volume: str
    feed_volume: str
    bottom_volume: str


def _section_volume_ids(section: str, count: int) -> tuple[str, ...]:
    if count < 1:
        raise ValueError(f"{section} section requires at least one volume")
    if count == 1:
        return (f"{section}_tray",)
    return tuple(f"{section}_volume_{index}" for index in range(1, count + 1))


def build_column_topology(
    *,
    rectifying_volume_count: int = 1,
    stripping_volume_count: int = 1,
) -> ColumnTopology:
    """Build a generic terminal/interior/feed column topology."""
    top = "reflux_drum"
    feed = "feed_tray"
    bottom = "combined_reboiler_sump"
    rectifying = _section_volume_ids("rectifying", rectifying_volume_count)
    stripping = _section_volume_ids("stripping", stripping_volume_count)
    volumes = (top, *rectifying, feed, *stripping, bottom)
    liquid_links = tuple(
        (
            source,
            destination,
            "R" if source == top else f"L[{source}]",
        )
        for source, destination in zip(volumes[:-1], volumes[1:], strict=True)
    )
    vapor_links = tuple(
        (
            source,
            destination,
            f"V[{source}->{destination}]",
        )
        for source, destination in zip(
            reversed(volumes[1:]), reversed(volumes[:-1]), strict=True
        )
    )
    return ColumnTopology(
        volume_ids=volumes,
        equilibrium_volume_ids=volumes[1:],
        hydraulic_volume_ids=volumes[1:-1],
        terminal_volume_ids=(top, bottom),
        liquid_links=liquid_links,
        vapor_links=vapor_links,
        top_volume=top,
        feed_volume=feed,
        bottom_volume=bottom,
    )


def _validated_topology(topology: ColumnTopology) -> ColumnTopology:
    volumes = topology.volume_ids
    if len(volumes) < 5 or len(set(volumes)) != len(volumes):
        raise ValueError("column topology requires at least five unique volumes")
    if (
        topology.top_volume != volumes[0]
        or topology.bottom_volume != volumes[-1]
        or topology.feed_volume not in volumes[1:-1]
        or topology.equilibrium_volume_ids != volumes[1:]
        or topology.hydraulic_volume_ids != volumes[1:-1]
        or topology.terminal_volume_ids != (volumes[0], volumes[-1])
    ):
        raise ValueError("column topology volume ownership is inconsistent")
    expected_liquid_pairs = tuple(zip(volumes[:-1], volumes[1:], strict=True))
    expected_vapor_pairs = tuple(
        zip(reversed(volumes[1:]), reversed(volumes[:-1]), strict=True)
    )
    if tuple(link[:2] for link in topology.liquid_links) != expected_liquid_pairs:
        raise ValueError("liquid links must connect every adjacent volume downward")
    if tuple(link[:2] for link in topology.vapor_links) != expected_vapor_pairs:
        raise ValueError("vapor links must connect every adjacent volume upward")
    symbols = tuple(
        symbol for _, _, symbol in (*topology.liquid_links, *topology.vapor_links)
    )
    if len(symbols) != len(set(symbols)):
        raise ValueError("internal flow symbols must be unique")
    return topology


DEFAULT_TOPOLOGY = build_column_topology()
VOLUME_IDS = DEFAULT_TOPOLOGY.volume_ids
EQUILIBRIUM_VOLUME_IDS = DEFAULT_TOPOLOGY.equilibrium_volume_ids
HYDRAULIC_VOLUME_IDS = DEFAULT_TOPOLOGY.hydraulic_volume_ids
TERMINAL_VOLUME_IDS = DEFAULT_TOPOLOGY.terminal_volume_ids
LIQUID_LINKS = DEFAULT_TOPOLOGY.liquid_links
VAPOR_LINKS = DEFAULT_TOPOLOGY.vapor_links

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
    topology: ColumnTopology
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
    topology: ColumnTopology | None = None,
) -> ProviderGovernedRegistry:
    """Build a provider-tagged steady structural ledger."""
    components = _validated_components(component_names)
    topology = _validated_topology(
        DEFAULT_TOPOLOGY if topology is None else topology
    )
    volumes = topology.volume_ids
    equilibrium_volumes = topology.equilibrium_volume_ids
    hydraulic_volumes = topology.hydraulic_volume_ids
    terminal_volumes = topology.terminal_volume_ids
    liquid_links = topology.liquid_links
    vapor_links = topology.vapor_links
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

    for volume in volumes:
        unknowns.append(Unknown(f"NL[{volume}]", "liquid_amount", volume))
        unknowns.extend(
            Unknown(name, "liquid_composition", volume)
            for name in _coordinates(components, "x", volume)
        )
        unknowns.append(Unknown(f"T[{volume}]", "temperature", volume))
    for volume in equilibrium_volumes:
        unknowns.extend(
            Unknown(name, "vapor_composition", volume)
            for name in _coordinates(components, "y", volume)
        )
    for volume in hydraulic_volumes:
        unknowns.append(
            Unknown(f"L[{volume}]", "francis_liquid_flow", "francis_hydraulics")
        )
    for _source, _destination, symbol in vapor_links:
        unknowns.append(
            Unknown(symbol, "energy_owned_vapor_flow", "energy_balances")
        )
    unknowns.extend(
        (
            Unknown("D", "terminal_product_flow", topology.top_volume),
            Unknown("B", "terminal_product_flow", topology.bottom_volume),
        )
    )
    unknowns.extend(
        Unknown(
            name,
            "condenser_incipient_vapor",
            "total_condenser_reflux_drum_boundary",
        )
        for name in _coordinates(components, "y_bubble", topology.top_volume)
    )
    unknowns.append(
        Unknown(
            "Q_C",
            "solved_condenser_duty",
            "total_condenser_reflux_drum_boundary",
        )
    )

    for volume in equilibrium_volumes:
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
        for source, destination, symbol in liquid_links
    ) + tuple(
        (source, destination, symbol, "vapor")
        for source, destination, symbol in vapor_links
    )
    for volume in volumes:
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
            if volume == topology.feed_volume:
                dependencies.append(f"F_component[{component}]")
            if volume == topology.top_volume:
                dependencies.extend(
                    ("D", *_coordinates(components, "x", volume))
                )
            if volume == topology.bottom_volume:
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
        if volume == topology.feed_volume:
            energy_dependencies.append("H_feed")
        if volume == topology.top_volume:
            energy_dependencies.extend(
                (
                    "D",
                    "Q_C",
                    *_phase_state_dependencies(components, "liquid", volume),
                )
            )
        if volume == topology.bottom_volume:
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

    for volume in hydraulic_volumes:
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
    for volume in terminal_volumes:
        residuals.append(
            Residual(
                f"terminal_amount[{volume}]",
                "terminal_amount_specification",
                volume,
                (f"NL[{volume}]", f"NL_target[{volume}]"),
            )
        )

    bubble_dependencies = (
        f"T[{topology.top_volume}]",
        f"P[{topology.top_volume}]",
        *_coordinates(components, "x", topology.top_volume),
        *_coordinates(components, "y_bubble", topology.top_volume),
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
        *(f"P[{volume}]" for volume in volumes),
        "R",
        *(f"F_component[{component}]" for component in components),
        "H_feed",
        "Q_R",
        *(f"francis_geometry[{volume}]" for volume in hydraulic_volumes),
        *(f"NL_target[{volume}]" for volume in terminal_volumes),
    )
    return ProviderGovernedRegistry(
        architecture_name=ARCHITECTURE_NAME,
        architecture_version=ARCHITECTURE_VERSION,
        provider_identity=identity,
        interface_provider_identities=interface_identities,
        component_names=components,
        topology=topology,
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
    topology = registry.topology
    expected = 2 * len(topology.volume_ids) * (
        len(registry.component_names) + 1
    )

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
        symbol
        for _, _, symbol in (*topology.liquid_links, *topology.vapor_links)
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
        and vapor_count == len(topology.vapor_links)
        and liquid_count == len(topology.hydraulic_volume_ids)
        and full_fugacity_count
        == len(topology.equilibrium_volume_ids) * len(registry.component_names)
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
    "ColumnTopology",
    "DEFAULT_TOPOLOGY",
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
    "build_column_topology",
    "build_provider_governed_registry",
]
