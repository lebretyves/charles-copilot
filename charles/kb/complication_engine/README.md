# CHARLES - Complication Engine

Ce dossier pose l'ossature commune de la double analyse clinique de CHARLES.

Principe directeur:
- l'objet principal est la `complication`
- les `terrains` ne sont pas des detecteurs autonomes
- les terrains modifient legerement les algorithmes des complications:
  - sensibilite
  - priorite
  - seuils
  - poids de certains facteurs
  - niveau de confiance

Les complications doivent pouvoir etre evaluees a partir de trois flux d'evidence:
- `sources_officielles`
- `vitaldb_no_wave`
- `vitaldb_wave`

Le moteur final de complication fusionnera:
- le score referentiel issu des sources officielles
- le score observationnel sans waveforms
- le score observationnel avec waveforms
- les modulateurs de terrain
- les penalites de donnees manquantes

## Fichiers

- `canonical_schema.yaml`
  Schema commun que toutes les branches doivent respecter.
- `data_branches.yaml`
  Description des branches d'analyse et de ce qu'elles apportent.
- `complications_registry.yaml`
  Registre principal des complications prioritaires.
- `terrain_modifiers.yaml`
  Catalogue des terrains qui modulent les algorithmes de complication.
- `official_vitaldb_alignment.yaml`
  Table de correspondance canonique entre complications officielles et signaux VitalDB.
- `official_required_inputs.yaml`
  Liste des donnees que les sources officielles rendent necessaires pour une parite forte.
- `terrain_vitaldb_alignment.yaml`
  Table de correspondance entre terrains de la KB et champs/absences VitalDB.
- `gap_registry.yaml`
  Registre explicite des zones ou VitalDB et les sources officielles ne se recouvrent pas encore.
- `fusion_strategy.yaml`
  Regles de combinaison des scores et de gestion des donnees manquantes.
- `OFFICIAL_KB_MISSING_WITH_WITHOUT_WAVEFORMS.md`
  Rapport genere qui se concentre sur la branche `sources_officielles`, sans melanger VitalDB.
- `generate_official_missing_report.py`
  Script qui regenere ce rapport a partir du registre des complications et des inputs requis.
- `hypotension_model_design.yaml`
  Document de design cible pour un moteur hypotension pluridimensionnel, a etats, avec analyse mono-courbe et combinaison multi-courbes.
- `../learning/problems/hypotension_model.py`
  Premiere implementation robuste hors moteur legacy, avec etat latent, memoire d'episode, profils causaux, contradiction et confiance.
- `../learning/pipelines/evaluate_hypotension_model.py`
  Script d'evaluation offline VitalDB pour mesurer les temps de detection `early/probable/confirmed/critical`.
- `../learning/evaluation/hypotension_model_precise_cases/`
  Rapport et JSON de reference sur 2 cas avec waveforms et 2 cas sans waveforms.
- `../learning/evaluation/hypotension_model_precise_cases_v2/`
  Rapport v2 plus reactif sur les memes 4 cas, avec comparaison `v1 -> v2`.

## Regle de modelisation

Une complication doit toujours pouvoir repondre a ces questions:
- quelle evidence officielle la supporte ?
- quelles variables sans waveforms peuvent la suggerer ?
- quelles variables waveform peuvent la raffiner ?
- quels terrains changent sa detection ?
- quelles donnees manquent pour etre confiant ?

Un terrain doit toujours repondre a ces questions:
- quelles complications il influence
- quel type de modulation il applique
- a quelle intensite
- quelles variables supplementaires il rend importantes

## Ordre de travail recommande

1. Completer `complications_registry.yaml`
2. Completer `terrain_modifiers.yaml`
3. Mapper `sources_officielles -> complications`
4. Mapper `VitalDB no-wave -> complications`
5. Mapper `VitalDB wave -> complications`
6. Appliquer `fusion_strategy.yaml`

## Hypotension

La complication `hypotension_perioperatoire` a maintenant 3 niveaux documentes:

1. `hypotension_model_design.yaml`
   architecture cible pluridimensionnelle
2. `learning/problems/hypotension_model.py`
   premiere implementation robuste et defensive
3. `learning/evaluation/hypotension_model_precise_cases/`
   evaluation offline precise sur cas VitalDB

Sorties suivies par le module robuste:
- `risk_5min`
- `state`
- `severity`
- `refractory_flag`
- `cause_profile`
- `confidence`
- `explanation`

Le module se veut prudent:
- nettoyage explicite des pressions aberrantes
- degradation de confiance en cas de contradiction inter-signaux
- separation entre detection precoce et confirmation
- support waveform optionnel sans imposer les courbes
