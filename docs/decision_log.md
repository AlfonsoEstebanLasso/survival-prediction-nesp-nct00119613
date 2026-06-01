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
