# DD-065: Frozen Checkpoint UV and Hydraulic Closure

Date: 2026-07-17

## Question

Can the accepted 2400-second C3/C4 checkpoint be reinterpreted as frozen
conserved component totals and internal energy, then closed algebraically
without changing the production dynamic model?

This is the falsification step required before a broader implicit or DAE
rewrite.

## Frozen State

For each active interior tray, the bridge freezes:

```text
N_total[k, component] = N_liquid + N_vapor
U_total[k] = EL + EV - P * V_total
```

The checkpoint liquid/vapor split, temperature, pressure, and flows are used
only as algebraic initial guesses. The solve determines temperature, pressure,
phase fraction, equilibrium compositions, liquid flow, and vapor flow.

`EL` and `EV` are phase enthalpy inventories in the runtime state. The explicit
`P*V` subtraction is therefore required to obtain the internal energy used by
the UV formulation.

## Local UV Result

All 18 active interior trays closed with DWSIM Peng-Robinson.

| Metric | Result | Gate |
|---|---:|---:|
| Component reconstruction relative maximum | `5.78e-11` | `<1e-8` |
| Energy relative maximum | `4.73e-12` | `<1e-7` |
| Volume relative maximum | `1.15e-10` | `<1e-7` |
| Flash beta consistency maximum | `6.19e-11` | `<1e-6` |
| Negative phase amounts | `0` | `0` |
| Accepted projected states | `0` | `0` |

The first unscaled Newton attempt failed on stages 3 and 4. An explicitly
scaled bounded least-squares retry closed both stages tightly from several
initial guesses. This was a numerical scaling issue, not evidence that their
conserved states lacked a UV solution.

The thermo-provider protocol does not expose phase fugacity coefficients.
Therefore a direct fugacity-residual gate remains unverified. TP-flash and
phase-fraction consistency pass, but must not be mislabeled as a fugacity
residual.

The locally reconstructed pressure profile is physically incompatible with
normal upward vapor traffic:

- stage 2: `321.89 psia`;
- stage 3: `320.55 psia`;
- stage 11: `270.12 psia`;
- stage 12: `230.29 psia`;
- stage 17: `202.47 psia`;
- stage 19: `205.16 psia`.

By contrast, the checkpoint hydraulic pressure rises from about `225.11 psia`
at stage 2 to `232.18 psia` at stage 19. The frozen per-tray totals, internal
energies, and volumes therefore imply a pressure field with the wrong overall
direction. This is direct evidence that the operational checkpoint is off the
global algebraic constraint manifold.

## Column Hydraulic Result

The nominal simultaneous pressure/liquid-flow/vapor-flow solve did not
converge in 12 iterations and failed the gates by a wide margin.

| Metric | Result | Gate |
|---|---:|---:|
| Liquid-flow scaled residual | `1.0545` | `<1e-5` |
| Vapor/pressure-drop scaled residual | `6.8154` | `<1e-5` |
| Local-UV versus global pressure maximum | `86.78 psi` | `<0.1 psi` |
| Active liquid profile/previous-flow limiters | `18` | `0` |
| Active vapor profile/previous-flow limiters | `18` | `0` |
| Accepted projected global states | `5` | `0` |

The `+/-10%` robustness repetitions were intentionally not run after the
nominal solve met several explicit stop conditions. A failed nominal solve
that depends on widespread flow limiting cannot pass the robustness gate.

## Terminal Mapping Follow-Up

DD-066 replaced the earlier excluded-inventory diagnostic with an explicit
four-block ownership map:

- empty algebraic total-condenser stage;
- physical reflux drum;
- physical partial-reboiler stage;
- physical bottoms sump.

The full checkpoint now closes its inventory bookkeeping to
`2.27e-13 lbmol` maximum component error and `1.86e-9 BTU` energy error. The
empty total-condenser stage is eliminated algebraically rather than assigned
the nonphysical `-P*V` energy of an empty fixed-volume vessel.

The terminal gate still does not pass. The simultaneous residual continues to
use liquid-only top and bottom nodes and does not yet include the mapped
reflux-drum vapor, partial-reboiler inventory, or sump headspace as algebraic
unknowns. Separate terminal UV closure also produces a reversed pressure
ordering: `P_bottom-P_top=-13.95 psi`. See
`docs/dd_066_terminal_conserved_inventory_mapping_20260717.md`.

## Controller Degree-of-Freedom Audit

The checkpoint run used four independent controlled-variable/manipulated-
variable pairs:

| Controlled variable | Manipulated variable |
|---|---|
| Distillate-drum true level | Distillate flow |
| Bottom-sump true level | Bottoms flow |
| Top pressure | Condenser duty |
| Bottoms propane mole fraction | Reboiler duty |

Reflux was fixed at `5967.32 lbmol/h`; feed was specified. The controller
assignment is not obviously overconstrained and no MV is shared by two active
controllers. `condenser-duty-mode=specified` supplies the duty basis and
bounds; the active pressure controller manipulates the duty command within
those bounds.

## Decision

Classify the result as:

> **Local UV closure succeeds; global pressure/vapor-flow closure fails.**

This is real progress because it localizes the architecture problem. The
conserved-state and DWSIM UV formulation are viable for the interior trays.
The next work belongs in an isolated, uncapped pressure/vapor-flow constraint
probe and terminal-equipment algebraic coupling. If the pressure network
cannot close because the frozen per-tray totals imply the reversed pressure
profile above, the following experiment must allow the tray conserved totals
and energies to move subject to global component and energy conservation. It
must not tune phase relaxation or reintroduce imported flow ownership.

Do not proceed to a one-step implicit production residual yet.

## Implementation and Evidence

- `src/dynamic_distillation/frozen_checkpoint_closure_v1.py`
- `tools/audit_frozen_checkpoint_closure.py`
- `tests/test_frozen_checkpoint_closure_v1.py`
- `logs/frozen_checkpoint_closure_nominal_20260717.json`
- `logs/frozen_checkpoint_closure_nominal_20260717.md`
