/* Quem assume nos próximos mandatos (frente "eleitos 2026"):
   - o mandato 2027 do "Ver outro mandato" nas páginas do Brasil e do estado (brasil.html?mandato=2027,
     estado.html?uf=SP&mandato=2027; os links antigos #quem-assume levam para lá): as mesmas abas da página de hoje
     (mandatos-r11), com quem foi eleito em 2026, a data da posse de cada cargo e como ficam o Senado, a Câmara e a Assembleia
     a partir da posse (EP.eleitos.brasilAbas, EP.eleitos.estadoAbas);
   - "A próxima eleição" na página da cidade: a data, o que se escolhe, a posse e as eleições suplementares;
   - o perfil de quem foi eleito em 2026 e não tem cargo hoje (pessoa.html?id=e26-<UF>-<SQ_CANDIDATO>), que o js/pessoa.js
     monta com EP.eleitos.perfil(id).
   Lê dados/eleitos/BR.json, dados/eleitos/<UF>.json e dados/eleitos/municipal.json (scripts/eleitos.py). Cada cargo sai dos
   arquivos no dia da posse: a aba daquele cargo passa a dizer que ele já tomou posse, e sem arquivo o endereço leva para hoje. */
(function () {
  "use strict";
  var EP = window.EP, D = EP.trd, esc = EP.esc;
  if (!EP) return;
  var X = EP.eleitos = {};
  var CF = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm";
  var LEI_PARTIDOS = "https://www.planalto.gov.br/ccivil_03/leis/l9096.htm";

  function hoje() {
    var d = new Date(), m = d.getMonth() + 1, dia = d.getDate();
    return d.getFullYear() + "-" + (m < 10 ? "0" : "") + m + "-" + (dia < 10 ? "0" : "") + dia;
  }
  function fonteCF(pt, en) {
    var f = { veiculo: "Planalto", titulo: EP.tr("Constituição Federal, " + pt, "Federal Constitution, " + en + " (in Portuguese)"), url: CF, data: "1988-10-05" };
    if (EP.en) f.lang = "en";
    return f;
  }
  function minus(s) { s = String(s || ""); return s.charAt(0).toLowerCase() + s.slice(1); }
  function nomePartido(p) { return /^sem partido$/i.test(p || "") ? EP.tr("Sem partido", "No party") : p || ""; }
  function novaAba() { return '<span class="sr"> ' + EP.tr("(abre em outra aba)", "(opens in a new tab)") + "</span>"; }
  function linkFora(url, html) {
    return '<a href="' + esc(url) + '" target="_blank" rel="noopener"' + (EP.en ? ' hreflang="pt-BR"' : "") + ">" + html + ' <span aria-hidden="true">↗</span>' + novaAba() + "</a>";
  }
  function urlPerfil(id) { return "pessoa.html?id=" + encodeURIComponent(id); }
  function chip(ic, txt, cls) { return '<span class="chip ' + (cls || "neutro") + '"><span aria-hidden="true">' + ic + " </span>" + esc(txt) + "</span>"; }
  function votos(n, chapa) {
    if (n == null) return "";
    return EP.tr(EP.num(n) + (n === 1 ? " voto" : " votos") + (chapa ? " da chapa" : ""), EP.num(n) + (n === 1 ? " vote" : " votes") + (chapa ? " for the ticket" : ""));
  }
  // o cargo de hoje (atual) ou o que a pessoa deixou para concorrer (antes), com o lugar: "deputado estadual (SP)",
  // "vereadora em Porto Velho (RO)"
  function cargoLugar(c) {
    if (!c) return "";
    var cid = /\(/.test(c.onde || "");
    var pt = minus(c.cargo) + (c.onde ? (cid ? " em " : " (") + c.onde + (cid ? "" : ")") : "");
    var en = D.cargo(c.cargo) + (c.onde ? (cid ? " in " : " (") + c.onde + (cid ? "" : ")") : "");
    return EP.tr(pt, en);
  }
  // de onde a pessoa vem: só a situação de hoje, sem adjetivo (é uma contagem, não um julgamento)
  function chipChegada(m) {
    var g = m.genero;
    if (m.chegada === "reeleicao") return chip("🔁", EP.tr(EP.gen(g, "Reeleito", "Reeleita"), "Re-elected"));
    if (m.chegada === "troca" && m.atual) return chip("🔀", EP.tr("Hoje: ", "Today: ") + cargoLugar(m.atual));
    if (m.antes) return chip("↩️", EP.tr("Era ", "Was ") + cargoLugar(m.antes));
    return chip("🆕", EP.tr("Sem cargo eletivo hoje", "No elected office today"));
  }
  // "Deputada federal eleita" / "Federal Deputy-elect"
  var ELEITO_EN = { pres: "President-elect", vp: "Vice President-elect", gov: "Governor-elect", vgov: "Vice Governor-elect", sen: "Senator-elect",
    supl1: "Elected 1st alternate senator", supl2: "Elected 2nd alternate senator", dep: "Federal Deputy-elect", dest: "State Deputy-elect", dist: "District Deputy-elect" };
  var CARGO_EN = { pres: "President", vp: "Vice President", gov: "governor", vgov: "vice governor", sen: "senator", supl1: "1st alternate senator",
    supl2: "2nd alternate senator", dep: "federal deputy", dest: "state deputy", dist: "district deputy" };
  function tipoDe(p) { return p.tipo === "dest" && p.uf === "DF" ? "dist" : p.tipo; }
  function eleitoCargo(p) { return EP.tr((p.cargo || "") + " eleit" + (p.genero === "F" ? "a" : "o"), ELEITO_EN[tipoDe(p)] || "Elected"); }
  // "Eleita deputada federal em 2026" / "Elected federal deputy in 2026"
  function eleitoEm(p) { return EP.tr("Eleit" + (p.genero === "F" ? "a " : "o ") + minus(p.cargo) + " em 2026", "Elected " + (CARGO_EN[tipoDe(p)] || "") + " in 2026"); }
  function posseTxt(data) { return EP.tr("Toma posse em ", "Takes office on ") + EP.dataLonga(data); }
  X.chipChegada = chipChegada;

  // cartão de pessoa (o mesmo desenho do EP.cartaoPessoa, com a chegada no lugar do selo de 2026): leva ao perfil de hoje
  // (quem já tem cargo) ou ao perfil e26- (quem não tem). Suplente de senador de 2022 que assume uma vaga: leva ao TSE.
  function cartao(m, extra) {
    var linha2 = [nomePartido(m.partido), m.uf && m.uf !== "BR" ? m.uf : ""].filter(Boolean).join(" · ");
    var fora = /^https?:/.test(m.link || "");
    return '<a class="pessoa-card" href="' + esc(fora ? m.link : urlPerfil(m.link || m.id)) + '"' + (fora ? ' target="_blank" rel="noopener"' : "") + ">" +
      EP.av(m.foto, m.nome) + "<b>" + EP.pt(esc(m.nome)) + "</b>" + (extra ? "<small>" + esc(extra) + "</small>" : "") +
      (linha2 ? "<small>" + esc(linha2) + "</small>" : "") + (m.chipHtml != null ? m.chipHtml : chipChegada(m)) + (fora ? novaAba() : "") + "</a>";
  }
  // cartão grande (presidente, governador e vices eleitos)
  function cartaoGrande(p, rotulo) {
    if (!p) return "";
    return '<a class="pessoa-grande rev" href="' + urlPerfil(p.link || p.id) + '">' + EP.av(p.foto, p.nome, null, true) +
      '<span><span class="cargo">' + esc(rotulo || eleitoCargo(p)) + "</span><b>" + EP.pt(esc(p.nome)) + "</b><small>" +
      [p.partido ? EP.pt(esc(nomePartido(p.partido))) : "", esc(votos(p.votos, p.votosDaChapa))].filter(Boolean).join(" · ") + "</small>" +
      (p.situacao ? "<small>" + D.situacao(p.situacao, p.situacao_en) + "</small>" : "") +
      '<small class="posse-e26">' + esc(posseTxt(p.posse)) + "</small>" + chipChegada(p) +
      '<span class="ver">' + EP.tr("Ver mais", "See more") + ' <span aria-hidden="true">›</span></span></span></a>';
  }
  // ---------------------------------------------------------------- peças comuns
  var MESES = { pt: ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"],
    en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] };
  // folhinha de calendário (desenho, escondido do leitor de tela: a data vem escrita ao lado)
  function folhinha(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
    if (!m) return "";
    return '<span class="folhinha" aria-hidden="true"><span class="f-mes">' + (EP.en ? MESES.en : MESES.pt)[+m[2] - 1] + '</span><span class="f-dia">' + (+m[3]) +
      '</span><span class="f-ano">' + m[1] + "</span></span>";
  }
  // linha do tempo das posses: [{data, txt}] em ordem de data (as que já passaram não aparecem)
  function linhaDoTempo(itens, idTit) {
    var h = hoje();
    var dias = {};
    itens.forEach(function (x) { if (x.data && x.data > h) (dias[x.data] = dias[x.data] || []).push(x.txt); });
    itens = Object.keys(dias).sort().map(function (d) { return { data: d, txt: dias[d].join("; ") }; });
    if (!itens.length) return "";
    return '<ol class="posses rev"' + (idTit ? ' aria-labelledby="' + idTit + '"' : "") + ">" + itens.map(function (x) {
      return "<li>" + folhinha(x.data) + '<span class="p-txt"><b>' + esc(EP.dataLonga(x.data)) + "</b><span>" + x.txt + "</span></span></li>";
    }).join("") + "</ol>";
  }
  // só contagem: quantos foram reeleitos e quantos chegam agora (e, desses, quantos têm outro cargo hoje)
  function contaHtml(c, nome) {
    if (!c || !c.total) return "";
    var chegam = c.troca + c.novo, um = c.total === 1;
    var outro = c.troca ? EP.tr(" (" + EP.num(c.troca) + (c.troca === 1 ? " tem" : " deles têm") + " outro cargo eletivo hoje)",
      " (" + EP.num(c.troca) + (c.troca === 1 ? " holds" : " of them hold") + " another elected office today)") : "";
    var txt;
    if (!chegam) txt = EP.tr(um ? "1 eleito, que foi reeleito." : EP.num(c.total) + " eleitos: todos foram reeleitos.", um ? "1 elected, who was re-elected." : EP.num(c.total) + " elected: all were re-elected.");
    else if (!c.reeleicao) txt = EP.tr(um ? "1 eleito, que chega agora" : EP.num(c.total) + " eleitos: todos chegam agora", um ? "1 elected, who is joining now" : EP.num(c.total) + " elected: all are joining now") + outro + ".";
    else txt = EP.tr(EP.num(c.total) + " eleitos. " + EP.num(c.reeleicao) + (c.reeleicao === 1 ? " foi reeleito" : " foram reeleitos") + " e " + EP.num(chegam) + (chegam === 1 ? " chega agora" : " chegam agora"),
      EP.num(c.total) + " elected. " + EP.num(c.reeleicao) + (c.reeleicao === 1 ? " was" : " were") + " re-elected and " + EP.num(chegam) + (chegam === 1 ? " is" : " are") + " joining now") + outro + ".";
    return "<li><b>" + esc(nome) + ":</b> " + esc(txt) + "</li>";
  }
  function contas(lista) {
    var itens = lista.map(function (x) { return contaHtml(x[0], x[1]); }).join("");
    if (!itens) return "";
    return '<div class="contas-e26 rev"><ul>' + itens + '</ul><p class="muted">' + EP.tr(
      "É só uma contagem: voltar ao mesmo cargo ou chegar agora não é bom nem ruim. \"Reeleito\" quer dizer que a pessoa já tem esse cargo hoje; \"chega agora\", que não tem (pode ter outro cargo, ou nenhum).",
      "It is just a count: returning to the same office or joining now is neither good nor bad. \"Re-elected\" means the person already holds that office today; \"joining now\" means they do not (they may hold another office, or none).") + "</p></div>";
  }
  function sub(id, ic, pt, en, nivel) {
    var h = "h" + (nivel || 3);
    return "<" + h + ' class="sub rev" id="' + id + '"><span aria-hidden="true">' + ic + " </span>" + esc(EP.tr(pt, en)) + "</" + h + ">";
  }
  // uma Casa a partir da posse: plenário por partido, filtros e a lista (EP.montaCasa, em js/casa.js)
  function casa(el, membros, o) {
    EP.montaCasa(el, Object.assign({
      membros: membros, nivel: 3, cartao: cartao,
      titPartidos: EP.tr("Quantos de cada partido", "Seats per party"),
      extra: function (m) { return m.extraTxt != null ? m.extraTxt : votos(m.votos, m.votosDaChapa); },
      sabia: function (mu, ho) {
        return EP.en ? "Did you know? There will be <b>" + EP.num(mu) + (mu === 1 ? " woman" : " women") + "</b> and <b>" + EP.num(ho) + (ho === 1 ? " man" : " men") + "</b> in this list." :
          "Você sabia? Nesta lista são <b>" + EP.plural(mu, o.nomes.uma, o.nomes.varias) + "</b> e <b>" + EP.plural(ho, o.nomes.um, o.nomes.varios) + "</b>.";
      }
    }, o));
  }
  function nomes(pt1, pt2, ptv, ptvs, en1, env) { return { um: EP.tr(pt1, en1), uma: EP.tr(pt2, en1), varios: EP.tr(ptv, env), varias: EP.tr(ptvs, env) }; }
  var NOMES = {
    sen: function () { return nomes("senador", "senadora", "senadores", "senadoras", "senator", "senators"); },
    dep: function () { return nomes("deputado", "deputada", "deputados", "deputadas", "deputy", "deputies"); },
    dest: function () { return nomes("deputado estadual", "deputada estadual", "deputados estaduais", "deputadas estaduais", "state deputy", "state deputies"); },
    dist: function () { return nomes("deputado distrital", "deputada distrital", "deputados distritais", "deputadas distritais", "district deputy", "district deputies"); }
  };
  function fontesArquivo(d, extra) {
    var f = d.fontes || {};
    return [f.candidaturas, f.resultados].concat(f.posse || [], extra || []).filter(Boolean);
  }
  function blocoFontes(lista, rotulo) {
    return '<p class="fonte-casa">' + EP.botaoFontes(lista, rotulo || EP.tr("De onde vem isso?", "Where does this come from?")) + "</p>";
  }
  // a seção some sozinha quando não há nada para mostrar (depois das posses, os arquivos deixam de existir)
  function esconde(el) {
    var s = el.closest("section") || el;
    s.hidden = true;
    s.style.display = "none";
    var id = s.id;
    if (id) [].forEach.call(document.querySelectorAll('a[href="#' + id + '"]'), function (a) { a.hidden = true; a.style.display = "none"; });
  }
  function falhou(el) {
    el.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">⚠️</span>' +
      EP.tr("Não foi possível carregar esta parte agora. Tente de novo daqui a pouco.", "Could not load this part right now. Please try again in a little while.") + "</div>";
  }
  function semArquivo(err) { return /^404 /.test((err && err.message) || ""); }
  // ---------------------------------------------------------------- o próximo mandato, no "Ver outro mandato"
  // ui-r9 (decisão do Lucas, 30/10): "Quem assume em 2027" deixou de ser aba. Virou o mandato "2027 a 2030 (eleitos em 2026)"
  // do campo "Ver outro mandato" (js/historico.js), com endereço próprio: brasil.html?mandato=2027, estado.html?uf=SP&mandato=2027.
  // mandatos-r11 (pedido do Lucas, 3/11): a página do mandato 2027 tem o mesmo layout da de hoje (as mesmas abas e partes), com
  // quem foi eleito em 2026; a faixa amarela embaixo das abas diz que é o próximo mandato. Os links antigos (#quem-assume e
  // #qa-...) levam para a aba certa. Nas abas de hoje, um aviso curto com link ("Veja quem assume em 2027"). A opção e os avisos
  // somem sozinhos depois das posses, junto com os arquivos (dados/eleitos/).
  X.FUTURO = "2027";
  function urlFuturo(hash, sem) {
    var u = new URL(location.href);
    if (sem) u.searchParams.delete("mandato"); else u.searchParams.set("mandato", X.FUTURO);
    var q = u.searchParams.toString();
    return (u.pathname.split("/").pop() || "index.html") + (q ? "?" + q : "") + (hash || "");
  }
  X.urlFuturo = function (hash) { return urlFuturo(hash); };
  // os endereços antigos de dentro do "Quem assume" e a aba de cada um (o resto abre a primeira aba)
  var ANTIGOS = /^#(quem-assume|qa-[\w-]+|proximos-(brasil|estado))$/;
  var ABA_ANTIGA = {
    brasil: { "qa-presidente": "executivo", "qa-senado": "senado", "qa-camara": "camara", "qa-casa-sen": "senado", "qa-casa-cam": "camara" },
    estado: { "qa-governo": "governo", "qa-senado": "senadores", "qa-camara": "federais", "qa-assembleia": "estaduais", "qa-casa-fed": "federais", "qa-casa-est": "estaduais" }
  };
  function abaDoAntigo(hash) {
    var t = ABA_ANTIGA[/estado\.html$/.test(location.pathname) ? "estado" : "brasil"][hash.slice(1)];
    return t ? "#" + t : "";
  }
  X.ehFuturo = function () {
    // um link antigo dentro da própria página (#quem-assume) também leva ao mandato 2027
    window.addEventListener("hashchange", function () {
      if (ANTIGOS.test(location.hash)) location.replace(urlFuturo(abaDoAntigo(location.hash)));
    });
    var futuro = EP.param("mandato") === X.FUTURO;
    if ((futuro || !EP.param("mandato")) && ANTIGOS.test(location.hash)) {
      try { history.replaceState(history.state, "", urlFuturo(abaDoAntigo(location.hash))); } catch (e) {}
      return true;
    }
    return futuro;
  };
  function temAlgo(d) { return !!d && !!(d.presidencia || d.senado || d.camara || d.governo || d.assembleia); }
  X.dados = function (arq) { return EP.json("dados/eleitos/" + arq + ".json").then(function (d) { return temAlgo(d) ? d : null; }, function () { return null; }); };
  X.opcaoFutura = function (arq) {
    return X.dados(arq).then(function (d) { return d ? { v: X.FUTURO, t: EP.tr("2027 a 2030 (eleitos em 2026)", "2027–2030 (elected in 2026)") } : null; });
  };
  // o aviso curto nas abas de hoje: lugares = [[parte do arquivo, id da seção, aba da página de 2027], ...]
  X.avisos = function (arq, lugares) {
    X.dados(arq).then(function (d) {
      if (!d) return;
      lugares.forEach(function (l) {
        var s = document.getElementById(l[1]), cab = s && s.querySelector(".cab-bloco");
        if (!d[l[0]] || !cab || s.querySelector(".aviso-futuro")) return;
        cab.insertAdjacentHTML("afterend", '<p class="aviso-futuro"><a href="' + esc(urlFuturo(l[2])) + '"><span aria-hidden="true">📅 </span>' +
          EP.tr("Veja quem assume em 2027", "See who takes office in 2027") + ' <span aria-hidden="true">›</span></a></p>');
      });
    });
  };
  // ---------------------------------------------------------------- peças da página do mandato 2027
  // o mesmo resumo da página de hoje (12 pessoas e "Ver todos")
  function resumoAbas() { return EP.abas && EP.abas.ativa() ? { lote: EP.RESUMO_CASA || 12, verTodos: true } : {}; }
  // o aviso em cima das abas: de onde vêm os dados e, num bloco que abre, quando cada um toma posse
  function notaFuturo(itens) {
    var lt = linhaDoTempo(itens, "qa-posses");
    return '<p class="aviso azul"><span aria-hidden="true">📅 </span>' + esc(EP.tr(
      "Você está vendo o próximo mandato. Aqui aparece quem foi eleito em 2026, segundo o TSE, e quando cada um toma posse. Até a posse, quem está no cargo continua sendo quem aparece na página de hoje. Toque em alguém para ver mais.",
      "You are looking at the next term. This shows who was elected in 2026, according to the TSE, and when each one takes office. Until then, the people in office are still the ones on today's page. Tap anyone to see more.")) + "</p>" +
      (lt ? EP.blocoAbre("posses-abre", '<span aria-hidden="true">📅</span><span id="qa-posses">' + esc(EP.tr("Quando cada um toma posse", "When each one takes office")) + "</span>", lt) : "");
  }
  // uma parte que já tomou posse (os arquivos perdem cada cargo no dia da posse): está na página de hoje
  function jaTomou(ic, pt, en, aba, linkPt, linkEn) {
    return EP.hist.semDados(ic, esc(EP.tr(pt, en)), [EP.hist.link(ic, EP.hist.hojeEm(aba), EP.tr(linkPt, linkEn))]);
  }
  function cabecalho(selo, h1, lead, onde, txtLead) {
    var H = EP.hist;
    H.poeTitulo(EP.tr("Quem assume em 2027 · ", "Who takes office in 2027 · ") + document.title);
    H.poeOnde(onde);
    H.poeTexto(selo, EP.tr("Quem assume em 2027", "Who takes office in 2027"));
    H.poePeriodo(h1, EP.tr("de 2027 a 2030", "2027–2030"));
    H.poeTexto(lead, txtLead);
  }
  function faixaFuturo() { EP.hist.faixa(EP.tr("o próximo mandato, 2027 a 2030 (eleitos em 2026)", "the next term, 2027–2030 (elected in 2026)")); }
  // os ministros do próximo governo: quem nomeia é o presidente, depois da posse (Constituição, art. 84, I)
  function ministrosFuturo(posse) {
    var H = EP.hist, tit = document.getElementById("os-ministros"), desc = tit && tit.nextElementSibling, grade = document.getElementById("ministros");
    H.poeTexto(desc, EP.tr("Ministros não são eleitos: o presidente escolhe cada um para cuidar de uma área, como a saúde ou a educação.",
      "Ministers are not elected: the President chooses each one to take care of an area, such as health or education."));
    if (!grade) return;
    grade.className = "min-futuro";
    grade.innerHTML = H.semDados("👔", esc(EP.tr("Quem nomeia os ministros é o presidente, depois de tomar posse" + (posse ? " (em " + EP.dataLonga(posse) + ")" : "") +
      ". Por isso, os ministros do mandato de 2027 a 2030 não aparecem aqui. Os ministros de hoje estão na página de hoje.",
      "Ministers are appointed by the President after taking office" + (posse ? " (on " + EP.dataLonga(posse) + ")" : "") +
      ". That is why the ministers of the 2027–2030 term are not shown here. Today's ministers are on today's page.")),
    [H.link("👔", H.hojeEm("os-ministros"), EP.tr("Ver os ministros de hoje", "See today's ministers"))]) +
      "<p>" + EP.botaoFontes([fonteCF("art. 84, I (o presidente nomeia os ministros)", "art. 84, I (the President appoints the ministers)")], EP.tr("De onde vem isso?", "Where does this come from?")) + "</p>";
  }

  // ---------------------------------------------------------------- Brasil (brasil.html?mandato=2027)
  // a linha do tempo do Brasil: presidente, governadores, Congresso e as Assembleias (as que tomam posse em outro dia vêm à parte)
  function linhaBrasil(d) {
    var ps = d.posses || {}, a = ps.assembleias || {}, ex = a.excecoes || {}, itens = [];
    var nEx = Object.keys(ex).length;
    if (d.presidencia) itens.push({ data: ps.presidente, txt: esc(EP.tr("presidente e vice-presidente", "the President and the Vice President")) });
    itens.push({ data: ps.governador, txt: esc(EP.tr("governadores e vice-governadores", "governors and vice governors")) });
    var leg = [];
    if (d.senado) leg.push(EP.tr("senadores", "senators"));
    if (d.camara) leg.push(EP.tr("deputados federais", "federal deputies"));
    if (a.padrao === ps.congresso) leg.push(EP.tr("deputados estaduais de " + (27 - nEx) + " estados", "state deputies in " + (27 - nEx) + " states"));
    else if (a.padrao) itens.push({ data: a.padrao, txt: esc(EP.tr("deputados estaduais de " + (27 - nEx) + " estados", "state deputies in " + (27 - nEx) + " states")) });
    if (leg.length) itens.push({ data: ps.congresso, txt: esc(leg.slice(0, -1).join(", ") + (leg.length > 1 ? EP.tr(" e ", " and ") : "") + leg[leg.length - 1]) });
    Object.keys(ex).forEach(function (uf) {
      itens.push({ data: ex[uf], txt: esc(EP.tr("deputados " + (uf === "DF" ? "distritais" : "estaduais") + " " + EP.doEstado(uf), (uf === "DF" ? "district" : "state") + " deputies " + EP.doEstado(uf))) });
    });
    return itens;
  }
  // js/brasil.js já montou as abas de hoje; aqui entram os eleitos de 2026. o.abre(id, fn) = EP.abas.quandoAbrir
  X.brasilAbas = function (o) {
    o = o || {};
    var abre = o.abre || function (id, fn) { fn(); }, H = EP.hist;
    return X.dados("BR").then(function (d) {
      if (!d) { location.replace(urlFuturo("", true)); return; }
      var main = document.getElementById("conteudo"), cab = main.querySelector(".cab-pagina"), c = d.contas || {}, ps = d.posses || {}, pres = d.presidencia;
      cabecalho(cab.querySelector(".selo-topo"), cab.querySelector("h1"), cab.querySelector(".lead"), EP.tr("A política do Brasil (2027 a 2030)", "Brazil's politics (2027–2030)"),
        EP.tr("Aqui você vê quem foi eleito em 2026 para governar o país e fazer as leis de 2027 a 2030, e quando cada um toma posse.",
          "Here you can see who was elected in 2026 to govern the country and make its laws from 2027 to 2030, and when each one takes office."));
      H.nota(notaFuturo(linhaBrasil(d)));
      faixaFuturo();
      // Quem governa
      var posseP = (pres && pres.posse) || ps.presidente;
      H.desc("executivo", EP.tr("O Poder Executivo: o presidente e o vice eleitos em 2026" + (posseP ? ", que tomam posse em " + EP.dataLonga(posseP) : "") + ", e os ministros, que o presidente escolhe.",
        "The executive branch: the President and the Vice President elected in 2026" + (posseP ? ", who take office on " + EP.dataLonga(posseP) : "") + ", and the ministers, whom the President chooses."));
      abre("executivo", function () {
        var topo = document.getElementById("exec-topo");
        if (pres && (pres.presidente || pres.vice)) {
          topo.innerHTML = cartaoGrande(pres.presidente) + cartaoGrande(pres.vice);
          topo.insertAdjacentHTML("afterend", contas([[c.presidencia, EP.tr("Presidente e vice", "President and Vice President")]]) +
            blocoFontes(fontesArquivo(d), EP.tr("De onde vêm estes dados?", "Where does this data come from?")));
        } else {
          topo.innerHTML = jaTomou("🏢", "O presidente e o vice eleitos em 2026 já tomaram posse: eles estão na página de hoje.",
            "The President and the Vice President elected in 2026 have already taken office: they are on today's page.", "executivo", "Ver quem governa hoje", "See who governs today");
        }
        ministrosFuturo(posseP);
        EP.revelar(document.getElementById("executivo"));
      });
      // Senado: os 54 eleitos em 2026 e os 27 que continuam
      var corpoSen = document.querySelector("#senado .casa-corpo"), corpoCam = document.querySelector("#camara .casa-corpo");
      if (corpoSen) corpoSen.id = "qa-casa-sen";
      if (corpoCam) corpoCam.id = "qa-casa-cam";
      if (d.senado) {
        var ne = (d.senado.eleitos || []).length, nc = (d.senado.continuam || []).length;
        var saem = (d.senado.continuam || []).filter(function (m) { return m.eleito2026 && m.assume; });
        H.desc("senado", EP.tr(
          "São 81 senadores, 3 por estado. Em 2026 foram eleitos " + EP.num(ne) + " (2 por estado e 2 pelo Distrito Federal), para 8 anos, e tomam posse em " + EP.dataLonga(d.senado.posse) + ". Os outros " + EP.num(nc) + ", eleitos em 2022, continuam até 2031.",
          "There are 81 senators, 3 per state. In 2026, " + EP.num(ne) + " were elected (2 per state and 2 for the Federal District), for 8-year terms, and take office on " + EP.dataLonga(d.senado.posse) + ". The other " + EP.num(nc) + ", elected in 2022, stay until 2031.") +
          (saem.length ? " " + EP.tr(saem.map(function (m) { return m.nome; }).join(", ") + (saem.length === 1 ? " foi eleito" : " foram eleitos") +
            " para outro cargo em 2026: na posse, " + (saem.length === 1 ? "deixa" : "deixam") + " o Senado, e quem assume é o 1º suplente da chapa (Constituição, art. 56).",
            saem.map(function (m) { return m.nome; }).join(", ") + (saem.length === 1 ? " was" : " were") + " elected to another office in 2026: on taking it, " +
            (saem.length === 1 ? "leaves" : "they leave") + " the Senate, and the seat goes to the 1st alternate on the ticket (Constitution, art. 56).") : ""));
        abre("senado", function () {
          if (!corpoSen) return;
          corpoSen.insertAdjacentHTML("beforebegin", contas([[c.senado, EP.tr("Senado", "Senate")]]));
          senadoBrasil(corpoSen, d.senado, Object.assign({ atualizado: d.atualizado }, resumoAbas()));
        });
      } else if (corpoSen) {
        corpoSen.innerHTML = jaTomou("🏛️", "Os senadores eleitos em 2026 já tomaram posse: eles estão na página de hoje.", "The senators elected in 2026 have already taken office: they are on today's page.",
          "senado", "Ver o Senado de hoje", "See today's Senate");
      }
      // Câmara: os 513 eleitos em 2026
      if (d.camara) {
        H.desc("camara", EP.tr(
          "Os " + EP.num((d.camara.membros || []).length) + " deputados federais eleitos em 2026, com o partido da eleição. Tomam posse em " + EP.dataLonga(d.camara.posse) + ". Quem for eleito e virar ministro ou secretário deixa a vaga para um suplente (Constituição, art. 56).",
          "The " + EP.num((d.camara.membros || []).length) + " federal deputies elected in 2026, with the party they were elected for. They take office on " + EP.dataLonga(d.camara.posse) + ". Anyone elected who becomes a minister or a state secretary leaves the seat to an alternate (Constitution, art. 56)."));
        abre("camara", function () {
          if (!corpoCam) return;
          corpoCam.insertAdjacentHTML("beforebegin", contas([[c.camara, EP.tr("Câmara dos Deputados", "Chamber of Deputies")]]));
          casa(corpoCam, d.camara.membros || [], Object.assign({ nomes: NOMES.dep(), fonte: fontesArquivo(d, [fonteCF("art. 56 (suplentes)", "art. 56 (alternates)")]), atualizado: d.atualizado,
            notaPlenario: EP.tr("O partido é o da eleição de 2026, segundo o TSE.", "The party is the one each person was elected for in 2026, according to the TSE.") }, resumoAbas()));
        });
      } else if (corpoCam) {
        corpoCam.innerHTML = jaTomou("🏛️", "Os deputados federais eleitos em 2026 já tomaram posse: eles estão na página de hoje.", "The federal deputies elected in 2026 have already taken office: they are on today's page.",
          "camara", "Ver a Câmara de hoje", "See today's Chamber");
      }
      EP.revelar(main);
    });
  };
  // o Senado a partir da posse: os 54 eleitos em 2026 e os 27 que continuam até 2031. Quem continua e foi eleito para outro
  // cargo em 2026 deixa o Senado quando toma posse dele (Constituição, art. 54, II, "d"): no lugar, aparece o 1º suplente
  // da chapa de 2022 (art. 56, § 1º), com o partido daquela eleição.
  function suplenteQueAssume(m) {
    return { id: "sup-" + m.id, link: m.assume.tse, nome: m.assume.nome, partido: m.assume.partido, uf: m.uf, genero: m.assume.genero, foto: m.assume.foto,
      extraTxt: EP.tr("1º suplente (partido de 2022)", "1st alternate (2022 party)"),
      chipHtml: chip("🪑", EP.tr("Assume a vaga de " + m.nome, "Takes " + m.nome + "'s seat")) };
  }
  function quemContinua(m) {
    return Object.assign({}, m, { extraTxt: m.eleito2026 ? EP.tr("Eleit" + (m.genero === "F" ? "a " : "o ") + minus(m.eleito2026.cargo) + " em 2026",
      "Elected " + minus(D.cargo(m.eleito2026.cargo)) + " in 2026") : "",
      chipHtml: chip("⏳", EP.tr("Continua até ", "Stays until ") + String(m.fimMandato || "").slice(0, 4)) });
  }
  function senadoBrasil(el, s, extra) {
    var membros = (s.eleitos || []).map(function (m) { return Object.assign({}, m, { extraTxt: votos(m.votos) }); });
    (s.continuam || []).forEach(function (m) { membros.push(m.eleito2026 && m.assume ? suplenteQueAssume(m) : quemContinua(m)); });
    casa(el, membros, Object.assign({ nomes: NOMES.sen(), fonte: s.fontes, coletivo: EP.tr("senadores", "senators"),
      notaPlenario: EP.tr("Partido: o da eleição de 2026 para quem foi eleito agora e o de hoje para quem continua.", "Party: the one from the 2026 election for those elected now, and today's party for those who stay.") }, extra));
  }
  // ---------------------------------------------------------------- estado (estado.html?uf=SP&mandato=2027)
  function suplentesHtml(s) {
    var l = s.suplentes || [];
    if (!l.length) return "";
    return '<p class="suplentes-e26"><small>' + EP.tr("Suplentes (assumem se a vaga ficar aberta): ", "Alternates (they take the seat if it becomes vacant): ") +
      l.map(function (x) {
        return (x.tipo === "supl1" ? "1º " : "2º ").replace("º", EP.en ? (x.tipo === "supl1" ? "st" : "nd") : "º") +
          '<a href="' + urlPerfil(x.link || x.id) + '">' + EP.pt(esc(x.nome)) + "</a> (" + EP.pt(esc(nomePartido(x.partido))) + ")";
      }).join("; ") + "</small></p>";
  }
  // js/estado.js já montou as abas de hoje; aqui entram os eleitos de 2026. o.quando(id, fn) = EP.abas.quandoAbrir
  X.estadoAbas = function (uf, o) {
    o = o || {};
    var quando = o.quando || function (id, fn) { fn(); }, H = EP.hist;
    return X.dados(uf).then(function (d) {
      if (!d) { location.replace(urlFuturo("", true)); return; }
      var c = d.contas || {}, de = EP.doEstado(uf), ehDF = uf === "DF", itens = [], el = document.getElementById("estado");
      var a = d.assembleia, nomeCasa = a ? (EP.en ? a.casa_en || "Legislative Assembly" : a.casa || "Assembleia Legislativa") : "";
      if (d.governo) itens.push({ data: d.governo.posse, txt: esc(EP.tr("governador e vice", "governor and vice governor")) });
      var leg = [];
      if (d.senado) leg.push(EP.tr("senadores", "senators"));
      if (d.camara) leg.push(EP.tr("deputados federais", "federal deputies"));
      if (a && a.posse === (d.senado || d.camara || {}).posse) leg.push(EP.tr("deputados " + (ehDF ? "distritais" : "estaduais"), (ehDF ? "district" : "state") + " deputies"));
      else if (a) itens.push({ data: a.posse, txt: esc(EP.tr("deputados " + (ehDF ? "distritais" : "estaduais"), (ehDF ? "district" : "state") + " deputies")) });
      if (leg.length) itens.push({ data: (d.senado || d.camara).posse, txt: esc(leg.slice(0, -1).join(", ") + (leg.length > 1 ? EP.tr(" e ", " and ") : "") + leg[leg.length - 1]) });
      cabecalho(el.querySelector(".cab-pagina .selo-topo"), document.getElementById("titulo-uf"), document.getElementById("lead-uf"), EP.UFS[uf] + EP.tr(" (2027 a 2030)", " (2027–2030)"),
        EP.tr("Quem foi eleito em 2026 para governar, para representar " + (ehDF ? "o Distrito Federal" : "o estado") + " no Congresso e para fazer as leis " + de + " de 2027 a 2030, e quando cada um toma posse.",
          "Who was elected in 2026 to govern, to represent " + (ehDF ? "the Federal District" : "the state") + " in the National Congress and to make the laws " + de + " from 2027 to 2030, and when each one takes office."));
      H.nota(notaFuturo(itens));
      faixaFuturo();
      var fCF = fonteCF("arts. 27, 28, 46 e 56 (mandatos, suplentes e posse)", "arts. 27, 28, 46 and 56 (terms, alternates and taking office)");
      // Quem governa
      var gov = d.governo, gv = gov && gov.governador, vc = gov && gov.vice;
      if (gv || vc) {
        H.desc("governo", EP.tr("O governador e o vice eleitos em 2026, que tomam posse em " + EP.dataLonga(gov.posse) + ".", "The governor and the vice governor elected in 2026, who take office on " + EP.dataLonga(gov.posse) + "."));
        document.getElementById("gov").innerHTML = cartaoGrande(gv) + cartaoGrande(vc);
        document.getElementById("gov-nota").innerHTML = blocoFontes(fontesArquivo(d, [fCF]), EP.tr("De onde vêm estes dados?", "Where does this data come from?"));
      } else {
        document.getElementById("gov").innerHTML = jaTomou("🏢", "O governador e o vice eleitos em 2026 já tomaram posse: eles estão na página de hoje.",
          "The governor and the vice governor elected in 2026 have already taken office: they are on today's page.", "governo", "Ver quem governa hoje", "See who governs today");
        document.getElementById("gov-nota").innerHTML = "";
      }
      // Senadores: os eleitos em 2026 (com os 2 suplentes) e quem continua, em ordem alfabética, como na página de hoje
      var ls = document.getElementById("lista-sen");
      if (d.senado) {
        var ss = d.senado.eleitos || [], ct = d.senado.continuam || [], fimCt = ct.length ? String(ct[0].fimMandato || "").slice(0, 4) : "";
        H.desc("senadores", EP.tr("Todo estado tem 3 senadores. Em 2026 foram eleitos " + EP.num(ss.length) + ", cada um com 2 suplentes, para o mandato de 8 anos, de " + d.senado.posse.slice(0, 4) + " a " + String(d.senado.fim || "").slice(0, 4) + "." +
          (ct.length ? (ct.length === 1 ? " O outro, eleito em 2022, continua até " : " Os outros, eleitos em 2022, continuam até ") + fimCt + "." : ""),
        "Every state has 3 senators. In 2026, " + EP.num(ss.length) + " were elected, each with 2 alternates, for the 8-year term from " + d.senado.posse.slice(0, 4) + " to " + String(d.senado.fim || "").slice(0, 4) + "." +
          (ct.length ? (ct.length === 1 ? " The other one, elected in 2022, stays until " : " The others, elected in 2022, stay until ") + fimCt + "." : "")));
        var lista = ss.map(function (s) { return { nome: s.nome, html: '<div class="sen-e26">' + cartao(Object.assign({}, s, { uf: "" }), votos(s.votos)) + suplentesHtml(s) + "</div>" }; })
          .concat(ct.map(function (m) {
            var x = m.eleito2026 && m.assume ? suplenteQueAssume(m) : quemContinua(m);
            return { nome: x.nome, html: cartao(Object.assign({}, x, { uf: "" }), x.extraTxt) };
          }));
        ls.innerHTML = EP.alfabetica(lista).map(function (x) { return x.html; }).join("");
        ls.insertAdjacentHTML("afterend", contas([[c.senado, EP.tr("Senado", "Senate")]]) + blocoFontes(d.senado.fontes || fontesArquivo(d, [fCF]), EP.tr("De onde vem esta lista?", "Where does this list come from?")));
      } else {
        ls.innerHTML = jaTomou("🏛️", "Os senadores eleitos em 2026 já tomaram posse: eles estão na página de hoje.", "The senators elected in 2026 have already taken office: they are on today's page.",
          "senadores", "Ver os senadores de hoje", "See today's senators");
      }
      var nota = EP.tr("O partido é o da eleição de 2026, segundo o TSE.", "The party is the one each person was elected for in 2026, according to the TSE.");
      // Deputados federais
      if (d.camara) {
        H.desc("federais", EP.tr("Os " + EP.num((d.camara.membros || []).length) + " deputados federais eleitos " + EP.noEstado(uf) + " em 2026. Eles representam o povo " + de + " na Câmara dos Deputados a partir de " + EP.dataLonga(d.camara.posse) + ".",
          "The " + EP.num((d.camara.membros || []).length) + " federal deputies elected " + EP.noEstado(uf) + " in 2026. They will represent the people " + de + " in the Chamber of Deputies from " + EP.dataLonga(d.camara.posse) + "."));
        quando("federais", function () {
          var el2 = document.getElementById("casa-fed");
          el2.insertAdjacentHTML("beforebegin", contas([[c.camara, EP.tr("Deputados federais", "Federal deputies")]]));
          casa(el2, d.camara.membros || [], Object.assign({ nomes: NOMES.dep(), filtroUF: false, fonte: fontesArquivo(d), atualizado: d.atualizado, notaPlenario: nota }, resumoAbas()));
        });
      } else {
        document.getElementById("casa-fed").innerHTML = jaTomou("🏛️", "Os deputados federais eleitos em 2026 já tomaram posse: eles estão na página de hoje.",
          "The federal deputies elected in 2026 have already taken office: they are on today's page.", "federais", "Ver os deputados federais de hoje", "See today's federal deputies");
      }
      // Deputados estaduais (ou distritais)
      if (a) {
        H.desc("estaduais", EP.tr("Os " + EP.num((a.membros || []).length) + " deputados " + (ehDF ? "distritais" : "estaduais") + " eleitos em 2026, com o partido da eleição. Tomam posse em " + EP.dataLonga(a.posse) + ".",
          "The " + EP.num((a.membros || []).length) + " " + (ehDF ? "district" : "state") + " deputies elected in 2026, with the party they were elected for. They take office on " + EP.dataLonga(a.posse) + "."));
        quando("estaduais", function () {
          var el3 = document.getElementById("casa-est");
          el3.insertAdjacentHTML("beforebegin", contas([[c.assembleia, nomeCasa]]));
          casa(el3, a.membros || [], Object.assign({ nomes: ehDF ? NOMES.dist() : NOMES.dest(), filtroUF: false, fonte: fontesArquivo(d, a.fontePosse ? [a.fontePosse] : []), atualizado: d.atualizado, notaPlenario: nota },
            resumoAbas()));
        });
      } else {
        document.getElementById("casa-est").innerHTML = jaTomou("🏛️", "Os deputados " + (ehDF ? "distritais" : "estaduais") + " eleitos em 2026 já tomaram posse: eles estão na página de hoje.",
          "The " + (ehDF ? "district" : "state") + " deputies elected in 2026 have already taken office: they are on today's page.", "estaduais", "Ver a lista de hoje", "See today's list");
      }
      EP.revelar(el);
    });
  };
  // ---------------------------------------------------------------- página da cidade (#proxima-eleicao)
  var CARGOS_SUP = { prefeito: ["prefeito", "mayor"], vice: ["vice-prefeito", "vice mayor"], vereadores: ["vereadores", "city councilors"] };
  function suplementarHtml(s, nomeCid) {
    var cargos = (s.cargos || []).map(function (k) { return EP.tr((CARGOS_SUP[k] || [k])[0], (CARGOS_SUP[k] || [k, k])[1]); });
    var lista = cargos.slice(0, -1).join(", ") + (cargos.length > 1 ? EP.tr(" e ", " and ") : "") + (cargos[cargos.length - 1] || "");
    var txt;
    if (s.situacao === "marcada") txt = EP.tr("Está marcada uma eleição suplementar em " + nomeCid + " para " + EP.dataLonga(s.data) + ", para escolher " + lista + ".",
      "A special election is scheduled in " + nomeCid + " for " + EP.dataLonga(s.data) + ", to choose the " + lista + ".");
    else if (s.situacao === "sem-resultado") txt = EP.tr("Foi marcada uma eleição suplementar em " + nomeCid + " para " + EP.dataLonga(s.data) + " (" + lista + "), mas o DivulgaCandContas, do TSE, não mostra ninguém eleito nela: ela pode ter sido suspensa ou adiada, ou o resultado pode estar em julgamento.",
      "A special election was scheduled in " + nomeCid + " for " + EP.dataLonga(s.data) + " (" + lista + "), but DivulgaCandContas, a TSE website, shows no one elected in it: it may have been suspended or postponed, or the result may be under review.");
    else txt = EP.tr("Em " + EP.dataLonga(s.data) + ", " + nomeCid + " teve uma eleição suplementar para escolher " + lista + ".",
      "On " + EP.dataLonga(s.data) + ", " + nomeCid + " held a special election to choose the " + lista + ".");
    var el = s.eleitos || {}, quem = [];
    var PARA = { prefeito: ["Para prefeito", "For mayor"], vice: ["Para vice-prefeito", "For vice mayor"], vereadores: ["Para vereador", "For the city council"] };
    ["prefeito", "vice", "vereadores"].forEach(function (k) {
      var l = el[k] || [];
      if (!l.length) return;
      quem.push("<li><b>" + esc(EP.tr(PARA[k][0], PARA[k][1])) + ":</b> " + l.map(function (x) {
        return linkFora(x.tse, EP.pt(esc(x.nome))) + " (" + EP.pt(esc(nomePartido(x.partido))) + ")";
      }).join(", ") + "</li>");
    });
    return '<li class="sup-e26">' + folhinha(s.data) + '<div class="p-txt"><p>' + esc(txt) + "</p>" +
      (quem.length ? "<p><b>" + EP.tr("Quem foi eleito:", "Who was elected:") + '</b></p><ul class="eleitos-sup">' + quem.join("") + "</ul>" : "") +
      (s.fonte ? '<p class="fonte-sup">' + EP.botaoFontes([s.fonte], EP.tr("Fonte", "Source")) + "</p>" : "") + "</div></li>";
  }
  X.cidade = function (el, ibge, uf, nomeCid) {
    if (!el || !ibge) return;
    EP.json("dados/eleitos/municipal.json").then(function (d) {
      var p = d && d.proxima, c = ((d && d.cidades) || {})[ibge] || {};
      if (!p) { esconde(el); return; }
      var h0 = hoje(), passou = p.turno1 <= h0;
      var mand = (p.mandato || []).join(EP.tr(" a ", " to "));
      var h = '<div class="proxima-e26 rev">' + folhinha(p.turno1) + '<div class="p-txt"><p class="grande-e26">' + (passou ?
        esc(EP.tr("A eleição municipal de " + p.ano + " foi em " + EP.dataLonga(p.turno1) + ".", "The " + p.ano + " city election was held on " + EP.dataLonga(p.turno1) + ".")) :
        esc(EP.tr("A próxima eleição em " + nomeCid + " é no domingo, " + EP.dataLonga(p.turno1) + ".", "The next election in " + nomeCid + " is on Sunday, " + EP.dataLonga(p.turno1) + "."))) + "</p>" +
        '<ul class="itens-e26">' +
        "<li><b>" + EP.tr("O que se escolhe:", "What is chosen:") + "</b> " + esc(EP.tr("o prefeito (ou a prefeita), o vice e os vereadores da Câmara Municipal, para o mandato de " + mand + " (4 anos).",
          "the mayor, the vice mayor and the members of the City Council, for the " + mand + " term (4 years).")) + "</li>" +
        "<li><b>" + EP.tr("2º turno:", "Runoff:") + "</b> " + esc(EP.tr("só para prefeito, em " + EP.dataLonga(p.turno2) + ", nas cidades com mais de 200 mil eleitores em que ninguém tiver mais da metade dos votos válidos.",
          "for mayor only, on " + EP.dataLonga(p.turno2) + ", in cities with more than 200,000 voters where no one gets more than half of the valid votes.")) + "</li>" +
        "<li><b>" + EP.tr("Posse:", "Taking office:") + "</b> " + esc(EP.tr(EP.dataLonga(p.posse) + ". Até lá, quem está no cargo continua.", EP.dataLonga(p.posse) + ". Until then, the people in office stay.")) + "</li>" +
        "</ul>" + blocoFontes(p.fontes || [], EP.tr("De onde vem esta data?", "Where does this date come from?")) + "</div></div>";
      var sup = c.suplementares || [];
      if (sup.length) {
        h += sub("pe-sup", "🗳️", "Eleição suplementar", "Special election") +
          '<p class="muted">' + esc(EP.tr("Quando a Justiça Eleitoral anula a eleição de uma cidade (por exemplo, porque quem ganhou teve a candidatura negada), os eleitores votam de novo, fora da data de sempre. Isso se chama eleição suplementar.",
            "When the electoral courts annul a city's election (for example, because the winner's candidacy was rejected), voters vote again, outside the usual date. This is called a special election.")) + "</p>" +
          '<ol class="posses sups-e26" aria-labelledby="pe-sup">' + sup.map(function (s) { return suplementarHtml(s, nomeCid); }).join("") + "</ol>" +
          blocoFontes(d.fontesSuplementares || [], EP.tr("De onde vem isso?", "Where does this come from?"));
      }
      var e26 = c.eleitos2026 || [];
      if (e26.length) {
        h += sub("pe-e26", "📅", "Daqui, eleitos em 2026", "From here, elected in 2026") +
          '<p class="muted">' + esc(EP.tr("Estas pessoas têm (ou tinham) um cargo em " + nomeCid + " e foram eleitas em 2026. Ninguém pode ter dois cargos eletivos ao mesmo tempo: na posse do cargo novo, a pessoa deixa o da cidade, e a vaga de vereador fica com o suplente. Quem é prefeito e concorre a outro cargo deixa a prefeitura 6 meses antes da eleição.",
            "These people hold (or held) an office in " + nomeCid + " and were elected in 2026. No one can hold two elected offices at the same time: on taking the new office, the person leaves the city one, and a city council seat goes to the alternate. A mayor who runs for another office leaves city hall 6 months before the election.")) + "</p>" +
          '<div class="grade-pessoas">' + e26.map(function (m) {
            return cartao(Object.assign({}, m, { chipHtml: chip("🗳️", eleitoEm(m)) }), (m.hoje && m.hoje.cargo ? EP.tr((m.deixou ? "Era " : "Hoje: ") + minus(m.hoje.cargo),
              (m.deixou ? "Was " : "Today: ") + D.cargo(m.hoje.cargo)) + " · " + minus(posseTxt(m.posse)) : posseTxt(m.posse)));
          }).join("") + "</div>" +
          blocoFontes([fonteCF("art. 14, § 6º, art. 27, § 1º, e art. 54, II, \"d\" (um cargo eletivo por vez)", "art. 14, § 6, art. 27, § 1, and art. 54, II, \"d\" (one elected office at a time)")]
            .concat(d.fontesEleitos || []), EP.tr("De onde vem isso?", "Where does this come from?"));
      }
      el.innerHTML = h;
      EP.revelar(el);
    }).catch(function (e) { if (semArquivo(e)) esconde(el); else falhou(el); });
  };
  // ---------------------------------------------------------------- perfil de quem foi eleito e não tem cargo hoje (e26-)
  function fichas(d) {
    var l = [];
    [d.presidencia, d.governo].forEach(function (g) { if (g) ["presidente", "vice", "governador"].forEach(function (k) { if (g[k]) l.push(g[k]); }); });
    ((d.senado || {}).eleitos || []).forEach(function (s) { l.push(s); (s.suplentes || []).forEach(function (x) { l.push(x); }); });
    ["camara", "assembleia"].forEach(function (k) { ((d[k] || {}).membros || []).forEach(function (m) { l.push(m); }); });
    return l;
  }
  function ehSuplente(x) { return x.tipo === "supl1" || x.tipo === "supl2"; }
  // a aba da página do mandato 2027 onde a pessoa aparece (o "Voltar" do perfil e26- leva para lá)
  function abaDoCargo(x) {
    var t = ehSuplente(x) ? "sen" : x.tipo;
    if (x.uf === "BR") return { pres: "executivo", vp: "executivo", sen: "senado", dep: "camara" }[t] || "";
    return { gov: "governo", vgov: "governo", sen: "senadores", dep: "federais", dest: "estaduais" }[t] || "";
  }
  function perfilDe(x, d, l) {
    var f = d.fontes || {}, supl = ehSuplente(x), chapa = !!x.votosDaChapa, a = x.genero === "F" ? "a" : "o";
    var fCand = { veiculo: "TSE", titulo: "DivulgaCandContas: candidatura de " + x.nome + " (2026)", url: x.tse, data: (f.candidaturas || {}).data || d.atualizado };
    var fBens = { veiculo: "TSE", titulo: "DivulgaCandContas: bens declarados por " + x.nome + " (2026)", url: x.tse, data: (f.bens || {}).data || d.atualizado };
    var tit = x.chapa ? l.filter(function (y) { return y.id === x.chapa.id; })[0] || x.chapa : null;
    var txtPt = "Eleit" + a + " " + minus(x.cargo) + " em 2026", txtEn = "Elected " + (CARGO_EN[tipoDe(x)] || "") + " in 2026";
    var cargo = supl ? EP.tr(txtPt + (tit ? " · na chapa de " + tit.nome : ""), txtEn + (tit ? " · on " + tit.nome + "'s ticket" : "")) :
      EP.tr(txtPt + " · toma posse em " + EP.dataLonga(x.posse), txtEn + " · takes office on " + EP.dataLonga(x.posse));
    return {
      id: x.id, tipo: supl ? "supl" : x.tipo, uf: x.uf, nome: x.nome, nomeCivil: x.nomeCivil, genero: x.genero, partido: x.partido, foto: x.foto,
      fotoCredito: "TSE (DivulgaCandContas)", cargo: cargo, nascimento: x.nascimento,
      naturalidade: x.ufNascimento ? EP.UFS[x.ufNascimento] || x.ufNascimento : null,
      escolaridade: x.escolaridade || null, escolaridadeFonte: fCand,
      ocupacao: x.ocupacao ? { txt: x.ocupacao, ano: 2026, fonte: fCand } : null,
      eleicao: { ano: 2026, cargo: x.cargo, votos: x.votos, situacao: x.situacao + (chapa ? " (votos da chapa)" : ""),
        situacao_en: (x.situacao_en || "") + (chapa ? " (votes for the whole ticket)" : ""), fonte: [f.resultados, fCand].filter(Boolean) },
      bens: x.bens ? { ano: 2026, total: x.bens.total, fonte: fBens } : null,
      mandato: supl ? null : { inicio: x.posse, fim: x.fim },
      eleicao2026: { situacao: supl ? "suplente" : "eleito", cargo: x.cargo, txt: txtPt, txt_en: txtEn },
      fontes: [fCand, f.resultados, f.candidaturas, fBens].concat(f.posse || []).filter(Boolean),
      atualizado: d.atualizado,
      volta: { pagina: x.uf === "BR" ? "brasil.html?mandato=" + X.FUTURO : "estado.html?uf=" + x.uf + "&mandato=" + X.FUTURO, secao: abaDoCargo(x), id: x.id },
      e26: { ficha: x, arquivo: d, titular: tit, fBens: fBens }
    };
  }
  // pessoa.js: carregarBase() pede a ficha de um id e26-<UF>-<SQ>
  X.perfil = function (id) {
    var m = /^e26-([A-Z]{2})-\d+$/.exec(id || "");
    if (!m) return Promise.reject(new Error("id inválido"));
    return EP.json("dados/eleitos/" + m[1] + ".json").then(function (d) {
      var l = fichas(d || {}), x = l.filter(function (y) { return y.id === id; })[0];
      if (!x) throw new Error("não achei");
      if (x.link && x.link !== id) {
        // quem já tem cargo hoje tem um perfil só: o de hoje (com o selo de eleito em 2026)
        location.replace(urlPerfil(x.link) + (EP.en ? "&lang=en" : ""));
        return new Promise(function () {});
      }
      return perfilDe(x, d, l);
    });
  };
  function bensHtml(x, d, fonte) {
    var b = x.bens || {}, itens = b.itens || [], tipos = d.tiposBem || {}, n = itens.length, LIM = 12;
    var h = '<section class="secao-perfil" aria-labelledby="t-bens-e26"><h2 id="t-bens-e26"><span class="ic" aria-hidden="true">🏠</span>' +
      EP.tr("O que declarou ter", "What they declared to own") + "</h2>";
    if (!n) h += "<p>" + EP.tr("A lista de bens desta candidatura no TSE está vazia.", "The list of assets for this candidacy at the TSE is empty.") + "</p>";
    else {
      h += "<p>" + esc(EP.tr((n === 1 ? "1 bem" : EP.num(n) + " bens") + ", que somam " + EP.dinheiro(b.total) + ", em ordem de declaração:",
        (n === 1 ? "1 asset" : EP.num(n) + " assets") + ", adding up to " + EP.dinheiro(b.total) + ", in the order they were declared:")) + "</p>" +
        '<ul class="bens-e26" id="bens-e26">' + itens.map(function (it, k) {
          var t = tipos[it[0]] || [EP.tr("Outros bens", "Other assets"), null];
          var nome = EP.en ? (t[1] ? esc(t[1]) : EP.pt(esc(t[0]))) : esc(t[0]);
          return "<li" + (k >= LIM ? " hidden" : "") + ' tabindex="-1"><span class="b-tipo">' + nome + '</span> <span class="b-valor">' + esc(EP.dinheiro(it[1])) + "</span></li>";
        }).join("") + "</ul>" +
        (n > LIM ? '<p><button type="button" class="btn claro peq" data-bens-todos aria-controls="bens-e26">' + EP.tr("Mostrar os outros " + EP.num(n - LIM), "Show the other " + EP.num(n - LIM)) +
          ' <span aria-hidden="true">▾</span></button></p>' : "");
    }
    return h + '<p class="muted">' + EP.tr(
      "Valores que a própria pessoa declarou ao se candidatar. É uma lista de bens: não mostra dívidas nem renda. A descrição de cada bem (como o endereço de um imóvel) fica na página da candidatura, no site do TSE.",
      "Amounts the person declared when running for office. It is a list of assets: it does not show debts or income. The description of each asset (such as a property's address) is on the candidacy page, on the TSE website.") + "</p>" +
      "<p>" + EP.botaoFontes([fonte], EP.tr("Fonte", "Source")) + "</p></section>";
  }
  function federacaoHtml(fd) {
    if (!fd) return "";
    var ps = fd.partidos || [];
    var lista = ps.slice(0, -1).join(", ") + (ps.length > 1 ? EP.tr(" e ", " and ") : "") + (ps[ps.length - 1] || "");
    var fonte = { veiculo: "Planalto", titulo: EP.tr("Lei nº 9.096/1995 (Lei dos Partidos Políticos), art. 11-A", "Law No. 9,096/1995 (Political Parties Law), art. 11-A (in Portuguese)"),
      url: LEI_PARTIDOS, data: "2021-09-29" };
    if (EP.en) fonte.lang = "en";
    return "<p><b>" + EP.tr("Federação:", "Federation:") + "</b> " + EP.pt(esc(fd.nome + (fd.sigla ? " (" + fd.sigla + ")" : ""))) + (lista ? " – " + EP.pt(esc(lista)) : "") + ". " +
      esc(EP.tr("Uma federação junta partidos que atuam como se fossem um só, por pelo menos 4 anos.", "A federation brings parties together to act as if they were one, for at least 4 years.")) +
      " " + EP.botaoFontes([fonte], EP.tr("Fonte", "Source")) + "</p>";
  }
  // pessoa.js: render() junta estas seções ao perfil e26-
  X.perfilHtml = function (p) {
    var e = p.e26 || {}, x = e.ficha || {}, d = e.arquivo || {}, supl = ehSuplente(x), ela = x.genero === "F";
    var quando = (d.turnos || {})[String(x.turno)];
    // "pelo Acre", "pela Bahia", "por Alagoas" (a mesma regra de EP.noEstado)
    var de = x.uf === "BR" ? EP.tr("pelo Brasil", "for Brazil") : EP.tr(EP.noEstado(x.uf).replace(/^no /, "pelo ").replace(/^na /, "pela ").replace(/^em /, "por "),
      "for " + (x.uf === "DF" ? "the " : "") + (EP.UFS[x.uf] || x.uf));
    var txt = supl ?
      EP.tr(x.nome + " foi eleit" + (ela ? "a " : "o ") + minus(x.cargo) + (e.titular ? ", na chapa de " + e.titular.nome : "") + (quando ? ", em " + EP.dataLonga(quando) : "") +
        ". O suplente não toma posse junto com o senador: assume a vaga se o senador sair (para ser ministro, por exemplo) ou se a vaga ficar aberta. Até lá, não tem cargo.",
        x.nome + " was elected " + (CARGO_EN[x.tipo] || "") + (e.titular ? ", on " + e.titular.nome + "'s ticket" : "") + (quando ? ", on " + EP.dataLonga(quando) : "") +
        ". An alternate does not take office with the senator: " + (ela ? "she" : "he") + " takes the seat if the senator leaves (to become a minister, for example) or if the seat becomes vacant. Until then, " + (ela ? "she holds" : "he holds") + " no office.") :
      EP.tr(x.nome + " foi eleit" + (ela ? "a " : "o ") + minus(x.cargo) + " " + de + (quando ? " em " + EP.dataLonga(quando) + (x.turno === 2 ? " (2º turno)" : "") : "") +
        " e toma posse em " + EP.dataLonga(x.posse) + ", para o mandato de " + String(x.posse).slice(0, 4) + " a " + String(x.fim || "").slice(0, 4) +
        ". Até a posse, " + (ela ? "ela" : "ele") + " não tem o cargo: esta página mostra o que " + (ela ? "ela" : "ele") + " declarou ao TSE quando se candidatou. Na posse, " +
        (ela ? "ela" : "ele") + " passa a aparecer na lista de quem está no cargo.",
        x.nome + " was elected " + (CARGO_EN[tipoDe(x)] || "") + " " + de + (quando ? " on " + EP.dataLonga(quando) + (x.turno === 2 ? " (runoff)" : "") : "") +
        " and takes office on " + EP.dataLonga(x.posse) + ", for the " + String(x.posse).slice(0, 4) + "–" + String(x.fim || "").slice(0, 4) + " term. Until then, " +
        (ela ? "she does" : "he does") + " not hold the office: this page shows what " + (ela ? "she" : "he") + " declared to the TSE when running. Once in office, " +
        (ela ? "she" : "he") + " will appear on the list of people in office.");
    var h = '<section class="secao-perfil e26-perfil" aria-labelledby="t-e26"><h2 id="t-e26"><span class="ic" aria-hidden="true">📅</span>' +
      esc(supl ? EP.tr("Eleit" + (ela ? "a" : "o") + " suplente em 2026", "Elected alternate in 2026") : EP.tr("Eleit" + (ela ? "a" : "o") + " em 2026", "Elected in 2026")) + "</h2>" +
      "<p>" + esc(txt) + "</p>" + federacaoHtml(x.federacao) +
      (e.titular && !supl ? "<p>" + EP.tr("Na chapa de ", "On the ticket of ") + '<a href="' + urlPerfil(e.titular.link || e.titular.id) + '">' + EP.pt(esc(e.titular.nome)) + "</a>.</p>" : "") +
      (supl && e.titular ? "<p>" + EP.tr("Senador da chapa: ", "Senator on the ticket: ") + '<a href="' + urlPerfil(e.titular.link || e.titular.id) + '">' + EP.pt(esc(e.titular.nome)) + "</a>.</p>" : "") +
      suplentesHtml(x) +
      '<p class="links-e26">' + linkFora(x.tse, EP.tr("Ver a candidatura no site do TSE (DivulgaCandContas)", "See the candidacy on the TSE website (DivulgaCandContas)")) + "</p>" +
      '<p><a class="link-seta" href="' + (x.uf === "BR" ? "brasil.html?mandato=" + X.FUTURO : "estado.html?uf=" + x.uf + "&mandato=" + X.FUTURO) + (EP.en ? "&lang=en" : "") + '">' +
      EP.tr("Ver todos que assumem " + (x.uf === "BR" ? "no Brasil" : EP.noEstado(x.uf)), "See everyone taking office " + (x.uf === "BR" ? "in Brazil" : EP.noEstado(x.uf))) +
      ' <span aria-hidden="true">›</span></a> ' + EP.botaoFontes([fonteCF(supl ? "arts. 46, § 3º, e 56, § 1º (suplentes)" : "arts. 27, 28, 44, 46 e 82 (mandatos e posse)",
        supl ? "arts. 46, § 3, and 56, § 1 (alternates)" : "arts. 27, 28, 44, 46 and 82 (terms and taking office)")], EP.tr("Fonte", "Source")) + "</p></section>";
    return h + bensHtml(x, d, e.fBens);
  };
  // pessoa.js: endereço e26- que não existe mais (a pessoa já tomou posse) ou errado
  X.semPerfil = function (raiz) {
    raiz.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">📅</span><h1>' + EP.tr("Esta página não está mais aqui", "This page is no longer here") + "</h1><p>" +
      EP.tr("Ela mostrava alguém eleito em 2026, antes da posse. Depois da posse, cada pessoa eleita aparece na lista de quem está no cargo. Procure pelo nome:",
        "It showed someone elected in 2026, before they took office. After taking office, each person appears on the list of people in office. Search by name:") + "</p>" +
      '<p><a class="btn" href="brasil.html#procurar"><span aria-hidden="true">🔎 </span>' + EP.tr("Procurar um político", "Search for a politician") + "</a> " +
      '<a class="btn claro" href="estado.html">' + EP.tr("Ver meu estado", "See the states") + "</a></p></div>";
  };
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest("[data-bens-todos]");
    if (!b) return;
    var novos = document.querySelectorAll("#bens-e26 li[hidden]");
    [].forEach.call(novos, function (li) { li.hidden = false; });
    var p = b.closest("p");
    if (novos[0]) novos[0].focus();
    if (p) p.remove();
  });
})();