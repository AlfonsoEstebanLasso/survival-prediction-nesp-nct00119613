# Decisión log

Registro de decisiones metodológicas y de diseño. Añade una entrada nueva cada vez que tomes o cambies una decisión relevante. Formato: fecha, decisión, motivo, alternativa descartada.

## Decisiones registradas

### Fuente de datos y marco interpretativo
La cohorte procede del estudio NESP-Oncology-20010145 (NCT00119613) en Project Data Sphere, no de cBioPortal como contemplaba la propuesta inicial. Motivo: variables de outcome más completas y trazables, homogeneidad del régimen quimioterapéutico y trazabilidad temporal del seguimiento. El ensayo es de fase III (Darbepoetin Alfa frente a placebo); el TFG lo reformula como pronóstico bajo quimioterapia y no estudia el efecto del agente eritropoyético.

### Pivote P1: variable objetivo a supervivencia
Tras la auditoria de la cohorte, el exceso de valores faltantes en las etiquetas de respuesta directa (RECIST/ORR) comprometia una clasificación binaria valida. Se reformulo a supervivencia con censura (OS y PFS). Diseño adaptado: Cox baseline, Random Survival Forest y XGBoost/LightGBM con perdida de supervivencia, con C-index e IBS como métricas principales.

### Pivote P2: validación adaptada al tamaño muestral
n efectivo = 479. Se aplico validación cruzada estratificada k=5 con regularizacion robusta y bootstrap n=1000, priorizando estabilidad sobre complejidad.

### Ajuste 3: brazo NESP/placebo como estratificación
La asignación TXG se usa como variable de estratificación y se reporta rendimiento por estrato, no como predictor. Motivo: evitar que el modelo aprenda el efecto del fármaco del estudio en lugar de la heterogeneidad clínica, y permitir análisis de transferibilidad entre estratos.

### Estrategia de covariables (Estrategia 1)
Núcleo de 7 predictores basales con señal: AGE, SEXCD, B_ECOGN, B_WEIGHT, CADIAGM, B_HGB y MEDHX_N (comorbilidad derivada). Se excluyen por ser constantes en la cohorte: TUMORCD, EXTENTCD y CHDCLASS son invariantes por los criterios de inclusión del protocolo (todos los sujetos son cáncer de pulmón microcítico en estadio extenso tratados con platino y etopósido), y RACECD presenta varianza cero observada en esta cohorte. Alternativas descartadas: enriquecer con basales adicionales (EPO, LDH, transfusión) y mantener las 11 covariables literales con columnas constantes.

### Derivación de MEDHX_N
Comorbilidad operacionalizada como número de sistemas corporales con antecedente anormal (MEDHXYN = 1) por sujeto, rango 0 a 6. El valor 7 de MEDHXYN no cuenta como anomalía.

### Tamaño muestral real
n = 479 (confirmado por el ETL). El protocolo planifico aproximadamente 600 sujetos (unos 300 por brazo, con análisis final previsto a las 496 muertes); la cohorte disponible en Project Data Sphere comprende 479. La cifra de 600 que aparecia en informes previos corresponde al tamaño planificado del ensayo, no a una cantidad ilustrativa. La memoria final usa 479.

### Criterio de selección de modelo (a priori)
Fijado antes de observar resultados: métrica principal (C-index) más IBS más coeficiente de variación entre folds. Se aplicara a los valores reales del pipeline para confirmar el modelo final.

### Postcalibracion
Se evaluan Platt e isotónica. Si las mejoras son marginales y no significativas frente a los IC bootstrap, el modelo final se reporta sin postcalibracion por parsimonia.

### Valores ilustrativos frente a reales
Los números de PEC3 son ilustrativos. La memoria final reportara los valores reales del pipeline.

### Selección del modelo final: Cox proporcional (parsimonia)

**Fecha:** 2026-06-01. **Decisión:** el modelo final es el Cox proporcional de Harrell,
retenido por parsimonia. Ningún candidato mejora de forma estadísticamente significativa
el baseline segun el criterio de selección fijado a priori (C-index + IBS + CV%).

**Resultados reales del pipeline (CV k=5, bootstrap n=1000):**

| Modelo   | OS C-index (CV)     | OS IBS (CV)         | PFS C-index (CV)    |
|----------|---------------------|---------------------|---------------------|
| Cox PH   | 0.600 +/- 0.042     | 0.182 +/- 0.013     | 0.552 +/- 0.028     |
| RSF      | 0.593 +/- 0.027     | 0.181 +/- 0.011     | 0.544 +/- 0.024     |
| XGBoost  | 0.549 +/- 0.030     | 0.187 +/- 0.014     | 0.528 +/- 0.030     |

