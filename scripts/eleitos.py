"""Quem foi eleito em 2026 e quando toma posse ("Quem assume", nas páginas do Brasil, do estado e da cidade).

Gera:
- dados/eleitos/BR.json ......... presidente e vice eleitos; o Senado e a Câmara a partir de 1º/2/2027 (listas curtas);
                                   as contas de quem foi reeleito, de quem troca de cargo e de quem chega agora
- dados/eleitos/<UF>.json ....... governador e vice, senadores (com os 2 suplentes), deputados federais e deputados
                                   estaduais (ou distritais) eleitos no estado, com a ficha do TSE (foto, partido, votos,
                                   bens declarados...) e a data da posse de cada cargo. É daqui que sai o perfil
                                   pessoa.html?id=e26-<UF>-<SQ_CANDIDATO> de quem foi eleito e não tem cargo hoje
- dados/eleitos/municipal.json .. a próxima eleição municipal (data, o que se escolhe, posse) e, por cidade, as eleições
                                   suplementares (marcadas ou feitas) e quem tem um cargo na cidade e foi eleito em 2026

Cada cargo sai do arquivo no dia da posse (scripts/mandatos.py): depois disso, quem foi eleito já aparece nas listas de
quem está no cargo, com o perfil normal. Quando todos os cargos de um arquivo já tomaram posse, o arquivo é apagado.

Fontes: TSE (Dados Abertos de 2026: candidaturas com a situação depois da totalização, bens e votação por município e
zona; candidaturas de 2018, 2022 e 2024, para ligar cada pessoa ao cargo que tem hoje; DivulgaCandContas: foto, página
de cada candidatura e eleições suplementares); Câmara e Senado (quem está no mandato hoje, pelas mesmas consultas do
tse.py); Planalto (Constituição e Lei 9.504/1997).

Ligação das pessoas: CPF; sem CPF, nome civil + data de nascimento (como o tse.py). Nunca só pelo nome. O CPF serve só
para ligar as pessoas e nunca vai para os arquivos.

Uso:
    python scripts/eleitos.py                  # roda no robô diário, depois do tse.py
    python scripts/eleitos.py --hoje 2027-01-07 --saida .cache/eleitos/teste   # simula uma data (testes da posse)
Se o TSE estiver fora do ar, ficam os arquivos de antes.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import re
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import *  # noqa: E402,F401
import ibge  # noqa: E402
import mandatos  # noqa: E402
import tse  # noqa: E402

ANO = 2026
SAIDA = DADOS / "eleitos"
CACHE_E = CACHE / "eleitos"
URL_VOTOS = f"{tse.CDN}votacao_candidato_munzona/votacao_candidato_munzona_{ANO}.zip"
DIAS_VOTOS = 7          # o arquivo de votos tem ~460 MB e o TSE o refaz todo dia; depois da totalização, quase não muda
PAUSA = 1.2             # segundos entre pedidos ao DivulgaCandContas
CF = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm"
LEI_ELEICOES = "https://www.planalto.gov.br/ccivil_03/leis/l9504.htm"
QUADRO_EC = "https://www.planalto.gov.br/ccivil_03/constituicao/Emendas/Emc/quadro_emc.htm"
TSE_SUPLEMENTARES = "https://www.tse.jus.br/eleicoes/eleicoes-suplementares"
# conferido à mão no quadro de Emendas Constitucionais do Planalto: a mais nova era a EC 141, de 16/10/2026, e nenhuma
# mudou a data das eleições municipais nem o mandato de prefeitos e vereadores (art. 29). Confira de novo se mudar.
EC_CONFERIDA = ("2026-10-29", 141)

# DS_CARGO do TSE -> (tipo no site, cargo em scripts/mandatos.py)
CARGOS = {
    "PRESIDENTE": ("pres", "presidente"), "VICE-PRESIDENTE": ("vp", "vice-presidente"),
    "GOVERNADOR": ("gov", "governador"), "VICE-GOVERNADOR": ("vgov", "vice-governador"),
    "SENADOR": ("sen", "senador"), "1º SUPLENTE": ("supl1", "senador"), "2º SUPLENTE": ("supl2", "senador"),
    "DEPUTADO FEDERAL": ("dep", "deputado_federal"), "DEPUTADO ESTADUAL": ("dest", "deputado_estadual"),
    "DEPUTADO DISTRITAL": ("dest", "deputado_estadual"),
}
ANOS_MANDATO = {"sen": 8, "supl1": 8, "supl2": 8}  # os outros: 4
# cargo em inglês, para as frases prontas (tipo -> en)
CARGO_EN = {"pres": "President", "vp": "Vice President", "gov": "governor", "vgov": "vice governor", "sen": "senator",
            "supl1": "1st alternate senator", "supl2": "2nd alternate senator", "dep": "federal deputy",
            "dest": "state deputy", "dist": "district deputy"}
CARGO_EN_BUSCA = {"pres": "President-elect", "vp": "Vice President-elect", "gov": "Governor-elect",
                  "vgov": "Vice Governor-elect", "sen": "Senator-elect", "supl1": "Elected 1st alternate senator",
                  "supl2": "Elected 2nd alternate senator", "dep": "Federal Deputy-elect", "dest": "State Deputy-elect",
                  "dist": "District Deputy-elect"}
# quem tem de deixar o cargo 6 meses antes para concorrer a outro (Constituição, art. 14, § 6º). Se o site ainda mostra a
# pessoa nesse cargo, a ficha está desatualizada: ela conta como "sem cargo eletivo hoje" ("antes")
RENUNCIA = {"pres", "gov", "pref"}
# ordem para escolher o cargo de hoje quando a pessoa aparece em mais de uma lista
ORDEM_CARGO = ["pres", "vp", "sen", "dep", "gov", "vgov", "dest", "pref", "vpref", "ver"]

# tipos de bem do TSE (DS_TIPO_BEM_CANDIDATO) em inglês; o que não estiver aqui aparece em português
TIPOS_BEM_EN = {
    "Veículo automotor terrestre: caminhão, automóvel, moto, etc.": "Land vehicle (truck, car, motorcycle, etc.)",
    "Terreno": "Plot of land", "Casa": "House", "Apartamento": "Apartment",
    "Depósito bancário em conta corrente no País": "Money in a checking account in Brazil",
    "Depósito bancário em conta corrente no exterior": "Money in a bank account abroad",
    "Quotas ou quinhões de capital": "Shares in a company (quotas)",
    "Aplicação de renda fixa (CDB, RDB e outros)": "Fixed-income investment (CDB, RDB and others)",
    "OUTROS BENS E DIREITOS": "Other assets and rights", "Outros bens imóveis": "Other real estate",
    "Outras aplicações e Investimentos": "Other investments", "Caderneta de poupança": "Savings account",
    "Outras participações societárias": "Other stakes in companies",
    "Dinheiro em espécie - moeda nacional": "Cash (Brazilian reais)",
    "Dinheiro em espécie - moeda estrangeira": "Cash (foreign currency)",
    "Ações (inclusive as provenientes de linha telefônica)": "Stocks", "Outros fundos": "Other funds",
    "Consórcio não contemplado": "Share in a purchase pool that has not been drawn",
    "Outros créditos e poupança vinculados": "Other credits and linked savings",
    "Outros bens móveis": "Other movable goods", "VGBL - Vida Gerador de Benefício Livre": "Private pension plan (VGBL)",
    "Terra nua": "Bare land", "Sala ou conjunto": "Office room or suite", "Prédio residencial": "Residential building",
    "Prédio comercial": "Commercial building", "Crédito decorrente de empréstimo": "Money lent to someone",
    "Fundos: Ações, Mútuos de Privatização, Invest. Empresas Emergentes, Invest.Participação e Invest. Índice Mercado":
        "Stock investment funds",
    "Fundo de Investimento Imobiliário": "Real estate investment fund", "Loja": "Store",
    "Fundo de Longo Prazo e Fundo de Investimentos em Direitos Creditórios (FIDC)": "Long-term or receivables fund (FIDC)",
    "Bem relacionado com o exercício da atividade autônoma": "Equipment for self-employed work",
    "Outros depósitos à vista e numerário": "Other cash and demand deposits",
    "Jóia, quadro, objeto de arte, de coleção, antiguidade, etc.": "Jewelry, art, collectibles or antiques",
    "Embarcação": "Boat", "Construção": "Building under construction", "Fundo de Curto Prazo": "Short-term fund",
    "Galpão": "Warehouse", "Ouro, ativo financeiro": "Gold (financial asset)", "Linha telefônica": "Phone line",
    "Benfeitorias": "Improvements to a property", "Aeronave": "Aircraft", "Título de clube e assemelhado": "Club membership",
    "Crédito decorrente de alienação": "Money owed from a sale",
    "Poupança para construção ou aquisição de bem imóvel": "Savings to build or buy real estate",
    "Direito de autor, de inventor e patente": "Copyright, inventor's rights and patents",
    "Mercado futuros, de opções e a termo": "Futures, options and forward contracts",
    "Licença e concessões especiais": "Special licenses and concessions", "Leasing": "Leasing",
}
_TIPOS_BEM_EN = {chave_nome(k): v for k, v in TIPOS_BEM_EN.items()}

# as Assembleias que não tomam posse em 1º de fevereiro (scripts/mandatos.py, POSSE_ESTADUAL), com a norma de cada uma (as
# mesmas fontes da página "De onde vêm os dados", js/info.js)
FONTE_POSSE_UF = {
    "RS": ("Assembleia Legislativa do RS", "Constituição do Rio Grande do Sul, art. 49, § 3º (a posse dos deputados é em 31 de janeiro)",
           "https://www2.al.rs.gov.br/dal/LinkClick.aspx?fileticket=WQdIfqNoXO4%3d&tabid=3683&mid=5359"),
    "DF": ("Sistema Integrado de Normas Jurídicas do DF (SINJ-DF)", "Emenda à Lei Orgânica nº 131, de 2024 (a posse dos deputados distritais é em 6 de janeiro)",
           "https://www.sinj.df.gov.br/sinj/Norma/c50c92bdd30e4a04ae0c20c0d1dd89f2/ELO_131_2024.html"),
    "RR": ("Assembleia Legislativa de Roraima", "Constituição de Roraima, art. 30, § 4º (Emenda 75/2021: a posse dos deputados estaduais é em 1º de janeiro)",
           "https://sapl.al.rr.leg.br/norma/3912"),
}

HOJE = None  # data de hoje (AAAA-MM-DD); --hoje troca para simular outra data


def hoje_() -> str:
    return HOJE or hoje()


def a_(g: str | None) -> str:
    return "a" if g == "F" else "o"


def tipo_dist(tipo: str, uf: str) -> str:
    return "dist" if tipo == "dest" and uf == "DF" else tipo


# ---------------------------------------------------------------- dados do TSE de 2026
def votos_2026() -> dict:
    """{"SQ|turno": votos nominais válidos} de 2026, somados da votação por município e zona (Dados Abertos do TSE).
    O arquivo do TSE tem ~460 MB: baixa para .cache/eleitos, soma e apaga; as somas valem DIAS_VOTOS dias (no robô,
    .cache/eleitos é guardado de um dia para o outro). Se o TSE não responder, valem as somas de antes."""
    destino = CACHE_E / f"votos_{ANO}.json"
    antes = ler_json(destino)
    if antes and time.time() - destino.stat().st_mtime < DIAS_VOTOS * 86400:
        return antes
    z = CACHE_E / f"votacao_candidato_munzona_{ANO}.zip"
    try:
        z = baixar_arquivo(URL_VOTOS, f"eleitos/{z.name}", max_idade_h=DIAS_VOTOS * 24)
        soma, data = collections.Counter(), None
        with zipfile.ZipFile(z) as zz:
            for nome in tse.membros_csv(zz):
                with zz.open(nome) as f:
                    cab = f.readline().decode("latin-1").strip().replace('"', "").split(";")
                    i_t, i_sq, i_g = cab.index("NR_TURNO"), cab.index("SQ_CANDIDATO"), cab.index("DT_GERACAO")
                    i_v = cab.index("QT_VOTOS_NOMINAIS_VALIDOS")
                    for linha in f:
                        p = linha.split(b";")
                        if len(p) != len(cab):  # ";" dentro de algum texto: usa o leitor de CSV
                            p = [x.encode("latin-1") for x in next(csv.reader([linha.decode("latin-1")], delimiter=";"))]
                        if data is None:
                            data = data_iso(p[i_g].decode("latin-1").strip('"'))
                        soma[p[i_sq].strip(b'"').decode() + "|" + p[i_t].strip(b'"').decode()] += int(p[i_v].strip(b'"') or 0)
        v = {"data": data, "votos": dict(soma)}
        salvar_json(destino, v)
        log(f"  votos de {ANO}: {len(soma)} candidaturas somadas (arquivo do TSE de {data})")
        return v
    except Exception as e:  # noqa: BLE001
        if antes:
            log(f"  [aviso] votação de {ANO} não baixou ({e}); valem as somas de {antes.get('data')}")
            return antes
        raise
    finally:
        if z.exists():
            z.unlink()


def extras_2026() -> dict:
    """Do arquivo de candidaturas de 2026, o que o tse.cand() não guarda: federação e UF de nascimento.
    {(SQ, turno): {"federacao": {"sigla", "nome"} | None, "ufNasc": "BA" | None}}"""
    out = {}
    for r in tse.ler_csv(tse.zip_tse("consulta_cand", ANO)):
        if not (r.get("DS_SIT_TOT_TURNO") or "").upper().startswith("ELEITO"):
            continue
        uf_n = (r.get("SG_UF_NASCIMENTO") or "").strip().upper()
        out[(r["SQ_CANDIDATO"], int(r["NR_TURNO"]))] = {
            "federacao": federacao(tse.social(r.get("NM_FEDERACAO")), tse.social(r.get("DS_COMPOSICAO_FEDERACAO"))),
            "ufNasc": uf_n if uf_n in tse.REGIAO else None,
        }
    return out


# siglas de partido que são palavras (no nome de uma federação, ficam como palavra: "Federação PSOL Rede")
_PALAVRAS = {"REDE", "NOVO", "UNIÃO", "CIDADANIA", "SOLIDARIEDADE", "PODEMOS", "AVANTE", "MOBILIZA", "DEMOCRATA",
             "REPUBLICANOS", "AGIR", "PATRIOTA"}


def federacao(nm: str | None, comp: str | None) -> dict | None:
    """Federação de partidos (partidos que se juntam por pelo menos 4 anos e atuam como um só: Lei 9.096/1995, art. 11-A).
    'FEDERAÇÃO BRASIL DA ESPERANÇA - FE BRASIL', '13-PT/65-PC do B/43-PV' ->
    {"nome": "Federação Brasil da Esperança", "sigla": "FE BRASIL", "partidos": ["PT", "PC do B", "PV"]}"""
    if not nm:
        return None
    partidos = [s.split("-", 1)[-1].strip() for s in (comp or "").split("/") if s.strip()]
    base, _, sigla = nm.partition(" - ")
    up = {x.upper() for x in partidos}
    nome = " ".join(w.upper() if w.upper() in up and w.upper() not in _PALAVRAS else w
                    for w in (tse.nome_tse(base) or base).split())
    return {"nome": nome, "sigla": sigla.strip() or None, "partidos": partidos}


def bens_2026(sqs: set) -> tuple[dict, dict, str | None]:
    """Bens declarados de quem foi eleito: ({SQ: {"total", "itens": [[código do tipo, valor]]}}, {código: [tipo, tipo_en]},
    data do arquivo). Só o tipo e o valor: a descrição de cada bem é texto livre (pode ter endereço ou número de conta) e
    fica na página da candidatura no DivulgaCandContas, que o perfil liga."""
    por_sq, tipos, data = collections.defaultdict(list), {}, None
    for r in tse.ler_csv(tse.zip_tse("bem_candidato", ANO)):
        data = data or data_iso(r["DT_GERACAO"])
        sq = r["SQ_CANDIDATO"]
        if sq not in sqs:
            continue
        try:
            valor = round(float((r["VR_BEM_CANDIDATO"] or "0").replace(".", "").replace(",", ".")), 2)
        except ValueError:
            continue
        cod = (r.get("CD_TIPO_BEM_CANDIDATO") or "").strip() or "0"
        ds = limpa(r.get("DS_TIPO_BEM_CANDIDATO")) or "Outros bens e direitos"
        tipos.setdefault(cod, [ds[:1].upper() + ds[1:].lower() if ds.isupper() else ds, _TIPOS_BEM_EN.get(chave_nome(ds))])
        try:
            ordem = int(r.get("NR_ORDEM_BEM_CANDIDATO") or 0)
        except ValueError:
            ordem = 0
        por_sq[sq].append((ordem, cod, valor))
    out = {}
    for sq, l in por_sq.items():
        l.sort()
        out[sq] = {"total": round(sum(x[2] for x in l), 2), "itens": [[c, v] for _, c, v in l]}
    return out, tipos, data

# ---------------------------------------------------------------- quem tem um cargo hoje (as listas do site)
_SQ_FOTO = re.compile(r"/img/\d+/(\d+)/")
_SQ_CAND = re.compile(r"/candidato/[A-Z]+/[A-Z]{2}/\d+/(\d+)/\d{4}/")


def _sq_2024(p: dict) -> str | None:
    """SQ da candidatura de 2024 de um prefeito ou vice (está na URL da foto ou da página do DivulgaCandContas)."""
    for u in [p.get("foto") or ""] + [f.get("url") or "" for f in (p.get("fontes") or []) if isinstance(f, dict)]:
        m = _SQ_FOTO.search(u) or _SQ_CAND.search(u)
        if m:
            return m.group(1)
    return None


def cargos_de_hoje(b18: tse.Base, b22: tse.Base) -> tuple[dict, dict, dict, list]:
    """Quem tem um cargo hoje segundo as listas que o site mostra (Brasil, estados e cidades), com o CPF (ou nome civil e
    nascimento) da candidatura no TSE, para ligar com quem foi eleito em 2026.
    Devolve ({cpf: [cargo]}, {(nome, nascimento): [cargo]}, {UE do TSE: código IBGE}, federais do tse.py).
    cargo = {"id", "tipo", "cargo", "onde", "uf", "ibge"?, "nome", "partido", "foto", "genero"}"""
    lista = []

    def junta(pid, tipo, cargo, onde, uf, ficha, cpf, nome, nasc, ibge_=None):
        if not (cpf or (nome and nasc)):
            return
        d = {"id": pid, "tipo": tipo, "cargo": cargo, "onde": onde, "uf": uf, "nome": ficha.get("nome"),
             "partido": ficha.get("partido"), "foto": ficha.get("foto"), "genero": ficha.get("genero"),
             "_cpf": tse.cpf_valido(cpf), "_nn": (chave_nome(nome), nasc[:10]) if nome and nasc else None}
        if ibge_:
            d["ibge"] = ibge_
        lista.append(d)

    # federais: as mesmas consultas do tse.py (Câmara, Senado e Planalto), já guardadas no cache por ele
    listas = {}
    for arq in ("camara.json", "senado.json"):
        for m in (ler_json(DADOS / arq) or {}).get("membros") or []:
            listas[m["id"]] = m
    ex = ler_json(DADOS / "executivo.json") or {}
    for k in ("presidente", "vice"):
        if ex.get(k):
            listas[ex[k]["id"]] = ex[k]
    fed = tse.carregar_federais(b18, b22, b22)
    for f in fed:
        ficha = dict(listas.get(f["id"]) or {}, nome=(listas.get(f["id"]) or {}).get("nome") or f["nome"])
        ficha.setdefault("partido", f["partido"])
        ficha.setdefault("genero", f["genero"])
        uf = f["uf"] if f["tipo"] in ("dep", "sen") else "BR"
        junta(f["id"], f["tipo"], tse.cargo_txt(f["cargo"], ficha.get("genero")), None if uf == "BR" else uf, uf, ficha,
              f["cpf"], f["nomeCivil"], f["nasc"])
    # estados: governador, vice e deputados estaduais (a lista oficial da Assembleia ou a do TSE)
    for arq in sorted((DADOS / "estados").glob("*.json")):
        e = ler_json(arq) or {}
        uf = e.get("uf") or arq.stem
        for k, tipo, cargo in (("governador", "gov", "GOVERNADOR"), ("vice", "vgov", "VICE-GOVERNADOR")):
            p = e.get(k) or {}
            if not p.get("nome") or p.get("vago"):
                continue
            cpf, nome, nasc = tse.chaves_executivo_estadual(p, b22)
            junta(p["id"], tipo, tse.cargo_txt(cargo, p.get("genero")), uf, uf, p, cpf, nome, nasc)
        for m in (e.get("deputadosEstaduais") or {}).get("membros") or []:
            sq = m["id"].rsplit("-", 1)[1]
            c = b22.linha(sq) if sq.isdigit() else None
            if c:
                junta(m["id"], "dest", tse.cargo_txt(c["cargo"], m.get("genero") or c["genero"]), uf, uf, m, c["cpf"], c["nome"], c["nasc"])
    # cidades: prefeito, vice e vereadores (o CPF vem da candidatura de 2024)
    quer, cidades, ues = {}, {}, {}
    for arq in sorted((DADOS / "cidades").glob("*/*.json")):
        c = ler_json(arq) or {}
        uf, cod = arq.parent.name, arq.stem
        onde = f"{c.get('nome')} ({uf})"
        for k, tipo in (("prefeito", "pref"), ("vice", "vpref")):
            p = c.get(k)
            if not isinstance(p, dict) or not p.get("nome") or p.get("vago"):
                continue
            sq = _sq_2024(p)
            cargo = ("Prefeit" if tipo == "pref" else "Vice-prefeit") + a_(p.get("genero"))
            if p.get("desde") and p.get("nomeCivil") and p.get("nascimento"):  # pesquisa à mão (ex.: vice que assumiu)
                junta(p["id"], tipo, cargo, onde, uf, p, None, p["nomeCivil"], p["nascimento"], cod)
            elif sq:
                quer[sq] = (p["id"], tipo, cargo, onde, uf, p, cod)
        for v in (c.get("vereadores") or {}).get("membros") or []:
            sq = v["id"].rsplit("-", 1)[1]
            if sq.isdigit():
                quer[sq] = (v["id"], "ver", "Vereador" + ("a" if v.get("genero") == "F" else ""), onde, uf, v, cod)
    for r in tse.ler_csv(tse.zip_tse("consulta_cand", 2024)):
        ues[r["SG_UE"]] = (r["SG_UF"], r["NM_UE"])
        x = quer.get(r["SQ_CANDIDATO"])
        if x:
            junta(x[0], x[1], x[2], x[3], x[4], x[5], r.get("NR_CPF_CANDIDATO"), limpa(r["NM_CANDIDATO"]),
                  data_iso(r["DT_NASCIMENTO"]), x[6])
    por_cpf, por_nn = collections.defaultdict(list), collections.defaultdict(list)
    for d in lista:
        cpf, nn = d.pop("_cpf"), d.pop("_nn")
        if cpf:
            por_cpf[cpf].append(d)
        if nn:
            por_nn[nn].append(d)
    log(f"  cargos de hoje: {len(lista)} pessoas nas listas do site ({dict(collections.Counter(d['tipo'] for d in lista))})")
    return por_cpf, por_nn, ibge.casar_tse(ues), fed

# ---------------------------------------------------------------- quem foi eleito em 2026
def eleitos_2026(b26: tse.Base2026) -> list[dict]:
    """As linhas do TSE de quem foi eleito em 2026: a do turno que decidiu (no 2º turno, a do 2º turno)."""
    out = []
    for rs in b26.por_sq.values():
        rs = [c for c in rs if c["el"] in tse.ORDINARIAS[ANO] and c["cargo"] in CARGOS]
        if rs:
            ult = max(rs, key=lambda c: c["turno"])
            if tse.eleito(ult["sit"]):
                out.append(ult)
    return out


def titulares(eleitos: list[dict]) -> dict:
    """{SQ do vice ou do suplente: linha de quem encabeça a chapa} (vice: mesmo estado; suplentes: mesmo número)."""
    exec_ = {(c["cargo"], c["uf"]): c for c in eleitos if c["cargo"] in ("PRESIDENTE", "GOVERNADOR")}
    sen = {(c["uf"], c["num"]): c for c in eleitos if c["cargo"] == "SENADOR"}
    out = {}
    for c in eleitos:
        if c["cargo"] in ("VICE-PRESIDENTE", "VICE-GOVERNADOR"):
            t = exec_.get((c["cargo"][5:], c["uf"]))
        elif c["cargo"] in tse.SUPLENTES_SENADO:
            t = sen.get((c["uf"], c["num"]))
        else:
            continue
        if t:
            out[c["sq"]] = t
        else:
            log(f"  [aviso] sem a chapa de {c['urna']} ({c['cargo']}, {c['uf']})")
    return out


def situacao(c: dict, tipo: str, tit: dict | None) -> tuple[str, str]:
    """(situação em português, em inglês), nas palavras que o site já usa (js/traducoes.js, REGRAS_SIT)."""
    a = a_(c["genero"])
    n_tit = tse.nome_tse(tit["urna"]) if tit else None
    if tipo in ("dep", "dest"):
        en = {"ELEITO POR QP": "Elected through the party's vote quota",
              "ELEITO POR MÉDIA": "Elected through the leftover seats"}.get(c["sit"], "Elected")
        return tse.sit_txt(c["sit"], c["genero"]) or f"Eleit{a}", en
    turno_en = "Elected in the first round" if c["turno"] == 1 else "Elected in the runoff"
    if tipo in ("pres", "gov"):
        return f"Eleit{a} no {c['turno']}º turno", turno_en
    if tipo in ("vp", "vgov"):
        return (f"Eleit{a} no {c['turno']}º turno" + (f", na chapa de {n_tit}" if n_tit else ""),
                turno_en + (f", on {n_tit}'s ticket" if n_tit else ""))
    if tipo == "sen":
        return f"Eleit{a}", "Elected"
    n = c["cargo"][0]
    return (f"Eleit{a} {n}º suplente" + (f", na chapa de {n_tit}" if n_tit else ""),
            ("Elected 1st alternate" if n == "1" else "Elected 2nd alternate") + (f", on {n_tit}'s ticket" if n_tit else ""))


def cargo_hoje(c: dict, tipo: str, por_cpf: dict, por_nn: dict) -> tuple[dict | None, dict | None, str]:
    """(cargo que a pessoa tem hoje, cargo que ela deixou para concorrer, chegada).
    chegada: "reeleicao" (o mesmo cargo de hoje), "troca" (tem outro cargo hoje) ou "novo" (sem cargo eletivo hoje)."""
    cands = por_cpf.get(c["cpf"] or "") or por_nn.get((chave_nome(c["nome"]), c["nasc"])) or []
    cands = list({d["id"]: d for d in cands}.values())
    if not cands:
        return None, None, "novo"
    mesmo = [d for d in cands if d["tipo"] == tipo]
    if mesmo:
        return mesmo[0], None, "reeleicao"
    d = min(cands, key=lambda x: ORDEM_CARGO.index(x["tipo"]) if x["tipo"] in ORDEM_CARGO else 99)
    if d["tipo"] in RENUNCIA:
        # presidente, governador e prefeito deixam o cargo 6 meses antes para concorrer a outro (Constituição, art. 14,
        # § 6º): se o site ainda mostra a pessoa no cargo, é a ficha que está desatualizada
        return None, d, "novo"
    return d, None, "troca"


def resumo_cargo(d: dict | None) -> dict | None:
    return {k: d[k] for k in ("id", "cargo", "onde") if d.get(k)} if d else None


def pessoa(c: dict, ctx: dict) -> dict:
    """A ficha de quem foi eleito, para as listas "Quem assume" e (se não tem cargo hoje) para o perfil e26-."""
    tipo, chave = CARGOS[c["cargo"]]
    uf, sq, g = c["uf"], c["sq"], c["genero"]
    tit = ctx["titular"].get(sq)
    uf_posse = uf if tipo == "dest" else None
    eid = f"e26-{uf}-{sq}"
    atual, antes, chegada = cargo_hoje(c, tipo, ctx["por_cpf"], ctx["por_nn"])
    link = (atual or antes or {}).get("id") or eid
    sit, sit_en = situacao(c, tipo, tit)
    quem = tit or c  # vice e suplentes: os votos são os da chapa
    votos = ctx["votos"].get(f"{quem['sq']}|{quem['turno']}")
    ficha = atual or antes or {}
    d = {
        "id": eid, "link": link, "tipo": tipo, "cargo": tse.cargo_txt(c["cargo"], g), "uf": uf,
        "nome": ficha.get("nome") or tse.nome_tse(c["urna"]), "partido": c["partido"], "genero": g,
        "foto": ficha.get("foto") or tse.url_foto(ANO, sq, uf), "numero": c["num"],
        "votos": votos, "turno": c["turno"], "situacao": sit, "situacao_en": sit_en,
        "posse": mandatos.posse(chave, ANO, uf_posse), "fim": mandatos.posse(chave, ANO + ANOS_MANDATO.get(tipo, 4), uf_posse),
        "chegada": chegada,
    }
    if tit:
        d["chapa"] = {"id": f"e26-{tit['uf']}-{tit['sq']}", "nome": tse.nome_tse(tit["urna"])}
        d["votosDaChapa"] = True
    if atual:
        d["atual"] = resumo_cargo(atual)
    if antes:
        d["antes"] = resumo_cargo(antes)
    ex = ctx["extras"].get((sq, c["turno"])) or ctx["extras"].get((sq, 1)) or {}
    if ex.get("federacao"):
        d["federacao"] = ex["federacao"]
    if link == eid:
        # quem não tem cargo hoje ganha o perfil e26-: a ficha do TSE inteira
        b = ctx["bens"].get(sq) or {"total": 0.0, "itens": []}
        d.update({k: v for k, v in {
            "nomeCivil": tse.nome_tse(c["civil"]), "nascimento": c["nasc"], "ufNascimento": ex.get("ufNasc"),
            "ocupacao": tse._ficha_txt(c.get("ocup"), g), "escolaridade": tse._ficha_txt(c.get("instr"), None),
            "bens": {"total": b["total"], "itens": b["itens"]},
            "tse": tse.url_cand(ANO, sq, uf, c["ue"]),
        }.items() if v is not None})
        if sq in ctx["fonte2t"]:
            d["fonte2turno"] = ctx["fonte2t"][sq]
    return d

# ---------------------------------------------------------------- arquivos do Brasil e de cada estado
def fonte_cf(titulo: str) -> dict:
    return fonte("Planalto", f"Constituição Federal, {titulo}", CF, "1988-10-05")


def conta(lista: list[dict]) -> dict:
    """Só contagem: quantos voltam ao mesmo cargo, quantos vêm de outro cargo e quantos não têm cargo eletivo hoje."""
    c = collections.Counter(p["chegada"] for p in lista)
    return {"total": len(lista), "reeleicao": c["reeleicao"], "troca": c["troca"], "novo": c["novo"]}


def ordena(lista: list[dict]) -> list[dict]:
    return sorted(lista, key=lambda p: tse.chave_ord(p.get("nome"), p.get("id") or ""))


CURTA = ("id", "link", "nome", "partido", "uf", "genero", "foto", "chegada", "votos", "situacao")


def curta(p: dict) -> dict:
    """A ficha curta das listas grandes (o Senado e a Câmara do Brasil inteiro): sem o id do cargo de hoje, que já é o
    "link", e sem a situação em inglês (o site traduz "Eleito por QP" e "Eleito por média")."""
    d = {k: p[k] for k in CURTA if p.get(k) is not None}
    for k in ("atual", "antes"):
        if p.get(k):
            d[k] = {x: p[k][x] for x in ("cargo", "onde") if p[k].get(x)}
    return d


def senado_continua(fed: list[dict], eleitos_p: list[dict], b22: tse.Base) -> list[dict]:
    """Quem fica no Senado até 2031 (dados/senado.json: quem está no cargo hoje com o mandato até 2031). Se a pessoa foi
    eleita para outro cargo em 2026, ela deixa o Senado quando tomar posse dele (Constituição, art. 54, II, "d") e quem
    assume é o 1º suplente da chapa (art. 56, § 1º), segundo o TSE (candidaturas de 2022)."""
    linha = {f["id"]: f.get("tse") for f in fed}
    saem = {p["atual"]["id"]: p for p in eleitos_p if p.get("atual") and p["chegada"] == "troca"}
    out = []
    for m in (ler_json(DADOS / "senado.json") or {}).get("membros") or []:
        if str(m.get("fimMandato") or "")[:4] <= str(ANO + 1):
            continue
        d = {k: m.get(k) for k in ("id", "nome", "partido", "uf", "genero", "foto", "fimMandato")}
        d["link"] = m["id"]
        p = saem.get(m["id"])
        if p:
            d["eleito2026"] = {"cargo": p["cargo"], "posse": p["posse"], "situacao": p["situacao"], "situacao_en": p["situacao_en"]}
            row = linha.get(m["id"])
            s1 = None
            if row and row["cargo"] == "SENADOR":
                s1 = next((x for x in b22.rows if x["cargo"] == "1º SUPLENTE" and x["uf"] == row["uf"] and x["el"] == row["el"]
                           and x["num"] == row["num"] and tse.eleito(x["sit"])), None)
            if s1:
                d["assume"] = {"nome": tse.nome_tse(s1["urna"]), "partido": s1["partido"], "genero": s1["genero"],
                               "foto": tse.url_foto(s1["ano"], s1["sq"], s1["uf"]),
                               "tse": tse.url_cand(s1["ano"], s1["sq"], s1["uf"], s1["ue"])}
        out.append(d)
    return ordena(out)


def nome_casa(uf: str) -> dict:
    """Nome da Assembleia (ou da Câmara Legislativa do DF), como o arquivo da Casa escreve (dados/assembleias/<UF>.json)."""
    a = ler_json(DADOS / "assembleias" / f"{uf}.json") or {}
    if uf == "DF":
        pt, en = "Câmara Legislativa do Distrito Federal", "Legislative Chamber of the Federal District"
    else:
        pt, en = "Assembleia Legislativa", "Legislative Assembly"
    return {"casa": a.get("casa") or pt, "casa_en": a.get("casa_en") or en, "sigla": a.get("sigla")}


def arquivo_uf(uf: str, ps: list[dict], nome_uf: str | None, continuam: list[dict]) -> dict | None:
    """dados/eleitos/<UF>.json: só os cargos que ainda não tomaram posse. None quando todos já tomaram."""
    por = collections.defaultdict(list)
    for p in ps:
        por[p["tipo"]].append(p)
    d, data = hoje_(), {"uf": uf, "nome": nome_uf, "eleicao": ANO}
    tem = False
    if mandatos.antes_da_posse("governador", ANO, d) and (por["gov"] or por["vgov"]):
        data["governo"] = {"posse": mandatos.posse("governador", ANO), "fim": mandatos.posse("governador", ANO + 4),
                           "governador": (por["gov"] or [None])[0], "vice": (por["vgov"] or [None])[0]}
        tem = True
    if mandatos.antes_da_posse("senador", ANO, d) and por["sen"]:
        sens = ordena(por["sen"])
        for s in sens:
            s["suplentes"] = sorted((x for t in ("supl1", "supl2") for x in por[t] if (x.get("chapa") or {}).get("id") == s["id"]),
                                    key=lambda x: x["tipo"])
        data["senado"] = {"posse": mandatos.posse("senador", ANO), "fim": mandatos.posse("senador", ANO + 8), "eleitos": sens,
                          "continuam": [x for x in continuam if x.get("uf") == uf]}
        tem = True
    if mandatos.antes_da_posse("deputado_federal", ANO, d) and por["dep"]:
        data["camara"] = {"posse": mandatos.posse("deputado_federal", ANO), "fim": mandatos.posse("deputado_federal", ANO + 4),
                          "vagas": len(por["dep"]), "membros": ordena(por["dep"])}
        tem = True
    if mandatos.antes_da_posse("deputado_estadual", ANO, d, uf=uf) and por["dest"]:
        data["assembleia"] = dict(nome_casa(uf), posse=mandatos.posse("deputado_estadual", ANO, uf),
                                  fim=mandatos.posse("deputado_estadual", ANO + 4, uf), vagas=len(por["dest"]),
                                  membros=ordena(por["dest"]))
        if uf in FONTE_POSSE_UF:
            data["assembleia"]["fontePosse"] = fonte(*FONTE_POSSE_UF[uf])
        tem = True
    if not tem:
        return None
    data["contas"] = {k: conta(v) for k, v in (
        ("senado", por["sen"] if "senado" in data else []),
        ("camara", por["dep"] if "camara" in data else []),
        ("assembleia", por["dest"] if "assembleia" in data else [])) if v}
    return data


def posses() -> dict:
    """As datas de posse dos eleitos em 2026 (scripts/mandatos.py), para a linha do tempo das páginas."""
    est = {uf: mandatos.posse("deputado_estadual", ANO, uf) for uf in tse.UFS}
    padrao = collections.Counter(est.values()).most_common(1)[0][0]
    return {"presidente": mandatos.posse("presidente", ANO), "governador": mandatos.posse("governador", ANO),
            "congresso": mandatos.posse("deputado_federal", ANO),
            "assembleias": {"padrao": padrao, "excecoes": {uf: v for uf, v in est.items() if v != padrao}}}


def fontes_posse() -> list[dict]:
    return [mandatos.EC111, fonte_cf("arts. 27, 28, 44, 46, 57 e 82 (posse e duração de cada mandato)")]


def arquivo_br(todas: list[dict], continuam: list[dict], b22: tse.Base) -> dict | None:
    """dados/eleitos/BR.json: presidente e vice eleitos, o Senado e a Câmara a partir de 1º/2/2027 e as contas."""
    d = hoje_()
    por = collections.defaultdict(list)
    for p in todas:
        por[p["tipo"]].append(p)
    data, tem = {"eleicao": ANO, "posses": posses()}, False
    if mandatos.antes_da_posse("presidente", ANO, d) and (por["pres"] or por["vp"]):
        data["presidencia"] = {"posse": mandatos.posse("presidente", ANO), "fim": mandatos.posse("presidente", ANO + 4),
                               "presidente": (por["pres"] or [None])[0], "vice": (por["vp"] or [None])[0]}
        tem = True
    if mandatos.antes_da_posse("senador", ANO, d) and por["sen"]:
        data["senado"] = {"posse": mandatos.posse("senador", ANO), "eleitos": [curta(p) for p in ordena(por["sen"])],
                          "continuam": continuam,
                          "fontes": [(ler_json(DADOS / "senado.json") or {}).get("fonte"),
                                     tse.fonte_candidatos(2022, b22.data, "Dados Abertos: candidaturas de 2022 (suplentes de senador)"),
                                     fonte_cf("arts. 46, 54 e 56 (Senado, suplentes e vaga)")]}
        data["senado"]["fontes"] = [f for f in data["senado"]["fontes"] if f]
        tem = True
    if mandatos.antes_da_posse("deputado_federal", ANO, d) and por["dep"]:
        data["camara"] = {"posse": mandatos.posse("deputado_federal", ANO), "vagas": len(por["dep"]),
                          "membros": [curta(p) for p in ordena(por["dep"])]}
        tem = True
    if not tem:
        return None
    vivos = []  # quem ainda não tomou posse
    for tipo, chave in (("pres", "presidente"), ("vp", "presidente"), ("gov", "governador"), ("vgov", "governador"),
                        ("sen", "senador"), ("dep", "deputado_federal")):
        if mandatos.antes_da_posse(chave, ANO, d):
            vivos += por[tipo]
    vivos += [p for p in por["dest"] if mandatos.antes_da_posse("deputado_estadual", ANO, d, uf=p["uf"])]
    data["contas"] = {k: conta([p for p in vivos if p["tipo"] in tipos]) for k, tipos in (
        ("presidencia", ("pres", "vp")), ("governadores", ("gov",)), ("senado", ("sen",)), ("camara", ("dep",)),
        ("assembleias", ("dest",)))}
    data["contas"] = {k: v for k, v in data["contas"].items() if v["total"]}
    return data

# ---------------------------------------------------------------- cidades: a próxima eleição municipal e as suplementares
def domingos_outubro(ano: int) -> tuple[str, str]:
    """(primeiro, último) domingo de outubro do ano: os dias do 1º e do 2º turno (Constituição, arts. 29, II, e 77)."""
    dias = [dt.date(ano, 10, d) for d in range(1, 32) if dt.date(ano, 10, d).weekday() == 6]
    return dias[0].isoformat(), dias[-1].isoformat()


def proxima_municipal() -> dict:
    """A próxima eleição de prefeito, vice e vereadores cuja posse ainda não aconteceu (a regra é a mesma para todas as
    cidades): 1º turno no primeiro domingo de outubro, 2º turno no último (só para prefeito, em cidades com mais de
    200 mil eleitores) e posse em 1º de janeiro do ano seguinte."""
    a = 2024
    while mandatos.posse("prefeito", a) <= hoje_():
        a += 4
    t1, t2 = domingos_outubro(a)
    return {"ano": a, "turno1": t1, "turno2": t2, "posse": mandatos.posse("prefeito", a),
            "fim": mandatos.posse("prefeito", a + 4), "mandato": [a + 1, a + 4],
            "fontes": [fonte_cf("art. 29, I, II e III (eleição e posse de prefeito, vice e vereadores) e art. 77 (2º turno)"),
                       fonte("Planalto", "Lei nº 9.504/1997 (Lei das Eleições), arts. 1º e 3º", LEI_ELEICOES, "1997-09-30"),
                       fonte("Planalto", f"Quadro das Emendas Constitucionais (até a EC {EC_CONFERIDA[1]}: nenhuma mudou a data "
                             "das eleições municipais)", QUADRO_EC, EC_CONFERIDA[0])]}


_FALHAS = {"divulga": 0}  # pedidos seguidos que falharam: com 2, o DivulgaCandContas não é mais procurado nesta rodada


def divulga(caminho: str, cache: str, horas: float):
    """Consulta pública do DivulgaCandContas (TSE), com cache em .cache/eleitos/divulga e pausa entre pedidos. Se o site
    estiver fora do ar (2 falhas seguidas), a rodada para de pedir e fica o que estava publicado."""
    destino = CACHE_E / "divulga" / cache
    if destino.exists() and time.time() - destino.stat().st_mtime < horas * 3600:
        return ler_json(destino)
    if _FALHAS["divulga"] >= 2:
        raise RuntimeError("o DivulgaCandContas não respondeu nesta rodada")
    time.sleep(PAUSA)
    try:
        r = baixar_json(f"{tse.DIVULGA}/rest/v1/{caminho}", cache=f"eleitos/divulga/{cache}", max_idade_h=horas,
                        headers=tse.H_DIVULGA, tentativas=3, timeout=60)
    except Exception:
        _FALHAS["divulga"] += 1
        raise
    _FALHAS["divulga"] = 0
    return r


def _eleito_divulga(c: dict, ue: str, uf: str, id_el: str) -> dict:
    sq = str(c["id"])
    return {"nome": tse.nome_tse(c.get("nomeUrna")) or tse.nome_tse(c.get("nomeCompleto")),
            "partido": (c.get("partido") or {}).get("sigla"), "numero": c.get("numero"),
            "situacao": c.get("descricaoTotalizacao"), "foto": tse.url_foto(2024, sq, ue, id_el),
            "tse": tse.url_cand(2024, sq, uf, ue, id_el)}


def suplementares(mapa_ue: dict, antigas: dict) -> dict:
    """{IBGE: [eleição suplementar]} das eleições suplementares ligadas às eleições municipais de 2024 (feitas ou marcadas),
    pela consulta pública do DivulgaCandContas, com quem foi eleito (prefeito, vice e vereadores). Se o TSE não responder,
    fica o que estava publicado (antigas)."""
    out = collections.defaultdict(list)
    d0 = hoje_()
    for uf in tse.UFS:
        if uf == "DF":
            continue
        try:
            lista = divulga(f"eleicao/suplementares/2024/{uf}", f"suplementares_2024_{uf}.json", 20) or []
        except Exception as e:  # noqa: BLE001
            log(f"  [aviso] eleições suplementares de {uf}: {e}; fica o que estava publicado")
            pre = next(k for k, v in ibge.UF_CODIGO.items() if v == uf)
            out.update({cod: l for cod, l in antigas.items() if cod.startswith(pre)})
            continue
        for e in lista:
            ue, data, id_el = str(e.get("siglaUF") or ""), str(e.get("dataEleicao") or "")[:10], str(e.get("id") or "")
            cod = mapa_ue.get(ue)
            if not cod or not data or not id_el:
                continue
            # resultado que já saiu (mais de 30 dias) não muda: o cache vale 30 dias
            horas = 24 * 30 if data < (dt.date.fromisoformat(d0) - dt.timedelta(days=30)).isoformat() else 20
            cargos, ok = {}, True
            try:
                for cod_cargo, chave in ((11, "prefeito"), (12, "vice"), (13, "vereadores")):
                    if chave == "vice" and not cargos.get("_tem11"):
                        continue
                    if chave == "vereadores" and cargos.get("_tem11"):
                        continue
                    r = divulga(f"candidatura/listar/2024/{ue}/{id_el}/{cod_cargo}/candidatos", f"listar_{ue}_{id_el}_{cod_cargo}.json", horas) or {}
                    cands = r.get("candidatos") or []
                    if cod_cargo == 11 and cands:
                        cargos["_tem11"] = True
                    if cands:
                        cargos[chave] = [_eleito_divulga(c, ue, uf, id_el) for c in cands
                                         if (c.get("descricaoTotalizacao") or "").upper().startswith("ELEIT")]
            except Exception as ex:  # noqa: BLE001
                log(f"  [aviso] eleição suplementar {e.get('nomeEleicao')}: {ex}; fica o que estava publicado")
                ok = False
            cargos.pop("_tem11", None)
            if not ok:
                velho = next((x for x in antigas.get(cod) or [] if x.get("data") == data), None)
                if velho:
                    out[cod].append(velho)
                continue
            if not cargos:
                continue  # o DivulgaCandContas não mostra nenhuma candidatura desta eleição nesta cidade
            eleitos_ = [x for v in cargos.values() for x in v]
            sit = "marcada" if data > d0 else "feita" if eleitos_ else "sem-resultado"
            out[cod].append({"data": data, "nome": limpa(e.get("nomeEleicao")), "situacao": sit,
                             "cargos": [k for k in ("prefeito", "vice", "vereadores") if k in cargos],
                             "eleitos": {k: v for k, v in cargos.items() if v},
                             "fonte": fonte("TSE", f"DivulgaCandContas: candidaturas da eleição \"{limpa(e.get('nomeEleicao'))}\"",
                                            f"{tse.DIVULGA}/#/candidato/{tse.REGIAO[uf]}/{uf}/{id_el}", d0)})
    return {k: sorted(v, key=lambda x: x["data"]) for k, v in out.items()}


def arquivo_municipal(todas: list[dict], mapa_ue: dict, saida: Path, fontes: dict) -> dict:
    """dados/eleitos/municipal.json: a próxima eleição municipal, as suplementares e quem tem um cargo na cidade e foi
    eleito em 2026 (vereador eleito deputado, por exemplo: na posse, deixa a Câmara Municipal e o suplente assume)."""
    antigo = ler_json(saida / "municipal.json") or {}
    antigas = {k: v.get("suplementares") for k, v in (antigo.get("cidades") or {}).items() if v.get("suplementares")}
    sup = suplementares(mapa_ue, antigas)
    por_cid = collections.defaultdict(list)
    for p in todas:
        cargo = p.get("atual") or p.get("antes")
        m = re.match(r"(?:pref|vpref|ver)-(\d{7})", (cargo or {}).get("id") or "")
        chave = CARGOS_CHAVE.get(p["tipo"])
        if m and mandatos.antes_da_posse(chave, ANO, hoje_(), uf=p["uf"] if p["tipo"] == "dest" else None):
            d = {k: p[k] for k in ("link", "nome", "partido", "genero", "foto", "cargo", "uf", "posse", "chegada") if p.get(k) is not None}
            d["hoje"] = {x: cargo[x] for x in ("cargo",) if cargo.get(x)}
            if p.get("antes"):
                d["deixou"] = True  # deixou o cargo para concorrer (Constituição, art. 14, § 6º)
            por_cid[m.group(1)].append(d)
    cids = {}
    for cod in sorted(set(sup) | set(por_cid)):
        c = {}
        if sup.get(cod):
            c["suplementares"] = sup[cod]
        if por_cid.get(cod):
            c["eleitos2026"] = ordena(por_cid[cod])
        cids[cod] = c
    return {"proxima": proxima_municipal(), "cidades": cids,
            "fontesSuplementares": [fonte("TSE", "Eleições suplementares (calendário e cidades)", TSE_SUPLEMENTARES, hoje_())],
            "fontesEleitos": [fontes["candidaturas"]]}


CARGOS_CHAVE = {t: ch for t, ch in CARGOS.values()}

# ---------------------------------------------------------------- junção com o resto do site (chamada pelo montar.py)
def fichas(pasta: Path = SAIDA) -> list[tuple[dict, str | None]]:
    """[(ficha, data do arquivo)] de todas as pessoas de dados/eleitos/BR.json e <UF>.json (com os suplentes de senador)."""
    out = []
    for arq in sorted(pasta.glob("*.json")):
        if arq.stem != "BR" and arq.stem not in tse.REGIAO:
            continue
        d = ler_json(arq) or {}
        at = d.get("atualizado")
        grupos = [d.get("presidencia") or {}, d.get("governo") or {}]
        ps = [g.get(k) for g in grupos for k in ("presidente", "vice", "governador") if isinstance(g.get(k), dict)]
        if arq.stem != "BR":
            for s in (d.get("senado") or {}).get("eleitos") or []:
                ps += [s] + list(s.get("suplentes") or [])
            for k in ("camara", "assembleia"):
                ps += list((d.get(k) or {}).get("membros") or [])
        out += [(p, at) for p in ps if p.get("id")]
    return out


def cargo_eleito(p: dict) -> tuple[str, str]:
    """("Deputada federal eleita", "Federal Deputy-elect"): o cargo de quem foi eleito e ainda não tomou posse."""
    tipo = tipo_dist(p.get("tipo") or "", p.get("uf") or "")
    pt = f"{p.get('cargo') or ''} eleit{a_(p.get('genero'))}".strip()
    return pt, CARGO_EN_BUSCA.get(tipo, "Elected in 2026")


def selo(p: dict) -> dict:
    """O selo "eleito em 2026" (campo eleicao2026, o mesmo dos perfis federais) de quem tem cargo numa cidade."""
    tipo = tipo_dist(p.get("tipo") or "", p.get("uf") or "")
    a = a_(p.get("genero"))
    cargo = (p.get("cargo") or "")[:1].lower() + (p.get("cargo") or "")[1:]
    en = CARGO_EN.get(tipo, "")
    return {"cargo": p.get("cargo"), "situacao": "suplente" if tipo in ("supl1", "supl2") else "eleito",
            "txt": f"Eleit{a} {cargo} em {ANO}", "txt_en": f"Elected {en} in {ANO}".replace("  ", " ")}


_MUNICIPAL = re.compile(r"^(?:pref|vpref|ver)-(\d{7})")


def busca_e_selos(pasta: Path = SAIDA) -> str:
    """Chamada pelo scripts/montar.py, depois de a busca ficar pronta:
    1. dados/busca.json ganha quem foi eleito em 2026 e tem o perfil e26- (sem cargo hoje) e os vereadores eleitos em 2026
       (a busca não tem vereadores; estes ficam nela até a posse), com o cargo em inglês na 7ª coluna. Ninguém entra duas
       vezes: quem já está na busca com outro id (mesmo nome, estado e partido) fica de fora;
    2. o selo "eleito em 2026" (eleicao2026) vai para quem tem cargo numa cidade (prefeito, vice e vereadores), nas fichas
       de dados/cidades/<UF>/<IBGE>.json (o tse.py só põe o selo nos cargos federais e estaduais)."""
    ps = [p for p, _ in fichas(pasta)]
    b_arq = DADOS / "busca.json"
    busca = [x for x in (ler_json(b_arq, []) or []) if not str(x[0]).startswith(("e26-", "ver-"))]
    ja = {(chave_nome(x[1] or ""), x[3], x[4]) for x in busca}
    novos, repetidos = [], []
    for p in ps:
        if p.get("link") == p["id"]:
            uf = None if p.get("uf") == "BR" else p.get("uf")
            if (chave_nome(p.get("nome") or ""), uf, p.get("partido")) in ja:
                repetidos.append(p["id"])
                continue
            pt, en = cargo_eleito(p)
            novos.append([p["id"], p.get("nome"), pt, uf, p.get("partido"), None, en])
        elif str(p.get("link") or "").startswith("ver-") and p.get("atual"):
            pt, en = cargo_eleito(p)
            onde = re.sub(r"\s*\([A-Z]{2}\)$", "", p["atual"].get("onde") or "") or None
            hoje_c = p["atual"].get("cargo") or "Vereador"
            novos.append([p["link"], p.get("nome"), f"{hoje_c} · {pt[:1].lower() + pt[1:]}", p.get("uf"), p.get("partido"),
                          onde, f"City Councilor · {en}"])
    busca += novos
    busca.sort(key=lambda x: (chave_nome(x[1] or ""), x[0]))
    salvar_json(b_arq, busca)
    if repetidos:
        log(f"  [aviso] fora da busca porque alguém com o mesmo nome, estado e partido já está nela: {repetidos}")
    # selos nas fichas das cidades
    alvo = collections.defaultdict(dict)
    for p in ps:
        m = _MUNICIPAL.match(str(p.get("link") or ""))
        if m:
            alvo[m.group(1)][p["link"]] = selo(p)
    n = 0
    for c_arq in sorted((DADOS / "cidades").glob("*/*.json")):
        sel = alvo.get(c_arq.stem) or {}
        if not sel and "eleicao2026" not in c_arq.read_text(encoding="utf-8"):
            continue
        c = ler_json(c_arq)
        if not isinstance(c, dict):
            continue
        mudou = False
        for q in [c.get("prefeito"), c.get("vice")] + list((c.get("vereadores") or {}).get("membros") or []):
            if not isinstance(q, dict):
                continue
            novo = sel.get(q.get("id"))
            if q.get("eleicao2026") != novo:
                if novo:
                    q["eleicao2026"] = novo
                else:
                    q.pop("eleicao2026", None)
                mudou = True
        if mudou:
            salvar_json(c_arq, sem_mudar_data(c, c_arq))
            n += 1
    return (f"{sum(1 for x in novos if x[0].startswith('e26-'))} perfis novos e "
            f"{sum(1 for x in novos if x[0].startswith('ver-'))} vereadores na busca; selo em {sum(len(v) for v in alvo.values())} "
            f"pessoas das cidades ({n} arquivos mudaram)")


def urls_sitemap(pasta: Path = SAIDA) -> list[tuple[str, str | None]]:
    """[(endereço, data)] dos perfis e26- (quem foi eleito em 2026 e não tem cargo hoje), para o sitemap.xml."""
    return [(f"pessoa.html?id={p['id']}", at) for p, at in fichas(pasta) if p.get("link") == p["id"]]


# ---------------------------------------------------------------- principal
def grava(caminho: Path, obj: dict) -> bool:
    """Grava só se o conteúdo mudou (as datas de consulta não contam)."""
    obj = dict(obj, atualizado=hoje())
    return salvar_json(caminho, sem_mudar_data(obj, caminho))


def main() -> int:
    global HOJE
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hoje", help="simula outra data (AAAA-MM-DD), para testar o que acontece na posse")
    ap.add_argument("--saida", help="pasta de saída (padrão: dados/eleitos)")
    args = ap.parse_args()
    if args.hoje:
        HOJE = args.hoje
    saida = Path(args.saida) if args.saida else SAIDA
    t0 = time.time()
    CACHE_E.mkdir(parents=True, exist_ok=True)
    log(f"Eleitos em {ANO}: quem assume e quando (data usada: {hoje_()})")
    try:
        b26 = tse.Base2026()
        extras = extras_2026()
        vot = votos_2026()
        b22, b18 = tse.Base(2022), tse.Base(2018)
        por_cpf, por_nn, mapa_ue, fed = cargos_de_hoje(b18, b22)
        eleitos = eleitos_2026(b26)
        bens, tipos_bem, data_bens = bens_2026({c["sq"] for c in eleitos})
        nomes_uf = ibge.estados()
    except Exception as e:  # noqa: BLE001
        log(f"[aviso] o TSE (ou a Câmara, o Senado ou o IBGE) não respondeu: {e}. Ficam os arquivos de antes.")
        return 1
    ctx = {"titular": titulares(eleitos), "por_cpf": por_cpf, "por_nn": por_nn, "votos": vot["votos"], "extras": extras,
           "bens": bens, "fonte2t": b26.fonte_2turno}
    todas = [pessoa(c, ctx) for c in eleitos]
    sem_votos = [p["id"] for p in todas if p["votos"] is None]
    if sem_votos:
        log(f"  [aviso] {len(sem_votos)} eleitos sem os votos no arquivo do TSE: {sem_votos[:5]}")
    fontes = {
        "candidaturas": tse.fonte_candidatos(ANO, b26.data, f"Dados Abertos: candidaturas de {ANO} (situação depois da totalização)"),
        "resultados": tse.fonte_resultados(ANO, vot["data"], f"Dados Abertos: resultados de {ANO} (votação nominal por município e zona)"),
        "bens": fonte("TSE", f"Dados Abertos: bens declarados pelas candidaturas de {ANO}", f"{tse.PORTAL}candidatos-{ANO}", data_bens),
        "posse": fontes_posse(),
    }
    saida.mkdir(parents=True, exist_ok=True)
    escritos, apagados = [], []

    def escreve(nome: str, d: dict | None, ps: list[dict]) -> None:
        caminho = saida / f"{nome}.json"
        if d is None:
            if caminho.exists():
                caminho.unlink()
                apagados.append(nome)
            return
        cods = sorted({str(i[0]) for p in ps if p["link"] == p["id"] for i in (p.get("bens") or {}).get("itens") or []})
        if cods:
            d["tiposBem"] = {c: tipos_bem[c] for c in cods if c in tipos_bem}
        d["fontes"] = fontes
        if grava(caminho, d):
            escritos.append(nome)

    por_uf = collections.defaultdict(list)
    for p in todas:
        por_uf[p["uf"]].append(p)
    continuam = senado_continua(fed, todas, b22)
    turnos = {str(c["turno"]): c["dt"] for c in eleitos if c.get("dt")}
    br = arquivo_br(todas, continuam, b22)
    if br:
        br["turnos"] = turnos
    escreve("BR", br, por_uf.get("BR", []))
    for uf in tse.UFS:
        d = arquivo_uf(uf, por_uf.get(uf, []), nomes_uf.get(uf), continuam)
        if d:
            d["turnos"] = turnos
        escreve(uf, d, por_uf.get(uf, []))
    try:
        if grava(saida / "municipal.json", arquivo_municipal(todas, mapa_ue, saida, fontes)):
            escritos.append("municipal")
    except Exception as e:  # noqa: BLE001
        log(f"[aviso] dados/eleitos/municipal.json: {e}; fica o de antes")
    cont = collections.Counter((p["tipo"], p["chegada"]) for p in todas)
    for tipo in ("pres", "vp", "gov", "vgov", "sen", "supl1", "supl2", "dep", "dest"):
        n = {ch: cont[(tipo, ch)] for ch in ("reeleicao", "troca", "novo")}
        log(f"  {tipo}: {sum(n.values())} eleitos ({n['reeleicao']} no mesmo cargo, {n['troca']} com outro cargo hoje, "
            f"{n['novo']} sem cargo eletivo hoje)")
    log(f"  perfis novos (e26-): {sum(1 for p in todas if p['link'] == p['id'])}; com perfil que já existe: "
        f"{sum(1 for p in todas if p['link'] != p['id'])} (deixaram o cargo para concorrer: {sum(1 for p in todas if p.get('antes'))})")
    log(f"dados/eleitos: {len(escritos)} arquivos gravados ({', '.join(escritos) or 'nenhum'}), {len(apagados)} apagados "
        f"({', '.join(apagados) or 'nenhum'}), em {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
