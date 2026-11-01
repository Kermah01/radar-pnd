"""Formatage des nombres à la française et des montants en FCFA."""
import unicodedata

NNBSP = "\u00a0"  # espace insécable (séparateur de milliers ; l espace fine manque à certaines polices)
NBSP = " "


def nombre(v, decimales=0):
    """1234567.8 -> '1 234 567,8' (espace fine insécable, virgule décimale)."""
    if v is None:
        return ""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    txt = f"{v:,.{decimales}f}"
    entier, _, dec = txt.partition(".")
    entier = entier.replace(",", NNBSP)
    if dec and decimales:
        dec = dec.rstrip("0")
    return f"{entier},{dec}" if dec else entier


def montant(millions, unite=True):
    """
    Montant exprimé en millions de FCFA -> texte en milliards (Md) ou millions (M).
    114839520 -> '114 839 Md FCFA' ; 1950 -> '2 Md FCFA' ; 26 115 -> '26,1 Md FCFA' ; 450 -> '450 M FCFA'
    """
    v = float(millions or 0)
    suffixe = f"{NBSP}FCFA" if unite else ""
    if v == 0:
        return f"0{NBSP}FCFA" if unite else "0"
    md = v / 1000
    if abs(md) >= 1:
        dec = 0 if abs(md) >= 100 else 1
        return f"{nombre(md, dec)}{NBSP}Md{suffixe}"
    dec = 0 if abs(v) >= 10 else 1
    return f"{nombre(v, dec)}{NBSP}M{suffixe}"


def milliards(millions, decimales=0):
    return nombre((millions or 0) / 1000, decimales)


def pourcent(part, tout, decimales=1):
    if not tout:
        return "0 %"
    return f"{nombre(part / tout * 100, decimales)}{NBSP}%"


def multiplicateur(g):
    if not g:
        return ""
    if g >= 99:
        return "nouvelle"
    return f"x{NBSP}{nombre(g, 1)}"


def normaliser(txt):
    """Minuscules sans accents, pour la recherche."""
    t = unicodedata.normalize("NFD", txt or "")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t.lower().replace("’", "'")
