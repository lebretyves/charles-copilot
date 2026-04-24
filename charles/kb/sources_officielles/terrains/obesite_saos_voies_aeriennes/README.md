# Obesite, SAOS et voies aeriennes

- `id`: `obesite_saos_voies_aeriennes`
- `niveau_source`: `normatif_plus_pedagogique`
- `confiance_algo`: `forte`

## Sources

- SFAR Intubation difficile et extubation en anesthesie chez l'adulte: https://sfar.org/actualisation-de-recommandations-intubation-difficile-et-extubation-en-anesthesie-chez-ladulte/
- SOFIA Intubation difficile - support SFAR: https://sofia.medicalistes.fr/spip/IMG/pdf/l_intubation_difficile_SFAR_.pdf

## Ce que les sources apportent

- evaluation preop des voies aeriennes et du risque d'extubation
- SAOS comme amplificateur de desaturation et de sensibilite aux opioides
- lien fort entre morphotype et difficulte d'oxygenation

## Exploitation algo possible

- `entrees`: BMI, Mallampati, ouverture buccale, antecedent de VA difficile, SpO2, temps de desaturation, PEEP, Ppeak
- `modulateurs`: SAOS connu, obesite morbide, chirurgie ORL ou cervicale, decubitus, opioides
- `sorties`: score de risque intubation, score de risque extubation, seuils plus stricts de desaturation, priorisation de l'analyse LLM sur echec de ventilation

## Donnees a demander ou ajouter

- STOP-BANG
- circonference cervicale
- antecedent CPAP
- dentition / mobilite cervicale

## Pistes KB

- lier population `obese` et terrain `saos`
- preparer un score combine `morphotype + histoire VA + dynamique SpO2`
