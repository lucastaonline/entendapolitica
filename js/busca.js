/* Busca de políticos (lê dados/busca.json na primeira vez que a pessoa digita).
   Linhas do arquivo: [id, nome, cargo curto, UF, partido, cidade|null]
   Acessibilidade: a lista de resultados não é "ao vivo" (seria lida inteira a cada letra); um aviso escondido diz quantos foram achados.
   Teclado: seta para baixo vai do campo para os resultados; setas andam entre eles; Esc volta para o campo. */
(function () {
  "use strict";
  var EP = window.EP;
  var LIMITE = 12;
  var promessa = null;

  function carregar() {
    if (!promessa) {
      promessa = EP.json("dados/busca.json").then(function (linhas) {
        return linhas.map(function (l) {
          var uf = l[3] || "";
          var extra = [l[2], uf, EP.UFS[uf], l[4], l[5]];
          if (EP.en) extra.push(EP.cargo(l[2]));
          return { id: l[0], nome: l[1], cargo: l[2], uf: uf, partido: l[4], cidade: l[5], n: EP.norm(l[1]), resto: EP.norm(extra.join(" ")) };
        });
      });
      promessa.catch(function () { promessa = null; });
    }
    return promessa;
  }

  function procurar(lista, q) {
    var termos = EP.norm(q).split(/\s+/).filter(Boolean);
    if (!termos.length) return [];
    var res = [];
    lista.forEach(function (p) {
      var pontos = 0;
      for (var i = 0; i < termos.length; i++) {
        var t = termos[i];
        var noNome = p.n.indexOf(t);
        if (noNome === 0 || p.n.indexOf(" " + t) > -1) pontos += 3;
        else if (noNome > -1) pontos += 2;
        else if ((" " + p.resto + " ").indexOf(" " + t) > -1) pontos += 1;
        else return;
      }
      res.push({ p: p, pontos: pontos });
    });
    res.sort(function (a, b) { return b.pontos - a.pontos || a.p.n.localeCompare(b.p.n); });
    return res.map(function (r) { return r.p; });
  }

  function linhaHtml(p) {
    var onde = p.cidade ? p.cidade + " (" + p.uf + ")" : (EP.UFS[p.uf] || p.uf || EP.tr("Brasil", "Brazil"));
    return '<li><a href="pessoa.html?id=' + encodeURIComponent(p.id) + '">' + EP.av(null, p.nome) +
      "<span><b>" + EP.esc(p.nome) + "</b><small>" + EP.esc(EP.cargo(p.cargo)) + (p.partido ? " · " + EP.pt(EP.esc(p.partido)) : "") + " · " + EP.esc(onde) + "</small></span></a></li>";
  }

  EP.ligaBusca = function (input, saida) {
    if (!input || !saida) return;
    saida.removeAttribute("aria-live");
    var aviso = document.createElement("p");
    aviso.className = "sr";
    aviso.setAttribute("role", "status");
    aviso.setAttribute("aria-live", "polite");
    saida.parentNode.insertBefore(aviso, saida);
    function avisa(txt) { if (aviso.textContent !== txt) aviso.textContent = txt; }
    var t = null;
    function roda() {
      var q = input.value.trim();
      if (q.length < 2) { saida.innerHTML = ""; avisa(""); return; }
      carregar().then(function (lista) {
        if (input.value.trim() !== q) return;
        var r = procurar(lista, q);
        if (!r.length) {
          saida.innerHTML = '<li class="mais-res">' + EP.tr('Ninguém encontrado com "' + EP.esc(q) + '". Confira se o nome está escrito certo.',
            'No one found for "' + EP.esc(q) + '". Check the spelling.') + "</li>";
          avisa(EP.tr("Ninguém encontrado.", "No one found."));
          return;
        }
        saida.innerHTML = r.slice(0, LIMITE).map(linhaHtml).join("") +
          (r.length > LIMITE ? '<li class="mais-res">' + EP.tr("E mais " + EP.num(r.length - LIMITE) + ". Digite mais letras para achar mais rápido.",
            "And " + EP.num(r.length - LIMITE) + " more. Type more letters to narrow it down.") + "</li>" : "");
        avisa(r.length === 1 ? EP.tr("1 pessoa encontrada.", "1 person found.") :
          r.length > LIMITE ? EP.tr(EP.num(r.length) + " pessoas encontradas. Mostrando as " + LIMITE + " primeiras.", EP.num(r.length) + " people found. Showing the first " + LIMITE + ".") :
            EP.tr(EP.num(r.length) + " pessoas encontradas.", EP.num(r.length) + " people found."));
      }).catch(function () {
        saida.innerHTML = '<li class="mais-res">' + EP.tr("A lista de nomes ainda não está disponível. Tente de novo daqui a pouco.", "The list of names is not available yet. Please try again in a little while.") + "</li>";
        avisa(EP.tr("A lista de nomes ainda não está disponível.", "The list of names is not available yet."));
      });
    }
    input.addEventListener("input", function () { clearTimeout(t); t = setTimeout(roda, 180); });
    input.addEventListener("focus", function () { carregar().catch(function () {}); }, { once: true });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") {
        var a = saida.querySelector("a");
        if (a) { e.preventDefault(); a.focus(); }
      }
    });
    saida.addEventListener("keydown", function (e) {
      var links = [].slice.call(saida.querySelectorAll("a")), i = links.indexOf(document.activeElement);
      if (i < 0) return;
      if (e.key === "ArrowDown" && i < links.length - 1) { e.preventDefault(); links[i + 1].focus(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); (i > 0 ? links[i - 1] : input).focus(); }
      else if (e.key === "Escape") { e.preventDefault(); input.focus(); }
    });
  };
})();
