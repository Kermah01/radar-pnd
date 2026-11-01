"""Exports Word (.docx) et CSV des fiches d'alignement."""
import csv
import io

from django.utils import timezone
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from ..models import ANNEES, COULEURS_PILIERS
from .alignement import paragraphe
from .formatage import montant, nombre

INK = RGBColor(0x15, 0x22, 0x33)
MUTED = RGBColor(0x5B, 0x67, 0x78)
ORANGE = RGBColor(0xE0, 0x6F, 0x00)
VERT = RGBColor(0x00, 0x8A, 0x55)

AVERTISSEMENT = (
    "Source : PND 2026-2030, Tome 3 (Matrice d'actions prioritaires et cadre de résultats), document public. "
    "Les coûts programmés ne sont ni des budgets votés ni des marchés publics. Données extraites automatiquement : "
    "vérifiez montants et indicateurs sur le document source avant tout dépôt officiel. Radar PND est un service "
    "indépendant d'Analytics & Impact Consulting (AIC), sans lien avec l'administration."
)


def _hex(c):
    c = c.lstrip("#")
    return RGBColor(int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def _shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill.lstrip("#"))
    tcPr.append(shd)


def _base_document(titre, sous_titre):
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    for side in ("left_margin", "right_margin"):
        setattr(sec, side, Cm(2.2))
    sec.top_margin, sec.bottom_margin = Cm(2), Cm(2)

    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10.5)
    st.font.color.rgb = INK
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    for name, size in (("Heading 1", 15), ("Heading 2", 12), ("Heading 3", 11)):
        h = doc.styles[name]
        h.font.name = "Calibri"
        h.font.size = Pt(size)
        h.font.bold = True
        h.font.color.rgb = INK

    # bandeau tricolore
    band = doc.add_table(rows=1, cols=3)
    band.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, fill in zip(band.rows[0].cells, ("F77F00", "FFFFFF", "009E60")):
        _shade(cell, fill)
        cell.paragraphs[0].paragraph_format.space_after = Pt(0)
        r = cell.paragraphs[0].add_run(" ")
        r.font.size = Pt(3)

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    r = p.add_run("RADAR PND  ·  Analytics & Impact Consulting")
    r.font.size = Pt(8.5)
    r.font.bold = True
    r.font.color.rgb = MUTED
    t = doc.add_paragraph()
    r = t.add_run(titre)
    r.font.size = Pt(20)
    r.font.bold = True
    r.font.color.rgb = INK
    if sous_titre:
        s = doc.add_paragraph()
        r = s.add_run(sous_titre)
        r.font.color.rgb = MUTED
        r.font.size = Pt(10)

    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.LEFT
    fr = footer.add_run("Radar PND · From data to impact · Les coûts programmés ne sont ni des budgets votés ni des marchés.")
    fr.font.size = Pt(7.5)
    fr.font.color.rgb = MUTED
    return doc


def _kv_table(doc, rows):
    tbl = doc.add_table(rows=0, cols=2)
    tbl.style = "Table Grid"
    for k, v in rows:
        cells = tbl.add_row().cells
        cells[0].width, cells[1].width = Cm(4.5), Cm(12)
        _shade(cells[0], "F2F4F7")
        rk = cells[0].paragraphs[0].add_run(k)
        rk.font.bold = True
        rk.font.size = Pt(9)
        rv = cells[1].paragraphs[0].add_run(v)
        rv.font.size = Pt(9.5)
    return tbl


