# Bronchospasme perioperatoire

- `id`: `bronchospasme_perioperatoire`
- `niveau_source`: `normatif_plus_pratique`
- `confiance_algo`: `forte`

## Sources

- SFAR Bronchospasme: https://sfar.org/download/bronchospasme/
- MAPAR Fiches urgence: https://www.mapar.org/index.php/fiches-urgence

## Signaux utiles pour algo

- Ppeak qui augmente
- capnographie avec pente expiratoire evocatrice d'obstruction
- SpO2 qui baisse
- Vt qui baisse pour une meme pression
- prolongation expiratoire / auto-PEEP

## Regles candidates

- score d'obstruction sur `Ppeak + EtCO2 shape + SpO2`
- facteur terrain `asthme/BPCO`
- facteur temporalite `intubation, incision, antibiotique, aspiration`

## Combinaisons pertinentes

- bronchospasme vs intubation selective
- bronchospasme vs coudure / bouchon
- bronchospasme + hypotension = penser anaphylaxie

## Pistes KB

- creer un facteur derive `obstruction_respiratoire_probable`
- enregistrer la forme de capnographie comme feature explicite
