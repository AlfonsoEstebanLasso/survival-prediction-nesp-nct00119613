// build_d4.js
// Propósito: generar el entregable D4 (paquete de transparencia y gobernanza)
//   en formato .docx, coherente en estilo con la memoria D3.
// Entradas: docs/D4_paquete_transparencia.md (fuente de contenido), docs/model_card.md,
//   docs/decision_log.md y docs/scripts/_style.js (paleta y fuente).
// Salida: output/D4_paquete_transparencia.docx
// Transformaciones: maqueta portada, ficha, índice, y las tres partes del paquete
//   (Parte 1 checklist TRIPOD+AI, Parte 2 Model Card final, Parte 3 análisis de riesgos).
//   No inventa números: todos los valores proceden de las fuentes citadas.
// Regla del proyecto: sin guiones largos (em/en) en ningún texto generado.

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  Header, Footer, PageNumber, TableOfContents, SimpleField, PageBreak, VerticalAlign,
} from "docx";
import { FONT, COLORS, TABLE } from "./_style.js";
import { renderMarkdownToDocx } from "./_markdown.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..", "..");
const OUT = path.join(ROOT, "output");
const MODEL_CARD_MD = fs.readFileSync(path.join(ROOT, "docs", "model_card.md"), "utf-8");

// ----------------------------------------------------------------------------
// Helpers de formato (idénticos en estilo a build_d3.js)
// ----------------------------------------------------------------------------
const DOUBLE = 480; // interlineado doble
const PLACEHOLDER = "B7791F"; // ámbar para avisos

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
    children: [run("Entregable D4: checklist TRIPOD+AI, Model Card final y análisis de riesgos", { size: 24, italics: true, color: "555555" })] }),
);
A(table([
  ["Campo", "Valor"],
  ["Estudiante", "Alfonso Esteban Lasso"],
  ["Tutor de TF", "Tutor del TFG"],
  ["Título del trabajo", "Predicción de respuesta a fármacos quimioterapéuticos a partir de datos clínicos anonimizados"],
  ["Fecha de cierre", "2026-06-01"],
  ["Idioma del trabajo", "Castellano"],
]));
A(new Paragraph({ children: [new PageBreak()] }));

// ---- PRESENTACIÓN E ÍNDICE ---------------------------------------------------
A(h1("Presentación del documento"));
A(p("Este documento es autocontenido y reune tres partes: (1) el checklist de reporte transparente TRIPOD+AI con referencia cruzada a la memoria D3; (2) la Model Card final del modelo; y (3) el análisis de riesgos del proyecto, del modelo y de la privacidad. Todos los valores proceden de los artefactos del pipeline (carpeta output) y de la documentación viva del proyecto (decision_log y model_card). No se introduce ningún valor que no figure en esas fuentes."));
A(noteBox([
  [run("Nota sobre derechos de autor: ", { bold: true, size: 20 }),
   run("el checklist TRIPOD+AI (Collins y colaboradores, 2024, BMJ 385:e078378) es material protegido por copyright. En la Parte 1 no se reproduce el texto literal de los items ni las tablas oficiales. Cada item se parafrasea de forma breve y original, con la única finalidad de documentar el cumplimiento del estudio.", { size: 20 })],
]));
A(h1("Índice de contenido"));
A(new TableOfContents("Índice de contenido", { hyperlink: true, headingStyleRange: "1-2" }));
A(noteBox([
  [run("Aviso: ", { bold: true, color: PLACEHOLDER, size: 20 }),
   run("el índice y los números de tabla se generan mediante campos de Word. Tras abrir el documento, selecciona todo (Ctrl+E) y pulsa F9 para actualizar los campos y la paginación.", { size: 20 })],
]));
A(new Paragraph({ children: [new PageBreak()] }));

// ============================================================================
// PARTE 1. CHECKLIST TRIPOD+AI
// ============================================================================
A(h1("Parte 1. Checklist TRIPOD+AI con referencia cruzada a D3"));

