"""Roda as três coletas em segundo plano, uma de cada vez, sem travar a janela."""
import threading
import time

from jarvis_pc.inventario.arquivos import varrer_arquivos
from jarvis_pc.inventario.pacotes import coletar_pacotes
from jarvis_pc.inventario.sistema import coletar_sistema
from jarvis_pc.ps import executar_powershell


class Atualizador:
    def __init__(self, banco, raizes, exclusoes, *, executor=executar_powershell, agora=time.time, sincrono=False):
        self.banco = banco
        self.raizes = list(raizes)
        self.exclusoes = exclusoes
        self._executor = executor
        self._agora = agora
        self._sincrono = sincrono
        self._ativa = False
        self._cancelar = False
        self._trava = threading.Lock()
        self.ultimo_erro = ""

    def rodando(self):
        return self._ativa

    def cancelar(self):
        with self._trava:
            if self._ativa:
                self._cancelar = True

    def iniciar(self):
        with self._trava:
            if self._ativa:
                return False
            self._ativa = True
        self.ultimo_erro = ""
        self._encerrar_pendentes()
        if self._sincrono:
            self._rodar()
        else:
            try:
                threading.Thread(target=self._rodar, name="inventario", daemon=True).start()
            except BaseException:
                self._ativa = False
                raise
        return True

    def _rodar(self):
        try:
            varrer_arquivos(
                self.banco, self.raizes, self.exclusoes, agora=self._agora, cancelado=lambda: self._cancelar
            )
            self._cancelar = False
            coleta = coletar_sistema(self.banco, executor=self._executor, agora=self._agora)
            if not coleta.ok:
                self.ultimo_erro = coleta.motivo
            else:
                coletar_pacotes(self.banco, coleta.pythons, coleta.npm, agora=self._agora)
        except Exception as erro:
            self.ultimo_erro = f"{type(erro).__name__}: {erro}"
        finally:
            self._cancelar = False
            self._encerrar_pendentes()
            self._ativa = False

    def _encerrar_pendentes(self):
        """Nenhuma varredura fica 'rodando' depois que a rodada termina, por qualquer caminho."""
        try:
            for v in self.banco.em_andamento():
                self.banco.encerrar_varredura(v["id"], "falhou", 1, self._agora())
        except Exception as erro:
            if not self.ultimo_erro:
                self.ultimo_erro = f"{type(erro).__name__}: {erro}"
