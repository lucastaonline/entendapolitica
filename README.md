# Entenda Política

Site estático (HTML, CSS e JS puros, sem build no navegador) que explica como a política brasileira funciona, de um jeito que **uma criança de 10 anos entenda**, e mostra **quem está no mandato hoje**, com tudo o que cada pessoa propôs, o que foi aprovado e o que virou lei. **Tudo com fonte. Tudo imparcial.**

Mesma identidade visual do [Entenda o 2º turno](https://entendaosegundoturno.vercel.app): fundo creme, azul `#1f3a5f`, amarelo `#f2b705`, letra do sistema bem grossa, emojis, botões "gordinhos" e peças 3D feitas só com CSS.

## As 4 portas da página inicial

1. **Entenda a política** (`entenda.html`): um **mapa 3D** (tabuleiro) com 10 paradas: o que é política (escola), os Três Poderes, país/estado/cidade, os cargos (torre), o Congresso (no centro), como nasce uma lei, eleições (urna), quem julga e fiscaliza (tribunal), como participar (palanque) e, numa faixa ao norte, a urna eletrônica por dentro (a urna com o boletim saindo). Uma trilha amarela sugere a ordem, mas dá para clicar em qualquer lugar. Ao clicar, a câmera "mergulha" no lugar e abre a **aula daquela parada**: uma apresentação com muito 3D (escadas para processos, cartões que viram, quadrinhos que folheiam, quiz e simuladores). No fim: estrela no mapa e "próxima parada". O progresso fica salvo no aparelho. A parada 10, a urna eletrônica por dentro, mostra o caminho do voto em 12 etapas (antes, no dia e depois), quem confere cada uma, o que o Teste Público já achou e o que foi corrigido, as camadas de proteção, perguntas comuns (inclusive o que já foi votado e decidido sobre o voto impresso) e uma parte técnica opcional (hash, assinatura digital, cadeia de confiança, RDV, log, QR Code e onde baixar os arquivos oficiais), com joguinhos: o caminho do voto animado, o lacre digital (hash de verdade no navegador) e "confira o boletim" (dados inventados). Fontes: só TSE, Planalto, STF e Câmara; cada fato foi conferido de novo, por outra pessoa, antes de ir ao ar.
2. **A política do Brasil** (`brasil.html`): presidente, vice, ministros, os 81 senadores e os 513 deputados federais, com busca por qualquer político, e o Supremo Tribunal Federal (STF), cujos ministros não são eleitos: como alguém chega ao STF, quem preside, os ministros na ordem oficial do tribunal (quem indicou cada um, desde quando está no STF, a Turma e a aposentadoria obrigatória aos 75 anos) e as Turmas. Cada ministro tem um perfil (`pessoa.html?id=stf-<slug>`) com a indicação, o placar na CCJ e no Plenário do Senado, o decreto de nomeação e a posse.
3. **A política do meu estado** (`estado.html`): a pessoa escolhe o estado num mapa 3D com o formato real de cada estado (malha do IBGE; os estados pequenos têm a sigla num selo fora deles, ligado por uma linha) ou digitando o nome. Mostra governador e vice, os senadores e deputados federais do estado e os deputados estaduais. No fim, um campo leva para a página da cidade.
4. **A política da minha cidade** (`cidade.html`): a pessoa digita o nome da cidade (as 5.569 do Brasil, com o estado ao lado para desempatar) e vê prefeito, vice e vereadores, além do que cada um faz. Brasília e Fernando de Noronha têm explicação própria (não têm prefeitura comum). Endereço: `cidade.html?ibge=<código IBGE>`; os endereços antigos `estado.html?uf=XX&cidade=<IBGE>` levam para lá.

Nas páginas do Brasil, do estado e da cidade, o campo **Ver outro mandato** mostra quem foi **eleito** em cada mandato anterior, segundo o TSE: desde 1995 no Brasil e nos estados, desde 1997 nas cidades. O padrão continua sendo o mandato de hoje; o passado tem endereço próprio (`brasil.html?mandato=2019`, `estado.html?uf=BA&mandato=2019`, `cidade.html?ibge=2927408&mandato=2021`) e uma faixa avisando, em texto, que é o passado.

Até a posse de quem foi eleito em 2026, as mesmas páginas mostram **quem assume**. No Brasil, a seção **Quem assume em 2027** (`brasil.html#quem-assume`): as datas de posse, o presidente e o vice eleitos, o Senado a partir de 1º/2/2027 (os 54 eleitos em 2026 e os 27 que continuam até 2031; quem foi eleito governador sai na posse, e no lugar aparece o 1º suplente da chapa de 2022) e a Câmara a partir de 1º/2/2027 (plenário por partido e lista com filtros), com quantos foram reeleitos e quantos chegam agora (só a contagem). No estado (`estado.html?uf=XX#quem-assume`): governador e vice eleitos, os senadores eleitos com os 2 suplentes, quem continua até 2031, os deputados federais do estado e a Assembleia (ou a Câmara Legislativa do DF) a partir da posse, com a data de cada posse. Na cidade (`cidade.html?ibge=...#proxima-eleicao`): a próxima eleição municipal (a data, o que vai ser escolhido e a posse, pela Constituição e pela Lei 9.504/1997), as eleições suplementares da cidade (com quem foi eleito, pelo TSE) e quem tem cargo na cidade e foi eleito em 2026. Quem já tem cargo leva ao perfil de hoje, com o selo "Eleito em 2026"; quem foi eleito e não tem cargo eletivo hoje ganha um perfil com os dados do TSE até a posse (`pessoa.html?id=e26-<UF>-<SQ_CANDIDATO>`; `BR` para presidente e vice): foto, partido (e federação), votos e situação, ficha, bens declarados (o tipo e o valor de cada bem) e o link da candidatura no TSE. Cada cargo sai no dia da sua posse, e a seção some sozinha depois da última; um endereço `e26-` antigo mostra uma mensagem com o link para a busca.

Cada pessoa tem uma página (`pessoa.html?id=...`) com ficha, propostas (com explicação simples + texto oficial + link da fonte), situação de cada proposta, votações, gastos e eleições. O botão **Voltar** leva para a página de onde a pessoa veio (o Brasil, o estado, a cidade, uma votação ou a busca), guardada nesta aba pelo `js/comum.js` (`EP.gravaVolta`/`EP.leVolta`); se ela veio direto de lá, usa o histórico do navegador, e a lista reaparece como estava. Aberto por link direto, vai para a lista do cargo.

**Votações** (`votacoes.html`): todas as votações do Plenário em que o voto de cada um fica registrado (nominais), na Câmara e no Senado, desde o começo da legislatura (fevereiro de 2023), da mais nova para a mais antiga, com filtros (Casa, ano, tipo, resultado) e busca. Cada votação tem a sua página (`votacao.html?casa=camara&id=<id da Câmara>` ou `?casa=senado&id=<código do Senado>`): o que foi votado (descrição oficial e a ementa da proposta), o resultado com o placar e um plenário 3D em que cada cadeira é uma pessoa (pintada pelo voto), a regra para aprovar quando ela é clara (PEC, lei complementar, lei comum, urgência do art. 155 da Câmara), como cada partido votou (do partido com mais gente para o com menos, só contagem) com a orientação que a liderança publicou, a lista completa de orientações e quem votou o quê (filtros por voto, partido, estado e nome). Na página do Brasil, o bloco "Como o Congresso votou" mostra as votações mais recentes do texto principal (uma por proposta). No perfil, "Como votou" tem filtro por tipo e cada votação leva para a página dela.

Cada Casa (Senado, Câmara, Assembleia, Câmara Municipal) tem um **plenário 3D por partido**: cada fatia é um partido, do maior para o menor, com a sigla em cima (as que não cabem aparecem ao passar o mouse). Passar o mouse num partido (na lista, numa cadeira ou na sigla), ou chegar nele com o Tab, acende as cadeiras dele em amarelo; tocar ou clicar mostra só quem é dele.

## Idiomas (português e inglês)

O site tem versão em inglês para quem é de fora do Brasil (`?lang=en`; a escolha fica salva no aparelho; botão 🌐 no topo).
- **HTML:** o português fica no HTML e o inglês ao lado, em atributos: `data-en`, `data-en-html`, `data-en-title`, `data-en-placeholder`, `data-en-aria-label`, `data-en-content` (meta). O `js/comum.js` troca tudo quando a página está em inglês.
- **JavaScript:** `EP.tr("português", "English")`. Números, datas e dinheiro saem no formato do idioma (`EP.num`, `EP.data`, `EP.dinheiro`).
- **Conteúdo do mapa:** `conteudo/entenda/en/parte-N.json` (mesma estrutura do português). Se faltar, a parada aparece em português com aviso. Termos em português no meio do texto em inglês vão entre chaves duplas, `{{título de eleitor}}`, e viram `<span lang="pt-BR">` (o leitor de tela pronuncia em português). No HTML e no JavaScript, use o `<span lang="pt-BR">` direto (ou `EP.md`, que entende `**negrito**` e `{{termo}}`).
- **Dados:** campos `*_en` quando existem (ex.: `txt_en` da eleição de 2026, `s_en` da explicação simples). Textos oficiais em português (ementas, nomes) aparecem marcados com `lang="pt-BR"`.

## Acessibilidade

- Menu ♿ em todas as páginas: tamanho da letra (4 tamanhos), alto contraste, menos movimento, mais espaço no texto, ouvir a página (voz do aparelho), Libras (VLibras, do governo federal) e idioma. As escolhas ficam salvas e são aplicadas antes de a página aparecer (script curto no `<head>`).
- Tudo funciona pelo teclado; janelas prendem o foco e fecham com Esc; o mapa 3D tem lista alternativa (📋) e cada parada é um botão com nome; as setas giram o mapa e trocam as páginas das aulas.
- Ao voltar de um perfil para a lista, a página rola até quem foi aberto e põe o foco nele (quem usa teclado ou leitor de tela continua de onde parou). O plenário é só desenho (`aria-hidden`): tudo o que ele mostra está também na lista de partidos, que são botões.
- Respeita "reduzir movimento" do aparelho. Textos oficiais e termos em português dentro da página em inglês têm `lang="pt-BR"`.
- **Nenhum `<select>` comum:** toda lista de escolha é um campo com busca (`EP.combo` e `EP.comboSelect`, em `js/comum.js`, no padrão ARIA 1.2 de combobox com lista). A pessoa digita e as opções aparecem; vale sem acento e fora de ordem ("bom jesus pi"), e cada palavra digitada precisa ser o começo de uma palavra da opção (se assim não achar nada, vale qualquer pedaço). Setas, Enter e Esc funcionam; o leitor de tela ouve quantas opções há.
- Auditoria automática: `python testes/acessibilidade.py pagina.html "pagina.html?lang=en" [--mobile]` (axe-core, WCAG 2.2 AA).

## Fases combinadas

1. **Fase 1:** federal completo (presidente, vice, ministros, senadores, deputados federais) + ficha básica (TSE) de governadores, deputados estaduais, prefeitos e vereadores. **Feita**, com as votações da Câmara e do Senado e os mandatos anteriores.
2. **Fase 2:** propostas dos deputados estaduais, Assembleia por Assembleia. **Feita em 21 das 27** (lista oficial nas 27; votações em 10; gastos em 14): ver "Assembleias Legislativas".
3. **Fase 3:** vereadores das capitais e das Câmaras com dados abertos (ex.: SAPL/Interlegis). **Capitais feitas** (lista oficial em 19 de 26, propostas em 8) e 804 Câmaras com SAPL no site; as outras 14 da lista entram aos poucos pelo robô das cidades (ver "Câmaras Municipais").

Mandatos: o site mostra **quem está no cargo hoje** e marca quem foi **eleito/reeleito em 2026**. As listas trocam sozinhas no dia da posse de quem foi eleito (presidente em 5/1/2027 e governadores em 6/1/2027, pela Emenda Constitucional 111/2021; Congresso em 1º/2/2027; prefeitos e vereadores em 1º/1/2029). Qual é o mandato de hoje sai das datas de posse (`scripts/mandatos.py`, a mesma regra para os coletores e para o navegador), nunca de um ano escrito no código. Os mandatos anteriores (quem foi eleito em cada um, segundo o TSE) ficam no campo **Ver outro mandato**.

## Regras de imparcialidade (valem para tudo)

1. **Mesma régua para todos.** Os mesmos campos, calculados do mesmo jeito, para todo mundo.
2. **Fonte em tudo.** Todo bloco de informação tem `fonte` (órgão oficial: Câmara, Senado, TSE, IBGE, Planalto, Diário Oficial; ou imprensa quando não houver fonte oficial).
3. **Ordem neutra.** Listas em ordem alfabética, ou na ordem oficial da própria instituição quando ela existe (os ministros do STF aparecem como o STF os lista: o presidente, o vice e os outros por antiguidade, nunca agrupados por quem os indicou). Nada de ranking de "melhor" ou "pior".
4. **Sem cores de partido.** Nenhum partido tem cor própria. No plenário, cada fatia é um partido e as fatias alternam dois tons neutros de azul só para separar uma da vizinha (do maior partido para o menor); o partido em destaque acende em amarelo.
5. **Linguagem neutra.** Sem adjetivos de valor ("bom", "ruim", "polêmico", "importante"). Explicações simples dizem **o que a proposta faz**, nunca se é boa.
6. **Quem fez de verdade.** Separar **autor(a) principal** de **coautor(a)** (quem só assinou junto).
7. **Contexto nos números.** Ex.: "propor muitos projetos não quer dizer trabalhar mais ou melhor".
8. **Canal para corrigir.** Formulário "Viu algo errado ou que parece puxar para um lado?".

## Estrutura

```
index.html            página inicial (4 portas)
entenda.html          mapa 3D da política + aulas de cada parada (lê conteudo/entenda/[en/]parte-N.json)
brasil.html           política do Brasil (lê dados/executivo.json, dados/senado.json, dados/camara.json, dados/stf.json e dados/eleitos/BR.json)
estado.html           política do meu estado (lê dados/mapa-brasil.json, dados/estados/UF.json, dados/cidades/UF.json e dados/eleitos/UF.json)
cidade.html           política da minha cidade (lê dados/cidades.json, dados/cidades/UF/IBGE.json e dados/eleitos/municipal.json)
pessoa.html           perfil de uma pessoa (lê dados/pessoas/<id>.json e dados/votacoes/<casa>.json; o perfil e26- lê dados/eleitos/<UF>.json)
votacoes.html         todas as votações nominais da Câmara e do Senado (filtros por Casa, ano, tipo e resultado; busca)
votacao.html          uma votação: o que foi votado, resultado com plenário 3D, como cada partido votou, orientações e quem votou o quê
404.html              endereço não encontrado (a Vercel usa sozinha), com as 4 portas
imparcialidade.html   como cuidamos da imparcialidade
dados.html            de onde vêm os dados, com que frequência são atualizados e os limites
css/base.css          visual comum (cores, botões, cartões, janela) + acessibilidade (contraste, movimento, espaçamento)
css/tres.css          peças 3D que vieram do site do 2º turno (urna, cubos, formas)
css/tres-politica.css peças 3D novas (Congresso, Três Poderes, níveis, escola, torre, tribunal, palanque, escada, urna com o boletim...)
css/mapa.css          o mundo 3D do mapa (chão, lotes, placas, câmera)
css/entenda.css       as aulas (slides em 3D)
css/votacoes.css      as duas páginas de votações e o bloco "Como o Congresso votou" do Brasil
css/historico.css     a faixa "Você está vendo o passado" e o campo de mandatos
css/stf.css           a seção do STF na página do Brasil e o perfil de cada ministro do STF
css/proximos.css      "Quem assume" (Brasil e estado), "A próxima eleição" (cidade) e o perfil e26- de quem foi eleito em 2026
js/comum.js           idioma, acessibilidade, janela, fontes, ouvir, Libras, formatação, listas com busca (EP.combo), compartilhar
js/casa.js            monta uma Casa (Senado, Câmara, Assembleia, Câmara Municipal): plenário 3D com fatias e siglas por partido, filtros e lista de cartões
js/brasil.js, js/estado.js, js/cidade.js, js/pessoa.js   as páginas do Brasil, do estado, da cidade e de cada pessoa
js/votacoes.js        ajudas comuns das votações (EP.VOT), a lista de votações e o bloco do Brasil (#votos-recentes)
js/votacao.js         a página de uma votação
js/historico.js       mandatos anteriores: o campo "Ver outro mandato" e a página do passado (Brasil, estado e cidade)
js/stf.js             ministros do STF (EP.stf): a seção #judiciario da página do Brasil e o perfil pessoa.html?id=stf-<slug>, montados no navegador a partir de dados/stf.json
js/proximos.js        quem foi eleito em 2026, até a posse (EP.eleitos): as seções "Quem assume" do Brasil e do estado, "A próxima eleição" da cidade e o perfil pessoa.html?id=e26-..., montados no navegador a partir de dados/eleitos/
js/tres.js, js/tres-politica.js   montam as peças 3D (cada modelo tem modo "cena" e modo "mundo")
js/mapa3d.js          monta o mapa 3D, câmera (voar até um lugar), girar, zoom, lista acessível
js/entenda.js         carrega o conteúdo, liga o mapa e as aulas (especificação dos slides no topo do arquivo)
conteudo/entenda/     texto das 10 paradas em português; conteudo/entenda/en/ em inglês
dados/                tudo o que os scripts geram (JSON); não edite à mão, exceto dados/manual/. dados/historico/ é feito por scripts/historico.py, que roda à mão
scripts/              coletores em Python (só biblioteca padrão + Pillow):
  camara.py, senado.py, executivo.py, tse.py   Câmara, Senado, presidente e vice, TSE e IBGE (todo dia)
  votacoes.py         categoria, placar, quórum e orientações de cada votação; grava dados/votacoes/<casa>/<id>.json (chamado pelo camara.py e pelo senado.py)
  legislativos.py     roda os coletores das Assembleias (scripts/assembleias/<uf>.py) e das Câmaras Municipais (scripts/camaras/c<IBGE>.py nas capitais; as Câmaras com SAPL de scripts/camaras/sapl_cidades.json)
  regional.py         ajudas comuns desses coletores (formato dos arquivos, casar cada pessoa com o TSE)
  mandatos.py         datas de posse e qual mandato está em curso em cada data (a regra da "virada" de mandato)
  simplificar.py, montar.py   explicações simples (IA) e a junção final (todo dia)
  historico.py, mapa.py       mandatos anteriores e mapa do Brasil (à mão)
  stf.py                      ministros do STF (sites do STF e Dados Abertos do Senado): roda no robô diário, mas só lê uma vez por semana
  eleitos.py                  quem foi eleito em 2026, até a posse (TSE): grava dados/eleitos/; roda no robô diário, logo depois do tse.py
  municipios/mapear.py        mapa das Câmaras Municipais e prefeituras (sites oficiais, sistema de propostas, Diário Oficial, pedido de informação)
  municipios/diarios.py       leis e vetos de cada prefeitura (Diários Oficiais e páginas oficiais de leis), só onde a contagem é segura
  atualizar_do_brasil.py      à mão, num computador no Brasil: lê de novo as Casas que os robôs do GitHub não conseguem ler e publica
.github/workflows/    atualizar.yml (robô diário) e cidades.yml (robô das cidades: o mapa das Câmaras e prefeituras e as leis e vetos das prefeituras, um grupo de estados por dia, e as Câmaras com SAPL, as cidades do dia da semana)
.vercelignore         o que vai para o repositório mas não para o site (scripts, testes e arquivos de trabalho dos coletores)
testes/               capturas de tela, auditoria de acessibilidade e amostras
```

Para ver no computador: `python -m http.server 8770` dentro da pasta e abra http://127.0.0.1:8770.

## Testes (com o servidor local acima rodando; precisam do Playwright com o Edge e, para acessibilidade, do axe-core em `../ferramentas/node_modules`)

- `python testes/captura.py index.html "pessoa.html?id=pres-lula&lang=en" --mobile --cheia`: capturas de tela em `testes/capturas/`, erros do console e rolagem para os lados.
- `python testes/acessibilidade.py brasil.html "brasil.html?lang=en" [--mobile]` e `--aulas` (todos os slides das 10 paradas, nos 2 idiomas): auditoria axe-core (WCAG 2.2 AA). Meta: 0 problemas.
- `python testes/verifica_texto.py "estado.html?uf=BA&lang=en" ...`: procura "undefined"/"null" e português solto na versão em inglês.
- `python testes/interacao.py`: teclado, busca, listas com busca (estado, cidade, filtros), página da cidade, 4 portas, filtros, mapa e menu de acessibilidade.
- `python testes/interacao_votacoes.py`: votações (lista, uma votação, bloco do Brasil e "Como votou" do perfil): teclado, filtros, "Mostrar mais" com o foco, números que batem com os dados, inglês, 320 px e axe-core depois de rolar e clicar.
- `python testes/interacao_historico.py`: mandatos anteriores (campo pelo teclado, páginas do passado no Brasil, estado e cidade, "Voltar para hoje", cidade que ainda não existia, virada de mandato com o relógio adiantado).
- `python testes/interacao_stf.py`: ministros do STF (a seção da página do Brasil: um cartão por ministro, na ordem oficial, a cadeira vazia, a presidência, as Turmas, as regras com fonte e o link para a parada 8; o perfil em português e em inglês, com o placar da CCJ e do Plenário do Senado, as datas, quem indicou, o decreto e as fontes, conferidos contra `dados/stf.json`; a busca; teclado, Voltar, 320 px, axe-core e nenhum erro de JavaScript).
- `python testes/stf_robo.py` (sem servidor e sem rede): o que o `scripts/stf.py` faz quando os sites caem (o `dados/stf.json` não muda nem um byte; com o Senado fora do ar, cada ministro fica com o bloco do Senado de antes; uma página do STF quebrada é recusada), os avisos de mudança na composição e a leitura uma vez por semana.
- `python testes/interacao_eleitos.py`: quem foi eleito em 2026 (a seção "Quem assume em 2027" do Brasil e do estado e "A próxima eleição" da cidade): os números da página conferidos contra `dados/eleitos/`, os filtros pelo teclado e os links (quem tem cargo vai ao perfil de hoje; quem não tem, ao `e26-`), o perfil `e26-` em português e em inglês (votos, bens com "Mostrar os outros", link do TSE, Voltar), o selo de quem já tem cargo, um endereço `e26-` que não existe mais, a busca e o sitemap, 320 px, axe-core depois de rolar e nenhum erro de JavaScript; e o `scripts/eleitos.py --hoje` nos dias seguintes às posses, numa pasta à parte (`.cache/eleitos/teste-posse`, apagada no fim).
- `python testes/interacao_urna.py`: a parada 10 (a urna eletrônica): mapa com 10 paradas e a placa 10 visível (computador, 390 e 320 px), aberta pelo mapa e pelo botão da parada 7, todos os slides pelo teclado, o caminho do voto, o lacre digital (o hash da página confere com o do Python, em SHA-256 e SHA-512), o boletim de exemplo, os quizzes, o pular da parte técnica, o progresso de quem já tinha 9 paradas, inglês sem português solto, "menos movimento", axe-core e nenhum erro de JavaScript.
- `python testes/interacao_camaras.py`: Câmaras Municipais (capitais e Câmaras com SAPL; só as que o `montar.py` já juntou à página da cidade): lista oficial na página da cidade, perfil do vereador com propostas e filtros, perfil do prefeito ("Como contamos", "A lei mais recente na fonte"), textos em inglês, cidades só com a lista; votações nominais (São Paulo, Porto Alegre, Recife e uma Câmara com SAPL: resumo, a votação mais nova, placar, link oficial, "Mostrar mais votações") e os gastos de São Paulo, conferidos contra os dados.
- `python testes/interacao_capitais_a.py`, `interacao_capitais_b.py` e `interacao_capitais_c.py`: as capitais cujas Câmaras são lidas em páginas do site (propostas, prefeito, notas, gastos e votações onde houver, inglês, 320 px).
- `python testes/interacao_prefeituras.py`: leis e vetos das prefeituras pelos Diários Oficiais (perfil do prefeito com a contagem, vetos totais e parciais, fontes, "Como contamos", o motivo e o link em "Onde ver mais", inglês, 320 px e axe-core).
- `python testes/diarios_titulos.py`, `python testes/diarios_falhas.py` e `python testes/diarios_robo.py` (sem servidor e sem rede; o último simula a primeira rodada do robô, com o cache vazio e todos os sites falhando: nenhum byte de `dados/prefeituras/` pode mudar): as regras que leem os títulos das leis e fazem as contagens dos Diários Oficiais, e o que acontece quando um site bloqueia, cai ou devolve uma página quebrada (a cidade fica pendente, com o que já estava publicado).
- `python testes/gerar_imagens.py`: gera os ícones e a imagem de compartilhamento (`testes/og.html` → `img/compartilhar.jpg`).
- Observação: as fotos do TSE não carregam no navegador sem janela dos testes (o firewall do TSE barra); num navegador normal, carregam.

## Como os dados são atualizados

`.github/workflows/atualizar.yml` roda todo dia às 6h (Brasília), nesta ordem:
1. `scripts/camara.py` (Câmara), `scripts/senado.py` (Senado), `scripts/executivo.py` (presidente e vice), `scripts/tse.py` (TSE e IBGE: estados, cidades, eleições, bens, busca), `scripts/eleitos.py` (quem foi eleito em 2026, até a posse; logo depois do `tse.py`) e `scripts/legislativos.py` (Assembleias Legislativas e Câmaras Municipais com dados abertos; se o site de uma Casa estiver fora do ar, fica a lista da última rodada que deu certo). O `camara.py` e o `senado.py` também gravam um arquivo por votação em `dados/votacoes/<casa>/` (com `scripts/votacoes.py`; para refazer só as votações a partir do que já foi baixado: `python scripts/votacoes.py --cache` e depois `python scripts/montar.py`);
2. `scripts/simplificar.py`: escreve, com IA, a explicação simples (português e inglês) das propostas que ainda não têm, a partir da ementa oficial (o texto oficial aparece sempre ao lado). Usa o GitHub Models com o token do próprio Actions (grátis, cerca de 2.800 propostas por dia, em no máximo 60 minutos: `MINUTOS`) ou uma chave da OpenAI no segredo `OPENAI_API_KEY` (mais rápido). Ordem: rodízio por pessoa (a cada rodada, cada político ganha a explicação da sua proposta mais nova que ainda falta), para todo mundo avançar no mesmo ritmo, sem prioridade para quem governa. Um programa confere cada explicação antes de publicar (no máximo 35 palavras em português e 45 em inglês, palavras de opinião proibidas, números e trechos entre aspas que precisam existir na ementa); a que for recusada 2 vezes fica só com o texto oficial (`dados/simples-recusadas.json`);
3. `scripts/montar.py`: junta tudo (TSE nos perfis, explicações simples nos perfis e nas votações, textos em inglês da eleição de 2026, listas oficiais das Assembleias e Câmaras nas páginas do estado e da cidade, os ministros do STF, os perfis e26- e os vereadores eleitos em 2026 na busca, sitemap);
4. faz commit só do que mudou de verdade (datas de consulta não contam) e a Vercel publica sozinha. Os caches (`.cache/`) são guardados no fim, mesmo se alguma etapa falhar ou o tempo acabar, para o que já foi baixado não se perder.

O robô das cidades (`.github/workflows/cidades.yml`, todo dia de madrugada, antes do diário; os dois nunca rodam ao mesmo tempo) atualiza, para o grupo de estados do dia, o mapa das Câmaras e prefeituras (`scripts/municipios/mapear.py --rodizio`) e as leis e vetos das prefeituras (`scripts/municipios/diarios.py --rodizio --minutos 40`), e as Câmaras com SAPL: as cidades do dia da semana e as que ainda não terminaram a primeira carga (`python scripts/legislativos.py sapl --parte hoje --pendentes --paralelo 40 --minutos 150`), com o cache `.cache/camaras` guardado entre as rodadas (o mesmo do passo das capitais no robô diário).

**Do Brasil, à mão.** Os robôs rodam no GitHub, fora do Brasil, e alguns sites oficiais de Assembleias e Câmaras Municipais não aceitam esse acesso (recusam, não respondem ou mandam regras que proíbem a leitura): essas Casas ficam com os dados da última leitura completa, e o site mostra essa data ("Última atualização dos dados", no quadro da Casa nas páginas do estado e da cidade, e "Dados da Assembleia/Câmara atualizados em" no topo do perfil; em amarelo quando tem mais de 8 dias). A data é o `conferido` de cada Casa em `dados/legislativos.json` (o dia da última leitura completa que deu certo, gravado pelo `scripts/legislativos.py`), que o `montar.py` leva para `infoCasa.conferido`. Para atualizar essas Casas, num computador no Brasil: `python scripts/atualizar_do_brasil.py --so-ver` (o que está atrasado e por quê) e `python scripts/atualizar_do_brasil.py --publicar` (lê de novo só as atrasadas, roda o `montar.py` e faz o commit e o push só dos dados; não roda com um robô do GitHub rodando). Opções: `--todas` (todas as Assembleias e capitais), `--casas BA RN 2111300`, `--mapa` (o mapa das cidades) e `--diarios` (as leis das prefeituras). Não há rotina automática: roda quando alguém pede (a skill `entendapolitica-atualizar` do Copilot, no computador do Lucas, faz isso).

**Troca de mandato.** Ninguém precisa mexer no código quando um mandato acaba: `scripts/mandatos.py` sabe a data de posse de cada cargo (presidente em 5/1 e governadores em 6/1 a partir de 2027, pela EC 111/2021; Congresso em 1º/2; prefeitos e vereadores em 1º/1) e os coletores perguntam a ele qual mandato está em curso. No dia da posse, presidente, vice, governadores, deputados estaduais e as legislaturas da Câmara e do Senado trocam sozinhos, e os selos "Eleito em 2026" saem. As pesquisas à mão dizem de qual mandato são (`"eleicao": 2022` em `governadores.json`, `"eleicao": 2024` em `prefeitos.json`, `"mandatoInicio"` em `ministros.json`): quando um mandato novo começa, a de governadores deixa de valer (o site mostra quem ganhou, com "aConfirmar") e a de ministros ganha um aviso, até serem refeitas. Para as eleições municipais de 2028, `tse.py` ainda precisa aprender o ano novo (`ORDINARIAS`, `ID_DIVULGA` e a leitura de 2024).

**Ministros do STF.** `scripts/stf.py` (no robô diário, antes de juntar tudo) lê os sites do STF (a página "O STF", as Pastas dos Ministros da Biblioteca do STF, as Turmas, a lista de presidentes e a de ministros por antiguidade) e a API de Dados Abertos do Senado (a mensagem de cada indicação, a CCJ e o Plenário) e grava `dados/stf.json` e as fotos `img/pessoas/stf-<slug>.jpg`. Roda todo dia, mas só lê os sites uma vez por semana: se o `conferido` do arquivo tem menos de 7 dias, sai sem pedir nada. Se um site estiver fora do ar ou a leitura vier incompleta (menos de 8 ministros, ou alguém sem nascimento, sem posse, sem quem indicou ou sem o placar do Senado), fica o arquivo de antes; se só o Senado cair, cada ministro fica com o bloco do Senado de antes; sem a foto nova, fica a de antes. Quando a composição muda (aposentadoria, posse, presidência, Turmas, indicação nova no Senado, cadeira vazia), o log mostra `⚠️ STF: ...` e o resumo do Actions ganha um aviso. Ninguém precisa mexer no código quando um ministro se aposenta ou toma posse: quem entra ganha o id `stf-<slug>`, e quem sai deixa a seção, a busca e o sitemap na mesma rodada (o `montar.py` refaz as entradas `stf-`). Para ler já: `python scripts/stf.py --agora`; para refazer o arquivo só com o que está no cache (`.cache/stf/`), sem rede: `python scripts/stf.py --cache` (a data `conferido` continua a da última leitura de verdade). O cache entra no cache "outros" do robô.

**Depois de um 2º turno.** Os dados abertos de candidaturas do TSE (`consulta_cand`) levam alguns dias para trazer a situação depois do 2º turno (até lá, a linha do 2º turno vem com `#NULO`). Enquanto isso, o `tse.py` (`Base2026._completar_2turno`) lê a totalização final de cada 2º turno de presidente e de governador no sistema de resultados do TSE (`resultados.tse.jus.br/oficial/ele<ano>/<eleição do 2º turno>/dados/<uf>/<uf>-c<cargo>-e<eleição>-u.json`, só quando `"tf": "s"`) e põe esse arquivo como fonte junto com a candidatura. Quando os dados abertos chegam, eles passam a valer sozinhos. Depois do resultado final, rode `python scripts/historico.py` (o mandato seguinte entra no histórico).

**Quem assume (eleitos de 2026).** `scripts/eleitos.py` (no robô diário, logo depois do `tse.py`; só biblioteca padrão) junta as candidaturas de 2026 (`tse.Base2026`, com a situação depois do 2º turno), os bens declarados, a votação por município e zona e quem tem cargo hoje (as listas do site), e grava `dados/eleitos/BR.json`, `dados/eleitos/<UF>.json` (um por estado) e `dados/eleitos/municipal.json`. As pessoas são ligadas pelo CPF (sem CPF, nome civil + nascimento; nunca só pelo nome), e o CPF não vai para os arquivos. Quem o site ainda mostra como presidente, governador ou prefeito, mas foi eleito para outro cargo, deixou o cargo 6 meses antes da eleição (Constituição, art. 14, § 6º): conta como "sem cargo eletivo hoje", e o link vai para o perfil que já existe. A votação por município e zona (~460 MB) é baixada para `.cache/eleitos/` no máximo uma vez a cada 7 dias, somada por candidatura e apagada (ficam só as somas, em `votos_2026.json`). As eleições suplementares vêm do DivulgaCandContas do TSE (um pedido por vez, 1,2 s entre pedidos, cache em `.cache/eleitos/divulga/`; com 2 falhas seguidas, ele para de pedir naquela rodada e fica o que estava publicado). Se o TSE não responder, ficam os arquivos de antes. Cada cargo sai dos arquivos no dia da posse (`mandatos.antes_da_posse`: Roraima em 1º/1/2027, presidência em 5/1, governos e a Câmara Legislativa do DF em 6/1, Rio Grande do Sul em 31/1, Congresso e as outras Assembleias em 1º/2); o arquivo que fica vazio é apagado e a seção some sozinha (fica só o `municipal.json`, com a próxima eleição municipal). Para ver o que acontece em outra data: `python scripts/eleitos.py --hoje 2027-01-07 --saida <pasta>`. O `montar.py` põe os perfis `e26-` e os vereadores eleitos em 2026 na busca, os `e26-` no sitemap e o selo "Eleito em 2026" nas fichas das cidades (`eleitos.busca_e_selos` e `eleitos.urls_sitemap`). A data da próxima eleição municipal sai da regra da Constituição (1º domingo de outubro; 2º turno no último domingo; posse em 1º de janeiro), conferida no quadro das Emendas Constitucionais do Planalto em 29/10/2026 (até a EC 141; `EC_CONFERIDA` no script): se uma emenda mudar a data, mude o script. Para as eleições de 2030, o script precisa aprender o ano novo (`ANO`), como o `tse.py`.

O mapa do Brasil da página do estado (`dados/mapa-brasil.json`: o contorno real de cada estado, da malha oficial do IBGE, já desenhado, e o lugar da sigla) é feito por `scripts/mapa.py`. O contorno dos estados quase nunca muda, então ele não roda todo dia: rode à mão se o IBGE mudar a malha.

Os mandatos anteriores (`dados/historico/`) são feitos por `scripts/historico.py`, a partir dos dados abertos do TSE (candidaturas de 1994 a 2026 e o resultado de 1990, para o Senado de 1995 a 1998) e, para os ministros, de `dados/manual/ministros-anteriores.json`. O passado não muda, então ele **não roda todo dia**: rode à mão (`python scripts/historico.py`, uns 40 s com o cache; na primeira vez baixa uns 650 MB para `.cache/tse/`; só os ministros: `python scripts/historico.py --ministros`, sem baixar nada). Rode de novo quando o resultado de uma eleição fechar: o mandato novo entra sozinho no índice e, no dia da posse, o de antes vira passado (até lá, ele não aparece no campo "Ver outro mandato"). Enquanto os dados abertos ainda não trazem o 2º turno, o `historico.py` usa a mesma totalização final do sistema de resultados do TSE que o `tse.py` (`completar_2turno`), com a fonte na ficha de quem venceu. O mandato 2027–2030 entrou em 26/10/2026, depois do 2º turno de 2026.

Correções à mão (sempre com fonte): `dados/manual/governadores.json`, `dados/manual/ministros.json`, `dados/manual/prefeitos.json` (quando quem está no cargo hoje não é quem o TSE mostra: morte, renúncia, cassação) `dados/manual/presidentes.json` (presidente e vice dos mandatos anteriores: só o que o TSE não tem, como o vice de 1994 e 1998 e o 2º turno de 2006, e o que mudou durante um mandato, como em 2016) e `dados/manual/ministros-anteriores.json` (ministros dos governos de 1995 a 2022: transcrito das listas da Biblioteca da Presidência e dos decretos do Diário Oficial, cada pessoa com a sua fonte; para corrigir, mude aqui e rode `python scripts/historico.py --ministros`).

### Câmaras Municipais

As Câmaras Municipais entram de dois jeitos, sempre lendo só o sistema oficial de cada Câmara:

- **Capitais** (`python scripts/legislativos.py camaras --paralelo 26 --minutos 60`, no robô diário: todas ao mesmo tempo,
  cada uma no seu servidor): um coletor por Câmara (`scripts/camaras/c<IBGE>.py`).
  19 das 26 capitais têm a **lista oficial de quem está no cargo** (inclusive suplentes que assumiram), com o partido de
  hoje, a foto oficial (reduzida para 240 px em `img/pessoas/ver-*.jpg`) e a página oficial de cada pessoa; Recife,
  Maceió, Campo Grande, Florianópolis, Macapá, Aracaju e Palmas continuam com a lista de eleitos do TSE (os motivos
  estão nas notas de cada uma). **Propostas desde 1º/1/2025** em 17 capitais, e o que a **prefeitura** mandou à Câmara
  em 16 delas (em Belém, as páginas do Executivo no site da Câmara estão vazias):
  - pelo SAPL: Fortaleza, Manaus, Natal, João Pessoa, Porto Velho, Rio Branco e Boa Vista; pelo SPLegis: São Paulo;
  - pelo SAGL (API JSON, `@@materias`, com a autoria e o andamento de cada matéria): Recife, nos perfis dos eleitos em
    2024 (como as votações);
  - pelo Processo Legislativo Eletrônico da Ágape, o "Câmara sem Papel" (`scripts/camaras/_agape.py`): Vitória, Teresina
    e Cuiabá, lidos como uma pessoa lê o sistema — a planilha da consulta de cada tipo e ano e a página de cada
    proposição, com a tramitação de onde sai a situação (regras de cada Câmara, conferidas à mão); em Cuiabá, cuja
    página de proposição é muito pesada, a situação vem primeiro da norma ligada no módulo de Legislação e da fase da
    lista;
  - por páginas do site da Câmara: **Rio de Janeiro** (o sistema de proposições em Lotus Notes,
    aplicnt.camara.rj.gov.br, entrega as listas e a tramitação em JSON; a situação vem do documento mais novo que decide
    e a lei tem o link do texto, contlei.nsf), **Porto Alegre** (o CSV da busca e a página de cada processo, com o
    documento da lei e o veto), **Belo Horizonte** (a pesquisa de proposições do portal, com os 10 s entre pedidos do
    robots.txt), **Salvador** (o sistema legislativo, um ScriptCase em páginas HTML: a lista de cada ano e modalidade e
    a janela de tramitação de cada proposição; o link de cada proposta é o PDF do texto) e **Belém** (as listas e a
    página de cada projeto, com os autores; o site quase nunca mostra o andamento, e a situação fica "não classificada",
    com uma nota no perfil).

  Ficam sem propostas Curitiba (o sistema de proposições, SPL, pede um código de imagem, CAPTCHA, para entrar, e o site
  não contorna CAPTCHA), Goiânia (as proposições estão só no SUAP, cujo robots.txt pede que robôs não leiam nada) e São
  Luís (o robots.txt do site da Câmara passou a fechar a leitura para robôs, visto em 26/10/2026, e o coletor respeita:
  fica a lista da última leitura, de 23/10/2026, com uma nota que explica isso, até a Câmara voltar a permitir a
  leitura). **Votações nominais**: São Paulo (arquivo XML anual da Câmara), Porto Alegre (sistema de votações da
  Câmara), Recife (SAGL) e, pelo SAPL, Porto Velho e Rio Branco. **Gastos do mandato**: São Paulo (Auxílio-Encargos
  Gerais de Gabinete, pelo SisGV), Porto Alegre (a cota mensal de cada gabinete, QBM, do Portal Transparência, pela API
  pública que a própria página usa, com a mesma conta da página, "Valores utilizados"), Goiânia (a cota parlamentar,
  CEAP, com os tipos de despesa, pelo Portal da Transparência, NúcleoGov), Teresina (a verba de atividade parlamentar,
  pela data do pagamento) e João Pessoa (a verba indenizatória da tabela do site da Câmara); nessas duas, só os totais,
  porque a Câmara não divide os gastos por tipo. Os gastos não entram no Recife (o sistema da verba pede o teste "não
  sou robô" a cada pesquisa), em Salvador (a tabela de despesas não liga com segurança cada pagamento a cada vereador e
  mês), no Rio (a cota fica em partes separadas — combustível, alimentação e carros blindados —, sem os gastos de cada
  vereador mês a mês), em Belo Horizonte (verba indenizatória extinta em 2015), em Curitiba (só subsídio), em Vitória
  (sem cotas desde 2023), em Cuiabá (valor fixo por lei) e em Belém (declarações mensais de que não houve cotas).

  Ajudas: `scripts/camaras/_capitais.py` (robots.txt, pausa, redirecionamento só para onde o robots.txt deixa, fim da
  rodada e o bloco dos gastos), `_paginas.py` (comum ao Rio, a Belo Horizonte e a Porto Alegre), `_cmrj.py`, `_cmbh.py`,
  `_cmpa.py`, `_capitais_c.py` (comum ao Recife, a Salvador e a Belém), `_scriptcase.py` (sessão de sistemas ScriptCase,
  como o de Salvador) e `_jp_gastos.py`; o estado de cada carga fica em `.cache/camaras/<IBGE>/`. As capitais lidas em
  páginas seguem o `Crawl-delay` de cada robots.txt (Belo Horizonte 10 s, Belém 5 s) ou esperam de 1,5 a 2 s (o servidor
  do SAGL do Recife respondeu "503" com 1 s); a primeira carga leva de 1 a 8 rodadas do robô (Belo Horizonte, a mais
  longa: umas 4 horas de pedidos) e, até terminar, fica publicado o de antes (o resumo marca `pendente` e a `etapa`).
  Vitória, Teresina, Cuiabá, Curitiba, Porto Alegre e São Luís não aceitam o robô do GitHub e são atualizadas pelo
  `scripts/atualizar_do_brasil.py`.
- **As outras Câmaras com SAPL** (`python scripts/legislativos.py sapl`, no robô das cidades): uma linha por cidade em
  `scripts/camaras/sapl_cidades.json` (818 cidades; feita por `python scripts/descobrir_sapl.py --lista`, que testa
  `sapl.<cidade>.<uf>.leg.br` e os endereços que o mapa das cidades achou), sem um arquivo .py por cidade
  (`scripts/camaras/_lista.py`). O nome, a sigla e o site da Câmara vêm do próprio SAPL.

O que cada Câmara com SAPL dá (`scripts/camaras/_sapl.py`, só a API pública `<endereço>/api/` do Interlegis):
1. **quem está no cargo hoje** (legislatura atual, mandatos e o campo "ativo"), ligado ao candidato do TSE de 2024 pelo nome
   (`ver-<IBGE>-<SQ>`). Conferência: o número de vereadores ativos tem de ser igual ao de vagas (eleitos em 2024) e pelo
   menos 70% deles têm de ser achados no TSE; se não bater, a página continua com a lista do TSE e as propostas entram só
   para quem foi ligado sem dúvida (as notas da Câmara dizem por quê);
2. as **propostas desde 1º/1/2025** (projetos de lei, de lei complementar, de emenda à Lei Orgânica, de decreto legislativo e
   de resolução), com autor ou coautor e a situação (a da última tramitação e a norma ligada: "virou lei");
3. o **prefeito** (`pref-<IBGE>`): os projetos que a prefeitura mandou à Câmara desde a posse (ou desde que assumiu, se era
   vice) e o quadro "Leis sancionadas e vetos": as leis ordinárias e complementares cadastradas no SAPL (cada lei uma vez),
   só quando a numeração das leis do período está quase completa — começa logo depois da última lei de antes do mandato,
   chega até perto de hoje (a que falta no fim é estimada pelo ritmo de leis), faltam no máximo 15% dos números e nenhum
   buraco de mais de 5 números seguidos (a mesma régua da contagem pelos Diários Oficiais) — e os projetos vetados (pelo
   andamento, ou pelas mensagens de veto). O que não dá para contar com segurança fica fora, com o motivo em "Como contamos"
   e nas notas da Câmara. No arquivo, `executivo.notaLeis` e `executivo.notaVetos` explicam cada número em separado
   (`nota` = as duas juntas): quando o SAPL só tem um dos dois números e o Diário Oficial tem o outro, o perfil junta as
   duas contas, cada uma com a explicação e a fonte de onde veio;
4. as **votações nominais** desde 1º/1/2025, quando a Câmara registra no SAPL o voto de cada vereador
   (`sessao/registrovotacao` e `sessao/votoparlamentar`): as de projetos, das emendas, substitutivos e redações finais deles e
   de vetos que decidiram a matéria (resultado de natureza "aprovado" ou "rejeitado"); requerimentos, indicações, moções,
   outros documentos e votações de adiamento ou pedido de vista ficam fora. O placar é o publicado no registro (se a soma dos
   votos for diferente, vai junto um `aviso`, e o perfil diz isso), e cada votação leva à página de transparência dela no SAPL.
   O que foi votado fica num catálogo dentro do arquivo da cidade (`dados/camaras/extras/<IBGE>.json` → `votacoes`); o perfil
   guarda só `[chave, voto]`, como no Congresso. A primeira leitura de uma Câmara com muitas votações leva várias rodadas;
   enquanto isso, a cidade é publicada com as votações de antes (ou sem elas) e fica na fila diária até terminar. "De antes" =
   as da última leitura completa guardada no cache ou, se ela não existe (no robô, que começa com o cache vazio) ou se a
   rodada acabou antes dos tipos de resultado que o catálogo usa, as que já estão publicadas no arquivo da cidade, e também a
   nota da Câmara sobre as votações ("não entram... e por quê"): nada some porque uma leitura parou no meio. Os gastos do
   mandato não estão no SAPL (nota da Câmara). As notas das capitais sem dados abertos dizem o formato em que cada uma publica
   votações e gastos (PDF, consulta de página, CAPTCHA) ou que a verba não existe (Belo Horizonte, Curitiba, Belém, Vitória).

**Um arquivo por cidade** (limite de arquivos da Vercel): `dados/camaras/<IBGE>.json` (a lista oficial, a cobertura e as
notas) e `dados/camaras/extras/<IBGE>.json` (o que a Câmara publica a mais sobre cada vereador e sobre o prefeito). O
`montar.py` marca `"extras": "cidade"` na página da cidade e o perfil busca esse arquivo. Fotos: só as capitais guardam a foto
reduzida; nas outras cidades vale a foto do TSE (os suplentes que assumiram ganham a foto da candidatura deles no TSE).

**Educado com os servidores** (robots.txt): cada servidor tem o robots.txt lido uma vez por rodada; o do SAPL pede **60 s
entre pedidos** (`Crawl-delay`), e o coletor espera isso entre um pedido e outro ao mesmo endereço (cidades diferentes ao
mesmo tempo: `--paralelo`). Cada cidade faz **no máximo 60 pedidos por rodada** (`SAPL_PEDIDOS`) e nada começa depois do
limite de tempo (`--minutos`). Por isso a **primeira carga** de uma cidade grande leva alguns dias: o que foi lido fica em
`.cache/camaras/<IBGE>/estado.json` (outra pasta: `CAMARAS_CACHE`), a rodada seguinte continua dali e, enquanto a carga não
termina, fica publicado o que já estava (nada pela metade). Depois disso, cada rodada pede só o que mudou (4 a 9 pedidos na
maioria das cidades). **Rodízio:** `--parte hoje` roda as cidades do dia da semana (cada cidade uma vez por semana, sempre no
mesmo dia: `int(IBGE) % 7 + 1`) e `--pendentes` junta as que ainda não terminaram a primeira carga (uma cidade que falha 3
dias seguidos sai dessa fila e volta no dia dela).

**Cobertura (27/10/2026):** 838 Câmaras com dados no site (791 com a lista oficial), 7.123 vereadores com
propostas, 772 prefeitos com os projetos que mandaram à Câmara e 536 com leis ou vetos; **votações nominais em
522 Câmaras** (75.472 votações e 5.733 vereadores; 519 com SAPL, mais São Paulo, Porto Alegre e Recife) e
**gastos do mandato** em São Paulo, Teresina, Goiânia, Porto Alegre e João Pessoa (180 vereadores). Todas as cidades da lista
terminaram a primeira carga; em 3 Câmaras com SAPL a leitura das votações não terminou (o robô continua). Por estado: ver
`dados/legislativos.json` (`camaras.<IBGE>`) e as notas de cada `dados/camaras/<IBGE>.json`.

- **Situação das propostas numa Câmara de uma casa só**: o "aprovado" da votação final vai para a sanção do prefeito
  (`aprovada`); sancionado, promulgado ou com norma ligada = `lei`; "veto rejeitado" quer dizer que a Câmara derrubou o veto;
  "veto acatado/mantido" = a Câmara manteve o veto; aprovação em 1º turno e pareceres = `andando`. As regras estão em
  `scripts/camaras/_base.py` (`REGRAS`). Câmara que não registra o andamento: "A Câmara não registrou o andamento desta
  proposta no SAPL".
- `python scripts/descobrir_sapl.py --lista` (não roda todo dia) refaz a lista das Câmaras com SAPL sem apagar os ajustes
  feitos à mão (`tipos`, `regras`, `tse_manual`, `incluir`, `excluir`, `vagas`, `notas`, `ativo`).
- **Testes:** `python testes/interacao_camaras.py` (só olha as Câmaras que o `montar.py` já juntou à página da cidade) e,
  nas capitais lidas em páginas do site, `python testes/interacao_capitais_a.py` (Vitória, Teresina, Cuiabá e Goiânia),
  `interacao_capitais_b.py` (Rio, Belo Horizonte, Curitiba e Porto Alegre) e `interacao_capitais_c.py` (Recife, Salvador,
  Belém e João Pessoa): propostas, prefeito, notas da Câmara, gastos e votações onde houver, inglês e 320 px.

### Mapa das Câmaras Municipais e prefeituras (`dados/municipios/<UF>.json`)

`python scripts/municipios/mapear.py [UF ...]` confere, nas 5.569 cidades, o site oficial da Câmara Municipal e da prefeitura, o sistema de proposições da Câmara e se as proposições estão na internet (quando não estão, por quê), a página de pedido de informação (e-SIC), o portal da transparência e o Diário Oficial da prefeitura. É o que o quadro **"Onde ver mais"** dos perfis de vereadores e prefeitos mostra (o `montar.py` leva cada cidade para o campo `onde` de `dados/cidades/<UF>/<IBGE>.json`; nas cidades com coletor próprio da Câmara, `dados/camaras/<IBGE>.json`, o que o coletor leu vale mais que o palpite do mapa: sai o motivo do mapa, as notas da Câmara dizem o que falta e por quê, e o site da Câmara vem do coletor quando o mapa não o achou). As pistas vêm de listas oficiais — a do Interlegis (domínio .leg.br, SAPL e Portal Modelo de cada Câmara), a descoberta do SAPL (`scripts/descobrir_sapl.py`), as listas de municípios dos Diários Oficiais das associações de municípios (SIGPub, em www.diariomunicipal.com.br, e Assomasul) e a do Ciga (SC) —, mas tudo é conferido no próprio site oficial (título, nome do site, texto). Só entram sites .leg.br e .gov.br; o Diário Oficial pode estar na plataforma que o site da prefeitura indica (ou na da associação em que a cidade publicou nos últimos 6 meses). O cadastro do Interlegis às vezes traz o e-mail ou o domínio de outra Câmara (a da capital ou a vizinha; em 29/10/2026 eram 12 Câmaras com o site de outra cidade, como São José do Rio Preto com o da Câmara de Nova Aliança): por isso, um endereço tirado do e-mail cadastrado só vale se a página falar da cidade ou se o endereço tiver o nome dela, e um endereço com o nome de outra cidade do estado (`alheio`) só vale se a página disser no topo o nome desta.

- **No robô:** `.github/workflows/cidades.yml` roda `mapear.py --rodizio` todo dia (um grupo de estados por dia: cada estado é conferido uma vez por semana) e junta tudo com o `montar.py`.
- **Educado:** respeita o robots.txt de cada site (e o `Crawl-delay`; o do SAPL pede 60 s); 1 s entre pedidos ao mesmo site; poucos pedidos ao mesmo tempo para o mesmo servidor; até 16 cidades em paralelo (sites diferentes); um servidor que para de responder é deixado em paz pelo resto da rodada. O que foi visto fica em `.cache/municipios/`; cada cidade só é refeita depois de 6 dias e, se um site não abrir, vale o que foi conferido até 45 dias antes. O robô do GitHub roda fora do Brasil, e muitos sites de prefeituras e Câmaras bloqueiam esse acesso: por isso, um bloco já publicado (Câmara ou prefeitura) só é trocado quando a rodada nova acha pelo menos o mesmo tanto de informação, quando o site muda de endereço (e o novo é lido), quando o endereço publicado deixa de existir ou quando ele é de outra cidade; senão fica o bloco publicado, com a data em que foi conferido, por até 90 dias (`manter_publicado`). Quando a rodada não consegue abrir o site da Câmara e só acha o SAPL dela, ela põe o endereço do SAPL como site: aí o site e o pedido de informação publicados continuam, e só as proposições passam a ser as do SAPL, se ele tiver a legislatura atual e o publicado não tiver proposições na internet (`_com_sapl`; antes disso, em 27 e 28/10/2026, 17 Câmaras perderam o link do pedido de informação). A lista do Interlegis demora uns 25 s para começar a chegar (é gerada na hora): as listas oficiais têm até 180 s (`TEMPO_LISTAS`), e uma lista que não abrir continua citada nas fontes do estado. Em 26/10/2026, uma rodada no robô achou bem menos que a rodada feita no Brasil (350 prefeituras de MG sem leitura, contra 220): de vez em quando, vale rodar o mapa num computador no Brasil (`python scripts/municipios/mapear.py`).
- **Formato:** `{uf, atualizado, fontes, nota, cidades: {<IBGE>: {camara: {site, sistema, api, propostas, propostasOnline, sic, conferido, motivo, motivo_en, plataforma?}, prefeitura: {site, transparencia, sic, diarioOficial: {nome, url, plataforma, entidade?, confirmado?}, conferido, lido?}}}}`. `sistema`: `sapl`, `sagl`, `nopaper` (SPL da Ágape, "Câmara sem Papel"), `outro` ou `null`. `propostasOnline`: `true` (conferido que estão na internet), `false` (conferido que não estão onde deviam) ou `null` (não deu para conferir); `motivo`/`motivo_en` dizem por quê, em frases curtas que qualquer pessoa confere abrindo o site. `propostas` é a página pública das proposições (no SAPL, a busca de matérias).
- **Conferir:** `python scripts/municipios/resumo.py` (tabela por estado e plataformas de Diário Oficial) e `python scripts/municipios/resumo.py --conferir` (formato); `python scripts/municipios/mapear.py --ibge <código>` mostra o que foi achado numa cidade.
- **Limites:** domínios fora do padrão (abreviações, .com.br) ficam sem site ("Não achamos..."); sites que pedem no robots.txt para não serem lidos, ou que só funcionam com JavaScript, ficam com o endereço e o motivo; o DOM/SC fecha para robôs (em SC, sem link no site da prefeitura, a ligação ao DOM/SC vem da adesão ao Ciga: `"confirmado": false`).
- Os canais de pedido de informação conferidos à mão (`dados/manual/canais-lai.json`) completam o mapa nas capitais em que ele não achou.

### O que cada prefeitura fez: leis e vetos pelos Diários Oficiais (`dados/prefeituras/<UF>.json`)

`python scripts/municipios/diarios.py [UF ...]` (no robô das cidades: `--rodizio --minutos 40`, cada estado uma vez por semana) conta, nas cidades sem SAPL, as leis que a prefeitura publicou desde o começo do mandato de quem é prefeito hoje (1º/1/2025, ou o `desde` da ficha da cidade) e, quando dá, os vetos. Lê a plataforma do Diário Oficial que o mapa das cidades achou (`dados/municipios/<UF>.json`):
- **SIGPub** (www.diariomunicipal.com.br, os Diários das associações de municípios): a busca por título ("lei", "veto") e período de cada associação inteira, mês a mês, com a cidade e o órgão de cada matéria (`_diario_sigpub.py`); título sem número ("Lei Municipal"): o texto da matéria, lido uma vez;
- **Diário Oficial MS** (Assomasul): o filtro avançado (município, título e período) (`_diario_assomasul.py`);
- **DOSP / Imprensa Oficial Municipal**: a seção "Leis" de cada cidade (`_diario_listas.py`);
- **página de leis do site oficial da prefeitura**, nos fornecedores que deixam listar as leis por tipo e data: ADiários (`/leis.php`, filtro por período), Instar (`/portal/leis_decretos`, filtro por categoria e ano) e Digitaliza (`/legislacoes/...`, a lista por tipo e ano que a própria página usa) (`_diario_listas.py`); o link vem da página inicial do site, achado pelo mapa;
- **portal de legislação do município no CESPRO** (cespro.com.br, quase todo o RS): a busca por tipo de norma e ano (`_diario_cespro.py`; a busca do site responde a POST, feito com as mesmas regras da rede educada).

Quando mais de uma fonte dá a contagem segura, vale a que tem os vetos; senão a mais completa (menos números de lei faltando); empate: o Diário.

- **Só quando é seguro** (`_atos.py`, testes em `python testes/diarios_titulos.py`): cada número de lei conta uma vez (republicações, retificações, erratas e anexos não contam de novo; projetos, decretos e avisos que só citam uma lei ficam fora); leis publicadas pela Câmara (promulgadas por ela) não contam quando a fonte diz quem publicou. A contagem de uma cidade só entra quando a numeração das leis do período está quase completa (no máximo 15% dos números faltando e nenhum buraco de mais de 5 números seguidos), começa logo depois da última lei de antes do mandato e chega até perto de hoje (a lei mais nova tem até 120 dias). Vetos: só quando a prefeitura publica todos numerados, sem buracos (nenhum veto publicado não quer dizer zero vetos). As outras cidades ficam em `fora`, com o motivo em frases curtas e o link para conferir.
- **Educado:** robots.txt e Crawl-delay de cada site (`_rede.py`); um pedido por vez a cada servidor (1,5 s entre pedidos; 1 s entre sites diferentes do mesmo servidor); as plataformas, em servidores diferentes, ao mesmo tempo; limite de tempo: o que não der fica para a próxima rodada, que continua de onde parou, e nada é publicado pela metade. Erro de rede ou bloqueio deixa a cidade pendente, com o que já estava publicado. Cache em `.cache/municipios/diarios/atos/`: os meses já lidos do SIGPub não são lidos de novo (toda semana entram só as matérias novas); nas páginas de leis, toda semana só as últimas semanas, e a página inteira a cada 4 semanas.
- **Formato:** `{uf, atualizado, fontes, nota, nota_en, cidades: {<IBGE>: {executivo: {periodo: {inicio, fim, ultimaLei}, leisSancionadas, vetos?, vetosTotais?, vetosParciais?, fonte, fontes?, nota, nota_en, notaLeis, notaLeis_en, notaVetos, notaVetos_en, conferencia}}}, fora: {<IBGE>: {motivo, motivo_en, codigo, tipo, nome, nome_en, url?, plataforma, diario, leis, falta, faixa, data}}, rotas: {<IBGE>: {cespro?, diario?, digitaliza?, instar?, leis?}}}`. `nota` é `notaLeis` + `notaVetos` (a explicação de cada número à parte, para o perfil poder juntar esta conta com a do SAPL). `rotas` guarda onde ler cada cidade (Diário e páginas de leis): o robô começa com o cache vazio e muitos sites de prefeituras bloqueiam o acesso de fora do Brasil, então a rota que já deu certo continua valendo mesmo quando o mapa não consegue achar o link de novo.
- **No site:** o `montar.py` (`_executivo_prefeito`) põe o bloco `executivo` (sem `conferencia`) na ficha do prefeito, em `dados/cidades/<UF>/<IBGE>.json`, só se for de quem governa hoje desde o começo do período contado (fica fora quem assumiu numa eleição suplementar sem a data da posse na ficha e quem está "a confirmar"); onde o SAPL da Câmara já tem a contagem (`dados/camaras/extras/<IBGE>.json`), vale a do SAPL; se o SAPL tiver só os vetos (ou só as leis) e as duas contas começarem no mesmo dia, o perfil junta as duas (`juntaExecutivo`, em `js/pessoa.js`), cada número com a explicação (`notaLeis`, `notaVetos`) e a fonte de onde veio; sem as explicações separadas, fica só a conta do SAPL. Nas cidades em `fora`, o motivo e o link vão para `onde.prefeitura.leis`, que o quadro "Onde ver mais" do prefeito mostra.
- **Hoje (26/10/2026):** 931 prefeituras com a contagem (de 5.569, em 20 estados), 12 também com o número de vetos; no site, a contagem dos Diários aparece no perfil de 846 prefeitos (75 têm a conta do SAPL da Câmara, que vale primeiro; 42 juntam as leis dos Diários com os vetos do SAPL; 7 assumiram numa eleição suplementar, 2 cidades estão sem prefeito e 1 está "a confirmar"); 1.192 em `fora`, com o motivo e o link para conferir (a maioria não publica as leis na fonte lida; as outras têm a lista incompleta). Tabela por estado e plataforma: `python scripts/municipios/diarios_resumo.py`; conferir o formato: `--conferir`; uma cidade: `python scripts/municipios/diarios.py --ibge <código> [--detalhe]`.
- **Limites:** contamos leis publicadas (a nota diz quantos números faltam); DOM/SC, Ágape e DIOF fecham para robôs no robots.txt; Dioenet, DOEM, Município Online, DIO-ES, Famem e os Diários próprios não deixam conferir a numeração das leis pela lista (ou pedem um formulário de navegador); os portais de legislação de outros fornecedores ficam para quando o mapa marcar o fornecedor. Por isso BA, SE, ES, AC, PI e TO ainda não têm nenhuma cidade contada.

### Assembleias Legislativas (e a Câmara Legislativa do DF)

`python scripts/legislativos.py assembleias` (ou só alguns estados: `python scripts/legislativos.py BA SP GO`) roda um coletor por Casa (`scripts/assembleias/<uf>.py`; ajudas em `_ne_comum.py`, `_ne_sapl.py` e `_ne_nopaper.py` no Nordeste, `_sse_comum.py` no Sudeste, Sul e DF, `_nco_comum.py`, `_nco_sapl.py` e `_nco_gov.py` no Norte e Centro-Oeste, `_ap_elegis.py` (o e-Legis da Alap: propostas e governador do AP), `_ne_gov.py` no Nordeste e, para as três, `_carga.py` (tempo da rodada e primeira carga) e `_votos_gastos.py` (votações e gastos)). Cada um lê só o site oficial da Casa, um pedido por vez, com pausa, e guarda o que leu em `.cache/<casa>/`. Hoje, **as 27 Casas** têm a **lista oficial de quem está no cargo** (inclusive suplentes que assumiram: "Suplente em exercício"), com o partido de hoje, a foto e a página oficial; cada pessoa é ligada ao candidato do TSE da eleição da legislatura (`dest-<UF>-<SQ_CANDIDATO>`; conferências à mão no próprio coletor). **22** têm as **propostas desde a posse** (61.141: projetos de lei, de lei complementar, de emenda à Constituição — no DF, à Lei Orgânica —, de decreto legislativo e de resolução), com autor principal ou coautor e a situação (regras de cada Casa, conferidas à mão numa amostra, antes da tabela comum). **10** têm **votações nominais** (o voto de cada deputado no Plenário: AM, RO, GO e PA em catálogos `dados/votacoes/<aleam|alero|alego|alepa>.json`; CE, RN, RS, SC, PI e PB dentro do perfil, no campo `lista`) e **14** têm **gastos** (verba indenizatória, cota ou verba de gabinete; o perfil diz o nome de cada uma). As ajudas comuns das votações e dos gastos estão em `scripts/assembleias/_votos_gastos.py` (formato, ligação de nomes, planilhas XLSX/ODS com a biblioteca padrão e a regra da primeira carga: enquanto a leitura de uma Casa não termina, cada perfil fica com o bloco publicado antes).

| UF | Casa | No cargo (suplentes marcados) | Propostas | Votações nominais | Gastos |
|---|---|---|---|---|---|
| AC | Aleac | 24 (0) | 868 | — | — |
| AL | ALE-AL | 27 (0) | 2.136 | — | — |
| AM | Aleam | 24 (1) | 3.966 | 3.140 | cota parlamentar (CEAP) |
| AP | Alap | 24 (2) | 1.993 | — (o e-Legis não diz se a lista de votos é nominal ou simbólica) | CEAP |
| BA | Alba | 63 (0) | 1.359 | — | verba indenizatória |
| CE | Alece | 46 (0) | 3.103 | 60 | verba de desempenho parlamentar |
| DF | CLDF | 24 (0) | 2.757 | — | — |
| ES | Ales | 30 (2) | 2.770 | — (boletins em PDF) | cota parlamentar (valor solicitado) |
| GO | Alego | 41 (2) | — (o sistema proíbe robôs) | 2.080 | verba indenizatória |
| MA | Alema | 42 (0) | 2.389 | — (PDF) | CEAP |
| MG | ALMG | 77 (5) | 5.559 | — (só nas atas) | verba indenizatória |
| MS | Alems | 24 (1) | — (desafio anti-robô) | — | CEAP |
| MT | ALMT | 24 (1) | — (a API exige cadastro) | — | — |
| PA | Alepa | 41 (2) | — (busca sem paginação aberta) | 151 | — (painel fora do domínio da Casa) |
| PB | ALPB | 36 (3) | 7.862 | 148 (o SAPL só tem votos desde 10/2024) | verba indenizatória (VIAP) |
| PE | Alepe | 49 (0) | 3.912 | — | CEAP |
| PI | Alepi | 30 (3) | 1.509 | 136 | — |
| PR | Alep | 54 (3) | 3.260 | — | — |
| RJ | Alerj | 70 (9) | — (o sistema só mostra as 15 mais recentes) | — | — (não existe verba indenizatória no RJ) |
| RN | ALRN | 24 (0) | 2.240 | 141 (236 dão erro no sistema da ALRN) | — (serviço com chave) |
| RO | Ale-RO | 24 (1) | 2.439 | 367 | verba indenizatória (verbas gerais) |
| RR | ALE-RR | 24 (1) | 1.296 | — | — |
| RS | ALRS | 55 (1) | 1.590 | 846 | — |
| SC | Alesc | 40 (4) | 2.038 | 226 | despesas dos gabinetes |
| SE | Alese | 24 (0) | 1.510 | — | — |
| SP | Alesp | 94 (5) | 4.824 | — (voto só em PDF) | despesas de gabinete |
| TO | Aleto | 24 (1) | 1.761 | — | — |

(Listas e propostas: números de 23/10/2026; votações, gastos e o Amapá: 26/10/2026; propostas do Amapá: 27/10/2026. "Suplentes marcados" = onde a lista oficial diz que a pessoa é suplente; nas outras, o perfil mostra "Como chegou ao cargo".) O que falta em cada Casa, e por quê, está nas `notas` de `dados/assembleias/<UF>.json`, que a página do estado mostra no quadro "O que o site já tem da Assembleia".

- **Educado com cada site:** todos os pedidos respeitam o robots.txt de cada servidor (lido uma vez por rodada; o que ele fecha não é lido, e um robots.txt fora do ar faz o site não ser lido naquele dia) e o intervalo que ele pede (`Crawl-delay`: 60 s nos SAPL do Interlegis — AC, AL, AM, PB, PI, RO, RR e TO —, 10 s nos dados abertos do RJ e de GO). Nos SAPL, cada rodada pede só o que mudou desde a anterior, em páginas de 100, e confere as outras situações aos poucos (5 a 12 pedidos por Casa e por dia).
- **Tempo por dia:** as 27 Casas rodam ao mesmo tempo (`python scripts/legislativos.py assembleias --paralelo 27 --minutos 50`; cada uma no seu servidor): com o cache cheio, 6 a 13 minutos. Nenhum pedido novo começa depois do fim da rodada (`scripts/assembleias/_carga.py`).
- **Primeira carga (cache vazio, como no robô do GitHub):** cada Casa usa a rodada toda, guarda o que já leu em `.cache/<casa>/` e continua no dia seguinte; enquanto não termina, não grava nada (ficam os arquivos publicados antes e o `dados/legislativos.json` marca a Casa como "em andamento"). A maioria termina em 1 ou 2 dias; os SAPL do Interlegis, em 2 a 7 dias (PB é o mais longo), e a ALMG em uns 7 (sem os arquivos anuais, que o robots.txt fecha, ela procura número por número). Para encher de uma vez à mão: `NE_SEM_LIMITE=1` (sem limite de tempo); `ALMG_VERBAS_MAX`, `CLDF_NORMAS_MAX`, `ALEP_NORMAS_MAX`, `ALESC_FICHAS`, `ALESC_PAGINAS` e `ALES_SEGUNDOS` mudam os limites diários de cada Casa.
- **Votações e gastos (fase 6):** só onde a Casa publica o voto de cada deputado ou o gasto de cada gabinete em formato que dá para ler e conferir (API, CSV/XLSX/ODS, JSON ou HTML com tabela); PDF não entra. Votações: só do Plenário, desde a posse, sem quem não registrou voto; o placar é conferido com a apuração oficial. Gastos: o ano mais recente por tipo (os tipos da própria Casa) e o total desde a posse, iguais à página oficial (conferências à mão em cada coletor). RN: API da Transparência Legislativa (o "Extrato de Votação"; as votações em que o sistema da ALRN dá erro ficam fora, com a conta no escopo); CE: planilhas da página "Votação Nominal" e a "Verba de Desempenho Parlamentar" (CSV por mês, sem tipos); SC: "Extrato de votação" do e-Legis; RS: planilhas de votação do portal do DAL; PI e PB: votos registrados no SAPL (na PB, desde 10/2024; o SAPL da ALPB ignora o filtro `id__in`, e a sessão e a matéria saem do texto de cada voto); AM: CSV da cota por deputado e mês; RO: verba indenizatória (só as verbas gerais); ES: Cotas Parlamentares; BA: planilha anual da verba; PE: serviços da página "Verbas Indenizatórias"; PB: planilhas da VIAP; MA: páginas da CEAP; AP: CEAP do Portal da Transparência. Nas votações de veto, o escopo diz o que quer dizer o "sim" quando o resultado oficial confirma (`_votos_gastos.sentido_veto`). Onde não entra, a nota da Casa diz por quê (PDF, teste anti-robô, chave de acesso, site fora do ar...).
- **Amapá (e-Legis):** `scripts/assembleias/_ap_elegis.py` lê o e-Legis da Alap (o sistema do processo legislativo, que trouxe do sistema antigo os anos anteriores e avisa que a mudança está em andamento): as listas de proposições por tipo e ano, a página de cada proposição (a norma que ela gerou e a movimentação, de onde sai a situação), o CSV de legislação e as mensagens de veto. A situação foi conferida com a situação oficial de todos os projetos de lei de 2025 (225 de 226 iguais; a diferente está atrasada na busca) e, onde a movimentação não mostra ("Devolvido ao Autor", "Rejeitado pela CCJ"), vale a situação oficial. Origem com mais de um nome: o primeiro é o autor principal. Ficam fora os 62 projetos de "Deputados Diversos" (sem os nomes) e os que a busca conta e não mostra. Primeira carga ~2.430 pedidos (~80 min, 2 a 3 rodadas do robô); depois, ~135 por dia.
- **Posse da legislatura eleita em 2026** (conferida nas Constituições e na Lei Orgânica do DF; fica em `scripts/mandatos.py`, `POSSE_ESTADUAL`): 1º de fevereiro de 2027 em 24 estados; **31 de janeiro no RS**, **6 de janeiro no DF** (Emenda à Lei Orgânica 131/2024) e **1º de janeiro em RR** (Constituição de RR, art. 30, § 4º). Em 2023 foi diferente em SP (15 de março) e no DF (1º de janeiro): `POSSE_ESTADUAL_ATE_2022`.
- **Troca de legislatura:** o começo das propostas (`regional.inicio_estadual(uf)`), os textos e a eleição do TSE usada nos ids (2026) trocam sozinhos na posse. A lista de quem está no cargo troca quando a Casa atualiza a dela; até lá, alguns coletores falham de propósito (para não mostrar a lista velha como se fosse a de hoje), e o `montar.py` não usa uma lista de uma legislatura que já acabou (`_lista_velha`): fica a lista do TSE, que já é a dos eleitos. Depois da posse, os ids dos deputados estaduais passam a usar o número do TSE de 2026 (o link antigo de um reeleito deixa de abrir o perfil).
- **Testes:** `python testes/interacao_ale_sse.py` (Sudeste, Sul e DF), `python testes/interacao_assembleias_nco.py` (Norte e Centro-Oeste, com o Amapá: propostas do e-Legis e o governador) e `python testes/interacao_assembleias_votos.py` (votações e gastos da fase 6: números das páginas × dados, "Mostrar mais votações" com o foco, link oficial, inglês, 320 px e axe).

#### O que cada governador fez (`dados/pessoas/gov-<UF>.json`)

O perfil do governador mostra o que o governo do estado fez desde a posse de quem governa hoje (1º/1/2023, ou o `desde` da ficha para quem assumiu depois): os **projetos que o Poder Executivo mandou à Assembleia** (`propostas`, com a situação calculada pelas mesmas regras das propostas dos deputados de cada Casa) e as **leis sancionadas e os vetos** do período (bloco `executivo`: `leisSancionadas`, `vetos` e, quando a fonte separa, `vetosTotais`/`vetosParciais` e `leisPromulgadasPelaCasa`; `periodo.ultimaLei`; e a `nota` "Como contamos"). A régua é a do perfil do presidente: conta tudo o que o governo assinou no período, inclusive quando outra pessoa estava no exercício do cargo (vice, presidente da Assembleia; a nota diz quantas, quando a fonte diz quem assinou); ficam fora as leis promulgadas pela própria Assembleia, quando a fonte as separa (quando não separa, a nota diz que elas estão na conta). Cada coletor de Assembleia grava o arquivo do governador no fim da rodada (roda todo dia junto; ajudas em `_ne_gov.py`, `_sse_comum.py` e `_nco_gov.py`); se a parte do governo falhar ou estiver incompleta (ex.: textos de lei ainda por ler), fica o arquivo de antes, a não ser que seja de outro governo (aí é apagado). As fontes ficam dentro de cada bloco (nada de `fontes` no topo, que cobriria as da ficha).

| UF | Projetos do Executivo | Leis | Vetos |
|---|---|---|---|
| AC | SAPL | — (a Aleac não cadastra as leis) | SAPL |
| AL, PB | SAPL (na PB, também as medidas provisórias) | normas do SAPL, sem as promulgadas pela Assembleia | SAPL |
| AM, RO, RR | SAPL (em RR, cada governador é um autor; entram todos do período) | normas do SAPL | SAPL |
| PI | SAPL | — (o SAPL da Alepi não tem todas as leis) | SAPL |
| TO | SAPL (inclui medidas provisórias) | página "Legislação Estadual" da Aleto (o começo de cada lei diz quem assinou) | SAPL |
| BA | portal legislativo da Alba | Legisla Bahia (Casa Civil), pelo texto de cada lei ("eu sanciono" × "eu promulgo") | mensagens de veto do Executivo |
| CE | listas da Alece | listas "Leis de <ano>" e ementário, pelo texto de cada lei | — (a Alece não publica a lista) |
| MA | AlemaLegis (inclui medidas provisórias) | AlemaLegis (não separa as promulgadas) | AlemaLegis |
| PE | dados abertos da Alepe | Legislação Estadual da Alepe, pelo texto de cada lei | — (não publica os vetos) |
| RN | API da Transparência Legislativa | — (a ALRN não publica a lista de leis) | API (desde 2025) |
| SE | portal da Alese | módulo de Legislação, pelo texto de cada lei | — (registro incompleto) |
| MG | API de dados abertos (autor "Governador do Estado") | pesquisa da Legislação Mineira | mensagens de veto (VET) |
| SP | API do portal (autor "Governador") | arquivo de normas (dados abertos) | documentos de veto total e parcial |
| RJ | Mensagens do Executivo (sistema da Alerj) | Diário Oficial em dados abertos (Casa Civil), pela assinatura | Diário Oficial |
| ES | API pública (autor "Governador do Estado") | cadastro de legislação (sancionada × promulgada) | mensagens de veto |
| PR | API (autor "Poder Executivo") | normas legais com a conclusão "Sancionada" | — (a lista de vetos da API para em 2024) |
| SC | e-Legis (iniciativa do Governador; sem as medidas provisórias) | pesquisa da Legislação SC | mensagens de veto |
| RS | pesquisa do portal (Poder Executivo) | Sistema LEGIS | proposições VT e VP |
| DF | PLe (autoria do Poder Executivo) | cadastro de normas do PLe | — (o PLe não registra o veto) |
| PA | — | Banco de Leis da Alepa (a partir da 1ª lei do governo, conferida à mão: `PRIMEIRAS` em `pa.py`) | — |
| GO | — | dados abertos da Casa Civil (arquivo mensal) | — |
| MS | — | banco Legislação Estadual do governo | — |
| MT | — | — (o perfil leva ao Diário Oficial) | — |
| AP | e-Legis da Alap (origem "Poder Executivo"/"Governo do Estado", números "-GEA") | CSV de legislação do e-Legis, sem as promulgadas pela Assembleia (pela movimentação de cada projeto: "Proposição Sancionada" × "Proposição Promulgada") | mensagens de veto do e-Legis (tipo "Veto"; "Veto Total"/"Veto Parcial" na ementa) |

O que não entra fica explicado nas `notas` da Casa e na `nota` do bloco `executivo`; o perfil mostra, no lugar, o quadro "Onde ver mais". **Na troca de governo** (posse de 6/1/2027): o período troca sozinho (`mandatos.py` e o `desde` da ficha); o PA precisa de uma linha nova em `PRIMEIRAS` (`scripts/assembleias/pa.py`) com a primeira lei do novo governo, conferida no PDF; RR e TO acham o governador no SAPL pelo nome civil da ficha.

---

## Contrato dos dados (`dados/`)

Todos os arquivos são JSON em UTF-8, compactos (sem espaços), gerados pelos scripts. Datas em `AAAA-MM-DD`.

### Fonte

Todo bloco de informação leva uma `fonte` (ou uma lista `fontes`):

```json
{ "veiculo": "Câmara dos Deputados", "titulo": "Dados Abertos: deputado 204379", "url": "https://...", "data": "2026-10-15" }
```

`veiculo` = quem publicou; `titulo` = o que é; `url` = link que uma pessoa consegue abrir (prefira a página humana; se só existir API, use a API); `data` = data do dado ou da consulta.

### IDs das pessoas

| Prefixo | Quem | Exemplo |
|---|---|---|
| `dep-<id Câmara>` | deputado(a) federal | `dep-204379` |
| `sen-<código Senado>` | senador(a) | `sen-5672` |
| `pres-<slug>` / `vp-<slug>` | presidente / vice | `pres-lula` |
| `min-<slug>` | ministro(a) | `min-saude` (slug do ministério) |
| `stf-<slug>` | ministro(a) do Supremo Tribunal Federal | `stf-flavio-dino` (slug do nome que o STF usa; o id fica preso ao número do ministro no STF, `idStf`, e não muda se o STF mudar a grafia) |
| `gov-<UF>` / `vgov-<UF>` | governador(a) / vice em exercício | `gov-BA` |
| `dest-<UF>-<SQ_CANDIDATO TSE>` | deputado(a) estadual ou distrital | `dest-BA-50001603470` |
| `pref-<IBGE>` / `vpref-<IBGE>` | prefeito(a) / vice | `pref-2927408` |
| `ver-<IBGE>-<SQ_CANDIDATO TSE>` | vereador(a) | `ver-2927408-50002...` |
| `e26-<UF>-<SQ_CANDIDATO TSE>` | eleito(a) em 2026 sem cargo eletivo hoje, até a posse (`BR` para presidente e vice) | `e26-AP-30002530514` |

Os ministros do STF não têm `dados/pessoas/<id>.json`: o perfil é montado no navegador a partir de `dados/stf.json` (`EP.stf.carregar`, em `js/stf.js`), com `tipo: "stf"`.

Os perfis `e26-` também não têm `dados/pessoas/<id>.json`: são montados no navegador a partir de `dados/eleitos/<UF>.json` (`EP.eleitos.perfil`, em `js/proximos.js`). Só ganha `e26-` quem não tem cargo eletivo hoje; quem tem continua com o id de hoje (um endereço `e26-` dessa pessoa leva ao perfil de hoje). Depois da posse, o id deixa de existir (o endereço mostra uma mensagem com o link para a busca) e a pessoa aparece com o id do cargo (`dep-`, `sen-`, `gov-`...) quando as listas trocam.

### `dados/pessoas/<id>.json` (perfil completo)

```jsonc
{
  "id": "dep-204379",
  "tipo": "dep",                       // dep | sen | pres | vp | min | gov | vgov | dest | pref | vpref | ver
  "nome": "Nome usado no cargo",
  "nomeCivil": "Nome completo",
  "cargo": "Deputada federal",         // com o gênero certo
  "genero": "F",                       // "F" | "M" | null
  "uf": "AP",
  "municipio": null,                   // prefeito/vereador: { "ibge": "2927408", "nome": "Salvador" }
  "partido": "MDB",
  "foto": "img/pessoas/dep-204379.jpg",// caminho local (240 px de largura) ou URL externa ou null
  "fotoCredito": "Câmara dos Deputados",
  "nascimento": "1983-04-15",
  "naturalidade": "Macapá (AP)",
  "escolaridade": "Superior completo",  // declarada ao TSE na candidatura mais recente (mesma fonte para todos)
  "escolaridadeFonte": {},
  "ocupacao": { "txt": "Advogada", "ano": 2026, "fonte": {} },  // ocupação declarada ao TSE
  "mandato": { "inicio": "2023-02-01", "fim": "2027-01-31", "situacao": "Em exercício", "obs": null, "fonte": {} },
  "mandatosAnteriores": [ { "cargo": "Deputada federal", "inicio": "2019-02-01", "fim": "2023-01-31", "obs": null } ],  // obs: quando a Câmara só informa a legislatura (1987–1995) e as datas são as da legislatura
  "eleicao": { "ano": 2022, "cargo": "Deputada federal", "votos": 12345, "situacao": "Eleita por média", "fonte": {} },
  "eleicao2026": { "cargo": "Senadora", "situacao": "eleito", "txt": "Eleita senadora em 2026", "fonte": {} },
  "bens": { "ano": 2022, "total": 123456.78, "fonte": {} },
  "links": { "oficial": "https://www.camara.leg.br/deputados/204379", "email": null, "redes": [] },
  "comissoes": [ { "sigla": "CCJC", "nome": "Comissão de Constituição e Justiça e de Cidadania", "papel": "Titular" } ],
  "propostas": {
    "escopo": "Propostas apresentadas como deputada federal",
    "resumo": { "total": 120, "autor": 80, "coautor": 40, "lei": 3, "aprovada": 5, "andando": 70, "junta": 10, "arquivada": 30, "rejeitada": 1, "retirada": 1, "outra": 0 },
    "porTipo": { "PL": 100, "PEC": 2, "PDL": 18 },
    "porTema": [ { "tema": "Saúde", "n": 20 } ],
    "outros": { "total": 300, "porTipo": { "REQ": 250, "INC": 50 }, "url": "https://...", "txt": "Pedidos de informação, indicações e requerimentos" },
    "apoios": { "total": 376, "porTipo": { "PEC": 20, "REQ": 189 }, "txt": "Assinaturas só de apoio..." },  // Câmara: assinou só para a proposta de outra pessoa poder ser apresentada (não é autor nem coautor)
    "fonte": {},
    "lista": [
      {
        "id": "camara:2345678",
        "sigla": "PL 1234/2023",
        "tipo": "PL",
        "data": "2023-03-01",
        "ementa": "Texto oficial (ementa)",
        "s": "Explicação simples",      // preenchida por scripts/montar.py a partir de dados/simples/ (ausente = ainda não tem)
        "s_en": "Simple explanation",   // a mesma explicação em inglês
        "status": "lei",                // lei | aprovada | andando | junta | arquivada | rejeitada | parada | retirada | outra
        "statusTxt": "Virou a Lei nº 14.999/2024",
        "situacao": "Transformado em Norma Jurídica",  // texto oficial da situação
        "dataStatus": "2024-05-02",
        "papel": "autor",               // autor (autor principal / 1º a assinar) | coautor
        "temas": ["Saúde"],
        "url": "https://www.camara.leg.br/propostas-legislativas/2345678",
        "lei": { "nome": "Lei nº 14.999/2024", "url": "https://www.planalto.gov.br/..." }
      }
    ]
  },
  "gastos": { "ano": 2025, "total": 412345.67, "porTipo": [ { "tipo": "Passagens aéreas", "valor": 123.4 } ], "mandatoTotal": 1234567.89, "desde": "2023-02", "fonte": {} },
  "votacoes": {
    "escopo": "Votações com voto de cada um (nominais) no Plenário da Câmara desde fevereiro de 2023",
    "escopo_en": "Roll-call votes (where each member's vote is recorded) in the full Chamber of Deputies since February 2023.",
    "resumo": { "total": 300, "Sim": 150, "Não": 120, "Abstenção": 5, "Obstrução": 20, "Outro": 5 },
    "fonte": {},
    "arquivo": "dados/votacoes/camara.json",   // onde estão os detalhes de cada votação (compartilhados por todos)
    "votos": [ ["2345678-123", "Sim", "Não", "f"], ["2345678-120", "Não"] ]   // [chave no arquivo, voto, orientação, de quem]: os 2 últimos
                                                                            // só quando o partido da pessoa na época recebeu orientação publicada
                                                                            // (p = do partido, f = da federação, b = do bloco); da mais nova para a mais antiga
  },
  "fontes": [],
  "atualizado": "2026-10-15"
}
```

Campos sem informação: `null` (nunca invente). A lista de propostas vem **da mais nova para a mais antiga**.

**Votações.** O que foi votado é igual para todos os 513 (ou 81), então fica num catálogo por Casa, e o perfil guarda só a chave e o voto da pessoa. Cada votação tem também um arquivo próprio, com o voto de todos.

`dados/votacoes/camara.json` e `dados/votacoes/senado.json` (catálogo, da mais nova para a mais antiga):

```jsonc
{
  "votacoes": {
    "2345678-123": { "data": "2024-05-02", "hora": "20:56", "propostaId": "camara:2345678", "proposta": "PL 1234/2023",
                     "descricao": "Descrição oficial do que foi votado", "resultado": "Aprovado",   // "Aprovado" | "Rejeitado" | null
                     "categoria": "principal",                                                      // principal | mudanca | procedimento | outra
                     "placar": { "Sim": 300, "Não": 120, "Abstenção": 2, "Obstrução": 0, "Outro": 1, "total": 423 },
                     "url": "https://..." }   // página da proposta (Câmara) ou das votações da matéria (Senado)
  },
  "legenda": { "NCom": "Não Compareceu" },   // só no Senado: o que quer dizer cada código de voto
  "fonte": {}, "atualizado": "2026-10-15"
}
```

Chaves: Câmara = id da votação na Câmara (`2345678-123`); Senado = `senado-vot:<código>`. Votações secretas do Senado (escolha de autoridades) não entram, porque o voto de cada um não é divulgado.

`dados/votacoes/<casa>/<id>.json` (uma votação; `id` = id da Câmara, ex. `2236186-60`, ou o código do Senado, ex. `7107`). É o que `votacao.html?casa=<casa>&id=<id>` abre:

```jsonc
{
  "id": "2236186-60", "chave": "2236186-60", "casa": "camara",
  "data": "2026-10-14", "hora": "20:56",       // Câmara: hora do registro do resultado; Senado: fim da votação (null se não publicada)
  "proposta": { "sigla": "PLP 281/2019", "propostaId": "camara:2236186", "url": "https://www.camara.leg.br/propostas-legislativas/2236186",
                "ementa": "Texto oficial", "s": "Explicação simples", "s_en": "..." },   // s/s_en só se existirem em dados/simples/
  "descricao": "Rejeitada a Subemenda Substitutiva...", "resultado": "Rejeitado", "categoria": "principal",
  "placar": { "Sim": 252, "Não": 176, "Abstenção": 0, "Obstrução": 0, "Outro": 1, "total": 429 },   // contado a partir de "votos"
  "quorum": { "regra": "plp", "minimoSim": 257 },    // pec | plp | urgencia155 (com minimoSim) | maioria (com presentes) | null
  "orientacoes": [ { "lideranca": "Bl UniPpPsd...", "orientacao": "Sim", "tipo": "bloco", "partidos": ["PP", "PSD", "UNIÃO"] } ],
     // orientacao: Sim | Não | Abstenção | Obstrução | Liberado (o Senado escreve "LIVRE") | null (não orientou)
     // tipo: partido | federacao | bloco | governo | maioria | minoria | oposicao | bancada (Bancada Feminina do Senado)
     // partidos (só partido/federação/bloco): os partidos desta votação que dá para saber pelo nome publicado
  "orientacaoPartidos": { "PL": { "orientacao": "Sim", "lideranca": "PL", "tipo": "partido" } },  // a que vale para cada partido
  "votos": [ ["dep-204379", "Nome", "MDB", "AP", "Sim"] ],   // [pessoaId, nome, partido na época, UF, voto], em ordem alfabética;
                                                              // inclui quem não está mais no mandato
  "legenda": { "NCom": "Não Compareceu" },    // Senado: os códigos de voto usados nesta votação (Câmara: null)
  "presidente": "Davi Alcolumbre",            // Senado: quem presidia a sessão (Câmara: null; lá quem preside aparece com "Artigo 17")
  "aviso": { "oficial": { "Sim": 35, "Não": 375 }, "contado": { "Sim": 315, "Não": 87 } },   // placar publicado ≠ soma dos votos (raro)
  "url": "https://...",                       // Câmara: a sessão no portal (lá se escolhe a votação na lista); Senado: votações da matéria
  "fontes": [], "atualizado": "2026-10-23"
}
```

Na Câmara, a lista de votos traz só quem registrou voto (os ausentes não aparecem: "não registraram voto" = 513 − total). No Senado, traz os 81 da época, com códigos para quem não votou (NCom, MIS, LS, AP, P-NRV, Presidente...).

**Categoria** (regra fixa, `scripts/votacoes.py`, a partir da descrição oficial; olha o que vem depois de "Aprovado(a)", "Rejeitado(a)", "Mantido", "Votação nominal do(a)"): `procedimento` = requerimentos (urgência, adiamento, retirada de pauta, encerramento da discussão, preferência, quebra de interstício, calendário especial, inclusão) e recursos para levar ao Plenário (RICD arts. 117, 132 § 2º, 154, 155; RISF arts. 279 e 336); `outra` = parecer sobre os pressupostos de medida provisória (CF art. 62 § 5º), casos sobre o mandato de um parlamentar (sustação de ação penal, medida cautelar, representação) e questões de ordem; `mudanca` = emendas, subemendas, destaques, "mantido/suprimido o texto", artigos, parágrafos e expressões (RICD arts. 118 e 161; RISF art. 312); `principal` = o projeto, a PEC (cada turno), a medida provisória, o projeto de lei de conversão, o substitutivo (RICD art. 118 § 4º) e a redação final (RICD art. 195 § 1º). O resto fica em `outra`. Conferir: `python scripts/votacoes.py --cache --revisar` (grava `.cache/votacoes/categorias.txt`).

**Quórum** (só quando a regra é clara): `pec` = 3/5 em dois turnos (CF art. 60 § 2º: 308 deputados, 49 senadores); `plp` = maioria absoluta (CF art. 69: 257 / 41); `urgencia155` = urgência do art. 155 do Regimento da Câmara (257); `maioria` = projeto de lei, medida provisória ou lei de conversão: maioria dos votos, com a maioria absoluta presente (CF art. 47; RICD art. 183; RISF art. 288). Só para o texto principal (e para a urgência do art. 155); nunca para a redação final.

**Orientação de cada partido** (`orientacaoPartidos` e os pares do perfil): vale a orientação publicada mais específica do partido da pessoa NA ÉPOCA: a do próprio partido; senão a da federação (o nome traz os partidos: "Fdr PT-PCdoB-PV"); senão a do bloco, quando o partido aparece no nome abreviado do bloco ("Bl UniPpPsd..." = União, PP, PSD e outros que o nome cortado não mostra). Governo, Maioria, Minoria, Oposição e Bancada Feminina aparecem na lista, mas não contam como orientação de partido. Sem orientação identificável, nada é mostrado (nunca se deduz a orientação pelos votos).

**Situação das propostas (`status`)**, igual para Câmara, Senado e Assembleias:

| status | Quer dizer | Exemplo de `situacao` oficial |
|---|---|---|
| `lei` | virou lei (ou norma: decreto legislativo, resolução, emenda à Constituição) | Transformado em Norma Jurídica |
| `aprovada` | aprovada numa Casa e enviada à outra, ou esperando a sanção do presidente | Aguardando Apreciação pelo Senado Federal |
| `andando` | ainda em discussão | Aguardando Parecer, Pronta para Pauta |
| `junta` | está andando junto com outra proposta parecida (apensada) | Tramitando em Conjunto |
| `arquivada` | foi para o arquivo | Arquivada |
| `rejeitada` | rejeitada numa votação ou vetada por inteiro pelo presidente | Rejeitada, Vetado totalmente |
| `parada` | parou sem ser rejeitada: perdeu a validade (medida provisória não votada a tempo), ficou prejudicada, foi devolvida ao autor ou impugnada (a Constituição, art. 62, §§ 3º e 11, trata rejeição e perda de eficácia como coisas diferentes) | Perda de eficácia, Prejudicada, Devolvida ao(à) Autor(a) |
| `retirada` | o próprio autor desistiu | Retirado pelo(a) Autor(a) |
| `outra` | não deu para classificar com segurança | |

**Tipos que contam como "proposta"** (vão para `lista`): PL, PLP, PEC, PDL, PRC, MPV, PLV, PLN e equivalentes antigos/do Senado (PDC, PLS, PLC, PDS, PRS, PEC do Senado). O resto (requerimentos, indicações, emendas, pareceres) entra só como contagem em `outros`.

### Listas gerais

- `dados/camara.json`: `{ "total": 513, "porPartido": [{"partido":"PL","n":90}], "membros": [ {"id","nome","partido","uf","foto","genero","eleicao2026"} ], "fonte": {}, "atualizado" }`
- `dados/senado.json`: mesmo formato, com `"fimMandato"` em cada membro.
- `dados/executivo.json`: `{ "presidente": {resumo}, "vice": {resumo}, "fontes": [], "atualizado" }` (resumo = `id, nome, cargo, partido, foto, genero, mandato, eleicao2026`).
- `dados/manual/ministros.json` e `dados/manual/governadores.json`: pesquisados à mão, **sempre com fonte** em cada item.
- `dados/estados/<UF>.json`: `{ "uf", "nome", "capital": {"ibge","nome"}, "governador": {...}, "vice": {...}, "senadores": ["sen-..."], "deputadosFederais": ["dep-..."], "deputadosEstaduais": { "total", "aviso", "fonte", "membros": [ {"id","nome","partido","foto","genero","votos","situacao2022","eleicao2026"} ] }, "municipios": 417, "atualizado" }`
- `dados/cidades.json`: todas as cidades do Brasil para a busca da página da cidade: `[[ibge, nome, UF], ...]` (feito por `scripts/montar.py`).
- `dados/mapa-brasil.json`: o mapa da página do estado (feito por `scripts/mapa.py`): `{ "fonte", "largura", "altura", "sigla", "seloAltura", "ufs": { "BA": { "d": "caminho SVG", "x", "y" (lugar da sigla), "selo": { "x", "y" } (só nos estados pequenos: a sigla fica fora, ligada por uma linha) } } }`.
- `dados/cidades/<UF>.json`: lista para escolher a cidade: `[ {"ibge","nome","prefeito":"Nome (PARTIDO)"} ]`.
- `dados/cidades/<UF>/<IBGE>.json`: `{ "ibge","nome","uf","prefeito":{...},"vice":{...},"vereadores":{"total","aviso","fonte","membros":[...]},"onde"?: {"camara":{...},"prefeitura":{...}},"atualizado" }`. `onde` vem do mapa das Câmaras e prefeituras (`dados/municipios/<UF>.json`, abaixo).
- `dados/municipios/<UF>.json` (mapa das Câmaras Municipais e prefeituras, feito por `scripts/municipios/mapear.py`): `{ "uf", "atualizado", "fontes", "cidades": { "<IBGE>": { "camara": { "site", "sistema" (sapl | sagl | nopaper | outro | null), "api", "propostas" (página pública das proposições), "propostasOnline" (true | false | null), "sic" (pedido de informação), "conferido", "motivo"/"motivo_en" (por que não dá, quando não publica) }, "prefeitura": { "site", "transparencia", "sic", "diarioOficial": { "nome", "url", "plataforma" } } } } }`. Só endereços oficiais. É o que o perfil mostra no quadro **"Onde ver mais"** quando falta um dado.
- `dados/busca.json`: `[[id, nome, cargo curto, UF, partido, cidade ou null, cargo em inglês (opcional)], ...]` (sem vereadores, que aparecem na página da cidade, menos os eleitos em 2026). Os ministros do STF entram pelo `montar.py` (`_stf_busca`), com o cargo "Ministro do Supremo Tribunal Federal" ou "Ministra do Supremo Tribunal Federal" e UF, partido e cidade `null`. Quem foi eleito em 2026 e não tem cargo eletivo hoje entra com o id `e26-`, o cargo de eleito ("Deputada federal eleita") e o cargo em inglês na 7ª coluna ("Federal Deputy-elect"), que o `js/busca.js` usa quando a página está em inglês; os vereadores eleitos em 2026 entram com o id `ver-` e o cargo "Vereadora · deputada estadual eleita" (`montar.py`, `eleitos.busca_e_selos`; ninguém aparece duas vezes).
- `dados/simples/<00-99>.json`: cache das explicações simples: `{ "camara:2345678": { "pt": "Explicação simples", "en": "Simple explanation" }, ... }` (arquivo = 2 últimos dígitos do número). Escritas por `scripts/simplificar.py` só a partir da ementa oficial: no máximo 35 palavras, começando por um verbo (cria, muda, proíbe...), sem palavras de opinião. Quem quiser corrigir uma explicação edita o cache e roda `scripts/montar.py`.
- `dados/tse/federais.json`: o que o TSE diz de cada pessoa do Congresso e do Executivo (eleição de 2022, bens declarados, resultado de 2026), juntado aos perfis por `scripts/montar.py`.

`eleicao2026.situacao`: `eleito` | `reeleito` | `segundo-turno` | `nao-eleito` | `suplente` | `candidato` | `nao-concorreu` | `null` (não sabemos). `eleicao2026.txt` e `txt_en`: a frase pronta para mostrar. Nas fichas das cidades (`dados/cidades/<UF>/<IBGE>.json`), o `montar.py` põe o `eleicao2026` também em prefeitos, vices e vereadores eleitos em 2026 para outro cargo (`eleitos.busca_e_selos`).

Campos extras de quem vem do TSE (estados e cidades): `aConfirmar` (o TSE ainda não fechou o resultado, ou a pesquisa à mão ainda não é do mandato em curso), `sq<ano>` e `eleito<ano>` (a ficha de quem foi eleito para o cargo, com o ano da eleição na chave: `eleito2022`, `eleito2024`, `eleito2026`...), `situacao<ano>` dos deputados estaduais, `vago` (com `txt`/`txt_en`), `votosDaChapa`, `desde` e `comoAssumiu`/`comoAssumiu_en` (quando quem está no cargo não é quem foi eleito, ex.: vice que assumiu), `nota`/`nota_en` (observação da pesquisa à mão), `casa`, `aviso`/`aviso_en` e `fonteMunicipios`. Nos estados, `eleicaoGoverno` (ano da eleição do governador em exercício) e `deputadosEstaduais.eleicao` (ano da eleição da Assembleia em curso).

**Gastos (Câmara):** valores líquidos da cota parlamentar, iguais aos da página oficial de cada deputado, incluindo o que a página oficial mostra (passagens compradas pelo sistema da Câmara, o SIGEPA, e a complementação do auxílio-moradia). Não entram o salário nem a verba de gabinete (salários de assessores); por isso o site diz "gastos da cota" e não "tudo o que custou".

**Mesma régua nos perfis federais (`scripts/montar.py`):** ocupação e escolaridade vêm, para todo mundo, da candidatura mais recente no TSE (`ocupacao`, `escolaridade`, `escolaridadeFonte`); as Casas e o Planalto descrevem isso de jeitos diferentes, ou não descrevem. "Mandatos anteriores" mostra só mandatos no mesmo cargo/Casa (deputado: Câmara; senador: Senado; presidente: Presidência), também para todo mundo.

### Assembleias e Câmaras Municipais (`dados/assembleias/<UF>.json` e `dados/camaras/<IBGE>.json`, feitos por `scripts/legislativos.py`)

Cada Casa tem um coletor com a função `coletar() -> dict` (`scripts/assembleias/<uf>.py`, `scripts/camaras/c<IBGE>.py`), que usa as ajudas de `scripts/regional.py`. Se o site da Casa cair, o coletor lança a exceção e o `legislativos.py` mantém o arquivo de antes; o resumo de cada rodada fica em `dados/legislativos.json`.

```jsonc
{
  "uf": "SP", "ibge": null,                       // Câmara Municipal: "ibge": "3550308"
  "casa": "Assembleia Legislativa do Estado de São Paulo", "casa_en": "Legislative Assembly of the State of São Paulo",
  "sigla": "Alesp", "site": "https://www.al.sp.gov.br", "sic": "https://... (pedido de informação, se houver)", "fonte": {},
  "cobertura": { "lista": true, "propostas": true, "votacoes": false, "gastos": true },
  "escopoPropostas": "Projetos apresentados desde ...", "escopoPropostas_en": "...",
  "legislatura": { "numero": 20, "inicio": "2023-03-15", "fim": "2027-01-31" },   // nem toda Casa tem
  "membros": [ { "id": "dest-SP-250001612345", "nome", "nomeCivil", "partido", "genero", "foto", "url",
                 "exercicio": "Suplente em exercício", "exercicio_en": "Substitute in office" } ],   // exercicio só de suplente
  "notas": ["o que falta e por quê"], "notas_en": ["..."], "atualizado": "2026-10-23"
}
```

- Ids: os mesmos da lista do TSE (`dest-<UF>-<SQ_CANDIDATO>` da eleição da legislatura; `ver-<IBGE>-<SQ_CANDIDATO de 2024>`), achados pelo nome com `regional.candidatos_tse` + `regional.casar_tse` (na dúvida, não liga: o id vira `dest-<UF>-x<nome>`).
- Quem tem algo a mais (propostas, votações, gastos, links) ganha `dados/pessoas/<id>.json`, com os mesmos campos dos perfis federais; `gastos` traz também `nome`/`nome_en` (o nome da verba naquela Casa) e `meses` (o primeiro e o último mês do ano mostrado). Ids das propostas: `<sigla da Casa>:<id oficial>` (ex.: `alesp:1000473`).
- `scripts/montar.py` põe a lista oficial no lugar da lista do TSE em `dados/estados/<UF>.json` (`deputadosEstaduais`) e em `dados/cidades/<UF>/<IBGE>.json` (`vereadores`), com `oficial: true`, `infoCasa` (cobertura, notas, site e `sic`, para o quadro "O que o site já tem da Casa") e `extras: true` em quem tem o arquivo a mais; e troca os deputados estaduais da busca. Não usa a lista de uma legislatura que já acabou.
- Sem promessas: em `notas`, avisos e escopos, nada de "ainda não" ou "em breve". Diga o que não entra, por quê e onde ver. Quando falta um dado no perfil, ele mostra o quadro "Onde ver mais" (`ondeVerHtml` em `js/pessoa.js`): as notas da Casa sobre propostas, os links oficiais e como pedir pela Lei de Acesso à Informação.

### Mandatos anteriores (`dados/historico/`, feitos por `scripts/historico.py`)

Quem foi **eleito** para cada mandato, segundo o TSE, com o **partido da eleição** (sem votos; eleições suplementares não entram), e, no Brasil, os **ministros** de cada governo (de 1995 a 2022).

- `dados/historico/indice.json`: `{ "brasil": [mandato], "estados": [mandato], "cidades": [mandato], "fontes", "aviso", "aviso_en", "atualizado" }`, do mais novo para o mais velho. Mandato = `{ "id": "2019", "eleicao": 2018, "inicio": "2019-01-01", "fim": "2023-01-01", "rotulo": "2019 a 2022", "rotulo_en": "2019–2022", "aviso"?, "aviso_en"? }` (`fim` = dia da posse dos próximos; no Brasil também `"congresso": {"legislatura", "inicio", "fim"}`). O site calcula o mandato de hoje com `inicio <= hoje < fim`.
- `dados/historico/brasil/<id>.json`: `{ "id", "eleicao", "inicio", "fim", "legislatura", "presidente", "vice", "mudancas"?, "nota"?, "senado": {"total", "membros", "fontes", "aviso", "aviso_en", "suplementar"?}, "camara": {"total", "membros", "fonte", "aviso", "aviso_en"} }`. Pessoa = `{ "nome", "nomeCivil"?, "partido", "genero", "situacao", "situacao_en", "fontes" }`; membro = `{ "nome", "nomeCivil"?, "partido", "genero", "uf", "eleito"? (senado: ano da eleição) }`; `mudancas` = `[{ "data", "txt", "txt_en", "fontes" }]`; `suplementar` = `[{ "uf", "data", "txt", "txt_en" }]`.
- `dados/historico/estados/<UF>.json`: `{ "uf", "mandatos": { "<id>": { "eleicao", "governador", "vice", "avisoVice"?, "suplementar"? (datas), "deputados": {"total", "cadeiras", "membros", "fonte", "aviso", "aviso_en"} } } }`. Senadores e deputados federais do estado saem do arquivo do Brasil do mesmo mandato.
- `dados/historico/cidades/<UF>/<id>.json`: `{ "uf", "id", "eleicao", "inicio", "fim", "fonte", "aviso", "aviso_en", "avisoVice"?, "avisoPartidoVice"?, "cidades": { "<IBGE>": cidade }, "depois"?: { "<IBGE>": ano da 1ª eleição (a cidade ainda não existia) } }`. Cidade (compacta, para caber): `{ "p": [nome, nomeCivil, partido, genero, turno], "v": [nome, nomeCivil, partido, genero], "ver": [[nome, partido, genero]], "vagas"? (cadeiras, quando o TSE lista menos eleitos), "exc"? (eleitos tirados por renúncia/registro negado), "supP"?/"supV"? (datas de eleições suplementares), "nm"? (nome da cidade no TSE naquela eleição) }`.
- `dados/historico/indice.json`: no Brasil, `"ministros": true` quando o mandato tem a lista de ministros.
- `dados/historico/ministros/<id>.json`: `{ "id", "inicio", "fim", "governos": [{ "presidente", "inicio", "fim", "inicioGoverno", "fimGoverno", "nota", "nota_en", "pastas": [pasta], "fontes": [fonte] }], "atualizado" }` (em 2015 a 2018, dois governos: Dilma até 12/5/2016 e Temer desde 12/5/2016; o nome de cada presidente é o com que assinava os decretos no Diário Oficial). Pasta = `{ "nome", "nome_en" (null = sem tradução segura), "grupo" ("ministerio" | "orgao"), "pessoas": [pessoa], "semEfeito"?: [anulada], "lacunas"?: [[de, até]], "lacunaFonte"?: "lista" | "dou" }`. Anulada = nomeação do Diário Oficial tornada sem efeito por outro decreto (não é período de ninguém) = `{ "nome", "tipo" ("titular" | "interino"), "nomeacao", "anulacao" (datas dos dois decretos), "outrasAnulacoes"?, "f": [os dois decretos] }`; quando uma cai dentro de um intervalo sem ninguém, o aviso fala em "nomeação válida". Pessoa = `{ "nome", "tipo" ("titular" | "interino" | "substituto" = quadro "Interino" da lista), "periodos": [[início, fim ou null]], "posto"?, "conhecido"?, "cargoNoAto"?, "obs"?, "obs_en"?, "f": [índices em "fontes"] }`. Só entram os períodos que tocam o mandato; quem sai no dia da posse do governo seguinte não entra nele.
- `dados/manual/ministros-anteriores.json`: o mesmo formato, por governo inteiro (`"governos": [{ "id", "presidente", "inicio", "fim", "nota", "nota_en", "pastas", "fontes" }]`), mais `"sobre"`, `"semEfeito"` (o que é), `"tipos"` e `"atualizado"`.
- Regras dos ministros: titular, interino e quadro "Interino" como a fonte diz; datas da fonte (no Diário Oficial, a data do decreto); saída sem data quando a fonte não traz; nomeação tornada sem efeito aparece no cartão com os dois decretos, sem contar como período; aviso de intervalo de mais de 15 dias sem ninguém na fonte. Entram os ministérios e os órgãos da Presidência que a fonte chama de ministro; o advogado-geral da União e o presidente do Banco Central não entram.
- Limites combinados: até ~40 MB, ~400 arquivos e ~600 KB por arquivo (hoje: 252 arquivos, 20,9 MB, o maior com 407 KB). Por isso os vereadores vão sem o nome civil.

### Ministros do STF (`dados/stf.json`, feito por `scripts/stf.py`)

Quem está no Supremo Tribunal Federal hoje, na ordem oficial do tribunal (o presidente, o vice e os outros por antiguidade: a data da posse, depois a da nomeação, depois a idade, Regimento Interno do STF, art. 17), e como cada um chegou lá. Só fontes oficiais: STF (página "O STF", Pastas dos Ministros da Biblioteca, Turmas, Presidentes), Dados Abertos do Senado e a cópia do Diário Oficial guardada na Biblioteca do STF.

```jsonc
{
  "tribunal": "Supremo Tribunal Federal", "sigla": "STF",
  "cadeiras": 11, "cadeirasTurma": 5, "idadeLimite": 75, "maioriaSenado": 41,
  "presidencia": { "presidente": "stf-...", "vice": "stf-...", "desde": "2025-09-29", "periodo": "2025–2027", "anos": 2, "fontes": [] },
  "turmas": [ { "numero": 1, "nome": "Primeira Turma", "presidente": "stf-...", "membros": ["stf-..."], "cadeiras": 5 } ],
  "fonteTurmas": [],
  "ministros": [ {                                   // na ordem oficial
    "id": "stf-flavio-dino", "idStf": 54,            // idStf: o número do ministro no STF (prende o id)
    "pasta": "FlavioDino",                           // nome da pasta na Biblioteca do STF
    "nome": "Flávio Dino", "nomeCivil": "Flávio Dino de Castro e Costa", "genero": "M",
    "papel": null,                                   // "presidente" | "vice" | null
    "decano": false, "turma": 1, "presideTurma": true,   // quem preside o STF: turma null
    "foto": "img/pessoas/stf-flavio-dino.jpg", "fotoUrl": "https://portal.stf.jus.br/util/imagem.asp?id=...", "fotoCredito": "Supremo Tribunal Federal",
    "nascimento": "1968-04-30", "naturalidade": "São Luís (MA)",
    "aposentadoria": { "data": "2043-04-30", "idade": 75, "fontes": [] },            // 75 anos: EC 88/2015
    "indicacao": { "presidente": "Luiz Inácio Lula da Silva", "presidenteGenero": "M", "data": "2023-11-27",
                   "mensagem": "Mensagem nº 627, de 27 de novembro de 2023", "dou": "citação do DOU",
                   "vaga": { "motivo": "aposentadoria", "de": "Rosa Maria Pires Weber", "nome": "Rosa Weber" },  // motivo: aposentadoria | falecimento
                   "fontes": [] },
    "senado": { "materia": "MSF 88/2023", "codigoMateria": 161290, "url": "página da matéria", "ementa": "texto oficial",
                "chegou": "2023-11-27", "tramitando": false,
                "ccj": { "data", "sim", "nao", "abstencao", "unanimidade", "aprovado", "texto" },
                "plenario": { "data", "sim", "nao", "abstencao", "total", "resultado": "aprovada", "texto" },  // resultado: aprovada | rejeitada
                "minimoSim": 41, "fontes": [] },     // "texto": o trecho oficial do resultado (null quando o placar veio só da votação estruturada)
    "nomeacao": { "data": "2024-01-31", "decreto": "Decreto de 31 de janeiro de 2024", "aPartirDe": "2024-02-22",
                  "dou": "citação do DOU", "douData": "2024-01-31", "fontes": [] },
    "posse": { "data": "2024-02-22", "fontes": [] },
    "presidencia": null,                             // de quem preside: { "posse": "2025-09-29" }
    "links": { "gabinete", "pasta", "curriculo", "biografia" },   // páginas oficiais do STF ("Onde ver mais")
    "fontes": []
  } ],
  "vagas": [ { "de": "Luís Roberto Barroso", "motivo": "aposentadoria", "desde": "2025-10-18", "pendente": false, "fontes": [],
               "indicacoes": [ { "nome", "materia", "codigoMateria", "url", "ementa", "chegou", "tramitando", "ccj", "plenario", "minimoSim", "fontes" } ] } ],
  "decisoes": { "total": 166339, "ano": 2025, "fonte": {} },   // o total do tribunal publicado na página "O STF" (null se sumir)
  "links": { "corteAberta", "corteAbertaSobre", "composicao", "turmas", "ostf" },
  "regras": { "fontes": [] },                         // Constituição, EC 122/2022, EC 88/2015, Regimento Interno do STF
  "fontes": [],
  "conferido": "2026-10-29",                          // a última leitura completa dos sites (o robô lê de novo 7 dias depois)
  "atualizado": "2026-10-29"
}
```

- `vagas`: uma por cadeira vazia (11 − número de ministros), com as indicações para o STF que o Senado recebeu neste ano e no anterior; `pendente: true` quando a cadeira não tem nenhuma indicação. O site mostra a vaga como mais um cartão, depois dos ministros.
- O perfil `pessoa.html?id=stf-<slug>` é montado por `js/stf.js` a partir deste arquivo (não há `dados/pessoas/stf-*.json`).
- Mesma régua: os mesmos campos para todos. Podem ser `null`: `papel`, `turma` (quem preside o STF não fica em Turma), `presidencia`, `nomeacao.aPartirDe` (só existe quando o decreto marca outra data para valer), `senado.ccj.abstencao` (os textos oficiais da CCJ não falam em abstenções: `null` para todos, e o site não mostra) e `senado.plenario.texto` (quando o placar veio só da votação estruturada da API). Os outros campos existem para os 10; se um faltar na fonte oficial, fica `null` e o site não mostra a linha.

### Quem foi eleito em 2026, até a posse (`dados/eleitos/`, feitos por `scripts/eleitos.py`)

Quem foi eleito em 2026 para presidente e vice, governador e vice, senador (com os 2 suplentes), deputado federal e deputado estadual ou distrital, só enquanto não tomou posse: cada cargo sai no dia da posse, e o arquivo que fica vazio é apagado. Fontes: TSE (candidaturas com a situação depois da totalização, bens, votação por município e zona, DivulgaCandContas) e Planalto (Constituição, Lei 9.504/1997).

```jsonc
// dados/eleitos/<UF>.json (um por estado; as chaves de um cargo que já tomou posse somem)
{
  "uf": "AP", "nome": "Amapá", "eleicao": 2026,
  "governo": { "posse": "2027-01-06", "fim": "2031-01-06", "governador": eleito, "vice": eleito },
  "senado": { "posse": "2027-02-01", "fim": "2035-02-01", "eleitos": [ eleito + "suplentes": [eleito, eleito] ], "continuam": [continua] },
  "camara": { "posse": "2027-02-01", "fim": "2031-02-01", "vagas": 8, "membros": [eleito] },
  "assembleia": { "casa", "casa_en", "sigla", "posse", "fim", "vagas", "membros": [eleito], "fontePosse"? },  // fontePosse: RS, DF e RR (posse fora de 1º/2)
  "contas": { "senado"|"camara"|"assembleia": { "total", "reeleicao", "troca", "novo" } },
  "turnos": { "1": "2026-10-04", "2": "2026-10-25" },
  "tiposBem": { "<código do tipo de bem no TSE>": ["Casa", "House"] },   // inglês null = mostra em português
  "fontes": { "candidaturas", "resultados", "bens", "posse": [] }, "atualizado": "2026-10-29"
}
// eleito
{ "id": "e26-AP-30002530514", "link": "e26-AP-30002530514",   // link: o perfil para onde o site leva (o de hoje, se a pessoa tem cargo)
  "tipo": "dep",                      // pres | vp | gov | vgov | sen | supl1 | supl2 | dep | dest
  "cargo": "Deputada federal", "uf": "AP", "nome": "Dra. Erica", "partido": "PODE", "genero": "F", "foto": "URL do TSE ou img/pessoas/...",
  "numero": "2000", "votos": 15358, "turno": 1, "situacao": "Eleita por QP", "situacao_en": "Elected through the party's vote quota",
  "posse": "2027-02-01", "fim": "2031-02-01",
  "chegada": "novo",                  // reeleicao (o mesmo cargo hoje) | troca (outro cargo eletivo hoje) | novo (nenhum)
  "atual"?: { "id": "dep-204353", "cargo": "Deputada federal", "onde": "AP" },   // o cargo eletivo de hoje
  "antes"?: { "id": "pref-3118601", "cargo": "Prefeita", "onde": "Contagem (MG)" },   // deixou para concorrer, e o site ainda mostra
  "federacao"?: { "nome", "sigla", "partidos": [] },
  "chapa"?: { "id", "nome" }, "votosDaChapa"?: true,   // vices e suplentes: os votos são os da chapa
  // só quem não tem cargo hoje (link = id), para o perfil e26-:
  "nomeCivil", "nascimento", "ufNascimento", "ocupacao", "escolaridade",
  "bens": { "total": 524076.7, "itens": [["13", 72290.67]] },   // [código do tipo, valor], na ordem da declaração; sem a descrição
  "tse": "página da candidatura no DivulgaCandContas", "fonte2turno"? }
// continua (senador eleito em 2022, até 2031)
{ "id": "sen-3830", "nome", "partido", "uf", "genero", "foto", "fimMandato": "2031-01-31", "link",
  "eleito2026"?: { "cargo", "posse", "situacao", "situacao_en" },               // foi eleito para outro cargo em 2026
  "assume"?: { "nome", "partido", "genero", "foto", "tse" } }                   // o 1º suplente da chapa de 2022, que assume a vaga
```

- `dados/eleitos/BR.json`: `{ "eleicao", "posses": { "presidente", "governador", "congresso", "assembleias": { "padrao", "excecoes": { "DF", "RR", "RS" } } }, "presidencia"?: { "posse", "fim", "presidente": eleito, "vice": eleito }, "senado"?: { "posse", "eleitos": [curto], "continuam": [continua], "fontes" }, "camara"?: { "posse", "vagas": 513, "membros": [curto] }, "contas": { "presidencia"|"governadores"|"senado"|"camara"|"assembleias": { "total", "reeleicao", "troca", "novo" } }, "turnos", "fontes", "atualizado" }`. Curto = `{ "id", "link", "nome", "partido", "uf", "genero", "foto", "chegada", "votos", "situacao", "atual"?: { "cargo", "onde" } }`.
- `dados/eleitos/municipal.json` (continua depois das posses): `{ "proxima": { "ano": 2028, "turno1", "turno2", "posse", "fim", "mandato": [2029, 2032], "fontes" }, "cidades": { "<IBGE>": { "suplementares"?: [ { "data", "nome", "situacao" (feita | marcada | sem-resultado), "cargos", "eleitos"?: { "prefeito", "vice", "vereadores": [ { "nome", "partido", "numero", "situacao", "foto", "tse" } ] }, "fonte" } ], "eleitos2026"?: [ { "link", "nome", "partido", "genero", "foto", "cargo", "uf", "posse", "chegada", "hoje": { "cargo" }, "deixou"? } ] } }, "fontesSuplementares", "fontesEleitos", "atualizado" }`.
- Mesma régua: os mesmos campos para todos os eleitos. Os bens mostram só o tipo e o valor (a descrição é texto livre e pode ter endereço ou número de conta: fica na página da candidatura no TSE). Nada de CPF. Ordem das listas: alfabética (o site ordena).

---

## Contrato das aulas (`conteudo/entenda/parte-N.json` e `conteudo/entenda/en/parte-N.json`)

Cada parada do mapa é uma "parte". A versão em inglês tem exatamente os mesmos slides, na mesma ordem, com os mesmos ids de fonte (só os textos mudam; as fontes continuam sendo as oficiais brasileiras). No inglês, o título da fonte termina com " (in Portuguese)" e, quando foi traduzido, leva `"lang": "en"` (sem isso, o site marca o título como português para o leitor de tela). No glossário em inglês, o `termo` fica só em inglês (ex.: "alternate") e o nome em português vai no fim do `simples` ("In Portuguese: {{suplente}}."), porque o botão 📖 só aparece quando o termo inteiro está no texto do slide. Nos textos, `**palavra**` vira negrito e `{{termo}}` marca um termo em português (só nos campos de texto: `titulo`, `texto`, `txt`, `mais`, `coruja`, `simples`, `exemplo`, `explica`, `moral`, `nota`, `pergunta`, `opcoes`, `itens`; nunca nas fontes).

```jsonc
{
  "parte": 1, "ic": "🤝", "nome": "O que é política?",
  "resumo": "Uma frase dizendo o que a parte ensina.",
  "fontes": [ { "id": "cf-art1", "veiculo": "Planalto", "titulo": "Constituição Federal, art. 1º", "url": "https://...", "data": "1988-10-05" } ],
  "glossario": [ { "termo": "mandato", "simples": "O tempo que a pessoa eleita fica no cargo." } ],
  "slides": [ { "tipo": "...", "...": "...", "fontes": ["cf-art1"] } ]
}
```

Tipos de slide: `abertura`, `explica`, `cards` (cartões que viram), `passos` (escada 3D), `comparar` (portas que abrem), `numeros` (blocos que caem), `historia` (quadrinhos que folheiam), `quiz` (peças 3D), `simulador` (`quem-cuida`, `quociente`, `caminho-lei`, `votos-precisos`, `caminho-voto`, `lacre-digital`, `confira-boletim`). Os campos de cada tipo e as ilustrações disponíveis estão descritos no começo de `js/entenda.js`. Qualquer slide pode ter um botão para outra página do próprio site: `"link": { "url": "brasil.html#os-ministros", "ic": "👔", "txt": "Ver os ministérios de hoje" }` (só aceita páginas do site; no inglês, o link já leva `?lang=en`). Para testar uma parte nova sem mexer nas outras: `entenda.html?teste=1` carrega `testes/parte-teste.json` como parte 1. Um botão de link pode levar a outra parada (`"url": "entenda.html#parte-10"`): o mapa fecha a parada aberta e voa até a outra. `"pular": true` num slide põe o botão "⏭ Pular a parte técnica e ir para o fim" (usado antes da parte técnica opcional da parada 10).

## Publicar

Repositório **público** no GitHub ([lucastaonline/entendapolitica](https://github.com/lucastaonline/entendapolitica)): o código aberto ajuda a mostrar a imparcialidade, e repositório público tem minutos ilimitados no GitHub Actions para a atualização diária. Site na Vercel (projeto `entendapolitica`, Framework Preset: **Other**, sem comando de build, pasta raiz `./`): cada commit na `main` (inclusive os do workflow diário) é publicado sozinho. Commits com o e-mail noreply do GitHub (senão a Vercel bloqueia o deploy). O workflow junta as mudanças com a `main` antes de enviar (`git pull --rebase`), então dá para publicar uma correção enquanto ele roda. **Nada é publicado sem o dono pedir.**

Antes de publicar algo novo: nenhum segredo no código (chaves ficam nos segredos do GitHub, como `OPENAI_API_KEY`) e nenhum dado pessoal desnecessário (o `montar.py` tira números de CPF que aparecem em textos oficiais, com `comum.sem_documentos`).
