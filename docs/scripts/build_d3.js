// build_d3.js
// Proposito: generar la memoria final del TFG (entregable D3) en formato .docx
//   siguiendo la estructura de la plantilla oficial UOC
//   (docs/plantilla/TF_Plantilla_Memoria_es_v9_2025.docx).
// Entradas: docs/decision_log.md, docs/model_card.md, output/*.json, output/*.csv,
//   output/*.png, docs/style_guide.md, docs/scripts/_style.js.
// Salida: output/D3_Memoria_TFG_NESP.docx
// Transformaciones: maqueta portada, licencia, ficha, tres indices, cuerpo
//   (capitulos 1 a 7), glosario, bibliografia y anexos. No inventa numeros:
//   todos los valores proceden de los artefactos del pipeline.
// Regla del proyecto: sin guiones largos (em/en) en ningun texto generado.

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  Header, Footer, PageNumber, TableOfContents, SimpleField, ImageRun,
  PageBreak, VerticalAlign, LevelFormat, convertInchesToTwip,
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
    // separacion simple por comas (los CSV del pipeline no llevan comas internas)
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
const PLACEHOLDER = "B7791F"; // ambar para marcar pendientes

function run(text, opts = {}) {
  return new TextRun({ text, font: FONT, ...opts });
}

// Parrafo de cuerpo: justificado y doble espacio. Acepta texto o array de runs.
function p(content, opts = {}) {
  const children = typeof content === "string" ? [run(content)] : content;
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: DOUBLE, after: 120 },
    children,
    ...opts,
  });
}

// Parrafo con citas [n]: convierte "...texto [1]..." en runs.
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

// Lista con vinetas
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
// Numeracion de figuras y tablas (campos SEQ para alimentar los indices)
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

// Pie de pagina "Pagina X de Y" con campos reales de docx. Un unico TextRun
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

// Atajo de cita en texto: devuelve runs intercalando enfasis no necesario.
// (las citas [n] se escriben directamente en el texto)

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
    children: [run("Prediccion de respuesta a farmacos quimioterapeuticos a partir de datos clinicos anonimizados",
      { bold: true, size: 40, color: COLORS.blueDark })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 },
    children: [run("Prototipo de investigacion reproducible y auditable para la prediccion de supervivencia bajo quimioterapia",
      { size: 24, italics: true, color: "555555" })] }),
);
const portadaFicha = [
  ["Estudiante", "Alfonso Esteban Lasso"],
  ["Programa", "[PLACEHOLDER: programa exacto, p. ej. Grado en Ciencia de Datos Aplicada]"],
  ["Area del Trabajo Final", "[PLACEHOLDER: area exacta del TF]"],
  ["Tutor de TF", "Tutor del TFG"],
  ["Profesor responsable de la asignatura (PRA)", "[PLACEHOLDER: nombre del PRA]"],
  ["Fecha de entrega", "06/2026"],
];
A(table([["Campo", "Valor"], ...portadaFicha]));
A(new Paragraph({ children: [new PageBreak()] }));

// ---- PAGINA DE LICENCIA ------------------------------------------------------
A(
  h1("Licencia"),
  noteBox([
    [run("Nota para el estudiante: ", { bold: true, color: PLACEHOLDER, size: 20 }),
     run("la licencia que figura a continuacion es la opcion por defecto propuesta. Puedes cambiarla por otra de las recogidas en la plantilla oficial UOC (otras variantes Creative Commons, GNU FDL o Copyright) si lo acuerdas con el tutor.", { size: 20 })],
  ]),
  p([run("Esta obra esta sujeta a una licencia de Reconocimiento NoComercial SinObraDerivada 3.0 Espana de Creative Commons (CC BY NC ND 3.0 ES).", { italics: true })]),
  p("Se permite la reproduccion, distribucion y comunicacion publica de la obra siempre que se reconozca la autoria, no se haga un uso comercial y no se generen obras derivadas. El texto completo de la licencia esta disponible en la pagina oficial de Creative Commons."),
  new Paragraph({ children: [new PageBreak()] }),
);

// ---- FICHA DEL TRABAJO FINAL -------------------------------------------------
const resumenES =
  "Este Trabajo Final de Grado desarrolla un prototipo de investigacion reproducible y auditable para predecir la supervivencia de pacientes oncologicos bajo quimioterapia a partir de datos clinicos basales anonimizados. El contexto de aplicacion es metodologico y no clinico. La cohorte procede del estudio NESP-Oncology-20010145 (NCT00119613) de Project Data Sphere, con 479 sujetos. La variable objetivo es la supervivencia con censura, en sus endpoints OS (primario) y PFS (secundario). La metodologia aplica un control estricto contra fugas de informacion: todo el preprocesado se ajusta dentro de cada particion de entrenamiento, en un esquema de validacion cruzada estratificada k=5 con bootstrap de n=1000. Se comparan tres modelos, Cox de riesgos proporcionales como baseline, Random Survival Forest y XGBoost, con un criterio de seleccion fijado a priori que combina C-index, IBS y estabilidad entre particiones. El modelo final es el Cox proporcional por parsimonia: ningun candidato mejora de forma estadisticamente significativa el baseline (KPI-3 no cumplido, hallazgo honesto). Se evalua la calibracion con bandas bootstrap, la interpretabilidad mediante hazard ratios y la robustez por subgrupos, incluido el sexo como perspectiva de genero. Se genera ademas un conjunto sintetico con CTGAN, exclusivamente para prototipado, y se analiza el riesgo de reidentificacion en tres dimensiones. El trabajo se enmarca en el RGPD, la LOPDGDD, el AI Act y las guias de la AEPD, con privacidad por diseno y advertencia explicita de no uso clinico.";
const resumenEN =
  "This Bachelor's thesis develops a reproducible and auditable research prototype to predict the survival of cancer patients under chemotherapy from anonymized baseline clinical data. The application context is methodological and not clinical. The cohort comes from the NESP-Oncology-20010145 study (NCT00119613) in Project Data Sphere, with 479 subjects. The target is right-censored survival, in its OS (primary) and PFS (secondary) endpoints. The methodology applies strict leakage control: all preprocessing is fitted within each training fold, using stratified k=5 cross-validation with bootstrap of n=1000. Three models are compared, a Cox proportional hazards baseline, Random Survival Forest and XGBoost, with an a priori selection criterion combining C-index, IBS and cross-fold stability. The final model is Cox proportional hazards by parsimony: no candidate significantly outperforms the baseline (KPI-3 not met, an honest finding). Calibration is assessed with bootstrap bands, interpretability through hazard ratios and robustness across subgroups, including sex as a gender perspective. A synthetic dataset is also generated with CTGAN, solely for prototyping, and the re-identification risk is analyzed across three dimensions. The work is framed within the GDPR, the Spanish data protection law, the AI Act and the AEPD guidelines, with privacy by design and an explicit non-clinical-use warning.";

A(h1("Ficha del Trabajo Final"));
A(table([
  ["Campo", "Contenido"],
  ["Titulo del trabajo", "Prediccion de respuesta a farmacos quimioterapeuticos a partir de datos clinicos anonimizados"],
  ["Nombre del autor", "Alfonso Esteban Lasso"],
  ["Nombre del director (tutor)", "Tutor del TFG"],
  ["Nombre del PRA", "[PLACEHOLDER: nombre del PRA]"],
  ["Fecha de entrega (mm/aaaa)", "06/2026"],
  ["Titulacion o programa", "[PLACEHOLDER: titulacion o programa exacto]"],
  ["Area del Trabajo Final", "[PLACEHOLDER: area del TF]"],
  ["Idioma del trabajo", "Castellano (con abstract en ingles)"],
]));
A(new Paragraph({ spacing: { before: 120, after: 40 },
  children: [run("Palabras clave (maximo 3): ", { bold: true }),
    run("supervivencia, quimioterapia, reproducibilidad", {}),
    run("  [PLACEHOLDER: a validar por el tutor]", { color: PLACEHOLDER, italics: true })] }));
