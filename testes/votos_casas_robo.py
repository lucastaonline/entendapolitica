"""Teste sem rede e sem servidor do scripts/votos_casas.py (site-d-r16): o arquivo de votações recentes de cada Assembleia e
Câmara Municipal, com o voto de cada pessoa. Monta uma pasta de dados de mentira (testes/_votos_casas_tmp/, apagada no fim),
roda o script nela e confere: as duas formas das Assembleias (o que foi votado dentro do perfil, ou num catálogo da Casa),
a Câmara Municipal (catálogo no arquivo da cidade), a ordem (a mais nova primeiro; pessoas em ordem alfabética), o limite de
votações recentes, o placar oficial (ou null), quem não tem perfil fica fora, o arquivo que não muda não é regravado e o de
uma Casa que deixou de ter votações é apagado. No fim, confere os arquivos de verdade de dados/votacoes/ contra os perfis.
Uso: python testes/votos_casas_robo.py"""
import json
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
import votos_casas as V  # noqa: E402

TMP = RAIZ / "testes" / "_votos_casas_tmp"
ok = falhas = 0


def confere(cond, txt, extra=""):
    global ok, falhas
    if cond:
        ok += 1
        print("  ok  ", txt)
    else:
        falhas += 1
        print("  FALHOU", txt, extra)


def grava(rel, obj):
    p = TMP / "dados" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def le(rel):
    return json.loads((TMP / "dados" / rel).read_text(encoding="utf-8"))


def fonte(t):
    return {"veiculo": "Casa", "titulo": t, "url": "https://exemplo.leg.br/" + t, "data": "2026-11-01"}


