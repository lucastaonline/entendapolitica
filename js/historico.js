/* ====== Entenda Política: mandatos anteriores ======
   O campo "Ver outro mandato" (lista com busca, EP.combo) nas páginas do Brasil, do estado e da cidade, e a página do passado:
   quem foi ELEITO para cada mandato, segundo o TSE (dados/historico/, gerados por scripts/historico.py, que roda à mão).
   Por padrão a página mostra hoje; com ?mandato=<ano de início> (ex.: brasil.html?mandato=2019) ela mostra o passado.
   Qual mandato é o de hoje sai das datas de posse do índice (dados/historico/indice.json), nunca de um ano escrito aqui.

   EP.hist.param()                              "2019" ou null
   EP.hist.seletor(lugar, nivel, escolhido)     monta o campo dentro de "lugar" (nivel: "brasil" | "estados" | "cidades")
   EP.hist.brasil(id)                           a página do Brasil no passado (js/brasil.js chama quando há ?mandato=)
   EP.hist.estado(uf, id)                       a página do estado no passado (js/estado.js)
   EP.hist.cidade(caixa, ibge, uf, id, pronto)  a cidade no passado (js/cidade.js); "pronto" roda depois de desenhar
   Se o mandato pedido não é do passado (é o de hoje, ainda não começou ou não existe), a página volta para hoje. */
