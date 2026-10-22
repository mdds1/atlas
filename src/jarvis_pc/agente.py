"""Monta o agente: ferramentas de leitura, comando travado e confirmação."""
import unicodedata

from openjarvis.agents.orchestrator import OrchestratorAgent

from jarvis_pc.comando import ComandoPcTool
from jarvis_pc.leitura import criar_ferramentas_leitura
from jarvis_pc.prompt import SYSTEM_PROMPT
from jarvis_pc.ps import executar_powershell
from jarvis_pc.trava import avaliar


def montar_texto_confirmacao(pendente, texto_padrao):
    """Texto de OK em português, com o comando literal (sem barras dobradas)."""
    comando = pendente.get("comando")
    if not isinstance(comando, str) or not comando.strip():
        return texto_padrao
    motivo = str(pendente.get("motivo") or "")
    motivo = "".join(" " if unicodedata.category(c) in ("Cc", "Cf") else c for c in motivo)
    motivo = " ".join(motivo.split())
    if len(motivo) > 300:
        motivo = motivo[:300] + "..."
    motivo = motivo or "nao informado"
    return (
        "A Jarvis quer executar este comando no seu PC:\n\n"
        + comando
        + "\n\nMotivo: "
        + motivo
        + "\n\nPermitir?"
    )


def criar_agente(
    *, modelo, confirmar, registro, executor=executar_powershell, engine=None, host=None, max_turns=8, extras=()
):
    """Cria o agente. `confirmar(texto) -> bool` é obrigatório: sem ele, nada executa."""
    if not callable(confirmar):
        raise ValueError("confirmar é obrigatório: sem ele a Jarvis não executa nada")
    ferramentas = criar_ferramentas_leitura(executor) + [ComandoPcTool(executor)] + list(extras)
    conhecidas = {f.spec.name for f in ferramentas}
    pendente = {}

    def antes(nome, argumentos):
        permitido = nome in conhecidas
        if permitido and nome == "pc_comando":
            permitido = avaliar(argumentos.get("comando")).permitido
        if permitido and nome == "pc_comando":
            pendente.clear()
            pendente.update(comando=argumentos.get("comando"), motivo=argumentos.get("motivo"))
        if not permitido:
            pendente.clear()
        registro.evento("chamada", ferramenta=nome, argumentos=argumentos, permitido=permitido)
        return permitido

    def pedir(texto):
        texto_mostrado = montar_texto_confirmacao(pendente, texto)
        try:
            resposta = bool(confirmar(texto_mostrado))
        except Exception:
            resposta = False
        finally:
            pendente.clear()
        registro.evento("confirmacao", pedido=texto_mostrado, resposta=resposta)
        return resposta

    if engine is None:
        from openjarvis.engine.ollama import OllamaEngine

        engine = OllamaEngine(host=host)
    return OrchestratorAgent(
        engine,
        modelo,
        tools=ferramentas,
        system_prompt=SYSTEM_PROMPT,
        interactive=True,
        confirm_callback=pedir,
        before_tool_call=antes,
        parallel_tools=False,
        max_turns=max_turns,
        temperature=0.2,
    )


def perguntar(agente, registro, texto):
    """Roda uma pergunta, registra tudo e devolve o texto da resposta."""
    registro.evento("pergunta", texto=texto)
    try:
        resultado = agente.run(texto)
    except Exception as erro:
        registro.evento("erro", classe=type(erro).__name__, mensagem=str(erro))
        raise
    registro.evento("resposta", texto=resultado.content)
    return resultado.content
