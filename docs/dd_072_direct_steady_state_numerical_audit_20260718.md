# DD-072: Direct Steady-State Numerical Audit

Date: 2026-07-18

## Purpose

DD-071 produced a square, structurally full-rank direct conserved
steady-state registry. DD-072 implements and audits the corresponding live
numerical residual. It evaluates residuals, conservation telescoping,
physical scaling, and numerical Jacobian rank. It does not take a Newton,
least-squares, line-search, continuation, optimization, or repair step.

## Direct Evaluation

The evaluator reconstructs the last liquid and vapor mole fraction as
`1-sum(first Nc-1)`. It does not clip, renormalize, or substitute an imported
profile when the reconstructed composition is invalid. A failure identifies
the node and phase.

For every registered two-phase node, live DWSIM PR supplies phase enthalpy,
liquid density, vapor compressibility, and a TP-flash K vector at the trial
temperature, pressure, and liquid composition. The evaluator directly forms:

- component inventory reconstruction;
- internal-energy reconstruction using `U=H-PV`;
- occupied-volume closure;
- logarithmic `y/(Kx)` equilibrium residuals;
- steady component and energy balances;
- Francis-weir liquid-flow equations;
- vapor pressure-drop equations;
- condenser, reflux-drum, and combined-bottom balances;
- level, pressure, and bottoms-composition specifications.

The feed enters the conserved tray balance as its external component vector
and total enthalpy rate. A separate feed phase split is algebraically
unnecessary for these total balances: flashing may redistribute the feed
between local phases, but it cannot change the injected components or
enthalpy. Local phase ownership is determined by the node equilibrium and
volume equations.

## Conservation Assembly

Every internal liquid or vapor enthalpy stream is constructed once, then
applied to its source and destination with opposite signs. All internal
component and energy terms therefore telescope independently of distance
from a solution.

At the ChemSep, bounded-perturbation, and checkpoint guesses:

- maximum component telescoping error is approximately `2e-16` relative;
- energy telescoping error is approximately `3e-16` relative or less;
- every internal enthalpy term appears exactly twice with opposite signs;
- no residual-evaluator safeguard is used.

## Numerical Results

| Guess | Scaled residual L2 | Scaled residual infinity norm | Rank at `h` | Rank at `h/2` |
|---|---:|---:|---:|---:|
| ChemSep | `2.04121` | `0.713344` | `281` | `281` |
| Perturbed ChemSep | `2.04933` | `0.713497` | `281` | `281` |
| Operational checkpoint | `5.15485` | `4.50650` | `281` | `281` |

The ChemSep residual is dominated by Francis liquid-hydraulic mismatch,
especially in the lower active section. The checkpoint residual is dominated
by reflux-drum equilibrium mismatch and also retains bottom volume and liquid
hydraulic mismatch. These are starting-point residuals, not solved results.

The scaled Jacobian condition estimates are approximately:

| Guess | `h` | `h/2` |
|---|---:|---:|
| ChemSep | `1.33e8` | `1.32e8` |
| Perturbed ChemSep | `7.01e8` | `2.42e9` |
| Checkpoint | `2.66e8` | `4.11e8` |

Rank is stable, but conditioning is not benign. DD-073 must use bounded
continuation and monitor conditioning rather than launching an unrestricted
monolithic Newton solve.

## Sparsity Verification

The colored finite-difference Jacobian uses `28` colors. An uncolored
ChemSep reference independently perturbed all `281` unknowns.

- uncolored numerical rank: `281`;
- unexpected numerical nonzeros outside the registry graph: `0`;
- maximum colored/uncolored difference on registered entries: `0`;
- structurally allowed entries numerically zero: `468`.

The registered graph is an upper bound because some reconstructed-component
and property dependencies can be inactive at a particular state. The zero
entries are reported and do not create a zero row, zero column, or rank loss.

## Decision

Classification: `dd072_numerical_audit_passed`.

DD-072 passes its numerical gate. It authorizes DD-073 to attempt a bounded,
staged continuation solve. It does not establish a solved initializer, local
closure tolerances, multi-start robustness, or dynamic usability.

DD-073 should retain the previously proposed order:

1. local thermo and equipment-volume closure;
2. steady material and energy balances;
3. liquid hydraulics;
4. vapor pressure-drop network;
5. terminal operating specifications.

Any loss of conservation, rank, property validity, or safeguard-free
evaluation stops DD-073 before dynamic testing.

## Evidence

- `src/dynamic_distillation/direct_steady_state_residual_v1.py`
- `tools/audit_direct_steady_state_numerics.py`
- `tests/test_direct_steady_state_residual_v1.py`
- `logs/direct_steady_state_numerics_20260718.json`
- `logs/direct_steady_state_numerics_20260718.md`
- `logs/direct_steady_state_numerics_20260718_jacobians.npz`
