/* Perfil de uma pessoa: ficha, propostas, votações, gastos e fontes (em português ou inglês). */
(function () {
  "use strict";
  var EP = window.EP, D = EP.trd;
  var esc = EP.esc;
  var raiz = document.getElementById("perfil");
  var id = (EP.param("id") || "").trim();
  var CF = { veiculo: "Planalto", titulo: "Constituição Federal de 1988", url: "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm", data: "1988-10-05" };

  // o que faz cada cargo [pt, en]
  var OQUE = {
    dep: ["Deputados federais fazem leis para o país todo, votam o orçamento e fiscalizam o governo federal. Cada estado elege um número de deputados de acordo com a sua população.",
      "Federal deputies make laws for the whole country, vote on the federal budget and oversee the federal government. Each state elects a number of deputies according to its population."],
    sen: ["Senadores representam o seu estado. Eles fazem e revisam leis, aprovam algumas autoridades (como ministros do Supremo) e fiscalizam o governo federal.",
      "Senators represent their state. They make and review laws, approve some authorities (such as Supreme Court justices) and oversee the federal government."],
    pres: ["O presidente governa o país: comanda os ministérios, propõe leis e medidas provisórias, sanciona ou veta as leis aprovadas pelo Congresso e representa o Brasil no exterior.",
      "The President governs the country: leads the ministries, proposes laws and provisional measures, signs or vetoes the laws passed by Congress and represents Brazil abroad."],
    vp: ["O vice-presidente substitui o presidente quando ele viaja ou fica impedido, e assume o cargo se o presidente sair de vez.",
      "The Vice President stands in for the President during trips or when the President cannot serve, and takes over if the President leaves office for good."],
    gov: ["O governador comanda o estado: cuida da polícia, das escolas de ensino médio, dos hospitais estaduais e das estradas estaduais, entre outras coisas.",
      "The governor runs the state: the state police, high schools, state hospitals and state roads, among other things."],
    vgov: ["O vice-governador substitui o governador quando ele viaja ou fica impedido, e assume o cargo se o governador sair de vez.",
      "The vice governor stands in for the governor during trips or when the governor cannot serve, and takes over if the governor leaves office for good."],
    dest: ["Deputados estaduais fazem as leis do estado, votam o orçamento do estado e fiscalizam o governador.",
      "State deputies (Brazil's state legislators) make the state's laws, vote on the state budget and oversee the governor."],
    dist: ["Deputados distritais fazem as leis do Distrito Federal, votam o orçamento e fiscalizam o governador.",
      "District deputies make the laws of the Federal District, vote on its budget and oversee the governor."],
    pref: ["O prefeito comanda a cidade: cuida de creches e escolas, postos de saúde, coleta de lixo, ruas e ônibus da cidade, entre outras coisas.",
      "The mayor runs the city: daycare centers and schools, health clinics, garbage collection, streets and city buses, among other things."],
    vpref: ["O vice-prefeito substitui o prefeito quando ele viaja ou fica impedido, e assume o cargo se o prefeito sair de vez.",
      "The vice mayor stands in for the mayor during trips or when the mayor cannot serve, and takes over if the mayor leaves office for good."],
    ver: ["Vereadores fazem as leis da cidade, votam o orçamento da prefeitura e fiscalizam o prefeito.",
      "City councilors ({{vereadores}}) make the city's laws, vote on the city budget and oversee the mayor."],
    min: ["Ministros são escolhidos pelo presidente para cuidar de uma área do governo federal. Eles não são eleitos.",
      "Ministers are chosen by the President to take care of one area of the federal government. They are not elected."]
  };
  // "O que faz um deputado federal?" [masc, fem, en]
  var QUEM = {
    dep: ["um deputado federal", "uma deputada federal", "a federal deputy"], sen: ["um senador", "uma senadora", "a senator"],
    pres: ["o presidente da República", "a presidente da República", "the President"], vp: ["o vice-presidente", "a vice-presidente", "the Vice President"],
    gov: ["um governador", "uma governadora", "a governor"], vgov: ["um vice-governador", "uma vice-governadora", "a vice governor"],
    dest: ["um deputado estadual", "uma deputada estadual", "a state deputy"], dist: ["um deputado distrital", "uma deputada distrital", "a district deputy"],
    pref: ["um prefeito", "uma prefeita", "a mayor"], vpref: ["um vice-prefeito", "uma vice-prefeita", "a vice mayor"],
    ver: ["um vereador", "uma vereadora", "a city councilor"], min: ["um ministro", "uma ministra", "a minister"]
  };
  var COR_VOTO = { "Sim": "#1f3a5f", "Não": "#9a4f00", "Abstenção": "#5b6573", "Obstrução": "#6a3fb0", "Outro": "#6b5a33" };
  var P = null;

  // ---------------------------------------------------------------- pronomes
  function ele(p) { return EP.en ? (p.genero === "F" ? "she" : p.genero === "M" ? "he" : "they") : EP.gen(p.genero, "ele", "ela"); }
  function Ele(p) { var e = ele(p); return e.charAt(0).toUpperCase() + e.slice(1); }
  function dele(p) { return EP.en ? (p.genero === "F" ? "her" : p.genero === "M" ? "him" : "them") : EP.gen(p.genero, "ele", "ela"); }
  function tipoCargo(p) { return p.tipo === "dest" && p.uf === "DF" ? "dist" : p.tipo; }
  function novaAba() { return '<span class="sr"> ' + EP.tr("(abre em outra aba)", "(opens in a new tab)") + "</span>"; }
  function linkFora(url, txt, emPt) {
    return '<a href="' + esc(url) + '" target="_blank" rel="noopener"' + (EP.en && emPt ? ' hreflang="pt-BR"' : "") + ">" + txt + ' <span aria-hidden="true">↗</span>' + novaAba() + "</a>";
  }
  // botão "De onde veio isso?" com o assunto escondido para quem usa leitor de tela
  function fonteBtn(lista, rotulo, assunto) {
    var b = EP.botaoFontes(lista, rotulo);
    return b && assunto ? b.replace(/<\/button>$/, '<span class="sr"> (' + esc(assunto) + ")</span></button>") : b;
  }

  // ---------------------------------------------------------------- carregar
  function deEstado(e, quem, chave) {
    var p = e[chave];
    if (!p) throw new Error("sem " + chave);
    // infoCasa: a Assembleia do estado (o site oficial dela), para o quadro "Onde ver mais"
    return Object.assign({ id: id, tipo: quem, uf: e.uf, cargo: quem === "gov" ? EP.gen(p.genero, "Governador", "Governadora") : EP.gen(p.genero, "Vice-governador", "Vice-governadora"),
      infoCasa: (e.deputadosEstaduais || {}).infoCasa || null }, p);
  }
  function carregar() {
    if (/^(dep|sen|pres|vp)-[\w-]+$/.test(id)) return EP.json("dados/pessoas/" + id + ".json");
    return carregarBase().then(comExtras);
  }
  // Estaduais e municipais: a ficha vem da lista do estado ou da cidade (TSE ou lista oficial da Casa). Quando a Assembleia,
  // a Câmara Municipal ou o governo publicam mais dados (propostas, votações, gastos), eles entram por cima da ficha, com os
  // mesmos campos dos perfis federais. A ficha avisa onde estão, para a página não pedir arquivos que não existem:
  // "extras": true = dados/pessoas/<id>.json; "extras": "cidade" = dados/camaras/extras/<IBGE>.json (um arquivo por cidade,
  // com todos os vereadores e o prefeito dela).
  function comExtras(base) {
    if (!base || !base.extras) return base;
    var cid = /^(?:ver|pref|vpref)-(\d{7})/.exec(id);
    var porCidade = base.extras === "cidade" && cid;
    return EP.json(porCidade ? "dados/camaras/extras/" + cid[1] + ".json" : "dados/pessoas/" + id + ".json").then(function (x) {
      if (porCidade) x = ((x && x.pessoas) || {})[id];
      if (!x) return base;
      var p = Object.assign({}, base, x);
      p.id = base.id || id;
      p.tipo = base.tipo;
      ["uf", "municipio", "cargo", "avisoLista", "avisoLista_en"].forEach(function (k) { if (base[k] != null && x[k] == null) p[k] = base[k]; });
      if (base.executivo && x.executivo) p.executivo = juntaExecutivo(x.executivo, base.executivo);
      return p;
    }, function () { return base; });
  }
  // Leis e vetos de duas fontes oficiais: vale o que o sistema da Câmara (SAPL, no arquivo extra) contou; o que ele não
  // conseguiu contar com segurança vem da ficha (Diário Oficial ou página oficial de leis do município, que o montar.py só
  // põe ali quando falta no SAPL e as duas contas começam no mesmo dia). Cada número leva a explicação e a fonte de onde
  // veio ("notaLeis", "notaVetos"); sem as explicações separadas, fica só a conta do SAPL (nada de frase que contradiga
  // o número mostrado).
  function juntaExecutivo(a, b) {
    var leis = a.leisSancionadas == null && b.leisSancionadas != null, vetos = a.vetos == null && b.vetos != null;
    var deLeis = leis ? b : a, deVetos = vetos ? b : a;
    if (!(leis || vetos) || !deLeis.notaLeis || !deVetos.notaVetos) return a;
    var e = Object.assign({}, a);
    if (leis) {
      e.leisSancionadas = b.leisSancionadas;
      e.periodo = Object.assign({}, a.periodo || b.periodo, { ultimaLei: (b.periodo || {}).ultimaLei || null });
    }
    if (vetos) ["vetos", "vetosTotais", "vetosParciais"].forEach(function (k) { e[k] = b[k] != null ? b[k] : null; });
    e.fontes = [].concat(b.fontes || b.fonte || [], a.fontes || a.fonte || []);
    e.nota = deLeis.notaLeis + " " + deVetos.notaVetos;
    e.nota_en = deLeis.notaLeis_en && deVetos.notaVetos_en ? deLeis.notaLeis_en + " " + deVetos.notaVetos_en : null;
    return e;
  }
  function carregarBase() {
    var m;
    if ((m = /^(gov|vgov)-([A-Z]{2})$/.exec(id))) {
      return EP.json("dados/estados/" + m[2] + ".json").then(function (e) { return deEstado(e, m[1], m[1] === "gov" ? "governador" : "vice"); });
    }
    // o id de quem a Casa lista mas não foi ligado ao TSE é "dest-UF-x<nome-com-hifens>" (regional.id_pessoa)
    if ((m = /^dest-([A-Z]{2})-[\w-]+$/.exec(id))) {
      return EP.json("dados/estados/" + m[1] + ".json").then(function (e) {
        var de = e.deputadosEstaduais || {}, p = (de.membros || []).filter(function (x) { return x.id === id; })[0];
        if (!p) throw new Error("não achei");
        return Object.assign({ tipo: "dest", uf: e.uf, cargo: e.uf === "DF" ? EP.gen(p.genero, "Deputado distrital", "Deputada distrital") : EP.gen(p.genero, "Deputado estadual", "Deputada estadual"),
          avisoLista: de.aviso, avisoLista_en: de.aviso_en, fonte: p.fonte || de.fonte, infoCasa: de.infoCasa || null }, p);
      });
    }
    if ((m = /^(pref|vpref|ver)-(\d{7})(?:-[\w-]+)?$/.exec(id))) {
      var uf = EP.UF_IBGE[m[2].slice(0, 2)];
      return EP.json("dados/cidades/" + uf + "/" + m[2] + ".json").then(function (c) {
        var p, tipo = m[1];
        if (tipo === "pref") p = c.prefeito;
        else if (tipo === "vpref") p = c.vice;
        else p = ((c.vereadores || {}).membros || []).filter(function (x) { return x.id === id; })[0];
        if (!p) throw new Error("não achei");
        // prefeitos 2026: cargo vago, ou quem governa hoje não foi conferido (a página da cidade explica por quê)
        if (!p.nome && (tipo === "pref" || tipo === "vpref")) { var semNome = new Error("não achei"); semNome.cidade = { c: c, p: p, tipo: tipo, uf: uf }; throw semNome; }
        var cargo = tipo === "pref" ? EP.gen(p.genero, "Prefeito", "Prefeita") : tipo === "vpref" ? EP.gen(p.genero, "Vice-prefeito", "Vice-prefeita") : EP.gen(p.genero, "Vereador", "Vereadora");
        var v = c.vereadores || {};
        return Object.assign({ tipo: tipo, uf: uf, municipio: { ibge: c.ibge, nome: c.nome }, cargo: cargo,
          avisoLista: tipo === "ver" ? v.aviso : c.aviso, avisoLista_en: tipo === "ver" ? v.aviso_en : c.aviso_en,
          fonte: p.fonte || (tipo === "ver" ? v.fonte : null), onde: c.onde || null, infoCasa: v.infoCasa || null }, p);
      });
    }
    if (/^min-/.test(id)) {
      return EP.json("dados/manual/ministros.json").then(function (d) {
        var p = (d.ministerios || []).filter(function (x) { return x.id === id; })[0];
        if (!p) throw new Error("não achei");
        return EP.avisoMinistros(d).then(function (t) { return Object.assign({ tipo: "min", avisoLista: t, avisoLista_en: t }, p); });
      });
    }
    if (/^e26-/.test(id)) return EP.eleitos ? EP.eleitos.perfil(id) : Promise.reject(new Error("id inválido"));  // eleitos 2026 (até a posse): js/proximos.js
    if (/^stf-[a-z0-9-]+$/.test(id)) return EP.stf ? EP.stf.carregar(id) : Promise.reject(new Error("id inválido"));  // ministros do STF: js/stf.js
    return Promise.reject(new Error("id inválido"));
  }

  // ---------------------------------------------------------------- pedaços
  function nomeMinisterio(p) {
    var en = EP.en ? (p.ministerio_en || D.ministerio(p.ministerio)) : null;
    return en ? esc(en) : EP.pt(esc(p.ministerio || ""));
  }
  function cargoHtml(p) {
    if (p.tipo === "min") return esc(EP.tr(EP.gen(p.genero, "Ministro", "Ministra"), "Minister")) + " · " + nomeMinisterio(p);
    return esc(D.cargo(p.cargo || ""));
  }
  function cargoTexto(p) {
    if (p.tipo === "min") return EP.tr(EP.gen(p.genero, "Ministro", "Ministra"), "Minister") + " · " + ((EP.en && (p.ministerio_en || D.ministerio(p.ministerio))) || p.ministerio || "");
    return D.cargo(p.cargo || "");
  }
  function fato(ic, rot, val, fonte) {
    if (val == null || val === "") return "";
    return '<div class="fato"><span class="f-ic" aria-hidden="true">' + ic + '</span><span class="f-rot">' + esc(rot) + '</span><span class="f-val">' + val + "</span>" +
      (fonte ? fonteBtn(fonte, EP.tr("Fonte", "Source"), rot) : "") + "</div>";
  }
  function onde(p) {
    if (p.tipo === "pres" || p.tipo === "vp" || p.tipo === "min") return EP.tr("Brasil", "Brazil");
    if (p.municipio) return p.municipio.nome + " (" + p.uf + ")";
    return EP.UFS[p.uf] || p.uf || "";
  }
  function coletarFontes(obj) {
    var vistas = {}, lista = [];
    (function anda(v) {
      if (!v || typeof v !== "object") return;
      if (Array.isArray(v)) { v.forEach(anda); return; }
      if (v.url && (v.veiculo || v.titulo)) {
        if (!vistas[v.url]) { vistas[v.url] = 1; lista.push(v); }
        return;
      }
      Object.keys(v).forEach(function (k) { if (k !== "lista" && k !== "votos" && k.charAt(0) !== "_") anda(v[k]); });
    })(obj);
    return lista;
  }
  function mesmaPessoa(a, b) {
    if (!a || !b) return false;
    return EP.norm(a.nomeCivil || a.nome) === EP.norm(b.nomeCivil || b.nome) || EP.norm(a.nome) === EP.norm(b.nome);
  }
  // a ficha de quem foi eleito para o cargo vem com o ano da eleição na chave ("eleito2022", "eleito2026", "eleito2024"...)
  function eleitoNoCargo(p) {
    var ano = null;
    Object.keys(p || {}).forEach(function (k) { var m = /^eleito(\d{4})$/.exec(k); if (m && p[k] && (!ano || +m[1] > ano)) ano = +m[1]; });
    return ano ? { ano: ano, e: p["eleito" + ano] } : null;
  }
  function situacaoNaEleicao(p) {
    var ano = null;
    Object.keys(p || {}).forEach(function (k) { var m = /^situacao(\d{4})$/.exec(k); if (m && p[k] && (!ano || +m[1] > ano)) ano = +m[1]; });
    return ano ? { ano: ano, txt: p["situacao" + ano], en: p["situacao" + ano + "_en"] } : null;
  }
  // eleição que levou a pessoa ao cargo, no formato comum: { ano, votos, situacao, situacao_en, cargo, chapa, fonte }
  function eleicaoDe(p) {
    if (p.eleicao) return { ano: p.eleicao.ano, votos: p.eleicao.votos, situacao: p.eleicao.situacao, situacao_en: p.eleicao.situacao_en, cargo: p.eleicao.cargo, fonte: p.eleicao.fonte || p.eleicao.fontes };
    var el = eleitoNoCargo(p), e = el && el.e;
    if (e && mesmaPessoa(e, p)) return { ano: el.ano, votos: e.votos, situacao: e.situacao, situacao_en: e.situacao_en, chapa: e.votosDaChapa, fonte: e.fontes || e.fonte };
    var sit = situacaoNaEleicao(p);
    if (p.votos != null || p.situacao || sit) {
      return { ano: sit ? sit.ano : p.tipo === "dest" ? 2022 : /^(pref|vpref|ver)$/.test(p.tipo) ? 2024 : null, votos: p.votos, situacao: p.situacao || (sit && sit.txt),
        situacao_en: p.situacao_en || (sit && sit.en), chapa: p.votosDaChapa, fonte: null };
    }
    return null;
  }

  // ---------------------------------------------------------------- topo e ficha
  function topoHtml(p) {
    var m = p.mandato || {};
    var anos = m.inicio ? m.inicio.slice(0, 4) + EP.tr(" a ", " to ") + (m.fim || "").slice(0, 4) : "";
    // começa e acaba no mesmo ano (ex.: suplente que assumiu por uns meses): mostra as datas inteiras
    if (m.inicio && m.fim && m.inicio.slice(0, 4) === m.fim.slice(0, 4)) anos = EP.data(m.inicio) + EP.tr(" a ", " to ") + EP.data(m.fim);
    // perfil-mandato-r10: com o seletor de mandato, o período fica nele (e o chip some); num mandato antigo, o chip diz o período
    var sel = seletorHtml(), md = p._md;
    if (sel) anos = "";
    var chips = [];
    if (p.tipo === "min") { /* ministro não tem partido obrigatório: aparece na ficha */ }
    if (p.partido) chips.push('<span class="chip"><span aria-hidden="true">🎗️ </span><span class="sr">' + (md ? EP.tr("Partido na época: ", "Party at the time: ") : EP.tr("Partido: ", "Party: ")) + "</span>" +
      (/^sem partido$/i.test(p.partido) ? esc(EP.tr("Sem partido", "No party")) : EP.pt(esc(p.partido))) + "</span>");
    if (anos) chips.push('<span class="chip neutro"><span aria-hidden="true">📅 </span>' + EP.tr("Mandato: ", "Term: ") + esc(anos) + "</span>");
    if (md && md.como === "suplente") chips.push('<span class="chip amarelo"><span aria-hidden="true">🔑 </span>' + EP.tr("Suplente que assumiu", "Alternate who took office") + "</span>");
    if (p.eleicao2026) chips.push(EP.chip2026(p.eleicao2026, p.genero, true));
    if (m.obs) chips.push('<span class="chip amarelo"><span aria-hidden="true">ℹ️ </span>' + D.obs(m.obs, m.obs_en) + "</span>");
    if (p.interino) chips.push('<span class="chip amarelo">' + EP.tr(EP.gen(p.genero, "Interino", "Interina"), "Acting") + "</span>");
    // suplente que assumiu a vaga (listas oficiais das Assembleias e Câmaras Municipais)
    if (p.exercicio) chips.push('<span class="chip amarelo"><span aria-hidden="true">🔑 </span>' + esc(EP.tr(p.exercicio, p.exercicio_en || p.exercicio)) + "</span>");
    // dados que vêm do site oficial da Assembleia ou da Câmara Municipal: a data da última leitura completa (infoCasa.conferido)
    var conf = (p.infoCasa || {}).conferido, dias = conf ? EP.diasDesde(conf) : null;
    if (dias != null && (p.tipo === "dest" || p.tipo === "ver" || ((p.tipo === "gov" || p.tipo === "pref") && p.extras))) {
      var daCasa = p.tipo === "dest" || p.tipo === "gov" ? (p.uf === "DF" ? EP.tr("da Câmara Legislativa", "from the Legislative Chamber") : EP.tr("da Assembleia", "from the state legislature")) :
        EP.tr("da Câmara Municipal", "from the city council");
      chips.push('<span class="chip ' + (dias > 8 ? "amarelo" : "neutro") + '"><span aria-hidden="true">' + (dias > 8 ? "⚠️ " : "🔄 ") + "</span>" +
        EP.tr("Dados " + daCasa + " atualizados em ", "Data " + daCasa + " updated on ") + esc(EP.data(conf)) +
        (dias > 8 ? EP.tr(" (podem ter mudado desde então)", " (they may have changed since then)") : "") + "</span>");
    }
    return '<section class="perfil-topo" aria-labelledby="nome-pessoa"><div class="moldura">' + EP.av(p.foto, p.nome, null, true) + "</div><div>" +
      '<span class="cargo-p">' + cargoHtml(p) + (onde(p) ? " · " + esc(onde(p)) : "") + '</span><h1 id="nome-pessoa">' + EP.pt(esc(p.nome)) + "</h1>" +
      (p.nomeCivil && EP.norm(p.nomeCivil) !== EP.norm(p.nome) ? '<p class="muted" style="margin:-4px 0 8px">' + EP.tr("Nome completo: ", "Full name: ") + EP.pt(esc(p.nomeCivil)) + "</p>" : "") +
      (chips.length ? '<div class="chips">' + chips.join("") + "</div>" : "") + sel +
      (p.fotoCredito ? '<p class="muted credito">' + EP.tr("Foto: ", "Photo: ") + (/licença/.test(p.fotoCredito) ? esc(EP.en ? p.fotoCredito.replace("licença", "license") : p.fotoCredito) : EP.pt(esc(p.fotoCredito))) + "</p>" : "") + "</div></section>";
  }
  // site-d-r14 (protótipo D): os números grandes embaixo do nome; cada um leva à aba dele. Os mesmos para todo tipo de perfil
  // (o que existe para aquele cargo e aquele mandato); o número e o texto ficam escritos, o ícone é enfeite
  function numerosHtml(p) {
    if (!EP.d) return "";
    var k = [], pr = p.propostas && p.propostas.lista ? p.propostas.lista : null, md = p._md;
    if (pr) {
      k.push({ ic: "📝", n: EP.num(pr.length), t: EP.tr(pr.length === 1 ? "proposta" : "propostas", pr.length === 1 ? "proposal" : "proposals") + (md ? EP.tr(" neste mandato", " in this term") : ""), href: "#propostas" });
      var lei = pr.filter(function (x) { return x.status === "lei"; }).length;
      k.push({ ic: "📜", n: EP.num(lei), t: EP.tr(lei === 1 ? "virou lei" : "viraram lei", "became law"), href: "#propostas" });
    }
    var e = p.executivo;
    if (e && e.leisSancionadas != null) k.push({ ic: "✍️", n: EP.num(e.leisSancionadas), t: EP.tr("leis sancionadas", "laws signed"), href: "#leis" });
    if (e && e.vetos != null) k.push({ ic: "✋", n: EP.num(e.vetos), t: EP.tr(e.vetos === 1 ? "veto" : "vetos", e.vetos === 1 ? "veto" : "vetoes"), href: "#leis" });
    var v = p.votacoes, nv = v ? ((v.resumo || {}).total || (v.lista || []).length || (v.votos || []).length) : 0;
    if (nv && !v._fr) k.push({ ic: "🗳️", n: EP.num(nv), t: EP.tr(nv === 1 ? "votação" : "votações", nv === 1 ? "vote" : "votes"), href: "#votacoes" });
    if (p.gastos && p.gastos.total != null) k.push({ ic: "💸", n: EP.dinheiroCurto(p.gastos.total), t: EP.tr("gastos em ", "spent in ") + p.gastos.ano, href: "#gastos" });
    var el = eleicaoDe(p);
    if (md && md.it && md.it.k === "c" && md.it.v != null) k.push({ ic: "🗳️", n: EP.num(md.it.v), t: EP.tr("votos na eleição de " + md.it.a, "votes in the " + md.it.a + " election"), href: "#sobre" });
    else if (!md && el && el.votos != null) k.push({ ic: "🗳️", n: EP.num(el.votos), t: EP.tr("votos", "votes") + (el.ano ? EP.tr(" na eleição de " + el.ano, " in the " + el.ano + " election") : ""), href: "#sobre" });
    var idade = EP.idade(p.nascimento);
    if (md && p.nascimento && /^\d{4}-\d{2}-\d{2}$/.test(md.i || "")) {
      var a = +md.i.slice(0, 4) - +p.nascimento.slice(0, 4) - (md.i.slice(5) < p.nascimento.slice(5, 10) ? 1 : 0);
      if (a > 0 && a < 120) k.push({ ic: "🎂", n: a, t: EP.tr("anos no começo do mandato", "years old at the start of the term"), href: "#sobre" });
    } else if (!md && idade != null) k.push({ ic: "🎂", n: idade, t: EP.tr("anos de idade", "years old"), href: "#sobre" });
    if (!k.length) return "";
    return '<div class="d-numeros-perfil">' + EP.d.kpis(k.slice(0, 6), EP.tr("Números de ", "Numbers for ") + p.nome) + "</div>";
  }
  function fatosHtml(p) {
    var idade = EP.idade(p.nascimento);
    var el = eleicaoDe(p);
    var votoHtml = null;
    if (el && (el.votos != null || el.situacao)) {
      votoHtml = (el.votos != null ? EP.num(el.votos) + " " + EP.tr(el.votos === 1 ? "voto" : "votos", el.votos === 1 ? "vote" : "votes") +
        (el.chapa ? " " + EP.tr("(da chapa)", "(for the ticket)") : "") : "") +
        (el.situacao ? (el.votos != null ? "<br><small>" : "") + D.situacao(el.situacao, el.situacao_en) + (el.votos != null ? "</small>" : "") : "") +
        (el.cargo && /suplente/i.test(el.cargo) ? "<br><small>" + EP.tr("Concorreu como ", "Ran as ") + esc(D.cargo(el.cargo).toLowerCase()) + "</small>" : "");
    }
    var noCargo = eleitoNoCargo(p);
    var outroEleito = noCargo && noCargo.e && !mesmaPessoa(noCargo.e, p) ? noCargo.e : null;
    var oc = p.ocupacao;
    // site-d-r14: "Quem é" em blocos. À vista, o que é do cargo (a eleição, desde quando, como chegou, a idade, onde nasceu);
    // o que a pessoa declarou ao TSE (escolaridade, ocupação, bens) fica em "Mais sobre ele/ela"
    var h = fato("🗳️", el && el.ano ? EP.tr("Na eleição de " + el.ano, "In the " + el.ano + " election") : EP.tr("Na eleição", "In the election"), votoHtml, el && el.fonte) +
      (outroEleito ? fato("🗳️", EP.tr("Eleito(a) para este cargo em " + noCargo.ano, "Elected to this office in " + noCargo.ano),
        esc(outroEleito.nome) + (outroEleito.partido ? " (" + EP.pt(esc(outroEleito.partido)) + ")" : ""), outroEleito.fontes || outroEleito.fonte) : "") +
      (p.desde ? fato("📅", EP.tr("No cargo desde", "In office since"), EP.dataLonga(p.desde)) : "") +
      (p.comoAssumiu ? fato("🔑", EP.tr("Como chegou ao cargo", "How they took office"), D.traduz(p.comoAssumiu, null, p.comoAssumiu_en)) : "") +
      fato("🎂", EP.tr("Idade", "Age"), idade != null ? EP.tr(idade + " anos", idade + " years old") + (p.nascimento ? "<br><small>" + EP.tr("nasceu em ", "born on ") + EP.dataLonga(p.nascimento) + "</small>" : "") : null) +
      fato("📍", EP.tr("Nasceu em", "Born in"), p.naturalidade ? esc(p.naturalidade) : null) +
      (p.nota && p.tipo !== "min" ? fato("📝", EP.tr("Observação", "Note"), D.traduz(p.nota, null, p.nota_en)) : "");
    var mais = fato("🎓", EP.tr("Escolaridade (declarada ao TSE)", "Education (declared to the TSE)"), p.escolaridade ? D.escolaridade(p.escolaridade) : null, p.escolaridadeFonte) +
      fato("💼", oc && oc.ano ? EP.tr("Ocupação declarada ao TSE (" + oc.ano + ")", "Occupation declared to the TSE (" + oc.ano + ")") : EP.tr("Ocupação", "Occupation"),
        oc && oc.txt ? D.profissao(oc.txt) : null, oc && oc.fonte) +
      fato("🏠", EP.tr("Bens declarados à Justiça Eleitoral", "Assets declared to the electoral courts"), p.bens && p.bens.total != null ? EP.dinheiroCurto(p.bens.total) +
        (p.bens.ano ? " <small>(" + EP.tr("em ", "in ") + esc(p.bens.ano) + ")</small>" : "") +
        '<br><small class="nota-bens">' + EP.tr("Valor que a própria pessoa declarou ao se candidatar. É uma lista de bens: não mostra dívidas nem renda. Valores de anos diferentes não dão para comparar.",
          "Amount the person declared when running for office. It is a list of assets: it does not show debts or income. Amounts from different years cannot be compared.") + "</small>" : null, p.bens && p.bens.fonte);
    if (!h) { h = mais; mais = ""; }
    return (h ? '<div class="fatos">' + h + "</div>" : "") + (mais && EP.d ? EP.d.saiba('<div class="fatos">' + mais + "</div>", EP.tr("Mais sobre " + EP.gen(p.genero, "ele", "ela"), "More about " + dele(p)), "d-mais-sobre") :
      mais ? '<div class="fatos">' + mais + "</div>" : "");
  }
  function anterioresHtml(p) {
    var l = (p.mandatosAnteriores || []).filter(function (m) { return m && m.cargo; });
    if (!l.length) return "";
    var obs = null;
    var chips = l.map(function (m) {
      var per = m.periodo ? D.periodo(m.periodo) : [(m.inicio || "").slice(0, 4), (m.fim || "").slice(0, 4)].filter(Boolean).join("–");
      if (m.obs && !obs) obs = m;
      return '<li class="chip neutro">' + esc(D.cargo(m.cargo)) + (per ? " (" + per + ")" : "") + (m.obs ? '<span aria-hidden="true">*</span>' : "") + "</li>";
    });
    return '<div class="anteriores"><b id="t-anteriores">' + EP.tr("Mandatos anteriores no mesmo cargo:", "Previous terms in the same office:") + '</b><ul class="comissoes" aria-labelledby="t-anteriores">' + chips.join("") + "</ul>" +
      (obs ? '<p class="muted" style="font-size:.8rem;margin:0;width:100%"><span aria-hidden="true">* </span>' + D.obs(obs.obs, obs.obs_en) + "</p>" : "") + "</div>";
  }
  function contatosHtml(p) {
    var l = p.links || {};
    var itens = [];
    if (l.oficial) itens.push(linkFora(l.oficial, '<span aria-hidden="true">🏛️ </span>' + EP.tr("Página oficial", "Official page"), true));
    if (l.email) itens.push('<a href="mailto:' + esc(l.email) + '"><span aria-hidden="true">✉️ </span><span class="sr">' + EP.tr("E-mail: ", "Email: ") + "</span>" + esc(l.email) + "</a>");
    (l.redes || []).forEach(function (u) {
      var host = "";
      try { host = new URL(u).hostname.replace(/^(www\.|m\.)/, ""); } catch (e) { return; }
      itens.push(linkFora(u, '<span class="sr">' + EP.tr("Rede social: ", "Social media: ") + "</span>" + esc(host), false));
    });
    if (!itens.length) return "";
    return '<div class="contatos"><b id="t-contatos">' + EP.tr("Contato e links:", "Contact and links:") + "</b>" + itens.join("") + "</div>";
  }
  function oqueFazHtml(p) {
    var t = tipoCargo(p), o = OQUE[t], q = QUEM[t];
    if (!o || !q) return "";
    var pergunta = EP.en ? "What does " + q[2] + " do?" : "O que faz " + (p.genero === "F" ? q[1] : q[0]) + "?";
    // site-d-r14: a explicação do cargo fica no "💡 Saber mais" (a pergunta é o título)
    if (EP.d) return EP.d.saiba('<p>' + EP.md(EP.tr(o[0], o[1])) + "</p><p>" + '<a class="link-seta" href="entenda.html#parte-4">' + EP.tr("Entenda os cargos", "Learn about each office") +
      ' <span aria-hidden="true">›</span></a> ' + fonteBtn([CF], EP.tr("Fonte", "Source"), EP.tr("o que faz o cargo", "what the office does")) + "</p>", pergunta, "oque-faz");
    return '<div class="dica-coruja oque-faz"><span class="coruja" aria-hidden="true">🦉</span><div><p style="margin:0"><b>' + esc(pergunta) + "</b></p><p style=\"margin:4px 0 6px\">" + EP.md(EP.tr(o[0], o[1])) + "</p>" +
      '<a class="link-seta" href="entenda.html#parte-4">' + EP.tr("Entenda os cargos", "Learn about each office") + ' <span aria-hidden="true">›</span></a> ' + fonteBtn([CF], EP.tr("Fonte", "Source"), EP.tr("o que faz o cargo", "what the office does")) + "</div></div>";
  }

  // ---------------------------------------------------------------- propostas
  // ui-r9: as listas do perfil começam com um resumo (6 propostas; 8 votações no computador e 6 no celular) e "Mostrar mais"
  // traz mais 20 propostas ou 15 votações de cada vez (com as abas, cada parte cabe em poucas telas)
  var CELULAR = !!(window.matchMedia && matchMedia("(max-width: 600px)").matches);
  var INI_PROP = 6, INI_VOTOS = CELULAR ? 6 : 8;
  var filtro = { papel: "autor", status: "", tema: "", q: "" }, mostrando = INI_PROP;
  function contaPor(lista) {
    var c = { total: lista.length };
    Object.keys(EP.STATUS).forEach(function (s) { c[s] = 0; });
    lista.forEach(function (x) { var s = EP.STATUS[x.status] ? x.status : "outra"; c[s] = (c[s] || 0) + 1; });
    return c;
  }
  function daPapel(lista, papel) { return papel === "todas" ? lista : lista.filter(function (x) { return (x.papel || "coautor") === papel; }); }
  function escopoHtml(p, pr) {
    // deputados e senadores: todas as propostas dos mandatos naquela Casa; diz de quando é a mais antiga. Filtradas por
    // mandato (perfil-mandato-r10, pr._md): diz de qual mandato são
    var anoMin = (pr.lista || []).reduce(function (m, x) { var a = (x.data || "").slice(0, 4); return a && (!m || a < m) ? a : m; }, null);
    var extra = pr._md ? EP.tr(" no mandato de " + EP.trajetoria.periodo(pr._md), " in the " + EP.trajetoria.periodo(pr._md) + " term") :
      (p.tipo === "dep" || p.tipo === "sen") && anoMin ?
      EP.tr(", em todos os mandatos (a mais antiga é de " + anoMin + ")", ", in all terms (the oldest is from " + anoMin + ")") : "";
    if (!EP.en) return esc((pr.escopo || "") + extra);
    if (pr.escopo_en) return esc(pr.escopo_en + extra);
    var t = {
      dep: "Bills and other proposals filed as a federal deputy", sen: "Bills and other proposals filed as a senator",
      pres: "Proposals sent by the President to Congress in the current term (since January 1, 2023)",
      vp: "The Vice President does not file bills: proposals are sent to Congress on behalf of the executive branch by the President. When the Vice President stands in for the President (during trips, for example), what they sign counts as an act of the Presidency.",
      dest: "Bills filed as a state deputy", ver: "Bills filed as a city councilor"
    }[p.tipo];
    return t ? esc(t + extra) : D.ptHtml(pr.escopo);
  }
  // perfil-mandato-r10: "outros documentos" e "assinaturas só de apoio" vêm somados de todos os mandatos na Casa; quando a
  // lista de cima é de um mandato só, a frase diz isso
  function somaTxt(p) {
    return p.tipo === "sen" ? ["somando todos os mandatos no Senado", "adding up all terms in the Senate"] : ["somando todos os mandatos na Câmara", "adding up all terms in the Chamber"];
  }
  function outrosHtml(p, o, soma) {
    if (!o || !o.total) return "";
    var oque = EP.en ? (o.txt_en || {
      dep: "other documents (requests for information, motions, suggestions to the government and others)",
      sen: "other documents (motions, suggestions, official letters and other requests; these are not bills)",
      pres: "other documents sent to Congress (messages such as nominations of authorities and agreements with other countries, radio and TV license renewals and others)"
    }[p.tipo]) : null;
    var txt = EP.en ? (oque ? esc(oque) : D.ptHtml(o.txt || "")) : esc((o.txt || "outros documentos").toLowerCase());
    return '<p class="aviso azul"><span aria-hidden="true">📨 </span>' + EP.tr("Além disso, " + (soma ? somaTxt(p)[0] + ", " : "") + ele(p) + " apresentou",
      "Besides that, " + (soma ? somaTxt(p)[1] + ", " : "") + ele(p) + " filed") + " <b>" + EP.num(o.total) + "</b> " + txt + "." +
      (o.url ? " " + linkFora(o.url, EP.tr("Ver a lista oficial", "See the official list"), true) : "") + "</p>";
  }
  // mandato antigo: só onde ver os outros documentos daquele período (a contagem do site soma todos os mandatos)
  function outrosAntigoHtml(p, pr) {
    if (!pr.outrosUrl) return "";
    return '<p class="aviso azul"><span aria-hidden="true">📨 </span>' + EP.tr("Os outros documentos (como requerimentos e pedidos de informação) estão na lista oficial.",
      "The other documents (such as motions and requests for information) are in the official list.") + " " + linkFora(pr.outrosUrl, EP.tr("Ver a lista oficial", "See the official list"), true) + "</p>";
  }
  function apoiosHtml(p, a, soma) {
    if (!a || !a.total) return "";
    var resto;
    if (EP.en) {
      var n = (/(\d+) assinaturas/.exec(a.txt || "") || [])[1] || "171";
      resto = a.txt_en ? esc(a.txt_en) : esc(Ele(p) + " signed so that someone else's proposal could be filed (a constitutional amendment, PEC, needs " + n + " signatures). Supporting only does not make " + dele(p) + " an author or a co-author.");
    } else {
      var t = String(a.txt || "").replace(/^Assinaturas só de apoio:\s*/i, "");
      resto = esc(t.charAt(0).toUpperCase() + t.slice(1));
    }
    return '<p class="muted apoios" style="font-size:.86rem"><span aria-hidden="true">🖊️ </span>' + EP.tr("Assinaturas só de apoio", "Support-only signatures") +
      (soma ? " (" + EP.tr(somaTxt(p)[0], somaTxt(p)[1]) + ")" : "") + ": <b>" + EP.num(a.total) + "</b>. " + resto + "</p>";
  }
  function notaPresHtml(pr) {
    if (!pr.nota) return "";
    var en = pr.nota_en || (/^Medidas provisórias \(MPV\) já valem como lei/i.test(pr.nota) ?
      "Provisional measures (MPV) take effect as law as soon as the President publishes them, but they expire if Congress does not approve them within 120 days. The status of MPVs and PLNs (budget bills) is the one in the National Congress; for the other proposals it is the status in the Chamber of Deputies, where they start." : null);
    return '<p class="aviso"><span aria-hidden="true">ℹ️ </span>' + D.traduz(pr.nota, null, en) + "</p>";
  }
  function propostasHtml(p) {
    var pr = p.propostas;
    var lista = pr.lista || [];
    var nAutor = lista.filter(function (x) { return x.papel === "autor"; }).length, nCo = lista.length - nAutor;
    if (!nAutor && nCo) filtro.papel = "coautor";
    if (!lista.length || /^(pres|gov|pref)$/.test(p.tipo)) filtro.papel = "todas";
    leFiltros(lista);
    var h = '<section class="secao-perfil" id="propostas" aria-labelledby="t-propostas"><h2 id="t-propostas"><span class="ic" aria-hidden="true">📜</span>' +
      EP.tr("O que " + ele(p) + " propôs", "What " + ele(p) + " proposed") + "</h2>" +
      '<p class="muted">' + escopoHtml(p, pr) + " " + (pr.fonte ? fonteBtn(pr.fonte, null, EP.tr("propostas", "proposals")) : "") + "</p>" + notaPresHtml(pr);
    if (!lista.length) {
      if (p.tipo !== "vp") h += '<div class="vazio"><span class="grande" aria-hidden="true">📭</span>' + EP.tr("Não encontramos propostas apresentadas nesse período.", "We found no proposals filed in this period.") + "</div>";
    } else {
      var temPapel = !/^(pres|gov|pref)$/.test(p.tipo);  // o Executivo é sempre o autor das propostas que manda
      var nS = lista.filter(function (x) { return EP.en ? x.s_en : x.s; }).length;
      // ui-r9: a nota da IA fica na coluna da direita, em cima dos filtros (no celular, logo depois do funil)
      var notaIa = pr._semIa ? '<div class="nota-ia"><span aria-hidden="true">📄</span><p>' + EP.tr(
        "Neste mandato antigo, cada proposta aparece com o texto oficial (a ementa), do jeito que a Casa publicou, e o link para a página dela.",
        "For this past term, each bill appears with its official text (the ementa, in Portuguese), as the legislature published it, and a link to its page.") + "</p></div>" :
        '<div class="nota-ia"><span aria-hidden="true">🤖</span><p>' + EP.tr(
        'As explicações em palavras simples são escritas por <b>inteligência artificial</b> a partir do texto oficial (a ementa), com regras para não puxar para nenhum lado. Como a IA pode errar, o texto oficial aparece sempre embaixo, com o link. <a href="imparcialidade.html#ia">Saiba mais</a>.',
        'The plain-language explanations are written by <b>artificial intelligence</b> from the official summary of each bill (the ementa), following rules so as not to take sides. Since AI can make mistakes, the official text (in Portuguese) always appears below, with a link. <a href="imparcialidade.html#ia">Learn more</a>.') +
        " " + EP.tr("Até agora, <b>" + EP.num(nS) + " de " + EP.num(lista.length) + "</b> propostas desta pessoa têm explicação em palavras simples; as outras mostram só o texto oficial. Elas são preparadas aos poucos, no mesmo ritmo para todo mundo.",
          "So far, <b>" + EP.num(nS) + " of " + EP.num(lista.length) + "</b> of this person's proposals have a plain-language explanation; the others show only the official text. They are being prepared gradually, at the same pace for everyone.") + "</p></div>";
      h += '<div class="duas-p"><div>' +
        (temPapel ? '<div class="papeis" role="group" aria-label="' + EP.tr("Escolha o tipo de autoria", "Choose the type of authorship") + '">' +
          '<button type="button" class="papel-btn" data-papel="autor" aria-pressed="' + (filtro.papel === "autor") + '"><b>' + EP.num(nAutor) + '</b><span><span aria-hidden="true">✍️ </span>' +
          EP.tr(EP.gen(p.genero, "Autor principal", "Autora principal"), "Main author") + "</span><small>" +
          EP.tr(EP.gen(p.genero, "Ele", "Ela") + " escreveu e foi " + EP.gen(p.genero, "o primeiro", "a primeira") + " a assinar.", Ele(p) + " wrote it and was the first to sign.") + "</small></button>" +
          '<button type="button" class="papel-btn" data-papel="coautor" aria-pressed="' + (filtro.papel === "coautor") + '"><b>' + EP.num(nCo) + '</b><span><span aria-hidden="true">🤝 </span>' +
          EP.tr("Assinou junto", "Co-signed") + "</span><small>" + EP.tr("Outra pessoa escreveu; " + ele(p) + " assinou como " + EP.gen(p.genero, "coautor", "coautora") + ".",
            "Someone else wrote it; " + ele(p) + " signed as a co-author.") + "</small></button></div>" : "") +
        '<div class="funil" id="funil"></div>' +
        // site-d-r14: a barra colorida da situação (cada cor é um botão que filtra a lista) e as barras dos assuntos
        '<div class="status-chips d-status" id="status-chips" role="group" aria-label="' + EP.tr("Filtrar pela situação", "Filter by status") + '"></div></div>' +
        '<div><div class="temas-chips d-temas" id="temas-chips" role="group" aria-label="' + EP.tr("Filtrar pelo assunto", "Filter by topic") + '"></div></div></div>' +
        (EP.d ? EP.d.saiba('<p class="nota-contexto"><span aria-hidden="true">🦉 </span>' + EP.tr(
          'Quantidade não mede qualidade: um projeto pode ser bem simples ou muito grande. E o caminho até virar lei é longo, com muitas votações. <a href="entenda.html#parte-6">Veja como nasce uma lei</a>.',
          'Quantity does not measure quality: a bill can be very simple or very big. And the road to becoming law is long, with many votes. <a href="entenda.html#parte-6">See how a law is made</a>.') + "</p>" +
          '<p class="muted nota-contexto"><span aria-hidden="true">📜 </span>' + EP.tr('"Virou lei" inclui também decretos legislativos e resoluções, que são outras normas.',
            '"Became law" also includes legislative decrees and resolutions, which are other kinds of legal rules.') + "</p>" + notaIa,
          EP.tr("É só uma contagem: quantidade não mede qualidade", "It is just a count: quantity does not measure quality"), "d-saiba-prop") :
          '<p class="muted nota-contexto"><span aria-hidden="true">📜 </span>' + EP.tr('"Virou lei" inclui também decretos legislativos e resoluções, que são outras normas.',
            '"Became law" also includes legislative decrees and resolutions, which are other kinds of legal rules.') + "</p>" + notaIa) +
        '<label class="sr" for="busca-prop">' + EP.tr("Procurar nas propostas", "Search the proposals") + "</label>" +
        '<div class="busca busca-prop"><input type="search" id="busca-prop" placeholder="' + EP.tr("Procurar nas propostas (ex.: escola, saúde)", "Search the proposals (e.g. school, health)") + '" autocomplete="off" aria-controls="lista-prop"></div>' +
        '<p class="contagem" id="contagem-prop" aria-live="polite"></p><ol class="lista-prop" id="lista-prop"></ol><div class="mais-lista" id="mais-prop"></div>';
    }
    h += pr._antigo ? outrosAntigoHtml(p, pr) : apoiosHtml(p, pr.apoios, pr._md) + outrosHtml(p, pr.outros, pr._md);
    return h + "</section>";
  }
  function desenhaFunil() {
    var lista = daPapel(P.propostas.lista || [], filtro.papel), c = contaPor(lista);
    var aprov = c.aprovada + c.lei;
    var el = document.getElementById("funil");
    if (!el) return;
    el.classList.remove("anima");
    void el.offsetWidth;
    el.innerHTML =
      '<div class="funil-degrau d1"><span class="ic" aria-hidden="true">📝</span><span class="r">' + EP.tr(lista.length === 1 ? "proposta apresentada" : "propostas apresentadas", lista.length === 1 ? "proposal filed" : "proposals filed") +
      '</span><span class="q">' + EP.num(lista.length) + "</span></div>" +
      '<div class="funil-degrau d2"><span class="ic" aria-hidden="true">☑️</span><span class="r">' + EP.tr("aprovadas em pelo menos uma votação final", "approved in at least one final vote") + '</span><span class="q">' + EP.num(aprov) + "</span></div>" +
      '<div class="funil-degrau d3"><span class="ic" aria-hidden="true">📜</span><span class="r">' + EP.tr("viraram lei", "became law") + '</span><span class="q">' + EP.num(c.lei) + "</span></div>";
    if (!EP.reduzido) el.classList.add("anima");
  }
  function desenhaChips() {
    var lista = daPapel(P.propostas.lista || [], filtro.papel), c = contaPor(lista);
    var ordem = ["lei", "aprovada", "andando", "junta", "arquivada", "rejeitada", "parada", "retirada", "outra"];
    var tem = ordem.filter(function (s) { return c[s]; });
    // site-d-r14: a barra colorida (só desenho) e, embaixo, um botão por cor, com o número escrito, que filtra a lista
    document.getElementById("status-chips").innerHTML = (tem.length ? '<span class="d-status-barra" aria-hidden="true">' + tem.map(function (s) {
      return '<i class="gv-st-' + s + '" style="flex:' + c[s] + '"></i>';
    }).join("") + "</span>" : "") + '<span class="rot-filtro" aria-hidden="true">' + EP.tr("Toque numa cor para filtrar:", "Tap a color to filter:") + "</span>" + tem.map(function (s) {
      return '<button type="button" data-status="' + s + '" aria-pressed="' + (filtro.status === s) + '"><i class="d-st-q gv-st-' + s + '" aria-hidden="true"></i>' + EP.carimbo(s, EP.STATUS[s].curto) + '<span class="q">' + EP.num(c[s]) + "</span></button>";
    }).join("");
    var temas = {};
    lista.forEach(function (x) { (x.temas || []).forEach(function (t) { temas[t] = (temas[t] || 0) + 1; }); });
    var top = Object.keys(temas).sort(function (a, b) { return temas[b] - temas[a] || a.localeCompare(b); }).slice(0, 8);
    var max = top.length ? temas[top[0]] : 1;
    document.getElementById("temas-chips").innerHTML = top.length ? '<span class="rot-filtro d-h3" aria-hidden="true">' + EP.tr("Assuntos que mais aparecem (toque para filtrar):", "Most common topics (tap to filter):") + "</span>" + top.map(function (t) {
      return '<button type="button" class="d-tema" data-tema="' + esc(t) + '" aria-pressed="' + (filtro.tema === t) + '"><span class="d-tema-nome"><span aria-hidden="true">🏷️ </span>' + esc(EP.tema(t)) + "</span>" +
        '<b class="d-tema-n">' + EP.num(temas[t]) + '</b><span class="d-tema-trilho" aria-hidden="true"><i style="width:' + (100 * temas[t] / max).toFixed(1) + '%"></i></span></button>';
    }).join("") : "";
  }
  function propHtml(x, focavel) {
    var s = EP.STATUS[x.status] ? x.status : "outra";
    var ondeLink = /^senado:/.test(x.id || "") ? ["Ver no site do Senado", "See it on the Senate website"] :
      /^camara:/.test(x.id || "") ? ["Ver no site da Câmara", "See it on the Chamber of Deputies website"] :
      /^(dest|gov)$/.test(P.tipo) && P.uf === "DF" ? ["Ver no site da Câmara Legislativa", "See it on the Legislative Chamber website"] :
      /^(dest|gov)$/.test(P.tipo) ? ["Ver no site da Assembleia", "See it on the state legislature website"] :
      /^(ver|pref)$/.test(P.tipo) ? ["Ver no site da Câmara Municipal", "See it on the city council website"] :
      ["Ver no site oficial", "See it on the official website"];
    var simples = EP.en ? x.s_en : x.s;
    var ementa = EP.pt(esc(x.ementa || ""));
    var corpo = simples ?
      '<p class="simples"><span class="rot-texto">' + EP.tr("Em palavras simples (feita por IA)", "In plain words (written by AI)") + "</span>" + esc(simples) + "</p>" +
      '<div class="oficial"><span class="rot-texto">' + EP.tr("Texto oficial (ementa)", "Official text (ementa, in Portuguese)") + "</span>" + ementa + "</div>" :
      '<div class="oficial so-oficial"><span class="rot-texto">' + EP.tr("Texto oficial (ementa)", "Official text (ementa, in Portuguese)") + "</span>" + ementa + "</div>" +
      (P.propostas && P.propostas._semIa ? "" : '<p class="muted preparando"><span aria-hidden="true">⏳ </span>' + EP.tr("Explicação simples em preparo.", "Plain-language explanation in preparation.") + "</p>");
    return '<li class="prop s-' + s + '"><div class="prop-cab"><h3 class="sigla"' + (focavel ? ' tabindex="-1"' : "") + (EP.en ? ' lang="pt-BR"' : "") + ">" + esc(x.sigla || x.tipo || "") + "</h3>" +
      (x.data ? '<span class="data"><span class="sr">' + EP.tr("Apresentada em ", "Filed on ") + "</span>" + EP.data(x.data) + "</span>" : "") + EP.carimbo(s) +
      (P.tipo !== "pres" ? '<span class="papel' + (x.papel === "autor" ? "" : " coautor") + '">' + (x.papel === "autor" ? '<span aria-hidden="true">✍️ </span>' + EP.tr(EP.gen(P.genero, "Autor principal", "Autora principal"), "Main author") :
        '<span aria-hidden="true">🤝 </span>' + EP.tr("Assinou junto", "Co-signed")) + "</span>" : "") + "</div>" + corpo +
      '<div class="rodape-prop"><span class="status-txt">' + D.status(x) + "</span>" +
      ((x.temas || []).length ? '<span class="temas"><span aria-hidden="true">🏷️ </span><span class="sr">' + EP.tr("Assuntos: ", "Topics: ") + "</span>" + esc(x.temas.map(EP.tema).join(", ")) + "</span>" : "") +
      (x.url ? linkFora(x.url, (/\.pdf($|[?#])/i.test(x.url) ? EP.tr("Ver o documento oficial", "See the official document") : EP.tr(ondeLink[0], ondeLink[1])) +
        '<span class="sr"> (' + EP.pt(esc(x.sigla || "")) + ")</span>", true) : "") +
      (x.lei && x.lei.url ? linkFora(x.lei.url, EP.tr("Ler a ", "Read ") + EP.pt(esc(x.lei.nome || "lei")), true) : "") + "</div></li>";
  }
  function textoBusca(x) {
    var t = [x.s, x.ementa, x.sigla].concat(x.temas || []);
    if (EP.en) t = t.concat([x.s_en], (x.temas || []).map(EP.tema));
    return EP.norm(t.join(" "));
  }
  function filtradas() {
    var q = EP.norm(filtro.q);
    return daPapel(P.propostas.lista || [], filtro.papel).filter(function (x) {
      return (!filtro.status || (EP.STATUS[x.status] ? x.status : "outra") === filtro.status) && (!filtro.tema || (x.temas || []).indexOf(filtro.tema) > -1) &&
        (!q || textoBusca(x).indexOf(q) > -1);
    });
  }
  function desenhaLista(focarDe) {
    lembraProp();
    var l = filtradas(), vis = l.slice(0, mostrando);
    document.getElementById("lista-prop").innerHTML = vis.map(function (x, k) { return propHtml(x, focarDe != null && k === focarDe); }).join("") ||
      '<li class="vazio"><span class="grande" aria-hidden="true">🔍</span>' + EP.tr("Nenhuma proposta com esses filtros.", "No proposals with these filters.") + "</li>";
    var txt = EP.tr("Mostrando " + EP.num(vis.length) + " de " + EP.num(l.length) + (l.length === 1 ? " proposta" : " propostas") + ", da mais nova para a mais antiga.",
      "Showing " + EP.num(vis.length) + " of " + EP.num(l.length) + (l.length === 1 ? " proposal" : " proposals") + ", newest first.");
    var c = document.getElementById("contagem-prop");
    if (c.textContent !== txt) c.textContent = txt;
    var resta = l.length - vis.length;
    document.getElementById("mais-prop").innerHTML = resta > 0 ? '<button type="button" class="btn claro" id="ver-mais-prop">' +
      EP.tr("Mostrar mais " + Math.min(20, resta), "Show " + Math.min(20, resta) + " more") + ' <span aria-hidden="true">▾</span></button>' : "";
    if (focarDe != null) {
      var alvo = document.querySelectorAll("#lista-prop .sigla")[focarDe];
      if (alvo) alvo.focus();
    }
  }
  function redesenhaTudo() { desenhaFunil(); desenhaChips(); mostrando = INI_PROP; desenhaLista(); }

  // ---------------------------------------------------------------- memória (ui-r9): filtros, busca e "Mostrar mais" voltam como estavam
  // Os filtros ficam no endereço (?prop-status=lei&prop-q=escola&voto-tipo=principal: dá para compartilhar) e quantos
  // "Mostrar mais" estavam abertos fica na memória do histórico (EP.memo, js/comum.js). Voltando de uma votação ou de outra
  // página, a lista aparece igual.
  var LOTE_PROP = 20, LOTE_VOTOS = 15, nProp0 = null;
  function leFiltros(lista) {
    if (!EP.memo) return;
    var pa = EP.memo.url("prop-papel"), st = EP.memo.url("prop-status"), tm = EP.memo.url("prop-tema"), q = EP.memo.url("prop-q");
    if (/^(autor|coautor|todas)$/.test(pa || "") && filtro.papel !== "todas") filtro.papel = pa;
    if (st && EP.STATUS[st]) filtro.status = st;
    if (tm && lista.some(function (x) { return (x.temas || []).indexOf(tm) > -1; })) filtro.tema = tm;
    if (q) filtro.q = q;
    var n = EP.memo.le("prop-n");
    if (typeof n === "number" && n > INI_PROP) nProp0 = n;
    var v = EP.memo.url("voto-tipo");
    if (CAT_VOTO[v]) filtroV = v;
    var nv = EP.memo.le("voto-n");
    if (typeof nv === "number" && nv > INI_VOTOS) mostrandoV = nv;
  }
  function lembraProp() {
    if (!EP.memo || !P || !P.propostas) return;
    var padrao = (P.propostas.lista || []).some(function (x) { return x.papel === "autor"; }) ? "autor" : "coautor";
    EP.memo.poeUrl("prop-papel", filtro.papel === padrao || /^(pres|gov|pref)$/.test(P.tipo) ? "" : filtro.papel);
    EP.memo.poeUrl("prop-status", filtro.status);
    EP.memo.poeUrl("prop-tema", filtro.tema);
    EP.memo.poeUrl("prop-q", (filtro.q || "").trim());
    EP.memo.grava("prop-n", mostrando > INI_PROP ? mostrando : null);
  }
  function lembraVotos() {
    if (!EP.memo) return;
    EP.memo.poeUrl("voto-tipo", filtroV);
    EP.memo.grava("voto-n", mostrandoV > INI_VOTOS ? mostrandoV : null);
  }

  // ---------------------------------------------------------------- votações (formato antigo: lista; novo: votos + arquivo central)
  function escopoVotosHtml(p, v) {
    if (!EP.en) return esc(v.escopo || "");
    if (v.escopo_en) return esc(v.escopo_en);
    var t = {
      dep: "Roll-call votes (where each member's vote is recorded) in the full Chamber of Deputies since February 2023.",
      sen: "Open votes (with each senator's vote recorded) in the full Senate since February 2023. Secret votes, such as choosing authorities, are not included: in those, individual votes are not published."
    }[p.tipo];
    return t ? esc(t) : D.ptHtml(v.escopo);
  }
  function votacoesHtml(p) {
    var v = p.votacoes;
    var n = v ? (v.lista || []).length || (v.votos || []).length : 0;
    if (!n) return "";
    var r = v.resumo || {}, tot = r.total || n;
    var chaves = ["Sim", "Não", "Abstenção", "Obstrução", "Outro"].filter(function (k) { return r[k]; });
    return '<section class="secao-perfil" id="votacoes" aria-labelledby="t-votacoes"><h2 id="t-votacoes"><span class="ic" aria-hidden="true">🗳️</span>' + EP.tr("Como " + ele(p) + " votou", "How " + ele(p) + " voted") + "</h2>" +
      '<p class="muted">' + escopoVotosHtml(p, v) + " " + (v.fonte ? fonteBtn(v.fonte, null, EP.tr("votações", "votes")) : "") + "</p>" +
      // site-d-r14: uma coluna por tipo de voto (só desenho, com o número em cima); a legenda embaixo é o mesmo em texto
      (chaves.length ? '<div class="d-colunas" aria-hidden="true">' + chaves.map(function (k) {
        return '<span class="d-coluna" style="--c:' + COR_VOTO[k] + '"><b>' + EP.num(r[k]) + "</b><i style=\"height:" + Math.max(4, Math.round(100 * r[k] / tot)) + '%"></i><small>' + esc(D.nomeVoto(k)) + "</small></span>";
      }).join("") + "</div>" +
        '<ul class="legenda-votos">' + chaves.map(function (k) { return '<li><i style="background:' + COR_VOTO[k] + '" aria-hidden="true"></i>' + esc(D.nomeVoto(k)) + ": " + EP.num(r[k]) + "</li>"; }).join("") +
        "<li>" + EP.tr("Total: ", "Total: ") + EP.num(tot) + "</li></ul>" : "") +
      '<div class="dica-coruja nota-contexto" style="margin-top:12px"><span class="coruja" aria-hidden="true">🦉</span><p>' + EP.tr(
        'Votar "Sim" não é bom e votar "Não" não é ruim: depende do que estava sendo votado. Leia cada votação para entender.',
        'Voting "Yes" is not good and voting "No" is not bad: it depends on what was being voted on. Read each vote to understand it.') + "</p></div>" +
      (r.Outro || r["Obstrução"] ? (EP.d ? EP.d.saiba : function (x) { return x; })(
        (r.Outro ? '<p class="muted" style="font-size:.85rem;margin:0 0 6px">' + (p.tipo === "ver" ?
          EP.tr('"Outro" quer dizer: não votou, estava ausente (com ou sem justificativa), representava a Câmara fora dela ou presidia a sessão.',
            '"Other" means: did not vote, was absent (excused or not), was representing the City Council elsewhere or was presiding over the session.') :
          EP.tr('"Outro" quer dizer: estava ausente, de licença, em missão oficial ou presidindo a sessão.',
            '"Other" means: absent, on leave, on an official mission or presiding over the session.')) + "</p>" : "") +
        // "Obstrução" é um recurso das regras do Congresso: a explicação só aparece para quem tem votos assim
        (r["Obstrução"] ? "<p>" + EP.tr(
          '"Obstrução" é um recurso previsto nas regras da Casa: o líder anuncia que o partido está em obstrução, e os parlamentares dele deixam de contar para o número mínimo de presentes, para adiar ou evitar aquela votação.',
          '"Obstruction" is a tool allowed by the rules: the party leader announces it, and the party\'s members stop counting toward the minimum number of members present, in order to delay or prevent that vote.') + "</p>" : ""),
        EP.tr("O que quer dizer cada tipo de voto", "What each type of vote means")) : "") +
      (EP.en ? '<p class="muted" style="font-size:.85rem;margin:10px 0 0">The descriptions of each vote are official texts in Portuguese.</p>' : "") +
      '<div class="temas-chips" id="filtro-votos" role="group" aria-label="' + EP.tr("Filtrar as votações pelo tipo", "Filter the votes by type") + '" style="margin-top:14px" hidden></div>' +
      '<p class="muted nota-contexto" id="nota-tipos-votos" style="margin:0" hidden><span aria-hidden="true">💬 </span>' + EP.tr(
        "Quando foi publicada, aparece também a orientação do partido " + EP.gen(p.genero, "dele", "dela") + " na época (ou do bloco ou da federação de que o partido fazia parte): o voto que o líder pediu. É só um pedido: cada um decide o próprio voto. Toque numa votação para ver como todos votaram.",
        "When it was published, the orientation of " + (EP.en && p.genero === "F" ? "her" : EP.en && p.genero === "M" ? "his" : "their") + " party at the time (or of the bloc or federation the party belonged to) also appears: the vote the leader asked for. It is only a request: each member decides their own vote. Tap a vote to see how everyone voted.") + "</p>" +
      '<p class="contagem" id="contagem-votos" aria-live="polite"></p>' +
      '<ul class="lista-votos" id="lista-votos"><li class="carregando">' + EP.tr("Carregando as votações…", "Loading the votes…") + '</li></ul><div class="mais-lista" id="mais-votos"></div></section>';
  }
  var VOTOS = null, mostrandoV = INI_VOTOS, filtroV = "";
  // tipos de votação (classificados por scripts/votacoes.py a partir da descrição oficial; mais em votacoes.html)
  // [ícone, nome no filtro (pt, en), nome na etiqueta (pt, en)]
  var CAT_VOTO = { principal: ["📜", "Texto principal", "Main text", "Texto principal", "Main text"],
    mudanca: ["✏️", "Mudanças no texto", "Changes to the text", "Mudança no texto", "Change to the text"],
    procedimento: ["⏱️", "Procedimentos", "Procedures", "Procedimento", "Procedure"], outra: ["🗂️", "Outras decisões", "Other decisions", "Outra decisão", "Other decision"] };
  var ORI_VOTO = { "Sim": ["Sim", "Yes"], "Não": ["Não", "No"], "Abstenção": ["Abstenção", "Abstain"], "Obstrução": ["Obstrução", "Obstruction"], "Liberado": ["Liberado", "Free vote"] };
  // página da votação (só Câmara e Senado: "2236186-60" e "senado-vot:7107"); outras Casas ainda não têm
  function urlVotacao(k) {
    var m = /^senado-vot:(\d+)$/.exec(k), c = /^(?:camara-vot:)?(\d+-\d+)$/.exec(k);
    return m ? "votacao.html?casa=senado&id=" + m[1] : c ? "votacao.html?casa=camara&id=" + c[1] : null;
  }
  // orientação do partido da pessoa NA ÉPOCA (3º e 4º elementos do par: p = do partido, f = da federação, b = do bloco)
  function oriVotoHtml(x) {
    if (!x.ori) return "";
    var de = x.oriDe === "f" ? EP.tr("Orientação da federação do partido", "Orientation of the party's federation") :
      x.oriDe === "b" ? EP.tr("Orientação do bloco do partido", "Orientation of the party's bloc") : EP.tr("Orientação do partido", "Party's orientation");
    var val = ORI_VOTO[x.ori];
    return '<small><span aria-hidden="true">💬 </span>' + de + ": <b>" + (val ? esc(EP.tr(val[0], val[1])) : D.ptHtml(x.ori, true)) + "</b></small>";
  }
  function desenhaFiltroVotos() {
    var box = document.getElementById("filtro-votos");
    if (!box || !VOTOS || !VOTOS.some(function (x) { return x.categoria; })) return;
    var c = {};
    VOTOS.forEach(function (x) { c[x.categoria] = (c[x.categoria] || 0) + 1; });
    box.innerHTML = '<span class="rot-filtro" aria-hidden="true">' + EP.tr("Tipo de votação:", "Type of vote:") + "</span>" +
      '<button type="button" data-vcat="" aria-pressed="' + (filtroV === "") + '">' + EP.tr("Todas", "All") + " (" + EP.num(VOTOS.length) + ")</button>" +
      ["principal", "mudanca", "procedimento"].filter(function (k) { return c[k]; }).map(function (k) {
        return '<button type="button" data-vcat="' + k + '" aria-pressed="' + (filtroV === k) + '"><span aria-hidden="true">' + CAT_VOTO[k][0] + " </span>" +
          esc(EP.tr(CAT_VOTO[k][1], CAT_VOTO[k][2])) + " (" + EP.num(c[k]) + ")</button>";
      }).join("");
    box.hidden = false;
    document.getElementById("nota-tipos-votos").hidden = false;
  }
  function listaVotos(v) {
    // perfil-mandato-r10: só as votações do período do mandato escolhido (v._fr = [de, até])
    var fr = v._fr, dentro = function (l) { return fr ? l.filter(function (x) { return !x.data || (x.data >= fr[0] && x.data.slice(0, 10) <= fr[1]); }) : l; };
    if ((v.lista || []).length) return Promise.resolve(dentro(v.lista));
    if (!(v.votos || []).length || !v.arquivo) return Promise.resolve([]);
    return EP.json(v.arquivo).then(function (arq) {
      var tab = arq.votacoes || {};
      return dentro(v.votos.map(function (par) {
        var k = String(par[0]);
        var info = tab[k] || tab["camara-vot:" + k] || tab["senado-vot:" + k] || tab[k.replace(/^(camara|senado)-vot:/, "")] || {};
        return Object.assign({ id: k, voto: par[1], ori: par[2] || null, oriDe: par[3] || null }, info);
      }).sort(function (a, b) { return (b.data || "").localeCompare(a.data || ""); }));
    });
  }
  function carregaVotos() {
    var el = document.getElementById("lista-votos");
    if (!el) return;
    function vai() {
      listaVotos(P.votacoes).then(function (l) { VOTOS = l; desenhaFiltroVotos(); desenhaVotos(); }).catch(function () {
        el.innerHTML = '<li class="vazio">' + EP.tr("Não foi possível carregar as votações agora. Tente de novo daqui a pouco.", "The votes could not be loaded right now. Please try again in a little while.") + "</li>";
      });
    }
    // o arquivo central é grande: só carrega quando a seção chega perto da tela
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (ents) { if (ents.some(function (x) { return x.isIntersecting; })) { io.disconnect(); vai(); } }, { rootMargin: "600px 0px" });
      io.observe(document.getElementById("votacoes"));
    } else vai();
  }
  // placar publicado, nas votações que não têm página neste site (Assembleias e Câmaras Municipais); se a lista de votos da
  // fonte somar diferente do placar publicado, a frase diz isso (como na página das votações do Congresso)
  function placarHtml(x) {
    if (!x.placar) return "";
    function pl(o) { return ["Sim", "Não", "Abstenção"].map(function (k) { return esc(D.nomeVoto(k)) + " " + EP.num((o || {})[k] || 0); }).join(" · "); }
    return " (" + pl(x.placar) + ")" + (x.aviso && x.aviso.oficial && x.aviso.contado ? "<small>" + EP.tr(
      "O placar publicado (" + pl(x.aviso.oficial) + ") é diferente da soma da lista de votos da fonte (" + pl(x.aviso.contado) + ").",
      "The published tally (" + pl(x.aviso.oficial) + ") differs from the sum of the source's list of votes (" + pl(x.aviso.contado) + ").") + "</small>" : "");
  }
  function desenhaVotos(focarDe) {
    var el = document.getElementById("lista-votos");
    if (!el || !VOTOS) return;
    lembraVotos();
    var lista = filtroV ? VOTOS.filter(function (x) { return x.categoria === filtroV; }) : VOTOS;
    var vis = lista.slice(0, mostrandoV);
    el.innerHTML = vis.map(function (x, k) {
      var vt = D.voto(x.voto);
      var cat = CAT_VOTO[x.categoria], u = urlVotacao(x.id);
      var res = x.resultado ? " · " + EP.tr("Resultado: ", "Result: ") + D.resultado(x.resultado) + (u ? "" : placarHtml(x)) : "";
      var tit = "<b>" + (x.proposta ? EP.pt(esc(x.proposta)) : EP.tr("Votação", "Vote")) + "</b>" + (x.data ? "\u00a0·\u00a0" + EP.data(x.data) : "");
      return "<li" + (focarDe != null && k === focarDe ? ' tabindex="-1"' : "") + '><span class="voto-chip" style="--cv:' + (COR_VOTO[vt.cat] || COR_VOTO.Outro) + '"><span class="sr">' + EP.tr("Voto: ", "Vote: ") + "</span>" + esc(vt.curto) + "</span>" +
        '<span class="v-txt">' + (u ? '<a href="' + u + '">' + tit + '<span class="sr"> (' + EP.tr("ver como todos votaram", "see how everyone voted") + ")</span></a>" : tit) + res +
        (cat ? ' <span class="chip neutro" style="font-size:.75rem;padding:1px 8px;white-space:normal"><span aria-hidden="true">' + cat[0] + " </span>" +
          esc(EP.tr(cat[3], cat[4])) + "</span>" : "") +
        (vt.longo ? "<small>" + esc(vt.longo) + "</small>" : "") + oriVotoHtml(x) +
        (x.descricao ? '<span class="desc-voto" style="display:block">' + EP.pt(esc(x.descricao)) + "</span>" : "") +
        (x.url ? linkFora(x.url, EP.tr("Ver no site oficial", "See it on the official website") + '<span class="sr"> (' + EP.pt(esc(x.proposta || "")) + ")</span>", true) : "") + "</span></li>";
    }).join("") || '<li class="vazio">' + EP.tr("Nenhuma votação encontrada.", "No votes found.") + "</li>";
    var c = document.getElementById("contagem-votos");
    if (c) {
      var txt = EP.tr("Mostrando " + EP.num(vis.length) + " de " + EP.num(lista.length) + (lista.length === 1 ? " votação" : " votações") + ", da mais nova para a mais antiga.",
        "Showing " + EP.num(vis.length) + " of " + EP.num(lista.length) + (lista.length === 1 ? " vote" : " votes") + ", newest first.");
      if (c.textContent !== txt) c.textContent = txt;
    }
    document.getElementById("mais-votos").innerHTML = lista.length > vis.length ? '<button type="button" class="btn claro" id="ver-mais-votos">' +
      EP.tr("Mostrar mais votações", "Show more votes") + ' <span aria-hidden="true">▾</span></button>' : "";
    if (focarDe != null && el.children[focarDe]) el.children[focarDe].focus();
  }

  // ---------------------------------------------------------------- gastos, comissões, executivo
  // "desde fevereiro de 2023" / "since February 2023": começo do período que os dados cobrem (muda a cada mandato)
  var MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
  var MESES_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  function desdeMes(iso) {
    var m = /^(\d{4})-(\d{2})/.exec(iso || "");
    if (!m) return "";
    return EP.tr("desde " + MESES_PT[+m[2] - 1] + " de " + m[1], "since " + MESES_EN[+m[2] - 1] + " " + m[1]);
  }
  function gastosHtml(p) {
    var g = p.gastos;
    if (!g || g.total == null) return "";
    var max = Math.max.apply(null, (g.porTipo || []).map(function (x) { return x.valor; }).concat([1]));
    var regional = p.tipo === "dest" || p.tipo === "ver";
    var quem = p.tipo === "sen" ? EP.tr("Todo senador", "Every senator") : EP.tr("Todo deputado", "Every deputy");
    var quemR = p.tipo === "ver" ? EP.tr("cada vereador", "each city councilor") : p.uf === "DF" ? EP.tr("cada deputado distrital", "each district deputy") : EP.tr("cada deputado estadual", "each state deputy");
    var explica = regional ? EP.tr(
        "Além do salário, " + quemR + " pode usar uma verba para pagar despesas do trabalho, como escritório, combustível e divulgação. <b>Não é salário.</b> Cada Casa tem as suas regras e os seus limites. Gastar mais ou menos não quer dizer, sozinho, trabalhar mais ou menos.",
        "Besides the salary, " + quemR + " can use an allowance to pay for work expenses, such as offices, fuel and publicity. <b>It is not a salary.</b> Each legislature has its own rules and limits. Spending more or less does not, on its own, mean working more or less.") :
      EP.tr(quem + " tem uma verba por mês para pagar despesas do trabalho, como passagens, escritório, combustível e divulgação. <b>Não é salário.</b> O limite muda de estado para estado. Gastar mais ou menos não quer dizer, sozinho, trabalhar mais ou menos.",
        quem + " has a monthly allowance (the cota) to pay for work expenses, such as flights, offices, fuel and publicity. <b>It is not a salary.</b> The limit is different for each state. Spending more or less does not, on its own, mean working more or less.");
    // meses que o número do ano cobre (["2026-01", "2026-09"]): "de janeiro a setembro de 2026"
    var ms = g.meses && g.meses.length === 2 ? [+String(g.meses[0]).slice(5, 7), +String(g.meses[1]).slice(5, 7)] : null;
    var rotAno = ms && ms[0] && ms[1] && ms[1] >= ms[0] ? (ms[0] === ms[1] ? EP.tr("gastos em " + MESES_PT[ms[0] - 1] + " de " + g.ano, "spent in " + MESES_EN[ms[0] - 1] + " " + g.ano) :
      EP.tr("gastos de " + MESES_PT[ms[0] - 1] + " a " + MESES_PT[ms[1] - 1] + " de " + g.ano, "spent from " + MESES_EN[ms[0] - 1] + " to " + MESES_EN[ms[1] - 1] + " " + g.ano)) :
      EP.tr("gastos em ", "spent in ") + esc(g.ano);
    return '<section class="secao-perfil" id="gastos" aria-labelledby="t-gastos"><h2 id="t-gastos"><span class="ic" aria-hidden="true">💰</span>' +
      (regional ? EP.tr("Gastos do mandato", "Office spending") : EP.tr("Gastos da cota do mandato", "Spending from the office allowance")) + "</h2>" +
      (g.nome ? '<p class="muted">' + EP.tr("O que entra aqui: ", "What is counted here: ") + "<b>" + (EP.en && g.nome_en ? esc(g.nome_en) : EP.pt(esc(g.nome))) + "</b></p>" : "") +
      '<div class="grandes-n d-grandes" style="margin-top:14px"><div class="grande-n"><span class="d-ic peq" aria-hidden="true">💰</span><b>' + EP.dinheiroCurto(g.total) + "</b><span>" + rotAno + "</span></div>" +
      (g.mandatoTotal != null ? '<div class="grande-n"><span class="d-ic peq" aria-hidden="true">🧾</span><b>' + EP.dinheiroCurto(g.mandatoTotal) + "</b><span>" + desdeMes(g.desde || "2023-02") + "</span></div>" : "") + "</div>" +
      // site-d-r14: a frase essencial fica à vista; a explicação inteira, no "Saber mais"
      '<div class="dica-coruja"><span class="coruja" aria-hidden="true">🦉</span><p>' + EP.tr("É uma verba para as despesas do trabalho. <b>Não é salário.</b>", "It is an allowance for work expenses. <b>It is not a salary.</b>") + "</p></div>" +
      (EP.d ? EP.d.saiba("<p>" + explica + "</p>", EP.tr("Como funciona esta verba", "How this allowance works")) : '<div class="dica-coruja"><span class="coruja" aria-hidden="true">🦉</span><p>' + explica + "</p></div>") +
      ((g.porTipo || []).length ? '<h3 style="margin-top:16px">' + EP.tr("Com o que gastou em ", "What the money was spent on in ") + esc(g.ano) + '</h3><ul class="gastos-lista" style="list-style:none;padding:0">' + g.porTipo.slice(0, 8).map(function (x) {
        return '<li class="gasto"><span>' + D.gasto(x.tipo) + "</span><b>" + EP.dinheiro(x.valor) + '</b><span class="tr" aria-hidden="true"><i style="width:' + (100 * x.valor / max).toFixed(1) + '%"></i></span></li>';
      }).join("") + "</ul>" : regional ? '<p class="muted" style="margin-top:10px">' + EP.tr("A Casa não separa estes gastos por tipo: aqui aparecem só os totais.",
        "The legislature does not break this spending down by type: only the totals are shown here.") + "</p>" : "") +
      (g.fonte ? '<p style="margin-top:10px">' + fonteBtn(g.fonte, null, EP.tr("gastos", "spending")) + "</p>" : "") + "</section>";
  }
  function comissoesHtml(p) {
    if (!(p.comissoes || []).length) return "";
    return '<section class="secao-perfil" aria-labelledby="t-comissoes"><h2 id="t-comissoes"><span class="ic" aria-hidden="true">👥</span>' + EP.tr("Comissões de que participa", "Committees") + "</h2>" +
      '<p class="muted">' + EP.tr("Comissões são grupos menores que estudam as propostas de um assunto antes da votação de todos.", "Committees are smaller groups that study the proposals on one subject before everyone votes on them.") +
      (EP.en ? " Committee names are official names in Portuguese." : "") + "</p>" +
      '<ul class="comissoes">' + p.comissoes.map(function (c) { return '<li class="chip neutro">' + EP.pt(esc(c.nome || c.sigla)) + (c.papel ? " · " + D.papel(c.papel) : "") + "</li>"; }).join("") + "</ul></section>";
  }
  // texto em inglês que cita, entre aspas, nomes oficiais em português ("Veto a Projeto de Lei"): as citações ficam
  // marcadas como português (leitor de tela e conferência de idioma)
  function citacoesPt(txt) {
    return String(txt).split(/("[^"]+"|“[^”]+”)/).map(function (s, k) {
      return k % 2 && /[ãõçáéíóúâêôà]|\b(de|do|da|dos|das|ao|projeto|lei|veto|mensagem)\b/i.test(s) ?
        esc(s.charAt(0)) + EP.pt(esc(s.slice(1, -1))) + esc(s.charAt(s.length - 1)) : esc(s);
    }).join("");
  }
  function executivoHtml(p) {
    var e = p.executivo;
    if (!e || (e.leisSancionadas == null && e.vetos == null)) return "";
    var ini = (e.periodo && e.periodo.inicio) || "2023";
    // começo do mandato (1º de janeiro): só o ano; quem assumiu depois: a data ("desde 4 de maio de 2026")
    var desde = /^\d{4}(-01-01)?$/.test(ini) ? ini.slice(0, 4) : EP.dataLonga(ini);
    var ultima = e.periodo && e.periodo.ultimaLei;
    var comoContou = EP.en ? e.nota_en || e.obs_en : e.nota || e.obs;
    // quem aprova as leis e quem as assina: Congresso e presidente; Assembleia e governador; Câmara Municipal e prefeito
    var f = p.genero === "F";
    var casa = p.tipo === "gov" ? (p.uf === "DF" ? ["A Câmara Legislativa", "pela Câmara Legislativa", "a Câmara Legislativa", "the Legislative Chamber"] :
        ["A Assembleia Legislativa", "pela Assembleia Legislativa", "a Assembleia Legislativa", "the state legislature"]) :
      p.tipo === "pref" ? ["A Câmara Municipal", "pela Câmara Municipal", "a Câmara Municipal", "the city council"] :
      ["O Congresso", "pelo Congresso", "o Congresso", "Congress"];
    var chefe = p.tipo === "gov" ? (f ? ["a governadora", "pela governadora"] : ["o governador", "pelo governador"]).concat(["the governor"]) :
      p.tipo === "pref" ? (f ? ["a prefeita", "pela prefeita"] : ["o prefeito", "pelo prefeito"]).concat(["the mayor"]) :
      ["o presidente", "pelo presidente", "the President"];
    function mai(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
    var regra = p.tipo === "gov" ? (p.uf === "DF" ? ["na Lei Orgânica do Distrito Federal", "the Federal District's Organic Law"] : ["na Constituição do estado", "the state Constitution"]) :
      p.tipo === "pref" ? ["na Lei Orgânica do município", "the city's Organic Law"] : ["na Constituição", "the Constitution"];
    return '<section class="secao-perfil" aria-labelledby="t-exec"><h2 id="t-exec"><span class="ic" aria-hidden="true">✍️</span>' + EP.tr("Leis sancionadas e vetos", "Laws signed and vetoes") + "</h2>" +
      '<p class="muted">' + EP.tr(casa[0] + " aprova as leis; " + chefe[0] + " assina (sanciona) ou recusa (veta), no todo ou em parte. " + casa[0] + " pode derrubar o veto.",
        mai(casa[3]) + " passes laws; " + chefe[2] + " signs them (sanction) or rejects them (veto), in whole or in part. " + mai(casa[3]) + " can override a veto.") + '</p><div class="grandes-n d-grandes">' +
      (e.leisSancionadas != null ? '<div class="grande-n"><span class="d-ic peq" aria-hidden="true">✍️</span><b>' + EP.num(e.leisSancionadas) + "</b><span>" + EP.tr("leis sancionadas desde " + desde, "laws signed since " + desde) + "</span></div>" : "") +
      (e.leisPromulgadasPelaCasa ? '<div class="grande-n"><span class="d-ic peq" aria-hidden="true">📜</span><b>' + EP.num(e.leisPromulgadasPelaCasa) + "</b><span>" + EP.tr("leis promulgadas " + casa[1] + " desde " + desde, "laws promulgated by " + casa[3] + " itself since " + desde) + "</span></div>" : "") +
      (e.vetos != null ? '<div class="grande-n"><span class="d-ic peq" aria-hidden="true">✋</span><b>' + EP.num(e.vetos) + "</b><span>" + (e.vetosTotais != null && e.vetosParciais != null ?
        EP.tr("vetos desde " + desde + ": " + EP.num(e.vetosTotais) + (e.vetosTotais === 1 ? " total" : " totais") + " e " + EP.num(e.vetosParciais) + (e.vetosParciais === 1 ? " parcial" : " parciais"),
          "vetoes since " + desde + ": " + EP.num(e.vetosTotais) + " full and " + EP.num(e.vetosParciais) + " partial") :
        EP.tr("vetos (totais ou parciais) desde " + desde, "vetoes (full or partial) since " + desde)) + "</span></div>" : "") +
      "</div>" + (e.vetosTotais != null && e.vetosParciais != null && (e.vetosTotais + e.vetosParciais) ? '<div class="d-dupla" aria-hidden="true"><span class="d-dupla-barra"><i style="flex:' + e.vetosTotais +
        '"></i><i class="b" style="flex:' + e.vetosParciais + '"></i></span><span class="d-dupla-leg"><span><i></i>' + esc(EP.tr("vetos à lei inteira", "full vetoes")) + '</span><span><i class="b"></i>' +
        esc(EP.tr("vetos a uma parte", "partial vetoes")) + "</span></span></div>" : "") + (e.leisSancionadas != null && ultima ? '<p class="muted" style="margin-top:8px">' + esc(EP.tr("A lei mais recente na fonte é de " + EP.dataLonga(ultima) + ".", "The most recent law in the source is from " + EP.dataLonga(ultima) + ".")) + "</p>" : "") +
      (EP.d ? EP.d.saiba : function (x) { return x; })('<p class="muted nota-contexto" style="margin-top:0"><span aria-hidden="true">🦉 </span>' + (e.leisSancionadas != null ? EP.tr(
        "Quase todo projeto aprovado " + casa[1] + " passa " + chefe[1] + ", venha de quem vier. Por isso, este número mostra o que " + casa[2] + " aprovou e " + chefe[0] + " assinou, e não o que " + chefe[0] + " propôs" + (p.propostas ? " (isso está em \"O que " + ele(p) + " propôs\")" : "") + ". ",
        "Almost every bill passed by " + casa[3] + " goes to " + chefe[2] + ", no matter who proposed it. So this number shows what " + casa[3] + " passed and " + chefe[2] + " signed, not what " + chefe[2] + " proposed" + (p.propostas ? " (that is under \"What " + ele(p) + " proposed\")" : "") + ". ") : "") + EP.tr(
        "Vetar também é uma tarefa prevista " + regra[0] + ": o número, sozinho, não diz se as decisões foram boas ou ruins.",
        "Vetoing is also a task set by " + regra[1] + ": the number alone does not say whether the decisions were good or bad.") +
      (e.leisPromulgadasPelaCasa ? " " + EP.tr(casa[0] + " promulga a própria lei quando derruba um veto ou quando " + chefe[0] + " não sanciona nem veta no prazo.",
        mai(casa[3]) + " promulgates a law itself when it overrides a veto or when " + chefe[2] + " neither signs nor vetoes it in time.") : "") + "</p>",
        EP.tr("Assinar não é propor: o que estes números querem dizer", "Signing is not proposing: what these numbers mean")) +
      (comoContou ? '<details class="como-contou"><summary>' + EP.tr("Como contamos", "How we counted") + "</summary><p>" + (EP.en && !(e.nota_en || e.obs_en) ? D.ptHtml(comoContou) : EP.en ? citacoesPt(comoContou) : esc(comoContou)) + "</p></details>" : "") +
      (e.fonte || (e.fontes || []).length ? '<p style="margin-top:10px">' + fonteBtn((e.fontes || []).length ? e.fontes : e.fonte, null, EP.tr("leis e vetos", "laws and vetoes")) + "</p>" : "") + "</section>";
  }
  // ---------------------------------------------------------------- onde ver mais
  // Quando a Assembleia, a Câmara Municipal ou o governo não publicam um dado de um jeito que o site consiga ler, o perfil
  // não promete nada: diz o que não está aqui e por quê (as notas da Casa e o mapa das cidades, dados/municipios), onde ver
  // nos sites oficiais e como pedir pela Lei de Acesso à Informação, que vale para todo órgão público.
  var LAI_URL = "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12527.htm";
  function urlBoa(u) { return typeof u === "string" && /^https?:\/\/[^\s"'<>]+$/i.test(u) ? u : ""; }
  function nomeAssembleia(p) {
    var i = p.infoCasa || {};
    if (i.casa) return EP.en && i.casa_en ? esc(i.casa_en) : EP.pt(esc(i.casa));
    if (p.uf === "DF") return EP.tr("Câmara Legislativa do Distrito Federal", "Legislative Chamber of the Federal District");
    return EP.en ? "Legislative Assembly " + esc(EP.doEstado(p.uf)) : "Assembleia Legislativa " + esc(EP.doEstado(p.uf));
  }
  // as notas da Casa que falam de um assunto (ex.: só as que explicam por que as propostas não entram)
  function notasCasa(p, re) {
    var i = p.infoCasa || {}, pt = i.notas || [], en = i.notas_en || [], par = EP.en && en.length === pt.length;
    return pt.map(function (n, k) { return re.test(n) ? (par ? esc(en[k]) : EP.en ? EP.pt(esc(n)) : esc(n)) : null; }).filter(Boolean);
  }
  // a página de proposições do sistema da Câmara: a que o mapa das cidades achou, ou a busca padrão do SAPL
  function urlPropostasCamara(c) {
    if (urlBoa(c.propostas)) return c.propostas;
    if (c.sistema === "sapl" && urlBoa(c.api)) return c.api.replace(/\/api\/?$/, "") + "/materia/pesquisar-materia";
    return "";
  }
  function itemOnde(ic, url, txt, desc) {
    return '<li><span class="ic-onde" aria-hidden="true">' + ic + "</span><span>" + linkFora(url, txt, true) + (desc ? "<small>" + desc + "</small>" : "") + "</span></li>";
  }
  function ondeVerHtml(p) {
    if (p.e26) return "";  // eleitos 2026 (até a posse): ainda sem o cargo, não há o que procurar na Casa
    var t = p.tipo, ex = p.executivo || {};
    var semProp = !p.propostas, semExec = ex.leisSancionadas == null && ex.vetos == null;
    if (!((t === "dest" || t === "ver") && semProp) && !((t === "gov" || t === "pref") && (semProp || semExec))) return "";
    var i = p.infoCasa || {}, o = p.onde || {}, cam = o.camara || {}, pre = o.prefeitura || {};
    var f = p.genero === "F", txt = "", notas = [], links = [], conferido = cam.conferido || pre.conferido || "";
    var urlProp = urlPropostasCamara(cam);
    var sicCasa = urlBoa(i.sic) || urlBoa(cam.sic);
    var pedir = EP.tr("Pedir a informação pela Lei de Acesso à Informação", "Ask for the information under the Access to Information Law");

    if (t === "dest") {
      var casa = nomeAssembleia(p);
      txt = EP.tr("As propostas de cada " + (p.uf === "DF" ? "deputado distrital" : "deputado estadual") + " não estão neste site.",
        "Each " + (p.uf === "DF" ? "district" : "state") + " deputy's bills are not on this site.");
      notas = notasCasa(p, /propost|proposi/i);
      if (!notas.length) txt += EP.tr(" Não achamos essas informações publicadas num formato que o site consiga ler sozinho.",
        " We could not find this information published in a format this site can read on its own.");
      if (urlBoa(i.site)) links.push(itemOnde("🏛️", i.site, EP.tr("Site oficial da ", "Official website of the ") + casa,
        EP.tr("Lá dá para procurar as propostas de cada deputado.", "You can look up each deputy's bills there.")));
      if (sicCasa) links.push(itemOnde("✉️", sicCasa, pedir, EP.tr("Canal oficial da ", "Official channel of the ") + casa + "."));
    } else if (t === "ver") {
      txt = EP.tr("As propostas de cada vereador não estão neste site.", "Each city councilor's bills are not on this site.");
      notas = notasCasa(p, /propost|proposi/i);
      if (cam.propostasOnline === false) {
        txt += EP.tr(" Não achamos as propostas dos vereadores publicadas no site oficial da Câmara Municipal.",
          " We did not find the councilors' bills published on the City Council's official website.");
        if (cam.motivo) notas.push(EP.en && cam.motivo_en ? esc(cam.motivo_en) : EP.en ? EP.pt(esc(cam.motivo)) : esc(cam.motivo));
      }
      if (urlProp && cam.propostasOnline !== false) links.push(itemOnde("📜", urlProp, EP.tr("Propostas no sistema oficial da Câmara Municipal", "Bills on the City Council's official system"),
        EP.tr("A Câmara mostra lá as propostas de cada vereador.", "The City Council shows each councilor's bills there.")));
      if (urlBoa(i.site) || urlBoa(cam.site)) links.push(itemOnde("🏛️", urlBoa(i.site) || cam.site, EP.tr("Site oficial da Câmara Municipal", "Official website of the City Council"), ""));
      if (sicCasa) links.push(itemOnde("✉️", sicCasa, pedir, EP.tr("Canal oficial da Câmara Municipal.", "The City Council's official channel.")));
    } else {
      // governador(a) ou prefeito(a): o que assinou e vetou (Diário Oficial) e o que mandou para a Casa
      var gov = t === "gov", chefe = gov ? EP.gen(p.genero, "o governador", "a governadora") : EP.gen(p.genero, "o prefeito", "a prefeita");
      var casaPt = gov ? (p.uf === "DF" ? "a Câmara Legislativa" : "a Assembleia Legislativa") : "a Câmara Municipal";
      var casaEn = gov ? (p.uf === "DF" ? "the Legislative Chamber" : "the state legislature") : "the City Council";
      var chefeEn = gov ? "the governor" : "the mayor";
      var oQue = semProp && semExec ? [
          "As leis que " + chefe + " assinou, os vetos e os projetos que mandou para " + casaPt + " não estão neste site.",
          "The laws " + chefeEn + " signed, the vetoes and the bills sent to " + casaEn + " are not on this site."] :
        semExec ? ["As leis que " + chefe + " assinou e os vetos não estão neste site.", "The laws " + chefeEn + " signed and the vetoes are not on this site."] :
        ["Os projetos que " + chefe + " mandou para " + casaPt + " não estão neste site.", "The bills " + chefeEn + " sent to " + casaEn + " are not on this site."];
      txt = EP.tr(oQue[0], oQue[1]);
      if (!gov) notas = notasCasa(p, /prefeit|executivo/i);
      var dio = pre.diarioOficial || p.diarioOficial || {};
      // dados/prefeituras (montar.py): onde o robô procurou as leis da prefeitura e por que a contagem não é segura
      var lf = !gov && semExec && pre.leis && pre.leis.motivo ? pre.leis : null, lfLink = lf && urlBoa(lf.url);
      if (lf) {
        var lfMot = EP.en && lf.motivo_en ? esc(lf.motivo_en) : EP.en ? EP.pt(esc(lf.motivo)) : esc(lf.motivo);
        var lfNome = lf.nome ? (EP.en ? (lf.nome_en && lf.nome_en !== lf.nome ? esc(lf.nome_en) : EP.pt(esc(lf.nome))) : esc(lf.nome)) :
          lf.tipo === "legislacao" ? EP.tr("Página de leis do site oficial da prefeitura", "Laws page of the city government's official website") : EP.tr("Diário Oficial", "Official Gazette");
        if (lfLink) links.push(itemOnde(lf.tipo === "legislacao" ? "📜" : "📰", lf.url, lfNome, lfMot));
        else notas.push(lfMot);
      }
      if (semExec && urlBoa(dio.url) && !(lfLink && lf.tipo === "diario")) links.push(itemOnde("📰", dio.url, dio.nome ? (EP.en ? EP.pt(esc(dio.nome)) : esc(dio.nome)) : EP.tr("Diário Oficial", "Official Gazette"),
        gov ? EP.tr("É onde saem as leis, os vetos e os decretos do governo do estado.", "Where the state government's laws, vetoes and decrees are published.") :
          EP.tr("É onde saem as leis, os vetos e os decretos da prefeitura.", "Where the city government's laws, vetoes and decrees are published.")));
      if (gov && urlBoa(i.site)) links.push(itemOnde("🏛️", i.site, EP.tr("Site oficial da ", "Official website of the ") + nomeAssembleia(p),
        EP.tr("Os projetos do governo e as leis do estado passam por lá.", "The government's bills and the state's laws go through there.")));
      if (!gov && urlProp) links.push(itemOnde("📜", urlProp, EP.tr("Projetos no sistema oficial da Câmara Municipal", "Bills on the City Council's official system"),
        EP.tr("Os projetos que a prefeitura manda passam pela Câmara.", "The bills the city government sends go through the City Council.")));
      if (!gov && urlBoa(pre.transparencia)) links.push(itemOnde("💰", pre.transparencia, EP.tr("Portal da Transparência da prefeitura", "City government's transparency portal"),
        EP.tr("Mostra quanto a prefeitura recebe e gasta.", "Shows how much the city government receives and spends.")));
      if (!gov && urlBoa(pre.site)) links.push(itemOnde("🏢", pre.site, EP.tr("Site oficial da prefeitura", "Official website of the city government"), ""));
      if (!gov && urlBoa(pre.sic)) links.push(itemOnde("✉️", pre.sic, pedir, EP.tr("Canal oficial da prefeitura.", "The city government's official channel.")));
    }
    return '<section class="secao-perfil onde-ver" aria-labelledby="t-onde"><h2 id="t-onde"><span class="ic" aria-hidden="true">🔎</span>' + EP.tr("Onde ver mais", "Where to find more") + "</h2>" +
      "<p>" + txt + "</p>" + (notas.length ? '<ul class="notas-casa">' + notas.map(function (n) { return "<li>" + n + "</li>"; }).join("") + "</ul>" : "") +
      (links.length ? '<ul class="links-onde">' + links.join("") + "</ul>" : "") +
      (links.length && conferido ? '<p class="muted" style="margin-top:8px;font-size:.88rem">' + EP.tr("Endereços oficiais conferidos em ", "Official addresses checked on ") + EP.data(conferido) + ".</p>" : "") +
      '<details class="lai"><summary>' + EP.tr("Como pedir uma informação que não está na internet?", "How to ask for information that is not online?") + "</summary><p>" + EP.tr(
        "Pela <b>Lei de Acesso à Informação</b>, qualquer pessoa pode pedir informações a um órgão público, como uma Câmara, uma Assembleia, uma prefeitura ou um governo, sem precisar dizer por quê. O pedido é de graça, e a resposta tem que sair em até 20 dias (que podem virar 30, se o órgão explicar o motivo). Procure \"Acesso à Informação\" ou \"e-SIC\" no site oficial do órgão.",
        "Under the <b>Access to Information Law</b>, anyone can ask public bodies (such as city councils, state legislatures, city governments and state governments) for information, without having to say why. The request is free, and the answer must come within 20 days (which can become 30 if the body explains why). Look for \"<span lang=\"pt-BR\">Acesso à Informação</span>\" or \"e-SIC\" on the body's official website.") +
      " " + linkFora(LAI_URL, EP.tr("Lei nº 12.527/2011", "Law No. 12,527/2011"), true) + "</p></details></section>";
  }
  function avisoEMinisterio(p) {
    var h = "";
    if (p.avisoLista) h += '<p class="aviso"><span aria-hidden="true">ℹ️ </span>' + D.aviso(p.avisoLista, p.avisoLista_en) + "</p>";
    h += ondeVerHtml(p);
    if (p.tipo === "min") {
      var f = [].concat(p.fontes || p.fonte || []);
      if (p.oQueFaz) h = '<section class="secao-perfil" aria-labelledby="t-area"><h2 id="t-area"><span class="ic" aria-hidden="true">' + esc(p.ic || "🏢") + "</span>" + EP.tr("O que o ministério faz", "What the ministry does") + "</h2><p>" +
        (EP.en && !p.oQueFaz_en ? D.ptHtml(p.oQueFaz) : EP.md(EP.campo(p, "oQueFaz"))) + "</p>" +
        (p.nota ? '<p class="aviso">' + (EP.en && !p.nota_en ? D.ptHtml(p.nota) : EP.md(EP.campo(p, "nota"))) + "</p>" : "") + "</section>" + h;
      if (f.length) h += '<section class="secao-perfil" aria-labelledby="t-fontes-min"><h2 id="t-fontes-min"><span class="ic" aria-hidden="true">📚</span>' + EP.tr("Fontes", "Sources") + "</h2>" + EP.fontesHtml(f) + "</section>";
    }
    return h;
  }

  // ---------------------------------------------------------------- "Voltar"
  // Volta para a página de onde a pessoa veio (o Brasil, um estado, uma cidade, uma votação ou a busca da página inicial), e não
  // sempre para a lista do cargo. Se veio direto de lá, usa o histórico do navegador: a lista reaparece como estava (filtros e rolagem).
  // Sem pista de onde veio (link compartilhado, por exemplo), vai para a lista do cargo.
  var LISTAS = /^(index|brasil|estado|cidade|votacoes|votacao)\.html/;
  function combina(pagina, p) {
    var m = /^estado\.html\?uf=([a-z]{2})/i.exec(pagina);
    if (m) return String(p.uf || "").toUpperCase() === m[1].toUpperCase();
    m = /^cidade\.html\?ibge=(\d+)/.exec(pagina);
    if (m) return !!p.municipio && String(p.municipio.ibge) === m[1];
    return LISTAS.test(pagina);
  }
  function nomeVolta(pagina) {
    var m = /^estado\.html\?uf=([a-z]{2})/i.exec(pagina);
    if (m) return EP.tr("Voltar para a política " + EP.doEstado(m[1].toUpperCase()), "Back to the politics " + EP.doEstado(m[1].toUpperCase()));
    if (/^cidade\.html/.test(pagina)) return EP.tr("Voltar para a política da cidade", "Back to the city's politics");
    if (/^brasil\.html/.test(pagina)) return EP.tr("Voltar para a política do Brasil", "Back to Brazil's politics");
    if (/^index\.html/.test(pagina)) return EP.tr("Voltar para a página inicial", "Back to the home page");
    if (/^votacao\.html/.test(pagina)) return EP.tr("Voltar para a votação", "Back to the vote");
    if (/^votacoes\.html/.test(pagina)) return EP.tr("Voltar para as votações", "Back to the votes");
    return EP.tr("Voltar para a lista", "Back to the list");
  }
  function ligaVoltar(p) {
    var volta = document.getElementById("voltar-lista");
    if (!volta) return;
    var v = EP.leVolta(), ref = null, destino = null, peloHistorico = false, mexeu = false;
    try { if (document.referrer && new URL(document.referrer).origin === location.origin) ref = EP.endereco(document.referrer); } catch (e) {}
    if (ref && LISTAS.test(ref)) {
      destino = v && v.pagina === ref ? v : { pagina: ref, secao: "", id: id };
      peloHistorico = history.length > 1;
    } else if (v && combina(v.pagina, p)) destino = v;
    if (!destino && p.volta) destino = p.volta;  // perfis montados por outro arquivo (ministros do STF, eleitos 2026): o Voltar leva à seção de onde vieram
    // perfil-mandato-r10: trocar de mandato abre o perfil de novo (um passo a mais no histórico); quem tinha vindo de uma lista
    // continua voltando para ela de uma vez (o destino e os passos ficam guardados em history.state)
    var st0 = history.state || {};
    if ((!ref || !LISTAS.test(ref)) && st0.epVolta && st0.epVolta.pagina) { destino = st0.epVolta; peloHistorico = true; }
    VOLTA = peloHistorico ? destino : null;
    if (!destino) {
      var federal = /^(dep|sen|pres|vp|min)$/.test(p.tipo);
      destino = { pagina: federal ? "brasil.html" : p.municipio ? "cidade.html?ibge=" + p.municipio.ibge : "estado.html?uf=" + p.uf,
        secao: federal ? { dep: "camara", sen: "senado" }[p.tipo] || "executivo" : "", id: id };
    }
    var nome = nomeVolta(destino.pagina);
    volta.href = destino.pagina + (EP.en ? (destino.pagina.indexOf("?") > -1 ? "&" : "?") + "lang=en" : "") + (destino.secao ? "#" + destino.secao : "");
    volta.removeAttribute("data-en-aria-label");
    volta.removeAttribute("data-en-title");
    volta.setAttribute("aria-label", nome);
    volta.title = nome;
    // um link para dentro da página (ex.: "Pular para o conteúdo") também entra no histórico: aí o "voltar" do navegador não serve
    window.addEventListener("hashchange", function () { mexeu = true; });
    volta.addEventListener("click", function (e) {
      if (e.button || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
      EP.gravaVolta({ pagina: destino.pagina, secao: destino.secao || "", id: destino.id || id, y: destino.y || 0, voltando: Date.now() });
      // as abas do perfil (js/abas.js) põem passos no histórico: volta todos de uma vez, até a lista
      if (peloHistorico && !mexeu) { e.preventDefault(); history.go(-(((history.state || {}).epPassos || 0) + 1)); }
    });
  }

  // ---------------------------------------------------------------- mandatos (perfil-mandato-r10)
  // O perfil mostra um mandato de cada vez. O padrão é o de hoje; com ?mandato=<id> (ex.: pessoa.html?id=pres-lula&mandato=dep-1987)
  // a mesma tela (Quem é, O que propôs, Leis e vetos, Como votou, Gastos, Fontes) mostra só o daquele mandato, com a faixa
  // amarela "Você está vendo: ..." e o "Voltar para hoje". Os mandatos vêm da linha do tempo (dados/trajetoria/, js/trajetoria.js);
  // o que a pessoa propôs num mandato antigo vem do próprio perfil (filtrado pelas datas), do perfil de hoje de quem já foi
  // deputado(a) ou senador(a) (dados/pessoas/<dep|sen>-<id>.json) ou de dados/trajetoria/propostas/. Trocar de mandato abre o
  // endereço novo (Voltar e Avançar do navegador funcionam, e dá para compartilhar).
  var MAND = null, VOLTA = null, P0 = null, LISTA0 = null, CHEGOU = null;
  var LEGIS = /^(dep|sen|dest|ddist|ver)$/, EXEC_T = /^(pres|gov|pref)$/, VICE = /^(vp|vgov|vpref)$/;
  var CHAVE_TROCA = "ep-perfil-mandato";
  function dentro(fr) { return function (x) { var d = (x.data || "").slice(0, 10); return !d || (d >= fr[0] && d <= fr[1]); }; }
  function opcoesMandato() { return MAND ? (MAND.futuro ? [MAND.futuro] : []).concat(MAND.lista) : []; }
  function mandatoAberto() { return MAND ? MAND.sel || MAND.atual || MAND.futuro : null; }
  // as abas que cada tipo de mandato tem (para não levar a pessoa a uma aba que o outro mandato não tem)
  function abasDe(md) {
    var l = ["sobre", "trajetoria", "fontes"];
    if (!/^(stf|min)$/.test(md.c)) l.push("propostas");
    if (EXEC_T.test(md.c)) l.push("leis");
    if (LEGIS.test(md.c)) l.push("votacoes", "gastos");
    return l;
  }
  // o endereço do perfil num mandato (null = o de hoje), na mesma aba (ou em "aba"), sem os filtros das listas
  function urlMandato(md, aba) {
    var u = new URL(location.href);
    ["mandato", "prop-papel", "prop-status", "prop-tema", "prop-q", "voto-tipo"].forEach(function (k) { u.searchParams.delete(k); });
    var hoje = !md || md === MAND.atual || md.futuro;
    if (!hoje) u.searchParams.set("mandato", md.id);
    var h = aba != null ? aba : location.hash.slice(1);
    if (h && !hoje && abasDe(md).indexOf(h) < 0) h = "sobre";
    return (u.pathname.split("/").pop() || "pessoa.html") + u.search + (h ? "#" + h : "");
  }
  function vaiPara(md, foco, aba) {
    try {
      sessionStorage.setItem(CHAVE_TROCA, JSON.stringify({ id: id, foco: foco, t: Date.now(), volta: VOLTA,
        passos: ((history.state || {}).epPassos || 0) + 1 }));
    } catch (e) {}
    location.href = urlMandato(md, aba);
  }
  // chegou trocando de mandato? (o seletor, o botão da linha do tempo ou o "Voltar para hoje"): guarda o caminho de volta para
  // a lista e para onde vai o foco
  function chegada() {
    var x = null;
    try { x = JSON.parse(sessionStorage.getItem(CHAVE_TROCA) || "null"); sessionStorage.removeItem(CHAVE_TROCA); } catch (e) {}
    if (!x || x.id !== id || Date.now() - x.t > 20000) return;
    CHEGOU = x;
    if (x.volta) {
      try { history.replaceState(Object.assign({}, history.state || {}, { epPassos: x.passos, epVolta: x.volta }), "", location.href); } catch (e) {}
    }
  }
  function tiraParam() {
    var u = new URL(location.href);
    u.searchParams.delete("mandato");
    try { history.replaceState(history.state, "", u.pathname + u.search + u.hash); } catch (e) {}
  }

  // carrega a linha do tempo e decide o mandato; num mandato antigo, monta a "vista" daquele mandato
  function preparaMandato(p) {
    P0 = p;
    if (!EP.trajetoria || !EP.trajetoria.carrega || p.tipo === "min") { if (EP.param("mandato")) tiraParam(); return p; }
    return EP.trajetoria.carrega(p).then(function (x) {
      if (!x) { if (EP.param("mandato")) tiraParam(); return p; }
      x.d.cidade = p.municipio && p.municipio.nome;
      var M = EP.trajetoria.mandatos(p, x.d, x.t), q = EP.param("mandato"), sel = null;
      MAND = M;
      if (q) sel = M.lista.filter(function (md) { return md.id === q; })[0] || null;
      if (q && (!sel || sel === M.atual)) { tiraParam(); sel = null; }
      M.sel = sel;
      if (p.propostas) LISTA0 = p.propostas.lista || [];
      if (!sel) { filtraHoje(p, M); return p; }
      return vistaMandato(p, sel, M);
    }).catch(function (e) { if (window.console) console.warn("mandato:", e); return p; });
  }
  // o mandato de hoje de deputados e senadores: a lista da Casa tem todos os mandatos; fica só a do mandato de hoje
  function filtraHoje(p, M) {
    var md = M.atual, pr = p.propostas;
    if (!md || !md.m || !pr || !(pr.lista || []).length || !/^(dep|sen)$/.test(p.tipo) || opcoesMandato().length < 2) return;
    var l = pr.lista.filter(dentro(md.fr));
    if (l.length === pr.lista.length) return;
    p.propostas = Object.assign({}, pr, { lista: l, _md: md });
  }
  // quantas propostas o perfil de hoje tem em cada mandato da mesma Casa (para o resumo da linha do tempo)
  function contaProprio(md) {
    if (!md.m || md.m.pf !== id || !LISTA0) return null;
    var l = LISTA0.filter(dentro(md.fr));
    return { prop: l.length, lei: l.filter(function (x) { return x.status === "lei"; }).length };
  }
  var URL_PROP = { camara: "https://www.camara.leg.br/propostas-legislativas/", senado: "https://www25.senado.leg.br/web/atividade/materias/-/materia/" };
  function urlBuscaAutor(m) {
    return m.casa === "camara" ? "https://www.camara.leg.br/busca-portal?contextoBusca=BuscaProposicoes&pagina=1&order=data&abaEspecifica=true&q=autores.ideCadastro%3A%20" + m.id :
      "https://www25.senado.leg.br/web/atividade/materias/-/materia/autor/" + m.id + "/p/1";
  }
  function urlPaginaCasa(m) {
    return m.casa === "camara" ? "https://www.camara.leg.br/deputados/" + m.id : "https://www25.senado.leg.br/web/senadores/senador/-/perfil/" + m.id;
  }
  // a "vista" de um mandato antigo: a mesma forma de um perfil (os mesmos pedaços desenham), só com o daquele período
  function vistaMandato(b, md, M) {
    var d = M.d, c = md.c, g = b.genero, m = md.m;
    var V = { id: b.id, nome: b.nome, nomeCivil: b.nomeCivil, genero: g, foto: b.foto, fotoCredito: b.fotoCredito, nascimento: b.nascimento,
      tipo: c === "ddist" ? "dest" : c, cargo: EP.trajetoria.cargo(c, g, false), uf: c === "ddist" ? "DF" : /^(pres|vp)$/.test(c) ? null : md.uf,
      partido: md.p || null, mandato: { inicio: md.i, fim: md.f }, _md: md, _base: b, _M: M, volta: b.volta };
    var cid = md.ue && d.ues && d.ues[md.ue];
    if (cid && cid[0]) V.municipio = { ibge: cid[0], nome: cid[1] };
    else if (md.it && md.it.cid && b.municipio) V.municipio = b.municipio;
    var arq = null, lista = null, lugar = null;
    if (m && m.pf) arq = m.pf === b.id ? Promise.resolve(b) : EP.json("dados/pessoas/" + m.pf + ".json").catch(function () { return null; });
    else if (m && m.pl) {
      var k = m.casa === "camara" ? "camara:" + m.id + ":" + m.leg : "senado:" + m.id + ":" + m.i;
      lista = EP.json("dados/trajetoria/propostas/" + EP.trajetoria.baldePropostas(m.casa + "-" + m.id) + ".json").then(function (o) { return ((o && o.m) || {})[k] || null; }, function () { return null; });
    }
    // onde ver mais: a Câmara Municipal e a prefeitura da cidade, ou a Assembleia do estado (dados do próprio site)
    if (V.municipio && V.municipio.ibge) lugar = EP.json("dados/cidades/" + EP.UF_IBGE[String(V.municipio.ibge).slice(0, 2)] + "/" + V.municipio.ibge + ".json").catch(function () { return null; });
    else if (/^(gov|vgov|dest|ddist)$/.test(c) && V.uf) lugar = EP.json("dados/estados/" + V.uf + ".json").catch(function () { return null; });
    return Promise.all([arq, lista, lugar]).then(function (r) {
      var f = r[0], pl = r[1], lu = r[2];
      if (lu && lu.onde) { V.onde = lu.onde; V.infoCasa = (lu.vereadores || {}).infoCasa || null; }
      else if (lu && lu.deputadosEstaduais) V.infoCasa = lu.deputadosEstaduais.infoCasa || null;
      var escopo = EP.gen(g, "Propostas apresentadas como " + EP.trajetoria.cargo(c, "M", false).toLowerCase(), "Propostas apresentadas como " + EP.trajetoria.cargo(c, "F", false).toLowerCase());
      if (f && f.propostas) {
        V.propostas = { lista: (f.propostas.lista || []).filter(dentro(md.fr)), escopo: escopo, fonte: f.propostas.fonte, _md: md, _antigo: true,
          outrosUrl: (f.propostas.outros || {}).url || (m ? urlBuscaAutor(m) : null) };
      } else if (pl) {
        V.propostas = { lista: pl.map(function (x) {
          var n = String(x.id).split(":");
          return Object.assign({ tipo: (x.sigla || "").split(" ")[0], url: URL_PROP[n[0]] ? URL_PROP[n[0]] + n[1] : null }, x);
        }), escopo: escopo, fonte: EP.trajetoria.fontesMandato(m).concat([{ veiculo: m.casa === "camara" ? "Câmara dos Deputados" : "Senado Federal",
          titulo: m.casa === "camara" ? "Busca oficial de proposições por autor" : "Matérias por autor (página oficial)", url: urlBuscaAutor(m) }]),
          _md: md, _antigo: true, _semIa: true, outrosUrl: urlBuscaAutor(m) };
      }
      // votações e gastos: o site guarda só os do mandato que está em curso (o de hoje daquele perfil)
      if (f && md.andando && f.votacoes) V.votacoes = Object.assign({}, f.votacoes, { _fr: md.fr });
      if (f && md.andando && f.gastos && f.gastos.total != null) V.gastos = f.gastos;
      if (f && f !== b && md.andando) V.comissoes = f.comissoes;
      return V;
    });
  }

  // ---------------------------------------------------------------- seletor, faixa e partes de um mandato antigo
  function seletorHtml() {
    if (opcoesMandato().length < 2) return "";
    return '<div class="mandato-perfil" id="mandato-perfil"><label id="mp-rot" for="mp-campo"><span aria-hidden="true">📅 </span>' + EP.tr("Mandato", "Term") + "</label>" +
      '<div class="mandato-campo" id="mp-lugar"></div><p class="mandato-dica" id="mp-dica">' +
      esc(EP.tr("Escolha um mandato para ver só o que é daquele período.", "Choose a term to see only what belongs to that period.")) + "</p></div>";
  }
  function ligaSeletor() {
    var lugar = document.getElementById("mp-lugar");
    if (!lugar || !EP.combo) return;
    var ops = opcoesMandato(), aberto = mandatoAberto();
    function v(md) { return md.id || "hoje"; }
    EP.combo(lugar, {
      id: "mp-campo", rotuloId: "mp-rot", descricao: "mp-dica", max: 80, valor: aberto ? v(aberto) : "",
      placeholder: EP.tr("Escolha o mandato…", "Choose a term…"),
      itens: ops.map(function (md) { return { v: v(md), t: EP.trajetoria.rotulo(md, P0, MAND.d) }; }),
      aoEscolher: function (it) {
        var md = ops.filter(function (x) { return v(x) === it.v; })[0];
        if (!md || md === aberto) return;
        vaiPara(md === MAND.atual || md.futuro ? null : md, "seletor");
      }
    });
  }
  function faixaHtml(V) {
    var md = V._md, txt = EP.trajetoria.cargoLugar(md, V._base, MAND.d) + ", " + EP.trajetoria.periodo(md);
    return '<div class="faixa-mandato" id="faixa-mandato" role="region" aria-label="' + esc(EP.tr("Mandato que você está vendo", "Term you are viewing")) + '">' +
      '<p><span class="fm-txt" id="faixa-mandato-txt" tabindex="-1"><span aria-hidden="true">📅 </span>' + EP.tr("Você está vendo: ", "You are viewing: ") + "<b>" + esc(txt) + "</b></span>" +
      '<span class="fm-sep" aria-hidden="true"> · </span><a class="fm-hoje" href="' + esc(urlMandato(null)) + '">' + EP.tr("Voltar para hoje", "Back to today") + "</a></p></div>";
  }
  // a faixa fica presa logo abaixo da barra das abas (ou do cabeçalho, sem abas) e não cobre o conteúdo: a altura dela entra
  // na conta do que fica preso no topo (rolagem até um item, listas que abrem)
  function poeFaixa(V) {
    var grupo = raiz.querySelector(".abas-grupo"), lista = grupo && grupo.querySelector('[role="tablist"]');
    lista = lista && (lista.closest(".abas-barra") || lista);  // a faixa vem logo depois da barra das abas
    var div = document.createElement("div");
    div.innerHTML = faixaHtml(V);
    var f = div.firstChild;
    if (lista) lista.insertAdjacentElement("afterend", f);
    else { var topo = raiz.querySelector(".perfil-topo"); if (topo) topo.insertAdjacentElement("afterend", f); else raiz.insertBefore(f, raiz.firstChild); }
    var html = document.documentElement;
    html.classList.add("com-faixa");
    if (!lista) html.classList.add("faixa-sem-abas");
    function mede() {
      var t = document.querySelector("header.topo");
      html.style.setProperty("--faixa-h", Math.round(f.getBoundingClientRect().height) + "px");
      if (!lista && t) html.style.setProperty("--topo-h", Math.round(t.getBoundingClientRect().height) + "px");
    }
    mede();
    if ("ResizeObserver" in window) new ResizeObserver(mede).observe(f);
    else window.addEventListener("resize", mede);
    var antes = EP.topoFixo;
    EP.topoFixo = function () { return (antes ? antes() : (document.querySelector("header.topo") || { offsetHeight: 0 }).offsetHeight) + f.offsetHeight; };
  }
  // depois de trocar de mandato: o leitor de tela ouve qual mandato está aberto, e o foco vai para onde a pessoa estava
  function avisaTroca(V) {
    if (!CHEGOU) return;
    var av = document.createElement("p");
    av.className = "sr";
    av.setAttribute("role", "status");
    av.id = "mandato-aviso";
    raiz.insertBefore(av, raiz.firstChild);
    var txt = V ? EP.tr("Agora você está vendo o mandato de ", "You are now viewing the term of ") + EP.trajetoria.cargoLugar(V._md, V._base, MAND.d) + ", " + EP.trajetoria.periodo(V._md) + "." :
      EP.tr("Agora você está vendo o mandato de hoje.", "You are now viewing the current term.");
    setTimeout(function () { av.textContent = txt; }, 700);
    setTimeout(function () {
      var alvo = CHEGOU.foco === "faixa" ? document.getElementById("faixa-mandato-txt") : document.getElementById("mp-campo");
      if (alvo) alvo.focus({ preventScroll: CHEGOU.foco === "faixa" });
    }, 60);
  }

  function semDadosHtml(sec, ic, tit, txt, links) {
    return '<section class="secao-perfil sem-dados-mandato" id="' + sec + '" aria-labelledby="t-' + sec + '"><h2 id="t-' + sec + '"><span class="ic" aria-hidden="true">' + ic + "</span>" + tit + "</h2>" +
      '<div class="vazio"><span class="grande" aria-hidden="true">📭</span><p>' + txt + "</p></div>" +
      (links.length ? '<ul class="links-onde">' + links.join("") + "</ul>" : "") + "</section>";
  }
  // links oficiais de onde ver o que o site não tem daquele mandato
  function linksCasa(V, oque) {
    var md = V._md, m = md.m, l = [], i = V.infoCasa || {}, o = V.onde || {}, cam = o.camara || {}, pre = o.prefeitura || {};
    if (m) {
      if (oque === "propostas") l.push(itemOnde("📜", urlBuscaAutor(m), m.casa === "camara" ? EP.tr("Propostas na busca oficial da Câmara", "Bills on the Chamber's official search") : EP.tr("Propostas no site do Senado", "Bills on the Senate website"), ""));
      l.push(itemOnde("🏛️", urlPaginaCasa(m), m.casa === "camara" ? EP.tr("Página na Câmara dos Deputados", "Page at the Chamber of Deputies") : EP.tr("Página no Senado Federal", "Page at the Federal Senate"), ""));
      return l;
    }
    var c = md.c;
    if (/^(dest|ddist|gov|vgov)$/.test(c) && urlBoa(i.site)) l.push(itemOnde("🏛️", i.site, EP.tr("Site oficial da ", "Official website of the ") + nomeAssembleia(V), ""));
    if (/^(ver|pref|vpref)$/.test(c)) {
      var up = urlPropostasCamara(cam);
      if (up && cam.propostasOnline !== false && oque !== "gastos") l.push(itemOnde("📜", up, EP.tr("Propostas no sistema oficial da Câmara Municipal", "Bills on the City Council's official system"), ""));
      if (urlBoa(i.site) || urlBoa(cam.site)) l.push(itemOnde("🏛️", urlBoa(i.site) || cam.site, EP.tr("Site oficial da Câmara Municipal", "Official website of the City Council"), ""));
      if (/^pref/.test(c) && urlBoa(pre.site)) l.push(itemOnde("🏢", pre.site, EP.tr("Site oficial da prefeitura", "Official website of the city government"), ""));
    }
    if (c === "pres" && oque === "leis") {
      l.push(itemOnde("📜", "https://www4.planalto.gov.br/legislacao/portal-legis/legislacao-1/leis-ordinarias", EP.tr("Leis federais, por ano (Palácio do Planalto)", "Federal laws, by year (Presidential Palace)"), ""));
      l.push(itemOnde("✋", "https://www.congressonacional.leg.br/materias/vetos", EP.tr("Vetos presidenciais (Congresso Nacional)", "Presidential vetoes (National Congress)"), ""));
    }
    if (c === "pres" && oque === "propostas") l.push(itemOnde("📜", "https://dadosabertos.camara.leg.br/swagger/api.html#staticfile", EP.tr("Dados abertos da Câmara: proposições de cada ano", "Chamber of Deputies open data: bills of each year"), ""));
    return l;
  }
  function semPropHtml(V) {
    var md = V._md, c = md.c, m = md.m, z = m && m.fez, txt;
    var casaPt = c === "ver" || /^pref/.test(c) ? "Câmaras Municipais" : "Assembleias Legislativas";
    if (VICE.test(c)) txt = EP.tr("Quem é vice não apresenta projetos como titular: substitui o titular quando ele viaja ou se afasta, e assume o cargo se ele sair de vez.",
      "A vice does not file bills as the office holder: they stand in when the office holder travels or steps away, and take over if they leave for good.");
    else if (m && z && !z.prop) txt = EP.tr("Não apresentou propostas " + (m.casa === "camara" ? "na Câmara" : "no Senado") + " neste mandato, segundo os dados abertos.",
      "Did not file any bills " + (m.casa === "camara" ? "in the Chamber of Deputies" : "in the Senate") + " in this term, according to the open data.");
    else if (m) txt = EP.tr("A lista das propostas deste mandato não está neste site." + (z ? " Pelos dados abertos, foram " + EP.num(z.prop) + " (" + EP.num(z.lei || 0) + " " + ((z.lei || 0) === 1 ? "virou lei" : "viraram lei") + ")." : ""),
      "The list of bills from this term is not on this site." + (z ? " According to the open data, there were " + EP.num(z.prop) + " (" + EP.num(z.lei || 0) + " became law)." : ""));
    else if (c === "pres") txt = EP.tr("O site reúne as propostas que o presidente manda ao Congresso só no mandato de hoje. As deste mandato não estão aqui.",
      "This site gathers the bills the President sends to Congress only for the current term. Those from this term are not here.");
    else if (c === "gov") txt = EP.tr("O site não reúne as propostas que o governo do estado mandou à Assembleia neste mandato.", "This site does not gather the bills the state government sent to the legislature in this term.");
    else if (c === "pref") txt = EP.tr("O site não reúne as propostas que a prefeitura mandou à Câmara Municipal neste mandato.", "This site does not gather the bills the city government sent to the city council in this term.");
    else txt = EP.tr("O site só tem as propostas das " + casaPt + " no mandato de hoje. As deste mandato ficam no site oficial da Casa.",
      "This site only has " + (c === "ver" ? "city council" : "state legislature") + " bills for the current term. Those from this term are on the legislature's official website.");
    return semDadosHtml("propostas", "📜", EP.tr("O que " + ele(V) + " propôs", "What " + ele(V) + " proposed"), txt, VICE.test(c) ? [] : linksCasa(V, "propostas"));
  }
  function semLeisHtml(V) {
    var c = V._md.c;
    var txt = c === "pres" ? EP.tr("O site conta as leis sancionadas e os vetos só do mandato de hoje. Os deste mandato estão nos sites oficiais abaixo.",
        "This site counts the laws signed and the vetoes only for the current term. Those from this term are on the official websites below.") :
      EP.tr("O site conta as leis sancionadas e os vetos só do mandato de hoje, e só onde o governo publica de um jeito que dá para ler.",
        "This site counts the laws signed and the vetoes only for the current term, and only where the government publishes them in a readable way.");
    return semDadosHtml("leis", "✍️", EP.tr("Leis sancionadas e vetos", "Laws signed and vetoes"), txt, linksCasa(V, "leis"));
  }
  function desdeLegislatura() {
    var h = new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10), L = 48;
    while (EP.trajetoria.legDatas(L + 1)[0] <= h) L++;
    return EP.trajetoria.legDatas(L)[0];
  }
  function semVotosHtml(V) {
    var m = V._md.m;
    var txt = m ? EP.tr("O site guarda as votações só de quem está no cargo hoje, " + desdeMes(desdeLegislatura()) + ". As deste mandato estão no site oficial.",
        "This site only keeps the votes of those in office today, " + desdeMes(desdeLegislatura()) + ". Those from this term are on the official website.") :
      EP.tr("O site só tem as votações das " + (V._md.c === "ver" ? "Câmaras Municipais" : "Assembleias Legislativas") + " no mandato de hoje, e só onde a Casa publica o voto de cada um.",
        "This site only has " + (V._md.c === "ver" ? "city council" : "state legislature") + " votes for the current term, and only where the legislature publishes each member's vote.");
    return semDadosHtml("votacoes", "🗳️", EP.tr("Como " + ele(V) + " votou", "How " + ele(V) + " voted"), txt, linksCasa(V, "votacoes"));
  }
  function semGastosHtml(V) {
    var txt = EP.tr("O site mostra os gastos só de quem está no cargo hoje. Os deste mandato estão com a Casa.", "This site only shows the spending of those in office today. Spending from this term is kept by the legislature.");
    return semDadosHtml("gastos", "💰", EP.tr("Gastos do mandato", "Office spending"), txt, linksCasa(V, "gastos"));
  }
  // "Quem é" num mandato antigo: o cargo, o período, como chegou, a eleição, o partido da época e a idade no começo
  function sobreMandatoHtml(V) {
    var md = V._md, it = md.it || {}, M = V._M, d = M.d, g = V.genero, m = md.m;
    var per, fontes = EP.trajetoria.fontes(it, d, V._base);
    if (m && !m.dl && md.f) per = EP.tr("de " + EP.dataLonga(md.i) + " a " + EP.dataLonga(md.f), "from " + EP.dataLonga(md.i) + " to " + EP.dataLonga(md.f));
    else if (m && m.dl) per = EP.tr("legislatura de " + EP.trajetoria.periodo(md), "the " + EP.trajetoria.periodo(md) + " legislature") + "<br><small>" +
      EP.tr("A Câmara não publica o dia em que cada um entrou e saiu nessa legislatura.", "The Chamber does not publish the day each member started and left in that legislature.") + "</small>";
    else if (!md.f) per = EP.tr("desde " + EP.dataLonga(md.i), "since " + EP.dataLonga(md.i));
    else per = esc(EP.trajetoria.periodo(md)) + "<br><small>" + EP.tr("O mandato para o qual " + EP.gen(g, "foi eleito", "foi eleita") + ".", "The term " + ele(V) + " was elected for.") + "</small>";
    var como = null;
    if (md.como === "suplente") como = EP.tr("Era suplente e assumiu a vaga.", "Was an alternate and took the seat.");
    else if (it.k === "c") como = EP.trajetoria.resultado(it, g)[0] + EP.tr(" na eleição de " + it.a, " in the " + it.a + " election");
    else if (it.k === "a" && it.txt) como = esc(EP.tr(it.txt, it.txt_en || it.txt));
    else if (it.k === "m") como = EP.tr("A eleição deste mandato é anterior a 1994, quando começam os dados do TSE usados aqui.", "The election for this term was before 1994, when the TSE data used here begins.");
    var votos = it.k === "c" && it.v != null ? EP.num(it.v) + " " + EP.tr(it.v === 1 ? "voto" : "votos", it.v === 1 ? "vote" : "votes") + (it.t === 2 ? EP.tr(" no 2º turno", " in the runoff") : "") :
      it.k === "c" && it.ch && it.ch.v != null ? EP.num(it.ch.v) + " " + EP.tr("votos (da chapa)", "votes (for the ticket)") : null;
    var idade = null;
    if (V.nascimento && /^\d{4}-\d{2}-\d{2}$/.test(md.i)) {
      var n = V.nascimento, a = +md.i.slice(0, 4) - +n.slice(0, 4) - (md.i.slice(5) < n.slice(5, 10) ? 1 : 0);
      if (a > 0 && a < 120) idade = EP.tr(a + " anos", a + " years old");
    }
    var h = fato("🏛️", EP.tr("Cargo", "Office"), esc(EP.trajetoria.cargoLugar(md, V._base, d))) +
      fato("📅", EP.tr("Período", "Period"), per) +
      fato("🔑", EP.tr("Como chegou ao cargo", "How they took office"), como) +
      fato("🗳️", EP.tr("Votos", "Votes"), votos) +
      fato("🎗️", EP.tr("Partido na época", "Party at the time"), md.p ? EP.pt(esc(md.p)) : null) +
      fato("🎂", EP.tr("Idade no começo do mandato", "Age at the start of the term"), idade);
    var nota = md.aprox && md.f ? '<p class="aviso"><span aria-hidden="true">ℹ️ </span>' + EP.tr(
      "O site não tem o dia em que " + ele(V) + " entrou e saiu deste cargo: o período é o do mandato para o qual " + EP.gen(g, "foi eleito", "foi eleita") + ". A pessoa pode ter saído antes, por exemplo para assumir outro cargo.",
      "This site does not have the day " + ele(V) + " started and left this office: the period is that of the term " + ele(V) + " was elected for. The person may have left earlier, for example to take another office.") + "</p>" : "";
    return '<div class="fatos">' + h + "</div>" + nota +
      (fontes.length ? '<p class="fonte-mandato">' + fonteBtn(fontes, EP.tr("De onde vêm esses dados?", "Where does this data come from?"), EP.tr("o mandato", "the term")) + "</p>" : "") +
      oqueFazHtml(V) + comissoesHtml(V);
  }
  function partesMandato(V) {
    var md = V._md, c = md.c, fontesIt = EP.trajetoria.fontes(md.it || {}, V._M.d, V._base);
    var todas = coletarFontes(fontesIt.concat(V.propostas ? [].concat(V.propostas.fonte || []) : [], V.votacoes ? [].concat(V.votacoes.fonte || []) : [], V.gastos ? [].concat(V.gastos.fonte || []) : []));
    return [["sobre", "👤", EP.tr("Quem é", "About"), sobreMandatoHtml(V)],
      ["trajetoria", "🧭", EP.tr("História", "Career"), '<section class="secao-perfil traj" id="trajetoria"></section>'],
      ["propostas", "📜", EP.tr("O que propôs", "Proposals"), /^(stf|min)$/.test(c) ? "" : V.propostas ? propostasHtml(V) : semPropHtml(V)],
      ["leis", "✍️", EP.tr("Leis e vetos", "Laws and vetoes"), EXEC_T.test(c) ? semLeisHtml(V) : ""],
      ["votacoes", "🗳️", EP.tr("Como votou", "Votes"), LEGIS.test(c) ? (V.votacoes ? votacoesHtml(V) : semVotosHtml(V)) : ""],
      ["gastos", "💰", EP.tr("Gastos", "Spending"), LEGIS.test(c) ? (V.gastos ? gastosHtml(V) : semGastosHtml(V)) : ""],
      ["fontes", "📚", EP.tr("Fontes", "Sources"), todas.length ? '<section class="secao-perfil" id="fontes" aria-labelledby="t-fontes"><h2 id="t-fontes"><span class="ic" aria-hidden="true">📚</span>' +
        EP.tr("Todas as fontes deste mandato", "All the sources for this term") + "</h2>" + EP.fontesHtml(todas) + "</section>" : ""]].filter(function (x) { return x[3]; });
  }
  // a linha do tempo (aba História), com o botão "Ver este mandato" em cada mandato
  function montaTrajetoria(p) {
    if (!EP.trajetoria) return;
    var el = document.getElementById("trajetoria");
    var o = MAND && opcoesMandato().length > 1 ? { mandatos: MAND, sel: MAND.sel, url: function (md) { return urlMandato(md, "sobre"); }, conta: contaProprio } : null;
    EP.trajetoria(el, p._base || p, o);
  }

  // ---------------------------------------------------------------- caminho e abas (ui-r9)
  // Início › (Brasil | estado | estado › cidade) › nome. O caminho segue o cargo (não a página de onde a pessoa veio: para
  // voltar para lá, há o "◀ Voltar" e o Voltar do navegador).
  function trilhaPerfil(p) {
    if (!EP.trilha) return;
    var l = [], lang = EP.en ? "pt-BR" : null;
    var federal = /^(dep|sen|pres|vp|min|stf)$/.test(p.tipo) || /^stf-/.test(id);
    if (federal) l.push({ t: EP.tr("A política do Brasil", "Brazil's politics"), href: "brasil.html" + ({ dep: "#camara", sen: "#senado", stf: "#judiciario" }[p.tipo] || "") });
    if (!federal && p.uf && EP.UFS[p.uf]) l.push({ t: EP.UFS[p.uf], href: "estado.html?uf=" + p.uf });
    if (p.municipio && p.municipio.ibge) l.push({ t: p.municipio.nome || EP.tr("Cidade", "City"), href: "cidade.html?ibge=" + p.municipio.ibge, lang: lang });
    l.push({ t: p.nome, lang: lang });
    EP.trilha(l);
  }
  function montaAbas(p) {
    var nav = raiz.querySelector("nav.atalhos-perfil");
    if (!nav || !EP.abas) return;
    EP.abas.monta({ nav: nav });
  }

  // ---------------------------------------------------------------- montar
  function render(p) {
    P = p;
    var antigo = !!p._md, base = p._base || p;
    var cargo = cargoTexto(p) + (antigo ? ", " + EP.trajetoria.periodo(p._md) : "");
    var t = document.querySelector("title");
    if (t) t.removeAttribute("data-en");
    document.title = p.nome + ": " + cargo + EP.tr(" | Entenda Política", " | Understand Politics");
    var d = document.querySelector('meta[name="description"]');
    if (d) {
      d.removeAttribute("data-en-content");
      d.setAttribute("content", EP.tr("Quem é " + p.nome + " (" + cargo + "), o que propôs, o que foi aprovado e o que virou lei. Tudo com fonte.",
        "Who " + p.nome + " (" + cargo + ") is, what they proposed, what was approved and what became law. Everything with sources."));
    }
    D.canonico({ id: id });
    var o = document.getElementById("onde");
    o.removeAttribute("data-en");
    o.textContent = p.nome;
    if (EP.en) o.setAttribute("lang", "pt-BR");
    ligaVoltar(base);
    trilhaPerfil(base);

    if (p.tipo === "stf" && EP.stf && !antigo) {  // ministros do STF: o perfil vem do js/stf.js
      raiz.innerHTML = EP.stf.perfilHtml(p).replace(/(<\/section>)/, "$1" + (EP.stf.numerosHtml ? EP.stf.numerosHtml(p) : "")) + (EP.trajetoria ? '<section class="secao-perfil traj" id="trajetoria"></section>' : "");  // trajetoria
      // perfil-mandato-r10: o seletor de mandato embaixo do nome (quem já teve outros mandatos, como deputado ou senador)
      var sel = seletorHtml(), h1 = raiz.querySelector(".perfil-topo h1");
      if (sel && h1) { (h1.parentNode.querySelector(".chips") || h1).insertAdjacentHTML("afterend", sel); ligaSeletor(); }
      montaTrajetoria(p);
      avisaTroca(null);
      return;
    }
    var todas = coletarFontes(p), partes;
    if (antigo) partes = partesMandato(p);
    else {
      // ui-r9: o perfil em partes (abas, js/abas.js): "Quem é" (a ficha, contatos, comissões e onde ver mais), "O que propôs",
      // "Leis e vetos", "Como votou", "Gastos" e "Fontes". O topo (foto, nome, partido) fica sempre à vista, em cima das abas.
      // Com uma parte grande só, fica tudo numa página, como antes (sem abas).
      partes = [["sobre", "👤", EP.tr("Quem é", "About"), (p.e26 && EP.eleitos ? EP.eleitos.perfilHtml(p) : "") + fatosHtml(p) + (EP.trajetoria ? "" : anterioresHtml(p)) + contatosHtml(p) + oqueFazHtml(p) + comissoesHtml(p) + avisoEMinisterio(p)],
        // trajetoria (js/trajetoria.js): a história na política; enquanto carrega (ou se não houver dados), "Mandatos anteriores"
        ["trajetoria", "🧭", EP.tr("História", "Career"), EP.trajetoria ? '<section class="secao-perfil traj" id="trajetoria">' + anterioresHtml(p) + "</section>" : ""],
        ["propostas", "📜", EP.tr("O que propôs", "Proposals"), p.propostas ? propostasHtml(p) : ""], ["leis", "✍️", EP.tr("Leis e vetos", "Laws and vetoes"), executivoHtml(p)],
        ["votacoes", "🗳️", EP.tr("Como votou", "Votes"), votacoesHtml(p)], ["gastos", "💰", EP.tr("Gastos", "Spending"), gastosHtml(p)],
        ["fontes", "📚", EP.tr("Fontes", "Sources"), todas.length && p.tipo !== "min" ? '<section class="secao-perfil" id="fontes" aria-labelledby="t-fontes"><h2 id="t-fontes"><span class="ic" aria-hidden="true">📚</span>' + EP.tr("Todas as fontes desta página", "All the sources on this page") + "</h2>" + EP.fontesHtml(todas) +
          (p.atualizado ? '<p class="muted" style="margin-top:10px">' + EP.tr("Dados atualizados em ", "Data updated on ") + EP.data(p.atualizado) + ".</p>" : "") + "</section>" : ""]].filter(function (x) { return x[3]; });
    }
    var grandes = partes.filter(function (x) { return /^(propostas|leis|votacoes|gastos)$/.test(x[0]); }).length;
    // num mandato antigo, as mesmas abas mesmo quando a Casa não publica (a aba diz isso)
    var comAbas = (grandes >= 2 || (antigo && partes.length >= 3)) && !!EP.abas;
    raiz.innerHTML = topoHtml(p) + numerosHtml(p) + (comAbas ? '<nav class="atalhos atalhos-perfil" aria-label="' + EP.tr("Partes deste perfil", "Parts of this profile") + '">' + partes.map(function (x) {
      return '<a class="chip" href="#' + x[0] + '"><span aria-hidden="true">' + x[1] + "</span><span>" + esc(x[2]) + "</span></a>";
    }).join("") + "</nav>" : "") + partes.map(function (x) {
      if (x[0] !== "sobre") return x[3].replace(/^<section class="secao-perfil"(?! id=)/, '<section class="secao-perfil" id="' + x[0] + '"');
      return '<section class="secao-perfil sobre" id="sobre" aria-label="' + esc(EP.tr("Quem é", "About")) + '">' + x[3] + "</section>";
    }).join("");
    raiz.classList.toggle("perfil-abas", comAbas);
    ligaSeletor();
    if (p.propostas && (p.propostas.lista || []).length) {
      redesenhaTudo();
      var bp = document.getElementById("busca-prop");
      if (bp && filtro.q) bp.value = filtro.q;
      if (nProp0) { mostrando = nProp0; nProp0 = null; desenhaLista(); }
    }
    if (document.getElementById("lista-votos")) carregaVotos();
    montaAbas(p);
    if (antigo) poeFaixa(p);
    montaTrajetoria(p);  // trajetoria: a história na política
    avisaTroca(antigo ? p : null);
  }

  // perfil-mandato-r10: "Ver este mandato" (linha do tempo) e "Voltar para hoje" (faixa) guardam para onde vai o foco
  raiz.addEventListener("click", function (e) {
    var a = e.target.closest("a.traj-ver-btn, a.fm-hoje, a.d-tempo-item");
    if (!a || !MAND || e.button || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    if (a.classList.contains("fm-hoje")) { vaiPara(null, "seletor"); return; }
    var md = MAND.lista.filter(function (x) { return x.id === a.getAttribute("data-mandato"); })[0];
    if (md) vaiPara(md, "faixa", "sobre");
  });

  raiz.addEventListener("click", function (e) {
    var t = e.target.closest("[data-papel],[data-status],[data-tema],[data-vcat],#ver-mais-prop,#ver-mais-votos");
    if (!t) return;
    if (t.id === "ver-mais-prop") { var de = mostrando; mostrando += LOTE_PROP; desenhaLista(de); return; }
    if (t.id === "ver-mais-votos") { var dv = mostrandoV; mostrandoV += LOTE_VOTOS; desenhaVotos(dv); return; }
    // tipo de votação: o botão continua no lugar (só muda o aria-pressed), então o foco fica nele
    if (t.hasAttribute("data-vcat")) {
      filtroV = t.getAttribute("data-vcat");
      [].forEach.call(raiz.querySelectorAll("[data-vcat]"), function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-vcat") === filtroV)); });
      mostrandoV = INI_VOTOS;
      desenhaVotos();
      return;
    }
    if (t.hasAttribute("data-papel")) {
      var novo = t.getAttribute("data-papel");
      filtro.papel = filtro.papel === novo ? "todas" : novo;
      filtro.status = ""; filtro.tema = "";
      [].forEach.call(raiz.querySelectorAll("[data-papel]"), function (b) { b.setAttribute("aria-pressed", String(filtro.papel === b.getAttribute("data-papel"))); });
      redesenhaTudo();
      return;
    }
    // os botões de filtro são redesenhados: o foco volta para o mesmo botão
    function redesenhaFiltro(attr, val) {
      desenhaChips();
      mostrando = INI_PROP;
      desenhaLista();
      var b = raiz.querySelector("[" + attr + '="' + (window.CSS && CSS.escape ? CSS.escape(val) : val) + '"]');
      if (b) b.focus();
    }
    if (t.hasAttribute("data-status")) { var s = t.getAttribute("data-status"); filtro.status = filtro.status === s ? "" : s; redesenhaFiltro("data-status", s); return; }
    if (t.hasAttribute("data-tema")) { var tm = t.getAttribute("data-tema"); filtro.tema = filtro.tema === tm ? "" : tm; redesenhaFiltro("data-tema", tm); }
  });
  var tBusca = null;
  raiz.addEventListener("input", function (e) {
    if (e.target.id !== "busca-prop") return;
    clearTimeout(tBusca);
    tBusca = setTimeout(function () { filtro.q = e.target.value; mostrando = INI_PROP; desenhaLista(); }, 200);
  });

  D.rodapeErros(document.getElementById("links-erro"), "Viu algo errado nesta página?", "Did you see something wrong on this page?");
  function erro(tit, txt) {
    raiz.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">🔎</span><h1>' + tit + "</h1><p>" + txt + "</p>" +
      '<p><a class="btn" href="brasil.html">' + EP.tr("Ver a política do Brasil", "See Brazil's politics") + '</a> <a class="btn claro" href="estado.html">' + EP.tr("Ver meu estado", "See the states") + "</a></p></div>";
  }
  if (!id) {
    erro(EP.tr("Faltou dizer quem", "No one was chosen"), EP.tr("Volte e escolha uma pessoa.", "Go back and choose a person."));
    return;
  }
  chegada();
  carregar().then(preparaMandato).then(render).catch(function (err) {
    if (window.console && err && !/não achei|id inválido|^\d{3} /.test(err.message || "")) console.warn(err);
    if (/^e26-/.test(id) && EP.eleitos) { EP.eleitos.semPerfil(raiz); return; }  // eleitos 2026: endereço de antes da posse
    if (err && err.cidade) { semPessoaCidade(err.cidade); return; }  // prefeitos 2026: cargo vago ou não conferido
    erro(EP.tr("Não encontramos essa pessoa", "We could not find this person"),
      EP.tr("Pode ser que ela não esteja mais no cargo, ou que os dados ainda estejam sendo atualizados.", "They may no longer be in office, or the data may still be being updated."));
  });

  // prefeitos 2026 (frente prefeitos-r7): o endereço pref-/vpref- de uma cidade em que o cargo está vago, ou em que quem
  // governa hoje não foi conferido (a pessoa que aparecia deixou a prefeitura para concorrer em 2026): diz isso, com o
  // motivo da ficha da cidade, e leva à página da cidade
  function semPessoaCidade(o) {
    var c = o.c, p = o.p, pref = o.tipo === "pref", lugar = c.nome + " (" + o.uf + ")";
    var tit = pref ? EP.tr("Prefeitura de " + lugar, "Mayor of " + lugar) : EP.tr("Vice-prefeitura de " + lugar, "Vice mayor of " + lugar);
    var txt = p.vago ? EP.tr("O cargo está vago.", "The office is vacant.") + " " + D.traduz(p.txt || p.nota, null, p.txt_en || p.nota_en) :
      D.traduz(p.txt, null, p.txt_en);
    var t = document.querySelector("title");
    if (t) t.removeAttribute("data-en");
    document.title = tit + EP.tr(" | Entenda Política", " | Understand Politics");
    var o2 = document.getElementById("onde");
    if (o2) { o2.removeAttribute("data-en"); o2.textContent = tit; }
    raiz.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">🏢</span><h1>' + esc(tit) + "</h1><p>" + txt + "</p>" +
      ((p.fontes || p.fonte) ? "<p>" + EP.botaoFontes([].concat(p.fontes || p.fonte)) + "</p>" : "") +
      '<p><a class="btn" href="cidade.html?ibge=' + encodeURIComponent(c.ibge) + (EP.en ? "&lang=en" : "") + '">' +
      esc(EP.tr("Ver a política de " + c.nome, "See the politics of " + c.nome)) + "</a></p></div>";
  }
})();
