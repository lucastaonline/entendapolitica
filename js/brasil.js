/* A política do Brasil: presidente, vice, ministros, Senado e Câmara. */
(function () {
  "use strict";
  var EP = window.EP, T = window.TRES || {};
  var CONFIG = window.EP_CONFIG || {};

  if (T.tresPoderes) document.getElementById("ilu-poderes").innerHTML = T.tresPoderes();
  EP.fundo3d([["cubo", "4%", "12%", 40, 0, 0, 18], ["esfera", "93%", "8%", 36, 3, 0, 7], ["anel", "90%", "50%", 56, 2, 0, 20], ["esfera", "3%", "70%", 30, 6, 0, 8]], document.body);

  function falhou(el, oque) {
    el.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">🛠️</span>Ainda estamos juntando ' + oque + ". Volte daqui a pouco.</div>";
  }
  function anos(m) {
    if (!m) return "";
    var a = (m.inicio || "").slice(0, 4), b = (m.fim || "").slice(0, 4);
    return a && b ? "Mandato: " + a + " a " + b : "";
  }

  // ---------- presidente e vice ----------
  EP.json("dados/executivo.json").then(function (d) {
    var html = [d.presidente, d.vice].filter(Boolean).map(function (p) {
      return '<a class="pessoa-grande rev" href="pessoa.html?id=' + encodeURIComponent(p.id) + '">' + EP.av(p.foto, p.nome, null, true) +
        '<span><span class="cargo">' + EP.esc(p.cargo) + "</span><b>" + EP.esc(p.nome) + "</b><small>" + EP.esc([p.partido, anos(p.mandato)].filter(Boolean).join(" · ")) + "</small>" +
        EP.chip2026(p.eleicao2026, p.genero, true) + '<span class="ver">Ver tudo sobre ' + EP.gen(p.genero, "ele", "ela") + " ›</span></span></a>";
    }).join("");
    var el = document.getElementById("exec-topo");
    el.innerHTML = html + (d.fontes ? '<p style="grid-column:1/-1;margin:0">' + EP.botaoFontes(d.fontes) + "</p>" : "");
    EP.revelar(el);
  }).catch(function () { falhou(document.getElementById("exec-topo"), "os dados do presidente e do vice"); });

  // ---------- ministros ----------
  var MIN = [];
  EP.json("dados/manual/ministros.json").then(function (d) {
    MIN = EP.alfabetica(d.ministerios || [], "ministerio");
    document.getElementById("qtd-min").textContent = "(" + MIN.length + ")";
    var el = document.getElementById("ministros");
    el.innerHTML = MIN.map(function (m, k) {
      return '<button type="button" class="min-card" data-min="' + k + '"><span class="m-ic" aria-hidden="true">' + EP.esc(m.ic || "🏢") + "</span><span><b>" + EP.esc(m.ministerio) + "</b>" +
        "<small>" + EP.esc(m.vago ? "Cargo vago" : m.nome) + (m.partido ? " · " + EP.esc(m.partido) : m.vago ? "" : " · Sem partido") + "</small>" +
        (m.interino ? '<span class="chip amarelo">' + EP.gen(m.genero, "Interino", "Interina") + "</span>" : "") + "</span></button>";
    }).join("");
    if (d.atualizado) document.getElementById("fonte-min").innerHTML = '<small class="muted">Lista conferida em ' + EP.data(d.atualizado) + ". Cada ministério tem a sua fonte (toque nele).</small>";
  }).catch(function () { falhou(document.getElementById("ministros"), "a lista de ministros"); });
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-min]");
    if (!b) return;
    var m = MIN[+b.getAttribute("data-min")];
    EP.abrir(EP.esc((m.ic || "") + " " + m.ministerio),
      (m.oQueFaz ? '<p class="lead">' + EP.md(m.oQueFaz) + "</p>" : "") +
      '<div class="fatos">' +
      '<div class="fato"><span class="f-ic">👤</span><span class="f-rot">' + EP.gen(m.genero, "Ministro", "Ministra") + (m.interino ? EP.gen(m.genero, " (interino)", " (interina)") : "") + '</span><span class="f-val">' + EP.esc(m.vago ? "Cargo vago" : m.nome) + "</span></div>" +
      '<div class="fato"><span class="f-ic">🎗️</span><span class="f-rot">Partido</span><span class="f-val">' + EP.esc(m.partido || "Sem partido") + "</span></div>" +
      (m.desde ? '<div class="fato"><span class="f-ic">📅</span><span class="f-rot">No cargo desde</span><span class="f-val">' + EP.dataLonga(m.desde) + "</span></div>" : "") +
      "</div>" + (m.nota ? '<p class="aviso">' + EP.md(m.nota) + "</p>" : "") +
      "<h3>📚 Fontes</h3>" + EP.fontesHtml(m.fonte));
  });

  // ---------- Senado e Câmara ----------
  function casa(id, arquivo, nomes, extra, nota) {
    var el = document.querySelector("#" + id + " .casa-corpo");
    EP.json(arquivo).then(function (d) {
      EP.montaCasa(el, { membros: d.membros, porPartido: d.porPartido, nomes: nomes, fonte: d.fonte, atualizado: d.atualizado, extra: extra, notaPlenario: nota });
    }).catch(function () { falhou(el, "esta lista"); });
  }
  casa("senado", "dados/senado.json", { um: "senador", uma: "senadora", varios: "senadores", varias: "senadoras" },
    function (m) { return m.fimMandato ? "Mandato até " + String(m.fimMandato).slice(0, 4) : ""; }, "");
  casa("camara", "dados/camara.json", { um: "deputado", uma: "deputada", varios: "deputados", varias: "deputadas" }, null, "");

  // ---------- busca e rodapé ----------
  EP.ligaBusca(document.getElementById("busca"), document.getElementById("resultados"));
  if (CONFIG.formularioErros) document.getElementById("links-erro").innerHTML = '🔎 Viu algo errado ou que parece puxar para um lado? <a href="' + EP.esc(CONFIG.formularioErros) + '" target="_blank" rel="noopener">Avise aqui</a>';
  EP.revelar();
  EP.paralaxe();
})();
