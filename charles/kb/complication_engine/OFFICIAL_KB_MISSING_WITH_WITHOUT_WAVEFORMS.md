# Manques KB Officielle Avec / Sans Waveforms

Date: 2026-04-01

Ce rapport reste strictement sur la branche `sources officielles`. Il ne fusionne pas encore l'evidence VitalDB dans les conclusions.

## Regle de lecture

- `sans waveforms`: numeriques monitor, contexte clinique, labs, terrain
- `avec waveforms`: morphologie capnographique ou signaux temporels manquants
- `hors monitorage`: donnees cliniques, therapeutiques ou contextuelles qu'aucune waveform ne comblera seule

## hypotension_perioperatoire

- Famille: `hemodynamique`
- No-wave cible dans le registry: `true`
- Waveforms utiles dans le registry: `true`

### Sans waveforms

Inputs requis:
- `Pression arterielle de reference` (`baseline_blood_pressure`): necessaire pour calculer une baisse relative conforme aux sources officielles [status: partial]
- `Duree cumulee sous seuil` (`cumulative_hypotension_duration`): les sources insistent sur le burden hypotensif et pas seulement le minimum ponctuel [status: missing]
Inputs utiles:
- `Horodatage des vasopresseurs` (`vasopressor_timing`): ameliore la distinction entre hypotension corrigee et hypotension refractaire [status: partial]
- `Index EEG traite type BIS/Entropy` (`processed_eeg_depth_index`): utile pour distinguer une hypotension de surprofondeur hypnotique d'une autre cause hemodynamique [status: missing]

### Apport potentiel des waveforms

- Cette complication est surtout contrainte par des donnees numeriques ou contextuelles.

### Ce qui manque encore meme avec waveforms

- `Duree cumulee sous seuil` (`cumulative_hypotension_duration`): les sources insistent sur le burden hypotensif et pas seulement le minimum ponctuel [status: missing]
- `Index EEG traite type BIS/Entropy` (`processed_eeg_depth_index`): utile pour distinguer une hypotension de surprofondeur hypnotique d'une autre cause hemodynamique [status: missing]

### Ce que les waveforms peuvent reellement combler

- Peu de gain attendu uniquement par morphologie waveform.

## choc_hemorragique_transfusion_massive

- Famille: `hemodynamique`
- No-wave cible dans le registry: `true`
- Waveforms utiles dans le registry: `true`

### Sans waveforms

Inputs requis:
- `Pertes sanguines horodatees` (`estimated_blood_loss_time_series`): necessaire pour distinguer suspicion precoce et aggravation rapide [status: partial]
- `Fibrinogene` (`fibrinogen`): les sources officielles donnent un seuil direct < 1,5 g/L [status: partial]
- `TP/TCA` (`coagulation_panel`): les sources utilisent TP < 40 % ou TP/TCA > 1,5 fois la normale [status: partial]
- `Calcemie ionisee` (`ionized_calcium`): necessaire pour couvrir la correction de l'hypocalcemie [status: partial]
Inputs utiles:
- `Contexte de controle chirurgical du saignement` (`surgical_hemostasis_context`): ameliore l'interpretation du choc hemorragique [status: missing]

### Apport potentiel des waveforms

- Cette complication est surtout contrainte par des donnees numeriques ou contextuelles.

### Ce qui manque encore meme avec waveforms

- `Contexte de controle chirurgical du saignement` (`surgical_hemostasis_context`): ameliore l'interpretation du choc hemorragique [status: missing]

### Ce que les waveforms peuvent reellement combler

- Peu de gain attendu uniquement par morphologie waveform.

## anaphylaxie_perioperatoire

- Famille: `hemodynamique_respiratoire`
- No-wave cible dans le registry: `true`
- Waveforms utiles dans le registry: `true`

### Sans waveforms