(function () {
  "use strict";
  var EP = window.EP;
  if (!EP) return;
  var D = EP.trd, esc = EP.esc;
  var H = (EP.hist = {});
  var BASE = "dados/historico/";

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
      var l = (ind[nivel] || []).filter(function (m) { return m.inicio <= hoje; })
        .sort(function (a, b) { return a.inicio < b.inicio ? 1 : -1; });
      var atual = l.filter(function (m) { return hoje < m.fim; })[0] || null;
      if (!atual && l.length) {
        // já começou um mandato que ainda não está no histórico: "hoje" é ele (a página de hoje já mostra quem está lá)
        var a = +l[0].fim.slice(0, 4);
        atual = { id: String(a), inicio: l[0].fim, novo: true, rotulo: a + " a " + (a + 3), rotulo_en: a + "–" + (a + 3) };
        l.unshift(atual);
      }
      return { lista: l, atual: atual, indice: ind };
    });
  };
  // o mandato pedido, se for do passado (senão, null)
  function doPassado(r, id) {
    return r.lista.filter(function (m) { return m.id === id && m !== r.atual && !m.novo; })[0] || null;
  }
  // mesmo endereço, com outro mandato (null = hoje); mantém uf, ibge e lang
  H.url = function (id) {
    var u = new URL(location.href);
    if (id) u.searchParams.set("mandato", id); else u.searchParams.delete("mandato");
    var q = u.searchParams.toString();
    return (u.pathname.split("/").pop() || "index.html") + (q ? "?" + q : "");
  };
  function paraHoje() { location.replace(H.url(null)); }

  // ---------------------------------------------------------------- campo "Ver outro mandato"
  var nSel = 0;
  H.seletor = function (lugar, nivel, escolhido) {
    if (!lugar) return Promise.resolve(null);
    return H.mandatos(nivel).then(function (r) {
      if (!r.atual || r.lista.length < 2) { lugar.hidden = true; return r; }
      var id = "mandato-" + (++nSel), desde = r.lista[r.lista.length - 1].inicio.slice(0, 4);
      lugar.innerHTML = '<div class="mandato-box"><label id="' + id + '-rot" for="' + id + '"><span aria-hidden="true">🕰️ </span>' +
        EP.tr("Ver outro mandato", "See another term") + '</label><div class="mandato-campo"></div>' +
        '<p class="mandato-dica" id="' + id + '-dica">' + esc(EP.tr("O atual mostra quem está no cargo hoje. Os anteriores (desde " + desde + ") mostram quem foi eleito. Ao escolher, a página muda para o mandato escolhido.",
          "The current term shows who is in office today. Earlier terms (since " + desde + ") show who was elected. When you choose one, the page switches to that term.")) + "</p>" +
        (r.indice.fontes ? '<p class="mandato-fontes">' + EP.botaoFontes(r.indice.fontes, EP.tr("De onde vêm os mandatos?", "Where do the terms come from?")) + "</p>" : "") + "</div>";
      EP.combo(lugar.querySelector(".mandato-campo"), {
        id: id, rotuloId: id + "-rot", descricao: id + "-dica", max: 40, valor: escolhido || r.atual.id,
        placeholder: EP.tr("Escolha o mandato…", "Choose a term…"),
        itens: r.lista.map(function (m) { return { v: m.id, t: rotulo(m) + (m === r.atual ? EP.tr(" (atual)", " (current)") : "") }; }),
        aoEscolher: function (it) {
          var alvo = H.url(it.v === r.atual.id ? null : it.v);
          if (alvo !== H.url(H.param())) location.href = alvo;
        }
      });
      lugar.hidden = false;
      return r;
    }).catch(function () { lugar.hidden = true; return null; });
  };

  // ---------------------------------------------------------------- peças da página do passado
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
  // esconde de verdade (o atributo hidden sozinho perde para o display de classes como .chip e .grade-min)
  function esconde(x) { x.hidden = true; x.style.display = "none"; }
  // faixa que deixa claro (em texto, não só em cor) que a página mostra o passado
  H.faixa = function (m) {
    return '<div class="faixa-passado">' +
      '<p class="faixa-tit"><span aria-hidden="true">🕰️ </span><strong>' + esc(EP.tr("Você está vendo o passado: mandato de " + m.rotulo, "You are looking at the past: the " + m.rotulo_en + " term")) + "</strong></p>" +
      "<p>" + esc(EP.tr("Aqui aparece quem foi eleito para este mandato, segundo o TSE (Tribunal Superior Eleitoral), com o partido da eleição. Durante o mandato, algumas pessoas podem ter saído, e vices ou suplentes podem ter assumido.",
        "This shows the people elected for this term, according to the TSE (Brazil's Superior Electoral Court), with the party they had in the election. During the term, some may have left, and vices or alternates may have taken over.")) + "</p>" +
      (m.aviso ? "<p>" + D.aviso(m.aviso, m.aviso_en) + "</p>" : "") +
      '<p class="faixa-acoes"><a class="btn peq" href="' + esc(H.url(null)) + '"><span aria-hidden="true">⏩ </span>' + EP.tr("Voltar para hoje", "Back to today") + "</a></p></div>";
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
    el.innerHTML = '<div class="miolo"><div class="vazio"><span class="grande" aria-hidden="true">🛠️</span>' +
      EP.tr("Não conseguimos abrir este mandato agora. Tente de novo daqui a pouco.", "We could not open this term right now. Please try again in a little while.") +
      (link === false ? "" : '<p><a class="btn peq claro" href="' + esc(H.url(null)) + '">' + EP.tr("Voltar para hoje", "Back to today") + "</a></p>") + "</div></div>";
  }
  function data(iso) { return EP.dataLonga(iso); }
  function suplementarTxt(datas, cargoPt, cargoEn) {
    return (datas || []).map(function (d) {
      return EP.tr("Houve eleição suplementar para " + cargoPt + " em " + data(d) + ": quem foi eleito nela não aparece aqui.",
        "There was a special election for " + cargoEn + " on " + data(d) + ": whoever was elected in it is not shown here.");
    }).join(" ");
  }

  // cartão de quem governou (sem link: o perfil do site é de quem está no cargo hoje)
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
  // uma Casa (plenário por partido + filtros + lista), com os cartões sem link e o "Você sabia?" do passado
  function casa(el, membros, o) {
    if (!el) return;
    EP.montaCasa(el, {
      membros: membros || [], nomes: o.nomes, fonte: o.fonte, filtroUF: o.filtroUF === true ? undefined : false, nivel: o.nivel || 3,
      cartao: H.cartao, extra: o.extra, sabia: sabia, vazio: o.vazio,
      titPartidos: EP.tr("Quantos de cada partido (partido na eleição)", "Seats per party (party at the election)")
    });
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
  function rev(raiz) { EP.revelar(raiz); }

  // ---------------------------------------------------------------- Brasil (brasil.html?mandato=2019)
  H.brasil = function (id) {
    document.documentElement.classList.add("modo-passado");
    return H.mandatos("brasil").then(function (r) {
      var m = doPassado(r, id);
      if (!m) return paraHoje();
      return EP.json(BASE + "brasil/" + m.id + ".json").then(function (d) { brasil(m, d); });
    }).catch(function () { falhou(document.getElementById("exec-topo")); });
  };
  function brasil(m, d) {
    var main = document.getElementById("conteudo"), cab = main.querySelector(".cab-pagina");
    D.canonico({ mandato: m.id });
    poeTitulo(EP.tr("A política do Brasil de " + m.rotulo + ": presidente, senadores e deputados federais eleitos | Entenda Política",
      "Brazil's politics, " + m.rotulo_en + ": the elected President, senators and federal deputies | Understand Politics"),
    EP.tr("Quem foi eleito no Brasil para o mandato de " + m.rotulo + ": presidente, vice, os senadores e os deputados federais. Segundo o TSE, com fonte.",
      "Who was elected in Brazil for the " + m.rotulo_en + " term: the President, the Vice President, the senators and the federal deputies. According to the TSE, with sources."));
    poeOnde(EP.tr("A política do Brasil (" + m.rotulo + ")", "Brazil's politics (" + m.rotulo_en + ")"));
    poeTexto(cab.querySelector(".selo-topo"), EP.tr("Quem foi eleito no mandato de " + m.rotulo, "Who was elected for the " + m.rotulo_en + " term"));
    poeTexto(cab.querySelector("h1"), esc(EP.tr("A política do Brasil", "Brazil's politics")) + ' <span class="h1-periodo">' + esc(periodo(m)) + "</span>", true);
    poeTexto(cab.querySelector(".lead"), EP.tr("Aqui você vê quem foi eleito para governar e para fazer as leis do país no mandato de " + m.rotulo + ": o presidente, o vice, os senadores e os deputados federais.",
      "Here you can see who was elected to govern and to make the country's laws in the " + m.rotulo_en + " term: the President, the Vice President, the senators and the federal deputies."));
    var lugar = document.getElementById("mandato-lugar");
    if (!lugar) { cab.insertAdjacentHTML("afterend", '<div class="miolo mandato-lugar" id="mandato-lugar"></div>'); lugar = document.getElementById("mandato-lugar"); }
    lugar.insertAdjacentHTML("beforebegin", '<div class="miolo passado-faixa">' + H.faixa(m) + "</div>");
    H.seletor(lugar, "brasil", m.id);
    // o que só existe para o mandato de hoje (ministros, busca, votações...) fica escondido
    var fica = { executivo: 1, senado: 1, camara: 1, judiciario: 1 };
    [].forEach.call(main.children, function (x) {
      if (x === cab || x === lugar || x.classList.contains("passado-faixa") || x.classList.contains("atalhos") || fica[x.id]) return;
      esconde(x);
    });
    [].forEach.call(main.querySelectorAll(".atalhos a[href^='#']"), function (a) { if (!fica[a.getAttribute("href").slice(1)]) esconde(a); });
    var chipGov = main.querySelector('.atalhos a[href="#executivo"] span:last-child');
    poeTexto(chipGov, EP.tr("Quem governou", "Who governed"));
    // quem governou
    var ex = document.getElementById("executivo");
    poeTexto(ex.querySelector("#t-exec"), EP.tr("Quem governou o país", "Who governed the country"));
    poeTexto(ex.querySelector(".cab-bloco p"), EP.tr("O Poder Executivo: o presidente e o vice eleitos para o mandato de " + m.rotulo + ".",
      "The executive branch: the President and the Vice President elected for the " + m.rotulo_en + " term."));
    var p = d.presidente, v = d.vice, f = fontes(p, v);
    document.getElementById("exec-topo").innerHTML = (cartaoGrande(p, EP.tr("Presidente", "President")) + cartaoGrande(v, EP.tr("Vice-presidente", "Vice President")) ||
      '<div class="vazio">' + EP.tr("O TSE não mostra quem foi eleito presidente.", "The TSE does not show who was elected President.") + "</div>") +
      (d.nota ? '<p class="nota-hist">' + D.aviso(d.nota, d.nota_en) + "</p>" : "") +
      (f.length ? '<p class="fontes-exec">' + EP.botaoFontes(f) + "</p>" : "");
    ["os-ministros", "ministros", "fonte-min"].forEach(function (i) {
      var x = document.getElementById(i);
      if (!x) return;
      esconde(x);
      if (i === "os-ministros" && x.nextElementSibling && x.nextElementSibling.tagName === "P") esconde(x.nextElementSibling);
    });
    document.getElementById("exec-topo").insertAdjacentHTML("afterend", mudancasHtml(d) +
      aviso(esc(EP.tr("Os ministros de governos anteriores ainda não aparecem aqui. Os ministros de hoje estão na página do mandato atual.",
        "Ministers of earlier governments are not shown here yet. Today's ministers are on the current term's page.")), "👔"));
    // Senado e Câmara
    [["senado", d.senado, NOMES.sen(), eleitoEm], ["camara", d.camara, NOMES.dep(), null]].forEach(function (c) {
      var el = document.querySelector("#" + c[0] + " .casa-corpo"), b = c[1] || {};
      if (!el) return;
      el.insertAdjacentHTML("beforebegin", aviso(avisosDe(b)));
      casa(el, b.membros, { nomes: c[2], fonte: fontes(b), filtroUF: true, extra: c[3] });
    });
    D.rodapeErros(document.getElementById("links-erro"));
    rev(main);
    EP.paralaxe();
  }

  // ---------------------------------------------------------------- estado (estado.html?uf=BA&mandato=2019)
  H.estado = function (uf, id) {
    document.documentElement.classList.add("modo-passado");
    var el = document.getElementById("estado");
    el.hidden = false;
    el.innerHTML = '<div class="miolo"><div class="carregando">' + EP.tr("Carregando…", "Loading…") + "</div></div>";
    return H.mandatos("estados").then(function (r) {
      var m = doPassado(r, id);
      if (!m) return paraHoje();
      return Promise.all([EP.json(BASE + "estados/" + uf + ".json"), EP.json(BASE + "brasil/" + m.id + ".json").catch(function () { return null; })])
        .then(function (x) { estado(el, uf, m, ((x[0] || {}).mandatos || {})[m.id] || {}, x[1]); });
    }).catch(function () { falhou(el); });
  };
  function secao(id, ic, titulo, sub, corpo) {
    return '<section class="miolo bloco" id="' + id + '" aria-labelledby="t-' + id + '"><div class="cab-bloco rev"><span class="ic-bloco" aria-hidden="true">' + ic + '</span><div><h2 id="t-' + id + '">' + titulo + "</h2>" +
      (sub ? '<p class="muted">' + sub + "</p>" : "") + "</div></div>" + corpo + "</section>";
  }
  function chip(href, ic, txt) { return '<a class="chip" href="' + href + '"><span aria-hidden="true">' + ic + "</span><span>" + txt + "</span></a>"; }
  function estado(el, uf, m, e, br) {
    var nome = EP.UFS[uf], de = EP.doEstado(uf), ehDF = uf === "DF";
    D.canonico({ uf: uf, mandato: m.id });
    poeTitulo(EP.tr("A política " + de + " de " + m.rotulo + ": governador, senadores e deputados eleitos | Entenda Política",
      "Politics " + de + ", " + m.rotulo_en + ": the elected governor, senators and deputies | Understand Politics"),
    EP.tr("Quem foi eleito " + EP.noEstado(uf) + " para o mandato de " + m.rotulo + ": governador, vice, senadores, deputados federais e estaduais. Segundo o TSE, com fonte.",
      "Who was elected " + EP.noEstado(uf) + " for the " + m.rotulo_en + " term: governor, vice governor, senators, federal and state deputies. According to the TSE, with sources."));
    poeOnde(nome + " (" + rotulo(m) + ")");
    var g = e.governador, v = e.vice;
    var sen = br ? EP.alfabetica(((br.senado || {}).membros || []).filter(function (x) { return x.uf === uf; })) : null;
    var fed = br ? ((br.camara || {}).membros || []).filter(function (x) { return x.uf === uf; }) : null;
    var dep = e.deputados || {};
    var notasGov = [];
    if (!g) notasGov.push(esc(EP.tr("O TSE não mostra quem foi eleito governador nesta eleição.", "The TSE does not show who was elected governor in this election.")));
    if (g && !v && e.avisoVice) notasGov.push(D.aviso(e.avisoVice, e.avisoVice_en));
    if (e.suplementar) notasGov.push(esc(suplementarTxt(e.suplementar, "governador", "governor")));
    var fg = fontes(g, v);
    el.innerHTML =
      '<section class="miolo cab-pagina" aria-labelledby="titulo-uf"><div class="cab-txt rev"><span class="selo-topo">' + esc(EP.tr("A política " + de, "Politics " + de)) + "</span>" +
      '<h1 id="titulo-uf">' + esc(nome) + ' <span class="h1-periodo">' + esc(periodo(m)) + "</span></h1>" +
      '<p class="lead">' + esc(EP.tr("Quem foi eleito para governar, para representar " + (ehDF ? "o Distrito Federal" : "o estado") + " no Congresso e para fazer as leis " + de + " no mandato de " + m.rotulo + ".",
        "Who was elected to govern, to represent " + (ehDF ? "the Federal District" : "the state") + " in the National Congress and to make the laws " + de + " in the " + m.rotulo_en + " term.")) + "</p>" +
      '<p><a class="btn peq bege" href="estado.html"><span aria-hidden="true">🗺️ </span>' + EP.tr("Trocar de estado", "Choose another state") + "</a></p></div>" +
      '<div class="cab-3d rev pop" style="--i:1" aria-hidden="true">' + (window.TRES && TRES.predio ? TRES.predio() : "") + "</div></section>" +
      '<div class="miolo passado-faixa">' + H.faixa(m) + '<div class="mandato-lugar" id="mandato-lugar"></div></div>' +
      '<nav class="miolo atalhos rev" aria-label="' + EP.tr("Ir direto para", "Jump to") + '">' +
      chip("#governo", "🏢", EP.tr("Quem governou", "Who governed")) + chip("#senadores", "🏛️", EP.tr("Senadores", "Senators")) +
      chip("#federais", "🏛️", EP.tr("Deputados federais", "Federal deputies")) +
      chip("#estaduais", "🏛️", ehDF ? EP.tr("Deputados distritais", "District deputies") : EP.tr("Deputados estaduais", "State deputies")) + "</nav>" +
      secao("governo", "🏢", esc(EP.tr("Quem governou " + (ehDF ? "o Distrito Federal" : "o estado"), "Who governed " + (ehDF ? "the Federal District" : "the state"))),
        esc(EP.tr("O governador e o vice eleitos para o mandato de " + m.rotulo + ".", "The governor and the vice governor elected for the " + m.rotulo_en + " term.")),
        '<div class="exec-topo">' + cartaoGrande(g, EP.tr(EP.gen(g && g.genero, "Governador", "Governadora"), "Governor")) +
          cartaoGrande(v, EP.tr(EP.gen(v && v.genero, "Vice-governador", "Vice-governadora"), "Vice Governor")) + "</div>" +
          aviso(notasGov.join(" ")) + (fg.length ? '<p style="margin-top:12px">' + EP.botaoFontes(fg) + "</p>" : "")) +
      secao("senadores", "🏛️", esc(EP.tr("Os senadores " + de, "The senators " + (ehDF ? "for the Federal District" : "for " + nome))),
        esc(EP.tr("Os senadores eleitos " + EP.noEstado(uf) + " que estavam no mandato de " + m.rotulo + " (cada estado tem 3).",
          "The senators elected " + EP.noEstado(uf) + " who were serving in the " + m.rotulo_en + " term (each state has 3).")),
        (br ? aviso(avisosDe(br.senado || {}, uf)) : "") + '<div class="grade-pessoas" id="lista-sen">' +
          (sen ? sen.map(function (x) { return H.cartao(x, eleitoEm(x)); }).join("") || '<div class="vazio">' + EP.tr("O TSE não mostra senadores deste estado neste mandato.", "The TSE shows no senators for this state in this term.") + "</div>"
            : '<div class="vazio">' + EP.tr("Lista indisponível agora.", "This list is not available right now.") + "</div>") + "</div>" +
          (br && fontes(br.senado).length ? '<p class="fonte-casa">' + EP.botaoFontes(fontes(br.senado), EP.tr("De onde vem esta lista?", "Where does this list come from?")) + "</p>" : "")) +
      secao("federais", "🏛️", esc(EP.tr("Os deputados federais " + de, "The federal deputies " + (ehDF ? "for the Federal District" : "for " + nome))),
        esc(EP.tr("Eleitos " + EP.noEstado(uf) + " para a Câmara dos Deputados, em Brasília, no mandato de " + m.rotulo + ".",
          "Elected " + EP.noEstado(uf) + " to the Chamber of Deputies, in Brasília, for the " + m.rotulo_en + " term.")),
        (br ? aviso(avisosDe(br.camara || {})) : "") + '<div class="casa-corpo" id="casa-fed"></div>') +
      secao("estaduais", "🏛️", esc(ehDF ? EP.tr("A Câmara Legislativa: deputados distritais", "The Legislative Chamber: district deputies") :
        EP.tr("A Assembleia Legislativa: deputados estaduais", "The Legislative Assembly: state deputies")),
        esc(EP.tr("Eleitos para fazer as leis " + de + " e fiscalizar o governador no mandato de " + m.rotulo + ".",
          (ehDF ? "District deputies" : "State deputies") + " elected to make the laws " + de + " and oversee the governor in the " + m.rotulo_en + " term.")),
        aviso(D.aviso(dep.aviso, dep.aviso_en)) + '<div class="casa-corpo" id="casa-est"></div>') +
      (ehDF ? "" : '<section class="miolo bloco" aria-labelledby="t-cidades-passado"><h2 class="sub" id="t-cidades-passado"><span aria-hidden="true">🏘️ </span>' +
        EP.tr("E as cidades?", "What about the cities?") + "</h2><p>" +
        esc(EP.tr("Prefeitos e vereadores são eleitos em outros anos (1996, 2000, 2004...), por isso os mandatos das cidades são outros. Na página de cada cidade também dá para ver os mandatos anteriores.",
          "Mayors and city councilors are elected in other years (1996, 2000, 2004...), so city terms are different. Each city's page also lets you see earlier terms.")) +
        '</p><p><a class="btn claro peq" href="cidade.html' + (EP.en ? "?lang=en" : "") + '"><span aria-hidden="true">🏘️ </span>' + EP.tr("Ver a página das cidades", "Go to the cities page") + "</a></p></section>");
    H.seletor(document.getElementById("mandato-lugar"), "estados", m.id);
    if (fed) casa(document.getElementById("casa-fed"), fed, { nomes: NOMES.dep(), fonte: fontes(br.camara) });
    else falhou(document.getElementById("casa-fed"), false);
    casa(document.getElementById("casa-est"), dep.membros, { nomes: ehDF ? NOMES.ddist() : NOMES.dest(), fonte: fontes(dep) });
    rev(el);
  }

  // ---------------------------------------------------------------- cidade (cidade.html?ibge=2927408&mandato=2021)
  H.cidade = function (caixa, ibge, uf, id, pronto) {
    document.documentElement.classList.add("modo-passado");
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
          cidade(caixa, ibge, uf, nome, m, x[0]);
          if (pronto) pronto();
        });
    }).catch(function () { falhou(caixa); });
  };
  function pessoaArr(a) { return a ? { nome: a[0], nomeCivil: a[1] || null, partido: a[2], genero: a[3] || null, turno: a[4] } : null; }
  function cidade(caixa, ibge, uf, nome, m, f) {
    var c = (f.cidades || {})[ibge], ano = f.eleicao;
    D.canonico({ ibge: ibge, mandato: m.id });
    poeTitulo(EP.tr("A política de " + nome + " (" + uf + ") de " + m.rotulo + ": prefeito, vice e vereadores eleitos | Entenda Política",
      "Politics in " + nome + " (" + uf + "), " + m.rotulo_en + ": the elected mayor, vice mayor and city councilors | Understand Politics"),
    EP.tr("Quem foi eleito em " + nome + " (" + uf + ") para o mandato de " + m.rotulo + ": prefeito, vice e vereadores. Segundo o TSE, com fonte.",
      "Who was elected in " + nome + " (" + uf + "), Brazil, for the " + m.rotulo_en + " term: mayor, vice mayor and city councilors. According to the TSE, with sources."));
    poeOnde(nome + " (" + rotulo(m) + ")");
    var cab = '<div class="cab-bloco rev"><span class="ic-bloco" aria-hidden="true">🏙️</span><div>' +
      '<h2 id="nome-cidade" tabindex="-1">' + esc(nome) + ' <span class="h1-periodo">' + esc(periodo(m)) + "</span></h2>" +
      '<p class="muted">' + esc(EP.tr("Uma cidade " + EP.doEstado(uf) + " (" + uf + ")", "A city in " + (EP.UFS[uf] || uf) + " (" + uf + "), Brazil")) + "</p></div></div>" +
      H.faixa(m) + '<div class="mandato-lugar" id="mandato-lugar"></div>';
    var links = '<section class="miolo bloco" aria-label="' + EP.tr("Ver mais", "See more") + '"><div class="links-cidade rev">' +
      '<a class="btn claro" href="estado.html?uf=' + uf + (EP.en ? "&lang=en" : "") + '"><span aria-hidden="true">📍 </span>' +
      esc(EP.tr("Ver a política " + EP.doEstado(uf), "See the politics " + EP.doEstado(uf))) + "</a>" +
      '<button class="btn bege" type="button" id="outra-cidade"><span aria-hidden="true">🔎 </span>' + EP.tr("Procurar outra cidade", "Search for another city") + "</button></div></section>";
    if (!c) {
      var prim = (f.depois || {})[ibge];
      var txt = prim ? EP.tr("No mandato de " + m.rotulo + ", " + nome + " ainda não era um município. Segundo o TSE, a primeira eleição de prefeito e vereadores da cidade foi em " + prim + ".",
        "In the " + m.rotulo_en + " term, " + nome + " was not a municipality yet. According to the TSE, the city's first election for mayor and city councilors was in " + prim + ".") :
        EP.tr("O TSE não tem dados de " + nome + " na eleição de " + ano + ".", "The TSE has no data on " + nome + " in the " + ano + " election.");
      caixa.innerHTML = '<section class="miolo bloco" aria-labelledby="nome-cidade">' + cab + '<div class="aviso azul"><span aria-hidden="true">ℹ️ </span>' + esc(txt) + "</div>" +
        '<p style="margin-top:10px">' + EP.botaoFontes(f.fonte) + "</p></section>" + links;
      H.seletor(document.getElementById("mandato-lugar"), "cidades", m.id);
      return;
    }
    var p = pessoaArr(c.p), v = pessoaArr(c.v), ver = (c.ver || []).map(function (x) { return { nome: x[0], partido: x[1], genero: x[2] || null }; });
    if (v && f.avisoPartidoVice && !v.partido) v.partidoTxt = EP.tr("não informado (veja o aviso abaixo)", "not given (see the note below)");
    function sitP(x) {
      return x ? "<small>" + esc(EP.tr(EP.gen(x.genero, "Eleito", "Eleita") + " no " + x.turno + "º turno", x.turno > 1 ? "Elected in the runoff" : "Elected in the first round")) + "</small>" : "";
    }
    function sitV(x) {
      return x && p ? "<small>" + esc(EP.tr(EP.gen(x.genero, "Eleito", "Eleita") + " na chapa de " + p.nome, "Elected on " + p.nome + "'s ticket")) + "</small>" : "";
    }
    var notas = [D.aviso(f.aviso, f.aviso_en)];
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
    caixa.innerHTML =
      '<section class="miolo bloco" aria-labelledby="nome-cidade">' + cab + aviso(notas.join(" ")) +
        '<h3 class="sub"><span aria-hidden="true">🏢 </span>' + EP.tr("Quem governou a cidade", "Who governed the city") + "</h3>" +
        '<div class="exec-topo">' + cartaoGrande(p, EP.tr(EP.gen(p && p.genero, "Prefeito", "Prefeita"), "Mayor"), sitP(p)) +
          cartaoGrande(v, EP.tr(EP.gen(v && v.genero, "Vice-prefeito", "Vice-prefeita"), "Vice Mayor"), sitV(v)) + "</div>" +
        aviso(notasP.join(" ")) + '<p style="margin-top:8px">' + EP.botaoFontes(f.fonte) + "</p></section>" +
      '<section class="miolo bloco" aria-labelledby="t-camara-mun"><div class="cab-bloco rev"><span class="ic-bloco" aria-hidden="true">🏛️</span><div>' +
        '<h2 id="t-camara-mun">' + EP.tr("A Câmara Municipal", "The City Council") + " <small>(" + EP.num(n) + " " + EP.tr(n === 1 ? "vereador eleito" : "vereadores eleitos", n === 1 ? "elected councilor" : "elected councilors") + ")</small></h2>" +
        '<p class="muted">' + EP.tr("Os vereadores eleitos para fazer as leis da cidade e fiscalizar o prefeito no mandato de " + esc(m.rotulo) + ".",
          "The city councilors (<span lang=\"pt-BR\">vereadores</span>) elected to make the city's laws and oversee the mayor in the " + esc(m.rotulo_en) + " term.") + "</p></div></div>" +
        aviso(notasV.join(" ")) + '<div id="casa-ver"></div></section>' + links;
    H.seletor(document.getElementById("mandato-lugar"), "cidades", m.id);
    casa(document.getElementById("casa-ver"), ver, { nomes: NOMES.ver(), fonte: f.fonte,
      vazio: EP.tr("O TSE não mostra os vereadores eleitos nesta eleição.", "The TSE does not show the city councilors elected in this election.") });
  }
})();
