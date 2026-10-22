"""Dependências instaladas: pacotes Python de cada ambiente e módulos globais do npm.

Nada é executado: lê as pastas `*.dist-info` (nome e versão estão no nome da
pasta) e os `package.json`. Os ambientes vêm de duas fontes: os `pyvenv.cfg`
já catalogados (cada um marca um venv) e os Python globais que o registro do
Windows informou. Pacotes em AppData só entram aqui, como inventário.
Pasta ilegível ou ausente é contada como erro e a coleta segue.
"""
import json
import ntpath
import time
from pathlib import Path


LIMITE_JSON = 1024 * 1024


def _pasta_real(p):
    try:
        return p.is_dir()
    except OSError:
        return False


def ler_dist_info(site_packages):
    """Devolve (pacotes, erros). Pasta ausente ou ilegivel conta como 1 erro."""
    site_packages = Path(site_packages)
    pacotes = []
    try:
        pastas = [p for p in site_packages.iterdir() if p.name.endswith(".dist-info") and _pasta_real(p)]
    except OSError:
        return pacotes, 1
    for p in pastas:
        nome, _, versao = p.name[: -len(".dist-info")].rpartition("-")
        if nome and versao:
            pacotes.append((nome, versao))
    return pacotes, 0


def ler_npm(modulos):
    """Devolve (modulos, erros). Pasta ausente, ilegivel ou package.json ilegivel ou grande demais contam como erro."""
    modulos = Path(modulos)
    achados = []
    erros = 0

    def um(pasta, nome):
        nonlocal erros
        versao = ""
        try:
            with open(pasta / "package.json", "rb") as f:
                bruto = f.read(LIMITE_JSON + 1)
            if len(bruto) > LIMITE_JSON:
                erros += 1
            else:
                valor = json.loads(bruto.decode("utf-8")).get("version")
                versao = "" if valor is None else str(valor)
        except FileNotFoundError:
            pass
        except OSError:
            erros += 1
        except (ValueError, AttributeError):
            pass
        achados.append((nome, versao))

    try:
        pastas = [p for p in modulos.iterdir() if _pasta_real(p)]
    except OSError:
        return achados, 1
    for p in pastas:
        if p.name.startswith("@"):
            try:
                internas = [q for q in p.iterdir() if _pasta_real(q)]
            except OSError:
                erros += 1
                continue
            for q in internas:
                um(q, f"{p.name}/{q.name}")
        else:
            um(p, p.name)
    return achados, erros


def _chave(caminho):
    return ntpath.normcase(ntpath.normpath(str(caminho)))


def coletar_pacotes(banco, pythons, npm, agora=time.time):
    vid = banco.iniciar_varredura("pacotes", agora())
    try:
        ambientes = {}
        for r in banco.consultar("SELECT pasta FROM arquivos WHERE nome = 'pyvenv.cfg'"):
            ambientes.setdefault(_chave(r["pasta"]), r["pasta"])
        for p in pythons:
            raiz = str(p).rstrip("\\/")
            ambientes.setdefault(_chave(raiz), raiz)
        linhas = []
        erros = 0
        for ambiente in ambientes.values():
            achados, falhas = ler_dist_info(Path(ambiente) / "Lib" / "site-packages")
            linhas += [(ambiente, nome, versao) for nome, versao in achados]
            erros += falhas
        if npm:
            achados, falhas = ler_npm(npm)
            linhas += [("npm-global", nome, versao) for nome, versao in achados]
            erros += falhas
        banco.gravar("pacotes", vid, linhas)
    except Exception:
        try:
            banco.encerrar_varredura(vid, "falhou", 1, agora())
        except Exception:
            pass
        raise
    banco.encerrar_varredura(vid, "ok", erros, agora())
    return len(linhas)
