# D4. Paquete de transparencia y gobernanza

Trabajo Final de Grado. Predicción de respuesta a fármacos quimioterapéuticos a partir de datos clínicos anonimizados. Estudiante: Alfonso Esteban Lasso. Fecha de cierre: 2026-06-01.

Este documento es autocontenido y reune tres partes: (1) el checklist de reporte transparente TRIPOD+AI con referencia cruzada a la memoria D3; (2) la Model Card final del modelo; y (3) el análisis de riesgos del proyecto, del modelo y de la privacidad. Todos los valores proceden de los artefactos del pipeline (carpeta output) y de la documentación viva del proyecto (decision_log y model_card). No se introduce ningún valor que no figure en esas fuentes.

Nota sobre derechos de autor: el checklist TRIPOD+AI (Collins y colaboradores, 2024, BMJ 385:e078378) es material protegido por copyright. En la Parte 1 no se reproduce el texto literal de los items ni las tablas oficiales. Cada item se parafrasea de forma breve y original, con la única finalidad de documentar el cumplimiento del estudio.

---

## PARTE 1. Checklist TRIPOD+AI con referencia cruzada a D3

### 1.1 Naturaleza del estudio y alcance de la validación

Se declara de entrada que este trabajo es un estudio de DESARROLLO de un modelo pronóstico, con validación interna mediante validación cruzada estratificada k=5 y bootstrap de n=1000. No se realiza validación externa en una cohorte independiente. En consecuencia, todos los items relativos a validación externa se marcan como No aplica o como línea futura, de forma explícita y honesta. Esta limitación se recoge también en la Parte 2 (Model Card) y en la Parte 3 (análisis de riesgos).

Leyenda de estado: Cumplido (el item se aborda en D3), Parcial (se aborda de forma incompleta o con matices), No aplica (no procede por el alcance del estudio).

El índice de la memoria D3 al que se hace referencia es: 1.1 contexto; 1.2 estado del arte; 1.3 objetivos; 1.4 impacto CCEG; 1.5 enfoque; 1.6 planificacion; 1.7 productos; 1.8 otros capítulos; 1.9 declaración de IA; 2.1 datos y cohorte; 2.2 diseño y control de fugas; 2.3 modelos; 2.4 métricas; 2.5 privacidad y sintéticos; 2.6 reproducibilidad; 2.7 valoración económica; 3.1 comparativa y selección; 3.2 modelo final OS y PFS; 3.3 calibración; 3.4 interpretabilidad; 3.5 robustez y subgrupos; 3.6 datos sintéticos; 4.1 conclusiones; 4.2 objetivos; 4.3 planificacion; 4.4 impactos; 4.5 líneas futuras.

### 1.2 Título y resumen

| Item (parafraseado) | Estado | Sección D3 |
|---|---|---|
| El título identifica que el trabajo desarrolla un modelo de predicción de supervivencia y senala la población oncologica. | Cumplido | Portada y 1.1 |
| El resumen recoge objetivo, datos, métodos, resultados principales y conclusiones, e indica que se trata de un prototipo no clínico. | Cumplido | Ficha (resumen y abstract) |

### 1.3 Introducción

| Item (parafraseado) | Estado | Sección D3 |
|---|---|---|
| Se explica el contexto clínico, la variabilidad de respuesta a la quimioterapia y por qué un modelo pronóstico es pertinente. | Cumplido | 1.1 |
| Se justifica el enfoque metodológico de prototipo reproducible frente a uno orientado a la complejidad. | Cumplido | 1.1, 1.4 |
| Se enuncian los objetivos general y específicos (O1 a O6) con sus criterios de éxito (KPI). | Cumplido | 1.2 |

### 1.4 Métodos

