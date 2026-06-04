// build_d5.js
// Propósito: generar el entregable D5 (presentación de defensa) en formato .pptx.
// Entradas: figuras de output/ y valores reales de docs/model_card.md y docs/decision_log.md.
// Salida: output/D5_presentacion.pptx.
// Regla del proyecto: fuente Arial, paleta corporativa, sin guiones largos.

import pptxgen from "pptxgenjs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..", "..");
const OUT = path.join(ROOT, "output");
const fig = (name) => path.join(OUT, name);

const FONT = "Arial";
const C = {
  blueDark: "1F4E79",
  blueMid: "2E6CA4",
  blueLight: "D5E8F0",
  blueWash: "EEF5FB",
  green: "1F7A3A",
  amber: "B7791F",
  grayText: "44474B",
  white: "FFFFFF",
  rule: "C9D6E2",
};

const pres = new pptxgen();
pres.defineLayout({ name: "W", width: 13.333, height: 7.5 });
pres.layout = "W";
pres.author = "Alfonso Esteban Lasso";
pres.title = "TFG NESP - Defensa (D5)";

const W = 13.333;
const H = 7.5;
const MX = 0.7; // margen lateral

// ---------- helpers ----------

// Cabecera de diapositiva de contenido: número, título y motivo (kicker).
function header(slide, kicker, title, n) {
  slide.background = { color: C.white };
  // motivo visual repetido: pequeño cuadrado azul a la izquierda del kicker
  slide.addShape(pres.shapes.RECTANGLE, {
    x: MX, y: 0.55, w: 0.16, h: 0.16, fill: { color: C.amber }, line: { type: "none" },
  });
  slide.addText(kicker.toUpperCase(), {
    x: MX + 0.28, y: 0.46, w: 10, h: 0.34, fontFace: FONT, fontSize: 12,
    color: C.amber, bold: true, charSpacing: 2, align: "left", valign: "middle", margin: 0,
  });
  slide.addText(title, {
    x: MX, y: 0.82, w: W - 2 * MX - 1.0, h: 0.9, fontFace: FONT, fontSize: 28,
    color: C.blueDark, bold: true, align: "left", valign: "top", margin: 0,
  });
  // número de diapositiva (esquina superior derecha)
  slide.addText(String(n).padStart(2, "0"), {
    x: W - 1.3, y: 0.46, w: 0.9, h: 0.4, fontFace: FONT, fontSize: 13,
    color: C.blueLight, bold: true, align: "right", valign: "middle", margin: 0,
  });
}

// Pie discreto con identificación.
function footer(slide) {
  slide.addText("TFG - Predicción de supervivencia bajo quimioterapia | Grado en Ciencia de Datos Aplicada | UOC 2025.1", {
    x: MX, y: H - 0.42, w: W - 2 * MX, h: 0.3, fontFace: FONT, fontSize: 8.5,
    color: "9AA7B4", align: "left", valign: "middle", margin: 0,
  });
}

// Tarjeta rectangular con sombra suave.
function card(slide, x, y, w, h, fill) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h, fill: { color: fill || C.blueWash }, line: { color: C.rule, width: 0.75 },
    shadow: { type: "outer", color: "1F4E79", blur: 7, offset: 2, angle: 90, opacity: 0.1 },
  });
}

// Imagen contenida en una caja, preservando proporción (centrada).
function figureBox(slide, file, x, y, w, h) {
  slide.addImage({ path: file, x, y, w, h, sizing: { type: "contain", w, h } });
}

// ---------- 1. Portada ----------
{
  const s = pres.addSlide();
  s.background = { color: C.blueDark };
  // motivo: banda inferior azul claro fina como línea de acento de marca
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.28, h: H, fill: { color: C.amber }, line: { type: "none" } });
  s.addText("TRABAJO FINAL DE GRADO", {
    x: 1.0, y: 1.25, w: 11.3, h: 0.4, fontFace: FONT, fontSize: 14, color: C.blueLight,
    bold: true, charSpacing: 3, align: "left", margin: 0,
  });
  s.addText("Predicción de respuesta a fármacos quimioterapéuticos a partir de datos clínicos anonimizados", {
    x: 1.0, y: 1.75, w: 11.0, h: 1.7, fontFace: FONT, fontSize: 34, color: C.white,
    bold: true, align: "left", valign: "top", margin: 0,
  });
  s.addText("Prototipo de investigación reproducible y auditable para predecir supervivencia bajo quimioterapia", {
    x: 1.0, y: 3.5, w: 11.0, h: 0.6, fontFace: FONT, fontSize: 16, color: C.blueLight,
    italic: true, align: "left", margin: 0,
  });
  // bloque autoría
  s.addShape(pres.shapes.LINE, { x: 1.0, y: 4.55, w: 6.2, h: 0, line: { color: C.blueMid, width: 1 } });
  s.addText([
    { text: "Estudiante:  ", options: { bold: true, color: C.blueLight } },
    { text: "Alfonso Esteban Lasso", options: { color: C.white } },
    { text: "\nTutor:  ", options: { bold: true, color: C.blueLight } },
    { text: "Tutor del TFG", options: { color: C.white } },
    { text: "\nTitulacion:  ", options: { bold: true, color: C.blueLight } },
    { text: "Grado en Ciencia de Datos Aplicada", options: { color: C.white } },
    { text: "\nSemestre:  ", options: { bold: true, color: C.blueLight } },
    { text: "2025.1", options: { color: C.white } },
  ], { x: 1.0, y: 4.75, w: 9.0, h: 1.7, fontFace: FONT, fontSize: 15, align: "left", valign: "top", lineSpacingMultiple: 1.25, margin: 0 });
  s.addText("Defensa PEC4 | 02/06/2026", {
    x: W - 5.0, y: H - 0.7, w: 4.3, h: 0.4, fontFace: FONT, fontSize: 12, color: C.blueLight,
    align: "right", margin: 0,
  });
}

