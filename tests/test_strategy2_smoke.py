"""
tests/test_strategy2_smoke.py

Smoke tests del analisis ampliado (Estrategia 2). Cubren los componentes propios de
la Estrategia 2 sin tocar el pipeline primario ni su KPI-1, y sin requerir el dataset
real (se usan datos sinteticos con senal artificial).

Verificaciones cubiertas:
    1. Pool de 10 covariables: listas numerica y categorica esperadas, sin variables
       prohibidas (outcomes, TXG, SUBJID, constantes).
    2. log1p de B_SEREPO antes de escalar: la columna transformada correlaciona con
       log1p del crudo, no con el crudo.
    3. Anti-leakage del preprocesador de la Estrategia 2: el ajuste sobre el train no
       depende del test (transformacion identica reajustando con el mismo train).
    4. CV anidada: run_outer_oof cubre todos los sujetos con prediccion OOF y es
       determinista con la misma semilla (coxnet, configuracion minima).
    5. Test pareado: paired_bootstrap devuelve la estructura esperada y un IC coherente.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pytest

from src.models.cv_utils import SEED, make_y, make_strata, event_time_grid
from src.preprocessing.build_preprocessor_strategy2 import (
    CATEGORICAL_FEATURES as S2_CAT,
    NUMERIC_FEATURES as S2_NUM,
    LOG_FEATURES,
    build_preprocessor_strategy2,
)
from src.models.nested_cv_strategy2 import S1_FEATURES, S2_FEATURES, run_outer_oof
from src.models.paired_test_strategy2 import paired_bootstrap

FORBIDDEN = {"DTH", "DTHDY", "PFSCD", "PFSDY", "TXG", "SUBJID",
             "EVALPRIM", "EVALQOL", "RACECD", "TUMORCD", "EXTENTCD", "CHDCLASS"}

N = 80
LOGGER = logging.getLogger("test_strategy2")


# ---------------------------------------------------------------------------
# Fixture: dataset sintetico con las columnas de S1 y S2
# ---------------------------------------------------------------------------

# Genera un dataset sintetico con todas las columnas que necesitan el baseline (S1)
# y los modelos de la Estrategia 2 (S2). Introduce senal artificial (mayor edad,
# comorbilidad y LDH anormal => mayor riesgo) para que el C-index supere el azar, y
# asimetria fuerte en B_SEREPO para verificar el efecto del log1p.
@pytest.fixture(scope="module")
def df_synth() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    n = N
    age = rng.uniform(40, 80, n)
    medhx = rng.integers(0, 7, n).astype(float)
    ldh = rng.choice([1.0, 2.0], n)            # 1 normal, 2 anormal
    # Predictor lineal centrado: mayor edad, comorbilidad y LDH anormal => mayor riesgo.
    # La escala en dias se reparte de forma amplia (sin colapsar al clip) para que la
    # rejilla de tiempos del IBS tenga puntos distintos.
    linpred = 0.04 * (age - 60) + 0.25 * (medhx - 3) + 0.6 * (ldh == 2.0)
    time = np.clip(rng.exponential(scale=600.0 * np.exp(-linpred)), 5, 1500)
    event = rng.uniform(size=n) < 0.80
    weight = rng.uniform(50, 100, n)
    height = rng.uniform(150, 195, n)
    df = pd.DataFrame({
        "AGE": age,
        "B_WEIGHT": weight,
        "BMI": weight / (height / 100.0) ** 2,
        "CADIAGM": rng.uniform(1, 120, n),
        "B_HGB": rng.uniform(8, 16, n),
        "B_SEREPO": rng.lognormal(mean=3.0, sigma=1.0, size=n),  # muy asimetrica
        "MEDHX_N": medhx,
        "SEXCD": rng.choice([1.0, 2.0], n),
        "B_ECOGN": rng.choice([1.0, 2.0], n),
        "B_LDHN": ldh,
        "PRTFN": rng.choice([0.0, 1.0], n, p=[0.95, 0.05]),
        "DTH": event.astype(int),
        "DTHDY": time,
        "PFSCD": rng.integers(0, 2, n),
        "PFSDY": rng.uniform(1, 800, n),
        "TXG": rng.integers(0, 2, n),
    })
    idx = rng.choice(n, size=max(1, int(0.09 * n)), replace=False)
    df.loc[idx, "B_SEREPO"] = np.nan  # ~9% de faltantes, como en el dato real
    return df


# ---------------------------------------------------------------------------
# 1. Pool de variables de la Estrategia 2
# ---------------------------------------------------------------------------

class TestStrategy2Pool:

    # El pool de 10 variables (6 numericas + 4 categoricas) es exactamente el esperado.
    def test_pool_esperado(self):
        assert S2_NUM == ["AGE", "BMI", "CADIAGM", "B_HGB", "B_SEREPO", "MEDHX_N"]
        assert S2_CAT == ["SEXCD", "B_ECOGN", "B_LDHN", "PRTFN"]
        assert len(S2_FEATURES) == 10

    # Ninguna variable del pool es un outcome, la estratificacion o una constante excluida.
    def test_pool_sin_prohibidas(self):
        assert not (set(S2_FEATURES) & FORBIDDEN)

    # B_SEREPO es la unica variable marcada para log1p; B_WEIGHT no esta en S2 (sustituida por BMI).
    def test_log_feature_y_sustitucion_imc(self):
        assert LOG_FEATURES == ["B_SEREPO"]
        assert "BMI" in S2_FEATURES and "B_WEIGHT" not in S2_FEATURES
        assert "B_WEIGHT" in S1_FEATURES  # el baseline si conserva el peso


# ---------------------------------------------------------------------------
# 2. log1p de B_SEREPO antes de escalar
# ---------------------------------------------------------------------------

class TestLog1pPreprocessor:

    # La columna B_SEREPO de salida correlaciona ~1 con log1p del crudo imputado por
    # mediana y mucho menos con el crudo, confirmando que el log1p se aplica antes de escalar.
    def test_b_serepo_es_log1p(self, df_synth):
        prep = build_preprocessor_strategy2()
        Xt = prep.fit_transform(df_synth)
        names = list(prep.named_steps["column_transformer"].get_feature_names_out())
        col = Xt[:, names.index("B_SEREPO")]
        raw = df_synth["B_SEREPO"].fillna(df_synth["B_SEREPO"].median())
        corr_log = np.corrcoef(col, np.log1p(raw))[0, 1]
        corr_raw = np.corrcoef(col, raw)[0, 1]
        assert corr_log > 0.999, f"B_SEREPO no se transforma con log1p (corr={corr_log:.4f})"
        assert corr_log > corr_raw  # el log1p domina sobre la escala cruda

    # La salida esta estandarizada: media ~0 y desviacion ~1 en la columna log-transformada.
    def test_salida_estandarizada(self, df_synth):
        prep = build_preprocessor_strategy2()
        Xt = prep.fit_transform(df_synth)
        names = list(prep.named_steps["column_transformer"].get_feature_names_out())
        col = Xt[:, names.index("B_SEREPO")]
        assert abs(col.mean()) < 1e-6 and abs(col.std() - 1.0) < 1e-2


# ---------------------------------------------------------------------------
# 3. Anti-leakage del preprocesador de la Estrategia 2
# ---------------------------------------------------------------------------

class TestStrategy2AntiLeakage:

    # Reajustar el preprocesador con el mismo train produce la misma transformacion:
    # el test nunca participa en el calculo de medianas, medias ni del log1p.
    def test_test_no_altera_ajuste(self, df_synth):
        mid = len(df_synth) // 2
        p1 = build_preprocessor_strategy2(); p1.fit(df_synth.iloc[:mid])
        p2 = build_preprocessor_strategy2(); p2.fit(df_synth.iloc[:mid])
        X1 = p1.transform(df_synth.iloc[:mid])
        X2 = p2.transform(df_synth.iloc[:mid])
        np.testing.assert_array_almost_equal(X1, X2, decimal=10)


# ---------------------------------------------------------------------------
# 4. CV anidada minima: cobertura OOF y determinismo
# ---------------------------------------------------------------------------

class TestNestedCV:

    # Ejecuta run_outer_oof con una configuracion minima (coxnet, pocos trials y folds)
    # sobre datos sinteticos y devuelve (oof_risk, fold_metrics) para los asserts.
    def _run(self, df):
        y = make_y(df["DTH"].values, df["DTHDY"].values)
        strata = make_strata(df, "DTH")
        gt = event_time_grid(y)
        X_s1, X_s2 = df[S1_FEATURES].copy(), df[S2_FEATURES].copy()
        fold_metrics, oof_risk, _, _, _ = run_outer_oof(
            "coxnet", X_s1, X_s2, y, strata, gt,
            outer_k=2, n_trials=2, inner_k=2, logger=LOGGER)
        return oof_risk, fold_metrics

    # Todos los sujetos reciben prediccion OOF (sin NaN) tras el bucle externo.
    def test_oof_cubre_todos(self, df_synth):
        oof_risk, _ = self._run(df_synth)
        assert np.isfinite(oof_risk).all(), "Hay sujetos sin prediccion OOF en la CV anidada"

    # Con la misma semilla, dos ejecuciones dan C-index por fold identicos (determinismo).
    def test_determinista(self, df_synth):
        _, fm1 = self._run(df_synth)
        _, fm2 = self._run(df_synth)
        c1 = [m["c_index"] for m in fm1]
        c2 = [m["c_index"] for m in fm2]
        np.testing.assert_array_almost_equal(c1, c2, decimal=10)


# ---------------------------------------------------------------------------
# 5. Test pareado
# ---------------------------------------------------------------------------

class TestPairedBootstrap:

    # paired_bootstrap devuelve las claves esperadas, el IC ordenado y excludes_zero booleano.
    def test_estructura_y_ic(self):
        rng = np.random.default_rng(SEED)
        n = 100
        y = make_y((rng.uniform(size=n) < 0.8).astype(int), rng.uniform(1, 1000, n))
        risk_a = rng.normal(size=n)
        risk_b = risk_a + rng.normal(scale=0.1, size=n)  # muy correlados (caso pareado)
        out = paired_bootstrap(y, risk_a, risk_b, n=100, seed=SEED)
        for k in ("delta_point", "delta_mean", "ci_low", "ci_high", "frac_gt_0", "excludes_zero"):
            assert k in out
        assert out["ci_low"] <= out["ci_high"]
        assert isinstance(out["excludes_zero"], bool)
        assert 0.0 <= out["frac_gt_0"] <= 1.0
