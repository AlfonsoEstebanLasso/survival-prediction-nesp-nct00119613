# Model Card

Documento vivo desde el Sprint 3, cerrado en el Sprint 8 con los valores reales del pipeline (2026-06-01). La estructura sigue el marco de referencia de model cards de Mitchell et al. (2018), "Model Cards for Model Reporting" (Google), con sus nueve secciones.

## 1. Detalles del modelo

- Nombre: Predicción de supervivencia (OS y PFS) bajo quimioterapia. Modelo pronóstico Cox de riesgos proporcionales.
- Versión: 1.0 (cerrada el 2026-06-01).
- Tipo de modelo: regresión de Cox de riesgos proporcionales (lifelines), modelo de supervivencia con censura por la derecha.
- Endpoints modelados: supervivencia global OS (variables DTH, DTHDY) y supervivencia libre de progresión PFS (variables PFSCD, PFSDY), codificados con 1 = evento y 0 = censura.
- Autor: Alfonso Esteban Lasso ([email-eliminado]). Tutor: Tutor del TFG.
- Contexto: Trabajo Final del Grado en Ciencia de Datos Aplicada (UOC). Prototipo de investigación, no dispositivo clínico.
- Entorno y reproducibilidad: Python 3.12.4; lifelines 0.30.3; scikit-survival 0.27.0; scikit-learn 1.8.0; xgboost 3.2.0; lightgbm 4.6.0; pandas 2.3.3; numpy 2.4.6. Semilla global fija (SEED = 42). Versiones congeladas en environment.yml; reproducibilidad verificada en entorno limpio (KPI-1).
- Licencia: Reconocimiento-NoComercial-SinObraDerivada 3.0 España de Creative Commons (CC BY-NC-ND 3.0 ES).
- Cómo citar: Esteban Lasso, A. (2026). Predicción de respuesta a fármacos quimioterapéuticos a partir de datos clínicos anonimizados (Trabajo Final de Grado). Universitat Oberta de Catalunya.

## 2. Uso previsto

Prototipo de investigación y validación metodológica para predecir supervivencia (OS y PFS) bajo quimioterapia a partir de variables clínicas basales. Su finalidad es académica y metodológica: demostrar un proceso reproducible, auditable y con control estricto de fugas de información.

- Usuarios previstos: perfiles de ciencia de datos biomédica y equipos de I+D interesados en metodología pronóstica reproducible.
- Usos fuera de alcance: no es un dispositivo clínico ni una herramienta de ayuda a la decisión. No debe usarse para decisiones individuales de pacientes, cribado, triaje, ni para estimar el efecto del agente del estudio (darbepoetina alfa). El modelo no está validado para uso clínico.

## 3. Factores

Factores relevantes considerados en la evaluación del rendimiento (análisis por subgrupos en la sección 7):

- Grupos de sujeto: sexo (SEXCD), estado funcional ECOG basal (B_ECOGN), edad, carga de comorbilidad (MEDHX_N) y tiempo desde el diagnóstico.
- Factor de tratamiento: brazo de aleatorización NESP/placebo (TXG), usado como variable de estratificación, nunca como predictor ni objeto causal.
- Instrumentación y entorno: ensayo clínico multicéntrico único, con laboratorios locales. La homogeneidad del protocolo (tipo tumoral, estadio y régimen de quimioterapia constantes por criterio de inclusión) limita la variabilidad de instrumentación, pero también la validez externa.

## 4. Métricas

Métricas de evaluación y justificación de su elección. Todas se calculan sobre predicciones OOF (out-of-fold) del CV k=5 estratificado, con intervalos de confianza por bootstrap (n=1000), para evitar sobreajuste.

- C-index (índice de concordancia): discriminación, es decir, capacidad de ordenar correctamente el riesgo entre pares de sujetos. Métrica principal del criterio de selección.
- IBS (Integrated Brier Score) y Brier puntual: error de predicción integrado en el tiempo y calibración global; penaliza tanto la discriminación como la calibración.
- AUC dependiente del tiempo: discriminación por horizonte temporal concreto.
- Curvas de calibración con bandas bootstrap: concordancia entre probabilidad predicha y observada por horizonte.
- Coeficiente de variación entre folds: estabilidad del rendimiento (criterio anti-leakage y de robustez).

## 5. Datos de evaluación

- Esquema: validación interna mediante validación cruzada estratificada k=5 con predicciones OOF y bootstrap de n=1000. No existe partición fija de entrenamiento y prueba: cada métrica se calcula sobre los folds de validación.
- No se realiza validación externa en una cohorte independiente; se documenta como limitación y línea futura.
- Anti-leakage: todo el preprocesado (imputación, codificación, escalado) se ajusta solo dentro del fold de entrenamiento. La ausencia de fuga se verifica por la estabilidad entre folds (CV% < 10%).

## 6. Datos de entrenamiento

