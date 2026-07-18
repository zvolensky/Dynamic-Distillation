# DD-069: Terminal Energy, Volume, And Basis Audit

Date: 2026-07-17

## Purpose

DD-068 found a reproducible conservative redistribution basin, but it moved
more energy than DD-067, retained a `79.16 psi` maximum pressure correction,
and placed `80.3%` of absolute energy movement in the terminal assemblies.

DD-069 tests whether that behavior comes from:

1. an incorrect `U = H - P*V` conversion;
2. inconsistent terminal or interior control volumes;
3. inconsistent phase aggregation or enthalpy basis;
4. the eliminated total-condenser placeholder;
5. DD-068 objective scaling that makes terminal movement artificially cheap.

The audit covers the reflux drum, partial-reboiler stage, bottoms sump, and
three interior controls: the first active tray, feed tray, and last active
tray. It does not run another optimizer or any hydraulic equations.

## Basis Contract

All property reconstructions use DWSIM Peng-Robinson with the same component
ordering as the runtime case. Units are:

```text
pressure             psia
volume               ft3
enthalpy/internal U  BTU
temperature          F, converted to R where required
```

The implemented pressure-volume conversion is:

```text
PV [BTU] = P [psia] * V [ft3] * 0.185049714738
```

Interior trays and the partial-reboiler stage obtain stored enthalpy from
checkpoint `EL + EV`. The reflux-drum and sump boundary layout has no stored
boundary energy state; their H and U are reconstructed from checkpoint phase
inventories, temperature, pressure, and live properties.

## Falsification Results

| Test | Result | Evidence |
|---|---|---|
| A: H/U/PV round trip | PASS | Maximum relative error `0` |
| B: fixed-volume reconstruction | FAIL | Maximum relative error `0.514720` |
| C: phase aggregation and energy basis | FAIL | Phase aggregation `1.43e-16`, but stored-H mismatch reaches `2.3325` relative |
| D: empty condenser invariance | PASS | `1.32e-14 lbmol`, `0 BTU`, and `0 ft3` mapped |
| E: scaling neutrality | FAIL | Maximum/minimum cost ratio `4134.77` |

The conversion itself is correct. Mapped U also matches its declared source
basis exactly. The defects are the physical compatibility of checkpoint
phase states with the mapped volumes and live enthalpy basis, plus the
redistribution weighting.

## Region Results

| Region | Fixed V, ft3 | Reconstructed phase V, ft3 | V relative error | Stored-H relative error |
|---|---:|---:|---:|---:|
| Reflux drum | `4330.142` | `4322.764` | `0.001704` | N/A |
| Partial-reboiler stage | `291.900` | `287.950` | `0.013532` | `0.006614` |
| Bottoms sump | `3113.601` | `1510.969` | `0.514720` | N/A |
| Tray 2 control | `908.740` | `753.860` | `0.170434` | `2.332518` |
| Feed tray 12 control | `354.155` | `218.900` | `0.381911` | `0.174207` |
| Tray 19 control | `390.064` | `278.658` | `0.285608` | `0.071014` |

The sump is the dominant terminal volume failure. Its checkpoint contains
approximately `792 lbmol` of liquid and only epsilon vapor, yet DD-068 maps
the complete `3113.6 ft3` vessel as a UV control volume. The reconstructed
checkpoint phases occupy only `1511.0 ft3`. A physical headspace therefore
exists without a corresponding conserved vapor inventory.

The interior controls are also inconsistent. Their stored phase enthalpies
and phase volumes do not reproduce the current DWSIM TP properties and fixed
control volumes. This independently confirms that the checkpoint is not
already on the conserved algebraic manifold.

## Scaling Result

DD-068 uses a node-local energy scale approximately equal to the magnitude of
that node's internal energy. The normalized L2 cost of moving `1000 BTU` is:

| Node | Energy scale, BTU | Normalized cost | Cost / median interior |
|---|---:|---:|---:|
| Top terminal | `8.5915e6` | `1.3548e-8` | `0.000418` |
| Tray 2 | `1.3361e5` | `5.6016e-5` | `1.726` |
| Feed tray 12 | `2.8911e5` | `1.1964e-5` | `0.369` |
| Tray 19 | `3.7134e5` | `7.2521e-6` | `0.224` |
| Bottom terminal | `3.2292e6` | `9.5900e-8` | `0.002956` |

The same physical energy move is therefore roughly `338` to `2395` times
cheaper at a terminal than at the median interior node. The DD-068 terminal
concentration cannot be interpreted as thermodynamic preference until this
weighting is corrected.

## Decision

Classification: `dd069_terminal_basis_or_volume_defect_found`.

Checkpoint repair is not yet retired because DD-069 found concrete defects.
It remains paused. Do not add hydraulics.

The next bounded correction must:

1. replace node-local energy scaling with a common physical energy scale, or
   otherwise prove an intentional neutral weighting;
2. give sump vapor space an explicit conserved vapor owner, or select and
   document a liquid-only sump topology that excludes that headspace from the
   UV target;
3. reconcile checkpoint `EL + EV` with live DWSIM phase enthalpy before
   converting it to conserved U;
4. rerun DD-067/DD-068 only after those corrections.

If the corrected redistribution remains large, pressure-discontinuous, or
non-robust, retire checkpoint projection and proceed to the direct conserved
steady-state formulation.

The DD-065 controller degree-of-freedom audit already passed and is not a
pending DD-069 item.

## Evidence

- `src/dynamic_distillation/terminal_energy_volume_audit_v1.py`
- `tools/audit_terminal_energy_volume_basis.py`
- `tests/test_terminal_energy_volume_audit_v1.py`
- `logs/terminal_energy_volume_basis_audit_20260717.json`
- `logs/terminal_energy_volume_basis_audit_20260717.md`
