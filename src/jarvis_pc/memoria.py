"""Fatos fixos que o Matheus mandou a Atlas lembrar, em memoria.json.

Só entra o que ele mandou (mem_lembrar pede OK). A lista entra no prompt de
toda conversa. Arquivo ilegível não é sobrescrito: a memória fica vazia e
somente leitura até ele consertar.
"""
import json
import os
import threading
import unicodedata
from datetime import datetime
from pathlib import Path

from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

LIMITE_FATOS = 50
LIMITE_TEXTO = 300


def _chave(texto):
    t = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in t if not unicodedata.combining(c)).casefold()


class Memoria:
    def __init__(self, caminho=None):
        self.caminho = Path(caminho) if caminho else None
        self._fatos = []
        self._proximo = 1
        self.erro = ""
        self._trava = threading.Lock()
        if self.caminho and self.caminho.exists():
            try:
                dados = json.loads(self.caminho.read_text(encoding="utf-8"))
                self._fatos = [f for f in dados["fatos"] if isinstance(f, dict) and isinstance(f.get("texto"), str)]
                self._proximo = int(dados.get("proximo", len(self._fatos) + 1))
            except (ValueError, KeyError, TypeError, OSError) as e:
                self._fatos = []
                self.erro = f"memoria.json ilegível ({e})"

    def listar(self):
        return [dict(f) for f in self._fatos]

    def lembrar(self, texto):
        if self.erro:
            raise ValueError(self.erro)
        if not isinstance(texto, str) or not texto.strip():
            raise ValueError("o fato está vazio")
        texto = " ".join(texto.split())
        if len(texto) > LIMITE_TEXTO:
            raise ValueError(f"o fato passa de {LIMITE_TEXTO} caracteres; resuma")
        with self._trava:
            for f in self._fatos:
                if _chave(f["texto"]) == _chave(texto):
                    return dict(f)
            if len(self._fatos) >= LIMITE_FATOS:
                raise ValueError(f"já há {LIMITE_FATOS} fatos; peça para esquecer algum antes")
            fato = {"id": self._proximo, "texto": texto, "quando": datetime.now().isoformat(timespec="seconds")}
            self._proximo += 1
            self._fatos.append(fato)
            self._salvar()
        return dict(fato)

    def esquecer(self, chave):
        if self.erro:
            raise ValueError(self.erro)
        alvo = str(chave if chave is not None else "").strip()
        if not alvo:
            raise ValueError("diga o número ou um trecho do fato")
        with self._trava:
            if alvo.isdigit():
                achados = [f for f in self._fatos if f["id"] == int(alvo)]
            else:
                achados = [f for f in self._fatos if _chave(alvo) in _chave(f["texto"])]
            if not achados:
                raise ValueError(f"não achei fato com {alvo!r}")
            if len(achados) > 1:
                lista = "; ".join(f"[{f['id']}] {f['texto']}" for f in achados)
                raise ValueError(f"mais de um fato casa com {alvo!r}: {lista}. Pergunte ao Matheus qual.")
            self._fatos.remove(achados[0])
            self._salvar()
        return dict(achados[0])

    def para_prompt(self):
        if not self._fatos:
            return ""
        return "Fatos que o Matheus pediu para lembrar:\n" + "\n".join(f"- [{f['id']}] {f['texto']}" for f in self._fatos)

    def _salvar(self):
        if not self.caminho:
            return
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.caminho.with_suffix(".tmp")
        tmp.write_text(json.dumps({"proximo": self._proximo, "fatos": self._fatos}, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.caminho)


class _FerramentaMemoria(BaseTool):
    def __init__(self, memoria, nome, descricao, acao):
        self._memoria, self._nome, self._descricao, self._acao = memoria, nome, descricao, acao
        self.tool_id = nome

    @property
    def spec(self):
        return ToolSpec(
            name=self._nome,
            description=self._descricao,
            parameters={
                "type": "object",
                "properties": {"fato": {"type": "string", "description": "O fato, ou o número dele para esquecer."}},
                "required": ["fato"],
            },
            category="memoria",
        )

    def execute(self, **params):
        try:
            texto = self._acao(self._memoria, params.get("fato"))
        except ValueError as e:
            return ToolResult(tool_name=self._nome, content=str(e), success=False)
        return ToolResult(tool_name=self._nome, content=texto)


def criar_ferramentas_memoria(memoria):
    def lembrar(m, fato):
        f = m.lembrar(fato)
        return f"Guardado como [{f['id']}]: {f['texto']}"

    def esquecer(m, fato):
        f = m.esquecer(fato)
        return f"Esquecido [{f['id']}]: {f['texto']}"

    return [
        _FerramentaMemoria(memoria, "mem_lembrar", "Guarda um fato que o Matheus mandou lembrar. Só use quando ele pedir.", lembrar),
        _FerramentaMemoria(memoria, "mem_esquecer", "Apaga um fato da memória, pelo número ou por um trecho.", esquecer),
    ]