A(h2("1.1 Naturaleza del estudio y alcance de la validación"));
A(p("Se declara de entrada que este trabajo es un estudio de DESARROLLO de un modelo pronóstico, con validación interna mediante validación cruzada estratificada k=5 y bootstrap de n=1000. No se realiza validación externa en una cohorte independiente. En consecuencia, todos los items relativos a validación externa se marcan como No aplica o como línea futura, de forma explícita y honesta. Esta limitación se recoge también en la Parte 2 (Model Card) y en la Parte 3 (análisis de riesgos)."));
A(p([run("Leyenda de estado: ", { bold: true }), run("Cumplido (el item se aborda en D3), Parcial (se aborda de forma incompleta o con matices), No aplica (no procede por el alcance del estudio).")]));
A(p("El índice de la memoria D3 al que se hace referencia es: 1.1 contexto; 1.2 objetivos; 1.3 impacto CCEG; 1.4 enfoque; 1.5 planificacion; 1.6 productos; 1.7 otros capítulos; 1.8 declaración de IA; 2.1 datos y cohorte; 2.2 diseño y control de fugas; 2.3 modelos; 2.4 métricas; 2.5 privacidad y sintéticos; 2.6 reproducibilidad; 2.7 valoración económica; 3.1 comparativa y selección; 3.2 modelo final OS y PFS; 3.3 calibración; 3.4 interpretabilidad; 3.5 robustez y subgrupos; 3.6 datos sintéticos; 4.1 conclusiones; 4.2 objetivos; 4.3 planificacion; 4.4 impactos; 4.5 líneas futuras."));

A(h2("1.2 Título y resumen"));
A(table([
  ["Item (parafraseado)", "Estado", "Sección D3"],
  ["El título identifica que el trabajo desarrolla un modelo de predicción de supervivencia y senala la población oncologica.", "Cumplido", "Portada y 1.1"],
  ["El resumen recoge objetivo, datos, métodos, resultados principales y conclusiones, e indica que se trata de un prototipo no clínico.", "Cumplido", "Ficha (resumen y abstract)"],
], { aligns: A_TRIPOD }));

A(h2("1.3 Introducción"));
A(table([
  ["Item (parafraseado)", "Estado", "Sección D3"],
  ["Se explica el contexto clínico, la variabilidad de respuesta a la quimioterapia y por qué un modelo pronóstico es pertinente.", "Cumplido", "1.1"],
  ["Se justifica el enfoque metodológico de prototipo reproducible frente a uno orientado a la complejidad.", "Cumplido", "1.1, 1.4"],
  ["Se enuncian los objetivos general y específicos (O1 a O6) con sus criterios de éxito (KPI).", "Cumplido", "1.2"],
], { aligns: A_TRIPOD }));

A(h2("1.4 Métodos"));
A(table([
  ["Item (parafraseado)", "Estado", "Sección D3"],
  ["Se describe la fuente de datos (estudio NESP-Oncology-20010145, NCT00119613, Project Data Sphere) y el cambio documentado de fuente respecto de la propuesta inicial.", "Cumplido", "2.1"],
  ["Se indica el diseño del estudio (desarrollo con validación interna) y la ventana temporal basal del seguimiento.", "Cumplido", "2.1, 2.2"],
  ["Se detallan los participantes y los criterios de la cohorte (479 sujetos, una fila por sujeto).", "Cumplido", "2.1"],
  ["Se definen los desenlaces OS (a partir de DTH y DTHDY) y PFS (a partir de PFSCD y PFSDY), con censura y codificación 1 evento, 0 censura.", "Cumplido", "2.1, 2.4"],
  ["Se especifican los siete predictores basales (AGE, SEXCD, B_ECOGN, B_WEIGHT, CADIAGM, B_HGB, MEDHX_N) y la derivación de MEDHX_N.", "Cumplido", "2.1"],
  ["Se documenta el control de variables posteriores al desenlace: exclusión de ficheros longitudinales y post-basales para evitar fuga.", "Cumplido", "2.2"],
  ["Se justifica el tamaño muestral (n=479) y la validación adaptada (k=5 estratificada con bootstrap de n=1000).", "Cumplido", "2.1, 2.2"],
  ["Se describe el tratamiento de datos faltantes con imputación ajustada dentro de cada partición de entrenamiento.", "Cumplido", "2.1, 2.2"],
  ["Se detallan los métodos de análisis: Cox, RSF y XGBoost, validación cruzada estratificada, bootstrap, criterio de selección a priori y control de fugas.", "Cumplido", "2.2, 2.3"],
  ["Se describe la salida del modelo (función de riesgo y supervivencia) y la interpretación mediante hazard ratios.", "Cumplido", "2.3, 3.4"],
  ["Se especifican las métricas de evaluación (C-index, IBS, Brier dependiente del tiempo, AUC dependiente del tiempo y calibración con bandas).", "Cumplido", "2.4"],
  ["Se aborda la validación externa en una cohorte independiente.", "No aplica (línea futura)", "4.5"],
], { aligns: A_TRIPOD }));

