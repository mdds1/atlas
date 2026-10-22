import threading
import unittest

from jarvis_pc.ponte import NAO, SIM, SIM_SEMPRE, PonteConfirmacao


def perguntar_em_thread(ponte, texto, pode_sempre=True):
    saida = {}

    def alvo():
        saida["resposta"] = ponte.pedir(texto, pode_sempre)

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
    def responder(self, resposta, pode_sempre=True):
        ponte = PonteConfirmacao(tempo_limite=5)
        t, saida = perguntar_em_thread(ponte, "posso?", pode_sempre)
        pedido = esperar_pedido(ponte)
        pedido.responder(resposta)
        t.join(2)
        return saida["resposta"], pedido

    def test_as_tres_respostas_chegam_ao_agente(self):
        for r in (SIM, SIM_SEMPRE, NAO):
            with self.subTest(r=r):
                self.assertEqual(self.responder(r)[0], r)

    def test_pedido_leva_texto_e_se_pode_sempre(self):
        _, pedido = self.responder(SIM, pode_sempre=False)
        self.assertEqual(pedido.texto, "posso?")
        self.assertIs(pedido.pode_sempre, False)

    def test_sim_sempre_quando_nao_pode_vira_nao(self):
        self.assertEqual(self.responder(SIM_SEMPRE, pode_sempre=False)[0], NAO)

    def test_resposta_estranha_vira_nao(self):
        for r in (True, 1, "Sim", "", None):
            with self.subTest(r=r):
                self.assertEqual(self.responder(r)[0], NAO)

    def test_sem_resposta_no_prazo_e_nao(self):
        self.assertEqual(PonteConfirmacao(tempo_limite=0.05).pedir("posso?"), NAO)

    def test_prazo_padrao_e_cinco_minutos(self):
        self.assertEqual(PonteConfirmacao().tempo_limite, 300.0)

    def test_resposta_tardia_nao_muda_o_que_o_agente_ja_recebeu(self):
        ponte = PonteConfirmacao(tempo_limite=0.05)
        t, saida = perguntar_em_thread(ponte, "posso?")
        pedido = esperar_pedido(ponte)
        t.join(2)
        pedido.responder(SIM)
        self.assertEqual(saida["resposta"], NAO)
        self.assertIs(pedido.expirado, True)
        self.assertEqual(pedido.esperar(0), NAO)

    def test_primeira_resposta_vence(self):
        ponte = PonteConfirmacao(tempo_limite=5)
        t, saida = perguntar_em_thread(ponte, "posso?")
        pedido = esperar_pedido(ponte)
        pedido.responder(NAO)
        pedido.responder(SIM)
        t.join(2)
        self.assertEqual(saida["resposta"], NAO)
        self.assertIs(pedido.expirado, False)
