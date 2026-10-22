"""Uma conversa com histórico, salva em <pasta>/<ident>.json.

Janela e Telegram usam a mesma sessão ativa. Só pergunta e resposta final
entram: o que as ferramentas devolveram (conteúdo de arquivo, saída de
comando) nunca é salvo aqui.
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path

PAPEIS = ("usuario", "atlas")
ORIGENS = ("janela", "telegram")


class Sessao:
    def __init__(self, pasta=None, ident=None):
        self.pasta = Path(pasta) if pasta else None
        self.ident = ident or time.strftime("%Y-%m-%d-%H%M%S")
        self.mensagens = []

    @classmethod
    def ultima(cls, pasta):
        pasta = Path(pasta)
        if pasta.is_dir():
            for arquivo in sorted(pasta.glob("*.json"), reverse=True):
                try:
                    dados = json.loads(arquivo.read_text(encoding="utf-8"))
                    mensagens = [m for m in dados["mensagens"] if m.get("papel") in PAPEIS and isinstance(m.get("texto"), str)]
                except (ValueError, KeyError, TypeError, AttributeError, OSError):
                    continue
                s = cls(pasta, ident=arquivo.stem)
                s.mensagens = mensagens
                return s
        return cls(pasta)

    def acrescentar(self, papel, texto, origem):
        if papel not in PAPEIS:
            raise ValueError(f"papel inválido: {papel!r}")
        if origem not in ORIGENS:
            raise ValueError(f"origem inválida: {origem!r}")
        self.mensagens.append(
            {"papel": papel, "texto": str(texto), "origem": origem, "quando": datetime.now().isoformat(timespec="seconds")}
        )
        self._salvar()

    def historico(self, limite=20):
        return [(m["papel"], m["texto"]) for m in self.mensagens[-limite:]]

    def _salvar(self):
        if not self.pasta:
            return
        self.pasta.mkdir(parents=True, exist_ok=True)
        destino = self.pasta / f"{self.ident}.json"
        tmp = destino.with_suffix(".tmp")
        tmp.write_text(json.dumps({"ident": self.ident, "mensagens": self.mensagens}, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, destino)
