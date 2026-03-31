# GitHub Backlog

Backlog propose pour structurer CHARLES apres les refontes runtime, front, learning et Docker.

Chaque ticket ci-dessous est pret a etre cree comme issue GitHub.

## 1. Unifier les workflows CI

- Type: `chore`
- Priorite: `P1`
- Labels: `ci`, `github-actions`, `quality`
- Titre:
  `Unifier les workflows GitHub Actions en une pipeline canonique`
- Objectif:
  Remplacer le doublon entre `.github/workflows/ci.yml` et `.github/workflows/charles-ci.yml` par une seule pipeline de reference.
- A faire:
  - garder un workflow unique
  - couvrir backend tests, frontend build, Docker smoke, e2e smoke
  - archiver logs et artefacts utiles en cas d'echec
- Critères d'acceptation:
  - un seul workflow principal reste actif
  - tous les checks obligatoires passent sur PR
  - la doc indique clairement quel workflow fait foi

## 2. Proteger `main` avec un ruleset

- Type: `chore`
- Priorite: `P1`
- Labels: `github`, `governance`, `quality`
- Titre:
  `Ajouter un ruleset GitHub pour proteger la branche main`
- Objectif:
  Empêcher les merges non verifiés et les pushes directs.
- A faire:
  - PR obligatoire sur `main`
  - checks CI obligatoires
  - historique lineaire
  - blocage si checks rouges
- Critères d'acceptation:
  - aucun push direct possible sur `main`
  - merge bloque si CI en echec
  - settings GitHub documentes dans le repo

## 3. Ajouter `CODEOWNERS`

- Type: `chore`
- Priorite: `P1`
- Labels: `github`, `governance`
- Titre:
  `Ajouter un fichier CODEOWNERS par zone du projet`
- Objectif:
  Clarifier qui revoit quoi entre backend, frontend, learning, ops.
- A faire:
  - definir owners pour `services/backend`
  - definir owners pour `services/frontend`
  - definir owners pour `learning`
  - definir owners pour `ops`
- Critères d'acceptation:
  - fichier `.github/CODEOWNERS` ajoute
  - les paths critiques ont un owner explicite

## 4. Standardiser les issues et PR

- Type: `chore`
- Priorite: `P1`
- Labels: `github`, `documentation`, `process`
- Titre:
  `Creer des templates d'issues et de pull requests`
- Objectif:
  Uniformiser les bugs, refactors, runs ML et changements infra.
- A faire:
  - template bug
  - template refactor
  - template model/dataset
  - PR template avec checklist tests, docs, impact runtime, impact prod-like
- Critères d'acceptation:
  - `.github/ISSUE_TEMPLATE/` existe
  - `pull_request_template.md` existe
  - chaque template demande contexte, impact, validation

## 5. Formaliser la matrice de capacites

- Type: `docs`
- Priorite: `P1`
- Labels: `documentation`, `architecture`, `diagnostic`
- Titre:
  `Documenter une capability matrix du projet`
- Objectif:
  Pouvoir refaire facilement le diagnostic complet du projet a chaque phase.
- A faire:
  - fichier `docs/CAPABILITY_MATRIX.md`
  - colonnes: fonctionnalite, statut, utile en dev, utile en prod-like, utile en R&D, owner, source de verite
  - inclure backend, frontend, simulator, LLM, learning, Docker, ops
- Critères d'acceptation:
  - la matrice couvre les zones majeures du projet
  - elle distingue clairement `dev`, `prod-like` et `research`
  - elle est referencee dans le README

## 6. Generer un diagnostic periodique

- Type: `feature`
- Priorite: `P1`
- Labels: `diagnostic`, `ci`, `quality`
- Titre:
  `Ajouter un rapport de diagnostic periodique du projet`
- Objectif:
  Produire regulierement un etat de sante du projet, pas seulement des tests unitaires.
- A faire:
  - job CI planifie
  - rapport Markdown en artefact
  - verifier gros fichiers, tests, build, Docker, drift docs/config, learning runs disponibles
- Critères d'acceptation:
  - un rapport est genere automatiquement
  - il est exploitable par un humain sans lire les logs bruts

## 7. Brancher MLflow local pour les runs

- Type: `feature`
- Priorite: `P1`
- Labels: `mlops`, `learning`, `training`
- Titre:
  `Tracer les runs de fine-tuning et d'evaluation avec MLflow local`
- Objectif:
  Savoir quel run, dataset, parametres et adapter ont produit quels resultats.
- A faire:
  - logger params LoRA
  - logger dataset version
  - logger metrics train/eval
  - logger artefacts adapter et rapports
- Critères d'acceptation:
  - chaque run a un `run_id`
  - les runs sont comparables entre eux
  - le path du modele/adapter est trace

## 8. Ajouter un registre modele minimal

- Type: `feature`
- Priorite: `P1`
- Labels: `mlops`, `models`, `governance`
- Titre:
  `Maintenir un registre simple des adapters et modeles utilises`
- Objectif:
  Savoir quel adapter est `draft`, `reviewed`, `validated` ou `runtime-ready`.
