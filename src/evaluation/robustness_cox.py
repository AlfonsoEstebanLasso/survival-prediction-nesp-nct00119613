"""
src/evaluation/robustness_cox.py

Proposito:
    Análisis de robustez del modelo Cox PH final sobre OS (primario) y PFS (secundario).

    1. C-index e IBS por subgrupos clinicos disponibles en el dataset derivado:
       brazo (TXG), estado funcional basal (B_ECOGN), carga de comorbilidades (MEDHX_N),
       sexo (SEXCD), edad (AGE) y tiempo desde diagnostico (CADIAGM).
       Discusion de transferibilidad: si el IC bootstrap de un subgrupo no solapa
       con el global, el modelo se transfiere de forma diferencial.

    2. Análisis de errores por percentil de riesgo predicho OOF:
       para cada quintil de riesgo se calcula la tasa de evento observada, la
       supervivencia KM media y el riesgo medio predicho, permitiendo detectar
       grupos en los que el modelo calibra peor.

Entradas:
    output/nesp_nct00119613_dataset.csv

Salidas (en output/):
    robustness_subgroups_OS.csv / PFS.csv   Tabla de metricas por subgrupo
    fig_subgroup_cindex.png                 Forest plot de C-index por subgrupo
    fig_error_by_risk_OS.png / PFS.png      Análisis de errores por quintil de riesgo
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter
from sksurv.metrics import concordance_index_censored, integrated_brier_score

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.eval_cox_final import collect_oof
from src.models.cv_utils import SEED, make_y

warnings.filterwarnings("ignore")

DATASET_PATH = PROJECT_ROOT / "output" / "nesp_nct00119613_dataset.csv"
OUTPUT_DIR   = PROJECT_ROOT / "output"
N_BOOT       = 1000
N_QUINTILES  = 5

C_DARK  = "#1F4E79"
C_LIGHT = "#D5E8F0"
C_AMBER = "#B7791F"
C_GREEN = "#1F7A3A"
C_GRAY  = "#888888"

ENDPOINTS = {
    "OS":  {"event": "DTH",   "time": "DTHDY"},
    "PFS": {"event": "PFSCD", "time": "PFSDY"},
}


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

# Inicializa el logger del modulo con formato de hora, nivel y mensaje.
# Entrada: ninguna. Salida: objeto Logger configurado con StreamHandler a stdout.
# Registra el progreso del análisis de robustez en consola sin dependencia de ficheros de log.
def setup_logger() -> logging.Logger:
    logger = logging.getLogger("robustness")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(message)s", "%H:%M:%S"))
        logger.addHandler(sh)
    return logger


# Establece parametros globales de estilo para matplotlib.
# Entrada: ninguna. Salida: ninguna (efecto colateral sobre plt.rcParams).
# Garantiza coherencia visual entre todos los graficos del modulo de robustez.
def _rc() -> None:
    plt.rcParams.update({
        "font.family":     "sans-serif",
        "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": "#E0E0E0", "grid.linewidth": 0.7,
        "axes.titlesize": 11, "axes.labelsize": 10,
        "xtick.labelsize": 9, "ytick.labelsize": 9,
        "legend.fontsize": 8, "figure.dpi": 150,
    })


# Guarda una figura matplotlib en disco y cierra el objeto para liberar memoria.
# Entrada: figura (Figure), ruta de salida (Path o str), resolucion en ppp.
# Salida: ninguna. Imprescindible en bucles que generan multiples figuras por endpoint.
def _save(fig, path, dpi=300):
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Definicion de subgrupos
# ---------------------------------------------------------------------------

# Define las mascaras booleanas que identifican cada subgrupo clinico de análisis.
# Entrada: dataframe derivado completo (n = 479 sujetos).
# Salida: diccionario {nombre_subgrupo: array booleano de longitud n}.
# Perspectiva de ciencia de datos: la particion en subgrupos permite evaluar si el modelo
# transfiere su capacidad discriminativa de forma homogenea o presenta heterogeneidad
# pronostica. Los subgrupos se definen sobre la mediana de variables continuas (corte
# empirico, sin sesgo de seleccion) y sobre categorias binarias o nominales predefinidas.
# La inclusion del brazo TXG como subgrupo (NESP vs placebo) permite analizar la
# transferibilidad entre poblaciones con diferente distribucion de hemoglobina, sin
# implicar causalidad: TXG es variable de estratificacion y nunca se usa como predictor.
# Nota oncologica: B_ECOGN 2 vs 1 es el contraste mas relevante para heterogeneidad
# pronostica en oncologia: ECOG 2 implica mayor limitacion funcional y menor reserva
# fisiologica, lo que puede reducir la capacidad discriminativa del modelo en ese estrato.
# El sexo (SEXCD) se incluye como subgrupo de equidad: detectar diferencias en C-index
# por sexo es un requisito de la perspectiva de genero en modelos de IA en salud.
def build_subgroups(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Devuelve mascaras booleanas numpy por subgrupo."""
    age_med     = df["AGE"].median()
    cadiagm_med = df["CADIAGM"].fillna(df["CADIAGM"].median()).median()
    medhx_med   = df["MEDHX_N"].median()

    cadiagm_imp = df["CADIAGM"].fillna(df["CADIAGM"].median()).values

    sg: dict[str, np.ndarray] = {
        "Global":                               np.ones(len(df), dtype=bool),
        # Brazo de tratamiento: variable de estratificacion incluida solo como subgrupo de transferibilidad, nunca como predictor
        "Brazo NESP (TXG = 1)":                 df["TXG"].values == 1,
        "Brazo placebo (TXG = 0)":              df["TXG"].values == 0,
        # Estado funcional basal (BYVAR: 1 = ECOG 0-1, 2 = ECOG 2)
        "Estado funcional bueno (B_ECOGN = 1)": df["B_ECOGN"].values == 1,
        "Estado funcional reducido (B_ECOGN = 2)": df["B_ECOGN"].values == 2,
        # Carga de comorbilidades
        f"Comorbilidades bajas (MEDHX_N <= {int(medhx_med)})":
            df["MEDHX_N"].values <= medhx_med,
        f"Comorbilidades altas (MEDHX_N > {int(medhx_med)})":
            df["MEDHX_N"].values > medhx_med,
        # Sexo (SEXCD = 0 hombre, 1 mujer segun codificacion SAS)
        "Sexo = 0":                             df["SEXCD"].values == 0,
        "Sexo = 1":                             df["SEXCD"].values == 1,
        # Edad respecto a la mediana
        f"Edad < {int(age_med)} años":           df["AGE"].values < age_med,
        f"Edad >= {int(age_med)} años":          df["AGE"].values >= age_med,
        # Tiempo desde diagnostico (proxy de linea de tratamiento)
        f"Tiempo desde diag. < mediana ({cadiagm_med:.2f} m)":
            cadiagm_imp < cadiagm_med,
        f"Tiempo desde diag. >= mediana ({cadiagm_med:.2f} m)":
            cadiagm_imp >= cadiagm_med,
    }
    return sg