**Justificación detallada:**

- **RSF** es el mejor candidato en términos de discriminación equivalente a Cox (diferencia
  de C-index OS = 0.007, inferior al nivel de ruido del CV) y mayor estabilidad entre folds
  (CV% = 4.5% frente a 7.0% de Cox). Sin embargo, el intervalo bootstrap del C-index se solapa
  completamente con el de Cox: RSF IC95% [0.562, 0.621] frente a Cox IC95% [0.567, 0.629]. La
  diferencia no es estadísticamente significativa. El IBS es prácticamente idéntico (0.181 vs
  0.182). Aplicando el principio de parsimonia, no hay justificación para sustituir Cox por RSF.
- **XGBoost** queda por detrás en ambos endpoints. Con n=479 y 7 predictores, el early
  stopping activa tras 1-30 árboles en la mayoría de folds, indicando que la señal disponible
  no sustenta la capacidad de un modelo gradient-boosted. Los intervalos bootstrap no se solapan
  favorablemente con Cox.

**KPI-3 (mejora sobre baseline): NO CUMPLIDO.** Este es un hallazgo honesto y esperado.
Con n=479, 7 predictores basales y alta tasa de eventos (83% OS), la superficie de decisión
es prácticamente lineal. El supuesto de proporcionalidad de Cox se ajusta bien a estos datos
y los modelos no lineales no tienen ventaja en esta cohorte. Se documenta como limitación
explícitamente en la memoria final (D3) y en la Model Card.

**Alternativa descartada:** usar RSF como modelo final pese a la equivalencia estadística.
Razón: el coste interpretativo (no hay coeficientes directamente interpretables) no se justifica
ante la ausencia de ganancia significativa en discriminación ni en calibración.

### Evaluación del modelo final: métricas reales OS (primario) y PFS (secundario)

**Fecha:** 2026-06-01. **Alcance:** curvas de calibración con bandas bootstrap, Brier Score
a lo largo del tiempo, AUC dinámica acumulada con bandas bootstrap. Todas las métricas se
calculan sobre predicciones OOF (out-of-fold) del CV k=5 para evitar sobreajuste.

Resultados sintéticos (valores completos en output/eval_*.csv):

- OS Boot C-index: 0.599 IC95% [0.567, 0.629]
- OS Boot IBS:     0.182 IC95% [0.172, 0.191]
- PFS Boot C-index: 0.555 IC95% [0.525, 0.586]
- PFS Boot IBS:     0.182 IC95% [0.172, 0.192]

### Componente de datos sintéticos (Sprint 6)

**Fecha:** 2026-06-01. **Alcance:** generación con CTGAN (SDV >= 1.0), evaluación de
utilidad TSTR y evaluación de riesgo de reidentificación en tres dimensiones.

**Decisiones de diseño:**

- Generador: CTGANSynthesizer de SDV con 300 épocas y n_sintético = n_real = 479.
  Columnas binarias (DTH, PFSCD, TXG, EVALPRIM, EVALQOL) y categóricas (SEXCD, B_ECOGN)
  declaradas explícitamente como "categorical" en los metadatos SDV.
- TSTR: preprocesador ajustado solo sobre datos sintéticos (escenario TSTR puro);
  evaluación sobre cada fold de test real del CV k=5; comparación directa con TRTR.
- Membership inference: N=5 shadow models, cada uno ajustado sobre el 70% del real,
  con 100 épocas. Score = negativo de la distancia Euclídea mínima en el espacio
  preprocesado. AUC y TPR a FPR=0.1 sobre los pares pooled de todos los shadows.
- K-anonimidad: cuasi-identificadores AGE (bins de 5 años), SEXCD y B_ECOGN.
  Para cada registro sintético, se cuenta el número de registros reales con la misma
  combinación de QI. Se reportan las fracciones k=1, k<=2, k<=5.
- DCR: distancia Euclídea mínima de cada sintético al real más cercano, en el espacio
  preprocesado (ajuste sobre reales para espacio de referencia común). RRDR (LOO)
  como referencia del ruido natural del dataset.

**Criterios de aceptación a priori (privacidad):**
  - Membership inference: AUC <= 0.60, TPR@FPR=0.1 <= 0.20
  - K-anonimidad: k=1 < 5%, k<=2 < 10%, k<=5 < 20%
  - DCR: DCR_p5 / RRDR_mediana >= 0.50

