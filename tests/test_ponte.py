import threading
import unittest

from jarvis_pc.ponte import PonteConfirmacao


def perguntar_em_thread(ponte, texto):
    saida = {}

    def alvo():
        saida["resposta"] = ponte.pedir(texto)

    t = threading.Thread(target=alvo)
    t.start()
    return t, saida


def esperar_pedido(ponte):
    for _ in range(200):
        pedido = ponte.proximo()
        if pedido:
            return pedido
        threading.Event().wait(0.01)
    raise AssertionError("o pedido não chegou na fila")


class TestPonte(unittest.TestCase):
    def test_sim_chega_ao_agente(self):
        ponte = PonteConfirmacao(tempo_limite=5)
        t, saida = perguntar_em_thread(ponte, "posso?")
        pedido = esperar_pedido(ponte)
        self.assertEqual(pedido.texto, "posso?")
        pedido.responder(True)
        t.join(2)
        self.assertIs(saida["resposta"], True)

    def test_nao_chega_ao_agente(self):
        ponte = PonteConfirmacao(tempo_limite=5)
        t, saida = perguntar_em_thread(ponte, "posso?")
        esperar_pedido(ponte).responder(False)
        t.join(2)
        self.assertIs(saida["resposta"], False)

    def test_sem_resposta_no_prazo_e_nao(self):
        ponte = PonteConfirmacao(tempo_limite=0.05)
        self.assertIs(ponte.pedir("posso?"), False)

    def test_resposta_tardia_nao_muda_o_que_o_agente_ja_recebeu(self):
        ponte = PonteConfirmacao(tempo_limite=0.05)
        t, saida = perguntar_em_thread(ponte, "posso?")
        pedido = esperar_pedido(ponte)
        t.join(2)
        pedido.responder(True)
        self.assertIs(saida["resposta"], False)

    def test_primeira_resposta_vence(self):
        ponte = PonteConfirmacao(tempo_limite=5)
        t, saida = perguntar_em_thread(ponte, "posso?")
        pedido = esperar_pedido(ponte)
        pedido.responder(False)
        pedido.responder(True)
        t.join(2)
        self.assertIs(saida["resposta"], False)

    def test_fila_vazia_devolve_none(self):
        self.assertIsNone(PonteConfirmacao().proximo())


if __name__ == "__main__":
    unittest.main()
