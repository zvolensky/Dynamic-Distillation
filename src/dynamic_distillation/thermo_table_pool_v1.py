"""
thermo_table_pool_v1.py

Dynamic Distillation - Parallel Tabular Thermo Pool Provider

PURPOSE
-------
Provide process-pool acceleration for tabular thermo batch flashes used in
`table-pool` mode while keeping local scalar-property access available.

INPUTS
------
ParallelTabularThermoProviderV1 constructor:
- table path and expected component ordering
- worker count, chunk size, optional task timeout

Runtime:
- flash_TP_full_batch(T_rows, P_rows, z_rows)
- scalar delegates to local tabular provider

OUTPUTS
-------
- batch flash results aligned to input order
- local fallback results when worker tasks fail/timeout

KEY DEPENDENCIES
----------------
- thermo_surrogate_v1.TabularThermoProviderV1
- concurrent.futures.ProcessPoolExecutor

ASSUMPTIONS & CONSTRAINTS
-------------------------
- Uses spawn-based worker initialization.
- Caller should close provider to release worker processes deterministically.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import os
from typing import List, Optional, Sequence, Tuple

import numpy as np

from dynamic_distillation.thermo_provider_v1 import FlashResult
from dynamic_distillation.thermo_surrogate_v1 import TabularThermoProviderV1


_WORKER_PROVIDER: Optional[TabularThermoProviderV1] = None


def _normalize_row(z: Sequence[float], n_components: int) -> np.ndarray:
    arr = np.asarray(z, dtype=float).reshape((-1,))
    if arr.size != int(n_components):
        raise ValueError(f"Expected composition length {int(n_components)}, got {arr.size}")
    s = float(np.sum(arr))
    if (not np.isfinite(s)) or s <= 0.0:
        raise ValueError("Composition sum must be > 0")
    return arr / s


def _pool_worker_init(
    table_path: str,
    expected_component_names_excel: Sequence[str],
    expected_component_ids_dwsim: Sequence[str],
    cp_dt_F: float,
    n_anchor_blend: int,
    anchor_blend_power: float,
    anchor_distance_eps: float,
) -> None:
    global _WORKER_PROVIDER
    _WORKER_PROVIDER = TabularThermoProviderV1.from_json(
        str(table_path),
        expected_component_names_excel=expected_component_names_excel,
        expected_component_ids_dwsim=expected_component_ids_dwsim,
        cp_dt_F=float(cp_dt_F),
        n_anchor_blend=int(n_anchor_blend),
        anchor_blend_power=float(anchor_blend_power),
        anchor_distance_eps=float(anchor_distance_eps),
    )


def _pool_worker_flash_chunk(
    jobs: Sequence[Tuple[int, float, float, Sequence[float]]],
) -> List[Tuple[int, list, list, list, float, float, Optional[float]]]:
    global _WORKER_PROVIDER
    if _WORKER_PROVIDER is None:
        raise RuntimeError("Worker thermo provider was not initialized")

    out: List[Tuple[int, list, list, list, float, float, Optional[float]]] = []
    for idx, T_F, P_psia, z in jobs:
        res = _WORKER_PROVIDER.flash_TP_full(float(T_F), float(P_psia), z)
        out.append(
            (
                int(idx),
                np.asarray(res.x, dtype=float).tolist(),
                np.asarray(res.y, dtype=float).tolist(),
                np.asarray(res.K, dtype=float).tolist(),
                float(res.HL_BTU_lbmol),
                float(res.HV_BTU_lbmol),
                (None if res.Z is None else float(res.Z)),
            )
        )
    return out


class ParallelTabularThermoProviderV1:
    """
    Process-pool backed tabular thermo provider.

    Notes:
      - Scalar methods delegate to a local TabularThermoProviderV1 instance.
      - Batch flash calls are parallelized across worker processes.
      - Workers are started lazily at construction and should be closed by caller.
    """

    def __init__(
        self,
        *,
        table_path: str,
        expected_component_names_excel: Optional[Sequence[str]] = None,
        expected_component_ids_dwsim: Optional[Sequence[str]] = None,
        cp_dt_F: float = 1.0,
        n_anchor_blend: int = 3,
        anchor_blend_power: float = 2.0,
        anchor_distance_eps: float = 1e-12,
        max_workers: Optional[int] = None,
        chunk_size: int = 4,
        task_timeout_sec: Optional[float] = None,
    ):
        self._local = TabularThermoProviderV1.from_json(
            str(table_path),
            expected_component_names_excel=expected_component_names_excel,
            expected_component_ids_dwsim=expected_component_ids_dwsim,
            cp_dt_F=float(cp_dt_F),
            n_anchor_blend=int(n_anchor_blend),
            anchor_blend_power=float(anchor_blend_power),
            anchor_distance_eps=float(anchor_distance_eps),
        )
        self.table_path = str(table_path)
        self.component_names_excel = list(self._local.component_names_excel)
        self.component_ids_dwsim = list(self._local.component_ids_dwsim)
        self.n_components = int(self._local.n_components)
        self.T_grid_F = np.asarray(self._local.T_grid_F, dtype=float).copy()
        self.P_grid_psia = np.asarray(self._local.P_grid_psia, dtype=float).copy()

        workers_default = max((os.cpu_count() or 1) - 1, 1)
        workers = workers_default if max_workers is None else int(max_workers)
        self.max_workers = max(int(workers), 1)

        self.chunk_size = max(int(chunk_size), 1)
        self.task_timeout_sec = (
            None
            if task_timeout_sec is None
            else max(float(task_timeout_sec), 1e-6)
        )
        self._closed = False
        self._pool: Optional[ProcessPoolExecutor] = None

        if self.max_workers > 1:
            ctx = mp.get_context("spawn")
            self._pool = ProcessPoolExecutor(
                max_workers=self.max_workers,
                mp_context=ctx,
                initializer=_pool_worker_init,
                initargs=(
                    self.table_path,
                    self.component_names_excel,
                    self.component_ids_dwsim,
                    float(self._local.cp_dt_F),
                    int(self._local.n_anchor_blend),
                    float(self._local.anchor_blend_power),
                    float(self._local.anchor_distance_eps),
                ),
            )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._pool is not None:
            self._pool.shutdown(wait=True, cancel_futures=True)
            self._pool = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def flash_TP_full(self, T_F: float, P_psia: float, z: Sequence[float]) -> FlashResult:
        return self._local.flash_TP_full(float(T_F), float(P_psia), z)

    def flash_TP_full_F_psia(self, T_F: float, P_psia: float, z: Sequence[float]):
        return self._local.flash_TP_full_F_psia(float(T_F), float(P_psia), z)

    def cp_liq_vap_btu_per_lbmolF(
        self,
        T_F: float,
        P_psia: float,
        z: Sequence[float],
    ):
        return self._local.cp_liq_vap_btu_per_lbmolF(float(T_F), float(P_psia), z)

    def liquid_density_lbmol_ft3(
        self,
        T_F: float,
        P_psia: float,
        x: Sequence[float],
    ):
        return self._local.liquid_density_lbmol_ft3(float(T_F), float(P_psia), x)

    def component_mw_lbm_per_lbmol(self):
        return self._local.component_mw_lbm_per_lbmol()

    def _flash_chunk_local(
        self,
        jobs: Sequence[Tuple[int, float, float, Sequence[float]]],
    ) -> List[Tuple[int, list, list, list, float, float, Optional[float]]]:
        out: List[Tuple[int, list, list, list, float, float, Optional[float]]] = []
        for idx, T_F, P_psia, z in jobs:
            res = self._local.flash_TP_full(float(T_F), float(P_psia), z)
            out.append(
                (
                    int(idx),
                    np.asarray(res.x, dtype=float).tolist(),
                    np.asarray(res.y, dtype=float).tolist(),
                    np.asarray(res.K, dtype=float).tolist(),
                    float(res.HL_BTU_lbmol),
                    float(res.HV_BTU_lbmol),
                    (None if res.Z is None else float(res.Z)),
                )
            )
        return out

    def flash_TP_full_batch(
        self,
        T_F: Sequence[float],
        P_psia: Sequence[float],
        z_rows: Sequence[Sequence[float]],
    ) -> List[FlashResult]:
        T_arr = np.asarray(T_F, dtype=float).reshape((-1,))
        P_arr = np.asarray(P_psia, dtype=float).reshape((-1,))
        if T_arr.size != P_arr.size:
            raise ValueError(f"T_F and P_psia length mismatch: {T_arr.size} vs {P_arr.size}")

        n_rows = int(T_arr.size)
        if n_rows == 0:
            return []

        if len(z_rows) != n_rows:
            raise ValueError(f"z_rows length mismatch: expected {n_rows}, got {len(z_rows)}")

        jobs_all: List[Tuple[int, float, float, Sequence[float]]] = []
        for i in range(n_rows):
            z_norm = _normalize_row(z_rows[i], self.n_components)
            jobs_all.append((int(i), float(T_arr[i]), float(P_arr[i]), z_norm.tolist()))

        rows_out: List[Optional[Tuple[int, list, list, list, float, float, Optional[float]]]] = [None] * n_rows

        if self._pool is None:
            rows = self._flash_chunk_local(jobs_all)
            for row in rows:
                rows_out[int(row[0])] = row
        else:
            futures = {}
            for i0 in range(0, n_rows, self.chunk_size):
                chunk = jobs_all[i0 : i0 + self.chunk_size]
                fut = self._pool.submit(_pool_worker_flash_chunk, chunk)
                futures[fut] = chunk

            for fut in as_completed(futures):
                chunk = futures[fut]
                try:
                    timeout = None if self.task_timeout_sec is None else float(self.task_timeout_sec)
                    rows = fut.result(timeout=timeout)
                except Exception:
                    rows = self._flash_chunk_local(chunk)
                for row in rows:
                    rows_out[int(row[0])] = row

        out: List[FlashResult] = []
        for row in rows_out:
            if row is None:
                raise RuntimeError("Internal error: missing row result from flash batch")
            _idx, x, y, K, HL, HV, Zfac = row
            out.append(
                FlashResult(
                    x=np.asarray(x, dtype=float),
                    y=np.asarray(y, dtype=float),
                    K=np.asarray(K, dtype=float),
                    HL_BTU_lbmol=float(HL),
                    HV_BTU_lbmol=float(HV),
                    Z=(None if Zfac is None else float(Zfac)),
                    cpL_BTU_lbmolF=None,
                    cpV_BTU_lbmolF=None,
                )
            )
        return out
