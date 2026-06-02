// build_model_card.js
// Proposito: generar la Model Card (estandar Mitchell et al. 2018, 9 secciones)
//   en formato .docx a partir de la fuente unica docs/model_card.md.
// Entradas: docs/model_card.md (fuente de contenido), docs/assets/uoc_logo.png
//   (opcional), docs/scripts/_markdown.js (renderizador compartido) y
//   docs/scripts/_style.js (paleta y fuente).
// Salida: output/model_card.docx
// Transformaciones: el Markdown se tokeniza con 'marked' y se maqueta con la
//   libreria docx y el estilo del proyecto (Arial, azul UOC, tablas con cabecera
//   azul, pie "Pagina X de Y", logo UOC).
// Regla del proyecto: sin guiones largos (em/en) en ningun texto generado.

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import {
  Document, Packer, Paragraph, TextRun, AlignmentType,
  Header, Footer, PageNumber, BorderStyle, ImageRun,
} from "docx";
import { FONT, COLORS } from "./_style.js";
import { renderMarkdownToDocx, run } from "./_markdown.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..", "..");
const OUT = path.join(ROOT, "output");
const SRC = path.join(ROOT, "docs", "model_card.md");

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
const body = renderMarkdownToDocx(md, { coverTitle: true });

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
