# CHARLES — VitalDB Open Dataset

Données issues de VitalDB (https://vitaldb.net), le plus grand dataset open-access
de signaux vitaux peropératoires au monde.

## Licence
Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)

## Citation obligatoire
Lee HC, Park Y, Yoon SB, Yang SM, Park D, Jung CW.
VitalDB, a high-fidelity multi-parameter vital signs database in surgical patients.
Sci Data. 2022 Jun 8;9(1):279.
doi: 10.1038/s41597-022-01411-5. PMID: 35676300; PMCID: PMC9178032.

## Contenu du dossier

```
vitaldb/
  README.md                  # Ce fichier
  download_all.py            # Script de téléchargement complet
  clinical_metadata.csv      # 6 388 cas × 60+ colonnes cliniques  (~5 Mo)
  intraop_labs.csv           # Résultats labo peropératoires          (~20 Mo)
  track_index.csv            # Index de tous les tracks disponibles   (~2 Mo)
  catalog.yaml               # Index structuré des cas téléchargés
  cases/                     # Données numériques par cas (.parquet)
    case_00042.parquet
    ...
```

## Dataset summary
- 6 388 patients chirurgicaux (non-cardiaque)
- Départements: Chirurgie générale (4 930), Thoracique (1 111), Gynécologie (230), Urologie (117)
- 196 paramètres (signaux) disponibles
- Résolution: 500 Hz (waveforms), 1-7 sec (numériques)
- Appareils: Solar 8000M, Primus, BIS Vista, Orchestra, Vigileo, EV1000, etc.

## Utilisation dans CHARLES
- `clinical_metadata.csv` → alimente les KB YAML (terrains, chirurgies, populations)
- `intraop_labs.csv` → corrélation signaux/biologie pour pattern detection
- `cases/*.parquet` → mode replay simulateur (vrais signaux patients)
- `waveforms/*.parquet` -> replay ECG / pleth / ART / CO2 / AWP / EEG haute frequence

## Positionnement MVP
- CHARLES utilise ici des waveforms issues d'un dataset public de recherche.
- Le MVP est calibre pour de l'analyse et du replay de donnees publiques/anonymes.
- Aucun flux HL7 n'est necessaire tant que le projet reste sur ce perimetre dataset.
