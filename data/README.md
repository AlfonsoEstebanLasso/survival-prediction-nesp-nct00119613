# Datos

Los datos clinicos crudos NO se incluyen en el repositorio (privacidad por diseno).

- Fuente: estudio NESP-Oncology-20010145 (NCT00119613), Project Data Sphere.
- Coloca los ficheros `.sas7bdat` en una carpeta `SAS dataset/` en la raiz del proyecto.
- El ETL (`src/data/etl_nesp_nct00119613.py`) apunta por defecto a esa carpeta.
- Esta carpeta `data/` solo aloja metadatos: diccionario, hashes y manifiesto de calidad.
- Ni los datos crudos ni el dataset derivado a nivel de sujeto se versionan.
