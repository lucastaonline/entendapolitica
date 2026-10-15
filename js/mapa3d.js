/* Mapa da Política: mundo 3D com os 9 lugares (paradas) da página "Entenda a política".
   window.MAPA.montar(tela, lugares, aoEscolher); .estado(feitos, proximo); .voar(n) -> Promise; .geral(); .lista() */
(function () {
  "use strict";
  var EP = window.EP, T = window.TRES || {};
  var esc = EP.esc;
  var M = (window.MAPA = {});

  // posição no chão (1000 x 1000), modelo, base do modelo (y do "chão" do modelo), escala e altura da placa
  var POS = {
    1: { x: 790, y: 790, modelo: "escola", base: 90, esc: .55, hp: 175 },
    2: { x: 500, y: 830, modelo: "poderes", base: 74, esc: .5, hp: 110 },
    3: { x: 205, y: 790, modelo: "niveis", base: 94, esc: .5, hp: 130 },
    4: { x: 190, y: 500, modelo: "cargos", base: 0, esc: .6, hp: 215 },
    5: { x: 500, y: 500, modelo: "congresso", base: 60, esc: .58, hp: 165 },
    6: { x: 810, y: 500, modelo: "lei", base: 0, esc: .66, hp: 190 },
    7: { x: 795, y: 205, modelo: "urna", base: 0, esc: .62, hp: 180 },
    8: { x: 500, y: 175, modelo: "tribunal", base: 46, esc: .52, hp: 150 },
    9: { x: 205, y: 210, modelo: "palanque", base: 0, esc: .6, hp: 170 }
  };
  var ENFEITES = [
    ["🌳", 46, 330], ["🌳", 46, 660], ["🌲", 340, 50], ["🌳", 660, 46], ["🌲", 955, 340], ["🌳", 955, 650], ["🌳", 340, 955], ["🌲", 650, 955],
    ["🌳", 60, 60], ["🌲", 935, 70], ["🌳", 70, 930], ["🌻", 640, 660], ["🌷", 360, 640], ["🌼", 650, 350], ["🦆", 355, 350], ["🚩", 930, 905]
  ];
  var cam = { ax: 56, az: 42, z: .8, cx: 0, cy: 0, ox: 50, oy: 56 }, fit = .8;
  var tela, mundo, lugares = [], aoEscolher = null, focado = null, oyBase = 56;

  function modelo(nome) {
    var o = { mundo: true };
    switch (nome) {
      case "escola": return T.escola ? T.escola(o) : "";
      case "poderes": return T.tresPoderes ? T.tresPoderes(o) : "";
      case "niveis": return T.niveis ? T.niveis(o) : "";
      case "cargos": return T.torreCargos ? T.torreCargos(o) : "";
      case "congresso": return T.congresso ? T.congresso(o) : "";
      case "lei": return T.lei ? T.lei(o) : "";
      case "urna": return T.urnaMesa ? T.urnaMesa(o) : "";
      case "tribunal": return T.tribunal ? T.tribunal(o) : "";
      case "palanque": return T.palanque ? T.palanque(o) : "";
    }
    return "";
  }
  function cartaz(txt, x, y, h, t) {
    return '<div class="enfeite" style="--x:' + x + "px;--y:" + y + 'px" aria-hidden="true"><span class="cartaz" style="--h:' + (h || 0) + "px;--t:" + (t || 64) + 'px">' + txt + "</span></div>";
  }
  function estadoAria(L) {
    var s = ". " + EP.tr("Parada ", "Stop ") + L.n + EP.tr(" de 9", " of 9");
    if (L.feito) s += EP.tr(". Você já aprendeu.", ". Already learned.");
    else if (L.proximo) s += EP.tr(". Próxima parada sugerida.", ". Suggested next stop.");
    if (!L.temConteudo) s += EP.tr(". Em breve.", ". Coming soon.");
    return s;
  }

  // ---------------------------------------------------------------- câmera
  function aplica() {
    var s = mundo.style;
    s.setProperty("--ax", cam.ax + "deg");
    s.setProperty("--az", cam.az + "deg");
    s.setProperty("--z", cam.z.toFixed(4));
    s.setProperty("--cx", cam.cx + "px");
    s.setProperty("--cy", cam.cy + "px");
    s.setProperty("--lz", Math.max(.9, Math.min(tela.classList.contains("estreito") ? 1.7 : 2.4, .62 / cam.z)).toFixed(3));
    s.setProperty("--ox", cam.ox + "%");
    s.setProperty("--oy", cam.oy + "%");
  }
  function calculaFit() {
    var r = tela.getBoundingClientRect();
    var estreito = r.width < 700;
    fit = estreito ? Math.min(r.width / 1010, r.height / 780) : Math.min(r.width / 1250, r.height / 900);
    fit = Math.max(.27, Math.min(1.05, fit));
    tela.classList.toggle("estreito", estreito);
    oyBase = estreito ? 41 : 56;
    return fit;
  }
  M.ajustar = function () {
    var antes = fit;
    calculaFit();
    if (!focado) { cam.z = fit; cam.oy = oyBase; }
    else cam.z = cam.z * fit / antes;
    aplica();
  };
  M.geral = function () {
    focado = null;
    cam.cx = 0; cam.cy = 0; cam.z = fit; cam.ox = 50; cam.oy = oyBase; cam.ax = 56;
    aplica();
  };
  M.voar = function (n) {
    var p = POS[n];
    focado = n;
    cam.cx = 500 - p.x; cam.cy = 500 - p.y;
    cam.z = Math.min(2.4, fit * 2.3);
    cam.oy = 62;
    aplica();
    return new Promise(function (ok) { setTimeout(ok, EP.reduzido ? 30 : 950); });
  };
  M.girar = function (graus) { cam.az += graus; aplica(); };

  // ---------------------------------------------------------------- estado (feitos e próxima parada)
  M.estado = function (feitos, proximo, info) {
    lugares.forEach(function (L) {
      L.feito = !!feitos[L.n];
      L.proximo = L.n === proximo;
      if (info && info[L.n]) { L.nome = info[L.n].nome; L.ic = info[L.n].ic; L.temConteudo = info[L.n].tem; }
      L.el.classList.toggle("feito", L.feito);
      L.el.classList.toggle("proximo", L.proximo);
      L.el.classList.toggle("sem-conteudo", !L.temConteudo);
      L.el.querySelector(".pl-ic").textContent = L.ic;
      L.el.querySelector(".pl-nome").textContent = L.nome;
      L.el.querySelector(".pl-estado").textContent = estadoAria(L);
    });
    var todos = lugares.every(function (L) { return L.feito; });
    tela.classList.toggle("todos-feitos", todos);
  };

  // ---------------------------------------------------------------- montar
  M.montar = function (el, info, cb) {
    tela = el;
    aoEscolher = cb;
    var estrada = [1, 2, 3, 4, 5, 6, 7, 8, 9].map(function (n) { return POS[n].x + " " + POS[n].y; }).join(" L");
    var html = '<div class="mundo" role="group" aria-label="' + esc(EP.tr("Mapa da política com 9 paradas", "Politics map with 9 stops")) + '">' +
      '<div class="chao" aria-hidden="true"><div class="sombra-mundo"></div><div class="grama"></div><i class="rim s"></i><i class="rim e"></i><i class="rim n"></i><i class="rim w"></i>' +
      '<div class="lagoa"></div><svg class="estrada" viewBox="0 0 1000 1000" width="1000" height="1000" aria-hidden="true">' +
      '<path d="M' + estrada + '" fill="none" stroke="#eadcb8" stroke-width="58" stroke-linejoin="round" stroke-linecap="round"/>' +
      '<path d="M' + estrada + '" fill="none" stroke="#f6edd6" stroke-width="46" stroke-linejoin="round" stroke-linecap="round"/>' +
      '<path d="M' + estrada + '" fill="none" stroke="#f2b705" stroke-width="10" stroke-dasharray="2 26" stroke-linejoin="round" stroke-linecap="round"/></svg></div>';
    ENFEITES.forEach(function (e) { html += cartaz(e[0], e[1], e[2], 0, e[0] === "🚩" || e[0] === "🏁" ? 70 : 64); });
    html += '<div class="nuvem" style="--y:250px;--dur:110s" aria-hidden="true"><span class="cartaz" style="--h:430px;--t:90px">☁️</span></div>' +
      '<div class="nuvem" style="--y:720px;--dur:140s;--atraso:-60s" aria-hidden="true"><span class="cartaz" style="--h:480px;--t:110px">☁️</span></div>' +
      '<div class="andarilho" aria-hidden="true"><span class="cartaz"><span>🚶</span></span></div>' +
      cartaz("🏆", 500, 500, 330, 120).replace('class="enfeite"', 'class="enfeite trofeu-final"');
    [1, 2, 3, 4, 5, 6, 7, 8, 9].forEach(function (n) {
      var p = POS[n], I = info[n] || {};
      html += '<div class="lugar" data-n="' + n + '" style="--x:' + p.x + "px;--y:" + p.y + "px;--esc:" + p.esc + ";--base:" + p.base + "px;--hp:" + p.hp + 'px">' +
        '<div class="lote" aria-hidden="true"><i class="t"></i><i class="s"></i><i class="e"></i><i class="n"></i><i class="w"></i></div>' +
        '<div class="em-pe" aria-hidden="true">' + modelo(p.modelo) + "</div>" +
        '<div class="placa" role="button" tabindex="0"><span class="pl-num">' + n + '</span><span class="pl-ic" aria-hidden="true">' + esc(I.ic || "") + '</span><span class="pl-nome">' + esc(I.nome || "") +
        '</span><span class="pl-estrela" aria-hidden="true">⭐</span><span class="sr pl-estado"></span></div><div class="seta-prox" aria-hidden="true"><span>👇</span></div></div>';
    });
    html += "</div>";
    tela.insertAdjacentHTML("afterbegin", html);
    mundo = tela.querySelector(".mundo");
    lugares = [].map.call(tela.querySelectorAll(".lugar"), function (el) {
      var n = +el.getAttribute("data-n");
      return { n: n, el: el, nome: (info[n] || {}).nome || "", ic: (info[n] || {}).ic || "", temConteudo: !!(info[n] || {}).tem };
    });
    // urnas do mapa apertam CONFIRMA de vez em quando
    if (T.confirma) [].forEach.call(tela.querySelectorAll(".urna3d"), function (u) { T.confirma(u, 2500, true); });
    calculaFit();
    cam.z = fit;
    cam.oy = oyBase;
    aplica();
    ligaEventos();
    andarilho();
    window.addEventListener("resize", M.ajustar);
  };

  // ---------------------------------------------------------------- arrastar, roda, pinça e teclado
  function ligaEventos() {
    var ptrs = {}, x0 = 0, y0 = 0, az0 = 0, ax0 = 0, moveu = false, dist0 = 0, z0 = 0;
    tela.addEventListener("pointerdown", function (e) {
      if (e.target.closest(".mapa-ui")) return;
      ptrs[e.pointerId] = { x: e.clientX, y: e.clientY };
      var ids = Object.keys(ptrs);
      if (ids.length === 1) { x0 = e.clientX; y0 = e.clientY; az0 = cam.az; ax0 = cam.ax; moveu = false; }
      if (ids.length === 2) { var a = ptrs[ids[0]], b = ptrs[ids[1]]; dist0 = Math.hypot(a.x - b.x, a.y - b.y); z0 = cam.z; }
    });
    tela.addEventListener("pointermove", function (e) {
      if (!ptrs[e.pointerId]) return;
      ptrs[e.pointerId] = { x: e.clientX, y: e.clientY };
      var ids = Object.keys(ptrs);
      if (ids.length === 2) {
        var a = ptrs[ids[0]], b = ptrs[ids[1]], d = Math.hypot(a.x - b.x, a.y - b.y);
        cam.z = Math.max(fit * .8, Math.min(fit * 2.8, z0 * d / Math.max(1, dist0)));
        moveu = true;
        tela.classList.add("arrastando");
        aplica();
        return;
      }
      var dx = e.clientX - x0, dy = e.clientY - y0;
      if (!moveu && Math.hypot(dx, dy) < 7) return;
      if (!moveu) { moveu = true; tela.classList.add("arrastando"); try { tela.setPointerCapture(e.pointerId); } catch (er) {} }
      cam.az = az0 - dx * 0.3;
      cam.ax = Math.max(32, Math.min(72, ax0 - dy * 0.18));
      aplica();
    });
    function solta(e) {
      delete ptrs[e.pointerId];
      if (!Object.keys(ptrs).length) setTimeout(function () { tela.classList.remove("arrastando"); }, 0);
    }
    tela.addEventListener("pointerup", solta);
    tela.addEventListener("pointercancel", solta);
    tela.addEventListener("click", function (e) {
      if (moveu) { moveu = false; return; }
      var l = e.target.closest(".lugar");
      if (l && aoEscolher) aoEscolher(+l.getAttribute("data-n"));
    });
    tela.addEventListener("wheel", function (e) {
      if (e.target.closest(".mapa-ui")) return;
      e.preventDefault();
      cam.z = Math.max(fit * .8, Math.min(fit * 2.8, cam.z * (e.deltaY < 0 ? 1.1 : 0.9)));
      aplica();
    }, { passive: false });
    tela.addEventListener("keydown", function (e) {
      var l = e.target.closest && e.target.closest(".lugar");
      if (l && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); if (aoEscolher) aoEscolher(+l.getAttribute("data-n")); return; }
      if (e.target.closest && e.target.closest(".mapa-ui")) return;
      if (e.key === "ArrowLeft") { e.preventDefault(); M.girar(15); }
      else if (e.key === "ArrowRight") { e.preventDefault(); M.girar(-15); }
      else if (e.key === "ArrowUp") { e.preventDefault(); cam.ax = Math.max(32, cam.ax - 6); aplica(); }
      else if (e.key === "ArrowDown") { e.preventDefault(); cam.ax = Math.min(72, cam.ax + 6); aplica(); }
      else if (e.key === "+" || e.key === "=") { cam.z = Math.min(fit * 2.8, cam.z * 1.15); aplica(); }
      else if (e.key === "-") { cam.z = Math.max(fit * .8, cam.z * .87); aplica(); }
    });
  }

  // ---------------------------------------------------------------- bonequinho andando pela trilha
  function andarilho() {
    var el = tela.querySelector(".andarilho");
    if (!el) return;
    if (EP.reduzido) { el.hidden = true; return; }
    var pts = [1, 2, 3, 4, 5, 6, 7, 8, 9].map(function (n) { return POS[n]; });
    var seg = 0, t = 0, pausa = 0, ultimo = null;
    function passo(agora) {
      if (ultimo === null) ultimo = agora;
      var dt = Math.min(100, agora - ultimo) / 1000;
      ultimo = agora;
      if (!document.hidden && !EP.reduzido && tela.offsetParent !== null) {
        if (pausa > 0) pausa -= dt;
        else {
          var a = pts[seg], b = pts[(seg + 1) % pts.length];
          var len = Math.hypot(b.x - a.x, b.y - a.y);
          t += (dt * 55) / len;
          if (t >= 1) { t = 0; seg = (seg + 1) % (pts.length - 1); pausa = 1.2; if (seg === 0) pausa = 3; }
          a = pts[seg]; b = pts[seg + 1];
          var x = a.x + (b.x - a.x) * t, y = a.y + (b.y - a.y) * t;
          el.style.setProperty("--x", x.toFixed(1) + "px");
          el.style.setProperty("--y", y.toFixed(1) + "px");
          var r = cam.az * Math.PI / 180, sx = (b.x - a.x) * Math.cos(r) - (b.y - a.y) * Math.sin(r);
          el.classList.toggle("volta", sx > 0);
        }
      }
      requestAnimationFrame(passo);
    }
    requestAnimationFrame(passo);
  }

  // ---------------------------------------------------------------- lista (alternativa acessível ao 3D)
  M.lista = function () {
    EP.abrir("📋 " + EP.tr("As 9 paradas", "The 9 stops"), '<p class="muted">' + EP.tr("A ordem é só uma sugestão: escolha qualquer uma.", "The order is just a suggestion: pick any stop.") + '</p><ol class="lista-lugares">' +
      lugares.map(function (L) {
        return '<li class="' + (L.feito ? "feito" : "") + '"><button type="button" data-abrir-parada="' + L.n + '"><span class="ll-num">' + L.n + '</span><span class="ll-ic" aria-hidden="true">' + esc(L.ic) + "</span>" +
          "<span><b>" + esc(L.nome) + "</b><small>" + (L.feito ? "⭐ " + EP.tr("Você já aprendeu", "Already learned") : L.proximo ? "👉 " + EP.tr("Próxima sugerida", "Suggested next") : "") +
          (!L.temConteudo ? EP.tr(" Em breve", " Coming soon") : "") + "</small></span></button></li>";
      }).join("") + "</ol>");
  };
})();
