# Decision log

Registro de decisiones metodologicas y de diseno. Anade una entrada nueva cada vez que tomes o cambies una decision relevante. Formato: fecha, decision, motivo, alternativa descartada.

## Decisiones registradas

### Fuente de datos y marco interpretativo
La cohorte procede del estudio NESP-Oncology-20010145 (NCT00119613) en Project Data Sphere, no de cBioPortal como contemplaba la propuesta inicial. Motivo: variables de outcome mas completas y trazables, homogeneidad del regimen quimioterapeutico y trazabilidad temporal del seguimiento. El ensayo es de fase III (Darbepoetin Alfa frente a placebo); el TFG lo reformula como pronostico bajo quimioterapia y no estudia el efecto del agente eritropoyetico.

### Pivote P1: variable objetivo a supervivencia
Tras la auditoria de la cohorte, el exceso de valores faltantes en las etiquetas de respuesta directa (RECIST/ORR) comprometia una clasificacion binaria valida. Se reformulo a supervivencia con censura (OS y PFS). Diseno adaptado: Cox baseline, Random Survival Forest y XGBoost/LightGBM con perdida de supervivencia, con C-index e IBS como metricas principales.

### Pivote P2: validacion adaptada al tamano muestral
n efectivo = 479. Se aplico validacion cruzada estratificada k=5 con regularizacion robusta y bootstrap n=1000, priorizando estabilidad sobre complejidad.

### Ajuste 3: brazo NESP/placebo como estratificacion
La asignacion TXG se usa como variable de estratificacion y se reporta rendimiento por estrato, no como predictor. Motivo: evitar que el modelo aprenda el efecto del farmaco del estudio en lugar de la heterogeneidad clinica, y permitir analisis de transferibilidad entre estratos.

### Estrategia de covariables (Estrategia 1)
Nucleo de 7 predictores basales con senal: AGE, SEXCD, B_ECOGN, B_WEIGHT, CADIAGM, B_HGB y MEDHX_N (comorbilidad derivada). Se excluyen por varianza cero en la cohorte: RACECD, TUMORCD, EXTENTCD, CHDCLASS. Alternativas descartadas: enriquecer con basales adicionales (EPO, LDH, transfusion) y mantener las 11 covariables literales con columnas constantes.

### Derivacion de MEDHX_N
Comorbilidad operacionalizada como numero de sistemas corporales con antecedente anormal (MEDHXYN = 1) por sujeto, rango 0 a 6. El valor 7 de MEDHXYN no cuenta como anomalia.

### Tamano muestral real
n = 479 (confirmado por el ETL), no 600. El 600 de informes previos era ilustrativo. La memoria final debe usar 479.

### Criterio de seleccion de modelo (a priori)
Fijado antes de observar resultados: metrica principal (C-index) mas IBS mas coeficiente de variacion entre folds. Se aplicara a los valores reales del pipeline para confirmar el modelo final.

### Postcalibracion
Se evaluan Platt e isotonica. Si las mejoras son marginales y no significativas frente a los IC bootstrap, el modelo final se reporta sin postcalibracion por parsimonia.

### Valores ilustrativos frente a reales
Los numeros de PEC3 son ilustrativos. La memoria final reportara los valores reales del pipeline.

### Seleccion del modelo final: Cox proporcional (parsimonia)

**Fecha:** 2026-06-01. **Decision:** el modelo final es el Cox proporcional de Harrell,
retenido por parsimonia. Ningun candidato mejora de forma estadisticamente significativa
el baseline segun el criterio de seleccion fijado a priori (C-index + IBS + CV%).

**Resultados reales del pipeline (CV k=5, bootstrap n=1000):**

| Modelo   | OS C-index (CV)     | OS IBS (CV)         | PFS C-index (CV)    |
|----------|---------------------|---------------------|---------------------|
| Cox PH   | 0.600 +/- 0.042     | 0.182 +/- 0.013     | 0.552 +/- 0.028     |
| RSF      | 0.593 +/- 0.027     | 0.181 +/- 0.011     | 0.544 +/- 0.024     |
| XGBoost  | 0.549 +/- 0.030     | 0.187 +/- 0.014     | 0.528 +/- 0.030     |