# ---------------------------------------------------------------------------
# C-index por subgrupo con bootstrap
# ---------------------------------------------------------------------------

# Calcula el C-index puntual e IC95% bootstrap para un subgrupo definido por una mascara booleana.
# Entrada: array structured y (event, time), riesgo OOF, mascara de subgrupo, n iteraciones y semilla.
# Salida: tupla (C-index, IC_lo, IC_hi, n_subgrupo, n_eventos); NaN si el subgrupo no es evaluable.
# Perspectiva de ciencia de datos: el bootstrap por estrato (n = 1000 remuestreos con reemplazamiento)
# proporciona IC95% empiricos que reflejan la incertidumbre del C-index dentro de cada subgrupo.
# Si el IC de un subgrupo no solapa con el IC global, existe evidencia de rendimiento diferencial
# (transferibilidad limitada). Los umbrales minimos (n >= 10, n_eventos >= 5) evitan estimaciones
# degeneradas en subgrupos demasiado pequenos. La semilla se modula por la suma de indices del
# subgrupo para garantizar independencia entre subgrupos manteniendo reproducibilidad exacta.
# Nota oncologica: el subgrupo ECOG 2 tiene mayor riesgo basal y menor heterogeneidad pronostica,
# lo que puede reducir el C-index: un C-index mas bajo en ese estrato no implica error del modelo.
def subgroup_cindex(
    y_all: np.ndarray,
    oof_risk: np.ndarray,
    mask: np.ndarray,
    n_boot: int = N_BOOT,
    seed: int = SEED,
) -> tuple[float, float, float, int, int]:
    idx = np.where(mask)[0]
    y_sg   = y_all[idx]
    r_sg   = oof_risk[idx]
    n_sg   = len(idx)
    n_ev   = int(y_sg["event"].sum())

    if n_ev < 5 or n_sg < 10:
        return np.nan, np.nan, np.nan, n_sg, n_ev

    try:
        c, *_ = concordance_index_censored(y_sg["event"], y_sg["time"], r_sg)
    except Exception:
        return np.nan, np.nan, np.nan, n_sg, n_ev

    rng = np.random.default_rng(seed + idx.sum() % 9999)  # Semilla modular por subgrupo: reproducibilidad e independencia entre estratos
    boot = []
    for _ in range(n_boot):
        bi = rng.integers(0, n_sg, n_sg)
        try:
            bc, *_ = concordance_index_censored(
                y_sg["event"][bi], y_sg["time"][bi], r_sg[bi])
            boot.append(bc)
        except Exception:
            pass
    boot = np.array(boot)
    lo = float(np.percentile(boot, 2.5)) if len(boot) else np.nan
    hi = float(np.percentile(boot, 97.5)) if len(boot) else np.nan
    return float(c), lo, hi, n_sg, n_ev


