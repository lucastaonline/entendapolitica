# Entenda Política

Site estático (HTML, CSS e JS puros, sem build no navegador) que explica como a política brasileira funciona, de um jeito que **uma criança de 10 anos entenda**, e mostra **quem está no mandato hoje**, com tudo o que cada pessoa propôs, o que foi aprovado e o que virou lei. **Tudo com fonte. Tudo imparcial.**

Mesma identidade visual do [Entenda o 2º turno](https://entendaosegundoturno.vercel.app): fundo creme, azul `#1f3a5f`, amarelo `#f2b705`, letra do sistema bem grossa, emojis, botões "gordinhos" e peças 3D feitas só com CSS.

## As 3 portas da página inicial

1. **Entenda a política** (`entenda.html`): apresentação em slides, parte por parte: o que é política, os Três Poderes, país/estado/cidade, cada cargo, o Congresso, como nasce uma lei, eleições, quem julga e fiscaliza, como participar.
2. **A política do Brasil** (`brasil.html`): presidente, vice, ministros, os 81 senadores e os 513 deputados federais, com busca por qualquer político.
3. **A política do meu estado** (`estado.html`): governador e vice, os senadores e deputados federais do estado, os deputados estaduais e, escolhendo a cidade, prefeito, vice e vereadores.

Cada pessoa tem uma página (`pessoa.html?id=...`) com ficha, propostas (com explicação simples + texto oficial + link da fonte), situação de cada proposta, gastos e eleições.

## Fases combinadas

1. **Fase 1:** federal completo (presidente, vice, ministros, senadores, deputados federais) + ficha básica (TSE) de governadores, deputados estaduais, prefeitos e vereadores.
2. **Fase 2:** propostas dos deputados estaduais, Assembleia por Assembleia.
3. **Fase 3:** vereadores das capitais e das Câmaras com dados abertos (ex.: SAPL/Interlegis).

Mandatos: o site mostra **quem está no cargo hoje** e marca quem foi **eleito/reeleito em 2026**. Quando os novos tomarem posse (jan./fev. de 2027), as listas trocam.

## Regras de imparcialidade (valem para tudo)

1. **Mesma régua para todos.** Os mesmos campos, calculados do mesmo jeito, para todo mundo.
2. **Fonte em tudo.** Todo bloco de informação tem `fonte` (órgão oficial: Câmara, Senado, TSE, IBGE, Planalto, Diário Oficial; ou imprensa quando não houver fonte oficial).
3. **Ordem neutra.** Listas em ordem alfabética. Nada de ranking de "melhor" ou "pior".
4. **Sem cores de partido.** Partidos aparecem com a mesma cor neutra.
5. **Linguagem neutra.** Sem adjetivos de valor ("bom", "ruim", "polêmico", "importante"). Explicações simples dizem **o que a proposta faz**, nunca se é boa.
6. **Quem fez de verdade.** Separar **autor(a) principal** de **coautor(a)** (quem só assinou junto).
7. **Contexto nos números.** Ex.: "propor muitos projetos não quer dizer trabalhar mais ou melhor".
8. **Canal para corrigir.** Formulário "Viu algo errado ou que parece puxar para um lado?".

## Estrutura

```
index.html            página inicial (3 portas)
entenda.html          slides "Entenda a política" (lê conteudo/entenda/parte-N.json)
brasil.html           política do Brasil (lê dados/executivo.json, dados/senado.json, dados/camara.json)
estado.html           política do meu estado (lê dados/estados/UF.json e dados/cidades/...)
pessoa.html           perfil de uma pessoa (lê dados/pessoas/<id>.json)
imparcialidade.html   como cuidamos da imparcialidade
dados.html            de onde vêm os dados, com que frequência são atualizados e os limites
css/base.css          visual comum (cores, botões, cartões, janela)
css/tres.css          peças 3D (vieram do site do 2º turno) + novas
js/tres.js            monta as peças 3D
js/comum.js           barra do topo (Início, Ouvir, A+), janela, fontes, glossário, animação ao rolar
conteudo/entenda/     texto dos slides, uma parte por arquivo (JSON)
dados/                tudo o que os scripts geram (JSON); não edite à mão, exceto dados/manual/
scripts/              coletores em Python (só biblioteca padrão + Pillow)
.github/workflows/    atualização automática
testes/               testes com Playwright
```

Para ver no computador: `python -m http.server 8765` dentro da pasta e abra http://127.0.0.1:8765.

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
  "escolaridade": "Superior completo",
  "profissoes": ["Advogada"],
  "mandato": { "inicio": "2023-02-01", "fim": "2027-01-31", "situacao": "Em exercício", "obs": null, "fonte": {} },
  "mandatosAnteriores": [ { "cargo": "Deputada federal", "inicio": "2019-02-01", "fim": "2023-01-31" } ],
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
    "fonte": {},
    "lista": [
      {
        "id": "camara:2345678",
        "sigla": "PL 1234/2023",
        "tipo": "PL",
        "data": "2023-03-01",
        "ementa": "Texto oficial (ementa)",
        "s": null,                      // explicação simples (preenchida por scripts/simplificar.py)
        "status": "lei",                // lei | aprovada | andando | junta | arquivada | rejeitada | retirada | outra
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
    "lista": [
      { "id": "camara-vot:2345678-123", "data": "2024-05-02", "propostaId": "camara:2345678", "proposta": "PL 1234/2023",
        "descricao": "Descrição oficial do que foi votado", "voto": "Sim", "resultado": "Aprovado", "url": "https://..." }
    ]
  },
  "fontes": [],
  "atualizado": "2026-10-15"
}
```

Campos sem informação: `null` (nunca invente). A lista de propostas vem **da mais nova para a mais antiga**.

**Situação das propostas (`status`)**, igual para Câmara, Senado e Assembleias:

| status | Quer dizer | Exemplo de `situacao` oficial |
|---|---|---|
| `lei` | virou lei (ou norma: decreto legislativo, resolução, emenda à Constituição) | Transformado em Norma Jurídica |
| `aprovada` | aprovada numa Casa e enviada à outra, ou esperando a sanção do presidente | Aguardando Apreciação pelo Senado Federal |
| `andando` | ainda em discussão | Aguardando Parecer, Pronta para Pauta |
| `junta` | está andando junto com outra proposta parecida (apensada) | Tramitando em Conjunto |
| `arquivada` | foi para o arquivo | Arquivada |
| `rejeitada` | votaram contra, foi vetada por inteiro ou ficou prejudicada | Rejeitada, Vetado totalmente |
| `retirada` | o próprio autor desistiu | Retirado pelo(a) Autor(a) |
| `outra` | não deu para classificar com segurança | |

**Tipos que contam como "proposta"** (vão para `lista`): PL, PLP, PEC, PDL, PRC, MPV, PLV, PLN e equivalentes antigos/do Senado (PDC, PLS, PLC, PDS, PRS, PEC do Senado). O resto (requerimentos, indicações, emendas, pareceres) entra só como contagem em `outros`.

### Listas gerais

- `dados/camara.json`: `{ "total": 513, "porPartido": [{"partido":"PL","n":90}], "membros": [ {"id","nome","partido","uf","foto","genero","eleicao2026"} ], "fonte": {}, "atualizado" }`
- `dados/senado.json`: mesmo formato, com `"fimMandato"` em cada membro.
- `dados/executivo.json`: `{ "presidente": {resumo}, "vice": {resumo}, "fontes": [], "atualizado" }` (resumo = `id, nome, cargo, partido, foto, genero, mandato, eleicao2026`).
- `dados/manual/ministros.json` e `dados/manual/governadores.json`: pesquisados à mão, **sempre com fonte** em cada item.
- `dados/estados/<UF>.json`: `{ "uf", "nome", "capital": {"ibge","nome"}, "governador": {...}, "vice": {...}, "senadores": ["sen-..."], "deputadosFederais": ["dep-..."], "deputadosEstaduais": { "total", "aviso", "fonte", "membros": [ {"id","nome","partido","foto","genero","votos","situacao2022","eleicao2026"} ] }, "municipios": 417, "atualizado" }`
- `dados/cidades/<UF>.json`: lista para escolher a cidade: `[ {"ibge","nome","prefeito":"Nome (PARTIDO)"} ]`.
- `dados/cidades/<UF>/<IBGE>.json`: `{ "ibge","nome","uf","prefeito":{...},"vice":{...},"vereadores":{"total","aviso","fonte","membros":[...]},"atualizado" }`.
- `dados/busca.json`: `[[id, nome, cargo curto, UF, partido, cidade ou null], ...]` (sem vereadores; eles aparecem na página da cidade).
- `dados/simples/<00-99>.json`: cache das explicações simples: `{ "camara:2345678": "Explicação simples", ... }` (arquivo = 2 últimos dígitos do número).

`eleicao2026.situacao`: `eleito` | `reeleito` | `segundo-turno` | `nao-eleito` | `suplente` | `candidato` | `nao-concorreu` | `null` (não sabemos).

---

## Contrato dos slides (`conteudo/entenda/parte-N.json`)

```jsonc
{
  "parte": 1, "ic": "🤝", "nome": "O que é política?",
  "resumo": "Uma frase dizendo o que a parte ensina.",
  "fontes": [ { "id": "cf-art1", "veiculo": "Planalto", "titulo": "Constituição Federal, art. 1º", "url": "https://...", "data": "1988-10-05" } ],
  "glossario": [ { "termo": "mandato", "simples": "O tempo que a pessoa eleita fica no cargo." } ],
  "slides": [ { "tipo": "...", "...": "...", "fontes": ["cf-art1"] } ]
}
```

Tipos de slide: `abertura`, `explica`, `cards`, `passos`, `comparar`, `numeros`, `historia`, `quiz`, `simulador`. Os campos de cada tipo e as ilustrações disponíveis estão descritos no começo de `js/entenda.js`.

## Publicar

Repositório privado no GitHub + Vercel (Framework Preset: Other). Commits com o e-mail noreply do GitHub (senão a Vercel bloqueia o deploy). **Nada é publicado sem o dono pedir.**
