import base64
import os
import stat
import tempfile
import unittest

from jarvis_pc.ps import clixml_para_texto, executar_powershell, montar_argv


def decodificar(argv):
    return base64.b64decode(argv[-1]).decode("utf-16-le")


class TestMontarArgv(unittest.TestCase):
    def test_comando_codificado_contem_o_script(self):
        argv = montar_argv("Get-Date", json=True)
        self.assertEqual(argv[0], "powershell")
        self.assertIn("-NoProfile", argv)
        self.assertIn("-EncodedCommand", argv)
        self.assertIn("Get-Date", decodificar(argv))

    def test_modo_json_escapa_o_que_nao_e_ascii(self):
        texto = decodificar(montar_argv("Get-Date", json=True))
        self.assertIn("ConvertTo-Json", texto)
        self.assertIn("\\u{0:x4}", texto)

    def test_modo_texto_usa_saida_utf8_e_nao_converte_json(self):
        texto = decodificar(montar_argv("Get-Date", json=False))
        self.assertIn("UTF8Encoding", texto)
        self.assertNotIn("ConvertTo-Json", texto)

    def test_percentual_no_script_nao_quebra_a_montagem(self):
        self.assertIn("%{ $_ }", decodificar(montar_argv("1 | %{ $_ }")))


class TestExecutar(unittest.TestCase):
    def test_executavel_inexistente_nao_levanta_erro(self):
        r = executar_powershell("x", exe="nao-existe-xyz-123")
        self.assertEqual(r.codigo, -1)
        self.assertIn("não encontrado", r.erro)

    def test_executavel_sem_permissao_nao_levanta_erro(self):
        with tempfile.TemporaryDirectory() as pasta:
            sem_permissao = os.path.join(pasta, "ps-sem-permissao")
            with open(sem_permissao, "w") as f:
                f.write("#!/bin/sh\necho ok\n")
            r = executar_powershell("x", exe=sem_permissao)
        self.assertEqual(r.codigo, -1)
        self.assertIn("não foi possível executar", r.erro)

    def test_tempo_esgotado_nao_levanta_erro(self):
        with tempfile.TemporaryDirectory() as pasta:
            falso = os.path.join(pasta, "ps-falso")
            with open(falso, "w") as f:
                f.write("#!/bin/sh\nsleep 5\n")
            os.chmod(falso, os.stat(falso).st_mode | stat.S_IEXEC)
            r = executar_powershell("x", exe=falso, timeout=0.3)
        self.assertEqual(r.codigo, -1)
        self.assertIn("tempo esgotado", r.erro)

    def test_stdout_fora_de_utf8_tambem_e_decodificado_sem_erro(self):
        with tempfile.TemporaryDirectory() as pasta:
            falso = os.path.join(pasta, "ps-falso")
            with open(falso, "w") as f:
                f.write("#!/bin/sh\nprintf 'ok\\242'\n")
            os.chmod(falso, os.stat(falso).st_mode | stat.S_IEXEC)
            r = executar_powershell("x", exe=falso)
        self.assertEqual(r.codigo, 0)
        self.assertTrue(r.saida.startswith("ok"))

    def test_saida_fora_de_utf8_e_decodificada_sem_erro(self):
        with tempfile.TemporaryDirectory() as pasta:
            falso = os.path.join(pasta, "ps-falso")
            with open(falso, "w") as f:
                f.write("#!/bin/sh\nprintf 'ok\\242\\n' >&2\nprintf '{}'\n")
            os.chmod(falso, os.stat(falso).st_mode | stat.S_IEXEC)
            r = executar_powershell("x", exe=falso)
        self.assertEqual(r.codigo, 0)
        self.assertEqual(r.saida, "{}")
        self.assertIn("ok", r.erro)


if __name__ == "__main__":
    unittest.main()


REAL = (
    '#< CLIXML\r\n<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04">'
    '<S S="Error">Restart-Service : O servico \'Spooler\' nao pode ser interrompido _x000D__x000A_</S>'
    '<S S="Error">No linha:4 caractere:1_x000D__x000A_</S></Objs>'
)


class TestClixml(unittest.TestCase):
    def test_exemplo_real_vira_texto_legivel(self):
        self.assertEqual(
            clixml_para_texto(REAL),
            "Restart-Service : O servico 'Spooler' nao pode ser interrompido\nNo linha:4 caractere:1",
        )

    def test_texto_comum_passa_intacto(self):
        self.assertEqual(clixml_para_texto("erro simples"), "erro simples")

    def test_ignora_fluxos_que_nao_sao_erro(self):
        xml = '#< CLIXML\n<Objs xmlns="x"><S S="progress">lixo</S><S S="Error">ruim_x000A_</S></Objs>'
        self.assertEqual(clixml_para_texto(xml), "ruim")

    def test_xml_quebrado_devolve_o_original(self):
        self.assertEqual(clixml_para_texto("#< CLIXML\n<Objs"), "#< CLIXML\n<Objs")

    def test_executar_converte_o_stderr(self):
        with tempfile.TemporaryDirectory() as pasta:
            falso = os.path.join(pasta, "ps-falso")
            with open(falso, "w") as f:
                f.write("#!/bin/sh\nprintf '%s' '" + REAL.replace("'", "'\\''") + "' >&2\nexit 1\n")
            os.chmod(falso, os.stat(falso).st_mode | stat.S_IXUSR)
            r = executar_powershell("x", exe=falso)
        self.assertNotIn("CLIXML", r.erro)
        self.assertIn("nao pode ser interrompido", r.erro)
