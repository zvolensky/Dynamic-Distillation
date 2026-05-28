**Thermo Pool Workers/Chunk Findings**

Date: 2026-02-22

Scope:
1. `--thermo table-pool` only.
2. Focus on `--thermo-pool-workers` and `--thermo-pool-chunk-size`.
3. Evidence from logged parity benchmarks on the same case and horizon.

Benchmark basis:
1. Case: `logs/tmp_pressure_hydraulic_conductance_20260221_152741.xlsx`
2. Mode: `--runtime-mode parity`
3. Horizon: mostly `n-steps=600`, `dt=0.2` (`120 s` sim time)
4. Source of truth: `logs/run_registry.csv` + corresponding `logs/column_summary_<run_id>.csv`

**Worker Sweep (Chunk Auto)**

| Run ID | Workers | Chunk | Wall (s) | Sim/Wall |
|---|---:|---:|---:|---:|
| `20260222_094600` | 1 | auto | 133.053 | 0.9019 |
| `20260222_094831` | 2 | auto | 115.140 | 1.0422 |
| `20260222_095042` | 4 | auto | 123.542 | 0.9713 |
| `20260222_095303` | 8 | auto | 121.397 | 0.9885 |
| `20260222_095521` | 15 | auto | 120.243 | 0.9980 |

Finding:
1. For this workload, 2 workers was the fastest in the clean worker sweep.

**Chunk Sweep**

8 workers:

| Run ID | Workers | Chunk | Wall (s) | Sim/Wall |
|---|---:|---:|---:|---:|
| `20260222_101448` | 8 | 4 | 129.940 | 0.9235 |
| `20260222_101702` | 8 | 8 | 129.784 | 0.9246 |
| `20260222_101916` | 8 | 11 | 156.245 | 0.7680 |

15 workers:

| Run ID | Workers | Chunk | Wall (s) | Sim/Wall |
|---|---:|---:|---:|---:|
| `20260222_102157` | 15 | 4 | 125.327 | 0.9575 |
| `20260222_102407` | 15 | 8 | 126.817 | 0.9462 |
| `20260222_102618` | 15 | 11 | 115.382 | 1.0400 |

Findings:
1. Chunk behavior is worker-dependent.
2. At 8 workers, larger chunk (`11`) hurt badly.
3. At 15 workers, chunk `11` performed best in that test set.

**Repeatability / Noise**

Paired repeats:

| Config | Run IDs | Mean Wall (s) | Std Dev (s) |
|---|---|---:|---:|
| 2 workers, chunk 4 | `20260222_102839`, `20260222_103218` | 117.640 | 11.565 |
| 15 workers, chunk 11 | `20260222_103029`, `20260222_103432` | 121.650 | 15.920 |

Longer-horizon check (`n-steps=3000`, `600 s` sim):

| Run ID | Workers | Chunk | Wall (s) |
|---|---:|---:|---:|
| `20260222_095818` | 2 | auto | 606.878 |
| `20260222_103713` | 15 | 11 | 642.681 |

Findings:
1. Runtime variance is material; single-run conclusions can be misleading.
2. On average in these repeats, 2 workers remained modestly faster.
3. Long horizon also favored 2 workers in this case.

**Interpretation**

1. This case is small enough that process-pool overhead can offset high worker counts.
2. Worker counts above 2 did not provide consistent speedup on this machine/case.
3. Chunk tuning matters, but interaction with worker count is non-linear.

**Operational Decision (Current Project Default)**

Use this default for subsequent runs unless explicitly benchmarking:
1. `--thermo-pool-workers 2`
2. `--thermo-pool-chunk-size 4`

**How To Re-Tune For A Different Column**

1. Fix one scenario and compare `workers = 2, 4, 8` first.
2. For each worker setting, test `chunk = 4, 8, 11`.
3. Run each point at least 2 times and compare median wall time.
4. Prefer the smallest config within ~5% of best runtime to reduce variability risk.