**Justificacion detallada:**

- **RSF** es el mejor candidato en terminos de discriminacion equivalente a Cox (diferencia
  de C-index OS = 0.007, inferior al nivel de ruido del CV) y mayor estabilidad entre folds
  (CV% = 4.5% frente a 7.0% de Cox). Sin embargo, el intervalo bootstrap del C-index se solapa
  completamente con el de Cox: RSF IC95% [0.562, 0.621] frente a Cox IC95% [0.567, 0.629]. La
  diferencia no es estadisticamente significativa. El IBS es practicamente identico (0.181 vs
  0.182). Aplicando el principio de parsimonia, no hay justificacion para sustituir Cox por RSF.
- **XGBoost** queda por detras en ambos endpoints. Con n=479 y 7 predictores, el early
  stopping activa tras 1-30 arboles en la mayoria de folds, indicando que la senal disponible
  no sustenta la capacidad de un modelo gradient-boosted. Los intervalos bootstrap no se solapan
  favorablemente con Cox.

**KPI-3 (mejora sobre baseline): NO CUMPLIDO.** Este es un hallazgo honesto y esperado.
Con n=479, 7 predictores basales y alta tasa de eventos (83% OS), la superficie de decision
es practicamente lineal. El supuesto de proporcionalidad de Cox se ajusta bien a estos datos
y los modelos no lineales no tienen ventaja en esta cohorte. Se documenta como limitacion
explicitamente en la memoria final (D3) y en la Model Card.

**Alternativa descartada:** usar RSF como modelo final pese a la equivalencia estadistica.
Razon: el coste interpretativo (no hay coeficientes directamente interpretables) no se justifica
ante la ausencia de ganancia significativa en discriminacion ni en calibracion.

### Evaluacion del modelo final: metricas reales OS (primario) y PFS (secundario)

**Fecha:** 2026-06-01. **Alcance:** curvas de calibracion con bandas bootstrap, Brier Score
a lo largo del tiempo, AUC dinamica acumulada con bandas bootstrap. Todas las metricas se
calculan sobre predicciones OOF (out-of-fold) del CV k=5 para evitar sobreajuste.

Resultados sinteticos (valores completos en output/eval_*.csv):

- OS Boot C-index: 0.599 IC95% [0.567, 0.629]
- OS Boot IBS:     0.182 IC95% [0.172, 0.191]
- PFS Boot C-index: 0.555 IC95% [0.525, 0.586]
- PFS Boot IBS:     0.182 IC95% [0.172, 0.192]

### Componente de datos sinteticos (Sprint 6)

**Fecha:** 2026-06-01. **Alcance:** generacion con CTGAN (SDV >= 1.0), evaluacion de
utilidad TSTR y evaluacion de riesgo de reidentificacion en tres dimensiones.

**Decisiones de diseno:**

- Generador: CTGANSynthesizer de SDV con 300 epocas y n_sintetico = n_real = 479.
  Columnas binarias (DTH, PFSCD, TXG, EVALPRIM, EVALQOL) y categoricas (SEXCD, B_ECOGN)
  declaradas explicitamente como "categorical" en los metadatos SDV.
- TSTR: preprocesador ajustado solo sobre datos sinteticos (escenario TSTR puro);
  evaluacion sobre cada fold de test real del CV k=5; comparacion directa con TRTR.
- Membership inference: N=5 shadow models, cada uno ajustado sobre el 70% del real,
  con 100 epocas. Score = negativo de la distancia Euclidea minima en el espacio
  preprocesado. AUC y TPR a FPR=0.1 sobre los pares pooled de todos los shadows.
