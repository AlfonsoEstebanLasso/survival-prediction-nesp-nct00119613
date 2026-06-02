"""
src/models/rsf_model.py

Proposito:
    Random Survival Forest con optimizacion de hiperparametros mediante Optuna.
    Mismo esquema de validacion cruzada estratificada k=5 y bootstrap n=1000
    que el baseline Cox (cv_utils.py).

Entradas:
    output/nesp_nct00119613_dataset.csv

Salidas:
    output/rsf_metrics.json      Metricas completas (CV + bootstrap) por endpoint

Metodologia:
    - Optuna TPE con 30 trials y MedianPruner.
    - Warm-start incremental (50 -> 200 arboles) para activar el pruner en cada trial.
    - Hiperparametros buscados: min_samples_split, min_samples_leaf, max_features, max_samples.
    - Modelo final por fold: 300 arboles con los mejores hiperparametros.
    - Ajuste y busqueda de hiperparametros SOLO sobre el fold de entrenamiento.
"""

from __future__ import annotations

import json
import logging
import sys
import warnings
from pathlib import Path

import numpy as np
import optuna
import pandas as pd
from sklearn.model_selection import StratifiedKFold, StratifiedShuffleSplit

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.cv_utils import (
    ENDPOINTS, K_FOLDS, N_BOOTSTRAP, SEED,
    bootstrap_cindex, bootstrap_ibs, ci95,
    event_time_grid, make_strata, make_y, safe_fold_times, safe_ibs,
)
from src.preprocessing.build_preprocessor import (
    CATEGORICAL_FEATURES, NUMERIC_FEATURES, build_preprocessor,
)

optuna.logging.set_verbosity(optuna.logging.WARNING)
warnings.filterwarnings("ignore")

from sksurv.ensemble import RandomSurvivalForest

FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
N_TRIALS_RSF   = 30
N_TREES_FINAL  = 300
DATASET_PATH   = PROJECT_ROOT / "output" / "nesp_nct00119613_dataset.csv"
OUTPUT_DIR     = PROJECT_ROOT / "output"


# ---------------------------------------------------------------------------
# Optuna: objetivo con warm-start incremental
# ---------------------------------------------------------------------------

# _make_rsf_objective: genera la funcion objetivo de Optuna para ajustar el RSF.
# Recibe las particiones interna de entrenamiento y validacion (matrices numpy)
# ya preprocesadas. Devuelve una funcion 'objective' que Optuna invoca en cada trial.
# Justificacion: el RSF es un modelo no lineal basado en bosques de supervivencia;
# la busqueda de hiperparametros se realiza DENTRO del fold de entrenamiento
# (nunca expone el conjunto de test externo) para respetar el control anti-fuga.
# El warm-start incremental (50 -> 200 arboles) permite al MedianPruner descartar
# configuraciones poco prometedoras antes de completar el entrenamiento completo,
# reduciendo el coste computacional sin sesgar la busqueda.
def _make_rsf_objective(X_inner: np.ndarray, X_val: np.ndarray,
                         y_inner: np.ndarray, y_val: np.ndarray):
    def objective(trial: optuna.Trial) -> float:
        params = {
            "min_samples_split": trial.suggest_int("min_samples_split", 5, 25),
            "min_samples_leaf":  trial.suggest_int("min_samples_leaf", 2, 10),
            "max_features":      trial.suggest_categorical("max_features", ["sqrt", "log2"]),
            "max_samples":       trial.suggest_float("max_samples", 0.5, 0.9),
        }
        rsf = RandomSurvivalForest(
            n_estimators=50, warm_start=True,
            random_state=SEED, n_jobs=1, **params,
        )
        c_last = 0.5
        for step, n_est in enumerate([50, 200]):
            rsf.n_estimators = n_est
            try:
                rsf.fit(X_inner, y_inner)
                c_last = float(rsf.score(X_val, y_val))
            except Exception:
                c_last = 0.5
            trial.report(c_last, step)
            if trial.should_prune():
                raise optuna.TrialPruned()
        return c_last
    return objective


# optimize_rsf: ejecuta el estudio Optuna con muestreador TPE para el RSF.
# Entradas: conjuntos de entrenamiento e interno de validacion (numpy arrays),
# y la semilla especifica del fold para garantizar reproducibilidad entre ejecuciones.
# Salida: diccionario con los mejores hiperparametros encontrados en los 30 trials.
# Justificacion: el muestreador TPE (Tree-structured Parzen Estimator) aproxima
# la distribucion de hiperparametros que maximizan el C-index, siendo mas eficiente
# que la busqueda en rejilla en espacios de alta dimension. La semilla por fold
# (SEED + fold_i) preserva la reproducibilidad sin repetir la misma secuencia de
# trials en cada fold de la validacion cruzada.
def optimize_rsf(X_tr: np.ndarray, y_tr: np.ndarray,
                 X_val: np.ndarray, y_val: np.ndarray,
                 fold_seed: int) -> dict:
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=fold_seed),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=0),
    )
    study.optimize(
        _make_rsf_objective(X_tr, X_val, y_tr, y_val),
        n_trials=N_TRIALS_RSF,
        show_progress_bar=False,
    )
    return study.best_params


