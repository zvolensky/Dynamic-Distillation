# Independent Review: Core V3 Zero-Rate Initialization

## 1. Executive conclusion

**Classification: repairable after architectural change.**

Core V3 appears usable as a conservative open-loop dynamic DAE, but the present zero-rate formulation is **not well posed as a physically owned terminal-level steady-state problem**.

DD-120 is a valid negative result for the frozen `48 × 46` least-squares formulation. It demonstrates that:

* the two prescribed terminal inventories can be met;
* the solver reaches a reproducible, physical, interior stationary point;
* the remaining 46 DAE rows cannot simultaneously be reduced below `2.4486e-3` within the tested basin and bounds.

It does **not** establish that the numerical values `1388.9 lbmol` and `794 lbmol` are intrinsically incompatible with zero rate. That causal interpretation is too strong.

The more likely problem is:

> **Distillate and bottoms flows are frozen as operating specifications while the two terminal inventories are simultaneously imposed, even though those product flows are the natural manipulated variables for reflux-drum and sump inventory control.**

The terminal inventory rows expose the specification problem; they probably do not cause it.

The current terminal-scaled `48 × 46` path should remain retired. The next experiment should not be another solver variant. It should be one bounded `48 × 48` controlled-terminal feasibility test in which `D` and `B` are released as unknown controller outputs.

---

## 2. Most likely root cause

### Conclusion

**Most likely cause: operating-specification and terminal-ownership mismatch.**

**Confidence: high, approximately 80%.**

The fixed open-loop product flows inherited from the non-steady initializer most likely do not correspond to an exact steady state for the simultaneously fixed:

* feed;
* reflux;
* reboiler duty;
* top pressure;
* equilibrium model;
* Francis hydraulics;
* vapor pressure-drop model.

The terminal inventory constraints then make the mismatch visible.

### Evidence

1. Core V3 explicitly fixes feed, reflux, distillate, bottoms, reboiler duty, and top pressure, solves condenser duty, and contains no controllers.
   `[README_REVIEW_FIRST.md:19–32]`

2. `D` and `B` are registered as fixed parameters rather than algebraic unknowns.
   `[src/dynamic_distillation/core_v3/dynamic_dae_contract_v1.py:338–346]`

3. The runtime mapping explicitly rejects any change in `D` or `B`.
   `[src/dynamic_distillation/core_v3/dynamic_dae_numerical_audit_v1.py:125–146]`

4. The terminal component balances directly contain those fixed flows:

   [
   V_{\text{rect}}y_{\text{rect}}-(R+D)x_D=0
   ]

   [
   L_{\text{strip}}x_{\text{strip}}-Bx_B-V_B y_B=0
   ]

   `[src/dynamic_distillation/core_v3/provider_governed_residual_v1.py:704–736]`

5. The corresponding energy balances also use the fixed product flows, while `Q_C` is solved and `Q_R` is fixed.
   `[src/dynamic_distillation/core_v3/provider_governed_residual_v1.py:739–777]`

6. The two terminal inventory rows are added separately to the 46-row DAE, producing the overdetermined `48 × 46` DD-120 residual.
   `[src/dynamic_distillation/core_v3/zero_rate_readiness_v1.py:82–118]`
   `[src/dynamic_distillation/core_v3/conserved_nu_pressure_initializer_numerical_v1.py:231–246]`

7. The fixed DD-120 product flows are not the workbook stream flows:

   | Source                  | Distillate, lbmol/h | Bottoms, lbmol/h |
   | ----------------------- | ------------------: | ---------------: |
   | Workbook stream profile |             2380.99 |          4761.98 |
   | DD-120 fixed values     |            2085.666 |         5057.308 |

   The DD-120 values came from the prior equation-consistent but non-steady initializer, not from a demonstrated Core V3 steady state.
   `[distillation_column_template_8stage.xlsx, Streams!B7:D12]`
   `[logs/dd120_core_v3_zero_rate_root_20260727.json, starts[*].distillate_lbmolph and bottoms_lbmolph]`

