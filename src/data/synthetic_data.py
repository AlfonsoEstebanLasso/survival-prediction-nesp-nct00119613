"""
src/data/synthetic_data.py

Proposito:
    Generacion de datos sinteticos tabulares con CTGAN (SDV), evaluacion de utilidad
    mediante TSTR (Train on Synthetic, Test on Real) sobre el modelo final Cox PH para OS,
    y evaluacion del riesgo de reidentificacion en tres dimensiones: membership inference
    con shadow models, unicidad de cuasi-identificadores (k-anonimidad) y distancia al
    registro mas cercano (DCR).

ADVERTENCIA: Los datos sinteticos son exclusivamente para prototipado metodologico.
    No refuerzan las conclusiones del modelo principal de supervivencia, no representan
    pacientes reales y no deben utilizarse con fines clinicos ni para extraer conclusiones
    epidemiologicas. El generador se ajusta sobre n=479 sujetos de un ensayo clinico
    especifico; su capacidad de generalizacion es limitada.

Entradas:
    output/nesp_nct00119613_dataset.csv
    output/cox_baseline_cv_detail.csv   (opcional, para TRTR por fold)

Salidas (en output/):
    synthetic_dataset.csv           Dataset sintetico (excluido del control de versiones)
    synthetic_metrics.json          Metricas de utilidad y riesgo de privacidad
    synthetic_tstr_comparison.csv   Comparativa TRTR vs TSTR por fold (OS)
    fig_synthetic_tstr.png          Grafico de barras TRTR vs TSTR
    fig_synthetic_membership.png    Curva ROC del ataque de membership inference
    fig_synthetic_dcr.png           Distribucion de DCR y RRDR
    fig_synthetic_kanon.png         Porcentaje de registros por nivel k-anonimidad
"""

from __future__ import annotations

import json
import logging
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import StratifiedKFold
from sksurv.linear_model import CoxPHSurvivalAnalysis
from sksurv.metrics import concordance_index_censored

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.preprocessing.build_preprocessor import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    build_preprocessor,
)

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

SEED              = 42
N_SYNTHETIC       = 479        # igual al tamano real para comparabilidad
MAIN_EPOCHS       = 300        # epocas del sintetizador principal
SHADOW_EPOCHS     = 100        # epocas de cada shadow model (balance velocidad/calidad)
N_SHADOW          = 5          # numero de shadow models para membership inference
SHADOW_TRAIN_FRAC = 0.70       # fraccion de datos reales usada como "miembros" en cada shadow
K_FOLDS           = 5          # folds del CV para TSTR

FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
ALL_COLS = FEATURES + ["DTH", "DTHDY", "PFSCD", "PFSDY", "TXG", "EVALPRIM", "EVALQOL"]
AGE_BIN_STEP = 5               # anchura de los bins de edad para quasi-identificadores

# Valores de referencia TRTR (del Decision Log, valores reales del pipeline)
TRTR_CINDEX_MEAN = 0.600
TRTR_CINDEX_STD  = 0.042

DATASET_PATH   = PROJECT_ROOT / "output" / "nesp_nct00119613_dataset.csv"
CV_DETAIL_PATH = PROJECT_ROOT / "output" / "cox_baseline_cv_detail.csv"
OUTPUT_DIR     = PROJECT_ROOT / "output"

# Colores corporativos (style_guide.md)
C_DARK  = "#1F4E79"
C_LIGHT = "#D5E8F0"
C_AMBER = "#B7791F"
C_GREEN = "#1F7A3A"
C_GRAY  = "#888888"

# Criterios de aceptacion a priori (privacidad)
ACCEPT: dict[str, float] = {
    "mi_auc_max":            0.60,  # AUC del ataque MI: <= 0.60 aceptable
    "mi_tpr_fpr01_max":      0.20,  # TPR a FPR=0.1: <= 0.20 aceptable
    "kanon_k1_max":          0.05,  # <= 5 % de registros sinteticos unicos (k=1)
    "kanon_k2_max":          0.10,  # <= 10 % con k<=2
    "kanon_k5_max":          0.20,  # <= 20 % con k<=5
    "dcr_p5_rrdr_ratio_min": 0.50,  # DCR_p5 / RRDR_mediana >= 0.50
}

DISCLAIMER = (
    "ADVERTENCIA: Los datos sinteticos son exclusivamente para prototipado metodologico. "
    "No refuerzan las conclusiones del modelo principal de supervivencia, "
    "no representan pacientes reales y no deben utilizarse con fines clinicos "
    "ni para extraer conclusiones epidemiologicas."
)


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

# Crea y configura el logger del modulo con formato de hora, nivel y mensaje.
# Salida: objeto Logger listo para uso en todas las funciones del pipeline.
# Garantiza que no se duplican handlers si el modulo se importa multiples veces.
def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("synthetic_data")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(message)s", "%H:%M:%S",
        ))
        logger.addHandler(sh)
    return logger


# ---------------------------------------------------------------------------
# Utilidades comunes
# ---------------------------------------------------------------------------

# Establece los parametros globales de Matplotlib segun la guia de estilo del proyecto.
# Fuente Arial, sin bordes superior y derecho, cuadricula gris suave y tamanos de texto
# coherentes con los entregables del TFG. Sin entrada ni salida de datos.
def _setup_rcparams() -> None:
    plt.rcParams.update({
        "font.family":       "sans-serif",
        "font.sans-serif":   ["Arial", "Liberation Sans", "DejaVu Sans"],
        "axes.spines.top":   False,
        "axes.spines.right": False,
        "axes.grid":         True,
        "grid.color":        "#E0E0E0",
        "grid.linewidth":    0.7,
        "axes.titlesize":    11,
        "axes.labelsize":    10,
        "xtick.labelsize":   9,
        "ytick.labelsize":   9,
        "legend.fontsize":   9,
    })


# Guarda la figura en disco con resolucion de 300 DPI apta para documentos academicos
# y libera la memoria de Matplotlib cerrando la figura tras el guardado.
# Entrada: figura, ruta de destino y DPI opcional. Sin retorno.
def _save_fig(fig: plt.Figure, path: Path, dpi: int = 300) -> None:
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# Convierte vectores separados de evento y tiempo al formato de array estructurado
# que exige scikit-survival: dtype=[("event", bool), ("time", float)].
# Entrada: arrays de indicador de evento (DTH o PFSCD) y tiempo (DTHDY o PFSDY).
# Salida: array estructurado compatible con CoxPHSurvivalAnalysis y concordance_index_censored.
# Nota oncologica: el indicador de evento sigue la convencion 1=muerte/progresion, 0=censura.
def _make_y(event: np.ndarray, time: np.ndarray) -> np.ndarray:
    return np.array(
        [(bool(e), float(t)) for e, t in zip(event, time)],
        dtype=[("event", bool), ("time", float)],
    )


