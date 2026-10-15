/* Página inicial: Congresso em 3D, cubos das 3 portas, busca, compartilhar. */
(function () {
  "use strict";
  var EP = window.EP, T = window.TRES;
  var esc = EP.esc;
  var SITE = "https://entendapolitica.vercel.app/";
  var CONFIG = window.EP_CONFIG || {};

  // a versão em inglês é o mesmo endereço com ?lang=en
  if (EP.en) {
    var can = document.querySelector('link[rel="canonical"]');
    if (can) can.href = SITE + "?lang=en";
  }

  if (T) {
    document.getElementById("congresso").innerHTML = T.congresso({ auto: true, rotulos: true });
    document.querySelectorAll("[data-cubo]").forEach(function (el) {
      var p = el.getAttribute("data-cubo").split("|");
      el.innerHTML = T.cubo(p[0], p[1], "lento", 64);
    });
    EP.fundo3d([["cubo", "4%", "10%", 46, 0, 0, 18], ["esfera", "92%", "7%", 40, 3, 0, 7], ["anel", "88%", "44%", 64, 2, 0, 20],
      ["esfera", "3%", "55%", 34, 6, 0, 8], ["cubo", "94%", "80%", 34, 5, 0, 14], ["anel", "6%", "88%", 44, 1, 0, 16]], document.body);
  }

  // ---------- busca ----------
  EP.ligaBusca(document.getElementById("busca"), document.getElementById("resultados"));

  // ---------- formulário de erros (links em js/config.js, quando existirem) ----------
  var novaAba = '<span class="sr"> ' + EP.tr("(abre em outra aba)", "(opens in a new tab)") + "</span>";
  var l = ['<span aria-hidden="true">🔎 </span>' + EP.tr("Viu algo errado ou que parece puxar para um lado?", "Did you see something wrong, or something that seems to take sides?") + " " +
    (CONFIG.formularioErros ? '<a href="' + esc(CONFIG.formularioErros) + '" target="_blank" rel="noopener">' + EP.tr("Avise aqui", "Let us know here") + novaAba + "</a>" :
      '<a href="imparcialidade.html#avisar">' + EP.tr("Veja como avisar", "See how to tell us") + "</a>")];
  if (CONFIG.formularioRespostas) l.push('<a href="' + esc(CONFIG.formularioRespostas) + '" target="_blank" rel="noopener">' + EP.tr("Ver o que as pessoas avisaram", "See what people reported") + novaAba + "</a>");
  document.getElementById("links-erro").innerHTML = l.join(" · ");

  // ---------- compartilhar (a janela é a mesma do mapa: EP.compartilhar, em js/comum.js) ----------
  document.getElementById("btn-compartilhar").addEventListener("click", function () { EP.compartilhar("inicio"); });

  EP.revelar();
  EP.paralaxe();
})();
