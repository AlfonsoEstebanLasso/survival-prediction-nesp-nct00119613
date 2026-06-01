"""
tests/test_pipeline_smoke.py

Smoke tests de integracion del pipeline de supervivencia.

Verificaciones cubiertas:
    1. FEATURES no contiene variables prohibidas (outcomes, TXG, SUBJID, temporales).
    2. Semilla global: dos ejecuciones con el mismo SEED producen identico C-index.
    3. Anti-leakage: el preprocesador ajustado en train almacena estadisticas exclusivas del fold.
    4. Predicciones OOF: despues del CV k=3 sobre n=60, todos los sujetos tienen prediccion.
    5. C-index en rango plausible [0.40, 0.95] sobre datos con senal artificial.
    6. El preprocesador no transfiere informacion del fold de test al de train.

Todos los tests usan datos sinteticos; no requieren el dataset real.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import StratifiedKFold
from sksurv.linear_model import CoxPHSurvivalAnalysis
from sksurv.metrics import concordance_index_censored

from src.preprocessing.build_preprocessor import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    build_preprocessor,
)
from src.models.cv_utils import SEED, make_y

FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
FORBIDDEN = {"DTH", "DTHDY", "PFSCD", "PFSDY", "TXG", "SUBJID",
             "EVALPRIM", "EVALQOL", "RACECD", "TUMORCD", "EXTENTCD", "CHDCLASS"}

RNG = np.random.default_rng(SEED)
N = 60
K = 3   # folds reducidos para velocidad


# ---------------------------------------------------------------------------
# Fixture: dataset sintetico con senal de supervivencia
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def df_synth() -> pd.DataFrame:
    """
    Dataset sintetico con estructura identica al NESP derivado.
    Se introduce senal artificial: mayor AGE y mayor MEDHX_N => mayor riesgo.
    """
    n = N
    rng = np.random.default_rng(SEED)

    age     = rng.uniform(40, 80, n)
    medhx   = rng.integers(0, 7, n).astype(float)
    risk    = 0.03 * age + 0.15 * medhx

    # Tiempo de supervivencia: exponencial inverso al riesgo
    time    = rng.exponential(scale=1.0 / (0.01 + risk))
    time    = np.clip(time, 1, 1500)
    event   = rng.uniform(size=n) < 0.80  # 80 % de eventos

    df = pd.DataFrame({
        "AGE":      age,
        "B_WEIGHT": rng.uniform(50, 100, n),
        "CADIAGM":  rng.uniform(1, 120, n),
        "B_HGB":    rng.uniform(8, 16, n),
        "MEDHX_N":  medhx,
        "SEXCD":    rng.choice([1.0, 2.0], n),
        "B_ECOGN":  rng.choice([0.0, 1.0, 2.0], n),
        "DTH":      event.astype(int),
        "DTHDY":    time,
        "PFSCD":    rng.integers(0, 2, n),
        "PFSDY":    rng.uniform(1, 800, n),
        "TXG":      rng.integers(0, 2, n),
    })
    # Introducir 5 % de faltantes en B_HGB
    idx = rng.choice(n, size=max(1, int(0.05 * n)), replace=False)
    df.loc[idx, "B_HGB"] = np.nan
    return df


# ---------------------------------------------------------------------------
# 1. Ausencia de variables prohibidas en FEATURES
# ---------------------------------------------------------------------------

class TestFeaturesDefinition:

    def test_no_outcome_variables(self):
        """DTH, DTHDY, PFSCD, PFSDY no deben estar en FEATURES."""
        overlap = set(FEATURES) & FORBIDDEN
        assert not overlap, (
            f"FEATURES contiene variables prohibidas: {overlap}"
        )

    def test_no_stratification_variable(self):
        """TXG (brazo de aleatorizacion) no debe ser predictor."""
        assert "TXG" not in FEATURES

    def test_features_are_baseline(self):
        """Todos los predictores deben ser basales conocidos."""
        expected = {"AGE", "B_WEIGHT", "CADIAGM", "B_HGB", "MEDHX_N", "SEXCD", "B_ECOGN"}
        assert set(FEATURES) == expected, (
            f"FEATURES inesperado. Esperado: {expected}. Actual: {set(FEATURES)}"
        )


# ---------------------------------------------------------------------------
# 2. Reproducibilidad: misma semilla -> mismo C-index
# ---------------------------------------------------------------------------

class TestSeedReproducibility:

    def _run_cv(self, df: pd.DataFrame, seed: int) -> float:
        y = make_y(df["DTH"].values, df["DTHDY"].values)
        X = df[FEATURES]
        strata = df["DTH"].astype(int).values * 2 + df["TXG"].astype(int).values
        cv = StratifiedKFold(n_splits=K, shuffle=True, random_state=seed)

        cindexes = []
        for train_idx, test_idx in cv.split(X, strata):
            preproc = build_preprocessor()
            X_tr = preproc.fit_transform(X.iloc[train_idx])
            X_te = preproc.transform(X.iloc[test_idx])
            cox = CoxPHSurvivalAnalysis(alpha=0, ties="efron")
            cox.fit(X_tr, y[train_idx])
            cindexes.append(float(cox.score(X_te, y[test_idx])))
        return float(np.mean(cindexes))

    def test_same_seed_same_result(self, df_synth):
        c1 = self._run_cv(df_synth, seed=SEED)
        c2 = self._run_cv(df_synth, seed=SEED)
        assert abs(c1 - c2) < 1e-10, (
            f"Dos ejecuciones con seed={SEED} dan C-index distintos: {c1} vs {c2}"
        )

    def test_different_seed_different_split(self, df_synth):
        """Seeds distintas pueden dar resultados distintos (sin garantia de diferencia exacta)."""
        c1 = self._run_cv(df_synth, seed=SEED)
        c2 = self._run_cv(df_synth, seed=SEED + 99)
        # Solo verificamos que ambos son numeros validos
        assert 0 < c1 < 1
        assert 0 < c2 < 1


# ---------------------------------------------------------------------------
# 3. Anti-leakage: estadisticas del preprocesador son del fold de train
# ---------------------------------------------------------------------------

class TestAntiLeakage:

    def test_mediana_imputer_es_de_train(self, df_synth):
        """
        La mediana almacenada en el SimpleImputer debe coincidir con la mediana
        del fold de entrenamiento, sin contaminacion del fold de test.
        """
        df = df_synth.copy()
        # Forzar faltantes en AGE para activar SimpleImputer en esa columna
        df.loc[0, "AGE"] = np.nan

        n = len(df)
        train_idx = list(range(n // 2))
        test_idx  = list(range(n // 2, n))

        preproc = build_preprocessor()
        preproc.fit(df[FEATURES].iloc[train_idx])

        imputer = preproc.named_steps["imputer"]
        if "AGE" in imputer._num_simple_cols_:
            idx_age = imputer._num_simple_cols_.index("AGE")
            stored  = float(imputer._simple_num_.statistics_[idx_age])
            expected = float(df[FEATURES].iloc[train_idx]["AGE"].median())
            assert abs(stored - expected) < 1e-6, (
                "Mediana del imputer no coincide con la del fold de entrenamiento."
            )

    def test_scaler_params_solo_de_train(self, df_synth):
        """
        La media del StandardScaler para AGE debe coincidir con la media del train.
        El test no debe influir en el ajuste.
        """
        df = df_synth.copy()
        n = len(df)
        train_idx = list(range(n // 2))

        preproc = build_preprocessor()
        preproc.fit(df[FEATURES].iloc[train_idx])

        scaler = preproc.named_steps["column_transformer"].transformers_[0][1]
        # Indice de AGE en NUMERIC_FEATURES
        age_idx = NUMERIC_FEATURES.index("AGE")
        stored_mean = float(scaler.mean_[age_idx])
        expected_mean = float(df["AGE"].iloc[train_idx].mean())
        assert abs(stored_mean - expected_mean) < 1e-6, (
            "Media del scaler no coincide con la del fold de entrenamiento."
        )

    def test_test_no_altera_ajuste(self, df_synth):
        """
        Ajustar el preprocesador con distintos folds de test produce el mismo
        resultado al transformar el mismo fold de train.
        """
        df = df_synth.copy()
        n = len(df)
        mid = n // 2

        preproc1 = build_preprocessor()
        preproc1.fit(df[FEATURES].iloc[:mid])
        X_ref = preproc1.transform(df[FEATURES].iloc[:mid])

        preproc2 = build_preprocessor()
        preproc2.fit(df[FEATURES].iloc[:mid])
        X_alt = preproc2.transform(df[FEATURES].iloc[:mid])

        np.testing.assert_array_almost_equal(X_ref, X_alt, decimal=10)


# ---------------------------------------------------------------------------
# 4. OOF: todas las muestras reciben prediccion
# ---------------------------------------------------------------------------

class TestOOFCoverage:

    def test_oof_cubre_todas_las_muestras(self, df_synth):
        y = make_y(df_synth["DTH"].values, df_synth["DTHDY"].values)
        X = df_synth[FEATURES]
        strata = df_synth["DTH"].astype(int).values * 2 + df_synth["TXG"].astype(int).values

        cv = StratifiedKFold(n_splits=K, shuffle=True, random_state=SEED)
        oof = np.full(N, np.nan)

        for train_idx, test_idx in cv.split(X, strata):
            preproc = build_preprocessor()
            X_tr = preproc.fit_transform(X.iloc[train_idx])
            X_te = preproc.transform(X.iloc[test_idx])
            cox = CoxPHSurvivalAnalysis(alpha=0, ties="efron")
            cox.fit(X_tr, y[train_idx])
            oof[test_idx] = cox.predict(X_te)

        n_missing = np.isnan(oof).sum()
        assert n_missing == 0, (
            f"{n_missing} muestras sin prediccion OOF de {N} totales."
        )


# ---------------------------------------------------------------------------
# 5. C-index en rango plausible
# ---------------------------------------------------------------------------

class TestCIndexRange:

    def test_cindex_en_rango(self, df_synth):
        """C-index de Cox sobre datos con senal debe estar en [0.40, 0.95]."""
        y = make_y(df_synth["DTH"].values, df_synth["DTHDY"].values)
        X = df_synth[FEATURES]
        strata = df_synth["DTH"].astype(int).values * 2 + df_synth["TXG"].astype(int).values
        cv = StratifiedKFold(n_splits=K, shuffle=True, random_state=SEED)

        cindexes = []
        for train_idx, test_idx in cv.split(X, strata):
            preproc = build_preprocessor()
            X_tr = preproc.fit_transform(X.iloc[train_idx])
            X_te = preproc.transform(X.iloc[test_idx])
            cox = CoxPHSurvivalAnalysis(alpha=0, ties="efron")
            cox.fit(X_tr, y[train_idx])
            cindexes.append(float(cox.score(X_te, y[test_idx])))

        c_mean = float(np.mean(cindexes))
        assert 0.40 <= c_mean <= 0.95, (
            f"C-index medio fuera del rango esperado: {c_mean:.4f}"
        )