// ---------- 2. Problema y motivación ----------
{
  const s = pres.addSlide();
  header(s, "Problema y motivación", "Pronóstico de supervivencia con transparencia", 2);
  const bx = MX, bw = 7.0;
  s.addText([
    { text: "La quimioterapia tiene una respuesta heterogénea entre pacientes y un pronóstico difícil de anticipar a partir de variables clínicas basales.", options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 10 } },
    { text: "Los modelos predictivos en oncología suelen carecer de trazabilidad, auditabilidad y control explícito de fugas de información.", options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 10 } },
    { text: "El objetivo no es un dispositivo clínico, sino un prototipo de investigación reproducible que prediga supervivencia y documente todo el proceso.", options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 10 } },
    { text: "La motivación es metodológica: demostrar un pipeline honesto, reproducible y conforme al marco regulatorio europeo.", options: { bullet: { code: "2022" } } },
  ], { x: bx, y: 2.0, w: bw, h: 3.6, fontFace: FONT, fontSize: 16.5, color: C.grayText, align: "left", valign: "top", lineSpacingMultiple: 1.1, margin: 0 });

  // tarjeta lateral con la idea fuerza
  const cx = bx + bw + 0.5, cw = W - MX - cx;
  card(s, cx, 2.0, cw, 3.5, C.blueDark);
  s.addText("Idea fuerza", { x: cx + 0.35, y: 2.3, w: cw - 0.7, h: 0.4, fontFace: FONT, fontSize: 13, color: C.amber, bold: true, charSpacing: 2, margin: 0 });
  s.addText("Reproducibilidad y honestidad antes que rendimiento.", {
    x: cx + 0.35, y: 2.75, w: cw - 0.7, h: 1.6, fontFace: FONT, fontSize: 22, color: C.white, bold: true, valign: "top", margin: 0,
  });
  s.addText("Un resultado bien documentado, aunque modesto, vale más que una cifra brillante sin trazabilidad.", {
    x: cx + 0.35, y: 4.35, w: cw - 0.7, h: 1.0, fontFace: FONT, fontSize: 13, color: C.blueLight, italic: true, valign: "top", margin: 0,
  });
  footer(s);
}

// ---------- 3. Objetivos y KPIs ----------
{
  const s = pres.addSlide();
  header(s, "Objetivos y KPIs", "Cinco indicadores de éxito", 3);
  s.addText("Objetivo general: construir y auditar un pipeline reproducible de predicción de supervivencia (OS y PFS) bajo quimioterapia, con evaluación ético-legal explícita.", {
    x: MX, y: 1.95, w: W - 2 * MX, h: 0.8, fontFace: FONT, fontSize: 15, color: C.grayText, valign: "top", margin: 0,
  });
  const kpis = [
    ["KPI-1", "Reproducibilidad", "Entorno limpio y versiones congeladas", C.green, "Cumplido"],
    ["KPI-2", "Calidad de datos", "Diccionario, hashes y manifiesto", C.green, "Cumplido"],
    ["KPI-3", "Rendimiento", "Mejora sobre baseline Cox", C.amber, "No cumplido"],
    ["KPI-4", "Calibración", "Fiabilidad de la supervivencia", C.green, "Cumplido"],
    ["KPI-5", "Evaluación ético-legal", "RGPD, AI Act, AEPD", C.green, "Cumplido"],
  ];
  const n = kpis.length;
  const gap = 0.3;
  const cw = (W - 2 * MX - gap * (n - 1)) / n;
  const y0 = 3.0, ch = 3.1;
  kpis.forEach((k, i) => {
    const x = MX + i * (cw + gap);
    card(s, x, y0, cw, ch, C.white);
    s.addShape(pres.shapes.RECTANGLE, { x, y: y0, w: cw, h: 0.12, fill: { color: k[3] }, line: { type: "none" } });
    s.addText(k[0], { x: x + 0.18, y: y0 + 0.32, w: cw - 0.36, h: 0.4, fontFace: FONT, fontSize: 18, color: C.blueDark, bold: true, margin: 0 });
    s.addText(k[1], { x: x + 0.18, y: y0 + 0.85, w: cw - 0.36, h: 0.8, fontFace: FONT, fontSize: 14.5, color: C.grayText, bold: true, valign: "top", margin: 0 });
    s.addText(k[2], { x: x + 0.18, y: y0 + 1.6, w: cw - 0.36, h: 0.9, fontFace: FONT, fontSize: 11.5, color: "6B7178", valign: "top", margin: 0 });
    s.addText(k[4], { x: x + 0.18, y: y0 + ch - 0.5, w: cw - 0.36, h: 0.36, fontFace: FONT, fontSize: 12, color: k[3], bold: true, margin: 0 });
  });
  s.addText("KPI-3 se documenta como hallazgo honesto, no como fracaso. Se explica más adelante.", {
    x: MX, y: y0 + ch + 0.2, w: W - 2 * MX, h: 0.4, fontFace: FONT, fontSize: 12.5, color: C.amber, italic: true, margin: 0,
  });
  footer(s);
}

