import json
import tempfile
import unittest
from pathlib import Path

from jarvis_pc.inventario.banco import Banco
from jarvis_pc.inventario.pacotes import coletar_pacotes, ler_dist_info, ler_npm


def fazer_site_packages(raiz, pacotes):
    sp = Path(raiz) / "Lib" / "site-packages"
    sp.mkdir(parents=True)
    for nome in pacotes:
        (sp / nome).mkdir()
    (sp / "requests").mkdir()  # pasta do código, não é dist-info
    return sp


class TestDistInfo(unittest.TestCase):
    def test_le_nome_e_versao_das_pastas_dist_info(self):
        with tempfile.TemporaryDirectory() as t:
            sp = fazer_site_packages(t, ["requests-2.31.0.dist-info", "typing_extensions-4.9.0.dist-info", "x-1.egg-info"])
            self.assertEqual(
                sorted(ler_dist_info(sp)), [("requests", "2.31.0"), ("typing_extensions", "4.9.0")]
            )

    def test_pasta_inexistente_devolve_vazio(self):
        self.assertEqual(ler_dist_info(Path("/nao/existe")), [])

    def test_nome_sem_versao_e_ignorado(self):
        with tempfile.TemporaryDirectory() as t:
            sp = fazer_site_packages(t, ["quebrado.dist-info"])
            self.assertEqual(ler_dist_info(sp), [])


class TestNpm(unittest.TestCase):
    def test_le_modulos_globais_com_escopo(self):
        with tempfile.TemporaryDirectory() as t:
            nm = Path(t)
            (nm / "pm2").mkdir()
            (nm / "pm2" / "package.json").write_text(json.dumps({"version": "5.3.0"}))
            (nm / "@anthropic-ai" / "claude-code").mkdir(parents=True)
            (nm / "@anthropic-ai" / "claude-code" / "package.json").write_text(json.dumps({"version": "1.0.0"}))
            (nm / "sem-json").mkdir()
            self.assertEqual(
                sorted(ler_npm(nm)),
                [("@anthropic-ai/claude-code", "1.0.0"), ("pm2", "5.3.0"), ("sem-json", "")],
            )

    def test_pasta_vazia_ou_inexistente(self):
        self.assertEqual(ler_npm(Path("/nao/existe")), [])


