"""Permissões da Atlas: o código decide, antes de cada chamada, se lê, pede OK ou recusa.

Ler roda direto. Agir pede OK, salvo regra gravada pelo Matheus. Bloqueado
recusa sempre, mesmo com regra: ferramenta desconhecida ou comando que a trava
barra. O modelo nunca escolhe o nível.
"""
from dataclasses import dataclass

from jarvis_pc.trava import avaliar

LER, AGIR, BLOQUEADO = "ler", "agir", "bloqueado"

NIVEIS = {
    "pc_resumo": LER,
    "pc_processos": LER,
    "pc_inicializacao": LER,
    "pc_eventos": LER,
    "pc_servicos": LER,
    "pc_drivers": LER,
    "pc_gpu": LER,
    "pc_atualizacoes": LER,
    "inv_status": LER,
    "inv_atualizar": LER,
    "inv_arquivos": LER,
    "inv_apps": LER,
    "inv_dependencias": LER,
    "inv_sistema": LER,
    "pc_comando": AGIR,
    "mem_lembrar": AGIR,
    "mem_esquecer": AGIR,
}

# Para cada ferramenta de agir, o argumento que a regra compara.
ALVOS = {"pc_comando": "comando", "mem_lembrar": "fato", "mem_esquecer": "fato"}


def nivel_de(nome):
    return NIVEIS.get(nome, BLOQUEADO) if isinstance(nome, str) else BLOQUEADO


def alvo_de(nome, argumentos):
    if not isinstance(argumentos, dict):
        return ""
    valor = argumentos.get(ALVOS.get(nome, ""), "")
    return valor.strip() if isinstance(valor, str) else ""


@dataclass(frozen=True)
class Decisao:
    acao: str  # "rodar", "pedir" ou "recusar"
    nivel: str
    regra: str = ""
    motivo: str = ""


class Permissoes:
    def __init__(self, caminho=None):
        self.caminho = caminho
        self.regras = []

    def decidir(self, nome, argumentos):
        nivel = nivel_de(nome)
        if nivel == BLOQUEADO:
            return Decisao("recusar", BLOQUEADO, motivo=f"a ferramenta {nome!r} não existe para a Atlas")
        if nivel == LER:
            return Decisao("rodar", LER)
        alvo = alvo_de(nome, argumentos)
        if not alvo:
            return Decisao("recusar", AGIR, motivo=f"faltou o argumento {ALVOS[nome]!r}")
        if nome == "pc_comando":
            veredito = avaliar(alvo)
            if not veredito.permitido:
                return Decisao("recusar", BLOQUEADO, motivo=veredito.motivo or "barrado pela trava")
        regra = self._regra_que_libera(nome, alvo)
        if regra:
            return Decisao("rodar", AGIR, regra=regra)
        return Decisao("pedir", AGIR)

    def _regra_que_libera(self, nome, alvo):
        return ""
