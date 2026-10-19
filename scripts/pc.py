#!/usr/bin/env python3
"""Roda coisas no PC Windows do Matheus por `ssh win`, a partir da bancada.

  python scripts/pc.py validar arquivo.ps1   confere a sintaxe, sem executar
  python scripts/pc.py rodar arquivo.ps1     executa o script e mostra a saída
  python scripts/pc.py cmd "Get-Date"        executa um comando solto

Tudo vai por -EncodedCommand, sem passar por aspas do ssh nem por arquivo no PC.
O script é lido como UTF-8 aqui; use só ASCII nos .ps1 que forem instalados.
"""
import base64
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from jarvis_pc.ps import montar_argv  # noqa: E402

VALIDADOR = """$t = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__B64__'))
$erros = $null; $tokens = $null
[void][System.Management.Automation.Language.Parser]::ParseInput($t, [ref]$tokens, [ref]$erros)
if ($erros.Count -eq 0) { 'sintaxe ok' } else {
  $erros | ForEach-Object { 'ERRO: ' + $_.Message + ' (linha ' + $_.Extent.StartLineNumber + ')' }
  exit 1
}"""


def ssh_powershell(script, timeout):
    argv = ["ssh", "-o", "ServerAliveInterval=30", "win"] + montar_argv(script, json=False)
    p = subprocess.run(argv, capture_output=True, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def main(argv):
    if len(argv) != 3 or argv[1] not in ("validar", "rodar", "cmd"):
        print(__doc__)
        return 2
    modo, alvo = argv[1], argv[2]
    if modo == "cmd":
        script, timeout = alvo, 120
    else:
        conteudo = Path(alvo).read_text(encoding="utf-8")
        if modo == "validar":
            b64 = base64.b64encode(conteudo.encode("utf-8")).decode("ascii")
            script, timeout = VALIDADOR.replace("__B64__", b64), 60
        else:
            script, timeout = conteudo, 1200
    codigo, saida, erro = ssh_powershell(script, timeout)
    print(saida, end="")
    if erro.strip():
        print(erro, end="", file=sys.stderr)
    return codigo


if __name__ == "__main__":
    sys.exit(main(sys.argv))
