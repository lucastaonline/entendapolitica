/* A política do Brasil: presidente, vice, ministros, Senado e Câmara. */
(function () {
  "use strict";
  var EP = window.EP, T = window.TRES || {}, D = EP.trd;
  var esc = EP.esc;

  D.canonico();
  if (T.tresPoderes) document.getElementById("ilu-poderes").innerHTML = T.tresPoderes();
  EP.fundo3d([["cubo", "4%", "12%", 40, 0, 0, 18], ["esfera", "93%", "8%", 36, 3, 0, 7], ["anel", "90%", "50%", 56, 2, 0, 20], ["esfera", "3%", "70%", 30, 6, 0, 8]], document.body);
  // mandato anterior (brasil.html?mandato=2019): quem monta a página do passado é o js/historico.js
  if (EP.hist && EP.hist.param()) { EP.hist.brasil(EP.hist.param()); return; }
  if (EP.hist) EP.hist.seletor(document.getElementById("mandato-lugar"), "brasil");

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

  // ---------- ministros ----------
  var MIN = [];
  function nomeMin(m) {
    var en = EP.en ? (m.ministerio_en || D.ministerio(m.ministerio)) : null;
    return { txt: en || m.ministerio || "", pt: EP.en && !en };
  }
  function nomeMinHtml(m) { var n = nomeMin(m); return n.pt ? EP.pt(esc(n.txt)) : esc(n.txt); }
  // texto escrito à mão (em português, com **negrito**); no inglês usa o campo _en, se existir
  function textoManual(m, campo) {
    if (!m[campo]) return "";
    if (EP.en && !m[campo + "_en"]) return D.ptHtml(m[campo]);
    return EP.md(EP.campo(m, campo));
  }
  function partidoHtml(m) { return m.partido ? EP.pt(esc(m.partido)) : esc(EP.tr("Sem partido", "No party")); }

  EP.json("dados/manual/ministros.json").then(function (d) {
    MIN = (d.ministerios || []).map(function (m) { return Object.assign({ _nome: nomeMin(m).txt }, m); });
    if (!MIN.length) throw new Error("vazio");
    MIN = EP.alfabetica(MIN, "_nome");
    document.getElementById("qtd-min").textContent = "(" + MIN.length + ")";
    var el = document.getElementById("ministros");
    el.innerHTML = MIN.map(function (m, k) {
      return '<button type="button" class="min-card" data-min="' + k + '" aria-haspopup="dialog"><span class="m-ic" aria-hidden="true">' + esc(m.ic || "🏢") + "</span><span><b>" + nomeMinHtml(m) + "</b>" +
        "<small>" + (m.vago ? esc(EP.tr("Cargo vago", "Vacant")) : esc(m.nome) + " · " + partidoHtml(m)) + "</small>" +
        (m.interino ? '<span class="chip amarelo">' + EP.tr(EP.gen(m.genero, "Interino", "Interina"), "Acting") + "</span>" : "") + "</span></button>";
    }).join("");
    if (d.atualizado) document.getElementById("fonte-min").innerHTML = '<small class="muted">' +
      EP.tr("Lista conferida em " + EP.data(d.atualizado) + ". Cada ministério tem a sua fonte (toque nele).", "List checked on " + EP.data(d.atualizado) + ". Each ministry has its own source (tap it).") + "</small>";
    EP.avisoMinistros(d).then(function (t) { if (t) el.insertAdjacentHTML("beforebegin", '<p class="aviso"><span aria-hidden="true">⚠️ </span>' + esc(t) + "</p>"); });
  }).catch(function () { falhou(document.getElementById("ministros"), "a lista de ministros", "the list of ministers"); });

  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-min]");
    if (!b) return;
    var m = MIN[+b.getAttribute("data-min")];
    if (!m) return;
    var cargo = EP.en ? "Minister" + (m.interino ? " (acting)" : "") : EP.gen(m.genero, "Ministro", "Ministra") + (m.interino ? EP.gen(m.genero, " (interino)", " (interina)") : "");
    var f = [].concat(m.fontes || m.fonte || []);
    EP.abrir('<span aria-hidden="true">' + esc(m.ic || "🏢") + " </span>" + nomeMinHtml(m),
      (m.oQueFaz ? '<p class="lead">' + textoManual(m, "oQueFaz") + "</p>" : "") +
      '<div class="fatos">' +
      '<div class="fato"><span class="f-ic" aria-hidden="true">👤</span><span class="f-rot">' + esc(cargo) + '</span><span class="f-val">' + esc(m.vago ? EP.tr("Cargo vago", "Vacant") : m.nome) + "</span></div>" +
      '<div class="fato"><span class="f-ic" aria-hidden="true">🎗️</span><span class="f-rot">' + EP.tr("Partido", "Party") + '</span><span class="f-val">' + partidoHtml(m) + "</span></div>" +
      (m.desde ? '<div class="fato"><span class="f-ic" aria-hidden="true">📅</span><span class="f-rot">' + EP.tr("No cargo desde", "In office since") + '</span><span class="f-val">' + EP.dataLonga(m.desde) + "</span></div>" : "") +
      "</div>" + (m.nota ? '<p class="aviso">' + textoManual(m, "nota") + "</p>" : "") +
      (m.id && !m.vago ? '<p><a class="btn peq claro" href="pessoa.html?id=' + encodeURIComponent(m.id) + '">' + EP.tr("Ver a página de ", "See the page about ") + esc(m.nome) + ' <span aria-hidden="true">›</span></a></p>' : "") +
      '<h3><span aria-hidden="true">📚 </span>' + EP.tr("Fontes", "Sources") + "</h3>" + EP.fontesHtml(f));
  });

  // ---------- Senado e Câmara ----------
  function casa(id, arquivo, nomes, extra) {
    var el = document.querySelector("#" + id + " .casa-corpo");
    EP.json(arquivo).then(function (d) {
      EP.montaCasa(el, { membros: d.membros, porPartido: d.porPartido, nomes: nomes, fonte: d.fonte, atualizado: d.atualizado, extra: extra });
    }).catch(function () { falhou(el, "esta lista", "this list"); });
  }
  casa("senado", "dados/senado.json", { um: EP.tr("senador", "senator"), uma: EP.tr("senadora", "senator"), varios: EP.tr("senadores", "senators"), varias: EP.tr("senadoras", "senators") },
    function (m) { return m.fimMandato ? EP.tr("Mandato até ", "Term ends in ") + String(m.fimMandato).slice(0, 4) : ""; });
  casa("camara", "dados/camara.json", { um: EP.tr("deputado", "deputy"), uma: EP.tr("deputada", "deputy"), varios: EP.tr("deputados", "deputies"), varias: EP.tr("deputadas", "deputies") });
  if (EP.eleitos) EP.eleitos.brasil(document.getElementById("proximos-brasil"));  // eleitos 2026 (até a posse): "Quem assume em 2027"

  // ---------- busca e rodapé ----------
  EP.ligaBusca(document.getElementById("busca"), document.getElementById("resultados"));
  D.rodapeErros(document.getElementById("links-erro"));
  EP.revelar();
  EP.paralaxe();
})();
