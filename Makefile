SHELL := /bin/bash

ENV_FILE ?= config/.env

.PHONY: age-up age-down age-logs age-psql \
        preprocess pipeline-a pipeline-b compare \
        install

install:
	pip install -e .

age-up:
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

pipeline-a:
	python -m scripts.run_pipeline_a

pipeline-b:
	python -m scripts.run_pipeline_b

compare:
	python -m scripts.compare.run_compare
