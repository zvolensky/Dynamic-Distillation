# Core V3 Real-World Readiness Review

Date: 2026-08-16

## Executive summary

Core V3 is a strong reduced-order dynamic distillation model with disciplined numerical auditing, but it is not yet sufficiently rigorous for real-world dynamic simulation in the plant-engineering sense.

The project documentation repeatedly treats Core V3 as a bounded feasibility layer rather than a complete dynamic model. It shows strong solver discipline, provider ownership, and conservation checks, but it does not yet include the full physical closure that a real industrial dynamic column requires.

## Key conclusion

Core V3 is credible as a research-grade or reduced-order DAE model, but it is not yet a production-grade dynamic simulator.

## Why it is strong

The model shows clear evidence of engineering discipline:

- It has an explicit provider-governed architecture and ownership model in the DD-091 structural audit.
- It performs live residual and Jacobian audits with rank and conditioning checks.
- It enforces conservation and structural consistency in reduced dynamic DAE layers.
- It has a concrete backward-Euler implicit-step implementation and explicit solver contracts.

These are important strengths. The system is not a loose prototype; it is a carefully constrained model with explicit gates and acceptance logic.

## Why it is not yet real-world rigorous

The decisive limitation is that Core V3 explicitly omits resident vapor holdup and pressure-dynamic closure in its reduced dynamic layer.

The design documentation is explicit:

- Core V3 “prescribes pressure, neglects resident vapor holdup, and enforces all component fugacity equalities.”
- Pressure differential states, vapor holdup, pressure control, product control, and production-horizon integration remain unauthorized.
- The model is not yet claimed to establish production-horizon, controller, pressure-dynamic, or vapor-holdup acceptance.
- The architecture document states the current implementation does not yet complete the intended DAE structure, and that pressure-vapor-holdup closure remains an open issue.

This is not a minor simplification. It is a structural limitation.

## Why vapor holdup matters

For a real distillation column, vapor residence inventory is often a central dynamic state. It couples with:

- pressure-volume consistency,
- vapor traffic,
- equilibrium closure,
- density and compressibility,
- energy balance and phase redistribution.

If the model omits explicit vapor holdup, it cannot claim to represent the full dynamic column physics of an industrial unit.

## Assessment

Core V3 is rigorous enough for:

- reduced-order research,
- bounded DAE verification,
- short fixed-pressure open-loop studies,
- solver and conservation audits under controlled assumptions.

Core V3 is not yet rigorous enough for:

- general real-world dynamic simulation,
- production-grade column operation,
- pressure-coupled vapor inventory behavior,
- controller design for real plant operation,
- realistic startup/upset simulation without major architecture additions.

## Recommended interpretation

The correct interpretation is:

> Core V3 is a credible, audited reduced-order dynamic model with strong numerical hygiene, but it remains a controlled feasibility layer rather than a complete industrial dynamic simulator.

## Supporting evidence

- model_architecture.md
- dd_095_core_v3_dynamic_dae_contract_20260725.md
- dd_101_core_v3_pressure_layer_contract_20260725.md
- dd_100_core_v3_longer_open_loop_20260725.md
- requirements.md

The concrete code and equation changes required to close this gap are
documented in [core_v3_vapor_holdup_implementation_plan_20260819.md](core_v3_vapor_holdup_implementation_plan_20260819.md).

## Final verdict

Core V3 should be regarded as a valuable reduced-order dynamic framework and a strong numerical testbed, but not as a real-world dynamic simulation model until the following are added and accepted:

1. explicit vapor holdup closure,
2. coupled pressure-vapor-volume consistency,
3. controller architecture with manipulated and controlled variables,
4. production-scale validation,
5. initialization acceptance under full dynamic closure.

Until then, the model is best described as research-grade and dynamically bounded, not industrially rigorous.
