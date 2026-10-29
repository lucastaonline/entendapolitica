"""O que o scripts/tse.py faz com os arquivos de 2024 do TSE que são baixados de novo toda semana (as eleições
suplementares entram neles): no máximo uma vez por semana do calendário, o arquivo de antes fica quando o TSE não
responde (e os outros da rodada nem tentam), sem arquivo e sem rede o erro sobe, --cache não pede nada, e o nome do cache
do GitHub Actions muda com a semana. Sem servidor e sem rede: tudo numa pasta à parte (.cache/teste-prefeitos-robo,
apagada no fim); o .cache/tse de verdade não é tocado.
Uso: python testes/prefeitos_robo.py"""
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
import mandatos  # noqa: E402
import tse  # noqa: E402

RES = []
PASTA = RAIZ / ".cache" / "teste-prefeitos-robo"


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def main():
    shutil.rmtree(PASTA, ignore_errors=True)
    PASTA.mkdir(parents=True)
    tse.CACHE_TSE, tse.SEMANAL_REG = PASTA, PASTA / "semanais.json"
    pedidos, falhar, dia = [], [False], ["2026-10-29"]
    tse.hoje = lambda: dia[0]
    mandatos._hoje = lambda: dia[0]

    def baixar(url, nome_cache, max_idade_h=20, **kw):
        pedidos.append(url)
        if falhar[0]:
            raise RuntimeError("o TSE não respondeu (simulado)")
        p = PASTA / Path(nome_cache).name
        p.write_text(f"novo {dia[0]}", encoding="utf-8")
        return p

    tse.baixar_arquivo = baixar
    cand, vot = PASTA / "consulta_cand_2024.zip", PASTA / "votacao_candidato_munzona_2024.zip"
    cand.write_text("antigo", encoding="utf-8")
    vot.write_text("antigo", encoding="utf-8")

    ok("só as candidaturas e os votos de 2024 são semanais (o 2022 e o 2026, não)",
       tse.renova_semanal("consulta_cand", 2024) and tse.renova_semanal("votacao_candidato_munzona", 2024)
       and not tse.renova_semanal("consulta_cand", 2022) and not tse.renova_semanal("bem_candidato", 2024))
    # 1. sem registro (primeira rodada com o código novo): baixa e grava o dia
    p = tse.zip_tse("consulta_cand", 2024)
    reg = tse.ler_json(tse.SEMANAL_REG, {})
    ok("1ª rodada: baixa de novo e anota o dia em semanais.json", len(pedidos) == 1 and p == cand
       and cand.read_text(encoding="utf-8") == "novo 2026-10-29" and reg.get(cand.name) == "2026-10-29", str(reg))
    # 2. outro dia da mesma semana (domingo, 01/11): não pede nada
    dia[0] = "2026-11-01"
    tse.zip_tse("consulta_cand", 2024)
    ok("mesma semana: não pede de novo", len(pedidos) == 1, str(pedidos))
    # 3. semana seguinte com o TSE fora do ar: fica o arquivo de antes, e o outro arquivo semanal nem tenta
    dia[0], falhar[0] = "2026-11-02", True
    p1 = tse.zip_tse("consulta_cand", 2024)
    n = len(pedidos)
    p2 = tse.zip_tse("votacao_candidato_munzona", 2024)
    ok("TSE fora do ar: fica o arquivo de antes (o robô não quebra) e o outro arquivo semanal nem tenta",
       p1 == cand and cand.read_text(encoding="utf-8") == "novo 2026-10-29" and p2 == vot and len(pedidos) == n == 2
       and tse._FALHA_SEMANAL == [cand.name], f"{pedidos} | {tse._FALHA_SEMANAL}")
    ok("o registro continua com o último download que deu certo", tse.ler_json(tse.SEMANAL_REG, {}).get(cand.name) == "2026-10-29")
    # 4. sem o arquivo e sem rede: o erro sobe (como antes)
    tse._FALHA_SEMANAL.clear()
    vot.unlink()
    try:
        tse.zip_tse("votacao_candidato_munzona", 2024)
        subiu = False
    except RuntimeError:
        subiu = True
    ok("sem o arquivo no cache e sem rede: o erro sobe (o passo do TSE falha, como antes)", subiu)
    # 5. o TSE voltou: baixa, na semana seguinte
    falhar[0] = False
    tse.zip_tse("consulta_cand", 2024)
    ok("o TSE voltou: baixa e anota o dia", cand.read_text(encoding="utf-8") == "novo 2026-11-02"
       and tse.ler_json(tse.SEMANAL_REG, {}).get(cand.name) == "2026-11-02")
    # 6. --cache (sem rede): nada é pedido, mesmo numa semana nova
    dia[0], n = "2026-11-09", len(pedidos)
    tse.SEM_REDE = True
    tse.zip_tse("consulta_cand", 2024)
    tse.SEM_REDE = False
    ok("--cache: nenhum pedido à internet", len(pedidos) == n)
    # 7. o nome do cache do Actions
    dia[0] = "2026-10-29"
    c1 = tse.chave_cache()
    dia[0] = "2026-11-02"
    c2 = tse.chave_cache()
    dia[0] = "2029-01-02"  # posse dos eleitos de 2028: o 2024 deixa de ser semanal
    sem24 = not tse.renova_semanal("consulta_cand", 2024)
    ok("o nome do cache muda com a semana (o arquivo novo é guardado) e o 2024 deixa de ser semanal na posse de 2029",
       c1 == "tse-2022-2024-s2026-44" and c2 == "tse-2022-2024-s2026-45" and sem24, f"{c1} | {c2}")
    # 8. o CPF "-4" dos dados abertos de 2024 não é CPF
    ok("cpf_valido: '-4', '#NULO' e vazio não são CPF; um CPF de verdade passa",
       tse.cpf_valido("-4") is None and tse.cpf_valido("#NULO#") is None and tse.cpf_valido("") is None
       and tse.cpf_valido("123.456.789-01") == "12345678901")
    # 9. o prazo do art. 14, § 6º
    ok("seis_meses_antes: 04/10/2026 -> 04/04/2026", tse.seis_meses_antes("2026-10-04") == "2026-04-04")
    # 10. o DivulgaCandContas recusa o robô do GitHub (HTTP 403 fora do Brasil): vale o que ficou guardado numa rodada
    # que deu certo (dados/tse/divulga_2024.json); sem isso, as cidades com o resultado de 2024 "sem definição" ficavam
    # sem prefeito e sem vereadores, e quem foi eleito numa suplementar ficava sem foto (robô de 29/10/2026)
    tse.RESERVA_DIVULGA = PASTA / "divulga_2024.json"
    tse._RESERVA_DIV.clear()
    tse._RESERVA_DIV_MUDOU.clear()
    resp = {"candidatura/listar/2024/16675/2045202024/11/candidatos": {"candidatos": [
                {"id": 200001889942, "descricaoTotalizacao": "Eleito"},
                {"id": 200002198765, "descricaoTotalizacao": "Não eleito"}]},
            "eleicao/suplementares/2024/MA": [{"siglaUF": "08850", "dataEleicao": "2026-12-06T08:00:00", "id": 10652002026}]}
    recusa = [False]
    pedidos_div = []

    def divulga(caminho, cache):
        pedidos_div.append(caminho)
        if recusa[0]:
            raise RuntimeError(f"Falha ao baixar {caminho}: HTTP Error 403: Forbidden (simulado)")
        return resp[caminho]

    tse.divulga_json = divulga
    t1, s1 = tse.divulga_totalizacao_2024("16675", 11), tse.ids_suplementares_2024({"MA"})
    tse.salvar_reserva_divulga()
    guardado = tse.ler_json(tse.RESERVA_DIVULGA, {})
    ok("o DivulgaCandContas respondeu: guarda quem foi eleito e os ids das eleições suplementares",
       t1.get("200001889942") == "ELEITO" and guardado.get("totalizacao/16675/11") == {"200001889942": "ELEITO"}
       and guardado.get("suplementares/MA") == [["08850", "2026-12-06", "10652002026"]], str(guardado))
    tse._RESERVA_DIV.clear()  # outra rodada (o robô): começa lendo o arquivo
    recusa[0] = True
    t2, s2 = tse.divulga_totalizacao_2024("16675", 11), tse.ids_suplementares_2024({"MA"})
    ok("o DivulgaCandContas recusou: vale o que ficou guardado (o mesmo eleito e o mesmo id da suplementar)",
       t2 == {"200001889942": "ELEITO"} and s2 == s1 == {("08850", "2026-12-06"): "10652002026"}, f"{t2} | {s2}")
    antes = tse.RESERVA_DIVULGA.read_bytes()
    tse.salvar_reserva_divulga()
    ok("recusou com tudo guardado: o arquivo guardado não muda",
       not tse._RESERVA_DIV_MUDOU and tse.RESERVA_DIVULGA.read_bytes() == antes)
    falta_t, falta_s = tse.divulga_totalizacao_2024("99999", 11), tse.ids_suplementares_2024({"AC"})
    tse.salvar_reserva_divulga()
    g = tse.ler_json(tse.RESERVA_DIVULGA, {})
    ok("recusou sem nada guardado: None e nenhuma suplementar (como antes), e o pedido fica anotado em _faltam",
       falta_t is None and falta_s == {} and g.get("_faltam") == ["suplementares/AC", "totalizacao/99999/11"],
       str(g.get("_faltam")))
    # do Brasil (scripts/atualizar_do_brasil.py): tse.py --so-divulga pede de novo tudo o que está guardado e o que falta
    recusa[0] = False
    resp["candidatura/listar/2024/99999/2045202024/11/candidatos"] = {"candidatos": [{"id": 1, "descricaoTotalizacao": "Eleito"}]}
    resp["eleicao/suplementares/2024/AC"] = []
    pedidos_div.clear()
    tse.renovar_reserva_divulga()
    g = tse.ler_json(tse.RESERVA_DIVULGA, {})
    ok("--so-divulga (do Brasil): pede tudo de novo, guarda o que faltava e limpa _faltam",
       "_faltam" not in g and g.get("totalizacao/99999/11") == {"1": "ELEITO"} and g.get("suplementares/AC") == []
       and g.get("totalizacao/16675/11") == {"200001889942": "ELEITO"} and len(pedidos_div) == 4,
       f"{len(pedidos_div)} pedidos | {sorted(k for k in g if k != '_')}")
    # 11. eleito segundo o DivulgaCandContas, com os votos "Anulado sub judice" nos dados abertos (0 válidos): a ficha
    # não diz "0 votos" (Equador, RN, em 29/10/2026)
    base = {"el": "619", "ue": "16675", "uf": "RN", "dt": "2024-10-06", "turno": 1, "genero": "M"}
    pref = dict(base, cargo="PREFEITO", urna="PROFESSOR CLETSON", civil="CLETSON RIVALDO DE OLIVEIRA",
                sq="200001889942", partido="MDB")
    vice = dict(base, cargo="VICE-PREFEITO", urna="CAIO SABINO", civil="CAIO CESAR FERREIRA DE OLIVEIRA",
                sq="200002366738", partido="PODE")
    v0 = {"votos": {"200001889942|1": 0}, "data": "2026-10-29"}
    p = tse._pessoa_cidade(pref, "pref-2403400", pref, v0, "2026-10-29", {}, True, "ELEITO")
    v = tse._pessoa_cidade(vice, "vpref-2403400", pref, v0, "2026-10-29", {}, True, "ELEITO")
    p2 = tse._pessoa_cidade(pref, "pref-2403400", pref, {"votos": {"200001889942|1": 2216}, "data": "2026-10-29"},
                            "2026-10-29", {}, True, "ELEITO")
    ok("eleito segundo o DivulgaCandContas: sem '0 votos' (nem 'da chapa'); com votos válidos, o número fica",
       p["votos"] is None and v["votos"] is None and "votosDaChapa" not in v and p2["votos"] == 2216
       and p["situacao"] == "Eleito em 2024 (segundo o DivulgaCandContas)", f"{p['votos']} | {v['votos']} | {p2['votos']}")
    shutil.rmtree(PASTA, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} ok")
    sys.exit(0 if all(RES) else 1)


main()
