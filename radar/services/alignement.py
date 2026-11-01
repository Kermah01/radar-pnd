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
