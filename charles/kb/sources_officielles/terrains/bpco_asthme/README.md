# BPCO et asthme

- `id`: `bpco_asthme`
- `niveau_source`: `normatif_plus_pratique`
- `confiance_algo`: `forte`

## Sources

- SFAR Bronchospasme: https://sfar.org/download/bronchospasme/
- MAPAR Fiches urgence: https://www.mapar.org/index.php/fiches-urgence

## Ce que les sources apportent

- reconnaissance du profil obstructif perioperatoire
- importance de la forme de capnographie, des pressions ventilatoires et de l'hypoxemie
- lien entre terrain respiratoire et risque de bronchospasme, auto-PEEP ou sevrage difficile

## Exploitation algo possible

- `entrees`: SpO2, EtCO2, pente expiratoire, Ppeak, Vt, FR, I:E, FiO2
- `modulateurs`: BPCO, asthme actif, infection recente, chirurgie thoraco-abdominale, tabagisme
- `sorties`: score d'obstruction, detection auto-PEEP probable, seuils SpO2 personnalises, tri entre bronchospasme et cause mecanique

## Donnees a demander ou ajouter

- VEMS ou antecedent EFR
- traitement bronchodilatateur habituel
- exacerbation recente
- statut tabagique

## Pistes KB

- formaliser les terrains `bpco`, `asthme`, `insuffisance_respiratoire_chronique`
- relier capno en requin et hausse de Ppeak a un facteur `obstruction_probable`