# Instancia el preprocesador (imputacion, estandarizacion, one-hot) y lo ajusta
# exclusivamente sobre las columnas FEATURES del dataframe recibido.
# Principio anti-leakage: el ajuste nunca toca datos de test ni datos reales cuando
# se invoca en el contexto TSTR (donde df es el dataset sintetico).
# Entrada: dataframe con las columnas de FEATURES. Salida: (X_procesado, preprocesador_ajustado).
def _fit_preprocessor(df: pd.DataFrame):
    """Ajusta el preprocesador solo sobre df[FEATURES] y lo devuelve junto con X procesado."""
    preproc = build_preprocessor()
    X = preproc.fit_transform(df[FEATURES].copy())
    return X, preproc


# Fija la semilla de aleatoriedad en NumPy, random de Python y PyTorch (si esta instalado).
# Reproducibilidad: garantiza que CTGAN y los shadow models producen los mismos resultados
# entre ejecuciones, condicion necesaria para el KPI-1 (entorno limpio reproducible).
# Entrada: entero de semilla. Sin retorno.
def _set_global_seeds(seed: int) -> None:
    np.random.seed(seed)
    try:
        import random as _random
        _random.seed(seed)
    except Exception:
        pass
    try:
        import torch
        torch.manual_seed(seed)
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Generacion con CTGAN (SDV >= 1.0)
# ---------------------------------------------------------------------------

# Construye el objeto SingleTableMetadata de SDV para el dataframe dado.
# SDV infiere automaticamente los tipos de columna; esta funcion corrige las columnas
# binarias y categoricas que el detector automatico podria tratar como numericas continuas.
# Nota de implementacion SDV: declarar sdtype="categorical" en columnas binarias (DTH, PFSCD,
# TXG, EVALPRIM, EVALQOL) y ordinales (SEXCD, B_ECOGN) permite a CTGAN aprender correctamente
# sus distribuciones discretas en lugar de modelarlas como Gaussianas.
# Entrada: dataframe completo. Salida: objeto SingleTableMetadata configurado.
def _build_sdv_metadata(df: pd.DataFrame):
    from sdv.metadata import SingleTableMetadata
    meta = SingleTableMetadata()
    meta.detect_from_dataframe(df)
    # Forzar tipo categorico en variables binarias y ordinales para evitar sintesis incorrecta
    for col in ["DTH", "PFSCD", "TXG", "EVALPRIM", "EVALQOL", "SEXCD", "B_ECOGN"]:
        if col in df.columns:
            meta.update_column(col, sdtype="categorical")
    return meta


# Instancia y entrena un CTGANSynthesizer (SDV >= 1.0) sobre el dataframe recibido.
# CTGAN es un GAN condicional para datos tabulares que aprende la distribucion conjunta
# de covariables mixtas (numericas y categoricas).
# El parametro epochs controla el numero de epocas de entrenamiento del generador y el
# discriminador. Para el sintetizador principal se usan MAIN_EPOCHS=300; para los shadow
# models del ataque de membership inference se usan SHADOW_EPOCHS=100 (balance velocidad/calidad).
# seed_offset permite aislar la semilla de cada shadow model del resto del pipeline.
# Entrada: dataframe de entrenamiento, numero de epocas y desplazamiento de semilla.
# Salida: sintetizador ajustado listo para llamar a .sample().
def _train_ctgan(df: pd.DataFrame, epochs: int, seed_offset: int = 0):
    from sdv.single_table import CTGANSynthesizer
    _set_global_seeds(SEED + seed_offset)  # semilla diferenciada por shadow model
    meta = _build_sdv_metadata(df)
    synth = CTGANSynthesizer(meta, epochs=epochs, verbose=False)  # epocas fijadas a priori
    synth.fit(df)
    return synth


