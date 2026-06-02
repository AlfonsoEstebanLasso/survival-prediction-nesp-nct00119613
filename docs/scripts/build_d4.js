// build_d4.js
// Proposito: generar el entregable D4 (paquete de transparencia y gobernanza)
//   en formato .docx, coherente en estilo con la memoria D3.
// Entradas: docs/D4_paquete_transparencia.md (fuente de contenido), docs/model_card.md,
//   docs/decision_log.md y docs/scripts/_style.js (paleta y fuente).
// Salida: output/D4_paquete_transparencia.docx
// Transformaciones: maqueta portada, ficha, indice, y las tres partes del paquete
//   (Parte 1 checklist TRIPOD+AI, Parte 2 Model Card final, Parte 3 analisis de riesgos).
//   No inventa numeros: todos los valores proceden de las fuentes citadas.
// Regla del proyecto: sin guiones largos (em/en) en ningun texto generado.

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  Header, Footer, PageNumber, TableOfContents, SimpleField, PageBreak, VerticalAlign,
} from "docx";
import { FONT, COLORS, TABLE } from "./_style.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..", "..");
const OUT = path.join(ROOT, "output");

// ----------------------------------------------------------------------------
// Helpers de formato (identicos en estilo a build_d3.js)
// ----------------------------------------------------------------------------
const DOUBLE = 480; // interlineado doble
const PLACEHOLDER = "B7791F"; // ambar para avisos

function run(text, opts = {}) {
  return new TextRun({ text, font: FONT, ...opts });
}

function p(content, opts = {}) {
  const children = typeof content === "string" ? [run(content)] : content;
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: DOUBLE, after: 120 },
    children,
    ...opts,
  });
}

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 160 },
    children: [run(text, { bold: true, color: COLORS.blueDark, size: 32 })] });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 120 },
    children: [run(text, { bold: true, color: COLORS.blueDark, size: 26 })] });
}
function h3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 100 },
    children: [run(text, { bold: true, color: COLORS.blueDark, size: 23 })] });
}

function bullet(text) {
  const children = typeof text === "string" ? [run(text)] : text;
  return new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { line: DOUBLE, after: 60 },
    bullet: { level: 0 }, children });
}

// ----------------------------------------------------------------------------
// Tablas con estilo del proyecto (cabecera azul claro, filas alternadas)
// ----------------------------------------------------------------------------
function cell(text, { header = false, alt = false, bold = false, align = AlignmentType.LEFT } = {}) {
  const fill = header ? TABLE.headerFill : (alt ? TABLE.rowFillAlt : TABLE.rowFill);
  return new TableCell({
    shading: { type: ShadingType.CLEAR, color: "auto", fill },
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    children: [new Paragraph({ alignment: align, spacing: { line: 240, after: 0 },
      children: [run(String(text), { bold: header || bold, size: 18,
        color: header ? COLORS.blueDark : COLORS.text })] })],
  });
}

// rows: array de arrays. La primera fila es cabecera.
function table(rows, { aligns = null } = {}) {
  const trs = rows.map((cells, ri) => new TableRow({
    tableHeader: ri === 0,
    children: cells.map((c, ci) => cell(c, {
      header: ri === 0,
      alt: ri > 0 && ri % 2 === 0,
      align: aligns ? aligns[ci] : (ci === 0 ? AlignmentType.LEFT : AlignmentType.CENTER),
    })),
  }));
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" },
      left: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" },
      right: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "D9D9D9" },
      insideVertical: { style: BorderStyle.SINGLE, size: 2, color: "D9D9D9" },
    },
    rows: trs,
  });
}

let tabN = 0;
function tableCaption(textAfter) {
  tabN += 1;
  return new Paragraph({
    style: "Caption",
    spacing: { before: 80, after: 160 },
    alignment: AlignmentType.LEFT,
    children: [
      run("Tabla ", { bold: true, size: 18 }),
      new SimpleField("SEQ Tabla \\* ARABIC", String(tabN)),
      run(". " + textAfter, { size: 18, italics: true }),
    ],
  });
}

function noteBox(lines) {
  const paras = lines.map((t, i) => new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: 300, after: i === lines.length - 1 ? 0 : 80 },
    children: typeof t === "string" ? [run(t, { size: 20 })] : t,
  }));
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: {
      top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE },
      right: { style: BorderStyle.NONE }, insideHorizontal: { style: BorderStyle.NONE },
      left: { style: BorderStyle.SINGLE, size: 24, color: COLORS.blueDark },
    },
    rows: [new TableRow({ children: [new TableCell({
      shading: { type: ShadingType.CLEAR, color: "auto", fill: COLORS.blueLight },
      margins: { top: 120, bottom: 120, left: 160, right: 160 },
      children: paras,
    })] })],
  });
}

function footerParagraph() {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({
      font: FONT, size: 16,
      children: ["Página ", PageNumber.CURRENT, " de ", PageNumber.TOTAL_PAGES],
    })],
  });
}

// Alineaciones reutilizadas
const A_TRIPOD = [AlignmentType.LEFT, AlignmentType.CENTER, AlignmentType.CENTER];
const A_RISK = [AlignmentType.LEFT, AlignmentType.LEFT, AlignmentType.LEFT, AlignmentType.LEFT, AlignmentType.LEFT, AlignmentType.LEFT];

// ============================================================================
// CONTENIDO
// ============================================================================
const children = [];
const A = (...xs) => xs.forEach((x) => children.push(x));

