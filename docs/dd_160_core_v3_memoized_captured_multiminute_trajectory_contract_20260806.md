# DD-160 Frozen Memoized Captured Five-Minute Trajectory Contract

- Payload SHA-256: `123b38755f3a403fb574d7a97fe06838994691f2b8adf2ef1a164805e68f083b`
- Scientific case: exact DD-151 `300 s`, `300 x 1.0 s` and `600 x 0.5 s`
- Only runtime change: production exact memoization with one unique epoch per Jacobian
- Exact work: 900 roots, 37,800 tasks, 1,058,400 logical worker-provider calls
- Complete replay: every accepted state and full capture digest must equal DD-151 exactly
- Memo accounting: 1,176 calls/root and hit fraction `>=0.60` for every root
- Performance: trajectory wall `<=0.60x` DD-151; governed total wall `<300 s`
- Rebuild, retry, fallback, clipping, projection, controller change, or grid change: prohibited

Passing establishes the first accepted five-minute Core V3 controlled trajectory. No longer run is authorized.
