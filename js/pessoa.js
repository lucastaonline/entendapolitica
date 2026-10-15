/* Perfil de uma pessoa: ficha, propostas, votações, gastos e fontes. */
(function () {
  "use strict";
  var EP = window.EP;
  var esc = EP.esc, md = EP.md;
  var CONFIG = window.EP_CONFIG || {};
  var raiz = document.getElementById("perfil");
  var id = (EP.param("id") || "").trim();
  var CF = { veiculo: "Planalto", titulo: "Constituição Federal de 1988", url: "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm", data: "1988-10-05" };

  var OQUE = {
    dep: "Deputados federais fazem leis para o país todo, votam o orçamento e fiscalizam o governo federal. Cada estado elege um número de deputados de acordo com a sua população.",
    sen: "Senadores representam o seu estado. Eles fazem e revisam leis, aprovam algumas autoridades (como ministros do Supremo) e fiscalizam o governo federal.",
    pres: "O presidente governa o país: comanda os ministérios, propõe leis e medidas provisórias, sanciona ou veta as leis aprovadas pelo Congresso e representa o Brasil no exterior.",
    vp: "O vice-presidente substitui o presidente quando ele viaja ou fica impedido, e assume o cargo se o presidente sair de vez.",
    gov: "O governador comanda o estado: cuida da polícia, das escolas de ensino médio, dos hospitais estaduais e das estradas estaduais, entre outras coisas.",
    vgov: "O vice-governador substitui o governador quando ele viaja ou fica impedido, e assume o cargo se o governador sair de vez.",
    dest: "Deputados estaduais fazem as leis do estado, votam o orçamento do estado e fiscalizam o governador.",
    pref: "O prefeito comanda a cidade: cuida de creches e escolas, postos de saúde, coleta de lixo, ruas e ônibus da cidade, entre outras coisas.",
    vpref: "O vice-prefeito substitui o prefeito quando ele viaja ou fica impedido, e assume o cargo se o prefeito sair de vez.",
    ver: "Vereadores fazem as leis da cidade, votam o orçamento da prefeitura e fiscalizam o prefeito.",
    min: "Ministros são escolhidos pelo presidente para cuidar de uma área do governo federal. Eles não são eleitos."
  };
  var PARTE_ENTENDA = { dep: 4, sen: 4, pres: 4, vp: 4, gov: 4, vgov: 4, dest: 4, pref: 4, vpref: 4, ver: 4, min: 4 };
  var COR_VOTO = { "Sim": "#1f3a5f", "Não": "#e08a00", "Abstenção": "#8a94a3", "Obstrução": "#7c4dbd", "Outro": "#b8ad96" };

  // ---------------------------------------------------------------- carregar
  function deEstado(e, quem, chave) {
    var p = e[chave];
    if (!p) throw new Error("sem " + chave);
    return Object.assign({ id: id, tipo: quem, uf: e.uf, cargo: quem === "gov" ? EP.gen(p.genero, "Governador", "Governadora") : EP.gen(p.genero, "Vice-governador", "Vice-governadora") }, p);
  }
  function carregar() {
    var m;
    if (/^(dep|sen|pres|vp)-[\w-]+$/.test(id)) return EP.json("dados/pessoas/" + id + ".json");
    if ((m = /^(gov|vgov)-([A-Z]{2})$/.exec(id))) {
      return EP.json("dados/estados/" + m[2] + ".json").then(function (e) { return deEstado(e, m[1], m[1] === "gov" ? "governador" : "vice"); });
    }
    if ((m = /^dest-([A-Z]{2})-\w+$/.exec(id))) {
      return EP.json("dados/estados/" + m[1] + ".json").then(function (e) {
        var de = e.deputadosEstaduais || {}, p = (de.membros || []).filter(function (x) { return x.id === id; })[0];
        if (!p) throw new Error("não achei");
        return Object.assign({ tipo: "dest", uf: e.uf, cargo: e.uf === "DF" ? EP.gen(p.genero, "Deputado distrital", "Deputada distrital") : EP.gen(p.genero, "Deputado estadual", "Deputada estadual"),
          avisoLista: de.aviso, fonte: p.fonte || de.fonte }, p);
      });
    }
    if ((m = /^(pref|vpref|ver)-(\d{7})(?:-\w+)?$/.exec(id))) {
      var uf = EP.UF_IBGE[m[2].slice(0, 2)];
      return EP.json("dados/cidades/" + uf + "/" + m[2] + ".json").then(function (c) {
        var p, tipo = m[1];
        if (tipo === "pref") p = c.prefeito;
        else if (tipo === "vpref") p = c.vice;
        else p = ((c.vereadores || {}).membros || []).filter(function (x) { return x.id === id; })[0];
        if (!p) throw new Error("não achei");
        var cargo = tipo === "pref" ? EP.gen(p.genero, "Prefeito", "Prefeita") : tipo === "vpref" ? EP.gen(p.genero, "Vice-prefeito", "Vice-prefeita") : EP.gen(p.genero, "Vereador", "Vereadora");
        return Object.assign({ tipo: tipo, uf: uf, municipio: { ibge: c.ibge, nome: c.nome }, cargo: cargo,
          avisoLista: tipo === "ver" ? (c.vereadores || {}).aviso : c.aviso, fonte: p.fonte || (tipo === "ver" ? (c.vereadores || {}).fonte : c.fonte) }, p);
      });
    }
    if (/^min-/.test(id)) {
      return EP.json("dados/manual/ministros.json").then(function (d) {
        var p = (d.ministerios || []).filter(function (x) { return x.id === id; })[0];
        if (!p) throw new Error("não achei");
        return Object.assign({ tipo: "min", cargo: EP.gen(p.genero, "Ministro", "Ministra") + " · " + p.ministerio }, p);
      });
    }
    return Promise.reject(new Error("id inválido"));
  }

  // ---------------------------------------------------------------- pedaços
  function fato(ic, rot, val, fonte) {
    if (val == null || val === "") return "";
    return '<div class="fato"><span class="f-ic" aria-hidden="true">' + ic + '</span><span class="f-rot">' + esc(rot) + '</span><span class="f-val">' + val + "</span>" + (fonte ? EP.botaoFontes(fonte, "Fonte") : "") + "</div>";
  }
  function onde(p) {
    if (p.tipo === "pres" || p.tipo === "vp" || p.tipo === "min") return "Brasil";
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
      Object.keys(v).forEach(function (k) { if (k !== "lista") anda(v[k]); });
    })(obj);
    return lista;
  }

  // ---------------------------------------------------------------- topo e ficha
  function topoHtml(p) {
    var anos = p.mandato && p.mandato.inicio ? "Mandato: " + p.mandato.inicio.slice(0, 4) + " a " + (p.mandato.fim || "").slice(0, 4) : "";
    var chips = [];
    if (p.partido) chips.push('<span class="chip">🎗️ ' + esc(p.partido) + "</span>");
    if (anos) chips.push('<span class="chip neutro">📅 ' + esc(anos) + "</span>");
    if (p.eleicao2026) chips.push(EP.chip2026(p.eleicao2026, p.genero, true));
    if (p.mandato && p.mandato.obs) chips.push('<span class="chip amarelo">ℹ️ ' + esc(p.mandato.obs) + "</span>");
    if (p.interino) chips.push('<span class="chip amarelo">' + EP.gen(p.genero, "Interino", "Interina") + "</span>");
    return '<section class="perfil-topo"><div class="moldura">' + EP.av(p.foto, p.nome, null, true) + "</div><div>" +
      '<span class="cargo-p">' + esc(p.cargo || "") + (onde(p) ? " · " + esc(onde(p)) : "") + "</span><h1>" + esc(p.nome) + "</h1>" +
      (p.nomeCivil && EP.norm(p.nomeCivil) !== EP.norm(p.nome) ? '<p class="muted" style="margin:-4px 0 8px">Nome completo: ' + esc(p.nomeCivil) + "</p>" : "") +
      '<div class="chips">' + chips.join("") + "</div>" +
      (p.fotoCredito ? '<p class="muted" style="font-size:.72rem;margin:8px 0 0">Foto: ' + esc(p.fotoCredito) + "</p>" : "") + "</div></section>";
  }
  function fatosHtml(p) {
    var idade = EP.idade(p.nascimento);
    var votos = p.eleicao && p.eleicao.votos != null ? EP.num(p.eleicao.votos) + " votos" + (p.eleicao.ano ? " em " + p.eleicao.ano : "") : (p.votos != null ? EP.num(p.votos) + " votos" : null);
    var sit = p.eleicao && p.eleicao.situacao ? p.eleicao.situacao : (p.situacao || p.situacao2022 || null);
    var h = fato("🎂", "Idade", idade != null ? idade + " anos" + (p.nascimento ? " (nasceu em " + EP.dataLonga(p.nascimento) + ")" : "") : null) +
      fato("📍", "Nasceu em", p.naturalidade ? esc(p.naturalidade) : null) +
      fato("🎓", "Escolaridade", p.escolaridade ? esc(p.escolaridade) : null) +
      fato("💼", (p.profissoes || []).length > 1 ? "Profissões" : "Profissão", (p.profissoes || []).length ? esc(p.profissoes.join(", ")) : null) +
      fato("🗳️", "Na eleição", votos ? esc(votos) + (sit ? "<br><small>" + esc(sit) + "</small>" : "") : (sit ? esc(sit) : null), (p.eleicao && p.eleicao.fonte) || null) +
      fato("🏠", "Bens declarados ao TSE", p.bens && p.bens.total != null ? EP.dinheiroCurto(p.bens.total) + (p.bens.ano ? " (em " + p.bens.ano + ")" : "") : null, p.bens && p.bens.fonte) +
      (p.desde ? fato("📅", "No cargo desde", EP.dataLonga(p.desde)) : "") +
      (p.comoAssumiu ? fato("🔑", "Como chegou ao cargo", esc(p.comoAssumiu)) : "");
    return h ? '<div class="fatos">' + h + "</div>" : "";
  }
  function oqueFazHtml(p) {
    var t = OQUE[p.tipo];
    if (!t) return "";
    if (p.tipo === "dest" && p.uf === "DF") t = "Deputados distritais fazem as leis do Distrito Federal, votam o orçamento e fiscalizam o governador.";
    return '<div class="dica-coruja oque-faz"><span class="coruja" aria-hidden="true">🦉</span><div><b>O que faz ' + EP.gen(p.genero, "um ", "uma ") + esc((p.cargo || "").split(" · ")[0].toLowerCase()) + "?</b><p style=\"margin:4px 0 6px\">" + esc(t) + "</p>" +
      '<a class="link-seta" href="entenda.html#parte-' + PARTE_ENTENDA[p.tipo] + '">Entenda os cargos ›</a> ' + EP.botaoFontes([CF], "Fonte") + "</div></div>";
  }

  // ---------------------------------------------------------------- propostas
  var P = null, filtro = { papel: "autor", status: "", tema: "", q: "" }, mostrando = 20;
  function contaPor(lista) {
    var c = { total: lista.length };
    Object.keys(EP.STATUS).forEach(function (s) { c[s] = 0; });
    lista.forEach(function (x) { c[x.status || "outra"] = (c[x.status || "outra"] || 0) + 1; });
    return c;
  }
  function daPapel(lista, papel) { return papel === "todas" ? lista : lista.filter(function (x) { return (x.papel || "coautor") === papel; }); }
  function propostasHtml(p) {
    var pr = p.propostas;
    var lista = pr.lista || [];
    var nAutor = lista.filter(function (x) { return x.papel === "autor"; }).length, nCo = lista.length - nAutor;
    if (!nAutor && nCo) filtro.papel = "coautor";
    if (!lista.length) filtro.papel = "todas";
    var nomeCargo = (p.cargo || "").split(" · ")[0].toLowerCase();
    var h = '<section class="secao-perfil" id="propostas"><h2><span class="ic" aria-hidden="true">📜</span>O que ' + EP.gen(p.genero, "ele", "ela") + " propôs</h2>" +
      '<p class="muted">' + esc(pr.escopo || "") + " " + (pr.fonte ? EP.botaoFontes(pr.fonte) : "") + "</p>";
    if (!lista.length) {
      h += '<div class="vazio"><span class="grande" aria-hidden="true">📭</span>Não encontramos propostas apresentadas nesse período.</div>';
    } else {
      h += '<div class="duas-p"><div>' +
        '<div class="papeis" role="group" aria-label="Escolha o tipo de autoria">' +
        '<button type="button" class="papel-btn" data-papel="autor" aria-pressed="' + (filtro.papel === "autor") + '"><b>' + EP.num(nAutor) + "</b><span>✍️ " + EP.gen(p.genero, "Autor principal", "Autora principal") + "</span><small>" + EP.gen(p.genero, "Ele", "Ela") + " escreveu e foi " + EP.gen(p.genero, "o primeiro", "a primeira") + " a assinar.</small></button>" +
        '<button type="button" class="papel-btn" data-papel="coautor" aria-pressed="' + (filtro.papel === "coautor") + '"><b>' + EP.num(nCo) + "</b><span>🤝 Assinou junto</span><small>Outra pessoa escreveu; " + EP.gen(p.genero, "ele", "ela") + " assinou como " + EP.gen(p.genero, "coautor", "coautora") + ".</small></button></div>" +
        '<div class="funil" id="funil"></div>' +
        '<p class="muted nota-contexto" style="margin-top:10px">🏆 "Virou lei" inclui também decretos legislativos e resoluções, que são outras normas.</p></div>' +
        '<div><div class="status-chips" id="status-chips"></div><div class="temas-chips" id="temas-chips"></div>' +
        '<div class="dica-coruja nota-contexto"><span class="coruja" aria-hidden="true">🦉</span><p>Quantidade não mede qualidade: um projeto pode ser bem simples ou muito grande. E o caminho até virar lei é longo, com muitas votações. <a href="entenda.html#parte-6">Veja como nasce uma lei</a>.</p></div></div></div>' +
        '<div class="busca busca-prop"><input type="search" id="busca-prop" placeholder="Procurar nas propostas (ex.: escola, saúde)" aria-label="Procurar nas propostas" autocomplete="off"></div>' +
        '<p class="contagem" id="contagem-prop" aria-live="polite"></p><ol class="lista-prop" id="lista-prop"></ol><div class="mais-lista" id="mais-prop"></div>';
    }
    if (pr.outros && pr.outros.total) {
      h += '<p class="aviso azul">📨 Além disso, ' + EP.gen(p.genero, "ele", "ela") + " apresentou <b>" + EP.num(pr.outros.total) + "</b> " + esc((pr.outros.txt || "outros documentos").toLowerCase()) + "." +
        (pr.outros.url ? ' <a href="' + esc(pr.outros.url) + '" target="_blank" rel="noopener">Ver a lista oficial ↗</a>' : "") + "</p>";
    }
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
      '<div class="funil-degrau d1"><span class="ic" aria-hidden="true">📝</span><span class="r">' + (lista.length === 1 ? "proposta apresentada" : "propostas apresentadas") + '</span><span class="q">' + EP.num(lista.length) + "</span></div>" +
      '<div class="funil-degrau d2"><span class="ic" aria-hidden="true">✅</span><span class="r">aprovadas em pelo menos uma votação final</span><span class="q">' + EP.num(aprov) + "</span></div>" +
      '<div class="funil-degrau d3"><span class="ic" aria-hidden="true">🏆</span><span class="r">viraram lei</span><span class="q">' + EP.num(c.lei) + "</span></div>";
    if (!EP.reduzido) el.classList.add("anima");
  }
  function desenhaChips() {
    var lista = daPapel(P.propostas.lista || [], filtro.papel), c = contaPor(lista);
    var ordem = ["lei", "aprovada", "andando", "junta", "arquivada", "rejeitada", "retirada", "outra"];
    document.getElementById("status-chips").innerHTML = '<span class="muted" style="width:100%;font-size:.85rem;font-weight:800">Toque para filtrar:</span>' + ordem.filter(function (s) { return c[s]; }).map(function (s) {
      return '<button type="button" data-status="' + s + '" aria-pressed="' + (filtro.status === s) + '">' + EP.carimbo(s, EP.STATUS[s].curto) + '<span class="q">' + EP.num(c[s]) + "</span></button>";
    }).join("");
    var temas = {};
    lista.forEach(function (x) { (x.temas || []).forEach(function (t) { temas[t] = (temas[t] || 0) + 1; }); });
    var top = Object.keys(temas).sort(function (a, b) { return temas[b] - temas[a] || a.localeCompare(b); }).slice(0, 10);
    document.getElementById("temas-chips").innerHTML = top.length ? '<span class="muted" style="width:100%;font-size:.85rem;font-weight:800">Assuntos que mais aparecem:</span>' + top.map(function (t) {
      return '<button type="button" data-tema="' + esc(t) + '" aria-pressed="' + (filtro.tema === t) + '">🏷️ ' + esc(t) + " (" + temas[t] + ")</button>";
    }).join("") : "";
  }
  function propHtml(x) {
    var s = x.status || "outra";
    var casa = /^senado:/.test(x.id) ? "Senado" : "Câmara";
    return '<li class="prop s-' + s + '"><div class="prop-cab"><span class="sigla">' + esc(x.sigla) + "</span>" +
      (x.data ? '<span class="data">' + EP.data(x.data) + "</span>" : "") + EP.carimbo(s) +
      '<span class="papel' + (x.papel === "autor" ? "" : " coautor") + '">' + (x.papel === "autor" ? "✍️ " + EP.gen(P.genero, "Autor principal", "Autora principal") : "🤝 Assinou junto") + "</span></div>" +
      (x.s ? '<p class="simples"><small>Em palavras simples</small>' + esc(x.s) + "</p>" +
        '<div class="oficial"><small>Texto oficial (ementa)</small>' + esc(x.ementa || "") + "</div>" :
        '<p class="simples" style="font-weight:600"><small>Texto oficial (ementa)</small>' + esc(x.ementa || "") + '</p><p class="muted" style="font-size:.8rem;margin:0 0 6px">⏳ A explicação em palavras simples desta proposta está sendo preparada.</p>') +
      '<div class="rodape-prop">' + (x.statusTxt ? '<span class="status-txt">' + esc(x.statusTxt) + "</span>" : "") +
      ((x.temas || []).length ? '<span class="temas">🏷️ ' + esc(x.temas.join(", ")) + "</span>" : "") +
      (x.url ? '<a href="' + esc(x.url) + '" target="_blank" rel="noopener">Ver no site ' + (casa === "Senado" ? "do Senado" : "da Câmara") + " ↗</a>" : "") +
      (x.lei && x.lei.url ? '<a href="' + esc(x.lei.url) + '" target="_blank" rel="noopener">Ler a ' + esc(x.lei.nome || "lei") + " ↗</a>" : "") + "</div></li>";
  }
  function filtradas() {
    var q = EP.norm(filtro.q);
    return daPapel(P.propostas.lista || [], filtro.papel).filter(function (x) {
      return (!filtro.status || x.status === filtro.status) && (!filtro.tema || (x.temas || []).indexOf(filtro.tema) > -1) &&
        (!q || EP.norm((x.s || "") + " " + (x.ementa || "") + " " + (x.sigla || "")).indexOf(q) > -1);
    });
  }
  function desenhaLista() {
    var l = filtradas(), vis = l.slice(0, mostrando);
    document.getElementById("lista-prop").innerHTML = vis.map(propHtml).join("") || '<li class="vazio"><span class="grande" aria-hidden="true">🔍</span>Nenhuma proposta com esses filtros.</li>';
    document.getElementById("contagem-prop").textContent = "Mostrando " + EP.num(vis.length) + " de " + EP.num(l.length) + (l.length === 1 ? " proposta" : " propostas") + ", da mais nova para a mais antiga.";
    document.getElementById("mais-prop").innerHTML = l.length > vis.length ? '<button type="button" class="btn claro" id="ver-mais-prop">Mostrar mais ' + Math.min(20, l.length - vis.length) + " ▾</button>" : "";
  }
  function redesenhaTudo() { desenhaFunil(); desenhaChips(); mostrando = 20; desenhaLista(); }

  // ---------------------------------------------------------------- votações, gastos, comissões
  function votacoesHtml(p) {
    var v = p.votacoes;
    if (!v || !(v.lista || []).length) return "";
    var r = v.resumo || {}, tot = r.total || v.lista.length;
    var chaves = ["Sim", "Não", "Abstenção", "Obstrução", "Outro"].filter(function (k) { return r[k]; });
    var casa = p.tipo === "sen" ? "Senado" : "Câmara";
    return '<section class="secao-perfil" id="votacoes"><h2><span class="ic" aria-hidden="true">🗳️</span>Como ' + EP.gen(p.genero, "ele", "ela") + " votou</h2>" +
      '<p class="muted">' + esc(v.escopo || "") + " " + (v.fonte ? EP.botaoFontes(v.fonte) : "") + "</p>" +
      '<div class="votos-barra" aria-hidden="true">' + chaves.map(function (k) { return '<i style="width:' + (100 * r[k] / tot).toFixed(2) + "%;background:" + COR_VOTO[k] + '"></i>'; }).join("") + "</div>" +
      '<div class="legenda-votos">' + chaves.map(function (k) { return '<span><i style="background:' + COR_VOTO[k] + '"></i>' + k + ": " + EP.num(r[k]) + "</span>"; }).join("") + "<span>Total: " + EP.num(tot) + "</span></div>" +
      '<div class="dica-coruja nota-contexto" style="margin-top:12px"><span class="coruja" aria-hidden="true">🦉</span><p>Votar "Sim" não é bom e votar "Não" não é ruim: depende do que estava sendo votado. Leia cada votação para entender. "Obstrução" é quando o parlamentar tenta atrasar a votação de propósito.</p></div>' +
      '<ul class="lista-votos" id="lista-votos"></ul><div class="mais-lista" id="mais-votos"></div></section>';
  }
  var mostrandoV = 15;
  function desenhaVotos() {
    var el = document.getElementById("lista-votos");
    if (!el) return;
    var l = P.votacoes.lista, vis = l.slice(0, mostrandoV);
    el.innerHTML = vis.map(function (x) {
      var k = COR_VOTO[x.voto] ? x.voto : (/^n[aã]o$/i.test(x.voto || "") ? "Não" : "Outro");
      return '<li><span class="voto-chip" style="--cv:' + COR_VOTO[k] + '">' + esc(x.voto || "—") + '</span><span class="v-txt"><b>' + esc(x.proposta || "Votação") + "</b> · " + EP.data(x.data) +
        (x.resultado ? " · Resultado: " + esc(x.resultado) : "") + "<br>" + esc(x.descricao || "") + (x.url ? ' <a href="' + esc(x.url) + '" target="_blank" rel="noopener">Ver ↗</a>' : "") + "</span></li>";
    }).join("");
    document.getElementById("mais-votos").innerHTML = l.length > vis.length ? '<button type="button" class="btn claro" id="ver-mais-votos">Mostrar mais votações ▾</button>' : "";
  }
  function gastosHtml(p) {
    var g = p.gastos;
    if (!g || g.total == null) return "";
    var max = Math.max.apply(null, (g.porTipo || []).map(function (x) { return x.valor; }).concat([1]));
    var casa = p.tipo === "sen" ? "senador" : "deputado";
    return '<section class="secao-perfil" id="gastos"><h2><span class="ic" aria-hidden="true">💰</span>Gastos da cota do mandato</h2>' +
      '<div class="dica-coruja"><span class="coruja" aria-hidden="true">🦉</span><p>Todo ' + casa + " tem uma verba por mês para pagar despesas do trabalho, como passagens, escritório, combustível e divulgação. <b>Não é salário.</b> O limite muda de estado para estado. Gastar mais ou menos não quer dizer, sozinho, trabalhar mais ou menos.</p></div>" +
      '<div class="grandes-n" style="margin-top:14px"><div class="grande-n"><b>' + EP.dinheiroCurto(g.total) + "</b><span>gastos em " + esc(g.ano) + "</span></div>" +
      (g.mandatoTotal != null ? '<div class="grande-n"><b>' + EP.dinheiroCurto(g.mandatoTotal) + "</b><span>desde fevereiro de 2023</span></div>" : "") + "</div>" +
      ((g.porTipo || []).length ? '<h3 style="margin-top:16px">Com o que gastou em ' + esc(g.ano) + "</h3><div class=\"gastos-lista\">" + g.porTipo.slice(0, 8).map(function (x) {
        return '<div class="gasto"><span>' + esc(x.tipo) + "</span><b>" + EP.dinheiro(x.valor) + '</b><span class="tr"><i style="width:' + (100 * x.valor / max).toFixed(1) + '%"></i></span></div>';
      }).join("") + "</div>" : "") + (g.fonte ? '<p style="margin-top:10px">' + EP.botaoFontes(g.fonte) + "</p>" : "") + "</section>";
  }
  function comissoesHtml(p) {
    if (!(p.comissoes || []).length) return "";
    return '<section class="secao-perfil"><h2><span class="ic" aria-hidden="true">👥</span>Comissões de que participa</h2><p class="muted">Comissões são grupos menores que estudam as propostas de um assunto antes da votação de todos.</p>' +
      '<div class="comissoes">' + p.comissoes.map(function (c) { return '<span class="chip neutro">' + esc(c.nome || c.sigla) + (c.papel ? " · " + esc(c.papel) : "") + "</span>"; }).join("") + "</div></section>";
  }
  function executivoHtml(p) {
    var e = p.executivo;
    if (!e || (e.leisSancionadas == null && e.vetos == null)) return "";
    return '<section class="secao-perfil"><h2><span class="ic" aria-hidden="true">✍️</span>Leis sancionadas e vetos</h2>' +
      '<p class="muted">O Congresso aprova as leis; o presidente assina (sanciona) ou recusa (veta), no todo ou em parte. O Congresso pode derrubar o veto.</p><div class="grandes-n">' +
      (e.leisSancionadas != null ? '<div class="grande-n"><b>' + EP.num(e.leisSancionadas) + "</b><span>leis sancionadas desde 2023</span></div>" : "") +
      (e.vetos != null ? '<div class="grande-n"><b>' + EP.num(e.vetos) + "</b><span>vetos (totais ou parciais) desde 2023</span></div>" : "") +
      "</div>" + (e.fonte ? '<p style="margin-top:10px">' + EP.botaoFontes(e.fonte) + "</p>" : "") + "</section>";
  }
  function emBreveHtml(p) {
    var oque = { dest: "As propostas dos deputados estaduais", ver: "As propostas dos vereadores", gov: "O que o governo do estado fez", vgov: "", pref: "O que a prefeitura fez", vpref: "", min: "" }[p.tipo];
    var h = "";
    if (p.avisoLista) h += '<p class="aviso">ℹ️ ' + esc(p.avisoLista) + "</p>";
    if (oque) h += '<section class="secao-perfil"><h2><span class="ic" aria-hidden="true">🛠️</span>Em breve</h2><p>' + esc(oque) + " ainda não estão aqui. Cada Assembleia, Câmara de Vereadores e governo publica os dados de um jeito diferente, e estamos juntando um por um, sempre com fonte.</p></section>";
    if (p.tipo === "min" && p.fonte) h += '<section class="secao-perfil"><h2><span class="ic" aria-hidden="true">📚</span>Fontes</h2>' + EP.fontesHtml(p.fonte) + "</section>";
    return h;
  }

  // ---------------------------------------------------------------- montar
  function render(p) {
    P = p;
    document.title = p.nome + ": " + (p.cargo || "") + " | Entenda Política";
    var d = document.querySelector('meta[name="description"]');
    if (d) d.setAttribute("content", "Quem é " + p.nome + " (" + (p.cargo || "") + "), o que propôs, o que foi aprovado e o que virou lei. Tudo com fonte.");
    document.getElementById("onde").textContent = "👤 " + p.nome;
    var volta = document.getElementById("voltar-lista");
    if (p.tipo === "dep" || p.tipo === "sen" || p.tipo === "pres" || p.tipo === "vp" || p.tipo === "min") volta.href = "brasil.html#" + ({ dep: "camara", sen: "senado" }[p.tipo] || "executivo");
    else if (p.municipio) volta.href = "estado.html?uf=" + p.uf + "&cidade=" + p.municipio.ibge;
    else volta.href = "estado.html?uf=" + p.uf;

    var todas = coletarFontes(p);
    raiz.innerHTML = topoHtml(p) + fatosHtml(p) + oqueFazHtml(p) +
      (p.propostas ? propostasHtml(p) : "") + executivoHtml(p) + votacoesHtml(p) + gastosHtml(p) + comissoesHtml(p) + emBreveHtml(p) +
      (todas.length && p.tipo !== "min" ? '<section class="secao-perfil"><h2><span class="ic" aria-hidden="true">📚</span>Todas as fontes desta página</h2>' + EP.fontesHtml(todas) +
        (p.atualizado ? '<p class="muted" style="margin-top:10px">Dados atualizados em ' + EP.data(p.atualizado) + ".</p>" : "") + "</section>" : "");
    if (p.propostas && (p.propostas.lista || []).length) redesenhaTudo();
    if (p.votacoes && (p.votacoes.lista || []).length) desenhaVotos();
    if (CONFIG.formularioErros) document.getElementById("links-erro").innerHTML = '🔎 Viu algo errado nesta página? <a href="' + esc(CONFIG.formularioErros) + '" target="_blank" rel="noopener">Avise aqui</a>';
  }

  raiz.addEventListener("click", function (e) {
    var t = e.target.closest("[data-papel],[data-status],[data-tema],#ver-mais-prop,#ver-mais-votos");
    if (!t) return;
    if (t.id === "ver-mais-prop") { mostrando += 20; desenhaLista(); return; }
    if (t.id === "ver-mais-votos") { mostrandoV += 15; desenhaVotos(); return; }
    if (t.hasAttribute("data-papel")) {
      var novo = t.getAttribute("data-papel");
      filtro.papel = filtro.papel === novo ? "todas" : novo;
      filtro.status = ""; filtro.tema = "";
      [].forEach.call(raiz.querySelectorAll("[data-papel]"), function (b) { b.setAttribute("aria-pressed", String(filtro.papel === b.getAttribute("data-papel"))); });
      redesenhaTudo();
      return;
    }
    if (t.hasAttribute("data-status")) { var s = t.getAttribute("data-status"); filtro.status = filtro.status === s ? "" : s; desenhaChips(); mostrando = 20; desenhaLista(); return; }
    if (t.hasAttribute("data-tema")) { var tm = t.getAttribute("data-tema"); filtro.tema = filtro.tema === tm ? "" : tm; desenhaChips(); mostrando = 20; desenhaLista(); }
  });
  var tBusca = null;
  raiz.addEventListener("input", function (e) {
    if (e.target.id !== "busca-prop") return;
    clearTimeout(tBusca);
    tBusca = setTimeout(function () { filtro.q = e.target.value; mostrando = 20; desenhaLista(); }, 180);
  });

  if (!id) {
    raiz.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">🤔</span><h2>Faltou dizer quem</h2><p>Volte e escolha uma pessoa.</p><p><a class="btn" href="brasil.html">Ver a política do Brasil</a></p></div>';
    return;
  }
  carregar().then(render).catch(function () {
    raiz.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">🔎</span><h2>Não encontramos essa pessoa</h2><p>Pode ser que ela não esteja mais no cargo, ou que os dados ainda estejam sendo atualizados.</p><p><a class="btn" href="brasil.html">Ver a política do Brasil</a> <a class="btn claro" href="estado.html">Ver meu estado</a></p></div>';
  });
})();