# ---------------------------------------------------------------------------
# Un fold
# ---------------------------------------------------------------------------

# run_fold: ejecuta el ciclo completo de un fold de la validacion cruzada para el RSF.
# Entradas: DataFrames de train y test del fold, arrays estructurados de supervivencia
# (evento + tiempo), rejilla global de tiempos, indice del fold y logger.
# Salida: diccionario con C-index, IBS, scores de riesgo, matriz de supervivencia OOF
# y tiempo maximo observado en entrenamiento.
# Justificacion: el preprocesado (imputacion, escalado, codificacion) se ajusta
# exclusivamente sobre X_tr para evitar fuga de informacion hacia el fold de test.
# La busqueda de hiperparametros se delega en un split estratificado interno del 20%,
# de modo que el conjunto de test externo permanece virgen durante toda la optimizacion.
# El modelo final usa 300 arboles (N_TREES_FINAL), valor que equilibra varianza y coste
# computacional para n moderado (n=479 sujetos en esta cohorte).
# Nota oncologica: el target estructurado (evento OS/PFS + tiempo DTHDY/PFSDY) incluye
# la censura, lo que permite al RSF aprovechar la informacion parcial de los sujetos
# vivos al cierre del seguimiento.
def run_fold(X_tr: pd.DataFrame, X_te: pd.DataFrame,
             y_tr: np.ndarray, y_te: np.ndarray,
             global_times: np.ndarray, fold_i: int,
             logger: logging.Logger) -> dict:

    # Preprocesado: ajustar SOLO sobre el fold de entrenamiento.
    preprocessor = build_preprocessor()
    X_tr_proc = preprocessor.fit_transform(X_tr)
    X_te_proc = preprocessor.transform(X_te)

    # Split interno para busqueda de hiperparametros (20% del fold de entrenamiento).
    sss = StratifiedShuffleSplit(n_splits=1, test_size=0.20,
                                 random_state=SEED + fold_i)
    event_labels = y_tr["event"].astype(int)
    inner_tr_idx, inner_val_idx = next(sss.split(X_tr_proc, event_labels))

    best_params = optimize_rsf(
        X_tr_proc[inner_tr_idx], y_tr[inner_tr_idx],
        X_tr_proc[inner_val_idx], y_tr[inner_val_idx],
        fold_seed=SEED + fold_i,
    )
    logger.info("    Fold %d best_params: %s", fold_i + 1, best_params)

    # Modelo final: 300 arboles (N_TREES_FINAL), fijando la semilla global para reproducibilidad.
    rsf = RandomSurvivalForest(
        n_estimators=N_TREES_FINAL, random_state=SEED, n_jobs=-1, **best_params
    )
    rsf.fit(X_tr_proc, y_tr)

    c_index = float(rsf.score(X_te_proc, y_te))
    risk_scores = rsf.predict(X_te_proc)

    fold_times = safe_fold_times(global_times, y_tr)
    surv_fns   = rsf.predict_survival_function(X_te_proc)
    surv_mat   = np.vstack([fn(fold_times) for fn in surv_fns])
    surv_full  = np.vstack([fn(global_times) for fn in surv_fns])
    ibs        = safe_ibs(y_tr, y_te, surv_mat, fold_times)

    logger.info("    Fold %d: C-index=%.4f  IBS=%.4f", fold_i + 1, c_index, ibs)
    return {
        "c_index": c_index, "ibs": ibs,
        "risk_scores": risk_scores,
        "surv_full": surv_full,
        "t_max_obs": float(y_tr["time"].max()),
    }


# ---------------------------------------------------------------------------
# Por endpoint
# ---------------------------------------------------------------------------

