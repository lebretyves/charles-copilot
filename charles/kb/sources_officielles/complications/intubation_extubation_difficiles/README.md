# Intubation et extubation difficiles

- `id`: `intubation_extubation_difficiles`
- `niveau_source`: `normatif_plus_pratique_plus_pedagogique`
- `confiance_algo`: `forte`

## Sources

- SFAR Intubation difficile et extubation en anesthesie chez l'adulte: https://sfar.org/actualisation-de-recommandations-intubation-difficile-et-extubation-en-anesthesie-chez-ladulte/
- MAPAR Intubation: https://www.mapar.org/article/pdf/739/Intubation
- SOFIA Intubation difficile - support SFAR: https://sofia.medicalistes.fr/spip/IMG/pdf/l_intubation_difficile_SFAR_.pdf

## Signaux utiles pour algo

- score preop de voie aerienne
- nombre de tentatives
- duree de tentative
- EtCO2 absent ou retardee
- desaturation pendant tentative
- difficulte de ventilation au masque

## Regles candidates

- preop score morphologique
- perop score d'echec de tentative
- extubation a risque si terrain SAOS / oedeme / chirurgie ORL ou cervicale
- alerte prioritaire si `desaturation + pas d'EtCO2 valide`

## Combinaisons pertinentes

- obesite + SAOS + antecedent de VA difficile
- tentative prolongee + chute rapide de SpO2
- reintubation potentiellement difficile au reveil

## Pistes KB

- deux sous-scores distincts: `risque_intubation` et `risque_extubation`
- journalisation structured des tentatives pour alimenter les futurs algos
