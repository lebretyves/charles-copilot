Drop the production TLS files here for `docker-compose.prod.yml`.

Required filenames:

- `charles.crt`
- `charles.key`

The frontend container runs with `CHARLES_TLS_MODE=provided` in production-like mode and will fail fast if these files are missing.
