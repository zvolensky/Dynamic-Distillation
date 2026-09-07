# DD-077 Core V2 Reduced Structural Registry

- Classification: `dd077_structural_gate_passed`
- Decision: `authorize_source_equation_residual_evaluator`
- Vapor-flow owner: `prescribed-section-rates`
- Inventory volumes: `5`
- Components: `3`
- Unknowns/residuals: `53 / 53`
- Structural rank/nullity: `53 / 0`
- Structure gate: `True`
- Ownership gate: `True`
- Conservation gate: `True`

## Deliberate First-Layer Choices

- pressure is prescribed data, not an unknown;
- rectifying and stripping vapor rates are prescribed section parameters;
- tray liquid outlets are owned only by Francis equations;
- terminal liquid amounts are specified and D/B are solved;
- the total condenser has no inventory volume;
- the bottom is one combined reboiler/sump volume;
- no imported profile enters a physical residual;
- no controller, property call, nonlinear solve, or integration is present.

## Authorization

Implement the property-free Gate A source-equation residual comparison next. Live DWSIM, nonlinear solves, and dynamic integration remain unauthorized.
