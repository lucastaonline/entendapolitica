/* ======================================================================
   Entenda a política: mapa 3D + aula (apresentação em 3D de cada parada).
   Português: conteudo/entenda/parte-1.json ... parte-10.json
   Inglês:    conteudo/entenda/en/parte-1.json ... (mesma estrutura, textos traduzidos)

   FORMATO DE CADA PARTE
   {
     "parte": 1, "ic": "🤝", "nome": "O que é política?",
     "resumo": "Uma frase dizendo o que a parte ensina.",
     "fontes": [ { "id": "cf-art1", "veiculo": "Planalto", "titulo": "Constituição Federal, art. 1º",
                   "url": "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm", "data": "1988-10-05" } ],
     "glossario": [ { "termo": "mandato", "simples": "O tempo que a pessoa eleita fica no cargo." } ],
     "slides": [ ...um objeto por slide... ]
   }

   Em qualquer texto: **assim** vira negrito. Nada de HTML.
   Todo slide (menos "abertura") deve ter "fontes": ["id", ...] apontando para a lista "fontes" da parte.

   TIPOS DE SLIDE
   abertura   { "tipo":"abertura", "titulo":"Frase-título da parte", "texto":"1 ou 2 frases", "ilustracao":"id" }
   explica    { "tipo":"explica", "etiqueta":"RÓTULO (opcional)", "titulo":"...", "texto":"(opcional)",
                "itens":[ { "ic":"🏫", "txt":"frase curta" } ], "ilustracao":"id (opcional)", "emoji":"🏫 (opcional)",
                "coruja":"dica (opcional)", "fontes":["id"] }
   cards      { "tipo":"cards", "etiqueta":"...", "titulo":"...", "texto":"...",
                "cards":[ { "ic":"👑", "titulo":"...", "txt":"...", "dados":[ { "rot":"Mandato", "val":"4 anos" } ], "mais":"(opcional: vai no verso do cartão)" } ],
                "fontes":["id"] }
   passos     { "tipo":"passos", "titulo":"...", "texto":"...", "passos":[ { "ic":"💡", "titulo":"...", "txt":"..." } ], "fontes":["id"] }   (vira uma escada 3D)
   comparar   { "tipo":"comparar", "titulo":"...", "texto":"...", "colunas":[ { "ic":"🥇", "titulo":"...", "itens":["..."], "exemplo":"(opcional)" } ], "fontes":["id"] }
   numeros    { "tipo":"numeros", "titulo":"...", "texto":"...", "numeros":[ { "val":"513", "rot":"deputados federais", "ic":"🧑‍💼" } ], "nota":"(opcional)", "fontes":["id"] }
   historia   { "tipo":"historia", "titulo":"...", "quadros":[ { "ic":"🏫", "txt":"..." } ], "moral":"...", "fontes":["id"] }
   quiz       { "tipo":"quiz", "pergunta":"...", "opcoes":["...", "..."], "certa":0, "explica":"...", "fontes":["id"] }
   simulador  { "tipo":"simulador", "id":"quem-cuida" | "quociente" | "caminho-lei" | "votos-precisos" | "caminho-voto" | "lacre-digital" | "confira-boletim", "titulo":"...", "texto":"...", "fontes":["id"], ... }
      quem-cuida:  "itens":[ { "ic":"🏫", "txt":"Creche", "quem":"cidade", "explica":"..." } ]   // quem: pais | estado | cidade | todos
      quociente:   "cadeiras":10, "partidos":[ { "nome":"Partido Círculo", "votos":420 } ], "passos":["explicação passo a passo"]   // partidos inventados com nome de forma, nunca de cor
      caminho-lei: "passos":[ { "ic":"💡", "titulo":"...", "txt":"..." } ]
      votos-precisos: "casas":[ { "nome":"Câmara dos Deputados", "total":513, "quem":"deputados" } ],
                      "opcoes":[ { "ic":"📕", "nome":"Mudar a Constituição (PEC)", "explica":"...",
                                   "casas":[ { "sim":308, "nao":0, "rot":"“sim”, no mínimo, dos 513 deputados" } ] } ]   // uma entrada em "casas" por Casa, na mesma ordem
      caminho-voto: "fases":[ { "id":"antes", "ic":"📅", "nome":"Antes da eleição" } ],
                    "etapas":[ { "fase":"antes", "ic":"📂", "titulo":"...", "quando":"...", "txt":"...", "quem":"quem confere" } ]   // a ficha anda de etapa em etapa
      lacre-digital: "inicial":"frase do começo", "explica":"(opcional)"   // hash SHA-256 ou SHA-512 de verdade (Web Crypto)
      confira-boletim: "aviso":"EXEMPLO...", "secao":{ "municipio","zona","secao","local" }, "aptos":300,
                       "linhas":[ { "nome":"Candidata Círculo", "papel":98, "site":98 } ],   // uma linha com papel ≠ site: a pessoa acha a diferença
                       "acerto":"...", "erro":"...", "qr":"(opcional: texto do botão de ler o QR Code)"   // dados inventados, nomes de forma, nunca números de partido

   ILUSTRAÇÕES ("ilustracao"): congresso, tres-poderes, niveis, urna, urna-boletim, constituicao, balanca, lei, cofre, mapa,
   plenario, megafone, predio, palacio, escola, tribunal, cargos, palanque. Se precisar de outra coisa, use "emoji".

   LINK (qualquer slide, opcional): "link": { "url":"brasil.html#os-ministros", "ic":"👔", "txt":"Ver os ministérios de hoje" }
   vira um botão no fim do slide. Só aceita páginas do próprio site (no inglês, o link já leva ?lang=en).
   Para outra parada: "url":"entenda.html#parte-10" (o mapa voa até ela).
   PULAR (qualquer slide, opcional): "pular": true vira o botão "Pular para o fim" (ex.: antes de uma parte opcional).
   ====================================================================== */