### Why the terminal targets are probably not the cause

The terminal inventory magnitudes behave as two scale gauges in the present steady equations.

#### Reflux-drum scale

Scaling all three reflux-drum inventories by a common positive factor leaves:

* drum composition unchanged;
* saturation closure unchanged;
* component and energy flows unchanged;
* pressure unchanged;
* all zero-rate drum balance equations unchanged.

There is no terminal Francis equation, and top internal energy is derived rather than stored as an independent state. Francis rows exist only for the three interior hydraulic volumes.
`[src/dynamic_distillation/core_v3/dynamic_dae_contract_v1.py:296–330]`

#### Reboiler/sump scale

Scaling all three bottom inventories and bottom internal energy by the same positive factor leaves:

* bottom composition unchanged;
* specific internal energy unchanged;
* equilibrium unchanged;
* product and vapor enthalpies unchanged;
* component and energy balances unchanged at zero rate.

The bottom-to-stripping pressure equation is deliberately dry-resistance-only and excludes liquid-head dependence on bottom inventory.
`[src/dynamic_distillation/core_v3/pressure_implicit_dae_contract_v1.py:103–136]`

The lower storage equation is homogeneous:

[
U_B=N_B,u_L(T_B,P_B,x_B)
]

so simultaneous scaling of `N_B` and `U_B` preserves closure.
`[src/dynamic_distillation/core_v3/conserved_nu_pressure_dae_contract_v1.py:139–175]`

Therefore, if an exact DAE-only root exists in the admissible physical domain, its two terminal scales should normally be adjustable to the requested positive totals without changing the remaining physics.

### What DD-120 actually proves

At either DD-120 endpoint:

[
|r|_2=\sqrt{2,\text{cost}}
=7.673687\times10^{-3}
]

This is essentially identical to the reported left-null projection:

[
|P_{\mathcal N(J^T)}r|_2
=7.673687\times10^{-3}
]

That means the residual is almost entirely in the two-dimensional left-null space of the augmented `48 × 46` Jacobian. The solver reached a genuine first-order least-squares stationary point; this is not merely slow convergence.

But it does not identify whether the incompatible information is:

* the fixed product-flow split;
* another operating specification;
* a hidden implementation coupling;
* inherited numerical bounds;
* or the terminal targets.

The missing final 48-element residual vector prevents row-level adjudication.
`[README_REVIEW_FIRST.md:152–154]`

---

## 3. Degree-of-freedom review

### Current zero-rate unknowns and equations

| Block                                   |  Count | Current role                                            | Correct ownership                          |
| --------------------------------------- | -----: | ------------------------------------------------------- | ------------------------------------------ |
| Component inventories `N[j,k]`          |     15 | Differential states; solved as steady-state coordinates | Dynamic states and initial conditions      |
| Lower internal energies `U[j]`          |      4 | Differential states; solved as steady-state coordinates | Dynamic states and initial conditions      |
| Temperatures                            |      5 | Algebraic unknowns                                      | Thermodynamic closure                      |
| Independent equilibrium vapor fractions |      8 | Algebraic unknowns                                      | Four equilibrium blocks                    |
| Francis liquid flows                    |      3 | Algebraic unknowns                                      | Interior hydraulic equations               |
| Vapor flows                             |      4 | Algebraic unknowns                                      | Energy balances plus pressure-drop closure |
| Condenser bubble composition            |      2 | Algebraic unknowns                                      | Condenser saturation closure               |
| Condenser duty `Q_C`                    |      1 | Algebraic unknown                                       | Drum energy balance                        |
| Lower pressures                         |      4 | Algebraic unknowns                                      | Four pressure-drop equations               |
| **Total**                               | **46** |                                                         |                                            |

