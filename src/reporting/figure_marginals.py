"""
src/reporting/figure_marginals.py

Proposito:
    Figura de fidelidad marginal: compara las distribuciones marginales de las variables
    categoricas clave del dataset real frente a los conjuntos sintéticos (CTGAN, TVAE y la
    solucion combinada TVAE con augmentacion y filtro DCR). Evidencia de forma visual el colapso
    de modos del TVAE sin augmentacion y su correccion en la solucion combinada.

ADVERTENCIA: los datos sintéticos son exclusivamente para prototipado metodologico.

Entradas (en output/):
    nesp_nct00119613_dataset.csv               (real)
    synthetic_dataset.csv                       (CTGAN)
    synthetic_dataset_tvae.csv                  (TVAE)
    synthetic_dataset_tvae_dcr_aug_n5000.csv    (solucion combinada)

Salida (en output/):
    fig_synthetic_marginals.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT = PROJECT_ROOT / "output"

C_DARK, C_LIGHT, C_GREEN, C_AMBER, C_GRAY = "#1F4E79", "#D5E8F0", "#1F7A3A", "#B7791F", "#888888"

# Conjuntos a comparar: etiqueta, fichero, color
SETS = [
    ("Real",            "nesp_nct00119613_dataset.csv",                C_GRAY),
    ("CTGAN",           "synthetic_dataset.csv",                       C_LIGHT),
    ("TVAE",            "synthetic_dataset_tvae.csv",                  C_AMBER),
    ("TVAE+AUG+DCR",    "synthetic_dataset_tvae_dcr_aug_n5000.csv",    C_GREEN),
]

# Marginales a representar como porcentaje de la clase indicada
METRICS = [
    ("Eventos OS\n(muerte)",  lambda d: d["DTH"].mean() * 100),
    ("Eventos PFS",           lambda d: d["PFSCD"].mean() * 100),
    ("Sexo = 1\n(femenino)",  lambda d: d["SEXCD"].mean() * 100),
    ("ECOG = 2",              lambda d: (d["B_ECOGN"] == 2).mean() * 100),
]


def main() -> int:
    data = {}
    for label, fn, _ in SETS:
        p = OUT / fn
        if not p.exists():
            print("Falta:", fn)
            return 1
        data[label] = pd.read_csv(p)

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": "#E0E0E0", "grid.linewidth": 0.7,
    })
    fig, ax = plt.subplots(figsize=(9, 4.8))
    n_metrics = len(METRICS)
    n_sets = len(SETS)
    x = np.arange(n_metrics)
    width = 0.8 / n_sets

    for i, (label, _, color) in enumerate(SETS):
        vals = [fn(data[label]) for _, fn in METRICS]
        edge = "#555555" if color == C_LIGHT else "white"
        bars = ax.bar(x + i * width - 0.4 + width / 2, vals, width,
                      label=label, color=color, edgecolor=edge, linewidth=0.7)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.0f}",
                    ha="center", va="bottom", fontsize=7.5, color=C_GRAY)

    ax.set_xticks(x)
    ax.set_xticklabels([m[0] for m in METRICS], fontsize=9)
    ax.set_ylabel("Porcentaje (%)")
    ax.set_ylim(0, 109)
    ax.set_title("Fidelidad de las marginales: real frente a generadores sintéticos",
                 color=C_DARK, fontweight="bold")
    ax.legend(ncol=4, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    ax.text(0.5, -0.30,
            "TVAE colapsa las clases minoritarias (eventos al 100%, pocas mujeres y ECOG 2); "
            "la augmentacion las restituye hacia los valores reales.",
            transform=ax.transAxes, ha="center", va="top", fontsize=7, color=C_GRAY, style="italic")

    fig.tight_layout()
    out = OUT / "fig_synthetic_marginals.png"
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("Guardado:", out.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