**Advertencia invariante:** los datos sintéticos son exclusivamente para prototipado
metodológico. No refuerzan las conclusiones del modelo principal de supervivencia.

### Evaluación final de datos sintéticos: resultados reales

**Fecha:** 2026-06-01. **Alcance:** resultados numéricos del pipeline de evaluación de
riesgo de reidentificación y utilidad (output/synthetic_metrics.json).

**Resultados por dimensión:**

| Dimensión | Valor | Umbral | Resultado |
|-----------|-------|--------|-----------|
| Membership inference AUC | 0.534 | <= 0.60 | ACEPTADO |
| TPR @ FPR=0.1 | 0.139 | <= 0.20 | ACEPTADO |
| K-anonimidad k=1 (bins 5a) | 7.32% | < 5.00% | NO ACEPTADO |
| K-anonimidad k<=2 (bins 5a) | 10.04% | < 10.00% | NO ACEPTADO |
| K-anonimidad k<=5 (bins 5a) | 20.71% | < 20.00% | NO ACEPTADO |
| DCR_p5 / RRDR_mediana | 0.622 | >= 0.50 | ACEPTADO |

**Evaluación global: NO ACEPTADO** por k-anonimidad con la configuración preregistrada
(bins de edad de 5 años). El membership inference y la DCR pasan sin problemas.

**Análisis de sensibilidad:** con bins de edad de 10 años, k1=5.44%, k2=7.32%, k5=11.51%.
K2 y k5 pasan el umbral; k1 sigue por encima (5.44% > 5.00%). La k-anonimidad es
sensible a la granularidad del binning de la variable de edad.

**Utilidad TSTR:** C-index medio TSTR = 0.437 vs TRTR = 0.600. Ratio = 72.8%.

**Decisión:** los datos sintéticos se documentan con el resultado de NO ACEPTADO y se
acompanan del análisis de sensibilidad. Su uso queda restringido al prototipado
metodológico, con advertencia explícita en la memoria y en la Model Card.

### Proporcionalidad de Cox: test de Schoenfeld

**Fecha:** 2026-06-01. **Alcance:** verificación del supuesto de proporcionalidad de
riesgos en el modelo final Cox PH (output/cox_schoenfeld_test.csv).

**Resultados:**

| Variable | Endpoint | p Schoenfeld | Supuesto OK |
|----------|----------|-------------|------------|
| AGE | OS | 0.030 | No |
| B_WEIGHT | OS | 0.026 | No |
| B_WEIGHT | PFS | 0.011 | No |
| Resto de variables | OS y PFS | > 0.10 | Si |

**Interpretación:** AGE y B_WEIGHT muestran evidencia de efectos no proporcionales en OS;
B_WEIGHT también en PFS. El resto de variables (SEXCD, B_ECOGN, B_HGB, CADIAGM, MEDHX_N)
cumplen el supuesto. Las variables con mayor señal pronóstica (SEXCD, B_ECOGN) no violan
el supuesto.

**Decisión:** se reporta la violación parcial como limitación explícita en la Model Card
y en la memoria final (D3). No se reestima el modelo con extensiones de tiempo variable,
dado el carácter de prototipo académico y el tamaño muestral moderado. Alternativas
descartadas: modelo de Cox estratificado por tiempo o con interaccion tiempo-covariable.

### Hazard ratios significativos del modelo final

**Fecha:** 2026-06-01. **Alcance:** tabla de coeficientes e interpretación de las
asociaciones estadísticamente significativas (output/cox_hazard_ratios.csv).

**OS (predictores significativos):**
- MEDHX_N: HR = 1.086 IC95% [1.003, 1.177], p = 0.042. Cada sistema corporal adicional
  con antecedente anómalo se asocia con un 8.6% más de riesgo de muerte.
- SEXCD = 1 (femenino vs masculino): HR = 0.641 IC95% [0.514, 0.799], p < 0.001.
  El sexo femenino se asocia con un 36% menos de riesgo de muerte.
- B_ECOGN = 2 vs 1: HR = 1.693 IC95% [1.326, 2.160], p < 0.001. El estado funcional
  reducido se asocia con un 69% más de riesgo de muerte.

**PFS (predictores significativos):**
- SEXCD = 1: HR = 0.779 IC95% [0.634, 0.958], p = 0.018.
- B_ECOGN = 2 vs 1: HR = 1.432 IC95% [1.132, 1.811], p = 0.003.