def _fiche(doc, action, note="", indicateurs=None):
    indicateurs = action.indicateurs() if indicateurs is None else indicateurs
    h = doc.add_heading(level=1)
    rc = h.add_run(f"{action.code}  ")
    rc.font.color.rgb = _hex(COULEURS_PILIERS.get(action.pilier.numero, "#5B6B82"))
    h.add_run(action.label)

    _kv_table(doc, [
        ("Pilier", f"{action.pilier.numero}. {action.pilier.nom}"),
        ("Secteur", f"{action.secteur.code} {action.secteur.nom}"),
        ("Résultat sectoriel", action.secteur.resultat or ""),
        ("Effet", f"{action.effet.code} {action.effet.label}"),
        ("Produit", f"{action.produit.code} {action.produit.label}"),
        ("Structure responsable", action.structure or "Non précisée dans la matrice"),
        ("Coût programmé 2026-2030", montant(action.total)),
        ("Programmation annuelle", "  ·  ".join(f"{an} : {montant(c)}" for an, c in zip(ANNEES, action.couts))),
        ("Année de pic / tendance", f"{action.peak or 'n.d.'} / {action.trend}"),
        ("Familles d'opportunités", ", ".join(f.nom for f in action.familles.all()) or "Non classée"),
        ("Référence", f"PND 2026-2030, Tome 3, page {action.page}" if action.page else "PND 2026-2030, Tome 3"),
    ])

    doc.add_heading("Paragraphe d'alignement", level=2)
    p = doc.add_paragraph(paragraphe(action, indicateurs))
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.15
    hint = doc.add_paragraph()
    r = hint.add_run("Remplacez le texte entre crochets par la contribution propre de votre projet.")
    r.italic = True
    r.font.size = Pt(8.5)
    r.font.color.rgb = MUTED

    if indicateurs:
        doc.add_heading("Indicateurs rattachés", level=2)
        tbl = doc.add_table(rows=1, cols=5)
        tbl.style = "Table Grid"
        for cell, txt in zip(tbl.rows[0].cells, ("Id", "Indicateur", "Niveau", "Référence", "Cible 2030")):
            _shade(cell, "152233")
            r = cell.paragraphs[0].add_run(txt)
            r.font.bold = True
            r.font.size = Pt(8.5)
            r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        for ind in indicateurs[:10]:
            c = tbl.add_row().cells
            vals = (ind.ident, ind.label, getattr(ind, "niveau_label", ind.niveau),
                    f"{ind.base} ({ind.annee})" if ind.annee else ind.base, ind.cible_finale)
            for cell, v in zip(c, vals):
                r = cell.paragraphs[0].add_run(v or "")
                r.font.size = Pt(8.5)

    if note:
        doc.add_heading("Mes notes", level=2)
        for ligne in note.splitlines():
            doc.add_paragraph(ligne)


def _fin(doc):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    r = p.add_run(AVERTISSEMENT)
    r.font.size = Pt(8)
    r.font.color.rgb = MUTED


def docx_action(action, note=""):
    doc = _base_document("Fiche d'alignement au PND 2026-2030",
                         f"Générée le {timezone.localdate().strftime('%d/%m/%Y')}")
    _fiche(doc, action, note)
    _fin(doc)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def docx_selection(selections, utilisateur=""):
    total = sum(s.action.total for s in selections)
    doc = _base_document(
        "Ma sélection d'actions du PND 2026-2030",
        f"{len(selections)} action(s) · {montant(total)} programmés · générée le "
        f"{timezone.localdate().strftime('%d/%m/%Y')}" + (f" pour {utilisateur}" if utilisateur else ""),
    )
    if selections:
        doc.add_heading("Synthèse", level=2)
        tbl = doc.add_table(rows=1, cols=4)
        tbl.style = "Table Grid"
        for cell, txt in zip(tbl.rows[0].cells, ("Code", "Action", "Secteur", "Coût 2026-2030")):
            _shade(cell, "152233")
            r = cell.paragraphs[0].add_run(txt)
            r.font.bold = True
            r.font.size = Pt(8.5)
            r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        for s in selections:
            a = s.action
            c = tbl.add_row().cells
            for cell, v in zip(c, (a.code, a.label, a.secteur.nom, montant(a.total))):
                r = cell.paragraphs[0].add_run(v)
                r.font.size = Pt(8.5)
    for s in selections:
        doc.add_page_break()
        _fiche(doc, s.action, s.note)
    _fin(doc)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


ENTETES_CSV = (
    ["Code", "Intitulé", "Pilier", "Secteur", "Effet", "Produit", "Structure responsable"]
    + [f"Coût {an} (M FCFA)" for an in ANNEES]
    + ["Total 2026-2030 (M FCFA)", "Total (Md FCFA)", "Année de pic", "Tendance", "Familles", "Page Tome 3"]
)


def _ligne_csv(a):
    return (
        [a.code, a.label, f"{a.pilier.numero}. {a.pilier.nom}", f"{a.secteur.code} {a.secteur.nom}", a.effet.code,
         a.produit.code, a.structure]
        + [nombre(c, 1) for c in a.couts]
        + [nombre(a.total, 1), nombre(a.total / 1000, 3), a.peak or "", a.trend,
           " | ".join(f.nom for f in a.familles.all()), a.page or ""]
    )


def csv_actions(actions, avec_paragraphe=False, notes=None):
    """CSV séparé par des points-virgules, UTF-8 avec BOM (ouverture directe dans Excel)."""
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";")
    entetes = list(ENTETES_CSV)
    if notes is not None:
        entetes.append("Mes notes")
    if avec_paragraphe:
        entetes.append("Paragraphe d'alignement")
    w.writerow(entetes)
    for a in actions:
        row = _ligne_csv(a)
        if notes is not None:
            row.append(notes.get(a.id, ""))
        if avec_paragraphe:
            row.append(paragraphe(a))
        w.writerow(row)
    return buf.getvalue().encode("utf-8")
