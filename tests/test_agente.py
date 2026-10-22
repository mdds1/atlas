import json
import tempfile
import unittest
from pathlib import Path

from jarvis_pc.agente import criar_agente, montar_texto_confirmacao, perguntar
from jarvis_pc.memoria import Memoria
from jarvis_pc.permissoes import Permissoes
from jarvis_pc.ponte import NAO, SIM, SIM_SEMPRE
from jarvis_pc.registro import Registro
from jarvis_pc.sessao import Sessao

from tests.ajuda import ExecutorFalso, MotorFalso, chamada, final, fixture

CMD = {"comando": "Restart-Service -Name Spooler", "motivo": "travado"}


def nunca(_texto, _pode_sempre):
    raise AssertionError("o OK não devia ser pedido")


def responde(resposta, pedidos=None):
    def f(texto, pode_sempre):
        if pedidos is not None:
            pedidos.append((texto, pode_sempre))
        return resposta
    return f


def montar(roteiro, confirmar, executor=None, **kw):
    registro = Registro()
    executor = executor or ExecutorFalso(saida=json.dumps(fixture("resumo")))
    motor = MotorFalso(roteiro)
    agente = criar_agente(modelo="falso", confirmar=confirmar, registro=registro, executor=executor, engine=motor, **kw)
    return agente, registro, executor, motor


def eventos(registro, tipo):
    return [e for e in registro.eventos if e["tipo"] == tipo]


class TestLeitura(unittest.TestCase):
    def test_leitura_roda_sem_ok_e_registra_nivel(self):
        agente, registro, executor, _ = montar([chamada("pc_resumo"), final("Disco ok.")], nunca)
        self.assertEqual(agente.perguntar("o pc está lento?"), "Disco ok.")
        self.assertEqual(len(executor.chamadas), 1)
        c = eventos(registro, "chamada")[0]
        self.assertEqual((c["nivel"], c["permitido"], c["regra"], c["origem"]), ("ler", True, "leitura", "janela"))


class TestAgir(unittest.TestCase):
    def test_sim_executa_uma_vez_sem_gravar_regra(self):
        pedidos = []
        agente, registro, executor, _ = montar([chamada("pc_comando", **CMD), final("Reiniciei.")], responde(SIM, pedidos))
        agente.perguntar("conserta a impressora")
        self.assertEqual([c["script"] for c in executor.chamadas], ["Restart-Service -Name Spooler"])
        self.assertIn("Restart-Service -Name Spooler", pedidos[0][0])
        self.assertIs(pedidos[0][1], True)
        self.assertEqual(agente.permissoes.regras, [])
        self.assertEqual(eventos(registro, "chamada")[0]["regra"], "ok desta vez")

    def test_nao_para_o_laco_e_pergunta(self):
        agente, registro, executor, motor = montar([chamada("pc_comando", **CMD), final("nunca chega")], responde(NAO))
        texto = agente.perguntar("conserta a impressora")
        self.assertEqual(executor.chamadas, [])
        self.assertEqual(motor.chamadas, 1)
        self.assertIn("O que prefere", texto)
        self.assertEqual(eventos(registro, "resposta")[0]["parou"], "nao")

    def test_erro_no_ok_conta_como_nao(self):
        def quebra(_t, _p):
            raise RuntimeError("janela fechou")
        agente, _, executor, _ = montar([chamada("pc_comando", **CMD), final("x")], quebra)
        agente.perguntar("conserta")
        self.assertEqual(executor.chamadas, [])

    def test_resposta_estranha_conta_como_nao(self):
        agente, _, executor, _ = montar([chamada("pc_comando", **CMD), final("x")], responde(True))
        agente.perguntar("conserta")
        self.assertEqual(executor.chamadas, [])

    def test_sim_sempre_pela_janela_grava_e_a_proxima_nao_pede(self):
        with tempfile.TemporaryDirectory() as t:
            p = Permissoes(Path(t) / "permissoes.json")
            pedidos = []
            roteiro = [chamada("pc_comando", **CMD), final("1"), chamada("pc_comando", **CMD), final("2")]
            agente, registro, executor, _ = montar(roteiro, responde(SIM_SEMPRE, pedidos), permissoes=p)
            agente.perguntar("conserta")
            agente.perguntar("conserta de novo")
        self.assertEqual(len(pedidos), 1)
        self.assertEqual(len(executor.chamadas), 2)
        self.assertEqual(eventos(registro, "regra_nova")[0]["regra"], "pc_comando: Restart-Service -Name Spooler")
        self.assertEqual(eventos(registro, "chamada")[1]["regra"], "pc_comando: Restart-Service -Name Spooler")

    def test_sim_sempre_com_regra_recusada_avisa_o_matheus(self):
        cmd = {"comando": "Restart-Service -Name Spo*", "motivo": "travado"}
        agente, registro, executor, _ = montar([chamada("pc_comando", **cmd), final("Feito.")], responde(SIM_SEMPRE))
        resposta = agente.perguntar("conserta")
        self.assertEqual(len(executor.chamadas), 1)
        self.assertIn("Executei só desta vez; a regra não foi gravada porque", resposta)
        self.assertIn("curinga", resposta)
        self.assertTrue(resposta.startswith("Feito."))

    def test_aviso_de_regra_nao_vaza_para_a_pergunta_seguinte(self):
        cmd = {"comando": "Restart-Service -Name Spo*", "motivo": "travado"}
        roteiro = [chamada("pc_comando", **cmd), final("a"), final("b")]
        agente, _, _, _ = montar(roteiro, responde(SIM_SEMPRE))
        agente.perguntar("1")
        self.assertEqual(agente.perguntar("2"), "b")

    def test_pelo_telegram_nao_oferece_e_nao_grava_regra(self):
        pedidos = []
        agente, _, executor, _ = montar([chamada("pc_comando", **CMD), final("x")], responde(SIM_SEMPRE, pedidos))
        agente.perguntar("conserta", origem="telegram")
        self.assertIs(pedidos[0][1], False)
        self.assertEqual(agente.permissoes.regras, [])
        self.assertEqual(executor.chamadas, [])

    def test_origem_desconhecida_e_tratada_como_telegram(self):
        pedidos = []
        agente, _, _, _ = montar([chamada("pc_comando", **CMD), final("x")], responde(SIM, pedidos))
        agente.perguntar("conserta", origem="email")
        self.assertIs(pedidos[0][1], False)

    def test_bloqueado_nem_pede_ok(self):
        roteiro = [chamada("pc_comando", comando="Format-Volume -DriveLetter D", motivo="x"), final("Não posso.")]
        agente, registro, executor, motor = montar(roteiro, nunca)
        agente.perguntar("formate o D")
        self.assertEqual(executor.chamadas, [])
        c = eventos(registro, "chamada")[0]
        self.assertEqual((c["nivel"], c["permitido"]), ("bloqueado", False))
        self.assertIn("BLOQUEADO", motor.vistas[1][-1].content)

    def test_ferramenta_desconhecida_e_negada(self):
        agente, registro, _, motor = montar([chamada("shell_exec", command="dir"), final("fim")], nunca)
        agente.perguntar("x")
        self.assertIn("não existe", motor.vistas[1][-1].content)

    def test_acao_que_falha_para(self):
        executor = ExecutorFalso(saida="", codigo=1, erro="acesso negado")
        roteiro = [chamada("pc_comando", **CMD), final("nunca chega")]
        agente, registro, _, motor = montar(roteiro, responde(SIM), executor=executor)
        texto = agente.perguntar("conserta")
        self.assertIn("Parei", texto)
        self.assertEqual(motor.chamadas, 1)


