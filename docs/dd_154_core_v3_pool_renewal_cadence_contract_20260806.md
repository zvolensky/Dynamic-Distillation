# DD-154 Frozen Zero-Call Pool-Renewal Cadence Contract

- Payload SHA-256: `a45f55bc28be6d02f9cc6280af899b358be27fe557ca4bee1dae1e69268ec8bd`
- Candidates: `60/120/180/240/300/360/450/900` roots
- Inputs: DD-152 coarse/refined aging slopes and DD-153 fresh matrix/pool lifecycle measurements
- Projection: path-specific fresh cost plus slope-by-worker-age, complete pool lifecycle overhead, and fixed DD-151 non-Jacobian wall
- Calibration: cadence `900` must reproduce DD-151 total wall exactly
- Uncertainty: slopes at `0.75x`, `1.0x`, and `1.25x`
- Selection: minimum nominal projected total; cadence must lie in `120..450` and improve at least `20%`
- DWSIM/provider/model/solver/state calls: prohibited

Passing may authorize only implementation of the selected renewal cadence plus a separately frozen saved-state equivalence proof. No trajectory is authorized.
