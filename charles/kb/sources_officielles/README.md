# Sources officielles KB

Ce dossier reference les sources francaises retenues pour enrichir la KB clinique
de CHARLES a partir de sites officiels ou pedagogiques francophones cibles:

- `SFAR` pour les recommandations et referentiels normatifs
- `MAPAR` pour les protocoles pratiques, fiches urgences et supports operationnels
- `SOFIA` pour les cours/fiches IADE utiles en appui pedagogique
- `AP-HP / ReaMondor / services hospitalo-universitaires` pour completer les
  contextes terrain, voies aeriennes, ventilation et parcours perioperatoires complexes

Le contenu stocke ici est volontairement:

- paraphrase
- structure
- oriente exploitation algorithmique

Il ne s'agit pas d'un miroir integral des pages ou PDF sources. Chaque dossier
contient une synthese exploitable pour:

- enrichir la KB YAML
- definir des facteurs de risque
- proposer des variables candidates pour les scores ponderes
- preparer des regles d'alerte et des modulateurs de terrain

Une hierarchie documentaire est maintenant explicite:

- `normative_recommandations`
- `professionnelle_pratique_fr`
- `pedagogique_enseignement_medecins`

## Arborescence

```text
sources_officielles/
  catalog.yaml
  source_classes.yaml
  source_resource_catalog.yaml
  discovery_tools.yaml
  complication_source_landscape.yaml
  BIBLIOGRAPHY_SOURCES_FR.yaml
  BIBLIOGRAPHY_SOURCES_FR.md
  generate_structured_from_readme.ps1
  generate_bibliography.py
  sync_traceability.py
  terrains/
    <terrain_id>/
      README.md
      sources.yaml
      faits_source.yaml
      inferences_algo.yaml
      validation.yaml
  complications/
    <complication_id>/
      README.md
      sources.yaml
      faits_source.yaml
      inferences_algo.yaml
      validation.yaml
  signaux_transverses/
    <signal_id>/
      README.md
      sources.yaml
      faits_source.yaml
      inferences_algo.yaml
      validation.yaml
```

## Conventions

- `niveau_source`: `normatif`, `pratique`, `pedagogique`
- `confiance_algo`: `forte`, `mixte`, `a_confirmer`
- `sources.yaml`: references sourcees avec organisme, URL et date de consultation
- `faits_source.yaml`: uniquement les faits directement supportes ou resumes au plus pres de la source
- `inferences_algo.yaml`: deductions de design pour les scores, seuils et combinaisons
- `validation.yaml`: niveau de confiance, reste a completer, points a verifier
- `sync_traceability.py`: enrichit automatiquement les `faits_source.yaml` avec
  `source_title`, `source_url`, `source_organisme` et `source_class_id`
- `generate_bibliography.py`: agrege toutes les sources en une vraie bibliographie
  centralisee YAML + Markdown
- `discovery_tools.yaml`: outils de recherche bibliographique a utiliser pour trouver
  des sources, sans les traiter comme preuves cliniques finales
- `exploitation_algo`:
  - `entrees`: signaux ou donnees a exposer au moteur
  - `modulateurs`: facteurs qui changent la sensibilite ou les seuils
  - `sorties`: scores, alertes, priorites ou explications candidates
- `manques`: donnees absentes aujourd'hui dans CHARLES mais utiles plus tard

## Priorite d'usage

1. `SFAR` pour la couche normative
2. `MAPAR` pour les conduites pratiques et operationalisation
3. `SOFIA` pour completer la couche enseignement / IADE

Le script [generate_structured_from_readme.ps1](/d:/projet%20Iade/charles/kb/sources_officielles/generate_structured_from_readme.ps1)
regenere les fichiers structures a partir des README. Les dossiers raffines
manuellement peuvent ensuite etre completes fichier par fichier.

Voir aussi [catalog.yaml](/d:/projet%20Iade/charles/kb/sources_officielles/catalog.yaml).
Voir aussi [TABLEAU_COMPARAISON_SOURCES_COMPLICATIONS.md](/d:/projet%20Iade/charles/kb/sources_officielles/TABLEAU_COMPARAISON_SOURCES_COMPLICATIONS.md).
Voir aussi [source_classes.yaml](/d:/projet%20Iade/charles/kb/sources_officielles/source_classes.yaml).
Voir aussi [source_resource_catalog.yaml](/d:/projet%20Iade/charles/kb/sources_officielles/source_resource_catalog.yaml).
Voir aussi [discovery_tools.yaml](/d:/projet%20Iade/charles/kb/sources_officielles/discovery_tools.yaml).
Voir aussi [complication_source_landscape.yaml](/d:/projet%20Iade/charles/kb/sources_officielles/complication_source_landscape.yaml).
Voir aussi [BIBLIOGRAPHY_SOURCES_FR.yaml](/d:/projet%20Iade/charles/kb/sources_officielles/BIBLIOGRAPHY_SOURCES_FR.yaml).
Voir aussi [BIBLIOGRAPHY_SOURCES_FR.md](/d:/projet%20Iade/charles/kb/sources_officielles/BIBLIOGRAPHY_SOURCES_FR.md).
Voir aussi [generate_bibliography.py](/d:/projet%20Iade/charles/kb/sources_officielles/generate_bibliography.py).
Voir aussi [sync_traceability.py](/d:/projet%20Iade/charles/kb/sources_officielles/sync_traceability.py).
