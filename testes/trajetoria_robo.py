"""Teste sem rede e sem servidor do scripts/trajetoria.py: a ligação entre eleições (CPF, título de eleitor, nome civil +
nascimento, homônimos que não podem se juntar, 2024 sem CPF), o resultado de cada candidatura (turnos, vice na chapa),
o balde de cada id (a mesma conta do js/trajetoria.js) e o formato curto do arquivo.

Uso: python testes/trajetoria_robo.py
"""
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
import trajetoria as T  # noqa: E402

falhas = []


def ok(cond, msg):
    print(("  ok   " if cond else "  FALHA ") + msg)
    if not cond:
        falhas.append(msg)


def linha(ano, cargo, nome, nasc, cpf="", tit="", sit="ELEITO", sq=None, ue="SP", uf="SP", num="10", turno="1", ordi="1",
          el=None, urna=None, partido="PX"):
    f = [""] * len(T.CAMPOS)
    v = dict(el=el or f"{ano}1", ord=ordi, turno=turno, dt=f"{ano}-10-0{turno}", uf=uf, ue=ue, nm_ue="X", cargo=cargo,
             sq=sq or f"{ano}{len(nome)}{num}{turno}", num=num, nome=nome, urna=urna or nome.split()[0], partido=partido, sit=sit,
             sitc="", det="", cpf=cpf, tit=tit, nasc=nasc, g="F",
             nk=T.chave_nn(nome, nasc), sk="", mk=T.chave_corte(nome, nasc) if ano in T.CORTADOS and len(nome) >= 30 else "")
    for k, x in v.items():
        f[T.I[k]] = x
    return f


def monta(rows):
    """rows: [(rótulo, ano, linha)] -> linhas no formato do script, ligação e índices."""
    linhas = {(ano, n): (f, ano, "S") for n, (_, ano, f) in enumerate(rows)}
    rot = {(ano, n): r for n, (r, ano, _) in enumerate(rows)}
    u, conflitos = T.ligar(linhas)
    comps, idx, tits = T.indices(linhas, u)
    return linhas, rot, u, conflitos, comps, idx, tits


def mesma(u, rot, a, b):
    ra = [k for k, v in rot.items() if v == a][0]
    rb = [k for k, v in rot.items() if v == b][0]
    return u.acha(ra) == u.acha(rb)


print("== ligação")
rows = [
    # 1. CPF: o nome mudou (casamento), o CPF é o mesmo
    ("ana18", 2018, linha(2018, "DEPUTADO ESTADUAL", "ANA MARIA SOUZA", "1970-01-02", cpf="11111111111", tit="9001")),
    ("ana22", 2022, linha(2022, "DEPUTADO FEDERAL", "ANA MARIA SOUZA LIMA", "1970-01-02", cpf="11111111111", tit="9001")),
    # 2. nome civil + nascimento: 1996 não tem CPF nem título
    ("ana96", 1996, linha(1996, "VEREADOR", "ANA MARIA SOUZA", "1970-01-02")),
    # 3. homônimos: mesmo nome e nascimento, CPFs diferentes; a linha de 1996 sem CPF não pode ir para nenhum dos dois
    ("joseA", 2000, linha(2000, "VEREADOR", "JOSE CARLOS DA SILVA", "1960-05-05", cpf="22222222222", tit="8001")),
    ("joseB", 2004, linha(2004, "VEREADOR", "JOSE CARLOS DA SILVA", "1960-05-05", cpf="33333333333", tit="8002", ue="RJ", uf="RJ")),
    ("jose96", 1996, linha(1996, "VEREADOR", "JOSE CARLOS DA SILVA", "1960-05-05")),
    # 4. 2024 sem CPF: liga pelo título (mesmo nascimento)
    ("bia20", 2020, linha(2020, "VEREADOR", "BEATRIZ COSTA", "1985-03-04", cpf="44444444444", tit="7001")),
    ("bia24", 2024, linha(2024, "VEREADOR", "BEATRIZ COSTA", "1985-03-04", tit="7001")),
    # 5. mesmo título, nascimento muito diferente e nome diferente: não junta
    ("tit_x", 2024, linha(2024, "VEREADOR", "PEDRO ALVES", "1999-09-09", tit="7001")),
    # 6. título com erro de um algarismo no nascimento e o mesmo nome: junta
    ("caio16", 2016, linha(2016, "VEREADOR", "CAIO PRADO", "1975-06-15", cpf="55555555555", tit="6001")),
    ("caio24", 2024, linha(2024, "VEREADOR", "CAIO PRADO", "1975-06-16", tit="6001")),
    # 7. homônimo com outro nascimento: nunca junta
    ("caio_outro", 2024, linha(2024, "VEREADOR", "CAIO PRADO", "1990-01-01", tit="6999")),
    # 8. nome cortado em 30 letras (1994) + nascimento
    ("long94", 1994, linha(1994, "DEPUTADO ESTADUAL", "MARIA DAS GRACAS FONSECA PEREI", "1950-07-07")),
    ("long98", 1998, linha(1998, "DEPUTADO ESTADUAL", "MARIA DAS GRACAS FONSECA PEREIRA", "1950-07-07", cpf="66666666666", tit="5001")),
]
linhas, rot, u, conflitos, comps, idx, tits = monta(rows)
ok(mesma(u, rot, "ana18", "ana22"), "CPF liga 2018 e 2022 (o nome mudou)")
ok(mesma(u, rot, "ana18", "ana96"), "nome civil + nascimento liga 1996 (sem CPF) à mesma pessoa")
ok(not mesma(u, rot, "joseA", "joseB"), "homônimos (mesmo nome e nascimento, CPFs diferentes) ficam separados")
ok(not mesma(u, rot, "jose96", "joseA") and not mesma(u, rot, "jose96", "joseB"), "a linha de 1996 sem CPF dos homônimos não vai para nenhum")
ok(any(k.startswith("NJOSE CARLOS DA SILVA") for k, _ in conflitos), "o conflito vai para a lista de conferência")
ok(mesma(u, rot, "bia20", "bia24"), "2024 sem CPF: liga pelo título de eleitor (mesmo nascimento)")
ok(not mesma(u, rot, "bia24", "tit_x"), "mesmo título com outro nome e outro nascimento não junta")
ok(mesma(u, rot, "caio16", "caio24"), "título + mesmo nome com 1 algarismo diferente no nascimento junta (erro de digitação)")
ok(not mesma(u, rot, "caio24", "caio_outro"), "homônimo com outro nascimento nunca junta")
ok(mesma(u, rot, "long94", "long98"), "1994: nome cortado em 30 letras + nascimento liga")
ok(T.quase_igual("1975-06-12", "1975-12-06") and not T.quase_igual("1975-06-12", "1980-01-01"), "dia e mês trocados contam como erro de digitação; datas bem diferentes, não")

