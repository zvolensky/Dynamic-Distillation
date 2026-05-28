# Validation Candidate Scorecard

Updated: 2026-05-26

Purpose: keep validation-source selection disciplined. A candidate is useful only if it can be reproduced from published/source data and can test model physics that the current implementation actually represents.

## Validation Tiers

| Tier | Role | Acceptance Standard | Current Status |
|---|---|---|---|
| Tier 1 | Source-topology/material-balance validation | Reproduce a documented or source-code reference case within stated numeric tolerances. | Accepted for Skogestad Column A constant-relative-volatility case. |
| Tier 2 | Richer model-physics development benchmark | Exercise energy states, vapor holdup, liquid hydraulics, pressure behavior, and controls where applicable; comparison may be qualitative/digitized if the source lacks tables. | Pending. Candidate sources identified, none accepted. |
| Tier 3 | Real-chemical/experimental validation | Compare against published experimental or plant data with named components, operating conditions, and dynamic response data. | Pending. |

## Acceptance Policy

`steady_state_flag` and `steady_state_score` are diagnostics, not validation acceptance criteria by themselves. A validation case is accepted only when the run is compared with an external/source reference or with explicit case-specific KPI tolerances.

The Skogestad Tier 1 workflow is the current accepted pattern: use source-equivalent topology and product draws, confirm a steady/source-equivalent baseline, then compare steady profiles and dynamic disturbance response against the source equations. Future Tier 2 and Tier 3 cases should keep the same distinction between numerical steadiness and source agreement.

## Candidate Summary

| Candidate | System | Source Type | Dynamic Data | Thermo Burden | Physics Fit | Reproducibility | Recommended Use |
|---|---|---|---|---|---|---|---|
| Skogestad Column A (`cola.dat` / `colamod.m`) | Hypothetical binary, alpha = 1.5 | Public source equations/data | Yes, by direct source translation | Constant relative volatility | Excellent for material balance and liquid-holdup dynamics; excludes energy, vapor holdup, named chemicals, density, and controllers | High | Accepted Tier 1 baseline. |
| Gani/Ruiz/Cameron industrial debutanizer via ChemSep seed | 1,3-butadiene / isobutene / n-pentane / 1-pentene / 1-hexene / benzene | ChemSep steady-state reconstruction from literature-derived case data | Not yet accepted | ChemSep PR for source parity; Clapeyron PR mismatch under separate model-topology attempt | Useful real-component material-balance parity check when source topology is matched; not yet valid for explicit drum/sump, vapor holdup, energy, or hydraulics | Medium | Accepted only as a narrow source-topology material-balance parity check; full rigorous validation remains open under `DD-030`. |
| Relative-volatility 30-stage internal case | N-butane / n-pentane labels with constant alpha | Internal synthetic case | Internal only | Constant relative volatility | Good capability scaffold for energy states and vapor inventory; not external validation | High internally | Fast regression/capability probe only. |
| Wittgens & Skogestad 2000 experimental column | Ethanol / butanol | Experimental + model paper | Yes, mostly plots | UNIFAC/NRTL likely needed for temperature-response validation | Strong tray-hydraulic/holdup fit; includes real column behavior | Medium; chart digitization and thermo setup required | Tier 3 candidate after runtime strategy is acceptable. |
| Kooijman 1995 dynamic nonequilibrium thesis | BTX design case; extractive n-heptane/toluene/phenol; acetone/water absorber; debutanizer/depropanizer examples | Simulation thesis | Yes, plots | Mixed; BTX uses UNIFAC + Antoine + PR vapor; other cases use UNIQUAC/NRTL/DECHEMA models | Strong for model-physics exploration; includes tray design, pressure drop, holdup variants, vapor holdup effects, and energy/nonequilibrium dynamics | Medium for development benchmark; low for validation because no experimental dynamic comparison was carried out | Tier 2 literature benchmark only; not Tier 3 validation. |
| Hoffmann et al. 2020 pressure-driven model | Benzene / toluene | Simulation benchmark/model paper | Yes, plots | Light; ideal/Raoult-style benzene-toluene | Strong for energy, pressure-driven vapor/liquid flow, vapor holdup, and tray hydraulics; startup/shutdown focus is a mismatch for current dry-tray capability | Medium | Tier 2 development benchmark only if initialized as an already-wet operating disturbance or if dry-start logic is added. |
| Choe & Luyben 1987 rigorous dynamic models | Reported examples include xylene/toluene vacuum-column behavior in later citations | Simulation/model paper | Likely, but full article inspection needed | Light for xylene/toluene if Raoult/Antoine | Conceptually strong for vapor holdup and pressure dynamics | Unknown until full article is inspected | Keep searching; promising but not validation-ready. |
| Yiu, Carling & Wood 1990 depropanizer | Light hydrocarbons | Dynamic/control study | Likely plots | PR/SRK or hydrocarbon K-values | Good operating disturbance/control fit; thermo and details may be heavier | Unknown until full article is inspected | Secondary candidate if sufficient case details are available. |
| Kender et al. 2018 ASU pressure-driven model | N2 / O2 / Ar | Simulation/model paper | Startup plots | Cryogenic thermo; not necessarily simple ideal | Strong pressure/energy/holdup concepts; startup-focused and industrial double-column complexity | Low to medium | Conceptual reference, not near-term validation. |