class TestColeta(unittest.TestCase):
    def setUp(self):
        self.banco = Banco()
        self.addCleanup(self.banco.fechar)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name)

    def lista(self):
        return sorted((r["ambiente"], r["nome"], r["versao"]) for r in self.banco.consultar("SELECT * FROM pacotes"))

    def catalogar(self, pasta):
        vid = self.banco.iniciar_varredura("arquivos", 1.0)
        self.banco.gravar("arquivos", vid, [(str(pasta / "pyvenv.cfg"), "pyvenv.cfg", ".cfg", str(pasta), 10, 1.0)])
        self.banco.encerrar_varredura(vid, "ok", 0, 2.0)

    def test_venv_achado_pelo_catalogo(self):
        venv = self.raiz / "meuvenv"
        fazer_site_packages(venv, ["flask-3.0.0.dist-info"])
        self.catalogar(venv)
        n = coletar_pacotes(self.banco, [], "")
        self.assertEqual(n, 1)
        self.assertEqual(self.lista(), [(str(venv), "flask", "3.0.0")])

    def test_python_global_pelo_caminho_de_instalacao(self):
        py = self.raiz / "Python310"
        fazer_site_packages(py, ["pip-23.0.dist-info"])
        coletar_pacotes(self.banco, [str(py) + "\\"], "")
        self.assertEqual(self.lista(), [(str(py), "pip", "23.0")])

    def test_npm_global(self):
        nm = self.raiz / "node_modules"
        (nm / "pm2").mkdir(parents=True)
        (nm / "pm2" / "package.json").write_text(json.dumps({"version": "5.3.0"}))
        coletar_pacotes(self.banco, [], str(nm))
        self.assertEqual(self.lista(), [("npm-global", "pm2", "5.3.0")])

    def test_segunda_coleta_substitui_a_primeira(self):
        py = self.raiz / "P"
        sp = fazer_site_packages(py, ["a-1.dist-info"])
        coletar_pacotes(self.banco, [str(py)], "")
        (sp / "a-1.dist-info").rmdir()
        (sp / "b-2.dist-info").mkdir()
        coletar_pacotes(self.banco, [str(py)], "")
        self.assertEqual([x[1] for x in self.lista()], ["b"])

    def test_registra_varredura_ok(self):
        coletar_pacotes(self.banco, [], "")
        self.assertEqual(self.banco.ultima_varredura("pacotes")["estado"], "ok")

    def test_excecao_na_gravacao_falha_e_preserva_o_inventario_anterior(self):
        py = self.raiz / "P"
        fazer_site_packages(py, ["a-1.dist-info"])
        coletar_pacotes(self.banco, [str(py)], "")
        original = self.banco.gravar

        def quebrado(*a, **k):
            raise RuntimeError("disco")

        self.banco.gravar = quebrado
        try:
            n = coletar_pacotes(self.banco, [str(py)], "")
        finally:
            self.banco.gravar = original
        self.assertEqual(n, 0)
        self.assertEqual(self.banco.em_andamento(), [])
        ultimo = self.banco.consultar("SELECT estado FROM varreduras ORDER BY id DESC LIMIT 1")[0]
        self.assertEqual(ultimo["estado"], "falhou")
        self.assertEqual([x[1] for x in self.lista()], ["a"])

    def test_pasta_ilegivel_nao_derruba_a_coleta(self):
        bom = self.raiz / "Bom"
        fazer_site_packages(bom, ["ok-1.dist-info"])
        nm = self.raiz / "nm"
        (nm / "bom").mkdir(parents=True)
        (nm / "bom" / "package.json").write_text(json.dumps({"version": "1"}))
        (nm / "@esc").mkdir()
        original = Path.iterdir

        def iterdir(self_):
            if self_.name == "@esc":
                raise PermissionError("negado")
            return original(self_)

        Path.iterdir = iterdir
        self.addCleanup(setattr, Path, "iterdir", original)
        coletar_pacotes(self.banco, [str(bom)], str(nm))
        self.assertEqual(sorted(x[1] for x in self.lista()), ["bom", "ok"])
        self.assertEqual(self.banco.ultima_varredura("pacotes")["estado"], "ok")

    def test_nao_segue_links_simbolicos(self):
        alvo = self.raiz / "alvo"
        (alvo / "pm2").mkdir(parents=True)
        (alvo / "pm2" / "package.json").write_text(json.dumps({"version": "9"}))
        nm = self.raiz / "nm"
        nm.mkdir()
        (nm / "ligado").symlink_to(alvo, target_is_directory=True)
        self.assertEqual(ler_npm(nm), [])
        sp = self.raiz / "sp"
        sp.mkdir()
        (sp / "x-1.dist-info").symlink_to(alvo, target_is_directory=True)
        self.assertEqual(ler_dist_info(sp), [])

    def test_package_json_invalido_ou_nao_objeto_da_versao_vazia(self):
        nm = self.raiz / "nm"
        for nome, texto in (("a", "{quebrado"), ("b", "[1]"), ("c", '{"version": 3}')):
            (nm / nome).mkdir(parents=True)
            (nm / nome / "package.json").write_text(texto)
        self.assertEqual(sorted(ler_npm(nm)), [("a", ""), ("b", ""), ("c", "3")])

    def test_nome_com_hifen_usa_o_ultimo_hifen_como_separador(self):
        with tempfile.TemporaryDirectory() as t:
            sp = fazer_site_packages(t, ["my-pkg-1.2.dist-info"])
            self.assertEqual(ler_dist_info(sp), [("my-pkg", "1.2")])

    def test_ambiente_do_venv_nao_duplica_com_python_global_igual(self):
        venv = self.raiz / "v"
        fazer_site_packages(venv, ["flask-3.0.0.dist-info"])
        self.catalogar(venv)
        n = coletar_pacotes(self.banco, [str(venv)], "")
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