A(h2("1.5 Componente específico de inteligencia artificial y aprendizaje automático"));
A(table([
  ["Item (parafraseado)", "Estado", "Sección D3"],
  ["Se identifica el tipo de modelos empleados (un modelo estadístico de riesgos proporcionales y dos modelos de aprendizaje automático de supervivencia).", "Cumplido", "2.3"],
  ["Se indican el software y las versiones de las herramientas utilizadas.", "Cumplido", "2.6"],
  ["Se documentan las semillas fijas y las condiciones de reproducibilidad.", "Cumplido", "2.6"],
  ["Se evalua el rendimiento por subgrupos y la equidad del desempeño, incluido el sexo como perspectiva de género.", "Cumplido", "3.5"],
  ["Se describe el procedimiento de ajuste de hiperparametros dentro del esquema de validación.", "Parcial", "2.2, 2.3"],
  ["Se valora el riesgo de sesgo y la robustez del modelo entre estratos.", "Cumplido", "3.5"],
], { aligns: A_TRIPOD }));

A(h2("1.6 Ciencia abierta y disponibilidad"));
A(table([
  ["Item (parafraseado)", "Estado", "Sección D3"],
  ["Se indica la disponibilidad del código en el repositorio del pipeline (entregable D1).", "Cumplido", "2.6, anexo 7.2"],
  ["Se aclara que los datos a nivel de sujeto no se comparten por privacidad por diseño y que solo se publican metadatos.", "Cumplido", "2.5, 2.6"],
  ["Se incluye la declaración sobre el uso de herramientas de inteligencia artificial generativa.", "Cumplido", "1.8"],
  ["Se declara el protocolo o registro previo del estudio.", "Parcial", "2.2 (criterios a priori)"],
], { aligns: A_TRIPOD }));

A(h2("1.7 Resultados"));
A(table([
  ["Item (parafraseado)", "Estado", "Sección D3"],
  ["Se describe el flujo de participantes y el número de eventos (OS: 397 eventos; PFS: 440 eventos sobre n=479).", "Cumplido", "2.1, 3.2"],
  ["Se presenta la comparativa de modelos bajo el criterio fijado a priori.", "Cumplido", "3.1"],
  ["Se identifica el modelo final (Cox proporcional por parsimonia) y su justificación.", "Cumplido", "3.1"],
  ["Se reporta el rendimiento (C-index, IBS, AUC dependiente del tiempo) con intervalos de confianza.", "Cumplido", "3.2"],
  ["Se presenta la calibración con bandas bootstrap en varios horizontes temporales.", "Cumplido", "3.3"],
  ["Se aporta la interpretabilidad mediante hazard ratios y el test de proporcionalidad.", "Cumplido", "3.4"],
  ["Se analiza la robustez por subgrupos.", "Cumplido", "3.5"],
  ["Se documentan los datos sintéticos y su evaluación de utilidad y riesgo.", "Cumplido", "3.6"],
], { aligns: A_TRIPOD }));

A(h2("1.8 Discusión"));
A(table([
  ["Item (parafraseado)", "Estado", "Sección D3"],
  ["Se discuten las limitaciones: validez externa limitada por tratarse de una cohorte de ensayo.", "Cumplido", "4.1, 4.2"],
  ["Se reconoce el tamaño muestral moderado (n=479).", "Cumplido", "4.2"],
  ["Se reporta de forma honesta que el KPI-3 (mejora sobre baseline) no se cumple.", "Cumplido", "3.1, 4.2"],
  ["Se documenta la violación parcial del supuesto de proporcionalidad en AGE y B_WEIGHT.", "Cumplido", "3.4"],
  ["Se senala que el endpoint PFS es poco informativo con estos predictores.", "Cumplido", "3.2"],
  ["Se aclara que la interpretación de las asociaciones es descriptiva y no causal.", "Cumplido", "3.4"],
  ["Se incluye la advertencia explícita de no uso clínico.", "Cumplido", "1.1, Model Card"],
  ["Se interpretan los resultados en el contexto de la evidencia disponible y su implicación práctica como prototipo.", "Cumplido", "4.1, 4.4"],
], { aligns: A_TRIPOD }));