# ---------------------------------------------------------------------------
# IBS por subgrupo
# ---------------------------------------------------------------------------

# Calcula el Integrated Brier Score (IBS) para un subgrupo definido por una mascara booleana.
# Entrada: array structured y completo, predicciones de supervivencia OOF, tiempos evaluados y mascara.
# Salida: IBS del subgrupo (float); NaN si el subgrupo no es evaluable (menos de 5 eventos).
# Perspectiva de ciencia de datos: el IBS mide la calibración-discriminacion conjunta integrada
# en el tiempo (0 = perfecto, 0.25 = modelo nulo). Se pasa y_all completo como referencia de
# censura para la estimacion IPCW (inverse probability of censoring weighting): esto garantiza
# que la correccion por censura sea consistente con la distribucion global, aunque el calculo
# de la perdida se restrinja al subgrupo. Subgrupos con alta censura pueden tener IBS inestable.
def subgroup_ibs(
    y_all: np.ndarray,
    oof_surv: np.ndarray,
    safe_times: np.ndarray,
    mask: np.ndarray,
) -> float:
    idx = np.where(mask)[0]
    y_sg   = y_all[idx]
    s_sg   = oof_surv[idx]
    if y_sg["event"].sum() < 5:
        return np.nan
    try:
        return float(integrated_brier_score(y_all, y_sg, s_sg, safe_times))
    except Exception:
        return np.nan


# ---------------------------------------------------------------------------
# Tabla de subgrupos
# ---------------------------------------------------------------------------

# Construye la tabla consolidada de metricas de rendimiento por subgrupo para un endpoint.
# Entrada: dataframe, array y, predicciones OOF de riesgo y supervivencia, tiempos, nombre del endpoint y logger.
# Salida: DataFrame con columnas Subgrupo, n, n_eventos, C-index, IC95% y IBS.
# Perspectiva de ciencia de datos: esta tabla es el instrumento central del análisis de robustez.
# Permite comparar el rendimiento del modelo global frente a cada subgrupo clinico y detectar
# grupos en los que el modelo discrimina peor o calibra de forma diferencial. La columna IBS
# complementa el C-index: un modelo puede discriminar bien (alto C-index) pero calibrar mal
# (alto IBS) en un subgrupo especifico. El logger registra cada fila en tiempo real para
# monitorizar el calculo de los 1000 bootstrap por subgrupo, que puede ser lento.
def compute_subgroup_table(
    df: pd.DataFrame,
    y_all: np.ndarray,
    oof_risk: np.ndarray,
    oof_surv: np.ndarray,
    safe_times: np.ndarray,
    ep_name: str,
    logger: logging.Logger,
) -> pd.DataFrame:
    sg = build_subgroups(df)
    rows = []
    for name, mask in sg.items():
        c, lo, hi, n, n_ev = subgroup_cindex(y_all, oof_risk, mask)
        ibs = subgroup_ibs(y_all, oof_surv, safe_times, mask)
        rows.append({
            "Subgrupo":    name,
            "n":           n,
            "n_eventos":   n_ev,
            "C_index":     round(c,   4) if not np.isnan(c)   else np.nan,
            "CI_lo":       round(lo,  4) if not np.isnan(lo)  else np.nan,
            "CI_hi":       round(hi,  4) if not np.isnan(hi)  else np.nan,
            "IBS":         round(ibs, 4) if not np.isnan(ibs) else np.nan,
        })
        logger.info("  %-55s n=%3d ev=%3d C=%.3f [%.3f,%.3f] IBS=%.3f",
                    name, n, n_ev,
                    c if not np.isnan(c) else -1,
                    lo if not np.isnan(lo) else -1,
                    hi if not np.isnan(hi) else -1,
                    ibs if not np.isnan(ibs) else -1)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Forest plot de subgrupos
