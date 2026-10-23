/* Uma votação do Plenário: votacao.html?casa=camara&id=2236186-60 (Câmara) ou votacao.html?casa=senado&id=7107 (Senado).
   Lê dados/votacoes/<casa>/<id>.json (contrato no README) e mostra: o que foi votado, o resultado com o plenário 3D,
   como cada partido votou (com a orientação publicada), o que cada liderança orientou e quem votou o quê.
   O plenário é só desenho (aria-hidden): tudo o que ele mostra está também no placar, em texto. */
(function () {
  "use strict";
  var EP = window.EP, D = EP.trd, V = EP.VOT, T = window.TRES || {}, esc = EP.esc;
  var raiz = document.getElementById("votacao");
  var id = (EP.param("id") || "").trim().replace(/^(camara|senado)-vot:/, "");
  var casa = (EP.param("casa") || "").toLowerCase().trim() || (/^\d+$/.test(id) ? "senado" : "camara");
  var DADO = null, FOTOS = {}, LOTE = 60, mostrando = LOTE, tBusca = null;
  var filtro = { voto: "", partido: "", uf: "", q: "" };
  var SEM = "Sem partido";

  D.canonico({ casa: casa, id: id });
  D.rodapeErros(document.getElementById("links-erro"), "Viu algo errado nesta página?", "Did you see something wrong on this page?");

  // ---------------------------------------------------------------- textos
  function gente(n) {
    return casa === "senado" ? EP.tr(n === 1 ? "senador" : "senadores", n === 1 ? "senator" : "senators") :
      EP.tr(n === 1 ? "deputado" : "deputados", n === 1 ? "deputy" : "deputies");
  }
  function novaAba() { return '<span class="sr"> ' + EP.tr("(abre em outra aba)", "(opens in a new tab)") + "</span>"; }
  function linkFora(url, txt) {
    return '<a href="' + esc(url) + '" target="_blank" rel="noopener"' + (EP.en ? ' hreflang="pt-BR"' : "") + ">" + txt + ' <span aria-hidden="true">↗</span>' + novaAba() + "</a>";
  }
  function nomePartido(p) { return p === SEM ? EP.tr("Sem partido", "No party") : p; }
  function rotuloVoto(v) {
    var x = D.voto(v);
    if (x.longo) return esc(x.longo);
    var leg = (DADO.legenda || {})[v];
    return leg ? (EP.en ? D.ptHtml(leg, true) : esc(leg)) : esc(x.curto);
  }
  function cab(icone, idTit, tit, sub) {
    return '<div class="cab-bloco"><span class="ic-bloco" aria-hidden="true">' + icone + '</span><div><h2 id="' + idTit + '">' + tit + "</h2>" +
      (sub ? '<p class="muted">' + sub + "</p>" : "") + "</div></div>";
  }
  function titulo(d) { return (d.proposta && d.proposta.sigla) || EP.tr("Votação no Plenário", "Vote in the full house"); }

  // ---------------------------------------------------------------- topo
  function heroHtml(d) {
    var cat = V.cat(d.categoria);
    return '<section class="miolo cab-pagina vot-hero" aria-labelledby="titulo-pagina"><div class="cab-txt">' +
      '<span class="selo-topo">' + esc(V.casaNome(casa)) + "</span>" +
      '<h1 id="titulo-pagina">' + esc(titulo(d)) + "</h1>" +
      '<p class="vot-quando">' + EP.tr("Votação nominal no Plenário em ", "Roll-call vote in the full house on ") + EP.dataLonga(d.data) +
      (d.hora ? EP.tr(", às ", " at ") + V.hora(d.hora) : "") + ".</p>" +
      '<div class="cat-explica">' + V.chipCat(d.categoria) + "<p>" + esc(EP.tr(cat.explica[0], cat.explica[1])) + "<br>" +
      EP.botaoFontes(cat.fontes, EP.tr("De onde vem essa explicação?", "Where does this explanation come from?")) + "</p></div>" +
      '<p><a class="link-seta voltar-vot" href="votacoes.html"><span aria-hidden="true">◀ </span>' + EP.tr("Ver todas as votações", "See all the votes") + "</a></p>" +
      '</div><div class="cab-3d" aria-hidden="true">' + (T.cuboEmoji ? T.cuboEmoji("🗳️") : "") + "</div></section>";
  }

  // ---------------------------------------------------------------- o que foi votado
  function oqueHtml(d) {
    var p = d.proposta || {}, s = EP.en ? p.s_en : p.s;
    var site = casa === "senado" ? EP.tr("no site do Senado", "on the Senate website") : EP.tr("no site da Câmara", "on the Chamber of Deputies website");
    return '<section class="miolo bloco" id="o-que" aria-labelledby="t-oque">' + cab("📄", "t-oque", EP.tr("O que foi votado", "What was voted on")) +
      '<div class="vot-oficial"><span class="rot-texto">' + EP.tr("Descrição oficial da votação", "Official description of the vote (in Portuguese)") + "</span>" +
      EP.pt(esc(d.descricao || "—")) + "</div>" +
      (/^(mantid|suprimid)[oa] o texto/i.test(d.descricao || "") ? '<p class="nota-lista"><span aria-hidden="true">✂️ </span>' + EP.tr(
        "Nesta votação, um pedaço do texto foi votado sozinho (um destaque): quem votou “Sim” queria que ele continuasse na proposta; quem votou “Não” queria tirá-lo.",
        "In this vote, one piece of the text was voted on separately: those who voted “Yes” wanted it to stay in the proposal; those who voted “No” wanted to take it out.") + "</p>" : "") +
      (p.sigla || p.ementa ? '<div class="vot-prop"><h3>' + EP.tr("A proposta", "The proposal") + (p.sigla ? ": " + esc(p.sigla) : "") + "</h3>" +
        (s ? '<p class="vot-simples"><span class="rot-texto">' + EP.tr("Em palavras simples (feita por IA)", "In plain words (written by AI)") + "</span>" + esc(s) + "</p>" : "") +
        (p.ementa ? '<div class="vot-oficial"><span class="rot-texto">' + EP.tr("Texto oficial (ementa)", "Official summary (ementa, in Portuguese)") + "</span>" + EP.pt(esc(p.ementa)) + "</div>" : "") +
        "</div>" : "") +
      '<p class="vot-links">' + (d.url ? linkFora(d.url, EP.tr("Ver esta votação ", "See this vote ") + site) : "") +
      (p.url ? linkFora(p.url, EP.tr("Ver a proposta ", "See the proposal ") + site) : "") + "</p>" +
      (casa === "camara" && /presenca-comissoes/.test(d.url || "") ? '<p class="nota-lista">' + EP.tr("No site da Câmara, escolha esta votação na lista da sessão.", "On the Chamber's website, choose this vote in the session's list.") + "</p>" : "") +
      "</section>";
  }

  // ---------------------------------------------------------------- resultado e plenário
  function semRegistro(d) { return casa === "camara" ? Math.max(0, V.TOTAL.camara - d.placar.total) : 0; }
  function plenarioHtml(d) {
    var p = d.placar, sr = semRegistro(d);
    // da esquerda para a direita: Sim, Abstenção, Obstrução, Outro, não registrou voto, Não (cores em css/votacoes.css)
    var g = [p["Sim"], p["Abstenção"], p["Obstrução"], p["Outro"], sr, p["Não"]];
    var total = g.reduce(function (a, b) { return a + b; }, 0);
    if (!T.plenario || !total) return "";
    return '<div class="plen-voto">' + T.plenario({ total: total, grupos: g, max: casa === "camara" ? 520 : 400 }) + "<p>" +
      (casa === "camara" ? EP.tr("Cada cadeira é um deputado. As cadeiras claras são de quem não registrou voto.", "Each seat is one deputy. The light seats belong to those who did not register a vote.") :
        EP.tr("Cada cadeira é um senador.", "Each seat is one senator.")) + "</p></div>";
  }
  function quorumHtml(d) {
    var q = d.quorum;
    if (!q) return "";
    var n = q.minimoSim || q.presentes, tot = V.TOTAL[casa], txt, fontes;
    if (q.regra === "pec") {
      txt = EP.tr("Para mudar a Constituição (PEC), são precisos pelo menos " + EP.num(n) + " votos “Sim”: três quintos dos " + EP.num(tot) + " " + gente(tot) + ". E isso em dois turnos (duas votações) em cada Casa.",
        "To change the Constitution (a PEC), at least " + EP.num(n) + " “Yes” votes are needed: three fifths of the " + EP.num(tot) + " " + gente(tot) + ". And that in two rounds (two votes) in each house.");
      fontes = V.F.pec;
    } else if (q.regra === "plp") {
      txt = EP.tr("Um projeto de lei complementar precisa de pelo menos " + EP.num(n) + " votos “Sim”: mais da metade de todos os " + EP.num(tot) + " " + gente(tot) + " (a maioria absoluta).",
        "A complementary law bill needs at least " + EP.num(n) + " “Yes” votes: more than half of all " + EP.num(tot) + " " + gente(tot) + " (an absolute majority).");
      fontes = V.F.plp;
    } else if (q.regra === "urgencia155") {
      txt = EP.tr("Este tipo de pedido de urgência (art. 155 do Regimento da Câmara) precisa de pelo menos " + EP.num(n) + " votos “Sim”: mais da metade dos " + EP.num(tot) + " deputados.",
        "This kind of urgency request (art. 155 of the Chamber's rules) needs at least " + EP.num(n) + " “Yes” votes: more than half of the " + EP.num(tot) + " deputies.");
      fontes = V.F.urgencia155;
    } else if (q.regra === "maioria") {
      txt = EP.tr("Regra geral: ganha o lado com mais votos, desde que pelo menos " + EP.num(n) + " " + gente(n) + " (mais da metade) estejam presentes.",
        "General rule: the side with more votes wins, as long as at least " + EP.num(n) + " " + gente(n) + " (more than half) are present.");
      fontes = V.F.maioria[casa];
    } else return "";
    var conta = q.minimoSim ? " " + EP.tr("Nesta votação, foram " + EP.num(d.placar.Sim) + " votos “Sim”.", "In this vote, there were " + EP.num(d.placar.Sim) + " “Yes” votes.") : "";
    return '<div class="quorum-vot"><span aria-hidden="true">⚖️</span><p><b>' + EP.tr("Quantos votos são precisos? ", "How many votes are needed? ") + "</b>" + esc(txt + conta) + "<br>" +
      EP.botaoFontes(fontes, EP.tr("De onde vem essa regra?", "Where does this rule come from?")) + "</p></div>";
  }
  function resultadoHtml(d) {
    var p = d.placar, sr = semRegistro(d);
    var ks = V.CATS_VOTO.filter(function (k) { return k === "Sim" || k === "Não" || p[k]; });
    var outros = {}, ordem = [];
    d.votos.forEach(function (v) {
      if (V.catVoto(v[4]) !== "Outro") return;
      var t = rotuloVoto(v[4]);
      t = /^[A-ZÀ-Ý][a-zà-ÿ]/.test(t) ? t.charAt(0).toLowerCase() + t.slice(1) : t;
      if (!(t in outros)) { outros[t] = 0; ordem.push(t); }
      outros[t]++;
    });
    var av = d.aviso;
    return '<section class="miolo bloco" id="resultado" aria-labelledby="t-res">' + cab("🗳️", "t-res", EP.tr("O resultado", "The result")) +
      '<div class="res-grade">' + plenarioHtml(d) + "<div>" +
      '<p class="res-linha">' + EP.tr("Resultado:", "Result:") + " " + V.chipRes(d.resultado, d.descricao) + "</p>" +
      '<ul class="placar-grande">' + ks.map(function (k) {
        return '<li data-v="' + k + '" style="--cv:' + V.COR[k] + '"><span class="pg-rot">' + esc(D.nomeVoto(k)) + "</span><b>" + EP.num(p[k]) + "</b></li>";
      }).join("") +
      (sr ? '<li class="sem-reg"><span class="pg-rot">' + EP.tr("Não registraram voto", "Did not register a vote") + "</span><b>" + EP.num(sr) + "</b></li>" : "") + "</ul>" +
      (ordem.length ? '<p class="outros-vot">' + EP.tr("Em “Outro”: ", "In “Other”: ") + ordem.map(function (t) { return t + " (" + EP.num(outros[t]) + ")"; }).join("; ") + ".</p>" : "") +
      (sr ? '<p class="outros-vot">' + EP.tr("A Câmara publica só quem registrou voto. Quem não registrou pode estar ausente, de licença, em missão oficial ou ter outro motivo.",
        "The Chamber only publishes who registered a vote. Those who did not may have been absent, on leave, on an official mission or had another reason.") + "</p>" : "") +
      (d.presidente ? '<p class="outros-vot">' + EP.tr("Quem presidia a sessão: ", "Presiding over the session: ") + esc(d.presidente) + ".</p>" : "") +
      quorumHtml(d) + "</div></div>" +
      (av && av.oficial && av.contado ? '<div class="aviso aviso-dados"><span aria-hidden="true">⚠️</span><p>' + EP.tr(
        "Atenção: a descrição oficial traz um placar (Sim " + EP.num(av.oficial.Sim) + ", Não " + EP.num(av.oficial["Não"]) + ") diferente da soma dos votos de cada um, publicada pela própria Casa (Sim " +
        EP.num(av.contado.Sim) + ", Não " + EP.num(av.contado["Não"]) + "). Mostramos os dois; o placar acima e a lista abaixo são os votos de cada um.",
        "Note: the official description shows a count (Yes " + EP.num(av.oficial.Sim) + ", No " + EP.num(av.oficial["Não"]) + ") that is different from the sum of each member's vote, published by the house itself (Yes " +
        EP.num(av.contado.Sim) + ", No " + EP.num(av.contado["Não"]) + "). We show both; the count above and the list below are the individual votes.") + "</p></div>" : "") +
      '<div class="dica-coruja nota-contexto" style="margin-top:18px"><span class="coruja" aria-hidden="true">🦉</span><p>' + EP.tr(
        "Votar “Sim” não é bom e votar “Não” não é ruim: depende do que estava sendo votado. E não votar tem muitos motivos: a pessoa pode estar em missão oficial, de licença, presidindo a sessão ou ausente. “Obstrução” é um recurso das regras da Casa: o partido deixa de contar para o número mínimo de presentes, para adiar ou evitar a votação.",
        "Voting “Yes” is not good and voting “No” is not bad: it depends on what was being voted on. And there are many reasons for not voting: the person may be on an official mission, on leave, presiding over the session or absent. “Obstruction” is a tool allowed by the house's rules: the party stops counting toward the minimum number of members present, to delay or prevent the vote.") +
      "</p></div></section>";
  }

  // ---------------------------------------------------------------- como cada partido votou
  function porPartido(d) {
    var m = {};
    d.votos.forEach(function (v) {
      var p = v[2] || SEM, x = m[p] || (m[p] = { partido: p, n: 0, c: {} });
      var c = V.catVoto(v[4]);
      x.n++;
      x.c[c] = (x.c[c] || 0) + 1;
    });
    // do partido com mais gente nesta votação para o com menos (é só uma contagem); empate: ordem alfabética
    return Object.keys(m).map(function (k) { return m[k]; }).sort(function (a, b) { return b.n - a.n || EP.norm(a.partido).localeCompare(EP.norm(b.partido)); });
  }
  function oriPartido(d, p) {
    var o = (d.orientacaoPartidos || {})[p];
    if (o) {
      var de = o.tipo === "partido" ? EP.tr("Orientação do partido", "Party's orientation") :
        (o.tipo === "federacao" ? EP.tr("Orientação da federação", "Federation's orientation") : EP.tr("Orientação do bloco", "Bloc's orientation")) + " (" + EP.pt(esc(o.lideranca)) + ")";
      return '<span aria-hidden="true">💬 </span>' + de + ": <b>" + V.orientacao(o.orientacao) + "</b>";
    }
    var coberto = (d.orientacoes || []).some(function (e) { return (e.partidos || []).indexOf(p) > -1; });
    return '<span aria-hidden="true">💬 </span>' + (coberto ? EP.tr("A liderança não registrou orientação.", "The leadership did not register an orientation.") :
      EP.tr("Orientação não identificada nos dados publicados.", "Orientation not identified in the published data."));
  }
  function partidosHtml(d) {
    var l = porPartido(d), max = l.length ? l[0].n : 1, temOri = (d.orientacoes || []).length > 0;
    return '<section class="miolo bloco" id="partidos" aria-labelledby="t-partidos">' +
      cab("🎗️", "t-partidos", EP.tr("Como cada partido votou", "How each party voted"),
        EP.tr("Uma linha para cada partido (o da época da votação), do que tinha mais gente votando para o que tinha menos. É só uma contagem, não um ranking.",
          "One row per party (the party at the time of the vote), from the one with the most members voting to the one with the fewest. It is just a count, not a ranking.")) +
      '<div class="explica-orient"><span aria-hidden="true">💬</span><p>' + EP.tr(
        "<b>Orientação</b> é o voto que o líder de um partido (ou de um grupo de partidos) pede para a sua bancada logo antes da votação. É só um pedido: cada um decide o próprio voto.",
        "An <b>orientation</b> is the vote that the leader of a party (or of a group of parties) asks their members to cast just before the vote. It is only a request: each member decides their own vote.") +
      (temOri ? "" : " " + EP.tr("Para esta votação, a Casa não publicou orientações.", "For this vote, the house did not publish any orientations.")) +
      "<br>" + EP.botaoFontes(V.F.orientacao, EP.tr("De onde vem isso?", "Where does this come from?")) + "</p></div>" +
      '<ul class="partidos-vot">' + l.map(function (x) {
        var ks = V.CATS_VOTO.filter(function (k) { return x.c[k]; });
        return '<li class="pv"><div class="pv-cab"><b class="pv-nome">' + (x.partido === SEM ? esc(nomePartido(x.partido)) : EP.pt(esc(x.partido))) + "</b>" +
          '<span class="pv-n">' + EP.num(x.n) + " " + gente(x.n) + "</span></div>" +
          '<span class="pv-trilho" aria-hidden="true"><span class="pv-barra" style="width:' + (100 * x.n / max).toFixed(1) + '%">' + ks.map(function (k) {
            return '<i style="width:' + (100 * x.c[k] / x.n).toFixed(2) + "%;background:" + V.COR[k] + '"></i>';
          }).join("") + "</span></span>" +
          '<p class="pv-txt">' + ks.map(function (k) { return '<span><i class="vot-q" style="background:' + V.COR[k] + '" aria-hidden="true"></i>' + esc(D.nomeVoto(k)) + " " + EP.num(x.c[k]) + "</span>"; }).join("") + "</p>" +
          (temOri ? '<p class="pv-ori">' + oriPartido(d, x.partido) + "</p>" : "") + "</li>";
      }).join("") + "</ul></section>";
  }

  // ---------------------------------------------------------------- o que cada liderança orientou
  var GERAIS = {
    governo: ["Governo", "Government", "O líder do governo, que fala pelo presidente da República.", "The government leader, who speaks for the President."],
    maioria: ["Maioria", "Majority", "O partido ou bloco com mais cadeiras.", "The party or bloc with the most seats."],
    minoria: ["Minoria", "Minority", "O maior grupo que tem, sobre o governo, uma posição diferente da Maioria.", "The largest group that takes a different position on the government from the Majority."],
    oposicao: ["Oposição", "Opposition", "Os partidos que fazem oposição ao governo.", "The parties that oppose the government."],
    bancada: ["Bancada Feminina", "Women's caucus", "As senadoras, juntas, com uma líder própria.", "The women senators together, with their own leader."]
  };
  var ORDEM_GERAL = ["governo", "maioria", "minoria", "oposicao", "bancada"];
  function valorLid(e) {
    return e.orientacao ? '<b class="lid-val">' + V.orientacao(e.orientacao) + "</b>" : '<span class="lid-val sem">' + EP.tr("não orientou", "no orientation") + "</span>";
  }
  function liderancasHtml(d) {
    var ori = d.orientacoes || [];
    if (!ori.length) return "";
    var gerais = ori.filter(function (e) { return GERAIS[e.tipo]; }).sort(function (a, b) { return ORDEM_GERAL.indexOf(a.tipo) - ORDEM_GERAL.indexOf(b.tipo); });
    var outras = ori.filter(function (e) { return !GERAIS[e.tipo]; });
    var TIPO = { partido: EP.tr("partido", "party"), federacao: EP.tr("federação", "federation"), bloco: EP.tr("bloco", "bloc") };
    return '<section class="miolo bloco" id="orientacoes" aria-labelledby="t-lid">' +
      cab("📣", "t-lid", EP.tr("O que cada liderança orientou", "What each leadership asked for"),
        EP.tr("A lista completa, do jeito que a " + (casa === "senado" ? "Casa" : "Câmara") + " publicou.", "The full list, as published by the " + (casa === "senado" ? "Senate" : "Chamber") + ".")) +
      (gerais.length ? '<h3 class="lid-grupo">' + EP.tr("Governo e grupos da Casa", "Government and groups in the house") + '</h3><ul class="lid-lista">' + gerais.map(function (e) {
        var g = GERAIS[e.tipo];
        return '<li><span class="lid-topo"><span class="lid-nome">' + esc(EP.tr(g[0], g[1])) + "</span>" + valorLid(e) + "</span><small>" + esc(EP.tr(g[2], g[3])) + "</small></li>";
      }).join("") + "</ul>" : "") +
      (outras.length ? '<h3 class="lid-grupo">' + EP.tr("Partidos, federações e blocos", "Parties, federations and blocs") + '</h3><ul class="lid-lista">' + outras.map(function (e) {
        var ps = (e.partidos || []).map(function (p) { return EP.pt(esc(nomePartido(p))); });
        return '<li><span class="lid-topo"><span class="lid-nome">' + EP.pt(esc(e.lideranca)) + "</span>" + valorLid(e) + "</span><small>" + esc(TIPO[e.tipo] || "") +
          (e.tipo !== "partido" && ps.length ? " · " + EP.tr("partidos que o nome mostra: ", "parties shown in the name: ") + ps.join(", ") : "") + "</small></li>";
      }).join("") + "</ul>" : "") +
      '<p class="abrev">' + EP.tr(
        "“Bl” quer dizer bloco: partidos que se juntam e passam a ter um líder só. O nome do bloco vem abreviado do jeito que a Câmara publica (às vezes cortado com “...”, e aí não dá para saber todos os partidos dele). “Fdr” quer dizer federação: partidos que se unem para agir como se fossem um só, por pelo menos 4 anos. “Liberado”: o líder deixou cada um votar como quiser" + (casa === "senado" ? " (o Senado escreve “livre”)." : "."),
        "“Bl” means bloc: parties that join together under a single leader. The bloc's name is abbreviated the way the Chamber publishes it (sometimes cut off with “...”, and then it is not possible to know all of its parties). “Fdr” means federation: parties that unite to act as a single one for at least 4 years. “Free vote”: the leader let each member vote as they wished.") + "</p></section>";
  }

  // ---------------------------------------------------------------- quem votou o quê
  function quemHtml(d) {
    return '<section class="miolo bloco" id="quem" aria-labelledby="t-quem">' +
      cab("👥", "t-quem", EP.tr("Quem votou o quê", "Who voted for what"),
        casa === "camara" ? EP.tr("Todos que registraram voto, em ordem alfabética. Toque numa pessoa para ver a página dela.", "Everyone who registered a vote, in alphabetical order. Tap a person to see their page.") :
          EP.tr("Os 81 senadores da época, em ordem alfabética, com o voto ou o motivo de não terem votado. Toque numa pessoa para ver a página dela.",
            "The 81 senators at the time, in alphabetical order, with their vote or the reason they did not vote. Tap a person to see their page.")) +
      '<div class="filtros-vot quatro" role="search" aria-label="' + EP.tr("Filtrar quem votou", "Filter who voted") + '">' +
      '<div class="f-busca"><label for="q-nome">' + EP.tr("Procurar pelo nome", "Search by name") + '</label><div class="busca"><input type="search" id="q-nome" autocomplete="off" aria-controls="lista-quem" placeholder="' +
      EP.tr("Digite um nome", "Type a name") + '"></div></div>' +
      '<div><label for="q-voto">' + EP.tr("Voto", "Vote") + '</label><select id="q-voto"></select></div>' +
      '<div><label for="q-partido">' + EP.tr("Partido", "Party") + '</label><select id="q-partido"></select></div>' +
      '<div><label for="q-uf">' + EP.tr("Estado", "State") + '</label><select id="q-uf"></select></div></div>' +
      '<p class="contagem" id="contagem-quem" aria-live="polite"></p><div class="grade-pessoas" id="lista-quem"></div><div class="mais-lista" id="mais-quem"></div></section>';
  }
  function cartaoVoto(v, focavel) {
    var pid = v[0], nome = v[1] || "", partido = v[2], uf = v[3], m = FOTOS[pid], vt = D.voto(v[4]);
    var linha2 = [partido ? nomePartido(partido) : "", uf].filter(Boolean).join(" · ");
    var corpo = EP.av(m && m.foto, nome) + "<b>" + esc(nome) + "</b>" + (linha2 ? "<small>" + esc(linha2) + "</small>" : "") +
      '<span class="voto-chip" style="--cv:' + (V.COR[vt.cat] || V.COR.Outro) + '"><span class="sr">' + EP.tr("Voto: ", "Vote: ") + "</span>" + esc(vt.curto) + "</span>" +
      (vt.cat === "Outro" && vt.longo && vt.longo !== vt.curto ? "<small>" + esc(vt.longo) + "</small>" : "");
    if (m) return '<a class="pessoa-card voto-card" href="pessoa.html?id=' + encodeURIComponent(pid) + '">' + corpo + "</a>";
    return '<div class="pessoa-card voto-card fora"' + (focavel ? ' tabindex="-1"' : "") + ">" + corpo + '<small class="fora-txt">' +
      EP.tr("Sem página aqui: não está em exercício hoje", "No page here: not serving today") + "</small></div>";
  }
  function filtrados() {
    var q = EP.norm(filtro.q);
    return DADO.votos.filter(function (v) {
      return (!filtro.voto || V.catVoto(v[4]) === filtro.voto) && (!filtro.partido || (v[2] || SEM) === filtro.partido) &&
        (!filtro.uf || v[3] === filtro.uf) && (!q || EP.norm(v[1]).indexOf(q) > -1);
    });
  }
  function desenhaQuem(focarDe) {
    var l = filtrados(), vis = l.slice(0, mostrando), el = document.getElementById("lista-quem");
    el.innerHTML = vis.map(function (v, k) { return cartaoVoto(v, focarDe != null && k === focarDe); }).join("") ||
      '<div class="vazio" style="grid-column:1/-1"><span class="grande" aria-hidden="true">🤷</span>' + EP.tr("Ninguém encontrado com esses filtros.", "No one found with these filters.") + "</div>";
    var tot = DADO.votos.length;
    var txt = l.length === tot ? EP.tr("Mostrando " + EP.num(vis.length) + " de " + EP.num(tot) + ", em ordem alfabética.", "Showing " + EP.num(vis.length) + " of " + EP.num(tot) + ", in alphabetical order.") :
      EP.tr("Mostrando " + EP.num(vis.length) + " de " + EP.num(l.length) + " encontrados (de " + EP.num(tot) + "), em ordem alfabética.",
        "Showing " + EP.num(vis.length) + " of " + EP.num(l.length) + " found (out of " + EP.num(tot) + "), in alphabetical order.");
    var c = document.getElementById("contagem-quem");
    if (c.textContent !== txt) c.textContent = txt;
    var resta = l.length - vis.length;
    document.getElementById("mais-quem").innerHTML = resta > 0 ? '<button type="button" class="btn claro" id="ver-mais-quem">' +
      EP.tr("Mostrar mais " + Math.min(LOTE, resta), "Show " + Math.min(LOTE, resta) + " more") + ' <span aria-hidden="true">▾</span></button>' : "";
    // depois de "Mostrar mais", o foco vai para a primeira pessoa nova
    if (focarDe != null && el.children[focarDe]) el.children[focarDe].focus();
  }
  function ligaQuem(d) {
    var cont = { voto: {}, partido: {}, uf: {} };
    d.votos.forEach(function (v) {
      var c = V.catVoto(v[4]), p = v[2] || SEM;
      cont.voto[c] = (cont.voto[c] || 0) + 1;
      cont.partido[p] = (cont.partido[p] || 0) + 1;
      if (v[3]) cont.uf[v[3]] = (cont.uf[v[3]] || 0) + 1;
    });
    function opcoes(sel, l) {
      sel.innerHTML = l.map(function (o) { return '<option value="' + esc(o[0]) + '"' + (o[2] ? ' lang="pt-BR"' : "") + (o[3] ? ' data-busca="' + esc(o[3]) + '"' : "") + ">" + esc(o[1]) + "</option>"; }).join("");
    }
    var sv = document.getElementById("q-voto"), sp = document.getElementById("q-partido"), su = document.getElementById("q-uf");
    opcoes(sv, [["", EP.tr("Todos", "All") + " (" + EP.num(d.votos.length) + ")"]].concat(V.CATS_VOTO.filter(function (k) { return cont.voto[k]; }).map(function (k) {
      return [k, D.nomeVoto(k) + " (" + EP.num(cont.voto[k]) + ")"];
    })));
    opcoes(sp, [["", EP.tr("Todos os partidos", "All parties")]].concat(Object.keys(cont.partido).sort(function (a, b) { return EP.norm(a).localeCompare(EP.norm(b)); }).map(function (p) {
      return [p, nomePartido(p) + " (" + EP.num(cont.partido[p]) + ")", EP.en && p !== SEM];
    })));
    opcoes(su, [["", EP.tr("Todos os estados", "All states")]].concat(Object.keys(cont.uf).sort(function (a, b) { return EP.norm(EP.UFS[a] || a).localeCompare(EP.norm(EP.UFS[b] || b)); }).map(function (u) {
      return [u, (EP.UFS[u] || u) + " (" + EP.num(cont.uf[u]) + ")", false, u];
    })));
    [[sv, "voto"], [sp, "partido"], [su, "uf"]].forEach(function (x) {
      EP.comboSelect(x[0], { placeholder: EP.tr("Digite para procurar…", "Type to search…") });
      x[0].addEventListener("change", function () { filtro[x[1]] = x[0].value; mostrando = LOTE; desenhaQuem(); });
    });
    document.getElementById("q-nome").addEventListener("input", function (e) {
      clearTimeout(tBusca);
      tBusca = setTimeout(function () { filtro.q = e.target.value; mostrando = LOTE; desenhaQuem(); }, 200);
    });
    document.getElementById("mais-quem").addEventListener("click", function (e) {
      if (!e.target.closest("#ver-mais-quem")) return;
      var de = mostrando;
      mostrando += LOTE;
      desenhaQuem(de);
    });
    desenhaQuem();
    // fotos de quem está no cargo hoje (e só elas têm página no site)
    EP.json("dados/" + casa + ".json").then(function (lst) {
      (lst.membros || []).forEach(function (m) { FOTOS[m.id] = m; });
      desenhaQuem();
    }).catch(function () {});
  }

  // ---------------------------------------------------------------- fontes
  function fontesHtml(d) {
    var q = d.quorum, l = (d.fontes || []).concat(V.cat(d.categoria).fontes);
    if (q) l = l.concat(q.regra === "maioria" ? V.F.maioria[casa] : V.F[q.regra] || []);
    if ((d.orientacoes || []).length) l = l.concat(V.F.orientacao);
    l = l.concat(V.F.nominal);
    var vistos = {};
    l = l.filter(function (f) { var k = f.url + "|" + f.titulo; if (vistos[k]) return false; vistos[k] = 1; return true; });
    return '<section class="miolo bloco" id="fontes" aria-labelledby="t-fontes">' + cab("📚", "t-fontes", EP.tr("Todas as fontes desta página", "All the sources on this page")) +
      EP.fontesHtml(l) + (d.atualizado ? '<p class="muted" style="margin-top:10px">' + EP.tr("Dados atualizados em ", "Data updated on ") + EP.data(d.atualizado) + ".</p>" : "") + "</section>";
  }

  // ---------------------------------------------------------------- montar
  function render(d) {
    DADO = d;
    d.votos = d.votos || [];
    d.placar = d.placar || { "Sim": 0, "Não": 0, "Abstenção": 0, "Obstrução": 0, "Outro": 0, total: d.votos.length };
    var t = document.querySelector("title"), quando = EP.data(d.data);
    if (t) t.removeAttribute("data-en");
    document.title = EP.tr("Votação ", "Vote on ") + titulo(d) + " (" + quando + ", " + V.casaCurta(casa) + ")" + EP.tr(" | Entenda Política", " | Understand Politics");
    var m = document.querySelector('meta[name="description"]');
    if (m) {
      m.removeAttribute("data-en-content");
      m.setAttribute("content", EP.tr("Como votou cada " + (casa === "senado" ? "senador" : "deputado") + " na votação de " + quando + " sobre " + titulo(d) + ": o resultado, os partidos e as orientações. Tudo com fonte.",
        "How each " + (casa === "senado" ? "senator" : "deputy") + " voted on " + quando + " on " + titulo(d) + ": the result, the parties and the orientations. Everything with sources."));
    }
    var o = document.getElementById("onde");
    if (o) { o.removeAttribute("data-en"); o.textContent = EP.tr("Votação: ", "Vote: ") + titulo(d); }
    raiz.innerHTML = heroHtml(d) + oqueHtml(d) + resultadoHtml(d) + partidosHtml(d) + liderancasHtml(d) + quemHtml(d) + fontesHtml(d);
    ligaQuem(d);
    // o plenário enche (cadeira por cadeira) quando aparece na tela
    var plen = raiz.querySelector(".plen-voto .plenario");
    if (plen) {
      if ("IntersectionObserver" in window && !EP.reduzido) {
        var io = new IntersectionObserver(function (ents) {
          if (ents.some(function (x) { return x.isIntersecting; })) { io.disconnect(); setTimeout(function () { plen.classList.add("cheio"); }, 200); }
        }, { threshold: 0.2 });
        io.observe(plen);
      } else plen.classList.add("cheio");
    }
    EP.revelar(raiz);
  }
  function erro(tit, txt) {
    raiz.innerHTML = '<div class="miolo vazio"><span class="grande" aria-hidden="true">🔎</span><h1>' + tit + "</h1><p>" + txt + "</p>" +
      '<p><a class="btn" href="votacoes.html">' + EP.tr("Ver todas as votações", "See all the votes") + '</a> <a class="btn claro" href="brasil.html">' +
      EP.tr("Ver a política do Brasil", "See Brazil's politics") + "</a></p></div>";
  }
  if (!/^(camara|senado)$/.test(casa) || !/^\d+(-\d+)?$/.test(id)) {
    erro(EP.tr("Faltou dizer qual votação", "No vote was chosen"), EP.tr("Volte e escolha uma votação na lista.", "Go back and choose a vote from the list."));
    return;
  }
  EP.json("dados/votacoes/" + casa + "/" + id + ".json").then(render).catch(function (err) {
    if (window.console && err && !/^\d{3} /.test(err.message || "")) console.warn(err);
    erro(EP.tr("Não encontramos essa votação", "We could not find this vote"),
      EP.tr("Pode ser que o endereço esteja errado, ou que os dados ainda estejam sendo atualizados.", "The address may be wrong, or the data may still be being updated."));
  });
})();
