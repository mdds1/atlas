"""Ponte de confirmação entre a thread do agente e quem mostra o pedido.

O agente roda numa thread e precisa de uma resposta do Matheus: Sim (só esta
vez), Sim sempre (grava regra) ou Não. Quem mostra (a janela agora, o Telegram
na parte 5) busca o pedido na fila e responde. Sem resposta no prazo, é Não.
Qualquer resposta fora das três também é Não, e Sim sempre num pedido que não
permite regra (origem Telegram) também.
"""
import queue
import threading

SIM, SIM_SEMPRE, NAO = "sim", "sim_sempre", "nao"


class Pedido:
    def __init__(self, texto, pode_sempre=True):
        self.texto = texto
        self.pode_sempre = bool(pode_sempre)
        self._evento = threading.Event()
        self._resposta = NAO
        self.expirado = False

    def responder(self, resposta):
        if self._evento.is_set():
            return
        if not isinstance(resposta, str) or resposta not in (SIM, SIM_SEMPRE):
            resposta = NAO
        if resposta == SIM_SEMPRE and not self.pode_sempre:
            resposta = NAO
        self._resposta = resposta
        self._evento.set()

    def esperar(self, tempo_limite):
        if self._evento.wait(tempo_limite):
            return self._resposta
        self.expirado = True
        self._evento.set()
        return NAO


class PonteConfirmacao:
    def __init__(self, tempo_limite=300.0):
        self.tempo_limite = tempo_limite
        self._fila = queue.Queue()

    def pedir(self, texto, pode_sempre=True):
        """Chamado pelo agente. Bloqueia até a resposta; sem resposta, NAO."""
        pedido = Pedido(texto, pode_sempre)
        self._fila.put(pedido)
        return pedido.esperar(self.tempo_limite)

    def proximo(self):
        """Chamado por quem mostra. Devolve o próximo Pedido ou None."""
        try:
            return self._fila.get_nowait()
        except queue.Empty:
            return None
