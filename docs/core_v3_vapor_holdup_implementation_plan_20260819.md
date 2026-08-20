# Core V3 Vapor-Holdup Implementation Plan

Date: 2026-08-19

## Purpose

This document translates the Core V3 vapor-holdup gap into specific code and model changes. It is an implementation plan, not evidence that the vapor-holdup extension has already been implemented or validated.

The current Core V3 dynamic layer contains algebraic vapor compositions and energy-owned vapor-link flow rates, but it does not contain conserved resident vapor inventory. The relevant current structures are:

- `src/dynamic_distillation/core_v3/provider_governed_residual_v1.py`
- `src/dynamic_distillation/core_v3/dynamic_dae_contract_v1.py`
- `src/dynamic_distillation/core_v3/dynamic_dae_numerical_audit_v1.py`
- `src/dynamic_distillation/core_v3/implicit_step_v1.py`
- `src/dynamic_distillation/core_v3/pressure_layer_contract_v1.py`
- `src/dynamic_distillation/core_v3/pressure_implicit_step_v1.py`

## Implementation status

DD-236 implements the first two property-free steps in a separately versioned successor module:

- `src/dynamic_distillation/core_v3/vapor_holdup_dae_contract_v1.py`
- `tools/audit_core_v3_vapor_holdup_dae_contract.py`
- `tests/test_core_v3_vapor_holdup_dae_contract_v1.py`

Completed:

- explicit vapor-bearing ownership for every physical control volume;
- required positive volume declaration with no default geometry;
- conserved `N_L[j,k]` and `N_V[j,k]` state ledgers;
- inventory-derived vapor composition;
- separate liquid/vapor balances and cancelling phase transfer;
- property-free vapor EOS, pressure-drop, pressure-anchor, and two-phase energy ownership;
- full structural rank for both five-volume (`63 x 63`) and 20-volume C3/C4 (`258 x 258`) systems.

Still pending:

- complete coupled fugacity/EOS/component/energy/hydraulic/pressure residual;
- consistent root construction, implicit stepping, and dynamic validation.

DD-237 completes the physical geometry mapping:

- real workbook tray area and spacing determine tray gross capacity;
- horizontal reflux-drum dimensions and hemispherical heads determine drum capacity;
- vertical sump dimensions plus the reboiler vapor extension determine bottom capacity;
- endpoint free vapor volume is gross capacity minus live liquid displacement;
- all 20 C3/C4 volumes map exactly once and retain structural rank `258/258`.

DD-238 completes live property and initial vapor-state reconstruction:

- aligned parameter-specific PR owns liquid density;
- DWSIM owns vapor compressibility and liquid/vapor enthalpy;
- free volume includes live liquid displacement;
- `N_V`, component vapor inventory, and `U_L+U_V` are reconstructed at the accepted root;
- all 80 expected property calls are recorded without fallback;
- the 20-volume EOS closes to `1.122839e-16` relative error;
- resident vapor is `473.563386 lbmol`, so its omission is materially significant.

The complete two-phase component and energy residual remains pending. No solve,
timestep, or dynamic integration is authorized.

DD-239 completes the separately testable conservation core:

- liquid and vapor transports have separate ledgers;
- positive `M_VL` is defined as vapor-to-liquid transfer;
- the transfer cancels exactly when phase equations are summed;
- the accepted stationary root closes separate phase balances and two-phase
  energy to the declared tolerances;
- global component and energy transport telescope to the external streams and
  duties.

Full residual assembly remains pending because fugacity, EOS, Francis,
pressure-drop, and pressure-anchor rows must still be joined to this
conservation core under one coordinate and scaling contract.

The accepted Core V3 V1 implementation remains unchanged and is now explicitly classified as reduced order.

## Current gap

The current state representation has:

