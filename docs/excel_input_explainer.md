# Excel Input File Explainer

This document explains what the model reads from the Excel case file and how each field is used.

Source of truth in code:
- `src/dynamic_distillation/excel_case_loader_v1.py`
- `src/dynamic_distillation/column_spec_builder_v1.py`
- `src/dynamic_distillation/state_vector_layout_v1.py`
- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`

Related initialization policy:
- `docs/dynamic_column_initialization_strategy.md`

## Workbook Structure

Expected sheets:
- `Specifications` (required)
- `Initial Conditions` (required)
- `Streams` (optional; best effort)
- `Components` (optional but preferred over `Specifications` component row)
- `Boundary State` (optional restart sheet)
- `Energy State` (optional restart sheet)
- `Controller State` (optional restart sheet)
- `Dynamic Memory` (optional restart sheet)

If `Streams` is missing or malformed, the loader continues with `streams={}`.

## Fresh Runs vs Restart Runs

- A "fresh" run uses the base workbook only, without explicit runtime restart sheets.
- A restart run uses a workbook that also contains `Boundary State`, `Energy State`, `Controller State`, and optionally `Dynamic Memory`.

Current practical behavior:
- On this column, a fresh full-startup run has recently taken about `10-12 minutes` of wall-clock time before the first logged integration row appears.
- That startup time is spent aligning vapor holdup with startup pressure, conditioning thermo state, and steadying the top drum so the simulation starts from a dynamically consistent state.
- This startup work is important. It reduces pressure/holdup/thermo mismatch at `t=0` and improves the early integration trajectory.
- For the dependency-free relative-volatility validation case, the workbook intentionally carries explicit tray `Vapor Holdup (lbmol)`. Run it with `--use-excel-vapor-holdup` and keep `Vapor Holdup Relaxation (sec)=0` so pressure-based vapor-holdup relaxation does not erase the seeded vapor residence inventory.
- For Skogestad Column A Tier 1 validation, the workbook intentionally omits `Boundary State` because the source's 41 stages already include the total condenser and reboiler. Run that case with `--disable-boundary-states --disable-vapor-states --no-equilibrium` so the model topology matches the source's constant-molar-overflow equations with algebraic vapor composition.
- For Skogestad Column A dynamic disturbance checks, product stream component mole-flow cells should be blank. The source model withdraws products as `D*xD` and `B*xB`, so fixed distillate/bottoms component rates are not source-equivalent; only the feed uses fixed component rates.
- For the Gani 1986/ChemSep source-topology material parity check, use `validation_gani_1986_debutanizer_chemsep_source_topology.xlsx` and keep the ChemSep liquid and vapor profiles together. Run with `--disable-boundary-states --disable-vapor-states --no-equilibrium` and leave energy off. Do not replace ChemSep vapor composition with another PR backend unless you are solving a new model-topology steady state; doing so breaks the ChemSep component material balance.
- ChemSep and other external steady-state profiles should be treated as initialization seeds, not as automatically valid full dynamic initial conditions. The workbook may supply approximate `T/P/x/y/L/V`, duties, products, geometry, and holdup scale, but the dynamic model must still reconcile those values against its own topology, feed treatment, explicit vapor/liquid holdup states, and RHS equations before the state is accepted for validation or controller work. See `docs/dynamic_column_initialization_strategy.md`.

Completed-run restart export:
- Every completed run now writes a companion restart workbook into the run folder.
- That restart workbook contains the final dynamic state needed to continue a simulation without repeating most fresh-startup calculations.
- Restart runs also apply a short hidden re-entry settling pass before the first logged row so the resumed trajectory lands closer to the pre-stop state.
- Recommended workflow:
  - keep the base workbook as the case definition
  - run the case to a good conditioned state
  - use the generated restart workbook as the next run input when you want to continue from that state

Restart sheets are optional:
- `Boundary State`: top/bottom liquid and vapor holdups
- `Energy State`: tray liquid/vapor energy state
- `Controller State`: PI integrals and related controller memory

Validation-source topology exception:
- `Boundary State` should be absent for sources where the stage list already includes condenser/reboiler holdup states.
- `--disable-vapor-states` removes dynamic tray vapor holdup/composition states and lets the RHS compute vapor composition algebraically from liquid composition and the active thermo provider.
- Product draws should be represented by total flow only when the source equations remove products at current terminal composition. In the Skogestad Column A workbook, distillate and bottoms component mole-flow cells are intentionally blank for this reason.
- This mode is appropriate for source reproduction tests such as Skogestad Column A; it is not a substitute for the standard explicit drum/sump and vapor-holdup model used for plant-like dynamic cases.
- Imported steady profiles must match the topology, thermo, and state variables used in the run. A source-topology workbook can be steady with source vapor compositions and source terminal-stage assumptions, while the same profile can be non-steady if explicit drum/sump states, dynamic vapor holdup, energy states, or a different thermo backend are added without a new steady-state solve.
- For plant-like full dynamic cases, imported profiles are best viewed as high-quality initial guesses. Acceptance requires an initialization residual audit and profile/conservation gates, not just `steady_state_flag=1`.

## Specifications Sheet

### How it is parsed

- Sheet is read with `header=None`.
- Keys are matched case-insensitively against column 0 text.
- Value is taken as the last non-empty cell across columns 1..end for that row.

### Required keys

| Key | Type | Used for |
|---|---|---|
| `Number of Stages` | integer | Stage count validation and array sizes |
| `Number of Components` | integer | Component count validation |
| `Log Frequency (timesteps)` | integer > 0 | Default logging cadence |

### Optional keys (currently read)

| Key | Type | Used for |
|---|---|---|
| `Condenser Type` | string | Condenser behavior hints |
| `Condenser Duty (Btu/h)` | float | Energy balance duty term |
| `Reboiler Duty (Btu/h)` | float | Energy balance / boilup in duty mode |
| `Simulation Length (min)` | float | Default run horizon |
| `Timestep (sec)` | float | Default dt |
| `Top Accumulator Holdup (lbmol)` | float | Initial top liquid holdup total; authoritative startup inventory input when present |
| `Bottom Holdup (lbmol)` | float | Initial bottom liquid holdup total |
| `Top Drum Vapor Volume (ft3)` | float | Explicit top/reflux drum vapor-space volume for top-pressure state |
| `Top Drum Total Volume (ft3)` | float | Optional; used with liquid fraction/holdup to infer vapor-space volume |
| `Top Drum Diameter (ft)` | float | Optional; if paired with `Top Drum Length (ft)`, computes total drum volume (`pi/4*D^2*L`) |
| `Top Drum Length (ft)` | float | Optional; used with diameter to compute total drum volume |
| `Top Drum Liquid Fraction (-)` | float or % | Optional liquid fill fraction (`0..1` or `0..100`) for level/geometry interpretation and vapor-volume inference when explicit top holdup is absent |
| `Overhead Vapor Line Volume (ft3)` | float | Optional vapor-only add-on volume added to top-end vapor capacitance |
| `Condenser Vapor Volume (ft3)` | float | Optional vapor-only add-on volume added to top-end vapor capacitance |
| `Stage time constant [tau] (sec)` | float | Equilibrium relaxation tau; also used as the vapor-holdup relaxation fallback when `Vapor Holdup Relaxation (sec)` is absent |
| `Dry Tray K` | float | Hydraulic dry pressure drop coefficient |
| `Vapor Holdup Relaxation (sec)` | float | Dynamic vapor holdup relaxation; set `0` to disable pressure-based tray vapor-holdup relaxation and retain seeded tray vapor inventories |
| `Vapor Flow Relaxation (sec)` | float | Dynamic vapor flow relaxation |
| `Condenser Pressure Drop (psi)` | float | Fixed pressure drop from stage 2 to stage 1 in hydraulic pressure mode |
| `Reboiler Neighbor Vapor Hi Ratio` | float | Upper ratio bound for stage `N-1` vapor flow vs boilup in `vapor_flow_model="energy"` (runner fallback default `1.20`) |
| `Reboiler Neighbor Vapor Lo Ratio` | float | Lower ratio bound for stage `N-1` vapor flow vs boilup in `vapor_flow_model="energy"` (runner fallback default `0.80`) |
| `Thermo Refresh dT (F)` | float | Per-stage thermo refresh threshold |
| `Thermo Refresh dP (psia)` | float | Per-stage thermo refresh pressure threshold |
| `Thermo Refresh dX` | float | Per-stage thermo refresh composition threshold (`max(abs(dz_k))`) |
| `Thermo Mode` | string | Workbook-level thermo mode hint; `relative-volatility` selects the simple constant-alpha validation backend when the runner is launched with that mode |
| `Relative Volatility` | float | Alpha for the `relative-volatility` thermo backend; defaults to `1.6` when omitted |
| `Thermo Refresh Delta T (F)` | float | Alias for `Thermo Refresh dT (F)` |
| `Thermo Refresh Delta (F)` | float | Alias for `Thermo Refresh dT (F)` |
| `Thermo Refresh ΔT (F)` | float | Alias for `Thermo Refresh dT (F)` |
| `Distillate Composition SP` | float | Optional distillate composition setpoint read into `col.specs_raw` for distillate-composition control fallback |
| `Distillate C4 SP` | float | Alias for `Distillate Composition SP` |
| `Distillate x SP` | float | Alias for `Distillate Composition SP` |
| `Bottoms Composition SP` | float | Optional bottoms composition setpoint read into `col.specs_raw` for bottoms-composition control fallback |
| `Bottoms C5 SP` | float | Alias for `Bottoms Composition SP` |
| `Bottoms x SP` | float | Alias for `Bottoms Composition SP` |

### Control-related spec keys (runner support vs loader support)

The runner supports these keys in `col.specs_raw`:
- `Enable Level Control` / `Level Control Enabled`
- `Top Level PV Mode`, `Bottom Level PV Mode`
- `Top Level SP (lbmol)` / `Top Drum Level SP (lbmol)` / `Reflux Drum Level SP (lbmol)`
- `Bottom Level SP (lbmol)` / `Bottom Sump Level SP (lbmol)`
- `Top Drum Liquid Fraction (-)` / related fill-fraction aliases
- `Bottom Sump Liquid Fraction (-)` / related fill-fraction aliases
- `Top Level Kc`, `Top Level Ti (sec)`
- `Bottom Level Kc`, `Bottom Level Ti (sec)`
- `Top Drum Total Volume (ft3)` / `Top Drum Diameter (ft)` + `Top Drum Length (ft)`
- `Bottom Sump Total Volume (ft3)` / `Bottom Sump Diameter (ft)` + `Bottom Sump Height (ft)`
- `Enable Pressure Control` / `Pressure Control Enabled`
- `Top Pressure SP (psia)` / `Condenser Pressure SP (psia)`
- `Top Pressure Kc`, `Top Pressure Ti (sec)`
- `Pressure Control MV` / `Pressure Controller MV` / `Pressure MV`
- `Enable Top PSV` / `Top PSV Enabled` / `Top Drum PSV Enabled`
- `Top PSV SP (psia)` / `Top PSV Setpoint (psia)`
- `Top PSV Gain (lbmol/s/psi)` / `Top PSV Gain (lbmolps/psi)`
- `Top PSV Max Vent (lbmol/s)` / `Top PSV Max (lbmol/s)`
- `Equilibrium Relaxation Mode`
- `Equilibrium Tau (sec)` / `Equilibrium Relaxation Tau (sec)`
- `Equilibrium Energy Damping Gain`
- `Equilibrium Relaxation Live PR`
- `Hydraulic Energy Temperature Follow Tau (sec)`
- `Distillate Composition SP` / `Distillate C4 SP` / `Distillate x SP`
- `Bottoms Composition SP` / `Bottoms C5 SP` / `Bottoms x SP`

Current limitation:
- `excel_case_loader_v1.py` currently persists only the explicitly listed spec keys in this document.
- Distillate/bottom composition setpoints are now persisted from Excel aliases listed above.
- Many control enable/tuning keys above (level/pressure/PSV and most PI knobs) are still not reliably available from Excel yet.
- For now, use CLI flags (`--enable-level-control`, `--enable-pressure-control`, `--enable-top-psv`, etc.) to configure these loops.

### Geometry table (optional block in Specifications)

The loader looks for a table header containing both `Start Stage` and `End Stage`, then reads:
- `Start Stage`
- `End Stage`
- `Diameter (ft)` (any header containing `diam`)
- `Tray Spacing (ft)` (any header containing `spacing`)
- `Gas Void Fraction` (optional)
- `Weir Height` column (optional)
- `Weir Length` column (optional)
- `Active Area` column (optional)
- `System Factor` / `Hydraulic Factor` column (optional; used as tray hydraulic C multiplier)

Notes:
- `Gas Void Fraction` and `Active Area` accept either fraction (`0..1`) or percent (`0..100`).
- Rows are read until `Start Stage` is blank.
- Parsed rows are stored as `specs["Geometry Sections"]` and expanded in `column_spec_builder_v1`.
- At minimum, the geometry table must retain both `Diameter (ft)` and `Tray Spacing (ft)`. If workbook cleanup removes either of those columns, `Geometry Sections` will not load and the hydraulic pressure model will fall back to non-hydraulic pressure behavior.

### Reflux Drum Geometry Keys (optional)

The loader also reads reflux-drum geometry aliases into canonical keys:
- `Top Drum Vapor Volume (ft3)` (aliases include `Top Accumulator Vapor Volume (ft3)`, `Reflux Drum Vapor Volume (ft3)`, `Distillate Drum Vapor Volume (ft3)`)
- `Top Drum Total Volume (ft3)` (aliases include `Top Accumulator/Reflux/Distillate Drum Volume (ft3)`)
- `Top Drum Diameter (ft)` and `Top Drum Length (ft)` (aliases include `Top Accumulator ...`, `Reflux Drum ...`, `Distillate Drum ...`)
- `Top Drum Liquid Fraction (-)` (aliases include `... Liquid Volume Fraction`, `... Fill Fraction`)
- `Overhead Vapor Line Volume (ft3)` and `Condenser Vapor Volume (ft3)` (vapor-only adders)

Volume inference precedence in runner:
1. Explicit vapor volume (`Top Drum Vapor Volume (ft3)`), else
2. Total volume + liquid fraction, else
3. Diameter+length -> total volume, then:
   - use explicit top holdup first when provided;
   - else use liquid fraction if provided;
   - else estimate liquid volume from top holdup + thermo liquid density when possible;
   - else assume half-full.

Startup inventory precedence for the reflux drum:
1. `Top Accumulator Holdup (lbmol)` / `Top Drum Holdup (lbmol)` / `Reflux Drum Holdup (lbmol)` if present.
2. `Top Drum Liquid Fraction (-)` and related fill-fraction aliases only when explicit top holdup is absent.

Interpretation:
- `Top Accumulator Holdup (lbmol)` is the authoritative startup liquid inventory for the reflux drum.
- `Top Drum Liquid Fraction (-)` is still useful for true-level control, UI display, and geometry-based inference, but it is treated as secondary when an explicit top holdup is available.

Dynamic behavior:
- If total drum volume is available (`Top Drum Total Volume (ft3)` or inferred from `Diameter/Length`), the model updates top vapor volume every timestep from current top liquid holdup and inferred liquid density.
- If only vapor volume is available, the runner tries to infer total volume from initial top holdup plus thermo liquid density.
- If total volume still cannot be inferred, vapor volume is treated as fixed.
- If overhead/condenser vapor adders are provided:
  - for `Condenser Type = Total`, pressure-side vapor capacitance uses these adders (drum vapor is excluded),
  - otherwise they are added to effective top-end vapor capacitance (vapor-only contribution).

### Components source

Order of precedence:
1. `Components` sheet (preferred)
2. `Specifications` row labeled `Component Name` with names across columns 1..end

Component names are canonicalized to DWSIM IDs during load.

### Important current behavior

At present, the loader persists explicitly supported keys (including `Pressure Model` and `Vapor Flow Model`), but most arbitrary free-form spec rows are not retained automatically.
Runtime precedence for pressure/vapor model selection is:
- `--runtime-mode parity` (CLI default): forces `pressure_model=spec`, `vapor_flow_model=profile`, and liquid-hydraulic override off.
- `--runtime-mode hydraulic`: forces `pressure_model=hydraulic`, `vapor_flow_model=energy`, leaves liquid-hydraulic override plus vapor-holdup relaxation off unless explicitly enabled, and defaults feed-stage flashing off unless explicitly requested so imported steady profiles stay closer to the workbook seed.
- `--runtime-mode legacy`: uses Excel/CLI behavior; `Pressure Model` and `Vapor Flow Model` are honored when valid.
- In `legacy`, if no valid model strings are provided, defaults are: `pressure_model=hydraulic` when geometry exists (else `spec`), then `vapor_flow_model=energy` when pressure is hydraulic (else `profile`).
- Startup hydraulic sequencing flags apply only in `legacy`; they are ignored in `parity` and `hydraulic`.

## Initial Conditions Sheet

### Required columns

| Column | Type | Purpose |
|---|---|---|
| `Stage` | integer sequence `1..N` | Stage indexing and validation |
| `Temperature (F)` | float | Initial tray temperatures |
| `Pressure (psia)` | float | Spec pressure profile |
| `Vapor Flow (lbmol/h)` | float | Base vapor profile |
| `Liquid Flow (lbmol/h)` | float | Base liquid profile |
| `Liquid Composition Component i` | float | Initial tray liquid composition (`i=1..Nc`) |
| `Vapor Composition Component i` | float | Initial tray vapor composition (`i=1..Nc`) |

Validation:
- Exactly `N` rows must exist.
- `Stage` must be exactly `1,2,...,N` in order.
- No NaN in required numeric columns.
- Each composition row sum must be near 1.0 (`tol=5e-6`).

### Optional columns

| Column | Type | Purpose |
|---|---|---|
| `Liquid Holdup (lbmol)` | float | Initializes `M_L_lbmol` tray holdup |
| `Vapor Holdup (lbmol)` | float | Initializes `M_V_lbmol` tray holdup if `--use-excel-vapor-holdup` is enabled; otherwise tray vapor holdup is cleared and re-initialized from the pressure profile. To keep these values during the run, set `Vapor Holdup Relaxation (sec)` to `0` or omit pressure-based vapor-holdup relaxation deliberately. |

If optional holdup columns are absent/all-NaN, model defaults from existing spec/state logic are used.

## Streams Sheet (Optional)

### Expected layout

- Find header row where first cell is `Stream`.
- Stream names are taken from columns 1..end of that header row.
- Scalar rows are read until `Mole flows (lbmol/h)`.
- Then a component flow block is read.

### Recognized scalar row labels

- `Stage`
- `Pressure (psia)`
- `Vapour Fraction`
- `Temperature (F)`
- `Total Molar Flow (lbmol/h)`

### Component flow block

- Starts at row labeled exactly `Mole flows (lbmol/h)`.
- Subsequent rows: first column is component name, each stream column is component molar flow.
- Stored under each stream as `Component Mole Flows (lbmol/h)`.

### Stream data usage examples

- Feed/top/bottom boundary flows and compositions.
- Initial top drum / bottom sump composition hints in state initialization.
- Optional bottom sump temperature initialization from bottoms stream temperature.
- In the standard explicit-sump model, the bottom sump is the source state for
  both bottoms draw and reboiler liquid feed.

## What Gets Used in Simulation

High-level mapping:
- `Specifications` + `Initial Conditions` -> validated `ColumnSpec`
- `ColumnSpec` + `Streams` -> runtime `ColumnInputs` and initial state vector
- RHS computes dynamic `L_out/V_out`, pressures, compositions, energy residuals each step

Important nuance:
- The steady-state `Vapor Flow/Liquid Flow` profiles from `Initial Conditions` are used directly as the internal baseline profile.
- Runtime may still modify vapor flow through `vapor_flow_model="energy"` and always enforces boundary endpoints (`V_out[1]=0`, `V_out[N]=boilup`, `L_out[1]=reflux`).
- In `vapor_flow_model="energy"`, the feed stage vapor outflow is solved dynamically (not pinned to the input profile).
- Feed split into liquid/vapor source terms can be recomputed by TP flash at feed-stage pressure when a thermo provider is active; the stream `Vapour Fraction` is then only a fallback.
- Stream component molar-flow keys are matched case/format-insensitively when mapping to model components.
- If level control is enabled, distillate and bottoms draw rates are adjusted dynamically each step by PI loops using top/bottom liquid holdup (`lbmol`) as PVs.
- Vessel geometry to convert holdup to physical level (`%` or `ft`) is not implemented yet.

## Common Formatting Pitfalls

- Missing exact column names in `Initial Conditions`.
- `Stage` not strictly `1..N` ordered.
- Composition rows not summing to 1.
- `Streams` row label typo (`Mole flows (lbmol/h)` must match).
- Adding new spec rows and expecting automatic use without loader support.

## Quick Authoring Checklist

1. Fill required `Specifications` keys and verify numeric fields.
2. Ensure `Initial Conditions` has exact required headers and no NaN.
3. Verify each stage liquid/vapor composition row sums to 1.
4. If using streams, verify `Stream` header row and exact scalar labels.
5. If using geometry, include `Start/End Stage`, diameter, and spacing columns.

## Runtime Preflight Validation

Before the timestep loop starts, the runner performs a preflight validation and prints:
- `"[Validation] PASS ..."` for non-blocking startup.
- `"[Validation][Warn] ..."` for suspicious values/defaulted settings.
- `"[Validation] FAIL ..."` and `"[Validation][Error] ..."` if startup must stop.

