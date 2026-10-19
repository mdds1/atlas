import tempfile
import unittest
from pathlib import Path

from jarvis_pc.config import Config, carregar


def com_arquivo(texto):
    pasta = tempfile.TemporaryDirectory()
    caminho = Path(pasta.name) / "config.json"
    caminho.write_text(texto, encoding="utf-8")
    return pasta, caminho


class TestConfig(unittest.TestCase):
    def test_sem_arquivo_usa_o_padrao(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.assertEqual(carregar(Path(pasta) / "nao-existe.json"), Config())

    def test_sobrescreve_so_o_que_veio(self):
        pasta, caminho = com_arquivo('{"modelo": "outro", "tecla": "K"}')
        with pasta:
            c = carregar(caminho)
        self.assertEqual(c.modelo, "outro")
        self.assertEqual(c.tecla, "K")
        self.assertEqual(c.host, Config().host)

    def test_ignora_chave_desconhecida(self):
        pasta, caminho = com_arquivo('{"modelo": "x", "coisa": 1}')
        with pasta:
            self.assertEqual(carregar(caminho).modelo, "x")

    def test_json_quebrado_da_erro_claro(self):
        pasta, caminho = com_arquivo("{ nao é json")
        with pasta, self.assertRaisesRegex(ValueError, "config inválida"):
            carregar(caminho)

    def test_json_que_nao_e_objeto_da_erro_claro(self):
        pasta, caminho = com_arquivo("[1, 2]")
        with pasta, self.assertRaisesRegex(ValueError, "esperado um objeto"):
            carregar(caminho)

    def test_padrao_pede_confirmacao_com_prazo(self):
        self.assertGreater(Config().tempo_confirmacao, 0)


if __name__ == "__main__":
    unittest.main()
