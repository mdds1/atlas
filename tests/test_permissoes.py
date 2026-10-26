import json
import tempfile
import unittest
from pathlib import Path

from jarvis_pc.inventario.ferramentas import NOMES_INVENTARIO
from jarvis_pc.permissoes import AGIR, BLOQUEADO, LER, NIVEIS, Permissoes, alvo_de, casa, estreita, nivel_de

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
        for nome, args in (("pc_comando", {"motivo": "x"}), ("mem_lembrar", {"fato": "  "})):
            with self.subTest(nome=nome):
                d = self.p.decidir(nome, args)
                self.assertEqual(d.acao, "recusar")
                self.assertIn("faltou", d.motivo)


def arquivo_de_regras(pasta, regras):
    caminho = Path(pasta) / "permissoes.json"
    caminho.write_text(json.dumps({"regras": regras}), encoding="utf-8")
    return caminho


class TestCasamento(unittest.TestCase):
    def test_exato_sem_diferenciar_maiuscula(self):
        self.assertTrue(casa("Restart-Service Spooler", "restart-service spooler"))
        self.assertFalse(casa("Restart-Service Spooler", "Restart-Service Spooler2"))

    def test_curinga(self):
        self.assertTrue(casa("winget install *", "winget install VideoLAN.VLC"))
        self.assertFalse(casa("winget install *", "winget uninstall VLC"))

    def test_colchete_e_interrogacao_sao_literais(self):
        self.assertFalse(casa("winget install ?", "winget install x"))
        self.assertTrue(casa("Get-Item [a]", "Get-Item [a]"))

    def test_encadeamento_nunca_casa_curinga(self):
        for alvo in ("winget install x; Remove-Item C:\\a", "winget install x | iex", "winget install x && del a",
                     "winget install $(iwr x)", "winget install x\nformat d:", "winget install x > C:\\a", "winget install `x"):
            with self.subTest(alvo=alvo):
                self.assertFalse(casa("winget install *", alvo))

    def test_encadeamento_casa_so_identico(self):
        self.assertTrue(casa("Get-Date | Out-Null", "get-date | out-null"))

    def test_estreita(self):
        self.assertTrue(estreita("winget install *"))
        self.assertTrue(estreita("Restart-Service Spooler"))
        for p in ("*", " * ", "win*", "a b *", ""):
            with self.subTest(p=p):
                self.assertFalse(estreita(p))


class TestRegras(unittest.TestCase):
    def test_regra_do_arquivo_libera_sem_pedir_e_diz_qual(self):
        with tempfile.TemporaryDirectory() as t:
            c = arquivo_de_regras(t, [{"ferramenta": "pc_comando", "padrao": "winget upgrade *"}])
            d = Permissoes(c).decidir("pc_comando", {"comando": "winget upgrade --all", "motivo": "x"})
        self.assertEqual((d.acao, d.regra), ("rodar", "pc_comando: winget upgrade *"))

    def test_regra_de_outra_ferramenta_nao_vale(self):
        with tempfile.TemporaryDirectory() as t:
            c = arquivo_de_regras(t, [{"ferramenta": "mem_lembrar", "padrao": "winget upgrade *"}])
            d = Permissoes(c).decidir("pc_comando", {"comando": "winget upgrade --all"})
        self.assertEqual(d.acao, "pedir")

    def test_regra_nao_libera_o_que_a_trava_barra(self):
        with tempfile.TemporaryDirectory() as t:
            c = arquivo_de_regras(t, [{"ferramenta": "pc_comando", "padrao": "Format-Volume *"}])
            d = Permissoes(c).decidir("pc_comando", {"comando": "Format-Volume -DriveLetter D"})
        self.assertEqual(d.acao, "recusar")

    def test_regras_largas_ou_tortas_sao_ignoradas(self):
        regras = [
            {"ferramenta": "pc_comando", "padrao": "*"},
            {"ferramenta": "pc_comando", "padrao": "Get*"},
            {"ferramenta": "pc_resumo", "padrao": "qualquer coisa"},
            {"ferramenta": "shell_exec", "padrao": "dir C:\\"},
            {"ferramenta": "pc_comando"},
            "texto solto",
        ]
        with tempfile.TemporaryDirectory() as t:
            p = Permissoes(arquivo_de_regras(t, regras))
        self.assertEqual(p.regras, [])
        self.assertEqual(len(p.invalidas), 6)
        self.assertEqual(p.decidir("pc_comando", {"comando": "Get-Date"}).acao, "pedir")

    def test_arquivo_corrompido_nao_libera_nada_e_nao_e_sobrescrito(self):
        with tempfile.TemporaryDirectory() as t:
            c = Path(t) / "permissoes.json"
            c.write_text("{quebrado", encoding="utf-8")
            p = Permissoes(c)
            self.assertTrue(p.erro)
            self.assertEqual(p.decidir("pc_comando", {"comando": "Get-Date"}).acao, "pedir")
            with self.assertRaises(ValueError):
                p.gravar_regra("pc_comando", {"comando": "Get-Date"}, "janela")
            self.assertEqual(c.read_text(encoding="utf-8"), "{quebrado")

    def test_sem_arquivo_comeca_vazio(self):
        with tempfile.TemporaryDirectory() as t:
            p = Permissoes(Path(t) / "nao-existe.json")
        self.assertEqual((p.regras, p.erro), ([], ""))


