# Core V3 water-methanol Clapeyron density qualification

- Result: `clapeyron_density_model_qualified`
- Selected density model: `VTPR`
- Decision: `authorize_vtpr_density_only_provider_route`
- States checked per model: `20`
- Nonlinear solve or timestep: `False`
- Workbook modified: `False`

| Model | Max density difference | Median difference | Max derivative change | Pass |
|---|---:|---:|---:|---:|
| VTPR | 4.174277e-02 | 1.734590e-02 | 1.603979e-09 | True |
| CPA | 4.331842e-02 | 1.677198e-02 | 2.090259e-06 | True |
| PCSAFT | 6.027168e-02 | 2.155043e-02 | 1.570513e-07 | True |

DWSIM density is used here as a continuity reference. The selected model passed positivity, value-parity, repeatability, and two-step derivative checks over both available column profiles.
