"""Utilitários de texto: decodificação de HTML, normalização e limpeza para Excel."""
from __future__ import annotations

import re
import unicodedata

ESPACOS = re.compile(r"\s+")

# Caracteres proibidos no XML do Excel (XML 1.0 só aceita \t, \n e \r abaixo de 0x20),
# além de surrogates soltos e non-characters.
CONTROLE_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ud800-\udfff￾￿]")

# Assinatura de mojibake: UTF-8 lido como Latin-1 ("Ã§", "Ã£", "Ã©", "Â ").
MOJIBAKE = re.compile(r"Ã[\x80-\xbfŒœŠšŸŽž‘-›€™]|Â[\x80-\xbf\xa0]")

META_CHARSET = re.compile(rb'<meta[^>]+charset=["\']?([^"\'>\s;]+)', re.I)


def decodificar_html(dados: bytes) -> str:
    """Decodifica bytes de um HTML do Lattes da forma mais fiel possível.

    UTF-8 vem primeiro porque é estrito: só aceita bytes UTF-8 válidos. O coletor salva
    em UTF-8, mas a página declara ISO-8859-1 no <meta>; confiar no <meta> gerava
    mojibake em todo arquivo. Latin-1 aceita qualquer byte, por isso fica por último.
    Só chama o ftfy (lento) quando há sinal real de mojibake.
    """
    tentativas = ["utf-8"]
    m = META_CHARSET.search(dados[:4096])
    if m:
        tentativas.append(m.group(1).decode("ascii", "ignore").lower())
    tentativas += ["cp1252", "iso-8859-1"]

    texto = None
    for enc in dict.fromkeys(tentativas):
        try:
            texto = dados.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if texto is None:  # inalcançável na prática (latin-1 aceita tudo)
        texto = dados.decode("utf-8", errors="replace")

    if MOJIBAKE.search(texto):
        texto = reparar_mojibake(texto)
    return texto


def reparar_mojibake(texto: str) -> str:
    try:
        import ftfy
    except ImportError:  # ftfy é opcional: sem ele, tenta o round-trip simples
        try:
            return texto.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return texto
    # NFC (e não NFKC) para não alterar dados: NFKC troca 'º' por 'o', '²' por '2'.
    return ftfy.fix_text(texto, normalization="NFC", uncurl_quotes=False)


def limpar(texto: str | None) -> str:
    """Colapsa espaços e tira as pontas."""
    if not texto:
        return ""
    return ESPACOS.sub(" ", texto).strip()


def sem_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def normalizar(texto: str | None) -> str:
    """Forma canônica para comparação: sem acento, minúsculo, só letras/números/espaço."""
    if not texto:
        return ""
    t = sem_acentos(str(texto)).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return t.strip()


def para_excel(texto: str) -> str:
    """Remove caracteres que quebram o XML do Excel e normaliza quebras de linha."""
    return CONTROLE_XML.sub("", texto.replace("\r\n", "\n").replace("\r", "\n"))


def slug(texto: str, maximo: int = 60) -> str:
    """Nome seguro para pasta/arquivo, legível (mantém acentos e espaços)."""
    t = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", texto)
    t = limpar(t).strip(". ")
    return t[:maximo] or "sem nome"
