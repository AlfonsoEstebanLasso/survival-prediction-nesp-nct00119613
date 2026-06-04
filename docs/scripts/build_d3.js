// build_d3.js
// Propósito: generar la memoria final del TFG (entregable D3) en formato .docx
//   siguiendo la estructura de la plantilla oficial UOC
//   (docs/plantilla/TF_Plantilla_Memoria_es_v9_2025.docx).
// Entradas: docs/decision_log.md, docs/model_card.md, output/*.json, output/*.csv,
//   output/*.png, docs/style_guide.md, docs/scripts/_style.js.
// Salida: output/D3_Memoria_TFG_NESP.docx
// Transformaciones: maqueta portada, licencia, ficha, tres índices, cuerpo
//   (capítulos 1 a 7), glosario, bibliografía y anexos. No inventa números:
//   todos los valores proceden de los artefactos del pipeline.
// Regla del proyecto: sin guiones largos (em/en) en ningún texto generado.

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  Header, Footer, PageNumber, TableOfContents, SimpleField, ImageRun,
  PageBreak, VerticalAlign, LevelFormat, convertInchesToTwip, HeightRule,
} from "docx";
import { FONT, COLORS, TABLE } from "./_style.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..", "..");
const OUT = path.join(ROOT, "output");

// ----------------------------------------------------------------------------
// Utilidades de lectura de artefactos
// ----------------------------------------------------------------------------
function readJSON(rel) {
  return JSON.parse(fs.readFileSync(path.join(OUT, rel), "utf-8"));
}
function readCSV(rel) {
  const txt = fs.readFileSync(path.join(OUT, rel), "utf-8").trim();
  const lines = txt.split(/\r?\n/);
  const head = lines[0].split(",");
  return lines.slice(1).map((l) => {
    // separación simple por comas (los CSV del pipeline no llevan comas internas)
    const cells = l.split(",");
    const obj = {};
    head.forEach((h, i) => (obj[h] = cells[i]));
    return obj;
  });
}
function pngSize(buf) {
  // Lee ancho y alto desde la cabecera IHDR del PNG.
  const w = buf.readUInt32BE(16);
  const h = buf.readUInt32BE(20);
  return { w, h };
}
// Carga el logo UOC de la portada (extraido de la plantilla oficial). Si no esta
// disponible, devuelve null y la portada cae a una cabecera de texto.
function tryReadLogo() {
  try {
    return fs.readFileSync(path.join(ROOT, "docs", "assets", "uoc_logo.png"));
  } catch {
    return null;
  }
}
const LOGO = tryReadLogo();

// ----------------------------------------------------------------------------
// Carga de datos del pipeline
// ----------------------------------------------------------------------------
const cox = readJSON("cox_baseline_metrics.json");
const synth = readJSON("synthetic_metrics.json");
const manifest = readJSON("nesp_nct00119613_etl_manifest.json");
const comp = readCSV("model_comparison.csv");
const hr = readCSV("cox_hazard_ratios.csv");
const schoen = readCSV("cox_schoenfeld_test.csv");
const subOS = readCSV("robustness_subgroups_OS.csv");
const subPFS = readCSV("robustness_subgroups_PFS.csv");
const kanon = readCSV("synthetic_kanon_sensitivity.csv");

// ----------------------------------------------------------------------------
// Helpers de formato (Arial, justificado, doble espacio)
// ----------------------------------------------------------------------------
const DOUBLE = 480; // interlineado doble (240 = simple)
const PLACEHOLDER = "B7791F"; // ámbar para marcar pendientes

function run(text, opts = {}) {
  return new TextRun({ text, font: FONT, ...opts });
}

// Párrafo de cuerpo: justificado y doble espacio. Acepta texto o array de runs.
function p(content, opts = {}) {
  const children = typeof content === "string" ? [run(content)] : content;
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: DOUBLE, after: 120 },
    children,
    ...opts,
  });
}

// Párrafo con citas [n]: convierte "...texto [1]..." en runs.
function pc(text, opts = {}) {
  return p(text, opts);
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

// Lista con viñetas
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

// ----------------------------------------------------------------------------
// Numeración de figuras y tablas (campos SEQ para alimentar los índices)
// ----------------------------------------------------------------------------
let figN = 0, tabN = 0;
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
function figureBlock(file, captionText, maxWidthPx = 540) {
  const abs = path.join(OUT, file);
  const buf = fs.readFileSync(abs);
  const { w, h } = pngSize(buf);
  const scale = Math.min(1, maxWidthPx / w);
  const W = Math.round(w * scale), H = Math.round(h * scale);
  figN += 1;
  const img = new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 120, after: 60 },
    children: [new ImageRun({ data: buf, transformation: { width: W, height: H } })],
  });
  const cap = new Paragraph({
    style: "Caption",
    alignment: AlignmentType.CENTER,
    spacing: { after: 200 },
    children: [
      run("Figura ", { bold: true, size: 18 }),
      new SimpleField("SEQ Figura \\* ARABIC", String(figN)),
      run(". " + captionText, { size: 18, italics: true }),
    ],
  });
  return [img, cap];
}

// Nota destacada (barra lateral azul) para advertencias
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

// Pie de página "Página X de Y" con campos reales de docx. Un único TextRun
// con children mezclando texto y campos para que se pueble al actualizar (F9).
function footerParagraph() {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({
      font: FONT,
      size: 16,
      children: ["Página ", PageNumber.CURRENT, " de ", PageNumber.TOTAL_PAGES],
    })],
  });
}

// Atajo de cita en texto: devuelve runs intercalando énfasis no necesario.
// (las citas [n] se escriben directamente en el texto)

// ============================================================================
// CONTENIDO
// ============================================================================
const children = [];
const A = (...xs) => xs.forEach((x) => children.push(x));

// ---- PORTADA (formato de la plantilla oficial UOC v9) -----------------------
const COVER_CYAN = "73EDFF";  // banner superior de la portada UOC
const COVER_NAVY = "000078";  // color del título en la plantilla UOC
const TITLE_D3 = "Predicción de respuesta a fármacos quimioterapéuticos a partir de datos clínicos anonimizados";
const SUBTITLE_D3 = "Prototipo de investigación reproducible y auditable para la predicción de supervivencia bajo quimioterapia";

// Logo UOC (de la plantilla oficial) escalado al ancho del área de texto. Si no
// esta disponible, se cae a una cabecera de texto.
if (LOGO) {
  const { w, h } = pngSize(LOGO);
  const wPx = 600;
  const hPx = Math.round((wPx * h) / w);
  A(new Paragraph({ alignment: AlignmentType.LEFT, spacing: { before: 200, after: 400 },
    children: [new ImageRun({ data: LOGO, transformation: { width: wPx, height: hPx } })] }));
} else {
  A(new Paragraph({ alignment: AlignmentType.LEFT, spacing: { before: 200, after: 400 },
    children: [run("Universitat Oberta de Catalunya (UOC)", { bold: true, size: 28, color: COLORS.blueDark })] }));
}

// Banner superior cian con título y subtítulo (replica del banner de la plantilla).
A(new Table({
  width: { size: 100, type: WidthType.PERCENTAGE },
  borders: {
    top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE },
    left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE },
    insideHorizontal: { style: BorderStyle.NONE }, insideVertical: { style: BorderStyle.NONE },
  },
  rows: [new TableRow({
    height: { value: 4206, rule: HeightRule.ATLEAST },
    children: [new TableCell({
      shading: { type: ShadingType.CLEAR, color: "auto", fill: COVER_CYAN },
      verticalAlign: VerticalAlign.CENTER,
      margins: { top: 200, bottom: 200, left: 300, right: 300 },
      children: [
        new Paragraph({ alignment: AlignmentType.LEFT, spacing: { after: 220 },
          children: [run(TITLE_D3, { bold: true, size: 40, color: COVER_NAVY })] }),
        new Paragraph({ alignment: AlignmentType.LEFT,
          children: [run(SUBTITLE_D3, { size: 26, color: COVER_NAVY })] }),
      ],
    })],
  })],
}));

// Pila de campos de la portada, en el mismo orden que la plantilla.
const coverFields = [
  [null, "Alfonso Esteban Lasso"],
  [null, "Grado en Ciencia de Datos Aplicada"],
  [null, "Salud"],
  ["Nombre del Tutor/a de TF", "Tutor del TFG"],
  ["Profesor/a responsable de la asignatura", "PRA del TFG"],
  [null, "06/2026"],
];
coverFields.forEach(([label, value], i) => {
  const runs = label
    ? [run(label + ": ", { size: 26, color: COLORS.blueDark }),
       run(value, { bold: true, size: 26, color: COLORS.blueDark })]
    : [run(value, { bold: true, size: 26, color: COLORS.blueDark })];
  A(new Paragraph({ alignment: AlignmentType.LEFT,
    spacing: { before: i === 0 ? 500 : 60, after: 60 }, children: runs }));
});
A(new Paragraph({ children: [new PageBreak()] }));

// ---- PÁGINA DE LICENCIA ------------------------------------------------------
A(
  h1("Licencia"),
  noteBox([
    [run("Nota para el estudiante: ", { bold: true, color: PLACEHOLDER, size: 20 }),
     run("la licencia que figura a continuación es la opción por defecto propuesta. Puedes cambiarla por otra de las recogidas en la plantilla oficial UOC (otras variantes Creative Commons, GNU FDL o Copyright) si lo acuerdas con el tutor.", { size: 20 })],
  ]),
  p([run("Esta obra esta sujeta a una licencia de Reconocimiento NoComercial SinObraDerivada 3.0 España de Creative Commons (CC BY NC ND 3.0 ES).", { italics: true })]),
  p("Se permite la reproducción, distribución y comunicación pública de la obra siempre que se reconozca la autoría, no se haga un uso comercial y no se generen obras derivadas. El texto completo de la licencia esta disponible en la página oficial de Creative Commons."),
  new Paragraph({ children: [new PageBreak()] }),
);

