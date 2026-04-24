# CHARLES

CHARLES is a waveform-focused MVP for anesthesia monitoring replay and analysis.

Current scope:
- replay of public VitalDB cases
- high-frequency waveform streaming (ECG, pleth, invasive arterial pressure, CO2, airway pressure, EEG)
- real-time dashboard
- alert engine
- optional LLM commentary layer

This repository is currently positioned as a **research / demo MVP on public and anonymized data**.
It is **not** documented as a production hospital deployment.

## Why this README changed

The project had a strong technical base, but the documentation mixed several stories:
- anesthesia copilot
- hospital production platform
- local demo
- waveform replay sandbox

The repository is now documented around the real MVP:

`public waveforms -> replay -> monitoring UI -> analysis -> exportable observations`

## MVP scope

What CHARLES does today:
- loads VitalDB metadata and waveform assets
- replays waveform-enabled cases through the simulator
- pushes live vitals and wave chunks over MQTT and WebSocket
- renders a scope-like frontend
- stores alerts, manual actions, fluid balance and LLM analyses in PostgreSQL

What CHARLES does not claim today:
- hospital interoperability
- certified medical device behavior
- HDS-ready hosted platform
- HL7/FHIR integration

## Data scope

For this MVP, the project is handled as a workflow on **public / anonymized waveform datasets**.

Important:
- if you later connect real patient data, pseudonymized exports, hospital feeds, or care workflows, the security and compliance perimeter changes immediately
- in that case, revisit CNIL / RGPD / HDS requirements before any deployment decision

## Architecture

```
simulator -> MQTT -> FastAPI backend -> WebSocket -> React monitor
                           |-> PostgreSQL
                           |-> Redis
                           |-> optional LLM / RAG
```

Main services:
- `services/backend`: FastAPI API, auth, alerts, catalog, LLM bridge, DB access
- `services/frontend`: React monitor and admin screens
- `services/simulator`: synthetic scenarios and VitalDB replay
- `learning/`: VitalDB learning scaffolding (segment manifests, weak labels, future training pipelines)
- `kb/`: YAML clinical knowledge base
- `vitaldb/`: open dataset files and download helpers
- `tests/`: backend and replay tests

## Repo layout

```
charles/
  docker-compose.yml
  start.py
  start.sh
  start.bat
  learning/
  kb/
  services/
    backend/
    frontend/
    simulator/
  tests/
  vitaldb/
    README.md
    download_waveforms.py
    cases/
    waveforms/
```

## Quick start

### Prerequisites

- Docker Desktop with Compose v2
- optional: Ollama if you want local LLM analysis

### Local Python tooling

Docker is enough for the main monitoring stack, but local scripts outside containers now use layered requirement files:

- backend runtime image: `services/backend/requirements.txt`
- learning datasets, DVC snapshots and MLflow helpers: `learning/requirements.txt`
- local fine-tuning extras on top of the learning stack: `learning/finetune/requirements.txt`
- optional load testing helpers: `tests/requirements.txt`

Typical installs:

```bash
py -m pip install -r learning/requirements.txt
py -m pip install -r learning/finetune/requirements.txt
py -m pip install -r tests/requirements.txt
```

Important:
- `learning/finetune/requirements.txt` intentionally does not pin `torch`
- install the CPU or CUDA wheel that matches your machine before launching local SFT

### Start the stack

```bash
cp .env.example .env
docker compose up --build
```

Open:
- frontend: `http://localhost:3000`
- local gateway: `http://localhost:8080`
- backend docs: `http://localhost:8000/docs`
- Grafana: `http://localhost:3001`
- Prometheus: `http://localhost:9090`
- MLflow: `http://localhost:5000`

Notes:
- the dev stack currently serves the frontend over plain HTTP locally
- the production-like compose path remains the HTTPS/TLS entry point with certificates

### Production-like stack

The repository now also includes a stricter production-like path:

