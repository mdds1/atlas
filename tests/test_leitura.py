import json
import unittest

from jarvis_pc import leitura
from jarvis_pc.leitura import AVISO, DEFINICOES, LIMITE_SAIDA, criar_ferramentas_leitura, ler_script

from tests.ajuda import ExecutorFalso, fixture


class TestFormatadores(unittest.TestCase):
    def test_resumo(self):
        texto = leitura.formatar_resumo(
            {
                "cpu_percent": 24,
                "ram_total_gb": 32.0,
                "ram_livre_gb": 20.0,
                "ligado_desde": "2026-10-19T10:29:41",
                "discos": [{"unidade": "C:", "total_gb": 1000.0, "livre_gb": 250.0}],
            }
        )
        self.assertIn("CPU em uso: 24%.", texto)
        self.assertIn("12.0 GB usados de 32.0 GB (20.0 GB livres).", texto)
        self.assertIn("Disco C: 250.0 GB livres de 1000.0 GB (25% livre).", texto)

    def test_resumo_com_disco_de_tamanho_zero_nao_quebra(self):
        texto = leitura.formatar_resumo({"discos": [{"unidade": "D:", "total_gb": 0, "livre_gb": 0}]})
        self.assertIn("Disco D:", texto)

    def test_processos_somam_por_programa_e_ordenam(self):
        texto = leitura.formatar_processos(
            {
                "processos": [
                    {"nome": "chrome", "pid": 1, "ram_mb": 600, "cpu_s": 10.0},
                    {"nome": "code", "pid": 2, "ram_mb": 800, "cpu_s": 5.0},
                    {"nome": "chrome", "pid": 3, "ram_mb": 500, "cpu_s": 2.0},
                ]
            }
        )
        linhas = texto.splitlines()
        self.assertIn("- chrome: 1100 MB em 2 processo(s), 12 s de CPU acumulada", linhas[1])
        self.assertIn("- code: 800 MB em 1 processo(s)", linhas[2])

    def test_processos_vazio(self):
        self.assertEqual(leitura.formatar_processos({"processos": []}), "Nenhum processo lido.")

    def test_inicializacao_tira_duplicados(self):
        item = {"nome": "Steam", "comando": "steam.exe -silent", "local": "Run"}
        texto = leitura.formatar_inicializacao({"itens": [item, dict(item, local="Outro")]})
        self.assertIn("(1)", texto)
        self.assertEqual(texto.count("- Steam"), 1)

    def test_inicializacao_limita_a_lista(self):
        itens = [{"nome": f"p{i}", "comando": "x"} for i in range(30)]
        texto = leitura.formatar_inicializacao({"itens": itens})
        self.assertIn("... e mais 5", texto)

    def test_eventos_agrupam_repeticoes(self):
        e = {"quando": "2026-10-19T10:00:00", "fonte": "SCM", "id": 7031, "mensagem": "servico   caiu"}
        mais_novo = dict(e, quando="2026-10-19T11:00:00")
        texto = leitura.formatar_eventos({"eventos": [e, mais_novo]})
        self.assertIn("(x2)", texto)
        self.assertIn("2026-10-19T11:00:00 SCM id 7031", texto)
        self.assertIn("servico caiu", texto)

    def test_eventos_vazio(self):
        self.assertEqual(leitura.formatar_eventos({"eventos": []}), "Nenhum erro crítico nas últimas 24 horas.")

    def test_servicos(self):
        self.assertEqual(
            leitura.formatar_servicos({"servicos": []}), "Todos os serviços automáticos estão rodando."
        )
        texto = leitura.formatar_servicos(
            {"servicos": [{"nome": "gpsvc", "exibicao": "Política", "estado": "Stopped", "codigo_saida": 0}]}
        )
        self.assertIn("parados (1)", texto)
        self.assertIn("- gpsvc (Política): Stopped, código de saída 0", texto)

    def test_drivers(self):
        ok = leitura.formatar_drivers(
            {"com_problema": [], "video": [{"nome": "RTX", "versao": "1.2", "data": "2026-09-29"}]}
        )
        self.assertIn("Nenhum dispositivo com erro de driver.", ok)
        self.assertIn("Placa de vídeo: RTX, driver 1.2 de 2026-09-29.", ok)
        ruim = leitura.formatar_drivers({"com_problema": [{"nome": "Wi-Fi", "codigo_erro": 43}], "video": []})
        self.assertIn("com erro de driver (1)", ruim)
        self.assertIn("- Wi-Fi: código de erro 43", ruim)

    def test_gpu(self):
        d = {
            "gpu": {"nome": "RTX", "temperatura_c": 52, "uso_percent": 3, "vram_usada_mb": 1328, "vram_total_mb": 12288},
            "cpu_temperatura_c": None,
        }
        texto = leitura.formatar_gpu(d)
        self.assertIn("GPU RTX: 52 °C, uso 3%, VRAM 1328 de 12288 MB (11%).", texto)
        self.assertIn("Temperatura da CPU: indisponível neste PC.", texto)
        self.assertIn("Temperatura da CPU: 61.5 °C.", leitura.formatar_gpu(dict(d, cpu_temperatura_c=61.5)))
        self.assertIn("GPU NVIDIA não encontrada", leitura.formatar_gpu({"gpu": None, "cpu_temperatura_c": None}))

    def test_atualizacoes(self):
        self.assertEqual(leitura.formatar_atualizacoes({"pendentes": []}), "Nenhuma atualização pendente.")
        texto = leitura.formatar_atualizacoes(
            {"pendentes": [{"titulo": "KB1", "critica": True}, {"titulo": "KB2", "critica": False}]}
        )
        self.assertIn("pendentes (2)", texto)
        self.assertIn("- KB1 [CRÍTICA]", texto)
        self.assertIn("- KB2", texto)
        self.assertNotIn("KB2 [CRÍTICA]", texto)