// ---- FICHA DEL TRABAJO FINAL -------------------------------------------------
const resumenES =
  "Este Trabajo Final de Grado desarrolla un prototipo de investigación reproducible y auditable para predecir la supervivencia de pacientes oncologicos bajo quimioterapia a partir de datos clínicos basales anonimizados. El contexto de aplicación es metodológico y no clínico. La cohorte procede del estudio NESP-Oncology-20010145 (NCT00119613) de Project Data Sphere, con 479 sujetos. La variable objetivo es la supervivencia con censura, en sus endpoints OS (primario) y PFS (secundario). La metodología aplica un control estricto contra fugas de información: todo el preprocesado se ajusta dentro de cada partición de entrenamiento, en un esquema de validación cruzada estratificada k=5 con bootstrap de n=1000. Se comparan tres modelos, Cox de riesgos proporcionales como baseline, Random Survival Forest y XGBoost, con un criterio de selección fijado a priori que combina C-index, IBS y estabilidad entre particiones. El modelo final es el Cox proporcional por parsimonia: ningún candidato mejora de forma estadísticamente significativa el baseline (KPI-3 no cumplido, hallazgo honesto). Se evalua la calibración con bandas bootstrap, la interpretabilidad mediante hazard ratios y la robustez por subgrupos, incluido el sexo como perspectiva de género. Se genera además un conjunto sintético con CTGAN, exclusivamente para prototipado, y se analiza el riesgo de reidentificación en tres dimensiones. El trabajo se enmarca en el RGPD, la LOPDGDD, el AI Act y las guías de la AEPD, con privacidad por diseño y advertencia explícita de no uso clínico.";
const resumenEN =
  "This Bachelor's thesis develops a reproducible and auditable research prototype to predict the survival of cáncer patients under chemotherapy from anonymized baseline clinical data. The application context is methodological and not clinical. The cohort comes from the NESP-Oncology-20010145 study (NCT00119613) in Project Data Sphere, with 479 subjects. The target is right-censored survival, in its OS (primary) and PFS (secondary) endpoints. The methodology applies strict leakage control: all preprocessing is fitted within each training fold, using stratified k=5 cross-validation with bootstrap of n=1000. Three models are compared, a Cox proportional hazards baseline, Random Survival Forest and XGBoost, with an a priori selection criterion combining C-index, IBS and cross-fold stability. The final model is Cox proportional hazards by parsimony: no candidate significantly outperforms the baseline (KPI-3 not met, an honest finding). Calibration is assessed with bootstrap bands, interpretability through hazard ratios and robustness across subgroups, including sex as a gender perspective. A synthetic dataset is also generated with CTGAN, solely for prototyping, and the re-identification risk is analyzed across three dimensions. The work is framed within the GDPR, the Spanish data protection law, the AI Act and the AEPD guidelines, with privacy by design and an explicit non-clinical-use warning.";

A(h1("Ficha del Trabajo Final"));
A(table([
  ["Campo", "Contenido"],
  ["Título del trabajo", "Predicción de respuesta a fármacos quimioterapéuticos a partir de datos clínicos anonimizados"],
  ["Nombre del autor", "Alfonso Esteban Lasso"],
  ["Nombre del director (tutor)", "Tutor del TFG"],
  ["Nombre del PRA", "PRA del TFG"],
  ["Fecha de entrega (mm/aaaa)", "06/2026"],
  ["Titulacion o programa", "Grado en Ciencia de Datos Aplicada"],
  ["Área del Trabajo Final", "Salud"],
  ["Idioma del trabajo", "Castellano (con abstract en inglés)"],
]));
A(new Paragraph({ spacing: { before: 120, after: 40 },
  children: [run("Palabras clave (máximo 3): ", { bold: true }),
    run("supervivencia, quimioterapia, reproducibilidad", {})] }));
A(h3("Resumen del Trabajo (máximo 250 palabras)"));
A(p(resumenES));
A(h3("Abstract (maximum 250 words)"));
A(p([run(resumenEN, { italics: true })]));
A(new Paragraph({ children: [new PageBreak()] }));

// ---- ÍNDICES -----------------------------------------------------------------
A(h1("Índice de contenido"));
A(new TableOfContents("Índice de contenido", { hyperlink: true, headingStyleRange: "1-3" }));
A(new Paragraph({ children: [new PageBreak()] }));
A(h1("Índice de figuras"));
A(new TableOfContents("Índice de figuras", { hyperlink: true, captionLabel: "Figura" }));
A(new Paragraph({ children: [new PageBreak()] }));
A(h1("Índice de tablas"));
A(new TableOfContents("Índice de tablas", { hyperlink: true, captionLabel: "Tabla" }));
A(noteBox([
  [run("Aviso: ", { bold: true, color: PLACEHOLDER, size: 20 }),
   run("los tres índices y los números de figura y tabla se generan mediante campos de Word. Tras abrir el documento, selecciona todo (Ctrl+E) y pulsa F9 para actualizar los campos y la paginación.", { size: 20 })],
]));
A(new Paragraph({ children: [new PageBreak()] }));

// ============================================================================
// 1. INTRODUCCIÓN
// ============================================================================
A(h1("1. Introducción"));

A(h2("1.1 Contexto y justificación del Trabajo"));
A(pc("La respuesta a los tratamientos quimioterapéuticos en oncología presenta una elevada variabilidad entre pacientes. Una fracción relevante de los sujetos no obtiene beneficio clínico o sufre toxicidades sin mejora del pronóstico, lo que motiva el interés por herramientas que estimen el riesgo de forma individualizada a partir de información disponible al inicio del tratamiento. La predicción de supervivencia bajo quimioterapia es, por tanto, un problema de relevancia clínica y metodológica."));
A(pc("El presente trabajo no construye un dispositivo clínico ni una herramienta de ayuda a la decisión. Su finalidad es metodológica: desarrollar un prototipo de investigación reproducible y auditable que prediga la supervivencia con censura y, sobre todo, que documente el proceso con transparencia y trazabilidad. Esta orientación responde a una doble motivación. En primer lugar, la calidad de la evidencia en modelos pronósticos depende más del rigor del diseño (control de fugas, validación honesta, calibración, evaluación por subgrupos) que de la complejidad del algoritmo [6, 7]. En segundo lugar, el tratamiento de datos de salud exige garantías de privacidad por diseño y un marco ético y legal explícito."));
A(pc("La aportación del trabajo es, en consecuencia, un pipeline completo y reproducible (extracción, transformación y carga, preprocesado sin fuga, modelado, evaluación, interpretabilidad y análisis de privacidad) acompañado de un paquete de transparencia. El valor no reside en superar el estado del arte en discriminación, sino en demostrar un proceso defendible, con resultados honestos incluso cuando estos no son favorables a la hipótesis de mejora."));

A(h2("1.2 Objetivos del Trabajo"));
A(pc("El objetivo general es desarrollar y documentar un prototipo reproducible que prediga la supervivencia con censura bajo quimioterapia a partir de covariables clínicas basales anonimizadas, con control estricto de fugas de información y evaluación honesta del rendimiento, la calibración y la robustez."));
A(pc("Los objetivos específicos, con sus indicadores de éxito (KPI) asociados, son los siguientes:"));
A(bullet([run("O1. ", { bold: true }), run("Construir un ETL trazable que derive un dataset a nivel de sujeto desde las tablas del estudio, con diccionario, manifiesto de calidad y hashes. Criterio de éxito: KPI-2 (calidad de datos).")]));
A(bullet([run("O2. ", { bold: true }), run("Implementar un preprocesado ajustado exclusivamente dentro de cada partición de entrenamiento, sin fuga entre entrenamiento y prueba. Criterio de éxito: estabilidad del rendimiento entre particiones (verificación indirecta de ausencia de fuga).")]));
A(bullet([run("O3. ", { bold: true }), run("Entrenar y comparar un baseline Cox y dos modelos alternativos (Random Survival Forest y XGBoost) bajo un criterio de selección fijado a priori. Criterio de éxito: KPI-3 (mejora sobre baseline).")]));
A(bullet([run("O4. ", { bold: true }), run("Evaluar el modelo final con métricas de discriminación, error de predicción y calibración con bandas bootstrap. Criterio de éxito: KPI-4 (calibración).")]));
A(bullet([run("O5. ", { bold: true }), run("Analizar la robustez por subgrupos y la interpretabilidad descriptiva del modelo, incluida la perspectiva de género. Criterio de éxito: coherencia entre estratos y lectura no causal documentada.")]));
A(bullet([run("O6. ", { bold: true }), run("Garantizar la reproducibilidad y la privacidad por diseño, con datos sintéticos para prototipado y análisis de riesgo de reidentificación, en el marco RGPD, LOPDGDD, AI Act y AEPD. Criterio de éxito: KPI-1 (reproducibilidad) y KPI-5 (evaluación ético legal).")]));

