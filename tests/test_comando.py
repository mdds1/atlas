import unittest

from jarvis_pc.comando import ComandoPcTool

from tests.ajuda import ExecutorFalso


class TestComando(unittest.TestCase):
    def test_exige_confirmacao_e_pede_comando_e_motivo(self):
        spec = ComandoPcTool(ExecutorFalso()).spec
        self.assertTrue(spec.requires_confirmation)
        self.assertEqual(spec.name, "pc_comando")
        self.assertEqual(sorted(spec.parameters["required"]), ["comando", "motivo"])

    def test_comando_proibido_nao_chega_ao_powershell(self):
        ex = ExecutorFalso()
        r = ComandoPcTool(ex).execute(comando="Remove-Item C:\\x -Recurse", motivo="limpar")
        self.assertFalse(r.success)
        self.assertIn("Bloqueado pela trava de segurança", r.content)
        self.assertIn("apagar pasta inteira", r.content)
        self.assertEqual(ex.chamadas, [])

    def test_comando_vazio_nao_chega_ao_powershell(self):
        ex = ExecutorFalso()
        r = ComandoPcTool(ex).execute(motivo="x")
        self.assertFalse(r.success)
        self.assertEqual(ex.chamadas, [])

    def test_comando_permitido_roda_em_modo_texto_com_limite(self):
        ex = ExecutorFalso(saida="Spooler reiniciado")
        r = ComandoPcTool(ex).execute(comando="Restart-Service -Name Spooler", motivo="travado")
        self.assertTrue(r.success)
        self.assertEqual(ex.chamadas, [{"script": "Restart-Service -Name Spooler", "timeout": 60, "json": False}])
        self.assertIn("Código de saída: 0", r.content)
        self.assertIn("Spooler reiniciado", r.content)

    def test_codigo_de_saida_diferente_de_zero_e_falha(self):
        ex = ExecutorFalso(saida="", codigo=1, erro="serviço não existe")
        r = ComandoPcTool(ex).execute(comando="Restart-Service -Name X", motivo="x")
        self.assertFalse(r.success)
        self.assertIn("Código de saída: 1", r.content)
        self.assertIn("Erros: serviço não existe", r.content)


if __name__ == "__main__":
    unittest.main()
