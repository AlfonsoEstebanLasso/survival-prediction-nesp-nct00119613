"""
src/models/cv_utils.py

Utilidades compartidas por todos los modelos de supervivencia del TFG:
constantes de la validacion, construccion del array estructurado, rejilla de tiempos
para el IBS y bootstrap de C-index e IBS sobre predicciones OOF.
"""

from __future__ import annotations

import numpy as np
from sksurv.metrics import concordance_index_censored, integrated_brier_score

# ---------------------------------------------------------------------------
# Constantes del esquema de validacion
# ---------------------------------------------------------------------------

SEED       = 42
K_FOLDS    = 5
N_BOOTSTRAP = 1000
N_TIME_GRID = 25
TIME_Q_LOW  = 10.0
TIME_Q_HIGH = 90.0

ENDPOINTS: dict[str, dict[str, str]] = {
    "OS":  {"event": "DTH",   "time": "DTHDY"},
    "PFS": {"event": "PFSCD", "time": "PFSDY"},
}


# ---------------------------------------------------------------------------
# Array estructurado para scikit-survival
# ---------------------------------------------------------------------------

def make_y(event: np.ndarray, time: np.ndarray) -> np.ndarray:
    return np.array(
        [(bool(e), float(t)) for e, t in zip(event, time)],
        dtype=[("event", bool), ("time", float)],
    )


# ---------------------------------------------------------------------------
# Rejilla de tiempos para IBS
# ---------------------------------------------------------------------------

def event_time_grid(y: np.ndarray) -> np.ndarray:
    """25 puntos entre TIME_Q_LOW y TIME_Q_HIGH de los tiempos de evento."""
    event_times = y["time"][y["event"]]
    return np.percentile(event_times, np.linspace(TIME_Q_LOW, TIME_Q_HIGH, N_TIME_GRID))


def safe_fold_times(global_times: np.ndarray, y_tr: np.ndarray) -> np.ndarray:
    """
    Recorta la rejilla al maximo tiempo observado en el fold de entrenamiento
    (requisito del estimador IPCW de Kaplan-Meier para el IBS).
    """
    return global_times[global_times < y_tr["time"].max()]


def safe_ibs(y_tr, y_te, surv_mat, fold_times) -> float:
    """
    IBS con filtrado de sujetos de test fuera del rango de entrenamiento.
    Devuelve NaN si no hay sujetos validos.
    """
    valid = y_te["time"] < y_tr["time"].max()
    if valid.sum() == 0 or len(fold_times) == 0:
        return float("nan")
    return float(integrated_brier_score(y_tr, y_te[valid], surv_mat[valid], fold_times))


# ---------------------------------------------------------------------------
# Bootstrap sobre predicciones OOF
# ---------------------------------------------------------------------------

def bootstrap_cindex(
    y_all: np.ndarray,
    oof_risk: np.ndarray,
    n: int = N_BOOTSTRAP,
    seed: int = SEED,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n_samples = len(y_all)
    out = []
    for _ in range(n):
        idx = rng.integers(0, n_samples, size=n_samples)
        try:
            c, *_ = concordance_index_censored(
                y_all["event"][idx], y_all["time"][idx], oof_risk[idx]
            )
            out.append(c)
        except Exception:
            continue
    return np.array(out)


def bootstrap_ibs(
    y_all: np.ndarray,
    oof_surv: np.ndarray,
    times: np.ndarray,
    n: int = N_BOOTSTRAP,
    seed: int = SEED,
) -> np.ndarray:
    rng = np.random.default_rng(seed + 1)
    n_samples = len(y_all)
    out = []
    for _ in range(n):
        idx = rng.integers(0, n_samples, size=n_samples)
        try:
            ibs = float(integrated_brier_score(y_all, y_all[idx], oof_surv[idx], times))
            out.append(ibs)
        except Exception:
            continue
    return np.array(out)


def ci95(arr: np.ndarray) -> dict:
    return {
        "mean":    float(np.mean(arr)),
        "std":     float(np.std(arr, ddof=1)),
        "ci_low":  float(np.percentile(arr, 2.5)),
        "ci_high": float(np.percentile(arr, 97.5)),
    }


# ---------------------------------------------------------------------------
# Estratificacion para el CV
# ---------------------------------------------------------------------------

def make_strata(df, event_col: str) -> np.ndarray:
    """Estrato = indicador de evento x TXG => 4 clases (0-3)."""
    return df[event_col].astype(int).values * 2 + df["TXG"].astype(int).values
