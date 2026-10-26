"""Testes do caminho de falha de partida.

O caminho feliz de main (abrir a janela) nao e testavel na bancada: nao ha tkinter
aqui. Por isso estes testes cobrem so as partidas que falham antes da janela.
"""
import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from jarvis_pc.__main__ import main
from jarvis_pc.inventario.banco import Banco


class TestFalhaDePartida(unittest.TestCase):
    def _main_com_config(self, texto):
        with tempfile.TemporaryDirectory() as pasta:
            (Path(pasta) / "config.json").write_text(texto, encoding="utf-8")
            codigo = main(["x", pasta])
            arquivo = Path(pasta) / "erro-de-partida.txt"
            conteudo = arquivo.read_text(encoding="utf-8") if arquivo.exists() else None
        return codigo, conteudo

    def test_tecla_invalida_devolve_1_e_grava_o_motivo(self):
        codigo, conteudo = self._main_com_config(json.dumps({"tecla": "F5"}))
        self.assertEqual(codigo, 1)
        self.assertIsNotNone(conteudo)
        self.assertIn("tecla", conteudo)
        self.assertIn("Traceback", conteudo)

    def test_json_quebrado_devolve_1_e_grava_o_motivo(self):
        codigo, conteudo = self._main_com_config("{ quebrado")
        self.assertEqual(codigo, 1)
        self.assertIsNotNone(conteudo)
        self.assertIn("config", conteudo)

    def test_falha_depois_do_registro_grava_erro_e_fim(self):
        # Na bancada nao ha tkinter: com config valida, a partida falha ao abrir a janela.
        with tempfile.TemporaryDirectory() as pasta, mock.patch.dict(sys.modules, {"jarvis_pc.janela": None}):
            self.assertEqual(main(["x", pasta]), 1)
            linhas = (Path(pasta) / "registro.jsonl").read_text(encoding="utf-8").splitlines()
        tipos = [json.loads(l)["tipo"] for l in linhas]
        self.assertEqual(tipos[0], "inicio")
        self.assertIn("erro", tipos)
        self.assertEqual(tipos[-1], "fim")

    def _main_com_janela_falsa(self, config, previa=None):
        from jarvis_pc import __main__ as principal

        with tempfile.TemporaryDirectory() as pasta:
            (Path(pasta) / "config.json").write_text(json.dumps({"raizes": [pasta], **config}), encoding="utf-8")
            if previa:
                b = Banco(Path(pasta) / "inventario.db")
                v = b.iniciar_varredura("arquivos", previa - 5)
                b.encerrar_varredura(v, "ok", 0, previa)
                b.fechar()
            with mock.patch.object(principal, "criar_agente") as criar, mock.patch(
                "jarvis_pc.inventario.atualizador.Atualizador.iniciar"
            ) as iniciar, mock.patch("jarvis_pc.inventario.atualizador.Atualizador.cancelar") as cancelar, mock.patch(
                "jarvis_pc.inventario.banco.Banco.fechar", autospec=True, side_effect=Banco.fechar
            ) as fechar, mock.patch.dict(
                sys.modules, {"jarvis_pc.janela": mock.MagicMock()}
            ):
                criar.return_value.permissoes.erro = None
                codigo = principal.main(["x", pasta])
            kw = criar.call_args.kwargs
            self.assertEqual(kw["max_passos"], 30)
            self.assertEqual(kw["permissoes"].caminho, Path(pasta) / "permissoes.json")
            self.assertEqual(kw["memoria"].caminho, Path(pasta) / "memoria.json")
            self.assertEqual(kw["sessao"].pasta, Path(pasta) / "conversas")
            existe = (Path(pasta) / "inventario.db").exists()
            erro = (Path(pasta) / "erro-de-partida.txt").exists()
        self.fechou = fechar.call_count
        return codigo, existe, erro, criar, iniciar, cancelar

    def test_cria_o_banco_do_inventario_e_nao_atualiza_se_desligado(self):
        codigo, existe, _, criar, iniciar, cancelar = self._main_com_janela_falsa({"atualizar_ao_abrir": False})
        self.assertEqual(codigo, 0)
        self.assertTrue(existe)
        iniciar.assert_not_called()
        self.assertEqual(len(criar.call_args.kwargs["extras"]), 6)
        cancelar.assert_called_once()
        self.assertEqual(self.fechou, 1)

    def test_atualiza_uma_vez_ao_abrir_sem_varredura_previa(self):
        codigo, _, _, _, iniciar, _ = self._main_com_janela_falsa({"atualizar_ao_abrir": True})
        self.assertEqual(codigo, 0)
        iniciar.assert_called_once_with()

    def test_nao_atualiza_se_a_varredura_previa_e_recente(self):
        import time

        _, _, _, _, iniciar, _ = self._main_com_janela_falsa({"atualizar_ao_abrir": True}, previa=time.time() - 60)
        iniciar.assert_not_called()

    def test_atualiza_se_a_varredura_previa_e_antiga(self):
        import time

        _, _, _, _, iniciar, _ = self._main_com_janela_falsa({"atualizar_ao_abrir": True}, previa=time.time() - 90000)
        iniciar.assert_called_once_with()

    def test_falha_ao_iniciar_a_varredura_nao_trava_a_janela(self):
        from jarvis_pc import __main__ as principal

        with tempfile.TemporaryDirectory() as pasta:
            (Path(pasta) / "config.json").write_text(json.dumps({"raizes": [pasta]}), encoding="utf-8")
            janela = mock.MagicMock()
            with mock.patch.object(principal, "criar_agente") as criar, mock.patch(
                "jarvis_pc.inventario.atualizador.Atualizador.iniciar", side_effect=RuntimeError("sem thread")
            ), mock.patch.dict(sys.modules, {"jarvis_pc.janela": mock.MagicMock(Janela=janela)}):
                criar.return_value.permissoes.erro = None
                codigo = principal.main(["x", pasta])
        self.assertEqual(codigo, 0)
        janela.assert_called_once()

    def test_pasta_nao_gravavel_nao_levanta(self):
        self.assertEqual(main(["x", "/proc/nao-existe/jarvis"]), 1)


if __name__ == "__main__":
    unittest.main()
