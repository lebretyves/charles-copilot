# Hyperthermie maligne

- `id`: `hyperthermie_maligne`
- `niveau_source`: `normatif_plus_pedagogique`
- `confiance_algo`: `forte`

## Sources

- SFAR Prise en charge de l'Hyperthermie Maligne: https://sfar.org/prise-en-charge-de-lhyperthermie-maligne/
- SFAR Boite a outils Hyperthermie Maligne: https://sfar.org/espace-professionel-anesthesiste-reanimateur/outils-professionnels/boite-a-outils/hyperthermie-maligne/
- SOFIA Fiche de synthese prise en charge de l'hyperthermie maligne: https://sofia.medicalistes.fr/spip/IMG/pdf/fiche_de_synthese_prise_en_charge_de_l_hyperthermie_maligne_2019_sfar.pdf

## Signaux utiles pour algo

- EtCO2 en hausse rapide inexpliquée
- tachycardie
- rigidite ou difficulte ventilatoire si renseignee
- temperature qui monte secondairement
- acidose / hyperkaliemie si biologie disponible
- exposition halogenes / succinylcholine

## Regles candidates

- facteur `declencheur_present`
- facteur `EtCO2_hausse_rapide`
- facteur `tachycardie_incoherente`
- facteur `temperature_tardive`

## Combinaisons pertinentes

- EtCO2 + FC avant temperature
- hyperthermie maligne vs sepsis vs hypoventilation simple
- hyperthermie maligne + rigidite + hyperK

## Pistes KB

- score `hm_probable`
- escalade immediate si scenario compatible meme avant hyperthermie franche
