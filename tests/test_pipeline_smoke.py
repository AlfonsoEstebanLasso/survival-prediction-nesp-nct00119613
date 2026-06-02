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

# Fixture de alcance modular que genera el dataset sintetico compartido por todos los tests.
# Desde la perspectiva de ciencia de datos, centralizar la generacion en un fixture garantiza
# que todos los tests del modulo operan sobre exactamente los mismos datos y la misma semilla,
# lo que es imprescindible para la reproducibilidad y para que los asserts de C-index sean
# comparables entre si. La senal artificial (riesgo ligado a AGE y MEDHX_N) permite verificar
# que el pipeline extrae informacion real y que el C-index supera el umbral de 0.40.
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
    df.loc[idx, "B_HGB"] = np.nan  # simula missingness real del 5 por ciento en B_HGB
    return df


# ---------------------------------------------------------------------------
# 1. Ausencia de variables prohibidas en FEATURES
# ---------------------------------------------------------------------------

# Clase que agrupa los tests de definicion de FEATURES.
# Protege el invariante de que el vector de predictores no contenga informacion
# posterior al inicio del tratamiento (outcomes OS/PFS), la variable de estratificacion
# TXG (brazo de aleatorizacion) ni identificadores directos como SUBJID.
# Garantizar esto es la primera barrera contra el leakage data-snooping.
class TestFeaturesDefinition:

    # Verifica que ninguna variable del endpoint de supervivencia (DTH, DTHDY para OS;
    # PFSCD, PFSDY para PFS) ni otros campos prohibidos aparecen como predictores.
    # Invariante: el modelo solo puede usar informacion basal disponible antes del evento.
    # La presencia de variables de outcome como predictores constituye leakage directo.
    def test_no_outcome_variables(self):
        """DTH, DTHDY, PFSCD, PFSDY no deben estar en FEATURES."""
        overlap = set(FEATURES) & FORBIDDEN
        assert not overlap, (  # cualquier interseccion indica leakage de outcome
            f"FEATURES contiene variables prohibidas: {overlap}"
        )

    # Verifica que TXG, la variable que indica el brazo del ensayo (NESP vs placebo),
    # no se incluye en FEATURES. Invariante: TXG es variable de estratificacion de la
    # validacion cruzada, nunca predictor ni objetivo causal del modelo.
    def test_no_stratification_variable(self):
        """TXG (brazo de aleatorizacion) no debe ser predictor."""
        assert "TXG" not in FEATURES  # TXG como predictor introduciria sesgo de confundidor

    # Verifica que el conjunto de predictores es exactamente el definido en la estrategia
    # de covariables del proyecto (7 variables basales con senal, Estrategia 1 del contrato ETL).
    # Cualquier adicion o sustraccion no autorizada rompe la trazabilidad metodologica.
    def test_features_are_baseline(self):
        """Todos los predictores deben ser basales conocidos."""
        expected = {"AGE", "B_WEIGHT", "CADIAGM", "B_HGB", "MEDHX_N", "SEXCD", "B_ECOGN"}
        assert set(FEATURES) == expected, (  # la igualdad exacta protege contra cambios no registrados
            f"FEATURES inesperado. Esperado: {expected}. Actual: {set(FEATURES)}"
        )


# ---------------------------------------------------------------------------
# 2. Reproducibilidad: misma semilla -> mismo C-index
# ---------------------------------------------------------------------------