# run_endpoint: orquesta la validacion cruzada estratificada k=5 y el bootstrap
# para un endpoint concreto (OS o PFS) con el modelo RSF.
# Entradas: DataFrame completo del dataset, nombre del endpoint, columnas de evento
# y tiempo, y logger.
# Salida: diccionario con metricas CV (C-index e IBS por fold, media, std, CV%) y
# estimaciones bootstrap (media, IC95%) listas para serializar a JSON.
# Justificacion: la estratificacion de los folds por la variable combinada
# (evento x brazo TXG) garantiza que la proporcion de eventos y la distribucion
# del brazo de aleatorizacion sean homogeneas entre folds, lo cual es critico
# para la validez interna en cohortes pequenas (n=479).
# Los scores OOF (out-of-fold) se agregan para construir las curvas de supervivencia
# globales que alimentan el bootstrap, evitando el sesgo de estimacion en muestra.
def run_endpoint(df: pd.DataFrame, endpoint_name: str,
                 event_col: str, time_col: str,
                 logger: logging.Logger) -> dict:
    logger.info("=== RSF | Endpoint %s ===", endpoint_name)

    y = make_y(df[event_col].values, df[time_col].values)
    X = df[FEATURES].copy()
    strata = make_strata(df, event_col)
    global_times = event_time_grid(y)

    cv = StratifiedKFold(n_splits=K_FOLDS, shuffle=True, random_state=SEED)

    fold_metrics, oof_risk = [], np.empty(len(df))
    oof_surv = np.zeros((len(df), len(global_times)))
    t_max_per_fold = []

    for fold_i, (train_idx, test_idx) in enumerate(cv.split(X, strata)):
        res = run_fold(
            X.iloc[train_idx], X.iloc[test_idx],
            y[train_idx], y[test_idx],
            global_times, fold_i, logger,
        )
        fold_metrics.append({"fold": fold_i + 1,
                             "c_index": res["c_index"], "ibs": res["ibs"]})
        oof_risk[test_idx] = res["risk_scores"]  # agregacion OOF: cada sujeto puntua desde el fold en que fue test
        oof_surv[test_idx] = res["surv_full"]
        t_max_per_fold.append(res["t_max_obs"])

    cv_c = [m["c_index"] for m in fold_metrics]
    cv_i = [m["ibs"]     for m in fold_metrics]
    cv_c_mean, cv_c_std = float(np.mean(cv_c)), float(np.std(cv_c, ddof=1))
    cv_i_mean, cv_i_std = float(np.nanmean(cv_i)), float(np.nanstd(cv_i, ddof=1))
    logger.info("CV C-index: %.4f +/- %.4f", cv_c_mean, cv_c_std)
    logger.info("CV IBS:     %.4f +/- %.4f", cv_i_mean, cv_i_std)

    t_max_common = min(t_max_per_fold)
    boot_times = global_times[global_times < t_max_common]
    boot_surv  = oof_surv[:, global_times < t_max_common]

    logger.info("Bootstrap n=%d...", N_BOOTSTRAP)
    boot_c = bootstrap_cindex(y, oof_risk, n=N_BOOTSTRAP, seed=SEED)
    boot_i = bootstrap_ibs(y, boot_surv, boot_times, n=N_BOOTSTRAP, seed=SEED)
    bc, bi = ci95(boot_c), ci95(boot_i)
    logger.info("Boot C-index: %.4f  IC95%% [%.4f, %.4f]",
                bc["mean"], bc["ci_low"], bc["ci_high"])
    logger.info("Boot IBS:     %.4f  IC95%% [%.4f, %.4f]",
                bi["mean"], bi["ci_low"], bi["ci_high"])

    return {
        "model": "RSF",
        "endpoint": endpoint_name,
        "n_events":   int(y["event"].sum()),
        "n_censored": int((~y["event"]).sum()),
        "cv": {
            "k": K_FOLDS,
            "c_index": {"per_fold": cv_c, "mean": cv_c_mean, "std": cv_c_std,
                        "cv_pct": round(100 * cv_c_std / cv_c_mean, 2)},
            "ibs":     {"per_fold": cv_i, "mean": cv_i_mean, "std": cv_i_std,
                        "cv_pct": round(100 * cv_i_std / cv_i_mean, 2) if cv_i_mean else None},
        },
        "bootstrap": {"n": N_BOOTSTRAP, "c_index": bc, "ibs": bi},
        "fold_detail": fold_metrics,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# setup_logger: configura y devuelve un logger con formato de hora, nivel e
# identificador de modulo. Evita anadir manejadores duplicados si se llama
# varias veces en la misma sesion de Python.
def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(message)s", "%H:%M:%S"))
        logger.addHandler(sh)
    return logger


# main: punto de entrada del script RSF. Carga el dataset derivado, ejecuta
# la validacion cruzada con bootstrap para OS y PFS, y serializa los resultados
# en output/rsf_metrics.json.
# Justificacion: centralizar la ejecucion en main() facilita el uso del modulo
# tanto como script autonomo (python rsf_model.py) como desde un orquestador
# de pipeline, manteniendo la semilla global (np.random.seed) para reproducibilidad.
def main() -> int:
    logger = setup_logger("rsf_model")
    np.random.seed(SEED)

    if not DATASET_PATH.exists():
        logger.error("Dataset no encontrado: %s", DATASET_PATH)
        return 1
    df = pd.read_csv(DATASET_PATH)
    logger.info("Dataset: %d sujetos.", len(df))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    for ep_name, ep_cfg in ENDPOINTS.items():
        results[ep_name] = run_endpoint(
            df, ep_name, ep_cfg["event"], ep_cfg["time"], logger)

    out_path = OUTPUT_DIR / "rsf_metrics.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    logger.info("Guardado: %s", out_path.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