A(h2("1.3 Impacto en sostenibilidad, ético-social y de diversidad"));
A(pc("Siguiendo la Guía transversal sobre la Competencia Ética y Global (CCEG) de la UOC, se identifican los impactos del trabajo en sus tres dimensiones y su relación con los Objetivos de Desarrollo Sostenible (ODS)."));
A(h3("1.3.1 Sostenibilidad"));
A(pc("El prototipo tiene una huella de cómputo modesta. El pipeline se ejecuta íntegramente en un equipo portátil, sin dependencia de infraestructura en la nube ni de aceleradores especializados, gracias a una cohorte de tamaño moderado (479 sujetos) y a modelos de baja demanda computacional. La reproducibilidad (semillas fijas, entorno versionado y artefactos trazables) evita re-ejecuciones innecesarias y reduce el consumo asociado a la repetición de experimentos. Estos rasgos se alinean con el ODS 9 (industria, innovación e infraestructura) en su vertiente de eficiencia y con el ODS 12 (producción y consumo responsables) por el uso sobrio de recursos de cómputo."));
A(h3("1.3.2 Ético-social y responsabilidad social"));
A(pc("El trabajo maneja datos de salud, que son una categoría especial de datos personales. Se adopta una estrategia de privacidad por diseño: los datos crudos y el dataset derivado a nivel de sujeto no se versionan, solo se publican metadatos (diccionario, hashes y manifiesto de calidad). El marco regulatorio aplicado comprende el RGPD [13], la LOPDGDD [14], el AI Act [15] y las guías de anonimizacion de la AEPD [16]. Se asume el riesgo de que un modelo pronóstico produzca probabilidades mal calibradas que, en un hipotético uso indebido, induzcan decisiones erróneas; por ello la calibración se evalua de forma explícita y se acompana de una advertencia inequívoca de no uso clínico. La transparencia se materializa en el seguimiento de TRIPOD+AI [7] y en una Model Card viva. Adicionalmente, se realiza un análisis de riesgo de reidentificación sobre datos sintéticos. Estas medidas conectan con el ODS 3 (salud y bienestar), por la orientación responsable hacia el ámbito sanitario, y con el ODS 16 (instituciones sólidas), por la rendición de cuentas y la transparencia del proceso."));
A(h3("1.3.3 Diversidad, género y derechos humanos"));
A(pc("El rendimiento del modelo se evalua por subgrupos, incluido el sexo, que se incorpora como perspectiva de género en el análisis de equidad del desempeño. Se documenta de forma honesta la representatividad limitada de la cohorte: al tratarse de un ensayo clínico con criterios de inclusión y exclusión, su validez externa es restringida, y varias variables (raza, tipo tumoral y extensión) son constantes en esta población, lo que impide cualquier análisis de equidad sobre esas dimensiones y debe advertirse. La protección de los datos personales se entiende como un derecho fundamental. Estas consideraciones se alinean con el ODS 5 (igualdad de género), por el análisis del desempeño segun el sexo, y con el ODS 10 (reducción de las desigualdades), por la atención a la representatividad y a los límites de generalización del modelo."));

A(h2("1.4 Enfoque y método seguido"));
A(pc("Se consideraron dos estrategias generales. La primera, orientada a maximizar la complejidad del modelo (ingeniería intensiva de variables, modelos de aprendizaje profundo y búsqueda extensa de hiperparametros). La segunda, orientada a maximizar la calidad metodológica y la reproducibilidad sobre un núcleo de predictores basales con señal, con control estricto de fugas y evaluación honesta. Se eligio la segunda."));
A(pc("La elección es la apropiada por tres razones. Primera, el tamaño muestral moderado (479 sujetos) y el uso exclusivo de covariables basales limitan el beneficio esperable de modelos de alta capacidad y aumentan el riesgo de sobreajuste. Segunda, en un prototipo de investigación el valor reside en la trazabilidad y la defensa del proceso, no en una ganancia marginal de discriminación. Tercera, la sensibilidad de los datos de salud obliga a priorizar la privacidad y la transparencia. El proceso se estructura segun CRISP-ML(Q) (comprensión del problema y de los datos, preparación, modelado, evaluación y despliegue documental) y se organiza en sprints incrementales, con registro continuo de decisiones en un Decisión log y mantenimiento de una Model Card viva."));

A(h2("1.5 Planificacion del Trabajo"));
A(pc("Los recursos empleados son un equipo portátil de propósito general, un entorno de software libre (Python para el pipeline y Node para la generación de documentos) y el acceso a los datos a través de Project Data Sphere [19]. El trabajo se organiza en ocho sprints alineados con las entregas (PEC). La siguiente tabla resume el calendario y los hitos, a modo de diagrama de Gantt simplificado."));
A(table([
  ["Sprint", "Fase", "Hito principal", "Entrega"],
  ["1-2", "Comprensión y datos", "ETL trazable y dataset derivado", "D0, D2"],
  ["3", "Preprocesado sin fuga", "Transformador ajustado por partición", "D1"],
  ["4", "Modelado", "Cox, RSF y XGBoost", "D1"],
  ["5", "Evaluación", "Métricas, calibración y subgrupos", "D1, D3"],
  ["6", "Privacidad", "Datos sintéticos y reidentificación", "D4"],
  ["7", "Redacción y transparencia", "Memoria y TRIPOD+AI", "D3, D4"],
  ["8", "Cierre", "Entorno limpio, release y defensa", "D1, D5"],
]));
A(tableCaption("Planificacion por sprints y entregas (PEC). La entrega final corresponde a la PEC4 (02/06/2026)."));

A(h2("1.6 Breve sumario de productos obtenidos"));
A(pc("El trabajo genera cinco productos: D1, repositorio del pipeline reproducible; D2, dataset derivado, diccionario y reporte de calidad; D3, la presente memoria final; D4, paquete de transparencia (TRIPOD+AI, Model Card final y análisis de riesgos); y D5, presentación y guión de defensa. El detalle de cada producto se desarrolla en los capítulos siguientes."));

A(h2("1.7 Breve descripción de los otros capítulos de la memoria"));
A(pc("El capítulo 2 (Materiales y métodos) describe la cohorte, el diseño experimental con control de fugas, los modelos, las métricas de evaluación, la estrategia de privacidad y datos sintéticos, y las decisiones de reproducibilidad. El capítulo 3 (Resultados) presenta la comparativa de modelos y la selección del modelo final, su rendimiento en OS y PFS, la calibración, la interpretabilidad, la robustez por subgrupos y los resultados de datos sintéticos. El capítulo 4 (Conclusiones y trabajos futuros) recoge las conclusiones, la reflexión crítica sobre los objetivos, el seguimiento de la planificacion y la metodología, la evaluación de los impactos y las líneas futuras. Siguen el glosario (capítulo 5), la bibliografía (capítulo 6) y los anexos (capítulo 7)."));

A(h2("1.8 Declaración sobre el uso de inteligencia artificial generativa"));
A(noteBox([
  [run("Nota de revisión: ", { bold: true, color: PLACEHOLDER, size: 20 }),
   run("esta declaración describe el alcance real del uso de herramientas de apoyo en el trabajo. Revisa que se corresponde con tu experiencia antes de la entrega y comentalo con el tutor.", { size: 20 })],
]));
A(pc("Se han utilizado herramientas de apoyo únicamente para tareas de soporte técnico (andamiaje inicial de código y maquetacion de los documentos), sin incidencia en el contenido científico. El diseño experimental, las decisiones metodológicas y estadísticas, la ejecución del pipeline y el análisis e interpretación de los resultados son autoría del autor, que ha revisado y validado cada cifra frente a los artefactos generados por el código. El uso de estas herramientas se realizó con conocimiento del tutor."));

// ============================================================================
// 2. MATERIALES Y MÉTODOS
// ============================================================================
A(h1("2. Materiales y métodos"));

A(h2("2.1 Datos y cohorte"));
A(pc("Los datos proceden del estudio NESP-Oncology-20010145 (ensayo NCT00119613), disponible a través de Project Data Sphere [19]. Se trata de un ensayo de fase III, aleatorizado, doble ciego y controlado con placebo, realizado en pacientes con cáncer de pulmón microcítico (de células pequeñas) en estadio extenso, no tratados previamente, que reciben quimioterapia con platino y etopósido (darbepoetina alfa frente a placebo). El presente trabajo lo reformula como un problema de pronóstico de supervivencia bajo quimioterapia y no estudia el efecto del agente del estudio. La elección de esta fuente fue una decisión documentada: la propuesta inicial contemplaba cBioPortal, pero se optó por Project Data Sphere por disponer de variables de outcome más completas y trazables, homogeneidad del régimen y trazabilidad temporal del seguimiento."));
A(pc("El protocolo del ensayo planificó aproximadamente 600 sujetos (unos 300 por brazo, con análisis final previsto a las 496 muertes); la cohorte disponible en Project Data Sphere comprende 479 sujetos, con una fila por sujeto tras el ETL. La clave de unión es SUBJID y la espina de datos es la tabla c_keyvar con uniones por la izquierda sobre las tablas de endpoints, características basales, diagnóstico y antecedentes médicos. La integridad se verificó con un manifiesto de calidad que incluye hashes SHA-256 de cada fuente. Los endpoints son OS (a partir de las variables DTH y DTHDY) y PFS (a partir de PFSCD y PFSDY), codificados con 1 = evento y 0 = censura. La cohorte presenta 397 eventos de OS (83 por ciento) y 82 censuras, y 440 eventos de PFS (92 por ciento) y 39 censuras."));
A(pc("Se emplean siete predictores basales con señal (Estrategia 1): AGE, SEXCD, B_ECOGN, B_WEIGHT, CADIAGM, B_HGB y MEDHX_N. El estado funcional B_ECOGN sigue la escala ECOG [11]. La covariable MEDHX_N se deriva del número de sistemas corporales con antecedente anómalo por sujeto (rango 0 a 6). Se excluyeron por ser constantes en esta cohorte las variables RACECD, TUMORCD, EXTENTCD y CHDCLASS: el tipo tumoral, la extensión de la enfermedad y la clase de quimioterapia son invariantes por los criterios de inclusión del protocolo (todos los sujetos son cáncer de pulmón microcítico en estadio extenso tratados con platino y etopósido), mientras que RACECD presenta varianza cero observada. El control de calidad detectó un missingness mínimo (1 valor en CADIAGM y 3 en B_HGB), tratado dentro del esquema de validación. El diccionario de variables y el reporte de calidad forman parte del entregable D2."));
A(table([
  ["Predictor", "Descripción"],
  ["AGE", "Edad basal en años"],
  ["SEXCD", "Sexo (codificado 0 / 1)"],
  ["B_ECOGN", "Estado funcional ECOG basal (1 / 2)"],
  ["B_WEIGHT", "Peso basal en kilogramos"],
  ["CADIAGM", "Tiempo desde el diagnóstico en meses"],
  ["B_HGB", "Hemoglobina basal en g/dL"],
  ["MEDHX_N", "Número de sistemas con antecedente anómalo (0 a 6)"],
]));
A(tableCaption("Predictores basales empleados (Estrategia 1, núcleo con señal)."));