- liquid component inventory `N[j,k]`;
- liquid composition `x[j,k]` derived from liquid inventory;
- algebraic vapor composition `y[j,k]`;
- algebraic vapor-link flow `V[j]`;
- fixed or algebraic pressure, depending on the contract;
- liquid internal-energy storage only.

It does not have:

- resident vapor component inventory `N_V[j,k]`;
- vapor total holdup `N_V[j]`;
- vapor volume and EOS closure;
- vapor internal-energy storage;
- vapor component balances;
- interphase mass-transfer ownership;
- pressure ownership that is consistent with vapor inventory and volume.

Consequently, changing vapor flow currently changes transport without storing the vapor material that resides in a tray or vessel.

## Recommended modeling choice

The extension should use conserved vapor component inventories as the canonical vapor state:

```text
N_L[j,k]   liquid component inventory
N_V[j,k]   vapor component inventory
N_T[j,k] = N_L[j,k] + N_V[j,k]
```

Derived quantities are:

```text
a_V[j] = sum_k N_V[j,k]
y[j,k] = N_V[j,k] / a_V[j]
```

Positive exponential coordinates should be used for both `N_L` and `N_V` during implicit stepping. This avoids independently integrating a total vapor amount and a composition vector that can lose consistency.

The implementation must choose one phase-transfer family before coding:

1. **Equilibrium-stage DAE:** solve an algebraic UV/volume/equilibrium block for temperature, pressure, phase split, `x`, and `y`; or
2. **Rate-based model:** add explicit interphase mass- and heat-transfer laws.

The existing Core V3 design is equilibrium-stage based. The first vapor-holdup successor should therefore use an equilibrium-stage DAE, with rate-based transfer explicitly out of scope unless a separate architecture is approved.

## Required code changes

### 1. Extend topology and operating specification

Update `provider_governed_registry_v1.py` and the operating specification in `provider_governed_residual_v1.py`.

Add explicit ownership for:

- vapor-bearing tray/control volumes;
- reflux-drum vapor volume, if present;
- condenser vapor-side volume, if present;
- terminal vapor outlet and vent paths;
- vapor volume geometry or declared free volume;
- vapor pressure anchor or pressure-control boundary.

The existing `ColumnTopology.vapor_links` describes interstage transport links only. It must not be treated as resident vapor storage. Add a separate topology declaration for vapor control volumes and terminal vapor connections.

The operating specification must carry, at minimum:

```text
vapor_volume_ft3[j]
vapor_control_volume_ids
vapor_outlet_ids
vapor_holdup_reference_lbmol[j,k]
pressure_owner
vapor_volume_model
```

The specification must reject a vapor-holdup run that has vapor inventory but no declared volume and pressure ownership.

### 2. Extend physical state and coordinate layout

Update `NumericalReference`, `CoordinateLayout`, and `PhysicalState` in `provider_governed_residual_v1.py`.

Add:

```text
vapor_moles_lbmol: ndarray[J,C]
```

The existing `vapor_mole_fraction` field should become a derived field for conserved-inventory mode, or be renamed to make clear when it is an algebraic trial variable. It must not remain an independently solved composition if it can disagree with `N_V`.

Update:

- `coordinate_layout()`;
- `decode_coordinates()`;
- `encode_state()`;
- `dynamic_algebraic_indices()`;
- `_state_from_inventory_and_algebraic()`.

The coordinate layout must include positive vapor-inventory coordinates, for example:

```text
log_NL[j,k]
log_NV[j,k]
```

The endpoint decoder must reconstruct `y` from `N_V` and reject zero, negative, nonfinite, or compositionally invalid vapor inventory.

### 3. Add vapor property evaluation and storage

Update `LiveProperties` and `_evaluate_properties()` in `provider_governed_residual_v1.py`.

Add provider-owned vapor quantities for every vapor-bearing volume:

```text
vapor_density or vapor_molar_volume
vapor_compressibility_factor Z_V
vapor_enthalpy
vapor_internal_energy
vapor_volume residual
```

