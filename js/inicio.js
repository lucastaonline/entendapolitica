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

  // ---------- compartilhar (no inglês, o texto e os links vão em inglês, com ?lang=en) ----------
  var TXT = EP.tr("A política do Brasil explicada de um jeito fácil: como funciona, quem está no poder e o que cada político propôs. Tudo com fonte:",
    "Brazilian politics made easy: how it works, who is in power and what each politician proposed. Everything with sources:");
  function link(origem) { return SITE + "?" + (EP.en ? "lang=en&" : "") + "utm_source=" + origem + "&utm_medium=compartilhar"; }
  document.getElementById("btn-compartilhar").addEventListener("click", function () {
    EP.track("compartilhar_abriu");
    if (navigator.share && /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent)) {
      navigator.share({ title: document.title, text: TXT, url: link("celular") }).catch(function () {});
      return;
    }
    var wa = "https://wa.me/?text=" + encodeURIComponent(TXT + " " + link("whatsapp"));
    var tg = "https://t.me/share/url?url=" + encodeURIComponent(link("telegram")) + "&text=" + encodeURIComponent(TXT);
    var fb = "https://www.facebook.com/sharer/sharer.php?u=" + encodeURIComponent(link("facebook"));
    function op(url, ic, nome, classe, estilo) {
      return '<a class="btn ' + classe + '"' + (estilo ? ' style="' + estilo + '"' : "") + ' href="' + esc(url) + '" target="_blank" rel="noopener"><span aria-hidden="true">' + ic + " </span>" + nome + novaAba + "</a>";
    }
    EP.abrir('<span aria-hidden="true">📤 </span>' + EP.tr("Compartilhar o site", "Share the site"),
      "<p>" + EP.tr("Escolha por onde mandar.", "Choose how to send it.") + "</p>" +
      '<div class="opcoes-comp">' +
      op(wa, "💬", "WhatsApp", "", "background:#25d366;color:#08311a;box-shadow:0 5px 0 #179a4a") +
      op(tg, "✈️", "Telegram", "claro") + op(fb, "👍", "Facebook", "claro") +
      '<button class="btn bege" type="button" id="copiar-link"><span aria-hidden="true">🔗 </span>' + EP.tr("Copiar o link", "Copy the link") + "</button>" +
      '<p class="link-copia" id="link-copia" hidden></p><p class="sr" id="aviso-copia" role="status" aria-live="polite"></p></div>');
    document.getElementById("copiar-link").addEventListener("click", function () {
      var u = link("link"), b = this, caixa = document.getElementById("link-copia"), aviso = document.getElementById("aviso-copia");
      function ok() {
        b.innerHTML = '<span aria-hidden="true">✅ </span>' + EP.tr("Link copiado! É só colar onde quiser.", "Link copied! Just paste it wherever you want.");
        aviso.textContent = EP.tr("Link copiado.", "Link copied.");
      }
      function mostra() {
        caixa.hidden = false;
        caixa.textContent = u;
        b.textContent = EP.tr("Copie o link abaixo:", "Copy the link below:");
        aviso.textContent = EP.tr("Não deu para copiar sozinho. O link está escrito abaixo do botão.", "It could not be copied automatically. The link is written below the button.");
      }
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(u).then(ok, mostra);
      else mostra();
    });
  });

  EP.revelar();
  EP.paralaxe();
})();
