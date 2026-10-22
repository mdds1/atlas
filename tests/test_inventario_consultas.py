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
    def test_apps_aproxima(self):
        t = consultas.apps(self.b, nome="Olama")
        self.assertIn("APROXIMEI", t)
        self.assertIn("Ollama", t)

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


class TestSoVarreduraOk(Base):
    def test_sistema_que_falha_nao_duplica_apps(self):
        b = Banco()
        v1 = b.iniciar_varredura("sistema", AGORA - 100)
        b.gravar("apps", v1, [{"origem": "registro", "nome": "Git", "versao": "1", "editor": "", "local": ""}])
        b.encerrar_varredura(v1, "ok", 0, AGORA - 90)
        v2 = b.iniciar_varredura("sistema", AGORA - 50)
        b.gravar("apps", v2, [{"origem": "registro", "nome": "Git", "versao": "1", "editor": "", "local": ""},
                              {"origem": "registro", "nome": "Novo", "versao": "1", "editor": "", "local": ""}])
        b.encerrar_varredura(v2, "falhou", 1, AGORA - 40)
        t = consultas.apps(b)
        self.assertIn("Achei 1 app(s)", t)
        self.assertNotIn("Novo", t)
        self.assertIn("1 app(s)", consultas.status(b, agora=lambda: AGORA))

    def test_arquivos_cancelada_nao_vaza_e_nova_ok_remove(self):
        b = Banco()
        v1 = b.iniciar_varredura("arquivos", AGORA - 100)
        b.gravar("arquivos", v1, [arq("C:\\x.txt"), arq("C:\\y.txt")])
        b.encerrar_varredura(v1, "ok", 0, AGORA - 90)
        v2 = b.iniciar_varredura("arquivos", AGORA - 50)
        b.gravar("arquivos", v2, [arq("C:\\x.txt"), arq("C:\\z.txt")])
        b.encerrar_varredura(v2, "cancelada", 0, AGORA - 40)
        t = consultas.arquivos_buscar(b, nome="txt")
        self.assertIn("Achei 2 arquivo(s)", t)
        self.assertIn("x.txt", t)
        self.assertIn("y.txt", t)
        self.assertNotIn("z.txt", t)
        self.assertIn(consultas.data_curta(AGORA - 90), t.splitlines()[0])
        self.assertIn("2 arquivo(s)", consultas.status(b, agora=lambda: AGORA))
        v3 = b.iniciar_varredura("arquivos", AGORA - 30)
        b.gravar("arquivos", v3, [arq("C:\\x.txt")])
        b.encerrar_varredura(v3, "ok", 0, AGORA - 20)
        t = consultas.arquivos_buscar(b, nome="txt")
        self.assertIn("Achei 1 arquivo(s)", t)
        self.assertNotIn("y.txt", t)

    def test_status_informa_ultima_tentativa_que_falhou(self):
        b = banco_com_arquivos([arq("C:\\a.txt")])
        v = b.iniciar_varredura("arquivos", AGORA - 10)
        b.encerrar_varredura(v, "cancelada", 0, AGORA - 5)
        self.assertIn("cancelada", consultas.status(b, agora=lambda: AGORA))

    def test_aviso_de_dado_velho_em_toda_consulta(self):
        b = banco_com_arquivos([arq("C:\\a.txt")], fim=AGORA - 3 * 86400)
        self.assertIn("desatualizado", consultas.arquivos_buscar(b, nome="a", agora=lambda: AGORA))
        self.assertIn("Dados da varredura de", consultas.arquivos_buscar(b, nome="a", agora=lambda: AGORA).splitlines()[0])


