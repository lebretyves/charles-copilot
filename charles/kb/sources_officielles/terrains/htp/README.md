# Hypertension arterielle pulmonaire

- `id`: `htp`
- `niveau_source`: `pratique`
- `confiance_algo`: `mixte`

## Sources

- MAPAR Gestion peri-operatoire de l'HTP: https://www.mapar.org/presentation/1/Staff%20junior/13/Gestion%20p%C3%A9ri-op%C3%A9ratoire%20de%20l%E2%80%99HTP

## Ce que les sources apportent

- risque de decompensation ventriculaire droite
- importance de l'oxygenation, de la ventilation et de l'evitement de l'hypotension
- intolerance a l'hypercapnie et a l'hypoxemie

## Exploitation algo possible

- `entrees`: SpO2, EtCO2, FC, PAS/PAM, Ppeak, signes de bas debit, besoin vasopresseur
- `modulateurs`: HTP connue, chirurgie thoracique, ventilation positive, antecedent d'insuffisance VD
- `sorties`: score de stress VD, escalade rapide si hypoxemie + hypercapnie + hypotension, priorisation des complications respiratoires

## Donnees a demander ou ajouter

- PAP connue
- classe fonctionnelle
- traitements specifiques HTP
- echographie cardiaque recente

## Pistes KB

- ajouter un modulateur `risque_vd`
- relier ce terrain a un facteur combine `SpO2 + EtCO2 + PAM + Ppeak`