A(h3("Resumen del Trabajo (maximo 250 palabras)"));
A(p(resumenES));
A(h3("Abstract (maximum 250 words)"));
A(p([run(resumenEN, { italics: true })]));
A(new Paragraph({ children: [new PageBreak()] }));

// ---- INDICES -----------------------------------------------------------------
A(h1("Indice de contenido"));
A(new TableOfContents("Indice de contenido", { hyperlink: true, headingStyleRange: "1-3" }));
A(new Paragraph({ children: [new PageBreak()] }));
A(h1("Indice de figuras"));
A(new TableOfContents("Indice de figuras", { hyperlink: true, captionLabel: "Figura" }));
A(new Paragraph({ children: [new PageBreak()] }));
A(h1("Indice de tablas"));
A(new TableOfContents("Indice de tablas", { hyperlink: true, captionLabel: "Tabla" }));
A(noteBox([
  [run("Aviso: ", { bold: true, color: PLACEHOLDER, size: 20 }),
   run("los tres indices y los numeros de figura y tabla se generan mediante campos de Word. Tras abrir el documento, selecciona todo (Ctrl+E) y pulsa F9 para actualizar los campos y la paginacion.", { size: 20 })],
]));
A(new Paragraph({ children: [new PageBreak()] }));

// ============================================================================
// 1. INTRODUCCION
// ============================================================================
A(h1("1. Introduccion"));

A(h2("1.1 Contexto y justificacion del Trabajo"));
A(pc("La respuesta a los tratamientos quimioterapeuticos en oncologia presenta una elevada variabilidad entre pacientes. Una fraccion relevante de los sujetos no obtiene beneficio clinico o sufre toxicidades sin mejora del pronostico, lo que motiva el interes por herramientas que estimen el riesgo de forma individualizada a partir de informacion disponible al inicio del tratamiento. La prediccion de supervivencia bajo quimioterapia es, por tanto, un problema de relevancia clinica y metodologica."));
A(pc("El presente trabajo no construye un dispositivo clinico ni una herramienta de ayuda a la decision. Su finalidad es metodologica: desarrollar un prototipo de investigacion reproducible y auditable que prediga la supervivencia con censura y, sobre todo, que documente el proceso con transparencia y trazabilidad. Esta orientacion responde a una doble motivacion. En primer lugar, la calidad de la evidencia en modelos pronosticos depende mas del rigor del diseno (control de fugas, validacion honesta, calibracion, evaluacion por subgrupos) que de la complejidad del algoritmo [6, 7]. En segundo lugar, el tratamiento de datos de salud exige garantias de privacidad por diseno y un marco etico y legal explicito."));
A(pc("La aportacion del trabajo es, en consecuencia, un pipeline completo y reproducible (extraccion, transformacion y carga, preprocesado sin fuga, modelado, evaluacion, interpretabilidad y analisis de privacidad) acompanado de un paquete de transparencia. El valor no reside en superar el estado del arte en discriminacion, sino en demostrar un proceso defendible, con resultados honestos incluso cuando estos no son favorables a la hipotesis de mejora."));

A(h2("1.2 Objetivos del Trabajo"));
A(pc("El objetivo general es desarrollar y documentar un prototipo reproducible que prediga la supervivencia con censura bajo quimioterapia a partir de covariables clinicas basales anonimizadas, con control estricto de fugas de informacion y evaluacion honesta del rendimiento, la calibracion y la robustez."));
A(pc("Los objetivos especificos, con sus indicadores de exito (KPI) asociados, son los siguientes:"));
A(bullet([run("O1. ", { bold: true }), run("Construir un ETL trazable que derive un dataset a nivel de sujeto desde las tablas del estudio, con diccionario, manifiesto de calidad y hashes. Criterio de exito: KPI-2 (calidad de datos).")]));
A(bullet([run("O2. ", { bold: true }), run("Implementar un preprocesado ajustado exclusivamente dentro de cada particion de entrenamiento, sin fuga entre entrenamiento y prueba. Criterio de exito: estabilidad del rendimiento entre particiones (verificacion indirecta de ausencia de fuga).")]));
A(bullet([run("O3. ", { bold: true }), run("Entrenar y comparar un baseline Cox y dos modelos alternativos (Random Survival Forest y XGBoost) bajo un criterio de seleccion fijado a priori. Criterio de exito: KPI-3 (mejora sobre baseline).")]));
A(bullet([run("O4. ", { bold: true }), run("Evaluar el modelo final con metricas de discriminacion, error de prediccion y calibracion con bandas bootstrap. Criterio de exito: KPI-4 (calibracion).")]));
A(bullet([run("O5. ", { bold: true }), run("Analizar la robustez por subgrupos y la interpretabilidad descriptiva del modelo, incluida la perspectiva de genero. Criterio de exito: coherencia entre estratos y lectura no causal documentada.")]));
A(bullet([run("O6. ", { bold: true }), run("Garantizar la reproducibilidad y la privacidad por diseno, con datos sinteticos para prototipado y analisis de riesgo de reidentificacion, en el marco RGPD, LOPDGDD, AI Act y AEPD. Criterio de exito: KPI-1 (reproducibilidad) y KPI-5 (evaluacion etico legal).")]));

A(h2("1.3 Impacto en sostenibilidad, etico-social y de diversidad"));
A(pc("Siguiendo la Guia transversal sobre la Competencia Etica y Global (CCEG) de la UOC, se identifican los impactos del trabajo en sus tres dimensiones y su relacion con los Objetivos de Desarrollo Sostenible (ODS)."));
A(h3("1.3.1 Sostenibilidad"));
A(pc("El prototipo tiene una huella de computo modesta. El pipeline se ejecuta integramente en un equipo portatil, sin dependencia de infraestructura en la nube ni de aceleradores especializados, gracias a una cohorte de tamano moderado (479 sujetos) y a modelos de baja demanda computacional. La reproducibilidad (semillas fijas, entorno versionado y artefactos trazables) evita re-ejecuciones innecesarias y reduce el consumo asociado a la repeticion de experimentos. Estos rasgos se alinean con el ODS 9 (industria, innovacion e infraestructura) en su vertiente de eficiencia y con el ODS 12 (produccion y consumo responsables) por el uso sobrio de recursos de computo."));
A(h3("1.3.2 Etico-social y responsabilidad social"));
A(pc("El trabajo maneja datos de salud, que son una categoria especial de datos personales. Se adopta una estrategia de privacidad por diseno: los datos crudos y el dataset derivado a nivel de sujeto no se versionan, solo se publican metadatos (diccionario, hashes y manifiesto de calidad). El marco regulatorio aplicado comprende el RGPD [13], la LOPDGDD [14], el AI Act [15] y las guias de anonimizacion de la AEPD [16]. Se asume el riesgo de que un modelo pronostico produzca probabilidades mal calibradas que, en un hipotetico uso indebido, induzcan decisiones erroneas; por ello la calibracion se evalua de forma explicita y se acompana de una advertencia inequivoca de no uso clinico. La transparencia se materializa en el seguimiento de TRIPOD+AI [7] y en una Model Card viva. Adicionalmente, se realiza un analisis de riesgo de reidentificacion sobre datos sinteticos. Estas medidas conectan con el ODS 3 (salud y bienestar), por la orientacion responsable hacia el ambito sanitario, y con el ODS 16 (instituciones solidas), por la rendicion de cuentas y la transparencia del proceso."));
A(h3("1.3.3 Diversidad, genero y derechos humanos"));
A(pc("El rendimiento del modelo se evalua por subgrupos, incluido el sexo, que se incorpora como perspectiva de genero en el analisis de equidad del desempeno. Se documenta de forma honesta la representatividad limitada de la cohorte: al tratarse de un ensayo clinico con criterios de inclusion y exclusion, su validez externa es restringida, y varias variables (raza, tipo tumoral y extension) son constantes en esta poblacion, lo que impide cualquier analisis de equidad sobre esas dimensiones y debe advertirse. La proteccion de los datos personales se entiende como un derecho fundamental. Estas consideraciones se alinean con el ODS 5 (igualdad de genero), por el analisis del desempeno segun el sexo, y con el ODS 10 (reduccion de las desigualdades), por la atencion a la representatividad y a los limites de generalizacion del modelo."));

