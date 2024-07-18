VENV := .venv/
BIN := $(VENV)/bin
PYTHON := $(BIN)/python
SHELL := /bin/bash
.PHONY: help
help: ## Show this 
	@egrep -h '\s##\s' $(MAKE`FILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: venv
venv: ## Make a new virtual environment
	python3 -m venv $(VENV) && source $(BIN)/activate

.PHONY: install
install: venv ## Make venv and install requirements
	$(BIN)/pip install --upgrade -r requirements.txt

freeze: ## Pin current dependencies
	$(BIN)/pip freeze > requirements.txt

migrate: ## Make and run migrations
	doppler run -- $(PYTHON) /workspaces/the-dozens-django/thedozens/manage.py makemigrations
	doppler run -- $(PYTHON) /workspaces/the-dozens-django/thedozens/manage.py migrate

.PHONY: run
backup-services-up: ## Pull and start the Docker Postgres container in the background
.PHONY: run
backup-services-up: ## Pull and start the Docker Postgres container in the background
	docker-compose up -d

db-shell: ## Access the Postgres Docker database interactively with psql. Pass in DBNAME=<name>.
	docker exec -it container_name psql -d $(DBNAME)

.PHONY: test
test: ## Run tests
	$(PYTHON) manage.py test application --verbosity=0 --parallel --failfast

.PHONY: run
run: ## Run the Django server
	doppler run -t $(DOPPLER_TOKEN) -- $(PYTHON) thedozens/manage.py runserver

start:
	install migrate run ## Install requirements, apply migrations, then start development server
.PHONY: schema-check
schema-check:
	doppler run -- $(PYTHON) /workspaces/the-dozens-django/thedozens/manage.py spectacular --file schema.yaml --validate --fail-on-warn

schema: schema-check
	doppler run -- $(PYTHON) /workspaces/the-dozens-django/thedozens/manage.py spectacular --file schema.yaml 