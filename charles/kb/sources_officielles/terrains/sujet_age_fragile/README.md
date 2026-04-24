# Sujet age fragile

- `id`: `sujet_age_fragile`
- `niveau_source`: `normatif`
- `confiance_algo`: `forte`

## Sources

- SFAR AGEARISK: https://sfar.org/agearisk/
- SFAR Programme d'optimisation perioperatoire du patient adulte: https://sfar.org/programme-doptimisation-perioperatoire-du-patient-adulte/

## Ce que les sources apportent

- focus sur les patients `> 75 ans`
- importance de la chirurgie majeure et du parcours perioperatoire complet
- logique d'evaluation des facteurs pre, per et postoperatoires
- interet d'un suivi specifique des complications graves et de la mortalite

## Exploitation algo possible

- `entrees`: age, type de chirurgie, chirurgie majeure oui/non, PA de reference, temperature, SpO2, delais de recuperation
- `modulateurs`: reserve physiologique basse, fragilite, risque cognitif, risque d'hypothermie, tolerance reduite a l'hypotension
- `sorties`: sensibilite accrue sur hypotension relative, hypothermie, desaturation, delai d'analyse LLM plus court si profil fragile

## Donnees a demander ou ajouter

- score de fragilite
- autonomie de base
- trouble cognitif connu
- lieu de vie / institution
- delai de reprise d'autonomie postop

## Pistes KB

- mapper vers `geriatrique` dans `populations.yaml`
- ajouter un facteur `hypotension_relative_personnalisee`
- ajouter un modulateur `fragilite_elevee` independant de l'age seul
