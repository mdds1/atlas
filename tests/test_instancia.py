import json
import tempfile
import unittest
from pathlib import Path

from jarvis_pc.instancia import travar


class TestInstanciaUnica(unittest.TestCase):
    def test_segunda_trava_na_mesma_pasta_falha_e_liberar_permite(self):
        with tempfile.TemporaryDirectory() as pasta:
            primeira = travar(pasta)
            self.assertIsNotNone(primeira)
            self.assertIsNone(travar(pasta))
            primeira.liberar()
            outra = travar(pasta)
            self.assertIsNotNone(outra)
            outra.liberar()

    def test_main_com_instancia_ja_aberta_sai_sem_janela_e_registra(self):
        from jarvis_pc.__main__ import main

        with tempfile.TemporaryDirectory() as pasta:
            (Path(pasta) / "config.json").write_text(json.dumps({}), encoding="utf-8")
            primeira = travar(pasta)
            try:
                codigo = main(["x", pasta])
            finally:
                primeira.liberar()
            self.assertEqual(codigo, 0)
            registros = "".join(p.read_text(encoding="utf-8") for p in Path(pasta).glob("*.jsonl")) + "".join(
                p.read_text(encoding="utf-8") for p in Path(pasta).glob("*.log"))
            self.assertIn("ja_aberta", registros)
