# Terrain cardiovasculaire a haut risque

- `id`: `cardiovasculaire_haut_risque`
- `niveau_source`: `normatif_plus_pedagogique`
- `confiance_algo`: `forte`

## Sources

- SFAR Optimisation hemodynamique perioperatoire - Adulte dont obstetrique: https://sfar.org/optimisation-hemodynamique-perioperatoire-adulte-dont-obstetrique/
- SOFIA Controle perioperatoire de la pression arterielle: https://sofia.medicalistes.fr/spip/IMG/pdf/controle_perioperatoire_de_la_pression_arterielle_pierre-gregoire_guinot_dijon_.pdf

## Ce que les sources apportent

- primat de l'hypotension relative et de sa duree
- individualisation des objectifs tensionnels selon le terrain
- importance de la perfusion d'organe et de l'equilibre FC/PA

## Exploitation algo possible

- `entrees`: PAS/PAM de base, PAM instantanee, duree sous seuil, FC, ECG/ST si disponible, vasopresseurs, lactate
- `modulateurs`: HTA chronique, coronaropathie, insuffisance cardiaque, valvulopathie, arythmie
- `sorties`: score de dette hemodynamique, seuils relatifs personnalises, escalade plus precoce si coronarien ou insuffisant cardiaque

## Donnees a demander ou ajouter

- PA habituelle
- statut coronarien / stents
- NYHA / FEVG
- valvulopathie severe
- betabloquants ou IEC/ARA2

## Pistes KB

- creer un facteur `hypotension_relative_chargee`
- ponderer FC et PAM differemment selon coronarien vs insuffisant cardiaque
