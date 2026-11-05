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
    el.innerHTML = '<div class="miolo"><div class="vazio"><span class="grande" aria-hidden="true">⚠️</span>' +
      EP.tr("Não foi possível carregar " + pt + " agora. Tente de novo daqui a pouco.", "Could not load " + en + " right now. Please try again in a little while.") + "</div></div>";
  }
  function aviso(html) { return html ? '<p class="aviso"><span aria-hidden="true">ℹ️ </span>' + html + "</p>" : ""; }
  // prefeitos 2026: quem a ficha mostrava como prefeito(a) pediu registro de candidatura em 2026 e não há pesquisa à mão
  // feita depois do prazo para deixar o cargo (scripts/tse.py, deixou_prefeitura): no lugar da pessoa, um cartão que diz
  // isso e leva ao site oficial da prefeitura, onde se vê quem governa hoje
  function naoConferido(p) { return !!(p && !p.nome && !p.vago && p.deixou); }
  function cartaoNaoConferido(p, c) {
    var d = p.deixou || {}, site = ((c.onde || {}).prefeitura || {}).site;
    return '<div class="pessoa-grande"><span class="av av-letra" aria-hidden="true">?</span><span><span class="cargo">' +
      EP.tr("Prefeito(a)", "Mayor") + "</span><b>" + EP.tr("Quem governa hoje: não conferido", "Current mayor: not checked") + "</b>" +
      (d.txt ? "<small>" + D.traduz(d.txt, null, d.txt_en) + "</small>" : "") +
      (/^https?:\/\//.test(site || "") ? '<small style="margin-top:6px"><a href="' + esc(site) + '" target="_blank" rel="noopener" hreflang="pt-BR">' +
        EP.tr("Ver no site oficial da prefeitura", "See the city government's official website") + ' <span aria-hidden="true">↗</span><span class="sr"> ' +
        EP.tr("(abre em outra aba)", "(opens in a new tab)") + "</span></a></small>" : "") + "</span></div>";
  }
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
  // o ano da eleição do mandato de prefeito em curso: a eleição municipal (anos 0, 4, 8...) cuja posse (1º de janeiro) já aconteceu
  function anoEleicaoMunicipal() {
    var h = new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10), a = +h.slice(0, 4);
    for (var y = a; y > a - 8; y--) if (y % 4 === 0 && (y + 1) + "-01-01" <= h) return y;
    return a;
  }

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
    // ui-r9: com uma cidade já na tela (em abas), escolher outra abre a página dela (endereço novo, o Voltar volta para a anterior)
    aoEscolher: function (it) {
      if (!document.getElementById("cidade").hidden && document.querySelector("#cidade .abas-ep")) {
        try { sessionStorage.setItem("ep-foca-cidade", "1"); } catch (e) {}
        location.href = "cidade.html?ibge=" + it.v + (mandato ? "&mandato=" + mandato : "") + (EP.en ? "&lang=en" : "");
        return;
      }
      abre(it.v, true);
    }
  });

  // ---------------------------------------------------------------- uma cidade
  // mandato anterior (cidade.html?ibge=...&mandato=2021): a cidade aparece como era nele (js/historico.js); trocar de cidade mantém o mandato
  var mandato = EP.hist ? EP.hist.param() : null;
  function abre(ibge, focar) {
    var caixa = document.getElementById("cidade");
    caixa.hidden = false;
    var mand = ibge === BRASILIA || ibge === NORONHA ? null : mandato;
    // ui-r9: a mesma cidade (ao abrir a página) guarda o resto do endereço: a aba (#camara-mun), os filtros e a memória do
    // histórico (EP.memo); outra cidade começa um endereço limpo
    try {
      var u = new URL(location.href), mesma = u.searchParams.get("ibge") === String(ibge);
      if (!mesma) u = new URL("cidade.html", location.href);
      u.searchParams.set("ibge", ibge);
      if (mand) u.searchParams.set("mandato", mand); else u.searchParams.delete("mandato");
      if (EP.en) u.searchParams.set("lang", "en");
      history.replaceState(mesma ? history.state : null, "", u.pathname.split("/").pop() + u.search + (mesma ? location.hash : ""));
    } catch (e) {}
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
    if (mand) return EP.hist.cidade(caixa, ibge, uf, mand, { esqueleto: esqueleto, pronto: function () { depois(caixa, focar); } });
    EP.json("dados/cidades/" + uf + "/" + ibge + ".json").then(function (c) { desenha(caixa, c, uf, focar); })
      .catch(function () { falhou(caixa, "os dados desta cidade", "the data for this city"); });
  }

  // ---------------------------------------------------------------- a página de uma cidade (hoje e nos mandatos anteriores)
  // ui-r9: o nome da cidade, o "Ver outro mandato" e os avisos ficam em cima; embaixo, as abas (js/abas.js): quem governa, a
  // Câmara Municipal, a próxima eleição e "Quem faz o quê" (cidade.html?ibge=...#camara-mun). mandatos-r11: o mesmo esqueleto
  // para todos os mandatos (js/historico.js usa este também); só os dados mudam.
  // x = { nome, uf, periodo?, avisos?, gov (cartões), govNotas?, semCidade? (a cidade ainda não existia: o aviso vai em govNotas),
  // nTxt?, camDesc?, camAviso?, info?, proxima? (HTML da aba; sem ela, "A próxima eleição" de hoje, do js/proximos.js) }.
  // Devolve { quando(secao, fn) }: roda fn quando a aba abre.
  function esqueleto(caixa, x) {
    var uf = x.uf;
    // site-d-r16 (protótipo D): os números grandes (o ano da eleição do mandato, os 4 anos de mandato e quantos vereadores), o
    // prefeito e o vice em moldura (css/d.css), a Câmara com o plenário em ordem alfabética e a gaveta do partido (js/casa.js),
    // a aba "Como votaram" (js/votacoes.js) e o "Onde ver mais" em cartões. O mesmo em todo mandato.
    EP.casaD = true;
    var ano = x.ano || (mandato ? +mandato - 1 : anoEleicaoMunicipal());
    var CF0 = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm";
    var fk = [{ veiculo: "Planalto", titulo: EP.tr("Constituição Federal, art. 29 (prefeito, vice e vereadores: eleição, mandato de 4 anos e número de vereadores)",
      "Federal Constitution, art. 29 (mayor, vice mayor and city councilors: election, 4-year term and number of councilors)"), url: CF0, data: "1988-10-05", lang: EP.en ? "en" : undefined },
      { veiculo: "Tribunal Superior Eleitoral (TSE)", titulo: EP.tr("Dados abertos: candidaturas e resultados de cada eleição", "Open data: candidates and results of each election"), url: "https://dadosabertos.tse.jus.br/dataset/?q=candidatos", data: null, lang: EP.en ? "en" : undefined }];
    var kpis = EP.d ? EP.d.kpis([
      { ic: "🗳️", n: ano, t: EP.tr("ano da eleição deste mandato", "year this term was elected") },
      { ic: "🏢", n: 4, t: EP.tr("anos de mandato do prefeito", "years in the mayor's term"), href: "#governo-cidade" },
      { ic: "🏛️", n: x.nVer, t: EP.tr(x.nVer === 1 ? "vereador" : "vereadores", x.nVer === 1 ? "city councilor" : "city councilors"), href: "#camara-mun" }
    ], EP.tr(x.nome + " em números", x.nome + " in numbers"), "d-kpis-cidade") + '<p class="d-fonte-kpis">' + EP.botaoFontes(fk, EP.tr("De onde vêm estes números?", "Where do these numbers come from?")) + "</p>" : "";
    caixa.innerHTML =
      '<div class="miolo cidade-cab"><div class="cab-bloco rev"><span class="ic-bloco" aria-hidden="true">🏙️</span><div>' +
        '<h2 id="nome-cidade" tabindex="-1">' + esc(x.nome) + (x.periodo ? ' <span class="h1-periodo">' + esc(x.periodo) + "</span>" : "") + "</h2>" +
        '<p class="muted">' + esc(EP.tr("Uma cidade " + EP.doEstado(uf) + " (" + uf + ")", "A city in " + (EP.UFS[uf] || uf) + " (" + uf + "), Brazil")) + "</p></div></div>" +
        '<div class="d-numeros" id="numeros-cid">' + kpis + "</div>" +
        '<div class="mandato-lugar" id="mandato-lugar"></div>' + (x.avisos || "") + "</div>" +
      '<nav class="miolo atalhos" aria-label="' + EP.tr("Ir direto para", "Jump to") + '">' +
        '<a class="chip" href="#governo-cidade"><span aria-hidden="true">🏢</span><span>' + EP.tr("Quem governa", "Who governs") + "</span></a>" +
        '<a class="chip" href="#camara-mun"><span aria-hidden="true">🏛️</span><span>' + EP.tr("Câmara Municipal", "City Council") + "</span></a>" +
        '<a class="chip" href="#votacoes"><span aria-hidden="true">🗳️</span><span>' + EP.tr("Como votaram", "How they voted") + "</span></a>" +
        '<a class="chip" href="#proxima-eleicao"><span aria-hidden="true">🗳️</span><span>' + EP.tr("A próxima eleição", "The next election") + "</span></a>" +
        '<a class="chip" href="#papeis"><span aria-hidden="true">🦉</span><span>' + EP.tr("Quem faz o quê", "Who does what") + "</span></a></nav>" +
      '<section class="miolo bloco" id="governo-cidade" aria-labelledby="t-gov-cid"><div class="cab-bloco rev"><span class="ic-bloco" aria-hidden="true">🏢</span><div>' +
        '<h2 id="t-gov-cid">' + EP.tr("Quem governa a cidade", "Who governs the city") + "</h2>" +
        '<p class="muted">' + EP.tr("O prefeito e o vice comandam a prefeitura, o governo da cidade.", "The mayor and the vice mayor lead the city government.") + "</p></div></div>" +
        (x.gov ? '<div class="exec-topo">' + x.gov + "</div>" : x.semCidade ? "" : '<div class="vazio">' + EP.tr("O TSE não mostra quem governa esta cidade.", "The TSE does not show who governs this city.") + "</div>") +
        (x.govNotas || "") + (x.govMais || "") + "</section>" +
      '<section class="miolo bloco" id="camara-mun" aria-labelledby="t-camara-mun"><div class="cab-bloco rev"><span class="ic-bloco" aria-hidden="true">🏛️</span><div>' +
        '<h2 id="t-camara-mun">' + EP.tr("A Câmara Municipal", "The City Council") + (x.nTxt ? " <small>(" + x.nTxt + ")</small>" : "") + "</h2>" +
        '<p class="muted">' + (x.camDesc || EP.tr("Os vereadores fazem as leis da cidade e fiscalizam o prefeito.", "City councilors (<span lang=\"pt-BR\">vereadores</span>) make the city's laws and oversee the mayor.")) + "</p></div></div>" +
        (x.camAviso || "") + '<div id="casa-ver"></div>' + (x.info || "") + (x.camMais || "") + "</section>" +
      // site-d-r16: o voto de cada vereador, onde a Câmara publica (js/votacoes.js)
      '<section class="miolo bloco" id="votacoes" aria-labelledby="t-votacoes-cid"><div class="cab-bloco rev"><span class="ic-bloco" aria-hidden="true">🗳️</span><div>' +
        '<h2 id="t-votacoes-cid">' + EP.tr("Como votaram na Câmara Municipal", "How the City Council voted") + "</h2>" +
        '<p class="muted">' + EP.tr("Em cada votação, os vereadores dizem Sim ou Não a uma proposta. Aqui aparece o voto de cada um, quando a Câmara publica.",
          "In each vote, the city councilors say Yes or No to a proposal. This shows each one's vote, when the council publishes it.") + "</p></div></div>" +
        '<div class="recentes-vot" id="vot-casa">' + (x.votacoes || '<div class="carregando">' + EP.tr("Carregando…", "Loading…") + "</div>") + "</div></section>" +
      // a próxima eleição da cidade e as eleições suplementares (js/proximos.js)
      '<section class="miolo bloco" id="proxima-eleicao" aria-labelledby="t-proxima-eleicao"><div class="cab-bloco rev"><span class="ic-bloco" aria-hidden="true">🗳️</span><div>' +
        '<h2 id="t-proxima-eleicao">' + EP.tr("A próxima eleição", "The next election") + "</h2>" +
        '<p class="muted">' + EP.tr("Quando a cidade escolhe de novo o prefeito, o vice e os vereadores.", "When the city chooses its mayor, vice mayor and city councilors again.") + "</p></div></div>" +
        (x.proxima || '<div id="proximos-cidade"><div class="carregando">' + EP.tr("Carregando…", "Loading…") + "</div></div>") + "</section>" +
      '<section class="miolo bloco" aria-label="' + EP.tr("Ver mais", "See more") + '"><div class="links-cidade rev">' +
        '<a class="btn claro" href="estado.html?uf=' + uf + (EP.en ? "&lang=en" : "") + '"><span aria-hidden="true">📍 </span>' +
          esc(EP.tr("Ver a política " + EP.doEstado(uf), "See the politics " + EP.doEstado(uf))) + "</a>" +
        '<button class="btn bege" type="button" id="outra-cidade"><span aria-hidden="true">🔎 </span>' + EP.tr("Procurar outra cidade", "Search for another city") + "</button></div></section>";
    if (EP.trilha) EP.trilha([{ t: EP.UFS[uf] || uf, href: "estado.html?uf=" + uf }, { t: x.nome, lang: EP.en ? "pt-BR" : null }]);
    var comAbas = !!(EP.abas && EP.abas.monta({ nav: caixa.querySelector("nav.atalhos") }));
    if (EP.desenhosAbas) EP.desenhosAbas(caixa, [["governo-cidade", "prefeitura"], ["camara-mun", "predio"], ["votacoes", "urna"], ["proxima-eleicao", "urna"]]);
    // um mandato que acabou: o site guarda só as votações de hoje (a aba fica no lugar e diz isso)
    if (mandato && !x.votacoes && EP.hist) document.getElementById("vot-casa").innerHTML = EP.hist.semDados("🗳️", esc(EP.tr(
      "O site guarda as votações só do mandato de hoje, e só das Câmaras que publicam o voto de cada vereador. As votações deste mandato estão no site oficial da Câmara.",
      "The site keeps votes only for today's term, and only from the councils that publish each councilor's vote. The votes of this term are on the City Council's official website.")),
    [EP.hist.link("🗳️", EP.hist.hojeEm("votacoes"), EP.tr("Ver as votações de hoje", "See today's votes"))]);
    return { quando: function (secao, fn) { if (comAbas) EP.abas.quandoAbrir(secao, fn); else fn(); } };
  }

  function desenha(caixa, c, uf, focar) {
    var v = c.vereadores || {}, p = c.prefeito, vi = c.vice, n = (v.membros || []).length;
    poeTitulo(EP.tr("A política de " + c.nome + " (" + uf + "): prefeito, vice e vereadores | Entenda Política",
      "Politics in " + c.nome + " (" + uf + "): mayor, vice mayor and city councilors | Understand Politics"),
    EP.tr("Quem governa " + c.nome + " (" + uf + ") e quem faz as leis da cidade: prefeito, vice e vereadores. Tudo com fonte.",
      "Who governs " + c.nome + " (" + uf + "), Brazil, and who makes the city's laws: the mayor, the vice mayor and the city councilors. Everything with sources."), c.nome);
    function sit(x) { return x && x.situacao ? "<small>" + D.situacao(x.situacao, x.situacao_en) + "</small>" : ""; }
    var nc = naoConferido(p);  // prefeitos 2026
    var conferir = !nc && ((p && p.aConfirmar) || (vi && vi.aConfirmar));
    var fp = fontesDe(c, p, vi);
    // site-d-r16: leis e vetos do prefeito (o arquivo só é baixado quando o bloco abre) e "Onde ver mais" (os sites oficiais
    // do mapa das Câmaras e prefeituras, dados/municipios, que o montar.py põe em c.onde)
    var onde = c.onde || {}, pf = onde.prefeitura || {}, cm = onde.camara || {}, info = v.infoCasa || {};
    var govMais = (!nc && p ? EP.leisVetosD(p, EP.tr(EP.gen(p.genero, "o prefeito", "a prefeita"), "mayor")) : "") +
      EP.ondeVerD([{ ic: "🏢", t: EP.tr("Site da prefeitura", "City government website"), href: pf.site },
        { ic: "💰", t: EP.tr("Portal da transparência", "Transparency portal"), href: pf.transparencia },
        { ic: "📰", t: EP.tr("Diário Oficial", "Official Gazette"), href: (pf.diarioOficial || {}).url, sub: (pf.diarioOficial || {}).nome },
        { ic: "✉️", t: EP.tr("Pedir uma informação à prefeitura", "Ask the city government for information"), href: pf.sic, sub: EP.tr("Lei de Acesso à Informação", "Access to Information Law") }]);
    var camMais = info.cobertura ? "" : EP.ondeVerD([{ ic: "🏛️", t: EP.tr("Site da Câmara Municipal", "City Council website"), href: cm.site },
      { ic: "📜", t: EP.tr("As propostas no site da Câmara", "Proposals on the council's website"), href: cm.propostas },
      { ic: "✉️", t: EP.tr("Pedir uma informação à Câmara", "Ask the City Council for information"), href: cm.sic, sub: EP.tr("Lei de Acesso à Informação", "Access to Information Law") }]);
    var quando = esqueleto(caixa, {
      nome: c.nome, uf: uf, nVer: n,
      avisos: (nc ? '<p class="aviso"><span aria-hidden="true">⚠️ </span>' + D.aviso(c.aviso, c.aviso_en) + "</p>" : aviso(D.aviso(c.aviso, c.aviso_en))) +
        (conferir ? '<p class="aviso"><span aria-hidden="true">⚠️ </span>' + EP.tr("Estamos conferindo se quem aparece aqui ainda está no cargo.", "We are checking whether the people shown here are still in office.") + "</p>" : ""),
      gov: (nc ? cartaoNaoConferido(p, c) : EP.cartaoGrande(p, EP.tr(EP.gen(p && p.genero, "Prefeito", "Prefeita"), "Mayor"), sit(p))) +
        EP.cartaoGrande(vi, EP.tr(EP.gen(vi && vi.genero, "Vice-prefeito", "Vice-prefeita"), "Vice Mayor"), sit(vi)),
      govNotas: fp.length ? '<p style="margin-top:8px">' + EP.botaoFontes(fp) + "</p>" : "", govMais: govMais, camMais: camMais,
      nTxt: EP.num(n) + " " + EP.tr(n === 1 ? "vereador" : "vereadores", n === 1 ? "councilor" : "councilors"),
      camAviso: aviso(D.aviso(v.aviso, v.aviso_en)), info: EP.infoCasa(v.infoCasa)
    }).quando, comAbas = !!(EP.abas && EP.abas.ativa());
    // "Como votaram" (site-d-r16): as votações da Câmara com o voto de cada vereador, só quando a aba abre
    var vc = document.getElementById("vot-casa"), gente = [EP.tr("vereador", "city councilor"), EP.tr("vereadores", "city councilors")];
    var temVot = !!(info.cobertura || {}).votacoes, semVot = "";
    if (EP.VOT && vc) {
      var notasEn = EP.en && (info.notas_en || []).length === (info.notas || []).length && (info.notas_en || []).length;
      var notas = temVot ? [] : (notasEn ? info.notas_en : info.notas || []).filter(function (t) { return /vota|voto|vote|roll-call/i.test(t); })
        .map(function (t) { return EP.en && !notasEn ? EP.pt(esc(t)) : esc(t); });
      if (!info.cobertura && (cm.motivo || cm.motivo_en)) notas.push(EP.en && cm.motivo_en ? esc(cm.motivo_en) : EP.en ? EP.pt(esc(cm.motivo)) : esc(cm.motivo));
      semVot = EP.VOT.semVotosLocal({ casaHtml: EP.en ? (info.casa_en ? esc(info.casa_en) : EP.pt(esc(c.nome)) + " City Council") : esc(info.casa || "Câmara Municipal de " + c.nome),
        gente: gente, notas: notas, site: info.site || cm.site, sic: info.sic || cm.sic,
        vazioTxt: info.cobertura ? null : EP.tr("Este site não tem o voto de cada vereador desta Câmara: ela não está entre as Câmaras com dados abertos que o site lê.",
          "This site does not have each city councilor's vote in this council: it is not among the councils with open data that the site reads.") });
      if (temVot) quando("votacoes", function () { EP.VOT.casaLocal(vc, { arquivo: "dados/votacoes/camaras/" + c.ibge + ".json", gente: gente, semVotos: semVot }); });
      else vc.innerHTML = semVot;
    }
    quando("camara-mun", function () {
      EP.montaCasa(document.getElementById("casa-ver"), Object.assign({ membros: v.membros || [], filtroUF: false, fonte: v.fonte,
        atualizado: (v.oficial && (v.infoCasa || {}).conferido) || c.atualizado, nivel: 3,
        nomes: { um: EP.tr("vereador", "city councilor"), uma: EP.tr("vereadora", "city councilor"), varios: EP.tr("vereadores", "city councilors"), varias: EP.tr("vereadoras", "city councilors") },
        extra: function (m) {
          if (m.exercicio) return EP.tr(m.exercicio, m.exercicio_en || m.exercicio);  // suplente que assumiu a vaga
          return m.votos != null ? EP.tr(EP.num(m.votos) + " votos em 2024", EP.num(m.votos) + " votes in 2024") : "";
        } }, comAbas ? { lote: EP.RESUMO_CASA, verTodos: true } : {}));
    });
    if (EP.hist) EP.hist.seletor(document.getElementById("mandato-lugar"), "cidades");  // "Ver outro mandato" (js/historico.js)
    if (EP.eleitos) quando("proxima-eleicao", function () { EP.eleitos.cidade(document.getElementById("proximos-cidade"), c.ibge, uf, c.nome); });
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
  var focar0 = false;
  try { focar0 = sessionStorage.getItem("ep-foca-cidade") === "1"; sessionStorage.removeItem("ep-foca-cidade"); } catch (e) {}
  if (ibge0) { combo.escolhe(ibge0, true); abre(ibge0, focar0); }
  else D.canonico();
  EP.revelar();
  EP.paralaxe();
})();
