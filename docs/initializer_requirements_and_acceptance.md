# Initializer Requirements and Acceptance Criteria

## Purpose

This document captures the user and functional requirements for the dynamic column initializer, including its inputs, outputs, acceptance criteria, and the current implementation strategy.

## User Requirements

1. Start from an imported steady-state seed.
   - The user should be able to provide a ChemSep, Excel, or other steady-state profile as an initialization seed.

2. Obtain a dynamically acceptable initial state.
   - The user should be able to generate an initial state that is not only numerically quiet, but also dynamically acceptable at $t=0$.

3. Inspect why a candidate fails.
   - The user should be able to see which model blocks are inconsistent, including vapor state, equilibrium/K-value, pressure/vapor-flow, energy/temperature, and boundary states.

4. Compare candidate initializations.
   - The user should be able to compare a baseline seed, a residual-solver candidate, and any other candidate initialization.

5. Avoid accepting weak or misleading seeds.
   - The system should prevent acceptance of a candidate that only improves static residuals but still fails in a short dynamic run.

6. Preserve and reuse accepted states.
   - Once a candidate is accepted, the user should be able to serialize it for later restart or replay.

## Functional Requirements

1. Seed ingestion.
   - The initializer must accept a case definition, Excel workbook, or steady-state profile and associated column/specification data.

2. State construction.
   - The initializer must construct an initial state vector containing tray liquid composition, tray vapor composition, tray temperature, tray pressure, tray liquid/vapor holdup, and top/bottom boundary states.

3. Residual evaluation at $t=0$.
   - The system must evaluate the dynamic model RHS at $t=0$ and compute residuals for tray liquid rates, tray vapor rates, boundary rates, pressure/vapor-flow closure, energy/temperature rates, and feed-stage terms.

4. Residual-based solve.
   - The initializer must be able to solve for a better initial state by minimizing or driving the residual vector toward zero.

5. Physical constraints.
   - The solve must enforce bounds and physical plausibility, including nonnegative holdups, bounded pressures, bounded compositions, and nonnegative flow terms where appropriate.

6. Relaxation/homotopy support.
   - The initializer may use relaxation or homotopy terms as stabilization aids, but these must not be the sole criterion for acceptance.

7. Coupling diagnostics.
   - The system must report coupling-level diagnostics such as K-state vs K-thermo mismatch, vapor composition closure error, vapor-flow mismatch, energy/temperature mismatch, pressure-vapor-holdup inconsistency, and low liquid-inventory/timestep-sensitivity risk.

8. Baseline-vs-candidate comparison.
   - The system must compare a candidate initialization against a baseline and report where the candidate is better or worse.

9. Dynamic acceptance gate.
   - A candidate should only be accepted if it performs better than the baseline in a short dynamic smoke test or equivalent acceptance metrics.

10. Serialization.
    - The accepted state must be serialized to a restartable artifact. A native checkpoint or structured state file is preferred for accepted dynamic seeds because it can preserve packed state, thermo/hydraulic memory, controller state, and boundary state without Excel round-tripping.
    - Excel restart workbooks may be emitted for inspection and interoperability, but they are not sufficient acceptance artifacts unless a dynamic smoke gate proves that reloading the workbook preserves the accepted state.

11. Initializer execution logging.
    - The initializer must generate a detailed execution log in plain-text format with filename convention `initializer_<case_name>_<YYYYMMDD_HHMMSS>.log`.
    - The log must record:
      - **Header**: run start date/time (ISO 8601), Excel seed file name, case name, column name, runtime configuration (thermo mode, relaxation settings, acceptance thresholds).
      - **Milestones**: structured entries for each key phase with wall-clock timestamp, elapsed time since start, status (OK/FAIL), and phase-specific metrics.
      - **Reproducibility**: Git commit hash or code version, random seeds, and initialization parameters for deterministic replay.
    - **Tracked Milestones**:
      1. Seed ingestion & validation — file loaded, composition normalization, bound checks
      2. State vector construction — total holdups, total moles, pressure distribution
      3. Initial residual evaluation (t=0) — residual norms (L2, L∞) by block (liquid rates, vapor rates, boundary rates, pressure/vapor-flow closure, energy/temperature, feed-stage)
      4. Residual-based solve iterations — iteration count, convergence rate, worst-residual tray/component per iteration
      5. Physical constraint enforcement — bound violations detected and corrected, holdup/pressure/composition adjustments
      6. Dynamic acceptance gate (smoke test) — duration, max state-rate changes, stability assessment, max ΔP and ΔT over test window
      7. Coupling diagnostics summary — K-state vs K-thermo mismatch, vapor closure error, vapor-flow mismatch, energy/temperature mismatch, pressure-vapor-holdup inconsistency
      8. Baseline-vs-candidate comparison — residual improvement, smoke test performance delta
      9. Serialization — checkpoint or workbook written, file size, verification status
      10. Final acceptance/rejection decision — reason code and summary
    - The log must also include a clean usable assessment milestone with explicit `usable=true/false`, assessment basis, residual gate result, dynamic gate result, and rejection reason.
    - **Key Metrics Format**: each milestone includes [WALL_TIME | ELAPSED_TIME | STATUS | METRIC_1=value | METRIC_2=value | ...]
    - **Diagnostic Features**:
      - Cumulative and per-milestone elapsed times to identify bottlenecks
      - Worst-offending trays and components flagged at each residual/constraint/diagnostic phase
      - Failure-mode capture: which milestone failed, residual threshold exceeded, bound violation type
      - Smoke test trajectory excerpt (first, max, final state-rate and pressure values)
    - **Closure**: log ends with final status summary and output artifact locations (checkpoint, workbook, residual audit report).

