"""Trava de comandos: decide, em código, o que a Jarvis nunca executa.

É um cinto de segurança, não uma caixa de areia. O que protege de verdade é o
Matheus ler o comando exato e dizer Sim. A trava existe para que o modelo, um
erro dele ou um texto malicioso lido da web nunca consiga nem pedir certas
coisas: o pedido perigoso não chega a aparecer na tela.
"""
import re
import unicodedata
from dataclasses import dataclass

LIMITE_TAMANHO = 2000


@dataclass(frozen=True)
class Veredito:
    permitido: bool
    regra: str = ""
    motivo: str = ""


_APAGAR = r"\b(?:remove-item|ri|rm|del|erase|rd|rmdir)\b"
_RECURSIVO = r"(?:^|\s)(?:-r|-rf|-fr|-rec[a-z]*)(?=\s|$)|(?:^|\s)/s(?=\s|$)"
_SISTEMA = (
    r"c:\\windows|system32|syswow64|program files|programdata|%windir%|"
    r"%systemroot%|\$env:windir|\$env:systemroot"
)
_HIVE = r"\bhk(?:lm|cu|cr|u|cc)\b|\bhkey_[a-z_]+\b"
_ESCRITA_REGISTRO = r"\b(?:set|new|remove|rename|copy|move|clear)-item(?:property)?\b"

# Cada regra: nome, motivo mostrado ao Matheus, e uma função texto -> bool.
_REGRAS = [
    (
        "formatar_disco",
        "formatar, particionar ou apagar disco",
        lambda t: re.search(
            r"\bformat-volume\b|\bformat\s+[a-z]:|\bdiskpart\b|\bclear-disk\b|"
            r"\bremove-partition\b|\binitialize-disk\b|\bset-disk\b|"
            r"\bnew-partition\b|\bresize-partition\b|\bset-partition\b",
            t,
        ),
    ),
    (
        "apagar_recursivo",
        "apagar pasta inteira, de forma recursiva",
        lambda t: re.search(_APAGAR, t) and re.search(_RECURSIVO, t),
    ),
    (
        "apagar_curinga",
        "apagar com curinga (* ou ?)",
        lambda t: re.search(_APAGAR, t) and re.search(r"[*?]", t),
    ),
    (
        "apagar_sistema",
        "apagar em pasta do sistema",
        lambda t: re.search(_APAGAR, t) and re.search(_SISTEMA, t),
    ),
    (
        "registro",
        "alterar o registro do Windows",
        lambda t: re.search(r"\bregedit\b", t)
        or re.search(r"\breg(?:\.exe)?\s+(?:add|delete|import|restore|load|unload|copy|save)\b", t)
        or (re.search(_HIVE, t) and re.search(_ESCRITA_REGISTRO, t)),
    ),
    (
        "rede",
        "desligar ou derrubar a rede",
        lambda t: re.search(
            r"\bdisable-netadapter\b|\bipconfig\s+/release\b|"
            r"\bnetsh\b[^|;\n]*\bdisable\b|"
            r"\bnetsh\s+advfirewall\s+set\b[^|;\n]*\boff\b|"
            r"\bset-netfirewallprofile\b[^|;\n]*-enabled\s+(?:false|0)\b|"
            r"\bremove-netipaddress\b|\bremove-netroute\b",
            t,
        ),
    ),
    (
        "execucao_dinamica",
        "baixar ou executar código montado na hora",
        lambda t: re.search(
            r"\b(?:invoke-expression|iex)\b|downloadstring|downloadfile|downloaddata|"
            r"frombase64string|(?:^|\s)-e(?:nc(?:odedcommand)?)?(?=\s)|\badd-type\b|"
            r"\[scriptblock\]|reflection\.assembly|\binvoke-webrequest\b|\biwr\b|"
            r"\binvoke-restmethod\b|\birm\b|\bstart-bitstransfer\b|\bcurl\b|\bwget\b|"
            r"\bbitsadmin\b|\bcertutil\b|\bmshta\b|\brundll32\b|\bregsvr32\b|"
            r"(?:^|[\s;|])&\s*[(\$\"']|(?:^|[\s;|])\.\s*[(\$\"']",
            t,
        ),
    ),
    (
        "sistema_critico",
        "mexer em inicialização, contas, tarefas agendadas, antivírus ou permissões",
        lambda t: re.search(
            r"\bbcdedit\b|\bbcdboot\b|\bvssadmin\b|\bwbadmin\b|\bcipher\s+/w\b|"
            r"\btakeown\b|\bicacls\b|\bnet\s+(?:user|localgroup|accounts)\b|"
            r"\bschtasks\s+/(?:create|change|delete)\b|\bregister-scheduledtask\b|"
            r"\bnew-scheduledtask\b|\bunregister-scheduledtask\b|"
            r"\bsc(?:\.exe)?\s+(?:delete|config|create)\b|\bremove-service\b|"
            r"\bnew-service\b|\b(?:set|add|remove)-mppreference\b|"
            r"\bdisable-windowsoptionalfeature\b|\bset-executionpolicy\b|"
            r"\bdism\b[^|;\n]*/(?:remove|disable)-",
            t,
        ),
    ),
    (
        "encerrar_em_massa",
        "encerrar processos com curinga",
        lambda t: re.search(r"\b(?:stop-process|taskkill)\b", t) and re.search(r"\*", t),
    ),
    (
        "elevacao",
        "pedir privilégio de administrador",
        lambda t: re.search(r"-verb\s+runas\b|\brunas\b", t),
    ),
]


def _normalizar(comando):
    texto = unicodedata.normalize("NFKC", comando)
    texto = texto.replace("`", "").replace("^", "")
    texto = re.sub(r"\s+", " ", texto)
    return texto.lower()


def avaliar(comando):
    """Devolve o Veredito para um comando de PowerShell ou cmd."""
    if not isinstance(comando, str) or not comando.strip():
        return Veredito(False, "vazio", "comando vazio")
    if len(comando) > LIMITE_TAMANHO:
        return Veredito(False, "tamanho", f"comando maior que {LIMITE_TAMANHO} caracteres")
    normal = _normalizar(comando)
    sem_aspas = normal.replace('"', "").replace("'", "")
    for nome, motivo, bate in _REGRAS:
        if bate(normal) or bate(sem_aspas):
            return Veredito(False, nome, motivo)
    return Veredito(True)
