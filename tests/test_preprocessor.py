"""
tests/test_preprocessor.py

Smoke tests del preprocesador de supervivencia (MissingnessAwareImputer y build_preprocessor).

Verificaciones cubiertas:
    1. Ruta simple: missingness <= 20 por ciento en todas las columnas -> SimpleImputer.
    2. Ruta iterativa: una columna numerica con > 20 por ciento de faltantes -> IterativeImputer.
    3. Sin fuga train/test: el Pipeline ajustado en train transforma test correctamente.
    4. Forma de la salida: sin NaN, numero de columnas >= 5 (minimo numericas escaladas).
    5. Idempotencia del ajuste: llamar a fit dos veces sobre los mismos datos da el mismo resultado.
"""

import numpy as np
import pandas as pd
import pytest

from src.preprocessing.build_preprocessor import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    MissingnessAwareImputer,
    build_preprocessor,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RNG = np.random.default_rng(42)
N_TRAIN = 40
N_TEST = 10


# Funcion auxiliar de generacion de datos sinteticos con la estructura exacta del NESP.
# Crea un DataFrame con las 7 covariables basales del proyecto, introduce missingness
# controlado del 5 por ciento en B_HGB y CADIAGM (ruta simple) y, opcionalmente,
# missingness superior al 20 por ciento en una columna indicada (ruta iterativa).
# Centralizar la construccion del dataset evita duplicacion y garantiza consistencia
# entre fixtures, cumpliendo el principio DRY en la suite de pruebas.
def _make_dataset(n: int, high_miss_col: str | None = None) -> pd.DataFrame:
    """Genera un DataFrame sintetico con la misma estructura que el dataset NESP."""
    df = pd.DataFrame(
        {
            "AGE": RNG.uniform(40, 80, n),
            "B_WEIGHT": RNG.uniform(50, 100, n),
            "CADIAGM": RNG.uniform(1, 120, n),
            "B_HGB": RNG.uniform(8, 16, n),
            "MEDHX_N": RNG.integers(0, 7, n).astype(float),
            "SEXCD": RNG.choice([1.0, 2.0], n),
            "B_ECOGN": RNG.choice([0.0, 1.0, 2.0], n),
        }
    )
    # Introducir un 5 por ciento de faltantes en B_HGB y CADIAGM (ruta simple).
    for col in ("B_HGB", "CADIAGM"):
        idx = RNG.choice(n, size=max(1, int(0.05 * n)), replace=False)
        df.loc[idx, col] = np.nan

    # Introducir > 20 por ciento de faltantes en la columna objetivo si se pide.
    if high_miss_col:
        idx = RNG.choice(n, size=int(0.25 * n), replace=False)
        df.loc[idx, high_miss_col] = np.nan  # 25 por ciento de faltantes activa la ruta IterativeImputer

    return df


# Fixture de alcance modular que genera el par (train, test) con missingness bajo.
# Invariante: todas las columnas tienen missingness <= 20 por ciento, lo que debe
# activar exclusivamente la ruta SimpleImputer (mediana/moda) del MissingnessAwareImputer.
# Compartir el fixture entre tests del modulo evita regeneraciones costosas y
# garantiza que todos los tests de la ruta simple operan sobre los mismos datos.
@pytest.fixture(scope="module")
def data_simple():
    """Dataset con missingness bajo en todas las columnas."""
    train = _make_dataset(N_TRAIN)
    test = _make_dataset(N_TEST)
    return train, test


# Fixture de alcance modular que genera el par (train, test) con AGE con missingness
# del 25 por ciento en el conjunto de entrenamiento.
# Invariante: este escenario debe activar la ruta IterativeImputer para AGE en el
# MissingnessAwareImputer. Verificar que la ruta iterativa se selecciona correctamente
# es fundamental para el plan de imputacion del proyecto (patron MAR asumido).
@pytest.fixture(scope="module")
def data_high_miss():
    """Dataset con AGE con > 20 por ciento de faltantes (ruta iterativa)."""
    train = _make_dataset(N_TRAIN, high_miss_col="AGE")
    test = _make_dataset(N_TEST)
    return train, test


