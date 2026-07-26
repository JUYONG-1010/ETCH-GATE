"""Shared finite-sample statistical utilities."""

from __future__ import annotations

import numpy as np


def lot_cluster_bootstrap_mean(
    lot_values: np.ndarray,
    *,
    replicates: int,
    random_seed: int,
) -> np.ndarray:
    """Resample complete lot-level values and return bootstrap means."""

    values = np.asarray(lot_values, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError("lot_values must be a finite non-empty vector")
    if replicates < 1:
        raise ValueError("replicates must be positive")
    generator = np.random.default_rng(random_seed)
    return generator.choice(
        values,
        size=(replicates, len(values)),
        replace=True,
    ).mean(axis=1)
