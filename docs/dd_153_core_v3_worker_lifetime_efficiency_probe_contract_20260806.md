# DD-153 Frozen Worker-Lifetime Efficiency Probe Contract

- Payload SHA-256: `bbc20ff7b0ed25545a37b3be114721db7a46883dbf14f786ab5444f68db60df0`
- States: DD-151 coarse roots `60/180/300`, refined roots `120/360/600`
- Repeats: two fresh four-worker pools per state, second round reversed
- Work: one saved-state 21-color Jacobian per pool; no solve or state acceptance
- Exact work: 12 matrices, 504 tasks, 14,112 governing calls
- Matrix reproduction: `<=1e-10` absolute
- Fresh repeat spread: `<30%` relative
- Lifetime confirmation: median aged/fresh `>=1.25`, at least 4/6 checkpoints, fresh late/early `<=1.25`
- Wall limit: `<180 s`

Passing lifetime isolation may authorize only a separately frozen pool-renewal cadence benchmark. No trajectory is authorized.