class TestPastasExatas(Base):
    def test_varios_soltos_viram_uma_linha_com_a_soma(self):
        b = banco_com_arquivos([arq("C:\\A\\um.txt", 10), arq("C:\\A\\dois.txt", 20), arq("C:\\A\\s\\x", 5)])
        t = consultas.arquivos_pastas(b, "C:\\A")
        self.assertEqual(t.count("arquivos soltos"), 1)
        self.assertIn("- (arquivos soltos em C:\\A): 30 B em 2 arquivo(s)", t)
        self.assertIn("- s: 5 B em 1 arquivo(s)", t)

    def test_arquivo_e_pasta_homonimos(self):
        for nome_arq in ("foo", "Foo"):
            with self.subTest(arq=nome_arq):
                b = banco_com_arquivos([arq("C:\\A\\" + nome_arq, 7), arq("C:\\A\\foo\\x", 3)])
                t = consultas.arquivos_pastas(b, "C:\\A")
                self.assertIn("- (arquivos soltos em C:\\A): 7 B em 1 arquivo(s)", t)
                self.assertIn("- foo: 3 B em 1 arquivo(s)", t)

    def test_subpastas_com_maiusculas_diferentes_somam_juntas(self):
        b = banco_com_arquivos([arq("C:\\A\\Foo\\x", 3), arq("C:\\A\\foo\\y", 4)])
        t = consultas.arquivos_pastas(b, "C:\\A")
        self.assertEqual(sum(1 for l in t.splitlines() if l.startswith("- ")), 1)
        self.assertIn("7 B em 2 arquivo(s)", t)

    def test_soma_das_linhas_bate_com_o_total(self):
        b = banco_com_arquivos([arq("C:\\A\\a", 1), arq("C:\\A\\b", 2), arq("C:\\A\\s\\c", 4), arq("C:\\A\\t\\d", 8)])
        t = consultas.arquivos_pastas(b, "C:\\A")
        self.assertEqual(sum(int(l.split(": ")[1].split(" B")[0]) for l in t.splitlines() if l.startswith("- ")), 15)

    def test_soltos_ficam_fora_do_limite(self):
        b = banco_com_arquivos([arq("C:\\A\\a", 1), arq("C:\\A\\s\\c", 4), arq("C:\\A\\t\\d", 8)])
        t = consultas.arquivos_pastas(b, "C:\\A", limite=1)
        self.assertIn("soltos", t)
        self.assertIn("- t:", t)
        self.assertNotIn("- s:", t)


class TestDuplicadosRobustos(Base):
    def setUp(self):
        import jarvis_pc.inventario.consultas as c
        self._antigo = c.LIMITE_HASH
        self.addCleanup(setattr, c, "LIMITE_HASH", self._antigo)

    def test_limite_de_hash_da_resultado_parcial_e_converge(self):
        consultas.LIMITE_HASH = 3
        b = banco_com_arquivos([arq(f"C:\\d{i}\\x.bin", 2 * MB) for i in range(7)])
        chamadas = []
        calc = lambda c: chamadas.append(c) or "H"
        t1 = consultas.arquivos_duplicados(b, calcular_hash=calc)
        self.assertIn("Resultado parcial: faltam 4 arquivo(s) a verificar. Pergunte de novo para continuar.", t1)
        t2 = consultas.arquivos_duplicados(b, calcular_hash=calc)
        self.assertIn("faltam 1 arquivo(s)", t2)
        t3 = consultas.arquivos_duplicados(b, calcular_hash=calc)
        self.assertNotIn("parcial", t3)
        self.assertIn("7 cópias", t3)
        self.assertIn("desperdício de 12.0 MB", t3)
        self.assertEqual(len(chamadas), 7)

    def test_ilegiveis_ganham_sentinela_e_nao_travam_o_orcamento(self):
        consultas.LIMITE_HASH = 3
        linhas = [arq(f"C:\\u{i}\\z.bin", 3 * MB) for i in range(5)]
        linhas += [arq("C:\\a\\x.bin", 2 * MB), arq("C:\\b\\x.bin", 2 * MB)]
        b = banco_com_arquivos(linhas)
        calc = lambda c: None if c.endswith("z.bin") else "H"
        consultas.arquivos_duplicados(b, calcular_hash=calc)
        chamadas = []
        t = consultas.arquivos_duplicados(b, calcular_hash=lambda c: chamadas.append(c) or calc(c))
        self.assertEqual(chamadas, [])
        self.assertIn("C:\\a\\x.bin", t)
        self.assertIn("5 arquivo(s) ilegível(is) ignorado(s)", t)

    def test_upsert_preserva_o_sentinela_se_nada_mudou(self):
        b = banco_com_arquivos([arq("C:\\a\\z.bin", 3 * MB), arq("C:\\b\\z.bin", 3 * MB)])
        consultas.arquivos_duplicados(b, calcular_hash=lambda c: None)
        v = b.iniciar_varredura("arquivos", AGORA)
        b.gravar("arquivos", v, [arq("C:\\a\\z.bin", 3 * MB), arq("C:\\b\\z.bin", 3 * MB)])
        b.encerrar_varredura(v, "ok", 0, AGORA + 1)
        chamadas = []
        consultas.arquivos_duplicados(b, calcular_hash=lambda c: chamadas.append(c) or None)
        self.assertEqual(chamadas, [])

    def test_duplicados_ignoram_arquivo_de_varredura_cancelada(self):
        b = banco_com_arquivos([arq("C:\\a\\x.bin", 2 * MB)])
        v = b.iniciar_varredura("arquivos", AGORA)
        b.gravar("arquivos", v, [arq("C:\\a\\x.bin", 2 * MB), arq("C:\\b\\x.bin", 2 * MB)])
        b.encerrar_varredura(v, "cancelada", 0, AGORA + 1)
        chamadas = []
        t = consultas.arquivos_duplicados(b, calcular_hash=lambda c: chamadas.append(c) or "H", agora=lambda: AGORA)
        self.assertIn("Não achei", t)
        self.assertEqual(chamadas, [])

    def test_vazios_nao_sao_duplicados(self):
        b = banco_com_arquivos([arq("C:\\a\\v", 0), arq("C:\\b\\v", 0)])
        self.assertIn("Não achei", consultas.arquivos_duplicados(b, minimo_mb=0, calcular_hash=lambda c: "H"))

    def test_mostra_quantos_grupos_e_copias_ficaram_de_fora(self):
        b = banco_com_arquivos([arq(f"C:\\d{i}\\x.bin", 2 * MB) for i in range(8)])
        t = consultas.arquivos_duplicados(b, calcular_hash=lambda c: "H")
        self.assertIn("e mais 2 cópia(s)", t)
        linhas = [arq(f"C:\\g{g}\\{i}.bin", (2 + g) * MB) for g in range(3) for i in range(2)]
        t = consultas.arquivos_duplicados(banco_com_arquivos(linhas), limite=2, calcular_hash=lambda c: "H" + str(c)[3])
        self.assertIn("mostrando 2 de 3 grupo(s)", t)


