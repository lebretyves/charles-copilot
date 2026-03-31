# Production Notes

This repository now includes a production-like path in addition to the local HTTPS stack.

## What exists now

- `docker-compose.yml`
  Local HTTPS stack for development on `https://localhost:3000`
- `docker-compose.prod.yml`
  Production-like stack with:
  - frontend exposed on `80/443`
  - backend kept internal to Docker
  - provided TLS certificates
  - file-based secrets for backend, worker, simulator and mosquitto

## Required files before a production-like run

Create `ops/secrets/` with:

- `jwt_secret`
- `default_password`
- `admin_password`
- `mqtt_password`

Create `ops/certs/` with:

- `charles.crt`
- `charles.key`

Copy `.env.prod.example` to `.env.prod` and replace every placeholder.

Keep `localhost,127.0.0.1` in `TRUSTED_HOSTS` unless you also replace the container healthcheck behavior.

## Start

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.prod up --build -d
```

## Stop

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.prod down
```

## Security posture improved by this setup

- TLS terminates at nginx with provided certificates
- backend is not published directly on the host
- trusted hosts are enforced by the API
- prod config rejects dev JWT/password defaults
- secret files are supported for auth, MQTT and optional API keys
- frontend can hide dev-account hints at build time

## Still required before a real deployment decision

- real certificates from a public CA
- external monitoring / log shipping
- tested backup retention and restore drills
- stricter secret distribution than bind-mounted files
- network firewalling and host hardening
- compliance review if data scope leaves public/anonymized datasets
