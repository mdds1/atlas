"""Dependências instaladas: pacotes Python de cada ambiente e módulos globais do npm.

Nada é executado: lê as pastas `*.dist-info` (nome e versão estão no nome da
pasta) e os `package.json`. Os ambientes vêm de duas fontes: os `pyvenv.cfg`
já catalogados (cada um marca um venv) e os Python globais que o registro do
Windows informou. Pacotes em AppData só entram aqui, como inventário.
Links simbólicos não são seguidos; pasta ilegível é ignorada e a coleta segue.
"""
import json
import time
from pathlib import Path


def _pasta_real(p):
    try:
        return p.is_dir() and not p.is_symlink()
    except OSError:
        return False


def ler_dist_info(site_packages):
    site_packages = Path(site_packages)
    pacotes = []
    try:
        pastas = [p for p in site_packages.iterdir() if p.name.endswith(".dist-info") and _pasta_real(p)]
    except OSError:
        return pacotes
    for p in pastas:
        nome, _, versao = p.name[: -len(".dist-info")].rpartition("-")
        if nome and versao:
            pacotes.append((nome, versao))
    return pacotes


def ler_npm(modulos):
    modulos = Path(modulos)
    achados = []

    def um(pasta, nome):
        try:
            versao = str(json.loads((pasta / "package.json").read_text(encoding="utf-8")).get("version", ""))
        except (OSError, ValueError, AttributeError):
            versao = ""
        achados.append((nome, versao))

    try:
        pastas = [p for p in modulos.iterdir() if _pasta_real(p)]
    except OSError:
        return achados
    for p in pastas:
        if p.name.startswith("@"):
            try:
                internas = [q for q in p.iterdir() if _pasta_real(q)]
            except OSError:
                continue
            for q in internas:
                um(q, f"{p.name}/{q.name}")
        else:
            um(p, p.name)
    return achados


def coletar_pacotes(banco, pythons, npm, agora=time.time):
    vid = banco.iniciar_varredura("pacotes", agora())
    try:
        ambientes = {}
        for r in banco.consultar("SELECT pasta FROM arquivos WHERE nome = 'pyvenv.cfg'"):
            ambientes[r["pasta"]] = Path(r["pasta"]) / "Lib" / "site-packages"
        for p in pythons:
            raiz = str(p).rstrip("\\/")
            ambientes.setdefault(raiz, Path(raiz) / "Lib" / "site-packages")
        linhas = []
        for ambiente, site in ambientes.items():
            linhas += [(ambiente, nome, versao) for nome, versao in ler_dist_info(site)]
        if npm:
            linhas += [("npm-global", nome, versao) for nome, versao in ler_npm(npm)]
        banco.gravar("pacotes", vid, linhas)
    except Exception:
        banco.encerrar_varredura(vid, "falhou", 1, agora())
        return 0
    banco.encerrar_varredura(vid, "ok", 0, agora())
    return len(linhas)
