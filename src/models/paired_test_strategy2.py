"""
src/models/paired_test_strategy2.py

Proposito:
    Test bootstrap PAREADO de la diferencia de C-index entre el Cox elastic-net de la
    Estrategia 2 (pool de 10 variables) y el baseline de 7 variables de la Estrategia 1,
    ambos bajo EL MISMO protocolo de validacion cruzada anidada. Es la operacionalizacion
    de la evaluacion de significacion del criterio a priori, no un cambio de criterio: el
    contraste pareado sobre las predicciones OOF es la forma correcta y mas potente de
    comparar dos modelos que el solapamiento de intervalos marginales.

    Se restringe DELIBERADAMENTE a coxnet vs baseline en OS (primario) y PFS (secundario).
    No se testean los seis contrastes: RSF y XGBoost ya muestran que no mejoran y multiplicar
    contrastes inflaria los falsos positivos.

Entradas:
    output/dataset_strategy2.parquet, output/nesp_nct00119613_dataset.csv
    (reutiliza run_outer_oof de nested_cv_strategy2 con las mismas semillas, por lo que
    reproduce exactamente las predicciones OOF de la corrida larga reportada).

Salidas:
    output/strategy2_paired_test.json   delta de C-index, IC95% bootstrap pareado y veredicto

Marco honesto (invariante, salga lo que salga):
    - Si el IC95% de la diferencia excluye el cero: mejora pequena pero detectable, que se
      reporta como hallazgo EXPLORATORIO (no como el primario pre-registrado), de tamano
      modesto y atribuible a las variables nuevas LDH y EPO (seleccionadas en todos los folds).
    - Si incluye el cero: base rigurosa para "sin mejora significativa".
    - En ambos casos el efecto es pequeno, el modelo final del TFG sigue siendo el Cox del
      primario y el aporte de la Estrategia 2 es metodologico.
"""

from __future__ import annotations

import json
import logging
import sys
import warnings
from pathlib import Path

import numpy as np
from sksurv.metrics import concordance_index_censored

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.cv_utils import ENDPOINTS, N_BOOTSTRAP, SEED, event_time_grid, make_strata, make_y
from src.models.nested_cv_strategy2 import (
    S1_FEATURES, S2_FEATURES, load_aligned_datasets, run_outer_oof,
)

warnings.filterwarnings("ignore")

OUTPUT_DIR = PROJECT_ROOT / "output"
N_TRIALS = 100
INNER_K = 5
OUTER_K = 5
MODELS = ("baseline", "coxnet")


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("paired_test_strategy2")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s", "%H:%M:%S"))
        logger.addHandler(sh)
    return logger


# C-index puntual de un vector de riesgo OOF frente al array estructurado y.
def _cindex(y, risk) -> float:
    c, *_ = concordance_index_censored(y["event"], y["time"], risk)
    return float(c)


# Bootstrap PAREADO de la diferencia de C-index (coxnet menos baseline).
# En cada remuestra se aplica el MISMO indice a ambos modelos (pareo), de modo que la
# correlacion entre sus predicciones reduce la varianza de la diferencia. Devuelve el
# delta puntual, la media y el IC95% percentilico de la diferencia, la fraccion de
# remuestras con delta > 0 y si el IC excluye el cero (significacion al 5%).
def paired_bootstrap(y, risk_a, risk_b, n=N_BOOTSTRAP, seed=SEED) -> dict:
    rng = np.random.default_rng(seed)
    n_samples = len(y)
    deltas = []
    for _ in range(n):
        idx = rng.integers(0, n_samples, size=n_samples)
        try:
            ca = _cindex(y[idx], risk_a[idx])
            cb = _cindex(y[idx], risk_b[idx])
            deltas.append(ca - cb)
        except Exception:
            continue
    deltas = np.array(deltas)
    ci_low, ci_high = float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))
    # p-valor bootstrap. Una cola (H0: coxnet no mejora, delta <= 0) y dos colas.
    p_one_sided = float(np.mean(deltas <= 0))
    p_two_sided = min(1.0, float(2.0 * min(np.mean(deltas <= 0), np.mean(deltas >= 0))))
    return {
        "delta_point": _cindex(y, risk_a) - _cindex(y, risk_b),
        "delta_mean": float(np.mean(deltas)),
        "ci_low": ci_low,
        "ci_high": ci_high,
        "frac_gt_0": float(np.mean(deltas > 0)),
        "p_one_sided": p_one_sided,
        "p_two_sided": p_two_sided,
        "excludes_zero": bool(ci_low > 0 or ci_high < 0),
        "n_boot": int(len(deltas)),
    }