print("== quem é a pessoa do perfil (âncora)")
p = {"id": "dep-1", "tipo": "dep", "nome": "Ana", "nomeCivil": "ANA MARIA SOUZA LIMA", "nasc": "1970-01-02", "cpf": "11111111111",
     "seeds": {"C11111111111", "N" + T.chave_nn("ANA MARIA SOUZA LIMA", "1970-01-02")}, "esperado": {"c": {"dep"}, "uf": "SP"}}
r, como = T.ancora(p, idx, comps, u, linhas)
ok(r is not None and como == "cpf", f"deputada achada pelo CPF ({como})")
p2 = {"id": "x", "tipo": "sen", "nome": "José", "nomeCivil": "JOSE CARLOS DA SILVA", "nasc": "1960-05-05", "cpf": None,
      "seeds": {"N" + T.chave_nn("JOSE CARLOS DA SILVA", "1960-05-05")}, "esperado": {"c": {"sen"}, "uf": "SP"}}
r2, como2 = T.ancora(p2, idx, comps, u, linhas)
ok(r2 is None and como2 == "duvida", f"homônimos sem nada que separe: fica em dúvida, sem candidaturas ({como2})")
p3 = dict(p2, esperado={"c": {"ver"}, "uf": "RJ"})
r3, como3 = T.ancora(p3, idx, comps, u, linhas)
ok(r3 is not None and r3 == u.acha([k for k, v in rot.items() if v == "joseB"][0]), "homônimos: o cargo e o estado esperados escolhem a pessoa")
p4 = dict(p2, nomeCivil="FULANO DE TAL", seeds={"N" + T.chave_nn("FULANO DE TAL", "1960-05-05")})
ok(T.ancora(p4, idx, comps, u, linhas) == (None, "nao-achou"), "quem nunca concorreu: nenhuma candidatura")

