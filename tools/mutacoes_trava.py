#!/usr/bin/env python3
"""Sabota cada palavra bloqueada da trava e confere que algum teste falha.

Para cada \\b<palavra> e cada alternativa (a|b|c) dentro de src/jarvis_pc/trava.py, troca a palavra por
<palavra>x (que já não casa com o comando perigoso), roda os testes e restaura
o arquivo. Lista as que ESCAPARAM: palavra bloqueada que nenhum teste exige.
Roda só tests/test_trava.py: a trava precisa ser exigida pelos testes dela mesma,
não por acaso por um teste de outro módulo.

Uso: python tools/mutacoes_trava.py
Sai com 0 se nada escapou, com 1 se algo escapou.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "src" / "jarvis_pc" / "trava.py"
PADRAO = re.compile(r"\\b([a-z][a-z0-9.-]*)\\b|[(|:]([a-z][a-z0-9.-]*)(?=[|)])")


def limpar_pycache():
    for pasta in RAIZ.rglob("__pycache__"):
        shutil.rmtree(pasta, ignore_errors=True)


def testes_passam():
    limpar_pycache()
    resultado = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_trava.py", "-q"],
        capture_output=True,
        text=True,
        cwd=RAIZ,
    )
    return resultado.returncode == 0


def main():
    original = ARQUIVO.read_text(encoding="utf-8")
    if not testes_passam():
        print("ABORTADO: os testes já falham sem sabotagem")
        return 2
    escaparam = []
    total = 0
    try:
        for achado in PADRAO.finditer(original):
            total += 1
            grupo = 1 if achado.group(1) else 2
            palavra = achado.group(grupo)
            inicio, fim = achado.span(grupo)
            sabotado = original[:fim] + "x" + original[fim:]
            ARQUIVO.write_text(sabotado, encoding="utf-8")
            if testes_passam():
                escaparam.append(f"{palavra} (posição {inicio})")
    finally:
        ARQUIVO.write_text(original, encoding="utf-8")
        limpar_pycache()
    print(f"{total} palavras sabotadas, {len(escaparam)} escaparam")
    for item in escaparam:
        print("  ESCAPOU:", item)
    return 1 if escaparam else 0


if __name__ == "__main__":
    sys.exit(main())