The governing property provider must expose a declared path for vapor compressibility and vapor-phase enthalpy. Ideal-gas substitution, TP-flash substitution, stale values, or fallback providers must remain prohibited in the governing residual.

For each vapor volume, evaluate a thermodynamic closure such as:

```text
V_free[j] - N_V[j] * Z_V[j] * R * T[j] / P[j] = 0
```

with a consistent unit conversion. If vessel geometry includes liquid displacement, use:

```text
V_free[j] = V_shell[j] - V_liquid[j](N_L, x, rho_L)
```

The liquid and vapor volume equations must have one owner. They must not independently prescribe both pressure and vapor inventory without a compatible EOS residual.

### 4. Replace liquid-only component balances with total phase balances

Update `_component_balances()` and the dynamic residual assembly.

For every component and control volume, the governing conservation equation must include both phase inventories:

```text
dN_L[j,k]/dt + dN_V[j,k]/dt
    = inflow_L[k] + inflow_V[k]
    + feed[k] - product[k]
```

If phase transfer is represented explicitly, add equal and opposite transfer terms:

```text
dN_L[j,k]/dt = liquid transport + feed/product + M_VL[j,k]
dN_V[j,k]/dt = vapor transport              - M_VL[j,k]
```

If the equilibrium-stage formulation eliminates `M_VL`, the algebraic phase-equilibrium and volume/energy equations must determine the phase split without silently deleting vapor accumulation. The sum of the liquid and vapor equations must recover the exact total component balance.

The telescoping audit must separately report:

- liquid-phase transport cancellation;
- vapor-phase transport cancellation;
- interphase transfer cancellation;
- global total-component conservation.

### 5. Add vapor energy storage and phase-energy closure

Update `_energy_balances()`, the storage functions in `dynamic_dae_numerical_audit_v1.py`, and `governing_storage_vector()` in `implicit_step_v1.py`.

The stored energy for each control volume must include both phases:

```text
U_total[j] = U_L[j] + U_V[j]
U_L[j] = N_L[j] * u_L(T,P,x)
U_V[j] = N_V[j] * u_V(T,P,y)
```

The dynamic energy equation must use either:

```text
dU_total[j]/dt = enthalpy inflow - enthalpy outflow + duties
```

or an exactly equivalent coupled differential/algebraic formulation.

The current liquid-only `saturated_storage_vector()` and `governing_storage_vector()` cannot be reused unchanged. Their replacements must:

- include vapor enthalpy/internal energy;
- include pressure work consistently;
- include phase-transfer latent energy;
- use the same provider basis for residual and storage;
- support pressure movement if pressure becomes algebraic or differential.

A fixed-temperature or fixed-pressure phase redistribution that changes phase totals without this energy closure must remain diagnostic-only.

### 6. Extend the structural DAE contract

Update `dynamic_dae_contract_v1.py` and successor pressure contracts.

The current contract registers `N[j,k]` derivatives but no vapor-inventory derivatives. Add:

```text
dN_V[j,k]/dt
```

and the associated state coordinates:

```text
N_V[j,k]
```

Add rows for:

- vapor component balances;
- phase-transfer or equilibrium phase-allocation closure;
- vapor volume/EOS closure;
- vapor energy storage or total-energy closure;
- terminal vapor inventory balances;
- vent/condensation/reflux vapor boundary equations where applicable.

The contract must publish new counts generically in component count and topology. For a simple model with one liquid and one vapor component inventory per phase, the number of differential inventory states approximately doubles from `J*C` to `2*J*C`; exact counts depend on whether phase allocation and energy are represented as differential or algebraic variables.

The structural audit must reject:

- vapor state columns with no balance row;
- vapor balance rows with no owner;
- duplicated pressure or volume owners;
- independently solved `y` inconsistent with `N_V`;
- phase transfer appearing in only one phase balance;
- vapor holdup present in state but absent from energy storage.