| Item (parafraseado) | Estado | Sección D3 |
|---|---|---|
| Se describe la fuente de datos (estudio NESP-Oncology-20010145, NCT00119613, Project Data Sphere) y el cambio documentado de fuente respecto de la propuesta inicial. | Cumplido | 2.1 |
| Se indica el diseño del estudio (desarrollo con validación interna) y la ventana temporal basal del seguimiento. | Cumplido | 2.1, 2.2 |
| Se detallan los participantes y los criterios de la cohorte (479 sujetos, una fila por sujeto). | Cumplido | 2.1 |
| Se definen los desenlaces OS (a partir de DTH y DTHDY) y PFS (a partir de PFSCD y PFSDY), con censura y codificación 1 evento, 0 censura. | Cumplido | 2.1, 2.4 |
| Se especifican los siete predictores basales (AGE, SEXCD, B_ECOGN, B_WEIGHT, CADIAGM, B_HGB, MEDHX_N) y la derivación de MEDHX_N. | Cumplido | 2.1 |
| Se documenta el control de variables posteriores al desenlace: exclusión de ficheros longitudinales y post-basales para evitar fuga. | Cumplido | 2.2 |
| Se justifica el tamaño muestral (n=479) y la validación adaptada (k=5 estratificada con bootstrap de n=1000). | Cumplido | 2.1, 2.2 |
| Se describe el tratamiento de datos faltantes con imputación ajustada dentro de cada partición de entrenamiento. | Cumplido | 2.1, 2.2 |
| Se detallan los métodos de análisis: Cox, RSF y XGBoost, validación cruzada estratificada, bootstrap, criterio de selección a priori y control de fugas. | Cumplido | 2.2, 2.3 |
| Se describe la salida del modelo (función de riesgo y supervivencia) y la interpretación mediante hazard ratios. | Cumplido | 2.3, 3.4 |
| Se especifican las métricas de evaluación (C-index, IBS, Brier dependiente del tiempo, AUC dependiente del tiempo y calibración con bandas). | Cumplido | 2.4 |
| Se aborda la validación externa en una cohorte independiente. | No aplica (línea futura) | 4.5 |

### 1.5 Componente específico de inteligencia artificial y aprendizaje automático

| Item (parafraseado) | Estado | Sección D3 |
|---|---|---|
| Se identifica el tipo de modelos empleados (un modelo estadístico de riesgos proporcionales y dos modelos de aprendizaje automático de supervivencia). | Cumplido | 2.3 |
| Se indican el software y las versiones de las herramientas utilizadas. | Cumplido | 2.6 |
| Se documentan las semillas fijas y las condiciones de reproducibilidad. | Cumplido | 2.6 |
| Se evalua el rendimiento por subgrupos y la equidad del desempeño, incluido el sexo como perspectiva de género. | Cumplido | 3.5 |
| Se describe el procedimiento de ajuste de hiperparametros dentro del esquema de validación. | Parcial | 2.2, 2.3 |
| Se valora el riesgo de sesgo y la robustez del modelo entre estratos. | Cumplido | 3.5 |

### 1.6 Ciencia abierta y disponibilidad

| Item (parafraseado) | Estado | Sección D3 |
|---|---|---|
| Se indica la disponibilidad del código en el repositorio del pipeline (entregable D1). | Cumplido | 2.6, anexo 7.2 |
| Se aclara que los datos a nivel de sujeto no se comparten por privacidad por diseño y que solo se publican metadatos. | Cumplido | 2.5, 2.6 |
| Se incluye la declaración sobre el uso de herramientas de inteligencia artificial generativa. | Cumplido | 1.8 |
| Se declara el protocolo o registro previo del estudio. | Parcial | 2.2 (criterios a priori) |

### 1.7 Resultados

| Item (parafraseado) | Estado | Sección D3 |
|---|---|---|
| Se describe el flujo de participantes y el número de eventos (OS: 397 eventos; PFS: 440 eventos sobre n=479). | Cumplido | 2.1, 3.2 |
| Se presenta la comparativa de modelos bajo el criterio fijado a priori. | Cumplido | 3.1 |
| Se identifica el modelo final (Cox proporcional por parsimonia) y su justificación. | Cumplido | 3.1 |
| Se reporta el rendimiento (C-index, IBS, AUC dependiente del tiempo) con intervalos de confianza. | Cumplido | 3.2 |
| Se presenta la calibración con bandas bootstrap en varios horizontes temporales. | Cumplido | 3.3 |
| Se aporta la interpretabilidad mediante hazard ratios y el test de proporcionalidad. | Cumplido | 3.4 |
| Se analiza la robustez por subgrupos. | Cumplido | 3.5 |
| Se documentan los datos sintéticos y su evaluación de utilidad y riesgo. | Cumplido | 3.6 |

### 1.8 Discusión