**Nota:** las asociaciones son descriptivas. El ensayo no fue disenado para identificar
estos efectos y pueden estar confundidos por factores no medidos. No se interpretan como
relaciones causales.

### Análisis de subgrupos: resultados reales

**Fecha:** 2026-06-01. **Alcance:** rendimiento del modelo final por estrato
(output/robustness_subgroups_OS.csv y robustness_subgroups_PFS.csv). Estadísticas
bootstrap calculadas sobre cada subgrupo por separado.

**OS - resumen de subgrupos:**

| Subgrupo | n | C-index | IC95% |
|----------|---|---------|-------|
| Global | 479 | 0.599 | [0.569, 0.630] |
| Brazo NESP (TXG=1) | 240 | 0.587 | [0.542, 0.629] |
| Brazo placebo (TXG=0) | 239 | 0.611 | [0.564, 0.655] |
| ECOG 1 | 379 | 0.574 | [0.537, 0.607] |
| ECOG 2 | 100 | 0.525 | [0.453, 0.593] |
| MEDHX_N <= 1 | 253 | 0.601 | [0.561, 0.642] |
| MEDHX_N > 1 | 226 | 0.591 | [0.546, 0.637] |

**PFS - resumen de subgrupos:**

| Subgrupo | n | C-index | IC95% |
|----------|---|---------|-------|
| Global | 479 | 0.555 | [0.525, 0.585] |
| Brazo NESP (TXG=1) | 240 | 0.536 | [0.490, 0.575] |
| Brazo placebo (TXG=0) | 239 | 0.572 | [0.526, 0.616] |
| ECOG 1 | 379 | 0.528 | [0.492, 0.562] |
| ECOG 2 | 100 | 0.484 | [0.420, 0.550] |

**Conclusión:** el rendimiento es consistente entre estratos. La caída en ECOG 2 es
esperable por la menor heterogeneidad pronóstica en ese subgrupo. La similitud entre
brazos NESP y placebo confirma la transferibilidad del modelo entre estratos de
tratamiento, coherente con su diseño basado en predictores basales únicamente.

### Calibración del modelo final: KPI-4

**Fecha:** 2026-06-01. **Alcance:** curvas de calibración para OS y PFS evaluadas sobre
predicciones OOF del CV k=5, en tres horizontes temporales por endpoint. Estimación
observada mediante Kaplan-Meier (km_obs) con bandas bootstrap (output/eval_calibration_OS.csv,
output/eval_calibration_PFS.csv, output/fig_calibration_OS.png).

**KPI-4: CUMPLIDO.** La calibración es aceptable en el rango central del horizonte temporal
y ruidosa en los extremos, lo cual es esperable con n=479 sujetos y la alta tasa de eventos.

**Hallazgos por horizonte temporal (OS):**

- **t = 164 días:** bien calibrado. Los deciles siguen la diagonal con dispersión moderada
  y sin sesgo sistemático. Las predicciones en el rango central (supervivencia estimada
  0.70-0.85) son las más fiables.

- **t = 259 días:** bien calibrado. La mayoría de deciles se situan próximos a la diagonal
  dentro de los IC bootstrap. Ligera dispersión en los extremos coherente con el tamaño
  muestral.

- **t = 355 días:** los deciles de alto riesgo (grupos con supervivencia predicha baja,
  < 0.35) quedan por encima de la diagonal: km_obs > mean_pred. El modelo subestima la
  supervivencia en ese extremo temporal para los pacientes de mayor riesgo. Los deciles
  de riesgo bajo (supervivencia predicha > 0.45) son más estables pero con mayor
  incertidumbre por el número reducido de sujetos en riesgo a esa profundidad de seguimiento.

**Interpretación general:** el patrón de subestimacion a t=355 en los deciles de alto riesgo
es coherente con un modelo de Cox sin covariables tiempo-dependientes y con la violación
parcial del supuesto de proporcionalidad en AGE y B_WEIGHT (registrada en la entrada
"Proporcionalidad de Cox"). No invalida el modelo para su uso como prototipo de investigación;
si limita la precisión de las predicciones absolutas de supervivencia en el largo plazo para
el subgrupo de mayor riesgo. Se documenta como limitación en la memoria final (D3) y en la
Model Card.

**Postcalibracion:** Platt e isotónica evaluadas. Mejoras marginales sin significación
estadística frente a los IC bootstrap. Decisión final: modelo reportado sin postcalibracion
por parsimonia.