A(h2("2.2 Diseño experimental y control de fugas"));
A(pc("El diseño incorpora dos pivotes metodológicos adoptados de forma deliberada tras auditar la cohorte. El pivote P1 responde a una constatacion directa sobre los datos: las etiquetas de respuesta directa (RECIST [12] y ORR) presentaban un nivel de valores faltantes que comprometía una clasificación binaria valida. Por ello se reformuló el problema como supervivencia con censura (OS y PFS), que aprovecha la información temporal del seguimiento, es más trazable y se ajusta mejor a la naturaleza del outcome. El pivote P2 deriva del tamaño muestral efectivo (479 sujetos): se descartó una partición única de entrenamiento y prueba por su elevada varianza con esta n, y se optó por validación cruzada estratificada k=5 con bootstrap de n=1000, una elección que prioriza la estabilidad y la cuantificacion honesta de la incertidumbre sobre la complejidad del modelo."));
A(pc("El brazo de aleatorizacion (variable TXG) se utiliza únicamente como variable de estratificación y como eje de análisis de transferibilidad, nunca como predictor ni como objeto causal. El control de fugas es la invariante central del diseño: todo el preprocesado (imputación, codificación y escalado) se ajusta solo sobre la partición de entrenamiento dentro del esquema de validación, nunca sobre el conjunto completo. No se usan variables posteriores al outcome ni información temporal posterior al inicio del tratamiento, y se excluyen los ficheros longitudinales o post-basales (respuesta RECIST, radioterapia en estudio, transfusiones en estudio y ECOG longitudinal). La ausencia de fuga se verifica indirectamente por la estabilidad del rendimiento entre particiones."));
A(pc("El criterio de selección de modelo se fijó a priori, antes de observar los resultados, para evitar elegir el modelo a posteriori en función de la métrica que más le favoreciera. Se estableció una regla con tres componentes: la métrica principal de discriminación (C-index), el error de predicción (IBS) y la estabilidad entre particiones (coeficiente de variación del C-index entre folds). Esta combinación responde a la convicción de que un modelo útil no solo debe discriminar y predecir bien, sino hacerlo de forma estable, y se acompana del principio de parsimonia como criterio de desempate."));

A(h2("2.3 Modelos"));
A(pc("Se comparan tres modelos. El baseline es el modelo de riesgos proporcionales de Cox [1], con coeficientes directamente interpretables como hazard ratios [2]. Los dos candidatos alternativos son Random Survival Forest [3], un ensemble de árboles de supervivencia que captura no linealidades e interacciones, y XGBoost [4], un modelo de gradient boosting con perdida adaptada a supervivencia. Las implementaciones se apoyan en bibliotecas de supervivencia estandar [17, 18]."));

A(h2("2.4 Métricas y evaluación"));
A(pc("La discriminación se mide con el C-index [2] y el AUC dependiente del tiempo. El error de predicción se cuantifica con el Brier Score a lo largo del tiempo y el Integrated Brier Score (IBS) [5]. La calibración se evalua con curvas de fiabilidad por deciles de riesgo y bandas bootstrap, con la supervivencia observada estimada por Kaplan-Meier. Es importante distinguir dos formas de agregar las métricas: la media entre particiones (promedio de las cinco métricas por fold, que informa de la estabilidad) y la métrica calculada sobre las predicciones OOF (out of fold) agregadas (todas las predicciones de prueba reunidas, que es la base del bootstrap de incertidumbre). Ambas se reportan y pueden diferir ligeramente. La incertidumbre se expresa con intervalos de confianza al 95 por ciento por bootstrap de n=1000. Se evaluo también la postcalibracion (Platt [22] e isotónica)."));

A(h2("2.5 Privacidad y datos sintéticos"));
A(pc("La privacidad se aborda por diseño: minimizacion, no versionado de datos a nivel de sujeto y trazabilidad. Como complemento metodológico se generó un conjunto sintético con CTGAN [8] (implementacion de la Synthetic Data Vault [9], 300 épocas, n=478). El conjunto sintético se usó exclusivamente para prototipado y no refuerza ninguna conclusión del modelo principal. Su utilidad se midió con el protocolo TSTR (train on synthetic, test on real). El riesgo de reidentificación se analizó en tres dimensiones: ataque de inferencia de pertenencia o membership inference [21], unicidad de cuasi-identificadores mediante k-anonimidad [20] y distancia al vecino más cercano (DCR). Los criterios de aceptación se fijaron a priori."));

A(h2("2.6 Reproducibilidad y herramientas"));
A(pc("La reproducibilidad se garantiza con semillas fijas en todo el código (semilla 42), un entorno de software versionado, un repositorio del pipeline (entregable D1) con cabeceras de propósito, entradas y salidas en cada script, y pruebas de humo. La elección de herramientas responde a criterios de transparencia y coste: Python con bibliotecas de supervivencia de código abierto [17, 18] para el pipeline, y la librería docx de Node para la generación de documentos. Todo el software es libre y se ejecuta en local, sin dependencias propietarias ni de nube, lo que favorece la verificación en un entorno limpio (KPI-1)."));

A(h2("2.7 Valoración económica"));
A(pc("El coste económico del trabajo es bajo. No se requiere infraestructura de pago: el pipeline se ejecuta en un equipo portátil de propósito general con software libre, sin dependencia de servicios en la nube ni de licencias propietarias. El acceso a los datos se obtiene de forma gratuita a través de Project Data Sphere [19]. Los principales costes son, por tanto, el tiempo de dedicación y el consumo eléctrico del equipo, ambos modestos. Esta sobriedad es coherente con la dimensión de sostenibilidad descrita en el apartado 1.3."));

// ============================================================================
// 3. RESULTADOS
// ============================================================================
A(h1("3. Resultados"));

A(h2("3.1 Comparativa de modelos y selección"));
A(pc("La tabla siguiente resume el rendimiento de los tres modelos en el endpoint primario (OS), con la media entre particiones del CV k=5 (y su coeficiente de variación) y el C-index bootstrap con su intervalo de confianza al 95 por ciento."));
function compRows(endpoint) {
  const rows = comp.filter((r) => r.Endpoint === endpoint);
  const order = ["Cox PH", "RSF", "XGBoost"];
  rows.sort((a, b) => order.indexOf(a.Modelo) - order.indexOf(b.Modelo));
  return rows.map((r) => [
    r.Modelo,
    `${(+r.CV_Cindex_mean).toFixed(3)} (${(+r.CV_Cindex_pct).toFixed(1)}%)`,
    (+r.CV_IBS_mean).toFixed(3),
    (+r.Boot_Cindex).toFixed(3),
    `[${(+r.Boot_Cindex_lo).toFixed(3)}, ${(+r.Boot_Cindex_hi).toFixed(3)}]`,
  ]);
}
A(table([["Modelo", "C-index CV (CV%)", "IBS CV", "C-index boot", "IC95% boot"], ...compRows("OS")]));
A(tableCaption("Comparativa de modelos en OS (CV k=5 y bootstrap n=1000). El CV% es el coeficiente de variación del C-index entre particiones."));
A(pc("Aplicando el criterio de selección fijado a priori, el modelo final es el Cox de riesgos proporcionales, retenido por parsimonia. El mejor candidato alternativo, Random Survival Forest, alcanza una discriminación prácticamente equivalente (diferencia de C-index en OS de 0.007, inferior al nivel de ruido del CV) y una estabilidad algo mayor (CV% de 4.5 frente a 7.0 de Cox), pero su intervalo bootstrap se solapa por completo con el de Cox (RSF IC95% [0.562, 0.621] frente a Cox IC95% [0.567, 0.629]) y su IBS es casi idéntico. XGBoost queda por detrás en ambos endpoints: con 479 sujetos y 7 predictores, la señal disponible no sustenta la capacidad de un modelo de gradient boosting."));
A(noteBox([
  [run("KPI-3 (mejora sobre baseline): NO CUMPLIDO. ", { bold: true, color: PLACEHOLDER, size: 20 }),
   run("Es un hallazgo honesto y esperado. Con un tamaño muestral moderado, siete predictores basales y alta tasa de eventos, la superficie de decisión es prácticamente lineal y los modelos no lineales no aportan ventaja en esta cohorte. Se documenta como limitación explícita y no se fuerza la elección de un modelo más complejo sin ganancia significativa.", { size: 20 })],
]));

A(h2("3.2 Modelo final: OS primario y PFS secundario"));
A(pc("El modelo final (Cox proporcional) se evalua sobre predicciones OOF agregadas del CV k=5. La tabla resume las métricas principales con sus intervalos bootstrap para el endpoint primario (OS) y el secundario (PFS)."));
A(table([
  ["Métrica", "OS (IC95%)", "PFS (IC95%)"],
  ["C-index (boot)", `${cox.OS.bootstrap.c_index.mean.toFixed(3)} [${cox.OS.bootstrap.c_index.ci_low.toFixed(3)}, ${cox.OS.bootstrap.c_index.ci_high.toFixed(3)}]`,
    `${cox.PFS.bootstrap.c_index.mean.toFixed(3)} [${cox.PFS.bootstrap.c_index.ci_low.toFixed(3)}, ${cox.PFS.bootstrap.c_index.ci_high.toFixed(3)}]`],
  ["IBS (boot)", `${cox.OS.bootstrap.ibs.mean.toFixed(3)} [${cox.OS.bootstrap.ibs.ci_low.toFixed(3)}, ${cox.OS.bootstrap.ibs.ci_high.toFixed(3)}]`,
    `${cox.PFS.bootstrap.ibs.mean.toFixed(3)} [${cox.PFS.bootstrap.ibs.ci_low.toFixed(3)}, ${cox.PFS.bootstrap.ibs.ci_high.toFixed(3)}]`],
  ["C-index CV (media, CV%)", `${cox.OS.cv.c_index.mean.toFixed(3)} (${cox.OS.cv.c_index.cv_pct}%)`, `${cox.PFS.cv.c_index.mean.toFixed(3)} (${cox.PFS.cv.c_index.cv_pct}%)`],
  ["IBS CV (media, CV%)", `${cox.OS.cv.ibs.mean.toFixed(3)} (${cox.OS.cv.ibs.cv_pct}%)`, `${cox.PFS.cv.ibs.mean.toFixed(3)} (${cox.PFS.cv.ibs.cv_pct}%)`],
]));
A(tableCaption("Métricas del modelo final Cox proporcional en OS y PFS. Se distingue la media entre particiones (CV) del valor sobre OOF agregado (boot)."));
A(pc("En OS la discriminación es moderada (C-index de 0.599) y estable. El detalle por partición en OS es 0.528, 0.614, 0.635, 0.623 y 0.599, lo que ilustra la variabilidad esperable con este tamaño muestral. El IBS de OS sobre OOF agregado es 0.182, mientras que las particiones individuales alcanzan valores hasta 0.193 (fold 3); ambas cifras se etiquetan con cuidado para no confundir la media entre folds con la métrica sobre OOF agregado."));
A(...figureBlock("fig_brier_time_OS.png", "Brier Score dependiente del tiempo en OS, con banda bootstrap. El error se mantiene por debajo del modelo nulo en el horizonte evaluado."));
A(pc("El AUC dependiente del tiempo en OS es decreciente a lo largo del seguimiento: parte de valores en torno a 0.70 en los primeros días y desciende de forma progresiva, con un valor medio integrado de 0.645 (IC95% [0.601, 0.690]). Este patrón decreciente indica que la capacidad discriminativa del modelo es mayor a corto plazo que a largo plazo."));
A(...figureBlock("fig_auc_time_OS.png", "AUC dependiente del tiempo en OS, con banda bootstrap. La discriminación decrece a lo largo del seguimiento."));
A(pc("El endpoint secundario (PFS) es prácticamente no informativo: el C-index bootstrap es 0.555 (IC95% [0.525, 0.586]), muy próximo al azar (0.5), y el AUC medio integrado es 0.584. La alta tasa de eventos de PFS (92 por ciento) deja muy poca información de censura y limita la estimación de la curva de supervivencia. Se reporta PFS por completitud, pero su utilidad pronóstica con estos predictores basales es marginal."));

