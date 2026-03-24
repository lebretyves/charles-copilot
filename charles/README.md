<p align="center">
  <img src="https://img.shields.io/badge/CHARLES-IA%20Vigilance%20Anesthésique-00d084?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAyMWMtNC45NyAwLTktNC4wMy05LTlzNC4wMy05IDktOSA5IDQuMDMgOSA5LTQuMDMgOS05IDl6bTAtMTZjLTMuODcgMC03IDMuMTMtNyA3czMuMTMgNyA3IDcgNy0zLjEzIDctNy0zLjEzLTctNy03eiIvPjxwYXRoIGZpbGw9IndoaXRlIiBkPSJNMTIuNSA3SDExdjZsNS4yNSAzLjE1Ljc1LTEuMjMtNC41LTIuNjdWN3oiLz48L3N2Zz4="/>
  <br/>
  <strong>Copilote IA d'aide à la vigilance anesthésique peropératoire</strong>
</p>

---

# CHARLES

**CHARLES** — **C**opilote **H**ospitalier d'**A**ide en **R**éanimation et **L**ogiciel d'**E**xpertise en **S**urveillance — est un système temps réel d'aide à la vigilance pour les IADE (Infirmiers Anesthésistes Diplômés d'État) en peropératoire.

> **Projet MBA1 — Epitech Technology & Management** | Yves Le Bret — IADE

---

## Table des matières