// ---- PORTADA ----------------------------------------------------------------
A(
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 1200, after: 200 },
    children: [run("Universitat Oberta de Catalunya (UOC)", { bold: true, size: 28, color: COLORS.blueDark })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [run("Grado en Ciencia de Datos Aplicada", { size: 24, color: COLORS.blueDark })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 },
    children: [run("Trabajo Final de Grado", { size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 400, after: 300 },
    children: [run("Paquete de transparencia y gobernanza", { bold: true, size: 40, color: COLORS.blueDark })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 },
    children: [run("Entregable D4: checklist TRIPOD+AI, Model Card final y analisis de riesgos", { size: 24, italics: true, color: "555555" })] }),
);
A(table([
  ["Campo", "Valor"],
  ["Estudiante", "Alfonso Esteban Lasso"],
  ["Tutor de TF", "Tutor del TFG"],
  ["Titulo del trabajo", "Prediccion de respuesta a farmacos quimioterapeuticos a partir de datos clinicos anonimizados"],
  ["Fecha de cierre", "2026-06-01"],
  ["Idioma del trabajo", "Castellano"],
]));
A(new Paragraph({ children: [new PageBreak()] }));

// ---- PRESENTACION E INDICE ---------------------------------------------------
A(h1("Presentacion del documento"));
A(p("Este documento es autocontenido y reune tres partes: (1) el checklist de reporte transparente TRIPOD+AI con referencia cruzada a la memoria D3; (2) la Model Card final del modelo; y (3) el analisis de riesgos del proyecto, del modelo y de la privacidad. Todos los valores proceden de los artefactos del pipeline (carpeta output) y de la documentacion viva del proyecto (decision_log y model_card). No se introduce ningun valor que no figure en esas fuentes."));
A(noteBox([
  [run("Nota sobre derechos de autor: ", { bold: true, size: 20 }),
   run("el checklist TRIPOD+AI (Collins y colaboradores, 2024, BMJ 385:e078378) es material protegido por copyright. En la Parte 1 no se reproduce el texto literal de los items ni las tablas oficiales. Cada item se parafrasea de forma breve y original, con la unica finalidad de documentar el cumplimiento del estudio.", { size: 20 })],
]));
A(h1("Indice de contenido"));
A(new TableOfContents("Indice de contenido", { hyperlink: true, headingStyleRange: "1-2" }));
A(noteBox([
  [run("Aviso: ", { bold: true, color: PLACEHOLDER, size: 20 }),
   run("el indice y los numeros de tabla se generan mediante campos de Word. Tras abrir el documento, selecciona todo (Ctrl+E) y pulsa F9 para actualizar los campos y la paginacion.", { size: 20 })],
]));
A(new Paragraph({ children: [new PageBreak()] }));

// ============================================================================
// PARTE 1. CHECKLIST TRIPOD+AI
// ============================================================================
A(h1("Parte 1. Checklist TRIPOD+AI con referencia cruzada a D3"));

A(h2("1.1 Naturaleza del estudio y alcance de la validacion"));
A(p("Se declara de entrada que este trabajo es un estudio de DESARROLLO de un modelo pronostico, con validacion interna mediante validacion cruzada estratificada k=5 y bootstrap de n=1000. No se realiza validacion externa en una cohorte independiente. En consecuencia, todos los items relativos a validacion externa se marcan como No aplica o como linea futura, de forma explicita y honesta. Esta limitacion se recoge tambien en la Parte 2 (Model Card) y en la Parte 3 (analisis de riesgos)."));
A(p([run("Leyenda de estado: ", { bold: true }), run("Cumplido (el item se aborda en D3), Parcial (se aborda de forma incompleta o con matices), No aplica (no procede por el alcance del estudio).")]));
A(p("El indice de la memoria D3 al que se hace referencia es: 1.1 contexto; 1.2 objetivos; 1.3 impacto CCEG; 1.4 enfoque; 1.5 planificacion; 1.6 productos; 1.7 otros capitulos; 1.8 declaracion de IA; 2.1 datos y cohorte; 2.2 diseno y control de fugas; 2.3 modelos; 2.4 metricas; 2.5 privacidad y sinteticos; 2.6 reproducibilidad; 2.7 valoracion economica; 3.1 comparativa y seleccion; 3.2 modelo final OS y PFS; 3.3 calibracion; 3.4 interpretabilidad; 3.5 robustez y subgrupos; 3.6 datos sinteticos; 4.1 conclusiones; 4.2 objetivos; 4.3 planificacion; 4.4 impactos; 4.5 lineas futuras."));

A(h2("1.2 Titulo y resumen"));
A(table([
  ["Item (parafraseado)", "Estado", "Seccion D3"],
  ["El titulo identifica que el trabajo desarrolla un modelo de prediccion de supervivencia y senala la poblacion oncologica.", "Cumplido", "Portada y 1.1"],
  ["El resumen recoge objetivo, datos, metodos, resultados principales y conclusiones, e indica que se trata de un prototipo no clinico.", "Cumplido", "Ficha (resumen y abstract)"],
], { aligns: A_TRIPOD }));

A(h2("1.3 Introduccion"));
A(table([
  ["Item (parafraseado)", "Estado", "Seccion D3"],
  ["Se explica el contexto clinico, la variabilidad de respuesta a la quimioterapia y por que un modelo pronostico es pertinente.", "Cumplido", "1.1"],
  ["Se justifica el enfoque metodologico de prototipo reproducible frente a uno orientado a la complejidad.", "Cumplido", "1.1, 1.4"],
  ["Se enuncian los objetivos general y especificos (O1 a O6) con sus criterios de exito (KPI).", "Cumplido", "1.2"],
], { aligns: A_TRIPOD }));

