/* A política do meu estado: mapa em quadradinhos, governador, bancada no Congresso, deputados estaduais e a cidade. */
(function () {
  "use strict";
  var EP = window.EP, D = EP.trd, esc = EP.esc;
  // [linha, coluna, região] de cada UF no mapa em quadradinhos
  var GRADE = {
    RR: [0, 2, "N"], AP: [0, 4, "N"],
    AM: [1, 1, "N"], PA: [1, 3, "N"], MA: [1, 4, "NE"], CE: [1, 5, "NE"], RN: [1, 6, "NE"],
    AC: [2, 0, "N"], RO: [2, 1, "N"], MT: [2, 2, "CO"], TO: [2, 3, "N"], PI: [2, 4, "NE"], PE: [2, 5, "NE"], PB: [2, 6, "NE"],
    MS: [3, 2, "CO"], GO: [3, 3, "CO"], DF: [3, 4, "CO"], BA: [3, 5, "NE"], AL: [3, 6, "NE"],
    SP: [4, 3, "SE"], MG: [4, 4, "SE"], ES: [4, 5, "SE"], SE: [4, 6, "NE"],
    PR: [5, 3, "S"], RJ: [5, 4, "SE"],
    SC: [6, 3, "S"], RS: [7, 3, "S"]
  };
  // cores com contraste de pelo menos 4,5:1 com o texto branco
  var REGIOES = { N: ["Norte", "North", "#0f766e"], NE: ["Nordeste", "Northeast", "#a15c00"], CO: ["Centro-Oeste", "Center-West", "#55689e"], SE: ["Sudeste", "Southeast", "#1f3a5f"], S: ["Sul", "South", "#7a6a55"] };
  var uf = (EP.param("uf") || "").toUpperCase();
  var cidade0 = EP.param("cidade");

  function falhou(el, pt, en) {
    el.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">🛠️</span>' +
      EP.tr("Ainda estamos juntando " + pt + ". Volte daqui a pouco.", "We are still gathering " + en + ". Please come back in a little while.") + "</div>";
  }
  // troca um texto que tinha tradução fixa no HTML (data-en) por um texto montado aqui
  function poeTexto(el, txt) { if (el) { el.removeAttribute("data-en"); el.textContent = txt; } }
  function poeTitulo(t, desc) {
    var te = document.querySelector("title");
    if (te) te.removeAttribute("data-en");
    document.title = t;
    var m = document.querySelector('meta[name="description"]');
    if (m && desc) { m.removeAttribute("data-en-content"); m.setAttribute("content", desc); }
  }
  function aviso(html) { return html ? '<p class="aviso"><span aria-hidden="true">ℹ️ </span>' + html + "</p>" : ""; }
  function fontesDe() {
    var l = [];
    [].forEach.call(arguments, function (p) { if (p) l = l.concat(p.fontes || p.fonte || []); });
    return l;
  }

  // ---------------------------------------------------------------- escolher o estado
  function mostraMapa() {
    D.canonico();
    document.getElementById("escolher").hidden = false;
    var mapa = document.getElementById("mapa");
    var ordem = Object.keys(GRADE).sort(function (a, b) { return GRADE[a][0] - GRADE[b][0] || GRADE[a][1] - GRADE[b][1]; });
    mapa.innerHTML = ordem.map(function (u) {
      var g = GRADE[u];
      return '<a class="tile-uf" href="estado.html?uf=' + u + '" style="grid-row:' + (g[0] + 1) + ";grid-column:" + (g[1] + 1) + ";--cor:" + REGIOES[g[2]][2] +
        '" aria-label="' + u + ", " + esc(EP.UFS[u]) + '" data-nome="' + esc(EP.UFS[u]) + '">' + u + "</a>";
    }).join("");
    var rot = document.getElementById("rotulo-uf");
    var dica = "👆 " + EP.tr("Passe o mouse sobre um estado para ver o nome", "Point to a state to see its name");
    rot.textContent = dica;
    function mostraNome(e) { var t = e.target.closest && e.target.closest(".tile-uf"); if (t) rot.textContent = "👆 " + t.getAttribute("data-nome"); }
    mapa.addEventListener("mouseover", mostraNome);
    mapa.addEventListener("focusin", mostraNome);
    mapa.addEventListener("mouseleave", function () { rot.textContent = dica; });
    document.getElementById("regioes").innerHTML = Object.keys(REGIOES).map(function (r) {
      return '<li><i style="background:' + REGIOES[r][2] + '" aria-hidden="true"></i>' + EP.tr(REGIOES[r][0], REGIOES[r][1]) + "</li>";
    }).join("");
    // lista: escolher e confirmar com o botão (trocar a opção sozinho não muda de página)
    var sel = document.getElementById("sel-uf");
    sel.insertAdjacentHTML("beforeend", Object.keys(EP.UFS).sort(function (a, b) { return EP.norm(EP.UFS[a]).localeCompare(EP.norm(EP.UFS[b])); })
      .map(function (u) { return '<option value="' + u + '">' + esc(EP.UFS[u]) + "</option>"; }).join(""));
    if (EP.en) document.getElementById("form-uf").insertAdjacentHTML("afterbegin", '<input type="hidden" name="lang" value="en">');
    if (window.TRES) EP.fundo3d([["cubo", "5%", "14%", 40, 0, 0, 18], ["esfera", "92%", "10%", 36, 3, 0, 7], ["anel", "90%", "60%", 56, 2, 0, 20], ["esfera", "4%", "72%", 30, 6, 0, 8]], document.body);
    EP.revelar();
  }

  // ---------------------------------------------------------------- página do estado
  function cartaoGrande(p, cargo, extra) {
    if (!p) return "";
    if (p.vago) {
      return '<div class="pessoa-grande"><span class="av av-letra" aria-hidden="true">–</span><span><span class="cargo">' + esc(cargo) + "</span><b>" + EP.tr("Cargo vago", "Vacant") + "</b>" +
        (p.txt || p.nota ? "<small>" + D.traduz(p.txt || p.nota, null, p.txt_en || p.nota_en) + "</small>" : "") + "</span></div>";
    }
    var desde = p.desde ? EP.tr("No cargo desde ", "In office since ") + EP.data(p.desde) : "";
    return '<a class="pessoa-grande rev" href="pessoa.html?id=' + encodeURIComponent(p.id) + '">' + EP.av(p.foto, p.nome, null, true) +
      '<span><span class="cargo">' + esc(cargo) + "</span><b>" + esc(p.nome) + "</b><small>" + [p.partido ? EP.pt(esc(p.partido)) : "", esc(desde)].filter(Boolean).join(" · ") + "</small>" +
      (extra || "") + EP.chip2026(p.eleicao2026, p.genero, true) +
      (p.comoAssumiu && !/^eleit/i.test(p.comoAssumiu) ? '<small style="margin-top:6px"><span aria-hidden="true">🔑 </span>' + D.traduz(p.comoAssumiu, null, p.comoAssumiu_en) + "</small>" : "") +
      (p.nota ? '<small style="margin-top:6px"><span aria-hidden="true">📝 </span>' + D.traduz(p.nota, null, p.nota_en) + "</small>" : "") +
      '<span class="ver">' + EP.tr("Ver mais", "See more") + ' <span aria-hidden="true">›</span></span></span></a>';
  }
  function secao(id, ic, titulo, sub, corpo) {
    return '<section class="miolo bloco" id="' + id + '" aria-labelledby="t-' + id + '"><div class="cab-bloco rev"><span class="ic-bloco" aria-hidden="true">' + ic + "</span><div><h2 id=\"t-" + id + '">' + titulo + "</h2>" +
      (sub ? '<p class="muted">' + sub + "</p>" : "") + "</div></div>" + corpo + "</section>";
  }
  function chipAtalho(href, ic, txt) { return '<a class="chip" href="' + href + '"><span aria-hidden="true">' + ic + "</span><span>" + txt + "</span></a>"; }

  function mostraEstado() {
    var nome = EP.UFS[uf], de = EP.doEstado(uf), ehDF = uf === "DF";
    poeTitulo(EP.tr("A política " + de + ": governador, deputados, prefeitos e vereadores | Entenda Política", "Politics " + de + ": governor, deputies, mayors and city councilors | Understand Politics"),
      EP.tr("Quem governa, quem representa e quem faz as leis " + de + ": governador, senadores, deputados federais e estaduais, prefeitos e vereadores. Tudo com fonte.",
        "Who governs, who represents and who makes the laws " + de + ": governor, senators, federal and state deputies, mayors and city councilors. Everything with sources."));
    poeTexto(document.getElementById("onde"), nome);
    D.canonico({ uf: uf });
    var el = document.getElementById("estado");
    el.hidden = false;
    el.innerHTML =
      '<section class="miolo cab-pagina" aria-labelledby="titulo-uf"><div class="cab-txt rev"><span class="selo-topo">' + esc(EP.tr("A política " + de, "Politics " + de)) + '</span><h1 id="titulo-uf">' + esc(nome) + "</h1>" +
      '<p class="lead" id="lead-uf">' + esc(EP.tr("Quem governa, quem representa " + (ehDF ? "o Distrito Federal" : "o estado") + " no Congresso e quem faz as leis " + de + ".",
        "Who governs, who represents " + (ehDF ? "the Federal District" : "the state") + " in the National Congress and who makes the laws " + de + ".")) + "</p>" +
      '<p><a class="btn peq bege" href="estado.html"><span aria-hidden="true">🗺️ </span>' + EP.tr("Trocar de estado", "Choose another state") + "</a></p></div>" +
      '<div class="cab-3d rev pop" style="--i:1" aria-hidden="true">' + (window.TRES ? TRES.predio() : "") + "</div></section>" +
      '<nav class="miolo atalhos rev" aria-label="' + EP.tr("Ir direto para", "Jump to") + '">' +
      chipAtalho("#governo", "🏢", EP.tr("Quem governa", "Who governs")) + chipAtalho("#senadores", "🏛️", EP.tr("Senadores", "Senators")) +
      chipAtalho("#federais", "🏛️", EP.tr("Deputados federais", "Federal deputies")) +
      chipAtalho("#estaduais", "🏛️", ehDF ? EP.tr("Deputados distritais", "District deputies") : EP.tr("Deputados estaduais", "State deputies")) +
      (ehDF ? "" : chipAtalho("#cidade", "🏘️", EP.tr("Minha cidade", "Cities"))) + "</nav>" +
      secao("governo", "🏢", esc(EP.tr("Quem governa " + (ehDF ? "o Distrito Federal" : "o estado"), "Who governs " + (ehDF ? "the Federal District" : "the state"))),
        esc(EP.tr("O governador e o vice comandam o Poder Executivo " + de + ".", "The governor and the vice governor lead the executive branch " + de + ".")),
        '<div class="exec-topo" id="gov"><div class="carregando">' + EP.tr("Carregando…", "Loading…") + '</div></div><div id="gov-nota"></div>') +
      secao("senadores", "🏛️", esc(EP.tr("Os senadores " + de, "The senators " + (ehDF ? "for the Federal District" : "for " + nome))),
        EP.tr(esc("Todo estado tem 3 senadores no Senado Federal, em Brasília."), "Every state, and the Federal District, has 3 senators in the Federal Senate (" + EP.pt("Senado Federal") + "), in Brasília."),
        '<div class="grade-pessoas" id="lista-sen"><div class="carregando">' + EP.tr("Carregando…", "Loading…") + "</div></div>") +
      secao("federais", "🏛️", esc(EP.tr("Os deputados federais " + de, "The federal deputies " + (ehDF ? "for the Federal District" : "for " + nome))),
        EP.tr(esc("Eles representam o povo " + de + " na Câmara dos Deputados, em Brasília."), "They represent the people " + esc(de) + " in the Chamber of Deputies (" + EP.pt("Câmara dos Deputados") + "), in Brasília."),
        '<div class="casa-corpo" id="casa-fed"><div class="carregando">' + EP.tr("Carregando…", "Loading…") + "</div></div>") +
      secao("estaduais", "🏛️", esc(ehDF ? EP.tr("A Câmara Legislativa: deputados distritais", "The Legislative Chamber: district deputies") :
        EP.tr("A Assembleia Legislativa: deputados estaduais", "The Legislative Assembly: state deputies")),
        esc(EP.tr("Eles fazem as leis " + de + " e fiscalizam o governador.", (ehDF ? "District deputies (the Federal District's legislators)" : "State deputies (Brazil's state legislators)") + " make the laws " + de + " and oversee the governor.")),
        '<div id="aviso-est"></div><div class="casa-corpo" id="casa-est"><div class="carregando">' + EP.tr("Carregando…", "Loading…") + "</div></div>") +
      (ehDF ? '<section class="miolo bloco" aria-label="' + EP.tr("Cidades", "Cities") + '"><div class="aviso azul" id="aviso-df"><span aria-hidden="true">ℹ️ </span>' +
        esc(EP.tr("O Distrito Federal não é dividido em cidades com prefeito e vereadores. Quem cuida dessas coisas é o próprio governo do DF, e as leis são feitas pela Câmara Legislativa.",
          "The Federal District is not divided into cities with mayors and city councilors. The Federal District's own government takes care of those things, and its laws are made by the Legislative Chamber.")) + "</div></section>" :
        secao("cidade", "🏘️", esc(EP.tr("Minha cidade", "Cities")), esc(EP.tr("Escolha a sua cidade para ver o prefeito, o vice e os vereadores.", "Choose a city to see its mayor, vice mayor and city councilors (vereadores).")),
          '<div id="aviso-cid"></div><div class="cidade-busca"><label for="busca-cidade">' + EP.tr("Digite o nome da sua cidade", "Type the name of a city") + "</label>" +
          '<div class="busca"><input type="search" id="busca-cidade" autocomplete="off" aria-describedby="dica-cidade" aria-controls="sugestoes"></div>' +
          '<p class="muted" id="dica-cidade" style="font-size:.85rem;margin:6px 0 0">' + EP.tr("Depois de digitar, use a seta para baixo para ir até as cidades encontradas.", "After typing, use the down arrow to move to the cities found.") + "</p>" +
          '<p class="sr" id="status-cidade" role="status" aria-live="polite"></p><ul class="sugestoes" id="sugestoes" aria-label="' + EP.tr("Cidades encontradas", "Cities found") + '"></ul></div>' +
          '<div class="cidade-caixa" id="cidade-caixa"></div>'));
    EP.revelar(el);

    // governo + Assembleia (arquivo do estado)
    EP.json("dados/estados/" + uf + ".json").then(function (e) {
      var g = e.governador, v = e.vice;
      document.getElementById("gov").innerHTML = (cartaoGrande(g, EP.tr(EP.gen(g && g.genero, "Governador", "Governadora"), "Governor")) +
        cartaoGrande(v, EP.tr(EP.gen(v && v.genero, "Vice-governador", "Vice-governadora"), "Vice Governor"))) ||
        '<div class="vazio">' + EP.tr("Ainda não temos os dados de quem governa este estado.", "We do not have data on who governs this state yet.") + "</div>";
      var notas = [];
      if ((g && g.aConfirmar) || (v && v.aConfirmar)) notas.push(EP.tr("Estamos conferindo se quem foi eleito em 2022 ainda está no cargo.", "We are checking whether the people elected in 2022 are still in office."));
      var fg = fontesDe(g, v);
      document.getElementById("gov-nota").innerHTML = (notas.length ? '<p class="aviso"><span aria-hidden="true">⚠️ </span>' + esc(notas.join(" ")) + "</p>" : "") +
        (fg.length ? '<p style="margin-top:12px">' + EP.botaoFontes(fg) + "</p>" : "");
      if (e.capital || e.municipios) {
        var bc = document.getElementById("busca-cidade");
        if (bc && e.capital) bc.placeholder = EP.tr("Ex.: ", "E.g.: ") + e.capital.nome;
        document.getElementById("lead-uf").insertAdjacentHTML("afterend", '<p class="muted">' +
          (e.capital ? '<span aria-hidden="true">🏙️ </span>' + EP.tr("Capital: ", "Capital: ") + "<b>" + esc(e.capital.nome) + "</b>" : "") +
          (e.municipios ? (e.capital ? " · " : "") + '<span aria-hidden="true">🏘️ </span>' + EP.num(e.municipios) + " " + EP.tr(e.municipios === 1 ? "município" : "municípios", e.municipios === 1 ? "municipality" : "municipalities") : "") + "</p>");
      }
      if (e.aviso) {
        var alvo = document.getElementById(uf === "DF" ? "aviso-df" : "aviso-cid");
        if (alvo && uf === "DF") alvo.innerHTML = '<span aria-hidden="true">ℹ️ </span>' + D.aviso(e.aviso, e.aviso_en);
        else if (alvo) alvo.innerHTML = aviso(D.aviso(e.aviso, e.aviso_en));
      }
      var de2 = e.deputadosEstaduais || {};
      if (de2.aviso) document.getElementById("aviso-est").innerHTML = aviso(D.aviso(de2.aviso, de2.aviso_en));
      var nomesE = uf === "DF" ? { um: EP.tr("deputado distrital", "district deputy"), uma: EP.tr("deputada distrital", "district deputy"), varios: EP.tr("deputados distritais", "district deputies"), varias: EP.tr("deputadas distritais", "district deputies") } :
        { um: EP.tr("deputado estadual", "state deputy"), uma: EP.tr("deputada estadual", "state deputy"), varios: EP.tr("deputados estaduais", "state deputies"), varias: EP.tr("deputadas estaduais", "state deputies") };
      EP.montaCasa(document.getElementById("casa-est"), { membros: de2.membros || [], nomes: nomesE, filtroUF: false, fonte: de2.fonte, atualizado: e.atualizado,
        extra: function (m) { return m.votos != null ? EP.tr(EP.num(m.votos) + " votos em 2022", EP.num(m.votos) + " votes in 2022") : ""; } });
      EP.revelar(el);
    }).catch(function () {
      falhou(document.getElementById("gov"), "os dados deste estado", "the data for this state");
      falhou(document.getElementById("casa-est"), "a lista de deputados estaduais", "the list of state deputies");
    });

    // senadores e deputados federais do estado
    EP.json("dados/senado.json").then(function (d) {
      var l = EP.alfabetica((d.membros || []).filter(function (m) { return m.uf === uf; }));
      document.getElementById("lista-sen").innerHTML = l.map(function (m) {
        return EP.cartaoPessoa(m, m.fimMandato ? EP.tr("Mandato até ", "Term ends in ") + String(m.fimMandato).slice(0, 4) : "");
      }).join("") || '<div class="vazio">' + EP.tr("Lista indisponível agora.", "This list is not available right now.") + "</div>";
      if (d.fonte) document.getElementById("lista-sen").insertAdjacentHTML("afterend", '<p class="fonte-casa">' + EP.botaoFontes(d.fonte, EP.tr("De onde vem esta lista?", "Where does this list come from?")) + "</p>");
    }).catch(function () { falhou(document.getElementById("lista-sen"), "a lista de senadores", "the list of senators"); });
    EP.json("dados/camara.json").then(function (d) {
      var l = (d.membros || []).filter(function (m) { return m.uf === uf; });
      EP.montaCasa(document.getElementById("casa-fed"), { membros: l, filtroUF: false, fonte: d.fonte, atualizado: d.atualizado,
        nomes: { um: EP.tr("deputado", "deputy"), uma: EP.tr("deputada", "deputy"), varios: EP.tr("deputados", "deputies"), varias: EP.tr("deputadas", "deputies") } });
    }).catch(function () { falhou(document.getElementById("casa-fed"), "a lista de deputados federais", "the list of federal deputies"); });

    if (!ehDF) ligaCidade();
  }

  // ---------------------------------------------------------------- cidade
  function ligaCidade() {
    var input = document.getElementById("busca-cidade"), sug = document.getElementById("sugestoes"), status = document.getElementById("status-cidade");
    var lista = null;
    function avisa(t) { if (status.textContent !== t) status.textContent = t; }
    var pronto = EP.json("dados/cidades/" + uf + ".json").then(function (l) {
      lista = l.map(function (c) { return { ibge: String(c.ibge), nome: c.nome, prefeito: c.prefeito, n: EP.norm(c.nome) }; });
      return lista;
    });
    function sugere() {
      var q = EP.norm(input.value);
      if (!lista || q.length < 2) { sug.innerHTML = ""; avisa(""); return; }
      var r = lista.filter(function (c) { return c.n.indexOf(q) > -1; }).sort(function (a, b) { return (a.n.indexOf(q) === 0 ? 0 : 1) - (b.n.indexOf(q) === 0 ? 0 : 1) || a.n.localeCompare(b.n); });
      var vis = r.slice(0, 8);
      sug.innerHTML = vis.length ? vis.map(function (c) {
        return '<li><button type="button" data-ibge="' + c.ibge + '"><b>' + esc(c.nome) + "</b>" + (c.prefeito ? "<br><small>" + EP.tr("Prefeito(a): ", "Mayor: ") + esc(c.prefeito) + "</small>" : "") + "</button></li>";
      }).join("") : '<li class="muted">' + esc(EP.tr("Nenhuma cidade com esse nome " + EP.noEstado(uf) + ".", "No city with that name " + EP.noEstado(uf) + ".")) + "</li>";
      avisa(!r.length ? EP.tr("Nenhuma cidade encontrada.", "No city found.") : r.length === 1 ? EP.tr("1 cidade encontrada.", "1 city found.") :
        r.length > vis.length ? EP.tr(EP.num(r.length) + " cidades encontradas. Mostrando as 8 primeiras.", EP.num(r.length) + " cities found. Showing the first 8.") :
          EP.tr(EP.num(r.length) + " cidades encontradas.", EP.num(r.length) + " cities found."));
    }
    var t = null;
    input.addEventListener("input", function () {
      clearTimeout(t);
      t = setTimeout(function () {
        pronto.then(sugere).catch(function () {
          sug.innerHTML = '<li class="muted">' + EP.tr("A lista de cidades ainda não está disponível.", "The list of cities is not available yet.") + "</li>";
          avisa(EP.tr("A lista de cidades ainda não está disponível.", "The list of cities is not available yet."));
        });
      }, 150);
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { var b = sug.querySelector("button"); if (b) { e.preventDefault(); b.focus(); } }
    });
    sug.addEventListener("keydown", function (e) {
      var bs = [].slice.call(sug.querySelectorAll("button")), i = bs.indexOf(document.activeElement);
      if (i < 0) return;
      if (e.key === "ArrowDown" && i < bs.length - 1) { e.preventDefault(); bs[i + 1].focus(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); (i > 0 ? bs[i - 1] : input).focus(); }
      else if (e.key === "Escape") { e.preventDefault(); input.focus(); }
    });
    sug.addEventListener("click", function (e) {
      var b = e.target.closest("[data-ibge]");
      if (!b) return;
      sug.innerHTML = "";
      avisa("");
      input.value = b.querySelector("b").textContent;
      abreCidade(b.getAttribute("data-ibge"), true);
    });
    pronto.catch(function () {});
    if (cidade0) pronto.then(function () {
      var c = lista.filter(function (x) { return x.ibge === cidade0; })[0];
      if (c) input.value = c.nome;
      abreCidade(cidade0, false);
      setTimeout(function () { document.getElementById("cidade").scrollIntoView({ behavior: EP.reduzido ? "auto" : "smooth" }); }, 400);
    }).catch(function () {});
  }

  function abreCidade(ibge, focar) {
    var caixa = document.getElementById("cidade-caixa");
    caixa.innerHTML = '<div class="carregando">' + EP.tr("Carregando…", "Loading…") + "</div>";
    try { history.replaceState(null, "", "estado.html?uf=" + uf + "&cidade=" + ibge + (EP.en ? "&lang=en" : "") + "#cidade"); } catch (e) {}
    D.canonico({ uf: uf, cidade: ibge });
    EP.json("dados/cidades/" + uf + "/" + ibge + ".json").then(function (c) {
      var v = c.vereadores || {}, p = c.prefeito, vi = c.vice;
      function sit(x) { return x && x.situacao ? "<small>" + D.situacao(x.situacao, x.situacao_en) + "</small>" : ""; }
      var conferir = (p && p.aConfirmar) || (vi && vi.aConfirmar);
      var fp = fontesDe(c, p, vi);
      caixa.innerHTML = '<h3 class="sub" id="nome-cidade" tabindex="-1"><span aria-hidden="true">🏙️ </span>' + esc(c.nome) + "</h3>" + aviso(D.aviso(c.aviso, c.aviso_en)) +
        (conferir ? '<p class="aviso"><span aria-hidden="true">⚠️ </span>' + EP.tr("Estamos conferindo se quem aparece aqui ainda está no cargo.", "We are checking whether the people shown here are still in office.") + "</p>" : "") +
        '<div class="exec-topo">' + (cartaoGrande(p, EP.tr(EP.gen(p && p.genero, "Prefeito", "Prefeita"), "Mayor"), sit(p)) +
          cartaoGrande(vi, EP.tr(EP.gen(vi && vi.genero, "Vice-prefeito", "Vice-prefeita"), "Vice Mayor"), sit(vi)) ||
          '<div class="vazio">' + EP.tr("O TSE não mostra quem governa esta cidade.", "The TSE does not show who governs this city.") + "</div>") + "</div>" +
        (fp.length ? '<p style="margin-top:8px">' + EP.botaoFontes(fp) + "</p>" : "") +
        '<h4 class="sub"><span aria-hidden="true">🏛️ </span>' + EP.tr("A Câmara de Vereadores", "The City Council (Câmara de Vereadores)") + " <small>(" + EP.num((v.membros || []).length) + ")</small></h4>" +
        '<p class="muted">' + EP.tr("Os vereadores fazem as leis da cidade e fiscalizam o prefeito.", "City councilors (vereadores) make the city's laws and oversee the mayor.") + "</p>" +
        aviso(D.aviso(v.aviso, v.aviso_en)) + '<div id="casa-ver"></div>';
      EP.montaCasa(document.getElementById("casa-ver"), { membros: v.membros || [], filtroUF: false, fonte: v.fonte, atualizado: c.atualizado, nivel: 5,
        nomes: { um: EP.tr("vereador", "city councilor"), uma: EP.tr("vereadora", "city councilor"), varios: EP.tr("vereadores", "city councilors"), varias: EP.tr("vereadoras", "city councilors") },
        extra: function (m) { return m.votos != null ? EP.tr(EP.num(m.votos) + " votos em 2024", EP.num(m.votos) + " votes in 2024") : ""; } });
      EP.revelar(caixa);
      if (focar) {
        var h = document.getElementById("nome-cidade");
        h.focus({ preventScroll: true });
        h.scrollIntoView({ behavior: EP.reduzido ? "auto" : "smooth", block: "start" });
      }
    }).catch(function () { falhou(caixa, "os dados desta cidade", "the data for this city"); });
  }

  D.rodapeErros(document.getElementById("links-erro"));
  if (uf && EP.UFS[uf]) mostraEstado();
  else mostraMapa();
  EP.paralaxe();
})();
