"""Trava de instância única: um arquivo de trava na pasta de dados."""
from pathlib import Path


class Trava:
    def __init__(self, arquivo):
        self._arquivo = arquivo

    def liberar(self):
        try:
            _destravar(self._arquivo)
        finally:
            self._arquivo.close()


try:
    import msvcrt

    def _travar(f):
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)

    def _destravar(f):
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
except ImportError:
    import fcntl

    def _travar(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _destravar(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def travar(pasta):
    """Devolve a Trava, ou None se outra instância já a tem."""
    arquivo = open(Path(pasta) / "atlas.lock", "a+b")
    try:
        _travar(arquivo)
    except OSError:
        arquivo.close()
        return None
    return Trava(arquivo)