# ---------------------------------------------------------------------------

# Genera el forest plot de C-index por subgrupo con IC95% bootstrap para OS y PFS.
# Entrada: diccionario {nombre_endpoint: DataFrame de subgrupos} con OS y PFS.
# Salida: objeto Figure de matplotlib con un panel unico y dos series de puntos/IC.
# Perspectiva de ciencia de datos: este forest plot traduce la tabla de subgrupos a una
# visualizacion que permite detectar de forma inmediata los subgrupos con rendimiento
# diferencial. Las lineas discontinuas verticales marcan el C-index global de cada endpoint,
# facilitando la comparacion visual. El offset vertical separa OS y PFS sin solapamiento.
# La linea punteada en C = 0.5 marca el umbral de modelo sin informacion pronostica.
# Un IC de subgrupo que no solapa con la linea del C-index global indica transferibilidad
# diferencial significativa (contexto descriptivo, no test formal de hipotesis).
# Nota oncologica: en la cohorte NESP, la comparacion NESP vs placebo en este grafico
# cuantifica la transferibilidad del modelo entre brazos con diferente perfil de hemoglobina.
def plot_forest_subgroups(
    tables: dict[str, pd.DataFrame],   # {"OS": df_os, "PFS": df_pfs}
) -> plt.Figure:
    _rc()
    ep_colors = {"OS": C_DARK, "PFS": C_AMBER}

    # Usar filas del primer endpoint como referencia para el orden
    ref_rows = next(iter(tables.values()))
    labels   = ref_rows["Subgrupo"].tolist()
    n_rows   = len(labels)
    y_pos    = np.arange(n_rows)

    fig, ax = plt.subplots(figsize=(12, max(6, n_rows * 0.52)))
    fig.suptitle("C-index por subgrupo - Cox PH (predicciones OOF)",
                 fontsize=13, fontweight="bold", color=C_DARK, y=1.01)

    offsets = {"OS": -0.15, "PFS": 0.15}
    for ep_name, df_sg in tables.items():
        c   = df_sg["C_index"].values
        lo  = df_sg["CI_lo"].values
        hi  = df_sg["CI_hi"].values
        col = ep_colors[ep_name]
        off = offsets[ep_name]

        # Dibujar IC95% bootstrap como segmentos horizontales y punto central por subgrupo
        for i in range(n_rows):
            if np.isnan(c[i]):
                continue
            ax.plot([lo[i], hi[i]], [y_pos[i] + off] * 2,
                    color=col, lw=2, alpha=0.7)
            ax.plot(c[i], y_pos[i] + off, "o",
                    color=col, ms=7, zorder=3, label=ep_name if i == 0 else "")

    # Lineas de referencia (C-index global por endpoint)
    for ep_name, df_sg in tables.items():
        global_c = df_sg.loc[df_sg["Subgrupo"] == "Global", "C_index"]
        if not global_c.empty and not np.isnan(global_c.iloc[0]):
            ax.axvline(global_c.iloc[0], color=ep_colors[ep_name],
                       ls="--", lw=1.2, alpha=0.5)

    ax.axvline(0.5, color="#CCCCCC", ls=":", lw=1)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.set_xlabel("C-index (IC95% bootstrap, n=1000)")
    ax.set_xlim(0.3, 0.9)
    ax.invert_yaxis()
    ax.legend(loc="lower right")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Análisis de errores por quintil de riesgo
# ---------------------------------------------------------------------------