class TestDadosReais(unittest.TestCase):
    def test_formatador_aceita_a_saida_real_de_cada_script(self):
        for d in DEFINICOES:
            with self.subTest(ferramenta=d.nome):
                texto = d.formatar(fixture(d.arquivo))
                self.assertTrue(texto.strip())

    def test_todo_script_existe_e_nao_e_vazio(self):
        for d in DEFINICOES:
            with self.subTest(ferramenta=d.nome):
                self.assertGreater(len(ler_script(d.arquivo).strip()), 20)


class TestFerramenta(unittest.TestCase):
    def ferramenta(self, nome, executor):
        return next(t for t in criar_ferramentas_leitura(executor) if t.spec.name == nome)

    def test_devolve_aviso_e_texto(self):
        ex = ExecutorFalso(saida=json.dumps(fixture("resumo")))
        r = self.ferramenta("pc_resumo", ex).execute()
        self.assertTrue(r.success)
        self.assertTrue(r.content.startswith(AVISO))
        self.assertIn("CPU em uso", r.content)
        self.assertEqual(ex.chamadas[0]["json"], True)

    def test_usa_o_tempo_limite_da_definicao(self):
        ex = ExecutorFalso(saida=json.dumps(fixture("atualizacoes")))
        self.ferramenta("pc_atualizacoes", ex).execute()
        self.assertEqual(ex.chamadas[0]["timeout"], 120)

    def test_falha_do_powershell_vira_resultado_de_erro(self):
        ex = ExecutorFalso(saida="", codigo=-1, erro="tempo esgotado (30s)")
        r = self.ferramenta("pc_resumo", ex).execute()
        self.assertFalse(r.success)
        self.assertIn("Falha ao ler: tempo esgotado (30s)", r.content)

    def test_json_invalido_vira_resultado_de_erro(self):
        r = self.ferramenta("pc_resumo", ExecutorFalso(saida="isto não é json")).execute()
        self.assertFalse(r.success)
        self.assertIn("formato inesperado", r.content)

    def test_json_de_tipo_errado_vira_resultado_de_erro(self):
        r = self.ferramenta("pc_resumo", ExecutorFalso(saida="[1, 2]")).execute()
        self.assertFalse(r.success)

    def test_saida_muito_longa_e_cortada(self):
        eventos = [
            {"quando": "2026-10-19T10:00:00", "fonte": f"fonte{i}", "id": i, "mensagem": "m" * 300}
            for i in range(100)
        ]
        r = self.ferramenta("pc_eventos", ExecutorFalso(saida=json.dumps({"eventos": eventos}))).execute()
        self.assertEqual(len(r.content), LIMITE_SAIDA)


class TestEspecificacao(unittest.TestCase):
    def test_leitura_nunca_pede_confirmacao_e_nomes_sao_unicos(self):
        ferramentas = criar_ferramentas_leitura()
        nomes = [t.spec.name for t in ferramentas]
        self.assertEqual(len(nomes), len(set(nomes)))
        self.assertEqual(len(nomes), 8)
        for t in ferramentas:
            self.assertFalse(t.spec.requires_confirmation, t.spec.name)
            self.assertEqual(t.spec.parameters["type"], "object")


if __name__ == "__main__":
    unittest.main()
