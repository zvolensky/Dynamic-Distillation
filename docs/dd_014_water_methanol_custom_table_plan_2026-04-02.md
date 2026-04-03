## Water-Methanol Custom Table Plan

Date: 2026-04-02

### Scope

This note defines a first-pass thermo-table envelope for the current
water-methanol 10-stage ChemSep-seeded case, using:

- [water_methanol_template_10stage_chemsep_seed_20260401.xlsx](/C:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/water_methanol_template_10stage_chemsep_seed_20260401.xlsx)
- [water-methanol-ChemSep.xls](/C:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/water-methanol-ChemSep.xls)

This is not a water-ethanol table plan. The files currently available in the
workspace are for water-methanol, so the concrete numeric proposal below is for
that system.

### Observed Envelope

From the ChemSep seed workbook and companion ChemSep export:

- Tray temperature range: `148.658 F` to `206.942 F`
- Tray pressure range: `14.6959 psia` to `14.6959 psia`
- Liquid composition range, water: `0.0144239` to `0.985576`
- Vapor composition range, water: `0.00597427` to `0.898693`
- Feed stage: `8`
- Feed temperature: `163.642 F`
- Feed pressure: `14.6959 psia`

From the completed `60 s` parity UNIFAC run:

- Top pressure drifted down to about `14.36377 psia`
- Bottom pressure remained about `14.69573 psia`
- Tray temperatures remained inside the seeded `148.658 F` to `206.942 F` band

### Proposed Table Envelope

The table should cover slightly more than the steady-state case, with extra room
on the high side for dynamic excursions:

- Temperature range: `140.0 F` to `235.0 F`
- Pressure range: `12.0 psia` to `25.0 psia`

Rationale:

- `Tmin=140 F` keeps a modest cushion below the observed top-tray temperature.
- `Tmax=235 F` gives about `28 F` of headroom above the hottest seeded tray.
- `Pmin=12 psia` covers the observed top-pressure sag plus margin.
- `Pmax=25 psia` gives substantial upward room for condenser/top-end dynamic drift.

### Proposed Grid Density

First-pass grid:

- `n_T = 21`
- `n_P = 11`

This is dense enough for a binary case without making the table unnecessarily
large. If interpolation error near the top section is still high, increase the
temperature grid before increasing pressure density.

### Proposed Composition Anchors

For this binary system, use explicit water-composition anchors rather than only
sparse stage anchors. Recommended `x_water` anchor set:

`[0.0, 0.005, 0.01, 0.0144239, 0.02, 0.03, 0.0348168, 0.05, 0.0675978, 0.10, 0.120157, 0.16, 0.20379, 0.28, 0.333678, 0.42, 0.518999, 0.62, 0.719926, 0.82, 0.920414, 0.96, 0.985576, 0.995, 1.0]`

Notes:

- Includes exact stage-liquid seed compositions from the ChemSep profile.
- Adds extra density near the distillate end, bottoms end, and mid-column swing region.
- Keeps pure-component endpoints explicitly represented.

### Top-End Handling

If a dedicated top-end helper table is used, it should come from the same live
thermo model as the main table. For this case, the top section is methanol-rich,
so the top-end composition window should be biased toward low water mole fraction:

- Suggested top-end `x_water` focus region: `0.0` to `0.20`
- Suggested denser top-end anchors:
  `0.0, 0.002, 0.005, 0.01, 0.0144239, 0.02, 0.03, 0.05, 0.08, 0.12, 0.16, 0.20`

### Source Model Requirement

The current repo table builder is PR-backed. That is acceptable for hydrocarbon
cases but is not the recommended source model for this water-methanol case.

Recommended source model for any serious custom table:

- `UNIFAC`, or
- `NRTL`

Using the current PR-backed table path as-is would only be appropriate for rough
smoke/parity acceleration, not for trusted dynamic results.

### Validation Required

Before using a custom table in parity or hydraulic runs, compare it against the
live source model on:

- Tray `K` values
- `HL` and `HV`
- Liquid density
- Top-end bubble-point behavior
- Short parity trajectory (`5 s` to `60 s`)
- Product compositions at top and bottom

Suggested acceptance targets:

- `K` relative error: small enough that tray-composition trends match the live model
- `HL/HV` error: small enough to preserve boilup/condenser behavior over short runs
- Pressure/composition trajectories: no material top-end drift relative to live thermo