| Item (parafraseado) | Estado | Sección D3 |
|---|---|---|
| Se discuten las limitaciones: validez externa limitada por tratarse de una cohorte de ensayo. | Cumplido | 4.1, 4.2 |
| Se reconoce el tamaño muestral moderado (n=479). | Cumplido | 4.2 |
| Se reporta de forma honesta que el KPI-3 (mejora sobre baseline) no se cumple. | Cumplido | 3.1, 4.2 |
| Se documenta la violación parcial del supuesto de proporcionalidad en AGE y B_WEIGHT. | Cumplido | 3.4 |
| Se senala que el endpoint PFS es poco informativo con estos predictores. | Cumplido | 3.2 |
| Se aclara que la interpretación de las asociaciones es descriptiva y no causal. | Cumplido | 3.4 |
| Se incluye la advertencia explícita de no uso clínico. | Cumplido | 1.1, Model Card |
| Se interpretan los resultados en el contexto de la evidencia disponible y su implicación práctica como prototipo. | Cumplido | 4.1, 4.4 |

### 1.9 Otra información

| Item (parafraseado) | Estado | Sección D3 |
|---|---|---|
| Se declara la financiacion del trabajo: ninguna. | Cumplido | Otra información (este documento) |
| Se declaran los conflictos de interés: ninguno. | Cumplido | Otra información (este documento) |
| Se confirma la ausencia de mención a centros externos de colaboración. | Cumplido | Todo el documento |

Financiacion: el trabajo no ha recibido financiacion. Conflictos de interés: el autor declara no tener ningún conflicto de interés. No existe ninguna entidad externa de colaboración asociada al trabajo.

---

## PARTE 2. Model Card final

Nota sobre la fuente canónica: la versión viva y de referencia de la Model Card es el fichero docs/model_card.md, cerrado en el Sprint 8 con los valores reales del pipeline. El contenido que sigue reproduce esa fuente sin alterar ningún valor. En caso de discrepancia, prevalece docs/model_card.md.

### Uso previsto

Prototipo de investigación y validación metodológica para predecir supervivencia (OS y PFS) bajo quimioterapia a partir de variables clínicas basales. Público: perfiles de ciencia de datos biomedica y equipos de I+D. No es un dispositivo clínico.

### Advertencia de no uso clínico

El modelo no esta validado para uso clínico ni para decisiones individuales de pacientes. Su finalidad es académica y metodológica.

### Población y datos

- Cohorte: estudio NESP-Oncology-20010145 (NCT00119613), Project Data Sphere. Ensayo de fase III, aleatorizado, doble ciego y controlado con placebo, en pacientes con cáncer de pulmón microcítico (de células pequeñas) en estadio extenso, no tratados previamente, que reciben quimioterapia con platino y etopósido (darbepoetina alfa frente a placebo). El trabajo lo reformula como pronóstico de supervivencia y no estudia el efecto del agente del estudio.
- n = 479 sujetos (una fila por sujeto). El protocolo del ensayo planifico aproximadamente 600 sujetos (unos 300 por brazo, con análisis final previsto a las 496 muertes); la cohorte disponible en Project Data Sphere comprende 479. Eventos OS: 397 (83%); censurados: 82 (17%). Eventos PFS: 440 (92%); censurados: 39 (8%).
- Brazo de aleatorizacion NESP/placebo usado como estratificación, no como predictor.
- Predictores (Estrategia 1): AGE, SEXCD, B_ECOGN, B_WEIGHT, CADIAGM, B_HGB, MEDHX_N.
- Endpoints: OS (DTH, DTHDY) y PFS (PFSCD, PFSDY).

### Modelo

- Baseline: Cox proporcional.
- Candidatos: Random Survival Forest y XGBoost/LightGBM con perdida de supervivencia.
- Selección por criterio a priori: C-index más IBS más coeficiente de variación entre folds.
- Modelo final: Cox proporcional (parsimonia). Ningún candidato mejora significativamente el baseline segun el criterio fijado a priori. Los IC bootstrap se solapan completamente entre Cox y RSF.

### Métricas del modelo final (Cox proporcional)

Todas las métricas se calculan sobre predicciones OOF (out-of-fold) del CV k=5 para evitar sobreajuste.

#### OS (endpoint primario)

