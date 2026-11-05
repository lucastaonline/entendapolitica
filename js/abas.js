/* ====== Abas das páginas grandes (componente "tabs" do Basecoat, vendor/basecoat) ======
   Cada seção grande da página (<section class="miolo bloco" id="..."> ou <section class="secao-perfil" id="...">) vira uma aba,
   com endereço próprio (pagina.html#id). Marcação do Basecoat: div.tabs > [role=tablist] > button[role=tab] e
   [role=tabpanel] (site-d-r14: o tablist fica dentro de div.abas-barra, a barra presa, com os botões ‹ e › nas pontas); o js do Basecoat (tabs) cuida do clique e das setas/Home/End; aqui ficam o endereço, o Voltar, a barra
   presa no topo, montar o conteúdo só quando a aba abre e o resto. Sem JavaScript, a página fica como era (seções em
   sequência e o menu "Ir direto para"). Usado pelo Brasil, estado, cidade e perfil (ui-r8 e ui-r9; até a ui-r9 era a Web
   Awesome).

   EP.abas.monta(o)              transforma as seções em abas; devolve true se montou. o.nav = o menu "Ir direto para"
                                 (nav.atalhos): cada link "#id" para uma seção vira uma aba, com o mesmo emoji, texto e data-en.
                                 O menu sai da página (a barra das abas faz o papel dele).
   EP.abas.quandoAbrir(id, fn)   roda fn na primeira vez que a aba da seção id fica visível (na hora, se ela já está visível ou
                                 se a página não tem abas): cada aba monta o seu conteúdo só quando precisa.
   EP.abas.mostra(id)            abre a aba da seção id, ou da seção que tem o elemento id dentro.
   EP.abas.ativa()               a aba visível (id da seção), ou null sem abas.
   EP.mostraSecao(id)            o mesmo que mostra(), para o js/comum.js (voltar de um perfil para a lista).
   EP.topoFixo()                 (só quando a página tem abas) altura do que fica preso no topo (cabeçalho + barra das abas).
   Evento "ep-aba" (em window, detail.id) toda vez que uma aba aparece: quem mede posições (o plenário do js/casa.js) refaz.

   Endereço: pagina.html#senado abre a aba Senado; um id de dentro de uma seção (ex.: #os-ministros) abre a aba dela e rola
   até ele. Clicar numa aba muda o endereço (pushState) e o Voltar do navegador volta para a aba anterior; as setas do teclado
   trocam de aba sem encher o histórico (replaceState). Uma seção que some (hidden) leva a aba junto. */
