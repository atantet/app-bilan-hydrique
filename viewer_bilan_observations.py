import pandas as pd
import panel as pn
import param
import plotly.graph_objects as go
from plotly.colors import DEFAULT_PLOTLY_COLORS
from plotly.subplots import make_subplots
import numpy as np
import traceback

import bilan
import meteofrance
from datastore_observations import DataStoreObservations

# Choix de la texture
DEFAUT_TEXTURE = 'Terres limoneuses'

# Fraction du sol occupé par des cailloux et graviers (entre 0 pour absence de cailloux et 1 pour totalité de cailloux)
DEFAUT_FRACTION_CAILLOUX = 0.1

# Part de la RU facilement utilisable (entre 1/2 et 2/3)
DEFAUT_RU_VERS_RFU = 0.67

# Fraction de la réserve utile du sol remplie d'eau (entre 0 pour une période sèche et 1 pour une période pluvieuse)
DEFAUT_FRACTION_RU_REMPLIE = 1.

# Besoin d'irrigation minimal à partir du quel irriguer (mm)
DEFAUT_SEUIL_IRRIGATION = 0.1

# Conversion de hauteur (mm) vers durée d'irrigation (min)
DEFAUT_HAUTEUR_VERS_DUREE_IRRIGATION = 10

# Distribution des variables par panel pour le subplot de la météo
DEFAULT_PANELS_VARIABLES = [
    [
        ['temperature_2m', 'humidite_relative'],
        ['rayonnement_global', 'vitesse_vent_10m']
    ],
    [
        ['precipitation', 'etp']
    ]
]

class View(pn.viewable.Viewer):
    datastore = param.ClassSelector(class_=DataStoreObservations)

class ViewerIntroduction(View):
    def __panel__(self):
        return pn.Column(
            pn.pane.Markdown(
                """
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
                - Estimation du bilan hydrique à partir de l'ETP et de la précipitation, et suivant des hypothèses concernant le sol et la culture (dont l'estimation de l'évapo-transpiration maximale de la culture en fonction de son stade à partir des coefficients culturaux [ARDEPI](https://www.ardepi.fr/nos-services/vous-etes-irrigant/estimer-ses-besoins-en-eau/maraichage/)).

                ### Prérequis
                
                Pour permettre la récupération des données Météo-France, il faut :

                - Avoir ouvert un compte sur le [Portail Météo-France](https://portail-api.meteofrance.fr/).
                - Avoir souscrit à [l'API Package Observations](https://portail-api.meteofrance.fr/web/fr/api/DonneesPubliquesPaquetObservation).
                - Avoir copié son Application ID. Pour cela :
                    - Se connecter au [Portail Météo-France](https://portail-api.meteofrance.fr/) ;
                    - Aller à son [Dashboard](https://portail-api.meteofrance.fr/web/fr/dashboard) ;
                    - Cliquer sur "Générer Token" dans la boite "Package Observations" ;
                    - Copier l'Application IDs se trouvant dans le cadre noir sous "curl". L'Application ID est la longue chaine de caractères après "Authorization: Basic".

                ### Utilisation

                - Utiliser le bandeau de gauche pour récupérer les observations météo et les interpoler pour le site de référence en suivant les instructions.
                - Défiler la fenêtre de droite pour afficher les observations météo et le bilan hydrique pour les dernières 24 h.
                """
            )
        )
        