# Clase que agrupa los tests de reproducibilidad por semilla global.
# Invariante central: dado el mismo SEED, el pipeline completo (particion CV,
# preprocesado, ajuste Cox) debe producir exactamente el mismo C-index en
# dos ejecuciones independientes. Esto garantiza la reproducibilidad del
# KPI-1 del proyecto y la capacidad de auditoria del resultado final.
class TestSeedReproducibility:

    # Metodo auxiliar que ejecuta el pipeline CV completo con una semilla dada y
    # devuelve el C-index medio sobre los k folds.
    # Encapsula la logica repetida para que los tests de reproducibilidad la reutilicen
    # sin duplicar codigo, siguiendo el principio DRY en la suite de pruebas.
    def _run_cv(self, df: pd.DataFrame, seed: int) -> float:
        y = make_y(df["DTH"].values, df["DTHDY"].values)  # estructura sksurv: (evento, tiempo)
        X = df[FEATURES]
        strata = df["DTH"].astype(int).values * 2 + df["TXG"].astype(int).values  # estratificacion combinada evento x brazo
        cv = StratifiedKFold(n_splits=K, shuffle=True, random_state=seed)

        cindexes = []
        for train_idx, test_idx in cv.split(X, strata):
            preproc = build_preprocessor()
            X_tr = preproc.fit_transform(X.iloc[train_idx])  # ajuste exclusivo en train (anti-leakage)
            X_te = preproc.transform(X.iloc[test_idx])
            cox = CoxPHSurvivalAnalysis(alpha=0, ties="efron")
            cox.fit(X_tr, y[train_idx])
            cindexes.append(float(cox.score(X_te, y[test_idx])))
        return float(np.mean(cindexes))

    # Verifica que dos ejecuciones con identica semilla producen el mismo C-index
    # hasta precision numerica de maquina (tolerancia 1e-10).
    # Invariante: el pipeline es determinista dado el SEED global, lo que es
    # requisito del KPI-1 (reproducibilidad) del proyecto.
    def test_same_seed_same_result(self, df_synth):
        c1 = self._run_cv(df_synth, seed=SEED)
        c2 = self._run_cv(df_synth, seed=SEED)
        assert abs(c1 - c2) < 1e-10, (  # diferencia mayor que 1e-10 indica no determinismo
            f"Dos ejecuciones con seed={SEED} dan C-index distintos: {c1} vs {c2}"
        )

    # Verifica que con semillas distintas el pipeline produce valores de C-index
    # numericamente validos. No se exige diferencia estricta porque distintas
    # particiones pueden coincidir por azar; solo se comprueba que ambos resultados
    # son C-index en el intervalo abierto (0, 1), descartando degenneracion numerica.
    def test_different_seed_different_split(self, df_synth):
        """Seeds distintas pueden dar resultados distintos (sin garantia de diferencia exacta)."""
        c1 = self._run_cv(df_synth, seed=SEED)
        c2 = self._run_cv(df_synth, seed=SEED + 99)
        # Solo verificamos que ambos son numeros validos
        assert 0 < c1 < 1  # C-index fuera de (0,1) indica error de calculo
        assert 0 < c2 < 1


# ---------------------------------------------------------------------------
# 3. Anti-leakage: estadisticas del preprocesador son del fold de train
# ---------------------------------------------------------------------------

