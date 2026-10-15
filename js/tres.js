/* Peças 3D compartilhadas (ver css/tres.css): formas flutuantes, urna, cubo e colunas. */
(function () {
  "use strict";
  var CORES = ["#f2b705", "#1f3a5f", "#e08a00", "#8fb3d9", "#ffd08a", "#c9b8f0", "#9fd8cd"];
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  // lista: [tipo ("cubo" | "esfera" | "anel"), x, y, tamanho em px, cor (0-6), profundidade ao rolar, duração em s]
  function formas(lista, classe) {
    return '<div class="formas' + (classe ? " " + classe : "") + '" aria-hidden="true">' + lista.map(function (f) {
      var miolo = f[0] === "cubo" ? "<b></b><b></b><b></b><b></b><b></b><b></b>" : f[0] === "anel" ? "<b></b><b></b>" : "";
      return '<span class="forma ' + f[0] + '" style="--x:' + f[1] + ";--y:" + f[2] + ";--s:" + f[3] + "px;--c:" + CORES[f[4] % CORES.length] + ";--d:" + f[5] + ";--t:" + f[6] + 's"><i>' + miolo + "</i></span>";
    }).join("") + "</div>";
  }
  // urna: o = { id, auto (balança sozinha), peq (menor) }
  function urna(o) {
    o = o || {};
    return '<div class="cena-urna' + (o.peq ? " peq" : "") + '" aria-hidden="true"><div class="sombra-urna"></div>' +
      '<div class="urna3d' + (o.auto ? " auto" : "") + (o.peq ? " peq" : "") + '"' + (o.id ? ' id="' + o.id + '"' : "") + ">" +
      '<div class="f frente"><div class="tela-urna">' + esc(o.tela || "SEU VOTO") + '<div class="quadros"><i></i><i></i></div><small>Digite o número</small><div class="fim-urna">FIM</div></div>' +
      '<div class="teclado"><i>1</i><i>2</i><i>3</i><i>4</i><i>5</i><i>6</i><i>7</i><i>8</i><i>9</i><i class="zero">0</i>' +
      '<div class="teclas-cor"><i class="br">BRANCO</i><i class="co">CORRIGE</i><i class="cfm">CONFIRMA</i></div></div></div>' +
      '<div class="f tras"></div><div class="f ldd"></div><div class="f lde"></div><div class="f tp"></div><div class="f bs"></div>' +
      '<span class="dedo3d">👆</span></div></div>';
  }
  // aperta CONFIRMA de tempos em tempos (ou uma vez, se repetir = false)
  function confirma(el, atraso, repetir) {
    if (!el) return;
    var reduzido = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduzido) { el.classList.add("confirmado"); return; }
    setTimeout(function ciclo() {
      el.classList.add("confirmado");
      if (repetir) setTimeout(function () { el.classList.remove("confirmado"); setTimeout(ciclo, 2600); }, 3200);
    }, atraso || 2000);
  }
  // cubo com o número (faces ímpares) e o ícone (faces pares)
  function cubo(num, ic, classe, tam) {
    var faces = "";
    for (var i = 0; i < 6; i++) faces += "<b>" + (i < 4 ? esc(i % 2 ? ic : num) : "") + "</b>";
    return '<div class="cubo-num' + (classe ? " " + classe : "") + '"' + (tam ? ' style="--s:' + tam + 'px"' : "") + ' aria-hidden="true"><i>' + faces + "</i></div>";
  }
  function col(h, cor, rot) {
    return '<div class="col3d" style="--h:' + h + ";--cor:" + cor + '"><div class="cresce"><div class="cf frente"></div><div class="cf ld"></div><div class="cf tp"></div></div>' +
      (rot ? '<span class="rot-col">' + rot + "</span>" : "") + "</div>";
  }
  // avatares (*-mini.jpg, 240 px): oferece também a versão de 120 px. Reduzir muito uma foto dentro das
  // cenas 3D deixava a imagem granulada em algumas máquinas; com o tamanho certo, isso não acontece.
  function srcsetMini(src) {
    if (!/-mini\.jpg$/.test(src || "")) return "";
    return ' sizes="64px" srcset="' + src.replace(/\.jpg$/, "-120.jpg") + " 120w, " + src + ' 240w"';
  }
  window.TRES = { formas: formas, urna: urna, confirma: confirma, cubo: cubo, col: col, CORES: CORES, srcsetMini: srcsetMini };
})();
