"""
src/reporting/figures_strategy2.py

Proposito:
    Generar las figuras del analisis ampliado (Estrategia 2) para la memoria D3,
    a partir de los artefactos ya producidos por la CV anidada y el test pareado.
    No recalcula nada: solo lee JSON y dibuja, con el estilo corporativo del proyecto
    (Arial, azul #1F4E79 / #D5E8F0, segun style_guide.md).

Entradas:
    output/strategy2_nested_metrics.json   (nested_cv_strategy2.py)
    output/strategy2_paired_test.json      (paired_test_strategy2.py)

Salidas (PNG 300 dpi en output/):
    fig_strategy2_models.png      Comparacion de modelos: C-index con IC95% por endpoint.
    fig_strategy2_paired.png      Test pareado: diferencia Cox elastic-net menos baseline, IC95%.
    fig_strategy2_selection.png   Frecuencia de seleccion de variables por el Cox elastic-net.

Uso:
    python src/reporting/figures_strategy2.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "output"
NESTED = OUTPUT_DIR / "strategy2_nested_metrics.json"
PAIRED = OUTPUT_DIR / "strategy2_paired_test.json"

# Colores corporativos (style_guide.md), identicos a los del primario.
C_DARK = "#1F4E79"
C_LIGHT = "#D5E8F0"
C_AMBER = "#B7791F"
C_GREEN = "#1F7A3A"
C_GRAY = "#888888"

ENDPOINTS = [("OS", "OS (primario)"), ("PFS", "PFS (secundario)")]
MODELS = [
    ("baseline", "Baseline 7 var"),
    ("coxnet", "Cox elastic-net"),
    ("rsf", "RSF"),
    ("xgb", "XGBoost"),
]

# Mapa de columna codificada (one-hot) a nombre legible para la figura de seleccion.
VAR_ORDER = ["AGE", "BMI", "CADIAGM", "B_HGB", "B_SEREPO", "MEDHX_N",
             "SEXCD", "B_ECOGN", "B_LDHN", "PRTFN"]
VAR_LABEL = {
    "AGE": "Edad", "BMI": "IMC", "CADIAGM": "Tiempo desde diag.",
    "B_HGB": "Hemoglobina", "B_SEREPO": "EPO", "MEDHX_N": "Comorbilidad",
    "SEXCD": "Sexo", "B_ECOGN": "ECOG", "B_LDHN": "LDH", "PRTFN": "Transfusion",
}


# Aplica el estilo corporativo de matplotlib (igual que el primario).
def _setup() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#E0E0E0",
        "grid.linewidth": 0.7,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "figure.dpi": 150,
    })


def _save(fig, name: str) -> None:
    path = OUTPUT_DIR / name
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("Generada:", path.name)


# Quita el sufijo one-hot (p.ej. SEXCD_1.0 -> SEXCD) para contar por variable.
def _canon(feat: str) -> str:
    for v in VAR_ORDER:
        if feat == v or feat.startswith(v + "_"):
            return v
    return feat


# Figura A: C-index con IC95% bootstrap por modelo y endpoint (dot + barras de error).
# Una linea de referencia vertical marca el baseline de cada endpoint.
def fig_models(nested: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.3), sharex=False)
    for ax, (ep, ep_lbl) in zip(axes, ENDPOINTS):
        ys = list(range(len(MODELS)))[::-1]  # baseline arriba
        base = nested[ep]["baseline"]["bootstrap"]["c_index"]["mean"]
        ax.axvline(base, color=C_GRAY, ls="--", lw=1.2, label="Baseline (referencia)")
        for y, (mk, lbl) in zip(ys, MODELS):
            bc = nested[ep][mk]["bootstrap"]["c_index"]
            m, lo, hi = bc["mean"], bc["ci_low"], bc["ci_high"]
            color = C_DARK if mk == "coxnet" else (C_GRAY if mk == "baseline" else C_AMBER)
            ax.errorbar(m, y, xerr=[[m - lo], [hi - m]], fmt="o", color=color,
                        ms=7, lw=1.8, capsize=5)
            ax.annotate(f"{m:.3f}", (m, y), textcoords="offset points", xytext=(0, 9),
                        ha="center", fontsize=8, color=color)
        ax.set_yticks(ys)
        ax.set_yticklabels([lbl for _, lbl in MODELS])
        ax.set_xlabel("C-index (IC95% bootstrap)")
        ax.set_title(ep_lbl, color=C_DARK, fontweight="bold")
        ax.axvline(0.5, color="#CCCCCC", ls=":", lw=1)
        ax.legend(loc="lower right", fontsize=8)
    fig.suptitle("Estrategia 2: discriminacion por modelo", color=C_DARK,
                 fontweight="bold", fontsize=13, y=1.02)
    fig.tight_layout()
    _save(fig, "fig_strategy2_models.png")


# Figura B: diferencia pareada de C-index (Cox elastic-net menos baseline) con IC95%,
# y linea de referencia en cero. Es el contraste de significacion clave.
def fig_paired(paired: dict) -> None:
    fig, ax = plt.subplots(figsize=(8, 3.4))
    ys = [1, 0]  # OS arriba, PFS abajo
    for y, (ep, ep_lbl) in zip(ys, ENDPOINTS):
        d = paired[ep]
        m, lo, hi = d["delta_point"], d["ci_low"], d["ci_high"]
        excl = d["excludes_zero"]
        color = C_GREEN if excl else C_AMBER
        ax.errorbar(m, y, xerr=[[m - lo], [hi - m]], fmt="o", color=color,
                    ms=8, lw=2, capsize=6)
        nota = "IC excluye 0 (al limite)" if excl else "IC incluye 0"
        ax.annotate(f"{m:+.3f}  [{lo:+.3f}, {hi:+.3f}]   {nota}",
                    (hi, y), textcoords="offset points", xytext=(10, 0),
                    va="center", fontsize=8.5, color=color)
    ax.axvline(0.0, color=C_GRAY, ls="--", lw=1.4, label="Sin diferencia (0)")
    ax.set_yticks(ys)
    ax.set_yticklabels([lbl for _, lbl in ENDPOINTS])
    ax.set_ylim(-0.6, 1.6)
    ax.set_xlim(-0.06, 0.10)
    ax.set_xlabel("Diferencia de C-index (Cox elastic-net menos baseline)")
    ax.set_title("Test pareado frente al baseline (IC95% bootstrap pareado)",
                 color=C_DARK, fontweight="bold")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    _save(fig, "fig_strategy2_paired.png")


# Figura C: frecuencia (sobre 5 folds externos) con que el Cox elastic-net retiene cada
# variable, por endpoint. Barras horizontales agrupadas OS / PFS.
def fig_selection(nested: dict) -> None:
    counts = {ep: Counter() for ep, _ in ENDPOINTS}
    for ep, _ in ENDPOINTS:
        for fold in nested[ep]["coxnet"]["selection"]:
            for feat in fold.get("selected_features", []):
                counts[ep][_canon(feat)] += 1
    ys = list(range(len(VAR_ORDER)))[::-1]
    h = 0.38
    fig, ax = plt.subplots(figsize=(9, 5.4))
    ax.barh([y + h / 2 for y in ys], [counts["OS"][v] for v in VAR_ORDER],
            height=h, color=C_DARK, label="OS")
    ax.barh([y - h / 2 for y in ys], [counts["PFS"][v] for v in VAR_ORDER],
            height=h, color=C_AMBER, label="PFS")
    ax.set_yticks(ys)
    ax.set_yticklabels([VAR_LABEL[v] for v in VAR_ORDER])
    ax.set_xlim(0, 5.4)
    ax.set_xticks(range(6))
    ax.set_xlabel("Folds externos que retienen la variable (de 5)")
    ax.set_title("Estrategia 2: seleccion de variables por el Cox elastic-net",
                 color=C_DARK, fontweight="bold")
    ax.legend(loc="lower right")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    _save(fig, "fig_strategy2_selection.png")


def main() -> int:
    if not NESTED.exists() or not PAIRED.exists():
        print("Faltan artefactos de la Estrategia 2. Ejecuta primero "
              "nested_cv_strategy2.py y paired_test_strategy2.py.", file=sys.stderr)
        return 1
    nested = json.load(open(NESTED, encoding="utf-8"))
    paired = json.load(open(PAIRED, encoding="utf-8"))
    _setup()
    fig_models(nested)
    fig_paired(paired)
    fig_selection(nested)
    print("Figuras de la Estrategia 2 generadas en", OUTPUT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
