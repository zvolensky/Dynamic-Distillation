# DD-136 Frozen DD-134 Residual-Replay Audit Contract

- Payload SHA-256: `cd2787e19bf955fe637737b700f4bf51aaacbb042425bb24df838a1483975fa8`
- Saved points: DD-134 coarse `t=7 s` and refined `t=3 s` failures
- Fresh processes: `3`
- Repetitions: `3` complete 50-row residuals per point per process
- Orders: grouped forward, grouped reverse, and interleaved
- Same-process spread limit: `1e-12`
- Cross-process/order spread limit: `1e-10`
- Jacobian, solve, state advance, timestep, and trajectory: prohibited
- Provider-call limit: `<1000`
- Wall-clock limit: `<180 s`

The audit determines whether DD-135 failed because of provider/residual nonrepeatability or because DD-134 did not serialize a replay-complete numerical failure artifact.