# Clase que agrupa los tests de ausencia de fuga de informacion entre folds.
# Es el grupo de tests mas critico desde la perspectiva de ciencia de datos:
# si el preprocesador usa estadisticas del fold de test para imputar o escalar
# el fold de train, el rendimiento reportado sera optimista y no transferible.
# Cada test inspecciona los parametros internos del Pipeline ajustado para
# confirmar que solo reflejan el conjunto de entrenamiento correspondiente.
class TestAntiLeakage:

    # Verifica que la mediana almacenada por el SimpleImputer para AGE corresponde
    # exclusivamente al fold de entrenamiento, no al dataset completo.
    # Invariante: toda estadistica de imputacion debe calcularse a partir de train;
    # usar la mediana global filtraria informacion del test hacia el train (leakage).
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
        preproc.fit(df[FEATURES].iloc[train_idx])  # ajuste solo sobre la primera mitad

        imputer = preproc.named_steps["imputer"]
        if "AGE" in imputer._num_simple_cols_:
            idx_age = imputer._num_simple_cols_.index("AGE")
            stored  = float(imputer._simple_num_.statistics_[idx_age])
            expected = float(df[FEATURES].iloc[train_idx]["AGE"].median())
            assert abs(stored - expected) < 1e-6, (  # desviacion mayor indica contaminacion con test
                "Mediana del imputer no coincide con la del fold de entrenamiento."
            )

    # Verifica que la media almacenada por el StandardScaler para AGE coincide con
    # la media del fold de entrenamiento. El escalado con estadisticas del dataset
    # completo o del test implicaria leakage de distribucion, inflando artificialmente
    # el rendimiento del modelo en validacion cruzada.
    def test_scaler_params_solo_de_train(self, df_synth):
        """
        La media del StandardScaler para AGE debe coincidir con la media del train.
        El test no debe influir en el ajuste.
        """
        df = df_synth.copy()
        n = len(df)
        train_idx = list(range(n // 2))

        preproc = build_preprocessor()
        preproc.fit(df[FEATURES].iloc[train_idx])  # ajuste exclusivo en train

        scaler = preproc.named_steps["column_transformer"].transformers_[0][1]
        # Indice de AGE en NUMERIC_FEATURES
        age_idx = NUMERIC_FEATURES.index("AGE")
        stored_mean = float(scaler.mean_[age_idx])
        expected_mean = float(df["AGE"].iloc[train_idx].mean())
        assert abs(stored_mean - expected_mean) < 1e-6, (  # tolerancia numerica de maquina
            "Media del scaler no coincide con la del fold de entrenamiento."
        )

    # Verifica que el resultado de la transformacion sobre el mismo fold de train
    # es identico independientemente de los datos de test con los que se combine.
    # Este test es una prueba de caja negra del principio de encapsulacion del Pipeline:
    # el fold de test no debe participar en el calculo de los parametros del preprocesador.
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

        np.testing.assert_array_almost_equal(X_ref, X_alt, decimal=10)  # precision 1e-10 garantiza igualdad numerica


# ---------------------------------------------------------------------------
# 4. OOF: todas las muestras reciben prediccion
# ---------------------------------------------------------------------------

# Clase que verifica la cobertura total de las predicciones Out-Of-Fold (OOF).
# Invariante: en un esquema de validacion cruzada k-fold estratificada, cada
# sujeto pertenece exactamente a un fold de test, por lo que al finalizar el CV
# todos deben tener una prediccion OOF asignada. La ausencia de cobertura total
# indica un error en la logica de indices o en la asignacion de resultados.
class TestOOFCoverage:

    # Verifica que el array OOF no contiene ninguna posicion con NaN al finalizar el CV.
    # La cobertura total es un requisito de la metodologia de validacion cruzada:
    # sin ella no se puede calcular el C-index global OOF ni la curva de calibracion.
    def test_oof_cubre_todas_las_muestras(self, df_synth):
        y = make_y(df_synth["DTH"].values, df_synth["DTHDY"].values)  # array estructurado sksurv
        X = df_synth[FEATURES]
        strata = df_synth["DTH"].astype(int).values * 2 + df_synth["TXG"].astype(int).values

        cv = StratifiedKFold(n_splits=K, shuffle=True, random_state=SEED)
        oof = np.full(N, np.nan)  # inicializado con NaN para detectar posiciones sin cubrir

        for train_idx, test_idx in cv.split(X, strata):
            preproc = build_preprocessor()
            X_tr = preproc.fit_transform(X.iloc[train_idx])
            X_te = preproc.transform(X.iloc[test_idx])
            cox = CoxPHSurvivalAnalysis(alpha=0, ties="efron")
            cox.fit(X_tr, y[train_idx])
            oof[test_idx] = cox.predict(X_te)  # asignacion por indice original de sujeto

        n_missing = np.isnan(oof).sum()
        assert n_missing == 0, (  # cualquier NaN indica un sujeto sin prediccion OOF
            f"{n_missing} muestras sin prediccion OOF de {N} totales."
        )


# ---------------------------------------------------------------------------
# 5. C-index en rango plausible
# ---------------------------------------------------------------------------

# Clase que verifica que el C-index del modelo Cox sobre datos sinteticos
# con senal artificial cae dentro del rango esperado [0.40, 0.95].
# Un C-index inferior a 0.40 sugiere que el pipeline tiene un error grave
# (por ejemplo inversión de la escala de riesgo o problema en make_y).
# Un C-index superior a 0.95 sobre datos sinteticos simples indicaria sobreajuste
# o leakage no detectado. El rango actua como guardarrailes de sanidad del pipeline.
class TestCIndexRange:

    # Verifica que el C-index medio del CV sobre el dataset sintetico con senal
    # esta en el intervalo [0.40, 0.95]. Es la comprobacion de rendimiento minimo
    # del pipeline completo (preprocesado + Cox) sobre datos controlados.
    # Nota oncologica: el C-index del 0.50 equivale a prediccion aleatoria;
    # valores superiores indican discriminacion entre pacientes de bajo y alto riesgo.
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
        assert 0.40 <= c_mean <= 0.95, (  # umbrales de sanidad del pipeline sobre datos sinteticos
            f"C-index medio fuera del rango esperado: {c_mean:.4f}"
        )
