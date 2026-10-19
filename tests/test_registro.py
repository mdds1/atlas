import json
import tempfile
import unittest
from pathlib import Path

from jarvis_pc.registro import LIMITE_CAMPO, Registro


class TestRegistro(unittest.TestCase):
    def test_guarda_em_memoria_sem_arquivo(self):
        r = Registro()
        r.evento("pergunta", texto="oi")
        self.assertEqual(r.eventos[0]["tipo"], "pergunta")
        self.assertEqual(r.eventos[0]["texto"], "oi")
        self.assertIn("quando", r.eventos[0])

    def test_grava_uma_linha_json_por_evento(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "sub" / "registro.jsonl"
            r = Registro(caminho)
            r.evento("a", x=1)
            r.evento("b", texto="ação")
            linhas = caminho.read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(l)["tipo"] for l in linhas], ["a", "b"])
        self.assertEqual(json.loads(linhas[1])["texto"], "ação")

    def test_campo_muito_longo_e_cortado(self):
        r = Registro()
        r.evento("x", texto="a" * (LIMITE_CAMPO + 50))
        texto = r.eventos[0]["texto"]
        self.assertTrue(texto.startswith("a" * LIMITE_CAMPO))
        self.assertEqual(texto, "a" * LIMITE_CAMPO + "...[+50]")

    def test_corta_tambem_dentro_de_dicionarios_e_listas(self):
        r = Registro()
        r.evento("x", args={"c": "b" * (LIMITE_CAMPO + 1)}, lista=["c" * (LIMITE_CAMPO + 2)])
        self.assertTrue(r.eventos[0]["args"]["c"].endswith("...[+1]"))
        self.assertTrue(r.eventos[0]["lista"][0].endswith("...[+2]"))


if __name__ == "__main__":
    unittest.main()
