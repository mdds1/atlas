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

    def _carregar_json(self, **campos):
        import json

        pasta, caminho = com_arquivo(json.dumps(campos))
        with pasta:
            return carregar(caminho)

    def test_tecla_invalida_da_erro(self):
        for tecla in ("", "F5", "@", 5, None, "JJ"):
            with self.subTest(tecla=tecla):
                with self.assertRaisesRegex(ValueError, "tecla"):
                    self._carregar_json(tecla=tecla)

    def test_tecla_vira_maiuscula(self):
        self.assertEqual(self._carregar_json(tecla="j").tecla, "J")
        self.assertEqual(self._carregar_json(tecla="7").tecla, "7")

    def test_tempo_confirmacao_invalido_da_erro(self):
        for valor in ("120", 0, -1, 4000, True, None):
            with self.subTest(valor=valor):
                with self.assertRaisesRegex(ValueError, "tempo_confirmacao"):
                    self._carregar_json(tempo_confirmacao=valor)

    def test_tempo_confirmacao_nos_limites(self):
        self.assertEqual(self._carregar_json(tempo_confirmacao=3600).tempo_confirmacao, 3600)
        self.assertEqual(self._carregar_json(tempo_confirmacao=0.5).tempo_confirmacao, 0.5)

    def test_texto_invalido_da_erro(self):
        for campo in ("modelo", "host", "registro"):
            for valor in ("", 5, None):
                with self.subTest(campo=campo, valor=valor):
                    with self.assertRaisesRegex(ValueError, campo):
                        self._carregar_json(**{campo: valor})

    def test_config_completa_valida_carrega(self):
        c = self._carregar_json(
            modelo="m", host="http://h:1", registro="r.jsonl", tecla="k", tempo_confirmacao=60
        )
        self.assertEqual(
            c, Config(modelo="m", host="http://h:1", registro="r.jsonl", tecla="K", tempo_confirmacao=60)
        )


if __name__ == "__main__":
    unittest.main()