Inputs requis:
- `Horodatage du produit suspect` (`suspect_drug_timing`): le diagnostic officiel depend de la chronologie apres injection [status: missing]
- `Signes cutaneo-muqueux` (`cutaneous_signs`): participent au grade clinique d'anaphylaxie [status: missing]
- `Grade clinique d'anaphylaxie` (`clinical_grade`): utile pour la severite et la strategie adrenaline [status: missing]
- `Tendance d'oxygenation` (`oxygenation_trend`): les formes respiratoires imposent de suivre la cinetique de desaturation et pas seulement une SpO2 isolee [status: partial]
Inputs utiles:
- `Prelevements tryptase` (`tryptase_sampling`): utile pour la confirmation secondaire [status: missing]
- `Pression des voies aeriennes` (`airway_pressure`): renforce la lecture des formes avec bronchospasme associe [status: partial]

### Apport potentiel des waveforms

Inputs requis dependants des waveforms:
- `Capnographie ou pattern de bronchospasme` (`capnography_or_bronchospasm_pattern`): le CO2 et la forme de capno aident a objectiver la composante respiratoire de l'anaphylaxie [status: partial]

### Ce qui manque encore meme avec waveforms

- `Horodatage du produit suspect` (`suspect_drug_timing`): le diagnostic officiel depend de la chronologie apres injection [status: missing]
- `Signes cutaneo-muqueux` (`cutaneous_signs`): participent au grade clinique d'anaphylaxie [status: missing]
- `Grade clinique d'anaphylaxie` (`clinical_grade`): utile pour la severite et la strategie adrenaline [status: missing]
- `Prelevements tryptase` (`tryptase_sampling`): utile pour la confirmation secondaire [status: missing]

### Ce que les waveforms peuvent reellement combler

- `Capnographie ou pattern de bronchospasme` (`capnography_or_bronchospasm_pattern`): le CO2 et la forme de capno aident a objectiver la composante respiratoire de l'anaphylaxie [status: partial]

## bronchospasme_perioperatoire

- Famille: `respiratoire`
- No-wave cible dans le registry: `true`
- Waveforms utiles dans le registry: `true`

### Sans waveforms

Inputs requis:
- `Pression des voies aeriennes` (`airway_pressure`): necessaire pour appliquer les signes de gravite type > 40-45 cmH2O [status: available]
- `Tendance numerique de l'EtCO2` (`etco2_numeric_trend`): permet d'associer la baisse de l'EtCO2 a la modification de la forme capnographique [status: partial]
Inputs utiles:
- `Sibilants / auscultation` (`auscultation_or_wheeze`): ameliore la distinction bronchospasme vs cause mecanique [status: missing]
- `Tendance de la SpO2` (`spo2_trend`): utile pour caracteriser la gravite respiratoire et la reponse au traitement [status: partial]

### Apport potentiel des waveforms

Inputs requis dependants des waveforms:
- `Morphologie capnographique` (`capnography_shape`): les sources officielles et MAPAR insistent sur la courbe en requin [status: partial]

### Ce qui manque encore meme avec waveforms

- `Sibilants / auscultation` (`auscultation_or_wheeze`): ameliore la distinction bronchospasme vs cause mecanique [status: missing]

### Ce que les waveforms peuvent reellement combler

- `Morphologie capnographique` (`capnography_shape`): les sources officielles et MAPAR insistent sur la courbe en requin [status: partial]

## intubation_extubation_difficiles

- Famille: `voies_aeriennes`
- No-wave cible dans le registry: `true`
- Waveforms utiles dans le registry: `false`

### Sans waveforms

Inputs requis:
- `Nombre de tentatives` (`attempt_count`): la definition officielle d'intubation difficile depend du nombre de tentatives [status: missing]
- `Duree de tentative` (`attempt_duration`): necessaire pour l'alignement avec les definitions basees sur le temps [status: partial]
- `Contexte de risque d'extubation` (`extubation_risk_context`): les recommandations officielles couvrent aussi l'extubation difficile [status: missing]
Inputs utiles:
- `Cormack par tentative` (`cormack_per_attempt`): ameliore le niveau de precision sur les voies aeriennes difficiles [status: partial]
- `Confirmation capnographique apres prise de VA` (`etco2_confirmation_after_airway_management`): utile pour objectiver la ventilation efficace apres intubation ou ventilation de sauvetage [status: partial]

