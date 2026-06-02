# Model Card (viva)

Documento vivo desde el Sprint 3. Cerrado en Sprint 8 con valores reales del pipeline (2026-06-01).

## Uso previsto

Prototipo de investigacion y validacion metodologica para predecir supervivencia (OS y PFS) bajo quimioterapia a partir de variables clinicas basales. Publico: perfiles de ciencia de datos biomedica y equipos de I+D. No es un dispositivo clinico.

## Advertencia de no uso clínico

El modelo no esta validado para uso clinico ni para decisiones individuales de pacientes. Su finalidad es academica y metodologica.

## Población y datos

- Cohorte: estudio NESP-Oncology-20010145 (NCT00119613), Project Data Sphere. Ensayo de fase III, aleatorizado, doble ciego y controlado con placebo, en pacientes con cancer de pulmon microcitico (de celulas pequenas) en estadio extenso, no tratados previamente, que reciben quimioterapia con platino y etoposido (darbepoetina alfa frente a placebo). El trabajo lo reformula como pronostico de supervivencia y no estudia el efecto del agente del estudio.
- n = 479 sujetos (una fila por sujeto). El protocolo del ensayo planifico aproximadamente 600 sujetos (unos 300 por brazo, con analisis final previsto a las 496 muertes); la cohorte disponible en Project Data Sphere comprende 479. Eventos OS: 397 (83%); censurados: 82 (17%). Eventos PFS: 440 (92%); censurados: 39 (8%).
- Brazo de aleatorizacion NESP/placebo usado como estratificacion, no como predictor.
- Predictores (Estrategia 1): AGE, SEXCD, B_ECOGN, B_WEIGHT, CADIAGM, B_HGB, MEDHX_N.
- Endpoints: OS (DTH, DTHDY) y PFS (PFSCD, PFSDY).

## Modelo

- Baseline: Cox proporcional.
- Candidatos: Random Survival Forest y XGBoost/LightGBM con perdida de supervivencia.
- Seleccion por criterio a priori: C-index mas IBS mas coeficiente de variacion entre folds.
- **Modelo final: Cox proporcional (parsimonia).** Ningun candidato mejora significativamente el baseline segun el criterio fijado a priori. Los IC bootstrap se solapan completamente entre Cox y RSF.

## Métricas del modelo final (Cox proporcional)

Todas las métricas se calculan sobre predicciones OOF (out-of-fold) del CV k=5 para evitar sobreajuste.

### OS (endpoint primario)

| Métrica | CV k=5 media +/- std (CV%) | Bootstrap n=1000 | IC95% bootstrap |
|---------|---------------------------|-----------------|-----------------|
| C-index | 0.600 +/- 0.042 (7.1%) | 0.599 | [0.567, 0.629] |
| IBS | 0.182 +/- 0.013 (7.2%) | 0.182 | [0.172, 0.191] |
| AUC dinamica media | -- | 0.645 | [0.601, 0.690] |

Detalle por fold (OS): fold 1 = 0.528, fold 2 = 0.614, fold 3 = 0.635, fold 4 = 0.623, fold 5 = 0.599.

### PFS (endpoint secundario)

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

## Coeficientes y hazard ratios (Cox proporcional)

### OS

| Variable | HR | IC95% | p |
|----------|-----|-------|---|
| Edad (por año) | 1.006 | [0.993, 1.019] | 0.347 |
| Peso basal (por kg) | 0.994 | [0.987, 1.002] | 0.130 |
| Tiempo desde diag. (por mes) | 0.969 | [0.877, 1.070] | 0.536 |
| Hemoglobina basal (por g/dL) | 0.979 | [0.890, 1.077] | 0.666 |
| N. sistemas comorbilidad | 1.086 | [1.003, 1.177] | 0.042 (*) |
| Sexo = 1 vs 0 | 0.641 | [0.514, 0.799] | < 0.001 (***) |
| B_ECOGN = 2 vs 1 (referencia) | 1.693 | [1.326, 2.160] | < 0.001 (***) |

### PFS

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

## Calibración:

