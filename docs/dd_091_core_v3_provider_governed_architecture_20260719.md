# DD-091 Core V3 Provider-Governed Architecture

Date: 2026-07-19

## Decision

DD-091 passes its structural gate.

The project now has a separate architecture identity:

> Core V3 - Provider-Governed Energy-Owned Equilibrium Architecture

Core V3 is not a corrected DD-088 run or a revived Core V2 model. It retains
the physical equation ledger that produced a valid `40 x 40` structure, but
it adopts the prospective provider ownership established by DD-090. It does
not import a Core V2 residual evaluator or DD-088 acceptance status.

## Scope

DD-091 is structural only. It performed:

- namespace and version definition;
- unknown and residual registration;
- physical-owner and provider-authority tagging;
- sparse dependency and structural-rank audit;
- exact internal component and energy cancellation checks;
- prohibited dependency and fallback checks;
- prospective numerical acceptance-rule registration;
- unit tests of both accepted and deliberately invalid registries.

DD-091 performed no:

- DWSIM property evaluation;
- independent Peng-Robinson evaluation;
- column residual evaluation;
- nonlinear solve;
- import or acceptance of the DD-088 root;
- mass-matrix derivation;
- dynamic integration.

## Physical Ledger

Core V3 retains five liquid inventory locations:

1. reflux drum;
2. rectifying tray;
3. feed tray;
4. stripping tray;
5. combined reboiler/sump.

It also retains:

- an inventory-free saturated-liquid total condenser;
- prescribed ordered pressure;
- prescribed feed, reflux, and reboiler duty;
- solved condenser duty `Q_C`;
- four independent vapor links owned by simultaneous energy balances;
- full component fugacity equilibrium at four column vapor outlets;
- full bubble-fugacity equilibrium at the condenser;
- Francis-only interior liquid hydraulics;
- specified terminal liquid amounts;
- solved distillate and bottoms rates;
- exact internal material and energy telescoping.

### Unknowns

| Block | Count |
|---|---:|
| Liquid amounts | 5 |
| Independent liquid compositions | 10 |
| Temperatures | 5 |
| Column vapor compositions | 8 |
| Francis liquid flows | 3 |
| Energy-owned vapor links | 4 |
| Terminal product flows `D/B` | 2 |
| Condenser incipient-vapor coordinates | 2 |
| Solved condenser duty `Q_C` | 1 |
| **Total** | **40** |

### Residuals

| Block | Count |
|---|---:|
| Column full-fugacity equilibrium | 12 |
| Component balances | 15 |
| Energy balances | 5 |
| Francis hydraulics | 3 |
| Terminal amount specifications | 2 |
| Condenser bubble fugacity | 3 |
| **Total** | **40** |

## Provider Authority

| Quantity | Authority | Role |
|---|---|---|
| Stage fugacity equilibrium | DWSIM direct imposed-phase fugacity | Governing equation |
| Condenser bubble equilibrium | DWSIM direct imposed-phase fugacity | Governing equation |
| Liquid/vapor enthalpy | Declared DWSIM phase-enthalpy path | Governing balance |
| Liquid density | Declared DWSIM liquid-density path | Francis geometry |
| Bubble temperature and incipient vapor | DWSIM direct imposed-phase fugacity | Governing state |
| Stable phase | DWSIM TP flash | Diagnostic gate |
| Vapor fraction | DWSIM TP flash | Diagnostic gate |
| Flash `x/y/K` | DWSIM TP flash | Flash-basis diagnostic |
| Lever-rule closure | DWSIM TP flash | Diagnostic gate |
| Independent PR bubble | Parameter-aligned independent PR | Validation only |

All production property paths fail explicitly if their declared interface is
unavailable. No provider may silently substitute for another.

## Structural Results

The committed DD-091 audit reports:

| Check | Result |
|---|---:|
| Unknowns/residuals | `40 / 40` |
| Structural rank | `40` |
| Structural nullity | `0` |
| Zero residual rows | `0` |
| Zero unknown columns | `0` |
| Full stage-fugacity rows | `12` |
| Condenser bubble-fugacity rows | `3` |
| Energy-owned vapor links | `4` |
| Francis-owned liquid flows | `3` |
| Component telescoping | Pass |
| Energy telescoping | Pass |
| Fixed `Q_C` parameter | Absent |
| TP flash in governing residuals | Absent |
| Independent PR in production residuals | Absent |
| Mixed `K_flash*z` dependency | Absent |
| Interface fallback | Absent |
| Imported DD-088 acceptance | Absent |
| Core V2 residual owner import | Absent |

The exact global forms after internal-stream cancellation are:

```text
component: F_k - D*x_D,k - B*x_B,k
energy:    H_feed + Q_R + Q_C - D*h_D - B*h_B
```

## Prospective Numerical Gates

The following rules are registered now but were not evaluated by DD-091:

- direct stage and condenser fugacity residual infinity norm below `1e-10`;
- independent PR bubble-temperature difference below `1e-3 F`;
- independent PR incipient-vapor composition difference below `1e-6`;
- TP flash does not classify the directly solved condenser state as stable
  vapor;
- TP flash vapor fraction at that boundary is at most `1e-3`;
- TP flash reconstructs `y_flash` from `K_flash*x_flash` below `1e-12`;
- TP flash lever-rule closure is below `1e-12`.

No direct-bubble-`y` versus TP-flash-`y` equality gate exists. Flash `K` is
defined only on the corresponding `x_flash/y_flash` basis.

## Authorization

DD-091 authorizes exactly one next activity:

> DD-092 - Core V3 live residual, provider-ownership, conservation, and
> Jacobian audit.

DD-092 must be precommitted and must evaluate the new Core V3 residual under
the DD-090 authority rules. It must not repeat the discredited mixed-basis
test.

DD-091 does not authorize:

- a nonlinear root campaign;
- acceptance or import of the DD-088 root;
- a dynamic mass matrix;
- dynamic integration.

Primary evidence:

- `src/dynamic_distillation/core_v3/provider_governed_registry_v1.py`
- `tools/audit_core_v3_provider_governed_registry.py`
- `tests/test_core_v3_provider_governed_registry_v1.py`
- `logs/dd091_core_v3_provider_governed_structural_20260719.json`
- `logs/dd091_core_v3_provider_governed_structural_20260719.md`
