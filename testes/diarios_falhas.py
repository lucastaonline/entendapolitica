"""Testes sem rede: falhas de rede e bloqueios não mudam o que está publicado (fase 4: leis e vetos das prefeituras).

No robô (GitHub, IPs de fora do Brasil) muitos sites municipais bloqueiam ou caem. Estes testes simulam, em cada
plataforma, respostas ruins — 403, 429, 503, tempo esgotado, DNS, página de bloqueio/captcha no lugar da lista, resposta
vazia, JSON quebrado ou sem a lista, página cortada no meio da lista — e conferem que:
1. a leitura falha e o cache da cidade não muda (nada é gravado pela metade);
2. a montagem deixa a cidade como estava publicada em dados/prefeituras/<UF>.json (pendente), sem virar "fora" nem
   contagem menor — também quando o cache some (primeira carga no robô) ou quando o mapa perde o link da fonte;
3. uma leitura válida que traz menos leis (site com problema) não diminui a lista;
4. uma cidade contada só vai para "fora" quando a leitura nova foi completa e a regra mudou de verdade (a lei mais nova
   passou de 120 dias).

Tudo numa pasta de rascunho em .cache/testes/diarios_falhas/ (apagada no fim). Rodar: python testes/diarios_falhas.py
"""
import json
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts" / "municipios"))
sys.path.insert(0, str(RAIZ / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
import _rede  # noqa: E402
import _diario_listas as DL  # noqa: E402
import _diario_assomasul as AS  # noqa: E402
import _diario_cespro as CE  # noqa: E402
import _diario_sigpub as SG  # noqa: E402
import diarios as D  # noqa: E402

RASCUNHO = RAIZ / ".cache" / "testes" / "diarios_falhas"
DESDE = "2024-10-01"
H1, H2, H3 = "2026-10-26", "2026-11-09", "2027-03-01"   # leitura boa; rodada seguinte; rodada bem depois

erros: list[str] = []
n_conf = 0


def confere(cond, msg):
    global n_conf
    n_conf += 1
    if not cond:
        erros.append(msg)


# ---------------------------------------------------------------------------------------------------- rede falsa
def resp(status=200, corpo=b"", erro=None):
    r = _rede.Resposta(url="", final="")
    r.status, r.corpo, r.erro, r.charset = status, corpo, erro, "utf-8"
    return r


CAPTCHA = (b"<html><head><title>Just a moment...</title></head><body><div id='cf-challenge'>Checking your browser "
           b"before accessing. Please complete the security check (captcha).</div></body></html>")
FALHAS = {
    "403": lambda: resp(403, b"Forbidden", "http 403"),
    "429": lambda: resp(429, b"Too Many Requests", "http 429"),
    "503": lambda: resp(503, b"Service Unavailable", "http 503"),
    "tempo esgotado": lambda: resp(None, b"", "timeout"),
    "DNS": lambda: resp(None, b"", "dns"),
    "captcha no lugar da lista": lambda: resp(200, CAPTCHA),
    "resposta vazia": lambda: resp(200, b""),
    "JSON quebrado": lambda: resp(200, b'{"data": [{"id": 1, "titulo": "LEI'),
    "JSON sem a lista": lambda: resp(200, b'{"message": "Too Many Attempts."}'),
}


class RedeFalsa:
    def __init__(self, responder):
        self.responder, self.pedidos = responder, 0

    def pagina(self, url, ua=None, aceitar=None, max_bytes=None, respeitar_robots=True, extra=None):
        self.pedidos += 1
        r = self.responder(url)
        r.url = r.final = url
        return r


CE.post_json = lambda rede, url, corpo: rede.pagina(url)      # o POST do CESPRO passa pela rede falsa


def sempre(falha):
    return lambda url: FALHAS[falha]()


# ---------------------------------------------------------------------------------------------------- leis de mentira
# a lei 100 é de antes do mandato; as 101 a 130, do mandato (de 15/1/2025 a 1º/10/2026)
def leis(ate=130):
    out = [(100, "2024-12-10")]
    for i, n in enumerate(range(101, ate + 1)):
        mes = 1 + i * 21 // 30
        ano, mes = 2025 + (mes - 1) // 12, (mes - 1) % 12 + 1
        out.append((n, f"{ano}-{mes:02d}-{1 + i % 27:02d}"))
    out[-1] = (ate, "2026-10-01")
    return out


def br(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


def dosp_ok(lista):
    linhas = "".join(f"<tr><td>LEI {n}</td><td>{br(d)}</td><td></td><td></td><td><a href='l{n}.pdf'>ver</a></td></tr>"
                     for n, d in lista)
    return lambda url: resp(200, f"<table><tr><th>Título</th><th>Data</th></tr>{linhas}</table>".encode())


def adiarios_ok(lista):
    cards = "".join(f"<a class='card-clean' href='leis.php?id={n}'><strong class='card-clean__title'>LEI MUNICIPAL: "
                    f"{n}/{d[:4]}</strong><i></i> {br(d)}</a>" for n, d in lista)
    return lambda url: resp(200, f"<form><select name=\"cat\"></select></form>{cards}".encode())


SELECT_INSTAR = ('<select id="form_categoria_simples" name="form_categoria"><option value="">TODAS</option>'
                 '<option value="1">Lei Ordinária</option></select>')


def instar_ok(lista):
    blocos = "".join(f'<div class="leg_norma_listagem"><div class="leg_numero_norma"><span>Nº {n}</span></div>'
                     f'<input type="hidden" class="leg_id_norma" value="{n}"><strong>Data:</strong> {br(d)}</div>'
                     for n, d in sorted(lista, key=lambda z: z[1], reverse=True))

    def r(url):
        if url.endswith("/portal/leis_decretos"):
            return resp(200, f"<html>{SELECT_INSTAR}</html>".encode())
        return resp(200, f"<html>{SELECT_INSTAR}{blocos}</html>".encode())
    return r


def digitaliza_ok(lista):
    def r(url):
        if "/legislacoes/todas/" in url:
            return resp(200, b'<a href="https://x/legislacoes/4/Leis">Leis</a> <script>url: "/legislacoes/get/todas"</script>')
        ano = url.split("columns%5B1%5D%5Bsearch%5D%5Bvalue%5D=")[-1][:4] if "search" in url else None
        dados = [{"id": n, "ano": d[:4], "numero": str(n), "arquivo": {"created_at": d + "T10:00:00Z"}}
                 for n, d in lista if not ano or d[:4] == ano]
        return resp(200, json.dumps({"draw": 1, "recordsTotal": len(dados), "recordsFiltered": len(dados),
                                     "data": dados}).encode())
    return r


def cespro_ok(lista):
    def r(url):
        if "cdTipo=" not in url:
            return resp(200, json.dumps({"dados_tipo_diplomas": [{"cd_municipio_tipo_diploma": "10",
                                                                  "ds_municipio_tipo_diploma": "Leis Municipais"}]}).encode())
        res = {str(i + 1): {"id": str(n), "ds_title": f"LEI MUNICIPAL Nº {n}, DE {br(d)}"}
               for i, (n, d) in enumerate(sorted(lista, key=lambda z: z[1], reverse=True))}
        return resp(200, json.dumps({"dados_legislacao_resultado_pesquisa_json": res,
                                     "dados_paginacao_resultado_new": f"Encontrado(s) {len(res)} Diploma(s) Legais em "
                                                                      "1 página(s)."}).encode())
    return r


def assomasul_ok(lista):
    def r(url):
        if "titulo%5D=veto" in url:
            return resp(200, b'{"draw": 1, "recordsFiltered": 0, "data": []}')
        dados = [{"id": n, "titulo": f"LEI Nº {n}/{d[:4]}", "data_de_circulacao": br(d)} for n, d in lista]
        return resp(200, json.dumps({"draw": 1, "recordsFiltered": len(dados), "data": dados}).encode())
    return r


# ---------------------------------------------------------------------------------------------------- 1. leituras
def conferir_plataforma(nome, criar, responder_bom):
    pasta = RASCUNHO / "cache"
    c = criar(RedeFalsa(responder_bom), H1)
    confere(c.ler(), f"{nome}: a leitura boa devia dar certo ({c.erro})")
    antes = c.arq.read_bytes()
    n_antes = len(c.itens("lei"))
    confere(n_antes >= 31, f"{nome}: leitura boa com {n_antes} leis")
    for falha in FALHAS:
        c2 = criar(RedeFalsa(sempre(falha)), H2)
        ok = c2.ler()
        confere(not ok, f"{nome} / {falha}: a leitura devia falhar")
        confere(c2.arq.read_bytes() == antes, f"{nome} / {falha}: o cache mudou")
    # uma leitura válida, mas com menos leis (site com problema): a lista não diminui
    c3 = criar(RedeFalsa(MENOS[nome]), H2)
    confere(c3.ler() and len(c3.itens("lei")) >= n_antes,
            f"{nome}: a lista diminuiu ({len(c3.itens('lei'))} < {n_antes})")
    return pasta


MENOS = {}


def main():
    if RASCUNHO.exists():
        shutil.rmtree(RASCUNHO)
    pasta = RASCUNHO / "cache"
    pasta.mkdir(parents=True)
    todas, poucas = leis(), leis(110)
    plataformas = {
        "DOSP": (lambda rede, h: DL.DospCidade(rede, "teste", pasta, h, DESDE), dosp_ok),
        "ADiários": (lambda rede, h: DL.AdiariosCidade(rede, "https://www.teste.ce.gov.br", pasta, h, DESDE), adiarios_ok),
        "Instar": (lambda rede, h: DL.InstarCidade(rede, "https://www.teste.sp.gov.br", pasta, h, DESDE), instar_ok),
        "Digitaliza": (lambda rede, h: DL.DigitalizaCidade(rede, "https://www.teste.mg.gov.br", pasta, h, DESDE),
                       digitaliza_ok),
        "CESPRO": (lambda rede, h: CE.CesproCidade(rede, "4304", pasta, h, DESDE), cespro_ok),
        "Assomasul": (lambda rede, h: AS.Cidade(rede, "123", pasta, h, DESDE), assomasul_ok),
    }
    for nome, (criar, bom) in plataformas.items():
        MENOS[nome] = bom(poucas)
        conferir_plataforma(nome, criar, bom(todas))

    # Instar e Digitaliza: uma página do meio da lista que vem como bloqueio (a primeira veio boa) também falha
    def meio_bloqueado(bom, n_boas):
        cont = {"n": 0}

        def r(url):
            cont["n"] += 1
            return bom(url) if cont["n"] <= n_boas else FALHAS["captcha no lugar da lista"]()
        return r
    for nome, n_boas in (("Instar", 1), ("Digitaliza", 1), ("CESPRO", 1)):
        criar, bom = plataformas[nome]
        c = criar(RedeFalsa(meio_bloqueado(bom(todas), n_boas)), H3)
        antes = c.arq.read_bytes()
        confere(not c.ler(), f"{nome} / bloqueio no meio da lista: a leitura devia falhar")
        confere(c.arq.read_bytes() == antes, f"{nome} / bloqueio no meio da lista: o cache mudou")

    # ------------------------------------------------------------------------------------------------ SIGPub
    def sigpub_pagina(lista, total=None, cortada=False):
        cards = "".join(f'<li class="materia-card"><div class="materia-card__titulo"><a href="/teste/materia/L{n}">'
                        f'LEI Nº {n}/{d[:4]}</a></div><span class="materia-card__entidade">Prefeitura Municipal de Teste'
                        f'</span><span class="materia-card__orgao">Gabinete</span><dl><dt>Circulação</dt><dd>{br(d)}</dd>'
                        f'</dl></li>' for n, d in ([] if cortada else lista))
        t = total if total is not None else len(lista)
        cab = (f"Mostrando <strong>1</strong> a <strong>{min(25, t)}</strong> de <strong>{t}</strong>" if t else
               "Nenhuma matéria encontrada")
        return resp(200, f"<html>{cab}<ul>{cards}</ul></html>".encode())

    for falha in FALHAS:
        a = SG.Associacao(RedeFalsa(sempre(falha)), "teste", pasta, H1, DESDE)
        confere(a._pagina(SG.url_busca("teste", "lei", DESDE, "2024-10-31")) is None,
                f"SIGPub / {falha}: a página ruim devia ser recusada")
        st = a.ler(prazo=10 ** 12)
        confere(st == "erro" and not a.completo() and not a.itens_mes("2024-10"),
                f"SIGPub / {falha}: a leitura devia falhar sem gravar ({st})")
    # página cortada: o total diz 30 matérias e a 2ª página vem sem nenhuma
    trinta = [(n, "2024-10-15") for n in range(1, 31)]
    paginas = iter([sigpub_pagina(trinta[:25], 30), sigpub_pagina([], 30, cortada=True)])
    shutil.rmtree(pasta / "sigpub-teste", ignore_errors=True)
    a = SG.Associacao(RedeFalsa(lambda url: next(paginas)), "teste", pasta, H1, DESDE)
    st = a.ler(prazo=10 ** 12)
    confere(st == "erro" and not (a.estado["meses"].get("2024-10") or {}).get("completo"),
            f"SIGPub / página cortada: o mês não podia ficar completo ({st})")
    # matéria (texto da lei sem número no título): página de bloqueio não é guardada
    a = SG.Associacao(RedeFalsa(sempre("captcha no lugar da lista")), "teste", pasta, H1, DESDE)
    confere(a.materia("ABC123", prazo=10 ** 12) is None and not (a.pasta / "materias" / "ABC123.json").exists(),
            "SIGPub / matéria com captcha: não podia guardar")

    # ------------------------------------------------------------------------------------------------ 2. montagem
    D.PASTA, D.ROTAS = pasta, pasta / "rotas.json"
    D.SAIDA, D.MAPA, D.CACHE = RASCUNHO / "saida", RASCUNHO / "mapa", RASCUNHO / "cachemapa"
    for p in (D.SAIDA, D.MAPA, D.CACHE / "municipios" / "cidades" / "RN"):
        p.mkdir(parents=True, exist_ok=True)
    ibge, ibge2 = "9900001", "9900002"
    do = {"nome": "Diário Oficial do Município de Teste", "url": "https://imprensaoficialmunicipal.com.br/teste",
          "plataforma": D.PLAT_DOSP}
    do2 = {"nome": "Diário Oficial do Município de Teste Dois", "url": "https://imprensaoficialmunicipal.com.br/teste2",
           "plataforma": D.PLAT_DOSP}

    def mapa(com_diario=True):
        cid = {ibge: {"prefeitura": {"diarioOficial": do if com_diario else {}}},
               ibge2: {"prefeitura": {"diarioOficial": do2}}}
        (D.MAPA / "RN.json").write_text(json.dumps({"uf": "RN", "cidades": cid}), encoding="utf-8")
    # a 2ª cidade: Diário com poucas leis (fica fora) e a página de leis do site (Instar) com a lista toda (contada)
    (D.CACHE / "municipios" / "cidades" / "RN" / f"{ibge2}.json").write_text(json.dumps(
        {"prefeitura": {"legislacao": "https://www.teste2.rn.gov.br/portal/leis_decretos"}}), encoding="utf-8")

    def montar(h):
        D.hoje = lambda: h
        D.montar(["RN"], {}, 0, ler_materias=False)
        return json.loads((D.SAIDA / "RN.json").read_text(encoding="utf-8"))

    mapa()
    shutil.rmtree(pasta / "dosp", ignore_errors=True)
    shutil.rmtree(pasta / "instar", ignore_errors=True)
    assert DL.DospCidade(RedeFalsa(dosp_ok(todas)), "teste", pasta, H1, DESDE).ler()
    assert DL.DospCidade(RedeFalsa(dosp_ok([(100, "2024-12-10"), (101, "2025-01-15")])), "teste2", pasta, H1, DESDE).ler()
    assert DL.InstarCidade(RedeFalsa(instar_ok(todas)), "https://www.teste2.rn.gov.br", pasta, H1, DESDE).ler()
    s0 = montar(H1)
    e0 = (s0["cidades"].get(ibge) or {}).get("executivo") or {}
    e02 = (s0["cidades"].get(ibge2) or {}).get("executivo") or {}
    confere(e0.get("leisSancionadas") == 30, f"montagem: a cidade devia ter 30 leis ({e0.get('leisSancionadas')})")
    confere(e02.get("conferencia", {}).get("plataforma") == D.PLAT_INSTAR,
            f"montagem: a 2ª cidade devia ser contada pela página de leis ({e02.get('conferencia')})")

    def igual(s, msg):
        confere(s["cidades"].get(ibge) == s0["cidades"].get(ibge) and ibge not in s["fora"], f"{msg} (1ª cidade)")
        confere(s["cidades"].get(ibge2) == s0["cidades"].get(ibge2) and ibge2 not in s["fora"], f"{msg} (2ª cidade)")

    # 2a. na rodada seguinte, todas as fontes falham (cada tipo de falha): fica o que está publicado
    for falha in FALHAS:
        for chave in ("teste", "teste2"):
            DL.DospCidade(RedeFalsa(sempre(falha)), chave, pasta, H2, DESDE).ler()
        DL.InstarCidade(RedeFalsa(sempre(falha)), "https://www.teste2.rn.gov.br", pasta, H2, DESDE).ler()
        igual(montar(H2), f"montagem / {falha}: mudou o que estava publicado")
    # 2b. o cache some (primeira carga no robô, com os sites bloqueando): pendente, fica o publicado
    guardado = RASCUNHO / "guardado"
    shutil.copytree(pasta, guardado)
    shutil.rmtree(pasta / "dosp")
    shutil.rmtree(pasta / "instar")
    igual(montar(H2), "montagem / sem cache: mudou o que estava publicado")
    # 2c. só a fonte da contagem da 2ª cidade (a página de leis) não pôde ser lida; o Diário dela foi lido (e fica fora)
    shutil.copytree(guardado / "dosp", pasta / "dosp")
    igual(montar(H2), "montagem / fonte da contagem pendente: mudou o que estava publicado")
    shutil.rmtree(pasta)
    shutil.copytree(guardado, pasta)
    # 2d. o mapa perde o link do Diário numa rodada (site fora do ar para o robô do mapa): vale a rota guardada
    mapa(com_diario=False)
    igual(montar(H2), "montagem / mapa sem o link: mudou o que estava publicado")
    # 2e. o mapa perde a cidade e a rota guardada some também: fica o publicado
    (D.MAPA / "RN.json").write_text(json.dumps({"uf": "RN", "cidades": {}}), encoding="utf-8")
    D.ROTAS.unlink()
    igual(montar(H2), "montagem / cidade fora do mapa: mudou o que estava publicado")
    mapa()
    # 2f. a 2ª cidade com o Diário também contável, mas menos completo (27 leis): vale a página de leis (30); quando a
    # página de leis não pode ser lida, a contagem publicada fica — não troca pela menor
    furado = [x for x in todas if x[0] not in (105, 115, 125)]
    DL.DospCidade(RedeFalsa(dosp_ok(furado)), "teste2", pasta, "2026-10-27", DESDE).ler()
    s = montar("2026-10-27")
    e2 = (s["cidades"].get(ibge2) or {}).get("executivo") or {}
    confere(e2.get("leisSancionadas") == 30 and e2.get("conferencia", {}).get("plataforma") == D.PLAT_INSTAR,
            f"montagem / duas fontes: devia valer a mais completa ({e2.get('leisSancionadas')})")
    shutil.rmtree(pasta / "instar")
    s = montar("2026-10-27")
    confere(s["cidades"].get(ibge2) == e2 or s["cidades"].get(ibge2, {}).get("executivo") == e2,
            "montagem / fonte da contagem pendente e outra fonte com menos leis: a contagem mudou")
    shutil.rmtree(pasta)
    shutil.copytree(guardado, pasta)

    # 3. leitura válida com menos leis (site com problema): a contagem não diminui
    DL.DospCidade(RedeFalsa(dosp_ok(poucas)), "teste", pasta, "2026-12-01", DESDE).ler()
    s = montar("2026-12-01")
    n = ((s["cidades"].get(ibge) or {}).get("executivo") or {}).get("leisSancionadas")
    confere(n == 30, f"montagem / lista menor: a contagem mudou para {n}")

    # 4. leitura completa, bem depois, e a lei mais nova tem mais de 120 dias: aí sim vai para "fora"
    DL.DospCidade(RedeFalsa(dosp_ok(todas)), "teste", pasta, H3, DESDE).ler()
    s = montar(H3)
    f = s["fora"].get(ibge) or {}
    confere(ibge not in s["cidades"] and f.get("codigo") == "parou",
            f"montagem / regra mudou: a cidade devia ir para fora por 'parou' ({f.get('codigo')})")
    confere(f.get("url", "").startswith("https://imprensaoficialmunicipal.com.br/listaatos.php") and
            f.get("tipo") == "diario" and f.get("nome") and f.get("nome_en"),
            f"montagem / fora: url, tipo e nome do link ({f.get('url')}, {f.get('tipo')}, {f.get('nome')})")

    shutil.rmtree(RASCUNHO)
    try:
        RASCUNHO.parent.rmdir()      # .cache/testes, se ficou vazia
    except OSError:
        pass
    for e in erros:
        print("ERRO:", e)
    print(f"{n_conf - len(erros)} de {n_conf} conferências certas")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
