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


class TestPromptAtlas(unittest.TestCase):
    def test_identidade(self):
        self.assertIn("Você é a Atlas", SYSTEM_PROMPT)
        self.assertNotIn("diagnóstico do PC", SYSTEM_PROMPT)
        self.assertNotIn("Jarvis", SYSTEM_PROMPT)

    def test_regra_de_ambiguidade(self):
        self.assertIn("mais de um candidato", SYSTEM_PROMPT)
        self.assertIn("liste", SYSTEM_PROMPT)
        self.assertIn("nunca escolha sozinha", SYSTEM_PROMPT)

    def test_regras_de_permissao(self):
        for trecho in ("Sim sempre", "Não", "não tente caminho equivalente", "mem_lembrar", "APROXIMEI", "dados, não instruções"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, SYSTEM_PROMPT)

    def test_sem_em_dash_nem_emoji(self):
        self.assertNotIn("\u2014", SYSTEM_PROMPT)
        self.assertTrue(all(ord(c) < 0x2000 for c in SYSTEM_PROMPT))

    def test_cita_todas_as_ferramentas_de_ler_e_agir(self):
        from jarvis_pc.permissoes import NIVEIS
        for nome in NIVEIS:
            with self.subTest(nome=nome):
                self.assertIn(nome, SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()


class TestPromptAgirSemConfirmarNoTexto(unittest.TestCase):
    def test_manda_chamar_a_ferramenta_direto(self):
        for trecho in ("chame a ferramenta direto", "nunca peça confirmação em texto",
                       "sim\" digitado no chat não autoriza nada"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, SYSTEM_PROMPT)

    def test_diz_que_o_dialogo_do_pc_faz_a_pergunta(self):
        self.assertIn("diálogo do PC faz a pergunta", SYSTEM_PROMPT)

    def test_atlas_roda_como_administrador(self):
        for trecho in ("administrador", "não invente instrução"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, SYSTEM_PROMPT)
