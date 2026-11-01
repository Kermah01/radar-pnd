# Radar PND

Plateforme web qui accompagne l'ebook consacré au Plan National de Développement (PND) 2026-2030 de Côte d'Ivoire.
Elle classe les 1 480 actions prioritaires du Tome 3 selon le profil de chaque lecteur, restitue des fiches détaillées
(généalogie, coûts annuels, indicateurs), génère des paragraphes d'alignement et les exporte en Word ou en CSV.

Une réalisation d'**Analytics & Impact Consulting (AIC)**, *From data to impact*.

## Contenu

| Élément | Emplacement |
|---|---|
| Projet Django (réglages, URL, WSGI) | `radarpnd/` |
| Référentiel PND, radar, fiches, sélection, exports | `radar/` |
| Score de pertinence (9 profils types) | `radar/services/scoring.py` |
| Paragraphe d'alignement | `radar/services/alignement.py` |
| Projets et opportunités du Groupe consultatif (pages, classement par profil, CSV) | `radar/views_gc.py`, `radar/services/gcpnd.py` |
| Exports Word et CSV | `radar/services/export.py` |
| Comptes, codes d'accès, inscription | `comptes/` |
| Gabarits HTML | `templates/` |
| CSS, JS, police Plus Jakarta Sans (OFL, via @fontsource) et Chart.js 4.4.7 auto-hébergés | `static/` |
| Données extraites du Tome 3 | `data/pnd.json` |
| Projets et opportunités du Groupe consultatif (gcpnd.gouv.ci, consulté le 1er novembre 2026) | `data/gcpnd.json` |
| Captures d'écran (interface actuelle à 390 px et 1280 px) | `docs/screenshots/v2/` |

### Interface

Mobile d'abord : barre d'onglets en bas d'écran (Accueil, Radar, Explorer, Projets, Ma sélection), filtres en feuille
du bas, cartes sur mobile et tableaux à partir de 900 px, profil du radar en trois étapes, fiches avec panneaux repliables
et barre d'actions fixe. Tout fonctionne sans JavaScript (amélioration progressive) ; les animations respectent
`prefers-reduced-motion`.

### Pages

* **Publiques** : accueil, Tendances, pages Pilier et Secteur (aperçu limité à 5 actions), Explorer (aperçu limité à 15 lignes),
  Méthode RADAR, À propos et mentions.
* **Réservées aux lecteurs disposant d'un code actif** : Mon radar, Explorer complet (pagination, export CSV), fiches action,
  Ma sélection (notes, export Word et CSV), fiche Word d'une action.

### Groupe consultatif pour le financement du PND (GCPND)

Le Groupe consultatif s'est tenu à Abidjan les 8 et 9 juillet 2026 pour présenter le PND et mobiliser son financement
(jour 1 : partie publique avec les partenaires techniques et financiers ; jour 2 : secteur privé). Les projets publiés sur
gcpnd.gouv.ci sont des projets du PND déjà identifiés et mûris, présentés aux financeurs : ils ne forment pas la liste
exhaustive des projets du PND. La matrice d'actions prioritaires (Tome 3) reste le document qui détaille l'ensemble des
actions prévues. La plateforme présente les deux comme complémentaires (`templates/radar/partials/gc_explication.html`).

* **Projets GCPND** (`/projets-gcpnd/`) : 337 projets publics (207), en partenariat public-privé (98) et privés (32),
  filtrables par type, pilier, secteur, tranche de coût et mot-clé, avec lien vers la fiche officielle (PDF).
  Aperçu public limité aux 20 premières lignes (`APERCU_GC`) ; liste complète, fiches projet et export CSV avec un code actif.
* **Fiche projet** : coût estimatif, paragraphe d'alignement au PND, actions de la matrice du même secteur, autres projets
  du secteur et lien vers l'inscription et la prise de rendez-vous sur gcpnd.gouv.ci.
* **Opportunités** (`/opportunites/`) : 66 fiches sectorielles regroupées par pilier et secteur, dont 22 résumées
  (chiffres clés, segments, incitations, emplois). Intitulés publics, contenu et fiches détaillées avec un code actif.
* Les pages Pilier et Secteur, les fiches action, Mon radar (classement par profil) et l'accueil reprennent ces données.
* Les coûts du Groupe consultatif sont des **coûts estimatifs indicatifs**, à ne pas additionner aux coûts programmés de la matrice.

### Accès par code (vente via Chariow)

* Modèle `CodeAcces` : code `RPND-XXXX-XXXX`, formule *Découverte 3 mois* ou *Pro 12 mois*, utilisateur, date d'expiration.
* L'inscription exige un code valide. Un utilisateur déjà inscrit active un nouveau code depuis « Mon compte » : la durée
  s'ajoute à l'accès en cours.
* Générer des codes :
  * dans l'administration : *Codes d'accès* > bouton **Générer des codes** (formule, nombre, lot), puis action
    **Exporter les codes sélectionnés (CSV)** pour les charger dans Chariow ;
  * en ligne de commande : `python manage.py generer_codes --nombre 100 --formule decouverte --lot "Chariow lancement" --csv codes.csv`
* Les comptes administrateurs (`is_staff`) ont accès à tout sans code.

## Lancer en local

