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
      return p;
    }, function () { return base; });
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
      Object.keys(v).forEach(function (k) { if (k !== "lista" && k !== "votos") anda(v[k]); });
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
    var chips = [];
    if (p.tipo === "min") { /* ministro não tem partido obrigatório: aparece na ficha */ }
    if (p.partido) chips.push('<span class="chip"><span aria-hidden="true">🎗️ </span><span class="sr">' + EP.tr("Partido: ", "Party: ") + "</span>" +
      (/^sem partido$/i.test(p.partido) ? esc(EP.tr("Sem partido", "No party")) : EP.pt(esc(p.partido))) + "</span>");
    if (anos) chips.push('<span class="chip neutro"><span aria-hidden="true">📅 </span>' + EP.tr("Mandato: ", "Term: ") + esc(anos) + "</span>");
    if (p.eleicao2026) chips.push(EP.chip2026(p.eleicao2026, p.genero, true));
    if (m.obs) chips.push('<span class="chip amarelo"><span aria-hidden="true">ℹ️ </span>' + D.obs(m.obs, m.obs_en) + "</span>");
    if (p.interino) chips.push('<span class="chip amarelo">' + EP.tr(EP.gen(p.genero, "Interino", "Interina"), "Acting") + "</span>");
    // suplente que assumiu a vaga (listas oficiais das Assembleias e Câmaras Municipais)
    if (p.exercicio) chips.push('<span class="chip amarelo"><span aria-hidden="true">🔑 </span>' + esc(EP.tr(p.exercicio, p.exercicio_en || p.exercicio)) + "</span>");
    return '<section class="perfil-topo" aria-labelledby="nome-pessoa"><div class="moldura">' + EP.av(p.foto, p.nome, null, true) + "</div><div>" +
      '<span class="cargo-p">' + cargoHtml(p) + (onde(p) ? " · " + esc(onde(p)) : "") + '</span><h1 id="nome-pessoa">' + EP.pt(esc(p.nome)) + "</h1>" +
      (p.nomeCivil && EP.norm(p.nomeCivil) !== EP.norm(p.nome) ? '<p class="muted" style="margin:-4px 0 8px">' + EP.tr("Nome completo: ", "Full name: ") + esc(p.nomeCivil) + "</p>" : "") +
      (chips.length ? '<div class="chips">' + chips.join("") + "</div>" : "") +
      (p.fotoCredito ? '<p class="muted credito">' + EP.tr("Foto: ", "Photo: ") + (/licença/.test(p.fotoCredito) ? esc(EP.en ? p.fotoCredito.replace("licença", "license") : p.fotoCredito) : EP.pt(esc(p.fotoCredito))) + "</p>" : "") + "</div></section>";
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
    var h = fato("🎂", EP.tr("Idade", "Age"), idade != null ? EP.tr(idade + " anos", idade + " years old") + (p.nascimento ? "<br><small>" + EP.tr("nasceu em ", "born on ") + EP.dataLonga(p.nascimento) + "</small>" : "") : null) +
      fato("📍", EP.tr("Nasceu em", "Born in"), p.naturalidade ? esc(p.naturalidade) : null) +
      fato("🎓", EP.tr("Escolaridade (declarada ao TSE)", "Education (declared to the TSE)"), p.escolaridade ? D.escolaridade(p.escolaridade) : null, p.escolaridadeFonte) +
      fato("💼", oc && oc.ano ? EP.tr("Ocupação declarada ao TSE (" + oc.ano + ")", "Occupation declared to the TSE (" + oc.ano + ")") : EP.tr("Ocupação", "Occupation"),
        oc && oc.txt ? D.profissao(oc.txt) : null, oc && oc.fonte) +
      fato("🗳️", el && el.ano ? EP.tr("Na eleição de " + el.ano, "In the " + el.ano + " election") : EP.tr("Na eleição", "In the election"), votoHtml, el && el.fonte) +
      (outroEleito ? fato("🗳️", EP.tr("Eleito(a) para este cargo em " + noCargo.ano, "Elected to this office in " + noCargo.ano),
        esc(outroEleito.nome) + (outroEleito.partido ? " (" + EP.pt(esc(outroEleito.partido)) + ")" : ""), outroEleito.fontes || outroEleito.fonte) : "") +
      fato("🏠", EP.tr("Bens declarados à Justiça Eleitoral", "Assets declared to the electoral courts"), p.bens && p.bens.total != null ? EP.dinheiroCurto(p.bens.total) +
        (p.bens.ano ? " <small>(" + EP.tr("em ", "in ") + esc(p.bens.ano) + ")</small>" : "") +
        '<br><small class="nota-bens">' + EP.tr("Valor que a própria pessoa declarou ao se candidatar. É uma lista de bens: não mostra dívidas nem renda. Valores de anos diferentes não dão para comparar.",
          "Amount the person declared when running for office. It is a list of assets: it does not show debts or income. Amounts from different years cannot be compared.") + "</small>" : null, p.bens && p.bens.fonte) +
      (p.desde ? fato("📅", EP.tr("No cargo desde", "In office since"), EP.dataLonga(p.desde)) : "") +
      (p.comoAssumiu ? fato("🔑", EP.tr("Como chegou ao cargo", "How they took office"), D.traduz(p.comoAssumiu, null, p.comoAssumiu_en)) : "") +
      (p.nota && p.tipo !== "min" ? fato("📝", EP.tr("Observação", "Note"), D.traduz(p.nota, null, p.nota_en)) : "");
    return h ? '<div class="fatos">' + h + "</div>" : "";
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
    return '<div class="dica-coruja oque-faz"><span class="coruja" aria-hidden="true">🦉</span><div><p style="margin:0"><b>' + esc(pergunta) + "</b></p><p style=\"margin:4px 0 6px\">" + EP.md(EP.tr(o[0], o[1])) + "</p>" +
      '<a class="link-seta" href="entenda.html#parte-4">' + EP.tr("Entenda os cargos", "Learn about each office") + ' <span aria-hidden="true">›</span></a> ' + fonteBtn([CF], EP.tr("Fonte", "Source"), EP.tr("o que faz o cargo", "what the office does")) + "</div></div>";
  }

  // ---------------------------------------------------------------- propostas
  var filtro = { papel: "autor", status: "", tema: "", q: "" }, mostrando = 20;
  function contaPor(lista) {
    var c = { total: lista.length };
    Object.keys(EP.STATUS).forEach(function (s) { c[s] = 0; });
    lista.forEach(function (x) { var s = EP.STATUS[x.status] ? x.status : "outra"; c[s] = (c[s] || 0) + 1; });
    return c;
  }
  function daPapel(lista, papel) { return papel === "todas" ? lista : lista.filter(function (x) { return (x.papel || "coautor") === papel; }); }
  function escopoHtml(p, pr) {
    // deputados e senadores: todas as propostas dos mandatos naquela Casa; diz de quando é a mais antiga
    var anoMin = (pr.lista || []).reduce(function (m, x) { var a = (x.data || "").slice(0, 4); return a && (!m || a < m) ? a : m; }, null);
    var extra = (p.tipo === "dep" || p.tipo === "sen") && anoMin ?
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
  function outrosHtml(p, o) {
    if (!o || !o.total) return "";
    var oque = EP.en ? (o.txt_en || {
      dep: "other documents (requests for information, motions, suggestions to the government and others)",
      sen: "other documents (motions, suggestions, official letters and other requests; these are not bills)",
      pres: "other documents sent to Congress (messages such as nominations of authorities and agreements with other countries, radio and TV license renewals and others)"
    }[p.tipo]) : null;
    var txt = EP.en ? (oque ? esc(oque) : D.ptHtml(o.txt || "")) : esc((o.txt || "outros documentos").toLowerCase());
    return '<p class="aviso azul"><span aria-hidden="true">📨 </span>' + EP.tr("Além disso, " + ele(p) + " apresentou", "Besides that, " + ele(p) + " filed") + " <b>" + EP.num(o.total) + "</b> " + txt + "." +
      (o.url ? " " + linkFora(o.url, EP.tr("Ver a lista oficial", "See the official list"), true) : "") + "</p>";
  }
  function apoiosHtml(p, a) {
    if (!a || !a.total) return "";
    var resto;
    if (EP.en) {
      var n = (/(\d+) assinaturas/.exec(a.txt || "") || [])[1] || "171";
      resto = a.txt_en ? esc(a.txt_en) : esc(Ele(p) + " signed so that someone else's proposal could be filed (a constitutional amendment, PEC, needs " + n + " signatures). Supporting only does not make " + dele(p) + " an author or a co-author.");
    } else {
      var t = String(a.txt || "").replace(/^Assinaturas só de apoio:\s*/i, "");
      resto = esc(t.charAt(0).toUpperCase() + t.slice(1));
    }
    return '<p class="muted apoios" style="font-size:.86rem"><span aria-hidden="true">🖊️ </span>' + EP.tr("Assinaturas só de apoio: ", "Support-only signatures: ") + "<b>" + EP.num(a.total) + "</b>. " + resto + "</p>";
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
    if (!lista.length || (p.tipo === "pres")) filtro.papel = "todas";
    var h = '<section class="secao-perfil" id="propostas" aria-labelledby="t-propostas"><h2 id="t-propostas"><span class="ic" aria-hidden="true">📜</span>' +
      EP.tr("O que " + ele(p) + " propôs", "What " + ele(p) + " proposed") + "</h2>" +
      '<p class="muted">' + escopoHtml(p, pr) + " " + (pr.fonte ? fonteBtn(pr.fonte, null, EP.tr("propostas", "proposals")) : "") + "</p>" + notaPresHtml(pr);
    if (!lista.length) {
      if (p.tipo !== "vp") h += '<div class="vazio"><span class="grande" aria-hidden="true">📭</span>' + EP.tr("Não encontramos propostas apresentadas nesse período.", "We found no proposals filed in this period.") + "</div>";
    } else {
      var temPapel = p.tipo !== "pres";
      var nS = lista.filter(function (x) { return EP.en ? x.s_en : x.s; }).length;
      h += '<div class="nota-ia"><span aria-hidden="true">🤖</span><p>' + EP.tr(
        'As explicações em palavras simples são escritas por <b>inteligência artificial</b> a partir do texto oficial (a ementa), com regras para não puxar para nenhum lado. Como a IA pode errar, o texto oficial aparece sempre embaixo, com o link. <a href="imparcialidade.html#ia">Saiba mais</a>.',
        'The plain-language explanations are written by <b>artificial intelligence</b> from the official summary of each bill (the ementa), following rules so as not to take sides. Since AI can make mistakes, the official text (in Portuguese) always appears below, with a link. <a href="imparcialidade.html#ia">Learn more</a>.') +
        " " + EP.tr("Até agora, <b>" + EP.num(nS) + " de " + EP.num(lista.length) + "</b> propostas desta pessoa têm explicação em palavras simples; as outras mostram só o texto oficial. Elas são preparadas aos poucos, no mesmo ritmo para todo mundo.",
          "So far, <b>" + EP.num(nS) + " of " + EP.num(lista.length) + "</b> of this person's proposals have a plain-language explanation; the others show only the official text. They are being prepared gradually, at the same pace for everyone.") + "</p></div>" +
        '<div class="duas-p"><div>' +
        (temPapel ? '<div class="papeis" role="group" aria-label="' + EP.tr("Escolha o tipo de autoria", "Choose the type of authorship") + '">' +
          '<button type="button" class="papel-btn" data-papel="autor" aria-pressed="' + (filtro.papel === "autor") + '"><b>' + EP.num(nAutor) + '</b><span><span aria-hidden="true">✍️ </span>' +
          EP.tr(EP.gen(p.genero, "Autor principal", "Autora principal"), "Main author") + "</span><small>" +
          EP.tr(EP.gen(p.genero, "Ele", "Ela") + " escreveu e foi " + EP.gen(p.genero, "o primeiro", "a primeira") + " a assinar.", Ele(p) + " wrote it and was the first to sign.") + "</small></button>" +
          '<button type="button" class="papel-btn" data-papel="coautor" aria-pressed="' + (filtro.papel === "coautor") + '"><b>' + EP.num(nCo) + '</b><span><span aria-hidden="true">🤝 </span>' +
          EP.tr("Assinou junto", "Co-signed") + "</span><small>" + EP.tr("Outra pessoa escreveu; " + ele(p) + " assinou como " + EP.gen(p.genero, "coautor", "coautora") + ".",
            "Someone else wrote it; " + ele(p) + " signed as a co-author.") + "</small></button></div>" : "") +
        '<div class="funil" id="funil"></div>' +
        '<p class="muted nota-contexto" style="margin-top:10px"><span aria-hidden="true">📜 </span>' + EP.tr('"Virou lei" inclui também decretos legislativos e resoluções, que são outras normas.',
          '"Became law" also includes legislative decrees and resolutions, which are other kinds of legal rules.') + "</p></div>" +
        '<div><div class="status-chips" id="status-chips" role="group" aria-label="' + EP.tr("Filtrar pela situação", "Filter by status") + '"></div>' +
        '<div class="temas-chips" id="temas-chips" role="group" aria-label="' + EP.tr("Filtrar pelo assunto", "Filter by topic") + '"></div>' +
        '<div class="dica-coruja nota-contexto"><span class="coruja" aria-hidden="true">🦉</span><p>' + EP.tr(
          'Quantidade não mede qualidade: um projeto pode ser bem simples ou muito grande. E o caminho até virar lei é longo, com muitas votações. <a href="entenda.html#parte-6">Veja como nasce uma lei</a>.',
          'Quantity does not measure quality: a bill can be very simple or very big. And the road to becoming law is long, with many votes. <a href="entenda.html#parte-6">See how a law is made</a>.') + "</p></div></div></div>" +
        '<label class="sr" for="busca-prop">' + EP.tr("Procurar nas propostas", "Search the proposals") + "</label>" +
        '<div class="busca busca-prop"><input type="search" id="busca-prop" placeholder="' + EP.tr("Procurar nas propostas (ex.: escola, saúde)", "Search the proposals (e.g. school, health)") + '" autocomplete="off" aria-controls="lista-prop"></div>' +
        '<p class="contagem" id="contagem-prop" aria-live="polite"></p><ol class="lista-prop" id="lista-prop"></ol><div class="mais-lista" id="mais-prop"></div>';
    }
    h += apoiosHtml(p, pr.apoios) + outrosHtml(p, pr.outros);
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
    document.getElementById("status-chips").innerHTML = '<span class="rot-filtro" aria-hidden="true">' + EP.tr("Toque para filtrar:", "Tap to filter:") + "</span>" + ordem.filter(function (s) { return c[s]; }).map(function (s) {
      return '<button type="button" data-status="' + s + '" aria-pressed="' + (filtro.status === s) + '">' + EP.carimbo(s, EP.STATUS[s].curto) + '<span class="q">' + EP.num(c[s]) + "</span></button>";
    }).join("");
    var temas = {};
    lista.forEach(function (x) { (x.temas || []).forEach(function (t) { temas[t] = (temas[t] || 0) + 1; }); });
    var top = Object.keys(temas).sort(function (a, b) { return temas[b] - temas[a] || a.localeCompare(b); }).slice(0, 10);
    document.getElementById("temas-chips").innerHTML = top.length ? '<span class="rot-filtro" aria-hidden="true">' + EP.tr("Assuntos que mais aparecem:", "Most common topics:") + "</span>" + top.map(function (t) {
      return '<button type="button" data-tema="' + esc(t) + '" aria-pressed="' + (filtro.tema === t) + '"><span aria-hidden="true">🏷️ </span>' + esc(EP.tema(t)) + " (" + EP.num(temas[t]) + ")</button>";
    }).join("") : "";
  }
  function propHtml(x, focavel) {
    var s = EP.STATUS[x.status] ? x.status : "outra";
    var ondeLink = /^senado:/.test(x.id || "") ? ["Ver no site do Senado", "See it on the Senate website"] :
      /^camara:/.test(x.id || "") ? ["Ver no site da Câmara", "See it on the Chamber of Deputies website"] :
      P.tipo === "dest" && P.uf === "DF" ? ["Ver no site da Câmara Legislativa", "See it on the Legislative Chamber website"] :
      P.tipo === "dest" ? ["Ver no site da Assembleia", "See it on the state legislature website"] :
      P.tipo === "ver" ? ["Ver no site da Câmara Municipal", "See it on the city council website"] :
      ["Ver no site oficial", "See it on the official website"];
    var simples = EP.en ? x.s_en : x.s;
    var ementa = EP.pt(esc(x.ementa || ""));
    var corpo = simples ?
      '<p class="simples"><span class="rot-texto">' + EP.tr("Em palavras simples (feita por IA)", "In plain words (written by AI)") + "</span>" + esc(simples) + "</p>" +
      '<div class="oficial"><span class="rot-texto">' + EP.tr("Texto oficial (ementa)", "Official text (ementa, in Portuguese)") + "</span>" + ementa + "</div>" :
      '<div class="oficial so-oficial"><span class="rot-texto">' + EP.tr("Texto oficial (ementa)", "Official text (ementa, in Portuguese)") + "</span>" + ementa + "</div>" +
      '<p class="muted preparando"><span aria-hidden="true">⏳ </span>' + EP.tr("A explicação em palavras simples desta proposta está sendo preparada.", "A plain-language explanation is being prepared.") + "</p>";
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
  function redesenhaTudo() { desenhaFunil(); desenhaChips(); mostrando = 20; desenhaLista(); }

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
      (chaves.length ? '<div class="votos-barra" aria-hidden="true">' + chaves.map(function (k) { return '<i style="width:' + (100 * r[k] / tot).toFixed(2) + "%;background:" + COR_VOTO[k] + '"></i>'; }).join("") + "</div>" +
        '<ul class="legenda-votos">' + chaves.map(function (k) { return '<li><i style="background:' + COR_VOTO[k] + '" aria-hidden="true"></i>' + esc(D.nomeVoto(k)) + ": " + EP.num(r[k]) + "</li>"; }).join("") +
        "<li>" + EP.tr("Total: ", "Total: ") + EP.num(tot) + "</li></ul>" : "") +
      (r.Outro ? '<p class="muted" style="font-size:.8rem;margin:6px 0 0">' + EP.tr('"Outro" quer dizer: estava ausente, de licença, em missão oficial ou presidindo a sessão.',
        '"Other" means: absent, on leave, on an official mission or presiding over the session.') + "</p>" : "") +
      '<div class="dica-coruja nota-contexto" style="margin-top:12px"><span class="coruja" aria-hidden="true">🦉</span><p>' + EP.tr(
        'Votar "Sim" não é bom e votar "Não" não é ruim: depende do que estava sendo votado. Leia cada votação para entender. "Obstrução" é um recurso previsto nas regras da Casa: o líder anuncia que o partido está em obstrução, e os parlamentares dele deixam de contar para o número mínimo de presentes, para adiar ou evitar aquela votação.',
        'Voting "Yes" is not good and voting "No" is not bad: it depends on what was being voted on. Read each vote to understand it. "Obstruction" is a tool allowed by the rules: the party leader announces it, and the party\'s members stop counting toward the minimum number of members present, in order to delay or prevent that vote.') + "</p></div>" +
      (EP.en ? '<p class="muted" style="font-size:.85rem;margin:10px 0 0">The descriptions of each vote are official texts in Portuguese.</p>' : "") +
      '<div class="temas-chips" id="filtro-votos" role="group" aria-label="' + EP.tr("Filtrar as votações pelo tipo", "Filter the votes by type") + '" style="margin-top:14px" hidden></div>' +
      '<p class="muted nota-contexto" id="nota-tipos-votos" style="margin:0" hidden><span aria-hidden="true">💬 </span>' + EP.tr(
        "Quando foi publicada, aparece também a orientação do partido " + EP.gen(p.genero, "dele", "dela") + " na época (ou do bloco ou da federação de que o partido fazia parte): o voto que o líder pediu. É só um pedido: cada um decide o próprio voto. Toque numa votação para ver como todos votaram.",
        "When it was published, the orientation of " + (EP.en && p.genero === "F" ? "her" : EP.en && p.genero === "M" ? "his" : "their") + " party at the time (or of the bloc or federation the party belonged to) also appears: the vote the leader asked for. It is only a request: each member decides their own vote. Tap a vote to see how everyone voted.") + "</p>" +
      '<p class="contagem" id="contagem-votos" aria-live="polite"></p>' +
      '<ul class="lista-votos" id="lista-votos"><li class="carregando">' + EP.tr("Carregando as votações…", "Loading the votes…") + '</li></ul><div class="mais-lista" id="mais-votos"></div></section>';
  }
  var VOTOS = null, mostrandoV = 15, filtroV = "";
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
    if ((v.lista || []).length) return Promise.resolve(v.lista);
    if (!(v.votos || []).length || !v.arquivo) return Promise.resolve([]);
    return EP.json(v.arquivo).then(function (arq) {
      var tab = arq.votacoes || {};
      return v.votos.map(function (par) {
        var k = String(par[0]);
        var info = tab[k] || tab["camara-vot:" + k] || tab["senado-vot:" + k] || tab[k.replace(/^(camara|senado)-vot:/, "")] || {};
        return Object.assign({ id: k, voto: par[1], ori: par[2] || null, oriDe: par[3] || null }, info);
      }).sort(function (a, b) { return (b.data || "").localeCompare(a.data || ""); });
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
  function desenhaVotos(focarDe) {
    var el = document.getElementById("lista-votos");
    if (!el || !VOTOS) return;
    var lista = filtroV ? VOTOS.filter(function (x) { return x.categoria === filtroV; }) : VOTOS;
    var vis = lista.slice(0, mostrandoV);
    el.innerHTML = vis.map(function (x, k) {
      var vt = D.voto(x.voto);
      var res = x.resultado ? " · " + EP.tr("Resultado: ", "Result: ") + D.resultado(x.resultado) : "";
      var cat = CAT_VOTO[x.categoria], u = urlVotacao(x.id);
      var tit = "<b>" + (x.proposta ? EP.pt(esc(x.proposta)) : EP.tr("Votação", "Vote")) + "</b>" + (x.data ? "\u00a0·\u00a0" + EP.data(x.data) : "");
      return "<li" + (focarDe != null && k === focarDe ? ' tabindex="-1"' : "") + '><span class="voto-chip" style="--cv:' + (COR_VOTO[vt.cat] || COR_VOTO.Outro) + '"><span class="sr">' + EP.tr("Voto: ", "Vote: ") + "</span>" + esc(vt.curto) + "</span>" +
        '<span class="v-txt">' + (u ? '<a href="' + u + '">' + tit + '<span class="sr"> (' + EP.tr("ver como todos votaram", "see how everyone voted") + ")</span></a>" : tit) + res +
        (cat ? ' <span class="chip neutro" style="font-size:.7rem;padding:1px 8px;white-space:normal"><span aria-hidden="true">' + cat[0] + " </span>" +
          esc(EP.tr(cat[3], cat[4])) + "</span>" : "") +
        (vt.longo ? "<small>" + esc(vt.longo) + "</small>" : "") + oriVotoHtml(x) +
        (x.descricao ? '<span class="desc-voto" style="display:block">' + EP.pt(esc(x.descricao)) + "</span>" : "") +
        (x.url ? linkFora(x.url, EP.tr("Ver no site oficial", "See it on the official website") + '<span class="sr"> (' + esc(x.proposta || "") + ")</span>", true) : "") + "</span></li>";
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
      '<div class="dica-coruja"><span class="coruja" aria-hidden="true">🦉</span><p>' + explica + "</p></div>" +
      '<div class="grandes-n" style="margin-top:14px"><div class="grande-n"><b>' + EP.dinheiroCurto(g.total) + "</b><span>" + rotAno + "</span></div>" +
      (g.mandatoTotal != null ? '<div class="grande-n"><b>' + EP.dinheiroCurto(g.mandatoTotal) + "</b><span>" + desdeMes(g.desde || "2023-02") + "</span></div>" : "") + "</div>" +
      ((g.porTipo || []).length ? '<h3 style="margin-top:16px">' + EP.tr("Com o que gastou em ", "What the money was spent on in ") + esc(g.ano) + '</h3><ul class="gastos-lista" style="list-style:none;padding:0">' + g.porTipo.slice(0, 8).map(function (x) {
        return '<li class="gasto"><span>' + D.gasto(x.tipo) + "</span><b>" + EP.dinheiro(x.valor) + '</b><span class="tr" aria-hidden="true"><i style="width:' + (100 * x.valor / max).toFixed(1) + '%"></i></span></li>';
      }).join("") + "</ul>" : "") + (g.fonte ? '<p style="margin-top:10px">' + fonteBtn(g.fonte, null, EP.tr("gastos", "spending")) + "</p>" : "") + "</section>";
  }
  function comissoesHtml(p) {
    if (!(p.comissoes || []).length) return "";
    return '<section class="secao-perfil" aria-labelledby="t-comissoes"><h2 id="t-comissoes"><span class="ic" aria-hidden="true">👥</span>' + EP.tr("Comissões de que participa", "Committees") + "</h2>" +
      '<p class="muted">' + EP.tr("Comissões são grupos menores que estudam as propostas de um assunto antes da votação de todos.", "Committees are smaller groups that study the proposals on one subject before everyone votes on them.") +
      (EP.en ? " Committee names are official names in Portuguese." : "") + "</p>" +
      '<ul class="comissoes">' + p.comissoes.map(function (c) { return '<li class="chip neutro">' + EP.pt(esc(c.nome || c.sigla)) + (c.papel ? " · " + D.papel(c.papel) : "") + "</li>"; }).join("") + "</ul></section>";
  }
  function executivoHtml(p) {
    var e = p.executivo;
    if (!e || (e.leisSancionadas == null && e.vetos == null)) return "";
    var desde = ((e.periodo && e.periodo.inicio) || "2023").slice(0, 4);
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
        mai(casa[3]) + " passes laws; " + chefe[2] + " signs them (sanction) or rejects them (veto), in whole or in part. " + mai(casa[3]) + " can override a veto.") + '</p><div class="grandes-n">' +
      (e.leisSancionadas != null ? '<div class="grande-n"><b>' + EP.num(e.leisSancionadas) + "</b><span>" + EP.tr("leis sancionadas desde " + desde, "laws signed since " + desde) + "</span></div>" : "") +
      (e.vetos != null ? '<div class="grande-n"><b>' + EP.num(e.vetos) + "</b><span>" + EP.tr("vetos (totais ou parciais) desde " + desde, "vetoes (full or partial) since " + desde) + "</span></div>" : "") +
      "</div>" + '<p class="muted nota-contexto" style="margin-top:10px"><span aria-hidden="true">🦉 </span>' + EP.tr(
        "Quase todo projeto aprovado " + casa[1] + " passa " + chefe[1] + ", venha de quem vier. Por isso, este número mostra o que " + casa[2] + " aprovou e " + chefe[0] + " assinou, e não o que " + chefe[0] + " propôs (isso está em \"O que " + ele(p) + " propôs\"). Vetar também é uma tarefa prevista " + regra[0] + ": o número, sozinho, não diz se as decisões foram boas ou ruins.",
        "Almost every bill passed by " + casa[3] + " goes to " + chefe[2] + ", no matter who proposed it. So this number shows what " + casa[3] + " passed and " + chefe[2] + " signed, not what " + chefe[2] + " proposed (that is under \"What " + ele(p) + " proposed\"). Vetoing is also a task set by " + regra[1] + ": the number alone does not say whether the decisions were good or bad.") + "</p>" +
      (e.fonte ? '<p style="margin-top:10px">' + fonteBtn(e.fonte, null, EP.tr("leis e vetos", "laws and vetoes")) + "</p>" : "") + "</section>";
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
      if (semExec && urlBoa(dio.url)) links.push(itemOnde("📰", dio.url, dio.nome ? (EP.en ? EP.pt(esc(dio.nome)) : esc(dio.nome)) : EP.tr("Diário Oficial", "Official Gazette"),
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
      if (peloHistorico && !mexeu) { e.preventDefault(); history.back(); }
    });
  }

  // ---------------------------------------------------------------- montar
  function render(p) {
    P = p;
    var cargo = cargoTexto(p);
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
    ligaVoltar(p);

    var todas = coletarFontes(p);
    raiz.innerHTML = topoHtml(p) + fatosHtml(p) + anterioresHtml(p) + contatosHtml(p) + oqueFazHtml(p) +
      (p.propostas ? propostasHtml(p) : "") + executivoHtml(p) + votacoesHtml(p) + gastosHtml(p) + comissoesHtml(p) + avisoEMinisterio(p) +
      (todas.length && p.tipo !== "min" ? '<section class="secao-perfil" aria-labelledby="t-fontes"><h2 id="t-fontes"><span class="ic" aria-hidden="true">📚</span>' + EP.tr("Todas as fontes desta página", "All the sources on this page") + "</h2>" + EP.fontesHtml(todas) +
        (p.atualizado ? '<p class="muted" style="margin-top:10px">' + EP.tr("Dados atualizados em ", "Data updated on ") + EP.data(p.atualizado) + ".</p>" : "") + "</section>" : "");
    if (p.propostas && (p.propostas.lista || []).length) redesenhaTudo();
    if (document.getElementById("lista-votos")) carregaVotos();
  }

  raiz.addEventListener("click", function (e) {
    var t = e.target.closest("[data-papel],[data-status],[data-tema],[data-vcat],#ver-mais-prop,#ver-mais-votos");
    if (!t) return;
    if (t.id === "ver-mais-prop") { var de = mostrando; mostrando += 20; desenhaLista(de); return; }
    if (t.id === "ver-mais-votos") { var dv = mostrandoV; mostrandoV += 15; desenhaVotos(dv); return; }
    // tipo de votação: o botão continua no lugar (só muda o aria-pressed), então o foco fica nele
    if (t.hasAttribute("data-vcat")) {
      filtroV = t.getAttribute("data-vcat");
      [].forEach.call(raiz.querySelectorAll("[data-vcat]"), function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-vcat") === filtroV)); });
      mostrandoV = 15;
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
      mostrando = 20;
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
    tBusca = setTimeout(function () { filtro.q = e.target.value; mostrando = 20; desenhaLista(); }, 200);
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
  carregar().then(render).catch(function (err) {
    if (window.console && err && !/não achei|id inválido|^\d{3} /.test(err.message || "")) console.warn(err);
    erro(EP.tr("Não encontramos essa pessoa", "We could not find this person"),
      EP.tr("Pode ser que ela não esteja mais no cargo, ou que os dados ainda estejam sendo atualizados.", "They may no longer be in office, or the data may still be being updated."));
  });
})();
