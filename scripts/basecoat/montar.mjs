// Monta o Basecoat (MIT) para o Entenda Política: só os componentes usados, o estilo "Vega", sem o reset global do Tailwind
// e sem as classes utilitárias (o site não usa Tailwind nas páginas). Uso (fora do site, nunca no deploy):
//   cd scripts\basecoat && npm ci && node montar.mjs <pasta do site>
// Grava <site>/vendor/basecoat/basecoat.css, basecoat.js (runtime + dropdown-menu + popover + tabs) e LICENCAS.txt.
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { gzipSync } from "node:zlib";
import path from "node:path";

const AQUI = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1"));
const SITE = process.argv[2];
if (!SITE) { console.error("uso: node montar.mjs <pasta do site>"); process.exit(1); }
const NM = path.join(AQUI, "node_modules");
const BC = path.join(NM, "basecoat-css", "dist");
const SAIDA = path.join(SITE, "vendor", "basecoat");
mkdirSync(SAIDA, { recursive: true });

// componentes usados: [arquivo em dist/components, seção em dist/styles/vega.css]
const USADOS = [["button", "Button"], ["input", "Input"], ["combobox", "Combobox"], ["dropdown-menu", "Dropdown Menu"], ["popover", "Popover"],
  ["tabs", "Tabs"], ["dialog", "Dialog"], ["switch", "Switch"], ["badge", "Badge"], ["accordion", "Accordion"], ["card", "Card"],
  ["breadcrumb", "Breadcrumb"], ["kbd", "Kbd"], ["label", "Label"]];

// 1. recorte do estilo Vega: só as seções dos componentes usados
const vega = readFileSync(path.join(BC, "styles", "vega.css"), "utf8").split(/\r?\n/);
const secoes = {};
let atual = null;
for (const l of vega) {
  const m = /^\s*\/\* ([A-Z][A-Za-z ]+) \*\/\s*$/.exec(l);
  if (m && !/^States go/.test(m[1])) { atual = m[1]; secoes[atual] = []; continue; }
  if (/^@layer components \{$/.test(l) || l === "}") continue;
  if (atual) secoes[atual].push(l);
}
const faltam = USADOS.filter(([, s]) => !secoes[s]);
if (faltam.length) throw new Error("seções do Vega que não existem mais: " + faltam.map(x => x[1]).join(", "));
writeFileSync(path.join(AQUI, "vega-recorte.css"), "@layer components {\n" + USADOS.map(([, s]) => "/* " + s + " */\n" + secoes[s].join("\n")).join("\n") + "\n}\n");

// 2. entrada do Tailwind: tema (só variáveis usadas), tokens do site, reset só nos componentes, estrutura e estilo
const entrada = [
  "@layer theme, base, components, utilities;",
  '@import "tailwindcss/theme.css" layer(theme);',
  '@import "./tokens.css";',
  '@import "./escopo.css";',
  ...USADOS.map(([f]) => `@import "./node_modules/basecoat-css/dist/components/${f}.css";`),
  '@import "./vega-recorte.css";',
  '@source not inline("*");',
].join("\n") + "\n";
writeFileSync(path.join(AQUI, "entrada.css"), entrada);
const cli = path.join(NM, "@tailwindcss", "cli", "dist", "index.mjs");
execFileSync(process.execPath, [cli, "-i", path.join(AQUI, "entrada.css"), "-o", path.join(SAIDA, "basecoat.css"), "--minify"], { cwd: AQUI, stdio: "inherit" });
let css = readFileSync(path.join(SAIDA, "basecoat.css"), "utf8");
const cab = "/* Basecoat 1.1.0 (MIT, basecoatui.com) + Tailwind CSS 4.3.3 (MIT), montado para o Entenda Política: só os componentes usados, estilo Vega, sem reset global. Licenças em LICENCAS.txt. Não editar: refazer com scripts/basecoat/montar.mjs */\n";
css = cab + css.replace(/^\/\*![^*]*\*\/\s*/, "");
writeFileSync(path.join(SAIDA, "basecoat.css"), css);

// 3. JavaScript: o runtime e os componentes com comportamento usados (um arquivo só)
const js = ["basecoat", "dropdown-menu", "popover", "tabs"].map(n => readFileSync(path.join(BC, "js", n + ".min.js"), "utf8").trim()).join(";\n");
writeFileSync(path.join(SAIDA, "basecoat.js"), "/* Basecoat 1.1.0 (MIT): runtime, dropdown-menu, popover e tabs. Licença em LICENCAS.txt */\n" + js + "\n");

// 4. licenças
const lic = (p) => readFileSync(path.join(NM, p), "utf8");
writeFileSync(path.join(SAIDA, "LICENCAS.txt"),
  "Basecoat 1.1.0 (basecoat-css)\n" + lic("basecoat-css/LICENSE.md") + "\n\n---\nTailwind CSS 4.3.3 (o CSS foi gerado com ele)\n" + lic("tailwindcss/LICENSE") +
  "\n\n---\nLucide (ícones copiados como SVG para dentro do site)\n" + lic("lucide-static/LICENSE") + "\n");

// 5. conferências: nenhum endereço de outro servidor; nada de reset global
const tudo = css + js;
const urls = (tudo.match(/https?:\/\/[^"')\s]+/g) || []).filter(u => !/^http:\/\/www\.w3\.org\//.test(u));
if (urls.length) throw new Error("endereços externos no Basecoat montado: " + urls.join(", "));
if (/(^|[},])\s*\*\s*,\s*::?after|(^|[},])\s*(html|body)\s*\{/.test(css.replace(/:where\([^)]*\)/g, ""))) throw new Error("o CSS montado tem regra global (reset)");
for (const f of ["basecoat.css", "basecoat.js"]) {
  const b = readFileSync(path.join(SAIDA, f));
  console.log(`${f}: ${(b.length / 1024).toFixed(1)} KB (gzip ${(gzipSync(b).length / 1024).toFixed(1)} KB)`);
}