A(h2("1.4 Metodos"));
A(table([
  ["Item (parafraseado)", "Estado", "Seccion D3"],
  ["Se describe la fuente de datos (estudio NESP-Oncology-20010145, NCT00119613, Project Data Sphere) y el cambio documentado de fuente respecto de la propuesta inicial.", "Cumplido", "2.1"],
  ["Se indica el diseno del estudio (desarrollo con validacion interna) y la ventana temporal basal del seguimiento.", "Cumplido", "2.1, 2.2"],
  ["Se detallan los participantes y los criterios de la cohorte (479 sujetos, una fila por sujeto).", "Cumplido", "2.1"],
  ["Se definen los desenlaces OS (a partir de DTH y DTHDY) y PFS (a partir de PFSCD y PFSDY), con censura y codificacion 1 evento, 0 censura.", "Cumplido", "2.1, 2.4"],
  ["Se especifican los siete predictores basales (AGE, SEXCD, B_ECOGN, B_WEIGHT, CADIAGM, B_HGB, MEDHX_N) y la derivacion de MEDHX_N.", "Cumplido", "2.1"],
  ["Se documenta el control de variables posteriores al desenlace: exclusion de ficheros longitudinales y post-basales para evitar fuga.", "Cumplido", "2.2"],
  ["Se justifica el tamano muestral (n=479) y la validacion adaptada (k=5 estratificada con bootstrap de n=1000).", "Cumplido", "2.1, 2.2"],
  ["Se describe el tratamiento de datos faltantes con imputacion ajustada dentro de cada particion de entrenamiento.", "Cumplido", "2.1, 2.2"],
  ["Se detallan los metodos de analisis: Cox, RSF y XGBoost, validacion cruzada estratificada, bootstrap, criterio de seleccion a priori y control de fugas.", "Cumplido", "2.2, 2.3"],
  ["Se describe la salida del modelo (funcion de riesgo y supervivencia) y la interpretacion mediante hazard ratios.", "Cumplido", "2.3, 3.4"],
  ["Se especifican las metricas de evaluacion (C-index, IBS, Brier dependiente del tiempo, AUC dependiente del tiempo y calibracion con bandas).", "Cumplido", "2.4"],
  ["Se aborda la validacion externa en una cohorte independiente.", "No aplica (linea futura)", "4.5"],
], { aligns: A_TRIPOD }));

A(h2("1.5 Componente especifico de inteligencia artificial y aprendizaje automatico"));
A(table([
  ["Item (parafraseado)", "Estado", "Seccion D3"],
  ["Se identifica el tipo de modelos empleados (un modelo estadistico de riesgos proporcionales y dos modelos de aprendizaje automatico de supervivencia).", "Cumplido", "2.3"],
  ["Se indican el software y las versiones de las herramientas utilizadas.", "Cumplido", "2.6"],
  ["Se documentan las semillas fijas y las condiciones de reproducibilidad.", "Cumplido", "2.6"],
  ["Se evalua el rendimiento por subgrupos y la equidad del desempeno, incluido el sexo como perspectiva de genero.", "Cumplido", "3.5"],
  ["Se describe el procedimiento de ajuste de hiperparametros dentro del esquema de validacion.", "Parcial", "2.2, 2.3"],
  ["Se valora el riesgo de sesgo y la robustez del modelo entre estratos.", "Cumplido", "3.5"],
], { aligns: A_TRIPOD }));

A(h2("1.6 Ciencia abierta y disponibilidad"));
A(table([
  ["Item (parafraseado)", "Estado", "Seccion D3"],
  ["Se indica la disponibilidad del codigo en el repositorio del pipeline (entregable D1).", "Cumplido", "2.6, anexo 7.2"],
  ["Se aclara que los datos a nivel de sujeto no se comparten por privacidad por diseno y que solo se publican metadatos.", "Cumplido", "2.5, 2.6"],
  ["Se incluye la declaracion sobre el uso de herramientas de inteligencia artificial generativa.", "Cumplido", "1.8"],
  ["Se declara el protocolo o registro previo del estudio.", "Parcial", "2.2 (criterios a priori)"],
], { aligns: A_TRIPOD }));

A(h2("1.7 Resultados"));
A(table([
  ["Item (parafraseado)", "Estado", "Seccion D3"],
  ["Se describe el flujo de participantes y el numero de eventos (OS: 397 eventos; PFS: 440 eventos sobre n=479).", "Cumplido", "2.1, 3.2"],
  ["Se presenta la comparativa de modelos bajo el criterio fijado a priori.", "Cumplido", "3.1"],
  ["Se identifica el modelo final (Cox proporcional por parsimonia) y su justificacion.", "Cumplido", "3.1"],
  ["Se reporta el rendimiento (C-index, IBS, AUC dependiente del tiempo) con intervalos de confianza.", "Cumplido", "3.2"],
  ["Se presenta la calibracion con bandas bootstrap en varios horizontes temporales.", "Cumplido", "3.3"],
  ["Se aporta la interpretabilidad mediante hazard ratios y el test de proporcionalidad.", "Cumplido", "3.4"],
  ["Se analiza la robustez por subgrupos.", "Cumplido", "3.5"],
  ["Se documentan los datos sinteticos y su evaluacion de utilidad y riesgo.", "Cumplido", "3.6"],
], { aligns: A_TRIPOD }));

