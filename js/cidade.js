/* A política da minha cidade: busca entre as 5.569 cidades (campo com autocomplete) e mostra prefeito, vice e vereadores.
   Endereço: cidade.html?ibge=2927408 (código IBGE da cidade, 7 dígitos).
   Lê dados/cidades.json (índice: [código, nome, UF]) e dados/cidades/UF/CODIGO.json (a cidade). */
(function () {
  "use strict";
  var EP = window.EP, D = EP.trd, esc = EP.esc;
  var CF = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm";
  var BRASILIA = "5300108", NORONHA = "2605459";

  function fonte(id, titulo, tituloEn, url, data) {
    var f = { id: id, veiculo: "Planalto", titulo: EP.tr(titulo, tituloEn + " (in Portuguese)"), url: url, data: data };
    if (EP.en) f.lang = "en";
    return f;
  }
  var F = {
    cf29: fonte("cf-art29", "Constituição Federal, art. 29 (prefeito, vice e vereadores: eleição, mandato e número de vereadores)",
      "Federal Constitution, art. 29 (mayor, vice mayor and city councilors: election, term and number of councilors)", CF, "1988-10-05"),
    cf30: fonte("cf-art30", "Constituição Federal, art. 30 (do que a cidade cuida)", "Federal Constitution, art. 30 (what cities take care of)", CF, "1988-10-05"),
    cf31: fonte("cf-art31", "Constituição Federal, art. 31 (a Câmara Municipal fiscaliza a prefeitura)", "Federal Constitution, art. 31 (the City Council oversees the city government)", CF, "1988-10-05"),
    cf32: fonte("cf-art32", "Constituição Federal, art. 32 (o Distrito Federal não pode ser dividido em municípios)", "Federal Constitution, art. 32 (the Federal District cannot be divided into municipalities)", CF, "1988-10-05"),
    adct15: fonte("adct-art15", "Ato das Disposições Constitucionais Transitórias, art. 15 (Fernando de Noronha volta a ser de Pernambuco)",
      "Transitional Constitutional Provisions Act, art. 15 (Fernando de Noronha becomes part of Pernambuco again)", CF, "1988-10-05"),
    l9504: fonte("lei-9504", "Lei nº 9.504/1997 (Lei das Eleições), art. 3º, § 1º (o vice é eleito junto com o prefeito)",
      "Law No. 9,504/1997 (Elections Law), art. 3, § 1 (the vice mayor is elected together with the mayor)", "https://www.planalto.gov.br/ccivil_03/leis/l9504.htm", "1997-09-30"),
    l11445: fonte("lei-11445", "Lei nº 11.445/2007 (saneamento básico), arts. 3º e 8º", "Law No. 11,445/2007 (basic sanitation), arts. 3 and 8",
      "https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2007/lei/l11445.htm", "2007-01-05"),
    l6766: fonte("lei-6766", "Lei nº 6.766/1979, art. 22 (ruas e praças passam a ser do município)", "Law No. 6,766/1979, art. 22 (streets and squares become property of the municipality)",
      "https://www.planalto.gov.br/ccivil_03/leis/l6766.htm", "1979-12-19")
  };

  function falhou(el, pt, en) {
    el.innerHTML = '<div class="miolo"><div class="vazio"><span class="grande" aria-hidden="true">🛠️</span>' +
      EP.tr("Ainda estamos juntando " + pt + ". Volte daqui a pouco.", "We are still gathering " + en + ". Please come back in a little while.") + "</div></div>";
  }
  function aviso(html) { return html ? '<p class="aviso"><span aria-hidden="true">ℹ️ </span>' + html + "</p>" : ""; }
  function fontesDe() {
    var l = [];
    [].forEach.call(arguments, function (p) { if (p) l = l.concat(p.fontes || p.fonte || []); });
    return l;
  }
  // título da aba, descrição e o "onde estou" do topo mudam com a cidade escolhida
  function poeTitulo(t, desc, onde) {
    var te = document.querySelector("title");
    if (te) te.removeAttribute("data-en");
    document.title = t;
    var m = document.querySelector('meta[name="description"]');
    if (m && desc) { m.removeAttribute("data-en-content"); m.setAttribute("content", desc); }
    var o = document.getElementById("onde");
    if (o && onde) { o.removeAttribute("data-en"); o.textContent = onde; }
  }
  function nomeUF(uf) { return (EP.UFS[uf] || uf) + " (" + uf + ")"; }

  // ---------------------------------------------------------------- busca de cidade
  var combo = EP.combo(document.getElementById("busca-cidade"), {
    id: "campo-cidade", rotuloId: "rotulo-cidade", descricao: "dica-cidade", classe: "grande", min: 2, max: 8,
    placeholder: EP.tr("Ex.: Salvador, Campinas, Bom Jesus…", "E.g.: Salvador, Campinas, Bom Jesus…"),
    dica: EP.tr("Digite pelo menos 2 letras do nome da cidade.", "Type at least 2 letters of the city's name."),
    nada: EP.tr("Nenhuma cidade com esse nome. Confira se está escrito certo.", "No city with that name. Check the spelling."),
    itens: function () {
      return EP.json("dados/cidades.json").then(function (l) {
        var itens = l.map(function (c) { return { v: c[0], t: c[1], sub: nomeUF(c[2]), busca: c[2] + " " + (EP.UFS[c[2]] || "") }; });
        // quem procura Brasília ou Fernando de Noronha também encontra (e entende por que não têm prefeito)
        itens.push({ v: BRASILIA, t: "Brasília", sub: nomeUF("DF"), busca: "DF distrito federal" });
        itens.push({ v: NORONHA, t: "Fernando de Noronha", sub: nomeUF("PE"), busca: "PE pernambuco ilha" });
        return itens.sort(function (a, b) { return EP.norm(a.t).localeCompare(EP.norm(b.t)) || a.sub.localeCompare(b.sub); });
      });
    },
    aoEscolher: function (it) { abre(it.v, true); }
  });

  // ---------------------------------------------------------------- uma cidade
  // mandato anterior (cidade.html?ibge=...&mandato=2021): a cidade aparece como era nele (js/historico.js); trocar de cidade mantém o mandato
  var mandato = EP.hist ? EP.hist.param() : null;
  function abre(ibge, focar) {
    var caixa = document.getElementById("cidade");
    caixa.hidden = false;
    var mand = ibge === BRASILIA || ibge === NORONHA ? null : mandato;
    try { history.replaceState(null, "", "cidade.html?ibge=" + ibge + (mand ? "&mandato=" + mand : "") + (EP.en ? "&lang=en" : "")); } catch (e) {}
    D.canonico({ ibge: ibge, mandato: mand });
    if (ibge === BRASILIA) return especial(caixa, "DF", focar);
    if (ibge === NORONHA) return especial(caixa, "PE", focar);
    var uf = EP.UF_IBGE[String(ibge).slice(0, 2)];
    if (!uf || uf === "DF" || !/^\d{7}$/.test(ibge)) {
      caixa.innerHTML = '<div class="miolo"><div class="vazio"><span class="grande" aria-hidden="true">🤷</span>' +
        EP.tr("Não encontramos essa cidade. Procure pelo nome no campo acima.", "We could not find that city. Search for it by name above.") + "</div></div>";
      return;
    }
    caixa.innerHTML = '<div class="miolo"><div class="carregando">' + EP.tr("Carregando…", "Loading…") + "</div></div>";
    if (mand) return EP.hist.cidade(caixa, ibge, uf, mand, function () { depois(caixa, focar); });
    EP.json("dados/cidades/" + uf + "/" + ibge + ".json").then(function (c) { desenha(caixa, c, uf, focar); })
      .catch(function () { falhou(caixa, "os dados desta cidade", "the data for this city"); });
  }

  function desenha(caixa, c, uf, focar) {
    var v = c.vereadores || {}, p = c.prefeito, vi = c.vice, n = (v.membros || []).length;
    poeTitulo(EP.tr("A política de " + c.nome + " (" + uf + "): prefeito, vice e vereadores | Entenda Política",
      "Politics in " + c.nome + " (" + uf + "): mayor, vice mayor and city councilors | Understand Politics"),
    EP.tr("Quem governa " + c.nome + " (" + uf + ") e quem faz as leis da cidade: prefeito, vice e vereadores. Tudo com fonte.",
      "Who governs " + c.nome + " (" + uf + "), Brazil, and who makes the city's laws: the mayor, the vice mayor and the city councilors. Everything with sources."), c.nome);
    function sit(x) { return x && x.situacao ? "<small>" + D.situacao(x.situacao, x.situacao_en) + "</small>" : ""; }
    var conferir = (p && p.aConfirmar) || (vi && vi.aConfirmar);
    var fp = fontesDe(c, p, vi);
    caixa.innerHTML =
      '<section class="miolo bloco" aria-labelledby="nome-cidade"><div class="cab-bloco rev"><span class="ic-bloco" aria-hidden="true">🏙️</span><div>' +
        '<h2 id="nome-cidade" tabindex="-1">' + esc(c.nome) + "</h2>" +
        '<p class="muted">' + esc(EP.tr("Uma cidade " + EP.doEstado(uf) + " (" + uf + ")", "A city in " + (EP.UFS[uf] || uf) + " (" + uf + "), Brazil")) + "</p></div></div>" +
        '<div class="mandato-lugar" id="mandato-lugar"></div>' +
        aviso(D.aviso(c.aviso, c.aviso_en)) +
        (conferir ? '<p class="aviso"><span aria-hidden="true">⚠️ </span>' + EP.tr("Estamos conferindo se quem aparece aqui ainda está no cargo.", "We are checking whether the people shown here are still in office.") + "</p>" : "") +
        '<h3 class="sub"><span aria-hidden="true">🏢 </span>' + EP.tr("Quem governa a cidade", "Who governs the city") + "</h3>" +
        '<div class="exec-topo">' + (EP.cartaoGrande(p, EP.tr(EP.gen(p && p.genero, "Prefeito", "Prefeita"), "Mayor"), sit(p)) +
          EP.cartaoGrande(vi, EP.tr(EP.gen(vi && vi.genero, "Vice-prefeito", "Vice-prefeita"), "Vice Mayor"), sit(vi)) ||
          '<div class="vazio">' + EP.tr("O TSE não mostra quem governa esta cidade.", "The TSE does not show who governs this city.") + "</div>") + "</div>" +
        (fp.length ? '<p style="margin-top:8px">' + EP.botaoFontes(fp) + "</p>" : "") + "</section>" +
      '<section class="miolo bloco" aria-labelledby="t-camara-mun"><div class="cab-bloco rev"><span class="ic-bloco" aria-hidden="true">🏛️</span><div>' +
        '<h2 id="t-camara-mun">' + EP.tr("A Câmara Municipal", "The City Council") + " <small>(" + EP.num(n) + " " + EP.tr(n === 1 ? "vereador" : "vereadores", n === 1 ? "councilor" : "councilors") + ")</small></h2>" +
        '<p class="muted">' + EP.tr("Os vereadores fazem as leis da cidade e fiscalizam o prefeito.", "City councilors (<span lang=\"pt-BR\">vereadores</span>) make the city's laws and oversee the mayor.") + "</p></div></div>" +
        aviso(D.aviso(v.aviso, v.aviso_en)) + '<div id="casa-ver"></div></section>' +
      '<section class="miolo bloco" aria-label="' + EP.tr("Ver mais", "See more") + '"><div class="links-cidade rev">' +
        '<a class="btn claro" href="estado.html?uf=' + uf + (EP.en ? "&lang=en" : "") + '"><span aria-hidden="true">📍 </span>' +
          esc(EP.tr("Ver a política " + EP.doEstado(uf), "See the politics " + EP.doEstado(uf))) + "</a>" +
        '<button class="btn bege" type="button" id="outra-cidade"><span aria-hidden="true">🔎 </span>' + EP.tr("Procurar outra cidade", "Search for another city") + "</button></div></section>";
    EP.montaCasa(document.getElementById("casa-ver"), { membros: v.membros || [], filtroUF: false, fonte: v.fonte, atualizado: c.atualizado, nivel: 3,
      nomes: { um: EP.tr("vereador", "city councilor"), uma: EP.tr("vereadora", "city councilor"), varios: EP.tr("vereadores", "city councilors"), varias: EP.tr("vereadoras", "city councilors") },
      extra: function (m) { return m.votos != null ? EP.tr(EP.num(m.votos) + " votos em 2024", EP.num(m.votos) + " votes in 2024") : ""; } });
    if (EP.hist) EP.hist.seletor(document.getElementById("mandato-lugar"), "cidades");  // "Ver outro mandato" (js/historico.js)
    depois(caixa, focar);
  }

  // Brasília (Distrito Federal) e Fernando de Noronha (distrito de Pernambuco) não têm prefeito nem vereadores
  function especial(caixa, uf, focar) {
    var df = uf === "DF", nome = df ? "Brasília" : "Fernando de Noronha";
    poeTitulo(EP.tr(nome + ": por que não tem prefeito | Entenda Política", nome + ": why there is no mayor | Understand Politics"), null, nome);
    var txt = df ?
      EP.tr("Brasília é a capital do Brasil e fica no Distrito Federal. O Distrito Federal não pode ser dividido em municípios: por isso, lá não tem prefeito nem vereadores. Quem governa é o governador do DF, e as leis são feitas pelos deputados distritais, na Câmara Legislativa.",
        "Brasília is Brazil's capital and is in the Federal District. The Federal District cannot be divided into municipalities, so it has no mayor and no city councilors. It is governed by the governor of the Federal District, and its laws are made by district deputies in the Legislative Chamber.") :
      EP.tr("Fernando de Noronha é um arquipélago que pertence a Pernambuco. Ele não é um município: é um distrito do estado. Por isso, não tem prefeito nem vereadores; quem cuida da ilha é o governo de Pernambuco.",
        "Fernando de Noronha is an archipelago that belongs to the state of Pernambuco. It is not a municipality: it is a district of the state. That is why it has no mayor and no city councilors; the island is run by the government of Pernambuco.");
    caixa.innerHTML = '<section class="miolo bloco" aria-labelledby="nome-cidade"><div class="cab-bloco rev"><span class="ic-bloco" aria-hidden="true">' + (df ? "⭐" : "🏝️") + "</span><div>" +
      '<h2 id="nome-cidade" tabindex="-1">' + esc(nome) + "</h2>" + '<p class="muted">' + esc(nomeUF(uf)) + "</p></div></div>" +
      '<div class="aviso azul"><span aria-hidden="true">ℹ️ </span>' + esc(txt) + "</div>" +
      '<p style="margin-top:10px">' + EP.botaoFontes([df ? F.cf32 : F.adct15]) + "</p>" +
      '<div class="links-cidade"><a class="btn" href="estado.html?uf=' + uf + (EP.en ? "&lang=en" : "") + '"><span aria-hidden="true">📍 </span>' +
        esc(EP.tr("Ver a política " + EP.doEstado(uf), "See the politics " + EP.doEstado(uf))) + "</a>" +
      '<button class="btn bege" type="button" id="outra-cidade"><span aria-hidden="true">🔎 </span>' + EP.tr("Procurar outra cidade", "Search for another city") + "</button></div></section>";
    depois(caixa, focar);
  }

  function depois(caixa, focar) {
    EP.revelar(caixa);
    var outra = document.getElementById("outra-cidade");
    if (outra) outra.addEventListener("click", function () {
      combo.foco();
      document.getElementById("busca-cidade").scrollIntoView({ behavior: EP.reduzido ? "auto" : "smooth", block: "center" });
    });
    if (focar) {
      var h = document.getElementById("nome-cidade");
      h.focus({ preventScroll: true });
      h.scrollIntoView({ behavior: EP.reduzido ? "auto" : "smooth", block: "start" });
    }
  }

  // ---------------------------------------------------------------- começar
  if (window.TRES && TRES.prefeitura) document.getElementById("prefeitura-3d").innerHTML = TRES.prefeitura({ auto: true });
  document.getElementById("fontes-papeis").innerHTML = EP.botaoFontes([F.cf29, F.cf30, F.cf31, F.l9504, F.l11445, F.l6766]);
  if (window.TRES) EP.fundo3d([["cubo", "5%", "14%", 40, 0, 0, 18], ["esfera", "92%", "10%", 36, 3, 0, 7], ["anel", "90%", "60%", 56, 2, 0, 20], ["esfera", "4%", "72%", 30, 6, 0, 8]], document.body);
  D.rodapeErros(document.getElementById("links-erro"));
  var ibge0 = (EP.param("ibge") || "").replace(/\D/g, "");
  if (ibge0) { combo.escolhe(ibge0, true); abre(ibge0, false); }
  else D.canonico();
  EP.revelar();
  EP.paralaxe();
})();
