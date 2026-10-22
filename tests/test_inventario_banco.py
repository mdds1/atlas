import unittest

from jarvis_pc.inventario.banco import Banco, TABELAS


def arq(caminho, tamanho=10, modificado=1.0):
    nome = caminho.rpartition("\\")[2]
    ext = "." + nome.rpartition(".")[2].lower() if "." in nome else ""
    return (caminho, nome, ext, caminho.rpartition("\\")[0], tamanho, modificado)


class TestBanco(unittest.TestCase):
    def setUp(self):
        self.b = Banco()
        self.addCleanup(self.b.fechar)

    def test_grava_e_consulta_arquivos(self):
        vid = self.b.iniciar_varredura("arquivos", 100.0)
        self.b.gravar("arquivos", vid, [arq("C:\\a\\x.py"), arq("C:\\a\\y.txt", 5)])
        self.b.encerrar_varredura(vid, "ok", 0, 110.0)
        linhas = self.b.consultar("SELECT caminho, tamanho FROM arquivos ORDER BY caminho")
        self.assertEqual([(r["caminho"], r["tamanho"]) for r in linhas], [("C:\\a\\x.py", 10), ("C:\\a\\y.txt", 5)])

    def test_aceita_dict_e_tupla(self):
        vid = self.b.iniciar_varredura("sistema", 1.0)
        self.b.gravar("apps", vid, [{"origem": "registro", "nome": "Git", "versao": "2.4"}, ("loja", "Calc", "1", "MS", "")])
        self.b.encerrar_varredura(vid, "ok", 0, 2.0)
        nomes = [r["nome"] for r in self.b.consultar("SELECT nome FROM apps ORDER BY nome")]
        self.assertEqual(nomes, ["Calc", "Git"])

    def test_tabela_desconhecida_e_recusada(self):
        vid = self.b.iniciar_varredura("arquivos", 1.0)
        with self.assertRaises(ValueError):
            self.b.gravar("arquivos; DROP TABLE apps", vid, [])

    def test_varredura_ok_apaga_o_que_ficou_para_tras(self):
        v1 = self.b.iniciar_varredura("arquivos", 1.0)
        self.b.gravar("arquivos", v1, [arq("C:\\velho.txt"), arq("C:\\fica.txt")])
        self.b.encerrar_varredura(v1, "ok", 0, 2.0)
        v2 = self.b.iniciar_varredura("arquivos", 3.0)
        self.b.gravar("arquivos", v2, [arq("C:\\fica.txt"), arq("C:\\novo.txt")])
        self.b.encerrar_varredura(v2, "ok", 0, 4.0)
        caminhos = [r["caminho"] for r in self.b.consultar("SELECT caminho FROM arquivos ORDER BY caminho")]
        self.assertEqual(caminhos, ["C:\\fica.txt", "C:\\novo.txt"])

    def test_varredura_cancelada_nao_apaga_nada(self):
        v1 = self.b.iniciar_varredura("arquivos", 1.0)
        self.b.gravar("arquivos", v1, [arq("C:\\velho.txt")])
        self.b.encerrar_varredura(v1, "ok", 0, 2.0)
        v2 = self.b.iniciar_varredura("arquivos", 3.0)
        self.b.gravar("arquivos", v2, [arq("C:\\novo.txt")])
        self.b.encerrar_varredura(v2, "cancelada", 0, 4.0)
        n = self.b.consultar("SELECT COUNT(*) AS n FROM arquivos")[0]["n"]
        self.assertEqual(n, 2)
        self.assertEqual(self.b.ultima_varredura("arquivos")["id"], v1)

    def test_varredura_do_sistema_nao_mexe_nos_arquivos(self):
        v1 = self.b.iniciar_varredura("arquivos", 1.0)
        self.b.gravar("arquivos", v1, [arq("C:\\a.txt")])
        self.b.encerrar_varredura(v1, "ok", 0, 2.0)
        v2 = self.b.iniciar_varredura("sistema", 3.0)
        self.b.encerrar_varredura(v2, "ok", 0, 4.0)
        self.assertEqual(self.b.consultar("SELECT COUNT(*) AS n FROM arquivos")[0]["n"], 1)

    def test_hash_sobrevive_se_o_arquivo_nao_mudou_e_some_se_mudou(self):
        v1 = self.b.iniciar_varredura("arquivos", 1.0)
        self.b.gravar("arquivos", v1, [arq("C:\\a.bin", 10, 5.0), arq("C:\\b.bin", 10, 5.0)])
        self.b.encerrar_varredura(v1, "ok", 0, 2.0)
        self.b.definir_hash("C:\\a.bin", "h1")
        self.b.definir_hash("C:\\b.bin", "h2")
        v2 = self.b.iniciar_varredura("arquivos", 3.0)
        self.b.gravar("arquivos", v2, [arq("C:\\a.bin", 10, 5.0), arq("C:\\b.bin", 10, 9.0)])
        self.b.encerrar_varredura(v2, "ok", 0, 4.0)
        h = {r["caminho"]: r["hash"] for r in self.b.consultar("SELECT caminho, hash FROM arquivos")}
        self.assertEqual(h, {"C:\\a.bin": "h1", "C:\\b.bin": None})

    def test_ultima_varredura_ignora_as_que_nao_deram_certo(self):
        self.assertIsNone(self.b.ultima_varredura("arquivos"))
        v1 = self.b.iniciar_varredura("arquivos", 1.0)
        self.b.encerrar_varredura(v1, "ok", 2, 5.0)
        v2 = self.b.iniciar_varredura("arquivos", 6.0)
        self.b.encerrar_varredura(v2, "falhou", 1, 7.0)
        u = self.b.ultima_varredura("arquivos")
        self.assertEqual((u["id"], u["fim"], u["erros"], u["estado"]), (v1, 5.0, 2, "ok"))

    def test_em_andamento_e_progresso(self):
        v = self.b.iniciar_varredura("arquivos", 1.0)
        self.b.progresso(v, 1234)
        andamento = self.b.em_andamento()
        self.assertEqual([(a["tipo"], a["itens"]) for a in andamento], [("arquivos", 1234)])
        self.b.encerrar_varredura(v, "ok", 0, 2.0)
        self.assertEqual(self.b.em_andamento(), [])

    def test_varredura_que_ficou_rodando_de_uma_execucao_anterior_vira_falhou(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "i.db")
            a = Banco(caminho)
            a.iniciar_varredura("arquivos", 1.0)
            a.fechar()
            b = Banco(caminho)
            self.assertEqual(b.em_andamento(), [])
            b.fechar()

    def test_todas_as_tabelas_existem(self):
        for tabela in TABELAS:
            with self.subTest(tabela=tabela):
                self.b.consultar(f"SELECT COUNT(*) FROM {tabela}")


if __name__ == "__main__":
    unittest.main()