### Entregable D5 y matriz de trazabilidad de resultados de aprendizaje (PEC4)

**Fecha:** 2026-06-02. **Alcance:** generación de la presentación de defensa (D5) y
ampliación de la memoria final (D3) con la matriz de trazabilidad de resultados de aprendizaje.

**Decisiones:**

- **D5 presentación (output/D5_presentacion.pptx):** 15 diapositivas con la paleta del
  proyecto (azul 1F4E79 y D5E8F0, verde 1F7A3A, ámbar B7791F), fuente Arial y una idea por
  diapositiva, apoyada en las figuras de output/. Generador reproducible en
  docs/scripts/build_d5.js (dependencia pptxgenjs). Guión cronometrado a 20 minutos en
  output/D5_guión.md, con preguntas anticipadas del tribunal. Motivo: requisitos de la PEC4
  (presentación de uñas 20 transparencias y exposición oral de máximo 20 minutos).
- **Anexo 7.4 de la memoria D3:** matriz de trazabilidad que mapea cada resultado de
  aprendizaje del TFG (conocimientos K, habilidades S y competencias C) a la sección de la
  memoria o al entregable donde se evidencia, con una columna de cobertura (sólida, parcial,
  fuera de alcance). S8 (interfaz de usuario) y S10 (administración de redes y sistemas) se
  marcan como fuera del alcance del TFG por no aplicar a este tipo de proyecto. Motivo: la
  PEC4 evalua los resultados de aprendizaje y la matriz hace explícita su cobertura.

**Pendiente manual:** actualizar campos e índices en Word (F9) y exportar D3 y D5 a PDF.

### Generador del paquete de transparencia D4 en Word

**Fecha:** 2026-06-02. **Alcance:** generación del entregable D4 como documento Word.

**Decisión:** se crea docs/scripts/build_d4.js (npm run build:d4), que genera
output/D4_paquete_transparencia.docx con el estilo de la memoria D3 (Arial, paleta
corporativa, cabecera UOC, pie "Página X de Y", tablas con filas alternadas, sin guiones
largos). Reune las tres partes del paquete: checklist TRIPOD+AI con referencia cruzada a D3,
Model Card final y análisis de riesgos. La fuente de contenido es docs/D4_paquete_transparencia.md
y docs/model_card.md; en caso de discrepancia prevalece docs/model_card.md.

### Verificación de referencias y corrección del año de la AEPD

**Fecha:** 2026-06-02. **Alcance:** revisión de las 22 referencias de la bibliografía de D3
(idénticas en D4) para comprobar que son correctas y localizables (DOI, EUR-Lex, BOE, JMLR,
JOSS, arXiv, PubMed, etc.).

**Resultado:** 21 de 22 correctas y revisables. Se detecta un único error de fecha: la guía
de la AEPD "Orientaciones y garantías en los procedimientos de anonimizacion de datos
personales" figuraba con año 2019; la guía con ese título es de 2016 (versión 1.0). Se corrige
la referencia [16] en docs/scripts/build_d3.js de 2019 a 2016 y se regenera la memoria.

**Notas:** las referencias [11] Oken (1982, ECOG) y [22] Platt (1999, capítulo de Advances in
Large Margin Classifiers, MIT Press) no tienen DOI; su trazabilidad se asegura por PMID y por
la ficha bibliográfica. El enlace estable verificado para Platt es el registro de Semantic
Scholar (no la página de BibSonomy). La bibliografía de los entregables es texto plano, sin
URLs incrustadas, por lo que los enlaces se mantienen como referencia de revisión externa.

### Documentación del código del pipeline y los tests

**Fecha:** 2026-06-02. **Alcance:** añadir comentarios explicativos a los 14 módulos de src/
y los 3 ficheros de tests/.

**Decisión:** se documenta cada función con un bloque de comentarios '#' encima de su definición
y comentarios en línea en los pasos metodológicos clave. La documentación prioriza la perspectiva
de ciencia de datos (control anti-fugas, validación cruzada estratificada, bootstrap OOF,
criterios a priori, utilidad y privacidad de los sintéticos) con notas oncologicas breves donde
aportan (OS/PFS, censura, ECOG, comorbilidad MEDHX_N, brazo NESP). No se modifican docstrings de
cabecera ni código. Estilo del proyecto: sin tildes, sin enie y sin guiones largos.

