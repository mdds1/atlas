"""Peças falsas para testar sem Ollama e sem PowerShell."""
import json
from pathlib import Path

from openjarvis.engine._stubs import InferenceEngine

from jarvis_pc.ps import ResultadoPS

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture(nome):
    return json.loads((FIXTURES / f"{nome}.json").read_text(encoding="utf-8"))


def chamada(nome, **argumentos):
    return {
        "content": "",
        "tool_calls": [{"id": "c1", "name": nome, "arguments": json.dumps(argumentos)}],
        "usage": {},
    }


def final(texto):
    return {"content": texto, "tool_calls": [], "usage": {}}


class MotorFalso(InferenceEngine):
    """Devolve respostas roteirizadas, na ordem."""

    engine_id = "falso"

    def __init__(self, roteiro):
        self.roteiro = list(roteiro)
        self.chamadas = 0

    def generate(self, messages, *, model, temperature=0.7, max_tokens=1024, **kwargs):
        self.chamadas += 1
        return self.roteiro.pop(0)

    async def stream(self, messages, *, model, temperature=0.7, max_tokens=1024, **kwargs):
        yield ""

    def list_models(self):
        return ["falso"]

    def health(self):
        return True


class ExecutorFalso:
    """Registra o que o PowerShell receberia e devolve um resultado fixo."""

    def __init__(self, saida="{}", codigo=0, erro=""):
        self.chamadas = []
        self._resultado = ResultadoPS(codigo, saida, erro)

    def __call__(self, script, *, timeout=30, json=True):
        self.chamadas.append({"script": script, "timeout": timeout, "json": json})
        return self._resultado
