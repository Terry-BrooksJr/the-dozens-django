VENV := .venv
BIN := $(VENV)/bin
PYTHON := $(BIN)/python
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

.PHONY:
migrate: ## Make and run migrations
	doppler run -t $(DOPPLER_TOKEN) -- $(PYTHON) $(PATH_PREFIX)the-dozens-django/thedozens/manage.py makemigrations
	doppler run -t $(DOPPLER_TOKEN) --  $(PYTHON) $(PATH_PREFIX)the-dozens-django/thedozens/manage.py migrate

.PHONY: 
collect:
	doppler run -t $(DOPPLER_TOKEN) -- $(PYTHON) $(PATH_PREFIX)the-dozens-django/thedozens/manage.py collectstatic --no-input

.PHONY: test
test: ## Run tests
	doppler run -t $(DOPPLER_TOKEN) -- $(PYTHON) manage.py test application --verbosity=0 --parallel --failfast

.PHONY: run
run: ## Run the Django server
	doppler run  -- python  thedozens/manage.py runserver

start:
	install migrate run ## Install requirements, apply migrations, then start development server

.PHONY: schema-check
schema-check:
	doppler run -- $(PYTHON) $(PATH_PREFIX)the-dozens-django/thedozens/manage.py spectacular --file schema.yaml --validate --fail-on-warn

schema: schema-check
	doppler run -- $(PYTHON) $(PATH_PREFIX)the-dozens-django/thedozens/manage.py spectacular --file schema.yaml 


.PHONY:
production-server:
	doppler run -t $(DOPPLER_TOKEN) -- $(PYTHON) -m gunicorn --workers=2 --threads=2 thedozens.thedozens.wsgi:application -b :9090: