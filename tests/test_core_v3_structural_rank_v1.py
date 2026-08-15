import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank

from dynamic_distillation.core_v3.structural_rank_v1 import structural_rank_fast


def test_structural_rank_fast_matches_scipy_on_small_patterns():
    rng = np.random.default_rng(20260815)
    patterns = [
        np.zeros((0, 0), dtype=np.int8),
        np.zeros((3, 4), dtype=np.int8),
        np.eye(8, dtype=np.int8),
        np.tri(12, 12, dtype=np.int8),
        (rng.random((30, 24)) < 0.12).astype(np.int8),
    ]

    for pattern in patterns:
        assert structural_rank_fast(pattern) == structural_rank(csr_matrix(pattern))


def test_structural_rank_fast_detects_full_and_deficient_rectangular_matchings():
    full = csr_matrix(
        (
            np.ones(6, dtype=np.int8),
            ([0, 1, 2, 3, 4, 5], [5, 4, 3, 2, 1, 0]),
        ),
        shape=(6, 8),
    )
    deficient = full.copy().tolil()
    deficient[5, 0] = 0

    assert structural_rank_fast(full) == 6
    assert structural_rank_fast(deficient.tocsr()) == 5
