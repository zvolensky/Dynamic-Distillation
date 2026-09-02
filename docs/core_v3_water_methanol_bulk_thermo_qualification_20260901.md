# Core V3 water-methanol bulk-thermo qualification

- Selected for prescribed-pressure gate: `dwsim_unifac`
- Decision: `run_prescribed_pressure_stationary_parity`
- No fallback property route was allowed.
- ChemSep method: `DECHEMA K model` / `UNIFAC Activity coefficient` / `Antoine Vapour pressure` / `Excess Enthalpy(`
- ChemSep UNIFAC interaction record: `2 289.6 -181 # 7-6 = H2O-CH3OH`

| Provider | Compatible | Max VLE log error | RMS VLE log error | Energy residual (BTU/h) | Top dT (F) | Bottom dT (F) |
|---|---:|---:|---:|---:|---:|---:|
| dwsim_unifac | Yes | 0.175600 | 0.114562 | 3991524.537 | +0.037695 | +9.795736 |
| dwsim_nrtl | Yes | 0.183009 | 0.108507 | 3991524.537 | +0.016507 | +10.066823 |
| dwsim_modfac | Yes | 0.175653 | 0.109313 | 3991524.537 | +0.030317 | +9.699072 |
| clapeyron_unifac | No | -- | -- | -- | -- | -- |
| clapeyron_nrtl | No | -- | -- | -- | -- | -- |
| clapeyron_vtpr | Yes | 1.163023 | 0.494879 | 421351.110 | -1.327001 | +15.954129 |

## Unavailable interfaces

- `clapeyron_unifac`: JuliaError: MethodError: no method matching PT_property_gibbs(::Clapeyron.PTFlashWrapper{GammaPhi{UNIFAC{PR{BasicIdeal, PRAlpha, NoTranslation, vdW1fRule}, Float64}, PR{BasicIdeal, PRAlpha, NoTranslation, vdW1fRule}}, Vector{PR{BasicIdeal, PRAlpha, NoTranslation, vdW1fRule}}, Tuple{Float64, Float64, Float64}, Float64}, ::Float64, ::Float64, ::PyArray{Float64, 1, true, true, Float64}, ::typeof(Clapeyron.VT_fugacity_coefficient))
- `clapeyron_nrtl`: JuliaError: MethodError: no method matching PT_property_gibbs(::Clapeyron.PTFlashWrapper{GammaPhi{NRTL{PR{BasicIdeal, PRAlpha, NoTranslation, vdW1fRule}}, PR{BasicIdeal, PRAlpha, NoTranslation, vdW1fRule}}, Vector{PR{BasicIdeal, PRAlpha, NoTranslation, vdW1fRule}}, Tuple{Float64, Float64, Float64}, Float64}, ::Float64, ::Float64, ::PyArray{Float64, 1, true, true, Float64}, ::typeof(Clapeyron.VT_fugacity_coefficient))

## Meaning

This is a fixed-state comparison, not a fitted model. The selected provider is simply the available Core-compatible provider that most closely reproduces the ChemSep interior equilibrium rows. Density-only VTPR remains a separate choice and does not alter this bulk-provider ranking.
