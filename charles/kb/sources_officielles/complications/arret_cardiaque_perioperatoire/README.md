# Arret cardiaque perioperatoire

- `id`: `arret_cardiaque_perioperatoire`
- `niveau_source`: `pratique`
- `confiance_algo`: `mixte`

## Sources

- MAPAR Fiches urgence: https://www.mapar.org/index.php/fiches-urgence

## Signaux utiles pour algo

- disparition brutale du signal arteriel
- FC a zero ou rythme choquable documente
- EtCO2 qui s'effondre
- hypotension profonde et bradycardie pre-arret

## Regles candidates

- seuil de detection ultra sensible
- confirmation sur deux canaux minimum si possible
- classer le mode d'entree: asystolie, brady-extreme, FV/TV, dissociation

## Combinaisons pertinentes

- bradycardie severe + PAM effondree
- desaturation + EtCO2 effondre + arret
- arret en contexte anaphylaxie ou hemorragie

## Pistes KB

- regle de broadcast prioritaire maximale
- lier l'ACR a une recherche automatique de cause reversible probable