```bash
cp .env.prod.example .env.prod
docker compose -f docker-compose.prod.yml --env-file .env.prod up --build -d
```

This mode expects:
- real certificate files in `ops/certs/`
- secret files in `ops/secrets/`
- HTTPS-only origin/host settings

Operational notes:
- [Production guide](/d:/projet%20Iade/charles/ops/PRODUCTION.md)
- [Backup script](/d:/projet%20Iade/charles/ops/backup-postgres.ps1)
- [Restore script](/d:/projet%20Iade/charles/ops/restore-postgres.ps1)

### Launcher scripts

- Windows: `python start.py` or `start.bat`
- macOS / Linux: `./start.sh`

## Default accounts

Development-only accounts:

| Login | Password | Role |
| --- | --- | --- |
| `iade1` | `charles2026` | IADE |
| `iade2` | `charles2026` | IADE |
| `mar1` | `charles2026` | MAR |
| `admin` | `admin2026` | Admin |

Notes:
- passwords can be overridden with `CHARLES_DEFAULT_PASSWORD` and `CHARLES_ADMIN_PASSWORD`
- `JWT_SECRET` must be changed before sharing the stack
- the production-like frontend build hides these demo hints automatically

## LLM mode

LLM analysis is optional.

Supported providers:
- Ollama
- OpenAI API

Default local model:

```bash
ollama pull meditron:7b
```

Behavior:
- live waveform/vitals updates do **not** wait for the LLM anymore
- critical-alert LLM analysis is launched in the background
- manual analysis remains available from the UI

## VitalDB dataset

The waveform MVP is centered on VitalDB.

Useful paths:
- metadata: `vitaldb/clinical_metadata.csv`
- numeric case files: `vitaldb/cases/`
- waveform files: `vitaldb/waveforms/`

Waveform replay is used for:
- ECG
- plethysmogram
- invasive arterial pressure
- CO2
- airway pressure
- EEG

See `vitaldb/README.md` for dataset notes.

## Learning scaffold

The repository now includes a first learning scaffold under `learning/`.

Step 1 implemented today:
- dataset manifest for VitalDB waveform windows
- reusable segment index builder
- weak labels inferred from numeric windows

Step 2 implemented today:
- feature extraction for waveform and numeric windows
- baseline problem inference on top of segment features
- JSONL exports for feature datasets and ranked problem hypotheses

Step 3 implemented today:
- structured LLM dataset builder on top of problem outputs
- deterministic `train/eval` split for local fine-tuning and local evals
- reference JSON targets aligned with the CHARLES analysis schema

Fine-tuning step 1 implemented today:
- review pack generation for human validation / correction

Fine-tuning step 2 implemented today:
- export to local `chat` and `instruction` SFT formats
- `gold_reference.jsonl` to preserve reviewer-aligned targets

Fine-tuning step 3 implemented today:
- local Meditron run scaffold generation
- prepared text datasets ready for TRL SFT
- `run_config.json`, environment validation, and launch scripts

This stage is meant to prepare future local training on:
- waveform morphology
- problem scoring/classification
- explanatory LLM outputs

Important:
- the scaffold now prepares the run pack for local LoRA/QLoRA
- it still does not improve the model until you provide a local Transformers-compatible Meditron directory and launch training
- an Ollama tag like `meditron:7b` remains the runtime target, not the training input format

## Security level for this MVP

Because the current scope is public/anonymized data, the immediate priority is **coherent MVP security**, not full hospital compliance.

Implemented or expected for the MVP:
- bearer auth on API routes
- stronger password hashing than plain SHA-256
- JWT secret in environment
- file-based secret support for JWT, user passwords, MQTT and optional API keys
- MQTT credentials in environment
- audit-style logs for login, manual writes, simulator control and websocket access
- explicit HTTP 503 on write persistence failure instead of false success
- lightweight operational metrics on backend activity and waveform flow
- local HTTPS by default, plus a production-like compose path with provided TLS certs

