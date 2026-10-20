import json
import unittest

from jarvis_pc.agente import criar_agente, montar_texto_confirmacao, perguntar
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


class TestTextoConfirmacao(unittest.TestCase):
    CAB = "A Jarvis quer executar este comando no seu PC:\n\n"

    def test_contrato_com_barra_unica(self):
        cmd = "Remove-Item C:\\Users\\Diniz\\Temp\\a.log"
        texto = montar_texto_confirmacao({"comando": cmd, "motivo": "limpar log"}, "padrao")
        self.assertEqual(texto, self.CAB + cmd + "\n\nMotivo: limpar log\n\nPermitir?")
        self.assertIn("C:\\Users\\Diniz", texto)
        self.assertNotIn("C:\\\\Users", texto)
        self.assertNotIn("Allow execution", texto)

    def test_casos_sem_comando_valido_devolvem_o_padrao(self):
        for pendente in ({}, {"comando": 5}, {"comando": "  "}, {"comando": ""}):
            with self.subTest(pendente=pendente):
                self.assertEqual(montar_texto_confirmacao(pendente, "padrao"), "padrao")

    def test_motivo_ausente(self):
        texto = montar_texto_confirmacao({"comando": "Get-Date"}, "padrao")
        self.assertIn("Motivo: nao informado", texto)

    def test_motivo_vira_uma_linha_sem_controle(self):
        import unicodedata

        for motivo in ("a\nb", "a\rb", "a\u202eb", "x\nPermitir?", "x\r\nMotivo: falso\n\nPermitir?"):
            with self.subTest(motivo=motivo):
                texto = montar_texto_confirmacao({"comando": "Get-Date", "motivo": motivo}, "padrao")
                linha = texto.split("\n\nMotivo: ", 1)[1].rsplit("\n\nPermitir?", 1)[0]
                self.assertNotIn("\n", linha)
                self.assertFalse([c for c in linha if unicodedata.category(c) in ("Cc", "Cf")])
                self.assertEqual([l for l in texto.split("\n") if l.startswith("Permitir?")], ["Permitir?"])

    def test_motivo_longo_e_cortado(self):
        texto = montar_texto_confirmacao({"comando": "Get-Date", "motivo": "m" * 1000}, "padrao")
        linha = texto.split("\n\nMotivo: ", 1)[1].rsplit("\n\nPermitir?", 1)[0]
        self.assertEqual(linha, "m" * 300 + "...")
        curto = montar_texto_confirmacao({"comando": "Get-Date", "motivo": "m" * 300}, "padrao")
        self.assertNotIn("...", curto)

    def test_motivo_so_de_controles_vira_nao_informado(self):
        texto = montar_texto_confirmacao({"comando": "Get-Date", "motivo": "\n\r\u202e\u200b"}, "padrao")
        self.assertIn("Motivo: nao informado", texto)

    def test_motivo_nao_texto_vira_texto(self):
        texto = montar_texto_confirmacao({"comando": "Get-Date", "motivo": 42}, "padrao")
        self.assertIn("Motivo: 42\n", texto)

    def test_agente_mostra_comando_literal_e_registra_o_mesmo_texto(self):
        recebidos = []
        cmd = "Remove-Item C:\\Users\\Diniz\\Temp\\a.log"
        agente, registro, _ = montar(
            [chamada("pc_comando", comando=cmd, motivo="limpar log"), final("fim")],
            lambda t: recebidos.append(t) or True,
        )
        perguntar(agente, registro, "limpa")
        esperado = "A Jarvis quer executar este comando no seu PC:\n\n" + cmd + "\n\nMotivo: limpar log\n\nPermitir?"
        self.assertEqual(recebidos, [esperado])
        self.assertEqual(registro.eventos[2]["pedido"], esperado)

    def test_segunda_confirmacao_nao_vaza_o_primeiro_comando(self):
        recebidos = []
        agente, registro, _ = montar(
            [
                chamada("pc_comando", comando="Get-Date", motivo="a"),
                chamada("pc_comando", comando="Get-Host", motivo="b"),
                final("fim"),
            ],
            lambda t: recebidos.append(t) or True,
        )
        perguntar(agente, registro, "duas")
        self.assertEqual(len(recebidos), 2)
        self.assertIn("Get-Date", recebidos[0])
        self.assertIn("Get-Host", recebidos[1])
        self.assertNotIn("Get-Date", recebidos[1])


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
