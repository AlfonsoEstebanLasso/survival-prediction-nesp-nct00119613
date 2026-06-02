# D4. Paquete de transparencia y gobernanza

Trabajo Final de Grado. Prediccion de respuesta a farmacos quimioterapeuticos a partir de datos clinicos anonimizados. Estudiante: Alfonso Esteban Lasso. Fecha de cierre: 2026-06-01.

Este documento es autocontenido y reune tres partes: (1) el checklist de reporte transparente TRIPOD+AI con referencia cruzada a la memoria D3; (2) la Model Card final del modelo; y (3) el analisis de riesgos del proyecto, del modelo y de la privacidad. Todos los valores proceden de los artefactos del pipeline (carpeta output) y de la documentacion viva del proyecto (decision_log y model_card). No se introduce ningun valor que no figure en esas fuentes.

Nota sobre derechos de autor: el checklist TRIPOD+AI (Collins y colaboradores, 2024, BMJ 385:e078378) es material protegido por copyright. En la Parte 1 no se reproduce el texto literal de los items ni las tablas oficiales. Cada item se parafrasea de forma breve y original, con la unica finalidad de documentar el cumplimiento del estudio.

---

## PARTE 1. Checklist TRIPOD+AI con referencia cruzada a D3

### 1.1 Naturaleza del estudio y alcance de la validacion

Se declara de entrada que este trabajo es un estudio de DESARROLLO de un modelo pronostico, con validacion interna mediante validacion cruzada estratificada k=5 y bootstrap de n=1000. No se realiza validacion externa en una cohorte independiente. En consecuencia, todos los items relativos a validacion externa se marcan como No aplica o como linea futura, de forma explicita y honesta. Esta limitacion se recoge tambien en la Parte 2 (Model Card) y en la Parte 3 (analisis de riesgos).

Leyenda de estado: Cumplido (el item se aborda en D3), Parcial (se aborda de forma incompleta o con matices), No aplica (no procede por el alcance del estudio).

El indice de la memoria D3 al que se hace referencia es: 1.1 contexto; 1.2 objetivos; 1.3 impacto CCEG; 1.4 enfoque; 1.5 planificacion; 1.6 productos; 1.7 otros capitulos; 1.8 declaracion de IA; 2.1 datos y cohorte; 2.2 diseno y control de fugas; 2.3 modelos; 2.4 metricas; 2.5 privacidad y sinteticos; 2.6 reproducibilidad; 2.7 valoracion economica; 3.1 comparativa y seleccion; 3.2 modelo final OS y PFS; 3.3 calibracion; 3.4 interpretabilidad; 3.5 robustez y subgrupos; 3.6 datos sinteticos; 4.1 conclusiones; 4.2 objetivos; 4.3 planificacion; 4.4 impactos; 4.5 lineas futuras.

### 1.2 Titulo y resumen

| Item (parafraseado) | Estado | Seccion D3 |
|---|---|---|
| El titulo identifica que el trabajo desarrolla un modelo de prediccion de supervivencia y senala la poblacion oncologica. | Cumplido | Portada y 1.1 |
| El resumen recoge objetivo, datos, metodos, resultados principales y conclusiones, e indica que se trata de un prototipo no clinico. | Cumplido | Ficha (resumen y abstract) |

### 1.3 Introduccion

| Item (parafraseado) | Estado | Seccion D3 |
|---|---|---|
| Se explica el contexto clinico, la variabilidad de respuesta a la quimioterapia y por que un modelo pronostico es pertinente. | Cumplido | 1.1 |
| Se justifica el enfoque metodologico de prototipo reproducible frente a uno orientado a la complejidad. | Cumplido | 1.1, 1.4 |
| Se enuncian los objetivos general y especificos (O1 a O6) con sus criterios de exito (KPI). | Cumplido | 1.2 |

### 1.4 Metodos

