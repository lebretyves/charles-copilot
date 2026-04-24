# Hypotension perioperatoire

- `id`: `hypotension_perioperatoire`
- `niveau_source`: `normatif_plus_pedagogique`
- `confiance_algo`: `forte`

## Sources

- SFAR Optimisation hemodynamique perioperatoire - Adulte dont obstetrique: https://sfar.org/optimisation-hemodynamique-perioperatoire-adulte-dont-obstetrique/
- SOFIA Controle perioperatoire de la pression arterielle: https://sofia.medicalistes.fr/spip/IMG/pdf/controle_perioperatoire_de_la_pression_arterielle_pierre-gregoire_guinot_dijon_.pdf

## Signaux utiles pour algo

- PAS
- PAM
- duree sous seuil
- chute relative vs PA de reference
- FC associee
- besoin vasopresseur

## Regles candidates

- facteur absolu: `PAM < 65`
- facteur relatif: `chute >= 20 %` vs baseline
- facteur charge: aire ou duree sous seuil
- facteur contexte: terrain HTA/coronarien/IC/obstetrique

## Combinaisons pertinentes

- hypotension + bradycardie
- hypotension + tachycardie
- hypotension + EtCO2 qui baisse
- hypotension prolongee + terrain renal ou coronarien

## Pistes KB

- score `dette_hemodynamique`
- seuils personnalises par terrain
- ponderation plus forte de la duree que du point bas isole
