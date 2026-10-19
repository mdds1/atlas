"""Registro de auditoria: uma linha JSON por evento, em arquivo local."""
import json
import threading
from datetime import datetime
from pathlib import Path

LIMITE_CAMPO = 2000


def _cortar(valor):
    if isinstance(valor, str) and len(valor) > LIMITE_CAMPO:
        return valor[:LIMITE_CAMPO] + f"...[+{len(valor) - LIMITE_CAMPO}]"
    if isinstance(valor, dict):
        return {k: _cortar(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_cortar(v) for v in valor]
    return valor


class Registro:
    """Guarda eventos em memória e, se houver caminho, também no arquivo."""

    def __init__(self, caminho=None):
        self.caminho = Path(caminho) if caminho else None
        self.eventos = []
        self._trava = threading.Lock()
        if self.caminho:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)

    def evento(self, tipo, **dados):
        linha = {"quando": datetime.now().isoformat(timespec="seconds"), "tipo": tipo}
        linha.update(_cortar(dados))
        with self._trava:
            self.eventos.append(linha)
            if self.caminho:
                with self.caminho.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(linha, ensure_ascii=False) + "\n")