A(h2("1.8 Discusion"));
A(table([
  ["Item (parafraseado)", "Estado", "Seccion D3"],
  ["Se discuten las limitaciones: validez externa limitada por tratarse de una cohorte de ensayo.", "Cumplido", "4.1, 4.2"],
  ["Se reconoce el tamano muestral moderado (n=479).", "Cumplido", "4.2"],
  ["Se reporta de forma honesta que el KPI-3 (mejora sobre baseline) no se cumple.", "Cumplido", "3.1, 4.2"],
  ["Se documenta la violacion parcial del supuesto de proporcionalidad en AGE y B_WEIGHT.", "Cumplido", "3.4"],
  ["Se senala que el endpoint PFS es poco informativo con estos predictores.", "Cumplido", "3.2"],
  ["Se aclara que la interpretacion de las asociaciones es descriptiva y no causal.", "Cumplido", "3.4"],
  ["Se incluye la advertencia explicita de no uso clinico.", "Cumplido", "1.1, Model Card"],
  ["Se interpretan los resultados en el contexto de la evidencia disponible y su implicacion practica como prototipo.", "Cumplido", "4.1, 4.4"],
], { aligns: A_TRIPOD }));

A(h2("1.9 Otra informacion"));
A(table([
  ["Item (parafraseado)", "Estado", "Seccion D3"],
  ["Se declara la financiacion del trabajo: ninguna.", "Cumplido", "Otra informacion (este documento)"],
  ["Se declaran los conflictos de interes: ninguno.", "Cumplido", "Otra informacion (este documento)"],
  ["Se confirma la ausencia de mencion a centros externos de colaboracion.", "Cumplido", "Todo el documento"],
], { aligns: A_TRIPOD }));
A(p("Financiacion: el trabajo no ha recibido financiacion. Conflictos de interes: el autor declara no tener ningun conflicto de interes. No existe ninguna entidad externa de colaboracion asociada al trabajo."));
A(new Paragraph({ children: [new PageBreak()] }));

// ============================================================================
// PARTE 2. MODEL CARD FINAL
// ============================================================================
A(h1("Parte 2. Model Card final"));
A(noteBox([
  [run("Nota sobre la fuente canonica: ", { bold: true, size: 20 }),
   run("la version viva y de referencia de la Model Card es el fichero docs/model_card.md, cerrado en el Sprint 8 con los valores reales del pipeline. El contenido que sigue reproduce esa fuente sin alterar ningun valor. En caso de discrepancia, prevalece docs/model_card.md.", { size: 20 })],
]));

A(h2("2.1 Uso previsto"));
A(p("Prototipo de investigacion y validacion metodologica para predecir supervivencia (OS y PFS) bajo quimioterapia a partir de variables clinicas basales. Publico: perfiles de ciencia de datos biomedica y equipos de I+D. No es un dispositivo clinico."));

A(h2("2.2 Advertencia de no uso clinico"));
A(p([run("El modelo no esta validado para uso clinico ni para decisiones individuales de pacientes. Su finalidad es academica y metodologica.", { bold: true })]));

A(h2("2.3 Poblacion y datos"));
A(bullet("Cohorte: estudio NESP-Oncology-20010145 (NCT00119613), Project Data Sphere. Ensayo de fase III, aleatorizado, doble ciego y controlado con placebo, en pacientes con cancer de pulmon microcitico (de celulas pequenas) en estadio extenso, no tratados previamente, que reciben quimioterapia con platino y etoposido (darbepoetina alfa frente a placebo). Se reformula como pronostico de supervivencia y no estudia el efecto del agente del estudio."));
A(bullet("n = 479 sujetos (una fila por sujeto). El protocolo planifico aproximadamente 600 sujetos (unos 300 por brazo, con analisis final previsto a las 496 muertes); la cohorte disponible comprende 479. Eventos OS: 397 (83%); censurados: 82 (17%). Eventos PFS: 440 (92%); censurados: 39 (8%)."));
A(bullet("Brazo de aleatorizacion NESP/placebo usado como estratificacion, no como predictor."));
A(bullet("Predictores (Estrategia 1): AGE, SEXCD, B_ECOGN, B_WEIGHT, CADIAGM, B_HGB, MEDHX_N."));
A(bullet("Endpoints: OS (DTH, DTHDY) y PFS (PFSCD, PFSDY)."));

A(h2("2.4 Modelo"));
A(bullet("Baseline: Cox proporcional."));
A(bullet("Candidatos: Random Survival Forest y XGBoost/LightGBM con perdida de supervivencia."));
A(bullet("Seleccion por criterio a priori: C-index mas IBS mas coeficiente de variacion entre folds."));
A(bullet([run("Modelo final: Cox proporcional (parsimonia). ", { bold: true }), run("Ningun candidato mejora significativamente el baseline segun el criterio fijado a priori. Los IC bootstrap se solapan completamente entre Cox y RSF.")]));

