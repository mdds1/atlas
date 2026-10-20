#!/usr/bin/env python3
"""Sabotagens dos pontos de segurança (fora a trava, que tem a própria ferramenta).

Cada linha troca um trecho único por uma versão errada. Todas precisam ser
PEGAS: algum teste tem que falhar. Sai com 0 se todas foram pegas.

Uso: python tools/mutacoes.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mutar import RAIZ, executar  # noqa: E402

S = RAIZ / "src" / "jarvis_pc"
MUTACOES = [
    (S / "agente.py", "if not callable(confirmar):", "if False:"),
    (S / "agente.py", "permitido = nome in conhecidas", "permitido = True"),
    (S / "agente.py", 'if permitido and nome == "pc_comando":\n            permitido = avaliar', "if False:\n            permitido = avaliar"),
    (S / "agente.py", "            resposta = False\n", "            resposta = True\n"),
    (S / "agente.py", "parallel_tools=False", "parallel_tools=True"),
    (S / "agente.py", "interactive=True,", "interactive=False,"),
    (S / "agente.py", 'registro.evento("resposta", texto=resultado.content)', "pass"),
    (S / "agente.py", '"A Jarvis quer executar este comando no seu PC:\\n\\n"', '"Texto qualquer:\\n\\n"'),
    (S / "agente.py", "if not isinstance(comando, str) or not comando.strip():", "if not True or not comando.strip():"),
    (S / "agente.py", "pedido=texto_mostrado", "pedido=texto"),
    (S / "comando.py", "if not veredito.permitido:", "if False:"),
    (S / "comando.py", "requires_confirmation=True", "requires_confirmation=False"),
    (S / "comando.py", "timeout=60, json=False", "timeout=600, json=False"),
    (S / "comando.py", "success=resultado.codigo == 0", "success=True"),
    (S / "leitura.py", 'f"{AVISO}\\n{texto}"[:LIMITE_SAIDA]', "texto"),
    (S / "leitura.py", 'f"{AVISO}\\n{texto}"[:LIMITE_SAIDA]', 'f"{AVISO}\\n{texto}"'),
    (S / "leitura.py", "if resultado.codigo != 0 or not resultado.saida.strip():", "if False:"),
    (S / "leitura.py", "requires_confirmation=False,", "requires_confirmation=True,"),
    (S / "leitura.py", "formatar_atualizacoes, 120)", "formatar_atualizacoes, 30)"),
    (S / "ponte.py", "        return False\n\n\nclass PonteConfirmacao", "        return True\n\n\nclass PonteConfirmacao"),
    (S / "ponte.py", "if not self._evento.is_set():", "if True:"),
    (S / "registro.py", "return valor[:LIMITE_CAMPO] +", "return valor +"),
    (S / "ps.py", 'p.stdout.decode("utf-8", "replace")', 'p.stdout.decode("utf-8")'),
    (S / "ps.py", 'p.stderr.decode("utf-8", "replace")', 'p.stderr.decode("utf-8")'),
    (S / "ps.py", "except subprocess.TimeoutExpired:", "except ZeroDivisionError:"),
    (S / "ps.py", "except OSError as erro:", "except ZeroDivisionError as erro:"),
    (S / "ps.py", 'texto = envoltorio.replace("__SCRIPT__", script)', 'texto = envoltorio % script'),
    (S / "config.py", "if k in nomes", "if True"),
    (S / "verificar.py", "falhas += 0 if resultado.success else 1", "falhas += 0"),
    (S / "verificar.py", "return 1 if (falhas or carregou) else 0", "return 0"),
    (S / "verificar.py", 'carregou = "posthog" in sys.modules or', "carregou = False or"),
    (S / "verificar.py", ' or "openjarvis.analytics.client" in sys.modules', ""),
    (S / "comando.py", "veredito = avaliar(comando)", 'veredito = avaliar("Get-Date")'),
    (S / "trava.py", 'if categoria == "Cf" or (categoria == "Cc" and caractere != "\\t"):', 'if categoria == "Cc" and caractere != "\\t":'),
    (S / "trava.py", 'if categoria == "Cf" or (categoria == "Cc" and caractere != "\\t"):', 'if categoria == "Cf" or categoria == "Cc":'),
    (S / "agente.py", "if len(motivo) > 300:", "if len(motivo) > 3000:"),
    (S / "agente.py", 'motivo = " ".join(motivo.split())', "motivo = motivo"),
]


def main():
    escaparam = 0
    for arquivo, antes, depois in MUTACOES:
        print(f"{arquivo.name}: {antes[:60]!r} -> {depois[:30]!r}")
        codigo = executar(RAIZ, arquivo, antes, depois)
        if codigo != 0:
            escaparam += 1
    print(f"\n{len(MUTACOES)} sabotagens, {escaparam} com problema")
    return 1 if escaparam else 0


if __name__ == "__main__":
    sys.exit(main())
