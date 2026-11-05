/* ====== Entenda Política: mandatos anteriores ======
   O campo "Ver outro mandato" (lista com busca, EP.combo) nas páginas do Brasil, do estado e da cidade, e os mandatos do
   passado: quem foi ELEITO para cada mandato, segundo o TSE (dados/historico/, gerados por scripts/historico.py, que roda à mão).
   Por padrão a página mostra hoje; com ?mandato=<ano de início> (ex.: brasil.html?mandato=2019) ela mostra o passado.
   Qual mandato é o de hoje sai das datas de posse do índice (dados/historico/indice.json), nunca de um ano escrito aqui.

   mandatos-r11 (pedido do Lucas, 3/11): todo mandato tem o MESMO layout da página de hoje (as mesmas abas, na mesma ordem, os
   mesmos cartões, plenário, partidos, filtros e resumos com "Ver todos"); só os dados mudam. A página (js/brasil.js, estado.js,
   cidade.js) monta o mesmo esqueleto e as abas (js/abas.js); daqui vêm só os dados do passado. Uma faixa amarela presa embaixo
   das abas diz qual mandato está à vista ("Voltar para hoje"), como no perfil (css/mandato.css). Onde o site não tem o dado
   daquele período, a aba fica no mesmo lugar e diz isso em texto simples (H.semDados).

   EP.hist.param()                              "2019" ou null
   EP.hist.seletor(lugar, nivel, escolhido, fut) monta o campo dentro de "lugar" (nivel: "brasil" | "estados" | "cidades")
   EP.hist.url(id)                              o endereço da mesma página em outro mandato (null = hoje), na mesma aba
   EP.hist.faixa(txt)                           a faixa amarela "Você está vendo: <txt> · Voltar para hoje" (embaixo das abas)
   EP.hist.nota(html)                           o aviso em cima das abas (de onde vêm os dados daquele mandato)
   EP.hist.semDados(ic, html, links)            o quadro de uma aba sem dados daquele mandato; links = EP.hist.link(...)
   EP.hist.votacoesSemDados(futuro)             a aba "Como votaram" de um mandato que não é o de hoje
   EP.hist.brasil(id, o)                        preenche a página do Brasil (js/brasil.js já montou as abas); o.abre = quandoAbrir
   EP.hist.estado(uf, id, o)                    preenche a página do estado (js/estado.js); o.quando, o.resumo
   EP.hist.cidade(caixa, ibge, uf, id, o)       a cidade no passado (js/cidade.js); o.esqueleto monta a página, o.pronto roda no fim
   Se o mandato pedido não é do passado (é o de hoje, ainda não começou ou não existe), a página volta para hoje. */
