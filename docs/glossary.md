# Dynamic Distillation Glossary

This glossary collects the project-specific terms used across the runner, RHS,
logs, and issue discussions. The goal is consistency with the current codebase,
not textbook completeness.

## A

**Active area fraction**
- Fraction of tray cross-sectional area treated as hydraulically active.
- Used in tray hydraulic calculations such as Francis-weir liquid outflow.

## B

**Boilup**
- Vapor returned from the reboiler to the bottom tray.
- In logs and CLI, usually expressed as `lbmol/h`.

**Bottoms sump**
- Explicit liquid holdup at the bottom of the column, below the bottom tray.
- In the standard model, it is the source state for both bottoms draw and
  reboiler liquid feed.

**Bubble-point target**
- Temperature target obtained from a flash/bubble-point calculation for a given
  pressure and liquid composition.
- Used in some temperature-closure and equilibrium-relaxation paths.

## C

**Calibration mode**
- Runner runtime mode that uses the same closure set as parity mode, but is
  intended for calibration/parity checks.

**ColumnInputs**
- Per-step runtime inputs passed into `column_rhs(...)`.
- Carries boundary flows, thermo provider, model toggles, cached seeds, and
  control-related overrides.

**ColumnSpec**
- Immutable normalized model case built from Excel input.
- Holds tray profiles, geometry, duties, components, streams, and simulation
  defaults.

**Composition-only equilibrium relaxation**
- Equilibrium-relaxation mode that adjusts vapor composition at fixed vapor
  holdup rather than relaxing toward the flash phase split.
- Available as `equilibrium_relaxation_mode="composition-only"`.

**Condenser-duty mode**
- Setting that determines how condenser duty is handled.
- Current options are `total-condense` and `specified`.

## D

**Distillate drum / reflux drum**
- Explicit top liquid and vapor holdup above the condenser tray.
- Distillate draw is taken from this drum; reflux is sent from this drum back to
  the column.

**Distillate drum liquid fraction / top drum liquid fraction**
- Geometric fill-fraction style input for the reflux drum.
- Useful for true-level interpretation, UI display, and geometry-based volume
  inference.
- Secondary to explicit top-drum holdup when both are present.

**Dry Tray K**
- Hydraulic dry pressure-drop coefficient used in tray pressure calculations.

## E

**Energy mode**
- Short form for `vapor_flow_model="energy"`.
- Internal vapor traffic is solved from the tray energy closure instead of using
  the seeded profile directly.

**Energy residual**
- Difference between the assembled tray energy inflows/outflows and the current
  tray energy-state evolution.
- Logged in diagnostics such as `stage_energy_balance_resid_BTUps`.

**Equilibrium relaxation**
- Model path that nudges tray phase state toward thermo equilibrium on a finite
  time scale `tau_eq`.
- Current main modes are `phase-holdup` and `composition-only`.

## F

**Feed flashing at stage conditions**
- Optional behavior where feed liquid/vapor split is recomputed at the feed
  stage pressure/temperature conditions instead of relying only on workbook feed
  vapor fraction.

**Francis liquid hydraulics**
- The active internal liquid hydraulic closure used in the standard model.
- Based on weir flow and tray liquid holdup/geometry.

## H

**Hydraulic mode**
- Runner runtime mode that forces hydraulic pressure plus energy vapor closure.
- Current standard research path for the dynamic column branch.

**Hydraulic pressure**
- Tray pressure profile computed from hydraulic relations instead of taken
  directly from the seeded pressure profile.

## I

**IDA mode**
- Pilot implicit DAE-style stepper available in the runner.
- Uses fixed-point / algebraic closure logic rather than simple explicit Euler.

**Integrator fallback**
- Automatic switch from a requested stiff stepper back to explicit Euler for a
  problematic step when solve limits are hit.

## K

**K-state**
- Instantaneous dynamic-state phase ratio `y/x` on a tray.
- Logged separately from thermo-equilibrium `K`.

**K-thermo**
- Thermodynamic equilibrium `K` value from flash/property calculations at tray
  state.

## L

**Legacy mode**
- Runner runtime mode that preserves older Excel/CLI-driven behavior and is the
  only mode where startup hydraulic sequencing is active.

