# TFG: prediccion de supervivencia bajo quimioterapia (NCT00119613)

Prototipo reproducible de investigacion para predecir supervivencia (OS y PFS) en una
cohorte oncologica a partir de variables clinicas basales, con evaluacion robusta,
control anti-leakage y documentacion transparente.

**Advertencia:** este repositorio es un prototipo academico. No es un dispositivo
clinico y no debe usarse con fines clinicos ni para decisiones sobre pacientes.

Trabajo Final de Grado, Grado en Ciencia de Datos (UOC), semestre 2025.1.
Estudiante: Alfonso Esteban Lasso.

## Estructura del repositorio

```
CLAUDE.md              memoria del proyecto para Claude Code
src/data/              ETL y generacion de datos sinteticos
src/preprocessing/     preprocesado dentro de la validacion (anti-leakage)
src/models/            Cox PH, RSF, XGBoost y comparativa
src/evaluation/        C-index, IBS, Brier, calibracion, robustez, interpretabilidad
src/reporting/         figuras y tablas para la memoria
docs/                  decision_log.md, model_card.md, style_guide.md
data/                  metadatos (datos crudos en "SAS dataset/", no versionada)
output/                artefactos generados en ejecucion (no versionados)
tests/                 smoke tests del pipeline
environment.yml        entorno conda con versiones exactas congeladas (Sprint 8)
requirements.txt       equivalente pip con versiones exactas
```

## Datos de entrada

La cohorte procede del estudio NESP-Oncology-20010145 (NCT00119613), disponible
en Project Data Sphere. Los datos clinicos crudos no se incluyen por privacidad
por diseno.

1. Solicitar acceso en Project Data Sphere (NCT00119613).
2. Colocar los ficheros `.sas7bdat` en la carpeta `SAS dataset/` en la raiz del proyecto.

Ni los datos crudos ni el dataset derivado a nivel de sujeto se versionan.

## Puesta en marcha del entorno

Con conda (recomendado para reproducibilidad estricta):

```bash
conda env create -f environment.yml
conda activate tfg-nesp
```

Con pip:

```bash
pip install -r requirements.txt
```

Verificar la instalacion:

```bash
python -c "import pandas, numpy, sksurv, sdv; print('OK')"
pytest tests/ -q
```

## Ejecucion de extremo a extremo

Ejecutar todos los pasos desde la raiz del proyecto con el entorno activado.
Los artefactos se escriben en `output/` (gitignoreado).

### Paso 1: ETL y construccion del dataset derivado

```bash
python src/data/etl_nesp_nct00119613.py
```

Genera: `output/nesp_nct00119613_dataset.csv`, diccionario y manifiesto de calidad.
Prerequisito: ficheros `.sas7bdat` en `SAS dataset/`.

### Paso 2: Modelado (Cox, RSF, XGBoost y comparativa)

```bash
python src/models/compare_models.py
```

Ejecuta los tres modelos con CV k=5 y bootstrap n=1000, y guarda la tabla
comparativa en `output/model_comparison.csv`.

Si se quiere ejecutar un modelo por separado:

```bash
python src/models/cox_baseline.py
python src/models/rsf_model.py
python src/models/xgb_model.py
```

### Paso 3: Evaluacion completa del modelo final (Cox PH)

```bash
python src/evaluation/eval_cox_final.py
```

Genera calibracion, Brier Score y AUC dinamica con bandas bootstrap para OS y PFS.

### Paso 4: Robustez e interpretabilidad

```bash
python src/evaluation/robustness_cox.py
python src/evaluation/interpretability_cox.py
```

Genera analisis por subgrupos y valores SHAP.

### Paso 5: Datos sinteticos y riesgo de reidentificacion (Sprint 6)

```bash
python src/data/synthetic_data.py
```

Genera el dataset sintetico con CTGAN, evalua utilidad TSTR, membership inference
con shadow models, k-anonimidad y DCR. Tiempo estimado: 1-3 minutos en CPU.

Artefactos principales: `output/synthetic_metrics.json` y cuatro figuras PNG.
El dataset sintetico (`output/synthetic_dataset.csv`) no se versiona.

**Advertencia:** los datos sinteticos son solo para prototipado metodologico;
no refuerzan las conclusiones del modelo principal.

## Orden recomendado para una ejecucion completa

```
Paso 1  ->  Paso 2  ->  Paso 3  ->  Paso 4  ->  Paso 5
```

Cada paso lee los artefactos del anterior desde `output/`. No se puede saltar el ETL.

## Ejecucion de los tests

```bash
pytest tests/ -v
```

Los smoke tests cubren:

- `test_preprocessor.py`: imputador adaptativo y pipeline de preprocesado.
- `test_pipeline_smoke.py`: anti-leakage, semillas, predicciones OOF y C-index.
- `test_synthetic_smoke.py`: k-anonimidad, DCR y criterios de aceptacion a priori.

Todos los tests usan datos sinteticos generados internamente; no requieren el
dataset real.

## Control de versiones del entorno

Las versiones exactas de los paquetes estan congeladas en `environment.yml` y
`requirements.txt` (Sprint 8, 2026-06-01). Para generar un fichero de lock exacto:

```bash
pip freeze > requirements.lock.txt
```

## Anti-leakage: garantias del pipeline

- El preprocesador (imputacion, escalado, codificacion) se ajusta exclusivamente
  sobre el fold de entrenamiento dentro del CV k=5.
- Los predictores son variables basales: AGE, SEXCD, B_ECOGN, B_WEIGHT, CADIAGM,
  B_HGB y MEDHX_N. Nunca se incluyen outcomes (DTH, DTHDY, PFSCD, PFSDY) ni TXG.
- La busqueda de hiperparametros (Optuna) opera sobre splits internos del fold de
  entrenamiento; el fold de test nunca se usa para seleccionar hiperparametros.
- El bootstrap evalua predicciones OOF (nunca datos de entrenamiento del fold).
- La ausencia de leakage se verifica por la estabilidad del rendimiento entre folds
  (CV% < 10 %) y por los smoke tests de `test_pipeline_smoke.py`.

## Reproducibilidad

Semilla global: `SEED = 42` (definida en `src/models/cv_utils.py` e importada
por todos los scripts). Para reproducir exactamente los resultados:

1. Usar el mismo entorno: `conda env create -f environment.yml`.
2. Colocar los mismos datos crudos en `SAS dataset/`.
3. Ejecutar los pasos en orden.

## Uso con Claude Code

```bash
claude
```

Claude Code leera `CLAUDE.md` y dispondra del contexto metodologico completo.
