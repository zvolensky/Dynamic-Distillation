# DD-163 Hybrid Fugacity Root-Reconstruction Result

- Classification: `hybrid_fugacity_root_reconstruction_failed`
- Decision: `retain_dwsim_only_and_stop_hybrid_acceleration_path`
- Initial/final scaled residual: `1.641114621e-04` / `1.641114621e-04`
- Iterations/residual evaluations: `1` / `5`
- Solver rank/condition: `50` / `2.498027760e+06`
- Endpoint rank/condition: `50` / `2.498027760e+06`
- Maximum temperature shift: `0 F`
- Maximum liquid/vapor composition shift: `0` / `0`
- Maximum pressure shift: `0 psia`
- Maximum liquid/vapor flow relative shift: `0` / `0`
- Hybrid provider calls: `1820`
- Wall clock: `5.078 s`

The first frozen-Jacobian correction had an infinity norm of `0.408243`. None
of the four predeclared line-search fractions reduced the residual:

| Fraction | Scaled residual infinity norm |
|---:|---:|
| `1.0` | `3.301146710e-2` |
| `0.5` | `8.803952140e-3` |
| `0.25` | `2.275195508e-3` |
| `0.125` | `5.784315406e-4` |

The unchanged engineering-comparison values are not evidence of root
equivalence; they reflect that the solver correctly accepted no candidate.
DD-162 remains valid as a residual/Jacobian performance benchmark, but DD-163
rejects direct hybrid root ownership without a tuned retry.

No reconstructed endpoint was accepted as a simulation state; no timestep or trajectory advanced.
