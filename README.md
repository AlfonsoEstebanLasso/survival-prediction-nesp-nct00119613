# TFG: prediccion de supervivencia bajo quimioterapia (NCT00119613)

Prototipo reproducible de investigacion para predecir supervivencia (OS y PFS) en una cohorte oncologica a partir de variables clinicas basales, con evaluacion robusta, control anti-leakage y documentacion transparente. No es un dispositivo clinico y no debe usarse con fines clinicos.

Trabajo Final de Grado, Grado en Ciencia de Datos (UOC), semestre 2025.1.

## Estructura

```
CLAUDE.md            memoria del proyecto para Claude Code (leer primero)
src/data/            ETL y construccion del dataset derivado
src/preprocessing/   preprocesado dentro de la validacion
src/models/          Cox, RSF, XGBoost/LightGBM
src/evaluation/      C-index, IBS, Brier, calibracion, bootstrap
src/reporting/       figuras y tablas
docs/                decision log, model card, guia de estilo y scripts de documentos
data/                metadatos (los datos crudos van en "SAS dataset/", no versionada)
outputs/             artefactos generados (no versionados)
tests/               pruebas
```

## Datos

La cohorte procede del estudio NESP-Oncology-20010145 (NCT00119613) en Project Data Sphere. Los datos clinicos crudos no se incluyen en el repositorio por privacidad por diseno. Coloca los ficheros `.sas7bdat` en una carpeta `SAS dataset/` en la raiz del proyecto. Ni los datos crudos ni el dataset derivado a nivel de sujeto se versionan.

## Puesta en marcha

Con conda:

```
conda env create -f environment.yml
conda activate tfg-nesp
```

Con pip:

```
pip install -r requirements.txt
```

Ejecutar el ETL desde la raiz del proyecto:

```
python src/data/etl_nesp_nct00119613.py
```

La ruta de datos por defecto apunta a `SAS dataset/`. Los artefactos (dataset, diccionario, manifiesto) se escriben en `output/`.

## Uso con Claude Code

Abre una terminal en la carpeta del proyecto y ejecuta `claude`. Claude Code leera `CLAUDE.md` y dispondra del contexto, las reglas metodologicas y la guia de estilo. Desde ahi puede continuar el pipeline (preprocesado, modelado, evaluacion) y generar los documentos D3, D4 y D5.

## Control de versiones (local)

```
git init
git add .
git commit -m "Bootstrap del proyecto TFG"
```

Los datos crudos y derivados quedan fuera del control de versiones por el `.gitignore`.
