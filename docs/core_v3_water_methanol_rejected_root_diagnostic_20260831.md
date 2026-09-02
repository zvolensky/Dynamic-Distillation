# Core V3 water-methanol rejected-root diagnosis

- Finding: `rejected_candidate_derivatives_unreliable`
- Decision: `investigate_local_derivative_noise_before_any_second_solve`
- Candidate scaled equation error: `1.331071e-02`
- Rank at both step sizes: `100 / 100`
- Condition number: `5.694291e+08 / 1.730461e+09`
- Matrix change when step was halved: `5.927584e-01`
- Solver optimality measure: `1.382899e+01`
- Live property calls: `5340`
- Second nonlinear solve or timestep: `False`

## Meaning

The candidate remained physical and away from its bounds, but the local derivatives became badly conditioned and changed sharply with numerical step size. The solver therefore stopped with a small step before the stationary equations were closed.

The next task is to isolate the noisy property or equation derivatives. A second solve should not be attempted until that numerical issue is understood.