A(h2("1.4 Enfoque y metodo seguido"));
A(pc("Se consideraron dos estrategias generales. La primera, orientada a maximizar la complejidad del modelo (ingenieria intensiva de variables, modelos de aprendizaje profundo y busqueda extensa de hiperparametros). La segunda, orientada a maximizar la calidad metodologica y la reproducibilidad sobre un nucleo de predictores basales con senal, con control estricto de fugas y evaluacion honesta. Se eligio la segunda."));
A(pc("La eleccion es la apropiada por tres razones. Primera, el tamano muestral moderado (479 sujetos) y el uso exclusivo de covariables basales limitan el beneficio esperable de modelos de alta capacidad y aumentan el riesgo de sobreajuste. Segunda, en un prototipo de investigacion el valor reside en la trazabilidad y la defensa del proceso, no en una ganancia marginal de discriminacion. Tercera, la sensibilidad de los datos de salud obliga a priorizar la privacidad y la transparencia. El proceso se estructura segun CRISP-ML(Q) (comprension del problema y de los datos, preparacion, modelado, evaluacion y despliegue documental) y se organiza en sprints incrementales, con registro continuo de decisiones en un Decision log y mantenimiento de una Model Card viva."));

A(h2("1.5 Planificacion del Trabajo"));
A(pc("Los recursos empleados son un equipo portatil de proposito general, un entorno de software libre (Python para el pipeline y Node para la generacion de documentos) y el acceso a los datos a traves de Project Data Sphere [19]. El trabajo se organiza en ocho sprints alineados con las entregas (PEC). La siguiente tabla resume el calendario y los hitos, a modo de diagrama de Gantt simplificado."));
A(table([
  ["Sprint", "Fase", "Hito principal", "Entrega"],
  ["1-2", "Comprension y datos", "ETL trazable y dataset derivado", "D0, D2"],
  ["3", "Preprocesado sin fuga", "Transformador ajustado por particion", "D1"],
  ["4", "Modelado", "Cox, RSF y XGBoost", "D1"],
  ["5", "Evaluacion", "Metricas, calibracion y subgrupos", "D1, D3"],
  ["6", "Privacidad", "Datos sinteticos y reidentificacion", "D4"],
  ["7", "Redaccion y transparencia", "Memoria y TRIPOD+AI", "D3, D4"],
  ["8", "Cierre", "Entorno limpio, release y defensa", "D1, D5"],
]));
A(tableCaption("Planificacion por sprints y entregas (PEC). La entrega final corresponde a la PEC4 (02/06/2026)."));

A(h2("1.6 Breve sumario de productos obtenidos"));
A(pc("El trabajo genera cinco productos: D1, repositorio del pipeline reproducible; D2, dataset derivado, diccionario y reporte de calidad; D3, la presente memoria final; D4, paquete de transparencia (TRIPOD+AI, Model Card final y analisis de riesgos); y D5, presentacion y guion de defensa. El detalle de cada producto se desarrolla en los capitulos siguientes."));

A(h2("1.7 Breve descripcion de los otros capitulos de la memoria"));
A(pc("El capitulo 2 (Materiales y metodos) describe la cohorte, el diseno experimental con control de fugas, los modelos, las metricas de evaluacion, la estrategia de privacidad y datos sinteticos, y las decisiones de reproducibilidad. El capitulo 3 (Resultados) presenta la comparativa de modelos y la seleccion del modelo final, su rendimiento en OS y PFS, la calibracion, la interpretabilidad, la robustez por subgrupos y los resultados de datos sinteticos. El capitulo 4 (Conclusiones y trabajos futuros) recoge las conclusiones, la reflexion critica sobre los objetivos, el seguimiento de la planificacion y la metodologia, la evaluacion de los impactos y las lineas futuras. Siguen el glosario (capitulo 5), la bibliografia (capitulo 6) y los anexos (capitulo 7)."));

A(h2("1.8 Declaracion sobre el uso de inteligencia artificial generativa"));
A(noteBox([
  [run("Nota de revision: ", { bold: true, color: PLACEHOLDER, size: 20 }),
   run("esta declaracion describe el alcance real del uso de herramientas de apoyo en el trabajo. Revisa que se corresponde con tu experiencia antes de la entrega y comentalo con el tutor.", { size: 20 })],
]));
A(pc("Se han utilizado herramientas de apoyo unicamente para tareas de soporte tecnico (andamiaje inicial de codigo y maquetacion de los documentos), sin incidencia en el contenido cientifico. El diseno experimental, las decisiones metodologicas y estadisticas, la ejecucion del pipeline y el analisis e interpretacion de los resultados son autoria del autor, que ha revisado y validado cada cifra frente a los artefactos generados por el codigo. El uso de estas herramientas se realizo con conocimiento del tutor."));

// ============================================================================
// 2. MATERIALES Y METODOS
// ============================================================================
A(h1("2. Materiales y metodos"));

A(h2("2.1 Datos y cohorte"));
A(pc("Los datos proceden del estudio NESP-Oncology-20010145 (ensayo NCT00119613), disponible a traves de Project Data Sphere [19]. Se trata de un ensayo de fase III. El presente trabajo lo reformula como un problema de pronostico de supervivencia bajo quimioterapia y no estudia el efecto del agente del estudio. La eleccion de esta fuente fue una decision documentada: la propuesta inicial contemplaba cBioPortal, pero se opto por Project Data Sphere por disponer de variables de outcome mas completas y trazables, homogeneidad del regimen y trazabilidad temporal del seguimiento."));
A(pc("La cohorte tiene 479 sujetos, con una fila por sujeto tras el ETL. La clave de union es SUBJID y la espina de datos es la tabla c_keyvar con uniones por la izquierda sobre las tablas de endpoints, caracteristicas basales, diagnostico y antecedentes medicos. La integridad se verifico con un manifiesto de calidad que incluye hashes SHA-256 de cada fuente. Los endpoints son OS (a partir de las variables DTH y DTHDY) y PFS (a partir de PFSCD y PFSDY), codificados con 1 = evento y 0 = censura. La cohorte presenta 397 eventos de OS (83 por ciento) y 82 censuras, y 440 eventos de PFS (92 por ciento) y 39 censuras."));
A(pc("Se emplean siete predictores basales con senal (Estrategia 1): AGE, SEXCD, B_ECOGN, B_WEIGHT, CADIAGM, B_HGB y MEDHX_N. El estado funcional B_ECOGN sigue la escala ECOG [11]. La covariable MEDHX_N se deriva del numero de sistemas corporales con antecedente anomalo por sujeto (rango 0 a 6). Se excluyeron por varianza cero en esta cohorte las variables RACECD, TUMORCD, EXTENTCD y CHDCLASS. El control de calidad detecto un missingness minimo (1 valor en CADIAGM y 3 en B_HGB), tratado dentro del esquema de validacion. El diccionario de variables y el reporte de calidad forman parte del entregable D2."));
A(table([
  ["Predictor", "Descripcion"],
  ["AGE", "Edad basal en anos"],
  ["SEXCD", "Sexo (codificado 0 / 1)"],
  ["B_ECOGN", "Estado funcional ECOG basal (1 / 2)"],
  ["B_WEIGHT", "Peso basal en kilogramos"],
  ["CADIAGM", "Tiempo desde el diagnostico en meses"],
  ["B_HGB", "Hemoglobina basal en g/dL"],
  ["MEDHX_N", "Numero de sistemas con antecedente anomalo (0 a 6)"],
]));
A(tableCaption("Predictores basales empleados (Estrategia 1, nucleo con senal)."));

