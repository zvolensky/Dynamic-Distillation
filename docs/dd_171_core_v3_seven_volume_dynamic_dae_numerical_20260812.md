# DD-171 Seven-Volume Dynamic DAE Numerical Result

## Verdict

**DD-171 passes every frozen gate.** The accepted DD-169 stationary root is a
numerically consistent zero-rate point of the seven-volume conserved dynamic
DAE, and its live leading system is complete, well-conditioned, and stable to
finite-difference step halving.

## Results

| Metric | Result | Gate |
|---|---:|---:|
| Zero-rate scaled residual | `4.979842e-13` | `<1e-8` |
| Component-rate maximum, lbmol/h | `0.0` | `0.0` |
| Energy-storage-rate maximum, BTU/h | `0.0` | `0.0` |
| Storage-gradient relative step change | `2.021471e-9` | `<1e-3` |
| Maximum storage bubble residual | `7.771561e-15` | `<1e-10` |
| Leading ranks | `54 / 54` and `54 / 54` | Required |
| Worst leading condition | `50.970640` | `<1e8` |
| Singular-spectrum relative change | `1.095288e-10` | `<0.25` |
| Component conservation error | `1.432430e-16` | `<1e-12` |
| Energy conservation error | `7.660863e-17` | `<1e-10` |
| Logical provider calls | `11,494` | `<30,000` |
| Wall clock, s | `8.446` | `<120` |

Neither matrix has a zero row, zero column, or unexpected coupling above the
frozen `1e-7` threshold. DWSIM Peng-Robinson owns every governing property
call, and provider provenance passes without fallback.

Exact-state memoization serves `9,096` repeated requests and delegates `2,398`
misses. The hit fraction is approximately `79.1%`; this improves execution
cost without changing the equations or acceptance basis.

## Meaning

DD-171 closes the gap between a stationary algebraic root and a usable dynamic
DAE leading system. At the accepted state:

- the conserved inventory derivatives can be exactly zero;
- the provider-consistent energy-storage derivative is finite and stable;
- the algebraic variables and inventory rates form a nonsingular implicit
  system;
- the larger topology has not inherited the severe conditioning seen in
  earlier abandoned formulations.

This remains a zero-time numerical audit. It does not prove timestep
convergence, moving dynamics, controller behavior, or long-horizon stability.

## Decision

Authorize one separately frozen stationary root-hold implicit-step contract.
That successor should compare one `1.0 s` backward-Euler step with two
successive `0.5 s` steps and require the accepted state to remain stationary
within strict residual, refinement, conservation, rank, physicality, call,
and wall gates. A disturbance or moving trajectory remains unauthorized.

## Artifacts

- `logs/dd171_core_v3_seven_volume_dynamic_dae_numerical_contract_20260812.json`
- `logs/dd171_core_v3_seven_volume_dynamic_dae_numerical_20260812.json`
- `logs/dd171_core_v3_seven_volume_dynamic_dae_numerical_20260812.md`
- `tools/audit_core_v3_seven_volume_dynamic_dae_numerical.py`