(function () {
  "use strict";
  var EP = window.EP;
  if (!EP) return;
  var D = EP.trd, esc = EP.esc;
  var H = (EP.hist = {});
  var BASE = "dados/historico/";
  var CF = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm";

  // ---------------------------------------------------------------- mandatos
  H.param = function () { var m = /^\d{4}$/.exec(EP.param("mandato") || ""); return m ? m[0] : null; };
  // hoje em Brasília (UTC-3), "AAAA-MM-DD"
  H.hoje = function () { return new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10); };

  function rotulo(m) { return EP.tr(m.rotulo, m.rotulo_en); }
  function periodo(m) { return EP.tr("de " + m.rotulo, m.rotulo_en); }

  // { lista: mandatos que já começaram (do mais novo para o mais velho), atual: o de hoje }
  H.mandatos = function (nivel) {
    return EP.json(BASE + "indice.json").then(function (ind) {
      var hoje = H.hoje();
      var todos = (ind[nivel] || []).slice().sort(function (a, b) { return a.inicio < b.inicio ? 1 : -1; });
      var l = todos.filter(function (m) { return m.inicio <= hoje; });
      var atual = l.filter(function (m) { return hoje < m.fim; })[0] || null;
      if (!atual && l.length) {
        // já começou um mandato que ainda não está no histórico: "hoje" é ele (a página de hoje já mostra quem está lá)
        var a = +l[0].fim.slice(0, 4);
        atual = { id: String(a), inicio: l[0].fim, novo: true, rotulo: a + " a " + (a + 3), rotulo_en: a + "–" + (a + 3) };
        l.unshift(atual);
      }
      return { lista: l, atual: atual, indice: ind, todos: todos };
    });
  };
  // o mandato pedido, se for do passado (senão, null)
  function doPassado(r, id) {
    return r.lista.filter(function (m) { return m.id === id && m !== r.atual && !m.novo; })[0] || null;
  }
  // a aba aberta (js/abas.js), para continuar nela depois de trocar de mandato
  function abaAberta() { var a = EP.abas && EP.abas.ativa && EP.abas.ativa(); return a ? "#" + a : ""; }
  // mesmo endereço, com outro mandato (null = hoje), na mesma aba. Fica só o que diz qual é a página (uf, ibge e lang): os
  // filtros de uma lista (EP.memo) não passam de um mandato para outro (são listas diferentes)
  H.url = function (id, semAba) {
    var u = new URL(location.href), n = new URL(u.pathname, location.href);
    ["uf", "ibge", "lang"].forEach(function (k) { var v = u.searchParams.get(k); if (v) n.searchParams.set(k, v); });
    if (id) n.searchParams.set("mandato", id);
    var q = n.searchParams.toString();
    return (n.pathname.split("/").pop() || "index.html") + (q ? "?" + q : "") + (semAba ? "" : abaAberta());
  };
  function paraHoje() { location.replace(H.url(null, true) + location.hash); }

  // ---------------------------------------------------------------- campo "Ver outro mandato"
  var nSel = 0;
  // futuro: (opcional) promessa de { v, t } com o próximo mandato (eleitos ainda sem posse; js/proximos.js), que entra no topo
  H.seletor = function (lugar, nivel, escolhido, futuro) {
    if (!lugar) return Promise.resolve(null);
    return Promise.all([H.mandatos(nivel), futuro || null]).then(function (x) {
      var r = x[0], fut = x[1];
      // o próximo mandato só aparece antes de começar (depois da posse, ele já é o atual)
      if (fut && r.atual && r.atual.id >= fut.v) fut = null;
      if (!r.atual || r.lista.length + (fut ? 1 : 0) < 2) { lugar.hidden = true; return r; }
      var id = "mandato-" + (++nSel), desde = r.lista[r.lista.length - 1].inicio.slice(0, 4);
      lugar.innerHTML = '<div class="mandato-box"><label id="' + id + '-rot" for="' + id + '"><span aria-hidden="true">🕰️ </span>' +
        EP.tr("Ver outro mandato", "See another term") + '</label><div class="mandato-campo"></div>' +
        // ui-r9: mais compacto: uma frase curta à vista; o resto (e as fontes) num bloco que abre
        '<p class="mandato-dica" id="' + id + '-dica">' + esc(fut ? EP.tr("Veja quem estava no poder antes (desde " + desde + ") e quem assume em 2027.", "See who was in power before (since " + desde + ") and who takes office in 2027.") :
          EP.tr("Veja quem estava no poder antes (desde " + desde + ").", "See who was in power before (since " + desde + ").")) + "</p>" +
        '<details class="mandato-mais"><summary><span aria-hidden="true">ℹ️ </span>' + EP.tr("Como funciona", "How it works") + "</summary>" +
        "<p>" + esc(EP.tr("O mandato atual mostra quem está no cargo hoje. Os anteriores mostram quem foi eleito, segundo o TSE. Ao escolher um, a página mostra as mesmas partes, com os dados daquele mandato.",
          "The current term shows who is in office today. Earlier terms show who was elected, according to the TSE. When you choose one, the page shows the same parts, with the data for that term.")) +
        (fut ? " " + esc(EP.tr("O de 2027 a 2030 mostra quem foi eleito em 2026 e toma posse em 2027; ele sai da lista depois das posses.",
          "The 2027–2030 one shows who was elected in 2026 and takes office in 2027; it leaves the list after they take office.")) : "") + "</p>" +
        (r.indice.fontes ? '<p class="mandato-fontes">' + EP.botaoFontes(r.indice.fontes, EP.tr("De onde vêm os mandatos?", "Where do the terms come from?")) + "</p>" : "") + "</details></div>";
      EP.combo(lugar.querySelector(".mandato-campo"), {
        id: id, rotuloId: id + "-rot", descricao: id + "-dica", max: 40, valor: escolhido || r.atual.id,
        placeholder: EP.tr("Escolha o mandato…", "Choose a term…"),
        itens: (fut ? [fut] : []).concat(r.lista.map(function (m) { return { v: m.id, t: rotulo(m) + (m === r.atual ? EP.tr(" (atual)", " (current)") : "") }; })),
        aoEscolher: function (it) {
          var v = it.v === r.atual.id ? null : it.v;
          if (H.url(v, true) !== H.url(H.param(), true)) location.href = H.url(v);
        }
      });
      lugar.hidden = false;
      return r;
    }).catch(function () { lugar.hidden = true; return null; });
  };

  // ---------------------------------------------------------------- peças comuns de um mandato que não é o de hoje
  function poeTitulo(t, desc) {
    var te = document.querySelector("title");
    if (te) te.removeAttribute("data-en");
    document.title = t;
    var m = document.querySelector('meta[name="description"]');
    if (m && desc) { m.removeAttribute("data-en-content"); m.setAttribute("content", desc); }
  }
  // troca um texto que tinha tradução fixa no HTML (data-en) por um texto montado aqui
  function poeTexto(el, txt, ehHtml) {
    if (!el) return;
    el.removeAttribute("data-en");
    el.removeAttribute("data-en-html");
    if (ehHtml) el.innerHTML = txt; else el.textContent = txt;
  }
  function poeOnde(txt) {
    var o = document.getElementById("onde") || document.querySelector(".topo .onde span:last-child");
    poeTexto(o, txt);
  }
  // o título da página com o período embaixo ("A política do Brasil / de 2019 a 2022")
  function poePeriodo(h, txt) {
    if (!h || h.querySelector(".h1-periodo")) return;
    var nome = h.textContent;
    poeTexto(h, esc(nome) + ' <span class="h1-periodo">' + esc(txt) + "</span>", true);
  }
  H.poeTitulo = poeTitulo;
  H.poeTexto = poeTexto;
  H.poeOnde = poeOnde;
  H.poePeriodo = poePeriodo;
  // a descrição de uma seção (o parágrafo embaixo do título)
  H.desc = function (secId, txt, ehHtml) {
    var s = document.getElementById(secId);
    poeTexto(s && s.querySelector(".cab-bloco p"), txt, ehHtml);
  };

  // faixa amarela presa logo abaixo da barra das abas (o mesmo desenho da faixa do perfil, css/mandato.css): diz em texto qual
  // mandato está à vista e leva de volta para hoje, na mesma aba. A altura dela entra na conta do que fica preso no topo
  H.faixa = function (txt) {
    var raiz = document.getElementById("conteudo") || document.body, html = document.documentElement;
    if (document.getElementById("faixa-mandato")) return null;
    var lista = raiz.querySelector(".abas-grupo [role=tablist]");
    lista = lista && (lista.closest(".abas-barra") || lista);  // a faixa vem logo depois da barra das abas
    var f = document.createElement("div");
    f.className = "faixa-mandato faixa-pagina";
    f.id = "faixa-mandato";
    f.setAttribute("role", "region");
    f.setAttribute("aria-label", EP.tr("Mandato que você está vendo", "Term you are viewing"));
    f.innerHTML = '<p><span class="fm-txt" id="faixa-mandato-txt" tabindex="-1"><span aria-hidden="true">📅 </span>' + EP.tr("Você está vendo: ", "You are viewing: ") +
      "<b>" + esc(txt) + '</b></span><span class="fm-sep" aria-hidden="true"> · </span><a class="fm-hoje" href="' + esc(H.url(null)) + '">' +
      EP.tr("Voltar para hoje", "Back to today") + "</a></p>";
    if (lista) lista.insertAdjacentElement("afterend", f);
    else {
      var s = raiz.querySelector("section.bloco");
      if (s) s.parentNode.insertBefore(f, s); else raiz.appendChild(f);
      html.classList.add("faixa-sem-abas");
    }
    html.classList.add("com-faixa");
    var hoje = f.querySelector(".fm-hoje");
    function mede() {
      var t = document.querySelector("header.topo");
      html.style.setProperty("--faixa-h", Math.round(f.getBoundingClientRect().height) + "px");
      if (!lista && t) html.style.setProperty("--topo-h", Math.round(t.getBoundingClientRect().height) + "px");
    }
    mede();
    if ("ResizeObserver" in window) new ResizeObserver(mede).observe(f);
    else window.addEventListener("resize", mede);
    // "Voltar para hoje" leva para a mesma aba
    window.addEventListener("ep-aba", function () { hoje.setAttribute("href", H.url(null)); });
    var antes = EP.topoFixo;
    EP.topoFixo = function () { return (antes ? antes() : (document.querySelector("header.topo") || { offsetHeight: 0 }).offsetHeight) + f.offsetHeight; };
    return f;
  };
  // o aviso de onde vêm os dados daquele mandato, em cima das abas
  H.nota = function (html) {
    var raiz = document.getElementById("conteudo") || document.body;
    var antes = raiz.querySelector(".abas-ep") || raiz.querySelector("section.bloco:not(.cab-pagina)");
    var d = document.createElement("div");
    d.className = "miolo nota-mandato";
    d.innerHTML = html;
    if (antes) antes.parentNode.insertBefore(d, antes); else raiz.appendChild(d);
    return d;
  };
  // corpo (opcional): o aviso do próprio arquivo daquele mandato (ex.: o da cidade), no lugar da frase de sempre
  H.notaPassado = function (m, corpo) {
    return '<p class="aviso azul"><span aria-hidden="true">🕰️ </span>' + (corpo ? esc(EP.tr("Você está vendo o passado. ", "You are looking at the past. ")) + corpo :
      esc(EP.tr("Você está vendo o passado. Aqui aparece quem foi eleito para o mandato de " + m.rotulo +
      ", segundo o TSE (Tribunal Superior Eleitoral), com o partido da eleição. Durante o mandato, algumas pessoas podem ter saído, e vices ou suplentes podem ter assumido.",
      "You are looking at the past. This shows the people elected for the " + m.rotulo_en + " term, according to the TSE (Brazil's Superior Electoral Court), with the party they had in the election. During the term, some may have left, and vices or alternates may have taken over."))) +
      (m.aviso ? " " + D.aviso(m.aviso, m.aviso_en) : "") + "</p>";
  };
  // links do quadro "sem dados": de dentro do site (para hoje) ou de um site oficial (abre em outra aba)
  H.link = function (ic, href, txt, desc) {
    var fora = /^https?:/.test(href);
    return '<li><span class="ic-onde" aria-hidden="true">' + ic + '</span><span><a href="' + esc(href) + '"' +
      (fora ? ' target="_blank" rel="noopener"' + (EP.en ? ' hreflang="pt-BR"' : "") : "") + ">" + esc(txt) +
      (fora ? ' <span aria-hidden="true">↗</span><span class="sr"> ' + EP.tr("(abre em outra aba)", "(opens in a new tab)") + "</span>" : "") + "</a>" +
      (desc ? "<small>" + esc(desc) + "</small>" : "") + "</span></li>";
  };
  // a aba fica no mesmo lugar e diz, em texto simples, que o site não tem aquele dado daquele período (sem prometer nada)
  H.semDados = function (ic, html, links) {
    return '<div class="sem-dados-mandato"><div class="vazio"><span class="grande" aria-hidden="true">' + (ic || "📭") + "</span><p>" + html + "</p></div>" +
      (links && links.length ? '<ul class="links-onde">' + links.join("") + "</ul>" : "") + "</div>";
  };
  // endereço de hoje numa aba (o link "na página de hoje")
  H.hojeEm = function (aba) { return H.url(null, true) + (aba ? "#" + aba : ""); };
  H.fonteCF = function (pt, en) {
    var f = { veiculo: "Planalto", titulo: EP.tr("Constituição Federal, " + pt, "Federal Constitution, " + en + " (in Portuguese)"), url: CF, data: "1988-10-05" };
    if (EP.en) f.lang = "en";
    return f;
  };
  // "Como votaram" (Brasil): o site guarda só as votações do Congresso de hoje
  H.votacoesSemDados = function (futuro) {
    var hoje = H.link("🗳️", H.hojeEm("votacoes"), EP.tr("Ver as votações do Congresso de hoje", "See today's Congress votes"));
    if (futuro) return H.semDados("🗳️", esc(EP.tr("O Congresso eleito em 2026 toma posse em 1º de fevereiro de 2027. As votações deste site são as do Congresso de hoje, desde fevereiro de 2023.",
      "The Congress elected in 2026 takes office on February 1, 2027. The votes on this site are those of today's Congress, since February 2023.")), [hoje]);
    return H.semDados("🗳️", esc(EP.tr("O site guarda as votações do Congresso só do mandato de hoje, desde fevereiro de 2023. As votações deste mandato estão nos sites oficiais do Senado e da Câmara.",
      "The site keeps Congress votes only for today's term, since February 2023. The votes of this term are on the official websites of the Senate and the Chamber of Deputies.")),
    [H.link("🏛️", "https://www25.senado.leg.br/web/atividade/votacoes-nominais", EP.tr("Votações nominais no site do Senado", "Roll-call votes on the Senate website")),
      H.link("🏛️", "https://dadosabertos.camara.leg.br/swagger/api.html#staticfile", EP.tr("Dados abertos da Câmara: arquivos de votações de cada ano", "Chamber of Deputies open data: vote files for each year")),
      hoje]);
  };

  function aviso(html, ic) { return html ? '<p class="aviso"><span aria-hidden="true">' + (ic || "ℹ️") + " </span>" + html + "</p>" : ""; }
  function fontes() {
    var l = [], vistas = {};
    [].forEach.call(arguments, function (p) {
      [].concat((p && (p.fontes || p.fonte)) || []).forEach(function (f) { if (f && !vistas[f.url + f.titulo]) { vistas[f.url + f.titulo] = 1; l.push(f); } });
    });
    return l;
  }
  function falhou(el, link) {
    if (!el) return;
    el.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">🛠️</span>' +
      EP.tr("Não conseguimos abrir este mandato agora. Tente de novo daqui a pouco.", "We could not open this term right now. Please try again in a little while.") +
      (link === false ? "" : '<p><a class="btn peq claro" href="' + esc(H.url(null)) + '">' + EP.tr("Voltar para hoje", "Back to today") + "</a></p>") + "</div>";
  }
  function data(iso) { return EP.dataLonga(iso); }
  function suplementarTxt(datas, cargoPt, cargoEn) {
    return (datas || []).map(function (d) {
      return EP.tr("Houve eleição suplementar para " + cargoPt + " em " + data(d) + ": quem foi eleito nela não aparece aqui.",
        "There was a special election for " + cargoEn + " on " + data(d) + ": whoever was elected in it is not shown here.");
    }).join(" ");
  }

  // cartão de quem governou (sem link: os dados do passado não trazem um número que ligue a pessoa a um perfil do site com
  // segurança, como o CPF; só o nome não basta)
  function cartaoGrande(p, cargo, extra) {
    if (!p) return "";
    return '<div class="pessoa-grande passado">' + EP.av(null, p.nome, null, true) + "<span>" +
      '<span class="cargo">' + esc(cargo) + "</span><b>" + esc(p.nome) + "</b>" +
      (p.nomeCivil && p.nomeCivil !== p.nome ? "<small>" + esc(p.nomeCivil) + "</small>" : "") +
      "<small>" + EP.tr("Partido na eleição: ", "Party at the election: ") + (p.partidoTxt ? esc(p.partidoTxt) : p.partido ? EP.pt(esc(p.partido)) : esc(EP.tr("sem partido", "no party"))) + "</small>" +
      (p.situacao ? "<small>" + D.traduz(p.situacao, null, p.situacao_en) + "</small>" : "") + (extra || "") + "</span></div>";
  }
  // cartão de uma lista (Senado, Câmara, Assembleia, Câmara Municipal), sem link para perfil
  H.cartao = function (m, extra) {
    var partido = m.partido || EP.tr("Sem partido", "No party");
    return '<div class="pessoa-card passado" tabindex="-1">' + EP.av(null, m.nome) + "<b>" + esc(m.nome) + "</b>" +
      (extra ? "<small>" + esc(extra) + "</small>" : "") + "<small>" + esc([partido, m.uf].filter(Boolean).join(" · ")) + "</small></div>";
  };
  function sabia(mulheres, homens) {
    return EP.en ? "Did you know? This list of elected people has <b>" + EP.num(mulheres) + (mulheres === 1 ? " woman" : " women") + "</b> and <b>" + EP.num(homens) + (homens === 1 ? " man" : " men") + "</b>."
      : "Você sabia? Nesta lista de eleitos, são <b>" + EP.num(mulheres) + (mulheres === 1 ? " mulher" : " mulheres") + "</b> e <b>" + EP.num(homens) + (homens === 1 ? " homem" : " homens") + "</b>.";
  }
  var NOMES = {
    sen: function () { return { um: EP.tr("senador", "senator"), uma: EP.tr("senadora", "senator"), varios: EP.tr("senadores", "senators"), varias: EP.tr("senadoras", "senators") }; },
    dep: function () { return { um: EP.tr("deputado", "deputy"), uma: EP.tr("deputada", "deputy"), varios: EP.tr("deputados", "deputies"), varias: EP.tr("deputadas", "deputies") }; },
    dest: function () { return { um: EP.tr("deputado estadual", "state deputy"), uma: EP.tr("deputada estadual", "state deputy"), varios: EP.tr("deputados estaduais", "state deputies"), varias: EP.tr("deputadas estaduais", "state deputies") }; },
    ddist: function () { return { um: EP.tr("deputado distrital", "district deputy"), uma: EP.tr("deputada distrital", "district deputy"), varios: EP.tr("deputados distritais", "district deputies"), varias: EP.tr("deputadas distritais", "district deputies") }; },
    ver: function () { return { um: EP.tr("vereador", "city councilor"), uma: EP.tr("vereadora", "city councilor"), varios: EP.tr("vereadores", "city councilors"), varias: EP.tr("vereadoras", "city councilors") }; }
  };
  function eleitoEm(m) { return m.eleito ? EP.tr(EP.gen(m.genero, "Eleito", "Eleita") + " em " + m.eleito, "Elected in " + m.eleito) : ""; }
  // uma Casa (plenário por partido + filtros + lista), com os cartões sem link e o "Você sabia?" do passado; o.resumo: o mesmo
  // resumo da página de hoje (12 pessoas e "Ver todos")
  function casa(el, membros, o) {
    if (!el) return;
    EP.montaCasa(el, Object.assign({
      membros: membros || [], nomes: o.nomes, fonte: o.fonte, filtroUF: o.filtroUF === true ? undefined : false, nivel: o.nivel || 3,
      cartao: H.cartao, extra: o.extra, sabia: sabia, vazio: o.vazio,
      titPartidos: EP.tr("Quantos de cada partido (partido na eleição)", "Seats per party (party at the election)")
    }, o.resumo || {}));
  }
  function avisosDe(b, uf) {
    return [D.aviso(b.aviso, b.aviso_en)].concat((b.suplementar || []).filter(function (s) { return !uf || s.uf === uf; })
      .map(function (s) { return D.aviso(s.txt, s.txt_en); })).filter(Boolean).join(" ");
  }
  function mudancasHtml(d) {
    var l = d.mudancas || [];
    return l.length ? '<div class="mudancas"><h3 class="sub"><span aria-hidden="true">🔁 </span>' + EP.tr("O que mudou durante o mandato", "What changed during the term") + "</h3><ol>" +
      l.map(function (x) {
        return "<li><b>" + esc(data(x.data)) + "</b><span>" + D.aviso(x.txt, x.txt_en) + "</span>" + EP.botaoFontes(x.fontes) + "</li>";
      }).join("") + "</ol></div>" : "";
  }
  function resumoPadrao() { return EP.abas && EP.abas.ativa() ? { lote: EP.RESUMO_CASA || 12, verTodos: true } : {}; }

  // ---------------------------------------------------------------- ministros dos governos anteriores
  // dados/historico/ministros/<id>.json (feito por scripts/historico.py a partir de dados/manual/ministros-anteriores.json):
  // { governos: [{ presidente, inicio, fim, nota, pastas: [{ nome, nome_en, pessoas: [{ nome, tipo, periodos, f }],
  //   semEfeito?: [{ nome, tipo, nomeacao, anulacao, f }], lacunas?, lacunaFonte? }], fontes }] }.
  // mandatos-r11: o mesmo cartão da página de hoje (um botão por ministério, em ordem alfabética, com o resumo de 8 e "Ver todos");
  // tocar nele abre a janela com quem chefiou, as datas e as fontes. Sem link para perfil.
  function diaAntes(iso) { var d = new Date(iso + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() - 1); return d.toISOString().slice(0, 10); }
  function diaDepois(iso) { var d = new Date(iso + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + 1); return d.toISOString().slice(0, 10); }
  // "21/09 e 22/09" vira "21/09 a 22/09" (só quando um dos dois é um dia só; saídas e voltas de um dia continuam separadas)
  function juntaDias(l) {
    var out = [];
    l.forEach(function (p) {
      var u = out[out.length - 1];
      if (u && u[1] && p[0] && diaDepois(u[1]) === p[0] && (u[0] === u[1] || p[0] === p[1])) u[1] = p[1];
      else out.push([p[0], p[1]]);
    });
    return out;
  }
  function periodoMin(p) {
    var a = p[0], b = p[1];
    if (!a) return EP.tr("até " + EP.data(b), "until " + EP.data(b));
    if (!b) return EP.tr("desde " + EP.data(a) + " (a fonte não traz a data de saída)", "from " + EP.data(a) + " (the source gives no end date)");
    if (a === b) return EP.data(a);
    return EP.tr(EP.data(a) + " a " + EP.data(b), EP.data(a) + " – " + EP.data(b));
  }
  function nomePasta(pa) { return EP.en ? pa.nome_en || D.ministerio(pa.nome) || null : pa.nome; }
  function nomePastaHtml(pa) { var n = nomePasta(pa); return n ? esc(n) : EP.pt(esc(pa.nome)); }
  function pessoaMin(x) {
    return "<li><b>" + esc(x.nome) + "</b>" + (x.conhecido ? " <span>(" + esc(x.conhecido) + ")</span>" : "") +
      '<span class="mh-per">' + esc(juntaDias(x.periodos).map(periodoMin).join("; ")) + "</span>" +
      (x.posto ? "<small>" + EP.pt(esc(x.posto)) + "</small>" : "") +
      (x.cargoNoAto ? "<small>" + esc(EP.tr("No decreto, o cargo aparece como ", "In the decree, the office appears as ")) + "“" + EP.pt(esc(x.cargoNoAto)) + "”.</small>" : "") +
      (x.obs ? "<small>" + (EP.en && x.obs_en ? esc(x.obs_en) : EP.pt(esc(x.obs))) + "</small>" : "") + "</li>";
  }
  // nomeação tornada sem efeito (anulada) por outro decreto: uma linha neutra, sem contar como período de ninguém
  function anuladaMin(s) {
    var n = esc(s.nome), d1 = EP.data(s.nomeacao), d2 = EP.data(s.anulacao), outras = (s.outrasAnulacoes || []).map(EP.data);
    var txt = s.tipo === "interino"
      ? EP.tr("A nomeação interina de " + n + ", em " + d1 + ", foi tornada sem efeito (anulada) por um decreto de " + d2 + ".",
        "The acting appointment of " + n + " on " + d1 + " was made void by a decree of " + d2 + ".")
      : EP.tr("A nomeação de " + n + ", em " + d1 + ", foi tornada sem efeito (anulada) por um decreto de " + d2 + ".",
        "The appointment of " + n + " on " + d1 + " was made void by a decree of " + d2 + ".");
    if (outras.length) txt += outras.length === 1 ? EP.tr(" Outro decreto, de " + outras[0] + ", diz o mesmo.", " Another decree, of " + outras[0] + ", says the same.")
      : EP.tr(" Outros decretos, de " + outras.join(" e ") + ", dizem o mesmo.", " Other decrees, of " + outras.join(" and ") + ", say the same.");
    return '<p class="mh-anulada"><span aria-hidden="true">📄 </span>' + txt + "</p>";
  }
  function porTipo(pa, t) { return pa.pessoas.filter(function (x) { return x.tipo === t; }); }
  function fontesPasta(pa, g) {
    var f = [];
    pa.pessoas.concat(pa.semEfeito || []).forEach(function (x) { x.f.forEach(function (i) { if (g.fontes[i] && f.indexOf(g.fontes[i]) < 0) f.push(g.fontes[i]); }); });
    return f;
  }
  // o cartão (o mesmo .min-card da página de hoje, no visual D: um ícone por ministério): o ministério e quem foi titular
  function areaPastaHtml(pa) { var n = nomePasta(pa), a = EP.d ? EP.d.area(n || pa.nome) : (n || pa.nome); return n ? esc(a) : EP.pt(esc(a)); }
  function cartaoMin(pa, gi, k) {
    var tit = porTipo(pa, "titular"), inter = porTipo(pa, "interino");
    var nomes = tit.map(function (x) { return x.nome; });
    var quem = nomes.length ? (nomes.length > 3 ? nomes.slice(0, 2).join("; ") + EP.tr(" e mais " + (nomes.length - 2), " and " + (nomes.length - 2) + " more") : nomes.join("; ")) :
      inter.length ? EP.tr("Só interinos neste período", "Only acting ministers in this period") : EP.tr("A fonte não traz ministro", "The source shows no minister");
    return '<button type="button" class="min-card d-min" data-min-hist="' + gi + ":" + k + '" aria-haspopup="dialog"><span class="m-ic" aria-hidden="true">' + esc(pa._ic || "🏢") +
      '</span><span class="d-min-txt"><span class="d-min-area" aria-hidden="true">' + areaPastaHtml(pa) + '</span><b class="sr">' + nomePastaHtml(pa) + "</b><small>" + esc(quem) + "</small></span></button>";
  }
  // a janela de um ministério: quem chefiou, as datas da fonte, interinos, avisos e as fontes
  function janelaMin(pa, g, fimMandato) {
    var tit = porTipo(pa, "titular"), inter = porTipo(pa, "interino"), sub = porTipo(pa, "substituto"), anul = pa.semEfeito || [];
    var fim = g.fim === fimMandato ? diaAntes(g.fim) : g.fim;
    var lista = function (l) { return '<ul class="mh-lista">' + l.map(pessoaMin).join("") + "</ul>"; };
    return '<p class="min-gov-per">' + esc(EP.tr("Ministros de " + g.presidente + ", de " + EP.dataLonga(g.inicio) + " a " + EP.dataLonga(fim) + ".",
      "Ministers of " + g.presidente + ", from " + EP.dataLonga(g.inicio) + " to " + EP.dataLonga(fim) + ".")) + "</p>" +
      '<h3><span aria-hidden="true">👤 </span>' + EP.tr("Quem chefiou", "Who headed it") + "</h3>" +
      (tit.length ? lista(tit) : '<p class="mh-expl">' + (inter.length ? EP.tr("Neste período, só aparecem interinos.", "In this period, only acting ministers appear.")
        : EP.tr("Neste período, a fonte não traz ministro nesta pasta.", "In this period, the source shows no minister for this office.")) + "</p>") +
      anul.map(anuladaMin).join("") +
      (pa.lacunas || []).map(function (l) {
        var a = EP.data(l[0]), b = EP.data(l[1]);
        // uma nomeação tornada sem efeito dentro do intervalo não valeu: o aviso fala de nomeação válida, para não contradizer a linha acima
        var comAnulada = anul.some(function (s) { return s.nomeacao >= l[0] && s.nomeacao <= l[1]; });
        return '<p class="mh-lacuna"><span aria-hidden="true">⏸️ </span>' + esc(pa.lacunaFonte !== "dou"
          ? EP.tr("A lista oficial não traz ninguém à frente desta pasta de " + a + " a " + b + ".", "The official list shows no one heading this office from " + a + " to " + b + ".")
          : comAnulada ? EP.tr("O Diário Oficial não traz nomeação válida de ministro de " + a + " a " + b + ".", "The Official Gazette shows no valid minister appointment from " + a + " to " + b + ".")
            : EP.tr("O Diário Oficial não traz nomeação de ministro de " + a + " a " + b + ".", "The Official Gazette shows no minister appointed from " + a + " to " + b + ".")) + "</p>";
      }).join("") +
      (inter.length ? '<details class="mh-mais"><summary>' + EP.tr("Interinos", "Acting ministers") + " (" + inter.length + ")</summary>" +
        '<p class="mh-expl">' + EP.tr("Interino é quem respondeu pelo ministério por um tempo, no lugar do ministro.", "An acting minister is someone who ran the ministry for a while, in the minister's place.") + "</p>" + lista(inter) + "</details>" : "") +
      (sub.length ? '<details class="mh-mais"><summary>' + EP.tr("Quadro “Interino” da lista oficial", "The list's “" + EP.pt("Interino") + "” table") + " (" + sub.length + ")</summary>" +
        '<p class="mh-expl">' + EP.tr("A lista da Biblioteca da Presidência também tem um quadro chamado “Interino”, com estas pessoas e estes períodos (em geral, longos). Ele aparece aqui como está na lista.",
          "The Presidency Library list also has a table called “" + EP.pt("Interino") + "” (acting), with these people and periods (usually long ones). It is shown here as it appears in the list.") + "</p>" + lista(sub) + "</details>" : "") +
      '<p class="mh-expl">' + esc(EP.tr("As datas são as da fonte oficial, da nomeação até a saída. Uma pessoa pode ter mais de um período, quando saiu e voltou ao cargo.",
        "The dates are those in the official source, from appointment to departure. A person may have more than one period, when they left and came back.")) + "</p>" +
      '<h3><span aria-hidden="true">📚 </span>' + EP.tr("Fontes", "Sources") + "</h3>" + EP.fontesHtml(fontesPasta(pa, g));
  }
  var MIN_H = null;  // { gs: governos com as pastas em ordem, fim }
  // site-d-r14: o ministério abre na gaveta (EP.gaveta; o endereço guarda: ?ver=minh:<governo>.<pasta>)
  function abreMinHist(gi, k, de) {
    var g = MIN_H && MIN_H.gs[gi], pa = g && g._pastas[k];
    if (!pa) return;
    if (EP.gaveta) EP.gaveta({ tit: '<span aria-hidden="true">' + esc(pa._ic || "🏢") + " </span>" + nomePastaHtml(pa), ver: "minh:" + gi + "." + k, corpo: janelaMin(pa, g, MIN_H.fim) }, de);
    else EP.abrir('<span aria-hidden="true">' + esc(pa._ic || "🏢") + " </span>" + nomePastaHtml(pa), janelaMin(pa, g, MIN_H.fim));
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-min-hist]");
    if (!b || !MIN_H) return;
    var k = b.getAttribute("data-min-hist").split(":");
    abreMinHist(+k[0], +k[1], b);
  });
  if (EP.gavetaVer) EP.gavetaVer.minh = function (v) {
    var m = /^(\d+)\.(\d+)$/.exec(v || ""), t0 = Date.now();
    if (!m) return;
    if (EP.abas && EP.abas.mostra) EP.abas.mostra("executivo");
    (function tenta() {
      if (MIN_H) abreMinHist(+m[1], +m[2], document.querySelector('[data-min-hist="' + m[1] + ":" + m[2] + '"]'));
      else if (Date.now() - t0 < 8000) setTimeout(tenta, 150);
    })();
  };
  // ícone de cada ministério: o mesmo da página de hoje, quando o nome é igual (dados/manual/ministros.json); senão, 🏢
  function icones(manual) {
    var ic = {};
    ((manual && manual.ministerios) || []).forEach(function (m) { if (m.ministerio && m.ic) ic[EP.norm(m.ministerio)] = m.ic; });
    return ic;
  }
  function ministrosPassado(mins, manual) {
    var tit = document.getElementById("os-ministros"), desc = tit && tit.nextElementSibling, grade = document.getElementById("ministros"), fonte = document.getElementById("fonte-min");
    if (!grade) return;
    poeTexto(desc, EP.tr("Ministros não são eleitos: o presidente escolhe cada um para cuidar de uma área, como a saúde ou a educação. Toque num ministério para ver quem o chefiou neste mandato, com as datas da fonte oficial.",
      "Ministers are not elected: the President chooses each one to take care of an area, such as health or education. Tap a ministry to see who headed it in this term, with the dates from the official source."));
    var caixa = document.createElement("div");
    caixa.className = "min-hist";
    caixa.id = "min-hist";
    grade.parentNode.insertBefore(caixa, grade);
    grade.hidden = true;
    grade.style.display = "none";
    var gs = (mins && mins.governos) || [], ic = icones(manual);
    if (fonte) fonte.innerHTML = "";
    if (!mins) { caixa.innerHTML = aviso(esc(EP.tr("Não conseguimos abrir a lista de ministros agora. Tente de novo daqui a pouco.", "We could not open the list of ministers right now. Please try again in a little while.")), "🛠️"); return; }
    if (!gs.length) {
      caixa.innerHTML = H.semDados("👔", esc(EP.tr("Esta página não tem a lista de ministros deste mandato.", "This page does not have the list of ministers for this term.")),
        [H.link("👔", H.hojeEm("os-ministros"), EP.tr("Ver os ministros de hoje", "See today's ministers"))]);
      return;
    }
    gs.forEach(function (g) {
      g._pastas = EP.alfabetica(g.pastas.map(function (pa) { return Object.assign({ _nome: EP.d ? EP.d.area(nomePasta(pa) || pa.nome) : nomePasta(pa) || pa.nome, _ic: ic[EP.norm(pa.nome)] }, pa); }), "_nome");  // site-d-r14: pelo nome da área do ícone
    });
    MIN_H = { gs: gs, fim: mins.fim };
    caixa.innerHTML = (gs.length > 1 ? aviso(esc(EP.tr("O governo mudou em " + EP.dataLonga(gs[1].inicio) + ", quando " + gs[1].presidente + " passou a exercer a Presidência (veja “O que mudou durante o mandato”, acima). Por isso a lista tem duas partes.",
      "The government changed on " + EP.dataLonga(gs[1].inicio) + ", when " + gs[1].presidente + " became acting President (see “What changed during the term”, above). That is why the list has two parts.")), "🔁") : "") +
      gs.map(function (g, i) {
        var fim = g.fim === mins.fim ? diaAntes(g.fim) : g.fim, ps = g._pastas, n = ps.length;  // site-d-r14: todos os ícones à vista
        return '<section class="min-gov" aria-labelledby="t-min-gov-' + i + '"><h4 id="t-min-gov-' + i + '">' + esc(EP.tr("Ministros de ", "Ministers of ") + g.presidente) +
          " <small>(" + ps.length + " " + EP.tr(ps.length === 1 ? "pasta" : "pastas", ps.length === 1 ? "office" : "offices") + ")</small>" +
          '<span class="min-gov-per">' + esc(EP.tr("De " + EP.dataLonga(g.inicio) + " a " + EP.dataLonga(fim), "From " + EP.dataLonga(g.inicio) + " to " + EP.dataLonga(fim))) + "</span></h4>" +
          (g.nota ? '<p class="nota-min">' + D.aviso(g.nota, g.nota_en) + "</p>" : "") +
          '<div class="grade-min d-mins" id="min-grade-' + i + '">' + ps.slice(0, n).map(function (pa, k) { return cartaoMin(pa, i, k); }).join("") + "</div>" +
          (n < ps.length ? '<p class="mais-lista ver-todos-min"><button type="button" class="btn claro peq" aria-controls="min-grade-' + i + '" data-min-todos="' + i + '">' +
            esc(EP.tr("Ver todos os " + EP.num(ps.length) + " ministérios", "See all " + EP.num(ps.length) + " ministries")) + ' <span aria-hidden="true">▾</span></button></p>' : "") + "</section>";
      }).join("");
    [].forEach.call(caixa.querySelectorAll("[data-min-todos]"), function (b) {
      b.addEventListener("click", function () {
        var i = +b.getAttribute("data-min-todos"), el = document.getElementById("min-grade-" + i), ps = gs[i]._pastas, n = el.children.length;
        el.insertAdjacentHTML("beforeend", ps.slice(n).map(function (pa, k) { return cartaoMin(pa, i, n + k); }).join(""));
        b.parentNode.remove();
        var novo = el.querySelector('[data-min-hist="' + i + ":" + n + '"]');
        if (novo) EP.focaSuave(novo);
      });
    });
    if (fonte) fonte.innerHTML = '<small class="muted">' + esc(EP.tr("Cada ministério tem a sua fonte (toque nele). As datas são as da fonte oficial, da nomeação até a saída. Quando a fonte não traz ninguém à frente de uma pasta por mais de 15 dias, o quadro que abre avisa.",
      "Each ministry has its own source (tap it). The dates are those in the official source, from appointment to departure. When the source shows no one heading an office for more than 15 days, the panel that opens says so.")) + "</small>";
  }

  // ---------------------------------------------------------------- Brasil (brasil.html?mandato=2019)
  // js/brasil.js já montou as abas de hoje (Quem governa, Senado, Câmara, Como votaram, STF); aqui entram os dados do passado.
  // o.abre(id, fn): roda fn quando a aba id abre (EP.abas.quandoAbrir)
  H.brasil = function (id, o) {
    o = o || {};
    return H.mandatos("brasil").then(function (r) {
      var m = doPassado(r, id);
      if (!m) return paraHoje();
      return Promise.all([EP.json(BASE + "brasil/" + m.id + ".json"),
        m.ministros ? EP.json(BASE + "ministros/" + m.id + ".json").catch(function () { return null; }) : { governos: [] },
        EP.json("dados/manual/ministros.json").catch(function () { return null; })])
        .then(function (x) { brasil(m, x[0], x[1], x[2], o); });
    }).catch(function () { falhou(document.getElementById("exec-topo")); });
  };
  function brasil(m, d, mins, manual, o) {
    var abre = o.abre || function (id, fn) { fn(); };
    var main = document.getElementById("conteudo"), cab = main.querySelector(".cab-pagina");
    D.canonico({ mandato: m.id });
    poeTitulo(EP.tr("A política do Brasil de " + m.rotulo + ": presidente, ministros, senadores e deputados federais | Entenda Política",
      "Brazil's politics, " + m.rotulo_en + ": the President, ministers, senators and federal deputies | Understand Politics"),
    EP.tr("Quem governou o Brasil no mandato de " + m.rotulo + ": o presidente e o vice eleitos, os ministros de cada pasta, os senadores e os deputados federais eleitos. Com fonte oficial.",
      "Who governed Brazil in the " + m.rotulo_en + " term: the elected President and Vice President, the ministers of each office, and the elected senators and federal deputies. With official sources."));
    poeOnde(EP.tr("A política do Brasil (" + m.rotulo + ")", "Brazil's politics (" + m.rotulo_en + ")"));
    poeTexto(cab.querySelector(".selo-topo"), EP.tr("Quem governou e quem foi eleito no mandato de " + m.rotulo, "Who governed and who was elected in the " + m.rotulo_en + " term"));
    poePeriodo(cab.querySelector("h1"), periodo(m));
    poeTexto(cab.querySelector(".lead"), EP.tr("Aqui você vê quem governou e quem fez as leis do país no mandato de " + m.rotulo + ": o presidente e o vice eleitos, os ministros, os senadores e os deputados federais.",
      "Here you can see who governed and who made the country's laws in the " + m.rotulo_en + " term: the elected President and Vice President, the ministers, the senators and the federal deputies."));
    H.nota(H.notaPassado(m));
    H.faixa(EP.tr("o mandato de " + m.rotulo, "the " + m.rotulo_en + " term"));
    // Quem governa
    H.desc("executivo", EP.tr("O Poder Executivo: o presidente e o vice eleitos para o mandato de " + m.rotulo + " e os ministros de cada governo. Eles governam: põem as leis em prática e cuidam dos serviços públicos.",
      "The executive branch: the President and the Vice President elected for the " + m.rotulo_en + " term, and the ministers of each government. They govern: they put the laws into practice and run public services."));
    abre("executivo", function () {
      var p = d.presidente, v = d.vice, f = fontes(p, v), topo = document.getElementById("exec-topo");
      topo.innerHTML = (cartaoGrande(p, EP.tr("Presidente", "President")) + cartaoGrande(v, EP.tr("Vice-presidente", "Vice President")) ||
        '<div class="vazio">' + EP.tr("O TSE não mostra quem foi eleito presidente.", "The TSE does not show who was elected President.") + "</div>") +
        (d.nota ? '<p class="nota-hist">' + D.aviso(d.nota, d.nota_en) + "</p>" : "") +
        (f.length ? '<p class="fontes-exec">' + EP.botaoFontes(f) + "</p>" : "");
      topo.insertAdjacentHTML("afterend", mudancasHtml(d));
      ministrosPassado(mins, manual);
      EP.revelar(document.getElementById("executivo"));
    });
    // Senado e Câmara
    [["senado", d.senado, NOMES.sen(), eleitoEm], ["camara", d.camara, NOMES.dep(), null]].forEach(function (c) {
      abre(c[0], function () {
        var el = document.querySelector("#" + c[0] + " .casa-corpo"), b = c[1] || {};
        if (!el) return;
        el.insertAdjacentHTML("beforebegin", aviso(avisosDe(b)));
        casa(el, b.membros, { nomes: c[2], fonte: fontes(b), filtroUF: true, extra: c[3], resumo: resumoPadrao() });
      });
    });
    EP.revelar(main);
  }

  // ---------------------------------------------------------------- estado (estado.html?uf=BA&mandato=2019)
  // js/estado.js já montou as abas de hoje (Quem governa, Senadores, Deputados federais, Deputados estaduais, Minha cidade)
  H.estado = function (uf, id, o) {
    o = o || {};
    return H.mandatos("estados").then(function (r) {
      var m = doPassado(r, id);
      if (!m) return paraHoje();
      return Promise.all([EP.json(BASE + "estados/" + uf + ".json"), EP.json(BASE + "brasil/" + m.id + ".json").catch(function () { return null; })])
        .then(function (x) { estado(uf, m, ((x[0] || {}).mandatos || {})[m.id] || {}, x[1], o); });
    }).catch(function () { falhou(document.getElementById("gov")); });
  };
  function estado(uf, m, e, br, o) {
    var quando = o.quando || function (id, fn) { fn(); }, resumo = o.resumo || {};
    var nome = EP.UFS[uf], de = EP.doEstado(uf), ehDF = uf === "DF";
    D.canonico({ uf: uf, mandato: m.id });
    poeTitulo(EP.tr("A política " + de + " de " + m.rotulo + ": governador, senadores e deputados eleitos | Entenda Política",
      "Politics " + de + ", " + m.rotulo_en + ": the elected governor, senators and deputies | Understand Politics"),
    EP.tr("Quem foi eleito " + EP.noEstado(uf) + " para o mandato de " + m.rotulo + ": governador, vice, senadores, deputados federais e estaduais. Segundo o TSE, com fonte.",
      "Who was elected " + EP.noEstado(uf) + " for the " + m.rotulo_en + " term: governor, vice governor, senators, federal and state deputies. According to the TSE, with sources."));
    poeOnde(nome + " (" + rotulo(m) + ")");
    poePeriodo(document.getElementById("titulo-uf"), periodo(m));
    poeTexto(document.getElementById("lead-uf"), EP.tr("Quem foi eleito para governar, para representar " + (ehDF ? "o Distrito Federal" : "o estado") + " no Congresso e para fazer as leis " + de + " no mandato de " + m.rotulo + ".",
      "Who was elected to govern, to represent " + (ehDF ? "the Federal District" : "the state") + " in the National Congress and to make the laws " + de + " in the " + m.rotulo_en + " term."));
    H.nota(H.notaPassado(m));
    H.faixa(EP.tr("o mandato de " + m.rotulo, "the " + m.rotulo_en + " term"));
    // Quem governa
    H.desc("governo", EP.tr("O governador e o vice eleitos para o mandato de " + m.rotulo + ".", "The governor and the vice governor elected for the " + m.rotulo_en + " term."));
    var g = e.governador, v = e.vice, notasGov = [], fg = fontes(g, v);
    if (!g) notasGov.push(esc(EP.tr("O TSE não mostra quem foi eleito governador nesta eleição.", "The TSE does not show who was elected governor in this election.")));
    if (g && !v && e.avisoVice) notasGov.push(D.aviso(e.avisoVice, e.avisoVice_en));
    if (e.suplementar) notasGov.push(esc(suplementarTxt(e.suplementar, "governador", "governor")));
    document.getElementById("gov").innerHTML = cartaoGrande(g, EP.tr(EP.gen(g && g.genero, "Governador", "Governadora"), "Governor")) +
      cartaoGrande(v, EP.tr(EP.gen(v && v.genero, "Vice-governador", "Vice-governadora"), "Vice Governor"));
    document.getElementById("gov-nota").innerHTML = aviso(notasGov.join(" ")) + (fg.length ? '<p style="margin-top:12px">' + EP.botaoFontes(fg) + "</p>" : "");
    // Senadores
    H.desc("senadores", EP.tr("Os senadores eleitos " + EP.noEstado(uf) + " que estavam no mandato de " + m.rotulo + " (cada estado tem 3).",
      "The senators elected " + EP.noEstado(uf) + " who were serving in the " + m.rotulo_en + " term (each state has 3)."));
    var sen = br ? EP.alfabetica(((br.senado || {}).membros || []).filter(function (x) { return x.uf === uf; })) : null, ls = document.getElementById("lista-sen");
    ls.innerHTML = sen ? sen.map(function (x) { return H.cartao(x, eleitoEm(x)); }).join("") || '<div class="vazio">' + EP.tr("O TSE não mostra senadores deste estado neste mandato.", "The TSE shows no senators for this state in this term.") + "</div>"
      : '<div class="vazio">' + EP.tr("Lista indisponível agora.", "This list is not available right now.") + "</div>";
    if (br) {
      ls.insertAdjacentHTML("beforebegin", aviso(avisosDe(br.senado || {}, uf)));
      if (fontes(br.senado).length) ls.insertAdjacentHTML("afterend", '<p class="fonte-casa">' + EP.botaoFontes(fontes(br.senado), EP.tr("De onde vem esta lista?", "Where does this list come from?")) + "</p>");
    }
    // Deputados federais e estaduais
    H.desc("federais", EP.tr("Eleitos " + EP.noEstado(uf) + " para a Câmara dos Deputados, em Brasília, no mandato de " + m.rotulo + ".",
      "Elected " + EP.noEstado(uf) + " to the Chamber of Deputies, in Brasília, for the " + m.rotulo_en + " term."));
    var fed = br ? ((br.camara || {}).membros || []).filter(function (x) { return x.uf === uf; }) : null, dep = e.deputados || {};
    quando("federais", function () {
      var el = document.getElementById("casa-fed");
      if (!fed) { falhou(el, false); return; }
      el.insertAdjacentHTML("beforebegin", aviso(avisosDe(br.camara || {})));
      casa(el, fed, { nomes: NOMES.dep(), fonte: fontes(br.camara), resumo: resumo });
    });
    H.desc("estaduais", EP.tr("Eleitos para fazer as leis " + de + " e fiscalizar o governador no mandato de " + m.rotulo + ".",
      (ehDF ? "District deputies" : "State deputies") + " elected to make the laws " + de + " and oversee the governor in the " + m.rotulo_en + " term."));
    quando("estaduais", function () {
      document.getElementById("aviso-est").innerHTML = aviso(D.aviso(dep.aviso, dep.aviso_en));
      casa(document.getElementById("casa-est"), dep.membros, { nomes: ehDF ? NOMES.ddist() : NOMES.dest(), fonte: fontes(dep), resumo: resumo });
    });
    EP.revelar(document.getElementById("estado"));
  }

  // ---------------------------------------------------------------- cidade (cidade.html?ibge=2927408&mandato=2021)
  // o.esqueleto(caixa, x): a mesma página de hoje (js/cidade.js), com as abas; devolve { quando }. o.pronto: roda no fim
  H.cidade = function (caixa, ibge, uf, id, o) {
    o = o || {};
    return H.mandatos("cidades").then(function (r) {
      var m = doPassado(r, id);
      if (!m) return paraHoje();
      return Promise.all([EP.json(BASE + "cidades/" + uf + "/" + m.id + ".json"), EP.json("dados/cidades.json").catch(function () { return []; })])
        .then(function (x) {
          var nome = ((x[1] || []).filter(function (c) { return c[0] === ibge; })[0] || [])[1];
          if (!nome) {
            caixa.innerHTML = '<div class="miolo"><div class="vazio"><span class="grande" aria-hidden="true">🤷</span>' +
              EP.tr("Não encontramos essa cidade. Procure pelo nome no campo acima.", "We could not find that city. Search for it by name above.") + "</div></div>";
            return;
          }
          cidade(caixa, ibge, uf, nome, m, x[0], r, o);
          if (o.pronto) o.pronto();
        });
    }).catch(function () { falhou(caixa); });
  };
  function pessoaArr(a) { return a ? { nome: a[0], nomeCivil: a[1] || null, partido: a[2], genero: a[3] || null, turno: a[4] } : null; }
  // "A próxima eleição" de um mandato que já acabou: a eleição que escolheu quem veio depois (e o link para aquele mandato)
  function proximaPassado(m, r) {
    var depois = r.todos.filter(function (x) { return x.inicio === m.fim; })[0];
    var vai = depois && depois.id !== r.atual.id && !r.atual.novo ? depois.id : null;
    var txt = depois ? EP.tr("Este mandato acabou em " + data(diaAntes(m.fim)) + ". Quem veio depois foi escolhido na eleição de " + depois.eleicao + ", para o mandato de " + depois.rotulo + ".",
      "This term ended on " + data(diaAntes(m.fim)) + ". The next ones were chosen in the " + depois.eleicao + " election, for the " + depois.rotulo_en + " term.") :
      EP.tr("Este mandato acabou em " + data(diaAntes(m.fim)) + ".", "This term ended on " + data(diaAntes(m.fim)) + ".");
    return H.semDados("🗳️", esc(txt), depois ? [H.link("🕰️", vai ? H.url(vai, true) : H.hojeEm("proxima-eleicao"),
      vai ? EP.tr("Ver o mandato de " + depois.rotulo, "See the " + depois.rotulo_en + " term") : EP.tr("Ver a página de hoje (a próxima eleição)", "See today's page (the next election)"))] : []);
  }
  function cidade(caixa, ibge, uf, nome, m, f, r, o) {
    var c = (f.cidades || {})[ibge], ano = f.eleicao;
    D.canonico({ ibge: ibge, mandato: m.id });
    poeTitulo(EP.tr("A política de " + nome + " (" + uf + ") de " + m.rotulo + ": prefeito, vice e vereadores eleitos | Entenda Política",
      "Politics in " + nome + " (" + uf + "), " + m.rotulo_en + ": the elected mayor, vice mayor and city councilors | Understand Politics"),
    EP.tr("Quem foi eleito em " + nome + " (" + uf + ") para o mandato de " + m.rotulo + ": prefeito, vice e vereadores. Segundo o TSE, com fonte.",
      "Who was elected in " + nome + " (" + uf + "), Brazil, for the " + m.rotulo_en + " term: mayor, vice mayor and city councilors. According to the TSE, with sources."));
    poeOnde(nome + " (" + rotulo(m) + ")");
    var x = { nome: nome, uf: uf, periodo: periodo(m), proxima: proximaPassado(m, r),
      camDesc: EP.tr("Os vereadores eleitos para fazer as leis da cidade e fiscalizar o prefeito no mandato de " + esc(m.rotulo) + ".",
        "The city councilors (<span lang=\"pt-BR\">vereadores</span>) elected to make the city's laws and oversee the mayor in the " + esc(m.rotulo_en) + " term.") };
    if (!c) {
      var prim = (f.depois || {})[ibge];
      var txt = prim ? EP.tr("No mandato de " + m.rotulo + ", " + nome + " ainda não era um município. Segundo o TSE, a primeira eleição de prefeito e vereadores da cidade foi em " + prim + ".",
        "In the " + m.rotulo_en + " term, " + nome + " was not a municipality yet. According to the TSE, the city's first election for mayor and city councilors was in " + prim + ".") :
        EP.tr("O TSE não tem dados de " + nome + " na eleição de " + ano + ".", "The TSE has no data on " + nome + " in the " + ano + " election.");
      var semCidade = '<div class="aviso azul"><span aria-hidden="true">ℹ️ </span>' + esc(txt) + "</div>" + '<p style="margin-top:10px">' + EP.botaoFontes(f.fonte) + "</p>";
      x.gov = "";
      x.semCidade = true;
      x.govNotas = semCidade;
      x.camAviso = semCidade;
      x.nTxt = null;
    } else {
      var p = pessoaArr(c.p), v = pessoaArr(c.v), ver = (c.ver || []).map(function (y) { return { nome: y[0], partido: y[1], genero: y[2] || null }; });
      if (v && f.avisoPartidoVice && !v.partido) v.partidoTxt = EP.tr("não informado (veja o aviso abaixo)", "not given (see the note below)");
      var sitP = function (y) {
        return y ? "<small>" + esc(EP.tr(EP.gen(y.genero, "Eleito", "Eleita") + " no " + y.turno + "º turno", y.turno > 1 ? "Elected in the runoff" : "Elected in the first round")) + "</small>" : "";
      };
      var sitV = function (y) {
        return y && p ? "<small>" + esc(EP.tr(EP.gen(y.genero, "Eleito", "Eleita") + " na chapa de " + p.nome, "Elected on " + p.nome + "'s ticket")) + "</small>" : "";
      };
      var notas = [];
      if (c.nm) notas.push(EP.tr("Nesta eleição, o TSE chamava a cidade de “" + esc(c.nm) + "”.", "In this election, the TSE listed the city as “" + EP.pt(esc(c.nm)) + "”."));
      var notasP = [];
      if (!p) notasP.push(esc(EP.tr("O TSE não mostra prefeito eleito nesta eleição: ela pode ter sido anulada.", "The TSE does not show an elected mayor in this election: it may have been annulled.")));
      if (p && !v) notasP.push(f.avisoVice ? D.aviso(f.avisoVice, f.avisoVice_en) :
        esc(EP.tr("Nos dados do TSE, o vice desta chapa não aparece.", "In the TSE data, the vice mayor of this ticket does not appear.")));
      if (v && v.partidoTxt) notasP.push(D.aviso(f.avisoPartidoVice, f.avisoPartidoVice_en));
      if (c.supP) notasP.push(esc(suplementarTxt(c.supP, "prefeito", "mayor")));
      var notasV = [];
      if (c.vagas) notasV.push(esc(ver.length ? EP.tr("O TSE lista " + ver.length + " vereadores eleitos, mas a Câmara tinha " + c.vagas + " cadeiras: faltam nomes nos dados abertos.",
        "The TSE lists " + ver.length + " elected city councilors, but the council had " + c.vagas + " seats: some names are missing from the open data.") :
        EP.tr("O TSE não mostra os vereadores eleitos nesta eleição (a Câmara tinha " + c.vagas + " cadeiras).", "The TSE does not show the city councilors elected in this election (the council had " + c.vagas + " seats).")));
      if (c.supV) notasV.push(esc(suplementarTxt(c.supV, "vereador", "city councilor")));
      if (c.exc) notasV.push(esc(c.exc === 1 ? EP.tr("Nos dados do TSE, 1 pessoa aparece como eleita, mas com a candidatura marcada como renúncia, falecimento ou registro negado: ela não entra na lista.",
        "In the TSE data, 1 person appears as elected, but with the candidacy marked as withdrawn, deceased or rejected: this person is not on the list.") :
        EP.tr("Nos dados do TSE, " + c.exc + " pessoas aparecem como eleitas, mas com a candidatura marcada como renúncia, falecimento ou registro negado: elas não entram na lista.",
          "In the TSE data, " + c.exc + " people appear as elected, but with the candidacy marked as withdrawn, deceased or rejected: they are not on the list.")));
      var n = ver.length;
      x.avisos = aviso(notas.filter(Boolean).join(" "));
      x.gov = cartaoGrande(p, EP.tr(EP.gen(p && p.genero, "Prefeito", "Prefeita"), "Mayor"), sitP(p)) + cartaoGrande(v, EP.tr(EP.gen(v && v.genero, "Vice-prefeito", "Vice-prefeita"), "Vice Mayor"), sitV(v));
      x.govNotas = aviso(notasP.join(" ")) + '<p style="margin-top:8px">' + EP.botaoFontes(f.fonte) + "</p>";
      x.nTxt = EP.num(n) + " " + EP.tr(n === 1 ? "vereador eleito" : "vereadores eleitos", n === 1 ? "elected councilor" : "elected councilors");
      x.nVer = n;  // site-d-r16: o número grande do topo
      x.ano = ano;
      x.camAviso = aviso(notasV.join(" "));
    }
    var pag = o.esqueleto(caixa, x);
    H.nota(H.notaPassado(m, D.aviso(f.aviso, f.aviso_en)));
    H.faixa(EP.tr("o mandato de " + m.rotulo, "the " + m.rotulo_en + " term"));
    H.seletor(document.getElementById("mandato-lugar"), "cidades", m.id);
    if (c) pag.quando("camara-mun", function () {
      casa(document.getElementById("casa-ver"), ver, { nomes: NOMES.ver(), fonte: f.fonte, resumo: resumoPadrao(),
        vazio: EP.tr("O TSE não mostra os vereadores eleitos nesta eleição.", "The TSE does not show the city councilors elected in this election.") });
    });
  }
})();