# Corrige tipos y recorta rangos del dataset sintetico al espacio plausible del dataset real.
# CTGAN puede generar valores fuera del dominio clinico valido (p.ej., tiempos negativos,
# indicadores de evento fuera de {0,1} o niveles de ECOG no definidos). Esta funcion aplica:
# - Clipping de binarias a {0,1} y de tiempos a valores positivos.
# - Restriccion de MEDHX_N al rango entero [0,6] tal como define el ETL.
# - Clipping de AGE al rango observado en los datos reales.
# - Proyeccion de SEXCD y B_ECOGN a los valores validos del dataset real, usando la moda
#   como valor de reemplazo cuando se genera un nivel inexistente.
# Entrada: dataset sintetico crudo y dataset real de referencia. Salida: dataset corregido.
def _postprocess(df_syn: pd.DataFrame, df_real: pd.DataFrame) -> pd.DataFrame:
    """Corrige tipos y recorta rangos del dataset sintetico al rango plausible del real."""
    df = df_syn.copy()

    for col in ["DTH", "PFSCD", "TXG", "EVALPRIM", "EVALQOL"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int).clip(0, 1)

    for col in ["DTHDY", "PFSDY"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(1).clip(lower=1)

    if "MEDHX_N" in df.columns:
        df["MEDHX_N"] = (
            pd.to_numeric(df["MEDHX_N"], errors="coerce")
            .fillna(0).round().astype(int).clip(0, 6)
        )

    if "AGE" in df.columns and "AGE" in df_real.columns:
        df["AGE"] = pd.to_numeric(df["AGE"], errors="coerce").clip(
            float(df_real["AGE"].min()), float(df_real["AGE"].max())
        )

    for col in ["SEXCD", "B_ECOGN"]:
        if col in df.columns and col in df_real.columns:
            valid_vals = set(df_real[col].dropna().unique())
            mode_val   = df_real[col].mode().iloc[0]
            try:
                df[col] = df[col].apply(
                    lambda x: x if x in valid_vals else mode_val
                )
                df[col] = df[col].astype(df_real[col].dtype)
            except Exception:
                pass

    return df


# Orquesta el entrenamiento del sintetizador CTGAN principal y la generacion de N_SYNTHETIC
# registros sinteticos a partir del dataset real de n=479 sujetos.
# Flujo: seleccion de columnas relevantes (ALL_COLS), entrenamiento con MAIN_EPOCHS=300,
# muestreo y postprocesado para garantizar coherencia de dominio clinico.
# Las filas con NaN en covariables predictoras se eliminan con aviso al logger.
# N_SYNTHETIC = 479 (igual al real) para que las comparaciones de distribucion sean directas.
# Nota de privacidad: los datos sinteticos se destinan UNICAMENTE a prototipado metodologico;
# no representan pacientes reales ni deben usarse con fines clinicos.
# Entrada: dataset real y logger. Salida: dataframe sintetico postprocesado.
def generate_synthetic(df_real: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    """Entrena el sintetizador CTGAN sobre el dataset real y genera N_SYNTHETIC registros."""
    cols   = [c for c in ALL_COLS if c in df_real.columns]
    df_fit = df_real[cols].reset_index(drop=True)

    logger.info("Entrenando CTGAN principal (epocas=%d, n_real=%d)...", MAIN_EPOCHS, len(df_fit))
    synth  = _train_ctgan(df_fit, epochs=MAIN_EPOCHS, seed_offset=0)

    logger.info("Generando %d registros sinteticos...", N_SYNTHETIC)
    df_syn = synth.sample(num_rows=N_SYNTHETIC)
    df_syn = _postprocess(df_syn, df_real)

    n_antes = len(df_syn)
    feats_presentes = [c for c in FEATURES if c in df_syn.columns]
    df_syn = df_syn.dropna(subset=feats_presentes).reset_index(drop=True)
    if len(df_syn) < n_antes:
        logger.warning("Eliminadas %d filas con NaN tras la sintesis.", n_antes - len(df_syn))

    return df_syn


# ---------------------------------------------------------------------------
# TSTR: Train on Synthetic, Test on Real
# ---------------------------------------------------------------------------

# Evalua la utilidad del dataset sintetico mediante la metodologia TSTR
# (Train on Synthetic, Test on Real) con validacion cruzada estratificada k=5 sobre OS.
# Protocolo TSTR puro:
#   1. El preprocesador se ajusta UNICAMENTE sobre los datos sinteticos (sin ver el real),
#      garantizando que no hay fuga de informacion del real al sintetico.
#   2. Cox PH se ajusta sobre todos los datos sinteticos transformados.
#   3. El C-index se calcula en cada fold de test del dataset real, aplicando el preprocesador
#      ya ajustado sobre sinteticos mediante .transform() (nunca .fit_transform()).
# La comparacion TSTR vs TRTR cuantifica cuanta utilidad predictiva conservan los sinteticos
# respecto al modelo entrenado en datos reales (referencia: C-index TRTR = 0.600 +/- 0.042).
# Entrada: dataset real, dataset sintetico y logger. Salida: diccionario con metricas de utilidad.
def evaluate_tstr(
    df_real: pd.DataFrame,
    df_syn: pd.DataFrame,
    logger: logging.Logger,
) -> dict:
    """
    Para cada fold del CV estratificado k=5 sobre los datos reales:
        - Preprocesador ajustado en df_syn (escenario TSTR puro).
        - Cox ajustado en todos los datos sinteticos.
        - C-index evaluado en el fold de test real.
    Compara con TRTR (del Decision Log: CV OS C-index = 0.600 +/- 0.042).
    """
    logger.info("Evaluando TSTR (Cox PH, OS)...")

    # Preprocesado ajustado sobre sinteticos: principio TSTR puro, sin ver datos reales
    n_events_syn = int(pd.to_numeric(df_syn.get("DTH", pd.Series(dtype=float)),
                                     errors="coerce").fillna(0).sum())
    if n_events_syn < 10:
        logger.error("Insuficientes eventos en sinteticos (%d); TSTR no ejecutado.", n_events_syn)
        return {}

    X_syn_proc, preproc_syn = _fit_preprocessor(df_syn)  # preprocesador ajustado solo sobre sinteticos
    y_syn = _make_y(df_syn["DTH"].values, df_syn["DTHDY"].values)

    cox_tstr = CoxPHSurvivalAnalysis(alpha=0, ties="efron", n_iter=100)
    cox_tstr.fit(X_syn_proc, y_syn)

    # Evaluacion fold a fold sobre el real: el preprocesador ya ajustado se aplica con .transform()
    y_real  = _make_y(df_real["DTH"].values, df_real["DTHDY"].values)
    X_real  = df_real[FEATURES].copy()
    strata  = df_real["DTH"].astype(int).values * 2 + df_real["TXG"].astype(int).values  # estratificacion por evento y brazo

    cv = StratifiedKFold(n_splits=K_FOLDS, shuffle=True, random_state=SEED)
    tstr_folds = []
    for fold_i, (_, test_idx) in enumerate(cv.split(X_real, strata)):
        X_te = preproc_syn.transform(X_real.iloc[test_idx])
        y_te = y_real[test_idx]
        try:
            c, *_ = concordance_index_censored(
                y_te["event"], y_te["time"], cox_tstr.predict(X_te)
            )
        except Exception:
            c = float("nan")
        tstr_folds.append({"fold": fold_i + 1, "tstr_cindex": float(c)})
        logger.info("  Fold %d: TSTR C-index = %.4f", fold_i + 1, c)

    # Cargar TRTR por fold desde el CSV de detalle del CV real, si esta disponible
    trtr_by_fold: dict[int, float] = {}
    if CV_DETAIL_PATH.exists():
        try:
            detail = pd.read_csv(CV_DETAIL_PATH)
            os_rows = detail[detail["endpoint"] == "OS"].set_index("fold")["c_index"]
            trtr_by_fold = os_rows.to_dict()
        except Exception:
            pass

    rows = []
    for r in tstr_folds:
        rows.append({
            "fold":         r["fold"],
            "trtr_cindex":  trtr_by_fold.get(r["fold"], TRTR_CINDEX_MEAN),
            "tstr_cindex":  r["tstr_cindex"],
        })
    df_cmp = pd.DataFrame(rows)

    tstr_mean = float(np.nanmean(df_cmp["tstr_cindex"].values))
    tstr_std  = float(np.nanstd(df_cmp["tstr_cindex"].values, ddof=1))
    ratio     = tstr_mean / TRTR_CINDEX_MEAN if TRTR_CINDEX_MEAN > 0 else float("nan")

    logger.info(
        "TSTR C-index: %.4f +/- %.4f  |  TRTR: %.4f  |  Ratio: %.4f",
        tstr_mean, tstr_std, TRTR_CINDEX_MEAN, ratio,
    )

    return {
        "tstr_mean":     tstr_mean,
        "tstr_std":      tstr_std,
        "trtr_mean":     TRTR_CINDEX_MEAN,
        "trtr_std":      TRTR_CINDEX_STD,
        "utility_ratio": ratio,
        "per_fold_df":   df_cmp,
    }


# ---------------------------------------------------------------------------
# Membership Inference (Shadow Models)
# ---------------------------------------------------------------------------

# Evalua el riesgo de membership inference mediante N_SHADOW shadow models de CTGAN.
# El ataque de membership inference trata de determinar si un registro concreto formaba
# parte del conjunto de entrenamiento del generador. Este es uno de los ataques de privacidad
# mas relevantes en sintetizadores de datos clinicos (Shokri et al., 2017).
# Protocolo de shadow models:
#   - Cada shadow se entrena sobre SHADOW_TRAIN_FRAC (70%) del dataset real (subconjunto aleatorio).
#   - El registro pertenece a la clase "miembro" si fue incluido en ese subconjunto de entrenamiento.
#   - Score de ataque: negativo de la distancia minima del registro real al dataset sintetico
#     del shadow (menor distancia => mayor probabilidad de haber sido "miembro").
#   - Se acumulan pares (score, etiqueta) de todos los shadows y se calcula AUC y TPR@FPR=0.1.
# Criterios a priori fijados: AUC <= 0.60, TPR@FPR=0.1 <= 0.20.
# Un AUC cercano a 0.5 indica que el sintetizador no memoriza registros individuales.
# Nota oncologica: cuasi-identificadores como edad, sexo y ECOG aumentan el riesgo de
# reidentificacion de pacientes oncologicos en datasets de ensayos clinicos pequenos (n=479).
# Entrada: dataset real y logger. Salida: diccionario con AUC, TPR@FPR=0.1 y curva ROC,
# o None si todos los shadow models fallaron.
def membership_inference_shadow(
    df_real: pd.DataFrame,
    logger: logging.Logger,
) -> dict | None:
    """
    Ataque de membership inference con N_SHADOW shadow models.

    Metodologia:
        - Cada shadow model se entrena sobre el SHADOW_TRAIN_FRAC del dataset real.
        - Para cada registro real, se calcula su distancia minima al dataset sintetico
          generado por ese shadow model.
        - Score de ataque: negativo de la distancia (menor distancia = mayor probabilidad
          de haber sido miembro del entrenamiento).
        - Se acumulan todos los pares (score, etiqueta_miembro) de todos los shadows.
        - Se evaluan AUC y TPR a FPR=0.1 (criterios de aceptacion a priori).

    Criterios a priori:
        AUC <= 0.60, TPR@FPR=0.1 <= 0.20
    """
    logger.info("Membership inference con %d shadow models...", N_SHADOW)

    cols = [c for c in ALL_COLS if c in df_real.columns]
    n    = len(df_real)

    # Preprocesador de referencia ajustado sobre TODOS los reales para definir espacio comun de distancias
    X_real_all, preproc_ref = _fit_preprocessor(df_real)

    all_scores: list[float] = []
    all_labels: list[int]   = []

    for si in range(N_SHADOW):
        logger.info("  Shadow %d/%d...", si + 1, N_SHADOW)

        rng      = np.random.default_rng(SEED + 200 + si)
        idx_perm = rng.permutation(n)
        n_train  = int(n * SHADOW_TRAIN_FRAC)
        train_idx = idx_perm[:n_train]

        shadow_mask = np.zeros(n, dtype=bool)
        shadow_mask[train_idx] = True

        df_shadow = df_real[cols].iloc[train_idx].reset_index(drop=True)

        try:
            synth_s  = _train_ctgan(df_shadow, epochs=SHADOW_EPOCHS, seed_offset=200 + si)
            df_syn_s = synth_s.sample(num_rows=n)
            df_syn_s = _postprocess(df_syn_s, df_real)
            feats_ok = [c for c in FEATURES if c in df_syn_s.columns]
            df_syn_s = df_syn_s.dropna(subset=feats_ok)
        except Exception as exc:
            logger.warning("  Shadow %d fallo (%s); saltando.", si + 1, exc)
            continue

        if len(df_syn_s) < 10:
            logger.warning("  Shadow %d: datos sinteticos insuficientes; saltando.", si + 1)
            continue

        # Transformar sinteticos al espacio comun con .transform() para que las distancias sean comparables
        try:
            X_syn_s = preproc_ref.transform(df_syn_s[FEATURES].copy())
        except Exception:
            continue

        # Calcular distancia minima de cada registro real al sintetico del shadow (score de ataque)
        dist_mat = cdist(X_real_all, X_syn_s, metric="euclidean")  # (n_real, n_syn)
        min_dists = dist_mat.min(axis=1)

        # Score: negativo de la distancia (menor distancia = mayor score de membership)
        all_scores.extend((-min_dists).tolist())
        all_labels.extend(shadow_mask.astype(int).tolist())

    if len(all_scores) == 0:
        logger.error("No se obtuvieron scores de membership inference.")
        return None

    scores_arr = np.array(all_scores)
    labels_arr = np.array(all_labels)

    auc = float(roc_auc_score(labels_arr, scores_arr))
    fpr_arr, tpr_arr, _ = roc_curve(labels_arr, scores_arr)
    tpr_at_fpr01 = float(np.interp(0.10, fpr_arr, tpr_arr))

    # Comparar AUC y TPR@FPR=0.1 contra umbrales fijados a priori en ACCEPT
    accepted_auc = auc         <= ACCEPT["mi_auc_max"]      # umbral: AUC <= 0.60
    accepted_tpr = tpr_at_fpr01 <= ACCEPT["mi_tpr_fpr01_max"]  # umbral: TPR@FPR=0.1 <= 0.20

    logger.info(
        "  AUC = %.4f (%s)  TPR@FPR=0.1 = %.4f (%s)",
        auc, "ACEPTADO" if accepted_auc else "RECHAZADO",
        tpr_at_fpr01, "ACEPTADO" if accepted_tpr else "RECHAZADO",
    )

    return {
        "auc":            auc,
        "tpr_at_fpr01":   tpr_at_fpr01,
        "fpr":            fpr_arr.tolist(),
        "tpr":            tpr_arr.tolist(),
        "accepted_auc":   accepted_auc,
        "accepted_tpr":   accepted_tpr,
        "n_shadow":       N_SHADOW,
        "shadow_train_frac": SHADOW_TRAIN_FRAC,
    }


# ---------------------------------------------------------------------------
# K-anonimidad (quasi-identifier uniqueness)
# ---------------------------------------------------------------------------

# Mide el riesgo de reidentificacion mediante k-anonimidad sobre cuasi-identificadores.
# La k-anonimidad cuantifica cuantos registros del dataset real comparten los mismos valores
# de cuasi-identificadores que un registro sintetico dado. Un registro sintetico con k=1
# es "unico" y podria usarse como pivote para reidentificar al sujeto real correspondiente.
# Cuasi-identificadores seleccionados: AGE (en intervalos de AGE_BIN_STEP=5 anos), SEXCD y B_ECOGN.
# Estos tres campos son los cuasi-identificadores mas relevantes en oncologia clinica porque
# combinados con el diagnostico pueden identificar a pacientes en ensayos pequenos (n=479).
# Criterios a priori: registros sinteticos unicos (k=1) < 5%, k<=2 < 10%, k<=5 < 20%.
# Entrada: dataset sintetico, dataset real (como referencia de conteos) y logger.
# Salida: diccionario con fracciones por nivel k y flags de aceptacion.
def compute_k_anonymity(
    df_syn: pd.DataFrame,
    df_real: pd.DataFrame,
    logger: logging.Logger,
) -> dict:
    """
    Para cada registro sintetico, cuenta cuantos registros reales coinciden en los
    cuasi-identificadores: AGE (bin de 5 anos), SEXCD y B_ECOGN.

    Reporta la fraccion de registros sinteticos con k=1 (unicos), k<=2 y k<=5.
    Criterios de aceptacion a priori: k1<5%, k2<10%, k5<20%.
    """
    logger.info("K-anonimidad sobre cuasi-identificadores...")

    # Discretizar AGE en bins de 5 anos para definir el cuasi-identificador de edad
    # Funcion auxiliar: convierte una edad continua al limite inferior del intervalo de 5 anos.
    # El binning reduce la granularidad de la edad, aproximando el concepto de k-anonimidad
    # segun el estandar de anonimizacion de la AEPD para datos clinicos.
    def _age_bin(age: float) -> int:
        return int(float(age) // AGE_BIN_STEP) * AGE_BIN_STEP  # binning de edad: paso=5 anos

    # Funcion auxiliar: construye la clave de cuasi-identificador de una fila como tupla.
    # Combina edad bineada, sexo y ECOG basal: los tres cuasi-identificadores principales
    # de este dataset de ensayo clinico oncologico.
    def _qi_key(row) -> tuple:
        return (_age_bin(row["AGE"]), str(row["SEXCD"]), str(row["B_ECOGN"]))

    real_qi_counts: dict[tuple, int] = {}
    for _, row in df_real[["AGE", "SEXCD", "B_ECOGN"]].iterrows():
        k = _qi_key(row)
        real_qi_counts[k] = real_qi_counts.get(k, 0) + 1

    k_values: list[int] = []
    for _, row in df_syn[["AGE", "SEXCD", "B_ECOGN"]].iterrows():
        try:
            k_values.append(real_qi_counts.get(_qi_key(row), 0))
        except Exception:
            k_values.append(0)

    k_arr = np.array(k_values)
    n_syn = len(k_arr)

    k1_pct = float((k_arr == 1).sum() / n_syn)
    k2_pct = float((k_arr <= 2).sum() / n_syn)
    k5_pct = float((k_arr <= 5).sum() / n_syn)
    k0_pct = float((k_arr == 0).sum() / n_syn)

    # Comparar fracciones contra umbrales fijados a priori en ACCEPT
    a_k1 = k1_pct <= ACCEPT["kanon_k1_max"]  # umbral: k=1 <= 5%
    a_k2 = k2_pct <= ACCEPT["kanon_k2_max"]  # umbral: k<=2 <= 10%
    a_k5 = k5_pct <= ACCEPT["kanon_k5_max"]  # umbral: k<=5 <= 20%

    logger.info(
        "  k=1: %.1f%% (%s)  k<=2: %.1f%% (%s)  k<=5: %.1f%% (%s)",
        k1_pct * 100, "ACEPTADO" if a_k1 else "RECHAZADO",
        k2_pct * 100, "ACEPTADO" if a_k2 else "RECHAZADO",
        k5_pct * 100, "ACEPTADO" if a_k5 else "RECHAZADO",
    )

    return {
        "quasi_identifiers": ["AGE_bin_5y", "SEXCD", "B_ECOGN"],
        "n_synthetic":   n_syn,
        "k1_pct":        k1_pct,  "k1_accepted": a_k1,
        "k2_pct":        k2_pct,  "k2_accepted": a_k2,
        "k5_pct":        k5_pct,  "k5_accepted": a_k5,
        "k0_pct":        k0_pct,
    }


# ---------------------------------------------------------------------------
# Distance to Closest Record (DCR)
# ---------------------------------------------------------------------------

# Calcula la Distance to Closest Record (DCR) y la Real-to-Real Distance Reference (RRDR)
# en el espacio de covariables preprocesadas para cuantificar el riesgo de reidentificacion
# mediante proximidad geometrica.
# DCR: para cada registro sintetico, distancia Euclidea minima al registro real mas cercano.
#   Un DCR bajo indica que el sintetico es casi identico a algun real, aumentando el riesgo
#   de que revele informacion de ese sujeto especifico.
# RRDR: para cada registro real, distancia al vecino real mas cercano (leave-one-out).
#   Sirve como referencia del "ruido natural" del dataset: si DCR >= RRDR, los sinteticos
#   no estan mas cerca de los reales de lo que los reales lo estan entre si.
# Criterio a priori: DCR_p5 / RRDR_mediana >= 0.50.
# Entrada: matrices X_syn y X_real ya preprocesadas (mismo espacio de covariables) y logger.
# Salida: diccionario con percentiles de DCR y RRDR, ratio y flag de aceptacion.
def compute_dcr(
    X_syn: np.ndarray,
    X_real: np.ndarray,
    logger: logging.Logger,
) -> dict:
    """
    DCR: para cada registro sintetico, distancia Euclidea minima al real mas cercano.
    RRDR (Real-to-Real Distance): para cada registro real, distancia al vecino real
    mas cercano (leave-one-out), usada como referencia del "ruido natural" del dataset.

    Criterio a priori: DCR_p5 / RRDR_mediana >= 0.50.
    """
    logger.info("Computando DCR y RRDR...")

    # DCR: matriz de distancias sintetico vs real; min por fila = distancia al vecino mas cercano
    dist_sr  = cdist(X_syn, X_real, metric="euclidean")   # (n_syn, n_real)
    dcr      = dist_sr.min(axis=1)

    # RRDR: distancias real vs real con diagonal infinita para excluir la distancia consigo mismo (LOO)
    dist_rr  = cdist(X_real, X_real, metric="euclidean")  # (n_real, n_real)
    np.fill_diagonal(dist_rr, np.inf)
    rrdr = dist_rr.min(axis=1)

    pcts = [5, 25, 50, 75, 95]
    dcr_p  = {f"p{p}": float(np.percentile(dcr, p))  for p in pcts}
    rrdr_p = {f"p{p}": float(np.percentile(rrdr, p)) for p in pcts}

    rrdr_med = rrdr_p["p50"]
    # Calcular ratio DCR_p5 / RRDR_mediana y comparar contra el umbral fijado a priori (>= 0.50)
    ratio    = dcr_p["p5"] / rrdr_med if rrdr_med > 0 else float("nan")
    accepted = bool(ratio >= ACCEPT["dcr_p5_rrdr_ratio_min"]) if not np.isnan(ratio) else False  # umbral: ratio >= 0.50

    logger.info(
        "  DCR p5=%.4f  RRDR mediana=%.4f  ratio=%.4f (%s)",
        dcr_p["p5"], rrdr_med, ratio, "ACEPTADO" if accepted else "RECHAZADO",
    )

    return {
        "dcr_synthetic":               dcr_p,
        "rrdr_real":                   rrdr_p,
        "dcr_p5_rrdr_median_ratio":    ratio,
        "accepted":                    accepted,
        "_dcr_raw":                    dcr.tolist(),
        "_rrdr_raw":                   rrdr.tolist(),
    }


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------

# Genera el grafico de barras comparativo TRTR vs TSTR con barras de error (desviacion tipica).
# Visualiza la utilidad del dataset sintetico: si la barra TSTR es cercana a TRTR, los
# sinteticos son informativos para el modelo de supervivencia. El ratio TSTR/TRTR se muestra
# como anotacion en el grafico para cuantificar la perdida de utilidad.
# El pie de advertencia DISCLAIMER recuerda el uso exclusivamente metodologico de los sinteticos.
# Entrada: diccionario de metricas TSTR, ruta de salida y logger. Sin retorno (guarda PNG).
def _plot_tstr(tstr: dict, path: Path, logger: logging.Logger) -> None:
    _setup_rcparams()
    fig, ax = plt.subplots(figsize=(7, 4.5))

    labels = ["TRTR\n(referencia real)", "TSTR\n(sintetico -> real)"]
    means  = [tstr["trtr_mean"], tstr["tstr_mean"]]
    stds   = [tstr["trtr_std"],  tstr["tstr_std"]]
    colors = [C_DARK, C_AMBER]

    bars = ax.bar(labels, means, yerr=stds, width=0.45, color=colors,
                  capsize=6, edgecolor="white", linewidth=0.8, error_kw={"lw": 1.5})
    for bar, m, s in zip(bars, means, stds):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            m + s + 0.005,
            f"{m:.3f}",
            ha="center", va="bottom", fontsize=10, fontweight="bold",
            color=bar.get_facecolor(),
        )

    ax.axhline(0.5, color=C_GRAY, ls="--", lw=1.2, label="Referencia aleatoria (0.5)")
    ax.set_ylim(0.4, max(means) + max(stds) + 0.08)
    ax.set_ylabel("C-index (OS)")
    ax.set_title("Utilidad TSTR vs TRTR - Cox PH (OS)", color=C_DARK, fontweight="bold")
    ax.legend()

    ratio = tstr.get("utility_ratio", float("nan"))
    ax.text(
        0.97, 0.06,
        f"Ratio TSTR/TRTR = {ratio:.3f}",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=9, color=C_DARK,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=C_LIGHT, lw=1),
    )
    ax.text(
        0.5, -0.13, DISCLAIMER,
        transform=ax.transAxes, ha="center", va="top",
        fontsize=6, color=C_GRAY, style="italic",
        wrap=True,
    )

    fig.tight_layout()
    _save_fig(fig, path)
    logger.info("Guardado: %s", path.name)


# Genera la curva ROC del ataque de membership inference junto con las lineas de referencia:
# clasificador aleatorio (AUC=0.5), umbral de TPR@FPR=0.1 y punto de operacion del ataque.
# La etiqueta "ACEPTADO" o "RECHAZADO" se colorea en verde o ambar segun los criterios a priori.
# Un AUC cercano a 0.5 indica que el sintetizador no memoriza registros individuales del real.
# Entrada: diccionario de membership inference, ruta de salida y logger. Sin retorno (guarda PNG).
def _plot_membership(mi: dict, path: Path, logger: logging.Logger) -> None:
    _setup_rcparams()
    fig, ax = plt.subplots(figsize=(6, 5))

    fpr  = np.array(mi["fpr"])
    tpr  = np.array(mi["tpr"])
    auc  = mi["auc"]
    t01  = mi["tpr_at_fpr01"]

    ax.plot(fpr, tpr, color=C_DARK, lw=2, label=f"Ataque MI (AUC = {auc:.4f})")
    ax.plot([0, 1], [0, 1], "--", color=C_GRAY, lw=1.2, label="Clasificador aleatorio")
    ax.axvline(0.10, color=C_AMBER, ls=":", lw=1.5, alpha=0.8)
    ax.scatter([0.10], [t01], color=C_AMBER, zorder=5, s=60,
               label=f"TPR@FPR=0.1 = {t01:.3f}")
    ax.axhline(
        ACCEPT["mi_tpr_fpr01_max"], color=C_GREEN, ls="--", lw=1.2,
        label=f"Umbral TPR ({ACCEPT['mi_tpr_fpr01_max']})",
    )

    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_xlabel("Tasa de Falsos Positivos (FPR)")
    ax.set_ylabel("Tasa de Verdaderos Positivos (TPR)")
    ax.set_title(
        f"Membership Inference - Shadow Models (n={N_SHADOW})",
        color=C_DARK, fontweight="bold",
    )
    ax.legend(loc="lower right", fontsize=8)

    aceptado = mi["accepted_auc"] and mi["accepted_tpr"]
    ax.text(
        0.97, 0.10,
        "ACEPTADO" if aceptado else "RECHAZADO",
        transform=ax.transAxes, ha="right", va="bottom",
        fontsize=12, fontweight="bold",
        color=C_GREEN if aceptado else C_AMBER,
    )

    fig.tight_layout()
    _save_fig(fig, path)
    logger.info("Guardado: %s", path.name)


# Genera histogramas superpuestos de DCR (sintetico vs real) y RRDR (real vs real LOO).
# Permite comparar visualmente si los sinteticos mantienen una distancia suficiente respecto
# a los reales (DCR >> 0) o si estan concentrados cerca de registros reales concretos.
# La linea vertical en DCR_p5 y la anotacion del ratio facilitan la auditoria de privacidad.
# Un solapamiento significativo entre DCR y RRDR indica que los sinteticos son indistinguibles
# de los reales en el espacio de covariables, lo que supone un riesgo de reidentificacion.
# Entrada: diccionario DCR, ruta de salida y logger. Sin retorno (guarda PNG).
def _plot_dcr(dcr: dict, path: Path, logger: logging.Logger) -> None:
    _setup_rcparams()
    fig, ax = plt.subplots(figsize=(8, 4.5))

    d_raw = np.array(dcr["_dcr_raw"])
    r_raw = np.array(dcr["_rrdr_raw"])
    bins  = np.histogram_bin_edges(np.concatenate([d_raw, r_raw]), bins=40)

    ax.hist(d_raw, bins=bins, color=C_AMBER, alpha=0.65, label="DCR (sintetico vs real)")
    ax.hist(r_raw, bins=bins, color=C_DARK,  alpha=0.50, label="RRDR (real vs real, LOO)")

    p5 = dcr["dcr_synthetic"]["p5"]
    ax.axvline(p5, color=C_AMBER, ls="--", lw=2.0, label=f"DCR p5 = {p5:.3f}")

    ratio = dcr["dcr_p5_rrdr_median_ratio"]
    ax.set_xlabel("Distancia Euclidea (espacio preprocesado)")
    ax.set_ylabel("Frecuencia")
    ax.set_title(
        "DCR y RRDR - mayor DCR implica menor riesgo de reidentificacion",
        color=C_DARK, fontweight="bold",
    )
    ax.legend()
    ax.text(
        0.97, 0.97,
        f"DCR_p5 / RRDR_median = {ratio:.3f}\n{'ACEPTADO' if dcr['accepted'] else 'RECHAZADO'}",
        transform=ax.transAxes, ha="right", va="top", fontsize=9, color=C_DARK,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=C_LIGHT, lw=1),
    )

    fig.tight_layout()
    _save_fig(fig, path)
    logger.info("Guardado: %s", path.name)