| Métrica | CV k=5 media +/- std (CV%) | Bootstrap n=1000 | IC95% bootstrap |
|---------|---------------------------|-----------------|-----------------|
| C-index | 0.600 +/- 0.042 (7.1%) | 0.599 | [0.567, 0.629] |
| IBS | 0.182 +/- 0.013 (7.2%) | 0.182 | [0.172, 0.191] |
| AUC dinámica media | -- | 0.645 | [0.601, 0.690] |

Detalle por fold (OS): fold 1 = 0.528, fold 2 = 0.614, fold 3 = 0.635, fold 4 = 0.623, fold 5 = 0.599.

#### PFS (endpoint secundario)

| Métrica | CV k=5 media +/- std (CV%) | Bootstrap n=1000 | IC95% bootstrap |
|---------|---------------------------|-----------------|-----------------|
| C-index | 0.552 +/- 0.028 (5.1%) | 0.555 | [0.525, 0.586] |
| IBS | 0.182 +/- 0.012 (6.4%) | 0.182 | [0.172, 0.192] |
| AUC dinámica media | -- | 0.584 | [0.536, 0.632] |

#### Comparación de modelos (OS, criterio a priori)

| Modelo | C-index CV (CV%) | IBS CV | Boot C-index | IC95% |
|--------|-----------------|--------|-------------|-------|
| Cox PH | 0.600 (7.05%) | 0.182 | 0.599 | [0.567, 0.629] |
| RSF | 0.593 (4.54%) | 0.181 | 0.592 | [0.562, 0.621] |
| XGBoost | 0.549 (5.50%) | 0.187 | 0.552 | [0.523, 0.582] |

KPI-3 (mejora sobre baseline): NO CUMPLIDO. Los IC bootstrap de RSF y Cox solapan completamente (diferencia C-index = 0.007). Con n=479 y 7 predictores basales, la superficie de decisión es prácticamente lineal y los modelos no lineales no tienen ventaja en esta cohorte. Se documenta como limitación explícita.

### Coeficientes y hazard ratios (Cox proporcional)

#### OS

| Variable | HR | IC95% | p |
|----------|-----|-------|---|
| Edad (por año) | 1.006 | [0.993, 1.019] | 0.347 |
| Peso basal (por kg) | 0.994 | [0.987, 1.002] | 0.130 |
| Tiempo desde diag. (por mes) | 0.969 | [0.877, 1.070] | 0.536 |
| Hemoglobina basal (por g/dL) | 0.979 | [0.890, 1.077] | 0.666 |
| N. sistemas comorbilidad | 1.086 | [1.003, 1.177] | 0.042 (*) |
| Sexo = 1 vs 0 | 0.641 | [0.514, 0.799] | < 0.001 (***) |
| B_ECOGN = 2 vs 1 (referencia) | 1.693 | [1.326, 2.160] | < 0.001 (***) |

#### PFS

| Variable | HR | IC95% | p |
|----------|-----|-------|---|
| Edad (por año) | 1.007 | [0.994, 1.019] | 0.292 |
| Peso basal (por kg) | 0.998 | [0.991, 1.005] | 0.527 |
| Tiempo desde diag. (por mes) | 0.941 | [0.853, 1.038] | 0.221 |
| Hemoglobina basal (por g/dL) | 0.970 | [0.886, 1.062] | 0.516 |
| N. sistemas comorbilidad | 1.034 | [0.956, 1.118] | 0.407 |
| Sexo = 1 vs 0 | 0.779 | [0.634, 0.958] | 0.018 (*) |
| B_ECOGN = 2 vs 1 (referencia) | 1.432 | [1.132, 1.811] | 0.003 (**) |

Interpretación clínica descriptiva: el estado funcional reducido (ECOG 2) y el mayor número de sistemas con comorbilidad se asocian con mayor riesgo de muerte (OS). El sexo femenino (SEXCD=1) se asocia con menor riesgo en ambos endpoints, coherente con la literatura general en cáncer de pulmón. Las asociaciones son descriptivas, no causales.

Proporcionalidad: el test de Schoenfeld detecta violación del supuesto de proporcionalidad en AGE (OS, p=0.030) y B_WEIGHT (OS, p=0.026; PFS, p=0.011). El resto de variables cumplen el supuesto. Esta violación parcial se reporta como limitación; los efectos de esas dos variables pueden variar a lo largo del tiempo de seguimiento.

### Calibración

