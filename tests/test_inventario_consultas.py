import time
import unittest

from jarvis_pc.inventario import consultas
from jarvis_pc.inventario.banco import Banco as _Banco

MB = 1024 * 1024
AGORA = 1_800_000_000.0
_ABERTOS = []


def Banco():
    b = _Banco()
    _ABERTOS.append(b)
    return b


class Base(unittest.TestCase):
    def tearDown(self):
        while _ABERTOS:
            _ABERTOS.pop().fechar()


def arq(caminho, tamanho=10, mod=1.0):
    pasta, _, nome = caminho.rpartition("\\")
    ext = "." + nome.rpartition(".")[2].lower() if "." in nome else ""
    return (caminho, nome, ext, pasta, tamanho, mod)


def banco_com_arquivos(linhas, fim=AGORA - 3600):
    b = Banco()
    vid = b.iniciar_varredura("arquivos", fim - 5)
    b.gravar("arquivos", vid, linhas)
    b.encerrar_varredura(vid, "ok", 0, fim)
    return b


class TestFormatos(Base):
    def test_humano(self):
        self.assertEqual(consultas.humano(0), "0 B")
        self.assertEqual(consultas.humano(1023), "1023 B")
        self.assertEqual(consultas.humano(1024), "1.0 KB")
        self.assertEqual(consultas.humano(5 * MB), "5.0 MB")
        self.assertEqual(consultas.humano(3 * 1024 * MB), "3.00 GB")

    def test_data_curta(self):
        self.assertRegex(consultas.data_curta(AGORA), r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}$")


class TestSemDados(Base):
    def test_sem_varredura_orienta_a_atualizar(self):
        t = consultas.arquivos_buscar(Banco(), nome="x")
        self.assertIn("Ainda não há varredura de arquivos", t)
        self.assertIn("inv_atualizar", t)


class TestStatus(Base):
    def test_conta_cada_coisa_e_cita_a_data(self):
        b = banco_com_arquivos([arq("C:\\a.txt"), arq("C:\\b.txt")])
        t = consultas.status(b, agora=lambda: AGORA)
        self.assertIn("2 arquivo(s)", t)
        self.assertIn("0 app(s)", t)
        self.assertIn("há 1 hora(s)", t)

    def test_avisa_quando_esta_velho(self):
        b = banco_com_arquivos([arq("C:\\a.txt")], fim=AGORA - 3 * 86400)
        self.assertIn("desatualizado", consultas.status(b, agora=lambda: AGORA))

    def test_mostra_varredura_em_andamento(self):
        b = Banco()
        vid = b.iniciar_varredura("arquivos", AGORA)
        b.progresso(vid, 4321)
        t = consultas.status(b, agora=lambda: AGORA)
        self.assertIn("em andamento", t)
        self.assertIn("4321", t)


class TestBuscar(Base):
    def setUp(self):
        self.b = banco_com_arquivos(
            [
                arq("C:\\Jarvis\\instalar.ps1", 3000),
                arq("C:\\Jarvis\\venv\\x.py", 50),
                arq("C:\\Outro\\Instalar.PS1", 7000),
                arq("C:\\Outro\\grande.iso", 900 * MB),
                arq("C:\\Outro\\100%_pronto.txt", 5),
            ]
        )

    def test_por_nome_sem_diferenciar_maiuscula_e_conta_exata(self):
        t = consultas.arquivos_buscar(self.b, nome="instalar")
        self.assertIn("Achei 2 arquivo(s); mostrando 2.", t)
        self.assertIn("C:\\Jarvis\\instalar.ps1", t)
        self.assertIn("C:\\Outro\\Instalar.PS1", t)

    def test_por_extensao_com_ou_sem_ponto(self):
        for ext in (".py", "py", "PY"):
            with self.subTest(ext=ext):
                self.assertIn("Achei 1 arquivo(s)", consultas.arquivos_buscar(self.b, extensao=ext))

    def test_por_pasta_pega_subpastas_mas_nao_pasta_parecida(self):
        b = banco_com_arquivos([arq("C:\\Jarvis\\a.txt"), arq("C:\\Jarvis\\sub\\b.txt"), arq("C:\\Jarvis2\\c.txt")])
        self.assertIn("Achei 2 arquivo(s)", consultas.arquivos_buscar(b, pasta="C:\\Jarvis"))
        self.assertIn("Achei 2 arquivo(s)", consultas.arquivos_buscar(b, pasta="c:/jarvis/"))

    def test_por_tamanho_minimo(self):
        t = consultas.arquivos_buscar(self.b, minimo_mb=100)
        self.assertIn("Achei 1 arquivo(s)", t)
        self.assertIn("grande.iso", t)

    def test_limite_corta_a_lista_mas_nao_a_contagem(self):
        b = banco_com_arquivos([arq(f"C:\\p\\{i}.txt") for i in range(30)])
        t = consultas.arquivos_buscar(b, nome="txt", limite=5)
        self.assertIn("Achei 30 arquivo(s); mostrando 5.", t)
        self.assertEqual(sum(1 for l in t.splitlines() if l.startswith("- ")), 5)

    def test_percent_e_underscore_do_usuario_nao_viram_curinga(self):
        self.assertIn("Achei 1 arquivo(s)", consultas.arquivos_buscar(self.b, nome="100%"))
        self.assertIn("Não achei", consultas.arquivos_buscar(self.b, nome="inst_lar"))

    def test_nao_achou(self):
        self.assertIn("Não achei nenhum arquivo", consultas.arquivos_buscar(self.b, nome="zzz"))

    def test_limite_absurdo_e_aparado(self):
        b = banco_com_arquivos([arq(f"C:\\p\\{i}.txt") for i in range(3)])
        self.assertIn("mostrando 3", consultas.arquivos_buscar(b, nome="txt", limite=10**9))
        self.assertIn("mostrando 3", consultas.arquivos_buscar(b, nome="txt", limite=-4))

    def test_limite_maximo_de_100_linhas(self):
        b = banco_com_arquivos([arq(f"C:\\p\\{i}.txt") for i in range(120)])
        t = consultas.arquivos_buscar(b, nome="txt", limite=10**9)
        self.assertIn("Achei 120 arquivo(s); mostrando 100.", t)

    def test_percent_literal_nao_casa_outros_nomes(self):
        b = banco_com_arquivos([arq("C:\\p\\100%_x.txt"), arq("C:\\p\\1000_x.txt")])
        self.assertIn("Achei 1 arquivo(s)", consultas.arquivos_buscar(b, nome="100%"))

    def test_buscar_ordena_do_maior_para_o_menor(self):
        b = banco_com_arquivos([arq("C:\\p\\a.txt", 1), arq("C:\\p\\b.txt", 9)])
        t = consultas.arquivos_buscar(b, nome="txt")
        self.assertLess(t.index("b.txt"), t.index("a.txt"))