# Correccion por comparaciones multiples sobre los contrastes evaluados (OS y PFS).
# Se evalua el mismo contraste relevante (coxnet vs baseline) en los dos endpoints: hay
# m=2 tests. Se aplican Bonferroni (umbral conservador) y Holm-Bonferroni (control del FWER
# menos conservador). Si ningun p ajustado baja de alpha, no hay mejora significativa tras
# controlar la multiplicidad, lo que refuerza el veredicto de KPI-3 no cumplido.
def multiplicity_adjust(p_by_contrast: dict, alpha: float = 0.05) -> dict:
    items = list(p_by_contrast.items())
    m = len(items)
    bonf = {k: min(1.0, p * m) for k, p in items}
    order = sorted(items, key=lambda kv: kv[1])  # Holm: p ascendente, factor (m-i) decreciente
    holm, running = {}, 0.0
    for i, (k, p) in enumerate(order):
        running = max(running, min(1.0, p * (m - i)))  # monotonia no decreciente
        holm[k] = running
    return {
        "contrasts": list(p_by_contrast.keys()),
        "m_tests": m,
        "alpha": alpha,
        "p_raw": dict(p_by_contrast),
        "p_bonferroni": bonf,
        "p_holm": holm,
        "significant_bonferroni": {k: bool(v < alpha) for k, v in bonf.items()},
        "significant_holm": {k: bool(v < alpha) for k, v in holm.items()},
        "any_significant": bool(any(v < alpha for v in holm.values())),
    }


def main() -> int:
    logger = setup_logger()
    np.random.seed(SEED)

    try:
        df_s2, df_s1 = load_aligned_datasets(logger)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        return 1

    X_s1, X_s2 = df_s1[S1_FEATURES].copy(), df_s2[S2_FEATURES].copy()
    results = {"config": {"contraste": "coxnet vs baseline", "endpoints": ["OS", "PFS"],
                          "trials": N_TRIALS, "inner_k": INNER_K, "outer_k": OUTER_K,
                          "n_boot": N_BOOTSTRAP, "seed": SEED}}

    for ep in ("OS", "PFS"):
        cfg = ENDPOINTS[ep]
        y = make_y(df_s2[cfg["event"]].values, df_s2[cfg["time"]].values)
        strata = make_strata(df_s2, cfg["event"])
        global_times = event_time_grid(y)
        logger.info("=== Endpoint %s (eventos=%d): OOF baseline y coxnet ===", ep, int(y["event"].sum()))

        oof = {}
        for mk in MODELS:
            _, oof_risk, _, _, _ = run_outer_oof(
                mk, X_s1, X_s2, y, strata, global_times, OUTER_K, N_TRIALS, INNER_K, logger)
            oof[mk] = oof_risk

        pt = paired_bootstrap(y, oof["coxnet"], oof["baseline"])
        results[ep] = pt
        veredicto = ("mejora pequena DETECTABLE (IC excluye 0)" if pt["excludes_zero"]
                     else "sin mejora significativa (IC incluye 0)")
        logger.info("[%s] delta C-index (coxnet - baseline) = %+.4f  IC95%% [%+.4f, %+.4f]  "
                    "P(delta>0)=%.3f  p2=%.3f  -> %s",
                    ep, pt["delta_point"], pt["ci_low"], pt["ci_high"], pt["frac_gt_0"],
                    pt["p_two_sided"], veredicto)

    # Correccion por comparaciones multiples sobre los 2 contrastes (OS, PFS).
    p_by_contrast = {ep: results[ep]["p_two_sided"] for ep in ("OS", "PFS")}
    mult = multiplicity_adjust(p_by_contrast, alpha=0.05)
    results["multiplicity"] = mult
    logger.info("--- Correccion por comparaciones multiples (m=%d contrastes, alpha=0.05) ---",
                mult["m_tests"])
    for ep in ("OS", "PFS"):
        logger.info("    %s: p_raw=%.4f  p_Holm=%.4f (%s)  p_Bonf=%.4f (%s)",
                    ep, mult["p_raw"][ep], mult["p_holm"][ep],
                    "sig" if mult["significant_holm"][ep] else "ns",
                    mult["p_bonferroni"][ep],
                    "sig" if mult["significant_bonferroni"][ep] else "ns")
    logger.info("    Veredicto tras multiplicidad: %s",
                "alguna mejora significativa" if mult["any_significant"]
                else "ninguna mejora significativa (KPI-3 no cumplido reforzado)")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "strategy2_paired_test.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    logger.info("Guardado: %s", out_path.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
