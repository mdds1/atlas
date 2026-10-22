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
                sorted(ler_dist_info(sp)[0]), [("requests", "2.31.0"), ("typing_extensions", "4.9.0")]
            )

    def test_pasta_inexistente_devolve_vazio(self):
        self.assertEqual(ler_dist_info(Path("/nao/existe")), ([], 1))

    def test_nome_sem_versao_e_ignorado(self):
        with tempfile.TemporaryDirectory() as t:
            sp = fazer_site_packages(t, ["quebrado.dist-info"])
            self.assertEqual(ler_dist_info(sp), ([], 0))


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
                sorted(ler_npm(nm)[0]),
                [("@anthropic-ai/claude-code", "1.0.0"), ("pm2", "5.3.0"), ("sem-json", "")],
            )

    def test_pasta_vazia_ou_inexistente(self):
        self.assertEqual(ler_npm(Path("/nao/existe")), ([], 1))


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
            with self.assertRaises(RuntimeError):
                coletar_pacotes(self.banco, [str(py)], "")
        finally:
            self.banco.gravar = original
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

    def test_le_package_json_atras_de_link_simbolico(self):
        alvo = self.raiz / "alvo"
        (alvo / "pm2").mkdir(parents=True)
        (alvo / "pm2" / "package.json").write_text(json.dumps({"version": "9"}))
        nm = self.raiz / "nm"
        nm.mkdir()
        try:
            (nm / "ligado").symlink_to(alvo / "pm2", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("sistema nao permite criar link simbolico")
        self.assertEqual(ler_npm(nm)[0], [("ligado", "9")])

    def test_package_json_invalido_ou_nao_objeto_da_versao_vazia(self):
        nm = self.raiz / "nm"
        for nome, texto in (("a", "{quebrado"), ("b", "[1]"), ("c", '{"version": 3}')):
            (nm / nome).mkdir(parents=True)
            (nm / nome / "package.json").write_text(texto)
        self.assertEqual(sorted(ler_npm(nm)[0]), [("a", ""), ("b", ""), ("c", "3")])

    def test_nome_com_hifen_usa_o_ultimo_hifen_como_separador(self):
        with tempfile.TemporaryDirectory() as t:
            sp = fazer_site_packages(t, ["my-pkg-1.2.dist-info"])
            self.assertEqual(ler_dist_info(sp)[0], [("my-pkg", "1.2")])

    def test_ambiente_do_venv_nao_duplica_com_python_global_igual(self):
        venv = self.raiz / "v"
        fazer_site_packages(venv, ["flask-3.0.0.dist-info"])
        self.catalogar(venv)
        n = coletar_pacotes(self.banco, [str(venv)], "")
        self.assertEqual(n, 1)

    def test_erros_de_pasta_ilegivel_e_site_packages_ausente_sao_contados(self):
        sem_site = self.raiz / "SemSite"
        sem_site.mkdir()
        bom = self.raiz / "Bom"
        fazer_site_packages(bom, ["ok-1.dist-info"])
        nm = self.raiz / "nm"
        (nm / "@esc").mkdir(parents=True)
        original = Path.iterdir

        def iterdir(self_):
            if self_.name == "@esc":
                raise PermissionError("negado")
            return original(self_)

        Path.iterdir = iterdir
        self.addCleanup(setattr, Path, "iterdir", original)
        n = coletar_pacotes(self.banco, [str(sem_site), str(bom)], str(nm))
        self.assertEqual(n, 1)
        ultima = self.banco.ultima_varredura("pacotes")
        self.assertEqual((ultima["estado"], ultima["erros"]), ("ok", 2))

    def test_caminhos_equivalentes_viram_um_ambiente(self):
        vid = self.banco.iniciar_varredura("arquivos", 1.0)
        self.banco.gravar("arquivos", vid, [("C:\\Py\\venv\\pyvenv.cfg", "pyvenv.cfg", ".cfg", "C:\\Py\\venv", 1, 1.0)])
        self.banco.encerrar_varredura(vid, "ok", 0, 2.0)
        import jarvis_pc.inventario.pacotes as m

        visto = []
        original = m.ler_dist_info
        m.ler_dist_info = lambda site: (visto.append(str(site)) or [("a", "1")], 0)
        self.addCleanup(setattr, m, "ler_dist_info", original)
        n = coletar_pacotes(self.banco, ["c:/py/venv/"], "")
        self.assertEqual(n, 1)
        self.assertEqual(len(visto), 1)
        self.assertEqual([r["ambiente"] for r in self.banco.consultar("SELECT ambiente FROM pacotes")], ["C:\\Py\\venv"])

    def test_insert_que_falha_de_verdade_preserva_pacotes_antigos(self):
        py = self.raiz / "P"
        fazer_site_packages(py, ["a-1.dist-info"])
        coletar_pacotes(self.banco, [str(py)], "")
        import jarvis_pc.inventario.pacotes as m

        original = m.ler_dist_info
        m.ler_dist_info = lambda site: ([("so-nome",)], 0)
        self.addCleanup(setattr, m, "ler_dist_info", original)
        with self.assertRaises(Exception):
            coletar_pacotes(self.banco, [str(py)], "")
        self.assertEqual([x[1] for x in self.lista()], ["a"])
        ultimo = self.banco.consultar("SELECT estado FROM varreduras ORDER BY id DESC LIMIT 1")[0]
        self.assertEqual(ultimo["estado"], "falhou")
        self.assertEqual(self.banco.em_andamento(), [])

    def test_excecao_original_prevalece_se_encerrar_tambem_falha(self):
        original = self.banco.encerrar_varredura
        self.banco.gravar = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("original"))
        self.banco.encerrar_varredura = lambda *a, **k: (_ for _ in ()).throw(OSError("secundaria"))
        with self.assertRaises(RuntimeError):
            coletar_pacotes(self.banco, [], "")
        self.banco.encerrar_varredura = original

    def test_version_null_grava_vazio_e_arquivo_grande_conta_erro(self):
        nm = self.raiz / "nm"
        (nm / "n").mkdir(parents=True)
        (nm / "n" / "package.json").write_text('{"version": null}')
        (nm / "g").mkdir()
        (nm / "g" / "package.json").write_text('{"version": "1", "x": "' + "a" * (1024 * 1024) + '"}')
        lista, erros = ler_npm(nm)
        self.assertEqual(sorted(lista), [("g", ""), ("n", "")])
        self.assertEqual(erros, 1)


if __name__ == "__main__":
    unittest.main()
