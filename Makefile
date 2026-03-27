.PHONY: up down logs migrate test seed-mock train-ml

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

migrate:
	cat scripts/init_db.sql | docker compose exec -T postgres psql -U postgres -d vyrus -v ON_ERROR_STOP=1

test:
	docker compose exec fastapi sh -lc "python -m pytest -q || echo 'No tests configured yet (Phase 1 scaffold).'"

seed-mock:
	docker compose exec -w /app ml python /app/scripts/seed_mock_training_data.py

train-ml:
	docker compose exec -w /app/ml ml python train.py --city_id delhi --mlflow_experiment_name vyrus_flood_v1 --force-register