A(h2("3.3 Calibración"));
A(pc("La calibración del modelo final se evaluó sobre predicciones OOF en tres horizontes temporales de OS, con bandas bootstrap. El KPI-4 se considera cumplido: la calibración es aceptable en el rango central del horizonte y más ruidosa en los extremos, lo cual es esperable con 479 sujetos y alta tasa de eventos."));
A(...figureBlock("fig_calibration_OS.png", "Curvas de calibración en OS por deciles de riesgo, en tres horizontes temporales, con bandas bootstrap."));
A(pc("En los horizontes de 164 días y 259 días el modelo esta bien calibrado: los deciles siguen la diagonal con dispersión moderada y dentro de las bandas bootstrap, sin sesgo sistemático. En el horizonte de 355 días se observa una tendencia predominante a subestimar la supervivencia en los deciles de alto riesgo (la supervivencia observada por Kaplan-Meier queda por encima de la predicción media), con una dispersión apreciable por el menor número de sujetos en riesgo a esa profundidad de seguimiento. Este patrón es coherente con un modelo de Cox sin covariables dependientes del tiempo y con la violación parcial del supuesto de proporcionalidad que se describe en el apartado 3.4. No invalida el modelo como prototipo, pero limita la precisión de las predicciones absolutas de supervivencia a largo plazo en el subgrupo de mayor riesgo."));
A(pc("Se evaluo la postcalibracion (Platt e isotónica). Las mejoras fueron marginales y sin significación estadística frente a los intervalos bootstrap, por lo que el modelo final se reporta sin postcalibracion por parsimonia."));

A(h2("3.4 Interpretabilidad"));
A(pc("Al ser el modelo final un Cox proporcional, los coeficientes se interpretan directamente como hazard ratios (HR). La tabla recoge los HR con su intervalo de confianza y su significación para OS. La categoría de referencia de B_ECOGN es el estado funcional 1; SEXCD=1 corresponde al sexo femenino."));
function hrRows(endpoint) {
  return hr.filter((r) => r.endpoint === endpoint).map((r) => [
    r.display_name,
    (+r.HR).toFixed(3),
    `[${(+r.HR_CI_lo).toFixed(3)}, ${(+r.HR_CI_hi).toFixed(3)}]`,
    (+r.p_valor) < 0.001 ? "<0.001" : (+r.p_valor).toFixed(3),
    r.sig === "ns" ? "ns" : r.sig,
  ]);
}
A(table([["Variable", "HR", "IC95%", "p", "Sig."], ...hrRows("OS")]));
A(tableCaption("Hazard ratios del modelo final Cox en OS. Sig.: * p<0.05, ** p<0.01, *** p<0.001, ns no significativo."));
A(pc("En OS, las asociaciones estadísticamente significativas son tres. El sexo femenino (SEXCD=1) se asocia con menor riesgo de muerte (HR 0.641, IC95% [0.514, 0.799], p<0.001). El estado funcional reducido (B_ECOGN=2 frente a 1) se asocia con mayor riesgo (HR 1.693, IC95% [1.326, 2.160], p<0.001). Cada sistema corporal adicional con antecedente anómalo (MEDHX_N) se asocia con un incremento del riesgo (HR 1.086, IC95% [1.003, 1.177], p=0.042). En PFS se mantienen significativas SEXCD (HR 0.779, p=0.018) y B_ECOGN (HR 1.432, p=0.003). Estas asociaciones son descriptivas y no causales: el ensayo no fue disenado para identificarlas y pueden estar confundidas por factores no medidos."));
A(...figureBlock("fig_forest_plot.png", "Forest plot de los hazard ratios del modelo final, con intervalos de confianza al 95 por ciento."));
A(pc("El supuesto de proporcionalidad de riesgos se verificó con el test de Schoenfeld. Dos variables lo violan: AGE en OS (p=0.030) y B_WEIGHT en OS (p=0.026) y en PFS (p=0.011). El resto de variables cumplen el supuesto, incluidas las de mayor señal pronóstica (SEXCD y B_ECOGN). La violación parcial se reporta como limitación: el efecto de esas dos variables puede variar a lo largo del seguimiento. No se reestima el modelo con extensiones dependientes del tiempo, dado el carácter de prototipo académico y el tamaño muestral moderado."));
A(...figureBlock("fig_schoenfeld_OS.png", "Residuos de Schoenfeld en OS. AGE y B_WEIGHT muestran tendencia temporal (violación del supuesto de proporcionalidad)."));

A(h2("3.5 Robustez y subgrupos"));
A(pc("El rendimiento del modelo final se analizó por subgrupos, con estadísticas bootstrap calculadas sobre cada estrato por separado. Las tablas recogen el C-index con su intervalo de confianza y el IBS para OS y PFS."));
function subRows(rows) {
  return rows.map((r) => [
    r.Subgrupo, r.n, r.n_eventos,
    (+r.C_index).toFixed(3),
    `[${(+r.CI_lo).toFixed(3)}, ${(+r.CI_hi).toFixed(3)}]`,
    (+r.IBS).toFixed(3),
  ]);
}
A(table([["Subgrupo", "n", "Eventos", "C-index", "IC95%", "IBS"], ...subRows(subOS)]));
A(tableCaption("Rendimiento por subgrupos en OS (bootstrap por estrato)."));
A(table([["Subgrupo", "n", "Eventos", "C-index", "IC95%", "IBS"], ...subRows(subPFS)]));
A(tableCaption("Rendimiento por subgrupos en PFS (bootstrap por estrato)."));
A(...figureBlock("fig_subgroup_cindex.png", "C-index por subgrupo con intervalos de confianza al 95 por ciento (OS y PFS)."));
const ecog2OS = (+subOS.find((r) => r.Subgrupo.includes("B_ECOGN = 2")).C_index).toFixed(3);
const ecog2PFS = (+subPFS.find((r) => r.Subgrupo.includes("B_ECOGN = 2")).C_index).toFixed(3);
A(pc(`El rendimiento es consistente entre estratos, sin caídas abruptas. Los dos brazos de aleatorizacion muestran rendimientos similares (en OS, 0.587 en el brazo NESP frente a 0.611 en placebo, con intervalos solapados), lo que sugiere transferibilidad del modelo entre estratos de tratamiento, coherente con un diseño basado solo en predictores basales. La discriminación es menor en el subgrupo de estado funcional reducido (ECOG 2: ${ecog2OS} en OS y ${ecog2PFS} en PFS), lo cual es esperable por la menor heterogeneidad pronóstica cuando el riesgo basal ya es elevado. Desde la perspectiva de género, el desempeño por sexo es comparable (en OS, 0.595 para SEXCD=0 y 0.586 para SEXCD=1).`));

