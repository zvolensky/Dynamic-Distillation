# DD-175 Seven-Volume Smaller Moving-Step Contract

- Payload SHA-256: `65d7be099fa03bf3add2451eff4b3078345ac25d297dd49eba3e74936ce39f2b`
- Preparation base commit: `ef84126bb95d24490c87ef285a582b0d13396d12`
- Disturbance: unchanged DD-173 `+0.1%` feed rate and enthalpy
- Comparison: one `0.25 s` step versus two `0.125 s` steps
- Strict DD-173 relative-inventory gate retained: `<1e-7`
- DD-174 physical-scale gates retained
- Solver/Jacobian/memoization: unchanged
- Live property evaluation during preparation: `False`

Commit before the one execution. No retry, controller, alternate disturbance, or trajectory is authorized by this contract.
