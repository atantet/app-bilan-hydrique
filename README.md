# Application Bilan Hydrique

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/atantet/app-bilan-hydrique/HEAD?urlpath=panel/app_bilan_hydrique)

## Introduction

### Objectif

Estimer le besoin d'irrigation d'une culture sur un site particulier pour les dernières 24 heures à partir d'un bilan hydrique basé sur des observations Météo-France et d'une estimation de l'Évapo-Transpiration Potentielle (ETP) en suivant le [calcul de la FAO](https://www.fao.org/4/X0490E/x0490e06.htm).

### Méthodologie

- Récupération de la liste des stations météo.
- Sélection des stations les plus proches du site de référence où est localisée la culture.
- Téléchargement des observations Météo-France des dernières 24 h pour les stations les plus proches.
- Interpolation des variables météo au site de référence.
- Estimation de l'ETP à partir des observations météo horaires.
- Calcul des valeurs journalières.
- Estimation du bilan hydrique à partir de l'ETP et de la précipitation, et suivant des hypothèses concernant le sol et la culture (dont l'estimation de l'évapotranspiration maximale de la culture en fonction de son stade à partir des coefficients culturaux [ARDEPI](https://www.ardepi.fr/nos-services/vous-etes-irrigant/estimer-ses-besoins-en-eau/maraichage/)).

### Prérequis

Pour permettre la récupération des données Météo-France, il faut :

- Avoir ouvert un compte sur le [Portail Météo-France](https://portail-api.meteofrance.fr/).
- Avoir souscrit à [l'API Package Observations](https://portail-api.meteofrance.fr/web/fr/api/DonneesPubliquesPaquetObservation).
- Avoir copié son Application ID. Pour cela :
	- Se connecter au [Portail Météo-France](https://portail-api.meteofrance.fr/) ;
	- Aller à son [Dashboard](https://portail-api.meteofrance.fr/web/fr/dashboard) ;
	- Cliquer sur "Générer Token" dans la boite "Package Observations" ;
	- Copier l'Application IDs se trouvant dans le cadre noir sous "curl". L'Application ID est la longue chaine de caractères après "Authorization: Basic".

### Utilisation de l'application

- Lancer l'application. Pour cela, plusieurs possibilités (si vous ne savez pas laquelle choisir, choisissez la première) :
  - Sur le cloud, en lançant [MyBinder](https://mybinder.org/v2/gh/atantet/app-bilan-hydrique/HEAD?urlpath=panel/app_bilan_hydrique), en cliquant sur le bouton ci-dessus ;
  - En local, avec [Anaconda ou Miniconda](https://www.anaconda.com/download/success), en ouvrant un terminal et en :
    - clonant ce dépôt (la première fois) : `git clone https://github.com/atantet/app-bilan-hydrique.git`,
	- allant dans son dossier (à chaque fois) : `cd app-bilan-hydrique/`,
	- créant son environnement conda (la première fois) : `conda env create --file=environment.yml`,
    - activant l'environnement (à chaque fois) : `conda activate app_bilan_hydrique`,
    - lançant l'application (à chaque fois) : `panel serve app_bilan_hydrique.ipynb`.
- Une fois dans l'application, utiliser le bandeau de gauche pour récupérer les observations météo et les interpoler pour le site de référence en suivant les instructions.
- Défiler la fenêtre de droite pour afficher les observations météo et le bilan hydrique pour les dernières 24 h.

### Autres applications

D'autres applications sont également fournies sous formes de notebooks et de scripts Python :
- [bilan_hydrique_climatologie_horaire.ipynb](bilan_hydrique_climatologie_horaire.ipynb) : pour récupérer des observations Météo-France horaires consolidées sur une période passée (au-delà des dernières 24 h) et estimer l'ETP à partir de celles-ci par la méthode FAO.
- [bilan_hydrique_climatologie_quotidienne.ipynb](bilan_hydrique_climatologie_quotidienne.ipynb) : pour récupérer des observations Météo-France journalières consolidées sur une période passée (au-delà des dernières 24 h) incluant déjà une estimation de l'ETP par Météo-France.
- [comparaison_donnee_etp_calcul_etp.ipynb](comparaison_donnee_etp_calcul_etp.ipynb) : pour comparer l'ETP estimée via `bilan_hydrique_climatologie_horaire.ipynb` et l'ETP téléchargée via `bilan_hydrique_climatologie_quotidienne.ipynb` pour un même site de référence et sur une même période.
- [comparaison_interpolation_meteo_nn.ipynb](comparaison_interpolation_meteo_nn.ipynb) : pour comparer les observations quotidiennes (dont l'ETP) téléchargées via `bilan_hydrique_climatologie_quotidienne.ipynb` pour un même site de référence et sur une même période, mais pour différents nombres de stations les plus proches retenues dans l'interpolation au site de référence.
- [compilation_periodes_donnees_observations.ipynb](compilation_periodes_donnees_observations.ipynb) : pour compiler en un même jeu de données les observations téléchargées via l'application pour différentes périodes.
