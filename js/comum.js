/* ====== Entenda Política: funções comuns a todas as páginas ======
   window.EP: idioma (pt/en), acessibilidade, textos, números, datas, carregar JSON, janela (com foco preso),
   fontes, ouvir em voz alta, Libras (VLibras), animação ao rolar, avatares e cartões de pessoa.

   IDIOMA: o português fica no HTML; o inglês fica ao lado, em atributos:
     data-en="texto"  data-en-html="texto com <b>"  data-en-title  data-en-placeholder  data-en-aria-label  data-en-content
   No JavaScript: EP.tr("texto em português", "text in English"). */
(function () {
  "use strict";
  var EP = (window.EP = window.EP || {});
  var raizDoc = document.documentElement;
  // site-d-r13: a página 404 é servida em qualquer endereço e usa caminhos que começam com "/": a casca (menu, busca, gaveta) também
  EP.RAIZ = (function () { var s = document.currentScript && document.currentScript.getAttribute("src"); return s && s.charAt(0) === "/" ? "/" : ""; })();

  // ---------------------------------------------------------------- preferências guardadas
  var A11Y = {};
  try { A11Y = JSON.parse(localStorage.getItem("ep-a11y") || "{}") || {}; } catch (e) {}
  function salvaA11y() { try { localStorage.setItem("ep-a11y", JSON.stringify(A11Y)); } catch (e) {} }

  // ---------------------------------------------------------------- idioma
  var q = null, salvo = null;
  try { q = (/[?&]lang=(en|pt)\b/.exec(location.search) || [])[1] || null; } catch (e) {}
  try { salvo = localStorage.getItem("ep-lang"); } catch (e) {}
  if (q) try { localStorage.setItem("ep-lang", q); } catch (e) {}
  EP.lang = q || (salvo === "en" ? "en" : "pt");
  EP.en = EP.lang === "en";
  EP.locale = EP.en ? "en-US" : "pt-BR";
  raizDoc.lang = EP.en ? "en" : "pt-BR";
  EP.tr = function (pt, en) { return EP.en && en != null ? en : pt; };
  // troca os textos marcados com data-en-* (só quando a página está em inglês)
  EP.aplicaIdioma = function (raiz) {
    if (!EP.en) return;
    raiz = raiz || document;
    [].forEach.call(raiz.querySelectorAll("[data-en]"), function (el) { el.textContent = el.getAttribute("data-en"); });
    [].forEach.call(raiz.querySelectorAll("[data-en-html]"), function (el) { el.innerHTML = el.getAttribute("data-en-html"); });
    ["title", "placeholder", "aria-label", "content", "alt"].forEach(function (at) {
      [].forEach.call(raiz.querySelectorAll("[data-en-" + at + "]"), function (el) { el.setAttribute(at, el.getAttribute("data-en-" + at)); });
    });
    var t = document.querySelector("title[data-en]");
    if (t) document.title = t.getAttribute("data-en");
  };
  // mesmo endereço, no outro idioma
  EP.urlIdioma = function (lang) {
    var u = new URL(location.href);
    u.searchParams.set("lang", lang);
    return u.pathname.split("/").pop() + u.search + u.hash;
  };
  EP.trocaIdioma = function (lang) {
    try { localStorage.setItem("ep-lang", lang); } catch (e) {}
    location.href = EP.urlIdioma(lang);
  };

  // ---------------------------------------------------------------- acessibilidade
  var mqMovimento = window.matchMedia ? matchMedia("(prefers-reduced-motion: reduce)") : null;
  EP.reduzido = !!(A11Y.movimento || (mqMovimento && mqMovimento.matches));
  var ESCALAS = [1, 1.15, 1.3, 1.5];
  function aplicaA11y() {
    raizDoc.classList.toggle("alto-contraste", !!A11Y.contraste);
    raizDoc.classList.toggle("sem-movimento", !!A11Y.movimento);
    raizDoc.classList.toggle("espacado", !!A11Y.espaco);
    raizDoc.style.setProperty("--escala", A11Y.escala || 1);
    EP.reduzido = !!(A11Y.movimento || (mqMovimento && mqMovimento.matches));
    // o menu "Leitura" do topo mostra o que está ligado (tamanho da letra e os interruptores)
    [].forEach.call(document.querySelectorAll("[data-escala]"), function (b) { b.setAttribute("aria-pressed", String(+b.getAttribute("data-escala") === (A11Y.escala || 1))); });
    [].forEach.call(document.querySelectorAll("[data-a11y]"), function (b) {
      var on = !!A11Y[b.getAttribute("data-a11y")];
      if (b.type === "checkbox") b.checked = on; else b.setAttribute("aria-checked", String(on));
    });
  }
  EP.ESCALAS = ESCALAS;
  EP.a11y = function (chave, valor) {
    if (valor === undefined) return A11Y[chave];
    A11Y[chave] = valor;
    salvaA11y();
    aplicaA11y();
    try { window.dispatchEvent(new CustomEvent("ep-a11y", { detail: { chave: chave, valor: valor } })); } catch (e) {}
  };
  EP.trocaLetra = function () {
    var i = ESCALAS.indexOf(A11Y.escala || 1);
    EP.a11y("escala", ESCALAS[(i + 1) % ESCALAS.length]);
  };
  aplicaA11y();
  if (mqMovimento && mqMovimento.addEventListener) mqMovimento.addEventListener("change", aplicaA11y);

  // ---------------------------------------------------------------- rolagem suave (site-d-r14, pedido do Lucas)
  // EP.rolaJanela(top[, fim]): leva a página até "top" deslizando (~260 ms, desacelerando no fim). Longe demais (mais de uma tela
  // e meia), salta até perto e desliza só o último trecho: a página nunca "voa". Com "menos movimento" (a opção do site ou a do
  // sistema), vai na hora. Para se a pessoa rolar, tocar ou usar o teclado. A rolagem é feita aqui (e não com o "smooth" do
  // navegador) para durar sempre o mesmo e terminar no lugar certo mesmo se a página mudar de altura no caminho.
  var rolagem = null;
  function paraRolagem() { if (rolagem) { cancelAnimationFrame(rolagem.id); rolagem = null; } }
  ["wheel", "touchstart", "keydown", "mousedown"].forEach(function (t) { window.addEventListener(t, paraRolagem, { passive: true, capture: true }); });
  EP.rolando = function () { return !!rolagem; };
  EP.rolaJanela = function (top, fim) {
    paraRolagem();
    var raiz = document.documentElement, max = Math.max(0, raiz.scrollHeight - innerHeight);
    top = Math.max(0, Math.min(max, Math.round(top)));
    var y0 = window.scrollY, d = top - y0;
    if (EP.reduzido || Math.abs(d) < 2) {
      window.scrollTo({ top: top, behavior: "instant" });
      if (fim) fim();
      return;
    }
    var longe = innerHeight * 1.5;
    if (Math.abs(d) > longe) { y0 = top - (d > 0 ? 1 : -1) * innerHeight * 0.6; window.scrollTo({ top: y0, behavior: "instant" }); d = top - y0; }
    var t0 = performance.now(), dur = 260, r = { id: 0 };
    rolagem = r;
    function passo(t) {
      if (rolagem !== r) return;
      var k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      window.scrollTo({ top: y0 + d * e, behavior: "instant" });
      if (k < 1) r.id = requestAnimationFrame(passo);
      else { rolagem = null; if (fim) fim(); }
    }
    r.id = requestAnimationFrame(passo);
  };
  // EP.rolaAte(el[, bloco]): o mesmo, até um elemento, descontando o que fica preso no topo (cabeçalho, barra das abas e a faixa)
  EP.rolaAte = function (el, bloco, fim) {
    if (!el || !el.getClientRects().length) return;
    var r = el.getBoundingClientRect(), fixo = EP.topoFixo ? EP.topoFixo() : ((document.querySelector("header.topo") || { offsetHeight: 0 }).offsetHeight);
    var y = bloco === "center" ? r.top + window.scrollY - (innerHeight + fixo - r.height) / 2 : r.top + window.scrollY - fixo - 12;
    EP.rolaJanela(y, fim);
  };
  // EP.focaSuave(el): põe o foco sem o salto do navegador; se o elemento estiver fora da tela, a página desliza até ele
  EP.focaSuave = function (el) {
    if (!el) return;
    try { el.focus({ preventScroll: true }); } catch (e) { el.focus(); }
    var r = el.getBoundingClientRect(), fixo = EP.topoFixo ? EP.topoFixo() : 60;
    if (r.top < fixo || r.bottom > innerHeight) EP.rolaAte(el, "center");
  };

  // ---------------------------------------------------------------- texto
  EP.esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  // **negrito** -> <b>negrito</b>; {{termo}} -> termo em português no meio do texto em inglês, marcado com lang="pt-BR"
  // para o leitor de tela pronunciar em português (o resto é escapado)
  EP.md = function (s) {
    return EP.esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\{\{(.+?)\}\}/g, '<span lang="pt-BR">$1</span>');
  };
  EP.norm = function (s) {
    return String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
  };
  // Quantos dias faz desde uma data "AAAA-MM-DD" (meio-dia, para não errar por causa do fuso); null se a data não for válida
  EP.diasDesde = function (iso) { var t = Date.parse(String(iso || "").slice(0, 10) + "T12:00:00"); return isNaN(t) ? null : Math.floor((Date.now() - t) / 864e5); };
  EP.gen = function (genero, masc, fem) { return genero === "F" ? fem : masc; };
  EP.plural = function (n, um, varios) { return EP.num(n) + " " + (n === 1 ? um : varios); };
  // marca um texto oficial em português dentro da página em inglês (o leitor de tela troca a pronúncia)
  EP.pt = function (html) { return EP.en ? '<span lang="pt-BR">' + html + "</span>" : html; };

  // ---------------------------------------------------------------- números e datas
  EP.num = function (v, dec) {
    if (v == null || isNaN(v)) return "—";
    return Number(v).toLocaleString(EP.locale, { minimumFractionDigits: dec || 0, maximumFractionDigits: dec || 0 });
  };
  EP.dinheiro = function (v) {
    if (v == null || isNaN(v)) return "—";
    return Number(v).toLocaleString(EP.locale, { style: "currency", currency: "BRL" });
  };
  // R$ 1,2 milhão / R$ 350 mil  (en: R$1.2 million / R$350 thousand)
  EP.dinheiroCurto = function (v) {
    if (v == null || isNaN(v)) return "—";
    var a = Math.abs(v), rs = EP.en ? "R$" : "R$ ";
    if (a >= 1e9) return rs + EP.num(v / 1e9, 1) + EP.tr(a < 2e9 ? " bilhão" : " bilhões", " billion");
    if (a >= 1e6) return rs + EP.num(v / 1e6, 1) + EP.tr(a < 2e6 ? " milhão" : " milhões", " million");
    if (a >= 1e4) return rs + EP.num(Math.round(v / 1e3)) + EP.tr(" mil", " thousand");
    return EP.dinheiro(v);
  };
  var MESES = { pt: ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"],
    en: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"] };
  EP.data = function (iso) {
    if (!iso) return "";
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
    if (!m) return String(iso);
    // inglês no estilo americano, igual ao das aulas: "Oct 27, 1945" / "October 27, 1945"
    return EP.en ? MESES.en[+m[2] - 1].slice(0, 3) + " " + (+m[3]) + ", " + m[1] : m[3] + "/" + m[2] + "/" + m[1];
  };
  EP.dataLonga = function (iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
    if (!m) return iso || "";
    if (EP.en) return MESES.en[+m[2] - 1] + " " + (+m[3]) + ", " + m[1];
    return (+m[3] === 1 ? "1º" : +m[3]) + " de " + MESES.pt[+m[2] - 1] + " de " + m[1];
  };
  EP.idade = function (iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
    if (!m) return null;
    var h = new Date(), i = h.getFullYear() - +m[1];
    if (h.getMonth() + 1 < +m[2] || (h.getMonth() + 1 === +m[2] && h.getDate() < +m[3])) i--;
    return i;
  };

  // ---------------------------------------------------------------- dados
  var cacheJson = {};
  EP.json = function (url) {
    if (!cacheJson[url]) {
      cacheJson[url] = fetch(url, { cache: "no-cache" }).then(function (r) {
        if (!r.ok) throw new Error(r.status + " " + url);
        return r.json();
      });
      cacheJson[url].catch(function () { delete cacheJson[url]; });
    }
    return cacheJson[url];
  };
  // dados/manual/ministros.json é pesquisado à mão para um mandato de presidente ("mandatoInicio"). Se um mandato novo
  // já começou e a lista ainda não foi refeita, o site avisa. Devolve o texto do aviso (no idioma da página) ou null.
  EP.avisoMinistros = function (d) {
    return EP.json("dados/executivo.json").then(function (ex) {
      var ini = ex && ex.presidente && ex.presidente.mandato && ex.presidente.mandato.inicio;
      if (!ini || !d || !d.mandatoInicio || d.mandatoInicio >= ini) return null;
      return EP.tr("Um novo mandato de presidente começou em " + EP.dataLonga(ini) + ". Esta lista de ministros é do mandato anterior e está sendo atualizada: alguns ministros podem ter mudado.",
        "A new presidential term began on " + EP.dataLonga(ini) + ". This list of ministers is from the previous term and is being updated: some ministers may have changed.");
    }).catch(function () { return null; });
  };
  EP.param = function (nome) {
    try { return new URLSearchParams(location.search).get(nome); } catch (e) { return null; }
  };
  // campo traduzido de um objeto de dados: usa "campo_en" no inglês, se existir
  EP.campo = function (obj, campo) {
    if (!obj) return null;
    return EP.en && obj[campo + "_en"] ? obj[campo + "_en"] : obj[campo];
  };

  // ---------------------------------------------------------------- estados
  EP.UFS = {
    AC: "Acre", AL: "Alagoas", AP: "Amapá", AM: "Amazonas", BA: "Bahia", CE: "Ceará", DF: "Distrito Federal", ES: "Espírito Santo",
    GO: "Goiás", MA: "Maranhão", MT: "Mato Grosso", MS: "Mato Grosso do Sul", MG: "Minas Gerais", PA: "Pará", PB: "Paraíba", PR: "Paraná",
    PE: "Pernambuco", PI: "Piauí", RJ: "Rio de Janeiro", RN: "Rio Grande do Norte", RS: "Rio Grande do Sul", RO: "Rondônia", RR: "Roraima",
    SC: "Santa Catarina", SP: "São Paulo", SE: "Sergipe", TO: "Tocantins"
  };
  if (EP.en) EP.UFS.DF = "Federal District";
  EP.UF_IBGE = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO", 21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL", 28: "SE", 29: "BA",
    31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR", 42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF"
  };
  // "no Acre", "na Bahia", "em Alagoas" (en: "in Acre")
  EP.noEstado = function (uf) {
    var nome = EP.UFS[uf] || uf;
    if (EP.en) return (uf === "DF" ? "in the " : "in ") + nome;
    var em = { AL: 1, GO: 1, MG: 1, MT: 1, MS: 1, PE: 1, RO: 1, RR: 1, SC: 1, SP: 1, SE: 1 };
    if (em[uf]) return "em " + nome;
    return ({ BA: 1, PB: 1 }[uf] ? "na " : "no ") + nome;
  };
  // "do Acre", "da Bahia", "de Alagoas" (en: "of Acre")
  EP.doEstado = function (uf) {
    if (EP.en) return (uf === "DF" ? "of the " : "of ") + (EP.UFS[uf] || uf);
    return EP.noEstado(uf).replace(/^(no|na|em) /, function (m) { return { "no ": "do ", "na ": "da ", "em ": "de " }[m]; });
  };

  // ---------------------------------------------------------------- cargos e temas em inglês
  var CARGOS_EN = {
    "presidente": "President", "presidenta": "President", "vice-presidente": "Vice President",
    "senador": "Senator", "senadora": "Senator", "deputado federal": "Federal Deputy", "deputada federal": "Federal Deputy",
    "governador": "Governor", "governadora": "Governor", "vice-governador": "Vice Governor", "vice-governadora": "Vice Governor",
    "deputado estadual": "State Deputy", "deputada estadual": "State Deputy", "deputado distrital": "District Deputy", "deputada distrital": "District Deputy",
    "prefeito": "Mayor", "prefeita": "Mayor", "vice-prefeito": "Vice Mayor", "vice-prefeita": "Vice Mayor",
    "vereador": "City Councilor", "vereadora": "City Councilor", "ministro": "Minister", "ministra": "Minister",
    "ministro do supremo tribunal federal": "Justice of the Federal Supreme Court", "ministra do supremo tribunal federal": "Justice of the Federal Supreme Court"
  };
  EP.cargo = function (pt) {
    if (!EP.en || !pt) return pt;
    var p = String(pt).split(" · ");
    var c = CARGOS_EN[EP.norm(p[0]).replace(/\s+/g, " ")] || CARGOS_EN[EP.norm(p[0]).replace(/[^a-z -]/g, "")];
    return (c || p[0]) + (p[1] ? " · " + p.slice(1).join(" · ") : "");
  };
  var TEMAS_EN = {
    "administracao publica": "Public administration", "agricultura, pecuaria, pesca e extrativismo": "Farming and fishing", "arte, cultura e religiao": "Arts, culture and religion",
    "cidades e desenvolvimento urbano": "Cities", "ciencia, tecnologia e inovacao": "Science and technology", "ciencias exatas e da terra": "Natural sciences",
    "ciencias sociais e humanas": "Social sciences", "comunicacoes": "Communications", "defesa e seguranca": "Defense and security",
    "direito civil e processual civil": "Civil law", "direito constitucional": "Constitutional law", "direito e defesa do consumidor": "Consumer rights",
    "direito e justica": "Law and justice", "direito penal e processual penal": "Criminal law", "direitos humanos e minorias": "Human rights and minorities",
    "economia": "Economy", "educacao": "Education", "energia, recursos hidricos e minerais": "Energy, water and minerals", "esporte e lazer": "Sports and leisure",
    "estrutura fundiaria": "Land ownership", "financas publicas e orcamento": "Public finances and budget", "homenagens e datas comemorativas": "Tributes and commemorative dates",
    "industria, comercio e servicos": "Industry, trade and services", "meio ambiente e desenvolvimento sustentavel": "Environment", "politica, partidos e eleicoes": "Politics, parties and elections",
    "previdencia e assistencia social": "Pensions and social assistance", "processo legislativo e atuacao parlamentar": "How Congress works",
    "relacoes internacionais e comercio exterior": "International relations and trade", "saude": "Health", "seguranca publica": "Public safety",
    "trabalho e emprego": "Work and jobs", "turismo": "Tourism", "viacao, transporte e mobilidade": "Transportation",
    // temas do Senado (classificação própria do Senado)
    "tributos": "Taxes", "financas publicas": "Public finances", "agentes publicos": "Public servants",
    "direito penal e penitenciario": "Criminal and prison law", "direito eleitoral": "Electoral law", "direitos e garantias": "Rights and guarantees",
    "organizacao administrativa": "Government organization", "organizacao federativa": "Federal organization (states and cities)", "poder legislativo": "Legislative branch",
    "poder judiciario": "Judicial branch", "processo legislativo": "How laws are made", "processo penal": "Criminal procedure",
    "previdencia social": "Pensions", "assistencia social": "Social assistance", "mulheres": "Women",
    "meio ambiente": "Environment", "fiscalizacao e controle": "Oversight and control", "criancas e adolescentes": "Children and teenagers",
    "desenvolvimento regional": "Regional development", "ciencia, tecnologia e informatica": "Science, technology and computing", "orcamento anual": "Annual budget",
    "viacao e transportes": "Transportation", "minas e energia": "Mining and energy", "orcamento publico": "Public budget",
    "sistema financeiro nacional": "Financial system", "direito do consumidor": "Consumer rights", "desporto e lazer": "Sports and leisure",
    "pessoas com deficiencia": "People with disabilities", "dominio e bens publicos": "Public property", "direito civil": "Civil law",
    "populacao indigena": "Indigenous peoples", "funcoes essenciais a justica": "Justice institutions (prosecutors, public defenders and lawyers)", "agropecuaria e abastecimento": "Farming and food supply",
    "processo civil": "Civil procedure", "homenagem": "Tributes", "servicos publicos": "Public services",
    "fiscalizacao e controle da atividade economica": "Business oversight", "protecao social": "Social protection", "calamidade publica e emergencia social": "Disasters and emergencies",
    "licitacao e contratos": "Public procurement and contracts", "direito de transito": "Traffic law", "data comemorativa": "Commemorative dates",
    "cultura": "Culture", "desenvolvimento sustentavel": "Sustainable development", "idosos": "Older people",
    "relacoes internacionais": "International relations", "espacos especialmente protegidos": "Protected areas", "economia e desenvolvimento": "Economy and development",
    "linha de credito": "Credit lines", "transparencia e governanca publicas": "Transparency and public governance", "desenvolvimento social e combate a fome": "Social development and fighting hunger",
    "defesa nacional e forcas armadas": "National defense and armed forces", "politica fundiaria e reforma agraria": "Land policy and agrarian reform", "direito empresarial e economico": "Business and economic law",
    "terceiro setor, parcerias publico-privadas e desestatizacao": "Nonprofits, public-private partnerships and privatization", "desenvolvimento urbano": "Urban development", "protecao aos animais": "Animal protection",
    "direito notarial e registral": "Notary and registry law", "crimes e infracoes ambientais": "Environmental crimes", "vegetacao nativa": "Native vegetation",
    "politica social": "Social policy", "residuos solidos": "Solid waste", "mudancas climaticas": "Climate change",
    "poluicao": "Pollution", "habitacao": "Housing", "recursos hidricos": "Water resources",
    "direito maritimo, aeronautico e espacial": "Maritime, air and space law", "processo do trabalho": "Labor procedure", "processo administrativo": "Administrative procedure",
    "licenciamento ambiental": "Environmental licensing", "infraestrutura": "Infrastructure", "direito dos estrangeiros": "Rights of foreigners",
    "intervencao na propriedade privada": "Government intervention in private property", "honorifico": "Honors", "diretrizes orcamentarias": "Budget guidelines",
    "defesa do estado e das instituicoes democraticas": "Defense of the State and of democratic institutions", "soberania, defesa nacional e ordem publica": "Sovereignty, national defense and public order", "processo": "Legal procedure",
    "patrimonio genetico": "Genetic heritage", "juridico": "Legal matters"
  };
  EP.tema = function (pt) { return EP.en ? TEMAS_EN[EP.norm(pt)] || pt : pt; };

  // ---------------------------------------------------------------- eleição de 2026 e cartões de pessoa
  EP.SIT2026 = {
    eleito: { ic: "🗳️", cls: "neutro" }, reeleito: { ic: "🔁", cls: "neutro" }, "segundo-turno": { ic: "⏳", cls: "amarelo" },
    "nao-eleito": { ic: "▫️", cls: "neutro" }, suplente: { ic: "🪑", cls: "neutro" }, candidato: { ic: "🗳️", cls: "amarelo" }, "nao-concorreu": { ic: "▫️", cls: "neutro" }
  };
  function txt2026(sit, genero, curto) {
    var a = genero === "F" ? "a" : "o";
    // o 2º turno de 2026 foi em 25/10: depois dessa data, o texto fala no passado
    var passou = new Date() >= new Date("2026-10-26T00:00:00-03:00");
    if (EP.en) return { eleito: "Elected in 2026", reeleito: "Re-elected in 2026", "segundo-turno": curto ? "Runoff in 2026" : passou ? "Ran in the runoff on October 25, 2026" : "In the runoff on October 25, 2026",
      "nao-eleito": "Not elected in 2026", suplente: "Alternate in 2026", candidato: "Candidate in 2026", "nao-concorreu": "Did not run in 2026" }[sit] || "2026";
    return { eleito: "Eleit" + a + " em 2026", reeleito: "Reeleit" + a + " em 2026", "segundo-turno": curto ? "2º turno em 2026" : (passou ? "Disputou" : "Disputa") + " o 2º turno em 25/10/2026",
      "nao-eleito": "Não eleit" + a + " em 2026", suplente: curto ? "Suplente em 2026" : "Ficou como suplente em 2026", candidato: "Candidat" + a + " em 2026",
      "nao-concorreu": "Não concorreu em 2026" }[sit] || "2026";
  }
  EP.texto2026 = function (e, genero) {
    if (!e || !e.situacao) return "";
    if (EP.en) return e.txt_en || txt2026(e.situacao, genero, false);
    return e.txt || txt2026(e.situacao, genero, false);
  };
  // selo para os cartões (mesma regra para todo mundo; "não concorreu" não aparece no cartão)
  EP.chip2026 = function (e, genero, longo) {
    if (!e) return "";
    var sit = typeof e === "string" ? e : e.situacao;
    if (!sit || (!longo && sit === "nao-concorreu")) return "";
    var c = EP.SIT2026[sit] || { ic: "🗳️", cls: "neutro" };
    var txt = longo && typeof e === "object" ? EP.texto2026(e, genero) : txt2026(sit, genero, true);
    return '<span class="chip ' + c.cls + '"><span aria-hidden="true">' + c.ic + " </span>" + EP.esc(txt) + "</span>";
  };
  EP.alfabetica = function (lista, campo) {
    campo = campo || "nome";
    return lista.slice().sort(function (a, b) { return EP.norm(a[campo]).localeCompare(EP.norm(b[campo])); });
  };

  // ---------------------------------------------------------------- situação das propostas
  EP.STATUS = {
    lei: { ic: "📜", txt: EP.tr("Virou lei", "Became law"), curto: EP.tr("Viraram lei", "Became law") },
    aprovada: { ic: "☑️", txt: EP.tr("Aprovada numa etapa (ainda não é lei)", "Approved at one stage (not law yet)"), curto: EP.tr("Aprovadas numa etapa", "Approved at one stage") },
    andando: { ic: "🚶", txt: EP.tr("Em discussão", "Under discussion"), curto: EP.tr("Em discussão", "Under discussion") },
    junta: { ic: "🔗", txt: EP.tr("Junto com outra", "Joined to a similar bill"), curto: EP.tr("Andando junto com outra parecida", "Joined to a similar bill") },
    arquivada: { ic: "🗄️", txt: EP.tr("Arquivada", "Shelved"), curto: EP.tr("Arquivadas", "Shelved") },
    rejeitada: { ic: "✖️", txt: EP.tr("Rejeitada", "Rejected"), curto: EP.tr("Rejeitadas ou vetadas", "Rejected or vetoed") },
    parada: { ic: "⏹️", txt: EP.tr("Parou", "Stopped"), curto: EP.tr("Pararam sem ser rejeitadas", "Stopped without a rejection") },
    retirada: { ic: "↩️", txt: EP.tr("Autor desistiu", "Withdrawn"), curto: EP.tr("O autor desistiu", "Withdrawn by the author") },
    outra: { ic: "❔", txt: EP.tr("Outra situação", "Other status"), curto: EP.tr("Outra situação", "Other status") }
  };
  EP.carimbo = function (status, txt) {
    var s = EP.STATUS[status] || EP.STATUS.outra;
    return '<span class="carimbo s-' + EP.esc(status || "outra") + '"><span aria-hidden="true">' + s.ic + " </span>" + EP.esc(txt || s.txt) + "</span>";
  };

  // ---------------------------------------------------------------- avatar e cartão de pessoa
  EP.av = function (foto, nome, classe, eager) {
    var c = "av" + (classe ? " " + classe : "");
    if (!foto) {
      var ini = String(nome || "?").replace(/^(Dr\.|Dra\.|Pr\.|Pra\.|Del\.|Cel\.|Sgt\.|Cap\.)\s+/i, "").trim().charAt(0).toUpperCase();
      return '<span class="' + c + ' av-letra" aria-hidden="true">' + EP.esc(ini) + "</span>";
    }
    return '<img class="' + c + '" src="' + EP.esc(foto) + '" alt="" ' + (eager ? "" : 'loading="lazy" ') +
      'decoding="async" referrerpolicy="no-referrer" onerror="this.onerror=null;this.outerHTML=EP.av(null,' +
      EP.esc(JSON.stringify(String(nome || "?"))) + "," + EP.esc(JSON.stringify(classe || "")) + ')">';
  };
  EP.cartaoPessoa = function (p, extra) {
    var partido = /^sem partido$/i.test(p.partido || "") ? EP.tr("Sem partido", "No party") : p.partido;
    var linha2 = [partido, p.uf].filter(Boolean).join(" · ");
    // nomes são em português: no inglês, o leitor de tela pronuncia melhor com lang="pt-BR"
    return '<a class="pessoa-card" href="pessoa.html?id=' + encodeURIComponent(p.id) + '">' + EP.av(p.foto, p.nome) +
      "<b>" + EP.pt(EP.esc(p.nome)) + "</b>" + (extra ? "<small>" + EP.esc(extra) + "</small>" : "") + (linha2 ? "<small>" + EP.esc(linha2) + "</small>" : "") +
      EP.chip2026(p.eleicao2026, p.genero) + "</a>";
  };

  // ---------------------------------------------------------------- janela (Basecoat "dialog": <dialog> com showModal)
  // ui-r9: a janela é um <dialog class="dialog"> do Basecoat, aberto com showModal(): fica por cima de tudo (a "top layer" do
  // navegador, acima da barra do topo, das abas e dos enfeites), o navegador prende o foco dentro dela e o resto da página
  // fica inerte. Esc, o ✕ Fechar e clicar fora fecham; o foco volta para quem abriu. A mesma API de antes.
  var dlg = null, focoAntes = null;
  var FOCAVEIS = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';
  function montaJanela() {
    if (dlg) return;
    dlg = document.createElement("dialog");
    dlg.className = "dialog janela-dialog";
    dlg.setAttribute("role", "dialog");
    dlg.setAttribute("aria-modal", "true");
    dlg.setAttribute("aria-labelledby", "janela-titulo");
    dlg.innerHTML = '<div class="janela"><div class="janela-cab"><h2 id="janela-titulo"></h2></div><section class="janela-corpo"></section>' +
      '<button class="fechar btn" data-variant="outline" type="button" data-fechar><span aria-hidden="true">✕ </span>' + EP.tr("Fechar", "Close") + "</button></div>";
    document.body.appendChild(dlg);
    dlg.addEventListener("click", function (e) {
      // clique no fundo (fora da caixa) ou no ✕
      if (e.target === dlg || (e.target.closest && e.target.closest("[data-fechar]"))) EP.fechar();
    });
    dlg.addEventListener("cancel", function (e) { e.preventDefault(); EP.fechar(); });
    // reserva, para navegadores sem <dialog> modal: o Tab não sai da janela
    dlg.addEventListener("keydown", function (e) {
      if (e.key !== "Tab" || dlg.matches(":modal")) return;
      var f = [].filter.call(dlg.querySelectorAll(FOCAVEIS), function (x) { return x.getClientRects().length; });
      if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    });
  }
  EP.abrir = function (titulo, html) {
    montaJanela();
    EP.calar();
    if (EP.fechaMenus) EP.fechaMenus(false);
    if (!dlg.open) focoAntes = document.activeElement;
    dlg.querySelector("#janela-titulo").innerHTML = titulo;
    dlg.querySelector(".janela-corpo").innerHTML = html;
    if (!dlg.open) {
      try { dlg.showModal(); } catch (e) { dlg.setAttribute("open", ""); }
    }
    dlg.querySelector(".janela").scrollTop = 0;
    dlg.querySelector(".fechar").focus();
  };
  EP.fechar = function () {
    if (!dlg || !dlg.open) return;
    EP.calar();
    try { dlg.close(); } catch (e) { dlg.removeAttribute("open"); }
    if (focoAntes && focoAntes.focus) focoAntes.focus();
  };
  EP.janelaAberta = function () { return !!(dlg && dlg.open); };
  EP.janelaEl = function () { return dlg && dlg.querySelector(".janela"); };
  document.addEventListener("keydown", function (e) {
    // Esc fecha só a janela (preventDefault avisa o resto da página para não fazer mais nada com esse Esc)
    if (e.key === "Escape" && EP.janelaAberta()) { e.preventDefault(); EP.fechar(); }
  });

  // ---------------------------------------------------------------- fontes
  function hostDe(url) { try { return new URL(url).hostname.replace(/^www\d*\./, ""); } catch (e) { return ""; } }
  EP.fontesHtml = function (lista) {
    lista = (lista || []).filter(Boolean);
    if (!lista.length) return '<p class="muted">' + EP.tr("Sem fonte registrada.", "No source recorded.") + "</p>";
    return (EP.en ? '<p class="muted">Most official sources are in Portuguese.</p>' : "") + '<ul class="fontes-lista">' + lista.map(function (f) {
      // no inglês, o título fica marcado como português, a não ser que já tenha sido traduzido (f.lang = "en")
      var tit = EP.esc(f.titulo || f.url || "");
      tit = f.lang === "en" ? tit : EP.pt(tit);
      return "<li><b>" + EP.pt(EP.esc(f.veiculo || hostDe(f.url))) + "</b>" +
        (f.url ? '<a href="' + EP.esc(f.url) + '" target="_blank" rel="noopener"' + (EP.en ? ' hreflang="pt-BR"' : "") + ">" + tit +
          ' <span aria-hidden="true">↗</span><span class="sr">' + EP.tr("(abre em outra aba)", "(opens in a new tab)") + "</span></a>" : tit) +
        (f.data ? "<br><small>" + (/^\d{4}-\d{2}-\d{2}$/.test(f.data) ? EP.tr("Data: ", "Date: ") + EP.data(f.data) : EP.esc(f.data)) + "</small>" : "") + "</li>";
    }).join("") + "</ul>";
  };
  var FONTES = [];
  EP.botaoFontes = function (lista, rotulo) {
    lista = Array.isArray(lista) ? lista : lista ? [lista] : [];
    if (!lista.length) return "";
    FONTES.push(lista);
    return '<button type="button" class="fontes-btn nao-ler" data-fontes="' + (FONTES.length - 1) + '"><span aria-hidden="true">📚 </span>' +
      EP.esc(rotulo || EP.tr("De onde veio isso?", "Where does this come from?")) + "</button>";
  };
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-fontes]");
    if (!b) return;
    var l = FONTES[+b.getAttribute("data-fontes")];
    if (!l) return;
    EP.abrir("📚 " + EP.tr("De onde veio isso?", "Where does this come from?"),
      "<p>" + EP.tr("Estas informações vieram destes lugares. Toque para abrir a página original.", "This information came from these places. Tap to open the original page.") + "</p>" + EP.fontesHtml(l));
  });

  // ---------------------------------------------------------------- animação ao rolar
  EP.revelar = function (raiz) {
    var els = (raiz || document).querySelectorAll(".rev:not(.visivel), .r3d:not(.visivel), .num3d:not(.visivel)");
    if (EP.reduzido || !("IntersectionObserver" in window)) {
      [].forEach.call(els, function (el) { el.classList.add("visivel"); });
      return;
    }
    var io = new IntersectionObserver(function (ents) {
      ents.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("visivel"); io.unobserve(en.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    [].forEach.call(els, function (el) { io.observe(el); });
  };
  EP.paralaxe = function () {
    if (EP.reduzido) return;
    var formas = document.querySelectorAll(".forma");
    if (!formas.length) return;
    var pend = false;
    function passo() {
      pend = false;
      var p = Math.min(1, window.scrollY / Math.max(1, document.documentElement.scrollHeight - innerHeight));
      [].forEach.call(formas, function (f) { f.style.setProperty("--p", p.toFixed(3)); });
    }
    window.addEventListener("scroll", function () { if (!pend) { pend = true; requestAnimationFrame(passo); } }, { passive: true });
  };

  // ---------------------------------------------------------------- ouvir (voz do aparelho)
  var podeFalar = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
  EP.podeFalar = podeFalar;
  EP.calar = function () {
    if (podeFalar && (speechSynthesis.speaking || speechSynthesis.pending)) speechSynthesis.cancel();
    var b = document.getElementById("btn-ouvir");
    if (b) b.setAttribute("aria-pressed", "false");
  };
  EP.textoParaLer = function (el) {
    if (!el) return "";
    var c = el.cloneNode(true);
    // páginas com abas (js/abas.js): só a aba aberta é lida; nada do que está escondido (hidden) entra
    c.querySelectorAll(".nao-ler,[aria-hidden='true'],svg,script,style,button.fechar,.formas,.sr,[hidden],.menu-painel").forEach(function (n) { n.remove(); });
    c.querySelectorAll("h1,h2,h3,h4,p,li,dt,dd,.ler-pausa").forEach(function (n) { n.appendChild(document.createTextNode(". ")); });
    return c.textContent
      .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}\u{200D}]/gu, "")
      .replace(/[▶◀›↗⟶↺⬆⬇↓▾]/g, "")
      .replace(/\s*\.\s*(\.\s*)+/g, ". ")
      .replace(/\s+/g, " ").trim();
  };
  EP.falar = function (texto) {
    if (!podeFalar || !texto) return;
    EP.calar();
    var u = new SpeechSynthesisUtterance(texto);
    u.lang = EP.en ? "en-US" : "pt-BR";
    u.rate = 0.95;
    var re = EP.en ? /^en[-_]/i : /^pt[-_]BR/i;
    var voz = speechSynthesis.getVoices().filter(function (v) { return re.test(v.lang); })[0];
    if (voz) u.voice = voz;
    var b = document.getElementById("btn-ouvir");
    u.onend = u.onerror = function () { if (b) b.setAttribute("aria-pressed", "false"); };
    speechSynthesis.speak(u);
    if (b) b.setAttribute("aria-pressed", "true");
  };
  EP.alvoLeitura = function () {
    if (EP.janelaAberta()) return EP.janelaEl();
    var g = document.getElementById("gaveta");
    if (g && g.open) return g.querySelector(".gv-caixa");
    return document.querySelector("[data-ler]") || document.querySelector("main");
  };
  EP.ouvir = function () {
    if (podeFalar && (speechSynthesis.speaking || speechSynthesis.pending)) { EP.calar(); return; }
    EP.falar(EP.textoParaLer(EP.alvoLeitura()));
  };
  if (podeFalar) speechSynthesis.getVoices();

  // ---------------------------------------------------------------- Libras (VLibras, do governo federal)
  var librasCarregado = false;
  EP.libras = function () {
    if (librasCarregado) {
      var botao = document.querySelector("[vw-access-button]");
      if (botao) botao.click();
      return;
    }
    librasCarregado = true;
    var d = document.createElement("div");
    d.setAttribute("vw", "");
    d.className = "enabled";
    d.innerHTML = '<div vw-access-button class="active"></div><div vw-plugin-wrapper><div class="vw-plugin-top-wrapper"></div></div>';
    document.body.appendChild(d);
    var s = document.createElement("script");
    s.src = "https://vlibras.gov.br/app/vlibras-plugin.js";
    s.onload = function () {
      try {
        new window.VLibras.Widget("https://vlibras.gov.br/app");
        // o VLibras começa no evento "load" da página; como ele chega depois, avisamos de novo
        window.dispatchEvent(new Event("load"));
        setTimeout(function () { var b = document.querySelector("[vw-access-button]"); if (b) b.click(); }, 1200);
      } catch (e) { librasCarregado = false; }
    };
    s.onerror = function () {
      librasCarregado = false;
      EP.abrir("🤟 Libras", "<p>Não foi possível carregar o tradutor de Libras (VLibras) agora. Tente de novo mais tarde.</p>");
    };
    document.body.appendChild(s);
  };

  // ---------------------------------------------------------------- menu de acessibilidade
  EP.menuA11y = function () {
    var esc = A11Y.escala || 1;
    function liga(chave, ic, titulo, explica) {
      var on = !!A11Y[chave];
      return '<button type="button" class="opcao-a11y" role="switch" aria-checked="' + on + '" data-a11y="' + chave + '"><span class="oa-ic" aria-hidden="true">' + ic + "</span>" +
        "<span><b>" + titulo + "</b><small>" + explica + '</small></span><span class="oa-chave" aria-hidden="true"><i></i></span></button>';
    }
    EP.abrir("♿ " + EP.tr("Acessibilidade", "Accessibility"),
      '<div class="menu-a11y">' +
      '<div class="grupo-a11y"><b>🔠 ' + EP.tr("Tamanho da letra", "Text size") + '</b><div class="tamanhos" role="group" aria-label="' + EP.tr("Tamanho da letra", "Text size") + '">' +
      ESCALAS.map(function (e, i) {
        return '<button type="button" data-escala="' + e + '" aria-pressed="' + (e === esc) + '" style="font-size:' + (0.85 + i * 0.18) + 'rem">A<span class="sr"> ' + EP.tr("tamanho", "size") + " " + (i + 1) + "</span></button>";
      }).join("") + "</div></div>" +
      liga("contraste", "🌓", EP.tr("Alto contraste", "High contrast"), EP.tr("Preto no branco, com bordas fortes.", "Black on white, with strong borders.")) +
      liga("movimento", "🐢", EP.tr("Menos movimento", "Reduce motion"), EP.tr("Desliga as animações e os giros.", "Turns off animations and spinning.")) +
      liga("espaco", "↔️", EP.tr("Mais espaço no texto", "More text spacing"), EP.tr("Mais espaço entre letras, palavras e linhas.", "More space between letters, words and lines.")) +
      (podeFalar ? '<button type="button" class="opcao-a11y" data-a11y-acao="ouvir"><span class="oa-ic" aria-hidden="true">🔊</span><span><b>' + EP.tr("Ouvir esta página", "Listen to this page") + "</b><small>" +
        EP.tr("O aparelho lê o texto em voz alta.", "Your device reads the text out loud.") + "</small></span></button>" : "") +
      (EP.en ? "" : '<button type="button" class="opcao-a11y" data-a11y-acao="libras"><span class="oa-ic" aria-hidden="true">🤟</span><span><b>Libras</b><small>Tradução para a Língua Brasileira de Sinais (VLibras, do governo federal).</small></span></button>') +
      '<button type="button" class="opcao-a11y" data-a11y-acao="idioma" lang="' + (EP.en ? "pt-BR" : "en") + '"><span class="oa-ic" aria-hidden="true">🌐</span><span><b>' +
      (EP.en ? "Ler em português" : "Read in English") + "</b><small>" + (EP.en ? "Versão original do site." : "English version of the site.") + "</small></span></button>" +
      '<details class="atalhos-teclado"><summary>⌨️ ' + EP.tr("Atalhos do teclado", "Keyboard shortcuts") + "</summary><ul>" +
      "<li><kbd>Tab</kbd> " + EP.tr("vai para o próximo botão ou link", "moves to the next button or link") + "</li>" +
      "<li><kbd>Enter</kbd> " + EP.tr("escolhe", "selects") + "</li>" +
      "<li><kbd>Esc</kbd> " + EP.tr("fecha janelas", "closes windows") + "</li>" +
      "<li><kbd>←</kbd> <kbd>→</kbd> " + EP.tr("trocam de página nas apresentações e giram o mapa", "change pages in presentations and turn the map") + "</li></ul></details></div>");
  };
  document.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest("[data-a11y],[data-a11y-acao],[data-escala]");
    if (!t) return;
    if (t.hasAttribute("data-escala")) {
      EP.a11y("escala", +t.getAttribute("data-escala"));
      [].forEach.call(document.querySelectorAll("[data-escala]"), function (b) { b.setAttribute("aria-pressed", String(+b.getAttribute("data-escala") === (A11Y.escala || 1))); });
      return;
    }
    if (t.hasAttribute("data-a11y")) {
      // interruptor do Basecoat (input checkbox com role="switch"): o próprio campo guarda o estado
      var k = t.getAttribute("data-a11y"), v = t.type === "checkbox" ? t.checked : !A11Y[k];
      EP.a11y(k, v);
      if (t.type !== "checkbox") t.setAttribute("aria-checked", String(v));
      return;
    }
    var acao = t.getAttribute("data-a11y-acao");
    if (acao === "ouvir") { EP.fechar(); EP.fechaMenus(false); setTimeout(EP.ouvir, 50); }
    else if (acao === "libras") { EP.fechar(); EP.fechaMenus(false); EP.libras(); }
    else if (acao === "idioma") EP.trocaIdioma(EP.en ? "pt" : "en");
  });

  // ---------------------------------------------------------------- aviso de idioma (primeira visita de fora do Brasil)
  function avisoIdioma() {
    var jaEscolheu = false;
    try { jaEscolheu = !!localStorage.getItem("ep-lang") || !!sessionStorage.getItem("ep-lang-aviso"); } catch (e) {}
    var langs = (navigator.languages || [navigator.language || ""]).join(",").toLowerCase();
    if (jaEscolheu || EP.en || /(^|,)pt/.test(langs)) return;
    var b = document.createElement("div");
    b.className = "aviso-idioma";
    b.setAttribute("role", "region");
    b.setAttribute("aria-label", "Language");
    b.lang = "en";
    b.innerHTML = '<span aria-hidden="true">🌐</span><span>This site is about Brazilian politics and it is also available in English.</span>' +
      '<a class="btn peq" href="' + EP.esc(EP.urlIdioma("en")) + '">Read in English</a><button type="button" class="btn peq bege" lang="pt-BR">Continuar em português</button>';
    document.body.insertBefore(b, document.body.firstChild);
    b.querySelector("button").addEventListener("click", function () {
      try { localStorage.setItem("ep-lang", "pt"); } catch (e) {}
      b.remove();
    });
    try { sessionStorage.setItem("ep-lang-aviso", "1"); } catch (e) {}
  }

  // ---------------------------------------------------------------- barra do topo (ui-r9, componentes do Basecoat)
  // 🔊 Ouvir sempre à vista; 🌐 idioma e ☰ menu do site são "dropdown-menu" do Basecoat (role="menu": setas, Home/End, Enter,
  // Esc, clicar fora fecha); Aa Leitura é um "popover" do Basecoat (um painel com interruptores e botões, que um menu não pode
  // ter: tamanho da letra, alto contraste, menos movimento, mais espaço, ouvir e Libras). O HTML dos botões já está em cada
  // página (não mudam de lugar quando o JavaScript chega); os painéis são montados aqui e ligados com window.basecoat.init.
  // Acessibilidade a mais que o Basecoat: nos menus, a seta leva o foco de verdade ao item (o leitor de tela lê o item; o
  // Basecoat só usa aria-activedescendant no botão, que não vale em botão); no celular estreito (até 360 px), o idioma entra
  // no ☰ menu (a barra cabe numa linha só).
  var CHEVRON = '<svg class="lucide seta-menu" aria-hidden="true" focusable="false" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>';
  EP.ICONES = {
    chevron: CHEVRON,
    x: '<svg class="lucide" aria-hidden="true" focusable="false" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>',
    check: '<svg class="lucide" aria-hidden="true" focusable="false" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>'
  };
  // as partes do site (menu ☰): [endereço, emoji, pt, en, arquivo da página]
  EP.PARTES = [["./", "🏠", "Início", "Home", "index.html"], ["entenda.html", "🗺️", "Entenda a política (o mapa)", "Understand politics (the map)", "entenda.html"],
    ["brasil.html", "🏛️", "A política do Brasil", "Brazil's politics", "brasil.html"], ["estado.html", "📍", "A política do meu estado", "Politics in my state", "estado.html"],
    ["cidade.html", "🏘️", "A política da minha cidade", "Politics in my city", "cidade.html"], ["votacoes.html", "🗳️", "Votações do Congresso", "Votes in Congress", "votacoes.html"],
    ["brasil.html#procurar", "🔎", "Procurar um político", "Search for a politician", ""],
    ["imparcialidade.html", "⚖️", "Como cuidamos da imparcialidade", "How we stay impartial", "imparcialidade.html"],
    ["dados.html", "🗂️", "De onde vêm os dados", "Where the data comes from", "dados.html"]];
  function arquivoAtual() { return (location.pathname.split("/").pop() || "index.html"); }
  var ESTREITO = window.matchMedia ? matchMedia("(max-width: 360px)") : { matches: false };
  var apertado = function () { return ESTREITO.matches; };
  function itemIdioma(l, pre) {
    var atual = l === EP.lang;
    return '<a role="menuitemradio" id="' + pre + "-" + l + '" aria-checked="' + atual + '" class="menu-item" href="' + EP.esc(EP.urlIdioma(l)) + '" data-idioma="' + l + '" lang="' + (l === "en" ? "en" : "pt-BR") +
      '" hreflang="' + (l === "en" ? "en" : "pt-BR") + '"><span class="mi-ic" aria-hidden="true">' + (l === "en" ? "🇺🇸" : "🇧🇷") + "</span><span><b>" + (l === "en" ? "English" : "Português") +
      "</b><small>" + (l === "en" ? "Brazilian politics explained in English" : "Versão original do site") + '</small></span><span class="mi-ok" data-indicator aria-hidden="true">' + EP.ICONES.check + "</span></a>";
  }
  function painelIdioma() {
    return '<div role="menu" id="menu-idioma-lista" aria-labelledby="menu-idioma-btn"><div role="heading" aria-level="2" class="menu-tit">' + EP.tr("Idioma do site", "Site language") + "</div>" +
      itemIdioma("pt", "mi") + itemIdioma("en", "mi") + "</div>";
  }
  function painelSite() {
    var aqui = arquivoAtual();
    if (aqui === "votacao.html") aqui = "votacoes.html";
    if (aqui === "pessoa.html") aqui = "";
    return '<div role="menu" id="menu-site-lista" aria-labelledby="menu-site-btn"><div role="heading" aria-level="2" class="menu-tit">' + EP.tr("Partes do site", "Parts of the site") + "</div>" +
      EP.PARTES.map(function (p, k) {
        var atual = p[4] && p[4] === aqui;
        return '<a role="menuitem" id="ms-' + k + '" class="menu-item" href="' + p[0] + '"' + (atual ? ' aria-current="page"' : "") + '><span class="mi-ic" aria-hidden="true">' + p[1] + "</span><span>" +
          EP.esc(EP.tr(p[2], p[3])) + "</span>" + (atual ? '<span class="mi-ok" aria-hidden="true">●</span>' : "") + "</a>";
      }).join("") +
      // no celular estreito, o idioma entra aqui (a montagem tira ou põe este grupo a cada vez que o menu abre)
      '<div class="grupo-idioma-site" role="group" aria-label="' + EP.tr("Idioma do site", "Site language") + '" hidden><hr role="separator">' + itemIdioma("pt", "ms") + itemIdioma("en", "ms") + "</div></div>";
  }
  function painelLeitura() {
    var esc = A11Y.escala || 1, NOMES = EP.en ? ["Normal", "Bigger", "Even bigger", "Biggest"] : ["Normal", "Maior", "Bem maior", "Enorme"];
    // interruptor do Basecoat: <input type="checkbox" role="switch" class="input">; a linha inteira (label) liga e desliga
    function liga(chave, ic, titulo, explica) {
      return '<label class="opcao-a11y" for="sw-' + chave + '"><span class="oa-ic" aria-hidden="true">' + ic + '</span><span class="oa-txt"><b id="sw-' + chave + '-t">' + titulo + '</b><small id="sw-' + chave + '-d">' + explica + "</small></span>" +
        '<input type="checkbox" role="switch" class="input" id="sw-' + chave + '" data-a11y="' + chave + '" aria-labelledby="sw-' + chave + '-t" aria-describedby="sw-' + chave + '-d"' + (A11Y[chave] ? " checked" : "") + "></label>";
    }
    return '<header><h2 class="menu-tit" id="menu-leitura-tit">' + EP.tr("Letra e leitura", "Text and reading") + "</h2></header>" +
      '<div class="grupo-a11y"><b id="menu-letra-tit"><span aria-hidden="true">🔠 </span>' + EP.tr("Tamanho da letra", "Text size") + '</b><div class="tamanhos" role="group" aria-labelledby="menu-letra-tit">' +
      ESCALAS.map(function (e, i) {
        return '<button type="button" class="btn" data-variant="outline" data-escala="' + e + '" aria-pressed="' + (e === esc) + '"><span class="ta" aria-hidden="true" style="font-size:' + (0.85 + i * 0.2) + 'rem">A</span><span class="tn">' + NOMES[i] + "</span></button>";
      }).join("") + "</div></div>" +
      liga("contraste", "🌓", EP.tr("Alto contraste", "High contrast"), EP.tr("Preto no branco, com bordas fortes.", "Black on white, with strong borders.")) +
      liga("movimento", "🐢", EP.tr("Menos movimento", "Reduce motion"), EP.tr("Desliga as animações e os giros.", "Turns off animations and spinning.")) +
      liga("espaco", "↔️", EP.tr("Mais espaço no texto", "More text spacing"), EP.tr("Mais espaço entre letras, palavras e linhas.", "More space between letters, words and lines.")) +
      (podeFalar ? '<button type="button" class="opcao-a11y acao" data-a11y-acao="ouvir"><span class="oa-ic" aria-hidden="true">🔊</span><span class="oa-txt"><b>' + EP.tr("Ouvir esta página", "Listen to this page") + "</b><small>" +
        EP.tr("O aparelho lê o texto em voz alta. Também fica no botão 🔊 da barra.", "Your device reads the text out loud. It is also the 🔊 button on the bar.") + "</small></span></button>" : "") +
      (EP.en ? "" : '<button type="button" class="opcao-a11y acao" data-a11y-acao="libras"><span class="oa-ic" aria-hidden="true">🤟</span><span class="oa-txt"><b>Libras</b><small>Tradução para a Língua Brasileira de Sinais (VLibras, do governo federal).</small></span></button>') +
      '<details class="atalhos-teclado"><summary><span aria-hidden="true">⌨️ </span>' + EP.tr("Atalhos do teclado", "Keyboard shortcuts") + "</summary><ul>" +
      "<li><kbd class=\"kbd\">Tab</kbd> " + EP.tr("vai para o próximo botão ou link", "moves to the next button or link") + "</li>" +
      "<li><kbd class=\"kbd\">Enter</kbd> " + EP.tr("escolhe", "selects") + "</li>" +
      "<li><kbd class=\"kbd\">Esc</kbd> " + EP.tr("fecha menus e janelas", "closes menus and windows") + "</li>" +
      "<li><kbd class=\"kbd\">↑</kbd> <kbd class=\"kbd\">↓</kbd> " + EP.tr("andam pelas listas de escolha e pelos menus", "move through choice lists and menus") + "</li>" +
      "<li><kbd class=\"kbd\">←</kbd> <kbd class=\"kbd\">→</kbd> " + EP.tr("trocam de aba, de página nas apresentações e de estado no mapa", "change tabs, pages in presentations and states on the map") + "</li></ul></details>" +
      '<button type="button" class="btn menu-fecha" data-variant="ghost" data-fecha-menu><span aria-hidden="true">✕ </span>' + EP.tr("Fechar", "Close") + "</button>";
  }
  // [id do painel, montar, tipo do Basecoat]
  // bloco que abre e fecha ("accordion" do Basecoat: <details> com <summary>): o título à vista, o resto ao abrir
  EP.blocoAbre = function (classe, resumoHtml, corpo, aberto) {
    return '<div class="accordion bloco-abre"><details class="' + classe + '"' + (aberto ? " open" : "") + '><summary><span class="resumo-det">' + resumoHtml + "</span>" +
      CHEVRON.replace('class="lucide seta-menu"', 'class="lucide seta-det"') + '</summary><div class="det-corpo">' + corpo + "</div></details></div>";
  };
  var MENUS = [["menu-idioma", painelIdioma, "dropdown-menu"], ["menu-leitura", painelLeitura, "popover"], ["menu-site", painelSite, "dropdown-menu"]];
  function raizMenu(id) { var b = document.getElementById(id + "-btn"); return b ? b.parentNode : null; }
  function aberto(id) { var b = document.getElementById(id + "-btn"); return !!b && b.getAttribute("aria-expanded") === "true"; }
  EP.fechaMenus = function (devolveFoco) {
    MENUS.forEach(function (m) {
      if (!aberto(m[0])) return;
      var r = raizMenu(m[0]), b = document.getElementById(m[0] + "-btn"), p = document.getElementById(m[0]);
      if (r && r.close) r.close(!!devolveFoco);
      else { b.setAttribute("aria-expanded", "false"); if (p) p.setAttribute("aria-hidden", "true"); if (devolveFoco) b.focus(); }
    });
  };
  // no computador, o painel abre embaixo do botão, alinhado pela direita; no celular, ocupa a largura da tela, logo abaixo da barra.
  // site-d-r13: o idioma e a Leitura moram no pé do menu lateral; ali o painel abre para cima, colado no botão
  function posMenu(p) {
    var b = document.getElementById(p.id + "-btn");
    if (b && b.closest(".casca-lado")) {
      var r = b.getBoundingClientRect();
      p.style.setProperty("--menu-baixo", Math.round(innerHeight - r.top + 6) + "px");
      p.style.maxHeight = Math.max(200, Math.round(r.top - 14)) + "px";
      return;
    }
    var topo = document.querySelector("header.topo");
    var h = topo ? topo.getBoundingClientRect().bottom : 60;
    p.style.setProperty("--menu-topo", Math.round(h + 6) + "px");
    p.style.maxHeight = Math.max(200, innerHeight - h - 16) + "px";
  }
  function montaTopo() {
    var topo = document.querySelector("header.topo");
    if (!topo) return;
    var bi = document.getElementById("menu-idioma-btn");
    if (bi) {
      bi.querySelector(".rotulo-idioma").textContent = EP.en ? "EN" : "PT";
      bi.querySelector(".sr").textContent = EP.en ? "Language: English" : "Idioma: português";
    }
    var bl = document.getElementById("menu-leitura-btn");
    if (bl) {
      bl.querySelector(".rotulo").textContent = EP.tr("Leitura", "Reading");
      bl.querySelector(".sr").textContent = EP.tr(" (tamanho da letra e acessibilidade)", " (text size and accessibility)");
    }
    var bs = document.getElementById("menu-site-btn");
    if (bs) bs.querySelector(".sr").textContent = EP.tr(" (partes do site)", " (parts of the site)");
    var bo = document.getElementById("btn-ouvir");
    if (bo) {
      if (!podeFalar) bo.hidden = true;
      var ro = bo.querySelector(".rotulo");
      if (ro) ro.textContent = EP.tr("Ouvir", "Listen");
      bo.removeAttribute("aria-label");
      bo.title = EP.tr("Ouvir esta página em voz alta", "Listen to this page out loud");
      bo.addEventListener("click", EP.ouvir);
    }
    MENUS.forEach(function (m) {
      var b = document.getElementById(m[0] + "-btn");
      if (!b) return;
      var r = b.parentNode, p = document.createElement("div"), noLado = !!b.closest(".casca-lado");
      p.setAttribute("data-popover", "");
      if (noLado) p.setAttribute("data-side", "top");
      p.setAttribute("data-align", noLado ? "start" : "end");
      p.setAttribute("aria-hidden", "true");
      p.id = m[0];
      p.className = "menu-painel";
      if (m[2] === "popover") { p.setAttribute("role", "region"); p.setAttribute("aria-labelledby", "menu-leitura-tit"); }
      p.innerHTML = m[1]();
      r.appendChild(p);
      // o idioma dentro do ☰ menu só no celular estreito (antes de o Basecoat ler os itens do menu, a cada vez que abre)
      if (m[0] === "menu-site") b.addEventListener("click", function () { var g = p.querySelector(".grupo-idioma-site"); if (g) g.hidden = !apertado(); }, true);
      b.addEventListener("click", function () { setTimeout(function () { if (aberto(m[0])) posMenu(p); }, 0); });
      var fecha = p.querySelector("[data-fecha-menu]");
      if (fecha) fecha.addEventListener("click", function () { EP.fechaMenus(true); });
      // nos menus: o item ativo (setas, Home, End) recebe o foco de verdade
      if (m[2] === "dropdown-menu") {
        new MutationObserver(function (muts) {
          muts.forEach(function (x) {
            var it = x.target;
            if (it.classList && it.classList.contains("active") && aberto(m[0]) && document.activeElement !== it) {
              it.setAttribute("tabindex", "-1");
              b.removeAttribute("aria-activedescendant");
              // logo ao abrir, o painel ainda está aparecendo (transição): tenta de novo nos quadros seguintes
              var vezes = 0;
              (function foca() {
                if (!it.classList.contains("active") || !aberto(m[0])) return;
                it.focus({ preventScroll: true });
                if (document.activeElement !== it && ++vezes < 12) requestAnimationFrame(foca);
              })();
            }
          });
        }).observe(p, { attributes: true, attributeFilter: ["class"], subtree: true });
        // com o foco num item, Tab sai do menu e fecha
        r.addEventListener("keydown", function (e) { if (e.key === "Tab" && aberto(m[0]) && r.close) r.close(false); });
      }
    });
    if (window.basecoat) { window.basecoat.init("dropdown-menu"); window.basecoat.init("popover"); }
    // o topo fica numa linha só: se os botões não couberem (celular estreito, ou uma página com "◀ Voltar"), o idioma vai para o ☰ Menu
    var ferr = document.querySelector(".ferramentas-topo"), cab = ferr && ferr.closest("header");
    // 1º passo: o idioma vai para o ☰ Menu; 2º (letra grande, zoom): somem as setinhas e os botões ficam mais justos
    function estoura() { return ferr.getBoundingClientRect().right > document.documentElement.clientWidth - 2; }
    function ajustaTopo() {
      if (!cab) return;
      cab.classList.remove("topo-apertado", "topo-apertado-2");
      if (ESTREITO.matches || estoura()) cab.classList.add("topo-apertado");
      if (estoura()) cab.classList.add("topo-apertado-2");
    }
    apertado = function () { return !!cab && cab.classList.contains("topo-apertado"); };
    ajustaTopo();
    window.addEventListener("resize", ajustaTopo);
    window.addEventListener("ep-a11y", ajustaTopo);
    // o que está à esquerda do topo pode mudar depois (o progresso do mapa, o nome da página): mede de novo
    if (cab && "ResizeObserver" in window) {
      var roTopo = new ResizeObserver(function () { ajustaTopo(); });
      [].forEach.call(cab.children, function (c) { if (c !== ferr) roTopo.observe(c); });
    }
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(ajustaTopo);
    // idioma: guarda a escolha e abre a mesma página (com a mesma aba, busca e filtros) no outro idioma (site-d-r13: o menu de
    // idioma fica no pé do menu lateral, fora da barra do topo)
    document.addEventListener("click", function (e) {
      var a = e.target.closest && e.target.closest("[data-idioma]");
      if (!a || e.button || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      if (a.getAttribute("data-idioma") !== EP.lang) EP.trocaIdioma(a.getAttribute("data-idioma"));
    });
    // levar o foco para fora do menu aberto fecha (o Basecoat fecha com clique fora e Esc)
    document.addEventListener("focusin", function (e) {
      MENUS.forEach(function (m) {
        var r = raizMenu(m[0]);
        if (r && aberto(m[0]) && !r.contains(e.target)) { if (r.close) r.close(false); }
      });
    });
    window.addEventListener("resize", function () { MENUS.forEach(function (m) { if (aberto(m[0])) posMenu(document.getElementById(m[0])); }); });
    // os links de idioma acompanham o endereço (aba, busca e filtros mudam o endereço sem recarregar a página)
    EP.atualizaLinksIdioma = function () {
      [].forEach.call(document.querySelectorAll("[data-idioma]"), function (a) { a.href = EP.urlIdioma(a.getAttribute("data-idioma")); });
    };
  }

  // ---------------------------------------------------------------- caminho ("Você está aqui": Início › Bahia › Salvador › pessoa)
  // EP.trilha([{ t: "Bahia", href: "estado.html?uf=BA", lang }, ..., { t: "Salvador" }]): o "Início" vem sozinho; o último é a
  // página atual (aria-current). Fica logo abaixo da barra do topo, em todas as páginas menos a inicial (que é o começo) e as
  // aulas do mapa (que têm o próprio caminho: 🗺️ Mapa e ☰ Páginas). Cada página chama de novo quando sabe mais.
  EP.trilha = function (itens) {
    var main = document.querySelector("main");
    if (!main || /^(index\.html|entenda\.html)?$/.test(arquivoAtual())) return;
    var nav = document.getElementById("trilha"), topo = document.querySelector("body > header.topo");
    if (!nav) {
      nav = document.createElement("nav");
      nav.id = "trilha";
      // site-d-r13: o caminho fica na barra do topo (no celular, a barra mostra só o nome da página)
      if (topo) { nav.className = "trilha"; topo.insertBefore(nav, topo.querySelector(".ferramentas-topo")); }
      else { nav.className = "trilha miolo"; main.insertBefore(nav, main.firstChild); }
    }
    nav.setAttribute("aria-label", EP.tr("Você está aqui", "You are here"));
    var l = [{ t: EP.tr("Início", "Home"), href: EP.RAIZ || "./", ic: "🏠" }].concat((itens || []).filter(function (x) { return x && x.t; }));
    nav.innerHTML = "<ol>" + l.map(function (x, i) {
      var ult = i === l.length - 1, lang = x.lang ? ' lang="' + EP.esc(x.lang) + '"' : "";
      var txt = (x.ic ? '<span aria-hidden="true">' + x.ic + " </span>" : "") + "<span" + lang + ">" + EP.esc(x.t) + "</span>";
      return "<li>" + (ult ? '<span aria-current="page">' + txt + "</span>" : '<a href="' + EP.esc(x.href) + '">' + txt + "</a>") + "</li>";
    }).join("") + "</ol>";
    raizDoc.classList.add("tem-trilha");
    // o perfil fica na porta de onde a pessoa é (Brasil, estado ou cidade): o último lugar do caminho diz qual
    if (arquivoAtual() === "pessoa.html") {
      var lugar = l.slice(1, -1).filter(function (x) { return x.href; }).pop();
      marcaPorta(!lugar ? 2 : /cidade\.html/.test(lugar.href) ? 4 : /estado\.html/.test(lugar.href) ? 3 : 2);
    }
  };
  // o primeiro caminho (Início › nome da página, do cabeçalho); as páginas trocam depois
  function trilhaInicial() {
    var o = document.querySelector("header.topo .onde");
    if (!o || document.getElementById("trilha")) return;
    var t = (o.textContent || "").replace(/^[^\p{L}\p{N}]+/u, "").trim();
    if (t) EP.trilha([{ t: t }]);
  }

  // ---------------------------------------------------------------- casca do site (site-d-r13: o protótipo D no site inteiro)
  // Menu lateral fixo no computador: as 4 portas numeradas (1 Entenda, 2 Brasil, 3 Estado, 4 Cidade, a mesma numeração da
  // página inicial), embaixo só os itens da seção em que a pessoa está (as abas da página, ou os lugares do Brasil nas
  // votações), "Sobre o site" e, no pé, o idioma e a Leitura. No celular (até 767 px; site-d-r14: o tablet fica com o menu lateral), uma barra embaixo com as 4
  // portas e "☰ Menu", que abre o mesmo menu como uma gaveta: prende o foco (o resto da página fica inerte) e o Esc fecha.
  // A barra do topo (já no HTML de cada página) tem o caminho, a busca rápida (js/casca.js) e o 🔊 Ouvir.
  EP.PORTAS = [
    { n: 1, ic: "🗺️", href: "entenda.html", t: ["Entenda a política", "Understand politics"], c: ["Entenda", "Learn"] },
    { n: 2, ic: "🏛️", href: "brasil.html", t: ["A política do Brasil", "Brazil's politics"], c: ["Brasil", "Brazil"] },
    { n: 3, ic: "📍", href: "estado.html", t: ["A política do meu estado", "Politics in my state"], c: ["Estado", "State"] },
    { n: 4, ic: "🏘️", href: "cidade.html", t: ["A política da minha cidade", "Politics in my city"], c: ["Cidade", "City"] }];
  var PORTA_DA_PAGINA = { "entenda.html": 1, "brasil.html": 2, "votacoes.html": 2, "votacao.html": 2, "estado.html": 3, "cidade.html": 4 };
  var SOBRE = [["imparcialidade.html", "⚖️", "Como cuidamos da imparcialidade", "How we stay impartial"], ["dados.html", "🗂️", "De onde vêm os dados", "Where the data comes from"]];
  // nas páginas da porta 2 sem abas (as votações), os itens da seção são os lugares da página do Brasil
  var ITENS_BRASIL = [["brasil.html#executivo", "🏢", "Quem governa", "Who governs"], ["brasil.html#senado", "🏛️", "Senado", "Senate"],
    ["brasil.html#camara", "🏛️", "Câmara", "Chamber of Deputies"], ["brasil.html#votacoes", "🗳️", "Como votaram", "How Congress voted"],
    ["brasil.html#judiciario", "⚖️", "STF", "Supreme Court"], ["votacoes.html", "📊", "Todas as votações", "All the votes"]];
  var MQ_LADO = window.matchMedia ? matchMedia("(min-width: 768px)") : { matches: true, addEventListener: function () {} };
  var MQ_CEL = window.matchMedia ? matchMedia("(max-width: 767px)") : { matches: false };
  var casca = { porta: 0, lado: null, btn: null, veu: null, inertes: [] };
  function cHref(h) { return (EP.RAIZ || "") + h; }
  function itemMenu(href, ic, txt, extra) {
    return '<li><a href="' + EP.esc(href) + '"' + (extra || "") + '><span class="cl-ic" aria-hidden="true">' + ic + '</span><span class="cl-txt">' + EP.esc(txt) + "</span></a></li>";
  }
  var BOTAO_IDIOMA = '<div class="dropdown-menu"><button type="button" class="btn" data-variant="outline" id="menu-idioma-btn" aria-haspopup="menu" aria-expanded="false" aria-controls="menu-idioma">' +
    '<span aria-hidden="true">🌐</span><span class="rotulo-idioma" aria-hidden="true">PT</span><span class="sr">Idioma: português</span>' + CHEVRON + "</button></div>";
  var BOTAO_LEITURA = '<div class="popover"><button type="button" class="btn" data-variant="outline" id="menu-leitura-btn" aria-expanded="false" aria-controls="menu-leitura">' +
    '<span class="ic-aa" aria-hidden="true">Aa</span><span class="rotulo">Leitura</span><span class="sr"> (tamanho da letra e acessibilidade)</span>' + CHEVRON + "</button></div>";
  function marcaPorta(n) {
    casca.porta = n;
    var aqui = arquivoAtual();
    [].forEach.call(document.querySelectorAll(".casca-lado [data-porta], .casca-baixo [data-porta]"), function (a) {
      var eu = +a.getAttribute("data-porta") === n;
      a.classList.toggle("atual", eu);
      if (eu) a.setAttribute("aria-current", EP.PORTAS[n - 1].href === aqui ? "page" : "true"); else a.removeAttribute("aria-current");
    });
  }
  EP.marcaPorta = marcaPorta;
  // itens da seção: as abas da página (Brasil, estado, cidade e perfil), com o mesmo emoji e o mesmo nome
  function itensDaSecao() {
    var tabs = [].filter.call(document.querySelectorAll('.abas-lista [role="tab"][data-aba]'), function (t) { return !t.hidden; });
    if (tabs.length) {
      return { t: EP.tr("Nesta página", "On this page"), l: tabs.map(function (t) {
        var c = t.cloneNode(true), ic = c.querySelector('[aria-hidden="true"]'), e = ic ? ic.textContent.trim() : "";
        [].forEach.call(c.querySelectorAll('[aria-hidden="true"], .sr'), function (x) { x.remove(); });
        return { id: t.getAttribute("data-aba"), href: "#" + t.getAttribute("data-aba"), ic: e || "•", t: c.textContent.replace(/\s+/g, " ").trim() };
      }) };
    }
    if (/^votaco?e?s?\.html$/.test(arquivoAtual()) || arquivoAtual() === "votacao.html") {
      return { t: EP.tr("A política do Brasil", "Brazil's politics"), l: ITENS_BRASIL.map(function (x) { return { id: x[0], href: cHref(x[0]), ic: x[1], t: EP.tr(x[2], x[3]) }; }) };
    }
    return { t: "", l: [] };
  }
  var ultimaSecao = "";
  function atualizaSecao() {
    var g = document.getElementById("cl-secao");
    if (!g) return;
    var s = itensDaSecao(), chave = s.t + "|" + s.l.map(function (x) { return x.id + x.t; }).join(",");
    if (chave !== ultimaSecao) {
      ultimaSecao = chave;
      g.querySelector(".cl-tit").textContent = s.t;
      g.querySelector("ul").innerHTML = s.l.map(function (x) { return itemMenu(x.href, x.ic, x.t, ' data-item="' + EP.esc(x.id) + '"'); }).join("");
      g.hidden = !s.l.length;
    }
    var at = EP.abas && EP.abas.ativa ? EP.abas.ativa() : null, aqui = arquivoAtual();
    [].forEach.call(g.querySelectorAll("[data-item]"), function (a) {
      var id = a.getAttribute("data-item");
      if (id === aqui) a.setAttribute("aria-current", "page");
      else if (at && id === at) a.setAttribute("aria-current", "location");
      else a.removeAttribute("aria-current");
    });
  }
  EP.atualizaMenuSecao = atualizaSecao;
  function menuAberto() { return !!casca.lado && casca.lado.classList.contains("aberto"); }
  function abreMenu() {
    if (MQ_LADO.matches || menuAberto() || !casca.lado) return;
    var l = casca.lado;
    l.classList.add("aberto");
    casca.veu.hidden = false;
    casca.btn.setAttribute("aria-expanded", "true");
    // o resto da página fica inerte: o Tab e o leitor de tela ficam dentro do menu
    casca.inertes = [].filter.call(document.body.children, function (el) {
      return el !== l && el !== casca.veu && !el.inert && !/^(SCRIPT|DIALOG|NOSCRIPT|STYLE)$/.test(el.tagName);
    });
    casca.inertes.forEach(function (el) { el.inert = true; });
    raizDoc.classList.add("menu-aberto");
    var f = document.getElementById("casca-fecha");
    if (f) setTimeout(function () { f.focus(); }, 20);
  }
  function fechaMenu(devolve) {
    if (!menuAberto()) return;
    if (EP.fechaMenus) EP.fechaMenus(false);
    casca.lado.classList.remove("aberto");
    casca.veu.hidden = true;
    casca.btn.setAttribute("aria-expanded", "false");
    casca.inertes.forEach(function (el) { el.inert = false; });
    casca.inertes = [];
    raizDoc.classList.remove("menu-aberto");
    if (devolve) casca.btn.focus();
  }
  EP.abreMenu = abreMenu;
  EP.fechaMenu = fechaMenu;
  function montaCasca() {
    var topo = document.querySelector("body > header.topo");
    if (!topo || document.getElementById("casca-lado")) return;
    var aqui = arquivoAtual();
    raizDoc.classList.add("casca");
    var lado = document.createElement("aside");
    lado.id = "casca-lado";
    lado.className = "casca-lado";
    lado.setAttribute("aria-label", EP.tr("Menu do site", "Site menu"));
    lado.innerHTML =
      '<div class="cl-cab"><a class="cl-marca" href="' + (EP.RAIZ || "./") + '"><span class="cl-logo" aria-hidden="true">🏛️</span><span class="cl-marca-txt"><b>' +
      EP.tr("Entenda Política", "Understand Politics") + "</b><small>" + EP.tr("A política do Brasil, fácil de entender", "Brazil's politics, made easy") + "</small></span></a>" +
      '<button type="button" class="btn cl-fecha" data-variant="outline" id="casca-fecha">' + EP.ICONES.x + '<span class="sr">' + EP.tr("Fechar o menu", "Close the menu") + "</span></button></div>" +
      '<nav class="cl-nav" aria-label="' + EP.tr("Partes do site", "Parts of the site") + '">' +
      '<div class="cl-grupo" role="group" aria-labelledby="cl-portas-t"><span class="cl-tit" id="cl-portas-t">' + EP.tr("Por onde ir", "Where to go") + '</span><ul class="cl-portas">' +
      EP.PORTAS.map(function (p) {
        return '<li><a href="' + cHref(p.href) + '" data-porta="' + p.n + '"><span class="cl-num" aria-hidden="true">' + p.n + '</span><span class="cl-ic" aria-hidden="true">' + p.ic +
          '</span><span class="cl-txt">' + EP.esc(EP.tr(p.t[0], p.t[1])) + "</span></a></li>";
      }).join("") + "</ul></div>" +
      '<div class="cl-grupo" role="group" aria-labelledby="cl-secao-t" id="cl-secao" hidden><span class="cl-tit" id="cl-secao-t"></span><ul></ul></div>' +
      '<div class="cl-grupo" role="group" aria-labelledby="cl-sobre-t"><span class="cl-tit" id="cl-sobre-t">' + EP.tr("Sobre o site", "About the site") + "</span><ul>" +
      SOBRE.map(function (s) { return itemMenu(cHref(s[0]), s[1], EP.tr(s[2], s[3]), s[0] === aqui ? ' aria-current="page"' : ""); }).join("") + "</ul></div></nav>" +
      '<div class="cl-pe" role="group" aria-labelledby="cl-pe-t"><span class="cl-tit" id="cl-pe-t">' + EP.tr("Idioma e leitura", "Language and reading") + '</span><div class="cl-pe-botoes">' +
      BOTAO_IDIOMA + BOTAO_LEITURA + "</div></div>";
    document.body.insertBefore(lado, topo);
    var veu = document.createElement("div");
    veu.className = "casca-veu";
    veu.hidden = true;
    document.body.insertBefore(veu, topo);
    var baixo = document.createElement("nav");
    baixo.className = "casca-baixo";
    baixo.setAttribute("aria-label", EP.tr("Atalhos", "Shortcuts"));
    baixo.innerHTML = EP.PORTAS.map(function (p) {
      return '<a href="' + cHref(p.href) + '" data-porta="' + p.n + '"><span class="cb-ic" aria-hidden="true">' + p.ic + '<i class="cl-num">' + p.n + '</i></span><span class="cb-txt">' +
        EP.esc(EP.tr(p.c[0], p.c[1])) + '</span><span class="sr"> (' + EP.esc(EP.tr(p.t[0], p.t[1])) + ")</span></a>";
    }).join("") + '<button type="button" id="casca-menu-btn" aria-controls="casca-lado" aria-expanded="false"><span class="cb-ic" aria-hidden="true">☰</span><span class="cb-txt">Menu</span></button>';
    var pe = document.querySelector("body > footer");
    if (pe) pe.insertAdjacentElement("afterend", baixo); else document.body.appendChild(baixo);
    casca.lado = lado; casca.veu = veu; casca.btn = baixo.querySelector("#casca-menu-btn");
    marcaPorta(PORTA_DA_PAGINA[aqui] || 0);
    casca.btn.addEventListener("click", function () { if (menuAberto()) fechaMenu(true); else abreMenu(); });
    veu.addEventListener("click", function () { fechaMenu(true); });
    document.getElementById("casca-fecha").addEventListener("click", function () { fechaMenu(true); });
    // um item da própria página (uma aba) fecha o menu; os outros links levam para outra página
    lado.addEventListener("click", function (e) {
      var a = e.target.closest && e.target.closest("a[href]");
      if (a && menuAberto() && /^#/.test(a.getAttribute("href"))) fechaMenu(false);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape" || !menuAberto()) return;
      // um painel aberto (idioma ou Leitura) fecha primeiro, pelo Basecoat
      if (lado.querySelector('[data-popover][aria-hidden="false"]')) return;
      e.preventDefault();
      fechaMenu(true);
    }, true);
    if (MQ_LADO.addEventListener) MQ_LADO.addEventListener("change", function () { if (MQ_LADO.matches) fechaMenu(false); });
    window.addEventListener("pageshow", function () { fechaMenu(false); });
    window.addEventListener("ep-aba", function () { setTimeout(atualizaSecao, 0); });
    window.addEventListener("hashchange", function () { setTimeout(atualizaSecao, 0); });
    // as abas aparecem (e somem) quando os dados chegam: o menu da seção acompanha
    var obsAbas = null;
    function olhaAbas() {
      var l = document.querySelector(".abas-lista");
      if (!l || obsAbas) return !!l;
      obsAbas = new MutationObserver(function () { atualizaSecao(); });
      obsAbas.observe(l, { attributes: true, attributeFilter: ["hidden"], subtree: true, childList: true });
      return true;
    }
    atualizaSecao();
    if (!olhaAbas()) {
      var obsPag = new MutationObserver(function () { if (olhaAbas()) { obsPag.disconnect(); atualizaSecao(); } });
      obsPag.observe(document.body, { childList: true, subtree: true });
      setTimeout(function () { obsPag.disconnect(); }, 15000);
    }
  }

  // ---------------------------------------------------------------- gaveta (site-d-r13: a do protótipo D)
  // EP.gaveta(o, de) abre uma gaveta do lado direito (no celular, sobe de baixo) sem sair da página. É um <dialog> modal: o
  // navegador prende o foco e deixa o resto inerte; Esc, ✕ e clicar fora fecham; o foco volta para quem abriu.
  //   o = { tit (html), sub (texto), corpo: html | function (el, o) -> html | promessa de html, pagina: { href, t, secao },
  //         ver: "p:dep-178866" (vai para o endereço, ?ver=…), depois(el) }
  // Uma gaveta aberta de dentro de outra empilha: "‹ Voltar" volta para a de antes. O endereço guarda a gaveta: dá para
  // compartilhar; o Voltar do navegador fecha e o Avançar abre de novo. EP.gavetaVer[prefixo] = function (resto) abre pelo
  // endereço ("p" é a pessoa, aqui mesmo). "Ver a página inteira" toma o lugar do passo da gaveta no histórico: o Voltar de
  // lá volta para a lista, sem a gaveta, com o foco em quem foi aberto. O EP.abrir (janela) continua para as fontes.
  var gav = null, gPilha = [], gOrigem = null, gEmpurrou = false, gPorVoltar = false;
  EP.gavetaVer = {};
  function urlVer(v) {
    var u = new URL(location.href);
    if (v) u.searchParams.set("ver", v); else u.searchParams.delete("ver");
    return u.pathname + u.search + u.hash;
  }
  function gEl(s) { return gav.querySelector(s); }
  function montaGaveta() {
    if (gav) return;
    gav = document.createElement("dialog");
    gav.className = "gaveta";
    gav.id = "gaveta";
    gav.setAttribute("aria-labelledby", "gaveta-tit");
    gav.innerHTML = '<div class="gv-caixa"><header class="gv-cab"><div class="gv-botoes"><button type="button" class="btn gv-volta" data-variant="outline" hidden><span aria-hidden="true">‹ </span>' +
      EP.tr("Voltar", "Back") + '</button><button type="button" class="btn gv-fecha" data-variant="outline">' + EP.ICONES.x + '<span class="sr">' + EP.tr("Fechar", "Close") + "</span></button></div>" +
      '<h2 id="gaveta-tit" tabindex="-1"></h2><p class="gv-sub" hidden></p></header><div class="gv-corpo"></div><footer class="gv-pe" hidden></footer></div>';
    document.body.appendChild(gav);
    gEl(".gv-volta").addEventListener("click", function () { gPilha.pop(); gDesenha(); gEl("#gaveta-tit").focus(); });
    gEl(".gv-fecha").addEventListener("click", function () { gav.close(); });
    gav.addEventListener("click", function (e) {
      if (e.target === gav) { gav.close(); return; }
      var a = e.target.closest && e.target.closest("a.gv-pagina");
      if (!a || e.button || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
      if (gEmpurrou && history.state && history.state.gaveta) { e.preventDefault(); location.replace(a.href); }
      else { try { history.replaceState(history.state, "", urlVer("")); } catch (x) {} }
    });
    gav.addEventListener("close", function () {
      gPilha = [];
      EP.calar();
      if (gPorVoltar) gPorVoltar = false;
      else if (gEmpurrou && history.state && history.state.gaveta) { gEmpurrou = false; history.back(); }
      else { try { history.replaceState(history.state, "", urlVer("")); } catch (e) {} }
      gEmpurrou = false;
      if (EP.atualizaLinksIdioma) EP.atualizaLinksIdioma();
      if (gOrigem && gOrigem.focus && document.contains(gOrigem)) gOrigem.focus();
      // o Voltar do histórico (acima) pode fazer a lista ser montada de novo: aí o foco vai para o mesmo cartão, já novo
      var o = gOrigem, h = o && o.getAttribute ? o.getAttribute("href") : null, s = o && o.closest ? o.closest("section[id]") : null, sid = s ? s.id : "";
      [120, 450, 1000].forEach(function (ms) {
        setTimeout(function () {
          if (gav.open || (document.activeElement && document.activeElement !== document.body)) return;
          var alvo = o && document.contains(o) ? o : null;
          if (!alvo && h) {
            var sec = sid && document.getElementById(sid), sel = 'a[href="' + h.replace(/"/g, '\\"') + '"]';
            alvo = (sec && sec.querySelector(sel)) || document.querySelector("main " + sel);
          }
          if (alvo) alvo.focus({ preventScroll: true });
        }, ms);
      });
    });
  }
  function gDesenha() {
    var v = gPilha[gPilha.length - 1], corpo = gEl(".gv-corpo"), pe = gEl(".gv-pe"), sub = gEl(".gv-sub");
    gEl("#gaveta-tit").innerHTML = v.tit;
    sub.textContent = v.sub || "";
    sub.hidden = !v.sub;
    gEl(".gv-volta").hidden = gPilha.length < 2;
    pe.innerHTML = v.pagina ? '<a class="btn azul gv-pagina" href="' + EP.esc(v.pagina.href) + '"' + (v.pagina.secao ? ' data-secao="' + EP.esc(v.pagina.secao) + '"' : "") + ">" +
      EP.esc(v.pagina.t || EP.tr("Ver a página inteira", "See the full page")) + ' <span aria-hidden="true">›</span></a>' : "";
    pe.hidden = !v.pagina;
    corpo.scrollTop = 0;
    corpo.innerHTML = "";
    var r = typeof v.corpo === "function" ? v.corpo(corpo, v) : v.corpo;
    if (typeof r === "string") { corpo.innerHTML = r; if (v.depois) v.depois(corpo); }
    else if (r && r.then) {
      corpo.innerHTML = '<p class="gv-carregando">' + EP.tr("Carregando…", "Loading…") + "</p>";
      r.then(function (h) {
        if (gPilha[gPilha.length - 1] !== v) return;
        if (typeof h === "string") corpo.innerHTML = h;
        if (v.depois) v.depois(corpo);
      }).catch(function () {
        if (gPilha[gPilha.length - 1] === v) corpo.innerHTML = "<p>" + EP.tr("Não foi possível carregar agora. Tente de novo daqui a pouco.", "This could not be loaded right now. Please try again in a little while.") + "</p>";
      });
    }
    try { history.replaceState(history.state, "", urlVer(v.ver || "")); } catch (e) {}
    if (EP.atualizaLinksIdioma) EP.atualizaLinksIdioma();
  }
  EP.gaveta = function (o, de) {
    montaGaveta();
    var nova = !gav.open;
    if (nova) {
      gPilha = [];
      gOrigem = de || document.activeElement;
      EP.calar();
      if (EP.fechaMenus) EP.fechaMenus(false);
      fechaMenu(false);
      if (!EP.param("ver")) {
        // a gaveta põe um passo no histórico (o Voltar do navegador fecha); a rolagem da lista fica guardada no passo de antes
        if (EP.memo) EP.memo.grava("y", Math.round(window.scrollY));
        try { history.pushState(Object.assign({}, history.state || {}, { gaveta: 1 }), "", location.href); gEmpurrou = true; } catch (e) { gEmpurrou = false; }
      } else gEmpurrou = false;
    }
    gPilha.push(o);
    gav.setAttribute("data-lado", MQ_CEL.matches ? "baixo" : "direita");
    gDesenha();
    if (nova) { try { gav.showModal(); } catch (e) { gav.setAttribute("open", ""); } }
    (gPilha.length > 1 ? gEl(".gv-volta") : gEl("#gaveta-tit")).focus();
  };
  EP.gavetaAberta = function () { return !!(gav && gav.open); };
  EP.fechaGaveta = function () { if (gav && gav.open) gav.close(); };
  // muda o título da gaveta de cima (quando os dados chegam)
  EP.gavetaTitulo = function (tit, sub) {
    var v = gPilha[gPilha.length - 1];
    if (!v) return;
    v.tit = tit;
    if (sub !== undefined) v.sub = sub;
    gEl("#gaveta-tit").innerHTML = tit;
    gEl(".gv-sub").textContent = v.sub || "";
    gEl(".gv-sub").hidden = !v.sub;
  };
  function abreVer(v) {
    var m = /^([a-z]+):(.+)$/.exec(v || "");
    if (m && EP.gavetaVer[m[1]]) { try { EP.gavetaVer[m[1]](m[2]); } catch (e) {} }
  }
  window.addEventListener("popstate", function () {
    if (gav && gav.open && !EP.param("ver")) { gPorVoltar = true; gav.close(); }
    else if ((!gav || !gav.open) && EP.param("ver")) abreVer(EP.param("ver"));
  });

  // a pessoa na gaveta: o que o cartão já mostra (foto, nome, partido, lugar, 2026) e, para quem tem arquivo próprio
  // (dados/pessoas/), os números grandes (propostas, leis, votações, gastos) e a barra da situação das propostas
  var COM_ARQUIVO = /^(dep|sen|pres|vp|dest|gov)-[\w-]+$/;
  function achaCartao(id) {
    var h = 'pessoa.html?id=' + encodeURIComponent(id);
    return document.querySelector('main a.pessoa-card[href="' + h + '"], main a.pessoa-grande[href="' + h + '"]');
  }
  function resumoCartao(card) {
    if (!card) return "";
    var av = card.querySelector(".av"), linhas = [].map.call(card.querySelectorAll(".cargo, small"), function (s) { return s.textContent.trim(); }).filter(Boolean);
    var chip = card.querySelector(".chip");
    return '<div class="gv-pessoa"><span class="gv-moldura">' + (av ? av.outerHTML.replace(/\bloading="lazy"\s*/, "") : "") + "</span><div>" +
      linhas.map(function (t) { return '<p class="gv-linha">' + EP.esc(t) + "</p>"; }).join("") + (chip ? chip.outerHTML : "") + "</div></div>";
  }
  function kpi(ic, n, t) { return '<li class="gv-kpi"><span class="gv-kpi-ic" aria-hidden="true">' + ic + "</span><b>" + EP.esc(String(n)) + "</b><span>" + EP.esc(t) + "</span></li>"; }
  var ORDEM_ST = ["lei", "aprovada", "andando", "junta", "arquivada", "rejeitada", "parada", "retirada", "outra"];
  function barraSituacao(lista) {
    var c = {};
    lista.forEach(function (x) { var s = EP.STATUS[x.status] ? x.status : "outra"; c[s] = (c[s] || 0) + 1; });
    var cs = ORDEM_ST.filter(function (k) { return c[k]; });
    if (!cs.length) return "";
    return '<div class="gv-situacao"><p class="gv-h3">' + EP.tr("O que aconteceu com as propostas", "What happened to the proposals") + '</p><div class="gv-barra" aria-hidden="true">' +
      cs.map(function (k) { return '<i class="gv-st-' + k + '" style="flex:' + c[k] + '"></i>'; }).join("") + '</div><ul class="gv-legenda">' +
      cs.map(function (k) { return '<li><i class="gv-st-' + k + '" aria-hidden="true"></i><span aria-hidden="true">' + EP.STATUS[k].ic + "</span> " + EP.esc(EP.STATUS[k].curto) + " <b>" + EP.num(c[k]) + "</b></li>"; }).join("") +
      "</ul></div>";
  }
  function corpoPessoa(id, card) {
    var base = resumoCartao(card);
    if (!COM_ARQUIVO.test(id)) {
      return base + '<p class="gv-dica">' + EP.tr("Na página inteira estão o que esta pessoa propôs, a história dela na política e as fontes.",
        "The full page shows what this person proposed, their history in politics and the sources.") + "</p>";
    }
    return EP.json(cHref("dados/pessoas/" + id + ".json")).then(function (p) {
      var partido = !p.partido ? "" : /^sem partido$/i.test(p.partido) ? EP.tr("Sem partido", "No party") : p.partido;
      var lugar = p.municipio && p.municipio.nome ? p.municipio.nome + " (" + p.uf + ")" : p.uf ? EP.UFS[p.uf] || p.uf : "";
      EP.gavetaTitulo(EP.pt(EP.esc(p.nome)), [EP.cargo(p.cargo), lugar].filter(Boolean).join(" · "));
      var pr = p.propostas && p.propostas.lista ? p.propostas.lista : [], lei = pr.filter(function (x) { return x.status === "lei"; }).length, k = [];
      if (pr.length) k.push(kpi("📝", EP.num(pr.length), EP.tr("propostas", "proposals")), kpi("📜", EP.num(lei), EP.tr("viraram lei", "became law")));
      if (p.executivo && p.executivo.leisSancionadas != null) k.push(kpi("✍️", EP.num(p.executivo.leisSancionadas), EP.tr("leis sancionadas", "laws signed")));
      if (p.votacoes && p.votacoes.resumo && p.votacoes.resumo.total) k.push(kpi("🗳️", EP.num(p.votacoes.resumo.total), EP.tr("votações", "votes")));
      if (p.gastos && p.gastos.total != null) k.push(kpi("💸", EP.dinheiroCurto(p.gastos.total), EP.tr("gastos em ", "spent in ") + p.gastos.ano));
      var topo = '<div class="gv-pessoa"><span class="gv-moldura">' + EP.av(p.foto, p.nome, "", true) + '</span><div><p class="gv-chips">' +
        (partido ? '<span class="gv-chip">' + EP.pt(EP.esc(partido)) + "</span>" : "") + (p.uf ? '<span class="gv-chip claro">' + EP.esc(p.uf) + "</span>" : "") + "</p>" +
        EP.chip2026(p.eleicao2026, p.genero, true) + "</div></div>";
      var saiba = [];
      if (pr.length) saiba.push(EP.tr("Propor muito não quer dizer trabalhar mais, e propor pouco não quer dizer trabalhar menos: cada proposta é diferente, e muitas são feitas junto com outras pessoas.",
        "Proposing a lot does not mean working more, and proposing little does not mean working less: each proposal is different, and many are written together with other people."));
      if (p.gastos && p.gastos.total != null) saiba.push(EP.tr("Os gastos são da verba que a Casa paga para o trabalho do mandato (escritório, viagens, divulgação). Gastar mais ou menos, sozinho, não diz se alguém trabalha melhor ou pior.",
        "The spending comes from the allowance the house pays for the work of the office (office, travel, communication). Spending more or less does not, by itself, say whether someone works better or worse."));
      return topo + (k.length ? '<ul class="gv-kpis" aria-label="' + EP.tr("Números", "Numbers") + '">' + k.join("") + "</ul>" : "") + barraSituacao(pr) +
        (saiba.length ? '<details class="gv-saiba"><summary><span aria-hidden="true">💡</span> ' + EP.tr("Saber mais", "Learn more") + "</summary><div>" +
          saiba.map(function (t) { return "<p>" + t + "</p>"; }).join("") + "</div></details>" : "") +
        '<p class="gv-fonte">' + EP.botaoFontes([].concat(p.fontes || [], (p.propostas || {}).fonte || [], (p.votacoes || {}).fonte || [], (p.gastos || {}).fonte || [], (p.executivo || {}).fonte || [])
          .filter(function (f, i, l) { return f && f.url && l.map(function (x) { return x && x.url; }).indexOf(f.url) === i; })) + "</p>";
    }, function () { return base; });
  }
  EP.abrePessoa = function (id, de) {
    var card = de && de.closest ? de.closest("a.pessoa-card, a.pessoa-grande") : achaCartao(id);
    var nome = card && card.querySelector("b") ? card.querySelector("b").innerHTML : "";
    var sec = card && card.closest("section[id]");
    EP.gaveta({ tit: nome || EP.tr("Carregando…", "Loading…"), ver: "p:" + id,
      pagina: { href: cHref("pessoa.html?id=" + encodeURIComponent(id)), secao: sec ? sec.id : "" },
      corpo: function () { return corpoPessoa(id, card); } }, de);
  };
  EP.gavetaVer.p = function (id) {
    if (!/^[\w:-]+$/.test(id)) return;
    // pelo endereço: espera o cartão aparecer na lista (os dados chegam depois), para a gaveta ter foto e nome mesmo sem arquivo próprio
    var t0 = Date.now();
    (function tenta() {
      var c = achaCartao(id);
      if (c || COM_ARQUIVO.test(id) || Date.now() - t0 > 4000) EP.abrePessoa(id, c);
      else setTimeout(tenta, 150);
    })();
  };
  // clicar numa pessoa das listas do Brasil, do estado e da cidade abre a gaveta (Ctrl/⌘ + clique, Shift + clique e o botão
  // do meio continuam abrindo a página inteira). site-d-r14: também nos cartões grandes (presidente, vice, governador,
  // prefeito) e nas pessoas de dentro de uma gaveta (ex.: as de um partido), que abrem uma gaveta por cima (com "‹ Voltar")
  var PAGINAS_GAVETA = /^(brasil|estado|cidade)\.html$/;
  var CARTOES_GAVETA = ["main a.pessoa-card", "main a.pessoa-grande", "#gaveta a.pessoa-card"].map(function (s) { return s + '[href^="pessoa.html?id="]'; }).join(", ");
  document.addEventListener("click", function (e) {
    if (!PAGINAS_GAVETA.test(arquivoAtual()) || e.defaultPrevented || e.button || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest && e.target.closest(CARTOES_GAVETA);
    if (!a) return;
    var id = new URLSearchParams(a.getAttribute("href").split("?")[1]).get("id");
    if (!id) return;
    e.preventDefault();
    EP.abrePessoa(id, a);
  });

  // ---------------------------------------------------------------- peças do visual D (site-d-r14)
  // Ícone com volume, foto em moldura, números grandes, "💡 Saber mais" e o placar de uma votação: usadas pelo Brasil e pelo
  // perfil (e, nos próximos passos, pelo estado e pela cidade). O visual fica em css/d.css. Todo desenho tem o texto ao lado
  // (o número escrito) ou é aria-hidden com o equivalente em texto perto.
  var DV = (EP.d = {});
  DV.ic = function (e, cls) { return '<span class="d-ic' + (cls ? " " + cls : "") + '" aria-hidden="true">' + e + "</span>"; };
  DV.moldura = function (foto, nome, cls, eager) { return '<span class="d-moldura' + (cls ? " " + cls : "") + '">' + EP.av(foto, nome, null, eager) + "</span>"; };
  // o nome curto da área de um ministério ("Ministério da Saúde" -> "Saúde"; "Ministry of Health" -> "Health")
  DV.area = function (n) {
    var a = String(n || "").replace(/^Minist[ée]rio (da|do|de|das|dos) /i, "").replace(/^Ministry (of the|of|for the|for) /i, "")
      .replace(/ da Presid[êe]ncia da Rep[úu]blica$/i, "").replace(/ of the Presidency( of the Republic)?$/i, "").trim();
    return a.charAt(0).toUpperCase() + a.slice(1);
  };
  DV.saiba = function (corpo, rot, cls) {
    return '<details class="d-saiba' + (cls ? " " + cls : "") + '"><summary><span aria-hidden="true">💡</span> ' + EP.esc(rot || EP.tr("Saber mais", "Learn more")) +
      '</summary><div class="d-saiba-corpo">' + corpo + "</div></details>";
  };
  // números grandes: l = [{ ic, n, t, href?, titulo? }] (o número e o texto ficam escritos; o ícone é enfeite)
  DV.kpis = function (l, rot, cls) {
    l = (l || []).filter(function (k) { return k && k.n != null && k.n !== ""; });
    if (!l.length) return "";
    return '<ul class="d-kpis' + (cls ? " " + cls : "") + '"' + (rot ? ' aria-label="' + EP.esc(rot) + '"' : "") + ">" + l.map(function (k) {
      var s = String(k.n), m = DV.ic(k.ic, "peq") + "<b" + (s.length > 7 ? ' class="longo"' : s.length > 5 ? ' class="medio"' : "") + ">" + EP.esc(s) + '</b><span class="d-kpi-t">' + EP.esc(k.t) + "</span>";
      return "<li>" + (k.href ? '<a class="d-kpi" href="' + EP.esc(k.href) + '"' + (k.aba ? ' data-aba-kpi="' + EP.esc(k.aba) + '"' : "") + ">" + m + "</a>" : '<div class="d-kpi">' + m + "</div>") + "</li>";
    }).join("") + "</ul>";
  };
  // cabeçalho de um bloco: ícone com volume + título + 1 linha (o resto do texto vai para o "Saber mais")
  DV.cab = function (ic, nivel, id, titHtml, linha, extra) {
    var h = "h" + (nivel || 3);
    return '<div class="d-bloco-cab">' + DV.ic(ic) + '<div class="d-bloco-txt"><' + h + (id ? ' id="' + id + '"' : "") + ">" + titHtml + "</" + h + ">" +
      (linha ? '<p class="d-linha">' + linha + "</p>" : "") + "</div>" + (extra || "") + "</div>";
  };
  // placar de uma votação: os números escritos (Sim × Não e os outros) e a barra (só desenho)
  DV.COR_VOTO = { "Sim": "#1f3a5f", "Não": "#9a4f00", "Abstenção": "#5b6573", "Obstrução": "#6a3fb0", "Outro": "#6b5a33" };
  DV.placar = function (pl) {
    if (!pl || !pl.total) return "";
    var outros = (pl["Abstenção"] || 0) + (pl["Obstrução"] || 0) + (pl.Outro || 0);
    return '<div class="d-placar"><p class="d-placar-n"><span class="v-sim"><b>' + EP.num(pl.Sim || 0) + "</b> " + EP.tr("Sim", "Yes") + '</span><i aria-hidden="true">×</i>' +
      '<span class="v-nao"><b>' + EP.num(pl["Não"] || 0) + "</b> " + EP.tr("Não", "No") + "</span>" +
      (outros ? '<span class="v-outro"><b>' + EP.num(outros) + "</b> " + EP.tr(outros === 1 ? "outro" : "outros", outros === 1 ? "other" : "others") + "</span>" : "") + "</p>" +
      '<span class="d-placar-barra" aria-hidden="true">' + ["Sim", "Não", "Abstenção", "Obstrução", "Outro"].filter(function (k) { return pl[k]; }).map(function (k) {
        return '<i style="flex:' + pl[k] + ";background:" + DV.COR_VOTO[k] + '"></i>';
      }).join("") + "</span></div>";
  };

  function ligaTopo() {
    EP.aplicaIdioma();
    if (!topoMontado) { montaCasca(); montaTopo(); }
    trilhaInicial();
    aplicaA11y();
    avisoIdioma();
    // a página foi aberta com uma gaveta no endereço (?ver=…): abre de novo
    if (EP.param("ver")) setTimeout(function () { abreVer(EP.param("ver")); }, 0);
  }

  // ---------------------------------------------------------------- campo de escolha com busca (no lugar de todo "select")
  // A pessoa digita e as opções vão aparecendo (padrão ARIA 1.2: combobox com lista). Funciona com mouse, toque,
  // teclado (setas, Enter, Esc, Home/End na lista) e leitor de tela.
  //   EP.combo(onde, o)       cria o campo dentro de "onde". o = { id, rotulo (se não houver <label>), rotuloId (id do <label>),
  //                           placeholder, itens: [{ v, t, sub, lang, busca, ph }] ou function () -> Promise, valor, min (letras
  //                           para começar a mostrar), max (opções mostradas), classe, dica, aoEscolher(item) }
  //                           ph: true = o texto de "escolha…" de um select (vira o placeholder do campo, nunca uma opção).
  //   EP.comboSelect(select)  troca um <select> por esse campo (o select fica escondido, guarda o valor e recebe "change").
  //   EP.comboSync(select)    avisa o campo quando o código mudou select.value.
  // ui-r9: a marcação e o visual são os do "combobox" do Basecoat (div.combobox > input[role=combobox] + [data-popover] com a
  // lista; a opção escolhida tem aria-selected="true" e o ✓; a marcada pelas setas, a classe "active"); a busca enquanto se
  // digita, o teclado e o leitor de tela continuam daqui. A lista abre na "top layer" do navegador (atributo popover): fica
  // por cima de tudo (barra do topo, barra das abas, rodapé, enfeites), presa embaixo do campo (ou em cima, quando embaixo
  // não cabe), da largura do campo pelo menos, sem passar da tela. O texto não fica todo selecionado ao entrar no campo (com
  // uma opção escolhida, a primeira letra digitada começa uma busca nova); × limpa o campo.
  var nCombo = 0;
  EP.combo = function (onde, o) {
    o = o || {};
    var id = o.id || "combo-" + (++nCombo), max = o.max || 80, min = o.min || 0;
    var caixa = document.createElement("div");
    caixa.className = "combo combobox" + (o.classe ? " " + o.classe : "");
    caixa.innerHTML = '<input type="text" class="input" id="' + id + '" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="' + id + '-lista"' +
      ' autocomplete="off" autocapitalize="off" spellcheck="false"' + (o.rotulo ? ' aria-label="' + EP.esc(o.rotulo) + '"' : "") +
      (o.descricao ? ' aria-describedby="' + EP.esc(o.descricao) + '"' : "") + (o.placeholder ? ' placeholder="' + EP.esc(o.placeholder) + '"' : "") + ">" +
      '<button type="button" class="combo-limpa" data-clear hidden aria-label="' + EP.tr("Limpar o campo", "Clear the field") + '" title="' + EP.tr("Limpar", "Clear") + '">' + EP.ICONES.x + "</button>" +
      EP.ICONES.chevron.replace('class="lucide seta-menu"', 'class="lucide combobox-trigger-icon combo-seta"') +
      '<div class="combo-pop" data-popover aria-hidden="true" popover="manual"><ul class="combo-lista" id="' + id + '-lista" role="listbox"' +
      (o.rotuloId ? ' aria-labelledby="' + EP.esc(o.rotuloId) + '"' : o.rotulo ? ' aria-label="' + EP.esc(o.rotulo) + '"' : "") + "></ul></div>" +
      '<p class="combo-nada" hidden></p><p class="sr" role="status" aria-live="polite"></p>';
    onde.appendChild(caixa);
    var input = caixa.querySelector("input"), lista = caixa.querySelector(".combo-lista"), nada = caixa.querySelector(".combo-nada"), status = caixa.querySelector('[role="status"]');
    var limpa = caixa.querySelector(".combo-limpa"), pop = caixa.querySelector(".combo-pop");
    // sem a "top layer" (navegador antigo): a lista fica embaixo do campo, com z-index acima da barra das abas
    var naTopo = typeof pop.showPopover === "function";
    if (!naTopo) pop.removeAttribute("popover");
    var todos = null, opcoes = null, carregando = null, atual = null, vis = [], ativo = -1, aberto = false, tAviso = null;

    // sem acento, sem maiúscula e sem pontuação ("Santa Bárbara d'Oeste" -> "santa barbara d oeste")
    function chave(s) { return EP.norm(s).replace(/[^a-z0-9]+/g, " ").trim(); }
    function prepara(l) {
      todos = (l || []).map(function (it) { it.v = String(it.v); it.n = chave(it.t); it.nb = " " + chave(it.t + " " + (it.busca || "")); return it; });
      opcoes = todos.filter(function (it) { return !it.ph; });
      return todos;
    }
    if (Array.isArray(o.itens)) prepara(o.itens);
    function carrega() {
      if (todos) return Promise.resolve(todos);
      if (!carregando) carregando = Promise.resolve(typeof o.itens === "function" ? o.itens() : []).then(prepara);
      return carregando;
    }
    // o texto que o campo mostra quando nada foi digitado: o da opção escolhida (o "escolha…" não aparece: é o placeholder)
    function textoDe(it) { return it && !it.ph ? it.t : ""; }
    function padrao() { return (opcoes || []).filter(function (it) { return it.v === ""; })[0] || null; }
    // o × aparece quando há algo para limpar: texto digitado (diferente da opção escolhida) ou, nos filtros, uma escolha
    // diferente da de começo ("Todos os partidos"). Num campo sem opção vazia (o mandato, a cidade aberta), a escolha fica
    function poeLimpa() {
      var p = padrao(), tem = input.value !== "" && (input.value !== textoDe(atual) || (!!p && atual !== p));
      if (limpa.hidden === tem) limpa.hidden = !tem;
      caixa.classList.toggle("com-limpa", tem);
    }
    // cada palavra digitada precisa ser o começo de uma palavra da opção ("bom jesus pi" acha Bom Jesus, Piauí, e não
    // Bom Jesus do Norte, Espírito Santo); se assim não achar nada, vale a palavra em qualquer lugar.
    // Ordem: primeiro o nome que começa igual, depois o nome com uma palavra que começa igual, depois o resto.
    function filtra(q) {
      var qn = chave(q);
      if (!qn) return opcoes.slice();
      var pal = qn.split(" ");
      function junta(inicio) {
        var r = [[], [], []];
        opcoes.forEach(function (it) {
          for (var i = 0; i < pal.length; i++) if (it.nb.indexOf(inicio ? " " + pal[i] : pal[i]) < 0) return;
          r[it.n.indexOf(qn) === 0 ? 0 : (" " + it.n).indexOf(" " + pal[0]) > -1 ? 1 : 2].push(it);
        });
        return r[0].concat(r[1], r[2]);
      }
      var achou = junta(true);
      return achou.length ? achou : junta(false);
    }
    function avisa(t) { clearTimeout(tAviso); tAviso = setTimeout(function () { if (status.textContent !== t) status.textContent = t; }, 450); }
    function marca(k) {
      var lis = lista.querySelectorAll('[role="option"]');
      if (ativo > -1 && lis[ativo]) lis[ativo].classList.remove("ativo", "active");
      ativo = k;
      if (k > -1 && lis[k]) {
        lis[k].classList.add("ativo", "active");
        input.setAttribute("aria-activedescendant", lis[k].id);
        var topo = lis[k].offsetTop, base = topo + lis[k].offsetHeight;
        if (topo < lista.scrollTop) lista.scrollTop = topo - 6;
        else if (base > lista.scrollTop + lista.clientHeight) lista.scrollTop = base - lista.clientHeight + 6;
      } else input.removeAttribute("aria-activedescendant");
    }
    function fecha(restaura) {
      aberto = false;
      escondePop();
      nada.hidden = true;
      ativo = -1;
      caixa.classList.remove("aberto", "acima");
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      if (restaura) input.value = textoDe(atual);
      poeLimpa();
    }
    // abre para baixo; se embaixo não couber (pouco espaço até o fim da tela) e em cima couber mais, abre para cima.
    // A altura acompanha o espaço que sobra (no celular, o teclado da tela diminui a janela visível)
    function escondePop() {
      pop.setAttribute("aria-hidden", "true");
      if (naTopo) { try { pop.hidePopover(); } catch (e) {} }
    }
    function mostraPop() {
      pop.setAttribute("aria-hidden", "false");
      if (naTopo) { try { pop.showPopover(); } catch (e) {} }
    }
    function posiciona() {
      var r = input.getBoundingClientRect(), vv = window.visualViewport, alto = vv ? vv.height : innerHeight;
      var topoFixo = EP.topoFixo ? EP.topoFixo() : (document.querySelector("header.topo") || { getBoundingClientRect: function () { return { bottom: 0 }; } }).getBoundingClientRect().bottom;
      var baixo = alto - r.bottom - 12, cima = r.top - Math.max(0, topoFixo) - 12;
      var acima = baixo < 180 && cima > baixo + 40;
      caixa.classList.toggle("acima", acima);
      pop.setAttribute("data-side", acima ? "top" : "bottom");
      lista.style.maxHeight = Math.max(140, Math.min(360, acima ? cima : baixo)) + "px";
      if (!naTopo) return;
      // na top layer, a posição é a da tela (fixed): logo embaixo (ou em cima) do campo, sem passar da tela pelos lados
      var s = pop.style;
      s.position = "fixed";
      s.margin = "0";
      s.inset = "auto";
      // a largura é medida na hora (sem transição de tamanho, ver css/componentes.css): pelo menos a do campo, no máximo 512 px.
      // Ancorada no campo: começa na borda esquerda dele; se passar da tela, alinha pela borda direita do campo
      var W = document.documentElement.clientWidth || innerWidth;
      s.minWidth = Math.round(Math.min(r.width, W - 16)) + "px";
      s.maxWidth = Math.round(Math.min(W - 16, Math.max(r.width, 512))) + "px";
      s.width = "max-content";
      var larg = Math.min(Math.max(r.width, pop.offsetWidth), W - 16);
      s.width = Math.round(larg) + "px";
      var x = r.left;
      if (x + larg > W - 8) x = r.right - larg;
      s.left = Math.round(Math.max(8, Math.min(x, W - 8 - larg))) + "px";
      if (acima) { s.top = "auto"; s.bottom = Math.round(innerHeight - r.top + 6) + "px"; }
      else { s.bottom = "auto"; s.top = Math.round(r.bottom + 6) + "px"; }
    }
    // a lista acompanha o campo quando a página rola; se o campo sai da tela (ou some embaixo da barra), a lista fecha.
    // Logo depois de o campo receber o foco, a página ainda pode estar rolando (suave) até ele: aí a lista não fecha
    var focadoEm = 0;
    input.addEventListener("focus", function () { focadoEm = Date.now(); });
    window.addEventListener("scroll", function () {
      if (!aberto) return;
      var r = input.getBoundingClientRect();
      if ((r.bottom < 0 || r.top > innerHeight) && Date.now() - focadoEm > 1200) fecha(true); else posiciona();
    }, { passive: true, capture: true });
    function mostra(l) {
      vis = l.slice(0, max);
      ativo = -1;
      if (!vis.length) {
        fecha(false);
        lista.innerHTML = "";
        nada.hidden = false;
        nada.textContent = o.nada || EP.tr("Nada encontrado com esse nome. Confira se está escrito certo.", "Nothing found with that name. Check the spelling.");
        avisa(nada.textContent);
        return;
      }
      nada.hidden = true;
      lista.innerHTML = vis.map(function (it, k) {
        var ja = atual && it.v === atual.v;
        return '<li role="option" id="' + id + "-o" + k + '" data-k="' + k + '" data-value="' + EP.esc(it.v) + '" aria-selected="' + !!ja + '"' + (ja ? ' class="escolhido"' : "") + (it.lang ? ' lang="' + EP.esc(it.lang) + '"' : "") + ">" +
          '<span class="combo-t">' + EP.esc(it.t) + "</span>" + (it.sub ? "<small>" + EP.esc(it.sub) + "</small>" : "") + "</li>";
      }).join("");
      lista.scrollTop = 0;
      mostraPop();
      aberto = true;
      caixa.classList.add("aberto");
      input.setAttribute("aria-expanded", "true");
      posiciona();
      var n = l.length;
      avisa((n > vis.length ? EP.tr(EP.num(n) + " opções. Mostrando as " + vis.length + " primeiras; continue digitando para achar mais rápido.",
        EP.num(n) + " options. Showing the first " + vis.length + "; keep typing to narrow it down.") :
        n === 1 ? EP.tr("1 opção.", "1 option.") : EP.tr(EP.num(n) + " opções.", EP.num(n) + " options.")) + " " + EP.tr("Use as setas para escolher.", "Use the arrow keys to choose."));
    }
    function abre(q, marcaPrimeiro) {
      return carrega().then(function () {
        if (chave(q || "").length < min) {
          fecha(false);
          if (o.dica) { nada.hidden = false; nada.textContent = o.dica; }
          return;
        }
        mostra(filtra(q || ""));
        if (!vis.length) return;
        var k = marcaPrimeiro ? 0 : -1;
        if (!marcaPrimeiro && atual) vis.forEach(function (it, j) { if (it.v === atual.v) k = j; });
        marca(k);
      });
    }
    function escolhe(it, silencioso) {
      atual = it || null;
      input.value = textoDe(it);
      fecha(false);
      if (!silencioso && it && o.aoEscolher) o.aoEscolher(it);
    }
    function acha(v) { return (todos || []).filter(function (it) { return it.v === String(v); })[0] || null; }
    // o campo mostra exatamente a opção escolhida (sem nada digitado por cima)
    function mostraEscolhido() { return !!atual && input.value === textoDe(atual) && input.value !== ""; }
    // ao sair do campo: aceita o texto se for igual a uma opção; campo vazio volta para a opção "todos" (valor vazio), se houver
    function sai() {
      if (!aberto && input.value === textoDe(atual)) return;
      var qn = chave(input.value);
      var igual = (opcoes || []).filter(function (it) { return qn ? it.n === qn : it.v === ""; });
      if (igual.length === 1 && (!atual || igual[0].v !== atual.v)) escolhe(igual[0]);
      else if (!qn && !igual.length && atual && !atual.ph) { var ph = acha(""); escolhe(ph && ph.ph ? ph : null, false); }
      else fecha(true);
    }

    // com uma opção escolhida, a primeira letra digitada começa uma busca nova e o primeiro "apagar" limpa o campo (como num
    // select: ninguém quer "Bahiap" nem "Bahi"), sem precisar deixar o texto todo selecionado (azul) ao entrar no campo
    input.addEventListener("beforeinput", function (e) {
      if (!mostraEscolhido()) return;
      var apaga = /^delete/.test(e.inputType || "");
      if (!apaga && !((e.inputType === "insertText" || e.inputType === "insertReplacementText") && e.data)) return;
      e.preventDefault();
      input.value = apaga ? "" : e.data;
      input.setSelectionRange(input.value.length, input.value.length);
      abre(input.value, true);
      poeLimpa();
    });
    input.addEventListener("input", function () { abre(input.value, true); poeLimpa(); });
    // no celular (toque), o campo sobe para perto do topo ao receber o foco: a lista abre embaixo, com espaço, mesmo com o teclado
    // da tela aberto
    input.addEventListener("focus", function () {
      var toque = navigator.maxTouchPoints > 0 || (window.matchMedia && matchMedia("(pointer: coarse)").matches);
      if (!toque || innerWidth > 900) return;
      var r = input.getBoundingClientRect(), topo = document.querySelector("header.topo"), h = topo ? topo.getBoundingClientRect().bottom : 0;
      var fixo = EP.topoFixo ? EP.topoFixo() : h;
      if (r.top > innerHeight * 0.4) {
        window.scrollBy({ top: r.top - fixo - 16, behavior: "instant" });
        // o campo andou embaixo do dedo: o navegador não manda o "click" desse toque; a lista abre aqui
        setTimeout(function () { if (!aberto && document.activeElement === input) abreDoClique(); }, 60);
      }
    });
    function abreDoClique() {
      if (aberto) return;
      if (mostraEscolhido() || input.value === "") abre("", false); else abre(input.value, true);
    }
    input.addEventListener("click", abreDoClique);
    input.addEventListener("keydown", function (e) {
      var k = e.key;
      if (k === "ArrowDown" || k === "ArrowUp") {
        e.preventDefault();
        if (!aberto) {
          abre(mostraEscolhido() ? "" : input.value, false).then(function () { if (aberto && ativo < 0) marca(k === "ArrowDown" ? 0 : vis.length - 1); });
          return;
        }
        if (vis.length) marca(ativo < 0 ? (k === "ArrowDown" ? 0 : vis.length - 1) : (ativo + (k === "ArrowDown" ? 1 : -1) + vis.length) % vis.length);
      } else if ((k === "Home" || k === "End") && aberto && ativo > -1 && vis.length) {
        e.preventDefault();
        marca(k === "Home" ? 0 : vis.length - 1);
      } else if (k === "Enter") {
        if (!aberto) return;
        e.preventDefault();
        if (ativo > -1) escolhe(vis[ativo]);
        else if (vis.length === 1) escolhe(vis[0]);
      } else if (k === "Escape") {
        if (aberto || input.value !== textoDe(atual)) { e.preventDefault(); e.stopPropagation(); fecha(true); }
      } else if (k === "Tab") sai();
    });
    input.addEventListener("blur", function () { setTimeout(function () { if (document.activeElement !== input && document.activeElement !== limpa) sai(); }, 150); });
    lista.addEventListener("mousedown", function (e) { e.preventDefault(); });
    lista.addEventListener("click", function (e) {
      var li = e.target.closest ? e.target.closest('[role="option"]') : null;
      if (li) escolhe(vis[+li.getAttribute("data-k")]);
    });
    // ×: volta para a opção de começo ("Todos os partidos"), ou deixa o campo vazio; o foco fica no campo, com a lista aberta
    limpa.addEventListener("mousedown", function (e) { e.preventDefault(); });
    limpa.addEventListener("click", function () {
      carrega().then(function () {
        var p = padrao();
        if (p && atual !== p) escolhe(p);
        else if (!p && atual) { var ph = acha(""); if (ph && ph.ph && atual !== ph) { atual = ph; if (o.aoEscolher) o.aoEscolher(ph); } }
        input.value = "";
        input.focus();
        abre("", false);
        poeLimpa();
        avisa(EP.tr("Campo limpo.", "Field cleared."));
      });
    });
    window.addEventListener("resize", function () { if (aberto) posiciona(); });

    var api = {
      input: input, caixa: caixa,
      valor: function () { return atual && !atual.ph ? atual.v : ""; },
      escolhe: function (v, silencioso) { return carrega().then(function () { escolhe(acha(v), silencioso); poeLimpa(); }); },
      foco: function () { input.focus(); }
    };
    if (o.valor != null && o.valor !== "") api.escolhe(o.valor, true);
    else if (todos && acha("")) escolhe(acha(""), true);
    poeLimpa();
    return api;
  };
  EP.comboSelect = function (sel, o) {
    if (!sel) return null;
    if (sel._combo) return sel._combo;
    o = o || {};
    var itens = [].map.call(sel.options, function (op, i) {
      var t = (op.textContent || "").trim();
      // o "Escolha um estado…" de um select obrigatório não é uma opção: vira o placeholder do campo
      var ph = i === 0 && op.value === "" && (sel.required || op.hasAttribute("data-placeholder") || /…$/.test(t));
      return { v: op.value, t: t, lang: op.getAttribute("lang"), sub: op.getAttribute("data-sub"), busca: op.getAttribute("data-busca"), ph: ph };
    });
    var onde = document.createElement("div");
    onde.className = "combo-sel";
    sel.parentNode.insertBefore(onde, sel);
    var lbl = sel.id ? document.querySelector('label[for="' + sel.id + '"]') : null;
    if (lbl && !lbl.id) lbl.id = sel.id + "-rotulo";
    var ph = itens[0] && itens[0].ph ? itens[0].t : null;
    var c = EP.combo(onde, {
      id: sel.id ? sel.id + "-campo" : null, rotulo: lbl ? null : sel.getAttribute("aria-label"), rotuloId: lbl ? lbl.id : null,
      itens: itens, valor: sel.value, max: o.max || 100, placeholder: o.placeholder || ph || EP.tr("Digite para procurar…", "Type to search…"),
      aoEscolher: function (it) {
        if (sel.value !== it.v) { sel.value = it.v; sel.dispatchEvent(new Event("change", { bubbles: true })); }
        if (o.aoEscolher) o.aoEscolher(it);
      }
    });
    if (lbl) lbl.htmlFor = c.input.id;
    sel.hidden = true;
    sel.style.display = "none";
    sel.required = false;
    sel.tabIndex = -1;
    sel._combo = c;
    return c;
  };
  EP.comboSync = function (sel) { if (sel && sel._combo) sel._combo.escolhe(sel.value, true); };

  // ---------------------------------------------------------------- compartilhar o site
  // Mesma janela na página inicial e no fim do mapa. No inglês, o texto e o link vão em inglês (?lang=en).
  EP.SITE = "https://entendapolitica.vercel.app/";
  EP.compartilhar = function (origem) {
    var TXT = EP.tr("A política do Brasil explicada de um jeito fácil: como funciona, quem está no poder e o que cada político propôs. Tudo com fonte:",
      "Brazilian politics made easy: how it works, who is in power and what each politician proposed. Everything with sources:");
    var novaAba = '<span class="sr"> ' + EP.tr("(abre em outra aba)", "(opens in a new tab)") + "</span>";
    function link(canal) { return EP.SITE + "?" + (EP.en ? "lang=en&" : "") + "utm_source=" + canal + "&utm_medium=compartilhar" + (origem ? "&utm_campaign=" + origem : ""); }
    EP.track("compartilhar_abriu", { origem: origem || "" });
    if (navigator.share && /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent)) {
      navigator.share({ title: document.title, text: TXT, url: link("celular") }).catch(function () {});
      return;
    }
    var wa = "https://wa.me/?text=" + encodeURIComponent(TXT + " " + link("whatsapp"));
    var tg = "https://t.me/share/url?url=" + encodeURIComponent(link("telegram")) + "&text=" + encodeURIComponent(TXT);
    var fb = "https://www.facebook.com/sharer/sharer.php?u=" + encodeURIComponent(link("facebook"));
    function op(url, ic, nome, classe, estilo) {
      return '<a class="btn ' + classe + '"' + (estilo ? ' style="' + estilo + '"' : "") + ' href="' + EP.esc(url) + '" target="_blank" rel="noopener"><span aria-hidden="true">' + ic + " </span>" + nome + novaAba + "</a>";
    }
    EP.abrir('<span aria-hidden="true">📤 </span>' + EP.tr("Compartilhar o site", "Share the site"),
      "<p>" + EP.tr("Escolha por onde mandar.", "Choose how to send it.") + "</p>" +
      '<div class="opcoes-comp">' +
      op(wa, "💬", "WhatsApp", "", "background:#25d366;color:#08311a;box-shadow:0 5px 0 #179a4a") +
      op(tg, "✈️", "Telegram", "claro") + op(fb, "👍", "Facebook", "claro") +
      '<button class="btn bege" type="button" id="copiar-link"><span aria-hidden="true">🔗 </span>' + EP.tr("Copiar o link", "Copy the link") + "</button>" +
      '<p class="link-copia" id="link-copia" hidden></p><p class="sr" id="aviso-copia" role="status" aria-live="polite"></p></div>');
    document.getElementById("copiar-link").addEventListener("click", function () {
      var u = link("link"), b = this, caixa = document.getElementById("link-copia"), aviso = document.getElementById("aviso-copia");
      function ok() {
        b.innerHTML = '<span aria-hidden="true">✅ </span>' + EP.tr("Link copiado! É só colar onde quiser.", "Link copied! Just paste it wherever you want.");
        aviso.textContent = EP.tr("Link copiado.", "Link copied.");
      }
      function mostra() {
        caixa.hidden = false;
        caixa.textContent = u;
        b.textContent = EP.tr("Copie o link abaixo:", "Copy the link below:");
        aviso.textContent = EP.tr("Não deu para copiar sozinho. O link está escrito abaixo do botão.", "It could not be copied automatically. The link is written below the button.");
      }
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(u).then(ok, mostra);
      else mostra();
    });
  };

  // ---------------------------------------------------------------- memória da página (ui-r9): busca, filtros, listas abertas e rolagem
  // A pesquisa e os filtros ficam no endereço, para o Voltar do navegador trazer tudo de volta e para dar para compartilhar
  // (brasil.html?q=silva, brasil.html?senado-partido=PT#senado). O que não precisa ir no endereço (quantos "Mostrar mais" ou
  // "Ver todos" estavam abertos, a rolagem) fica em history.state, que o navegador guarda em cada passo do histórico, também
  // quando a página é carregada de novo ao voltar (sem o "bfcache").
  function estadoHist() { var s = history.state; return s && typeof s === "object" ? s : {}; }
  EP.memo = {
    url: function (k) { try { return new URLSearchParams(location.search).get(k); } catch (e) { return null; } },
    poeUrl: function (k, v) {
      try {
        var u = new URL(location.href);
        if (v == null || v === "") u.searchParams.delete(k); else u.searchParams.set(k, v);
        if (u.href !== location.href) history.replaceState(history.state, "", u.pathname + u.search + u.hash);
      } catch (e) {}
      if (EP.atualizaLinksIdioma) EP.atualizaLinksIdioma();
    },
    le: function (k) { var s = estadoHist().ep; return s && Object.prototype.hasOwnProperty.call(s, k) ? s[k] : null; },
    grava: function (k, v) {
      try {
        var s = Object.assign({}, estadoHist()), ep = Object.assign({}, s.ep || {});
        if (v == null) delete ep[k]; else ep[k] = v;
        s.ep = ep;
        history.replaceState(s, "", location.href);
      } catch (e) {}
    },
    // a página foi aberta pelo Voltar/Avançar do navegador (ou recarregada): vale trazer de volta o que estava aberto
    voltando: function () {
      var t = "";
      try { t = (performance.getEntriesByType("navigation")[0] || {}).type || ""; } catch (e) {}
      return t === "back_forward" || t === "reload";
    }
  };
  // a rolagem: guardada ao sair da página (e ao clicar num link); ao voltar, se o navegador não conseguiu pôr a página no mesmo
  // lugar (o conteúdo chega depois), põe quando ela crescer o bastante. Para se a pessoa rolar, tocar ou usar o teclado.
  function guardaRolagem() { EP.memo.grava("y", Math.round(window.scrollY)); }
  window.addEventListener("pagehide", guardaRolagem);
  document.addEventListener("click", function (e) { if (e.target.closest && e.target.closest("a[href]")) guardaRolagem(); }, true);
  function voltaRolagem() {
    var y = EP.memo.le("y");
    if (!y || !EP.memo.voltando()) return;
    var parou = false, obs = null, ro = null, prazo = null;
    function fim() {
      parou = true;
      if (obs) obs.disconnect();
      if (ro) ro.disconnect();
      clearTimeout(prazo);
      ["wheel", "touchstart", "keydown", "mousedown"].forEach(function (t) { window.removeEventListener(t, fim, true); });
    }
    function tenta() {
      if (parou) return;
      if (Math.abs(window.scrollY - y) < 4) return;
      if (raizDoc.scrollHeight - innerHeight >= y) window.scrollTo({ top: y, behavior: "instant" });
    }
    ["wheel", "touchstart", "keydown", "mousedown"].forEach(function (t) { window.addEventListener(t, fim, { capture: true, passive: true }); });
    obs = new MutationObserver(tenta);
    obs.observe(document.body, { childList: true, subtree: true });
    if ("ResizeObserver" in window) { ro = new ResizeObserver(tenta); ro.observe(document.body); }
    tenta();
    prazo = setTimeout(fim, 6000);
  }

  // ---------------------------------------------------------------- voltar para a lista de onde a pessoa veio
  // Ao abrir o perfil de alguém (pessoa.html), esta aba guarda de onde veio: a página, a seção e quem foi aberto.
  // O "Voltar" do perfil usa isso (e não manda sempre para o Brasil). Ao voltar, a lista rola até quem foi aberto e põe o foco
  // nele: quem usa teclado ou leitor de tela continua de onde parou.
  // "estado.html?uf=BA": arquivo e parâmetros do endereço, sem o idioma nem marcas de campanha (a página inicial vira "index.html")
  EP.endereco = function (u) {
    var x = new URL(u || location.href, location.href);
    ["lang", "utm_source", "utm_medium", "utm_campaign", "ver"].forEach(function (k) { x.searchParams.delete(k); });
    var q = x.searchParams.toString();
    return (x.pathname.split("/").pop() || "index.html") + (q ? "?" + q : "");
  };
  EP.leVolta = function () { try { return JSON.parse(sessionStorage.getItem("ep-volta") || "null"); } catch (e) { return null; } };
  EP.gravaVolta = function (v) {
    try { if (v) sessionStorage.setItem("ep-volta", JSON.stringify(v)); else sessionStorage.removeItem("ep-volta"); } catch (e) {}
  };
  function voltaNaLista(daMemoria) {
    var v = EP.leVolta();
    if (!v || v.pagina !== EP.endereco()) { if (!daMemoria) voltaRolagem(); return; }
    var nav = {};
    try { nav = performance.getEntriesByType("navigation")[0] || {}; } catch (e) {}
    EP.gravaVolta(null);
    if (!daMemoria && nav.type !== "back_forward" && !(v.voltando && Date.now() - v.voltando < 120000)) { voltaRolagem(); return; }
    // página com abas (js/abas.js): abre a aba da seção de onde a pessoa saiu; as listas com resumo (js/casa.js, verTodos)
    // mostram a lista inteira se a pessoa estava depois do resumo. Nas páginas sem abas, nada muda.
    if (v.secao && EP.mostraSecao) EP.mostraSecao(v.secao);
    EP.voltaAlvo = { secao: v.secao || "", id: v.id || "", t: Date.now() };
    try { window.dispatchEvent(new CustomEvent("ep-volta", { detail: EP.voltaAlvo })); } catch (e) {}
    var sel = 'a[href="pessoa.html?id=' + encodeURIComponent(v.id || "") + '"]', obs = null, prazo = null, mexeu = false;
    // se a pessoa já começou a rolar ou a usar o teclado, não mexe em nada
    ["wheel", "touchstart", "keydown", "mousedown"].forEach(function (t) { window.addEventListener(t, function () { mexeu = true; }, { once: true, passive: true }); });
    function acha() {
      var s = v.secao && document.getElementById(v.secao);
      var a = (s && s.querySelector(sel)) || document.querySelector(sel);
      return a && a.getClientRects().length ? a : null;
    }
    function fim(a) {
      if (obs) obs.disconnect();
      clearTimeout(prazo);
      if (mexeu) return;
      if (a) {
        var r = a.getBoundingClientRect(), cobre = EP.topoFixo ? EP.topoFixo() + 8 : 70;  // com abas, a barra presa no topo também cobre
        // voltando da memória do navegador, a página já está onde estava: só devolve o foco
        // (site-d-r14) deslizando até o cartão; voltando da memória, a página já está no lugar (nada se mexe)
        if (!daMemoria && (r.top < cobre || r.bottom > innerHeight)) EP.rolaAte(a, "center");
        a.focus({ preventScroll: true });
      } else if (!daMemoria) {
        var s = v.secao && document.getElementById(v.secao);
        if (s) EP.rolaAte(s);
        else if (v.y) window.scrollTo({ top: v.y, behavior: "instant" });
      }
    }
    var a0 = acha();
    if (a0 || daMemoria) { fim(a0); return; }
    // a lista é montada depois que os dados chegam: espera a pessoa aparecer (no máximo 6 s)
    obs = new MutationObserver(function () { var a = acha(); if (a) fim(a); });
    obs.observe(document.body, { childList: true, subtree: true });
    prazo = setTimeout(function () { fim(acha()); }, 6000);
  }
  if (!/(^|\/)pessoa\.html$/.test(location.pathname)) {
    document.addEventListener("click", function (e) {
      var a = e.target.closest ? e.target.closest('a[href^="pessoa.html?"]') : null;
      if (!a || e.button || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
      var sec = a.closest("section[id]");
      EP.gravaVolta({ pagina: EP.endereco(), secao: sec ? sec.id : a.getAttribute("data-secao") || "", id: new URLSearchParams(a.getAttribute("href").split("?")[1]).get("id") || "",
        y: Math.round(window.scrollY) });
    }, true);
    window.addEventListener("pageshow", function (e) { voltaNaLista(e.persisted); });
  } else window.addEventListener("pageshow", function (e) { if (!e.persisted) voltaRolagem(); });

  // ---------------------------------------------------------------- analytics (desligado até ter ID)
  EP.track = function (evento, params) {
    try { if (window.gtag) window.gtag("event", evento, params || {}); } catch (e) {}
  };
  EP.fundo3d = function (lista, alvo) {
    if (!window.TRES || !alvo || A11Y.contraste) return;
    alvo.insertAdjacentHTML("afterbegin", TRES.formas(lista, "fundo-fixo"));
    // ui-r9: os enfeites ficam atrás de tudo (z-index -1) e só nas margens livres, dos lados da coluna do conteúdo (.miolo,
    // 1080 px); onde não cabem (celular, tablet, janela estreita), somem. Assim nunca ficam por cima de texto, campo ou botão.
    var caixa = alvo.querySelector(".formas.fundo-fixo");
    if (!caixa) return;
    var formas = [].slice.call(caixa.querySelectorAll(".forma"));
    function poe() {
      // site-d-r13: a coluna do conteúdo começa depois do menu lateral (no computador): as margens livres são as dela
      var lado = document.getElementById("casca-lado"), x0 = lado && MQ_LADO.matches ? lado.getBoundingClientRect().right : 0;
      var w = raizDoc.clientWidth - x0, h = innerHeight, livre = (w - EP.LARGURA_CONTEUDO) / 2;
      var topo = document.querySelector("header.topo"), cima = topo ? Math.max(0, topo.getBoundingClientRect().bottom) : 0;
      formas.forEach(function (f, i) {
        var s = lista[i][3], esquerda = parseFloat(lista[i][1]) < 50, cabe = livre >= s + 2 * EP.FOLGA_ENFEITE && h > 360;
        f.hidden = !cabe;
        if (!cabe) return;
        var x = x0 + (esquerda ? (livre - s) / 2 : w - livre + (livre - s) / 2);
        var y = Math.min(Math.max(cima + EP.FOLGA_ENFEITE, parseFloat(lista[i][2]) / 100 * h), h - s - EP.FOLGA_ENFEITE);
        f.style.left = Math.round(x) + "px";
        f.style.top = Math.round(y) + "px";
      });
    }
    poe();
    window.addEventListener("resize", poe);
    window.addEventListener("ep-a11y", poe);
  };
  // tamanho dos resumos das listas grandes nas páginas com abas (Brasil, estado e cidade): quantas pessoas aparecem antes do
  // "Ver todos" em cada Casa e quantos ministérios antes do "Ver todos os ministérios". Para mudar, é só trocar aqui.
  EP.RESUMO_CASA = 12;
  EP.RESUMO_MINISTERIOS = 8;
  // largura da coluna do conteúdo (a mesma do .miolo em css/base.css) e a distância mínima entre um enfeite e ela
  EP.LARGURA_CONTEUDO = 1080;
  EP.FOLGA_ENFEITE = 16;

  // a barra do topo já está na página (este arquivo vem no fim do <body>): os menus são montados já, antes de o Basecoat
  // procurar os componentes (no DOMContentLoaded)
  var topoMontado = false;
  if (document.querySelector("header.topo .ferramentas-topo")) { montaCasca(); montaTopo(); topoMontado = true; }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ligaTopo);
  else ligaTopo();
})();
