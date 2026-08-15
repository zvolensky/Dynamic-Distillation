"""Deterministic structural rank without SciPy's pathological match cases."""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np
from scipy.sparse import csr_matrix


def structural_rank_fast(pattern: Any) -> int:
    """Return bipartite structural rank with Hopcroft-Karp matching."""
    matrix = csr_matrix(pattern)
    row_count, column_count = matrix.shape
    if row_count == 0 or column_count == 0 or matrix.nnz == 0:
        return 0
    matrix.sum_duplicates()
    matrix.sort_indices()
    pair_row = np.full(row_count, -1, dtype=np.int64)
    pair_column = np.full(column_count, -1, dtype=np.int64)
    distance = np.empty(row_count, dtype=np.int64)

    def breadth_first_search() -> bool:
        queue: deque[int] = deque()
        distance.fill(-1)
        for row in range(row_count):
            if pair_row[row] < 0:
                distance[row] = 0
                queue.append(row)
        augmenting_path_exists = False
        while queue:
            row = queue.popleft()
            start, stop = matrix.indptr[row : row + 2]
            for column in matrix.indices[start:stop]:
                matched_row = int(pair_column[column])
                if matched_row < 0:
                    augmenting_path_exists = True
                elif distance[matched_row] < 0:
                    distance[matched_row] = distance[row] + 1
                    queue.append(matched_row)
        return augmenting_path_exists

    def depth_first_search(row: int) -> bool:
        start, stop = matrix.indptr[row : row + 2]
        for column_value in matrix.indices[start:stop]:
            column = int(column_value)
            matched_row = int(pair_column[column])
            if matched_row < 0 or (
                distance[matched_row] == distance[row] + 1
                and depth_first_search(matched_row)
            ):
                pair_row[row] = column
                pair_column[column] = row
                return True
        distance[row] = -1
        return False

    matching = 0
    while breadth_first_search():
        for row in range(row_count):
            if pair_row[row] < 0 and depth_first_search(row):
                matching += 1
    return matching


__all__ = ["structural_rank_fast"]
