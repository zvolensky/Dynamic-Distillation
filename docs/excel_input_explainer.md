# Excel Input File Explainer

This document explains what the model reads from the Excel case file and how each field is used.

Source of truth in code:
- `src/dynamic_distillation/excel_case_loader_v1.py`
- `src/dynamic_distillation/column_spec_builder_v1.py`
- `src/dynamic_distillation/state_vector_layout_v1.py`
- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`

## Workbook Structure

Expected sheets:
- `Specifications` (required)
- `Initial Conditions` (required)
- `Streams` (optional; best effort)
- `Components` (optional but preferred over `Specifications` component row)

If `Streams` is missing or malformed, the loader continues with `streams={}`.

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
| `Top Accumulator Holdup (lbmol)` | float | Initial top liquid holdup total |
| `Bottom Holdup (lbmol)` | float | Initial bottom liquid holdup total |
| `Top Drum Vapor Volume (ft3)` | float | Explicit top/reflux drum vapor-space volume for top-pressure state |
| `Top Drum Total Volume (ft3)` | float | Optional; used with liquid fraction/holdup to infer vapor-space volume |
| `Top Drum Diameter (ft)` | float | Optional; if paired with `Top Drum Length (ft)`, computes total drum volume (`pi/4*D^2*L`) |
| `Top Drum Length (ft)` | float | Optional; used with diameter to compute total drum volume |
| `Top Drum Liquid Fraction (-)` | float or % | Optional liquid fill fraction (`0..1` or `0..100`) for vapor-volume inference |
| `Stage time constant [tau] (sec)` | float | Equilibrium relaxation tau; fallback for vapor holdup relaxation |
| `Dry Tray K` | float | Hydraulic dry pressure drop coefficient |
| `Vapor Holdup Relaxation (sec)` | float | Dynamic vapor holdup relaxation |
| `Vapor Flow Relaxation (sec)` | float | Dynamic vapor flow relaxation |
| `Condenser Pressure Drop (psi)` | float | Fixed pressure drop from stage 2 to stage 1 in hydraulic pressure mode |
| `Reboiler Neighbor Vapor Hi Ratio` | float | Upper ratio bound for stage `N-1` vapor flow vs boilup in `vapor_flow_model="energy"` (runner fallback default `1.20`) |
| `Reboiler Neighbor Vapor Lo Ratio` | float | Lower ratio bound for stage `N-1` vapor flow vs boilup in `vapor_flow_model="energy"` (runner fallback default `0.80`) |
| `Thermo Refresh dT (F)` | float | Per-stage thermo refresh threshold |
| `Thermo Refresh dP (psia)` | float | Per-stage thermo refresh pressure threshold |
| `Thermo Refresh dX` | float | Per-stage thermo refresh composition threshold (`max(abs(dz_k))`) |
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
- `Top Level SP (lbmol)` / `Top Drum Level SP (lbmol)` / `Reflux Drum Level SP (lbmol)`
- `Bottom Level SP (lbmol)` / `Bottom Sump Level SP (lbmol)`
- `Top Level Kc`, `Top Level Ti (sec)`
- `Bottom Level Kc`, `Bottom Level Ti (sec)`
- `Enable Pressure Control` / `Pressure Control Enabled`
- `Top Pressure SP (psia)` / `Condenser Pressure SP (psia)`
- `Top Pressure Kc`, `Top Pressure Ti (sec)`
- `Pressure Control MV` / `Pressure Controller MV` / `Pressure MV`
- `Enable Top PSV` / `Top PSV Enabled` / `Top Drum PSV Enabled`
- `Top PSV SP (psia)` / `Top PSV Setpoint (psia)`
- `Top PSV Gain (lbmol/s/psi)` / `Top PSV Gain (lbmolps/psi)`
- `Top PSV Max Vent (lbmol/s)` / `Top PSV Max (lbmol/s)`
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

### Reflux Drum Geometry Keys (optional)

The loader also reads reflux-drum geometry aliases into canonical keys:
- `Top Drum Vapor Volume (ft3)` (aliases include `Top Accumulator Vapor Volume (ft3)`, `Reflux Drum Vapor Volume (ft3)`, `Distillate Drum Vapor Volume (ft3)`)
- `Top Drum Total Volume (ft3)` (aliases include `Top Accumulator/Reflux/Distillate Drum Volume (ft3)`)
- `Top Drum Diameter (ft)` and `Top Drum Length (ft)` (aliases include `Top Accumulator ...`, `Reflux Drum ...`, `Distillate Drum ...`)
- `Top Drum Liquid Fraction (-)` (aliases include `... Liquid Volume Fraction`, `... Fill Fraction`)

Volume inference precedence in runner:
1. Explicit vapor volume (`Top Drum Vapor Volume (ft3)`), else
2. Total volume + liquid fraction, else
3. Diameter+length -> total volume, then:
   - use liquid fraction if provided;
   - else estimate liquid volume from top holdup + thermo liquid density when possible;
   - else assume half-full.

Dynamic behavior:
- If total drum volume is available (`Top Drum Total Volume (ft3)` or inferred from `Diameter/Length`), the model updates top vapor volume every timestep from current top liquid holdup and inferred liquid density.
- If only vapor volume is available, the runner tries to infer total volume from initial top holdup plus thermo liquid density.
- If total volume still cannot be inferred, vapor volume is treated as fixed.

### Components source

Order of precedence:
1. `Components` sheet (preferred)
2. `Specifications` row labeled `Component Name` with names across columns 1..end

Component names are canonicalized to DWSIM IDs during load.

### Important current behavior

At present, the loader persists explicitly supported keys (including `Pressure Model` and `Vapor Flow Model`), but most arbitrary free-form spec rows are not retained automatically.
Runtime precedence for pressure/vapor model selection is:
- `--runtime-mode parity` (CLI default): forces `pressure_model=spec`, `vapor_flow_model=profile`, and liquid-hydraulic override off.
- `--runtime-mode hydraulic`: forces `pressure_model=hydraulic`, `vapor_flow_model=energy`, and liquid-hydraulic override on.
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
| `Vapor Holdup (lbmol)` | float | Initializes `M_V_lbmol` tray holdup if `--use-excel-vapor-holdup` is enabled; otherwise tray vapor holdup is cleared and re-initialized from pressure profile. |

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