- [Contexte clinique](#contexte-clinique)
- [Architecture](#architecture)
- [Stack technique](#stack-technique)
- [Fonctionnalités](#fonctionnalités)
- [Démarrage rapide](#démarrage-rapide)
- [Base de connaissances (KB)](#base-de-connaissances)
- [Données VitalDB](#données-vitaldb)
- [Intégration LLM](#intégration-llm)
- [API REST](#api-rest)
- [Tests](#tests)
- [Structure du projet](#structure-du-projet)
- [Roadmap](#roadmap)
- [Licence](#licence)

---

## Contexte clinique

L'anesthésie peropératoire repose sur la **vigilance continue** de l'IADE. Les moniteurs multiparamétriques (scope) délivrent un flux constant de données vitales que le soignant doit interpréter en temps réel, tout en gérant les administrations médicamenteuses, le bilan entrées/sorties et les événements chirurgicaux.

**CHARLES** ne remplace pas l'IADE — il l'assiste :

- 🔍 **Détection précoce** — Alertes intelligentes basées sur des seuils adaptatifs, des règles multi-paramètres et la détection de tendances
- 🧠 **Analyse contextuelle** — LLM enrichi par une base de connaissances clinique de 3 000+ lignes YAML
- 📊 **Dashboard scope** — Interface temps réel façon moniteur d'anesthésie (dark theme, courbes de tendance)
- 📁 **Traçabilité** — Persistence PostgreSQL complète (cas, alertes, analyses, médicaments, événements, bilan liquidien)

---

## Architecture

```
┌──────────────┐     MQTT      ┌──────────────────────────────────────────────┐
│  Simulateur  │──────────────▶│                 Backend FastAPI              │
│  (5 scénarios│  bloc/+/vitals│                                              │
│  + replay    │               │  ┌────────────┐  ┌──────┐  ┌────────────┐   │
│  VitalDB)    │               │  │Alert Engine │  │  KB  │  │ LLM Engine │   │
└──────────────┘               │  │ (8 params × │  │ YAML │  │ (Ollama /  │   │
                               │  │  3 niveaux  │  │ 10   │  │  OpenAI)   │   │
                               │  │ + 7 règles  │  │files │  │            │   │
                               │  │ + tendances)│  │      │  │            │   │
                               │  └──────┬──────┘  └──┬───┘  └─────┬──────┘   │
                               │         │            │            │           │
                               │         ▼            ▼            ▼           │
                               │  ┌─────────────────────────────────────────┐  │
                               │  │              WebSocket /ws              │  │
   ┌────────────┐              │  └──────────────────┬──────────────────────┘  │
   │  Frontend   │◀════════════╡                     │                         │
   │  React 18   │  WebSocket  │  ┌──────────┐  ┌────┴─────┐  ┌───────────┐   │
   │  Dashboard  │             │  │PostgreSQL│  │  Redis   │  │  Mosquitto│   │
   │  Scope-like │             │  │ 7 tables │  │  Cache   │  │  MQTT     │   │
   └────────────┘              │  └──────────┘  └──────────┘  └───────────┘   │
                               └──────────────────────────────────────────────┘
```

**6 services Docker** orchestrés via `docker-compose.yml` :

| Service | Image / Build | Port | Rôle |
|---------|--------------|------|------|
| Mosquitto | `eclipse-mosquitto:2` | 1883, 9001 | Broker MQTT — transport des données vitales |
| PostgreSQL | `postgres:16-alpine` | 5432 | Persistence — 7 tables (cas, alertes, LLM, feedback, médicaments, événements, fluides) |
| Redis | `redis:7-alpine` | 6379 | Cache temps réel des derniers vitaux par salle |
| Backend | FastAPI (build) | 8000 | API REST + WebSocket + moteur d'alertes + LLM + KB |
| Simulateur | Python (build) | — | Génération physiologique réaliste + replay VitalDB |
| Frontend | React/Vite → Nginx | 3000 | Dashboard scope temps réel |

---

## Stack technique

| Couche | Technologies |
|--------|-------------|
| **Backend** | Python 3.12+ · FastAPI · Pydantic v2 · SQLAlchemy (async) · asyncpg · paho-mqtt · httpx · redis |
| **Frontend** | React 18 · TypeScript · Vite 6 · Canvas API (mini-trends) · WebSocket natif |
| **LLM** | Ollama (llama3.1:8b par défaut) ou OpenAI API (gpt-4o-mini) |
| **Infrastructure** | Docker Compose · Mosquitto MQTT · PostgreSQL 16 · Redis 7 · Nginx |
| **Données** | VitalDB (6 388 cas peropératoires, ~500 Mo parquet) · KB YAML clinique (3 000+ lignes) |
| **Tests** | pytest · 21 tests unitaires (models, alert engine, KB, auth, LLM) |

---

## Fonctionnalités

### Moteur d'alertes (`alert_engine.py`)

- **8 paramètres vitaux** surveillés : FC, PAS, PAD, PAM, SpO2, EtCO2, BIS, T°C
- **3 niveaux d'alerte** par paramètre : info (attention) → warning (vigilance) → critical (action immédiate)
- **7 règles multi-paramètres** : triade hypotension, détresse respiratoire, anesthésie inadéquate, hypovolémie, choc septique, hypothermie profonde, tempête catécholaminergique
- **Détection de tendances** : alerte si chute > 20% d'un paramètre en 5 minutes
- **Hystérésis** : évite les alertes oscillantes (seuil de retour différent du seuil de déclenchement)
- **Seuils adaptatifs** : ajustement KB selon la population (pédiatrie, gériatrie, obstétrique, obèse)

### Simulateur (`simulator/`)

- **5 scénarios physiologiques** : Normal, Hypotension, Désaturation, Anaphylaxie, Hémorragie
- **Modèle PhysioState** : bruit gaussien réaliste, corrélations inter-paramètres
- **Replay VitalDB** : rejeu de vrais cas peropératoires en temps réel ajustable
- Publication MQTT toutes les 5 secondes (vitals, ventilator, BIS, AIVOC)

### Dashboard Frontend

- **Interface scope** : dark theme inspiré GE/Philips, polices médicales
- **Cartes vitaux** : FC, SpO2, PAS/PAD, EtCO2, BIS, T°C avec seuils colorés
- **Mini-trends Canvas** : historique 120 points (10 min) par paramètre
- **Multi-salles** : onglets pour surveiller plusieurs blocs simultanément
- **Panel AIVOC** : propofol (Ce, Cp, Ct) et rémifentanil
- **Panel LLM** : analyse IA contextuelle avec situation, risques, recommandations, confiance
- **Alertes** : bandeau trié par sévérité avec acquittement

### Base de connaissances (KB)

10 fichiers YAML couvrant l'ensemble du périmètre anesthésique :

| Fichier | Lignes | Domaine |
|---------|--------|---------|
| `monitoring_params.yaml` | 478 | Paramètres de monitorage + seuils CHARLES |
| `surgeries.yaml` | 558 | Chirurgies par spécialité (risques, monitorage spécifique) |
| `drugs_anesthesia.yaml` | 406 | Agents anesthésiques, PK, interactions |
| `complications_perop.yaml` | 337 | Complications transversales peropératoires |
| `terrains.yaml` | 331 | Comorbidités par système organique |
| `populations.yaml` | 221 | Populations spécifiques (pédiatrie, gériatrie, obstétrique) |
| `scores_cliniques.yaml` | 183 | Scores (ASA, Mallampati, Lee, Apfel…) |
| `reference_trends.yaml` | 168 | Tendances de référence par population |
| `algorithms.yaml` | 162 | Arbres décisionnels (intubation difficile, anaphylaxie…) |
| `data_sources.yaml` | 155 | Sources de données référencées (VitalDB, MIMIC…) |

### Persistence PostgreSQL

7 tables normalisées : `cases`, `alerts`, `llm_analyses`, `alert_feedback`, `drug_administrations`, `case_events`, `fluid_balance`

### API REST & WebSocket

- **Auth JWT** (HMAC-SHA256) avec rôles IADE / MAR / Admin
- **Authentification obligatoire** : tous les endpoints retournent 401 sans token valide
- **Rate limiting** : `/auth/login` limité à 5 tentatives/minute par IP (protection brute force)
- **CORS configurable** : origines autorisées via `CORS_ORIGINS` dans `.env`
- **CRUD complet** : cas opératoires, alertes, médicaments, événements, bilan liquidien
- **WebSocket bidirectionnel** : push temps réel + commandes (acquittement, analyse LLM)
- **Endpoint LLM** : analyse contextuelle à la demande ou déclenchée par alertes critiques

---

## Démarrage rapide

### Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Docker Compose v2)
- (Optionnel) [Ollama](https://ollama.ai/) pour le LLM local

### Lancement

```bash
# Cloner le projet
git clone <repo-url> charles
cd charles

# Copier et configurer les variables d'environnement
cp .env.example .env
# Éditer .env : JWT_SECRET, POSTGRES_PASSWORD, etc.

# Lancer tous les services
docker compose up --build

# Accéder au dashboard
# → http://localhost:3000
```

### Comptes par défaut

| Utilisateur | Mot de passe | Rôle |
|-------------|-------------|------|
| `iade1`, `iade2` | `charles2026` | IADE |
| `mar1` | `charles2026` | MAR |
| `admin` | `admin2026` | Admin |

> ⚠️ Changer les mots de passe et le `JWT_SECRET` avant tout déploiement.

### Avec LLM local (optionnel)

```bash
# Installer Ollama, puis :
ollama pull llama3.1:8b

# Le backend détecte automatiquement Ollama sur localhost:11434
```

### Avec OpenAI (alternative)

```bash
# Dans .env :
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

### Développement local (sans Docker)

```bash
# Backend
cd services/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd services/frontend
npm install
npm run dev

# Tests
cd charles
pytest tests/ -v
```

---

## Données VitalDB

Le projet utilise [VitalDB](https://vitaldb.net), une base de données ouverte contenant **6 388 cas opératoires** avec données vitales continues haute résolution.

- **Téléchargement** : `vitaldb/download_fast.py` — téléchargeur parallèle (4 workers)
- **Format** : fichiers Parquet individuels dans `vitaldb/cases/`
- **Taille** : ~500 Mo pour les 6 388 cas
- **Replay** : `services/simulator/simulator/replay.py` — rejeu sur MQTT en temps réel

> **Licence** : CC BY-NC-SA 4.0 — Usage académique/recherche uniquement.
> Citation : Lee HC, Jung CW. Vital Recorder—a free research tool for automatic recording of high-resolution time-synchronised physiological data from multiple anaesthesia devices. *Scientific Reports* 2018;8:1527.

---

## Intégration LLM

CHARLES intègre un LLM pour fournir des analyses contextuelles aux IADE :

1. **Prompt système** : définit CHARLES comme copilote IADE expert
2. **Enrichissement KB** : le prompt inclut les données pertinentes de la kb clinique
3. **Données vitales** : paramètres actuels + alertes actives + contexte cas
4. **Réponse structurée JSON** : `situation`, `risques[]`, `recommandations[]`, `confiance` (0-100)

**Déclenchement** :
- Automatique sur alerte critique
- Manuel via bouton "Analyser la situation" dans le dashboard
- Via API `POST /rooms/{room_id}/analyze`

**Providers supportés** :
- **Ollama** (défaut) : `llama3.1:8b` en local — gratuit, pas de données envoyées
- **OpenAI** : `gpt-4o-mini` — plus performant, nécessite clé API

---

## API REST

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/auth/login` | Authentification → token JWT |
| `GET` | `/auth/me` | Utilisateur courant |
| `POST` | `/cases` | Créer un cas opératoire |
| `GET` | `/cases` | Lister les cas (filtres : room_id, status) |
| `GET` | `/cases/{id}` | Détails d'un cas |
| `PUT` | `/cases/{id}/end` | Terminer un cas |
| `POST` | `/cases/{id}/drugs` | Enregistrer une administration médicamenteuse |
| `POST` | `/cases/{id}/events` | Enregistrer un événement peropératoire |
| `POST` | `/cases/{id}/fluids` | Enregistrer entrée/sortie liquidienne |
| `GET` | `/cases/{id}/fluids` | Bilan entrées/sorties |
| `GET` | `/alerts` | Lister les alertes (filtres : room_id, case_id, level) |
| `PUT` | `/alerts/{id}/acknowledge` | Acquitter une alerte |
| `POST` | `/rooms/{id}/analyze` | Déclencher analyse LLM pour une salle |
| `GET` | `/kb/status` | État de la knowledge base |
| `GET` | `/health` | Health check |
| `WS` | `/ws` | WebSocket temps réel (push vitaux + alertes + LLM) |

---

## Tests

```bash
# Lancer la suite complète (21 tests)
pytest tests/test_backend.py -v

# Couverture
# - Modèles Pydantic (validation, sérialisation)
# - Moteur d'alertes (seuils, multi-paramètres, hystérésis, BIS, tendances)
# - KB Loader (chargement YAML, extraction seuils, contexte LLM)
# - Auth (login, token, vérification)
# - LLM Engine (construction prompt)
```

---

## Structure du projet

```
charles/
├── docker-compose.yml          # Orchestration 6 services
├── init.sql                    # Schéma PostgreSQL (7 tables)
├── .env                        # Variables d'environnement
├── .gitignore                  # Exclusions Git
│
├── kb/                         # Knowledge Base clinique (10 fichiers YAML)
│   ├── monitoring_params.yaml
│   ├── surgeries.yaml
│   ├── drugs_anesthesia.yaml
│   ├── complications_perop.yaml
│   ├── terrains.yaml
│   ├── populations.yaml
│   ├── scores_cliniques.yaml
│   ├── reference_trends.yaml
│   ├── algorithms.yaml
│   └── data_sources.yaml
│
├── services/
│   ├── backend/                # FastAPI + Alert Engine + LLM + KB + Auth
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py         # Application FastAPI (REST + WS + MQTT)
│   │       ├── alert_engine.py # Moteur d'alertes temps réel
│   │       ├── llm_engine.py   # Intégration LLM (Ollama / OpenAI)
│   │       ├── kb_loader.py    # Chargeur Knowledge Base YAML
│   │       ├── database.py     # Couche PostgreSQL async
│   │       ├── auth.py         # Authentification JWT
│   │       ├── models.py       # Modèles Pydantic
│   │       ├── config.py       # Configuration (pydantic-settings)
│   │       └── mqtt_consumer.py# Consumer MQTT thread-safe
│   │
│   ├── frontend/               # React 18 + Vite + TypeScript
│   │   ├── Dockerfile
│   │   ├── package.json
│   │   └── src/
│   │       ├── App.tsx
│   │       ├── scope.css       # Dark theme scope anesthésie
│   │       ├── types.ts        # Types TypeScript
│   │       ├── hooks/
│   │       │   └── useCharlesWS.ts  # Hook WebSocket persistant
│   │       └── components/
│   │           ├── RoomMonitor.tsx   # Dashboard salle complet
│   │           ├── VitalCard.tsx     # Carte paramètre vital + trend
│   │           ├── AlertPanel.tsx    # Bandeau alertes
│   │           ├── LLMPanel.tsx      # Panel recommandations IA
│   │           └── StatusBar.tsx     # Barre de statut
│   │
│   └── simulator/              # Générateur de données physiologiques
│       ├── Dockerfile
│       ├── requirements.txt
│       └── simulator/
│           ├── main.py         # 5 scénarios (normal, hypoTA, désat, anaphylaxie, hémorragie)
│           └── replay.py       # Replay VitalDB → MQTT
│
├── tests/
│   └── test_backend.py         # 21 tests pytest
│
└── vitaldb/                    # Données VitalDB
    ├── download_fast.py        # Téléchargeur parallèle
    ├── watchdog_download.py    # Watchdog auto-relance
    ├── catalog.yaml            # Index des 6 388 cas
    └── cases/                  # Fichiers parquet (~500 Mo)
```

---

## Roadmap

- [x] Architecture microservices Docker Compose
- [x] Broker MQTT + consumer temps réel
- [x] Moteur d'alertes multi-niveaux avec hystérésis
- [x] Dashboard React scope-like (dark theme, mini-trends)
- [x] Simulateur 5 scénarios + replay VitalDB
- [x] Knowledge Base clinique (10 fichiers YAML, 3 000+ lignes)
- [x] Intégration LLM (Ollama / OpenAI)
- [x] Persistence PostgreSQL (7 tables)
- [x] API REST CRUD complète
- [x] Auth JWT avec rôles
- [x] RBAC complet — tous les endpoints protégés
- [x] Rate limiting brute force (`/auth/login`)
- [x] CORS configurable par environnement
- [x] HEALTHCHECK sur les 3 services Docker
- [x] Auto-reconnect MQTT avec backoff exponentiel
- [x] Téléchargement VitalDB 6 388 cas
- [x] Tests unitaires (21 tests)
- [ ] CI/CD (GitHub Actions)
- [ ] Tests d'intégration end-to-end
- [ ] Monitoring Prometheus/Grafana
- [ ] Mode SSPI (post-opératoire)
- [ ] Application mobile IADE

---

## Licence

Projet académique — MBA1 Epitech Technology & Management.

Données VitalDB sous licence **CC BY-NC-SA 4.0**.

---

<p align="center">
  <sub>CHARLES v0.1 — conçu par un IADE, pour les IADE.</sub>
</p>
