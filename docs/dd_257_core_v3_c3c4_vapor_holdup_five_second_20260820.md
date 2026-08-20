# DD-257 Five-Second Vapor-Holdup Trajectory Result

- Classification: `five_second_vapor_holdup_trajectory_aborted_during_reporting`
- Decision: `no_scientific_classification`
- Contract commit: `b54e3b3`
- Failure location: post-solve stage-profile reporting
- Failure: vapor-link tuples were treated as objects with `source_volume`
- Result metrics retained: `False`
- Accepted endpoint/state advance: `False`
- DD-257 rerun: `False`

The full 20-endpoint solve path returned before the reporter raised the
exception, but no result or endpoint evidence had yet been serialized. The
campaign therefore cannot be accepted or rejected scientifically. The frozen
DD-257 implementation is not changed or rerun. One separately versioned
successor is permitted only after a property-free stage-profile preflight test.
