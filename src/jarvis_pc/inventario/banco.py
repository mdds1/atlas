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
  modificado REAL, hash TEXT, varredura INTEGER NOT NULL, visto_ok INTEGER);
CREATE INDEX IF NOT EXISTS ix_arquivos_nome ON arquivos(nome);
CREATE INDEX IF NOT EXISTS ix_arquivos_ext ON arquivos(ext);
CREATE INDEX IF NOT EXISTS ix_arquivos_tamanho ON arquivos(tamanho);
CREATE TABLE IF NOT EXISTS apps (origem TEXT, nome TEXT, versao TEXT, editor TEXT, local TEXT, varredura INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS servicos (nome TEXT, exibicao TEXT, estado TEXT, inicio TEXT, varredura INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS tarefas (caminho TEXT, nome TEXT, estado TEXT, varredura INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS inicializacao (nome TEXT, comando TEXT, local TEXT, varredura INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS pacotes (ambiente TEXT, nome TEXT, versao TEXT, varredura INTEGER NOT NULL);
"""

# As consultas leem so estas views: elas enxergam apenas a ultima varredura
# bem-sucedida do tipo dono, nunca linhas de uma coleta falha ou cancelada.
VIEWS = """
DROP VIEW IF EXISTS arquivos_ok;
CREATE VIEW arquivos_ok AS SELECT * FROM arquivos
  WHERE visto_ok = (SELECT MAX(id) FROM varreduras WHERE tipo = 'arquivos' AND estado = 'ok');
DROP VIEW IF EXISTS apps_ok;
CREATE VIEW apps_ok AS SELECT * FROM apps
  WHERE varredura = (SELECT MAX(id) FROM varreduras WHERE tipo = 'sistema' AND estado = 'ok');
DROP VIEW IF EXISTS servicos_ok;
CREATE VIEW servicos_ok AS SELECT * FROM servicos
  WHERE varredura = (SELECT MAX(id) FROM varreduras WHERE tipo = 'sistema' AND estado = 'ok');
DROP VIEW IF EXISTS tarefas_ok;
CREATE VIEW tarefas_ok AS SELECT * FROM tarefas
  WHERE varredura = (SELECT MAX(id) FROM varreduras WHERE tipo = 'sistema' AND estado = 'ok');
DROP VIEW IF EXISTS inicializacao_ok;
CREATE VIEW inicializacao_ok AS SELECT * FROM inicializacao
  WHERE varredura = (SELECT MAX(id) FROM varreduras WHERE tipo = 'sistema' AND estado = 'ok');
DROP VIEW IF EXISTS pacotes_ok;
CREATE VIEW pacotes_ok AS SELECT * FROM pacotes
  WHERE varredura = (SELECT MAX(id) FROM varreduras WHERE tipo = 'pacotes' AND estado = 'ok');
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
            self._con.executescript(VIEWS)
            with self._con:
                self._con.execute("UPDATE varreduras SET estado = 'falhou' WHERE estado = 'rodando'")

    def fechar(self):
        with self._trava:
            self._con.close()

    def iniciar_varredura(self, tipo, agora):
        if tipo not in DONAS:
            raise ValueError(f"tipo de varredura desconhecido: {tipo}")
        with self._trava, self._con:
            cur = self._con.execute(
                "INSERT INTO varreduras (tipo, inicio, estado) VALUES (?, ?, 'rodando')", (tipo, agora)
            )
            return cur.lastrowid

    def gravar(self, tabela, vid, linhas):
        if tabela not in TABELAS:
            raise ValueError(f"tabela desconhecida: {tabela}")
        colunas = TABELAS[tabela]
        dados = [_linha(colunas, l) + (vid,) for l in linhas]
        with self._trava, self._con:
            if tabela == "arquivos":
                self._con.executemany(UPSERT_ARQUIVOS, dados)
            else:
                marcas = ", ".join("?" for _ in range(len(colunas) + 1))
                self._con.executemany(
                    f"INSERT INTO {tabela} ({', '.join(colunas)}, varredura) VALUES ({marcas})", dados
                )

    def progresso(self, vid, itens):
        with self._trava, self._con:
            self._con.execute("UPDATE varreduras SET itens = ? WHERE id = ?", (itens, vid))

    def encerrar_varredura(self, vid, estado, erros, agora):
        with self._trava, self._con:
            tipo = self._con.execute("SELECT tipo FROM varreduras WHERE id = ?", (vid,)).fetchone()["tipo"]
            self._con.execute(
                "UPDATE varreduras SET estado = ?, erros = ?, fim = ? WHERE id = ?", (estado, erros, agora, vid)
            )
            if estado == "ok":
                if tipo == "arquivos":
                    self._con.execute("UPDATE arquivos SET visto_ok = ? WHERE varredura = ?", (vid, vid))
                for tabela in DONAS[tipo]:
                    self._con.execute(f"DELETE FROM {tabela} WHERE varredura <> ?", (vid,))

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
        with self._trava, self._con:
            self._con.execute("UPDATE arquivos SET hash = ? WHERE caminho = ?", (valor, caminho))

    def consultar(self, sql, params=()):
        with self._trava:
            self._con.execute("PRAGMA query_only = ON")
            try:
                return self._con.execute(sql, params).fetchall()
            except (sqlite3.OperationalError, sqlite3.ProgrammingError) as erro:
                texto = str(erro).lower()
                if "readonly" in texto or "one statement" in texto:
                    raise ValueError("consultar aceita apenas SELECT") from erro
                raise
            finally:
                self._con.execute("PRAGMA query_only = OFF")
