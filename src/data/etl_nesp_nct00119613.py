"""
ETL del ensayo NESP-Oncology-20010145 (NCT00119613) para el TFG de Ciencia de Datos (UOC).

Proposito
    Leer los ficheros SAS (.sas7bdat) del estudio y construir un dataset derivado de
    una fila por sujeto (SUBJID) con los endpoints de supervivencia (OS y PFS) y el
    nucleo de covariables basales con senal (Estrategia 1, 7 predictores), apto para
    el pipeline de modelado de supervivencia documentado en las PEC.

Entradas (ficheros SAS, resueltos sin distinguir mayusculas/minusculas)
    c_keyvar.sas7bdat   espina: SUBJID, demografia y baseline (AGE, SEXCD, B_ECOGN,
                        B_HGB), brazo de aleatorizacion (TXG) y flags de evaluabilidad
    a_eendpt.sas7bdat   endpoints de supervivencia (DTH, DTHDY, PFSCD, PFSDY)
    c_bchar.sas7bdat    peso basal (B_WEIGHT)
    c_diag.sas7bdat     tiempo desde el diagnostico (CADIAGM)
    c_medhis.sas7bdat   historia medica (formato largo) para la covariable derivada

Salidas (en el directorio --out)
    nesp_nct00119613_dataset.parquet   dataset derivado (si hay motor parquet)
    nesp_nct00119613_dataset.csv       dataset derivado
    nesp_nct00119613_dictionary.csv    diccionario de variables del dataset
    nesp_nct00119613_etl_manifest.json manifiesto de procedencia y calidad
    nesp_nct00119613_etl_log.txt       traza de ejecucion

Transformaciones
    1. Normalizacion de nombres de columna a mayusculas en cada fuente.
    2. Seleccion de columnas por fuente segun la Estrategia 1.
    3. Derivacion de la covariable de comorbilidad MEDHX_N: numero de sistemas
       corporales con antecedente anormal (MEDHXYN = 1) por sujeto. El valor 7 de
       MEDHXYN (desconocido / no realizado) no cuenta como anomalia.
    4. Union LEFT JOIN por SUBJID sobre la espina c_keyvar.
    5. Ordenacion estable por SUBJID para reproducibilidad byte a byte del CSV.

Control anti-leakage
    Solo se incorporan variables basales (pre-tratamiento). Se excluyen de forma
    explicita las tablas longitudinales o post-basales (c_lesion, c_radio, c_trans,
    c_vitals) y las covariables documentadas de varianza cero en esta cohorte
    (RACECD, TUMORCD, EXTENTCD, CHDCLASS). El motivo de cada exclusion queda
    registrado en el manifiesto.

Uso (por ejemplo, desde la linea de comandos en Windows)
    python etl_nesp_nct00119613.py
    python etl_nesp_nct00119613.py --data-dir "SAS dataset" --out ".\\output"

Dependencias
    pip install pyreadstat pandas numpy
    (parquet opcional: pip install pyarrow)
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


# ----------------------------------------------------------------------------
# Configuracion
# ----------------------------------------------------------------------------

SEED = 42
SUBJECT_KEY = "SUBJID"
EXPECTED_N = 479  # tamano de cohorte esperado (control blando, solo advierte)

DEFAULT_DATA_DIR = r"SAS dataset"
DEFAULT_OUT_DIR = "output"
OUTPUT_STEM = "nesp_nct00119613"

# Fuentes a nivel de paciente y columnas seleccionadas de cada una.
SOURCES = {
    "spine":     ("c_keyvar.sas7bdat", [SUBJECT_KEY, "AGE", "SEXCD", "B_ECOGN",
                                        "B_HGB", "TXG", "EVALPRIM", "EVALQOL"]),
    "endpoints": ("a_eendpt.sas7bdat", [SUBJECT_KEY, "DTH", "DTHDY", "PFSCD", "PFSDY"]),
    "weight":    ("c_bchar.sas7bdat",  [SUBJECT_KEY, "B_WEIGHT"]),
    "diag":      ("c_diag.sas7bdat",   [SUBJECT_KEY, "CADIAGM"]),
}
MEDHIS_FILE = "c_medhis.sas7bdat"
DERIVED_COMORBIDITY = "MEDHX_N"

# Rol de cada variable del dataset final (variable -> rol, fuente, nota).
COLUMN_ROLES = {
    SUBJECT_KEY: ("clave", "c_keyvar", "Identificador de sujeto. Clave de union."),
    "DTH":      ("endpoint_OS_evento", "a_eendpt", "Muerte. 1 = evento, 0 = censura."),
    "DTHDY":    ("endpoint_OS_tiempo", "a_eendpt", "Dia de muerte o ultima observacion (dias)."),
    "PFSCD":    ("endpoint_PFS_evento", "a_eendpt", "Progresion o muerte. 1 = evento, 0 = censura."),
    "PFSDY":    ("endpoint_PFS_tiempo", "a_eendpt", "Tiempo a progresion o muerte (dias)."),
    "AGE":      ("predictor", "c_keyvar", "Edad (anos)."),
    "SEXCD":    ("predictor", "c_keyvar", "Sexo (codigo)."),
    "B_ECOGN":  ("predictor", "c_keyvar", "ECOG basal (categoria BYVAR)."),
    "B_WEIGHT": ("predictor", "c_bchar", "Peso basal."),
    "CADIAGM":  ("predictor", "c_diag", "Tiempo desde el diagnostico (meses). 1 valor faltante."),
    "B_HGB":    ("predictor", "c_keyvar", "Hemoglobina basal (g/dL). 3 valores faltantes."),
    DERIVED_COMORBIDITY: ("predictor_derivado", "c_medhis",
                          "Numero de sistemas con antecedente anormal (MEDHXYN = 1). Rango 0 a 6."),
    "TXG":      ("estratificacion", "c_keyvar",
                 "Brazo aleatorizado NESP/placebo. Solo estratificacion, NO predictor."),
    "EVALPRIM": ("flag_evaluabilidad", "c_keyvar", "Evaluable para el analisis primario."),
    "EVALQOL":  ("flag_evaluabilidad", "c_keyvar", "Evaluable para el analisis de calidad de vida."),
}

# Covariables documentadas excluidas por varianza cero en esta cohorte.
EXCLUDED_CONSTANTS = [
    {"variable": "RACECD",   "motivo": "Varianza cero: un unico valor en la cohorte."},
    {"variable": "TUMORCD",  "motivo": "Varianza cero: un unico tipo tumoral."},
    {"variable": "EXTENTCD", "motivo": "Varianza cero: todos los sujetos = 10."},
    {"variable": "CHDCLASS", "motivo": "Varianza cero: una sola clase (ANTINEOPLASTIC AGENTS)."},
]

# Ficheros excluidos por ser longitudinales o post-basales (control anti-leakage).
EXCLUDED_FILES = [
    {"fichero": "c_lesion.sas7bdat",
     "motivo": "Respuesta tumoral RECIST (rayos X, TC, respuesta global). Post-basal: usarlo seria leakage. Es el endpoint del que se pivoto."},
    {"fichero": "c_radio.sas7bdat",
     "motivo": "Radioterapia en estudio, concurrente y sensible al momento. No es basal limpio."},
    {"fichero": "c_trans.sas7bdat",
     "motivo": "Transfusiones en estudio, solo en 139 de 479 sujetos. La transfusion basal limpia ya esta en PRTFN."},
    {"fichero": "c_vitals.sas7bdat",
     "motivo": "ECOG y constantes vitales longitudinales. El ECOG basal ya esta en B_ECOGN."},
]


# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------

# Inicializa el logger del ETL con dos manejadores: consola (stdout) y fichero de traza.
# La traza persistente es un requisito de trazabilidad y reproducibilidad: permite
# reconstruir exactamente que ocurrio en cada ejecucion del pipeline, incluyendo
# advertencias de calidad y mensajes de error, sin necesidad de relectura del codigo.
def setup_logger(out_dir: Path) -> logging.Logger:
    logger = logging.getLogger("etl_nesp")
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

# Calcula el hash SHA-256 del fichero binario indicado por 'path'.
# Entrada: ruta al fichero (Path). Salida: cadena hexadecimal del digest SHA-256.
# El hash se usa como huella de integridad de cada fuente SAS en el manifiesto,
# garantizando que el dataset derivado sea rastreable hasta la version exacta del
# fichero de entrada. La lectura por bloques de 64 KB evita cargar ficheros
# grandes en memoria, lo cual es relevante cuando los .sas7bdat son voluminosos.
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):  # lectura por bloques para eficiencia en memoria
            h.update(chunk)
    return h.hexdigest()


# Resuelve la ruta de un fichero SAS dentro de 'data_dir' sin distinguir mayusculas
# ni minusculas. Entrada: directorio base (Path) y nombre de fichero (str).
# Salida: Path absoluto al fichero encontrado.
# La busqueda insensible a mayusculas es necesaria porque los sistemas de ficheros
# de Windows no distinguen el caso, pero el codigo debe ser portable a Linux (donde
# si se distingue). Esta funcion garantiza la reproducibilidad en ambos entornos.
def resolve_file(data_dir: Path, name: str) -> Path:
    """Devuelve la ruta del fichero buscando sin distinguir mayusculas/minusculas."""
    direct = data_dir / name
    if direct.exists():
        return direct
    target = name.lower()
    for p in data_dir.iterdir():
        if p.name.lower() == target:
            return p
    raise FileNotFoundError(f"No se encuentra '{name}' en {data_dir}")


# Carga un fichero SAS (.sas7bdat) con pyreadstat, normaliza los nombres de columna
# a mayusculas y extrae las etiquetas SAS de cada variable.
# Entrada: ruta al fichero SAS (Path). Salida: DataFrame con columnas en mayusculas
# y diccionario {NOMBRE_COL: etiqueta_SAS}.
# La normalizacion a mayusculas es un paso critico de homogeneizacion: los ficheros
# del estudio pueden exportar columnas en distintas combinaciones de caso segun la
# herramienta de extraccion, y el ETL asume mayusculas en todas las referencias
# posteriores (SOURCES, COLUMN_ROLES). Sin este paso, los LEFT JOIN fallarian
# silenciosamente si hay discrepancias de caso en SUBJID u otras claves.
def load_sas(path: Path) -> tuple[pd.DataFrame, dict]:
    """Lee un .sas7bdat, pasa los nombres de columna a mayusculas y devuelve etiquetas."""
    df, meta = pyreadstat.read_sas7bdat(str(path))
    df.columns = [c.upper() for c in df.columns]
    labels = {c.upper(): (lab or "") for c, lab in
              zip(meta.column_names, meta.column_labels)}
    return df, labels


# Selecciona el subconjunto de columnas 'cols' del DataFrame 'df' y verifica que
# todas esten presentes. Entrada: DataFrame cargado, lista de columnas requeridas,
# nombre de la fuente (para mensajes de error) y logger. Salida: copia del subconjunto.
# Hacer una copia explicita evita modificaciones accidentales sobre el DataFrame
# original (patron defensivo de calidad de datos). El control previo de columnas
# faltantes convierte un error silencioso de pandas en un KeyError descriptivo,
# lo que facilita la depuracion durante la integracion de nuevas versiones del estudio.
def select(df: pd.DataFrame, cols: list[str], source_name: str,
           logger: logging.Logger) -> pd.DataFrame:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"En {source_name} faltan columnas esperadas: {missing}")
    return df[cols].copy()


# ----------------------------------------------------------------------------
# Derivacion de comorbilidad
# ----------------------------------------------------------------------------

# Deriva la covariable de comorbilidad MEDHX_N a partir del fichero de historia
# medica c_medhis (formato largo, una fila por sistema corporal y sujeto).
# Entrada: DataFrame de c_medhis (ya normalizado a mayusculas) y logger.
# Salida: DataFrame con columnas [SUBJID, MEDHX_N], una fila por sujeto.
# Justificacion de diseno:
#   - Se filtra MEDHXYN == 1 para retener solo los sistemas con antecedente anormal.
#     El valor MEDHXYN == 7 (desconocido / no realizado) se excluye expresamente
#     porque no es informacion confirmada de presencia de patologia.
#   - Se cuenta el numero de sistemas corporales DISTINTOS (MEDHXCD.nunique()) por
#     sujeto, lo que produce una variable ordinal de carga comorbida con rango 0-6.
#   - MEDHX_N es un predictor basal derivado: resume la carga de antecedentes medicos
#     previos al tratamiento, relevante en oncologia porque la comorbilidad influye
#     en la tolerancia al regimen quimioterapeutico y en la supervivencia global (OS).
#   - Los sujetos sin ningun antecedente anormal no aparecen en 'comorb'; el LEFT JOIN
#     posterior en assemble() los recibe con NaN, que se rellena con 0 (cero sistemas).
def build_comorbidity(medhis: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    """MEDHX_N: numero de sistemas con antecedente anormal (MEDHXYN = 1) por sujeto."""
    for col in (SUBJECT_KEY, "MEDHXYN", "MEDHXCD"):
        if col not in medhis.columns:
            raise KeyError(f"c_medhis no contiene la columna requerida '{col}'")
    abnormal = medhis[medhis["MEDHXYN"] == 1]  # excluye MEDHXYN == 7 (desconocido): no cuenta como anomalia confirmada
    comorb = (abnormal.groupby(SUBJECT_KEY)["MEDHXCD"]
                      .nunique()  # numero de sistemas corporales distintos con antecedente anormal
                      .rename(DERIVED_COMORBIDITY)
                      .reset_index())
    logger.info("MEDHX_N derivada: %d sujetos con al menos un antecedente anormal.",
                len(comorb))
    return comorb


# ----------------------------------------------------------------------------
# Ensamblaje
# ----------------------------------------------------------------------------

# Orquesta la carga, seleccion, derivacion y union de todas las fuentes SAS para
# producir el dataset derivado de una fila por sujeto.
# Entrada: directorio de datos (Path) y logger. Salida: tupla (DataFrame ensamblado,
# diccionario de procedencia con hashes SHA-256, diccionario de etiquetas SAS).
# Justificacion de diseno:
#   - Cada fuente se carga de forma independiente y se valida la unicidad de SUBJID
#     antes de la union, asegurando que el modelo de datos sea 1:1 por sujeto.
#   - Se registra el hash SHA-256 de cada fichero fuente en 'provenance' para el
#     manifiesto de calidad: permite verificar que los datos de entrada no han
#     cambiado entre ejecuciones (trazabilidad byte a byte).
#   - La union es siempre LEFT JOIN sobre la espina c_keyvar, que contiene los 479
#     sujetos de la cohorte. Esto garantiza que no se pierda ningun sujeto por
#     ausencia en fuentes secundarias, y que no se incorporen sujetos no presentes
#     en la espina (control de poblacion).
#   - La reordenacion final de columnas segun COLUMN_ROLES impone un orden
#     semantico estable, independiente del orden de carga, lo que facilita la
#     reproducibilidad byte a byte del CSV de salida.
def assemble(data_dir: Path, logger: logging.Logger) -> tuple[pd.DataFrame, dict, dict]:
    provenance, labels_all = {}, {}

    # Cargar y seleccionar cada fuente a nivel de paciente.
    frames = {}
    for role, (fname, cols) in SOURCES.items():
        path = resolve_file(data_dir, fname)
        df, labels = load_sas(path)
        labels_all.update(labels)
        sub = select(df, cols, fname, logger)

        n_unique = sub[SUBJECT_KEY].nunique()
        n_dups = int(sub[SUBJECT_KEY].duplicated().sum())
        if n_dups:
            raise ValueError(f"{fname} tiene {n_dups} SUBJID duplicados; se esperaba clave unica.")
        provenance[fname] = {
            "sha256": sha256_file(path),  # hash SHA-256 del fichero fuente para el manifiesto de integridad
            "n_filas": int(len(df)),
            "subjid_unicos": int(n_unique),
        }
        logger.info("Cargada %s: %d filas, %d sujetos unicos.", fname, len(df), n_unique)
        frames[role] = sub

    # Covariable derivada de comorbilidad.
    medhis_path = resolve_file(data_dir, MEDHIS_FILE)
    medhis, labels_mh = load_sas(medhis_path)
    labels_all.update(labels_mh)
    provenance[MEDHIS_FILE] = {
        "sha256": sha256_file(medhis_path),  # hash SHA-256 de c_medhis para trazabilidad de la fuente de comorbilidad
        "n_filas": int(len(medhis)),
        "subjid_unicos": int(medhis[SUBJECT_KEY].nunique()),
    }
    logger.info("Cargada %s: %d filas, %d sujetos unicos.",
                MEDHIS_FILE, len(medhis), medhis[SUBJECT_KEY].nunique())
    comorb = build_comorbidity(medhis, logger)

    # Union LEFT JOIN sobre la espina c_keyvar: garantiza que la poblacion final
    # sea exactamente la definida por c_keyvar (479 sujetos), sin perdidas ni adiciones.
    df = frames["spine"]
    for role in ("endpoints", "weight", "diag"):
        df = df.merge(frames[role], on=SUBJECT_KEY, how="left")  # LEFT JOIN por SUBJID: la espina es la referencia de poblacion
    df = df.merge(comorb, on=SUBJECT_KEY, how="left")  # LEFT JOIN de MEDHX_N: sujetos sin antecedente anormal reciben NaN (se rellena con 0)
    df[DERIVED_COMORBIDITY] = df[DERIVED_COMORBIDITY].fillna(0).astype(int)

    # Orden estable y reordenacion de columnas segun el rol declarado.
    df = df.sort_values(SUBJECT_KEY).reset_index(drop=True)  # orden estable por SUBJID para reproducibilidad byte a byte del CSV
    ordered = [c for c in COLUMN_ROLES if c in df.columns]
    df = df[ordered]

    logger.info("Dataset ensamblado: %d filas, %d columnas.", df.shape[0], df.shape[1])
    return df, provenance, labels_all


# ----------------------------------------------------------------------------
# Diccionario y calidad
# ----------------------------------------------------------------------------

# Genera el diccionario de variables del dataset derivado.
# Entrada: DataFrame ensamblado y diccionario de etiquetas SAS. Salida: DataFrame
# con una fila por variable y columnas: variable, rol, fuente, etiqueta_sas, tipo,
# n_faltantes y nota.
# El diccionario de variables es un artefacto de documentacion exigido por el marco
# de transparencia (TRIPOD+AI, Model Card) y por los requisitos del RGPD de
# trazabilidad del tratamiento de datos personales de salud. Combina el rol semantico
# definido en COLUMN_ROLES con los metadatos estructurales del DataFrame (tipo y
# missingness), proporcionando una vista unica que facilita la auditoria del pipeline.
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


# Ejecuta las comprobaciones de calidad sobre el dataset ensamblado y devuelve
# un informe estructurado.
# Entrada: DataFrame final y logger. Salida: diccionario con tres secciones:
# 'checks' (resultado bool de cada verificacion), 'faltantes' (missingness por
# variable) y 'todo_ok' (flag global de aprobacion).
# Justificacion de diseno:
#   - La verificacion de unicidad de SUBJID en el dataset de salida es un control
#     de integridad referencial: cualquier duplicado indicaria un error en la union.
#   - La comparacion con EXPECTED_N (479) actua como control de poblacion: una
#     discrepancia puede senalar un cambio en la fuente o un filtrado incorrecto.
#   - La cobertura completa de los cuatro campos de endpoint (DTH, DTHDY, PFSCD,
#     PFSDY) es critica: valores faltantes en OS o PFS impediran el ajuste de los
#     modelos de supervivencia (Cox, RSF, XGBoost) y viciaran las metricas C-index
#     e IBS. DTH/DTHDY codifican OS (1 = muerte, 0 = censura) y PFSCD/PFSDY
#     codifican PFS (1 = progresion o muerte, 0 = censura).
def quality_report(df: pd.DataFrame, logger: logging.Logger) -> dict:
    checks, ok = {}, True

    dup = int(df[SUBJECT_KEY].duplicated().sum())
    checks["subjid_unico_en_salida"] = (dup == 0)
    ok = ok and (dup == 0)

    checks["n_filas"] = int(len(df))
    checks["coincide_n_esperado"] = (len(df) == EXPECTED_N)
    if len(df) != EXPECTED_N:
        logger.warning("Filas = %d, esperado = %d. Revisa la cohorte.", len(df), EXPECTED_N)

    # Cobertura de endpoints (no debe haber huecos).
    for c in ("DTH", "DTHDY", "PFSCD", "PFSDY"):  # OS: DTH/DTHDY; PFS: PFSCD/PFSDY - faltantes bloquean el modelado de supervivencia
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

# Escribe todos los artefactos del ETL en el directorio de salida:
# dataset (CSV y Parquet opcional), diccionario de variables, y manifiesto JSON.
# Entradas: DataFrame final, DataFrame diccionario, diccionario de procedencia con
# hashes, informe de calidad, rutas de datos y salida, logger. Sin valor de retorno.
# Justificacion de diseno:
#   - El CSV es el formato primario de intercambio (legible por cualquier herramienta).
#     El Parquet, cuando esta disponible pyarrow, preserva los tipos de datos con
#     mayor fidelidad y es mas eficiente para pipelines de modelado en pandas/sklearn.
#   - El manifiesto JSON es el artefacto de transparencia central: recoge el
#     identificador del estudio, la marca de tiempo UTC, las versiones de todas
#     las librerias (para reproducibilidad del entorno), los hashes SHA-256 de cada
#     fichero fuente, las variables excluidas por varianza cero, los ficheros
#     excluidos por riesgo de leakage y el informe de calidad. Este diseno cumple
#     con los requisitos de trazabilidad del RGPD y del marco TRIPOD+AI.
def write_outputs(df: pd.DataFrame, dictionary: pd.DataFrame, provenance: dict,
                  quality: dict, data_dir: Path, out_dir: Path,
                  logger: logging.Logger) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / f"{OUTPUT_STEM}_dataset.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8")
    logger.info("Escrito %s", csv_path.name)

    try:
        pq_path = out_dir / f"{OUTPUT_STEM}_dataset.parquet"
        df.to_parquet(pq_path, index=False)
        logger.info("Escrito %s", pq_path.name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo escribir parquet (%s). Instala 'pyarrow' si lo necesitas.", exc)

    dict_path = out_dir / f"{OUTPUT_STEM}_dictionary.csv"
    dictionary.to_csv(dict_path, index=False, encoding="utf-8")
    logger.info("Escrito %s", dict_path.name)

    manifest = {
        "estudio": "NESP-Oncology-20010145 (NCT00119613)",
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "semilla": SEED,
        "directorio_datos": str(data_dir),
        "versiones": {
            "python": sys.version.split()[0],
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "pyreadstat": pyreadstat.__version__,
        },
        "estrategia_covariables": "Estrategia 1: nucleo con senal (7 predictores)",
        "fuentes": provenance,  # hashes SHA-256 y estadisticos de cada fichero fuente para auditoria
        "dataset": {
            "n_filas": int(df.shape[0]),
            "n_columnas": int(df.shape[1]),
            "columnas": list(df.columns),
        },
        "constantes_excluidas": EXCLUDED_CONSTANTS,  # variables con varianza cero excluidas del dataset final
        "ficheros_excluidos_antileakage": EXCLUDED_FILES,  # tablas longitudinales o post-basales excluidas para prevenir leakage
        "calidad": quality,
    }
    manifest_path = out_dir / f"{OUTPUT_STEM}_etl_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2, default=str)
    logger.info("Escrito %s", manifest_path.name)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

# Parsea los argumentos de linea de comandos del ETL.
# Salida: Namespace con atributos 'data_dir' (ruta a los .sas7bdat) y 'out'
# (directorio de salida). Los valores por defecto apuntan a las rutas del proyecto.
# La interfaz por argumentos permite ejecutar el ETL en cualquier entorno sin
# modificar el codigo, lo que es un requisito de portabilidad y reproducibilidad
# en entornos limpios de verificacion (KPI-1 del TFG).
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ETL del ensayo NESP NCT00119613 para el TFG (UOC).")
    p.add_argument("--data-dir", default=DEFAULT_DATA_DIR,
                   help="Directorio con los ficheros .sas7bdat.")
    p.add_argument("--out", default=DEFAULT_OUT_DIR,
                   help="Directorio de salida para los artefactos.")
    return p.parse_args()


# Punto de entrada principal del ETL. Orquesta la secuencia completa:
# fijacion de semillas, configuracion del logger, carga y ensamblaje de fuentes,
# generacion del diccionario, informe de calidad y escritura de artefactos.
# Entrada: argumentos de linea de comandos (via parse_args). Salida: codigo de
# retorno 0 (exito) o 1 (error controlado).
# Justificacion de diseno:
#   - La semilla SEED se fija en random y numpy antes de cualquier operacion para
#     garantizar la reproducibilidad de cualquier componente estocastico que pueda
#     anadirse en el futuro al pipeline de datos.
#   - El tratamiento de excepciones captura solo errores esperados (fichero no
#     encontrado, columna ausente, duplicados); los errores inesperados se propagan
#     para facilitar la depuracion. El codigo de retorno permite la integracion en
#     scripts de CI/CD (KPI-1 de reproducibilidad en entorno limpio).
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
        write_outputs(df, dictionary, provenance, quality, data_dir, out_dir, logger)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        logger.error("ETL detenido: %s", exc)
        return 1

    logger.info("ETL completado. Artefactos en: %s", out_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