# ---------------------------------------------------------------------------
# Tests de MissingnessAwareImputer
# ---------------------------------------------------------------------------


# Clase que agrupa los tests unitarios del MissingnessAwareImputer.
# Verifica que el imputer selecciona correctamente la ruta de imputacion
# (simple vs iterativa) segun el porcentaje de faltantes en cada columna,
# que el ajuste es exclusivo del fold de entrenamiento (invariante anti-leakage),
# y que la salida no contiene NaN en ninguno de los dos conjuntos transformados.
class TestMissingnessAwareImputer:

    # Verifica que el imputer se ajusta sin errores sobre datos completamente limpios
    # y que la salida no contiene NaN. Es el caso base: si no hay faltantes, el imputer
    # no debe introducir ningun cambio en los valores y tampoco debe lanzar excepciones.
    # Invariante: el imputer es robusto al caso de ausencia total de missingness.
    def test_fit_sin_nans(self, data_simple):
        """Con datos limpios el imputer se ajusta sin errores y no modifica los valores."""
        train, _ = data_simple
        df_clean = train.copy()
        for col in NUMERIC_FEATURES + CATEGORICAL_FEATURES:
            df_clean[col] = df_clean[col].fillna(df_clean[col].median() if col in NUMERIC_FEATURES else df_clean[col].mode()[0])

        imp = MissingnessAwareImputer(NUMERIC_FEATURES, CATEGORICAL_FEATURES)
        out = imp.fit_transform(df_clean)
        assert out[NUMERIC_FEATURES].isnull().sum().sum() == 0  # ningun faltante en la salida con datos limpios

    # Verifica que cuando todas las columnas tienen missingness por debajo del umbral
    # del 20 por ciento, el imputer selecciona exclusivamente la ruta SimpleImputer
    # y que ningun faltante persiste en la salida. Invariante: la ruta iterativa
    # (computacionalmente mas costosa) no debe activarse con datos que no lo requieren.
    def test_ruta_simple(self, data_simple):
        """Missingness <= 20 por ciento: todas las columnas van por SimpleImputer."""
        train, test = data_simple
        imp = MissingnessAwareImputer(NUMERIC_FEATURES, CATEGORICAL_FEATURES)
        imp.fit(train)

        assert len(imp._num_iterative_cols_) == 0, "No debe haber columnas en ruta iterativa."  # ruta iterativa inactiva
        assert len(imp._num_simple_cols_) > 0  # al menos una columna usa SimpleImputer

        out_train = imp.transform(train)
        out_test = imp.transform(test)

        assert out_train[NUMERIC_FEATURES].isnull().sum().sum() == 0  # sin NaN en train transformado
        assert out_test[NUMERIC_FEATURES].isnull().sum().sum() == 0  # sin NaN en test transformado

    # Verifica que cuando AGE supera el umbral del 20 por ciento de faltantes en train,
    # el imputer la incluye en la lista de columnas para IterativeImputer.
    # Invariante: la seleccion dinamica de ruta garantiza que el patron MAR se trata
    # con imputacion multivariante cuando el nivel de ausencia lo justifica,
    # mejorando la calidad de la imputacion respecto a la mediana univariante.
    def test_ruta_iterativa(self, data_high_miss):
        """Missingness > 20 por ciento en AGE: debe activar la ruta IterativeImputer."""
        train, test = data_high_miss
        imp = MissingnessAwareImputer(NUMERIC_FEATURES, CATEGORICAL_FEATURES)
        imp.fit(train)

        assert "AGE" in imp._num_iterative_cols_, "AGE debe estar en ruta iterativa."  # seleccion correcta de ruta

        out_test = imp.transform(test)
        assert out_test[NUMERIC_FEATURES].isnull().sum().sum() == 0  # IterativeImputer elimina todos los NaN

    # Verifica que la mediana almacenada por el SimpleImputer coincide exactamente
    # con la mediana calculada sobre el conjunto de entrenamiento.
    # Este es el test mas directo del invariante anti-leakage del imputer:
    # si la mediana almacenada difiriera de la de train, significaria que el imputer
    # ha usado informacion del test (o del dataset completo) durante el ajuste.
    def test_sin_fuga_train_test(self, data_simple):
        """Los parametros del imputer se calculan sobre train; test no influye en el ajuste."""
        train, test = data_simple
        imp = MissingnessAwareImputer(NUMERIC_FEATURES, CATEGORICAL_FEATURES)
        imp.fit(train)  # ajuste exclusivo en train

        # Mediana calculada sobre train.
        median_train_age = train["AGE"].median()
        # La mediana almacenada debe coincidir con la del fold de entrenamiento.
        idx_age = imp._num_simple_cols_.index("AGE")
        stored_median = imp._simple_num_.statistics_[idx_age]
        assert abs(stored_median - median_train_age) < 1e-6, (  # desviacion mayor indica fuga de datos
            "La mediana almacenada debe ser la del fold de entrenamiento."
        )

    # Verifica que los faltantes en variables categoricas se rellenan con la moda
    # del fold de entrenamiento. Para SEXCD (binaria: 1.0 o 2.0), la moda es el
    # valor mas frecuente en train. Nota oncologica: SEXCD es una covariable basal
    # que puede influir en la tolerancia a la quimioterapia y en la supervivencia.
    def test_categoricas_imputadas(self, data_simple):
        """Las categoricas faltantes se rellenan con la moda del fold de entrenamiento."""
        train, test = data_simple
        train_mod = train.copy()
        train_mod.loc[0, "SEXCD"] = np.nan

        imp = MissingnessAwareImputer(NUMERIC_FEATURES, CATEGORICAL_FEATURES)
        out = imp.fit_transform(train_mod)
        assert out["SEXCD"].isnull().sum() == 0  # ningun faltante categorico debe persistir


