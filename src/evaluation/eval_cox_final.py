"""
src/evaluation/eval_cox_final.py

Proposito:
    Evaluacion completa del modelo final (Cox PH) sobre OS y PFS mediante
    predicciones OOF (out-of-fold) del esquema CV k=5.

Entradas:
    output/nesp_nct00119613_dataset.csv

Salidas (en output/):
    Figuras (PNG 300 dpi):
        fig_calibration_{EP}.png   Calibracion en 3 tiempos de referencia
        fig_brier_time_{EP}.png    Brier Score a lo largo del tiempo con bandas bootstrap
        fig_auc_time_{EP}.png      AUC dinamica acumulada con bandas bootstrap
        fig_evaluation_{EP}.png    Panel 1x3 combinado por endpoint

    Tablas (CSV):
        eval_calibration_{EP}.csv  Predicted vs observed por grupo y tiempo de referencia
        eval_brier_time_{EP}.csv   B(t) con IC95% bootstrap en cada punto de la rejilla
        eval_auc_time_{EP}.csv     AUC(t) con IC95% bootstrap en cada punto de la rejilla

Metodologia:
    - Las predicciones OOF se generan refitando el Cox (sin hiperparametros que optimizar)
      con el mismo esquema CV k=5 estratificado que cox_baseline.py.
    - Calibracion: 10 grupos de decil por probabilidad predicha; S observada = KM en el grupo.
      Bandas de error = IC95% KM (formula log-log de lifelines).
    - Brier Score: brier_score() de sksurv en rejilla de 50 tiempos; bootstrap n=1000.
    - AUC: cumulative_dynamic_auc() de sksurv; bootstrap n=1000.
    - Estilo: Arial, azul corporativo #1F4E79 / #D5E8F0 segun style_guide.md.
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
from lifelines import KaplanMeierFitter
from sklearn.model_selection import StratifiedKFold
from sksurv.linear_model import CoxPHSurvivalAnalysis
from sksurv.metrics import brier_score, cumulative_dynamic_auc

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.cv_utils import (
    SEED, K_FOLDS, make_y, make_strata, event_time_grid,
    safe_fold_times,
)
from src.preprocessing.build_preprocessor import (
    NUMERIC_FEATURES, CATEGORICAL_FEATURES, build_preprocessor,
)

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------

FEATURES    = NUMERIC_FEATURES + CATEGORICAL_FEATURES
N_TIME_EVAL = 50       # puntos en la rejilla de evaluacion (mas fina que la de entrenamiento)
N_CAL_GROUPS = 10      # deciles de calibracion
N_BOOT      = 1000     # bootstrap para Brier y AUC
N_BOOT_CAL  = 500      # bootstrap para calibracion (mas caro por KM interna)
ENDPOINTS   = {
    "OS":  {"event": "DTH",   "time": "DTHDY",  "label": "OS (tiempo hasta muerte)"},
    "PFS": {"event": "PFSCD", "time": "PFSDY",  "label": "SLP (supervivencia libre de progresion)"},
}
DATASET_PATH = PROJECT_ROOT / "output" / "nesp_nct00119613_dataset.csv"
OUTPUT_DIR   = PROJECT_ROOT / "output"

# Colores corporativos (style_guide.md)
C_DARK  = "#1F4E79"
C_LIGHT = "#D5E8F0"
C_AMBER = "#B7791F"
C_GREEN = "#1F7A3A"
C_GRAY  = "#888888"

# ---------------------------------------------------------------------------
# Utilidades matplotlib
# ---------------------------------------------------------------------------

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
        "figure.dpi":        150,
    })


def _save(fig: plt.Figure, path: Path, dpi: int = 300) -> None:
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Recolecion OOF
# ---------------------------------------------------------------------------

def collect_oof(df: pd.DataFrame, event_col: str, time_col: str) -> dict:
    """
    Ejecuta CV k=5 recogiendo predicciones OOF del modelo Cox:
    - risk scores (log hazard)
    - survival matrix en la rejilla de evaluacion
    - y estructurado completo
    """
    y = make_y(df[event_col].values, df[time_col].values)
    X = df[FEATURES].copy()
    strata = make_strata(df, event_col)

    # Rejilla de evaluacion mas fina. Se deduplica para evitar que sksurv
    # llame a np.unique internamente y desalinee times con estimate.
    event_times = y["time"][y["event"]]
    global_times = np.unique(np.percentile(
        event_times,
        np.linspace(10.0, 90.0, N_TIME_EVAL),
    ))

    cv = StratifiedKFold(n_splits=K_FOLDS, shuffle=True, random_state=SEED)

    n_times   = len(global_times)
    oof_risk  = np.zeros(len(df))
    oof_surv  = np.zeros((len(df), n_times))
    t_max_per_fold = []

    for fold_i, (train_idx, test_idx) in enumerate(cv.split(X, strata)):
        preproc = build_preprocessor()
        X_tr = preproc.fit_transform(X.iloc[train_idx])
        X_te = preproc.transform(X.iloc[test_idx])

        y_tr = y[train_idx]
        y_te = y[test_idx]

        cox = CoxPHSurvivalAnalysis(alpha=0, ties="efron", n_iter=100)
        cox.fit(X_tr, y_tr)

        oof_risk[test_idx] = cox.predict(X_te)

        surv_fns = cox.predict_survival_function(X_te)
        oof_surv[test_idx] = np.vstack([fn(global_times) for fn in surv_fns])

        t_max_per_fold.append(float(y_tr["time"].max()))

    t_max_common = min(t_max_per_fold)
    safe_times = global_times[global_times < t_max_common]
    safe_surv  = oof_surv[:, global_times < t_max_common]

    return {
        "y":           y,
        "oof_risk":    oof_risk,
        "oof_surv":    oof_surv,       # en global_times completo
        "safe_surv":   safe_surv,      # en safe_times (para IBS/bootstrap)
        "global_times": global_times,
        "safe_times":   safe_times,
    }


# ---------------------------------------------------------------------------
# Calibracion
# ---------------------------------------------------------------------------

def _km_at_t(event_arr: np.ndarray, time_arr: np.ndarray,
              t_ref: float) -> tuple[float, float, float]:
    """KM puntual y IC95% (log-log) en t_ref para un grupo."""
    if event_arr.astype(bool).sum() < 2 or len(event_arr) < 5:
        return np.nan, np.nan, np.nan
    kmf = KaplanMeierFitter()
    kmf.fit(time_arr, event_observed=event_arr.astype(bool))
    try:
        s   = float(kmf.survival_function_at_times([t_ref]).iloc[0])
        ci  = kmf.confidence_interval_survival_function_at_times([t_ref])
        lo  = float(ci.iloc[0, 0])
        hi  = float(ci.iloc[0, 1])
        return s, lo, hi
    except Exception:
        return np.nan, np.nan, np.nan


def compute_calibration(
    s_pred_col: np.ndarray,
    y: np.ndarray,
    ref_times: np.ndarray,
    n_groups: int = N_CAL_GROUPS,
) -> pd.DataFrame:
    """
    Para cada tiempo de referencia: divide los sujetos en n_groups por probabilidad
    predicha, calcula media predicha y KM observada en cada grupo.
    """
    rows = []
    for t_ref in ref_times:
        q_labels = pd.qcut(pd.Series(s_pred_col), n_groups, labels=False, duplicates="drop")
        for g in sorted(q_labels.dropna().unique()):
            mask = q_labels == g
            if mask.sum() < 5:
                continue
            mean_pred = float(s_pred_col[mask].mean())
            obs, lo, hi = _km_at_t(y["event"][mask], y["time"][mask], t_ref)
            rows.append({
                "ref_time":   t_ref,
                "group":      int(g),
                "n":          int(mask.sum()),
                "n_events":   int(y["event"][mask].sum()),
                "mean_pred":  mean_pred,
                "km_obs":     obs,
                "km_ci_lo":   lo,
                "km_ci_hi":   hi,
            })
    return pd.DataFrame(rows)


def _plot_calibration(
    calib_df: pd.DataFrame,
    ref_times: np.ndarray,
    ep_label: str,
    ax_list: list,
) -> None:
    colors = [C_DARK, C_AMBER, C_GREEN]
    ref_labels = [f"t = {int(t)} dias" for t in ref_times]

    for ax, t_ref, color, lbl in zip(ax_list, ref_times, colors, ref_labels):
        sub = calib_df[calib_df["ref_time"] == t_ref].dropna(subset=["km_obs"])
        if sub.empty:
            ax.set_visible(False)
            continue

        ax.errorbar(
            sub["mean_pred"], sub["km_obs"],
            yerr=[sub["km_obs"] - sub["km_ci_lo"], sub["km_ci_hi"] - sub["km_obs"]],
            fmt="o", color=color, ms=6, lw=1.5, capsize=4,
            label=lbl, zorder=3,
        )
        # Diagonal perfecta
        lim = [0, 1]
        ax.plot(lim, lim, "--", color="#AAAAAA", lw=1, label="Calibracion perfecta")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.set_xlabel("S(t) predicha (Cox)")
        ax.set_ylabel("S(t) observada (Kaplan-Meier)")
        ax.set_title(lbl, color=C_DARK, fontweight="bold")
        ax.legend(fontsize=8)
        ax.set_aspect("equal", adjustable="box")


# ---------------------------------------------------------------------------
# Brier Score a lo largo del tiempo
# ---------------------------------------------------------------------------

def compute_brier_curve(
    y: np.ndarray,
    safe_surv: np.ndarray,
    safe_times: np.ndarray,
    n_boot: int = N_BOOT,
    seed: int = SEED,
) -> pd.DataFrame:
    """
    B(t) puntual con IC95% bootstrap. Ademas calcula la referencia del modelo nulo
    (KM marginal para todos los sujetos, sin covariables).

    Filtra la rejilla de tiempos al rango estrictamente interior del dataset para
    que el estimador IPCW de sksurv no quede fuera de dominio.
    """
    # Tiempos estrictamente dentro del rango observable y sin duplicados
    # (sksurv llama np.unique internamente, lo que desalinearia times vs estimate).
    t_obs_min = float(y["time"].min())
    t_obs_max = float(y["time"].max())
    mask = (safe_times > t_obs_min) & (safe_times < t_obs_max)
    eval_times_raw = safe_times[mask]
    eval_surv_raw  = safe_surv[:, mask]
    # Deduplicar manteniendo el orden ascendente.
    uniq_vals, uniq_idx = np.unique(eval_times_raw, return_index=True)
    eval_times = uniq_vals
    eval_surv  = eval_surv_raw[:, uniq_idx]

    if len(eval_times) < 3:
        return pd.DataFrame()

    # Brier Score del modelo Cox (OOF)
    _, bs_cox = brier_score(y, y, eval_surv, eval_times)

    # Modelo nulo: predecir la KM marginal para todos (sin covariables)
    kmf_ref = KaplanMeierFitter()
    kmf_ref.fit(y["time"], event_observed=y["event"])
    s_null = np.column_stack([
        kmf_ref.survival_function_at_times([t]).values[0] * np.ones(len(y))
        for t in eval_times
    ])
    _, bs_null = brier_score(y, y, s_null, eval_times)

    # Bootstrap
    rng = np.random.default_rng(seed + 10)
    n = len(y)
    boot_bs = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        try:
            _, bs_b = brier_score(y, y[idx], eval_surv[idx], eval_times)
            boot_bs.append(bs_b)
        except Exception:
            continue
    boot_bs = np.array(boot_bs)

    return pd.DataFrame({
        "time":       eval_times,
        "brier":      bs_cox,
        "brier_null": bs_null,
        "ci_lo":      np.percentile(boot_bs, 2.5,  axis=0),
        "ci_hi":      np.percentile(boot_bs, 97.5, axis=0),
    })


def _plot_brier(
    brier_df: pd.DataFrame,
    ep_label: str,
    ax: plt.Axes,
) -> None:
    t = brier_df["time"].values
    b = brier_df["brier"].values
    lo = brier_df["ci_lo"].values
    hi = brier_df["ci_hi"].values
    bn = brier_df["brier_null"].values

    ax.fill_between(t, lo, hi, color=C_LIGHT, alpha=0.8, label="IC95% bootstrap")
    ax.plot(t, b, color=C_DARK, lw=2, label="Cox PH (OOF)")
    ax.plot(t, bn, "--", color=C_GRAY, lw=1.2, label="Modelo nulo (KM marginal)")
    ax.set_xlabel("Tiempo (dias)")
    ax.set_ylabel("Brier Score B(t)")
    ax.set_title(f"Brier Score en el tiempo\n{ep_label}", color=C_DARK, fontweight="bold")
    ax.legend()
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))


# ---------------------------------------------------------------------------
# AUC dinamica acumulada
# ---------------------------------------------------------------------------

def compute_auc_curve(
    y: np.ndarray,
    oof_risk: np.ndarray,
    safe_times: np.ndarray,
    n_boot: int = N_BOOT,
    seed: int = SEED,
) -> pd.DataFrame:
    """
    AUC(t) acumulada/dinamica con IC95% bootstrap.
    Usa el dataset completo como referencia IPCW (aproximacion estandar para OOF).
    """
    # Restriccion: tiempos dentro del rango de eventos
    event_times = y["time"][y["event"]]
    t_min, t_max = event_times.min(), event_times.max()
    valid = (safe_times > t_min) & (safe_times < t_max)
    eval_times = safe_times[valid]

    if len(eval_times) < 3:
        return pd.DataFrame()

    auc_vals, mean_auc = cumulative_dynamic_auc(y, y, oof_risk, eval_times)

    rng = np.random.default_rng(seed + 20)
    n = len(y)
    boot_auc = []
    boot_mean = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        try:
            av, ma = cumulative_dynamic_auc(y[idx], y[idx], oof_risk[idx], eval_times)
            boot_auc.append(av)
            boot_mean.append(ma)
        except Exception:
            continue
    boot_auc  = np.array(boot_auc)
    boot_mean = np.array(boot_mean)

    return pd.DataFrame({
        "time":       eval_times,
        "auc":        auc_vals,
        "ci_lo":      np.percentile(boot_auc, 2.5,  axis=0),
        "ci_hi":      np.percentile(boot_auc, 97.5, axis=0),
        "mean_auc":   mean_auc,
        "mean_ci_lo": float(np.percentile(boot_mean, 2.5)),
        "mean_ci_hi": float(np.percentile(boot_mean, 97.5)),
    })


def _plot_auc(
    auc_df: pd.DataFrame,
    ep_label: str,
    ax: plt.Axes,
) -> None:
    if auc_df.empty:
        ax.set_visible(False)
        return
    t  = auc_df["time"].values
    a  = auc_df["auc"].values
    lo = auc_df["ci_lo"].values
    hi = auc_df["ci_hi"].values
    ma  = float(auc_df["mean_auc"].iloc[0])
    mlo = float(auc_df["mean_ci_lo"].iloc[0])
    mhi = float(auc_df["mean_ci_hi"].iloc[0])

    ax.fill_between(t, lo, hi, color=C_LIGHT, alpha=0.8, label="IC95% bootstrap")
    ax.plot(t, a, color=C_DARK, lw=2, label="AUC acumulada/dinamica")
    ax.axhline(0.5, color=C_GRAY, ls="--", lw=1.2, label="Referencia aleatoria (0.5)")
    ax.set_xlabel("Tiempo (dias)")
    ax.set_ylabel("AUC(t)")
    ax.set_ylim(0.3, 1.0)
    ax.set_title(
        f"AUC dinamica acumulada\n{ep_label}",
        color=C_DARK, fontweight="bold",
    )
    ax.legend()
    ax.text(
        0.97, 0.08,
        f"AUC media = {ma:.3f}\nIC95% [{mlo:.3f}, {mhi:.3f}]",
        transform=ax.transAxes, ha="right", va="bottom",
        fontsize=8, color=C_DARK,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=C_LIGHT, lw=1),
    )


# ---------------------------------------------------------------------------
# Evaluacion completa por endpoint
# ---------------------------------------------------------------------------

def run_endpoint_eval(
    df: pd.DataFrame,
    ep_name: str,
    event_col: str,
    time_col: str,
    ep_label: str,
    logger: logging.Logger,
) -> None:
    logger.info("=== Evaluacion | Endpoint %s ===", ep_name)

    # OOF
    logger.info("  Recogiendo predicciones OOF (CV k=5)...")
    oof = collect_oof(df, event_col, time_col)
    y             = oof["y"]
    oof_risk      = oof["oof_risk"]
    safe_surv     = oof["safe_surv"]
    safe_times    = oof["safe_times"]
    global_times  = oof["global_times"]

    # Tiempos de referencia para calibracion: p25, p50, p75 de tiempos de evento
    ref_times = np.percentile(y["time"][y["event"]], [25, 50, 75])
    logger.info("  Tiempos de referencia (dias): %s", np.round(ref_times).astype(int))

    # Indice de safe_times mas cercano a cada ref_time para extraer S(t*)
    ref_time_idxs = [np.argmin(np.abs(safe_times - t)) for t in ref_times]
    ref_times_actual = safe_times[ref_time_idxs]

    # --------------- Calibracion ---------------
    logger.info("  Calibracion en %d tiempos de referencia...", len(ref_times_actual))
    calib_rows = []
    for t_ref, t_idx in zip(ref_times_actual, ref_time_idxs):
        s_pred_col = safe_surv[:, t_idx]
        sub = compute_calibration(s_pred_col, y, np.array([t_ref]))
        calib_rows.append(sub)
    calib_df = pd.concat(calib_rows, ignore_index=True)
    calib_path = OUTPUT_DIR / f"eval_calibration_{ep_name}.csv"
    calib_df.to_csv(calib_path, index=False)
    logger.info("  Guardado: %s", calib_path.name)

    # --------------- Brier Score ---------------
    logger.info("  Brier Score bootstrap (n=%d)...", N_BOOT)
    brier_df = compute_brier_curve(y, safe_surv, safe_times)
    brier_path = OUTPUT_DIR / f"eval_brier_time_{ep_name}.csv"
    brier_df.to_csv(brier_path, index=False)
    logger.info("  Guardado: %s", brier_path.name)

    # --------------- AUC ---------------
    logger.info("  AUC dinamica bootstrap (n=%d)...", N_BOOT)
    auc_df = compute_auc_curve(y, oof_risk, safe_times)
    auc_path = OUTPUT_DIR / f"eval_auc_time_{ep_name}.csv"
    auc_df.to_csv(auc_path, index=False)
    logger.info("  Guardado: %s", auc_path.name)

    _setup_rcparams()

    # --------------- Figura calibracion (1x3) ---------------
    fig_cal, axes_cal = plt.subplots(1, 3, figsize=(14, 4.5))
    fig_cal.suptitle(
        f"Curvas de calibracion - Cox PH - {ep_label}",
        fontsize=13, fontweight="bold", color=C_DARK, y=1.02,
    )
    _plot_calibration(calib_df, ref_times_actual, ep_label, list(axes_cal))
    fig_cal.tight_layout()
    _save(fig_cal, OUTPUT_DIR / f"fig_calibration_{ep_name}.png")
    logger.info("  Guardado: fig_calibration_%s.png", ep_name)

    # --------------- Figura Brier ---------------
    fig_br, ax_br = plt.subplots(figsize=(7, 4.5))
    _plot_brier(brier_df, ep_label, ax_br)
    fig_br.tight_layout()
    _save(fig_br, OUTPUT_DIR / f"fig_brier_time_{ep_name}.png")
    logger.info("  Guardado: fig_brier_time_%s.png", ep_name)

    # --------------- Figura AUC ---------------
    fig_auc, ax_auc = plt.subplots(figsize=(7, 4.5))
    _plot_auc(auc_df, ep_label, ax_auc)
    fig_auc.tight_layout()
    _save(fig_auc, OUTPUT_DIR / f"fig_auc_time_{ep_name}.png")
    logger.info("  Guardado: fig_auc_time_%s.png", ep_name)

    # --------------- Panel combinado (1x3) ---------------
    fig_all, axes_all = plt.subplots(1, 3, figsize=(18, 5))
    fig_all.suptitle(
        f"Evaluacion completa - Cox PH - {ep_label}",
        fontsize=13, fontweight="bold", color=C_DARK,
    )

    # Calibracion en el tiempo de referencia central (p50)
    mid = calib_df[calib_df["ref_time"] == ref_times_actual[1]].dropna(subset=["km_obs"])
    if not mid.empty:
        ax_c = axes_all[0]
        ax_c.errorbar(
            mid["mean_pred"], mid["km_obs"],
            yerr=[mid["km_obs"] - mid["km_ci_lo"], mid["km_ci_hi"] - mid["km_obs"]],
            fmt="o", color=C_DARK, ms=6, lw=1.5, capsize=4,
            label=f"t = {int(ref_times_actual[1])} dias",
        )
        ax_c.plot([0, 1], [0, 1], "--", color="#AAAAAA", lw=1, label="Calibracion perfecta")
        ax_c.set_xlim(0, 1); ax_c.set_ylim(0, 1)
        ax_c.set_xlabel("S(t) predicha"); ax_c.set_ylabel("S(t) observada (KM)")
        ax_c.set_title("Calibracion", color=C_DARK, fontweight="bold")
        ax_c.legend(fontsize=8)

    _plot_brier(brier_df, ep_label, axes_all[1])
    _plot_auc(auc_df, ep_label, axes_all[2])

    fig_all.tight_layout()
    _save(fig_all, OUTPUT_DIR / f"fig_evaluation_{ep_name}.png")
    logger.info("  Guardado: fig_evaluation_%s.png", ep_name)

    # Resumen en consola
    if not auc_df.empty:
        ma  = float(auc_df["mean_auc"].iloc[0])
        mlo = float(auc_df["mean_ci_lo"].iloc[0])
        mhi = float(auc_df["mean_ci_hi"].iloc[0])
    else:
        ma = mlo = mhi = float("nan")
    ibs_val = float(brier_df["brier"].mean())

    logger.info(
        "  Resumen %s: IBS medio=%.4f | AUC media=%.4f IC95%% [%.4f, %.4f]",
        ep_name, ibs_val, ma, mlo, mhi,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def setup_logger() -> logging.Logger:
    logger = logging.getLogger("eval_cox")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(message)s", "%H:%M:%S",
        ))
        logger.addHandler(sh)
    return logger


def main() -> int:
    logger = setup_logger()
    np.random.seed(SEED)

    if not DATASET_PATH.exists():
        logger.error("Dataset no encontrado: %s", DATASET_PATH)
        return 1

    df = pd.read_csv(DATASET_PATH)
    logger.info("Dataset: %d sujetos.", len(df))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for ep_name, ep_cfg in ENDPOINTS.items():
        run_endpoint_eval(
            df, ep_name, ep_cfg["event"], ep_cfg["time"], ep_cfg["label"], logger,
        )

    logger.info("Evaluacion completa. Artefactos en: %s", OUTPUT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
