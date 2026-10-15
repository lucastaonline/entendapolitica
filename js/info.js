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
      "https://www12.senado.leg.br/dados-abertos")
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
