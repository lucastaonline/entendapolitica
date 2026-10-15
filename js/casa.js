/* Bloco de uma casa legislativa: plenário 3D, quantos de cada partido, filtros e a grade de pessoas.
   Usado para Senado, Câmara, Assembleias (deputados estaduais) e Câmaras Municipais (vereadores). */
(function () {
  "use strict";
  var EP = window.EP, T = window.TRES || {};

  // (o desenho das fileiras fica em TRES.plenario)

  EP.montaCasa = function (el, o) {
    var membros = EP.alfabetica(o.membros || []);
    var nomes = o.nomes || { um: "pessoa", uma: "pessoa", varios: "pessoas", varias: "pessoas" };
    var porPartido = o.porPartido;
    if (!porPartido) {
      var cont = {};
      membros.forEach(function (m) { var p = m.partido || "Sem partido"; cont[p] = (cont[p] || 0) + 1; });
      porPartido = Object.keys(cont).map(function (p) { return { partido: p, n: cont[p] }; });
    }
    porPartido = porPartido.slice().sort(function (a, b) { return b.n - a.n || EP.norm(a.partido).localeCompare(EP.norm(b.partido)); });
    var idxPartido = {};
    porPartido.forEach(function (p, k) { idxPartido[p.partido] = k; });
    var total = membros.length;
    var maxN = porPartido.length ? porPartido[0].n : 1;
    var VIS = 8;

    var plen = T.plenario ? T.plenario({ total: total, grupos: porPartido.map(function (p) { return p.n; }), max: total > 300 ? 520 : total > 60 ? 440 : 380 }) : "";

    var mulheres = membros.filter(function (m) { return m.genero === "F"; }).length;
    var homens = membros.filter(function (m) { return m.genero === "M"; }).length;
    var ufs = {};
    membros.forEach(function (m) { if (m.uf) ufs[m.uf] = 1; });
    var listaUF = Object.keys(ufs).sort(function (a, b) { return EP.norm(EP.UFS[a] || a).localeCompare(EP.norm(EP.UFS[b] || b)); });

    el.innerHTML =
      '<div class="casa-resumo"><div class="plen-box rev">' + plen + "<p>Cada cadeira é um" + (nomes.um === "pessoa" ? "a pessoa" : " " + nomes.um) + ". " + EP.esc(o.notaPlenario || "") + "</p></div>" +
      '<div class="partidos rev" style="--i:1"><div class="tit-p">Quantos de cada partido</div>' +
      porPartido.map(function (p, k) {
        return '<button type="button" class="barra-partido" data-g="' + k + '"' + (k >= VIS ? " hidden" : "") + ' aria-pressed="false" title="Mostrar só ' + EP.esc(p.partido) + '">' +
          '<span class="nome-p">' + EP.esc(p.partido) + '</span><span class="trilho-p"><i data-w="' + (100 * p.n / maxN).toFixed(1) + '%"></i></span><span class="n-p">' + p.n + "</span></button>";
      }).join("") +
      (porPartido.length > VIS ? '<button type="button" class="mais-p">Ver todos os ' + porPartido.length + " partidos ▾</button>" : "") +
      '<p class="explica-p">Partido é um grupo de pessoas que se juntam para disputar eleições e defender ideias parecidas. Toque num partido para ver só quem é dele. Todos os partidos têm a mesma cor aqui, de propósito.</p></div></div>' +
      (mulheres + homens ? '<p class="sabia rev"><span aria-hidden="true">💡</span><span>Você sabia? Hoje são <b>' + EP.plural(mulheres, nomes.uma, nomes.varias) + "</b> e <b>" + EP.plural(homens, nomes.um, nomes.varios) + "</b>.</span></p>" : "") +
      '<div class="filtros-casa"><div class="busca"><input type="search" class="f-nome" placeholder="Procurar pelo nome" aria-label="Procurar pelo nome" autocomplete="off"></div>' +
      (o.filtroUF !== false && listaUF.length > 1 ? '<select class="f-uf" aria-label="Filtrar por estado"><option value="">Todos os estados</option>' +
        listaUF.map(function (u) { return '<option value="' + u + '">' + EP.esc(EP.UFS[u] || u) + "</option>"; }).join("") + "</select>" : "<span></span>") +
      '<select class="f-partido" aria-label="Filtrar por partido"><option value="">Todos os partidos</option>' +
      EP.alfabetica(porPartido, "partido").map(function (p) { return '<option value="' + EP.esc(p.partido) + '">' + EP.esc(p.partido) + " (" + p.n + ")</option>"; }).join("") + "</select></div>" +
      '<p class="contagem" aria-live="polite"></p><div class="grade-pessoas"></div>' +
      (o.fonte ? '<p style="margin-top:14px">' + EP.botaoFontes(o.fonte, "De onde vem esta lista?") + (o.atualizado ? ' <small class="muted">Atualizado em ' + EP.data(o.atualizado) + "</small>" : "") + "</p>" : "");

    var fNome = el.querySelector(".f-nome"), fUF = el.querySelector(".f-uf"), fPart = el.querySelector(".f-partido");
    var grade = el.querySelector(".grade-pessoas"), contagem = el.querySelector(".contagem"), plenEl = el.querySelector(".plenario");
    var LOTE = 60, mostrando = LOTE;

    function filtrados() {
      var q = EP.norm(fNome.value), uf = fUF ? fUF.value : "", pa = fPart.value;
      return membros.filter(function (m) {
        return (!q || EP.norm(m.nome).indexOf(q) > -1 || EP.norm(m.nomeCivil || "").indexOf(q) > -1) && (!uf || m.uf === uf) && (!pa || (m.partido || "Sem partido") === pa);
      });
    }
    function desenha() {
      var l = filtrados();
      var vis = l.slice(0, mostrando);
      grade.innerHTML = vis.length ? vis.map(function (m) { return EP.cartaoPessoa(m, o.extra ? o.extra(m) : ""); }).join("") :
        '<div class="vazio"><span class="grande" aria-hidden="true">🤷</span>Ninguém encontrado com esses filtros.</div>';
      if (l.length > vis.length) grade.insertAdjacentHTML("beforeend", '<div class="mais-lista" style="grid-column:1/-1"><button type="button" class="btn claro peq ver-mais">Mostrar mais ' + Math.min(LOTE, l.length - vis.length) + " ▾</button></div>");
      contagem.textContent = l.length === total ? "Mostrando todos os " + EP.num(total) + " " + (o.coletivo || nomes.varios) + ", em ordem alfabética." :
        "Mostrando " + EP.num(l.length) + " de " + EP.num(total) + ".";
      // acende as cadeiras do partido escolhido
      if (plenEl) {
        var g = pa ? idxPartido[pa] : null;
        plenEl.classList.toggle("tem-aceso", g != null);
        [].forEach.call(plenEl.querySelectorAll("i"), function (c) { c.classList.toggle("aceso", g != null && +c.getAttribute("data-g") === g); });
      }
      [].forEach.call(el.querySelectorAll(".barra-partido"), function (b) { b.setAttribute("aria-pressed", String(pa !== "" && +b.getAttribute("data-g") === idxPartido[pa])); });
    }
    var t = null;
    fNome.addEventListener("input", function () { clearTimeout(t); t = setTimeout(function () { mostrando = LOTE; desenha(); }, 150); });
    if (fUF) fUF.addEventListener("change", function () { mostrando = LOTE; desenha(); });
    fPart.addEventListener("change", function () { mostrando = LOTE; desenha(); });
    el.addEventListener("click", function (e) {
      var b = e.target.closest(".barra-partido");
      if (b) {
        var p = porPartido[+b.getAttribute("data-g")].partido;
        fPart.value = fPart.value === p ? "" : p;
        mostrando = LOTE;
        desenha();
        return;
      }
      if (e.target.closest(".mais-p")) {
        [].forEach.call(el.querySelectorAll(".barra-partido[hidden]"), function (x) { x.hidden = false; });
        e.target.closest(".mais-p").remove();
        return;
      }
      if (e.target.closest(".ver-mais")) { mostrando += LOTE; desenha(); }
    });
    desenha();

    // anima o plenário e as barras quando aparecem na tela
    function anima() {
      if (plenEl) plenEl.classList.add("cheio");
      [].forEach.call(el.querySelectorAll(".trilho-p i"), function (i) { i.style.width = i.getAttribute("data-w"); });
    }
    if ("IntersectionObserver" in window && !EP.reduzido) {
      var io = new IntersectionObserver(function (ents) {
        if (ents.some(function (x) { return x.isIntersecting; })) { setTimeout(anima, 250); io.disconnect(); }
      }, { threshold: 0.2 });
      io.observe(el.querySelector(".casa-resumo"));
    } else anima();
    EP.revelar(el);
  };
})();