- K-anonimidad: cuasi-identificadores AGE (bins de 5 anos), SEXCD y B_ECOGN.
  Para cada registro sintetico, se cuenta el numero de registros reales con la misma
  combinacion de QI. Se reportan las fracciones k=1, k<=2, k<=5.
- DCR: distancia Euclidea minima de cada sintetico al real mas cercano, en el espacio
  preprocesado (ajuste sobre reales para espacio de referencia comun). RRDR (LOO)
  como referencia del ruido natural del dataset.

**Criterios de aceptacion a priori (privacidad):**
  - Membership inference: AUC <= 0.60, TPR@FPR=0.1 <= 0.20
  - K-anonimidad: k=1 < 5%, k<=2 < 10%, k<=5 < 20%
  - DCR: DCR_p5 / RRDR_mediana >= 0.50

**Advertencia invariante:** los datos sinteticos son exclusivamente para prototipado
metodologico. No refuerzan las conclusiones del modelo principal de supervivencia.

### Evaluacion final de datos sinteticos: resultados reales

**Fecha:** 2026-06-01. **Alcance:** resultados numericos del pipeline de evaluacion de
riesgo de reidentificacion y utilidad (output/synthetic_metrics.json).

**Resultados por dimension:**

| Dimension | Valor | Umbral | Resultado |
|-----------|-------|--------|-----------|
| Membership inference AUC | 0.534 | <= 0.60 | ACEPTADO |
| TPR @ FPR=0.1 | 0.139 | <= 0.20 | ACEPTADO |
| K-anonimidad k=1 (bins 5a) | 7.32% | < 5.00% | NO ACEPTADO |
| K-anonimidad k<=2 (bins 5a) | 10.04% | < 10.00% | NO ACEPTADO |
| K-anonimidad k<=5 (bins 5a) | 20.71% | < 20.00% | NO ACEPTADO |
| DCR_p5 / RRDR_mediana | 0.622 | >= 0.50 | ACEPTADO |

**Evaluacion global: NO ACEPTADO** por k-anonimidad con la configuracion preregistrada
(bins de edad de 5 anos). El membership inference y la DCR pasan sin problemas.

**Analisis de sensibilidad:** con bins de edad de 10 anos, k1=5.44%, k2=7.32%, k5=11.51%.
K2 y k5 pasan el umbral; k1 sigue por encima (5.44% > 5.00%). La k-anonimidad es
sensible a la granularidad del binning de la variable de edad.

**Utilidad TSTR:** C-index medio TSTR = 0.437 vs TRTR = 0.600. Ratio = 72.8%.

**Decision:** los datos sinteticos se documentan con el resultado de NO ACEPTADO y se
acompanan del analisis de sensibilidad. Su uso queda restringido al prototipado
metodologico, con advertencia explicita en la memoria y en la Model Card.

### Proporcionalidad de Cox: test de Schoenfeld

**Fecha:** 2026-06-01. **Alcance:** verificacion del supuesto de proporcionalidad de
riesgos en el modelo final Cox PH (output/cox_schoenfeld_test.csv).

**Resultados:**

| Variable | Endpoint | p Schoenfeld | Supuesto OK |
|----------|----------|-------------|------------|
| AGE | OS | 0.030 | No |
| B_WEIGHT | OS | 0.026 | No |
| B_WEIGHT | PFS | 0.011 | No |
| Resto de variables | OS y PFS | > 0.10 | Si |

**Interpretacion:** AGE y B_WEIGHT muestran evidencia de efectos no proporcionales en OS;
B_WEIGHT tambien en PFS. El resto de variables (SEXCD, B_ECOGN, B_HGB, CADIAGM, MEDHX_N)
cumplen el supuesto. Las variables con mayor senal pronostica (SEXCD, B_ECOGN) no violan
el supuesto.

**Decision:** se reporta la violacion parcial como limitacion explicita en la Model Card
y en la memoria final (D3). No se reestima el modelo con extensiones de tiempo variable,
dado el caracter de prototipo academico y el tamano muestral moderado. Alternativas
descartadas: modelo de Cox estratificado por tiempo o con interaccion tiempo-covariable.