(function () {
  "use strict";
  var EP = window.EP;
  if (!EP) return;
  var A = (EP.abas = {});
  var raiz = document.documentElement;
  var caixa = null, grupo = null;
  var ordem = [], abas = {}, paineis = {}, secoes = {}, fila = {}, montadas = {};
  var atual = null, teclado = false, estava = false, lista = null, faixaAbas = null, setaE = null, setaD = null;

  function nomeDe(id) {
    if (!grupo || !id) return null;
    if (paineis[id]) return id;
    var el = document.getElementById(id);
    var p = el && el.closest ? el.closest('[role="tabpanel"][data-aba]') : null;
    return p && grupo.contains(p) ? p.getAttribute("data-aba") : null;
  }
  function visivel(n) { return !!abas[n] && !abas[n].hidden; }
  function primeira() { return ordem.filter(visivel)[0] || null; }
  function doEndereco() {
    var h = "";
    try { h = decodeURIComponent(location.hash.slice(1)); } catch (e) { h = location.hash.slice(1); }
    return { id: h, nome: nomeDe(h) };
  }
  function avisa(n) { try { window.dispatchEvent(new CustomEvent("ep-aba", { detail: { id: n } })); } catch (e) {} }
  function monta(n) {
    if (montadas[n]) return;
    montadas[n] = true;
    (fila[n] || []).splice(0).forEach(function (fn) { try { fn(); } catch (e) { if (window.console) console.error(e); } });
  }

  // ---------------------------------------------------------------- alturas do que fica preso no topo
  function alturaTopo() { var t = document.querySelector("header.topo"); return t ? t.getBoundingClientRect().height : 0; }
  function barra() { return faixaAbas || lista; }
  function alturaBarra() { var b = barra(); return b ? b.getBoundingClientRect().height : 0; }
  function poeAlturas() {
    raiz.style.setProperty("--topo-h", Math.round(alturaTopo()) + "px");
    var b = alturaBarra();
    if (b) raiz.style.setProperty("--abas-h", Math.round(b) + "px");
  }
  // presa ao topo: o js/comum.js usa (EP.topoFixo) para saber o que a barra cobre (só existe quando a página tem abas)
  function topoFixo() { return grupo ? alturaTopo() + alturaBarra() : alturaTopo(); }
  // a barra está presa no topo (a pessoa já rolou até ela)?
  function presa() { return grupo && grupo.getBoundingClientRect().top <= alturaTopo() + 1; }
  // põe o começo das abas logo abaixo do cabeçalho (a barra presa e a aba nova começando embaixo dela). Usado ao trocar de aba
  // lá embaixo de uma lista comprida: sem isso, a pessoa cairia no meio da aba nova
  // (site-d-r14) deslizando (EP.rolaJanela, js/comum.js); com "menos movimento", na hora
  // segura(): antes de trocar de aba lá embaixo, as abas guardam a altura de agora até a rolagem terminar (sem isso, uma aba nova
  // mais curta encurtaria a página e o navegador a puxaria para cima de uma vez, sem deslizar)
  var soltaT = 0;
  function solta() { clearTimeout(soltaT); if (grupo) grupo.style.minHeight = ""; }
  function segura() { if (!grupo) return; clearTimeout(soltaT); grupo.style.minHeight = Math.ceil(grupo.getBoundingClientRect().height) + "px"; soltaT = setTimeout(solta, 900); }
  function vaiAoComeco() {
    var y = Math.max(0, grupo.getBoundingClientRect().top + window.scrollY - alturaTopo());
    if (EP.rolaJanela) EP.rolaJanela(y, solta); else { window.scrollTo({ top: y, behavior: "instant" }); solta(); }
  }
  // rola até um elemento (o scroll-padding do html desconta o cabeçalho e a barra). O conteúdo das abas chega depois (e o
  // "Ver outro mandato", em cima, também): durante 5 s, se algo mudar de tamanho, rola de novo, a não ser que a pessoa role,
  // toque ou use o teclado antes. Se o elemento ainda não existe, espera por ele.
  function rolaPara(id) {
    var parou = false, ro = null, obs = null, prazo = null, quando = 0, alvo = null;
    // a primeira vez desliza (EP.rolaJanela); depois, se a página mudou de altura no caminho, corrige: deslizando, se ainda está
    // indo, ou na hora, se já chegou
    function vai(suave) {
      var el = document.getElementById(id);
      if (!el || !el.getClientRects().length) return false;
      // a posição sem o deslocamento da animação de aparecer (.rev sobe 34px quando aparece)
      var dy = 0;
      try { dy = new DOMMatrixReadOnly(getComputedStyle(el).transform).m42 || 0; } catch (e) {}
      var pad = parseFloat(getComputedStyle(raiz).scrollPaddingTop) || 0;
      var y = Math.max(0, el.getBoundingClientRect().top - dy + window.scrollY - pad);
      if (EP.rolaJanela && (suave || (EP.rolando && EP.rolando()))) {
        if (suave || alvo == null || Math.abs(y - alvo) > 4) EP.rolaJanela(y);
      } else window.scrollTo({ top: y, behavior: "instant" });
      alvo = y;
      return true;
    }
    function fim() {
      parou = true;
      if (obs) obs.disconnect();
      if (ro) ro.disconnect();
      clearTimeout(prazo);
      PARA.forEach(function (t) { window.removeEventListener(t, fim, true); });
    }
    // para quando a pessoa rola, toca ou usa o teclado, quando o foco vai para algum lugar e quando a página está voltando de
    // um perfil (o js/comum.js leva a pessoa ao cartão de quem foi aberto)
    var PARA = ["wheel", "touchstart", "keydown", "mousedown", "focusin", "ep-volta"];
    PARA.forEach(function (t) { window.addEventListener(t, fim, true); });
    function denovo() { if (!parou && Date.now() - quando > 30) { quando = Date.now(); vai(); } }
    vai(true);
    obs = new MutationObserver(denovo);
    obs.observe(document.body, { childList: true, subtree: true });
    if ("ResizeObserver" in window) { ro = new ResizeObserver(denovo); ro.observe(document.body); }
    // ao terminar de carregar, o navegador ainda rola sozinho até o endereço (e às vezes para o lugar de antes): rola de novo
    if (document.readyState !== "complete") window.addEventListener("load", function () { setTimeout(denovo, 50); setTimeout(denovo, 400); }, { once: true });
    prazo = setTimeout(fim, 5000);
  }
  function poeEndereco(n, modo) {
    if (!n || location.hash === "#" + n) return;
    // epPassos: quantas abas a pessoa abriu nesta página (cada clique é um passo do histórico). O "◀ Voltar" do perfil usa
    // isso para voltar de uma vez à lista de onde veio, e não à aba anterior
    var st = Object.assign({}, history.state || {});
    if (modo !== "replace") st.epPassos = (st.epPassos || 0) + 1;
    try { history[modo === "replace" ? "replaceState" : "pushState"](st, "", location.pathname + location.search + "#" + n); } catch (e) {}
    // o menu de idioma do topo leva para a mesma aba no outro idioma
    if (EP.atualizaLinksIdioma) EP.atualizaLinksIdioma();
  }

  // ---------------------------------------------------------------- a barra que rola para o lado
  // (site-d-r14, pedidos do Lucas de 4/11) quando as abas não cabem, a barra rola para o lado e ganha os botões ‹ e › nas
  // pontas, fora da parte que rola (a parte que rola fica só entre os dois). A barra para sempre com uma aba alinhada à
  // borda (scroll-snap, css/abas.css); parada, a aba que não aparece inteira numa ponta fica transparente (.fora): nunca há
  // aba cortada à vista. O botão de um lado fica desativado (apagado) quando não há aba escondida daquele lado.
  function semMovimento() {
    return raiz.classList.contains("sem-movimento") || (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  }
  // as abas em coordenadas da parte que rola (a = começo, b = fim), a largura à vista e o recuo das pontas
  function geo() {
    var rl = lista.getBoundingClientRect(), cs = getComputedStyle(lista), sl = lista.scrollLeft;
    return { sl: sl, cw: lista.clientWidth, max: Math.max(0, lista.scrollWidth - lista.clientWidth),
      pl: parseFloat(cs.paddingLeft) || 0, pr: parseFloat(cs.paddingRight) || 0,
      tabs: ordem.filter(visivel).map(function (n) {
        var r = abas[n].getBoundingClientRect();
        return { t: abas[n], a: r.left - rl.left - lista.clientLeft + sl, b: r.right - rl.left - lista.clientLeft + sl };
      }) };
  }
  function inteira(x, g, sl) { return x.a >= sl - 0.5 && x.b <= sl + g.cw + 0.5; }
  // a posição (um ponto de parada) que mostra a aba x inteira: indo para a esquerda, ela fica na ponta da esquerda; indo para a
  // direita, a primeira aba à vista é a primeira que deixa x inteira
  function posPara(x, g) {
    var p;
    if (x.a < g.sl - 0.5 || x.b - x.a >= g.cw - g.pl - g.pr) p = x.a - g.pl;
    else {
      var k = g.tabs.filter(function (y) { return y.a - g.pl >= x.b + g.pr - g.cw - 0.5; })[0] || x;
      p = k.a - g.pl;
    }
    p = Math.max(0, Math.min(g.max, p));
    if (p < 2) p = 0;
    if (p > g.max - 2) p = g.max;
    return p;
  }
  function rolaAte(p, suave) {
    if (Math.abs(p - lista.scrollLeft) < 1) { marcaFora(); return; }
    try { lista.scrollTo({ left: p, behavior: suave && !semMovimento() ? "smooth" : "instant" }); } catch (e) { lista.scrollLeft = p; }
  }
  // a aba aberta fica à vista, inteira
  function emVista(t, suave) {
    if (!t || !lista || lista.scrollWidth <= lista.clientWidth + 1) return;
    var g = geo(), x = g.tabs.filter(function (y) { return y.t === t; })[0];
    if (x && !inteira(x, g, g.sl)) rolaAte(posPara(x, g), !!suave);
  }
  // ‹ e ›: a primeira aba escondida daquele lado aparece inteira, alinhada (uma "página" de abas)
  function passo(dir) {
    var g = geo(), x;
    // (a aba já alinhada na ponta não conta: se ela for mais larga que a área, o › passa para a seguinte)
    if (dir > 0) x = g.tabs.filter(function (y) { return y.b > g.sl + g.cw + 0.5 && y.a - g.pl > g.sl + 0.5; })[0];
    else x = g.tabs.filter(function (y) { return y.a < g.sl - 0.5; }).pop();
    var p = x ? (dir > 0 ? Math.max(0, Math.min(g.max, x.a - g.pl)) : posPara(x, g)) : (dir > 0 ? g.max : 0);
    if (x && dir < 0 && p >= g.sl - 0.5) p = Math.max(0, x.a - g.pl);
    if (dir > 0 && p > g.max - 2) p = g.max;
    rolaAte(p, true);
  }
  // parada: a aba que não aparece inteira fica transparente; rolando (dedo, roda, botão), todas aparecem
  var foraT = 0;
  function marcaFora() {
    clearTimeout(foraT);
    if (!lista) return;
    var rola = faixaAbas.classList.contains("rola"), g = rola ? geo() : null;
    ordem.forEach(function (n) {
      var x = g && g.tabs.filter(function (y) { return y.t === abas[n]; })[0];
      abas[n].classList.toggle("fora", !!x && !inteira(x, g, g.sl) && x.b - x.a <= g.cw);
    });
  }
  function rolando() {
    ordem.forEach(function (n) { abas[n].classList.remove("fora"); });
    clearTimeout(foraT);
    foraT = setTimeout(marcaFora, 160);
  }
  function seta(dir) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "abas-seta nao-ler " + (dir < 0 ? "abas-seta-esq" : "abas-seta-dir");
    b.setAttribute("aria-label", dir < 0 ? EP.tr("Ver abas anteriores", "Previous tabs") : EP.tr("Ver mais abas", "More tabs"));
    b.setAttribute("aria-controls", lista.id);
    b.disabled = true;
    b.innerHTML = '<svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="' +
      (dir < 0 ? "m15 18-6-6 6-6" : "m9 18 6-6-6-6") + '"/></svg>';
    b.addEventListener("click", function () { passo(dir); });
    return b;
  }
  // ativa ou desativa um botão; se ele tinha o foco e foi desativado, o foco vai para o outro botão (ou para a aba aberta)
  function poeSeta(b, on) {
    if (!b || b.classList.contains("on") === on) return;
    var tinha = document.activeElement === b;
    b.classList.toggle("on", on);
    b.disabled = !on;
    if (!on && tinha) {
      var o = b === setaE ? setaD : setaE;
      var alvo = o && o.classList.contains("on") ? o : abas[atual];
      if (alvo) try { alvo.focus({ preventScroll: true }); } catch (e) { alvo.focus(); }
    }
  }

  // ---------------------------------------------------------------- mostrar uma aba
  function mostra(n) {
    if (!visivel(n)) n = primeira();
    if (!n) return null;
    var mudou = n !== atual, jaTinha = atual !== null;
    atual = n;
    ordem.forEach(function (k) {
      var on = k === n, t = abas[k], p = paineis[k];
      if (t.getAttribute("aria-selected") !== String(on)) t.setAttribute("aria-selected", on ? "true" : "false");
      t.setAttribute("tabindex", on ? "0" : "-1");
      if (p.hidden === on) p.hidden = !on;
    });
    if (grupo.getAttribute("data-ativa") !== n) grupo.setAttribute("data-ativa", n);
    emVista(abas[n], jaTinha);
    if (mudou) {
      monta(n);
      avisa(n);
    }
    return n;
  }

  // ---------------------------------------------------------------- "‹ anterior" e "próxima ›" no fim de cada aba
  // (pedido do Lucas, 4/11) no fim de cada painel, botões grandes para a aba anterior e a próxima (só as abas à vista). Trocam
  // a aba como o clique na barra (endereço próprio, Voltar do navegador, montar ao abrir), levam ao começo das abas e põem o
  // foco no título da aba nova
  function nomeAba(n) {
    var c = abas[n].cloneNode(true), ic = c.querySelector('[aria-hidden="true"]'), e = ic ? ic.textContent.trim() : "";
    [].forEach.call(c.querySelectorAll('[aria-hidden="true"], .sr'), function (x) { x.remove(); });
    return { ic: e, t: c.textContent.replace(/\s+/g, " ").trim() };
  }
  function botaoPasso(n, dir) {
    var a = nomeAba(n), b = document.createElement("button");
    var rot = dir < 0 ? EP.tr("Parte anterior", "Previous") : EP.tr("Próxima parte", "Next");
    b.type = "button";
    b.className = "abas-passo " + (dir < 0 ? "abas-passo-ant" : "abas-passo-prox");
    b.setAttribute("data-vai", n);
    b.setAttribute("aria-label", rot + ": " + a.t);
    b.innerHTML = (dir < 0 ? '<span class="ap-seta" aria-hidden="true">‹</span>' : "") + '<span class="ap-txt"><small>' + EP.esc(rot) + "</small><b>" +
      (a.ic ? '<span aria-hidden="true">' + EP.esc(a.ic) + " </span>" : "") + EP.esc(a.t) + "</b></span>" + (dir > 0 ? '<span class="ap-seta" aria-hidden="true">›</span>' : "");
    return b;
  }
  function poePassos() {
    var vis = ordem.filter(visivel);
    ordem.forEach(function (n) {
      var p = paineis[n], nav = p.querySelector(":scope > .abas-passos"), i = vis.indexOf(n);
      // (os nomes entram na chave: a tradução para o inglês chega às abas depois)
      var chave = i < 0 || vis.length < 2 ? "" : [vis[i - 1] || "", vis[i + 1] || "", vis[i - 1] ? nomeAba(vis[i - 1]).t : "", vis[i + 1] ? nomeAba(vis[i + 1]).t : ""].join("|");
      if (nav && nav.getAttribute("data-chave") === chave) return;
      if (nav) nav.remove();
      if (!chave) return;
      nav = document.createElement("div");  // um grupo (e não um "nav"): com várias abas à vista (impressão, testes), não repete o nome de um ponto de referência
      nav.setAttribute("role", "group");
      nav.className = "abas-passos nao-ler" + (secoes[n].classList.contains("miolo") ? " miolo" : "");
      nav.setAttribute("aria-label", EP.tr("Outras partes desta página", "Other parts of this page"));
      nav.setAttribute("data-chave", chave);
      if (vis[i - 1]) nav.appendChild(botaoPasso(vis[i - 1], -1));
      if (vis[i + 1]) nav.appendChild(botaoPasso(vis[i + 1], 1));
      p.appendChild(nav);
    });
  }
  function vaiPasso(n) {
    if (!visivel(n)) return;
    segura();
    mostra(n);
    poeEndereco(n, "push");
    vaiAoComeco();
    var h = secoes[n].querySelector("h2") || secoes[n].querySelector("h3");
    if (h) {
      if (!h.hasAttribute("tabindex")) h.setAttribute("tabindex", "-1");
      try { h.focus({ preventScroll: true }); } catch (e) { h.focus(); }
    }
  }
  A.mostra = function (id) {
    var n = nomeDe(id);
    if (!n) return null;
    var antes = atual;
    n = mostra(n);
    if (n && n !== antes) poeEndereco(n, "replace");
    return n;
  };
  EP.mostraSecao = function (id) { return A.mostra(id); };
  A.ativa = function () { return grupo ? atual : null; };
  A.quandoAbrir = function (id, fn) {
    var n = nomeDe(id);
    if (!n || montadas[n]) { fn(); return; }
    (fila[n] = fila[n] || []).push(fn);
  };

  // uma seção que some (ex.: "Quem assume em 2027" depois das posses) leva a aba junto; se era a aberta, abre a primeira
  function confereSecoes() {
    ordem.forEach(function (n) {
      var s = secoes[n], some = !s.isConnected || s.hidden || s.style.display === "none";
      if (!!abas[n].hidden === some) return;
      abas[n].hidden = some;
      abas[n].toggleAttribute("disabled", some);
      paineis[n].hidden = some;
    });
    if (atual && !visivel(atual)) {
      var era = atual, n = mostra(primeira());
      if (location.hash === "#" + era) poeEndereco(n, "replace");
    }
    poePassos();
  }

  // ---------------------------------------------------------------- montar
  A.monta = function (o) {
    o = o || {};
    if (grupo || !o.nav) return false;
    var itens = [];
    [].forEach.call(o.nav.querySelectorAll('a[href^="#"]'), function (a) {
      var id = a.getAttribute("href").slice(1), s = document.getElementById(id);
      if (s && s.tagName === "SECTION" && (s.classList.contains("bloco") || s.classList.contains("secao-perfil")) && !itens.some(function (x) { return x.id === id; })) itens.push({ id: id, s: s, a: a });
    });
    if (itens.length < 2) return false;
    caixa = document.createElement("div");
    caixa.className = "abas-ep";
    grupo = document.createElement("div");
    grupo.className = "tabs abas-grupo";
    lista = document.createElement("div");
    lista.className = "abas-lista";
    lista.setAttribute("role", "tablist");
    lista.setAttribute("aria-orientation", "horizontal");
    // o nome da barra para o leitor de tela, no idioma da página (o aria-label do menu "Ir direto para" não é traduzido)
    lista.setAttribute("aria-label", EP.tr("Partes desta página", "Parts of this page"));
    lista.id = "abas-lista";
    faixaAbas = document.createElement("div");
    faixaAbas.className = "abas-barra";
    setaE = seta(-1);
    setaD = seta(1);
    faixaAbas.appendChild(setaE);
    faixaAbas.appendChild(lista);
    faixaAbas.appendChild(setaD);
    grupo.appendChild(faixaAbas);
    var primeiro = itens[0].s;
    itens.forEach(function (it) {
      var n = it.id;
      ordem.push(n);
      secoes[n] = it.s;
      var t = document.createElement("button");
      t.type = "button";
      t.setAttribute("role", "tab");
      t.id = "aba-" + n;
      t.className = "aba nao-ler";  // o "Ouvir" lê a aba aberta, não os nomes das abas
      t.setAttribute("data-aba", n);
      t.setAttribute("aria-controls", "painel-" + n);
      t.setAttribute("aria-selected", "false");
      t.setAttribute("tabindex", "-1");
      t.innerHTML = it.a.innerHTML;
      abas[n] = t;
      lista.appendChild(t);
      var p = document.createElement("div");
      p.setAttribute("role", "tabpanel");
      p.setAttribute("data-aba", n);
      p.id = "painel-" + n;
      p.setAttribute("aria-labelledby", t.id);
      p.hidden = true;
      paineis[n] = p;
    });
    caixa.appendChild(grupo);
    primeiro.parentNode.insertBefore(caixa, primeiro);
    ordem.forEach(function (n) { paineis[n].appendChild(secoes[n]); grupo.appendChild(paineis[n]); });
    o.nav.remove();
    raiz.classList.add("com-abas");
    EP.topoFixo = topoFixo;

    // a aba do endereço (ou a primeira); com endereço de aba, rola até ela (ou até o elemento de dentro dela)
    var e = doEndereco();
    mostra(e.nome || ordem[0]);
    // voltando pelo histórico (ou recarregando), quem põe a página no lugar é a memória da rolagem (EP.memo, js/comum.js)
    var voltando = EP.memo && EP.memo.voltando() && EP.memo.le("y") != null;
    if (e.nome && !voltando) rolaPara(e.id);

    // o Basecoat (tabs) cuida do clique e das setas; antes dele (captura), guarda se a barra estava presa e se foi o teclado
    // (site-d-r14) o Basecoat troca os painéis antes de nós: com a barra presa, as abas seguram a altura já aqui (segura())
    grupo.addEventListener("click", function (ev) {
      estava = presa();
      var t = ev.target.closest ? ev.target.closest('[role="tab"], .abas-passo') : null;
      if (estava && t && grupo.contains(t)) segura();
    }, true);
    grupo.addEventListener("keydown", function (ev) {
      if (/^(Arrow(Left|Right)|Home|End)$/.test(ev.key) && ev.target.getAttribute && ev.target.getAttribute("role") === "tab") { teclado = true; estava = presa(); if (estava) segura(); }
    }, true);
    function depois(ev, modo) {
      var t = ev.target.closest ? ev.target.closest('[role="tab"]') : null;
      if (!t || !grupo.contains(t)) return;
      var sel = lista.querySelector('[role="tab"][aria-selected="true"]') || t, n = sel.getAttribute("data-aba");
      if (ev.type === "click") n = t.getAttribute("data-aba");
      if (!visivel(n)) return;
      // clicar na aba que já está aberta leva ao começo dela (útil no fim de uma lista comprida)
      if (n === atual) { if (ev.type === "click" && estava) vaiAoComeco(); return; }
      if (estava) segura();
      mostra(n);
      poeEndereco(n, modo);
      if (estava) vaiAoComeco();
    }
    grupo.addEventListener("click", function (ev) { depois(ev, "push"); });
    grupo.addEventListener("click", function (ev) {
      var b = ev.target.closest ? ev.target.closest(".abas-passo[data-vai]") : null;
      if (b && grupo.contains(b)) vaiPasso(b.getAttribute("data-vai"));
    });
    grupo.addEventListener("keydown", function (ev) {
      if (!teclado) return;
      teclado = false;
      // sem o js do Basecoat, as setas funcionam aqui mesmo
      if (!window.basecoat) {
        var vis = ordem.filter(visivel), i = vis.indexOf(atual), k = ev.key;
        var n = k === "Home" ? vis[0] : k === "End" ? vis[vis.length - 1] : vis[(i + (k === "ArrowRight" ? 1 : -1) + vis.length) % vis.length];
        ev.preventDefault();
        if (estava) segura();
        mostra(n);
        abas[n].focus();
        poeEndereco(n, "replace");
        if (estava) vaiAoComeco();
        return;
      }
      depois(ev, "replace");
    });
    // Voltar e Avançar do navegador, e links "#..." dentro da página
    var ultimoPop = 0;
    function peloEndereco(ev) {
      if (ev.type === "popstate") ultimoPop = Date.now();
      var x = doEndereco();
      if (x.id && !x.nome) return;  // um id fora das abas (ex.: #procurar, #conteudo): não muda de aba
      var n = x.nome || primeira(), est = presa();
      if (n !== atual) { if (est) segura(); mostra(n); if (est) vaiAoComeco(); }
      // um link "#..." dentro da página rola até o lugar; o Voltar e o Avançar só trocam a aba
      if (x.nome && ev.type === "hashchange" && Date.now() - ultimoPop > 100) rolaPara(x.id);
    }
    window.addEventListener("popstate", peloEndereco);
    window.addEventListener("hashchange", peloEndereco);

    // seções que somem levam a aba junto
    var obs = new MutationObserver(confereSecoes);
    new MutationObserver(function () { poePassos(); }).observe(lista, { childList: true, characterData: true, subtree: true });
    ordem.forEach(function (n) { obs.observe(secoes[n], { attributes: true, attributeFilter: ["hidden", "style"] }); });
    confereSecoes();

    // alturas do cabeçalho e da barra (para a barra grudar logo abaixo do cabeçalho e o scroll-padding descontar as duas)
    poeAlturas();
    if ("ResizeObserver" in window) {
      var ro = new ResizeObserver(poeAlturas);
      var topo = document.querySelector("header.topo");
      if (topo) ro.observe(topo);
      ro.observe(lista);
      ro.observe(faixaAbas);
    } else window.addEventListener("resize", poeAlturas);
    window.addEventListener("ep-a11y", poeAlturas);
    // a barra rola para o lado sem barra de rolagem à vista: a roda do mouse (para cima e para baixo) também rola a barra, e as
    // bordas esmaecem do lado em que há abas escondidas (mandatos-r11: medido pelas próprias abas, não pela largura da barra:
    // só esmaece quando uma aba passa mesmo da borda)
    function bordas() {
      var vis = ordem.filter(visivel).map(function (n) { return abas[n]; });
      if (!vis.length) return;
      var rl = lista.getBoundingClientRect(), a = vis[0].getBoundingClientRect(), z = vis[vis.length - 1].getBoundingClientRect();
      var esq = a.left < rl.left - 1, dir = z.right > rl.right + 1;
      lista.classList.toggle("mais-esq", esq);
      lista.classList.toggle("mais-dir", dir);
      poeSeta(setaE, esq);
      poeSeta(setaD, dir);
    }
    // mandatos-r11: o recuo da esquerda acompanha o texto da página; se as abas não cabem com ele, ele diminui (até a borda
    // mínima, --abas-borda) antes de a barra precisar rolar. Medido de novo quando as abas mudam de tamanho (fontes e emojis
    // que chegam depois, letra maior, aba que some ou aparece) e quando a janela muda
    var medindo = 0;
    function ajusta() {
      var vis = ordem.filter(visivel).map(function (n) { return abas[n]; });
      // mede sem os botões ‹ › (eles só entram quando a barra precisa rolar) e sem perder o lugar em que a barra estava
      var era = faixaAbas.classList.contains("rola"), sl = lista.scrollLeft;
      faixaAbas.classList.remove("rola");
      lista.style.removeProperty("--abas-esq");
      if (vis.length) {
        var cs = getComputedStyle(lista), pl = parseFloat(cs.paddingLeft) || 0, pr = parseFloat(cs.paddingRight) || 0;
        var min = parseFloat(cs.getPropertyValue("--abas-borda")) || 0;
        var a = vis[0], z = vis[vis.length - 1];
        var total = z.getBoundingClientRect().right - a.getBoundingClientRect().left;
        var cabe = Math.floor(lista.clientWidth - pr - total - 1);
        if (pl > min && cabe < pl) lista.style.setProperty("--abas-esq", Math.max(min, cabe) + "px");
      }
      var rola = lista.scrollWidth > lista.clientWidth + 1;
      faixaAbas.classList.toggle("rola", rola);
      lista.scrollLeft = sl;
      bordas();
      // os botões entraram ou saíram (a parte que rola mudou de largura): a aba aberta continua à vista
      if (rola !== era) emVista(abas[atual]);
      marcaFora();
    }
    function pedeAjuste() { cancelAnimationFrame(medindo); medindo = requestAnimationFrame(ajusta); }
    lista.addEventListener("scroll", function () { bordas(); rolando(); }, { passive: true });
    if ("onscrollend" in window) lista.addEventListener("scrollend", marcaFora);
    window.addEventListener("resize", pedeAjuste);
    window.addEventListener("ep-a11y", pedeAjuste);
    if ("ResizeObserver" in window) {
      var roAbas = new ResizeObserver(pedeAjuste);
      roAbas.observe(lista);
      ordem.forEach(function (n) { roAbas.observe(abas[n]); });
    }
    if (document.fonts) {
      if (document.fonts.ready) document.fonts.ready.then(pedeAjuste);
      if (document.fonts.addEventListener) document.fonts.addEventListener("loadingdone", pedeAjuste);
    }
    window.addEventListener("load", pedeAjuste);
    lista.addEventListener("wheel", function (ev) {
      var max = lista.scrollWidth - lista.clientWidth;
      if (max <= 2 || Math.abs(ev.deltaX) > Math.abs(ev.deltaY)) return;
      // com o scroll-snap, somar pixels à posição voltaria para a mesma aba: a roda anda até a próxima aba daquele lado
      var g = geo(), dir = ev.deltaY > 0 ? 1 : -1, p;
      if (dir > 0) { var x = g.tabs.filter(function (y) { return y.a - g.pl > g.sl + 1; })[0]; p = x ? Math.min(g.max, x.a - g.pl) : g.max; }
      else { var z = g.tabs.filter(function (y) { return y.a - g.pl < g.sl - 1; }).pop(); p = z ? Math.max(0, z.a - g.pl) : 0; }
      if (p > g.max - 2) p = g.max;
      if (p < 2) p = 0;
      if (Math.abs(p - g.sl) < 1) return;
      ev.preventDefault();
      rolaAte(p, false);
    }, { passive: false });
    ajusta();
    // o js do Basecoat (tabs) liga o clique e as setas
    if (window.basecoat && window.basecoat.init) window.basecoat.init("tabs");
    return true;
  };
})();