| Equation block                          |  Count |
| --------------------------------------- | -----: |
| Five-volume component balances          |     15 |
| Five energy balances                    |      5 |
| Four full phase-equilibrium blocks      |     12 |
| Condenser saturation/fugacity closure   |      3 |
| Francis hydraulics                      |      3 |
| Vapor pressure-drop equations           |      4 |
| Lower-volume energy-storage definitions |      4 |
| **Total**                               | **46** |

The registry is structurally `46 × 46`, but the physical equations contain approximately two terminal scale freedoms.

### Numerical rank interpretation

DD-119 reported formal DAE rank `46/46`, but its two smallest canonical singular values were approximately:

[
1.33\times10^{-11},\qquad 7.40\times10^{-13}
]

while the condition number was `2.54e13`. At the second finite-difference step, the smallest value changed to approximately `3.47e-13`.

The rank test uses ordinary machine-precision SVD tolerance.
`[src/dynamic_distillation/core_v3/zero_rate_readiness_v1.py:189–194]`

Consequently, “rank 46” should not be interpreted as evidence of 46 strongly independent physical directions. The incidence-based structural rank does not detect nonlinear homogeneity or ratio invariance. The defensible physical interpretation is:

> **44 strongly constrained directions plus two terminal scale gauges contaminated by finite-difference and property-evaluation noise.**

Adding the two terminal rows raises the smallest augmented singular value to approximately `0.00334`, explaining the improvement to condition `≈5.6e3`.

### Operating specifications

| Quantity                          | Current role                    | Assessment                                               |
| --------------------------------- | ------------------------------- | -------------------------------------------------------- |
| Feed component rates and enthalpy | Fixed disturbance/specification | Correct                                                  |
| Reflux `R`                        | Fixed manipulated input         | Reasonable operating specification                       |
| Reboiler duty `Q_R`               | Fixed manipulated input         | Reasonable operating specification                       |
| Top pressure                      | Fixed boundary/specification    | Reasonable for this feasibility model                    |
| Condenser duty `Q_C`              | Solved algebraic variable       | Correct for fixed top pressure and saturated drum liquid |
| Distillate `D`                    | Fixed input                     | Questionable at steady state                             |
| Bottoms `B`                       | Fixed input                     | Questionable at steady state                             |
| Drum inventory/level              | Extra DD-120 row                | No present physical owner                                |
| Sump inventory/level              | Extra DD-120 row                | No present physical owner                                |

### Ownership of terminal inventories

The four alternatives posed in the review prompt resolve as follows:

1. **True free initial conditions:**
   **Yes during open-loop dynamics.** Drum and sump inventories are differential states whose initial magnitudes may be selected independently, subject to physical geometry.

2. **Algebraic scale or gauge selections:**
   **Yes in the current zero-rate equations.** Their magnitudes are absent from the terminal steady physics except through homogeneous storage.

3. **Steady-state constraints requiring level control and manipulated variables:**
   **Yes if the project intends fixed operating levels.** In that case each level requires:

   * explicit geometry;
   * inventory-to-volume-to-level mapping;
   * a level setpoint;
   * a controller;
   * an independent manipulated flow.

   The physically natural assignments are:

   * reflux-drum level → distillate flow `D`;
   * sump level → bottoms flow `B`.

4. **Already determined elsewhere:**
   **No.** The current equations determine terminal compositions and thermodynamic conditions, not their absolute inventory scales.

### Missing terminal volume ownership

The workbook contains explicit overhead drum geometry:

* diameter `12.1 ft`;
* length `36.3 ft`;
* liquid fraction `0.5`.

`[distillation_column_template_8stage.xlsx, Specifications!B26:B28]`

Core V3 does not use that geometry in a terminal volume or level equation. No corresponding bottom sump geometry is evident in the reduced workbook.

This is inconsistent with the general requirement that terminal equipment have explicit conserved-state and volume mappings.
`[docs/requirements.md:110–113]`

A total-mole target is not automatically a level setpoint. The mapping must include live liquid density and vessel geometry:

[
V_L=\frac{N_L}{\rho_L(T,P,x)}, \qquad
h=g^{-1}(V_L)
]

---

## 4. Findings ordered by severity and certainty

### Finding 1 — High severity, confirmed

**DD-120 establishes failure of the frozen `48 × 46` formulation, but not the stated terminal-incompatibility cause.**

Both starts found the same stationary point and closed the terminal rows, but no per-row final residual was retained.
`[docs/dd_120_core_v3_zero_rate_root_20260727.md:7–20]`

### Finding 2 — High severity, strong inference

**The steady problem is operating-specification constrained by fixed `D` and `B`.**

Given fixed feed, reflux and reboiler duty, product flows normally emerge from material balance and level-control ownership. Freezing both at values taken from a non-steady initializer gives no strong reason for zero terminal accumulation to be attainable.

Once the terminal inventories are treated as setpoints, the problem is plainly overdetermined:

[
48\ \text{equations},\quad 46\ \text{unknowns}
]

Adding `D` and `B` as unknown controller outputs restores a natural `48 × 48` closure.

### Finding 3 — High severity, strong inference

**The two terminal “near freedoms” are physical scale gauges, not merely weak variables.**

The two near-zero singular values are consistent with the exact homogeneity of the terminal equations. Structural rank does not disprove this.

A gauge-invariance test is missing from the test suite. The current readiness tests verify dimensions, finite-difference coloring and formal rank, but do not scale terminal inventories and confirm DAE invariance.
`[tests/test_core_v3_zero_rate_readiness_v1.py:37–98]`

### Finding 4 — High severity, confirmed

**Terminal total inventories are being used without terminal level geometry or controller ownership.**

The current rows constrain `sum(N)` directly. They do not implement physical drum or sump level equations.

### Finding 5 — Medium severity, confirmed

**The DD-114 state is equation-consistent and conservative but not steady.**

Its 52 constraints closed below numerical tolerance, with Jacobian condition approximately `2054`, but significant conserved rates remained. For example, bottom component rates included approximately:

* `+792.87 lbmol/h` propane;
* `−404.10 lbmol/h` butane;
* `−62.26 lbmol/h` pentane.

The lower/boundary energy rates were also material.
`[logs/dd114_core_v3_initializer_zero_time_audit_20260727.json, fresh_endpoint]`

DD-115 proved that implicit steps could close at machine precision and preserve physicality and conservation, but its vapor-flow and initial-rate refinement gates failed.
`[logs/dd115_core_v3_initializer_first_step_refinement_20260727.json, gates and refinement]`

Therefore DD-114 is a credible **non-steady consistent state**, not yet a fully accepted dynamic initializer.

### Finding 6 — Medium severity, confirmed

**Gross scaling or finite-difference failure is unlikely to explain DD-120.**

Supporting evidence:

* colored and full Jacobians agreed;
* spectra were stable at two finite-difference steps;
* both starts reached the same endpoint;
* optimality was below `5.60e-9`;
* the residual was wholly consistent with the augmented left-null space.

Scaling may influence which least-squares point is reached, but positive row scaling cannot remove an attainable exact root.

Finite-difference noise does, however, affect the interpretation of the two weakest DAE singular directions.

### Finding 7 — Medium severity, unresolved

**An exact root elsewhere has not been ruled out.**

Reasons:

* the two starts are related states from the same initializer lineage;
* DD-120 used inherited bounds;
* all four solved lower pressures ended close to their lower coordinate bounds.

The closest normalized bound distances were approximately:

| Variable                    | Normalized distance |
| --------------------------- | ------------------: |
| `P[rectifying_tray]`        |             0.00193 |
| `P[feed_tray]`              |             0.00482 |
| `P[stripping_tray]`         |             0.00744 |
| `P[combined_reboiler_sump]` |             0.00826 |

This does not invalidate DD-120, but “interior” is less reassuring than the report implies.

