/* Bloco de uma casa legislativa: plenário 3D, quantos de cada partido, filtros e a grade de pessoas.
   Usado para Senado, Câmara, Assembleias (deputados estaduais) e Câmaras Municipais (vereadores).
   o.nomes = { um, uma, varios, varias } já no idioma da página (use EP.tr); o.nivel = nível do título "Quantos de cada partido" (3).
   Opcionais (mandatos anteriores, js/historico.js): o.cartao(m, extra) monta o cartão no lugar de EP.cartaoPessoa (ex.: sem link
   para perfil); o.sabia(mulheres, homens) devolve o HTML do "Você sabia?"; o.vazio = HTML de quando a lista não tem ninguém;
   o.titPartidos = texto do título "Quantos de cada partido".
   Opcionais da página do Brasil com abas (js/brasil.js e js/proximos.js; as outras páginas continuam como antes):
   o.lote = quantas pessoas aparecem de começo (60); o.verTodos = o botão do fim mostra todas de uma vez ("Ver todos os 81
   senadores"), e quem volta de um perfil de alguém que estava depois do resumo encontra a lista inteira de novo;
   o.recolher = texto do bloco que abre e fecha (EP.blocoAbre: <details> do Basecoat) com o plenário, os partidos e os filtros (fechado de começo). */
