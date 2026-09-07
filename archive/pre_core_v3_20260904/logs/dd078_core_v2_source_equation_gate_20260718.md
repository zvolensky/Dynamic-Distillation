# DD-078 Core V2 Source-Equation Gate

- Classification: `dd078_source_equation_residual_gate_passed`
- Decision: `authorize_gate_a_dynamic_integration_increment`
- Source workbook: `validation_skogestad_column_a_relative_volatility.xlsx`
- Stages: `41`
- Nominal parity error: `2.22044604925e-16`
- Published-profile residual: `3.68312544907e-08 /min`
- +1% feed parity error: `2.22044604925e-16`
- Perturbed-state parity error: `5.56629395354e-16`
- Material-conservation gate: `True`
- Residual-parity gate: `True`

## Scope

- property-free binary source equations only;
- residual evaluation only;
- no nonlinear solve;
- no dynamic integration;
- no DWSIM or other live property evaluation;
- no clipping, projection, profile forcing, or controller action.

The tabulated source profile is not machine-exact: its largest source-equation rate is about 3.7e-8 /min. The gate therefore uses 1e-7 /min for the published-profile residual while requiring the new assembly to match the accepted independent translation to 1e-12.

## Mini8 Reuse Decision

- reuse its compact workbook, geometry, feed/terminal data, UV state-building patterns, and conditioning-audit patterns for Gates B and C;
- do not use its sampled old-model profile or historical run trajectory as an independent acceptance reference;
- do not import its clipping, explicit-Euler advance, profile flow ownership, regularization, or legacy governing balances into core_v2.

## Authorization

The property-free residual assembly is accepted. A separately bounded Gate A dynamic-integration comparison may proceed next; live properties and the five-volume solve remain unauthorized.
