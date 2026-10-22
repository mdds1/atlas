"""Laço do agente da Atlas: pensar, chamar ferramenta, conferir, até responder.

Substitui o OrchestratorAgent do OpenJarvis (ver o plano da parte 1): aqui a
autorização tem três saídas (rodar, recusar, parar), a primeira ação que falha
encerra o laço com relato, e o limite de passos devolve o que foi feito.
"""
import json
from dataclasses import dataclass, field

from openjarvis.core.types import Message, Role, ToolCall, ToolResult

LIMITE_SAIDA = 8000


@dataclass
class Passo:
    ferramenta: str
    argumentos: dict
    executou: bool
    sucesso: bool


@dataclass
class ResultadoLaco:
    texto: str
    passos: list = field(default_factory=list)
    parou: str = "fim"


def _feitas(passos):
    feitas = [p for p in passos if p.executou and p.sucesso]
    if not feitas:
        return "Nada tinha sido executado antes."
    return "Já feito: " + "; ".join(f"{p.ferramenta} {json.dumps(p.argumentos, ensure_ascii=False)}" for p in feitas) + "."


def rodar_laco(engine, modelo, mensagens, ferramentas, autorizar, eh_acao, *, max_passos=30, ao_resultado=None):
    por_nome = {f.spec.name: f for f in ferramentas}
    specs = [f.to_openai_function() for f in ferramentas]
    passos = []
    for _ in range(max_passos):
        extra = {"tools": specs} if specs else {}
        r = engine.generate(mensagens, model=modelo, temperature=0.2, max_tokens=1024, **extra)
        conteudo = r.get("content") or ""
        brutas = r.get("tool_calls") or []
        if not brutas:
            return ResultadoLaco(conteudo.strip(), passos, "fim")
        chamadas = [
            ToolCall(id=c.get("id") or f"c{i}", name=c.get("name") or "", arguments=c.get("arguments") or "{}")
            for i, c in enumerate(brutas)
        ]
        mensagens.append(Message(role=Role.ASSISTANT, content=conteudo, tool_calls=chamadas))
        for tc in chamadas:
            def responder(texto):
                mensagens.append(Message(role=Role.TOOL, content=texto, tool_call_id=tc.id, name=tc.name))

            try:
                argumentos = json.loads(tc.arguments) if isinstance(tc.arguments, str) else dict(tc.arguments)
                if not isinstance(argumentos, dict):
                    raise ValueError("não é objeto")
            except (ValueError, TypeError):
                passos.append(Passo(tc.name, {}, False, False))
                responder("Argumentos inválidos: mande um objeto JSON.")
                continue
            if tc.name not in por_nome:
                passos.append(Passo(tc.name, argumentos, False, False))
                responder(f"A ferramenta {tc.name!r} não existe.")
                continue
            acao, texto = autorizar(tc.name, argumentos)
            if acao == "parar":
                passos.append(Passo(tc.name, argumentos, False, False))
                return ResultadoLaco(texto, passos, "nao")
            if acao != "rodar":
                passos.append(Passo(tc.name, argumentos, False, False))
                responder(texto)
                continue
            try:
                resultado = por_nome[tc.name].execute(**argumentos)
            except Exception as e:
                resultado = ToolResult(tool_name=tc.name, content=f"Falha: {type(e).__name__}: {e}", success=False)
            passos.append(Passo(tc.name, argumentos, True, bool(resultado.success)))
            if ao_resultado:
                ao_resultado(tc.name, resultado)
            responder((resultado.content or "")[:LIMITE_SAIDA])
            if not resultado.success and eh_acao(tc.name):
                antes = passos[:-1]
                texto = (
                    f"Parei: a ação {tc.name} falhou.\n{(resultado.content or '').strip()[:1500]}\n\n"
                    f"{_feitas(antes)} Diga se quer que eu tente desfazer ou siga de outro jeito."
                )
                return ResultadoLaco(texto, passos, "erro_acao")
    return ResultadoLaco(
        f"Cheguei ao limite de {max_passos} passos sem terminar. {_feitas(passos)} Quer que eu continue?",
        passos,
        "limite",
    )
