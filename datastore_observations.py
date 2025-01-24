import pandas as pd
import param
import panel as pn
import traceback

import bilan
import etp
import geo
import meteofrance

# Météo-France API
METEOFRANCE_API = 'DPPaquetObs'

# Fréquence des données climatiques
METEOFRANCE_FREQUENCE = 'horaire'

# Variables utilisées pour le calcul de l'ETP et du bilan hydrique 
VARIABLES_POUR_CALCULS = dict(
    **etp.VARIABLES_CALCUL_ETP,
    **bilan.VARIABLES_CALCUL_BILAN)
VARIABLES_POUR_CALCULS_SANS_ETP = VARIABLES_POUR_CALCULS.copy()
del VARIABLES_POUR_CALCULS_SANS_ETP['etp']

LARGEUR_BOUTONS = 450
PARAMS_TABULATOR = dict(
    disabled=True,
    pagination="local",
    page_size=8,
    stylesheets=[":host .tabulator {font-size: 10px;}"],
    width=LARGEUR_BOUTONS
)

class DataStoreObservations(pn.viewable.Viewer):
    application_id = param.String(
        doc="""Entrer l'Application ID de l'API Météo-France ici et cliquer ENTER..."""
    )
    lire_liste_stations = param.Boolean(
        default=False,
        doc="""Cliquer pour lire la liste des stations au lieu de la télécharger..."""
    )
    ref_station_name = param.String(
        doc="""Entrer le nom de la station de référence et cliquer ENTER..."""
    )
    ref_station_altitude = param.Number(
        bounds=(0., None), default=None,
        doc="""Entrer l'altitude de la station de référence..."""
    )
    ref_station_lat = param.Number(
        bounds=(-90, 90.), default=None,
        doc="""Entrer la latitude de la station de référence..."""
    )
    ref_station_lon = param.Number(
        bounds=(-180., 180.), default=None,
        doc="""Entrer la longitude de la station de référence..."""
    )
    nn_rayon_km = param.Number(
        softbounds=(1., 100.), bounds=(0., 1000.), step=1.,
        doc="""Entrer la distance maximale des stations à la référence..."""
    )
    lire_donnee_liste_stations = param.Boolean(
        default=False,
        doc="""Cliquer pour lire la donnée météo pour la liste des stations au lieu de la télécharger..."""
    )
    date_deb = param.Date(
        doc="""Date UTC de début de la période météo de 24 h (calculée à partir de la date de fin)"""
    )
    date_fin = param.Date(
        doc="""Entrer la date UTC de fin de la période météo de 24 h (YYYY-mm-dd HH:MM:SS)..."""
    )
    lire_dernieres24h = param.Boolean(
        doc="""Cliquer pour récupérer les dernières 24 h de donnée météo..."""
    )
    lire_donnee_ref = param.Boolean(
        default=False,
        doc="""Cliquer pour lire la donnée météo pour la station de référence au lieu de la télécharger..."""
    )
    recuperation_donnee_liste_stations_faite = param.Boolean(default=False)
    recuperation_donnee_ref_faite = param.Boolean(default=False)
    selection_stations_plus_proches_faite = param.Boolean(default=False)
    recuperation_liste_stations_faite = param.Boolean(default=False)
    
    def __init__(self, **params):
        super().__init__(**params)
    
        if "date_deb" in params:
            raise ValueError("Le paramètre 'date_deb' ne peut pas être changé, "
                             "car la date de début est calculée à partir de la date de fin "
                             "pour définir une période météo de 24 h.") 
            
        # Initialisation d'un client pour accéder à l'API Météo-France
        self._client = meteofrance.Client(METEOFRANCE_API)
        
        # Donnée
        self.tab_liste_stations = pn.widgets.Tabulator(
            pd.DataFrame(), frozen_columns=[self._client.id_station_label],
            **PARAMS_TABULATOR)
        self.tab_liste_stations_nn = pn.widgets.Tabulator(
            pd.DataFrame(), frozen_columns=[self._client.id_station_label],
            **PARAMS_TABULATOR)
        self.tab_meteo = pn.widgets.Tabulator(
            pd.DataFrame(), frozen_columns=[self._client.id_station_donnee_label,
                                            self._client.time_label],
            **PARAMS_TABULATOR)
        self.tab_meteo_ref_heure_si = pn.widgets.Tabulator(
            pd.DataFrame(), frozen_columns=[self._client.time_label],
            **PARAMS_TABULATOR)
        self.tab_meteo_ref_si = pn.widgets.Tabulator(
            pd.DataFrame(), **PARAMS_TABULATOR)
        
        # Widget de lecture des données
        self._lire_liste_stations_widget = pn.widgets.Checkbox.from_param(
            self.param.lire_liste_stations,
            name="Lire la liste des stations")
        self._lire_donnee_liste_stations_widget = pn.widgets.Checkbox.from_param(
            self.param.lire_donnee_liste_stations,
            name="Lire la donnée pour la liste des stations")
        self._lire_donnee_ref_widget = pn.widgets.Checkbox.from_param(
            self.param.lire_donnee_ref,
            name="Lire la donnée pour la station de référence")

        # Widget pour lire les jeux de donnée ou non
        self._sortie_lire_liste_stations = pn.bind(
            self._montrer_lire_liste_stations_widget,
            self._lire_donnee_liste_stations_widget, self._lire_donnee_ref_widget)
        self._sortie_lire_donnee_liste_stations = pn.bind(
            self._montrer_lire_donnee_liste_stations_widget,
            self._lire_donnee_ref_widget)

        # Widgets pour l'Application ID
        self._application_id_widget = pn.widgets.TextInput.from_param(
            self.param.application_id, name="Application ID Météo-France")
        self._sortie_entrer_application_id = pn.bind(
            self._entrer_application_id, self.param.application_id)

        # Widgets pour la liste des stations
        self._sortie_recuperer_liste_stations = pn.bind(
            self._montrer_liste_stations_widgets, self.param.application_id)
        self._bouton_liste_stations = pn.widgets.Button(
            button_type='primary', width=LARGEUR_BOUTONS)
        self._sortie_liste_stations = pn.bind(
            self._recuperer_liste_stations, self._bouton_liste_stations)
        
        # Widgets pour la station de référence
        self._ref_station_name_widget = pn.widgets.TextInput.from_param(
            self.param.ref_station_name,
            name="Nom de la station de référence")
        self._ref_station_altitude_widget = pn.widgets.FloatInput.from_param(
            self.param.ref_station_altitude,
            name="Altitude de la station de référence")
        self._ref_station_lat_widget = pn.widgets.FloatInput.from_param(
            self.param.ref_station_lat,
            name="Latitude de la station de référence")
        self._ref_station_lon_widget = pn.widgets.FloatInput.from_param(
            self.param.ref_station_lon,
            name="Longitude de la station de référence")

        # Widgets pour les plus proches voisins
        self._sortie_selectionner_stations_plus_proches = pn.bind(
            self._montrer_stations_plus_proches_widgets,
            self.param.recuperation_liste_stations_faite)
        self._nn_rayon_km_widget = pn.widgets.EditableFloatSlider.from_param(
            self.param.nn_rayon_km,
            name="Distance maximale des stations à la référence (> 0)")
        self._bouton_liste_stations_nn = pn.widgets.Button(
            button_type='primary', width=LARGEUR_BOUTONS)
        self._sortie_bouton_liste_stations_nn = pn.bind(
            self._montrer_bouton_liste_stations_nn,
            self._ref_station_name_widget,
            self._ref_station_altitude_widget,
            self._ref_station_lat_widget,
            self._ref_station_lon_widget,
            self._nn_rayon_km_widget)
        self._sortie_liste_stations_nn = pn.bind(
            self._selectionner_stations_plus_proches, self._bouton_liste_stations_nn)

        # Widgets pour la définition de la période
        self._date_deb_widget = pn.widgets.DatetimePicker.from_param(
            self.param.date_deb, disabled=True,
            name="Date UTC de début de période météo de 24 h (calculée à partir de la date de fin)")
        self._date_fin_widget = pn.widgets.DatetimePicker.from_param(
            self.param.date_fin,
            name="Date UTC de fin de période météo de 24 h (YYYY-mm-dd HH:MM:SS)")
        self._lire_dernieres24h_widget = pn.widgets.Checkbox.from_param(
            self.param.lire_dernieres24h,
            name="Récupérer les dernières 24 h")
        self._sortie_date_deb = pn.bind(
            self._montrer_date_deb_widget, self._date_fin_widget)
        self._sortie_dates = pn.bind(
            self._montrer_dates_widgets, self._lire_dernieres24h_widget)
        self._sortie_choix_periode = pn.bind(
            self._montrer_choix_periode_widgets,
            self.param.selection_stations_plus_proches_faite,
            self._lire_donnee_liste_stations_widget)
        
        # Widgets pour la donnée météo pour la liste des stations
        self._bouton_donnee_liste_stations = pn.widgets.Button(
            button_type='primary', width=LARGEUR_BOUTONS)
        self._sortie_donnee_liste_stations = pn.bind(
            self._recuperer_donnee_liste_stations, 
            self._bouton_donnee_liste_stations)
        self._sortie_recuperer_donnee_liste_stations = pn.bind(
            self._montrer_donnee_liste_stations_widgets,
            self.param.selection_stations_plus_proches_faite)

        # Widgets pour la donnée météo pour la station de référence
        self._sortie_recuperer_donnee_ref = pn.bind(
            self._montrer_donnee_ref_widgets,
            self.param.recuperation_donnee_liste_stations_faite,
            self._lire_donnee_ref_widget)
        self._bouton_donnee_ref = pn.widgets.Button(
            button_type='primary', width=LARGEUR_BOUTONS)
        self._sortie_donnee_ref = pn.bind(
            self._recuperer_donnee_ref, self._bouton_donnee_ref)

    def _sortie_application_id(self):
        return pn.Column(
            pn.pane.Markdown("### Accès à l'API Météo-France"),
            self._application_id_widget,
            self._sortie_entrer_application_id
        )
        
    def _entrer_application_id(self, application_id):
        guide = pn.pane.Alert(
            "Application ID vide. L'entrer pour poursuivre...",
            alert_type="warning")
        sortie = guide
        if application_id:
            self._client.application_id = application_id
            sortie = pn.pane.Alert(
                "Client initialisé pour l'API Météo-France. Poursuivre...",
                alert_type="success")
        return sortie

    def _montrer_lire_liste_stations_widget(
        self, lire_donnee_liste_stations, lire_donnee_ref):
        self._lire_liste_stations_widget.disabled = False
        if lire_donnee_liste_stations or lire_donnee_ref:
            self._lire_liste_stations_widget.disabled = True
            self._lire_liste_stations_widget.value = True
    
        return self._lire_liste_stations_widget

    def _montrer_lire_donnee_liste_stations_widget(self, lire_donnee_ref):
        self._lire_donnee_liste_stations_widget.disabled = False
        if lire_donnee_ref:
            self._lire_donnee_liste_stations_widget.disabled = True
            self._lire_donnee_liste_stations_widget.value = True
    
        return self._lire_donnee_liste_stations_widget

    def _montrer_liste_stations_widgets(self, application_id):
        titre = pn.pane.Markdown(
            "### Récupération de la liste complète des stations")
        self._bouton_liste_stations.disabled = True
        self._bouton_liste_stations.name = (
            "D'abord donner l'Application ID...")
        if application_id:
            self._bouton_liste_stations.disabled = False
            self._bouton_liste_stations.name = (
                "Cliquer pour récupérer la liste des stations Météo-France")
        return pn.Column(
                titre,
                self._bouton_liste_stations,
                self._sortie_liste_stations
            )

    def _recuperer_liste_stations(self, event):
        sortie = None
        if event:
            # Écraser la liste des stations précédente
            self.tab_liste_stations.value = pd.DataFrame()
            try:
                filepath = meteofrance.get_filepath_liste_stations(
                    self._client)
                if self._lire_liste_stations_widget.value:
                    # Lecture de la liste des stations
                    self.tab_liste_stations.value = pd.read_csv(
                        filepath, index_col=self._client.id_station_label)
                    msg = pn.pane.Alert("Liste des stations lue.",
                                        alert_type="success")
                else:
                    # Demande de la liste des stations
                    section = meteofrance.SECTION_LISTE_STATIONS
                    response = meteofrance.demande(self._client, section)
                    self.tab_liste_stations.value = meteofrance.response_text_to_frame(
                        self._client, response, index_col=self._client.id_station_label)
                    # Sauvegarde de la liste des stations
                    self.tab_liste_stations.value.to_csv(filepath)
                    msg = pn.pane.Alert("Liste des stations téléchargée.", 
                                        alert_type="success")

                assert len(self.tab_liste_stations.value) != 0, (
                    "La table de la liste des stations est vide!")
                
                dst_filename, bouton_telechargement = self.tab_liste_stations.download_menu(
                    text_kwargs={'name': 'Entrer nom de fichier', 'value': filepath.name},
                    button_kwargs={'name': 'Télécharger la liste des stations'}
                )
                sortie = pn.Column(
                    msg,
                    self.tab_liste_stations,
                    dst_filename,
                    bouton_telechargement,
                )
                self.recuperation_liste_stations_faite = True
            except Exception as exc:
                sortie = pn.pane.Str(traceback.format_exc())
            return sortie
        else:
            return sortie

    def _montrer_bouton_liste_stations_nn(
        self, ref_station_name, ref_station_altitude,
        ref_station_lat, ref_station_lon, nn_rayon_km
    ):
        self._bouton_liste_stations_nn.disabled = False
        if (
            (ref_station_name is None) or
            (ref_station_altitude is None) or
            (ref_station_lat is None) or
            (ref_station_lon is None) or
            (nn_rayon_km == 0)
        ):
            self._bouton_liste_stations_nn.disabled = True
        return self._bouton_liste_stations_nn

    def _montrer_stations_plus_proches_widgets(
        self, recuperation_liste_stations_faite
    ):
        titre = pn.pane.Markdown(
            "### Sélection des stations les plus proches "
            "d'une station de référence")
        self._bouton_liste_stations_nn.disabled = True
        self._bouton_liste_stations_nn.name = (
            "D'abord récupérer la liste complète des stations...")
        sortie = pn.Column(
            titre,
            self._bouton_liste_stations_nn
        )
        if recuperation_liste_stations_faite:
            self._bouton_liste_stations_nn.disabled = False
            self._bouton_liste_stations_nn.name = (
                "Cliquer pour sélectionner les stations les plus proches")            
            sortie = pn.Column(
                titre,
                pn.pane.Markdown("#### Définition de la station de référence"),
                self._ref_station_name_widget,
                self._ref_station_altitude_widget,
                self._ref_station_lat_widget,
                self._ref_station_lon_widget,
                pn.pane.Markdown("#### Sélection des stations plus proches"),
                self._nn_rayon_km_widget,
                self._sortie_bouton_liste_stations_nn,
                self._sortie_liste_stations_nn
            )
        return sortie        

    def _selectionner_stations_plus_proches(self, event):
        sortie = None
        if event:
            # Écraser la liste des stations les plus proches précédente
            self.tab_liste_stations_nn.value = pd.DataFrame()
            try:
                ref_station_latlon = [self._ref_station_lat_widget.value,
                                      self._ref_station_lon_widget.value]
                self.tab_liste_stations_nn.value = geo.selection_stations_plus_proches(
                    self.tab_liste_stations.value, ref_station_latlon,
                    self._client.latlon_labels,
                    rayon_km=self._nn_rayon_km_widget.value)

                assert len(self.tab_liste_stations_nn.value) != 0, (
                    "La table de la liste des stations les plus proches est vide!")

                filepath = meteofrance.get_filepath_liste_stations_nn(
                    self._client, self.ref_station_name, self.tab_liste_stations_nn.value)
                dst_filename, bouton_telechargement = self.tab_liste_stations_nn.download_menu(
                    text_kwargs={'name': 'Entrer nom de fichier', 'value': filepath.name},
                    button_kwargs={'name': 'Télécharger la liste des stations les plus proches'}
                )
                sortie = pn.Column(
                    pn.pane.Alert("Stations les plus proches sélectionnées.",
                                  alert_type="success"),
                    self.tab_liste_stations_nn,
                    dst_filename,
                    bouton_telechargement
                )
                self.selection_stations_plus_proches_faite = True
            except Exception as exc:
                sortie = pn.pane.Str(traceback.format_exc())
            return sortie
        else:
            return sortie

    def _montrer_date_deb_widget(self, date_fin):
        if date_fin is not None:
            self._date_deb_widget.value = date_fin - pd.Timedelta(hours=23)
    
        return self._date_deb_widget

    def _montrer_dates_widgets(self, lire_dernieres24h):
        self._date_fin_widget.disabled = lire_dernieres24h
        if lire_dernieres24h:
            self._date_fin_widget.value = pd.Timestamp.now(
                tz=meteofrance.TZ).replace(minute=0, second=0, microsecond=0)

        return pn.Column(
            self._sortie_date_deb,
            self._date_fin_widget
        )

    def _montrer_choix_periode_widgets(
        self, selection_stations_plus_proches_faite,
        lire_donnee_liste_stations
    ):
        titre = pn.pane.Markdown(
            "### Définition de la période météo (stations et référence)")
        sortie_base = pn.Column(
            titre,
            self._lire_dernieres24h_widget
        )
        sortie = sortie_base
        self._lire_dernieres24h_widget.name = (
            "Récupérer les dernières 24 h (seule possibilité en téléchargement)")
        self._lire_dernieres24h_widget.value = True
        self._lire_dernieres24h_widget.disabled = True
        self._date_fin_widget.value = pd.Timestamp.now(
            tz=meteofrance.TZ).replace(minute=0, second=0, microsecond=0)
        self._date_deb_widget.value = self._date_fin_widget.value - pd.Timedelta(hours=23)
        if lire_donnee_liste_stations:
            self._lire_dernieres24h_widget.name = "Récupérer les dernières 24 h"
            if selection_stations_plus_proches_faite:
                self._lire_dernieres24h_widget.value = False
                self._lire_dernieres24h_widget.disabled = False
                sortie = pn.Column(
                    sortie_base,
                    self._sortie_dates,
                )
            
        return sortie

    def _montrer_donnee_liste_stations_widgets(
        self, selection_stations_plus_proches_faite):
        titre = pn.pane.Markdown(
            "### Obtention des données météo pour les stations voisines")
        self._bouton_donnee_liste_stations.disabled = True
        self._bouton_donnee_liste_stations.name = (
            "D'abord récupérer la liste des stations les plus proches...")
        if selection_stations_plus_proches_faite:
            self._bouton_donnee_liste_stations.disabled = False
            self._bouton_donnee_liste_stations.name = (
                "Cliquer pour récupérer la donnée météo pour les stations")
        return pn.Column(
                titre,
                self._bouton_donnee_liste_stations,
                self._sortie_donnee_liste_stations
            )

    def _recuperer_donnee_liste_stations(self, event):
        sortie = None
        if event:
            # Écraser donnee météo pour la liste des stations précédente
            self.tab_meteo.value = pd.DataFrame()
            try:
                filepath = meteofrance.get_filepath_donnee_periode(
                    self._client, self.ref_station_name, self.tab_liste_stations_nn.value,
                    self._date_deb_widget.value, self._date_fin_widget.value)
                if self._lire_donnee_liste_stations_widget.value:
                    # Lecture de la donnée météo pour la liste des stations
                    self.tab_meteo.value = pd.read_csv(
                        filepath, parse_dates=[self._client.time_label],
                        index_col=[self._client.id_station_donnee_label,
                                   self._client.time_label])
                    msg = pn.pane.Alert("Donnée météo pour la liste des stations lue.",
                                        alert_type="success")
                else:
                    # Demande de la donnée météo pour la liste des stations pour les dernières 24 h
                    variables = [self._client.variables_labels[METEOFRANCE_FREQUENCE][k]
                         for k in VARIABLES_POUR_CALCULS_SANS_ETP]
                    self.tab_meteo.value = meteofrance.compiler_donnee_des_departements(
                        self._client, self.tab_liste_stations_nn.value,
                        frequence=METEOFRANCE_FREQUENCE)[variables]
    
                    # Sauvegarde de la donnée météo pour la liste des stations
                    self.tab_meteo.value.to_csv(filepath)
                    msg = pn.pane.Alert("Donnée météo pour la liste des stations téléchargée.",
                                        alert_type="success")

                assert len(self.tab_meteo.value) != 0, (
                    "La table de la donnée météo pour la liste des stations est vide!")
                    
                dst_filename, bouton_telechargement = self.tab_meteo.download_menu(
                    text_kwargs={'name': 'Entrer nom de fichier',
                                 'value': filepath.name},
                    button_kwargs={'name': 'Télécharger la donnée météo pour la liste des stations'}
                )
                sortie = pn.Column(
                    msg,
                    self.tab_meteo,
                    dst_filename,
                    bouton_telechargement
                )
                self.recuperation_donnee_liste_stations_faite = True
            except Exception as exc:
                sortie = pn.pane.Str(traceback.format_exc())
            return sortie
        else:
            return sortie

    def _montrer_donnee_ref_widgets(
        self, recuperation_donnee_liste_stations_faite, lire_donnee_ref
    ):
        titre = pn.pane.Markdown(
            "### Interpolation des données météo pour la station de référence")
        self._bouton_donnee_ref.disabled = True
        self._bouton_donnee_ref.name = (
            "D'abord récupérer la donnée météo des stations...")
        if ((len(self.tab_meteo.value) > 0) or
            ((len(self.tab_liste_stations_nn.value) > 0) and lire_donnee_ref)):
            self._bouton_donnee_ref.disabled = False
            self._bouton_donnee_ref.name = (
                "Cliquer pour récupérer la donnée météo pour la référence")
        return pn.Column(
                titre,
                self._bouton_donnee_ref,
                self._sortie_donnee_ref
            )

    def _recuperer_donnee_ref(self, event):
        sortie = None
        if event:
            # Écraser donnee météo pour la station de référence précédente
            self.tab_meteo_ref_heure_si.value = pd.DataFrame()
            self.tab_meteo_ref_si.value = pd.DataFrame()
            try: 
                filepath = meteofrance.get_filepath_donnee_periode(
                    self._client, self.ref_station_name, self.tab_liste_stations_nn.value,
                    self._date_deb_widget.value, self._date_fin_widget.value, ref=True)
                if self._lire_donnee_ref_widget.value:
                    # Lecture de la donnée météo pour la station de référence
                    df_meteo_ref_heure = pd.read_csv(
                        filepath, parse_dates=[self._client.time_label],
                        index_col=self._client.time_label)
                    msg = pn.pane.Alert("Donnée météo pour la station de référence lue.",
                                        alert_type="success")
                else:
                    # Demande de la donnée météo pour la station de référence
                    df_meteo_ref_heure = geo.interpolation_inverse_distance_carre(
                        self.tab_meteo.value, self.tab_liste_stations_nn.value['distance'])
    
                    # Sauvegarde de la donnée météo pour la station de référence
                    df_meteo_ref_heure.to_csv(filepath)
                    msg = pn.pane.Alert("Donnée météo pour la station de référence interpolée.",
                                           alert_type="success")

                df_meteo_ref_heure_renom = meteofrance.renommer_variables(
                    self._client, df_meteo_ref_heure, METEOFRANCE_FREQUENCE)


                df_meteo_ref_heure_si = meteofrance.convertir_unites(
                    self._client, df_meteo_ref_heure_renom)

                df_meteo_ref_heure_si['etp'] = etp.calcul_etp(
                    df_meteo_ref_heure_si,
                    self._ref_station_lat_widget.value,
                    self._ref_station_lon_widget.value,
                    self._ref_station_altitude_widget.value)

                # Calcul des valeurs journalières des variables météo
                df_meteo_ref_si = pd.DataFrame()
                for variable, series in df_meteo_ref_heure_si.items():
                    df_meteo_ref_si[variable] = [
                        getattr(df_meteo_ref_heure_si[variable],
                                VARIABLES_POUR_CALCULS[variable])(0)]
                df_meteo_ref_si.index = [(
                    f"{df_meteo_ref_heure_si.index.min()} - "
                    f"{df_meteo_ref_heure_si.index.max()}")]

                self.tab_meteo_ref_heure_si.value = df_meteo_ref_heure_si
                self.tab_meteo_ref_si.value = df_meteo_ref_si

                assert len(self.tab_meteo_ref_si.value) != 0, (
                    "La table de la donnée météo pour la station de référence est vide!")
                
                dst_filename, bouton_telechargement = self.tab_meteo_ref_heure_si.download_menu(
                    text_kwargs={'name': 'Entrer nom de fichier', 'value': filepath.name},
                    button_kwargs={'name': 'Télécharger la donnée météo pour la station de référence'}
                )
                sortie = pn.Column(
                    msg,
                    self.tab_meteo_ref_heure_si,
                    dst_filename,
                    bouton_telechargement,
                )
                self.recuperation_donnee_ref_faite = True
            except Exception as exc:
                sortie = pn.pane.Str(traceback.format_exc())
            return sortie
        else:
            return sortie

    def __panel__(self):
        p = pn.Column(
            pn.pane.Markdown("## Récupération des données météo"),
            self._sortie_lire_liste_stations,
            self._sortie_lire_donnee_liste_stations,
            self._lire_donnee_ref_widget,
            self._sortie_application_id,
            self._sortie_recuperer_liste_stations,
            self._sortie_selectionner_stations_plus_proches,
            self._sortie_choix_periode,
            self._sortie_recuperer_donnee_liste_stations,
            self._sortie_recuperer_donnee_ref
        )

        return p
