/* Busca de políticos (lê dados/busca.json na primeira vez que a pessoa digita).
   Linhas do arquivo: [id, nome, cargo curto, UF, partido, cidade|null] */
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
          return { id: l[0], nome: l[1], cargo: l[2], uf: uf, partido: l[4], cidade: l[5],
            n: EP.norm(l[1]), resto: EP.norm([l[2], uf, EP.UFS[uf], l[4], l[5]].join(" ")) };
        });
      });
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
    var onde = p.cidade ? p.cidade + " (" + p.uf + ")" : (EP.UFS[p.uf] || p.uf || "Brasil");
    return '<li><a href="pessoa.html?id=' + encodeURIComponent(p.id) + '">' + EP.av(null, p.nome) +
      "<span><b>" + EP.esc(p.nome) + "</b><small>" + EP.esc(p.cargo) + (p.partido ? " · " + EP.esc(p.partido) : "") + " · " + EP.esc(onde) + "</small></span></a></li>";
  }

  EP.ligaBusca = function (input, saida) {
    if (!input || !saida) return;
    var t = null;
    function roda() {
      var q = input.value.trim();
      if (q.length < 2) { saida.innerHTML = ""; return; }
      carregar().then(function (lista) {
        if (input.value.trim() !== q) return;
        var r = procurar(lista, q);
        if (!r.length) { saida.innerHTML = '<li class="mais-res">Ninguém encontrado com "' + EP.esc(q) + '". Confira se o nome está escrito certo.</li>'; return; }
        saida.innerHTML = r.slice(0, LIMITE).map(linhaHtml).join("") +
          (r.length > LIMITE ? '<li class="mais-res">E mais ' + EP.num(r.length - LIMITE) + ". Digite mais letras para achar mais rápido.</li>" : "");
      }).catch(function () {
        saida.innerHTML = '<li class="mais-res">A lista de nomes ainda não está disponível. Tente de novo daqui a pouco.</li>';
      });
    }
    input.addEventListener("input", function () { clearTimeout(t); t = setTimeout(roda, 160); });
    input.addEventListener("focus", function () { carregar().catch(function () {}); }, { once: true });
  };
})();
