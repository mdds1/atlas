import os
import tempfile
import unittest
from pathlib import Path

from jarvis_pc.inventario import arquivos
from jarvis_pc.inventario.arquivos import varrer_arquivos
from jarvis_pc.inventario.banco import Banco
from jarvis_pc.inventario.exclusoes import Exclusoes


def criar(raiz, relativo, conteudo=b"x"):
    caminho = Path(raiz) / relativo
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(conteudo)
    return caminho


class TestVarredura(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = self._tmp.name
        self.addCleanup(self._tmp.cleanup)
        self.banco = Banco()
        self.addCleanup(self.banco.fechar)
        self.e = os.path.join(self.raiz, "E")
        self.ex = Exclusoes(
            raiz_fotos=self.e,
            pasta_vetada=os.path.join(self.e, "Fotos & Videos"),
            pasta_livre=os.path.join(self.e, "FORWARD"),
        )

    def caminhos(self):
        return sorted(r["caminho"] for r in self.banco.consultar("SELECT caminho FROM arquivos"))

    def test_cataloga_arquivos_com_tamanho_extensao_e_pasta(self):
        a = criar(self.raiz, "proj/main.PY", b"12345")
        r = varrer_arquivos(self.banco, [self.raiz], self.ex)
        linha = self.banco.consultar("SELECT * FROM arquivos WHERE caminho = ?", (str(a),))[0]
        self.assertEqual((linha["nome"], linha["ext"], linha["tamanho"]), ("main.PY", ".py", 5))
        self.assertEqual(linha["pasta"], str(a.parent))
        self.assertEqual((r.arquivos, r.erros, r.estado), (1, 0, "ok"))

    def test_arquivo_sem_extensao(self):
        criar(self.raiz, "Makefile")
        varrer_arquivos(self.banco, [self.raiz], self.ex)
        self.assertEqual(self.banco.consultar("SELECT ext FROM arquivos")[0]["ext"], "")

    def test_fotos_e_videos_fica_inteira_de_fora(self):
        criar(self.e, "Fotos & Videos/Videos/festa.mp4")
        criar(self.e, "Fotos & Videos/nota.txt")
        criar(self.e, "Docs/plano.docx")
        varrer_arquivos(self.banco, [self.raiz], self.ex)
        self.assertEqual([os.path.basename(c) for c in self.caminhos()], ["plano.docx"])

    def test_foto_no_e_fora_do_forward_nao_entra_e_a_do_forward_entra(self):
        criar(self.e, "Mae/fotos/a.jpg")
        criar(self.e, "FORWARD/marca/logo.png")
        criar(self.e, "FORWARD/marca/leia.txt")
        varrer_arquivos(self.banco, [self.raiz], self.ex)
        self.assertEqual([os.path.basename(c) for c in self.caminhos()], ["leia.txt", "logo.png"])

    def test_segredo_e_appdata_nao_entram(self):
        criar(self.raiz, "x/.env")
        criar(self.raiz, "x/senhas.txt")
        criar(self.raiz, "Users/d/AppData/Local/a.txt")
        criar(self.raiz, "x/ok.txt")
        varrer_arquivos(self.banco, [self.raiz], self.ex)
        self.assertEqual([os.path.basename(c) for c in self.caminhos()], ["ok.txt"])

    def test_pasta_ilegivel_conta_erro_e_segue(self):
        criar(self.raiz, "boa/a.txt")
        original = os.scandir

        def scandir(caminho):
            if str(caminho).endswith("ruim"):
                raise PermissionError("negado")
            return original(caminho)

        (Path(self.raiz) / "ruim").mkdir()
        arquivos.os.scandir = scandir
        try:
            r = varrer_arquivos(self.banco, [self.raiz], self.ex)
        finally:
            arquivos.os.scandir = original
        self.assertEqual(r.erros, 1)
        self.assertEqual(len(self.caminhos()), 1)

    def test_nao_segue_link_simbolico(self):
        criar(self.raiz, "real/a.txt")
        try:
            os.symlink(Path(self.raiz) / "real", Path(self.raiz) / "atalho")
        except (OSError, NotImplementedError):
            self.skipTest("sem permissao para criar link simbolico")
        varrer_arquivos(self.banco, [self.raiz], self.ex)
        self.assertEqual(len(self.caminhos()), 1)

    def test_nao_entra_em_ponto_de_reparse(self):
        class Stat:
            st_file_attributes = 0x400

        class Entrada:
            def stat(self, follow_symlinks=False):
                return Stat()

        self.assertTrue(arquivos._reparse(Entrada()))

        class Comum:
            def stat(self, follow_symlinks=False):
                return type("S", (), {})()

        self.assertFalse(arquivos._reparse(Comum()))

    def test_pasta_podada_nem_chega_a_ser_aberta(self):
        criar(self.e, "Fotos & Videos/nota.txt")
        abertas = []
        original = os.scandir

        def scandir(caminho):
            abertas.append(str(caminho))
            return original(caminho)

        arquivos.os.scandir = scandir
        try:
            varrer_arquivos(self.banco, [self.raiz], self.ex)
        finally:
            arquivos.os.scandir = original
        self.assertFalse([a for a in abertas if "Fotos & Videos" in a])

    def test_link_simbolico_e_ignorado_mesmo_que_pareca_arquivo(self):
        class Stat:
            st_size = 1
            st_mtime = 1.0

        class Falsa:
            path = os.path.join("x", "ligado.txt")
            name = "ligado.txt"

            def is_symlink(self):
                return True

            def is_dir(self, follow_symlinks=True):
                return False

            def is_file(self, follow_symlinks=True):
                return True

            def stat(self, follow_symlinks=True):
                return Stat()

        class Lista:
            def __enter__(self):
                return iter([Falsa()])

            def __exit__(self, *a):
                return False

        original = os.scandir
        arquivos.os.scandir = lambda caminho: Lista()
        try:
            varrer_arquivos(self.banco, [self.raiz], self.ex)
        finally:
            arquivos.os.scandir = original
        self.assertEqual(self.caminhos(), [])

    def test_cancelada_nao_apaga_o_catalogo_anterior(self):
        criar(self.raiz, "a.txt")
        varrer_arquivos(self.banco, [self.raiz], self.ex)
        r = varrer_arquivos(self.banco, [self.raiz], self.ex, cancelado=lambda: True)
        self.assertEqual(r.estado, "cancelada")
        self.assertEqual(len(self.caminhos()), 1)

    def test_segunda_varredura_tira_o_que_sumiu(self):
        a = criar(self.raiz, "a.txt")
        criar(self.raiz, "b.txt")
        varrer_arquivos(self.banco, [self.raiz], self.ex)
        a.unlink()
        varrer_arquivos(self.banco, [self.raiz], self.ex)
        self.assertEqual([os.path.basename(c) for c in self.caminhos()], ["b.txt"])

    def test_grava_em_lotes_e_registra_progresso(self):
        for i in range(7):
            criar(self.raiz, f"p/{i}.txt")
        r = varrer_arquivos(self.banco, [self.raiz], self.ex, lote=3)
        self.assertEqual(r.arquivos, 7)
        self.assertEqual(self.banco.ultima_varredura("arquivos")["itens"], 7)

    def test_usa_o_relogio_injetado(self):
        criar(self.raiz, "a.txt")
        tempos = iter([100.0, 107.5])
        r = varrer_arquivos(self.banco, [self.raiz], self.ex, agora=lambda: next(tempos))
        self.assertEqual(r.segundos, 7.5)
        u = self.banco.ultima_varredura("arquivos")
        self.assertEqual((u["inicio"], u["fim"]), (100.0, 107.5))


if __name__ == "__main__":
    unittest.main()
