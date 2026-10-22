"""O que nunca entra no inventário. É a única fonte dessas regras.

Decididas pelo Matheus em 21/10/2026: a pasta E:\\Fotos & Videos inteira e
qualquer foto em E:\\ ficam de fora (exceto sob E:\\FORWARD); AppData entra só
como inventário de apps; segredos nunca entram. Arquivo excluído não aparece
nem pelo nome. As comparações ignoram maiúscula e aceitam / ou \\.
"""
import fnmatch
import ntpath
import re
from dataclasses import dataclass

FOTOS = frozenset(
    {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".heif", ".tif", ".tiff", ".raw", ".cr2", ".nef", ".dng"}
)
PASTAS_SEGREDO = frozenset({".ssh", ".aws", ".gnupg"})
PASTAS_RUIDO = frozenset({"$recycle.bin", "system volume information"})
PADROES_NOME = ("*.pem", "*.key", "*.kdbx", "*.ppk", "id_rsa*", ".env", ".env.*", "cookies", "login data")
PALAVRAS_NOME = ("senha", "password", "token", "secret", "credenc", "credential")


def normalizar(caminho):
    """Forma canônica: sem prefixo \\\\?\\, sem barras repetidas, sem . e .., sem ponto/espaço final."""
    c = str(caminho).replace("/", "\\")
    if c.lower().startswith("\\\\?\\unc\\"):
        c = "\\\\" + c[8:]
    elif c.startswith("\\\\?\\"):
        c = c[4:]
    unc = c.startswith("\\\\")
    c = re.sub(r"\\+", r"\\", c)
    if unc:
        c = "\\" + c
    if not c:
        return ""
    c = ntpath.normpath(c)
    c = "\\".join(seg.rstrip(" .") for seg in c.split("\\"))
    return c.rstrip("\\").lower()


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