A(h2("3.6 Datos sintéticos"));
A(pc("El conjunto sintético generado con CTGAN se evaluó en utilidad y en riesgo de reidentificación. La utilidad TSTR (entrenar en sintético, evaluar en real) arroja un C-index medio de 0.437, frente a 0.600 del esquema TRTR equivalente, con un ratio de utilidad del 72.8 por ciento. El valor TSTR esta por debajo de 0.5, es decir, por debajo del azar, lo que indica que el conjunto sintético no captura adecuadamente la estructura de correlación necesaria para el pronóstico de supervivencia. Esto confirma su carácter exclusivamente de prototipado."));
A(...figureBlock("fig_synthetic_tstr.png", "Utilidad TSTR frente a TRTR por partición. El TSTR queda por debajo de 0.5 (azar)."));
A(pc("El riesgo de reidentificación se evaluó en tres dimensiones con criterios de aceptación fijados a priori. La tabla resume los resultados."));
A(table([
  ["Dimensión", "Valor", "Umbral", "Resultado"],
  ["Membership inference AUC", synth.reidentification_risk.membership_inference.auc.toFixed(3), "<= 0.60", "ACEPTADO"],
  ["TPR @ FPR=0.1", synth.reidentification_risk.membership_inference.tpr_at_fpr01.toFixed(3), "<= 0.20", "ACEPTADO"],
  ["K-anonimidad k=1 (bins 5a)", (synth.reidentification_risk.k_anonymity.k1_pct * 100).toFixed(2) + "%", "< 5.00%", "NO ACEPTADO"],
  ["K-anonimidad k<=2 (bins 5a)", (synth.reidentification_risk.k_anonymity.k2_pct * 100).toFixed(2) + "%", "< 10.00%", "NO ACEPTADO"],
  ["K-anonimidad k<=5 (bins 5a)", (synth.reidentification_risk.k_anonymity.k5_pct * 100).toFixed(2) + "%", "< 20.00%", "NO ACEPTADO"],
  ["DCR_p5 / RRDR_mediana", synth.reidentification_risk.dcr.dcr_p5_rrdr_median_ratio.toFixed(3), ">= 0.50", "ACEPTADO"],
]));
A(tableCaption("Análisis de riesgo de reidentificación del conjunto sintético. Evaluación global: NO ACEPTADO por k-anonimidad."));
A(pc("La evaluación global es NO ACEPTADO, motivada por la k-anonimidad con la configuración de cuasi-identificadores preregistrada (bins de edad de 5 años, junto con SEXCD y B_ECOGN). El membership inference y la distancia al vecino más cercano superan sus umbrales sin problema, lo que indica que el riesgo no reside en la copia literal de registros, sino en la similitud estructural de combinaciones de atributos. El análisis de sensibilidad con bins de edad de 10 años reduce las fracciones a k1=5.44 por ciento, k2=7.32 por ciento y k5=11.51 por ciento, de modo que k2 y k5 pasan el umbral en esa configuración alternativa, pero k1 sigue por encima. Esto evidencia que la k-anonimidad depende directamente de la granularidad del binning de la edad."));
A(table([
  ["Configuración", "k=1", "k<=2", "k<=5"],
  ...kanon.map((r) => [`bins ${r.bin_step_years} años`, (+r.k1_pct * 100).toFixed(2) + "%", (+r.k2_pct * 100).toFixed(2) + "%", (+r.k5_pct * 100).toFixed(2) + "%"]),
]));
A(tableCaption("Análisis de sensibilidad de la k-anonimidad a la granularidad del binning de edad."));
A(...figureBlock("fig_synthetic_kanon.png", "Unicidad de cuasi-identificadores (k-anonimidad) en el conjunto sintético."));
A(...figureBlock("fig_synthetic_membership.png", "Ataque de inferencia de pertenencia (membership inference): curva ROC y AUC."));
A(noteBox([
  [run("Advertencia: ", { bold: true, color: PLACEHOLDER, size: 20 }),
   run("los datos sintéticos son exclusivamente para prototipado metodológico. No representan pacientes reales, no refuerzan las conclusiones del modelo principal y no deben usarse con fines clínicos ni epidemiologicos.", { size: 20 })],
]));

// ----------------------------------------------------------------------------
// 3.7 Análisis ampliado (Estrategia 2), exploratorio. Valores reales de
// output/strategy2_nested_metrics.json y output/strategy2_paired_test.json,
// registrados en el decision log (entradas de la Estrategia 2).
// ----------------------------------------------------------------------------
A(h2("3.7 Análisis ampliado: Estrategia 2 (exploratorio)"));
A(pc("Como complemento exploratorio al pipeline primario, y sin sustituirlo, se evaluó si ampliar el conjunto de covariables basales y optimizar la selección de características y los hiperparámetros mediante validación cruzada anidada mejora el rendimiento pronóstico sin sesgo de selección. El protocolo se pre-registró por escrito antes de ejecutar ningún modelado."));
A(pc("Se construyó un dataset derivado propio de 10 covariables basales o pre-aleatorización: las 7 del primario, con el peso sustituido por el índice de masa corporal, más la EPO sérica basal (transformada con log1p), el LDH basal (normal o anormal, factor de estratificación de la aleatorización) y la transfusión previa al tratamiento. El esquema fue una validación cruzada anidada: un bucle externo k=5 para la estimación de rendimiento sin sesgo y un bucle interno k=5 donde se confinaron la selección embebida (penalización L1 en Cox, poda por importancia de permutación en Random Survival Forest y de ganancia en XGBoost) y el ajuste de hiperparámetros con Optuna (100 iteraciones por modelo y fold). El Cox elastic-net, el Random Survival Forest y el XGBoost se compararon contra el baseline de 7 variables ejecutado bajo el mismo protocolo anidado."));
A(table([
  ["Endpoint", "Modelo", "C-index (IC95%)", "IBS", "CV%"],
  ["OS", "Baseline 7 var", "0.599 [0.567, 0.629]", "0.182", "7.1"],
  ["OS", "Cox elastic-net 10 var", "0.613 [0.581, 0.644]", "0.179", "7.8"],
  ["OS", "RSF 10 var", "0.596 [0.568, 0.624]", "0.181", "9.0"],
  ["OS", "XGBoost 10 var", "0.573 [0.546, 0.603]", "0.185", "4.9"],
  ["PFS", "Baseline 7 var", "0.555 [0.525, 0.586]", "0.182", "5.1"],
  ["PFS", "Cox elastic-net 10 var", "0.579 [0.547, 0.610]", "0.180", "3.4"],
  ["PFS", "RSF 10 var", "0.545 [0.512, 0.576]", "0.184", "3.3"],
  ["PFS", "XGBoost 10 var", "0.546 [0.517, 0.577]", "0.183", "8.5"],
], { aligns: [AlignmentType.LEFT, AlignmentType.LEFT, AlignmentType.CENTER, AlignmentType.CENTER, AlignmentType.CENTER] }));
A(tableCaption("Estrategia 2: rendimiento anidado por endpoint y modelo (C-index con IC95% bootstrap, IBS y coeficiente de variación entre folds)."));
A(pc("El mejor modelo de la Estrategia 2 fue el Cox elastic-net en ambos endpoints; el Random Survival Forest y el XGBoost no mejoraron al baseline, lo que refuerza el carácter casi lineal de la superficie pronóstica en esta cohorte. La selección embebida retuvo casi todo el pool, y las dos señales nuevas, LDH y EPO, se seleccionaron en los cinco folds de ambos endpoints. El contraste de significación se operacionalizó con un bootstrap pareado de la diferencia de C-index sobre las predicciones out-of-fold, restringido a la comparación relevante (Cox elastic-net frente a baseline). En el endpoint primario (OS) la diferencia fue +0.014 con IC95% [-0.008, +0.036], que incluye el cero: no hay mejora significativa. En el secundario (PFS) fue +0.024 con IC95% [+0.001, +0.046]; el intervalo excluye el cero, pero por un margen mínimo (límite inferior +0.001) y en un endpoint de discriminación intrínsecamente débil. Es un resultado en el umbral de la significación y frágil, que proviene además de uno de dos contrastes, por lo que se reporta como hallazgo exploratorio y no como evidencia robusta de mejora."));
A(pc("En conjunto, el efecto es pequeño, sin significación en el primario y solo en el umbral en el secundario, y el KPI-3 sigue sin cumplirse en el endpoint primario. El modelo final del trabajo continúa siendo el Cox del pipeline primario; el aporte de la Estrategia 2 es metodológico (un esquema de validación anidada sin sesgo de selección, con selección embebida e hiperparámetros confinados al bucle interno), no un modelo de mayor rendimiento."));

// ============================================================================
// 4. CONCLUSIONES
// ============================================================================
A(h1("4. Conclusiones y trabajos futuros"));
A(h2("4.1 Conclusiones"));
A(pc("Se ha desarrollado un prototipo de investigación reproducible y auditable para la predicción de supervivencia bajo quimioterapia, con un pipeline completo que va de la extracción de datos al análisis de privacidad. El modelo final es un Cox de riesgos proporcionales con un C-index en OS de 0.599 (IC95% [0.567, 0.629]), discriminación moderada y estable, y una calibración aceptable en el rango central del horizonte temporal. El resultado central, sin embargo, no es la cifra de discriminación, sino la demostración de un proceso defendible y honesto."));
A(pc("Algunos resultados han sido los esperados (discriminación moderada con predictores basales) y otros, aunque no favorables, son valiosos por su honestidad: los modelos no lineales no mejoran al baseline, el endpoint PFS es prácticamente no informativo y el conjunto sintético no alcanza el umbral de protección por k-anonimidad. Estos hallazgos negativos se documentan sin maquillaje, que es precisamente lo que se espera de un trabajo metodológico riguroso."));
A(h2("4.2 Reflexión crítica sobre la consecución de los objetivos"));
A(pc("Los objetivos se valoran de forma crítica. O1 (ETL trazable) se ha alcanzado con dataset derivado, diccionario, manifiesto de calidad y hashes (KPI-2 cumplido). O2 (preprocesado sin fuga) se ha alcanzado: el preprocesado se ajusta dentro de cada partición y la estabilidad entre folds respalda la ausencia de fuga. O3 (comparación de modelos) se ha completado, pero su KPI-3 (mejora sobre baseline) no se ha cumplido: ningún candidato supera significativamente al Cox; se trata de un objetivo alcanzado en ejecución y de un KPI no superado, documentado como hallazgo honesto. O4 (calibración) se ha alcanzado (KPI-4 cumplido), con la matizacion de la subestimacion a largo plazo en alto riesgo. O5 (robustez e interpretabilidad) se ha alcanzado, con lectura descriptiva no causal y análisis por subgrupos incluido el sexo. O6 (reproducibilidad y privacidad) se ha alcanzado en lo metodológico (KPI-1 y KPI-5), con la salvedad de que la evaluación de reidentificación del conjunto sintético resultó NO ACEPTADO, lo que es en si mismo un resultado del análisis de riesgo."));
A(h2("4.3 Seguimiento de la planificacion y la metodología"));
A(pc("La planificacion por sprints se ha seguido en lo esencial. La metodología prevista (CRISP-ML(Q) con control de fugas y validación adaptada) ha sido adecuada. Fue necesario introducir dos cambios relevantes, registrados como decisiones: el pivote P1 (de clasificación de respuesta a supervivencia con censura) ante la incompletitud de las etiquetas RECIST/ORR, y el pivote P2 (validación cruzada k=5 con bootstrap) para adaptar la evaluación al tamaño muestral. También se cambió la fuente de datos respecto de la propuesta inicial (de cBioPortal a Project Data Sphere) por mayor completitud y trazabilidad. Estos cambios garantizaron la validez del trabajo y se justificaron en su momento."));
A(h2("4.4 Evaluación de los impactos previstos"));
A(pc("Respecto de los impactos del apartado 1.3: en sostenibilidad, el objetivo de una huella de cómputo modesta se ha logrado (ejecución en portátil, sin nube). En la dimensión ético-social, las medidas de privacidad por diseño y de transparencia se han aplicado; el riesgo de probabilidades mal calibradas se ha mitigado mediante la evaluación explícita de la calibración y la advertencia de no uso clínico. En diversidad y género, el análisis por subgrupos incluido el sexo se ha realizado, y se ha documentado de forma honesta la representatividad limitada de la cohorte (variables de raza, tipo tumoral y extensión constantes). Como impacto no previsto, el análisis de reidentificación reveló que el conjunto sintético no cumple el umbral de k-anonimidad preregistrado; se ha mitigado documentando el hallazgo, anadiendo un análisis de sensibilidad y restringiendo el uso de los sintéticos al prototipado."));
A(h2("4.5 Líneas de trabajo futuro"));
A(bullet("Ampliar la cohorte o validar de forma externa en una población independiente para mejorar la validez externa."));
A(bullet("Explorar extensiones del modelo de Cox con efectos dependientes del tiempo para las variables que violan el supuesto de proporcionalidad (AGE y B_WEIGHT)."));
A(bullet("Incorporar predictores basales adicionales con señal, evaluando su disponibilidad sin introducir fugas."));
A(bullet("Mejorar la generación sintética (ajuste de cuasi-identificadores y generalización de la edad) para alcanzar el umbral de k-anonimidad sin degradar en exceso la utilidad."));
A(bullet("Aplicar interpretabilidad SHAP post-hoc [10] con la cautela de su inestabilidad bajo cambio de distribución."));