class ViewerMeteoObservations(View):
    def __init__(self, **params):
        super().__init__(**params)

        self._sortie_plots = pn.bind(
            self._creer_plots, self.datastore.param.recuperation_donnee_ref_faite)

    def _creer_plot_meteo(
        self, df,
        panels_variables=DEFAULT_PANELS_VARIABLES,
        width=900, height=600
    ):
        rows = len(panels_variables)
        cols = len(panels_variables[0])
        axes = 2
        specs = [[{"secondary_y": True}] * cols] * rows
        fig = make_subplots(rows=rows, cols=cols, specs=specs)

        for irow, panels_variables_row in enumerate(panels_variables):
            for icol, panels_variables_row_col in enumerate(panels_variables_row):
                for axis, variable in enumerate(panels_variables_row_col):
                    name = f"{variable} [{meteofrance.UNITES[variable]}]"
                    row = irow + 1
                    col = icol + 1
                    k = ((irow * cols) + icol) * axes + axis
                    secondary_y = bool(axis)
                    params = dict(row=row, col=col, secondary_y=secondary_y)
                    color = DEFAULT_PLOTLY_COLORS[k % len(DEFAULT_PLOTLY_COLORS)]
                    fig.add_trace(
                        go.Scatter(x=df.index, y=df[variable], line_color=color),
                        **params)
                    fig.update_yaxes(
                        title_text=name, color=color, **params)
        
        fig.update_layout(showlegend=False, width=width, height=height)
    
        return pn.pane.Plotly(fig)

    def _creer_plots(self, recuperation_donnee_ref_faite):
        guide = pn.pane.Alert(
            "Récupérérer la donnée météo de la station de référence "
            "pour pouvoir représenter sa météo...", alert_type="warning")
        sortie = guide
        if recuperation_donnee_ref_faite:    
            try:
                df = self.datastore.tab_meteo_ref_heure_si.value
                assert len(df) != 0, (
                    "La table de la donnée météo pour la station de référence est vide!")
            
                sortie = self._creer_plot_meteo(df)
            except Exception as exc:
                sortie = pn.pane.Str(traceback.format_exc())    
        return sortie

    def __panel__(self):
        return pn.Column(
            pn.pane.Markdown("## Météo des dernières 24 h"),
            self._sortie_plots
        )
        

