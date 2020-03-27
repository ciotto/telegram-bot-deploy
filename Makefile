SHELL := /bin/bash

init:
	pip install -r requirements-dev.txt

test:
	pytest --cov=bot_ci

travis:
	pytest --cov=bot_ci
