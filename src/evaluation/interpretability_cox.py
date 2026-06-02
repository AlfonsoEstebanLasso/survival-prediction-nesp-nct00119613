"""
src/evaluation/interpretability_cox.py

Proposito:
    Interpretabilidad del modelo final Cox PH sobre OS y PFS.

    1. Tabla de Hazard Ratios (HR) con IC95% y p-valores, ajustados sobre el dataset
       completo con las variables en su escala original (las HR del modelo predictivo
       usan estandarizacion interna, pero se reportan en escala natural para interpretacion
       clinica). CADIAGM y B_HGB con imputacion por mediana de los 4 valores faltantes.

    2. Forest plot de HRs con escala logarítmica y referencia en HR = 1.

    3. Test de proporcionalidad de riesgos de Schoenfeld (estadistico rho, p-valor global
       y por variable). Si p < 0.05 se documenta la desviacion del supuesto PH.

    4. Graficos de residuos de Schoenfeld escalados frente al tiempo de supervivencia
       (suavizados con media movil) para inspection visual del supuesto PH.

Entradas:
    output/nesp_nct00119613_dataset.csv

Salidas (en output/):
    cox_hazard_ratios.csv          Tabla de HR con IC95% y p-valor
    fig_forest_plot.png            Forest plot de HRs (OS y PFS en paneles)
    cox_schoenfeld_test.csv        Resultados del test PH por variable
    fig_schoenfeld_residuals.png   Residuos de Schoenfeld frente al tiempo
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from lifelines.statistics import proportional_hazard_test

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

warnings.filterwarnings("ignore")

DATASET_PATH = PROJECT_ROOT / "output" / "nesp_nct00119613_dataset.csv"
OUTPUT_DIR   = PROJECT_ROOT / "output"
SEED         = 42

C_DARK  = "#1F4E79"
C_LIGHT = "#D5E8F0"
C_AMBER = "#B7791F"
C_GREEN = "#1F7A3A"
C_RED   = "#C0392B"
C_GRAY  = "#888888"

ENDPOINTS = {
    "OS":  {"event": "DTH",   "time": "DTHDY",  "label": "OS"},
    "PFS": {"event": "PFSCD", "time": "PFSDY",  "label": "SLP"},
}

# Nombres de display para el forest plot
DISPLAY_NAMES = {
    "AGE":         "Edad (por ano)",
    "B_WEIGHT":    "Peso basal (por kg)",
    "CADIAGM":     "Tiempo desde diag. (por mes)",
    "B_HGB":       "Hemoglobina basal (por g/dL)",
    "MEDHX_N":     "N. sistemas comorbilidad (por unidad)",
    "SEXCD_1.0":   "Sexo = 1 vs 0",
    "B_ECOGN_2.0": "B_ECOGN = 2 vs 1 (referencia)",
}


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

# Inicializa el logger del modulo con formato de hora, nivel y mensaje.
# Entrada: ninguna. Salida: objeto Logger configurado con StreamHandler a stdout.
# Permite registrar el progreso del análisis de interpretabilidad en consola.
def setup_logger() -> logging.Logger:
    logger = logging.getLogger("interpretability")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(message)s", "%H:%M:%S"))
        logger.addHandler(sh)
    return logger


# Establece parametros globales de estilo para matplotlib.
# Entrada: ninguna. Salida: ninguna (efecto colateral sobre plt.rcParams).
# Garantiza consistencia visual (fuente Arial, grilla suave, sin espinas superior/derecha)
# en todos los graficos del modulo.
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
# Salida: ninguna. El cierre evita acumulacion de figuras abiertas en procesos largos.
def _save(fig, path, dpi=300):
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Preparacion del dataset para lifelines
# ---------------------------------------------------------------------------

# Prepara el dataframe de entrada para el ajuste del modelo Cox con lifelines.
# Entrada: dataframe completo, nombre de la columna de evento y nombre de la columna de tiempo.
# Salida: subconjunto con covariables en escala original, imputacion por mediana y dummies.
# Perspectiva de ciencia de datos: se trabaja en escala natural (no estandarizada) para que
# los coeficientes del Cox sean interpretables directamente como log-HR por unidad de la
# covariable. La imputacion por mediana de CADIAGM y B_HGB (4 valores faltantes) es
# conservadora y coherente con el patron MCAR/MAR de baja proporcion de missingness.
# La codificacion dummy con drop_first=True evita la trampa de la variable indicadora:
# B_ECOGN_2.0 contrasta ECOG 2 frente a ECOG 1 (referencia), con importancia oncologica
# clara ya que ECOG 2 implica mayor limitacion funcional y peor pronostico esperado.
def prepare_lifelines_df(
    df: pd.DataFrame, event_col: str, time_col: str,
) -> pd.DataFrame:
    """
    Dataset en escala original para lifelines CoxPHFitter.
    Imputacion por mediana de los 4 valores faltantes.
    B_ECOGN y SEXCD codificados como dummies (drop_first=True).
    """
    num_cols = ["AGE", "B_WEIGHT", "CADIAGM", "B_HGB", "MEDHX_N"]
    cat_cols = ["SEXCD", "B_ECOGN"]

    sub = df[num_cols + cat_cols + [event_col, time_col]].copy()
    for col in num_cols:
        sub[col] = sub[col].fillna(sub[col].median())

    # Codificacion categorica: SEXCD y B_ECOGN como dummies (primera = referencia)
    sub = pd.get_dummies(sub, columns=cat_cols, drop_first=True)

    # Asegurarse de que los dummies sean float
    dummy_cols = [c for c in sub.columns if c.startswith(("SEXCD_", "B_ECOGN_"))]
    for c in dummy_cols:
        sub[c] = sub[c].astype(float)

    return sub


# ---------------------------------------------------------------------------
# Ajuste Cox con lifelines
# ---------------------------------------------------------------------------

# Ajusta el modelo Cox proporcional completo sobre todo el dataset con lifelines.
# Entrada: dataframe preparado (covariables + tiempo + evento), nombres de columnas.
# Salida: objeto CoxPHFitter ajustado con coeficientes, IC95% y p-valores.
# Perspectiva de ciencia de datos: el ajuste sobre el conjunto completo (sin particion)
# sirve exclusivamente para la interpretabilidad descriptiva (HR e IC95%): las metricas
# predictivas (C-index, IBS) se calculan mediante validacion cruzada OOF en otros modulos.
# El penalizador se fija a 0.0 para obtener estimaciones MLE sin contraccion, adecuadas
# para la lectura de asociaciones. Las asociaciones obtenidas son descriptivas, no causales:
# el diseno observacional y el ajuste incompleto de confusores impiden inferencia causal.
# Nota oncologica: en cohortes de quimioterapia con n = 479, la ausencia de penalizador
# es razonable dada la dimension reducida (7 covariables) y la proporcion de eventos.
def fit_lifelines_cox(
    df_lf: pd.DataFrame, event_col: str, time_col: str,
) -> CoxPHFitter:
    cph = CoxPHFitter(penalizer=0.0)  # Sin regularizacion: estimacion MLE pura para interpretabilidad
    cph.fit(df_lf, duration_col=time_col, event_col=event_col, show_progress=False)
    return cph


# ---------------------------------------------------------------------------
# Tabla de HRs
# ---------------------------------------------------------------------------

# Construye la tabla de Hazard Ratios con IC95% y p-valores a partir del resumen de lifelines.
# Entrada: objeto CoxPHFitter ajustado, nombre del endpoint.
# Salida: DataFrame con columnas log_HR, HR, IC95% inferior y superior, p-valor y significacion.
# Perspectiva de ciencia de datos: exp(coef) es el HR, que cuantifica la asociacion descriptiva
# (no causal) entre cada covariable y el riesgo instantaneo de evento. Un HR > 1 indica mayor
# tasa de riesgo; HR < 1 indica efecto protector en sentido descriptivo. Los IC95% se obtienen
# directamente de la aproximacion asintotica de Wald del Cox: covariables con IC que no cruzan 1
# se consideran estadisticamente significativas. La columna 'sig' facilita la lectura en tablas
# de la memoria. Nota oncologica: en esta cohorte, MEDHX_N (numero de sistemas con comorbilidad)
# captura carga de enfermedad previa y puede asociarse a mayor riesgo basal de mortalidad.
def build_hr_table(cph: CoxPHFitter, ep_name: str) -> pd.DataFrame:
    s = cph.summary.copy()
    s = s[["coef", "exp(coef)", "exp(coef) lower 95%", "exp(coef) upper 95%", "p"]].copy()
    s.columns = ["log_HR", "HR", "HR_CI_lo", "HR_CI_hi", "p_valor"]  # Renombrado para claridad: exp(coef) = HR
    s["endpoint"]     = ep_name
    s["variable"]     = s.index
    s["display_name"] = s["variable"].map(lambda v: DISPLAY_NAMES.get(v, v))
    s = s.reset_index(drop=True)
    # Significacion
    s["sig"] = s["p_valor"].apply(
        lambda p: "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else "ns"))
    )
    return s[["endpoint","variable","display_name","log_HR","HR","HR_CI_lo","HR_CI_hi","p_valor","sig"]]


# ---------------------------------------------------------------------------
# Forest plot de HRs
# ---------------------------------------------------------------------------

# Genera el forest plot de Hazard Ratios para todos los endpoints en un unico grafico.
# Entrada: diccionario {nombre_endpoint: DataFrame de HR} con OS y PFS.
# Salida: objeto Figure de matplotlib con un panel unico y dos series de puntos/IC.
# Perspectiva de ciencia de datos: el forest plot en escala logarítmica es el estandar
# para comunicar HR con IC95% en análisis de supervivencia multivariante. La escala log
# simetriza la representacion de efectos protectores (HR < 1) y de riesgo (HR > 1) respecto
# a la linea de referencia HR = 1 (ausencia de asociacion). El desplazamiento vertical (offset)
# entre OS y PFS permite comparar ambos endpoints sin solapamiento de puntos. Las estrellas
# de significacion marcan las asociaciones mas robustas. La lectura es descriptiva, no causal.
# Nota oncologica: la comparacion visual entre OS y PFS permite detectar si una covariable
# como B_ECOGN o MEDHX_N tiene efecto diferencial sobre mortalidad frente a progresion.
def plot_forest_hr(
    hr_tables: dict[str, pd.DataFrame],
) -> plt.Figure:
    _rc()
    ep_list   = list(hr_tables.keys())
    n_ep      = len(ep_list)
    ep_colors = {"OS": C_DARK, "PFS": C_AMBER}
    offsets   = {"OS": -0.15, "PFS": 0.15}

    # Variables en comun
    vars_ordered = list(hr_tables[ep_list[0]]["display_name"])
    n_vars = len(vars_ordered)
    y_pos  = np.arange(n_vars)

    fig, ax = plt.subplots(figsize=(10, max(5, n_vars * 0.65)))
    fig.suptitle("Hazard Ratios - Cox PH (escala original, IC95%)",
                 fontsize=13, fontweight="bold", color=C_DARK, y=1.01)

    for ep_name, hr_df in hr_tables.items():
        col = ep_colors[ep_name]
        off = offsets[ep_name]
        for i, var in enumerate(hr_df["display_name"]):
            row = hr_df[hr_df["display_name"] == var].iloc[0]
            hr, lo, hi = row["HR"], row["HR_CI_lo"], row["HR_CI_hi"]
            if np.isnan(hr):
                continue
            # Clip extremos para visualizacion: IC muy amplios se truncan para mantener escala legible
            lo_plot = max(lo, 0.05)
            hi_plot = min(hi, 20.0)
            ax.plot([lo_plot, hi_plot], [y_pos[i] + off] * 2,
                    color=col, lw=2.2, alpha=0.75)
            ax.plot(hr, y_pos[i] + off, "o", color=col, ms=7, zorder=3,
                    label=ep_name if i == 0 else "")
            # p-valor significativo: poner estrella
            if row["p_valor"] < 0.05:
                ax.text(hi_plot * 1.05, y_pos[i] + off,
                        row["sig"], color=col, fontsize=9, va="center")

    ax.axvline(1.0, color="#AAAAAA", ls="--", lw=1.3)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(mticker.ScalarFormatter())
    ax.xaxis.set_minor_formatter(mticker.NullFormatter())
    ax.set_xticks([0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0, 5.0])
    ax.set_yticks(y_pos)
    ax.set_yticklabels(vars_ordered, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Hazard Ratio (escala logarítmica)")
    ax.legend(loc="lower right")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Test de Schoenfeld y residuos
# ---------------------------------------------------------------------------

# Ejecuta el test de proporcionalidad de riesgos de Schoenfeld variable a variable.
# Entrada: CoxPHFitter ajustado, dataframe lifelines, nombre del endpoint.
# Salida: DataFrame con estadistico rho, p-valor y flag de cumplimiento por covariable.
# Perspectiva de ciencia de datos: el test de Schoenfeld contrasta la hipotesis nula de
# proporcionalidad (HR constante en el tiempo). La transformacion "rank" del tiempo es
# la opcion mas robusta ante distribucion temporal asimetrica. Un p < 0.05 indica que el HR
# de esa covariable varia a lo largo del seguimiento, lo que invalida la interpretacion
# de un unico HR constante y puede requerir estratificacion o inclusion de interaccion
# tiempo-covariable. El flag 'supuesto_ok' (p > 0.05) facilita la clasificacion automatica
# de covariables que cumplen o violan el supuesto PH en la tabla de la memoria.
def run_schoenfeld_test(
    cph: CoxPHFitter, df_lf: pd.DataFrame, ep_name: str,
) -> pd.DataFrame:
    """Ejecuta el test de proporcionalidad y devuelve una tabla de resultados."""
    try:
        result = proportional_hazard_test(cph, df_lf, time_transform="rank")  # Transformacion rank: robusta ante asimetria temporal
        tbl = result.summary.copy()
        tbl["endpoint"] = ep_name
        tbl["variable"] = tbl.index
        tbl = tbl.reset_index(drop=True)
        tbl["display_name"] = tbl["variable"].map(
            lambda v: DISPLAY_NAMES.get(v, v))
        tbl["supuesto_ok"] = tbl["p"] > 0.05
        return tbl[["endpoint","variable","display_name","test_statistic","p","supuesto_ok"]]
    except Exception as exc:
        return pd.DataFrame({"error": [str(exc)]})


# Genera el grafico de residuos de Schoenfeld escalados frente al tiempo para cada covariable.
# Entrada: CoxPHFitter ajustado, dataframe lifelines, nombre e identificador del endpoint.
# Salida: objeto Figure con un panel por covariable (dispuesto en rejilla de hasta 3 columnas).
# Perspectiva de ciencia de datos: los residuos de Schoenfeld escalados deben distribuirse
# aleatoriamente alrededor de cero a lo largo del tiempo si el supuesto PH se cumple. Una
# tendencia sistematica (curva suavizada con pendiente no nula) evidencia variacion del HR
# en el tiempo. La media movil (ventana = 10% de los eventos) suaviza el ruido puntual sin
# introducir sesgo de frontera excesivo, facilitando la inspeccion visual del patron temporal.
# Esta inspeccion complementa el test formal de Schoenfeld y es especialmente util para
# detectar efectos que se diluyen a largo plazo, comunes en ensayos de soporte oncologico
# donde el beneficio del NESP sobre hemoglobina puede atenuarse conforme avanza la enfermedad.
def plot_schoenfeld(
    cph: CoxPHFitter,
    df_lf: pd.DataFrame,
    ep_name: str,
    ep_label: str,
) -> plt.Figure:
    """Residuos de Schoenfeld escalados frente al tiempo de supervivencia."""
    _rc()
    try:
        schoen = cph.compute_residuals(df_lf, kind="schoenfeld")
    except Exception:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "Residuos no disponibles",
                ha="center", va="center", transform=ax.transAxes)
        return fig

    event_col = [c for c in df_lf.columns
                 if c not in cph.params_.index.tolist() and df_lf[c].max() <= 1
                 and df_lf[c].dtype == float][0] if False else None

    # Tiempo de cada evento (las filas de schoen corresponden a eventos)
    vars_plot = [c for c in schoen.columns if c in cph.params_.index]
    n_vars = len(vars_plot)
    n_cols = min(3, n_vars)
    n_rows = int(np.ceil(n_vars / n_cols))

    fig, axes = plt.subplots(n_rows, n_cols,
                             figsize=(5 * n_cols, 3.5 * n_rows),
                             squeeze=False)
    fig.suptitle(
        f"Residuos de Schoenfeld - Cox PH - {ep_label}\n"
        "(curva plana = supuesto de proporcionalidad cumplido)",
        fontsize=11, fontweight="bold", color=C_DARK,
    )

    event_times = schoen.index.values  # el indice son los tiempos de los eventos

    for idx, var in enumerate(vars_plot):
        row_i = idx // n_cols
        col_i = idx % n_cols
        ax = axes[row_i][col_i]
        res = schoen[var].values

        ax.scatter(event_times, res, color=C_LIGHT, s=18, alpha=0.6, zorder=2)

        # Suavizado con media movil: ventana adaptativa al 10% de eventos, minimo 5 puntos
        w = max(5, len(res) // 10)
        smoothed = pd.Series(res).rolling(w, center=True, min_periods=1).mean().values
        ax.plot(event_times, smoothed, color=C_DARK, lw=2, zorder=3,
                label="Media movil")
        ax.axhline(0, color="#AAAAAA", ls="--", lw=1)

        dname = DISPLAY_NAMES.get(var, var)
        ax.set_title(dname, fontsize=9, color=C_DARK)
        ax.set_xlabel("Tiempo (días)", fontsize=8)
        ax.set_ylabel("Residuo Schoenfeld", fontsize=8)

    # Ocultar subplots vacios
    for idx in range(n_vars, n_rows * n_cols):
        axes[idx // n_cols][idx % n_cols].set_visible(False)

    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Orquesta el pipeline completo de interpretabilidad del modelo Cox PH.
# Entrada: dataset CSV en output/. Salida: tablas CSV y figuras PNG en output/.
# Perspectiva de ciencia de datos: ejecuta en orden la preparacion, ajuste, extraccion
# de HR con IC95%, test de Schoenfeld, graficos de residuos y forest plot para OS y PFS.
# La separacion entre la interpretabilidad (ajuste completo, escala natural) y la evaluacion
# predictiva (CV-OOF, escala estandarizada) es deliberada: evita confundir la lectura
# descriptiva de asociaciones con la capacidad discriminativa del modelo.
# La semilla SEED = 42 se fija aqui aunque la funcion no tenga componente estocastico,
# por coherencia con el resto del pipeline y reproducibilidad de entorno numpy.
def main() -> int:
    logger = setup_logger()
    np.random.seed(SEED)  # Fijacion de semilla para reproducibilidad del entorno numpy

    if not DATASET_PATH.exists():
        logger.error("Dataset no encontrado: %s", DATASET_PATH)
        return 1
    df = pd.read_csv(DATASET_PATH)
    logger.info("Dataset: %d sujetos.", len(df))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_hr_tables:   dict[str, pd.DataFrame] = {}
    all_schoen_rows: list[pd.DataFrame]      = []

    for ep_name, ep_cfg in ENDPOINTS.items():
        event_col = ep_cfg["event"]
        time_col  = ep_cfg["time"]
        ep_label  = ep_cfg["label"]

        logger.info("=== Interpretabilidad | Endpoint %s ===", ep_name)

        df_lf = prepare_lifelines_df(df, event_col, time_col)
        cph   = fit_lifelines_cox(df_lf, event_col, time_col)

        # HR tabla
        hr_df = build_hr_table(cph, ep_name)
        all_hr_tables[ep_name] = hr_df
        logger.info("  Hazard Ratios:")
        for _, row in hr_df.iterrows():
            logger.info("    %-40s HR=%.3f [%.3f, %.3f]  p=%.4f %s",
                        row["display_name"], row["HR"],
                        row["HR_CI_lo"], row["HR_CI_hi"],
                        row["p_valor"], row["sig"])

        # Schoenfeld test
        logger.info("  Test de proporcionalidad de Schoenfeld...")
        schoen_tbl = run_schoenfeld_test(cph, df_lf, ep_name)
        all_schoen_rows.append(schoen_tbl)
        if "p" in schoen_tbl.columns:
            for _, row in schoen_tbl.iterrows():
                ok = "OK" if row["supuesto_ok"] else "DESVIACION"
                logger.info("    %-40s p=%.4f  %s",
                            row.get("display_name", row.get("variable","")),
                            row["p"], ok)

        # Residuos de Schoenfeld
        fig_sch = plot_schoenfeld(cph, df_lf, ep_name, ep_label)
        sch_path = OUTPUT_DIR / f"fig_schoenfeld_{ep_name}.png"
        _save(fig_sch, sch_path)
        logger.info("  Guardado: %s", sch_path.name)

    # Guardar tabla HR combinada
    hr_all = pd.concat(all_hr_tables.values(), ignore_index=True)
    hr_path = OUTPUT_DIR / "cox_hazard_ratios.csv"
    hr_all.to_csv(hr_path, index=False)
    logger.info("Guardado: %s", hr_path.name)

    # Guardar tabla Schoenfeld combinada
    sch_all = pd.concat(all_schoen_rows, ignore_index=True)
    sch_csv = OUTPUT_DIR / "cox_schoenfeld_test.csv"
    sch_all.to_csv(sch_csv, index=False)
    logger.info("Guardado: %s", sch_csv.name)

    # Forest plot HR (OS + PFS en el mismo grafico)
    _rc()
    fig_forest = plot_forest_hr(all_hr_tables)
    forest_path = OUTPUT_DIR / "fig_forest_plot.png"
    _save(fig_forest, forest_path)
    logger.info("Guardado: %s", forest_path.name)

    # Resumen en consola
    print("\n" + "=" * 70)
    print("  HAZARD RATIOS - COX PH (escala original, IC95%)")
    print("=" * 70)
    for ep_name, hr_df in all_hr_tables.items():
        print(f"\n  Endpoint {ep_name}:")
        for _, r in hr_df.iterrows():
            print(f"    {r['display_name']:<38}  "
                  f"HR={r['HR']:.3f}  [{r['HR_CI_lo']:.3f}, {r['HR_CI_hi']:.3f}]  "
                  f"p={r['p_valor']:.4f} {r['sig']}")

    if "p" in sch_all.columns:
        print("\n" + "=" * 70)
        print("  TEST DE PROPORCIONALIDAD DE SCHOENFELD")
        print("=" * 70)
        for _, r in sch_all.iterrows():
            ok = "OK" if r["supuesto_ok"] else "DESVIACION (p<0.05)"
            print(f"    [{r['endpoint']}] {r.get('display_name',''):<38}  "
                  f"p={r['p']:.4f}  {ok}")
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
