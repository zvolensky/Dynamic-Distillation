**Thermo Container Parallelization Exploration**

**Goal**
Run thermo calculations out-of-process so they can be scaled across CPU cores safely, without changing column solver math.

**Current State (Codebase)**
- Thermo backend in `src/dynamic_distillation/pr_flash_backend_v1.py` is module-global and mutable (`_dtlc`, `_prop_package`, `_carray`).
- Thermo provider in `src/dynamic_distillation/thermo_provider_v1.py` configures that shared backend on calls.
- Runner selects provider in `build_inputs_for_runner(...)` in:
  - `src/dynamic_distillation/dynamic_run_scaffold_v1.py`
  - `src/dynamic_run_scaffold_v1.py`
- Existing `thermo_bridge.py` already proves out-of-process thermo I/O can work.

**Implication**
In-process threading is unsafe/high-risk with current backend state model.
Out-of-process workers are the practical path to parallelization.

**Target Architecture**
1. Simulation process keeps ODE/RHS logic.
2. Thermo provider becomes a remote client (`ThermoProviderRemoteV1`).
3. Remote service runs N worker containers (typically N=number of cores).
4. Each worker owns its own DWSIM engine instance.
5. Requests are load-balanced across workers.

**Service API (Recommended)**
- `POST /flash_tp_full`
- `POST /flash_tp_full_batch`
- `POST /cp_liq_vap`
- `POST /liquid_density`
- `GET /health`

Input contract for flash:
- `T_F`, `P_psia`, `z`, `components_excel`, `components_dwsim`

Output contract for flash:
- `x`, `y`, `K`, `HL_BTU_lbmol`, `HV_BTU_lbmol`, `Z` (optional)

Batch endpoint is important. It reduces RPC overhead and is needed for real speedup.

**Container Choice**
- `Option A (Recommended for parity)`: Windows containers with DWSIM DLLs + pythonnet.
- `Option B (Fast prototype)`: Linux container using `thermo` package PR/SRK fallback.

Tradeoff:
- Option A keeps current thermo parity.
- Option B is easier to stand up but can diverge numerically.

**Parallelization Pattern**
- Prefer stage-batch calls (`/flash_tp_full_batch`) over per-stage calls.
- Keep each worker single-process/single-engine (no intra-worker threading).
- Scale by worker count (e.g., 4-8 workers) and queue depth.

**Expected Performance**
- Best gains when thermo dominates runtime and batches are large enough.
- Typical practical gain for one simulation: moderate (`~1.2x-2x` often), not linear with 8 cores.
- Running multiple independent simulations in parallel can approach near-linear CPU utilization.

**Implementation Touch Points**
1. Add remote provider module:
   - `src/dynamic_distillation/thermo_provider_remote_v1.py`
2. Extend thermo mode selection (`stub|dwsim|remote`) in:
   - `src/dynamic_distillation/dynamic_run_scaffold_v1.py`
   - `src/dynamic_run_scaffold_v1.py`
3. Add CLI flags:
   - `--thermo remote`
   - `--thermo-url http://...`
   - optional `--thermo-timeout`, `--thermo-batch-size`
4. Add service app and container files:
   - `services/thermo_api/app.py`
   - `services/thermo_api/Dockerfile` (Windows base for DWSIM path)
   - `docker-compose.yml`
5. Add benchmark script:
   - compare `dwsim` in-process vs `remote` for identical case and steps.

**Phased Plan**
1. Phase 1: Remote client + single service instance (no scaling)
   - Success: numerical parity within tolerance for K/HL/HV on sampled states.
2. Phase 2: Batch endpoint + profiling
   - Success: remote overhead acceptable vs in-process baseline.
3. Phase 3: Multi-worker scaling
   - Success: measurable wall-clock reduction on representative runs.

**Risk Register**
- DWSIM/pythonnet behavior in Windows containers.
- Serialization overhead erasing gains for tiny requests.
- Numerical drift if moving to non-DWSIM thermo in container.
- Operational complexity (container image size, startup time, deployment).

**Go/No-Go Criteria**
- Go if:
  - parity check passes,
  - and end-to-end run improves meaningfully on your target case.
- No-go if:
  - overhead dominates,
  - or parity/maintenance costs are too high.

**Minimal Compose Shape (Conceptual)**
```yaml
services:
  thermo:
    image: dynamic-distillation/thermo-api:windows
    deploy:
      replicas: 4
    ports:
      - "8080"
  sim:
    image: dynamic-distillation/sim:latest
    environment:
      THERMO_MODE: remote
      THERMO_URL: http://thermo:8080
```