A(h2("1.9 Otra información"));
A(table([
  ["Item (parafraseado)", "Estado", "Sección D3"],
  ["Se declara la financiacion del trabajo: ninguna.", "Cumplido", "Otra información (este documento)"],
  ["Se declaran los conflictos de interés: ninguno.", "Cumplido", "Otra información (este documento)"],
  ["Se confirma la ausencia de mención a centros externos de colaboración.", "Cumplido", "Todo el documento"],
], { aligns: A_TRIPOD }));
A(p("Financiacion: el trabajo no ha recibido financiacion. Conflictos de interés: el autor declara no tener ningún conflicto de interés. No existe ninguna entidad externa de colaboración asociada al trabajo."));
A(new Paragraph({ children: [new PageBreak()] }));

// ============================================================================
// PARTE 2. MODEL CARD FINAL
// ============================================================================
A(h1("Parte 2. Model Card final"));
A(noteBox([
  [run("Nota sobre la fuente canónica: ", { bold: true, size: 20 }),
   run("la versión viva y de referencia de la Model Card es el fichero docs/model_card.md, cerrado en el Sprint 8 con los valores reales del pipeline. El contenido que sigue reproduce esa fuente sin alterar ningún valor. En caso de discrepancia, prevalece docs/model_card.md.", { size: 20 })],
]));

A(...renderMarkdownToDocx(MODEL_CARD_MD, { skipFirstH1: true, headingOffset: 1 }));
A(new Paragraph({ children: [new PageBreak()] }));

// ============================================================================
// PARTE 3. ANÁLISIS DE RIESGOS
// ============================================================================
A(h1("Parte 3. Análisis de riesgos"));
A(p("Escalas: probabilidad e impacto se valoran como Baja, Media o Alta. La columna de estado al cierre resume la situación real al final del trabajo (2026-06-01)."));

A(h2("3.1 Riesgos del proyecto (propuesta y PEC1)"));
A(table([
  ["Riesgo", "Probabilidad", "Impacto", "Señal temprana", "Mitigación", "Estado al cierre"],
  ["Etiquetas de respuesta inadecuadas o incompletas (RECIST y ORR)", "Alta", "Alto", "Alto porcentaje de valores faltantes en la respuesta directa durante la auditoria de la cohorte", "Reformulacion del problema a supervivencia con censura (pivote P1), que aprovecha la información temporal del seguimiento", "Materializado y resuelto: motivo el pivote P1, registrado en el Decisión log"],
  ["Heterogeneidad de tumor y de terapia en la cohorte", "Media", "Medio", "Variabilidad clínica entre subgrupos y presencia del brazo de aleatorizacion", "Uso del brazo NESP/placebo como variable de estratificación y análisis de transferibilidad entre estratos", "Mitigado: rendimiento consistente entre brazos (sección 3.5 de D3)"],
  ["Desbalanceo de clases en una tarea de clasificación binaria", "Media", "Medio", "Distribución desigual de la etiqueta de respuesta", "Reformulacion a supervivencia con censura, que elimina la dependencia de un umbral de clase", "Mitigado: el problema se trata como tiempo hasta evento"],
  ["Fuga de información (leakage) en el preprocesado o por variables post-outcome", "Media", "Alto", "Rendimiento inusualmente alto o inestable entre particiones", "Preprocesado ajustado dentro de cada partición de entrenamiento y exclusión de ficheros longitudinales y post-basales", "Mitigado: estabilidad entre folds coherente (CV% bajo), sin indicios de fuga"],
  ["Privacidad y riesgo de reidentificación de datos de salud", "Media", "Alto", "Datos a nivel de sujeto potencialmente identificables", "Privacidad por diseño: datos crudos y derivados no versionados, solo metadatos; análisis de reidentificación en tres dimensiones", "Mitigado en lo organizativo; el conjunto sintético queda como NO ACEPTADO por k-anonimidad (ver categoría 3.3)"],
  ["Sobrecoste por ampliación del alcance", "Media", "Medio", "Acumulación de tareas fuera del plan de sprints", "Planificacion por sprints, criterios a priori y principio de parsimonia para acotar el alcance", "Controlado: alcance estable, sin dependencia de nube ni de licencias"],
], { aligns: A_RISK }));
A(tableCaption("Riesgos del proyecto y su estado al cierre."));

