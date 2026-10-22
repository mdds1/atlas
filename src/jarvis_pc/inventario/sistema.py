"""Coleta do sistema: apps instalados, serviços, tarefas agendadas e inicialização.

Um único script PowerShell (só leitura) devolve tudo em JSON. O PowerShell
devolve um objeto, e não uma lista, quando só há um item; `_lista` aceita os dois.
"""
import json
import time
from dataclasses import dataclass, field

from jarvis_pc.leitura import ler_script
from jarvis_pc.ps import executar_powershell

TABELAS_SISTEMA = ("apps", "servicos", "tarefas", "inicializacao")
PRAZO = 180


@dataclass(frozen=True)
class ResultadoColeta:
    ok: bool
    motivo: str = ""
    pythons: list = field(default_factory=list)
    npm: str = ""
    itens: int = 0


def _lista(valor):
    if valor is None:
        return []
    if isinstance(valor, list):
        return valor
    return [valor]


def _texto(valor):
    return "" if valor is None else str(valor)


def coletar_sistema(banco, executor=executar_powershell, agora=time.time):
    vid = banco.iniciar_varredura("sistema", agora())
    try:
        resultado = executor(ler_script("inventario_sistema"), timeout=PRAZO, json=True)
    except Exception as erro:
        banco.encerrar_varredura(vid, "falhou", 1, agora())
        return ResultadoColeta(False, f"falha ao executar o PowerShell: {type(erro).__name__}: {erro}")
    if resultado.codigo != 0 or not resultado.saida.strip():
        motivo = (resultado.erro or "sem saída").strip()
        banco.encerrar_varredura(vid, "falhou", 1, agora())
        return ResultadoColeta(False, f"o PowerShell falhou: {motivo}")
    try:
        dados = json.loads(resultado.saida)
        if not isinstance(dados, dict):
            raise ValueError("esperado um objeto")
        tabelas = {
            tabela: [
                {k: _texto(v) for k, v in item.items()} for item in _lista(dados.get(tabela)) if isinstance(item, dict)
            ]
            for tabela in TABELAS_SISTEMA
        }
        pythons = [_texto(p) for p in _lista(dados.get("pythons")) if p]
        npm = _texto(dados.get("npm"))
    except (ValueError, TypeError, AttributeError):
        banco.encerrar_varredura(vid, "falhou", 1, agora())
        return ResultadoColeta(False, "o PowerShell devolveu um formato inesperado")
    if not tabelas["apps"] and not tabelas["servicos"]:
        banco.encerrar_varredura(vid, "falhou", 1, agora())
        return ResultadoColeta(False, "o PowerShell devolveu a coleta vazia (sem apps nem servicos)")
    try:
        total = 0
        for tabela, linhas in tabelas.items():
            banco.gravar(tabela, vid, linhas)
            total += len(linhas)
    except Exception as erro:
        banco.encerrar_varredura(vid, "falhou", 1, agora())
        return ResultadoColeta(False, f"falha ao gravar o inventario do sistema: {type(erro).__name__}")
    banco.encerrar_varredura(vid, "ok", 0, agora())
    return ResultadoColeta(True, "", pythons, npm, total)
