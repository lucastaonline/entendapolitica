"""Testes do leitor de títulos e das contagens de leis e vetos dos Diários Oficiais (scripts/municipios/_atos.py).

Sem rede: títulos reais (copiados dos Diários Oficiais dos municípios em 26/10/2026) e o que cada um deve virar.
Rodar: python testes/diarios_titulos.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "municipios"))
sys.stdout.reconfigure(encoding="utf-8")
import _atos as A  # noqa: E402

LEIS = [  # (título, complementar?, número, ano, data)
    ("LEI MUNICIPAL N° 226/2026-GP/PMA, DE 16 DE OUTUBRO DE 2026.", False, 226, 2026, "2026-10-16"),
    ("LEI Nº473 - ALTERA O ANEXO X, DA LEI MUNICIPAL Nº. 290, DE 2 DE MAIO DE 2018, QUE TRATA", False, 473, None, None),
    ("LEI Nº 0630/GPMAAN/2026, ÁGUA AZUL DO NORTE-PA, 09 DE JUNHO DE 2026", False, 630, 2026, "2026-06-09"),
    ("LEI MUNICIPAL Nº 1.607-26 = ALTERA DENOMINAÇÃO DE ESCOLA", False, 1607, 2026, None),
    ("LEI MUNICIPAL N° 432 DE 2026 - LDO 2027", False, 432, 2026, None),
    ("LEI N° 4.746 DE 22 DE SETEMBRO DE 2026.", False, 4746, 2026, "2026-09-22"),
    ("LEI MUNICIAL DE Nº 374, DE 29 DE SETEMBRO DE 2026.", False, 374, 2026, "2026-09-29"),
    ("LEI MUNICIPAL Nº, 467, DE 20 MAIO DE 2026", False, 467, 2026, "2026-05-20"),
    ("REESTRUTURAÇÃO ADMINISTRATIVA DO PODER EXECUTIVO MUNICIPAL DE AMATURA/AM LEI COMPLEMENTAR Nº 215/2026, DE 19 DE "
     "MARÇO DE 2026. DISPÕE SOBRE", True, 215, 2026, "2026-03-19"),
    ("LEI COMPLEMENTAR N° 010", True, 10, None, None),
    ("Lei nº. 1.373, de 19 de fevereiro de 2025.", False, 1373, 2025, "2025-02-19"),
    ("LEI ORÇAMENTÁRIA ANUAL LEI Nº 0476/2025 - LOA", False, 476, 2025, None),
    ("LEI - Nº 1701 - LDO 2025", False, 1701, None, None),
]
PROVAS = ["REPUBLICAÇÃO DA LEI ORDINARIA 649/2026", "ERRATA – LEI Nº 3493/2026", "TERMO DE SANÇÃO À LEI Nº 432/2026",
          "ANEXO I - LEI MUNICIPAL Nº 461/2025 PLANO PLURIANUAL – PPA", "LEI Nº. 3.238/2026 - REPUBLICADO POR INCORREÇÃO"]
# categorias do formulário de legislação dos sites Instar (vistas em 26/10/2026): (rótulo, (complementar?, promulgada?,
# ano da categoria) ou None quando não é categoria de lei sancionada ou promulgada)
INSTAR_CATS = [
    ("Lei", (False, False, None)), ("Lei Ordinária", (False, False, None)), ("Leis", (False, False, None)),
    ("Leis 2025", (False, False, 2025)), ("Lei Complementar", (True, False, None)),
    ("Leis Complementares 2026", (True, False, 2026)), ("Lei Municipal", (False, False, None)),
    ("LDO - Lei de Diretrizes Orçamentárias", (False, False, None)), ("LOA - Lei Orçamentária Anual", (False, False, None)),
    ("PPA - Plano Plurianual", (False, False, None)), ("Lei Promulgada", (False, True, None)),
    ("Leis Complementares Antigas", None), ("Lei Orgânica", None), ("Lei Orgânica do Município", None),
    ("Emenda á lei orgânica", None), ("Projeto de Lei", None), ("Lei de Organização Municipal", None),
    ("Código Tributário", None), ("Decreto Legislativo", None), ("Decretos 2025", None),
]
INSTAR_NUMS = [  # (categoria|número|data, número, ano)
    ("Lei Ordinária|Nº 4544|2026-09-23", 4544, None), ("Lei Ordinária|Nº 5882025|2025-08-26", 588, 2025),
    ("Lei Ordinária|Nº 589/2025|2025-09-25", 589, 2025), ("Lei|Nº 1.234|2025-02-02", 1234, None),
    ("Lei|-/2025|2025-02-06", None, None), ("Lei Complementar|Nº 12/25|2025-03-01", 12, 2025),
]
# nome do Diário no mapa -> rótulo curto do link "Onde ver mais" das cidades que ficam fora
ROTULOS = [
    ("Diário Oficial dos Municípios (Federação das Associações de Municípios da Paraíba - FAMUP)",
     "Diário Oficial dos Municípios (FAMUP)"),
    ("Diário Oficial dos Municípios (FEDERAÇÃO DOS MUNICÍPIOS DO ESTADO DO RIO GRANDE DO NORTE (FEMURN))",
     "Diário Oficial dos Municípios (FEMURN)"),
    ("Diário Oficial dos Municípios (AMP - Associação dos Municípios do Paraná)", "Diário Oficial dos Municípios (AMP)"),
    ("Diário Oficial dos Municípios (Associação dos Municípios Alagoanos – AMA)", "Diário Oficial dos Municípios (AMA)"),
    ("Diário Oficial dos Municípios (Associação Mineira de Municípios - AMM-MG)", "Diário Oficial dos Municípios (AMM-MG)"),
    ("Diário Oficial dos Municípios (SIGPub)", "Diário Oficial dos Municípios (SIGPub)"),
    ("Diário Oficial MS (Assomasul)", "Diário Oficial MS (Assomasul)"),
    ("Diário Oficial do Município de Horizonte", "Diário Oficial do Município de Horizonte"),
]
NAO_LEIS = ["DECRETO Nº 3 , DE 01 DE ABRIL DE 2026 - LEI N.462",
            "AVISO DE DISPENSA Nº 317/2026 COM BASE NO ARTIGO 75, § 7º, DA LEI FEDERAL Nº 14.133/21",
            "BALANÇO PATRIMONIAL ANEXO XIV, DA LEI Nº 4.320/64 - FUNPREV", "NOVA LEI ORGÂNICA DO MUNICÍPIO DE IBARETAMA",
            "ATA DA AUDIÊNCIA PÚBLICA PARA ELABORAÇÃO DA LEI ORÇAMENTÁRIA ANUAL (LOA)", "LEI ALDIR BLANC",
            "LEI DE DIRETRIZES ORÇAMENTÁRIAS - 2025", "LEI ORDINÁRIA - REPUBLICADO POR INCORREÇÃO",
            "PROMULGA PROPOSIÇÃO LEGISLATIVA SANCIONADA TACITAMENTE, EM VIRTUDE DO SILÊNCIO DE SANÇÃO OU VETO",
            "EMENDA À LEI ORGÂNICA DO MUNICIPIO DE BATAYPORÃ Nº 001/2025"]
SEM_NUMERO = ["LEI MUNICIPAL", "LEI ORDINÁRIA", "LEI COMPLEMENTAR MUNICIPAL"]
VETOS = [  # (título, número, ano, parcial)
    ("MENSAGEM DE VETO TOTAL Nº 001/2025", 1, 2025, False),
    ("MENSAGEM DE VETO PARCIAL Nº 001-2025", 1, 2025, True),
    ("RAZÕES DE VETO 007/2026", 7, 2026, None),
    ("VETO INTEGRAL Nº 002/2025 AO AUTÓGRAFO DE LEI N.º 799/2025", 2, 2025, False),
    ("VETO Nº 001/2026 - VETO INTEGRAL AO PL Nº 012/2026.", 1, 2026, False),
    ("MENSAGEM DE VETO Nº 27, DE 16 DE SETEMBRO DE 2025", 27, None, None),
    ("VETO TOTAL AO PROJETO DE LEI Nº 10/2025", None, None, False),
]
NAO_VETOS = ["DECRETO LEGISLATIVO N.º 002/2026 ACOLHE O VETO PARCIAL APOSTO PELO CHEFE DO EXECUTIVO"]
LISTA = [  # títulos da seção "Leis" (nomes de arquivo): (título, complementar?, número)
    ("LEI 1767 PARA DOM", False, 1767), ("PARA PUBLICAR LEI 1.754", False, 1754), ("Lei Odinária 4301-2026", False, 4301),
    ("Lei Complemetar 1938- 2026", True, 1938), ("LC 57-2026 - FUNÇÃO GRATIFICADA", True, 57), ("LO 3575", False, 3575),
    ("LM 6662-2026", False, 6662), ("l5215", False, 5215), ("l-1491-2026-Cred Ad Especial", False, 1491),
    ("Compl. 130-26 Tab. Venc. Câmara", True, 130), ("leicomplementar151_26", True, 151), ("LEIS_02679_2026", False, 2679),
    ("9152.lei", False, 9152), ("3983 E ANEXOS", False, 3983), ("4.377", False, 4377), ("19- 207-26 - LEI -_PMPI", False, 207),
    ("Lei 30682026 - Termo de Fomento", False, 3068), ("08 LC_N_307_DISPOE_SOBRE", True, 307),
    ("07 6LEI_N_4731_DISPOE", False, 4731), ("Lei Número nº 3.237-2025 - CALENDÁRIO", False, 3237),
]
LISTA_NAO = ["Anexo_IV_Microzoneamento", "DEMONSTRATIVO 7", "03-Despesas por programa", "23 Convocacao_Imprensa_2026_10_23",
             "PL 2.265", "Emenda LOM nº 001-26 - Altera art. 119-A", "Dec 7558 (Homologação do Concurso 01-2026)"]
LISTA_SEM_NUMERO = ["LEIS", "LECE44~1", "WhatsApp Scan 2026-07-15 at 14.20.04", "LEI REFIS 2025", "15.07.2026 (1)"]


def item(lei, circ, camara=False):
    return {"lei": A.ler_titulo(lei) if isinstance(lei, str) else lei, "circ": circ, "camara": camara, "id": circ + str(lei)}


def main() -> int:
    erros = []

    def confere(cond, msg):
        if not cond:
            erros.append(msg)

    for t, lc, n, ano, dt in LEIS:
        x = A.ler_titulo(t)
        confere(x and x["tipo"] == "lei" and x["lc"] == lc and x["num"] == n and x["ano"] == ano and x["data"] == dt,
                f"lei: {t!r} -> {x}")
    for t in PROVAS:
        x = A.ler_titulo(t)
        confere(x and x["tipo"] == "lei" and x["num"] and x["prova"], f"prova: {t!r} -> {x}")
    for t in NAO_LEIS + NAO_VETOS:
        confere(A.ler_titulo(t) is None, f"não é lei nem veto: {t!r} -> {A.ler_titulo(t)}")
    for t in SEM_NUMERO:
        x = A.ler_titulo(t)
        confere(x and x["tipo"] == "lei" and x["num"] is None, f"sem número: {t!r} -> {x}")
    for t, n, ano, parcial in VETOS:
        x = A.ler_titulo(t)
        confere(x and x["tipo"] == "veto" and x["num"] == n and x["ano"] == ano and x["parcial"] == parcial,
                f"veto: {t!r} -> {x}")
    for t, lc, n in LISTA:
        x = A.ler_titulo_lista(t)
        confere(x and x["lc"] == lc and x["num"] == n, f"lista: {t!r} -> {x}")
    for t in LISTA_NAO:
        confere(A.ler_titulo_lista(t) is None, f"lista, não é lei: {t!r} -> {A.ler_titulo_lista(t)}")
    for t in LISTA_SEM_NUMERO:
        x = A.ler_titulo_lista(t)
        confere(x and x["num"] is None, f"lista, sem número: {t!r} -> {x}")
    x = A.ler_titulo_lista("Leis 1754 ate 1760")
    confere(x and x["num"] == 1754 and x.get("mais") == list(range(1755, 1761)), f"várias leis num título -> {x}")

    # contagem: numeração contínua, começo conferido pela última lei de antes do período, um buraco, uma republicação,
    # uma lei promulgada pela Câmara (não conta, mas não é buraco) e um número fora da sequência (erro de digitação)
    itens = [item(f"LEI Nº {n}/2024", "2024-11-10") for n in (98, 99)]
    itens += [item(f"LEI Nº {n}/2025", f"2025-0{1 + n % 9}-10") for n in range(100, 130) if n not in (117, 118)]
    itens += [item("REPUBLICAÇÃO DA LEI Nº 105/2025", "2025-09-01"), item("LEI Nº 118/2025", "2025-07-01", camara=True),
              item("LEI Nº 1/2026", "2026-02-01")]
    itens += [item(f"LEI Nº {n}/2026", "2026-09-10") for n in range(130, 140)]
    r = A.contar_leis(itens, "2025-01-01", "2026-10-26")
    confere(r["ok"] and r["leis"] == 38 and r["promulgadas"] == 1 and r["falta"] == 1 and r["fora_seq"] == 1 and
            r["inicio_conferido"], f"contagem contínua -> {({k: v for k, v in r.items() if k != 'numeros'})}")
    # o começo não confere (a última lei de antes do período não aparece e a numeração não começa em 1)
    r = A.contar_leis([x for x in itens if x["circ"] >= "2025"], "2025-01-01", "2026-10-26")
    confere(not r["ok"] and r["motivo"] == "inicio", f"começo sem conferir -> {r['motivo']}")
    # buracos demais
    poucas = [x for x in itens if (x["lei"] or {}).get("num", 0) % 3]
    r = A.contar_leis(poucas, "2025-01-01", "2026-10-26")
    confere(not r["ok"] and r["motivo"] == "buracos", f"buracos -> {r['motivo']}")
    # parou de publicar
    r = A.contar_leis([x for x in itens if x["circ"] < "2026"], "2025-01-01", "2026-10-26")
    confere(not r["ok"] and r["motivo"] == "parou", f"parou -> {r['motivo']}")
    # numeração que recomeça em 1 a cada ano
    anual = [item(f"LEI Nº {n}/2025", "2025-05-05") for n in range(1, 41)] + \
            [item(f"LEI Nº {n}/2026", "2026-09-05") for n in range(1, 31)]
    r = A.contar_leis(anual, "2025-01-01", "2026-10-26")
    confere(r["ok"] and r["leis"] == 70 and r["modo"] == "anual", f"anual -> {({k: v for k, v in r.items() if k != 'numeros'})}")

    # vetos: numerados por ano a partir de 1 (vale); com buraco (não vale); continuando a numeração de antes (vale)
    def veto(t, circ):
        return {"veto": A.ler_titulo(t), "circ": circ, "id": t + circ}
    v = A.contar_vetos([veto("RAZÕES DE VETO 001/2025", "2025-07-03"), veto("RAZÕES DE VETO 002/2025", "2025-10-14"),
                        veto("RAZÕES DE VETO 001/2026", "2026-05-25")], "2025-01-01", "2026-10-26")
    confere(v["ok"] and v["vetos"] == 3, f"vetos por ano -> {v}")
    v = A.contar_vetos([veto("VETO Nº 001/2025", "2025-07-03"), veto("VETO Nº 003/2025", "2025-10-14")], "2025-01-01",
                       "2026-10-26")
    confere(not v["ok"], f"vetos com buraco -> {v}")
    v = A.contar_vetos([veto("MENSAGEM DE VETO Nº 26, DE 6 DE NOVEMBRO DE 2024", "2024-11-07"),
                        veto("MENSAGEM DE VETO Nº 27, DE 16 DE SETEMBRO DE 2025", "2025-09-18")], "2025-01-01", "2026-10-26")
    confere(v["ok"] and v["vetos"] == 1, f"vetos continuando a numeração -> {v}")
    v = A.contar_vetos([], "2025-01-01", "2026-10-26")
    confere(not v["ok"], f"nenhum veto publicado não é zero vetos -> {v}")

    # Instar (página de legislação dos sites de prefeituras): as categorias de lei do formulário e o "título" guardado no
    # cache (categoria|número|data da lei)
    import _diario_listas as DL
    for rot, esperado in INSTAR_CATS:
        confere(DL.InstarCidade.categoria(rot) == esperado, f"categoria Instar {rot!r} -> {DL.InstarCidade.categoria(rot)}")
    for t, num, ano in INSTAR_NUMS:
        x = DL.InstarCidade.ler_titulo(t)
        confere(x and x["num"] == num and x["ano"] == ano, f"número Instar {t!r} -> {x}")

    # rótulo curto do Diário (link das cidades que ficam fora)
    import diarios as D
    for nome, esperado in ROTULOS:
        confere(D.rotulo_diario(nome) == esperado, f"rótulo {nome!r} -> {D.rotulo_diario(nome)!r}")

    for e in erros:
        print("ERRO:", e)
    total = len(LEIS) + len(PROVAS) + len(NAO_LEIS) + len(NAO_VETOS) + len(SEM_NUMERO) + len(VETOS) + len(LISTA) + \
        len(LISTA_NAO) + len(LISTA_SEM_NUMERO) + len(INSTAR_CATS) + len(INSTAR_NUMS) + len(ROTULOS) + 10
    print(f"{total - len(erros)} de {total} conferências certas")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
