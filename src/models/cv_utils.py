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

# Construye el array estructurado requerido por scikit-survival a partir de
# dos arrays numpy de igual longitud (indicador de evento y tiempo en dias).
# Entrada: event (0 = censura, 1 = evento) y time (float, dias hasta evento o censura).
# Salida: ndarray con dtype [('event', bool), ('time', float)].
# Perspectiva oncologica: OS usa DTH/DTHDY; PFS usa PFSCD/PFSDY.
# Esta funcion es compartida por Cox, RSF y XGBoost para garantizar
# un formato uniforme en todos los modelos del proyecto.
def make_y(event: np.ndarray, time: np.ndarray) -> np.ndarray:
    return np.array(
        [(bool(e), float(t)) for e, t in zip(event, time)],
        dtype=[("event", bool), ("time", float)],
    )


# ---------------------------------------------------------------------------
# Rejilla de tiempos para IBS
# ---------------------------------------------------------------------------

# Calcula la rejilla global de N_TIME_GRID puntos equiespaciados en percentiles
# entre TIME_Q_LOW (p10) y TIME_Q_HIGH (p90) de los tiempos de evento.
# Entrada: array estructurado y con campos 'event' y 'time'.
# Salida: ndarray de 25 puntos de tiempo (float, dias) para evaluar el IBS.
# Justificacion: la rejilla interior al rango de eventos reduce la varianza
# del estimador IPCW de Kaplan-Meier y evita extrapolaciones fuera de la muestra.
def event_time_grid(y: np.ndarray) -> np.ndarray:
    """25 puntos entre TIME_Q_LOW y TIME_Q_HIGH de los tiempos de evento."""
    event_times = y["time"][y["event"]]
    return np.percentile(event_times, np.linspace(TIME_Q_LOW, TIME_Q_HIGH, N_TIME_GRID))


# Recorta la rejilla global al maximo tiempo observado (incluidos censurados)
# en el fold de entrenamiento para que el estimador IPCW sea valido.
# Entrada: global_times (rejilla completa), y_tr (array estructurado del fold train).
# Salida: subconjunto de global_times con valores estrictamente menores que
#   y_tr["time"].max(). Control anti-fuga temporal: la cota superior del IPCW
#   depende del fold de entrenamiento y no del dataset completo.
def safe_fold_times(global_times: np.ndarray, y_tr: np.ndarray) -> np.ndarray:
    """
    Recorta la rejilla al maximo tiempo observado en el fold de entrenamiento
    (requisito del estimador IPCW de Kaplan-Meier para el IBS).
    """
    return global_times[global_times < y_tr["time"].max()]


# Calcula el IBS filtrando los sujetos de test cuyo tiempo supera el maximo
# tiempo observado en el fold de entrenamiento (requisito IPCW).
# Entrada: y_tr (array train), y_te (array test), surv_mat (probabilidades
#   de supervivencia predichas para el test), fold_times (rejilla recortada).
# Salida: IBS como float, o NaN si no hay sujetos validos o la rejilla esta vacia.
# Justificacion: el estimador IPCW de Kaplan-Meier no puede extrapolar mas alla
# del tiempo maximo observado en entrenamiento, por lo que los sujetos de test
# con tiempo superior deben excluirse del calculo del IBS por fold.
def safe_ibs(y_tr, y_te, surv_mat, fold_times) -> float:
    """
    IBS con filtrado de sujetos de test fuera del rango de entrenamiento.
    Devuelve NaN si no hay sujetos validos.
    """
    valid = y_te["time"] < y_tr["time"].max()
    if valid.sum() == 0 or len(fold_times) == 0:
        return float("nan")
    # Robustez ante folds degenerados: si la rejilla de tiempos cae fuera del seguimiento
    # del subconjunto de test (puede ocurrir con folds muy pequenos), el estimador IPCW de
    # integrated_brier_score lanza ValueError. Se degrada a NaN, que el nanmean posterior
    # ya gestiona, en lugar de abortar toda la ejecucion. En el dato real (n=479, k=5) esta
    # rama no se activa, por lo que el resultado del pipeline primario no varia.
    try:
        return float(integrated_brier_score(y_tr, y_te[valid], surv_mat[valid], fold_times))
    except ValueError:
        return float("nan")


