# Nx Target Architecture

Ce document decrit une cible `Nx` pour le dossier `iade-monito-op`.

## Pourquoi ne pas initialiser Nx tout de suite

Le repo principal n'est pas une workspace `Nx` aujourd'hui. Initialiser `Nx` maintenant imposerait :

- un choix de package manager
- des dependances supplementaires
- possiblement des telechargements reseau
- une integration a arbitrer avec le frontend Vite deja en place

La bonne approche est donc de preparer d'abord les frontieres de domaine.

## Decoupage conseille

### Apps

- `clinician-web`
  Interface detaillee par patient et par salle.
- `wallboard`
  Supervision multi-salles avec focus sur alertes et disponibilite du signal.
- `telemetry-gateway`
  Adaptateurs d'entree pour les moniteurs, respirateurs et pousse-seringues.

### Libs

- `data-contracts`
  Types partages, schemas JSON, validateurs.
- `domain-vitals`
  Signaux standard : `HR`, `SpO2`, `BP`, `MAP`, `Temp`.
- `domain-ventilation`
  `EtCO2`, capno, `Vt`, `MV`, `Ppeak`, `PEEP`, mode ventilatoire.
- `domain-depth`
  `BIS`, `SQI`, `EMG`, `SR`, interpretation simple.
- `domain-aivoc`
  cible, modele PK, concentration predite plasma / site effet.
- `domain-alerting`
  regles, priorisation, hysteresis, acquittement.
- `ui-cards`
  widgets : numeriques, waveforms, alarmes, trend badges.
- `replay-simulator`
  rejeu de cas pour tests et formation.

## Flux de donnees

```text
Moniteurs / respirateurs / pousse-seringues
  -> telemetry-gateway
  -> normalisation
  -> event bus / websocket / MQTT
  -> clinician-web + wallboard
```

## Contrats minimaux

Il faut au minimum trois envelopes de donnees :

- `standard_monitoring_frame`
- `ventilator_frame`
- `anesthesia_drug_frame`

Le fichier [realtime-monitoring.example.json](/c:/Users/lebre/Desktop/Monitoring/postop-monitoring/iade-monito-op/realtime-monitoring.example.json) sert de base.

## Decision pratique

Quand on passera a l'implementation, je recommande :

1. `apps/telemetry-gateway` en Node.js ou Python selon les protocoles machines
2. `apps/clinician-web` en React
3. `wallboard` partageant les memes `libs/ui-*`

Cela evite de melanger acquisition bas niveau et rendu UI.

