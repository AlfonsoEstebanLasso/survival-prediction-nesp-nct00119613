// build_model_card.js
// Proposito: generar la Model Card (estandar Mitchell et al. 2018, 9 secciones)
//   en formato .docx a partir de la fuente unica docs/model_card.md.
// Entradas: docs/model_card.md (fuente de contenido), docs/assets/uoc_logo.png
//   (opcional), docs/scripts/_style.js (paleta y fuente).
// Salida: output/model_card.docx
// Transformaciones: el Markdown se tokeniza con la libreria 'marked' (tooling de
//   documentacion Node, ajeno al entorno reproducible del pipeline src/) y se
//   maqueta con la libreria docx y el estilo del proyecto (Arial, azul UOC,
//   tablas con cabecera azul, pie "Pagina X de Y", logo UOC).
// Regla del proyecto: sin guiones largos (em/en) en ningun texto generado.

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { marked } from "marked";
import {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  Header, Footer, PageNumber, VerticalAlign, ImageRun,
} from "docx";
import { FONT, COLORS, TABLE } from "./_style.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..", "..");
const OUT = path.join(ROOT, "output");
const SRC = path.join(ROOT, "docs", "model_card.md");

// ----------------------------------------------------------------------------
// Helpers de formato (coherentes con build_d3.js / build_d4.js)
// ----------------------------------------------------------------------------
function run(text, opts = {}) {
  return new TextRun({ text, font: FONT, ...opts });
}

// Convierte una lista de tokens inline de 'marked' en runs de docx, respetando
// negrita (strong), cursiva (em), codigo en linea y enlaces (texto plano).
function inlineRuns(tokens, base = {}) {
  const out = [];
  for (const t of tokens || []) {
    if (t.type === "strong") out.push(...inlineRuns(t.tokens || [{ type: "text", text: t.text }], { ...base, bold: true }));
    else if (t.type === "em") out.push(...inlineRuns(t.tokens || [{ type: "text", text: t.text }], { ...base, italics: true }));
    else if (t.type === "codespan") out.push(run(t.text, base));
    else if (t.type === "link") out.push(run(t.text, base));
    else if (t.type === "text") {
      if (t.tokens && t.tokens.length) out.push(...inlineRuns(t.tokens, base));
      else out.push(run(t.text, base));
    } else if (t.text != null) {
      out.push(run(t.text, base));
    }
  }
  return out.length ? out : [run("", base)];
}

function heading(text, level) {
  const sizes = { 1: 32, 2: 26, 3: 23, 4: 21 };
  const hl = { 1: HeadingLevel.HEADING_1, 2: HeadingLevel.HEADING_2,
               3: HeadingLevel.HEADING_3, 4: HeadingLevel.HEADING_4 }[level];
  return new Paragraph({
    heading: hl,
    spacing: { before: level <= 2 ? 320 : 200, after: 120 },
    children: [run(text, { bold: true, color: COLORS.blueDark, size: sizes[level] })],
  });
}

// ---- Tablas con estilo del proyecto -----------------------------------------
function cell(text, { header = false, alt = false } = {}) {
  const fill = header ? TABLE.headerFill : (alt ? TABLE.rowFillAlt : TABLE.rowFill);
  return new TableCell({
    shading: { type: ShadingType.CLEAR, color: "auto", fill },
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    children: [new Paragraph({ spacing: { line: 240, after: 0 },
      children: [run(text, { bold: header, size: 18,
        color: header ? COLORS.blueDark : COLORS.text })] })],
  });
}

function buildTable(headerCells, rowCells) {
  const rows = [headerCells, ...rowCells];
  const trs = rows.map((cells, ri) => new TableRow({
    tableHeader: ri === 0,
    children: cells.map((c) => cell(c, { header: ri === 0, alt: ri > 0 && ri % 2 === 0 })),
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
// Mapeo de tokens de 'marked' a elementos docx
// ----------------------------------------------------------------------------
function tokensToDocx(tokens) {
  const out = [];
  let coverTitleDone = false;

  for (const tok of tokens) {
    if (tok.type === "heading") {
      if (tok.depth === 1 && !coverTitleDone) {
        // El primer '#' es el titulo de portada.
        coverTitleDone = true;
        out.push(new Paragraph({ alignment: AlignmentType.LEFT, spacing: { before: 200, after: 200 },
          children: [run(tok.text, { bold: true, color: COLORS.blueDark, size: 48 })] }));
      } else {
        // ## -> H1, ### -> H2, #### -> H3.
        out.push(heading(tok.text, Math.max(1, tok.depth - 1)));
      }
    } else if (tok.type === "paragraph") {
      out.push(new Paragraph({
        alignment: AlignmentType.JUSTIFIED,
        spacing: { line: 300, after: 120 },
        children: inlineRuns(tok.tokens),
      }));
    } else if (tok.type === "list") {
      for (const item of tok.items) {
        const inline = item.tokens && item.tokens[0] && item.tokens[0].tokens
          ? item.tokens[0].tokens : [{ type: "text", text: item.text }];
        out.push(new Paragraph({
          alignment: AlignmentType.JUSTIFIED,
          spacing: { line: 280, after: 40 },
          bullet: { level: 0 },
          children: inlineRuns(inline),
        }));
      }
    } else if (tok.type === "table") {
      const headerCells = tok.header.map((h) => h.text);
      const rowCells = tok.rows.map((r) => r.map((c) => c.text));
      out.push(buildTable(headerCells, rowCells));
      out.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
    }
    // 'space', 'hr', etc. se ignoran.
  }
  return out;
}

// ----------------------------------------------------------------------------
// Pie, cabecera y logo
// ----------------------------------------------------------------------------
function footerParagraph() {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ font: FONT, size: 16,
      children: ["Página ", PageNumber.CURRENT, " de ", PageNumber.TOTAL_PAGES] })],
  });
}

function tryReadLogo() {
  try { return fs.readFileSync(path.join(ROOT, "docs", "assets", "uoc_logo.png")); }
  catch { return null; }
}
function pngSize(buf) { return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) }; }

// ----------------------------------------------------------------------------
// Construccion del documento
// ----------------------------------------------------------------------------
const md = fs.readFileSync(SRC, "utf-8");
const body = tokensToDocx(marked.lexer(md));

const children = [];
const LOGO = tryReadLogo();
if (LOGO) {
  const { w, h } = pngSize(LOGO);
  const wPx = 520;
  const hPx = Math.round((wPx * h) / w);
  children.push(new Paragraph({ alignment: AlignmentType.LEFT, spacing: { before: 100, after: 200 },
    children: [new ImageRun({ data: LOGO, transformation: { width: wPx, height: hPx } })] }));
}
children.push(...body);

const doc = new Document({
  creator: "Alfonso Esteban Lasso",
  title: "Model Card - Prediccion de supervivencia bajo quimioterapia",
  description: "Model Card (estandar Mitchell et al. 2018) generada desde docs/model_card.md",
  styles: { default: { document: { run: { font: FONT, size: 22 } } } },
  sections: [{
    properties: { page: { margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    headers: {
      default: new Header({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: COLORS.blueDark, space: 4 } },
        children: [run("Universitat Oberta de Catalunya (UOC)  |  Model Card", { size: 16, color: COLORS.blueDark })],
      })] }),
    },
    footers: { default: new Footer({ children: [footerParagraph()] }) },
    children,
  }],
});

const outFile = path.join(OUT, "model_card.docx");
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(outFile, buf);
  console.log("Generado:", outFile);
});
