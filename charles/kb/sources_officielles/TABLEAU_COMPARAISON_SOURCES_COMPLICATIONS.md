# Tableau De Comparaison Des Sources Officielles Par Complication

Ce tableau compare, pour chaque complication actuellement structuree dans la KB, ce que disent les sources **SFAR**, **MAPAR** et **SOFIA**.

Objectif :
- voir si les sources disent globalement la meme chose
- identifier ce qui est surtout **complementaire**
- reperer les zones ou la comparaison est encore **impossible** faute de pluralite de sources

Regle de lecture :
- `Convergence forte` : les sources vont dans le meme sens, sans divergence utile a ce stade
- `Complementaire` : le noyau clinique est commun, mais chaque source apporte une couche differente
- `Comparaison limitee` : une seule famille de source ou pas assez de recouvrement pour conclure

## Tableau

| Complication | SFAR | MAPAR | SOFIA | Verdict | Noyau commun | Apport distinct / limite |
| --- | --- | --- | --- | --- | --- | --- |
| `hypotension_perioperatoire` | Oui | Non | Oui | Complementaire avec bon recouvrement | Importance de l'hypotension perop, surveillance de la PAM, interpretation non reduite a un seul chiffre | SFAR apporte le seuil absolu et la notion de duree/burden ; SOFIA apporte surtout la baisse relative d'environ `20 %` et une lecture pedagogique |
| `choc_hemorragique_transfusion_massive` | Oui | Oui | Non | Convergence forte | Reconnaissance precoce, approche protocolisee, association clinique + hemodynamique + biologie | SFAR apporte les cibles biologiques et la logique transfusion/coagulopathie ; MAPAR operationalise la prise en charge d'urgence |
| `anaphylaxie_perioperatoire` | Oui | Oui | Oui | Convergence forte et complementaire | Meme logique de reconnaissance d'une reaction severe perop et d'un traitement urgent par adrenaline | SFAR cadre le diagnostic et la prise en charge globale ; MAPAR donne les doses/bolus/IVSE ; SOFIA sert de support pedagogique de consolidation |
| `bronchospasme_perioperatoire` | Oui | Oui | Non | Convergence forte | Bronchospasme reconnu sur signes ventilatoires et capnographiques, traitement rapide necessaire | SFAR fournit le cadre clinique ; MAPAR apporte les seuils operationnels (`> 40-45 cmH2O`, `SpO2 < 90 %`) et les doses |
| `intubation_extubation_difficiles` | Oui | Oui | Oui | Convergence forte | Priorite a l'oxygenation, algorithmes d'abord securitaires, definition pratique proche de la difficulte | MAPAR et SOFIA convergent sur `> 2 laryngoscopies` et/ou `> 10 min` ; SFAR porte surtout l'algorithme normatif et la strategie globale |
| `hypothermie_perioperatoire` | Oui | Non | Non | Comparaison limitee | Hypothermie perop accidentelle a prevenir, temperature centrale pertinente, seuil `< 36 C` | Une seule famille de source structuree actuellement, donc pas de comparaison inter-organismes solide |
| `hyperthermie_maligne` | Oui | Oui | Oui | Convergence forte | Declencheurs communs, dantrolene precoce, prise en charge urgente standardisee | SFAR fixe les doses et la surveillance ; MAPAR detaille la conduite operationnelle ; SOFIA est tres proche du contenu SFAR |
| `arret_cardiaque_perioperatoire` | Non | Oui | Non | Comparaison limitee | Algorithme d'urgence adulte perioperatoire disponible | Pour l'instant, seule la fiche MAPAR est structuree dans cette base |
| `embolie_pulmonaire_etat_de_choc` | Non | Oui | Non | Comparaison limitee | Suspicion d'EP grave avec hypotension/choc, logique de reperfusion urgente | Pour l'instant, seule la fiche MAPAR est structuree dans cette base |
| `laryngospasme_enfant` | Non | Oui | Non | Comparaison limitee | Logique respiratoire pediatrique d'urgence, CPAP/O2/therapeutiques de sauvetage | Deux sources MAPAR se completent, mais pas encore de triangulation SFAR/SOFIA dans la base structuree |

## Lecture Rapide

### Complications avec forte convergence multi-sources
- `choc_hemorragique_transfusion_massive`
- `anaphylaxie_perioperatoire`
- `bronchospasme_perioperatoire`
- `intubation_extubation_difficiles`
- `hyperthermie_maligne`

### Complications ou les sources sont surtout complementaires
- `hypotension_perioperatoire`

### Complications encore peu triangulees
- `hypothermie_perioperatoire`
- `arret_cardiaque_perioperatoire`
- `embolie_pulmonaire_etat_de_choc`
- `laryngospasme_enfant`

## Consequence Pour Les Algos

- Les complications a **forte convergence** sont les meilleures candidates pour construire en premier des algos de detection officiels robustes.
- Les complications **complementaires** demandent une fusion intelligente des apports, sans forcer un faux consensus.
- Les complications a **comparaison limitee** peuvent etre integrees, mais avec un niveau de confiance documentaire inferieur tant qu'on n'a pas enrichi la base source.