- Cohorte: estudio NESP-Oncology-20010145 (NCT00119613), Project Data Sphere. Ensayo de fase III, aleatorizado, doble ciego y controlado con placebo, en pacientes con cáncer de pulmón microcítico (de células pequeñas) en estadio extenso, no tratados previamente, que reciben quimioterapia con platino y etopósido (darbepoetina alfa frente a placebo). El trabajo lo reformula como pronóstico de supervivencia y no estudia el efecto del agente del estudio.
- n = 479 sujetos (una fila por sujeto). El protocolo del ensayo planificó aproximadamente 600 sujetos (unos 300 por brazo, con análisis final previsto a las 496 muertes); la cohorte disponible en Project Data Sphere comprende 479. Eventos OS: 397 (83%); censurados: 82 (17%). Eventos PFS: 440 (92%); censurados: 39 (8%).
- Brazo de aleatorización NESP/placebo usado como estratificación, no como predictor.
- Predictores (Estrategia 1): AGE, SEXCD, B_ECOGN, B_WEIGHT, CADIAGM, B_HGB, MEDHX_N. Solo variables basales (pre-tratamiento).
- Variables de tipo tumoral, extensión y clase de quimioterapia invariantes por los criterios de inclusión del protocolo, y raza de varianza cero observada: todas constantes en la cohorte y excluidas.
- No hay partición fija train/test: dentro del CV k=5, el preprocesado se ajusta en cada fold de entrenamiento y se aplica al de validación.

## 7. Análisis cuantitativo

### Modelo y selección

- Baseline: Cox proporcional.
- Candidatos: Random Survival Forest y XGBoost/LightGBM con pérdida de supervivencia.
- Selección por criterio a priori: C-index más IBS más coeficiente de variación entre folds.
- **Modelo final: Cox proporcional (parsimonia).** Ningún candidato mejora significativamente el baseline según el criterio fijado a priori. Los IC bootstrap se solapan completamente entre Cox y RSF.

### Métricas del modelo final (Cox proporcional)

#### OS (endpoint primario)

| Métrica | CV k=5 media +/- std (CV%) | Bootstrap n=1000 | IC95% bootstrap |
|---------|---------------------------|-----------------|-----------------|
| C-index | 0.600 +/- 0.042 (7.1%) | 0.599 | [0.567, 0.629] |
| IBS | 0.182 +/- 0.013 (7.2%) | 0.182 | [0.172, 0.191] |
| AUC dinamica media | -- | 0.645 | [0.601, 0.690] |

Detalle por fold (OS): fold 1 = 0.528, fold 2 = 0.614, fold 3 = 0.635, fold 4 = 0.623, fold 5 = 0.599.

#### PFS (endpoint secundario)

| Métrica | CV k=5 media +/- std (CV%) | Bootstrap n=1000 | IC95% bootstrap |
|---------|---------------------------|-----------------|-----------------|
| C-index | 0.552 +/- 0.028 (5.1%) | 0.555 | [0.525, 0.586] |
| IBS | 0.182 +/- 0.012 (6.4%) | 0.182 | [0.172, 0.192] |
| AUC dinamica media | -- | 0.584 | [0.536, 0.632] |

### Comparación de modelos (OS, criterio a priori)

| Modelo | C-index CV (CV%) | IBS CV | Boot C-index | IC95% |
|--------|-----------------|--------|-------------|-------|
| Cox PH | 0.600 (7.05%) | 0.182 | 0.599 | [0.567, 0.629] |
| RSF | 0.593 (4.54%) | 0.181 | 0.592 | [0.562, 0.621] |
| XGBoost | 0.549 (5.50%) | 0.187 | 0.552 | [0.523, 0.582] |

**KPI-3 (mejora sobre baseline): NO CUMPLIDO.** Los IC bootstrap de RSF y Cox solapan completamente (diferencia C-index = 0.007). Con n=479 y 7 predictores basales, la superficie de decisión es prácticamente lineal y los modelos no lineales no tienen ventaja en esta cohorte. Se documenta como limitación explícita.

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

**Proporcionalidad:** el test de Schoenfeld detecta violación del supuesto de proporcionalidad en AGE (OS, p=0.030) y B_WEIGHT (OS, p=0.026; PFS, p=0.011). El resto de variables cumplen el supuesto. Esta violación parcial se reporta como limitación; los efectos de esas dos variables pueden variar a lo largo del tiempo de seguimiento.

### Calibración

Curvas de fiabilidad para supervivencia con bandas bootstrap (n=1000) calculadas sobre predicciones OOF. El Brier Score puntual se mantiene por debajo del modelo nulo en todos los horizontes temporales evaluados (44 a 494 dias en OS), con IBS OS = 0.182 IC95% [0.172, 0.191]. El IBS PFS = 0.182 IC95% [0.172, 0.192]. La calibración es moderada y coherente con el nivel de discriminación observado.

