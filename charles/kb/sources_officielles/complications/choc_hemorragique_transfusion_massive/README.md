# Choc hemorragique et transfusion massive

- `id`: `choc_hemorragique_transfusion_massive`
- `niveau_source`: `normatif_plus_pratique`
- `confiance_algo`: `forte`

## Sources

- SFAR Reanimation du choc hemorragique: https://sfar.org/recommandations-sur-la-reanimation-du-choc-hemorragique/
- SFAR PLYO en choc hemorragique / risque de transfusion massive: https://sfar.org/indications-de-transfusion-de-plasmas-lyophilises-plyo-chez-un-patient-en-choc-hemorragique-ou-a-risque-de-transfusion-massive-en-milieu-civil/
- MAPAR Fiche urgence choc hemorragique: https://www.mapar.org/contenu/fichetechnique/protocoles_mapar_2016_fiche_urgence_05_choc_hemorragique.pdf

## Signaux utiles pour algo

- PAS/PAM
- FC
- `shock_index = FC / PAS`
- pertes sanguines estimees
- Hb, lactate, fibrinogene, coagulation
- temperature et calcium si disponibles

## Regles candidates

- detection precoce sur tendance `FC monte + PAS baisse`
- renforcement si `shock_index > 0.9`
- score de gravite augmente si hypotension + lactate + baisse Hb
- mode transfusion massive si terrain antithrombotique ou chirurgie a haut risque

## Combinaisons pertinentes

- hemorragie + hypothermie
- hemorragie + acidose
- hemorragie + hypocalcemie
- hemorragie + vasopresseurs croissants

## Pistes KB

- score pondere `hemo_score`
- facteur `charge_hemorragique` lie a la cinetique et non au seul seuil
