SHELL := /bin/bash

ENV_FILE    ?= config/.env
ENV_SAMPLE  := config/.env.sample

.PHONY: age-up age-down age-logs age-psql \
        preprocess pipeline-a pipeline-b compare \
        install env

# Copy .env.sample to .env the first time. Idempotent.
env:
	@if [ ! -f $(ENV_FILE) ]; then \
	  cp $(ENV_SAMPLE) $(ENV_FILE); \
	  echo "[env] created $(ENV_FILE) from $(ENV_SAMPLE) - edit it before running pipelines"; \
	fi

install:
	pip install -e .

age-up: env
	docker compose --env-file $(ENV_FILE) -f docker/docker-compose.yml up -d

age-down:
	docker compose --env-file $(ENV_FILE) -f docker/docker-compose.yml down

age-logs:
	docker compose -f docker/docker-compose.yml logs -f age

age-psql:
	docker compose -f docker/docker-compose.yml exec age \
	  psql -U $${POSTGRES_USER:-lightrag} -d $${POSTGRES_DATABASE:-lightrag_db}

preprocess:
	python -m scripts.preprocess.run_preprocess

pipeline-a: env
	python -m scripts.run_pipeline_a

pipeline-b: env
	python -m scripts.run_pipeline_b

compare: env
	python -m scripts.compare.run_compare