| Item (parafraseado) | Estado | Seccion D3 |
|---|---|---|
| Se describe la fuente de datos (estudio NESP-Oncology-20010145, NCT00119613, Project Data Sphere) y el cambio documentado de fuente respecto de la propuesta inicial. | Cumplido | 2.1 |
| Se indica el diseno del estudio (desarrollo con validacion interna) y la ventana temporal basal del seguimiento. | Cumplido | 2.1, 2.2 |
| Se detallan los participantes y los criterios de la cohorte (479 sujetos, una fila por sujeto). | Cumplido | 2.1 |
| Se definen los desenlaces OS (a partir de DTH y DTHDY) y PFS (a partir de PFSCD y PFSDY), con censura y codificacion 1 evento, 0 censura. | Cumplido | 2.1, 2.4 |
| Se especifican los siete predictores basales (AGE, SEXCD, B_ECOGN, B_WEIGHT, CADIAGM, B_HGB, MEDHX_N) y la derivacion de MEDHX_N. | Cumplido | 2.1 |
| Se documenta el control de variables posteriores al desenlace: exclusion de ficheros longitudinales y post-basales para evitar fuga. | Cumplido | 2.2 |
| Se justifica el tamano muestral (n=479) y la validacion adaptada (k=5 estratificada con bootstrap de n=1000). | Cumplido | 2.1, 2.2 |
| Se describe el tratamiento de datos faltantes con imputacion ajustada dentro de cada particion de entrenamiento. | Cumplido | 2.1, 2.2 |
| Se detallan los metodos de analisis: Cox, RSF y XGBoost, validacion cruzada estratificada, bootstrap, criterio de seleccion a priori y control de fugas. | Cumplido | 2.2, 2.3 |
| Se describe la salida del modelo (funcion de riesgo y supervivencia) y la interpretacion mediante hazard ratios. | Cumplido | 2.3, 3.4 |
| Se especifican las metricas de evaluacion (C-index, IBS, Brier dependiente del tiempo, AUC dependiente del tiempo y calibracion con bandas). | Cumplido | 2.4 |
| Se aborda la validacion externa en una cohorte independiente. | No aplica (linea futura) | 4.5 |

### 1.5 Componente especifico de inteligencia artificial y aprendizaje automatico

| Item (parafraseado) | Estado | Seccion D3 |
|---|---|---|
| Se identifica el tipo de modelos empleados (un modelo estadistico de riesgos proporcionales y dos modelos de aprendizaje automatico de supervivencia). | Cumplido | 2.3 |
| Se indican el software y las versiones de las herramientas utilizadas. | Cumplido | 2.6 |
| Se documentan las semillas fijas y las condiciones de reproducibilidad. | Cumplido | 2.6 |
| Se evalua el rendimiento por subgrupos y la equidad del desempeno, incluido el sexo como perspectiva de genero. | Cumplido | 3.5 |
| Se describe el procedimiento de ajuste de hiperparametros dentro del esquema de validacion. | Parcial | 2.2, 2.3 |
| Se valora el riesgo de sesgo y la robustez del modelo entre estratos. | Cumplido | 3.5 |

### 1.6 Ciencia abierta y disponibilidad

| Item (parafraseado) | Estado | Seccion D3 |
|---|---|---|
| Se indica la disponibilidad del codigo en el repositorio del pipeline (entregable D1). | Cumplido | 2.6, anexo 7.2 |
| Se aclara que los datos a nivel de sujeto no se comparten por privacidad por diseno y que solo se publican metadatos. | Cumplido | 2.5, 2.6 |
| Se incluye la declaracion sobre el uso de herramientas de inteligencia artificial generativa. | Cumplido | 1.8 |
| Se declara el protocolo o registro previo del estudio. | Parcial | 2.2 (criterios a priori) |

### 1.7 Resultados

| Item (parafraseado) | Estado | Seccion D3 |
|---|---|---|
| Se describe el flujo de participantes y el numero de eventos (OS: 397 eventos; PFS: 440 eventos sobre n=479). | Cumplido | 2.1, 3.2 |
| Se presenta la comparativa de modelos bajo el criterio fijado a priori. | Cumplido | 3.1 |
| Se identifica el modelo final (Cox proporcional por parsimonia) y su justificacion. | Cumplido | 3.1 |
| Se reporta el rendimiento (C-index, IBS, AUC dependiente del tiempo) con intervalos de confianza. | Cumplido | 3.2 |
| Se presenta la calibracion con bandas bootstrap en varios horizontes temporales. | Cumplido | 3.3 |
| Se aporta la interpretabilidad mediante hazard ratios y el test de proporcionalidad. | Cumplido | 3.4 |
| Se analiza la robustez por subgrupos. | Cumplido | 3.5 |
| Se documentan los datos sinteticos y su evaluacion de utilidad y riesgo. | Cumplido | 3.6 |

### 1.8 Discusion

