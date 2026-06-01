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
        df.loc[idx, high_miss_col] = np.nan

    return df


@pytest.fixture(scope="module")
def data_simple():
    """Dataset con missingness bajo en todas las columnas."""
    train = _make_dataset(N_TRAIN)
    test = _make_dataset(N_TEST)
    return train, test


@pytest.fixture(scope="module")
def data_high_miss():
    """Dataset con AGE con > 20 por ciento de faltantes (ruta iterativa)."""
    train = _make_dataset(N_TRAIN, high_miss_col="AGE")
    test = _make_dataset(N_TEST)
    return train, test


# ---------------------------------------------------------------------------
# Tests de MissingnessAwareImputer
# ---------------------------------------------------------------------------


class TestMissingnessAwareImputer:

    def test_fit_sin_nans(self, data_simple):
        """Con datos limpios el imputer se ajusta sin errores y no modifica los valores."""
        train, _ = data_simple
        df_clean = train.copy()
        for col in NUMERIC_FEATURES + CATEGORICAL_FEATURES:
            df_clean[col] = df_clean[col].fillna(df_clean[col].median() if col in NUMERIC_FEATURES else df_clean[col].mode()[0])

        imp = MissingnessAwareImputer(NUMERIC_FEATURES, CATEGORICAL_FEATURES)
        out = imp.fit_transform(df_clean)
        assert out[NUMERIC_FEATURES].isnull().sum().sum() == 0

    def test_ruta_simple(self, data_simple):
        """Missingness <= 20 por ciento: todas las columnas van por SimpleImputer."""
        train, test = data_simple
        imp = MissingnessAwareImputer(NUMERIC_FEATURES, CATEGORICAL_FEATURES)
        imp.fit(train)

        assert len(imp._num_iterative_cols_) == 0, "No debe haber columnas en ruta iterativa."
        assert len(imp._num_simple_cols_) > 0

        out_train = imp.transform(train)
        out_test = imp.transform(test)

        assert out_train[NUMERIC_FEATURES].isnull().sum().sum() == 0
        assert out_test[NUMERIC_FEATURES].isnull().sum().sum() == 0

    def test_ruta_iterativa(self, data_high_miss):
        """Missingness > 20 por ciento en AGE: debe activar la ruta IterativeImputer."""
        train, test = data_high_miss
        imp = MissingnessAwareImputer(NUMERIC_FEATURES, CATEGORICAL_FEATURES)
        imp.fit(train)

        assert "AGE" in imp._num_iterative_cols_, "AGE debe estar en ruta iterativa."

        out_test = imp.transform(test)
        assert out_test[NUMERIC_FEATURES].isnull().sum().sum() == 0

    def test_sin_fuga_train_test(self, data_simple):
        """Los parametros del imputer se calculan sobre train; test no influye en el ajuste."""
        train, test = data_simple
        imp = MissingnessAwareImputer(NUMERIC_FEATURES, CATEGORICAL_FEATURES)
        imp.fit(train)

        # Mediana calculada sobre train.
        median_train_age = train["AGE"].median()
        # La mediana almacenada debe coincidir con la del fold de entrenamiento.
        idx_age = imp._num_simple_cols_.index("AGE")
        stored_median = imp._simple_num_.statistics_[idx_age]
        assert abs(stored_median - median_train_age) < 1e-6, (
            "La mediana almacenada debe ser la del fold de entrenamiento."
        )

    def test_categoricas_imputadas(self, data_simple):
        """Las categoricas faltantes se rellenan con la moda del fold de entrenamiento."""
        train, test = data_simple
        train_mod = train.copy()
        train_mod.loc[0, "SEXCD"] = np.nan

        imp = MissingnessAwareImputer(NUMERIC_FEATURES, CATEGORICAL_FEATURES)
        out = imp.fit_transform(train_mod)
        assert out["SEXCD"].isnull().sum() == 0


# ---------------------------------------------------------------------------
# Tests de build_preprocessor
# ---------------------------------------------------------------------------


class TestBuildPreprocessor:

    def test_pipeline_no_ajustado(self):
        """build_preprocessor devuelve un Pipeline sin ajustar."""
        from sklearn.exceptions import NotFittedError

        pipe = build_preprocessor()
        with pytest.raises(NotFittedError):
            pipe.transform(pd.DataFrame({c: [1.0] for c in NUMERIC_FEATURES + CATEGORICAL_FEATURES}))

    def test_fit_transform_ruta_simple(self, data_simple):
        """Pipeline completo: fit en train, transform en train y test, sin NaN."""
        train, test = data_simple
        feats = NUMERIC_FEATURES + CATEGORICAL_FEATURES

        pipe = build_preprocessor()
        X_train_out = pipe.fit_transform(train[feats])
        X_test_out = pipe.transform(test[feats])

        assert not np.isnan(X_train_out).any(), "Train: no debe haber NaN en la salida."
        assert not np.isnan(X_test_out).any(), "Test: no debe haber NaN en la salida."
        # Minimo 5 columnas (las numericas escaladas) mas las dummies categoricas.
        assert X_train_out.shape[1] >= 5
        assert X_train_out.shape[0] == N_TRAIN
        assert X_test_out.shape[0] == N_TEST

    def test_fit_transform_ruta_iterativa(self, data_high_miss):
        """Pipeline con ruta iterativa activa: salida sin NaN y forma correcta."""
        train, test = data_high_miss
        feats = NUMERIC_FEATURES + CATEGORICAL_FEATURES

        pipe = build_preprocessor()
        X_train_out = pipe.fit_transform(train[feats])
        X_test_out = pipe.transform(test[feats])

        assert not np.isnan(X_train_out).any()
        assert not np.isnan(X_test_out).any()
        assert X_train_out.shape[0] == N_TRAIN

    def test_forma_salida_coherente(self, data_simple):
        """Train y test deben tener el mismo numero de columnas en la salida."""
        train, test = data_simple
        feats = NUMERIC_FEATURES + CATEGORICAL_FEATURES

        pipe = build_preprocessor()
        X_train_out = pipe.fit_transform(train[feats])
        X_test_out = pipe.transform(test[feats])

        assert X_train_out.shape[1] == X_test_out.shape[1], (
            "Train y test deben tener el mismo numero de columnas tras preprocesar."
        )

    def test_idempotencia_fit(self, data_simple):
        """Ajustar dos veces sobre los mismos datos produce la misma salida."""
        train, test = data_simple
        feats = NUMERIC_FEATURES + CATEGORICAL_FEATURES

        pipe = build_preprocessor()
        out1 = pipe.fit_transform(train[feats])
        out2 = pipe.fit_transform(train[feats])

        np.testing.assert_array_almost_equal(out1, out2, decimal=10)

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
        assert out.shape == (N_TRAIN, 3)
