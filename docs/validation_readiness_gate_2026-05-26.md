# Validation Readiness Gate

Date: 2026-05-26

Related initialization note: `docs/dynamic_column_initialization_strategy.md`
Current model-state note: `docs/dynamic_model_current_state_2026-07-12.md`

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

Follow-up on 2026-07-07: the C3/C4 case remains the best near-term diagnostic, but recent probes argue against more broad residual tuning. Quarantining degenerate PR unit-K packets improved thermo hygiene but did not produce an accepted launch. Top-liquid condensate alignment reduced the targeted top-boundary liquid residual but still failed the dynamic gate. A vapor-flow nominal ceiling probe slightly improved one local vapor-flow mismatch while worsening score, peak score, and temperature behavior. A vapor-flow/energy-closure residual objective reduced optimizer norm but worsened physical residual audits. Current stance: do not claim full-topology C3/C4 validation, and do not pursue another generic residual-reweighting initializer before reviewing the energy/vapor-flow closure equations and topology.

Follow-up on 2026-07-08: the C3/C4 case now has a useful 900 s linear-steady/equilibrium-guard working baseline and native checkpoint path, but it is still not a full validation case. No-energy checkpoint reloads, top-pressure anchoring, top-vapor packing, and liquid-holdup projection/solve probes did not remove the remaining vapor/material/pressure residual family. The model should be described as improved and bounded under a specific diagnostic recipe, not as generally healthy or production-validated. The next validation-relevant work is a dynamic-model coupling audit and incremental equation/closure repair, not another generic initializer tuning pass.

Follow-up on 2026-07-08 K-level gate: the 900 s C3/C4 rate-based pass is not enough for validation readiness. `K_state` versus `K_thermo` remains materially inconsistent and worsens late in the run, dominated by n-pentane in generic interior stages. Validation readiness now requires a K-level consistency gate in addition to derivative/rate gates.

## Gate Criteria

Before claiming rigorous dynamic validation for a case involving real components and full topology, the model should satisfy all relevant criteria below.

1. Topology match is explicit.
   - The case must state whether condenser/reboiler are included as stages or represented as explicit boundary vessels.
   - Terminal liquid/vapor flows must be converted consistently when moving between source topology and model topology.
   - For total condensers, the validation case must state whether the total condenser is an algebraic boundary, an explicit condenser/reflux-drum boundary, or a counted source stage. Condenser duty and condensed-liquid enthalpy must be owned by that boundary, not by a dry tray state.

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
   - A total-condenser case must pass a condenser/reflux-drum energy closure check before it is used for full-topology energy validation.

7. Numerical steadiness is not enough.
   - `steady_state_flag` and `steady_state_score` remain diagnostics.
   - Validation requires comparison to external/source results or defined acceptance metrics for the specific case.

8. Imported steady-state profiles are seeds unless proven otherwise.
   - ChemSep/Excel `T/P/x/y/L/V` values may be used as initialization guesses and source-topology references.
   - Full dynamic acceptance requires an initialization residual audit against this model's RHS and topology.
   - Freezing dynamic states or disabling physics may be useful diagnostically, but cannot validate behavior that depends on those states or physics.

9. Equilibrium level consistency must hold.
   - A rate-based steady-state score is not sufficient if `K_state` is drifting away from `K_thermo`.
   - Accepted full-topology runs must pass an explicit K-state drift gate, including final magnitude and trend checks.

10. Internal liquid inventories must remain buffered.
   - A full-topology dynamic run must not pass validation if an internal tray liquid inventory slowly drains toward zero and then produces a large explicit composition step.
   - Use `tools/audit_liquid_inventory_depletion.py` on dynamic profile CSVs to check minimum internal liquid inventory, inventory update fraction, and largest composition step.
   - Top and bottom terminal equipment should be assessed by their boundary-specific inventory/level checks; the liquid-inventory depletion audit defaults to internal stages.

## Recommended Path

1. Keep Skogestad as the accepted Tier 1 validation baseline.
2. Freeze Gani as:
   - accepted source-topology material parity,
   - useful full-topology material-reconciliation diagnostic,
   - not full rigorous dynamic validation.
3. Preserve C3/C4 DD-058 as an operational regression checkpoint, not the
   foundation for another initializer or solver variant.
4. Implement the DD-076 equilibrium-DAE v2 gates in order, beginning with
   source-equation assembly and one-volume energy/property closure.
5. Require one independently reproduced five-volume steady reference with
   Francis as the sole liquid-flow owner before production tray count.
6. Add hydraulic pressure only after the prescribed-pressure,
   negligible-vapor-holdup model passes steady and dynamic gates.
7. Add explicit vapor inventory only as a separately derived final layer with
   a new ownership and index audit.
8. Continue searching for validation sources whose topology, thermo, feed,
   pressure, energy, and dynamic outputs are sufficiently specified to avoid
   fitting the model around missing assumptions.

## Bottom Line

We cannot validate around known model defects. The correct near-term goal is to use these cases to expose and repair model behavior, then return to validation once topology, phase holdup, feed handling, and energy closure are internally credible.