**Verificación:** el flujo de tokens es idéntico al previo en los 20 ficheros (solo se añaden
comentarios) y los 34 smoke tests siguen pasando.

### Revisión de marcas de IA y referencias a Claude en el código

**Fecha:** 2026-06-02. **Alcance:** auditar el repositorio para que el código y los entregables
no contengan marcas de agua de IA ni referencias al asistente.

**Resultado:** sin caracteres invisibles sospechosos (ZWSP, BOM intercalado, etc.) en los 33
ficheros de texto. Sin referencias a Claude en los entregables D3 y D5. Se corrigen las referencias
encontradas en código y entregables: docstring de src/data/etl_nesp_nct00119613.py, comentario de
src/preprocessing/build_preprocessor.py y la línea de fuentes del paquete D4 (build_d4.js y
docs/D4_paquete_transparencia.md), con regeneración del D4 (0 referencias tras el cambio). Los
ficheros propios del entorno de trabajo (CLAUDE.md, .claude/settings.json y la sección del README)
se tratan aparte por ser configuración de desarrollo, no código del pipeline.

### Verificación cruzada del pipeline contra el protocolo y el diccionario de variables

**Fecha:** 2026-06-02. **Alcance:** contrastar los supuestos del ETL y de los entregables con
las dos fuentes primarias del estudio: el protocolo (Amendment 2, 16 julio 2004) y el diccionario
de variables (Data Definition Table v2).

**Hallazgos confirmados como correctos (sin cambio de código):**
- Endpoints. La supervivencia es endpoint co-primario del ensayo (junto al cambio de hemoglobina).
  Se verifico de forma agregada que DTH, DTHDY, PFSCD y PFSDY son idénticos en los 479 sujetos entre
  los datasets de análisis a_eendpt (período de quimioterapia), a_eendfu (período completo hasta la
  muerte 496) y a_eendes (período de tratamiento). El horizonte observado (DTHDY máximo 1208 días,
  mediana de OS 261 días, coherente con la mediana de ~9 meses del protocolo) confirma que son
  variables de seguimiento completo hasta el corte del estudio. La elección de a_eendpt en el ETL es
  por tanto correcta y equivalente.
- Anti-leakage. Las 7 covariables de la Estrategia 1 son todas basales o pre-aleatorizacion segun el
  DDT. Las tablas excluidas (c_lesión, c_radio, c_trans, c_vitals) son longitudinales o post-basales.
- Brazo. El ensayo es de dos brazos (darbepoetina alfa frente a placebo); el nivel EPO del formato
  del DDT es residuo del codebook genérico y no aplica a este estudio.

**Cambios documentales derivados:** se fija la población exacta del ensayo (cáncer de pulmón
microcítico en estadio extenso, no tratado previamente, con platino y etopósido) en D3, D4 y Model
Card; se aclara el matiz del tamaño muestral (600 planificado frente a 479 disponibles); y se
reformula la justificación de las exclusiones de TUMORCD, EXTENTCD y CHDCLASS como invariantes por
los criterios de inclusión del protocolo (RACECD permanece como varianza cero observada).

### Pre-registro del protocolo de la Estrategia 2 (análisis ampliado con validación cruzada anidada)

**Fecha:** 2026-06-02. **Naturaleza:** este protocolo se pre-registra por escrito ANTES de ejecutar
ningún modelado, conforme a la buena práctica de fijar las decisiones de selección de características,
espacio de búsqueda y criterio de comparación antes de observar resultados. La Estrategia 2 es un
análisis EXPLORATORIO y ADICIONAL: no sustituye al pipeline primario (Estrategia 1), que permanece
intacto con sus artefactos, sus hashes y su KPI-1. La Estrategia 2 usa su PROPIO dataset derivado
(output/dataset_strategy2.parquet, más csv, diccionario y manifiesto con su SHA-256 de referencia),
en paralelo y sin tocar nada del primario.

**Objetivo:** evaluar si una selección de características embebida y un ajuste bayesiano de
hiperparámetros, ambos confinados a un bucle interno de validación cruzada anidada, mejoran el
rendimiento pronóstico sobre el baseline de 7 variables de la Estrategia 1, sin sesgo de selección.

#### Pool de variables candidatas (10), todas basales o pre-aleatorización, sin fuga

Fuentes verificadas en el diccionario de variables (DDT v2) y en el protocolo (Amendment 2,
2004-07-16). Todas las candidatas están resumidas a nivel de sujeto, antes del tratamiento, en
c_keyvar, c_bchar y c_diag. NO se usan los ficheros de laboratorio longitudinales (a_lab, c_chem,
c_hemat, c_iron) por ser post-basales y suponer riesgo de fuga; el LDH y el EPO basales ya están
resumidos como variables de cribado en c_keyvar.

