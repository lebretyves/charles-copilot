# Anticoagulants et antiagregants

- `id`: `anticoagulants_antiagregants`
- `niveau_source`: `normatif_plus_pratique`
- `confiance_algo`: `mixte`

## Sources

- SFAR Recommandations: https://sfar.org/recommandations/
- MAPAR Protocoles MAPAR 2025: https://www.mapar.org/livre/Livre%20de%20protocoles/1/Protocoles%20MAPAR

## Ce que les sources apportent

- gestion perioperatoire structuree des traitements antithrombotiques
- articulation entre risque hemorragique, risque thrombotique et timing operatoire
- besoin de protocoles simples, lisibles et dependants du geste

## Exploitation algo possible

- `entrees`: type d'agent, heure derniere prise, chirurgie a risque hemorragique, Hb, plaquettes, TP/INR, TCA, saignement estime
- `modulateurs`: coronarien stente, haut risque thrombotique, chirurgie urgente, geste neuraxial
- `sorties`: sur-risque hemorragique, sur-risque transfusionnel, seuil de suspicion hemorragique abaisse, message d'attention neuraxiale

## Donnees a demander ou ajouter

- molecule exacte
- dose / derniere prise
- indication du traitement
- haut risque thrombotique oui/non

## Pistes KB

- creer un terrain trans-systeme `antithrombotique`
- l'utiliser comme multiplicateur du score de saignement et du seuil de recours biologique
