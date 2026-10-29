/* Páginas de informação (imparcialidade.html e dados.html): ilustração 3D do topo, botões
   "De onde veio isso?", link do formulário de erros (js/config.js) e o botão de exemplo das fontes. */
(function () {
  "use strict";
  var EP = window.EP, T = window.TRES || {}, D = EP.trd || {};
  var esc = EP.esc;
  var CONFIG = window.EP_CONFIG || {};

  if (D.canonico) D.canonico();

  // ---------- ilustração 3D do topo e enfeites de fundo
  var ilu = document.getElementById("ilu");
  if (ilu) {
    var tipo = ilu.getAttribute("data-ilu");
    if (tipo === "balanca" && T.balanca) ilu.innerHTML = T.balanca();
    else if (tipo === "predio" && T.predio) {
      // prédio público com folhas de dados flutuando em volta
      ilu.innerHTML = T.predio({}) + [["📄", "10%", "24%", "0s"], ["📊", "80%", "8%", ".7s"], ["🗳️", "84%", "60%", "1.4s"]].map(function (d) {
        return '<span class="dado-voa" style="--x:' + d[1] + ";--y:" + d[2] + ";--a:" + d[3] + '">' + d[0] + "</span>";
      }).join("");
    }
  }
  EP.fundo3d([["esfera", "94%", "9%", 34, 3, 0, 7], ["anel", "93%", "62%", 52, 2, 0, 20], ["esfera", "4%", "56%", 30, 6, 0, 8], ["cubo", "4%", "88%", 40, 0, 0, 18]], document.body);

  // ---------- só no inglês: links com versão em inglês e tradução dos exemplos em português
  if (EP.en) {
    [].forEach.call(document.querySelectorAll("a[data-href-en]"), function (a) { a.href = a.getAttribute("data-href-en"); });
    [].forEach.call(document.querySelectorAll(".traducao[hidden]"), function (el) { el.hidden = false; });
  }
  // no celular, a tabela vira cartões: o exemplo ganha um título (o cabeçalho da coluna fica escondido)
  var rotulo = EP.tr("Exemplo do texto oficial", "Example of the official text (in Portuguese)");
  [].forEach.call(document.querySelectorAll(".tabela-info tbody td:last-child"), function (td) { td.setAttribute("data-rotulo", rotulo); });

  // ---------- fontes dos fatos citados nestas páginas
  var CF = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm";
  // título em português; no inglês, traduzido, com " (in Portuguese)" e lang "en" (como nas aulas)
  function fonte(veiculo, pt, en, url, data) {
    var f = { veiculo: veiculo, titulo: EP.tr(pt, en + " (in Portuguese)"), url: url };
    if (data) f.data = data;
    if (EP.en) f.lang = "en";
    return f;
  }
  var FONTES = {
    cf52: fonte("Planalto", "Constituição Federal, art. 52, III e IV: o Senado aprova, por voto secreto, a escolha de algumas autoridades",
      "Federal Constitution, art. 52, III and IV: the Senate approves the choice of some authorities by secret ballot", CF + "#art52", "1988-10-05"),
    cf57: fonte("Planalto", "Constituição Federal, art. 57, § 4º: deputados e senadores tomam posse a partir de 1º de fevereiro do primeiro ano da legislatura",
      "Federal Constitution, art. 57, § 4: deputies and senators take office from February 1 of the first year of the legislative term", CF + "#art57", "1988-10-05"),
    cf60: fonte("Planalto", "Constituição Federal, art. 60, I: uma emenda à Constituição pode ser proposta por, no mínimo, um terço dos deputados (171 de 513)",
      "Federal Constitution, art. 60, I: an amendment to the Constitution can be proposed by at least one third of the deputies (171 of 513)", CF + "#art60", "1988-10-05"),
    cf62: fonte("Planalto", "Constituição Federal, art. 62, §§ 3º e 11: a medida provisória pode ser rejeitada ou perder a eficácia (a validade) se não for votada no prazo; são coisas diferentes",
      "Federal Constitution, art. 62, §§ 3 and 11: a provisional measure can be rejected, or it can lose its effect (expire) if it is not voted on in time; these are different things", CF + "#art62", "1988-10-05"),
    ec111: fonte("Planalto", "Emenda Constitucional nº 111, de 2021: a partir das eleições de 2026, o presidente toma posse em 5 de janeiro e os governadores, em 6 de janeiro",
      "Constitutional Amendment No. 111 of 2021: starting with the 2026 elections, the President takes office on January 5 and governors on January 6",
      "https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc111.htm", "2021-09-28"),
    cf29: fonte("Planalto", "Constituição Federal, art. 29, III: prefeitos e vereadores tomam posse em 1º de janeiro do ano seguinte à eleição",
      "Federal Constitution, art. 29, III: mayors and city councilors take office on January 1 of the year after the election", CF + "#art29", "1988-10-05"),
    "posse-rs": fonte("Assembleia Legislativa do RS", "Constituição do Rio Grande do Sul, art. 49, § 3º: a primeira sessão de cada legislatura, para a posse dos deputados, é em 31 de janeiro",
      "Constitution of Rio Grande do Sul, art. 49, § 3: the first session of each legislative term, when deputies take office, is on January 31",
      "https://www2.al.rs.gov.br/dal/LinkClick.aspx?fileticket=WQdIfqNoXO4%3d&tabid=3683&mid=5359"),
    "posse-df": fonte("Sistema Integrado de Normas Jurídicas do DF (SINJ-DF)", "Emenda à Lei Orgânica nº 131, de 2024: a Câmara Legislativa se reúne em 6 de janeiro do primeiro ano da legislatura para a posse dos deputados distritais",
      "Amendment No. 131 of 2024 to the Organic Law of the Federal District: the Legislative Chamber meets on January 6 of the first year of the term for district deputies to take office",
      "https://www.sinj.df.gov.br/sinj/Norma/c50c92bdd30e4a04ae0c20c0d1dd89f2/ELO_131_2024.html"),
    "posse-rr": fonte("Assembleia Legislativa de Roraima", "Constituição de Roraima, art. 30, § 4º (Emenda 75/2021): a posse dos deputados estaduais é em 1º de janeiro do primeiro ano da legislatura",
      "Constitution of Roraima, art. 30, § 4 (Amendment 75/2021): state deputies take office on January 1 of the first year of the term",
      "https://sapl.al.rr.leg.br/norma/3912"),
    cf14: fonte("Planalto", "Constituição Federal, art. 14, § 6º: para concorrer a outro cargo, o presidente, os governadores e os prefeitos deixam o cargo até 6 meses antes da eleição",
      "Federal Constitution, art. 14, § 6: to run for another office, the President, governors and mayors must leave office up to 6 months before the election", CF + "#art14", "1988-10-05"),
    l9504: fonte("Planalto", "Lei nº 9.504/1997 (Lei das Eleições), arts. 1º e 3º: as eleições são no primeiro domingo de outubro; nas cidades com mais de 200 mil eleitores, pode haver 2º turno para prefeito",
      "Law No. 9,504/1997 (Elections Law), arts. 1 and 3: elections are held on the first Sunday of October; in cities with more than 200,000 voters, there may be a runoff for mayor",
      "https://www.planalto.gov.br/ccivil_03/leis/l9504.htm", "1997-09-30"),
    "tse-candidatos-2026": fonte("TSE", "Dados Abertos: candidaturas de 2026 (situação depois da totalização) e bens declarados",
      "Open data: 2026 candidacies (status after the final count) and declared assets", "https://dadosabertos.tse.jus.br/dataset/candidatos-2026"),
    "tse-votacao-2026": fonte("TSE", "Dados Abertos: resultados de 2026 (votação de cada candidatura por município e zona)",
      "Open data: 2026 results (votes for each candidacy by municipality and electoral zone)", "https://dadosabertos.tse.jus.br/dataset/resultados-2026"),
    "tse-suplementares": fonte("TSE", "Eleições suplementares: calendário e cidades", "Special elections: calendar and cities",
      "https://www.tse.jus.br/eleicoes/eleicoes-suplementares"),
    "camara-proposicoes": fonte("Câmara dos Deputados", "Dados Abertos: proposições e a situação de cada uma", "Open data: bills and the status of each one",
      "https://dadosabertos.camara.leg.br/swagger/api.html"),
    "camara-votacoes": fonte("Câmara dos Deputados", "Dados Abertos: votações do Plenário e o voto de cada deputado", "Open data: votes in the full Chamber and each deputy's vote",
      "https://dadosabertos.camara.leg.br/swagger/api.html"),
    "camara-cota": fonte("Câmara dos Deputados", "Cota parlamentar: consulta oficial dos gastos de cada deputado", "Office allowance (cota parlamentar): official lookup of each deputy's spending",
      "https://www.camara.leg.br/cota-parlamentar/"),
    "senado-processos": fonte("Senado Federal", "Dados Abertos Legislativos: processos e a situação de cada proposta", "Legislative open data: bills and the status of each one",
      "https://www12.senado.leg.br/dados-abertos/legislativo"),
    "senado-votacoes": fonte("Senado Federal", "Votações nominais do Plenário do Senado", "Roll-call votes in the full Senate",
      "https://www25.senado.leg.br/web/atividade/votacoes-nominais"),
    "senado-dados": fonte("Senado Federal", "Dados Abertos do Senado: gastos da cota dos senadores (CEAPS)", "Senate open data: senators' office allowance spending (CEAPS)",
      "https://www12.senado.leg.br/dados-abertos"),
    "camara-orientacoes": fonte("Câmara dos Deputados", "Dados Abertos: arquivos votacoesOrientacoes (a orientação de cada liderança em cada votação)",
      "Open data: votacoesOrientacoes files (the orientation of each party leadership in each vote)", "https://dadosabertos.camara.leg.br/swagger/api.html#staticfile"),
    "senado-orientacoes": fonte("Senado Federal", "Dados Abertos Legislativos: orientação das lideranças nas votações do Plenário",
      "Legislative open data: party leaderships' orientations in votes in the full Senate", "https://legis.senado.leg.br/dadosabertos/docs/"),
    "tse-candidatos": fonte("TSE", "Dados Abertos: candidatos (um conjunto por eleição, de 1994 a 2026; o de 1994 é o primeiro)",
      "Open data: candidates (one dataset per election, from 1994 to 2026; 1994 is the first)", "https://dadosabertos.tse.jus.br/dataset/candidatos-1994"),
    "interlegis-sigi": fonte("Interlegis (Senado Federal)", "SIGI: órgãos legislativos atendidos (domínio .leg.br e sistemas de cada Câmara Municipal)",
      "SIGI: legislative bodies served (the .leg.br domain and systems of each city council)", "https://sigi.interlegis.leg.br/servicos/casasatendidas/"),
    "sigpub": fonte("Diários Oficiais das associações de municípios (SIGPub)", "Municípios que publicam em cada Diário Oficial das associações",
      "Municipalities that publish in each official gazette run by the municipal associations", "https://www.diariomunicipal.com.br/"),
    "tse-resultados-2026": fonte("TSE", "Resultados das eleições de 2026: 2º turno para presidente (totalização final)",
      "2026 election results: presidential runoff (final count)", "https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/br-c0001-e006258-u.json", "2026-10-25"),
    "tse-1990": fonte("TSE", "Dados Abertos: resultados da eleição de 1990 (senadores eleitos em 1990, no Senado de 1995 a 1998)",
      "Open data: 1990 election results (senators elected in 1990, who served in the Senate from 1995 to 1998)", "https://dadosabertos.tse.jus.br/dataset/resultados-1990"),
    "senado-leg50": fonte("Senado Federal", "Dados Abertos: senadores da 50ª legislatura (1995 a 1999)", "Open data: senators of the 50th legislative term (1995 to 1999)",
      "https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/50"),
    "biblioteca-fhc": fonte("Biblioteca da Presidência da República", "Galeria dos ex-presidentes: ministérios do governo Fernando Henrique Cardoso (lista em PDF)",
      "Gallery of former presidents: ministries of the Fernando Henrique Cardoso government (PDF list)", "https://www.gov.br/secretariageral/pt-br/centrais-de-conteudo/biblioteca-da-pr/galeria-dos-ex-presidentes/fernando-henrique-cardoso/ministerios-fhc"),
    "biblioteca-lula": fonte("Biblioteca da Presidência da República", "Galeria dos ex-presidentes: ministérios do governo Luiz Inácio Lula da Silva, de 2003 a 2010 (lista em PDF)",
      "Gallery of former presidents: ministries of the Luiz Inácio Lula da Silva government, 2003 to 2010 (PDF list)", "https://www.gov.br/secretariageral/pt-br/centrais-de-conteudo/biblioteca-da-pr/galeria-dos-ex-presidentes/luiz-inacio-lula-da-silva/ministerios-lula.pdf"),
    "biblioteca-dilma": fonte("Biblioteca da Presidência da República", "Galeria dos ex-presidentes: ministérios do governo Dilma Rousseff (lista em PDF)",
      "Gallery of former presidents: ministries of the Dilma Rousseff government (PDF list)", "https://www.gov.br/secretariageral/pt-br/centrais-de-conteudo/biblioteca-da-pr/galeria-dos-ex-presidentes/dilma-vana-rousseff/ministerios-dilma.pdf"),
    "dou": fonte("Diário Oficial da União (Imprensa Nacional)", "Busca do Diário Oficial: decretos de nomeação e de exoneração de ministros de Estado",
      "Official Gazette search: appointment and dismissal decrees of ministers of State", "https://www.in.gov.br/consulta/-/buscar/dou"),
    cf101: fonte("Planalto", "Constituição Federal, art. 101: o STF tem 11 ministros, com mais de 35 e menos de 70 anos, nomeados pelo presidente da República depois de aprovados pela maioria absoluta do Senado",
      "Federal Constitution, art. 101: the STF has 11 justices, older than 35 and younger than 70, appointed by the President after approval by an absolute majority of the Senate", CF + "#art101", "2022-05-17"),
    ec88: fonte("Senado Federal", "Emenda Constitucional nº 88, de 2015: os ministros do STF se aposentam obrigatoriamente aos 75 anos",
      "Constitutional Amendment No. 88 of 2015: STF justices must retire at 75", "https://legis.senado.leg.br/norma/540691/publicacao/15624167", "2015-05-07"),
    "stf-ostf": fonte("Supremo Tribunal Federal", "O STF: composição do Plenário, Turmas e presidência",
      "The STF: members of the full court, Chambers (Turmas) and presidency", "https://portal.stf.jus.br/ostf/"),
    "stf-pastas": fonte("Supremo Tribunal Federal (Biblioteca)", "Pastas dos Ministros: a composição atual, na ordem oficial, e as datas de cada ministro (indicação, aprovação no Senado, nomeação e posse)",
      "Justices' files: the current composition, in the official order, and each justice's dates (nomination, Senate approval, appointment and swearing-in)",
      "https://portal.stf.jus.br/textos/verTexto.asp?servico=bibliotecaConsultaProdutoBibliotecaPastaMinistro&pagina=ComposicaoAtual"),
    "senado-msf": fonte("Senado Federal", "Dados Abertos: mensagens (MSF) com a indicação de autoridades, o parecer da CCJ e o resultado no Plenário",
      "Open data: messages (MSF) nominating authorities, the CCJ committee report and the result in the full Senate",
      "https://legis.senado.leg.br/dadosabertos/processo?sigla=MSF&ano=2026"),
    "corte-aberta": fonte("Supremo Tribunal Federal", "Corte Aberta: os painéis de estatísticas do STF, com as decisões e o acervo de cada gabinete",
      "Corte Aberta: the STF statistics dashboards, with the decisions and the caseload of each justice's office", "https://portal.stf.jus.br/hotsites/corteaberta/")
  };
  // botão "De onde veio isso?" com o assunto escondido para quem usa leitor de tela
  function fonteBtn(lista, assunto) {
    var b = EP.botaoFontes(lista);
    return b && assunto ? b.replace(/<\/button>$/, '<span class="sr"> (' + esc(assunto) + ")</span></button>") : b;
  }
  [].forEach.call(document.querySelectorAll("[data-fonte-ids]"), function (el) {
    var lista = el.getAttribute("data-fonte-ids").split(/\s+/).map(function (k) { return FONTES[k]; }).filter(Boolean);
    el.innerHTML = fonteBtn(lista, el.getAttribute(EP.en ? "data-assunto-en" : "data-assunto"));
  });

  // ---------- exemplo: as fontes de verdade da lista de deputados e senadores (carrega só ao tocar)
  var demo = document.getElementById("demo-fontes");
  if (demo) {
    demo.innerHTML = "<span>" + EP.tr("Experimente com a lista de deputados e senadores:", "Try it with the list of deputies and senators:") + "</span> " +
      '<button type="button" class="fontes-btn nao-ler" id="btn-demo-fontes"><span aria-hidden="true">📚 </span>' + EP.tr("De onde veio isso?", "Where does this come from?") +
      '<span class="sr"> (' + EP.tr("lista de deputados e senadores", "list of deputies and senators") + ")</span></button>";
    document.getElementById("btn-demo-fontes").addEventListener("click", function () {
      var b = this;
      b.setAttribute("aria-busy", "true");
      Promise.all([EP.json("dados/camara.json"), EP.json("dados/senado.json")]).then(function (r) {
        return r.map(function (d) { return d && d.fonte; }).filter(Boolean);
      }).catch(function () { return []; }).then(function (lista) {
        b.removeAttribute("aria-busy");
        if (!lista.length) lista = [FONTES["camara-proposicoes"], FONTES["senado-dados"]];
        EP.abrir('<span aria-hidden="true">📚 </span>' + EP.tr("De onde veio isso?", "Where does this come from?"),
          "<p>" + EP.tr("Estas informações vieram destes lugares. Toque para abrir a página original.", "This information came from these places. Tap to open the original page.") + "</p>" +
          EP.fontesHtml(lista));
      });
    });
  }

  // ---------- formulário "Viu algo errado?" (links em js/config.js; vazio = ainda não existe)
  var acoes = document.getElementById("avisar-acoes");
  function linkOk(u) { return /^https:\/\/\S+$/i.test(u || ""); }
  if (acoes && linkOk(CONFIG.formularioErros)) {
    var novaAba = '<span class="sr"> ' + EP.tr("(abre em outra aba)", "(opens in a new tab)") + "</span>";
    acoes.innerHTML = '<div class="botoes">' +
      '<a class="btn" href="' + esc(CONFIG.formularioErros) + '" target="_blank" rel="noopener"><span aria-hidden="true">📮 </span>' +
      EP.tr("Avisar um erro", "Report a mistake") + ' <span aria-hidden="true">↗</span>' + novaAba + "</a>" +
      (linkOk(CONFIG.formularioRespostas) ? '<a class="btn claro" href="' + esc(CONFIG.formularioRespostas) + '" target="_blank" rel="noopener"><span aria-hidden="true">👀 </span>' +
        EP.tr("Ver o que as pessoas já avisaram", "See what people have already reported") + ' <span aria-hidden="true">↗</span>' + novaAba + "</a>" : "") + "</div>";
  }

  if (D.rodapeErros) D.rodapeErros(document.getElementById("links-erro"));
  EP.revelar();
  EP.paralaxe();
})();
