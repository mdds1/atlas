import json
import tempfile
import unittest
from pathlib import Path

from jarvis_pc.sessao import Sessao


class TestSessao(unittest.TestCase):
    def test_grava_um_arquivo_por_sessao(self):
        with tempfile.TemporaryDirectory() as t:
            s = Sessao(t, ident="2026-10-22-100000")
            s.acrescentar("usuario", "oi", "janela")
            s.acrescentar("atlas", "olá", "janela")
            dados = json.loads((Path(t) / "2026-10-22-100000.json").read_text(encoding="utf-8"))
        self.assertEqual([(m["papel"], m["texto"], m["origem"]) for m in dados["mensagens"]],
                         [("usuario", "oi", "janela"), ("atlas", "olá", "janela")])

    def test_ultima_retoma_a_mais_recente(self):
        with tempfile.TemporaryDirectory() as t:
            Sessao(t, ident="2026-10-21-090000").acrescentar("usuario", "velha", "janela")
            Sessao(t, ident="2026-10-22-090000").acrescentar("usuario", "nova", "telegram")
            s = Sessao.ultima(t)
        self.assertEqual(s.ident, "2026-10-22-090000")
        self.assertEqual(s.historico(), [("usuario", "nova")])

    def test_ultima_pula_arquivo_corrompido(self):
        with tempfile.TemporaryDirectory() as t:
            Sessao(t, ident="2026-10-21-090000").acrescentar("usuario", "boa", "janela")
            (Path(t) / "2026-10-22-090000.json").write_text("{quebrado", encoding="utf-8")
            self.assertEqual(Sessao.ultima(t).historico(), [("usuario", "boa")])

    def test_ultima_sem_nada_e_nova(self):
        with tempfile.TemporaryDirectory() as t:
            s = Sessao.ultima(Path(t) / "nao-existe")
        self.assertEqual(s.mensagens, [])

    def test_historico_corta_nas_ultimas(self):
        s = Sessao()
        for i in range(30):
            s.acrescentar("usuario", f"m{i}", "janela")
        h = s.historico(limite=4)
        self.assertEqual([t for _, t in h], ["m26", "m27", "m28", "m29"])

    def test_papel_e_origem_invalidos(self):
        s = Sessao()
        with self.assertRaises(ValueError):
            s.acrescentar("tool", "x", "janela")
        with self.assertRaises(ValueError):
            s.acrescentar("usuario", "x", "email")

    def test_sem_pasta_fica_so_na_memoria(self):
        s = Sessao()
        s.acrescentar("usuario", "oi", "janela")
        self.assertEqual(s.historico(), [("usuario", "oi")])
