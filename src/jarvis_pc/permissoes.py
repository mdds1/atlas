"""Permissões da Atlas: o código decide, antes de cada chamada, se lê, pede OK ou recusa.

Ler roda direto. Agir pede OK, salvo regra gravada pelo Matheus. Bloqueado
recusa sempre, mesmo com regra: ferramenta desconhecida ou comando que a trava
barra. O modelo nunca escolhe o nível.
"""
import json
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

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


ENCADEAMENTO = re.compile(r"[;|&`>\r\n]|\$\(")


def casa(padrao, alvo):
    """`*` é o único curinga. Alvo com encadeamento só casa padrão idêntico e sem curinga."""
    p, a = padrao.casefold(), alvo.casefold()
    if "*" not in p or ENCADEAMENTO.search(a):
        return p == a
    partes = [re.escape(x) for x in p.split("*")]
    return re.fullmatch(".*".join(partes), a, flags=re.DOTALL) is not None


def estreita(padrao):
    """Alvo exato (sem `*`) é sempre estreito; com `*`, o trecho antes dele precisa de 6+ caracteres não brancos."""
    if not isinstance(padrao, str) or not padrao.strip():
        return False
    if "*" not in padrao:
        return True
    return len("".join(padrao.split("*", 1)[0].split())) >= 6


@dataclass(frozen=True)
class Decisao:
    acao: str  # "rodar", "pedir" ou "recusar"
    nivel: str
    regra: str = ""
    motivo: str = ""


class Permissoes:
    def __init__(self, caminho=None):
        self.caminho = Path(caminho) if caminho else None
        self.regras = []
        self.invalidas = []
        self.erro = ""
        self._trava = threading.Lock()
        self._carregar()

    def _carregar(self):
        if not self.caminho or not self.caminho.exists():
            return
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
            lista = dados["regras"]
            if not isinstance(lista, list):
                raise ValueError("regras não é lista")
        except (ValueError, KeyError, TypeError, OSError) as e:
            self.erro = f"permissoes.json ilegível ({e}); nenhuma regra vale até ser consertado"
            return
        for r in lista:
            if (
                isinstance(r, dict)
                and nivel_de(r.get("ferramenta")) == AGIR
                and isinstance(r.get("padrao"), str)
                and estreita(r["padrao"])
            ):
                self.regras.append(r)
            else:
                self.invalidas.append(json.dumps(r, ensure_ascii=False))

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
        for r in self.regras:
            if r["ferramenta"] == nome and casa(r["padrao"], alvo):
                return f"{nome}: {r['padrao']}"
        return ""

    def gravar_regra(self, nome, argumentos, origem):
        """Sim sempre: grava o alvo exato. Só pela janela, só para agir, nunca com o arquivo ilegível."""
        if origem != "janela":
            raise ValueError("regra nova só se cria pela janela do PC")
        if self.erro:
            raise ValueError(self.erro)
        decisao = self.decidir(nome, argumentos)
        if decisao.nivel != AGIR or decisao.acao == "recusar":
            raise ValueError(f"não cabe regra para {nome!r}")
        padrao = alvo_de(nome, argumentos)
        if "*" in padrao or not estreita(padrao):
            raise ValueError("alvo com curinga ou largo demais não vira regra")
        with self._trava:
            if not any(r["ferramenta"] == nome and r["padrao"].casefold() == padrao.casefold() for r in self.regras):
                self.regras.append(
                    {"ferramenta": nome, "padrao": padrao, "criada": datetime.now().isoformat(timespec="seconds"), "origem": origem}
                )
                self._salvar()
        return f"{nome}: {padrao}"

    def _salvar(self):
        if not self.caminho:
            return
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.caminho.with_suffix(".tmp")
        tmp.write_text(json.dumps({"regras": self.regras}, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.caminho)
