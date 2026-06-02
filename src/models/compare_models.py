"""
src/models/compare_models.py

Proposito:
    Script principal que entrena los tres modelos de supervivencia (Cox, RSF, XGBoost),
    calcula C-index e IBS por endpoint y guarda la tabla comparativa en output/.

Entradas:
    output/nesp_nct00119613_dataset.csv

Salidas:
    output/model_comparison.csv      Tabla comparativa (una fila por modelo x endpoint)
    output/model_comparison_wide.csv Tabla ancha (una fila por modelo, columnas por endpoint)
    output/cox_baseline_metrics.json (si no existe, se genera)
    output/rsf_metrics.json          (si no existe, se genera)
    output/xgb_metrics.json          (si no existe, se genera)

Uso:
    python src/models/compare_models.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.cv_utils import SEED

OUTPUT_DIR   = PROJECT_ROOT / "output"
DATASET_PATH = OUTPUT_DIR / "nesp_nct00119613_dataset.csv"

COX_JSON = OUTPUT_DIR / "cox_baseline_metrics.json"
RSF_JSON = OUTPUT_DIR / "rsf_metrics.json"
XGB_JSON = OUTPUT_DIR / "xgb_metrics.json"


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

# Configura y devuelve el logger del modulo de comparacion con formato de hora y nivel.
# Entrada: ninguna. Salida: instancia de logging.Logger lista para usar.
# Permite auditar el flujo de carga o generacion de resultados de cada modelo
# sin alterar la logica de calculo ni los datos.
def setup_logger() -> logging.Logger:
    logger = logging.getLogger("compare_models")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(message)s", "%H:%M:%S"))
        logger.addHandler(sh)
    return logger


# ---------------------------------------------------------------------------
# Cargar o generar resultados de cada modelo
# ---------------------------------------------------------------------------

# Carga los resultados del modelo Cox desde COX_JSON si ya existen,
# o los genera ejecutando run_endpoint() de cox_baseline para OS y PFS.
# Entrada: dataset derivado df y logger. Salida: diccionario con resultados
#   por endpoint {"OS": {...}, "PFS": {...}} en el formato de cox_baseline.
# Estrategia de cache: evita repetir el entrenamiento cuando el JSON existe,
# lo que es relevante dado el coste computacional del bootstrap n=1000.
# La generacion en demanda aplica el mismo esquema CV k=5 y anti-fuga que el baseline.
def load_or_run_cox(df: pd.DataFrame, logger: logging.Logger) -> dict:
    if COX_JSON.exists():
        logger.info("Cox: cargando resultados existentes de %s", COX_JSON.name)
        with open(COX_JSON, encoding="utf-8") as fh:
            return json.load(fh)
    logger.info("Cox: ejecutando cox_baseline...")
    from src.models.cox_baseline import run_endpoint, setup_logger as sl
    log_cox = sl()
    results = {}
    for ep, cfg in {"OS": {"event": "DTH", "time": "DTHDY"},
                    "PFS": {"event": "PFSCD", "time": "PFSDY"}}.items():
        results[ep] = run_endpoint(df, ep, cfg["event"], cfg["time"], log_cox)
    with open(COX_JSON, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    return results


# Carga los resultados del modelo Random Survival Forest desde RSF_JSON si ya existen,
# o los genera ejecutando run_endpoint() de rsf_model para OS y PFS.
# Entrada: dataset derivado df y logger. Salida: diccionario con resultados
#   por endpoint en el mismo formato que Cox (CV k=5, bootstrap n=1000).
# El RSF es un modelo de referencia no lineal basado en arboles de decision
# adaptados a datos de supervivencia con censura, mas flexible que Cox.
# La estrategia de cache evita reentrenar cuando los resultados ya estan en disco.
def load_or_run_rsf(df: pd.DataFrame, logger: logging.Logger) -> dict:
    if RSF_JSON.exists():
        logger.info("RSF: cargando resultados existentes de %s", RSF_JSON.name)
        with open(RSF_JSON, encoding="utf-8") as fh:
            return json.load(fh)
    logger.info("RSF: ejecutando rsf_model...")
    from src.models.rsf_model import run_endpoint, setup_logger as sl
    log_rsf = sl("rsf_model")
    results = {}
    for ep, cfg in {"OS": {"event": "DTH", "time": "DTHDY"},
                    "PFS": {"event": "PFSCD", "time": "PFSDY"}}.items():
        results[ep] = run_endpoint(df, ep, cfg["event"], cfg["time"], log_rsf)
    with open(RSF_JSON, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    return results


# Carga los resultados del modelo XGBoost con perdida de supervivencia desde
# XGB_JSON si ya existen, o los genera ejecutando run_endpoint() de xgb_model.
# Entrada: dataset derivado df y logger. Salida: diccionario con resultados
#   por endpoint (OS y PFS) en el mismo formato que Cox y RSF.
# XGBoost con perdida de supervivencia (AFT o Cox partial likelihood) es el
# modelo de mayor capacidad del proyecto; se compara contra el baseline Cox
# y el RSF aplicando el criterio a priori: C-index + IBS + CV% de estabilidad.
def load_or_run_xgb(df: pd.DataFrame, logger: logging.Logger) -> dict:
    if XGB_JSON.exists():
        logger.info("XGBoost: cargando resultados existentes de %s", XGB_JSON.name)
        with open(XGB_JSON, encoding="utf-8") as fh:
            return json.load(fh)
    logger.info("XGBoost: ejecutando xgb_model...")
    from src.models.xgb_model import run_endpoint, setup_logger as sl
    log_xgb = sl("xgb_model")
    results = {}
    for ep, cfg in {"OS": {"event": "DTH", "time": "DTHDY"},
                    "PFS": {"event": "PFSCD", "time": "PFSDY"}}.items():
        results[ep] = run_endpoint(df, ep, cfg["event"], cfg["time"], log_xgb)
    with open(XGB_JSON, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    return results


# ---------------------------------------------------------------------------
# Construir tabla comparativa
# ---------------------------------------------------------------------------

# Construye la tabla comparativa de los tres modelos en formato largo
# (una fila por modelo x endpoint), con las metricas CV y bootstrap.
# Entrada: diccionarios de resultados de Cox, RSF y XGBoost (mismo formato).
# Salida: DataFrame con columnas de C-index y IBS (media, std, CV%, boot IC95%)
#   para los endpoints OS y PFS.
# La tabla es el artefacto principal de la comparacion: permite aplicar el
# criterio de seleccion a priori (mayor C-index, menor IBS, menor CV%)
# registrado en decision_log.md para identificar el modelo final del proyecto.
def build_table(cox: dict, rsf: dict, xgb: dict) -> pd.DataFrame:
    rows = []
    for ep in ("OS", "PFS"):
        for model_name, results in [("Cox PH", cox), ("RSF", rsf), ("XGBoost", xgb)]:
            res = results[ep]
            cv_c = res["cv"]["c_index"]
            cv_i = res["cv"]["ibs"]
            bt_c = res["bootstrap"]["c_index"]
            bt_i = res["bootstrap"]["ibs"]
            rows.append({
                "Modelo":         model_name,
                "Endpoint":       ep,
                "Eventos":        res["n_events"],
                "Censurados":     res["n_censored"],
                "CV_Cindex_mean": round(cv_c["mean"], 4),
                "CV_Cindex_std":  round(cv_c["std"],  4),
                "CV_Cindex_pct":  cv_c.get("cv_pct"),
                "CV_IBS_mean":    round(cv_i["mean"], 4),
                "CV_IBS_std":     round(cv_i["std"],  4),
                "CV_IBS_pct":     cv_i.get("cv_pct"),
                "Boot_Cindex":    round(bt_c["mean"], 4),
                "Boot_Cindex_lo": round(bt_c["ci_low"],  4),
                "Boot_Cindex_hi": round(bt_c["ci_high"], 4),
                "Boot_IBS":       round(bt_i["mean"], 4),
                "Boot_IBS_lo":    round(bt_i["ci_low"],  4),
                "Boot_IBS_hi":    round(bt_i["ci_high"], 4),
            })
    return pd.DataFrame(rows)


# Imprime en consola la tabla comparativa con formato alineado por columnas,
# agrupada por endpoint (OS y PFS), con C-index y IBS del CV y bootstrap.
# Entrada: DataFrame generado por build_table().
# Salida: ninguna (impresion a stdout).
# Facilita la revision rapida de resultados y la transcripcion a la memoria D3
# sin necesidad de abrir los ficheros CSV.
def print_table(df: pd.DataFrame) -> None:
    sep = "=" * 88
    print(f"\n{sep}")
    print("  TABLA COMPARATIVA DE MODELOS DE SUPERVIVENCIA  -  NESP NCT00119613")
    print(sep)
    for ep in ("OS", "PFS"):
        sub = df[df["Endpoint"] == ep]
        n_ev  = sub.iloc[0]["Eventos"]
        n_cen = sub.iloc[0]["Censurados"]
        print(f"\n  Endpoint {ep}  (eventos={n_ev}, censurados={n_cen})")
        print(f"  {'Modelo':<12}  {'C-index CV':>12}  {'CV%':>5}  "
              f"{'IBS CV':>10}  {'CV%':>5}  "
              f"{'Boot C-idx':>12}  {'IC95%':>20}  "
              f"{'Boot IBS':>10}  {'IC95%':>18}")
        print("  " + "-" * 84)
        for _, row in sub.iterrows():
            c_ci = f"[{row['Boot_Cindex_lo']:.4f}, {row['Boot_Cindex_hi']:.4f}]"
            i_ci = f"[{row['Boot_IBS_lo']:.4f}, {row['Boot_IBS_hi']:.4f}]"
            print(
                f"  {row['Modelo']:<12}  "
                f"{row['CV_Cindex_mean']:.4f}+/-{row['CV_Cindex_std']:.4f}  "
                f"{row['CV_Cindex_pct']:>4.1f}%  "
                f"{row['CV_IBS_mean']:.4f}+/-{row['CV_IBS_std']:.4f}  "
                f"{row['CV_IBS_pct']:>4.1f}%  "
                f"{row['Boot_Cindex']:.4f}       "
                f"{c_ci:<22}  "
                f"{row['Boot_IBS']:.4f}   "
                f"{i_ci}"
            )
    print(f"\n{sep}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Punto de entrada del script de comparacion de modelos.
# Lee el dataset derivado, carga o genera los resultados de Cox, RSF y XGBoost,
# construye la tabla comparativa en formato largo y ancho, la persiste en CSV
# y aplica el criterio de seleccion a priori para identificar el mejor modelo
# por endpoint segun C-index, IBS y coeficiente de variacion entre folds.
# Entrada: ninguna (usa constantes del modulo).
# Salida: 0 si exito, 1 si el dataset no existe.
def main() -> int:
    logger = setup_logger()
    np.random.seed(SEED)  # semilla global para reproducibilidad de numpy

    if not DATASET_PATH.exists():
        logger.error("Dataset no encontrado: %s. Ejecuta el ETL primero.", DATASET_PATH)
        return 1

    df = pd.read_csv(DATASET_PATH)
    logger.info("Dataset: %d sujetos.", len(df))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cox_results = load_or_run_cox(df, logger)
    rsf_results = load_or_run_rsf(df, logger)
    xgb_results = load_or_run_xgb(df, logger)

    table = build_table(cox_results, rsf_results, xgb_results)

    # Tabla larga (una fila por modelo x endpoint)
    long_path = OUTPUT_DIR / "model_comparison.csv"
    table.to_csv(long_path, index=False, encoding="utf-8")
    logger.info("Guardado: %s", long_path.name)

    # Tabla ancha (una fila por modelo)
    wide = table.pivot_table(
        index="Modelo",
        columns="Endpoint",
        values=["CV_Cindex_mean", "CV_Cindex_std", "CV_IBS_mean", "CV_IBS_std",
                "Boot_Cindex", "Boot_Cindex_lo", "Boot_Cindex_hi",
                "Boot_IBS", "Boot_IBS_lo", "Boot_IBS_hi"],
        aggfunc="first",
    )
    wide.columns = ["_".join(col).strip() for col in wide.columns]
    wide_path = OUTPUT_DIR / "model_comparison_wide.csv"
    wide.to_csv(wide_path, encoding="utf-8")
    logger.info("Guardado: %s", wide_path.name)

    print_table(table)

    # Seleccion de modelo segun criterio a priori (decision_log.md):
    # C-index + IBS + CV% de estabilidad.
    print("  CRITERIO DE SELECCION (a priori): mayor C-index, menor IBS, menor CV%")
    print()
    for ep in ("OS", "PFS"):
        sub = table[table["Endpoint"] == ep].copy()
        # Score compuesto: C-index / CV_Cindex_pct - IBS (normalizado por rango)
        sub = sub.assign(
            score=sub["CV_Cindex_mean"] - 0.1 * sub["CV_Cindex_pct"] / 100 - sub["CV_IBS_mean"]
        )
        best = sub.sort_values("score", ascending=False).iloc[0]["Modelo"]
        print(f"  Endpoint {ep}: modelo con mejor equilibrio -> {best}")
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
