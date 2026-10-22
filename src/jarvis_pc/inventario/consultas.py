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