def monta():
    if TMP.exists():
        shutil.rmtree(TMP)
    # legislativos.json: XX (lista no perfil), YY (catálogo; a última leitura falhou e marcou "votacoes": false, mas os perfis
    # continuam com os votos da última leitura que deu certo: o arquivo é feito do mesmo jeito), ZZ sem nada; a Câmara 1234567
    grava("legislativos.json", {"assembleias": {"XX": {"cobertura": {"votacoes": True}}, "YY": {"cobertura": {"votacoes": False}, "ok": False},
                                                "ZZ": {"cobertura": {"votacoes": False}}},
                                "camaras": {"1234567": {"cobertura": {"votacoes": True}}, "7654321": {"cobertura": {"votacoes": False}}}})
    grava("assembleias/XX.json", {"sigla": "ALXX", "casa": "Assembleia de XX", "casa_en": "XX Assembly", "site": "https://xx.leg.br"})
    grava("assembleias/YY.json", {"sigla": "ALYY", "casa": "Assembleia de YY", "casa_en": "YY Assembly", "site": "https://yy.leg.br"})
    grava("estados/XX.json", {"deputadosEstaduais": {"membros": [
        {"id": "dest-XX-2", "nome": "Zélia", "partido": "B", "foto": None, "genero": "F"},
        {"id": "dest-XX-1", "nome": "Ana", "partido": "A", "foto": "https://xx.leg.br/a.jpg", "genero": "F"},
        {"id": "dest-XX-3", "nome": "Bruno", "partido": "A", "foto": None, "genero": "M"}]}})
    pl = {"Sim": 30, "Não": 5, "Abstenção": 0, "Obstrução": 0, "Outro": 0, "total": 35}

    def item(i, data, voto):
        return {"id": f"alxx-vot:{i}", "voto": voto, "data": data, "proposta": f"PL {i}/2026", "propostaId": f"alxx:{i}", "descricao": f"Projeto {i}",
                "resultado": "Aprovado", "placar": pl, "url": f"https://xx.leg.br/v/{i}"}
    esc = {"escopo": "Votações nominais da ALXX", "escopo_en": "Roll-call votes of the ALXX", "fonte": fonte("alxx")}
    # listas da mais nova para a mais antiga; 3 e 4 no mesmo dia (a 4 vem antes na lista: é a mais nova)
    grava("pessoas/dest-XX-1.json", {"id": "dest-XX-1", "propostas": {"lista": [{"id": "alxx:4", "ementa": "Ementa oficial 4", "url": "https://xx.leg.br/p/4",
                                                                           "s": "Cria a regra 4.", "s_en": "Creates rule 4."}]}, "votacoes": dict(esc, lista=[item(4, "2026-10-02", "Sim"), item(3, "2026-10-02", "Não"), item(1, "2026-09-01", "Sim")])})
    grava("pessoas/dest-XX-2.json", {"id": "dest-XX-2", "votacoes": dict(esc, lista=[item(4, "2026-10-02", "NR"), item(2, "2026-09-15", "Abstenção")])})
    # perfil de quem não está na lista oficial de hoje: fica fora
    grava("pessoas/dest-XX-9.json", {"id": "dest-XX-9", "votacoes": dict(esc, lista=[item(4, "2026-10-02", "Sim")])})
    # YY: catálogo da Casa
    grava("votacoes/alyy.json", {"votacoes": {"alyy-vot:20": {"data": "2026-10-10", "proposta": "PEC 1/2026", "descricao": "PEC", "resultado": "Aprovada", "url": "u20", "propostaId": None},
                                              "alyy-vot:19": {"data": "2026-10-01", "proposta": "PL 9/2026", "descricao": "PL", "resultado": "Rejeitado", "url": "u19", "propostaId": None}},
                                 "fonte": fonte("alyy-cat")})
    grava("estados/YY.json", {"deputadosEstaduais": {"membros": [{"id": "dest-YY-1", "nome": "Carla", "partido": "C", "foto": None, "genero": "F"},
                                                                 {"id": "dest-YY-2", "nome": "Davi", "partido": "D", "foto": None, "genero": "M"}]}})
    escy = {"escopo": "Votações da ALYY", "fonte": fonte("alyy"), "arquivo": "dados/votacoes/alyy.json"}
    grava("pessoas/dest-YY-1.json", {"id": "dest-YY-1", "votacoes": dict(escy, votos=[["alyy-vot:20", "Sim"], ["alyy-vot:19", "Não"]])})
    grava("pessoas/dest-YY-2.json", {"id": "dest-YY-2", "votacoes": dict(escy, votos=[["alyy-vot:20", "Não"], ["alyy-vot:99", "Sim"]])})
    # Câmara Municipal 1234567 (UF XX): catálogo no arquivo da cidade; nomes da lista oficial e da ficha da cidade
    grava("camaras/1234567.json", {"uf": "XX", "ibge": "1234567", "sigla": "CMT", "casa": "Câmara Municipal de Teste", "casa_en": "Teste City Council",
                                   "site": "https://cm.leg.br", "membros": [{"id": "ver-1234567-1", "nome": "Edu", "partido": "E", "foto": None, "genero": "M"}]})
    grava("cidades/XX/1234567.json", {"vereadores": {"membros": [{"id": "ver-1234567-1", "nome": "Edu", "partido": "E"},
                                                                 {"id": "ver-1234567-2", "nome": "Bia", "partido": "F", "foto": "https://f/2.jpg", "genero": "F"}]}})
    cat = {f"cm1234567-vot:{i}": {"data": f"2026-0{i}-01", "proposta": f"PLO {i}/2026", "descricao": f"PLO {i}", "resultado": "Aprovado",
                                  "placar": {"Sim": 9, "Não": 0, "Abstenção": 0, "total": 9}, "url": f"u{i}"} for i in (5, 4, 3, 2, 1)}
    ev = {"escopo": "Votações da CMT", "fonte": fonte("cmt"), "arquivo": "dados/camaras/extras/1234567.json"}
    grava("camaras/extras/1234567.json", {"votacoes": cat, "pessoas": {
        "ver-1234567-1": {"votacoes": dict(ev, votos=[[f"cm1234567-vot:{i}", "Sim"] for i in (5, 4, 3, 2, 1)])},
        "ver-1234567-2": {"votacoes": dict(ev, votos=[["cm1234567-vot:5", "Não"]])},
        "pref-1234567": {"votacoes": dict(ev, votos=[["cm1234567-vot:5", "Sim"]])}}})
    # um arquivo velho de uma Casa que não tem mais votações (deve sumir)
    grava("votacoes/assembleias/ZZ.json", {"velho": True})
    grava("votacoes/camaras/7654321.json", {"velho": True})


