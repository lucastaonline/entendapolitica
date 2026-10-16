/* Peças 3D do Entenda Política (ver css/tres-politica.css). Estende window.TRES (js/tres.js).
   Cada modelo funciona em dois modos:
   - normal: dentro de uma "cena" com perspectiva e girando sozinho (slides e páginas);
   - mundo (o.mundo = true): só o modelo, parado, para ser colocado de pé no mapa 3D. */
(function () {
  "use strict";
  var T = (window.TRES = window.TRES || {});

  function caixa(classe, faces, estilo) {
    faces = faces || {};
    return '<div class="cx ' + classe + '"' + (estilo ? ' style="' + estilo + '"' : "") + '><i class="fr">' + (faces.fr || "") + '</i><i class="tr"></i><i class="ld">' + (faces.ld || "") +
      '</i><i class="le"></i><i class="tp">' + (faces.tp || "") + '</i><i class="bs"></i></div>';
  }
  // fatias de meio-disco giradas em volta do eixo vertical: viram cúpula/cuia "sólidas"
  function fatias(n) {
    var h = "";
    for (var k = 0; k < n; k++) {
      var a = (k * 180) / n;
      var b = (0.84 + 0.16 * Math.cos(((a - 30) * Math.PI) / 180)).toFixed(3);
      h += '<i style="--a:' + a.toFixed(1) + "deg;--b:" + b + '"></i>';
    }
    return h;
  }
  function cena(classe, miolo) { return '<div class="cena3d ' + classe + '" aria-hidden="true">' + miolo + "</div>"; }
  // âncora do modelo: no modo mundo não tem cena, giro nem deslocamento
  function modelo(o, classeCena, classes, miolo) {
    o = o || {};
    if (o.mundo) return '<div class="ancora3d no-mundo ' + classes + '">' + miolo + "</div>";
    return cena(classeCena, '<div class="ancora3d ' + classes + (o.auto !== false ? " auto" : "") + '">' + miolo + "</div>");
  }
  function emoji(e, x, y, z, tam) {
    return '<span class="emoji3d" style="transform:translate3d(' + x + "px," + y + "px," + z + "px);font-size:" + (tam || 40) + 'px">' + e + "</span>";
  }
  T.caixa = caixa;

  // ---------------------------------------------------------------- Congresso Nacional
  T.congresso = function (o) {
    o = o || {};
    return modelo(o, "cena-congresso", "congresso3d",
      (o.mundo ? "" : '<div class="sombra-chao"></div>') + '<div class="espelho"></div>' +
      caixa("laje") + caixa("torre t1") + caixa("torre t2") + caixa("ponte") +
      '<div class="cupula">' + fatias(16) + "</div>" +
      '<div class="cuia">' + fatias(16) + '<i class="boca"></i></div>' +
      (o.rotulos ? '<span class="rotulo3d r-sen">🏛️ ' + (window.EP && EP.en ? "Senate" : "Senado") + '</span><span class="rotulo3d r-cam">🏛️ ' + (window.EP && EP.en ? "Chamber" : "Câmara") + "</span>" : ""));
  };

  // ---------------------------------------------------------------- Três Poderes: colunas da mesma altura, em triângulo
  T.tresPoderes = function (o) {
    o = o || {};
    var en = window.EP && EP.en;
    function pilar(cl, ic, nome) { return caixa("pilar " + cl, { fr: "<span>" + ic + "</span><small>" + nome + "</small>" }); }
    return modelo(o, "cena-poderes", "poderes3d",
      (o.mundo ? "" : '<div class="sombra-chao"></div>') + caixa("base") +
      pilar("p-exe", "🏢", en ? "Executive" : "Executivo") + pilar("p-leg", "📜", en ? "Legislative" : "Legislativo") + pilar("p-jud", "⚖️", en ? "Judiciary" : "Judiciário"));
  };

  // ---------------------------------------------------------------- níveis: país, estado e cidade empilhados
  T.niveis = function (o) {
    o = o || {};
    var en = window.EP && EP.en;
    function nivel(cl, ic, nome) { return caixa("nivel " + cl, { fr: "<span>" + ic + "</span>" + nome }); }
    return modelo(o, "cena-niveis", "niveis3d" + (o.entra ? " entra" : ""),
      nivel("n-cidade", "🏘️", en ? "City" : "Cidade") + nivel("n-estado", "🗺️", en ? "State" : "Estado") + nivel("n-pais", "🏛️", en ? "Country" : "País"));
  };

  T.livro = function (o) {
    var en = window.EP && EP.en;
    return modelo(o, "cena-livro", "livro3d", caixa("capa", { fr: "<b>" + (en ? "CONSTITUTION" : "CONSTITUIÇÃO") + "</b><span>📖</span><small>1988</small>" }));
  };

  T.balanca = function () {
    return cena("cena-balanca", '<div class="balanca"><div class="pe"></div><div class="poste"></div><div class="topo-b"></div>' +
      '<div class="viga"><div class="prato e"><i></i><b></b></div><div class="prato d"><i></i><b></b></div></div></div>');
  };

  function folha() {
    var en = window.EP && EP.en;
    return '<div class="folha3d"><b>' + (en ? "BILL" : "PROJETO DE LEI") + '</b><i></i><i></i><i></i><i></i><i></i><i></i><i></i><span class="selo-lei">' + (en ? "LAW ✓" : "LEI ✓") + "</span></div>";
  }
  T.lei = function (o) {
    o = o || {};
    if (o.mundo) {
      // pedestal com a folha de pé em cima
      return '<div class="ancora3d no-mundo pedestal3d">' + caixa("pedestal", { fr: "<span>💡 ➜ 📄 ➜ 📜</span>" }) + '<div class="folha-pe">' + folha() + "</div></div>";
    }
    return cena("cena-lei", folha());
  };

  T.cofre = function (o) {
    var moedas = "";
    for (var k = 0; k < 3; k++) moedas += '<span class="moeda" style="--atraso:' + (k * 0.8) + "s;left:" + (-60 + k * 38) + 'px">R$</span>';
    var en = window.EP && EP.en;
    return modelo(o, "cena-cofre", "cofre3d", caixa("caixa", { fr: "<span>🏦</span>" + (en ? "Everyone's money" : "Dinheiro de todos") }) + moedas);
  };

  // ---------------------------------------------------------------- plenário (cadeiras em semicírculo, responsivo)
  // o.total ou o.linhas; o.grupos = [n1, n2, ...] marca "fatias" (data-g) da esquerda para a direita; o.max = largura máxima em px.
  T.plenario = function (o) {
    o = o || {};
    var W = 1000, H = 560, cx = 500, cy = 540, rMax = 480;
    var linhas = o.linhas;
    if (!linhas) {
      var total = o.total || 81, nl = total > 300 ? 7 : total > 120 ? 6 : total > 50 ? 5 : total > 20 ? 4 : 3, pesos = [], soma = 0;
      for (var i = 0; i < nl; i++) { pesos.push(1 + i * 0.45); soma += pesos[i]; }
      linhas = pesos.map(function (p) { return Math.max(3, Math.round(total * p / soma)); });
      linhas[nl - 1] += total - linhas.reduce(function (a, b) { return a + b; }, 0);
    }
    var nl2 = linhas.length, r0 = rMax / (1 + 0.45 * (nl2 - 1)), passo = nl2 > 1 ? (rMax - r0) / (nl2 - 1) : 0;
    var lugares = [], somaR = 0;
    linhas.forEach(function (n, li) {
      var r = r0 + li * passo;
      somaR += r;
      for (var j = 0; j < n; j++) {
        var t = Math.PI - (Math.PI * (j + 0.5)) / n;
        lugares.push({ x: cx + r * Math.cos(t), y: cy - r * Math.sin(t), a: t });
      }
    });
    var max = o.max || 340;
    var espaco = (Math.PI * somaR / Math.max(1, lugares.length)) * (max / W);
    var tam = Math.max(3, Math.min(16, Math.round(espaco * 0.72)));
    lugares.sort(function (a, b) { return b.a - a.a; });
    var grupoDe = [];
    (o.grupos || []).forEach(function (n, g) { for (var k = 0; k < n; k++) grupoDe.push(g); });
    var h = lugares.map(function (l, k) {
      return '<i style="left:' + (100 * l.x / W).toFixed(2) + "%;top:" + (100 * l.y / H).toFixed(2) + "%;--k:" + (k % 120) + '"' +
        (grupoDe[k] != null ? ' data-g="' + grupoDe[k] + '"' : "") + "></i>";
    }).join("");
    return '<div class="plenario' + (o.cheio ? " cheio" : "") + '" style="--max:' + max + "px;--tam:" + tam + 'px" aria-hidden="true">' + h + '<span class="mesa"></span></div>';
  };

  T.megafone = function () {
    var ondas = "";
    for (var k = 0; k < 3; k++) ondas += '<span class="onda" style="--atraso:' + (k * 0.8) + 's"></span>';
    return cena("cena-megafone", '<div class="megafone"><span>📣</span>' + ondas + "</div>");
  };

  // ---------------------------------------------------------------- prédio (prefeitura) e escola
  function predioMiolo(o, extra) {
    var janelas = "";
    for (var k = 0; k < 8; k++) janelas += "<span></span>";
    return (o.mundo ? "" : '<div class="sombra-chao"></div>') + caixa("corpo", { fr: (extra && extra.placa ? '<em class="placa-predio">' + extra.placa + "</em>" : "") + janelas + '<span class="porta"></span>' }) +
      '<div class="frontao"></div><div class="mastro"></div><div class="bandeira"></div>' + (extra && extra.mais ? extra.mais : "");
  }
  T.predio = function (o) { return modelo(o, "cena-predio", "predio3d", predioMiolo(o || {})); };
  T.escola = function (o) {
    o = o || {};
    var en = window.EP && EP.en;
    return modelo(o, "cena-predio", "predio3d escola3d", predioMiolo(o, {
      placa: en ? "SCHOOL" : "ESCOLA",
      mais: caixa("sino", { fr: "<span>🔔</span>" }) + emoji("🧒", -88, 30, 80, 46) + emoji("👧", -40, 34, 92, 44) + emoji("🗳️", 30, 40, 88, 40) + emoji("🧑‍🦽", 70, 30, 80, 46)
    }));
  };

  // prefeitura (página "A política da minha cidade"): o prédio com placa, árvore e ônibus da cidade
  T.prefeitura = function (o) {
    o = o || {};
    var en = window.EP && EP.en;
    return modelo(o, "cena-predio", "predio3d prefeitura3d", predioMiolo(o, {
      placa: en ? "CITY HALL" : "PREFEITURA",
      mais: emoji("🌳", -150, 20, 70, 58) + emoji("🚌", 104, 44, 92, 44)
    }));
  };

  // ---------------------------------------------------------------- palácio (Planalto) e tribunal (STF)
  function palacioMiolo(o) {
    var cols = "";
    for (var k = 0; k < 9; k++) cols += '<span class="coluna" style="left:' + (-152 + k * 37) + 'px"></span>';
    return (o.mundo ? "" : '<div class="sombra-chao"></div>') + caixa("laje l1") + caixa("vidro") + caixa("laje l2") + cols;
  }
  T.palacio = function (o) { return modelo(o, "cena-predio", "predio3d palacio3d", palacioMiolo(o || {})); };
  T.tribunal = function (o) {
    o = o || {};
    return modelo(o, "cena-predio", "predio3d palacio3d tribunal3d", palacioMiolo(o) + emoji("⚖️", -52, -170, 20, 96));
  };

  // ---------------------------------------------------------------- torre dos cargos
  T.torreCargos = function (o) {
    o = o || {};
    var gente = ["🧑‍💼", "👩‍💼", "👨‍💼", "👩‍💼", "🧑‍💼", "👨‍💼", "👩‍💼", "🧑‍💼", "👨‍💼", "🧑‍💼", "👩‍💼", "👨‍💼"];
    var janelas = gente.map(function (g) { return "<span>" + g + "</span>"; }).join("");
    return modelo(o, "cena-predio", "torre3d", caixa("bloco", { fr: janelas, ld: "" }) + caixa("antena") + emoji("👔", -26, -300, 0, 52));
  };

  // ---------------------------------------------------------------- palanque (participação)
  T.palanque = function (o) {
    o = o || {};
    var en = window.EP && EP.en;
    return modelo(o, "cena-predio", "palanque3d", caixa("palco", { fr: "<span>" + (en ? "YOUR VOICE" : "SUA VOZ") + "</span>" }) + caixa("degrau") +
      emoji("📣", -40, -150, 0, 84) + emoji("🙋", -120, -6, 120, 50) + emoji("🙋‍♀️", -60, -2, 130, 50) + emoji("🧑‍🦯", 10, -6, 120, 50) + emoji("👵", 70, -2, 128, 50));
  };

  // ---------------------------------------------------------------- urna sobre uma mesa (mapa)
  T.urnaMesa = function (o) {
    var urna = "";
    if (T.urna) {
      var tmp = document.createElement("div");
      tmp.innerHTML = T.urna({ peq: true });
      var u = tmp.querySelector(".urna3d");
      urna = u ? u.outerHTML : "";
    }
    return '<div class="ancora3d no-mundo urna-mesa3d">' + caixa("mesa") + '<div class="urna-pe">' + urna + "</div>" + emoji("🧓", 120, -40, 40, 60) + "</div>";
  };

  // ---------------------------------------------------------------- cubo com emoji (substitui o "selo" plano)
  T.cuboEmoji = function (e) {
    return cena("cena-cubo-emoji", T.cubo ? T.cubo(e, e, "lento", 150) : '<div class="selo-emoji">' + e + "</div>");
  };
  T.seloEmoji = function (e) { return T.cuboEmoji(e || "✨"); };

  // ---------------------------------------------------------------- escada (passos de um processo)
  T.escada = function (passos) {
    var n = passos.length, w = 112, html = "";
    passos.forEach(function (p, k) {
      var h = 36 + k * 26, x = k * w - (n * w) / 2;
      html += caixa("degrau-e", { fr: '<span class="d-ic">' + (p.ic || "•") + '</span><span class="d-num">' + (k + 1) + "</span>" },
        "--h:" + h + "px;transform:translate3d(" + x + "px," + -h + "px,0)") ;
    });
    return '<div class="cena3d cena-escada" aria-hidden="true"><div class="ancora3d escada3d" style="--n:' + n + '">' + html +
      '<span class="ficha" style="--fx:' + (-(n * w) / 2 + w / 2 - 22) + "px;--fy:-90px\">📄</span></div></div>";
  };

  // ilustração pelo nome (usada pelos slides)
  T.ilustracao = function (id, e) {
    switch (id) {
      case "congresso": return T.congresso({ rotulos: true });
      case "tres-poderes": return T.tresPoderes();
      case "niveis": return T.niveis({ entra: true });
      case "urna": return T.urna ? T.urna({ auto: true, tela: window.EP && EP.en ? "YOUR VOTE" : "SEU VOTO" }) : T.cuboEmoji("🗳️");
      case "constituicao": return T.livro();
      case "balanca": return T.balanca();
      case "lei": return T.lei();
      case "cofre": return T.cofre();
      case "plenario": return T.plenario({ cheio: false });
      case "megafone": return T.megafone();
      case "predio": return T.predio();
      case "palacio": return T.palacio();
      case "escola": return T.escola();
      case "tribunal": return T.tribunal();
      case "cargos": return T.torreCargos();
      case "palanque": return T.palanque();
      case "mapa": return T.cuboEmoji("🗺️");
      default: return T.cuboEmoji(e || "✨");
    }
  };
})();