### Finding 8 — Medium severity, unresolved

**An implementation defect cannot yet be excluded.**

Conservation and provider tests argue against a broad coding failure. Nevertheless, the package lacks:

* a terminal gauge-invariance test;
* the final residual vector;
* per-row residual ranking;
* `J^T r` by row/block;
* saved left-null vectors.

A local equation-ordering, storage, terminal, or pressure coupling defect could therefore remain hidden.

### Finding 9 — Low severity, confirmed

**There is no evidence that DWSIM ownership, component conservation or energy conservation caused the failure.**

Those gates passed at machine precision. No fallback or mixed-property basis was used.

---

## 5. Ranked solution options

The ranking below is based on physical defensibility and usefulness as the next project decision, not merely ease of coding.

|  Rank | Option                                                                                                        | Benefits                                                                                                                                     | Main risks                                                                                                                  | Effort     | Falsifying evidence                                                                                               | Genericity                          |
| ----: | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| **1** | **Controlled-terminal `48 × 48` bridge: release `D` and `B`, retain two terminal setpoint rows**              | Directly tests the most likely ownership defect; square system; preserves every existing physical row; assigns natural level-control outputs | Terminal mole targets are still stand-ins for real levels; solved product flows may be impractical                          | Low–medium | Two fixed starts fail to reach one exact root, or `D/B` hit bounds                                                | Fully role-generic                  |
| **2** | **Full terminal reformulation: geometry, level measurements, PI controllers and `D/B` manipulated variables** | Correct production architecture; explicit terminal storage and level ownership; supports dynamic controller initialization                   | More states, controller tuning, possible interactions with pressure/reflux control                                          | High       | Controlled steady closure fails before controller dynamics                                                        | Fully role-generic                  |
| **3** | **Accept a nonzero-rate consistent initializer with a new dynamic-readiness gate**                            | Preserves current open-loop operating specs; DD-114 already demonstrates exact equation consistency and conservation                         | Real startup transient; DD-115 refinement did not fully pass; possible rapid inventory or vapor-flow movement               | Medium     | Predeclared timestep refinement fails, inventories approach depletion, or trajectories are not restart-repeatable | Fully generic                       |
| **4** | **DAE-only gauge-reduced zero-rate solve**                                                                    | Determines whether fixed `D/B` admit any zero-rate physical solution independent of terminal scale; useful diagnostic                        | Terminal inventories remain arbitrary; ill-conditioned unless gauges are analytically removed; not a production initializer | Medium     | Gauge-reduced system retains a reproducible residual floor                                                        | Fully generic                       |
| **5** | **Release another operating specification such as reflux or reboiler duty**                                   | Could recover a root if product rates must remain fixed for a real process requirement                                                       | Poor terminal-level ownership unless an explicit control philosophy justifies it; may produce unreasonable duty or reflux   | Medium     | Released variable becomes nonphysical or terminal zero rates still fail                                           | Generic, but case-control dependent |
| **6** | **Pseudo-transient or full implicit continuation**                                                            | May enlarge convergence basin for a known well-posed root problem                                                                            | Cannot repair incompatible specifications; can converge slowly toward a non-root; high property-call cost                   | High       | Residual plateaus independent of pseudo-time or converges to the same least-squares floor                         | Generic numerically                 |
| **7** | **Revise the exact-zero requirement alone**                                                                   | Correctly distinguishes dynamic-ready from steady initialization                                                                             | Does not repair an algebraic or ownership defect; cannot be used to accept DD-120’s residual floor                          | Low        | Algebraic residual or conservation gates remain failed                                                            | Generic requirement change          |

### Option 1: Accept a nonzero-rate consistent initializer

This is technically defensible **only as dynamic initialization**, not as steady-state initialization.

Requirements should include:

* exact algebraic and storage closure;
* exact component and energy conservation;
* reported equation-owned rates;
* bounded fractional inventory and energy change;
* timestep-refined first-step behavior;
* physical pressure, temperature and flow evolution;
* no projection or clipping;
* restart parity.

