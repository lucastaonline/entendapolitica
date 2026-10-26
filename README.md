# Entenda Política

Site estático (HTML, CSS e JS puros, sem build no navegador) que explica como a política brasileira funciona, de um jeito que **uma criança de 10 anos entenda**, e mostra **quem está no mandato hoje**, com tudo o que cada pessoa propôs, o que foi aprovado e o que virou lei. **Tudo com fonte. Tudo imparcial.**

Mesma identidade visual do [Entenda o 2º turno](https://entendaosegundoturno.vercel.app): fundo creme, azul `#1f3a5f`, amarelo `#f2b705`, letra do sistema bem grossa, emojis, botões "gordinhos" e peças 3D feitas só com CSS.

## As 4 portas da página inicial

1. **Entenda a política** (`entenda.html`): um **mapa 3D** (tabuleiro) com 9 paradas: o que é política (escola), os Três Poderes, país/estado/cidade, os cargos (torre), o Congresso (no centro), como nasce uma lei, eleições (urna), quem julga e fiscaliza (tribunal) e como participar (palanque). Uma trilha amarela sugere a ordem, mas dá para clicar em qualquer lugar. Ao clicar, a câmera "mergulha" no lugar e abre a **aula daquela parada**: uma apresentação com muito 3D (escadas para processos, cartões que viram, quadrinhos que folheiam, quiz e simuladores). No fim: estrela no mapa e "próxima parada". O progresso fica salvo no aparelho.
2. **A política do Brasil** (`brasil.html`): presidente, vice, ministros, os 81 senadores e os 513 deputados federais, com busca por qualquer político.
3. **A política do meu estado** (`estado.html`): a pessoa escolhe o estado num mapa 3D com o formato real de cada estado (malha do IBGE; os estados pequenos têm a sigla num selo fora deles, ligado por uma linha) ou digitando o nome. Mostra governador e vice, os senadores e deputados federais do estado e os deputados estaduais. No fim, um campo leva para a página da cidade.
4. **A política da minha cidade** (`cidade.html`): a pessoa digita o nome da cidade (as 5.569 do Brasil, com o estado ao lado para desempatar) e vê prefeito, vice e vereadores, além do que cada um faz. Brasília e Fernando de Noronha têm explicação própria (não têm prefeitura comum). Endereço: `cidade.html?ibge=<código IBGE>`; os endereços antigos `estado.html?uf=XX&cidade=<IBGE>` levam para lá.

Nas páginas do Brasil, do estado e da cidade, o campo **Ver outro mandato** mostra quem foi **eleito** em cada mandato anterior, segundo o TSE: desde 1995 no Brasil e nos estados, desde 1997 nas cidades. O padrão continua sendo o mandato de hoje; o passado tem endereço próprio (`brasil.html?mandato=2019`, `estado.html?uf=BA&mandato=2019`, `cidade.html?ibge=2927408&mandato=2021`) e uma faixa avisando, em texto, que é o passado.

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
2. **Fase 2:** propostas dos deputados estaduais, Assembleia por Assembleia. **Feita em 21 das 27** (lista oficial em 26; votações em 4; gastos em 5): ver "Assembleias Legislativas".
3. **Fase 3:** vereadores das capitais e das Câmaras com dados abertos (ex.: SAPL/Interlegis). **Capitais feitas** (lista oficial em 19 de 26, propostas em 8); outras 824 Câmaras com SAPL podem entrar (ver "Câmaras Municipais das capitais").

Mandatos: o site mostra **quem está no cargo hoje** e marca quem foi **eleito/reeleito em 2026**. As listas trocam sozinhas no dia da posse de quem foi eleito (presidente em 5/1/2027 e governadores em 6/1/2027, pela Emenda Constitucional 111/2021; Congresso em 1º/2/2027; prefeitos e vereadores em 1º/1/2029). Qual é o mandato de hoje sai das datas de posse (`scripts/mandatos.py`, a mesma regra para os coletores e para o navegador), nunca de um ano escrito no código. Os mandatos anteriores (quem foi eleito em cada um, segundo o TSE) ficam no campo **Ver outro mandato**.

## Regras de imparcialidade (valem para tudo)

1. **Mesma régua para todos.** Os mesmos campos, calculados do mesmo jeito, para todo mundo.
2. **Fonte em tudo.** Todo bloco de informação tem `fonte` (órgão oficial: Câmara, Senado, TSE, IBGE, Planalto, Diário Oficial; ou imprensa quando não houver fonte oficial).
3. **Ordem neutra.** Listas em ordem alfabética. Nada de ranking de "melhor" ou "pior".
4. **Sem cores de partido.** Nenhum partido tem cor própria. No plenário, cada fatia é um partido e as fatias alternam dois tons neutros de azul só para separar uma da vizinha (do maior partido para o menor); o partido em destaque acende em amarelo.
5. **Linguagem neutra.** Sem adjetivos de valor ("bom", "ruim", "polêmico", "importante"). Explicações simples dizem **o que a proposta faz**, nunca se é boa.
6. **Quem fez de verdade.** Separar **autor(a) principal** de **coautor(a)** (quem só assinou junto).
7. **Contexto nos números.** Ex.: "propor muitos projetos não quer dizer trabalhar mais ou melhor".
8. **Canal para corrigir.** Formulário "Viu algo errado ou que parece puxar para um lado?".

## Estrutura

```
index.html            página inicial (4 portas)
entenda.html          mapa 3D da política + aulas de cada parada (lê conteudo/entenda/[en/]parte-N.json)
brasil.html           política do Brasil (lê dados/executivo.json, dados/senado.json, dados/camara.json)
estado.html           política do meu estado (lê dados/mapa-brasil.json, dados/estados/UF.json e dados/cidades/UF.json)
cidade.html           política da minha cidade (lê dados/cidades.json e dados/cidades/UF/IBGE.json)
pessoa.html           perfil de uma pessoa (lê dados/pessoas/<id>.json e dados/votacoes/<casa>.json)
votacoes.html         todas as votações nominais da Câmara e do Senado (filtros por Casa, ano, tipo e resultado; busca)
votacao.html          uma votação: o que foi votado, resultado com plenário 3D, como cada partido votou, orientações e quem votou o quê
404.html              endereço não encontrado (a Vercel usa sozinha), com as 4 portas
imparcialidade.html   como cuidamos da imparcialidade
dados.html            de onde vêm os dados, com que frequência são atualizados e os limites
css/base.css          visual comum (cores, botões, cartões, janela) + acessibilidade (contraste, movimento, espaçamento)
css/tres.css          peças 3D que vieram do site do 2º turno (urna, cubos, formas)
css/tres-politica.css peças 3D novas (Congresso, Três Poderes, níveis, escola, torre, tribunal, palanque, escada...)
css/mapa.css          o mundo 3D do mapa (chão, lotes, placas, câmera)
css/entenda.css       as aulas (slides em 3D)
css/votacoes.css      as duas páginas de votações e o bloco "Como o Congresso votou" do Brasil
css/historico.css     a faixa "Você está vendo o passado" e o campo de mandatos
js/comum.js           idioma, acessibilidade, janela, fontes, ouvir, Libras, formatação, listas com busca (EP.combo), compartilhar
js/casa.js            monta uma Casa (Senado, Câmara, Assembleia, Câmara Municipal): plenário 3D com fatias e siglas por partido, filtros e lista de cartões
js/brasil.js, js/estado.js, js/cidade.js, js/pessoa.js   as páginas do Brasil, do estado, da cidade e de cada pessoa
js/votacoes.js        ajudas comuns das votações (EP.VOT), a lista de votações e o bloco do Brasil (#votos-recentes)
js/votacao.js         a página de uma votação
js/historico.js       mandatos anteriores: o campo "Ver outro mandato" e a página do passado (Brasil, estado e cidade)
js/tres.js, js/tres-politica.js   montam as peças 3D (cada modelo tem modo "cena" e modo "mundo")
js/mapa3d.js          monta o mapa 3D, câmera (voar até um lugar), girar, zoom, lista acessível
js/entenda.js         carrega o conteúdo, liga o mapa e as aulas (especificação dos slides no topo do arquivo)
conteudo/entenda/     texto das 9 paradas em português; conteudo/entenda/en/ em inglês
dados/                tudo o que os scripts geram (JSON); não edite à mão, exceto dados/manual/. dados/historico/ é feito por scripts/historico.py, que roda à mão
scripts/              coletores em Python (só biblioteca padrão + Pillow):
  camara.py, senado.py, executivo.py, tse.py   Câmara, Senado, presidente e vice, TSE e IBGE (todo dia)
  votacoes.py         categoria, placar, quórum e orientações de cada votação; grava dados/votacoes/<casa>/<id>.json (chamado pelo camara.py e pelo senado.py)
  legislativos.py     roda os coletores das Assembleias (scripts/assembleias/<uf>.py) e das Câmaras Municipais (scripts/camaras/c<IBGE>.py)
  regional.py         ajudas comuns desses coletores (formato dos arquivos, casar cada pessoa com o TSE)
  mandatos.py         datas de posse e qual mandato está em curso em cada data (a regra da "virada" de mandato)
  simplificar.py, montar.py   explicações simples (IA) e a junção final (todo dia)
  historico.py, mapa.py       mandatos anteriores e mapa do Brasil (à mão)
  municipios/mapear.py        mapa das Câmaras Municipais e prefeituras (sites oficiais, sistema de propostas, Diário Oficial, pedido de informação)
.github/workflows/    atualizar.yml (robô diário) e cidades.yml (robô das cidades: o mapa das Câmaras e prefeituras, um grupo de estados por dia)
.vercelignore         o que vai para o repositório mas não para o site (scripts, testes e arquivos de trabalho dos coletores)
testes/               capturas de tela, auditoria de acessibilidade e amostras
```

Para ver no computador: `python -m http.server 8770` dentro da pasta e abra http://127.0.0.1:8770.

## Testes (com o servidor local acima rodando; precisam do Playwright com o Edge e, para acessibilidade, do axe-core em `../ferramentas/node_modules`)

- `python testes/captura.py index.html "pessoa.html?id=pres-lula&lang=en" --mobile --cheia`: capturas de tela em `testes/capturas/`, erros do console e rolagem para os lados.
- `python testes/acessibilidade.py brasil.html "brasil.html?lang=en" [--mobile]` e `--aulas` (todos os slides das 9 paradas, nos 2 idiomas): auditoria axe-core (WCAG 2.2 AA). Meta: 0 problemas.
- `python testes/verifica_texto.py "estado.html?uf=BA&lang=en" ...`: procura "undefined"/"null" e português solto na versão em inglês.
- `python testes/interacao.py`: teclado, busca, listas com busca (estado, cidade, filtros), página da cidade, 4 portas, filtros, mapa e menu de acessibilidade.
- `python testes/interacao_votacoes.py`: votações (lista, uma votação, bloco do Brasil e "Como votou" do perfil): teclado, filtros, "Mostrar mais" com o foco, números que batem com os dados, inglês, 320 px e axe-core depois de rolar e clicar.
- `python testes/interacao_historico.py`: mandatos anteriores (campo pelo teclado, páginas do passado no Brasil, estado e cidade, "Voltar para hoje", cidade que ainda não existia, virada de mandato com o relógio adiantado).
- `python testes/interacao_camaras.py`: Câmaras Municipais das capitais (lista oficial na página da cidade, perfil com propostas e filtros, textos em inglês, cidades só com a lista).
- `python testes/gerar_imagens.py`: gera os ícones e a imagem de compartilhamento (`testes/og.html` → `img/compartilhar.jpg`).
- Observação: as fotos do TSE não carregam no navegador sem janela dos testes (o firewall do TSE barra); num navegador normal, carregam.

## Como os dados são atualizados

`.github/workflows/atualizar.yml` roda todo dia às 6h (Brasília), nesta ordem:
1. `scripts/camara.py` (Câmara), `scripts/senado.py` (Senado), `scripts/executivo.py` (presidente e vice), `scripts/tse.py` (TSE e IBGE: estados, cidades, eleições, bens, busca) e `scripts/legislativos.py` (Assembleias Legislativas e Câmaras Municipais com dados abertos; se o site de uma Casa estiver fora do ar, fica a lista da última rodada que deu certo). O `camara.py` e o `senado.py` também gravam um arquivo por votação em `dados/votacoes/<casa>/` (com `scripts/votacoes.py`; para refazer só as votações a partir do que já foi baixado: `python scripts/votacoes.py --cache` e depois `python scripts/montar.py`);
2. `scripts/simplificar.py`: escreve, com IA, a explicação simples (português e inglês) das propostas que ainda não têm, a partir da ementa oficial (o texto oficial aparece sempre ao lado). Usa o GitHub Models com o token do próprio Actions (grátis, cerca de 2.800 propostas por dia, em no máximo 60 minutos: `MINUTOS`) ou uma chave da OpenAI no segredo `OPENAI_API_KEY` (mais rápido). Ordem: rodízio por pessoa (a cada rodada, cada político ganha a explicação da sua proposta mais nova que ainda falta), para todo mundo avançar no mesmo ritmo, sem prioridade para quem governa. Um programa confere cada explicação antes de publicar (no máximo 35 palavras em português e 45 em inglês, palavras de opinião proibidas, números e trechos entre aspas que precisam existir na ementa); a que for recusada 2 vezes fica só com o texto oficial (`dados/simples-recusadas.json`);
3. `scripts/montar.py`: junta tudo (TSE nos perfis, explicações simples nos perfis e nas votações, textos em inglês da eleição de 2026, listas oficiais das Assembleias e Câmaras nas páginas do estado e da cidade, sitemap);
4. faz commit só do que mudou de verdade (datas de consulta não contam) e a Vercel publica sozinha. Os caches (`.cache/`) são guardados no fim, mesmo se alguma etapa falhar ou o tempo acabar, para o que já foi baixado não se perder.

**Troca de mandato.** Ninguém precisa mexer no código quando um mandato acaba: `scripts/mandatos.py` sabe a data de posse de cada cargo (presidente em 5/1 e governadores em 6/1 a partir de 2027, pela EC 111/2021; Congresso em 1º/2; prefeitos e vereadores em 1º/1) e os coletores perguntam a ele qual mandato está em curso. No dia da posse, presidente, vice, governadores, deputados estaduais e as legislaturas da Câmara e do Senado trocam sozinhos, e os selos "Eleito em 2026" saem. As pesquisas à mão dizem de qual mandato são (`"eleicao": 2022` em `governadores.json`, `"eleicao": 2024` em `prefeitos.json`, `"mandatoInicio"` em `ministros.json`): quando um mandato novo começa, a de governadores deixa de valer (o site mostra quem ganhou, com "aConfirmar") e a de ministros ganha um aviso, até serem refeitas. Para as eleições municipais de 2028, `tse.py` ainda precisa aprender o ano novo (`ORDINARIAS`, `ID_DIVULGA` e a leitura de 2024).

**Depois de um 2º turno.** Os dados abertos de candidaturas do TSE (`consulta_cand`) levam alguns dias para trazer a situação depois do 2º turno (até lá, a linha do 2º turno vem com `#NULO`). Enquanto isso, o `tse.py` (`Base2026._completar_2turno`) lê a totalização final de cada 2º turno de presidente e de governador no sistema de resultados do TSE (`resultados.tse.jus.br/oficial/ele<ano>/<eleição do 2º turno>/dados/<uf>/<uf>-c<cargo>-e<eleição>-u.json`, só quando `"tf": "s"`) e põe esse arquivo como fonte junto com a candidatura. Quando os dados abertos chegam, eles passam a valer sozinhos. Depois do resultado final, rode `python scripts/historico.py` (o mandato seguinte entra no histórico).

O mapa do Brasil da página do estado (`dados/mapa-brasil.json`: o contorno real de cada estado, da malha oficial do IBGE, já desenhado, e o lugar da sigla) é feito por `scripts/mapa.py`. O contorno dos estados quase nunca muda, então ele não roda todo dia: rode à mão se o IBGE mudar a malha.

Os mandatos anteriores (`dados/historico/`) são feitos por `scripts/historico.py`, a partir dos dados abertos do TSE (candidaturas de 1994 a 2026 e o resultado de 1990, para o Senado de 1995 a 1998) e, para os ministros, de `dados/manual/ministros-anteriores.json`. O passado não muda, então ele **não roda todo dia**: rode à mão (`python scripts/historico.py`, uns 40 s com o cache; na primeira vez baixa uns 650 MB para `.cache/tse/`; só os ministros: `python scripts/historico.py --ministros`, sem baixar nada). Rode de novo quando o resultado de uma eleição fechar: o mandato novo entra sozinho no índice e, no dia da posse, o de antes vira passado (até lá, ele não aparece no campo "Ver outro mandato"). Enquanto os dados abertos ainda não trazem o 2º turno, o `historico.py` usa a mesma totalização final do sistema de resultados do TSE que o `tse.py` (`completar_2turno`), com a fonte na ficha de quem venceu. O mandato 2027–2030 entrou em 26/10/2026, depois do 2º turno de 2026.

Correções à mão (sempre com fonte): `dados/manual/governadores.json`, `dados/manual/ministros.json`, `dados/manual/prefeitos.json` (quando quem está no cargo hoje não é quem o TSE mostra: morte, renúncia, cassação) `dados/manual/presidentes.json` (presidente e vice dos mandatos anteriores: só o que o TSE não tem, como o vice de 1994 e 1998 e o 2º turno de 2006, e o que mudou durante um mandato, como em 2016) e `dados/manual/ministros-anteriores.json` (ministros dos governos de 1995 a 2022: transcrito das listas da Biblioteca da Presidência e dos decretos do Diário Oficial, cada pessoa com a sua fonte; para corrigir, mude aqui e rode `python scripts/historico.py --ministros`).

### Câmaras Municipais das capitais

`python scripts/legislativos.py camaras` roda um coletor por Câmara (`scripts/camaras/c<IBGE>.py`). Hoje, 19 das 26 capitais têm a **lista oficial de quem está no cargo** (inclusive suplentes que assumiram), com o partido de hoje, a foto oficial (reduzida para 240 px em `img/pessoas/ver-*.jpg`) e a página oficial de cada pessoa; 8 delas têm também as **propostas desde 1º/1/2025** (projetos de lei, de lei complementar, de emenda à Lei Orgânica, de decreto legislativo e de resolução), com autor ou coautor e a situação de cada uma. Os ids são os mesmos da lista do TSE (`ver-<IBGE>-<SQ_CANDIDATO de 2024>`).

- **SAPL do Interlegis** (Fortaleza, Manaus, Natal, João Pessoa, Porto Velho, Rio Branco e Boa Vista): `scripts/camaras/_sapl.py` lê a API pública (`<endereço>/api/`): legislatura atual, mandatos e o campo "ativo", autoria (com o primeiro autor), a última tramitação de cada proposta e a norma ligada a ela ("virou lei"). Uma cidade nova com SAPL é um arquivo de 8 linhas. O estado fica em `.cache/camaras/<IBGE>/`: a primeira execução baixa o histórico das tramitações; as seguintes, só o que mudou. O coletor confere se o número de vereadores ativos bate com o de vagas; se não bater, a cidade é conferida à mão (`excluir`/`incluir`, sempre com a fonte anotada no arquivo da cidade).
- **São Paulo**: web service de dados abertos SPLegis. Ele não diz quem assinou primeiro um projeto de vários autores; nesse caso, todos aparecem como "assinou junto" (a página avisa).
- **Só a lista oficial** (uma página do portal de cada Câmara por dia): Rio de Janeiro, Belo Horizonte, Salvador, Curitiba, Porto Alegre, Belém, Goiânia, São Luís, Vitória, Teresina e Cuiabá (as três últimas usam o sistema da Ágape, `scripts/camaras/_agape.py`). As propostas dessas Câmaras só existem em páginas HTML, sem dados abertos.
- **Sem coletor** (continuam com a lista de eleitos do TSE): Recife (a API do SAGL não diz quais titulares estão licenciados), Maceió (a página mistura licenciados e não mostra os suplentes), Campo Grande e Florianópolis (os sites pedem "não sou robô"), Macapá (aplicativo sem API pública), Aracaju (sistema fora do ar) e Palmas (sistema parado em 2024).
- **Situação das propostas numa Câmara de uma casa só**: o "aprovado" da votação final vai para a sanção do prefeito (`aprovada`); sancionado, promulgado ou com norma ligada = `lei`; "veto rejeitado" quer dizer que a Câmara derrubou o veto; aprovação em 1º turno e pareceres = `andando`. As regras estão em `scripts/camaras/_base.py` (`REGRAS`).
- **Votações nominais e gastos** das Câmaras ainda não entram: o SAPL das capitais quase não tem votos nominais; São Paulo publica as votações em XML e os gastos no SisGV (próximo passo).
- `scripts/descobrir_sapl.py` (não roda todo dia) testa `sapl.<cidade>.<uf>.leg.br` nas 5.569 cidades: em 23/10/2026, 824 Câmaras tinham a API funcionando, a legislatura atual cadastrada e projetos desde 2025.

### Mapa das Câmaras Municipais e prefeituras (`dados/municipios/<UF>.json`)

`python scripts/municipios/mapear.py [UF ...]` confere, nas 5.569 cidades, o site oficial da Câmara Municipal e da prefeitura, o sistema de proposições da Câmara e se as proposições estão na internet (quando não estão, por quê), a página de pedido de informação (e-SIC), o portal da transparência e o Diário Oficial da prefeitura. É o que o quadro **"Onde ver mais"** dos perfis de vereadores e prefeitos mostra (o `montar.py` leva cada cidade para o campo `onde` de `dados/cidades/<UF>/<IBGE>.json`). As pistas vêm de listas oficiais — a do Interlegis (domínio .leg.br, SAPL e Portal Modelo de cada Câmara), a descoberta do SAPL (`scripts/descobrir_sapl.py`), as listas de municípios dos Diários Oficiais das associações de municípios (SIGPub, em www.diariomunicipal.com.br, e Assomasul) e a do Ciga (SC) —, mas tudo é conferido no próprio site oficial (título, nome do site, texto). Só entram sites .leg.br e .gov.br; o Diário Oficial pode estar na plataforma que o site da prefeitura indica (ou na da associação em que a cidade publicou nos últimos 6 meses).

- **No robô:** `.github/workflows/cidades.yml` roda `mapear.py --rodizio` todo dia (um grupo de estados por dia: cada estado é conferido uma vez por semana) e junta tudo com o `montar.py`.
- **Educado:** respeita o robots.txt de cada site (e o `Crawl-delay`; o do SAPL pede 60 s); 1 s entre pedidos ao mesmo site; poucos pedidos ao mesmo tempo para o mesmo servidor; até 16 cidades em paralelo (sites diferentes); um servidor que para de responder é deixado em paz pelo resto da rodada. O que foi visto fica em `.cache/municipios/`; cada cidade só é refeita depois de 6 dias e, se um site não abrir, vale o que foi conferido até 45 dias antes. O robô do GitHub roda fora do Brasil, e muitos sites de prefeituras e Câmaras bloqueiam esse acesso: por isso, um bloco já publicado (Câmara ou prefeitura) só é trocado quando a rodada nova acha pelo menos o mesmo tanto de informação, quando o site muda de endereço (e o novo é lido) ou quando o endereço publicado deixa de existir; senão fica o bloco publicado, com a data em que foi conferido, por até 90 dias (`manter_publicado`). Em 26/10/2026, uma rodada no robô achou bem menos que a rodada feita no Brasil (350 prefeituras de MG sem leitura, contra 220): de vez em quando, vale rodar o mapa num computador no Brasil (`python scripts/municipios/mapear.py`).
- **Formato:** `{uf, atualizado, fontes, nota, cidades: {<IBGE>: {camara: {site, sistema, api, propostas, propostasOnline, sic, conferido, motivo, motivo_en, plataforma?}, prefeitura: {site, transparencia, sic, diarioOficial: {nome, url, plataforma, entidade?, confirmado?}, conferido, lido?}}}}`. `sistema`: `sapl`, `sagl`, `nopaper` (SPL da Ágape, "Câmara sem Papel"), `outro` ou `null`. `propostasOnline`: `true` (conferido que estão na internet), `false` (conferido que não estão onde deviam) ou `null` (não deu para conferir); `motivo`/`motivo_en` dizem por quê, em frases curtas que qualquer pessoa confere abrindo o site. `propostas` é a página pública das proposições (no SAPL, a busca de matérias).
- **Conferir:** `python scripts/municipios/resumo.py` (tabela por estado e plataformas de Diário Oficial) e `python scripts/municipios/resumo.py --conferir` (formato); `python scripts/municipios/mapear.py --ibge <código>` mostra o que foi achado numa cidade.
- **Limites:** domínios fora do padrão (abreviações, .com.br) ficam sem site ("Não achamos..."); sites que pedem no robots.txt para não serem lidos, ou que só funcionam com JavaScript, ficam com o endereço e o motivo; o DOM/SC fecha para robôs (em SC, sem link no site da prefeitura, a ligação ao DOM/SC vem da adesão ao Ciga: `"confirmado": false`).
- Os canais de pedido de informação conferidos à mão (`dados/manual/canais-lai.json`) completam o mapa nas capitais em que ele não achou.

### Assembleias Legislativas (e a Câmara Legislativa do DF)

`python scripts/legislativos.py assembleias` (ou só alguns estados: `python scripts/legislativos.py BA SP GO`) roda um coletor por Casa (`scripts/assembleias/<uf>.py`; ajudas em `_ne_comum.py`, `_ne_sapl.py` e `_ne_nopaper.py` no Nordeste, `_sse_comum.py` no Sudeste, Sul e DF, `_nco_comum.py` e `_nco_sapl.py` no Norte e Centro-Oeste). Cada um lê só o site oficial da Casa, um pedido por vez, com pausa, e guarda o que leu em `.cache/<casa>/`. Hoje, **26 das 27 Casas** têm a **lista oficial de quem está no cargo** (1.035 deputados, inclusive suplentes que assumiram: "Suplente em exercício"), com o partido de hoje, a foto e a página oficial; cada pessoa é ligada ao candidato do TSE da eleição da legislatura (`dest-<UF>-<SQ_CANDIDATO>`; conferências à mão no próprio coletor). **21** têm as **propostas desde a posse** (59.148: projetos de lei, de lei complementar, de emenda à Constituição — no DF, à Lei Orgânica —, de decreto legislativo e de resolução), com autor principal ou coautor e a situação (regras de cada Casa, conferidas à mão numa amostra, antes da tabela comum). **4** têm **votações nominais** (catálogos `dados/votacoes/<aleam|alero|alego|alepa>.json`, no mesmo formato do Congresso) e **5** têm **gastos** (verba indenizatória ou cota; o perfil diz o nome de cada uma).

| UF | Casa | No cargo (suplentes marcados) | Propostas | Votações nominais | Gastos |
|---|---|---|---|---|---|
| AC | Aleac | 24 (0) | 868 | — | — |
| AL | ALE-AL | 27 (0) | 2.136 | — | — |
| AM | Aleam | 24 (1) | 3.966 | 3.140 | — |
| AP | Alap | — (o site não respondeu: fica a lista do TSE) | — | — | — |
| BA | Alba | 63 (0) | 1.359 | — | — |
| CE | Alece | 46 (0) | 3.103 | — | — |
| DF | CLDF | 24 (0) | 2.757 | — | — |
| ES | Ales | 30 (2) | 2.770 | — | — |
| GO | Alego | 41 (2) | — (o sistema proíbe robôs) | 2.080 | verba indenizatória |
| MA | Alema | 42 (0) | 2.389 | — | — |
| MG | ALMG | 77 (5) | 5.559 | — | verba indenizatória |
| MS | Alems | 24 (1) | — (desafio anti-robô) | — | CEAP |
| MT | ALMT | 24 (1) | — (a API exige cadastro) | — | — |
| PA | Alepa | 41 (2) | — (busca sem paginação aberta) | 151 | — |
| PB | ALPB | 36 (3) | 7.862 | — | — |
| PE | Alepe | 49 (0) | 3.912 | — | — |
| PI | Alepi | 30 (3) | 1.509 | — | — |
| PR | Alep | 54 (3) | 3.260 | — | — |
| RJ | Alerj | 70 (9) | — (o sistema só mostra as 15 mais recentes) | — | — (não existe verba indenizatória no RJ) |
| RN | ALRN | 24 (0) | 2.240 | — | — |
| RO | Ale-RO | 24 (1) | 2.439 | 367 | — |
| RR | ALE-RR | 24 (1) | 1.296 | — | — |
| RS | ALRS | 55 (1) | 1.590 | — | — |
| SC | Alesc | 40 (4) | 2.038 | — | despesas dos gabinetes |
| SE | Alese | 24 (0) | 1.510 | — | — |
| SP | Alesp | 94 (5) | 4.824 | — | despesas de gabinete |
| TO | Aleto | 24 (1) | 1.761 | — | — |

(Números de 23/10/2026. "Suplentes marcados" = onde a lista oficial diz que a pessoa é suplente; nas outras, o perfil mostra "Como chegou ao cargo".) O que falta em cada Casa, e por quê, está nas `notas` de `dados/assembleias/<UF>.json`, que a página do estado mostra no quadro "O que o site já tem da Assembleia".

- **Tempo por dia, com o cache cheio:** ~25 min para as 26 (os coletores lentos param num limite de tempo e completam aos poucos nos dias seguintes; enquanto isso fica o dado da rodada anterior). A **primeira rodada sem cache** é longa (PE ~70 min, ALMG ~70 min de verba, Alesc ~1 h, AM ~25 min). Para encher de uma vez: `NE_SEM_LIMITE=1`, `ALMG_VERBAS_MAX`, `CLDF_NORMAS_MAX`, `ALEP_NORMAS_MAX`, `ALESC_FICHAS`, `ALESC_PAGINAS` e `ALES_SEGUNDOS` (o que cada uma faz está no topo do coletor).
- **Posse da legislatura eleita em 2026** (conferida nas Constituições e na Lei Orgânica do DF; fica em `scripts/mandatos.py`, `POSSE_ESTADUAL`): 1º de fevereiro de 2027 em 24 estados; **31 de janeiro no RS**, **6 de janeiro no DF** (Emenda à Lei Orgânica 131/2024) e **1º de janeiro em RR** (Constituição de RR, art. 30, § 4º). Em 2023 foi diferente em SP (15 de março) e no DF (1º de janeiro): `POSSE_ESTADUAL_ATE_2022`.
- **Troca de legislatura:** o começo das propostas (`regional.inicio_estadual(uf)`), os textos e a eleição do TSE usada nos ids (2026) trocam sozinhos na posse. A lista de quem está no cargo troca quando a Casa atualiza a dela; até lá, alguns coletores falham de propósito (para não mostrar a lista velha como se fosse a de hoje), e o `montar.py` não usa uma lista de uma legislatura que já acabou (`_lista_velha`): fica a lista do TSE, que já é a dos eleitos. Depois da posse, os ids dos deputados estaduais passam a usar o número do TSE de 2026 (o link antigo de um reeleito deixa de abrir o perfil).
- **Testes:** `python testes/interacao_ale_sse.py` (Sudeste, Sul e DF) e `python testes/interacao_assembleias_nco.py` (Norte e Centro-Oeste).

#### O que cada governador fez (`dados/pessoas/gov-<UF>.json`)

O perfil do governador mostra o que o governo do estado fez desde a posse de quem governa hoje (1º/1/2023, ou o `desde` da ficha, para quem assumiu depois): os **projetos que o Poder Executivo mandou à Assembleia** (com a situação, como as propostas dos deputados) e as **leis sancionadas e os vetos** do período (bloco `executivo`, com a `nota` "Como contamos"). A régua é a mesma do perfil do presidente: conta tudo o que o governo assinou no período, inclusive quando outra pessoa estava no exercício do cargo (vice, presidente da Assembleia); ficam fora as leis promulgadas pela própria Assembleia (quando ela derruba um veto), se a fonte as separar. Cada coletor de Assembleia grava o arquivo do governador no fim da rodada (roda todo dia junto); se a parte do governo falhar, fica o arquivo de antes, a não ser que seja de outro governo (aí é apagado, para não mostrar o que outra pessoa fez).

| UF | Projetos do Executivo | Leis | Vetos |
|---|---|---|---|
| AM, RO, RR | SAPL (autor "Poder Executivo"; em RR, o próprio governador) | normas do SAPL | matérias de veto do SAPL |
| AC | SAPL | — (a Aleac não cadastra as leis) | SAPL |
| TO | SAPL (inclui medidas provisórias) | página "Legislação Estadual" da Aleto (o começo de cada lei diz quem assinou) | SAPL |
| PA | — | Banco de Leis da Alepa (a partir da 1ª lei do governo, conferida à mão: `PRIMEIRAS` em `pa.py`) | — |
| GO | — | dados abertos da Casa Civil (arquivo mensal) | — |
| MS | — | banco Legislação Estadual do governo | — |
| MT | — | — (o perfil leva ao Diário Oficial) | — |
| AP | — | — (o perfil leva ao Diário Oficial: `dados/manual/diarios-oficiais.json`) | — |

O que não entra fica explicado nas `notas` da Casa e na `nota` do bloco `executivo`; o perfil mostra, no lugar, o quadro "Onde ver mais". **Na troca de governo** (posse de 6/1/2027): o PA precisa de uma linha nova em `PRIMEIRAS` (`scripts/assembleias/pa.py`) com a primeira lei do novo governo, conferida no PDF; RR e TO acham o governador no SAPL pelo nome civil da ficha.

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
| `gov-<UF>` / `vgov-<UF>` | governador(a) / vice em exercício | `gov-BA` |
| `dest-<UF>-<SQ_CANDIDATO TSE>` | deputado(a) estadual ou distrital | `dest-BA-50001603470` |
| `pref-<IBGE>` / `vpref-<IBGE>` | prefeito(a) / vice | `pref-2927408` |
| `ver-<IBGE>-<SQ_CANDIDATO TSE>` | vereador(a) | `ver-2927408-50002...` |

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
- `dados/busca.json`: `[[id, nome, cargo curto, UF, partido, cidade ou null], ...]` (sem vereadores; eles aparecem na página da cidade).
- `dados/simples/<00-99>.json`: cache das explicações simples: `{ "camara:2345678": { "pt": "Explicação simples", "en": "Simple explanation" }, ... }` (arquivo = 2 últimos dígitos do número). Escritas por `scripts/simplificar.py` só a partir da ementa oficial: no máximo 35 palavras, começando por um verbo (cria, muda, proíbe...), sem palavras de opinião. Quem quiser corrigir uma explicação edita o cache e roda `scripts/montar.py`.
- `dados/tse/federais.json`: o que o TSE diz de cada pessoa do Congresso e do Executivo (eleição de 2022, bens declarados, resultado de 2026), juntado aos perfis por `scripts/montar.py`.

`eleicao2026.situacao`: `eleito` | `reeleito` | `segundo-turno` | `nao-eleito` | `suplente` | `candidato` | `nao-concorreu` | `null` (não sabemos). `eleicao2026.txt` e `txt_en`: a frase pronta para mostrar.

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

Tipos de slide: `abertura`, `explica`, `cards` (cartões que viram), `passos` (escada 3D), `comparar` (portas que abrem), `numeros` (blocos que caem), `historia` (quadrinhos que folheiam), `quiz` (peças 3D), `simulador` (`quem-cuida`, `quociente`, `caminho-lei`). Os campos de cada tipo e as ilustrações disponíveis estão descritos no começo de `js/entenda.js`. Qualquer slide pode ter um botão para outra página do próprio site: `"link": { "url": "brasil.html#os-ministros", "ic": "👔", "txt": "Ver os ministérios de hoje" }` (só aceita páginas do site; no inglês, o link já leva `?lang=en`). Para testar uma parte nova sem mexer nas outras: `entenda.html?teste=1` carrega `testes/parte-teste.json` como parte 1.

## Publicar

Repositório **público** no GitHub ([lucastaonline/entendapolitica](https://github.com/lucastaonline/entendapolitica)): o código aberto ajuda a mostrar a imparcialidade, e repositório público tem minutos ilimitados no GitHub Actions para a atualização diária. Site na Vercel (projeto `entendapolitica`, Framework Preset: **Other**, sem comando de build, pasta raiz `./`): cada commit na `main` (inclusive os do workflow diário) é publicado sozinho. Commits com o e-mail noreply do GitHub (senão a Vercel bloqueia o deploy). O workflow junta as mudanças com a `main` antes de enviar (`git pull --rebase`), então dá para publicar uma correção enquanto ele roda. **Nada é publicado sem o dono pedir.**

Antes de publicar algo novo: nenhum segredo no código (chaves ficam nos segredos do GitHub, como `OPENAI_API_KEY`) e nenhum dado pessoal desnecessário (o `montar.py` tira números de CPF que aparecem em textos oficiais, com `comum.sem_documentos`).
