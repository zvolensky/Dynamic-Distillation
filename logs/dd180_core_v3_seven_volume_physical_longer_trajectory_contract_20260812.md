# DD-180 Seven-Volume Physical-Policy Longer-Trajectory Contract

- Payload SHA-256: `8cc343bb23d087eac39a042e2d2a8173f6b68917b3509ad0cb3c81b6d3b474c3`
- Preparation base commit: `b19bbe5243423f5bb3552e86bd5f02cad63d62a8`
- Disturbance: unchanged DD-177/DD-178 open-loop feed step
- Duration: `30.0 s`
- Coarse path: `120 x 0.25 s`
- Refined path: `240 x 0.125 s`
- Shared-time comparisons: `120`
- Response: DD-179 duration-integrated expected-flow policy
- Evidence: compact per-root scalars plus complete endpoints
- Controllers: disabled

Commit before the one execution. Retry, alternate grid, controller, projection, clipping, fallback, or continuation is prohibited.
