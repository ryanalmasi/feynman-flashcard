COMPOSE := docker compose -f infra/docker-compose.yml

.PHONY: env db db-down db-reset db-psql migrate api

env:
	./scripts/dev-env.sh

db:
	$(COMPOSE) up -d --wait
	@APP_PASSWORD="$$(grep -E '^APP_PASSWORD=' infra/.env | head -1 | cut -d= -f2-)"; \
	if ! $(COMPOSE) exec -T -e PGPASSWORD="$$APP_PASSWORD" db psql -h db -U feynman_app -d feynman -c 'select 1' >/dev/null 2>&1; then \
		echo "DB volume was initialised with different credentials or before infra/.env existed. Run 'make db-reset' (DELETES all local DB data)."; \
		exit 1; \
	fi

db-down:
	$(COMPOSE) down

db-reset:
	$(COMPOSE) down -v
	$(MAKE) db

db-psql:
	$(COMPOSE) exec db psql -U feynman_migrator -d feynman

migrate:
	cd api && uv run alembic upgrade head

api:
	cd api && uv run uvicorn --factory feynman_api.main:create_app --reload --host 127.0.0.1 --port 8000