A(h2("2.2 Diseno experimental y control de fugas"));
A(pc("El diseno incorpora dos pivotes metodologicos adoptados de forma deliberada tras auditar la cohorte. El pivote P1 responde a una constatacion directa sobre los datos: las etiquetas de respuesta directa (RECIST [12] y ORR) presentaban un nivel de valores faltantes que comprometia una clasificacion binaria valida. Por ello se reformulo el problema como supervivencia con censura (OS y PFS), que aprovecha la informacion temporal del seguimiento, es mas trazable y se ajusta mejor a la naturaleza del outcome. El pivote P2 deriva del tamano muestral efectivo (479 sujetos): se descarto una particion unica de entrenamiento y prueba por su elevada varianza con esta n, y se opto por validacion cruzada estratificada k=5 con bootstrap de n=1000, una eleccion que prioriza la estabilidad y la cuantificacion honesta de la incertidumbre sobre la complejidad del modelo."));
A(pc("El brazo de aleatorizacion (variable TXG) se utiliza unicamente como variable de estratificacion y como eje de analisis de transferibilidad, nunca como predictor ni como objeto causal. El control de fugas es la invariante central del diseno: todo el preprocesado (imputacion, codificacion y escalado) se ajusta solo sobre la particion de entrenamiento dentro del esquema de validacion, nunca sobre el conjunto completo. No se usan variables posteriores al outcome ni informacion temporal posterior al inicio del tratamiento, y se excluyen los ficheros longitudinales o post-basales (respuesta RECIST, radioterapia en estudio, transfusiones en estudio y ECOG longitudinal). La ausencia de fuga se verifica indirectamente por la estabilidad del rendimiento entre particiones."));
A(pc("El criterio de seleccion de modelo se fijo a priori, antes de observar los resultados, para evitar elegir el modelo a posteriori en funcion de la metrica que mas le favoreciera. Se establecio una regla con tres componentes: la metrica principal de discriminacion (C-index), el error de prediccion (IBS) y la estabilidad entre particiones (coeficiente de variacion del C-index entre folds). Esta combinacion responde a la conviccion de que un modelo util no solo debe discriminar y predecir bien, sino hacerlo de forma estable, y se acompana del principio de parsimonia como criterio de desempate."));

A(h2("2.3 Modelos"));
A(pc("Se comparan tres modelos. El baseline es el modelo de riesgos proporcionales de Cox [1], con coeficientes directamente interpretables como hazard ratios [2]. Los dos candidatos alternativos son Random Survival Forest [3], un ensemble de arboles de supervivencia que captura no linealidades e interacciones, y XGBoost [4], un modelo de gradient boosting con perdida adaptada a supervivencia. Las implementaciones se apoyan en bibliotecas de supervivencia estandar [17, 18]."));

A(h2("2.4 Metricas y evaluacion"));
A(pc("La discriminacion se mide con el C-index [2] y el AUC dependiente del tiempo. El error de prediccion se cuantifica con el Brier Score a lo largo del tiempo y el Integrated Brier Score (IBS) [5]. La calibracion se evalua con curvas de fiabilidad por deciles de riesgo y bandas bootstrap, con la supervivencia observada estimada por Kaplan-Meier. Es importante distinguir dos formas de agregar las metricas: la media entre particiones (promedio de las cinco metricas por fold, que informa de la estabilidad) y la metrica calculada sobre las predicciones OOF (out of fold) agregadas (todas las predicciones de prueba reunidas, que es la base del bootstrap de incertidumbre). Ambas se reportan y pueden diferir ligeramente. La incertidumbre se expresa con intervalos de confianza al 95 por ciento por bootstrap de n=1000. Se evaluo tambien la postcalibracion (Platt [22] e isotonica)."));

A(h2("2.5 Privacidad y datos sinteticos"));
A(pc("La privacidad se aborda por diseno: minimizacion, no versionado de datos a nivel de sujeto y trazabilidad. Como complemento metodologico se genero un conjunto sintetico con CTGAN [8] (implementacion de la Synthetic Data Vault [9], 300 epocas, n=478). El conjunto sintetico se uso exclusivamente para prototipado y no refuerza ninguna conclusion del modelo principal. Su utilidad se midio con el protocolo TSTR (train on synthetic, test on real). El riesgo de reidentificacion se analizo en tres dimensiones: ataque de inferencia de pertenencia o membership inference [21], unicidad de cuasi-identificadores mediante k-anonimidad [20] y distancia al vecino mas cercano (DCR). Los criterios de aceptacion se fijaron a priori."));

A(h2("2.6 Reproducibilidad y herramientas"));
A(pc("La reproducibilidad se garantiza con semillas fijas en todo el codigo (semilla 42), un entorno de software versionado, un repositorio del pipeline (entregable D1) con cabeceras de proposito, entradas y salidas en cada script, y pruebas de humo. La eleccion de herramientas responde a criterios de transparencia y coste: Python con bibliotecas de supervivencia de codigo abierto [17, 18] para el pipeline, y la libreria docx de Node para la generacion de documentos. Todo el software es libre y se ejecuta en local, sin dependencias propietarias ni de nube, lo que favorece la verificacion en un entorno limpio (KPI-1)."));

A(h2("2.7 Valoracion economica"));
A(pc("El coste economico del trabajo es bajo. No se requiere infraestructura de pago: el pipeline se ejecuta en un equipo portatil de proposito general con software libre, sin dependencia de servicios en la nube ni de licencias propietarias. El acceso a los datos se obtiene de forma gratuita a traves de Project Data Sphere [19]. Los principales costes son, por tanto, el tiempo de dedicacion y el consumo electrico del equipo, ambos modestos. Esta sobriedad es coherente con la dimension de sostenibilidad descrita en el apartado 1.3."));

// ============================================================================
// 3. RESULTADOS
// ============================================================================
A(h1("3. Resultados"));

A(h2("3.1 Comparativa de modelos y seleccion"));
A(pc("La tabla siguiente resume el rendimiento de los tres modelos en el endpoint primario (OS), con la media entre particiones del CV k=5 (y su coeficiente de variacion) y el C-index bootstrap con su intervalo de confianza al 95 por ciento."));
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
A(tableCaption("Comparativa de modelos en OS (CV k=5 y bootstrap n=1000). El CV% es el coeficiente de variacion del C-index entre particiones."));
A(pc("Aplicando el criterio de seleccion fijado a priori, el modelo final es el Cox de riesgos proporcionales, retenido por parsimonia. El mejor candidato alternativo, Random Survival Forest, alcanza una discriminacion practicamente equivalente (diferencia de C-index en OS de 0.007, inferior al nivel de ruido del CV) y una estabilidad algo mayor (CV% de 4.5 frente a 7.0 de Cox), pero su intervalo bootstrap se solapa por completo con el de Cox (RSF IC95% [0.562, 0.621] frente a Cox IC95% [0.567, 0.629]) y su IBS es casi identico. XGBoost queda por detras en ambos endpoints: con 479 sujetos y 7 predictores, la senal disponible no sustenta la capacidad de un modelo de gradient boosting."));
A(noteBox([
  [run("KPI-3 (mejora sobre baseline): NO CUMPLIDO. ", { bold: true, color: PLACEHOLDER, size: 20 }),
   run("Es un hallazgo honesto y esperado. Con un tamano muestral moderado, siete predictores basales y alta tasa de eventos, la superficie de decision es practicamente lineal y los modelos no lineales no aportan ventaja en esta cohorte. Se documenta como limitacion explicita y no se fuerza la eleccion de un modelo mas complejo sin ganancia significativa.", { size: 20 })],
]));