**Level control**
- Inventory control, not geometric vessel `% level`.
- Top loop acts on distillate draw; bottom loop acts on bottoms draw.

## M

**Mass closure**
- Consistency check between feed, draws, and total inventory change.
- Common diagnostics include `dM_total_dt_lbmolph` and
  `net_F_minus_D_minus_B_lbmolph`.

## N

**No-holdup reboiler**
- Special shortcut mode where the bottom reboiler stage is treated as a
  flow-through flash node rather than a tray with its own liquid holdup.
- This is not the standard/default mode.

## P

**Parity mode**
- Runner runtime mode that forces pressure/spec, vapor/profile, and liquid
  hydraulics override off.
- Used for seeded-profile comparison and parity checks.

**Phase-holdup equilibrium relaxation**
- Equilibrium-relaxation mode that relaxes toward the flash phase split, so
  vapor holdup as well as composition can move toward equilibrium.
- Available as `equilibrium_relaxation_mode="phase-holdup"`.

**Pressure-control MV**
- Manipulated variable used by the top-pressure controller.
- Current options are `condenser-duty` and `top-anchor`.

**Profile mode**
- Short form for using the seeded Excel liquid/vapor traffic as the active
  internal flow profile.

## R

**Reboiler duty**
- Heat input at the bottom end of the column, usually in `Btu/h`.
- Can be fixed, commanded directly, or used indirectly to compute boilup.

**Reboiler feed from sump**
- Current standard topology: liquid drains from the bottom tray to the sump,
  and the reboiler draws its liquid feed from the sump.

**Runtime mode**
- High-level runner mode that selects a consistent set of pressure/vapor/liquid
  closure defaults.
- Current active modes are `legacy`, `parity`, `calibration`, and `hydraulic`.

## S

**Selective PR**
- Shorthand for using live PR thermo selectively in a targeted subpath rather
  than switching the entire run to live PR.
- In recent work, this referred specifically to using live PR in the
  equilibrium-relaxation flash path while keeping the thermo table elsewhere.

**Specified-duty condenser**
- Condenser operation where duty is taken from a specified/commanded value
  rather than computed as a total-condensation requirement.

**Stage 1 condenser tray**
- Small transfer node representing the condenser-side tray state when an
  explicit reflux drum is modeled.
- It is not the same thing as the reflux drum holdup.

**StateVectorLayout**
- Declarative layout object that defines which state blocks exist and where they
  sit in the packed state vector.

**Steady-state score**
- Composite diagnostic score used by the runner’s steady-state detector.
- Built from inventory-rate, KPI-slope, MV-rate, temperature-rate, and optional
  setpoint-error criteria.

## T

**Top accumulator holdup**
- Explicit startup liquid inventory for the reflux drum, usually in `lbmol`.
- Authoritative startup inventory input when both holdup and top-drum liquid
  fraction are provided.

**Table surrogate / thermo table**
- Precomputed tabular thermo surrogate used for faster flash/property lookup.
- Can run in single-process `table` mode or multiprocess `table-pool` mode.

**Top anchor**
- Hydraulic top-pressure anchor used by the pressure model/controller in some
  operating modes.

**Top-drum startup steadying**
- Startup pass that attempts to reduce drift in explicit top-drum states before
  the main simulation loop begins.

## U

**UV / energy holdup states**
- State blocks that carry tray liquid/vapor energy explicitly:
  `tray_EL_BTU`, `tray_EV_BTU`.

## V

**Vapor holdup**
- Total vapor inventory on a tray or boundary node.
- Can be seeded from Excel or initialized from pressure and vapor-space logic.

**Vapor-holdup relaxation**
- Dynamic source term that relaxes tray vapor holdup toward a pressure- or
  thermo-consistent target over a finite time constant.

**Vapor-flow model**
- Internal vapor-traffic closure selection.
- Current main options are `profile`, `conductance`, and `energy`.

## Notes

- This glossary is intentionally project-specific.
- Historical terms from removed side branches may still appear in old notes and
  ledgers, but are not part of the active model path unless stated otherwise.
