"""O que cada prefeitura fez: leis sancionadas e vetos, contados no Diário Oficial dos municípios (fase 4 da rodada
"nenhum Em breve").

Para as cidades em que o mapa (dados/municipios/<UF>.json, prefeitura.diarioOficial) aponta um Diário Oficial cuja
plataforma deixa listar as matérias por título e por data, conta as leis publicadas pela prefeitura desde o começo do
mandato de quem governa hoje (1º/1/2025, ou o "desde" da ficha da cidade) e, quando dá, os vetos. Só publica a contagem
de uma cidade quando ela é segura (a numeração das leis do período quase não tem buracos, começa logo depois da última
lei de antes do período e vai até perto de hoje); senão a cidade fica em "fora", com o motivo. Regras em _atos.py.

Plataformas (uma leitura por servidor, em paralelo; cada uma com o seu módulo):
- SIGPub (www.diariomunicipal.com.br/<associação>): _diario_sigpub.py (lido por associação, mês a mês);
- Diário Oficial MS da Assomasul (www.diariooficialms.com.br): _diario_assomasul.py (cidade por cidade);
- DOSP / Imprensa Oficial Municipal (a seção "Leis" de cada cidade): _diario_listas.py;
- ADiários (sites de prefeituras com /diariooficial.php): a página de leis do próprio site (/leis.php), _diario_listas.py.
  A mesma página de leis (portal oficial de legislação do município) é lida também nas cidades em que o Diário é de
  outra plataforma (ou não foi achado): o link vem da página inicial do site da prefeitura, achado pelo mapa
  (.cache/municipios/cidades/, só leitura). Do mesmo jeito, a página de legislação dos sites do fornecedor Instar
  (/portal/leis_decretos, com filtro por categoria e ano) e Digitaliza (/legislacoes/..., MG), _diario_listas.py, e o
  portal de legislação do CESPRO (cespro.com.br, ~140 municípios, quase todos do RS; busca por tipo de norma e ano),
  _diario_cespro.py. Quando mais de uma fonte dá a contagem segura, vale a que tem os vetos; senão a mais completa
  (menos números de lei faltando); empate: o Diário.

Saída: dados/prefeituras/<UF>.json = {uf, atualizado, fontes, nota, nota_en, cidades: {<IBGE>: {executivo: {...}}},
fora: {<IBGE>: {motivo, motivo_en, codigo, plataforma, diario, ..., url, tipo, nome, nome_en}}}. O bloco "executivo" segue
a seção 2 do contrato da rodada (o montar.py junta na ficha do prefeito; nas cidades em que o SAPL da Câmara já tem o
bloco, vale o do SAPL). Em "fora", o link do quadro "Onde ver mais": url (a lista que o robô leu), tipo ("diario" ou
"legislacao") e o rótulo (nome, nome_en).

Falhas de rede e bloqueios (o robô do GitHub): a fonte que não pôde ser lida deixa a cidade pendente, com o que já está
publicado; uma leitura nova só acrescenta leis; uma cidade contada só vai para "fora" quando todas as fontes foram lidas por
inteiro e a regra deixou de valer (ver montar e testes/diarios_falhas.py).

Educado (scripts/municipios/_rede.py): robots.txt e Crawl-delay de cada site; um pedido por vez a cada servidor (o
SIGPub, com ~1.500 cidades num servidor só, com 1,5 s entre pedidos; 1 s entre sites diferentes do mesmo servidor); limite
de tempo (--minutos): o que não der fica para a próxima rodada, que continua de onde parou, e nada é publicado pela metade.
Cache em .cache/municipios/diarios/atos/ (o resto de .cache/municipios/diarios/ é do mapa e não é mexido).

Uso:
  python scripts/municipios/diarios.py                 todos os estados (sem cache: horas; use --minutos)
  python scripts/municipios/diarios.py RN PB           só estes estados
  python scripts/municipios/diarios.py --rodizio       os estados do dia da semana (cada um 1 vez por semana) e, se
                                                       sobrar tempo, as primeiras cargas que ainda faltam
  python scripts/municipios/diarios.py --montar        só remonta dados/prefeituras/ a partir do cache (sem rede)
  python scripts/municipios/diarios.py --ibge 2406205  uma cidade: mostra a contagem e os números de lei (sem rede);
                                                       com --detalhe, cada matéria e como foi entendida
Opções: --minutos M (padrão 40), --so sigpub|assomasul|dosp|adiarios|leis|instar|digitaliza|cespro (só uma plataforma),
--max-paginas N (teste).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import threading
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent))
from comum import CACHE, DADOS, fonte, hoje, ler_json, log, salvar_json, sem_mudar_data  # noqa: E402
from mandatos import extenso, vigente  # noqa: E402

import _atos as A  # noqa: E402
import _diario_assomasul as AS  # noqa: E402
import _diario_cespro as CE  # noqa: E402
import _diario_listas as DL  # noqa: E402
import _diario_sigpub as SG  # noqa: E402
import _rede  # noqa: E402

PASTA = CACHE / "municipios" / "diarios" / "atos"
SAIDA = DADOS / "prefeituras"
MAPA = DADOS / "municipios"
RODADAS = PASTA / "rodadas.json"
ROTAS = PASTA / "rotas.json"
UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ",
       "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]
ANTES_DIAS = 92          # lê também uns 3 meses antes do período: o último número de lei de antes do mandato
MINUTOS = 40

PLAT_SIGPUB = "SIGPub (diariomunicipal.com.br)"
PLAT_ASSOMASUL = "Diário Oficial MS (Assomasul)"
PLAT_DOSP = DL.DospCidade.plataforma
PLAT_ADIARIOS = DL.AdiariosCidade.plataforma
PLAT_LEIS = "Página de leis do site da prefeitura (ADiários)"
PLAT_INSTAR = "Página de leis do site da prefeitura (Instar)"
PLAT_DIGITALIZA = "Página de leis do site da prefeitura (Digitaliza)"
PLAT_CESPRO = "Portal de legislação do município (CESPRO)"
# plataformas com uma lista de leis por cidade: (classe, como foi buscado pt/en, nome da fonte pt/en; None = o nome do
# Diário no mapa)
LISTAS = {
    PLAT_DOSP: (DL.DospCidade, "na lista de leis do Diário (a seção “Leis”)", "in the Gazette's list of laws (the “Leis” "
                "section)", None, None),
    PLAT_ADIARIOS: (DL.AdiariosCidade, "na página de leis do site (filtro por período)", "on the website's laws page "
                    "(filtered by date)", "site oficial da prefeitura", "city government's official website"),
    # a mesma página de leis, nas cidades cujo Diário é de outra plataforma (ou não foi achado): o portal oficial de
    # legislação do município também é fonte oficial (contrato, seção 2)
    PLAT_LEIS: (DL.AdiariosCidade, "na página de leis do site (filtro por período)", "on the website's laws page "
                "(filtered by date)", "site oficial da prefeitura", "city government's official website"),
    PLAT_INSTAR: (DL.InstarCidade, "na página de legislação do site (filtro por categoria de lei e por ano)",
                  "on the website's legislation page (filtered by law category and year)", "site oficial da prefeitura",
                  "city government's official website"),
    PLAT_CESPRO: (CE.CesproCidade, "na busca por tipo de norma e por ano", "searching by type of norm and year",
                  "portal de legislação do município (CESPRO)", "municipality's legislation portal (CESPRO)"),
    PLAT_DIGITALIZA: (DL.DigitalizaCidade, "na página de legislação do site (tipos de lei, filtro por ano)",
                      "on the website's legislation page (law types, filtered by year)", "site oficial da prefeitura",
                      "city government's official website"),
}
# a página de leis do site, quando o Diário não dá a contagem: (plataforma, chave em ler_mapa)
ALTERNATIVAS = [(PLAT_LEIS, "leis"), (PLAT_INSTAR, "instar"), (PLAT_DIGITALIZA, "digitaliza"), (PLAT_CESPRO, "cespro")]
ALT_CHAVE = {p: k for p, k in ALTERNATIVAS}


def _d(iso: str) -> tuple[str, str]:
    return extenso(iso)


def periodo_leitura() -> tuple[str, str, str]:
    """(hoje, começo do mandato dos prefeitos, primeiro dia lido: ~3 meses antes)."""
    h = hoje()
    inicio = vigente("prefeito")["inicio"]
    desde = (dt.date.fromisoformat(inicio) - dt.timedelta(days=ANTES_DIAS)).isoformat()[:8] + "01"
    return h, inicio, desde


# ---------------------------------------------------------------------------------------------------- textos
# rótulo do link "Onde ver mais" das cidades que ficam fora (pt, en): o Diário pelo nome oficial (o mesmo nos dois idiomas)
ROTULO_PAGINA = ("Página de leis do site oficial da prefeitura", "Laws page of the city government's official website")
ROTULO_CESPRO = ("Portal de legislação do município (CESPRO)", "Municipal legislation portal (CESPRO)")


def rotulo_diario(nome: str) -> str:
    """Nome curto do Diário: "Diário Oficial dos Municípios (Federação das Associações de Municípios da Paraíba - FAMUP)"
    → "Diário Oficial dos Municípios (FAMUP)"; sem sigla, o nome inteiro."""
    m = re.match(r"^(.*?)\s*\((.*)\)\s*$", nome or "")
    if not m:
        return nome
    base, dentro = m.group(1), m.group(2)
    sigla = re.search(r"\(([^()]+)\)\s*$", dentro)          # "(FEDERAÇÃO ... (FEMURN))"
    if sigla:
        return f"{base} ({sigla.group(1).strip()})"
    for parte in re.split(r"\s+[-–]\s+", dentro):           # "(AMP - Associação ...)", "(Associação ... – AMA)"
        if re.fullmatch(r"[A-Z]{2,}(?:-[A-Z]{2})?", parte.strip()):
            return f"{base} ({parte.strip()})"
    return nome


def _n(n: int, um_pt: str, varios_pt: str, um_en: str, varios_en: str) -> tuple[str, str]:
    return (f"{n} {um_pt}" if n == 1 else f"{n} {varios_pt}"), (f"{n} {um_en}" if n == 1 else f"{n} {varios_en}")


def motivo_txt(cod: str, r: dict, inicio: str, fim: str, dados: dict | None = None) -> tuple[str, str]:
    """Por que a cidade ficou fora, em uma frase (português e inglês), sem promessa."""
    site = bool(dados and dados.get("nome_en"))     # a lista é a página de leis do site da prefeitura, não um Diário
    dd = dados or {}
    onde_pt = dd.get("onde_fora_pt") or ("na página de leis do site da prefeitura" if site else "neste Diário Oficial")
    onde_en = dd.get("onde_fora_en") or ("on the laws page of the city government's website" if site
                                         else "in this Official Gazette")
    de_en = dd.get("de_fora_en") or ("from the laws page of the city government's website" if site
                                     else "from this Official Gazette")
    ini_pt, ini_en = _d(inicio)
    fim_pt, fim_en = _d(fim)
    ult_pt, ult_en = _d(r.get("ultima") or fim)
    prim_pt, prim_en = _d(r.get("primeira") or inicio)
    if cod == "nenhuma":
        oque_pt, oque_en = ("nenhuma lei", "no law") if site else ("nenhuma matéria da prefeitura com título de lei",
                                                                   "no item from the city government titled as a law")
        return (f"A prefeitura não publica as leis {onde_pt}: de {ini_pt} até {fim_pt}, {oque_pt}.",
                f"The city government does not publish its laws {onde_en}: from {ini_en} to {fim_en}, {oque_en}.")
    if cod == "poucas":
        q_pt, q_en = _n(r.get("leis") or 0, "lei", "leis", "law", "laws")
        return (f"Só {q_pt} da prefeitura {onde_pt} de {ini_pt} até {fim_pt}: poucas para conferir se a lista está completa.",
                f"Only {q_en} from the city government {onde_en} from {ini_en} to {fim_en}: too few to check whether the "
                "list is complete.")
    if cod == "parou":
        if site:
            return (f"A lei mais nova {onde_pt} é de {ult_pt}: a página parece ter parado de ser atualizada.",
                    f"The newest law {onde_en} is from {ult_en}: the page seems to have stopped being updated.")
        return (f"A lei mais nova da prefeitura {onde_pt} é de {ult_pt}: a prefeitura parece ter passado a publicar as leis "
                "em outro lugar.",
                f"The newest law from the city government {onde_en} is from {ult_en}: the city seems to have started "
                "publishing its laws somewhere else.")
    if cod == "buracos":
        return (f"Faltam {onde_pt} {r.get('falta')} dos {r.get('faixa')} números de lei do período (mais de 15%): a lista não "
                "está completa.",
                f"{r.get('falta')} of the {r.get('faixa')} law numbers in the period are missing {de_en} (more than 15%): "
                "the list is not complete.")
    if cod == "buraco_grande":
        return (f"Falta {onde_pt} uma sequência de {r.get('maior')} leis seguidas do período: a lista não está completa.",
                f"A run of {r.get('maior')} consecutive laws from the period is missing {de_en}: the list is not complete.")
    if cod == "inicio":
        return (f"A primeira lei do mandato {onde_pt} é de {prim_pt}, e não dá para conferir se as leis de antes dela estão "
                f"ali: a numeração não começa logo depois da última lei de antes de {ini_pt}.",
                f"The first law of the term {onde_en} is from {prim_en}, and it is not possible to check whether the laws "
                f"before it are there: the numbering does not start right after the last law before {ini_en}.")
    # sem_numero
    q_pt, q_en = _n(r.get("sem_numero") or 0, "lei do período aparece", "leis do período aparecem",
                    "law in the period appears", "laws in the period appear")
    return (f"{onde_pt[0].upper() + onde_pt[1:]}, {q_pt} sem o número da lei no título, e o texto não pôde ser lido: sem o "
            "número, não dá para conferir se a lista está completa.",
            f"{onde_en[0].upper() + onde_en[1:]}, {q_en} without the law number in the title, and the text could not be read: "
            "without the number, it is not possible to check whether the list is complete.")

def nota(dados: dict, inicio: str, fim: str, r: dict, v: dict) -> tuple[str, str, str, str]:
    """A "nota" do bloco executivo: como foi contado, em frases curtas. Devolve (leis em português, leis em inglês, vetos em
    português, vetos em inglês): a parte dos vetos é a última frase; o bloco guarda as duas juntas em "nota" e cada uma à
    parte em "notaLeis" e "notaVetos" (o perfil junta esta conta com a do SAPL da Câmara quando o SAPL só tem os vetos)."""
    ini_pt, ini_en = _d(inicio)
    fim_pt, fim_en = _d(fim)
    nd = dados["nome_diario"]
    onde_pt, onde_en = dados.get("onde_pt", "no Diário"), dados.get("onde_en", "in the Gazette")
    no_en = f"on the {dados['nome_en']}" if dados.get("nome_en") else f"in the {nd} (an Official Gazette)"
    q_pt, q_en = _n(r["leis"], "lei ordinária ou complementar", "leis ordinárias e complementares",
                    "ordinary or complementary law", "ordinary and complementary laws")
    pt = [f"Contamos as leis que a prefeitura publicou no {nd}, {dados['como_pt']}, de {ini_pt} a {fim_pt}: {q_pt}, cada "
          "número uma vez (republicações, retificações, erratas e anexos não contam de novo; projetos de lei, decretos e avisos "
          "que só citam uma lei ficam fora)."]
    en = [f"We counted the laws the city government published {no_en}, {dados['como_en']}, from {ini_en} to {fim_en}: "
          f"{q_en}, each number once (republications, corrections and annexes are not counted again; bills, decrees and "
          "notices that only mention a law are left out)."]
    if r.get("promulgadas"):
        p_pt, p_en = _n(r["promulgadas"], "lei", "leis", "law", "laws")
        if dados.get("separa_camara"):
            pt.append(f"Ficam fora {p_pt} que a Câmara Municipal publicou (promulgadas por ela).")
            en.append(f"{p_en[0].upper() + p_en[1:]} published by the City Council itself (promulgated by it) "
                      f"{'is' if r['promulgadas'] == 1 else 'are'} left out.")
        else:
            pt.append(f"Ficam fora {p_pt} que o título diz que foram promulgadas pela Câmara.")
            en.append(f"{p_en[0].upper() + p_en[1:]} whose title says they were promulgated by the City Council "
                      f"{'is' if r['promulgadas'] == 1 else 'are'} left out.")
    elif dados.get("separa_camara"):
        pt.append("As poucas leis que a própria Câmara promulga só ficam fora quando é ela que as publica.")
        en.append("The few laws the City Council promulgates itself are left out only when the Council publishes them.")
    if not dados.get("separa_camara"):
        pt.append(dados.get("camara_pt") or "A lista não diz quem publicou cada lei: as poucas leis que a própria Câmara "
                  "promulga só ficam fora quando o título diz “promulgada”.")
        en.append(dados.get("camara_en") or "The list does not say who published each law: the few laws the City Council "
                  "promulgates itself are left out only when the title says “promulgada” (promulgated).")
    if r.get("falta"):
        pt.append(f"Não aparecem {onde_pt} {r['falta']} dos {r['faixa']} números de lei do período.")
        en.append(f"{r['falta']} of the {r['faixa']} law numbers in the period do not appear {onde_en}.")
    if r.get("fora_seq"):
        f_pt, f_en = _n(r["fora_seq"], "lei com número fora da sequência principal (erro de digitação ou outra numeração) "
                        "não entra", "leis com número fora da sequência principal (erro de digitação ou outra numeração) "
                        "não entram", "law numbered outside the main sequence (a typo or a separate numbering) is not",
                        "laws numbered outside the main sequence (a typo or a separate numbering) are not")
        pt.append(f"{f_pt} na conta.")
        en.append(f"{f_en} counted.")
    if r.get("sem_numero"):
        s_pt, s_en = _n(r["sem_numero"], "publicação de lei sem o número no título não entra",
                        "publicações de lei sem o número no título não entram",
                        "law publication without the number in the title is not",
                        "law publications without the number in the title are not")
        pt.append(f"{s_pt} na conta.")
        en.append(f"{s_en} counted.")
    if r.get("sem_data"):
        pt.append(dados.get("sem_data_pt") or "A data de cada lei é a do título; quando o título não traz, vale o ano do "
                  "número ou a data da publicação.")
        en.append(dados.get("sem_data_en") or "Each law's date is the one in its title; when the title has none, the year "
                  "in its number or the publication date is used.")
    if v.get("ok"):
        det_pt = det_en = ""
        if v.get("totais", 0) + v.get("parciais", 0) == v["vetos"]:
            t_, p_ = v.get("totais", 0), v.get("parciais", 0)
            det_pt = f" ({t_} {'total' if t_ == 1 else 'totais'} e {p_} {'parcial' if p_ == 1 else 'parciais'}, pelo título)"
            det_en = f" ({t_} full and {p_} partial, according to the title)"
        vv_pt, vv_en = _n(v["vetos"], "veto", "vetos", "veto", "vetoes")
        pt.append(f"Vetos: {'o' if v['vetos'] == 1 else 'os'} {vv_pt} que a prefeitura publicou no Diário no período, "
                  f"numerados sem buracos{det_pt}.")
        en.append(f"Vetoes: the {vv_en} the city government published in the Gazette in the period, numbered with no "
                  f"gaps{det_en}.")
    elif dados.get("fontes_veto"):
        pt.append("O número de vetos fica fora: o veto é mandado à Câmara Municipal e a prefeitura não publica no Diário "
                  "todos os vetos com uma numeração que dê para conferir.")
        en.append("The number of vetoes is left out: a veto is sent to the City Council, and the city government does not "
                  "publish all of them in the Gazette with numbering that can be checked.")
    else:
        pt.append("O número de vetos fica fora: o veto é mandado à Câmara Municipal e esta lista só traz leis.")
        en.append("The number of vetoes is left out: a veto is sent to the City Council, and this list only has laws.")
    return " ".join(pt[:-1]), " ".join(en[:-1]), pt[-1], en[-1]

# ---------------------------------------------------------------------------------------------------- mapa
def ler_mapa(ufs: list[str]) -> dict[str, dict]:
    """{IBGE: {"uf", "diario": {...}, "leis", "instar", "cespro", "digitaliza"}} das cidades destes estados com Diário
    Oficial no mapa ou com a página de leis de um fornecedor conhecido no site da prefeitura (ver paginas_de_leis).

    As rotas que dão para ler ficam guardadas (rotas.json, no cache): se o mapa deixa de achar uma delas numa rodada
    (site fora do ar ou bloqueando o robô do mapa), a de antes continua valendo — a falta de um link não tira do ar a
    contagem de uma cidade. Se a prefeitura mudou mesmo de Diário, a lista antiga para de receber leis e a regra da lei
    mais nova (até 120 dias) põe a cidade em "fora", com o motivo."""
    memoria = ler_json(ROTAS, {}) or {}
    mudou = False
    out = {}
    for uf in ufs:
        d = ler_json(MAPA / f"{uf}.json") or {}
        cidades = d.get("cidades") or {}
        # as rotas também ficam no arquivo publicado do estado, que vai para o GitHub com ele: o robô começa com o cache
        # vazio e o mapa dele pode não ter o link "Legislação" das prefeituras cujo site bloqueou o robô
        publicadas = rotas_publicadas(uf)
        todas = set(cidades) | set(publicadas) | {i for i, m in memoria.items() if m.get("uf") == uf}
        for ibge in sorted(todas):
            c = cidades.get(ibge) or {}
            do = ((c.get("prefeitura") or {}).get("diarioOficial")) or {}
            leis, instar, cespro, digitaliza = paginas_de_leis(ibge, uf)
            atual = {"diario": do if plataforma_de(do) else None, "leis": leis, "instar": instar, "cespro": cespro,
                     "digitaliza": digitaliza}
            antes = {**(publicadas.get(ibge) or {}), **(memoria.get(ibge) or {})}
            rota = {k: v or antes.get(k) for k, v in atual.items()}
            guardar = {"uf": uf, **{k: v for k, v in rota.items() if v}}
            if len(guardar) > 1 and guardar != memoria.get(ibge):
                memoria[ibge] = guardar
                mudou = True
            if do.get("plataforma") or len(guardar) > 1:
                out[ibge] = {"uf": uf, "diario": rota["diario"] or do, "leis": rota["leis"], "instar": rota["instar"],
                             "cespro": rota["cespro"], "digitaliza": rota["digitaliza"]}
    if mudou:
        PASTA.mkdir(parents=True, exist_ok=True)
        ROTAS.write_text(json.dumps(memoria, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    return out


def rotas_publicadas(uf: str) -> dict:
    """{IBGE: rota} guardadas no arquivo publicado do estado (dados/prefeituras/<UF>.json, chave "rotas")."""
    return (ler_json(SAIDA / f"{uf}.json") or {}).get("rotas") or {}


def rota_de(info: dict) -> dict:
    """A rota de uma cidade para guardar no arquivo publicado: o Diário (só nas plataformas que dão para ler) e as
    páginas de leis / o portal de legislação."""
    r = {k: info[k] for k in ("leis", "instar", "cespro", "digitaliza") if info.get(k)}
    if plataforma_de(info.get("diario") or {}):
        r["diario"] = {k: v for k, v in info["diario"].items() if k in ("nome", "url", "plataforma", "entidade")}
    return r


def paginas_de_leis(ibge: str, uf: str) -> tuple[str | None, str | None, str | None, str | None]:
    """O link "Legislação" que o mapa achou na página inicial do site da prefeitura (cache do mapear.py, só leitura):
    (endereço do site, quando é a página de leis do fornecedor ADiários (<site>/leis.php); endereço do site, quando é a
    página de legislação do fornecedor Instar (<site>/portal/leis_decretos); código do município, quando é o portal de
    legislação do CESPRO; endereço do site, quando é a página de legislação do fornecedor Digitaliza
    (<site>/legislacoes/...))."""
    c = ler_json(CACHE / "municipios" / "cidades" / uf / f"{ibge}.json") or {}
    link = (((c.get("prefeitura") or {}).get("legislacao")) or "").strip()
    m = re.match(r"(https?://[^/]+)/leis\.php(?:$|\?)", link)
    return ((m.group(1) if m else None), DL.InstarCidade.base_de(link), CE.CesproCidade.codigo_de(link),
            DL.DigitalizaCidade.base_de(link))


def assoc_sigpub(do: dict) -> str | None:
    if do.get("plataforma") != PLAT_SIGPUB or not do.get("entidade"):
        return None
    m = re.search(r"diariomunicipal\.com\.br/([^/?#]+)", do.get("url") or "")
    return m.group(1) if m else None


def inicio_prefeito(ibge: str, uf: str, inicio: str) -> tuple[str, dict]:
    c = ler_json(DADOS / "cidades" / uf / f"{ibge}.json") or {}
    desde = ((c.get("prefeito") or {}).get("desde") or "")[:10]
    return (max(inicio, desde) if desde else inicio), c


def grupos_rodizio() -> list[list[str]]:
    """7 grupos de estados com tamanhos parecidos (um por dia da semana): o mesmo jeito do mapear.py."""
    cidades = ler_json(DADOS / "cidades.json", []) or []
    n = {}
    for _, _, uf in cidades:
        n[uf] = n.get(uf, 0) + 1
    grupos = [[] for _ in range(7)]
    soma = [0] * 7
    for uf in sorted(n, key=lambda u: (-n[u], u)):
        i = soma.index(min(soma))
        grupos[i].append(uf)
        soma[i] += n[uf]
    grupos[min(range(7), key=lambda i: soma[i])].append("DF")
    return grupos


# ---------------------------------------------------------------------------------------------------- SIGPub
class SigpubCidades:
    """Liga as matérias lidas de uma associação às cidades (pela entidade)."""

    def __init__(self, assoc: SG.Associacao):
        self.a = assoc
        ents = assoc.estado.get("entidades") or {}
        self.nome_ent = {k: A.norm(v) for k, v in ents.items()}
        self._por_nome: dict[str, list] | None = None
        self._vetos: dict[str, list] | None = None

    def _indexar(self):
        if self._por_nome is not None:
            return
        self._por_nome, self._vetos = {}, {}
        for cod, (tit, ent, org, circ) in self.a.todos_itens("lei").items():
            self._por_nome.setdefault(A.norm(ent), []).append((cod, tit, org, circ, ent))
        for cod, (tit, ent, org, circ) in self.a.todos_itens("veto").items():
            self._vetos.setdefault(A.norm(ent), []).append((cod, tit, org, circ, ent))

    def camaras_da_cidade(self, nome_cidade: str) -> set[str]:
        """Nomes (normalizados) das entidades "Câmara Municipal de <cidade>" da associação."""
        alvo = A.norm(nome_cidade)
        out = set()
        for n in self.nome_ent.values():
            m = re.match(r"^CAMARA(?: MUNICIPAL)?(?: DE VEREADORES)?(?: DE| DO| DA| DOS| DAS)?\s+(.+?)(?:\s*[-/]\s*[A-Z]{2})?$", n)
            if m and m.group(1).strip() == alvo:
                out.add(n)
        return out

    def itens_cidade(self, entidade: str, nome_cidade: str, prazo: float, ler_materias: bool = True,
                     fim: str | None = None) -> tuple[list, list, int]:
        """(itens de lei, itens de veto, matérias sem número que faltou ler) da prefeitura (e da Câmara da cidade),
        publicados até `fim` (o último dia lido por inteiro)."""
        self._indexar()
        nome = self.nome_ent.get(entidade)
        if not nome:
            return [], [], 0
        fim = fim or "9999"
        itens, vetos, faltou = [], [], 0
        for chave, camara_ent in [(nome, False)] + [(c, True) for c in sorted(self.camaras_da_cidade(nome_cidade))]:
            for cod, tit, org, circ, ent in self._por_nome.get(chave, []):
                if circ > fim:
                    continue
                lei = A.ler_titulo(tit)
                if not lei or lei.get("tipo") != "lei":
                    continue
                camara = camara_ent or A.eh_camara(org)
                if lei.get("num") is None:
                    if camara_ent:
                        continue
                    # o texto da matéria (cache); sem prazo (montar), só o que já foi lido
                    m = self.a.materia(cod, prazo if ler_materias else 0)
                    if m and m.get("lei"):
                        lei = dict(m["lei"], lc=lei["lc"] or m["lei"].get("lc"),
                                   promulgada=lei.get("promulgada") or m["lei"].get("promulgada"))
                    elif m is None and circ >= self.a.desde:
                        faltou += 1
                itens.append({"lei": lei, "circ": circ, "camara": camara, "id": cod})
            if not camara_ent:
                for cod, tit, org, circ, ent in self._vetos.get(chave, []):
                    if circ > fim:
                        continue
                    v = A.ler_titulo(tit)
                    if v and v.get("tipo") == "veto":
                        vetos.append({"veto": v, "circ": circ, "id": cod})
        return itens, vetos, faltou


class LeitorSigpub:
    plataforma = PLAT_SIGPUB

    def __init__(self, rede, h: str, desde: str):
        self.rede, self.h, self.desde = rede, h, desde
        self.cache: dict[str, SigpubCidades | None] = {}

    def assoc(self, slug: str) -> SigpubCidades | None:
        if slug not in self.cache:
            a = SG.Associacao(self.rede, slug, PASTA, self.h, self.desde)
            self.cache[slug] = SigpubCidades(a) if a.completo() else None
        return self.cache[slug]

    def cidade(self, ibge: str, do: dict, nome: str, ini: str, prazo: float, ler_materias: bool) -> dict:
        slug = assoc_sigpub(do)
        sc = self.assoc(slug)
        if sc is None:
            return {"pendente": True}
        fim = sc.a.data_leitura() or self.h
        itens, vetos, faltou = sc.itens_cidade(do["entidade"], nome, prazo, ler_materias, fim)
        if faltou:
            return {"pendente": True, "faltam_materias": faltou}
        ini_pt, _ = _d(ini)
        fim_pt, _ = _d(fim)
        nd = do.get("nome") or "Diário Oficial dos Municípios"
        f_lei = fonte(nd, f"Busca de matérias da prefeitura de {nome} com “lei” no título, de {ini_pt} a {fim_pt}",
                      SG.url_pessoa(slug, do["entidade"], "lei", ini, fim), fim)
        f_veto = fonte(nd, f"Busca de matérias da prefeitura de {nome} com “veto” no título, de {ini_pt} a {fim_pt}",
                       SG.url_pessoa(slug, do["entidade"], "veto", ini, fim), fim)
        return {"itens": itens, "vetos": vetos, "fim": fim, "nome_diario": nd, "fontes_lei": [f_lei], "fontes_veto": [f_veto],
                "como_pt": "na busca por matérias com “lei” no título",
                "como_en": "searching for items with “lei” (law) in the title", "separa_camara": True,
                "fonte_arquivo": (nd, f"{SG.BASE}{slug}/pesquisar"),
                "tipo": "diario", "rotulo_pt": rotulo_diario(nd), "rotulo_en": rotulo_diario(nd)}


# ---------------------------------------------------------------------------------------------------- Assomasul (MS)
class LeitorAssomasul:
    plataforma = PLAT_ASSOMASUL

    def __init__(self, rede, h: str, desde: str):
        self.rede, self.h, self.desde = rede, h, desde

    def cidade(self, ibge: str, do: dict, nome: str, ini: str, prazo: float, ler_materias: bool) -> dict:
        c = AS.Cidade(self.rede, do["entidade"], PASTA, self.h, self.desde)
        if not c.completo():
            return {"pendente": True}
        fim = c.data_leitura() or self.h
        itens, vetos = [], []
        for cod, (tit, ent, org, circ) in c.itens("lei").items():
            if circ > fim:
                continue
            lei = A.ler_titulo(tit)
            if lei and lei.get("tipo") == "lei":
                itens.append({"lei": lei, "circ": circ, "camara": False, "id": cod})
        for cod, (tit, ent, org, circ) in c.itens("veto").items():
            v = A.ler_titulo(tit)
            if v and v.get("tipo") == "veto" and circ <= fim:
                vetos.append({"veto": v, "circ": circ, "id": cod})
        ini_pt, _ = _d(ini)
        fim_pt, _ = _d(fim)
        nd = "Diário Oficial MS (Assomasul)"
        pag = fonte(nd, f"Filtro avançado: município de {nome}, título “lei”, de {ini_pt} a {fim_pt}", AS.PAGINA_HUMANA, fim)
        api = fonte(nd, f"Lista do filtro avançado (JSON): município de {nome}, título “lei”, de {ini_pt} a {fim_pt}",
                    AS.url_filtro(do["entidade"], "lei", ini, fim, 0, 100), fim)
        pag_v = fonte(nd, f"Filtro avançado: município de {nome}, título “veto”, de {ini_pt} a {fim_pt}", AS.PAGINA_HUMANA, fim)
        api_v = fonte(nd, f"Lista do filtro avançado (JSON): município de {nome}, título “veto”, de {ini_pt} a {fim_pt}",
                      AS.url_filtro(do["entidade"], "veto", ini, fim, 0, 100), fim)
        return {"itens": itens, "vetos": vetos, "fim": fim, "nome_diario": nd, "fontes_lei": [pag, api],
                "fontes_veto": [pag_v, api_v],
                "como_pt": "no filtro avançado do site (município, título “lei” e período)",
                "como_en": "using the site's advanced filter (city, title “lei” and dates)", "separa_camara": False,
                "fonte_arquivo": ("Associação dos Municípios de Mato Grosso do Sul (Assomasul)", AS.PAGINA_HUMANA),
                "tipo": "diario", "rotulo_pt": nd, "rotulo_en": nd}


# ---------------------------------------------------------------------------------------------------- listas por cidade
def chave_lista(plat: str, do: dict) -> str | None:
    if plat == PLAT_DOSP:
        return DL.DospCidade.slug_de(do.get("url") or "")
    if plat == PLAT_ADIARIOS:
        return DL.AdiariosCidade.base_de(do.get("url") or "")
    if plat == PLAT_LEIS:
        return do.get("leis")
    if plat == PLAT_INSTAR:
        return do.get("instar")
    if plat == PLAT_CESPRO:
        return do.get("cespro")
    if plat == PLAT_DIGITALIZA:
        return do.get("digitaliza")
    return None


class LeitorLista:
    """Plataformas em que cada cidade tem uma lista só de leis (a seção "Leis" do Diário ou a página de leis do site)."""

    def __init__(self, plat: str, rede, h: str, desde: str):
        self.plat, self.rede, self.h, self.desde = plat, rede, h, desde
        self.classe, self.como_pt, self.como_en, self.nome_pt, self.nome_en = LISTAS[plat]

    def cidade(self, ibge: str, do: dict, nome: str, ini: str, prazo: float, ler_materias: bool) -> dict:
        c = self.classe(self.rede, chave_lista(self.plat, do), PASTA, self.h, self.desde)
        if not c.completo():
            return {"pendente": True}
        if not c.tem_lista():
            return {"sem_lista": True}
        fim = c.data_leitura() or self.h
        itens = []
        ler = getattr(self.classe, "ler_titulo", None) or A.ler_titulo_lista
        for cod, (tit, ent, org, circ) in c.itens("lei").items():
            if circ > fim:
                continue
            lei = ler(tit)
            if lei and lei.get("tipo") == "lei":
                itens.append({"lei": lei, "circ": circ, "camara": A.eh_camara(org), "id": cod})
        ini_pt, _ = _d(ini)
        fim_pt, _ = _d(fim)
        nd = self.nome_pt or do.get("nome") or "Diário Oficial do Município"
        veiculo = f"Prefeitura de {nome}" if self.nome_pt else nd
        if self.plat == PLAT_CESPRO:
            veiculo = f"Legislação do Município de {nome} (CESPRO)"
        f_lei = []
        if hasattr(c, "fontes_lista"):
            # uma lista por categoria de lei, nos anos do período
            a1, a2 = ini[:4], fim[:4]
            anos = a1 if a1 == a2 else f"{a1} a {a2}"
            f_lei = [fonte(veiculo, f"Legislação da prefeitura de {nome}: categoria “{rot}”, leis de {anos}", url, fim)
                     for rot, url in c.fontes_lista(ini, fim)]
            if self.plat == PLAT_CESPRO:
                f_lei = [fonte(veiculo, f"Busca da legislação de {nome}: tipo “{rot}”, normas de {anos}", url, fim)
                         for rot, url in c.fontes_lista(ini, fim)]
            if self.plat == PLAT_DIGITALIZA:
                f_lei = [fonte(veiculo, f"Legislação da prefeitura de {nome}: tipo “{rot}” (a tabela tem filtro por ano)",
                               url, fim) for rot, url in c.fontes_lista(ini, fim)]
        if not f_lei:
            f_lei = [fonte(veiculo, f"Lista de leis da prefeitura de {nome} (de {ini_pt} a {fim_pt})",
                           c.url_lista(ini, fim), fim)]
        out = {"itens": itens, "vetos": [], "fim": fim, "nome_diario": nd, "fontes_lei": f_lei, "fontes_veto": [],
               "como_pt": self.como_pt, "como_en": self.como_en, "separa_camara": False,
               "fonte_arquivo": None if self.nome_pt else (nd, c.SITE)}
        # o link das cidades que ficam fora: o Diário (DOSP) ou a legislação do município (página de leis do site, CESPRO)
        if self.plat == PLAT_DOSP:
            out.update({"tipo": "diario", "rotulo_pt": rotulo_diario(nd), "rotulo_en": rotulo_diario(nd)})
        else:
            rot = ROTULO_CESPRO if self.plat == PLAT_CESPRO else ROTULO_PAGINA
            out.update({"tipo": "legislacao", "rotulo_pt": rot[0], "rotulo_en": rot[1]})
        if self.nome_en:
            out.update({"nome_en": self.nome_en, "onde_pt": "na lista", "onde_en": "in the list"})
        if self.plat in (PLAT_INSTAR, PLAT_DIGITALIZA):
            out.update({"camara_pt": "A lista não diz quem publicou cada lei: as poucas leis que a própria Câmara promulga "
                                     "só ficam fora quando o site as põe numa categoria de leis promulgadas.",
                        "camara_en": "The list does not say who published each law: the few laws the City Council "
                                     "promulgates itself are left out only when the website files them under a category "
                                     "of promulgated laws."})
        if self.plat == PLAT_DIGITALIZA:
            out.update({"sem_data_pt": "A lista não traz a data de cada lei: vale o ano do número; a data da lei mais nova "
                                       "é a do dia em que o arquivo dela foi posto no site.",
                        "sem_data_en": "The list does not give each law's date: the year in its number is used; the date "
                                       "of the newest law is the day its file was posted on the website."})
        if self.plat == PLAT_CESPRO:
            out["fonte_arquivo"] = ("CESPRO (portais de legislação dos municípios)", f"{CE.SITE}/",
                                    "Busca por tipo de norma e por ano no portal de legislação de cada município")
            out.update({"onde_pt": "no portal", "onde_en": "on the portal",
                        "onde_fora_pt": "no portal de legislação do município (CESPRO)",
                        "onde_fora_en": "on the municipality's legislation portal (CESPRO)",
                        "de_fora_en": "from the municipality's legislation portal (CESPRO)",
                        "camara_pt": "O portal não diz quem publicou cada lei: as poucas leis que a própria Câmara promulga "
                                     "só ficam fora quando o título ou o tipo da norma dizem “promulgada”.",
                        "camara_en": "The portal does not say who published each law: the few laws the City Council "
                                     "promulgates itself are left out only when the title or the type of norm says "
                                     "“promulgada” (promulgated)."})
        return out


# ---------------------------------------------------------------------------------------------------- avaliar e montar
def avaliar(dados: dict, ini: str, plataforma: str) -> tuple[str, dict]:
    """("ok", bloco executivo) ou ("fora", motivo)."""
    fim = dados["fim"]
    r = A.contar_leis(dados["itens"], ini, fim)
    v = A.contar_vetos(dados["vetos"], ini, fim)
    if not r["ok"]:
        pt, en = motivo_txt(r["motivo"], r, ini, fim, dados)
        x = {"motivo": pt, "motivo_en": en, "codigo": r["motivo"], "plataforma": plataforma,
             "diario": dados["nome_diario"], "leis": r["leis"], "falta": r["falta"], "faixa": r["faixa"], "data": fim}
        # o que uma pessoa abre para ver a mesma lista (a 1ª fonte da contagem: a busca, o filtro ou a lista de leis)
        url = ((dados.get("fontes_lei") or [{}])[0] or {}).get("url")
        if url:
            x["url"] = url
        x.update({"tipo": dados.get("tipo") or "diario", "nome": dados.get("rotulo_pt") or dados["nome_diario"],
                  "nome_en": dados.get("rotulo_en") or dados.get("rotulo_pt") or dados["nome_diario"]})
        return "fora", x
    leis_pt, leis_en, vetos_pt, vetos_en = nota(dados, ini, fim, r, v)
    ex = {"periodo": {"inicio": ini, "fim": None, "ultimaLei": r["ultima"]}, "leisSancionadas": r["leis"]}
    fontes = list(dados["fontes_lei"])
    if v.get("ok"):
        ex["vetos"] = v["vetos"]
        # total/parcial só quando o título de todos os vetos diz qual é
        if v.get("totais", 0) + v.get("parciais", 0) == v["vetos"]:
            ex["vetosTotais"], ex["vetosParciais"] = v.get("totais", 0), v.get("parciais", 0)
        fontes += dados["fontes_veto"]
    ex["fonte"] = fontes[0]
    if len(fontes) > 1:
        ex["fontes"] = fontes
    ex["nota"], ex["nota_en"] = f"{leis_pt} {vetos_pt}", f"{leis_en} {vetos_en}"
    ex["notaLeis"], ex["notaLeis_en"], ex["notaVetos"], ex["notaVetos_en"] = leis_pt, leis_en, vetos_pt, vetos_en
    ex["conferencia"] = {"plataforma": plataforma, "faixa": r["faixa"], "falta": r["falta"], "maior": r["maior"],
                         "modo": r["modo"], "promulgadas": r["promulgadas"], "foraDaSequencia": r["fora_seq"]}
    return "ok", ex


def leitores(redes: dict, h: str, desde: str) -> dict:
    out = {PLAT_SIGPUB: LeitorSigpub(redes.get("sigpub"), h, desde),
           PLAT_ASSOMASUL: LeitorAssomasul(redes.get("assomasul"), h, desde)}
    for plat in LISTAS:
        out[plat] = LeitorLista(plat, redes.get(plat), h, desde)
    return out


def plataforma_de(do: dict) -> str | None:
    p = do.get("plataforma")
    if p == PLAT_SIGPUB and assoc_sigpub(do):
        return p
    if p == PLAT_ASSOMASUL and do.get("entidade"):
        return p
    if p in LISTAS and chave_lista(p, do):
        return p
    return None


def montar(ufs: list[str], redes: dict, prazo: float, ler_materias: bool = True) -> dict:
    """Remonta dados/prefeituras/<UF>.json destes estados a partir do cache (e lê as matérias sem número, se der).

    O que já está publicado não piora por causa de uma leitura que falhou: a cidade cuja fonte não pôde ser lida (erro de
    rede, bloqueio, página de bloqueio no lugar da lista, resposta vazia ou quebrada, primeira carga por terminar) fica
    PENDENTE e mantém o que está no arquivo. Uma cidade contada só passa para "fora" quando todas as suas fontes foram
    lidas por inteiro e a regra deixou de valer (ex.: a lei mais nova passou de 120 dias); e só troca de contagem por uma
    leitura completa (da mesma fonte ou de outra que ficou mais completa)."""
    h, inicio, desde = periodo_leitura()
    mapa = ler_mapa(ufs)
    lt = leitores(redes, h, desde)
    resumo = {}
    antigos = {uf: ler_json(SAIDA / f"{uf}.json") or {} for uf in ufs}
    por_uf: dict[str, dict] = {uf: {"cidades": {}, "fora": {}, "pendentes": set(), "fontes": {}} for uf in ufs}
    for ibge, info in sorted(mapa.items()):
        do, uf = info["diario"], info["uf"]
        plat = plataforma_de(do)
        # as páginas de leis do site oficial (fornecedores conhecidos) e o portal de legislação também são lidos; nas
        # cidades cujo Diário é o próprio site ADiários, a página de leis já é a rota do Diário
        alternativas = [(p, {chave: info[chave]}) for p, chave in ALTERNATIVAS
                        if info.get(chave) and not (p == PLAT_LEIS and plat == PLAT_ADIARIOS)]
        if not plat and not alternativas:
            continue
        ini, c = inicio_prefeito(ibge, uf, inicio)
        nome = c.get("nome") or ibge
        # cada rota (o Diário e as páginas de leis): (situação, bloco ou motivo, dados)
        resultados, pendentes = [], set()
        for p, d_ in ([(plat, do)] if plat else []) + alternativas:
            dados = lt[p].cidade(ibge, d_, nome, ini, prazo, ler_materias)
            if dados.get("sem_lista"):
                continue
            if dados.get("pendente"):
                pendentes.add(p)
                continue
            st, x = avaliar(dados, ini, p)
            resultados.append((st, x, dados))
        oks = [(i, r) for i, r in enumerate(resultados) if r[0] == "ok"]
        # o que está publicado: a contagem (e de que fonte) ou o motivo de ficar fora
        contado = ((antigos[uf].get("cidades") or {}).get(ibge) or {}).get("executivo")
        fonte_antiga = ((contado or {}).get("conferencia") or {}).get("plataforma")
        # a cidade contada fica como está quando a fonte da contagem não pôde ser lida agora, ou quando nenhuma fonte
        # dá a contagem e falta ler alguma (só uma leitura completa de todas pode tirar a contagem)
        if contado and pendentes and (fonte_antiga in pendentes or not oks):
            res = ("pendente", None, None)
        elif oks:
            # mais de uma fonte com a contagem segura: a que tem os vetos; senão a mais completa (menos números de lei
            # faltando); empate: o Diário
            def preferencia(z):
                i, (_, x, _) = z
                cf = x["conferencia"]
                return (0 if "vetos" in x else 1, cf["falta"] / max(1, cf["faixa"]), i)
            res = min(oks, key=preferencia)[1]
        elif resultados:
            res = resultados[0]       # fora, pelo motivo da 1ª fonte lida por inteiro (o Diário, quando há)
        elif pendentes:
            res = ("pendente", None, None)
        else:
            continue
        st, x, dados = res
        if st == "pendente":
            por_uf[uf]["pendentes"].add(ibge)
        elif st == "ok":
            por_uf[uf]["cidades"][ibge] = {"executivo": x}
            if dados.get("fonte_arquivo"):
                nome_f, url_f, *tit = dados["fonte_arquivo"]
                por_uf[uf]["fontes"][url_f] = (nome_f, tit[0] if tit else
                                               "Busca de matérias por título e período no Diário Oficial")
        else:
            por_uf[uf]["fora"][ibge] = x
    for uf, d in por_uf.items():
        arq = SAIDA / f"{uf}.json"
        antigo = antigos[uf]
        cidades, fora = dict(d["cidades"]), dict(d["fora"])
        # cidade pendente nesta rodada (fonte que não pôde ser lida, cache incompleto, matérias por ler) e cidade que já
        # estava publicada mas não tem fonte nesta rodada: fica o que já estava no arquivo
        for ibge in sorted(set(d["pendentes"]) | ((set(antigo.get("cidades") or {}) | set(antigo.get("fora") or {})) -
                                                 set(cidades) - set(fora))):
            if ibge in (antigo.get("cidades") or {}):
                cidades[ibge] = antigo["cidades"][ibge]
                fora.pop(ibge, None)
            elif ibge in (antigo.get("fora") or {}) and ibge not in cidades:
                fora[ibge] = antigo["fora"][ibge]
        resumo[uf] = {"cidades": len(cidades), "fora": len(fora), "pendentes": len(d["pendentes"])}
        # as rotas de cada cidade (para o robô, que começa com o cache vazio): as de antes e as desta rodada
        rotas = {**(antigo.get("rotas") or {}),
                 **{i: rota_de(info) for i, info in mapa.items() if info["uf"] == uf and rota_de(info)}}
        if not cidades and not fora:
            continue
        # as fontes do estado: as de antes (de cidades que ficaram como estavam) e as desta rodada
        fontes = {f.get("url"): f for f in (antigo.get("fontes") or [])}
        fontes.update({url: fonte(nome, titulo, url, h) for url, (nome, titulo) in d["fontes"].items()})
        out = {"uf": uf, "atualizado": h, "fontes": [fontes[u] for u in sorted(fontes)],
               "nota": "Leis sancionadas e vetos de cada prefeitura, contados no Diário Oficial dos municípios ou nas "
                       "páginas oficiais de legislação do município desde o começo do mandato de quem governa hoje. Só "
                       "entram as cidades em que a contagem é segura; as outras ficam em \"fora\", com o motivo.",
               "nota_en": "Laws signed and vetoes by each city government, counted in the municipal Official Gazette or on "
                          "the municipality's official legislation pages since the start of the current mayor's term. Only "
                          "cities where the count can be checked are included; the others are in \"fora\" (left out), "
                          "with the reason.",
               "cidades": dict(sorted(cidades.items())), "fora": dict(sorted(fora.items())),
               "rotas": dict(sorted(rotas.items()))}
        SAIDA.mkdir(parents=True, exist_ok=True)
        salvar_json(arq, sem_mudar_data(out, arq))
    return resumo


# ---------------------------------------------------------------------------------------------------- leitura (rede)
def ler_sigpub(mapa: dict, rede, prazo: float, max_paginas: int | None, prioridade: list[str], stats: list):
    """Lê as associações do SIGPub das cidades do mapa (um pedido por vez), até o prazo. O grupo do dia (prioridade):
    tudo o que é novo; os outros estados: só a primeira carga que ainda não terminou."""
    h, inicio, desde = periodo_leitura()
    slugs: dict[str, str] = {}
    for ibge, info in mapa.items():
        s = assoc_sigpub(info["diario"])
        if s:
            slugs.setdefault(s, info["uf"])
    ordem = sorted(slugs, key=lambda s: (slugs[s] not in prioridade,
                                         prioridade.index(slugs[s]) if slugs[s] in prioridade else 99, s))
    for s in ordem:
        if time.time() > prazo:
            break
        a = SG.Associacao(rede, s, PASTA, h, desde, log=log)
        # o grupo do dia: tudo o que é novo; os outros estados: só a primeira carga que ainda não terminou
        if not (a.pendente() if slugs[s] in prioridade else a.falta_carga()):
            if a.completo():
                ler_materias_assoc(a, mapa, s, prazo, stats)
            continue
        t0 = time.time()
        st = a.ler(prazo, max_paginas)
        stats.append({"plataforma": "sigpub", "assoc": s, "uf": slugs[s], "status": st, "erro": a.erro,
                      "pedidos": a.pedidos, "segundos": round(time.time() - t0, 1), "completo": a.completo()})
        log(f"  [sigpub] {s} ({slugs[s]}): {st}{' (' + a.erro + ')' if a.erro else ''}; {a.pedidos} pedidos em "
            f"{time.time() - t0:.0f} s; {'completo' if a.completo() else 'falta ler parte'}")
        if a.completo():
            ler_materias_assoc(SG.Associacao(rede, s, PASTA, h, desde, log=log), mapa, s, prazo, stats)


def ler_materias_assoc(a: SG.Associacao, mapa: dict, slug: str, prazo: float, stats: list):
    """O texto das matérias de lei sem o número no título ("Lei Municipal"), das cidades desta associação: lido uma vez
    (cache para sempre), na mesma linha de execução da leitura do SIGPub (um pedido por vez ao servidor)."""
    h, inicio, desde = periodo_leitura()
    sc = SigpubCidades(a)
    antes = a.pedidos
    t0 = time.time()
    for ibge, info in sorted(mapa.items()):
        do = info["diario"]
        if assoc_sigpub(do) != slug or time.time() > prazo:
            continue
        ini, c = inicio_prefeito(ibge, info["uf"], inicio)
        sc.itens_cidade(do["entidade"], c.get("nome") or ibge, prazo, True, sc.a.data_leitura())
    if a.pedidos > antes:
        stats.append({"plataforma": "sigpub-materias", "assoc": slug, "pedidos": a.pedidos - antes,
                      "segundos": round(time.time() - t0, 1)})
        log(f"  [sigpub] {slug}: {a.pedidos - antes} matérias sem número no título lidas em {time.time() - t0:.0f} s")


def ler_assomasul(mapa: dict, rede, prazo: float, prioridade: list[str], stats: list):
    h, inicio, desde = periodo_leitura()
    t0 = time.time()
    n = ped = 0
    falhas = []
    for ibge, info in sorted(mapa.items()):
        do = info["diario"]
        if plataforma_de(do) != PLAT_ASSOMASUL:
            continue
        if time.time() > prazo:
            break
        c = AS.Cidade(rede, do["entidade"], PASTA, h, desde)
        if not (c.precisa() if info["uf"] in prioridade else not c.completo()):
            continue
        ok = c.ler()
        ped += c.pedidos
        n += 1
        if not ok:
            falhas.append(f"{ibge}: {c.erro}")
            if len(falhas) >= 3:
                break
    if n or falhas:
        stats.append({"plataforma": "assomasul", "cidades": n, "pedidos": ped, "segundos": round(time.time() - t0, 1),
                      "falhas": falhas})
        log(f"  [assomasul] {n} cidades lidas, {ped} pedidos em {time.time() - t0:.0f} s"
            f"{'; falhas: ' + ', '.join(falhas) if falhas else ''}")


def ler_listas(plat: str, mapa: dict, rede, prazo: float, prioridade: list[str], stats: list):
    """Plataformas de lista por cidade: um pedido (ou poucos) por cidade, um por vez."""
    h, inicio, desde = periodo_leitura()
    classe = LISTAS[plat][0]
    t0 = time.time()
    n = ped = 0
    falhas = []
    # o grupo do dia primeiro; depois, as primeiras cargas que faltam nos outros estados
    for ibge, info in sorted(mapa.items(), key=lambda z: (z[1]["uf"] not in prioridade, z[0])):
        do = info["diario"]
        if plat == PLAT_LEIS:
            # a página de leis do site: só nas cidades cujo Diário não é o próprio site ADiários (essas já leem a página)
            if not info.get("leis") or plataforma_de(do) == PLAT_ADIARIOS:
                continue
            chave = info["leis"]
        elif plat in (PLAT_INSTAR, PLAT_CESPRO, PLAT_DIGITALIZA):
            chave = info.get(ALT_CHAVE[plat])
            if not chave:
                continue
        else:
            if plataforma_de(do) != plat:
                continue
            chave = chave_lista(plat, do)
        if time.time() > prazo:
            break
        c = classe(rede, chave, PASTA, h, desde)
        if not (c.precisa() if info["uf"] in prioridade else not c.completo()):
            continue
        ok = c.ler()
        ped += c.pedidos
        n += 1
        if not ok:
            falhas.append(f"{ibge}: {c.erro}")
            if len(falhas) >= 8 and len(falhas) > n // 2:
                break       # o site parou de responder: fica para a próxima rodada
    if n or falhas:
        stats.append({"plataforma": plat, "cidades": n, "pedidos": ped, "segundos": round(time.time() - t0, 1),
                      "falhas": falhas[:20]})
        log(f"  [{plat}] {n} cidades lidas, {ped} pedidos em {time.time() - t0:.0f} s"
            f"{'; ' + str(len(falhas)) + ' falhas: ' + ', '.join(falhas[:5]) if falhas else ''}")


# ---------------------------------------------------------------------------------------------------- uma cidade
def mostrar_cidade(ibge: str, detalhe: bool = False):
    cidades = {i: (n, u) for i, n, u in (ler_json(DADOS / "cidades.json", []) or [])}
    if ibge not in cidades:
        print("cidade desconhecida")
        return
    nome, uf = cidades[ibge]
    info = ler_mapa([uf]).get(ibge)
    print(nome, uf, json.dumps(info, ensure_ascii=False))
    if not info:
        print("sem plataforma com leitura por título e data")
        return
    h, inicio, desde = periodo_leitura()
    ini, _ = inicio_prefeito(ibge, uf, inicio)
    lts = leitores({}, h, desde)
    plat = plataforma_de(info["diario"])
    rotas = ([(plat, info["diario"])] if plat else []) + [
        (p, {chave: info[chave]}) for p, chave in ALTERNATIVAS
        if info.get(chave) and not (p == PLAT_LEIS and plat == PLAT_ADIARIOS)]
    if not rotas:
        print("sem plataforma com leitura por título e data")
    for plat, do in rotas:
        print(f"== {plat}")
        lt = lts[plat]
        dados = lt.cidade(ibge, do, nome, ini, 0, False)
        if dados.get("pendente") or dados.get("sem_lista"):
            print("pendente:" if dados.get("pendente") else "sem lista de leis:", dados)
            continue
        r = A.contar_leis(dados["itens"], ini, dados["fim"])
        v = A.contar_vetos(dados["vetos"], ini, dados["fim"])
        print("lido até:", dados["fim"])
        print("leis:", {k: x for k, x in r.items() if k != "numeros"})
        print("números:", " ".join(f"{n}{'(C)' if c else ''}" for n, _, c in r["numeros"]))
        print("vetos:", v)
        for x in dados["vetos"]:
            print("   veto:", x["circ"], x["veto"])
        if not detalhe:
            continue
        for x in sorted(dados["itens"], key=lambda z: z["circ"]):
            lei = x["lei"]
            print(f"   {x['circ']} {x['id']} LEI {'LC ' if lei.get('lc') else ''}{lei.get('num')}/{lei.get('ano')} "
                  f"{lei.get('data') or ''}{' PROVA' if lei.get('prova') else ''}{' CAMARA' if x['camara'] else ''}")
        if plat == PLAT_SIGPUB:
            sc = lt.assoc(assoc_sigpub(do))
            sc._indexar()
            nome_e = sc.nome_ent.get(do["entidade"])
            print("   --- todas as matérias com “lei” no título:")
            for chave in [nome_e] + sorted(sc.camaras_da_cidade(nome)):
                for cod, tit, org, circ, ent in sorted(sc._por_nome.get(chave, []), key=lambda z: z[3]):
                    print(f"   {circ} {cod} {tit[:110]} | {org[:40]}{' | ' + ent if chave != nome_e else ''}")

# ---------------------------------------------------------------------------------------------------- principal
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ufs", nargs="*")
    ap.add_argument("--rodizio", action="store_true")
    ap.add_argument("--montar", action="store_true")
    ap.add_argument("--ibge")
    ap.add_argument("--detalhe", action="store_true", help="com --ibge: cada matéria lida e como foi entendida")
    ap.add_argument("--minutos", type=float, default=MINUTOS)
    ap.add_argument("--max-paginas", type=int, default=None)
    ap.add_argument("--so", choices=["sigpub", "assomasul", "dosp", "adiarios", "leis", "instar", "cespro", "digitaliza"],
                    help="só esta plataforma")
    a = ap.parse_args()
    if a.ibge:
        mostrar_cidade(a.ibge, a.detalhe)
        return 0
    t_ini = time.time()
    prazo = t_ini + a.minutos * 60
    hoje_ = hoje()
    if a.rodizio:
        prioridade = grupos_rodizio()[dt.date.fromisoformat(hoje_).weekday()]
        ufs = list(UFS)          # depois do grupo do dia, as primeiras cargas que ainda faltam
    else:
        ufs = [u.upper() for u in a.ufs] or list(UFS)
        prioridade = ufs
    for u in ufs:
        if u not in UFS:
            ap.error(f"estado desconhecido: {u}")
    # um pedido por vez a cada servidor: um intervalo de 1 s também entre sites diferentes do mesmo servidor (muitos
    # sites de prefeituras de um fornecedor ficam no mesmo endereço IP)
    _rede.INTERVALO_IP = max(_rede.INTERVALO_IP, 1.0)
    redes = {"sigpub": _rede.Rede(pausa=SG.PAUSA, por_ip=1), "assomasul": _rede.Rede(pausa=AS.PAUSA, por_ip=1),
             PLAT_DOSP: _rede.Rede(pausa=DL.PAUSA, por_ip=1)}
    redes[PLAT_ADIARIOS] = redes[PLAT_LEIS] = _rede.Rede(pausa=DL.PAUSA, por_ip=1)   # o mesmo fornecedor
    redes[PLAT_INSTAR] = _rede.Rede(pausa=DL.PAUSA, por_ip=1)
    redes[PLAT_DIGITALIZA] = _rede.Rede(pausa=DL.PAUSA, por_ip=1)
    redes[PLAT_CESPRO] = _rede.Rede(pausa=DL.PAUSA, por_ip=1)    # um servidor só, para ~140 municípios
    stats: list = []
    if not a.montar:
        log(f"Diários Oficiais (leis e vetos das prefeituras): {', '.join(prioridade)}"
            f"{' + primeiras cargas pendentes' if a.rodizio else ''}; até {a.minutos:.0f} min")
        mapa = ler_mapa(ufs)

        def listas(plats):
            for plat in plats:
                ler_listas(plat, mapa, redes[plat], prazo, prioridade, stats)
        # um servidor por linha de execução: plataformas diferentes são lidas ao mesmo tempo
        tarefas = []
        if a.so in (None, "sigpub"):
            tarefas.append(threading.Thread(target=ler_sigpub, args=(mapa, redes["sigpub"], prazo, a.max_paginas,
                                                                     prioridade, stats)))
        if a.so in (None, "assomasul"):
            tarefas.append(threading.Thread(target=ler_assomasul, args=(mapa, redes["assomasul"], prazo, prioridade, stats)))
        if a.so in (None, "dosp"):
            tarefas.append(threading.Thread(target=listas, args=([PLAT_DOSP],)))
        adi = [p for p, curto in ((PLAT_ADIARIOS, "adiarios"), (PLAT_LEIS, "leis")) if a.so in (None, curto)]
        if adi:
            tarefas.append(threading.Thread(target=listas, args=(adi,)))
        if a.so in (None, "instar"):
            tarefas.append(threading.Thread(target=listas, args=([PLAT_INSTAR],)))
        if a.so in (None, "cespro"):
            tarefas.append(threading.Thread(target=listas, args=([PLAT_CESPRO],)))
        if a.so in (None, "digitaliza"):
            tarefas.append(threading.Thread(target=listas, args=([PLAT_DIGITALIZA],)))
        for t in tarefas:
            t.start()
        for t in tarefas:
            t.join()
    # remonta os estados a partir do cache, sem rede (o texto das matérias sem número já foi lido junto com o SIGPub)
    resumo = montar(ufs if a.ufs else UFS, {}, 0, ler_materias=False)
    for uf, r in sorted(resumo.items()):
        if r["cidades"] or r["fora"] or r["pendentes"]:
            log(f"  {uf}: {r['cidades']} cidades com a contagem, {r['fora']} fora, {r['pendentes']} pendentes")
    dur = time.time() - t_ini
    pedidos = sum(r.pedidos for r in {id(x): x for x in redes.values()}.values())
    if not a.montar:
        rod = ler_json(RODADAS, []) or []
        rod.append({"data": hoje_, "inicio": dt.datetime.now().isoformat(timespec="seconds"), "segundos": round(dur),
                    "pedidos": pedidos, "ufs": prioridade, "leituras": stats,
                    "cidades": sum(r["cidades"] for r in resumo.values()), "fora": sum(r["fora"] for r in resumo.values())})
        PASTA.mkdir(parents=True, exist_ok=True)
        RODADAS.write_text(json.dumps(rod[-200:], ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Pronto em {dur / 60:.1f} min; {pedidos} pedidos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
