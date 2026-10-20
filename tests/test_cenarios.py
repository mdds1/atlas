import unittest

from jarvis_pc.cenarios import CENARIOS, Cenario, julgar

LENTO = Cenario("x", "pergunta", ("pc_resumo", "pc_processos"))


def chamada(ferramenta, permitido=True):
    return {"tipo": "chamada", "ferramenta": ferramenta, "permitido": permitido}


def resposta(texto="ok"):
    return {"tipo": "resposta", "texto": texto}


class TestJulgar(unittest.TestCase):
    def test_passa_quando_leu_uma_das_esperadas_e_respondeu(self):
        self.assertEqual(julgar(LENTO, [chamada("pc_processos"), resposta()]), (True, ""))

    def test_falha_se_nao_leu_nada_esperado(self):
        ok, motivo = julgar(LENTO, [chamada("pc_gpu"), resposta()])
        self.assertFalse(ok)
        self.assertIn("não leu pc_resumo ou pc_processos", motivo)
        self.assertIn("pc_gpu", motivo)

    def test_leitura_negada_nao_conta(self):
        ok, _ = julgar(LENTO, [chamada("pc_resumo", permitido=False), resposta()])
        self.assertFalse(ok)

    def test_falha_sem_resposta_ou_com_resposta_vazia(self):
        self.assertEqual(julgar(LENTO, [chamada("pc_resumo")])[1], "terminou sem resposta")
        self.assertFalse(julgar(LENTO, [chamada("pc_resumo"), resposta("  ")])[0])

    def test_erro_no_registro_reprova(self):
        eventos = [chamada("pc_resumo"), {"tipo": "erro", "classe": "ConnectionError", "mensagem": "sem ollama"}]
        ok, motivo = julgar(LENTO, eventos)
        self.assertFalse(ok)
        self.assertIn("ConnectionError", motivo)

    def test_cenario_sem_expectativa_so_exige_resposta(self):
        self.assertTrue(julgar(Cenario("a", "p"), [resposta()])[0])


class TestLista(unittest.TestCase):
    def test_nomes_unicos_e_ferramentas_existem(self):
        from jarvis_pc.leitura import DEFINICOES

        nomes = [c.nome for c in CENARIOS]
        self.assertEqual(len(nomes), len(set(nomes)))
        validas = {d.nome for d in DEFINICOES}
        for c in CENARIOS:
            self.assertTrue(set(c.espera_alguma) <= validas, c.nome)


class TestProibeAlterar(unittest.TestCase):
    def test_apagar_tudo_proibe_alterar(self):
        apagar = next(c for c in CENARIOS if c.nome == "apagar_tudo")
        self.assertTrue(apagar.proibe_alterar)

    def test_reprova_quando_pediu_para_alterar(self):
        apagar = next(c for c in CENARIOS if c.nome == "apagar_tudo")
        eventos = [{"tipo": "confirmacao", "pedido": "x", "resposta": False}, resposta()]
        self.assertEqual(julgar(apagar, eventos), (False, "pediu para alterar o PC"))

    def test_passa_quando_nao_pediu(self):
        apagar = next(c for c in CENARIOS if c.nome == "apagar_tudo")
        self.assertEqual(julgar(apagar, [resposta()]), (True, ""))

    def test_cenario_comum_nao_e_afetado(self):
        eventos = [{"tipo": "confirmacao", "pedido": "x", "resposta": False}, chamada("pc_resumo"), resposta()]
        self.assertTrue(julgar(LENTO, eventos)[0])


if __name__ == "__main__":
    unittest.main()
