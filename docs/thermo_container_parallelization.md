**Thermo Parallelization Status (Current State)**

This document summarizes what is implemented today and what is still exploratory.

**Implemented in this repo**

1. Tabular thermo process-pool mode (`table-pool`)
- Runner mode: `--thermo table-pool`
- Provider: `src/dynamic_distillation/thermo_table_pool_v1.py`
- Uses `ProcessPoolExecutor` workers for `flash_TP_full_batch(...)` chunks.
- Keeps a local tabular provider for scalar methods.
- Chunk failures/timeouts fall back to local tabular evaluation.

2. RHS batch hook
- `src/dynamic_distillation/column_rhs_v1.py` checks whether provider has `flash_TP_full_batch`.
- If available, refreshed stage flashes are evaluated through that batch path.
- Otherwise, RHS uses per-stage flash calls.

3. Pool controls exposed in CLI
- `--thermo-pool-workers`
- `--thermo-pool-chunk-size`
- `--thermo-pool-timeout-sec`

**Not implemented (still exploratory)**

1. Remote/container thermo service for live DWSIM flashes
- No `--thermo remote` mode exists today.
- No service app / Docker deployment exists in this repo.

2. Cross-process parallelism for mutable DWSIM backend state in current in-process mode
- Current DWSIM path remains single-process in runner usage.

**Current recommendation**

- Use `--thermo table` for simplest stable tabular runs.
- Use `--thermo table-pool` when stage flash work dominates and CPU parallelism is needed.
- Keep `--thermo dwsim` for highest parity path when performance is secondary.

**Future direction (if needed)**

If DWSIM parallel scaling is required beyond tabular mode, the next step is a remote thermo service with worker isolation and batch endpoints.