// ---------- 4. Datos y cohorte ----------
{
  const s = pres.addSlide();
  header(s, "Datos y cohorte", "Project Data Sphere, estudio NESP", 4);
  // estadísticos grandes
  const stats = [
    ["479", "sujetos\n(una fila por sujeto)"],
    ["397", "eventos OS (83%)\n82 censurados"],
    ["440", "eventos PFS (92%)\n39 censurados"],
    ["7", "predictores\nbasales con señal"],
  ];
  const n = stats.length, gap = 0.3;
  const cw = (W - 2 * MX - gap * (n - 1)) / n;
  const y0 = 2.0, ch = 1.85;
  stats.forEach((st, i) => {
    const x = MX + i * (cw + gap);
    card(s, x, y0, cw, ch, C.blueWash);
    s.addText(st[0], { x: x + 0.1, y: y0 + 0.18, w: cw - 0.2, h: 0.9, fontFace: FONT, fontSize: 40, color: C.blueDark, bold: true, align: "center", margin: 0 });
    s.addText(st[1], { x: x + 0.1, y: y0 + 1.05, w: cw - 0.2, h: 0.7, fontFace: FONT, fontSize: 11.5, color: C.grayText, align: "center", valign: "top", margin: 0 });
  });
  // bloque texto inferior
  s.addText([
    { text: "Fuente: ", options: { bold: true, color: C.blueDark } },
    { text: "Project Data Sphere, estudio NESP-Oncology-20010145 (ensayo NCT00119613). Régimen quimioterapéutico homogéneo y seguimiento trazable.", options: { color: C.grayText } },
  ], { x: MX, y: 4.2, w: W - 2 * MX, h: 0.7, fontFace: FONT, fontSize: 14.5, valign: "top", margin: 0, lineSpacingMultiple: 1.1 });

  card(s, MX, 5.0, W - 2 * MX, 1.55, "FBF3E3");
  s.addShape(pres.shapes.RECTANGLE, { x: MX, y: 5.0, w: 0.12, h: 1.55, fill: { color: C.amber }, line: { type: "none" } });
  s.addText("Cambio de fuente documentado", { x: MX + 0.35, y: 5.18, w: W - 2 * MX - 0.6, h: 0.4, fontFace: FONT, fontSize: 14, color: C.amber, bold: true, margin: 0 });
  s.addText("La propuesta inicial contemplaba cBioPortal. Se cambio a Project Data Sphere por variables de outcome más completas y trazables, homogeneidad del régimen y trazabilidad temporal del seguimiento. El ensayo es de fase III; el TFG lo reformula como pronóstico bajo quimioterapia y no estudia el efecto del agente eritropoyético.", {
    x: MX + 0.35, y: 5.55, w: W - 2 * MX - 0.6, h: 0.95, fontFace: FONT, fontSize: 12.5, color: C.grayText, valign: "top", margin: 0, lineSpacingMultiple: 1.05,
  });
  footer(s);
}

// ---------- 5. Método ----------
{
  const s = pres.addSlide();
  header(s, "Método", "Diseño adaptado y control de fugas", 5);
  const items = [
    ["Pivote P1", "De clasificación de respuesta (RECIST/ORR, con exceso de faltantes) a supervivencia con censura: OS y PFS."],
    ["Pivote P2", "Validación adaptada a n=479: validación cruzada estratificada k=5 con bootstrap de n=1000."],
    ["Brazo NESP/placebo", "Variable de estratificación, nunca predictor ni objeto causal. Permite análisis de transferibilidad."],
    ["Control de fugas", "Todo el preprocesado se ajusta solo dentro de cada fold de entrenamiento. Solo predictores basales."],
    ["Criterio a priori", "Selección fijada antes de ver resultados: C-index más IBS más coeficiente de variación entre folds."],
  ];
  const y0 = 2.05, rh = 0.95;
  items.forEach((it, i) => {
    const y = y0 + i * rh;
    // círculo numerado
    s.addShape(pres.shapes.OVAL, { x: MX, y: y + 0.05, w: 0.55, h: 0.55, fill: { color: C.blueDark }, line: { type: "none" } });
    s.addText(String(i + 1), { x: MX, y: y + 0.05, w: 0.55, h: 0.55, fontFace: FONT, fontSize: 18, color: C.white, bold: true, align: "center", valign: "middle", margin: 0 });
    s.addText(it[0], { x: MX + 0.8, y: y, w: 3.1, h: 0.65, fontFace: FONT, fontSize: 16, color: C.blueDark, bold: true, valign: "middle", margin: 0 });
    s.addText(it[1], { x: MX + 4.0, y: y, w: W - MX - (MX + 4.0), h: 0.8, fontFace: FONT, fontSize: 13.5, color: C.grayText, valign: "middle", margin: 0, lineSpacingMultiple: 1.0 });
    if (i < items.length - 1) s.addShape(pres.shapes.LINE, { x: MX + 0.8, y: y + rh - 0.07, w: W - 2 * MX - 0.8, h: 0, line: { color: C.rule, width: 0.5 } });
  });
  footer(s);
}

