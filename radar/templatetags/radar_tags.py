from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from ..models import COULEURS_PILIERS
from ..services import formatage

register = template.Library()


@register.filter
def fcfa(v):
    """Montant en millions de FCFA -> '12,3 Md FCFA'."""
    return formatage.montant(v)


@register.filter
def md(v):
    """Montant sans l'unité FCFA -> '12,3 Md'."""
    return formatage.montant(v, unite=False)


@register.filter
def md_nombre(v, decimales=0):
    return formatage.milliards(v, int(decimales))


@register.filter
def nombre(v, decimales=0):
    return formatage.nombre(v, int(decimales))


@register.filter
def md_gc(v):
    """Coût estimatif du Groupe consultatif -> '34,4 Md' ou 'Non défini'."""
    from ..services.gcpnd import md_gc as _md_gc

    return _md_gc(v)


@register.simple_tag
def badge_type(code, long=False):
    """Badge du type de projet du Groupe consultatif (Public, PPP, Privé)."""
    from ..models import ProjetGC

    txt = dict(ProjetGC.TYPES).get(code, code) if long else ProjetGC.TYPES_COURTS.get(code, code)
    return format_html('<span class="tbadge tb-{}">{}</span>', code.lower(), txt)


@register.filter
def multip(v):
    return formatage.multiplicateur(v)


@register.filter
def couleur(code):
    """Couleur d'un pilier à partir d'un numéro de pilier ou d'un code (5.01, 5.01.2.1.6)."""
    return COULEURS_PILIERS.get(str(code).split(".")[0], "#5B6B82")


@register.filter
def tendance_cls(t):
    return {"Hausse forte": "up", "Hausse": "up", "Nouvelle": "new", "Baisse": "down", "Stable": "flat"}.get(t, "flat")


@register.filter
def get(d, k):
    try:
        return d.get(k)
    except AttributeError:
        return None


@register.filter
def contient(liste, v):
    return v in (liste or [])


@register.simple_tag
def spark(couts, w=120, h=30, accent="var(--accent)"):
    """Mini-histogramme SVG des cinq années de programmation."""
    couts = [float(c or 0) for c in couts]
    m = max(couts + [1])
    bw = (w - 8) / 5
    rects = []
    for i, v in enumerate(couts):
        bh = max(1.0, v / m * h)
        fill = accent if v == m and v > 0 else "var(--spark)"
        rects.append(
            f'<rect x="{4 + i * bw + 2:.1f}" y="{h - bh:.1f}" width="{bw - 4:.1f}" height="{bh:.1f}" rx="1.5" fill="{fill}"/>'
        )
    return mark_safe(
        f'<svg class="spark" width="{w}" height="{h + 11}" viewBox="0 0 {w} {h + 11}" aria-hidden="true">'
        + "".join(rects)
        + f'<text x="4" y="{h + 10}">26</text><text x="{w - 15}" y="{h + 10}">30</text></svg>'
    )


@register.simple_tag
def badge_pilier(numero, texte=None):
    return format_html(
        '<span class="pil-badge" style="--pc:{}">{}</span>', COULEURS_PILIERS.get(str(numero), "#5B6B82"),
        texte or f"Pilier {numero}",
    )


@register.simple_tag(takes_context=True)
def url_param(context, **kwargs):
    """Reconstruit la chaîne de requête en remplaçant certains paramètres (pagination, tri)."""
    q = context["request"].GET.copy()
    for k, v in kwargs.items():
        if v in (None, ""):
            q.pop(k, None)
        else:
            q[k] = v
    s = q.urlencode()
    return f"?{s}" if s else "?"
