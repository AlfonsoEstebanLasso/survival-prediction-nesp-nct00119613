"""
src/preprocessing/build_preprocessor_strategy2.py

Proposito:
    Preprocesador anti-fugas para la Estrategia 2 (analisis ampliado). Es identico
    en filosofia al de la Estrategia 1 (imputacion adaptativa dentro de fold,
    estandarizacion de numericas, one-hot de categoricas) pero con una diferencia
    pre-registrada: la covariable B_SEREPO (EPO serica basal, muy asimetrica) se
    transforma con log1p ANTES de estandarizar. El resto del pool de 10 variables
    se trata como en el primario.

    Reutiliza MissingnessAwareImputer del preprocesador primario sin modificarlo, de
    modo que la logica de imputacion (mediana si missingness <= 20%, iterativa si >20%,
    moda para categoricas), ajustada solo sobre el fold de entrenamiento, es la misma.

Entradas:
    numeric_features     -- numericas del pool de la Estrategia 2 (default: 6)
    log_features         -- numericas a transformar con log1p antes de escalar (default: B_SEREPO)
    categorical_features -- categoricas del pool (default: 4)
    missingness_threshold, seed -- parametros del imputador adaptativo

Salidas:
    Pipeline(MissingnessAwareImputer -> ColumnTransformer) sin ajustar.
    Se debe llamar a .fit() SOLO sobre el fold de entrenamiento dentro del esquema CV.

Orden de transformaciones (rama numerica):
    1. Imputacion (en MissingnessAwareImputer): para B_SEREPO, con 9.2% de faltantes,
       imputacion por mediana en escala cruda. Como log1p es monotona, imputar la
       mediana cruda y luego aplicar log1p equivale a imputar la mediana de los valores
       transformados, por lo que el orden imputar -> log1p es correcto y sin fuga.
    2. log1p sobre B_SEREPO (FunctionTransformer), luego StandardScaler.
    3. StandardScaler sobre el resto de numericas.
    4. OneHotEncoder (drop='first') sobre las categoricas.

Control anti-leakage:
    Todas las estadisticas de ajuste (medianas, media/std del scaler, categorias del
    encoder) se calculan solo a partir del fold de entrenamiento. El log1p es una
    funcion fija sin parametros aprendidos, por lo que no introduce fuga.
"""

from __future__ import annotations

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

# Reutiliza el imputador adaptativo del preprocesador primario (sin modificarlo).
from src.preprocessing.build_preprocessor import (
    MISSINGNESS_THRESHOLD,
    SEED,
    MissingnessAwareImputer,
)

# Pool de la Estrategia 2 (coherente con el ETL etl_strategy2.py y el pre-registro).
NUMERIC_FEATURES: list[str] = ["AGE", "BMI", "CADIAGM", "B_HGB", "B_SEREPO", "MEDHX_N"]
LOG_FEATURES: list[str] = ["B_SEREPO"]
CATEGORICAL_FEATURES: list[str] = ["SEXCD", "B_ECOGN", "B_LDHN", "PRTFN"]


# Construye el Pipeline de preprocesado de la Estrategia 2 sin ajustar.
# La rama numerica se divide en dos: las variables de log_features pasan por
# log1p y luego StandardScaler; el resto de numericas solo por StandardScaler.
# La rama categorica usa OneHotEncoder(drop='first'). El ajuste (medianas, media,
# std, categorias) ocurre solo en el fold de entrenamiento dentro de la CV anidada.
def build_preprocessor_strategy2(
    numeric_features: list[str] | None = None,
    log_features: list[str] | None = None,
    categorical_features: list[str] | None = None,
    *,
    missingness_threshold: float = MISSINGNESS_THRESHOLD,
    seed: int = SEED,
) -> Pipeline:
    num_feats = list(numeric_features or NUMERIC_FEATURES)
    log_feats = list(log_features if log_features is not None else LOG_FEATURES)
    cat_feats = list(categorical_features or CATEGORICAL_FEATURES)

    # Numericas que se escalan directamente (sin log1p).
    plain_feats = [c for c in num_feats if c not in log_feats]

    imputer = MissingnessAwareImputer(
        numeric_features=num_feats,
        categorical_features=cat_feats,
        threshold=missingness_threshold,
        seed=seed,
    )

    transformers = []
    if plain_feats:
        transformers.append(("num", StandardScaler(), plain_feats))
    if log_feats:
        # log1p antes de escalar. np.log1p es seguro para valores >= 0 (B_SEREPO >= 12).
        log_pipe = Pipeline(steps=[
            ("log1p", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
            ("scale", StandardScaler()),
        ])
        transformers.append(("num_log", log_pipe, log_feats))
    transformers.append((
        "cat",
        OneHotEncoder(drop="first", handle_unknown="ignore", sparse_output=False),
        cat_feats,
    ))

    column_transformer = ColumnTransformer(
        transformers=transformers,
        remainder="drop",
        verbose_feature_names_out=False,
    )

    return Pipeline(steps=[
        ("imputer", imputer),
        ("column_transformer", column_transformer),
    ])
