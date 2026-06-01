// Constantes de estilo compartidas para la generacion de documentos .docx del TFG.
// Importar desde los scripts build_d3.js, build_d4.js, build_d5.js.
// Regla del proyecto: sin guiones largos en ningun texto generado.

export const FONT = "Arial";

export const COLORS = {
  blueDark: "1F4E79",   // azul corporativo oscuro (cabeceras, titulos)
  blueLight: "D5E8F0",  // azul claro (cabecera de tablas, barras laterales)
  green: "1F7A3A",      // estado completo
  amber: "B7791F",      // estado en curso / parcial / borrador
  text: "000000",
  white: "FFFFFF",
};

// Paginacion del pie: "Pagina X de Y".
export const FOOTER_PREFIX = "Pagina ";
export const FOOTER_INFIX = " de ";

// Tablas: cabecera en azul claro y filas alternadas.
export const TABLE = {
  headerFill: COLORS.blueLight,
  rowFillAlt: "F2F7FB",
  rowFill: COLORS.white,
};

// Resumen ejecutivo: barra lateral azul al inicio de cada seccion.
export const EXEC_SUMMARY = {
  sidebarColor: COLORS.blueDark,
};
