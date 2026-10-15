/* A política do meu estado: mapa em quadradinhos, governador, bancada no Congresso, deputados estaduais e a cidade. */
(function () {
  "use strict";
  var EP = window.EP, esc = EP.esc;
  var CONFIG = window.EP_CONFIG || {};
  // [linha, coluna, região] de cada UF no mapa em quadradinhos
  var GRADE = {
    RR: [0, 2, "N"], AP: [0, 4, "N"],
    AM: [1, 1, "N"], PA: [1, 3, "N"], MA: [1, 4, "NE"], CE: [1, 5, "NE"], RN: [1, 6, "NE"],
    AC: [2, 0, "N"], RO: [2, 1, "N"], MT: [2, 2, "CO"], TO: [2, 3, "N"], PI: [2, 4, "NE"], PE: [2, 5, "NE"], PB: [2, 6, "NE"],
    MS: [3, 2, "CO"], GO: [3, 3, "CO"], DF: [3, 4, "CO"], BA: [3, 5, "NE"], AL: [3, 6, "NE"],
    MG: [4, 4, "SE"], ES: [4, 5, "SE"], SE: [4, 6, "NE"], SP: [4, 3, "SE"],
    PR: [5, 3, "S"], RJ: [5, 4, "SE"],
    SC: [6, 3, "S"], RS: [7, 3, "S"]
  };
  var REGIOES = { N: ["Norte", "#0f766e"], NE: ["Nordeste", "#c27600"], CO: ["Centro-Oeste", "#5b6fa8"], SE: ["Sudeste", "#1f3a5f"], S: ["Sul", "#7a6a55"] };
  var uf = (EP.param("uf") || "").toUpperCase();
  var cidade0 = EP.param("cidade");

  function falhou(el, oque) { el.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">🛠️</span>Ainda estamos juntando ' + oque + ". Volte daqui a pouco.</div>"; }
  function de(u) { return EP.noEstado(u).replace(/^(no|na|em) /, function (m) { return { "no ": "do ", "na ": "da ", "em ": "de " }[m]; }); }

  // ---------------------------------------------------------------- escolher o estado
  function mostraMapa() {
    document.getElementById("escolher").hidden = false;
    var mapa = document.getElementById("mapa");
    mapa.innerHTML = Object.keys(GRADE).map(function (u) {
      var g = GRADE[u];
      return '<a class="tile-uf" href="estado.html?uf=' + u + '" style="grid-row:' + (g[0] + 1) + ";grid-column:" + (g[1] + 1) + ";--cor:" + REGIOES[g[2]][1] + '" aria-label="' + esc(EP.UFS[u]) + '" data-nome="' + esc(EP.UFS[u]) + '">' + u + "</a>";
    }).join("");
    var rot = document.getElementById("rotulo-uf");
    function mostraNome(e) { var t = e.target.closest && e.target.closest(".tile-uf"); if (t) rot.textContent = "👆 " + t.getAttribute("data-nome"); }
    mapa.addEventListener("mouseover", mostraNome);
    mapa.addEventListener("focusin", mostraNome);
    document.getElementById("regioes").innerHTML = Object.keys(REGIOES).map(function (r) { return '<span><i style="background:' + REGIOES[r][1] + '"></i>' + REGIOES[r][0] + "</span>"; }).join("");
    var sel = document.getElementById("sel-uf");
    sel.insertAdjacentHTML("beforeend", Object.keys(EP.UFS).sort(function (a, b) { return EP.norm(EP.UFS[a]).localeCompare(EP.norm(EP.UFS[b])); })
      .map(function (u) { return '<option value="' + u + '">' + esc(EP.UFS[u]) + "</option>"; }).join(""));
    sel.addEventListener("change", function () { if (sel.value) location.href = "estado.html?uf=" + sel.value; });
    if (window.TRES) EP.fundo3d([["cubo", "5%", "14%", 40, 0, 0, 18], ["esfera", "92%", "10%", 36, 3, 0, 7], ["anel", "90%", "60%", 56, 2, 0, 20], ["esfera", "4%", "72%", 30, 6, 0, 8]], document.body);
    EP.revelar();
  }

  // ---------------------------------------------------------------- página do estado
  function cartaoGrande(p, cargo) {
    if (!p) return "";
    if (p.vago) return '<div class="pessoa-grande"><span class="av av-letra" aria-hidden="true">–</span><span><span class="cargo">' + esc(cargo) + "</span><b>Cargo vago</b><small>" + esc(p.nota || "") + "</small></span></div>";
    var anos = p.desde ? "No cargo desde " + EP.data(p.desde) : "";
    return '<a class="pessoa-grande rev" href="pessoa.html?id=' + encodeURIComponent(p.id) + '">' + EP.av(p.foto, p.nome, null, true) +
      '<span><span class="cargo">' + esc(cargo) + "</span><b>" + esc(p.nome) + "</b><small>" + esc([p.partido, anos].filter(Boolean).join(" · ")) + "</small>" +
      EP.chip2026(p.eleicao2026, p.genero, true) + (p.comoAssumiu && !/^eleit/i.test(p.comoAssumiu) ? '<small style="margin-top:6px">🔑 ' + esc(p.comoAssumiu) + "</small>" : "") +
      '<span class="ver">Ver mais ›</span></span></a>';
  }
  function secao(id, ic, titulo, sub, corpo) {
    return '<section class="miolo bloco" id="' + id + '"><div class="cab-bloco rev"><span class="ic-bloco" aria-hidden="true">' + ic + "</span><div><h2>" + titulo + "</h2>" +
      (sub ? '<p class="muted">' + sub + "</p>" : "") + "</div></div>" + corpo + "</section>";
  }

  function mostraEstado() {
    var nome = EP.UFS[uf];
    document.title = "A política " + de(uf) + ": governador, deputados, prefeitos e vereadores | Entenda Política";
    document.getElementById("onde").textContent = "📍 " + nome;
    var el = document.getElementById("estado");
    el.hidden = false;
    var ehDF = uf === "DF";
    el.innerHTML =
      '<section class="miolo cab-pagina"><div class="cab-txt rev"><span class="selo-topo">A política ' + esc(de(uf)) + "</span><h1>" + esc(nome) + "</h1>" +
      '<p class="lead" id="lead-uf">Quem governa, quem representa o estado no Congresso e quem faz as leis ' + esc(de(uf)) + ".</p>" +
      '<p><a class="btn peq bege" href="estado.html">🗺️ Trocar de estado</a></p></div><div class="cab-3d rev pop" style="--i:1">' + (window.TRES ? TRES.predio() : "") + "</div></section>" +
      '<nav class="miolo atalhos rev" aria-label="Ir direto para"><a class="chip" href="#governo">🏢 Quem governa</a><a class="chip" href="#senadores">🏛️ Senadores</a>' +
      '<a class="chip" href="#federais">🏛️ Deputados federais</a><a class="chip" href="#estaduais">🏛️ ' + (ehDF ? "Deputados distritais" : "Deputados estaduais") + "</a>" +
      (ehDF ? "" : '<a class="chip" href="#cidade">🏘️ Minha cidade</a>') + "</nav>" +
      secao("governo", "🏢", "Quem governa " + (ehDF ? "o Distrito Federal" : "o estado"), "O governador e o vice comandam o Poder Executivo " + esc(de(uf)) + ".", '<div class="exec-topo" id="gov"><div class="carregando">Carregando…</div></div><p id="gov-nota"></p>') +
      secao("senadores", "🏛️", "Os senadores " + esc(de(uf)), "Todo estado tem 3 senadores no Senado Federal, em Brasília.", '<div class="grade-pessoas" id="lista-sen"><div class="carregando">Carregando…</div></div>') +
      secao("federais", "🏛️", "Os deputados federais " + esc(de(uf)), "Eles representam o povo " + esc(de(uf)) + " na Câmara dos Deputados, em Brasília.", '<div class="casa-corpo" id="casa-fed"><div class="carregando">Carregando…</div></div>') +
      secao("estaduais", "🏛️", ehDF ? "A Câmara Legislativa: deputados distritais" : "A Assembleia Legislativa: deputados estaduais",
        "Eles fazem as leis " + esc(de(uf)) + " e fiscalizam o governador.", '<div id="aviso-est"></div><div class="casa-corpo" id="casa-est"><div class="carregando">Carregando…</div></div>') +
      (ehDF ? '<section class="miolo bloco"><div class="aviso azul">ℹ️ O Distrito Federal não é dividido em cidades com prefeito e vereadores. Quem cuida dessas coisas é o próprio governo do DF, e as leis são feitas pela Câmara Legislativa.</div></section>' :
        secao("cidade", "🏘️", "Minha cidade", "Escolha a sua cidade para ver o prefeito, o vice e os vereadores.",
          '<div class="cidade-busca"><div class="busca"><input type="search" id="busca-cidade" placeholder="Digite o nome da sua cidade" autocomplete="off" aria-label="Digite o nome da sua cidade" aria-controls="sugestoes"></div>' +
          '<ul class="sugestoes" id="sugestoes"></ul></div><div class="cidade-caixa" id="cidade-caixa"></div>'));
    EP.revelar(el);

    // governo + Assembleia (arquivo do estado)
    EP.json("dados/estados/" + uf + ".json").then(function (e) {
      document.getElementById("gov").innerHTML = cartaoGrande(e.governador, EP.gen(e.governador && e.governador.genero, "Governador", "Governadora")) +
        cartaoGrande(e.vice, EP.gen(e.vice && e.vice.genero, "Vice-governador", "Vice-governadora"));
      var notas = [];
      if (e.governador && e.governador.aConfirmar) notas.push("⚠️ Estamos conferindo se quem foi eleito em 2022 ainda está no cargo.");
      var fg = [].concat((e.governador || {}).fonte || [], (e.vice || {}).fonte || []);
      document.getElementById("gov-nota").innerHTML = (notas.length ? '<span class="aviso" style="display:block">' + notas.join(" ") + "</span>" : "") + (fg.length ? EP.botaoFontes(fg) : "");
      if (e.capital || e.municipios) document.getElementById("lead-uf").insertAdjacentHTML("afterend", '<p class="muted">' +
        (e.capital ? "🏙️ Capital: <b>" + esc(e.capital.nome) + "</b>" : "") + (e.municipios ? " · 🏘️ " + EP.num(e.municipios) + (e.municipios === 1 ? " município" : " municípios") : "") + "</p>");
      var de2 = e.deputadosEstaduais || {};
      if (de2.aviso) document.getElementById("aviso-est").innerHTML = '<p class="aviso">ℹ️ ' + esc(de2.aviso) + "</p>";
      var nomesE = uf === "DF" ? { um: "deputado distrital", uma: "deputada distrital", varios: "deputados distritais", varias: "deputadas distritais" } :
        { um: "deputado estadual", uma: "deputada estadual", varios: "deputados estaduais", varias: "deputadas estaduais" };
      EP.montaCasa(document.getElementById("casa-est"), { membros: de2.membros || [], nomes: nomesE, filtroUF: false, fonte: de2.fonte, atualizado: e.atualizado,
        extra: function (m) { return m.votos != null ? EP.num(m.votos) + " votos em 2022" : ""; } });
      EP.revelar(el);
    }).catch(function () { falhou(document.getElementById("gov"), "os dados deste estado"); falhou(document.getElementById("casa-est"), "a lista de deputados estaduais"); });

    // senadores e deputados federais do estado
    EP.json("dados/senado.json").then(function (d) {
      var l = EP.alfabetica((d.membros || []).filter(function (m) { return m.uf === uf; }));
      document.getElementById("lista-sen").innerHTML = l.map(function (m) { return EP.cartaoPessoa(m, m.fimMandato ? "Mandato até " + String(m.fimMandato).slice(0, 4) : ""); }).join("") ||
        '<div class="vazio">Lista indisponível agora.</div>';
    }).catch(function () { falhou(document.getElementById("lista-sen"), "a lista de senadores"); });
    EP.json("dados/camara.json").then(function (d) {
      var l = (d.membros || []).filter(function (m) { return m.uf === uf; });
      EP.montaCasa(document.getElementById("casa-fed"), { membros: l, nomes: { um: "deputado", uma: "deputada", varios: "deputados", varias: "deputadas" }, filtroUF: false, fonte: d.fonte, atualizado: d.atualizado });
    }).catch(function () { falhou(document.getElementById("casa-fed"), "a lista de deputados federais"); });

    if (uf !== "DF") ligaCidade();
  }

  // ---------------------------------------------------------------- cidade
  function ligaCidade() {
    var input = document.getElementById("busca-cidade"), sug = document.getElementById("sugestoes");
    var lista = null;
    var pronto = EP.json("dados/cidades/" + uf + ".json").then(function (l) {
      lista = l.map(function (c) { return { ibge: String(c.ibge), nome: c.nome, prefeito: c.prefeito, n: EP.norm(c.nome) }; });
      return lista;
    });
    function sugere() {
      var q = EP.norm(input.value);
      if (!lista || q.length < 2) { sug.innerHTML = ""; return; }
      var r = lista.filter(function (c) { return c.n.indexOf(q) > -1; }).sort(function (a, b) { return (a.n.indexOf(q) === 0 ? 0 : 1) - (b.n.indexOf(q) === 0 ? 0 : 1) || a.n.localeCompare(b.n); }).slice(0, 8);
      sug.innerHTML = r.length ? r.map(function (c) { return '<li><button type="button" data-ibge="' + c.ibge + '"><b>' + esc(c.nome) + "</b>" + (c.prefeito ? "<br><small>Prefeito(a): " + esc(c.prefeito) + "</small>" : "") + "</button></li>"; }).join("") :
        '<li class="muted">Nenhuma cidade com esse nome ' + esc(EP.noEstado(uf)) + ".</li>";
    }
    input.addEventListener("input", function () { pronto.then(sugere).catch(function () { sug.innerHTML = '<li class="muted">A lista de cidades ainda não está disponível.</li>'; }); });
    sug.addEventListener("click", function (e) {
      var b = e.target.closest("[data-ibge]");
      if (!b) return;
      sug.innerHTML = "";
      input.value = b.querySelector("b").textContent;
      abreCidade(b.getAttribute("data-ibge"), true);
    });
    if (cidade0) pronto.then(function () {
      var c = lista.filter(function (x) { return x.ibge === cidade0; })[0];
      if (c) input.value = c.nome;
      abreCidade(cidade0, false);
      setTimeout(function () { document.getElementById("cidade").scrollIntoView({ behavior: EP.reduzido ? "auto" : "smooth" }); }, 400);
    }).catch(function () {});
  }
  function abreCidade(ibge, rolar) {
    var caixa = document.getElementById("cidade-caixa");
    caixa.innerHTML = '<div class="carregando">Carregando…</div>';
    try { history.replaceState(null, "", "estado.html?uf=" + uf + "&cidade=" + ibge + "#cidade"); } catch (e) {}
    EP.json("dados/cidades/" + uf + "/" + ibge + ".json").then(function (c) {
      var v = c.vereadores || {};
      caixa.innerHTML = '<h3 class="sub">🏙️ ' + esc(c.nome) + "</h3>" + (c.aviso ? '<p class="aviso">ℹ️ ' + esc(c.aviso) + "</p>" : "") +
        '<div class="exec-topo">' + cartaoGrande(c.prefeito, EP.gen(c.prefeito && c.prefeito.genero, "Prefeito", "Prefeita")) +
        cartaoGrande(c.vice, EP.gen(c.vice && c.vice.genero, "Vice-prefeito", "Vice-prefeita")) + "</div>" +
        (c.fonte ? '<p style="margin-top:8px">' + EP.botaoFontes(c.fonte) + "</p>" : "") +
        '<h3 class="sub">🏛️ A Câmara de Vereadores <small>(' + EP.num((v.membros || []).length) + ")</small></h3>" +
        '<p class="muted">Os vereadores fazem as leis da cidade e fiscalizam o prefeito.</p>' + (v.aviso ? '<p class="aviso">ℹ️ ' + esc(v.aviso) + "</p>" : "") + '<div id="casa-ver"></div>';
      EP.montaCasa(document.getElementById("casa-ver"), { membros: v.membros || [], nomes: { um: "vereador", uma: "vereadora", varios: "vereadores", varias: "vereadoras" }, filtroUF: false, fonte: v.fonte, atualizado: c.atualizado,
        extra: function (m) { return m.votos != null ? EP.num(m.votos) + " votos em 2024" : ""; } });
      EP.revelar(caixa);
      if (rolar) caixa.scrollIntoView({ behavior: EP.reduzido ? "auto" : "smooth", block: "start" });
    }).catch(function () { falhou(caixa, "os dados desta cidade"); });
  }

  if (CONFIG.formularioErros) document.getElementById("links-erro").innerHTML = '🔎 Viu algo errado ou que parece puxar para um lado? <a href="' + esc(CONFIG.formularioErros) + '" target="_blank" rel="noopener">Avise aqui</a>';
  if (uf && EP.UFS[uf]) mostraEstado();
  else mostraMapa();
  EP.paralaxe();
})();
