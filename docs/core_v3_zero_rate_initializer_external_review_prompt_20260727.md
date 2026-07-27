# External Review Prompt: Core V3 Zero-Rate Initialization

You are reviewing an attached artifact package from a dynamic distillation modeling project. Please analyze the evidence and propose technically defensible solution options. Do not assume the project's current diagnosis is correct; independently inspect the governing equations, numerical formulation, contracts, results, and tests.

Begin with `README_REVIEW_FIRST.md`, which contains the complete problem statement. Use `MANIFEST.csv` to locate supporting artifacts. The most important raw evidence is DD-108 through DD-120, especially:

- DD-118 structural zero-rate feasibility;
- DD-119 live zero-rate residual and Jacobian audit;
- DD-120 two-start terminal-scaled zero-rate root campaign;
- the Core V3 conserved-`N/U`, pressure, zero-rate readiness, and zero-rate root source modules;
- the reduced-column workbook and Core V3 tests.

## Central Problem

The model is a generic five-volume, three-component C3/C4 splitter using conserved component inventories, conserved lower-volume internal energies, direct DWSIM Peng-Robinson properties, full fugacity equilibrium, Francis liquid hydraulics, energy-owned vapor flows, and algebraic pressure-drop equations.

A prior initializer produced a live equation-consistent state with nonzero conserved rates. Its first implicit step was physical and conservative but had a real startup transient. A successor then attempted to find an exact zero-rate state.

The zero-rate DAE core is structurally `46 x 46`. The live DAE-only Jacobian is formally rank `46/46` but extremely ill-conditioned (`2.54e13` to `3.76e13`), with two apparent near-scale freedoms. Adding fixed reflux-drum and reboiler/sump total-holdup rows creates a `48 x 46` residual and improves conditioning to roughly `5.6e3`.

In DD-120, two independently frozen starts converged to the same physical least-squares endpoint within `1.35e-9`. Both terminal holdup rows closed below `7.04e-12`, and every gate except exact DAE residual closure passed. The DAE residual stopped at `2.4486e-3`, versus the required `1e-8`, with left-null projection `7.6737e-3`.

The current project interpretation is that the inherited terminal holdups are incompatible with exact zero rate under the frozen equations and operating specifications. Treat this as a hypothesis supported by evidence, not as a theorem.

## Review Tasks

### 1. Independently diagnose the failure

Determine whether DD-120 most likely represents:

- incompatible terminal inventory specifications;
- an over-specified steady-state problem;
- incorrect ownership of a terminal mass, energy, volume, pressure, or product equation;
- a hidden gauge freedom handled incorrectly;
- an equation implementation defect;
- poor residual scaling or finite-difference contamination;
- a local least-squares minimum despite an attainable exact root elsewhere;
- or a physically valid indication that exact zero rate is not appropriate for this operating specification.

Support the diagnosis with specific file, function, equation-row, and result-field references from the package. Distinguish confirmed facts, strong inferences, and unresolved possibilities.

### 2. Perform an equation/specification degree-of-freedom review

Audit the ownership and independence of:

- all five component balances;
- all five energy balances and storage definitions;
- four full phase-equilibrium blocks;
- condenser saturation closure;
- three Francis liquid-flow equations;
- four vapor pressure-drop equations;
- energy-owned vapor links;
- reflux, distillate, bottoms, feed, reboiler duty, condenser duty, and top-pressure specifications;
- reflux-drum and reboiler/sump inventories or levels.

Explain which quantities should be states, algebraic unknowns, operating specifications, controller setpoints, or diagnostics at steady state and during dynamic initialization.

Specifically decide whether terminal holdups are:

1. true free initial conditions;
2. algebraic scale or gauge selections;
3. steady-state constraints that require level-control equations and manipulated variables;
4. or quantities already determined elsewhere by the current equations.

### 3. Rank solution options

Evaluate at least these options, plus any better alternative you identify:

1. **Accept a nonzero-rate consistent initializer.** Use the DD-114-type state, then manage and validate the physical startup transient with timestep refinement and a dynamic acceptance gate.
2. **Reformulate terminal ownership.** Remove fixed terminal holdups from the zero-rate root and introduce physically explicit drum/sump geometry, level setpoints, controllers, and manipulated-variable equations.
3. **Change steady operating specifications.** Release an appropriate flow, duty, reflux, product, or pressure specification so terminal levels can be controlled without over-specification.
4. **Solve the DAE-only zero-rate system.** Treat terminal inventory scales as gauges or continuation parameters, then independently assess the resulting terminal holdups and physical uniqueness.
5. **Use pseudo-transient or full implicit continuation.** Apply it only if the equation set is first shown to be physically well posed, and explain how it would distinguish infeasibility from slow numerical progress.
6. **Revise the requirement for exact zero residual/rate.** Define a physically meaningful dynamic-readiness criterion if exact steady initialization is unnecessary or unattainable.

For each option, report:

- physical justification;
- equations or specifications changed;
- expected benefits;
- numerical and modeling risks;
- implementation effort;
- evidence that would falsify the option;
- whether it preserves genericity and avoids hardcoded interior stages.

### 4. Recommend one next action

Recommend the smallest decisive next step. It must answer a clearly stated question and must not become an open-ended tuning campaign.

Define before execution:

- the exact variables and residual rows;
- any released or added specification and its physical owner;
- solver and derivative method;
- starting states;
- physical, conservation, rank, condition, residual, robustness, and efficiency gates;
- the maximum number of permitted executions;
- pass, fail, and hard-stop criteria.

If no further numerical experiment is justified, say so and recommend the architectural change directly.

### 5. Assess the requirements

Review `docs/requirements.md` and advise whether exact zero conserved rates and residuals should remain mandatory for initialization. Propose replacement requirement language if dynamic consistency with bounded nonzero startup rates is more appropriate.

## Constraints

- Preserve exact component and energy conservation.
- Preserve direct, declared DWSIM provider ownership without fallback or mixed thermodynamic bases.
- Preserve generic physical-role topology; do not hardcode an interior stage number.
- Do not use clipping, profile forcing, arbitrary transfer terms, flow caps, or relaxation to conceal an incompatible model.
- Do not recommend changing tolerances merely to declare the existing residual floor acceptable.
- Do not assume a more powerful solver can fix an over-specified or physically inconsistent equation set.
- Separate initializer design, steady-state specification, dynamic equations, and controller design.
- Treat prior campaign contracts as immutable evidence; do not propose rerunning a failed frozen campaign under a new label.

## Required Response Format

1. **Executive conclusion**: repairable as formulated, repairable after architectural change, or not presently well posed.
2. **Most likely root cause**: with confidence level and evidence citations.
3. **Degree-of-freedom table**: unknowns, equations, specifications, and owners.
4. **Findings**: ordered by severity and certainty.
5. **Ranked solution options**: comparative table with benefits, risks, and effort.
6. **Recommended next action**: exact bounded protocol and hard stop.
7. **Requirements changes**: proposed wording.
8. **Open questions or missing evidence**.

Be candid. A recommendation to stop pursuing exact zero-rate initialization is acceptable if the evidence supports it. Conversely, if you identify a concrete equation or ownership defect, explain precisely how to test and correct it before any broader solver work.