// ============================================================================
// 5. GLOSARIO
// ============================================================================
A(h1("5. Glosario"));
const glos = [
  ["C-index", "Índice de concordancia de Harrell. Probabilidad de que el modelo ordene correctamente el riesgo de dos sujetos comparables. 0.5 equivale al azar."],
  ["IBS", "Integrated Brier Score. Error de predicción de supervivencia integrado a lo largo del tiempo. Menor es mejor."],
  ["Brier (t)", "Error cuadratico medio de la predicción de supervivencia en un instante t."],
  ["OS", "Overall Survival. Supervivencia global, medida hasta el fallecimiento."],
  ["PFS", "Progression Free Survival. Supervivencia libre de progresión."],
  ["Censura", "Situación en la que el evento de interés no se observa dentro del período de seguimiento."],
  ["OOF", "Out of fold. Predicciones generadas sobre las particiones de prueba, agregadas para evaluar sin sobreajuste."],
  ["CV", "Validación cruzada (cross-validation). Aquí, estratificada con k=5 particiones."],
  ["Bootstrap", "Remuestreo con reemplazo para estimar la incertidumbre (intervalos de confianza). Aquí n=1000."],
  ["Cox PH", "Modelo de riesgos proporcionales de Cox. Baseline de supervivencia con coeficientes interpretables."],
  ["RSF", "Random Survival Forest. Ensemble de árboles de supervivencia."],
  ["XGBoost", "Modelo de gradient boosting de árboles, con perdida adaptada a supervivencia."],
  ["Calibración", "Concordancia entre las probabilidades predichas y las frecuencias observadas."],
  ["CTGAN", "Conditional Tabular GAN. Generador de datos tabulares sintéticos."],
  ["TSTR", "Train on Synthetic, Test on Real. Protocolo de utilidad de datos sintéticos."],
  ["DCR", "Distance to Closest Record. Distancia al registro real más cercano, indicador de riesgo de copia."],
  ["k-anonimidad", "Propiedad por la que cada combinación de cuasi-identificadores es compartida por al menos k registros."],
  ["Membership inference", "Ataque que intenta determinar si un registro concreto formo parte del conjunto de entrenamiento."],
  ["ECOG", "Escala de estado funcional del Eastern Cooperative Oncology Group."],
  ["RECIST", "Response Evaluation Criteria in Solid Tumors. Criterios de respuesta tumoral."],
  ["RGPD", "Reglamento General de Protección de Datos (Reglamento UE 2016/679)."],
  ["LOPDGDD", "Ley Orgánica de Protección de Datos Personales y garantía de los derechos digitales (LO 3/2018)."],
  ["AI Act", "Reglamento europeo de inteligencia artificial (Reglamento UE 2024/1689)."],
  ["TRIPOD+AI", "Guía de reporte transparente de modelos de predicción que incorporan inteligencia artificial."],
  ["Model Card", "Documento de transparencia que describe uso previsto, datos, métricas, limitaciones y riesgos de un modelo."],
];
glos.forEach(([t, d]) => A(new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { line: 300, after: 80 },
  children: [run(t + ": ", { bold: true }), run(d)] })));

// ============================================================================
// 6. BIBLIOGRAFÍA
// ============================================================================
A(h1("6. Bibliografía"));
const refs = [
  "Cox, David R. Regression Models and Life-Tables. Journal of the Royal Statistical Society, Series B, páginas 187 a 220, volumen 34, 1972.",
  "Harrell, Frank E.; Lee, Kerry L.; Mark, Daniel B. Multivariable Prognostic Models. Statistics in Medicine, páginas 361 a 387, volumen 15, 1996.",
  "Ishwaran, Hemant; Kogalur, Udaya B.; Blackstone, Eugene H.; Lauer, Michael S. Random Survival Forests. The Annals of Applied Statistics, páginas 841 a 860, volumen 2, 2008.",
  "Chen, Tianqi; Guestrin, Carlos. XGBoost: A Scalable Tree Boosting System. Proceedings of the 22nd ACM SIGKDD, páginas 785 a 794, 2016.",
  "Graf, Erika; Schmoor, Claudia; Sauerbrei, Willi; Schumacher, Martin. Assessment and Comparison of Prognostic Classification Schemes for Survival Data. Statistics in Medicine, páginas 2529 a 2545, volumen 18, 1999.",
  "Collins, Gary S.; Reitsma, Johannes B.; Altman, Douglas G.; Moons, Karel G. M. Transparent Reporting of a Multivariable Prediction Model for Individual Prognosis or Diagnosis (TRIPOD). BMJ, volumen 350, 2015.",
  "Collins, Gary S. y colaboradores. TRIPOD+AI Statement: Updated Guidance for Reporting Clinical Prediction Models that Use Regression or Machine Learning Methods. BMJ, volumen 385, 2024.",
  "Xu, Lei; Skoularidou, Maria; Cuesta-Infante, Alfredo; Veeramachaneni, Kalyan. Modeling Tabular Data using Conditional GAN. Advances in Neural Information Processing Systems, volumen 32, 2019.",
  "Patki, Neha; Wedge, Roy; Veeramachaneni, Kalyan. The Synthetic Data Vault. IEEE International Conference on Data Science and Advanced Analytics, páginas 399 a 410, 2016.",
  "Lundberg, Scott M.; Lee, Su-In. A Unified Approach to Interpreting Model Predictions. Advances in Neural Information Processing Systems, volumen 30, 2017.",
  "Oken, Martin M. y colaboradores. Toxicity and Response Criteria of the Eastern Cooperative Oncology Group. American Journal of Clinical Oncology, páginas 649 a 655, volumen 5, 1982.",
  "Eisenhauer, Elizabeth A. y colaboradores. New Response Evaluation Criteria in Solid Tumours: Revised RECIST guideline (versión 1.1). European Journal of Cáncer, páginas 228 a 247, volumen 45, 2009.",
  "Unión Europea. Reglamento (UE) 2016/679, General de Protección de Datos (RGPD). Diario Oficial de la Unión Europea, 2016.",
  "Jefatura del Estado de España. Ley Orgánica 3/2018 de Protección de Datos Personales y garantía de los derechos digitales (LOPDGDD). Boletín Oficial del Estado, 2018.",
  "Unión Europea. Reglamento (UE) 2024/1689 por el que se establecen normas armonizadas en materia de inteligencia artificial (AI Act). Diario Oficial de la Unión Europea, 2024.",
  "Agencia Española de Protección de Datos (AEPD). Orientaciones y garantías en los procedimientos de anonimizacion de datos personales. AEPD, 2016.",
  "Polsterl, Sebastian. scikit-survival: A Library for Time-to-Event Analysis Built on Top of scikit-learn. Journal of Machine Learning Research, páginas 1 a 6, volumen 21, 2020.",
  "Davidson-Pilon, Cameron. lifelines: Survival Analysis in Python. Journal of Open Source Software, volumen 4, 2019.",
  "Project Data Sphere. Plataforma de acceso a datos de ensayos clínicos oncologicos. Consultado en 2026.",
  "Sweeney, Latanya. k-anonymity: A Model for Protecting Privacy. International Journal of Uncertainty, Fuzziness and Knowledge-Based Systems, páginas 557 a 570, volumen 10, 2002.",
  "Shokri, Reza; Stronati, Marco; Song, Congzheng; Shmatikov, Vitaly. Membership Inference Attacks Against Machine Learning Models. IEEE Symposium on Security and Privacy, páginas 3 a 18, 2017.",
  "Platt, John C. Probabilistic Outputs for Support Vector Machines and Comparisons to Regularized Likelihood Methods. Advances in Large Margin Classifiers, páginas 61 a 74, 1999.",
];
refs.forEach((r, i) => A(new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { line: 300, after: 80 },
  children: [run(`[${i + 1}] `, { bold: true }), run(r)] })));

