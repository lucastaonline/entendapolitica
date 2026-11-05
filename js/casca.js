/* ====== Busca rápida (site-d-r13: a do protótipo D, em todas as páginas) ======
   Ctrl+K (⌘K no Mac), "/" ou o botão 🔍 da barra do topo, de qualquer página: abre uma janela (<dialog> modal) com um campo
   (padrão ARIA 1.2 "combobox" + "listbox"). Procura pessoas (dados/busca.json), estados, cidades (dados/cidades.json) e as
   partes do site. Os dois arquivos só são baixados quando a busca abre: a página não fica mais pesada ao abrir.
   Teclado: ↑ ↓ escolhem, Home/End, Enter abre, Esc limpa o campo (com o campo vazio, fecha); o foco volta para quem abriu.
   A pesquisa volta: ao abrir um resultado e voltar (Voltar do navegador), a busca abre de novo com o mesmo texto e o resultado
   aberto marcado (history.state, como o EP.memo). Na página inicial (que não tem campo próprio), ?q=lula abre a busca já feita.
   Linhas de dados/busca.json: [id, nome, cargo curto, UF, partido, cidade|null, cargo em inglês (opcional)];
   de dados/cidades.json: [código IBGE, nome, UF]. */
(function () {
  "use strict";
  var EP = window.EP;
  if (!EP || !document.querySelector("body > header.topo")) return;
  var R = EP.RAIZ || "", esc = EP.esc;
  var LIM = 7;
  var MAC = /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent || "");
  EP.ATALHO_BUSCA = MAC ? "⌘K" : "Ctrl K";
  var LUPA = '<svg class="lucide lupa" aria-hidden="true" focusable="false" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7.5"/><path d="m20.5 20.5-4.3-4.3"/></svg>';
  EP.LUPA = LUPA;

  // ---------------------------------------------------------------- as partes do site (também aparecem com o campo vazio)
  // [endereço, emoji, pt, en, palavras para achar]
  var PAGINAS = [
    ["./", "🏠", "Início", "Home", "comeco pagina inicial portas home start"],
    ["entenda.html", "🗺️", "Entenda a política: o mapa 3D", "Understand politics: the 3D map", "aprender aulas tres poderes mapa learn map branches"],
    ["brasil.html", "🏛️", "A política do Brasil", "Brazil's politics", "pais presidente governo congresso country president"],
    ["estado.html", "📍", "A política do meu estado", "Politics in my state", "governador deputados estaduais assembleia governor state"],
    ["cidade.html", "🏘️", "A política da minha cidade", "Politics in my city", "prefeito vereadores camara municipal mayor councilors city"],
    ["brasil.html#executivo", "🏢", "Quem governa: presidente, vice e ministros", "Who governs: President, Vice President and ministers", "executivo ministerios ministros executive ministers"],
    ["brasil.html#senado", "🏛️", "Senado Federal: os 81 senadores", "Federal Senate: the 81 senators", "senadores senators senate"],
    ["brasil.html#camara", "🏛️", "Câmara dos Deputados: os 513 deputados", "Chamber of Deputies: the 513 deputies", "deputados federais deputies chamber"],
    ["brasil.html#judiciario", "⚖️", "Supremo Tribunal Federal (STF)", "Federal Supreme Court (STF)", "judiciario ministros stf supremo justices court"],
    ["votacoes.html", "🗳️", "Votações do Congresso", "Votes in Congress", "votacoes votos placar votes"],
    ["brasil.html?mandato=2027", "📅", "Quem assume em 2027", "Who takes office in 2027", "eleitos 2026 eleicao posse elected election"],
    ["entenda.html#parte-10", "🗳️", "Como funciona a urna eletrônica", "How the electronic voting machine works", "urna eletronica eleicao voto voting machine"],
    ["imparcialidade.html", "⚖️", "Como cuidamos da imparcialidade", "How we stay impartial", "regras neutro imparcial rules impartial"],
    ["dados.html", "🗂️", "De onde vêm os dados", "Where the data comes from", "fontes oficiais dados sources data"]
  ].map(function (p) { return { tipo: "pagina", href: R + p[0].replace(/^\.\/$/, R ? "" : "./"), ic: p[1], t: EP.tr(p[2], p[3]), n: EP.norm(p[2] + " " + p[3] + " " + p[4]) }; });

  // ---------------------------------------------------------------- dados (só quando a busca abre)
  var pPessoas = null, pCidades = null;
  function pessoas() {
    if (!pPessoas) {
      pPessoas = EP.json(R + "dados/busca.json").then(function (linhas) {
        return linhas.map(function (l) {
          var uf = l[3] || "", extra = [l[2], uf, EP.UFS[uf], l[4], l[5]];
          if (EP.en) extra.push(l[6] || EP.cargo(l[2]));
          return { tipo: "pessoa", id: l[0], nome: l[1], cargo: l[2], cargoEn: l[6] || null, uf: uf, partido: l[4], cidade: l[5], n: EP.norm(l[1]), resto: EP.norm(extra.join(" ")) };
        });
      });
      pPessoas.catch(function () { pPessoas = null; });
    }
    return pPessoas;
  }
  var ESTADOS = Object.keys(EP.UFS).map(function (uf) { return { tipo: "estado", uf: uf, nome: EP.UFS[uf], n: EP.norm(EP.UFS[uf]), resto: EP.norm(uf) }; });
  function cidades() {
    if (!pCidades) {
      pCidades = EP.json(R + "dados/cidades.json").then(function (l) {
        return l.map(function (c) { return { tipo: "cidade", ibge: c[0], nome: c[1], uf: c[2], n: EP.norm(c[1]), resto: EP.norm(c[2] + " " + (EP.UFS[c[2]] || "")) }; });
      });
      pCidades.catch(function () { pCidades = null; });
    }
    return pCidades;
  }
  // a mesma régua do js/busca.js: começo do nome vale mais; o resto (cargo, estado, partido, cidade) também acha
  function procura(lista, q) {
    var termos = EP.norm(q).split(/\s+/).filter(Boolean);
    if (!termos.length) return [];
    var res = [];
    lista.forEach(function (p) {
      var pontos = 0;
      for (var i = 0; i < termos.length; i++) {
        var t = termos[i], noNome = p.n.indexOf(t);
        if (noNome === 0 || p.n.indexOf(" " + t) > -1) pontos += 3;
        else if (noNome > -1) pontos += 2;
        else if ((" " + (p.resto || "") + " ").indexOf(" " + t) > -1) pontos += 1;
        else return;
      }
      res.push({ p: p, pontos: pontos });
    });
    res.sort(function (a, b) { return b.pontos - a.pontos || a.p.n.localeCompare(b.p.n); });
    return res.map(function (r) { return r.p; });
  }
  function busca(q) {
    var nq = EP.norm(q).trim();
    var pg = PAGINAS.filter(function (x) { return !nq || nq.split(/\s+/).every(function (t) { return x.n.indexOf(t) > -1; }); });
    if (nq.length < 2) return Promise.resolve({ q: q, paginas: nq ? pg.slice(0, 6) : pg.slice(0, 9), pessoas: [], lugares: [], total: 0 });
    return Promise.all([pessoas(), cidades().catch(function () { return []; })]).then(function (r) {
      var ps = procura(r[0], q), lu = procura(ESTADOS, q).concat(procura(r[1], q));
      return { q: q, paginas: pg.slice(0, 4), pessoas: ps.slice(0, LIM), totalPessoas: ps.length, lugares: lu.slice(0, 4), totalLugares: lu.length, total: ps.length + lu.length + pg.length };
    });
  }
  function link(x) {
    if (x.tipo === "estado") return R + "estado.html?uf=" + x.uf;
    if (x.tipo === "cidade") return R + "cidade.html?ibge=" + x.ibge;
    if (x.tipo === "pagina") return x.href;
    return R + "pessoa.html?id=" + encodeURIComponent(x.id);
  }
  function desc(x) {
    if (x.tipo === "estado") return EP.tr("Estado", "State");
    if (x.tipo === "cidade") return EP.tr("Cidade", "City") + " · " + (EP.UFS[x.uf] || x.uf);
    var onde = x.cidade ? x.cidade + " (" + x.uf + ")" : EP.UFS[x.uf] || x.uf || EP.tr("Brasil", "Brazil");
    var partido = !x.partido ? "" : /^sem partido$/i.test(x.partido) ? EP.tr("Sem partido", "No party") : x.partido;
    return [EP.en && x.cargoEn ? x.cargoEn : EP.cargo(x.cargo), partido, onde].filter(Boolean).join(" · ");
  }

  // ---------------------------------------------------------------- a janela
  var dlg = document.createElement("dialog");
  dlg.className = "busca-rapida";
  dlg.id = "busca-rapida";
  dlg.setAttribute("aria-labelledby", "br-tit");
  dlg.innerHTML = '<div class="br-caixa"><h2 class="sr" id="br-tit">' + EP.tr("Busca rápida", "Quick search") + "</h2>" +
    '<div class="br-cab">' + LUPA + '<label class="sr" for="br-q">' + EP.tr("Procure um político, um estado, uma cidade ou uma parte do site", "Search for a politician, a state, a city or a part of the site") + "</label>" +
    '<input type="text" id="br-q" role="combobox" aria-autocomplete="list" aria-controls="br-lista" aria-expanded="false" autocomplete="off" spellcheck="false" placeholder="' +
    esc(EP.tr("Procure um político, um estado, uma cidade…", "Search for a politician, a state, a city…")) + '" aria-describedby="br-ajuda">' +
    '<button type="button" class="btn br-fecha" data-variant="outline" data-fecha-busca><span class="br-esc" aria-hidden="true">Esc</span><span class="br-fecha-txt">' + EP.tr("Fechar", "Close") + "</span></button></div>" +
    '<p class="sr" id="br-ajuda">' + EP.tr("Use as setas para escolher e Enter para abrir.", "Use the arrow keys to choose and Enter to open.") + "</p>" +
    '<div class="br-lista" id="br-lista" role="listbox" aria-label="' + EP.tr("Resultados da busca", "Search results") + '"></div><p class="br-nota" hidden></p>' +
    '<p class="br-rodape" aria-hidden="true"><span><kbd class="kbd">↑</kbd><kbd class="kbd">↓</kbd> ' + EP.tr("escolher", "choose") + '</span><span><kbd class="kbd">Enter</kbd> ' +
    EP.tr("abrir", "open") + '</span><span><kbd class="kbd">Esc</kbd> ' + EP.tr("fechar", "close") + "</span></p>" +
    '<p class="sr" role="status" id="br-status"></p></div>';
  document.body.appendChild(dlg);
  var inp = dlg.querySelector("#br-q"), lista = dlg.querySelector("#br-lista"), nota = dlg.querySelector(".br-nota"), status = dlg.querySelector("#br-status");
  var ativo = -1, ultimo = null, tempo = null, volta = null, marcarHref = null;

  function ops() { return [].slice.call(lista.querySelectorAll('[role="option"]')); }
  function marca(i) {
    var l = ops();
    l.forEach(function (a) { a.classList.remove("active"); a.setAttribute("aria-selected", "false"); });
    ativo = l.length ? Math.max(-1, Math.min(i, l.length - 1)) : -1;
    if (ativo < 0) { inp.removeAttribute("aria-activedescendant"); return; }
    var a = l[ativo];
    a.classList.add("active");
    a.setAttribute("aria-selected", "true");
    inp.setAttribute("aria-activedescendant", a.id);
    a.scrollIntoView({ block: "nearest" });
  }
  function avisa(t) { if (status.textContent !== t) status.textContent = t; }
  var n = 0;
  function opcao(x, ic, tit, sub, lang) {
    return '<a role="option" id="br-o-' + (n++) + '" href="' + esc(link(x)) + '" tabindex="-1" aria-selected="false" class="br-op" data-tipo="' + x.tipo + '">' +
      '<span class="br-ic" aria-hidden="true">' + ic + '</span><span class="br-txt"><b' + (lang ? ' lang="pt-BR"' : "") + ">" + tit + "</b>" + (sub ? "<small>" + esc(sub) + "</small>" : "") + "</span></a>";
  }
  function grupo(id, tit, html) {
    return '<div role="group" aria-labelledby="' + id + '" class="br-grupo"><div class="br-grupo-tit" id="' + id + '">' + esc(tit) + "</div>" + html + "</div>";
  }
  function desenha(r) {
    var h = "";
    if (r.pessoas.length) {
      h += grupo("brg-p", EP.tr("Pessoas", "People") + (r.totalPessoas > r.pessoas.length ? " · " + EP.num(r.totalPessoas) + EP.tr(" encontradas", " found") : ""), r.pessoas.map(function (x) {
        return opcao(x, EP.av(null, x.nome, "br-av"), esc(x.nome), desc(x), EP.en);
      }).join(""));
    }
    if (r.lugares.length) {
      h += grupo("brg-l", EP.tr("Estados e cidades", "States and cities"), r.lugares.map(function (x) {
        return opcao(x, x.tipo === "estado" ? "📍" : "🏘️", esc(x.nome) + (x.tipo === "cidade" ? " (" + esc(x.uf) + ")" : ""), desc(x), EP.en && x.tipo === "cidade");
      }).join(""));
    }
    if (r.paginas.length) {
      h += grupo("brg-g", r.q && r.q.trim() ? EP.tr("Partes do site", "Parts of the site") : EP.tr("Ir para", "Go to"), r.paginas.map(function (x) { return opcao(x, x.ic, esc(x.t), ""); }).join(""));
    }
    lista.innerHTML = h;
    lista.hidden = !h;
    var q = (r.q || "").trim();
    nota.textContent = !h ? EP.tr("Nada encontrado com “" + q + "”. Confira se está escrito certo, ou tente o nome da cidade, do estado ou do partido.",
      "Nothing found for “" + q + "”. Check the spelling, or try the name of the city, the state or the party.") :
      r.totalPessoas > r.pessoas.length ? EP.tr("E mais " + EP.num(r.totalPessoas - r.pessoas.length) + " pessoas. Digite mais letras para achar mais rápido.",
        "And " + EP.num(r.totalPessoas - r.pessoas.length) + " more people. Type more letters to narrow it down.") : "";
    nota.hidden = !nota.textContent;
    inp.setAttribute("aria-expanded", h ? "true" : "false");
    ativo = -1;
    inp.removeAttribute("aria-activedescendant");
    if (marcarHref) {
      var i = ops().map(function (a) { return a.getAttribute("href"); }).indexOf(marcarHref);
      marcarHref = null;
      if (i > -1) marca(i);
    }
    if (q.length >= 2) {
      var tot = (r.totalPessoas || 0) + (r.totalLugares || 0);
      avisa(tot ? EP.num(tot) + EP.tr(tot === 1 ? " resultado." : " resultados.", tot === 1 ? " result." : " results.") : EP.tr("Nada encontrado.", "Nothing found."));
    } else avisa("");
  }
  function roda() {
    var q = inp.value;
    ultimo = q;
    busca(q).then(function (r) { if (inp.value === ultimo) desenha(r); }).catch(function () {
      lista.innerHTML = "";
      lista.hidden = true;
      inp.setAttribute("aria-expanded", "false");
      nota.hidden = false;
      nota.textContent = EP.tr("Não foi possível carregar a lista de nomes agora. Tente de novo daqui a pouco.", "The list of names could not be loaded right now. Please try again in a little while.");
    });
  }
  function vai(a) {
    if (!a) return;
    // guarda a pesquisa neste passo do histórico: voltando, a busca abre de novo como estava
    if (EP.memo) EP.memo.grava("busca", { q: inp.value, href: a.getAttribute("href") });
    location.href = a.href;
  }
  inp.addEventListener("input", function () { clearTimeout(tempo); tempo = setTimeout(roda, 120); });
  inp.addEventListener("keydown", function (e) {
    var l = ops();
    if (e.key === "ArrowDown") { e.preventDefault(); marca(ativo + 1 >= l.length ? 0 : ativo + 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); marca(ativo <= 0 ? l.length - 1 : ativo - 1); }
    else if (e.key === "Home" && ativo > -1) { e.preventDefault(); marca(0); }
    else if (e.key === "End" && ativo > -1) { e.preventDefault(); marca(l.length - 1); }
    else if (e.key === "Enter") {
      var a = ativo > -1 ? l[ativo] : inp.value.trim() ? l[0] : null;
      if (a) { e.preventDefault(); vai(a); }
    } else if (e.key === "Escape") {
      e.preventDefault();
      if (inp.value) { inp.value = ""; roda(); } else dlg.close();
    }
  });
  lista.addEventListener("mousemove", function (e) {
    var a = e.target.closest('[role="option"]');
    if (a) { var i = ops().indexOf(a); if (i !== ativo) marca(i); }
  });
  lista.addEventListener("click", function (e) {
    var a = e.target.closest('[role="option"]');
    if (!a || e.button || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    vai(a);
  });
  // o Esc do próprio <dialog> (cancel): o campo trata primeiro (limpa); com o campo vazio, fecha
  dlg.addEventListener("cancel", function (e) { if (inp.value && document.activeElement === inp) e.preventDefault(); });
  dlg.addEventListener("click", function (e) { if (e.target === dlg || (e.target.closest && e.target.closest("[data-fecha-busca]"))) dlg.close(); });
  dlg.addEventListener("close", function () {
    if (EP.memo) EP.memo.grava("busca", null);
    if (volta && volta.focus && document.contains(volta)) volta.focus();
    volta = null;
  });

  function abre(o, q) {
    if (dlg.open) { inp.focus(); return; }
    if (EP.fechaMenu) EP.fechaMenu(false);
    if (EP.fechaMenus) EP.fechaMenus(false);
    volta = o && o.focus ? o : document.activeElement;
    if (q != null) inp.value = q;
    try { dlg.showModal(); } catch (e) { dlg.setAttribute("open", ""); }
    inp.focus();
    if (q == null) inp.select();
    pessoas().catch(function () {});
    roda();
  }
  EP.abreBusca = abre;
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-abre-busca]");
    if (!b) return;
    e.preventDefault();
    abre(b);
  });
  document.addEventListener("keydown", function (e) {
    var k = (e.key || "").toLowerCase();
    if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && k === "k") {
      e.preventDefault();
      if (dlg.open) dlg.close(); else if (!document.querySelector("dialog[open]:not(#busca-rapida)")) abre();
      return;
    }
    if (k !== "/" || e.ctrlKey || e.metaKey || e.altKey || dlg.open || document.querySelector("dialog[open]")) return;
    var t = e.target;
    if (t && (/^(input|textarea|select)$/i.test(t.tagName || "") || t.isContentEditable)) return;
    e.preventDefault();
    abre();
  });
  // o atalho aparece no botão da barra (Ctrl K ou ⌘K)
  [].forEach.call(document.querySelectorAll("[data-abre-busca] .atalho"), function (k) { k.textContent = EP.ATALHO_BUSCA; });

  // voltando de um resultado (ou recarregando), a busca abre de novo como estava; na página inicial, ?q= abre a busca feita
  function reabre() {
    var m = EP.memo && EP.memo.le("busca");
    if (m && m.q != null && EP.memo.voltando()) { marcarHref = m.href || null; abre(null, m.q); return; }
    var q = EP.memo ? EP.memo.url("q") : null;
    if (q && !document.getElementById("busca")) abre(null, q);
  }
  window.addEventListener("pageshow", function (e) {
    if (e.persisted) { if (dlg.open && EP.memo && EP.memo.le("busca")) inp.focus(); return; }
    setTimeout(reabre, 0);
  });
})();