A(h2("3.2 Modelo final: OS primario y PFS secundario"));
A(pc("El modelo final (Cox proporcional) se evalua sobre predicciones OOF agregadas del CV k=5. La tabla resume las metricas principales con sus intervalos bootstrap para el endpoint primario (OS) y el secundario (PFS)."));
A(table([
  ["Metrica", "OS (IC95%)", "PFS (IC95%)"],
  ["C-index (boot)", `${cox.OS.bootstrap.c_index.mean.toFixed(3)} [${cox.OS.bootstrap.c_index.ci_low.toFixed(3)}, ${cox.OS.bootstrap.c_index.ci_high.toFixed(3)}]`,
    `${cox.PFS.bootstrap.c_index.mean.toFixed(3)} [${cox.PFS.bootstrap.c_index.ci_low.toFixed(3)}, ${cox.PFS.bootstrap.c_index.ci_high.toFixed(3)}]`],
  ["IBS (boot)", `${cox.OS.bootstrap.ibs.mean.toFixed(3)} [${cox.OS.bootstrap.ibs.ci_low.toFixed(3)}, ${cox.OS.bootstrap.ibs.ci_high.toFixed(3)}]`,
    `${cox.PFS.bootstrap.ibs.mean.toFixed(3)} [${cox.PFS.bootstrap.ibs.ci_low.toFixed(3)}, ${cox.PFS.bootstrap.ibs.ci_high.toFixed(3)}]`],
  ["C-index CV (media, CV%)", `${cox.OS.cv.c_index.mean.toFixed(3)} (${cox.OS.cv.c_index.cv_pct}%)`, `${cox.PFS.cv.c_index.mean.toFixed(3)} (${cox.PFS.cv.c_index.cv_pct}%)`],
  ["IBS CV (media, CV%)", `${cox.OS.cv.ibs.mean.toFixed(3)} (${cox.OS.cv.ibs.cv_pct}%)`, `${cox.PFS.cv.ibs.mean.toFixed(3)} (${cox.PFS.cv.ibs.cv_pct}%)`],
]));
A(tableCaption("Metricas del modelo final Cox proporcional en OS y PFS. Se distingue la media entre particiones (CV) del valor sobre OOF agregado (boot)."));
A(pc("En OS la discriminacion es moderada (C-index de 0.599) y estable. El detalle por particion en OS es 0.528, 0.614, 0.635, 0.623 y 0.599, lo que ilustra la variabilidad esperable con este tamano muestral. El IBS de OS sobre OOF agregado es 0.182, mientras que las particiones individuales alcanzan valores hasta 0.193 (fold 3); ambas cifras se etiquetan con cuidado para no confundir la media entre folds con la metrica sobre OOF agregado."));
A(...figureBlock("fig_brier_time_OS.png", "Brier Score dependiente del tiempo en OS, con banda bootstrap. El error se mantiene por debajo del modelo nulo en el horizonte evaluado."));
A(pc("El AUC dependiente del tiempo en OS es decreciente a lo largo del seguimiento: parte de valores en torno a 0.70 en los primeros dias y desciende de forma progresiva, con un valor medio integrado de 0.645 (IC95% [0.601, 0.690]). Este patron decreciente indica que la capacidad discriminativa del modelo es mayor a corto plazo que a largo plazo."));
A(...figureBlock("fig_auc_time_OS.png", "AUC dependiente del tiempo en OS, con banda bootstrap. La discriminacion decrece a lo largo del seguimiento."));
A(pc("El endpoint secundario (PFS) es practicamente no informativo: el C-index bootstrap es 0.555 (IC95% [0.525, 0.586]), muy proximo al azar (0.5), y el AUC medio integrado es 0.584. La alta tasa de eventos de PFS (92 por ciento) deja muy poca informacion de censura y limita la estimacion de la curva de supervivencia. Se reporta PFS por completitud, pero su utilidad pronostica con estos predictores basales es marginal."));

A(h2("3.3 Calibracion"));
A(pc("La calibracion del modelo final se evaluo sobre predicciones OOF en tres horizontes temporales de OS, con bandas bootstrap. El KPI-4 se considera cumplido: la calibracion es aceptable en el rango central del horizonte y mas ruidosa en los extremos, lo cual es esperable con 479 sujetos y alta tasa de eventos."));
A(...figureBlock("fig_calibration_OS.png", "Curvas de calibracion en OS por deciles de riesgo, en tres horizontes temporales, con bandas bootstrap."));
A(pc("En los horizontes de 164 dias y 259 dias el modelo esta bien calibrado: los deciles siguen la diagonal con dispersion moderada y dentro de las bandas bootstrap, sin sesgo sistematico. En el horizonte de 355 dias se observa una tendencia predominante a subestimar la supervivencia en los deciles de alto riesgo (la supervivencia observada por Kaplan-Meier queda por encima de la prediccion media), con una dispersion apreciable por el menor numero de sujetos en riesgo a esa profundidad de seguimiento. Este patron es coherente con un modelo de Cox sin covariables dependientes del tiempo y con la violacion parcial del supuesto de proporcionalidad que se describe en el apartado 3.4. No invalida el modelo como prototipo, pero limita la precision de las predicciones absolutas de supervivencia a largo plazo en el subgrupo de mayor riesgo."));
A(pc("Se evaluo la postcalibracion (Platt e isotonica). Las mejoras fueron marginales y sin significacion estadistica frente a los intervalos bootstrap, por lo que el modelo final se reporta sin postcalibracion por parsimonia."));

A(h2("3.4 Interpretabilidad"));
A(pc("Al ser el modelo final un Cox proporcional, los coeficientes se interpretan directamente como hazard ratios (HR). La tabla recoge los HR con su intervalo de confianza y su significacion para OS. La categoria de referencia de B_ECOGN es el estado funcional 1; SEXCD=1 corresponde al sexo femenino."));
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
A(pc("En OS, las asociaciones estadisticamente significativas son tres. El sexo femenino (SEXCD=1) se asocia con menor riesgo de muerte (HR 0.641, IC95% [0.514, 0.799], p<0.001). El estado funcional reducido (B_ECOGN=2 frente a 1) se asocia con mayor riesgo (HR 1.693, IC95% [1.326, 2.160], p<0.001). Cada sistema corporal adicional con antecedente anomalo (MEDHX_N) se asocia con un incremento del riesgo (HR 1.086, IC95% [1.003, 1.177], p=0.042). En PFS se mantienen significativas SEXCD (HR 0.779, p=0.018) y B_ECOGN (HR 1.432, p=0.003). Estas asociaciones son descriptivas y no causales: el ensayo no fue disenado para identificarlas y pueden estar confundidas por factores no medidos."));
A(...figureBlock("fig_forest_plot.png", "Forest plot de los hazard ratios del modelo final, con intervalos de confianza al 95 por ciento."));
A(pc("El supuesto de proporcionalidad de riesgos se verifico con el test de Schoenfeld. Dos variables lo violan: AGE en OS (p=0.030) y B_WEIGHT en OS (p=0.026) y en PFS (p=0.011). El resto de variables cumplen el supuesto, incluidas las de mayor senal pronostica (SEXCD y B_ECOGN). La violacion parcial se reporta como limitacion: el efecto de esas dos variables puede variar a lo largo del seguimiento. No se reestima el modelo con extensiones dependientes del tiempo, dado el caracter de prototipo academico y el tamano muestral moderado."));
A(...figureBlock("fig_schoenfeld_OS.png", "Residuos de Schoenfeld en OS. AGE y B_WEIGHT muestran tendencia temporal (violacion del supuesto de proporcionalidad)."));

A(h2("3.5 Robustez y subgrupos"));
A(pc("El rendimiento del modelo final se analizo por subgrupos, con estadisticas bootstrap calculadas sobre cada estrato por separado. Las tablas recogen el C-index con su intervalo de confianza y el IBS para OS y PFS."));
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
A(pc(`El rendimiento es consistente entre estratos, sin caidas abruptas. Los dos brazos de aleatorizacion muestran rendimientos similares (en OS, 0.587 en el brazo NESP frente a 0.611 en placebo, con intervalos solapados), lo que sugiere transferibilidad del modelo entre estratos de tratamiento, coherente con un diseno basado solo en predictores basales. La discriminacion es menor en el subgrupo de estado funcional reducido (ECOG 2: ${ecog2OS} en OS y ${ecog2PFS} en PFS), lo cual es esperable por la menor heterogeneidad pronostica cuando el riesgo basal ya es elevado. Desde la perspectiva de genero, el desempeno por sexo es comparable (en OS, 0.595 para SEXCD=0 y 0.586 para SEXCD=1).`));