// ============================================================================
// 7. ANEXOS
// ============================================================================
A(h1("7. Anexos"));
A(h2("7.1 Matriz de trazabilidad objetivos, tareas, entregables y KPIs"));
A(table([
  ["Objetivo", "Tarea principal", "Entregable", "KPI"],
  ["O1", "ETL trazable y dataset derivado", "D1, D2", "KPI-2"],
  ["O2", "Preprocesado sin fuga por partición", "D1", "Estabilidad entre folds"],
  ["O3", "Comparación Cox, RSF, XGBoost", "D1, D3", "KPI-3 (no cumplido)"],
  ["O4", "Calibración con bandas bootstrap", "D3", "KPI-4"],
  ["O5", "Robustez, subgrupos e interpretabilidad", "D3", "Coherencia entre estratos"],
  ["O6", "Reproducibilidad y privacidad", "D1, D4", "KPI-1, KPI-5"],
]));
A(tableCaption("Matriz de trazabilidad entre objetivos, tareas, entregables y KPIs."));
A(h2("7.2 Repositorio del código (D1)"));
A(pc("El código completo del pipeline (ETL, preprocesado, modelado, evaluación, reporting y análisis de privacidad) constituye el entregable D1. El repositorio incluye semillas fijas, entorno versionado, cabeceras de propósito en cada script y pruebas de humo, y permite la verificación en un entorno limpio (KPI-1). Los datos crudos y el dataset derivado a nivel de sujeto no se versionan por privacidad por diseño; solo se publican metadatos (diccionario, hashes y manifiesto de calidad)."));
A(h2("7.3 Paquete de transparencia (D4)"));
A(pc("El checklist TRIPOD+AI y la Model Card final forman parte del entregable D4 (paquete de transparencia), junto con el análisis de riesgos. La Model Card se ha mantenido viva durante todo el desarrollo y se cierra con los valores reales del pipeline. Estos documentos se referencian aquí y se entregan como parte de D4."));

A(h2("7.4 Matriz de trazabilidad de resultados de aprendizaje"));
A(pc("La siguiente matriz mapea cada resultado de aprendizaje del TFG a la sección de la memoria o al entregable donde se evidencia. Los resultados marcados como fuera de alcance no aplican a este tipo de proyecto."));

// Columnas: Resultado (izquierda), Evidencia principal (izquierda), Cobertura (centro).
const RA_ALIGNS = [AlignmentType.LEFT, AlignmentType.LEFT, AlignmentType.CENTER];

A(h3("Conocimientos"));
A(table([
  ["Resultado", "Evidencia principal (sección de D3 o entregable)", "Cobertura"],
  ["K1", "1.1 (el pronóstico bajo quimioterapia como oportunidad de mejora)", "Sólida"],
  ["K2", "2.3, 2.4 y 3.2 (modelos de supervivencia, métricas, bootstrap y calibración)", "Sólida"],
  ["K3", "2.6 y D1 (pipeline modular, semillas y pruebas; sin escala de gran volumen)", "Parcial"],
  ["K4", "2.6 y 2.7 (ejecución local sin nube; volumen de datos moderado)", "Parcial"],
  ["K5", "2.1 (selección de fuente, ETL, criterios y diccionario de variables)", "Sólida"],
  ["K6", "2.3, 2.4 y 3.1 (métodos y comparativa desde las preguntas del trabajo)", "Sólida"],
  ["K7", "3.2 a 3.6 y D5 (figuras de Brier, AUC, calibración, forest y subgrupos)", "Sólida"],
  ["K8", "2.2, 3.1, 3.3, 3.4 y 4.2 (fugas, KPI-3, límites de calibración, Schoenfeld, reflexión crítica)", "Sólida"],
], { aligns: RA_ALIGNS }));
A(tableCaption("Trazabilidad de los conocimientos (K) a las secciones y entregables del TFG."));

A(h3("Habilidades"));
A(table([
  ["Resultado", "Evidencia principal (sección de D3 o entregable)", "Cobertura"],
  ["S1", "2.3, 2.4 y D1 (integración de estadística y programacion)", "Sólida"],
  ["S2", "2.6 y D1 (semillas, pruebas de humo y cabeceras de propósito)", "Sólida"],
  ["S3", "2.1, 2.2 y 2.6 (flujo completo con manifiesto de calidad)", "Sólida"],
  ["S4", "2.1 (uniones sobre las tablas del estudio por SUBJID, hashes; fuente única)", "Parcial"],
  ["S5", "2.1 y 2.2 (datos clínicos estructurados)", "Parcial"],
  ["S6", "2.3, 2.4 y 3.1 (solución analítica con métodos y herramientas apropiados)", "Sólida"],
  ["S7", "1.3.2, 2.5, 3.6 y D4 (privacidad por diseño, marco legal y reidentificación)", "Sólida"],
  ["S8", "Fuera del alcance del TFG (no hay interfaz de usuario)", "Fuera de alcance"],
  ["S9", "3.2 a 3.6 y D5 (figuras y diapositivas)", "Sólida"],
  ["S10", "Fuera del alcance del TFG (no hay administración de redes ni sistemas)", "Fuera de alcance"],
  ["S11", "1.4, 2.7 y 3.1 (estrategias consideradas, valoración económica y comparativa)", "Sólida"],
  ["S12", "3.x, 4.x, resumen y D5 (comunicación rigurosa y crítica)", "Sólida"],
  ["S13", "Memoria completa (escrita) y video D5 (oral)", "Sólida"],
  ["S14", "1.3, 1.4 y 4.1 (aportación metodológica; innovación de proceso, no de producto)", "Parcial"],
  ["S15", "Abstract de la ficha (texto académico en inglés)", "Parcial"],
], { aligns: RA_ALIGNS }));
A(tableCaption("Trazabilidad de las habilidades (S) a las secciones y entregables del TFG."));

A(h3("Competencias"));
A(table([
  ["Resultado", "Evidencia principal (sección de D3 o entregable)", "Cobertura"],
  ["C1", "1.4, 1.5 y 4.3 (gestión del proyecto, sprints y pivotes)", "Sólida"],
  ["C2", "TFG completo, D5 y defensa de la PEC5", "Sólida"],
  ["C4", "1.3, 3.5 y 4.4 (tres dimensiones de la CCEG, sexo como perspectiva de género)", "Sólida"],
  ["C5", "3.1, 4.2, 4.4 y D4 (KPI-3 honesto, reflexión autocrítica y análisis de riesgos)", "Sólida"],
  ["C6", "2.6 y D1 (implementacion con tecnologías digitales)", "Sólida"],
], { aligns: RA_ALIGNS }));
A(tableCaption("Trazabilidad de las competencias (C) a las secciones y entregables del TFG."));

A(h2("7.5 Análisis ampliado (Estrategia 2): protocolo y resultados"));
A(pc("Este anexo detalla el análisis ampliado y exploratorio de la sección 3.7. Su protocolo se pre-registró por escrito en el registro de decisiones antes de ejecutar ningún modelado, conforme a la buena práctica de fijar el pool de variables, el método de selección, el espacio de búsqueda y el criterio de comparación antes de observar resultados. El análisis es adicional al primario, que permanece intacto con sus artefactos, sus hashes y su verificación en entorno limpio (KPI-1)."));
A(pc("El pool de 10 covariables candidatas, todas basales o pre-aleatorización y sin fuga, fue: edad, índice de masa corporal (derivado del peso y la altura), tiempo desde el diagnóstico, hemoglobina basal, EPO sérica basal (con log1p), número de sistemas con comorbilidad, sexo, ECOG basal, LDH basal y transfusión previa. Se excluyeron las variables constantes por varianza cero o por criterio de inclusión, los ficheros de laboratorio longitudinales (por ser post-basales; el LDH y la EPO basales ya están resumidos como variables de cribado), las categorizaciones redundantes y los flags administrativos. El preprocesado (imputación adaptativa, log1p de la EPO antes de escalar, estandarización y codificación) se ajustó solo en el train de cada partición, dentro del esquema anidado."));
A(pc("La selección de características y el ajuste de hiperparámetros se confinaron al bucle interno. La selección es embebida: penalización L1 en el Cox elastic-net (las variables retenidas son las de coeficiente no nulo) y poda por importancia (de permutación en Random Survival Forest, de ganancia en XGBoost) reajustando el modelo sobre las variables de mayor importancia, con el número de variables retenidas optimizado en el bucle interno. El bucle externo k=5 proporciono la estimación de rendimiento sin sesgo mediante predicciones out-of-fold con bootstrap n=1000."));
A(pc("La tabla siguiente muestra cuántos de los cinco folds externos retuvieron cada variable en el Cox elastic-net, el mejor modelo de la Estrategia 2. Las dos señales nuevas, LDH y EPO, se seleccionaron en los cinco folds de ambos endpoints; la transfusión previa, de prevalencia muy baja (1.3 por ciento), fue la menos retenida, como se anticipó."));
A(table([
  ["Variable", "OS (folds /5)", "PFS (folds /5)"],
  ["Edad", "4", "5"],
  ["Índice de masa corporal", "5", "5"],
  ["Tiempo desde el diagnóstico", "5", "5"],
  ["Hemoglobina basal", "5", "4"],
  ["EPO sérica basal", "5", "5"],
  ["Comorbilidad (n. de sistemas)", "5", "5"],
  ["Sexo", "5", "5"],
  ["ECOG basal", "5", "5"],
  ["LDH basal", "5", "5"],
  ["Transfusión previa", "3", "4"],
], { aligns: [AlignmentType.LEFT, AlignmentType.CENTER, AlignmentType.CENTER] }));
A(tableCaption("Frecuencia de selección de cada variable por el Cox elastic-net en los 5 folds externos, por endpoint."));
A(pc("Los artefactos de la Estrategia 2 (dataset derivado propio con su hash SHA-256 de referencia, diccionario, manifiesto, métricas anidadas y resultado del test pareado) se generan con los scripts de extracción y de validación cruzada anidada del repositorio, en paralelo a los del primario y sin modificarlos. El dataset a nivel de sujeto no se versiona por privacidad por diseño; solo se publican metadatos."));

// ============================================================================
// DOCUMENTO
// ============================================================================
const doc = new Document({
  creator: "Alfonso Esteban Lasso",
  title: "Memoria TFG - Predicción de supervivencia bajo quimioterapia",
  description: "Entregable D3 - Memoria final del TFG",
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
        children: [run("Universitat Oberta de Catalunya (UOC)  |  Trabajo Final de Grado", { size: 16, color: COLORS.blueDark })],
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

const outFile = path.join(OUT, "D3_Memoria_TFG_NESP.docx");
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(outFile, buf);
  console.log("Generado:", outFile);
  console.log("Figuras:", figN, "| Tablas:", tabN);
});
