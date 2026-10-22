import sqlite3
import unittest

from jarvis_pc.inventario.atualizador import Atualizador
from jarvis_pc.inventario.banco import Banco
from jarvis_pc.inventario.ferramentas import NOMES_INVENTARIO, criar_ferramentas_inventario
from jarvis_pc.leitura import AVISO

AGORA = 1_800_000_000.0


def banco_pronto():
    b = Banco()
    v = b.iniciar_varredura("arquivos", AGORA - 10)
    b.gravar("arquivos", v, [("C:\\a\\instalar.ps1", "instalar.ps1", ".ps1", "C:\\a", 3000, 1.0), ("C:\\a\\grande.iso", "grande.iso", ".iso", "C:\\a", 900 * 1024 * 1024, 1.0)])
    b.encerrar_varredura(v, "ok", 0, AGORA)
    s = b.iniciar_varredura("sistema", AGORA - 10)
    b.gravar("apps", s, [{"origem": "registro", "nome": "Git", "versao": "2.43", "editor": "G", "local": ""}])
    b.gravar("servicos", s, [{"nome": "Spooler", "exibicao": "Spooler", "estado": "Running", "inicio": "Auto"}])
    b.encerrar_varredura(s, "ok", 0, AGORA)
    p = b.iniciar_varredura("pacotes", AGORA - 10)
    b.gravar("pacotes", p, [("C:\\Jarvis\\venv", "openjarvis", "1.0.5")])
    b.encerrar_varredura(p, "ok", 0, AGORA)
    return b


class Falso:
    def __init__(self, inicia=True, roda=False):
        self.inicia, self.roda, self.chamou = inicia, roda, 0
        self.ultimo_erro = ""

    def iniciar(self):
        self.chamou += 1
        return self.inicia

    def rodando(self):
        return self.roda


class TestFerramentas(unittest.TestCase):
    def setUp(self):
        self.atual = Falso()
        self.banco = banco_pronto()
        self.addCleanup(self.banco.fechar)
        self.por_nome = {f.spec.name: f for f in criar_ferramentas_inventario(self.banco, self.atual)}

    def test_sao_exatamente_as_seis(self):
        self.assertEqual(set(self.por_nome), set(NOMES_INVENTARIO))
        self.assertEqual(len(NOMES_INVENTARIO), 6)

    def test_nenhuma_pede_confirmacao_e_todas_tem_descricao(self):
        for nome, f in self.por_nome.items():
            with self.subTest(nome=nome):
                self.assertFalse(f.spec.requires_confirmation)
                self.assertGreater(len(f.spec.description), 20)

    def test_resposta_comeca_com_o_aviso(self):
        r = self.por_nome["inv_status"].execute()
        self.assertTrue(r.success)
        self.assertTrue(r.content.startswith(AVISO))

    def test_arquivos_buscar(self):
        r = self.por_nome["inv_arquivos"].execute(operacao="buscar", nome="instalar")
        self.assertIn("C:\\a\\instalar.ps1", r.content)

    def test_arquivos_maiores(self):
        r = self.por_nome["inv_arquivos"].execute(operacao="maiores", limite=1)
        self.assertIn("grande.iso", r.content)
        self.assertNotIn("instalar.ps1", r.content)

    def test_arquivos_pastas_exige_pasta(self):
        r = self.por_nome["inv_arquivos"].execute(operacao="pastas")
        self.assertFalse(r.success)
        self.assertIn("pasta", r.content)

    def test_arquivos_operacao_invalida(self):
        r = self.por_nome["inv_arquivos"].execute(operacao="apagar")
        self.assertFalse(r.success)
        self.assertIn("buscar", r.content)

    def test_limite_como_texto_funciona(self):
        r = self.por_nome["inv_arquivos"].execute(operacao="maiores", limite="1")
        self.assertTrue(r.success)

    def test_apps_dependencias_e_sistema(self):
        self.assertIn("Git 2.43", self.por_nome["inv_apps"].execute(nome="git").content)
        self.assertIn("openjarvis 1.0.5", self.por_nome["inv_dependencias"].execute(nome="openjarvis").content)
        self.assertIn("Spooler", self.por_nome["inv_sistema"].execute(tipo="servicos").content)

    def test_sistema_sem_tipo_falha_com_explicacao(self):
        r = self.por_nome["inv_sistema"].execute()
        self.assertFalse(r.success)

    def test_parametro_desconhecido_nao_quebra(self):
        r = self.por_nome["inv_apps"].execute(nome="git", inventado=1)
        self.assertTrue(r.success)

    def test_atualizar_inicia_e_avisa(self):
        r = self.por_nome["inv_atualizar"].execute()
        self.assertEqual(self.atual.chamou, 1)
        self.assertIn("iniciada", r.content)

    def test_atualizar_quando_ja_esta_rodando(self):
        self.por_nome["inv_atualizar"]._ctx.atualizador.inicia = False
        r = self.por_nome["inv_atualizar"].execute()
        self.assertIn("já está em andamento", r.content)

    def test_erro_do_banco_vira_falha_limpa(self):
        b = banco_pronto()
        b.fechar()
        f = {x.spec.name: x for x in criar_ferramentas_inventario(b, self.atual)}["inv_apps"]
        r = f.execute(nome="git")
        self.assertFalse(r.success)
        self.assertIn("Falha ao consultar o inventário", r.content)
        self.assertNotIn("Traceback", r.content)
        self.assertTrue(issubclass(sqlite3.ProgrammingError, sqlite3.Error))

    def test_so_leitura_nenhuma_ferramenta_tem_parametro_de_sql_ou_escrita(self):
        for nome, f in self.por_nome.items():
            props = set(f.spec.parameters.get("properties", {}))
            with self.subTest(nome=nome):
                self.assertFalse(props & {"sql", "consulta_sql", "comando", "script", "apagar", "gravar"})


class TestMontagem(unittest.TestCase):
    def test_montar_inventario_cria_banco_e_atualizador(self):
        import tempfile
        from pathlib import Path

        from jarvis_pc.config import Config
        from jarvis_pc.inventario.ferramentas import montar_inventario

        with tempfile.TemporaryDirectory() as pasta:
            ferramentas, atualizador, banco = montar_inventario(pasta, Config(raizes=(pasta,)))
            self.assertEqual({f.spec.name for f in ferramentas}, set(NOMES_INVENTARIO))
            self.assertIsInstance(atualizador, Atualizador)
            self.assertTrue((Path(pasta) / "inventario.db").exists())
            banco.fechar()


if __name__ == "__main__":
    unittest.main()
