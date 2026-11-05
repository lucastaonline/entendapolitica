/* A política do meu estado: mapa do Brasil, governador, bancada no Congresso, deputados estaduais e a cidade. */
(function () {
  "use strict";
  var EP = window.EP, D = EP.trd, esc = EP.esc;
  // região de cada UF (as cores do mapa)
  var REGIAO = {
    AC: "N", AM: "N", AP: "N", PA: "N", RO: "N", RR: "N", TO: "N",
    AL: "NE", BA: "NE", CE: "NE", MA: "NE", PB: "NE", PE: "NE", PI: "NE", RN: "NE", SE: "NE",
    DF: "CO", GO: "CO", MS: "CO", MT: "CO", ES: "SE", MG: "SE", RJ: "SE", SP: "SE", PR: "S", RS: "S", SC: "S"
  };
  // [nome, nome em inglês, cor (contraste de pelo menos 4,5:1 com o texto branco), cor do "lado" (a espessura do estado no 3D)]
  var REGIOES = { N: ["Norte", "North", "#0f766e", "#094b46"], NE: ["Nordeste", "Northeast", "#a15c00", "#673b00"], CO: ["Centro-Oeste", "Center-West", "#55689e", "#36436a"],
    SE: ["Sudeste", "Southeast", "#1f3a5f", "#10203a"], S: ["Sul", "South", "#7a6a55", "#4f4537"] };
  var uf = (EP.param("uf") || "").toUpperCase();
  var cidade0 = EP.param("cidade");

  function falhou(el, pt, en) {
    el.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">⚠️</span>' +
      EP.tr("Não foi possível carregar " + pt + " agora. Tente de novo daqui a pouco.", "Could not load " + en + " right now. Please try again in a little while.") + "</div>";
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
  // Mapa com o formato real de cada estado (malha do IBGE, em dados/mapa-brasil.json, feita por scripts/mapa.py).
  // Cada estado é um link. Passar o mouse ou chegar com o Tab "levanta" o estado (uma cópia desenhada por cima, no grupo
  // .realce, para não mudar a ordem dos links). Nos estados pequenos, a sigla fica num selo fora dele, numa camada por cima
  // de todos: tocar no selo também abre o estado (o selo fica fora do Tab e do leitor de tela, que já têm o link do estado).
  function mapaSvg(m) {
    // ordem dos links (Tab e leitor de tela): por região, na ordem da legenda, e por nome dentro de cada região
    var ordemReg = Object.keys(REGIOES);
    var ufs = Object.keys(m.ufs).sort(function (a, b) { return ordemReg.indexOf(REGIAO[a]) - ordemReg.indexOf(REGIAO[b]) || EP.norm(EP.UFS[a]).localeCompare(EP.norm(EP.UFS[b])); });
    var lados = ufs.map(function (u) { return '<path d="' + m.ufs[u].d + '" fill="' + REGIOES[REGIAO[u]][3] + '"/>'; }).join("");
    function href(u) { return "estado.html?uf=" + u + (EP.en ? "&amp;lang=en" : ""); }
    function cores(u) { var r = REGIOES[REGIAO[u]]; return "--cor:" + r[2] + ";--lado:" + r[3]; }
    var links = ufs.map(function (u) {
      var e = m.ufs[u], nome = EP.UFS[u];
      var reg = EP.tr("região " + REGIOES[REGIAO[u]][0], REGIOES[REGIAO[u]][1] + " region");
      return '<a class="uf" href="' + href(u) + '" data-uf="' + u + '" data-nome="' + esc(nome) + '" data-regiao="' + esc(reg) + '" aria-label="' + esc(nome) + ", " + u + ", " + esc(reg) + '" style="' + cores(u) + '">' +
        '<path class="topo" d="' + e.d + '"/>' + (e.selo ? "" : '<text class="sigla" x="' + e.x + '" y="' + e.y + '">' + u + "</text>") + "</a>";
    }).join("");
    var selos = ufs.filter(function (u) { return m.ufs[u].selo; }).map(function (u) {
      var e = m.ufs[u], s = e.selo, w = 64, h = m.seloAltura;
      return '<a class="selo-link" href="' + href(u) + '" data-uf="' + u + '" tabindex="-1" aria-hidden="true" style="' + cores(u) + '">' +
        '<line class="fio" x1="' + e.x + '" y1="' + e.y + '" x2="' + s.x + '" y2="' + s.y + '"/><circle class="ponto" cx="' + e.x + '" cy="' + e.y + '" r="4.5"/>' +
        '<rect class="selo" x="' + (s.x - w / 2) + '" y="' + (s.y - h / 2) + '" width="' + w + '" height="' + h + '" rx="10"/><text class="sigla" x="' + s.x + '" y="' + s.y + '">' + u + "</text></a>";
    }).join("");
    return '<svg class="mapa-br" viewBox="0 0 ' + m.largura + " " + (m.altura + 16) + '" style="--sigla:' + m.sigla + 'px" focusable="false">' +
      '<g class="lados" aria-hidden="true" transform="translate(0 10)">' + lados + "</g>" +
      '<g class="ufs">' + links + "</g>" + '<g class="selos">' + selos + "</g>" +
      '<g class="realce" aria-hidden="true"><path class="r-lado"/><path class="r-anel"/><path class="r-topo"/><text class="sigla r-sigla"></text></g></svg>';
  }
  function mostraMapa() {
    D.canonico();
    document.getElementById("escolher").hidden = false;
    var mapa = document.getElementById("mapa");
    var rot = document.getElementById("rotulo-uf");
    // ui-r9: a dica serve para toque, mouse e teclado (antes: "Passe o mouse...", que não servia para quem toca ou usa o teclado)
    var dica = "👆 " + EP.tr("Toque ou clique no seu estado", "Tap or click your state");
    var dicaTeclado = EP.tr("Com o teclado: Tab ou as setas andam pelos estados, e Enter abre o escolhido.", "With the keyboard: Tab or the arrow keys move between states, and Enter opens the chosen one.");
    rot.removeAttribute("aria-hidden");
    rot.innerHTML = esc(dica) + '<span class="dica-mapa" id="dica-mapa">' + esc(dicaTeclado) + "</span>";
    mapa.setAttribute("aria-describedby", "dica-mapa");
    EP.json("dados/mapa-brasil.json").then(function (m) {
      mapa.innerHTML = mapaSvg(m);
      var svg = mapa.querySelector("svg"), realce = svg.querySelector(".realce"), rSigla = realce.querySelector(".r-sigla");
      var caminhos = [].slice.call(realce.querySelectorAll("path")), atual = null;
      // levanta o estado (ou nenhum) e mostra o nome dele em cima do mapa
      function levanta(a) {
        [].forEach.call(svg.querySelectorAll(".ativo"), function (x) { if (x !== a) x.classList.remove("ativo"); });
        if (!a) { realce.classList.remove("ligado", "teclado"); atual = null; rot.innerHTML = esc(dica) + '<span class="dica-mapa" id="dica-mapa">' + esc(dicaTeclado) + "</span>"; return; }
        var u = a.getAttribute("data-uf"), e = m.ufs[u], selo = svg.querySelector('.selo-link[data-uf="' + u + '"]');
        if (selo) selo.classList.add("ativo");
        if (u === atual) return;
        // o estado novo também "pula": volta a cópia para baixo sem animação e sobe de novo
        realce.classList.add("sem-anim");
        realce.classList.remove("ligado");
        realce.getBoundingClientRect();
        realce.classList.remove("sem-anim");
        atual = u;
        caminhos.forEach(function (p) { p.setAttribute("d", e.d); });
        realce.style.setProperty("--cor", a.style.getPropertyValue("--cor"));
        realce.style.setProperty("--lado", a.style.getPropertyValue("--lado"));
        rSigla.textContent = e.selo ? "" : u;
        rSigla.setAttribute("x", e.x);
        rSigla.setAttribute("y", e.y);
        a.classList.add("ativo");
        realce.classList.add("ligado");
        rot.innerHTML = "👆 " + esc(a.getAttribute("data-nome")) + '<span class="dica-mapa" id="dica-mapa">' + esc(a.getAttribute("data-regiao")) + " · " +
          esc(EP.tr("toque, clique ou aperte Enter para abrir", "tap, click or press Enter to open")) + "</span>";
      }
      // o foco do teclado levanta o estado com uma borda mais forte (o clique do mouse não deixa contorno)
      function teclado(a) { var ok = false; try { ok = !!a && a.matches(":focus-visible"); } catch (x) { ok = true; } return ok; }
      function focado() { var f = document.activeElement; return f && svg.contains(f) && f.closest ? f.closest("a.uf") : null; }
      // o selo de um estado pequeno vale pelo próprio estado
      function doAlvo(t) {
        var x = t && t.closest ? t.closest("a.uf, a.selo-link") : null;
        return x && x.classList.contains("selo-link") ? svg.querySelector('a.uf[data-uf="' + x.getAttribute("data-uf") + '"]') : x;
      }
      svg.addEventListener("pointerover", function (e) { var a = doAlvo(e.target); if (a) levanta(a); });
      svg.addEventListener("pointerleave", function () { levanta(focado()); });
      svg.addEventListener("focusin", function (e) {
        var a = e.target.closest("a.uf");
        if (!teclado(a)) return;
        levanta(a);
        realce.classList.add("teclado");
      });
      svg.addEventListener("focusout", function (e) { if (!svg.contains(e.relatedTarget)) { realce.classList.remove("teclado"); levanta(null); } });
      // clicar fora de um estado (no mar, nos cantos do desenho) não põe o foco no desenho inteiro (o navegador desenhava um
      // contorno em volta do mapa todo, inclinado como ele)
      svg.addEventListener("mousedown", function (e) { if (!doAlvo(e.target)) e.preventDefault(); });
      // setas: vão para o estado mais perto naquela direção (no mapa de verdade); Home e End, para o primeiro e o último da lista
      var ufsA = [].slice.call(svg.querySelectorAll("a.uf"));
      svg.addEventListener("keydown", function (e) {
        var a = e.target.closest && e.target.closest("a.uf");
        if (!a) return;
        var k = e.key, alvo = null;
        if (k === "Home" || k === "End") alvo = ufsA[k === "Home" ? 0 : ufsA.length - 1];
        else if (/^Arrow/.test(k)) {
          var o = m.ufs[a.getAttribute("data-uf")], dx = { ArrowLeft: -1, ArrowRight: 1 }[k] || 0, dy = { ArrowUp: -1, ArrowDown: 1 }[k] || 0, melhor = Infinity;
          ufsA.forEach(function (b) {
            if (b === a) return;
            var q = m.ufs[b.getAttribute("data-uf")], vx = q.x - o.x, vy = q.y - o.y, ao = vx * dx + vy * dy;
            if (ao <= 0) return;
            var lado = Math.abs(dx ? vy : vx), custo = ao + lado * 2.2;
            if (custo < melhor) { melhor = custo; alvo = b; }
          });
        } else return;
        e.preventDefault();
        if (alvo) alvo.focus();
      });
      document.getElementById("fonte-mapa").innerHTML = EP.botaoFontes([m.fonte], EP.tr("De onde vem este mapa?", "Where does this map come from?"));
    }).catch(function () { falhou(mapa, "o mapa", "the map"); });
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

  // mandatos-r11: todo mandato tem o mesmo layout de hoje. futuro: o mandato 2027 do "Ver outro mandato"
  // (estado.html?uf=SP&mandato=2027, quem foi eleito em 2026: js/proximos.js); passado: um mandato anterior
  // (estado.html?uf=BA&mandato=2019: js/historico.js). As abas e as partes são as mesmas; só os dados mudam
  function mostraEstado(futuro, passado) {
    var nome = EP.UFS[uf], de = EP.doEstado(uf), ehDF = uf === "DF", X = EP.eleitos;
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
      '<p><a class="btn peq bege" href="estado.html"><span aria-hidden="true">🗺️ </span>' + EP.tr("Trocar de estado", "Choose another state") + "</a></p>" +
      '<div class="mandato-lugar" id="mandato-lugar"></div></div>' +
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
    if (EP.trilha) EP.trilha([{ t: EP.tr("Estados", "States"), href: "estado.html" }, { t: nome }]);
    // ui-r9: a página em abas (js/abas.js), como a do Brasil: cada seção do menu "Ir direto para" vira uma aba com endereço
    // próprio (estado.html?uf=SP#federais); as listas grandes começam com um resumo (12) e "Ver todos"
    var comAbas = !!(EP.abas && EP.abas.monta({ nav: el.querySelector("nav.atalhos") }));
    function quando(secao, fn) { if (comAbas) EP.abas.quandoAbrir(secao, fn); else fn(); }
    var RESUMO = comAbas ? { lote: EP.RESUMO_CASA, verTodos: true } : {};
    // "Ver outro mandato" (js/historico.js), com o de 2027 (eleitos em 2026) enquanto houver eleitos sem posse
    if (EP.hist) EP.hist.seletor(document.getElementById("mandato-lugar"), "estados", futuro ? X.FUTURO : passado, X && X.opcaoFutura(uf));
    if (futuro || passado) {
      if (futuro) X.estadoAbas(uf, { quando: quando });
      else EP.hist.estado(uf, passado, { quando: quando, resumo: RESUMO });
      // Minha cidade: as cidades têm outros mandatos (eleições em outros anos); o campo leva à cidade hoje
      if (!ehDF) {
        document.getElementById("aviso-cid").innerHTML = aviso(esc(futuro ?
          EP.tr("Em 2026 não houve eleição nas cidades: prefeitos e vereadores continuam no mandato de 2025 a 2028. Escolha uma cidade para ver quem está no cargo hoje.",
            "There were no city elections in 2026: mayors and city councilors stay in the 2025–2028 term. Choose a city to see who is in office today.") :
          EP.tr("Prefeitos e vereadores são eleitos em outros anos (1996, 2000, 2004...), por isso os mandatos das cidades são outros. Escolha uma cidade para ver quem está no cargo hoje; na página dela, o campo “Ver outro mandato” mostra os mandatos anteriores.",
            "Mayors and city councilors are elected in other years (1996, 2000, 2004...), so city terms are different. Choose a city to see who is in office today; on its page, the “See another term” field shows earlier terms.")));
        EP.json("dados/estados/" + uf + ".json").then(capital).catch(function () {});
        ligaCidade();
      }
      return;
    }
    if (X) X.avisos(uf, [["governo", "governo", "#governo"], ["senado", "senadores", "#senadores"], ["camara", "federais", "#federais"], ["assembleia", "estaduais", "#estaduais"]]);

    // governo + Assembleia (arquivo do estado)
    EP.json("dados/estados/" + uf + ".json").then(function (e) {
      // sem nome e sem "vago" = o TSE ainda não mostra quem ganhou (ex.: segundo turno por fazer)
      var g = e.governador && (e.governador.nome || e.governador.vago) ? e.governador : null,
        v = e.vice && (e.vice.nome || e.vice.vago) ? e.vice : null, anoG = e.eleicaoGoverno || 2022;
      document.getElementById("gov").innerHTML = (cartaoGrande(g, EP.tr(EP.gen(g && g.genero, "Governador", "Governadora"), "Governor")) +
        cartaoGrande(v, EP.tr(EP.gen(v && v.genero, "Vice-governador", "Vice-governadora"), "Vice Governor"))) ||
        '<div class="vazio">' + EP.tr("O TSE não mostra quem ganhou a última eleição para governador deste estado.", "The TSE (Brazil's Superior Electoral Court) does not show who won the last election for governor in this state.") + "</div>";
      var notas = [];
      if ((g && g.aConfirmar) || (v && v.aConfirmar)) notas.push(EP.tr("Aqui aparece quem ganhou a eleição de " + anoG + ", segundo o TSE. Se alguém deixou o cargo depois (por renúncia, cassação ou morte), isso pode não aparecer aqui.",
        "This shows who won the " + anoG + " election, according to the TSE (Brazil's Superior Electoral Court). If someone left office afterwards (by resigning, being removed or dying), that may not show here."));
      var fg = fontesDe(g, v);
      document.getElementById("gov-nota").innerHTML = (notas.length ? '<p class="aviso"><span aria-hidden="true">⚠️ </span>' + esc(notas.join(" ")) + "</p>" : "") +
        (fg.length ? '<p style="margin-top:12px">' + EP.botaoFontes(fg) + "</p>" : "");
      if (e.capital || e.municipios) {
        capital(e);
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
      // lista oficial da Assembleia: a data da última leitura completa do site oficial (infoCasa.conferido)
      quando("estaduais", function () {
        EP.montaCasa(document.getElementById("casa-est"), Object.assign({ membros: de2.membros || [], nomes: nomesE, filtroUF: false, fonte: de2.fonte,
          atualizado: (de2.oficial && (de2.infoCasa || {}).conferido) || e.atualizado,
          extra: function (m) {
            if (m.exercicio) return EP.tr(m.exercicio, m.exercicio_en || m.exercicio);  // suplente que assumiu a vaga
            var a = de2.eleicao || 2022;
            return m.votos != null ? EP.tr(EP.num(m.votos) + " votos em " + a, EP.num(m.votos) + " votes in " + a) : "";
          } }, RESUMO));
        // o que o site já tem da Assembleia (lista oficial, propostas, votações, gastos) e as notas dela
        if (de2.infoCasa) document.getElementById("casa-est").insertAdjacentHTML("afterend", EP.infoCasa(de2.infoCasa));
        EP.revelar(el);
      });
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
      quando("federais", function () {
        EP.montaCasa(document.getElementById("casa-fed"), Object.assign({ membros: l, filtroUF: false, fonte: d.fonte, atualizado: d.atualizado,
          nomes: { um: EP.tr("deputado", "deputy"), uma: EP.tr("deputada", "deputy"), varios: EP.tr("deputados", "deputies"), varias: EP.tr("deputadas", "deputies") } }, RESUMO));
      });
    }).catch(function () { falhou(document.getElementById("casa-fed"), "a lista de deputados federais", "the list of federal deputies"); });

    if (!ehDF) ligaCidade();
  }

  // ---------------------------------------------------------------- cidade: campo com busca que leva para cidade.html
  // a capital do estado (dados/estados/UF.json): o exemplo do campo e o botão "Ver a capital"
  function capital(e) {
    var bc = document.getElementById("campo-cid"), cap = document.getElementById("capital-cid");
    if (!e || !e.capital) return;
    if (bc) bc.placeholder = EP.tr("Ex.: ", "E.g.: ") + e.capital.nome;
    if (cap) cap.innerHTML = '<a class="btn claro peq" href="cidade.html?ibge=' + e.capital.ibge + (EP.en ? "&lang=en" : "") + '"><span aria-hidden="true">🏙️ </span>' +
      esc(EP.tr("Ver a capital, " + e.capital.nome, "See the capital, " + e.capital.nome)) + "</a>";
  }
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
  else if (uf && EP.UFS[uf]) {
    // mandato anterior (estado.html?uf=BA&mandato=2019) e o de 2027: o mesmo layout, com os dados daquele mandato
    var fut = !!(EP.eleitos && EP.eleitos.ehFuturo());
    mostraEstado(fut, !fut && EP.hist ? EP.hist.param() : null);
  }
  else mostraMapa();
  EP.paralaxe();
})();
