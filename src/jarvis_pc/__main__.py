"""Ponto de entrada: python -m jarvis_pc [pasta-de-dados]."""
import sys
from pathlib import Path

from jarvis_pc.agente import criar_agente
from jarvis_pc.config import carregar
from jarvis_pc.janela import Janela
from jarvis_pc.ponte import PonteConfirmacao
from jarvis_pc.registro import Registro


def main(argv):
    pasta = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    config = carregar(pasta / "config.json")
    registro = Registro(pasta / config.registro)
    ponte = PonteConfirmacao(config.tempo_confirmacao)
    agente = criar_agente(
        modelo=config.modelo, confirmar=ponte.pedir, registro=registro, host=config.host
    )
    registro.evento("inicio", modelo=config.modelo)
    Janela(agente, registro, ponte, config.tecla).iniciar()
    registro.evento("fim")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
