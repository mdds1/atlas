import json
import unittest

from jarvis_pc.inventario import sistema
from jarvis_pc.inventario.banco import Banco
from jarvis_pc.inventario.sistema import coletar_sistema
from jarvis_pc.leitura import ler_script

from tests.ajuda import ExecutorFalso, fixture


def nomes(banco, tabela):
    return sorted(r["nome"] for r in banco.consultar(f"SELECT nome FROM {tabela}"))


class TestColeta(unittest.TestCase):
    def setUp(self):
        self.banco = Banco()
        self.addCleanup(self.banco.fechar)

    def test_grava_apps_servicos_tarefas_e_inicializacao(self):
        ex = ExecutorFalso(saida=json.dumps(fixture("inventario_sistema")))
        r = coletar_sistema(self.banco, executor=ex)
        self.assertTrue(r.ok)
        self.assertEqual(nomes(self.banco, "apps"), ["Git", "Microsoft.WindowsCalculator", "Ollama"])
        self.assertEqual(nomes(self.banco, "servicos"), ["Spooler", "wuauserv"])
        self.assertEqual(nomes(self.banco, "tarefas"), ["ScheduledDefrag"])
        self.assertEqual(nomes(self.banco, "inicializacao"), ["Discord"])
        self.assertEqual(r.itens, 3 + 2 + 1 + 1)

    def test_devolve_caminhos_de_python_e_npm(self):
        ex = ExecutorFalso(saida=json.dumps(fixture("inventario_sistema")))
        r = coletar_sistema(self.banco, executor=ex)
        self.assertEqual(r.pythons, ["C:\\Users\\Diniz\\AppData\\Local\\Programs\\Python\\Python310\\"])
        self.assertEqual(r.npm, "C:\\Users\\Diniz\\AppData\\Roaming\\npm\\node_modules")

    def test_varredura_fica_registrada_como_ok(self):
        coletar_sistema(self.banco, executor=ExecutorFalso(saida=json.dumps(fixture("inventario_sistema"))))
        self.assertEqual(self.banco.ultima_varredura("sistema")["estado"], "ok")

    def test_uma_lista_de_um_item_chega_como_objeto_e_funciona(self):
        d = fixture("inventario_sistema")
        d["servicos"] = d["servicos"][0]
        d["pythons"] = d["pythons"][0]
        r = coletar_sistema(self.banco, executor=ExecutorFalso(saida=json.dumps(d)))
        self.assertEqual(nomes(self.banco, "servicos"), ["Spooler"])
        self.assertEqual(r.pythons, ["C:\\Users\\Diniz\\AppData\\Local\\Programs\\Python\\Python310\\"])

    def test_campos_ausentes_viram_vazio_sem_quebrar(self):
        r = coletar_sistema(self.banco, executor=ExecutorFalso(saida=json.dumps({"apps": [{"nome": "So Nome"}]})))
        self.assertTrue(r.ok)
        self.assertEqual(nomes(self.banco, "apps"), ["So Nome"])
        self.assertEqual((r.pythons, r.npm), ([], ""))

    def test_falha_do_powershell_nao_apaga_o_que_existia(self):
        coletar_sistema(self.banco, executor=ExecutorFalso(saida=json.dumps(fixture("inventario_sistema"))))
        r = coletar_sistema(self.banco, executor=ExecutorFalso(saida="", codigo=1, erro="negado"))
        self.assertFalse(r.ok)
        self.assertIn("negado", r.motivo)
        self.assertEqual(len(nomes(self.banco, "apps")), 3)
        self.assertEqual(self.banco.consultar("SELECT estado FROM varreduras ORDER BY id DESC LIMIT 1")[0]["estado"], "falhou")

    def test_json_invalido_e_falha_limpa(self):
        r = coletar_sistema(self.banco, executor=ExecutorFalso(saida="isto nao e json"))
        self.assertFalse(r.ok)

    def test_usa_o_script_e_um_prazo_longo(self):
        ex = ExecutorFalso(saida=json.dumps(fixture("inventario_sistema")))
        coletar_sistema(self.banco, executor=ex)
        self.assertEqual(ex.chamadas[0]["script"], ler_script("inventario_sistema"))
        self.assertGreaterEqual(ex.chamadas[0]["timeout"], 120)


class TestScript(unittest.TestCase):
    def test_script_so_le(self):
        texto = ler_script("inventario_sistema").lower()
        for proibido in ("remove-", "set-", "new-item", "out-file", "add-content", "stop-", "start-", "restart-", "invoke-"):
            with self.subTest(proibido=proibido):
                self.assertNotIn(proibido, texto)


if __name__ == "__main__":
    unittest.main()
