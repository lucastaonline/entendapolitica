# Entenda Política

Site estático (HTML, CSS e JS puros, sem build no navegador) que explica como a política brasileira funciona, de um jeito que **uma criança de 10 anos entenda**, e mostra **quem está no mandato hoje**, com tudo o que cada pessoa propôs, o que foi aprovado e o que virou lei. **Tudo com fonte. Tudo imparcial.**

Mesma identidade visual do [Entenda o 2º turno](https://entendaosegundoturno.vercel.app): fundo creme, azul `#1f3a5f`, amarelo `#f2b705`, letra do sistema bem grossa, emojis, botões "gordinhos" e peças 3D feitas só com CSS.

## As 4 portas da página inicial

1. **Entenda a política** (`entenda.html`): um **mapa 3D** (tabuleiro) com 9 paradas: o que é política (escola), os Três Poderes, país/estado/cidade, os cargos (torre), o Congresso (no centro), como nasce uma lei, eleições (urna), quem julga e fiscaliza (tribunal) e como participar (palanque). Uma trilha amarela sugere a ordem, mas dá para clicar em qualquer lugar. Ao clicar, a câmera "mergulha" no lugar e abre a **aula daquela parada**: uma apresentação com muito 3D (escadas para processos, cartões que viram, quadrinhos que folheiam, quiz e simuladores). No fim: estrela no mapa e "próxima parada". O progresso fica salvo no aparelho.
2. **A política do Brasil** (`brasil.html`): presidente, vice, ministros, os 81 senadores e os 513 deputados federais, com busca por qualquer político.
3. **A política do meu estado** (`estado.html`): governador e vice, os senadores e deputados federais do estado e os deputados estaduais. No fim, um campo leva para a página da cidade.
4. **A política da minha cidade** (`cidade.html`): a pessoa digita o nome da cidade (as 5.569 do Brasil, com o estado ao lado para desempatar) e vê prefeito, vice e vereadores, além do que cada um faz. Brasília e Fernando de Noronha têm explicação própria (não têm prefeitura comum). Endereço: `cidade.html?ibge=<código IBGE>`; os endereços antigos `estado.html?uf=XX&cidade=<IBGE>` levam para lá.

Cada pessoa tem uma página (`pessoa.html?id=...`) com ficha, propostas (com explicação simples + texto oficial + link da fonte), situação de cada proposta, votações, gastos e eleições. O botão **Voltar** leva para a página de onde a pessoa veio (o Brasil, o estado, a cidade ou a busca), guardada nesta aba pelo `js/comum.js` (`EP.gravaVolta`/`EP.leVolta`); se ela veio direto de lá, usa o histórico do navegador, e a lista reaparece como estava. Aberto por link direto, vai para a lista do cargo.

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

1. **Fase 1:** federal completo (presidente, vice, ministros, senadores, deputados federais) + ficha básica (TSE) de governadores, deputados estaduais, prefeitos e vereadores.
2. **Fase 2:** propostas dos deputados estaduais, Assembleia por Assembleia.
3. **Fase 3:** vereadores das capitais e das Câmaras com dados abertos (ex.: SAPL/Interlegis).

Mandatos: o site mostra **quem está no cargo hoje** e marca quem foi **eleito/reeleito em 2026**. Quando os novos tomarem posse (jan./fev. de 2027), as listas trocam.

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
estado.html           política do meu estado (lê dados/estados/UF.json e dados/cidades/UF.json)
cidade.html           política da minha cidade (lê dados/cidades.json e dados/cidades/UF/IBGE.json)
pessoa.html           perfil de uma pessoa (lê dados/pessoas/<id>.json e dados/votacoes/<casa>.json)
imparcialidade.html   como cuidamos da imparcialidade
dados.html            de onde vêm os dados, com que frequência são atualizados e os limites
css/base.css          visual comum (cores, botões, cartões, janela) + acessibilidade (contraste, movimento, espaçamento)
css/tres.css          peças 3D que vieram do site do 2º turno (urna, cubos, formas)
css/tres-politica.css peças 3D novas (Congresso, Três Poderes, níveis, escola, torre, tribunal, palanque, escada...)
css/mapa.css          o mundo 3D do mapa (chão, lotes, placas, câmera)
css/entenda.css       as aulas (slides em 3D)
js/comum.js           idioma, acessibilidade, janela, fontes, ouvir, Libras, formatação, listas com busca (EP.combo), compartilhar
js/casa.js            monta uma Casa (Senado, Câmara, Assembleia, Câmara Municipal): plenário 3D com fatias e siglas por partido, filtros e lista de cartões
js/brasil.js, js/estado.js, js/cidade.js, js/pessoa.js   as páginas do Brasil, do estado, da cidade e de cada pessoa
js/tres.js, js/tres-politica.js   montam as peças 3D (cada modelo tem modo "cena" e modo "mundo")
js/mapa3d.js          monta o mapa 3D, câmera (voar até um lugar), girar, zoom, lista acessível
js/entenda.js         carrega o conteúdo, liga o mapa e as aulas (especificação dos slides no topo do arquivo)
conteudo/entenda/     texto das 9 paradas em português; conteudo/entenda/en/ em inglês
dados/                tudo o que os scripts geram (JSON); não edite à mão, exceto dados/manual/
scripts/              coletores em Python (só biblioteca padrão + Pillow)
.github/workflows/    atualização automática diária
testes/               capturas de tela, auditoria de acessibilidade e amostras
```

Para ver no computador: `python -m http.server 8770` dentro da pasta e abra http://127.0.0.1:8770.

## Testes (com o servidor local acima rodando; precisam do Playwright com o Edge e, para acessibilidade, do axe-core em `../ferramentas/node_modules`)

- `python testes/captura.py index.html "pessoa.html?id=pres-lula&lang=en" --mobile --cheia`: capturas de tela em `testes/capturas/`, erros do console e rolagem para os lados.
- `python testes/acessibilidade.py brasil.html "brasil.html?lang=en" [--mobile]` e `--aulas` (todos os slides das 9 paradas, nos 2 idiomas): auditoria axe-core (WCAG 2.2 AA). Meta: 0 problemas.
- `python testes/verifica_texto.py "estado.html?uf=BA&lang=en" ...`: procura "undefined"/"null" e português solto na versão em inglês.
- `python testes/interacao.py`: teclado, busca, listas com busca (estado, cidade, filtros), página da cidade, 4 portas, filtros, mapa e menu de acessibilidade.
- `python testes/gerar_imagens.py`: gera os ícones e a imagem de compartilhamento (`testes/og.html` → `img/compartilhar.jpg`).
- Observação: as fotos do TSE não carregam no navegador sem janela dos testes (o firewall do TSE barra); num navegador normal, carregam.

## Como os dados são atualizados

`.github/workflows/atualizar.yml` roda todo dia às 6h (Brasília), nesta ordem:
1. `scripts/camara.py` (Câmara), `scripts/senado.py` (Senado), `scripts/executivo.py` (presidente e vice), `scripts/tse.py` (TSE e IBGE: estados, cidades, eleições, bens, busca);
2. `scripts/simplificar.py`: escreve, com IA, a explicação simples (português e inglês) das propostas que ainda não têm, a partir da ementa oficial (o texto oficial aparece sempre ao lado). Usa o GitHub Models com o token do próprio Actions (grátis, cerca de 2.800 propostas por dia) ou uma chave da OpenAI no segredo `OPENAI_API_KEY` (mais rápido). Ordem: rodízio por pessoa (a cada rodada, cada político ganha a explicação da sua proposta mais nova que ainda falta), para todo mundo avançar no mesmo ritmo, sem prioridade para quem governa. Um programa confere cada explicação antes de publicar (no máximo 35 palavras em português e 45 em inglês, palavras de opinião proibidas, números e trechos entre aspas que precisam existir na ementa); a que for recusada 2 vezes fica só com o texto oficial (`dados/simples-recusadas.json`);
3. `scripts/montar.py`: junta tudo (TSE nos perfis, explicações simples, textos em inglês da eleição de 2026);
4. faz commit só do que mudou de verdade (datas de consulta não contam) e a Vercel publica sozinha.

Correções à mão (sempre com fonte): `dados/manual/governadores.json`, `dados/manual/ministros.json`, `dados/manual/prefeitos.json` (quando quem está no cargo hoje não é quem o TSE mostra: morte, renúncia, cassação).

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
  "gastos": { "ano": 2025, "total": 412345.67, "porTipo": [ { "tipo": "Passagens aéreas", "valor": 123.4 } ], "mandatoTotal": 1234567.89, "fonte": {} },
  "votacoes": {
    "escopo": "Votações com voto de cada um (nominais) no Plenário da Câmara desde fevereiro de 2023",
    "resumo": { "total": 300, "Sim": 150, "Não": 120, "Abstenção": 5, "Obstrução": 20, "Outro": 5 },
    "fonte": {},
    "arquivo": "dados/votacoes/camara.json",   // onde estão os detalhes de cada votação (compartilhados por todos)
    "votos": [ ["2345678-123", "Sim"], ["2345678-120", "Não"] ]   // [chave no arquivo, voto], da mais nova para a mais antiga
  },
  "fontes": [],
  "atualizado": "2026-10-15"
}
```

Campos sem informação: `null` (nunca invente). A lista de propostas vem **da mais nova para a mais antiga**.

**Votações (`dados/votacoes/camara.json` e `dados/votacoes/senado.json`).** O que foi votado é igual para todos os 513 (ou 81), então fica num arquivo só e o perfil guarda apenas a chave e o voto da pessoa:

```jsonc
{
  "votacoes": {
    "2345678-123": { "data": "2024-05-02", "propostaId": "camara:2345678", "proposta": "PL 1234/2023",
                     "descricao": "Descrição oficial do que foi votado", "resultado": "Aprovado", "url": "https://..." }
  },
  "legenda": { "NCom": "Não Compareceu" },   // só no Senado: o que quer dizer cada código de voto
  "fonte": {}, "atualizado": "2026-10-15"
}
```

Chaves: Câmara = id da votação na Câmara (`2345678-123`); Senado = `senado-vot:<código>`. Votações secretas do Senado (escolha de autoridades) não entram, porque o voto de cada um não é divulgado.

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
- `dados/cidades/<UF>.json`: lista para escolher a cidade: `[ {"ibge","nome","prefeito":"Nome (PARTIDO)"} ]`.
- `dados/cidades/<UF>/<IBGE>.json`: `{ "ibge","nome","uf","prefeito":{...},"vice":{...},"vereadores":{"total","aviso","fonte","membros":[...]},"atualizado" }`.
- `dados/busca.json`: `[[id, nome, cargo curto, UF, partido, cidade ou null], ...]` (sem vereadores; eles aparecem na página da cidade).
- `dados/simples/<00-99>.json`: cache das explicações simples: `{ "camara:2345678": { "pt": "Explicação simples", "en": "Simple explanation" }, ... }` (arquivo = 2 últimos dígitos do número). Escritas por `scripts/simplificar.py` só a partir da ementa oficial: no máximo 35 palavras, começando por um verbo (cria, muda, proíbe...), sem palavras de opinião. Quem quiser corrigir uma explicação edita o cache e roda `scripts/montar.py`.
- `dados/tse/federais.json`: o que o TSE diz de cada pessoa do Congresso e do Executivo (eleição de 2022, bens declarados, resultado de 2026), juntado aos perfis por `scripts/montar.py`.

`eleicao2026.situacao`: `eleito` | `reeleito` | `segundo-turno` | `nao-eleito` | `suplente` | `candidato` | `nao-concorreu` | `null` (não sabemos). `eleicao2026.txt` e `txt_en`: a frase pronta para mostrar.

Campos extras de quem vem do TSE (estados e cidades): `aConfirmar` (o TSE ainda não fechou o resultado), `sq2022`, `eleito2022`/`eleito2024`, `vago` (com `txt`/`txt_en`), `votosDaChapa`, `desde` e `comoAssumiu`/`comoAssumiu_en` (quando quem está no cargo não é quem foi eleito, ex.: vice que assumiu), `nota`/`nota_en` (observação da pesquisa à mão), `casa`, `aviso`/`aviso_en` e `fonteMunicipios`.

**Gastos (Câmara):** valores líquidos da cota parlamentar, iguais aos da página oficial de cada deputado, incluindo o que a página oficial mostra (passagens compradas pelo sistema da Câmara, o SIGEPA, e a complementação do auxílio-moradia). Não entram o salário nem a verba de gabinete (salários de assessores); por isso o site diz "gastos da cota" e não "tudo o que custou".

**Mesma régua nos perfis federais (`scripts/montar.py`):** ocupação e escolaridade vêm, para todo mundo, da candidatura mais recente no TSE (`ocupacao`, `escolaridade`, `escolaridadeFonte`); as Casas e o Planalto descrevem isso de jeitos diferentes, ou não descrevem. "Mandatos anteriores" mostra só mandatos no mesmo cargo/Casa (deputado: Câmara; senador: Senado; presidente: Presidência), também para todo mundo.

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

Repositório privado no GitHub + Vercel (Framework Preset: Other). Commits com o e-mail noreply do GitHub (senão a Vercel bloqueia o deploy). **Nada é publicado sem o dono pedir.**
