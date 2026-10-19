import contextlib
import io
import sys
import types
import unittest
from unittest import mock

from jarvis_pc.verificar import main, verificar

from tests.ajuda import ExecutorFalso


class TestVerificar(unittest.TestCase):
    def test_todas_as_leituras_ok(self):
        linhas, falhas = verificar(ExecutorFalso(saida="{}"))
        self.assertEqual(falhas, 0)
        self.assertEqual(len(linhas), 8)
        self.assertTrue(all(l.startswith("ok    pc_") for l in linhas))

    def test_conta_cada_falha(self):
        linhas, falhas = verificar(ExecutorFalso(saida="", codigo=-1, erro="sem powershell"))
        self.assertEqual(falhas, 8)
        self.assertTrue(all(l.startswith("FALHA pc_") for l in linhas))
        self.assertIn("Falha ao ler: sem powershell", linhas[0])

    def test_resumo_mostra_a_primeira_linha_de_dados_e_nao_o_aviso(self):
        linhas, _ = verificar(ExecutorFalso(saida="{}"))
        self.assertNotIn("dados lidos do PC", linhas[0])


class TestMain(unittest.TestCase):
    def rodar(self, executor):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            codigo = main(executor)
        return codigo, saida.getvalue()

    def test_sai_com_zero_quando_tudo_funciona(self):
        codigo, texto = self.rodar(ExecutorFalso(saida="{}"))
        self.assertEqual(codigo, 0)
        self.assertIn("telemetria carregada: False", texto)
        self.assertIn("8 de 8 leituras ok", texto)

    def test_sai_com_um_se_o_cliente_de_telemetria_foi_carregado(self):
        for modulo in ("posthog", "openjarvis.analytics.client"):
            with self.subTest(modulo=modulo):
                with mock.patch.dict(sys.modules, {modulo: types.ModuleType(modulo)}):
                    codigo, texto = self.rodar(ExecutorFalso(saida="{}"))
                self.assertEqual(codigo, 1)
                self.assertIn("telemetria carregada: True", texto)

    def test_sai_com_um_quando_alguma_leitura_falha(self):
        codigo, texto = self.rodar(ExecutorFalso(saida="", codigo=-1, erro="x"))
        self.assertEqual(codigo, 1)
        self.assertIn("0 de 8 leituras ok", texto)


if __name__ == "__main__":
    unittest.main()
