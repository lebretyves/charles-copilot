Create plain-text secret files in this folder before using `docker-compose.prod.yml`.

Recommended files:

- `jwt_secret`
- `default_password`
- `admin_password`
- `mqtt_password`

Optional:

- `openai_api_key`

Keep one secret value per file, without extra formatting.