(function () {
  "use strict";
  var EP = window.EP, T = window.TRES || {}, MAPA = window.MAPA;
  var esc = EP.esc, md = EP.md, tr = EP.tr;
  var $ = function (id) { return document.getElementById(id); };
  var palco = $("palco");
  var TOTAL = 10;
  var LETRAS = ["A", "B", "C", "D", "E"];
  var QUEM = { pais: tr("🏛️ País", "🏛️ Country"), estado: tr("🗺️ Estado", "🗺️ State"), cidade: tr("🏘️ Cidade", "🏘️ City"), todos: tr("🤝 Todos juntos", "🤝 All together") };
  var PALETA = ["#2f6db5", "#2f9a5a", "#d97a00", "#7c4dbd", "#d0558f", "#0f766e"];
  var PADRAO = {
    1: ["🤝", "O que é política?", "What is politics?"], 2: ["🏛️", "Os Três Poderes", "The Three Branches"], 3: ["🧱", "País, estado e cidade", "Country, state and city"],
    4: ["👔", "Os cargos, um por um", "Each office, one by one"], 5: ["🗣️", "O Congresso Nacional", "The National Congress"], 6: ["📜", "Como nasce uma lei", "How a law is made"],
    7: ["🗳️", "Como funcionam as eleições", "How elections work"], 8: ["⚖️", "Quem julga e quem fiscaliza", "Who judges and who oversees"], 9: ["🙋", "Como você pode participar", "How you can take part"],
    10: ["🔐", "A urna eletrônica por dentro", "Inside the voting machine"]
  };
  var MODELO_PARTE = { 1: "escola", 2: "tres-poderes", 3: "niveis", 4: "cargos", 5: "congresso", 6: "lei", 7: "urna", 8: "tribunal", 9: "palanque", 10: "urna-boletim" };

  var PARTES = {}, TRADUZIDA = {}, feitos = {};
  try { feitos = JSON.parse(localStorage.getItem("ep-mapa-feitos") || "{}") || {}; } catch (e) {}
  function salvaFeitos() { try { localStorage.setItem("ep-mapa-feitos", JSON.stringify(feitos)); } catch (e) {} }

  // ---------------------------------------------------------------- carregar o conteúdo
  function pega(url) { return fetch(url, { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }); }
  function carregar() {
    var ns = [];
    for (var n = 1; n <= TOTAL; n++) ns.push(n);
    return Promise.all(ns.map(function (n) {
      var urlPt = EP.param("teste") && n === 1 ? "testes/parte-teste.json" : "conteudo/entenda/parte-" + n + ".json";
      function guarda(j, traduzida) { if (j) { j.parte = n; PARTES[n] = j; TRADUZIDA[n] = !!traduzida; } }
      if (!EP.en) return pega(urlPt).then(function (j) { guarda(j, false); });
      return pega("conteudo/entenda/en/parte-" + n + ".json").then(function (je) {
        if (je) { guarda(je, true); return null; }
        return pega(urlPt).then(function (j) { guarda(j, false); });
      });
    }));
  }
  function info() {
    var o = {};
    for (var n = 1; n <= TOTAL; n++) {
      var P = PARTES[n], d = PADRAO[n];
      o[n] = { nome: P ? P.nome : tr(d[1], d[2]), ic: P ? P.ic : d[0], tem: !!P };
    }
    return o;
  }
  function proximo(depoisDe) {
    var ordem = [];
    for (var k = 1; k <= TOTAL; k++) ordem.push(k);
    if (depoisDe) ordem = ordem.slice(depoisDe).concat(ordem.slice(0, depoisDe));
    for (var i = 0; i < ordem.length; i++) if (!feitos[ordem[i]] && ordem[i] !== depoisDe) return ordem[i];
    return null;
  }
  function quantos() { return Object.keys(feitos).filter(function (k) { return feitos[k]; }).length; }

  // ---------------------------------------------------------------- mapa
  function atualizaMapa() {
    var I = info(), q = quantos(), p = proximo();
    if (MAPA) MAPA.estado(feitos, p, I);
    var pr = $("progresso-mapa");
    pr.textContent = (q === TOTAL ? "🏆 " : "⭐ ") + q + "/" + TOTAL;
    pr.setAttribute("aria-label", tr("Você aprendeu " + q + " de " + TOTAL + " paradas", "You learned " + q + " of " + TOTAL + " stops"));
    var b = $("bolha");
    if (q === 0) b.innerHTML = tr("Oi! Eu sou a Coruja. Toque em qualquer lugar do mapa para aprender. A trilha amarela mostra uma ordem sugerida: comece pela parada 1!", "Hi! I'm the Owl. Tap any place on the map to learn. The yellow trail shows a suggested order: start at stop 1!") +
      '<br><button class="btn peq" type="button" data-abrir-parada="1">' + tr("Começar pela parada 1 ▶", "Start at stop 1 ▶") + "</button>";
    else if (p) b.innerHTML = tr("Muito bem! Você já visitou " + q + " de " + TOTAL + " paradas. Próxima sugestão: ", "Well done! You have visited " + q + " of " + TOTAL + " stops. Next suggestion: ") + "<b>" + esc(I[p].nome) + "</b>." +
      '<br><button class="btn peq" type="button" data-abrir-parada="' + p + '">' + tr("Ir para a parada ", "Go to stop ") + p + " ▶</button>";
    else b.innerHTML = tr("Uau! Você visitou as " + TOTAL + " paradas! E agora, o que você quer fazer?", "Wow! You visited all " + TOTAL + " stops! What would you like to do next?") +
      '<br><a class="btn peq" href="brasil.html' + (EP.en ? "?lang=en" : "") + '">🏛️ ' + tr("Política do Brasil", "Politics of Brazil") + '</a> <a class="btn peq claro" href="estado.html' + (EP.en ? "?lang=en" : "") + '">📍 ' +
      tr("Meu estado", "My state") + '</a> <button class="btn peq bege" type="button" data-compartilhar="mapa-coruja">📤 ' + tr("Compartilhar", "Share") + "</button>";
  }

  // ---------------------------------------------------------------- pedaços de HTML
  function anim(i) { return ' class="anim" style="--i:' + (i || 0) + '"'; }
  function cab(s, i0) {
    i0 = i0 || 0;
    return (s.etiqueta ? '<span class="etiqueta anim" style="--i:' + i0 + '">' + esc(s.etiqueta) + "</span>" : "") +
      (s.titulo ? "<h2" + anim(i0 + 1) + ">" + md(s.titulo) + "</h2>" : "") +
      (s.texto ? '<p class="lead anim" style="--i:' + (i0 + 2) + '">' + md(s.texto) + "</p>" : "");
  }
  function ilustracao(s, reserva) {
    if (s.ilustracao && T.ilustracao) return T.ilustracao(s.ilustracao, s.emoji);
    if (s.emoji && T.cuboEmoji) return T.cuboEmoji(s.emoji);
    return reserva && T.cuboEmoji ? T.cuboEmoji(reserva) : "";
  }
  var DET = [];
  function det(titulo, html) { DET.push({ t: titulo, h: html }); return DET.length - 1; }
  var PAGINAS_SITE = /^(index|entenda|brasil|estado|cidade|votacoes|votacao|dados|imparcialidade)\.html(\?[\w=&-]*)?(#[\w-]+)?$/;
  function linkDoSlide(s) {
    var l = s.link, h = "";
    if (l && l.url && PAGINAS_SITE.test(l.url)) {
      var u = EP.en ? l.url.replace(/^([^?#]+)(\?[^#]*)?/, function (m, arq, q) { return arq + (q ? q + "&" : "?") + "lang=en"; }) : l.url;
      // a seta do fim ("... ▶" ou a padrão "›") é só enfeite: o leitor de tela não lê
      var txt = String(l.txt || ""), seta = /\s*▶\s*$/.test(txt) ? "▶" : "›";
      h += '<p class="link-slide anim" style="--i:9"><a class="btn peq claro" href="' + esc(u) + '">' + (l.ic ? '<span aria-hidden="true">' + esc(l.ic) + " </span>" : "") +
        md(txt.replace(/\s*▶\s*$/, "")) + ' <span aria-hidden="true">' + seta + "</span></a></p>";
    }
    // antes de uma parte opcional: botão para ir direto ao fim da parada
    if (s.pular) h += '<p class="link-slide anim" style="--i:9"><button type="button" class="btn peq bege" data-acao="fim">⏭ ' + tr("Pular a parte técnica e ir para o fim", "Skip the technical part and go to the end") + "</button></p>";
    return h;
  }

  var R = {};
  R.abertura = function (s, P) {
    var ilu = s.ilustracao ? T.ilustracao(s.ilustracao, s.emoji) : T.ilustracao(MODELO_PARTE[P.parte]);
    return '<div class="abertura"><div class="txt">' + (T.cubo ? T.cubo(String(P.parte), P.ic || "", "entra", 110) : "") +
      '<span class="etiqueta anim">' + tr("Parada ", "Stop ") + P.parte + tr(" de ", " of ") + TOTAL + " · " + esc(P.nome) + "</span>" +
      "<h1" + anim(1) + ">" + md(s.titulo || P.nome) + "</h1>" +
      (s.texto ? '<p class="lead anim" style="--i:2">' + md(s.texto) + "</p>" : "") +
      (P.resumo ? '<p class="muted anim" style="--i:3"><span aria-hidden="true">🎯 </span>' + md(P.resumo) + "</p>" : "") +
      '<p class="anim" style="--i:4"><button class="btn" type="button" data-acao="proximo">' + tr("Vamos lá ▶", "Let's go ▶") + "</button></p></div>" +
      '<div class="ilu anim" style="--i:2">' + ilu + "</div></div>";
  };
  R.explica = function (s, P) {
    var ilu = ilustracao(s, (s.itens && s.itens[0] && s.itens[0].ic) || P.ic);
    var itens = (s.itens || []).map(function (it, k) {
      return '<li style="--i:' + k + '"><span class="ic" aria-hidden="true">' + esc(it.ic || "•") + "</span><span>" + md(it.txt) + "</span></li>";
    }).join("");
    return '<div class="duas"><div class="txt">' + cab(s) + (itens ? '<ul class="itens">' + itens + "</ul>" : "") +
      (s.coruja ? '<div class="dica-coruja anim" style="--i:' + ((s.itens || []).length + 3) + '"><span class="coruja" aria-hidden="true">🦉</span><p>' + md(s.coruja) + "</p></div>" : "") +
      '</div><div class="ilu anim" style="--i:2">' + ilu + "</div></div>";
  };
  R.cards = function (s) {
    return cab(s) + '<div class="cards">' + (s.cards || []).map(function (c, k) {
      var dados = (c.dados || []).map(function (d) { return "<div><dt>" + esc(d.rot) + "</dt><dd>" + esc(d.val) + "</dd></div>"; }).join("");
      var titulo = '<span class="c-ic" aria-hidden="true">' + esc(c.ic || "") + "</span><h3>" + md(c.titulo) + "</h3>";
      return '<div class="card-3d anim" style="--i:' + k + '"><div class="face frente">' + titulo + (c.txt ? "<p>" + md(c.txt) + "</p>" : "") + (dados ? "<dl>" + dados + "</dl>" : "") +
        (c.mais ? '<button class="vira-btn" type="button" data-virar aria-expanded="false">🔄 ' + tr("Virar e saber mais", "Flip to learn more") + "</button>" : "") + "</div>" +
        (c.mais ? '<div class="face verso" aria-hidden="true" tabindex="-1">' + titulo + "<p>" + md(c.mais) + '</p><button class="vira-btn" type="button" data-virar tabindex="-1">↩️ ' + tr("Voltar", "Back") + "</button></div>" : "") + "</div>";
    }).join("") + "</div>";
  };
  R.passos = function (s, P, idx) {
    var p = s.passos || [];
    return cab(s) + '<div class="passos-3d" data-escada="' + idx + '">' + (T.escada ? T.escada(p) : "") +
      '<ol class="lista-passos">' + p.map(function (x, k) {
        return '<li data-k="' + k + '"><span class="n" aria-hidden="true">' + (k + 1) + "</span><span><b>" + esc(x.ic || "") + " " + md(x.titulo) + "</b>" + (x.txt ? md(x.txt) : "") + "</span></li>";
      }).join("") + '</ol><div class="ctrl-passos"><button class="btn peq claro" type="button" data-escada-replay="' + idx + '">↺ ' + tr("Ver de novo", "Watch again") + "</button></div></div>";
  };
  R.comparar = function (s) {
    var cores = ["#1f3a5f", "#c27600", "#0f766e"], n = (s.colunas || []).length;
    return cab(s) + '<div class="comparar" style="--n:' + n + '">' + (s.colunas || []).map(function (c, k) {
      return '<div class="col-comp" style="--i:' + k + ";--cor:" + cores[k % 3] + '"><h3><span aria-hidden="true">' + esc(c.ic || "") + "</span>" + md(c.titulo) + "</h3>" +
        "<ul>" + (c.itens || []).map(function (t) { return "<li>" + md(t) + "</li>"; }).join("") + "</ul>" +
        (c.exemplo ? '<div class="exemplo"><span aria-hidden="true">💡 </span>' + md(c.exemplo) + "</div>" : "") + "</div>";
    }).join("") + (n === 2 ? '<span class="moeda-vs" aria-hidden="true">⇄</span>' : "") + "</div>";
  };
  R.numeros = function (s) {
    var n = (s.numeros || []).length;
    // números grandes (ex.: 158.745.463) não cabem em 4 colunas: ficam em 2 (e em 1 no celular)
    var longos = (s.numeros || []).some(function (x) { return String(x.val).length >= 9; });
    return cab(s) + '<div class="numeros-s' + (longos ? " longos" : "") + '" style="--n:' + Math.min(n, longos ? 2 : 4) + '">' + (s.numeros || []).map(function (x, k) {
      return '<div class="num3d" style="--i:' + k + '"><div class="giro"><div class="face-num"><span class="n-ic" aria-hidden="true">' + esc(x.ic || "") + "</span>" +
        '<span class="n-val"><span class="conta" data-alvo="' + esc(x.val) + '">' + esc(x.val) + "</span></span>" +
        '<span class="n-rot">' + md(x.rot) + '</span></div><div class="verso" aria-hidden="true">' + esc(x.ic || "🔢") + "</div></div></div>";
    }).join("") + "</div>" + (s.nota ? '<p class="nota-s anim" style="--i:4">' + md(s.nota) + "</p>" : "");
  };
  R.historia = function (s) {
    var q = s.quadros || [];
    return cab(s) + '<div class="quadros" style="--n:' + Math.min(q.length, 5) + '">' + q.map(function (x, k) {
      return '<div class="quadro" style="--i:' + k + '"><span class="q-num" aria-hidden="true">' + (k + 1) + '</span><span class="q-ic" aria-hidden="true">' + esc(x.ic || "") + "</span><p>" + md(x.txt) + "</p></div>";
    }).join("") + "</div>" + (s.moral ? '<div class="moral anim" style="--i:' + (q.length * 2 + 3) + '"><span aria-hidden="true">💡 </span>' + md(s.moral) + "</div>" : "");
  };
  R.quiz = function (s, P, idx) {
    return '<div class="quiz"><div class="q-cab"><span class="anim" aria-hidden="true">' + (T.cubo ? T.cubo("?", "🤔", "lento", 76) : "🤔") + "</span><div>" +
      '<span class="etiqueta anim">' + tr("Pergunta rápida", "Quick question") + "</span><h2" + anim(1) + ">" + md(s.pergunta) + "</h2></div></div>" +
      '<div class="opcoes" role="group" aria-label="' + esc(tr("Respostas", "Answers")) + '">' + (s.opcoes || []).map(function (o, k) {
        return '<button type="button" class="opcao anim" style="--i:' + (k + 2) + '" data-quiz="' + idx + '" data-op="' + k + '"><span class="letra" aria-hidden="true">' + LETRAS[k] + "</span><span>" + md(o) + "</span></button>";
      }).join("") + '</div><div class="resposta" role="status" aria-live="polite" hidden></div></div>';
  };
  R.simulador = function (s, P, idx) {
    if (s.id === "quem-cuida") {
      var opc = Object.keys(QUEM).filter(function (q) { return (s.itens || []).some(function (it) { return it.quem === q; }) || q !== "todos"; });
      return cab(s) + '<div class="qc-lista">' + (s.itens || []).map(function (it, k) {
        var tit = '<div class="qc-tit"><span aria-hidden="true">' + esc(it.ic || "") + "</span>" + md(it.txt) + "</div>";
        return '<div class="qc-item" data-qc="' + idx + '" data-k="' + k + '"><div class="face frente">' + tit + '<div class="qc-botoes" role="group" aria-label="' + esc(tr("Quem cuida disso?", "Who takes care of this?")) + '">' +
          opc.map(function (q) { return '<button type="button" data-quem="' + q + '">' + QUEM[q] + "</button>"; }).join("") + "</div></div>" +
          '<div class="face verso" aria-hidden="true" tabindex="-1">' + tit + '<p class="qc-resp"></p><p class="qc-explica"></p></div></div>';
      }).join("") + '</div><p class="placar" data-placar="' + idx + '" aria-live="polite"></p>';
    }
    if (s.id === "quociente") {
      return cab(s) + '<div class="qe" data-qe="' + idx + '"><div class="qe-partidos"></div><div class="qe-painel"><b>🪑 ' + esc(s.cadeiras) + tr(" cadeiras para dividir", " seats to share") + "</b>" +
        '<div class="qe-cadeiras" aria-hidden="true"></div><div class="qe-conta" aria-live="polite"></div>' +
        '<div class="botoes"><button type="button" class="btn peq" data-qe-passo="' + idx + '"></button><button type="button" class="btn peq bege" data-qe-zera="' + idx + '">↺ ' + tr("Recomeçar", "Start over") + "</button></div></div></div>";
    }
    if (s.id === "votos-precisos") {
      // plenário 3D de cada Casa; a criança escolhe o que está sendo votado e as cadeiras dos "sim" acendem
      return cab(s) + '<div class="vp" data-vp="' + idx + '">' +
        '<div class="vp-opcoes" role="group" aria-label="' + esc(tr("O que está sendo votado?", "What is being voted on?")) + '">' +
        (s.opcoes || []).map(function (o, k) {
          return '<button type="button" class="vp-op anim" style="--i:' + (k + 2) + '" data-vp-op="' + k + '" aria-pressed="false"><span class="vp-ic" aria-hidden="true">' +
            esc(o.ic || "") + "</span><span>" + md(o.nome) + "</span></button>";
        }).join("") + "</div>" +
        '<div class="vp-explica" aria-live="polite"><p class="muted"><span aria-hidden="true">👆 </span>' + tr("Escolha uma opção acima.", "Choose an option above.") + "</p></div>" +
        '<div class="vp-casas">' + (s.casas || []).map(function (c, j) {
          return '<div class="vp-casa anim" style="--i:' + (j + 3) + '"><h3>' + esc(c.nome) + "</h3>" +
            (T.plenario ? T.plenario({ total: c.total, max: c.total > 200 ? 400 : 260 }) : "") +
            '<p class="vp-num"><b data-vp-n="' + j + '">–</b><span data-vp-rot="' + j + '">' + esc(tr("de " + EP.num(c.total) + " " + c.quem, "out of " + EP.num(c.total) + " " + c.quem)) + "</span></p></div>";
        }).join("") + "</div>" +
        '<p class="vp-legenda" aria-hidden="true"><span><i class="s"></i>' + tr("votos “sim” precisos", "“yes” votes needed") + '</span><span><i class="n"></i>' +
        tr("votos “não”", "“no” votes") + "</span><span><i></i>" + tr("os outros", "the others") + "</span></p></div>";
    }
    if (s.id === "caminho-voto") {
      // trilha com as etapas do voto, por fase; a ficha 🗳️ anda de etapa em etapa e o balão explica cada uma
      var et = s.etapas || [];
      return cab(s) + '<div class="cv" data-cv="' + idx + '"><div class="cv-trilha">' + (s.fases || []).map(function (f, fi) {
        var dela = et.map(function (x, k) { return { x: x, k: k }; }).filter(function (o) { return o.x.fase === f.id; });
        return '<div class="cv-fase anim" style="--i:' + (fi + 2) + ";--n:" + Math.max(1, dela.length) + '" data-fase="' + esc(f.id) + '"><h3 class="cv-fase-tit"><span aria-hidden="true">' + esc(f.ic || "") + " </span>" + md(f.nome) + "</h3>" +
          '<ol class="cv-casas" start="' + (dela.length ? dela[0].k + 1 : 1) + '">' + dela.map(function (o) {
            return '<li><button type="button" class="cv-casa" data-cv-ir="' + o.k + '"><span class="cv-n" aria-hidden="true">' + (o.k + 1) + '</span><span class="c-ic" aria-hidden="true">' +
              esc(o.x.ic || "•") + "</span><b>" + md(o.x.titulo) + "</b></button></li>";
          }).join("") + "</ol></div>";
      }).join("") + '<span class="cv-ficha" aria-hidden="true">🗳️</span></div>' +
        '<div class="cv-balao" aria-live="polite"></div>' +
        '<div class="cv-ctrl"><button type="button" class="btn peq bege" data-cv-ant="' + idx + '">◀ ' + tr("Etapa anterior", "Previous step") + "</button>" +
        '<button type="button" class="btn peq" data-cv-prox="' + idx + '">' + tr("Próxima etapa ▶", "Next step ▶") + "</button>" +
        '<button type="button" class="btn peq claro" data-cv-auto="' + idx + '" aria-pressed="false">' + cvTextoAuto() + "</button>" +
        '<button type="button" class="btn peq bege" data-cv-zera="' + idx + '">↺ ' + tr("Recomeçar", "Start over") + "</button></div></div>";
    }
    if (s.id === "lacre-digital") {
      // a pessoa escreve e vê o hash de verdade (Web Crypto); guarda um lacre, troca uma letra e compara
      return cab(s) + '<div class="lacre" data-lacre="' + idx + '"><div class="lacre-entrada anim" style="--i:3">' +
        '<label for="lacre-txt-' + idx + '">✏️ ' + tr("Escreva qualquer coisa", "Write anything") + "</label>" +
        '<textarea id="lacre-txt-' + idx + '" class="lacre-txt" rows="2" maxlength="300" spellcheck="false" autocomplete="off">' + esc(s.inicial || "") + "</textarea>" +
        '<div class="lacre-botoes"><button type="button" class="btn peq" data-lacre-troca="' + idx + '">🔤 ' + tr("Trocar uma letra", "Change one letter") + "</button>" +
        '<button type="button" class="btn peq claro" data-lacre-guarda="' + idx + '">🔏 ' + tr("Guardar este lacre", "Save this seal") + "</button></div>" +
        '<div class="lacre-algo" role="group" aria-label="' + esc(tr("Tipo de lacre (hash)", "Type of seal (hash)")) + '">' +
        '<button type="button" data-lacre-algo="SHA-256" aria-pressed="true">SHA-256</button>' +
        '<button type="button" data-lacre-algo="SHA-512" aria-pressed="false">SHA-512 <small>' + tr("(o das listas do TSE)", "(used in the TSE lists)") + "</small></button></div></div>" +
        '<div class="lacre-saida anim" style="--i:4"><p class="lacre-rot"><span aria-hidden="true">🔏 </span>' + tr("Lacre digital (hash) do texto:", "Digital seal (hash) of the text:") + "</p>" +
        '<p class="lacre-codigo" translate="no"></p><p class="lacre-conta"></p>' +
        '<div class="lacre-guardado" hidden><p class="lacre-rot"><span aria-hidden="true">📦 </span>' + tr("Lacre guardado:", "Saved seal:") + '</p><p class="lacre-codigo g" translate="no"></p></div>' +
        '<p class="lacre-status" role="status" aria-live="polite"></p></div>' +
        (s.explica ? '<p class="lacre-explica anim" style="--i:5"><span aria-hidden="true">💡 </span>' + md(s.explica) + "</p>" : "") + "</div>";
    }
    if (s.id === "confira-boletim") {
      // boletim de exemplo (dados inventados): o papel pregado na seção × o resultado "publicado"; a pessoa acha a linha diferente
      var ls = s.linhas || [], sc = s.secao || {};
      var somaP = ls.reduce(function (a, l) { return a + (+l.papel || 0); }, 0), somaS = ls.reduce(function (a, l) { return a + (+l.site || 0); }, 0);
      var qr = "", mapaQr = "111010110101101011010110011101110010110100101101011100101011010110111010100101";
      for (var q = 0; q < 49; q++) qr += "<i" + (mapaQr.charAt(q) === "1" ? ' class="p"' : "") + "></i>";
      return cab(s) + '<div class="cb" data-cb="' + idx + '">' + (s.aviso ? '<p class="cb-aviso anim" style="--i:3"><span aria-hidden="true">⚠️ </span>' + md(s.aviso) + "</p>" : "") +
        '<div class="cb-duas"><div class="cb-papel anim" style="--i:4"><h3><span aria-hidden="true">🧾 </span>' + tr("Boletim pregado na seção (papel)", "Report posted at the polling station (paper)") + "</h3>" +
        '<div class="cb-bu"><p class="cb-bu-cab"><b>' + tr("BOLETIM DE URNA", "VOTING MACHINE REPORT") + "</b><br>" + tr("EXEMPLO", "EXAMPLE") + " · " + esc(sc.municipio || "") + "<br>" +
        tr("Zona ", "Zone ") + esc(sc.zona || "") + " · " + tr("Seção ", "Station ") + esc(sc.secao || "") + (sc.local ? " · " + esc(sc.local) : "") + "</p>" +
        '<table class="cb-tab"><caption class="sr">' + tr("Votos no boletim de papel", "Votes on the paper report") + "</caption><tbody>" +
        ls.map(function (l, k) { return '<tr data-cb-p="' + k + '"><th scope="row">' + md(l.nome) + "</th><td>" + EP.num(l.papel) + "</td></tr>"; }).join("") +
        '</tbody><tfoot><tr><th scope="row">' + tr("Total de votos", "Total votes") + "</th><td>" + EP.num(somaP) + "</td></tr></tfoot></table>" +
        (s.aptos ? '<p class="cb-mini">' + tr("Eleitores aptos: ", "Eligible voters: ") + EP.num(s.aptos) + " · " + tr("Votaram: ", "Voted: ") + EP.num(somaP) + "</p>" : "") +
        '<div class="cb-qr" aria-hidden="true">' + qr + '</div><p class="cb-mini">✍️ ' + tr("Assinaturas dos mesários e dos fiscais", "Signatures of the poll workers and party monitors") + "</p></div></div>" +
        '<div class="cb-site anim" style="--i:5"><h3><span aria-hidden="true">🌐 </span>' + tr("Resultado publicado na internet (exemplo)", "Result published online (example)") + "</h3>" +
        '<p class="cb-dica">' + tr("Toque na linha que está diferente do papel.", "Tap the line that is different from the paper.") + "</p>" +
        '<ul class="cb-linhas" aria-label="' + esc(tr("Linhas do resultado publicado", "Lines of the published result")) + '">' + ls.map(function (l, k) {
          return '<li><button type="button" class="cb-linha" data-cb-linha="' + k + '" aria-pressed="false"><span>' + md(l.nome) + "</span><b>" + EP.num(l.site) + "</b></button></li>";
        }).join("") + '</ul><p class="cb-total">' + tr("Total de votos: ", "Total votes: ") + "<b>" + EP.num(somaS) + "</b></p></div></div>" +
        '<div class="cb-resp" role="status" aria-live="polite"></div>' +
        '<div class="botoes cb-ctrl">' + (s.qr ? '<button type="button" class="btn peq claro" data-cb-qr="' + idx + '">📱 ' + tr("Ler o QR Code (de mentirinha)", "Read the QR Code (pretend)") + "</button>" : "") +
        '<button type="button" class="btn peq bege" data-cb-zera="' + idx + '">↺ ' + tr("Recomeçar", "Start over") + "</button></div></div>";
    }
    if (s.id === "caminho-lei") {
      var p = s.passos || [];
      return cab(s) + '<div class="tabuleiro" data-lei="' + idx + '"><ol class="casas" style="--n:' + p.length + '">' + p.map(function (x, k) {
        return '<li class="casa' + (k === 0 ? " aqui" : "") + '"><span class="c-ic" aria-hidden="true">' + esc(x.ic || "•") + "</span><b>" + md(x.titulo) + "</b></li>";
      }).join("") + '</ol><div class="balao-lei" aria-live="polite"></div><div class="ctrl-lei"><button type="button" class="btn" data-lei-anda="' + idx + '"></button>' +
        '<button type="button" class="btn bege" data-lei-zera="' + idx + '">↺ ' + tr("Recomeçar", "Start over") + "</button></div></div>";
    }
    return cab(s) + (s.passos ? R.passos(s, P, idx) : "");
  };

  // ---------------------------------------------------------------- aula de uma parada
  var SL = [], SECS = [], TIT = [], atual = -1, parteAtual = null, QUIZ = {}, GLOSS = [], empurrou = false;
  function textoDoSlide(s) {
    var t = [];
    (function anda(v) {
      if (v == null) return;
      if (typeof v === "string") t.push(v);
      else if (Array.isArray(v)) v.forEach(anda);
      else if (typeof v === "object") Object.keys(v).forEach(function (k) { if (["fontes", "ic", "tipo", "id", "ilustracao", "emoji", "quem"].indexOf(k) < 0) anda(v[k]); });
    })(s);
    return t.join(" ");
  }
  function palavrasDo(s, P) {
    var txt = " " + EP.norm(textoDoSlide(s)).replace(/[^a-z0-9]+/g, " ") + " ";
    return (P.glossario || []).filter(function (g) {
      var t = EP.norm(g.termo).replace(/[^a-z0-9]+/g, " ").trim();
      return t && (txt.indexOf(" " + t + " ") > -1 || txt.indexOf(" " + t + "s ") > -1);
    }).slice(0, 4);
  }
  function fimHtml(P) {
    var n = P.parte, I = info(), prox = proximo(n);
    if (!prox) return fimMapaHtml();
    return '<div class="fim-s"><div class="trofeu anim" aria-hidden="true">⭐</div><h1' + anim(1) + ">" + tr("Parada concluída!", "Stop completed!") + "</h1>" +
      '<p class="lead anim" style="--i:2">' + tr("Você aprendeu: ", "You learned: ") + "<b>" + esc(P.nome) + "</b></p>" +
      '<p class="placar anim" style="--i:3" id="placar-parada"></p>' +
      '<div class="botoes anim" style="--i:4">' +
      '<button class="btn" type="button" data-proxima="' + prox + '">▶ ' + tr("Próxima parada: ", "Next stop: ") + esc(I[prox].nome) + "</button>" +
      '<button class="btn claro" type="button" data-acao="mapa">🗺️ ' + tr("Voltar ao mapa", "Back to the map") + "</button>" +
      '<button class="btn bege" type="button" data-acao="recomecar">↺ ' + tr("Ver esta parada de novo", "See this stop again") + "</button></div></div>";
  }
  // fim da última parada que faltava: o mapa está completo. Em vez de sugerir recomeçar, pergunta o que a pessoa quer fazer.
  function fimMapaHtml() {
    function porta(tag, attr, ic, titulo, txt) {
      return "<" + tag + " " + attr + '><span aria-hidden="true">' + ic + "</span><span><b>" + titulo + "</b><small>" + txt + "</small></span></" + tag + ">";
    }
    return '<div class="fim-s fim-mapa"><div class="trofeu anim" aria-hidden="true">🏆</div>' +
      "<h1" + anim(1) + ">" + tr("Você completou o Mapa da Política!", "You completed the Politics Map!") + "</h1>" +
      '<p class="lead anim" style="--i:2">' + tr("Agora você sabe como a política do Brasil funciona: os Poderes, os cargos, as leis, as eleições e a urna eletrônica.",
        "Now you know how politics works in Brazil: the branches of government, the offices, the laws, the elections and the electronic voting machine.") + "</p>" +
      '<p class="placar anim" style="--i:3" id="placar-parada"></p>' +
      '<h2 class="pergunta-fim anim" style="--i:4">' + tr("E agora, o que você quer fazer?", "What would you like to do next?") + "</h2>" +
      '<div class="portas-fim tres anim" style="--i:5">' +
      porta("a", 'href="brasil.html' + (EP.en ? "?lang=en" : "") + '"', "🏛️", tr("Ver quem está no poder no Brasil", "See who is in power in Brazil"),
        tr("Presidente, ministros, senadores e deputados federais, com o que cada um propôs.", "The President, ministers, senators and federal deputies, with what each one proposed.")) +
      porta("a", 'href="estado.html' + (EP.en ? "?lang=en" : "") + '"', "📍", tr("Ver a política do meu estado", "See the politics of my state"),
        tr("Governador, deputados estaduais e, na sua cidade, prefeito e vereadores.", "The governor, state deputies and, in your city, the mayor and city councilors.")) +
      porta("button", 'type="button" data-compartilhar="mapa-completo"', "📤", tr("Compartilhar o site", "Share the site"),
        tr("Ajude mais gente a entender a política também.", "Help more people understand politics too.")) +
      "</div>" +
      '<p class="anim" style="--i:6"><button class="btn claro peq" type="button" data-acao="mapa">🗺️ ' + tr("Voltar ao mapa", "Back to the map") + "</button></p></div>";
  }
  function montarAula(n) {
    var P = PARTES[n];
    parteAtual = n; DET = []; QUIZ = {}; SL = []; LACRE = {};
    cvPara();
    var temAbertura = (P.slides || []).some(function (s) { return s.tipo === "abertura"; });
    var slides = (temAbertura ? [] : [{ tipo: "abertura", titulo: P.nome, texto: P.resumo }]).concat(P.slides || []);
    slides.forEach(function (s) {
      var fontes = (s.fontes || []).map(function (id) { return (P.fontes || []).filter(function (f) { return f.id === id; })[0]; }).filter(Boolean);
      SL.push({ s: s, P: P, fontes: fontes, palavras: palavrasDo(s, P) });
    });
    SL.push({ fim: true, P: P });
    GLOSS = (P.glossario || []).slice().sort(function (a, b) { return EP.norm(a.termo).localeCompare(EP.norm(b.termo)); });
    palco.lang = EP.en && !TRADUZIDA[n] ? "pt-BR" : "";
    var semTraducao = EP.en && !TRADUZIDA[n];
    palco.innerHTML = SL.map(function (it, i) {
        var html, cls = "";
        if (it.fim) html = fimHtml(P);
        else {
          html = (R[it.s.tipo] || R.explica)(it.s, P, i) + linkDoSlide(it.s);
          if (it.s.tipo === "quiz") QUIZ[i] = { primeira: null };
          cls = "t-" + it.s.tipo;
        }
        var pe = "";
        if (!it.fim) {
          var chips = (it.palavras || []).map(function (g) {
            return '<button type="button" class="chip-palavra nao-ler" data-det="' + det("📖 " + esc(g.termo), "<p>" + md(g.simples) + "</p>") + '">📖 ' + esc(g.termo) + "</button>";
          }).join("");
          pe = '<div class="pe-slide">' + chips + (it.fontes.length ? EP.botaoFontes(it.fontes) : "") +
            (semTraducao ? '<span class="chip amarelo" lang="en">🌐 Not translated yet: showing the Portuguese original</span>' : "") + "</div>";
        }
        return '<section class="slide ' + cls + '" aria-hidden="true" data-i="' + i + '"><div class="miolo" tabindex="-1">' + html + pe + "</div></section>";
      }).join("");
    SECS = palco.querySelectorAll(".slide");
    if (T.formas && !EP.a11y("contraste")) {
      [].forEach.call(SECS, function (sec, i) {
        var it = SL[i];
        if (it.fim || (it.s && it.s.tipo === "abertura")) {
          sec.insertAdjacentHTML("afterbegin", T.formas([["cubo", "5%", "10%", 42, i % 7, 0, 18], ["esfera", "90%", "12%", 36, (i + 3) % 7, 0, 7], ["anel", "88%", "72%", 54, (i + 2) % 7, 0, 20], ["esfera", "4%", "80%", 30, (i + 5) % 7, 0, 8]]));
        }
      });
    }
    TIT = SL.map(function (it, i) { return tituloDe(i); });
    [].forEach.call(SECS, function (s) { s.addEventListener("scroll", function () { if (s === SECS[atual]) checaMais(); }, { passive: true }); });
    if (T.confirma) [].forEach.call(palco.querySelectorAll(".urna3d"), function (u) { T.confirma(u, 1800, true); });
  }
  function tituloDe(i) {
    var it = SL[i];
    if (it.fim) return tr("Fim da parada", "End of this stop");
    var s = it.s, t = s.titulo || s.pergunta || "";
    if (s.tipo === "quiz") t = tr("Pergunta: ", "Question: ") + t;
    if (s.tipo === "abertura") t = tr("Abertura: ", "Opening: ") + (s.titulo || it.P.nome);
    t = t.replace(/\*\*|\{\{|\}\}/g, "");
    return t.length > 110 ? t.slice(0, 108).replace(/\s+\S*$/, "") + "…" : t;
  }

  // ---------------------------------------------------------------- navegação
  function atualizaBarra() {
    var P = PARTES[parteAtual];
    $("nome-parte").textContent = (P.ic || "") + " " + tr("Parada ", "Stop ") + parteAtual + " · " + P.nome;
    $("progresso").style.transform = "scaleX(" + ((atual + 1) / SL.length) + ")";
    $("contador").textContent = (atual + 1) + tr(" de ", " of ") + SL.length;
    $("btn-voltar").disabled = atual === 0;
    $("btn-proximo").textContent = atual === SL.length - 1 ? "🗺️ " + tr("Mapa", "Map") : tr("Próximo ▶", "Next ▶");
  }
  // números do conteúdo vêm escritos no formato do idioma: 5.569 / 63,3 (português) ou 5,569 / 63.3 (inglês)
  function parseNum(s) { s = String(s); return parseFloat(EP.en ? s.replace(/,/g, "") : s.replace(/\./g, "").replace(",", ".")); }
  function animaNumeros(sec) {
    [].forEach.call(sec.querySelectorAll(".num3d"), function (n, k) {
      n.classList.remove("visivel");
      setTimeout(function () { n.classList.add("visivel"); }, EP.reduzido ? 0 : 250 + k * 160);
    });
    [].forEach.call(sec.querySelectorAll(".conta[data-alvo]"), function (el) {
      var alvo = el.getAttribute("data-alvo"), v = parseNum(alvo), dec = (alvo.split(EP.en ? "." : ",")[1] || "").length;
      el.textContent = alvo;
      if (isNaN(v) || EP.reduzido || !/^[\d.,]+$/.test(alvo)) return;
      el.style.minWidth = el.offsetWidth + "px";
      var t0 = null, dur = 1300, atraso = 700, ultimo = 0;
      function fmt(x) { return x.toLocaleString(EP.en ? "en-US" : "pt-BR", { minimumFractionDigits: dec, maximumFractionDigits: dec }); }
      el.textContent = fmt(0);
      function passo(t) {
        if (t0 === null) t0 = t;
        var p = Math.max(0, Math.min(1, (t - t0 - atraso) / dur));
        if (p < 1 && sec.classList.contains("ativo")) {
          if (t - ultimo >= 40) { el.textContent = fmt(v * (1 - Math.pow(1 - p, 3))); ultimo = t; }
          requestAnimationFrame(passo);
        } else el.textContent = alvo;
      }
      requestAnimationFrame(passo);
    });
  }
  // escada: a ficha sobe degrau por degrau
  var timersEscada = [];
  function sobeEscada(i) {
    var sec = SECS[i], box = sec && sec.querySelector("[data-escada]");
    if (!box) return;
    timersEscada.forEach(clearTimeout);
    timersEscada = [];
    var esc3 = box.querySelector(".escada3d"), degraus = box.querySelectorAll(".degrau-e"), itens = box.querySelectorAll(".lista-passos li"), ficha = box.querySelector(".ficha");
    var n = degraus.length, w = 112;
    // cabe na largura disponível
    var larg = box.clientWidth || 800;
    esc3.style.setProperty("--esc-escada", Math.min(1, Math.max(.32, larg / (n * w + 140))).toFixed(3));
    function vai(k) {
      [].forEach.call(degraus, function (d, j) { d.classList.toggle("aceso", j === k); d.classList.toggle("feito", j < k); });
      [].forEach.call(itens, function (li, j) { li.classList.toggle("aceso", j === k); li.classList.toggle("feito", j < k); });
      var h = 36 + k * 26, x = k * w - (n * w) / 2;
      ficha.style.setProperty("--fx", (x + w / 2 - 23) + "px");
      ficha.style.setProperty("--fy", (-h - 52) + "px");
      ficha.textContent = k === n - 1 ? "⭐" : "📄";
    }
    if (EP.reduzido) { vai(n - 1); return; }
    for (var k = 0; k < n; k++) (function (k) { timersEscada.push(setTimeout(function () { if (sec.classList.contains("ativo")) vai(k); }, 500 + k * 900)); })(k);
  }
  function entrou(sec, i) {
    animaNumeros(sec);
    sobeEscada(i);
    var pl = [].filter.call(sec.querySelectorAll(".plenario"), function (x) { return !x.closest("[data-vp]"); })[0];  // o do jogo de votos acende por conta própria
    if (pl) { pl.classList.remove("cheio"); setTimeout(function () { pl.classList.add("cheio"); }, 500); }
    var lei = sec.querySelector("[data-lei]");
    if (lei && !lei.getAttribute("data-pos")) leiMostra(+lei.getAttribute("data-lei"), 0);
    var qe = sec.querySelector("[data-qe]");
    if (qe && !qe.getAttribute("data-etapa")) qeZera(+qe.getAttribute("data-qe"));
    var cv = sec.querySelector("[data-cv]");
    if (cv) { if (!cv.getAttribute("data-pos")) cvMostra(i, 0); else cvFicha(cv); }
    if (sec.querySelector("[data-lacre]") && !(LACRE[i] && LACRE[i].atual)) lacreCalcula(i, false);
    if (SL[i].fim) {
      var ids = Object.keys(QUIZ), certas = ids.filter(function (k) { return QUIZ[k].primeira === true; }).length;
      var resp = ids.filter(function (k) { return QUIZ[k].primeira !== null; }).length;
      $("placar-parada").textContent = resp ? tr("🎯 Você acertou " + certas + " de " + resp + " perguntas de primeira.", "🎯 You got " + certas + " of " + resp + " questions right on the first try.") : "";
      if (!feitos[parteAtual]) { feitos[parteAtual] = true; salvaFeitos(); confete(); }
      atualizaMapa();
      EP.track("entenda_parada_" + parteAtual + "_fim");
    }
  }
  function ir(n, dir) {
    n = Math.max(0, Math.min(SL.length - 1, n));
    if (n === atual) return;
    EP.calar();
    cvPara();
    if (atual >= 0 && SECS[atual]) {
      var velho = SECS[atual];
      velho.classList.remove("ativo", "dir", "esq");
      velho.setAttribute("aria-hidden", "true");
    }
    var novo = SECS[n];
    novo.classList.remove("dir", "esq");
    void novo.offsetWidth;
    novo.classList.add("ativo", dir < 0 ? "esq" : "dir");
    novo.setAttribute("aria-hidden", "false");
    novo.scrollTop = 0;
    atual = n;
    entrou(novo, n);
    atualizaBarra();
    try { history.replaceState(history.state, "", "#parte-" + parteAtual + (n > 0 ? "-" + (n + 1) : "")); } catch (e) {}
    checaMais();
    setTimeout(checaMais, 700);
    var miolo = novo.querySelector(".miolo");
    if (miolo && !EP.janelaAberta()) miolo.focus({ preventScroll: true });
  }
  function proximoSlide() { if (atual === SL.length - 1) { voltarAoMapa(); return; } ir(atual + 1, 1); }
  function voltarSlide() { ir(atual - 1, -1); }
  var temMais = $("btn-mais");
  function checaMais() {
    var s = SECS[atual];
    temMais.hidden = !s || s.scrollTop + s.clientHeight >= s.scrollHeight - 24;
  }

  // ---------------------------------------------------------------- abrir e fechar uma parada
  var aulaAberta = false;
  function abrirParte(n, slide0, semVoo) {
    n = +n;
    if (!PARTES[n]) {
      EP.abrir("🗺️ " + tr("Parada não encontrada", "Stop not found"), "<p>" + tr("Essa parada não existe. Escolha uma das " + TOTAL + " paradas do mapa!", "That stop does not exist. Pick one of the " + TOTAL + " stops on the map!") + "</p>");
      return;
    }
    function abre() {
      montarAula(n);
      aulaAberta = true;
      document.body.classList.add("modo-aula");
      var a = $("aula");
      a.hidden = false;
      a.classList.remove("entrando");
      void a.offsetWidth;
      a.classList.add("entrando");
      $("mapa-tela").setAttribute("inert", "");
      $("mapa-tela").setAttribute("aria-hidden", "true");
      atual = -1;
      if (!/^#parte-/.test(location.hash)) { try { history.pushState({ parte: n }, "", "#parte-" + n); empurrou = true; } catch (e) {} }
      ir(Math.max(0, Math.min(SL.length - 1, slide0 || 0)), 1);
      EP.track("entenda_parada_" + n);
    }
    if (semVoo || EP.reduzido || !MAPA) abre();
    else MAPA.voar(n).then(abre);
  }
  function fecharAula(depois) {
    if (!aulaAberta) return;
    EP.calar();
    aulaAberta = false;
    timersEscada.forEach(clearTimeout);
    $("aula").hidden = true;
    document.body.classList.remove("modo-aula");
    $("mapa-tela").removeAttribute("inert");
    $("mapa-tela").removeAttribute("aria-hidden");
    $("nome-parte").textContent = "🗺️ " + tr("Mapa da Política", "Politics Map");
    palco.innerHTML = "";
    atualizaMapa();
    if (MAPA) MAPA.geral();
    var l = document.querySelector('.lugar[data-n="' + parteAtual + '"] .placa');
    if (l) l.focus({ preventScroll: true });
    if (depois) setTimeout(function () { abrirParte(depois); }, EP.reduzido ? 0 : 1050);
  }
  function voltarAoMapa(depois) {
    if (empurrou && history.state && history.state.parte) {
      proximaDepoisDoVoltar = depois || null;
      empurrou = false;
      history.back();
    } else {
      try { history.replaceState(null, "", location.pathname + location.search); } catch (e) {}
      fecharAula(depois);
    }
  }
  var proximaDepoisDoVoltar = null;
  window.addEventListener("popstate", function () {
    var m = /^#parte-(\d+)(?:-(\d+))?$/.exec(location.hash);
    if (m && !aulaAberta) { abrirParte(+m[1], m[2] ? +m[2] - 1 : 0, true); return; }
    // endereço de outra parada com a aula aberta (ex.: digitado na barra): fecha esta e abre a outra
    if (m && aulaAberta && +m[1] !== parteAtual && PARTES[+m[1]]) { empurrou = false; fecharAula(+m[1]); return; }
    if (!m && aulaAberta) { var d = proximaDepoisDoVoltar; proximaDepoisDoVoltar = null; fecharAula(d); }
  });

  // ---------------------------------------------------------------- jogos
  function confete() {
    if (EP.reduzido) return;
    var em = ["🎉", "⭐", "✨", "🎊", "👏"];
    for (var k = 0; k < 18; k++) {
      var c = document.createElement("span");
      c.className = "confete";
      c.setAttribute("aria-hidden", "true");
      c.textContent = em[k % em.length];
      c.style.left = Math.random() * 100 + "vw";
      c.style.animationDelay = Math.random() * 0.5 + "s";
      document.body.appendChild(c);
      setTimeout(function (x) { return function () { x.remove(); }; }(c), 2600);
    }
  }
  function responde(btn) {
    var i = +btn.getAttribute("data-quiz"), k = +btn.getAttribute("data-op"), s = SL[i].s;
    var sec = SECS[i], ops = sec.querySelectorAll(".opcao"), box = sec.querySelector(".resposta");
    var ok = k === s.certa;
    if (QUIZ[i].primeira === null) QUIZ[i].primeira = ok;
    [].forEach.call(ops, function (o) { o.disabled = true; });
    ops[s.certa].classList.add("certa");
    if (!ok) btn.classList.add("errada");
    box.className = "resposta " + (ok ? "ok" : "nao");
    box.innerHTML = (ok ? '<b class="grande">🎉 ' + tr("Isso mesmo!", "That's right!") + "</b>" : '<b class="grande">🤏 ' + tr("Quase! A resposta certa é a ", "Almost! The right answer is ") + LETRAS[s.certa] + ".</b>") +
      (s.explica ? "<p>" + md(s.explica) + "</p>" : "") +
      '<div class="botoes"><button type="button" class="btn peq bege" data-quiz-zera="' + i + '">↺ ' + tr("Tentar de novo", "Try again") + '</button><button type="button" class="btn peq" data-acao="proximo">' + tr("Continuar ▶", "Continue ▶") + "</button></div>";
    box.hidden = false;
    if (ok) confete();
    setTimeout(function () { box.scrollIntoView({ block: "nearest", behavior: EP.reduzido ? "auto" : "smooth" }); checaMais(); }, 50);
  }
  function quizZera(i) {
    var sec = SECS[i];
    [].forEach.call(sec.querySelectorAll(".opcao"), function (o) { o.disabled = false; o.classList.remove("certa", "errada"); });
    var box = sec.querySelector(".resposta");
    box.hidden = true;
    box.innerHTML = "";
    var primeira = sec.querySelector(".opcao");
    if (primeira) primeira.focus();
  }
  function quemCuida(btn) {
    var item = btn.closest(".qc-item"), i = +item.getAttribute("data-qc"), k = +item.getAttribute("data-k");
    var it = SL[i].s.itens[k];
    if (item.getAttribute("data-feito")) return;
    var ok = btn.getAttribute("data-quem") === it.quem;
    item.setAttribute("data-feito", ok ? "1" : "0");
    var verso = item.querySelector(".verso"), frente = item.querySelector(".frente");
    verso.querySelector(".qc-resp").textContent = (ok ? "✅ " + tr("Isso! ", "Yes! ") : "💡 " + tr("Quase! ", "Almost! ")) + tr("Quem cuida: ", "Who takes care: ") + QUEM[it.quem].replace(/^\S+\s/, "");
    verso.querySelector(".qc-explica").innerHTML = md(it.explica || "");
    item.classList.add(ok ? "certo" : "errou", "virado");
    frente.setAttribute("aria-hidden", "true");
    [].forEach.call(frente.querySelectorAll("button"), function (b) { b.tabIndex = -1; });
    verso.setAttribute("aria-hidden", "false");
    verso.focus({ preventScroll: true });
    var sec = SECS[i], feitosQ = sec.querySelectorAll(".qc-item[data-feito]"), certos = sec.querySelectorAll('.qc-item[data-feito="1"]');
    var total = SL[i].s.itens.length;
    sec.querySelector("[data-placar]").textContent = tr("Você acertou ", "You got ") + certos.length + tr(" de ", " of ") + feitosQ.length +
      (feitosQ.length === total ? ". " + (certos.length === total ? tr("Perfeito! 🎉", "Perfect! 🎉") : tr("Muito bem!", "Well done!")) : ".");
    if (feitosQ.length === total && certos.length === total) confete();
    checaMais();
  }
  function vira(btn) {
    var card = btn.closest(".card-3d");
    if (!card) return;
    var virado = !card.classList.contains("virado");
    card.classList.toggle("virado", virado);
    var frente = card.querySelector(".frente"), verso = card.querySelector(".verso");
    frente.setAttribute("aria-hidden", String(virado));
    verso.setAttribute("aria-hidden", String(!virado));
    [].forEach.call(frente.querySelectorAll("button"), function (b) { b.tabIndex = virado ? -1 : 0; });
    [].forEach.call(verso.querySelectorAll("button"), function (b) { b.tabIndex = virado ? 0 : -1; });
    var bf = frente.querySelector("[data-virar]");
    if (bf) bf.setAttribute("aria-expanded", String(virado));
    (virado ? verso : frente).focus({ preventScroll: true });
    if (virado) { var b2 = verso.querySelector("[data-virar]"); if (b2) b2.focus({ preventScroll: true }); }
    else if (bf) bf.focus({ preventScroll: true });
  }
  // caminho da lei
  function leiMostra(i, pos) {
    var sec = SECS[i], tab = sec.querySelector("[data-lei]"), p = SL[i].s.passos || [];
    tab.setAttribute("data-pos", pos);
    [].forEach.call(tab.querySelectorAll(".casa"), function (c, k) { c.classList.toggle("feita", k < pos); c.classList.toggle("aqui", k === pos); });
    var x = p[pos] || {}, ultimo = pos >= p.length - 1;
    tab.querySelector(".balao-lei").innerHTML = (ultimo ? '<div class="virou-lei" aria-hidden="true">📜✅</div>' : "") +
      "<h3>" + (pos + 1) + ". " + esc(x.ic || "") + " " + md(x.titulo || "") + "</h3>" + (x.txt ? "<p>" + md(x.txt) + "</p>" : "");
    var b = tab.querySelector("[data-lei-anda]");
    b.disabled = ultimo;
    b.textContent = ultimo ? "🎉 " + tr("Chegou ao fim!", "You made it to the end!") : "▶ " + tr("Andar uma casa", "Move one step");
    if (ultimo && pos > 0) confete();
  }
  // quantos "sim" são precisos: acende as cadeiras de cada Casa
  function vpEscolhe(b) {
    var box = b.closest("[data-vp]");
    if (!box) return;
    var s = SL[+box.getAttribute("data-vp")].s, o = (s.opcoes || [])[+b.getAttribute("data-vp-op")];
    if (!o) return;
    [].forEach.call(box.querySelectorAll("[data-vp-op]"), function (x) { x.setAttribute("aria-pressed", String(x === b)); });
    var resumo = [];
    [].forEach.call(box.querySelectorAll(".vp-casa"), function (casa, j) {
      var c = (o.casas || [])[j] || {}, sim = c.sim || 0, nao = c.nao || 0;
      [].forEach.call(casa.querySelectorAll(".plenario i"), function (it, q) {
        it.classList.toggle("s", q < sim);
        it.classList.toggle("n", q >= sim && q < sim + nao);
      });
      casa.querySelector("[data-vp-n]").textContent = EP.num(sim);
      casa.querySelector("[data-vp-rot]").innerHTML = md(c.rot || "");
      resumo.push(((s.casas || [])[j] || {}).nome + ": " + EP.num(sim) + " " + (c.rot || ""));
    });
    box.querySelector(".vp-explica").innerHTML = '<p><b><span aria-hidden="true">' + esc(o.ic || "") + " </span>" + md(o.nome) + ":</b> " + md(o.explica || "") + "</p>" +
      '<p class="sr">' + md(resumo.join(" ")) + "</p>";
  }
  // ---------------------------------------------------------------- caminho do voto: a ficha anda de etapa em etapa
  var cvTimer = null;
  function cvTextoAuto() { return "▶ " + tr("Ver o caminho todo", "Play the whole path"); }
  function cvPara() {
    if (cvTimer) { clearTimeout(cvTimer); cvTimer = null; }
    [].forEach.call(palco.querySelectorAll("[data-cv-auto]"), function (b) { b.setAttribute("aria-pressed", "false"); b.textContent = cvTextoAuto(); });
  }
  function cvFicha(box) {
    var casa = box.querySelector(".cv-casa.aqui"), trilha = box.querySelector(".cv-trilha"), ficha = box.querySelector(".cv-ficha");
    if (!casa || !trilha || !ficha || !trilha.offsetWidth) return;
    // posição pelo layout (offsetLeft/Top), que não muda durante as animações de entrada do slide
    var x = 0, y = 0, el = casa;
    while (el && el !== trilha) { x += el.offsetLeft; y += el.offsetTop; el = el.offsetParent; }
    if (el !== trilha) {
      var rt = trilha.getBoundingClientRect(), rc = casa.getBoundingClientRect();
      x = rc.left - rt.left; y = rc.top - rt.top;
    }
    ficha.style.setProperty("--fx", (x + casa.offsetWidth / 2).toFixed(1) + "px");
    ficha.style.setProperty("--fy", y.toFixed(1) + "px");
    ficha.classList.add("pronta");
  }
  function cvMostra(i, pos) {
    var sec = SECS[i], box = sec && sec.querySelector("[data-cv]"), s = SL[i].s, et = s.etapas || [];
    if (!box || !et.length) return;
    pos = Math.max(0, Math.min(et.length - 1, pos));
    box.setAttribute("data-pos", pos);
    var fases = {};
    (s.fases || []).forEach(function (f) { fases[f.id] = f; });
    [].forEach.call(box.querySelectorAll(".cv-casa"), function (c) {
      var k = +c.getAttribute("data-cv-ir");
      c.classList.toggle("feita", k < pos);
      c.classList.toggle("aqui", k === pos);
      if (k === pos) c.setAttribute("aria-current", "step"); else c.removeAttribute("aria-current");
    });
    var x = et[pos], f = fases[x.fase] || {};
    [].forEach.call(box.querySelectorAll(".cv-fase"), function (el) { el.classList.toggle("ativa", el.getAttribute("data-fase") === x.fase); });
    box.querySelector(".cv-balao").innerHTML = '<p class="cv-fase-rot"><span aria-hidden="true">' + esc(f.ic || "") + " </span>" + md(f.nome || "") + " · " + tr("etapa ", "step ") + (pos + 1) + tr(" de ", " of ") + et.length + "</p>" +
      "<h3><span aria-hidden=\"true\">" + esc(x.ic || "") + " </span>" + md(x.titulo || "") + "</h3>" +
      (x.quando ? '<p class="cv-quando"><span aria-hidden="true">🕐 </span><b>' + tr("Quando: ", "When: ") + "</b>" + md(x.quando) + "</p>" : "") +
      (x.txt ? "<p>" + md(x.txt) + "</p>" : "") +
      (x.quem ? '<p class="cv-quem"><span aria-hidden="true">👀 </span><b>' + tr("Quem confere: ", "Who checks: ") + "</b>" + md(x.quem) + "</p>" : "");
    var ba = box.querySelector("[data-cv-ant]"), bp = box.querySelector("[data-cv-prox]"), fim = pos === et.length - 1;
    // um botão com foco que fica desabilitado perde o foco: passa o foco para o botão que ainda faz sentido
    var focoAnt = document.activeElement === ba, focoProx = document.activeElement === bp;
    ba.disabled = pos === 0;
    bp.disabled = fim;
    bp.textContent = fim ? "🎉 " + tr("Chegou ao fim!", "You reached the end!") : tr("Próxima etapa ▶", "Next step ▶");
    if (focoProx && fim) box.querySelector("[data-cv-zera]").focus();
    if (focoAnt && pos === 0) bp.focus();
    cvFicha(box);
    if (fim && !box.getAttribute("data-fim")) { box.setAttribute("data-fim", "1"); confete(); }
    checaMais();
  }
  function cvAuto(i) {
    if (cvTimer) { cvPara(); return; }
    var box = SECS[i].querySelector("[data-cv]"), b = box.querySelector("[data-cv-auto]"), et = SL[i].s.etapas || [];
    if (+box.getAttribute("data-pos") >= et.length - 1) cvMostra(i, 0);
    b.setAttribute("aria-pressed", "true");
    b.textContent = "⏸ " + tr("Pausar", "Pause");
    (function passo() {
      cvTimer = setTimeout(function () {
        var p = +box.getAttribute("data-pos");
        if (!SECS[i] || !SECS[i].classList.contains("ativo") || p >= et.length - 1) { cvPara(); return; }
        cvMostra(i, p + 1);
        if (p + 1 >= et.length - 1) cvPara(); else passo();
      }, EP.reduzido ? 4500 : 3200);
    })();
  }

  // ---------------------------------------------------------------- lacre digital: hash de verdade (Web Crypto), guardar e comparar
  var LACRE = {};
  function hexDe(buf) { return Array.prototype.map.call(new Uint8Array(buf), function (b) { return ("0" + b.toString(16)).slice(-2); }).join(""); }
  // o código em blocos de 8; o que mudou em relação ao lacre anterior fica marcado
  function lacreHtml(h, ant) {
    var out = "", marcado = false;
    for (var k = 0; k < h.length; k++) {
      var mudou = !!ant && ant.charAt(k) !== h.charAt(k);
      if (mudou !== marcado) { out += mudou ? "<mark>" : "</mark>"; marcado = mudou; }
      out += h.charAt(k);
      if (k % 8 === 7 && k < h.length - 1) { if (marcado) { out += "</mark>"; marcado = false; } out += " "; }
    }
    return out + (marcado ? "</mark>" : "");
  }
  function lacreEstado(i) { return LACRE[i] || (LACRE[i] = { algo: "SHA-256", pedido: 0 }); }
  function lacreCompara(i) {
    var st = lacreEstado(i), box = SECS[i].querySelector("[data-lacre]"), g = box.querySelector(".lacre-guardado");
    g.classList.remove("igual", "diferente");
    if (!st.guardado) return "";
    if (st.guardadoAlgo !== st.atualAlgo) return tr("O lacre guardado é de outro tipo (" + st.guardadoAlgo + "). Guarde um novo para comparar.", "The saved seal is of another type (" + st.guardadoAlgo + "). Save a new one to compare.");
    var igual = st.guardado === st.atual;
    g.classList.add(igual ? "igual" : "diferente");
    return igual ? "✅ " + tr("Igual ao lacre guardado: o texto é o mesmo.", "Same as the saved seal: the text is the same.") :
      "❌ " + tr("Diferente do lacre guardado: o texto mudou.", "Different from the saved seal: the text changed.");
  }
  function lacreAnuncia(i, extra) {
    var st = lacreEstado(i), box = SECS[i].querySelector("[data-lacre]"), h = st.atual || "";
    if (!h) return;
    var msg = (extra ? extra + " " : "") + tr("Lacre (" + st.atualAlgo + "): começa com " + h.slice(0, 4) + " e termina com " + h.slice(-4) + ".",
      "Seal (" + st.atualAlgo + "): starts with " + h.slice(0, 4) + " and ends with " + h.slice(-4) + ".");
    if (st.mudou) msg += " " + tr("Mudaram " + st.mudou + " de " + h.length + " caracteres.", st.mudou + " of " + h.length + " characters changed.");
    var c = lacreCompara(i);
    box.querySelector(".lacre-status").textContent = msg + (c ? " " + c : "");
  }
  function lacreCalcula(i, anunciar, extra) {
    var box = SECS[i] && SECS[i].querySelector("[data-lacre]"), st = lacreEstado(i);
    if (!box) return Promise.resolve();
    var sub = window.crypto && window.crypto.subtle;
    if (!sub || !window.TextEncoder) {
      box.querySelector(".lacre-codigo").textContent = "—";
      box.querySelector(".lacre-status").textContent = tr("Este navegador não deixou calcular o lacre aqui: ele precisa de uma conexão segura (https).",
        "This browser did not allow the seal to be computed here: it needs a secure connection (https).");
      return Promise.resolve();
    }
    var algo = st.algo, pedido = ++st.pedido, txt = box.querySelector(".lacre-txt").value;
    return sub.digest(algo, new TextEncoder().encode(txt)).then(function (buf) {
      if (pedido !== st.pedido) return;   // já chegou um cálculo mais novo
      var h = hexDe(buf), ant = st.atual && st.atualAlgo === algo ? st.atual : null, mud = 0;
      if (ant) for (var k = 0; k < h.length; k++) if (ant.charAt(k) !== h.charAt(k)) mud++;
      st.atual = h; st.atualAlgo = algo; st.mudou = ant && ant !== h ? mud : 0;
      box.querySelector(".lacre-codigo:not(.g)").innerHTML = lacreHtml(h, ant !== h ? ant : null);
      box.querySelector(".lacre-conta").textContent = ant && ant !== h ? tr("Em amarelo: os " + mud + " caracteres (de " + h.length + ") que mudaram em relação ao lacre anterior.",
        "In yellow: the " + mud + " characters (out of " + h.length + ") that changed from the previous seal.") :
        tr("Este lacre tem " + h.length + " caracteres.", "This seal has " + h.length + " characters.");
      lacreCompara(i);
      if (anunciar) lacreAnuncia(i, extra);
      checaMais();
    }).catch(function () {
      box.querySelector(".lacre-status").textContent = tr("Não deu para calcular o lacre neste navegador.", "The seal could not be computed in this browser.");
    });
  }
  var lacreT1 = null, lacreT2 = null;
  function lacreDigitou(el) {
    var i = +el.closest("[data-lacre]").getAttribute("data-lacre");
    clearTimeout(lacreT1); clearTimeout(lacreT2);
    lacreT1 = setTimeout(function () { lacreCalcula(i, false); }, 120);
    lacreT2 = setTimeout(function () { lacreAnuncia(i); }, 900);
  }
  // troca a última letra: "o" vira "a", e qualquer outra vira "o" (apertar de novo volta ao texto de antes, com "o" e "a")
  function trocaLetra(t) {
    for (var k = t.length - 1; k >= 0; k--) {
      var c = t.charAt(k), m = c.toLowerCase();
      if (/[a-zà-ÿ]/.test(m)) {
        var novo = m === "o" ? "a" : "o";
        return t.slice(0, k) + (c !== m ? novo.toUpperCase() : novo) + t.slice(k + 1);
      }
    }
    return t + "a";
  }

  // ---------------------------------------------------------------- confira o boletim (exemplo com dados inventados)
  function cbEscolhe(btn) {
    var box = btn.closest("[data-cb]"), i = +box.getAttribute("data-cb"), s = SL[i].s, k = +btn.getAttribute("data-cb-linha"), l = (s.linhas || [])[k];
    if (!l || box.getAttribute("data-achou")) return;
    var resp = box.querySelector(".cb-resp");
    btn.setAttribute("aria-pressed", "true");
    if (+l.papel !== +l.site) {
      box.setAttribute("data-achou", "1");
      btn.classList.add("achou");
      var linhaP = box.querySelector('[data-cb-p="' + k + '"]');
      if (linhaP) linhaP.classList.add("achou");
      box.querySelector(".cb-total").classList.add("achou");
      resp.className = "cb-resp ok";
      resp.innerHTML = '<p><span aria-hidden="true">🎉 </span>' + md(s.acerto || "") + "</p>";
      confete();
    } else {
      btn.classList.add("igual");
      resp.className = "cb-resp nao";
      resp.innerHTML = '<p><span aria-hidden="true">🔎 </span>' + md(s.erro || "") + "</p>";
    }
    checaMais();
  }
  function cbZera(i) {
    var box = SECS[i].querySelector("[data-cb]");
    box.removeAttribute("data-achou");
    [].forEach.call(box.querySelectorAll(".achou, .igual"), function (el) { el.classList.remove("achou", "igual"); });
    [].forEach.call(box.querySelectorAll("[data-cb-linha]"), function (b) { b.setAttribute("aria-pressed", "false"); });
    var resp = box.querySelector(".cb-resp");
    resp.className = "cb-resp";
    resp.innerHTML = "";
    var b0 = box.querySelector("[data-cb-linha]");
    if (b0) b0.focus();
  }
  function cbQr(i) {
    var box = SECS[i].querySelector("[data-cb]"), s = SL[i].s, resp = box.querySelector(".cb-resp");
    box.classList.add("leu-qr");
    resp.className = "cb-resp info";
    resp.innerHTML = '<p><span aria-hidden="true">📱 </span>' + md(s.qr || "") + "</p><p class=\"cb-mini\">" + (s.linhas || []).map(function (l) { return md(l.nome) + ": " + EP.num(l.papel); }).join(" · ") + "</p>";
    checaMais();
  }

  // quociente eleitoral (Código Eleitoral, arts. 106 a 109)
  // partidos inventados (Círculo, Quadrado...): cor pela ordem, sem lembrar cores de partidos reais
  function corDe(nome, k) { return PALETA[k % PALETA.length]; }
  function qeCalc(s) {
    var ps = (s.partidos || []).map(function (p, k) { return { nome: p.nome, votos: +p.votos, cor: corDe(p.nome, k), qp: 0, sobra: 0 }; });
    var total = ps.reduce(function (a, p) { return a + p.votos; }, 0), vagas = +s.cadeiras;
    var bruto = total / vagas, qe = bruto - Math.floor(bruto) > 0.5 ? Math.ceil(bruto) : Math.floor(bruto);
    ps.forEach(function (p) { p.qp = Math.floor(p.votos / qe); });
    var usadas = ps.reduce(function (a, p) { return a + p.qp; }, 0), ordem = [];
    var aptos = ps.filter(function (p) { return p.votos >= 0.8 * qe; });
    if (!aptos.length) aptos = ps;
    for (var v = usadas; v < vagas; v++) {
      var melhor = null;
      aptos.forEach(function (p) { var m = p.votos / (p.qp + p.sobra + 1); if (!melhor || m > melhor.m || (m === melhor.m && p.votos > melhor.p.votos)) melhor = { p: p, m: m }; });
      melhor.p.sobra++;
      ordem.push(melhor.p);
    }
    return { ps: ps, total: total, vagas: vagas, qe: qe, usadas: usadas, ordem: ordem };
  }
  function cadeirasTxt(n) { return n + (n === 1 ? tr(" cadeira", " seat") : tr(" cadeiras", " seats")); }
  function qeZera(i) {
    var sec = SECS[i], box = sec.querySelector("[data-qe]"), c = qeCalc(SL[i].s), maxv = Math.max.apply(null, c.ps.map(function (p) { return p.votos; }));
    box.setAttribute("data-etapa", "0");
    box.querySelector(".qe-partidos").innerHTML = c.ps.map(function (p) {
      return '<div class="qe-p" style="--cor:' + p.cor + '"><div class="linha"><span>' + esc(p.nome) + "</span><span>" + EP.num(p.votos) + tr(" votos", " votes") + "</span></div>" +
        '<div class="trilho" aria-hidden="true"><i style="--w:' + (100 * p.votos / maxv).toFixed(1) + '%"></i></div><div class="cadeiras-p"></div></div>';
    }).join("");
    var cad = "";
    for (var k = 0; k < c.vagas; k++) cad += "<i></i>";
    box.querySelector(".qe-cadeiras").innerHTML = cad;
    box.querySelector(".qe-conta").innerHTML = tr("Toque no botão para começar a conta. São " + EP.num(c.total) + " votos válidos e " + c.vagas + " cadeiras.",
      "Tap the button to start counting. There are " + EP.num(c.total) + " valid votes and " + c.vagas + " seats.");
    var b = box.querySelector("[data-qe-passo]");
    b.disabled = false;
    b.textContent = "1️⃣ " + tr("Calcular o quociente ▶", "Work out the quota ▶");
  }
  function qePasso(i) {
    var sec = SECS[i], box = sec.querySelector("[data-qe]"), s = SL[i].s, c = qeCalc(s);
    var etapa = +box.getAttribute("data-etapa") + 1, conta = box.querySelector(".qe-conta"), b = box.querySelector("[data-qe-passo]");
    var cads = box.querySelectorAll(".qe-cadeiras i"), linhas = box.querySelectorAll(".cadeiras-p"), extra = (s.passos || [])[etapa - 1];
    box.setAttribute("data-etapa", etapa);
    if (etapa === 1) {
      conta.innerHTML = "<b>" + tr("Quociente eleitoral", "Electoral quota") + "</b> = " + EP.num(c.total) + tr(" votos ÷ ", " votes ÷ ") + cadeirasTxt(c.vagas) + " = <b>" + EP.num(c.qe) + tr(" votos", " votes") + "</b>. " +
        tr("É o \"preço\" de uma cadeira.", "That is the \"price\" of one seat.") + (extra ? "<br><small>" + md(extra) + "</small>" : "");
      b.textContent = "2️⃣ " + tr("Distribuir as cadeiras ▶", "Share out the seats ▶");
    } else if (etapa === 2) {
      var pos = 0;
      c.ps.forEach(function (p, k) {
        for (var j = 0; j < p.qp; j++) { cads[pos].style.setProperty("--cor", p.cor); cads[pos].style.setProperty("--k", pos); cads[pos].classList.add("ocupada"); pos++; }
        linhas[k].textContent = EP.num(p.votos) + " ÷ " + EP.num(c.qe) + " = " + cadeirasTxt(p.qp);
      });
      var sobram = c.vagas - c.usadas;
      conta.innerHTML = tr("Cada partido ganha uma cadeira para cada " + EP.num(c.qe) + " votos. Foram <b>" + cadeirasTxt(c.usadas) + "</b>.", "Each party gets one seat for every " + EP.num(c.qe) + " votes. That makes <b>" + cadeirasTxt(c.usadas) + "</b>.") +
        (sobram > 0 ? " " + tr("Sobraram <b>" + sobram + "</b>.", "<b>" + sobram + "</b> left over.") : "") + (extra ? "<br><small>" + md(extra) + "</small>" : "");
      b.textContent = sobram > 0 ? "3️⃣ " + tr("Distribuir as sobras ▶", "Share out the leftovers ▶") : "✅ " + tr("Pronto!", "Done!");
      if (sobram <= 0) b.disabled = true;
    } else {
      var pos2 = c.usadas;
      c.ordem.forEach(function (p, j) { cads[pos2].style.setProperty("--cor", p.cor); cads[pos2].style.setProperty("--k", j); cads[pos2].classList.add("ocupada"); pos2++; });
      c.ps.forEach(function (p, k) { var t = p.qp + p.sobra; linhas[k].textContent = "🪑 " + cadeirasTxt(t) + (p.sobra ? tr(" (" + p.sobra + " da sobra)", " (" + p.sobra + " from leftovers)") : ""); });
      conta.innerHTML = tr("As cadeiras que sobraram vão para os partidos com as <b>maiores médias</b> de votos por cadeira.", "The leftover seats go to the parties with the <b>highest averages</b> of votes per seat.") + (extra ? "<br><small>" + md(extra) + "</small>" : "");
      b.textContent = "✅ " + tr("Pronto!", "Done!");
      b.disabled = true;
      confete();
    }
    checaMais();
  }

  // ---------------------------------------------------------------- menu de páginas e palavras
  function abrirMenu() {
    var html = '<ol class="mp-sub">' + SL.map(function (it, i) {
      return '<li><button type="button" data-ir="' + i + '"' + (i === atual ? ' class="atual" aria-current="page"' : "") + '><span class="mp-num">' + (i + 1) + "</span><span>" + esc(TIT[i]) + "</span></button></li>";
    }).join("") + "</ol>";
    EP.abrir("☰ " + tr("Páginas desta parada", "Pages in this stop"), html +
      (GLOSS.length ? '<p style="margin-top:14px"><button type="button" class="btn peq claro" data-glossario>📖 ' + tr("Palavras difíceis", "Hard words") + " (" + GLOSS.length + ")</button></p>" : "") +
      '<p style="margin-top:8px"><button type="button" class="btn peq bege" data-acao="mapa">🗺️ ' + tr("Voltar ao mapa", "Back to the map") + "</button></p>");
  }
  function abrirGlossario() {
    EP.abrir("📖 " + tr("Palavras difíceis", "Hard words"), '<div class="glossario-lista">' + GLOSS.map(function (g) { return "<div><b>" + esc(g.termo) + "</b>: " + md(g.simples) + "</div>"; }).join("") + "</div>");
  }

  // ---------------------------------------------------------------- eventos
  document.addEventListener("click", function (e) {
    // botão de um slide que leva a outra parada (ex.: entenda.html#parte-10): o mapa voa até ela
    var lk = e.target.closest ? e.target.closest(".link-slide a[href]") : null;
    if (lk && aulaAberta && !e.button && !e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey) {
      var mm = /^entenda\.html(?:\?[^#]*)?#parte-(\d+)$/.exec(lk.getAttribute("href") || "");
      if (mm && PARTES[+mm[1]] && +mm[1] !== parteAtual) { e.preventDefault(); EP.fechar(); voltarAoMapa(+mm[1]); return; }
    }
    var t = e.target.closest ? e.target.closest("[data-acao],[data-ir],[data-det],[data-quiz],[data-quiz-zera],[data-quem],[data-lei-anda],[data-lei-zera],[data-qe-passo],[data-qe-zera],[data-vp-op],[data-compartilhar],[data-glossario],[data-virar],[data-abrir-parada],[data-proxima],[data-escada-replay]," +
      "[data-cv-ir],[data-cv-ant],[data-cv-prox],[data-cv-auto],[data-cv-zera],[data-lacre-troca],[data-lacre-guarda],[data-lacre-algo],[data-cb-linha],[data-cb-qr],[data-cb-zera]") : null;
    if (!t) return;
    if (t.hasAttribute("data-cv-ir")) { cvPara(); cvMostra(+t.closest("[data-cv]").getAttribute("data-cv"), +t.getAttribute("data-cv-ir")); return; }
    if (t.hasAttribute("data-cv-ant") || t.hasAttribute("data-cv-prox")) {
      cvPara();
      var ci = +t.closest("[data-cv]").getAttribute("data-cv"), cbox = SECS[ci].querySelector("[data-cv]");
      cvMostra(ci, +cbox.getAttribute("data-pos") + (t.hasAttribute("data-cv-prox") ? 1 : -1));
      return;
    }
    if (t.hasAttribute("data-cv-auto")) { cvAuto(+t.getAttribute("data-cv-auto")); return; }
    if (t.hasAttribute("data-cv-zera")) { cvPara(); var zi = +t.getAttribute("data-cv-zera"); SECS[zi].querySelector("[data-cv]").removeAttribute("data-fim"); cvMostra(zi, 0); return; }
    if (t.hasAttribute("data-lacre-troca")) {
      var ti = +t.getAttribute("data-lacre-troca"), ta = SECS[ti].querySelector(".lacre-txt");
      ta.value = trocaLetra(ta.value);
      lacreCalcula(ti, true, tr("Uma letra trocada.", "One letter changed."));
      return;
    }
    if (t.hasAttribute("data-lacre-guarda")) {
      var gi = +t.getAttribute("data-lacre-guarda"), gst = lacreEstado(gi), gbox = SECS[gi].querySelector("[data-lacre]");
      if (!gst.atual) return;
      gst.guardado = gst.atual; gst.guardadoAlgo = gst.atualAlgo;
      var gg = gbox.querySelector(".lacre-guardado");
      gg.hidden = false;
      gg.querySelector(".lacre-codigo").innerHTML = lacreHtml(gst.guardado, null);
      lacreAnuncia(gi, tr("Lacre guardado. Agora troque uma letra e compare.", "Seal saved. Now change one letter and compare."));
      checaMais();
      return;
    }
    if (t.hasAttribute("data-lacre-algo")) {
      var abox = t.closest("[data-lacre]"), ai = +abox.getAttribute("data-lacre");
      lacreEstado(ai).algo = t.getAttribute("data-lacre-algo");
      [].forEach.call(abox.querySelectorAll("[data-lacre-algo]"), function (b) { b.setAttribute("aria-pressed", String(b === t)); });
      lacreCalcula(ai, true);
      return;
    }
    if (t.hasAttribute("data-cb-linha")) { cbEscolhe(t); return; }
    if (t.hasAttribute("data-cb-qr")) { cbQr(+t.getAttribute("data-cb-qr")); return; }
    if (t.hasAttribute("data-cb-zera")) { cbZera(+t.getAttribute("data-cb-zera")); return; }
    if (t.hasAttribute("data-compartilhar")) { EP.compartilhar(t.getAttribute("data-compartilhar")); return; }
    if (t.hasAttribute("data-abrir-parada")) { EP.fechar(); abrirParte(+t.getAttribute("data-abrir-parada")); return; }
    if (t.hasAttribute("data-proxima")) { voltarAoMapa(+t.getAttribute("data-proxima")); return; }
    if (t.hasAttribute("data-ir")) { var n = +t.getAttribute("data-ir"); EP.fechar(); ir(n, n >= atual ? 1 : -1); return; }
    if (t.hasAttribute("data-det")) { var d = DET[+t.getAttribute("data-det")]; EP.abrir(d.t, d.h); return; }
    if (t.hasAttribute("data-glossario")) { abrirGlossario(); return; }
    if (t.hasAttribute("data-virar")) { vira(t); return; }
    if (t.hasAttribute("data-quiz")) { responde(t); return; }
    if (t.hasAttribute("data-quiz-zera")) { quizZera(+t.getAttribute("data-quiz-zera")); return; }
    if (t.hasAttribute("data-quem")) { quemCuida(t); return; }
    if (t.hasAttribute("data-escada-replay")) { sobeEscada(+t.getAttribute("data-escada-replay")); return; }
    if (t.hasAttribute("data-lei-anda")) { var li = +t.getAttribute("data-lei-anda"), tab = SECS[li].querySelector("[data-lei]"); leiMostra(li, +tab.getAttribute("data-pos") + 1); checaMais(); return; }
    if (t.hasAttribute("data-lei-zera")) { leiMostra(+t.getAttribute("data-lei-zera"), 0); return; }
    if (t.hasAttribute("data-qe-passo")) { qePasso(+t.getAttribute("data-qe-passo")); return; }
    if (t.hasAttribute("data-qe-zera")) { qeZera(+t.getAttribute("data-qe-zera")); return; }
    if (t.hasAttribute("data-vp-op")) { vpEscolhe(t); return; }
    var a = t.getAttribute("data-acao");
    if (a === "proximo") proximoSlide();
    else if (a === "recomecar") ir(0, -1);
    else if (a === "fim") ir(SL.length - 1, 1);
    else if (a === "mapa") { EP.fechar(); voltarAoMapa(); }
  });
  // lacre digital: recalcula enquanto a pessoa escreve
  palco.addEventListener("input", function (e) { if (e.target.classList && e.target.classList.contains("lacre-txt")) lacreDigitou(e.target); });
  $("btn-proximo").addEventListener("click", proximoSlide);
  $("btn-voltar").addEventListener("click", voltarSlide);
  $("btn-menu").addEventListener("click", abrirMenu);
  $("aula-mapa").addEventListener("click", function () { voltarAoMapa(); });
  $("girar-e").addEventListener("click", function () { MAPA.girar(30); });
  $("girar-d").addEventListener("click", function () { MAPA.girar(-30); });
  $("centralizar").addEventListener("click", function () { MAPA.geral(); });
  $("ver-lista").addEventListener("click", function () { MAPA.lista(); });
  temMais.addEventListener("click", function () { var s = SECS[atual]; s.scrollBy({ top: s.clientHeight * 0.7, behavior: EP.reduzido ? "auto" : "smooth" }); });
  window.addEventListener("resize", function () {
    if (!aulaAberta) return;
    checaMais();
    var sec = SECS[atual];
    if (sec && sec.querySelector("[data-escada]")) sobeEscada(atual);
    var cv = sec && sec.querySelector("[data-cv]");
    if (cv) cvFicha(cv);
  });
  document.addEventListener("keydown", function (e) {
    if (e.defaultPrevented || !aulaAberta || EP.janelaAberta() || e.altKey || e.ctrlKey || e.metaKey) return;
    var tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return;
    if (e.key === "ArrowRight" || e.key === "PageDown") { e.preventDefault(); proximoSlide(); }
    else if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); voltarSlide(); }
    else if (e.key === " " && tag !== "button" && tag !== "a" && tag !== "summary") { e.preventDefault(); proximoSlide(); }
    else if (e.key === "Home") { e.preventDefault(); ir(0, -1); }
    else if (e.key === "End") { e.preventDefault(); ir(SL.length - 1, 1); }
    else if (e.key === "Escape") { e.preventDefault(); voltarAoMapa(); }
  });
  var x0 = null, y0 = null;
  palco.addEventListener("touchstart", function (e) { if (e.touches.length === 1) { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; } }, { passive: true });
  palco.addEventListener("touchend", function (e) {
    if (x0 === null) return;
    var dx = e.changedTouches[0].clientX - x0, dy = e.changedTouches[0].clientY - y0;
    x0 = null;
    if (Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy) * 1.6) { if (dx < 0) proximoSlide(); else voltarSlide(); }
  }, { passive: true });
  // "Ouvir" lê o slide atual, a janela aberta ou o mapa
  EP.alvoLeitura = function () {
    if (EP.janelaAberta()) return document.querySelector(".janela");
    if (aulaAberta && SECS[atual]) return SECS[atual].querySelector(".miolo");
    return document.querySelector(".mapa-ui");
  };

  // ---------------------------------------------------------------- começar
  carregar().then(function () {
    var I = info();
    if (MAPA) MAPA.montar($("mapa-tela"), I, function (n) { abrirParte(n); });
    atualizaMapa();
    var m = /^#parte-(\d+)(?:-(\d+))?$/.exec(location.hash);
    if (m && PARTES[+m[1]]) abrirParte(+m[1], m[2] ? +m[2] - 1 : 0, true);
  });
})();
