# Insuffisance renale

- `id`: `insuffisance_renale`
- `niveau_source`: `normatif`
- `confiance_algo`: `forte`

## Sources

- SFAR Insuffisance renale aigue en perioperatoire et en reanimation: https://sfar.org/insuffisance-renale-aigue/
- SFAR Curarisation et decurarisation en anesthesie: https://sfar.org/curarisation-et-decurarisation-en-anesthesie/

## Ce que les sources apportent

- importance de l'IRA perioperatoire et de ses facteurs favorisants
- interet des strategies d'evitement d'hypoperfusion et des agressions medicamenteuses
- vigilance sur la pharmacocinetique et la decurarisation

## Exploitation algo possible

- `entrees`: creatinine, diurese, PAM, duree hypotension, K+, acidose, dose cumulee curares, TOF si disponible
- `modulateurs`: IRC connue, chirurgie a risque, sepsis, saignement, nephrotoxiques, terrain diabetique
- `sorties`: score de risque IRA, surpoids de l'hypotension prolongee, alerte hyperkaliemie, alerte decurarisation retardee

## Donnees a demander ou ajouter

- eGFR preop
- diurese horaire
- dialyse oui/non
- potassium preop et perop
- monitoring neuromusculaire plus detaille

## Pistes KB

- introduire un facteur `charge_hypotension_renale`
- coupler terrain renal avec seuils plus stricts sur K+, acidose et duree d'hypotension