The DD-114/DD-115 evidence is promising but not yet sufficient because the frozen vapor-flow and initial-rate refinement gates failed.

### Option 2: Reformulate terminal ownership

This is the preferred production architecture.

At steady state:

* add drum and sump level equations;
* solve `D` and `B`;
* retain `R`, `Q_R`, feed and top pressure as operating specifications.

During dynamics:

* drum and sump inventories remain differential states;
* levels are calculated from inventory, density and geometry;
* PI controller states determine `D` and `B`;
* controller integrators are initialized to the steady product flows.

### Option 3: Change steady operating specifications

The physically preferred release is **both product flows**, not an arbitrary duty or internal flow.

Releasing `D` and `B` adds two unknowns and allows the two terminal setpoint equations to have physical owners:

[
46+2=48\ \text{unknowns}
]

[
46+2=48\ \text{equations}
]

Releasing only reflux or reboiler duty would not by itself provide two independent terminal inventory-control outputs.

### Option 4: Solve the DAE-only system

A DAE-only solve is meaningful as a feasibility study, but the gauges should be handled analytically rather than left to an ill-conditioned `46 × 46` solve.

Suitable approaches include:

* remove one drum scale coordinate and one bottom scale coordinate;
* solve on normalized terminal compositions and specific internal energy;
* fix arbitrary unit terminal scales during the solve;
* rescale the resulting exact root afterward.

The resulting physical problem is effectively approximately `44 × 44`.

A DAE-only result would answer whether the fixed operating specifications permit zero rate, but it would not establish unique terminal levels.

### Option 5: Pseudo-transient continuation

Do not authorize this yet.

Pseudo-transient continuation is useful when:

* the physical equation system is square;
* specifications have explicit owners;
* a root is believed to exist;
* ordinary Newton/trust-region methods have inadequate basin size.

It distinguishes slow numerical progress from infeasibility by monitoring whether:

* the true physical residual decreases consistently as pseudo-time increases;
* the pseudo-transient term tends to zero;
* the endpoint is independent of pseudo-time schedule and starting state.

A persistent physical residual floor remains a failure regardless of pseudo-time convergence.

### Option 6: Revise the exact-zero requirement

This should be done, but it must not be used to approve DD-120.

The correct distinction is:

* **algebraic consistency is mandatory for every initializer**;
* **zero conserved rates are mandatory only for a steady-state classification**;
* **bounded nonzero rates may be accepted for dynamic initialization after a separate dynamic gate**.

---

## 6. Recommended next action

### Question to answer

> **Does releasing distillate and bottoms flows as terminal level-control outputs remove the DD-120 residual floor while every other Core V3 equation and operating specification remains unchanged?**

This is the smallest experiment that directly tests the most likely physical diagnosis.

### Proposed contract

#### A. Mandatory gauge preflight

Before any nonlinear solve, evaluate the 46 DAE residuals at the saved DD-120 endpoint under four exact physical transformations:

1. Multiply all reflux-drum component inventories by `1.01`.
2. Multiply them by `0.99`.
3. Multiply all bottom component inventories and bottom internal energy by `1.01`.
4. Multiply them by `0.99`.

All algebraic variables remain fixed.

Expected result:

* the 46 DAE residuals remain unchanged within provider repeatability;
* only the relevant terminal inventory row changes;
* drum and bottom compositions remain unchanged;
* bottom specific internal energy remains unchanged.

**Gauge gate**

[
\max |r_{\text{DAE,perturbed}}-r_{\text{DAE,baseline}}|
\leq
\max(10^{-10},10,r_{\text{repeatability}})
]

If this fails, stop immediately. The failure identifies a hidden terminal inventory owner or implementation defect that must be corrected before any root solve.

#### B. Unknowns

Use the existing 46 zero-rate coordinates plus:

