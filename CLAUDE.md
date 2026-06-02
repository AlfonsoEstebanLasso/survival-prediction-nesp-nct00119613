# CLAUDE.md

Memoria del proyecto para Claude Code. Lee este fichero al inicio de cada sesion y respeta las reglas que contiene. El detalle vivo se mantiene en `docs/decision_log.md`, `docs/model_card.md` y `docs/style_guide.md`.

## 1. Proposito

Trabajo Final de Grado del Grado en Ciencia de Datos (UOC, semestre 2025.1). Titulo: "Prediccion de respuesta a farmacos quimioterapeuticos a partir de datos clinicos anonimizados". Estudiante: Alfonso Esteban Lasso ([email-eliminado]). Tutor: Tutor del TFG. El objetivo no es un dispositivo clinico, sino un prototipo de investigacion reproducible y auditable que prediga supervivencia bajo quimioterapia y documente el proceso con transparencia.

## 2. Reglas de estilo y comunicacion (obligatorias)

- Responde siempre en espanol, tono universitario formal.
- Prohibidos los guiones largos (las rayas em y en). Usa puntos, comas, dos puntos, parentesis o guiones simples.
- No menciones ningun centro externo de colaboracion en ningun documento ni respuesta. El TFG se trabaja sin nombrarlo.
- Respuestas y entregables listos para usar, sin pasos intermedios de revision salvo que se pidan.

## 3. Eje metodologico (no cambiar sin registrar la decision)

- Cohorte y fuente: Project Data Sphere, estudio NESP-Oncology-20010145 (ensayo NCT00119613).
- Tamano muestral REAL: n = 479 sujetos (una fila por sujeto). El valor 600 que aparece en informes previos era ilustrativo. Usa 479.
- Variable objetivo: supervivencia con censura. OS a partir de DTH/DTHDY y PFS a partir de PFSCD/PFSDY (pivote P1, desde la clasificacion RECIST/ORR).
- Validacion: validacion cruzada estratificada k=5 con bootstrap de n=1000 (pivote P2, adaptado al tamano muestral).
- Brazo de aleatorizacion TXG (NESP/placebo): variable de estratificacion, nunca predictor ni objeto causal.
- Modelos: Cox proporcional (baseline), Random Survival Forest y XGBoost/LightGBM con perdida de supervivencia.
- Metricas: C-index, IBS, Brier, AUC dependiente del tiempo y curvas de calibracion con bandas. Postcalibracion (Platt e isotonica) evaluada; el modelo final se reporta sin postcalibracion por parsimonia.
- Criterio de seleccion de modelo, fijado a priori (registrado en el Decision log): metrica principal (C-index) mas IBS mas coeficiente de variacion entre folds (estabilidad). Aplica esta regla a los numeros reales para decidir el modelo final.
- Interpretabilidad: SHAP post-hoc, con la advertencia de que no es causal y puede ser inestable bajo cambio de distribucion.
- Marco regulatorio: RGPD, LOPDGDD, AI Act y guias de anonimizacion de la AEPD. Advertencia explicita de no uso clinico.

## 4. Datos y privacidad (privacidad por diseno)

- Los datos clinicos crudos (`*.sas7bdat`, carpeta `SAS dataset/`) NO se versionan nunca. Estan en `.gitignore`.
- El acceso a los datos es por Project Data Sphere. El repositorio documenta como obtenerlos, no los incluye.
- El dataset derivado a nivel de sujeto tampoco se versiona. Solo se pueden versionar metadatos: diccionario de variables, hashes y manifiesto de calidad.
- Minimizacion y trazabilidad en todo el pipeline.

## 5. Reglas anti-leakage (invariantes)

- Todo el preprocesado (imputacion, codificacion, escalado) se ajusta SOLO sobre el fold de entrenamiento, dentro del esquema de validacion. Nunca sobre el dataset completo.
- No se usan variables posteriores al outcome ni informacion temporal posterior al inicio del tratamiento.
- Ficheros excluidos por ser longitudinales o post-basales: `c_lesion` (respuesta RECIST), `c_radio` (radioterapia en estudio), `c_trans` (transfusiones en estudio), `c_vitals` (ECOG longitudinal). No usar como predictores.
- Covariables excluidas por varianza cero en esta cohorte: RACECD, TUMORCD, EXTENTCD, CHDCLASS.
- La ausencia de leakage se verifica por la estabilidad del rendimiento entre folds.

## 6. Contrato del ETL (ya implementado en `src/data/etl_nesp_nct00119613.py`)

- Clave de union: SUBJID.
- Estrategia 1 de covariables (7 predictores basales con senal): AGE, SEXCD, B_ECOGN, B_WEIGHT, CADIAGM, B_HGB y MEDHX_N.
- MEDHX_N es una covariable derivada de `c_medhis`: numero de sistemas corporales con antecedente anormal (MEDHXYN = 1) por sujeto. Rango 0 a 6. El valor 7 de MEDHXYN no cuenta como anomalia.
- Endpoints: ambos, OS (DTH, DTHDY) y PFS (PFSCD, PFSDY), con 1 = evento y 0 = censura.
- Poblacion: las 479 filas, sin filtrar, con los flags EVALPRIM y EVALQOL como columnas.
- Espina c_keyvar con LEFT JOIN sobre a_eendpt, c_bchar, c_diag y la covariable derivada de c_medhis.
- El script genera: dataset (CSV y Parquet), diccionario, manifiesto de calidad con hashes SHA-256 y traza de ejecucion.

## 7. Valores ilustrativos frente a valores reales

Los numeros que aparecen en PEC3 (C-index, IBS, Brier, estabilidad) son ILUSTRATIVOS. La memoria final (D3) debe reportar los valores REALES que salgan del pipeline. Al ejecutar el modelado, sustituye los ilustrativos por los reales y vuelve a aplicar el criterio de seleccion a priori para confirmar el modelo final.