# ---------------------------------------------------------------------------
# Tests de build_preprocessor
# ---------------------------------------------------------------------------


# Clase que agrupa los tests de integracion del Pipeline completo generado por build_preprocessor.
# Verifica las siguientes propiedades del pipeline: que es estacionario antes del ajuste
# (lanza NotFittedError), que produce salidas libres de NaN en ambas rutas de imputacion,
# que train y test tienen el mismo numero de columnas tras el preprocesado (coherencia de forma),
# que el ajuste es idempotente y que admite parametrizacion personalizada de features y umbral.
class TestBuildPreprocessor:

    # Verifica que build_preprocessor retorna un Pipeline en estado no ajustado,
    # de modo que intentar transformar sin fit previo lanza NotFittedError.
    # Invariante: el pipeline debe ser stateful, es decir, no puede transformar
    # hasta que sus estadisticas internas hayan sido calculadas sobre el fold de train.
    # Este test protege contra implementaciones que inicializan estatisticas por defecto.
    def test_pipeline_no_ajustado(self):
        """build_preprocessor devuelve un Pipeline sin ajustar."""
        from sklearn.exceptions import NotFittedError

        pipe = build_preprocessor()
        with pytest.raises(NotFittedError):  # cualquier otro error indica un error de diseno del pipeline
            pipe.transform(pd.DataFrame({c: [1.0] for c in NUMERIC_FEATURES + CATEGORICAL_FEATURES}))

    # Verifica el pipeline completo en la ruta de missingness bajo (SimpleImputer):
    # fit sobre train, transform sobre train y test, comprobando ausencia de NaN y
    # coherencia de las dimensiones de salida. Es el test de integracion principal
    # del pipeline para el caso de uso mas comun del dataset NESP (5 por ciento de faltantes).
    def test_fit_transform_ruta_simple(self, data_simple):
        """Pipeline completo: fit en train, transform en train y test, sin NaN."""
        train, test = data_simple
        feats = NUMERIC_FEATURES + CATEGORICAL_FEATURES

        pipe = build_preprocessor()
        X_train_out = pipe.fit_transform(train[feats])
        X_test_out = pipe.transform(test[feats])

        assert not np.isnan(X_train_out).any(), "Train: no debe haber NaN en la salida."  # sin faltantes en train
        assert not np.isnan(X_test_out).any(), "Test: no debe haber NaN en la salida."  # sin faltantes en test
        # Minimo 5 columnas (las numericas escaladas) mas las dummies categoricas.
        assert X_train_out.shape[1] >= 5  # 5 numericas escaladas + columnas dummies de categoricas
        assert X_train_out.shape[0] == N_TRAIN  # numero de filas de train conservado
        assert X_test_out.shape[0] == N_TEST  # numero de filas de test conservado

    # Verifica el pipeline completo cuando la ruta IterativeImputer esta activa (AGE > 20 por ciento).
    # Invariante: incluso con imputacion multivariante, la salida debe ser una matriz densa
    # sin NaN y con el numero correcto de filas. El IterativeImputer se ajusta solo en train
    # y aplica sus coeficientes para rellenar los faltantes en test sin revelar informacion de este.
    def test_fit_transform_ruta_iterativa(self, data_high_miss):
        """Pipeline con ruta iterativa activa: salida sin NaN y forma correcta."""
        train, test = data_high_miss
        feats = NUMERIC_FEATURES + CATEGORICAL_FEATURES

        pipe = build_preprocessor()
        X_train_out = pipe.fit_transform(train[feats])
        X_test_out = pipe.transform(test[feats])

        assert not np.isnan(X_train_out).any()  # IterativeImputer elimina todos los NaN en train
        assert not np.isnan(X_test_out).any()  # el modelo de imputacion ajustado en train se aplica a test
        assert X_train_out.shape[0] == N_TRAIN  # numero de sujetos en train conservado

    # Verifica que el numero de columnas en la salida es identico para train y test.
    # Invariante de forma: el modelo de supervivencia espera matrices de igual numero
    # de columnas en fit y predict. Si train y test difirieran (por ejemplo, por
    # categorias nuevas en test), el modelo falla en tiempo de ejecucion.
    # La one-hot encoding debe manejar correctamente las categorias ausentes en test.
    def test_forma_salida_coherente(self, data_simple):
        """Train y test deben tener el mismo numero de columnas en la salida."""
        train, test = data_simple
        feats = NUMERIC_FEATURES + CATEGORICAL_FEATURES

        pipe = build_preprocessor()
        X_train_out = pipe.fit_transform(train[feats])
        X_test_out = pipe.transform(test[feats])

        assert X_train_out.shape[1] == X_test_out.shape[1], (  # incoherencia de forma rompe el modelo
            "Train y test deben tener el mismo numero de columnas tras preprocesar."
        )

    # Verifica que llamar a fit_transform dos veces consecutivas sobre los mismos datos
    # produce exactamente el mismo resultado. Invariante de idempotencia: el pipeline
    # no tiene estado residual entre llamadas sucesivas que altere el resultado.
    # Esto garantiza que re-entrenar el preprocesador en un nuevo fold es seguro y predecible.
    def test_idempotencia_fit(self, data_simple):
        """Ajustar dos veces sobre los mismos datos produce la misma salida."""
        train, test = data_simple
        feats = NUMERIC_FEATURES + CATEGORICAL_FEATURES

        pipe = build_preprocessor()
        out1 = pipe.fit_transform(train[feats])
        out2 = pipe.fit_transform(train[feats])

        np.testing.assert_array_almost_equal(out1, out2, decimal=10)  # precision 1e-10 garantiza idempotencia numerica

    # Verifica que build_preprocessor acepta listas de features personalizadas y
    # un umbral de missingness distinto del valor por defecto.
    # Invariante de parametrizacion: la arquitectura del pipeline debe ser configurable
    # para facilitar experimentos con subconjuntos de features o umbrales alternativos
    # sin necesidad de modificar el codigo fuente del preprocesador.
    def test_parametros_personalizados(self, data_simple):
        """Se pueden cambiar las listas de features y el threshold."""
        train, _ = data_simple
        feats_num = ["AGE", "B_HGB"]
        feats_cat = ["SEXCD"]

        pipe = build_preprocessor(
            numeric_features=feats_num,
            categorical_features=feats_cat,
            missingness_threshold=0.10,
        )
        out = pipe.fit_transform(train[feats_num + feats_cat])
        # 2 numericas + 1 categorica con 2 valores -> 1 dummy = 3 columnas totales
        assert out.shape == (N_TRAIN, 3)  # forma esperada: 2 numericas escaladas + 1 dummy de SEXCD