- Continuas: AGE, BMI (derivada), CADIAGM, B_HGB, B_SEREPO (con log1p), MEDHX_N.
- Categóricas o binarias: SEXCD, B_ECOGN, B_LDHN, PRTFN.

Variables nuevas frente a los 7 de la Estrategia 1 y su justificación pronóstica:
- B_SEREPO (EPO sérica basal, mU/mL): relacionada con la anemia y la respuesta eritropoyética.
  Muy asimétrica (mediana 23.9, máximo 1242) y con 9.2% de faltantes, por lo que se transforma con
  log1p y se imputa por mediana dentro de fold (9.2% <= 20%).
- B_LDHN (LDH basal normal frente a anormal): factor de estratificación de la aleatorización segun
  el protocolo y marcador pronóstico reconocido en cáncer de pulmón microcítico. Binaria limpia
  (valores 1 y 2), sin faltantes.
- PRTFN (transfusión de hematíes antes de la primera dosis): marcador de carga de enfermedad basal.

**Tratamiento de PRTFN (ajuste pre-registro).** El DDT decodifica PRTFN con el formato genérico
compartido YESNOF (0=No, 1=Sí, 7=No aplicable, 8=Desconocido, 9=No realizado), que es texto
repetitivo del formato, no semántica propia de la variable. La comprobación agregada (solo recuentos,
sin filas) muestra que PRTFN solo toma 0 (473 sujetos) y 1 (6 sujetos), sin ningún 7/8/9 y sin
faltantes. Por tanto no procede mapear "No realizado" a "no" ni a faltante: PRTFN es un binario
sustantivo 0/1 ya limpio. Se documenta de forma explícita que su prevalencia de positivos es muy
baja (6 de 479, 1.3%), casi constante, por lo que es previsiblemente poco informativa y potencialmente
inestable entre folds. Se mantiene en el pool por interés clínico y se deja que la selección embebida
decida; cualquier inestabilidad se reportará con honestidad.

**Derivación del IMC (ajuste pre-registro).** Se sustituyen B_WEIGHT y B_HEIGHT por una única
covariable derivada BMI = B_WEIGHT / (B_HEIGHT/100)^2. Se opta por dejar SOLO el IMC (y no IMC más
peso) porque el IMC es el marcador nutricional pronóstico relevante en oncología (caquexia), mientras
que el peso aislado confunde el tamaño corporal con el estado nutricional; mantener ambos introduciría
colinealidad fuerte (el IMC ya contiene el peso) que gastaría presupuesto de penalización en el
elastic-net y desestabilizaría las importancias de RSF y XGBoost. El IMC derivado tiene 1 faltante
(0.2%) y rango plausible (15.6 a 47.0, mediana 24.6), imputado por mediana dentro de fold.

Exclusiones (documentadas): RACECD, TUMORCD, EXTENTCD y CHDCLASS (constantes por varianza cero o por
criterio de inclusión); los ficheros de laboratorio longitudinales y todas las variables post-basales,
de tratamiento (TX*/SAF*) o de fecha (B_*DY, STUDYDAY, WEEK, PHASE); las versiones categorizadas
redundantes de variables ya incluidas (AGE65YN, B_WGTN, B_HGBN, AGEN, B_ECOG2, BSEPON); los flags
administrativos o de elegibilidad (EVALPRIM, EVALQOL, EVALRND, EXHBCOYN, SITEID, PROTOCOL). La región
de aleatorización solo existe a través de SITEID y requeriría derivación; se deja fuera por su
carácter administrativo y su alta cardinalidad.

#### Diseño de validación cruzada anidada

- Bucle externo: k=5 estratificado por evento x TXG (cuatro clases), idéntico al esquema del primario.
  Produce la estimación de rendimiento sin sesgo mediante predicciones out-of-fold y bootstrap n=1000
  para los intervalos de confianza al 95%.
- Bucle interno: dentro de cada fold de entrenamiento externo, k=5 estratificado. TODA la selección de
  características y el ajuste de hiperparámetros ocurren aquí. La mejor configuración se reentrena sobre
  el fold de entrenamiento externo completo y se aplica al fold de test externo, que nunca interviene
  en la selección ni en el ajuste.
