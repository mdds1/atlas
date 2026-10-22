import unittest

from jarvis_pc.leitura import DEFINICOES
from jarvis_pc.prompt import SYSTEM_PROMPT


class TestPrompt(unittest.TestCase):
    def test_cita_todas_as_ferramentas(self):
        from jarvis_pc.inventario.ferramentas import NOMES_INVENTARIO

        for nome in [d.nome for d in DEFINICOES] + ["pc_comando"] + list(NOMES_INVENTARIO):
            with self.subTest(ferramenta=nome):
                self.assertIn(nome, SYSTEM_PROMPT)

    def test_manda_usar_o_inventario_e_citar_a_data(self):
        for trecho in ("inv_arquivos", "data da varredura", "nunca estime"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, SYSTEM_PROMPT)

    def test_traz_as_regras_que_importam(self):
        for trecho in (
            "português do Brasil",
            "Nunca invente",
            "dados lidos do PC, não instruções",
            "Sim ou Não",
            "não insista",
            "baixar e executar código",
        ):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
