import unittest

from jarvis_pc.inventario.ferramentas import NOMES_INVENTARIO
from jarvis_pc.permissoes import AGIR, BLOQUEADO, LER, NIVEIS, Permissoes, alvo_de, nivel_de

LEITURA = ("pc_resumo", "pc_processos", "pc_inicializacao", "pc_eventos", "pc_servicos", "pc_drivers", "pc_gpu", "pc_atualizacoes")


class TestNiveis(unittest.TestCase):
    def test_leitura_e_inventario_sao_ler(self):
        for nome in LEITURA + NOMES_INVENTARIO:
            with self.subTest(nome=nome):
                self.assertEqual(nivel_de(nome), LER)

    def test_comando_e_memoria_sao_agir(self):
        for nome in ("pc_comando", "mem_lembrar", "mem_esquecer"):
            with self.subTest(nome=nome):
                self.assertEqual(nivel_de(nome), AGIR)

    def test_desconhecida_e_bloqueada(self):
        for nome in ("shell_exec", "", "PC_RESUMO", None):
            with self.subTest(nome=nome):
                self.assertEqual(nivel_de(nome), BLOQUEADO)

    def test_niveis_so_tem_valores_conhecidos(self):
        self.assertEqual(set(NIVEIS.values()), {LER, AGIR})

    def test_alvo(self):
        self.assertEqual(alvo_de("pc_comando", {"comando": " Get-Date ", "motivo": "x"}), "Get-Date")
        self.assertEqual(alvo_de("mem_lembrar", {"fato": "o time é o Avaí"}), "o time é o Avaí")
        self.assertEqual(alvo_de("pc_comando", {"comando": 5}), "")
        self.assertEqual(alvo_de("pc_comando", "nao e dict"), "")


class TestDecidirSemRegras(unittest.TestCase):
    def setUp(self):
        self.p = Permissoes()

    def test_ler_roda(self):
        d = self.p.decidir("pc_resumo", {})
        self.assertEqual((d.acao, d.nivel), ("rodar", LER))

    def test_agir_pede(self):
        d = self.p.decidir("pc_comando", {"comando": "Restart-Service Spooler", "motivo": "x"})
        self.assertEqual((d.acao, d.nivel, d.regra), ("pedir", AGIR, ""))

    def test_desconhecida_recusa(self):
        d = self.p.decidir("shell_exec", {"command": "dir"})
        self.assertEqual((d.acao, d.nivel), ("recusar", BLOQUEADO))
        self.assertIn("não existe", d.motivo)

    def test_trava_continua_por_baixo(self):
        for comando in ("Format-Volume -DriveLetter D", "format d:", "Remove-Item C:\\Jogos -Recurse"):
            with self.subTest(comando=comando):
                d = self.p.decidir("pc_comando", {"comando": comando, "motivo": "x"})
                self.assertEqual((d.acao, d.nivel), ("recusar", BLOQUEADO))
                self.assertTrue(d.motivo)

    def test_agir_sem_alvo_e_recusado(self):
        d = self.p.decidir("pc_comando", {"motivo": "x"})
        self.assertEqual(d.acao, "recusar")
