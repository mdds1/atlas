import json
import unittest

from jarvis_pc.agente import criar_agente, perguntar
from jarvis_pc.registro import Registro

from tests.ajuda import ExecutorFalso, MotorFalso, chamada, final, fixture


def nunca(_texto):
    raise AssertionError("a confirmação não devia ser pedida")


def montar(roteiro, confirmar, executor=None):
    registro = Registro()
    executor = executor or ExecutorFalso(saida=json.dumps(fixture("resumo")))
    agente = criar_agente(
        modelo="falso", confirmar=confirmar, registro=registro, executor=executor, engine=MotorFalso(roteiro)
    )
    return agente, registro, executor


def tipos(registro):
    return [e["tipo"] for e in registro.eventos]


class TestLeitura(unittest.TestCase):
    def test_leitura_roda_sem_pedir_confirmacao(self):
        agente, registro, executor = montar([chamada("pc_resumo"), final("Disco ok.")], nunca)
        self.assertEqual(perguntar(agente, registro, "o pc está lento?"), "Disco ok.")
        self.assertEqual(len(executor.chamadas), 1)
        self.assertEqual(tipos(registro), ["pergunta", "chamada", "resposta"])
        self.assertTrue(registro.eventos[1]["permitido"])


class TestComando(unittest.TestCase):
    ARGS = {"comando": "Restart-Service -Name Spooler", "motivo": "travado"}

    def test_comando_com_ok_executa(self):
        pedidos = []
        agente, registro, executor = montar(
            [chamada("pc_comando", **self.ARGS), final("Reiniciei.")],
            lambda texto: pedidos.append(texto) or True,
        )
        perguntar(agente, registro, "conserta a impressora")
        self.assertEqual(len(pedidos), 1)
        self.assertIn("Restart-Service -Name Spooler", pedidos[0])
        self.assertEqual([c["script"] for c in executor.chamadas], ["Restart-Service -Name Spooler"])
        self.assertEqual(tipos(registro), ["pergunta", "chamada", "confirmacao", "resposta"])
        self.assertIs(registro.eventos[2]["resposta"], True)

    def test_comando_sem_ok_nao_executa(self):
        agente, registro, executor = montar(
            [chamada("pc_comando", **self.ARGS), final("Ok, não reiniciei.")], lambda _t: False
        )
        perguntar(agente, registro, "conserta a impressora")
        self.assertEqual(executor.chamadas, [])
        self.assertIs(registro.eventos[2]["resposta"], False)

    def test_erro_na_confirmacao_conta_como_nao(self):
        def quebra(_texto):
            raise RuntimeError("janela fechou")

        agente, registro, executor = montar([chamada("pc_comando", **self.ARGS), final("fim")], quebra)
        perguntar(agente, registro, "conserta")
        self.assertEqual(executor.chamadas, [])
        self.assertIs(registro.eventos[2]["resposta"], False)

    def test_comando_proibido_nem_chega_a_pedir_confirmacao(self):
        agente, registro, executor = montar(
            [chamada("pc_comando", comando="Remove-Item C:\\Jogos -Recurse", motivo="liberar espaço"), final("fim")],
            nunca,
        )
        perguntar(agente, registro, "libera espaço")
        self.assertEqual(executor.chamadas, [])
        self.assertEqual(tipos(registro), ["pergunta", "chamada", "resposta"])
        self.assertIs(registro.eventos[1]["permitido"], False)

    def test_ferramenta_desconhecida_e_negada(self):
        agente, registro, executor = montar([chamada("shell_exec", command="dir"), final("fim")], nunca)
        perguntar(agente, registro, "roda um dir")
        self.assertEqual(executor.chamadas, [])
        self.assertIs(registro.eventos[1]["permitido"], False)
        self.assertEqual(registro.eventos[1]["ferramenta"], "shell_exec")


class TestSequencial(unittest.TestCase):
    def test_duas_confirmacoes_na_mesma_vez_nunca_se_sobrepoem(self):
        import threading
        import time

        trava, estado = threading.Lock(), {"agora": 0, "maximo": 0}

        def confirmar(_texto):
            with trava:
                estado["agora"] += 1
                estado["maximo"] = max(estado["maximo"], estado["agora"])
            time.sleep(0.15)
            with trava:
                estado["agora"] -= 1
            return True

        duas = {
            "content": "",
            "tool_calls": [
                {"id": "a", "name": "pc_comando", "arguments": json.dumps({"comando": "Get-Date", "motivo": "x"})},
                {"id": "b", "name": "pc_comando", "arguments": json.dumps({"comando": "Get-Host", "motivo": "x"})},
            ],
            "usage": {},
        }
        agente, registro, executor = montar([duas, final("fim")], confirmar)
        perguntar(agente, registro, "faça as duas coisas")
        self.assertEqual(len(executor.chamadas), 2)
        self.assertEqual(estado["maximo"], 1)


class TestMontagem(unittest.TestCase):
    def test_sem_confirmacao_o_agente_nao_e_criado(self):
        for confirmar in (None, "sim", 1):
            with self.subTest(confirmar=confirmar):
                with self.assertRaises(ValueError):
                    criar_agente(modelo="m", confirmar=confirmar, registro=Registro(), engine=MotorFalso([]))

    def test_erro_do_motor_e_registrado_e_repassado(self):
        agente, registro, _ = montar([], nunca)  # roteiro vazio: pop de lista vazia
        with self.assertRaises(Exception):
            perguntar(agente, registro, "oi")
        self.assertEqual(tipos(registro)[-1], "erro")
        self.assertIn("classe", registro.eventos[-1])


if __name__ == "__main__":
    unittest.main()
