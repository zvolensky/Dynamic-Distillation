**MESH Equations (Current Model)**
This document reflects the equations in `src/dynamic_distillation/column_rhs_v1.py`.

**State And Notation**
```
i = stage index (1..N), 1 = condenser, N = reboiler tray
k = component index (1..Nc)
L_out[i], V_out[i] = liquid/vapor out of stage i (lbmol/s)
L_in[i],  V_in[i]  = liquid/vapor into stage i (lbmol/s)
x_i,k, y_i,k = liquid/vapor mole fractions on stage i
ML_i,k, MV_i,k = liquid/vapor component holdup on stage i (lbmol)
Top drum: M_topL,k, M_topV,k
Bottom sump: M_botL,k, M_botV,k
F_L,i,k, F_V,i,k = feed liquid/vapor component rates to stage i (lbmol/s)
D_k, B_k = distillate and bottoms component draws (lbmol/s)
Q_cond, Q_reb = condenser and reboiler duty (BTU/h)
T_i, P_i = tray temperature and pressure (F, psia)
```
Layout requirements:
- `tray_L` is always required.
- `tray_V` is required (`layout.include_vapor=True` is enforced).
- Optional: top drum holdup (`include_top`), bottom sump holdup (`include_bottom`), tray temperatures (`include_temperature`), tray energy holdups (`include_energy`).

**Flow Construction And Boundary Conditions**
Internal L/V profiles are taken from `col.L_lbmolph` and `col.V_lbmolph` (Excel/ChemSep steady-state profiles).
Feed effects are handled through explicit feed source terms in the tray balances rather than by rebuilding internal profiles.
Boundary conditions always enforced:
- `L_out[1] = reflux`
- `V_out[1] = 0` (total condenser)
- `V_out[N] = boilup`
Optional hydraulics: internal `L_out` (stages 2..N-1) can be overridden by Francis-weir outflow when geometry is available.
Runner preset note (`dynamic_run_scaffold_v1`):
- `--runtime-mode parity` (default CLI mode) forces `pressure_model="spec"`, `vapor_flow_model="profile"`, and disables liquid-hydraulic override.
- `--runtime-mode hydraulic` forces `pressure_model="hydraulic"`, `vapor_flow_model="energy"`, leaves liquid-hydraulic override plus vapor-holdup relaxation off unless explicitly enabled, and defaults feed-stage flashing off unless explicitly requested.
- `--runtime-mode huang` forces `pressure_model="hydraulic"`, `vapor_flow_model="profile"`, and enables liquid-hydraulic override with `liquid_hydraulic_model="huang-htc"`.
- `--runtime-mode legacy` keeps spec/CLI-driven model selection and is the only mode where startup hydraulic sequencing is active.

**Generic Tray Component Balances (All Stages)**
```
d(ML_i,k)/dt = L_in[i] * x_in[i,k] + F_L,i,k - L_out[i] * x_i,k

d(MV_i,k)/dt = V_in[i] * y_in[i,k] + F_V,i,k - V_out[i] * y_i,k
```
Feed components are only nonzero at the feed stage.
When a thermo provider is available, the feed split can be computed from a TP flash at the feed-stage pressure (`flash_feed_at_stage_conditions=True`), instead of using the raw stream vapor fraction. For ChemSep-seeded hydraulic startup, the runner now defaults this off so the imported steady tray profiles are not immediately perturbed by a second feed flash calculation.
Feed component-flow lookups are matched case/format-insensitively (for example `n-Pentane` and `N-Pentane` map to the same component).

**Condenser (Stage 1)**
Total condenser behavior. Vapor leaving upward is zero.

If `include_top=True` (top drum present):
```
d(M_topL,k)/dt = L_cond_to_top * x_cond,k
              - L_out[1] * x_top,k
              - D_k

d(M_topV,k)/dt = V_to_top * y_in[1,k]
              - V_cond_top * y_top,k
              - D_vap,k
              - V_psv_top * y_top,k

// Condenser tray liquid is independent from drum liquid
d(ML_1,k)/dt = V_cond_in * y_in[1,k]
             + V_cond_top * y_top,k
             - L_cond_to_top * x_cond,k
             + F_L,1,k + F_V,1,k

// Condenser tray has no vapor holdup accumulation
d(MV_1,k)/dt -= V_in[1] * y_in[1,k]
```
Where:
- `V_cond_in`: condensed portion of incoming stage-2 vapor.
- `V_to_top`: uncondensed portion routed to top vapor holdup.
- `V_cond_top`: top-vapor holdup condensed to liquid.
- `V_psv_top`: optional PSV vent flow from top vapor holdup.
- `L_cond_to_top`: condenser-liquid transfer to reflux drum (`V_cond_in + V_cond_top`, plus feed to stage 1 if present).
- `x_cond`: condenser-tray liquid composition.

When top-drum PSV is enabled:
```
V_psv_top = clamp(gain * max(P_top_drum - P_set, 0), 0, V_psv_max)
```

Distillate draw uses component breakdown if provided; otherwise draws total with `x_top` and `y_top`.
`D_k` can be dynamically overridden by runner-level control (top holdup PI -> total distillate draw).

If `include_top=False`:
```
// Immediate condensation on tray 1
d(ML_1,k)/dt += V_in[1] * y_in[1,k]
d(MV_1,k)/dt -= V_in[1] * y_in[1,k]
// Distillate draw removed from tray 1 holdup
```

**Reboiler Tray (Stage N)**
Boilup is applied as a phase-change term at stage N:
```
d(ML_N,k)/dt -= V_out[N] * x_reb,k

d(MV_N,k)/dt += V_out[N] * x_reb,k
               - V_out[N] * y_reb,k
```
`x_reb` and `y_reb` come from tray N holdup, or tray N-1 if the reboiler holdup is zero.

