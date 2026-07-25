# DD-094 Core V3 Reporting-Recovery Contract

Date: 2026-07-25

## Governance Exception

The user explicitly authorizes one successor campaign after DD-093 failed
solely in post-solve report assembly. DD-093 remains retired and its result
record remains unchanged.

DD-094 is permitted because the prior attempt produced no serialized endpoint
or scientific campaign decision. This exception does not relax any numerical,
physical, provider, or common-root gate.

## Allowed Change

Only scalar coordinate handling in `movement_by_family()` changes:

- product movement selects the integer `distillate` and `bottoms` indices;
- condenser-duty movement reads its integer index as a scalar;
- regression coverage directly exercises both paths.

No equation, coordinate, start, bound, scale, solver setting, tolerance,
provider rule, phase criterion, physical criterion, or hard stop changes.

## Frozen Campaign

DD-094 copies exactly from DD-093:

- all three 40-coordinate starts;
- the complete `40 x 40` Core V3 residual;
- physical and transformed bounds;
- residual and physical comparison scales;
- `least_squares(method="trf")` and all solver settings;
- both endpoint Jacobian steps and the `25%` spectrum-stability gate;
- provider provenance and independent PR/TP diagnostic rules;
- every residual, rank, condition, conservation, phase, geometry, bound,
  temperature-ordering, and common-root acceptance criterion.

The generated contract records a checksum over these mathematical fields so
identity with DD-093 is independently testable.

## Execution Rule

Commit and push this contract before execution. Then run it exactly once and
record the result without contract changes. A failure retires DD-094 without
another reporting repair, solver variation, or dynamic work. A full pass
authorizes only a structural dynamic-DAE contract, not integration.
