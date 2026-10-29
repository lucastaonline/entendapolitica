/* ====== Entenda Política: os textos dos dados em inglês ======
   Os coletores (scripts/) escrevem frases em português ("statusTxt", "aviso", "obs", "situacao"...).
   Aqui elas viram inglês a partir dos códigos ou de padrões conhecidos. Se existir o campo "_en", ele vale.
   Quando a frase não é reconhecida, o texto aparece em português, marcado com lang="pt-BR" e com "(in Portuguese)".
   Tudo devolve HTML já escapado. Em português, devolve o texto original. Uso: EP.trd.status(proposta), EP.trd.aviso(texto)... */
(function () {
  "use strict";
  var EP = window.EP;
  if (!EP) return;
  var esc = EP.esc;
  var D = (EP.trd = {});

  // ---------------------------------------------------------------- texto que só existe em português
  D.emPt = function () { return EP.en ? ' <span class="em-pt">(in Portuguese)</span>' : ""; };
  D.ptHtml = function (txt, semAviso) {
    if (txt == null || txt === "") return "";
    return EP.pt(esc(txt)) + (semAviso ? "" : D.emPt());
  };

  // dd/mm/aaaa -> data por extenso no idioma da página
  function dataBr(s) {
    var m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(s);
    return m ? EP.dataLonga(m[3] + "-" + m[2] + "-" + m[1]) : esc(s);
  }
  var DATA = "(\\d{2}\\/\\d{2}\\/\\d{4})";
  function re(txt, flags) { return new RegExp(txt.replace(/DATA/g, DATA), flags || "i"); }

  // frase por frase; devolve null se alguma não for reconhecida
  function porRegras(txt, regras) {
    if (txt == null || txt === "") return null;
    var fs = String(txt).trim().replace(/\.\s+(?=[A-ZÀ-Ý"(])/g, ".\u0001").split("\u0001"), out = [];
    for (var i = 0; i < fs.length; i++) {
      var f = fs[i].trim(), ponto = /\.$/.test(f), base = f.replace(/\.$/, ""), ok = null;
      for (var k = 0; k < regras.length && ok == null; k++) {
        var m = regras[k][0].exec(base);
        if (m) ok = typeof regras[k][1] === "function" ? regras[k][1](m) : regras[k][1];
      }
      if (ok == null) return null;
      out.push(ok + (ponto && !/[.!?]$/.test(ok) ? "." : ""));
    }
    return out.join(" ");
  }
  D.porRegras = porRegras;

  // pt (texto do coletor) -> HTML no idioma da página
  function traduz(pt, regras, en) {
    if (pt == null || pt === "") return "";
    if (!EP.en) return esc(pt);
    if (en) return esc(en);
    var t = regras ? porRegras(pt, regras) : null;
    return t != null ? t : D.ptHtml(pt);
  }
  D.traduz = traduz;

  // ---------------------------------------------------------------- situação das propostas (statusTxt)
  var NORMAS = [
    [/^Lei Complementar/i, "Became a complementary law"],
    [/^Lei/i, "Became law"],
    [/^Emenda Constitucional/i, "Became a constitutional amendment"],
    [/^Resolução do Senado/i, "Became a Senate resolution"],
    [/^Resolução da Câmara/i, "Became a Chamber of Deputies resolution"],
    [/^Resolução do Congresso/i, "Became a resolution of Congress"],
    [/^Resolução/i, "Became a resolution"],
    [/^Decreto Legislativo/i, "Became a legislative decree"]
  ];
  function virou(nome, vetada) {
    var tipo = "Became law";
    for (var i = 0; i < NORMAS.length; i++) if (NORMAS[i][0].test(nome)) { tipo = NORMAS[i][1]; break; }
    return tipo + ": " + EP.pt(esc(nome)) + (vetada ? " (with some parts vetoed)" : "");
  }
  var REGRAS_STATUS = [
    [/^Ainda em discussão$/i, "Still under discussion"],
    [/^Ainda em discussão no Senado$/i, "Still under discussion in the Senate"],
    [/^Ainda em discussão na Câmara$/i, "Still under discussion in the Chamber of Deputies"],
    [/^Pronta para ser votada$/i, "Ready for a vote"],
    [/^Apresentada; ainda vai começar a ser analisada$/i, "Filed; the review has not started yet"],
    [/^Apresentada; em análise inicial na Câmara$/i, "Filed; under initial review in the Chamber of Deputies"],
    [/^Aprovada; falta votar o texto final na Câmara$/i, "Approved; the final wording still needs a vote in the Chamber of Deputies"],
    [/^Já está valendo, mas o Congresso ainda precisa votar$/i, "Already in force, but Congress still has to vote on it"],
    [/^Ainda em análise no Congresso$/i, "Still under review in Congress"],
    [/^Aprovada na Câmara; agora está no Senado$/i, "Approved by the Chamber of Deputies; now in the Senate"],
    [/^Aprovada no Senado; agora está na Câmara$/i, "Approved by the Senate; now in the Chamber of Deputies"],
    [/^Aprovada no Senado e enviada à Câmara(?: em (\d{4}))?$/i, function (m) { return "Approved by the Senate and sent to the Chamber of Deputies" + (m[1] ? " in " + m[1] : ""); }],
    [/^Aprovada na Câmara; esperando ser enviada para a próxima etapa$/i, "Approved by the Chamber of Deputies; waiting to be sent to the next stage"],
    [/^Aprovada no Senado e na Câmara \(com mudanças\); o Senado analisa as mudanças$/i, "Approved by the Senate and the Chamber of Deputies (with changes); the Senate is reviewing the changes"],
    [/^Aprovada; esperando a decisão do presidente da República$/i, "Approved; waiting for the President's decision"],
    [/^Aprovada pelo Congresso; esperando a sanção do presidente$/i, "Approved by Congress; waiting for the President to sign it"],
    [/^Aprovada; esperando ser promulgada$/i, "Approved; waiting to be promulgated"],
    [/^Aprovada no Senado; na Câmara, anda junto com outra proposta$/i, "Approved by the Senate; in the Chamber of Deputies it was joined to a similar bill"],
    [/^Aprovada no Senado e na Câmara; ainda não virou lei$/i, "Approved by the Senate and the Chamber of Deputies; not law yet"],
    [/^Aprovada no Senado e na Câmara; virou lei$/i, "Approved by the Senate and the Chamber of Deputies; became law"],
    [/^Aprovada, mas ainda não virou lei$/i, "Approved, but not law yet"],
    [/^Arquivada$/i, "Shelved"],
    [/^Arquivada em (\d{4})$/i, function (m) { return "Shelved in " + m[1]; }],
    [/^Arquivada ao fim da legislatura em (\d{4})$/i, function (m) { return "Shelved at the end of the legislative term, in " + m[1]; }],
    [/^Arquivada no Senado em (\d{4})$/i, function (m) { return "Shelved in the Senate in " + m[1]; }],
    [/^Arquivada na Câmara em (\d{4})$/i, function (m) { return "Shelved in the Chamber of Deputies in " + m[1]; }],
    [/^Aprovada no Senado, mas arquivada na Câmara$/i, "Approved by the Senate, but shelved in the Chamber of Deputies"],
    [/^Andando junto com outra proposta parecida(?: \((.+)\))?$/i, function (m) { return "Joined to a similar bill" + (m[1] ? " (" + esc(m[1]) + ")" : ""); }],
    [/^Virou (?:a|o) (.+?)( \(com partes vetadas\))?$/i, function (m) { return virou(m[1], !!m[2]); }],
    [/^Virou resolução da Câmara$/i, "Became a Chamber of Deputies resolution"],
    [/^Virou emenda à Constituição$/i, "Became a constitutional amendment"],
    [/^Virou lei$/i, "Became law"],
    [/^A Câmara não informa a situação$/i, "The Chamber of Deputies does not report its status"],
    [/^Virou outra proposta(?:: (.+))?$/i, function (m) { return "Turned into another bill" + (m[1] ? ": " + esc(m[1]) : ""); }],
    [/^Foi transformada em indicação \(sugestão ao governo\)$/i, "Was turned into a suggestion to the government"],
    [/^Foi transformada em outro processo$/i, "Was turned into another proceeding"],
    [/^Situação não classificada$/i, "Status not classified"],
    [/^Situação na Câmara: (.+)$/i, function (m) { return "Status at the City Council: " + EP.pt(esc(m[1])); }],
    [/^Devolvida ao autor: a Presidência da Câmara não deixou seguir$/i, "Returned to the author: the Speaker of the Chamber did not let it go ahead"],
    [/^Ficou prejudicada \(não vai mais ser votada\)$/i, "Became moot (it will no longer be voted on)"],
    [/^Ficou prejudicada \(outra decisão fez ela perder o sentido\)$/i, "Became moot (another decision made it pointless)"],
    [/^Ficou prejudicada$/i, "Became moot"],
    [/^Rejeitada por uma comissão do Senado$/i, "Rejected by a Senate committee"],
    [/^Rejeitada pelo Plenário do Senado$/i, "Rejected by the full Senate"],
    [/^Rejeitada no Senado$/i, "Rejected in the Senate"],
    [/^Rejeitada na Câmara$/i, "Rejected in the Chamber of Deputies"],
    [/^Rejeitada na CCJ do Senado por ir contra a Constituição$/i, "Rejected by the Senate's Constitution and Justice Committee for going against the Constitution"],
    [/^O presidente vetou a proposta inteira$/i, "The President vetoed the whole bill"],
    [/^O presidente vetou tudo; o Congresso ainda vai decidir sobre o veto$/i, "The President vetoed all of it; Congress has yet to decide on the veto"],
    [/^Aprovada pelo Congresso, mas vetada por inteiro(?: pelo presidente)?$/i, "Approved by Congress, but fully vetoed by the President"],
    [/^Não pôde seguir: assinaturas foram retiradas$/i, "Could not go ahead: signatures were withdrawn"],
    [/^Perdeu a validade antes de virar lei$/i, "Expired before becoming law"],
    [/^Perdeu a validade \(o Congresso não votou a tempo\)$/i, "Expired (Congress did not vote on it in time)"],
    [/^Perdeu a validade \(ficou sem eficácia\)$/i, "Expired (it lost its legal effect)"],
    [/^Devolvida pela Presidência do Senado \(não pôde seguir\)$/i, "Returned by the President of the Senate (could not go ahead)"],
    [/^Aprovada no Senado, mas ficou prejudicada na Câmara$/i, "Approved by the Senate, but became moot in the Chamber of Deputies"],
    [/^Aprovada no Senado, mas rejeitada na Câmara$/i, "Approved by the Senate, but rejected in the Chamber of Deputies"],
    [/^Aprovada no Senado, mas retirada na Câmara$/i, "Approved by the Senate, but withdrawn in the Chamber of Deputies"],
    [/^Rejeitada pelo Congresso \(sem os requisitos de urgência\)$/i, "Rejected by Congress (it did not meet the urgency requirements)"],
    [/^Rejeitada pelo Congresso$/i, "Rejected by Congress"],
    [/^Rejeitada ou parada de vez$/i, "Rejected or stopped for good"],
    [/^Rejeitada$/i, "Rejected"],
    [/^Rejeitada em votação ou vetada por inteiro$/i, "Rejected in a vote or fully vetoed"],
    [/^Parou \(não vai mais ser votada\)$/i, "Stopped (it will no longer be voted on)"],
    [/^Parou \(perdeu a validade, ficou prejudicada ou foi devolvida\)$/i, "Stopped (expired, became moot or was returned)"],
    [/^Aprovada no Senado, mas parou na Câmara$/i, "Approved by the Senate, but stopped in the Chamber of Deputies"],
    [/^(?:O autor|A autora) desistiu$/i, "Withdrawn by the author"],
    [/^(?:O autor|A autora) desistiu e retirou a proposta$/i, "The author withdrew the bill"],
    [/^Foi revogada \(cancelada\)$/i, "Was revoked (cancelled)"],
    [/^O governo retirou a proposta$/i, "The government withdrew the bill"]
  ];
  // situação de uma proposta, em uma frase
  D.status = function (x) {
    var s = EP.STATUS[x.status] ? x.status : "outra";
    if (!EP.en) return esc(x.statusTxt || EP.STATUS[s].txt);
    if (x.statusTxt_en) return esc(x.statusTxt_en);
    var t = x.statusTxt ? porRegras(x.statusTxt, REGRAS_STATUS) : null;
    if (t != null) return t;
    if (s === "lei" && x.lei && x.lei.nome) return virou(x.lei.nome, false);
    return esc(EP.STATUS[s].txt);
  };

  // ---------------------------------------------------------------- resultado das eleições ("Eleito por QP"...)
  var REGRAS_SIT = [
    [/^Eleit[oa]$/i, "Elected"],
    [/^Eleit[oa] por QP$/i, "Elected through the party's vote quota"],
    [/^Eleit[oa] por média$/i, "Elected through the leftover seats"],
    [/^Suplente$/i, "Alternate"],
    [/^Não eleit[oa]$/i, "Not elected"],
    [/^Foi ao 2º turno$/i, "Went to the runoff"],
    [/^Eleit[oa] no ([12])º turno(?:, na chapa de (.+?))?( \(votos da chapa\))?$/i, function (m) {
      return (m[1] === "1" ? "Elected in the first round" : "Elected in the runoff") + (m[2] ? ", on " + esc(m[2]) + "'s ticket" : "") + (m[3] ? " (votes for the whole ticket)" : "");
    }],
    [/^Eleit[oa] em (\d{4}) \(segundo o DivulgaCandContas\)$/i, function (m) { return "Elected in " + m[1] + " (according to DivulgaCandContas, a TSE website)"; }],
    [re("^Eleit[oa] na eleição suplementar de DATA(?:, na chapa de (.+))?$"), function (m) {
      return "Elected in the special election of " + dataBr(m[1]) + (m[2] ? ", on " + esc(m[2]) + "'s ticket" : "");
    }],
    [re("^(.+) na eleição suplementar de DATA$"), function (m) {
      var a = porRegras(m[1], REGRAS_SIT);
      return a ? a + " in the special election of " + dataBr(m[2]) : null;
    }]
  ];
  D.situacao = function (txt, en) { return traduz(txt, REGRAS_SIT, en); };

  // ---------------------------------------------------------------- avisos das listas (TSE)
  var REGRAS_AVISO = [
    [/^Lista de quem foi eleito em (\d{4}), segundo o TSE$/i, function (m) { return "List of who was elected in " + m[1] + ", according to the TSE (Brazil's Superior Electoral Court)"; }],
    [/^Alguns podem ter saído e suplentes podem ter assumido$/i, "Some may have left office and alternates may have taken their seats"],
    [/^Alguns podem ter saído \(cassação, renúncia, licença\) e suplentes podem ter assumido$/i, "Some may have left office (removed from office, resigned or on leave) and alternates may have taken their seats"],
    [/^Alguns podem ter saído e suplentes podem ter assumido: quem está no cargo hoje aparece no site oficial da Assembleia$/i,
      "Some may have left office and alternates may have taken their seats: who is in office today is shown on the official website of the state Legislative Assembly"],
    [/^Alguns podem ter saído e suplentes podem ter assumido: quem está no cargo hoje aparece no site oficial da Câmara Legislativa$/i,
      "Some may have left office and alternates may have taken their seats: who is in office today is shown on the official website of the Legislative Chamber of the Federal District"],
    [/^Prefeito\(a\) e vice eleitos em 2024, segundo o TSE$/i, "Mayor and vice mayor elected in 2024, according to the TSE (Brazil's Superior Electoral Court)"],
    [/^Pode ter havido mudanças depois \(cassação, renúncia, morte ou eleição suplementar\)$/i, "There may have been changes since then (removal from office, resignation, death or a special election)"],
    [re("^Prefeito\\(a\\) e vice escolhidos na eleição suplementar de DATA$"), function (m) { return "Mayor and vice mayor chosen in the special election of " + dataBr(m[1]); }],
    [/^Nos dados abertos do TSE, o resultado de 2024 desta cidade aparece sem definição \(pode estar sendo recalculado\)$/i, "In the TSE's open data, this city's 2024 result appears without a final outcome (it may be being recalculated)"],
    [/^O nome veio do DivulgaCandContas, do TSE$/i, "The name came from DivulgaCandContas, a TSE website"],
    [/^Os nomes vieram do DivulgaCandContas, do TSE$/i, "The names came from DivulgaCandContas, a TSE website"],
    [/^O TSE não mostra prefeito\(a\) eleito\(a\) em 2024 nesta cidade: a eleição pode ter sido anulada ou ainda estar em julgamento na Justiça Eleitoral$/i,
      "The TSE shows no mayor elected in 2024 in this city: the election may have been annulled or may still be under review by the electoral courts"],
    [re("^Está marcada uma eleição suplementar para prefeito em DATA$"), function (m) { return "A special mayoral election is scheduled for " + dataBr(m[1]); }],
    [/^Até lá, quem está no cargo pode ser outra pessoa$/i, "Until then, the person in office may be someone else"],
    [/^Até lá, a cidade é governada de forma temporária \(em geral, por quem preside a Câmara Municipal\)$/i, "Until then, the city is governed temporarily (usually by the head of the city council)"],
    [re("^Uma eleição suplementar para prefeito foi marcada para DATA, mas o resultado não aparece nos dados abertos do TSE \\(ela pode ter sido suspensa ou adiada\\)$"), function (m) {
      return "A special mayoral election was scheduled for " + dataBr(m[1]) + ", but its result does not appear in the TSE's open data (it may have been suspended or postponed)";
    }],
    [/^Quem está no cargo pode ser outra pessoa$/i, "The person in office may be someone else"],
    [/^Quem está no cargo hoje foi conferido à mão \(veja as fontes\)$/i, "Who is in office today was checked by hand (see the sources)"],
    [/^Em "eleito2024" está quem o TSE mostra como eleito em 2024$/i, "The TSE's record of who was elected in 2024 is kept as well"],
    [re("^Estes vereadores foram eleitos na eleição suplementar de DATA$"), function (m) { return "These city councilors were elected in the special election of " + dataBr(m[1]); }],
    [re("^Em DATA houve eleição suplementar para vereador: (.+) (foi eleit[oa]|foram eleitos)$"), function (m) {
      return "On " + dataBr(m[1]) + " there was a special election for the city council: " + esc(m[2]) + (/^foi/i.test(m[3]) ? " was elected" : " were elected");
    }],
    [/^Quem saiu da Câmara não aparece nos dados do TSE, por isso a lista pode ter um nome a mais$/i, "People who left the council do not show up in the TSE data, so the list may have one name too many"],
    [/^O TSE ainda não mostra os vereadores eleitos em 2024 nesta cidade$/i, "The TSE does not show the city councilors elected in 2024 in this city yet"],
    [/^O Distrito Federal não é dividido em municípios: não tem prefeito nem vereadores$/i, "The Federal District is not divided into municipalities: it has no mayor and no city councilors"],
    [/^O governador e os (\d+) deputados distritais cuidam do DF todo$/i, function (m) { return "The governor and the " + m[1] + " district deputies take care of the whole Federal District"; }],
    [/^Fernando de Noronha é um distrito estadual de Pernambuco: não tem prefeito nem vereadores$/i, "Fernando de Noronha is a state district of Pernambuco: it has no mayor and no city councilors"]
  ];
  D.aviso = function (txt, en) { return traduz(txt, REGRAS_AVISO, en); };

  // ---------------------------------------------------------------- observações do mandato
  var REGRAS_OBS = [
    [/^Era suplente e virou titular \(efetivad[oa]\)$/i, "Was an alternate and became a full member"],
    [/^Suplente em exercício$/i, "Alternate currently in office"],
    [/^Virou titular depois da recontagem dos votos$/i, "Became a full member after the votes were recounted"],
    [re("^Suplente em exercício no lugar de (.+?), que renunciou ao mandato em DATA$"), function (m) { return "Alternate serving in place of " + esc(m[1]) + ", who resigned on " + dataBr(m[2]); }],
    [/^Suplente em exercício no lugar de (.+?), que faleceu em (\d{4})$/i, function (m) { return "Alternate serving in place of " + esc(m[1]) + ", who died in " + m[2]; }],
    [/^Suplente em exercício no lugar de (.+?), que está de licença$/i, function (m) { return "Alternate serving in place of " + esc(m[1]) + ", who is on leave"; }],
    [/^Suplente em exercício no lugar de (.+?), que está afastad[oa] do mandato$/i, function (m) { return "Alternate serving in place of " + esc(m[1]) + ", who is away from office"; }],
    [/^Suplente em exercício no lugar de ([^,]+)$/i, function (m) { return "Alternate serving in place of " + esc(m[1]); }],
    [re("^Voltou a exercer o mandato em DATA$"), function (m) { return "Back in office since " + dataBr(m[1]); }],
    [/^Datas da legislatura: a Câmara não informa as datas exatas deste mandato$/i, "Dates of the legislative term: the Chamber of Deputies does not report the exact dates of this term"],
    [/^O mandato vai até a posse do próximo presidente, em 5 de janeiro de 2027 \(regra da Emenda Constitucional 111, de 2021\)$/i,
      "The term lasts until the next president takes office, on January 5, 2027 (a rule set by Constitutional Amendment 111 of 2021)"],
    [/^O mandato vai até a posse da próxima chapa eleita, em 5 de janeiro de 2027$/i, "The term lasts until the next elected ticket takes office, on January 5, 2027"],
    [/^Também foi ministro do Desenvolvimento, Indústria, Comércio e Serviços de janeiro de 2023 até 3 de abril de 2026; hoje exerce só a Vice-Presidência$/i,
      "He was also Minister of Development, Industry, Trade and Services from January 2023 to April 3, 2026; today he only serves as Vice President"]
  ];
  D.obs = function (txt, en) { return traduz(txt, REGRAS_OBS, en); };

  // ---------------------------------------------------------------- cargos
  D.cargo = function (pt) {
    if (!EP.en || !pt) return pt || "";
    var c = EP.cargo(pt);
    if (c !== pt) return c;
    var m = /^(\d)º suplente de senador(?:a)?$/i.exec(pt);
    if (m) return ({ 1: "1st", 2: "2nd", 3: "3rd" }[m[1]] || m[1] + "th") + " alternate senator";
    m = /^(.+?) da República$/i.exec(pt);
    if (m) return EP.cargo(m[1]);
    m = /^(.+?) \(([A-Z]{2})\)$/.exec(pt);
    if (m) return D.cargo(m[1]) + " (" + m[2] + ")";
    m = /^(.+?) (?:de|do|da|dos|das) (.+)$/.exec(pt);
    if (m) {
      var c2 = EP.cargo(m[1]);
      if (c2 !== m[1]) return c2 + " of " + m[2];
    }
    return pt;
  };

  // ---------------------------------------------------------------- gastos da cota (categorias oficiais)
  var GASTOS = {
    "aquisicao de tokens e certificados digitais": "Digital certificates and tokens",
    "assinatura de publicacoes": "Subscriptions to publications",
    "combustiveis e lubrificantes": "Fuel and lubricants",
    "complementacao do auxilio-moradia": "Extra housing allowance",
    "consultorias, pesquisas e trabalhos tecnicos": "Consulting, research and technical work",
    "divulgacao da atividade parlamentar": "Publicizing their work as a legislator",
    "fornecimento de alimentacao do parlamentar": "Meals",
    "hospedagem, exceto do parlamentar no distrito federal": "Lodging (outside the Federal District)",
    "locacao ou fretamento de aeronaves": "Aircraft rental or charter",
    "locacao ou fretamento de embarcacoes": "Boat rental or charter",
    "locacao ou fretamento de veiculos automotores": "Vehicle rental or charter",
    "manutencao de escritorio de apoio a atividade parlamentar": "Running a support office",
    "participacao em curso, palestra ou evento similar": "Courses, talks and similar events",
    "passagem aerea - rpa": "Air tickets (RPA)",
    "passagem aerea - sigepa": "Air tickets (SIGEPA)",
    "passagem aerea - missao oficial": "Air tickets (official mission)",
    "passagem aerea - reembolso": "Air tickets (reimbursement)",
    "passagens terrestres, maritimas ou fluviais": "Bus, sea and river tickets",
    "servico de seguranca prestado por empresa especializada": "Security services",
    "servico de taxi, pedagio e estacionamento": "Taxis, tolls and parking",
    "servicos postais": "Postage",
    "telefonia": "Telephone",
    "aluguel de imoveis para escritorio politico, compreendendo despesas concernentes a eles": "Rent for local offices (and related costs)",
    "aquisicao de material de consumo para uso no escritorio politico, inclusive aquisicao ou locacao de software, despesas postais, aquisicao de publicacoes, locacao de moveis e de equipamentos":
      "Office supplies, software, postage, publications and equipment rental",
    "contratacao de consultorias, assessorias, pesquisas, trabalhos tecnicos e outros servicos de apoio ao exercicio do mandato parlamentar": "Consulting, advisory, research and other support services",
    "locomocao, hospedagem, alimentacao, combustiveis e lubrificantes": "Transport, lodging, meals and fuel",
    "outros": "Other",
    "passagens aereas, aquaticas e terrestres nacionais": "Domestic air, water and land tickets",
    "servicos de seguranca privada": "Private security services",
    // Assembleias (verba indenizatória da ALMG, despesas de gabinete da Alesp e da Alesc)
    "assinatura de publicacoes, periodicos e \"clippings\"": "Subscriptions to publications, periodicals and clippings",
    "combustivel e lubrificante": "Fuel and lubricants",
    "locacao de imovel e despesas a ele concernentes": "Office rent and related costs",
    "locacao e fretamento de veiculos": "Vehicle rental and charter",
    "manutencao e despesas gerais com veiculos": "Vehicle maintenance and general costs",
    "material de expediente e informatica e locacao de moveis e equipamentos para escritorio": "Office and computer supplies, furniture and equipment rental",
    "passagens, hospedagem e alimentacao": "Tickets, lodging and meals",
    "promocao e participacao em eventos": "Organizing and attending events",
    "servicos de consultoria, assessoria e pesquisa": "Consulting, advisory and research services",
    "assinaturas de periodicos, publicacoes, internet e softwares": "Subscriptions to periodicals, publications, internet and software",
    "hospedagem, alimentacao e despesas de locomocao": "Lodging, meals and travel costs",
    "locacao de bens imoveis": "Property rental",
    "locacao de bens moveis": "Equipment rental",
    "locacao de veiculo de apoio": "Support vehicle rental",
    "locacao de veiculo de representacao": "Official vehicle rental",
    "manutencao de bens moveis, imoveis, condominios e outros": "Maintenance of equipment and property, condo fees and others",
    "materiais de escritorio e outros materiais de consumo": "Office supplies and other consumables",
    "materiais e servicos de manut e conserv de veiculos": "Vehicle maintenance supplies and services",
    "materiais e servicos graficos, de copias e reproducao de docs": "Printing, copying and document reproduction",
    "moradia": "Housing",
    "pedagios": "Tolls",
    "serv.util.publica (telef.movel/fixa, energia, agua, gas etc)": "Utilities (phone, power, water, gas, etc.)",
    "servicos de comunicacao": "Communication services",
    "servicos tecnicos profissionais (consultoria, pesquisas etc)": "Professional technical services (consulting, research, etc.)",
    "almoxarifado": "Office supplies",
    "aluguel": "Rent",
    "assinatura de tv a cabo": "Cable TV subscription",
    "combustiveis": "Fuel",
    "correspondencia / telegrama": "Mail and telegrams",
    "diarias": "Per diems",
    "diarias da equipe": "Staff per diems",
    "grafica": "Printing",
    "inscricao": "Registration fees",
    "passagens": "Tickets",
    "passagens da equipe": "Staff tickets",
    "reembolsos": "Reimbursements",
    "telefone": "Telephone",
    "veiculos": "Vehicles",
    // Assembleias de Goiás (verba indenizatória) e de Mato Grosso do Sul
    "apoio tecnico em contabilidade e financas publicas": "Technical support in accounting and public finance",
    "apoio tecnico em marketing e comunicacao parlamentar": "Technical support in marketing and communication",
    "apoio tecnico em pesquisas": "Technical support in research",
    "apoio tecnico especializado": "Specialized technical support",
    "apoio tecnico juridico": "Legal technical support",
    "apoio a atividade parlamentar": "Support for legislative work",
    "comunicacao, telefone e dados": "Communication, phone and data",
    "conservacao e reforma de imovel usado para escritorio de apoio": "Upkeep and renovation of a support office",
    "divulgacao de atividade parlamentar": "Publicizing their work as a legislator",
    "fornecimento de alimentacao": "Meals",
    "hospedagem": "Lodging",
    "locacao de moveis e equipamentos": "Furniture and equipment rental",
    "locacao ou aquisicao de licenca de uso de software": "Software licenses (rental or purchase)",
    "locacao ou fretamento": "Rental or charter",
    "material de expediente, suprimentos de informatica e manutencao": "Office supplies, computer supplies and maintenance",
    "material para festividades e homenagens": "Supplies for celebrations and tributes",
    "servicos graficos": "Printing services",
    "transportes": "Transport",
    "aquisicao ou locacao de software, servicos postais, assinatura de publicacoes, tv a cabo ou similar, acesso a internet e locacao de moveis e equipamentos":
      "Software, postage, subscriptions, cable TV, internet access and furniture and equipment rental",
    "consultorias, assessorias, pesquisas e trabalhos tecnicos": "Consulting, advisory, research and technical work",
    "imovel de apoio a atividade parlamentar (aluguel, condominio, iptu, agua, telefone fixo e/ou movel, energia eletrica)":
      "Support office (rent, condo fees, property tax, water, phone and electricity)",
    "locomocao do parlamentar, de secretarios e adjuntos parlamentares(passagens, locacao de meios de transporte, hospedagem, alimentacao)":
      "Travel for the legislator and staff (tickets, transport rental, lodging and meals)",
    "material de expediente": "Office supplies",
    // Assembleias (fase 6): AM, AP, BA, ES, MA, PB, PE e RO
    "alimentacao": "Meals",
    "combustivel / lubrificante": "Fuel and lubricants",
    "consultoria e assessoria contabil": "Accounting consulting and advice",
    "consultoria e assessoria de comunicacao": "Communication consulting and advice",
    "consultoria e assessoria de gestao": "Management consulting and advice",
    "consultoria e assessoria de tecnologia da informacao": "IT consulting and advice",
    "consultoria e assessoria juridica": "Legal consulting and advice",
    "divulgacao da ativ. jornais elet/blogs e redes sociais/outdoor led": "Publicizing their work (news websites, blogs, social media and LED billboards)",
    "divulgacao radio/tv ativ. parlamentar": "Publicizing their work on radio and TV",
    "fretamento aereo": "Aircraft charter",
    "fretamento fluvial": "River boat charter",
    "informativos ativ. parlamentar - folders/banners/outdoor": "Newsletters about their work (leaflets, banners and billboards)",
    "internet modem": "Internet access (modem)",
    "locacao / aquisicao de software": "Software rental or purchase",
    "locacao de imovel escritorio parlamentar": "Rent for the legislator's office",
    "locacao de veiculos": "Vehicle rental",
    "material expediente e sup. de informatica": "Office and computer supplies",
    "pesquisas socioeconomicas p/ ativ. parlamentar": "Socioeconomic research for their work",
    "servicos de filmagem/fotograficos ativ. parlamentar": "Filming and photography of their work",
    "apoio administrativo, tecnico e operacional": "Administrative, technical and operational support",
    "combustiveis e lubrificantes automotivos": "Vehicle fuel and lubricants",
    "combustiveis e lubrificantes para outras finalidades": "Fuel and lubricants for other purposes",
    "generos de alimentacao": "Food supplies",
    "hospedagens": "Lodging",
    "locacao de bens moveis de outras naturezas e intangiveis": "Rental of other equipment and intangible assets",
    "locacao de bens moveis e intangiveis": "Rental of equipment and intangible assets",
    "locacao de imoveis": "Property rental",
    "locacao de maquinas e equipamentos": "Machinery and equipment rental",
    "locacao de software": "Software rental",
    "material de copa e cozinha": "Kitchen supplies",
    "outros servicos de terceiros - pessoa juridica": "Other services from companies",
    "passagens e despesas com locomocao": "Tickets and travel costs",
    "servico de processamento de dados": "Data processing services",
    "servico graficos e editoriais": "Printing and publishing services",
    "servicos de agua e esgoto": "Water and sewage services",
    "servicos de energia eletrica": "Electricity",
    "servicos de publicidade legal": "Publication of legal notices",
    "vigilancia ostensiva": "Security guards",
    "aluguel de imoveis para escritorio; despesas concernentes a eles": "Office rent and related costs",
    "aquisicao de material de expediente": "Office supplies",
    "aquisicao ou locacao de software; servicos postais e de seguranca; assinaturas de publicacoes; tv a cabo ou similar; acesso a internet; e locacao de moveis e equipamentos. telefones.": "Software, postage, security, subscriptions, cable TV, internet access, furniture and equipment rental, and phones",
    "assessorias": "Advisory services",
    "consultorias": "Consulting",
    "divulgacao da atividade parlamentar em redes sociais": "Publicizing their work on social media",
    "fretamento": "Charter",
    "locacao de veiculo terrestre": "Vehicle rental",
    "locomocao, hospedagem": "Travel and lodging",
    "pesquisas": "Research",
    "trabalhos tecnicos": "Technical work",
    "consultorias, trabalhos tecnicos e pesquisas socioeconomicas": "Consulting, technical work and socioeconomic research",
    "locacao de equipamentos de audio, video e fotos": "Audio, video and photo equipment rental",
    "locacao de imovel": "Property rental",
    "material": "Supplies",
    "passagens aereas": "Air tickets",
    "contratacao de assessorias, consultorias e trabalhos tecnicos": "Advisory, consulting and technical work",
    "criacao e manutencao de paginas institucionais": "Creating and maintaining institutional web pages",
    "diaria de servidor do gabinete": "Per diems for office staff",
    "fornecimento de alimentacao ao parlamentar e assessores": "Meals for the legislator and aides",
    "hospedagem, exceto do parlamentar em sao luis - ma": "Lodging (except for the legislator in the state capital)",
    "manutencao de escritorios de apoio a atividade parlamentar": "Running support offices",
    "manutencao, pecas e acessorios de veiculos": "Vehicle maintenance, parts and accessories",
    "material de expediente e suprimentos de informatica": "Office and computer supplies",
    "outras despesas com locomocao": "Other travel costs",
    "reprografia, fotografia e filmagem": "Copying, photography and filming",
    "servicos de seguranca, prestados por empresa especializada": "Security services from a specialized company",
    "servicos postais, vedada a aquisicao de selos": "Postage (buying stamps is not allowed)",
    "acesso a internet, tv a cabo e telefonia": "Internet access, cable TV and phone",
    "aquisicao agua cafe cha acucar adocante copos": "Water, coffee, tea, sugar, sweetener and cups",
    "aquisicao de material de limpeza e de higienizacao": "Cleaning and hygiene supplies",
    "consultoria": "Consulting",
    "contas de telefone fixo e movel": "Landline and mobile phone bills",
    "divulgacao do mandato parlamentar": "Publicizing their work as a legislator",
    "hospedagem e passagem do deputado": "Lodging and tickets for the deputy",
    "hospedagem servidores do gabinete": "Lodging for office staff",
    "i p t u": "Property tax (IPTU)",
    "locacao de bens moveis e equipamentos": "Furniture and equipment rental",
    "locacao ou aquisicao de licenca do uso de software": "Software licenses (rental or purchase)",
    "mao de obra servicos de manutencao imovel locado": "Labor for maintenance of the rented property",
    "material de expediente e suprimento de informatica": "Office and computer supplies",
    "passagens servidores do gabinete": "Tickets for office staff",
    "pesquisa socio economicas": "Socioeconomic research",
    "servico de agua e esgoto": "Water and sewage services",
    "servico de empresas especializada em seguranca": "Security services from specialized companies",
    "servico de energia eletrica": "Electricity",
    "servicos de advogados": "Legal services (lawyers)",
    "servicos de contabilidade": "Accounting services",
    "servicos de informatica": "IT services",
    "taxas ordinarias de condominios": "Condo fees",
    "tcr": "TCR fee",
    "assessoria juridica": "Legal advice",
    "consultorias e trabalhos tecnicos": "Consulting and technical work",
    "imoveis": "Property",
    "servicos de seguranca": "Security services",
    "servicos de telecomunicacoes em geral": "Telecommunications services",
    "deslocamentos": "Travel",
    "despesas do escritorio de apoio": "Support office costs",
    "divulgacao de atividades parl": "Publicizing their work as a legislator",
    "producao de videos ou documentarios": "Video or documentary production",
    "sem detalhamento na pagina": "No breakdown on the official page",
    "servico de seguranca": "Security services",
    "servicos de entrega": "Delivery services",
    "servicos graficos e informacionais": "Printing and information services",
    "tecnologia da informacao": "Information technology",
    "telecomunicacoes": "Telecommunications",
    // Câmara Municipal de Porto Alegre (cota mensal dos gabinetes, QBM)
    "indenizacao por uso de veiculo particular": "Reimbursement for using a private vehicle",
    "reprografia": "Photocopying",
    "viagens": "Travel",
    "produtos e servicos de ti": "IT products and services",
    // Câmara Municipal de São Paulo (SisGV)
    "aplicativo ottcs - deslocamento": "Ride-hailing apps",
    "assinatura de jornais e revistas": "Newspaper and magazine subscriptions",
    "combustivel": "Fuel",
    "composicao/arte/diagramacao/producao/impressao grafica": "Graphic design and printing",
    "contratacao de pessoa juridica": "Services hired from companies",
    "correios": "Postage",
    "despesas relacionadas ao imovel locado - inciso xvi do art. 3º do ato 971/07": "Costs of the rented office",
    "elaboracao/manutencao de site/hospedagem": "Website creation, upkeep and hosting",
    "estacionamento": "Parking",
    "eventos/seminarios": "Events and seminars",
    "intermediado - correios": "Postage (contracted by the City Council)",
    "intermediado - locacao veiculos hibridos": "Hybrid vehicle rental (contracted by the City Council)",
    "limpeza de veiculos": "Vehicle cleaning",
    "livros": "Books",
    "locacao de imovel de pessoa fisica - inciso xvi do art 3º do ato 971/07": "Office rental (from an individual)",
    "locacao de imovel de pessoa juridica - inciso xvi do art. 3º do ato 971/07": "Office rental (from a company)",
    "locacao de veiculo": "Vehicle rental",
    "locacao de veiculos onix": "Vehicle rental (Onix)",
    "material de escritorio e outros materiais de consumo": "Office supplies and other consumables",
    "producao de conteudo digital/edicao de videos/imagens/audios/textos para internet e redes sociais - inciso xvii do art. 3º do ato 971/07": "Digital content for the internet and social media (videos, images, audio, text)",
    "provedor de internet": "Internet service",
    "reprografia (xerox/encadernacao)": "Photocopying and binding",
    "telefone fixo": "Landline phone",
    "telefone movel": "Mobile phone",
    "consultoria contabil": "Accounting consulting",
    "consultoria de comunicacao e marketing": "Communication and marketing consulting",
    "consultoria juridica": "Legal consulting",
    "cursos, palestras e eventos": "Courses, talks and events",
    "generos alimenticios": "Food supplies",
    "interprete de libras": "Sign language (Libras) interpreter",
    "manutencao de escritorio": "Office upkeep",
    "outras consultorias e assessorias": "Other consulting and advisory services",
    "outras despesas": "Other expenses",
    "sem a divisao por tipo (a descricao do mes nao soma o valor pago)": "Not split by type (the month's description does not add up to the amount paid)",
    "viagens, estacionamento e pedagio": "Travel, parking and tolls"
  };
  D.gasto = function (tipo) {
    if (!EP.en) return esc(tipo);
    var en = GASTOS[EP.norm(tipo)];
    return en ? esc(en) : D.ptHtml(tipo, true);
  };

  // ---------------------------------------------------------------- comissões: papel de cada um
  var PAPEIS = {
    "titular": "Full member", "suplente": "Alternate member", "presidente": "Chair", "presidenta": "Chair", "vice-presidente": "Vice-chair", "vice-presidenta": "Vice-chair",
    "relator": "Rapporteur", "relatora": "Rapporteur", "relator-parcial": "Partial rapporteur", "relatora-parcial": "Partial rapporteur", "relator-geral": "General rapporteur",
    "relatora-geral": "General rapporteur", "sub-relator": "Deputy rapporteur", "sub-relatora": "Deputy rapporteur", "coordenador": "Coordinator", "coordenadora": "Coordinator",
    "subcoordenador": "Deputy coordinator", "subcoordenadora": "Deputy coordinator", "secretario": "Secretary", "secretaria": "Secretary",
    "suplente de secretario": "Alternate secretary", "suplente de secretaria": "Alternate secretary", "membro": "Member"
  };
  D.papel = function (p) {
    if (!p) return "";
    if (!EP.en) return esc(p);
    var m = /^(\d+)\s*[ºª°]\s*(.+)$/.exec(p), ord = "", resto = p;
    if (m) { ord = ({ 1: "1st ", 2: "2nd ", 3: "3rd " })[m[1]] || m[1] + "th "; resto = m[2]; }
    var en = PAPEIS[EP.norm(resto)];
    return en ? esc(ord + en) : D.ptHtml(p, true);
  };

  // ---------------------------------------------------------------- escolaridade e profissões
  var ESCOLA = {
    "superior": "Higher education", "superior completo": "College degree", "superior incompleto": "Some college", "pos-graduacao": "Postgraduate studies",
    "mestrado": "Master's degree", "mestrado incompleto": "Some master's studies", "doutorado": "Doctorate (PhD)", "doutorado incompleto": "Some doctoral studies",
    "ensino medio": "High school", "ensino medio completo": "High school", "ensino medio incompleto": "Some high school",
    "ensino fundamental": "Elementary school", "ensino fundamental completo": "Elementary school", "ensino fundamental incompleto": "Some elementary school",
    "primario": "Primary school", "primario incompleto": "Some primary school", "secundario": "Secondary school", "secundario incompleto": "Some secondary school",
    "le e escreve": "Can read and write"
  };
  D.escolaridade = function (v) {
    if (!v) return "";
    if (!EP.en) return esc(v);
    var en = ESCOLA[EP.norm(v)];
    return en ? esc(en) : D.ptHtml(v, true);
  };
  var PROF = {
    // ocupações como o TSE escreve (declaradas na candidatura)
    "agente de saude e sanitarista": "Health agent and sanitarian", "aposentado (exceto servidor publico)": "Retired (not a civil servant)", "aposentada (exceto servidor publico)": "Retired (not a civil servant)",
    "atleta profissional e tecnico em desportos": "Professional athlete and sports coach", "ator e diretor de espetaculos publicos": "Actor and show director", "bancario e economiario": "Bank employee",
    "bancaria e economiaria": "Bank employee", "deputado": "Legislator (deputy)", "deputada": "Legislator (deputy)",
    "dona de casa": "Homemaker", "estudante, bolsista, estagiario e assemelhados": "Student or intern", "estudante, bolsista, estagiaria e assemelhados": "Student or intern",
    "farmaceutico": "Pharmacist", "farmaceutica": "Pharmacist", "fisioterapeuta e terapeuta ocupacional": "Physical or occupational therapist",
    "fotografo e assemelhados": "Photographer", "jornalista e redator": "Journalist and writer", "membro das forcas armadas": "Member of the armed forces",
    "ministro de estado": "Government minister", "ministra de estado": "Government minister", "operador de equipamento de radio, televisao, som e cinema": "Radio, TV, sound and film equipment operator",
    "policial civil": "Civil police officer", "policial militar": "Military police officer", "produtor agropecuario": "Farmer and rancher",
    "produtora agropecuaria": "Farmer and rancher", "professor de ensino medio": "High school teacher", "professora de ensino medio": "High school teacher",
    "professor de ensino superior": "University professor", "professora de ensino superior": "University professor", "relacoes-publicas": "Public relations professional",
    "sacerdote ou membro de ordem ou seita religiosa": "Priest or member of a religious order", "senador": "Senator", "senadora": "Senator",
    "servidor publico civil aposentado": "Retired civil servant", "servidora publica civil aposentada": "Retired civil servant", "servidor publico estadual": "State civil servant",
    "servidora publica estadual": "State civil servant", "servidor publico federal": "Federal civil servant", "servidora publica federal": "Federal civil servant",
    "servidor publico municipal": "City civil servant", "servidora publica municipal": "City civil servant", "sociologo": "Sociologist",
    "sociologa": "Sociologist", "torneiro mecanico": "Lathe operator (machinist)", "trabalhador rural": "Farm worker",
    "trabalhadora rural": "Farm worker", "tecnico de eletricidade, eletronica e telecomunicacoes": "Electrical, electronics and telecom technician", "veterinario": "Veterinarian",
    "veterinaria": "Veterinarian",
    "empresario": "Business owner", "empresaria": "Business owner", "advogado": "Lawyer", "advogada": "Lawyer", "administrador": "Administrator", "administradora": "Administrator",
    "professor": "Teacher", "professora": "Teacher", "professor universitario": "University professor", "professora universitaria": "University professor",
    "medico": "Doctor", "medica": "Doctor", "medico veterinario": "Veterinarian", "medica veterinaria": "Veterinarian", "engenheiro": "Engineer", "engenheira": "Engineer",
    "jornalista": "Journalist", "servidor publico": "Civil servant", "servidora publica": "Civil servant", "policial": "Police officer", "agricultor": "Farmer", "agricultora": "Farmer",
    "comunicador": "Broadcaster", "comunicadora": "Broadcaster", "economista": "Economist", "agropecuarista": "Farmer and rancher", "pecuarista": "Rancher",
    "delegado de policia": "Police chief", "delegada de policia": "Police chief", "pastor": "Pastor", "pastora": "Pastor", "comerciario": "Retail worker", "comerciaria": "Retail worker",
    "comerciante": "Shopkeeper", "escritor": "Writer", "escritora": "Writer", "gestor publico": "Public manager", "gestora publica": "Public manager", "militar": "Military",
    "pedagogo": "Educator", "pedagoga": "Educator", "profissao nao declarada": "Not declared", "corretor": "Broker", "corretora": "Broker", "metalurgico": "Metalworker",
    "metalurgica": "Metalworker", "sindicalista": "Union leader", "cientista politico": "Political scientist", "cientista politica": "Political scientist",
    "teologo": "Theologian", "teologa": "Theologian", "bancario": "Bank worker", "bancaria": "Bank worker", "politico": "Politician", "politica": "Politician",
    "consultor": "Consultant", "consultora": "Consultant", "atleta profissional": "Professional athlete", "padre": "Priest", "ator": "Actor", "atriz": "Actress",
    "publicitario": "Advertising professional", "publicitaria": "Advertising professional", "enfermeiro": "Nurse", "enfermeira": "Nurse", "assistente social": "Social worker",
    "profissional tecnico": "Technician", "profissional tecnica": "Technician", "vendedor": "Salesperson", "vendedora": "Salesperson", "arquiteto": "Architect", "arquiteta": "Architect",
    "contador": "Accountant", "contadora": "Accountant", "musico": "Musician", "musica": "Musician", "eletricista": "Electrician", "empregado publico": "Public employee",
    "empregada publica": "Public employee", "auxiliar de enfermagem": "Nursing assistant", "bombeiro": "Firefighter", "bombeira": "Firefighter", "defensor publico": "Public defender",
    "defensora publica": "Public defender", "estudante": "Student", "filosofo": "Philosopher", "filosofa": "Philosopher", "psicologo": "Psychologist", "psicologa": "Psychologist",
    "agronomo": "Agronomist", "agronoma": "Agronomist", "auditor": "Auditor", "auditora": "Auditor", "historiador": "Historian", "historiadora": "Historian", "pescador": "Fisher",
    "pescadora": "Fisher", "bispo": "Bishop", "motorista profissional": "Professional driver", "fotografo": "Photographer", "fotografa": "Photographer", "tradutor": "Translator",
    "tradutora": "Translator", "secretario": "Secretary", "secretaria": "Secretary", "bibliotecario": "Librarian", "bibliotecaria": "Librarian", "dentista": "Dentist",
    "cirurgiao-dentista": "Dentist", "cirurgia-dentista": "Dentist", "relacoes publicas": "Public relations", "proprietario rural": "Landowner", "proprietaria rural": "Landowner",
    "desenhista": "Draftsperson", "sanitarista": "Public health specialist", "extensionista": "Rural extension worker", "auxiliar administrativo": "Administrative assistant",
    "auxiliar administrativa": "Administrative assistant", "jornaleiro": "Newspaper seller", "profissional autonomo": "Self-employed", "profissional autonoma": "Self-employed",
    "serventuario da justica": "Court clerk", "serventuaria da justica": "Court clerk", "medico (anestesiologista)": "Doctor (anesthesiologist)"
  };
  D.profissao = function (v) {
    if (!v) return "";
    if (!EP.en) return esc(v);
    var n = EP.norm(v).replace(/\s*\((?:a|o)\)$/, "");
    var en = PROF[n] || PROF[n.replace(/\s*\(.*\)$/, "")];
    return en ? esc(en) : D.ptHtml(v, true);
  };

  // ---------------------------------------------------------------- ministérios
  var MIN = {
    "agricultura e pecuaria": "Agriculture and Livestock", "cidades": "Cities", "ciencia, tecnologia e inovacao": "Science, Technology and Innovation",
    "comunicacoes": "Communications", "cultura": "Culture", "defesa": "Defense", "desenvolvimento agrario e agricultura familiar": "Agrarian Development and Family Farming",
    "desenvolvimento e assistencia social, familia e combate a fome": "Social Development, Family and the Fight Against Hunger",
    "desenvolvimento, industria, comercio e servicos": "Development, Industry, Trade and Services", "direitos humanos e da cidadania": "Human Rights and Citizenship",
    "direitos humanos e cidadania": "Human Rights and Citizenship", "educacao": "Education",
    "empreendedorismo, da microempresa e da empresa de pequeno porte": "Entrepreneurship and Small Business", "esporte": "Sports", "fazenda": "Finance",
    "gestao e da inovacao em servicos publicos": "Management and Innovation in Public Services", "gestao e inovacao em servicos publicos": "Management and Innovation in Public Services",
    "igualdade racial": "Racial Equality", "integracao e do desenvolvimento regional": "Integration and Regional Development",
    "integracao e desenvolvimento regional": "Integration and Regional Development", "justica e seguranca publica": "Justice and Public Security",
    "meio ambiente e mudanca do clima": "Environment and Climate Change", "minas e energia": "Mines and Energy", "mulheres": "Women", "pesca e aquicultura": "Fisheries and Aquaculture",
    "planejamento e orcamento": "Planning and Budget", "portos e aeroportos": "Ports and Airports", "povos indigenas": "Indigenous Peoples", "previdencia social": "Social Security",
    "relacoes exteriores": "Foreign Affairs", "saude": "Health", "trabalho e emprego": "Labor and Employment", "transportes": "Transport", "turismo": "Tourism"
  };
  var ORGAOS = {
    "casa civil": "Chief of Staff's Office (Casa Civil)", "secretaria-geral": "General Secretariat of the Presidency",
    "secretaria de relacoes institucionais": "Secretariat of Institutional Relations", "secretaria de comunicacao social": "Secretariat of Social Communication",
    "gabinete de seguranca institucional": "Institutional Security Office", "advocacia-geral da uniao": "Attorney General's Office (AGU)",
    "controladoria-geral da uniao": "Office of the Comptroller General (CGU)", "banco central": "Central Bank", "banco central do brasil": "Central Bank of Brazil"
  };
  D.ministerio = function (nome) {
    if (!nome) return "";
    if (!EP.en) return nome;
    var n = EP.norm(nome).replace(/\s*\([^)]*\)\s*$/, "").replace(/ da presidencia( da republica)?$/, "");
    var temPrefixo = /^ministerio /.test(n);
    var miolo = n.replace(/^ministerio (?:da |do |das |dos |de )?/, "");
    if (MIN[miolo]) return (temPrefixo ? "Ministry of " : "") + MIN[miolo];
    if (ORGAOS[n]) return ORGAOS[n];
    return null;
  };

  // ---------------------------------------------------------------- votos e resultados
  // [categoria (cor), curto pt, curto en, explicação pt, explicação en]
  var VOTOS = {
    "sim": ["Sim", "Sim", "Yes"], "nao": ["Não", "Não", "No"], "abstencao": ["Abstenção", "Abstenção", "Abstained"], "obstrucao": ["Obstrução", "Obstrução", "Obstruction"],
    "artigo 17": ["Outro", "Presidia", "Presiding", "Presidia a sessão (art. 17 do Regimento da Câmara)", "Was presiding over the session (art. 17 of the Chamber's rules)"],
    "presidente (art. 51 risf)": ["Outro", "Presidia", "Presiding", "Presidia a sessão (art. 51 do Regimento do Senado)", "Was presiding over the session (art. 51 of the Senate's rules)"],
    "ps": ["Outro", "Presidia", "Presiding", "Presidiu a sessão", "Presided over the session"],
    "pr": ["Outro", "Presidia", "Presiding", "Presidiu a votação", "Presided over the vote"],
    "p-nrv": ["Outro", "Não votou", "Did not vote", "Estava presente, mas não registrou voto", "Was present, but did not vote"],
    "nr": ["Outro", "Não votou", "Did not vote", "Não registrou voto", "Did not vote"],
    "p-od": ["Obstrução", "Obstrução", "Obstruction", "Presente, em obstrução declarada", "Present, declaring obstruction"],
    "ob": ["Obstrução", "Obstrução", "Obstruction", "Em obstrução declarada", "Declaring obstruction"],
    "ncom": ["Outro", "Ausente", "Absent", "Não compareceu", "Did not attend"],
    "aus": ["Outro", "Ausente", "Absent", "Avisou que estaria ausente", "Gave notice of absence"],
    "ap": ["Outro", "Em atividade", "On duty", "Em atividade parlamentar", "Away on parliamentary duty"],
    "mis": ["Outro", "Em missão", "On mission", "Em missão oficial do Senado, no Brasil ou no exterior", "On an official Senate mission, in Brazil or abroad"],
    "rep": ["Outro", "Representando", "Representing", "Representando a Casa em uma solenidade", "Representing the Senate at a ceremony"],
    "ls": ["Outro", "De licença", "On leave", "Licença saúde", "Sick leave"],
    "lp": ["Outro", "De licença", "On leave", "Licença particular", "Personal leave"],
    "lap": ["Outro", "De licença", "On leave", "Licença paternidade ou ao adotante", "Paternity or adoption leave"],
    "lg": ["Outro", "De licença", "On leave", "Licença à gestante", "Maternity leave"],
    "la": ["Outro", "De licença", "On leave", "Licença à adotante", "Adoption leave"],
    "afo": ["Outro", "Afastado", "Away", "Afastado do exercício do mandato", "Temporarily away from office"],
    "na": ["Outro", "Outro", "Other", "Ausência sem motivo informado", "Absence with no reason given"],
    // Câmara Municipal de Porto Alegre
    "justificado": ["Outro", "Justificado", "Excused", "Ausência justificada", "Excused absence"],
    "representacao externa": ["Outro", "Representação externa", "Away", "Representava a Câmara fora dela", "Was representing the City Council elsewhere"]
  };
  D.voto = function (v) {
    var x = VOTOS[EP.norm(v || "")];
    if (!x) return { cat: /^n[aã]o$/i.test(v || "") ? "Não" : "Outro", curto: v || "—", longo: "" };
    return { cat: x[0], curto: EP.tr(x[1], x[2]), longo: x[3] ? EP.tr(x[3], x[4]) : "" };
  };
  D.nomeVoto = function (cat) {
    return EP.tr(cat, { "Sim": "Yes", "Não": "No", "Abstenção": "Abstained", "Obstrução": "Obstruction", "Outro": "Other" }[cat] || cat);
  };
  D.resultado = function (r) {
    if (!r) return "";
    if (!EP.en) return esc(r);
    var n = EP.norm(r);
    // Câmaras Municipais (SAPL, Porto Alegre): o resultado diz o que foi votado ("Veto Mantido", "Emenda Rejeitada"...)
    if (/veto mantido/.test(n)) return "Veto upheld";
    if (/veto (rejeitad|derrubad)/.test(n)) return "Veto overridden";
    if (/^emenda aprovada/.test(n)) return "Amendment approved";
    if (/^emenda rejeitada/.test(n)) return "Amendment rejected";
    if (/^parecer aprovado/.test(n)) return "Committee report approved";
    if (/^parecer rejeitado/.test(n)) return "Committee report rejected";
    if (/^aprovad/.test(n)) return "Approved";
    if (/^rejeitad/.test(n)) return "Rejected";
    if (/^mantid/.test(n)) return "Upheld";      // veto mantido (Alece, ALPB)
    if (/^aceit/.test(n)) return "Accepted";     // veto parcial aceito (ALRS)
    return D.ptHtml(r, true);
  };

  // período livre ("2001–2006 e 2011–2018", "eleito em 1972")
  D.periodo = function (t) {
    if (!t) return "";
    if (!EP.en) return esc(t);
    var m = /^eleit[oa] em (\d{4})$/i.exec(t);
    if (m) return "elected in " + m[1];
    return esc(String(t).replace(/ e /g, " and "));
  };

  // ---------------------------------------------------------------- endereço canônico e rodapé
  // a versão em inglês é o mesmo endereço com ?lang=en: o "canonical" aponta para a versão que está aberta
  D.canonico = function (params) {
    var l = document.querySelector('link[rel="canonical"]');
    if (!l) return;
    var u = new URL(l.href, location.href);
    u.search = "";
    if (params) Object.keys(params).forEach(function (k) { if (params[k] != null && params[k] !== "") u.searchParams.set(k, params[k]); });
    if (EP.en) u.searchParams.set("lang", "en");
    l.href = u.href;
  };
  // "Viu algo errado?": link do formulário (js/config.js) ou, se ainda não existir, a explicação de como avisar
  D.rodapeErros = function (el, pt, en) {
    if (!el) return;
    var f = (window.EP_CONFIG || {}).formularioErros;
    var p = EP.tr(pt || "Viu algo errado ou que parece puxar para um lado?", en || "Did you see something wrong, or something that seems to take sides?");
    el.innerHTML = '<span aria-hidden="true">🔎 </span>' + esc(p) + " " + (f ?
      '<a href="' + esc(f) + '" target="_blank" rel="noopener">' + EP.tr("Avise aqui", "Let us know here") + '<span class="sr"> ' + EP.tr("(abre em outra aba)", "(opens in a new tab)") + "</span></a>" :
      '<a href="imparcialidade.html#avisar">' + EP.tr("Veja como avisar", "See how to tell us") + "</a>");
  };
})();
