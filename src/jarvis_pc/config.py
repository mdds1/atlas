"""Configuração da Jarvis, lida de um config.json ao lado da instalação."""
import json
from dataclasses import dataclass, fields, replace
from pathlib import Path


@dataclass(frozen=True)
class Config:
    modelo: str = "gemma4:12b-it-q4_K_M"
    host: str = "http://localhost:11434"
    registro: str = "registro.jsonl"
    tecla: str = "J"
    tempo_confirmacao: float = 120.0


def carregar(caminho):
    """Lê o JSON, ignora chaves desconhecidas e usa o padrão no que faltar."""
    caminho = Path(caminho)
    if not caminho.exists():
        return Config()
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except ValueError as erro:
        raise ValueError(f"config inválida em {caminho}: {erro}") from erro
    if not isinstance(dados, dict):
        raise ValueError(f"config inválida em {caminho}: esperado um objeto JSON")
    nomes = {f.name for f in fields(Config)}
    config = Config(**{k: v for k, v in dados.items() if k in nomes})
    return _validar(config, caminho)


def _validar(config, caminho):
    def erro(explicacao):
        return ValueError(f"config inválida em {caminho}: {explicacao}")

    for campo in ("modelo", "host", "registro"):
        valor = getattr(config, campo)
        if not isinstance(valor, str) or not valor.strip():
            raise erro(f"{campo} deve ser um texto não vazio")
    tecla = config.tecla
    if not isinstance(tecla, str) or len(tecla) != 1 or not (tecla.isascii() and tecla.isalnum()):
        raise erro("tecla deve ser uma única letra ou número (A-Z, 0-9)")
    tempo = config.tempo_confirmacao
    if isinstance(tempo, bool) or not isinstance(tempo, (int, float)) or not 0 < tempo <= 3600:
        raise erro("tempo_confirmacao deve ser um número maior que 0 e até 3600 (segundos)")
    return replace(config, tecla=tecla.upper())