### 7. Make pressure ownership physically consistent

Update `pressure_layer_contract_v1.py`, `pressure_layer_numerical_v1.py`, and `pressure_implicit_step_v1.py`.

The current pressure layer adds algebraic pressure-drop equations but deliberately reports `explicit_vapor_inventory_present = False`. That gate must become a required positive feature for the rigorous successor.

The successor must select one pressure model:

- algebraic pressure from vapor inventory, volume, EOS, and pressure-drop equations; or
- differential pressure from vapor compressibility/volume dynamics with an algebraic EOS closure.

It must not prescribe an interior pressure profile while also integrating vapor holdup.

Pressure residuals must include:

```text
EOS/volume closure
pressure-drop closure
pressure-boundary or controller closure
```

The pressure-layer evaluator must use the endpoint vapor inventory and endpoint pressure consistently. The current endpoint storage calculation in `pressure_implicit_step_v1.py` must include pressure-dependent vapor storage and must not reuse a fixed-pressure liquid-only gradient.

### 8. Extend implicit stepping

Update `implicit_step_v1.py` and `pressure_implicit_step_v1.py`.

A backward-Euler endpoint must advance both phase inventories:

```text
N_L,next = N_L,previous * exp(dt * nu_L / N_L,previous)
N_V,next = N_V,previous * exp(dt * nu_V / N_V,previous)
```

The physical component rates must be reconstructed from exact endpoint differences for both phases. The residual must enforce the coupled phase equations at the same endpoint.

The solver coordinate vector, sparsity pattern, colored Jacobian, rank audit, and condition audit must all include the new vapor-rate and vapor-algebraic dependencies.

The step evaluator must report:

- liquid inventory change;
- vapor inventory change;
- total inventory change;
- vapor-volume change;
- pressure change;
- liquid and vapor energy storage change;
- exact component and energy kinematics.

### 9. Extend initialization and restart handling

Update the Core V3 initializer, zero-time audit, serialized state schema, and any Excel/restart adapters that feed Core V3.

Initialization must accept or reconstruct:

- vapor component inventory;
- vapor composition derived from that inventory;
- vapor temperature and pressure;
- vapor volume and compressibility;
- vapor internal energy;
- terminal vapor states;
- consistent vapor transport and phase-transfer values.

An external steady-state profile must be treated as a seed only. The initializer must solve the coupled liquid/vapor algebraic manifold and report movement in:

```text
Delta N_L
Delta N_V
Delta U_L
Delta U_V
Delta P
Delta T
```

A zero-time audit must prove that every vapor state has both a component balance and an energy/volume closure before permitting a timestep.

### 10. Extend reporting and provenance

Add vapor-specific fields to result records and audit logs:

```text
vapor_inventory_lbmol[j,k]
vapor_holdup_lbmol[j]
vapor_composition[j,k]
vapor_volume_ft3[j]
vapor_pressure_psia[j]
vapor_Z[j]
vapor_energy_BTU[j]
phase_transfer_lbmolph[j,k]
vapor_balance_residual[j,k]
vapor_volume_residual[j]
```

Provider-call provenance must distinguish vapor density, vapor enthalpy, vapor compressibility, fugacity, and any phase-transfer property calls. The report must identify whether vapor holdup was dynamically solved, algebraically reconstructed, or disabled as an explicitly declared reduced-model option.

## Recommended implementation order

1. Freeze the vapor control-volume topology and pressure/volume ownership.
2. Add property-free `N_V` state, balance, and structural-rank contract.
3. Add live vapor volume/EOS and vapor-property provider ownership.
4. Add two-phase component and total-energy residuals.
5. Add pressure-enabled consistent initialization.
6. Add one-step stationary and disturbance refinement audits.
7. Add short open-loop trajectories with vapor holdup.
8. Add controllers only after the uncontrolled vapor-pressure model passes.
9. Validate against an external dynamic benchmark with reproducible vapor inventory and pressure traces.