A(h2("2.5 Metricas del modelo final (Cox proporcional)"));
A(p("Todas las metricas se calculan sobre predicciones OOF (out-of-fold) del CV k=5 para evitar sobreajuste."));
A(h3("OS (endpoint primario)"));
A(table([
  ["Metrica", "CV k=5 media +/- std (CV%)", "Bootstrap n=1000", "IC95% bootstrap"],
  ["C-index", "0.600 +/- 0.042 (7.1%)", "0.599", "[0.567, 0.629]"],
  ["IBS", "0.182 +/- 0.013 (7.2%)", "0.182", "[0.172, 0.191]"],
  ["AUC dinamica media", "--", "0.645", "[0.601, 0.690]"],
]));
A(tableCaption("Metricas del modelo final en OS (endpoint primario)."));
A(p("Detalle por fold (OS): fold 1 = 0.528, fold 2 = 0.614, fold 3 = 0.635, fold 4 = 0.623, fold 5 = 0.599."));
A(h3("PFS (endpoint secundario)"));
A(table([
  ["Metrica", "CV k=5 media +/- std (CV%)", "Bootstrap n=1000", "IC95% bootstrap"],
  ["C-index", "0.552 +/- 0.028 (5.1%)", "0.555", "[0.525, 0.586]"],
  ["IBS", "0.182 +/- 0.012 (6.4%)", "0.182", "[0.172, 0.192]"],
  ["AUC dinamica media", "--", "0.584", "[0.536, 0.632]"],
]));
A(tableCaption("Metricas del modelo final en PFS (endpoint secundario)."));
A(h3("Comparacion de modelos (OS, criterio a priori)"));
A(table([
  ["Modelo", "C-index CV (CV%)", "IBS CV", "Boot C-index", "IC95%"],
  ["Cox PH", "0.600 (7.05%)", "0.182", "0.599", "[0.567, 0.629]"],
  ["RSF", "0.593 (4.54%)", "0.181", "0.592", "[0.562, 0.621]"],
  ["XGBoost", "0.549 (5.50%)", "0.187", "0.552", "[0.523, 0.582]"],
]));
A(tableCaption("Comparacion de modelos en OS bajo el criterio de seleccion a priori."));
A(p([run("KPI-3 (mejora sobre baseline): NO CUMPLIDO. ", { bold: true }), run("Los IC bootstrap de RSF y Cox solapan completamente (diferencia C-index = 0.007). Con n=479 y 7 predictores basales, la superficie de decision es practicamente lineal y los modelos no lineales no tienen ventaja en esta cohorte. Se documenta como limitacion explicita.")]));

A(h2("2.6 Coeficientes y hazard ratios (Cox proporcional)"));
A(h3("OS"));
A(table([
  ["Variable", "HR", "IC95%", "p"],
  ["Edad (por ano)", "1.006", "[0.993, 1.019]", "0.347"],
  ["Peso basal (por kg)", "0.994", "[0.987, 1.002]", "0.130"],
  ["Tiempo desde diag. (por mes)", "0.969", "[0.877, 1.070]", "0.536"],
  ["Hemoglobina basal (por g/dL)", "0.979", "[0.890, 1.077]", "0.666"],
  ["N. sistemas comorbilidad", "1.086", "[1.003, 1.177]", "0.042 (*)"],
  ["Sexo = 1 vs 0", "0.641", "[0.514, 0.799]", "< 0.001 (***)"],
  ["B_ECOGN = 2 vs 1 (referencia)", "1.693", "[1.326, 2.160]", "< 0.001 (***)"],
]));
A(tableCaption("Hazard ratios del modelo final en OS."));
A(h3("PFS"));
A(table([
  ["Variable", "HR", "IC95%", "p"],
  ["Edad (por ano)", "1.007", "[0.994, 1.019]", "0.292"],
  ["Peso basal (por kg)", "0.998", "[0.991, 1.005]", "0.527"],
  ["Tiempo desde diag. (por mes)", "0.941", "[0.853, 1.038]", "0.221"],
  ["Hemoglobina basal (por g/dL)", "0.970", "[0.886, 1.062]", "0.516"],
  ["N. sistemas comorbilidad", "1.034", "[0.956, 1.118]", "0.407"],
  ["Sexo = 1 vs 0", "0.779", "[0.634, 0.958]", "0.018 (*)"],
  ["B_ECOGN = 2 vs 1 (referencia)", "1.432", "[1.132, 1.811]", "0.003 (**)"],
]));
A(tableCaption("Hazard ratios del modelo final en PFS."));
A(p("Interpretacion clinica descriptiva: el estado funcional reducido (ECOG 2) y el mayor numero de sistemas con comorbilidad se asocian con mayor riesgo de muerte (OS). El sexo femenino (SEXCD=1) se asocia con menor riesgo en ambos endpoints, coherente con la literatura general en cancer de pulmon. Las asociaciones son descriptivas, no causales."));
A(p([run("Proporcionalidad: ", { bold: true }), run("el test de Schoenfeld detecta violacion del supuesto de proporcionalidad en AGE (OS, p=0.030) y B_WEIGHT (OS, p=0.026; PFS, p=0.011). El resto de variables cumplen el supuesto. Esta violacion parcial se reporta como limitacion; los efectos de esas dos variables pueden variar a lo largo del tiempo de seguimiento.")]));

A(h2("2.7 Calibracion"));
A(p("Curvas de fiabilidad para supervivencia con bandas bootstrap (n=1000) calculadas sobre predicciones OOF. El Brier Score puntual se mantiene por debajo del modelo nulo en todos los horizontes temporales evaluados (44 a 494 dias en OS), con IBS OS = 0.182 IC95% [0.172, 0.191]. El IBS PFS = 0.182 IC95% [0.172, 0.192]. La calibracion es moderada y coherente con el nivel de discriminacion observado."));
A(p("Postcalibracion (Platt e isotonica) evaluada; mejoras marginales y sin significacion estadistica frente a los IC bootstrap. Modelo final reportado sin postcalibracion por parsimonia (decision registrada en el Decision log)."));