### Apport potentiel des waveforms

- Cette complication est surtout contrainte par des donnees numeriques ou contextuelles.

### Ce qui manque encore meme avec waveforms

- `Nombre de tentatives` (`attempt_count`): la definition officielle d'intubation difficile depend du nombre de tentatives [status: missing]
- `Contexte de risque d'extubation` (`extubation_risk_context`): les recommandations officielles couvrent aussi l'extubation difficile [status: missing]

### Ce que les waveforms peuvent reellement combler

- Peu de gain attendu uniquement par morphologie waveform.

## hypothermie_perioperatoire

- Famille: `thermique`
- No-wave cible dans le registry: `true`
- Waveforms utiles dans le registry: `false`

### Sans waveforms

Inputs requis:
- `Temperature centrale continue` (`core_temperature_continuous`): necessaire pour appliquer le seuil officiel < 36 C et la duree d'exposition [status: partial]
Inputs utiles:
- `Rechauffement actif` (`active_warming_context`): permet de distinguer echec de prevention et absence de prevention [status: missing]

### Apport potentiel des waveforms

- Cette complication est surtout contrainte par des donnees numeriques ou contextuelles.

### Ce qui manque encore meme avec waveforms

- `Rechauffement actif` (`active_warming_context`): permet de distinguer echec de prevention et absence de prevention [status: missing]

### Ce que les waveforms peuvent reellement combler

- Peu de gain attendu uniquement par morphologie waveform.

## hyperthermie_maligne

- Famille: `metabolique_thermique`
- No-wave cible dans le registry: `true`
- Waveforms utiles dans le registry: `true`

### Sans waveforms

Inputs requis:
- `Exposition aux agents declencheurs` (`triggering_agent_context`): les sources officielles reposent sur l'association clinique + agent declencheur [status: partial]
- `Rigidite musculaire` (`rigidity_context`): signe cle des recommandations [status: missing]
Inputs utiles:
- `Administration de dantrolene` (`dantrolene_admin`): utile pour reconstituer l'evolution et valider la suspicion [status: missing]

### Apport potentiel des waveforms

Inputs requis dependants des waveforms:
- `Vitesse d'ascension de l'EtCO2` (`etco2_trend_velocity`): la cinetique compte plus qu'une valeur isolee [status: partial]

### Ce qui manque encore meme avec waveforms

- `Rigidite musculaire` (`rigidity_context`): signe cle des recommandations [status: missing]
- `Administration de dantrolene` (`dantrolene_admin`): utile pour reconstituer l'evolution et valider la suspicion [status: missing]

### Ce que les waveforms peuvent reellement combler

- `Vitesse d'ascension de l'EtCO2` (`etco2_trend_velocity`): la cinetique compte plus qu'une valeur isolee [status: partial]

## arret_cardiaque_perioperatoire

- Famille: `critique`
- No-wave cible dans le registry: `true`
- Waveforms utiles dans le registry: `true`

### Sans waveforms

Inputs requis:
- `Rythme choquable ou non choquable` (`rhythm_class`): l'algorithme officiel depend du type de rythme [status: missing]
- `Contexte de massage cardiaque` (`chest_compression_context`): utile pour l'interpretation de l'EtCO2 et de l'etat per-op [status: missing]
Inputs utiles:
- `Journal des chocs` (`shock_delivery_log`): ameliore le suivi de l'algorithme per-op [status: missing]

### Apport potentiel des waveforms

- Cette complication est surtout contrainte par des donnees numeriques ou contextuelles.

### Ce qui manque encore meme avec waveforms