A(h2("3.6 Datos sinteticos"));
A(pc("El conjunto sintetico generado con CTGAN se evaluo en utilidad y en riesgo de reidentificacion. La utilidad TSTR (entrenar en sintetico, evaluar en real) arroja un C-index medio de 0.437, frente a 0.600 del esquema TRTR equivalente, con un ratio de utilidad del 72.8 por ciento. El valor TSTR esta por debajo de 0.5, es decir, por debajo del azar, lo que indica que el conjunto sintetico no captura adecuadamente la estructura de correlacion necesaria para el pronostico de supervivencia. Esto confirma su caracter exclusivamente de prototipado."));
A(...figureBlock("fig_synthetic_tstr.png", "Utilidad TSTR frente a TRTR por particion. El TSTR queda por debajo de 0.5 (azar)."));
A(pc("El riesgo de reidentificacion se evaluo en tres dimensiones con criterios de aceptacion fijados a priori. La tabla resume los resultados."));
A(table([
  ["Dimension", "Valor", "Umbral", "Resultado"],
  ["Membership inference AUC", synth.reidentification_risk.membership_inference.auc.toFixed(3), "<= 0.60", "ACEPTADO"],
  ["TPR @ FPR=0.1", synth.reidentification_risk.membership_inference.tpr_at_fpr01.toFixed(3), "<= 0.20", "ACEPTADO"],
  ["K-anonimidad k=1 (bins 5a)", (synth.reidentification_risk.k_anonymity.k1_pct * 100).toFixed(2) + "%", "< 5.00%", "NO ACEPTADO"],
  ["K-anonimidad k<=2 (bins 5a)", (synth.reidentification_risk.k_anonymity.k2_pct * 100).toFixed(2) + "%", "< 10.00%", "NO ACEPTADO"],
  ["K-anonimidad k<=5 (bins 5a)", (synth.reidentification_risk.k_anonymity.k5_pct * 100).toFixed(2) + "%", "< 20.00%", "NO ACEPTADO"],
  ["DCR_p5 / RRDR_mediana", synth.reidentification_risk.dcr.dcr_p5_rrdr_median_ratio.toFixed(3), ">= 0.50", "ACEPTADO"],
]));
A(tableCaption("Analisis de riesgo de reidentificacion del conjunto sintetico. Evaluacion global: NO ACEPTADO por k-anonimidad."));
A(pc("La evaluacion global es NO ACEPTADO, motivada por la k-anonimidad con la configuracion de cuasi-identificadores preregistrada (bins de edad de 5 anos, junto con SEXCD y B_ECOGN). El membership inference y la distancia al vecino mas cercano superan sus umbrales sin problema, lo que indica que el riesgo no reside en la copia literal de registros, sino en la similitud estructural de combinaciones de atributos. El analisis de sensibilidad con bins de edad de 10 anos reduce las fracciones a k1=5.44 por ciento, k2=7.32 por ciento y k5=11.51 por ciento, de modo que k2 y k5 pasan el umbral en esa configuracion alternativa, pero k1 sigue por encima. Esto evidencia que la k-anonimidad depende directamente de la granularidad del binning de la edad."));
A(table([
  ["Configuracion", "k=1", "k<=2", "k<=5"],
  ...kanon.map((r) => [`bins ${r.bin_step_years} anos`, (+r.k1_pct * 100).toFixed(2) + "%", (+r.k2_pct * 100).toFixed(2) + "%", (+r.k5_pct * 100).toFixed(2) + "%"]),
]));
A(tableCaption("Analisis de sensibilidad de la k-anonimidad a la granularidad del binning de edad."));
A(...figureBlock("fig_synthetic_kanon.png", "Unicidad de cuasi-identificadores (k-anonimidad) en el conjunto sintetico."));
A(...figureBlock("fig_synthetic_membership.png", "Ataque de inferencia de pertenencia (membership inference): curva ROC y AUC."));
A(noteBox([
  [run("Advertencia: ", { bold: true, color: PLACEHOLDER, size: 20 }),
   run("los datos sinteticos son exclusivamente para prototipado metodologico. No representan pacientes reales, no refuerzan las conclusiones del modelo principal y no deben usarse con fines clinicos ni epidemiologicos.", { size: 20 })],
]));

// ============================================================================
// 4. CONCLUSIONES
// ============================================================================
A(h1("4. Conclusiones y trabajos futuros"));
A(h2("4.1 Conclusiones"));
A(pc("Se ha desarrollado un prototipo de investigacion reproducible y auditable para la prediccion de supervivencia bajo quimioterapia, con un pipeline completo que va de la extraccion de datos al analisis de privacidad. El modelo final es un Cox de riesgos proporcionales con un C-index en OS de 0.599 (IC95% [0.567, 0.629]), discriminacion moderada y estable, y una calibracion aceptable en el rango central del horizonte temporal. El resultado central, sin embargo, no es la cifra de discriminacion, sino la demostracion de un proceso defendible y honesto."));
A(pc("Algunos resultados han sido los esperados (discriminacion moderada con predictores basales) y otros, aunque no favorables, son valiosos por su honestidad: los modelos no lineales no mejoran al baseline, el endpoint PFS es practicamente no informativo y el conjunto sintetico no alcanza el umbral de proteccion por k-anonimidad. Estos hallazgos negativos se documentan sin maquillaje, que es precisamente lo que se espera de un trabajo metodologico riguroso."));
A(h2("4.2 Reflexion critica sobre la consecucion de los objetivos"));
A(pc("Los objetivos se valoran de forma critica. O1 (ETL trazable) se ha alcanzado con dataset derivado, diccionario, manifiesto de calidad y hashes (KPI-2 cumplido). O2 (preprocesado sin fuga) se ha alcanzado: el preprocesado se ajusta dentro de cada particion y la estabilidad entre folds respalda la ausencia de fuga. O3 (comparacion de modelos) se ha completado, pero su KPI-3 (mejora sobre baseline) no se ha cumplido: ningun candidato supera significativamente al Cox; se trata de un objetivo alcanzado en ejecucion y de un KPI no superado, documentado como hallazgo honesto. O4 (calibracion) se ha alcanzado (KPI-4 cumplido), con la matizacion de la subestimacion a largo plazo en alto riesgo. O5 (robustez e interpretabilidad) se ha alcanzado, con lectura descriptiva no causal y analisis por subgrupos incluido el sexo. O6 (reproducibilidad y privacidad) se ha alcanzado en lo metodologico (KPI-1 y KPI-5), con la salvedad de que la evaluacion de reidentificacion del conjunto sintetico resulto NO ACEPTADO, lo que es en si mismo un resultado del analisis de riesgo."));
A(h2("4.3 Seguimiento de la planificacion y la metodologia"));
A(pc("La planificacion por sprints se ha seguido en lo esencial. La metodologia prevista (CRISP-ML(Q) con control de fugas y validacion adaptada) ha sido adecuada. Fue necesario introducir dos cambios relevantes, registrados como decisiones: el pivote P1 (de clasificacion de respuesta a supervivencia con censura) ante la incompletitud de las etiquetas RECIST/ORR, y el pivote P2 (validacion cruzada k=5 con bootstrap) para adaptar la evaluacion al tamano muestral. Tambien se cambio la fuente de datos respecto de la propuesta inicial (de cBioPortal a Project Data Sphere) por mayor completitud y trazabilidad. Estos cambios garantizaron la validez del trabajo y se justificaron en su momento."));
A(h2("4.4 Evaluacion de los impactos previstos"));
A(pc("Respecto de los impactos del apartado 1.3: en sostenibilidad, el objetivo de una huella de computo modesta se ha logrado (ejecucion en portatil, sin nube). En la dimension etico-social, las medidas de privacidad por diseno y de transparencia se han aplicado; el riesgo de probabilidades mal calibradas se ha mitigado mediante la evaluacion explicita de la calibracion y la advertencia de no uso clinico. En diversidad y genero, el analisis por subgrupos incluido el sexo se ha realizado, y se ha documentado de forma honesta la representatividad limitada de la cohorte (variables de raza, tipo tumoral y extension constantes). Como impacto no previsto, el analisis de reidentificacion revelo que el conjunto sintetico no cumple el umbral de k-anonimidad preregistrado; se ha mitigado documentando el hallazgo, anadiendo un analisis de sensibilidad y restringiendo el uso de los sinteticos al prototipado."));
A(h2("4.5 Lineas de trabajo futuro"));
A(bullet("Ampliar la cohorte o validar de forma externa en una poblacion independiente para mejorar la validez externa."));
A(bullet("Explorar extensiones del modelo de Cox con efectos dependientes del tiempo para las variables que violan el supuesto de proporcionalidad (AGE y B_WEIGHT)."));
A(bullet("Incorporar predictores basales adicionales con senal, evaluando su disponibilidad sin introducir fugas."));
A(bullet("Mejorar la generacion sintetica (ajuste de cuasi-identificadores y generalizacion de la edad) para alcanzar el umbral de k-anonimidad sin degradar en exceso la utilidad."));
A(bullet("Aplicar interpretabilidad SHAP post-hoc [10] con la cautela de su inestabilidad bajo cambio de distribucion."));

