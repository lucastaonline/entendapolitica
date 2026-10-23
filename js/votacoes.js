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
  V.url = function (casa, chave) { return "votacao.html?casa=" + casa + "&id=" + encodeURIComponent(V.id(chave)); };
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
  V.recentes = function (el, n) {
    if (!el) return;
    V.carrega().then(function (r) {
      // uma votação por proposta (a mais nova): os dois turnos de uma PEC não ocupam dois lugares
      var vistos = {}, l = r.lista.filter(function (v) {
        var k = v.casa + "|" + (v.propostaId || v.proposta || v.chave);
        if (v.categoria !== "principal" || vistos[k]) return false;
        vistos[k] = 1;
        return true;
      }).slice(0, n || 3);
      if (!l.length) throw new Error("vazio");
      el.innerHTML = '<ul class="lista-vot">' + l.map(function (v) { return V.cartao(v, { nivel: 3 }); }).join("") + "</ul>";
    }).catch(function () {
      el.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">⚠️</span>' +
        EP.tr("Não foi possível carregar as votações agora. Tente de novo daqui a pouco.", "The votes could not be loaded right now. Please try again in a little while.") + "</div>";
    });
  };
  function ligaRecentes() {
    var el = document.getElementById("votos-recentes");
    if (!el) return;
    // os catálogos são grandes: só carrega quando o bloco chega perto da tela
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (ents) {
        if (ents.some(function (x) { return x.isIntersecting; })) { io.disconnect(); V.recentes(el, 3); }
      }, { rootMargin: "700px 0px" });
      io.observe(el);
    } else V.recentes(el, 3);
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

    function opcoes(s, l) { s.innerHTML = l.map(function (o) { return '<option value="' + esc(o[0]) + '">' + esc(o[1]) + "</option>"; }).join(""); }
    function guardaEndereco() {
      var u = new URL(location.href);
      ["casa", "ano", "cat", "res", "q"].forEach(function (k) { if (f[k]) u.searchParams.set(k, f[k]); else u.searchParams.delete(k); });
      try { history.replaceState(history.state, "", u.pathname.split("/").pop() + u.search + u.hash); } catch (e) {}
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