Curvas de fiabilidad para supervivencia con bandas bootstrap (n=1000) calculadas sobre predicciones OOF. El Brier Score puntual se mantiene por debajo del modelo nulo en todos los horizontes temporales evaluados (44 a 494 días en OS), con IBS OS = 0.182 IC95% [0.172, 0.191]. El IBS PFS = 0.182 IC95% [0.172, 0.192]. La calibración es moderada y coherente con el nivel de discriminación observado.

Postcalibracion (Platt e isotónica) evaluada; mejoras marginales y sin significación estadística frente a los IC bootstrap. Modelo final reportado sin postcalibracion por parsimonia (decisión registrada en el Decisión log).

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
| Edad < 61 años | 225 | 182 | 0.570 | [0.519, 0.616] | 0.172 |
| Edad >= 61 años | 254 | 215 | 0.583 | [0.542, 0.624] | 0.190 |
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
| Edad < 61 años | 225 | 202 | 0.516 | [0.471, 0.560] | 0.182 |
| Edad >= 61 años | 254 | 238 | 0.564 | [0.518, 0.606] | 0.184 |
| Tiempo desde diag. < mediana (0.49 m) | 219 | 206 | 0.531 | [0.486, 0.578] | 0.189 |
| Tiempo desde diag. >= mediana (0.49 m) | 260 | 234 | 0.572 | [0.528, 0.616] | 0.177 |

Interpretación: el rendimiento es consistente entre estratos sin caídas abruptas. La discriminación es menor en ECOG 2 en ambos endpoints (OS: 0.524; PFS: 0.484), coherente con menor heterogeneidad pronóstica cuando el riesgo basal es ya elevado. Los dos brazos de aleatorizacion muestran rendimientos similares, lo que sugiere transferibilidad del modelo entre estratos de tratamiento al nivel de discriminación alcanzable con estas senales basales.

### Limitaciones

- Cohorte de ensayo con criterios de inclusión y exclusión: validez externa limitada.
- Tamaño muestral moderado (n=479).
- Predictores basales únicamente, por control anti-leakage.
- Variables de tipo tumoral, extensión y clase de quimioterapia invariantes por los criterios de inclusión del protocolo, y raza de varianza cero observada: todas constantes en la cohorte y excluidas.
- KPI-3 no cumplido: RSF y XGBoost no mejoran significativamente al Cox proporcional.
- Violación parcial del supuesto de proporcionalidad en AGE (OS) y B_WEIGHT (OS y PFS) segun test de Schoenfeld.
- Alta tasa de eventos PFS (92%) limita la información de censura para estimación de la curva de supervivencia.

### Privacidad

Datos crudos y derivados a nivel de sujeto no versionados. Análisis de riesgo de reidentificación en tres dimensiones sobre el conjunto sintético generado con CTGAN (SDV >= 1.0, 300 épocas, n=478).

#### Resultados del análisis de riesgo (datos sintéticos)

| Dimensión | Valor observado | Umbral preregistrado | Resultado |
|-----------|----------------|---------------------|-----------|
| Membership inference AUC | 0.534 | <= 0.60 | ACEPTADO |
| TPR @ FPR=0.1 | 0.139 | <= 0.20 | ACEPTADO |
| K-anonimidad k=1 (bins 5 años) | 7.32% | < 5.00% | NO ACEPTADO |
| K-anonimidad k<=2 (bins 5 años) | 10.04% | < 10.00% | NO ACEPTADO |
| K-anonimidad k<=5 (bins 5 años) | 20.71% | < 20.00% | NO ACEPTADO |
| DCR_p5 / RRDR_mediana | 0.622 | >= 0.50 | ACEPTADO |

Evaluación global: NO ACEPTADO por k-anonimidad con la configuración de cuasi-identificadores preregistrada (bins de edad de 5 años, SEXCD, B_ECOGN). El análisis de sensibilidad con bins de 10 años reduce k1 al 5.44%, k2 al 7.32% y k5 al 11.51% (k2 y k5 pasan el umbral en esa configuración alternativa).

Interpretación: la k-anonimidad depende directamente de la granularidad del binning de edad. Con la configuración preregistrada, un 7.3% de registros sintéticos coincide de forma única con al menos un real en el espacio de cuasi-identificadores, lo cual supera el umbral de protección. El membership inference y la DCR no muestran riesgo de identificación directa, lo que indica que el riesgo reside en la similitud estructural de las combinaciones de atributos, no en la copia literal de registros.