| Item (parafraseado) | Estado | Seccion D3 |
|---|---|---|
| Se discuten las limitaciones: validez externa limitada por tratarse de una cohorte de ensayo. | Cumplido | 4.1, 4.2 |
| Se reconoce el tamano muestral moderado (n=479). | Cumplido | 4.2 |
| Se reporta de forma honesta que el KPI-3 (mejora sobre baseline) no se cumple. | Cumplido | 3.1, 4.2 |
| Se documenta la violacion parcial del supuesto de proporcionalidad en AGE y B_WEIGHT. | Cumplido | 3.4 |
| Se senala que el endpoint PFS es poco informativo con estos predictores. | Cumplido | 3.2 |
| Se aclara que la interpretacion de las asociaciones es descriptiva y no causal. | Cumplido | 3.4 |
| Se incluye la advertencia explicita de no uso clinico. | Cumplido | 1.1, Model Card |
| Se interpretan los resultados en el contexto de la evidencia disponible y su implicacion practica como prototipo. | Cumplido | 4.1, 4.4 |

### 1.9 Otra informacion

| Item (parafraseado) | Estado | Seccion D3 |
|---|---|---|
| Se declara la financiacion del trabajo: ninguna. | Cumplido | Otra informacion (este documento) |
| Se declaran los conflictos de interes: ninguno. | Cumplido | Otra informacion (este documento) |
| Se confirma la ausencia de mencion a centros externos de colaboracion. | Cumplido | Todo el documento |

Financiacion: el trabajo no ha recibido financiacion. Conflictos de interes: el autor declara no tener ningun conflicto de interes. No existe ninguna entidad externa de colaboracion asociada al trabajo.

---

## PARTE 2. Model Card final

Nota sobre la fuente canonica: la version viva y de referencia de la Model Card es el fichero docs/model_card.md, cerrado en el Sprint 8 con los valores reales del pipeline. El contenido que sigue reproduce esa fuente sin alterar ningun valor. En caso de discrepancia, prevalece docs/model_card.md.

### Uso previsto

Prototipo de investigacion y validacion metodologica para predecir supervivencia (OS y PFS) bajo quimioterapia a partir de variables clinicas basales. Publico: perfiles de ciencia de datos biomedica y equipos de I+D. No es un dispositivo clinico.

### Advertencia de no uso clinico

El modelo no esta validado para uso clinico ni para decisiones individuales de pacientes. Su finalidad es academica y metodologica.

### Poblacion y datos

- Cohorte: estudio NESP-Oncology-20010145 (NCT00119613), Project Data Sphere.
- n = 479 sujetos (una fila por sujeto). Eventos OS: 397 (83%); censurados: 82 (17%). Eventos PFS: 440 (92%); censurados: 39 (8%).
- Brazo de aleatorizacion NESP/placebo usado como estratificacion, no como predictor.
- Predictores (Estrategia 1): AGE, SEXCD, B_ECOGN, B_WEIGHT, CADIAGM, B_HGB, MEDHX_N.
- Endpoints: OS (DTH, DTHDY) y PFS (PFSCD, PFSDY).

### Modelo

- Baseline: Cox proporcional.
- Candidatos: Random Survival Forest y XGBoost/LightGBM con perdida de supervivencia.
- Seleccion por criterio a priori: C-index mas IBS mas coeficiente de variacion entre folds.
- Modelo final: Cox proporcional (parsimonia). Ningun candidato mejora significativamente el baseline segun el criterio fijado a priori. Los IC bootstrap se solapan completamente entre Cox y RSF.

### Metricas del modelo final (Cox proporcional)

Todas las metricas se calculan sobre predicciones OOF (out-of-fold) del CV k=5 para evitar sobreajuste.

#### OS (endpoint primario)

| Metrica | CV k=5 media +/- std (CV%) | Bootstrap n=1000 | IC95% bootstrap |
|---------|---------------------------|-----------------|-----------------|
| C-index | 0.600 +/- 0.042 (7.1%) | 0.599 | [0.567, 0.629] |
| IBS | 0.182 +/- 0.013 (7.2%) | 0.182 | [0.172, 0.191] |
| AUC dinamica media | -- | 0.645 | [0.601, 0.690] |

Detalle por fold (OS): fold 1 = 0.528, fold 2 = 0.614, fold 3 = 0.635, fold 4 = 0.623, fold 5 = 0.599.

#### PFS (endpoint secundario)

