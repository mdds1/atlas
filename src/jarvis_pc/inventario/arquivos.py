"""Varredura dos arquivos: percorre as raízes, poda o que é excluído e grava no banco.

Lê só metadados (nome, tamanho, data); nunca abre um arquivo. Não segue link
simbólico nem ponto de reparse (junção do Windows), para não entrar em laço nem
em pasta do sistema que aponta para outra.
"""
import os
import time
from dataclasses import dataclass

REPARSE = 0x400


@dataclass(frozen=True)
class ResultadoVarredura:
    id: int
    arquivos: int
    erros: int
    segundos: float
    estado: str


def _reparse(entrada):
    return bool(getattr(entrada.stat(follow_symlinks=False), "st_file_attributes", 0) & REPARSE)


def _extensao(nome):
    return "." + nome.rpartition(".")[2].lower() if "." in nome.lstrip(".") else ""


def varrer_arquivos(banco, raizes, exclusoes, *, agora=time.time, cancelado=lambda: False, lote=2000):
    inicio = agora()
    vid = banco.iniciar_varredura("arquivos", inicio)
    pilha = list(raizes)
    pendentes, total, erros = [], 0, 0
    estado = "ok"
    try:
        while pilha:
            if cancelado():
                estado = "cancelada"
                break
            pasta = pilha.pop()
            if exclusoes.pasta_podada(pasta):
                continue
            try:
                with os.scandir(pasta) as it:
                    entradas = list(it)
            except OSError:
                erros += 1
                continue
            for e in entradas:
                try:
                    if e.is_symlink() or _reparse(e):
                        continue
                    if e.is_dir(follow_symlinks=False):
                        pilha.append(e.path)
                        continue
                    if not e.is_file(follow_symlinks=False) or exclusoes.arquivo_excluido(e.path):
                        continue
                    st = e.stat(follow_symlinks=False)
                except OSError:
                    erros += 1
                    continue
                pendentes.append((e.path, e.name, _extensao(e.name), pasta, st.st_size, st.st_mtime))
                if len(pendentes) >= lote:
                    banco.gravar("arquivos", vid, pendentes)
                    total += len(pendentes)
                    pendentes = []
                    banco.progresso(vid, total)
        if pendentes:
            banco.gravar("arquivos", vid, pendentes)
            total += len(pendentes)
        banco.progresso(vid, total)
    except Exception:
        banco.encerrar_varredura(vid, "falhou", erros, agora())
        raise
    fim = agora()
    banco.encerrar_varredura(vid, estado, erros, fim)
    return ResultadoVarredura(vid, total, erros, fim - inicio, estado)
