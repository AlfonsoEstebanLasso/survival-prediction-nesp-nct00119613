"""
src/models/cox_baseline.py

Proposito:
    Baseline de regresion de Cox proporcional para los endpoints OS (DTH/DTHDY) y
    PFS (PFSCD/PFSDY) del ensayo NESP NCT00119613. Sirve como referencia de rendimiento
    para comparar con RSF y XGBoost/LightGBM.

Entradas:
    output/nesp_nct00119613_dataset.csv   (generado por etl_nesp_nct00119613.py)

Salidas:
    output/cox_baseline_metrics.json      Metricas completas por endpoint (CV + bootstrap)
    output/cox_baseline_cv_detail.csv     C-index e IBS por fold y endpoint

Metodologia:
    - Validacion cruzada estratificada k=5. Estrato = indicador de evento x TXG (4 clases).
    - En cada fold: build_preprocessor() ajustado SOLO sobre el fold de entrenamiento.
    - Metricas por fold: C-index (concordance index) e IBS (Integrated Brier Score).
    - Bootstrap n=1000 sobre las predicciones OOF (out-of-fold) agregadas.
    - Endpoints OS y PFS ejecutados de forma independiente.
    - Los valores generados son REALES y reemplazan los ilustrativos de PEC3.

Control anti-leakage:
    El preprocesador se ajusta dentro de cada fold sobre el subconjunto de entrenamiento.
    La rejilla de tiempos para IBS se recorta al rango de eventos del fold de entrenamiento.
    El bootstrap usa solo las predicciones OOF (nunca datos de entrenamiento del fold).
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from sksurv.linear_model import CoxPHSurvivalAnalysis
from sksurv.metrics import concordance_index_censored, integrated_brier_score

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.preprocessing.build_preprocessor import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    build_preprocessor,
)

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------

SEED = 42
K_FOLDS = 5
N_BOOTSTRAP = 1000
N_TIME_GRID = 25
TIME_Q_LOW = 10.0
TIME_Q_HIGH = 90.0

ENDPOINTS: dict[str, dict[str, str]] = {
    "OS":  {"event": "DTH",   "time": "DTHDY"},
    "PFS": {"event": "PFSCD", "time": "PFSDY"},
}

FEATURES: list[str] = NUMERIC_FEATURES + CATEGORICAL_FEATURES

DATASET_PATH = PROJECT_ROOT / "output" / "nesp_nct00119613_dataset.csv"
OUTPUT_DIR   = PROJECT_ROOT / "output"


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def setup_logger() -> logging.Logger:
    logger = logging.getLogger("cox_baseline")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(message)s", "%H:%M:%S"
        ))
        logger.addHandler(sh)
    return logger


def make_y(event: np.ndarray, time: np.ndarray) -> np.ndarray:
    """Array estructurado requerido por scikit-survival."""
    return np.array(
        [(bool(e), float(t)) for e, t in zip(event, time)],
        dtype=[("event", bool), ("time", float)],
    )


def event_time_grid(y: np.ndarray) -> np.ndarray:
    """25 puntos entre los percentiles TIME_Q_LOW y TIME_Q_HIGH de los tiempos de evento."""
    event_times = y["time"][y["event"]]
    return np.percentile(event_times, np.linspace(TIME_Q_LOW, TIME_Q_HIGH, N_TIME_GRID))


# ---------------------------------------------------------------------------
# Un fold
# ---------------------------------------------------------------------------

def run_fold(
    X_tr: pd.DataFrame,
    X_te: pd.DataFrame,
    y_tr: np.ndarray,
    y_te: np.ndarray,
    global_times: np.ndarray,
) -> dict:
    """
    Ajusta preprocesador y Cox sobre el fold de entrenamiento; evalua en el fold de test.

    La rejilla de tiempos para IBS se recorta al maximo tiempo de evento del entrenamiento
    para garantizar la validez del estimador IPCW de Kaplan-Meier.
    """
    preprocessor = build_preprocessor()
    X_tr_proc = preprocessor.fit_transform(X_tr)
    X_te_proc = preprocessor.transform(X_te)

    cox = CoxPHSurvivalAnalysis(alpha=0, ties="efron", n_iter=100)
    cox.fit(X_tr_proc, y_tr)

    c_index = float(cox.score(X_te_proc, y_te))

    # Maximo tiempo observado en training (incluye censurados): cota superior del IPCW KM.
    t_max_obs_train = float(y_tr["time"].max())
    # La rejilla de tiempos debe ser estrictamente menor que t_max_obs_train.
    fold_times = global_times[global_times < t_max_obs_train]

    surv_fns = cox.predict_survival_function(X_te_proc)
    surv_mat_full = np.vstack([fn(global_times) for fn in surv_fns])
    surv_mat_fold = np.vstack([fn(fold_times)   for fn in surv_fns])

    # IPCW requiere que los tiempos de los sujetos de test esten dentro del rango de training.
    valid = y_te["time"] < t_max_obs_train
    ibs = float(
        integrated_brier_score(y_tr, y_te[valid], surv_mat_fold[valid], fold_times)
    )
    risk_scores = cox.predict(X_te_proc)

    return {
        "c_index": c_index,
        "ibs": ibs,
        "risk_scores": risk_scores,
        "surv_mat_full": surv_mat_full,   # evaluado en global_times (para OOF bootstrap)
        "t_max_obs_train": t_max_obs_train,
    }


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def bootstrap_cindex(
    y_all: np.ndarray,
    oof_risk: np.ndarray,
    n: int = N_BOOTSTRAP,
    seed: int = SEED,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n_samples = len(y_all)
    results = []
    for _ in range(n):
        idx = rng.integers(0, n_samples, size=n_samples)
        try:
            c, *_ = concordance_index_censored(
                y_all["event"][idx], y_all["time"][idx], oof_risk[idx]
            )
            results.append(c)
        except Exception:
            continue
    return np.array(results)


def bootstrap_ibs(
    y_all: np.ndarray,
    oof_surv: np.ndarray,
    times: np.ndarray,
    n: int = N_BOOTSTRAP,
    seed: int = SEED,
) -> np.ndarray:
    # y_all se usa como referencia IPCW; oof_surv[idx] es el test remuestreado.
    rng = np.random.default_rng(seed + 1)
    n_samples = len(y_all)
    results = []
    for _ in range(n):
        idx = rng.integers(0, n_samples, size=n_samples)
        try:
            ibs = float(integrated_brier_score(y_all, y_all[idx], oof_surv[idx], times))
            results.append(ibs)
        except Exception:
            continue
    return np.array(results)


# ---------------------------------------------------------------------------
# Por endpoint
# ---------------------------------------------------------------------------

def run_endpoint(
    df: pd.DataFrame,
    endpoint_name: str,
    event_col: str,
    time_col: str,
    logger: logging.Logger,
) -> dict:
    logger.info(
        "=== Endpoint %s  (evento=%s, tiempo=%s) ===",
        endpoint_name, event_col, time_col,
    )

    y = make_y(df[event_col].values, df[time_col].values)
    X = df[FEATURES].copy()

    # Estrato: evento (0/1) x TXG (0/1) => 4 clases para estratificacion del CV.
    strata = df[event_col].astype(int).values * 2 + df["TXG"].astype(int).values

    global_times = event_time_grid(y)
    logger.info(
        "Rejilla global: %d puntos, rango [%.1f, %.1f] dias.",
        len(global_times), global_times[0], global_times[-1],
    )

    cv = StratifiedKFold(n_splits=K_FOLDS, shuffle=True, random_state=SEED)

    fold_metrics: list[dict] = []
    oof_risk = np.empty(len(df))
    oof_surv = np.zeros((len(df), len(global_times)))
    t_max_per_fold: list[float] = []

    for fold_i, (train_idx, test_idx) in enumerate(cv.split(X, strata)):
        result = run_fold(
            X.iloc[train_idx], X.iloc[test_idx],
            y[train_idx], y[test_idx],
            global_times,
        )
        fold_metrics.append({
            "fold": fold_i + 1,
            "n_train": int(len(train_idx)),
            "n_test": int(len(test_idx)),
            "c_index": result["c_index"],
            "ibs": result["ibs"],
        })
        oof_risk[test_idx] = result["risk_scores"]
        oof_surv[test_idx] = result["surv_mat_full"]
        t_max_per_fold.append(result["t_max_obs_train"])

        logger.info(
            "  Fold %d/%d: C-index=%.4f  IBS=%.4f",
            fold_i + 1, K_FOLDS, result["c_index"], result["ibs"],
        )

    # Recortar la rejilla global al tiempo maximo de evento minimo de todos los folds
    # para que el bootstrap IBS sea valido en todos los casos.
    t_max_common = min(t_max_per_fold)
    boot_times = global_times[global_times <= t_max_common]
    boot_surv = oof_surv[:, global_times <= t_max_common]

    # Resumen CV
    cv_cindex = [m["c_index"] for m in fold_metrics]
    cv_ibs    = [m["ibs"]     for m in fold_metrics]
    cv_c_mean, cv_c_std = float(np.mean(cv_cindex)), float(np.std(cv_cindex, ddof=1))
    cv_i_mean, cv_i_std = float(np.mean(cv_ibs)),    float(np.std(cv_ibs, ddof=1))
    cv_c_pct = round(100 * cv_c_std / cv_c_mean, 2) if cv_c_mean else None
    cv_i_pct = round(100 * cv_i_std / cv_i_mean, 2) if cv_i_mean else None

    logger.info(
        "CV C-index: %.4f +/- %.4f  (CV%%=%.2f%%)", cv_c_mean, cv_c_std, cv_c_pct or 0
    )
    logger.info(
        "CV IBS:     %.4f +/- %.4f  (CV%%=%.2f%%)", cv_i_mean, cv_i_std, cv_i_pct or 0
    )

    # Bootstrap
    logger.info("Bootstrap n=%d sobre predicciones OOF...", N_BOOTSTRAP)
    boot_c = bootstrap_cindex(y, oof_risk, n=N_BOOTSTRAP, seed=SEED)
    boot_i = bootstrap_ibs(y, boot_surv, boot_times, n=N_BOOTSTRAP, seed=SEED)

    def ci95(arr: np.ndarray) -> dict:
        return {
            "mean":    float(np.mean(arr)),
            "std":     float(np.std(arr, ddof=1)),
            "ci_low":  float(np.percentile(arr, 2.5)),
            "ci_high": float(np.percentile(arr, 97.5)),
        }

    bc, bi = ci95(boot_c), ci95(boot_i)
    logger.info(
        "Boot C-index: %.4f  IC95%% [%.4f, %.4f]", bc["mean"], bc["ci_low"], bc["ci_high"]
    )
    logger.info(
        "Boot IBS:     %.4f  IC95%% [%.4f, %.4f]", bi["mean"], bi["ci_low"], bi["ci_high"]
    )

    return {
        "endpoint": endpoint_name,
        "event_col": event_col,
        "time_col": time_col,
        "n_events":   int(y["event"].sum()),
        "n_censored": int((~y["event"]).sum()),
        "cv": {
            "k": K_FOLDS,
            "c_index": {
                "per_fold": cv_cindex,
                "mean": cv_c_mean,
                "std":  cv_c_std,
                "cv_pct": cv_c_pct,
            },
            "ibs": {
                "per_fold": cv_ibs,
                "mean": cv_i_mean,
                "std":  cv_i_std,
                "cv_pct": cv_i_pct,
            },
        },
        "bootstrap": {
            "n": N_BOOTSTRAP,
            "c_index": bc,
            "ibs":     bi,
        },
        "fold_detail": fold_metrics,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    logger = setup_logger()
    np.random.seed(SEED)

    if not DATASET_PATH.exists():
        logger.error("Dataset no encontrado: %s. Ejecuta primero el ETL.", DATASET_PATH)
        return 1

    df = pd.read_csv(DATASET_PATH)
    logger.info("Dataset: %d sujetos, %d columnas.", *df.shape)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_results: dict[str, dict] = {}
    cv_rows: list[dict] = []

    for ep_name, ep_cfg in ENDPOINTS.items():
        result = run_endpoint(
            df,
            endpoint_name=ep_name,
            event_col=ep_cfg["event"],
            time_col=ep_cfg["time"],
            logger=logger,
        )
        all_results[ep_name] = result

        for fm in result["fold_detail"]:
            cv_rows.append({"endpoint": ep_name, **fm})

    # JSON con todas las metricas
    metrics_path = OUTPUT_DIR / "cox_baseline_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(all_results, fh, ensure_ascii=False, indent=2)
    logger.info("Guardado: %s", metrics_path.name)

    # CSV con detalle por fold
    detail_path = OUTPUT_DIR / "cox_baseline_cv_detail.csv"
    pd.DataFrame(cv_rows).to_csv(detail_path, index=False)
    logger.info("Guardado: %s", detail_path.name)

    # Resumen en consola
    sep = "=" * 62
    print(f"\n{sep}")
    print("  BASELINE COX PROPORCIONAL  -  NESP NCT00119613")
    print(sep)
    for ep_name, res in all_results.items():
        cv_c = res["cv"]["c_index"]
        cv_i = res["cv"]["ibs"]
        bt_c = res["bootstrap"]["c_index"]
        bt_i = res["bootstrap"]["ibs"]
        print(f"\n  Endpoint {ep_name}  "
              f"(eventos={res['n_events']}, censurados={res['n_censored']})")
        print(f"  {'':4}CV  C-index : {cv_c['mean']:.4f} +/- {cv_c['std']:.4f}"
              f"  (CV%={cv_c['cv_pct']}%)")
        print(f"  {'':4}CV  IBS     : {cv_i['mean']:.4f} +/- {cv_i['std']:.4f}"
              f"  (CV%={cv_i['cv_pct']}%)")
        print(f"  {'':4}Boot C-idx : {bt_c['mean']:.4f}"
              f"  IC95% [{bt_c['ci_low']:.4f}, {bt_c['ci_high']:.4f}]")
        print(f"  {'':4}Boot IBS   : {bt_i['mean']:.4f}"
              f"  IC95% [{bt_i['ci_low']:.4f}, {bt_i['ci_high']:.4f}]")
        print(f"\n  {'Fold':>6}  {'C-index':>9}  {'IBS':>8}")
        print(f"  {'-'*6}  {'-'*9}  {'-'*8}")
        for fm in res["fold_detail"]:
            print(f"  {fm['fold']:>6}  {fm['c_index']:>9.4f}  {fm['ibs']:>8.4f}")
    print(f"\n{sep}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