Still not a hospital-ready security posture:
- no MFA
- no external secret vault
- no RBAC administration UI
- no formal incident runbook in repo
- no HDS hosting statement

## Operational metrics

This MVP now exposes lightweight live metrics to make regressions visible early.

Available today:
- login success / failure counters
- monitoring update count
- forwarded waveform chunk count
- alert and critical-alert counters
- LLM request / success / failure / timeout counters
- WebSocket connection and command counters
- simulator command counter
- average LLM latency

Endpoints and UI:
- `GET /health` returns uptime plus last monitoring / waveform activity timestamps
- `GET /metrics` returns the full live counter snapshot
- `GET /metrics/prometheus` exposes a Prometheus scrape endpoint for authenticated clinical/admin roles
- the Admin system tab surfaces these metrics directly in the UI

## Admin capabilities

The admin area now groups the runtime controls added in this iteration:

- live alerting rule inspection, save and reset through `/admin/alerting/config`
- user listing and account creation through `/admin/users`
- learning registry, DVC snapshot and MLflow tracking visibility through `/admin/learning/status`
- live operational metrics and runtime health from the frontend admin tabs

## API highlights

- `POST /auth/login`
- `GET /health`
- `GET /metrics`
- `GET /metrics/prometheus`
- `GET /rooms`
- `GET /rooms/{room_id}`
- `POST /rooms/{room_id}/analyze`
- `GET /scenarios/catalog`
- `GET /scenarios/catalog/waveforms`
- `POST /scenarios/search`
- `POST /simulator/control`
- `GET /admin/alerting/config`
- `PUT /admin/alerting/config`
- `POST /admin/alerting/config/reset`
- `GET /admin/users`
- `POST /admin/users`
- `GET /admin/learning/status`

## What was fixed for this cleanup

- LLM model references are aligned on `meditron:7b`
- admin password mismatch in launcher/docs is corrected
- user-initiated write endpoints now fail loudly on DB persistence failure
- critical-alert LLM work is backgrounded so live updates stay responsive
- health endpoint exposes DB persistence failures and current data scope
- admin page now shows the active data scope and LLM model hint
- `.env.example` now matches the actual runtime settings

## HL7 / FHIR

Not needed for this MVP.

You only need HL7/FHIR if you decide to connect CHARLES to:
- hospital information systems
- real monitor exports
- admission / encounter / order systems
- clinical documentation workflows

Until then, keeping the project focused on waveform datasets is the right move.

## Tests

Backend tests:

```bash
pytest tests/test_backend.py -q
```

All backend and waveform regression tests:

```bash
pytest tests -q
```

Frontend type-check:

```bash
cd services/frontend
node_modules/.bin/tsc -b
```

Frontend production build:

```bash
cd services/frontend
npm run build
```

Frontend end-to-end smoke tests:

```bash
cd services/frontend
npm run test:e2e
```

Optional backend load test helpers:

```bash
py -m pip install -r tests/requirements.txt
locust -f tests/load_test.py
```

## Golden waveform tests

Waveform generation now has deterministic golden references for smoke/regression validation.

Files:
- `tests/golden_waveforms.json`
- `tests/test_metrics_and_golden.py`

These tests verify:
- waveform chunk shape and lengths
- exact deterministic output for seeded synthetic cases
- operational metrics behavior

## CI

GitHub Actions now runs:
- backend + golden tests
- frontend type-check and build
- Playwright smoke tests against a full stack

Workflow file:
- `.github/workflows/charles-ci.yml`

## Next sensible steps

1. Add dataset provenance / licensing notes per source.
2. Add a small export/report flow for waveform sessions.
3. Continue splitting remaining CSS and simulator scenario blocks by feature.
4. Add retention / archival strategy for long waveform sessions.
5. Revisit compliance only if the project leaves the public-anonymized dataset perimeter.