## Current progress through DD-244

- [x] Freeze vapor control-volume topology and pressure/volume ownership (`DD-236`).
- [x] Map physical tray, drum, sump, and reboiler geometry (`DD-237`).
- [x] Reconstruct live vapor inventory, EOS, and two-phase energy (`DD-238`).
- [x] Prove separate liquid/vapor conservation and phase-transfer cancellation (`DD-239`).
- [x] Assemble the complete 258-row implicit endpoint residual (`DD-240`).
- [x] Pass the two-step 258-row endpoint Jacobian audit (`DD-241`).
- [x] Define a true stationary initializer with terminal level closure (`DD-242`).
- [x] Assemble its complete 260-row live residual (`DD-243`).
- [x] Pass the two-step stationary Jacobian audit (`DD-244`).
- [x] Execute one frozen bounded stationary root campaign (`DD-245`).
- [x] Map an accepted root into the successor dynamic history/state schema (`DD-246`).
- [x] Pass stationary hold and refined moving-step gates (`DD-248` and `DD-249`).
- [x] Run a short open-loop trajectory before adding controllers (`DD-250`).
- [x] Qualify a persistent parallel Jacobian path (`DD-251`).
- [x] Integrate and qualify the persistent parallel path across repeated vapor-holdup steps; rejected on trajectory speed (`DD-254`).
- [x] Test one fresh Jacobian per root; scientifically clean but rejected by the frozen endpoint-equivalence gate (`DD-255`).
- [x] Test one fresh Jacobian plus secant updates; aborted on a same-coordinate callback and retired (`DD-256`).
- [ ] Choose between the accepted slower serial dynamics and a separately scoped derivative/solver redesign.

The stationary initializer solves distillate and bottoms rates so the reflux
drum and sump remain at their geometry-derived target inventories. This is not
controller execution; it is the steady algebraic closure required to select a
unique operating point. The pressure profile, vapor traffic, both phase
inventories, phase transfer, temperatures, condenser duty, and product rates
remain coupled solve quantities.

DD-245 accepted the full stationary root at a scaled residual of `3.05e-11`.
The endpoint remains full rank and physical, and the complete campaign required
23.437 seconds. The next work is mapping only: no new physics, root solve, or
time advance is needed to define the successor's current state and BDF2 history.

DD-246 maps all root values without property calls. The only deferred data are
the current/previous total two-phase energies, which must be reconstructed from
the same live provider basis used by the root before a zero-motion residual can
be evaluated.

DD-247 completes that reconstruction and proves exact zero inventory motion at
the accepted root. The full implicit Jacobian is rank 258 with condition about
`1.14e7`. One frozen stationary hold step is next; a disturbance remains
unauthorized until that step is accepted without state movement.

DD-248 accepts that hold step with exactly zero movement. DD-249 now freezes one
small feed disturbance and compares one `0.25 s` endpoint against two
successive `0.125 s` endpoints. A trajectory remains unauthorized until this
local response is conservative, physical, and timestep-consistent.

DD-249 passes that moving comparison. The full and refined paths both reproduce
the exact imposed inventory accumulation, remain full rank and physical, and
agree closely in every frozen comparison. One short open-loop trajectory may
now be frozen; controllers remain out of scope.

DD-250 freezes that trajectory at one simulated second, with four nominal and
eight refined endpoints. This deliberately tests repeated stepping and
timestep consistency without yet spending time on a process-scale run.

DD-250 passes scientifically, but 598,320 provider calls and 145.5 seconds of
solver wall per simulated second are too expensive for useful duration. The
call ledger identifies Jacobian perturbations as the dominant cost. Reuse the
existing persistent parallel Jacobian architecture next; do not extend the
serial trajectory or add controllers yet.

DD-251 freezes the first qualification benchmark: one serial and one
eight-worker matrix at the accepted DD-249 moving endpoint. Passing permits
parallel step-solver integration; failure retains the serial scientific path
and requires a different performance strategy.

