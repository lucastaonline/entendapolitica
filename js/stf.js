/* Ministros do Supremo Tribunal Federal (STF): a seção da página do Brasil (#judiciario, em brasil.html) e o perfil de
   cada ministro (pessoa.html?id=stf-<slug>, montado aqui e chamado pelo js/pessoa.js). Lê dados/stf.json (scripts/stf.py).
   Regras: a ordem é a oficial do tribunal (presidente, vice e os outros por antiguidade); todo ministro tem os mesmos campos,
   mostrados do mesmo jeito; quem indicou é só um dado de cada cartão; cada bloco tem a sua fonte. */
(function () {
  "use strict";
  var EP = window.EP;
  if (!EP) return;
  var esc = EP.esc;
  var S = (EP.stf = {});
  var ARQ = "dados/stf.json";
  var COR = { sim: "#1f3a5f", nao: "#9a4f00", abst: "#5b6573" };

  S.dados = function () { return EP.json(ARQ); };

  // ---------------------------------------------------------------- textos que se repetem
  function nomeHtml(n) { return EP.pt(esc(n || "")); }
  function ptOficial(t) { return t ? EP.pt(esc(t)) : ""; }
  function lang(url) { return url + (EP.en ? (url.indexOf("?") > -1 ? "&" : "?") + "lang=en" : ""); }
  function novaAba() { return '<span class="sr"> ' + EP.tr("(abre em outra aba)", "(opens in a new tab)") + "</span>"; }
  function linkFora(url, txt) {
    return '<a href="' + esc(url) + '" target="_blank" rel="noopener"' + (EP.en ? ' hreflang="pt-BR"' : "") + ">" + txt + ' <span aria-hidden="true">↗</span>' + novaAba() + "</a>";
  }
  // botão "De onde veio isso?" com o assunto escondido para quem usa leitor de tela
  function fonteBtn(lista, assunto, rotulo) {
    var b = EP.botaoFontes([].concat(lista || []).filter(Boolean), rotulo);
    return b && assunto ? b.replace(/<\/button>$/, '<span class="sr"> (' + esc(assunto) + ")</span></button>") : b;
  }
  function ministroDe(m) { return EP.gen(m.genero, "Ministro", "Ministra"); }
  function cargoTxt(m) { return EP.tr(ministroDe(m) + " do Supremo Tribunal Federal", "Justice of the Federal Supreme Court"); }
  function papelTxt(m) {
    if (m.papel === "presidente") return EP.tr("Presidente do STF", "President of the STF");
    if (m.papel === "vice") return EP.tr("Vice-presidente do STF", "Vice President of the STF");
    return "";
  }
  function turmaTxt(n) { return n === 1 ? EP.tr("1ª Turma", "First Chamber") : n === 2 ? EP.tr("2ª Turma", "Second Chamber") : ""; }
  function turmaPt(n) { return n === 1 ? "Primeira Turma" : "Segunda Turma"; }
  function ano(iso) { return (iso || "").slice(0, 4); }
  function votos(n, sing, plur) { return EP.num(n) + " " + (n === 1 ? sing : plur); }
  function placarTxt(p, ccj) {
    if (!p || p.sim == null) return "";
    var partes = [votos(p.sim, EP.tr("voto sim", "vote in favor"), EP.tr("votos sim", "votes in favor"))];
    if (p.nao != null && !(ccj && p.unanimidade && !p.nao)) partes.push(votos(p.nao, EP.tr("não", "against"), EP.tr("não", "against")));
    if (p.abstencao) partes.push(votos(p.abstencao, EP.tr("abstenção", "abstention"), EP.tr("abstenções", "abstentions")));
    return partes.length > 2 ? partes.slice(0, -1).join(", ") + EP.tr(" e ", " and ") + partes[partes.length - 1] : partes.join(EP.tr(" e ", " and "));
  }
  // barra do placar: só desenho (o texto ao lado diz os números)
  function barra(p) {
    var t = (p.sim || 0) + (p.nao || 0) + (p.abstencao || 0);
    if (!t) return "";
    function seg(n, cor) { return n ? '<i style="width:' + (100 * n / t).toFixed(2) + "%;background:" + cor + '"></i>' : ""; }
    return '<span class="stf-barra" aria-hidden="true">' + seg(p.sim, COR.sim) + seg(p.nao, COR.nao) + seg(p.abstencao, COR.abst) + "</span>";
  }
  function vagaTxt(v) {
    if (!v || !v.nome) return "";
    return v.motivo === "falecimento" ? EP.tr("a vaga de ", "the seat of ") + nomeHtml(v.nome) + esc(EP.tr(", que morreu", ", who died")) :
      EP.tr("a vaga de ", "the seat of ") + nomeHtml(v.nome) + esc(EP.tr(", que se aposentou", ", who retired"));
  }
  function conferidoHtml(d) {
    return d.conferido ? '<p class="muted stf-conf">' + EP.tr("Conferido no site do STF e nos dados abertos do Senado em " + EP.data(d.conferido) + ".",
      "Checked on the STF website and in the Senate's open data on " + EP.data(d.conferido) + ".") + "</p>" : "";
  }
  function itemCorte(d) {
    var l = (d && d.links) || {};
    return '<li><span class="ic-onde" aria-hidden="true">📊</span><span>' + linkFora(l.corteAberta, EP.md(EP.tr("Painéis estatísticos do STF (Corte Aberta)", "STF statistics dashboards ({{Corte Aberta}})"))) +
      "<small>" + EP.tr("Decisões e processos de cada gabinete, com filtros. Funciona aberto no navegador.", "Decisions and cases of each justice's office, with filters. Works in the browser.") + "</small></span></li>";
  }
  function corteAberta(d) {
    var l = (d && d.links) || {};
    return '<ul class="links-onde">' + itemCorte(d) +
      '<li><span class="ic-onde" aria-hidden="true">ℹ️</span><span>' + linkFora(l.corteAbertaSobre, EP.md(EP.tr("O que é o Corte Aberta (STF)", "What {{Corte Aberta}} is (STF)"))) + "</span></li></ul>";
  }

  // ---------------------------------------------------------------- como alguém chega ao STF (seção e perfil)
  function passosHtml(d) {
    var minimo = d.maioriaSenado || 41, idade = d.idadeLimite || 75;
    var p = [
      ["👤", EP.tr("O presidente da República escolhe uma pessoa brasileira de nascimento, com mais de 35 e menos de 70 anos, que saiba muito de Direito e tenha boa reputação (é o que a Constituição pede).",
        "The President of Brazil chooses a person who is Brazilian by birth, older than 35 and younger than 70, with deep legal knowledge and a good reputation (that is what the Constitution requires).")],
      ["🎤", EP.tr("O nome vai para o Senado. Na Comissão de Constituição, Justiça e Cidadania (CCJ), a pessoa responde às perguntas dos senadores, em público (a “sabatina”). Depois, a comissão vota, em segredo.",
        "The name goes to the Senate. At the Constitution, Justice and Citizenship Committee (CCJ), the nominee answers senators' questions in public (a hearing). Then the committee votes, by secret ballot.")],
      ["🗳️", EP.tr("Todos os senadores votam, também em segredo. Para ser aprovada, a pessoa precisa de pelo menos " + minimo + " votos “sim”: mais da metade dos 81 senadores.",
        "The full Senate votes, also by secret ballot. To be approved, the nominee needs at least " + minimo + " votes in favor: more than half of the 81 senators.")],
      ["✍️", EP.tr("Com a aprovação, o presidente assina a nomeação, que sai no Diário Oficial da União, e a pessoa toma posse no STF.",
        "Once approved, the President signs the appointment, which is published in the Official Gazette, and the nominee takes office at the STF.")],
      ["⏳", EP.tr("Ela fica no STF até completar " + idade + " anos: aí a aposentadoria é obrigatória. Também pode se aposentar antes.",
        "The justice stays at the STF until turning " + idade + ": then retirement is mandatory. They may also retire earlier.")]
    ];
    return '<ol class="stf-passos">' + p.map(function (x) {
      return '<li><span class="stf-p-ic" aria-hidden="true">' + x[0] + "</span><span>" + esc(x[1]) + "</span></li>";
    }).join("") + "</ol>";
  }

  // ---------------------------------------------------------------- seção da página do Brasil
  function cartaoHtml(m) {
    var ind = m.indicacao || {}, posse = (m.posse || {}).data, apos = (m.aposentadoria || {}).data;
    var chips = [];
    if (m.papel) chips.push('<span class="chip amarelo"><span aria-hidden="true">⚖️ </span>' + esc(papelTxt(m)) + "</span>");
    if (m.turma) chips.push('<span class="chip">' + esc(turmaTxt(m.turma)) + (m.presideTurma ? esc(EP.tr(" · preside", " · presides")) : "") + "</span>");
    else if (m.papel === "presidente") chips.push('<span class="chip neutro">' + esc(EP.tr("Não fica em Turma", "Not in a Chamber")) + "</span>");
    if (m.decano) chips.push('<span class="chip neutro">' + esc(EP.tr(EP.gen(m.genero, "Decano", "Decana") + ": há mais tempo no STF", "Dean: longest-serving")) + "</span>");
    return '<li><a class="stf-card" href="pessoa.html?id=' + encodeURIComponent(m.id) + '">' + EP.av(m.foto, m.nome) +
      '<span class="stf-c-txt"><b>' + nomeHtml(m.nome) + "</b>" +
      (chips.length ? '<span class="stf-chips">' + chips.join("") + "</span>" : "") +
      '<span class="stf-fatos">' +
      (posse ? "<span>" + EP.tr("No STF desde ", "At the STF since ") + "<b>" + esc(EP.data(posse)) + "</b></span>" : "") +
      (ind.presidente ? "<span>" + EP.tr(EP.gen(m.genero, "Indicado", "Indicada") + " por ", "Nominated by ") + "<b>" + nomeHtml(ind.presidente) + "</b>" +
        (ind.data ? " (" + ano(ind.data) + ")" : "") + "</span>" : "") +
      (apos ? "<span>" + EP.tr("Aposentadoria obrigatória: ", "Mandatory retirement: ") + "<b>" + esc(EP.data(apos)) + "</b>" +
        EP.tr(" (75 anos)", " (age 75)") + "</span>" : "") +
      "</span>" +
      '<span class="ver">' + EP.tr("Ver tudo sobre " + EP.gen(m.genero, "ele", "ela"), "See everything about " + EP.gen(m.genero, "him", "her")) + ' <span aria-hidden="true">›</span></span>' +
      "</span></a></li>";
  }
  function vagaHtml(v, d) {
    var txt = [], f = [].concat(v.fontes || []);
    var quando = v.desde ? esc(EP.tr(" em " + EP.data(v.desde), " on " + EP.data(v.desde))) : "";
    if (v.de) {
      txt.push(esc(EP.tr("Era de ", "It belonged to ")) + nomeHtml(v.de) +
        esc(v.motivo === "falecimento" ? EP.tr(", que morreu", ", who died") : EP.tr(", que se aposentou", ", who retired")) + quando + ".");
    }
    (v.indicacoes || []).forEach(function (s) {
      f = f.concat(s.fontes || []);
      var pl = s.plenario || {}, nome = s.nome ? nomeHtml(s.nome) : esc(EP.tr("uma pessoa", "a nominee"));
      if (pl.resultado === "rejeitada") {
        txt.push(esc(EP.tr("A Presidência da República indicou ", "The President nominated ")) + nome + ". " +
          esc(EP.tr("Em " + EP.data(pl.data) + ", o Senado rejeitou a indicação: " + placarTxt(pl) + ".",
            "On " + EP.data(pl.data) + ", the Senate rejected the nomination: " + placarTxt(pl) + ".")));
      } else if (pl.resultado === "aprovada") {
        txt.push(esc(EP.tr("O Senado aprovou a indicação de ", "The Senate approved the nomination of ")) + nome +
          esc(EP.tr(" em " + EP.data(pl.data) + " (" + placarTxt(pl) + "). Falta a posse.", " on " + EP.data(pl.data) + " (" + placarTxt(pl) + "). The swearing-in has not happened.")));
      } else if (s.tramitando) {
        txt.push(esc(EP.tr("A Presidência da República indicou ", "The President nominated ")) + nome + ". " +
          esc(EP.tr("A indicação chegou ao Senado em " + EP.data(s.chegou) + " e está em análise.", "The nomination reached the Senate on " + EP.data(s.chegou) + " and is under review.")));
      }
    });
    if (!v.pendente && d.conferido) txt.push(esc(EP.tr("Até " + EP.data(d.conferido) + ", o Senado não tinha outra indicação para esta vaga.",
      "As of " + EP.data(d.conferido) + ", the Senate had no other nomination for this seat.")));
    return '<li><div class="stf-card vaga"><span class="stf-cadeira" aria-hidden="true">🪑</span><span class="stf-c-txt"><b>' + esc(EP.tr("Cadeira vazia", "Empty seat")) + "</b>" +
      txt.map(function (t) { return "<span>" + t + "</span>"; }).join("") +
      (f.length ? '<span class="stf-fonte-vaga">' + fonteBtn(f, EP.tr("cadeira vazia", "empty seat")) + "</span>" : "") + "</span></div></li>";
  }
  function presidenciaHtml(d, por) {
    var pr = d.presidencia || {}, p = por[pr.presidente], v = por[pr.vice];
    if (!p) return "";
    function pessoa(m, rot) {
      return m ? '<a class="stf-pres" href="pessoa.html?id=' + encodeURIComponent(m.id) + '">' + EP.av(m.foto, m.nome) + "<span><small>" + esc(rot) + "</small><b>" + nomeHtml(m.nome) + "</b></span></a>" : "";
    }
    return '<div class="stf-presidencia cartao rev">' +
      '<div class="stf-pres-gente">' + pessoa(p, EP.tr("Presidente", "President")) + pessoa(v, EP.tr("Vice-presidente", "Vice President")) + "</div>" +
      "<p>" + nomeHtml(p.nome) + esc(EP.tr(" preside o STF desde " + EP.dataLonga(pr.desde) + (pr.periodo ? ", no período " + pr.periodo : "") + ".",
        " has presided over the STF since " + EP.dataLonga(pr.desde) + (pr.periodo ? ", for the " + pr.periodo + " term" : "") + ".")) + " " +
      esc(EP.tr("Os próprios ministros escolhem o presidente e o vice, para " + (pr.anos || 2) + " anos, sem reeleição para o período seguinte.",
        "The justices themselves choose the President and the Vice President of the Court, for " + (pr.anos || 2) + " years, with no re-election for the next term.")) + "</p>" +
      "<p>" + fonteBtn(pr.fontes, EP.tr("presidência do STF", "presidency of the STF")) + "</p></div>";
  }
  function turmasHtml(d, por) {
    var t = d.turmas || [];
    if (!t.length) return "";
    return '<h3 class="sub rev" id="stf-turmas"><span aria-hidden="true">👥 </span>' + EP.tr("As Turmas", "The Chambers") + "</h3>" +
      '<p class="muted">' + esc(EP.tr("O STF julga de dois jeitos: no Plenário, com todos os ministros juntos, e em duas Turmas, com " + (d.cadeirasTurma || 5) + " ministros cada. Quem preside o STF não fica em nenhuma Turma.",
        "The STF decides cases in two ways: in the Plenary, with all the justices together, and in two Chambers, with " + (d.cadeirasTurma || 5) + " justices each. The President of the STF is not in any Chamber.")) + "</p>" +
      '<div class="stf-turmas">' + t.map(function (x) {
        var vagas = (x.cadeiras || 5) - (x.membros || []).length;
        return '<section class="stf-turma cartao rev" aria-labelledby="t-turma-' + x.numero + '"><h4 id="t-turma-' + x.numero + '">' + esc(turmaTxt(x.numero)) +
          (EP.en ? ' <small lang="pt-BR">(' + esc(turmaPt(x.numero)) + ")</small>" : "") + "</h4>" +
          '<p class="muted">' + esc(EP.tr(EP.num((x.membros || []).length) + " de " + (x.cadeiras || 5) + " cadeiras" + (vagas > 0 ? " (" + EP.plural(vagas, "vaga aberta", "vagas abertas") + ")" : ""),
            EP.num((x.membros || []).length) + " of " + (x.cadeiras || 5) + " seats" + (vagas > 0 ? " (" + EP.plural(vagas, "empty seat", "empty seats") + ")" : ""))) + "</p>" +
          "<ul>" + (x.membros || []).map(function (id) {
            var m = por[id];
            return m ? '<li><a href="pessoa.html?id=' + encodeURIComponent(m.id) + '">' + nomeHtml(m.nome) + "</a>" +
              (m.presideTurma ? ' <span class="chip">' + esc(EP.tr("preside a Turma", "presides")) + "</span>" : "") + "</li>" : "";
          }).join("") + "</ul></section>";
      }).join("") + "</div>" +
      "<p>" + fonteBtn(d.fonteTurmas, EP.tr("Turmas", "Chambers")) + "</p>";
  }
  function trabalhoHtml(d) {
    var de = d.decisoes;
    return '<h3 class="sub rev" id="stf-trabalho"><span aria-hidden="true">📊 </span>' + EP.tr("O que o STF publica sobre o trabalho dos ministros", "What the STF publishes about the justices' work") + "</h3>" +
      '<div class="cartao rev stf-trabalho">' +
      (de ? "<p>" + esc(EP.tr("A página oficial do STF mostra o total do tribunal: " + EP.num(de.total) + " decisões em " + de.ano + ".",
        "The STF's official page shows the total for the whole court: " + EP.num(de.total) + " decisions in " + de.ano + ".")) + " " + fonteBtn(de.fonte, EP.tr("decisões do STF", "STF decisions")) + "</p>" : "") +
      "<p>" + EP.md(EP.tr("Os números de cada gabinete (as decisões e os processos de cada ministro) estão nos painéis do Corte Aberta, do próprio STF. Os painéis só funcionam abertos no navegador e não têm um arquivo de dados com endereço fixo que este site consiga ler e conferir. Por isso, os números de cada gabinete não estão copiados aqui: o link leva direto para lá.",
        "The numbers for each justice's office (each justice's decisions and cases) are on the STF's own dashboards, called {{Corte Aberta}}. The dashboards only work when opened in a browser and have no data file at a fixed address that this site could read and check. That is why the numbers for each office are not copied here: the link goes straight there.")) + "</p>" +
      '<p class="muted">' + esc(EP.tr("Contar decisões não mostra se elas são boas ou ruins: os casos são muito diferentes uns dos outros.",
        "Counting decisions does not show whether they are good or bad: cases are very different from one another.")) + "</p>" +
      corteAberta(d) + "</div>";
  }
  function secao(el, d) {
    var ms = d.ministros || [], por = {};
    ms.forEach(function (m) { por[m.id] = m; });
    var vagas = d.vagas || [], cad = d.cadeiras || 11;
    el.innerHTML =
      '<h3 class="sub rev" id="stf-como"><span aria-hidden="true">🪜 </span>' + EP.tr("Como alguém chega ao STF", "How someone gets to the STF") + "</h3>" +
      '<p class="muted">' + esc(EP.tr("Ninguém é eleito para o STF. Os juízes do país, em geral, entram por concurso; os " + cad + " ministros do STF são escolhidos assim:",
        "No one is elected to the STF. Most judges in Brazil get their jobs through a public exam; the " + cad + " justices of the STF are chosen like this:")) + "</p>" +
      passosHtml(d) + "<p>" + fonteBtn((d.regras || {}).fontes, EP.tr("como alguém chega ao STF", "how someone gets to the STF"), EP.tr("De onde vêm essas regras?", "Where do these rules come from?")) + "</p>" +
      '<h3 class="sub rev" id="stf-preside"><span aria-hidden="true">🏛️ </span>' + EP.tr("Quem preside o tribunal", "Who presides over the court") + "</h3>" +
      presidenciaHtml(d, por) +
      '<h3 class="sub rev" id="stf-ministros"><span aria-hidden="true">⚖️ </span>' + EP.tr("Os ministros", "The justices") + " <small>(" +
      esc(EP.tr(ms.length + " de " + cad + " cadeiras", ms.length + " of " + cad + " seats")) + ")</small></h3>" +
      '<p class="muted">' + esc(EP.tr("Na ordem oficial do STF: o presidente, o vice-presidente e os outros do mais antigo para o mais novo no tribunal (quem tomou posse antes vem primeiro). Quem indicou cada um é só um dado do cartão: o site não agrupa ninguém por isso.",
        "In the STF's official order: the President, the Vice President and then the others from the longest-serving to the newest (whoever took office first comes first). Who nominated each justice is just one fact on the card: the site does not group anyone by it.")) + "</p>" +
      '<ul class="stf-grade">' + ms.map(cartaoHtml).join("") + vagas.map(function (v) { return vagaHtml(v, d); }).join("") + "</ul>" +
      "<p>" + fonteBtn(d.fontes, EP.tr("lista dos ministros", "list of justices"), EP.tr("De onde vem esta lista?", "Where does this list come from?")) + "</p>" +
      turmasHtml(d, por) + trabalhoHtml(d) + conferidoHtml(d);
    EP.revelar(el);
  }
  // mandato que já acabou (brasil.html?mandato=2019): a composição do STF não muda junto com os mandatos; só as regras
  function secaoPassado(el, d) {
    el.innerHTML = '<h3 class="sub" id="stf-como"><span aria-hidden="true">🪜 </span>' + EP.tr("Como alguém chega ao STF", "How someone gets to the STF") + "</h3>" +
      passosHtml(d) + "<p>" + fonteBtn((d.regras || {}).fontes, EP.tr("como alguém chega ao STF", "how someone gets to the STF"), EP.tr("De onde vêm essas regras?", "Where do these rules come from?")) + "</p>" +
      '<p class="aviso azul"><span aria-hidden="true">ℹ️ </span>' + esc(EP.tr("Os ministros do STF não mudam junto com o presidente e o Congresso: cada um fica até se aposentar. Por isso esta página mostra só as regras; os ministros de hoje estão na página de hoje.",
        "STF justices do not change along with the President and Congress: each one stays until retiring. That is why this page only shows the rules; today's justices are on today's page.")) +
      ' <a href="' + esc(lang("brasil.html")) + '#judiciario">' + EP.tr("Ver os ministros de hoje", "See today's justices") + "</a></p>";
  }

  // ---------------------------------------------------------------- perfil (pessoa.html?id=stf-...)
  S.carregar = function (id) {
    return S.dados().then(function (d) {
      var m = (d.ministros || []).filter(function (x) { return x.id === id; })[0];
      if (!m) throw new Error("não achei");
      // "cargo" no idioma da página: é o que o pessoa.js põe no título e no topo; "volta": sem pista de onde a pessoa veio, o
      // botão Voltar leva à seção do STF na página do Brasil
      return Object.assign({ tipo: "stf", _stf: d, _m: m }, m, { cargo: cargoTxt(m), fonte: null, fontes: m.fontes,
        volta: { pagina: "brasil.html", secao: "judiciario", id: id } });
    });
  };
  function fato(ic, rot, val, fontes, assunto) {
    if (val == null || val === "") return "";
    return '<div class="fato"><span class="f-ic" aria-hidden="true">' + ic + '</span><span class="f-rot">' + esc(rot) + '</span><span class="f-val">' + val + "</span>" +
      (fontes ? fonteBtn(fontes, assunto || rot, EP.tr("Fonte", "Source")) : "") + "</div>";
  }
  function passo(ic, titulo, data, corpo, fontes, assunto) {
    return '<li><span class="stf-l-ic" aria-hidden="true">' + ic + '</span><div><h3>' + esc(titulo) + (data ? ' <small>' + esc(EP.data(data)) + "</small>" : "") + "</h3>" + corpo +
      (fontes && fontes.length ? "<p>" + fonteBtn(fontes, assunto || titulo) + "</p>" : "") + "</div></li>";
  }
  function linhaHtml(m, d) {
    var ind = m.indicacao || {}, s = m.senado || {}, c = s.ccj || {}, pl = s.plenario || {}, no = m.nomeacao || {}, po = m.posse || {};
    var nome = nomeHtml(m.nome), h = "";
    // 1. indicação
    var vg = vagaTxt(ind.vaga);
    h += passo("📨", EP.tr("Indicação", "Nomination"), ind.data,
      "<p>" + EP.tr(EP.gen(ind.presidenteGenero, "O presidente", "A presidente") + " da República " + nomeHtml(ind.presidente) + " mandou ao Senado o nome de " + nome + (vg ? ", para " + vg : "") + ".",
        "President " + nomeHtml(ind.presidente) + " sent the name of " + nome + " to the Senate" + (vg ? ", for " + vg : "") + ".") + "</p>" +
      (ind.mensagem ? '<p class="muted">' + EP.tr("Documento: ", "Document: ") + ptOficial(ind.mensagem) + (ind.dou ? " (" + ptOficial(ind.dou) + ")" : "") + "</p>" : ""),
      ind.fontes, EP.tr("indicação", "nomination"));
    // 2. CCJ
    if (c.sim != null) {
      h += passo("🎤", EP.tr("Sabatina na CCJ do Senado", "Senate committee hearing (CCJ)"), c.data,
        "<p>" + esc(EP.tr("A Comissão de Constituição, Justiça e Cidadania (CCJ) ouviu " + EP.gen(m.genero, "o indicado", "a indicada") + " em público e aprovou o nome em votação secreta" +
          (c.unanimidade ? ", sem nenhum voto contra: " : ": ") + placarTxt(c, true) + ".",
          "The Constitution, Justice and Citizenship Committee (CCJ) questioned the nominee in public and approved the name by secret ballot" +
          (c.unanimidade ? ", with no votes against: " : ": ") + placarTxt(c, true) + ".")) + "</p>", s.fontes, EP.tr("votação na CCJ", "committee vote"));
    }
    // 3. Plenário do Senado
    if (pl.sim != null) {
      h += passo("🗳️", EP.tr("Votação no Plenário do Senado", "Vote in the full Senate"), pl.data,
        '<p class="stf-placar">' + barra(pl) + "<span>" + esc(EP.tr((pl.resultado === "rejeitada" ? "Rejeitada" : "Aprovada") + " em votação secreta: " + placarTxt(pl) +
          (pl.total ? " (" + EP.num(pl.total) + " votos ao todo)" : "") + ".",
          (pl.resultado === "rejeitada" ? "Rejected" : "Approved") + " by secret ballot: " + placarTxt(pl) + (pl.total ? " (" + EP.num(pl.total) + " votes in all)" : "") + ".")) + "</span></p>" +
        '<p class="muted">' + esc(EP.tr("Eram precisos pelo menos " + (s.minimoSim || d.maioriaSenado || 41) + " votos sim (mais da metade dos 81 senadores). Como o voto é secreto, não se sabe como cada senador votou.",
          "At least " + (s.minimoSim || d.maioriaSenado || 41) + " votes in favor were needed (more than half of the 81 senators). Since the ballot is secret, how each senator voted is not known.")) + "</p>" +
        (s.materia ? '<p class="muted">' + EP.tr("No Senado: ", "In the Senate: ") + ptOficial(s.materia) + (s.url ? " · " + linkFora(s.url, EP.tr("ver a tramitação", "see the official record")) : "") + "</p>" : ""),
        s.fontes, EP.tr("votação no Plenário do Senado", "full Senate vote"));
    }
    // 4. nomeação (o decreto às vezes é assinado por quem está no exercício da Presidência: o texto não diz quem assinou)
    if (no.data) {
      h += passo("✍️", EP.tr("Nomeação", "Appointment"), no.data,
        "<p>" + esc(EP.tr("Saiu o decreto de nomeação" + (no.douData ? ", publicado no Diário Oficial da União em " + EP.data(no.douData) : "") +
          (no.aPartirDe ? ", valendo a partir de " + EP.data(no.aPartirDe) : "") + ".",
          "The appointment decree was issued" + (no.douData ? " and published in the Official Gazette on " + EP.data(no.douData) : "") +
          (no.aPartirDe ? ", effective " + EP.data(no.aPartirDe) : "") + ".")) + "</p>" +
        (no.decreto ? '<p class="muted">' + EP.tr("Documento: ", "Document: ") + ptOficial(no.decreto) + (no.dou ? " (" + ptOficial(no.dou) + ")" : "") + "</p>" : ""),
        no.fontes, EP.tr("nomeação", "appointment"));
    }
    // 5. posse
    if (po.data) {
      h += passo("🏛️", EP.tr("Posse no STF", "Swearing-in at the STF"), po.data,
        "<p>" + esc(EP.tr("Tomou posse como " + ministroDe(m).toLowerCase() + " do STF.", "Took office as a justice of the STF.")) + "</p>",
        po.fontes, EP.tr("posse", "swearing-in"));
    }
    return '<section class="secao-perfil" id="como-chegou" aria-labelledby="t-como-chegou"><h2 id="t-como-chegou"><span class="ic" aria-hidden="true">🪜</span>' +
      EP.tr("Como " + EP.gen(m.genero, "ele", "ela") + " chegou ao STF", "How " + EP.gen(m.genero, "he", "she") + " got to the STF") + "</h2>" +
      '<ol class="stf-linha">' + h + "</ol></section>";
  }
  function ondeHtml(m, d) {
    var l = m.links || {}, links = [];
    function item(ic, url, txt, desc) {
      return url ? '<li><span class="ic-onde" aria-hidden="true">' + ic + "</span><span>" + linkFora(url, txt) + (desc ? "<small>" + desc + "</small>" : "") + "</span></li>" : "";
    }
    links.push(item("🏛️", l.gabinete, EP.tr("Página do gabinete no STF", "The justice's office page at the STF"), EP.tr("Quem trabalha no gabinete e como pedir uma audiência.", "Who works in the office and how to request a meeting.")));
    links.push(item("📁", l.pasta, EP.tr("Pasta " + EP.gen(m.genero, "do ministro", "da ministra") + " na Biblioteca do STF", "The justice's file at the STF Library"), EP.tr("Datas, documentos, discursos, livros e artigos.", "Dates, documents, speeches, books and articles.")));
    links.push(item("📄", l.curriculo, EP.tr("Currículo e biografia (Biblioteca do STF)", "Résumé and biography (STF Library)"), EP.tr("Os currículos oficiais, inclusive o que foi mandado ao Senado.", "The official résumés, including the one sent to the Senate.")));
    links.push(itemCorte(d));
    return '<section class="secao-perfil onde-ver" aria-labelledby="t-onde"><h2 id="t-onde"><span class="ic" aria-hidden="true">🔎</span>' + EP.tr("Onde ver mais", "Where to find more") + "</h2>" +
      "<p>" + esc(EP.tr("Duas coisas não estão neste site, do mesmo jeito para todos os ministros:", "Two things are not on this site, in the same way for every justice:")) + "</p>" +
      '<ul class="notas-casa">' +
      "<li>" + EP.md(EP.tr("Os números do gabinete (decisões e processos): o STF publica esses números nos painéis do Corte Aberta, que só funcionam abertos no navegador, sem um arquivo de dados com endereço fixo que este site consiga ler e conferir.",
        "The office's numbers (decisions and cases): the STF publishes them on its {{Corte Aberta}} dashboards, which only work in a browser, with no data file at a fixed address that this site could read and check.")) + "</li>" +
      "<li>" + esc(EP.tr("Um resumo da carreira antes do STF: o STF publica a biografia em texto só de alguns ministros, e os currículos de cada um estão em documentos diferentes. Para tratar todos do mesmo jeito, o site não resume a carreira de ninguém e mostra o link dos currículos oficiais.",
        "A summary of the career before the STF: the STF publishes a biography in text only for some justices, and each one's résumés are in different documents. To treat everyone the same way, the site does not summarize anyone's career and links to the official résumés instead.")) + "</li></ul>" +
      '<ul class="links-onde">' + links.join("") + "</ul>" +
      '<p class="muted" style="margin-top:8px;font-size:.88rem">' + EP.tr("Contar decisões não mostra se elas são boas ou ruins: os casos são muito diferentes uns dos outros.",
        "Counting decisions does not show whether they are good or bad: cases are very different from one another.") + "</p></section>";
  }
  function todasFontes(p, d) {
    var vistas = {}, lista = [];
    (function anda(v) {
      if (!v || typeof v !== "object") return;
      if (Array.isArray(v)) { v.forEach(anda); return; }
      if (v.url && (v.veiculo || v.titulo)) { if (!vistas[v.url]) { vistas[v.url] = 1; lista.push(v); } return; }
      Object.keys(v).forEach(function (k) { if (k.charAt(0) !== "_") anda(v[k]); });
    })([p._m, fontesPresidencia(p, d), d.fonteTurmas, (d.regras || {}).fontes]);
    return lista;
  }
  // as fontes da presidência só entram no perfil de quem preside ou é vice
  function fontesPresidencia(p, d) { return p.papel === "presidente" || p.papel === "vice" ? (d.presidencia || {}).fontes : null; }
  S.perfilHtml = function (p) {
    var d = p._stf || {}, m = p._m || p, idade = EP.idade(m.nascimento), apos = m.aposentadoria || {}, ind = m.indicacao || {};
    var meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute("content", EP.tr("Quem é " + m.nome + ", " + cargoTxt(m).toLowerCase() + ": quem indicou, como o Senado votou, quando tomou posse e até quando pode ficar. Tudo com fonte oficial.",
      "Who " + m.nome + " is (" + cargoTxt(m) + "): who nominated them, how the Senate voted, when they took office and how long they can stay. Everything with official sources."));
    var chips = [];
    if (m.papel) chips.push('<span class="chip amarelo"><span aria-hidden="true">⚖️ </span>' + esc(papelTxt(m)) + "</span>");
    if (m.turma) chips.push('<span class="chip"><span aria-hidden="true">👥 </span>' + esc(turmaTxt(m.turma)) + (m.presideTurma ? esc(EP.tr(" · preside a Turma", " · presides over it")) : "") + "</span>");
    if (m.decano) chips.push('<span class="chip neutro">' + esc(EP.tr(EP.gen(m.genero, "Decano", "Decana") + ": há mais tempo no STF", "Dean: longest-serving justice")) + "</span>");
    if ((m.posse || {}).data) chips.push('<span class="chip neutro"><span aria-hidden="true">📅 </span>' + esc(EP.tr("No STF desde " + ano(m.posse.data), "At the STF since " + ano(m.posse.data))) + "</span>");
    var topo = '<section class="perfil-topo" aria-labelledby="nome-pessoa"><div class="moldura">' + EP.av(m.foto, m.nome, null, true) + "</div><div>" +
      '<span class="cargo-p">' + esc(cargoTxt(m)) + '</span><h1 id="nome-pessoa">' + nomeHtml(m.nome) + "</h1>" +
      (m.nomeCivil && EP.norm(m.nomeCivil) !== EP.norm(m.nome) ? '<p class="muted" style="margin:-4px 0 8px">' + EP.tr("Nome completo: ", "Full name: ") + nomeHtml(m.nomeCivil) + "</p>" : "") +
      '<div class="chips">' + chips.join("") + "</div>" +
      (m.fotoCredito ? '<p class="muted credito">' + EP.tr("Foto: ", "Photo: ") + EP.pt(esc(m.fotoCredito)) + "</p>" : "") + "</div></section>";
    var turma = m.turma ? esc(turmaTxt(m.turma)) + (m.presideTurma ? "<br><small>" + esc(EP.tr("preside a Turma", "presides over it")) + "</small>" : "") :
      m.papel === "presidente" ? esc(EP.tr("Nenhuma", "None")) + "<br><small>" + esc(EP.tr("quem preside o STF não fica em Turma", "the President of the STF is not in a Chamber")) + "</small>" : null;
    var fatos = '<div class="fatos">' +
      fato("🎂", EP.tr("Idade", "Age"), idade != null ? esc(EP.tr(idade + " anos", idade + " years old")) + (m.nascimento ? "<br><small>" + esc(EP.tr("nasceu em ", "born on ") + EP.dataLonga(m.nascimento)) + "</small>" : "") : null, m.fontes && [m.fontes[0]]) +
      fato("📍", EP.tr("Nasceu em", "Born in"), m.naturalidade ? EP.pt(esc(m.naturalidade)) : null) +
      fato("🏛️", EP.tr("No STF desde", "At the STF since"), (m.posse || {}).data ? esc(EP.dataLonga(m.posse.data)) : null, (m.posse || {}).fontes) +
      fato("⏳", EP.tr("Aposentadoria obrigatória", "Mandatory retirement"), apos.data ? esc(EP.dataLonga(apos.data)) + "<br><small>" + esc(EP.tr("quando completar " + (apos.idade || 75) + " anos", "when turning " + (apos.idade || 75))) + "</small>" : null, apos.fontes) +
      fato("📨", EP.tr("Quem indicou", "Nominated by"), ind.presidente ? nomeHtml(ind.presidente) + (ind.data ? "<br><small>" + esc(EP.tr("presidente da República, em ", "President of Brazil, on ") + EP.data(ind.data)) + "</small>" : "") : null, ind.fontes) +
      fato("👥", EP.tr("Turma", "Chamber"), turma, d.fonteTurmas) +
      (m.papel === "presidente" && (d.presidencia || {}).desde ? fato("⚖️", EP.tr("Preside o STF desde", "Presides over the STF since"), esc(EP.dataLonga(d.presidencia.desde)) + (d.presidencia.periodo ? "<br><small>" + esc(EP.tr("período " + d.presidencia.periodo, d.presidencia.periodo + " term")) + "</small>" : ""), d.presidencia.fontes) : "") +
      "</div>";
    var oque = '<div class="dica-coruja oque-faz"><span class="coruja" aria-hidden="true">🦉</span><div><p style="margin:0"><b>' +
      esc(EP.tr("O que faz " + EP.gen(m.genero, "um ministro", "uma ministra") + " do STF?", "What does a justice of the STF do?")) + "</b></p><p style=\"margin:4px 0 6px\">" +
      esc(EP.tr("Os ministros do STF julgam se as leis e os atos do governo respeitam a Constituição, a lei maior do país. Também julgam alguns casos que a Constituição manda direto para o STF. Eles não são eleitos.",
        "STF justices decide whether laws and government acts follow the Constitution, the country's highest law. They also decide some cases that the Constitution sends straight to the STF. They are not elected.")) + "</p>" +
      '<a class="link-seta" href="' + esc(lang("entenda.html")) + '#parte-8">' + EP.tr("Entenda quem julga e quem fiscaliza", "Learn who judges and who oversees") + ' <span aria-hidden="true">›</span></a> ' +
      fonteBtn((d.regras || {}).fontes, EP.tr("o que faz um ministro do STF", "what an STF justice does"), EP.tr("Fonte", "Source")) + "</div></div>";
    var todas = todasFontes(p, d);
    return topo + fatos + oque + linhaHtml(m, d) + ondeHtml(m, d) +
      '<section class="secao-perfil" aria-labelledby="t-fontes"><h2 id="t-fontes"><span class="ic" aria-hidden="true">📚</span>' + EP.tr("Todas as fontes desta página", "All the sources on this page") + "</h2>" +
      EP.fontesHtml(todas) + conferidoHtml(d) + "</section>";
  };

  // ---------------------------------------------------------------- liga a seção, se a página tiver
  var el = document.getElementById("stf");
  if (!el) return;
  S.dados().then(function (d) {
    if (EP.hist && EP.hist.param && EP.hist.param()) secaoPassado(el, d);
    else secao(el, d);
  }).catch(function () {
    el.innerHTML = '<div class="vazio"><span class="grande" aria-hidden="true">⚠️</span>' +
      EP.tr("Não foi possível carregar os ministros do STF agora. Tente de novo daqui a pouco.", "Could not load the STF justices right now. Please try again in a little while.") + "</div>";
  });
})();
