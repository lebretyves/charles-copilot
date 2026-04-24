# Terrain diabetique

- `id`: `diabete`
- `niveau_source`: `normatif_plus_pratique`
- `confiance_algo`: `forte`

## Sources

- SFAR Prise en charge du patient diabetique en peri-operatoire: https://sfar.org/download/prise-en-charge-du-patient-diabetique-en-peri-operatoire/
- MAPAR Fiches diabete: https://www.mapar.org/index.php/fiches-diabete

## Ce que les sources apportent

- surveillance glycemique peroperatoire reguliere
- adaptation selon type de traitement et chirurgie
- vigilance neuropathie autonome et gastroparasie

## Exploitation algo possible

- `entrees`: glycemie, trend glycemique, type de diabete, traitement, FC, PA, duree de jeune, insuline perop
- `modulateurs`: pompe a insuline, insulinotherapie, chirurgie majeure, neuropathie autonome, insuffisance renale associee
- `sorties`: alerte hypo/hyperglycemie, augmentation de sensibilite a l'instabilite hemodynamique, facteur de risque aspiration si gastroparasie

## Donnees a demander ou ajouter

- type 1/type 2
- pompe ou injections
- HbA1c recente
- heure derniere prise antidiabetique
- suspicion neuropathie autonome

## Pistes KB

- lier le terrain diabetique a des regles sur glycemie et variabilite hemodynamique
- creer un facteur `neuropathie_autonome_suspectee`