DD-251 passes with exact serial/parallel matrix equality and `3.93x` matrix
speedup. The eight-worker pool must remain alive across roots to amortize its
`11.69 s` startup. Integrate it next, then address Jacobian count and nonlinear
iteration count separately.

DD-252 freezes one serial/parallel moving-root comparison. It tests the actual
trust-region solve, not only a standalone matrix, while explicitly prohibiting
state acceptance or a second endpoint.

DD-252 proves exact solver-level equivalence and a `1.65x` speedup but fails two
mis-scoped accounting gates. DD-253 is a zero-call adjudication: it checks all
eight workers on governing tasks and exact total-work parity without repeating
the solve.

DD-253 passes without live calls. Persistent parallel stepping is now
authorized for a separately frozen trajectory. After integration, the next
performance target is fewer Jacobian builds and nonlinear iterations, because
parallel execution reduces wall time but not the 41,760-call root workload.

DD-254 freezes four serial and four persistent-parallel `0.25 s` endpoints over
the same one-second disturbed interval. One eight-worker pool remains alive
across all roots, and every worker receives the complete accepted endpoint as
the next reference basis. Passing proves that parallelism survives repeated
state handoff and gives a meaningful trajectory-level wall-time benefit. It
does not solve the remaining call-count problem; that requires fewer Jacobian
builds or a derivative strategy change after DD-254.

DD-254 preserves the science exactly but rejects the persistent pool: four
parallel steps take `31.04 s` after startup versus `27.17 s` serial, despite
identical work and endpoints. The dominant cost is now explicit: 25 Jacobian
builds account for 168,000 of 174,480 calls. Stop process-parallel variants.
Test one fresh Jacobian held fixed within each endpoint root before considering
automatic differentiation or a different nonlinear solver.

DD-255 freezes the first bounded call-count experiment. It computes one fresh
full Jacobian at each new endpoint and reuses it only during that endpoint's
nonlinear iterations. The saved DD-254 serial coordinates are the numerical
reference. Failure ends fixed-Jacobian reuse; success authorizes integration of
this modified-Newton step path before any longer physical trajectory.

DD-255 cuts calls by 80.3% and wall by 53.9%, but its maximum transformed
endpoint difference is `1.184879e-9` against the frozen `1e-9` requirement.
The miss is confined to condenser duty and is physically tiny, but the method
is not accepted. Do not tune the threshold or add fixed-refresh schedules. One
standard Broyden-update experiment is the final low-cost reuse option before a
larger derivative or nonlinear-solver redesign.

DD-256 freezes the standard good-Broyden update with no tuning choices. One
finite-difference matrix is built at the start of each root; later matrix
requests use only the observed coordinate and residual changes. The unchanged
DD-254 endpoint reference and DD-255 efficiency gates decide the result. This
is the final bounded low-cost reuse test.

DD-256 stops before an endpoint when SciPy requests another Jacobian at the
same point and the mandatory secant has zero length. The no-skip hard stop is
applied, so there is no corrected Broyden rerun. The accepted full-refresh
serial solver is retained. The next project decision is whether to spend the
known wall time on a modest physical trajectory or begin a separate derivative
and nonlinear-solver redesign.

DD-257 chooses the accepted serial path for one bounded five-second extension.
It requires the first second to replay DD-254 and all 20 endpoints to remain
full-rank, conservative, physical, and provider-clean. A final 20-volume profile
is mandatory. This spends known wall time to advance dynamic validation while
leaving any broader derivative redesign as a later, separately scoped project.

DD-257's solve returns, but its post-solve profile writer fails on the actual
tuple representation of vapor links before evidence is saved. The campaign is
unclassified and is not rerun. A corrected successor must first exercise the
reporter against all 20 topology volumes without property or solver calls.