// ---------- 6. Modelos comparados ----------
{
  const s = pres.addSlide();
  header(s, "Modelos comparados", "Cox, Random Survival Forest y XGBoost", 6);
  // gráfico de barras: C-index OS por modelo
  s.addChart(pres.charts.BAR, [{
    name: "C-index OS (CV)", labels: ["Cox PH", "RSF", "XGBoost"], values: [0.600, 0.593, 0.549],
  }], {
    x: MX, y: 2.1, w: 6.6, h: 4.4, barDir: "col",
    chartColors: [C.blueDark, C.blueMid, C.amber],
    valAxisMinVal: 0.5, valAxisMaxVal: 0.65, valAxisMajorUnit: 0.05,
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: "1E293B", dataLabelFontFace: FONT, dataLabelFontSize: 13, dataLabelFontBold: true, dataLabelFormatCode: "0.000",
    catAxisLabelColor: "64748B", catAxisLabelFontFace: FONT, catAxisLabelFontSize: 13,
    valAxisLabelColor: "64748B", valAxisLabelFontFace: FONT, valAxisLabelFontSize: 11,
    valGridLine: { color: "E2E8F0", size: 0.5 }, catGridLine: { style: "none" },
    showLegend: false, showTitle: true, title: "Discriminación en OS (validación cruzada k=5)", titleColor: C.blueDark, titleFontFace: FONT, titleFontSize: 14,
    chartArea: { fill: { color: C.white } },
  });
  // panel derecho con lectura
  const cx = MX + 6.6 + 0.5, cw = W - MX - cx;
  card(s, cx, 2.1, cw, 4.4, C.blueWash);
  s.addText("Lectura", { x: cx + 0.3, y: 2.35, w: cw - 0.6, h: 0.4, fontFace: FONT, fontSize: 13, color: C.amber, bold: true, charSpacing: 2, margin: 0 });
  s.addText([
    { text: "Cox proporcional", options: { bold: true, color: C.blueDark, breakLine: true } },
    { text: "Baseline lineal. C-index OS 0.600, CV entre folds 7.0%.", options: { color: C.grayText, breakLine: true, paraSpaceAfter: 12 } },
    { text: "Random Survival Forest", options: { bold: true, color: C.blueDark, breakLine: true } },
    { text: "C-index 0.593, más estable (CV 4.5%), pero IC bootstrap solapado por completo con Cox.", options: { color: C.grayText, breakLine: true, paraSpaceAfter: 12 } },
    { text: "XGBoost (perdida de supervivencia)", options: { bold: true, color: C.blueDark, breakLine: true } },
    { text: "C-index 0.549. El early stopping activa con 1 a 30 árboles: la señal no sustenta el boosting.", options: { color: C.grayText } },
  ], { x: cx + 0.3, y: 2.8, w: cw - 0.6, h: 3.5, fontFace: FONT, fontSize: 13, valign: "top", margin: 0, lineSpacingMultiple: 1.05 });
  footer(s);
}

