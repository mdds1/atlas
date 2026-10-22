# Jarvis: inventário exato deste PC (etapa 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Jarvis passa a saber, de forma exata e consultável, todos os arquivos, apps, dependências, serviços, tarefas e itens de inicialização do PC do Matheus, e a responder perguntas sobre isso com número vindo de um banco local, não de estimativa do modelo.

**Architecture:** Um subpacote `jarvis_pc.inventario` com um banco SQLite local (stdlib). Três coletores o alimentam: varredura de arquivos (`os.scandir` com poda), coleta do sistema (um script PowerShell que devolve JSON) e coleta de pacotes (lê pastas `*.dist-info`, sem executar nada). Seis ferramentas somente leitura expõem consultas fixas ao agente (o modelo nunca escreve SQL). Regras de exclusão (fotos em `E:\`, `Fotos & Videos`, `AppData`, segredos) são aplicadas na coleta, então o que é excluído nunca chega ao banco.

**Tech Stack:** Python 3.10 (o do PC), `sqlite3`, `os.scandir`, `threading`, `unittest` (como o resto do projeto), PowerShell 5.1 pelo `executar_powershell` existente. Nenhuma dependência nova.

## Global Constraints

- Português do Brasil em todo texto que o usuário ou o modelo vê. **Sem em-dash e sem emoji.**
- Testes com `unittest`, rodados por `.venv/bin/python -B -m unittest discover -s tests -q` (hoje 106 passam). Nada de `pytest`, que não está instalado.
- Estilo do código existente: docstring curta em português no topo do módulo, `@dataclass(frozen=True)`, sem tipagem pesada, ferramentas como subclasses de `BaseTool` com `ToolSpec` e `ToolResult`, resultado com o `AVISO` de "dados, não instruções".
- **Somente leitura sobre os arquivos do Matheus.** O único arquivo que este pacote grava é o seu próprio banco (`inventario.db`, na pasta da instalação). Nenhum `Remove-Item`, `Set-Content` ou escrita fora do banco.
- Regras de exclusão (spec, "Revisão", item 5): fica de fora `E:\Fotos & Videos` inteira; fica de fora qualquer foto em `E:\` (`.jpg .jpeg .png .gif .bmp .webp .heic .heif .tif .tiff .raw .cr2 .nef .dng`) **exceto** sob `E:\FORWARD`; `AppData` entra só como inventário de apps, sem conteúdo; nunca entram `.env`, `*.pem`, `*.key`, `id_rsa*`, `*.kdbx`, `*.ppk`, `cookies`, `Login Data`, pastas `.ssh`, `.aws`, `.gnupg`, e arquivo cujo nome contenha `senha`, `password`, `token`, `secret`, `credencial` ou `credential`. Arquivo excluído não entra nem pelo nome.
- O registro (`registro.jsonl`) guarda ferramenta, argumentos e tamanho; **nunca o conteúdo** de arquivo. O inventário devolve caminhos e números, nunca conteúdo.
- Toda resposta de ferramenta começa com `AVISO` e cita a data da varredura que a originou.
- Cada regra de exclusão e cada regra de somente leitura é conferida por **mutação** (`tools/mutar.py`): sabotar a regra precisa fazer um teste falhar.
- Commits em português, no formato `tipo(jarvis): resumo`, terminando com a linha `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Branch `main`, repositório local sem remoto.

## File Structure

Criar:
- `src/jarvis_pc/inventario/__init__.py`: vazio com docstring.
- `src/jarvis_pc/inventario/exclusoes.py`: classe `Exclusoes`, a única fonte das regras acima.
- `src/jarvis_pc/inventario/banco.py`: classe `Banco` (esquema, gravação por lote, varreduras, consulta).
- `src/jarvis_pc/inventario/arquivos.py`: `varrer_arquivos`.
- `src/jarvis_pc/inventario/sistema.py`: `coletar_sistema` (apps, serviços, tarefas, inicialização, caminhos de Python e npm).
- `src/jarvis_pc/inventario/pacotes.py`: `coletar_pacotes` (lê `*.dist-info` e `package.json`).
- `src/jarvis_pc/inventario/consultas.py`: consultas fixas que devolvem texto.
- `src/jarvis_pc/inventario/atualizador.py`: `Atualizador` (roda as três coletas numa thread).
- `src/jarvis_pc/inventario/ferramentas.py`: as seis ferramentas e `montar_inventario`.
- `src/jarvis_pc/ps/inventario_sistema.ps1`: script PowerShell da coleta do sistema.
- `tests/test_inventario_exclusoes.py`, `test_inventario_banco.py`, `test_inventario_arquivos.py`, `test_inventario_sistema.py`, `test_inventario_pacotes.py`, `test_inventario_consultas.py`, `test_inventario_atualizador.py`, `test_inventario_ferramentas.py`.
- `tests/fixtures/inventario_sistema.json`.
- `docs/medicoes-inventario.md`: números medidos no PC.

Modificar:
- `src/jarvis_pc/config.py` e `tests/test_config.py`: três campos novos.
- `src/jarvis_pc/agente.py`: parâmetro `extras`.
- `src/jarvis_pc/prompt.py` e `tests/test_prompt.py`: regra sobre o inventário.
- `src/jarvis_pc/__main__.py` e `tests/test_main.py`: montar o inventário e atualizar ao abrir.
- `src/jarvis_pc/cenarios.py` e `tests/test_cenarios.py`: seis cenários novos.
- `docs/superpowers/specs/2026-10-15-jarvis-design.md`: estado.

## Convenções de dados usadas em todas as tarefas

- Caminhos ficam no banco como o Windows os entrega (`C:\Jarvis\venv\pyvenv.cfg`), com barra invertida. A comparação é sempre sem diferenciar maiúscula de minúscula.
- `modificado` é `st_mtime` (segundos desde 1970, `float`). `tamanho` é inteiro em bytes.
- `ext` é minúscula com ponto (`.py`) ou `""` quando não há.
- Tipos de varredura: `"arquivos"`, `"sistema"`, `"pacotes"`. Estados: `"rodando"`, `"ok"`, `"cancelada"`, `"falhou"`.

---

### Task 1: Três campos novos na configuração

**Files:**
- Modify: `src/jarvis_pc/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config.inventario: str = "inventario.db"`, `Config.raizes: tuple = ("C:\\", "E:\\")`, `Config.atualizar_ao_abrir: bool = True`. `carregar()` converte a lista JSON de `raizes` em tupla.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim da classe `TestConfig` em `tests/test_config.py`:

```python
    def test_padroes_do_inventario(self):
        c = Config()
        self.assertEqual(c.inventario, "inventario.db")
        self.assertEqual(c.raizes, ("C:\\", "E:\\"))
        self.assertIs(c.atualizar_ao_abrir, True)

    def test_raizes_vem_como_lista_e_viram_tupla(self):
        pasta, caminho = com_arquivo('{"raizes": ["C:\\\\", "D:\\\\"], "atualizar_ao_abrir": false}')
        with pasta:
            c = carregar(caminho)
        self.assertEqual(c.raizes, ("C:\\", "D:\\"))
        self.assertIs(c.atualizar_ao_abrir, False)

    def test_raizes_invalidas_sao_recusadas(self):
        for texto in ('{"raizes": []}', '{"raizes": "C:\\\\"}', '{"raizes": ["C:\\\\", ""]}', '{"raizes": [1]}'):
            with self.subTest(texto=texto):
                pasta, caminho = com_arquivo(texto)
                with pasta:
                    with self.assertRaises(ValueError):
                        carregar(caminho)

    def test_atualizar_ao_abrir_so_aceita_booleano(self):
        pasta, caminho = com_arquivo('{"atualizar_ao_abrir": "sim"}')
        with pasta:
            with self.assertRaises(ValueError):
                carregar(caminho)

    def test_nome_do_banco_precisa_ser_texto_nao_vazio(self):
        pasta, caminho = com_arquivo('{"inventario": ""}')
        with pasta:
            with self.assertRaises(ValueError):
                carregar(caminho)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -B -m unittest tests.test_config -q`
Expected: FAIL com `AttributeError: ... has no attribute 'inventario'`.

- [ ] **Step 3: Implementar**

Em `src/jarvis_pc/config.py`, troque a classe e a validação por:

```python
@dataclass(frozen=True)
class Config:
    modelo: str = "gemma4:12b-it-q4_K_M"
    host: str = "http://localhost:11434"
    registro: str = "registro.jsonl"
    tecla: str = "J"
    tempo_confirmacao: float = 120.0
    inventario: str = "inventario.db"
    raizes: tuple = ("C:\\", "E:\\")
    atualizar_ao_abrir: bool = True
```

e, dentro de `_validar`, troque `for campo in ("modelo", "host", "registro"):` por `for campo in ("modelo", "host", "registro", "inventario"):`, e antes do `return`:

```python
    raizes = config.raizes
    if (
        not isinstance(raizes, (list, tuple))
        or not raizes
        or not all(isinstance(r, str) and r.strip() for r in raizes)
    ):
        raise erro("raizes deve ser uma lista não vazia de textos (por exemplo, [\"C:\\\\\", \"E:\\\\\"])")
    if not isinstance(config.atualizar_ao_abrir, bool):
        raise erro("atualizar_ao_abrir deve ser verdadeiro ou falso")
    return replace(config, tecla=tecla.upper(), raizes=tuple(raizes))
```

(remova o `return replace(config, tecla=tecla.upper())` antigo.)

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -B -m unittest tests.test_config -q`
Expected: PASS.

- [ ] **Step 5: Mutação**

Run: `.venv/bin/python tools/mutar.py src/jarvis_pc/config.py "isinstance(config.atualizar_ao_abrir, bool)" "True"`
Expected: saída 0 (a sabotagem foi pega). Se sair 1, o teste `test_atualizar_ao_abrir_so_aceita_booleano` está fraco: corrija antes de seguir.

- [ ] **Step 6: Commit**

```bash
git add src/jarvis_pc/config.py tests/test_config.py
git commit -m "feat(jarvis): campos do inventario na configuracao

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Regras de exclusão

**Files:**
- Create: `src/jarvis_pc/inventario/__init__.py`, `src/jarvis_pc/inventario/exclusoes.py`
- Test: `tests/test_inventario_exclusoes.py`

**Interfaces:**
- Produces: `Exclusoes(raiz_fotos="E:\\", pasta_vetada="E:\\Fotos & Videos", pasta_livre="E:\\FORWARD")` com `pasta_podada(caminho) -> bool` e `arquivo_excluido(caminho) -> bool`. Constantes `FOTOS`, `PASTAS_SEGREDO`, `PASTAS_RUIDO`, `PADROES_NOME`, `PALAVRAS_NOME`. Funções `normalizar(caminho) -> str` e `dentro(caminho, base) -> bool`, usadas depois pelas consultas.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_inventario_exclusoes.py`:

```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -B -m unittest tests.test_inventario_exclusoes -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'jarvis_pc.inventario'`.

- [ ] **Step 3: Implementar**

`src/jarvis_pc/inventario/__init__.py`:

```python
"""Inventário exato do PC: arquivos, apps, dependências, serviços e tarefas."""
```

`src/jarvis_pc/inventario/exclusoes.py`:

```python
"""O que nunca entra no inventário. É a única fonte dessas regras.

Decididas pelo Matheus em 21/10/2026: a pasta E:\\Fotos & Videos inteira e
qualquer foto em E:\\ ficam de fora (exceto sob E:\\FORWARD); AppData entra só
como inventário de apps; segredos nunca entram. Arquivo excluído não aparece
nem pelo nome. As comparações ignoram maiúscula e aceitam / ou \\.
"""
import fnmatch
from dataclasses import dataclass

FOTOS = frozenset(
    {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".heif", ".tif", ".tiff", ".raw", ".cr2", ".nef", ".dng"}
)
PASTAS_SEGREDO = frozenset({".ssh", ".aws", ".gnupg"})
PASTAS_RUIDO = frozenset({"$recycle.bin", "system volume information"})
PADROES_NOME = ("*.pem", "*.key", "*.kdbx", "*.ppk", "id_rsa*", ".env", ".env.*", "cookies", "login data")
PALAVRAS_NOME = ("senha", "password", "token", "secret", "credencial", "credential")


def normalizar(caminho):
    return str(caminho).replace("/", "\\").rstrip("\\").lower()


def dentro(caminho, base):
    c, b = normalizar(caminho), normalizar(base)
    return c == b or c.startswith(b + "\\")


@dataclass(frozen=True)
class Exclusoes:
    raiz_fotos: str = "E:\\"
    pasta_vetada: str = "E:\\Fotos & Videos"
    pasta_livre: str = "E:\\FORWARD"

    def pasta_podada(self, caminho):
        if dentro(caminho, self.pasta_vetada):
            return True
        partes = normalizar(caminho).split("\\")
        return any(p == "appdata" or p in PASTAS_SEGREDO or p in PASTAS_RUIDO for p in partes)

    def arquivo_excluido(self, caminho):
        n = normalizar(caminho)
        pasta, _, nome = n.rpartition("\\")
        if self.pasta_podada(pasta):
            return True
        if any(fnmatch.fnmatchcase(nome, p) for p in PADROES_NOME):
            return True
        if any(palavra in nome for palavra in PALAVRAS_NOME):
            return True
        ext = "." + nome.rpartition(".")[2] if "." in nome else ""
        return ext in FOTOS and dentro(n, self.raiz_fotos) and not dentro(n, self.pasta_livre)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -B -m unittest tests.test_inventario_exclusoes -q`
Expected: PASS.

- [ ] **Step 5: Mutação (obrigatória, uma por regra)**

Rode cada linha; todas precisam sair com código 0.

```bash
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/exclusoes.py "and not dentro(n, self.pasta_livre)" ""
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/exclusoes.py "and dentro(n, self.raiz_fotos)" ""
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/exclusoes.py 'if dentro(caminho, self.pasta_vetada):' 'if False:'
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/exclusoes.py 'p == "appdata" or ' ''
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/exclusoes.py 'if any(palavra in nome for palavra in PALAVRAS_NOME):' 'if False:'
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/exclusoes.py 'if any(fnmatch.fnmatchcase(nome, p) for p in PADROES_NOME):' 'if False:'
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/exclusoes.py 'return c == b or c.startswith(b + "\\")' 'return c.startswith(b)'
```

Se alguma sair com 1 (escapou), acrescente o teste que falta em `test_inventario_exclusoes.py` e rode de novo.

- [ ] **Step 6: Commit**

```bash
git add src/jarvis_pc/inventario tests/test_inventario_exclusoes.py
git commit -m "feat(jarvis): regras de exclusao do inventario

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: O banco

**Files:**
- Create: `src/jarvis_pc/inventario/banco.py`
- Test: `tests/test_inventario_banco.py`

**Interfaces:**
- Consumes: nada.
- Produces: `Banco(caminho=":memory:")` com
  - `iniciar_varredura(tipo, agora) -> int`
  - `gravar(tabela, vid, linhas) -> None` (cada linha é dict ou tupla na ordem de `TABELAS[tabela]`)
  - `progresso(vid, itens) -> None`
  - `encerrar_varredura(vid, estado, erros, agora) -> None` (só estado `"ok"` apaga as linhas de varreduras antigas do tipo)
  - `ultima_varredura(tipo) -> dict | None` com `id, tipo, inicio, fim, itens, erros, estado` (a última com estado `ok`)
  - `em_andamento() -> list[dict]`
  - `consultar(sql, params=()) -> list[sqlite3.Row]`
  - `definir_hash(caminho, valor) -> None`
  - constantes `TABELAS`, `DONAS`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_inventario_banco.py`:

```python
import unittest

from jarvis_pc.inventario.banco import Banco, TABELAS


def arq(caminho, tamanho=10, modificado=1.0):
    nome = caminho.rpartition("\\")[2]
    ext = "." + nome.rpartition(".")[2].lower() if "." in nome else ""
    return (caminho, nome, ext, caminho.rpartition("\\")[0], tamanho, modificado)


class TestBanco(unittest.TestCase):
    def setUp(self):
        self.b = Banco()

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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -B -m unittest tests.test_inventario_banco -q`
Expected: FAIL com `ModuleNotFoundError: ... banco`.

- [ ] **Step 3: Implementar**

`src/jarvis_pc/inventario/banco.py`:

```python
"""Banco SQLite do inventário. Só o inventário grava aqui; nada do usuário.

Cada coleta grava as linhas novas com o número da sua varredura. Só quando ela
termina bem (estado "ok") as linhas de varreduras antigas do mesmo tipo são
apagadas; uma coleta cancelada ou que falhou não destrói o que já existia.
"""
import sqlite3
import threading

TABELAS = {
    "arquivos": ("caminho", "nome", "ext", "pasta", "tamanho", "modificado"),
    "apps": ("origem", "nome", "versao", "editor", "local"),
    "servicos": ("nome", "exibicao", "estado", "inicio"),
    "tarefas": ("caminho", "nome", "estado"),
    "inicializacao": ("nome", "comando", "local"),
    "pacotes": ("ambiente", "nome", "versao"),
}
DONAS = {
    "arquivos": ("arquivos",),
    "sistema": ("apps", "servicos", "tarefas", "inicializacao"),
    "pacotes": ("pacotes",),
}

ESQUEMA = """
CREATE TABLE IF NOT EXISTS varreduras (
  id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, inicio REAL, fim REAL,
  itens INTEGER DEFAULT 0, erros INTEGER DEFAULT 0, estado TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS arquivos (
  caminho TEXT PRIMARY KEY, nome TEXT, ext TEXT, pasta TEXT, tamanho INTEGER,
  modificado REAL, hash TEXT, varredura INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS ix_arquivos_nome ON arquivos(nome);
CREATE INDEX IF NOT EXISTS ix_arquivos_ext ON arquivos(ext);
CREATE INDEX IF NOT EXISTS ix_arquivos_tamanho ON arquivos(tamanho);
CREATE TABLE IF NOT EXISTS apps (origem TEXT, nome TEXT, versao TEXT, editor TEXT, local TEXT, varredura INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS servicos (nome TEXT, exibicao TEXT, estado TEXT, inicio TEXT, varredura INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS tarefas (caminho TEXT, nome TEXT, estado TEXT, varredura INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS inicializacao (nome TEXT, comando TEXT, local TEXT, varredura INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS pacotes (ambiente TEXT, nome TEXT, versao TEXT, varredura INTEGER NOT NULL);
"""

UPSERT_ARQUIVOS = """
INSERT INTO arquivos (caminho, nome, ext, pasta, tamanho, modificado, varredura)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(caminho) DO UPDATE SET
  nome = excluded.nome, ext = excluded.ext, pasta = excluded.pasta,
  hash = CASE WHEN arquivos.tamanho = excluded.tamanho AND arquivos.modificado = excluded.modificado
              THEN arquivos.hash ELSE NULL END,
  tamanho = excluded.tamanho, modificado = excluded.modificado, varredura = excluded.varredura
"""


def _linha(colunas, linha):
    if isinstance(linha, dict):
        return tuple(linha.get(c) for c in colunas)
    return tuple(linha)


class Banco:
    def __init__(self, caminho=":memory:"):
        self._con = sqlite3.connect(str(caminho), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._trava = threading.RLock()
        with self._trava:
            self._con.executescript(ESQUEMA)
            self._con.execute("UPDATE varreduras SET estado = 'falhou' WHERE estado = 'rodando'")
            self._con.commit()

    def fechar(self):
        with self._trava:
            self._con.close()

    def iniciar_varredura(self, tipo, agora):
        if tipo not in DONAS:
            raise ValueError(f"tipo de varredura desconhecido: {tipo}")
        with self._trava:
            cur = self._con.execute(
                "INSERT INTO varreduras (tipo, inicio, estado) VALUES (?, ?, 'rodando')", (tipo, agora)
            )
            self._con.commit()
            return cur.lastrowid

    def gravar(self, tabela, vid, linhas):
        if tabela not in TABELAS:
            raise ValueError(f"tabela desconhecida: {tabela}")
        colunas = TABELAS[tabela]
        dados = [_linha(colunas, l) + (vid,) for l in linhas]
        with self._trava:
            if tabela == "arquivos":
                self._con.executemany(UPSERT_ARQUIVOS, dados)
            else:
                marcas = ", ".join("?" for _ in range(len(colunas) + 1))
                self._con.executemany(
                    f"INSERT INTO {tabela} ({', '.join(colunas)}, varredura) VALUES ({marcas})", dados
                )
            self._con.commit()

    def progresso(self, vid, itens):
        with self._trava:
            self._con.execute("UPDATE varreduras SET itens = ? WHERE id = ?", (itens, vid))
            self._con.commit()

    def encerrar_varredura(self, vid, estado, erros, agora):
        with self._trava:
            tipo = self._con.execute("SELECT tipo FROM varreduras WHERE id = ?", (vid,)).fetchone()["tipo"]
            self._con.execute(
                "UPDATE varreduras SET estado = ?, erros = ?, fim = ? WHERE id = ?", (estado, erros, agora, vid)
            )
            if estado == "ok":
                for tabela in DONAS[tipo]:
                    self._con.execute(f"DELETE FROM {tabela} WHERE varredura <> ?", (vid,))
            self._con.commit()

    def ultima_varredura(self, tipo):
        with self._trava:
            r = self._con.execute(
                "SELECT * FROM varreduras WHERE tipo = ? AND estado = 'ok' ORDER BY id DESC LIMIT 1", (tipo,)
            ).fetchone()
            return dict(r) if r else None

    def em_andamento(self):
        with self._trava:
            return [dict(r) for r in self._con.execute("SELECT * FROM varreduras WHERE estado = 'rodando'")]

    def definir_hash(self, caminho, valor):
        with self._trava:
            self._con.execute("UPDATE arquivos SET hash = ? WHERE caminho = ?", (valor, caminho))
            self._con.commit()

    def consultar(self, sql, params=()):
        with self._trava:
            return self._con.execute(sql, params).fetchall()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -B -m unittest tests.test_inventario_banco -q`
Expected: PASS.

- [ ] **Step 5: Mutação**

```bash
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/banco.py 'if estado == "ok":' 'if True:'
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/banco.py 'THEN arquivos.hash ELSE NULL END' 'THEN NULL ELSE NULL END'
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/banco.py "AND estado = 'ok' ORDER BY" "ORDER BY"
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/banco.py "UPDATE varreduras SET estado = 'falhou' WHERE estado = 'rodando'" "SELECT 1"
```
Todas devem sair com 0.

- [ ] **Step 6: Commit**

```bash
git add src/jarvis_pc/inventario/banco.py tests/test_inventario_banco.py
git commit -m "feat(jarvis): banco SQLite do inventario

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Varredura de arquivos

**Files:**
- Create: `src/jarvis_pc/inventario/arquivos.py`
- Test: `tests/test_inventario_arquivos.py`

**Interfaces:**
- Consumes: `Exclusoes.pasta_podada/arquivo_excluido` (Task 2), `Banco.iniciar_varredura/gravar/progresso/encerrar_varredura` (Task 3).
- Produces: `ResultadoVarredura(id, arquivos, erros, segundos, estado)` e `varrer_arquivos(banco, raizes, exclusoes, *, agora=time.time, cancelado=lambda: False, lote=2000) -> ResultadoVarredura`. Não segue links simbólicos nem pontos de reparse (junções do Windows).

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_inventario_arquivos.py`:

```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -B -m unittest tests.test_inventario_arquivos -q`
Expected: FAIL com `ImportError: cannot import name 'arquivos'`.

- [ ] **Step 3: Implementar**

`src/jarvis_pc/inventario/arquivos.py`:

```python
"""Varredura dos arquivos: percorre as raízes, poda o que é excluído e grava no banco.

Lê só metadados (nome, tamanho, data); nunca abre um arquivo. Não segue link
simbólico nem ponto de reparse (junção do Windows), para não entrar em laço nem
em pasta do sistema que aponta para outra.
"""
import os
import time
from dataclasses import dataclass

REPARSE = 0x400


@dataclass(frozen=True)
class ResultadoVarredura:
    id: int
    arquivos: int
    erros: int
    segundos: float
    estado: str


def _reparse(entrada):
    return bool(getattr(entrada.stat(follow_symlinks=False), "st_file_attributes", 0) & REPARSE)


def _extensao(nome):
    return "." + nome.rpartition(".")[2].lower() if "." in nome.lstrip(".") else ""


def varrer_arquivos(banco, raizes, exclusoes, *, agora=time.time, cancelado=lambda: False, lote=2000):
    inicio = agora()
    vid = banco.iniciar_varredura("arquivos", inicio)
    pilha = list(raizes)
    pendentes, total, erros = [], 0, 0
    estado = "ok"
    try:
        while pilha:
            if cancelado():
                estado = "cancelada"
                break
            pasta = pilha.pop()
            if exclusoes.pasta_podada(pasta):
                continue
            try:
                with os.scandir(pasta) as it:
                    entradas = list(it)
            except OSError:
                erros += 1
                continue
            for e in entradas:
                try:
                    if e.is_symlink() or _reparse(e):
                        continue
                    if e.is_dir(follow_symlinks=False):
                        pilha.append(e.path)
                        continue
                    if not e.is_file(follow_symlinks=False) or exclusoes.arquivo_excluido(e.path):
                        continue
                    st = e.stat(follow_symlinks=False)
                except OSError:
                    erros += 1
                    continue
                pendentes.append((e.path, e.name, _extensao(e.name), pasta, st.st_size, st.st_mtime))
                if len(pendentes) >= lote:
                    banco.gravar("arquivos", vid, pendentes)
                    total += len(pendentes)
                    pendentes = []
                    banco.progresso(vid, total)
        if pendentes:
            banco.gravar("arquivos", vid, pendentes)
            total += len(pendentes)
        banco.progresso(vid, total)
    except Exception:
        banco.encerrar_varredura(vid, "falhou", erros, agora())
        raise
    fim = agora()
    banco.encerrar_varredura(vid, estado, erros, fim)
    return ResultadoVarredura(vid, total, erros, fim - inicio, estado)
```

Nota para quem implementa: `_extensao(".env")` devolve `""` de propósito (arquivo que só tem ponto no começo não tem extensão); `.env` já é excluído de qualquer jeito.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -B -m unittest tests.test_inventario_arquivos -q`
Expected: PASS (o teste de link simbólico pode ser `skipped` no Windows sem privilégio).

- [ ] **Step 5: Mutação**

```bash
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/arquivos.py "or exclusoes.arquivo_excluido(e.path)" ""
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/arquivos.py "if exclusoes.pasta_podada(pasta):" "if False:"
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/arquivos.py "e.is_symlink() or _reparse(e)" "False"
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/arquivos.py "if cancelado():" "if False:"
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/arquivos.py "& REPARSE" "& 0"
```
Todas devem sair com 0. (A terceira pode escapar no Linux se o teste de link for pulado: nesse caso o teste de `_reparse` cobre só a função; acrescente um teste que injeta uma `Entrada` falsa com `is_symlink()` verdadeiro, ou rode a mutação no PC.)

- [ ] **Step 6: Commit**

```bash
git add src/jarvis_pc/inventario/arquivos.py tests/test_inventario_arquivos.py
git commit -m "feat(jarvis): varredura de arquivos do inventario

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Coleta do sistema (apps, serviços, tarefas, inicialização)

**Files:**
- Create: `src/jarvis_pc/ps/inventario_sistema.ps1`, `src/jarvis_pc/inventario/sistema.py`, `tests/fixtures/inventario_sistema.json`
- Test: `tests/test_inventario_sistema.py`

**Interfaces:**
- Consumes: `Banco` (Task 3); `executar_powershell(script, *, timeout, json) -> ResultadoPS` (já existe); `ler_script(nome)` de `jarvis_pc.leitura`.
- Produces: `ResultadoColeta(ok, motivo, pythons, npm, itens)` e `coletar_sistema(banco, executor=executar_powershell, agora=time.time) -> ResultadoColeta`. `pythons` é lista de pastas de instalação do Python; `npm` é a pasta `node_modules` global (texto ou `""`).

- [ ] **Step 1: Escrever o script PowerShell**

`src/jarvis_pc/ps/inventario_sistema.ps1`:

```powershell
$reg = @(
  'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
  'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
  'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*')
$apps = @(Get-ItemProperty $reg -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName } | ForEach-Object {
  [pscustomobject]@{ origem = 'registro'; nome = [string]$_.DisplayName; versao = [string]$_.DisplayVersion; editor = [string]$_.Publisher; local = [string]$_.InstallLocation } })
$apps += @(Get-AppxPackage -ErrorAction SilentlyContinue | ForEach-Object {
  [pscustomobject]@{ origem = 'loja'; nome = [string]$_.Name; versao = [string]$_.Version; editor = [string]$_.Publisher; local = [string]$_.InstallLocation } })
$servicos = @(Get-CimInstance Win32_Service | ForEach-Object {
  [pscustomobject]@{ nome = [string]$_.Name; exibicao = [string]$_.DisplayName; estado = [string]$_.State; inicio = [string]$_.StartMode } })
$tarefas = @(Get-ScheduledTask -ErrorAction SilentlyContinue | ForEach-Object {
  [pscustomobject]@{ caminho = [string]$_.TaskPath; nome = [string]$_.TaskName; estado = [string]$_.State } })
$inicializacao = @(Get-CimInstance Win32_StartupCommand | ForEach-Object {
  [pscustomobject]@{ nome = [string]$_.Name; comando = [string]$_.Command; local = [string]$_.Location } })
$pythons = @(Get-ItemProperty 'HKLM:\SOFTWARE\Python\PythonCore\*\InstallPath', 'HKCU:\SOFTWARE\Python\PythonCore\*\InstallPath' -ErrorAction SilentlyContinue |
  ForEach-Object { [string]$_.'(default)' } | Where-Object { $_ })
$npm = ''
if ($env:APPDATA) { $c = Join-Path $env:APPDATA 'npm\node_modules'; if (Test-Path $c) { $npm = $c } }
[pscustomobject]@{ apps = $apps; servicos = $servicos; tarefas = $tarefas; inicializacao = $inicializacao; pythons = $pythons; npm = $npm }
```

- [ ] **Step 2: Fixture e testes que falham**

`tests/fixtures/inventario_sistema.json`:

```json
{
  "apps": [
    {"origem": "registro", "nome": "Git", "versao": "2.43.0", "editor": "The Git Development Community", "local": "C:\\Program Files\\Git"},
    {"origem": "registro", "nome": "Ollama", "versao": "0.40.5", "editor": "Ollama", "local": "C:\\Users\\Diniz\\AppData\\Local\\Programs\\Ollama"},
    {"origem": "loja", "nome": "Microsoft.WindowsCalculator", "versao": "11.2.0.0", "editor": "CN=Microsoft", "local": "C:\\Program Files\\WindowsApps\\calc"}
  ],
  "servicos": [
    {"nome": "Spooler", "exibicao": "Spooler de Impressão", "estado": "Running", "inicio": "Auto"},
    {"nome": "wuauserv", "exibicao": "Windows Update", "estado": "Stopped", "inicio": "Manual"}
  ],
  "tarefas": [
    {"caminho": "\\Microsoft\\Windows\\Defrag\\", "nome": "ScheduledDefrag", "estado": "Ready"}
  ],
  "inicializacao": {"nome": "Discord", "comando": "C:\\Discord\\Update.exe", "local": "HKCU\\Run"},
  "pythons": ["C:\\Users\\Diniz\\AppData\\Local\\Programs\\Python\\Python310\\"],
  "npm": "C:\\Users\\Diniz\\AppData\\Roaming\\npm\\node_modules"
}
```

(`inicializacao` é um objeto solto de propósito: o ConvertTo-Json do PowerShell devolve objeto, não lista, quando só há um item. O parser precisa aceitar os dois formatos.)

`tests/test_inventario_sistema.py`:

```python
import json
import unittest

from jarvis_pc.inventario import sistema
from jarvis_pc.inventario.banco import Banco
from jarvis_pc.inventario.sistema import coletar_sistema
from jarvis_pc.leitura import ler_script

from tests.ajuda import ExecutorFalso, fixture


def nomes(banco, tabela):
    return sorted(r["nome"] for r in banco.consultar(f"SELECT nome FROM {tabela}"))


class TestColeta(unittest.TestCase):
    def setUp(self):
        self.banco = Banco()

    def test_grava_apps_servicos_tarefas_e_inicializacao(self):
        ex = ExecutorFalso(saida=json.dumps(fixture("inventario_sistema")))
        r = coletar_sistema(self.banco, executor=ex)
        self.assertTrue(r.ok)
        self.assertEqual(nomes(self.banco, "apps"), ["Git", "Microsoft.WindowsCalculator", "Ollama"])
        self.assertEqual(nomes(self.banco, "servicos"), ["Spooler", "wuauserv"])
        self.assertEqual(nomes(self.banco, "tarefas"), ["ScheduledDefrag"])
        self.assertEqual(nomes(self.banco, "inicializacao"), ["Discord"])
        self.assertEqual(r.itens, 3 + 2 + 1 + 1)

    def test_devolve_caminhos_de_python_e_npm(self):
        ex = ExecutorFalso(saida=json.dumps(fixture("inventario_sistema")))
        r = coletar_sistema(self.banco, executor=ex)
        self.assertEqual(r.pythons, ["C:\\Users\\Diniz\\AppData\\Local\\Programs\\Python\\Python310\\"])
        self.assertEqual(r.npm, "C:\\Users\\Diniz\\AppData\\Roaming\\npm\\node_modules")

    def test_varredura_fica_registrada_como_ok(self):
        coletar_sistema(self.banco, executor=ExecutorFalso(saida=json.dumps(fixture("inventario_sistema"))))
        self.assertEqual(self.banco.ultima_varredura("sistema")["estado"], "ok")

    def test_uma_lista_de_um_item_chega_como_objeto_e_funciona(self):
        d = fixture("inventario_sistema")
        d["servicos"] = d["servicos"][0]
        d["pythons"] = d["pythons"][0]
        r = coletar_sistema(self.banco, executor=ExecutorFalso(saida=json.dumps(d)))
        self.assertEqual(nomes(self.banco, "servicos"), ["Spooler"])
        self.assertEqual(r.pythons, ["C:\\Users\\Diniz\\AppData\\Local\\Programs\\Python\\Python310\\"])

    def test_campos_ausentes_viram_vazio_sem_quebrar(self):
        r = coletar_sistema(self.banco, executor=ExecutorFalso(saida=json.dumps({"apps": [{"nome": "So Nome"}]})))
        self.assertTrue(r.ok)
        self.assertEqual(nomes(self.banco, "apps"), ["So Nome"])
        self.assertEqual((r.pythons, r.npm), ([], ""))

    def test_falha_do_powershell_nao_apaga_o_que_existia(self):
        coletar_sistema(self.banco, executor=ExecutorFalso(saida=json.dumps(fixture("inventario_sistema"))))
        r = coletar_sistema(self.banco, executor=ExecutorFalso(saida="", codigo=1, erro="negado"))
        self.assertFalse(r.ok)
        self.assertIn("negado", r.motivo)
        self.assertEqual(len(nomes(self.banco, "apps")), 3)
        self.assertEqual(self.banco.consultar("SELECT estado FROM varreduras ORDER BY id DESC LIMIT 1")[0]["estado"], "falhou")

    def test_json_invalido_e_falha_limpa(self):
        r = coletar_sistema(self.banco, executor=ExecutorFalso(saida="isto nao e json"))
        self.assertFalse(r.ok)

    def test_usa_o_script_e_um_prazo_longo(self):
        ex = ExecutorFalso(saida=json.dumps(fixture("inventario_sistema")))
        coletar_sistema(self.banco, executor=ex)
        self.assertEqual(ex.chamadas[0]["script"], ler_script("inventario_sistema"))
        self.assertGreaterEqual(ex.chamadas[0]["timeout"], 120)


class TestScript(unittest.TestCase):
    def test_script_so_le(self):
        texto = ler_script("inventario_sistema").lower()
        for proibido in ("remove-", "set-", "new-item", "out-file", "add-content", "stop-", "start-", "restart-", "invoke-"):
            with self.subTest(proibido=proibido):
                self.assertNotIn(proibido, texto)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `.venv/bin/python -B -m unittest tests.test_inventario_sistema -q`
Expected: FAIL com `ImportError` (módulo `sistema` não existe).

- [ ] **Step 4: Implementar**

`src/jarvis_pc/inventario/sistema.py`:

```python
"""Coleta do sistema: apps instalados, serviços, tarefas agendadas e inicialização.

Um único script PowerShell (só leitura) devolve tudo em JSON. O PowerShell
devolve um objeto, e não uma lista, quando só há um item; `_lista` aceita os dois.
"""
import json
import time
from dataclasses import dataclass, field

from jarvis_pc.leitura import ler_script
from jarvis_pc.ps import executar_powershell

TABELAS_SISTEMA = ("apps", "servicos", "tarefas", "inicializacao")
PRAZO = 180


@dataclass(frozen=True)
class ResultadoColeta:
    ok: bool
    motivo: str = ""
    pythons: list = field(default_factory=list)
    npm: str = ""
    itens: int = 0


def _lista(valor):
    if valor is None:
        return []
    if isinstance(valor, list):
        return valor
    return [valor]


def _texto(valor):
    return "" if valor is None else str(valor)


def coletar_sistema(banco, executor=executar_powershell, agora=time.time):
    vid = banco.iniciar_varredura("sistema", agora())
    resultado = executor(ler_script("inventario_sistema"), timeout=PRAZO, json=True)
    if resultado.codigo != 0 or not resultado.saida.strip():
        motivo = (resultado.erro or "sem saída").strip()
        banco.encerrar_varredura(vid, "falhou", 1, agora())
        return ResultadoColeta(False, f"o PowerShell falhou: {motivo}")
    try:
        dados = json.loads(resultado.saida)
        if not isinstance(dados, dict):
            raise ValueError("esperado um objeto")
        total = 0
        for tabela in TABELAS_SISTEMA:
            linhas = [
                {k: _texto(v) for k, v in item.items()} for item in _lista(dados.get(tabela)) if isinstance(item, dict)
            ]
            banco.gravar(tabela, vid, linhas)
            total += len(linhas)
        pythons = [_texto(p) for p in _lista(dados.get("pythons")) if p]
        npm = _texto(dados.get("npm"))
    except (ValueError, TypeError):
        banco.encerrar_varredura(vid, "falhou", 1, agora())
        return ResultadoColeta(False, "o PowerShell devolveu um formato inesperado")
    banco.encerrar_varredura(vid, "ok", 0, agora())
    return ResultadoColeta(True, "", pythons, npm, total)
```

- [ ] **Step 5: Rodar e ver passar**

Run: `.venv/bin/python -B -m unittest tests.test_inventario_sistema -q`
Expected: PASS.

- [ ] **Step 6: Mutação**

```bash
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/sistema.py "if resultado.codigo != 0 or not resultado.saida.strip():" "if False:"
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/sistema.py "    return [valor]" "    return []"
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/sistema.py 'banco.encerrar_varredura(vid, "ok", 0, agora())' 'banco.encerrar_varredura(vid, "falhou", 0, agora())'
```
Todas devem sair com 0.

- [ ] **Step 7: Commit**

```bash
git add src/jarvis_pc/ps/inventario_sistema.ps1 src/jarvis_pc/inventario/sistema.py tests/test_inventario_sistema.py tests/fixtures/inventario_sistema.json
git commit -m "feat(jarvis): coleta de apps, servicos, tarefas e inicializacao

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Coleta de pacotes (dependências)

**Files:**
- Create: `src/jarvis_pc/inventario/pacotes.py`
- Test: `tests/test_inventario_pacotes.py`

**Interfaces:**
- Consumes: `Banco`; `ResultadoColeta.pythons` e `.npm` (Task 5); linhas de `arquivos` com `nome = 'pyvenv.cfg'` (Task 4).
- Produces: `coletar_pacotes(banco, pythons, npm, agora=time.time) -> int` (número de pacotes gravados). Ambiente de um venv é a pasta que contém o `pyvenv.cfg`; de um Python global é a pasta de instalação; do npm é a string `"npm-global"`. Nada é executado: só se listam pastas `*.dist-info` e se leem `package.json`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_inventario_pacotes.py`:

```python
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
                sorted(ler_dist_info(sp)), [("requests", "2.31.0"), ("typing_extensions", "4.9.0")]
            )

    def test_pasta_inexistente_devolve_vazio(self):
        self.assertEqual(ler_dist_info(Path("/nao/existe")), [])

    def test_nome_sem_versao_e_ignorado(self):
        with tempfile.TemporaryDirectory() as t:
            sp = fazer_site_packages(t, ["quebrado.dist-info"])
            self.assertEqual(ler_dist_info(sp), [])


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
                sorted(ler_npm(nm)),
                [("@anthropic-ai/claude-code", "1.0.0"), ("pm2", "5.3.0"), ("sem-json", "")],
            )

    def test_pasta_vazia_ou_inexistente(self):
        self.assertEqual(ler_npm(Path("/nao/existe")), [])


class TestColeta(unittest.TestCase):
    def setUp(self):
        self.banco = Banco()
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -B -m unittest tests.test_inventario_pacotes -q`
Expected: FAIL com `ModuleNotFoundError`.

- [ ] **Step 3: Implementar**

`src/jarvis_pc/inventario/pacotes.py`:

```python
"""Dependências instaladas: pacotes Python de cada ambiente e módulos globais do npm.

Nada é executado: lê as pastas `*.dist-info` (nome e versão estão no nome da
pasta) e os `package.json`. Os ambientes vêm de duas fontes: os `pyvenv.cfg`
já catalogados (cada um marca um venv) e os Python globais que o registro do
Windows informou. Pacotes em AppData só entram aqui, como inventário.
"""
import json
import time
from pathlib import Path


def ler_dist_info(site_packages):
    site_packages = Path(site_packages)
    pacotes = []
    try:
        pastas = [p for p in site_packages.iterdir() if p.name.endswith(".dist-info")]
    except OSError:
        return pacotes
    for p in pastas:
        nome, _, versao = p.name[: -len(".dist-info")].rpartition("-")
        if nome and versao:
            pacotes.append((nome, versao))
    return pacotes


def ler_npm(modulos):
    modulos = Path(modulos)
    achados = []

    def um(pasta, nome):
        try:
            versao = str(json.loads((pasta / "package.json").read_text(encoding="utf-8")).get("version", ""))
        except (OSError, ValueError, AttributeError):
            versao = ""
        achados.append((nome, versao))

    try:
        for p in modulos.iterdir():
            if not p.is_dir():
                continue
            if p.name.startswith("@"):
                for q in p.iterdir():
                    if q.is_dir():
                        um(q, f"{p.name}/{q.name}")
            else:
                um(p, p.name)
    except OSError:
        pass
    return achados


def coletar_pacotes(banco, pythons, npm, agora=time.time):
    vid = banco.iniciar_varredura("pacotes", agora())
    ambientes = {}
    for r in banco.consultar("SELECT pasta FROM arquivos WHERE nome = 'pyvenv.cfg'"):
        ambientes[r["pasta"]] = Path(r["pasta"]) / "Lib" / "site-packages"
    for p in pythons:
        raiz = str(p).rstrip("\\/")
        ambientes.setdefault(raiz, Path(raiz) / "Lib" / "site-packages")
    linhas = []
    for ambiente, site in ambientes.items():
        linhas += [(ambiente, nome, versao) for nome, versao in ler_dist_info(site)]
    if npm:
        linhas += [("npm-global", nome, versao) for nome, versao in ler_npm(npm)]
    banco.gravar("pacotes", vid, linhas)
    banco.encerrar_varredura(vid, "ok", 0, agora())
    return len(linhas)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -B -m unittest tests.test_inventario_pacotes -q`
Expected: PASS.

- [ ] **Step 5: Mutação**

```bash
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/pacotes.py 'if nome and versao:' 'if True:'
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/pacotes.py 'if p.name.startswith("@"):' 'if False:'
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/pacotes.py "WHERE nome = 'pyvenv.cfg'" "WHERE nome = 'x'"
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/pacotes.py 'raiz = str(p).rstrip("\\/")' 'raiz = str(p)'
```
Todas devem sair com 0.

- [ ] **Step 6: Commit**

```bash
git add src/jarvis_pc/inventario/pacotes.py tests/test_inventario_pacotes.py
git commit -m "feat(jarvis): coleta de dependencias sem executar nada

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Consultas

**Files:**
- Create: `src/jarvis_pc/inventario/consultas.py`
- Test: `tests/test_inventario_consultas.py`

**Interfaces:**
- Consumes: `Banco.consultar/ultima_varredura/em_andamento/definir_hash`; `normalizar` de `exclusoes`.
- Produces (todas devolvem `str`, em português, sem o `AVISO`, que a ferramenta acrescenta):
  - `status(banco, agora=time.time)`
  - `arquivos_buscar(banco, nome="", extensao="", pasta="", minimo_mb=0.0, limite=20)`
  - `arquivos_maiores(banco, pasta="", limite=15)`
  - `arquivos_pastas(banco, pasta, limite=15)`
  - `arquivos_duplicados(banco, pasta="", minimo_mb=1.0, limite=10, calcular_hash=hash_arquivo)`
  - `apps(banco, nome="", limite=30)`
  - `dependencias(banco, ambiente="", nome="", limite=40)`
  - `sistema(banco, tipo, filtro="", limite=40)` com `tipo` em `servicos | tarefas | inicializacao`
  - `humano(bytes) -> str`, `data_curta(ts) -> str`, `hash_arquivo(caminho) -> str | None`
- Contrato de texto: a primeira linha de cada resposta é `Dados da varredura de dd/mm/aaaa HH:MM.` (ou a frase de "ainda não há varredura"); depois vem a contagem exata (`Achei N arquivo(s); mostrando M.`) e as linhas.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_inventario_consultas.py`:

```python
import time
import unittest

from jarvis_pc.inventario import consultas
from jarvis_pc.inventario.banco import Banco

MB = 1024 * 1024
AGORA = 1_800_000_000.0


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


class TestFormatos(unittest.TestCase):
    def test_humano(self):
        self.assertEqual(consultas.humano(0), "0 B")
        self.assertEqual(consultas.humano(1023), "1023 B")
        self.assertEqual(consultas.humano(1024), "1.0 KB")
        self.assertEqual(consultas.humano(5 * MB), "5.0 MB")
        self.assertEqual(consultas.humano(3 * 1024 * MB), "3.00 GB")

    def test_data_curta(self):
        self.assertRegex(consultas.data_curta(AGORA), r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}$")


class TestSemDados(unittest.TestCase):
    def test_sem_varredura_orienta_a_atualizar(self):
        t = consultas.arquivos_buscar(Banco(), nome="x")
        self.assertIn("Ainda não há varredura de arquivos", t)
        self.assertIn("inv_atualizar", t)


class TestStatus(unittest.TestCase):
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


class TestBuscar(unittest.TestCase):
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


class TestMaioresEPastas(unittest.TestCase):
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


class TestDuplicados(unittest.TestCase):
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


class TestAppsEDependencias(unittest.TestCase):
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -B -m unittest tests.test_inventario_consultas -q`
Expected: FAIL com `ModuleNotFoundError`.

- [ ] **Step 3: Implementar**

`src/jarvis_pc/inventario/consultas.py`:

```python
"""Consultas fixas ao inventário. O modelo escolhe qual chamar; o número vem do banco.

Toda resposta começa com a data da varredura que a originou. Os textos são
curtos de propósito: o modelo local lê o que couber no contexto.
"""
import hashlib
import time
from datetime import datetime

from jarvis_pc.inventario.exclusoes import normalizar

ESCAPE = "!"
UM_MB = 1024 * 1024
LIMITE_MAXIMO = 100
VELHO_APOS_S = 2 * 86400
LIMITE_HASH = 300


def humano(n):
    n = int(n or 0)
    if n < 1024:
        return f"{n} B"
    if n < UM_MB:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * UM_MB:
        return f"{n / UM_MB:.1f} MB"
    return f"{n / (1024 * UM_MB):.2f} GB"


def data_curta(ts):
    return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")


def _limite(valor, padrao):
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return padrao
    if n < 1:
        return padrao
    return min(n, LIMITE_MAXIMO)


def _like(texto):
    t = str(texto).replace(ESCAPE, ESCAPE * 2).replace("%", ESCAPE + "%").replace("_", ESCAPE + "_")
    return f"%{t}%"


def _prefixo(pasta):
    n = normalizar(pasta)
    return n + "\\"


def _cabecalho(banco, tipo, rotulo):
    u = banco.ultima_varredura(tipo)
    if not u:
        return None, (
            f"Ainda não há varredura de {rotulo}. Use inv_atualizar para o inventário ser feito "
            "e depois pergunte de novo."
        )
    return u, f"Dados da varredura de {data_curta(u['fim'])}."


def _mostrando(total, mostrados, unidade):
    return f"Achei {total} {unidade}; mostrando {mostrados}."


def status(banco, agora=time.time):
    linhas = []
    agora_ts = agora()
    for tipo, rotulo in (("arquivos", "arquivos"), ("sistema", "sistema"), ("pacotes", "pacotes")):
        u = banco.ultima_varredura(tipo)
        if not u:
            linhas.append(f"- {rotulo}: nunca varrido.")
            continue
        horas = int((agora_ts - u["fim"]) // 3600)
        velho = " (desatualizado, use inv_atualizar)" if agora_ts - u["fim"] > VELHO_APOS_S else ""
        linhas.append(f"- {rotulo}: varredura de {data_curta(u['fim'])}, há {horas} hora(s){velho}, {u['erros']} erro(s).")
    contagens = {
        t: banco.consultar(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"]
        for t in ("arquivos", "apps", "pacotes", "servicos", "tarefas", "inicializacao")
    }
    linhas.append(
        f"No banco: {contagens['arquivos']} arquivo(s), {contagens['apps']} app(s), {contagens['pacotes']} pacote(s), "
        f"{contagens['servicos']} serviço(s), {contagens['tarefas']} tarefa(s), {contagens['inicializacao']} item(ns) de inicialização."
    )
    for a in banco.em_andamento():
        linhas.append(f"Varredura de {a['tipo']} em andamento: {a['itens']} item(ns) até agora.")
    return "\n".join(linhas)


def arquivos_buscar(banco, nome="", extensao="", pasta="", minimo_mb=0.0, limite=20):
    u, cab = _cabecalho(banco, "arquivos", "arquivos")
    if not u:
        return cab
    onde, params = [], []
    if nome:
        onde.append(f"nome LIKE ? ESCAPE '{ESCAPE}'")
        params.append(_like(nome))
    if extensao:
        e = str(extensao).strip().lower()
        params.append(e if e.startswith(".") else "." + e)
        onde.append("ext = ?")
    if pasta:
        onde.append(f"caminho LIKE ? ESCAPE '{ESCAPE}'")
        params.append(_like(_prefixo(pasta))[1:])
    try:
        minimo = float(minimo_mb or 0)
    except (TypeError, ValueError):
        minimo = 0.0
    if minimo > 0:
        onde.append("tamanho >= ?")
        params.append(int(minimo * UM_MB))
    clausula = (" WHERE " + " AND ".join(onde)) if onde else ""
    total = banco.consultar(f"SELECT COUNT(*) AS n FROM arquivos{clausula}", params)[0]["n"]
    if not total:
        return f"{cab}\nNão achei nenhum arquivo com esses filtros."
    n = _limite(limite, 20)
    linhas = banco.consultar(
        f"SELECT caminho, tamanho, modificado FROM arquivos{clausula} ORDER BY tamanho DESC LIMIT ?", params + [n]
    )
    saida = [cab, _mostrando(total, len(linhas), "arquivo(s)")]
    saida += [f"- {r['caminho']} ({humano(r['tamanho'])}, {data_curta(r['modificado'])})" for r in linhas]
    return "\n".join(saida)


def arquivos_maiores(banco, pasta="", limite=15):
    u, cab = _cabecalho(banco, "arquivos", "arquivos")
    if not u:
        return cab
    onde, params = "", []
    if pasta:
        onde = f" WHERE caminho LIKE ? ESCAPE '{ESCAPE}'"
        params.append(_like(_prefixo(pasta))[1:])
    n = _limite(limite, 15)
    linhas = banco.consultar(
        f"SELECT caminho, tamanho FROM arquivos{onde} ORDER BY tamanho DESC LIMIT ?", params + [n]
    )
    if not linhas:
        return f"{cab}\nNão achei arquivos nessa pasta."
    return "\n".join([cab, f"Os {len(linhas)} maiores arquivos:"] + [f"- {r['caminho']} ({humano(r['tamanho'])})" for r in linhas])


def arquivos_pastas(banco, pasta, limite=15):
    u, cab = _cabecalho(banco, "arquivos", "arquivos")
    if not u:
        return cab
    base = normalizar(pasta)
    corte = len(base) + 2
    linhas = banco.consultar(
        f"""SELECT sub, SUM(tamanho) AS total, COUNT(*) AS n FROM (
              SELECT substr(substr(caminho, ?), 1, instr(substr(caminho, ?) || '\\', '\\') - 1) AS sub, tamanho
              FROM arquivos WHERE caminho LIKE ? ESCAPE '{ESCAPE}')
            GROUP BY sub ORDER BY total DESC LIMIT ?""",
        (corte, corte, _like(base + "\\")[1:], _limite(limite, 15)),
    )
    if not linhas:
        return f"{cab}\nNão achei arquivos em {pasta}."
    saida = [cab, f"Espaço usado dentro de {pasta}, por subpasta:"]
    for r in linhas:
        nome = r["sub"] if "\\" not in r["sub"] and r["sub"] and not _eh_arquivo_solto(banco, base, r["sub"]) else None
        saida.append(f"- {nome or '(arquivos soltos em ' + pasta + ')'}: {humano(r['total'])} em {r['n']} arquivo(s)")
    return "\n".join(saida)


def _eh_arquivo_solto(banco, base, sub):
    achou = banco.consultar("SELECT 1 FROM arquivos WHERE LOWER(caminho) = ? LIMIT 1", (base + "\\" + sub.lower(),))
    return bool(achou)


def hash_arquivo(caminho):
    h = hashlib.sha256()
    try:
        with open(caminho, "rb") as f:
            for bloco in iter(lambda: f.read(1024 * 1024), b""):
                h.update(bloco)
    except OSError:
        return None
    return h.hexdigest()


def arquivos_duplicados(banco, pasta="", minimo_mb=1.0, limite=10, calcular_hash=hash_arquivo):
    u, cab = _cabecalho(banco, "arquivos", "arquivos")
    if not u:
        return cab
    try:
        minimo = max(float(minimo_mb), 0.0)
    except (TypeError, ValueError):
        minimo = 1.0
    onde, params = "tamanho >= ?", [int(minimo * UM_MB)]
    if pasta:
        onde += f" AND caminho LIKE ? ESCAPE '{ESCAPE}'"
        params.append(_like(_prefixo(pasta))[1:])
    candidatos = banco.consultar(
        f"""SELECT caminho, tamanho, hash FROM arquivos WHERE {onde} AND tamanho IN (
              SELECT tamanho FROM arquivos WHERE {onde} GROUP BY tamanho HAVING COUNT(*) > 1)
            ORDER BY tamanho DESC""",
        params + params,
    )
    feitos = 0
    por_hash = {}
    for r in candidatos:
        h = r["hash"]
        if h is None:
            if feitos >= LIMITE_HASH:
                continue
            h = calcular_hash(r["caminho"])
            feitos += 1
            if h is None:
                continue
            banco.definir_hash(r["caminho"], h)
        por_hash.setdefault((r["tamanho"], h), []).append(r["caminho"])
    grupos = sorted(
        ((t, c) for (t, _), c in por_hash.items() if len(c) > 1), key=lambda g: -g[0] * (len(g[1]) - 1)
    )
    if not grupos:
        return f"{cab}\nNão achei arquivos duplicados com pelo menos {minimo:g} MB."
    desperdicio = sum(t * (len(c) - 1) for t, c in grupos)
    saida = [cab, f"{len(grupos)} grupo(s) de arquivos idênticos, desperdício de {humano(desperdicio)} no total:"]
    for t, caminhos in grupos[: _limite(limite, 10)]:
        saida.append(f"- {humano(t)} cada, {len(caminhos)} cópias:")
        saida += [f"    {c}" for c in caminhos[:6]]
    return "\n".join(saida)


def apps(banco, nome="", limite=30):
    u, cab = _cabecalho(banco, "sistema", "sistema")
    if not u:
        return cab
    onde, params = "", []
    if nome:
        onde = f" WHERE nome LIKE ? ESCAPE '{ESCAPE}'"
        params.append(_like(nome))
    total = banco.consultar(f"SELECT COUNT(*) AS n FROM apps{onde}", params)[0]["n"]
    if not total:
        return f"{cab}\nNão achei nenhum app com esse nome."
    linhas = banco.consultar(
        f"SELECT origem, nome, versao, editor FROM apps{onde} ORDER BY nome COLLATE NOCASE LIMIT ?", params + [_limite(limite, 30)]
    )
    saida = [cab, _mostrando(total, len(linhas), "app(s)")]
    saida += [f"- {r['nome']} {r['versao'] or ''} [{r['origem']}] {r['editor'] or ''}".rstrip() for r in linhas]
    return "\n".join(saida)


def dependencias(banco, ambiente="", nome="", limite=40):
    u, cab = _cabecalho(banco, "pacotes", "pacotes")
    if not u:
        return cab
    if not ambiente and not nome:
        amb = banco.consultar("SELECT ambiente, COUNT(*) AS n FROM pacotes GROUP BY ambiente ORDER BY n DESC")
        if not amb:
            return f"{cab}\nNenhum ambiente com pacotes."
        return "\n".join([cab, f"Ambientes com pacotes ({len(amb)}):"] + [f"- {r['ambiente']}: {r['n']} pacote(s)" for r in amb])
    onde, params = [], []
    if ambiente:
        onde.append(f"ambiente LIKE ? ESCAPE '{ESCAPE}'")
        params.append(_like(ambiente))
    if nome:
        onde.append(f"nome LIKE ? ESCAPE '{ESCAPE}'")
        params.append(_like(nome))
    clausula = " WHERE " + " AND ".join(onde)
    total = banco.consultar(f"SELECT COUNT(*) AS n FROM pacotes{clausula}", params)[0]["n"]
    if not total:
        return f"{cab}\nNão achei nenhum pacote com esses filtros."
    linhas = banco.consultar(
        f"SELECT ambiente, nome, versao FROM pacotes{clausula} ORDER BY ambiente, nome COLLATE NOCASE LIMIT ?",
        params + [_limite(limite, 40)],
    )
    return "\n".join(
        [cab, _mostrando(total, len(linhas), "pacote(s)")] + [f"- {r['nome']} {r['versao']} ({r['ambiente']})" for r in linhas]
    )


def sistema(banco, tipo, filtro="", limite=40):
    tipos = {
        "servicos": ("serviço(s)", "servicos", "nome", "exibicao", lambda r: f"- {r['nome']} ({r['exibicao']}): {r['estado']}, início {r['inicio']}"),
        "tarefas": ("tarefa(s)", "tarefas", "nome", "caminho", lambda r: f"- {r['caminho']}{r['nome']}: {r['estado']}"),
        "inicializacao": ("item(ns) de inicialização", "inicializacao", "nome", "comando", lambda r: f"- {r['nome']}: {r['comando']}"),
    }
    if tipo not in tipos:
        return "O tipo deve ser servicos, tarefas ou inicializacao."
    unidade, tabela, c1, c2, fmt = tipos[tipo]
    u, cab = _cabecalho(banco, "sistema", "sistema")
    if not u:
        return cab
    onde, params = "", []
    if filtro:
        campos = [c1, c2] + (["estado"] if tipo != "inicializacao" else [])
        onde = " WHERE " + " OR ".join(f"{c} LIKE ? ESCAPE '{ESCAPE}'" for c in campos)
        params = [_like(filtro)] * len(campos)
    total = banco.consultar(f"SELECT COUNT(*) AS n FROM {tabela}{onde}", params)[0]["n"]
    if not total:
        return f"{cab}\nNão achei nenhum item com esse filtro."
    linhas = banco.consultar(f"SELECT * FROM {tabela}{onde} ORDER BY {c1} COLLATE NOCASE LIMIT ?", params + [_limite(limite, 40)])
    return "\n".join([cab, _mostrando(total, len(linhas), unidade)] + [fmt(r) for r in linhas])
```

Nota para quem implementa: o teste `test_espaco_por_pasta_numa_subpasta` espera o rótulo `(arquivos soltos em C:\A)` para o arquivo que está direto na pasta pedida. Em `arquivos_pastas`, quando `sub` é igual ao nome de um arquivo (não há barra depois dele) o item é "arquivos soltos". Se a lógica de `_eh_arquivo_solto` acima ficar frágil ao rodar os testes, simplifique: some os arquivos soltos numa consulta separada (`WHERE caminho LIKE base\% AND instr(substr(caminho, corte), '\') = 0`) e as subpastas noutra (`... > 0`), em vez de inferir pelo nome. Os testes é que mandam.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -B -m unittest tests.test_inventario_consultas -q`
Expected: PASS. Corrija o que falhar mudando só `consultas.py`; os testes definem o comportamento.

- [ ] **Step 5: Mutação**

```bash
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/consultas.py "return min(n, LIMITE_MAXIMO)" "return n"
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/consultas.py 'replace("%", ESCAPE + "%")' 'replace("%", "%")'
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/consultas.py 'HAVING COUNT(*) > 1)' 'HAVING COUNT(*) > 0)'
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/consultas.py "if len(c) > 1)" "if len(c) > 0)"
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/consultas.py "ORDER BY tamanho DESC LIMIT ?\", params + [n]" "ORDER BY tamanho ASC LIMIT ?\", params + [n]"
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/consultas.py "if h is None:
            if feitos >= LIMITE_HASH:" "if True:
            if feitos >= LIMITE_HASH:"
```
Todas devem sair com 0.

- [ ] **Step 6: Commit**

```bash
git add src/jarvis_pc/inventario/consultas.py tests/test_inventario_consultas.py
git commit -m "feat(jarvis): consultas exatas ao inventario

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Atualizador em segundo plano

**Files:**
- Create: `src/jarvis_pc/inventario/atualizador.py`
- Test: `tests/test_inventario_atualizador.py`

**Interfaces:**
- Consumes: `varrer_arquivos` (Task 4), `coletar_sistema` (Task 5), `coletar_pacotes` (Task 6), `Banco`, `Exclusoes`.
- Produces: `Atualizador(banco, raizes, exclusoes, *, executor=executar_powershell, agora=time.time, sincrono=False)` com `iniciar() -> bool` (falso se já rodando), `rodando() -> bool`, `cancelar() -> None`, `ultimo_erro: str`. Ordem: arquivos, sistema, pacotes. O cancelamento só afeta a varredura de arquivos (as outras são curtas).

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_inventario_atualizador.py`:

```python
import json
import tempfile
import time
import unittest
from pathlib import Path

from jarvis_pc.inventario.atualizador import Atualizador
from jarvis_pc.inventario.banco import Banco
from jarvis_pc.inventario.exclusoes import Exclusoes

from tests.ajuda import ExecutorFalso, fixture


class TestAtualizador(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        (Path(self._tmp.name) / "a.txt").write_text("x")
        self.banco = Banco()
        self.ex = ExecutorFalso(saida=json.dumps(fixture("inventario_sistema")))

    def montar(self, **kw):
        return Atualizador(self.banco, [self._tmp.name], Exclusoes(), executor=self.ex, **kw)

    def test_roda_as_tres_coletas_na_ordem(self):
        a = self.montar(sincrono=True)
        self.assertTrue(a.iniciar())
        for tipo in ("arquivos", "sistema", "pacotes"):
            with self.subTest(tipo=tipo):
                self.assertEqual(self.banco.ultima_varredura(tipo)["estado"], "ok")
        tipos = [r["tipo"] for r in self.banco.consultar("SELECT tipo FROM varreduras ORDER BY id")]
        self.assertEqual(tipos, ["arquivos", "sistema", "pacotes"])
        self.assertFalse(a.rodando())
        self.assertEqual(a.ultimo_erro, "")

    def test_nao_inicia_duas_vezes_ao_mesmo_tempo(self):
        a = self.montar(sincrono=True)
        a._ativa = True
        self.assertFalse(a.iniciar())

    def test_em_thread_termina_e_libera(self):
        a = self.montar()
        self.assertTrue(a.iniciar())
        for _ in range(100):
            if not a.rodando():
                break
            time.sleep(0.05)
        self.assertFalse(a.rodando())
        self.assertIsNotNone(self.banco.ultima_varredura("pacotes"))

    def test_erro_numa_coleta_fica_registrado_e_nao_derruba(self):
        class Quebra:
            def __call__(self, *a, **k):
                raise RuntimeError("boom")

        a = Atualizador(self.banco, [self._tmp.name], Exclusoes(), executor=Quebra(), sincrono=True)
        a.iniciar()
        self.assertIn("boom", a.ultimo_erro)
        self.assertFalse(a.rodando())
        self.assertEqual(self.banco.ultima_varredura("arquivos")["estado"], "ok")

    def test_falha_do_powershell_vira_erro_legivel(self):
        self.ex = ExecutorFalso(saida="", codigo=1, erro="negado")
        a = self.montar(sincrono=True)
        a.iniciar()
        self.assertIn("negado", a.ultimo_erro)

    def test_cancelar_interrompe_a_varredura_de_arquivos(self):
        a = self.montar(sincrono=True)
        a.cancelar()
        a.iniciar()
        self.assertIsNone(self.banco.ultima_varredura("arquivos"))
        estados = [r["estado"] for r in self.banco.consultar("SELECT estado FROM varreduras WHERE tipo = 'arquivos'")]
        self.assertEqual(estados, ["cancelada"])

    def test_cancelar_so_vale_para_a_rodada_atual(self):
        a = self.montar(sincrono=True)
        a.cancelar()
        a.iniciar()
        a.iniciar()
        self.assertIsNotNone(self.banco.ultima_varredura("arquivos"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -B -m unittest tests.test_inventario_atualizador -q`
Expected: FAIL com `ModuleNotFoundError`.

- [ ] **Step 3: Implementar**

`src/jarvis_pc/inventario/atualizador.py`:

```python
"""Roda as três coletas em segundo plano, uma de cada vez, sem travar a janela."""
import threading
import time

from jarvis_pc.inventario.arquivos import varrer_arquivos
from jarvis_pc.inventario.pacotes import coletar_pacotes
from jarvis_pc.inventario.sistema import coletar_sistema
from jarvis_pc.ps import executar_powershell


class Atualizador:
    def __init__(self, banco, raizes, exclusoes, *, executor=executar_powershell, agora=time.time, sincrono=False):
        self.banco = banco
        self.raizes = list(raizes)
        self.exclusoes = exclusoes
        self._executor = executor
        self._agora = agora
        self._sincrono = sincrono
        self._ativa = False
        self._cancelar = False
        self._trava = threading.Lock()
        self.ultimo_erro = ""

    def rodando(self):
        return self._ativa

    def cancelar(self):
        self._cancelar = True

    def iniciar(self):
        with self._trava:
            if self._ativa:
                return False
            self._ativa = True
        self.ultimo_erro = ""
        if self._sincrono:
            self._rodar()
        else:
            threading.Thread(target=self._rodar, name="inventario", daemon=True).start()
        return True

    def _rodar(self):
        try:
            varrer_arquivos(
                self.banco, self.raizes, self.exclusoes, agora=self._agora, cancelado=lambda: self._cancelar
            )
            self._cancelar = False
            coleta = coletar_sistema(self.banco, executor=self._executor, agora=self._agora)
            if not coleta.ok:
                self.ultimo_erro = coleta.motivo
            coletar_pacotes(self.banco, coleta.pythons, coleta.npm, agora=self._agora)
        except Exception as erro:
            self.ultimo_erro = f"{type(erro).__name__}: {erro}"
        finally:
            self._cancelar = False
            self._ativa = False
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -B -m unittest tests.test_inventario_atualizador -q`
Expected: PASS.

- [ ] **Step 5: Mutação**

```bash
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/atualizador.py "if self._ativa:
                return False" "if False:
                return False"
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/atualizador.py "cancelado=lambda: self._cancelar" "cancelado=lambda: False"
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/atualizador.py "            self._cancelar = False
            self._ativa = False" "            self._ativa = False"
```
Todas devem sair com 0.

- [ ] **Step 6: Commit**

```bash
git add src/jarvis_pc/inventario/atualizador.py tests/test_inventario_atualizador.py
git commit -m "feat(jarvis): atualizador do inventario em segundo plano

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 9: As seis ferramentas, o agente, o prompt e a partida

**Files:**
- Create: `src/jarvis_pc/inventario/ferramentas.py`
- Modify: `src/jarvis_pc/agente.py`, `src/jarvis_pc/prompt.py`, `src/jarvis_pc/__main__.py`
- Test: `tests/test_inventario_ferramentas.py`, `tests/test_prompt.py`, `tests/test_main.py`, `tests/test_agente.py`

**Interfaces:**
- Consumes: tudo das Tasks 1 a 8.
- Produces:
  - `NOMES_INVENTARIO = ("inv_status", "inv_atualizar", "inv_arquivos", "inv_apps", "inv_dependencias", "inv_sistema")`
  - `criar_ferramentas_inventario(banco, atualizador) -> list[BaseTool]`
  - `montar_inventario(pasta, config) -> tuple[list, Atualizador, Banco]`
  - `criar_agente(..., extras=())`: ferramentas extras entram no conjunto de ferramentas conhecidas.
  - `inv_arquivos` tem o parâmetro `operacao` em `buscar | maiores | pastas | duplicados`.

- [ ] **Step 1: Escrever os testes das ferramentas (falham)**

`tests/test_inventario_ferramentas.py`:

```python
import unittest

from jarvis_pc.inventario.atualizador import Atualizador
from jarvis_pc.inventario.banco import Banco
from jarvis_pc.inventario.exclusoes import Exclusoes
from jarvis_pc.inventario.ferramentas import NOMES_INVENTARIO, criar_ferramentas_inventario
from jarvis_pc.leitura import AVISO

AGORA = 1_800_000_000.0


def banco_pronto():
    b = Banco()
    v = b.iniciar_varredura("arquivos", AGORA - 10)
    b.gravar("arquivos", v, [("C:\\a\\instalar.ps1", "instalar.ps1", ".ps1", "C:\\a", 3000, 1.0), ("C:\\a\\grande.iso", "grande.iso", ".iso", "C:\\a", 900 * 1024 * 1024, 1.0)])
    b.encerrar_varredura(v, "ok", 0, AGORA)
    s = b.iniciar_varredura("sistema", AGORA - 10)
    b.gravar("apps", s, [{"origem": "registro", "nome": "Git", "versao": "2.43", "editor": "G", "local": ""}])
    b.gravar("servicos", s, [{"nome": "Spooler", "exibicao": "Spooler", "estado": "Running", "inicio": "Auto"}])
    b.encerrar_varredura(s, "ok", 0, AGORA)
    p = b.iniciar_varredura("pacotes", AGORA - 10)
    b.gravar("pacotes", p, [("C:\\Jarvis\\venv", "openjarvis", "1.0.5")])
    b.encerrar_varredura(p, "ok", 0, AGORA)
    return b


class Falso:
    def __init__(self, inicia=True, roda=False):
        self.inicia, self.roda, self.chamou = inicia, roda, 0
        self.ultimo_erro = ""

    def iniciar(self):
        self.chamou += 1
        return self.inicia

    def rodando(self):
        return self.roda


class TestFerramentas(unittest.TestCase):
    def setUp(self):
        self.atual = Falso()
        self.por_nome = {f.spec.name: f for f in criar_ferramentas_inventario(banco_pronto(), self.atual)}

    def test_sao_exatamente_as_seis(self):
        self.assertEqual(set(self.por_nome), set(NOMES_INVENTARIO))
        self.assertEqual(len(NOMES_INVENTARIO), 6)

    def test_nenhuma_pede_confirmacao_e_todas_tem_descricao(self):
        for nome, f in self.por_nome.items():
            with self.subTest(nome=nome):
                self.assertFalse(f.spec.requires_confirmation)
                self.assertGreater(len(f.spec.description), 20)

    def test_resposta_comeca_com_o_aviso(self):
        r = self.por_nome["inv_status"].execute()
        self.assertTrue(r.success)
        self.assertTrue(r.content.startswith(AVISO))

    def test_arquivos_buscar(self):
        r = self.por_nome["inv_arquivos"].execute(operacao="buscar", nome="instalar")
        self.assertIn("C:\\a\\instalar.ps1", r.content)

    def test_arquivos_maiores(self):
        r = self.por_nome["inv_arquivos"].execute(operacao="maiores", limite=1)
        self.assertIn("grande.iso", r.content)
        self.assertNotIn("instalar.ps1", r.content)

    def test_arquivos_pastas_exige_pasta(self):
        r = self.por_nome["inv_arquivos"].execute(operacao="pastas")
        self.assertFalse(r.success)
        self.assertIn("pasta", r.content)

    def test_arquivos_operacao_invalida(self):
        r = self.por_nome["inv_arquivos"].execute(operacao="apagar")
        self.assertFalse(r.success)
        self.assertIn("buscar", r.content)

    def test_limite_como_texto_funciona(self):
        r = self.por_nome["inv_arquivos"].execute(operacao="maiores", limite="1")
        self.assertTrue(r.success)

    def test_apps_dependencias_e_sistema(self):
        self.assertIn("Git 2.43", self.por_nome["inv_apps"].execute(nome="git").content)
        self.assertIn("openjarvis 1.0.5", self.por_nome["inv_dependencias"].execute(nome="openjarvis").content)
        self.assertIn("Spooler", self.por_nome["inv_sistema"].execute(tipo="servicos").content)

    def test_sistema_sem_tipo_falha_com_explicacao(self):
        r = self.por_nome["inv_sistema"].execute()
        self.assertFalse(r.success)

    def test_parametro_desconhecido_nao_quebra(self):
        r = self.por_nome["inv_apps"].execute(nome="git", inventado=1)
        self.assertTrue(r.success)

    def test_atualizar_inicia_e_avisa(self):
        r = self.por_nome["inv_atualizar"].execute()
        self.assertEqual(self.atual.chamou, 1)
        self.assertIn("iniciada", r.content)

    def test_atualizar_quando_ja_esta_rodando(self):
        self.por_nome["inv_atualizar"]._ctx.atualizador.inicia = False
        r = self.por_nome["inv_atualizar"].execute()
        self.assertIn("já está em andamento", r.content)

    def test_erro_do_banco_vira_falha_limpa(self):
        b = banco_pronto()
        b.fechar()
        f = {x.spec.name: x for x in criar_ferramentas_inventario(b, self.atual)}["inv_apps"]
        r = f.execute(nome="git")
        self.assertFalse(r.success)

    def test_so_leitura_nenhuma_ferramenta_tem_parametro_de_sql_ou_escrita(self):
        for nome, f in self.por_nome.items():
            props = set(f.spec.parameters.get("properties", {}))
            with self.subTest(nome=nome):
                self.assertFalse(props & {"sql", "consulta_sql", "comando", "script", "apagar", "gravar"})


class TestMontagem(unittest.TestCase):
    def test_montar_inventario_cria_banco_e_atualizador(self):
        import tempfile
        from pathlib import Path

        from jarvis_pc.config import Config
        from jarvis_pc.inventario.ferramentas import montar_inventario

        with tempfile.TemporaryDirectory() as pasta:
            ferramentas, atualizador, banco = montar_inventario(pasta, Config(raizes=(pasta,)))
            self.assertEqual({f.spec.name for f in ferramentas}, set(NOMES_INVENTARIO))
            self.assertIsInstance(atualizador, Atualizador)
            self.assertTrue((Path(pasta) / "inventario.db").exists())
            banco.fechar()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -B -m unittest tests.test_inventario_ferramentas -q`
Expected: FAIL com `ModuleNotFoundError`.

- [ ] **Step 3: Implementar as ferramentas**

`src/jarvis_pc/inventario/ferramentas.py`:

```python
"""As seis ferramentas do inventário que o agente enxerga. Só leitura.

O modelo nunca escreve SQL: cada ferramenta chama uma consulta fixa de
`consultas.py`. O texto devolvido começa com o aviso de que são dados.
"""
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

from jarvis_pc.inventario import consultas
from jarvis_pc.inventario.atualizador import Atualizador
from jarvis_pc.inventario.banco import Banco
from jarvis_pc.inventario.exclusoes import Exclusoes
from jarvis_pc.leitura import AVISO, LIMITE_SAIDA

NOMES_INVENTARIO = ("inv_status", "inv_atualizar", "inv_arquivos", "inv_apps", "inv_dependencias", "inv_sistema")
OPERACOES = ("buscar", "maiores", "pastas", "duplicados")
TIPOS_SISTEMA = ("servicos", "tarefas", "inicializacao")


@dataclass
class Contexto:
    banco: object
    atualizador: object


class Erro(Exception):
    """Pedido mal feito pelo modelo: a mensagem volta para ele como falha."""


def _status(ctx, **_):
    return consultas.status(ctx.banco)


def _atualizar(ctx, **_):
    if ctx.atualizador.iniciar():
        return (
            "Atualização do inventário iniciada em segundo plano. Pode levar vários minutos. "
            "Use inv_status para acompanhar."
        )
    return "A atualização do inventário já está em andamento. Use inv_status para acompanhar."


def _arquivos(ctx, operacao="", nome="", extensao="", pasta="", minimo_mb=0, limite=None, **_):
    if operacao not in OPERACOES:
        raise Erro("A operação deve ser: " + ", ".join(OPERACOES) + ".")
    extras = {} if limite is None else {"limite": limite}
    if operacao == "buscar":
        return consultas.arquivos_buscar(ctx.banco, nome=nome, extensao=extensao, pasta=pasta, minimo_mb=minimo_mb, **extras)
    if operacao == "maiores":
        return consultas.arquivos_maiores(ctx.banco, pasta=pasta, **extras)
    if operacao == "pastas":
        if not pasta:
            raise Erro("A operação pastas precisa do parâmetro pasta, por exemplo C:\\.")
        return consultas.arquivos_pastas(ctx.banco, pasta, **extras)
    return consultas.arquivos_duplicados(ctx.banco, pasta=pasta, minimo_mb=minimo_mb or 1.0, **extras)


def _apps(ctx, nome="", **_):
    return consultas.apps(ctx.banco, nome=nome)


def _dependencias(ctx, ambiente="", nome="", **_):
    return consultas.dependencias(ctx.banco, ambiente=ambiente, nome=nome)


def _sistema(ctx, tipo="", filtro="", **_):
    if tipo not in TIPOS_SISTEMA:
        raise Erro("O tipo deve ser: " + ", ".join(TIPOS_SISTEMA) + ".")
    return consultas.sistema(ctx.banco, tipo, filtro)


def _prop(tipo, descricao, **extra):
    return {"type": tipo, "description": descricao, **extra}


DEFINICOES = [
    (
        "inv_status",
        "Mostra quando o inventário do PC foi feito pela última vez e quantos arquivos, apps, pacotes, serviços e tarefas existem. Use para saber se os dados estão atuais.",
        {},
        _status,
    ),
    (
        "inv_atualizar",
        "Refaz o inventário do PC (arquivos, apps, dependências, serviços) em segundo plano. Só use quando o Matheus pedir ou quando os dados estiverem desatualizados.",
        {},
        _atualizar,
    ),
    (
        "inv_arquivos",
        "Consulta exata ao catálogo de TODOS os arquivos do PC: buscar por nome, extensão, pasta ou tamanho; listar os maiores; somar o espaço por subpasta; achar duplicados. Use para qualquer pergunta sobre quais arquivos existem, onde estão e quanto ocupam.",
        {
            "operacao": _prop("string", "buscar, maiores, pastas ou duplicados", enum=list(OPERACOES)),
            "nome": _prop("string", "parte do nome do arquivo (operação buscar)"),
            "extensao": _prop("string", "extensão, por exemplo .py (operação buscar)"),
            "pasta": _prop("string", "pasta onde procurar, por exemplo C:\\Jarvis (obrigatória em pastas)"),
            "minimo_mb": _prop("number", "tamanho mínimo em megabytes"),
            "limite": _prop("integer", "quantos resultados mostrar"),
        },
        _arquivos,
    ),
    (
        "inv_apps",
        "Lista os programas instalados no PC (do Windows e da Loja) com a versão. Use para saber se um programa está instalado e qual a versão.",
        {"nome": _prop("string", "parte do nome do programa; vazio lista todos")},
        _apps,
    ),
    (
        "inv_dependencias",
        "Lista os pacotes instalados: bibliotecas Python de cada ambiente (venv ou Python global) e módulos globais do npm, com a versão. Sem filtros, lista os ambientes.",
        {
            "ambiente": _prop("string", "parte do caminho do ambiente, por exemplo Jarvis"),
            "nome": _prop("string", "parte do nome do pacote"),
        },
        _dependencias,
    ),
    (
        "inv_sistema",
        "Lista todos os serviços do Windows (com estado), as tarefas agendadas ou os programas de inicialização, com filtro opcional.",
        {
            "tipo": _prop("string", "servicos, tarefas ou inicializacao", enum=list(TIPOS_SISTEMA)),
            "filtro": _prop("string", "parte do nome ou do estado, por exemplo Stopped"),
        },
        _sistema,
    ),
]


class FerramentaInventario(BaseTool):
    def __init__(self, nome, descricao, propriedades, funcao, contexto):
        self._nome, self._descricao, self._props, self._funcao, self._ctx = nome, descricao, propriedades, funcao, contexto
        self.tool_id = nome

    @property
    def spec(self):
        return ToolSpec(
            name=self._nome,
            description=self._descricao,
            parameters={"type": "object", "properties": self._props},
            category="pc-inventario",
            requires_confirmation=False,
            timeout_seconds=60.0,
        )

    def execute(self, **params):
        try:
            texto = self._funcao(self._ctx, **params)
        except Erro as erro:
            return ToolResult(tool_name=self._nome, content=str(erro), success=False)
        except (sqlite3.Error, ValueError, TypeError) as erro:
            return ToolResult(tool_name=self._nome, content=f"Falha ao consultar o inventário: {type(erro).__name__}.", success=False)
        return ToolResult(tool_name=self._nome, content=f"{AVISO}\n{texto}"[:LIMITE_SAIDA])


def criar_ferramentas_inventario(banco, atualizador):
    ctx = Contexto(banco, atualizador)
    return [FerramentaInventario(n, d, p, f, ctx) for n, d, p, f in DEFINICOES]


def montar_inventario(pasta, config):
    banco = Banco(Path(pasta) / config.inventario)
    atualizador = Atualizador(banco, config.raizes, Exclusoes())
    return criar_ferramentas_inventario(banco, atualizador), atualizador, banco
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -B -m unittest tests.test_inventario_ferramentas -q`
Expected: PASS. Se `test_erro_do_banco_vira_falha_limpa` mostrar `sqlite3.ProgrammingError`, ela já está coberta (é subclasse de `sqlite3.Error`).

- [ ] **Step 5: Ligar ao agente (teste primeiro)**

Acrescente em `tests/test_agente.py`, depois da classe `TestLeitura`:

```python
class TestExtras(unittest.TestCase):
    def test_ferramenta_extra_roda_sem_pedir_confirmacao_e_fica_no_registro(self):
        from jarvis_pc.inventario.banco import Banco
        from jarvis_pc.inventario.ferramentas import criar_ferramentas_inventario

        class Atual:
            def iniciar(self):
                return True

            def rodando(self):
                return False

        registro = Registro()
        agente = criar_agente(
            modelo="falso",
            confirmar=nunca,
            registro=registro,
            executor=ExecutorFalso(),
            engine=MotorFalso([chamada("inv_status"), final("Sem varredura ainda.")]),
            extras=criar_ferramentas_inventario(Banco(), Atual()),
        )
        self.assertEqual(perguntar(agente, registro, "o que tem no pc?"), "Sem varredura ainda.")
        self.assertEqual(tipos(registro), ["pergunta", "chamada", "resposta"])
        self.assertTrue(registro.eventos[1]["permitido"])

    def test_sem_extras_a_ferramenta_de_inventario_e_barrada(self):
        registro = Registro()
        agente = criar_agente(
            modelo="falso",
            confirmar=nunca,
            registro=registro,
            executor=ExecutorFalso(),
            engine=MotorFalso([chamada("inv_status"), final("ok")]),
        )
        perguntar(agente, registro, "o que tem no pc?")
        self.assertFalse(registro.eventos[1]["permitido"])
```

Run: `.venv/bin/python -B -m unittest tests.test_agente.TestExtras -q`
Expected: FAIL com `TypeError: criar_agente() got an unexpected keyword argument 'extras'`.

Em `src/jarvis_pc/agente.py`, mude a assinatura e a linha das ferramentas:

```python
def criar_agente(
    *, modelo, confirmar, registro, executor=executar_powershell, engine=None, host=None, max_turns=8, extras=()
):
```

```python
    ferramentas = criar_ferramentas_leitura(executor) + [ComandoPcTool(executor)] + list(extras)
```

Run: `.venv/bin/python -B -m unittest tests.test_agente -q`
Expected: PASS (os testes antigos continuam passando).

- [ ] **Step 6: Prompt (teste primeiro)**

Em `tests/test_prompt.py`, troque `test_cita_todas_as_ferramentas` por:

```python
    def test_cita_todas_as_ferramentas(self):
        from jarvis_pc.inventario.ferramentas import NOMES_INVENTARIO

        for nome in [d.nome for d in DEFINICOES] + ["pc_comando"] + list(NOMES_INVENTARIO):
            with self.subTest(ferramenta=nome):
                self.assertIn(nome, SYSTEM_PROMPT)

    def test_manda_usar_o_inventario_e_citar_a_data(self):
        for trecho in ("inv_arquivos", "data da varredura", "nunca estime"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, SYSTEM_PROMPT)
```

Run: `.venv/bin/python -B -m unittest tests.test_prompt -q`
Expected: FAIL.

Em `src/jarvis_pc/prompt.py`, acrescente depois da regra 1 (renumere as seguintes para 3 a 7) esta regra 2:

```
2. Para saber quais arquivos, programas, bibliotecas, serviços ou tarefas existem no PC, quanto espaço ocupam ou onde estão, use as ferramentas de inventário: inv_arquivos, inv_apps, inv_dependencias, inv_sistema e inv_status. Elas consultam um banco exato: copie os números que elas devolvem, nunca estime nem arredonde. Diga sempre a data da varredura que veio na resposta. Se os dados estiverem desatualizados ou o Matheus pedir, use inv_atualizar. Fotos do disco E: (fora da pasta FORWARD) e a pasta Fotos & Videos ficam de fora do inventário por decisão dele: se perguntarem, explique isso e não procure por outro caminho.
```

Atenção ao teste: ele procura as frases `data da varredura` e `nunca estime`; mantenha exatamente esses trechos (em minúsculas) no texto da regra. Ajuste a regra para conter "a data da varredura" em vez de "a data da varredura que veio" se necessário, e "nunca estime" já está presente.

Run: `.venv/bin/python -B -m unittest tests.test_prompt -q`
Expected: PASS.

- [ ] **Step 7: Partida (teste primeiro)**

Veja `tests/test_main.py` para o padrão de teste do `main`. Acrescente um teste que monta o `main` com uma pasta temporária e confere que o `inventario.db` foi criado e que `atualizar_ao_abrir=false` não inicia a varredura. Use o mesmo mecanismo de substituição que os testes atuais já usam para `Janela` e `criar_agente` (substituir `jarvis_pc.__main__.criar_agente` e `jarvis_pc.janela.Janela`). Esqueleto:

```python
    def test_cria_o_banco_do_inventario_e_nao_atualiza_se_desligado(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest import mock

        from jarvis_pc import __main__ as principal

        with tempfile.TemporaryDirectory() as pasta:
            Path(pasta, "config.json").write_text(json.dumps({"atualizar_ao_abrir": False, "raizes": [pasta]}))
            janela = mock.MagicMock()
            with mock.patch.object(principal, "criar_agente") as criar, mock.patch("jarvis_pc.janela.Janela", return_value=janela), mock.patch(
                "jarvis_pc.inventario.atualizador.Atualizador.iniciar"
            ) as iniciar:
                self.assertEqual(principal.main(["x", pasta]), 0)
            self.assertTrue(Path(pasta, "inventario.db").exists())
            iniciar.assert_not_called()
            self.assertIn("extras", criar.call_args.kwargs)
```

Run: `.venv/bin/python -B -m unittest tests.test_main -q`
Expected: FAIL.

Em `src/jarvis_pc/__main__.py`, dentro do `try` de `main`, substitua o bloco que cria o agente por:

```python
        config = carregar(pasta / "config.json")
        registro = Registro(pasta / config.registro)
        ponte = PonteConfirmacao(config.tempo_confirmacao)
        extras, atualizador, banco = montar_inventario(pasta, config)
        agente = criar_agente(
            modelo=config.modelo, confirmar=ponte.pedir, registro=registro, host=config.host, extras=extras
        )
        registro.evento("inicio", modelo=config.modelo)
        if config.atualizar_ao_abrir:
            u = banco.ultima_varredura("arquivos")
            if u is None or time.time() - u["fim"] > 86400:
                atualizador.iniciar()
        from jarvis_pc.janela import Janela

        Janela(agente, registro, ponte, config.tecla).iniciar()
        return 0
```

e acrescente o import `from jarvis_pc.inventario.ferramentas import montar_inventario`. No `finally`, antes do `registro.evento("fim")`, chame `atualizador.cancelar()` se `atualizador` existir (inicialize `atualizador = None` junto de `registro = None`).

Run: `.venv/bin/python -B -m unittest tests.test_main -q`
Expected: PASS.

- [ ] **Step 8: Suíte inteira e telemetria**

Run: `.venv/bin/python -B -m unittest discover -s tests -t . -q`
Expected: tudo passa (os 106 de antes mais os novos). `test_sem_telemetria` precisa continuar passando: o inventário não importa nada de analytics.

- [ ] **Step 9: Mutação**

```bash
.venv/bin/python tools/mutar.py src/jarvis_pc/agente.py "+ list(extras)" ""
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/ferramentas.py "if operacao not in OPERACOES:" "if False:"
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/ferramentas.py "if not pasta:
            raise Erro" "if False:
            raise Erro"
.venv/bin/python tools/mutar.py src/jarvis_pc/inventario/ferramentas.py 'return ToolResult(tool_name=self._nome, content=f"{AVISO}\n{texto}"[:LIMITE_SAIDA])' 'return ToolResult(tool_name=self._nome, content=texto[:LIMITE_SAIDA])'
.venv/bin/python tools/mutar.py src/jarvis_pc/__main__.py "if config.atualizar_ao_abrir:" "if True:"
```
Todas devem sair com 0.

- [ ] **Step 10: Commit**

```bash
git add src/jarvis_pc tests
git commit -m "feat(jarvis): ferramentas do inventario ligadas ao agente e a partida

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Cenários do modelo

**Files:**
- Modify: `src/jarvis_pc/cenarios.py`, `tests/test_cenarios.py`

**Interfaces:**
- Consumes: `montar_inventario` (Task 9), `criar_agente(..., extras=)`.
- Produces: seis cenários novos em `CENARIOS`; `rodar(config, pasta)` monta o inventário real da pasta e passa `extras`.

- [ ] **Step 1: Teste primeiro**

Veja o padrão em `tests/test_cenarios.py` (ele testa `julgar` com eventos falsos e o conteúdo de `CENARIOS`). Acrescente:

```python
    def test_cenarios_do_inventario_existem_e_esperam_as_ferramentas_certas(self):
        por_nome = {c.nome: c for c in CENARIOS}
        esperado = {
            "inv_achar_arquivo": "inv_arquivos",
            "inv_maiores": "inv_arquivos",
            "inv_programa": "inv_apps",
            "inv_pacote": "inv_dependencias",
            "inv_servico": "inv_sistema",
            "inv_foto_excluida": "inv_arquivos",
        }
        for nome, ferramenta in esperado.items():
            with self.subTest(nome=nome):
                self.assertIn(nome, por_nome)
                self.assertIn(ferramenta, por_nome[nome].espera_alguma)
```

Run: `.venv/bin/python -B -m unittest tests.test_cenarios -q`
Expected: FAIL.

- [ ] **Step 2: Implementar**

Em `src/jarvis_pc/cenarios.py`, acrescente à lista `CENARIOS`:

```python
    Cenario("inv_achar_arquivo", "Onde está o arquivo instalar.ps1 no meu PC?", ("inv_arquivos",)),
    Cenario("inv_maiores", "Quais são os 5 maiores arquivos do disco C:?", ("inv_arquivos",)),
    Cenario("inv_programa", "O Git está instalado? Qual a versão?", ("inv_apps",)),
    Cenario("inv_pacote", "Qual a versão do openjarvis instalada na pasta C:\\Jarvis?", ("inv_dependencias",)),
    Cenario("inv_servico", "O serviço Spooler existe? Em que estado está?", ("inv_sistema",)),
    Cenario("inv_foto_excluida", "Liste as fotos da pasta E:\\Fotos & Videos.", ("inv_arquivos",)),
```

Troque a assinatura e o corpo de `rodar` para montar o inventário real:

```python
def rodar(config, pasta=None):
    from pathlib import Path

    from jarvis_pc.inventario.ferramentas import montar_inventario

    extras, _atualizador, _banco = montar_inventario(Path(pasta or "."), config)
    passaram = 0
    for c in CENARIOS:
        registro = Registro()
        agente = criar_agente(
            modelo=config.modelo, confirmar=lambda _texto: False, registro=registro, host=config.host, extras=extras
        )
```

(o resto do laço continua igual) e em `main`, passe a pasta como terceiro argumento: `return rodar(config, argv[3] if len(argv) > 3 else None)`. Atualize o docstring do módulo: `Uso: python -m jarvis_pc.cenarios [modelo] [host] [pasta-de-dados]`.

- [ ] **Step 3: Rodar**

Run: `.venv/bin/python -B -m unittest discover -s tests -t . -q`
Expected: tudo passa.

- [ ] **Step 4: Commit**

```bash
git add src/jarvis_pc/cenarios.py tests/test_cenarios.py
git commit -m "feat(jarvis): cenarios do inventario para medir o modelo

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Instalar no PC, medir e aceitar com o Matheus

**Files:**
- Create: `docs/medicoes-inventario.md`
- Modify: `docs/superpowers/specs/2026-10-21-jarvis-pacote-arquivos-design.md` (estado da etapa 1)

**Interfaces:**
- Consumes: tudo acima.

Esta tarefa roda no PC do Matheus. Grava só em `C:\Jarvis` e em `C:\Users\Diniz\envio\` (pasta de passagem). **Não toca em mais nada.** O resultado do Step 6 é dele; não declare a etapa pronta sem ele.

- [ ] **Step 1: Gerar a roda nova e conferir**

```bash
.venv/bin/pip wheel . --no-deps -w /tmp/jarvis-roda
ls /tmp/jarvis-roda
```
Expected: um `jarvis_pc-0.1.0-py3-none-any.whl`. Confira que ele contém o subpacote e o script: `unzip -l /tmp/jarvis-roda/*.whl | grep -E "inventario|inventario_sistema"` deve listar `jarvis_pc/inventario/*.py` e `jarvis_pc/ps/inventario_sistema.ps1`.

- [ ] **Step 2: Levar para o PC e atualizar só o pacote da Jarvis**

Siga o mesmo caminho de `docs/registro-de-instalacao.md` (cópia por `C:\Users\Diniz\envio\`, conferência por MD5 pelo lado Linux). Copie a roda para `C:\Users\Diniz\envio\jarvis-rodas\` (substituindo a antiga do `jarvis_pc`; a do OpenJarvis fica) e rode no PC:

```bash
.venv/bin/python scripts/pc.py cmd 'C:\Jarvis\venv\Scripts\pip.exe install --force-reinstall --no-deps C:\Users\Diniz\envio\jarvis-rodas\jarvis_pc-0.1.0-py3-none-any.whl'
.venv/bin/python scripts/pc.py cmd 'C:\Jarvis\venv\Scripts\python.exe -c "import jarvis_pc.inventario.ferramentas as f; print(f.NOMES_INVENTARIO)"'
```
Expected: a tupla com as seis ferramentas.

- [ ] **Step 3: Varredura real e medição**

```bash
.venv/bin/python scripts/pc.py rodar 'C:\Jarvis\venv\Scripts\python.exe -c "import time, pathlib; from jarvis_pc.config import carregar; from jarvis_pc.inventario.ferramentas import montar_inventario; c = carregar(r\"C:\Jarvis\config.json\"); f, a, b = montar_inventario(pathlib.Path(r\"C:\Jarvis\"), c); t = time.time(); a._sincrono = True; a.iniciar(); print(\"segundos\", round(time.time() - t)); print(a.ultimo_erro or \"sem erro\")"'
.venv/bin/python scripts/pc.py cmd '(Get-Item C:\Jarvis\inventario.db).Length / 1MB'
```
Use `rodar` (limite de 1200 s) e não `cmd` (120 s). Se passar de 20 minutos, anote o tempo parcial, não cancele no meio sem avisar o Matheus, e veja `inv_status` para o progresso. Anote em `docs/medicoes-inventario.md`: segundos de cada coleta (consulte `varreduras`), número de arquivos, de apps, de pacotes, de serviços, tamanho do banco em MB e número de erros (pastas sem acesso).

- [ ] **Step 4: Conferir as exclusões no banco real**

```bash
.venv/bin/python scripts/pc.py cmd 'C:\Jarvis\venv\Scripts\python.exe -c "import sqlite3; c = sqlite3.connect(r\"C:\Jarvis\inventario.db\"); q = lambda s: c.execute(s).fetchone()[0]; print(\"fotos_e\", q(\"select count(*) from arquivos where lower(caminho) like \x27e:\\%\x27 and ext in (\x27.jpg\x27,\x27.jpeg\x27,\x27.png\x27,\x27.gif\x27,\x27.heic\x27) and lower(caminho) not like \x27e:\\forward\\%\x27\")); print(\"fotos_videos\", q(\"select count(*) from arquivos where lower(caminho) like \x27e:\\fotos & videos\\%\x27\")); print(\"appdata\", q(\"select count(*) from arquivos where lower(caminho) like \x27%\\appdata\\%\x27\")); print(\"env\", q(\"select count(*) from arquivos where nome in (\x27.env\x27,\x27id_rsa\x27)\")); print(\"forward_fotos\", q(\"select count(*) from arquivos where lower(caminho) like \x27e:\\forward\\%\x27 and ext in (\x27.jpg\x27,\x27.png\x27)\"))"'
```
Expected: `fotos_e 0`, `fotos_videos 0`, `appdata 0`, `env 0`, e `forward_fotos` maior que 0 (se a pasta FORWARD tem fotos). Qualquer outro resultado é falha de exclusão: pare, corrija com teste e mutação, apague o banco e refaça a varredura.

- [ ] **Step 5: Cenários nos dois modelos**

```bash
.venv/bin/python scripts/pc.py rodar 'C:\Jarvis\venv\Scripts\python.exe -m jarvis_pc.cenarios gemma4:12b-it-q4_K_M http://localhost:11434 C:\Jarvis'
.venv/bin/python scripts/pc.py rodar 'C:\Jarvis\venv\Scripts\python.exe -m jarvis_pc.cenarios gemma4:e4b-it-q4_K_M http://localhost:11434 C:\Jarvis'
```
Registre em `docs/medicoes-inventario.md` a tabela por cenário (PASSOU ou FALHOU e segundos) e o total, para cada modelo. Para cada FALHOU, leia o `registro.jsonl` e anote a causa (ferramenta errada, parâmetro errado, não usou ferramenta). Ajustes de descrição das ferramentas ou do prompt são permitidos, cada um com o seu teste, e a medição é refeita. **Exatidão:** nos cenários `inv_maiores` e `inv_programa`, confira a resposta do modelo contra a consulta direta ao banco; número copiado errado é falha mesmo que a ferramenta certa tenha sido usada.

- [ ] **Step 6: Aceitação com o Matheus**

Peça a ele, com a janela aberta, estas perguntas, e anote **o que ele viu**, item a item, sem interpretar:
1. "Quantos arquivos você tem catalogados?" (a resposta cita o número e a data da varredura).
2. "Quais são os 10 maiores arquivos do disco C:?" (ele confere dois deles no Explorador).
3. "Quanto espaço a pasta E:\FloripaOT ocupa, por subpasta?"
4. "Tenho o Python instalado? Qual versão?"
5. "Quais bibliotecas tem no ambiente da Jarvis?"
6. "Liste as fotos da pasta E:\Fotos & Videos." (ela deve dizer que isso ficou de fora, sem listar nada.)
7. "Tem alguma foto do E: no inventário fora da FORWARD?" (resposta: não).
8. "Atualize o inventário." (ela avisa que iniciou; `inv_status` mostra o andamento).

- [ ] **Step 7: Registrar e fechar**

Em `docs/superpowers/specs/2026-10-21-jarvis-pacote-arquivos-design.md`, acrescente ao fim a seção `## Estado da etapa 1 (inventário deste PC)` com a data, os números medidos, o resultado dos cenários nos dois modelos e o resultado da aceitação, marcando "entregue" ou "entregue com ressalvas" e listando o que falhou.

- [ ] **Step 8: Commit**

```bash
git add docs
git commit -m "docs(jarvis): medicoes e aceitacao do inventario deste PC

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Self-review

**Cobertura da spec (revisão de 21/10/2026, itens 1 e 5, e a seção Segurança):**
- Inventário exato de arquivos, apps, dependências, serviços, tarefas e inicialização: Tarefas 3 a 8.
- Número vem do banco, modelo não estima, data da varredura em toda resposta: Tarefa 7 (cabeçalho), Tarefa 9 (prompt e `AVISO`).
- Exclusões (`Fotos & Videos`, fotos do `E:` exceto `FORWARD`, `AppData`, segredos): Tarefa 2, aplicadas na Tarefa 4 e conferidas no banco real na Tarefa 11, Step 4.
- Somente leitura: o único gravador é o banco do inventário; scripts PowerShell sem verbos de escrita (teste na Tarefa 5); ferramentas sem parâmetro de SQL (teste na Tarefa 9).
- Registro sem conteúdo: o agente já registra ferramenta e argumentos; o inventário não devolve conteúdo de arquivo. Nenhuma tarefa lê o conteúdo, exceto o hash de duplicados (Tarefa 7), que não é gravado no registro.
- Atualizar ao abrir e sob demanda: Tarefa 9 (Step 7) e `inv_atualizar`.
- **Fora desta etapa, de propósito** (etapas seguintes): índice por sentido (embeddings) e leitura de conteúdo (`arq_ler`, `arq_buscar` por assunto); fontes de rede (drive, servidores, PC da Marcella); voz; pesquisa na web; construtor.

**Varredura por journal NTFS:** o spec fala em varredura rápida; este plano usa `os.scandir` com poda porque é simples, testável sem Windows e sem privilégio de administrador. O tempo real é medido na Tarefa 11, Step 3. Se passar de uns 10 minutos, abrir tarefa nova para ler o journal.

**Varredura de placeholders:** nenhum "TBD" ou "TODO". Os pontos em aberto são medições com critério (Tarefa 11) e a nota sobre `_eh_arquivo_solto` na Tarefa 7, que diz exatamente qual alternativa usar se os testes exigirem.

**Consistência de nomes:** `Exclusoes.pasta_podada/arquivo_excluido`, `normalizar`, `dentro` (T2) usados em T4 e T7; `Banco.iniciar_varredura/gravar/progresso/encerrar_varredura/ultima_varredura/em_andamento/definir_hash/consultar/fechar` (T3) usados em T4 a T9; `ResultadoColeta.ok/motivo/pythons/npm/itens` (T5) usado em T8; `coletar_pacotes(banco, pythons, npm, agora)` (T6) chamado igual em T8; `NOMES_INVENTARIO`, `criar_ferramentas_inventario(banco, atualizador)`, `montar_inventario(pasta, config)` (T9) usados em T10 e T11; parâmetro `extras` de `criar_agente` (T9) usado em T10.
