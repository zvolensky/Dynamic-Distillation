# DD-232 Full-C3/C4 Dynamic Handoff Mapping

## Result

`full_c3c4_dynamic_handoff_mapping_passed`

The accepted DD-231 stationary root maps completely into the full controlled
dynamic ledger without a property call or timestep.

| Item | Count |
|---|---:|
| Stationary coordinates consumed | 160 |
| Component inventory states | 60 |
| Dynamic algebraic coordinates | 98 |
| Open-loop dynamic rows / unknowns | 158 |
| Controlled rows / unknowns | 162 |
| BDF2 history values | 164 |

The root's liquid amounts and compositions become component inventories. Its
temperatures, phase compositions, internal flows, bubble composition, and
condenser duty become dynamic algebraic coordinates. Distillate and bottoms
rates become the controller's initial product references.

Both component-inventory history levels repeat the accepted state exactly. PI
rates, PI memories, and product log ratios begin at zero, making the controller
handoff bumpless by construction.

## Deferred Live Values

Internal-energy history and geometry-derived terminal level setpoints require
thermodynamic properties. They are deliberately not guessed here. The live
audit must:

1. evaluate phase enthalpy with DWSIM;
2. evaluate liquid density with the aligned-PR smallest positive root;
3. reconstruct one internal energy per volume and copy it to both history levels;
4. derive both terminal levels from accepted inventories and frozen geometry;
5. use those exact levels as initial controller setpoints;
6. verify the complete zero-motion residual and leading Jacobian.

## Decision

One separately frozen full-column live zero-motion audit is authorized. A
timestep, controller advance, and dynamic integration remain unauthorized.

## Artifacts

- `logs/dd232_core_v3_full_c3c4_dynamic_handoff_20260815.json`
- `logs/dd232_core_v3_full_c3c4_dynamic_handoff_20260815.md`
- `tools/audit_core_v3_full_c3c4_dynamic_handoff.py`
- `tests/test_core_v3_full_c3c4_dynamic_handoff.py`
