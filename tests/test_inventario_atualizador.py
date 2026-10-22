import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from jarvis_pc.inventario import atualizador as modulo
from jarvis_pc.inventario.atualizador import Atualizador
from jarvis_pc.inventario.banco import Banco
from jarvis_pc.inventario.exclusoes import Exclusoes

from tests.ajuda import ExecutorFalso, fixture


class TestAtualizador(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        (Path(self._tmp.name) / "a.txt").write_text("x")
        self.banco = Banco()
        self.addCleanup(self.banco.fechar)
        self.ex = ExecutorFalso(saida=json.dumps(fixture("inventario_sistema")))

    def montar(self, **kw):
        return Atualizador(self.banco, [self._tmp.name], Exclusoes(), executor=self.ex, **kw)

    def estados(self, tipo):
        return [r["estado"] for r in self.banco.consultar("SELECT estado FROM varreduras WHERE tipo = ? ORDER BY id", (tipo,))]

    def test_roda_as_tres_coletas_na_ordem(self):
        a = self.montar(sincrono=True)
        self.assertTrue(a.iniciar())
        for tipo in ("arquivos", "sistema", "pacotes"):
            with self.subTest(tipo=tipo):
                self.assertEqual(self.banco.ultima_varredura(tipo)["estado"], "ok")
        tipos = [r["tipo"] for r in self.banco.consultar("SELECT tipo FROM varreduras ORDER BY id")]
        self.assertEqual(tipos, ["arquivos", "sistema", "pacotes"])
        self.assertFalse(a.rodando())
        self.assertEqual(a.ultimo_erro, "")
        self.assertEqual(self.banco.em_andamento(), [])

    def test_nao_inicia_duas_vezes_ao_mesmo_tempo(self):
        a = self.montar(sincrono=True)
        a._ativa = True
        self.assertFalse(a.iniciar())
        self.assertEqual(self.banco.consultar("SELECT id FROM varreduras"), [])

    def test_em_thread_termina_e_libera(self):
        a = self.montar()
        self.assertTrue(a.iniciar())
        for _ in range(100):
            if not a.rodando():
                break
            time.sleep(0.05)
        self.assertFalse(a.rodando())
        self.assertIsNotNone(self.banco.ultima_varredura("pacotes"))

    def test_excecao_do_executor_fica_registrada_e_nao_derruba(self):
        class Quebra:
            def __call__(self, *a, **k):
                raise RuntimeError("boom")

        a = Atualizador(self.banco, [self._tmp.name], Exclusoes(), executor=Quebra(), sincrono=True)
        a.iniciar()
        self.assertIn("RuntimeError", a.ultimo_erro)
        self.assertFalse(a.rodando())
        self.assertEqual(self.banco.ultima_varredura("arquivos")["estado"], "ok")
        self.assertEqual(self.estados("sistema"), ["falhou"])
        self.assertEqual(self.estados("pacotes"), [])
        self.assertEqual(self.banco.em_andamento(), [])

    def test_falha_do_powershell_vira_erro_legivel(self):
        self.ex = ExecutorFalso(saida="", codigo=1, erro="negado")
        a = self.montar(sincrono=True)
        a.iniciar()
        self.assertIn("negado", a.ultimo_erro)
        self.assertEqual(self.banco.em_andamento(), [])

    def test_falha_em_pacotes_registra_a_causa_e_libera(self):
        def quebra(*a, **k):
            raise OSError("disco")

        a = self.montar(sincrono=True)
        with mock.patch.object(modulo, "coletar_pacotes", quebra):
            a.iniciar()
        self.assertEqual(a.ultimo_erro, "OSError: disco")
        self.assertFalse(a.rodando())
        self.assertEqual(self.banco.em_andamento(), [])

    def test_pacotes_recebe_pythons_e_npm_da_coleta_de_sistema(self):
        vistos = []

        def espia(banco, pythons, npm, agora=None):
            vistos.append((pythons, npm))

        a = self.montar(sincrono=True)
        with mock.patch.object(modulo, "coletar_pacotes", espia):
            a.iniciar()
        self.assertEqual(
            vistos,
            [(["C:\\Users\\Diniz\\AppData\\Local\\Programs\\Python\\Python310\\"], "C:\\Users\\Diniz\\AppData\\Roaming\\npm\\node_modules")],
        )

    def test_sistema_falho_nao_roda_pacotes_e_preserva_os_anteriores(self):
        self.montar(sincrono=True).iniciar()
        antes = self.banco.consultar("SELECT * FROM pacotes")
        id_antes = self.banco.ultima_varredura("pacotes")["id"]
        self.ex = ExecutorFalso(saida="", codigo=1, erro="negado")
        a = self.montar(sincrono=True)
        a.iniciar()
        self.assertIn("negado", a.ultimo_erro)
        self.assertEqual(self.estados("pacotes"), ["ok"])
        self.assertEqual(self.banco.ultima_varredura("pacotes")["id"], id_antes)
        self.assertEqual(self.banco.consultar("SELECT * FROM pacotes"), antes)

    def test_falha_ao_criar_a_thread_libera_e_relanca(self):
        a = self.montar()
        with mock.patch.object(modulo.threading, "Thread", side_effect=RuntimeError("sem threads")):
            with self.assertRaises(RuntimeError):
                a.iniciar()
        self.assertFalse(a.rodando())
        self.assertTrue(self.montar(sincrono=True).iniciar())

    def test_iniciar_recupera_varredura_orfa(self):
        self.banco.iniciar_varredura("pacotes", 1.0)
        a = self.montar(sincrono=True)
        vistos = []
        with mock.patch.object(modulo, "varrer_arquivos", side_effect=lambda *x, **k: vistos.append(self.banco.em_andamento())):
            a.iniciar()
        self.assertEqual(vistos, [[]])
        self.assertEqual(self.estados("pacotes")[0], "falhou")

    def test_falha_ao_encerrar_pendentes_vai_para_ultimo_erro(self):
        a = self.montar(sincrono=True)
        with mock.patch.object(self.banco, "em_andamento", side_effect=OSError("banco")):
            a.iniciar()
        self.assertIn("OSError", a.ultimo_erro)
        self.assertFalse(a.rodando())

    def test_nenhuma_varredura_fica_rodando_se_algo_escapa(self):
        def vaza(banco, pythons, npm, agora=None):
            banco.iniciar_varredura("pacotes", 1.0)
            raise RuntimeError("vazou")

        a = self.montar(sincrono=True)
        with mock.patch.object(modulo, "coletar_pacotes", vaza):
            a.iniciar()
        self.assertEqual(self.banco.em_andamento(), [])
        self.assertEqual(self.estados("pacotes"), ["falhou"])

    def test_cancelar_durante_a_rodada_interrompe_a_varredura_de_arquivos(self):
        chamado = []

        def relogio():
            if not chamado:
                chamado.append(1)
                a.cancelar()
            return 1.0

        a = self.montar(sincrono=True, agora=relogio)
        a.iniciar()
        self.assertIsNone(self.banco.ultima_varredura("arquivos"))
        self.assertEqual(self.estados("arquivos"), ["cancelada"])

    def test_cancelar_fora_de_rodada_nao_afeta_a_proxima(self):
        a = self.montar(sincrono=True)
        a.cancelar()
        a.iniciar()
        self.assertEqual(self.estados("arquivos"), ["ok"])

    def test_cancelamento_pendente_nao_vaza_se_a_varredura_levanta(self):
        a = self.montar(sincrono=True)
        a.cancelar()
        with mock.patch.object(modulo, "varrer_arquivos", side_effect=OSError("x")):
            a.iniciar()
        a.iniciar()
        self.assertEqual(self.estados("arquivos"), ["ok"])

    def test_ultimo_erro_e_zerado_a_cada_rodada(self):
        self.ex = ExecutorFalso(saida="", codigo=1, erro="negado")
        a = self.montar(sincrono=True)
        a.iniciar()
        self.assertIn("negado", a.ultimo_erro)
        self.ex = ExecutorFalso(saida=json.dumps(fixture("inventario_sistema")))
        a._executor = self.ex
        a.iniciar()
        self.assertEqual(a.ultimo_erro, "")


if __name__ == "__main__":
    unittest.main()
