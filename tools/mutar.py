#!/usr/bin/env python3
"""Mutação manual: troca um trecho único, roda os testes e restaura o arquivo.

Uso: tools/mutar.py ARQUIVO "trecho original" "trecho sabotado"

Sai com 0 se os testes PEGARAM a sabotagem (falharam), com 1 se ESCAPOU e com 2
se o trecho não é único. O arquivo volta ao texto original em qualquer caso.

Os testes rodam com -B e sem nenhum __pycache__ antes: o Python só confere a
data (em segundos) e o tamanho do fonte, então uma sabotagem trocada e
restaurada no mesmo segundo, com o mesmo tamanho, reaproveitaria o bytecode da
versão errada e o medidor mentiria.
"""
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def limpar_pycache(raiz):
    for pasta in Path(raiz).rglob("__pycache__"):
        shutil.rmtree(pasta, ignore_errors=True)


def executar(raiz, arquivo, antes, depois):
    arquivo = Path(arquivo)
    original = arquivo.read_text(encoding="utf-8")
    ocorrencias = original.count(antes)
    if ocorrencias != 1:
        print(f"ABORTADO: o trecho aparece {ocorrencias} vezes em {arquivo}, esperado 1")
        return 2
    limpar_pycache(raiz)
    try:
        arquivo.write_text(original.replace(antes, depois, 1), encoding="utf-8")
        resultado = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-q"],
            capture_output=True,
            text=True,
            cwd=raiz,
        )
    finally:
        arquivo.write_text(original, encoding="utf-8")
    if resultado.returncode != 0:
        print("PEGOU: os testes falharam com a sabotagem")
        return 0
    print("ESCAPOU: os testes passaram mesmo com o código sabotado")
    return 1


def main(argv):
    if len(argv) != 4:
        print(__doc__)
        return 2
    return executar(RAIZ, argv[1], argv[2], argv[3])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