def aponta():
    d = TMP / "dados"
    V.DADOS, V.PESSOAS, V.EXTRAS_CIDADES = d, d / "pessoas", d / "camaras" / "extras"
    V.SAIDA_ALE, V.SAIDA_CAM = d / "votacoes" / "assembleias", d / "votacoes" / "camaras"


def roda():
    monta()
    aponta()
    V.RECENTES = 30
    r = V.gravar()
    print("gravar():", r)
    confere(r.startswith("2 Assembleias e 1 Câmara"), "duas Assembleias (também a que a última leitura marcou sem votações) e uma Câmara gravadas", r)
    confere(not (TMP / "dados/votacoes/assembleias/ZZ.json").exists() and not (TMP / "dados/votacoes/camaras/7654321.json").exists(),
            "o arquivo de uma Casa sem votações é apagado")
    x = le("votacoes/assembleias/XX.json")
    confere(x["casa"] == "ALXX" and x["nome"] == "Assembleia de XX" and x["nome_en"] == "XX Assembly" and x["site"] == "https://xx.leg.br", "nome, sigla e site da Casa")
    confere([p[0] for p in x["pessoas"]] == ["dest-XX-1", "dest-XX-2"], "pessoas: só quem tem voto e está na lista oficial, em ordem alfabética", x["pessoas"])
    confere(x["pessoas"][0] == ["dest-XX-1", "Ana", "A", "https://xx.leg.br/a.jpg", "F"], "pessoa com nome, partido, foto e gênero")
    confere([v["id"] for v in x["votacoes"]] == ["alxx-vot:4", "alxx-vot:3", "alxx-vot:2", "alxx-vot:1"], "da mais nova para a mais antiga (desempate pela ordem da lista)",
            [v["id"] for v in x["votacoes"]])
    v4 = x["votacoes"][0]
    confere(v4["votos"] == {"Sim": [0], "NR": [1]}, "votos por grupo, com o índice da pessoa (quem não está na lista fica fora)", v4["votos"])
    confere(v4["placar"]["total"] == 35 and v4["proposta"] == "PL 4/2026" and v4["url"] == "https://xx.leg.br/v/4", "placar oficial, proposta e link")
    confere(v4.get("s") == "Cria a regra 4." and v4.get("s_en") == "Creates rule 4." and v4.get("ementa") == "Ementa oficial 4" and v4.get("urlProposta") == "https://xx.leg.br/p/4"
            and "s" not in x["votacoes"][1] and "ementa" not in x["votacoes"][1], "do que se trata: a ementa, a página e a explicação simples da proposta, achadas pelo id nos perfis")
    confere(x["total"] == 4 and x["recentes"] == 4 and x["escopo"] == "Votações nominais da ALXX" and x["escopo_en"] == "Roll-call votes of the ALXX", "total, recentes e escopo")
    confere(len(x["fontes"]) == 1 and x["fontes"][0]["url"].endswith("alxx"), "fontes sem repetir")
    y = le("votacoes/assembleias/YY.json")
    confere([v["id"] for v in y["votacoes"]] == ["alyy-vot:20", "alyy-vot:19"] and y["votacoes"][0]["placar"] is None, "catálogo da Casa: ordem e placar null (a Casa não publica o placar junto)")
    confere(y["votacoes"][0]["votos"] == {"Sim": [0], "Não": [1]} and y["votacoes"][1]["votos"] == {"Não": [0]}, "catálogo: voto de cada pessoa; chave fora do catálogo não entra")
    confere({f["url"] for f in y["fontes"]} == {"https://exemplo.leg.br/alyy", "https://exemplo.leg.br/alyy-cat"}, "fontes do perfil e do catálogo")
    c = le("votacoes/camaras/1234567.json")
    confere(c["ibge"] == "1234567" and c["uf"] == "XX" and c["casa"] == "CMT", "Câmara: ibge, UF e sigla")
    confere([p[:3] for p in c["pessoas"]] == [["ver-1234567-2", "Bia", "F"], ["ver-1234567-1", "Edu", "E"]], "Câmara: nomes da lista oficial e da ficha da cidade; o prefeito não entra", c["pessoas"])
    confere(c["votacoes"][0]["votos"] == {"Não": [0], "Sim": [1]} and c["votacoes"][0]["placar"]["total"] == 9, "Câmara: votos e placar oficial")
    # limite de recentes
    V.RECENTES = 2
    V.gravar()
    c2 = le("votacoes/camaras/1234567.json")
    confere(c2["total"] == 5 and c2["recentes"] == 2 and [v["id"] for v in c2["votacoes"]] == ["cm1234567-vot:5", "cm1234567-vot:4"], "só as N mais novas; o total continua")
    # não regrava quando nada mudou (nem o dia)
    arq = TMP / "dados/votacoes/camaras/1234567.json"
    dado = json.loads(arq.read_text(encoding="utf-8"))
    dado["atualizado"] = "2000-01-01"
    arq.write_bytes((json.dumps(dado, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    antes = arq.read_bytes()
    V.gravar()
    confere(arq.read_bytes() == antes, "sem mudança de verdade, o arquivo não é regravado (a data fica a de antes)")
    shutil.rmtree(TMP)
    confere(not TMP.exists(), "pasta de teste apagada")


def reais():
    """Os arquivos de verdade conferem com os perfis: cada voto do arquivo é o voto daquela pessoa no perfil dela."""
    dados = RAIZ / "dados"
    for uf in ("CE", "AM", "RS"):
        arq = dados / "votacoes" / "assembleias" / f"{uf}.json"
        if not arq.exists():
            confere(False, f"dados/votacoes/assembleias/{uf}.json existe")
            continue
        d = json.loads(arq.read_text(encoding="utf-8"))
        erros = 0
        for v in d["votacoes"][:10]:
            for voto, idxs in v["votos"].items():
                for i in idxs:
                    pid = d["pessoas"][i][0]
                    p = json.loads((dados / "pessoas" / f"{pid}.json").read_text(encoding="utf-8"))["votacoes"]
                    achou = [x["voto"] for x in p.get("lista") or [] if x["id"] == v["id"]] + [x[1] for x in p.get("votos") or [] if x[0] == v["id"]]
                    if achou != [voto]:
                        erros += 1
        confere(erros == 0 and len(d["votacoes"]) == min(V.RECENTES, d["total"]), f"{uf}: os votos das 10 mais novas batem com os perfis", erros)
    cams = sorted((dados / "votacoes" / "camaras").glob("*.json"))
    n_cob = 0
    for f in (dados / "camaras" / "extras").glob("*.json"):
        x = json.loads(f.read_text(encoding="utf-8"))
        if any(pid.startswith("ver-") and (p.get("votacoes") or {}).get("votos") for pid, p in (x.get("pessoas") or {}).items()):
            n_cob += 1
    confere(len(cams) == n_cob, f"um arquivo por Câmara com o voto de algum vereador guardado ({len(cams)} de {n_cob})")
    maior = max((f.stat().st_size for f in cams), default=0)
    confere(maior < 60 * 1024, f"o maior arquivo de Câmara tem menos de 60 KB ({maior // 1024} KB)")


if __name__ == "__main__":
    V.RECENTES = 30
    roda()
    V.RECENTES = 30
    reais()
    print(f"\n{ok} ok, {falhas} falhas")
    sys.exit(1 if falhas else 0)
