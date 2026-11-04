"""O site é publicado hoje? (Usado pelo robô diário, .github/workflows/atualizar.yml.)

Cada publicação guarda uma cópia inteira do site na Vercel (uns 270 MB), e publicar duas vezes por dia encheu o espaço da
Vercel (11 GB em 4/11/2026). Por isso os robôs continuam lendo as fontes todo dia (as Câmaras e Assembleias são lidas
aos poucos, um pedaço por dia, e o que eles leem vai para o repositório), mas o site só é publicado:
- no dia 1º de cada mês;
- num dia de posse (o site troca de mandato nesse dia; as datas vêm de scripts/mandatos.py);
- quando alguém pede (rodar o robô à mão com "publicar", ou um commit com [publicar] na mensagem).
Quem decide se a Vercel publica é o vercel.json ("ignoreCommand"): ela só publica um commit com [publicar] na mensagem.

Uso: python scripts/publicar_hoje.py [AAAA-MM-DD]   -> imprime "sim" ou "nao" (e o motivo, na saída de erro)
"""
from __future__ import annotations

import os
import sys

import mandatos


def dias_de_posse(ano: int) -> set[str]:
    """Todas as datas de posse no ano (de qualquer cargo, em qualquer estado)."""
    datas = set()
    for eleicao in range(ano - 2, ano):
        for cargo in mandatos.GERAIS + mandatos.MUNICIPAIS:
            for uf in ([None] if cargo != "deputado_estadual" else list(mandatos.POSSE_ESTADUAL) + list(mandatos.POSSE_ESTADUAL_ATE_2022) + [None]):
                d = mandatos.posse(cargo, eleicao, uf)
                if d.startswith(str(ano)):
                    datas.add(d)
    return datas


def motivo(hoje: str) -> str | None:
    if os.environ.get("PUBLICAR", "").lower() in ("1", "true", "sim", "yes"):
        return "pedido à mão"
    if hoje[8:10] == "01":
        return "dia 1º do mês"
    if hoje in dias_de_posse(int(hoje[:4])):
        return "dia de posse"
    return None


def main() -> int:
    hoje = sys.argv[1] if len(sys.argv) > 1 else mandatos._hoje()
    m = motivo(hoje)
    print("sim" if m else "nao")
    print(f"{hoje}: {'publica (' + m + ')' if m else 'não publica (só guarda os dados no repositório)'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
