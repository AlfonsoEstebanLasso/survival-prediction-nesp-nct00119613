"""
ETL de la Estrategia 2 (analisis ampliado y exploratorio) del ensayo
NESP-Oncology-20010145 (NCT00119613) para el TFG de Ciencia de Datos (UOC).

Proposito
    Construir un dataset derivado PROPIO de una fila por sujeto (SUBJID) para el
    analisis exploratorio de seleccion de caracteristicas e hiperparametros con
    validacion cruzada anidada (protocolo pre-registrado en docs/decision_log.md,
    entrada "Pre-registro del protocolo de la Estrategia 2"). Es ADICIONAL al
    pipeline primario (Estrategia 1): no lo sustituye ni toca sus artefactos, sus
    hashes ni su verificacion KPI-1. Genera su propio dataset, diccionario,
    manifiesto y hash de referencia, en paralelo.

Pool de 10 covariables candidatas (todas basales o pre-aleatorizacion, sin fuga)
    Continuas:   AGE, BMI (derivada), CADIAGM, B_HGB, B_SEREPO, MEDHX_N (derivada)
    Categoricas: SEXCD, B_ECOGN, B_LDHN, PRTFN
    El log1p de B_SEREPO NO se aplica aqui: es una transformacion de preprocesado
    que se ajusta dentro de fold para no introducir fuga. El ETL entrega B_SEREPO
    en su escala cruda (mU/mL).

Derivaciones
    BMI = B_WEIGHT / (B_HEIGHT/100)^2. Sustituye a B_WEIGHT y B_HEIGHT (decision
    pre-registrada: una sola covariable nutricional, por parsimonia y para evitar
    colinealidad). Las columnas crudas de peso y altura no se incluyen en el dataset.
    MEDHX_N: numero de sistemas corporales con antecedente anormal (MEDHXYN = 1) por
    sujeto, rango 0 a 6 (identica definicion que en la Estrategia 1).

Entradas (ficheros SAS, resueltos sin distinguir mayusculas/minusculas)
    c_keyvar.sas7bdat   SUBJID, AGE, SEXCD, B_ECOGN, B_HGB, B_SEREPO, B_LDHN, PRTFN,
                        TXG (estratificacion), EVALPRIM, EVALQOL
    a_eendpt.sas7bdat   endpoints de supervivencia (DTH, DTHDY, PFSCD, PFSDY)
    c_bchar.sas7bdat    peso y altura basales (B_WEIGHT, B_HEIGHT) para derivar BMI
    c_diag.sas7bdat     tiempo desde el diagnostico (CADIAGM)
    c_medhis.sas7bdat   historia medica (formato largo) para derivar MEDHX_N

Salidas (en el directorio --out)
    dataset_strategy2.parquet          dataset derivado (si hay motor parquet)
    dataset_strategy2.csv              dataset derivado
    dataset_strategy2_dictionary.csv   diccionario de variables del dataset
    dataset_strategy2_etl_manifest.json manifiesto de procedencia, calidad y hash de referencia
    dataset_strategy2_etl_log.txt      traza de ejecucion

Control anti-leakage
    Solo se incorporan variables basales (pre-tratamiento). Se excluyen los ficheros
    de laboratorio longitudinales (a_lab, c_chem, c_hemat, c_iron) por ser post-basales
    (el LDH y el EPO basales ya estan resumidos en c_keyvar como variables de cribado),
    todas las variables de tratamiento, fecha o post-basales, las categorizaciones IVRS
    redundantes y las constantes por varianza cero o por criterio de inclusion.

Uso (desde la raiz del proyecto)
    python src/data/etl_strategy2.py
    python src/data/etl_strategy2.py --data-dir "SAS dataset" --out ".\\output"

Dependencias
    pip install pyreadstat pandas numpy   (parquet opcional: pip install pyarrow)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat

# Reutilizacion de los helpers ya verificados del ETL primario, sin modificarlo.
# Al ejecutar este script, Python anade su directorio (src/data) al path, por lo que
# el modulo del ETL primario es importable por nombre. La importacion solo carga
# definiciones (el primario protege su ejecucion con if __name__ == "__main__").
from etl_nesp_nct00119613 import (  # noqa: E402
    SUBJECT_KEY,
    DERIVED_COMORBIDITY,
    sha256_file,
    resolve_file,
    load_sas,
    build_comorbidity,
)


# ----------------------------------------------------------------------------
# Configuracion
# ----------------------------------------------------------------------------

SEED = 42
EXPECTED_N = 479
DEFAULT_DATA_DIR = r"SAS dataset"
DEFAULT_OUT_DIR = "output"
OUTPUT_STEM = "dataset_strategy2"

# Columnas a leer de cada fuente a nivel de sujeto.
SOURCES = {
    "spine":     ("c_keyvar.sas7bdat", [SUBJECT_KEY, "AGE", "SEXCD", "B_ECOGN",
                                        "B_HGB", "B_SEREPO", "B_LDHN", "PRTFN",
                                        "TXG", "EVALPRIM", "EVALQOL"]),
    "endpoints": ("a_eendpt.sas7bdat", [SUBJECT_KEY, "DTH", "DTHDY", "PFSCD", "PFSDY"]),
    "bchar":     ("c_bchar.sas7bdat",  [SUBJECT_KEY, "B_WEIGHT", "B_HEIGHT"]),
    "diag":      ("c_diag.sas7bdat",   [SUBJECT_KEY, "CADIAGM"]),
}
MEDHIS_FILE = "c_medhis.sas7bdat"
DERIVED_BMI = "BMI"

# Rol de cada variable del dataset final (variable -> rol, fuente, nota).
COLUMN_ROLES = {
    SUBJECT_KEY: ("clave", "c_keyvar", "Identificador de sujeto. Clave de union."),
    "DTH":      ("endpoint_OS_evento", "a_eendpt", "Muerte. 1 = evento, 0 = censura."),
    "DTHDY":    ("endpoint_OS_tiempo", "a_eendpt", "Dia de muerte o ultima observacion (dias)."),
    "PFSCD":    ("endpoint_PFS_evento", "a_eendpt", "Progresion o muerte. 1 = evento, 0 = censura."),
    "PFSDY":    ("endpoint_PFS_tiempo", "a_eendpt", "Tiempo a progresion o muerte (dias)."),
    "AGE":      ("predictor_num", "c_keyvar", "Edad (anios)."),
    "BMI":      ("predictor_num_derivado", "c_bchar",
                 "Indice de masa corporal = B_WEIGHT / (B_HEIGHT/100)^2. Sustituye a peso y altura."),
    "CADIAGM":  ("predictor_num", "c_diag", "Tiempo desde el diagnostico (meses). 1 valor faltante."),
    "B_HGB":    ("predictor_num", "c_keyvar", "Hemoglobina basal (g/dL). 3 valores faltantes."),
    "B_SEREPO": ("predictor_num", "c_keyvar",
                 "EPO serica basal (mU/mL). Asimetrica; el log1p se aplica en preprocesado dentro de fold. 44 faltantes."),
    DERIVED_COMORBIDITY: ("predictor_num_derivado", "c_medhis",
                          "Numero de sistemas con antecedente anormal (MEDHXYN = 1). Rango 0 a 6."),
    "SEXCD":    ("predictor_cat", "c_keyvar", "Sexo (codigo)."),
    "B_ECOGN":  ("predictor_cat", "c_keyvar", "ECOG basal (categoria BYVAR, 1 vs 2)."),
    "B_LDHN":   ("predictor_cat", "c_keyvar",
                 "LDH basal normal/anormal (IVRS de cribado, factor de estratificacion). Valores 1 y 2, sin faltantes."),
    "PRTFN":    ("predictor_cat", "c_keyvar",
                 "Transfusion de hematies antes de la 1a dosis (0=No, 1=Si). Binario limpio; prevalencia 1.3% (6/479)."),
    "TXG":      ("estratificacion", "c_keyvar",
                 "Brazo aleatorizado NESP/placebo. Solo estratificacion, NO predictor."),
    "EVALPRIM": ("flag_evaluabilidad", "c_keyvar", "Evaluable para el analisis primario."),
    "EVALQOL":  ("flag_evaluabilidad", "c_keyvar", "Evaluable para el analisis de calidad de vida."),
}

# Listas de features para el preprocesado dentro de fold (consumidas por el experimento).
NUMERIC_FEATURES = ["AGE", "BMI", "CADIAGM", "B_HGB", "B_SEREPO", "MEDHX_N"]
CATEGORICAL_FEATURES = ["SEXCD", "B_ECOGN", "B_LDHN", "PRTFN"]

# Exclusiones documentadas (coherentes con el pre-registro).
EXCLUDED_CONSTANTS = [
    {"variable": "RACECD",   "motivo": "Varianza cero observada en la cohorte."},
    {"variable": "TUMORCD",  "motivo": "Invariante por criterio de inclusion (SCLC)."},
    {"variable": "EXTENTCD", "motivo": "Invariante por criterio de inclusion (estadio extenso)."},
    {"variable": "CHDCLASS", "motivo": "Invariante por el regimen del protocolo (platino mas etoposido)."},
]
EXCLUDED_FILES = [
    {"fichero": "a_lab / c_chem / c_hemat / c_iron",
     "motivo": "Laboratorios longitudinales post-basales. El LDH y el EPO basales ya estan en c_keyvar como variables de cribado."},
    {"fichero": "c_lesion / c_radio / c_trans / c_vitals",
     "motivo": "Respuesta RECIST, radioterapia, transfusiones en estudio y ECOG longitudinal: post-basales (leakage)."},
]
EXCLUDED_REDUNDANT = [
    {"variable": "B_WEIGHT, B_HEIGHT", "motivo": "Sustituidas por la derivada BMI (parsimonia, colinealidad)."},
    {"variable": "AGE65YN, AGEN, B_WGTN, B_HGBN, B_ECOG2, BSEPON",
     "motivo": "Categorizaciones IVRS redundantes de variables ya incluidas en escala continua."},
    {"variable": "EVALRND, EXHBCOYN, SITEID, PROTOCOL",
     "motivo": "Flags administrativos o de elegibilidad, no pronosticos."},
    {"variable": "Region (via SITEID)",
     "motivo": "Factor de estratificacion administrativo de alta cardinalidad; requeriria derivacion. Fuera del pool."},
]


# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------

# Inicializa el logger del ETL de la Estrategia 2 con salida a consola y a fichero
# de traza propio, para no mezclar la trazabilidad con la del ETL primario.
def setup_logger(out_dir: Path) -> logging.Logger:
    logger = logging.getLogger("etl_strategy2")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s", "%H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    fh = logging.FileHandler(out_dir / f"{OUTPUT_STEM}_etl_log.txt", mode="w", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------

# Selecciona el subconjunto de columnas y verifica su presencia (control defensivo
# de calidad: convierte un fallo silencioso de pandas en un KeyError descriptivo).
def select(df: pd.DataFrame, cols: list[str], source_name: str) -> pd.DataFrame:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"En {source_name} faltan columnas esperadas: {missing}")
    return df[cols].copy()


# ----------------------------------------------------------------------------
# Ensamblaje
# ----------------------------------------------------------------------------

# Orquesta carga, seleccion, derivaciones (BMI y MEDHX_N) y union LEFT JOIN sobre
# la espina c_keyvar para producir el dataset de una fila por sujeto de la Estrategia 2.
# Salida: (DataFrame ensamblado, diccionario de procedencia con hashes, etiquetas SAS).
def assemble(data_dir: Path, logger: logging.Logger) -> tuple[pd.DataFrame, dict, dict]:
    provenance, labels_all = {}, {}

    frames = {}
    for role, (fname, cols) in SOURCES.items():
        path = resolve_file(data_dir, fname)
        df, labels = load_sas(path)
        labels_all.update(labels)
        sub = select(df, cols, fname)
        n_dups = int(sub[SUBJECT_KEY].duplicated().sum())
        if n_dups:
            raise ValueError(f"{fname} tiene {n_dups} SUBJID duplicados; se esperaba clave unica.")
        provenance[fname] = {
            "sha256": sha256_file(path),
            "n_filas": int(len(df)),
            "subjid_unicos": int(sub[SUBJECT_KEY].nunique()),
        }
        logger.info("Cargada %s: %d filas, %d sujetos unicos.", fname, len(df), sub[SUBJECT_KEY].nunique())
        frames[role] = sub

    # Covariable derivada de comorbilidad (misma definicion que la Estrategia 1).
    medhis_path = resolve_file(data_dir, MEDHIS_FILE)
    medhis, labels_mh = load_sas(medhis_path)
    labels_all.update(labels_mh)
    provenance[MEDHIS_FILE] = {
        "sha256": sha256_file(medhis_path),
        "n_filas": int(len(medhis)),
        "subjid_unicos": int(medhis[SUBJECT_KEY].nunique()),
    }
    logger.info("Cargada %s: %d filas, %d sujetos unicos.",
                MEDHIS_FILE, len(medhis), medhis[SUBJECT_KEY].nunique())
    comorb = build_comorbidity(medhis, logger)

    # Union LEFT JOIN sobre la espina c_keyvar (479 sujetos de referencia).
    df = frames["spine"]
    for role in ("endpoints", "bchar", "diag"):
        df = df.merge(frames[role], on=SUBJECT_KEY, how="left")
    df = df.merge(comorb, on=SUBJECT_KEY, how="left")
    df[DERIVED_COMORBIDITY] = df[DERIVED_COMORBIDITY].fillna(0).astype(int)

    # Derivacion del IMC y eliminacion de las columnas crudas de peso y altura.
    # BMI = peso(kg) / altura(m)^2. Si peso o altura faltan, BMI queda NaN y se
    # imputa por mediana dentro de fold en el preprocesado (no aqui, para no introducir fuga).
    df[DERIVED_BMI] = df["B_WEIGHT"] / (df["B_HEIGHT"] / 100.0) ** 2
    df = df.drop(columns=["B_WEIGHT", "B_HEIGHT"])

    # Orden estable por SUBJID y reordenacion semantica de columnas.
    df = df.sort_values(SUBJECT_KEY).reset_index(drop=True)
    ordered = [c for c in COLUMN_ROLES if c in df.columns]
    df = df[ordered]

    logger.info("Dataset Estrategia 2 ensamblado: %d filas, %d columnas.", df.shape[0], df.shape[1])
    return df, provenance, labels_all


# ----------------------------------------------------------------------------
# Diccionario y calidad
# ----------------------------------------------------------------------------

# Genera el diccionario de variables del dataset derivado (rol semantico mas
# metadatos estructurales: tipo y missingness).
def build_dictionary(df: pd.DataFrame, labels: dict) -> pd.DataFrame:
    rows = []
    for col in df.columns:
        role, source, note = COLUMN_ROLES.get(col, ("", "", ""))
        rows.append({
            "variable": col,
            "rol": role,
            "fuente": source,
            "etiqueta_sas": labels.get(col, ""),
            "tipo": str(df[col].dtype),
            "n_faltantes": int(df[col].isna().sum()),
            "nota": note,
        })
    return pd.DataFrame(rows)


# Ejecuta las comprobaciones de calidad del dataset (unicidad de SUBJID, n esperado,
# cobertura de endpoints y missingness por variable). Salida: informe estructurado.
def quality_report(df: pd.DataFrame, logger: logging.Logger) -> dict:
    checks, ok = {}, True

    dup = int(df[SUBJECT_KEY].duplicated().sum())
    checks["subjid_unico_en_salida"] = (dup == 0)
    ok = ok and (dup == 0)

    checks["n_filas"] = int(len(df))
    checks["coincide_n_esperado"] = (len(df) == EXPECTED_N)
    if len(df) != EXPECTED_N:
        logger.warning("Filas = %d, esperado = %d.", len(df), EXPECTED_N)

    for c in ("DTH", "DTHDY", "PFSCD", "PFSDY"):
        n_null = int(df[c].isna().sum())
        checks[f"endpoint_{c}_completo"] = (n_null == 0)
        ok = ok and (n_null == 0)
        if n_null:
            logger.warning("Endpoint %s tiene %d valores faltantes.", c, n_null)

    nulls = {c: int(df[c].isna().sum()) for c in df.columns if df[c].isna().sum() > 0}
    logger.info("Comprobaciones de calidad: %s", "OK" if ok else "con advertencias")
    return {"checks": checks, "faltantes": nulls, "todo_ok": ok}


# ----------------------------------------------------------------------------
# Escritura
# ----------------------------------------------------------------------------

# Calcula el SHA-256 del contenido de un fichero ya escrito (hash de referencia del
# dataset, para reproducibilidad de la Estrategia 2 en entorno limpio).
def sha256_bytes(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# Escribe todos los artefactos del ETL de la Estrategia 2 y devuelve el manifiesto.
# El manifiesto incluye el hash de referencia del CSV (y del parquet, si se genera),
# que es la huella propia de reproducibilidad de la Estrategia 2, independiente del primario.
def write_outputs(df: pd.DataFrame, dictionary: pd.DataFrame, provenance: dict,
                  quality: dict, data_dir: Path, out_dir: Path,
                  logger: logging.Logger) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / f"{OUTPUT_STEM}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8")
    logger.info("Escrito %s", csv_path.name)

    reference_hashes = {"csv": sha256_bytes(csv_path)}
    try:
        pq_path = out_dir / f"{OUTPUT_STEM}.parquet"
        df.to_parquet(pq_path, index=False)
        reference_hashes["parquet"] = sha256_bytes(pq_path)
        logger.info("Escrito %s", pq_path.name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo escribir parquet (%s). Instala 'pyarrow' si lo necesitas.", exc)

    dict_path = out_dir / f"{OUTPUT_STEM}_dictionary.csv"
    dictionary.to_csv(dict_path, index=False, encoding="utf-8")
    logger.info("Escrito %s", dict_path.name)

    manifest = {
        "estudio": "NESP-Oncology-20010145 (NCT00119613)",
        "analisis": "Estrategia 2 (ampliado, exploratorio, adicional al primario)",
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "semilla": SEED,
        "directorio_datos": str(data_dir),
        "versiones": {
            "python": sys.version.split()[0],
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "pyreadstat": pyreadstat.__version__,
        },
        "pool_candidatas": {
            "numericas": NUMERIC_FEATURES,
            "categoricas": CATEGORICAL_FEATURES,
        },
        "derivaciones": {
            "BMI": "B_WEIGHT / (B_HEIGHT/100)^2; sustituye a peso y altura",
            "MEDHX_N": "numero de sistemas con antecedente anormal (MEDHXYN = 1), rango 0 a 6",
        },
        "fuentes": provenance,
        "dataset": {
            "n_filas": int(df.shape[0]),
            "n_columnas": int(df.shape[1]),
            "columnas": list(df.columns),
        },
        "hash_referencia_dataset": reference_hashes,
        "constantes_excluidas": EXCLUDED_CONSTANTS,
        "ficheros_excluidos_antileakage": EXCLUDED_FILES,
        "variables_excluidas_redundantes": EXCLUDED_REDUNDANT,
        "calidad": quality,
    }
    manifest_path = out_dir / f"{OUTPUT_STEM}_etl_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2, default=str)
    logger.info("Escrito %s", manifest_path.name)
    return manifest


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ETL de la Estrategia 2 (analisis ampliado) del ensayo NESP NCT00119613.")
    p.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help="Directorio con los .sas7bdat.")
    p.add_argument("--out", default=DEFAULT_OUT_DIR, help="Directorio de salida.")
    return p.parse_args()


# Punto de entrada. Fija semillas, ensambla, documenta, comprueba calidad y escribe
# los artefactos propios de la Estrategia 2 sin tocar los del primario.
def main() -> int:
    args = parse_args()
    random.seed(SEED)
    np.random.seed(SEED)

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logger(out_dir)

    logger.info("Directorio de datos: %s", data_dir)
    if not data_dir.exists():
        logger.error("El directorio de datos no existe. Pasa la ruta con --data-dir.")
        return 1

    try:
        df, provenance, labels = assemble(data_dir, logger)
        dictionary = build_dictionary(df, labels)
        quality = quality_report(df, logger)
        manifest = write_outputs(df, dictionary, provenance, quality, data_dir, out_dir, logger)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        logger.error("ETL detenido: %s", exc)
        return 1

    logger.info("Hash de referencia (csv): %s", manifest["hash_referencia_dataset"]["csv"])
    logger.info("ETL Estrategia 2 completado. Artefactos en: %s", out_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