## Current Accepted Baselines

### Skogestad Column A, steady profile

- Accepted run: `logs/validation_skogestad_column_a_rv_source_topology_productdraw_300s/column_summary_20260524_214800.csv`
- Source-equivalent run requirements:
  - `--disable-boundary-states`
  - `--disable-vapor-states`
  - `--no-equilibrium`
  - source-equivalent product draws (`D*xD`, `B*xB`), not fixed product component mole flows
- Comparison result: source `x/y` profiles matched to numerical precision (`max_abs_x_error` and `max_abs_y_error` about `8e-13`).

### Skogestad Column A, +1% feed-rate disturbance

- Accepted profile: `logs/validation_skogestad_column_a_rv_feed_F101_500min_linearL_productdraw/column_profile_20260524_215349.csv`
- Comparison reference: direct Python translation of Skogestad `colamod.m`.
- Endpoint errors:
  - `endpoint_max_abs_x_error = 1.04e-05`
  - `endpoint_max_abs_m_error = 1.72e-04`
- Comparative plots are in the accepted run folder.

### Gani 1986/ChemSep debutanizer, source-topology material parity

- Accepted workbook: `validation_gani_1986_debutanizer_chemsep_source_topology.xlsx`
- Accepted run: `logs/gani_chemsep_source_topology_material_60s/column_summary_20260525_220943.csv`
- Companion note: `docs/gani_1986_validation_note.md`
- Source-equivalent run requirements:
  - preserve the ChemSep liquid and vapor profiles together
  - `--disable-boundary-states`
  - `--disable-vapor-states`
  - `--no-equilibrium`
  - energy off
- Accepted result:
  - `steady_state_flag = 1`
  - `steady_state_score = 1.08e-05`
  - `ss_max_rel_state_rate_per_s = 3.24e-08/s`

This is a limited real-component material-balance check. It does not validate
explicit condenser drum behavior, explicit bottom sump behavior, tray vapor
holdup, pressure hydraulics, energy balances, condenser/reboiler duty dynamics,
or Clapeyron PR equivalence to ChemSep PR.

Regression command:

```powershell
python tools\check_gani_source_topology_parity.py
```

## Internal Tier 2 Capability Probe

Run on 2026-05-25:

```powershell
python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --excel validation_relative_volatility_energy_30stage.xlsx `
  --run-name tier2_capability_probe_rv_energy_liqhyd_10s `
  --run-description "Internal Tier 2 capability probe: relative-volatility energy states, preserved vapor holdup, linear liquid holdup hydraulics, small feed-rate step." `
  --runtime-mode hydraulic `
  --thermo relative-volatility `
  --include-energy `
  --use-excel-vapor-holdup `
  --vapor-holdup-relaxation-sec 0 `
  --enable-liquid-hydraulic-override `
  --liquid-hydraulic-model linear-holdup `
  --liquid-hydraulic-htc-sec 10 `
  --feed-step-time 2 `
  --feed-step-scale 1.02 `
  --dt 0.2 `
  --n-steps 50 `
  --log-every 5 `
  --logs-dir logs\tier2_capability_probe_rv_energy_liqhyd_10s `
  --allow-repeat-command