Utilidad TSTR: C-index medio entrenando en sintéticos y evaluando en reales = 0.437 (vs TRTR 0.600 en el mismo esquema). Ratio de utilidad = 72.8%. La reducción de utilidad es coherente con la capacidad limitada de CTGAN para capturar la estructura de correlación de datos clínicos de supervivencia.

Generador alternativo (TVAE) y tensión utilidad-privacidad: ante el incumplimiento de la k-anonimidad por CTGAN, se evaluó un autoencoder variacional tabular (TVAE) con los mismos metadatos, épocas, semilla y criterios preregistrados. TVAE mejora drásticamente la utilidad (TSTR 0.606, ratio 100.9%) y cumple la k-anonimidad (k1 1.46%, k5 3.56%), pero falla la distancia al registro más cercano (DCR_p5/RRDR 0.343, < 0.50): al reproducir mejor la estructura, genera registros demasiado próximos a sujetos reales. Por separado, ningún generador satisface a la vez los tres criterios.

Resolución de la tensión (solución combinada): el trilema entre fidelidad marginal, utilidad de discriminación y privacidad se resolvió combinando el TVAE con una augmentación contra el colapso de modos (replicación numérica de las clases DTH, PFSCD, SEXCD y B_ECOGN) y un filtro de privacidad por DCR (rechazo de los registros más próximos a un sujeto real), sin relajar ningún umbral, y midiendo la fidelidad marginal con la distancia de variación total (TVD). La configuración óptima (TVAE con augmentación y filtro DCR, n=5000) supera los tres criterios a la vez: TSTR 0.583, fidelidad TVD 0.057, membership inference 0.519, k1 1.24%, k5 3.60% y DCR_p5/RRDR 0.577. Evaluación global: ACEPTADO. El conjunto resultante (`synthetic_dataset_tvae_dcr_aug_n5000.csv`) es candidato a dataset sintético derivado compartible que sustituya al real no versionado. Detalle en `output/Solucion_sintetica_utilidad_privacidad.md`.

Los datos sintéticos son exclusivamente para prototipado metodológico y no refuerzan las conclusiones del modelo principal. Marco regulatorio: RGPD, LOPDGDD, AI Act y guías de anonimizacion de la AEPD.

---

## PARTE 3. Análisis de riesgos

Escalas: probabilidad e impacto se valoran como Baja, Media o Alta. La columna de estado al cierre resume la situación real al final del trabajo (2026-06-01).

### 3.1 Riesgos del proyecto (propuesta y PEC1)

| Riesgo | Probabilidad | Impacto | Señal temprana | Mitigación | Estado al cierre |
|---|---|---|---|---|---|
| Etiquetas de respuesta inadecuadas o incompletas (RECIST y ORR) | Alta | Alto | Alto porcentaje de valores faltantes en la respuesta directa durante la auditoria de la cohorte | Reformulacion del problema a supervivencia con censura (pivote P1), que aprovecha la información temporal del seguimiento | Materializado y resuelto: motivo el pivote P1, registrado en el Decisión log |
| Heterogeneidad de tumor y de terapia en la cohorte | Media | Medio | Variabilidad clínica entre subgrupos y presencia del brazo de aleatorizacion | Uso del brazo NESP/placebo como variable de estratificación y análisis de transferibilidad entre estratos | Mitigado: rendimiento consistente entre brazos (sección 3.5 de D3) |
| Desbalanceo de clases en una tarea de clasificación binaria | Media | Medio | Distribución desigual de la etiqueta de respuesta | Reformulacion a supervivencia con censura, que elimina la dependencia de un umbral de clase | Mitigado: el problema se trata como tiempo hasta evento |
| Fuga de información (leakage) en el preprocesado o por variables post-outcome | Media | Alto | Rendimiento inusualmente alto o inestable entre particiones | Preprocesado ajustado dentro de cada partición de entrenamiento y exclusión de ficheros longitudinales y post-basales | Mitigado: estabilidad entre folds coherente (CV% bajo), sin indicios de fuga |
| Privacidad y riesgo de reidentificación de datos de salud | Media | Alto | Datos a nivel de sujeto potencialmente identificables | Privacidad por diseño: datos crudos y derivados no versionados, solo metadatos; análisis de reidentificación en tres dimensiones | Mitigado en lo organizativo; la tensión de privacidad del sintético se resolvió con la solución combinada TVAE con augmentación y filtro DCR (ver categoría 3.3) |
| Sobrecoste por ampliación del alcance | Media | Medio | Acumulación de tareas fuera del plan de sprints | Planificacion por sprints, criterios a priori y principio de parsimonia para acotar el alcance | Controlado: alcance estable, sin dependencia de nube ni de licencias |

