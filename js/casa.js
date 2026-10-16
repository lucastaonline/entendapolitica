/* Bloco de uma casa legislativa: plenário 3D, quantos de cada partido, filtros e a grade de pessoas.
   Usado para Senado, Câmara, Assembleias (deputados estaduais) e Câmaras Municipais (vereadores).
   o.nomes = { um, uma, varios, varias } já no idioma da página (use EP.tr); o.nivel = nível do título "Quantos de cada partido" (3). */
(function () {
  "use strict";
  var EP = window.EP, T = window.TRES || {};
  var esc = EP.esc;
  var SEM = "Sem partido";
  var conta = 0;

  function nomePartido(p) { return p === SEM ? EP.tr("Sem partido", "No party") : p; }
  function nomePartidoHtml(p) { return p === SEM ? esc(nomePartido(p)) : EP.pt(esc(p)); }

  // cartão grande de quem governa (governador, prefeito e vices). Usado nas páginas do estado e da cidade.
  EP.cartaoGrande = function (p, cargo, extra) {
    var D = EP.trd;
    if (!p) return "";
    if (p.vago) {
      return '<div class="pessoa-grande"><span class="av av-letra" aria-hidden="true">–</span><span><span class="cargo">' + esc(cargo) + "</span><b>" + EP.tr("Cargo vago", "Vacant") + "</b>" +
        (p.txt || p.nota ? "<small>" + D.traduz(p.txt || p.nota, null, p.txt_en || p.nota_en) + "</small>" : "") + "</span></div>";
    }
    var desde = p.desde ? EP.tr("No cargo desde ", "In office since ") + EP.data(p.desde) : "";
    return '<a class="pessoa-grande rev" href="pessoa.html?id=' + encodeURIComponent(p.id) + '">' + EP.av(p.foto, p.nome, null, true) +
      '<span><span class="cargo">' + esc(cargo) + "</span><b>" + esc(p.nome) + "</b><small>" + [p.partido ? EP.pt(esc(p.partido)) : "", esc(desde)].filter(Boolean).join(" · ") + "</small>" +
      (extra || "") + EP.chip2026(p.eleicao2026, p.genero, true) +
      (p.comoAssumiu && !/^eleit/i.test(p.comoAssumiu) ? '<small style="margin-top:6px"><span aria-hidden="true">🔑 </span>' + D.traduz(p.comoAssumiu, null, p.comoAssumiu_en) + "</small>" : "") +
      (p.nota ? '<small style="margin-top:6px"><span aria-hidden="true">📝 </span>' + D.traduz(p.nota, null, p.nota_en) + "</small>" : "") +
      '<span class="ver">' + EP.tr("Ver mais", "See more") + ' <span aria-hidden="true">›</span></span></span></a>';
  };

  EP.montaCasa = function (el, o) {
    var uid = "casa" + (++conta);
    var membros = EP.alfabetica(o.membros || []);
    var nomes = o.nomes || { um: EP.tr("pessoa", "person"), uma: EP.tr("pessoa", "person"), varios: EP.tr("pessoas", "people"), varias: EP.tr("pessoas", "people") };
    var nivel = Math.min(6, Math.max(2, o.nivel || 3));
    var total = membros.length;

    if (!total) {
      el.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">🛠️</span>' +
        EP.tr("Esta lista ainda não está disponível. Estamos juntando os dados, sempre com fonte.", "This list is not available yet. We are gathering the data, always with sources.") + "</div>" +
        (o.fonte ? "<p>" + EP.botaoFontes(o.fonte, EP.tr("De onde vem esta lista?", "Where does this list come from?")) + "</p>" : "");
      return;
    }

    var porPartido = o.porPartido;
    if (!porPartido) {
      var cont = {};
      membros.forEach(function (m) { var p = m.partido || SEM; cont[p] = (cont[p] || 0) + 1; });
      porPartido = Object.keys(cont).map(function (p) { return { partido: p, n: cont[p] }; });
    }
    // do partido com mais cadeiras para o com menos (é só uma contagem); empate: ordem alfabética
    porPartido = porPartido.slice().sort(function (a, b) { return b.n - a.n || EP.norm(a.partido).localeCompare(EP.norm(b.partido)); });
    var idxPartido = {};
    porPartido.forEach(function (p, k) { idxPartido[p.partido] = k; });
    var maxN = porPartido.length ? porPartido[0].n : 1;
    var VIS = 999; // todos os partidos aparecem (esconder os menores daria destaque só aos maiores)

    var plen = T.plenario ? T.plenario({ total: total, grupos: porPartido.map(function (p) { return p.n; }), max: total > 300 ? 520 : total > 60 ? 440 : 380 }) : "";
    var mulheres = membros.filter(function (m) { return m.genero === "F"; }).length;
    var homens = membros.filter(function (m) { return m.genero === "M"; }).length;
    var ufs = {};
    membros.forEach(function (m) { if (m.uf) ufs[m.uf] = 1; });
    var listaUF = Object.keys(ufs).sort(function (a, b) { return EP.norm(EP.UFS[a] || a).localeCompare(EP.norm(EP.UFS[b] || b)); });
    var h = "h" + nivel;
    var cadeira = EP.en ? "Each seat is one " + nomes.um + "." : "Cada cadeira é " + (/^(pessoa|deputada|senadora|vereadora)/.test(nomes.um) ? "uma " : "um ") + nomes.um + ".";

    function textoContagem(n) {
      return n === total ? EP.tr("Mostrando todos os " + EP.num(total) + " " + (o.coletivo || nomes.varios) + ", em ordem alfabética.",
        "Showing all " + EP.num(total) + " " + (o.coletivo || nomes.varios) + ", in alphabetical order.") :
        EP.tr("Mostrando " + EP.num(n) + " de " + EP.num(total) + ", em ordem alfabética.", "Showing " + EP.num(n) + " of " + EP.num(total) + ", in alphabetical order.");
    }

    el.innerHTML =
      '<div class="casa-resumo"><div class="plen-box rev">' + plen + "<p>" + esc(cadeira) + (o.notaPlenario ? " " + esc(o.notaPlenario) : "") + "</p></div>" +
      '<div class="partidos rev" style="--i:1"><' + h + ' class="tit-p" id="' + uid + '-tit">' + EP.tr("Quantos de cada partido", "Seats per party") + "</" + h + ">" +
      '<div class="barras-p" role="group" aria-labelledby="' + uid + '-tit">' +
      porPartido.map(function (p, k) {
        return '<button type="button" class="barra-partido" data-g="' + k + '"' + (k >= VIS ? " hidden" : "") + ' aria-pressed="false">' +
          '<span class="nome-p">' + nomePartidoHtml(p.partido) + '</span> <span class="trilho-p" aria-hidden="true"><i data-w="' + (100 * p.n / maxN).toFixed(1) + '%"></i></span> ' +
          '<span class="n-p">' + EP.num(p.n) + '</span><span class="sr"> ' + esc(p.n === 1 ? nomes.um : nomes.varios) + "</span></button>";
      }).join("") + "</div>" +
      (porPartido.length > VIS ? '<button type="button" class="mais-p">' + EP.tr("Ver todos os " + porPartido.length + " partidos", "See all " + porPartido.length + " parties") + ' <span aria-hidden="true">▾</span></button>' : "") +
      '<p class="explica-p">' + EP.tr("Partido é um grupo de pessoas que se juntam para disputar eleições e defender ideias parecidas. Toque num partido para ver só quem é dele. A ordem vai do partido com mais cadeiras para o com menos: é só uma contagem, não um ranking. Todos os partidos têm a mesma cor aqui, de propósito.",
        "A party is a group of people who join together to run in elections and defend similar ideas. Tap a party to see only its members. The order goes from the party with the most seats to the one with the fewest: it is just a count, not a ranking. All parties have the same color here, on purpose.") + "</p></div></div>" +
      (mulheres + homens ? '<p class="sabia rev"><span aria-hidden="true">💡</span><span>' +
        (EP.en ? "Did you know? Right now there are <b>" + EP.num(mulheres) + (mulheres === 1 ? " woman" : " women") + "</b> and <b>" + EP.num(homens) + (homens === 1 ? " man" : " men") + "</b> in this list."
          : "Você sabia? Hoje são <b>" + EP.plural(mulheres, nomes.uma, nomes.varias) + "</b> e <b>" + EP.plural(homens, nomes.um, nomes.varios) + "</b>.") + "</span></p>" : "") +
      '<div class="filtros-casa"><div class="busca"><input type="search" class="f-nome" placeholder="' + EP.tr("Procurar pelo nome", "Search by name") + '" aria-label="' +
      EP.tr("Procurar pelo nome", "Search by name") + '" autocomplete="off"></div>' +
      (o.filtroUF !== false && listaUF.length > 1 ? '<select class="f-uf" aria-label="' + EP.tr("Filtrar por estado", "Filter by state") + '"><option value="">' + EP.tr("Todos os estados", "All states") + "</option>" +
        listaUF.map(function (u) { return '<option value="' + u + '" data-busca="' + u + '">' + esc(EP.UFS[u] || u) + "</option>"; }).join("") + "</select>" : "<span></span>") +
      '<select class="f-partido" aria-label="' + EP.tr("Filtrar por partido", "Filter by party") + '"><option value="">' + EP.tr("Todos os partidos", "All parties") + "</option>" +
      EP.alfabetica(porPartido, "partido").map(function (p) {
        return '<option value="' + esc(p.partido) + '"' + (EP.en && p.partido !== SEM ? ' lang="pt-BR"' : "") + ">" + esc(nomePartido(p.partido)) + " (" + EP.num(p.n) + ")</option>";
      }).join("") + "</select></div>" +
      '<p class="contagem" aria-live="polite">' + esc(textoContagem(total)) + '</p><div class="grade-pessoas"></div>' +
      (o.fonte ? '<p class="fonte-casa">' + EP.botaoFontes(o.fonte, EP.tr("De onde vem esta lista?", "Where does this list come from?")) +
        (o.atualizado ? ' <small class="muted">' + EP.tr("Atualizado em ", "Updated on ") + EP.data(o.atualizado) + "</small>" : "") + "</p>" : "");

    var fNome = el.querySelector(".f-nome"), fUF = el.querySelector(".f-uf"), fPart = el.querySelector(".f-partido");
    // listas de escolha com busca: a pessoa digita e as opções vão aparecendo
    if (fUF) EP.comboSelect(fUF, { placeholder: EP.tr("Digite o estado…", "Type a state…") });
    EP.comboSelect(fPart, { placeholder: EP.tr("Digite o partido…", "Type a party…") });
    var grade = el.querySelector(".grade-pessoas"), contagem = el.querySelector(".contagem"), plenEl = el.querySelector(".plenario");
    var LOTE = 60, mostrando = LOTE;

    function filtrados() {
      var q = EP.norm(fNome.value), uf = fUF ? fUF.value : "", pa = fPart.value;
      return membros.filter(function (m) {
        return (!q || EP.norm(m.nome).indexOf(q) > -1 || EP.norm(m.nomeCivil || "").indexOf(q) > -1) && (!uf || m.uf === uf) && (!pa || (m.partido || SEM) === pa);
      });
    }
    function desenha(focarDe) {
      var l = filtrados();
      var vis = l.slice(0, mostrando);
      grade.innerHTML = vis.length ? vis.map(function (m) { return EP.cartaoPessoa(m, o.extra ? o.extra(m) : ""); }).join("") :
        '<div class="vazio"><span class="grande" aria-hidden="true">🤷</span>' + EP.tr("Ninguém encontrado com esses filtros.", "No one found with these filters.") + "</div>";
      if (l.length > vis.length) {
        var n = Math.min(LOTE, l.length - vis.length);
        grade.insertAdjacentHTML("beforeend", '<div class="mais-lista" style="grid-column:1/-1"><button type="button" class="btn claro peq ver-mais">' +
          EP.tr("Mostrar mais " + n, "Show " + n + " more") + ' <span aria-hidden="true">▾</span></button></div>');
      }
      var txt = textoContagem(l.length);
      if (contagem.textContent !== txt) contagem.textContent = txt;
      // acende as cadeiras do partido escolhido
      var pa = fPart.value;
      if (plenEl) {
        var g = pa ? idxPartido[pa] : null;
        plenEl.classList.toggle("tem-aceso", g != null);
        [].forEach.call(plenEl.querySelectorAll("i"), function (c) { c.classList.toggle("aceso", g != null && +c.getAttribute("data-g") === g); });
      }
      [].forEach.call(el.querySelectorAll(".barra-partido"), function (b) {
        var on = pa !== "" && +b.getAttribute("data-g") === idxPartido[pa];
        b.setAttribute("aria-pressed", String(on));
        if (on) b.hidden = false;
      });
      // depois de "Mostrar mais", o foco vai para a primeira pessoa nova
      if (focarDe != null) {
        var cards = grade.querySelectorAll(".pessoa-card");
        if (cards[focarDe]) cards[focarDe].focus();
      }
    }
    var t = null;
    fNome.addEventListener("input", function () { clearTimeout(t); t = setTimeout(function () { mostrando = LOTE; desenha(); }, 200); });
    if (fUF) fUF.addEventListener("change", function () { mostrando = LOTE; desenha(); });
    fPart.addEventListener("change", function () { mostrando = LOTE; desenha(); });
    el.addEventListener("click", function (e) {
      var b = e.target.closest(".barra-partido");
      if (b) {
        var p = porPartido[+b.getAttribute("data-g")].partido;
        fPart.value = fPart.value === p ? "" : p;
        EP.comboSync(fPart);
        mostrando = LOTE;
        desenha();
        return;
      }
      var mp = e.target.closest(".mais-p");
      if (mp) {
        var novos = el.querySelectorAll(".barra-partido[hidden]");
        [].forEach.call(novos, function (x) { x.hidden = false; });
        mp.remove();
        if (novos[0]) novos[0].focus();
        return;
      }
      if (e.target.closest(".ver-mais")) {
        var de = mostrando;
        mostrando += LOTE;
        desenha(de);
      }
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
