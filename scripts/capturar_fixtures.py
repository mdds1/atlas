#!/usr/bin/env python3
"""Roda cada script de leitura no PC (por `ssh win`, só leitura) e grava a saída
em tests/fixtures/<nome>.json, para os testes usarem dados reais.

As amostras trazem nomes reais de programas, serviços e eventos do PC. O
repositório é local; não publique sem conferir.
"""
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from jarvis_pc.leitura import DEFINICOES, ler_script  # noqa: E402
from jarvis_pc.ps import montar_argv  # noqa: E402

DESTINO = RAIZ / "tests" / "fixtures"


def capturar(definicao):
    argv = ["ssh", "win"] + montar_argv(ler_script(definicao.arquivo), json=True)
    p = subprocess.run(argv, capture_output=True, timeout=definicao.timeout + 30)
    saida = p.stdout.decode("utf-8", "replace")
    dados = json.loads(saida)  # levanta erro se não for JSON
    (DESTINO / f"{definicao.arquivo}.json").write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return len(saida)


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    falhas = 0
    for d in DEFINICOES:
        try:
            print(f"{d.arquivo}: {capturar(d)} bytes")
        except Exception as erro:
            falhas += 1
            print(f"{d.arquivo}: FALHOU ({type(erro).__name__}: {erro})")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
