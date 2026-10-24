"""Ponto de entrada: python -m jarvis_pc [pasta-de-dados]."""
import sys
import time
import traceback
from pathlib import Path

from jarvis_pc.agente import criar_agente
from jarvis_pc.config import carregar
from jarvis_pc.instancia import travar
from jarvis_pc.inventario.ferramentas import montar_inventario
from jarvis_pc.memoria import Memoria
from jarvis_pc.permissoes import Permissoes
from jarvis_pc.ponte import PonteConfirmacao
from jarvis_pc.registro import Registro
from jarvis_pc.sessao import Sessao


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
        messagebox.showerror("A Atlas nao iniciou", str(erro))
        raiz.destroy()
    except Exception:
        pass


def _atualizar_se_velho(atualizador, banco, registro):
    """Refaz o inventário ao abrir se faltar varredura ou se ela tiver mais de um dia. Nunca trava a janela."""
    try:
        ultima = banco.ultima_varredura("arquivos")
        if ultima is None or time.time() - ultima["fim"] > 86400:
            atualizador.iniciar()
    except Exception as erro:
        registro.evento("erro", classe=type(erro).__name__, mensagem=str(erro))


def main(argv):
    pasta = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    registro = None
    atualizador = None
    banco = None
    trava = None
    try:
        config = carregar(pasta / "config.json")
        registro = Registro(pasta / config.registro)
        trava = travar(pasta)
        if trava is None:
            registro.evento("ja_aberta")
            return 0
        ponte = PonteConfirmacao(config.tempo_confirmacao)
        extras, atualizador, banco = montar_inventario(pasta, config)
        agente = criar_agente(
            modelo=config.modelo,
            confirmar=ponte.pedir,
            registro=registro,
            host=config.host,
            extras=extras,
            max_passos=config.max_passos,
            permissoes=Permissoes(pasta / config.permissoes),
            memoria=Memoria(pasta / config.memoria),
            sessao=Sessao.ultima(pasta / config.conversas),
        )
        if agente.permissoes.erro:
            registro.evento("erro", classe="Permissoes", mensagem=agente.permissoes.erro)
        registro.evento("inicio", modelo=config.modelo)
        if config.atualizar_ao_abrir:
            _atualizar_se_velho(atualizador, banco, registro)
        from jarvis_pc.janela import Janela

        Janela(agente, registro, ponte, config.tecla).iniciar()
        return 0
    except Exception as erro:
        _falha_de_partida(pasta, erro, registro)
        return 1
    finally:
        if trava is not None:
            trava.liberar()
        if atualizador is not None:
            atualizador.cancelar()
        if banco is not None:
            try:
                banco.fechar()
            except Exception:
                pass
        if registro is not None:
            registro.evento("fim")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
