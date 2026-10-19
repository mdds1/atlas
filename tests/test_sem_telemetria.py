import subprocess
import sys
import unittest


class TestSemTelemetria(unittest.TestCase):
    def test_montar_o_agente_nao_carrega_o_cliente_de_analytics(self):
        codigo = (
            "import sys, jarvis_pc.agente, jarvis_pc.leitura, jarvis_pc.comando;"
            "print('posthog' in sys.modules, 'openjarvis.analytics.client' in sys.modules)"
        )
        saida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, check=True)
        self.assertEqual(saida.stdout.strip(), "False False")


if __name__ == "__main__":
    unittest.main()