class TestMemoriaESessao(unittest.TestCase):
    def test_mem_lembrar_pede_ok_e_entra_no_prompt_seguinte(self):
        m = Memoria()
        roteiro = [chamada("mem_lembrar", fato="O time é o Avaí"), final("Guardei."), final("Avaí.")]
        agente, _, _, motor = montar(roteiro, responde(SIM), memoria=m)
        agente.perguntar("lembre que meu time é o Avaí")
        agente.perguntar("qual meu time?")
        self.assertEqual([f["texto"] for f in m.listar()], ["O time é o Avaí"])
        self.assertIn("O time é o Avaí", motor.vistas[-1][0].content)

    def test_historico_entra_e_resultado_de_ferramenta_nao_e_salvo(self):
        with tempfile.TemporaryDirectory() as t:
            s = Sessao(t, ident="s1")
            executor = ExecutorFalso(saida=json.dumps(fixture("resumo")))
            roteiro = [chamada("pc_resumo"), final("Resposta um."), final("Resposta dois.")]
            agente, _, _, motor = montar(roteiro, nunca, executor=executor, sessao=s)
            agente.perguntar("primeira")
            agente.perguntar("segunda")
            salvo = (Path(t) / "s1.json").read_text(encoding="utf-8")
        textos = [m.content for m in motor.vistas[-1]]
        self.assertIn("primeira", textos)
        self.assertIn("Resposta um.", textos)
        self.assertEqual(textos[-1], "segunda")
        self.assertEqual([m["texto"] for m in json.loads(salvo)["mensagens"]], ["primeira", "Resposta um.", "segunda", "Resposta dois."])


