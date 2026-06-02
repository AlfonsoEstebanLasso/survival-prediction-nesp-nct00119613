"""
src/preprocessing/build_preprocessor.py

Proposito:
    Construir el Pipeline de preprocesado para el modelado de supervivencia del
    ensayo NESP NCT00119613. El Pipeline encapsula imputacion adaptativa por columna,
    estandarizacion de numericas y codificacion one-hot de categoricas, sin fuga de
    informacion entre el fold de entrenamiento y el de validacion.

Entradas:
    numeric_features     -- lista de nombres de columnas numericas (default: 5 predictores)
    categorical_features -- lista de nombres de columnas categoricas (default: 2 predictores)
    missingness_threshold -- porcentaje maximo para usar imputacion simple (default 0.20)
    seed                 -- semilla de aleatorizacion (default 42)

Salidas:
    Pipeline(MissingnessAwareImputer -> ColumnTransformer) sin ajustar.
    Se debe llamar a .fit() SOLO sobre el fold de entrenamiento dentro del esquema CV.

Transformaciones:
    1. MissingnessAwareImputer (ajustado en el fold de entrenamiento):
       - Tasa de missingness <= threshold: mediana (numericas) o moda (categoricas).
       - Tasa de missingness >  threshold: IterativeImputer sobre todas las numericas
         (supuesto MAR; se usa el conjunto completo de numericas como contexto).
       - Las categoricas usan siempre moda: IterativeImputer no soporta categoricas nativas.
    2. StandardScaler sobre las columnas numericas (media 0, desviacion tipica 1).
    3. OneHotEncoder sobre las columnas categoricas (drop='first', handle_unknown='ignore').
       La salida es densa (sparse_output=False).

Control anti-leakage:
    Todas las estadisticas de ajuste (medianas, modas, parametros del IterativeImputer,
    media y desviacion tipica del scaler, categorias del encoder) se calculan SOLO a partir
    de los datos del fold de entrenamiento. El fold de validacion se transforma pero nunca
    influye en el ajuste.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer, SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.utils.validation import check_is_fitted

SEED: int = 42
MISSINGNESS_THRESHOLD: float = 0.20

NUMERIC_FEATURES: list[str] = ["AGE", "B_WEIGHT", "CADIAGM", "B_HGB", "MEDHX_N"]
CATEGORICAL_FEATURES: list[str] = ["SEXCD", "B_ECOGN"]


# Transformador personalizado que selecciona la estrategia de imputacion por columna
# en funcion de la tasa de faltantes calculada UNICAMENTE sobre el fold de entrenamiento.
# Hereda de BaseEstimator y TransformerMixin para integrarse en la API de scikit-learn
# (metodos fit, transform y get_params disponibles sin implementacion adicional).
# Justificacion: la eleccion adaptativa del imputador optimiza la reconstruccion de la
# distribucion marginal cuando el patron de datos faltantes es MAR (Missing At Random),
# hipotesis razonable para variables basales en un ensayo controlado aleatorizado.
class MissingnessAwareImputer(BaseEstimator, TransformerMixin):
    """
    Imputer que elige la estrategia por columna en el momento del ajuste, usando
    unicamente los datos del fold de entrenamiento.

    Reglas de decision (aplicadas en fit):
        - Numericas con tasa de faltantes <= threshold:
              SimpleImputer(strategy='median')
        - Numericas con tasa de faltantes >  threshold:
              IterativeImputer ajustado sobre TODAS las numericas como contexto
              (supuesto MAR; la correlacion entre variables mejora la estimacion).
        - Categoricas (independientemente de la tasa):
              SimpleImputer(strategy='most_frequent')

    El IterativeImputer se ajusta sobre el bloque completo de columnas numericas para
    que las columnas sin faltantes sirvan de contexto. En transform, solo se sobreescriben
    las posiciones que originalmente tenian missingness alto; las demas ya estaban limpias
    o se imputaron por mediana.

    Parametros
    ----------
    numeric_features : list[str]
        Nombres de las columnas numericas a imputar.
    categorical_features : list[str]
        Nombres de las columnas categoricas a imputar.
    threshold : float
        Tasa de missingness (entre 0 y 1) que divide las estrategias de imputacion.
    seed : int
        Semilla para el IterativeImputer.
    """

    def __init__(
        self,
        numeric_features: list[str],
        categorical_features: list[str],
        threshold: float = MISSINGNESS_THRESHOLD,
        seed: int = SEED,
    ) -> None:
        self.numeric_features = numeric_features
        self.categorical_features = categorical_features
        self.threshold = threshold
        self.seed = seed

    # ------------------------------------------------------------------
    # Privado
    # ------------------------------------------------------------------

    # Filtra la lista de columnas retornando solo las que existen en el DataFrame.
    # Evita KeyError cuando el conjunto de predictores difiere del esperado por defecto.
    @staticmethod
    def _present(X: pd.DataFrame, cols: list[str]) -> list[str]:
        return [c for c in cols if c in X.columns]

    # ------------------------------------------------------------------
    # API sklearn
    # ------------------------------------------------------------------

    # Ajusta el imputer sobre los datos de entrenamiento del fold actual.
    # Entradas: X (DataFrame con predictores), y ignorado (compatibilidad sklearn).
    # Salida: self con los atributos de ajuste almacenados (sufijo '_').
    # Paso metodologico clave: calcula la tasa de missingness por columna y asigna
    # cada columna numerica al imputador correspondiente segun el umbral configurado.
    # Todo el ajuste ocurre UNICAMENTE sobre el fold de entrenamiento, garantizando
    # que el fold de validacion no influye en las estadisticas de imputacion (anti-fuga).
    def fit(self, X: pd.DataFrame, y=None) -> "MissingnessAwareImputer":
        X = pd.DataFrame(X)
        num_cols = self._present(X, self.numeric_features)
        cat_cols = self._present(X, self.categorical_features)

        # Tasas de missingness calculadas SOLO sobre el fold de entrenamiento.
        self._num_simple_cols_: list[str] = []
        self._num_iterative_cols_: list[str] = []
        self._all_num_cols_: list[str] = num_cols

        if num_cols:
            miss_rate = X[num_cols].isnull().mean()
            # Umbral de missingness: <=threshold -> mediana; >threshold -> imputacion iterativa MAR.
            self._num_simple_cols_ = [c for c in num_cols if miss_rate[c] <= self.threshold]
            self._num_iterative_cols_ = [c for c in num_cols if miss_rate[c] > self.threshold]

        self._cat_cols_: list[str] = cat_cols

        # Imputer simple para numericas con missingness bajo.
        if self._num_simple_cols_:
            self._simple_num_: SimpleImputer = SimpleImputer(strategy="median")
            self._simple_num_.fit(X[self._num_simple_cols_])

        # Imputer iterativo para numericas con missingness alto.
        # Se ajusta sobre todas las numericas para aprovechar el contexto correlacional.
        if self._num_iterative_cols_:
            self._iterative_: IterativeImputer = IterativeImputer(
                random_state=self.seed,  # semilla fija para reproducibilidad del algoritmo iterativo
                max_iter=10,
                skip_complete=True,
            )
            self._iterative_.fit(X[num_cols].values)

        # Imputer de moda para categoricas.
        if self._cat_cols_:
            self._simple_cat_: SimpleImputer = SimpleImputer(strategy="most_frequent")
            self._simple_cat_.fit(X[self._cat_cols_])

        return self

    # Aplica la imputacion ajustada sobre cualquier conjunto (train o validacion).
    # Entradas: X (DataFrame, puede contener NaN). Salida: DataFrame sin NaN en las
    # columnas numericas y categoricas gestionadas.
    # El orden de aplicacion (mediana -> iterativa -> moda) garantiza que las columnas
    # con missingness bajo esten completas antes de que el IterativeImputer use el
    # bloque completo de numericas como contexto.
    def transform(self, X: pd.DataFrame, y=None) -> pd.DataFrame:
        check_is_fitted(self, ["_all_num_cols_", "_cat_cols_"])
        X = pd.DataFrame(X).copy()

        # 1. Imputacion por mediana de numericas con missingness bajo.
        if self._num_simple_cols_:
            X[self._num_simple_cols_] = self._simple_num_.transform(
                X[self._num_simple_cols_]
            )

        # 2. Imputacion iterativa de numericas con missingness alto.
        #    Se transforma el bloque completo y solo se sobreescriben las columnas objetivo.
        if self._num_iterative_cols_:
            all_num = self._all_num_cols_
            imputed_matrix = self._iterative_.transform(X[all_num].values)
            imputed_df = pd.DataFrame(imputed_matrix, columns=all_num, index=X.index)
            X[self._num_iterative_cols_] = imputed_df[self._num_iterative_cols_]

        # 3. Imputacion por moda de categoricas.
        if self._cat_cols_:
            X[self._cat_cols_] = self._simple_cat_.transform(X[self._cat_cols_])

        return X


# Fabrica que ensambla el Pipeline completo de preprocesado sin ajustarlo.
# Entradas: listas opcionales de predictores numericos y categoricos, umbral de
# missingness y semilla. Salida: Pipeline de scikit-learn listo para recibir
# fit() dentro del fold de entrenamiento de la CV estratificada k=5.
# Justificacion: encapsular el Pipeline garantiza que las estadisticas de ajuste
# (medianas, modas, parametros del IterativeImputer, media/std del StandardScaler,
# categorias del OneHotEncoder) solo se calculan sobre el fold de entrenamiento,
# cumpliendo el invariante anti-fuga establecido en la metodologia del proyecto.
# El ColumnTransformer divide el flujo en dos ramas: estandarizacion de numericas
# y codificacion one-hot de categoricas (drop='first' para evitar multicolinealidad).
def build_preprocessor(
    numeric_features: list[str] | None = None,
    categorical_features: list[str] | None = None,
    *,
    missingness_threshold: float = MISSINGNESS_THRESHOLD,
    seed: int = SEED,
) -> Pipeline:
    """
    Construye el Pipeline de preprocesado para el modelado de supervivencia.

    El Pipeline NO esta ajustado al devolverse. En el esquema de validacion cruzada
    estratificada k=5 del TFG, se debe llamar a preprocessor.fit(X_train) dentro de
    cada fold y usar preprocessor.transform(X_val) para el fold de validacion.

    Parametros
    ----------
    numeric_features : list[str] | None
        Nombres de las columnas numericas. Si None, usa NUMERIC_FEATURES por defecto.
    categorical_features : list[str] | None
        Nombres de las columnas categoricas. Si None, usa CATEGORICAL_FEATURES por defecto.
    missingness_threshold : float
        Porcentaje maximo de faltantes (0 a 1) para usar imputacion simple. Default 0.20.
    seed : int
        Semilla de aleatorizacion para el IterativeImputer. Default 42.

    Devuelve
    -------
    Pipeline
        Pasos: [('imputer', MissingnessAwareImputer), ('column_transformer', ColumnTransformer)].
        La salida del ColumnTransformer es un array numpy denso.
    """
    num_feats = list(numeric_features or NUMERIC_FEATURES)
    cat_feats = list(categorical_features or CATEGORICAL_FEATURES)

    imputer = MissingnessAwareImputer(
        numeric_features=num_feats,
        categorical_features=cat_feats,
        threshold=missingness_threshold,
        seed=seed,
    )

    # ColumnTransformer: rama numerica (StandardScaler) y rama categorica (OneHotEncoder).
    # remainder='drop' descarta cualquier columna no declarada en num_feats ni cat_feats.
    column_transformer = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), num_feats),  # estandarizacion (media 0, std 1) de las 5 numericas
            (
                "cat",
                OneHotEncoder(
                    drop="first",           # elimina la primera categoria para evitar multicolinealidad
                    handle_unknown="ignore",
                    sparse_output=False,    # salida densa para compatibilidad con sksurv y numpy
                ),
                cat_feats,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )

    return Pipeline(
        steps=[
            ("imputer", imputer),
            ("column_transformer", column_transformer),
        ]
    )
