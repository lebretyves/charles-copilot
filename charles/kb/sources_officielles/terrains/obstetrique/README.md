# Terrain obstetrique

- `id`: `obstetrique`
- `niveau_source`: `normatif`
- `confiance_algo`: `forte`

## Sources

- SFAR Optimisation hemodynamique perioperatoire - Adulte dont obstetrique: https://sfar.org/optimisation-hemodynamique-perioperatoire-adulte-dont-obstetrique/

## Ce que les sources apportent

- besoin d'un pilotage hemodynamique specifique en obstetrique
- mauvaise tolerance de l'hypotension maternelle
- contexte particulier de compression aorto-cave et de risque hemorragique

## Exploitation algo possible

- `entrees`: PAS, PAM, FC, SpO2, EtCO2, saignement estime, vasopresseurs, type d'anesthesie
- `modulateurs`: grossesse avancee, anesthesie neuraxiale, extraction en urgence, terrain preeclamptique
- `sorties`: seuils plus agressifs sur hypotension, priorisation de l'hemorragie obstetricale, score de risque combine hemodynamique + voie aerienne

## Donnees a demander ou ajouter

- terme / contexte obstetrical
- preeclampsie ou HTA gravidique
- type de cesarienne ou geste obstetrical
- hauteur uterine ou elements d'aorto-cave si disponibles

## Pistes KB

- ajouter un terrain `obstetrique_haute_priorite_hypotension`
- differencier hypotension sous rachianesthesie vs hemorragie
