"""Ponto de entrada: python -m jarvis_pc [pasta-de-dados]."""
import sys
import time
import traceback
from pathlib import Path

from jarvis_pc.agente import criar_agente
from jarvis_pc.config import carregar
from jarvis_pc.ponte import PonteConfirmacao
from jarvis_pc.registro import Registro


def _falha_de_partida(pasta, erro, registro):
    """Deixa rastro da falha mesmo sem console (pythonw). Nunca levanta."""
    detalhe = "".join(traceback.format_exception(type(erro), erro, erro.__traceback__))
    try:
        arquivo = Path(pasta) / "erro-de-partida.txt"
        arquivo.write_text(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\n{detalhe}", encoding="utf-8")
    except Exception:
        pass
    if registro is not None:
        try:
            registro.evento("erro", classe=type(erro).__name__, mensagem=str(erro))
        except Exception:
            pass
    try:
        import tkinter as tk
        from tkinter import messagebox

        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror("A Jarvis nao iniciou", str(erro))
        raiz.destroy()
    except Exception:
        pass


def main(argv):
    pasta = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    registro = None
    try:
        config = carregar(pasta / "config.json")
        registro = Registro(pasta / config.registro)
        ponte = PonteConfirmacao(config.tempo_confirmacao)
        agente = criar_agente(
            modelo=config.modelo, confirmar=ponte.pedir, registro=registro, host=config.host
        )
        registro.evento("inicio", modelo=config.modelo)
        from jarvis_pc.janela import Janela

        Janela(agente, registro, ponte, config.tecla).iniciar()
        return 0
    except Exception as erro:
        _falha_de_partida(pasta, erro, registro)
        return 1
    finally:
        if registro is not None:
            registro.evento("fim")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
