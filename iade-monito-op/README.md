# IADE Monito Op

Ce dossier cadre un futur module de monitorage peroperatoire pour IADE et MAR.

L'objectif est de suivre en temps reel un patient sous anesthesie generale avec :

- monitorage standard peroperatoire
- profondeur d'anesthesie avec BIS
- monitorage du respirateur d'anesthesie
- suivi des pousse-seringues en AIVOC

Ce dossier ne transforme pas ce repo en workspace `Nx`. Il prepare un sous-projet dedie, avec un langage commun clinique + technique.

## 1. Perimetre clinique

### Monitorage standard a afficher

Le socle minimal vient des standards ASA de monitorage anesthesique :

- oxygenation : `FiO2`, `SpO2`
- ventilation : `EtCO2`, courbe capno, `RR`
- circulation : `ECG`, `HR`, `NIBP` ou `IBP`, `MAP`
- temperature : `Temp`

En pratique produit, on peut aussi afficher :

- agent anesthesique expiratoire si anesthesie volatile
- alarmes actives et alarmes inhibees
- qualite du signal capno et SpO2

### BIS / profondeur d'anesthesie

Le BIS est un indice derive de l'EEG frontal. Il aide a titrer la profondeur hypnotique, en particulier :

- pendant une anesthesie generale
- pendant une TIVA
- chez les patients a risque de conscience peroperatoire

Elements utiles a afficher :

- `bis`
- `sqi` : signal quality index
- `emg_db`
- `suppression_ratio`
- `raw_eeg_available`

Note clinique :

- le BIS ne remplace pas le monitorage standard
- un intervalle `40-60` est classiquement vise pendant l'entretien d'une anesthesie generale
- cette cible doit rester interpretee avec le contexte clinique, les drogues et la qualite du signal

### Monitorage respirateur d'anesthesie

Le respirateur doit etre visible avec les reglages, les mesures et les alarmes. Ce point est partiellement issu des standards de ventilation, puis complete par une inference produit basee sur les machines d'anesthesie courantes.

Donnees recommandees :

- `mode`
- `rr_set`, `rr_measured`
- `tv_set_ml`, `tv_exp_ml`
- `mv_l_min`
- `fio2`
- `etco2_mmhg`
- `peep_cm_h2o`
- `ppeak_cm_h2o`
- `pplat_cm_h2o`
- `pmean_cm_h2o`
- `compliance_ml_cm_h2o`
- `insp_exp_ratio`
- `trigger_l_min`
- `apnea_alarm`
- `disconnect_alarm`
- `high_pressure_alarm`

### AIVOC

L'AIVOC est l'anesthesie intraveineuse a objectif de concentration. Le pousse-seringue regle une concentration cible, puis calcule automatiquement le debit necessaire a partir d'un modele pharmacocinetique.

Deux usages doivent etre separes dans l'interface :

- hypnotique : le plus souvent propofol
- morphinique : le plus souvent remifentanil

Champs utiles :

- `drug`
- `pk_model`
- `target_type` : `plasma` ou `effect_site`
- `target_value`
- `target_unit`
- `predicted_plasma_concentration`
- `predicted_effect_site_concentration`
- `infusion_rate_ml_h`
- `total_dose_mg` ou `total_dose_ug`
- `pump_state`
- `last_adjustment_at`

## 2. Ce qu'il faut surveiller en priorite

### Niveau 1

- desaturation
- capno absente ou chute brutale de `EtCO2`
- hypotension
- bradycardie ou tachycardie
- deconnexion respirateur
- pression de voies aeriennes elevee

### Niveau 2

- BIS > `60` avec curare ou contexte a risque
- BIS < `40` de facon durable
- `SpO2` basse avec `FiO2` elevee
- `MV` basse
- derive progressive de `MAP`
- cible AIVOC non coherente avec l'effet observe

### Niveau 3

