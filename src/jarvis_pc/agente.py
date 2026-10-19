"""Monta o agente: ferramentas de leitura, comando travado e confirmação."""
from openjarvis.agents.orchestrator import OrchestratorAgent

from jarvis_pc.comando import ComandoPcTool
from jarvis_pc.leitura import criar_ferramentas_leitura
from jarvis_pc.prompt import SYSTEM_PROMPT
from jarvis_pc.ps import executar_powershell
from jarvis_pc.trava import avaliar


def criar_agente(
    *, modelo, confirmar, registro, executor=executar_powershell, engine=None, host=None, max_turns=8
):
    """Cria o agente. `confirmar(texto) -> bool` é obrigatório: sem ele, nada executa."""
    if not callable(confirmar):
        raise ValueError("confirmar é obrigatório: sem ele a Jarvis não executa nada")
    ferramentas = criar_ferramentas_leitura(executor) + [ComandoPcTool(executor)]
    conhecidas = {f.spec.name for f in ferramentas}

    def antes(nome, argumentos):
        permitido = nome in conhecidas
        if permitido and nome == "pc_comando":
            permitido = avaliar(argumentos.get("comando")).permitido
        registro.evento("chamada", ferramenta=nome, argumentos=argumentos, permitido=permitido)
        return permitido

    def pedir(texto):
        try:
            resposta = bool(confirmar(texto))
        except Exception:
            resposta = False
        registro.evento("confirmacao", pedido=texto, resposta=resposta)
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