```

Outcome:

- Completed successfully in about `19 s` wall-clock total, with runtime marching around `6.4 sim-s/wall-s` after startup.
- Output summary: `logs/tier2_capability_probe_rv_energy_liqhyd_10s/column_summary_20260525_144133.csv`
- The run is not steady after the disturbance: final `steady_state_score = 198.5`, `ss_max_rel_state_rate_per_s = 0.595`, and `ss_max_temp_rate_F_per_s = 22.7`.
- The input workbook lacks `Geometry Sections`, so hydraulic pressure and Francis tray hydraulics are unavailable. `P_psia_hyd` remains blank in the profile; this is not a real pressure-hydraulic benchmark.
- The small feed step still produced aggressive top-end and temperature dynamics. By `10 s`, stage temperatures spanned roughly `7.9 F` to `433 F`, and stage 1 liquid holdup dropped from `5.0` to about `0.92 lbmol`.

Interpretation: this is a useful stress probe, not a validation case. It confirms that the current dependency-free RV scaffold can run fast with energy states, vapor inventory, and liquid-holdup override, but a credible Tier 2 benchmark needs a geometry-bearing workbook and a more controlled operating disturbance.

## Kooijman 1995 Dive Notes

Source inspected: `Dynamic Nonequilibrium Column Simulation`, H.A. Kooijman, Clarkson University dissertation, 1995. Accessible OCR text is available at `https://paperzz.com/doc/7161588/dynamic-nonequilibrium-column-simulation-hendrik`.

Key findings:

- The thesis explicitly says dynamic experimental data were virtually absent and that no comparison with data was carried out. That makes it a development benchmark, not external validation.
- The BTX design-mode example uses a 28-valve-tray benzene/toluene/p-xylene column with feed at the middle of the column. Thermo is UNIFAC + Antoine for liquid/vapor-pressure behavior and Peng-Robinson for vapor, including excess enthalpies.
- The BTX disturbance sequence is useful but not fully tabular: an initial boilup-ratio change, then after 10 min a reflux-ratio increase combined with a total-feed-flow decrease to avoid flooding. Figures 5.1 and 5.2 plot internal liquid flows over about 0-120 s and 600-720 s, respectively.
- The BTX case used automatic design at 75% flooding. The OCR text indicates two-pass and three-pass valve-tray sections with approximate diameters around 2.3 m and 2.7 m and flowpath lengths around 1 m, but the recovered text is too garbled to build a confident workbook without the original PDF/pages.
- The debutanizer/depropanizer material is more directly relevant to vapor holdup. A Gani et al. industrial debutanizer is perturbed with a 5% reflux-rate increase at constant reboiler duty; Figure 5.12 plots liquid flows over 0-300 s. A separate high-pressure depropanizer example discusses vapor holdup above the froth, downcomer liquid holdup, and compares two- vs four-holdup models with tray temperatures and product impurity plots on logarithmic time axes.
- Several Kooijman examples require physics outside the current model's validation target, especially nonequilibrium mass/heat transfer, downcomer holdup separation, vapor holdup above froth, weeping/entrainment-adjacent tray hydrodynamics, and activity-coefficient thermo.

Assessment: Kooijman is valuable for Tier 2 development and for understanding which holdups matter, especially vapor holdup at pressure. It should not be treated as a validation source unless paired with the original Gani et al. experimental/simulation source or another external data source that supplies reproducible inputs and response traces.

## Source Selection Rules Going Forward

Prefer candidates that satisfy all of these:

- already-wet operating column before the disturbance
- named chemicals or fully specified constant-alpha surrogate
- stage energy balances
- liquid holdup/hydraulic behavior that maps to our available closures
- vapor holdup or pressure dynamics if the source provides enough parameters
- dynamic response plots or tables with disturbance magnitude and duration
- enough operating data to build an input workbook without reverse-engineering the whole paper

Avoid treating these as validation-ready:

- dry-tray startup/shutdown cases unless dry-start logic is intentionally added
- sources where downcomer dynamics, weeping, entrainment, or heat loss dominate the response and cannot be disabled or approximated
- papers with only qualitative plots and insufficient operating conditions
- purely synthetic A/B cases with no published response trajectory

## Recommended Next Actions

1. Build or adapt a geometry-bearing, already-wet Tier 2 scaffold using simple thermo before chasing another source.
2. Continue source search for operating disturbance cases with energy, vapor holdup/pressure dynamics, and digitizable time-series response.
3. Inspect full text for Choe & Luyben 1987 and Yiu/Carling/Wood 1990 before investing in input templates.
4. Defer Wittgens/Skogestad ethanol-butanol UNIFAC/NRTL until a short live-thermo probe shows acceptable runtime or a cached thermo-table approach is ready.
