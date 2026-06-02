// _markdown.js
// Renderizador compartido de Markdown a elementos docx, con el estilo del proyecto.
// Lo usan build_model_card.js (documento standalone) y build_d4.js (Parte 2, que
// reutiliza docs/model_card.md como fuente unica de la Model Card).
// Tokeniza con 'marked' y mapea encabezados, parrafos, vinetas, tablas y negrita.
// Regla del proyecto: sin guiones largos (em/en) en ningun texto generado.

import { marked } from "marked";
import {
  Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType, VerticalAlign,
} from "docx";
import { FONT, COLORS, TABLE } from "./_style.js";

export function run(text, opts = {}) {
  return new TextRun({ text, font: FONT, ...opts });
}

// Tokens inline de 'marked' -> runs (negrita, cursiva, codigo y enlaces).
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
  const lv = Math.min(4, Math.max(1, level));
  const sizes = { 1: 32, 2: 26, 3: 23, 4: 21 };
  const hl = { 1: HeadingLevel.HEADING_1, 2: HeadingLevel.HEADING_2,
               3: HeadingLevel.HEADING_3, 4: HeadingLevel.HEADING_4 }[lv];
  return new Paragraph({
    heading: hl,
    spacing: { before: lv <= 2 ? 320 : 200, after: 120 },
    children: [run(text, { bold: true, color: COLORS.blueDark, size: sizes[lv] })],
  });
}

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

// Convierte los tokens de 'marked' en elementos docx.
// Opciones:
//   coverTitle  : si true, el primer '#' se renderiza como titulo de portada grande.
//   skipFirstH1 : si true, el primer '#' se omite (lo aporta el documento contenedor).
//   headingOffset: desplazamiento de nivel para anidar bajo un contenedor (p. ej. D4).
function tokensToDocx(tokens, { coverTitle = false, skipFirstH1 = false, headingOffset = 0 } = {}) {
  const out = [];
  let firstH1Seen = false;

  for (const tok of tokens) {
    if (tok.type === "heading") {
      if (tok.depth === 1 && !firstH1Seen) {
        firstH1Seen = true;
        if (skipFirstH1) continue;
        if (coverTitle) {
          out.push(new Paragraph({ alignment: AlignmentType.LEFT, spacing: { before: 200, after: 200 },
            children: [run(tok.text, { bold: true, color: COLORS.blueDark, size: 48 })] }));
          continue;
        }
      }
      // ## -> nivel 1, ### -> 2, #### -> 3, mas el desplazamiento del contenedor.
      out.push(heading(tok.text, Math.max(1, tok.depth - 1) + headingOffset));
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

// Renderiza una cadena Markdown a un array de elementos docx.
export function renderMarkdownToDocx(md, opts = {}) {
  return tokensToDocx(marked.lexer(md), opts);
}
