"""Configuração da Jarvis, lida de um config.json ao lado da instalação."""
import json
from dataclasses import dataclass, fields
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
    return Config(**{k: v for k, v in dados.items() if k in nomes})
