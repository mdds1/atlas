"""Verificação rápida no PC: a telemetria ficou de fora e as oito leituras funcionam.

Uso: python -m jarvis_pc.verificar
Sai com 0 só se nenhuma leitura falhou e o cliente de analytics não foi carregado.
"""
import importlib
import sys

from jarvis_pc.leitura import criar_ferramentas_leitura


def verificar(executor=None):
    """Roda as oito leituras. Devolve (linhas, falhas)."""
    ferramentas = criar_ferramentas_leitura(executor) if executor else criar_ferramentas_leitura()
    linhas, falhas = [], 0
    for ferramenta in ferramentas:
        resultado = ferramenta.execute()
        partes = resultado.content.splitlines() or [""]
        resumo = partes[1] if resultado.success and len(partes) > 1 else partes[0]
        linhas.append(f"{'ok   ' if resultado.success else 'FALHA'} {ferramenta.spec.name}: {resumo[:90]}")
        falhas += 0 if resultado.success else 1
    return linhas, falhas


def main(executor=None):
    importlib.import_module("jarvis_pc.agente")  # carrega a cadeia completa antes de olhar sys.modules
    carregou = "posthog" in sys.modules or "openjarvis.analytics.client" in sys.modules
    print(f"telemetria carregada: {carregou}")
    linhas, falhas = verificar(executor)
    print("\n".join(linhas))
    print(f"{len(linhas) - falhas} de {len(linhas)} leituras ok")
    return 1 if (falhas or carregou) else 0


if __name__ == "__main__":
    sys.exit(main())
