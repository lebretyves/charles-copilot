# CHARLES — Knowledge Base (KB)

Ce dossier contient le catalogue clinique exhaustif de CHARLES.

Chaque fichier YAML decrit un domaine de connaissances. Le backend charge ces fichiers
au demarrage et les utilise pour :

1. Contextualiser les alertes (quel terrain → quelle vigilance)
2. Alimenter le LLM (prompt enrichi par le contexte patient)
3. Definir les tendances de reference par population/pathologie/chirurgie
4. Aiguiller le scoring ML vers le bon modele si disponible

## Principe

- **Tout est declare ici, meme si le modele ML ou la tendance de reference n'existe pas encore.**
- Chaque entree a un champ `data_status` : `available`, `planned`, `research_needed`.
- Quand un modele est entraine ou une tendance validee, on passe le statut a `available`
  et on renseigne le chemin vers le modele ou la courbe de reference.
- Le simulateur pioche aussi dans ce catalogue pour generer des scenarios realistes.

## Structure

```
kb/
  populations.yaml           # Adulte, pediatrie, obstetrique, geriatrie
  terrains.yaml              # Comorbidites par systeme (cardio, respi, neuro...)
  surgeries.yaml             # Toutes les chirurgies par specialite
  complications_perop.yaml   # Complications transversales perop
  complications_by_surgery.yaml  # Complications specifiques par chirurgie
  algorithms.yaml            # Arbres decisionnels (intubation diff, anaphylaxie...)
  complication_engine/       # Ossature complication-first pour fusion sources officielles + VitalDB
  reference_trends.yaml      # Tendances de reference par population/situation
  drugs_anesthesia.yaml      # Agents anesthesiques, modeles PK, interactions
  monitoring_params.yaml     # Tous les parametres de monitorage connus
  scores_cliniques.yaml      # Scores utilises (ASA, Mallampati, Lee, Apfel...)
  data_sources.yaml          # Sources de donnees (VitalDB, MIMIC, CHU...)
  sources_officielles/       # Syntheses sourcees SFAR / MAPAR / SOFIA pour la KB
```

## Dossier `sources_officielles`

Le sous-dossier `sources_officielles/` n'est pas charge automatiquement par le
backend. Il sert de couche documentaire et algorithmique pour preparer:

- les futures extensions de `terrains.yaml`
- les futures extensions de `complications_perop.yaml`
- les signaux transverses officiels comme la capnographie ou le monitorage EEG/BIS
- les facteurs ponderes et regles composites du moteur d'alerte
- la documentation admin des seuils et complications

## Dossier `complication_engine`

Le sous-dossier `complication_engine/` fixe la logique de modelisation retenue:

- les complications sont les objets centraux
- les terrains sont des modulateurs, pas des detecteurs autonomes
- la fusion se fait entre trois branches:
  - `official_sources`
  - `vitaldb_no_wave`
  - `vitaldb_wave`

Cette couche sert a preparer:

- les futurs moteurs de score ponderes
- la fusion entre referentiel officiel et observation de donnees
- le mapping entre complications, terrains et donnees manquantes
- la correlation explicite entre `sources_officielles` et `VitalDB`
- les modules robustes de complication dedies, par exemple le moteur hypotension dans `learning/problems/hypotension_model.py`
- les campagnes d'evaluation offline associees, par exemple `learning/evaluation/hypotension_model_precise_cases/`

## Convention

- `id` : identifiant unique snake_case
- `label_fr` : libelle affichable en francais
- `label_en` : libelle anglais (pour recherche litterature)
- `data_status` : `available` | `planned` | `research_needed`
- `ml_model_path` : chemin vers le modele entraine (null si pas encore)
- `reference_trend_path` : chemin vers la courbe de reference (null si pas encore)
- `sources` : liste des references (SFAR, MAPAR, ASA, ESA, articles)