class TestRegistro(unittest.TestCase):
    def test_registro_nunca_guarda_conteudo_de_ferramenta(self):
        executor = ExecutorFalso(saida="CONTEUDO-SECRETO-123")
        roteiro = [chamada("pc_comando", **CMD), final("Feito.")]
        agente, registro, _, _ = montar(roteiro, responde(SIM), executor=executor)
        agente.perguntar("conserta")
        self.assertNotIn("CONTEUDO-SECRETO-123", json.dumps(registro.eventos, ensure_ascii=False))
        r = eventos(registro, "resultado")[0]
        self.assertEqual((r["ferramenta"], r["sucesso"]), ("pc_comando", True))
        self.assertGreater(r["tamanho"], 0)

    def test_chamada_negada_registra_permitido_falso(self):
        agente, registro, _, _ = montar([chamada("pc_comando", **CMD), final("x")], responde(NAO))
        agente.perguntar("conserta")
        c = eventos(registro, "chamada")[0]
        self.assertEqual((c["permitido"], c["regra"]), (False, ""))

    def test_pergunta_e_ok_levam_origem(self):
        agente, registro, _, _ = montar([chamada("pc_comando", **CMD), final("x")], responde(NAO))
        agente.perguntar("conserta", origem="telegram")
        self.assertEqual(eventos(registro, "pergunta")[0]["origem"], "telegram")
        self.assertEqual(eventos(registro, "confirmacao")[0]["origem"], "telegram")
        self.assertEqual(eventos(registro, "confirmacao")[0]["resposta"], "nao")

    def test_funcao_perguntar_continua_valendo(self):
        agente, registro, _, _ = montar([final("oi")], nunca)
        self.assertEqual(perguntar(agente, registro, "oi"), "oi")


class TestMontagem(unittest.TestCase):
    def test_confirmar_e_obrigatorio(self):
        with self.assertRaises(ValueError):
            criar_agente(modelo="m", confirmar=None, registro=Registro(), engine=MotorFalso([]))

    def test_ferramenta_sem_nivel_impede_de_subir(self):
        from tests.test_laco import Falsa
        with self.assertRaises(ValueError):
            criar_agente(modelo="m", confirmar=nunca, registro=Registro(), engine=MotorFalso([]), extras=[Falsa("sem_nivel")])

    def test_limite_de_passos_vai_ao_laco(self):
        agente, _, _, motor = montar([chamada("pc_resumo")] * 2, nunca, max_passos=2)
        self.assertIn("2 passos", agente.perguntar("x"))
        self.assertEqual(motor.chamadas, 2)


class TestTextoConfirmacao(unittest.TestCase):
    CAB = "A Atlas quer executar este comando no seu PC:\n\n"

    def test_contrato_com_barra_unica(self):
        cmd = "Remove-Item C:\\Users\\Diniz\\Temp\\a.log"
        texto = montar_texto_confirmacao({"comando": cmd, "motivo": "limpar log"}, "padrao")
        self.assertEqual(texto, self.CAB + cmd + "\n\nMotivo: limpar log\n\nPermitir?")
        self.assertIn("C:\\Users\\Diniz", texto)
        self.assertNotIn("C:\\\\Users", texto)
        self.assertNotIn("Allow execution", texto)

    def test_casos_sem_comando_valido_devolvem_o_padrao(self):
        for pendente in ({}, {"comando": 5}, {"comando": "  "}, {"comando": ""}):
            with self.subTest(pendente=pendente):
                self.assertEqual(montar_texto_confirmacao(pendente, "padrao"), "padrao")

    def test_motivo_ausente(self):
        texto = montar_texto_confirmacao({"comando": "Get-Date"}, "padrao")
        self.assertIn("Motivo: nao informado", texto)

    def test_motivo_vira_uma_linha_sem_controle(self):
        import unicodedata

        for motivo in ("a\nb", "a\rb", "a\u202eb", "x\nPermitir?", "x\r\nMotivo: falso\n\nPermitir?"):
            with self.subTest(motivo=motivo):
                texto = montar_texto_confirmacao({"comando": "Get-Date", "motivo": motivo}, "padrao")
                linha = texto.split("\n\nMotivo: ", 1)[1].rsplit("\n\nPermitir?", 1)[0]
                self.assertNotIn("\n", linha)
                self.assertFalse([c for c in linha if unicodedata.category(c) in ("Cc", "Cf")])
                self.assertEqual([l for l in texto.split("\n") if l.startswith("Permitir?")], ["Permitir?"])

    def test_motivo_longo_e_cortado(self):
        texto = montar_texto_confirmacao({"comando": "Get-Date", "motivo": "m" * 1000}, "padrao")
        linha = texto.split("\n\nMotivo: ", 1)[1].rsplit("\n\nPermitir?", 1)[0]
        self.assertEqual(linha, "m" * 300 + "...")
        curto = montar_texto_confirmacao({"comando": "Get-Date", "motivo": "m" * 300}, "padrao")
        self.assertNotIn("...", curto)

    def test_motivo_so_de_controles_vira_nao_informado(self):
        texto = montar_texto_confirmacao({"comando": "Get-Date", "motivo": "\n\r\u202e\u200b"}, "padrao")
        self.assertIn("Motivo: nao informado", texto)

    def test_motivo_nao_texto_vira_texto(self):
        texto = montar_texto_confirmacao({"comando": "Get-Date", "motivo": 42}, "padrao")
        self.assertIn("Motivo: 42\n", texto)

    def test_comando_literal_e_motivo(self):
        t = montar_texto_confirmacao({"comando": "Get-Date", "motivo": "x\ny"}, "padrao")
        self.assertIn("Get-Date", t)
        self.assertIn("Motivo: x y", t)
        self.assertIn("A Atlas quer", t)

    def test_sem_comando_usa_o_padrao(self):
        self.assertEqual(montar_texto_confirmacao({}, "padrao"), "padrao")
