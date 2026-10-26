#!/usr/bin/env python3
"""Least squares, written out rather than imported.

The monitor is standard library only so its scheduled run has no install step.
That rules out numpy, so the normal equations are solved here directly: build
X'X and X'y, then Gaussian elimination with partial pivoting. For the handful of
regressors this model uses that is both exact enough and fast.
"""


def _solve(matrix, rhs):
    """Gaussian elimination with partial pivoting. Returns None if singular."""
    n = len(matrix)
    aug = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            return None
        aug[col], aug[pivot] = aug[pivot], aug[col]
        for row in range(col + 1, n):
            factor = aug[row][col] / aug[col][col]
            if factor:
                for k in range(col, n + 1):
                    aug[row][k] -= factor * aug[col][k]
    out = [0.0] * n
    for col in range(n - 1, -1, -1):
        total = aug[col][n] - sum(aug[col][k] * out[k] for k in range(col + 1, n))
        out[col] = total / aug[col][col]
    return out


def fit(X, y):
    """OLS with an intercept prepended. X is a list of feature rows."""
    design = [[1.0] + list(row) for row in X]
    k = len(design[0])
    xtx = [[sum(r[i] * r[j] for r in design) for j in range(k)] for i in range(k)]
    xty = [sum(r[i] * t for r, t in zip(design, y)) for i in range(k)]
    return _solve(xtx, xty)


def predict(beta, row):
    return beta[0] + sum(b * v for b, v in zip(beta[1:], row))