class TestMaioresEPastas(Base):
    def setUp(self):
        self.b = banco_com_arquivos(
            [
                arq("C:\\A\\um.bin", 100),
                arq("C:\\A\\sub\\dois.bin", 500),
                arq("C:\\B\\tres.bin", 300),
                arq("C:\\B\\quatro.bin", 200),
            ]
        )

    def test_maiores_ordenados(self):
        linhas = [l for l in consultas.arquivos_maiores(self.b, limite=3).splitlines() if l.startswith("- ")]
        self.assertEqual([l.split(" (")[0] for l in linhas], ["- C:\\A\\sub\\dois.bin", "- C:\\B\\tres.bin", "- C:\\B\\quatro.bin"])

    def test_maiores_dentro_de_uma_pasta(self):
        t = consultas.arquivos_maiores(self.b, pasta="C:\\B", limite=1)
        self.assertIn("tres.bin", t)
        self.assertNotIn("dois.bin", t)

    def test_espaco_por_pasta_soma_exata(self):
        t = consultas.arquivos_pastas(self.b, "C:\\")
        self.assertIn("- A: 600 B em 2 arquivo(s)", t)
        self.assertIn("- B: 500 B em 2 arquivo(s)", t)
        self.assertLess(t.index("- A:"), t.index("- B:"))

    def test_espaco_por_pasta_numa_subpasta(self):
        t = consultas.arquivos_pastas(self.b, "C:\\A")
        self.assertIn("- sub: 500 B em 1 arquivo(s)", t)
        self.assertIn("- (arquivos soltos em C:\\A): 100 B em 1 arquivo(s)", t)


class TestDuplicados(Base):
    def setUp(self):
        self.b = banco_com_arquivos(
            [
                arq("C:\\a\\x.bin", 2 * MB),
                arq("C:\\b\\x.bin", 2 * MB),
                arq("C:\\c\\y.bin", 2 * MB),
                arq("C:\\d\\pequeno.txt", 10),
                arq("C:\\e\\pequeno.txt", 10),
            ]
        )

    def hashes(self, caminho):
        return "H1" if caminho.endswith("x.bin") else "H2"

    def test_agrupa_por_hash_e_calcula_o_desperdicio(self):
        t = consultas.arquivos_duplicados(self.b, calcular_hash=self.hashes)
        self.assertIn("1 grupo(s) de arquivos idênticos", t)
        self.assertIn("2.0 MB cada", t)
        self.assertIn("C:\\a\\x.bin", t)
        self.assertIn("C:\\b\\x.bin", t)
        self.assertNotIn("C:\\c\\y.bin", t)
        self.assertIn("desperdício de 2.0 MB", t)

    def test_arquivos_menores_que_o_minimo_nao_entram(self):
        t = consultas.arquivos_duplicados(self.b, calcular_hash=self.hashes)
        self.assertNotIn("pequeno.txt", t)

    def test_hash_fica_guardado_e_nao_e_recalculado(self):
        chamadas = []
        consultas.arquivos_duplicados(self.b, calcular_hash=lambda c: chamadas.append(c) or self.hashes(c))
        antes = len(chamadas)
        consultas.arquivos_duplicados(self.b, calcular_hash=lambda c: chamadas.append(c) or self.hashes(c))
        self.assertEqual(len(chamadas), antes)

    def test_so_calcula_hash_de_arquivos_com_tamanho_repetido(self):
        b = banco_com_arquivos([arq("C:\\a\\x.bin", 2 * MB), arq("C:\\b\\y.bin", 3 * MB)])
        chamadas = []
        consultas.arquivos_duplicados(b, calcular_hash=lambda c: chamadas.append(c) or "H")
        self.assertEqual(chamadas, [])

    def test_arquivo_ilegivel_e_ignorado(self):
        t = consultas.arquivos_duplicados(self.b, calcular_hash=lambda c: None)
        self.assertIn("Não achei arquivos duplicados", t)

    def test_nenhum_duplicado(self):
        b = banco_com_arquivos([arq("C:\\a\\x.bin", 2 * MB), arq("C:\\b\\y.bin", 3 * MB)])
        self.assertIn("Não achei arquivos duplicados", consultas.arquivos_duplicados(b, calcular_hash=lambda c: "H"))

    def test_hash_arquivo_real(self):
        import hashlib
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "f.bin"
            p.write_bytes(b"abc")
            self.assertEqual(consultas.hash_arquivo(str(p)), hashlib.sha256(b"abc").hexdigest())
            self.assertIsNone(consultas.hash_arquivo(str(Path(t) / "nao-existe")))


