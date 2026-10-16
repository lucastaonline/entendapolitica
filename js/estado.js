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
    // lista de estados com busca: a pessoa digita e escolhe; escolher já abre o estado (o rótulo avisa isso)
    var sel = document.getElementById("sel-uf"), form = document.getElementById("form-uf");
    sel.insertAdjacentHTML("beforeend", Object.keys(EP.UFS).sort(function (a, b) { return EP.norm(EP.UFS[a]).localeCompare(EP.norm(EP.UFS[b])); })
      .map(function (u) { return '<option value="' + u + '" data-busca="' + u + '">' + esc(EP.UFS[u]) + "</option>"; }).join(""));
    if (EP.en) form.insertAdjacentHTML("afterbegin", '<input type="hidden" name="lang" value="en">');
    var cUF = EP.comboSelect(sel, {
      placeholder: EP.tr("Digite o nome do estado…", "Type the state's name…"),
      aoEscolher: function (it) { if (it.v) location.href = "estado.html?uf=" + it.v + (EP.en ? "&lang=en" : ""); }
    });
    form.addEventListener("submit", function (e) {
      if (sel.value) return;
      e.preventDefault();
      cUF.foco();
      document.getElementById("aviso-uf").textContent = EP.tr("Escolha um estado na lista.", "Choose a state from the list.");
    });
    if (window.TRES) EP.fundo3d([["cubo", "5%", "14%", 40, 0, 0, 18], ["esfera", "92%", "10%", 36, 3, 0, 7], ["anel", "90%", "60%", 56, 2, 0, 20], ["esfera", "4%", "72%", 30, 6, 0, 8]], document.body);
    EP.revelar();
  }

  // ---------------------------------------------------------------- página do estado
  var cartaoGrande = EP.cartaoGrande;  // em js/casa.js (também usado na página da cidade)
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
        secao("cidade", "🏘️", esc(EP.tr("Minha cidade", "Cities")), EP.tr("Escolha a sua cidade para ver o prefeito, o vice e os vereadores.", 'Choose a city to see its mayor, vice mayor and city councilors (<span lang="pt-BR">vereadores</span>).'),
          '<div id="aviso-cid"></div><div class="cidade-busca"><label id="rotulo-cid" for="campo-cid">' + EP.tr("Digite o nome da sua cidade", "Type the name of a city") + "</label>" +
          '<div id="busca-cid"></div>' +
          '<p class="muted" id="dica-cidade" style="font-size:.85rem;margin:6px 0 0">' + EP.tr("Escolha na lista que aparece para abrir a página da cidade.", "Choose it from the list to open the city's page.") + "</p>" +
          '<p id="capital-cid" class="links-cidade"></p></div>'));
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
        var bc = document.getElementById("campo-cid"), cap = document.getElementById("capital-cid");
        if (bc && e.capital) bc.placeholder = EP.tr("Ex.: ", "E.g.: ") + e.capital.nome;
        if (cap && e.capital) cap.innerHTML = '<a class="btn claro peq" href="cidade.html?ibge=' + e.capital.ibge + (EP.en ? "&lang=en" : "") + '"><span aria-hidden="true">🏙️ </span>' +
          esc(EP.tr("Ver a capital, " + e.capital.nome, "See the capital, " + e.capital.nome)) + "</a>";
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

  // ---------------------------------------------------------------- cidade: campo com busca que leva para cidade.html
  function ligaCidade() {
    EP.combo(document.getElementById("busca-cid"), {
      id: "campo-cid", rotuloId: "rotulo-cid", descricao: "dica-cidade", classe: "grande", min: 1, max: 8,
      placeholder: EP.tr("Digite o nome da cidade…", "Type the city's name…"),
      nada: EP.tr("Nenhuma cidade com esse nome " + EP.noEstado(uf) + ".", "No city with that name " + EP.noEstado(uf) + "."),
      itens: function () {
        return EP.json("dados/cidades/" + uf + ".json").then(function (l) {
          return l.map(function (c) { return { v: c.ibge, t: c.nome, sub: c.prefeito ? EP.tr("Prefeito(a): ", "Mayor: ") + c.prefeito : null }; });
        });
      },
      aoEscolher: function (it) { location.href = "cidade.html?ibge=" + it.v + (EP.en ? "&lang=en" : ""); }
    });
  }

  D.rodapeErros(document.getElementById("links-erro"));
  if (cidade0 && /^\d{7}$/.test(cidade0)) location.replace("cidade.html?ibge=" + cidade0 + (EP.en ? "&lang=en" : ""));
  else if (uf && EP.UFS[uf]) mostraEstado();
  else mostraMapa();
  EP.paralaxe();
})();
