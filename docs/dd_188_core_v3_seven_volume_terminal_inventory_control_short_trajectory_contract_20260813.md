# DD-188 Seven-Volume Controlled Short-Trajectory Contract

- Payload SHA-256: `80d135bd009d185afff02aca444931302336d65dfd33ca1ed2e36a0b3242b132`
- Preparation base commit: `433cb95959f834cdd3d3df2b82d886d0db64eba6`
- Disturbance, setpoints, PI constants, and product references: unchanged from DD-187
- Duration: `2.0 s`
- Coarse path: `8 x 0.25 s`
- Refined path: `16 x 0.125 s`
- Shared-time comparisons: `8`
- Response acceptance: duration-scaled integrated external flow
- Property evaluation during preparation: `False`
- Timestep execution during preparation: `False`

Commit before the one execution. No tuning, retry, alternate grid, projection, clipping, or fallback is authorized.
