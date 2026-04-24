# Hypothermie perioperatoire

- `id`: `hypothermie_perioperatoire`
- `niveau_source`: `normatif`
- `confiance_algo`: `forte`

## Sources

- SFAR Prevention de l'hypothermie peroperatoire accidentelle: https://sfar.org/prevention-de-lhypothermie-peroperatoire-accidentelle-au-bloc-operatoire-chez-ladulte/

## Signaux utiles pour algo

- temperature centrale
- duree de chirurgie
- exposition / ouverture cavitaire
- volume de remplissage ou transfusion
- rechauffement actif oui/non

## Regles candidates

- seuil absolu temperature
- pente de baisse precoce
- facteur terrain age, maigreur, pediatrie
- facteur perte sanguine / chirurgie longue

## Combinaisons pertinentes

- hypothermie + hemorragie
- hypothermie + coagulopathie
- hypothermie + reveil retarde

## Pistes KB

- score de risque hypothermie preop
- score de cinetique de refroidissement perop