# Genera el grafico de barras de k-anonimidad: porcentaje de registros sinteticos por nivel k.
# Cada barra incluye una linea roja discontinua que marca el umbral de aceptacion a priori.
# Los cuasi-identificadores usados son AGE (intervalos de 5 anos), SEXCD y B_ECOGN.
# La barra "k=0 (sin match)" indica sinteticos sin ningun registro real con los mismos
# cuasi-identificadores, lo que en principio es favorable para la privacidad pero puede
# indicar distribucion fuera del dominio clinico observado.
# Entrada: diccionario de k-anonimidad, ruta de salida y logger. Sin retorno (guarda PNG).
def _plot_kanon(kanon: dict, path: Path, logger: logging.Logger) -> None:
    _setup_rcparams()
    fig, ax = plt.subplots(figsize=(7, 4.5))

    n_syn = kanon["n_synthetic"]
    labels_bar = ["k=1\n(unicos)", "k<=2", "k<=5", "k=0\n(sin match)"]
    values_bar = [
        kanon["k1_pct"] * 100,
        kanon["k2_pct"] * 100,
        kanon["k5_pct"] * 100,
        kanon["k0_pct"] * 100,
    ]
    thresholds = [
        ACCEPT["kanon_k1_max"] * 100,
        ACCEPT["kanon_k2_max"] * 100,
        ACCEPT["kanon_k5_max"] * 100,
        None,
    ]
    colors_bar = [C_AMBER, C_DARK, C_LIGHT, C_GRAY]
    edge_cols  = ["#8B5A00", "#0F2740", "#A0C8D8", "#555555"]

    bars = ax.bar(labels_bar, values_bar, color=colors_bar,
                  edgecolor=edge_cols, linewidth=0.8, width=0.55)
    for bar, val in zip(bars, values_bar):
        if val >= 0.3:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.2,
                f"{val:.1f}%",
                ha="center", va="bottom", fontsize=9,
            )

    for i, thr in enumerate(thresholds):
        if thr is not None:
            x_lo = i / len(labels_bar) + 0.02
            x_hi = (i + 1) / len(labels_bar) - 0.02
            ax.axhline(thr, xmin=x_lo, xmax=x_hi,
                       color="red", ls="--", lw=1.8, alpha=0.85)

    ax.set_ylabel("Porcentaje de registros sinteticos (%)")
    ax.set_title(
        f"K-anonimidad de registros sinteticos (n={n_syn})\n"
        "QI: AGE (intervalos de 5 anos), SEXCD, B_ECOGN",
        color=C_DARK, fontweight="bold",
    )
    ax.set_ylim(0, max(values_bar + [ACCEPT["kanon_k5_max"] * 100]) + 8)

    legend_els = [Line2D([0], [0], color="red", ls="--", lw=1.8, label="Umbral de aceptacion")]
    ax.legend(handles=legend_els, fontsize=8, loc="upper right")

    fig.tight_layout()
    _save_fig(fig, path)
    logger.info("Guardado: %s", path.name)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Punto de entrada principal del componente de datos sinteticos.