# Genera el análisis de errores por percentil de riesgo predicho OOF (quintiles por defecto).
# Entrada: dataframe, array y, riesgo OOF, supervivencias OOF, tiempos seguros, nombre y etiqueta del endpoint.
# Salida: tupla (Figure con 2 paneles, DataFrame de estadisticas por quintil).
# Perspectiva de ciencia de datos: la clasificacion en quintiles de riesgo predicho permite
# evaluar si el modelo discrimina y calibra de forma monotona a lo largo del espectro de riesgo.
# Panel 1 (discriminacion): la tasa de evento observada debe crecer monotonamente del quintil 1
# al 5 si el modelo ordena correctamente a los sujetos por riesgo. Desviaciones de la monotonia
# indican grupos donde el modelo falla en la ordenacion relativa.
# Panel 2 (calibración): se compara la supervivencia media predicha OOF frente a la supervivencia
# observada por Kaplan-Meier en un tiempo de referencia (mediana de los tiempos de evento).
# Una brecha sistematica entre la curva predicha y la KM en alguno de los quintiles indica
# miscalibracion localizada, que no queda capturada por el IBS global.
# Nota oncologica: en quintiles de alto riesgo (Q4-Q5), la tasa de mortalidad observada suele
# ser elevada; si el modelo subestima el riesgo ahi, puede comprometer decisiones de seguimiento.
# Las asociaciones son descriptivas: la diferencia entre quintiles refleja la senal pronostica
# de las covariables basales, no un efecto causal del riesgo predicho sobre el desenlace.
def plot_error_by_risk(
    df: pd.DataFrame,
    y: np.ndarray,
    oof_risk: np.ndarray,
    safe_surv: np.ndarray,
    safe_times: np.ndarray,
    ep_name: str,
    ep_label: str,
) -> plt.Figure:
    _rc()

    # Clasificar sujetos en quintiles segun su riesgo predicho OOF: grupos de igual tamano aproximado
    q_labels = pd.qcut(oof_risk, N_QUINTILES, labels=False, duplicates="drop")
    q_labels = np.asarray(q_labels, dtype=float)
    n_q = int(np.nanmax(q_labels)) + 1

    # Tiempo de referencia: mediana de los tiempos de evento
    t_ref  = float(np.median(y["time"][y["event"]]))
    t_idx  = int(np.argmin(np.abs(safe_times - t_ref)))
    t_ref  = safe_times[t_idx]

    q_rows = []
    for q in range(n_q):
        mask = q_labels == q
        n_q_g  = int(mask.sum())
        ev_q   = y["event"][mask]
        ti_q   = y["time"][mask]
        risk_q = oof_risk[mask]

        # Tasa de evento observada: proporcion de sujetos con evento en el quintil (discriminacion)
        event_rate = float(ev_q.mean())

        # Supervivencia observada KM en t_ref: estimador no parametrico de referencia para calibración
        kmf = KaplanMeierFitter()
        kmf.fit(ti_q, event_observed=ev_q.astype(bool))
        km_at_t = float(kmf.survival_function_at_times([t_ref]).iloc[0])

        # Supervivencia media predicha OOF en t_ref: promedio de las curvas del Cox por quintil
        pred_surv = float(safe_surv[mask, t_idx].mean())

        # Riesgo medio predicho
        mean_risk = float(risk_q.mean())

        q_rows.append({
            "quintil": q + 1, "n": n_q_g,
            "n_eventos": int(ev_q.sum()),
            "event_rate_obs": event_rate,
            "km_surv_obs": km_at_t,
            "pred_surv_mean": pred_surv,
            "mean_risk": mean_risk,
        })
    tbl = pd.DataFrame(q_rows)

    # Figura: 2 paneles
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    fig.suptitle(
        f"Análisis de errores por quintil de riesgo - Cox PH - {ep_label}",
        fontsize=12, fontweight="bold", color=C_DARK,
    )

    # Panel 1: Tasa de evento observada por quintil
    ax = axes[0]
    ax.bar(tbl["quintil"], tbl["event_rate_obs"], color=C_DARK, alpha=0.85,
           label="Tasa evento observada")
    ax.axhline(y["event"].mean(), color=C_AMBER, ls="--", lw=1.5,
               label=f"Tasa global ({y['event'].mean():.2f})")
    ax.set_xlabel("Quintil de riesgo predicho (1 = menor riesgo)")
    ax.set_ylabel("Proporción de eventos observados")
    ax.set_title("Discriminación por quintil de riesgo")
    ax.set_xticks(tbl["quintil"])
    for _, row in tbl.iterrows():
        ax.text(row["quintil"], row["event_rate_obs"] + 0.005,
                f'n={int(row["n"])}', ha="center", va="bottom", fontsize=8)
    ax.legend()
    ax.set_ylim(0, 1)

    # Panel 2: S predicha vs S observada (KM) en t_ref
    ax2 = axes[1]
    ax2.scatter(tbl["quintil"], tbl["pred_surv_mean"],
                color=C_DARK, s=70, zorder=3, label=f"S predicha media (t={int(t_ref)}d)")
    ax2.scatter(tbl["quintil"], tbl["km_surv_obs"],
                color=C_AMBER, marker="^", s=70, zorder=3,
                label=f"S observada KM (t={int(t_ref)}d)")
    ax2.plot(tbl["quintil"], tbl["pred_surv_mean"], color=C_DARK, lw=1.2, alpha=0.6)
    ax2.plot(tbl["quintil"], tbl["km_surv_obs"],   color=C_AMBER, lw=1.2, alpha=0.6)
    ax2.set_xlabel("Quintil de riesgo predicho (1 = menor riesgo)")
    ax2.set_ylabel("Probabilidad de supervivencia")
    ax2.set_title(f"Calibración por quintil de riesgo (t = {int(t_ref)} días)")
    ax2.set_xticks(tbl["quintil"])
    ax2.legend()
    ax2.set_ylim(0, 1)

    fig.tight_layout()
    return fig, tbl


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Orquesta el pipeline completo de análisis de robustez del modelo Cox PH.
# Entrada: dataset CSV en output/. Salida: tablas CSV y figuras PNG en output/.
# Perspectiva de ciencia de datos: recupera las predicciones OOF generadas durante la
# validacion cruzada (collect_oof), calcula el rendimiento por subgrupo con bootstrap
# y genera el análisis de errores por quintil de riesgo para OS y PFS.
# La separacion entre el modulo de evaluacion global (eval_cox_final) y este modulo de
# robustez es deliberada: permite reutilizar las predicciones OOF sin reentrenar el modelo,
# garantizando coherencia con las metricas reportadas en la memoria.
def main() -> int:
    logger = setup_logger()
    np.random.seed(SEED)  # Fijacion de semilla global para reproducibilidad del entorno numpy

    if not DATASET_PATH.exists():
        logger.error("Dataset no encontrado: %s", DATASET_PATH)
        return 1
    df = pd.read_csv(DATASET_PATH)
    logger.info("Dataset: %d sujetos.", len(df))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    sg_tables: dict[str, pd.DataFrame] = {}

    for ep_name, ep_cfg in ENDPOINTS.items():
        event_col = ep_cfg["event"]
        time_col  = ep_cfg["time"]
        ep_label  = "OS (tiempo hasta muerte)" if ep_name == "OS" \
                    else "SLP (supervivencia libre de progresión)"

        logger.info("=== Robustez | Endpoint %s ===", ep_name)
        logger.info("  Recogiendo predicciones OOF...")
        oof = collect_oof(df, event_col, time_col)
        y_all     = oof["y"]
        oof_risk  = oof["oof_risk"]
        safe_surv = oof["safe_surv"]
        safe_times = oof["safe_times"]

        # Tabla de subgrupos
        logger.info("  Calculando C-index e IBS por subgrupo...")
        sg_df = compute_subgroup_table(
            df, y_all, oof_risk, safe_surv, safe_times, ep_name, logger)
        sg_path = OUTPUT_DIR / f"robustness_subgroups_{ep_name}.csv"
        sg_df.to_csv(sg_path, index=False)
        logger.info("  Guardado: %s", sg_path.name)
        sg_tables[ep_name] = sg_df

        # Análisis de errores por quintil
        fig_err, tbl_err = plot_error_by_risk(
            df, y_all, oof_risk, safe_surv, safe_times, ep_name, ep_label)
        err_fig_path = OUTPUT_DIR / f"fig_error_by_risk_{ep_name}.png"
        tbl_err_path = OUTPUT_DIR / f"error_by_risk_{ep_name}.csv"
        _save(fig_err, err_fig_path)
        tbl_err.to_csv(tbl_err_path, index=False)
        logger.info("  Guardado: %s  |  %s", err_fig_path.name, tbl_err_path.name)

    # Forest plot combinado (OS + PFS)
    fig_forest = plot_forest_subgroups(sg_tables)
    forest_path = OUTPUT_DIR / "fig_subgroup_cindex.png"
    _save(fig_forest, forest_path)
    logger.info("Guardado: %s", forest_path.name)
    logger.info("Análisis de robustez completo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