// ---------- 7. Resultados y selección ----------
{
  const s = pres.addSlide();
  header(s, "Resultados y selección", "Cox final por parsimonia", 7);
  // izquierda: decisión
  const bw = 6.7;
  s.addText([
    { text: "El modelo final es el Cox proporcional, retenido por parsimonia.", options: { bold: true, color: C.blueDark, breakLine: true, paraSpaceAfter: 12, fontSize: 18 } },
    { text: "Ningún candidato mejora de forma estadísticamente significativa el baseline segun el criterio fijado a priori. Los IC bootstrap de RSF y Cox se solapan por completo (diferencia de C-index = 0.007).", options: { color: C.grayText, breakLine: true, paraSpaceAfter: 10, fontSize: 14.5 } },
    { text: "Con n=479, 7 predictores basales y alta tasa de eventos, la superficie de decisión es prácticamente lineal. Los modelos no lineales no aportan ventaja en esta cohorte.", options: { color: C.grayText, fontSize: 14.5 } },
  ], { x: MX, y: 2.05, w: bw, h: 3.4, fontFace: FONT, valign: "top", margin: 0, lineSpacingMultiple: 1.08 });

  // tarjeta KPI-3
  card(s, MX, 5.55, bw, 1.1, "FBF3E3");
  s.addShape(pres.shapes.RECTANGLE, { x: MX, y: 5.55, w: 0.12, h: 1.1, fill: { color: C.amber }, line: { type: "none" } });
  s.addText([
    { text: "KPI-3 no cumplido. ", options: { bold: true, color: C.amber } },
    { text: "Hallazgo honesto y esperado, documentado como limitación explícita en la memoria y la Model Card.", options: { color: C.grayText } },
  ], { x: MX + 0.35, y: 5.7, w: bw - 0.6, h: 0.85, fontFace: FONT, fontSize: 13, valign: "middle", margin: 0, lineSpacingMultiple: 1.05 });

  // derecha: tabla comparativa
  const cx = MX + bw + 0.5;
  const cw = W - MX - cx;
  const rows = [
    [
      { text: "Modelo", options: { bold: true, color: C.blueDark, fill: { color: C.blueLight }, align: "left" } },
      { text: "C-index OS", options: { bold: true, color: C.blueDark, fill: { color: C.blueLight }, align: "center" } },
      { text: "CV%", options: { bold: true, color: C.blueDark, fill: { color: C.blueLight }, align: "center" } },
      { text: "IBS", options: { bold: true, color: C.blueDark, fill: { color: C.blueLight }, align: "center" } },
    ],
    [
      { text: "Cox PH (final)", options: { bold: true, color: C.blueDark } },
      { text: "0.600", options: { align: "center", bold: true } },
      { text: "7.05", options: { align: "center" } },
      { text: "0.182", options: { align: "center" } },
    ],
    [
      { text: "RSF", options: {} },
      { text: "0.593", options: { align: "center" } },
      { text: "4.54", options: { align: "center" } },
      { text: "0.181", options: { align: "center" } },
    ],
    [
      { text: "XGBoost", options: {} },
      { text: "0.549", options: { align: "center" } },
      { text: "5.50", options: { align: "center" } },
      { text: "0.187", options: { align: "center" } },
    ],
  ];
  s.addTable(rows, {
    x: cx, y: 2.5, w: cw, colW: [cw * 0.4, cw * 0.24, cw * 0.18, cw * 0.18],
    rowH: [0.5, 0.55, 0.55, 0.55], fontFace: FONT, fontSize: 13, color: C.grayText,
    border: { type: "solid", pt: 0.5, color: C.rule }, valign: "middle", align: "left",
    fill: { color: C.white },
  });
  s.addText("IC95% bootstrap Cox [0.567, 0.629] frente a RSF [0.562, 0.621]: solapamiento total.", {
    x: cx, y: 4.85, w: cw, h: 0.8, fontFace: FONT, fontSize: 12, color: "6B7178", italic: true, valign: "top", margin: 0,
  });
  footer(s);
}

// ---------- 8. Rendimiento del modelo final ----------
{
  const s = pres.addSlide();
  header(s, "Rendimiento del modelo final", "OS primario y PFS secundario", 8);
  // tres callouts OS
  const stats = [
    ["C-index OS", "0.599", "IC95% [0.567, 0.629]"],
    ["IBS OS", "0.182", "IC95% [0.172, 0.191]"],
    ["AUC(t) media OS", "0.645", "IC95% [0.601, 0.690]"],
  ];
  const sx = MX, sw = 5.0;
  // colocar callouts en columna izquierda (apilados)
  const y0 = 2.05, ch = 1.0, vg = 0.15;
  stats.forEach((st, i) => {
    const y = y0 + i * (ch + vg);
    card(s, sx, y, sw, ch, C.white);
    s.addShape(pres.shapes.RECTANGLE, { x: sx, y, w: 0.12, h: ch, fill: { color: C.blueDark }, line: { type: "none" } });
    s.addText(st[0], { x: sx + 0.35, y: y + 0.12, w: sw - 0.6, h: 0.32, fontFace: FONT, fontSize: 12.5, color: C.grayText, bold: true, margin: 0 });
    s.addText(st[1], { x: sx + 0.35, y: y + 0.4, w: 2.0, h: 0.55, fontFace: FONT, fontSize: 30, color: C.blueDark, bold: true, margin: 0 });
    s.addText(st[2], { x: sx + 2.35, y: y + 0.5, w: sw - 2.6, h: 0.42, fontFace: FONT, fontSize: 11.5, color: "6B7178", valign: "middle", margin: 0 });
  });
  // PFS nota
  const py = y0 + 3 * (ch + vg);
  card(s, sx, py, sw, 0.95, "FBF3E3");
  s.addShape(pres.shapes.RECTANGLE, { x: sx, y: py, w: 0.12, h: 0.95, fill: { color: C.amber }, line: { type: "none" } });
  s.addText([
    { text: "PFS secundario poco informativo. ", options: { bold: true, color: C.amber } },
    { text: "C-index 0.555 [0.525, 0.586]. La alta tasa de eventos (92%) limita la información de censura.", options: { color: C.grayText } },
  ], { x: sx + 0.35, y: py + 0.1, w: sw - 0.6, h: 0.75, fontFace: FONT, fontSize: 12, valign: "middle", margin: 0, lineSpacingMultiple: 1.05 });

  // figura derecha
  figureBox(s, fig("fig_evaluation_OS.png"), sx + sw + 0.4, 2.05, W - MX - (sx + sw + 0.4), 4.5);
  footer(s);
}