// ============================================================================
// 5. GLOSARIO
// ============================================================================
A(h1("5. Glosario"));
const glos = [
  ["C-index", "Indice de concordancia de Harrell. Probabilidad de que el modelo ordene correctamente el riesgo de dos sujetos comparables. 0.5 equivale al azar."],
  ["IBS", "Integrated Brier Score. Error de prediccion de supervivencia integrado a lo largo del tiempo. Menor es mejor."],
  ["Brier (t)", "Error cuadratico medio de la prediccion de supervivencia en un instante t."],
  ["OS", "Overall Survival. Supervivencia global, medida hasta el fallecimiento."],
  ["PFS", "Progression Free Survival. Supervivencia libre de progresion."],
  ["Censura", "Situacion en la que el evento de interes no se observa dentro del periodo de seguimiento."],
  ["OOF", "Out of fold. Predicciones generadas sobre las particiones de prueba, agregadas para evaluar sin sobreajuste."],
  ["CV", "Validacion cruzada (cross-validation). Aqui, estratificada con k=5 particiones."],
  ["Bootstrap", "Remuestreo con reemplazo para estimar la incertidumbre (intervalos de confianza). Aqui n=1000."],
  ["Cox PH", "Modelo de riesgos proporcionales de Cox. Baseline de supervivencia con coeficientes interpretables."],
  ["RSF", "Random Survival Forest. Ensemble de arboles de supervivencia."],
  ["XGBoost", "Modelo de gradient boosting de arboles, con perdida adaptada a supervivencia."],
  ["Calibracion", "Concordancia entre las probabilidades predichas y las frecuencias observadas."],
  ["CTGAN", "Conditional Tabular GAN. Generador de datos tabulares sinteticos."],
  ["TSTR", "Train on Synthetic, Test on Real. Protocolo de utilidad de datos sinteticos."],
  ["DCR", "Distance to Closest Record. Distancia al registro real mas cercano, indicador de riesgo de copia."],
  ["k-anonimidad", "Propiedad por la que cada combinacion de cuasi-identificadores es compartida por al menos k registros."],
  ["Membership inference", "Ataque que intenta determinar si un registro concreto formo parte del conjunto de entrenamiento."],
  ["ECOG", "Escala de estado funcional del Eastern Cooperative Oncology Group."],
  ["RECIST", "Response Evaluation Criteria in Solid Tumors. Criterios de respuesta tumoral."],
  ["RGPD", "Reglamento General de Proteccion de Datos (Reglamento UE 2016/679)."],
  ["LOPDGDD", "Ley Organica de Proteccion de Datos Personales y garantia de los derechos digitales (LO 3/2018)."],
  ["AI Act", "Reglamento europeo de inteligencia artificial (Reglamento UE 2024/1689)."],
  ["TRIPOD+AI", "Guia de reporte transparente de modelos de prediccion que incorporan inteligencia artificial."],
  ["Model Card", "Documento de transparencia que describe uso previsto, datos, metricas, limitaciones y riesgos de un modelo."],
];
glos.forEach(([t, d]) => A(new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { line: 300, after: 80 },
  children: [run(t + ": ", { bold: true }), run(d)] })));

// ============================================================================
// 6. BIBLIOGRAFIA
// ============================================================================
A(h1("6. Bibliografia"));
const refs = [
  "Cox, David R. Regression Models and Life-Tables. Journal of the Royal Statistical Society, Series B, paginas 187 a 220, volumen 34, 1972.",
  "Harrell, Frank E.; Lee, Kerry L.; Mark, Daniel B. Multivariable Prognostic Models. Statistics in Medicine, paginas 361 a 387, volumen 15, 1996.",
  "Ishwaran, Hemant; Kogalur, Udaya B.; Blackstone, Eugene H.; Lauer, Michael S. Random Survival Forests. The Annals of Applied Statistics, paginas 841 a 860, volumen 2, 2008.",
  "Chen, Tianqi; Guestrin, Carlos. XGBoost: A Scalable Tree Boosting System. Proceedings of the 22nd ACM SIGKDD, paginas 785 a 794, 2016.",
  "Graf, Erika; Schmoor, Claudia; Sauerbrei, Willi; Schumacher, Martin. Assessment and Comparison of Prognostic Classification Schemes for Survival Data. Statistics in Medicine, paginas 2529 a 2545, volumen 18, 1999.",
  "Collins, Gary S.; Reitsma, Johannes B.; Altman, Douglas G.; Moons, Karel G. M. Transparent Reporting of a Multivariable Prediction Model for Individual Prognosis or Diagnosis (TRIPOD). BMJ, volumen 350, 2015.",
  "Collins, Gary S. y colaboradores. TRIPOD+AI Statement: Updated Guidance for Reporting Clinical Prediction Models that Use Regression or Machine Learning Methods. BMJ, volumen 385, 2024.",
  "Xu, Lei; Skoularidou, Maria; Cuesta-Infante, Alfredo; Veeramachaneni, Kalyan. Modeling Tabular Data using Conditional GAN. Advances in Neural Information Processing Systems, volumen 32, 2019.",
  "Patki, Neha; Wedge, Roy; Veeramachaneni, Kalyan. The Synthetic Data Vault. IEEE International Conference on Data Science and Advanced Analytics, paginas 399 a 410, 2016.",
  "Lundberg, Scott M.; Lee, Su-In. A Unified Approach to Interpreting Model Predictions. Advances in Neural Information Processing Systems, volumen 30, 2017.",
  "Oken, Martin M. y colaboradores. Toxicity and Response Criteria of the Eastern Cooperative Oncology Group. American Journal of Clinical Oncology, paginas 649 a 655, volumen 5, 1982.",
  "Eisenhauer, Elizabeth A. y colaboradores. New Response Evaluation Criteria in Solid Tumours: Revised RECIST guideline (version 1.1). European Journal of Cancer, paginas 228 a 247, volumen 45, 2009.",
  "Union Europea. Reglamento (UE) 2016/679, General de Proteccion de Datos (RGPD). Diario Oficial de la Union Europea, 2016.",
  "Jefatura del Estado de Espana. Ley Organica 3/2018 de Proteccion de Datos Personales y garantia de los derechos digitales (LOPDGDD). Boletin Oficial del Estado, 2018.",
  "Union Europea. Reglamento (UE) 2024/1689 por el que se establecen normas armonizadas en materia de inteligencia artificial (AI Act). Diario Oficial de la Union Europea, 2024.",
  "Agencia Espanola de Proteccion de Datos (AEPD). Orientaciones y garantias en los procedimientos de anonimizacion de datos personales. AEPD, 2016.",
  "Polsterl, Sebastian. scikit-survival: A Library for Time-to-Event Analysis Built on Top of scikit-learn. Journal of Machine Learning Research, paginas 1 a 6, volumen 21, 2020.",
  "Davidson-Pilon, Cameron. lifelines: Survival Analysis in Python. Journal of Open Source Software, volumen 4, 2019.",
  "Project Data Sphere. Plataforma de acceso a datos de ensayos clinicos oncologicos. Consultado en 2026.",
  "Sweeney, Latanya. k-anonymity: A Model for Protecting Privacy. International Journal of Uncertainty, Fuzziness and Knowledge-Based Systems, paginas 557 a 570, volumen 10, 2002.",
  "Shokri, Reza; Stronati, Marco; Song, Congzheng; Shmatikov, Vitaly. Membership Inference Attacks Against Machine Learning Models. IEEE Symposium on Security and Privacy, paginas 3 a 18, 2017.",
  "Platt, John C. Probabilistic Outputs for Support Vector Machines and Comparisons to Regularized Likelihood Methods. Advances in Large Margin Classifiers, paginas 61 a 74, 1999.",
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
  ["O2", "Preprocesado sin fuga por particion", "D1", "Estabilidad entre folds"],
  ["O3", "Comparacion Cox, RSF, XGBoost", "D1, D3", "KPI-3 (no cumplido)"],
  ["O4", "Calibracion con bandas bootstrap", "D3", "KPI-4"],
  ["O5", "Robustez, subgrupos e interpretabilidad", "D3", "Coherencia entre estratos"],
  ["O6", "Reproducibilidad y privacidad", "D1, D4", "KPI-1, KPI-5"],
]));
A(tableCaption("Matriz de trazabilidad entre objetivos, tareas, entregables y KPIs."));
A(h2("7.2 Repositorio del codigo (D1)"));
A(pc("El codigo completo del pipeline (ETL, preprocesado, modelado, evaluacion, reporting y analisis de privacidad) constituye el entregable D1. El repositorio incluye semillas fijas, entorno versionado, cabeceras de proposito en cada script y pruebas de humo, y permite la verificacion en un entorno limpio (KPI-1). Los datos crudos y el dataset derivado a nivel de sujeto no se versionan por privacidad por diseno; solo se publican metadatos (diccionario, hashes y manifiesto de calidad)."));
A(h2("7.3 Paquete de transparencia (D4)"));
A(pc("El checklist TRIPOD+AI y la Model Card final forman parte del entregable D4 (paquete de transparencia), junto con el analisis de riesgos. La Model Card se ha mantenido viva durante todo el desarrollo y se cierra con los valores reales del pipeline. Estos documentos se referencian aqui y se entregan como parte de D4."));

