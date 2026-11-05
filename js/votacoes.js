/* Votações nominais do Plenário (Câmara e Senado).
   - EP.VOT: ajudas comuns (cores dos votos, categorias, fontes das regras, cartão de uma votação, placar pequeno).
   - votacoes.html: a lista de todas as votações, com filtros (Casa, ano, categoria, resultado) e busca.
   - brasil.html: o bloco "Como o Congresso votou" (#votos-recentes), com as 3 votações mais novas do texto principal.
   Dados: dados/votacoes/camara.json e dados/votacoes/senado.json (catálogos); cada votação tem um arquivo próprio em
   dados/votacoes/<casa>/<id>.json, aberto por votacao.html (js/votacao.js). */
(function () {
  "use strict";
  var EP = window.EP, D = EP.trd, esc = EP.esc;
  var V = (EP.VOT = EP.VOT || {});

  // ---------------------------------------------------------------- cores e nomes
  V.COR = { "Sim": "#1f3a5f", "Não": "#9a4f00", "Abstenção": "#5b6573", "Obstrução": "#6a3fb0", "Outro": "#6b5a33" };
  V.CATS_VOTO = ["Sim", "Não", "Abstenção", "Obstrução", "Outro"];
  V.TOTAL = { camara: 513, senado: 81 };
  V.casaNome = function (c) { return c === "senado" ? EP.tr("Senado Federal", "Federal Senate") : EP.tr("Câmara dos Deputados", "Chamber of Deputies"); };
  V.casaCurta = function (c) { return c === "senado" ? EP.tr("Senado", "Senate") : EP.tr("Câmara", "Chamber"); };
  // "20h56" / "8:56 PM"
  V.hora = function (h) {
    var m = /^(\d{2}):(\d{2})/.exec(h || "");
    if (!m) return "";
    if (!EP.en) return +m[1] + "h" + m[2];
    var hh = +m[1] % 12 || 12;
    return hh + ":" + m[2] + (+m[1] < 12 ? " AM" : " PM");
  };
  V.id = function (chave) { return String(chave || "").split(":").pop(); };
  // um texto oficial longo, cortado numa palavra (o texto inteiro fica no "Saber mais")
  V.curto = function (t, n) { t = String(t || ""); return t.length > n ? t.slice(0, n - 10).replace(/\s+\S*$/, "") + "…" : t; };
  V.url = function (casa, chave) { return "votacao.html?casa=" + casa + "&id=" + encodeURIComponent(V.id(chave)); };
  // o caminho das páginas de votações (site-d-r16): elas fazem parte de "Como votaram", na página do Brasil
  // (Início › A política do Brasil › Como votaram › Todas as votações [› a votação])
  V.trilha = function (fim) {
    if (!EP.trilha) return;
    var todas = EP.tr("Todas as votações", "All the votes");
    EP.trilha([{ t: EP.tr("A política do Brasil", "Brazil's politics"), href: "brasil.html" }, { t: EP.tr("Como votaram", "How Congress voted"), href: "brasil.html#votacoes" },
      fim ? { t: todas, href: "votacoes.html" } : { t: todas }].concat(fim ? [fim] : []));
  };
  // categoria do voto de uma pessoa (Senado: códigos como "NCom", "P-OD")
  V.catVoto = function (v) {
    if (v === "Sim" || v === "Não" || v === "Abstenção") return v;
    return /^(Obstrução|P-OD|OB)$/.test(v || "") ? "Obstrução" : "Outro";
  };
  V.orientacao = function (o) {
    var t = { "Sim": ["Sim", "Yes"], "Não": ["Não", "No"], "Abstenção": ["Abstenção", "Abstain"], "Obstrução": ["Obstrução", "Obstruction"],
      "Liberado": ["Liberado", "Free vote"] }[o];
    return t ? esc(EP.tr(t[0], t[1])) : D.ptHtml(o, true);
  };
  V.partido = function (p) { return !p ? "" : /^sem partido$/i.test(p) ? esc(EP.tr("Sem partido", "No party")) : EP.pt(esc(p)); };

  // ---------------------------------------------------------------- fontes das regras (Constituição e Regimentos)
  var CF = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm";
  var RICD = "https://www2.camara.leg.br/legin/fed/rescad/1989/resolucaodacamaradosdeputados-17-21-setembro-1989-320110-normaatualizada-pl.html";
  var RISF = "https://www25.senado.leg.br/web/atividade/regimento-interno";
  function cf(art, sobre) { return { veiculo: "Planalto", titulo: "Constituição Federal, " + art + " (" + sobre + ")", url: CF, data: "1988-10-05" }; }
  function ricd(art, sobre) { return { veiculo: "Câmara dos Deputados", titulo: "Regimento Interno da Câmara dos Deputados, " + art + " (" + sobre + ")", url: RICD, data: "1989-09-21" }; }
  function risf(art, sobre) { return { veiculo: "Senado Federal", titulo: "Regimento Interno do Senado Federal, " + art + " (" + sobre + ")", url: RISF, data: "1970-11-27" }; }
  V.F = {
    nominal: [ricd("arts. 184 a 188", "votação simbólica, nominal e secreta"), risf("arts. 289 a 294", "votação ostensiva e secreta; processos simbólico e nominal")],
    orientacao: [ricd("art. 10, IV", "o líder encaminha a votação para orientar a sua bancada"), ricd("arts. 11 a 13", "liderança do Governo e da Minoria, blocos e Maioria"),
      risf("arts. 61 a 66-C", "blocos, Maioria, Minoria, Governo, Oposição e bancada feminina"),
      { veiculo: "Planalto", titulo: "Lei nº 9.096/1995 (partidos políticos), art. 11-A: federação de partidos (incluído pela Lei nº 14.208/2021)",
        url: "https://www.planalto.gov.br/ccivil_03/leis/l9096.htm", data: "2021-09-28" }],
    pec: [cf("art. 60, § 2º", "PEC: dois turnos em cada Casa, com três quintos dos votos")],
    plp: [cf("art. 69", "lei complementar: maioria absoluta")],
    urgencia155: [ricd("art. 155", "urgência aprovada pela maioria absoluta dos deputados")],
    maioria: { camara: [cf("art. 47", "maioria dos votos, com a maioria absoluta presente"), ricd("art. 183", "maioria de votos, presente a maioria absoluta")],
      senado: [cf("art. 47", "maioria dos votos, com a maioria absoluta presente"), risf("art. 288", "maioria de votos, presente a maioria absoluta")] }
  };

  // ---------------------------------------------------------------- categorias (classificadas por scripts/votacoes.py a partir da descrição oficial)
  V.CAT = {
    principal: { ic: "📜", nome: ["Texto principal", "Main text"], curto: ["Texto principal", "Main text"],
      explica: ["Votação do texto inteiro: o projeto, a PEC (que tem duas votações, os “turnos”), a medida provisória ou um texto novo que troca o original inteiro (o “substitutivo”).",
        "A vote on the whole text: the bill, the constitutional amendment (which is voted twice, in two “rounds”), the provisional measure, or a new text that replaces the whole original one (the “substitute”)."],
      fontes: [ricd("arts. 118, § 4º, e 195", "substitutivo e redação final"), risf("art. 300", "na votação, primeiro vem o projeto"), cf("art. 60, § 2º", "PEC: dois turnos")] },
    mudanca: { ic: "✏️", nome: ["Mudança no texto", "Change to the text"], curto: ["Mudanças no texto", "Changes to the text"],
      explica: ["Votação de uma mudança numa parte do texto: uma emenda (uma sugestão de mudança) ou um destaque (um pedaço do texto votado sozinho, para decidir se fica ou sai).",
        "A vote on changing one part of the text: an amendment (a suggested change) or a separate vote on one piece of the text, to decide whether it stays or goes."],
      fontes: [ricd("arts. 118 e 161", "emendas e destaques"), risf("arts. 312 e 314", "destaques")] },
    procedimento: { ic: "⏱️", nome: ["Procedimento", "Procedure"], curto: ["Procedimentos", "Procedures"],
      explica: ["Votação sobre o caminho, e não sobre o texto: pedidos para votar com urgência, adiar, tirar da pauta, encerrar a discussão ou mudar a ordem da votação.",
        "A vote on the process, not on the text: requests to vote urgently, postpone, take the item off the agenda, end the debate or change the voting order."],
      fontes: [ricd("arts. 117 e 155", "requerimentos e urgência"), risf("arts. 279 e 336", "adiamento e urgência")] },
    outra: { ic: "🗂️", nome: ["Outra decisão", "Other decision"], curto: ["Outras decisões", "Other decisions"],
      explica: ["Outras decisões, como dizer se uma medida provisória é mesmo urgente e importante para ser analisada, ou casos sobre o mandato de um parlamentar.",
        "Other decisions, such as whether a provisional measure really is urgent and important enough to be considered, or cases about a member's term in office."],
      fontes: [cf("art. 62, § 5º", "medida provisória: relevância e urgência"), cf("art. 53, §§ 2º e 3º", "prisão de parlamentar e sustação de ação penal")] }
  };
  V.ORDEM_CAT = ["principal", "mudanca", "procedimento", "outra"];
  V.cat = function (c) { return V.CAT[c] || V.CAT.outra; };
  V.chipCat = function (c) {
    var x = V.cat(c);
    return '<span class="chip-cat"><span aria-hidden="true">' + x.ic + " </span>" + esc(EP.tr(x.nome[0], x.nome[1])) + "</span>";
  };
  // resultado em tons neutros (os mesmos carimbos das propostas: ☑️ aprovada, ✖️ rejeitada). Nos destaques da Câmara
  // ("Mantido o texto." / "Suprimido o texto.") a Câmara não preenche o resultado: ele está escrito na própria descrição.
  V.chipRes = function (r, desc) {
    var n = EP.norm(r);
    if (/^aprovad/.test(n)) return EP.carimbo("aprovada", EP.tr("Aprovado", "Approved"));
    if (/^rejeitad/.test(n)) return EP.carimbo("rejeitada", EP.tr("Rejeitado", "Rejected"));
    if (!r && /^mantid[oa] o texto/i.test(desc || "")) return '<span class="carimbo s-aprovada"><span aria-hidden="true">📌 </span>' + EP.tr("Texto mantido", "Text kept") + "</span>";
    if (!r && /^suprimid[oa] o texto/i.test(desc || "")) return '<span class="carimbo s-rejeitada"><span aria-hidden="true">✂️ </span>' + EP.tr("Texto retirado", "Text removed") + "</span>";
    return EP.carimbo("outra", r ? (EP.en ? "Result: " : "Resultado: ") + r : EP.tr("Resultado não informado", "Result not reported"));
  };

  // ---------------------------------------------------------------- placar pequeno e cartão de uma votação
  V.miniPlacar = function (p) {
    if (!p || !p.total) return "";
    var ks = V.CATS_VOTO.filter(function (k) { return p[k]; });
    return '<div class="mini-placar"><span class="mp-barra" aria-hidden="true">' + ks.map(function (k) {
      return '<i style="width:' + (100 * p[k] / p.total).toFixed(2) + "%;background:" + V.COR[k] + '"></i>';
    }).join("") + '</span><span class="mp-txt">' + ks.map(function (k) {
      return '<span><i class="vot-q" style="background:' + V.COR[k] + '" aria-hidden="true"></i>' + esc(D.nomeVoto(k)) + " <b>" + EP.num(p[k]) + "</b></span>";
    }).join("") + "</span></div>";
  };
  V.cartao = function (v, o) {
    o = o || {};
    var h = "h" + (o.nivel || 3), desc = v.descricao || "";
    var curta = desc.length > 240 ? desc.slice(0, 230).replace(/\s+\S*$/, "") + "…" : desc;
    var quando = EP.data(v.data) + (v.hora ? " · " + V.hora(v.hora) : "");
    return '<li class="vot-card">' +
      '<p class="vot-topo"><span class="chip neutro chip-casa"><span aria-hidden="true">🏛️ </span>' + esc(V.casaCurta(v.casa)) + "</span>" +
      '<span class="vot-data"><span class="sr">' + EP.tr("Data: ", "Date: ") + "</span>" + esc(quando) + "</span></p>" +
      "<" + h + ' class="vot-tit"><a href="' + V.url(v.casa, v.chave) + '">' + esc(v.proposta || EP.tr("Votação no Plenário", "Vote in the full house")) +
      '<span class="sr">, ' + esc(EP.tr("votação de ", "vote of ") + quando + " (" + V.casaCurta(v.casa) + ")") + "</span></a></" + h + ">" +
      '<p class="vot-chips">' + V.chipCat(v.categoria) + " " + V.chipRes(v.resultado, v.descricao) + "</p>" +
      (curta ? '<p class="vot-desc">' + EP.pt(esc(curta)) + "</p>" : "") + V.miniPlacar(v.placar) +
      '<span class="vot-ver" aria-hidden="true">' + EP.tr("Ver como cada um votou ›", "See how each one voted ›") + "</span></li>";
  };

  // ---------------------------------------------------------------- as duas Casas juntas, da mais nova para a mais antiga
  V.carrega = function () {
    if (!V._todas) {
      V._todas = Promise.all(["camara", "senado"].map(function (c) {
        return EP.json("dados/votacoes/" + c + ".json").catch(function () { return null; });
      })).then(function (r) {
        if (!r[0] && !r[1]) throw new Error("sem votações");
        var l = [];
        [["camara", r[0]], ["senado", r[1]]].forEach(function (x) {
          var vs = (x[1] || {}).votacoes || {}, k = 0;
          Object.keys(vs).forEach(function (chave) { l.push(Object.assign({ casa: x[0], chave: chave, ordem: k++ }, vs[chave])); });
        });
        l.sort(function (a, b) {
          return (b.data || "").localeCompare(a.data || "") || (b.hora || "").localeCompare(a.hora || "") || a.casa.localeCompare(b.casa) || a.ordem - b.ordem;
        });
        return { lista: l, camara: r[0], senado: r[1] };
      });
      V._todas.catch(function () { V._todas = null; });
    }
    return V._todas;
  };

  // ---------------------------------------------------------------- página do Brasil: "Como o Congresso votou"
  // site-d-r14 (protótipo D): cada votação é um cartão com o placar grande (Sim × Não e os outros, escritos, e a barra, que é só
  // desenho), as mais novas primeiro (uma por proposta, só o texto principal). Tocar no cartão abre a gaveta com o voto de cada
  // partido (uma tabela, em ordem alfabética) e "Ver a votação inteira" (votacao.html); o endereço guarda a gaveta
  // (?ver=vot:camara:2236186-60). Filtro pela Casa e "Mostrar mais".
  var REC = { lista: [], n: 6, casa: "" };
  function cartaoD(v) {
    var desc = v.descricao || "", curta = desc.length > 150 ? desc.slice(0, 140).replace(/\s+\S*$/, "") + "…" : desc;
    var quando = EP.data(v.data);
    return '<li class="vot-card d-vot-li"><button type="button" class="d-vot" data-vot="' + esc(v.casa + ":" + V.id(v.chave)) + '" aria-haspopup="dialog">' +
      '<span class="d-vot-cab"><span class="chip neutro chip-casa"><span aria-hidden="true">🏛️ </span>' + esc(V.casaCurta(v.casa)) + '</span><time datetime="' + esc(v.data || "") + '">' + esc(quando) + "</time></span>" +
      '<b class="vot-tit">' + esc(v.proposta || EP.tr("Votação no Plenário", "Vote in the full house")) + '<span class="sr">, ' + esc(EP.tr("votação de ", "vote of ") + quando + " (" + V.casaCurta(v.casa) + ")") + "</span></b>" +
      '<span class="vot-chips">' + V.chipCat(v.categoria) + " " + V.chipRes(v.resultado, v.descricao) + "</span>" +
      (EP.d ? EP.d.placar(v.placar) : V.miniPlacar(v.placar)) +
      (curta ? '<span class="d-vot-desc">' + EP.pt(esc(curta)) + "</span>" : "") +
      '<span class="d-ver">' + EP.tr("Ver como cada pessoa votou", "See how each person voted") + ' <span aria-hidden="true">→</span></span></button></li>';
  }
  function desenhaRecentes(el, focarDe) {
    var l = REC.lista.filter(function (v) { return !REC.casa || v.casa === REC.casa; }), vis = l.slice(0, REC.n);
    var ul = el.querySelector(".lista-vot");
    ul.innerHTML = vis.map(cartaoD).join("");
    var c = el.querySelector(".d-vot-conta"), t = EP.tr("Mostrando " + EP.num(vis.length) + " de " + EP.num(l.length) + (l.length === 1 ? " votação" : " votações") + ", da mais nova para a mais antiga.",
      "Showing " + EP.num(vis.length) + " of " + EP.num(l.length) + (l.length === 1 ? " vote" : " votes") + ", newest first.");
    if (c.textContent !== t) c.textContent = t;
    el.querySelector(".d-vot-mais").innerHTML = l.length > vis.length ? '<button type="button" class="btn claro" data-vot-mais>' +
      esc(EP.tr("Mostrar mais " + Math.min(6, l.length - vis.length), "Show " + Math.min(6, l.length - vis.length) + " more")) + ' <span aria-hidden="true">▾</span></button>' : "";
    if (focarDe != null) { var b = ul.querySelectorAll(".d-vot")[focarDe]; if (b) b.focus(); }
  }
  V.recentes = function (el, n) {
    if (!el) return;
    V.carrega().then(function (r) {
      // uma votação por proposta (a mais nova): os dois turnos de uma PEC não ocupam dois lugares
      var vistos = {}, l = r.lista.filter(function (v) {
        var k = v.casa + "|" + (v.propostaId || v.proposta || v.chave);
        if (v.categoria !== "principal" || vistos[k]) return false;
        vistos[k] = 1;
        return true;
      });
      if (!l.length) throw new Error("vazio");
      REC.lista = l;
      REC.n = n || 6;
      el.innerHTML = '<div class="pd-seg d-seg" role="group" aria-label="' + EP.tr("Mostrar as votações de", "Show the votes of") + '">' +
        [["", EP.tr("Câmara e Senado", "Chamber and Senate")], ["camara", EP.tr("Câmara", "Chamber")], ["senado", EP.tr("Senado", "Senate")]].map(function (x) {
          return '<button type="button" class="btn claro peq" data-vot-casa="' + x[0] + '" aria-pressed="' + (x[0] === REC.casa) + '">' + esc(x[1]) + "</button>";
        }).join("") + '</div><p class="contagem d-vot-conta" role="status"></p><ul class="lista-vot d-vots"></ul><div class="mais-lista d-vot-mais"></div>' +
        (EP.d ? EP.d.saiba("<p>" + EP.tr("São as votações sobre o texto inteiro de cada proposta (uma de cada), da mais nova para a mais antiga. Votar Sim não é bom e votar Não não é ruim: depende do que estava em votação.",
          "These are the votes on the whole text of each proposal (one per proposal), newest first. Voting Yes is not good and voting No is not bad: it depends on what was being voted on.") + "</p>") : "") +
        '<p class="gv-fonte">' + EP.botaoFontes([].concat((r.camara || {}).fonte || [], (r.senado || {}).fonte || [])) + "</p>";
      desenhaRecentes(el);
      if (!el._ligado) {
        el._ligado = true;
        el.addEventListener("click", function (e) {
          var s = e.target.closest("[data-vot-casa]");
          if (s) {
            REC.casa = s.getAttribute("data-vot-casa");
            REC.n = n || 6;
            [].forEach.call(el.querySelectorAll("[data-vot-casa]"), function (x) { x.setAttribute("aria-pressed", String(x === s)); });
            desenhaRecentes(el);
            return;
          }
          if (e.target.closest("[data-vot-mais]")) { var de = REC.n; REC.n += 6; desenhaRecentes(el, de); return; }
          var b = e.target.closest("[data-vot]");
          if (b) V.abreVot(b.getAttribute("data-vot"), b);
        });
      }
    }).catch(function () {
      el.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">⚠️</span>' +
        EP.tr("Não foi possível carregar as votações agora. Tente de novo daqui a pouco.", "The votes could not be loaded right now. Please try again in a little while.") + "</div>";
    });
  };
  // ---------------------------------------------------------------- uma votação no modal (site-d-r16, pedido do Lucas de 5/11)
  // A votação (do Congresso, de uma Assembleia ou de uma Câmara Municipal) abre num modal grande, no meio da tela (no celular,
  // a tela cheia): o resultado e o placar; "📜 Do que se trata" (a explicação simples feita por IA, quando existe, com o texto
  // oficial num bloco que abre; sem ela, o texto oficial inteiro; o que é aquele tipo de proposta; o tipo de votação; os links
  // oficiais); e duas abas: "Pessoas" (o plenário pintado pelo voto e as pessoas agrupadas pelo voto) e "Partidos" (uma barra
  // por partido, em ordem alfabética, com os números e a orientação publicada; tocar num partido mostra as pessoas dele).
  var CF_URL = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm";
  function cfT(art, pt, en) {
    var f = { veiculo: "Planalto", titulo: EP.tr("Constituição Federal, " + art + " (" + pt + ")", "Federal Constitution, " + art + " (" + en + ")"), url: CF_URL, data: "1988-10-05" };
    if (EP.en) f.lang = "en";
    return f;
  }
  var GLOSSARIO = { veiculo: "Congresso Nacional", titulo: EP.tr("Glossário Legislativo", "Legislative Glossary (in Portuguese)"), url: "https://www.congressonacional.leg.br/legislacao-e-publicacoes/glossario-legislativo", data: null };
  // o que é cada tipo de proposta, em palavras simples (as mesmas do glossário do Entenda, parada 6). nivel: "federal",
  // "estadual" ou "municipal" (quem assina ou veta: o presidente, o governador ou o prefeito)
  V.tipoProposta = function (sigla, texto, casa) {
    var t = (/^\s*([A-Za-zÇç.*]+)/.exec(sigla || "") || [])[1] || "";
    t = t.replace(/\./g, "").toUpperCase();
    var d = EP.norm((texto || "").slice(0, 160)), nivel = casa === "camara" || casa === "senado" ? "federal" : casa;
    var chefe = nivel === "federal" ? ["o presidente", "the President"] : nivel === "estadual" ? ["o governador", "the governor"] : ["o prefeito", "the mayor"];
    var aCasa = nivel === "federal" ? ["o Congresso", "Congress"] : nivel === "estadual" ? ["a Assembleia", "the state legislature"] : ["a Câmara Municipal", "the city council"];
    function x(k, nome, exp, fontes) { return { k: k, nome: EP.tr(nome[0], nome[1]), explica: EP.tr(exp[0], exp[1]), fontes: (fontes || []).concat([GLOSSARIO]) }; }
    if (t === "PEC" || (/emenda (a|à) constituicao|emenda constitucional/.test(d) && !/lei organica/.test(d))) {
      return nivel === "federal" ? x("pec", ["Proposta de Emenda à Constituição (PEC)", "Proposed constitutional amendment (PEC)"],
        ["Um projeto para mudar a Constituição, a lei mais importante do país. Para passar, precisa de três quintos dos votos, em dois turnos, na Câmara e no Senado.",
          "A bill to change the Constitution, the country's most important law. To pass, it needs three fifths of the votes, in two rounds, in the Chamber and in the Senate."],
        [cfT("art. 60", "emendas à Constituição", "constitutional amendments")]) :
        x("pec", ["Proposta de Emenda à Constituição do estado", "Proposed amendment to the state constitution"],
          ["Um projeto para mudar a Constituição do estado, a lei mais importante do estado.", "A bill to change the state's constitution, the most important law of the state."],
          [cfT("art. 25", "cada estado tem a sua Constituição", "each state has its own constitution")]);
    }
    if (/^(PELO|PELOM|ELO|PELOA|PEMLO)$/.test(t) || /emenda (a|à) lei organica/.test(d)) {
      return x("lo", ["Emenda à Lei Orgânica", "Amendment to the city's Organic Law"], ["Um projeto para mudar a Lei Orgânica, que é como a Constituição da cidade.",
        "A bill to change the Organic Law, which is like the city's constitution."], [cfT("art. 29", "a Lei Orgânica de cada município", "each city's Organic Law")]);
    }
    if (/^(VET|VETO|VT|VTP|VPA|VTT)$/.test(t) || /^veto\b/.test(d)) {
      return x("veto", ["Veto", "Veto"], [chefe[0].charAt(0).toUpperCase() + chefe[0].slice(1) + " não concordou com um projeto aprovado e barrou ele inteiro ou uma parte. Nesta votação, " + aCasa[0] + " decide se mantém ou derruba o veto.",
        chefe[1].charAt(0).toUpperCase() + chefe[1].slice(1) + " disagreed with a bill that was passed and blocked all or part of it. In this vote, " + aCasa[1] + " decides whether to keep or override the veto."],
      [cfT("art. 66", "sanção e veto", "signing and veto")]);
    }
    if (nivel === "federal" && /^(MPV|MP)$/.test(t)) {
      return x("mpv", ["Medida provisória", "Provisional measure"], ["Uma norma que o presidente cria em casos urgentes. Vale na hora, mas só por um tempo: o Congresso vota se ela vira lei.",
        "A rule that the President creates in urgent cases. It applies right away, but only for a while: Congress votes on whether it becomes law."], [cfT("art. 62", "medidas provisórias", "provisional measures")]);
    }
    if (t === "PLV") {
      return x("plv", ["Projeto de lei de conversão", "Conversion bill"], ["O texto de uma medida provisória com as mudanças feitas pelo Congresso, para ela virar lei.",
        "The text of a provisional measure with the changes made by Congress, so that it becomes law."], [cfT("art. 62, § 12", "projeto de lei de conversão", "conversion bill")]);
    }
    if (t === "PLP" || /^(PLCE|PLCM|PLCOM)$/.test(t) || (t === "PLC" && casa !== "senado")) {
      return x("plp", ["Projeto de lei complementar", "Complementary law bill"], ["Um tipo de lei para assuntos em que a Constituição pede mais votos: precisa da maioria absoluta (mais da metade de todos os membros da Casa).",
        "A type of law for subjects where the Constitution asks for more votes: it needs an absolute majority (more than half of all the members of the house)."], [cfT("art. 69", "lei complementar", "complementary law")]);
    }
    if (/^(PDL|PDC|PDE|PDLG|PDS)$/.test(t) || /^projeto de decreto legislativo/.test(d)) {
      return x("pdl", ["Projeto de decreto legislativo", "Legislative decree bill"], ["Uma decisão sobre assuntos que só " + aCasa[0] + " resolve, sem passar por " + chefe[0] + ".",
        "A decision on matters that only " + aCasa[1] + " decides, without going to " + chefe[1] + "."], [cfT("art. 49", "o que só o Congresso decide", "what only Congress decides")]);
    }
    if (/^(PRC|PRS|PR|PRE|PRES|PRL)$/.test(t) || /^projeto de resolucao/.test(d)) {
      return x("res", ["Projeto de resolução", "Resolution bill"], ["Uma regra sobre o funcionamento da própria Casa, ou uma homenagem que ela concede.",
        "A rule about how the house itself works, or an honor that it grants."], [cfT("art. 59", "os tipos de norma que o Legislativo vota", "the types of rules the legislature votes on")]);
    }
    if (/^(EMD|EM|EME|EMI|EMEND|EMEN|EMM|EMMD|EA|EMA|EMS|EMC|SUBS)$/.test(t) || /^emenda (modificativa|aditiva|supressiva|substitutiva|impositiva)/.test(d)) {
      return x("emenda", ["Emenda", "Amendment"], ["Uma proposta de mudança num projeto que está sendo votado.", "A proposed change to a bill that is being voted on."]);
    }
    if (/^(RF|PRED|RED)$/.test(t) || /^redacao final/.test(d)) {
      return x("rf", ["Redação final", "Final wording"], ["O texto final do projeto, já com as mudanças aprovadas, votado antes de seguir em frente.",
        "The final text of the bill, with the approved changes, voted on before it moves forward."]);
    }
    if (/^(REQ|RQS|RQ|REQS)$/.test(t)) {
      return x("req", ["Requerimento", "Request"], ["Um pedido feito à Casa, como votar com urgência ou adiar uma votação.", "A request made to the house, such as voting urgently or postponing a vote."]);
    }
    if (nivel === "federal" && t === "MSC") {
      return x("msc", ["Mensagem do presidente", "Message from the President"], ["Um documento que o presidente manda ao Congresso, por exemplo com um acordo internacional para ser aprovado.",
        "A document that the President sends to Congress, for example with an international agreement to be approved."], [cfT("art. 49, I", "acordos internacionais", "international agreements")]);
    }
    if (/^(PL|PLS|PLO|PLL|PLE|PLOE|PLOL|PLOEX|PLEX|PLOM|PLORD|PLM|PLEI|PLOPL|PLOPE|PLEO|PLLEG|PLPE|PROJ|PROLE|PLC)$/.test(t) || /^projeto de lei\b/.test(d)) {
      return x("pl", ["Projeto de lei", "Bill"], ["O texto de uma lei que ainda está sendo discutido e votado. Se for aprovado, vai para " + chefe[0] + " assinar (sancionar) ou vetar.",
        "The text of a law that is still being discussed and voted on. If it is passed, it goes to " + chefe[1] + " to sign or veto."], [cfT("arts. 61 e 66", "projetos de lei, sanção e veto", "bills, signing and veto")]);
    }
    return null;
  };
  // "📜 Do que se trata". o = { sigla, s, s_en, ementa, descricao, cat (só no Congresso), casa, urlProposta, urlVotacao, site }
  V.doQueSeTrata = function (o) {
    var s = EP.en ? o.s_en : o.s, uid = "dq" + (++vpConta);
    var ementa = o.ementa || "", desc = o.descricao || "";
    var oficial = ementa || desc, desc2 = ementa && desc && EP.norm(desc).indexOf(EP.norm(ementa).slice(0, 80)) < 0 ? desc : "";
    var tipo = V.tipoProposta(o.sigla, oficial, o.casa);
    function fora(url, txt) {
      return /^https?:\/\//.test(url || "") ? '<a href="' + esc(url) + '" target="_blank" rel="noopener" hreflang="pt-BR">' + esc(txt) + ' <span aria-hidden="true">↗</span><span class="sr"> ' +
        EP.tr("(abre em outra aba)", "(opens in a new tab)") + "</span></a>" : "";
    }
    var cat = o.cat ? V.cat(o.cat) : null;
    var links = [fora(o.urlProposta, EP.tr("Ver a proposta ", "See the proposal ") + o.site), fora(o.urlVotacao, EP.tr("Ver esta votação ", "See this vote ") + o.site)].filter(Boolean);
    return '<section class="vt-oque" aria-labelledby="' + uid + '"><h3 id="' + uid + '"><span aria-hidden="true">📜 </span>' + EP.tr("Do que se trata", "What it is about") + "</h3>" +
      (s ? '<p class="vt-simples"><span class="rot-texto">' + EP.tr("Em palavras simples (feita por IA a partir do texto oficial)", "In plain words (written by AI from the official text)") + "</span>" + esc(s) + "</p>" +
        (oficial ? '<details class="d-saiba vt-oficial"><summary><span aria-hidden="true">📄</span> ' + EP.tr("Ver o texto oficial", "See the official text") + '</summary><div class="d-saiba-corpo"><p>' + EP.pt(esc(oficial)) + "</p></div></details>" : "") :
        (oficial ? '<div class="vot-oficial vt-ementa"><span class="rot-texto">' + (ementa ? EP.tr("Texto oficial da proposta (ementa)", "Official text of the proposal (in Portuguese)") :
          EP.tr("Texto oficial do que foi votado", "Official text of what was voted on (in Portuguese)")) + "</span>" + EP.pt(esc(oficial)) + "</div>" : "")) +
      (desc2 ? '<details class="d-saiba vt-desc"><summary><span aria-hidden="true">🗳️</span> ' + EP.tr("Ver a descrição oficial desta votação", "See the official description of this vote") +
        '</summary><div class="d-saiba-corpo"><p>' + EP.pt(esc(desc2)) + "</p></div></details>" : "") +
      (tipo ? '<p class="vt-tipo"><span class="d-ic peq" aria-hidden="true">📘</span><span>' + (o.sigla ? "<b>" + EP.pt(esc(o.sigla)) + "</b> " + EP.tr("é ", "is ") : "") + "<b>" +
        esc(tipo.nome) + "</b>: " + esc(tipo.explica) + " " + EP.botaoFontes(tipo.fontes, EP.tr("De onde vem essa explicação?", "Where does this explanation come from?")) + "</span></p>" : "") +
      (cat ? '<p class="vt-tipo"><span class="d-ic peq" aria-hidden="true">' + cat.ic + "</span><span><b>" + EP.tr("Que votação foi esta: ", "What kind of vote this was: ") + esc(EP.tr(cat.nome[0], cat.nome[1])) +
        "</b>. " + esc(EP.tr(cat.explica[0], cat.explica[1])) + " " + EP.botaoFontes(cat.fontes, EP.tr("De onde vem essa explicação?", "Where does this explanation come from?")) + "</span></p>" : "") +
      (links.length ? '<p class="vot-links vt-links">' + links.join("") + "</p>" : "") + "</section>";
  };
  // "Partidos": uma barra por partido (Sim, Não, Abstenção, Obstrução, outros; as cores dos votos, iguais para todos), em ordem
  // alfabética, com os números escritos e a orientação publicada pela Casa. Tocar num partido chama o.aoTocar(partido).
  // lista = [{ partido, voto }]; o = { orient: { partido: { orientacao, lideranca, tipo } }, gente: [um, varios], aoTocar }
  V.partidosMonta = function (el, lista, o) {
    if (!el) return;
    o = o || {};
    var por = {};
    lista.forEach(function (p) {
      var k = p.partido || "Sem partido", c = V.catVoto(p.voto);
      var x = por[k] || (por[k] = { p: k, n: 0, c: {} });
      x.c[c] = (x.c[c] || 0) + 1;
      x.n++;
    });
    var l = Object.keys(por).map(function (k) { return por[k]; }).sort(function (a, b) { return EP.norm(a.p).localeCompare(EP.norm(b.p)); });
    // as colunas da tabela: só os votos que aparecem nesta votação
    var cols = V.GRUPO_ORDEM.filter(function (k) { return l.some(function (x) { return x.c[k]; }); });
    var orient = o.orient || {}, temOri = l.some(function (x) { return orient[x.p] && orient[x.p].orientacao; });
    function nome(p) { return p === "Sem partido" ? esc(EP.tr("Sem partido", "No party")) : EP.pt(esc(p)); }
    function oriTxt(x) {
      var r = orient[x.p];
      if (!r || !r.orientacao) return "";
      var de = r.tipo === "federacao" ? EP.tr("da federação", "of the federation") : r.tipo === "bloco" ? EP.tr("do bloco", "of the bloc") : EP.tr("do partido", "of the party");
      return '<span class="vt-p-ori">' + EP.tr("Orientação ", "Orientation ") + de + (r.tipo !== "partido" && r.lideranca ? " (" + EP.pt(esc(r.lideranca)) + ")" : "") + ": <b>" + V.orientacao(r.orientacao) + "</b></span>";
    }
    el.innerHTML = '<h3 class="vp-tit">' + EP.tr("Como cada partido votou", "How each party voted") + "</h3>" +
      '<p class="d-linha">' + esc(EP.tr(EP.num(l.length) + (l.length === 1 ? " partido" : " partidos") + ", em ordem alfabética. Toque num partido para ver as pessoas dele.",
        EP.num(l.length) + (l.length === 1 ? " party" : " parties") + ", in alphabetical order. Tap a party to see its members.")) + "</p>" +
      '<ul class="vt-ps">' + l.map(function (x) {
        var ks = V.GRUPO_ORDEM.filter(function (k) { return x.c[k]; });
        return '<li><button type="button" class="vt-p" data-partido="' + esc(x.p) + '"><span class="vt-p-cab"><b>' + nome(x.p) + '</b><span class="vt-p-n">' +
          esc(EP.num(x.n) + " " + (x.n === 1 ? o.gente[0] : o.gente[1])) + "</span></span>" +
          '<span class="vt-p-barra" aria-hidden="true">' + ks.map(function (k) { return '<i style="flex:' + x.c[k] + ";background:" + V.COR[k] + '"></i>'; }).join("") + "</span>" +
          '<span class="vt-p-nums">' + ks.map(function (k) { return '<span><i class="vot-q" style="background:' + V.COR[k] + '" aria-hidden="true"></i>' + esc(V.grupoNome(k)) + " <b>" + EP.num(x.c[k]) + "</b></span>"; }).join("") + "</span>" +
          oriTxt(x) + "</button></li>";
      }).join("") + "</ul>" +
      EP.d.saiba((temOri ? "<p>" + EP.tr("Orientação é o que a liderança do partido, da federação ou do bloco pediu aos seus membros antes da votação. Só aparece quando a Casa publicou. Seguir ou não a orientação não é bom nem ruim.",
        "The orientation is what the leadership of the party, federation or bloc asked its members to do before the vote. It only appears when the house published it. Following it or not is neither good nor bad.") + " " +
        EP.botaoFontes(V.F.orientacao, EP.tr("De onde vem essa regra?", "Where does this rule come from?")) + "</p>" : "") +
        "<p>" + EP.tr("A barra de cada partido mostra como as pessoas dele votaram, do começo ao fim da barra; o tamanho do partido está no número ao lado do nome.",
          "Each party's bar shows how its members voted, from one end of the bar to the other; the party's size is the number next to its name.") + "</p>" +
        '<div class="vt-tab-rola" role="region" tabindex="0" aria-label="' + esc(EP.tr("Tabela: o voto de cada partido", "Table: how each party voted")) + '">' +
        '<table class="d-tab vt-tab-partidos"><caption>' + esc(EP.tr("O voto de cada partido (ordem alfabética)", "How each party voted (alphabetical order)")) + "</caption>" +
        '<thead><tr><th scope="col">' + EP.tr("Partido", "Party") + "</th>" + cols.map(function (k) { return '<th scope="col">' + esc(V.grupoNome(k)) + "</th>"; }).join("") +
        (temOri ? '<th scope="col">' + EP.tr("Orientação", "Orientation") + "</th>" : "") + "</tr></thead><tbody>" +
        l.map(function (x) {
          var r = orient[x.p];
          return '<tr><th scope="row">' + nome(x.p) + "</th>" + cols.map(function (k) { return "<td>" + EP.num(x.c[k] || 0) + "</td>"; }).join("") +
            (temOri ? "<td>" + (r && r.orientacao ? V.orientacao(r.orientacao) : "—") + "</td>" : "") + "</tr>";
        }).join("") + "</tbody></table></div>", EP.tr("Saber mais e a tabela dos partidos", "Learn more and the table of parties"), "vt-saiba-p");
    el.addEventListener("click", function (e) {
      var b = e.target.closest(".vt-p");
      if (b && o.aoTocar) o.aoTocar(b.getAttribute("data-partido"));
    });
  };
  // o corpo do modal de uma votação. x = { chips, placar, nota, oque, pessoas, pOpts, orient, gente, saiba, fontes }
  function corpoVoto(x) {
    var uid = "vt" + (++vpConta);
    return '<div class="vt-topo"><p class="vot-chips">' + x.chips + "</p>" + EP.d.placar(x.placar) + (x.nota ? '<p class="nota-lista">' + esc(x.nota) + "</p>" : "") + "</div>" +
      V.doQueSeTrata(x.oque) +
      '<div class="vt-abas" role="tablist" aria-label="' + EP.tr("Ver por pessoa ou por partido", "See by person or by party") + '">' +
      '<button type="button" role="tab" class="vt-aba" id="' + uid + '-ta" aria-controls="' + uid + '-pa" aria-selected="true"><span aria-hidden="true">👥 </span>' + EP.tr("Pessoas", "People") + "</button>" +
      '<button type="button" role="tab" class="vt-aba" id="' + uid + '-tb" aria-controls="' + uid + '-pb" aria-selected="false" tabindex="-1"><span aria-hidden="true">🎗️ </span>' + EP.tr("Partidos", "Parties") + "</button></div>" +
      '<div role="tabpanel" class="vt-painel vp-pessoas" id="' + uid + '-pa" aria-labelledby="' + uid + '-ta"></div>' +
      '<div role="tabpanel" class="vt-painel vt-partidos" id="' + uid + '-pb" aria-labelledby="' + uid + '-tb" hidden></div>' +
      EP.d.saiba(x.saiba, EP.tr("Votar Sim não é bom nem ruim: saber mais", "Voting Yes is neither good nor bad: learn more")) + '<p class="gv-fonte">' + EP.botaoFontes(x.fontes || []) + "</p>";
  }
  function ligaVoto(c, x) {
    var abas = [].slice.call(c.querySelectorAll(".vt-aba")), paineis = [c.querySelector(".vp-pessoas"), c.querySelector(".vt-partidos")];
    function mostra(k, foca) {
      abas.forEach(function (a, i) { a.setAttribute("aria-selected", String(i === k)); a.tabIndex = i === k ? 0 : -1; paineis[i].hidden = i !== k; });
      if (foca) abas[k].focus();
    }
    abas.forEach(function (a, i) {
      a.addEventListener("click", function () { mostra(i); });
      a.addEventListener("keydown", function (e) {
        var k = { ArrowLeft: 1 - i, ArrowRight: 1 - i, Home: 0, End: 1 }[e.key];
        if (k == null) return;
        e.preventDefault();
        mostra(k, true);
      });
    });
    var api = V.pessoasMonta(paineis[0], x.pessoas, x.pOpts);
    V.partidosMonta(paineis[1], x.pessoas, { orient: x.orient, gente: x.gente, aoTocar: function (p) {
      mostra(0);
      if (api) api.filtraPartido(p);
      var t = paineis[0].querySelector(".vp-conta");
      if (t) { t.setAttribute("tabindex", "-1"); EP.focaSuave(t); }
    } });
  }
  function abreModal(o, de) {
    var info = null;
    EP.gaveta({ modal: true, tit: o.tit, sub: o.sub, ver: o.ver, pagina: o.pagina,
      corpo: function () {
        return Promise.resolve(o.carrega()).then(function (x) {
          info = x;
          EP.gavetaTitulo(x.titHtml, x.subTxt);
          return corpoVoto(x);
        });
      },
      depois: function (c) { if (info) ligaVoto(c, info); } }, de);
  }
  // uma votação do Congresso (o arquivo da votação e a lista de quem está no cargo hoje, para as fotos e o link, só no toque)
  V.abreVot = function (chave, de) {
    var m = /^(camara|senado):([\w-]+)$/.exec(chave || "");
    if (!m || !EP.gaveta) return;
    var casa = m[1], id = m[2];
    abreModal({ tit: EP.tr("Votação", "Vote"), sub: V.casaNome(casa), ver: "vot:" + casa + ":" + id,
      pagina: { href: V.url(casa, id), t: EP.tr("Ver a votação inteira", "See the whole vote") },
      carrega: function () {
        return Promise.all([EP.json("dados/votacoes/" + casa + "/" + id + ".json"), EP.json("dados/" + casa + ".json").catch(function () { return {}; })]).then(function (r) {
          var d = r[0], membros = {}, p = typeof d.proposta === "object" ? d.proposta || {} : { sigla: d.proposta };
          (r[1].membros || []).forEach(function (y) { membros[y.id] = y; });
          var pessoas = (d.votos || []).map(function (y) {
            var mm = membros[y[0]];
            return { id: y[0], nome: y[1], partido: y[2], uf: y[3], voto: y[4], foto: mm ? mm.foto : null, link: !!mm };
          });
          var gente = casa === "senado" ? [EP.tr("senador", "senator"), EP.tr("senadores", "senators")] : [EP.tr("deputado", "deputy"), EP.tr("deputados", "deputies")];
          return {
            titHtml: esc(p.sigla || EP.tr("Votação no Plenário", "Vote in the full house")), subTxt: V.casaNome(casa) + " · " + EP.data(d.data) + (d.hora ? " · " + V.hora(d.hora) : ""),
            chips: V.chipCat(d.categoria) + " " + V.chipRes(d.resultado, d.descricao), placar: d.placar,
            oque: { sigla: p.sigla, s: p.s, s_en: p.s_en, ementa: p.ementa, descricao: d.descricao, cat: d.categoria, casa: casa, urlProposta: p.url, urlVotacao: d.url,
              site: casa === "senado" ? EP.tr("no site do Senado", "on the Senate website") : EP.tr("no site da Câmara", "on the Chamber's website") },
            pessoas: pessoas, gente: gente, orient: d.orientacaoPartidos || {},
            pOpts: { semRegistro: casa === "camara" ? Math.max(0, V.TOTAL.camara - ((d.placar || {}).total || pessoas.length)) : 0, gente: gente, legenda: d.legenda, filtroUF: true },
            saiba: "<p>" + EP.tr("Votar Sim não é bom e votar Não não é ruim: depende do que estava em votação. E não votar tem muitos motivos: a pessoa pode estar em missão oficial, de licença, presidindo a sessão ou ausente.",
              "Voting Yes is not good and voting No is not bad: it depends on what was being voted on. And there are many reasons for not voting: the person may be on an official mission, on leave, presiding over the session or absent.") + "</p>" +
              (casa === "camara" ? "<p>" + EP.tr("A Câmara publica só quem registrou voto. Por isso, quem não registrou aparece só na conta, sem o nome.",
                "The Chamber only publishes who registered a vote. That is why those who did not appear only in the count, without names.") + "</p>" : "") +
              "<p>" + EP.tr("As pessoas sem link não estão no cargo hoje (por isso o site não tem a página delas). Na página da votação inteira está também a regra de quantos votos eram precisos.",
                "People without a link are not in office today (so the site has no page for them). The page with the whole vote also shows how many votes were needed.") + "</p>",
            fontes: [].concat(d.fontes || [])
          };
        });
      } }, de);
  };

  // ---------------------------------------------------------------- o voto de cada pessoa (site-d-r16)
  // V.pessoasMonta(el, lista, o): o plenário pintado pelo voto (só desenho; a legenda e os grupos dizem o mesmo em texto), a
  // busca pelo nome, os filtros de partido e de estado e as pessoas agrupadas pelo voto (Sim, Não, Abstenção, Obstrução e "Não
  // votou ou outro motivo"), em ordem alfabética dentro de cada grupo, com o voto escrito com o nome oficial da Casa. As cores
  // são as mesmas para todos (as do site para cada voto); nenhum voto é "certo". Cada pessoa com página leva à gaveta dela.
  // lista = [{ id, nome, partido, uf?, voto (o nome oficial), foto?, link }]; o = { semRegistro (Câmara: quem não registrou voto,
  // só a conta), gente: [um, varios], legenda (Senado: códigos), filtroUF }
  V.GRUPO_ORDEM = ["Sim", "Não", "Abstenção", "Obstrução", "Outro"];
  V.grupoNome = function (c) { return c === "Outro" ? EP.tr("Não votou ou outro motivo", "Did not vote, or another reason") : D.nomeVoto(c); };
  // a mesma régua de V.catVoto, com o "NR" (não registrou voto) das Assembleias e Câmaras em "Outro"
  V.catVotoL = function (v) { return V.catVoto(v); };
  var LOTE_GRUPO = 12;
  V.pessoasMonta = function (el, lista, o) {
    if (!el) return;
    o = o || {};
    var grupos = {}, ufs = {}, partidos = {};
    lista.forEach(function (p) {
      var c = V.catVotoL(p.voto);
      (grupos[c] = grupos[c] || []).push(p);
      if (p.uf) ufs[p.uf] = 1;
      partidos[p.partido || "Sem partido"] = (partidos[p.partido || "Sem partido"] || 0) + 1;
    });
    var ks = V.GRUPO_ORDEM.filter(function (k) { return grupos[k]; });
    var sr = o.semRegistro || 0;
    // o plenário: da esquerda para a direita, Sim, Abstenção, Obstrução, Outro, quem não registrou voto e Não (as cores de css/votacoes.css)
    var g = [(grupos.Sim || []).length, (grupos["Abstenção"] || []).length, (grupos["Obstrução"] || []).length, (grupos.Outro || []).length, sr, (grupos["Não"] || []).length];
    var total = g.reduce(function (a, b) { return a + b; }, 0);
    var T = window.TRES || {};
    var plen = T.plenario && total ? '<div class="plen-voto vp-plen">' + T.plenario({ total: total, grupos: g, max: total > 120 ? 440 : total > 40 ? 380 : 300, cheio: true }) + "</div>" : "";
    var leg = '<ul class="vp-legenda" aria-label="' + EP.tr("Quantos votaram de cada jeito", "How many voted each way") + '">' + ks.map(function (k) {
      return '<li><i class="vot-q" style="background:' + V.COR[k] + '" aria-hidden="true"></i>' + esc(V.grupoNome(k)) + " <b>" + EP.num(grupos[k].length) + "</b></li>";
    }).join("") + (sr ? '<li><i class="vot-q vp-q-sr" aria-hidden="true"></i>' + esc(EP.tr("Não registraram voto", "Did not register a vote")) + " <b>" + EP.num(sr) + "</b></li>" : "") + "</ul>";
    var listaUF = Object.keys(ufs).sort(function (a, b) { return EP.norm(EP.UFS[a] || a).localeCompare(EP.norm(EP.UFS[b] || b)); });
    var listaP = Object.keys(partidos).sort(function (a, b) { return EP.norm(a).localeCompare(EP.norm(b)); });
    var uid = "vp" + (++vpConta);
    el.innerHTML = '<h3 class="vp-tit">' + EP.tr("Como cada pessoa votou", "How each person voted") + "</h3>" + plen + leg +
      '<p class="vp-cores">' + EP.tr("Cada cadeira é uma pessoa, pintada pelo voto. As cores são as mesmas para todos os partidos.", "Each seat is one person, colored by their vote. The colors are the same for every party.") + "</p>" +
      '<div class="filtros-casa gv-filtros vp-filtros"><div class="busca"><input type="search" class="vp-nome" id="' + uid + '-nome" placeholder="' + EP.tr("Procurar pelo nome", "Search by name") + '" aria-label="' +
      EP.tr("Procurar pelo nome", "Search by name") + '" autocomplete="off"></div>' +
      (listaP.length > 1 ? '<select class="vp-partido" aria-label="' + EP.tr("Filtrar por partido", "Filter by party") + '"><option value="">' + EP.tr("Todos os partidos", "All parties") + "</option>" +
        listaP.map(function (p) { return '<option value="' + esc(p) + '"' + (EP.en && p !== "Sem partido" ? ' lang="pt-BR"' : "") + ">" + esc(p === "Sem partido" ? EP.tr("Sem partido", "No party") : p) + " (" + EP.num(partidos[p]) + ")</option>"; }).join("") + "</select>" : "") +
      (o.filtroUF && listaUF.length > 1 ? '<select class="vp-uf" aria-label="' + EP.tr("Filtrar por estado", "Filter by state") + '"><option value="">' + EP.tr("Todos os estados", "All states") + "</option>" +
        listaUF.map(function (u) { return '<option value="' + u + '" data-busca="' + u + '">' + esc(EP.UFS[u] || u) + "</option>"; }).join("") + "</select>" : "") + "</div>" +
      '<p class="contagem vp-conta" aria-live="polite"></p><div class="vp-grupos"></div>';
    var fNome = el.querySelector(".vp-nome"), fP = el.querySelector(".vp-partido"), fU = el.querySelector(".vp-uf"), caixa = el.querySelector(".vp-grupos"), conta = el.querySelector(".vp-conta");
    if (fP) EP.comboSelect(fP, { placeholder: EP.tr("Digite o partido…", "Type a party…") });
    if (fU) EP.comboSelect(fU, { placeholder: EP.tr("Digite o estado…", "Type a state…") });
    var abertos = {};
    function cartao(p) {
      var vt = D.voto(p.voto), leg2 = (o.legenda || {})[p.voto];
      var longo = vt.longo || (leg2 && leg2 !== vt.curto ? leg2 : "");
      var linha2 = [p.partido ? (/^sem partido$/i.test(p.partido) ? EP.tr("Sem partido", "No party") : p.partido) : "", p.uf].filter(Boolean).join(" · ");
      var corpo = EP.av(p.foto, p.nome) + "<b>" + EP.pt(esc(p.nome || "")) + "</b>" + (linha2 ? "<small>" + esc(linha2) + "</small>" : "") +
        '<span class="voto-chip" style="--cv:' + (V.COR[vt.cat] || V.COR.Outro) + '"><span class="sr">' + EP.tr("Voto: ", "Vote: ") + "</span>" + esc(vt.curto) + "</span>" +
        (vt.cat === "Outro" && longo && longo !== vt.curto ? "<small>" + (leg2 && !vt.longo && EP.en ? EP.pt(esc(longo)) : esc(longo)) + "</small>" : "");
      if (p.link) return '<a class="pessoa-card voto-card" href="pessoa.html?id=' + encodeURIComponent(p.id) + '">' + corpo + "</a>";
      return '<div class="pessoa-card voto-card fora">' + corpo + '<small class="fora-txt">' + EP.tr("Sem página aqui: não está no cargo hoje", "No page here: not in office today") + "</small></div>";
    }
    function desenha() {
      var q = EP.norm(fNome.value).trim(), pa = fP ? fP.value : "", uf = fU ? fU.value : "", filtro = !!(q || pa || uf), n = 0;
      caixa.innerHTML = ks.map(function (k) {
        var l = grupos[k].filter(function (p) { return (!q || EP.norm(p.nome).indexOf(q) > -1) && (!pa || (p.partido || "Sem partido") === pa) && (!uf || p.uf === uf); });
        n += l.length;
        if (!l.length) return "";
        var vis = filtro || abertos[k] ? l : l.slice(0, LOTE_GRUPO);
        return '<section class="vp-grupo" data-g="' + k + '" aria-labelledby="' + uid + "-" + k.charAt(0) + '"><h4 class="vp-gtit" id="' + uid + "-" + k.charAt(0) + '"><i class="vot-q" style="background:' + V.COR[k] + '" aria-hidden="true"></i>' +
          esc(V.grupoNome(k)) + ' <span class="vp-gn">' + EP.num(l.length) + "</span></h4>" +
          '<div class="grade-pessoas gv-grade vp-grade">' + vis.map(cartao).join("") + "</div>" +
          (vis.length < l.length ? '<p class="mais-lista"><button type="button" class="btn claro peq vp-mais" data-g="' + k + '">' +
            esc(EP.tr("Ver todos os " + EP.num(l.length) + " (" + V.grupoNome(k) + ")", "See all " + EP.num(l.length) + " (" + V.grupoNome(k) + ")")) + ' <span aria-hidden="true">▾</span></button></p>' : "") + "</section>";
      }).join("") + (sr && !filtro ? '<section class="vp-grupo vp-sr"><h4 class="vp-gtit"><i class="vot-q vp-q-sr" aria-hidden="true"></i>' + esc(EP.tr("Não registraram voto", "Did not register a vote")) +
        ' <span class="vp-gn">' + EP.num(sr) + "</span></h4><p class=\"muted\">" + EP.tr("A Câmara publica só o nome de quem registrou voto. Quem não registrou pode estar ausente, de licença, em missão oficial ou ter outro motivo.",
          "The Chamber only publishes the names of those who registered a vote. Those who did not may have been absent, on leave, on an official mission or had another reason.") + "</p></section>" : "") ||
        '<div class="vazio"><span class="grande" aria-hidden="true">🤷</span>' + EP.tr("Ninguém encontrado com esses filtros.", "No one found with these filters.") + "</div>";
      var t = filtro ? EP.tr("Mostrando " + EP.num(n) + " de " + EP.num(lista.length) + " " + o.gente[1] + ", em ordem alfabética dentro de cada voto.", "Showing " + EP.num(n) + " of " + EP.num(lista.length) + " " + o.gente[1] + ", in alphabetical order within each vote.") :
        EP.tr(EP.num(lista.length) + " " + (lista.length === 1 ? o.gente[0] : o.gente[1]) + " com o voto registrado, em ordem alfabética dentro de cada voto.", EP.num(lista.length) + " " + (lista.length === 1 ? o.gente[0] : o.gente[1]) + " with a registered vote, in alphabetical order within each vote.");
      if (conta.textContent !== t) conta.textContent = t;
    }
    var tm = null;
    fNome.addEventListener("input", function () { clearTimeout(tm); tm = setTimeout(function () { desenha(); }, 150); });
    if (fP) fP.addEventListener("change", function () { desenha(); });
    if (fU) fU.addEventListener("change", function () { desenha(); });
    caixa.addEventListener("click", function (e) {
      var b = e.target.closest(".vp-mais");
      if (!b) return;
      var k = b.getAttribute("data-g");
      abertos[k] = true;
      desenha();
      // o foco vai para a primeira pessoa nova do grupo
      var gr = caixa.querySelector('.vp-grupo[data-g="' + k + '"]');
      var c = gr && gr.querySelectorAll(".pessoa-card")[LOTE_GRUPO];
      if (c) { if (!c.matches("a")) c.setAttribute("tabindex", "-1"); EP.focaSuave(c); }
    });
    desenha();
    return { filtraPartido: function (p) {
      if (!fP) return;
      fNome.value = "";
      if (fU) { fU.value = ""; EP.comboSync(fU); }
      fP.value = p;
      EP.comboSync(fP);
      desenha();
    } };
  };
  var vpConta = 0;

  // ---------------------------------------------------------------- "Como votaram" de uma Assembleia ou Câmara Municipal (site-d-r16)
  // estado.html#votacoes e cidade.html#votacoes. Lê dados/votacoes/assembleias/<UF>.json ou dados/votacoes/camaras/<IBGE>.json
  // (scripts/votos_casas.py: as votações mais recentes da Casa, com o voto de cada pessoa) só quando a aba abre. Cartões com o
  // placar (6 de cada vez); tocar abre a gaveta com o placar, o que foi votado, o link oficial e as pessoas agrupadas pelo voto
  // (?ver=vl:<id da votação>). Onde a Casa não publica o voto de cada um, V.semVotosLocal diz isso, com os links oficiais.
  var LOC = { d: null, n: 6, o: null };
  function chipResL(r) {
    var n = EP.norm(r || ""), st = /^aprovad/.test(n) ? "aprovada" : /^rejeitad/.test(n) ? "rejeitada" : "outra";
    if (!r) return EP.carimbo("outra", EP.tr("Resultado não informado", "Result not reported"));
    return '<span class="carimbo s-' + st + '"><span aria-hidden="true">' + EP.STATUS[st].ic + " </span>" + D.resultado(r) + "</span>";
  }
  // o placar: o oficial, ou a conta dos votos de quem está na Casa hoje (quando a Casa não publica o placar junto)
  function placarL(v, d) {
    if (v.placar && v.placar.total) return { p: v.placar, oficial: true };
    var p = { "Sim": 0, "Não": 0, "Abstenção": 0, "Obstrução": 0, "Outro": 0, total: 0 };
    Object.keys(v.votos || {}).forEach(function (k) { var c = V.catVoto(k), n = v.votos[k].length; p[c] += n; p.total += n; });
    return { p: p, oficial: false };
  }
  function nomeCasaL(d) { return EP.en && d.nome_en ? d.nome_en : d.nome || d.casa || ""; }
  function nomeCasaHtml(d) { return EP.en && d.nome_en ? esc(d.nome_en) : EP.pt(esc(d.nome || d.casa || "")); }
  function cartaoL(v, k) {
    var desc = v.descricao || "", curta = desc.length > 150 ? desc.slice(0, 140).replace(/\s+\S*$/, "") + "…" : desc, quando = EP.data(v.data);
    return '<li class="vot-card d-vot-li"><button type="button" class="d-vot" data-vl="' + k + '" aria-haspopup="dialog">' +
      '<span class="d-vot-cab"><span class="chip neutro chip-casa"><span aria-hidden="true">🏛️ </span>' + esc(LOC.d.casa || "") + '</span><time datetime="' + esc(v.data || "") + '">' + esc(quando) + "</time></span>" +
      '<b class="vot-tit">' + (v.proposta ? EP.pt(esc(v.proposta)) : esc(EP.tr("Votação no Plenário", "Vote in the full house"))) + '<span class="sr">, ' + esc(EP.tr("votação de ", "vote of ") + quando) + "</span></b>" +
      '<span class="vot-chips">' + chipResL(v.resultado) + "</span>" + EP.d.placar(placarL(v, LOC.d).p) +
      (curta ? '<span class="d-vot-desc">' + EP.pt(esc(curta)) + "</span>" : "") +
      '<span class="d-ver">' + EP.tr("Ver como cada pessoa votou", "See how each person voted") + ' <span aria-hidden="true">→</span></span></button></li>';
  }
  function desenhaL(el, focarDe) {
    var l = LOC.d.votacoes, vis = l.slice(0, LOC.n), ul = el.querySelector(".lista-vot");
    ul.innerHTML = vis.map(cartaoL).join("");
    var c = el.querySelector(".d-vot-conta"), t = EP.tr("Mostrando " + EP.num(vis.length) + " de " + EP.num(l.length) + (l.length === 1 ? " votação" : " votações") + ", da mais nova para a mais antiga.",
      "Showing " + EP.num(vis.length) + " of " + EP.num(l.length) + (l.length === 1 ? " vote" : " votes") + ", newest first.");
    if (c.textContent !== t) c.textContent = t;
    el.querySelector(".d-vot-mais").innerHTML = l.length > vis.length ? '<button type="button" class="btn claro" data-vl-mais>' +
      esc(EP.tr("Mostrar mais " + Math.min(6, l.length - vis.length), "Show " + Math.min(6, l.length - vis.length) + " more")) + ' <span aria-hidden="true">▾</span></button>' : "";
    if (focarDe != null) { var b = ul.querySelectorAll(".d-vot")[focarDe]; if (b) EP.focaSuave(b); }
  }
  // o = { arquivo, gente: [um, varios] (já no idioma), membroDe: "da Assembleia" (texto do "Saber mais") }
  V.casaLocal = function (el, o) {
    if (!el) return;
    LOC.o = o;
    el.innerHTML = '<div class="carregando">' + EP.tr("Carregando…", "Loading…") + "</div>";
    return EP.json(o.arquivo).then(function (d) {
      if (!d || !(d.votacoes || []).length) throw new Error("vazio");
      LOC.d = d;
      LOC.n = 6;
      var esc0 = d.escopo ? (EP.en && d.escopo_en ? esc(d.escopo_en) : EP.en ? EP.pt(esc(d.escopo)) : esc(d.escopo)) : "";
      el.innerHTML = '<p class="d-linha vl-linha">' + esc(EP.tr("As " + EP.num(d.recentes) + " votações mais recentes em que o voto de cada " + o.gente[0] + " ficou registrado (o site tem " + EP.num(d.total) + "). Toque numa para ver como cada pessoa votou.",
        "The " + EP.num(d.recentes) + " most recent votes in which each " + o.gente[0] + "'s vote was recorded (the site has " + EP.num(d.total) + "). Tap one to see how each person voted.")) + "</p>" +
        '<p class="contagem d-vot-conta" role="status"></p><ul class="lista-vot d-vots"></ul><div class="mais-lista d-vot-mais"></div>' +
        EP.d.saiba("<p>" + EP.tr("Votar Sim não é bom e votar Não não é ruim: depende do que estava em votação. E não votar tem muitos motivos: a pessoa pode estar ausente, de licença ou presidindo a sessão.",
          "Voting Yes is not good and voting No is not bad: it depends on what was being voted on. And there are many reasons for not voting: the person may be absent, on leave or presiding over the session.") + "</p>" +
          "<p>" + esc(EP.tr("Aqui aparece o voto de quem está na Casa hoje. O placar oficial conta todos que votaram naquele dia, inclusive quem já saiu. As outras votações estão na página de cada " + o.gente[0] + " (aba “Como votou”) e no site oficial.",
            "This shows the votes of the people who are in the house today. The official count includes everyone who voted that day, including those who have left. The other votes are on each " + o.gente[0] + "'s page (the “How they voted” tab) and on the official website.")) + "</p>" +
          (esc0 ? '<p><b>' + EP.tr("O que entra: ", "What is included: ") + "</b>" + esc0 + "</p>" : ""), EP.tr("Saber mais: o que estas votações mostram", "Learn more: what these votes show")) +
        '<p class="gv-fonte">' + EP.botaoFontes(d.fontes || [], EP.tr("De onde vêm estas votações?", "Where do these votes come from?")) + "</p>";
      desenhaL(el);
      if (!el._ligadoL) {
        el._ligadoL = true;
        el.addEventListener("click", function (e) {
          if (e.target.closest("[data-vl-mais]")) { var de = LOC.n; LOC.n += 6; desenhaL(el, de); return; }
          var b = e.target.closest("[data-vl]");
          if (b) V.abreVotLocal(LOC.d.votacoes[+b.getAttribute("data-vl")], b);
        });
      }
      return d;
    }).catch(function (err) {
      // o arquivo da Casa não existe (a Casa deixou de ter votações guardadas): a aba diz que o site não tem o voto de cada um
      if (o.semVotos && /^404\b|vazio/.test(String((err && err.message) || ""))) { el.innerHTML = o.semVotos; return; }
      el.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">⚠️</span>' +
        EP.tr("Não foi possível carregar as votações agora. Tente de novo daqui a pouco.", "The votes could not be loaded right now. Please try again in a little while.") + "</div>";
    });
  };
  V.abreVotLocal = function (v, de) {
    var d = LOC.d, o = LOC.o || { gente: [EP.tr("pessoa", "person"), EP.tr("pessoas", "people")] };
    if (!v || !d || !EP.gaveta) return;
    var pl = placarL(v, d), lista = [];
    Object.keys(v.votos || {}).forEach(function (voto) {
      v.votos[voto].forEach(function (i) {
        var p = d.pessoas[i];
        if (p) lista.push({ id: p[0], nome: p[1], partido: p[2], foto: p[3], voto: voto, link: true });
      });
    });
    lista.sort(function (a, b) { return EP.norm(a.nome).localeCompare(EP.norm(b.nome)); });
    var nota = !pl.oficial ? EP.tr("A " + nomeCasaL(d) + " não publica o placar junto com esta votação: os números são a conta dos votos de quem está na Casa hoje.",
      "The " + nomeCasaL(d) + " does not publish the count with this vote: the numbers are the sum of the votes of those in the house today.") :
      pl.p.total > lista.length ? EP.tr("O placar oficial tem " + EP.num(pl.p.total) + " votos. Aqui aparecem os " + EP.num(lista.length) + " de quem está na Casa hoje (quem já saiu não tem página no site).",
        "The official count has " + EP.num(pl.p.total) + " votes. This shows the " + EP.num(lista.length) + " of those in the house today (people who have left have no page on the site).") : "";
    var esc0 = d.escopo ? (EP.en && d.escopo_en ? esc(d.escopo_en) : EP.en ? EP.pt(esc(d.escopo)) : esc(d.escopo)) : "";
    abreModal({ tit: v.proposta ? EP.pt(esc(v.proposta)) : esc(EP.tr("Votação no Plenário", "Vote in the full house")), sub: nomeCasaL(d) + " · " + EP.data(v.data), ver: "vl:" + v.id,
      carrega: function () {
        return {
          titHtml: v.proposta ? EP.pt(esc(v.proposta)) : esc(EP.tr("Votação no Plenário", "Vote in the full house")), subTxt: nomeCasaL(d) + " · " + EP.data(v.data),
          chips: chipResL(v.resultado), placar: pl.p, nota: nota,
          oque: { sigla: v.proposta, s: v.s, s_en: v.s_en, ementa: v.ementa, descricao: v.descricao, casa: d.ibge ? "municipal" : "estadual", urlProposta: v.urlProposta, urlVotacao: v.url,
            site: EP.tr("no site oficial", "on the official website") },
          pessoas: lista, gente: o.gente, orient: {}, pOpts: { gente: o.gente, filtroUF: false },
          saiba: "<p>" + EP.tr("Votar Sim não é bom e votar Não não é ruim: depende do que estava em votação. Em votações de veto, o que quer dizer o Sim muda de Casa para Casa.",
            "Voting Yes is not good and voting No is not bad: it depends on what was being voted on. In votes on vetoes, what a Yes means changes from house to house.") + "</p>" +
            (esc0 ? "<p><b>" + EP.tr("O que entra: ", "What is included: ") + "</b>" + esc0 + "</p>" : "") +
            "<p>" + EP.tr("A Casa não publica a orientação dos partidos nestas votações: por isso, a aba “Partidos” mostra só como as pessoas de cada partido votaram.",
              "The house does not publish the parties' orientation in these votes: that is why the “Parties” tab only shows how each party's members voted.") + "</p>",
          fontes: d.fontes || []
        };
      } }, de);
  };
  if (EP.gavetaVer) EP.gavetaVer.vl = function (id) {
    if (EP.abas && EP.abas.mostra && document.getElementById("votacoes")) EP.abas.mostra("votacoes");
    var t0 = Date.now();
    (function tenta() {
      var k = -1;
      if (LOC.d) LOC.d.votacoes.some(function (v, i) { if (v.id === id) { k = i; return true; } return false; });
      if (k > -1) V.abreVotLocal(LOC.d.votacoes[k], document.querySelector('[data-vl="' + k + '"]'));
      else if (!LOC.d && Date.now() - t0 < 8000) setTimeout(tenta, 150);
    })();
  };
  // a Casa não publica o voto de cada um num formato que o site lê: a aba fica no lugar e diz isso, com os links oficiais
  // o = { casaHtml (nome da Casa, já marcado), gente: [um, varios], notas: [textos já no idioma], site, sic, vazioTxt }
  V.semVotosLocal = function (o) {
    function lk(ic, href, txt) {
      return /^https?:\/\//.test(href || "") ? '<li><span class="ic-onde" aria-hidden="true">' + ic + '</span><span><a href="' + esc(href) + '" target="_blank" rel="noopener" hreflang="pt-BR">' + esc(txt) +
        ' <span aria-hidden="true">↗</span><span class="sr"> ' + EP.tr("(abre em outra aba)", "(opens in a new tab)") + "</span></a></span></li>" : "";
    }
    var links = [lk("🏛️", o.site, EP.tr("Site oficial", "Official website")), lk("✉️", o.sic, EP.tr("Pedir a informação (Lei de Acesso à Informação)", "Request the information (Access to Information Law)"))].filter(Boolean);
    return '<div class="sem-dados-mandato vl-sem"><div class="vazio"><span class="grande" aria-hidden="true">🗳️</span><p>' +
      (o.vazioTxt || EP.tr("Este site não tem o voto de cada " + o.gente[0] + " da ", "This site does not have each " + o.gente[0] + "'s vote in the ") + o.casaHtml + ".") + "</p></div>" +
      ((o.notas || []).length ? '<ul class="notas-casa vl-notas">' + o.notas.map(function (n) { return "<li>" + n + "</li>"; }).join("") + "</ul>" : "") +
      (links.length ? '<ul class="links-onde">' + links.join("") + "</ul>" : "") +
      EP.d.saiba("<p>" + EP.tr("Votação nominal é a que registra o voto de cada pessoa, com o nome. Muitas Casas votam de forma simbólica (sem registrar o voto de cada um) ou publicam o resultado só em PDF ou em vídeo. Qualquer pessoa pode pedir esses dados à Casa pela Lei de Acesso à Informação, de graça e sem dizer por quê.",
        "A roll-call vote is one that records each person's vote, by name. Many houses vote symbolically (without recording each person's vote) or publish the result only as a PDF or a video. Anyone can request this data from the house under the Access to Information Law, for free and without saying why.") + "</p>") + "</div>";
  };
  if (EP.gavetaVer) EP.gavetaVer.vot = function (v) {
    if (EP.abas && EP.abas.mostra && document.getElementById("votacoes")) EP.abas.mostra("votacoes");
    V.abreVot(v, document.querySelector('[data-vot="' + v.replace(/"/g, "") + '"]'));
  };
  function ligaRecentes() {
    var el = document.getElementById("votos-recentes");
    if (!el) return;
    // os catálogos são grandes: só carrega quando o bloco chega perto da tela
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (ents) {
        if (ents.some(function (x) { return x.isIntersecting; })) { io.disconnect(); V.recentes(el, 6); }
      }, { rootMargin: "700px 0px" });
      io.observe(el);
    } else V.recentes(el, 6);
  }

  // ---------------------------------------------------------------- votacoes.html: todas as votações
  function paginaLista() {
    var lista = document.getElementById("lista-votacoes");
    if (!lista) return;
    var LOTE = 30, mostrando = LOTE, TODAS = [], tBusca = null;
    var f = { casa: "", ano: "", cat: "", res: "", q: "" };
    var sel = {
      casa: document.getElementById("f-casa"), ano: document.getElementById("f-ano"),
      cat: document.getElementById("f-cat"), res: document.getElementById("f-res")
    };
    var busca = document.getElementById("f-q"), contagem = document.getElementById("contagem-vot"), mais = document.getElementById("mais-vot");

    D.canonico();
    V.trilha();
    var fn = document.getElementById("fontes-nominal");
    if (fn) fn.innerHTML = EP.botaoFontes(V.F.nominal);
    var fc = document.getElementById("fontes-categorias");
    if (fc) fc.innerHTML = EP.botaoFontes([].concat(V.CAT.principal.fontes, V.CAT.mudanca.fontes, V.CAT.procedimento.fontes, V.CAT.outra.fontes),
      EP.tr("De onde vêm essas regras?", "Where do these rules come from?"));

    // valores iniciais pelo endereço (votacoes.html?casa=senado&ano=2025&cat=principal&res=aprovado&q=pec)
    ["casa", "ano", "cat", "res", "q"].forEach(function (k) { f[k] = (EP.param(k) || "").trim(); });
    if (!/^(camara|senado)$/.test(f.casa)) f.casa = "";
    if (!V.CAT[f.cat]) f.cat = "";
    if (!/^(aprovado|rejeitado)$/.test(f.res)) f.res = "";
    if (!/^\d{4}$/.test(f.ano)) f.ano = "";
    busca.value = f.q;
    var n0 = EP.memo ? EP.memo.le("vot-n") : null;
    if (typeof n0 === "number" && n0 > LOTE) mostrando = n0;

    function opcoes(s, l) { s.innerHTML = l.map(function (o) { return '<option value="' + esc(o[0]) + '">' + esc(o[1]) + "</option>"; }).join(""); }
    function guardaEndereco() {
      var u = new URL(location.href);
      ["casa", "ano", "cat", "res", "q"].forEach(function (k) { if (f[k]) u.searchParams.set(k, f[k]); else u.searchParams.delete(k); });
      try { history.replaceState(history.state, "", u.pathname.split("/").pop() + u.search + u.hash); } catch (e) {}
      if (EP.atualizaLinksIdioma) EP.atualizaLinksIdioma();
      // ui-r9: quantos "Mostrar mais" estavam abertos fica na memória do histórico (EP.memo): o Voltar traz a lista igual
      if (EP.memo) EP.memo.grava("vot-n", mostrando > LOTE ? mostrando : null);
    }
    function filtradas() {
      // cada palavra procurada precisa ser o começo de uma palavra do texto; número, só o número inteiro
      // ("45" acha "PEC 45/2019", e não "345" nem "Total: 457"; o placar no fim da descrição da Câmara não conta)
      var q = EP.norm(f.q).replace(/[^a-z0-9]+/g, " ").trim(), pal = q ? q.split(" ") : [];
      return TODAS.filter(function (v) {
        if ((f.casa && v.casa !== f.casa) || (f.ano && (v.data || "").slice(0, 4) !== f.ano) || (f.cat && v.categoria !== f.cat)) return false;
        if (f.res && EP.norm(v.resultado).indexOf(f.res.slice(0, 7)) !== 0) return false;
        if (!pal.length) return true;
        var t = v._busca || (v._busca = " " + EP.norm((v.proposta || "") + " " + (v.descricao || "").replace(/\s*Sim:\s*\d[\s\S]*$/i, ""))
          .replace(/[^a-z0-9]+/g, " ") + " ");
        return pal.every(function (p) { return t.indexOf(" " + p + (/^\d+$/.test(p) ? " " : "")) > -1; });
      });
    }
    function desenha(focarDe) {
      var l = filtradas(), vis = l.slice(0, mostrando);
      lista.innerHTML = vis.map(function (v) { return V.cartao(v, { nivel: 3 }); }).join("") ||
        '<li class="vazio" style="grid-column:1/-1"><span class="grande" aria-hidden="true">🔍</span>' + EP.tr("Nenhuma votação com esses filtros.", "No votes match these filters.") + "</li>";
      var txt = l.length === TODAS.length ?
        EP.tr("Mostrando " + EP.num(vis.length) + " de " + EP.num(l.length) + " votações, da mais nova para a mais antiga.", "Showing " + EP.num(vis.length) + " of " + EP.num(l.length) + " votes, newest first.") :
        EP.tr("Mostrando " + EP.num(vis.length) + " de " + EP.num(l.length) + (l.length === 1 ? " votação encontrada" : " votações encontradas") + " (de " + EP.num(TODAS.length) + " no total), da mais nova para a mais antiga.",
          "Showing " + EP.num(vis.length) + " of " + EP.num(l.length) + (l.length === 1 ? " vote found" : " votes found") + " (out of " + EP.num(TODAS.length) + " in total), newest first.");
      if (contagem.textContent !== txt) contagem.textContent = txt;
      var resta = l.length - vis.length;
      mais.innerHTML = resta > 0 ? '<button type="button" class="btn claro" id="ver-mais-vot">' + EP.tr("Mostrar mais " + Math.min(LOTE, resta), "Show " + Math.min(LOTE, resta) + " more") +
        ' <span aria-hidden="true">▾</span></button>' : "";
      // depois de "Mostrar mais", o foco vai para a primeira votação nova (quem usa teclado continua dali)
      if (focarDe != null) {
        var a = lista.querySelectorAll(".vot-tit a")[focarDe];
        if (a) a.focus();
      }
    }
    function muda() { mostrando = LOTE; guardaEndereco(); desenha(); }

    V.carrega().then(function (r) {
      TODAS = r.lista;
      var anos = {};
      TODAS.forEach(function (v) { if (v.data) anos[v.data.slice(0, 4)] = 1; });
      opcoes(sel.casa, [["", EP.tr("Câmara e Senado", "Chamber and Senate")], ["camara", EP.tr("Câmara dos Deputados", "Chamber of Deputies")], ["senado", EP.tr("Senado Federal", "Federal Senate")]]);
      opcoes(sel.ano, [["", EP.tr("Todos os anos", "All years")]].concat(Object.keys(anos).sort().reverse().map(function (a) { return [a, a]; })));
      opcoes(sel.cat, [["", EP.tr("Todas as categorias", "All categories")]].concat(V.ORDEM_CAT.map(function (c) { return [c, EP.tr(V.CAT[c].nome[0], V.CAT[c].nome[1])]; })));
      opcoes(sel.res, [["", EP.tr("Todos os resultados", "All results")], ["aprovado", EP.tr("Aprovado", "Approved")], ["rejeitado", EP.tr("Rejeitado", "Rejected")]]);
      Object.keys(sel).forEach(function (k) {
        if (f[k] && !sel[k].querySelector('option[value="' + f[k] + '"]')) f[k] = "";
        sel[k].value = f[k];
        EP.comboSelect(sel[k], { placeholder: EP.tr("Digite para procurar…", "Type to search…") });
        sel[k].addEventListener("change", function () { f[k] = sel[k].value; muda(); });
      });
      var at = document.getElementById("atualizado-vot");
      var datas = [r.camara && r.camara.atualizado, r.senado && r.senado.atualizado].filter(Boolean).sort();
      if (at && datas.length) at.textContent = EP.tr("Dados atualizados em ", "Data updated on ") + EP.data(datas[datas.length - 1]) + ".";
      var fl = document.getElementById("fontes-lista");
      if (fl) fl.innerHTML = EP.fontesHtml([r.camara && r.camara.fonte, r.senado && r.senado.fonte].filter(Boolean));
      desenha();
    }).catch(function () {
      lista.innerHTML = '<li class="vazio" style="grid-column:1/-1"><span class="grande" aria-hidden="true">⚠️</span>' +
        EP.tr("Não foi possível carregar as votações agora. Tente de novo daqui a pouco.", "The votes could not be loaded right now. Please try again in a little while.") + "</li>";
    });

    busca.addEventListener("input", function () {
      clearTimeout(tBusca);
      tBusca = setTimeout(function () { f.q = busca.value.trim(); muda(); }, 250);
    });
    mais.addEventListener("click", function (e) {
      if (!e.target.closest("#ver-mais-vot")) return;
      var de = mostrando;
      mostrando += LOTE;
      guardaEndereco();
      desenha(de);
    });
  }

  function inicia() {
    ligaRecentes();
    paginaLista();
    if (document.getElementById("lista-votacoes")) {
      D.rodapeErros(document.getElementById("links-erro"), "Viu algo errado nesta página?", "Did you see something wrong on this page?");
      if (window.TRES && TRES.congresso) {
        var il = document.getElementById("ilu-congresso");
        if (il) il.innerHTML = TRES.congresso({ rotulos: true });
      }
      EP.fundo3d([["cubo", "4%", "12%", 40, 0, 0, 18], ["esfera", "93%", "8%", 36, 3, 0, 7], ["anel", "90%", "50%", 56, 2, 0, 20], ["esfera", "3%", "70%", 30, 6, 0, 8]], document.body);
      EP.revelar();
      EP.paralaxe();
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", inicia);
  else inicia();
})();
