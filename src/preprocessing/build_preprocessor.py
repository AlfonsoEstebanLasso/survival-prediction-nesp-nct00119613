"""
Preprocesado contenido dentro de la validacion cruzada (pendiente de implementar).

Contrato (control anti-leakage):
    - Ajustar los transformadores SOLO sobre el fold de entrenamiento.
    - Imputacion: mediana o moda si missingness <= 20 por ciento;
      imputacion iterativa si > 20 por ciento con patron MAR.
    - Estandarizacion de variables numericas.
    - Codificacion one-hot de variables categoricas.
    - Sin fuga de informacion entre train y test.

Entradas previstas:
    - Dataset derivado del ETL (una fila por sujeto).
Salidas previstas:
    - Un objeto de preprocesado (por ejemplo, ColumnTransformer dentro de un Pipeline)
      listo para integrarse en el esquema de validacion del modelado.
"""


def build_preprocessor():
    raise NotImplementedError(
        "Pendiente: implementar el preprocesador segun el contrato del docstring."
    )
