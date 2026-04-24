# Terrain pediatrique

- `id`: `pediatrique`
- `niveau_source`: `normatif`
- `confiance_algo`: `forte`

## Sources

- SFAR Optimisation hemodynamique perioperatoire - Pediatrie: https://sfar.org/optimisation-hemodynamique-perioperatoire-pediatrie/
- SFAR Organisation de l'anesthesie pediatrique: https://sfar.org/organisation-de-lanesthesie-pediatrique/

## Ce que les sources apportent

- necessite de seuils age-dependants
- poids du contexte structurel et de l'expertise pediatrique
- importance du monitorage adapte a l'age, au poids et au type de chirurgie

## Exploitation algo possible

- `entrees`: age en mois/annees, poids, PAM, FC, SpO2, EtCO2, temperature, duree d'apnee, type de voie aerienne
- `modulateurs`: nourrisson, enfant enrhumé, chirurgie ORL, risque de desaturation rapide, faible reserve thermique
- `sorties`: tables de seuils par classes d'age, score de desaturation rapide, vigilance laryngospasme, escalade plus precoce sur bradycardie

## Donnees a demander ou ajouter

- age exact en mois pour les plus jeunes
- antecedent d'IVAS recente
- poids ideal et poids reel
- prematurite / cardiopathie congenitale

## Pistes KB

- etendre `populations.yaml` avec bandes d'age operatoires
- rendre les seuils `HR`, `PAM`, `FR`, `SpO2`, `Temp` dependants de l'age
