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

    def test_pasta_nao_gravavel_nao_levanta(self):
        self.assertEqual(main(["x", "/proc/nao-existe/jarvis"]), 1)


if __name__ == "__main__":
    unittest.main()
