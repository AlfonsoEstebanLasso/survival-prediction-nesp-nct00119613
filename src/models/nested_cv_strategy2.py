"""
src/models/nested_cv_strategy2.py

Proposito:
    Experimento de la Estrategia 2 (analisis ampliado y exploratorio): validacion
    cruzada ANIDADA con seleccion de caracteristicas e hiperparametros en el bucle
    INTERNO y estimacion de rendimiento sin sesgo en el bucle EXTERNO. Protocolo
    pre-registrado en docs/decision_log.md ("Pre-registro del protocolo de la
    Estrategia 2"). Es ADICIONAL al primario: no toca su dataset, sus hashes ni KPI-1.

Entradas:
    output/dataset_strategy2.parquet      (pool de 10 variables; etl_strategy2.py)
    output/nesp_nct00119613_dataset.csv   (solo para el baseline de 7 variables S1)

Salidas:
    output/strategy2_nested_metrics[<tag>].json   metricas anidadas por modelo y endpoint

Diseno (resumen):
    - Bucle externo: StratifiedKFold k=5 sobre estrato evento x TXG (igual que el primario).
      Produce predicciones out-of-fold y bootstrap n=1000 para IC95%.
    - Bucle interno: StratifiedKFold k=5 dentro de cada train externo. Optuna TPE
      optimiza los hiperparametros (y, por tanto, la seleccion embebida) de cada modelo.
      El preprocesado se ajusta SOLO en cada train interno (cacheado por fold interno) y,
      en el reentrenamiento, SOLO en el train externo. El test externo no interviene nunca.
    - Modelos: Cox elastic-net (CoxnetSurvivalAnalysis; seleccion embebida por L1),
      Random Survival Forest (submuestreo de variables max_features) y XGBoost
      survival:cox (submuestreo de columnas colsample_bytree y early stopping interno).
    - Baseline: Cox proporcional sin penalizar sobre las 7 variables de la Estrategia 1,
      corrido bajo EL MISMO protocolo anidado (sin tuning). Su C-index NO es el 0.599 de
      la CV simple del primario; es la referencia justa para juzgar la mejora.
    - Criterio a priori: C-index (principal) + IBS + estabilidad entre folds (CV%).

Control anti-leakage:
    Imputacion, log1p de B_SEREPO, escalado y codificacion se ajustan solo en el train
    (interno o externo segun la fase). La seleccion de variables y el tuning viven en el
    bucle interno. La rejilla IBS se recorta al rango del train (IPCW de Kaplan-Meier).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings
from pathlib import Path

import numpy as np
import optuna
import pandas as pd
import xgboost as xgb
from sklearn.inspection import permutation_importance
from sklearn.model_selection import StratifiedKFold, StratifiedShuffleSplit
from sksurv.ensemble import RandomSurvivalForest
from sksurv.linear_model import CoxnetSurvivalAnalysis, CoxPHSurvivalAnalysis
from sksurv.metrics import concordance_index_censored

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.cv_utils import (
    ENDPOINTS, N_BOOTSTRAP, SEED,
    bootstrap_cindex, bootstrap_ibs, ci95,
    event_time_grid, make_strata, make_y, safe_fold_times, safe_ibs,
)
from src.models.xgb_model import BreslowEstimator, _xgb_labels
from src.preprocessing.build_preprocessor import (
    CATEGORICAL_FEATURES as S1_CAT,
    NUMERIC_FEATURES as S1_NUM,
    build_preprocessor,
)
from src.preprocessing.build_preprocessor_strategy2 import (
    CATEGORICAL_FEATURES as S2_CAT,
    NUMERIC_FEATURES as S2_NUM,
    build_preprocessor_strategy2,
)

optuna.logging.set_verbosity(optuna.logging.WARNING)
warnings.filterwarnings("ignore")

S1_FEATURES = S1_NUM + S1_CAT
S2_FEATURES = S2_NUM + S2_CAT

S2_DATASET = PROJECT_ROOT / "output" / "dataset_strategy2.parquet"
S1_DATASET = PROJECT_ROOT / "output" / "nesp_nct00119613_dataset.csv"
OUTPUT_DIR = PROJECT_ROOT / "output"

XGB_MAX_TREES = 500
XGB_EARLY_STOP = 25

# Modelos que usan el pool de la Estrategia 2 (los demas, el baseline S1).
S2_MODELS = ("coxnet", "rsf", "xgb")


# ---------------------------------------------------------------------------
# Espacios de busqueda (Optuna)
# ---------------------------------------------------------------------------

# Numero maximo de columnas del pool de la Estrategia 2 tras one-hot (6 numericas mas
# 4 binarias drop-first = 10). top_k (variables retenidas tras la poda por importancia)
# se busca en [4, MAX_FEATURES] dentro del bucle interno.
MAX_FEATURES = 10


# Sugiere el diccionario de hiperparametros del modelo indicado para un trial Optuna.
# Cox elastic-net: l1_ratio (mezcla L1/L2) y alpha (fuerza de penalizacion); el L1
# realiza la seleccion embebida (no usa top_k). RSF y XGBoost: hiperparametros del
# modelo mas top_k, el numero de variables que se retienen tras la poda por importancia
# (permutacion en RSF, ganancia en XGBoost) ejecutada dentro del bucle interno.
def suggest_params(model_key: str, trial: optuna.Trial) -> dict:
    if model_key == "coxnet":
        return {
            "l1_ratio": trial.suggest_float("l1_ratio", 0.1, 1.0),
            "alpha": trial.suggest_float("alpha", 1e-3, 1.0, log=True),
        }
    if model_key == "rsf":
        return {
            "n_estimators": trial.suggest_int("n_estimators", 100, 300, step=50),
            "max_depth": trial.suggest_int("max_depth", 2, 12),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 3, 30),
            "min_samples_split": trial.suggest_int("min_samples_split", 5, 40),
            "max_features": trial.suggest_categorical("max_features", ["sqrt", "log2", 0.5, 1.0]),
            "top_k": trial.suggest_int("top_k", 4, MAX_FEATURES),
        }
    if model_key == "xgb":
        return {
            "max_depth": trial.suggest_int("max_depth", 2, 5),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
            "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 0.5, 3.0),
            "top_k": trial.suggest_int("top_k", 4, MAX_FEATURES),
        }
    raise ValueError(f"Modelo desconocido: {model_key}")


# ---------------------------------------------------------------------------
# Ajuste, riesgo y supervivencia por modelo
# ---------------------------------------------------------------------------

# Ajusta un Cox elastic-net con un unico par (alpha, l1_ratio) sobre datos ya
# preprocesados y estandarizados. fit_baseline_model=True habilita la funcion de
# supervivencia para el IBS. Devuelve el modelo ajustado o None si no converge.
def _fit_coxnet(X_tr, y_tr, params, seed):
    model = CoxnetSurvivalAnalysis(
        l1_ratio=params["l1_ratio"],
        alphas=[params["alpha"]],
        fit_baseline_model=True,
        normalize=False,
        max_iter=100000,
    )
    model.fit(X_tr, y_tr)
    return model


# Ajusta un Random Survival Forest con los hiperparametros del trial.
def _fit_rsf(X_tr, y_tr, params, seed):
    model = RandomSurvivalForest(random_state=seed, n_jobs=-1, **params)
    model.fit(X_tr, y_tr)
    return model


# Ajusta un XGBoost survival:cox. Si se pasa eval_set, usa early stopping nativo
# (el numero de arboles lo determina la validacion interna); en caso contrario,
# entrena con el n_estimators indicado en params.
def _fit_xgb(X_tr, y_tr, params, seed, eval_set=None, n_estimators=None):
    kwargs = dict(
        objective="survival:cox", eval_metric="cox-nloglik",
        importance_type="gain",  # feature_importances_ por ganancia para la poda embebida
        seed=seed, n_jobs=-1, verbosity=0,
    )
    if eval_set is not None:
        model = xgb.XGBRegressor(
            n_estimators=XGB_MAX_TREES, early_stopping_rounds=XGB_EARLY_STOP,
            **kwargs, **params,
        )
        Xv, yv = eval_set
        model.fit(X_tr, _xgb_labels(y_tr), eval_set=[(Xv, _xgb_labels(yv))], verbose=False)
    else:
        model = xgb.XGBRegressor(n_estimators=n_estimators, **kwargs, **params)
        model.fit(X_tr, _xgb_labels(y_tr), verbose=False)
    return model


# Devuelve el vector de riesgo (mayor = mayor riesgo) del modelo sobre X ya preprocesado.
# Para XGBoost el riesgo es el log-hazard (output_margin=True).
def _risk(model_key, model, X):
    if model_key == "xgb":
        return model.predict(X, output_margin=True)
    return model.predict(X)


# Construye la matriz de supervivencia S(t|x) sobre la rejilla 'times'.
# Cox/Coxnet/RSF exponen predict_survival_function; XGBoost usa el estimador de
# Breslow ajustado sobre el train (anti-fuga) a partir de los log-hazards de train.
def _surv_matrix(model_key, model, X, times, y_tr=None, X_tr=None):
    if model_key == "xgb":
        log_h_tr = model.predict(X_tr, output_margin=True)
        breslow = BreslowEstimator().fit(y_tr, log_h_tr)
        log_h = model.predict(X, output_margin=True)
        return breslow.surv_matrix(log_h, times)
    fns = model.predict_survival_function(X)
    return np.vstack([fn(times) for fn in fns])


# Separa los hiperparametros del modelo de top_k (que controla la poda, no el modelo).
def _model_hp(params: dict) -> dict:
    return {k: v for k, v in params.items() if k != "top_k"}


# Importancia por permutacion de un RSF sobre (X, y): mide la caida del C-index al
# permutar cada columna. Se calcula sobre el train del fold (in-sample) y solo se usa
# para ordenar variables, no para estimar rendimiento. n_repeats moderado por coste.
def _perm_importance_rsf(model, X, y, seed, n_repeats=5):
    r = permutation_importance(model, X, y, n_repeats=n_repeats,
                               random_state=seed, n_jobs=1)
    return r.importances_mean


# Devuelve los indices de las top_k columnas por importancia (orden estable ascendente).
# Si importances es None (Cox), devuelve todas las columnas.
def _top_k_idx(importances, top_k, n_cols):
    if importances is None:
        return np.arange(n_cols)
    k = min(int(top_k), n_cols)
    order = np.argsort(importances)[::-1][:k]
    return np.sort(order)


# Ajuste unificado para el bucle INTERNO con seleccion embebida por importancia.
# Devuelve (modelo, indices_seleccionados) o (None, None) si el ajuste falla.
# - Cox elastic-net: seleccion por penalizacion L1; usa todas las columnas (top_k no aplica).
# - RSF: ajuste con todas las columnas, importancia por permutacion, poda a top_k y reajuste.
# - XGBoost: ajuste con early stopping en el fold interno, importancia por ganancia,
#   poda a top_k y reajuste con early stopping sobre las columnas seleccionadas.
def _fit_inner(model_key, X_tr, y_tr, X_val, y_val, params, seed):
    try:
        if model_key == "coxnet":
            m = _fit_coxnet(X_tr, y_tr, params, seed)
            return m, np.arange(X_tr.shape[1])
        hp = _model_hp(params)
        if model_key == "rsf":
            full = _fit_rsf(X_tr, y_tr, hp, seed)
            imp = _perm_importance_rsf(full, X_tr, y_tr, seed)
            sel = _top_k_idx(imp, params["top_k"], X_tr.shape[1])
            m = _fit_rsf(X_tr[:, sel], y_tr, hp, seed)
            return m, sel
        if model_key == "xgb":
            full = _fit_xgb(X_tr, y_tr, hp, seed, eval_set=(X_val, y_val))
            sel = _top_k_idx(full.feature_importances_, params["top_k"], X_tr.shape[1])
            m = _fit_xgb(X_tr[:, sel], y_tr, hp, seed, eval_set=(X_val[:, sel], y_val))
            return m, sel
    except Exception:
        return None, None
    raise ValueError(f"Modelo desconocido: {model_key}")


# ---------------------------------------------------------------------------
# Seleccion de modelo, dataset y preprocesador
# ---------------------------------------------------------------------------

# Devuelve (DataFrame de features, fabrica de preprocesador) segun el modelo:
# el baseline usa las 7 variables de la Estrategia 1 y su preprocesador; los modelos
# de la Estrategia 2 usan el pool de 10 y el preprocesador con log1p de B_SEREPO.
def model_inputs(model_key, X_s1, X_s2):
    if model_key == "baseline":
        return X_s1, build_preprocessor
    return X_s2, build_preprocessor_strategy2


# ---------------------------------------------------------------------------
# Bucle interno: Optuna sobre folds internos cacheados
# ---------------------------------------------------------------------------

# Optimiza los hiperparametros de un modelo en el bucle interno de un fold externo.
# Pre-cachea el preprocesado de cada fold interno (ajustado SOLO en su train interno)
# para no reajustarlo en cada trial. El objetivo es el C-index medio sobre los folds
# internos. Devuelve los mejores hiperparametros encontrados por Optuna TPE.
def inner_optimize(model_key, X_tr_outer, y_tr_outer, strata_tr, build_prep,
                   n_trials, inner_k, fold_seed, logger):
    inner_cv = StratifiedKFold(n_splits=inner_k, shuffle=True, random_state=fold_seed)
    cached = []
    for in_tr, in_val in inner_cv.split(X_tr_outer, strata_tr):
        prep = build_prep()
        Xt = prep.fit_transform(X_tr_outer.iloc[in_tr])   # ajuste SOLO en train interno (anti-fuga)
        Xv = prep.transform(X_tr_outer.iloc[in_val])
        cached.append((Xt, y_tr_outer[in_tr], Xv, y_tr_outer[in_val]))

    def objective(trial: optuna.Trial) -> float:
        params = suggest_params(model_key, trial)
        scores = []
        for Xt, yt, Xv, yv in cached:
            model, sel = _fit_inner(model_key, Xt, yt, Xv, yv, params, fold_seed)
            if model is None:
                scores.append(0.5)
                continue
            try:
                risk = _risk(model_key, model, Xv[:, sel])
                c, *_ = concordance_index_censored(yv["event"], yv["time"], risk)
            except Exception:
                c = 0.5
            scores.append(float(c))
        return float(np.mean(scores))

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=fold_seed),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5),
    )
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    return study.best_params


# ---------------------------------------------------------------------------
# Reentrenamiento externo y prediccion sobre el test externo
# ---------------------------------------------------------------------------

# Reentrena el modelo con los mejores hiperparametros sobre el train externo COMPLETO
# (preprocesador ajustado solo ahi) y predice riesgo y supervivencia sobre el test externo.
# Para XGBoost, el numero de arboles se fija por early stopping en un hold-out del 20%
# del train externo y luego se reentrena en el train externo completo. Devuelve riesgo,
# matriz de supervivencia en global_times, t_max del train y, para coxnet, n de variables.
def outer_fit_predict(model_key, X_tr_outer, y_tr_outer, X_te_outer, y_te_outer,
                      strata_tr, build_prep, best_params, global_times, fold_seed):
    prep = build_prep()
    X_tr = prep.fit_transform(X_tr_outer)   # ajuste SOLO en train externo
    X_te = prep.transform(X_te_outer)
    feat_names = list(prep.named_steps["column_transformer"].get_feature_names_out())

    extra = {}
    sel = np.arange(X_tr.shape[1])
    hp = _model_hp(best_params) if best_params else {}

    if model_key == "baseline":
        model = CoxPHSurvivalAnalysis(alpha=0, ties="efron", n_iter=100)
        model.fit(X_tr, y_tr_outer)
    elif model_key == "coxnet":
        # Seleccion embebida por L1: las variables retenidas son las de coeficiente no nulo.
        model = _fit_coxnet(X_tr, y_tr_outer, best_params, fold_seed)
        nz = model.coef_[:, 0] != 0
        extra["n_selected"] = int(np.sum(nz))
        extra["selected_features"] = [feat_names[i] for i in np.where(nz)[0]]
    elif model_key == "rsf":
        # Poda por importancia de permutacion y reajuste sobre las top_k variables.
        full = _fit_rsf(X_tr, y_tr_outer, hp, fold_seed)
        imp = _perm_importance_rsf(full, X_tr, y_tr_outer, fold_seed)
        sel = _top_k_idx(imp, best_params["top_k"], X_tr.shape[1])
        model = _fit_rsf(X_tr[:, sel], y_tr_outer, hp, fold_seed)
        extra["n_selected"] = int(len(sel))
        extra["selected_features"] = [feat_names[i] for i in sel]
    elif model_key == "xgb":
        # Poda por importancia de ganancia: ranking con un ajuste breve y reajuste final
        # sobre las top_k. El numero de arboles se fija por early stopping en un hold-out
        # del 20% del train externo (sobre las columnas seleccionadas).
        ranker = _fit_xgb(X_tr, y_tr_outer, hp, fold_seed, n_estimators=200)
        sel = _top_k_idx(ranker.feature_importances_, best_params["top_k"], X_tr.shape[1])
        sss = StratifiedShuffleSplit(n_splits=1, test_size=0.20, random_state=fold_seed)
        h_tr, h_val = next(sss.split(X_tr, y_tr_outer["event"].astype(int)))
        es_model = _fit_xgb(X_tr[h_tr][:, sel], y_tr_outer[h_tr], hp, fold_seed,
                            eval_set=(X_tr[h_val][:, sel], y_tr_outer[h_val]))
        n_trees = es_model.best_iteration + 1
        model = _fit_xgb(X_tr[:, sel], y_tr_outer, hp, fold_seed, n_estimators=n_trees)
        extra["n_trees"] = int(n_trees)
        extra["n_selected"] = int(len(sel))
        extra["selected_features"] = [feat_names[i] for i in sel]
    else:
        raise ValueError(f"Modelo desconocido: {model_key}")

    # Riesgo y supervivencia sobre las columnas seleccionadas. _risk y _surv_matrix
    # distinguen XGBoost (log-hazard + Breslow) del resto (predict / predict_survival_function).
    X_te_sel, X_tr_sel = X_te[:, sel], X_tr[:, sel]
    risk = _risk(model_key, model, X_te_sel)
    surv_full = _surv_matrix(model_key, model, X_te_sel, global_times,
                             y_tr=y_tr_outer, X_tr=X_tr_sel)
    extra["risk"] = risk
    extra["surv_full"] = surv_full
    extra["t_max_obs"] = float(y_tr_outer["time"].max())
    return extra


# ---------------------------------------------------------------------------
# Un modelo, un endpoint: validacion cruzada anidada completa
# ---------------------------------------------------------------------------

# Ejecuta la CV anidada de un modelo para un endpoint: bucle externo k=5, bucle
# interno con Optuna (salvo el baseline, sin tuning), agregacion OOF, CV% y bootstrap.
# Devuelve un diccionario de metricas listo para serializar.
def run_model_endpoint(model_key, X_s1, X_s2, y, strata, global_times,
                       outer_k, n_trials, inner_k, n_boot, logger):
    X, build_prep = model_inputs(model_key, X_s1, X_s2)
    outer_cv = StratifiedKFold(n_splits=outer_k, shuffle=True, random_state=SEED)

    fold_metrics = []
    oof_risk = np.empty(len(X))
    oof_surv = np.zeros((len(X), len(global_times)))
    t_max_per_fold = []
    sel_info = []

    for fold_i, (tr_idx, te_idx) in enumerate(outer_cv.split(X, strata)):
        X_tr_o, X_te_o = X.iloc[tr_idx], X.iloc[te_idx]
        y_tr_o, y_te_o = y[tr_idx], y[te_idx]
        strata_tr = strata[tr_idx]
        fold_seed = SEED + fold_i

        if model_key == "baseline":
            best_params = {}
        else:
            best_params = inner_optimize(
                model_key, X_tr_o, y_tr_o, strata_tr, build_prep,
                n_trials, inner_k, fold_seed, logger,
            )

        out = outer_fit_predict(
            model_key, X_tr_o, y_tr_o, X_te_o, y_te_o,
            strata_tr, build_prep, best_params, global_times, fold_seed,
        )

        risk = out["risk"]
        try:
            c_index, *_ = concordance_index_censored(y_te_o["event"], y_te_o["time"], risk)
            c_index = float(c_index)
        except Exception:
            c_index = float("nan")

        fold_times = safe_fold_times(global_times, y_tr_o)
        surv_fold = out["surv_full"][:, global_times < y_tr_o["time"].max()]
        ibs = safe_ibs(y_tr_o, y_te_o, surv_fold, fold_times)

        oof_risk[te_idx] = risk
        oof_surv[te_idx] = out["surv_full"]
        t_max_per_fold.append(out["t_max_obs"])
        info = {k: out[k] for k in ("n_selected", "n_trees", "selected_features") if k in out}
        info.update({"fold": fold_i + 1, "best_params": best_params})
        sel_info.append(info)
        fold_metrics.append({"fold": fold_i + 1, "c_index": c_index, "ibs": ibs})
        logger.info("  [%s] fold %d/%d: C-index=%.4f  IBS=%.4f",
                    model_key, fold_i + 1, outer_k, c_index, ibs)

    cv_c = [m["c_index"] for m in fold_metrics]
    cv_i = [m["ibs"] for m in fold_metrics]
    cv_c_mean, cv_c_std = float(np.nanmean(cv_c)), float(np.nanstd(cv_c, ddof=1))
    cv_i_mean, cv_i_std = float(np.nanmean(cv_i)), float(np.nanstd(cv_i, ddof=1))

    # Bootstrap OOF (rejilla recortada al t_max comun de todos los folds).
    t_max_common = min(t_max_per_fold)
    boot_mask = global_times < t_max_common
    boot_times = global_times[boot_mask]
    boot_surv = oof_surv[:, boot_mask]
    boot_c = bootstrap_cindex(y, oof_risk, n=n_boot, seed=SEED)
    boot_i = bootstrap_ibs(y, boot_surv, boot_times, n=n_boot, seed=SEED)
    bc, bi = ci95(boot_c), ci95(boot_i)

    logger.info("[%s] CV C-index=%.4f +/- %.4f (CV%%=%.2f)  Boot C=%.4f IC[%.4f, %.4f]",
                model_key, cv_c_mean, cv_c_std,
                100 * cv_c_std / cv_c_mean if cv_c_mean else 0,
                bc["mean"], bc["ci_low"], bc["ci_high"])

    return {
        "model": model_key,
        "cv": {
            "c_index": {"per_fold": cv_c, "mean": cv_c_mean, "std": cv_c_std,
                        "cv_pct": round(100 * cv_c_std / cv_c_mean, 2) if cv_c_mean else None},
            "ibs": {"per_fold": cv_i, "mean": cv_i_mean, "std": cv_i_std,
                    "cv_pct": round(100 * cv_i_std / cv_i_mean, 2) if cv_i_mean else None},
        },
        "bootstrap": {"n": n_boot, "c_index": bc, "ibs": bi},
        "fold_detail": fold_metrics,
        "selection": sel_info,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def setup_logger() -> logging.Logger:
    logger = logging.getLogger("nested_cv_strategy2")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s", "%H:%M:%S"))
        logger.addHandler(sh)
    return logger


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CV anidada de la Estrategia 2 (NESP NCT00119613).")
    p.add_argument("--trials", type=int, default=100, help="Trials de Optuna por modelo y fold externo.")
    p.add_argument("--inner-k", type=int, default=5, help="Folds del bucle interno.")
    p.add_argument("--outer-k", type=int, default=5, help="Folds del bucle externo.")
    p.add_argument("--bootstrap", type=int, default=N_BOOTSTRAP, help="Remuestras bootstrap OOF.")
    p.add_argument("--endpoints", default="OS,PFS", help="Endpoints separados por coma (OS,PFS).")
    p.add_argument("--models", default="baseline,coxnet,rsf,xgb",
                   help="Modelos separados por coma (baseline,coxnet,rsf,xgb).")
    p.add_argument("--tag", default="", help="Sufijo del fichero de salida (p.ej. _validacion).")
    p.add_argument("--save", dest="save", action="store_true", default=True,
                   help="Guardar el JSON de metricas (por defecto si).")
    p.add_argument("--no-save", dest="save", action="store_false",
                   help="No guardar el JSON (pasadas de validacion no reportadas).")
    return p.parse_args()


# Punto de entrada. Carga ambos datasets alineados por SUBJID (S2 para los modelos
# del pool ampliado, S1 para el baseline), comparte los mismos folds externos y ejecuta
# la CV anidada de cada modelo y endpoint. Reporta el delta de C-index frente al baseline.
def main() -> int:
    args = parse_args()
    logger = setup_logger()
    np.random.seed(SEED)

    if not S2_DATASET.exists():
        logger.error("No existe %s. Ejecuta primero src/data/etl_strategy2.py.", S2_DATASET)
        return 1
    if not S1_DATASET.exists():
        logger.error("No existe %s (necesario para el baseline). Ejecuta el ETL primario.", S1_DATASET)
        return 1

    # SUBJID se lee como texto en ambos para preservar el formato con ceros a la
    # izquierda (p.ej. '000001'); read_csv lo inferiria como entero y romperia la union.
    df_s2 = pd.read_parquet(S2_DATASET)
    df_s2["SUBJID"] = df_s2["SUBJID"].astype(str)
    df_s2 = df_s2.sort_values("SUBJID").reset_index(drop=True)
    df_s1 = pd.read_csv(S1_DATASET, dtype={"SUBJID": str})
    df_s1 = df_s1.set_index("SUBJID").reindex(df_s2["SUBJID"]).reset_index()
    n_unmatched = int(df_s1[S1_FEATURES].isna().all(axis=1).sum())
    if n_unmatched > 0:
        logger.error("%d sujetos S1 no se alinearon con S2 por SUBJID. Revisa los datasets.", n_unmatched)
        return 1
    logger.info("Datasets alineados: S2 %d filas, S1 %d filas.", len(df_s2), len(df_s1))

    endpoints = [e.strip() for e in args.endpoints.split(",") if e.strip()]
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    logger.info("Endpoints=%s  Modelos=%s  trials=%d inner_k=%d outer_k=%d boot=%d",
                endpoints, models, args.trials, args.inner_k, args.outer_k, args.bootstrap)

    X_s1 = df_s1[S1_FEATURES].copy()
    X_s2 = df_s2[S2_FEATURES].copy()

    results: dict = {"config": {
        "trials": args.trials, "inner_k": args.inner_k, "outer_k": args.outer_k,
        "bootstrap": args.bootstrap, "endpoints": endpoints, "models": models,
        "s1_features": S1_FEATURES, "s2_features": S2_FEATURES,
    }}

    for ep in endpoints:
        cfg = ENDPOINTS[ep]
        y = make_y(df_s2[cfg["event"]].values, df_s2[cfg["time"]].values)
        strata = make_strata(df_s2, cfg["event"])
        global_times = event_time_grid(y)
        logger.info("=== Endpoint %s (eventos=%d) ===", ep, int(y["event"].sum()))

        results[ep] = {}
        for model_key in models:
            results[ep][model_key] = run_model_endpoint(
                model_key, X_s1, X_s2, y, strata, global_times,
                args.outer_k, args.trials, args.inner_k, args.bootstrap, logger,
            )

        # Resumen comparativo frente al baseline (mismo protocolo anidado).
        if "baseline" in results[ep]:
            base_c = results[ep]["baseline"]["bootstrap"]["c_index"]["mean"]
            logger.info("--- %s: C-index anidado (Boot) vs baseline %.4f ---", ep, base_c)
            for model_key in models:
                mc = results[ep][model_key]["bootstrap"]["c_index"]["mean"]
                logger.info("    %-9s C=%.4f  delta=%+.4f", model_key, mc, mc - base_c)

    if args.save:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / f"strategy2_nested_metrics{args.tag}.json"
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=2, default=str)
        logger.info("Guardado: %s", out_path.name)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
