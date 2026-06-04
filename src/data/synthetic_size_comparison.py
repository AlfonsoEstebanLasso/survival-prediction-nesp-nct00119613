"""
src/data/synthetic_size_comparison.py

Proposito:
    Comparativa del estudio de tamano muestral de los datos sintéticos. Reune las metricas de
    los generadores CTGAN y TVAE (sin filtro) y de TVAE con filtro de privacidad por DCR a tres
    tamanos crecientes (n=1000, 2500, 5000), y produce una tabla y una figura comparativas.
    El objetivo es identificar la configuracion que satisface SIMULTANEAMENTE los tres criterios
    de reidentificación preregistrados (k-anonimidad, membership inference y DCR) sin perder
    utilidad, resolviendo la tension utilidad-privacidad documentada en la memoria.

ADVERTENCIA: Los datos sintéticos son exclusivamente para prototipado metodologico. No
    representan pacientes reales y no deben usarse con fines clinicos ni epidemiologicos.

Entradas (en output/):
    synthetic_metrics.json                 (CTGAN, n=478, sin filtro)
    synthetic_metrics_tvae.json            (TVAE, n=478, sin filtro)
    synthetic_metrics_tvae_dcr_n1000.json  (TVAE + filtro DCR, n=1000)
    synthetic_metrics_tvae_dcr_n2500.json  (TVAE + filtro DCR, n=2500)
    synthetic_metrics_tvae_dcr_n5000.json  (TVAE + filtro DCR, n=5000)

Salidas (en output/):
    synthetic_size_comparison.csv          Tabla comparativa
    fig_synthetic_size_comparison.png      Figura comparativa (utilidad y riesgo por tamano)
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR   = PROJECT_ROOT / "output"

C_DARK  = "#1F4E79"
C_LIGHT = "#D5E8F0"
C_AMBER = "#B7791F"
C_GREEN = "#1F7A3A"
C_GRAY  = "#888888"

# Umbrales preregistrados (deben coincidir con ACCEPT de synthetic_data.py)
THR = {"mi_auc": 0.60, "k1": 0.05, "k2": 0.10, "k5": 0.20, "dcr": 0.50}

# Configuraciones a comparar: (etiqueta, fichero de metricas, fichero de dataset sintético)
CONFIGS = [
    ("CTGAN (n=478)",              "synthetic_metrics.json",                    "synthetic_dataset.csv"),
    ("TVAE (n=478)",               "synthetic_metrics_tvae.json",               "synthetic_dataset_tvae.csv"),
    ("TVAE+DCR (n=1000)",          "synthetic_metrics_tvae_dcr_n1000.json",     "synthetic_dataset_tvae_dcr_n1000.csv"),
    ("TVAE+DCR (n=2500)",          "synthetic_metrics_tvae_dcr_n2500.json",     "synthetic_dataset_tvae_dcr_n2500.csv"),
    ("TVAE+DCR (n=5000)",          "synthetic_metrics_tvae_dcr_n5000.json",     "synthetic_dataset_tvae_dcr_n5000.csv"),
    ("TVAE+AUG+DCR (n=1000)",      "synthetic_metrics_tvae_dcr_aug_n1000.json", "synthetic_dataset_tvae_dcr_aug_n1000.csv"),
    ("TVAE+AUG+DCR (n=2500)",      "synthetic_metrics_tvae_dcr_aug_n2500.json", "synthetic_dataset_tvae_dcr_aug_n2500.csv"),
    ("TVAE+AUG+DCR (n=5000)",      "synthetic_metrics_tvae_dcr_aug_n5000.json", "synthetic_dataset_tvae_dcr_aug_n5000.csv"),
]

REAL_PATH = OUTPUT_DIR / "nesp_nct00119613_dataset.csv"
CAT_COLS  = ["DTH", "PFSCD", "SEXCD", "B_ECOGN", "TXG"]


# Calcula el TVD medio de las marginales categoricas del dataset sintético frente al real.
# Se computa de forma uniforme para todas las configuraciones desde los CSV, de modo que la
# fidelidad sea directamente comparable. Entrada: ruta del dataset sintético y dataframe real.
# Salida: TVD medio (0 = marginales identicas) o NaN si no se encuentra el fichero.
def _fidelity_tvd(syn_path: Path, df_real: pd.DataFrame) -> float:
    if not syn_path.exists():
        return float("nan")
    d = pd.read_csv(syn_path)
    tvds = []
    for c in CAT_COLS:
        if c not in d.columns or c not in df_real.columns:
            continue
        va = df_real[c].value_counts(normalize=True)
        vb = d[c].value_counts(normalize=True)
        cats = set(va.index) | set(vb.index)
        tvds.append(0.5 * sum(abs(float(va.get(k, 0.0)) - float(vb.get(k, 0.0))) for k in cats))
    return float(np.mean(tvds)) if tvds else float("nan")


# Lee un fichero de metricas y extrae las cifras relevantes en un diccionario plano.
# Anade la fidelidad marginal (TVD medio categorico) calculada desde el dataset sintético.
# Entrada: etiqueta, ruta del JSON, ruta del dataset y dataframe real. Salida: dict de fila.
def _row(label: str, path: Path, syn_path: Path, df_real: pd.DataFrame) -> dict | None:
    if not path.exists():
        return None
    m   = json.load(open(path, encoding="utf-8"))
    gen = m["generation"]
    u   = m.get("utility_tstr", {})
    r   = m["reidentification_risk"]
    mi  = r["membership_inference"]
    k   = r["k_anonymity"]
    dcr = r["dcr"]
    return {
        "Configuracion":   label,
        "n_sintetico":     gen.get("n_synthetic"),
        "TSTR_cindex":     round(u.get("tstr_mean", float("nan")), 4),
        "ratio_util":      round(u.get("utility_ratio", float("nan")), 4),
        "Fidelidad_TVD":   round(_fidelity_tvd(syn_path, df_real), 4),
        "MI_AUC":          round(mi.get("auc", float("nan")), 4),
        "k1_pct":          round(k["k1_pct"] * 100, 2),
        "k5_pct":          round(k["k5_pct"] * 100, 2),
        "DCR_ratio":       round(dcr.get("dcr_p5_rrdr_median_ratio", float("nan")), 4),
        "Global":          "ACEPTADO" if m.get("overall_accepted") else "NO ACEPTADO",
    }


# Construye la figura comparativa: utilidad TSTR, DCR ratio y k-anonimidad k=1 por configuracion,
# con las lineas de umbral preregistradas. Entrada: dataframe comparativo. Sin retorno (guarda PNG).
def _plot(df: pd.DataFrame, path: Path) -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": "#E0E0E0", "grid.linewidth": 0.7,
    })
    labels = df["Configuracion"].tolist()
    x = np.arange(len(labels))
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))

    # Panel 1: utilidad TSTR
    ax = axes[0, 0]
    ax.bar(x, df["TSTR_cindex"], color=C_DARK, width=0.6, edgecolor="white")
    ax.axhline(0.5, color=C_GRAY, ls="--", lw=1.2, label="Azar (0.5)")
    ax.axhline(0.60, color=C_GREEN, ls=":", lw=1.4, label="TRTR real (0.60)")
    ax.set_title("Utilidad TSTR (C-index OS) - mayor mejor", color=C_DARK, fontweight="bold")
    ax.set_ylim(0.40, 0.66); ax.set_xticks(x); ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=7)
    ax.legend(fontsize=7.5)

    # Panel 2: fidelidad marginal (TVD medio categorico)
    ax = axes[0, 1]
    ax.bar(x, df["Fidelidad_TVD"], color=C_DARK, width=0.6, edgecolor="white")
    ax.axhline(0.10, color=C_GREEN, ls=":", lw=1.4, label="Buena fidelidad (<0.10)")
    ax.set_title("Fidelidad marginal: TVD medio categorico - menor mejor", color=C_DARK, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=7)
    ax.legend(fontsize=7.5)

    # Panel 3: DCR ratio
    ax = axes[1, 0]
    cols = [C_AMBER if v < THR["dcr"] else C_GREEN for v in df["DCR_ratio"]]
    ax.bar(x, df["DCR_ratio"], color=cols, width=0.6, edgecolor="white")
    ax.axhline(THR["dcr"], color="red", ls="--", lw=1.6, label="Umbral DCR (0.50)")
    ax.set_title("DCR p5 / RRDR mediana - mayor mejor", color=C_DARK, fontweight="bold")
    ax.set_ylim(0, 0.75); ax.set_xticks(x); ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=7)
    ax.legend(fontsize=7.5)

    # Panel 4: k-anonimidad k=1
    ax = axes[1, 1]
    cols = [C_AMBER if v > THR["k1"] * 100 else C_GREEN for v in df["k1_pct"]]
    ax.bar(x, df["k1_pct"], color=cols, width=0.6, edgecolor="white")
    ax.axhline(THR["k1"] * 100, color="red", ls="--", lw=1.6, label="Umbral k=1 (5%)")
    ax.set_title("K-anonimidad: registros unicos k=1 (%) - menor mejor", color=C_DARK, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=7)
    ax.legend(fontsize=7.5)

    fig.suptitle(
        "Comparativa de generadores y tamanos sintéticos frente a los criterios preregistrados",
        color=C_DARK, fontweight="bold", y=1.02,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> int:
    df_real = pd.read_csv(REAL_PATH)
    rows = [r for (lbl, fn, ds) in CONFIGS
            if (r := _row(lbl, OUTPUT_DIR / fn, OUTPUT_DIR / ds, df_real)) is not None]
    if not rows:
        print("No se encontraron ficheros de metricas.")
        return 1
    df = pd.DataFrame(rows)
    csv_path = OUTPUT_DIR / "synthetic_size_comparison.csv"
    df.to_csv(csv_path, index=False)
    _plot(df, OUTPUT_DIR / "fig_synthetic_size_comparison.png")

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print(df.to_string(index=False))
    print(f"\nGuardado: {csv_path.name} y fig_synthetic_size_comparison.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