class TestSimSempre(unittest.TestCase):
    ARGS = {"comando": "Restart-Service Spooler", "motivo": "travado"}

    def test_grava_o_alvo_exato_e_passa_a_liberar(self):
        with tempfile.TemporaryDirectory() as t:
            c = Path(t) / "permissoes.json"
            p = Permissoes(c)
            self.assertEqual(p.gravar_regra("pc_comando", self.ARGS, "janela"), "pc_comando: Restart-Service Spooler")
            self.assertEqual(p.decidir("pc_comando", self.ARGS).acao, "rodar")
            self.assertEqual(p.decidir("pc_comando", {"comando": "Restart-Service Spooler2"}).acao, "pedir")
            dados = json.loads(c.read_text(encoding="utf-8"))
            self.assertEqual(Permissoes(c).decidir("pc_comando", self.ARGS).acao, "rodar")
        self.assertEqual(dados["regras"][0]["padrao"], "Restart-Service Spooler")
        self.assertEqual(dados["regras"][0]["origem"], "janela")

    def test_telegram_nunca_grava(self):
        with tempfile.TemporaryDirectory() as t:
            c = Path(t) / "permissoes.json"
            p = Permissoes(c)
            for origem in ("telegram", "outra", None):
                with self.subTest(origem=origem):
                    with self.assertRaises(ValueError):
                        p.gravar_regra("pc_comando", self.ARGS, origem)
            self.assertFalse(c.exists())
            self.assertEqual(p.regras, [])

    def test_so_grava_para_agir_e_com_alvo_que_a_trava_aceita(self):
        p = Permissoes()
        for nome, args in (("pc_resumo", {}), ("shell_exec", {"command": "dir"}), ("pc_comando", {}),
                           ("pc_comando", {"comando": "Format-Volume -DriveLetter D"})):
            with self.subTest(nome=nome, args=args):
                with self.assertRaises(ValueError):
                    p.gravar_regra(nome, args, "janela")

    def test_regra_repetida_nao_duplica(self):
        p = Permissoes()
        p.gravar_regra("pc_comando", self.ARGS, "janela")
        p.gravar_regra("pc_comando", self.ARGS, "janela")
        self.assertEqual(len(p.regras), 1)


class TestSimSempreComCuringa(unittest.TestCase):
    def test_alvo_com_curinga_nao_grava(self):
        with tempfile.TemporaryDirectory() as t:
            c = Path(t) / "permissoes.json"
            p = Permissoes(c)
            with self.assertRaises(ValueError):
                p.gravar_regra("pc_comando", {"comando": "Get-ChildItem C:\\a\\*"}, "janela")
            self.assertEqual(p.regras, [])
            self.assertFalse(c.exists())