47. Positive distillate flow `D`.
48. Positive bottoms flow `B`.

Use logarithmic or logistic physical-domain coordinates. Do not clip.

#### C. Residual rows

Retain exactly:

* 15 component balances;
* 5 energy balances;
* 12 phase-equilibrium rows;
* 3 condenser saturation rows;
* 3 Francis rows;
* 4 pressure-drop rows;
* 4 internal-energy storage rows;
* reflux-drum total-inventory setpoint;
* reboiler/sump total-inventory setpoint.

Total:

[
48\ \text{rows}
]

For this feasibility test, the two inventory totals may remain at `1388.9` and `794 lbmol`, but they must be labelled **inventory setpoints**, not physical levels.

#### D. Released specifications and physical owners

Remove `D` and `B` from the fixed-parameter registry.

Assign:

* `D` → ideal reflux-drum level-controller output;
* `B` → ideal sump level-controller output.

Keep fixed:

* feed component flows and enthalpy;
* reflux;
* reboiler duty;
* reflux-drum pressure;
* geometry and property package.

Continue solving `Q_C`.

#### E. Starting states

Permit exactly two solves:

1. DD-112 canonical physical state with
   `D=2085.666 lbmol/h`, `B=5057.308 lbmol/h`.

2. DD-115 refined one-second state with the workbook product split:
   `D=2380.99 lbmol/h`, `B=4761.98 lbmol/h`.

These give materially different product-flow starts without inventing another physical profile.

#### F. Solver and derivatives

* `scipy.optimize.least_squares(method="trf")`;
* `ftol=xtol=gtol=1e-12`;
* `max_nfev=80`;
* `x_scale=1`;
* graph-colored central-difference Jacobian;
* solve step `1e-5`;
* endpoint spectrum check at `5e-6`;
* one full uncolored Jacobian cross-check at the canonical endpoint.

No alternate solver, continuation, pseudo-transient, target adjustment or tolerance change.

#### G. Acceptance gates

**Residual**

* every one of 48 scaled residuals `<1e-8`;
* save the complete raw and scaled residual vectors and per-row ranking.

**Robustness**

* both starts succeed;
* endpoint transformed-coordinate difference `<1e-6`;
* product flows agree within an engineering-equivalent tolerance.

**Rank and condition**

* endpoint Jacobian rank `48/48`;
* condition `<1e8`;
* relative singular-spectrum change `<0.25`;
* no zero row, unused variable or off-registry coupling.

**Physical**

* all inventories and flows positive;
* `0<D<F` and `0<B<F`;
* ordered positive pressure;
* valid compositions;
* no property fallback;
* no coordinate within `1e-6` normalized distance of a bound.

**Conservation**

* component telescoping relative error `<1e-12`;
* energy telescoping relative error `<1e-10`;
* whole-column total flow closure:

[
\frac{|F-D-B|}{F}<10^{-12}
]

**Efficiency**

* no more than two nonlinear solves;
* fewer than `100,000` audited provider calls total;
* wall time below `180 s`.

### Decision rules

#### Pass

If both starts reach the same exact root:

* classify fixed `D/B` ownership as the cause of DD-120;
* authorize explicit terminal geometry and dynamic level-controller implementation;
* do not run another zero-rate solver campaign.

#### Fail

If the gauge preflight passes but the `48 × 48` system does not reach one exact root:

* reject the hypothesis that releasing `D/B` alone repairs the formulation;
* preserve the full residual vectors;
* stop zero-rate numerical development;
* conduct a row-level equation/specification review based on the failed residual blocks.

#### Hard stop

Stop immediately on:

* gauge-invariance failure;
* provider ownership change;
* conservation failure;
* nonfinite property result;
* active-bound solution;
* differing physical roots;
* rank loss;
* call or wall limit;
* any attempt at a third solve or different numerical method.

---

## 7. Requirements changes

The existing requirements already distinguish DAE-consistent and steady-state initialization.
`[docs/requirements.md:60–64]`

