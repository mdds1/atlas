import json
import unittest

from openjarvis.core.types import Message, Role, ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

from jarvis_pc.laco import rodar_laco

from tests.ajuda import MotorFalso, chamada, final


class Falsa(BaseTool):
    def __init__(self, nome, conteudo="ok", sucesso=True, explode=False):
        self.tool_id = nome
        self._nome, self._conteudo, self._sucesso, self._explode = nome, conteudo, sucesso, explode
        self.recebidos = []

    @property
    def spec(self):
        return ToolSpec(name=self._nome, description="falsa", parameters={"type": "object", "properties": {}})

    def execute(self, **params):
        self.recebidos.append(params)
        if self._explode:
            raise RuntimeError("quebrou")
        return ToolResult(tool_name=self._nome, content=self._conteudo, success=self._sucesso)


def libera(_n, _a):
    return ("rodar", "")


def acoes(*nomes):
    return lambda n: n in nomes


def inicio():
    return [Message(role=Role.SYSTEM, content="sis"), Message(role=Role.USER, content="pedido")]


class TestLaco(unittest.TestCase):
    def test_resposta_direta(self):
        r = rodar_laco(MotorFalso([final(" Pronto. ")]), "m", inicio(), [], libera, acoes())
        self.assertEqual((r.texto, r.parou, r.passos), ("Pronto.", "fim", []))

    def test_executa_ferramenta_e_devolve_resultado_ao_modelo(self):
        ler = Falsa("ler", conteudo="CPU 10%")
        motor = MotorFalso([chamada("ler", x=1), final("CPU baixa.")])
        r = rodar_laco(motor, "m", inicio(), [ler], libera, acoes())
        self.assertEqual(r.texto, "CPU baixa.")
        self.assertEqual(ler.recebidos, [{"x": 1}])
        ultima = motor.vistas[1][-1]
        self.assertEqual((ultima.role, ultima.content, ultima.name), (Role.TOOL, "CPU 10%", "ler"))
        self.assertEqual(motor.kwargs[0]["tools"][0]["function"]["name"], "ler")

    def test_recusa_vai_ao_modelo_e_nao_executa(self):
        acao = Falsa("acao")
        motor = MotorFalso([chamada("acao"), final("Não posso.")])
        r = rodar_laco(motor, "m", inicio(), [acao], lambda n, a: ("recusar", "BLOQUEADO: trava"), acoes("acao"))
        self.assertEqual(acao.recebidos, [])
        self.assertEqual(motor.vistas[1][-1].content, "BLOQUEADO: trava")
        self.assertEqual(r.parou, "fim")
        self.assertFalse(r.passos[0].executou)

    def test_parar_encerra_na_hora_sem_executar(self):
        acao = Falsa("acao")
        motor = MotorFalso([chamada("acao"), final("nunca chega")])
        r = rodar_laco(motor, "m", inicio(), [acao], lambda n, a: ("parar", "Você disse Não."), acoes("acao"))
        self.assertEqual((r.texto, r.parou), ("Você disse Não.", "nao"))
        self.assertEqual(acao.recebidos, [])
        self.assertEqual(motor.chamadas, 1)

    def test_acao_que_falha_para_no_primeiro_erro_e_relata(self):
        ok = Falsa("acao_ok", conteudo="feito")
        ruim = Falsa("acao_ruim", conteudo="Código de saída: 1", sucesso=False)
        motor = MotorFalso([chamada("acao_ok", a=1), chamada("acao_ruim", b=2), final("nunca chega")])
        r = rodar_laco(motor, "m", inicio(), [ok, ruim], libera, acoes("acao_ok", "acao_ruim"))
        self.assertEqual(r.parou, "erro_acao")
        self.assertEqual(motor.chamadas, 2)
        self.assertIn("acao_ruim", r.texto)
        self.assertIn("Código de saída: 1", r.texto)
        self.assertIn("acao_ok", r.texto)

    def test_leitura_que_falha_nao_para(self):
        ler = Falsa("ler", conteudo="falhou a leitura", sucesso=False)
        r = rodar_laco(MotorFalso([chamada("ler"), final("Não consegui ler.")]), "m", inicio(), [ler], libera, acoes())
        self.assertEqual(r.parou, "fim")

    def test_excecao_na_ferramenta_vira_falha(self):
        acao = Falsa("acao", explode=True)
        r = rodar_laco(MotorFalso([chamada("acao"), final("x")]), "m", inicio(), [acao], libera, acoes("acao"))
        self.assertEqual(r.parou, "erro_acao")
        self.assertIn("RuntimeError", r.texto)

    def test_ferramenta_sem_implementacao_e_recusada_ao_modelo(self):
        motor = MotorFalso([chamada("fantasma"), final("ok")])
        r = rodar_laco(motor, "m", inicio(), [], libera, acoes())
        self.assertIn("não existe", motor.vistas[1][-1].content)
        self.assertEqual(r.parou, "fim")

    def test_argumentos_que_nao_sao_json(self):
        acao = Falsa("acao")
        quebrada = {"content": "", "tool_calls": [{"id": "c1", "name": "acao", "arguments": "{nao json"}], "usage": {}}
        motor = MotorFalso([quebrada, final("ok")])
        rodar_laco(motor, "m", inicio(), [acao], libera, acoes("acao"))
        self.assertEqual(acao.recebidos, [])
        self.assertIn("JSON", motor.vistas[1][-1].content)

    def test_limite_de_passos(self):
        ler = Falsa("ler")
        motor = MotorFalso([chamada("ler")] * 3)
        r = rodar_laco(motor, "m", inicio(), [ler], libera, acoes(), max_passos=3)
        self.assertEqual((r.parou, motor.chamadas, len(ler.recebidos)), ("limite", 3, 3))
        self.assertIn("3 passos", r.texto)

    def test_ao_resultado_recebe_cada_execucao(self):
        vistos = []
        ler = Falsa("ler", conteudo="dado")
        rodar_laco(MotorFalso([chamada("ler"), final("x")]), "m", inicio(), [ler], libera, acoes(),
                   ao_resultado=lambda n, res: vistos.append((n, res.content)))
        self.assertEqual(vistos, [("ler", "dado")])
