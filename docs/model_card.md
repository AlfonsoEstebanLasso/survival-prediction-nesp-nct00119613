# Model Card (viva)

Documento vivo desde el Sprint 3. Se actualiza en cada sprint y se cierra en el Sprint 7. Los valores marcados como pendiente se completan con los resultados reales del pipeline.

## Uso previsto

Prototipo de investigacion y validacion metodologica para predecir supervivencia (OS y PFS) bajo quimioterapia a partir de variables clinicas basales. Publico: perfiles de ciencia de datos biomedica y equipos de I+D. No es un dispositivo clinico.

## Advertencia de no uso clinico

El modelo no esta validado para uso clinico ni para decisiones individuales de pacientes. Su finalidad es academica y metodologica.

## Poblacion y datos

- Cohorte: estudio NESP-Oncology-20010145 (NCT00119613), Project Data Sphere.
- n = 479 sujetos (una fila por sujeto).
- Brazo de aleatorizacion NESP/placebo usado como estratificacion, no como predictor.
- Predictores (Estrategia 1): AGE, SEXCD, B_ECOGN, B_WEIGHT, CADIAGM, B_HGB, MEDHX_N.
- Endpoints: OS (DTH, DTHDY) y PFS (PFSCD, PFSDY).

## Modelo

- Baseline: Cox proporcional.
- Candidatos: Random Survival Forest y XGBoost/LightGBM con perdida de supervivencia.
- Seleccion por criterio a priori: C-index mas IBS mas estabilidad entre folds.
- Modelo final: pendiente (confirmar con valores reales).

## Metricas (pendiente de valores reales)

- C-index: pendiente.
- IBS: pendiente.
- Brier: pendiente.
- AUC dependiente del tiempo: pendiente.
- Intervalos de confianza por bootstrap (n=1000): pendiente.
- Estabilidad entre folds (coeficiente de variacion): pendiente.

## Calibracion

Curvas de fiabilidad para supervivencia con bandas e IBS estratificado por percentil de tiempo. Postcalibracion (Platt e isotonica) evaluada; decision sobre su uso registrada en el Decision log.

## Sesgos y subgrupos

Rendimiento estratificado por estadio clinico, linea de tratamiento, comorbilidades y brazo NESP/placebo. Discusion de transferibilidad entre estratos. Resultados: pendiente.

## Limitaciones

- Cohorte de ensayo con criterios de inclusion y exclusion: validez externa limitada.
- Tamano muestral moderado (n=479).
- Predictores basales unicamente, por control anti-leakage.
- Variables de raza, tipo tumoral y extension constantes en la cohorte.

## Privacidad

Datos crudos y derivados a nivel de sujeto no versionados. Analisis de riesgo de reidentificacion en tres dimensiones (membership inference, unicidad de cuasi-identificadores, distancia al vecino mas cercano). Marco RGPD, LOPDGDD, AI Act y guias AEPD.