// ---------- 9. Calibración ----------
{
  const s = pres.addSlide();
  header(s, "Calibración (KPI-4)", "Fiable en el rango central, ruidosa en el extremo", 9);
  figureBox(s, fig("fig_calibration_OS.png"), MX, 2.0, 8.0, 4.5);
  const cx = MX + 8.0 + 0.4, cw = W - MX - cx;
  s.addText([
    { text: "t = 164 días", options: { bold: true, color: C.green, breakLine: true } },
    { text: "Bien calibrado. Deciles sobre la diagonal, sin sesgo sistemático.", options: { color: C.grayText, breakLine: true, paraSpaceAfter: 12 } },
    { text: "t = 259 días", options: { bold: true, color: C.green, breakLine: true } },
    { text: "Bien calibrado. La mayoría de deciles dentro de los IC bootstrap.", options: { color: C.grayText, breakLine: true, paraSpaceAfter: 12 } },
    { text: "t = 355 días", options: { bold: true, color: C.amber, breakLine: true } },
    { text: "Tendencia a subestimar la supervivencia en alto riesgo, con dispersión. Coherente con un Cox sin covariables tiempo-dependientes.", options: { color: C.grayText } },
  ], { x: cx, y: 2.05, w: cw, h: 4.4, fontFace: FONT, fontSize: 13.5, valign: "top", margin: 0, lineSpacingMultiple: 1.08 });
  footer(s);
}

// ---------- 10. Interpretabilidad ----------
{
  const s = pres.addSlide();
  header(s, "Interpretabilidad", "Hazard ratios, lectura descriptiva no causal", 10);
  figureBox(s, fig("fig_forest_plot.png"), MX, 2.0, 7.6, 4.5);
  const cx = MX + 7.6 + 0.4, cw = W - MX - cx;
  s.addText("Asociaciones significativas (OS)", { x: cx, y: 2.05, w: cw, h: 0.4, fontFace: FONT, fontSize: 14, color: C.blueDark, bold: true, margin: 0 });
  s.addText([
    { text: "ECOG 2 vs 1:  ", options: { bold: true, color: C.blueDark } },
    { text: "HR 1.693 (p < 0.001). Estado funcional reducido, mayor riesgo.", options: { color: C.grayText, breakLine: true, paraSpaceAfter: 10 } },
    { text: "Sexo = 1 (femenino):  ", options: { bold: true, color: C.blueDark } },
    { text: "HR 0.641 (p < 0.001). Menor riesgo de muerte.", options: { color: C.grayText, breakLine: true, paraSpaceAfter: 10 } },
    { text: "N. sistemas comorbilidad:  ", options: { bold: true, color: C.blueDark } },
    { text: "HR 1.086 por unidad (p = 0.042).", options: { color: C.grayText } },
  ], { x: cx, y: 2.5, w: cw, h: 2.3, fontFace: FONT, fontSize: 13, valign: "top", margin: 0, lineSpacingMultiple: 1.05 });
  card(s, cx, 5.1, cw, 1.4, "FBF3E3");
  s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 5.1, w: 0.12, h: 1.4, fill: { color: C.amber }, line: { type: "none" } });
  s.addText("Las asociaciones son descriptivas, no causales. El ensayo no fue disenado para identificarlas y pueden estar confundidas por factores no medidos.", {
    x: cx + 0.35, y: 5.25, w: cw - 0.6, h: 1.1, fontFace: FONT, fontSize: 12.5, color: C.grayText, valign: "middle", margin: 0, lineSpacingMultiple: 1.05,
  });
  footer(s);
}

// ---------- 11. Robustez y equidad ----------
{
  const s = pres.addSlide();
  header(s, "Robustez y equidad", "Rendimiento por subgrupos", 11);
  figureBox(s, fig("fig_subgroup_cindex.png"), MX, 2.0, 8.2, 4.5);
  const cx = MX + 8.2 + 0.4, cw = W - MX - cx;
  s.addText([
    { text: "Consistencia entre estratos", options: { bold: true, color: C.blueDark, breakLine: true } },
    { text: "Sin caídas abruptas. La discriminación baja en ECOG 2 (OS 0.524) por menor heterogeneidad pronóstica cuando el riesgo basal ya es alto.", options: { color: C.grayText, breakLine: true, paraSpaceAfter: 12 } },
    { text: "Equidad por sexo", options: { bold: true, color: C.blueDark, breakLine: true } },
    { text: "Rendimiento similar: sexo 0 = 0.595 y sexo 1 = 0.586 en OS. Sin disparidad relevante.", options: { color: C.grayText, breakLine: true, paraSpaceAfter: 12 } },
    { text: "Transferibilidad entre brazos", options: { bold: true, color: C.blueDark, breakLine: true } },
    { text: "NESP 0.587 y placebo 0.611: similar entre estratos de tratamiento.", options: { color: C.grayText } },
  ], { x: cx, y: 2.05, w: cw, h: 4.4, fontFace: FONT, fontSize: 13, valign: "top", margin: 0, lineSpacingMultiple: 1.08 });
  footer(s);
}