| Metrica | CV k=5 media +/- std (CV%) | Bootstrap n=1000 | IC95% bootstrap |
|---------|---------------------------|-----------------|-----------------|
| C-index | 0.552 +/- 0.028 (5.1%) | 0.555 | [0.525, 0.586] |
| IBS | 0.182 +/- 0.012 (6.4%) | 0.182 | [0.172, 0.192] |
| AUC dinamica media | -- | 0.584 | [0.536, 0.632] |

#### Comparacion de modelos (OS, criterio a priori)

| Modelo | C-index CV (CV%) | IBS CV | Boot C-index | IC95% |
|--------|-----------------|--------|-------------|-------|
| Cox PH | 0.600 (7.05%) | 0.182 | 0.599 | [0.567, 0.629] |
| RSF | 0.593 (4.54%) | 0.181 | 0.592 | [0.562, 0.621] |
| XGBoost | 0.549 (5.50%) | 0.187 | 0.552 | [0.523, 0.582] |

KPI-3 (mejora sobre baseline): NO CUMPLIDO. Los IC bootstrap de RSF y Cox solapan completamente (diferencia C-index = 0.007). Con n=479 y 7 predictores basales, la superficie de decision es practicamente lineal y los modelos no lineales no tienen ventaja en esta cohorte. Se documenta como limitacion explicita.

### Coeficientes y hazard ratios (Cox proporcional)

#### OS

| Variable | HR | IC95% | p |
|----------|-----|-------|---|
| Edad (por ano) | 1.006 | [0.993, 1.019] | 0.347 |
| Peso basal (por kg) | 0.994 | [0.987, 1.002] | 0.130 |
| Tiempo desde diag. (por mes) | 0.969 | [0.877, 1.070] | 0.536 |
| Hemoglobina basal (por g/dL) | 0.979 | [0.890, 1.077] | 0.666 |
| N. sistemas comorbilidad | 1.086 | [1.003, 1.177] | 0.042 (*) |
| Sexo = 1 vs 0 | 0.641 | [0.514, 0.799] | < 0.001 (***) |
| B_ECOGN = 2 vs 1 (referencia) | 1.693 | [1.326, 2.160] | < 0.001 (***) |

#### PFS

| Variable | HR | IC95% | p |
|----------|-----|-------|---|
| Edad (por ano) | 1.007 | [0.994, 1.019] | 0.292 |
| Peso basal (por kg) | 0.998 | [0.991, 1.005] | 0.527 |
| Tiempo desde diag. (por mes) | 0.941 | [0.853, 1.038] | 0.221 |
| Hemoglobina basal (por g/dL) | 0.970 | [0.886, 1.062] | 0.516 |
| N. sistemas comorbilidad | 1.034 | [0.956, 1.118] | 0.407 |
| Sexo = 1 vs 0 | 0.779 | [0.634, 0.958] | 0.018 (*) |
| B_ECOGN = 2 vs 1 (referencia) | 1.432 | [1.132, 1.811] | 0.003 (**) |

Interpretacion clinica descriptiva: el estado funcional reducido (ECOG 2) y el mayor numero de sistemas con comorbilidad se asocian con mayor riesgo de muerte (OS). El sexo femenino (SEXCD=1) se asocia con menor riesgo en ambos endpoints, coherente con la literatura general en cancer de pulmon. Las asociaciones son descriptivas, no causales.

Proporcionalidad: el test de Schoenfeld detecta violacion del supuesto de proporcionalidad en AGE (OS, p=0.030) y B_WEIGHT (OS, p=0.026; PFS, p=0.011). El resto de variables cumplen el supuesto. Esta violacion parcial se reporta como limitacion; los efectos de esas dos variables pueden variar a lo largo del tiempo de seguimiento.

### Calibracion

Curvas de fiabilidad para supervivencia con bandas bootstrap (n=1000) calculadas sobre predicciones OOF. El Brier Score puntual se mantiene por debajo del modelo nulo en todos los horizontes temporales evaluados (44 a 494 dias en OS), con IBS OS = 0.182 IC95% [0.172, 0.191]. El IBS PFS = 0.182 IC95% [0.172, 0.192]. La calibracion es moderada y coherente con el nivel de discriminacion observado.

Postcalibracion (Platt e isotonica) evaluada; mejoras marginales y sin significacion estadistica frente a los IC bootstrap. Modelo final reportado sin postcalibracion por parsimonia (decision registrada en el Decision log).

### Sesgos y subgrupos

#### Subgrupos OS (Bootstrap IC95%)

