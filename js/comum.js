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
    var b = document.getElementById("btn-letra");
    if (b) {
      var maior = (A11Y.escala || 1) >= ESCALAS[ESCALAS.length - 1];
      b.textContent = maior ? "A−" : "A+";
      b.setAttribute("aria-label", (maior ? "A− " : "A+ ") + (maior ? EP.tr("voltar a letra ao tamanho normal", "reset text size") : EP.tr("aumentar a letra", "make text bigger")));
      b.title = b.getAttribute("aria-label");
    }
  }
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

  // ---------------------------------------------------------------- texto
  EP.esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  // **negrito** -> <b>negrito</b> (o resto é escapado)
  EP.md = function (s) { return EP.esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>"); };
  EP.norm = function (s) {
    return String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
  };
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
    "vereador": "City Councilor", "vereadora": "City Councilor", "ministro": "Minister", "ministra": "Minister"
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
    if (EP.en) return { eleito: "Elected in 2026", reeleito: "Re-elected in 2026", "segundo-turno": curto ? "Runoff in 2026" : "In the runoff on October 25, 2026",
      "nao-eleito": "Not elected in 2026", suplente: "Alternate in 2026", candidato: "Candidate in 2026", "nao-concorreu": "Did not run in 2026" }[sit] || "2026";
    return { eleito: "Eleit" + a + " em 2026", reeleito: "Reeleit" + a + " em 2026", "segundo-turno": curto ? "2º turno em 2026" : "Disputa o 2º turno em 25/10/2026",
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
    return '<a class="pessoa-card" href="pessoa.html?id=' + encodeURIComponent(p.id) + '">' + EP.av(p.foto, p.nome) +
      "<b>" + EP.esc(p.nome) + "</b>" + (extra ? "<small>" + EP.esc(extra) + "</small>" : "") + (linha2 ? "<small>" + EP.esc(linha2) + "</small>" : "") +
      EP.chip2026(p.eleicao2026, p.genero) + "</a>";
  };

  // ---------------------------------------------------------------- janela (diálogo com foco preso)
  var fundo = null, focoAntes = null;
  var FOCAVEIS = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';
  function montaJanela() {
    if (fundo) return;
    fundo = document.createElement("div");
    fundo.className = "janela-fundo";
    fundo.hidden = true;
    fundo.innerHTML = '<div class="janela" role="dialog" aria-modal="true" aria-labelledby="janela-titulo">' +
      '<div class="janela-cab"><h2 id="janela-titulo"></h2><button class="fechar" type="button" data-fechar>✕ ' + EP.tr("Fechar", "Close") + "</button></div>" +
      '<div class="janela-corpo"></div></div>';
    document.body.appendChild(fundo);
    fundo.addEventListener("click", function (e) {
      if (e.target === fundo || (e.target.closest && e.target.closest("[data-fechar]"))) EP.fechar();
    });
    fundo.addEventListener("keydown", function (e) {
      if (e.key !== "Tab") return;
      var f = [].filter.call(fundo.querySelectorAll(FOCAVEIS), function (x) { return x.offsetParent !== null; });
      if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    });
  }
  EP.abrir = function (titulo, html) {
    montaJanela();
    EP.calar();
    if (fundo.hidden) focoAntes = document.activeElement;
    fundo.querySelector("#janela-titulo").innerHTML = titulo;
    fundo.querySelector(".janela-corpo").innerHTML = html;
    fundo.hidden = false;
    fundo.querySelector(".janela").scrollTop = 0;
    document.body.style.overflow = "hidden";
    fundo.querySelector(".fechar").focus();
  };
  EP.fechar = function () {
    if (!fundo || fundo.hidden) return;
    EP.calar();
    fundo.hidden = true;
    document.body.style.overflow = "";
    if (focoAntes && focoAntes.focus) focoAntes.focus();
  };
  EP.janelaAberta = function () { return !!(fundo && !fundo.hidden); };
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
    c.querySelectorAll(".nao-ler,[aria-hidden='true'],svg,script,style,button.fechar,.formas,.sr").forEach(function (n) { n.remove(); });
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
    if (EP.janelaAberta()) return fundo.querySelector(".janela");
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
      var k = t.getAttribute("data-a11y"), v = !A11Y[k];
      EP.a11y(k, v);
      t.setAttribute("aria-checked", String(v));
      return;
    }
    var acao = t.getAttribute("data-a11y-acao");
    if (acao === "ouvir") { EP.fechar(); setTimeout(EP.ouvir, 50); }
    else if (acao === "libras") { EP.fechar(); EP.libras(); }
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

  // ---------------------------------------------------------------- barra do topo
  function ligaTopo() {
    EP.aplicaIdioma();
    var bl = document.getElementById("btn-letra");
    if (bl) bl.addEventListener("click", EP.trocaLetra);
    var bo = document.getElementById("btn-ouvir");
    if (bo) {
      if (!podeFalar) bo.hidden = true;
      bo.setAttribute("aria-label", EP.tr("Ouvir esta página em voz alta", "Listen to this page"));
      bo.addEventListener("click", EP.ouvir);
    }
    var lb = document.getElementById("btn-libras");
    if (lb) { if (EP.en) lb.hidden = true; else lb.addEventListener("click", EP.libras); }
    var ba = document.getElementById("btn-a11y");
    if (ba) {
      ba.setAttribute("aria-label", EP.tr("Opções de acessibilidade", "Accessibility options"));
      ba.addEventListener("click", EP.menuA11y);
    }
    var bi = document.getElementById("btn-idioma");
    if (bi) {
      bi.href = EP.urlIdioma(EP.en ? "pt" : "en");
      bi.lang = EP.en ? "pt-BR" : "en";
      bi.removeAttribute("aria-label");
      bi.innerHTML = '<span aria-hidden="true">🌐 </span>' + (EP.en ? "PT" : "EN") + '<span class="sr"> ' + (EP.en ? "(ler em português)" : "(read in English)") + "</span>";
      bi.addEventListener("click", function (e) { e.preventDefault(); EP.trocaIdioma(EP.en ? "pt" : "en"); });
    }
    aplicaA11y();
    avisoIdioma();
  }

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

  // ---------------------------------------------------------------- analytics (desligado até ter ID)
  EP.track = function (evento, params) {
    try { if (window.gtag) window.gtag("event", evento, params || {}); } catch (e) {}
  };
  EP.fundo3d = function (lista, alvo) {
    if (!window.TRES || !alvo || A11Y.contraste) return;
    alvo.insertAdjacentHTML("afterbegin", TRES.formas(lista, "fundo-fixo"));
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ligaTopo);
  else ligaTopo();
})();