Boilup selection:
- `reboiler_mode="specified"`: use `boundary.boilup_lbmolph` or `col.V_lbmolph[-1]`.
- `reboiler_mode="duty"`: compute boilup from reboiler duty and latent heat (requires `thermo_provider`).
- `reboiler_mode="auto"`: use duty if available and no explicit boilup; otherwise specified.

If `reboiler_equilibrium=True`, a bubble-point solve at the bottom pressure updates `T_reb` and `y_reb`.
If the reboiler tray holdup is zero, tray-N derivatives are forced to zero and a no-holdup flash is used.

**Bottom Sump (If `include_bottom=True`)**
Liquid-only holdup for bottoms draw (no coupling to boilup):
```
d(M_botL,k)/dt = L_out[N] * x_tray_N,k - B_k
```
Bottom vapor draw (if specified) removes from `M_botV,k`.
`B_k` can be dynamically overridden by runner-level control (bottom holdup PI -> total bottoms draw).

**Summation Constraints**
```
sum_k x_i,k = 1
sum_k y_i,k = 1
```
If liquid holdup is near zero, a fallback composition is supplied so flashes remain valid.

**Equilibrium Relaxation (Optional)**
When `equilibrium_relaxation=True` (requires `thermo_provider`):
```
y_eq,i,k = K_i,k * x_i,k / sum_j(K_i,j * x_i,j)
transfer_i,k = (MV_i / tau_eq) * (y_eq,i,k - y_i,k)

d(MV_i,k)/dt += transfer_i,k
d(ML_i,k)/dt -= transfer_i,k
```
`tau_eq` is `ColumnInputs.tau_eq_sec` if set, otherwise `ColumnSpec.tau_eq_sec`, else 10 s.

**Energy Option B1 (Enthalpy Holdup, `include_energy=True`)**
Energy holdup is stored as `EL_i = ML_i * hL_i` and `EV_i = MV_i * hV_i`.
```
hL_i = EL_i / ML_i
hV_i = EV_i / MV_i

d(EL_i)/dt = L_in[i] * hL_in - L_out[i] * hL_i

d(EV_i)/dt = V_in[i] * hV_in - V_out[i] * hV_i

d(EL_1)/dt += Q_cond / 3600   // total condenser: duty applied to liquid energy

d(EL_N)/dt += Q_reb  / 3600
```
No explicit feed enthalpy term is used in this option.

**Legacy Temperature-State Energy (If `include_temperature=True`)**
Tray temperatures evolve by energy balance using `thermo` (or `thermo_provider` for Cp):
```
dE_i = L_in[i] * hL_in + V_in[i] * hV_in + q_feed
     - L_out[i] * hL_out - V_out[i] * hV_out
     + Q_i

C_i = ML_i * cpL_i + MV_i * cpV_i

dT_i/dt = dE_i / C_i
```
`Q_i` includes `Q_cond` at stage 1 and `Q_reb` at stage N. The sump temperature has a separate liquid-only balance and can be relaxed to a bubble-point when `thermo_provider` is available.

**Vapor Flow Closure**
- `vapor_flow_model="profile"`: use the internal Excel/ChemSep `V` profile with boundary conditions enforced.
- `vapor_flow_model="energy"`: solve `V_out` from the tray energy balance with fixed `L_out`:
```
dE_target,i = C_i * dT_target,i

V_out[i] = (L_in[i] * (hL_in - hL_out)
          + V_in[i] * (hV_in - hL_out)
          + q_feed
          - F_total,i * hL_out
          + Q_i
          - dE_target,i) / (hV_out - hL_out)
```
Uses cached enthalpies when available and relaxes to `V_out_prev` when `vapor_flow_relaxation_sec` is set. Falls back to previous vapor flow when `|hV_out-hL_out|` is too small for stable division.
In energy mode, the feed stage vapor flow is solved dynamically (it is not pinned to the input profile).
Additional hard clamps limit single-step `V_out` excursions relative to previous/profile values.
The stage directly above the reboiler is additionally constrained near boilup (default `~98-102%` of boilup) to suppress non-physical lower-section drift.
This guard is configurable via `ColumnInputs.reboiler_neighbor_vflow_hi_ratio` and `ColumnInputs.reboiler_neighbor_vflow_lo_ratio` (and corresponding Excel/CLI settings in the runner).

Stage-level thermo flash refresh can be gated by per-stage thresholds:
- `thermo_refresh_dT_F`: refresh only if `|T_i - T_i,prev|` exceeds threshold
- `thermo_refresh_dP_psia`: refresh only if `|P_i - P_i,prev|` exceeds threshold
- `thermo_refresh_dx`: refresh only if `max_k |z_i,k - z_i,k,prev|` exceeds threshold
If all configured criteria are below threshold for a stage, that stage reuses cached thermo values.
If the active provider exposes `flash_TP_full_batch(T, P, z_rows)`, refreshed stages are solved in one batch path; otherwise flashes are solved one stage at a time.

**Pressure Model**
- `pressure_model="spec"`: use `col.P_psia`.
- `pressure_model="hydraulic"`: compute pressure from bottom anchor using dry tray pressure drop plus liquid head. Uses geometry, vapor flow, and mixture MW. These pressures are used for flashes and energy when enabled.

**Vapor Holdup Relaxation (Optional)**
When `vapor_holdup_relaxation_sec` is set (and hydraulic pressures are available):
```
MV_target,i = P_i * V_i / (Z_i * R * T_i)

d(MV_i)/dt += (MV_target,i - MV_i) / tau_v
```
Applied to internal stages only (condenser and no-holdup reboiler excluded).