## 8. Estructura del repositorio

```
src/data/          ETL y construccion del dataset derivado
src/preprocessing/ preprocesado dentro de la validacion (siguiente a implementar)
src/models/        Cox, RSF, XGBoost/LightGBM
src/evaluation/    C-index, IBS, Brier, calibracion, bootstrap
src/reporting/     figuras y tablas
docs/              decision_log.md, model_card.md, style_guide.md y scripts de documentos
data/              metadatos (los datos crudos van en SAS dataset/, no versionada)
outputs/           artefactos generados (no versionados)
tests/             pruebas (smoke tests del pipeline)
```

## 9. Entorno y comandos

- Crear entorno con conda: `conda env create -f environment.yml` y `conda activate tfg-nesp`. Alternativa con pip: `pip install -r requirements.txt`.
- Ejecutar el ETL desde la raiz del proyecto: `python src/data/etl_nesp_nct00119613.py`. La ruta de datos por defecto apunta a `SAS dataset/`; la salida va a `output/`.
- Antes del release de D1 (Sprint 8) hay que congelar las versiones exactas en `environment.yml` para la verificacion en entorno limpio (KPI-1).

## 10. Entregables y estado

- D0 Plan de trabajo: completo.
- D1 Repositorio del pipeline: ETL completo; faltan preprocesado, modelado, evaluacion, reporting y el release versionado.
- D2 Dataset derivado, diccionario y reporte de calidad: completo.
- D3 Memoria final: completo. Generada con valores reales del pipeline e incluye el anexo 7.4 (matriz de trazabilidad de resultados de aprendizaje) en `output/D3_Memoria_TFG_NESP.docx` (generador `docs/scripts/build_d3.js`). Pendiente manual: actualizar campos en Word (F9) y exportar a PDF.
- D4 Paquete de transparencia (TRIPOD+AI, Model Card final, analisis de riesgos): completo. Generado en `output/D4_paquete_transparencia.docx` (generador `docs/scripts/build_d4.js`); fuente viva en `docs/D4_paquete_transparencia.md` y `docs/model_card.md`. Pendiente manual: F9 y exportar a PDF.
- D5 Presentacion y guion de defensa: completo. Presentacion en `output/D5_presentacion.pptx` (generador `docs/scripts/build_d5.js`, libreria pptxgenjs) y guion cronometrado a 20 minutos en `output/D5_guion.md`. Pendiente manual: grabar el video de la exposicion y exportar la presentacion a PDF.

Sprints: 1 a 6 cerrados; Sprint 7 (redaccion y TRIPOD+AI) cerrado; Sprint 8 (entorno limpio, release y defensa) en curso, pendiente el release versionado de D1 y la grabacion del video. Entrega final PEC4: 02/06/2026.

KPIs: KPI-1 reproducibilidad, KPI-2 calidad de datos, KPI-3 rendimiento (mejora sobre baseline), KPI-4 calibracion, KPI-5 evaluacion etico-legal.

## 11. Generacion de documentos (.docx)

Los entregables D3 y D4 se generan como Word (.docx) mediante scripts de Node con la libreria `docx`; el D5 se genera como PowerPoint (.pptx) con la libreria `pptxgenjs` (ver `package.json` y `docs/scripts/_style.js`). Sigue siempre `docs/style_guide.md`: fuente Arial, azul corporativo (oscuro 1F4E79, claro D5E8F0), verde 1F7A3A para completo y ambar B7791F para en curso, pie "Pagina X de Y", cabecera UOC, tablas con filas alternadas y resumenes ejecutivos con barra lateral azul. Recuerda: sin guiones largos.

## 12. Como trabajar en este repositorio

- Reproducibilidad: semillas fijas en todo el codigo.
- Cada script lleva en cabecera su proposito, entradas, salidas y transformaciones.
- Commits pequenos y descriptivos. Solo control de versiones local (git), sin remoto.
- Cuando tomes una decision metodologica, registrala en `docs/decision_log.md`.
- Manten viva la Model Card en `docs/model_card.md` a medida que avanza el trabajo.
- Trabaja por pasos pequenos y muestra los cambios antes de aplicarlos.

## 13. Politica de modelos y optimizacion

- Modelo por defecto del proyecto: Sonnet, fijado en `.claude/settings.json`. Protege el limite semanal de Opus para el trabajo rutinario (ETL, preprocesado, modelado, refactors, generacion de documentos).
- Sube a Opus con `/model` solo para tareas que lo justifican: diseno de la evaluacion, depuracion de un posible leakage, decisiones estadisticas o metodologicas delicadas y revision critica de la memoria. Vuelve a Sonnet despues.
- Higiene de contexto: usa `/clear` entre tareas no relacionadas y `/compact` dentro de una sesion larga. Evita arrastrar muchos ficheros leidos, porque cada mensaje nuevo carga todo el historico.
- Idioma: espanol, fijado en `.claude/settings.json`.
- Vigila la cuota con la barra de estado o `/usage`, sobre todo al empezar y en sesiones largas.
- Privacidad: no se leen los `.sas7bdat` ni el dataset derivado al contexto (restringido en `.claude/settings.json`). El ETL los procesa en tiempo de ejecucion.

## Siguiente paso sugerido

Implementar `src/preprocessing/`: un transformador que se ajuste dentro de cada fold con imputacion por mediana o moda cuando el missingness es igual o inferior al 20 por ciento e imputacion iterativa cuando supera el 20 por ciento con patron MAR, estandarizacion de numericas y codificacion one-hot de categoricas, sin fuga entre train y test.