- signal BIS de mauvaise qualite
- artefacts EMG
- tension non mesuree depuis plus de 5 minutes
- temperature non remontee alors que le cas est long

## 3. Architecture Nx cible

L'idee la plus propre est de separer la collecte temps reel, le domaine clinique, et l'interface.

```text
iade-monito-op/
  apps/
    clinician-web/
    wallboard/
    telemetry-gateway/
  libs/
    data-contracts/
    domain-anesthesia/
    domain-monitoring/
    domain-alerting/
    ui-monitoring/
    ui-anesthesia/
    replay-simulator/
  docs/
```

### Roles proposes

- `apps/clinician-web` : vue detaillee d'une salle ou d'un patient
- `apps/wallboard` : vue multi-salles ou supervision bloc
- `apps/telemetry-gateway` : ingestion HL7, serial, websocket, MQTT ou vendor API
- `libs/data-contracts` : schemas TypeScript ou JSON Schema
- `libs/domain-anesthesia` : BIS, AIVOC, agent halogene, regles metier
- `libs/domain-monitoring` : vitaux, ventilateur, alarmes, normalisation des unites
- `libs/domain-alerting` : regles priorisees, hysteresis, acquittement
- `libs/ui-monitoring` : widgets reutilisables
- `libs/replay-simulator` : rejeu de cas pour demo, tests et formation

## 4. Ecrans a prevoir

### Vue salle

- bandeau patient : identite, salle, intervention, heure debut
- colonne vitaux : `HR`, `SpO2`, `NIBP/IBP`, `MAP`, `Temp`
- colonne ventilation : mode, `EtCO2`, `RR`, `Vt`, `MV`, pressions
- colonne hypnose : `BIS`, `SQI`, `EMG`, `SR`
- colonne AIVOC : propofol, remifentanil, cible, debit, modele
- bandeau alarmes : criticite, horodatage, acquittement

### Vue supervision bloc

- une carte par salle
- codes couleur sobres, pas uniquement rouge/vert
- resume des alarmes non acquittees
- badge si qualite du signal faible
- mise en avant des cas TIVA + BIS eleve ou capno absente

## 5. Limites et garde-fous

- ce dossier decrit un produit d'aide au monitorage, pas un dispositif medical certifie
- les seuils doivent etre validables par equipe clinique locale
- les champs exacts dependent des machines cibles : Drager, GE, Mindray, pousse-seringues compatibles AIVOC
- les donnees BIS et AIVOC doivent rester associees a un indicateur de qualite ou de source

## 6. Sources web utilisees

- ASA, Standards for Basic Anesthetic Monitoring:
  https://www.asahq.org/standards-and-practice-parameters/standards-for-basic-anesthetic-monitoring
- NICE, depth of anaesthesia monitors, usage recommande notamment en TIVA et chez les patients a risque:
  https://www.nice.org.uk/guidance/htg292
- NICE, recommandations detaillees:
  https://www.nice.org.uk/guidance/htg292/chapter/1-Recommendations
- Medtronic, BIS module specs (`BIS` 0-100, `SQI`, `EMG`, `SR`):
  https://www.medtronic.com/en-us/healthcare-professionals/products/patient-monitoring/oem-monitoring-solutions/brain-monitoring-oem-solutions/bis-loc-oem-module.html
- ScienceDirect, definition pratique de l'AIVOC et distinction cible plasma / site effet:
  https://www.sciencedirect.com/science/article/pii/S1279796008002635
- EM-Consulte, diffusion et usages de l'AIVOC en pratique anesthesique:
  https://www.em-consulte.com/article/920206/anesthesie-intraveineuse-a-objectif-de-concentrati

## 7. Point de depart recommande

Si on poursuit ce sous-projet, l'ordre logique est :

1. figer le contrat de donnees temps reel
2. choisir les machines sources et leurs protocoles
3. coder un `gateway` de normalisation
4. brancher une UI bloc operatoire
5. seulement ensuite, initialiser la vraie workspace `Nx`