| Subgrupo | n | Eventos | C-index | IC95% | IBS |
|----------|---|---------|---------|-------|-----|
| Global | 479 | 397 | 0.599 | [0.569, 0.630] | 0.182 |
| Brazo NESP (TXG=1) | 240 | 205 | 0.587 | [0.542, 0.629] | 0.186 |
| Brazo placebo (TXG=0) | 239 | 192 | 0.611 | [0.564, 0.655] | 0.177 |
| ECOG 1 | 379 | 306 | 0.574 | [0.537, 0.607] | 0.178 |
| ECOG 2 | 100 | 91 | 0.524 | [0.453, 0.593] | 0.193 |
| Comorbilidades bajas (MEDHX_N <= 1) | 253 | 206 | 0.601 | [0.561, 0.642] | 0.178 |
| Comorbilidades altas (MEDHX_N > 1) | 226 | 191 | 0.591 | [0.546, 0.637] | 0.186 |
| Sexo = 0 | 315 | 266 | 0.595 | [0.555, 0.637] | 0.173 |
| Sexo = 1 | 164 | 131 | 0.586 | [0.530, 0.644] | 0.197 |
| Edad < 61 anos | 225 | 182 | 0.570 | [0.519, 0.616] | 0.172 |
| Edad >= 61 anos | 254 | 215 | 0.583 | [0.542, 0.624] | 0.190 |
| Tiempo desde diag. < mediana (0.49 m) | 219 | 187 | 0.599 | [0.553, 0.645] | 0.190 |
| Tiempo desde diag. >= mediana (0.49 m) | 260 | 210 | 0.599 | [0.555, 0.640] | 0.174 |

#### Subgrupos PFS (Bootstrap IC95%)

| Subgrupo | n | Eventos | C-index | IC95% | IBS |
|----------|---|---------|---------|-------|-----|
| Global | 479 | 440 | 0.555 | [0.525, 0.585] | 0.183 |
| Brazo NESP (TXG=1) | 240 | 221 | 0.536 | [0.490, 0.575] | 0.187 |
| Brazo placebo (TXG=0) | 239 | 219 | 0.572 | [0.526, 0.616] | 0.178 |
| ECOG 1 | 379 | 345 | 0.528 | [0.492, 0.562] | 0.181 |
| ECOG 2 | 100 | 95 | 0.484 | [0.420, 0.550] | 0.190 |
| Comorbilidades bajas (MEDHX_N <= 1) | 253 | 233 | 0.556 | [0.511, 0.603] | 0.188 |
| Comorbilidades altas (MEDHX_N > 1) | 226 | 207 | 0.545 | [0.498, 0.590] | 0.177 |
| Sexo = 0 | 315 | 291 | 0.537 | [0.499, 0.579] | 0.180 |
| Sexo = 1 | 164 | 149 | 0.541 | [0.484, 0.598] | 0.189 |
| Edad < 61 anos | 225 | 202 | 0.516 | [0.471, 0.560] | 0.182 |
| Edad >= 61 anos | 254 | 238 | 0.564 | [0.518, 0.606] | 0.184 |
| Tiempo desde diag. < mediana (0.49 m) | 219 | 206 | 0.531 | [0.486, 0.578] | 0.189 |
| Tiempo desde diag. >= mediana (0.49 m) | 260 | 234 | 0.572 | [0.528, 0.616] | 0.177 |

Interpretacion: el rendimiento es consistente entre estratos sin caidas abruptas. La discriminacion es menor en ECOG 2 en ambos endpoints (OS: 0.524; PFS: 0.484), coherente con menor heterogeneidad pronostica cuando el riesgo basal es ya elevado. Los dos brazos de aleatorizacion muestran rendimientos similares, lo que sugiere transferibilidad del modelo entre estratos de tratamiento al nivel de discriminacion alcanzable con estas senales basales.

### Limitaciones

- Cohorte de ensayo con criterios de inclusion y exclusion: validez externa limitada.
- Tamano muestral moderado (n=479).
- Predictores basales unicamente, por control anti-leakage.
- Variables de raza, tipo tumoral y extension constantes en la cohorte (varianza cero, excluidas).
- KPI-3 no cumplido: RSF y XGBoost no mejoran significativamente al Cox proporcional.
- Violacion parcial del supuesto de proporcionalidad en AGE (OS) y B_WEIGHT (OS y PFS) segun test de Schoenfeld.
- Alta tasa de eventos PFS (92%) limita la informacion de censura para estimacion de la curva de supervivencia.