A(h2("2.8 Sesgos y subgrupos"));
A(h3("Subgrupos OS (Bootstrap IC95%)"));
A(table([
  ["Subgrupo", "n", "Eventos", "C-index", "IC95%", "IBS"],
  ["Global", "479", "397", "0.599", "[0.569, 0.630]", "0.182"],
  ["Brazo NESP (TXG=1)", "240", "205", "0.587", "[0.542, 0.629]", "0.186"],
  ["Brazo placebo (TXG=0)", "239", "192", "0.611", "[0.564, 0.655]", "0.177"],
  ["ECOG 1", "379", "306", "0.574", "[0.537, 0.607]", "0.178"],
  ["ECOG 2", "100", "91", "0.524", "[0.453, 0.593]", "0.193"],
  ["Comorbilidades bajas (MEDHX_N <= 1)", "253", "206", "0.601", "[0.561, 0.642]", "0.178"],
  ["Comorbilidades altas (MEDHX_N > 1)", "226", "191", "0.591", "[0.546, 0.637]", "0.186"],
  ["Sexo = 0", "315", "266", "0.595", "[0.555, 0.637]", "0.173"],
  ["Sexo = 1", "164", "131", "0.586", "[0.530, 0.644]", "0.197"],
  ["Edad < 61 anos", "225", "182", "0.570", "[0.519, 0.616]", "0.172"],
  ["Edad >= 61 anos", "254", "215", "0.583", "[0.542, 0.624]", "0.190"],
  ["Tiempo desde diag. < mediana (0.49 m)", "219", "187", "0.599", "[0.553, 0.645]", "0.190"],
  ["Tiempo desde diag. >= mediana (0.49 m)", "260", "210", "0.599", "[0.555, 0.640]", "0.174"],
], { aligns: [AlignmentType.LEFT, AlignmentType.CENTER, AlignmentType.CENTER, AlignmentType.CENTER, AlignmentType.CENTER, AlignmentType.CENTER] }));
A(tableCaption("Rendimiento por subgrupos en OS."));
A(h3("Subgrupos PFS (Bootstrap IC95%)"));
A(table([
  ["Subgrupo", "n", "Eventos", "C-index", "IC95%", "IBS"],
  ["Global", "479", "440", "0.555", "[0.525, 0.585]", "0.183"],
  ["Brazo NESP (TXG=1)", "240", "221", "0.536", "[0.490, 0.575]", "0.187"],
  ["Brazo placebo (TXG=0)", "239", "219", "0.572", "[0.526, 0.616]", "0.178"],
  ["ECOG 1", "379", "345", "0.528", "[0.492, 0.562]", "0.181"],
  ["ECOG 2", "100", "95", "0.484", "[0.420, 0.550]", "0.190"],
  ["Comorbilidades bajas (MEDHX_N <= 1)", "253", "233", "0.556", "[0.511, 0.603]", "0.188"],
  ["Comorbilidades altas (MEDHX_N > 1)", "226", "207", "0.545", "[0.498, 0.590]", "0.177"],
  ["Sexo = 0", "315", "291", "0.537", "[0.499, 0.579]", "0.180"],
  ["Sexo = 1", "164", "149", "0.541", "[0.484, 0.598]", "0.189"],
  ["Edad < 61 anos", "225", "202", "0.516", "[0.471, 0.560]", "0.182"],
  ["Edad >= 61 anos", "254", "238", "0.564", "[0.518, 0.606]", "0.184"],
  ["Tiempo desde diag. < mediana (0.49 m)", "219", "206", "0.531", "[0.486, 0.578]", "0.189"],
  ["Tiempo desde diag. >= mediana (0.49 m)", "260", "234", "0.572", "[0.528, 0.616]", "0.177"],
], { aligns: [AlignmentType.LEFT, AlignmentType.CENTER, AlignmentType.CENTER, AlignmentType.CENTER, AlignmentType.CENTER, AlignmentType.CENTER] }));
A(tableCaption("Rendimiento por subgrupos en PFS."));
A(p("Interpretacion: el rendimiento es consistente entre estratos sin caidas abruptas. La discriminacion es menor en ECOG 2 en ambos endpoints (OS: 0.524; PFS: 0.484), coherente con menor heterogeneidad pronostica cuando el riesgo basal es ya elevado. Los dos brazos de aleatorizacion muestran rendimientos similares, lo que sugiere transferibilidad del modelo entre estratos de tratamiento al nivel de discriminacion alcanzable con estas senales basales."));

A(h2("2.9 Limitaciones"));
A(bullet("Cohorte de ensayo con criterios de inclusion y exclusion: validez externa limitada."));
A(bullet("Tamano muestral moderado (n=479)."));
A(bullet("Predictores basales unicamente, por control anti-leakage."));
A(bullet("Variables de tipo tumoral, extension y clase de quimioterapia invariantes por los criterios de inclusion del protocolo, y raza de varianza cero observada: todas constantes en la cohorte y excluidas."));
A(bullet("KPI-3 no cumplido: RSF y XGBoost no mejoran significativamente al Cox proporcional."));
A(bullet("Violacion parcial del supuesto de proporcionalidad en AGE (OS) y B_WEIGHT (OS y PFS) segun test de Schoenfeld."));
A(bullet("Alta tasa de eventos PFS (92%) limita la informacion de censura para estimacion de la curva de supervivencia."));

