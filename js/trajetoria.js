/* ====== Trajetória (frente trajetoria-r9): a história de cada pessoa na política ======
   Todas as candidaturas no TSE desde 1994 (ganhou, perdeu, suplente), com o resultado de cada uma, os mandatos exercidos
   (Câmara e Senado: também o que a pessoa propôs em cada mandato) e, para quem está no cargo, o mandato de hoje.
   Dados: dados/trajetoria/<balde>.json, feitos por scripts/trajetoria.py (o balde sai do id, com a mesma conta do script).

   Uso (uma linha no perfil): EP.trajetoria(elemento, pessoa) — monta a seção dentro do elemento (um <section> vazio) e
   devolve uma promessa. Sem dados para a pessoa, o elemento fica vazio e escondido. Não pede nada a outro servidor. */
(function () {
  "use strict";
  var EP = window.EP;
  if (!EP) return;
  var N_BALDES = 256;
  var esc = EP.esc, tr = EP.tr;

  // a mesma conta do scripts/trajetoria.py (FNV-1a de 32 bits; os ids só têm letras, números, "-" e ":")
  function balde(id, n) {
    var h = 0x811c9dc5;
    for (var i = 0; i < id.length; i++) { h ^= id.charCodeAt(i) & 0xff; h = Math.imul(h, 0x01000193) >>> 0; }
    return ("0" + (h % (n || N_BALDES)).toString(16)).slice(-2);
  }

  // ---------------------------------------------------------------- textos
  var NIVEL = { pres: "pais", vp: "pais", sen: "pais", s1: "pais", s2: "pais", dep: "pais", gov: "estado", vgov: "estado",
    dest: "estado", ddist: "estado", pref: "cidade", vpref: "cidade", ver: "cidade" };
  var IC_NIVEL = { pais: "🏛️", estado: "🗺️", cidade: "🏘️" };
  function cargoTxt(c, g, en) {
    var m = {
      pres: ["Presidente", "Presidente", "President"], vp: ["Vice-presidente", "Vice-presidente", "Vice President"],
      gov: ["Governador", "Governadora", "Governor"], vgov: ["Vice-governador", "Vice-governadora", "Vice Governor"],
      sen: ["Senador", "Senadora", "Senator"], s1: ["1º suplente de senador", "1ª suplente de senador", "1st alternate senator"],
      s2: ["2º suplente de senador", "2ª suplente de senador", "2nd alternate senator"],
      dep: ["Deputado federal", "Deputada federal", "Federal Deputy"], dest: ["Deputado estadual", "Deputada estadual", "State Deputy"],
      ddist: ["Deputado distrital", "Deputada distrital", "District Deputy"], pref: ["Prefeito", "Prefeita", "Mayor"],
      vpref: ["Vice-prefeito", "Vice-prefeita", "Vice Mayor"], ver: ["Vereador", "Vereadora", "City Councilor"],
      stf: ["Ministro do STF", "Ministra do STF", "Supreme Court Justice"], min: ["Ministro", "Ministra", "Minister"]
    }[c] || [c, c, c];
    return en ? m[2] : (g === "F" ? m[1] : m[0]);
  }
  var REGIAO = {};
  [["NORTE", "AC AM AP PA RO RR TO"], ["NORDESTE", "AL BA CE MA PB PE PI RN SE"], ["CENTROOESTE", "DF GO MS MT"], ["SUDESTE", "ES MG RJ SP"], ["SUL", "PR RS SC"]]
    .forEach(function (x) { x[1].split(" ").forEach(function (uf) { REGIAO[uf] = x[0]; }); });

  function eleito(r) { return r === "e" || r === "eqp" || r === "emed"; }
  // o resultado, em palavras simples (mesma régua para todos; palavras neutras)
  function resultadoTxt(it, g) {
    var a = g === "F" ? "a" : "o";
    var ch = it.ch && it.ch.n ? it.ch.n : null;
    var vice = /^(vp|vgov|vpref|s1|s2)$/.test(it.c);
    var r = it.r, t2 = it.t === 2;
    if (vice && ch && (r === "e" || r === "ne" || r === "2t")) {
      if (r === "e") return [tr("Eleit" + a + " na chapa de ", "Elected on ") + "<span" + (EP.en ? ' lang="pt-BR"' : "") + ">" + esc(ch) + "</span>" + tr("", "'s ticket"), "e"];
      if (r === "2t") return [tr("A chapa de ", "") + EP.pt(esc(ch)) + tr(" foi ao 2º turno", "'s ticket went to the runoff"), "2t"];
      return [tr("A chapa de ", "") + EP.pt(esc(ch)) + tr(" não foi eleita", "'s ticket was not elected"), "ne"];
    }
    var T = {
      e: t2 ? tr("Eleit" + a + " no 2º turno", "Elected in the runoff") : tr("Eleit" + a, "Elected"),
      eqp: tr("Eleit" + a, "Elected"), emed: tr("Eleit" + a, "Elected"),
      "2t": tr("Foi ao 2º turno", "Went to the runoff"),
      sup: tr("Suplente", "Alternate"),
      ne: t2 ? tr("Não eleit" + a + " no 2º turno", "Not elected in the runoff") : tr("Não eleit" + a, "Not elected"),
      neg: tr("A Justiça Eleitoral não aceitou a candidatura", "The electoral courts did not accept the candidacy"),
      nega: tr("A Justiça Eleitoral negou a candidatura depois da eleição", "The electoral courts denied the candidacy after the election"),
      ren: tr("A candidatura acabou antes da eleição", "The candidacy ended before the election"),
      rena: tr("A candidatura acabou depois da eleição", "The candidacy ended after the election"),
      sub: tr("Foi trocad" + a + " por outra pessoa antes da eleição", "Was replaced by another candidate before the election"),
      cas: tr("A candidatura foi cassada", "The candidacy was revoked"),
      inapto: tr("A candidatura não valeu", "The candidacy was not valid"),
      sr: tr("O TSE não publica o resultado desta candidatura", "The TSE does not publish the result of this candidacy"),
      sv: tr("O TSE não registra o resultado do vice nesta eleição", "The TSE does not record the running mate's result in this election")
    };
    return [T[r] || T.sr, eleito(r) ? "e" : r === "2t" ? "2t" : r === "sup" ? "sup" : "outro"];
  }
  function explicaResultado(it) {
    return {
      eqp: tr("Pelas vagas que os votos do partido garantiram (quociente partidário).", "Through the seats the party's votes secured (party quota)."),
      emed: tr("Numa das vagas que sobraram, que vão para os partidos com as maiores médias de votos.", "In one of the leftover seats, which go to the parties with the highest vote averages."),
      sup: tr("Ficou na fila: pode assumir se uma vaga abrir.", "Next in line: can take office if a seat opens up."),
      ren: tr("O TSE registra renúncia, morte ou cassação, sem dizer qual.", "The TSE records withdrawal, death or removal, without saying which."),
      rena: tr("O TSE registra renúncia, morte ou cassação, sem dizer qual.", "The TSE records withdrawal, death or removal, without saying which."),
      inapto: tr("O TSE marca a candidatura como “inapta”: o registro foi negado, cancelado ou retirado.", "The TSE marks the candidacy as “inapt”: the registration was denied, canceled or withdrawn.")
    }[it.r] || "";
  }

  function lugarHtml(it, d) {
    if (it.c === "pres" || it.c === "vp") return esc(tr("Brasil", "Brazil"));
    if (it.ue && d.ues && d.ues[it.ue]) {
      var c = d.ues[it.ue];
      return EP.pt(esc(c[1])) + " (" + esc(c[2]) + ")";
    }
    if (it.cid && d.cidade) return EP.pt(esc(d.cidade)) + (it.uf ? " (" + esc(it.uf) + ")" : "");
    return esc(EP.UFS[it.uf] || it.uf || "");
  }
  function linkCidade(it, d) {
    var c = it.ue && d.ues && d.ues[it.ue];
    return c && c[0] ? "cidade.html?ibge=" + encodeURIComponent(c[0]) + (EP.en ? "&lang=en" : "") : null;
  }

  // ---------------------------------------------------------------- fontes (montadas a partir do item)
  var PORTAL = "https://dadosabertos.tse.jus.br/dataset/";
  var DIVULGA = "https://divulgacandcontas.tse.jus.br/divulga/#/candidato/";
  function fontesItem(it, d, p) {
    var f = [], ds = it.ds || (it.a % 2 ? it.a - 1 : it.a), cab = (d.tse || {})[ds] || {};
    if (it.k === "c") {
      f.push({ veiculo: "TSE", titulo: "Dados Abertos: candidaturas de " + ds, url: PORTAL + "candidatos-" + ds, data: cab.data });
      if (it.v != null || (it.ch && it.ch.v != null)) f.push({ veiculo: "TSE", titulo: "Dados Abertos: resultados de " + ds + " (votação nominal por município e zona)", url: PORTAL + "resultados-" + ds, data: cab.data });
      if (it.sq && cab.divulga) {
        var ue = it.ue || (it.c === "pres" || it.c === "vp" ? "BR" : it.uf), uf = it.c === "pres" || it.c === "vp" ? "BR" : it.uf;
        f.push({ veiculo: "TSE", titulo: "DivulgaCandContas: candidatura de " + (it.n || p.nome) + " (" + it.a + ")",
          url: DIVULGA + (uf === "BR" ? "BR" : REGIAO[uf]) + "/" + uf + "/" + cab.divulga + "/" + it.sq + "/" + ds + "/" + ue, data: cab.data });
      }
    }
    (it.fontes || []).forEach(function (x) { f.push(x); });
    if (it.m) f = f.concat(fontesMandato(it.m, it.uf));
    return f;
  }
  function fontesMandato(m, uf) {
    if (m.casa === "camara") {
      return [{ veiculo: "Câmara dos Deputados", titulo: "Dados Abertos: deputados da " + m.leg + "ª legislatura", url: "https://dadosabertos.camara.leg.br/api/v2/deputados?idLegislatura=" + m.leg + "&itens=100" },
        { veiculo: "Câmara dos Deputados", titulo: "Dados Abertos: proposições e autores (arquivos anuais, 1987 em diante)", url: "https://dadosabertos.camara.leg.br/swagger/api.html#staticfile" },
        { veiculo: "Câmara dos Deputados", titulo: "Página do(a) deputado(a) na Câmara", url: "https://www.camara.leg.br/deputados/" + m.id }];
    }
    if (m.casa === "senado") {
      return [{ veiculo: "Senado Federal", titulo: "Dados Abertos: mandatos do(a) senador(a)", url: "https://legis.senado.leg.br/dadosabertos/senador/" + m.id + "/mandatos.json" },
        { veiculo: "Senado Federal", titulo: "Dados Abertos: processos de autoria do(a) senador(a)", url: "https://legis.senado.leg.br/dadosabertos/processo.json?codigoParlamentarAutor=" + m.id },
        { veiculo: "Senado Federal", titulo: "Página do(a) senador(a) no Senado", url: "https://www25.senado.leg.br/web/senadores/senador/-/perfil/" + m.id }];
    }
    return [];
  }

  // ---------------------------------------------------------------- "o que fez nesse mandato"
  function periodoTxt(m) {
    var i = m.i, f = m.f;
    if (m.dl) return tr("na legislatura de " + i.slice(0, 4) + " a " + (f || "").slice(0, 4), "in the " + i.slice(0, 4) + "–" + (f || "").slice(0, 4) + " legislature");
    if (!f) return tr("desde " + EP.data(i), "since " + EP.data(i));
    return tr("de " + EP.data(i) + " a " + EP.data(f), "from " + EP.data(i) + " to " + EP.data(f));
  }
  function fezMandato(m, p, it) {
    var casa = m.casa === "camara" ? tr("na Câmara", "in the Chamber of Deputies") : tr("no Senado", "in the Senate");
    var z = m.fez || {}, h = "";
    if (!m.fez) h += "<p>" + tr("O que foi proposto nesse mandato está na página oficial.", "What was proposed in this term is on the official page.") + "</p>";
    else if (!z.prop) h += "<p>" + tr("Não apresentou propostas " + casa + " nesse período, segundo os dados abertos.", "Did not file any bills " + casa + " in this period, according to the open data.") + "</p>";
    else {
      h += "<p>" + tr("Apresentou ou assinou junto <b>" + EP.num(z.prop) + "</b> " + (z.prop === 1 ? "proposta" : "propostas") + " " + casa,
        "Filed or co-signed <b>" + EP.num(z.prop) + "</b> " + (z.prop === 1 ? "bill" : "bills") + " " + casa) +
        (m.casa === "camara" && z.autor != null ? tr(" (" + EP.num(z.autor) + " como autor" + (p.genero === "F" ? "a" : "") + " principal)", " (" + EP.num(z.autor) + " as lead author)") : "") +
        tr("; <b>" + EP.num(z.lei) + "</b> " + (z.lei === 1 ? "virou lei" : "viraram lei") + ".", "; <b>" + EP.num(z.lei) + "</b> became law.") + "</p>";
      h += '<p class="muted traj-contexto">' + tr("Propor muitas ou poucas propostas não quer dizer trabalhar mais ou menos: é só uma contagem.", "Filing many or few bills does not mean working more or less: it is just a count.") + "</p>";
    }
    var links = [];
    if (it.hoje && p.propostas && document.getElementById("propostas")) links.push('<a class="link-seta" href="#propostas">' + tr("Ver a lista na parte “O que propôs”", "See the list in “Proposals”") + ' <span aria-hidden="true">›</span></a>');
    if (it.hoje && p.votacoes && p.votacoes.resumo && p.votacoes.resumo.total) {
      h += "<p>" + tr("Neste mandato, registrou voto em <b>" + EP.num(p.votacoes.resumo.total) + "</b> votações nominais.", "In this term, cast a recorded vote in <b>" + EP.num(p.votacoes.resumo.total) + "</b> roll-call votes.") + "</p>";
      if (document.getElementById("votacoes")) links.push('<a class="link-seta" href="#votacoes">' + tr("Ver como votou", "See how they voted") + ' <span aria-hidden="true">›</span></a>');
    }
    var url = m.casa === "camara" ? "https://www.camara.leg.br/deputados/" + m.id : "https://www25.senado.leg.br/web/senadores/senador/-/perfil/" + m.id;
    links.push('<a class="link-seta" href="' + esc(url) + '" target="_blank" rel="noopener"' + (EP.en ? ' hreflang="pt-BR"' : "") + ">" +
      (m.casa === "camara" ? tr("Página na Câmara", "Page at the Chamber") : tr("Página no Senado", "Page at the Senate")) + ' <span aria-hidden="true">↗</span><span class="sr">' + tr("(abre em outra aba)", "(opens in a new tab)") + "</span></a>");
    return h + '<p class="traj-links">' + links.join(" ") + "</p>";
  }
  // sem dados da Câmara ou do Senado: o mandato de hoje (o que o perfil já mostra) ou o que o site não tem
  function fezSemCasa(it, p) {
    var g = p.genero, h = "", links = [];
    var vice = /^(vp|vgov|vpref|s1|s2)$/.test(it.c);
    if (vice) return "<p>" + tr("Quem é vice (ou suplente de senador) não apresenta projetos como titular: substitui o titular quando ele se afasta.",
      "A vice (or an alternate senator) does not file bills as the office holder: they replace the office holder when needed.") + "</p>";
    if (it.hoje) {
      var r = p.propostas && p.propostas.resumo;
      var exec = /^(pres|vp|gov|vgov|pref|vpref)$/.test(p.tipo);
      if (r && r.total && exec) {
        h += "<p>" + tr("Neste mandato, o governo mandou <b>" + EP.num(r.total) + "</b> " + (r.total === 1 ? "proposta" : "propostas") + " ao Legislativo; <b>" + EP.num(r.lei || 0) + "</b> " + ((r.lei || 0) === 1 ? "virou lei" : "viraram lei") + ".",
          "In this term, the government sent <b>" + EP.num(r.total) + "</b> " + (r.total === 1 ? "bill" : "bills") + " to the legislature; <b>" + EP.num(r.lei || 0) + "</b> became law.") + "</p>";
        if (document.getElementById("propostas")) links.push('<a class="link-seta" href="#propostas">' + tr("Ver a lista na parte “O que propôs”", "See the list in “Proposals”") + ' <span aria-hidden="true">›</span></a>');
      } else if (r && r.total) {
        h += "<p>" + tr("Neste mandato: <b>" + EP.num(r.total) + "</b> " + (r.total === 1 ? "proposta" : "propostas") + (r.autor != null ? " (" + EP.num(r.autor) + " como autor" + (g === "F" ? "a" : "") + " principal)" : "") + "; <b>" + EP.num(r.lei || 0) + "</b> " + ((r.lei || 0) === 1 ? "virou lei" : "viraram lei") + ".",
          "In this term: <b>" + EP.num(r.total) + "</b> " + (r.total === 1 ? "bill" : "bills") + (r.autor != null ? " (" + EP.num(r.autor) + " as lead author)" : "") + "; <b>" + EP.num(r.lei || 0) + "</b> became law.") + "</p>";
        if (document.getElementById("propostas")) links.push('<a class="link-seta" href="#propostas">' + tr("Ver a lista na parte “O que propôs”", "See the list in “Proposals”") + ' <span aria-hidden="true">›</span></a>');
      }
      var v = p.votacoes && p.votacoes.resumo;
      if (v && v.total) {
        h += "<p>" + tr("Registrou voto em <b>" + EP.num(v.total) + "</b> votações nominais.", "Cast a recorded vote in <b>" + EP.num(v.total) + "</b> roll-call votes.") + "</p>";
        if (document.getElementById("votacoes")) links.push('<a class="link-seta" href="#votacoes">' + tr("Ver como votou", "See how they voted") + ' <span aria-hidden="true">›</span></a>');
      }
      if (p.executivo && document.getElementById("leis")) links.push('<a class="link-seta" href="#leis">' + tr("Ver as leis e os vetos", "See the laws and vetoes") + ' <span aria-hidden="true">›</span></a>');
      if (!h && !links.length) h = "<p>" + tr("O que a pessoa faz no mandato de hoje está nas outras partes deste perfil, quando a Casa ou o governo publica.", "What the person does in the current term is in the other parts of this profile, when the legislature or the government publishes it.") + "</p>";
      return h + (links.length ? '<p class="traj-links">' + links.join(" ") + "</p>" : "");
    }
    var nivel = NIVEL[it.c];
    if (it.c === "dep") return "<p>" + tr("Este mandato não aparece na lista de quem exerceu o mandato na Câmara (por exemplo: quem foi eleito e não assumiu). Por isso o site não mostra o que foi proposto.", "This term does not appear in the Chamber's list of members (for example, someone who was elected and did not take office). So the site does not show what was proposed.") + "</p>";
    if (it.c === "sen") return "<p>" + tr("Este mandato não aparece nos dados do Senado ligados a esta pessoa. Por isso o site não mostra o que foi proposto.", "This term does not appear in the Senate data linked to this person. So the site does not show what was proposed.") + "</p>";
    if (it.c === "dest" || it.c === "ddist") return "<p>" + tr("O site só tem os dados das Assembleias Legislativas do mandato de hoje. O que foi proposto nesse mandato fica no site oficial da Assembleia" + (it.c === "ddist" ? " (Câmara Legislativa do DF)" : "") + ".",
      "The site only has state legislature data for the current term. What was proposed in this term is on the legislature's official website.") + "</p>";
    if (it.c === "ver") return "<p>" + tr("O site só tem os dados das Câmaras Municipais do mandato de hoje. O que foi proposto nesse mandato fica no site oficial da Câmara Municipal.",
      "The site only has city council data for the current term. What was proposed in this term is on the city council's official website.") + "</p>";
    if (nivel) return "<p>" + tr("O site não reúne o que foi feito nos mandatos antigos de " + (it.c === "pres" ? "presidente" : it.c === "gov" ? "governador" : "prefeito") + ". As leis assinadas ficam publicadas no Diário Oficial.",
      "The site does not gather what was done in past terms as " + cargoTxt(it.c, g, true).toLowerCase() + ". The laws that were signed are published in the Official Gazette.") + "</p>";
    return "";
  }

  // ---------------------------------------------------------------- um item da linha do tempo
  function itemHtml(it, d, p, k, vistos, o) {
    var g = p.genero, en = EP.en, h = "", chips = [], cls = ["traj-item"];
    var ano = it.a || (it.i ? +it.i.slice(0, 4) : null) || (it.m && it.m.i ? +it.m.i.slice(0, 4) : null);
    var nivel = it.k === "stf" || it.k === "min" ? "pais" : NIVEL[it.c] || "pais";
    var ic = it.k === "stf" ? "⚖️" : it.k === "min" ? "🏢" : IC_NIVEL[nivel];
    var titulo;
    if (it.k === "stf") titulo = tr(EP.gen(g, "Ministro", "Ministra") + " do Supremo Tribunal Federal", "Justice of the Federal Supreme Court");
    else if (it.k === "min") titulo = tr(EP.gen(g, "Ministro", "Ministra"), "Minister") + (it.min ? " · " + (en && it.min_en ? esc(it.min_en) : EP.pt(esc(it.min))) : "");
    else titulo = esc(cargoTxt(it.c, g, en)) + " · " + lugarHtml(it, d);
    var exerceu = !!(it.m || it.k === "a" || it.k === "stf" || it.k === "min" || it.hoje);
    if (exerceu) cls.push("traj-mandato");
    if (it.hoje || (it.m && it.m.hoje)) cls.push("traj-hoje");
    var res = null;
    if (it.k === "c") {
      res = resultadoTxt(it, g);
      chips.push('<span class="chip traj-r-' + res[1] + '"><span aria-hidden="true">' + ({ e: "🗳️ ", "2t": "⏳ ", sup: "🪑 ", outro: "▫️ " }[res[1]] || "") + "</span><span>" + res[0] + "</span></span>");
      if (it.s) chips.push('<span class="chip neutro"><span aria-hidden="true">🔁 </span>' + tr("Eleição suplementar", "Special election") + (it.dt ? " · " + esc(EP.data(it.dt)) : "") + "</span>");
    }
    if (it.k === "a") chips.push('<span class="chip"><span aria-hidden="true">🔑 </span>' + tr("Assumiu o cargo", "Took office") + (it.i ? " · " + esc(EP.data(it.i)) : "") + "</span>");
    if (it.k === "m" && !it.m) chips.push('<span class="chip"><span aria-hidden="true">🔑 </span>' + tr("Exerceu o mandato", "Served in office") + "</span>");
    if (it.k === "stf") chips.push('<span class="chip"><span aria-hidden="true">🔑 </span>' + tr("Tomou posse no STF", "Sworn in at the Supreme Court") + (it.i ? " · " + esc(EP.data(it.i)) : "") + "</span>");
    if (it.k === "min" && it.i) chips.push('<span class="chip"><span aria-hidden="true">🔑 </span>' + tr("No cargo desde ", "In office since ") + esc(EP.data(it.i)) + "</span>");
    if (it.hoje || (it.m && it.m.hoje)) chips.push('<span class="chip amarelo"><span aria-hidden="true">📍 </span>' + tr("No cargo hoje", "In office today") + "</span>");
    if (it.ex) chips.push('<span class="chip amarelo"><span aria-hidden="true">🔑 </span>' + esc(tr(it.ex, it.ex_en || it.ex)) + "</span>");
    if (it.po) chips.push('<span class="chip amarelo"><span aria-hidden="true">📅 </span>' + tr("Toma posse em ", "Takes office on ") + esc(EP.dataLonga(it.po)) + "</span>");
    // linha de detalhes: partido, votos, nome na urna
    var det = [];
    if (it.p) det.push(tr("Partido na época: ", "Party at the time: ") + EP.pt(esc(it.p)));
    if (it.v != null) det.push(EP.num(it.v) + " " + tr(it.v === 1 ? "voto" : "votos", it.v === 1 ? "vote" : "votes") + (it.t === 2 ? tr(" no 2º turno", " in the runoff") : ""));
    if (it.ch && it.ch.v != null) det.push(tr("votos da chapa: ", "votes for the ticket: ") + EP.num(it.ch.v));
    if (it.n) det.push(tr("nome na urna: ", "name on the ballot: ") + EP.pt(esc(it.n)));
    var expl = it.k === "c" ? explicaResultado(it) : "";
    if (it.k === "c" && it.r === "sup" && (it.hoje || it.ex || it.m)) expl = tr("Ficou como suplente e depois assumiu a vaga.", "Was an alternate and later took the seat.");
    // a explicação de cada tipo de resultado aparece uma vez só (na primeira vez)
    if (expl && vistos[expl]) expl = "";
    else if (expl) vistos[expl] = 1;
    // mandato exercido (Câmara/Senado)
    var mand = "";
    if (it.m) {
      var m = it.m, sup = m.como === "suplente" || it.r === "sup", agora = !m.f && !m.dl;
      var como = sup ? (agora ? tr("Assumiu como suplente e exerce o mandato ", "Took office as an alternate and has served ") : tr("Assumiu como suplente e exerceu o mandato ", "Took office as an alternate and served "))
        : (agora ? tr("Exerce o mandato ", "Has served ") : tr("Exerceu o mandato ", "Served "));
      mand = '<p class="traj-exerceu"><span aria-hidden="true">🔑 </span>' + como + esc(periodoTxt(m)) + (m.casa === "camara" ? tr(" (Câmara dos Deputados)", " (Chamber of Deputies)") : tr(" (Senado Federal)", " (Federal Senate)")) + ".</p>";
    }
    if (it.k === "a" && it.txt) mand = "<p>" + esc(tr(it.txt, it.txt_en || it.txt)) + "</p>";
    if (it.k === "stf") mand = "<p>" + tr("Ministros do STF não são eleitos: o presidente da República indica e o Senado aprova.", "Supreme Court justices are not elected: the President nominates and the Senate approves.") + "</p>";
    if (it.k === "min") mand = "<p>" + tr("Ministros não são eleitos: o presidente da República escolhe.", "Ministers are not elected: the President chooses them.") + "</p>";
    // "o que fez nesse mandato": com o seletor de mandato do perfil (perfil-mandato-r10), cada mandato exercido tem um
    // resumo de uma linha e o botão "Ver este mandato" (o perfil inteiro, filtrado); sem ele, o bloco que abre de antes
    var fez = "", md = o && o.mandatos && o.url ? doItem(o.mandatos, it) : null;
    if (md) fez = verMandatoHtml(md, it, p, o, vistos);
    else if (o && o.url) fez = "";
    else if (it.m) fez = fezMandato(it.m, p, it);
    else if ((it.k === "c" && (eleito(it.r) || it.hoje) && !it.po) || it.k === "a") fez = fezSemCasa(it, p);
    var fontes = fontesItem(it, d, p);
    h += '<li class="' + cls.join(" ") + (md && o.sel === md ? " traj-vendo-item" : "") + '" data-nivel="' + nivel + '" data-ganhou="' + (exerceu || (res && res[1] === "e") ? 1 : 0) + '"' +
      (md ? ' data-mandato="' + esc(md.id) + '"' : "") + ">" +
      '<span class="traj-ponto" aria-hidden="true">' + ic + "</span>" +
      '<div class="traj-cartao">' +
      '<h3 class="traj-tit" id="traj-' + k + '"><span class="traj-ano">' + (ano || "") + "</span> " + titulo + "</h3>" +
      (chips.length ? '<div class="chips traj-chips">' + chips.join("") + "</div>" : "") +
      (det.length ? '<p class="traj-det">' + det.join(" · ") + "</p>" : "") +
      (expl ? '<p class="traj-det muted">' + esc(expl) + "</p>" : "") + mand +
      (md ? fez : fez ? EP.blocoAbre("traj-fez", '<span aria-hidden="true">📜 </span>' + tr("O que fez nesse mandato", "What they did in this term"), fez, false) : "") +
      (fontes.length ? '<p class="traj-fonte">' + EP.botaoFontes(fontes, tr("Fonte", "Source")) + "</p>" : "") +
      "</div></li>";
    return h;
  }

  // ---------------------------------------------------------------- resumo no topo
  function resumoHtml(t, p, mand) {
    var g = p.genero, a = g === "F" ? "a" : "o";
    var cands = t.it.filter(function (it) { return it.k === "c"; });
    var n = cands.length;
    if (!n) {
      if (p.tipo === "min") return "<p>" + tr("A lista oficial dos ministros não traz o nome completo nem a data de nascimento, então o site não liga as eleições do TSE a esta pessoa (para não confundir com alguém de mesmo nome).",
        "The official list of ministers does not include the full name or the date of birth, so the site does not link TSE elections to this person (to avoid mixing them up with someone who has the same name).") + "</p>";
      return "<p>" + tr("Não achamos candidaturas desta pessoa nos dados do TSE desde 1994.", "We did not find any candidacies for this person in TSE data since 1994.") + "</p>";
    }
    var ganhas = cands.filter(function (it) { return eleito(it.r); });
    var cargos = {};
    ganhas.forEach(function (it) { cargos[it.c === "ddist" ? "dest" : it.c] = 1; });
    var nc = Object.keys(cargos).length, desde = Math.min.apply(null, cands.map(function (it) { return it.a; }));
    var supl = t.it.filter(function (it) { return it.r === "sup" && it.m; }).length;
    var txt;
    if (n === 1) txt = tr("Concorreu 1 vez, em " + desde, "Ran for office once, in " + desde) + (ganhas.length ? tr(", e foi eleit" + a + ".", ", and was elected.") : ".");
    else txt = tr("Concorreu " + EP.num(n) + " vezes desde " + desde, "Ran for office " + EP.num(n) + " times since " + desde) +
      (ganhas.length ? tr(": eleit" + a + " " + EP.num(ganhas.length) + (ganhas.length === 1 ? " vez" : " vezes") + " para " + nc + (nc === 1 ? " cargo" : " cargos diferentes") + ".",
        ": elected " + EP.num(ganhas.length) + (ganhas.length === 1 ? " time" : " times") + " to " + nc + (nc === 1 ? " office" : " different offices") + ".") :
        tr(". Não foi eleit" + a + " em nenhuma delas.", ". Was not elected in any of them."));
    if (supl) txt += " " + tr("Assumiu " + supl + (supl === 1 ? " vez" : " vezes") + " como suplente.", "Took office " + supl + (supl === 1 ? " time" : " times") + " as an alternate.");
    var chips = ['<span class="chip neutro"><span aria-hidden="true">🗳️ </span>' + EP.num(n) + " " + tr(n === 1 ? "candidatura" : "candidaturas", n === 1 ? "candidacy" : "candidacies") + "</span>",
      '<span class="chip neutro"><span aria-hidden="true">🏅 </span>' + EP.num(ganhas.length) + " " + tr(ganhas.length === 1 ? "eleição ganha" : "eleições ganhas", ganhas.length === 1 ? "election won" : "elections won") + "</span>"];
    // site-d-r14: os números grandes (as mesmas contas da frase, que continua para quem lê)
    if (EP.d && mand != null) return '<p class="traj-resumo">' + txt + "</p>" + EP.d.kpis([
      { ic: "🗳️", n: EP.num(n), t: tr(n === 1 ? "eleição disputada" : "eleições disputadas", n === 1 ? "election" : "elections") },
      { ic: "🏅", n: EP.num(ganhas.length), t: tr((ganhas.length === 1 ? "vez eleit" : "vezes eleit") + a, ganhas.length === 1 ? "time elected" : "times elected") },
      { ic: "🔑", n: EP.num(mand), t: tr(mand === 1 ? "mandato exercido" : "mandatos exercidos", mand === 1 ? "term served" : "terms served") }], tr("A história em números", "The career in numbers"), "traj-kpis");
    return '<p class="traj-resumo">' + txt + '</p><div class="chips traj-chips" aria-hidden="true">' + chips.join("") + "</div>";
  }

  // ---------------------------------------------------------------- site-d-r14: a faixa do tempo
  // Uma barra por mandato exercido, num eixo de anos (o mais novo em cima); o mandato aberto no perfil fica amarelo. Com o
  // seletor de mandato (perfil-mandato-r10), cada linha é um link "Ver este mandato" (o mesmo endereço do botão da lista).
  // A barra é só desenho: o cargo, o lugar e o período ficam escritos ao lado.
  function tempoHtml(M, p, o) {
    var l = (M && M.lista || []).filter(function (md) { return md.i; });
    if (!l.length) return "";
    var hoje = hojeISO(), ini = Math.min.apply(null, l.map(function (md) { return +md.i.slice(0, 4); })), fim = +hoje.slice(0, 4);
    l.forEach(function (md) { var f = md.f || md.fl; if (f) fim = Math.max(fim, +f.slice(0, 4)); });
    var anos = Math.max(1, fim - ini + 1), aberto = o && o.sel ? o.sel : M.atual;
    var links = !!(o && o.url && M.lista.length > 1);
    return '<h3 class="traj-tempo-tit" id="t-traj-tempo">' + tr("A faixa do tempo", "The timeline") + ' <small>' + ini + tr(" a ", "–") + fim + "</small></h3>" +
      '<ol class="d-tempo" aria-labelledby="t-traj-tempo" style="--anos:' + anos + '">' + l.map(function (md) {
        var a = +md.i.slice(0, 4), b = +((md.f || md.fl || hoje).slice(0, 4)), aqui = md === aberto;
        var rot = '<span class="d-tempo-rot"><b>' + esc(cargoLugar(md, p, M.d)) + "</b><small>" + esc(periodo(md)) + (aqui && links ? tr(" · você está vendo", " · you are viewing this") : "") + "</small></span>" +
          '<span class="d-tempo-trilho" aria-hidden="true"><i style="left:' + (100 * (a - ini) / anos).toFixed(1) + "%;width:" + Math.max(2, 100 * (b - a + 1) / anos).toFixed(1) + '%"></i></span>';
        return '<li class="' + (aqui ? "aqui" : "") + '">' + (links && !aqui ? '<a class="d-tempo-item" href="' + esc(o.url(md)) + '" data-mandato="' + esc(md.id) + '"><span class="sr">' +
          tr("Ver este mandato: ", "See this term: ") + "</span>" + rot + "</a>" : '<div class="d-tempo-item">' + rot + "</div>") + "</li>";
      }).join("") + "</ol>";
  }

  function comoHtml(t, p) {
    var falta = (t.falta || []).filter(function (a) { return a <= 1996; });
    var c = "<p>" + tr("Juntamos as candidaturas de cada eleição desde 1994 nos dados abertos do TSE. Para saber que é a mesma pessoa, usamos o CPF ou o número do título de eleitor e, quando eles não existem (1994 e 1996), o nome completo e a data de nascimento, exatos. Nunca só o nome: se houver dúvida, a candidatura fica de fora.",
      "We put together the candidacies of every election since 1994 from the TSE open data. To know it is the same person, we use the CPF (Brazilian taxpayer number) or the voter ID number and, when they do not exist (1994 and 1996), the full name and the date of birth, exactly. Never the name alone: if there is any doubt, the candidacy is left out.") + "</p>" +
      "<p>" + tr("Os mandatos na Câmara e no Senado vêm dos dados abertos de cada Casa, que mostram também quem era suplente e assumiu. O que a pessoa propôs é contado pelos mesmos arquivos, de 1987 em diante na Câmara.",
        "Terms in the Chamber of Deputies and the Senate come from each chamber's open data, which also show alternates who took office. What the person proposed is counted from the same files, from 1987 onwards in the Chamber.") + "</p>" +
      "<p>" + tr("O resultado de cada candidatura é o dos dados abertos do TSE (a situação depois da totalização). Os votos são a soma da votação por município e zona dos mesmos dados abertos; nas eleições mais antigas, essa soma pode ser um pouco diferente do total divulgado na época.",
        "The result of each candidacy is the one in the TSE open data (the status after the vote count). The votes are the sum of the votes by municipality and electoral zone in the same open data; in the oldest elections, this sum may differ slightly from the total announced at the time.") + "</p>";
    if (falta.length) c += '<p class="aviso">' + tr("Pode faltar uma candidatura de " + falta.join(" e ") + ": nesses anos, o TSE não guardou o CPF, o título nem a data de nascimento de parte dos candidatos, e há uma candidatura com o mesmo nome no mesmo estado. Não dá para saber se é a mesma pessoa.",
      "A candidacy from " + falta.join(" and ") + " may be missing: in those years, the TSE did not keep the CPF, voter ID or date of birth of some candidates, and there is a candidacy with the same name in the same state. There is no way to know if it is the same person.") + "</p>";
    return EP.blocoAbre("traj-como", '<span aria-hidden="true">🔎 </span>' + tr("Como montamos esta linha do tempo", "How we built this timeline"), c, false);
  }

  // ---------------------------------------------------------------- filtros (só quando a lista é longa)
  var LONGA = 6;
  function filtrosHtml(itens) {
    var niveis = {};
    itens.forEach(function (it) { niveis[it.k === "stf" || it.k === "min" ? "pais" : NIVEL[it.c] || "pais"] = 1; });
    var b = [["todos", tr("Tudo", "Everything")]];
    if (Object.keys(niveis).length > 1) {
      if (niveis.pais) b.push(["pais", "🏛️ " + tr("No país", "Country")]);
      if (niveis.estado) b.push(["estado", "🗺️ " + tr("No estado", "State")]);
      if (niveis.cidade) b.push(["cidade", "🏘️ " + tr("Na cidade", "City")]);
    }
    b.push(["ganhou", "🔑 " + tr("Só eleições ganhas e mandatos", "Only elections won and terms")]);
    return '<div class="traj-filtros" role="group" aria-label="' + esc(tr("Mostrar na linha do tempo", "Show in the timeline")) + '">' + b.map(function (x, i) {
      return '<button type="button" class="chip traj-filtro" data-traj-filtro="' + x[0] + '" aria-pressed="' + (i === 0) + '">' + esc(x[1]) + "</button>";
    }).join("") + '</div><p class="sr" aria-live="polite" data-traj-conta></p>';
  }
  function liga(raiz) {
    raiz.addEventListener("click", function (e) {
      var b = e.target.closest("[data-traj-filtro]");
      if (!b) return;
      var f = b.getAttribute("data-traj-filtro");
      [].forEach.call(raiz.querySelectorAll("[data-traj-filtro]"), function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      var lis = raiz.querySelectorAll(".traj-item"), n = 0;
      [].forEach.call(lis, function (li) {
        var ok = f === "todos" || (f === "ganhou" ? li.getAttribute("data-ganhou") === "1" : li.getAttribute("data-nivel") === f);
        li.hidden = !ok;
        if (ok) n++;
      });
      var c = raiz.querySelector("[data-traj-conta]");
      if (c) c.textContent = tr("Mostrando " + n + " de " + lis.length, "Showing " + n + " of " + lis.length);
    });
  }

  // as candidaturas vêm em lista curta: [ano, cargo, lugar, partido, resultado, votos, SQ, extras] (lugar = código do
  // município no TSE ou a UF); o resto (mandatos, posse no STF...) vem como objeto
  function expande(x, d) {
    if (!Array.isArray(x)) return x;
    var it = { k: "c", a: x[0], c: x[1], p: x[3] == null ? null : x[3], r: x[4], v: x[5] == null ? null : x[5], sq: x[6] || null };
    if (/^\d+$/.test(String(x[2]))) { it.ue = x[2]; it.uf = ((d.ues || {})[x[2]] || [])[2] || null; } else it.uf = x[2];
    if (x[7]) Object.keys(x[7]).forEach(function (k) { it[k] = x[7][k]; });
    return it;
  }

  // ---------------------------------------------------------------- perfil-mandato-r10: os mandatos exercidos
  // Cada mandato que a pessoa exerceu (ou para o qual foi eleita e tomou posse), do mais novo para o mais velho, para o
  // seletor "Mandato" do perfil (js/pessoa.js) e o botão "Ver este mandato" da linha do tempo:
  //   { id ("dep-1987": cargo + ano do começo), c (cargo), uf, ue (município no TSE), it (o item da linha do tempo), m (o
  //     mandato da Câmara ou do Senado, se houver), i, f (datas; f = null: em curso), fr ([de, até]: o período das propostas),
  //     aprox (as datas são as do mandato para o qual foi eleita: o TSE não diz quando a pessoa entrou e saiu), hoje (o
  //     mandato do perfil de hoje), andando (em curso, mas não é o do perfil: ex. eleito de 2026 que hoje é deputado),
  //     como ("titular" | "suplente"), p (partido na época, da candidatura), a (ano da eleição) }
  var EXEC = { pres: 1, vp: 1, gov: 1, vgov: 1, pref: 1, vpref: 1 };
  var TERMO = { pres: 1, vp: 1, gov: 1, vgov: 1, pref: 1, vpref: 1, ver: 1, dest: 1, ddist: 1 };
  function hojeISO() { return new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10); }
  // as datas de cada legislatura da Câmara (a 48ª começou em 1º/2/1987; cada uma tem 4 anos)
  function legDatas(L) { var a = 1987 + 4 * (L - 48); return [a + "-02-01", (a + 4) + "-01-31"]; }
  // o mandato para o qual a pessoa foi eleita numa eleição do ano "a" (posse e fim previstos na Constituição; as eleições de
  // 2022 terminam em 5/1/2027 para presidente e em 6/1/2027 para governador, pela Emenda Constitucional 111)
  function termo(c, a, it) {
    var ini, fim;
    if (/^(pres|vp|gov|vgov)$/.test(c)) { ini = (a + 1) + "-01-01"; fim = a >= 2022 ? (a + 5) + (/^(pres|vp)$/.test(c) ? "-01-05" : "-01-06") : (a + 4) + "-12-31"; }
    else if (/^(dest|ddist)$/.test(c)) { ini = (a + 1) + "-02-01"; fim = (a + 5) + "-01-31"; }
    else { ini = (a + 1) + "-01-01"; fim = (a + 4) + "-12-31"; }
    // eleição suplementar: do dia da eleição até o fim do mandato que estava em curso
    if (it && it.s) {
      var mun = /^(pref|vpref|ver)$/.test(c), y = a;
      while (mun ? y % 4 !== 0 : y % 4 !== 2) y++;
      ini = it.dt || a + "-01-01";
      fim = y + "-12-31";
    }
    return [ini, fim];
  }
  function mandatos(p, d, t) {
    var l = [], hoje = hojeISO(), po = null, pm = p.mandato || {};
    t.it.forEach(function (it) {
      var md = null;
      if (it.po && !po) po = it;
      if (it.m) {
        var m = it.m, sen = m.casa === "senado", r = m.leg ? legDatas(m.leg) : null;
        md = { c: sen ? "sen" : "dep", m: m, i: m.dl && r ? r[0] : m.i, f: m.f || null, fr: sen ? [m.i, m.f || "9999-12-31"] : r || [m.i, m.f || "9999-12-31"],
          como: m.como || (it.r === "sup" ? "suplente" : "titular"), hoje: !!(it.hoje || m.hoje), andando: !m.f };
        if (!m.f && r) md.fl = r[1];  // legislatura em curso: o fim previsto (para o nome do mandato)
      } else if (it.k === "c" && !it.po && ((eleito(it.r) && TERMO[it.c]) || (it.hoje && (it.r === "sup" || it.ex)))) {
        var tm = termo(it.c, it.a, it);
        md = { c: it.c, i: tm[0], f: tm[1], fr: tm, aprox: true, como: it.r === "sup" ? "suplente" : "titular", hoje: !!it.hoje };
      } else if (it.k === "a" || it.k === "stf" || it.k === "min") {
        md = { c: it.k === "stf" ? "stf" : it.k === "min" ? "min" : it.c, i: it.i, f: null, hoje: !!it.hoje, como: "titular" };
        md.fr = [md.i || "0000", "9999-12-31"];
      }
      if (!md) return;
      md.it = it;
      md.uf = it.uf || null;
      md.ue = it.ue || null;
      md.p = it.p || null;
      md.a = it.a || null;
      if (md.hoje) {
        // o mandato de hoje: as datas do perfil (o fim previsto e, fora da Câmara, o começo)
        if (pm.inicio && md.c !== "dep" && !md.m) { md.i = pm.inicio; md.aprox = false; }
        if (!md.f || md.aprox) md.f = pm.fim || md.f;
        md.andando = true;
        md.fr = [md.fr[0], "9999-12-31"];
      } else if (md.f && md.f >= hoje && !md.m) md.andando = true;
      if (!md.i) return;
      l.push(md);
    });
    l.sort(function (a, b) { return a.i < b.i ? 1 : a.i > b.i ? -1 : (b.hoje ? 1 : 0) - (a.hoje ? 1 : 0); });
    var vistos = {};
    l.forEach(function (md) {
      var id = md.c + "-" + md.i.slice(0, 4);
      if (vistos[id]) id = md.c + "-" + md.i;
      vistos[id] = 1;
      md.id = id;
    });
    var atual = l.filter(function (md) { return md.hoje; })[0] || null;
    // um só "hoje": quem era vice e assumiu o cargo tem os dois marcados; o de vice acaba quando assumiu
    l.forEach(function (md) {
      if (md.hoje && md !== atual) { md.hoje = false; md.andando = false; if (atual.i > md.i) md.f = atual.i; }
    });
    // eleitos de 2026 sem cargo hoje (perfil e26-): o "hoje" do perfil é a eleição, com a posse marcada
    var futuro = !atual && p.e26 && po ? { id: "", futuro: true, c: po.c, uf: po.uf, ue: po.ue, it: po, i: po.po, f: null, p: po.p, a: po.a } : null;
    return { lista: l, atual: atual, futuro: futuro, d: d, t: t };
  }
  function doItem(M, it) { return M.lista.filter(function (md) { return md.it === it; })[0] || null; }

  // ---------------------------------------------------------------- textos de um mandato
  function lugarTxt(md, d) {
    if (/^(pres|vp|stf|min)$/.test(md.c)) return "";
    var c = md.ue && d && d.ues && d.ues[md.ue];
    if (c) return c[1] + ", " + c[2];
    if (md.it && md.it.cid && d && d.cidade) return d.cidade + (md.uf ? ", " + md.uf : "");
    return EP.UFS[md.uf] || md.uf || "";
  }
  // "2003 a 2006" / "2003–2006"; datas inteiras quando começa e acaba no mesmo ano; "desde 2024" quando ainda não acabou
  function periodo(md) {
    if (md.futuro) return tr("posse em " + EP.dataLonga(md.i), "takes office on " + EP.dataLonga(md.i));
    var i = md.i, f = md.f || md.fl;
    if (!f) return tr("desde " + i.slice(0, 4), "since " + i.slice(0, 4));
    var a = +i.slice(0, 4), b = +f.slice(0, 4);
    // os mandatos do Executivo que acabam nos primeiros dias de janeiro (posse do próximo) contam até o ano anterior
    if (EXEC[md.c] && f.slice(5, 7) === "01" && b > a) b--;
    if (a === b && !md.aprox) return EP.data(i) + tr(" a ", " to ") + EP.data(f);
    return a === b ? String(a) : tr(a + " a " + b, a + "–" + b);
  }
  function cargoLugar(md, p, d) {
    var c = cargoTxt(md.c, p.genero, EP.en), l = lugarTxt(md, d);
    if (md.c === "min" && md.it && md.it.min) c += " · " + (EP.en && md.it.min_en ? md.it.min_en : md.it.min);
    return c + (l ? " (" + l + ")" : "");
  }
  // o nome do mandato no seletor: "2023 a 2026 – Presidente (atual)", "2011 a 2015 – Deputado federal · Alagoas"
  function rotulo(md, p, d) {
    var c = cargoTxt(md.c, p.genero, EP.en), l = lugarTxt(md, d);
    if (md.c === "min" && md.it && md.it.min) c += " · " + (EP.en && md.it.min_en ? md.it.min_en : md.it.min);
    c += l ? " · " + l : "";
    if (md.futuro) return c + tr(" – eleit" + (p.genero === "F" ? "a" : "o") + " em " + md.a + ", " + periodo(md), " – elected in " + md.a + ", " + periodo(md));
    return periodo(md) + " – " + c + (md.hoje ? tr(" (atual)", " (current)") : md.andando ? tr(" (em curso)", " (in progress)") : "");
  }

  // ---------------------------------------------------------------- "Ver este mandato" (linha do tempo)
  function verMandatoHtml(md, it, p, o, vistos) {
    var h = "", m = it.m, z = (o.conta && o.conta(md)) || (m && m.fez) || null;
    if (m && z) {
      var casa = m.casa === "camara" ? tr("na Câmara", "in the Chamber of Deputies") : tr("no Senado", "in the Senate");
      h = z.prop ? tr("Apresentou ou assinou junto <b>" + EP.num(z.prop) + "</b> " + (z.prop === 1 ? "proposta " : "propostas ") + casa + "; <b>" + EP.num(z.lei || 0) + "</b> " + ((z.lei || 0) === 1 ? "virou lei" : "viraram lei") + ".",
        "Filed or co-signed <b>" + EP.num(z.prop) + "</b> " + (z.prop === 1 ? "bill " : "bills ") + casa + "; <b>" + EP.num(z.lei || 0) + "</b> became law.") :
        tr("Não apresentou propostas " + casa + " nesse período, segundo os dados abertos.", "Did not file any bills " + casa + " in this period, according to the open data.");
      if (z.prop && !vistos._ctx) {
        vistos._ctx = 1;
        h += ' <span class="muted">' + tr("Propor muitas ou poucas propostas não quer dizer trabalhar mais ou menos: é só uma contagem.", "Filing many or few bills does not mean working more or less: it is just a count.") + "</span>";
      }
    }
    var aqui = o.sel ? o.sel === md : md.hoje;
    var rot = cargoLugar(md, p, o.mandatos.d) + ", " + periodo(md);
    var btn = aqui ? '<p class="traj-vendo"><span aria-hidden="true">👁️ </span>' + tr("Você está vendo este mandato nas outras abas.", "You are viewing this term in the other tabs.") + "</p>" :
      '<a class="btn peq traj-ver-btn" href="' + esc(o.url(md)) + '" data-mandato="' + esc(md.id) + '"><span aria-hidden="true">📅 </span>' +
      tr("Ver este mandato", "See this term") + '<span class="sr"> (' + esc(rot) + ")</span></a>";
    return '<div class="traj-ver">' + (h ? '<p class="traj-fez-curto">' + h + "</p>" : "") + btn + "</div>";
  }

  // ---------------------------------------------------------------- montar
  var baldes = {};
  function carrega(p) {
    if (!p || !p.id) return Promise.resolve(null);
    var b = balde(p.id);
    if (!baldes[b]) baldes[b] = EP.json("dados/trajetoria/" + b + ".json");
    return baldes[b].then(function (d) {
      var t = d && d.pessoas && d.pessoas[p.id];
      if (!t) return null;
      if (!t._pronto) { t.it = t.it.map(function (x) { return expande(x, d); }); t._pronto = true; }
      return { d: d, t: t };
    });
  }
  // o = { mandatos (EP.trajetoria.mandatos), sel (o mandato que o perfil mostra; null = o de hoje), url(md) (o endereço do
  // perfil filtrado), conta(md) ({ prop, lei } contados no próprio perfil, ou null) }
  EP.trajetoria = function (el, p, o) {
    if (!el || !p || !p.id) return Promise.resolve(null);
    return carrega(p).then(function (x) {
      var t = x && x.t, d = x && x.d;
      // sem trajetória para a pessoa: fica o que já estava no elemento (ex.: "Mandatos anteriores no mesmo cargo")
      if (!t || (!t.it.length && p.tipo !== "min")) { if (!el.innerHTML.trim()) el.hidden = true; return null; }
      d.cidade = p.municipio && p.municipio.nome;
      var itens = t.it, vistos = {}, M = o && o.mandatos ? o.mandatos : mandatos(p, d, t);
      var ela = p.genero === "F" ? "ela" : p.genero === "M" ? "ele" : "a pessoa", she = p.genero === "F" ? "she" : p.genero === "M" ? "he" : "this person";
      var intro = p.tipo === "min" ? tr("Os cargos desta pessoa que o site consegue mostrar com segurança, com a fonte oficial.", "The offices of this person that the site can show reliably, with the official source.") :
        tr("Todas as vezes que " + ela + " concorreu numa eleição desde 1994, segundo o TSE, e os mandatos que exerceu. Da mais nova para a mais antiga.",
          "Every time " + she + " ran in an election since 1994, according to the TSE (Superior Electoral Court), and the terms they served. Newest first.");
      if (o && o.url && o.mandatos && o.mandatos.lista.length > 1) intro += " " + tr("Em cada mandato, o botão “Ver este mandato” mostra o perfil só daquele período.",
        "For each term, the “See this term” button shows the profile for that period only.");
      var html = '<h2 id="t-traj"><span class="ic" aria-hidden="true">🧭</span>' + tr("A história na política", "Political career") + "</h2>" +
        '<p class="traj-intro">' + intro + "</p>" +
        resumoHtml(t, p, M.lista.length) + tempoHtml(M, p, o) +
        (EP.d ? '<h3 class="traj-todas">' + tr("Todas as eleições e os mandatos", "All the elections and terms") + "</h3>" : "") + (itens.length > LONGA ? filtrosHtml(itens) : "") +
        '<ol class="traj-lista" aria-labelledby="t-traj">' + itens.map(function (it, k) { return itemHtml(it, d, p, k, vistos, o); }).join("") + "</ol>" +
        comoHtml(t, p);
      el.innerHTML = html;
      el.classList.add("secao-perfil", "traj");
      if (!el.id) el.id = "trajetoria";
      el.setAttribute("aria-labelledby", "t-traj");
      el.hidden = false;
      liga(el);
      return t;
    }).catch(function (e) {
      if (window.console) console.warn("trajetória:", e);
      if (!el.innerHTML.trim()) el.hidden = true;
      return null;
    });
  };
  EP.trajetoria.balde = function (id) { return balde(id); };
  EP.trajetoria.baldePropostas = function (chave) { return balde(chave, 64); };  // dados/trajetoria/propostas/
  EP.trajetoria.carrega = carrega;
  EP.trajetoria.mandatos = mandatos;
  EP.trajetoria.rotulo = rotulo;
  EP.trajetoria.periodo = periodo;
  EP.trajetoria.cargoLugar = cargoLugar;
  EP.trajetoria.cargo = cargoTxt;
  EP.trajetoria.lugar = lugarTxt;
  EP.trajetoria.resultado = resultadoTxt;
  EP.trajetoria.fontes = fontesItem;
  EP.trajetoria.fontesMandato = fontesMandato;
  EP.trajetoria.legDatas = legDatas;
})();