(function () {
  "use strict";
  var EP = window.EP, T = window.TRES || {};
  var esc = EP.esc;
  var SEM = "Sem partido";
  var conta = 0;

  function nomePartido(p) { return p === SEM ? EP.tr("Sem partido", "No party") : p; }
  function nomePartidoHtml(p) { return p === SEM ? esc(nomePartido(p)) : EP.pt(esc(p)); }

  // cartão grande de quem governa (governador, prefeito e vices). Usado nas páginas do estado e da cidade.
  EP.cartaoGrande = function (p, cargo, extra) {
    var D = EP.trd;
    if (!p) return "";
    if (p.vago) {
      return '<div class="pessoa-grande"><span class="av av-letra" aria-hidden="true">–</span><span><span class="cargo">' + esc(cargo) + "</span><b>" + EP.tr("Cargo vago", "Vacant") + "</b>" +
        (p.txt || p.nota ? "<small>" + D.traduz(p.txt || p.nota, null, p.txt_en || p.nota_en) + "</small>" : "") + "</span></div>";
    }
    var desde = p.desde ? EP.tr("No cargo desde ", "In office since ") + EP.data(p.desde) : "";
    return '<a class="pessoa-grande rev" href="pessoa.html?id=' + encodeURIComponent(p.id) + '">' + EP.av(p.foto, p.nome, null, true) +
      '<span><span class="cargo">' + esc(cargo) + "</span><b>" + EP.pt(esc(p.nome)) + "</b><small>" + [p.partido ? EP.pt(esc(p.partido)) : "", esc(desde)].filter(Boolean).join(" · ") + "</small>" +
      (extra || "") + EP.chip2026(p.eleicao2026, p.genero, true) +
      (p.comoAssumiu && !/^eleit/i.test(p.comoAssumiu) ? '<small style="margin-top:6px"><span aria-hidden="true">🔑 </span>' + D.traduz(p.comoAssumiu, null, p.comoAssumiu_en) + "</small>" : "") +
      (p.nota ? '<small style="margin-top:6px"><span aria-hidden="true">📝 </span>' + D.traduz(p.nota, null, p.nota_en) + "</small>" : "") +
      '<span class="ver">' + EP.tr("Ver mais", "See more") + ' <span aria-hidden="true">›</span></span></span></a>';
  };

  // O que o site já tem de uma Assembleia ou Câmara Municipal (lista oficial, propostas, votações, gastos), as notas da Casa
  // (o que falta e por quê) e o site oficial. info = deputadosEstaduais.infoCasa ou vereadores.infoCasa (scripts/montar.py).
  var COBERTURA = [["lista", "👥", "Quem está no cargo hoje (lista oficial)", "Who is in office today (official list)"],
    ["propostas", "📜", "O que cada um propôs", "What each member proposed"],
    ["votacoes", "🗳️", "Como cada um votou", "How each member voted"],
    ["gastos", "💰", "Gastos com a verba do mandato", "Spending of the office allowance"]];
  // A última leitura completa do site oficial da Casa (infoCasa.conferido; EP.diasDesde fica em comum.js): o robô lê cada Casa todo dia (as Câmaras com SAPL,
  // uma vez por semana); alguns sites oficiais não aceitam o robô, que roda fora do Brasil, e são atualizados à mão. Com mais
  // de 8 dias, o aviso fica amarelo: os dados podem ter mudado desde então.
  EP.dataCasa = function (conferido) {
    var dias = conferido ? EP.diasDesde(conferido) : null;
    if (dias == null) return "";
    var velho = dias > 8;
    return '<p class="data-casa' + (velho ? " velho" : "") + '"><span aria-hidden="true">' + (velho ? "⚠️ " : "🔄 ") + "</span>" +
      EP.tr("Última atualização dos dados: ", "Data last updated: ") + "<b>" + esc(EP.dataLonga(conferido)) + "</b>" +
      (velho ? ". " + EP.tr("Os dados podem ter mudado desde então: o site oficial não pôde ser lido depois disso.",
        "The data may have changed since then: the official website could not be read after that date.") : ".") + "</p>";
  };
  EP.infoCasa = function (info) {
    if (!info || !info.cobertura) return "";
    var nomeHtml = EP.en && info.casa_en ? esc(info.casa_en) : EP.pt(esc(info.casa || ""));
    var notasEn = EP.en && (info.notas_en || []).length === (info.notas || []).length && (info.notas_en || []).length;
    var notas = notasEn ? info.notas_en : (info.notas || []);
    var falta = COBERTURA.some(function (c) { return !info.cobertura[c[0]]; });
    return '<div class="info-casa rev"><h3>' + EP.tr("O que o site já tem da ", "What this site has from the ") + nomeHtml + "</h3>" + EP.dataCasa(info.conferido) +
      '<ul class="cobertura-casa">' + COBERTURA.map(function (c) {
        var tem = !!info.cobertura[c[0]];
        return '<li class="' + (tem ? "tem" : "falta") + '"><span aria-hidden="true">' + (tem ? "✔️ " : "➖ ") + "</span>" +
          '<span class="sr">' + (tem ? EP.tr("Tem: ", "Available: ") : EP.tr("Não tem: ", "Not available: ")) + "</span>" + esc(EP.tr(c[2], c[3])) +
          (tem ? "" : " <small>(" + EP.tr("não está neste site", "not on this site") + ")</small>") + "</li>";
      }).join("") + "</ul>" +
      (notas.length ? '<ul class="notas-casa">' + notas.map(function (n) { return "<li>" + (EP.en && !notasEn ? EP.pt(esc(n)) : esc(n)) + "</li>"; }).join("") + "</ul>" : "") +
      (/^https:\/\//.test(info.site || "") ? '<p class="site-casa"><a href="' + esc(info.site) + '" target="_blank" rel="noopener" hreflang="pt-BR">' +
        EP.tr("Site oficial da ", "Official website of the ") + nomeHtml + ' <span aria-hidden="true">↗</span><span class="sr"> ' +
        EP.tr("(abre em outra aba)", "(opens in a new tab)") + "</span></a></p>" : "") +
      (/^https?:\/\//.test(info.sic || "") ? '<p class="site-casa"><a href="' + esc(info.sic) + '" target="_blank" rel="noopener" hreflang="pt-BR">' +
        EP.tr("Pedir uma informação à ", "Ask the ") + nomeHtml + EP.tr(" (Lei de Acesso à Informação)", " for information (Access to Information Law)") +
        ' <span aria-hidden="true">↗</span><span class="sr"> ' + EP.tr("(abre em outra aba)", "(opens in a new tab)") + "</span></a></p>" : "") +
      (falta ? '<p class="notas-casa" style="padding-left:0">' + EP.tr(
        "O que não está aqui pode ser pedido à Casa pela Lei de Acesso à Informação: qualquer pessoa pode pedir, de graça e sem dizer por quê. ",
        "Anything that is not here can be requested from the legislature under the Access to Information Law: anyone can ask, for free and without saying why. ") +
        '<a href="https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12527.htm" target="_blank" rel="noopener" hreflang="pt-BR">' + EP.tr("Lei nº 12.527/2011", "Law No. 12,527/2011") +
        ' <span aria-hidden="true">↗</span><span class="sr"> ' + EP.tr("(abre em outra aba)", "(opens in a new tab)") + "</span></a></p>" : "") + "</div>";
  };

  // ---------------------------------------------------------------- visual D (site-d-r14)
  // EP.casaD = true (a página do Brasil liga) ou o.d = true: o plenário fica em ordem alfabética dos partidos (os dois tons de
  // azul alternados, os mesmos para todos), e no lugar das barras "Quantos de cada partido" aparecem as etiquetas dos partidos
  // (botões de pelo menos 44 px, o caminho principal: as cadeiras são pequenas demais para tocar). Tocar numa etiqueta, numa
  // cadeira ou na sigla abre a gaveta (EP.gaveta) com as pessoas do partido, com os filtros de nome e de estado; o endereço guarda
  // a gaveta (?ver=partido:senado:PT). A tabela "partido × número" (o equivalente em texto do plenário), o que é um partido e o
  // "Você sabia?" ficam no "💡 Saber mais". A lista com os filtros de sempre continua embaixo, na página.
  var CASAS = {};
  function listaPartido(el, l, o, nomes) {
    var ufs = {};
    l.forEach(function (m) { if (m.uf) ufs[m.uf] = 1; });
    var listaUF = Object.keys(ufs).sort(function (a, b) { return EP.norm(EP.UFS[a] || a).localeCompare(EP.norm(EP.UFS[b] || b)); });
    el.innerHTML = '<div class="filtros-casa gv-filtros"><div class="busca"><input type="search" class="f-nome" placeholder="' + EP.tr("Procurar pelo nome", "Search by name") + '" aria-label="' +
      EP.tr("Procurar pelo nome", "Search by name") + '" autocomplete="off"></div>' +
      (o.filtroUF !== false && listaUF.length > 1 ? '<select class="f-uf" aria-label="' + EP.tr("Filtrar por estado", "Filter by state") + '"><option value="">' + EP.tr("Todos os estados", "All states") + "</option>" +
        listaUF.map(function (u) { return '<option value="' + u + '" data-busca="' + u + '">' + esc(EP.UFS[u] || u) + "</option>"; }).join("") + "</select>" : "") + "</div>" +
      '<p class="contagem" aria-live="polite"></p><div class="grade-pessoas gv-grade"></div>';
    var fNome = el.querySelector(".f-nome"), fUF = el.querySelector(".f-uf"), grade = el.querySelector(".grade-pessoas"), cont = el.querySelector(".contagem");
    if (fUF) EP.comboSelect(fUF, { placeholder: EP.tr("Digite o estado…", "Type a state…") });
    function desenha() {
      var q = EP.norm(fNome.value), uf = fUF ? fUF.value : "";
      var f = l.filter(function (m) { return (!q || EP.norm(m.nome).indexOf(q) > -1 || EP.norm(m.nomeCivil || "").indexOf(q) > -1) && (!uf || m.uf === uf); });
      grade.innerHTML = f.length ? f.map(function (m) { return (o.cartao || EP.cartaoPessoa)(m, o.extra ? o.extra(m) : ""); }).join("") :
        '<div class="vazio"><span class="grande" aria-hidden="true">🤷</span>' + EP.tr("Ninguém encontrado com esses filtros.", "No one found with these filters.") + "</div>";
      var t = f.length === l.length ? EP.tr("Mostrando " + (l.length === 1 ? "1 " + nomes.um : "os " + EP.num(l.length) + " " + nomes.varios) + ", em ordem alfabética.",
        "Showing " + (l.length === 1 ? "1 " + nomes.um : "all " + EP.num(l.length) + " " + nomes.varios) + ", in alphabetical order.") :
        EP.tr("Mostrando " + EP.num(f.length) + " de " + EP.num(l.length) + ".", "Showing " + EP.num(f.length) + " of " + EP.num(l.length) + ".");
      if (cont.textContent !== t) cont.textContent = t;
    }
    var tm = null;
    fNome.addEventListener("input", function () { clearTimeout(tm); tm = setTimeout(desenha, 150); });
    if (fUF) fUF.addEventListener("change", desenha);
    desenha();
  }
  EP.gavetaVer.partido = function (v) {
    var i = v.indexOf(":"), casa = v.slice(0, i), p = v.slice(i + 1), t0 = Date.now();
    if (!casa || !p) return;
    if (EP.abas && EP.abas.mostra) EP.abas.mostra(casa);
    (function tenta() {
      if (CASAS[casa]) CASAS[casa].abre(p);
      else if (Date.now() - t0 < 8000) setTimeout(tenta, 150);
    })();
  };

  EP.montaCasa = function (el, o) {
    var uid = "casa" + (++conta);
    var membros = EP.alfabetica(o.membros || []);
    var nomes = o.nomes || { um: EP.tr("pessoa", "person"), uma: EP.tr("pessoa", "person"), varios: EP.tr("pessoas", "people"), varias: EP.tr("pessoas", "people") };
    var nivel = Math.min(6, Math.max(2, o.nivel || 3));
    var total = membros.length;
    var modoD = o.d != null ? !!o.d : !!EP.casaD;

    if (!total) {
      el.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">📭</span>' +
        (o.vazio || EP.tr("A fonte oficial não mostra ninguém nesta lista agora.", "The official source does not show anyone on this list right now.")) + "</div>" +
        (o.fonte ? "<p>" + EP.botaoFontes(o.fonte, EP.tr("De onde vem esta lista?", "Where does this list come from?")) + "</p>" : "");
      return;
    }

    var porPartido = o.porPartido;
    if (!porPartido) {
      var cont = {};
      membros.forEach(function (m) { var p = m.partido || SEM; cont[p] = (cont[p] || 0) + 1; });
      porPartido = Object.keys(cont).map(function (p) { return { partido: p, n: cont[p] }; });
    }
    // do partido com mais cadeiras para o com menos (é só uma contagem); empate: ordem alfabética. No visual D, em ordem alfabética
    porPartido = porPartido.slice().sort(modoD ? function (a, b) { return EP.norm(a.partido).localeCompare(EP.norm(b.partido)); } :
      function (a, b) { return b.n - a.n || EP.norm(a.partido).localeCompare(EP.norm(b.partido)); });
    var idxPartido = {};
    porPartido.forEach(function (p, k) { idxPartido[p.partido] = k; });
    var maxN = porPartido.length ? porPartido[0].n : 1;
    var VIS = 999; // todos os partidos aparecem (esconder os menores daria destaque só aos maiores)

    var plen = T.plenario ? T.plenario({ total: total, grupos: porPartido.map(function (p) { return p.n; }), max: total > 300 ? 520 : total > 60 ? 440 : 380 }) : "";
    // a sigla de cada partido em cima da sua fatia. Só aparece sozinha quando a fatia é larga e a sigla não encosta numa
    // de partido maior; as outras aparecem ao passar o mouse ou tocar no partido
    var minSigla = Math.max(2, total * 0.03);
    // quando a sigla precisa ficar longe da fatia (por falta de espaço), uma linha fina liga as duas
    var siglas = plen ? '<div class="plen-rotulos" aria-hidden="true"><svg class="plen-linhas">' +
      porPartido.map(function (p, k) { return '<line class="lin-p" data-g="' + k + '"></line>'; }).join("") + "</svg>" + porPartido.map(function (p, k) {
      return '<span class="rot-p' + (k % 2 ? " b" : "") + (p.n >= minSigla ? " grande" : "") + '" data-g="' + k + '"><b>' + esc(nomePartido(p.partido)) + "</b><small>" + EP.num(p.n) + "</small></span>";
    }).join("") + "</div>" : "";
    var mulheres = membros.filter(function (m) { return m.genero === "F"; }).length;
    var homens = membros.filter(function (m) { return m.genero === "M"; }).length;
    var ufs = {};
    membros.forEach(function (m) { if (m.uf) ufs[m.uf] = 1; });
    var listaUF = Object.keys(ufs).sort(function (a, b) { return EP.norm(EP.UFS[a] || a).localeCompare(EP.norm(EP.UFS[b] || b)); });
    var h = "h" + nivel;
    var cadeira = EP.en ? "Each seat is one " + nomes.um + ". Each slice is one party." :
      "Cada cadeira é " + (/^(pessoa|deputada|senadora|vereadora)/.test(nomes.um) ? "uma " : "um ") + nomes.um + ". Cada fatia é um partido.";

    function textoContagem(n) {
      return n === total ? EP.tr("Mostrando todos os " + EP.num(total) + " " + (o.coletivo || nomes.varios) + ", em ordem alfabética.",
        "Showing all " + EP.num(total) + " " + (o.coletivo || nomes.varios) + ", in alphabetical order.") :
        EP.tr("Mostrando " + EP.num(n) + " de " + EP.num(total) + ", em ordem alfabética.", "Showing " + EP.num(n) + " of " + EP.num(total) + ", in alphabetical order.");
    }

    var topoHtml =
      '<div class="casa-resumo"><div class="plen-box rev"><div class="plen-area">' + plen + siglas + "</div><p>" + esc(cadeira) + (o.notaPlenario ? " " + esc(o.notaPlenario) : "") + "</p></div>" +
      '<div class="partidos rev" style="--i:1"><' + h + ' class="tit-p" id="' + uid + '-tit">' + esc(o.titPartidos || EP.tr("Quantos de cada partido", "Seats per party")) + "</" + h + ">" +
      '<div class="barras-p" role="group" aria-labelledby="' + uid + '-tit">' +
      porPartido.map(function (p, k) {
        return '<button type="button" class="barra-partido" data-g="' + k + '"' + (k >= VIS ? " hidden" : "") + ' aria-pressed="false">' +
          '<span class="nome-p">' + nomePartidoHtml(p.partido) + '</span> <span class="trilho-p" aria-hidden="true"><i data-w="' + (100 * p.n / maxN).toFixed(1) + '%"></i></span> ' +
          '<span class="n-p">' + EP.num(p.n) + '</span><span class="sr"> ' + esc(p.n === 1 ? nomes.um : nomes.varios) + "</span></button>";
      }).join("") + "</div>" +
      (porPartido.length > VIS ? '<button type="button" class="mais-p">' + EP.tr("Ver todos os " + porPartido.length + " partidos", "See all " + porPartido.length + " parties") + ' <span aria-hidden="true">▾</span></button>' : "") +
      '<p class="explica-p">' + EP.tr("Partido é um grupo de pessoas que se juntam para disputar eleições e defender ideias parecidas. No plenário, cada fatia é um partido: passe o mouse num partido (aqui na lista ou nas cadeiras) para acender as cadeiras dele, e toque ou clique para ver só quem é dele. As fatias e a lista vão do partido com mais cadeiras para o com menos: é só uma contagem, não um ranking. Nenhum partido tem cor própria, de propósito: os dois tons de azul só separam uma fatia da outra.",
        "A party is a group of people who join together to run in elections and defend similar ideas. In the chamber, each slice is one party: hover over a party (here in the list or on the seats) to light up its seats, and tap or click it to see only its members. The slices and the list go from the party with the most seats to the one with the fewest: it is just a count, not a ranking. No party has its own color, on purpose: the two shades of blue only separate one slice from the next.") + "</p></div></div>" +
      (mulheres + homens ? '<p class="sabia rev"><span aria-hidden="true">💡</span><span>' + (o.sabia ? o.sabia(mulheres, homens) :
        (EP.en ? "Did you know? Right now there are <b>" + EP.num(mulheres) + (mulheres === 1 ? " woman" : " women") + "</b> and <b>" + EP.num(homens) + (homens === 1 ? " man" : " men") + "</b> in this list."
          : "Você sabia? Hoje são <b>" + EP.plural(mulheres, nomes.uma, nomes.varias) + "</b> e <b>" + EP.plural(homens, nomes.um, nomes.varios) + "</b>.")) + "</span></p>" : "") +
      '<div class="filtros-casa"><div class="busca"><input type="search" class="f-nome" placeholder="' + EP.tr("Procurar pelo nome", "Search by name") + '" aria-label="' +
      EP.tr("Procurar pelo nome", "Search by name") + '" autocomplete="off"></div>' +
      (o.filtroUF !== false && listaUF.length > 1 ? '<select class="f-uf" aria-label="' + EP.tr("Filtrar por estado", "Filter by state") + '"><option value="">' + EP.tr("Todos os estados", "All states") + "</option>" +
        listaUF.map(function (u) { return '<option value="' + u + '" data-busca="' + u + '">' + esc(EP.UFS[u] || u) + "</option>"; }).join("") + "</select>" : "<span></span>") +
      '<select class="f-partido" aria-label="' + EP.tr("Filtrar por partido", "Filter by party") + '"><option value="">' + EP.tr("Todos os partidos", "All parties") + "</option>" +
      EP.alfabetica(porPartido, "partido").map(function (p) {
        return '<option value="' + esc(p.partido) + '"' + (EP.en && p.partido !== SEM ? ' lang="pt-BR"' : "") + ">" + esc(nomePartido(p.partido)) + " (" + EP.num(p.n) + ")</option>";
      }).join("") + "</select></div>";
    // visual D: o plenário, as etiquetas dos partidos e o "Saber mais" com a tabela (o equivalente em texto do plenário)
    var topoD = !modoD ? "" :
      '<div class="casa-resumo d-casa"><p class="d-linha d-casa-linha">' + esc(EP.tr(EP.num(porPartido.length) + " " + (porPartido.length === 1 ? "partido" : "partidos") + ". Toque num partido para ver quem é dele.",
        EP.num(porPartido.length) + " " + (porPartido.length === 1 ? "party" : "parties") + ". Tap a party to see its members.")) + "</p>" +
      (plen ? '<div class="plen-box rev"><div class="plen-area">' + plen + siglas + "</div></div>" : "") +
      '<div class="d-partidos" role="group" aria-labelledby="' + uid + '-tit"><' + h + ' class="sr" id="' + uid + '-tit">' +
      esc(EP.tr("Os partidos, em ordem alfabética, com o número de " + nomes.varios + " (toque para ver quem é de cada um)", "The parties, in alphabetical order, with the number of " + nomes.varios + " (tap to see each party's members)")) + "</" + h + ">" +
      porPartido.map(function (p, k) {
        return '<button type="button" class="d-partido' + (k % 2 ? " b" : "") + '" data-g="' + k + '" aria-haspopup="dialog"><b>' + nomePartidoHtml(p.partido) + "</b><span>" + EP.num(p.n) +
          '</span><span class="sr"> ' + esc(p.n === 1 ? nomes.um : nomes.varios) + "</span></button>";
      }).join("") + "</div>" +
      EP.d.saiba('<p>' + esc(cadeira) + (o.notaPlenario ? " " + esc(o.notaPlenario) : "") + "</p>" +
        '<p class="explica-p">' + EP.tr("Partido é um grupo de pessoas que se juntam para disputar eleições e defender ideias parecidas. No plenário, cada fatia é um partido, em ordem alfabética. Nenhum partido tem cor própria, de propósito: os dois tons de azul só separam uma fatia da outra.",
          "A party is a group of people who join together to run in elections and defend similar ideas. In the chamber, each slice is one party, in alphabetical order. No party has its own color, on purpose: the two shades of blue only separate one slice from the next.") + "</p>" +
        (mulheres + homens ? '<p class="sabia"><span aria-hidden="true">💡 </span>' + (o.sabia ? o.sabia(mulheres, homens) :
          (EP.en ? "Did you know? Right now there are <b>" + EP.num(mulheres) + (mulheres === 1 ? " woman" : " women") + "</b> and <b>" + EP.num(homens) + (homens === 1 ? " man" : " men") + "</b> in this list."
            : "Você sabia? Hoje são <b>" + EP.plural(mulheres, nomes.uma, nomes.varias) + "</b> e <b>" + EP.plural(homens, nomes.um, nomes.varios) + "</b>.")) + "</p>" : "") +
        '<table class="d-tab"><caption>' + esc(EP.tr("Quantos " + nomes.varios + " cada partido tem (ordem alfabética)", "How many " + nomes.varios + " each party has (alphabetical order)")) + "</caption>" +
        '<thead><tr><th scope="col">' + EP.tr("Partido", "Party") + '</th><th scope="col">' + esc(nomes.varios.charAt(0).toUpperCase() + nomes.varios.slice(1)) + "</th></tr></thead><tbody>" +
        porPartido.map(function (p) { return '<tr><th scope="row">' + nomePartidoHtml(p.partido) + "</th><td>" + EP.num(p.n) + "</td></tr>"; }).join("") + "</tbody></table>",
        EP.tr("Como funciona e a tabela dos partidos", "How it works and the table of parties"), "d-saiba-casa") + "</div>" +
      '<div class="filtros-casa"><div class="busca"><input type="search" class="f-nome" placeholder="' + EP.tr("Procurar pelo nome", "Search by name") + '" aria-label="' +
      EP.tr("Procurar pelo nome", "Search by name") + '" autocomplete="off"></div>' +
      (o.filtroUF !== false && listaUF.length > 1 ? '<select class="f-uf" aria-label="' + EP.tr("Filtrar por estado", "Filter by state") + '"><option value="">' + EP.tr("Todos os estados", "All states") + "</option>" +
        listaUF.map(function (u) { return '<option value="' + u + '" data-busca="' + u + '">' + esc(EP.UFS[u] || u) + "</option>"; }).join("") + "</select>" : "<span></span>") +
      '<select class="f-partido" aria-label="' + EP.tr("Filtrar por partido", "Filter by party") + '"><option value="">' + EP.tr("Todos os partidos", "All parties") + "</option>" +
      porPartido.map(function (p) {
        return '<option value="' + esc(p.partido) + '"' + (EP.en && p.partido !== SEM ? ' lang="pt-BR"' : "") + ">" + esc(nomePartido(p.partido)) + " (" + EP.num(p.n) + ")</option>";
      }).join("") + "</select></div>";
    if (modoD) topoHtml = topoD;
    // o.recolher (página do Brasil, "Quem assume"): plenário, partidos e filtros num bloco que abre e fecha
    el.innerHTML = (o.recolher ? EP.blocoAbre("casa-recolhe", '<span aria-hidden="true">🏛️</span><span>' + esc(o.recolher) + "</span>", topoHtml) : topoHtml) +
      '<p class="contagem" aria-live="polite">' + esc(textoContagem(total)) + '</p><div class="grade-pessoas"></div>' +
      (o.fonte ? '<p class="fonte-casa">' + EP.botaoFontes(o.fonte, EP.tr("De onde vem esta lista?", "Where does this list come from?")) +
        (o.atualizado ? ' <small class="muted">' + EP.tr("Atualizado em ", "Updated on ") + EP.data(o.atualizado) + "</small>" : "") + "</p>" : "");

    var fNome = el.querySelector(".f-nome"), fUF = el.querySelector(".f-uf"), fPart = el.querySelector(".f-partido");
    // ui-r9: os filtros ficam no endereço (?senado-nome=ana&senado-partido=PT) e quantos "Mostrar mais"/"Ver todos" estavam
    // abertos fica na memória do histórico (EP.memo, js/comum.js): voltando de um perfil, a lista aparece como estava
    var M = o.chave || (el.id ? el.id.replace(/^casa-/, "") : ((el.closest && el.closest("section[id]")) || {}).id || uid);
    function temOpcao(sel, v) { return !!sel && [].some.call(sel.options, function (op) { return op.value === v; }); }
    var lidos = EP.memo ? { nome: EP.memo.url(M + "-nome"), uf: EP.memo.url(M + "-uf"), partido: EP.memo.url(M + "-partido"), n: EP.memo.le(M + "-n") } : {};
    if (lidos.nome) fNome.value = lidos.nome;
    if (lidos.uf && temOpcao(fUF, lidos.uf)) fUF.value = lidos.uf;
    if (lidos.partido && temOpcao(fPart, lidos.partido)) fPart.value = lidos.partido;
    if ((lidos.nome || fPart.value || (fUF && fUF.value)) && el.querySelector("details.casa-recolhe")) el.querySelector("details.casa-recolhe").open = true;
    // listas de escolha com busca: a pessoa digita e as opções vão aparecendo
    if (fUF) EP.comboSelect(fUF, { placeholder: EP.tr("Digite o estado…", "Type a state…") });
    EP.comboSelect(fPart, { placeholder: EP.tr("Digite o partido…", "Type a party…") });
    var grade = el.querySelector(".grade-pessoas"), contagem = el.querySelector(".contagem"), plenEl = el.querySelector(".plenario");
    var LOTE = o.lote || 60, mostrando = LOTE;
    if (lidos.n === "todos") mostrando = Infinity;
    else if (typeof lidos.n === "number" && lidos.n > LOTE) mostrando = lidos.n;
    function lembra() {
      if (!EP.memo) return;
      EP.memo.poeUrl(M + "-nome", fNome.value.trim());
      if (fUF) EP.memo.poeUrl(M + "-uf", fUF.value);
      EP.memo.poeUrl(M + "-partido", fPart.value);
      EP.memo.grava(M + "-n", mostrando === Infinity ? "todos" : mostrando > LOTE ? mostrando : null);
    }
    var area = el.querySelector(".plen-area"), barrasEl = el.querySelector(modoD ? ".d-partidos" : ".barras-p");
    var siglasEls = [].slice.call(el.querySelectorAll(".rot-p")), linhasEls = [].slice.call(el.querySelectorAll(".lin-p"));
    var barras = [].slice.call(el.querySelectorAll(modoD ? ".d-partido" : ".barra-partido"));
    var cadeirasDe = {};
    if (plenEl) [].forEach.call(plenEl.querySelectorAll("i[data-g]"), function (c) { var g = c.getAttribute("data-g"); (cadeirasDe[g] = cadeirasDe[g] || []).push(c); });

    // partido aceso no plenário: o que está sob o mouse ou com o foco do teclado (só para olhar) ou, sem isso, o escolhido no filtro
    var escolhido = null, espiando = null, origemEspia = null, aceso = null;
    function acende() {
      var g = espiando != null ? espiando : escolhido;
      if (g !== aceso) {
        (cadeirasDe[aceso] || []).forEach(function (c) { c.classList.remove("aceso"); });
        (cadeirasDe[g] || []).forEach(function (c) { c.classList.add("aceso"); });
        aceso = g;
        if (plenEl) plenEl.classList.toggle("tem-aceso", g != null);
        if (area) area.classList.toggle("tem-aceso", g != null);
        siglasEls.concat(linhasEls).forEach(function (s) { s.classList.toggle("ativo", +s.getAttribute("data-g") === g); });
      }
      barras.forEach(function (b) { b.classList.toggle("realce", espiando != null && +b.getAttribute("data-g") === espiando); });
    }
    // origem: "mouse" ou "teclado". Quando um sai, o outro continua valendo (o mouse saiu, mas o foco ainda está num partido)
    function espia(g, origem) {
      if (g == null && origem !== origemEspia) return;
      origemEspia = g == null ? null : origem;
      if (g !== espiando) { espiando = g; acende(); }
    }
    function grupoDe(alvo) {
      var x = alvo && alvo.closest ? alvo.closest(".barra-partido, .d-partido, .plenario i[data-g], .rot-p") : null;
      return x && el.contains(x) ? +x.getAttribute("data-g") : null;
    }
    // no toque não existe "passar por cima": tocar já escolhe o partido (ver o clique, mais abaixo)
    [barrasEl, area].forEach(function (zona) {
      if (!zona) return;
      zona.addEventListener("pointerover", function (e) {
        if (e.pointerType === "touch") return;
        var g = grupoDe(e.target);
        if (g != null) espia(g, "mouse");
      });
      zona.addEventListener("pointerleave", function (e) { if (e.pointerType !== "touch") espia(null, "mouse"); });
    });
    if (barrasEl) {
      barrasEl.addEventListener("focusin", function (e) {
        var b = e.target.closest(".barra-partido, .d-partido"), teclado = true;
        try { teclado = b.matches(":focus-visible"); } catch (x) {}
        if (b && teclado) espia(+b.getAttribute("data-g"), "teclado");
      });
      barrasEl.addEventListener("focusout", function (e) { if (!barrasEl.contains(e.relatedTarget)) espia(null, "teclado"); });
    }

    // põe cada sigla do lado de fora da sua fatia, sem cobrir nenhuma cadeira. O plenário está inclinado em 3D: a posição vem do
    // marco invisível de cada fatia. Se a borda da área não deixar ir para fora, a sigla sobe. Indo do maior partido para o menor,
    // a sigla que encostaria numa já posta fica escondida (aparece ao passar o mouse ou tocar no partido).
    function posSiglas() {
      if (!area || !plenEl || !siglasEls.length) return;
      var ra = area.getBoundingClientRect(), mc = plenEl.querySelector(".marco.centro");
      if (!ra.width || !mc) return;
      function relativa(el) { var b = el.getBoundingClientRect(); return { l: b.left - ra.left, r: b.right - ra.left, t: b.top - ra.top, b: b.bottom - ra.top }; }
      function bate(c, lista) { return lista.some(function (q) { return c.l < q.r && c.r > q.l && c.t < q.b && c.b > q.t; }); }
      var cads = [].map.call(plenEl.querySelectorAll("i"), relativa), postas = [];
      var rc = relativa(mc), cx = rc.l, cy = rc.t;
      // do maior partido para o menor (no visual D, a ordem dos grupos é a alfabética)
      siglasEls.slice().sort(function (a, b) { return porPartido[+b.getAttribute("data-g")].n - porPartido[+a.getAttribute("data-g")].n; }).forEach(function (s) {
        var m = plenEl.querySelector('.marco[data-g="' + s.getAttribute("data-g") + '"]');
        if (!m) return;
        var rm = relativa(m), w = s.offsetWidth, h = s.offsetHeight, dx = rm.l - cx, dy = rm.t - cy, d = Math.sqrt(dx * dx + dy * dy) || 1;
        dx /= d;
        dy /= d;
        // distância do centro da sigla até a borda dela, na direção de fora
        var ate = Math.min(Math.abs(dx) > 0.01 ? w / 2 / Math.abs(dx) : 1e6, Math.abs(dy) > 0.01 ? h / 2 / Math.abs(dy) : 1e6) + 2;
        var lugares = [], k;
        for (k = 0; k <= 4; k++) lugares.push([rm.l + dx * (ate + 6 * k), rm.t + dy * (ate + 6 * k)]);
        for (k = 1; k <= 16; k++) lugares.push([rm.l + dx * ate, rm.t + dy * ate - 6 * k]);
        lugares = lugares.map(function (p) {
          var x = Math.max(w / 2 + 2, Math.min(ra.width - w / 2 - 2, p[0])), y = Math.max(h / 2 + 2, Math.min(ra.height - h / 2, p[1]));
          return { x: x, y: y, c: { l: x - w / 2 - 4, r: x + w / 2 + 4, t: y - h / 2 - 3, b: y + h / 2 + 3 } };
        });
        var livre = null, semCadeira = null;
        lugares.some(function (p) {
          if (bate(p.c, cads)) return false;
          if (!semCadeira) semCadeira = p;
          if (bate(p.c, postas)) return false;
          livre = p;
          return true;
        });
        var p = livre || semCadeira || lugares[0];
        s.style.left = p.x.toFixed(1) + "px";
        s.style.top = p.y.toFixed(1) + "px";
        var cabe = !!livre && s.classList.contains("grande");
        s.classList.toggle("cabe", cabe);
        if (cabe) postas.push(p.c);
        // a linha vai do marco da fatia até o ponto mais perto da sigla; só aparece se a sigla ficou longe
        var lin = linhasEls[+s.getAttribute("data-g")];
        if (lin) {
          var qx = Math.max(p.x - w / 2, Math.min(p.x + w / 2, rm.l)), qy = Math.max(p.y - h / 2, Math.min(p.y + h / 2, rm.t));
          lin.setAttribute("x1", rm.l.toFixed(1));
          lin.setAttribute("y1", rm.t.toFixed(1));
          lin.setAttribute("x2", qx.toFixed(1));
          lin.setAttribute("y2", qy.toFixed(1));
          lin.classList.toggle("longe", Math.sqrt((qx - rm.l) * (qx - rm.l) + (qy - rm.t) * (qy - rm.t)) > 12);
          lin.classList.toggle("cabe", cabe);
        }
      });
    }
    var pedido = 0;
    function pedeSiglas() { cancelAnimationFrame(pedido); pedido = requestAnimationFrame(posSiglas); }
    if (area && siglasEls.length) {
      if ("ResizeObserver" in window) new ResizeObserver(pedeSiglas).observe(area);
      else window.addEventListener("resize", pedeSiglas);
      window.addEventListener("ep-a11y", pedeSiglas);
      window.addEventListener("ep-aba", pedeSiglas);  // uma aba (js/abas.js) apareceu: o plenário que estava escondido já tem tamanho
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(pedeSiglas);
      pedeSiglas();
    }

    function filtrados() {
      var q = EP.norm(fNome.value), uf = fUF ? fUF.value : "", pa = fPart.value;
      return membros.filter(function (m) {
        return (!q || EP.norm(m.nome).indexOf(q) > -1 || EP.norm(m.nomeCivil || "").indexOf(q) > -1) && (!uf || m.uf === uf) && (!pa || (m.partido || SEM) === pa);
      });
    }
    function desenha(focarDe) {
      lembra();
      var l = filtrados();
      var vis = l.slice(0, mostrando);
      grade.innerHTML = vis.length ? vis.map(function (m) { return (o.cartao || EP.cartaoPessoa)(m, o.extra ? o.extra(m) : ""); }).join("") :
        '<div class="vazio"><span class="grande" aria-hidden="true">🤷</span>' + EP.tr("Ninguém encontrado com esses filtros.", "No one found with these filters.") + "</div>";
      if (l.length > vis.length) {
        var n = Math.min(LOTE, l.length - vis.length);
        // o.verTodos: o botão diz quantos são e mostra todos de uma vez ("Ver todos os 513 deputados"; com filtro, "os 14 encontrados")
        var col = o.coletivo || nomes.varios, todos = /^pessoas/.test(col) ? "todas as " : "todos os ";
        var rot = !o.verTodos ? EP.tr("Mostrar mais " + n, "Show " + n + " more") : l.length === total ?
          EP.tr("Ver " + todos + EP.num(total) + " " + col, "See all " + EP.num(total) + " " + col) :
          EP.tr("Ver " + todos + EP.num(l.length) + " encontrad" + (todos === "todas as " ? "as" : "os"), "See all " + EP.num(l.length) + " found");
        grade.insertAdjacentHTML("beforeend", '<div class="mais-lista" style="grid-column:1/-1"><button type="button" class="btn claro peq ver-mais">' +
          esc(rot) + ' <span aria-hidden="true">▾</span></button></div>');
      }
      var txt = textoContagem(l.length);
      // o.verTodos: enquanto só o resumo aparece, a contagem diz isso ("Mostrando os 12 primeiros de 81 senadores")
      if (o.verTodos && vis.length < l.length) {
        var fem = /^pessoas/.test(o.coletivo || nomes.varios);
        txt = l.length === total ? EP.tr("Mostrando " + (fem ? "as " : "os ") + EP.num(vis.length) + (fem ? " primeiras" : " primeiros") + " de " + EP.num(total) + " " + (o.coletivo || nomes.varios) + ", em ordem alfabética.",
          "Showing the first " + EP.num(vis.length) + " of " + EP.num(total) + " " + (o.coletivo || nomes.varios) + ", in alphabetical order.") :
          EP.tr("Mostrando " + (fem ? "as " : "os ") + EP.num(vis.length) + (fem ? " primeiras" : " primeiros") + " de " + EP.num(l.length) + " encontrad" + (fem ? "as" : "os") + " (de " + EP.num(total) + "), em ordem alfabética.",
            "Showing the first " + EP.num(vis.length) + " of the " + EP.num(l.length) + " found (out of " + EP.num(total) + "), in alphabetical order.");
      }
      if (contagem.textContent !== txt) contagem.textContent = txt;
      // acende as cadeiras do partido escolhido
      var pa = fPart.value;
      escolhido = pa && idxPartido[pa] != null ? idxPartido[pa] : null;
      acende();
      [].forEach.call(el.querySelectorAll(".barra-partido"), function (b) {
        var on = pa !== "" && +b.getAttribute("data-g") === idxPartido[pa];
        b.setAttribute("aria-pressed", String(on));
        if (on) b.hidden = false;
      });
      // depois de "Mostrar mais", o foco vai para a primeira pessoa nova
      if (focarDe != null) {
        var cards = grade.querySelectorAll(".pessoa-card");
        if (cards[focarDe]) EP.focaSuave(cards[focarDe]);
      }
    }
    var t = null;
    fNome.addEventListener("input", function () { clearTimeout(t); t = setTimeout(function () { mostrando = LOTE; desenha(); }, 200); });
    if (fUF) fUF.addEventListener("change", function () { mostrando = LOTE; desenha(); });
    fPart.addEventListener("change", function () { mostrando = LOTE; desenha(); });
    // visual D: a gaveta com as pessoas de um partido (os filtros de nome e de estado; Esc, ✕ e o Voltar fecham)
    var secId = ((el.closest && el.closest("section[id]")) || {}).id || M;
    function abrePartido(g, de) {
      var pp = porPartido[g];
      if (!pp) return;
      var l = membros.filter(function (m) { return (m.partido || SEM) === pp.partido; });
      // a gaveta cobre a página: o "passar o mouse" de antes não termina sozinho (o ponteiro sai por cima da gaveta)
      espiando = null;
      origemEspia = null;
      acende();
      var casaTxt = (el.closest && el.closest("section[id]") && el.closest("section[id]").querySelector("h2")) ? el.closest("section[id]").querySelector("h2").textContent.replace(/\s+/g, " ").trim() : "";
      EP.gaveta({ tit: nomePartidoHtml(pp.partido), sub: [casaTxt, EP.tr("em ordem alfabética", "in alphabetical order")].filter(Boolean).join(" · "), ver: "partido:" + secId + ":" + pp.partido,
        corpo: function (c) {
          c.innerHTML = '<div class="d-g-conta"><b>' + EP.num(l.length) + "</b><span>" + esc(EP.tr("de " + EP.num(total) + " " + nomes.varios, "of " + EP.num(total) + " " + nomes.varios)) +
            '</span><span class="d-g-prop" aria-hidden="true"><i style="width:' + (100 * l.length / Math.max(1, total)).toFixed(1) + '%"></i></span></div>' +
            '<div class="gv-lista-partido"></div>' + (o.fonte ? '<p class="gv-fonte">' + EP.botaoFontes(o.fonte, EP.tr("De onde vem esta lista?", "Where does this list come from?")) + "</p>" : "");
          listaPartido(c.querySelector(".gv-lista-partido"), l, o, nomes);
        } }, de);
    }
    if (modoD) {
      CASAS[secId] = { abre: function (p, de) {
        var k = -1;
        porPartido.some(function (x, i) { if (x.partido === p) { k = i; return true; } return false; });
        if (k > -1) abrePartido(k, de || el.querySelector('.d-partido[data-g="' + k + '"]'));
      } };
    }
    el.addEventListener("click", function (e) {
      // tocar ou clicar num partido (na lista, numa cadeira ou na sigla) mostra só quem é dele; de novo, mostra todos.
      // No visual D, abre a gaveta com as pessoas do partido (o foco volta para a etiqueta quando ela fecha)
      var b = e.target.closest(".barra-partido, .d-partido, .plenario i[data-g], .rot-p");
      if (b && modoD) {
        var g = +b.getAttribute("data-g");
        abrePartido(g, b.classList.contains("d-partido") ? b : el.querySelector('.d-partido[data-g="' + g + '"]'));
        return;
      }
      if (b) {
        var p = porPartido[+b.getAttribute("data-g")].partido;
        fPart.value = fPart.value === p ? "" : p;
        EP.comboSync(fPart);
        mostrando = LOTE;
        desenha();
        return;
      }
      var mp = e.target.closest(".mais-p");
      if (mp) {
        var novos = el.querySelectorAll(".barra-partido[hidden]");
        [].forEach.call(novos, function (x) { x.hidden = false; });
        mp.remove();
        if (novos[0]) EP.focaSuave(novos[0]);
        return;
      }
      if (e.target.closest(".ver-mais")) {
        var de = mostrando;
        mostrando = o.verTodos ? Infinity : mostrando + LOTE;
        desenha(de);
      }
    });
    // o.verTodos: quem volta de um perfil (js/comum.js, EP.voltaAlvo e o evento "ep-volta") encontra a pessoa mesmo se ela
    // estava depois do resumo: a lista volta inteira, como estava quando a pessoa clicou
    function revela(id) {
      if (!id || mostrando === Infinity) return false;
      var k = -1;
      filtrados().some(function (m, i) { if (m.id === id || m.link === id) { k = i; return true; } return false; });
      if (k < mostrando) return false;
      mostrando = Infinity;
      return true;
    }
    if (o.verTodos) {
      var va = EP.voltaAlvo;
      if (va && Date.now() - va.t < 15000) revela(va.id);
      window.addEventListener("ep-volta", function (ev) { if (revela(ev.detail && ev.detail.id)) desenha(); });
    }
    desenha();

    // anima o plenário e as barras quando aparecem na tela
    function anima() {
      if (plenEl) {
        plenEl.classList.add("cheio");
        // depois de encher, as cadeiras acendem e apagam juntas (sem a onda da entrada)
        setTimeout(function () { plenEl.classList.add("pronto"); }, 1600);
      }
      if (area) area.classList.add("cheio");
      [].forEach.call(el.querySelectorAll(".trilho-p i"), function (i) { i.style.width = i.getAttribute("data-w"); });
    }
    if ("IntersectionObserver" in window && !EP.reduzido) {
      var io = new IntersectionObserver(function (ents) {
        if (ents.some(function (x) { return x.isIntersecting; })) { setTimeout(anima, 250); io.disconnect(); }
      }, { threshold: 0.2 });
      io.observe(el.querySelector(".casa-resumo"));
    } else anima();
    EP.revelar(el);
  };
})();