```bash
python -m venv .venv
source .venv/bin/activate            # Windows : .venv\Scripts\activate
pip install -r requirements.txt
export DEBUG=True                    # Windows : set DEBUG=True
python manage.py migrate
python manage.py load_pnd            # charge data/pnd.json (relançable sans doublon)
python manage.py load_gcpnd          # charge data/gcpnd.json, après load_pnd
python manage.py init_demo           # admin, compte démo et codes de démonstration
python manage.py runserver
```

Ouvrir http://127.0.0.1:8000. Sans `DATABASE_URL`, la base SQLite `db.sqlite3` est utilisée.

### Comptes de démonstration (créés par `init_demo`)

En local (`DEBUG=True`), `init_demo` crée un administrateur et un compte de démonstration avec des mots de passe de développement.
En production, aucun mot de passe par défaut n'existe : définissez `ADMIN_EMAIL` et `ADMIN_PASSWORD` dans les variables d'environnement Render.
Laissez `CREATE_DEMO=0` en production. Les codes d'accès commerciaux se génèrent depuis l'admin (« Générer des codes »).

### Tests

```bash
python manage.py test
```

Dix-sept tests couvrent le score de pertinence, le formatage des montants, le chargement idempotent des données
(PND et Groupe consultatif), le parcours d'inscription par code (code invalide, code déjà utilisé, prolongation, exports)
et la liste des projets du Groupe consultatif (filtres, tri, aperçu public, accès aux fiches, export CSV, radar).

## Déployer sur Render

1. Pousser ce dossier sur un dépôt GitHub (par exemple `Kermah01/radar-pnd`).
2. Sur Render : **New > Blueprint**, choisir le dépôt. Le fichier `render.yaml` crée :
   * la base PostgreSQL gratuite `radar-pnd-db` ;
   * le service web `radar-pnd` (build `./build.sh`, démarrage `gunicorn radarpnd.wsgi:application`).
3. Renseigner les variables marquées `sync: false` : `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `DEMO_PASSWORD`,
   `CHARIOW_URL` (lien de la page de vente de l'ebook), `CONTACT_EMAIL`.
4. Si le service a un autre nom que `radar-pnd`, ajuster `CSRF_TRUSTED_ORIGINS`
   (l'hôte Render est de toute façon ajouté automatiquement via `RENDER_EXTERNAL_HOSTNAME`).
   Pour un domaine personnalisé, l'ajouter à `ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS`.
5. Le build exécute : installation, `collectstatic`, `migrate`, `load_pnd`, `load_gcpnd`, puis `init_demo` (avec codes de démonstration
   si `CREATE_DEMO=1`, sans codes de démonstration si seul `ADMIN_PASSWORD` est défini).

Notes : la base PostgreSQL gratuite de Render expire après 30 jours, passez à une offre payante avant le lancement
commercial. Le service gratuit se met en veille après 15 minutes d'inactivité (premier chargement plus lent).

### Variables d'environnement

| Variable | Rôle | Défaut |
|---|---|---|
| `SECRET_KEY` (ou `DJANGO_SECRET_KEY`) | clé secrète Django | générée par Render |
| `DEBUG` (ou `DJANGO_DEBUG`) | mode débogage | `False` |
| `ALLOWED_HOSTS` (ou `DJANGO_ALLOWED_HOSTS`) | hôtes autorisés, séparés par des virgules | `localhost,127.0.0.1` |
| `CSRF_TRUSTED_ORIGINS` | origines de confiance (avec `https://`) | local |
| `DATABASE_URL` | base PostgreSQL | SQLite |
| `CHARIOW_URL` | lien « Acheter l'ebook » | vide (lien masqué) |
| `CONTACT_EMAIL` | adresse affichée en pied de page | `contact@aic-consulting.ci` |
| `APERCU_LIGNES` | lignes visibles dans l'explorateur public | `15` |
| `APERCU_GC` | projets du Groupe consultatif visibles dans l'aperçu public | `20` |

## Mettre à jour les données

Remplacer `data/pnd.json` (même structure), puis `python manage.py load_pnd`. La commande met à jour les enregistrements
existants et conserve les sélections et notes des utilisateurs. `--supprimer-absents` retire les actions et indicateurs
absents du nouveau fichier.

Pour le Groupe consultatif : remplacer `data/gcpnd.json`, puis `python manage.py load_gcpnd` (`--supprimer-absents`
retire les projets et opportunités absents). Les projets sont rattachés aux secteurs par leur code ; les six fiches
« Économie circulaire » (code `x.xx`) n'ont pas de secteur dans la matrice.

Particularités de la source : l'action `3.07.2.3.2` apparaît deux fois dans le Tome 3 avec des montants différents ; la
seconde occurrence est conservée sous le code `3.07.2.3.2-bis`. Le produit `5.06.4.0` n'a pas de libellé dans la source.

## Précautions

* Les montants sont des **coûts programmés** dans la matrice : ni des budgets votés, ni des marchés.
* Les données sont extraites automatiquement : certains libellés d'indicateurs sont imparfaits et affichés tels quels.
* Le score est une aide à la priorisation, jamais une probabilité d'obtenir un marché.
* AIC est un cabinet indépendant ; la plateforme n'utilise ni armoiries ni logos officiels et ne s'appuie que sur des
  données publiques.