### 3.2 Riesgos del modelo en uso (no clínico)

| Riesgo | Probabilidad | Impacto | Señal temprana | Mitigación | Estado al cierre |
|---|---|---|---|---|---|
| Calibración que subestima la supervivencia a largo plazo en pacientes de alto riesgo (t=355 días) | Media | Medio | Deciles de alto riesgo con supervivencia observada por encima de la predicha en el horizonte largo | Reporte explícito de la tendencia, advertencia de no uso clínico y propuesta de extensiones dependientes del tiempo como línea futura | Documentado en 3.3 de D3 y en la Model Card; no se corrige por el carácter de prototipo |
| Discriminación modesta (C-index OS 0.599; PFS 0.555) | Alta | Medio | Valores de C-index próximos al rango moderado en el desarrollo | Comunicación honesta del rendimiento con intervalos de confianza y énfasis en el carácter metodológico | Documentado en 3.2 de D3; asumido como propio del prototipo |
| Interpretación causal indebida de los hazard ratios | Media | Alto | Lectura de asociaciones como relaciones causa-efecto | Advertencia expresa de interpretación descriptiva y no causal en D3 y en la Model Card | Mitigado mediante documentación explícita (3.4 de D3) |
| Validez externa limitada por tratarse de una cohorte de ensayo | Alta | Alto | Criterios de inclusión y exclusión estrictos y baja representatividad poblacional | Declaración de estudio de desarrollo sin validación externa y propuesta de validación externa como línea futura | Documentado como limitación (4.2 y 4.5 de D3) |
| Violación parcial del supuesto de proporcionalidad (AGE y B_WEIGHT) | Media | Medio | p del test de Schoenfeld por debajo de 0.05 en esas variables | Reporte de la violación y de su alcance acotado; las variables de mayor señal cumplen el supuesto | Documentado en 3.4 de D3 y en la Model Card |
| Endpoint PFS poco informativo con predictores basales | Alta | Bajo | C-index de PFS próximo al azar (0.555) y alta tasa de eventos (92%) | Reporte de PFS por completitud, con advertencia de su utilidad pronóstica marginal | Documentado en 3.2 de D3 |

### 3.3 Riesgos de privacidad y de uso indebido

| Riesgo | Probabilidad | Impacto | Señal temprana | Mitigación | Estado al cierre |
|---|---|---|---|---|---|
| El conjunto sintético resulta NO ACEPTADO por k-anonimidad con bins de edad de 5 años (CTGAN) | Alta | Medio | Fracción de registros sintéticos con combinación única de cuasi-identificadores por encima del umbral (k1 = 7.32%) | Uso del sintético solo para prototipado; análisis de sensibilidad con bins de 10 años; triangulación con membership inference (AUC 0.534) y DCR (ratio 0.622); desarrollo de una solución combinada (TVAE con augmentación de clases y filtro de proximidad por DCR) | Resuelto: la solución combinada (n=5000) supera los tres criterios preregistrados (k1 1.24%, MI 0.519, DCR 0.577) con buena fidelidad (TVD 0.057); es candidata a dataset derivado compartible (3.6.1 de D3 y Model Card) |
| Interpretación clínica del prototipo por parte de terceros | Media | Alto | Uso del modelo o de los sintéticos fuera del contexto metodológico | Advertencia explícita de no uso clínico en D3 y en la Model Card, y restricción del uso de los sintéticos al prototipado | Mitigado mediante documentación y advertencias inequívocas |
| Difusión de datos a nivel de sujeto | Baja | Alto | Inclusión accidental de datos crudos o derivados en el control de versiones | Privacidad por diseño: exclusión de los datos de sujeto del repositorio, solo metadatos (diccionario, hashes y manifiesto) | Controlado: no se versionan datos de sujeto |

---

Fin del documento D4. Fuentes: documentación interna del proyecto (decision_log y model_card) y artefactos de la carpeta output (ficheros JSON y CSV).
