"""Ponte de confirmação entre a thread do agente e a janela.

O agente roda numa thread e precisa de um Sim ou Não do Matheus. A janela
(tkinter) só pode ser mexida pela thread dela. A ponte guarda o pedido numa
fila; a janela busca, mostra e responde. Sem resposta no prazo, é Não.
"""
import queue
import threading


class Pedido:
    def __init__(self, texto):
        self.texto = texto
        self._evento = threading.Event()
        self._resposta = False
        self.expirado = False

    def responder(self, sim):
        if not self._evento.is_set():
            self._resposta = bool(sim)
            self._evento.set()

    def esperar(self, tempo_limite):
        if self._evento.wait(tempo_limite):
            return self._resposta
        self.expirado = True
        return False


class PonteConfirmacao:
    def __init__(self, tempo_limite=120.0):
        self.tempo_limite = tempo_limite
        self._fila = queue.Queue()

    def pedir(self, texto):
        """Chamado pelo agente. Bloqueia até a resposta; sem resposta, False."""
        pedido = Pedido(texto)
        self._fila.put(pedido)
        return pedido.esperar(self.tempo_limite)

    def proximo(self):
        """Chamado pela janela. Devolve o próximo Pedido ou None."""
        try:
            return self._fila.get_nowait()
        except queue.Empty:
            return None
