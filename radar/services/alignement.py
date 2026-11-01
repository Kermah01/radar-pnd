"""Paragraphe d'alignement au PND, à reprendre dans une offre, une note conceptuelle ou un dossier de financement."""
from .formatage import montant

A_COMPLETER = "[contribution chiffrée du projet]"


def indicateur_reference(indicateurs):
    """Premier indicateur exploitable : libellé, valeur de référence et cible 2030 renseignés."""
    for ind in indicateurs:
        if ind.label and ind.base and ind.cible_2030:
            return ind
    return None


def paragraphe(action, indicateurs=None):
    if indicateurs is None:
        indicateurs = action.indicateurs()
    sec = action.secteur
    pil = action.pilier
    t = (
        f"Le présent projet s'inscrit dans le Plan National de Développement (PND) 2026-2030, au titre du "
        f"pilier {pil.numero} ({pil.nom}), secteur {sec.code} {sec.nom}. Il contribue directement à l'action "
        f"{action.code} « {action.label} », rattachée au produit {action.produit.code} « {action.produit.label} » "
        f"et à l'effet {action.effet.code} « {action.effet.label} »."
    )
    resp = f", placée sous la responsabilité de {action.structure}," if action.structure else ""
    pic = f", avec un pic de programmation en {action.peak}" if action.peak else ""
    t += (
        f" Cette action{resp} bénéficie d'un coût programmé de {montant(action.total)} sur la période "
        f"2026-2030{pic}."
    )
    ind = indicateur_reference(indicateurs)
    if ind:
        annee = f" ({ind.annee})" if ind.annee else ""
        t += (
            f" Le projet contribuera à l'indicateur {ind.ident} « {ind.label} », dont la valeur de référence est de "
            f"{ind.base}{annee} et la cible fixée à {ind.cible_2030} en 2030, à travers {A_COMPLETER}."
        )
    else:
        t += f" Le projet y contribuera à travers {A_COMPLETER}."
    return t


def paragraphe_projet(projet, nb_actions=0, action_phare=None):
    """Paragraphe d'alignement d'un projet du Groupe consultatif sur le PND 2026-2030."""
    from .gcpnd import md_gc

    sec, pil = projet.secteur, projet.pilier
    cout = (f"d'un coût estimatif indicatif de {md_gc(projet.cout_millions)} FCFA" if projet.cout_millions is not None
            else "dont le coût estimatif n'est pas défini à ce stade")
    t = (
        f"Le projet {projet.code} « {projet.titre} », {cout}, est un projet du Plan National de Développement (PND) "
        f"2026-2030 présenté aux financeurs lors du Groupe consultatif pour le financement du plan (Abidjan, 8 et "
        f"9 juillet 2026), en tant que {projet.get_type_display().lower()}."
    )
    if sec and pil:
        t += f" Il s'inscrit dans le pilier {pil.numero} ({pil.nom}), secteur {sec.code} {sec.nom}."
        if sec.resultat:
            t += f" Il concourt au résultat sectoriel attendu : « {sec.resultat.rstrip('. ')} »."
        if nb_actions:
            t += (f" Dans la matrice d'actions prioritaires (Tome 3), ce secteur regroupe {nb_actions} actions pour un "
                  f"coût programmé de {montant(sec.total)} sur 2026-2030")
            if action_phare is not None:
                t += (f", la plus dotée étant l'action {action_phare.code} « {action_phare.label} » "
                      f"({montant(action_phare.total)})")
            t += "."
    elif pil:
        t += f" Il s'inscrit dans le pilier {pil.numero} ({pil.nom}) du PND."
    t += f" Le projet y contribuera à travers {A_COMPLETER}."
    return t