### Hazard ratios significativos del modelo final

**Fecha:** 2026-06-01. **Alcance:** tabla de coeficientes e interpretacion de las
asociaciones estadisticamente significativas (output/cox_hazard_ratios.csv).

**OS (predictores significativos):**
- MEDHX_N: HR = 1.086 IC95% [1.003, 1.177], p = 0.042. Cada sistema corporal adicional
  con antecedente anomalo se asocia con un 8.6% mas de riesgo de muerte.
- SEXCD = 1 (femenino vs masculino): HR = 0.641 IC95% [0.514, 0.799], p < 0.001.
  El sexo femenino se asocia con un 36% menos de riesgo de muerte.
- B_ECOGN = 2 vs 1: HR = 1.693 IC95% [1.326, 2.160], p < 0.001. El estado funcional
  reducido se asocia con un 69% mas de riesgo de muerte.

**PFS (predictores significativos):**
- SEXCD = 1: HR = 0.779 IC95% [0.634, 0.958], p = 0.018.
- B_ECOGN = 2 vs 1: HR = 1.432 IC95% [1.132, 1.811], p = 0.003.

**Nota:** las asociaciones son descriptivas. El ensayo no fue disenado para identificar
estos efectos y pueden estar confundidos por factores no medidos. No se interpretan como
relaciones causales.

### Analisis de subgrupos: resultados reales

**Fecha:** 2026-06-01. **Alcance:** rendimiento del modelo final por estrato
(output/robustness_subgroups_OS.csv y robustness_subgroups_PFS.csv). Estadisticas
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

**Conclusion:** el rendimiento es consistente entre estratos. La caida en ECOG 2 es
esperable por la menor heterogeneidad pronostica en ese subgrupo. La similitud entre
brazos NESP y placebo confirma la transferibilidad del modelo entre estratos de
tratamiento, coherente con su diseno basado en predictores basales unicamente.

### Calibracion del modelo final: KPI-4

**Fecha:** 2026-06-01. **Alcance:** curvas de calibracion para OS y PFS evaluadas sobre
predicciones OOF del CV k=5, en tres horizontes temporales por endpoint. Estimacion
observada mediante Kaplan-Meier (km_obs) con bandas bootstrap (output/eval_calibration_OS.csv,
output/eval_calibration_PFS.csv, output/fig_calibration_OS.png).

**KPI-4: CUMPLIDO.** La calibracion es aceptable en el rango central del horizonte temporal
y ruidosa en los extremos, lo cual es esperable con n=479 sujetos y la alta tasa de eventos.

**Hallazgos por horizonte temporal (OS):**

- **t = 164 dias:** bien calibrado. Los deciles siguen la diagonal con dispersion moderada
  y sin sesgo sistematico. Las predicciones en el rango central (supervivencia estimada
  0.70-0.85) son las mas fiables.

- **t = 259 dias:** bien calibrado. La mayoria de deciles se situan proximos a la diagonal
  dentro de los IC bootstrap. Ligera dispersion en los extremos coherente con el tamano
  muestral.

- **t = 355 dias:** los deciles de alto riesgo (grupos con supervivencia predicha baja,
  < 0.35) quedan por encima de la diagonal: km_obs > mean_pred. El modelo subestima la
  supervivencia en ese extremo temporal para los pacientes de mayor riesgo. Los deciles
  de riesgo bajo (supervivencia predicha > 0.45) son mas estables pero con mayor
  incertidumbre por el numero reducido de sujetos en riesgo a esa profundidad de seguimiento.

**Interpretacion general:** el patron de subestimacion a t=355 en los deciles de alto riesgo
es coherente con un modelo de Cox sin covariables tiempo-dependientes y con la violacion
parcial del supuesto de proporcionalidad en AGE y B_WEIGHT (registrada en la entrada
"Proporcionalidad de Cox"). No invalida el modelo para su uso como prototipo de investigacion;
si limita la precision de las predicciones absolutas de supervivencia en el largo plazo para
el subgrupo de mayor riesgo. Se documenta como limitacion en la memoria final (D3) y en la
Model Card.