class ViewerBilanObservations(View):    
    def __init__(self, **params):
        super().__init__(**params)

        # Widgets
        margin = (5, 40)
        self._texture_widget = pn.widgets.Select(
            name='Texture', options=list(bilan.RU_PAR_CM_DE_TF),
            value=DEFAUT_TEXTURE, margin=margin)
        self._fraction_cailloux_widget = pn.widgets.EditableFloatSlider(
            name='Pierrosité',
            start=0., end=1., step=0.01,
            value=DEFAUT_FRACTION_CAILLOUX, margin=margin)
        self._fraction_ru_remplie_widget = pn.widgets.EditableFloatSlider(
            name="Fraction de la RU remplie d'eau",
            start=0., end=1., step=0.1,
            value=DEFAUT_FRACTION_RU_REMPLIE, margin=margin)
        self._ru_vers_rfu_widget = pn.widgets.EditableFloatSlider(
            name="Part de la RU facilement utilisable",
            start=0.5, end=0.7, step=0.05,
            value=DEFAUT_RU_VERS_RFU, margin=margin)
        self._seuil_irrigation_widget = pn.widgets.EditableFloatSlider(
            name="Besoin au-dessus duquel irriguer (mm)", 
            start=0., end=10., step=0.1,
            value=DEFAUT_SEUIL_IRRIGATION, margin=margin) 
        self._hauteur_vers_duree_irrigation_widget = pn.widgets.EditableIntSlider(
            name="Hauteur vers durée d'irrigation (mm min-1)", 
            start=1, end=180, step=1,
            value=DEFAUT_HAUTEUR_VERS_DUREE_IRRIGATION, margin=margin)
        list_kc = list(bilan.KC)
        self._culture_widget = pn.widgets.Select(
            name='Culture', options=list_kc, value=list_kc[0],
            margin=margin)
        self._stade_widget = pn.widgets.Select(
            name='Stade', options=list(bilan.KC[list_kc[0]]),
            margin=margin)

        # Liaison des stades au choix de culture
        self._sortie_maj_stades_culture_choisie = pn.bind(
            self._maj_stades_culture_choisie, self._culture_widget)

        # Liaison du plot au widgets
        self._sortie_plots = pn.bind(
            self._creer_plots, self.datastore.param.recuperation_donnee_ref_faite,
            self._texture_widget, self._fraction_cailloux_widget,
            self._fraction_ru_remplie_widget, self._ru_vers_rfu_widget,
            self._seuil_irrigation_widget,
            self._hauteur_vers_duree_irrigation_widget,
            self._culture_widget, self._stade_widget
        )
        
    def _maj_stades_culture_choisie(self, culture_choisie):
        self._stade_widget.options = list(bilan.KC[culture_choisie])
        self._stade_widget.value = list(bilan.KC[culture_choisie])[0]

        return self._stade_widget
    
    def _creer_plot_sol(self, s, width=500, height=400):
        idx_deb = 1
        idx_fin = 5
        x = s.index[idx_deb:]
        s_ru = s.iloc[idx_deb:idx_fin].astype(float).values
        y = np.concatenate([[s_ru[0]], s_ru[1:] - s_ru[:-1]])
        measure = ['absolute'] + ['delta'] * (idx_fin - idx_deb - 1)
        wf = go.Waterfall(x=x, y=y, measure=measure,
                          texttemplate='%{final:.1f}', cliponaxis=False)
        fig = go.Figure(wf)
        fig.update_layout(
            title="Réserve accessible aux racines (valeurs absolues)",
            yaxis_title="Hauteur (mm)",
            width=width,
            height=height
        )
    
        return pn.pane.Plotly(fig)

    def _creer_plot_besoin(self, s, width=500, height=400):
        idx_deb = 4
        idx_fin = 10
        x = s.index[idx_deb:]
        y = s.iloc[idx_deb:idx_fin].astype(float)
        measure = ['absolute'] + ['relative'] * (idx_fin - idx_deb - 2) + ['absolute']
        wf = go.Waterfall(x=x, y=y, measure=measure,
                          texttemplate='%{delta:.1f}', cliponaxis=False)
        fig = go.Figure(wf)
        fig.update_layout(
            title="Bilan hydrique (différences)",
            yaxis_title="Hauteur (mm)",
            width=width,
            height=height
        )

        return pn.pane.Plotly(fig)

    def _creer_plots(
        self, recuperation_donnee_ref_faite, texture, fraction_cailloux,
        fraction_ru_remplie, ru_vers_rfu,
        seuil_irrigation, hauteur_vers_duree_irrigation,
        culture, stade
    ):
        guide = pn.pane.Alert(
            "Récupérérer la donnée météo de la station de référence "
            "pour pouvoir exécuter le bilan hydrique...", alert_type="warning")
        sortie = guide
        if recuperation_donnee_ref_faite:
            try:
                df = self.datastore.tab_meteo_ref_si.value
                assert len(df) != 0, (
                    "La table de la donnée météo pour la station de référence est vide!")

                sortie = pn.Column(
                    pn.Row(self._texture_widget,
                           self._fraction_cailloux_widget),
                    pn.Row(self._fraction_ru_remplie_widget,
                           self._ru_vers_rfu_widget),
                    pn.Row(self._seuil_irrigation_widget,
                           self._hauteur_vers_duree_irrigation_widget),
                    pn.Row(self._culture_widget,
                           self._sortie_maj_stades_culture_choisie)
                )
            
                # Get the data
                df_bilan = bilan.calcul_bilan(
                    df.iloc[0],
                    texture, fraction_cailloux,
                    culture, stade,
                    fraction_ru_remplie, ru_vers_rfu,
                    seuil_irrigation=seuil_irrigation,
                    hauteur_vers_duree_irrigation=hauteur_vers_duree_irrigation)  

                plot_sol = self._creer_plot_sol(df_bilan)
                plot_besoin = self._creer_plot_besoin(df_bilan)
                plot_titre = pn.pane.Markdown(
                    f"### Pour {culture.lower()} au stade {stade.lower()}")

                sortie = pn.Column(
                    sortie,
                    plot_titre,
                    pn.Row(plot_sol, plot_besoin)
                )
    
                if df_bilan['irrigation']:
                    plot_irrigation = pn.pane.Markdown(
                        f"### Besoin d'arroser {df_bilan['duree_irrigation']:.0f} min")
                    sortie = pn.Column(
                        sortie,
                        plot_irrigation
                    )
            except Exception as exc:
                sortie = pn.pane.Str(traceback.format_exc())    
    
        return sortie
        
    def __panel__(self):
        return pn.Column(
            pn.pane.Markdown("## Exécution du bilan hydrique"),
            self._sortie_plots
        )
