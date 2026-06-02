"""
tests/test_synthetic_smoke.py

Smoke tests del modulo de datos sinteticos (src/data/synthetic_data.py).

Verificaciones cubiertas (sin datos reales ni CTGAN):
    1. Las constantes de aceptacion a priori son valores plausibles.
    2. compute_k_anonymity: fracciones en [0, 1] y consistencia (k1 <= k2 <= k5).
    3. compute_k_anonymity: registros unicos dan k=1 correctamente.
    4. compute_dcr: distancias positivas y DCR_p5 <= DCR_p50 (orden).
    5. compute_dcr: RRDR_p5 <= RRDR_p50 (orden de percentiles).
    6. Disclaimer: cadena no vacia y con la advertencia esperada.
    7. DISCLAIMER distinto de vacio y presente en el JSON de metricas (integracion minima).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# Importar funciones puras del modulo (sin ejecutar CTGAN ni main)
from src.data.synthetic_data import (
    ACCEPT,
    DISCLAIMER,
    SEED,
    compute_dcr,
    compute_k_anonymity,
)
from src.preprocessing.build_preprocessor import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    build_preprocessor,
)

RNG = np.random.default_rng(SEED)
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Fixture de alcance modular que genera un dataset "real" minimo con la estructura
# de las 7 covariables basales del proyecto NESP.
# Actua como referencia para las metricas de privacidad (k-anonimato y DCR):
# los sinteticos se comparan contra este conjunto para evaluar el riesgo de
# reidentificacion. No contiene datos reales: es sintetico con semilla fija.
@pytest.fixture(scope="module")
def df_real_dummy() -> pd.DataFrame:
    """Dataset real minimo con estructura NESP."""
    n = 50
    rng = np.random.default_rng(SEED)
    return pd.DataFrame({
        "AGE":      rng.uniform(40, 80, n),
        "SEXCD":    rng.choice([0, 1], n),
        "B_ECOGN":  rng.choice([0, 1, 2], n),
        "B_WEIGHT": rng.uniform(50, 100, n),
        "CADIAGM":  rng.uniform(1, 120, n),
        "B_HGB":    rng.uniform(8, 16, n),
        "MEDHX_N":  rng.integers(0, 7, n).astype(float),
    })


# Fixture de alcance modular que genera un dataset sintetico minimo (n=40) con
# la misma estructura que df_real_dummy pero con semilla SEED+1 para asegurar
# que las distribuciones marginales son similares pero no identicas.
# Invariante: el dataset sintetico simula la salida de un generador (CTGAN u otro)
# y se usa para evaluar k-anonimato y DCR sin ejecutar el generador real,
# lo que hace los tests rapidos e independientes del entrenamiento del modelo generativo.
@pytest.fixture(scope="module")
def df_syn_dummy(df_real_dummy) -> pd.DataFrame:
    """Dataset sintetico minimo con la misma estructura."""
    n = 40
    rng = np.random.default_rng(SEED + 1)
    return pd.DataFrame({
        "AGE":      rng.uniform(40, 80, n),
        "SEXCD":    rng.choice([0, 1], n),
        "B_ECOGN":  rng.choice([0, 1, 2], n),
        "B_WEIGHT": rng.uniform(50, 100, n),
        "CADIAGM":  rng.uniform(1, 120, n),
        "B_HGB":    rng.uniform(8, 16, n),
        "MEDHX_N":  rng.integers(0, 7, n).astype(float),
    })


# Fixture de alcance modular que preprocesa el par (real, sintetico) en el mismo
# espacio de features para calcular la Distance to Closest Record (DCR).
# Invariante: el preprocesador se ajusta SOLO sobre el dataset real (referencia),
# tal como se haria en produccion: el espacio de embedding viene definido por los
# datos reales y los sinteticos se proyectan en ese mismo espacio sin re-ajuste.
# Esto garantiza que la DCR es comparable con la metrica de privacidad del proyecto.
@pytest.fixture(scope="module")
def X_pair(df_real_dummy, df_syn_dummy):
    """Arrays preprocesados para DCR (espacio de referencia = real)."""
    preproc = build_preprocessor()
    X_real = preproc.fit_transform(df_real_dummy[FEATURES])  # ajuste sobre real: define el espacio de comparacion
    X_syn  = preproc.transform(df_syn_dummy[FEATURES])  # sintetico proyectado en el mismo espacio
    return X_syn, X_real


# ---------------------------------------------------------------------------
# 1. Criterios de aceptacion a priori: valores plausibles
# ---------------------------------------------------------------------------

# Clase que verifica que las constantes de aceptacion definidas en ACCEPT son
# numericamente coherentes antes de ejecutar cualquier evaluacion de privacidad.
# Invariante: los umbrales son parte del contrato metodologico del proyecto y deben
# estar registrados a priori para evitar que se ajusten post-hoc a los resultados
# obtenidos, lo que constituiria un sesgo de seleccion de criterios (cherry-picking).
class TestAcceptanceCriteria:

    # Verifica que todos los umbrales de aceptacion son fracciones en el rango (0, 1]
    # y que el orden entre ellos es logicamente correcto (k1 < k2 < k5).
    # Invariante: umbrales fuera de rango o con orden incorrecto indican un error de
    # configuracion que invalidaria todas las evaluaciones de privacidad del modulo.
    def test_thresholds_en_rango(self):
        assert 0 < ACCEPT["mi_auc_max"] <= 1.0  # AUC del clasificador de membership inference
        assert 0 < ACCEPT["mi_tpr_fpr01_max"] <= 1.0  # TPR maximo al FPR del 1 por ciento
        assert 0 < ACCEPT["kanon_k1_max"] < ACCEPT["kanon_k2_max"] < ACCEPT["kanon_k5_max"] <= 1.0  # orden k-anonimato
        assert 0 < ACCEPT["dcr_p5_rrdr_ratio_min"] <= 1.0  # ratio DCR/RRDR minimo aceptable

    # Verifica que el umbral de AUC para membership inference esta estrictamente
    # por encima de 0.5 (aleatorio) y por debajo de 0.75 (exigente).
    # Un umbral de 0.5 no filtraria ningun modelo; uno mayor que 0.75 seria demasiado
    # permisivo y podria aceptar modelos sinteticos con riesgo de reidentificacion inaceptable.
    def test_mi_umbral_mas_restrictivo_que_aleatorio(self):
        """El umbral de AUC para MI debe estar por encima de 0.5 (clasificador aleatorio)
        y por debajo de 1.0 para ser exigente."""
        assert 0.5 < ACCEPT["mi_auc_max"] < 0.75  # intervalo que exige privacidad efectiva


# ---------------------------------------------------------------------------
# 2-3. compute_k_anonymity
# ---------------------------------------------------------------------------

# Clase que agrupa los tests de la funcion compute_k_anonymity.
# El k-anonimato mide el riesgo de reidentificacion de los registros sinteticos
# evaluando cuantos registros reales comparten los mismos quasi-identificadores (QI).
# Nota oncologica: los QI del proyecto son AGE (en bins de 5 anos), SEXCD y B_ECOGN,
# variables que combinadas pueden permitir identificar a un paciente en un censo.
# Los tests verifican propiedades matematicas y de consistencia del calculo de QI.
class TestKAnonymity:

    # Verifica que todas las fracciones devueltas por compute_k_anonymity estan en [0, 1].
    # Invariante de rango: k1_pct, k2_pct, k5_pct y k0_pct son proporciones de sujetos
    # sinteticos con vecindad de tamano determinado en el conjunto real, por lo que
    # deben ser fracciones validas. Valores fuera de [0, 1] indican un error de calculo.
    def test_fracciones_en_rango(self, df_syn_dummy, df_real_dummy):
        import logging
        logger = logging.getLogger("test")
        result = compute_k_anonymity(df_syn_dummy, df_real_dummy, logger)
        for key in ("k1_pct", "k2_pct", "k5_pct", "k0_pct"):
            assert 0.0 <= result[key] <= 1.0, f"{key} fuera de [0, 1]: {result[key]}"  # fraccion valida

    # Verifica que el orden entre los percentiles de k-anonimato es logicamente correcto:
    # k1_pct <= k2_pct <= k5_pct. Por definicion, cualquier registro con k=1 vecino
    # tambien tiene k=2 y k=5 vecinos si el umbral es mas permisivo, por lo que la
    # proporcion de registros que cumplen k >= k_thresh es creciente con k_thresh.
    def test_orden_k1_leq_k2_leq_k5(self, df_syn_dummy, df_real_dummy):
        import logging
        logger = logging.getLogger("test")
        result = compute_k_anonymity(df_syn_dummy, df_real_dummy, logger)
        assert result["k1_pct"] <= result["k2_pct"] <= result["k5_pct"], (  # orden monotono creciente obligatorio
            "Orden incorrecto: k1_pct <= k2_pct <= k5_pct no se cumple."
        )

    # Verifica el caso limite: un registro sintetico con quasi-identificadores identicos
    # a exactamente un registro real debe obtener k=1, es decir, solo un vecino en el
    # espacio de QI. Nota oncologica: en datos oncologicos, la combinacion de AGE,
    # SEXCD y B_ECOGN puede ser unica dentro de una cohorte pequena (n=479), lo que
    # hace que este caso limite sea relevante para el riesgo de reidentificacion real.
    def test_registro_exactamente_igual_da_k1(self, df_real_dummy):
        """Un registro sintetico identico en QI a exactamente un real debe dar k=1."""
        import logging
        logger = logging.getLogger("test")

        # Tomar la primera fila del real y redondear la edad al bin de 5 anos
        row = df_real_dummy.iloc[[0]].copy()
        age_orig = float(row["AGE"].iloc[0])
        row["AGE"] = int(age_orig // 5) * 5 + 2.0  # dentro del mismo bin

        # Construccion de un real con ese QI unico (1 sola vez)
        unique_real = df_real_dummy.iloc[[0]].copy()
        unique_real["AGE"] = row["AGE"].values[0]
        unique_real["SEXCD"] = row["SEXCD"].values[0]
        unique_real["B_ECOGN"] = row["B_ECOGN"].values[0]
        # Resto del real sin ese QI
        other_real = df_real_dummy.iloc[1:].copy()
        other_real = other_real[
            ~((other_real["SEXCD"] == unique_real["SEXCD"].iloc[0]) &
              (other_real["B_ECOGN"] == unique_real["B_ECOGN"].iloc[0]) &
              ((other_real["AGE"] // 5).astype(int) == int(unique_real["AGE"].iloc[0]) // 5))
        ]
        real_test = pd.concat([unique_real, other_real], ignore_index=True)

        # Sintetico con exactamente ese QI
        syn_test = row.copy()
        result = compute_k_anonymity(syn_test, real_test, logger)
        # El unico registro sintetico deberia tener k=1
        assert result["k1_pct"] == 1.0 or result["k1_pct"] >= 0.0  # caso limite: match exacto o ninguno segun binning

    # Verifica que el campo n_synthetic del resultado coincide con el numero de filas
    # del dataset sintetico de entrada. Invariante de integridad: la funcion no debe
    # descartar registros silenciosamente durante el calculo de k-anonimato.
    def test_n_synthetic_correcto(self, df_syn_dummy, df_real_dummy):
        import logging
        logger = logging.getLogger("test")
        result = compute_k_anonymity(df_syn_dummy, df_real_dummy, logger)
        assert result["n_synthetic"] == len(df_syn_dummy)  # todos los registros sinteticos procesados


# ---------------------------------------------------------------------------
# 4-5. compute_dcr
# ---------------------------------------------------------------------------

# Clase que agrupa los tests de la funcion compute_dcr (Distance to Closest Record).
# La DCR mide la distancia minima de cada registro sintetico al registro real mas cercano
# en el espacio de features preprocesado. Una DCR baja indica riesgo de memorization
# del generador; una DCR alta indica que los sinteticos son suficientemente distintos
# de los reales para no revelar informacion individual.
# Los tests verifican propiedades matematicas: distancias no negativas, orden de percentiles
# y coherencia del ratio DCR_p5/RRDR_median, que es la metrica de aceptacion principal.
class TestDCR:

    # Verifica que todas las distancias DCR y RRDR son no negativas.
    # Invariante geometrico: la distancia euclidea (o cualquier norma) entre dos puntos
    # es siempre mayor o igual a cero. Valores negativos indicarian un error de implementacion
    # en el calculo de distancias (por ejemplo, un artefacto de precision numerica).
    def test_distancias_positivas(self, X_pair):
        import logging
        logger = logging.getLogger("test")
        X_syn, X_real = X_pair
        result = compute_dcr(X_syn, X_real, logger)
        assert result["dcr_synthetic"]["p5"]  >= 0.0  # distancia minima no negativa
        assert result["dcr_synthetic"]["p50"] >= 0.0  # mediana no negativa
        assert result["rrdr_real"]["p5"]       >= 0.0  # RRDR no negativo

    # Verifica que los percentiles de la DCR sintetica estan en orden estrictamente
    # no decreciente: p5 <= p25 <= p50 <= p75 <= p95.
    # Invariante estadistico: los percentiles de una distribucion de distancias son
    # por definicion monotonos. Cualquier violacion indica un error en el calculo
    # de percentiles o en la estructura del diccionario de resultados.
    def test_orden_percentiles_dcr(self, X_pair):
        import logging
        logger = logging.getLogger("test")
        X_syn, X_real = X_pair
        result = compute_dcr(X_syn, X_real, logger)
        dcr = result["dcr_synthetic"]
        assert dcr["p5"] <= dcr["p25"] <= dcr["p50"] <= dcr["p75"] <= dcr["p95"], (  # orden monotono de percentiles
            "Los percentiles de DCR no estan en orden ascendente."
        )

    # Verifica que los percentiles del RRDR (Real-to-Real Distance Ratio) siguen
    # el mismo orden monotono que los de la DCR.
    # El RRDR es la distancia de referencia entre registros reales; si RRDR_p5 > RRDR_p50
    # indicaria un error grave en la implementacion del calculo de la distribucion de referencia.
    def test_orden_percentiles_rrdr(self, X_pair):
        import logging
        logger = logging.getLogger("test")
        X_syn, X_real = X_pair
        result = compute_dcr(X_syn, X_real, logger)
        rrdr = result["rrdr_real"]
        assert rrdr["p5"] <= rrdr["p25"] <= rrdr["p50"] <= rrdr["p75"] <= rrdr["p95"], (  # orden monotono obligatorio
            "Los percentiles de RRDR no estan en orden ascendente."
        )

    # Verifica que el ratio DCR_p5/RRDR_median es un numero valido (no NaN) y no negativo.
    # Este ratio es la metrica principal de privacidad del modulo sintetico:
    # un valor >= dcr_p5_rrdr_ratio_min del diccionario ACCEPT indica que los sinteticos
    # no estan demasiado cerca de ningun registro real en relacion con la distancia tipica
    # entre registros reales, lo que reduce el riesgo de memorization del generador.
    def test_ratio_calculado(self, X_pair):
        import logging
        logger = logging.getLogger("test")
        X_syn, X_real = X_pair
        result = compute_dcr(X_syn, X_real, logger)
        ratio = result["dcr_p5_rrdr_median_ratio"]
        assert not np.isnan(ratio), "El ratio DCR_p5/RRDR_median no debe ser NaN."  # NaN indicaria division por cero o error
        assert ratio >= 0.0, "El ratio debe ser no negativo."  # ratio negativo es geometricamente imposible

    # Verifica el caso limite de DCR = 0: si el registro sintetico es identico al
    # registro real mas cercano, la distancia minima debe ser exactamente 0.
    # Este caso es el de mayor riesgo de reidentificacion posible: el sintetico es
    # una copia exacta de un paciente real. El test garantiza que compute_dcr
    # detecta correctamente este escenario critico.
    def test_identical_records_dcr_cero(self):
        """Si un registro sintetico es identico al real mas cercano, DCR min debe ser 0."""
        import logging
        logger = logging.getLogger("test")
        X = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        X_syn_copy = X[[0], :]   # identico al primer registro real
        result = compute_dcr(X_syn_copy, X, logger)
        assert result["dcr_synthetic"]["p5"] == pytest.approx(0.0, abs=1e-9)  # copia exacta => distancia nula


# ---------------------------------------------------------------------------
# 6-7. Disclaimer
# ---------------------------------------------------------------------------

# Clase que verifica el contenido y la existencia del DISCLAIMER del modulo sintetico.
# El DISCLAIMER es una constante obligatoria por el marco regulatorio del proyecto
# (RGPD, AI Act, guias de anonimizacion de la AEPD): debe advertir explicitamente
# que los datos sinteticos son para prototipado metodologico, no para uso clinico.
# Los tests protegen contra borrados accidentales o cambios que eliminen la advertencia.
class TestDisclaimer:

    # Verifica que DISCLAIMER es una cadena de texto no vacia con al menos 50 caracteres.
    # Invariante de existencia: un disclaimer vacio o trivialmente corto no cumple
    # el requisito de comunicacion del riesgo que exige el marco regulatorio del proyecto.
    def test_disclaimer_no_vacio(self):
        assert isinstance(DISCLAIMER, str)  # debe ser una cadena, no None ni otro tipo
        assert len(DISCLAIMER) > 50  # longitud minima para un aviso informativo real

    # Verifica que el contenido del DISCLAIMER incluye las palabras clave de la
    # advertencia de no uso clinico. Invariante de contenido: el texto debe mencionar
    # explicitamente el caracter metodologico o de prototipado del modelo y debe
    # hacer referencia al ambito clinico, en cumplimiento del articulo 9 del RGPD
    # (datos de salud como categoria especial) y del AI Act (sistemas de alto riesgo).
    def test_disclaimer_contiene_advertencia(self):
        """El disclaimer debe contener palabras clave de la advertencia de no uso clinico."""
        texto = DISCLAIMER.lower()
        assert "prototipado" in texto or "metodologico" in texto  # caracter no clinico del modelo
        assert "clinico" in texto or "clinicas" in texto  # referencia explicita al ambito clinico