DD-258 provides the separately versioned successor. Its property-free preflight
passes for every volume and vapor link while the DD-257 science and limits stay
unchanged. One execution is authorized after the contract is committed.

DD-258 reaches JSON serialization after its solve and profile construction, but
a NumPy boolean in the gate mapping is not serializable. No admissible evidence
is retained. The predeclared serialization hard stop ends five-second extension
work without a rerun or another reporting successor. The implementation plan
returns to the accepted DD-254 one-second dynamic boundary; any future extension
requires a newly scoped campaign rather than continuation of DD-257/DD-258.

The user authorizes that newly scoped campaign as DD-259. Historical failures
remain unchanged. DD-259 uses the scientifically clean and materially faster
DD-255 root method, replaces the universal duty-coordinate comparison with a
physical relative duty limit, and writes atomic recovery evidence after every
accepted endpoint. Its complete JSON/NPZ/profile serialization path must pass
before the contract is frozen.

DD-259 passes all 20 endpoints and all reporting/recovery gates. Five-second
modified-Newton dynamics are now accepted with worst residual `1.72e-12`, exact
component conservation to `7.35e-13 lbmol`, 165,480 calls, and `55.77 s` wall.
The full final stage profile is serialized. The next dynamic work may extend
the open-loop horizon under a separately frozen contract; controller addition
still follows a longer uncontrolled response and timestep/refinement decision.

DD-260 freezes that longer response at 30 seconds with 120 nominal `0.25 s`
endpoints and a local two-step `0.125 s` refinement at the final interval. The
numerical path remains clean through endpoint 81 (`20.25 s`), but Windows denies
atomic replacement of the single live recovery file while it is being inspected.
DD-260 stops as required. Its complete endpoint-81 temporary recovery is
preserved byte-for-byte; DD-260 is not rerun or reclassified.

DD-261 resumes from that exact state under a new contract and writes each of the
remaining 39 endpoints once to a separate immutable journal file. The combined
120-endpoint path and final refinement complete. Every root, physical,
equilibrium, EOS, continuity, provider, rank, condition, refinement, call, and
wall gate passes. Its aggregate component and energy gates fail only because the
reporter multiplies the final boundary rates by all 30 seconds instead of summing
the changing rates at each endpoint. DD-261's formal failure is preserved.

DD-262 performs the frozen read-only adjudication. It decodes the exact 120 saved
states, replays properties without a solve or state advance, and sums every
endpoint's boundary rates over `0.25 s`. Component conservation closes to
`1.72e-12 lbmol` and energy conservation to `3.95e-11` relative. Endpoint-81 and
final-state parity are exact. The 30-second open-loop vapor-holdup trajectory is
therefore scientifically accepted. The next work may define terminal level-
control ownership structurally; a live controlled trajectory still requires a
separately frozen contract.

DD-263 completes that structural design using the terminal dimensions already
stored in the C3/C4 workbook. The reflux drum is `12.1 x 36.3 ft` with two
hemispherical heads; the vertical sump is `18.1759 x 12 ft`. The Excel loader,
not duplicated controller constants, owns these values. Drum level manipulates
distillate and sump level manipulates bottoms, with live terminal liquid
composition used for each product. The property-free controlled ledger is
`262 x 262`, full rank, and generic in component count. Next, perform one frozen
live zero-motion audit that reconstructs both levels from DWSIM liquid density
and initializes the two PI memories for bumpless stationary outputs. Do not run
a controlled trajectory until that audit passes.

DD-264 completes the live zero-time handoff. Workbook geometry and DWSIM liquid
density give initial drum/sump levels of `0.440779/0.523315`. The PI memories
cancel the initial proportional terms, preserving the stationary distillate and
bottoms rates exactly while all physical inventory rates remain zero. Since the
levels differ from the 50% setpoints, the PI integrators have finite nonzero
rates and will begin a smooth correction after activation. The full live
`262 x 262` Jacobian remains rank 262 and provider-clean. Next, freeze one
stationary controlled hold step. It must accept the first implicit endpoint
without a product jump, clipping, fallback, or unintended physical motion
beyond the declared PI correction.

