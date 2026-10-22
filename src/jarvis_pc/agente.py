"""Monta a Atlas: ferramentas, permissões, pedido de OK, memória, sessão e registro sobre o laço próprio."""
import unicodedata

from openjarvis.core.types import Message, Role

from jarvis_pc.comando import ComandoPcTool
from jarvis_pc.laco import rodar_laco
from jarvis_pc.leitura import criar_ferramentas_leitura
from jarvis_pc.memoria import Memoria, criar_ferramentas_memoria
from jarvis_pc.permissoes import AGIR, NIVEIS, Permissoes, alvo_de, nivel_de
from jarvis_pc.ponte import NAO, SIM, SIM_SEMPRE
from jarvis_pc.prompt import SYSTEM_PROMPT
from jarvis_pc.ps import executar_powershell
from jarvis_pc.sessao import Sessao


def _limpo(texto, limite=300):
    t = "".join(" " if unicodedata.category(c) in ("Cc", "Cf") else c for c in str(texto or ""))
    t = " ".join(t.split())
    return t[:limite] + "..." if len(t) > limite else t


def montar_texto_confirmacao(pendente, texto_padrao):
    """Texto de OK em português, com o comando literal (sem barras dobradas)."""
    comando = pendente.get("comando")
    if not isinstance(comando, str) or not comando.strip():
        return texto_padrao
    motivo = _limpo(pendente.get("motivo")) or "nao informado"
    return "A Atlas quer executar este comando no seu PC:\n\n" + comando + "\n\nMotivo: " + motivo + "\n\nPermitir?"


def texto_ok(nome, argumentos):
    padrao = f"A Atlas quer usar {nome} com:\n\n{alvo_de(nome, argumentos)}\n\nPermitir?"
    if nome == "pc_comando":
        return montar_texto_confirmacao(argumentos, padrao)
    return padrao


class Agente:
    def __init__(self, *, engine, modelo, ferramentas, confirmar, registro, permissoes, memoria, sessao, max_passos):
        self.engine, self.modelo, self.ferramentas = engine, modelo, ferramentas
        self.confirmar, self.registro = confirmar, registro
        self.permissoes, self.memoria, self.sessao = permissoes, memoria, sessao
        self.max_passos = max_passos

    def _mensagens(self, texto):
        sistema = SYSTEM_PROMPT
        fatos = self.memoria.para_prompt()
        if fatos:
            sistema += "\n" + fatos + "\n"
        msgs = [Message(role=Role.SYSTEM, content=sistema)]
        for papel, t in self.sessao.historico():
            msgs.append(Message(role=Role.USER if papel == "usuario" else Role.ASSISTANT, content=t))
        msgs.append(Message(role=Role.USER, content=texto))
        return msgs

    def _autorizador(self, origem):
        def autorizar(nome, argumentos):
            d = self.permissoes.decidir(nome, argumentos)

            def registrar(permitido, regra):
                self.registro.evento(
                    "chamada", ferramenta=nome, argumentos=argumentos, nivel=d.nivel,
                    permitido=permitido, regra=regra, origem=origem, motivo=d.motivo,
                )

            if d.acao == "recusar":
                registrar(False, "")
                return "recusar", f"BLOQUEADO: {d.motivo}. Não tente outro caminho; explique ao Matheus."
            if d.acao == "rodar":
                registrar(True, d.regra or "leitura")
                return "rodar", ""
            pedido = texto_ok(nome, argumentos)
            try:
                resposta = self.confirmar(pedido, origem == "janela")
            except Exception:
                resposta = NAO
            if resposta not in (SIM, SIM_SEMPRE) or (resposta == SIM_SEMPRE and origem != "janela"):
                resposta = NAO
            self.registro.evento("confirmacao", pedido=pedido, resposta=resposta, origem=origem)
            regra = "ok desta vez"
            if resposta == SIM_SEMPRE:
                try:
                    regra = self.permissoes.gravar_regra(nome, argumentos, origem)
                    self.registro.evento("regra_nova", regra=regra, origem=origem)
                except ValueError as e:
                    self.registro.evento("erro", classe="ValueError", mensagem=f"regra não gravada: {e}")
            registrar(resposta != NAO, regra if resposta != NAO else "")
            if resposta == NAO:
                return "parar", (
                    f"Não fiz: você disse Não (ou não respondeu) para {nome}: {alvo_de(nome, argumentos)}. "
                    "Não vou tentar outro caminho. O que prefere fazer?"
                )
            return "rodar", ""
        return autorizar

    def perguntar(self, texto, origem="janela"):
        origem = origem if origem == "janela" else "telegram"
        self.registro.evento("pergunta", texto=texto, origem=origem)
        try:
            r = rodar_laco(
                self.engine, self.modelo, self._mensagens(texto), self.ferramentas,
                self._autorizador(origem), lambda n: nivel_de(n) == AGIR,
                max_passos=self.max_passos,
                ao_resultado=lambda n, res: self.registro.evento(
                    "resultado", ferramenta=n, sucesso=bool(res.success), tamanho=len(res.content or "")
                ),
            )
        except Exception as erro:
            self.registro.evento("erro", classe=type(erro).__name__, mensagem=str(erro))
            raise
        self.sessao.acrescentar("usuario", texto, origem)
        self.sessao.acrescentar("atlas", r.texto, origem)
        self.registro.evento("resposta", texto=r.texto, parou=r.parou, passos=len(r.passos))
        return r.texto


def criar_agente(
    *, modelo, confirmar, registro, executor=executar_powershell, engine=None, host=None,
    max_passos=30, extras=(), permissoes=None, memoria=None, sessao=None,
):
    """Cria a Atlas. `confirmar(texto, pode_sempre) -> "sim" | "sim_sempre" | "nao"` é obrigatório."""
    if not callable(confirmar):
        raise ValueError("confirmar é obrigatório: sem ele a Atlas não executa nada")
    memoria = memoria if memoria is not None else Memoria()
    ferramentas = (
        criar_ferramentas_leitura(executor) + [ComandoPcTool(executor)] + criar_ferramentas_memoria(memoria) + list(extras)
    )
    sem_nivel = [f.spec.name for f in ferramentas if f.spec.name not in NIVEIS]
    if sem_nivel:
        raise ValueError(f"ferramenta sem nível de permissão: {', '.join(sem_nivel)}")
    if engine is None:
        from openjarvis.engine.ollama import OllamaEngine

        engine = OllamaEngine(host=host)
    return Agente(
        engine=engine, modelo=modelo, ferramentas=ferramentas, confirmar=confirmar, registro=registro,
        permissoes=permissoes if permissoes is not None else Permissoes(),
        memoria=memoria, sessao=sessao if sessao is not None else Sessao(), max_passos=max_passos,
    )


def perguntar(agente, registro, texto, origem="janela"):
    """Compatibilidade com janela e cenários. O registro usado é o do agente."""
    return agente.perguntar(texto, origem)
