# DD-085 Frozen Numeric Campaign Contract

- Schema: `dd085-core-v2-energy-owned-vapor-steady-root-contract-v1`
- Contract payload SHA-256: `c549bdb9a0f35546c0fee932b865c4b8610b0c6cc1f1d10aa51f7f2714d7b9c7`
- Preparation base commit: `02cb6bbbf8eef7246f76a0901be16ee373717482`
- Workbook: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\sandbox\mini8\input\distillation_column_template_8stage.xlsx`
- Workbook SHA-256: `d1442928feb89bded76737614c0751e62bd4383a900b3c56bc243178080ca904`
- Property package: `pr`
- Coordinates/residuals: `37` / `37`
- Nonlinear solve attempted during preparation: `False`

## Frozen Solver

```json
{
  "method": "trf",
  "jacobian_step": 1e-05,
  "endpoint_jacobian_steps": [
    1e-05,
    5e-06
  ],
  "ftol": 1e-12,
  "xtol": 1e-12,
  "gtol": 1e-12,
  "max_nfev": 500,
  "x_scale": 1.0,
  "residual_inf_tolerance": 1e-08,
  "root_agreement_tolerance": 1e-07,
  "active_bound_tolerance": 1e-06,
  "component_conservation_tolerance": 1e-12,
  "energy_conservation_tolerance": 1e-10,
  "jacobian_condition_hard_stop": 100000000.0,
  "jacobian_coupling_tolerance": 1e-07,
  "composition_floor": 1e-10,
  "temperature_min_F": 110.0,
  "temperature_max_F": 260.0,
  "terminal_amount_min_ratio": 0.8,
  "terminal_amount_max_ratio": 1.2,
  "interior_amount_min_ratio": 0.2,
  "interior_amount_max_ratio": 2.0,
  "internal_flow_min_ratio": 0.1,
  "internal_flow_max_ratio": 5.0,
  "product_feed_min_ratio": 0.0001,
  "product_feed_max_ratio": 1.05
}
```

## Frozen Bounds

The exact 37-element lower and upper transformed-coordinate vectors are stored in the adjacent JSON contract.

## Frozen Starts

- `canonical_role_mapped_seed`: 37 coordinates, `||q||inf=0.000000000e+00`
- `deterministic_combined_perturbation`: 37 coordinates, `||q||inf=2.876772824e-03`
- `independent_smooth_physical_seed`: 37 coordinates, `||q||inf=4.043994300e+00`

## Authorization

After this artifact and implementation are committed, exactly one execution of the three-start campaign is authorized. The execution must consume this JSON contract without modifying it.
