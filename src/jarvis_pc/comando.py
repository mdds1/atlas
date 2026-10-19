"""Ferramenta que altera o PC. Sempre com a trava e sempre com o OK do Matheus."""
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

from jarvis_pc.ps import executar_powershell
from jarvis_pc.trava import avaliar

LIMITE_SAIDA = 4000


class ComandoPcTool(BaseTool):
    """Roda um comando de PowerShell, depois da trava e da confirmação.

    A confirmação é feita pelo executor do OpenJarvis (requires_confirmation).
    A trava roda de novo aqui dentro: se alguém montar o agente sem o gancho,
    um comando proibido ainda não executa.
    """

    tool_id = "pc_comando"

    def __init__(self, executor=executar_powershell):
        self._executor = executor

    @property
    def spec(self):
        return ToolSpec(
            name="pc_comando",
            description=(
                "Executa um comando de PowerShell no PC do Matheus. Só use depois de ler os "
                "dados com as ferramentas de leitura. O Matheus vê o comando e decide Sim ou Não."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "comando": {"type": "string", "description": "Um comando de PowerShell."},
                    "motivo": {"type": "string", "description": "Por que este comando resolve o problema."},
                },
                "required": ["comando", "motivo"],
            },
            category="pc-comando",
            requires_confirmation=True,
            timeout_seconds=75.0,
        )

    def execute(self, **params):
        comando = params.get("comando", "")
        veredito = avaliar(comando)
        if not veredito.permitido:
            return ToolResult(
                tool_name="pc_comando",
                content=(
                    f"Bloqueado pela trava de segurança ({veredito.motivo}). Não tente "
                    "contornar. Explique ao Matheus o que você queria fazer."
                ),
                success=False,
            )
        resultado = self._executor(comando, timeout=60, json=False)
        partes = [f"Código de saída: {resultado.codigo}"]
        if resultado.saida.strip():
            partes.append(resultado.saida.strip())
        if resultado.erro.strip():
            partes.append("Erros: " + resultado.erro.strip())
        return ToolResult(
            tool_name="pc_comando",
            content="\n".join(partes)[:LIMITE_SAIDA],
            success=resultado.codigo == 0,
        )