That distinction should be retained and strengthened.

### Proposed dynamic-initialization requirement

> **Dynamic-ready initialization:** An initialization state may be accepted for dynamic integration without being classified as steady when all algebraic, equilibrium, hydraulic, pressure and storage equations satisfy their declared numerical tolerances; component and energy conservation pass; all nonzero conserved derivatives are equation-owned and reported; and a predeclared timestep-refinement and restart test demonstrates bounded, physical and conservative startup behavior. Such a state shall be classified `algebraically_consistent_nonsteady`.

### Proposed steady-state requirement

> **Steady-state initialization:** A state may be classified as steady only when all required component-inventory and internal-energy derivatives satisfy declared steady tolerances under a square, physically owned specification and control formulation. Terminal level setpoints shall have explicit geometry, measurement and manipulated-variable ownership. Numerical tolerances shall be declared before execution and shall not be relaxed after observing a residual floor.

“Exact zero” should mean satisfaction within a declared numerical tolerance, not bitwise zero.

### Proposed terminal-ownership requirement

> Reflux-drum and sump inventories are differential initial conditions unless explicit level-control closure is active. A terminal inventory may be imposed in a steady-state solve only as:
> (a) a documented numerical gauge that has been proven not to alter the physical DAE residual; or
> (b) a physical level setpoint with an inventory-volume-level mapping and one independent manipulated variable or controller output.
> A raw total-mole target shall not be described as a level constraint without that mapping.

### Proposed failed-solve evidence requirement

> Every failed steady-root or initializer campaign shall preserve the complete raw and scaled final residual vectors, row names, scales, per-row rankings, active-bound distances, `J^T r`, singular values and relevant left- and right-null vectors. Aggregate norms alone are insufficient for causal diagnosis.

### Exact-zero recommendation

* Keep the existing algebraic residual standards mandatory.
* Keep zero-rate tolerances mandatory for anything labelled **steady**.
* Do not make zero conserved rates mandatory for all dynamic initialization.
* Do not change the `1e-8` DD-120 tolerance to accept the existing `2.4486e-3` floor.
* Treat FR-019bi through FR-019bk as immutable historical campaign evidence, not as general proof that terminal target values caused the failure.

---

## 8. Open questions and missing evidence

1. **Which DAE rows make up the DD-120 residual floor?**
   The final 48-element residual was not saved.

2. **Does exact terminal gauge invariance hold in the live implementation?**
   It follows from the reviewed equations but has not been directly tested.

3. **What were the intended process-control owners of `D` and `B`?**
   The package currently treats them as fixed inputs, while the general requirements include top and bottom level control.

4. **What is the physical sump geometry?**
   Drum geometry is present in the workbook; equivalent bottom geometry is not evident.

5. **Are the inherited pressure bounds physically necessary?**
   The DD-120 endpoint lies close to all four lower-pressure coordinate bounds.

6. **Are product flow, product purity, reflux, boilup and pressure intended as simultaneous operating targets?**
   A production steady-state model needs a documented operating-DOF and control-pairing table.

7. **Should fixed top pressure represent an external boundary or an ideal pressure controller?**
   If it represents control, condenser-duty ownership should be documented explicitly.

8. **Would the released `D/B` solution remain operationally realistic?**
   Even an exact mathematical root should be rejected if it produces implausible product rates, purities, duties or inventory-control authority.

## Final judgment

DD-120 should be treated as a successful falsification of the frozen terminal-scaled formulation, but not as proof that the inherited terminal holdups are physically incompatible.

The strongest current diagnosis is:

> **The model is trying to impose terminal inventory setpoints while retaining both terminal product flows as fixed open-loop specifications.**

Release `D` and `B` in one bounded `48 × 48` controlled-terminal feasibility test. A pass justifies the terminal geometry and controller architecture. A fail should end zero-rate numerical experimentation until the row-level residual evidence identifies a different physical ownership defect.
