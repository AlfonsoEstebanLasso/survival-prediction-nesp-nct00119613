"""
src/models/xgb_model.py

Proposito:
    XGBoost con perdida de Cox (survival:cox) y estimador de Breslow para las curvas
    de supervivencia. Misma validacion cruzada estratificada k=5 y bootstrap n=1000
    que el baseline Cox.

Entradas:
    output/nesp_nct00119613_dataset.csv

Salidas:
    output/xgb_metrics.json      Metricas completas (CV + bootstrap) por endpoint

Metodologia:
    - Optuna TPE con 40 trials y MedianPruner.
    - Early stopping nativo de XGBoost (early_stopping_rounds=25) en el split interno.
    - Hiperparametros buscados: max_depth, learning_rate, subsample, colsample_bytree,
      min_child_weight, reg_alpha.
    - Breslow estimator ajustado sobre el fold de entrenamiento para predecir S(t|x).
    - Modelo final: best_params con n_estimators determinado por early stopping en hold-out
      del 20% del fold de entrenamiento.
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
import xgboost as xgb
from sklearn.model_selection import StratifiedKFold, StratifiedShuffleSplit
from sksurv.metrics import concordance_index_censored

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

FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
N_TRIALS_XGB      = 40
XGB_MAX_TREES     = 500
XGB_EARLY_STOP    = 25
DATASET_PATH      = PROJECT_ROOT / "output" / "nesp_nct00119613_dataset.csv"
OUTPUT_DIR        = PROJECT_ROOT / "output"


# ---------------------------------------------------------------------------
# Formato de etiquetas para XGBoost survival:cox
# y > 0  => evento observado en el tiempo y
# y < 0  => censurado en el tiempo |y|
# ---------------------------------------------------------------------------

# _xgb_labels: convierte el array estructurado de supervivencia al formato
# de etiquetas que requiere XGBoost con objective='survival:cox'.
# Entrada: array numpy estructurado con campos 'event' (bool) y 'time' (float).
# Salida: array 1-D donde los tiempos de evento son positivos y los de censura negativos.
# Justificacion: la perdida de Cox de XGBoost espera y > 0 para eventos observados
# e y < 0 para observaciones censuradas; esta transformacion es obligatoria y es
# el unico punto de contacto entre el formato interno de sksurv y la API de XGBoost.
def _xgb_labels(y_struct: np.ndarray) -> np.ndarray:
    t = y_struct["time"].astype(float)  # tiempo en dias hasta el evento o censura
    return np.where(y_struct["event"], t, -t)  # positivo=evento, negativo=censura


# ---------------------------------------------------------------------------
# Estimador de Breslow para funciones de supervivencia
# ---------------------------------------------------------------------------

# BreslowEstimator: estima el hazard acumulado basal H0(t) mediante el estimador
# no parametrico de Breslow y lo combina con los log-hazards del modelo para
# obtener curvas de supervivencia individuales S(t|x) = exp(-H0(t) * exp(log_h(x))).
# Justificacion: XGBoost con survival:cox produce log-hazards relativos pero no
# curvas de supervivencia absolutas; el estimador de Breslow (ajustado SOLO sobre
# el fold de entrenamiento) cierra esa brecha sin asumir una forma parametrica
# para la funcion basal, lo cual es coherente con el supuesto semiparametrico de Cox.
# Este componente es imprescindible para calcular el IBS (Integrated Brier Score),
# que requiere probabilidades de supervivencia y no solo rankings de riesgo.
class BreslowEstimator:
    """
    Estima la funcion de supervivencia basal H0(t) a partir de los scores del modelo
    y la construye para nuevas observaciones: S(t|x) = exp(-H0(t) * exp(log_h(x))).
    """

    # fit: ajusta el estimador de Breslow sobre los datos de entrenamiento del fold.
    # Entradas: array estructurado de supervivencia y log-hazards predichos por XGBoost.
    # Salida: la propia instancia con times_ y cumhaz_ calculados (patron fluent).
    # Justificacion: se ordena por tiempo para recorrer los eventos en orden cronologico
    # y calcular el incremento de hazard en cada tiempo de evento como d(t) / R(t),
    # donde d(t) son los eventos y R(t) la suma de exp(log_h) sobre los sujetos en riesgo.
    def fit(self, y_struct: np.ndarray, log_hazard: np.ndarray) -> "BreslowEstimator":
        event = y_struct["event"]
        time  = y_struct["time"]
        exp_h = np.exp(log_hazard)

        order = np.argsort(time)
        t_ord, e_ord, h_ord = time[order], event[order], exp_h[order]

        unique_t = np.unique(t_ord[e_ord])
        H0 = np.zeros(len(unique_t))
        for i, t in enumerate(unique_t):
            d = int(((t_ord == t) & e_ord).sum())
            risk_sum = h_ord[t_ord >= t].sum()
            H0[i] = d / risk_sum if risk_sum > 1e-12 else 0.0

        self.times_  = unique_t
        self.cumhaz_ = np.cumsum(H0)
        return self

    # surv_matrix: construye la matriz de supervivencia S(t|x) para un conjunto de sujetos
    # y una rejilla de tiempos arbitraria.
    # Entradas: log-hazards del conjunto de evaluacion y vector de tiempos de la rejilla.
    # Salida: array de forma (n_samples, len(times)) con probabilidades en [0, 1].
    # Justificacion: la interpolacion lineal de cumhaz_ sobre times evita extrapolar
    # fuera del rango observado (left=0, right=cumhaz_[-1]), garantizando que S(t) sea
    # monotona decreciente y que el IBS se calcule sobre tiempos validos del fold.
    def surv_matrix(self, log_hazard: np.ndarray, times: np.ndarray) -> np.ndarray:
        """Array (n_samples, len(times)) con probabilidades de supervivencia."""
        H0_t = np.interp(times, self.times_, self.cumhaz_,
                         left=0.0, right=self.cumhaz_[-1])
        return np.exp(-np.outer(np.exp(log_hazard), H0_t))


# ---------------------------------------------------------------------------
# Optuna: objetivo XGBoost con early stopping
# ---------------------------------------------------------------------------

# _make_xgb_objective: genera la funcion objetivo de Optuna para XGBoost con survival:cox.
# Recibe las particiones internas de entrenamiento y validacion ya preprocesadas,
# y la semilla del fold. Devuelve una funcion 'objective' que Optuna invoca en cada trial.
# Justificacion: el early stopping nativo de XGBoost (early_stopping_rounds=25) detiene
# el entrenamiento cuando la funcion de perdida de Cox en el conjunto interno de validacion
# deja de mejorar durante 25 rondas consecutivas, lo que determina automaticamente el numero
# optimo de arboles sin necesidad de fijarlo a priori. Esto es especialmente relevante en
# cohortes pequenas (n=479) donde el sobreajuste aparece con pocos estimadores.
# El criterio de evaluacion final es el C-index (concordance_index_censored) y no la perdida
# de entrenamiento, lo que alinea la busqueda de hiperparametros con la metrica principal
# del protocolo de evaluacion.
def _make_xgb_objective(X_inner: np.ndarray, X_val: np.ndarray,
                         y_inner: np.ndarray, y_val: np.ndarray,
                         fold_seed: int):
    y_inner_xgb = _xgb_labels(y_inner)  # etiquetas en formato survival:cox para el subconjunto interno
    y_val_xgb   = _xgb_labels(y_val)    # etiquetas en formato survival:cox para el subconjunto de validacion interna

    def objective(trial: optuna.Trial) -> float:
        params = dict(
            max_depth          = trial.suggest_int("max_depth", 2, 5),
            learning_rate      = trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            subsample          = trial.suggest_float("subsample", 0.5, 1.0),
            colsample_bytree   = trial.suggest_float("colsample_bytree", 0.5, 1.0),
            min_child_weight   = trial.suggest_int("min_child_weight", 1, 10),
            reg_alpha          = trial.suggest_float("reg_alpha", 0.0, 1.0),
            reg_lambda         = trial.suggest_float("reg_lambda", 0.5, 3.0),
        )
        model = xgb.XGBRegressor(
            objective="survival:cox",
            eval_metric="cox-nloglik",
            n_estimators=XGB_MAX_TREES,
            early_stopping_rounds=XGB_EARLY_STOP,
            seed=fold_seed,
            n_jobs=1,
            verbosity=0,
            **params,
        )
        model.fit(
            X_inner, y_inner_xgb,
            eval_set=[(X_val, y_val_xgb)],
            verbose=False,
        )
        log_h = model.predict(X_val, output_margin=True)
        try:
            c, *_ = concordance_index_censored(y_val["event"], y_val["time"], log_h)
        except Exception:
            c = 0.5

        # Reportar valor para que el pruner pueda actuar en trials futuros.
        trial.report(c, model.best_iteration)
        if trial.should_prune():
            raise optuna.TrialPruned()
        return c

    return objective


# optimize_xgb: ejecuta el estudio Optuna TPE para XGBoost con survival:cox.
# Entradas: conjuntos internos de entrenamiento y validacion (numpy arrays preprocesados),
# y la semilla especifica del fold.
# Salida: tupla (mejores hiperparametros, n_estimators optimo derivado del best_iteration).
# Justificacion: el muestreador TPE con 40 trials ofrece un equilibrio entre la cobertura
# del espacio de hiperparametros y el coste computacional. La semilla por fold garantiza
# que los trials sean reproducibles pero distintos entre folds, evitando sesgos de
# seleccion de hiperparametros hacia las caracteristicas de un fold especifico.
def optimize_xgb(X_inner: np.ndarray, X_val: np.ndarray,
                 y_inner: np.ndarray, y_val: np.ndarray,
                 fold_seed: int) -> tuple[dict, int]:
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=fold_seed),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5),
    )
    study.optimize(
        _make_xgb_objective(X_inner, X_val, y_inner, y_val, fold_seed),
        n_trials=N_TRIALS_XGB,
        show_progress_bar=False,
    )
    # Recuperar n_estimators optimo del mejor trial (best_iteration + 1).
    best_trial = study.best_trial
    # Si el atributo no esta disponible usamos un valor razonable.
    best_n_est = getattr(best_trial, "user_attrs", {}).get("best_iteration", 150)
    return study.best_params, int(best_n_est) + 1


# ---------------------------------------------------------------------------
# Un fold
# ---------------------------------------------------------------------------

# run_fold: ejecuta el ciclo completo de un fold de la validacion cruzada para XGBoost.
# Entradas: DataFrames de train y test del fold, arrays estructurados de supervivencia,
# rejilla global de tiempos, indice del fold y logger.
# Salida: diccionario con C-index, IBS, log-hazards OOF, matriz de supervivencia y
# tiempo maximo observado en entrenamiento.
# Justificacion: el diseno de dos etapas (Optuna interna + reajuste en fold completo)
# separa la busqueda de hiperparametros de la estimacion final del modelo, evitando
# que el conjunto de test externo contamine ninguna decision de modelado.
# El early stopping en el reajuste final usa el mismo hold-out interno del 20% para
# determinar n_estimators; a continuacion el modelo se vuelve a ajustar en el fold
# completo con ese numero de arboles, maximizando el uso de los datos de entrenamiento.
# Nota oncologica: para OS y PFS con censura, el Breslow estimator (ajustado en train)
# convierte los log-hazards del modelo en probabilidades S(t|x) necesarias para el IBS.
def run_fold(X_tr: pd.DataFrame, X_te: pd.DataFrame,
             y_tr: np.ndarray, y_te: np.ndarray,
             global_times: np.ndarray, fold_i: int,
             logger: logging.Logger) -> dict:

    # Preprocesado ajustado SOLO sobre el fold de entrenamiento.
    preprocessor = build_preprocessor()
    X_tr_proc = preprocessor.fit_transform(X_tr)
    X_te_proc = preprocessor.transform(X_te)

    # Split interno para Optuna (20% del fold de entrenamiento).
    sss = StratifiedShuffleSplit(n_splits=1, test_size=0.20,
                                 random_state=SEED + fold_i)
    inner_tr_idx, inner_val_idx = next(
        sss.split(X_tr_proc, y_tr["event"].astype(int))
    )

    best_params, _ = optimize_xgb(
        X_tr_proc[inner_tr_idx], X_tr_proc[inner_val_idx],
        y_tr[inner_tr_idx],      y_tr[inner_val_idx],
        fold_seed=SEED + fold_i,
    )
    logger.info("    Fold %d best_params: %s", fold_i + 1, best_params)

    # Modelo final: early stopping sobre hold-out del 20% del fold de entrenamiento.
    # El hold-out SOLO controla n_estimators; el outer test nunca se usa aqui.
    y_tr_xgb      = _xgb_labels(y_tr)                   # etiquetas del fold completo para reajuste final
    y_inner_xgb   = _xgb_labels(y_tr[inner_tr_idx])     # etiquetas del subconjunto interno de entrenamiento
    y_holdout_xgb = _xgb_labels(y_tr[inner_val_idx])    # etiquetas del hold-out para early stopping

    final_model = xgb.XGBRegressor(
        objective="survival:cox",
        eval_metric="cox-nloglik",
        n_estimators=XGB_MAX_TREES,          # techo de arboles; early stopping lo reducira
        early_stopping_rounds=XGB_EARLY_STOP, # detiene si cox-nloglik no mejora en 25 rondas
        seed=SEED,                            # semilla global para reproducibilidad del reajuste
        n_jobs=-1,
        verbosity=0,
        **best_params,
    )
    final_model.fit(
        X_tr_proc[inner_tr_idx], y_inner_xgb,
        eval_set=[(X_tr_proc[inner_val_idx], y_holdout_xgb)],
        verbose=False,
    )
    best_n_trees = final_model.best_iteration + 1  # n_estimators optimo determinado por early stopping
    logger.info("    Fold %d n_trees_optimo=%d", fold_i + 1, best_n_trees)

    # Reajustar el modelo en el fold COMPLETO con el n_estimators optimo.
    final_model2 = xgb.XGBRegressor(
        objective="survival:cox",
        n_estimators=best_n_trees,
        seed=SEED,
        n_jobs=-1,
        verbosity=0,
        **best_params,
    )
    final_model2.fit(X_tr_proc, y_tr_xgb, verbose=False)

    # Predicciones en el fold de test.
    log_h_te  = final_model2.predict(X_te_proc, output_margin=True)
    log_h_tr  = final_model2.predict(X_tr_proc, output_margin=True)

    try:
        c_index, *_ = concordance_index_censored(y_te["event"], y_te["time"], log_h_te)
        c_index = float(c_index)
    except Exception:
        c_index = float("nan")

    # Breslow ajustado sobre el fold de entrenamiento completo: garantiza que H0(t)
    # se estime sin ver los datos del fold de test, cumpliendo la regla anti-fuga.
    breslow = BreslowEstimator().fit(y_tr, log_h_tr)

    fold_times = safe_fold_times(global_times, y_tr)
    surv_mat   = breslow.surv_matrix(log_h_te, fold_times)
    surv_full  = breslow.surv_matrix(log_h_te, global_times)
    ibs        = safe_ibs(y_tr, y_te, surv_mat, fold_times)

    logger.info("    Fold %d: C-index=%.4f  IBS=%.4f", fold_i + 1, c_index, ibs)
    return {
        "c_index": c_index, "ibs": ibs,
        "risk_scores": log_h_te,
        "surv_full": surv_full,
        "t_max_obs": float(y_tr["time"].max()),
    }


# ---------------------------------------------------------------------------
# Por endpoint
# ---------------------------------------------------------------------------

# run_endpoint: orquesta la validacion cruzada estratificada k=5 y el bootstrap
# para un endpoint concreto (OS o PFS) con XGBoost survival:cox.
# Entradas: DataFrame completo del dataset, nombre del endpoint, columnas de evento
# y tiempo, y logger.
# Salida: diccionario con metricas CV (C-index e IBS por fold, media, std, CV%) y
# estimaciones bootstrap (media, IC95%) listas para serializar a JSON.
# Justificacion: la estratificacion de los folds garantiza proporciones de evento
# homogeneas. Los log-hazards OOF se usan para el bootstrap de C-index y las
# curvas de supervivencia OOF (via Breslow de cada fold) para el bootstrap de IBS.
# El coeficiente de variacion (CV%) entre folds es el tercer criterio de seleccion
# de modelo a priori (estabilidad), que junto con C-index e IBS determina si
# XGBoost supera al Cox baseline en esta cohorte de n=479 sujetos.
def run_endpoint(df: pd.DataFrame, endpoint_name: str,
                 event_col: str, time_col: str,
                 logger: logging.Logger) -> dict:
    logger.info("=== XGBoost | Endpoint %s ===", endpoint_name)

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
        oof_risk[test_idx] = res["risk_scores"]  # agregacion OOF: log-hazard de cada sujeto desde su fold de test
        oof_surv[test_idx] = res["surv_full"]
        t_max_per_fold.append(res["t_max_obs"])

    cv_c = [m["c_index"] for m in fold_metrics]
    cv_i = [m["ibs"]     for m in fold_metrics]
    cv_c_mean, cv_c_std = float(np.nanmean(cv_c)), float(np.nanstd(cv_c, ddof=1))
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
        "model": "XGBoost",
        "endpoint": endpoint_name,
        "n_events":   int(y["event"].sum()),
        "n_censored": int((~y["event"]).sum()),
        "cv": {
            "k": K_FOLDS,
            "c_index": {"per_fold": cv_c, "mean": cv_c_mean, "std": cv_c_std,
                        "cv_pct": round(100 * cv_c_std / cv_c_mean, 2) if cv_c_mean else None},
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
# identificador de modulo. Evita anadir manejadores duplicados si se invoca
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


# main: punto de entrada del script XGBoost. Carga el dataset derivado, ejecuta
# la validacion cruzada con bootstrap para OS y PFS, y serializa los resultados
# en output/xgb_metrics.json.
# Justificacion: la semilla global (np.random.seed) fija el estado del generador
# de numeros aleatorios de NumPy antes de cualquier operacion, garantizando que
# los resultados sean identicos en distintas ejecuciones del script completo.
def main() -> int:
    logger = setup_logger("xgb_model")
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

    out_path = OUTPUT_DIR / "xgb_metrics.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    logger.info("Guardado: %s", out_path.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