print("== resultado de cada candidatura")
ok(T.cod_sit(linha(2022, "DEPUTADO FEDERAL", "A B", "1970-01-01", sit="ELEITO POR QP")) == "eqp", "ELEITO POR QP")
ok(T.cod_sit(linha(1998, "DEPUTADO FEDERAL", "A B", "1970-01-01", sit="MÉDIA")) == "emed", "MÉDIA (1998) = eleito por média")
ok(T.cod_sit(linha(2010, "DEPUTADO FEDERAL", "A B", "1970-01-01", sit="REGISTRO NEGADO ANTES DA ELEIÇÃO")) == "neg", "registro negado")
ok(T.cod_sit(linha(2002, "DEPUTADO FEDERAL", "A B", "1970-01-01", sit="RENÚNCIA/FALECIMENTO/CASSAÇÃO APÓS A ELEIÇÃO")) == "rena", "renúncia/cassação depois da eleição")
f_in = linha(2018, "PRESIDENTE", "A B", "1970-01-01", sit="NULO")
f_in[T.I["sitc"]] = "INAPTO"
ok(T.cod_sit(f_in) == "inapto", "candidatura inapta (2018 em diante)")
t1 = linha(2022, "GOVERNADOR", "CARLA DIAS", "1970-01-01", sit="2º TURNO", turno="1", sq="77")
t2 = linha(2022, "GOVERNADOR", "CARLA DIAS", "1970-01-01", sit="ELEITO", turno="2", sq="77")
ok(T.resultado([(t1, 2022), (t2, 2022)])[:2] == ("e", 2), "2º turno: eleita no 2º turno")
t2n = linha(2022, "GOVERNADOR", "CARLA DIAS", "1970-01-01", sit="NÃO ELEITO", turno="2", sq="77")
ok(T.resultado([(t1, 2022), (t2n, 2022)])[:2] == ("ne", 2), "2º turno: não eleita no 2º turno")
# vice: o resultado vem da chapa (mesmo lugar e número)
vice = linha(2020, "VICE-PREFEITO", "LUIS VICE", "1980-01-01", cpf="88888888888", tit="4001", sit="NULO", num="15", ue="71072")
tit_ = linha(2020, "PREFEITO", "TITULAR NOME", "1970-01-01", cpf="99999999999", tit="4002", sit="ELEITO", num="15", ue="71072", urna="TITULAR")
linhas2 = {(2020, 0): (vice, 2020, "S"), (2020, 1): (tit_, 2020, "K")}
u2, _ = T.ligar(linhas2)
comps2, idx2, tits2 = T.indices(linhas2, u2)
its = T.itens_tse(comps2[u2.acha((2020, 0))], linhas2, tits2, lambda a: {"votos": {}}, {"nome": "Luis", "nomeCivil": "LUIS VICE"})
ok(len(its) == 1 and its[0]["r"] == "e" and its[0]["ch"]["n"] == "Titular", f"vice eleito na chapa do titular: {its}")

print("== balde (Python = JavaScript) e formato curto")
ids = ["dep-204379", "sen-5672", "ver-2927408-50001957281", "stf-flavio-dino", "e26-AP-30002530514", "min-saude"]
js = (RAIZ / "js" / "trajetoria.js").read_text(encoding="utf-8")
cod = ("var window={EP:{esc:function(s){return s},tr:function(a){return a},json:function(){}}};" + js +
       ";console.log(JSON.stringify(" + json.dumps(ids) + ".map(window.EP.trajetoria.balde)))")
import shutil  # noqa: E402
node = shutil.which("node")
if node:
    out = subprocess.run([node, "-"], input=cod, capture_output=True, text=True, encoding="utf-8", timeout=60).stdout.strip()
    ok(json.loads(out or "null") == [T.balde(i) for i in ids], f"balde igual em Python e JavaScript: {out}")
    # perfil-mandato-r10: o balde das listas de propostas dos mandatos antigos (dados/trajetoria/propostas/, 64 baldes)
    ks = ["camara-139289", "senado-5207", "camara-80815"]
    cod2 = cod.rsplit(";console.log", 1)[0] + ";console.log(JSON.stringify(" + json.dumps(ks) + ".map(function(k){return window.EP.trajetoria.baldePropostas(k)})))"
    out2 = subprocess.run([node, "-"], input=cod2, capture_output=True, text=True, encoding="utf-8", timeout=60).stdout.strip()
    ok(json.loads(out2 or "null") == [T.balde(k, T.N_BALDES_PROP) for k in ks], f"balde das propostas por mandato igual em Python e JavaScript: {out2}")
else:
    print("  (sem node: balde em JavaScript não conferido)")
it = {"k": "c", "a": 2024, "c": "ver", "uf": "BA", "ue": "38490", "p": "PT", "r": "e", "v": 100, "sq": "5", "hoje": 1}
ok(T.compacto(it) == [2024, "ver", "38490", "PT", "e", 100, "5", {"hoje": 1}], f"formato curto: {T.compacto(it)}")
ok(T.compacto({"k": "c", "a": 1994, "c": "pres", "uf": "BR", "p": "PT", "r": "ne"}) == [1994, "pres", "BR", "PT", "ne"], "formato curto sem votos e sem SQ")

print(f"\n{'TUDO CERTO' if not falhas else str(len(falhas)) + ' FALHA(S)'}")
sys.exit(1 if falhas else 0)
