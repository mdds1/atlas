import unittest

from jarvis_pc.inventario.exclusoes import Exclusoes, dentro, normalizar


class TestNormalizar(unittest.TestCase):
    def test_barra_maiuscula_e_barra_final(self):
        self.assertEqual(normalizar("E:/Fotos/"), "e:\\fotos")
        self.assertEqual(normalizar("C:\\Users\\Diniz"), "c:\\users\\diniz")

    def test_dentro_so_vale_para_a_propria_pasta_ou_filhos(self):
        self.assertTrue(dentro("E:\\FORWARD", "E:\\FORWARD"))
        self.assertTrue(dentro("e:\\forward\\a\\b.png", "E:\\FORWARD"))
        self.assertFalse(dentro("E:\\FORWARD2\\a.png", "E:\\FORWARD"))
        self.assertFalse(dentro("E:\\outra\\FORWARD\\a.png", "E:\\FORWARD"))


class TestPastas(unittest.TestCase):
    def setUp(self):
        self.ex = Exclusoes()

    def test_fotos_e_videos_inteira_fica_de_fora(self):
        self.assertTrue(self.ex.pasta_podada("E:\\Fotos & Videos"))
        self.assertTrue(self.ex.pasta_podada("e:\\fotos & videos\\2020\\viagem"))

    def test_pasta_parecida_nao_e_podada(self):
        self.assertFalse(self.ex.pasta_podada("E:\\Fotos & Videos antigos"))
        self.assertFalse(self.ex.pasta_podada("D:\\Fotos & Videos"))

    def test_appdata_em_qualquer_lugar_fica_de_fora(self):
        self.assertTrue(self.ex.pasta_podada("C:\\Users\\Diniz\\AppData"))
        self.assertTrue(self.ex.pasta_podada("C:\\Users\\Diniz\\appdata\\Local\\Temp"))
        self.assertTrue(self.ex.pasta_podada("D:\\backup\\AppData\\Roaming"))

    def test_pastas_de_segredo_e_de_ruido(self):
        for p in ("C:\\Users\\Diniz\\.ssh", "C:\\Users\\Diniz\\.aws\\x", "C:\\Users\\Diniz\\.gnupg",
                  "C:\\$Recycle.Bin\\S-1", "E:\\System Volume Information"):
            with self.subTest(p=p):
                self.assertTrue(self.ex.pasta_podada(p))

    def test_pasta_comum_nao_e_podada(self):
        for p in ("C:\\Jarvis", "E:\\FloripaOT\\Client", "E:\\FORWARD\\05 MARCA", "C:\\"):
            with self.subTest(p=p):
                self.assertFalse(self.ex.pasta_podada(p))


class TestFotos(unittest.TestCase):
    def setUp(self):
        self.ex = Exclusoes()

    def test_foto_no_e_fica_de_fora(self):
        for nome in ("a.jpg", "a.JPEG", "a.png", "a.gif", "a.bmp", "a.webp", "a.heic", "a.heif",
                     "a.tif", "a.tiff", "a.raw", "a.cr2", "a.nef", "a.dng"):
            with self.subTest(nome=nome):
                self.assertTrue(self.ex.arquivo_excluido("E:\\Mãe\\fotos mãe\\" + nome))

    def test_foto_sob_forward_entra(self):
        self.assertFalse(self.ex.arquivo_excluido("E:\\FORWARD\\05 MARCA\\Camisas Fotos\\frente.png"))
        self.assertFalse(self.ex.arquivo_excluido("e:\\forward\\logo.JPG"))

    def test_foto_fora_do_e_entra(self):
        self.assertFalse(self.ex.arquivo_excluido("C:\\Windows\\Web\\Wallpaper\\img0.jpg"))
        self.assertFalse(self.ex.arquivo_excluido("D:\\x\\a.png"))

    def test_nao_foto_no_e_entra(self):
        for nome in ("relatorio.docx", "plano.pdf", "video.mp4", "script.ps1"):
            with self.subTest(nome=nome):
                self.assertFalse(self.ex.arquivo_excluido("E:\\Documentos Matheus\\" + nome))

    def test_qualquer_arquivo_dentro_de_fotos_e_videos_fica_de_fora(self):
        self.assertTrue(self.ex.arquivo_excluido("E:\\Fotos & Videos\\Videos\\festa.mp4"))
        self.assertTrue(self.ex.arquivo_excluido("E:\\Fotos & Videos\\nota.txt"))

    def test_raiz_e_regras_sao_configuraveis(self):
        ex = Exclusoes(raiz_fotos="/tmp/x/E", pasta_vetada="/tmp/x/E/Fotos", pasta_livre="/tmp/x/E/FORWARD")
        self.assertTrue(ex.arquivo_excluido("/tmp/x/E/outra/a.jpg"))
        self.assertFalse(ex.arquivo_excluido("/tmp/x/E/FORWARD/a.jpg"))
        self.assertTrue(ex.arquivo_excluido("/tmp/x/E/Fotos/doc.txt"))


class TestSegredos(unittest.TestCase):
    def setUp(self):
        self.ex = Exclusoes()

    def test_nomes_de_segredo_ficam_de_fora(self):
        for nome in (".env", ".env.local", "chave.pem", "a.key", "id_rsa", "id_rsa.pub", "cofre.kdbx",
                     "putty.ppk", "Cookies", "Login Data", "SENHAS_lideres.json", "meu-password.txt",
                     "api_token.txt", "client_secret.json", "credencial.xml", "Credentials.db"):
            with self.subTest(nome=nome):
                self.assertTrue(self.ex.arquivo_excluido("C:\\Projetos\\x\\" + nome))

    def test_arquivo_normal_entra(self):
        for nome in ("main.py", "README.md", "config.json", "relatorio.docx"):
            with self.subTest(nome=nome):
                self.assertFalse(self.ex.arquivo_excluido("C:\\Projetos\\x\\" + nome))

    def test_arquivo_dentro_de_pasta_podada_fica_de_fora(self):
        self.assertTrue(self.ex.arquivo_excluido("C:\\Users\\Diniz\\.ssh\\known_hosts"))
        self.assertTrue(self.ex.arquivo_excluido("C:\\Users\\Diniz\\AppData\\Local\\a.txt"))


if __name__ == "__main__":
    unittest.main()
