/* Quem assume nos próximos mandatos (frente "eleitos 2026"):
   - "Quem assume em 2027" nas páginas do Brasil (#quem-assume) e do estado: quem foi eleito em 2026, a data da posse de cada
     cargo e como ficam o Senado, a Câmara e a Assembleia a partir da posse;
   - "A próxima eleição" na página da cidade: a data, o que se escolhe, a posse e as eleições suplementares;
   - o perfil de quem foi eleito em 2026 e não tem cargo hoje (pessoa.html?id=e26-<UF>-<SQ_CANDIDATO>), que o js/pessoa.js
     monta com EP.eleitos.perfil(id).
   Lê dados/eleitos/BR.json, dados/eleitos/<UF>.json e dados/eleitos/municipal.json (scripts/eleitos.py). Cada cargo sai dos
   arquivos no dia da posse: sem nada a mostrar, a seção some sozinha. */
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
      membros: membros, nivel: 4, cartao: cartao,
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
  // ---------------------------------------------------------------- página do Brasil (#quem-assume)
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
  X.brasil = function (el) {
    if (!el) return;
    EP.json("dados/eleitos/BR.json").then(function (d) {
      if (!d || !(d.presidencia || d.senado || d.camara)) { esconde(el); return; }
      var c = d.contas || {}, pres = d.presidencia;
      var h = '<p class="lead-e26 rev">' + EP.tr(
        "A eleição de 2026 já escolheu quem governa e quem faz as leis nos próximos anos. Até o dia da posse, quem está no cargo continua sendo quem aparece mais acima nesta página. Toque em alguém para ver mais.",
        "The 2026 election has already chosen who will govern and who will make the laws in the coming years. Until the day they take office, the people in office are still the ones shown above on this page. Tap anyone to see more.") + "</p>" +
        sub("qa-posses", "📅", "Quando cada um toma posse", "When each one takes office") + linhaDoTempo(linhaBrasil(d), "qa-posses") +
        sub("qa-contas", "🔢", "Quantos voltam e quantos chegam", "How many return and how many are joining") +
        contas([[c.presidencia, EP.tr("Presidente e vice", "President and Vice President")], [c.governadores, EP.tr("Governadores", "Governors")],
          [c.senado, EP.tr("Senado", "Senate")], [c.camara, EP.tr("Câmara dos Deputados", "Chamber of Deputies")],
          [c.assembleias, EP.tr("Assembleias Legislativas e Câmara Legislativa do DF", "State legislatures and the Federal District's Legislative Chamber")]]);
      if (pres && (pres.presidente || pres.vice)) {
        h += sub("qa-presidente", "🏢", "Presidente e vice eleitos", "President-elect and Vice President-elect") +
          '<div class="exec-topo">' + cartaoGrande(pres.presidente) + cartaoGrande(pres.vice) + "</div>";
      }
      if (d.senado) {
        var ne = (d.senado.eleitos || []).length, nc = (d.senado.continuam || []).length;
        var saem = (d.senado.continuam || []).filter(function (m) { return m.eleito2026 && m.assume; });
        h += sub("qa-senado", "🏛️", "O Senado a partir de " + EP.dataLonga(d.senado.posse), "The Senate from " + EP.dataLonga(d.senado.posse)) +
          '<p class="muted">' + esc(EP.tr(
            "São 81 senadores, 3 por estado. Em 2026 foram eleitos " + EP.num(ne) + " (2 por estado e 2 pelo Distrito Federal), para 8 anos. Os outros " + EP.num(nc) + ", eleitos em 2022, continuam até 2031.",
            "There are 81 senators, 3 per state. In 2026, " + EP.num(ne) + " were elected (2 per state and 2 for the Federal District), for 8-year terms. The other " + EP.num(nc) + ", elected in 2022, stay until 2031.")) +
          (saem.length ? " " + esc(EP.tr(saem.map(function (m) { return m.nome; }).join(", ") + (saem.length === 1 ? " foi eleito" : " foram eleitos") +
            " para outro cargo em 2026: na posse, " + (saem.length === 1 ? "deixa" : "deixam") + " o Senado, e quem assume é o 1º suplente da chapa (Constituição, art. 56).",
            saem.map(function (m) { return m.nome; }).join(", ") + (saem.length === 1 ? " was" : " were") + " elected to another office in 2026: on taking it, " +
            (saem.length === 1 ? "leaves" : "they leave") + " the Senate, and the seat goes to the 1st alternate on the ticket (Constitution, art. 56).")) : "") + "</p>" +
          '<div class="casa-corpo" id="qa-casa-sen"></div>';
      }
      if (d.camara) {
        h += sub("qa-camara", "🏛️", "A Câmara dos Deputados a partir de " + EP.dataLonga(d.camara.posse), "The Chamber of Deputies from " + EP.dataLonga(d.camara.posse)) +
          '<p class="muted">' + esc(EP.tr(
            "Os " + EP.num((d.camara.membros || []).length) + " deputados federais eleitos em 2026, com o partido da eleição. Quem for eleito e virar ministro ou secretário deixa a vaga para um suplente (Constituição, art. 56).",
            "The " + EP.num((d.camara.membros || []).length) + " federal deputies elected in 2026, with the party they were elected for. Anyone elected who becomes a minister or a state secretary leaves the seat to an alternate (Constitution, art. 56).")) + "</p>" +
          '<div class="casa-corpo" id="qa-casa-cam"></div>';
      }
      h += blocoFontes(fontesArquivo(d, [fonteCF("art. 56 (suplentes)", "art. 56 (alternates)")]), EP.tr("De onde vêm estes dados?", "Where does this data come from?"));
      el.innerHTML = h;
      if (d.senado) senadoBrasil(document.getElementById("qa-casa-sen"), d.senado);
      if (d.camara) casa(document.getElementById("qa-casa-cam"), d.camara.membros || [], { nomes: NOMES.dep(), fonte: fontesArquivo(d), atualizado: d.atualizado,
        notaPlenario: EP.tr("O partido é o da eleição de 2026, segundo o TSE.", "The party is the one each person was elected for in 2026, according to the TSE.") });
      EP.revelar(el);
    }).catch(function (e) { if (semArquivo(e)) esconde(el); else falhou(el); });
  };
  // o Senado a partir da posse: os 54 eleitos em 2026 e os 27 que continuam até 2031. Quem continua e foi eleito para outro
  // cargo em 2026 deixa o Senado quando toma posse dele (Constituição, art. 54, II, "d"): no lugar, aparece o 1º suplente
  // da chapa de 2022 (art. 56, § 1º), com o partido daquela eleição.
  function senadoBrasil(el, s) {
    var membros = (s.eleitos || []).map(function (m) { return Object.assign({}, m, { extraTxt: votos(m.votos) }); });
    (s.continuam || []).forEach(function (m) {
      if (m.eleito2026 && m.assume) {
        membros.push({ id: "sup-" + m.id, link: m.assume.tse, nome: m.assume.nome, partido: m.assume.partido, uf: m.uf, genero: m.assume.genero, foto: m.assume.foto,
          extraTxt: EP.tr("1º suplente (partido de 2022)", "1st alternate (2022 party)"),
          chipHtml: chip("🪑", EP.tr("Assume a vaga de " + m.nome, "Takes " + m.nome + "'s seat")) });
      } else {
        membros.push(Object.assign({}, m, { extraTxt: m.eleito2026 ? EP.tr("Eleit" + (m.genero === "F" ? "a " : "o ") + minus(m.eleito2026.cargo) + " em 2026",
          "Elected " + minus(D.cargo(m.eleito2026.cargo)) + " in 2026") : "",
          chipHtml: chip("⏳", EP.tr("Continua até ", "Stays until ") + String(m.fimMandato || "").slice(0, 4)) }));
      }
    });
    casa(el, membros, { nomes: NOMES.sen(), fonte: s.fontes, coletivo: EP.tr("senadores", "senators"),
      notaPlenario: EP.tr("Partido: o da eleição de 2026 para quem foi eleito agora e o de hoje para quem continua.", "Party: the one from the 2026 election for those elected now, and today's party for those who stay.") });
  }
  // ---------------------------------------------------------------- página do estado (#quem-assume)
  function suplentesHtml(s) {
    var l = s.suplentes || [];
    if (!l.length) return "";
    return '<p class="suplentes-e26"><small>' + EP.tr("Suplentes (assumem se a vaga ficar aberta): ", "Alternates (they take the seat if it becomes vacant): ") +
      l.map(function (x) {
        return (x.tipo === "supl1" ? "1º " : "2º ").replace("º", EP.en ? (x.tipo === "supl1" ? "st" : "nd") : "º") +
          '<a href="' + urlPerfil(x.link || x.id) + '">' + EP.pt(esc(x.nome)) + "</a> (" + EP.pt(esc(nomePartido(x.partido))) + ")";
      }).join("; ") + "</small></p>";
  }
  X.estado = function (el, uf) {
    if (!el || !uf) return;
    EP.json("dados/eleitos/" + uf + ".json").then(function (d) {
      if (!d || !(d.governo || d.senado || d.camara || d.assembleia)) { esconde(el); return; }
      var c = d.contas || {}, de = EP.doEstado(uf), ehDF = uf === "DF", itens = [];
      var a = d.assembleia, nomeCasa = a ? (EP.en ? esc(a.casa_en || "Legislative Assembly") : esc(a.casa || "Assembleia Legislativa")) : "";
      if (d.governo) itens.push({ data: d.governo.posse, txt: esc(EP.tr("governador e vice", "governor and vice governor")) });
      var leg = [];
      if (d.senado) leg.push(EP.tr("senadores", "senators"));
      if (d.camara) leg.push(EP.tr("deputados federais", "federal deputies"));
      if (a && a.posse === (d.senado || d.camara || {}).posse) leg.push(EP.tr("deputados " + (ehDF ? "distritais" : "estaduais"), (ehDF ? "district" : "state") + " deputies"));
      else if (a) itens.push({ data: a.posse, txt: esc(EP.tr("deputados " + (ehDF ? "distritais" : "estaduais"), (ehDF ? "district" : "state") + " deputies")) });
      if (leg.length) itens.push({ data: (d.senado || d.camara).posse, txt: esc(leg.slice(0, -1).join(", ") + (leg.length > 1 ? EP.tr(" e ", " and ") : "") + leg[leg.length - 1]) });
      var h = '<p class="lead-e26 rev">' + esc(EP.tr(
        "Até a posse, quem está no cargo continua sendo quem aparece mais acima nesta página. Toque em alguém para ver mais.",
        "Until they take office, the people in office are still the ones shown above on this page. Tap anyone to see more.")) + "</p>" +
        sub("qa-posses", "📅", "Quando cada um toma posse", "When each one takes office") + linhaDoTempo(itens, "qa-posses") +
        sub("qa-contas", "🔢", "Quantos voltam e quantos chegam", "How many return and how many are joining") +
        contas([[c.senado, EP.tr("Senado", "Senate")], [c.camara, EP.tr("Deputados federais", "Federal deputies")],
          [c.assembleia, a ? (EP.en ? a.casa_en || "Legislative Assembly" : a.casa || "Assembleia Legislativa") : ""]]);
      if (d.governo && (d.governo.governador || d.governo.vice)) {
        var gv = d.governo.governador, vc = d.governo.vice;
        h += sub("qa-governo", "🏢", "Governador e vice eleitos", "Governor-elect and vice governor-elect") +
          '<div class="exec-topo">' + cartaoGrande(gv) + cartaoGrande(vc) + "</div>";
      }
      if (d.senado) {
        var ss = d.senado.eleitos || [], ct = d.senado.continuam || [];
        h += sub("qa-senado", "🏛️", "Senadores eleitos", "Senators-elect") +
          '<p class="muted">' + esc(EP.tr("Mandato de 8 anos, de " + d.senado.posse.slice(0, 4) + " a " + String(d.senado.fim || "").slice(0, 4) + ". Cada senador foi eleito com 2 suplentes.",
            "8-year term, from " + d.senado.posse.slice(0, 4) + " to " + String(d.senado.fim || "").slice(0, 4) + ". Each senator was elected with 2 alternates.")) + "</p>" +
          '<div class="grade-senado-e26">' + ss.map(function (s) {
            return '<div class="sen-e26">' + cartao(Object.assign({}, s, { uf: "" }), votos(s.votos)) + suplentesHtml(s) + "</div>";
          }).join("") + "</div>" +
          (ct.length ? '<p class="muted continua-e26">' + ct.map(function (m) {
            var sai = m.eleito2026 && m.assume;
            return EP.tr("Continua até " + String(m.fimMandato || "").slice(0, 4) + ": ", "Stays until " + String(m.fimMandato || "").slice(0, 4) + ": ") +
              '<a href="' + urlPerfil(m.link || m.id) + '">' + EP.pt(esc(m.nome)) + "</a> (" + EP.pt(esc(nomePartido(m.partido))) + ")" +
              (sai ? esc(EP.tr(", eleit" + (m.genero === "F" ? "a " : "o ") + minus(m.eleito2026.cargo) + " em 2026: na posse, deixa o Senado e quem assume é o 1º suplente, ",
                ", elected " + minus(D.cargo(m.eleito2026.cargo)) + " in 2026: on taking office, " + (m.genero === "F" ? "she" : "he") + " leaves the Senate and the seat goes to the 1st alternate, ")) +
                linkFora(m.assume.tse, EP.pt(esc(m.assume.nome))) + " (" + EP.pt(esc(nomePartido(m.assume.partido))) + EP.tr(" em 2022", " in 2022") + ")" : "") + ".";
          }).join(" ") + "</p>" : "");
      }
      if (d.camara) {
        h += sub("qa-camara", "🏛️", "Deputados federais eleitos " + de, "Federal deputies elected " + EP.tr(de, "for " + (ehDF ? "the Federal District" : EP.UFS[uf]))) +
          '<p class="muted">' + esc(EP.tr("Eles representam o povo " + de + " na Câmara dos Deputados a partir de " + EP.dataLonga(d.camara.posse) + ".",
            "They will represent the people " + de + " in the Chamber of Deputies from " + EP.dataLonga(d.camara.posse) + ".")) + "</p>" +
          '<div class="casa-corpo" id="qa-casa-fed"></div>';
      }
      if (a) {
        h += "<h3 class=\"sub rev\" id=\"qa-assembleia\"><span aria-hidden=\"true\">🏛️ </span>" + (EP.en ? "The " : "A ") + (EP.en ? nomeCasa : EP.pt(nomeCasa)) + EP.tr(" a partir de ", " from ") + esc(EP.dataLonga(a.posse)) + "</h3>" +
          '<p class="muted">' + esc(EP.tr("Os " + EP.num((a.membros || []).length) + " deputados " + (ehDF ? "distritais" : "estaduais") + " eleitos em 2026, com o partido da eleição.",
            "The " + EP.num((a.membros || []).length) + " " + (ehDF ? "district" : "state") + " deputies elected in 2026, with the party they were elected for.")) + "</p>" +
          '<div class="casa-corpo" id="qa-casa-est"></div>';
      }
      h += blocoFontes(fontesArquivo(d, [fonteCF("arts. 27, 28, 46 e 56 (mandatos, suplentes e posse)", "arts. 27, 28, 46 and 56 (terms, alternates and taking office)")]
        .concat(a && a.fontePosse ? [a.fontePosse] : [])),
        EP.tr("De onde vêm estes dados?", "Where does this data come from?"));
      el.innerHTML = h;
      var nota = EP.tr("O partido é o da eleição de 2026, segundo o TSE.", "The party is the one each person was elected for in 2026, according to the TSE.");
      if (d.camara) casa(document.getElementById("qa-casa-fed"), d.camara.membros || [], { nomes: NOMES.dep(), filtroUF: false, fonte: fontesArquivo(d), atualizado: d.atualizado, notaPlenario: nota });
      if (a) casa(document.getElementById("qa-casa-est"), a.membros || [], { nomes: ehDF ? NOMES.dist() : NOMES.dest(), filtroUF: false, fonte: fontesArquivo(d), atualizado: d.atualizado, notaPlenario: nota });
      EP.revelar(el);
    }).catch(function (e) { if (semArquivo(e)) esconde(el); else falhou(el); });
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
      volta: { pagina: x.uf === "BR" ? "brasil.html" : "estado.html?uf=" + x.uf, secao: "quem-assume", id: x.id },
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
      '<p><a class="link-seta" href="' + (x.uf === "BR" ? "brasil.html" : "estado.html?uf=" + x.uf) + '#quem-assume">' +
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