class TestAppsEDependencias(Base):
    def setUp(self):
        self.b = Banco()
        vid = self.b.iniciar_varredura("sistema", AGORA - 60)
        self.b.gravar(
            "apps",
            vid,
            [
                {"origem": "registro", "nome": "Git", "versao": "2.43.0", "editor": "Git Dev", "local": "C:\\Git"},
                {"origem": "registro", "nome": "Ollama", "versao": "0.40.5", "editor": "Ollama", "local": ""},
                {"origem": "loja", "nome": "Microsoft.WindowsCalculator", "versao": "11.2", "editor": "MS", "local": ""},
            ],
        )
        self.b.gravar(
            "servicos",
            vid,
            [
                {"nome": "Spooler", "exibicao": "Spooler de Impressão", "estado": "Running", "inicio": "Auto"},
                {"nome": "wuauserv", "exibicao": "Windows Update", "estado": "Stopped", "inicio": "Manual"},
            ],
        )
        self.b.gravar("tarefas", vid, [{"caminho": "\\MS\\", "nome": "Defrag", "estado": "Ready"}])
        self.b.gravar("inicializacao", vid, [{"nome": "Discord", "comando": "C:\\D\\Update.exe", "local": "HKCU"}])
        self.b.encerrar_varredura(vid, "ok", 0, AGORA - 50)
        vp = self.b.iniciar_varredura("pacotes", AGORA - 40)
        self.b.gravar(
            "pacotes",
            vp,
            [("C:\\Jarvis\\venv", "openjarvis", "1.0.5"), ("C:\\Jarvis\\venv", "httpx", "0.27"), ("npm-global", "pm2", "5.3.0")],
        )
        self.b.encerrar_varredura(vp, "ok", 0, AGORA - 30)

    def test_apps_por_nome(self):
        t = consultas.apps(self.b, nome="git")
        self.assertIn("Achei 1 app(s)", t)
        self.assertIn("Git 2.43.0", t)

    def test_apps_sem_filtro_conta_tudo(self):
        self.assertIn("Achei 3 app(s)", consultas.apps(self.b))

    def test_apps_nao_achou(self):
        self.assertIn("Não achei nenhum app", consultas.apps(self.b, nome="zzz"))

    def test_dependencias_por_ambiente_e_nome(self):
        t = consultas.dependencias(self.b, ambiente="jarvis", nome="openjarvis")
        self.assertIn("Achei 1 pacote(s)", t)
        self.assertIn("openjarvis 1.0.5", t)

    def test_dependencias_sem_filtro_lista_os_ambientes(self):
        t = consultas.dependencias(self.b)
        self.assertIn("Ambientes com pacotes (2)", t)
        self.assertIn("C:\\Jarvis\\venv: 2 pacote(s)", t)
        self.assertIn("npm-global: 1 pacote(s)", t)

    def test_servicos_por_estado_ou_nome(self):
        t = consultas.sistema(self.b, "servicos", "stopped")
        self.assertIn("Achei 1 serviço(s)", t)
        self.assertIn("wuauserv", t)
        self.assertIn("Windows Update", consultas.sistema(self.b, "servicos", "update"))

    def test_tarefas_e_inicializacao(self):
        self.assertIn("Defrag", consultas.sistema(self.b, "tarefas"))
        self.assertIn("Discord", consultas.sistema(self.b, "inicializacao"))

    def test_tipo_desconhecido(self):
        self.assertIn("tipo deve ser", consultas.sistema(self.b, "banana"))


if __name__ == "__main__":
    unittest.main()