# ---------------------------------------------------------------------------
# Bootstrap sobre predicciones OOF
# ---------------------------------------------------------------------------

# Estima la distribucion muestral del C-index mediante bootstrap no parametrico
# (n=1000 remuestras con reemplazo) sobre las predicciones OOF agregadas de todos los folds.
# Entrada: y_all (array estructurado completo), oof_risk (vector de riesgos predichos OOF),
#   n numero de remuestras, seed semilla para reproducibilidad.
# Salida: ndarray de longitud <= n con los valores de C-index por remuestra.
# El bootstrap sobre OOF evita el sesgo de sobreajuste: cada prediccion fue
# generada por un modelo que no vio el sujeto en entrenamiento.
# El IC95% percentilico resultante es la banda de incertidumbre reportada en la memoria D3.
def bootstrap_cindex(
    y_all: np.ndarray,
    oof_risk: np.ndarray,
    n: int = N_BOOTSTRAP,
    seed: int = SEED,
) -> np.ndarray:
    rng = np.random.default_rng(seed)  # fijacion de semilla para reproducibilidad
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


# Estima la distribucion muestral del IBS mediante bootstrap no parametrico
# (n=1000 remuestras con reemplazo) sobre la matriz de supervivencia OOF.
# Entrada: y_all (referencia IPCW, array completo), oof_surv (matriz n_sujetos x n_tiempos
#   con probabilidades OOF), times (rejilla comun a todos los folds), n y seed.
# Salida: ndarray de longitud <= n con los valores de IBS por remuestra.
# La semilla se desplaza (seed + 1) para independencia estadistica respecto
# al bootstrap de C-index cuando ambos se ejecutan en el mismo script.
def bootstrap_ibs(
    y_all: np.ndarray,
    oof_surv: np.ndarray,
    times: np.ndarray,
    n: int = N_BOOTSTRAP,
    seed: int = SEED,
) -> np.ndarray:
    rng = np.random.default_rng(seed + 1)  # semilla desplazada para independencia del bootstrap de C-index
    n_samples = len(y_all)
    out = []
    for _ in range(n):
        idx = rng.integers(0, n_samples, size=n_samples)  # remuestreo bootstrap con reemplazo
        try:
            ibs = float(integrated_brier_score(y_all, y_all[idx], oof_surv[idx], times))
            out.append(ibs)
        except Exception:
            continue
    return np.array(out)


# Calcula estadisticos de resumen (media, desviacion estandar y IC95%
# percentilico) de un array de valores obtenidos por bootstrap.
# Entrada: arr ndarray con los valores de una metrica en n remuestras.
# Salida: diccionario con claves 'mean', 'std', 'ci_low' y 'ci_high'.
# Funcion compartida por todos los modelos del proyecto para garantizar
# uniformidad en la presentacion de resultados en la tabla comparativa D3.
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

# Construye el vector de estratos para StratifiedKFold combinando el indicador
# de evento con el brazo de aleatorizacion TXG (NESP=1 / placebo=0).
# Entrada: dataframe df con columnas event_col y 'TXG'; event_col como string.
# Salida: ndarray de enteros en {0, 1, 2, 3} (4 clases de estrato).
# Justificacion: la estratificacion garantiza que cada fold mantenga la proporcion
# de eventos y el balance entre brazos NESP y placebo, reduciendo la varianza
# del estimador del C-index entre folds y haciendo el CV% un indicador fiable
# de estabilidad del modelo segun el criterio de seleccion a priori.
# Nota oncologica: TXG es variable de estratificacion, nunca predictor.
def make_strata(df, event_col: str) -> np.ndarray:
    """Estrato = indicador de evento x TXG => 4 clases (0-3)."""
    return df[event_col].astype(int).values * 2 + df["TXG"].astype(int).values
