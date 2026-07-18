"""DD-073 transformed, square, staged continuation for the direct system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank

from dynamic_distillation.direct_steady_state_registry_v1 import (
    DirectSteadyStateRegistry,
    audit_registry_structure,
    structural_pattern,
)
from dynamic_distillation.direct_steady_state_residual_v1 import (
    DirectResidualEvaluation,
    DirectSteadyStateProblem,
    evaluate_direct_steady_state_residual,
)


_STAGE_BLOCKS = (
    (
        "local_closure",
        frozenset(
            {
                "local_thermo",
                "phase_amount",
                "liquid_composition",
                "vapor_composition",
            }
        ),
        frozenset(
            {
                "local_component_closure",
                "local_energy_closure",
                "local_volume_closure",
                "local_equilibrium",
            }
        ),
    ),
    (
        "conserved_balances",
        frozenset({"conserved_component", "conserved_energy"}),
        frozenset({"steady_component_balance", "steady_energy_balance"}),
    ),
    (
        "liquid_hydraulics",
        frozenset({"liquid_flow"}),
        frozenset({"liquid_hydraulics"}),
    ),
    (
        "vapor_pressure_drop",
        frozenset({"vapor_flow"}),
        frozenset({"vapor_pressure_drop"}),
    ),
    (
        "operating_specifications",
        frozenset({"manipulated_variable"}),
        frozenset({"operating_specification"}),
    ),
)

_MERGED_STAGE_BLOCKS = (
    (
        "merged_local_conserved",
        frozenset(
            {
                "local_thermo",
                "phase_amount",
                "liquid_composition",
                "vapor_composition",
                "conserved_component",
                "conserved_energy",
            }
        ),
        frozenset(
            {
                "local_component_closure",
                "local_energy_closure",
                "local_volume_closure",
                "local_equilibrium",
                "steady_component_balance",
                "steady_energy_balance",
            }
        ),
    ),
    (
        "liquid_hydraulics",
        frozenset({"liquid_flow"}),
        frozenset({"liquid_hydraulics"}),
    ),
    (
        "vapor_pressure_drop",
        frozenset({"vapor_flow"}),
        frozenset({"vapor_pressure_drop"}),
    ),
    (
        "operating_specifications",
        frozenset({"manipulated_variable"}),
        frozenset({"operating_specification"}),
    ),
)

DD074_STATE_SCHEMA = "dd074-merged-continuation-v1"


@dataclass(frozen=True)
class ContinuationStage:
    number: int
    name: str
    unknown_indices: tuple[int, ...]
    residual_indices: tuple[int, ...]
    new_unknown_indices: tuple[int, ...]
    new_residual_indices: tuple[int, ...]
    anchor_unknown_by_residual: tuple[tuple[int, int], ...]
    anchor_sign_by_residual: tuple[tuple[int, float], ...]

    @property
    def size(self) -> int:
        return len(self.unknown_indices)


@dataclass(frozen=True)
class StageHomotopyEvaluation:
    vector: np.ndarray
    physical_vector: np.ndarray
    physical: DirectResidualEvaluation
    homotopy_inf_norm: float
    physical_scaled_inf_norm: float


@dataclass(frozen=True)
class ContinuationPoint:
    stage: int
    stage_name: str
    lambda_value: float
    delta_lambda: float
    accepted: bool
    solver_success: bool
    nfev: int
    njev: int
    homotopy_inf_norm: float
    physical_scaled_inf_norm: float
    rank: int
    condition_estimate: float
    component_conservation_pass: bool
    energy_conservation_pass: bool
    safeguards_used: tuple[str, ...]
    coordinate_saturation: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ContinuationStageResult:
    stage: ContinuationStage
    accepted: bool
    final_lambda: float
    physical_vector: np.ndarray
    solver_coordinates: np.ndarray
    points: tuple[ContinuationPoint, ...]
    uncolored_endpoint_max_difference: float | None
    reason: str


@dataclass(frozen=True)
class DirectContinuationResult:
    accepted: bool
    classification: str
    final_stage: int
    final_vector: np.ndarray
    stages: tuple[ContinuationStageResult, ...]
    final_evaluation: DirectResidualEvaluation
    final_block_maxima: tuple[tuple[str, float], ...]
    final_gate_failures: tuple[str, ...]
    physical_final_matches_direct_evaluator: bool
    reason: str


@dataclass(frozen=True)
class ContinuationStageStructure:
    number: int
    name: str
    unknown_count: int
    residual_count: int
    physical_structural_rank: int
    physical_structural_nullity: int
    empty_residuals: tuple[str, ...]
    unused_unknowns: tuple[str, ...]
    unmatched_residuals: tuple[str, ...]
    unmatched_unknowns: tuple[str, ...]
    variable_identity_anchors: bool
    pass_gate: bool


@dataclass(frozen=True)
class MergedContinuationStructureAudit:
    expected_sizes: tuple[int, ...]
    actual_sizes: tuple[int, ...]
    stages: tuple[ContinuationStageStructure, ...]
    conserved_dependency_paths_pass: bool
    failed_conserved_dependency_paths: tuple[str, ...]
    pass_gate: bool
    decision: str


def build_continuation_stages(problem: DirectSteadyStateProblem) -> tuple[ContinuationStage, ...]:
    """Build the five nested square systems without residual reweighting tricks."""
    registry = problem.registry
    active_unknown_blocks: set[str] = set()
    active_residual_blocks: set[str] = set()
    stages: list[ContinuationStage] = []
    for stage_number, (name, new_unknown_blocks, new_residual_blocks) in enumerate(
        _STAGE_BLOCKS, start=1
    ):
        active_unknown_blocks.update(new_unknown_blocks)
        active_residual_blocks.update(new_residual_blocks)
        unknown_indices = tuple(
            index
            for index, entry in enumerate(registry.unknowns)
            if entry.block in active_unknown_blocks
        )
        residual_indices = tuple(
            index
            for index, entry in enumerate(registry.residuals)
            if entry.block in active_residual_blocks
        )
        new_unknown_indices = tuple(
            index
            for index, entry in enumerate(registry.unknowns)
            if entry.block in new_unknown_blocks
        )
        new_residual_indices = tuple(
            index
            for index, entry in enumerate(registry.residuals)
            if entry.block in new_residual_blocks
        )
        if len(unknown_indices) != len(residual_indices):
            raise ValueError(
                f"DD-073 stage {stage_number} is not square: "
                f"{len(unknown_indices)} unknowns, {len(residual_indices)} residuals"
            )
        if len(new_unknown_indices) != len(new_residual_indices):
            raise ValueError(f"DD-073 stage {stage_number} release is not square")

        anchors: dict[int, int] = {}
        if stage_number == 1:
            unknown_by_name = {
                entry.name: index for index, entry in enumerate(registry.unknowns)
            }
            residual_by_name = {
                entry.name: index for index, entry in enumerate(registry.residuals)
            }
            nodes = (
                "reflux_drum",
                *(f"tray_{stage}" for stage in registry.active_stage_ids),
                "partial_reboiler",
            )
            components = registry.component_names
            independent = components[:-1]
            for node in nodes:
                anchors[residual_by_name[f"energy_closure[{node}]"]] = (
                    unknown_by_name[f"T[{node}]"]
                )
                anchors[residual_by_name[f"volume_closure[{node}]"]] = (
                    unknown_by_name[f"P[{node}]"]
                )
                anchors[
                    residual_by_name[f"component_closure[{node},{components[0]}]"]
                ] = unknown_by_name[f"NL[{node}]"]
                anchors[
                    residual_by_name[f"component_closure[{node},{components[1]}]"]
                ] = unknown_by_name[f"NV[{node}]"]
                for component_index in range(2, len(components)):
                    liquid_component = independent[component_index - 2]
                    anchors[
                        residual_by_name[
                            f"component_closure[{node},{components[component_index]}]"
                        ]
                    ] = unknown_by_name[f"x[{node},{liquid_component}]"]
                for component in independent:
                    anchors[
                        residual_by_name[f"equilibrium[{node},{component}]"]
                    ] = unknown_by_name[f"y[{node},{component}]"]
                anchors[
                    residual_by_name[f"equilibrium[{node},{components[-1]}]"]
                ] = unknown_by_name[f"x[{node},{independent[-1]}]"]
        elif stage_number == 2:
            unknown_by_name = {
                entry.name: index for index, entry in enumerate(registry.unknowns)
            }
            for residual_index in new_residual_indices:
                residual_name = registry.residuals[residual_index].name
                if residual_name.startswith("component_balance["):
                    unknown_name = residual_name.replace(
                        "component_balance[", "N[", 1
                    )
                else:
                    unknown_name = residual_name.replace("energy_balance[", "U[", 1)
                anchors[residual_index] = unknown_by_name[unknown_name]
        else:
            closure_to_unknown = {
                entry.closure_residual: index
                for index, entry in enumerate(registry.unknowns)
                if index in new_unknown_indices and entry.closure_residual is not None
            }
            for residual_index in new_residual_indices:
                residual = registry.residuals[residual_index]
                if stage_number == 3:
                    unknown_name = f"L_out[{residual.owner}]"
                    unknown_index = next(
                        index
                        for index in new_unknown_indices
                        if registry.unknowns[index].name == unknown_name
                    )
                elif stage_number == 4:
                    unknown_name = f"V_out[{residual.owner}]"
                    unknown_index = next(
                        index
                        for index in new_unknown_indices
                        if registry.unknowns[index].name == unknown_name
                    )
                else:
                    unknown_index = closure_to_unknown[residual.name]
                anchors[residual_index] = unknown_index

        stages.append(
            ContinuationStage(
                number=stage_number,
                name=name,
                unknown_indices=unknown_indices,
                residual_indices=residual_indices,
                new_unknown_indices=new_unknown_indices,
                new_residual_indices=new_residual_indices,
                anchor_unknown_by_residual=tuple(sorted(anchors.items())),
                anchor_sign_by_residual=tuple(
                    (
                        residual_index,
                        (
                            -1.0
                            if (
                                (
                                    stage_number == 1
                                    and (
                                        registry.residuals[residual_index].block
                                        in {
                                            "local_energy_closure",
                                            "local_volume_closure",
                                        }
                                        or (
                                            registry.residuals[residual_index].block
                                            == "local_component_closure"
                                            and not registry.unknowns[
                                                anchors[residual_index]
                                            ].name.startswith("x[")
                                        )
                                    )
                                )
                                or stage_number == 4
                            )
                            else 1.0
                        ),
                    )
                    for residual_index in sorted(anchors)
                ),
            )
        )
    return tuple(stages)


def build_merged_continuation_stages(
    problem: DirectSteadyStateProblem,
) -> tuple[ContinuationStage, ...]:
    """Build the DD-074 four-stage proposal with variable-order identity anchors."""
    registry = problem.registry
    active_unknown_blocks: set[str] = set()
    active_residual_blocks: set[str] = set()
    stages: list[ContinuationStage] = []
    for stage_number, (name, new_unknown_blocks, new_residual_blocks) in enumerate(
        _MERGED_STAGE_BLOCKS, start=1
    ):
        active_unknown_blocks.update(new_unknown_blocks)
        active_residual_blocks.update(new_residual_blocks)
        unknown_indices = tuple(
            index
            for index, entry in enumerate(registry.unknowns)
            if entry.block in active_unknown_blocks
        )
        residual_indices = tuple(
            index
            for index, entry in enumerate(registry.residuals)
            if entry.block in active_residual_blocks
        )
        new_unknown_indices = tuple(
            index
            for index, entry in enumerate(registry.unknowns)
            if entry.block in new_unknown_blocks
        )
        new_residual_indices = tuple(
            index
            for index, entry in enumerate(registry.residuals)
            if entry.block in new_residual_blocks
        )
        if len(unknown_indices) != len(residual_indices):
            raise ValueError(
                f"DD-074 stage {stage_number} is not square: "
                f"{len(unknown_indices)} unknowns, {len(residual_indices)} residuals"
            )
        if len(new_unknown_indices) != len(new_residual_indices):
            raise ValueError(f"DD-074 stage {stage_number} release is not square")
        anchors = tuple(zip(new_residual_indices, new_unknown_indices))
        stages.append(
            ContinuationStage(
                number=stage_number,
                name=name,
                unknown_indices=unknown_indices,
                residual_indices=residual_indices,
                new_unknown_indices=new_unknown_indices,
                new_residual_indices=new_residual_indices,
                anchor_unknown_by_residual=anchors,
                anchor_sign_by_residual=tuple(
                    (residual_index, 1.0)
                    for residual_index in new_residual_indices
                ),
            )
        )
    return tuple(stages)


def _has_dependency_path(
    problem: DirectSteadyStateProblem,
    *,
    unknown_name: str,
    residual_name: str,
    allowed_unknowns: set[str],
    allowed_residuals: set[str],
) -> bool:
    registry = problem.registry
    adjacency: dict[str, set[str]] = {}
    for residual in registry.residuals:
        if residual.name not in allowed_residuals:
            continue
        residual_key = f"r:{residual.name}"
        for dependency in residual.dependencies:
            if dependency not in allowed_unknowns:
                continue
            unknown_key = f"u:{dependency}"
            adjacency.setdefault(residual_key, set()).add(unknown_key)
            adjacency.setdefault(unknown_key, set()).add(residual_key)
    start = f"u:{unknown_name}"
    target = f"r:{residual_name}"
    pending = [start]
    visited = {start}
    while pending:
        current = pending.pop()
        if current == target:
            return True
        for neighbor in adjacency.get(current, ()):
            if neighbor not in visited:
                visited.add(neighbor)
                pending.append(neighbor)
    return False


def audit_merged_continuation_structure(
    problem: DirectSteadyStateProblem,
) -> MergedContinuationStructureAudit:
    """Apply the structural-only DD-074 authorization gate."""
    registry = problem.registry
    stages = build_merged_continuation_stages(problem)
    full_pattern = structural_pattern(registry)
    stage_results: list[ContinuationStageStructure] = []
    for stage in stages:
        physical = full_pattern[list(stage.residual_indices), :][
            :, list(stage.unknown_indices)
        ].tocsr()
        row_counts = np.asarray(physical.getnnz(axis=1), dtype=int)
        column_counts = np.asarray(physical.getnnz(axis=0), dtype=int)
        rank = int(structural_rank(physical))
        subregistry = DirectSteadyStateRegistry(
            component_names=registry.component_names,
            active_stage_ids=registry.active_stage_ids,
            unknowns=tuple(registry.unknowns[index] for index in stage.unknown_indices),
            residuals=tuple(
                registry.residuals[index] for index in stage.residual_indices
            ),
            deliberate_eliminations=registry.deliberate_eliminations,
        )
        matching = audit_registry_structure(subregistry)
        identity_anchors = bool(
            len(stage.anchor_unknown_by_residual)
            == len(stage.new_unknown_indices)
            and all(sign == 1.0 for _, sign in stage.anchor_sign_by_residual)
            and tuple(
                residual for residual, _ in stage.anchor_unknown_by_residual
            )
            == stage.new_residual_indices
            and tuple(
                unknown for _, unknown in stage.anchor_unknown_by_residual
            )
            == stage.new_unknown_indices
        )
        empty_rows = tuple(
            registry.residuals[stage.residual_indices[index]].name
            for index in np.flatnonzero(row_counts == 0)
        )
        unused_columns = tuple(
            registry.unknowns[stage.unknown_indices[index]].name
            for index in np.flatnonzero(column_counts == 0)
        )
        passed = bool(
            stage.size == len(stage.residual_indices)
            and rank == stage.size
            and not empty_rows
            and not unused_columns
            and identity_anchors
        )
        stage_results.append(
            ContinuationStageStructure(
                number=stage.number,
                name=stage.name,
                unknown_count=stage.size,
                residual_count=len(stage.residual_indices),
                physical_structural_rank=rank,
                physical_structural_nullity=stage.size - rank,
                empty_residuals=empty_rows,
                unused_unknowns=unused_columns,
                unmatched_residuals=matching.unmatched_residuals,
                unmatched_unknowns=matching.unmatched_unknowns,
                variable_identity_anchors=identity_anchors,
                pass_gate=passed,
            )
        )

    first = stages[0]
    allowed_unknowns = {
        registry.unknowns[index].name for index in first.unknown_indices
    }
    allowed_residuals = {
        registry.residuals[index].name for index in first.residual_indices
    }
    failed_paths: list[str] = []
    for unknown in registry.unknowns:
        if unknown.name not in allowed_unknowns:
            continue
        if unknown.block == "conserved_component":
            suffix = unknown.name[len("N[") :]
            target = f"component_balance[{suffix}"
        elif unknown.block == "conserved_energy":
            suffix = unknown.name[len("U[") :]
            target = f"energy_balance[{suffix}"
        else:
            continue
        if not _has_dependency_path(
            problem,
            unknown_name=unknown.name,
            residual_name=target,
            allowed_unknowns=allowed_unknowns,
            allowed_residuals=allowed_residuals,
        ):
            failed_paths.append(f"{unknown.name} -> {target}")

    expected = (240, 258, 277, 281)
    actual = tuple(stage.size for stage in stages)
    passed = bool(
        actual == expected
        and all(stage.pass_gate for stage in stage_results)
        and not failed_paths
    )
    decision = (
        "DD-074 structural gates pass; one bounded merged-stage live attempt is authorized."
        if passed
        else (
            "DD-074 structural gates fail. Do not run the merged-stage live solve; "
            "retire manual staged continuation under the predefined hard stop."
        )
    )
    return MergedContinuationStructureAudit(
        expected_sizes=expected,
        actual_sizes=actual,
        stages=tuple(stage_results),
        conserved_dependency_paths_pass=not failed_paths,
        failed_conserved_dependency_paths=tuple(failed_paths),
        pass_gate=passed,
        decision=decision,
    )


def validate_continuation_state_schema(
    archive: object,
    *,
    expected_schema: str = DD074_STATE_SCHEMA,
) -> None:
    """Reject restart artifacts that do not explicitly declare the DD-074 schema."""
    try:
        schema_value = archive["schema_id"]  # type: ignore[index]
    except Exception as exc:
        raise ValueError("continuation state archive has no schema_id") from exc
    schema = str(np.asarray(schema_value).item())
    if schema != expected_schema:
        raise ValueError(
            f"continuation state schema {schema!r} does not match {expected_schema!r}"
        )


class SmoothPhysicalCoordinates:
    """Map unconstrained solver coordinates to valid physical variables."""

    def __init__(
        self,
        problem: DirectSteadyStateProblem,
        anchor_vector: Sequence[float],
        variable_scales: Sequence[float],
    ):
        self.problem = problem
        self.anchor = np.asarray(anchor_vector, dtype=float).copy()
        self.scales = np.asarray(variable_scales, dtype=float).copy()
        self.registry = problem.registry
        self._composition_groups: dict[tuple[str, str], tuple[int, ...]] = {}
        for index, entry in enumerate(self.registry.unknowns):
            if entry.name.startswith(("x[", "y[")):
                phase = entry.name[0]
                node = entry.name.split("[", 1)[1].split(",", 1)[0]
                self._composition_groups.setdefault((phase, node), tuple())
                self._composition_groups[(phase, node)] += (index,)
        self._composition_index = {
            index: group
            for group in self._composition_groups.values()
            for index in group
        }
        self._validate_physical(self.anchor)

    def _kind(self, index: int) -> str:
        name = self.registry.unknowns[index].name
        if index in self._composition_index:
            return "composition"
        if name.startswith(("T[", "U[")):
            return "affine"
        return "positive"

    def _validate_physical(self, vector: np.ndarray) -> None:
        if not np.all(np.isfinite(vector)):
            raise ValueError("coordinate anchor must be finite")
        for index in range(len(vector)):
            if self._kind(index) == "positive" and vector[index] <= 0.0:
                raise ValueError(
                    f"positive coordinate anchor is invalid: "
                    f"{self.registry.unknowns[index].name}"
                )
        for group in self._composition_groups.values():
            independent = vector[list(group)]
            final = 1.0 - float(np.sum(independent))
            if np.any(independent <= 0.0) or final <= 0.0:
                raise ValueError("composition coordinate anchor is outside the simplex")

    def encode(self, physical_vector: Sequence[float], indices: Sequence[int]) -> np.ndarray:
        physical = np.asarray(physical_vector, dtype=float)
        self._validate_physical(physical)
        full = np.zeros(len(self.registry.unknowns), dtype=float)
        handled_groups: set[tuple[int, ...]] = set()
        for index in indices:
            kind = self._kind(index)
            if kind == "composition":
                group = self._composition_index[index]
                if group in handled_groups:
                    continue
                base = self.anchor[list(group)]
                value = physical[list(group)]
                base_last = 1.0 - float(np.sum(base))
                value_last = 1.0 - float(np.sum(value))
                full[list(group)] = np.log(value / value_last) - np.log(
                    base / base_last
                )
                handled_groups.add(group)
            elif kind == "positive":
                full[index] = np.log(physical[index] / self.anchor[index])
            else:
                full[index] = (
                    physical[index] - self.anchor[index]
                ) / self.scales[index]
        return full[list(indices)]

    def decode(self, coordinates: Sequence[float], indices: Sequence[int]) -> np.ndarray:
        coords = np.asarray(coordinates, dtype=float).reshape((len(indices),))
        full_coords = np.zeros(len(self.registry.unknowns), dtype=float)
        full_coords[list(indices)] = coords
        result = self.anchor.copy()
        active = set(int(index) for index in indices)
        handled_groups: set[tuple[int, ...]] = set()
        for index in indices:
            index = int(index)
            kind = self._kind(index)
            if kind == "composition":
                group = self._composition_index[index]
                if group in handled_groups:
                    continue
                if not set(group).issubset(active):
                    raise ValueError("a composition group must be released as one block")
                base = self.anchor[list(group)]
                group_coordinates = full_coords[list(group)]
                if np.all(group_coordinates == 0.0):
                    result[list(group)] = base
                    handled_groups.add(group)
                    continue
                base_last = 1.0 - float(np.sum(base))
                logits = np.concatenate(
                    (
                        np.log(base / base_last) + group_coordinates,
                        np.asarray([0.0]),
                    )
                )
                shifted = logits - float(np.max(logits))
                composition = np.exp(shifted)
                composition /= float(np.sum(composition))
                result[list(group)] = composition[:-1]
                handled_groups.add(group)
            elif kind == "positive":
                result[index] = self.anchor[index] * np.exp(full_coords[index])
            else:
                result[index] = (
                    self.anchor[index] + self.scales[index] * full_coords[index]
                )
        self._validate_physical(result)
        return result

    def bounds(self, indices: Sequence[int]) -> tuple[np.ndarray, np.ndarray]:
        lower = np.empty(len(indices), dtype=float)
        upper = np.empty(len(indices), dtype=float)
        for local, index in enumerate(indices):
            kind = self._kind(int(index))
            limit = 30.0 if kind == "composition" else 20.0
            lower[local] = -limit
            upper[local] = limit
        return lower, upper

    def saturated(
        self, coordinates: Sequence[float], indices: Sequence[int], margin: float = 0.05
    ) -> tuple[str, ...]:
        lower, upper = self.bounds(indices)
        values = np.asarray(coordinates, dtype=float)
        return tuple(
            self.registry.unknowns[int(indices[local])].name
            for local in range(len(indices))
            if values[local] - lower[local] <= margin
            or upper[local] - values[local] <= margin
        )


def stage_structural_pattern(
    problem: DirectSteadyStateProblem, stage: ContinuationStage
) -> csr_matrix:
    full = structural_pattern(problem.registry).astype(bool)
    pattern = full[list(stage.residual_indices), :][:, list(stage.unknown_indices)].tolil()
    residual_local = {
        global_index: local for local, global_index in enumerate(stage.residual_indices)
    }
    unknown_local = {
        global_index: local for local, global_index in enumerate(stage.unknown_indices)
    }
    for residual_index, unknown_index in stage.anchor_unknown_by_residual:
        pattern[residual_local[residual_index], unknown_local[unknown_index]] = True

    # An ALR coordinate changes every independent fraction in its phase group.
    names = [entry.name for entry in problem.registry.unknowns]
    groups: dict[tuple[str, str], list[int]] = {}
    for global_index in stage.unknown_indices:
        name = names[global_index]
        if name.startswith(("x[", "y[")):
            groups.setdefault(
                (name[0], name.split("[", 1)[1].split(",", 1)[0]), []
            ).append(unknown_local[global_index])
    pattern = pattern.tocsr()
    for group in groups.values():
        rows = set()
        for column in group:
            rows.update(
                int(row)
                for row in pattern.tocsc().indices[
                    pattern.tocsc().indptr[column] : pattern.tocsc().indptr[column + 1]
                ]
            )
        mutable = pattern.tolil()
        for row in rows:
            for column in group:
                mutable[row, column] = True
        pattern = mutable.tocsr()
    return pattern.astype(np.int8)


def evaluate_stage_homotopy(
    problem: DirectSteadyStateProblem,
    stage: ContinuationStage,
    coordinate_system: SmoothPhysicalCoordinates,
    solver_coordinates: Sequence[float],
    lambda_value: float,
    residual_scales: Sequence[float],
) -> StageHomotopyEvaluation:
    physical_vector = coordinate_system.decode(
        solver_coordinates, stage.unknown_indices
    )
    physical = evaluate_direct_steady_state_residual(problem, physical_vector)
    scales = np.asarray(residual_scales, dtype=float)
    result = physical.raw[list(stage.residual_indices)] / scales[
        list(stage.residual_indices)
    ]
    anchor_map = dict(stage.anchor_unknown_by_residual)
    anchor_sign = dict(stage.anchor_sign_by_residual)
    residual_local = {
        global_index: local for local, global_index in enumerate(stage.residual_indices)
    }
    unknown_local = {
        global_index: local for local, global_index in enumerate(stage.unknown_indices)
    }
    coordinate_array = np.asarray(solver_coordinates, dtype=float)
    for residual_index in stage.new_residual_indices:
        unknown_index = anchor_map[residual_index]
        # The transformed coordinate is the smooth, normalized version of
        # (z-z_previous)/scale. Using it directly gives the lambda=0 system an
        # exact permutation-identity Jacobian, including ALR compositions.
        anchor_term = (
            anchor_sign[residual_index]
            * coordinate_array[unknown_local[unknown_index]]
        )
        local = residual_local[residual_index]
        result[local] = (
            (1.0 - float(lambda_value)) * anchor_term
            + float(lambda_value) * result[local]
        )
    return StageHomotopyEvaluation(
        vector=np.asarray(result, dtype=float),
        physical_vector=physical_vector,
        physical=physical,
        homotopy_inf_norm=float(np.max(np.abs(result))),
        physical_scaled_inf_norm=float(
            np.max(
                np.abs(
                    physical.raw[list(stage.residual_indices)]
                    / scales[list(stage.residual_indices)]
                )
            )
        ),
    )


def _column_colors(pattern: csr_matrix) -> tuple[tuple[int, ...], ...]:
    matrix = pattern.tocsc()
    row_sets = [
        set(
            int(row)
            for row in matrix.indices[matrix.indptr[column] : matrix.indptr[column + 1]]
        )
        for column in range(matrix.shape[1])
    ]
    colors: list[list[int]] = []
    occupied: list[set[int]] = []
    for column, rows in sorted(
        enumerate(row_sets), key=lambda item: (-len(item[1]), item[0])
    ):
        for color_index, used in enumerate(occupied):
            if rows.isdisjoint(used):
                colors[color_index].append(column)
                used.update(rows)
                break
        else:
            colors.append([column])
            occupied.append(set(rows))
    return tuple(tuple(sorted(color)) for color in colors)


def finite_difference_stage_jacobian(
    residual_function: Callable[[np.ndarray], np.ndarray],
    solver_coordinates: Sequence[float],
    pattern: csr_matrix,
    *,
    mode: str = "colored",
    step: float = 2.0e-6,
) -> csr_matrix:
    coordinates = np.asarray(solver_coordinates, dtype=float)
    matrix_pattern = pattern.astype(bool).tocsc()
    colors = (
        tuple((column,) for column in range(matrix_pattern.shape[1]))
        if mode == "uncolored"
        else _column_colors(matrix_pattern)
    )
    jacobian = np.zeros(matrix_pattern.shape, dtype=float)
    for color in colors:
        plus = coordinates.copy()
        minus = coordinates.copy()
        for column in color:
            plus[column] += step
            minus[column] -= step
        delta = (residual_function(plus) - residual_function(minus)) / (2.0 * step)
        for column in color:
            rows = (
                np.arange(matrix_pattern.shape[0], dtype=int)
                if mode == "uncolored"
                else matrix_pattern.indices[
                    matrix_pattern.indptr[column] : matrix_pattern.indptr[column + 1]
                ]
            )
            jacobian[rows, column] = delta[rows]
    return csr_matrix(jacobian)


@dataclass
class AdaptiveLambdaController:
    delta: float = 0.10
    minimum_delta: float = 1.0 / 128.0
    maximum_growth: float = 1.5
    maximum_consecutive_reductions: int = 6
    easy_nfev: int = 8
    consecutive_reductions: int = 0

    def target(self, accepted_lambda: float) -> float:
        return min(1.0, float(accepted_lambda) + self.delta)

    def accept(self, *, nfev: int) -> None:
        self.consecutive_reductions = 0
        if int(nfev) <= self.easy_nfev:
            self.delta = min(1.0, self.delta * self.maximum_growth)

    def reject(self) -> bool:
        self.consecutive_reductions += 1
        if self.delta <= self.minimum_delta:
            return False
        self.delta = max(self.minimum_delta, self.delta * 0.5)
        return bool(
            self.consecutive_reductions
            <= self.maximum_consecutive_reductions
        )


def _matrix_rank_condition(matrix: csr_matrix) -> tuple[int, float]:
    dense = matrix.toarray()
    singular = np.linalg.svd(dense, compute_uv=False)
    rank = int(np.linalg.matrix_rank(dense))
    condition = float(
        np.inf if singular.size == 0 or singular[-1] == 0.0 else singular[0] / singular[-1]
    )
    return rank, condition


def solve_direct_steady_state_continuation(
    problem: DirectSteadyStateProblem,
    initial_vector: Sequence[float],
    *,
    homotopy_tolerance: float = 1.0e-7,
    final_physical_tolerance: float = 1.0e-6,
    condition_limit: float = 1.0e12,
    condition_growth_limit: float = 100.0,
    max_nfev: int = 200,
    verify_uncolored_endpoints: bool = False,
    accepted_state_callback: Callable[[ContinuationPoint, np.ndarray], None] | None = None,
) -> DirectContinuationResult:
    """Solve the five DD-073 systems, stopping at the first failed gate."""
    stages = build_continuation_stages(problem)
    current = np.asarray(initial_vector, dtype=float).copy()
    stage_results: list[ContinuationStageResult] = []
    final_stage = 0
    stop_reason = ""

    for stage in stages:
        anchor_eval = evaluate_direct_steady_state_residual(problem, current)
        coordinates = SmoothPhysicalCoordinates(
            problem, current, anchor_eval.variable_scales
        )
        lower, upper = coordinates.bounds(stage.unknown_indices)
        solver_coordinates = coordinates.encode(current, stage.unknown_indices)
        residual_scales = anchor_eval.residual_scales.copy()
        pattern = stage_structural_pattern(problem, stage)
        accepted_lambda = 0.0
        controller = AdaptiveLambdaController()
        points: list[ContinuationPoint] = []
        previous_condition: float | None = None
        endpoint_difference: float | None = None

        while accepted_lambda < 1.0 - 1.0e-14:
            target_lambda = controller.target(accepted_lambda)
            attempted_delta = target_lambda - accepted_lambda

            def fun(value: np.ndarray) -> np.ndarray:
                return evaluate_stage_homotopy(
                    problem,
                    stage,
                    coordinates,
                    value,
                    target_lambda,
                    residual_scales,
                ).vector

            def jac(value: np.ndarray) -> csr_matrix:
                return finite_difference_stage_jacobian(fun, value, pattern)

            try:
                solved = least_squares(
                    fun,
                    solver_coordinates,
                    jac=jac,
                    bounds=(lower, upper),
                    method="trf",
                    tr_solver="lsmr",
                    x_scale="jac",
                    ftol=1.0e-11,
                    xtol=1.0e-11,
                    gtol=1.0e-11,
                    max_nfev=int(max_nfev),
                )
                candidate = evaluate_stage_homotopy(
                    problem,
                    stage,
                    coordinates,
                    solved.x,
                    target_lambda,
                    residual_scales,
                )
                jacobian = csr_matrix(solved.jac)
                rank, condition = _matrix_rank_condition(jacobian)
                saturation = coordinates.saturated(
                    solved.x, stage.unknown_indices
                )
                conservation_pass = bool(
                    candidate.physical.conservation.component_pass
                    and candidate.physical.conservation.energy_pass
                    and candidate.physical.conservation.internal_energy_pairing_pass
                )
                condition_growth_pass = bool(
                    previous_condition is None
                    or condition
                    <= condition_growth_limit * max(previous_condition, 1.0)
                )
                passed = bool(
                    solved.success
                    and candidate.homotopy_inf_norm < homotopy_tolerance
                    and rank == stage.size
                    and condition < condition_limit
                    and condition_growth_pass
                    and conservation_pass
                    and not candidate.physical.safeguards_used
                    and not saturation
                )
                reason = (
                    "accepted"
                    if passed
                    else (
                        f"solver_success={solved.success}; "
                        f"homotopy_inf={candidate.homotopy_inf_norm:.3e}; "
                        f"rank={rank}/{stage.size}; condition={condition:.3e}; "
                        f"condition_growth_pass={condition_growth_pass}; "
                        f"conservation_pass={conservation_pass}; "
                        f"saturation={len(saturation)}"
                    )
                )
                point = ContinuationPoint(
                    stage=stage.number,
                    stage_name=stage.name,
                    lambda_value=float(target_lambda),
                    delta_lambda=float(attempted_delta),
                    accepted=passed,
                    solver_success=bool(solved.success),
                    nfev=int(solved.nfev),
                    njev=int(solved.njev or 0),
                    homotopy_inf_norm=candidate.homotopy_inf_norm,
                    physical_scaled_inf_norm=candidate.physical_scaled_inf_norm,
                    rank=rank,
                    condition_estimate=condition,
                    component_conservation_pass=bool(
                        candidate.physical.conservation.component_pass
                    ),
                    energy_conservation_pass=bool(
                        candidate.physical.conservation.energy_pass
                    ),
                    safeguards_used=candidate.physical.safeguards_used,
                    coordinate_saturation=saturation,
                    reason=reason,
                )
            except Exception as exc:
                passed = False
                candidate = None
                solved = None
                point = ContinuationPoint(
                    stage=stage.number,
                    stage_name=stage.name,
                    lambda_value=float(target_lambda),
                    delta_lambda=float(attempted_delta),
                    accepted=False,
                    solver_success=False,
                    nfev=0,
                    njev=0,
                    homotopy_inf_norm=float("inf"),
                    physical_scaled_inf_norm=float("inf"),
                    rank=0,
                    condition_estimate=float("inf"),
                    component_conservation_pass=False,
                    energy_conservation_pass=False,
                    safeguards_used=(),
                    coordinate_saturation=(),
                    reason=f"{type(exc).__name__}: {exc}",
                )
            points.append(point)

            if passed and candidate is not None and solved is not None:
                solver_coordinates = np.asarray(solved.x, dtype=float).copy()
                current = candidate.physical_vector.copy()
                accepted_lambda = target_lambda
                previous_condition = point.condition_estimate
                controller.accept(nfev=point.nfev)
                if accepted_state_callback is not None:
                    accepted_state_callback(point, current.copy())
            elif not controller.reject():
                stop_reason = (
                    f"stage {stage.number} {stage.name} stopped at "
                    f"lambda={accepted_lambda:.8g}: {point.reason}"
                )
                break

        stage_accepted = accepted_lambda >= 1.0 - 1.0e-14
        if stage_accepted and verify_uncolored_endpoints:
            endpoint_lambda = 1.0

            def endpoint_fun(value: np.ndarray) -> np.ndarray:
                return evaluate_stage_homotopy(
                    problem,
                    stage,
                    coordinates,
                    value,
                    endpoint_lambda,
                    residual_scales,
                ).vector

            colored = finite_difference_stage_jacobian(
                endpoint_fun, solver_coordinates, pattern, mode="colored"
            ).toarray()
            uncolored = finite_difference_stage_jacobian(
                endpoint_fun, solver_coordinates, pattern, mode="uncolored"
            ).toarray()
            endpoint_difference = float(np.max(np.abs(colored - uncolored)))
            if endpoint_difference > 1.0e-9:
                stage_accepted = False
                stop_reason = (
                    f"stage {stage.number} colored/uncolored endpoint mismatch "
                    f"{endpoint_difference:.3e}"
                )

        stage_result = ContinuationStageResult(
            stage=stage,
            accepted=stage_accepted,
            final_lambda=float(accepted_lambda),
            physical_vector=current.copy(),
            solver_coordinates=solver_coordinates.copy(),
            points=tuple(points),
            uncolored_endpoint_max_difference=endpoint_difference,
            reason="accepted" if stage_accepted else stop_reason,
        )
        stage_results.append(stage_result)
        if not stage_accepted:
            break
        final_stage = stage.number

    final_evaluation = evaluate_direct_steady_state_residual(problem, current)
    final_stage_complete = final_stage == len(stages)
    block_tolerances = {
        "local_component_closure": 1.0e-8,
        "local_energy_closure": 1.0e-7,
        "local_volume_closure": 1.0e-7,
        "local_equilibrium": 1.0e-6,
        "steady_component_balance": 1.0e-8,
        "steady_energy_balance": 1.0e-7,
        "liquid_hydraulics": 1.0e-6,
        "vapor_pressure_drop": 1.0e-6,
        "operating_specification": 1.0e-6,
    }
    block_maxima = {
        block: max(
            abs(row.scaled_value)
            for row in final_evaluation.rows
            if row.block == block
        )
        for block in block_tolerances
    }
    failures = [
        f"{block}={block_maxima[block]:.3e}>{tolerance:.3e}"
        for block, tolerance in block_tolerances.items()
        if block_maxima[block] >= tolerance
    ]
    values = {
        entry.name: float(current[index])
        for index, entry in enumerate(problem.registry.unknowns)
    }
    pressure_nodes = (
        "reflux_drum",
        *(f"tray_{stage}" for stage in problem.registry.active_stage_ids),
        "partial_reboiler",
    )
    pressure_profile = np.asarray(
        [values[f"P[{node}]"] for node in pressure_nodes], dtype=float
    )
    if not np.all(np.diff(pressure_profile) > 0.0):
        failures.append("pressure profile is not strictly increasing top-to-bottom")
    flow_names = tuple(
        entry.name
        for entry in problem.registry.unknowns
        if entry.block in {"liquid_flow", "vapor_flow", "manipulated_variable"}
    )
    if any(values[name] <= 0.0 for name in flow_names):
        failures.append("one or more flow or duty variables are not positive")
    if not (
        final_evaluation.conservation.component_pass
        and final_evaluation.conservation.energy_pass
        and final_evaluation.conservation.internal_energy_pairing_pass
    ):
        failures.append("external conservation gate failed")
    if final_evaluation.safeguards_used:
        failures.append("a numerical safeguard was active")
    if final_stage_complete:
        endpoint = stage_results[-1].points[-1]
        if endpoint.rank != len(problem.registry.unknowns):
            failures.append(
                f"final Jacobian rank is {endpoint.rank}/{len(problem.registry.unknowns)}"
            )
        if endpoint.condition_estimate >= condition_limit:
            failures.append(
                f"final condition estimate {endpoint.condition_estimate:.3e} "
                f"exceeds {condition_limit:.3e}"
            )
    if final_evaluation.scaled_inf_norm >= final_physical_tolerance:
        failures.append(
            f"global scaled infinity norm {final_evaluation.scaled_inf_norm:.3e} "
            f"exceeds {final_physical_tolerance:.3e}"
        )
    accepted = bool(final_stage_complete and not failures)
    if accepted:
        classification = "dd073_direct_steady_state_solution_accepted"
        stop_reason = "all five continuation stages and the final physical gate passed"
    elif final_stage_complete:
        classification = "dd073_final_physical_gate_failed"
        stop_reason = (
            "all stages reached lambda=1, but the final physical gate failed: "
            + "; ".join(failures)
        )
    else:
        classification = "dd073_continuation_stopped"

    repeated = evaluate_direct_steady_state_residual(problem, current)
    return DirectContinuationResult(
        accepted=accepted,
        classification=classification,
        final_stage=final_stage,
        final_vector=current,
        stages=tuple(stage_results),
        final_evaluation=final_evaluation,
        final_block_maxima=tuple(sorted(block_maxima.items())),
        final_gate_failures=tuple(failures),
        physical_final_matches_direct_evaluator=bool(
            np.array_equal(final_evaluation.raw, repeated.raw)
        ),
        reason=stop_reason,
    )
