# DD-200 Controlled BDF2 Short-Refinement Result

- Classification: `controlled_bdf2_refinement_failed`
- Decision: `stop_bdf2_trajectory_path`
- Completed roots: `24`
- Worst residual / condition: `4.326583e-12` / `3.172742e+07`
- Worst shared inventory max / L1: `5.061785e-06` / `1.803948e-05 lbmol`
- DD-188 max / L1 ratios: `0.324749` / `0.325916`
- Coarse/refined accumulation: `3.968310e-03` / `3.968312e-03 lbmol`
- Provider calls / wall: `108562` / `59.276 s`
- Retry, tuning, alternate grid, or longer trajectory: `False`

## Assessment

DD-200 is formally failed and shall not be rerun or reclassified. Both paths
complete all 24 roots with worst residual `4.326583e-12`, rank `58`, worst
condition `3.172742e7`, and every root-level physical, equilibrium,
conservation, controller, provider, call, and wall gate passing.

The higher-order accuracy result is strong. Worst shared maximum inventory
difference is `5.061785e-6 lbmol`, only `0.324749` of DD-188 backward Euler.
Worst L1 difference is `1.803948e-5 lbmol`, only `0.325916` of DD-188. Rate,
algebraic, PI-memory, product, and level refinements all pass.

The sole formal failure family is the inherited absolute signed-total subgate:
it exceeds `1e-9 lbmol` at `1.75 s` and `2.0 s`, ending at
`1.982463e-9 lbmol`. The final coarse/refined difference is already explained
by their distinct integrated external product flows within
`2.509548e-12 lbmol` and is only `4.995733e-7` of response. This matches the
controlled-response policy issue previously adjudicated in DD-189.

## Decision Boundary

One zero-call adjudication may apply the prospective DD-189 policy at every
shared time using only saved inventories and feed/product rates. DD-200 must
remain failed, every non-signed-total gate must remain passing, unexplained
cross-grid total difference must stay below `1e-10 lbmol`, and the difference
must stay below `1e-5` of response. No live call or endpoint regeneration is
authorized.
