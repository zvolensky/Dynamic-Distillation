# DD-085 Energy-Owned Steady-Root Result

## Decision

DD-085 fails its frozen physical acceptance gate.

The failure is not numerical. All three precommitted starts converge to the
same essentially exact, full-rank, well-conditioned, conservative, interior
root. That common root violates the required terminal temperature ordering:

```text
T[reflux_drum]    = 166.130673 F
T[rectifying_tray] = 162.897548 F
difference          = +3.233125 F
```

The liquid reflux drum is hotter than the equilibrium stage supplying vapor
to an inventory-free total condenser while condenser duty is negative. The
root therefore fails the frozen physical gate.

Per the precommitted hard stop, the five-volume energy-owned steady
architecture is retired. No DD-086 solver tuning, continuation, wider bounds,
or operating-parameter variation is authorized.

## Frozen Execution

- Contract commit: `eaa7cc390a384b651afebdbc9cec5462db7d4846`
- Contract payload SHA-256:
  `c549bdb9a0f35546c0fee932b865c4b8610b0c6cc1f1d10aa51f7f2714d7b9c7`
- Solver: `scipy.optimize.least_squares(method="trf")`
- Jacobian: uncolored central difference, `h=1e-5`
- Endpoint audits: `h=1e-5` and `5e-6`
- Total campaign wall time: `101.486 s`
- Nonlinear campaign executions: `1`
- Dynamic integrations: `0`

The committed contract, workbook checksum, starts, bounds, scales, equations,
and solver settings were unchanged.

## Solver Result

| Start | Initial residual inf | Final residual inf | nfev / njev | Worst condition | Minimum bound distance |
|---|---:|---:|---:|---:|---:|
| canonical | `3.97863e-1` | `5.26888e-15` | `27 / 24` | `7.51535e2` | `1.82322e-1` |
| deterministic perturbation | `3.89121e-1` | `2.54594e-13` | `31 / 29` | `7.51535e2` | `1.82322e-1` |
| independent smooth seed | `4.85703e-1` | `2.88658e-15` | `40 / 38` | `7.51535e2` | `1.82322e-1` |

All three solvers terminated on `gtol`.

Pairwise maximum normalized physical-root differences are:

| Pair | Difference |
|---|---:|
| canonical / perturbation | `1.37124e-12` |
| canonical / smooth | `1.80885e-13` |
| perturbation / smooth | `1.55213e-12` |

The common-root gate therefore passes by more than four orders of magnitude.

## Residual Blocks

Canonical-start block norms show the complete reduction:

| Block | Initial | Final |
|---|---:|---:|
| Full phase equilibrium | `1.56468e-1` | `4.10783e-15` |
| Component balances | `1.91173e-1` | `5.26888e-15` |
| Energy balances | `7.45511e-2` | `2.62830e-15` |
| Francis hydraulics | `3.97863e-1` | `8.82134e-16` |
| Terminal amounts | `0` | `0` |

The endpoint Jacobian remains rank `37/37` at both finite-difference steps.
Its condition is `751.534`; the singular-value range is approximately
`0.00384405` to `2.88894`. There are no zero rows, zero columns, or
off-registry couplings.

## Common Root

Role order is reflux drum, rectifying tray, feed tray, stripping tray, and
combined reboiler/sump.

### Inventories and temperatures

| Role | Liquid amount (lbmol) | Temperature (F) | Residence time (s) |
|---|---:|---:|---:|
| Reflux drum | `1388.900` | `166.1307` | `570.09` |
| Rectifying tray | `30.3775` | `162.8975` | `22.73` |
| Feed tray | `44.0920` | `179.8992` | `13.20` |
| Stripping tray | `52.3600` | `191.6582` | `15.61` |
| Combined reboiler/sump | `794.000` | `206.2302` | `660.94` |

The three tray liquid heights are `0.3329`, `0.5103`, and `0.5472 ft`, all
below their tray spacings.

### Flows

```text
D = 2818.2023 lbmol/h
B = 4324.7717 lbmol/h

L[rectifying, feed, stripping]
  = [4810.1937, 12025.6087, 12076.0110] lbmol/h

V[bottom->stripping, stripping->feed, feed->rectifying, rectifying->drum]
  = [7751.2392, 7700.8369, 7628.3959, 8770.6823] lbmol/h
```

`D+B = 7142.9740 lbmol/h`, matching total feed through the component
balances.

### Liquid compositions

| Role | Propane | n-Butane | n-Pentane |
|---|---:|---:|---:|
| Reflux drum | `0.628884` | `0.352703` | `0.018412` |
| Rectifying tray | `0.420643` | `0.527227` | `0.052130` |
| Feed tray | `0.301072` | `0.602572` | `0.096356` |
| Stripping tray | `0.222033` | `0.659699` | `0.118268` |
| Combined reboiler/sump | `0.140740` | `0.687743` | `0.171518` |

### Vapor compositions

| Outlet role | Propane | n-Butane | n-Pentane |
|---|---:|---:|---:|
| Rectifying tray | `0.628884` | `0.352703` | `0.018412` |
| Feed tray | `0.497575` | `0.462752` | `0.039673` |
| Stripping tray | `0.391115` | `0.554740` | `0.054145` |
| Combined reboiler/sump | `0.267391` | `0.644051` | `0.088558` |

## Conservation and Bounds

- Component telescoping relative error: `2.29e-16`
- Energy telescoping relative error: `3.40e-17`
- Active transformed-coordinate bounds: none
- Minimum transformed bound distance: `0.182322`
- Property fallback: none
- Clipping or projection: none

The canonical campaign path recorded `15,640` live fugacity requests and
`841` liquid-density requests. The other starts also completed without
property failure.

## Interpretation

DD-085 answers the root-existence question more sharply than DD-082:

- releasing the four vapor links removes the previous component-balance
  residual floor;
- the system has a reproducible, isolated algebraic root;
- the root is not near a bound and is numerically benign;
- the remaining defect is physical ownership at the condenser boundary.

The fixed-duty, inventory-free total-condenser/liquid-drum closure can satisfy
material, energy, fugacity, terminal-amount, and Francis equations
simultaneously only by placing the product drum above the supplying stage
temperature for this case. This violates the frozen physical acceptance rule.

This result must not be converted into a pass by removing the temperature
ordering check or by retuning condenser duty. Such work would define a new
architecture or operating specification and is outside DD-085.

## Evidence

- `logs/dd085_energy_owned_steady_root_contract_20260718.json`
- `logs/dd085_energy_owned_steady_root_20260718.json`
- `logs/dd085_energy_owned_steady_root_20260718.md`
- `src/dynamic_distillation/core_v2/energy_owned_vapor_steady_solve_v1.py`
- `tools/run_core_v2_energy_owned_vapor_steady_root.py`
- `tests/test_core_v2_energy_owned_vapor_steady_solve_v1.py`