// ---------- 12. Datos sintéticos ----------
{
  const s = pres.addSlide();
  header(s, "Datos sintéticos", "Utilidad limitada y privacidad no garantizada", 12);
  figureBox(s, fig("fig_synthetic_kanon.png"), MX, 2.0, 7.0, 4.4);
  const cx = MX + 7.0 + 0.4, cw = W - MX - cx;
  // resultado global
  card(s, cx, 2.05, cw, 1.1, C.white);
  s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 2.05, w: 0.12, h: 1.1, fill: { color: C.amber }, line: { type: "none" } });
  s.addText([
    { text: "Evaluación global: NO ACEPTADO", options: { bold: true, color: C.amber, breakLine: true } },
    { text: "por k-anonimidad con los cuasi-identificadores preregistrados.", options: { color: C.grayText } },
  ], { x: cx + 0.35, y: 2.18, w: cw - 0.6, h: 0.85, fontFace: FONT, fontSize: 13, valign: "middle", margin: 0, lineSpacingMultiple: 1.05 });
  s.addText([
    { text: "TSTR = 0.437", options: { bold: true, color: C.blueDark } },
    { text: " (por debajo de 0.5): el modelo entrenado en sintéticos no discrimina en reales. Ratio de utilidad 72.8%.", options: { color: C.grayText, breakLine: true, paraSpaceAfter: 8 } },
    { text: "k=1 = 7.3%", options: { bold: true, color: C.blueDark } },
    { text: " de registros sintéticos coincide de forma única con un real: supera el umbral de protección.", options: { color: C.grayText, breakLine: true, paraSpaceAfter: 8 } },
    { text: "Membership inference y DCR", options: { bold: true, color: C.green } },
    { text: " si pasan: no hay copia literal de registros.", options: { color: C.grayText } },
  ], { x: cx, y: 3.35, w: cw, h: 2.0, fontFace: FONT, fontSize: 12.5, valign: "top", margin: 0, lineSpacingMultiple: 1.05 });
  card(s, cx, 5.5, cw, 1.0, C.blueDark);
  s.addText("Uso restringido a prototipado metodológico. No refuerzan las conclusiones del modelo principal ni representan pacientes reales.", {
    x: cx + 0.3, y: 5.6, w: cw - 0.6, h: 0.8, fontFace: FONT, fontSize: 12, color: C.white, italic: true, valign: "middle", margin: 0, lineSpacingMultiple: 1.05,
  });
  footer(s);
}

// ---------- 13. Ética y gobernanza ----------
{
  const s = pres.addSlide();
  header(s, "Ética y gobernanza", "Privacidad por diseño y marco regulatorio", 13);
  const items = [
    ["Marco regulatorio", "RGPD, LOPDGDD, AI Act y guías de anonimizacion de la AEPD aplicadas a todo el ciclo de vida."],
    ["Privacidad por diseño", "Datos crudos y derivados a nivel de sujeto no versionados. Solo metadatos: diccionario, hashes y manifiesto."],
    ["No uso clínico", "El modelo no esta validado para decisiones de pacientes. Finalidad académica y metodológica."],
    ["Transparencia", "TRIPOD+AI como guía de reporte y Model Card viva con métricas, sesgos, limitaciones y privacidad."],
  ];
  const gap = 0.35, cw = (W - 2 * MX - gap) / 2, ch = 1.95;
  items.forEach((it, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = MX + col * (cw + gap), y = 2.1 + row * (ch + 0.3);
    card(s, x, y, cw, ch, C.white);
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: cw, h: 0.1, fill: { color: C.green }, line: { type: "none" } });
    s.addText(it[0], { x: x + 0.3, y: y + 0.28, w: cw - 0.6, h: 0.5, fontFace: FONT, fontSize: 17, color: C.blueDark, bold: true, margin: 0 });
    s.addText(it[1], { x: x + 0.3, y: y + 0.85, w: cw - 0.6, h: 1.0, fontFace: FONT, fontSize: 13.5, color: C.grayText, valign: "top", margin: 0, lineSpacingMultiple: 1.08 });
  });
  footer(s);
}

// ---------- 14. Análisis ampliado (Estrategia 2) ----------
{
  const s = pres.addSlide();
  header(s, "Análisis ampliado (Estrategia 2)", "Validación cruzada anidada: mejora pequeña y no concluyente", 14);
  const bw = 6.3;
  s.addText("Diseño", { x: MX, y: 2.0, w: bw, h: 0.4, fontFace: FONT, fontSize: 16, color: C.blueDark, bold: true, margin: 0 });
  s.addText([
    { text: "Validación cruzada anidada: selección de variables e hiperparámetros en el bucle interno, sin sesgo de selección.", options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 9 } },
    { text: "Pool ampliado de 10 covariables basales: anade LDH, EPO, índice de masa corporal y transfusión previa.", options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 9 } },
    { text: "Cox elastic-net, RSF y XGBoost frente al baseline de 7 variables, bajo el mismo protocolo anidado.", options: { bullet: { code: "2022" } } },
  ], { x: MX, y: 2.45, w: bw, h: 3.0, fontFace: FONT, fontSize: 13.5, color: C.grayText, valign: "top", margin: 0, lineSpacingMultiple: 1.08 });

  const cx = MX + bw + 0.5, cw = W - MX - cx;
  s.addText("Resultado", { x: cx, y: 2.0, w: cw, h: 0.4, fontFace: FONT, fontSize: 16, color: C.blueDark, bold: true, margin: 0 });
  s.addText([
    { text: "OS (primario): ", options: { bold: true, color: C.blueDark } },
    { text: "sin mejora significativa (+0.014, IC95% [-0.008, +0.036]).", options: { color: C.grayText, breakLine: true, paraSpaceAfter: 10 } },
    { text: "PFS (secundario): ", options: { bold: true, color: C.amber } },
    { text: "+0.024, en el umbral de la significación y frágil.", options: { color: C.grayText, breakLine: true, paraSpaceAfter: 10 } },
    { text: "RSF y XGBoost: ", options: { bold: true, color: C.blueDark } },
    { text: "no mejoran al baseline. LDH y EPO se seleccionan en todos los folds.", options: { color: C.grayText } },
  ], { x: cx, y: 2.45, w: cw, h: 3.0, fontFace: FONT, fontSize: 13.5, valign: "top", margin: 0, lineSpacingMultiple: 1.08 });

  card(s, MX, 5.7, W - 2 * MX, 0.95, C.blueDark);
  s.addText("Confirma la robustez del primario. Aporte metodológico, no un modelo mejor.", {
    x: MX + 0.3, y: 5.8, w: W - 2 * MX - 0.6, h: 0.75, fontFace: FONT, fontSize: 13.5, color: C.white, italic: true, valign: "middle", margin: 0, lineSpacingMultiple: 1.05,
  });
  footer(s);
}