DD-265 implements that first controlled endpoint. The physical result is clean:
D moves slightly down, B moves slightly up, and both levels begin moving toward
50% while all other column changes remain microscopic. The endpoint residual is
`4.22e-10`, the Jacobian is full rank, and provider ownership passes. DD-265 is
formally failed because the fixed solver budget expires before SciPy declares
success and a near-zero-response energy ratio is stricter than the governing
residual allows. The formal failure is preserved.

DD-266 completes a zero-call adjudication. The `1.94e-6 BTU` energy discrepancy
is 392 times smaller than the aggregate error bound implied by the frozen
energy-row scaling and residual tolerance. The first controlled endpoint is
scientifically accepted. Next, define one short controlled trajectory with
immutable endpoint evidence, controller-memory continuity, level/product
direction gates, conservation, and a final local timestep check. Do not yet
authorize a long controlled run or controller tuning campaign.

DD-267 freezes that short trajectory at one simulated second. It reuses the
accepted `0.25 s` endpoint, advances three additional `0.25 s` roots, and
repeats only the final interval with two `0.125 s` roots. Each new root receives
one fresh colored Jacobian to control DWSIM cost. Both PI memories and absolute
product outputs persist across roots. The run must stop on any direction,
continuity, conservation, physicality, provider, or refinement failure; no
controller tuning or longer horizon is part of DD-267.

DD-267 completes all nominal and refined endpoints. Every new root is physical,
full rank, conservative, and below `1.61e-12` residual. One fresh Jacobian per
root limits the campaign to 27,600 DWSIM calls and `7.713 s`. Levels and product
flows move smoothly and monotonically in the intended directions. DD-267 remains
formally failed because its aggregate refinement gate incorrectly assumes fixed
external product rates.

DD-268 adjudicates that one metric without a live call. The nominal/refined
inventory difference agrees with the difference in integrated D/B histories to
`6.63e-14 lbmol`; both paths independently conserve components. The one-second
controlled trajectory is scientifically accepted. The next contract may extend
the controlled horizon while retaining immutable endpoint journals, one fresh
Jacobian per root, controller-aware conservation/refinement, and no tuning.

DD-269 freezes that extension at five simulated seconds. It replays the saved
one-second path without solving, advances 16 new quarter-second roots, and
repeats the final interval with two eighth-second roots. The controller-aware
boundary-integration identity replaces the fixed-boundary aggregate inventory
test from the outset. Eighteen immutable endpoint journals and a complete final
profile are required. Controller tuning and a longer horizon remain outside the
contract.

Do not add vapor variables to the existing reduced contract as an isolated patch. That would create state columns without resolving phase-transfer, volume, pressure, and energy ownership.

## Minimum acceptance gates

Before calling the extension rigorous, require:

- full structural rank and no unused vapor state columns;
- live Jacobian rank at two finite-difference steps;
- exact total component conservation;
- exact or declared-tolerance phase-transfer cancellation;
- exact or declared-tolerance total-energy conservation;
- vapor EOS/volume closure at every volume;
- pressure and vapor-volume consistency;
- positive vapor inventories and physical `y`;
- stationary root hold with negligible vapor drift;
- coarse/refined transient agreement;
- materially correct response to a feed, reflux, duty, or pressure disturbance;
- provider ownership and no fallback;
- external benchmark comparison for vapor holdup and pressure response.

## Scope warning

The existing `core_v3` reduced contracts and their historical DD-091 through DD-151 evidence should remain immutable historical evidence. Vapor holdup should be implemented as a separately versioned successor architecture with new structural, numerical, initialization, and trajectory gates. Historical reduced-model passes must not be reclassified as vapor-holdup acceptance.
