# Validation Readiness Gate

Date: 2026-05-26

Related initialization note: `docs/dynamic_column_initialization_strategy.md`

## Position

Do not claim rigorous dynamic validation while known model defects or unresolved topology mismatches materially affect the same behavior being compared.

Validation is not just obtaining a steady-state flag or forcing a run to resemble a source. A validation case must test the model as intended, with assumptions and topology aligned to the source. If the run only passes after disabling or bypassing relevant model physics, then it is a narrower regression or diagnostic, not full validation.

## Current Evidence

### Skogestad Column A

The Skogestad relative-volatility case remains a valid Tier 1 source-topology validation because:

- the model topology is intentionally matched to the source equations,
- the source does not include energy, vapor holdup, named chemicals, density, or hydraulic pressure,
- the steady profile and feed-disturbance response are compared against the source-equation behavior.

This validates the source-equivalent material-balance/liquid-holdup path. It does not validate rigorous thermo, vapor holdup, stage energy, hydraulic pressure, or controllers.

### Gani/ChemSep Debutanizer

The Gani case should not be called full rigorous dynamic validation at this time.

Accepted limited uses:

- source-topology real-component material-balance parity using the ChemSep `x/y/L/V` profile together,
- full-topology material-accounting diagnostic after explicit bottom-sump liquid-flow conversion,
- full-topology total material reconciliation under fixed profile-flow assumptions.

Not accepted:

- full dynamic validation with explicit condenser drum, bottom sump, tray vapor states, stage energy, and PR thermo.

Reason:

- the original ChemSep/source topology and the full model topology differ at the terminal reboiler/bottom sump,
- ChemSep vapor compositions and Clapeyron PR vapor compositions are materially different,
- full-topology dynamic runs still show large `tray_V` residuals even after total material reconciliation,
- the remaining behavior is tied to feed-stage phase redistribution and separate liquid/vapor holdup dynamics.

Forcing this case to pass by disabling vapor states, overwriting phase profiles, or using a source-topology-only run would validate only the reduced assumptions, not the full model.

### C3/C4 Splitter Diagnostic

The C3/C4/depropanizer-style case shows related but much milder residual behavior:

- C3/C4 recent 60 s probe: final `steady_state_score ~= 4.04`, max relative state rate `~= 0.0109 1/s`,
- older C3/C4 parity probes were around score `2-3`,
- Gani full-topology material-reconciled probe remained around score `62.5`, max relative state rate `~= 0.188 1/s`.

This suggests the issue is not purely Gani-specific, but Gani amplifies it through source/topology/phase-split mismatch. The C3/C4 case is therefore a better development diagnostic than Gani for isolating full-topology phase-holdup behavior.

Follow-up on 2026-05-28: freezing tray vapor derivatives in the C3/C4 open-loop parity case made the steady-state detector pass, but the liquid profile drifted far outside validation tolerance. This confirms that a quiet derivative score can be produced by suppressing one dynamic block while still losing the intended source profile. That result supports treating ChemSep or Excel steady-state data as initialization guesses requiring model-consistent reconciliation, not as final dynamic initial conditions.

## Gate Criteria

Before claiming rigorous dynamic validation for a case involving real components and full topology, the model should satisfy all relevant criteria below.

1. Topology match is explicit.
   - The case must state whether condenser/reboiler are included as stages or represented as explicit boundary vessels.
   - Terminal liquid/vapor flows must be converted consistently when moving between source topology and model topology.

2. Material balances close by phase where phase holdups are dynamic.
   - If tray vapor states are enabled, `tray_V` residuals must be meaningful and small, not merely cancelled by opposite `tray_L` residuals.
   - Total material closure alone is insufficient when separate phase holdups are part of the model being validated.

3. Feed treatment is consistent.
   - The feed split must be one of: source-specified, live thermo flash, enthalpy flash, or solved in a steady initializer.
   - The chosen treatment must match the source assumptions or be documented as a model-development deviation.

4. Thermo basis is consistent.
   - Source thermo and model thermo must be the same, or differences must be quantified and treated as a development comparison rather than validation.
   - Large vapor-composition moves introduced by reconciliation are evidence against a validation claim.

5. Startup does not alter a reconciled validation seed.
   - For deliberately reconciled workbooks, hidden startup/restart conditioning must be disabled or shown not to perturb the state.
   - The runner now supports `--disable-restart-reentry-settling` for this purpose.

6. Energy validation requires energy closure.
   - A case with stage energy balance must show acceptable energy residuals before its dynamic energy response is compared.
   - Material-only reconciliation cannot be used as proof of energy-model validity.

7. Numerical steadiness is not enough.
   - `steady_state_flag` and `steady_state_score` remain diagnostics.
   - Validation requires comparison to external/source results or defined acceptance metrics for the specific case.

8. Imported steady-state profiles are seeds unless proven otherwise.
   - ChemSep/Excel `T/P/x/y/L/V` values may be used as initialization guesses and source-topology references.
   - Full dynamic acceptance requires an initialization residual audit against this model's RHS and topology.
   - Freezing dynamic states or disabling physics may be useful diagnostically, but cannot validate behavior that depends on those states or physics.

## Recommended Path

1. Keep Skogestad as the accepted Tier 1 validation baseline.
2. Freeze Gani as:
   - accepted source-topology material parity,
   - useful full-topology material-reconciliation diagnostic,
   - not full rigorous dynamic validation.
3. Use the C3/C4 case as the near-term development diagnostic for full-topology phase-holdup behavior because it shows the same class of issue with less severe source mismatch.
4. Write or implement a feed-stage phase/energy reconciliation design before attempting another full rigorous validation claim.
5. Implement a staged initialization workflow: residual audit first, narrow vapor/boundary closure next, then golden-seed serialization only after profile and conservation gates pass.
6. Continue searching for a validation source whose topology, feed treatment, thermo, and dynamic outputs are sufficiently specified to avoid retrofitting the model around missing assumptions.

## Bottom Line

We cannot validate around known model defects. The correct near-term goal is to use these cases to expose and repair model behavior, then return to validation once topology, phase holdup, feed handling, and energy closure are internally credible.