- Control anti-fuga: el preprocesador (imputación adaptativa, estandarización, one-hot) se ajusta solo
  sobre el train interno durante el ajuste y solo sobre el train externo en el reentrenamiento. El
  brazo TXG nunca es predictor, solo estratificación.

#### Modelos y selección embebida (en el bucle interno)

- Cox elastic-net (CoxnetSurvivalAnalysis): la penalización L1 realiza la selección (coeficientes a
  cero). Se ajustan l1_ratio y la fuerza de penalización.
- Random Survival Forest: poda por importancia de permutación; se ajustan n_estimators, max_depth,
  min_samples_leaf y max_features.
- XGBoost (objetivo survival:cox): poda por ganancia; ajuste con early stopping sobre la validación
  interna.

#### Optimización de hiperparámetros

Optuna con muestreador TPE (bayesiano) y pruning, semillas fijas (SEED = 42). Configuración de la
corrida final: 100 trials por modelo y por fold externo. Antes de la corrida larga se ejecutará una
pasada de validación corta y NO reportada (20 a 30 trials, solo OS) para confirmar que el pipeline
anidado funciona de extremo a extremo; sus números no se publican en ningún entregable.

#### Criterio a priori y comparación

Criterio idéntico al del primario: C-index (métrica principal) más IBS más estabilidad entre folds
(coeficiente de variación). La comparación es entre la Estrategia 2 anidada y el baseline de 7
variables de la Estrategia 1 corrido bajo el MISMO protocolo anidado (mismos folds externos, mismo
reentrenamiento, mismas predicciones out-of-fold). Queda explícito que el C-index del baseline bajo el
protocolo anidado NO será el 0.599 de la validación cruzada simple del pipeline primario: el valor
de referencia para juzgar la mejora es el del baseline reejecutado en el esquema anidado, no el del
primario. Se reportará con honestidad cualquier resultado, incluida la ausencia de mejora, coherente
con el hallazgo del primario (KPI-3 no cumplido).

#### Endpoints y artefactos

Endpoints: OS (primario) y PFS (secundario), ambos con el protocolo anidado completo. Artefactos
propios de la Estrategia 2: dataset_strategy2 (parquet y csv), diccionario y manifiesto con su SHA-256
de referencia. El dataset primario, sus hashes y la verificación KPI-1 permanecen intactos.

**Alternativas descartadas:** validación cruzada plana con selección sobre todo el conjunto (sesgo de
selección optimista); usar los laboratorios longitudinales como basales (riesgo de fuga); mantener
peso e IMC simultáneamente (colinealidad); incluir las categorizaciones IVRS redundantes.

### Operacionalización de la selección embebida de la Estrategia 2

**Fecha:** 2026-06-03. **Alcance:** detalle de implementación de la poda por importancia
pre-registrada, fijado antes de la corrida reportada (src/models/nested_cv_strategy2.py).

Se mantiene la letra del pre-registro: la selección de variables es embebida y vive en el bucle
interno. Operacionalización exacta, igual en el bucle interno (para el tuning) y en el
reentrenamiento externo (sobre el train externo), siempre sin ver el test externo:

- Cox elastic-net: selección por penalización L1 (CoxnetSurvivalAnalysis con un par alpha, l1_ratio
  por trial). Las variables retenidas son las de coeficiente no nulo; se registra su número por fold.
- RSF: se ajusta el bosque con todas las columnas, se calcula la importancia por permutación
  (sklearn permutation_importance, n_repeats=5, sobre el train del fold) y se reajusta el bosque sobre
  las top_k variables de mayor importancia. top_k se optimiza en el bucle interno en el rango [4, 10].
- XGBoost (survival:cox): se ordena por importancia de ganancia (importance_type='gain'), se poda a
  las top_k (rango [4, 10], optimizado en el interno) y se reajusta. El número de árboles se fija por
  early stopping (25 rondas) en un hold-out del 20% del train, sobre las columnas seleccionadas.

El diseño matricial tiene 10 columnas (6 numéricas mas 4 binarias one-hot drop-first), por lo que
la poda opera sobre esas 10 columnas. Se registran por fold externo las variables seleccionadas, el
número de variables y, en XGBoost, el número de árboles, para trazabilidad e interpretación.

**Validación previa:** antes de la corrida reportada de 100 trials se ejecuta una pasada corta y no
reportada (25 trials, solo OS) para confirmar el funcionamiento de extremo a extremo del pipeline
anidado. Sus números no se publican en ningún entregable.
