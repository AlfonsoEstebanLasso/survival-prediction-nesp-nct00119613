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