**Postcalibracion:** Platt e isotonica evaluadas. Mejoras marginales sin significacion
estadistica frente a los IC bootstrap. Decision final: modelo reportado sin postcalibracion
por parsimonia.

### Entregable D5 y matriz de trazabilidad de resultados de aprendizaje (PEC4)

**Fecha:** 2026-06-02. **Alcance:** generacion de la presentacion de defensa (D5) y
ampliacion de la memoria final (D3) con la matriz de trazabilidad de resultados de aprendizaje.

**Decisiones:**

- **D5 presentacion (output/D5_presentacion.pptx):** 15 diapositivas con la paleta del
  proyecto (azul 1F4E79 y D5E8F0, verde 1F7A3A, ambar B7791F), fuente Arial y una idea por
  diapositiva, apoyada en las figuras de output/. Generador reproducible en
  docs/scripts/build_d5.js (dependencia pptxgenjs). Guion cronometrado a 20 minutos en
  output/D5_guion.md, con preguntas anticipadas del tribunal. Motivo: requisitos de la PEC4
  (presentacion de unas 20 transparencias y exposicion oral de maximo 20 minutos).
- **Anexo 7.4 de la memoria D3:** matriz de trazabilidad que mapea cada resultado de
  aprendizaje del TFG (conocimientos K, habilidades S y competencias C) a la seccion de la
  memoria o al entregable donde se evidencia, con una columna de cobertura (solida, parcial,
  fuera de alcance). S8 (interfaz de usuario) y S10 (administracion de redes y sistemas) se
  marcan como fuera del alcance del TFG por no aplicar a este tipo de proyecto. Motivo: la
  PEC4 evalua los resultados de aprendizaje y la matriz hace explicita su cobertura.

**Pendiente manual:** actualizar campos e indices en Word (F9) y exportar D3 y D5 a PDF.

### Generador del paquete de transparencia D4 en Word

**Fecha:** 2026-06-02. **Alcance:** generacion del entregable D4 como documento Word.

**Decision:** se crea docs/scripts/build_d4.js (npm run build:d4), que genera
output/D4_paquete_transparencia.docx con el estilo de la memoria D3 (Arial, paleta
corporativa, cabecera UOC, pie "Pagina X de Y", tablas con filas alternadas, sin guiones
largos). Reune las tres partes del paquete: checklist TRIPOD+AI con referencia cruzada a D3,
Model Card final y analisis de riesgos. La fuente de contenido es docs/D4_paquete_transparencia.md
y docs/model_card.md; en caso de discrepancia prevalece docs/model_card.md.

### Verificacion de referencias y correccion del ano de la AEPD

**Fecha:** 2026-06-02. **Alcance:** revision de las 22 referencias de la bibliografia de D3
(identicas en D4) para comprobar que son correctas y localizables (DOI, EUR-Lex, BOE, JMLR,
JOSS, arXiv, PubMed, etc.).

**Resultado:** 21 de 22 correctas y revisables. Se detecta un unico error de fecha: la guia
de la AEPD "Orientaciones y garantias en los procedimientos de anonimizacion de datos
personales" figuraba con ano 2019; la guia con ese titulo es de 2016 (version 1.0). Se corrige
la referencia [16] en docs/scripts/build_d3.js de 2019 a 2016 y se regenera la memoria.

**Notas:** las referencias [11] Oken (1982, ECOG) y [22] Platt (1999, capitulo de Advances in
Large Margin Classifiers, MIT Press) no tienen DOI; su trazabilidad se asegura por PMID y por
la ficha bibliografica. El enlace estable verificado para Platt es el registro de Semantic
Scholar (no la pagina de BibSonomy). La bibliografia de los entregables es texto plano, sin
URLs incrustadas, por lo que los enlaces se mantienen como referencia de revision externa.
