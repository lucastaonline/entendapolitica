/* A política do Brasil: presidente, vice, ministros, Senado e Câmara. */
(function () {
  "use strict";
  var EP = window.EP, T = window.TRES || {}, D = EP.trd;
  var esc = EP.esc;

  D.canonico();
  if (T.tresPoderes) document.getElementById("ilu-poderes").innerHTML = T.tresPoderes();
  EP.fundo3d([["cubo", "4%", "12%", 40, 0, 0, 18], ["esfera", "93%", "8%", 36, 3, 0, 7], ["anel", "90%", "50%", 56, 2, 0, 20], ["esfera", "3%", "70%", 30, 6, 0, 8]], document.body);
  // site-d-r14 (protótipo D): as Casas no visual novo (js/casa.js: plenário em ordem alfabética e etiquetas dos partidos que
  // abrem a gaveta com as pessoas); vale para todo mandato desta página (hoje, os anteriores e 2027)
  EP.casaD = true;
  // mandatos-r11: todo mandato tem o mesmo layout de hoje (as mesmas abas e as mesmas partes); só os dados mudam.
  // O próximo mandato (brasil.html?mandato=2027, ou os links antigos brasil.html#quem-assume) vem do js/proximos.js (quem foi
  // eleito em 2026); um mandato anterior (brasil.html?mandato=2019), do js/historico.js
  var X = EP.eleitos;
  var futuro = !!(X && X.ehFuturo()), passado = !futuro && EP.hist ? EP.hist.param() : null;
  if (EP.hist) EP.hist.seletor(document.getElementById("mandato-lugar"), "brasil", futuro ? X.FUTURO : passado, X && X.opcaoFutura("BR"));

  // ---------- números grandes do topo (site-d-r14) ----------
  // O mesmo para todo mandato: os números que a Constituição fixa (81 senadores, 513 deputados, 11 cadeiras no STF, 4 anos de
  // mandato) e o ano da eleição daquele mandato. Não pedem nenhum arquivo de dados (a página continua baixando, ao abrir, só o
  // que a aba aberta precisa); as contagens que mudam (ministérios, partidos, cadeiras ocupadas) ficam no topo de cada aba.
  function numeros() {
    var el = document.getElementById("numeros");
    if (!el || !EP.d) return;
    var anoEleicao = futuro ? 2026 : passado ? +String(passado).slice(0, 4) - 1 : 2022;
    var CF = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm";
    function cf(art, pt, en) { var f = { veiculo: "Planalto", titulo: EP.tr("Constituição Federal, " + art + " (" + pt + ")", "Federal Constitution, " + art + " (" + en + ")"), url: CF, data: "1988-10-05" }; if (EP.en) f.lang = "en"; return f; }
    var fontes = [cf("art. 45", "a Câmara dos Deputados e o número de deputados por estado", "the Chamber of Deputies and the number of deputies per state"),
      { veiculo: "Planalto", titulo: EP.tr("Lei Complementar nº 78/1993 (513 deputados federais)", "Supplementary Law No. 78/1993 (513 federal deputies)"), url: "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp78.htm", data: "1993-12-30", lang: EP.en ? "en" : undefined },
      cf("art. 46", "3 senadores por estado e pelo Distrito Federal, com mandato de 8 anos", "3 senators per state and for the Federal District, with 8-year terms"),
      cf("art. 82", "o mandato do presidente é de 4 anos", "the President's term is 4 years"),
      cf("art. 101", "o STF tem 11 ministros", "the STF has 11 justices"),
      { veiculo: "Tribunal Superior Eleitoral (TSE)", titulo: EP.tr("Dados abertos: candidaturas e resultados de cada eleição", "Open data: candidates and results of each election"), url: "https://dadosabertos.tse.jus.br/dataset/?q=candidatos", data: null, lang: EP.en ? "en" : undefined }];
    el.innerHTML = EP.d.kpis([
      { ic: "🗳️", n: anoEleicao, t: EP.tr("ano da eleição deste mandato", "year this term was elected") },
      { ic: "🏢", n: 4, t: EP.tr("anos de mandato do presidente", "years in the President's term"), href: "#executivo" },
      { ic: "🏛️", n: 81, t: EP.tr("senadores (3 por estado)", "senators (3 per state)"), href: "#senado" },
      { ic: "🏛️", n: 513, t: EP.tr("deputados federais", "federal deputies"), href: "#camara" },
      { ic: "⚖️", n: 11, t: EP.tr("cadeiras no STF", "seats on the Supreme Court"), href: "#judiciario" }
    ], EP.tr("O Brasil em números", "Brazil in numbers")) + '<p class="d-fonte-kpis">' + EP.botaoFontes(fontes, EP.tr("De onde vêm estes números?", "Where do these numbers come from?")) + "</p>";
  }
  numeros();
  // um desenho 3D pequeno no cabeçalho de cada aba (enfeite: aria-hidden, sem clique; só anima o que está à vista, porque as
  // abas escondidas não são desenhadas)
  [["executivo", "palacio"], ["senado", "congresso"], ["camara", "congresso"], ["votacoes", "urna"], ["judiciario", "tribunal"]].forEach(function (x) {
    var cab = document.querySelector("#" + x[0] + " > .cab-bloco");
    if (!cab || !T[x[1]] || cab.querySelector(".d-ilu-sec")) return;
    var h = "";
    try { h = T[x[1]]({ auto: true, peq: true }); } catch (e) { h = ""; }
    if (h) cab.insertAdjacentHTML("beforeend", '<div class="d-ilu-sec" aria-hidden="true">' + h + "</div>");
  });

  // ---------- abas (js/abas.js): cada seção vira uma aba e monta o seu conteúdo na primeira vez que aparece ----------
  var comAbas = !!(EP.abas && EP.abas.monta({ nav: document.querySelector("nav.atalhos") }));
  var abre = comAbas ? EP.abas.quandoAbrir : function (id, fn) { fn(); };
  // a busca e o "Ver outro mandato" ficam juntos em cima das abas (no computador, lado a lado)
  if (comAbas) {
    var busca = document.getElementById("procurar"), lugar = document.getElementById("mandato-lugar");
    if (busca && lugar) {
      var topo = document.createElement("div");
      topo.className = "miolo topo-ferramentas";
      busca.parentNode.insertBefore(topo, busca);
      topo.appendChild(busca);
      topo.appendChild(lugar);
    }
  }
  // brasil.html#procurar (ex.: o link "Procurar um político" de outras páginas) leva direto ao campo da busca. Ao abrir a
  // página, o navegador tira o foco de tudo quando rola até o endereço: por isso, de novo depois do "load"
  function focaBusca() { if (location.hash === "#procurar") { var b = document.getElementById("busca"); if (b) b.focus(); } }
  window.addEventListener("hashchange", focaBusca);
  window.addEventListener("load", function () { setTimeout(focaBusca, 0); });
  focaBusca();

  // mandato que não é o de hoje: as mesmas abas, com os dados daquele período
  if (futuro || passado) {
    // "Como votaram": o site guarda só as votações do Congresso de hoje (antes do js/votacoes.js procurar #votos-recentes)
    var vr = document.getElementById("votos-recentes");
    if (vr && EP.hist) {
      vr.removeAttribute("id");
      vr.className = "";
      vr.innerHTML = EP.hist.votacoesSemDados(futuro);
      if (vr.nextElementSibling && vr.nextElementSibling.querySelector('a[href="votacoes.html"]')) vr.nextElementSibling.remove();
      EP.hist.desc("votacoes", EP.tr("Em cada votação, os senadores e os deputados dizem Sim ou Não a uma proposta.", "In each vote, senators and deputies say Yes or No to a proposal."));
    }
    if (futuro) X.brasilAbas({ abre: abre });
    else if (EP.hist) EP.hist.brasil(passado, { abre: abre });
    EP.ligaBusca(document.getElementById("busca"), document.getElementById("resultados"));
    D.rodapeErros(document.getElementById("links-erro"));
    EP.revelar();
    EP.paralaxe();
    return;
  }
  function falhou(el, pt, en) {
    el.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">⚠️</span>' +
      EP.tr("Não foi possível carregar " + pt + " agora. Tente de novo daqui a pouco.", "Could not load " + en + " right now. Please try again in a little while.") + "</div>";
  }
  function anos(m) {
    if (!m) return "";
    var a = (m.inicio || "").slice(0, 4), b = (m.fim || "").slice(0, 4);
    return a && b ? EP.tr("Mandato: " + a + " a " + b, "Term: " + a + " to " + b) : "";
  }

  // ---------- presidente e vice ----------
  function presidenteVice() {
    EP.json("dados/executivo.json").then(function (d) {
      var html = [d.presidente, d.vice].filter(Boolean).map(function (p) {
        return '<a class="pessoa-grande rev" href="pessoa.html?id=' + encodeURIComponent(p.id) + '">' + EP.av(p.foto, p.nome, null, true) +
          '<span><span class="cargo">' + esc(D.cargo(p.cargo)) + "</span><b>" + esc(p.nome) + "</b><small>" +
          [p.partido ? EP.pt(esc(p.partido)) : "", esc(anos(p.mandato))].filter(Boolean).join(" · ") + "</small>" +
          EP.chip2026(p.eleicao2026, p.genero, true) + '<span class="ver">' +
          EP.tr("Ver tudo sobre " + EP.gen(p.genero, "ele", "ela"), "See everything about " + EP.gen(p.genero, "him", "her")) + ' <span aria-hidden="true">›</span></span></span></a>';
      }).join("");
      if (!html) throw new Error("vazio");
      var el = document.getElementById("exec-topo");
      var f = [].concat(d.fontes || d.fonte || []);
      el.innerHTML = html + (f.length ? '<p class="fontes-exec">' + EP.botaoFontes(f) + "</p>" : "");
      EP.revelar(el);
    }).catch(function () { falhou(document.getElementById("exec-topo"), "os dados do presidente e do vice", "the data on the President and the Vice President"); });
  }

  // ---------- ministros ----------
  // site-d-r14 (protótipo D): todos os ministérios à vista, numa grade de ícones (o nome curto da área à vista; o nome inteiro e
  // quem comanda, para o leitor de tela e embaixo, em letra pequena), em ordem alfabética; tocar abre a gaveta com quem
  // comanda, desde quando, o que faz, o partido e as fontes (endereço brasil.html?ver=min:<id>)
  var MIN = [];
  function nomeMin(m) {
    var en = EP.en ? (m.ministerio_en || D.ministerio(m.ministerio)) : null;
    return { txt: en || m.ministerio || "", pt: EP.en && !en };
  }
  function nomeMinHtml(m) { var n = nomeMin(m); return n.pt ? EP.pt(esc(n.txt)) : esc(n.txt); }
  function areaHtml(m) { var n = nomeMin(m), a = EP.d.area(n.txt); return n.pt ? EP.pt(esc(a)) : esc(a); }
  // texto escrito à mão (em português, com **negrito**); no inglês usa o campo _en, se existir
  function textoManual(m, campo) {
    if (!m[campo]) return "";
    if (EP.en && !m[campo + "_en"]) return D.ptHtml(m[campo]);
    return EP.md(EP.campo(m, campo));
  }
  function partidoHtml(m) { return m.partido ? EP.pt(esc(m.partido)) : esc(EP.tr("Sem partido", "No party")); }
  function cartaoMin(m, k) {
    return '<button type="button" class="min-card d-min" data-min="' + k + '" aria-haspopup="dialog"><span class="m-ic" aria-hidden="true">' + esc(m.ic || "🏢") + '</span><span class="d-min-txt">' +
      '<span class="d-min-area" aria-hidden="true">' + areaHtml(m) + '</span><b class="sr">' + nomeMinHtml(m) + "</b>" +
      "<small>" + (m.vago ? esc(EP.tr("Cargo vago", "Vacant")) : EP.pt(esc(m.nome)) + '<span class="sr"> · ' + partidoHtml(m) + "</span>") + "</small>" +
      (m.interino ? '<span class="chip amarelo">' + EP.tr(EP.gen(m.genero, "Interino", "Interina"), "Acting") + "</span>" : "") + "</span></button>";
  }
  function idMin(m) { return String(m.id || EP.norm(m.ministerio || "").replace(/[^a-z0-9]+/g, "-")); }

  function ministros() {
    EP.json("dados/manual/ministros.json").then(function (d) {
      // em ordem alfabética do nome da área que aparece no ícone ("Agricultura e Pecuária", "Casa Civil", "Cultura"...)
      MIN = (d.ministerios || []).map(function (m) { return Object.assign({ _nome: EP.d.area(nomeMin(m).txt) }, m); });
      if (!MIN.length) throw new Error("vazio");
      MIN = EP.alfabetica(MIN, "_nome");
      document.getElementById("qtd-min").textContent = "(" + MIN.length + ")";
      var el = document.getElementById("ministros");
      el.classList.add("d-mins");
      el.innerHTML = MIN.map(cartaoMin).join("");
      if (d.atualizado) document.getElementById("fonte-min").innerHTML = '<small class="muted">' +
        EP.tr("Lista conferida em " + EP.data(d.atualizado) + ". Cada ministério tem a sua fonte (toque nele).", "List checked on " + EP.data(d.atualizado) + ". Each ministry has its own source (tap it).") + "</small>";
      EP.avisoMinistros(d).then(function (t) { if (t) el.insertAdjacentHTML("beforebegin", '<p class="aviso"><span aria-hidden="true">⚠️ </span>' + esc(t) + "</p>"); });
    }).catch(function () { falhou(document.getElementById("ministros"), "a lista de ministros", "the list of ministers"); });
  }
  abre("executivo", function () { presidenteVice(); ministros(); });

  function abreMin(m, de) {
    var cargo = EP.en ? "Minister" + (m.interino ? " (acting)" : "") : EP.gen(m.genero, "Ministro", "Ministra") + (m.interino ? EP.gen(m.genero, " (interino)", " (interina)") : "");
    var f = [].concat(m.fontes || m.fonte || []);
    function fato(ic, rot, val) { return '<li><span class="d-ic peq" aria-hidden="true">' + ic + "</span><span>" + esc(rot) + "</span><b>" + val + "</b></li>"; }
    EP.gaveta({ tit: '<span aria-hidden="true">' + esc(m.ic || "🏢") + " </span>" + nomeMinHtml(m), ver: "min:" + idMin(m),
      pagina: m.id && !m.vago ? { href: "pessoa.html?id=" + encodeURIComponent(m.id), t: EP.tr("Ver a página de ", "See the page about ") + m.nome } : null,
      corpo: '<div class="gv-min"><span class="d-min-ic-g" aria-hidden="true">' + esc(m.ic || "🏢") + "</span>" +
        (m.oQueFaz ? '<p class="gv-oque">' + textoManual(m, "oQueFaz") + "</p>" : "") + "</div>" +
        '<ul class="d-fatos">' + fato("👤", cargo, m.vago ? esc(EP.tr("Cargo vago", "Vacant")) : EP.pt(esc(m.nome))) + fato("🎗️", EP.tr("Partido", "Party"), partidoHtml(m)) +
        (m.desde ? fato("📅", EP.tr("No cargo desde", "In office since"), esc(EP.dataLonga(m.desde))) : "") + "</ul>" +
        (m.nota ? '<p class="aviso">' + textoManual(m, "nota") + "</p>" : "") +
        EP.d.saiba("<p>" + EP.tr("Ministros não são eleitos: o presidente escolhe cada um para cuidar de uma área do governo, e pode trocar quando quiser.",
          "Ministers are not elected: the President chooses each one to take care of an area of the government, and can replace them at any time.") + "</p>") +
        '<p class="gv-fonte">' + EP.botaoFontes(f) + "</p>" }, de);
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-min]");
    if (!b) return;
    var m = MIN[+b.getAttribute("data-min")];
    if (m) abreMin(m, b);
  });
  // brasil.html?ver=min:<id>: abre a gaveta do ministério quando a lista chega (a aba "Quem governa" carrega a lista)
  EP.gavetaVer.min = function (v) {
    var t0 = Date.now();
    if (EP.abas && EP.abas.mostra) EP.abas.mostra("executivo");
    (function tenta() {
      var k = -1;
      MIN.some(function (m, i) { if (idMin(m) === v) { k = i; return true; } return false; });
      if (k > -1) abreMin(MIN[k], document.querySelector('#ministros [data-min="' + k + '"]'));
      else if (Date.now() - t0 < 6000) setTimeout(tenta, 150);
    })();
  };

  // ---------- Senado e Câmara ----------
  // na página do Brasil, cada lista começa com um resumo (12 pessoas, em ordem alfabética) e o botão "Ver todos os 81
  // senadores" (js/casa.js, opções lote e verTodos); a lista de todos os partidos continua inteira
  function casa(id, arquivo, nomes, extra) {
    var el = document.querySelector("#" + id + " .casa-corpo");
    EP.json(arquivo).then(function (d) {
      EP.montaCasa(el, { membros: d.membros, porPartido: d.porPartido, nomes: nomes, fonte: d.fonte, atualizado: d.atualizado, extra: extra, lote: EP.RESUMO_CASA || 12, verTodos: true });
    }).catch(function () { falhou(el, "esta lista", "this list"); });
  }
  abre("senado", function () {
    casa("senado", "dados/senado.json", { um: EP.tr("senador", "senator"), uma: EP.tr("senadora", "senator"), varios: EP.tr("senadores", "senators"), varias: EP.tr("senadoras", "senators") },
      function (m) { return m.fimMandato ? EP.tr("Mandato até ", "Term ends in ") + String(m.fimMandato).slice(0, 4) : ""; });
  });
  abre("camara", function () {
    casa("camara", "dados/camara.json", { um: EP.tr("deputado", "deputy"), uma: EP.tr("deputada", "deputy"), varios: EP.tr("deputados", "deputies"), varias: EP.tr("deputadas", "deputies") });
  });
  // eleitos 2026 (até a posse): "Quem assume em 2027" é o mandato 2027 do "Ver outro mandato" (brasil.html?mandato=2027).
  // Nas abas de hoje, um aviso curto leva para lá (só enquanto houver eleitos sem posse)
  if (X) X.avisos("BR", [["presidencia", "executivo", "#executivo"], ["senado", "senado", "#senado"], ["camara", "camara", "#camara"]]);

  // ---------- busca e rodapé ----------
  EP.ligaBusca(document.getElementById("busca"), document.getElementById("resultados"));
  D.rodapeErros(document.getElementById("links-erro"));
  EP.revelar();
  EP.paralaxe();
})();