### Privacidad

Datos crudos y derivados a nivel de sujeto no versionados. Analisis de riesgo de reidentificacion en tres dimensiones sobre el conjunto sintetico generado con CTGAN (SDV >= 1.0, 300 epocas, n=478).

#### Resultados del analisis de riesgo (datos sinteticos)

| Dimension | Valor observado | Umbral preregistrado | Resultado |
|-----------|----------------|---------------------|-----------|
| Membership inference AUC | 0.534 | <= 0.60 | ACEPTADO |
| TPR @ FPR=0.1 | 0.139 | <= 0.20 | ACEPTADO |
| K-anonimidad k=1 (bins 5 anos) | 7.32% | < 5.00% | NO ACEPTADO |
| K-anonimidad k<=2 (bins 5 anos) | 10.04% | < 10.00% | NO ACEPTADO |
| K-anonimidad k<=5 (bins 5 anos) | 20.71% | < 20.00% | NO ACEPTADO |
| DCR_p5 / RRDR_mediana | 0.622 | >= 0.50 | ACEPTADO |

Evaluacion global: NO ACEPTADO por k-anonimidad con la configuracion de cuasi-identificadores preregistrada (bins de edad de 5 anos, SEXCD, B_ECOGN). El analisis de sensibilidad con bins de 10 anos reduce k1 al 5.44%, k2 al 7.32% y k5 al 11.51% (k2 y k5 pasan el umbral en esa configuracion alternativa).

Interpretacion: la k-anonimidad depende directamente de la granularidad del binning de edad. Con la configuracion preregistrada, un 7.3% de registros sinteticos coincide de forma unica con al menos un real en el espacio de cuasi-identificadores, lo cual supera el umbral de proteccion. El membership inference y la DCR no muestran riesgo de identificacion directa, lo que indica que el riesgo reside en la similitud estructural de las combinaciones de atributos, no en la copia literal de registros.

Utilidad TSTR: C-index medio entrenando en sinteticos y evaluando en reales = 0.437 (vs TRTR 0.600 en el mismo esquema). Ratio de utilidad = 72.8%. La reduccion de utilidad es coherente con la capacidad limitada de CTGAN para capturar la estructura de correlacion de datos clinicos de supervivencia.

Los datos sinteticos son exclusivamente para prototipado metodologico y no refuerzan las conclusiones del modelo principal. Marco regulatorio: RGPD, LOPDGDD, AI Act y guias de anonimizacion de la AEPD.

---

## PARTE 3. Analisis de riesgos

Escalas: probabilidad e impacto se valoran como Baja, Media o Alta. La columna de estado al cierre resume la situacion real al final del trabajo (2026-06-01).

### 3.1 Riesgos del proyecto (propuesta y PEC1)

| Riesgo | Probabilidad | Impacto | Senal temprana | Mitigacion | Estado al cierre |
|---|---|---|---|---|---|
| Etiquetas de respuesta inadecuadas o incompletas (RECIST y ORR) | Alta | Alto | Alto porcentaje de valores faltantes en la respuesta directa durante la auditoria de la cohorte | Reformulacion del problema a supervivencia con censura (pivote P1), que aprovecha la informacion temporal del seguimiento | Materializado y resuelto: motivo el pivote P1, registrado en el Decision log |
| Heterogeneidad de tumor y de terapia en la cohorte | Media | Medio | Variabilidad clinica entre subgrupos y presencia del brazo de aleatorizacion | Uso del brazo NESP/placebo como variable de estratificacion y analisis de transferibilidad entre estratos | Mitigado: rendimiento consistente entre brazos (seccion 3.5 de D3) |
| Desbalanceo de clases en una tarea de clasificacion binaria | Media | Medio | Distribucion desigual de la etiqueta de respuesta | Reformulacion a supervivencia con censura, que elimina la dependencia de un umbral de clase | Mitigado: el problema se trata como tiempo hasta evento |
| Fuga de informacion (leakage) en el preprocesado o por variables post-outcome | Media | Alto | Rendimiento inusualmente alto o inestable entre particiones | Preprocesado ajustado dentro de cada particion de entrenamiento y exclusion de ficheros longitudinales y post-basales | Mitigado: estabilidad entre folds coherente (CV% bajo), sin indicios de fuga |
| Privacidad y riesgo de reidentificacion de datos de salud | Media | Alto | Datos a nivel de sujeto potencialmente identificables | Privacidad por diseno: datos crudos y derivados no versionados, solo metadatos; analisis de reidentificacion en tres dimensiones | Mitigado en lo organizativo; el conjunto sintetico queda como NO ACEPTADO por k-anonimidad (ver categoria 3.3) |
| Sobrecoste por ampliacion del alcance | Media | Medio | Acumulacion de tareas fuera del plan de sprints | Planificacion por sprints, criterios a priori y principio de parsimonia para acotar el alcance | Controlado: alcance estable, sin dependencia de nube ni de licencias |