A(h2("2.10 Privacidad"));
A(p("Datos crudos y derivados a nivel de sujeto no versionados. Analisis de riesgo de reidentificacion en tres dimensiones sobre el conjunto sintetico generado con CTGAN (SDV >= 1.0, 300 epocas, n=478)."));
A(table([
  ["Dimension", "Valor observado", "Umbral preregistrado", "Resultado"],
  ["Membership inference AUC", "0.534", "<= 0.60", "ACEPTADO"],
  ["TPR @ FPR=0.1", "0.139", "<= 0.20", "ACEPTADO"],
  ["K-anonimidad k=1 (bins 5 anos)", "7.32%", "< 5.00%", "NO ACEPTADO"],
  ["K-anonimidad k<=2 (bins 5 anos)", "10.04%", "< 10.00%", "NO ACEPTADO"],
  ["K-anonimidad k<=5 (bins 5 anos)", "20.71%", "< 20.00%", "NO ACEPTADO"],
  ["DCR_p5 / RRDR_mediana", "0.622", ">= 0.50", "ACEPTADO"],
], { aligns: [AlignmentType.LEFT, AlignmentType.CENTER, AlignmentType.CENTER, AlignmentType.CENTER] }));
A(tableCaption("Resultados del analisis de riesgo de reidentificacion sobre el conjunto sintetico."));
A(p([run("Evaluacion global: NO ACEPTADO ", { bold: true }), run("por k-anonimidad con la configuracion de cuasi-identificadores preregistrada (bins de edad de 5 anos, SEXCD, B_ECOGN). El analisis de sensibilidad con bins de 10 anos reduce k1 al 5.44%, k2 al 7.32% y k5 al 11.51% (k2 y k5 pasan el umbral en esa configuracion alternativa).")]));
A(p("Interpretacion: la k-anonimidad depende directamente de la granularidad del binning de edad. Con la configuracion preregistrada, un 7.3% de registros sinteticos coincide de forma unica con al menos un real en el espacio de cuasi-identificadores, lo cual supera el umbral de proteccion. El membership inference y la DCR no muestran riesgo de identificacion directa, lo que indica que el riesgo reside en la similitud estructural de las combinaciones de atributos, no en la copia literal de registros."));
A(p("Utilidad TSTR: C-index medio entrenando en sinteticos y evaluando en reales = 0.437 (vs TRTR 0.600 en el mismo esquema). Ratio de utilidad = 72.8%. La reduccion de utilidad es coherente con la capacidad limitada de CTGAN para capturar la estructura de correlacion de datos clinicos de supervivencia."));
A(p("Los datos sinteticos son exclusivamente para prototipado metodologico y no refuerzan las conclusiones del modelo principal. Marco regulatorio: RGPD, LOPDGDD, AI Act y guias de anonimizacion de la AEPD."));
A(new Paragraph({ children: [new PageBreak()] }));

// ============================================================================
// PARTE 3. ANALISIS DE RIESGOS
// ============================================================================
A(h1("Parte 3. Analisis de riesgos"));
A(p("Escalas: probabilidad e impacto se valoran como Baja, Media o Alta. La columna de estado al cierre resume la situacion real al final del trabajo (2026-06-01)."));

A(h2("3.1 Riesgos del proyecto (propuesta y PEC1)"));
A(table([
  ["Riesgo", "Probabilidad", "Impacto", "Senal temprana", "Mitigacion", "Estado al cierre"],
  ["Etiquetas de respuesta inadecuadas o incompletas (RECIST y ORR)", "Alta", "Alto", "Alto porcentaje de valores faltantes en la respuesta directa durante la auditoria de la cohorte", "Reformulacion del problema a supervivencia con censura (pivote P1), que aprovecha la informacion temporal del seguimiento", "Materializado y resuelto: motivo el pivote P1, registrado en el Decision log"],
  ["Heterogeneidad de tumor y de terapia en la cohorte", "Media", "Medio", "Variabilidad clinica entre subgrupos y presencia del brazo de aleatorizacion", "Uso del brazo NESP/placebo como variable de estratificacion y analisis de transferibilidad entre estratos", "Mitigado: rendimiento consistente entre brazos (seccion 3.5 de D3)"],
  ["Desbalanceo de clases en una tarea de clasificacion binaria", "Media", "Medio", "Distribucion desigual de la etiqueta de respuesta", "Reformulacion a supervivencia con censura, que elimina la dependencia de un umbral de clase", "Mitigado: el problema se trata como tiempo hasta evento"],
  ["Fuga de informacion (leakage) en el preprocesado o por variables post-outcome", "Media", "Alto", "Rendimiento inusualmente alto o inestable entre particiones", "Preprocesado ajustado dentro de cada particion de entrenamiento y exclusion de ficheros longitudinales y post-basales", "Mitigado: estabilidad entre folds coherente (CV% bajo), sin indicios de fuga"],
  ["Privacidad y riesgo de reidentificacion de datos de salud", "Media", "Alto", "Datos a nivel de sujeto potencialmente identificables", "Privacidad por diseno: datos crudos y derivados no versionados, solo metadatos; analisis de reidentificacion en tres dimensiones", "Mitigado en lo organizativo; el conjunto sintetico queda como NO ACEPTADO por k-anonimidad (ver categoria 3.3)"],
  ["Sobrecoste por ampliacion del alcance", "Media", "Medio", "Acumulacion de tareas fuera del plan de sprints", "Planificacion por sprints, criterios a priori y principio de parsimonia para acotar el alcance", "Controlado: alcance estable, sin dependencia de nube ni de licencias"],
], { aligns: A_RISK }));
A(tableCaption("Riesgos del proyecto y su estado al cierre."));

