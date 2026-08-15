# DD-227 Direct Hydraulic-Derivative Probe

## Result

The direct one-coordinate derivative exactly matches the colored Jacobian at both shared step sizes and both DD-223 endpoints. The structural coloring is therefore not the cause of DD-223's step-sensitive Jacobian.

The underlying DWSIM liquid-density result is discontinuous near the identified lower interior state:

- At the source endpoint, the baseline density is `0.4617479 lbmol/ft3`. Tiny positive temperature perturbations return about `0.580368`, while tiny negative perturbations return about `0.4617`.
- At the independent endpoint, the baseline density is `0.5686678 lbmol/ft3`. At three perturbation sizes, the negative side returns about `0.4706` while the positive side remains about `0.5687`. At the smallest step, both sides return about `0.5687`.
- As the difference step is halved, the apparent hydraulic derivative nearly doubles instead of converging.
- Exact baseline repeats agree exactly, so the recorded behavior is reproducible under the same call sequence.

The tiny temperature changes cannot physically cause a 17-26% density change. DWSIM's declared liquid-density calculation is switching between equation-of-state roots or phase branches. That jump changes calculated liquid height, weir head, and Francis flow and creates the false large Jacobian entry.

## Decision

Do not change the Francis equation, Jacobian coloring, or physical column equations. Do not retry the root solve yet.

The next bounded task is to test a smooth, phase-explicit liquid-density calculation using the same Peng-Robinson parameters. A defensible candidate is the smallest valid liquid root of the parameter-aligned PR equation. It must be compared against the saved DWSIM branches and checked for smoothness before it can be considered for governing hydraulics.

DD-227 used `1,980` logical provider calls in `3.379 s`. It performed no nonlinear solve, state change, timestep, retry, or dynamic integration.