### 3.2 Riesgos del modelo en uso (no clinico)

| Riesgo | Probabilidad | Impacto | Senal temprana | Mitigacion | Estado al cierre |
|---|---|---|---|---|---|
| Calibracion que subestima la supervivencia a largo plazo en pacientes de alto riesgo (t=355 dias) | Media | Medio | Deciles de alto riesgo con supervivencia observada por encima de la predicha en el horizonte largo | Reporte explicito de la tendencia, advertencia de no uso clinico y propuesta de extensiones dependientes del tiempo como linea futura | Documentado en 3.3 de D3 y en la Model Card; no se corrige por el caracter de prototipo |
| Discriminacion modesta (C-index OS 0.599; PFS 0.555) | Alta | Medio | Valores de C-index proximos al rango moderado en el desarrollo | Comunicacion honesta del rendimiento con intervalos de confianza y enfasis en el caracter metodologico | Documentado en 3.2 de D3; asumido como propio del prototipo |
| Interpretacion causal indebida de los hazard ratios | Media | Alto | Lectura de asociaciones como relaciones causa-efecto | Advertencia expresa de interpretacion descriptiva y no causal en D3 y en la Model Card | Mitigado mediante documentacion explicita (3.4 de D3) |
| Validez externa limitada por tratarse de una cohorte de ensayo | Alta | Alto | Criterios de inclusion y exclusion estrictos y baja representatividad poblacional | Declaracion de estudio de desarrollo sin validacion externa y propuesta de validacion externa como linea futura | Documentado como limitacion (4.2 y 4.5 de D3) |
| Violacion parcial del supuesto de proporcionalidad (AGE y B_WEIGHT) | Media | Medio | p del test de Schoenfeld por debajo de 0.05 en esas variables | Reporte de la violacion y de su alcance acotado; las variables de mayor senal cumplen el supuesto | Documentado en 3.4 de D3 y en la Model Card |
| Endpoint PFS poco informativo con predictores basales | Alta | Bajo | C-index de PFS proximo al azar (0.555) y alta tasa de eventos (92%) | Reporte de PFS por completitud, con advertencia de su utilidad pronostica marginal | Documentado en 3.2 de D3 |

### 3.3 Riesgos de privacidad y de uso indebido

| Riesgo | Probabilidad | Impacto | Senal temprana | Mitigacion | Estado al cierre |
|---|---|---|---|---|---|
| El conjunto sintetico resulta NO ACEPTADO por k-anonimidad con bins de edad de 5 anos | Alta | Medio | Fraccion de registros sinteticos con combinacion unica de cuasi-identificadores por encima del umbral (k1 = 7.32%) | Uso del sintetico solo para prototipado, no publicado; analisis de sensibilidad con bins de 10 anos; triangulacion con membership inference (AUC 0.534) y DCR (ratio 0.622) | Materializado y gestionado: documentado como NO ACEPTADO, con sensibilidad y triangulacion (3.6 de D3 y Model Card) |
| Interpretacion clinica del prototipo por parte de terceros | Media | Alto | Uso del modelo o de los sinteticos fuera del contexto metodologico | Advertencia explicita de no uso clinico en D3 y en la Model Card, y restriccion del uso de los sinteticos al prototipado | Mitigado mediante documentacion y advertencias inequivocas |
| Difusion de datos a nivel de sujeto | Baja | Alto | Inclusion accidental de datos crudos o derivados en el control de versiones | Privacidad por diseno: exclusion de los datos de sujeto del repositorio, solo metadatos (diccionario, hashes y manifiesto) | Controlado: no se versionan datos de sujeto |

---

Fin del documento D4. Fuentes: docs/CLAUDE.md, docs/decision_log.md, docs/model_card.md y artefactos de la carpeta output (ficheros JSON y CSV).