A(h2("3.2 Riesgos del modelo en uso (no clínico)"));
A(table([
  ["Riesgo", "Probabilidad", "Impacto", "Señal temprana", "Mitigación", "Estado al cierre"],
  ["Calibración que subestima la supervivencia a largo plazo en pacientes de alto riesgo (t=355 días)", "Media", "Medio", "Deciles de alto riesgo con supervivencia observada por encima de la predicha en el horizonte largo", "Reporte explícito de la tendencia, advertencia de no uso clínico y propuesta de extensiones dependientes del tiempo como línea futura", "Documentado en 3.3 de D3 y en la Model Card; no se corrige por el carácter de prototipo"],
  ["Discriminación modesta (C-index OS 0.599; PFS 0.555)", "Alta", "Medio", "Valores de C-index próximos al rango moderado en el desarrollo", "Comunicación honesta del rendimiento con intervalos de confianza y énfasis en el carácter metodológico", "Documentado en 3.2 de D3; asumido como propio del prototipo"],
  ["Interpretación causal indebida de los hazard ratios", "Media", "Alto", "Lectura de asociaciones como relaciones causa-efecto", "Advertencia expresa de interpretación descriptiva y no causal en D3 y en la Model Card", "Mitigado mediante documentación explícita (3.4 de D3)"],
  ["Validez externa limitada por tratarse de una cohorte de ensayo", "Alta", "Alto", "Criterios de inclusión y exclusión estrictos y baja representatividad poblacional", "Declaración de estudio de desarrollo sin validación externa y propuesta de validación externa como línea futura", "Documentado como limitación (4.2 y 4.5 de D3)"],
  ["Violación parcial del supuesto de proporcionalidad (AGE y B_WEIGHT)", "Media", "Medio", "p del test de Schoenfeld por debajo de 0.05 en esas variables", "Reporte de la violación y de su alcance acotado; las variables de mayor señal cumplen el supuesto", "Documentado en 3.4 de D3 y en la Model Card"],
  ["Endpoint PFS poco informativo con predictores basales", "Alta", "Bajo", "C-index de PFS próximo al azar (0.555) y alta tasa de eventos (92%)", "Reporte de PFS por completitud, con advertencia de su utilidad pronóstica marginal", "Documentado en 3.2 de D3"],
], { aligns: A_RISK }));
A(tableCaption("Riesgos del modelo en uso (no clínico) y su estado al cierre."));

A(h2("3.3 Riesgos de privacidad y de uso indebido"));
A(table([
  ["Riesgo", "Probabilidad", "Impacto", "Señal temprana", "Mitigación", "Estado al cierre"],
  ["El conjunto sintético resulta NO ACEPTADO por k-anonimidad con bins de edad de 5 años", "Alta", "Medio", "Fracción de registros sintéticos con combinación única de cuasi-identificadores por encima del umbral (k1 = 7.32%)", "Uso del sintético solo para prototipado, no publicado; análisis de sensibilidad con bins de 10 años; triangulación con membership inference (AUC 0.534) y DCR (ratio 0.622)", "Materializado y gestionado: documentado como NO ACEPTADO, con sensibilidad y triangulación (3.6 de D3 y Model Card)"],
  ["Interpretación clínica del prototipo por parte de terceros", "Media", "Alto", "Uso del modelo o de los sintéticos fuera del contexto metodológico", "Advertencia explícita de no uso clínico en D3 y en la Model Card, y restricción del uso de los sintéticos al prototipado", "Mitigado mediante documentación y advertencias inequívocas"],
  ["Difusión de datos a nivel de sujeto", "Baja", "Alto", "Inclusión accidental de datos crudos o derivados en el control de versiones", "Privacidad por diseño: exclusión de los datos de sujeto del repositorio, solo metadatos (diccionario, hashes y manifiesto)", "Controlado: no se versionan datos de sujeto"],
], { aligns: A_RISK }));
A(tableCaption("Riesgos de privacidad y de uso indebido, y su estado al cierre."));

A(p([run("Fin del documento D4. ", { bold: true }), run("Fuentes: documentación interna del proyecto (decision_log y model_card) y artefactos de la carpeta output (ficheros JSON y CSV).")]));

// ============================================================================
// DOCUMENTO
// ============================================================================
const doc = new Document({
  creator: "Alfonso Esteban Lasso",
  title: "Paquete de transparencia y gobernanza (D4) - TFG",
  description: "Entregable D4 - Checklist TRIPOD+AI, Model Card final y análisis de riesgos",
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