- A faire:
  - fichier ou table de registre
  - lien vers dataset, eval, date, statut
  - versionnement clair du base model et de l'adapter
- Critères d'acceptation:
  - un seul modele est marque `runtime-ready`
  - l'etat de chaque adapter est documente

## 9. Corriger et enrichir les model cards

- Type: `docs`
- Priorite: `P1`
- Labels: `models`, `documentation`, `learning`
- Titre:
  `Rendre les model cards des adapters completes et fiables`
- Objectif:
  Avoir une documentation modele exploitable et non generique.
- A faire:
  - corriger `base_model = None`
  - ajouter dataset, objectifs, limites, scores, contexte d'usage
  - distinguer waveform-aware, no-wave et partial-wave
- Critères d'acceptation:
  - chaque adapter a une model card complete
  - les limites et conditions d'usage sont explicites

## 10. Mettre les gros datasets sous DVC

- Type: `feature`
- Priorite: `P2`
- Labels: `dvc`, `datasets`, `mlops`
- Titre:
  `Versionner les datasets learning et exports lourds avec DVC`
- Objectif:
  Sortir les gros jeux de donnees de Git tout en gardant un historique propre.
- A faire:
  - versionner `learning/datasets/exports`
  - definir le remote de stockage
  - documenter le workflow `pull / repro / exp`
- Critères d'acceptation:
  - Git reste leger
  - les datasets utilises par les runs sont recuperables exactement

## 11. Ajouter OpenTelemetry sur backend, worker et simulateur

- Type: `feature`
- Priorite: `P2`
- Labels: `observability`, `telemetry`, `backend`
- Titre:
  `Instrumenter la stack avec OpenTelemetry`
- Objectif:
  Standardiser traces, metriques et logs entre backend, worker LLM et simulateur.
- A faire:
  - instrumentation FastAPI
  - instrumentation worker LLM
  - metriques et traces des jobs LLM
  - export vers un collecteur local
- Critères d'acceptation:
  - une requete API et un job LLM sont traçables de bout en bout
  - un dashboard permet de voir latence, erreurs et queue depth

## 12. Nettoyer la racine du repo

- Type: `refactor`
- Priorite: `P2`
- Labels: `repo`, `cleanup`, `quality`
- Titre:
  `Nettoyer la racine du depot et archiver les artefacts de travail`
- Objectif:
  Rendre le depot lisible et separer code, docs, mockups et artefacts temporaires.
- A faire:
  - deplacer HTML/PDF/images de travail
  - mieux ignorer caches et sorties temporaires
  - clarifier la place des assets de reference
- Critères d'acceptation:
  - la racine contient surtout des fichiers de projet, pas des artefacts jetables
  - `.gitignore` couvre les sorties temporaires frequentes

## 13. Ajouter `CONTRIBUTING.md` et `SECURITY.md`

- Type: `docs`
- Priorite: `P2`
- Labels: `documentation`, `security`, `process`
- Titre:
  `Documenter la contribution et la politique de securite du depot`
- Objectif:
  Clarifier comment contribuer et comment signaler un probleme de securite.
- A faire:
  - `CONTRIBUTING.md`
  - `SECURITY.md`
  - conventions de branches, PR, tests, signalement securite
- Critères d'acceptation:
  - les contributeurs ont une marche a suivre claire
  - la voie de signalement securite est explicite

## 14. Ajouter des ADR d'architecture

- Type: `docs`
- Priorite: `P2`
- Labels: `architecture`, `documentation`
- Titre:
  `Documenter les decisions d'architecture majeures en ADR`
- Objectif:
  Garder la trace de pourquoi on a choisi MQTT, worker LLM, Docker prod-like, pipeline learning, etc.
- A faire:
  - creer `docs/adr/`
  - ecrire au moins les ADR initiales
- Critères d'acceptation:
  - les choix structurants sont historises
  - on comprend le pourquoi sans fouiller tout Git

## 15. Continuer la refonte des fichiers lourds restants

- Type: `refactor`
- Priorite: `P2`
- Labels: `backend`, `frontend`, `maintainability`
- Titre:
  `Poursuivre le decoupage des gros fichiers restants`
- Objectif:
  Continuer a reduire la dette structurelle apres `simulator/main.py` et les routes simulateur backend.
- Cibles proposees:
  - `services/backend/app/scenario_catalog.py`
  - `services/frontend/src/components/ScenarioPanel.tsx`
  - `services/frontend/src/scope.css`
- Critères d'acceptation:
  - les fichiers critiques tombent sous un seuil de taille raisonnable
  - aucun comportement runtime ne regressse

## Ordre recommande

1. Unifier les workflows CI
2. Proteger `main` avec un ruleset
3. Ajouter `CODEOWNERS`
4. Standardiser les issues et PR
5. Formaliser la matrice de capacites
6. Generer un diagnostic periodique
7. Brancher MLflow local
8. Ajouter un registre modele
9. Corriger les model cards
10. Mettre les datasets lourds sous DVC
11. Ajouter OpenTelemetry
12. Nettoyer la racine du repo
13. Ajouter `CONTRIBUTING.md` et `SECURITY.md`
14. Ajouter des ADR
15. Continuer la refonte des fichiers lourds
