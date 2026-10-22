import json
import tempfile
import unittest
from pathlib import Path

from jarvis_pc.memoria import LIMITE_FATOS, Memoria, criar_ferramentas_memoria


class TestMemoria(unittest.TestCase):
    def test_lembra_lista_e_persiste(self):
        with tempfile.TemporaryDirectory() as t:
            c = Path(t) / "memoria.json"
            m = Memoria(c)
            f = m.lembrar("  O servidor do FloripaOT é a VM 301  ")
            self.assertEqual(f["texto"], "O servidor do FloripaOT é a VM 301")
            self.assertEqual(f["id"], 1)
            self.assertEqual([x["texto"] for x in Memoria(c).listar()], ["O servidor do FloripaOT é a VM 301"])
            self.assertEqual(json.loads(c.read_text(encoding="utf-8"))["fatos"][0]["id"], 1)

    def test_repetido_nao_duplica(self):
        m = Memoria()
        m.lembrar("Time: Avaí")
        m.lembrar("time: avaí")
        self.assertEqual(len(m.listar()), 1)

    def test_texto_invalido(self):
        m = Memoria()
        for texto in ("", "   ", None, 5, "x" * 301):
            with self.subTest(texto=texto):
                with self.assertRaises(ValueError):
                    m.lembrar(texto)

    def test_limite_de_fatos(self):
        m = Memoria()
        for i in range(LIMITE_FATOS):
            m.lembrar(f"fato {i}")
        with self.assertRaises(ValueError):
            m.lembrar("um a mais")

    def test_ids_nao_se_repetem_depois_de_apagar(self):
        m = Memoria()
        m.lembrar("a1")
        b = m.lembrar("b2")
        m.esquecer(b["id"])
        self.assertEqual(m.lembrar("c3")["id"], 3)

    def test_esquece_por_id_ou_trecho(self):
        m = Memoria()
        m.lembrar("O time é o Avaí")
        m.lembrar("A VM 301 é produção")
        self.assertEqual(m.esquecer("2")["texto"], "A VM 301 é produção")
        self.assertEqual(m.esquecer("avai")["texto"], "O time é o Avaí")
        self.assertEqual(m.listar(), [])

    def test_trecho_ambiguo_lista_e_nao_apaga(self):
        m = Memoria()
        m.lembrar("VM 301 é produção")
        m.lembrar("VM 110 é bancada")
        with self.assertRaises(ValueError) as e:
            m.esquecer("VM")
        self.assertIn("VM 301", str(e.exception))
        self.assertIn("VM 110", str(e.exception))
        self.assertEqual(len(m.listar()), 2)

    def test_nao_achou(self):
        with self.assertRaises(ValueError):
            Memoria().esquecer("nada")

    def test_arquivo_corrompido_vira_memoria_vazia_sem_apagar_o_arquivo(self):
        with tempfile.TemporaryDirectory() as t:
            c = Path(t) / "memoria.json"
            c.write_text("{quebrado", encoding="utf-8")
            m = Memoria(c)
            self.assertEqual(m.listar(), [])
            with self.assertRaises(ValueError):
                m.lembrar("x1")
            self.assertEqual(c.read_text(encoding="utf-8"), "{quebrado")

    def test_para_prompt(self):
        m = Memoria()
        self.assertEqual(m.para_prompt(), "")
        m.lembrar("O time é o Avaí")
        self.assertEqual(m.para_prompt(), "Fatos que o Matheus pediu para lembrar:\n- [1] O time é o Avaí")


class TestFerramentas(unittest.TestCase):
    def test_lembrar_e_esquecer(self):
        m = Memoria()
        lembrar, esquecer = criar_ferramentas_memoria(m)
        self.assertEqual((lembrar.spec.name, esquecer.spec.name), ("mem_lembrar", "mem_esquecer"))
        r = lembrar.execute(fato="O time é o Avaí")
        self.assertTrue(r.success)
        self.assertIn("[1]", r.content)
        r = esquecer.execute(fato="1")
        self.assertTrue(r.success)
        self.assertEqual(m.listar(), [])

    def test_falha_vira_resultado_sem_sucesso(self):
        lembrar, esquecer = criar_ferramentas_memoria(Memoria())
        self.assertFalse(lembrar.execute(fato="").success)
        self.assertFalse(esquecer.execute(fato="nada").success)