# Orquesta el pipeline completo en 7 etapas secuenciales:
#   1. Generacion de N_SYNTHETIC registros sinteticos con CTGAN.
#   2. Evaluacion de utilidad TSTR (Train on Synthetic, Test on Real) con Cox PH y CV k=5.
#   3. Evaluacion del riesgo de membership inference con N_SHADOW shadow models de CTGAN.
#   4. Computo de k-anonimidad sobre cuasi-identificadores (AGE_bin, SEXCD, B_ECOGN).
#   5. Computo de DCR y RRDR en el espacio de covariables preprocesadas.
#   6. Generacion de las cuatro figuras de reporte (TSTR, membership, DCR, k-anonimidad).
#   7. Serializacion de todas las metricas en synthetic_metrics.json.
# Retorna 0 si la ejecucion es exitosa, 1 si falta alguna dependencia o el dataset de entrada.
# Advertencia: los datos sinteticos generados son exclusivamente para prototipado metodologico.
def main() -> int:
    logger = _setup_logger()
    _set_global_seeds(SEED)

    logger.info(DISCLAIMER)
    logger.info("=" * 70)

    try:
        import sdv  # noqa: F401
    except ImportError:
        logger.error("SDV no encontrado. Instalar con: pip install sdv>=1.0.0")
        return 1

    if not DATASET_PATH.exists():
        logger.error("Dataset no encontrado: %s", DATASET_PATH)
        return 1

    df_real = pd.read_csv(DATASET_PATH)
    logger.info("Dataset real: %d sujetos, %d columnas.", *df_real.shape)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------
    # 1. Generacion de datos sinteticos
    # -------------------------------------------------------------------
    logger.info("\n=== 1. GENERACION DE DATOS SINTETICOS ===")
    df_syn = generate_synthetic(df_real, logger)
    syn_path = OUTPUT_DIR / "synthetic_dataset.csv"
    df_syn.to_csv(syn_path, index=False)
    logger.info(
        "Dataset sintetico guardado: %s (%d filas). "
        "Excluido del control de versiones por output/.",
        syn_path.name, len(df_syn),
    )

    # -------------------------------------------------------------------
    # 2. Evaluacion TSTR
    # -------------------------------------------------------------------
    logger.info("\n=== 2. EVALUACION TSTR ===")
    tstr = evaluate_tstr(df_real, df_syn, logger)

    if tstr:
        cmp_path = OUTPUT_DIR / "synthetic_tstr_comparison.csv"
        tstr["per_fold_df"].to_csv(cmp_path, index=False)
        logger.info("Guardado: %s", cmp_path.name)

    # -------------------------------------------------------------------
    # 3. Membership inference (shadow models)
    # -------------------------------------------------------------------
    logger.info("\n=== 3. MEMBERSHIP INFERENCE (SHADOW MODELS) ===")
    mi = membership_inference_shadow(df_real, logger)

    # -------------------------------------------------------------------
    # 4. K-anonimidad
    # -------------------------------------------------------------------
    logger.info("\n=== 4. K-ANONIMIDAD (CUASI-IDENTIFICADORES) ===")
    kanon = compute_k_anonymity(df_syn, df_real, logger)

    # -------------------------------------------------------------------
    # 5. DCR - Distance to Closest Record
    # -------------------------------------------------------------------
    logger.info("\n=== 5. DISTANCE TO CLOSEST RECORD (DCR) ===")
    X_real_proc, preproc_ref = _fit_preprocessor(df_real)
    X_syn_proc  = preproc_ref.transform(df_syn[FEATURES].copy())
    dcr = compute_dcr(X_syn_proc, X_real_proc, logger)

    # -------------------------------------------------------------------
    # 6. Figuras
    # -------------------------------------------------------------------
    logger.info("\n=== 6. FIGURAS ===")
    if tstr:
        _plot_tstr(tstr, OUTPUT_DIR / "fig_synthetic_tstr.png", logger)
    if mi:
        _plot_membership(mi, OUTPUT_DIR / "fig_synthetic_membership.png", logger)
    _plot_dcr(dcr,   OUTPUT_DIR / "fig_synthetic_dcr.png",   logger)
    _plot_kanon(kanon, OUTPUT_DIR / "fig_synthetic_kanon.png", logger)

    # -------------------------------------------------------------------
    # 7. JSON de metricas
    # -------------------------------------------------------------------
    tstr_json = {k: v for k, v in tstr.items() if k != "per_fold_df"} if tstr else {}
    mi_json   = {k: v for k, v in (mi or {}).items() if k not in ("fpr", "tpr")}
    dcr_json  = {k: v for k, v in dcr.items() if not k.startswith("_")}

    overall = all([
        mi is not None and mi["accepted_auc"] and mi["accepted_tpr"],
        kanon["k1_accepted"] and kanon["k2_accepted"] and kanon["k5_accepted"],
        dcr["accepted"],
    ])

    metrics = {
        "disclaimer":   DISCLAIMER,
        "generation":   {
            "method":      "CTGAN (SDV >= 1.0)",
            "epochs":      MAIN_EPOCHS,
            "n_real":      int(len(df_real)),
            "n_synthetic": int(len(df_syn)),
            "seed":        SEED,
        },
        "utility_tstr": tstr_json,
        "reidentification_risk": {
            "membership_inference": mi_json,
            "k_anonymity":          kanon,
            "dcr":                  dcr_json,
        },
        "acceptance_criteria": ACCEPT,
        "overall_accepted":    overall,
    }

    metrics_path = OUTPUT_DIR / "synthetic_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, ensure_ascii=False, indent=2)
    logger.info("Guardado: %s", metrics_path.name)

    # Resumen final
    logger.info("\n%s", "=" * 70)
    logger.info("RESUMEN - COMPONENTE DE DATOS SINTETICOS")
    logger.info(DISCLAIMER)
    if tstr:
        logger.info(
            "  Utilidad TSTR: C-index = %.4f (TRTR = %.4f, ratio = %.4f)",
            tstr["tstr_mean"], TRTR_CINDEX_MEAN, tstr["utility_ratio"],
        )
    if mi:
        logger.info(
            "  Membership Inference: AUC = %.4f, TPR@FPR=0.1 = %.4f",
            mi["auc"], mi["tpr_at_fpr01"],
        )
    logger.info(
        "  K-anonimidad: k=1 = %.1f%%, k<=2 = %.1f%%, k<=5 = %.1f%%",
        kanon["k1_pct"] * 100, kanon["k2_pct"] * 100, kanon["k5_pct"] * 100,
    )
    logger.info(
        "  DCR p5 = %.4f  RRDR mediana = %.4f  ratio = %.4f",
        dcr["dcr_synthetic"]["p5"],
        dcr["rrdr_real"]["p50"],
        dcr["dcr_p5_rrdr_median_ratio"],
    )
    logger.info("  Estado global: %s", "ACEPTADO" if overall else "RECHAZADO (revisar metricas)")
    logger.info("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
