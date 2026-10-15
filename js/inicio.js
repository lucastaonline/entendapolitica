/* Página inicial: Congresso em 3D, cubos das 3 portas, busca, compartilhar. */
(function () {
  "use strict";
  var EP = window.EP, T = window.TRES;
  var SITE = "https://entendapolitica.vercel.app/";
  var CONFIG = window.EP_CONFIG || {};

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
  var l = [];
  if (CONFIG.formularioErros) l.push('🔎 Viu algo errado ou que parece puxar para um lado? <a href="' + EP.esc(CONFIG.formularioErros) + '" target="_blank" rel="noopener">Avise aqui</a>');
  if (CONFIG.formularioRespostas) l.push('<a href="' + EP.esc(CONFIG.formularioRespostas) + '" target="_blank" rel="noopener">Ver o que as pessoas avisaram</a>');
  document.getElementById("links-erro").innerHTML = l.join(" · ");

  // ---------- compartilhar ----------
  var TXT = "A política do Brasil explicada de um jeito fácil: como funciona, quem está no poder e o que cada político propôs. Tudo com fonte:";
  function link(origem) { return SITE + "?utm_source=" + origem + "&utm_medium=compartilhar"; }
  document.getElementById("btn-compartilhar").addEventListener("click", function () {
    EP.track("compartilhar_abriu");
    if (navigator.share && /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent)) {
      navigator.share({ title: document.title, text: TXT, url: link("celular") }).catch(function () {});
      return;
    }
    var wa = "https://wa.me/?text=" + encodeURIComponent(TXT + " " + link("whatsapp"));
    var tg = "https://t.me/share/url?url=" + encodeURIComponent(link("telegram")) + "&text=" + encodeURIComponent(TXT);
    var fb = "https://www.facebook.com/sharer/sharer.php?u=" + encodeURIComponent(link("facebook"));
    EP.abrir("📤 Compartilhar o site",
      "<p>Escolha por onde mandar.</p>" +
      '<div class="opcoes-comp">' +
      '<a class="btn" style="background:#25d366;color:#08311a;box-shadow:0 5px 0 #179a4a" href="' + EP.esc(wa) + '" target="_blank" rel="noopener">💬 WhatsApp</a>' +
      '<a class="btn claro" href="' + EP.esc(tg) + '" target="_blank" rel="noopener">✈️ Telegram</a>' +
      '<a class="btn claro" href="' + EP.esc(fb) + '" target="_blank" rel="noopener">👍 Facebook</a>' +
      '<button class="btn bege" type="button" id="copiar-link">🔗 Copiar o link</button>' +
      '<p class="link-copia" id="link-copia" hidden></p></div>');
    document.getElementById("copiar-link").addEventListener("click", function () {
      var u = link("link"), b = this, caixa = document.getElementById("link-copia");
      function ok() { b.textContent = "✅ Link copiado! É só colar onde quiser."; }
      function mostra() { caixa.hidden = false; caixa.textContent = u; b.textContent = "Copie o link abaixo:"; }
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(u).then(ok, mostra);
      else mostra();
    });
  });

  EP.revelar();
  EP.paralaxe();
})();
