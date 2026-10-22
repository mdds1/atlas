"""Executa PowerShell no Windows e devolve o resultado sem nunca levantar erro.

Dois formatos de envoltório:
- json=True: o script devolve um objeto; a saída é JSON só com ASCII (o que não
  é ASCII vira \\uXXXX), então a página de código do Windows não estraga acento.
- json=False: texto livre, com saída em UTF-8.
O stderr do PowerShell sai na página de código do Windows, não em UTF-8, por
isso tudo é lido como bytes e decodificado tolerando erro.
"""
import base64
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass

ENVOLTORIO_JSON = r"""$ErrorActionPreference = 'SilentlyContinue'
$ProgressPreference = 'SilentlyContinue'
$r = & { __SCRIPT__ }
$j = $r | ConvertTo-Json -Compress -Depth 5
[regex]::Replace($j, '[^\x00-\x7F]', { param($m) ('\u{0:x4}' -f [int][char]$m.Value) })"""

ENVOLTORIO_TEXTO = r"""$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
__SCRIPT__"""


def clixml_para_texto(texto):
    """Converte o stderr em CLIXML do PowerShell em texto legível; o resto passa intacto."""
    if not texto.lstrip().startswith("#< CLIXML"):
        return texto
    corpo = texto.split("\n", 1)[1] if "\n" in texto else ""
    try:
        raiz = ET.fromstring(corpo.strip())
    except ET.ParseError:
        return texto
    linhas = []
    for no in raiz.iter():
        if no.tag.rpartition("}")[2] == "S" and no.get("S") == "Error":
            bruto = re.sub(r"_x([0-9A-Fa-f]{4})_", lambda m: chr(int(m.group(1), 16)), no.text or "")
            linhas.extend(l.strip() for l in bruto.splitlines() if l.strip())
    return "\n".join(linhas)


@dataclass(frozen=True)
class ResultadoPS:
    codigo: int
    saida: str
    erro: str


def montar_argv(script, *, json=True, exe="powershell"):
    envoltorio = ENVOLTORIO_JSON if json else ENVOLTORIO_TEXTO
    texto = envoltorio.replace("__SCRIPT__", script)
    codificado = base64.b64encode(texto.encode("utf-16-le")).decode("ascii")
    return [exe, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", codificado]


def executar_powershell(script, *, timeout=30, json=True, exe="powershell"):
    argv = montar_argv(script, json=json, exe=exe)
    extra = {}
    if sys.platform == "win32":
        extra["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        p = subprocess.run(argv, capture_output=True, timeout=timeout, **extra)
    except subprocess.TimeoutExpired:
        return ResultadoPS(-1, "", f"tempo esgotado ({timeout}s)")
    except FileNotFoundError:
        return ResultadoPS(-1, "", f"{exe} não encontrado")
    except OSError as erro:
        return ResultadoPS(-1, "", f"não foi possível executar {exe}: {erro}")
    return ResultadoPS(
        p.returncode,
        p.stdout.decode("utf-8", "replace"),
        clixml_para_texto(p.stderr.decode("utf-8", "replace")),
    )
