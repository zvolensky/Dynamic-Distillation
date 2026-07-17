# DD-060 Physics-Owned Tray-Flow Probe

Date: 2026-07-12

## Objective

Determine whether DD-058's composition-exponential update could be extended to the full flash phase split so net tray evaporation and condensation, and therefore non-flat liquid traffic, would emerge from physics rather than the imported profile.

## Implementation

An opt-in `phase-exponential` equilibrium mode was added. It combines the existing full TP-flash phase target with the bounded exponential post-transport update used successfully by `composition-exponential`. The accepted DD-058 mode and defaults were not changed.

Focused equilibrium and runner tests passed: `157 passed`.

## Dynamic probe

Run folder: `logs/c3c4_dd060_phase_exponential_onestep_20260712`

The probe restarted from the valid DD-058 native checkpoint with live DWSIM PR, retained the existing `alpha=0.25` liquid-hydraulic blend, and changed only the equilibrium mode.

The result failed immediately:

| Metric | DD-058 | DD-060 after 0.2 s |
|---|---:|---:|
| Dynamic score | 0.0848 | 821 |
| Maximum relative state rate | 0.000254/s | 2.46/s |

The fixed-T/P flash target requested very large phase-total changes. Examples from the post-step diagnostic include about `-30.8 lbmol/s` net vapor change on stage 2 and `+68.2 lbmol/s` on stage 19. Stage 19's TP flash target was all vapor even though the live tray was liquid dominated.

## Interpretation

This is not an integration-timestep or Francis-weir problem. A TP flash holds temperature and pressure fixed while changing phase inventory, so it does not simultaneously pay the latent-energy cost of vaporization or condensation. Applying that phase target to the explicit liquid and vapor holdups therefore creates a severe nonphysical source term.

The `phase-exponential` mode is retained only as an experimental diagnostic. It is not an accepted physics closure.

## UV probe

The existing stage UV solver was then applied to representative DD-058 trays. It conserves total component inventory, internal energy, and volume while solving temperature, pressure, phase fraction, and equilibrium compositions. All five representative solves converged in four or five iterations with tight residuals.

However, the comparison exposed incompatible pressure ownership in the current dynamic state:

| Stage | Hydraulic P (psia) | Vapor-holdup implied P (psia) | UV equilibrium P (psia) |
|---|---:|---:|---:|
| 2 | 223.87 | 237.60 | 221.36 |
| 6 | 225.52 | 285.79 | 233.15 |
| 12 | 228.28 | 299.70 | 233.67 |
| 18 | 231.60 | 291.93 | 247.77 |
| 19 | 232.18 | 293.85 | 268.67 |

The live model currently permits hydraulic pressure and explicit vapor holdup to imply different thermodynamic states. A local phase-transfer correction cannot reconcile both owners.

## Decision

Do not proceed to full Francis ownership by merely setting `alpha=1.0`, and do not tune a longer phase-relaxation time constant. Either action would mask the structural closure problem.

The next viable model formulation should use conserved tray component totals and internal energy as differential states, then solve a UV equilibrium/volume block for `T`, `P`, phase fraction, `x`, and `y`. Francis hydraulics should determine liquid outflow from the solved liquid inventory and geometry. Vapor traffic and pressure must be included in the same algebraic closure so vapor holdup and pressure no longer have independent owners.

DD-058 remains a useful numerically stable checkpoint and controller baseline, but its flat section-wise liquid traffic prevents it from being accepted as a rigorous physical steady-state solution.