Curvas de fiabilidad para supervivencia con bandas bootstrap (n=1000) calculadas sobre predicciones OOF. El Brier Score puntual se mantiene por debajo del modelo nulo en todos los horizontes temporales evaluados (44 a 494 dias en OS), con IBS OS = 0.182 IC95% [0.172, 0.191]. El IBS PFS = 0.182 IC95% [0.172, 0.192]. La calibración es moderada y coherente con el nivel de discriminación observado.

Postcalibración (Platt e isotónica) evaluada; mejoras marginales y sin significación estadística frente a los IC bootstrap. Modelo final reportado sin postcalibración por parsimonia (decisión registrada en el Decision log).

## Sesgos y subgrupos:

### Subgrupos OS (Bootstrap IC95%):

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

### Subgrupos PFS (Bootstrap IC95%):

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

**Interpretacion:** el rendimiento es consistente entre estratos sin caidas abruptas. La discriminacion es menor en ECOG 2 en ambos endpoints (OS: 0.524; PFS: 0.484), coherente con menor heterogeneidad pronostica cuando el riesgo basal es ya elevado. Los dos brazos de aleatorización muestran rendimientos similares, lo que sugiere transferibilidad del modelo entre estratos de tratamiento al nivel de discriminación alcanzable con estas señales basales.

## Limitaciones:

- Cohorte de ensayo con criterios de inclusión y exclusión: validez externa limitada.
- Tamaño muestral moderado (n=479).
- Predictores basales únicamente, por control anti-leakage.
- Variables de tipo tumoral, extensión y clase de quimioterapia invariantes por los criterios de inclusión del protocolo, y raza de varianza cero observada: todas constantes en la cohorte y excluidas.
- KPI-3 no cumplido: RSF y XGBoost no mejoran significativamente al Cox proporcional.
- Violación parcial del supuesto de proporcionalidad en AGE (OS) y B_WEIGHT (OS y PFS) segun test de Schoenfeld.
- Alta tasa de eventos PFS (92%) limita la información de censura para estimación de la curva de supervivencia.

## Privacidad:

Datos crudos y derivados a nivel de sujeto no versionados. Análisis de riesgo de reidentificación en tres dimensiones sobre el conjunto sintético generado con CTGAN (SDV >= 1.0, 300 épocas, n=478).

### Resultados del análisis de riesgo (datos sintéticos):

| Dimensión | Valor observado | Umbral preregistrado | Resultado |
|-----------|----------------|---------------------|-----------|
| Membership inference AUC | 0.534 | <= 0.60 | ACEPTADO |
| TPR @ FPR=0.1 | 0.139 | <= 0.20 | ACEPTADO |
| K-anonimidad k=1 (bins 5 años) | 7.32% | < 5.00% | NO ACEPTADO |
| K-anonimidad k<=2 (bins 5 años) | 10.04% | < 10.00% | NO ACEPTADO |
| K-anonimidad k<=5 (bins 5 años) | 20.71% | < 20.00% | NO ACEPTADO |
| DCR_p5 / RRDR_mediana | 0.622 | >= 0.50 | ACEPTADO |

**Evaluación global: NO ACEPTADO** por k-anonimidad con la configuración de cuasi-identificadores preregistrada (bins de edad de 5 años, SEXCD, B_ECOGN). El análisis de sensibilidad con bins de 10 años reduce k1 al 5.44%, k2 al 7.32% y k5 al 11.51% (k2 y k5 pasan el umbral en esa configuración alternativa).

**Interpretacion:** la k-anonimidad depende directamente de la granularidad del binning de edad. Con la configuración preregistrada, un 7.3% de registros sintéticos coincide de forma única con al menos un real en el espacio de cuasi-identificadores, lo cual supera el umbral de protección. El membership inference y la DCR no muestran riesgo de identificación directa, lo que indica que el riesgo reside en la similitud estructural de las combinaciones de atributos, no en la copia literal de registros.

**Utilidad TSTR:** C-index medio entrenando en sintéticos y evaluando en reales = 0.437 (vs TRTR 0.600 en el mismo esquema). Ratio de utilidad = 72.8%. La reducción de utilidad es coherente con la capacidad limitada de CTGAN para capturar la estructura de correlación de datos clinicos de supervivencia.

Los datos sintéticos son exclusivamente para prototipado metodológico y no refuerzan las conclusiones del modelo principal. Marco regulatorio: RGPD, LOPDGDD, AI Act y guias de anonimizacion de la AEPD.