if __name__ == "__main__":
    unittest.main()


class TestSemAcentoEAproximacao(Base):
    def setUp(self):
        self.b = banco_com_arquivos(
            [
                arq("C:\\Docs\\Relatório Anual.docx", 10),
                arq("C:\\Docs\\orcamento.xlsx", 20),
                arq("C:\\Jarvis\\instalar.ps1", 30),
            ]
        )

    def test_sem_acento_e_sem_maiuscula(self):
        t = consultas.arquivos_buscar(self.b, nome="RELATORIO")
        self.assertIn("C:\\Docs\\Relatório Anual.docx", t)
        self.assertNotIn("APROXIMEI", t)
        self.assertIn("C:\\Docs\\orcamento.xlsx", consultas.arquivos_buscar(self.b, nome="orçamento"))

    def test_aproxima_so_quando_a_exata_nao_acha_e_avisa(self):
        t = consultas.arquivos_buscar(self.b, nome="instalr.ps1")
        self.assertIn("APROXIMEI", t)
        self.assertIn("instalar.ps1", t)

    def test_sem_parecido_continua_nao_achei(self):
        t = consultas.arquivos_buscar(self.b, nome="zzzzzz")
        self.assertIn("Não achei nenhum arquivo", t)
        self.assertNotIn("APROXIMEI", t)

    def test_mesma_inicial_e_tamanho_mas_distante_nao_aproxima(self):
        t = consultas.arquivos_buscar(self.b, nome="oxxxxxxxxxxxx")
        self.assertNotIn("APROXIMEI", t)
        self.assertIn("Não achei nenhum arquivo", t)

    def test_aproximacao_nunca_devolve_arquivo_fora_da_varredura_ok(self):
        vid = self.b.iniciar_varredura("arquivos", AGORA - 10)
        self.b.gravar("arquivos", vid, [arq("C:\\Segredo\\orcamento2.xlsx", 5)])
        t = consultas.arquivos_buscar(self.b, nome="orcamnto2.xlsx")
        self.assertNotIn("orcamento2", t)
        self.assertNotIn("Segredo", t)
        self.assertEqual(consultas.aproximar(self.b, "arquivos_ok", "orcamnto2.xlsx"), ["orcamento.xlsx"])

    def test_aproximacao_e_deterministica_com_muitos_candidatos(self):
        linhas = [arq("C:\\L\\a%05d.txt" % i, 1) for i in range(300)]
        b = banco_com_arquivos(linhas)
        r = [consultas.aproximar(b, "arquivos_ok", "a00150.txt") for _ in range(2)]
        self.assertEqual(r[0], r[1])
        self.assertEqual(r[0][0], "a00150.txt")

    def test_funcao_sem_acento(self):
        from jarvis_pc.inventario.banco import sem_acento
        self.assertEqual(sem_acento("Ação É"), "acao e")
        self.assertIsNone(sem_acento(None))
