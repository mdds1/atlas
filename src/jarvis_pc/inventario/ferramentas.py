"""As seis ferramentas do inventário que o agente enxerga. Só leitura.

O modelo nunca escreve SQL: cada ferramenta chama uma consulta fixa de
`consultas.py`. O texto devolvido começa com o aviso de que são dados.
"""
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

from jarvis_pc.inventario import consultas
from jarvis_pc.inventario.atualizador import Atualizador
from jarvis_pc.inventario.banco import Banco
from jarvis_pc.inventario.exclusoes import Exclusoes
from jarvis_pc.leitura import AVISO, LIMITE_SAIDA

NOMES_INVENTARIO = ("inv_status", "inv_atualizar", "inv_arquivos", "inv_apps", "inv_dependencias", "inv_sistema")
OPERACOES = ("buscar", "maiores", "pastas", "duplicados")
TIPOS_SISTEMA = ("servicos", "tarefas", "inicializacao")


@dataclass
class Contexto:
    banco: object
    atualizador: object


class Erro(Exception):
    """Pedido mal feito pelo modelo: a mensagem volta para ele como falha."""


def _status(ctx, **_):
    return consultas.status(ctx.banco)


def _atualizar(ctx, **_):
    if ctx.atualizador.iniciar():
        return (
            "Atualização do inventário iniciada em segundo plano. Pode levar vários minutos. "
            "Use inv_status para acompanhar."
        )
    return "A atualização do inventário já está em andamento. Use inv_status para acompanhar."


def _arquivos(ctx, operacao="", nome="", extensao="", pasta="", minimo_mb=0, limite=None, **_):
    if operacao not in OPERACOES:
        raise Erro("A operação deve ser: " + ", ".join(OPERACOES) + ".")
    extras = {} if limite is None else {"limite": limite}
    if operacao == "buscar":
        return consultas.arquivos_buscar(ctx.banco, nome=nome, extensao=extensao, pasta=pasta, minimo_mb=minimo_mb, **extras)
    if operacao == "maiores":
        return consultas.arquivos_maiores(ctx.banco, pasta=pasta, **extras)
    if operacao == "pastas":
        if not pasta:
            raise Erro("A operação pastas precisa do parâmetro pasta, por exemplo C:\\.")
        return consultas.arquivos_pastas(ctx.banco, pasta, **extras)
    return consultas.arquivos_duplicados(ctx.banco, pasta=pasta, minimo_mb=minimo_mb or 1.0, **extras)


def _apps(ctx, nome="", **_):
    return consultas.apps(ctx.banco, nome=nome)


def _dependencias(ctx, ambiente="", nome="", **_):
    return consultas.dependencias(ctx.banco, ambiente=ambiente, nome=nome)


def _sistema(ctx, tipo="", filtro="", **_):
    if tipo not in TIPOS_SISTEMA:
        raise Erro("O tipo deve ser: " + ", ".join(TIPOS_SISTEMA) + ".")
    return consultas.sistema(ctx.banco, tipo, filtro)


def _prop(tipo, descricao, **extra):
    return {"type": tipo, "description": descricao, **extra}


DEFINICOES = [
    (
        "inv_status",
        "Mostra quando o inventário do PC foi feito pela última vez e quantos arquivos, apps, pacotes, serviços e tarefas existem. Use para saber se os dados estão atuais.",
        {},
        _status,
    ),
    (
        "inv_atualizar",
        "Refaz o inventário do PC (arquivos, apps, dependências, serviços) em segundo plano. Só use quando o Matheus pedir ou quando os dados estiverem desatualizados.",
        {},
        _atualizar,
    ),
    (
        "inv_arquivos",
        "Consulta exata ao catálogo de TODOS os arquivos do PC: buscar por nome, extensão, pasta ou tamanho; listar os maiores; somar o espaço por subpasta; achar duplicados. Use para qualquer pergunta sobre quais arquivos existem, onde estão e quanto ocupam.",
        {
            "operacao": _prop("string", "buscar, maiores, pastas ou duplicados", enum=list(OPERACOES)),
            "nome": _prop("string", "parte do nome do arquivo (operação buscar)"),
            "extensao": _prop("string", "extensão, por exemplo .py (operação buscar)"),
            "pasta": _prop("string", "pasta onde procurar, por exemplo C:\\Jarvis (obrigatória em pastas)"),
            "minimo_mb": _prop("number", "tamanho mínimo em megabytes"),
            "limite": _prop("integer", "quantos resultados mostrar"),
        },
        _arquivos,
    ),
    (
        "inv_apps",
        "Lista os programas instalados no PC (do Windows e da Loja) com a versão. Use para saber se um programa está instalado e qual a versão.",
        {"nome": _prop("string", "parte do nome do programa; vazio lista todos")},
        _apps,
    ),
    (
        "inv_dependencias",
        "Lista os pacotes instalados: bibliotecas Python de cada ambiente (venv ou Python global) e módulos globais do npm, com a versão. Sem filtros, lista os ambientes.",
        {
            "ambiente": _prop("string", "parte do caminho do ambiente, por exemplo Jarvis"),
            "nome": _prop("string", "parte do nome do pacote"),
        },
        _dependencias,
    ),
    (
        "inv_sistema",
        "Lista todos os serviços do Windows (com estado), as tarefas agendadas ou os programas de inicialização, com filtro opcional.",
        {
            "tipo": _prop("string", "servicos, tarefas ou inicializacao", enum=list(TIPOS_SISTEMA)),
            "filtro": _prop("string", "parte do nome ou do estado, por exemplo Stopped"),
        },
        _sistema,
    ),
]


class FerramentaInventario(BaseTool):
    def __init__(self, nome, descricao, propriedades, funcao, contexto):
        self._nome, self._descricao, self._props, self._funcao, self._ctx = nome, descricao, propriedades, funcao, contexto
        self.tool_id = nome

    @property
    def spec(self):
        return ToolSpec(
            name=self._nome,
            description=self._descricao,
            parameters={"type": "object", "properties": self._props},
            category="pc-inventario",
            requires_confirmation=False,
            timeout_seconds=60.0,
        )

    def execute(self, **params):
        try:
            texto = self._funcao(self._ctx, **params)
        except Erro as erro:
            return ToolResult(tool_name=self._nome, content=str(erro), success=False)
        except (sqlite3.Error, ValueError, TypeError) as erro:
            return ToolResult(tool_name=self._nome, content=f"Falha ao consultar o inventário: {type(erro).__name__}.", success=False)
        return ToolResult(tool_name=self._nome, content=f"{AVISO}\n{texto}"[:LIMITE_SAIDA])


def criar_ferramentas_inventario(banco, atualizador):
    ctx = Contexto(banco, atualizador)
    return [FerramentaInventario(n, d, p, f, ctx) for n, d, p, f in DEFINICOES]


def montar_inventario(pasta, config):
    banco = Banco(Path(pasta) / config.inventario)
    atualizador = Atualizador(banco, config.raizes, Exclusoes())
    return criar_ferramentas_inventario(banco, atualizador), atualizador, banco