// ---------- 15. Conclusiones y líneas futuras ----------
{
  const s = pres.addSlide();
  header(s, "Conclusiones y líneas futuras", "Aportación y siguientes pasos", 15);
  const bw = 6.5;
  s.addText("Conclusiones", { x: MX, y: 2.0, w: bw, h: 0.4, fontFace: FONT, fontSize: 16, color: C.blueDark, bold: true, margin: 0 });
  s.addText([
    { text: "Pipeline reproducible y auditable de supervivencia con control de fugas dentro de fold.", options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 9 } },
    { text: "Modelo final Cox por parsimonia: discriminación modesta (C-index OS 0.599) y calibración aceptable en el rango central.", options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 9 } },
    { text: "KPI-3 no cumplido reportado con honestidad: los modelos no lineales no aportan en esta cohorte.", options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 9 } },
    { text: "Evaluación ético-legal completa y datos sintéticos con riesgo de reidentificación documentado.", options: { bullet: { code: "2022" } } },
  ], { x: MX, y: 2.45, w: bw, h: 3.8, fontFace: FONT, fontSize: 14, color: C.grayText, valign: "top", margin: 0, lineSpacingMultiple: 1.08 });

  const cx = MX + bw + 0.5, cw = W - MX - cx;
  s.addText("Líneas futuras", { x: cx, y: 2.0, w: cw, h: 0.4, fontFace: FONT, fontSize: 16, color: C.amber, bold: true, margin: 0 });
  s.addText([
    { text: "Cox con extensiones tiempo-dependientes para AGE y B_WEIGHT (violación parcial de proporcionalidad).", options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 9 } },
    { text: "Enriquecer covariables basales (EPO, LDH) manteniendo el control anti-leakage.", options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 9 } },
    { text: "Validación externa en cohortes independientes más allá del ensayo.", options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 9 } },
    { text: "Generadores sintéticos más robustos que superen la k-anonimidad preregistrada.", options: { bullet: { code: "2022" } } },
  ], { x: cx, y: 2.45, w: cw, h: 3.8, fontFace: FONT, fontSize: 14, color: C.grayText, valign: "top", margin: 0, lineSpacingMultiple: 1.08 });
  footer(s);
}

// ---------- 15. Cierre ----------
{
  const s = pres.addSlide();
  s.background = { color: C.blueDark };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.28, h: H, fill: { color: C.amber }, line: { type: "none" } });
  s.addText("Gracias por su atención", {
    x: 1.0, y: 2.6, w: 11.3, h: 1.0, fontFace: FONT, fontSize: 40, color: C.white, bold: true, align: "left", margin: 0,
  });
  s.addText("Reproducibilidad y honestidad metodológica antes que rendimiento.", {
    x: 1.0, y: 3.7, w: 11.0, h: 0.6, fontFace: FONT, fontSize: 17, color: C.blueLight, italic: true, align: "left", margin: 0,
  });
  s.addText([
    { text: "Alfonso Esteban Lasso   |   ", options: { color: C.white } },
    { text: "Tutor: Tutor del TFG   |   ", options: { color: C.blueLight } },
    { text: "Grado en Ciencia de Datos Aplicada   |   UOC 2025.1", options: { color: C.blueLight } },
  ], { x: 1.0, y: 5.2, w: 11.3, h: 0.4, fontFace: FONT, fontSize: 13, align: "left", margin: 0 });
  s.addText("Preguntas", {
    x: 1.0, y: 5.9, w: 5, h: 0.5, fontFace: FONT, fontSize: 16, color: C.amber, bold: true, charSpacing: 2, align: "left", margin: 0,
  });
}

const outFile = path.join(OUT, "D5_presentacion.pptx");
pres.writeFile({ fileName: outFile }).then(() => {
  console.log("OK ->", outFile);
}).catch((e) => {
  console.error("ERROR", e);
  process.exit(1);
});