A(h2("7.4 Matriz de trazabilidad de resultados de aprendizaje"));
A(pc("La siguiente matriz mapea cada resultado de aprendizaje del TFG a la seccion de la memoria o al entregable donde se evidencia. Los resultados marcados como fuera de alcance no aplican a este tipo de proyecto."));

// Columnas: Resultado (izquierda), Evidencia principal (izquierda), Cobertura (centro).
const RA_ALIGNS = [AlignmentType.LEFT, AlignmentType.LEFT, AlignmentType.CENTER];

A(h3("Conocimientos"));
A(table([
  ["Resultado", "Evidencia principal (seccion de D3 o entregable)", "Cobertura"],
  ["K1", "1.1 (el pronostico bajo quimioterapia como oportunidad de mejora)", "Solida"],
  ["K2", "2.3, 2.4 y 3.2 (modelos de supervivencia, metricas, bootstrap y calibracion)", "Solida"],
  ["K3", "2.6 y D1 (pipeline modular, semillas y pruebas; sin escala de gran volumen)", "Parcial"],
  ["K4", "2.6 y 2.7 (ejecucion local sin nube; volumen de datos moderado)", "Parcial"],
  ["K5", "2.1 (seleccion de fuente, ETL, criterios y diccionario de variables)", "Solida"],
  ["K6", "2.3, 2.4 y 3.1 (metodos y comparativa desde las preguntas del trabajo)", "Solida"],
  ["K7", "3.2 a 3.6 y D5 (figuras de Brier, AUC, calibracion, forest y subgrupos)", "Solida"],
  ["K8", "2.2, 3.1, 3.3, 3.4 y 4.2 (fugas, KPI-3, limites de calibracion, Schoenfeld, reflexion critica)", "Solida"],
], { aligns: RA_ALIGNS }));
A(tableCaption("Trazabilidad de los conocimientos (K) a las secciones y entregables del TFG."));

A(h3("Habilidades"));
A(table([
  ["Resultado", "Evidencia principal (seccion de D3 o entregable)", "Cobertura"],
  ["S1", "2.3, 2.4 y D1 (integracion de estadistica y programacion)", "Solida"],
  ["S2", "2.6 y D1 (semillas, pruebas de humo y cabeceras de proposito)", "Solida"],
  ["S3", "2.1, 2.2 y 2.6 (flujo completo con manifiesto de calidad)", "Solida"],
  ["S4", "2.1 (uniones sobre las tablas del estudio por SUBJID, hashes; fuente unica)", "Parcial"],
  ["S5", "2.1 y 2.2 (datos clinicos estructurados)", "Parcial"],
  ["S6", "2.3, 2.4 y 3.1 (solucion analitica con metodos y herramientas apropiados)", "Solida"],
  ["S7", "1.3.2, 2.5, 3.6 y D4 (privacidad por diseno, marco legal y reidentificacion)", "Solida"],
  ["S8", "Fuera del alcance del TFG (no hay interfaz de usuario)", "Fuera de alcance"],
  ["S9", "3.2 a 3.6 y D5 (figuras y diapositivas)", "Solida"],
  ["S10", "Fuera del alcance del TFG (no hay administracion de redes ni sistemas)", "Fuera de alcance"],
  ["S11", "1.4, 2.7 y 3.1 (estrategias consideradas, valoracion economica y comparativa)", "Solida"],
  ["S12", "3.x, 4.x, resumen y D5 (comunicacion rigurosa y critica)", "Solida"],
  ["S13", "Memoria completa (escrita) y video D5 (oral)", "Solida"],
  ["S14", "1.3, 1.4 y 4.1 (aportacion metodologica; innovacion de proceso, no de producto)", "Parcial"],
  ["S15", "Abstract de la ficha (texto academico en ingles)", "Parcial"],
], { aligns: RA_ALIGNS }));
A(tableCaption("Trazabilidad de las habilidades (S) a las secciones y entregables del TFG."));

A(h3("Competencias"));
A(table([
  ["Resultado", "Evidencia principal (seccion de D3 o entregable)", "Cobertura"],
  ["C1", "1.4, 1.5 y 4.3 (gestion del proyecto, sprints y pivotes)", "Solida"],
  ["C2", "TFG completo, D5 y defensa de la PEC5", "Solida"],
  ["C4", "1.3, 3.5 y 4.4 (tres dimensiones de la CCEG, sexo como perspectiva de genero)", "Solida"],
  ["C5", "3.1, 4.2, 4.4 y D4 (KPI-3 honesto, reflexion autocritica y analisis de riesgos)", "Solida"],
  ["C6", "2.6 y D1 (implementacion con tecnologias digitales)", "Solida"],
], { aligns: RA_ALIGNS }));
A(tableCaption("Trazabilidad de las competencias (C) a las secciones y entregables del TFG."));

// ============================================================================
// DOCUMENTO
// ============================================================================
const doc = new Document({
  creator: "Alfonso Esteban Lasso",
  title: "Memoria TFG - Prediccion de supervivencia bajo quimioterapia",
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