A(h2("3.2 Riesgos del modelo en uso (no clinico)"));
A(table([
  ["Riesgo", "Probabilidad", "Impacto", "Senal temprana", "Mitigacion", "Estado al cierre"],
  ["Calibracion que subestima la supervivencia a largo plazo en pacientes de alto riesgo (t=355 dias)", "Media", "Medio", "Deciles de alto riesgo con supervivencia observada por encima de la predicha en el horizonte largo", "Reporte explicito de la tendencia, advertencia de no uso clinico y propuesta de extensiones dependientes del tiempo como linea futura", "Documentado en 3.3 de D3 y en la Model Card; no se corrige por el caracter de prototipo"],
  ["Discriminacion modesta (C-index OS 0.599; PFS 0.555)", "Alta", "Medio", "Valores de C-index proximos al rango moderado en el desarrollo", "Comunicacion honesta del rendimiento con intervalos de confianza y enfasis en el caracter metodologico", "Documentado en 3.2 de D3; asumido como propio del prototipo"],
  ["Interpretacion causal indebida de los hazard ratios", "Media", "Alto", "Lectura de asociaciones como relaciones causa-efecto", "Advertencia expresa de interpretacion descriptiva y no causal en D3 y en la Model Card", "Mitigado mediante documentacion explicita (3.4 de D3)"],
  ["Validez externa limitada por tratarse de una cohorte de ensayo", "Alta", "Alto", "Criterios de inclusion y exclusion estrictos y baja representatividad poblacional", "Declaracion de estudio de desarrollo sin validacion externa y propuesta de validacion externa como linea futura", "Documentado como limitacion (4.2 y 4.5 de D3)"],
  ["Violacion parcial del supuesto de proporcionalidad (AGE y B_WEIGHT)", "Media", "Medio", "p del test de Schoenfeld por debajo de 0.05 en esas variables", "Reporte de la violacion y de su alcance acotado; las variables de mayor senal cumplen el supuesto", "Documentado en 3.4 de D3 y en la Model Card"],
  ["Endpoint PFS poco informativo con predictores basales", "Alta", "Bajo", "C-index de PFS proximo al azar (0.555) y alta tasa de eventos (92%)", "Reporte de PFS por completitud, con advertencia de su utilidad pronostica marginal", "Documentado en 3.2 de D3"],
], { aligns: A_RISK }));
A(tableCaption("Riesgos del modelo en uso (no clinico) y su estado al cierre."));

A(h2("3.3 Riesgos de privacidad y de uso indebido"));
A(table([
  ["Riesgo", "Probabilidad", "Impacto", "Senal temprana", "Mitigacion", "Estado al cierre"],
  ["El conjunto sintetico resulta NO ACEPTADO por k-anonimidad con bins de edad de 5 anos", "Alta", "Medio", "Fraccion de registros sinteticos con combinacion unica de cuasi-identificadores por encima del umbral (k1 = 7.32%)", "Uso del sintetico solo para prototipado, no publicado; analisis de sensibilidad con bins de 10 anos; triangulacion con membership inference (AUC 0.534) y DCR (ratio 0.622)", "Materializado y gestionado: documentado como NO ACEPTADO, con sensibilidad y triangulacion (3.6 de D3 y Model Card)"],
  ["Interpretacion clinica del prototipo por parte de terceros", "Media", "Alto", "Uso del modelo o de los sinteticos fuera del contexto metodologico", "Advertencia explicita de no uso clinico en D3 y en la Model Card, y restriccion del uso de los sinteticos al prototipado", "Mitigado mediante documentacion y advertencias inequivocas"],
  ["Difusion de datos a nivel de sujeto", "Baja", "Alto", "Inclusion accidental de datos crudos o derivados en el control de versiones", "Privacidad por diseno: exclusion de los datos de sujeto del repositorio, solo metadatos (diccionario, hashes y manifiesto)", "Controlado: no se versionan datos de sujeto"],
], { aligns: A_RISK }));
A(tableCaption("Riesgos de privacidad y de uso indebido, y su estado al cierre."));

A(p([run("Fin del documento D4. ", { bold: true }), run("Fuentes: documentacion interna del proyecto (decision_log y model_card) y artefactos de la carpeta output (ficheros JSON y CSV).")]));

// ============================================================================
// DOCUMENTO
// ============================================================================
const doc = new Document({
  creator: "Alfonso Esteban Lasso",
  title: "Paquete de transparencia y gobernanza (D4) - TFG",
  description: "Entregable D4 - Checklist TRIPOD+AI, Model Card final y analisis de riesgos",
  styles: {
    default: {
      document: { run: { font: FONT, size: 22 } },
    },
    paragraphStyles: [
      { id: "Caption", name: "Caption", basedOn: "Normal", next: "Normal",
        run: { font: FONT, size: 18, italics: true, color: "595959" },
        paragraph: { spacing: { after: 120 } } },
    ],
  },
  sections: [{
    properties: {
      titlePage: true,
      page: { margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } },
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: COLORS.blueDark, space: 4 } },
        children: [run("Universitat Oberta de Catalunya (UOC)  |  Trabajo Final de Grado  |  D4", { size: 16, color: COLORS.blueDark })],
      })] }),
      first: new Header({ children: [new Paragraph({ children: [] })] }),
    },
    footers: {
      default: new Footer({ children: [footerParagraph()] }),
      first: new Footer({ children: [footerParagraph()] }),
    },
    children,
  }],
});

const outFile = path.join(OUT, "D4_paquete_transparencia.docx");
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(outFile, buf);
  console.log("Generado:", outFile);
  console.log("Tablas:", tabN);
});