Postcalibración (Platt e isotónica) evaluada; mejoras marginales y sin significación estadística frente a los IC bootstrap. Modelo final reportado sin postcalibración por parsimonia (decisión registrada en el Decision log).

### Análisis por subgrupos (factores)

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

**Interpretación:** el rendimiento es consistente entre estratos sin caídas abruptas. La discriminación es menor en ECOG 2 en ambos endpoints (OS: 0.524; PFS: 0.484), coherente con menor heterogeneidad pronóstica cuando el riesgo basal es ya elevado. Los dos brazos de aleatorización muestran rendimientos similares, lo que sugiere transferibilidad del modelo entre estratos de tratamiento al nivel de discriminación alcanzable con estas señales basales.

## 8. Consideraciones éticas

### Advertencia de no uso clínico

El modelo no está validado para uso clínico ni para decisiones individuales de pacientes. Su finalidad es académica y metodológica.

### Equidad y representatividad

El rendimiento se evalúa por subgrupos, incluido el sexo como perspectiva de género (sección 7). La representatividad de la cohorte es limitada: al tratarse de un ensayo con criterios de inclusión y exclusión, varias variables (tipo tumoral, extensión y clase de quimioterapia) son constantes, lo que impide cualquier análisis de equidad sobre esas dimensiones y debe advertirse.

### Privacidad

Datos crudos y derivados a nivel de sujeto no versionados. Análisis de riesgo de reidentificación en tres dimensiones sobre el conjunto sintético generado con CTGAN (SDV >= 1.0, 300 épocas, n=478).

| Dimensión | Valor observado | Umbral preregistrado | Resultado |
|-----------|----------------|---------------------|-----------|
| Membership inference AUC | 0.534 | <= 0.60 | ACEPTADO |
| TPR @ FPR=0.1 | 0.139 | <= 0.20 | ACEPTADO |
| K-anonimidad k=1 (bins 5 años) | 7.32% | < 5.00% | NO ACEPTADO |
| K-anonimidad k<=2 (bins 5 años) | 10.04% | < 10.00% | NO ACEPTADO |
| K-anonimidad k<=5 (bins 5 años) | 20.71% | < 20.00% | NO ACEPTADO |
| DCR_p5 / RRDR_mediana | 0.622 | >= 0.50 | ACEPTADO |

**Evaluación global: NO ACEPTADO** por k-anonimidad con la configuración de cuasi-identificadores preregistrada (bins de edad de 5 años, SEXCD, B_ECOGN). El análisis de sensibilidad con bins de 10 años reduce k1 al 5.44%, k2 al 7.32% y k5 al 11.51% (k2 y k5 pasan el umbral en esa configuración alternativa).

La k-anonimidad depende directamente de la granularidad del binning de edad. Con la configuración preregistrada, un 7.3% de registros sintéticos coincide de forma única con al menos un real en el espacio de cuasi-identificadores, lo cual supera el umbral de protección. El membership inference y la DCR no muestran riesgo de identificación directa, lo que indica que el riesgo reside en la similitud estructural de las combinaciones de atributos, no en la copia literal de registros.

Utilidad TSTR: C-index medio entrenando en sintéticos y evaluando en reales = 0.437 (vs TRTR 0.600 en el mismo esquema). Ratio de utilidad = 72.8%. La reducción de utilidad es coherente con la capacidad limitada de CTGAN para capturar la estructura de correlación de datos clínicos de supervivencia. Los datos sintéticos son exclusivamente para prototipado metodológico y no refuerzan las conclusiones del modelo principal.

### Marco regulatorio

RGPD, LOPDGDD, AI Act y guías de anonimización de la AEPD. Privacidad por diseño y advertencia explícita de no uso clínico.

## 9. Advertencias y recomendaciones

### Limitaciones

- Cohorte de ensayo con criterios de inclusión y exclusión: validez externa limitada.
- Tamaño muestral moderado (n=479).
- Predictores basales únicamente, por control anti-leakage.
- Variables de tipo tumoral, extensión y clase de quimioterapia invariantes por los criterios de inclusión del protocolo, y raza de varianza cero observada: todas constantes en la cohorte y excluidas.
- KPI-3 no cumplido: RSF y XGBoost no mejoran significativamente al Cox proporcional.
- Violación parcial del supuesto de proporcionalidad en AGE (OS) y B_WEIGHT (OS y PFS) según test de Schoenfeld.
- Alta tasa de eventos PFS (92%) limita la información de censura para estimación de la curva de supervivencia.

### Recomendaciones

- Uso exclusivamente metodológico y educativo; no apto para decisiones clínicas.
- Validación externa en una cohorte independiente antes de cualquier interpretación más allá del prototipo (línea futura).
- Explorar extensiones del Cox con efectos dependientes del tiempo para AGE y B_WEIGHT.
- Restringir el uso del conjunto sintético al prototipado, dado que no supera el umbral de k-anonimidad preregistrado y su utilidad TSTR es baja.
