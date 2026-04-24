# Embolie pulmonaire et etat de choc

- `id`: `embolie_pulmonaire_etat_de_choc`
- `niveau_source`: `pratique`
- `confiance_algo`: `mixte`

## Sources

- MAPAR Fiches urgence: https://www.mapar.org/index.php/fiches-urgence

## Signaux utiles pour algo

- chute brutale d'EtCO2
- hypotension
- tachycardie
- desaturation
- hausse des pressions ventilatoires ou signes de contrainte droite selon contexte

## Regles candidates

- facteur `EtCO2_drop_sudden`
- facteur `hemodynamique_choque`
- facteur `terrain_thromboembolique`

## Combinaisons pertinentes

- EtCO2 qui chute plus vite que la SpO2
- hypotension + tachycardie sans saignement evident
- contexte chirurgie a haut risque thrombotique

## Pistes KB

- score de suspicion `embolie_probable`
- a revalider plus tard avec sources supplementaires plus fortes si besoin