## Inputs

### Required inputs
- Case definition or Excel workbook
- Column specification
- Initial seed profile
- Runtime configuration
- Thermo configuration

### Optional inputs
- Bounds for state variables
- Residual weights
- Relaxation parameters
- Acceptance thresholds
- Dynamic smoke-test duration
- Target metrics for pressure, temperature, and state-rate behavior

## Outputs

### Primary outputs
- Accepted or rejected initialization candidate
- Solved initial state vector
- Residual audit report
- Dynamic gate report
- Clean usable assessment (`usable`, `basis`, `reason`, residual-gate status, and dynamic-gate status)
- Accepted artifact summary identifying whether the preferred restart artifact is a native checkpoint, provisional workbook, or diagnostic-only workbook
- Accepted artifact restart command showing how to launch the dynamic simulation from the selected workbook/checkpoint pair
- Initializer execution log file (plain-text, `initializer_<case_name>_<timestamp>.log`, containing run metadata, 10 key milestones with wall-clock/elapsed times and metrics, diagnostics, and decision rationale)

### Secondary outputs
- Ranked residual blocks
- Worst offending trays/components
- Coupling defect summary
- Liquid-inventory depletion and composition-step audit
- Serialized checkpoint or workbook
- Baseline-vs-candidate comparison report

## Acceptance Criteria

A candidate initialization is considered successful if:
- the $t=0$ residuals are materially reduced,
- the state remains physically plausible,
- the short dynamic run is stable or improved relative to baseline,
- and the coupling diagnostics do not reveal a new structural inconsistency.

The implementation should make this verdict explicit. The initializer summary and execution log should contain a `clean_usable_assessment` object rather than requiring the user to infer usability from separate residual, dynamic-gate, and diagnostic fields. If the dynamic gate is enabled, a seed is clean/usable only when both the residual gate and dynamic gate pass. If the dynamic gate is not enabled, the assessment may report residual-gate usability, but it must also flag that dynamic-gate evidence is still required for final acceptance.

The implementation should also make the accepted restart artifact explicit. If the clean/usable assessment passes and the dynamic smoke run produced a native checkpoint, that checkpoint should be reported as the preferred accepted artifact. If the only available artifact is an Excel workbook, the summary should mark it as provisional or diagnostic unless dynamic reload parity has been demonstrated.

For production acceptance, the initializer should be able to run an optional checkpoint reload gate: reload the preferred native checkpoint through the runtime `--init-from-checkpoint` path, run a short smoke test, and compare the reload trajectory against the accepted candidate smoke. A failed reload gate means the checkpoint is not yet a proven reusable initializer artifact.

The dynamic gate should also reject candidates that hide a slow internal liquid inventory depletion. A run can look acceptable by rate metrics until a nearly empty internal liquid inventory produces a large explicit composition step. The profile-level audit for this failure mode is `tools/audit_liquid_inventory_depletion.py`; by default it evaluates internal stages and leaves top/bottom terminal equipment to boundary-specific checks.

## Current Implementation Direction

The current recommended direction is:
- use residual audits and bounded least-squares as targeted diagnostic/solve steps, not as the sole acceptance mechanism,
- optimize the smallest justified state subset first, then verify with the dynamic gate,
- use relaxation/homotopy only as startup or solve stabilizers, not as proof of a steady initial condition,
- prefer native checkpoint-style serialization for accepted seeds,
- treat Excel-only checkpoint-guided exports as diagnostic bridges until they pass reload tests with startup/re-entry conditioning disabled,
- inspect vapor/thermo/energy/pressure coupling directly when a candidate fails dynamically.

## 2026-07-08 Checkpoint-Guided Seed Lesson

A checkpoint-guided Excel export was tested by writing the quiet `900 s` profile back into the workbook. After fixing generic component-name mapping (`n-Propane` workbook names versus `n_Propane` log columns), the workbook preserved tray compositions, holdups, flows, and top/bottom boundary liquid states. It still did not match native checkpoint restart behavior under default startup because startup thermo conditioning altered the reconciled tray compositions before the first logged timestep.

With startup/re-entry conditioning disabled, the workbook reload was much better and stayed bounded for `60 s`, but it still underperformed the native checkpoint restart. The practical conclusion is that the accepted initializer should serialize the accepted packed state and runtime memory, while workbook export remains useful for review, audits, and interoperability.