- `Rythme choquable ou non choquable` (`rhythm_class`): l'algorithme officiel depend du type de rythme [status: missing]
- `Contexte de massage cardiaque` (`chest_compression_context`): utile pour l'interpretation de l'EtCO2 et de l'etat per-op [status: missing]
- `Journal des chocs` (`shock_delivery_log`): ameliore le suivi de l'algorithme per-op [status: missing]

### Ce que les waveforms peuvent reellement combler

- Peu de gain attendu uniquement par morphologie waveform.

## embolie_pulmonaire_etat_de_choc

- Famille: `respiratoire_hemodynamique`
- No-wave cible dans le registry: `true`
- Waveforms utiles dans le registry: `true`

### Sans waveforms

Inputs requis:
- `Contexte thromboembolique` (`thromboembolic_context`): sans contexte thrombotique, la specificite reste faible [status: missing]
- `Contexte de surcharge ventriculaire droite` (`right_ventricular_context`): utile pour distinguer une embolie pulmonaire des autres chocs [status: missing]
Inputs utiles:
- `Contexte de thrombolyse` (`thrombolysis_context`): utile pour les formes graves [status: missing]
- `Tendance d'oxygenation` (`oxygenation_trend`): aide a caracteriser l'aggravation respiratoire associee au choc [status: partial]

### Apport potentiel des waveforms

Inputs requis dependants des waveforms:
- `Chute brutale de l'EtCO2` (`etco2_sudden_drop`): le CO2 est une donnee respiratoire-cle pour la suspicion d'embolie pulmonaire grave [status: partial]

### Ce qui manque encore meme avec waveforms

- `Contexte thromboembolique` (`thromboembolic_context`): sans contexte thrombotique, la specificite reste faible [status: missing]
- `Contexte de surcharge ventriculaire droite` (`right_ventricular_context`): utile pour distinguer une embolie pulmonaire des autres chocs [status: missing]
- `Contexte de thrombolyse` (`thrombolysis_context`): utile pour les formes graves [status: missing]

### Ce que les waveforms peuvent reellement combler

- `Chute brutale de l'EtCO2` (`etco2_sudden_drop`): le CO2 est une donnee respiratoire-cle pour la suspicion d'embolie pulmonaire grave [status: partial]

## laryngospasme_enfant

- Famille: `respiratoire`
- No-wave cible dans le registry: `true`
- Waveforms utiles dans le registry: `true`

### Sans waveforms

Inputs requis:
- `Contexte pediatrique structure` (`pediatric_context`): la complication est specifique de l'enfant dans notre referentiel [status: partial]
- `Phase per-extubation ou stimulation laryngee` (`extubation_or_stimulation_phase`): le contexte de survenue est central [status: missing]
- `Absence de ventilation ou stridor` (`ventilation_absence_or_stridor`): renforce la specificite clinique du laryngospasme [status: missing]
Inputs utiles:
- `IVAS recente` (`recent_uri`): facteur de risque important dans les sources [status: missing]
- `Cinetique de desaturation` (`spo2_drop_kinetics`): utile pour differencier un episode rapidement severe d'un evenement plus transitoire [status: partial]

### Apport potentiel des waveforms

Inputs requis dependants des waveforms:
- `Presence ou disparition de la capnographie` (`capnography_presence`): le signal CO2 aide a objectiver l'absence de ventilation efficace [status: partial]

### Ce qui manque encore meme avec waveforms

- `Phase per-extubation ou stimulation laryngee` (`extubation_or_stimulation_phase`): le contexte de survenue est central [status: missing]
- `Absence de ventilation ou stridor` (`ventilation_absence_or_stridor`): renforce la specificite clinique du laryngospasme [status: missing]
- `IVAS recente` (`recent_uri`): facteur de risque important dans les sources [status: missing]

### Ce que les waveforms peuvent reellement combler

- `Presence ou disparition de la capnographie` (`capnography_presence`): le signal CO2 aide a objectiver l'absence de ventilation efficace [status: partial]

