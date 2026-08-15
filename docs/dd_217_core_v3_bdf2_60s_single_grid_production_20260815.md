# DD-217 60-Second Single-Grid Production Result

- Classification: `single_grid_production_segment_passed`
- Decision: `adopt_60s_single_grid_production_segment`
- Completed roots: `240` / `240`
- Worst residual / condition: `4.046842e-12` / `7.933880e+06`
- Saved-science maximum difference: `0.000000e+00`
- Startup / active / shutdown / total: `2.731` / `116.237` / `15.024` / `134.005 s`
- Unattributed wall: `0.012423 s`
- Matrix count / logical calls: `688` / `834632`
- Retry, tuning, alternate grid, or fallback: `False`

## Result

DD-217 passes every frozen gate. All `240/240` roots complete with worst
residual `4.046842e-12`, worst condition `7.933880e+06`, valid response,
physicality, conservation, provider ownership, all-worker participation, and
complete per-root basis lifecycle. No deadline, retry, alternate grid, tuning,
fallback, clipping, projection, or equation change occurs.

All 240 accepted science records and the complete integrated-response report
match DD-213's saved coarse validation path with maximum numeric difference
`0.0`. The reusable production orchestration therefore changes lifecycle only;
it does not shift the accepted trajectory.

## Performance

| Timing block | Limit | Observed |
|---|---:|---:|
| Startup | `10 s` | `2.731425 s` |
| Active 60-second segment | `180 s` | `116.236862 s` |
| Final shutdown | `30 s` | `15.024129 s` |
| Complete session | `225 s` | `134.004839 s` |
| Unattributed overhead | `1 s` | `0.012423 s` |

The simulated/active-wall ratio is `0.5162`; simulated/complete-session wall is
`0.4477`. This is materially better than executing both validation grids, but
thermodynamic Jacobian work remains expensive: 688 matrices require 834,632
logical provider calls.

## Next Boundary

The accepted 60-second segment starts from the steady root and creates its own
backward-Euler startup history. Calling the existing trajectory function again
would create another startup rather than continue the accepted BDF2 history.
Before a second live segment, Core V3 needs a property-free continuation
payload containing the two accepted physical/storage/controller history levels,
current and prior solve coordinates, constant timestep, and elapsed time.

Continuation must not insert another backward-Euler step, reset controller
memory, change the worker session, or reuse a root epoch. No additional live
segment is authorized until that handoff is implemented and tested.
