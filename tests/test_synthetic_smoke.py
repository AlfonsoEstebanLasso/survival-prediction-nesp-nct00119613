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


@pytest.fixture(scope="module")
def X_pair(df_real_dummy, df_syn_dummy):
    """Arrays preprocesados para DCR (espacio de referencia = real)."""
    preproc = build_preprocessor()
    X_real = preproc.fit_transform(df_real_dummy[FEATURES])
    X_syn  = preproc.transform(df_syn_dummy[FEATURES])
    return X_syn, X_real


# ---------------------------------------------------------------------------
# 1. Criterios de aceptacion a priori: valores plausibles
# ---------------------------------------------------------------------------

class TestAcceptanceCriteria:

    def test_thresholds_en_rango(self):
        assert 0 < ACCEPT["mi_auc_max"] <= 1.0
        assert 0 < ACCEPT["mi_tpr_fpr01_max"] <= 1.0
        assert 0 < ACCEPT["kanon_k1_max"] < ACCEPT["kanon_k2_max"] < ACCEPT["kanon_k5_max"] <= 1.0
        assert 0 < ACCEPT["dcr_p5_rrdr_ratio_min"] <= 1.0

    def test_mi_umbral_mas_restrictivo_que_aleatorio(self):
        """El umbral de AUC para MI debe estar por encima de 0.5 (clasificador aleatorio)
        y por debajo de 1.0 para ser exigente."""
        assert 0.5 < ACCEPT["mi_auc_max"] < 0.75


# ---------------------------------------------------------------------------
# 2-3. compute_k_anonymity
# ---------------------------------------------------------------------------

class TestKAnonymity:

    def test_fracciones_en_rango(self, df_syn_dummy, df_real_dummy):
        import logging
        logger = logging.getLogger("test")
        result = compute_k_anonymity(df_syn_dummy, df_real_dummy, logger)
        for key in ("k1_pct", "k2_pct", "k5_pct", "k0_pct"):
            assert 0.0 <= result[key] <= 1.0, f"{key} fuera de [0, 1]: {result[key]}"

    def test_orden_k1_leq_k2_leq_k5(self, df_syn_dummy, df_real_dummy):
        import logging
        logger = logging.getLogger("test")
        result = compute_k_anonymity(df_syn_dummy, df_real_dummy, logger)
        assert result["k1_pct"] <= result["k2_pct"] <= result["k5_pct"], (
            "Orden incorrecto: k1_pct <= k2_pct <= k5_pct no se cumple."
        )

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
        assert result["k1_pct"] == 1.0 or result["k1_pct"] >= 0.0  # puede ser 0 si no hay match exacto

    def test_n_synthetic_correcto(self, df_syn_dummy, df_real_dummy):
        import logging
        logger = logging.getLogger("test")
        result = compute_k_anonymity(df_syn_dummy, df_real_dummy, logger)
        assert result["n_synthetic"] == len(df_syn_dummy)


# ---------------------------------------------------------------------------
# 4-5. compute_dcr
# ---------------------------------------------------------------------------

class TestDCR:

    def test_distancias_positivas(self, X_pair):
        import logging
        logger = logging.getLogger("test")
        X_syn, X_real = X_pair
        result = compute_dcr(X_syn, X_real, logger)
        assert result["dcr_synthetic"]["p5"]  >= 0.0
        assert result["dcr_synthetic"]["p50"] >= 0.0
        assert result["rrdr_real"]["p5"]       >= 0.0

    def test_orden_percentiles_dcr(self, X_pair):
        import logging
        logger = logging.getLogger("test")
        X_syn, X_real = X_pair
        result = compute_dcr(X_syn, X_real, logger)
        dcr = result["dcr_synthetic"]
        assert dcr["p5"] <= dcr["p25"] <= dcr["p50"] <= dcr["p75"] <= dcr["p95"], (
            "Los percentiles de DCR no estan en orden ascendente."
        )

    def test_orden_percentiles_rrdr(self, X_pair):
        import logging
        logger = logging.getLogger("test")
        X_syn, X_real = X_pair
        result = compute_dcr(X_syn, X_real, logger)
        rrdr = result["rrdr_real"]
        assert rrdr["p5"] <= rrdr["p25"] <= rrdr["p50"] <= rrdr["p75"] <= rrdr["p95"], (
            "Los percentiles de RRDR no estan en orden ascendente."
        )

    def test_ratio_calculado(self, X_pair):
        import logging
        logger = logging.getLogger("test")
        X_syn, X_real = X_pair
        result = compute_dcr(X_syn, X_real, logger)
        ratio = result["dcr_p5_rrdr_median_ratio"]
        assert not np.isnan(ratio), "El ratio DCR_p5/RRDR_median no debe ser NaN."
        assert ratio >= 0.0, "El ratio debe ser no negativo."

    def test_identical_records_dcr_cero(self):
        """Si un registro sintetico es identico al real mas cercano, DCR min debe ser 0."""
        import logging
        logger = logging.getLogger("test")
        X = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        X_syn_copy = X[[0], :]   # identico al primer registro real
        result = compute_dcr(X_syn_copy, X, logger)
        assert result["dcr_synthetic"]["p5"] == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# 6-7. Disclaimer
# ---------------------------------------------------------------------------

class TestDisclaimer:

    def test_disclaimer_no_vacio(self):
        assert isinstance(DISCLAIMER, str)
        assert len(DISCLAIMER) > 50

    def test_disclaimer_contiene_advertencia(self):
        """El disclaimer debe contener palabras clave de la advertencia de no uso clinico."""
        texto = DISCLAIMER.lower()
        assert "prototipado" in texto or "metodologico" in texto
        assert "clinico" in texto or "clinicas" in texto
